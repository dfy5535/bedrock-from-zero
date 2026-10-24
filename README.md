# Bedrock Flow

> An evidence-driven **pipeline for building Minecraft Bedrock Add-Ons with AI agents** —
> and the reason it actually ships: every stage is gated by real runtime proof, never by "looks fine".

Bedrock Flow is not an Add-On template. It is a **process framework**: a set of skills, gates,
and small tools that force an AI agent (or a human) to produce Bedrock Add-Ons that are
*verifiably* correct on a real server — not merely valid JSON.

---

## It runs

This is not a document collection. `tools/` contains working implementations:

| File | What it does | Lines |
|---|---|---|
| `tools/bootstrap.sh` | Bare Ubuntu -> working lab, one command | 240 |
| `tools/shctl.py` | Slot/ownership board: claim, start, bot, stop, reap | 696 |
| `tools/netbot.js` | Headless player over nethernet, discovery + connect | 186 |

```bash
git clone <this-repo> bedrock-flow && cd bedrock-flow
sudo ./tools/bootstrap.sh

shctl board
shctl claim alice
shctl start alice      # -> prints game port AND discovery port
shctl bot  alice probe1
shctl stop alice
```

[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md) walks that path end to end,
including the one verification that catches a silently broken world decoder.

---

## If you are an AI agent, start here

**[`docs/AI-START.md`](docs/AI-START.md)** — routing table, load order, hard constraints, and the
verdict vocabulary. Read it before you touch anything.

The three documents that matter most, in order:

1. **[`FIRST-ADDON.md`](docs/FIRST-ADDON.md)** — a complete working Add-On, every file in full
2. **[`GENERATOR.md`](docs/GENERATOR.md)** — the fast declarative path and its 12 silent gaps
3. **[`EVIDENCE-HIERARCHY.md`](docs/EVIDENCE-HIERARCHY.md)** — why you cannot answer from memory

---

## Start here — build one, verified, in 12 steps

If you want to know whether this framework is worth your time, do this first:
**[`docs/FIRST-ADDON.md`](docs/FIRST-ADDON.md)** — a complete custom block Add-On, every file
shown in full, from empty directory to a `.mcaddon` you have proven on a real server.

It includes the real failure modes that produce **no error message**:

- duplicate UUIDs → one pack silently dropped
- `destructible_by_mining: 0.5` (a number instead of `{ seconds_to_destroy: 0.5 }`)
- `"texture": "textures/blocks/x"` instead of a key into `terrain_texture.json` → checkerboard
- zipping one directory too high → nothing imports
- `minecraft:loot` path with a leading slash → block drops nothing

Read that document before anything else. Everything below explains *why* it is built that way.

---

## The problem this solves

Ask any LLM to build a Bedrock Add-On and you get the same three failures, every time:

1. **Confident hallucination.** `format_version` invented, component names guessed,
   `poly_mesh` used in a version that deprecated it. The JSON parses. The pack loads. The block is invisible.
2. **No runtime verification.** The agent declares "done" after `mct validate`. The world never
   saw the entity. Nobody ran it.
3. **No isolation.** Two agents (or two humans) share one BDS, one world, one port.
   They silently overwrite each other's world files and disconnect each other's bots.

Bedrock Flow attacks all three with **process**, not with more knowledge in the prompt.

---

## Core idea: evidence is ranked, memory is banned

The single most important artifact in this repo is the **evidence hierarchy**.
Every factual claim about Bedrock must cite a level, and a lower level can never override a higher one.

| Level | Source | Rule |
|---|---|---|
| **L0** | Runtime proof — a running BDS log line, `BF_TEST_RESULT` JSON | **The only source of truth.** No L0 evidence ⇒ the feature is unverified. |
| **L1** | The target version's `index.d.ts` type definitions | Authoritative for API surface |
| **L2** | Official JSON Schemas | Authoritative for file structure |
| **L3** | Official documentation (Microsoft Learn / minecraft.net) | Authoritative for intent |
| **L4** | Official samples (bedrock-samples, minecraft-samples) | Authoritative for idiom |
| **L5** | Reproducible community cases | Accepted **with** a source manifest |
| **L6** | Third-party mods for reference | Reference only, never a conclusion |
| **L7** | Blog posts / articles | A lead, never a conclusion |
| **L8** | Model memory | **Forbidden.** |

The consequence is blunt and deliberate: **an agent is not allowed to answer from memory.**
Before writing any JSON, it must resolve the version against local registry files and open the schema.
See [`docs/EVIDENCE-HIERARCHY.md`](docs/EVIDENCE-HIERARCHY.md).

---

## The pipeline

```
                ┌──────────────────────────────────────────────┐
                │  bedrock-engineer   ← orchestrator, no code   │
                └──────────────────────────────────────────────┘
   intake → runtime resolve → evidence → version → skeleton → implement
                                                                   │
              ┌────────────────────────────────────────────────────┘
              ▼
        validate (4 layers) → build → runtime (BDS) → test (A/B/C) → package → report
              │                                            │
              └──────────── any FAIL ──→ bedrock-debug ─────┘
                                        (minimal patch only)
```

