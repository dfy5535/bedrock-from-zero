# The Agent Layer — how an AI actually runs this pipeline

This document describes the **orchestration layer**: how an AI agent sits on top of these tools,
what its actual workflow is, and what it is forbidden from doing.

---

## What the agent layer is

```
┌──────────────────────────────────────────────┐
│  Control host (agent container)              │
│  ├─ skills/         process instructions     │
│  ├─ ssh aliases     → the other hosts        │
│  └─ LLM backend     reasoning                │
└───────────────┬──────────────────────────────┘
                │ ssh
                ▼
┌──────────────────────────────────────────────┐
│  Compute/BDS host                            │
│  ├─ BDS instances (slots)                    │
│  ├─ bot tooling                              │
│  └─ registries, evidence, artifacts          │
└──────────────────────────────────────────────┘
```

The agent **does not** run the model on the game host. It writes code on the control host, drives
remote actions over SSH, and reads evidence back.

This separation is not cosmetic:

| Concern | Why separated |
|---|---|
| Memory | A BDS plus a model on one 1 GB VPS is an OOM guarantee |
| Blast radius | The agent can be reset without touching worlds or saves |
| Egress | The control host may need different network reachability than the game host |
| Evidence | Logs live on the host that produced them |

---

## The single most important architectural rule

> **The agent must not be able to convince itself that it succeeded.**

Everything in this framework exists to enforce that. Concretely:

1. The agent may not answer from memory (see `EVIDENCE-HIERARCHY.md`).
2. The agent may not declare layer B without a log line.
3. The agent may not declare layer C at all.
4. The agent's own stdout is not evidence.

If you take nothing else from this repository: **an agent's self-report is never a test result.**

---

## The agent's actual working loop

```
   ┌─────────────────────────────────────────────────┐
   │ 1. ORIENT                                       │
   │    read the registry, check the slot board,     │
   │    confirm the harness is healthy               │
   └────────────────────┬────────────────────────────┘
                        ▼
   ┌─────────────────────────────────────────────────┐
   │ 2. RESEARCH                                     │
   │    resolve version triple, fetch schema + d.ts, │
   │    cite a level per fact                        │
   └────────────────────┬────────────────────────────┘
                        ▼
   ┌─────────────────────────────────────────────────┐
   │ 3. CONTRACT                                     │
   │    write design.yaml — before any pack file     │
   └────────────────────┬────────────────────────────┘
                        ▼
   ┌─────────────────────────────────────────────────┐
   │ 4. IMPLEMENT                                    │
   │    emit files, cite the schema per file         │
   └────────────────────┬────────────────────────────┘
                        ▼
   ┌─────────────────────────────────────────────────┐
   │ 5. VERIFY                                       │
   │    A (static) → B (runtime) → C (gate)          │
   └────────────────────┬────────────────────────────┘
                        ▼
              ┌─────────┴─────────┐
          FAIL│                   │PASS
              ▼                   ▼
   ┌──────────────────┐  ┌──────────────────┐
   │ 6. DEBUG         │  │ 7. PACKAGE       │
   │ minimal patch    │  │ + report         │
   │ re-enter at 5    │  │ + record case    │
   └──────────────────┘  └──────────────────┘
```

### Why step 1 exists

Most agent failures are environmental, not intellectual. Before any reasoning about the Add-On:

```bash
# is the harness itself alive?
python3 tools/shctl.py board
python3 tools/portctl.py verify

# can I reach the target?
ssh <bds-host> hostname

# what version am I actually targeting?
cat registry/runtime.json
```

If the harness is broken, every downstream result is noise. Agents that skip this step
routinely spend an hour debugging a MOD that was fine, because the bot was pointed at the wrong
slot or the discovery port was stale.

### Why step 3 exists

The Design Contract converts intent from something in a context window into a **file**. This is
what makes step 5 falsifiable: there is a written claim to test against, rather than a feeling
that the output "looks right".

### Why step 6 is restricted

```
❌ "the test failed, let me rewrite the whole script"
✅ "the test failed; reproduce it, isolate one variable, patch minimally, re-run stage 5"
```

Whole-project rewrites destroy the ability to attribute a fix. If a patch touches ten things and
the test passes, you have learned nothing about which of the ten mattered.

---

## How the agent talks to the hosts

The control host holds SSH aliases. Keep them symmetric and documented:

```sshconfig
Host control
    HostName <CONTROL_HOST>
    User <user>
    IdentityFile ~/.ssh/id_ed25519

Host bds
    HostName <BDS_HOST>
    Port 20030
    User root
    IdentityFile ~/.ssh/id_ed25519

Host slots
    HostName <SLOT_HOST>
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519

Host egress
    HostName <EGRESS_HOST>
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Rules:

- **Key-based only** inside the agent container. No passwords in a container that writes logs.
- **Every remote command explicitly names its host.** Never let a path from one host be used as
  a local path by accident — this is a real and frequent error.
- **The agent must be able to say "I cannot reach that host"** rather than retrying forever. A
  dead host is a fact to report, not a problem to grind on.

### When the target is dead

Test from more than one source before concluding anything:

```bash
# from the control host
timeout 8 bash -c 'cat </dev/null >/dev/tcp/<BDS_HOST>/20030' && echo OPEN || echo CLOSED

