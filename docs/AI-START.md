# For AI Agents — read this first

You are an AI agent asked to build a Minecraft Bedrock Add-On. This document tells you exactly how
to use this repository, in what order, and what will happen if you skip steps.

Read it fully before doing anything. It is short and it will save you hours.

---

## 0. Your situation

You have:
- this repository (skills, tools, docs)
- a Bedrock Dedicated Server you can start
- a headless bot you can drive
- a shell

You do **not** have:
- reliable memory of Bedrock's format versions, component names, or API signatures
- the ability to see a rendered texture
- permission to say "done" without evidence

The last three are the entire point of this framework. Internalize them now.

---

## 1. Before you write a single file

Run this, in order. Do not skip. Do not reason about the Add-On yet.

```bash
# --- A. Is the harness alive? ---
python3 tools/shctl.py board          # who owns what
python3 tools/portctl.py verify       # port hygiene

# --- B. Can you reach the target? ---
ssh <bds-host> hostname

# --- C. What version are you actually targeting? ---
cat registry/runtime.json
cat registry/compatibility.json
```

**If any of these fail, stop.** A broken harness makes every downstream result noise. Agents that
skip this spend an hour debugging a MOD that was fine, because the bot was pointed at the wrong
slot.

---

## 2. How to load the skills

Skills live in `skills/<name>/SKILL.md`. Each one has YAML front-matter:

```yaml
---
name: create-block
description: <when this is the right tool — read this to route>
whenToUse: <the phrasings and situations that should trigger it>
---
```

### Routing

| The user asks for | Load |
|---|---|
| "make a mod", "add a thing", anything end-to-end | `bedrock-engineer` (the orchestrator) |
| a custom block | `create-block` → then `bedrock-block` for detail |
| a custom item | `create-item` → then `bedrock-item` |
| a custom mob / entity | `create-mob` → then `bedrock-entity` |
| script logic, UI, events | `bedrock-script` |
| "it doesn't work", "pack won't load" | `bedrock-debug` |
| "is this API available in version X" | `bedrock-research` |
| "which version should I target" | `bedrock-version` |
| validate / build | `bedrock-build` |
| start / stop / world / logs | `bedrock-bds` |
| test it | `bedrock-test` |
| package it | `bedrock-package` |
| texture / pixel art / model | `bedrock-pixel-art`, `design-model`, `mc-art-engine` |
| "make it feel good" | `bedrock-experience` |

**When in doubt, load `bedrock-engineer` first.** It contains the full delegation table and the
serial stage order.

### The two rules for skills

1. **A skill contains process, never Minecraft knowledge.** If you find yourself copying a
   `format_version` out of a skill, you are using it wrong — read the registry instead.
2. **Follow the skill's "forbidden" section literally.** Every item in it was earned from a real
   failure that cost hours.

---

## 3. The order you must work in

```
1. ROUTE      pick skills, load them
2. ORIENT     harness check (§1 above)
3. RESEARCH   resolve version triple; open schema + d.ts; cite a level per fact
4. CONTRACT   write design.yaml BEFORE any pack file
5. IMPLEMENT  generate or hand-write, citing the schema per file
6. VERIFY     A (static) → B (runtime) → C (gate)
7. DEBUG      on FAIL only: minimal patch, one variable, re-enter at 6
8. PACKAGE    .mcaddon into artifacts/
9. REPORT     with an evidence row per case and a "not verified" section
```

**Step 4 is not optional.** `design.yaml` converts your plan from something in your context window
into a reviewable file. Without it, "done" is an opinion.

**Step 7 has a hard rule: never rewrite to fix.** One variable at a time, or you cannot attribute
the fix.

---

## 4. Fast path: the generator

For a new block, item, or mob, do not hand-write files. Use `createMinecraftContent`:

```json
{
  "schemaVersion": "1.0.0",
  "namespace": "gems",
  "blockTypes": [
    {
      "id": "ruby_ore",
      "displayName": "Ruby Ore",
      "traits": ["solid"],
      "destroyTime": 3,
      "sounds": "stone",
      "drops": [{ "item": "gems:ruby" }]
    }
  ]
}
```