Every stage is **serial**. A stage that does not PASS does not hand off.
See [`docs/PIPELINE.md`](docs/PIPELINE.md).

### Routing table (what the orchestrator delegates to)

| Situation | Skill |
|---|---|
| Need an official basis for an API / component / format | `bedrock-research` |
| Version selection, stable-vs-preview arbitration | `bedrock-version` |
| Missing official sources, manifest refresh | `bedrock-sources` |
| Project skeleton, Design Contract, git | `bedrock-project` |
| Custom block / item / entity | `bedrock-block`, `bedrock-item`, `bedrock-entity` |
| Script API, UI, event logic | `bedrock-script` |
| Validation, build, build manifest | `bedrock-build` |
| BDS install / start / stop / world / logs | `bedrock-bds` |
| Three-layer test and machine-readable results | `bedrock-test` |
| Any FAIL: locate and patch minimally | `bedrock-debug` |
| Packaging and artifacts | `bedrock-package` |
| Quality pass on in-game experience | `bedrock-experience` |
| Texture / pixel art / model authoring | `bedrock-pixel-art`, `design-model`, `mc-art-engine` |

25 skills ship in [`skills/`](skills/). Each `SKILL.md` answers exactly six questions:
**when to use it, what to check first, which commands, what is forbidden, what it outputs,
and how PASS is defined.** They contain **no Minecraft knowledge** — that is fetched at runtime.

---

## The three-layer test — this is the part that matters

Static validation cannot tell you whether a block is mineable in survival.
Bedrock Flow therefore defines three layers with an explicit honesty boundary:

| Layer | Method | Judgement |
|---|---|---|
| **A** — Static | JSON syntax, schema, paths, UUID uniqueness, TS compile, dependencies | **AUTO** |
| **B** — Server runtime | Load the add-on in a real BDS, drive it with a real headless bot, grep the server log | **AUTO** |
| **C** — Client / visual | A human looks at a real client | **`MANUAL_GATE`** |

**The hard rule: layer C may never be reported as PASS without client evidence.**
The framework will happily return `PARTIAL` instead of lying. That single constraint is what
makes the output trustworthy.

### How layer B actually proves things

Not by trusting the bot's own report. By producing **server-side log evidence**:

```bash
# 1. spawn a real player inside BDS
con('tp "probe_bot" 100 64 100')

# 2. place the target block
con('setblock 100 64 100 mymod:titanium_ore')

# 3. switch to survival, give a real tool, break it with real input packets
#    (block_action: start_break → predict_break), not with /setblock air
con('gamemode survival "probe_bot"')
con('give "probe_bot" minecraft:netherite_pickaxe 1')

# 4. read the verdict out of the BDS log, not out of the bot's stdout
grep -a 'block at 100,64,100' evidence/bds-A.log
```

A machine-readable result line is emitted for every case:

```
BF_TEST_RESULT {"id":"ore_drops","layer":"B","expect":"item_dropped","actual":"item_dropped","result":"PASS"}
```

That line is the only thing that counts. See [`docs/TESTING.md`](docs/TESTING.md).

---

## Multi-worker isolation (the part nobody else has)

A single BDS instance owns exactly **one** wide-area discovery port (`7551` in nethernet).
Therefore **two BDS instances on one host will fight**, and a bot that broadcasts to the default
port will silently join *the wrong server and the wrong world*. This is not a theoretical risk;
it is the single most common way an agent destroys another agent's test run.

Bedrock Flow solves it with an **explicit slot board**:

| Slot | Game port | World | Discovery port | Owner |
|---|---|---|---|---|
| A | 20031 | `bot-world` | auto-detected | worker 1 |
| B | 20041 | `dsh-test` | auto-detected | worker 2 |
| C | 20051 | `spare-world` | auto-detected | overflow |

```bash
shctl board                 # who owns what, right now
shctl claim alice           # take a slot (flock-protected, unique)
shctl start alice           # start that slot's BDS
shctl bot   alice alice_bot # start a bot that is *pinned to alice's* BDS
shctl stop  alice && shctl release alice
```

The crucial detail: the board **auto-detects** each slot's real discovery port and injects it
into the bot as `NETH_DISCOVERY_PORT`. A bot without that variable will join whichever server
won the race for `7551`. See [`docs/SLOT-ISOLATION.md`](docs/SLOT-ISOLATION.md) and
[`tools/shctl.py`](tools/shctl.py).

---

## Three components, one chain of trust

The pipeline rests on three concrete pieces of infrastructure. Each has a dedicated document
because each has a distinct failure mode that will silently produce fake results:

| Component | Role | Doc | Fails by |
|---|---|---|---|
| **Agent layer** | Writes code, drives everything over SSH | [`AGENT-LAYER.md`](docs/AGENT-LAYER.md) | Believing its own stdout |
| **BDS** | The server that witnesses behaviour | [`BDS.md`](docs/BDS.md) | Never being asked to prove anything |
| **Headless bot** | A real player speaking the real protocol | [`BOT.md`](docs/BOT.md) · [`BOT-API.md`](docs/BOT-API.md) | Timing out, joining the wrong world, or cache staleness |