# from a second host
ssh slots "timeout 8 bash -c 'cat </dev/null >/dev/tcp/<BDS_HOST>/20030' && echo OPEN || echo CLOSED"
```

`No route to host` from multiple independent networks means the instance is down or the IP is
gone. That is a provider-console problem; no amount of local debugging will fix it. Report it and
move on.

---

## Skills as the agent's instruction set

A skill is a Markdown file the agent loads when a task matches its `whenToUse` trigger. Each one
answers six questions:

1. When is this the right tool?
2. What do I check first, in what order?
3. Which commands do I run?
4. What am I forbidden from doing?
5. What files do I produce?
6. How is PASS defined?

**Why Markdown and not code:** the process has to be readable and reviewable by a human, and
editable without a build step. The enforcement comes from the gates, not from the file format.

### The critical content rule

> **Skills contain process. They contain no Minecraft knowledge.**

No `format_version` values, no component names, no API signatures. Those are resolved from the
registry at runtime. If a skill hard-codes them, it becomes a stale source of hallucination —
which is worse than having no skill at all.

```markdown
<!-- ✅ correct -->
Read `registry/runtime.json`. Use the reported stable target.
Any version in this document is a last-observed value; re-read before acting.

<!-- ❌ forbidden -->
Set format_version to "1.21.0" and use minecraft:destructible_by_mining
with a { seconds_to_destroy: 3 } object.
```

The second version works until a version bump, then silently poisons every project.

---

## Forbidden operations for the agent

These are hard rules, each earned from a real failure:

| # | Forbidden | Failure it prevents |
|---|---|---|
| 1 | Answering a Bedrock fact from memory | Guaranteed hallucination, silent breakage |
| 2 | Writing code before reading the schema | Wrong field names throughout |
| 3 | Declaring layer B without a `BF_TEST_RESULT` line | Fake completion |
| 4 | Declaring layer C at all without client evidence | Poisoned result set |
| 5 | Rewriting a project to fix one bug | Lost attribution |
| 6 | Changing two variables in one iteration | Unattributable results |
| 7 | Starting a bot without `NETH_DISCOVERY_PORT` | Bot joins the wrong world |
| 8 | Running a second BDS without a slot | Port and world corruption |
| 9 | Running `du`/`find /` on a small host with a server up | OOM kills sshd, host lost |
| 10 | Echoing a credential into stdout | Leaked via logs |
| 11 | Editing the version registry silently | Unreproducible builds |
| 12 | Inventing a CLI subcommand | Silent no-op that reads as success |

Rule 12 deserves emphasis: if a subcommand does not exist, the correct output is
`UNKNOWN: <subcommand> not implemented` followed by using a verified equivalent. Never invent a
command and then assume it worked because nothing errored.

---

## Handling a "BLOCKED" result honestly

This is the hardest judgement call in the whole pipeline.

```
BLOCKED ≠ FAIL ≠ PASS
```

| Verdict | Means |
|---|---|
| `PASS` | Evidence shows it works |
| `FAIL` | Evidence shows it is broken |
| `BLOCKED` | The **harness** cannot measure it |
| `MISSING` | Expected result line never appeared |

The trap: a `BLOCKED` on a crafting test gets reported as "MOD crafting is broken", the agent then
"fixes" working code, and the real conclusion — *the bot library cannot parse `crafting_data`* —
is lost.

**Rule: before reporting a FAIL, prove the harness could have detected a pass.**
If you cannot demonstrate a positive control, the honest verdict is `BLOCKED`, and the report
must say the tooling lacks the capability.

Real example worth internalising: an automated run reported two crafting failures. The protocol
library returned `hasCraftingData: true, recipesCount: 0` — it could not parse the version's
recipe format at all. A human then connected with a real phone client and crafted successfully.
The MOD was never broken. **The test was.**

---

## Report template

```markdown
# <project> — acceptance report

## Verdict
overall: PARTIAL
A: PASS (14/14)   B: PASS (9/9, 0 missing)   C: MANUAL_GATE (3 cases)

## Runtime
runtime 1.26.51.1 / samples 1.26.50.4 / schema 1.26.50 / script API 2.10.0

## Evidence
| case | layer | verdict | evidence |
|---|---|---|---|
| ore_placeable | B | PASS | bds-A.log:11840 "block at 100,64,100" |
| ore_drops | B | PASS | bds-A.log:11842 "Item entity spawned" |
| ore_visual | C | MANUAL_GATE | — |

## Blocked
| case | reason |
|---|---|
| craft_via_ui | bot lib returns recipesCount=0 for this version — harness gap, not a MOD defect |

## Not verified
- nothing claimed beyond the rows above
```

The last section is mandatory. A report that omits its own gaps is not a report.

---

## Scaling: one agent, multiple workers

The slot board is what makes concurrency safe. The agent's obligations:

```bash
# claim before doing anything
python3 tools/shctl.py claim alice

# work only inside your slot
python3 tools/shctl.py start alice
eval "$(python3 tools/shctl.py env alice)"   # sets BOT_PORT + NETH_DISCOVERY_PORT

# release when done — always, even on failure
python3 tools/shctl.py stop alice
python3 tools/shctl.py release alice
```

If a run crashes and leaves a slot claimed, `shctl reap` recovers it. Do not manually delete state
files; you will desynchronize the board from reality and the next worker will start a second
server on a live port.