Then **immediately** run the post-generation checklist in
[`GENERATOR.md`](GENERATOR.md#the-mandatory-post-generation-checklist).

Twelve known gaps produce **silence**. The worst three:

| Gap | What you get |
|---|---|
| Manifest rewrite | BP→RP dependency points at a new UUID that does not exist; `[PACKDEP]` on validate |
| Loot table not wired | Block drops itself instead of your item |
| Unknown field dropped | A feature you "added" produces no files |

An agent that trusts the generator's summary line ships broken content and then blames its own
JSON.

---

## 5. Your hard constraints

These are not style preferences. Each one prevents a specific, observed failure.

| # | Never | Because |
|---|---|---|
| 1 | Answer a Bedrock fact from memory | Guaranteed hallucination; the file parses and silently does nothing |
| 2 | Write code before reading the schema | Wrong field names propagate everywhere |
| 3 | Declare layer B without a `BF_TEST_RESULT` log line | That is a fabricated result |
| 4 | Declare layer C at all | You cannot see a texture. It is `MANUAL_GATE`. Forever. |
| 5 | Rewrite a project to fix one bug | Destroys attribution |
| 6 | Change two variables in one iteration | You learn nothing about which mattered |
| 7 | Start a bot without `NETH_DISCOVERY_PORT` | It joins whichever server won the discovery-port race |
| 8 | Start a second BDS without a slot | World and port corruption |
| 9 | Run `du /` or `find /` on a small host with a server up | OOM kills `sshd`; you lose the machine |
| 10 | Echo a credential to stdout | It lands in logs |
| 11 | Edit the version registry silently | Builds become unreproducible |
| 12 | Invent a CLI subcommand | Silent no-op that reads as success |

For #12: if a subcommand does not exist, emit `UNKNOWN: <subcommand> not implemented` and use a
verified equivalent. Never invent a command and assume it worked because nothing errored.

---

## 6. The verdict vocabulary

```
PASS     evidence shows it works
FAIL     evidence shows it is broken
BLOCKED  the harness cannot measure it
MISSING  the expected result line never appeared
```

`MISSING` counts as `FAIL`.

**`BLOCKED` is not `FAIL`.** This distinction is the hardest judgement call in the framework and
the one agents get wrong most often.

> Before reporting a `FAIL`, prove the harness could have detected a `PASS`.
> If you cannot demonstrate a positive control, the honest verdict is `BLOCKED`.

Real case: an automated run reported two crafting failures. The protocol library returned
`hasCraftingData: true, recipesCount: 0` — it could not parse that version's recipe format. A human
then crafted successfully with a real client. **The MOD was never broken. The test was.**

---

## 7. What "done" means

You may report `PASS` for a case only when:

- [ ] layer A: the file was validated against the **pinned** schema package
- [ ] layer B: a `BF_TEST_RESULT {...}` line exists in the **server log**
- [ ] the evidence row names the log file and a line number or excerpt
- [ ] layer C is explicitly `MANUAL_GATE`, not `PASS`

Your final report must contain a **"not verified"** section. A report that omits its own gaps is
not a report.

```markdown
## Not verified
- texture appearance (layer C, needs a client)
- behaviour under 20+ concurrent players
```

---

## 8. If you get stuck

| Symptom | Look at |
|---|---|
| Pack loads, block does nothing | duplicate UUIDs → `FIRST-ADDON.md` step 1 |
| Block is a purple checkerboard | texture key vs `terrain_texture.json` → `FIRST-ADDON.md` step 3 |
| Block drops nothing | `minecraft:loot` path → `FIRST-ADDON.md` step 4 |
| Nothing imports at all | zip top-level structure → `FIRST-ADDON.md` step 10 |
| Bot joins the wrong world | `NETH_DISCOVERY_PORT` → `SLOT-ISOLATION.md` |
| Bot times out on everything | harness unhealthy → `BOT.md` known-good baseline |
| Everything died, SSH gone | OOM → `BDS.md` resource discipline |
| Generator "did nothing" | one of the 12 gaps → `GENERATOR.md` |
| Test says FAIL but you suspect the harness | `BLOCKED` judgement → `AGENT-LAYER.md` |

---

## 9. Reading order

If you read nothing else, read these three, in this order:

1. **[`FIRST-ADDON.md`](FIRST-ADDON.md)** — a complete working Add-On, every file in full. You can
   copy this and have something that runs.
2. **[`GENERATOR.md`](GENERATOR.md)** — the fast path, and its twelve silent gaps.
3. **[`EVIDENCE-HIERARCHY.md`](EVIDENCE-HIERARCHY.md)** — why you are not allowed to answer from
   memory.

Then, as needed:
- [`AGENT-LAYER.md`](AGENT-LAYER.md) — your role and full obligations
- [`BDS.md`](BDS.md) — running the witness
- [`BOT.md`](BOT.md) / [`BOT-API.md`](BOT-API.md) — driving the actuator
- [`PIPELINE.md`](PIPELINE.md) — the 14 stages in detail
- [`TESTING.md`](TESTING.md) — the three layers
- [`SLOT-ISOLATION.md`](SLOT-ISOLATION.md) — concurrency
- [`DESIGN-CONTRACT.md`](DESIGN-CONTRACT.md) — `design.yaml`

---

## 10. One sentence to remember

> **You are not allowed to grade your own homework.**

The bot is the actuator. The server is the witness. You write the code and read the evidence —
and if the evidence is missing, the answer is "not verified", not "should work".

That single constraint is worth more than every JSON snippet in this repository.