```
AGENT  ──writes──▶  Add-On  ──loads into──▶  BDS  ──observed by──▶  BOT
  │                                            │                     │
  │                                            └──log lines──────────┴──▶ EVIDENCE
  └───────────── cannot declare PASS without ◀──────────────────────────────┘
```

The bot is the *actuator*. The server is the *witness*. The agent is *not allowed to testify*.

That is the whole design in one line: **remove the agent's ability to grade its own homework.**

---

## Repository layout

```
bedrock-flow/
├── skills/                 # 25 process skills (no MC knowledge inside)
│   ├── bedrock-engineer/   # ← orchestrator, start here
│   ├── bedrock-research/
│   ├── bedrock-test/
│   └── ...
├── tools/
│   ├── shctl.py            # slot board: claim / start / bot / stop / release
│   ├── sh-guard.py         # idle reaper (stops abandoned slots)
│   ├── portctl.py          # port lease + segment isolation
│   ├── mcreg.py            # world registry + live bot registry (reads /proc)
│   ├── bf-netbot.js      # headless bot: nethernet discovery + real input packets
│   └── verify-mine.js      # real block-break verification
├── docs/
│   ├── GETTING-STARTED.md      ** install -> server -> bot -> green test
│   ├── AI-START.md             ** for agents: routing, load order, constraints
│   ├── TEMPLATES.md            ★ production-verified code, copy directly
│   ├── PITFALLS-RUNTIME.md     ★ the two bugs that hung the server
│   ├── PITFALLS-TESTING.md     ★ false passes and false failures
│   ├── PITFALLS-ENVIRONMENT.md ★ 14 measured environment traps
│   ├── FIRST-ADDON.md          ** build a verified block in 12 steps
│   ├── GENERATOR.md            declarative generation + 12 silent gaps
│   ├── PROJECT-ANATOMY.md      what a real project looks like once it grows
│   ├── SCRIPTS.md              Script API wiring and traps
│   ├── EVIDENCE-HIERARCHY.md   L0-L8 evidence levels; memory is banned
│   ├── PIPELINE.md             14-stage gate pipeline + anti-pattern catalogue
│   ├── TESTING.md              three-layer testing, layer C is MANUAL_GATE
│   ├── SLOT-ISOLATION.md       multi-worker isolation, discovery-port injection
│   ├── DESIGN-CONTRACT.md      the design.yaml contract
│   ├── AGENT-LAYER.md          how an AI agent actually runs this pipeline
│   ├── BDS.md                  running the server that proves things
│   ├── BOT.md                  the headless bot: concept, layers, 12 pitfalls
│   └── BOT-API.md              bot API reference, ready to copy
├── CONTRIBUTING.md
├── SECURITY.md
└── LICENSE
```

---

## Quick start

```bash
# 0. prerequisites: Linux, python3, node 18+, tmux, a Bedrock Dedicated Server
git clone <repo> && cd bedrock-flow

# 1. point the framework at your hosts (see docs/CONFIG.md)
cp config/example.env config/local.env && $EDITOR config/local.env

# 2. verify the environment
python3 tools/portctl.py verify
python3 tools/shctl.py board

# 3. take a slot and bring up a server
python3 tools/shctl.py claim alice
python3 tools/shctl.py start alice

# 4. run a bot pinned to your own slot
./tools/wbot.sh alice alice_bot

# 5. ask the board what is true
python3 tools/shctl.py board
python3 tools/mcreg.py bot
```

If a stage cannot prove itself, the framework reports `FAIL` or `PARTIAL`.
It will not report success it cannot evidence.

---

## What is deliberately *not* included

This repository was extracted from a working private deployment. The following were removed
on purpose, and you should supply your own:

- Hostnames, IP addresses, credentials, SSH keys, proxy endpoints, panel domains.
- Bedrock Dedicated Server binaries and world saves (licensing + size).
- Official Microsoft sample repositories (fetch them yourself; a manifest format is provided).
- Private orchestration skills tied to a specific deployment (`model-sync`, `tool-map`).
- Any production project's assets, textures, or content.

What remains is the **method**: the skill contracts, the gates, the isolation model,
and the verification tooling.

---

## Honest limitations

This framework does not remove the hard parts of Bedrock development. It makes failure visible.

- **Layer C is manual.** Visual correctness still needs eyeballs. The framework refuses to fake it.
- **Discovery ports are host-global.** `nethernet` binds a single discovery port per host;
  the slot board works around this, it does not abolish it.
- **Public reachability.** Bots connect over local discovery; exposing a world to real external
  players requires your own gateway/NAT work.
- **Version drift.** Every version number in these docs is a *last-known* value.
  Always re-read your registry before acting. That rule is enforced in the skills themselves.
- **The skills are prompts, not code.** Their quality depends on the model executing them.
  The gates are what keep that honest.

---

## License

MIT — see [`LICENSE`](LICENSE).

*Bedrock Flow is an independent project. Not affiliated with or endorsed by Mojang or Microsoft.
"Minecraft" is a trademark of Mojang Synergies AB.*