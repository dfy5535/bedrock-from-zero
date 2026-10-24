# The Pipeline

Fourteen serial stages. Each stage has an explicit PASS condition. **No stage hands off on a
non-PASS.** This document is the contract; the per-stage detail lives in `skills/*/SKILL.md`.

---

## Stage map

| # | Stage | Skill | PASS condition |
|---|---|---|---|
| 1 | Intake | `bedrock-engineer` | Request decomposed into **feature / artifact type / target runtime** |
| 2 | Runtime resolve | `bedrock-version` | A resolved triple: `runtime` + `samples baseline` + `schema package` |
| 3 | Evidence retrieval | `bedrock-research` | An evidence bundle with a level (L1–L7) for **every** fact used |
| 4 | Skeleton | `bedrock-project` | `design.yaml` exists with all required fields |
| 5 | Implement | `bedrock-block` / `-item` / `-entity` / `-script` | Artifacts exist **and** cite their schema |
| 6 | Validate | `bedrock-build` | Four validation layers run; missing layers marked `N/A`, never silently skipped |
| 7 | Build | `bedrock-build` | A build manifest with hashes |
| 8 | Runtime up | `bedrock-bds` | BDS listening; discovery port detected and recorded |
| 9 | Test A | `bedrock-test` | Static assertions all pass |
| 10 | Test B | `bedrock-test` | Every case emits `BF_TEST_RESULT {...}` from **server logs** |
| 11 | Test C | `bedrock-test` | Marked `MANUAL_GATE` — **or** backed by real client evidence |
| 12 | Debug loop | `bedrock-debug` | Minimal patch applied; re-run from stage 6 |
| 13 | Package | `bedrock-package` | `.mcaddon` / `.mcpack` produced into `artifacts/` |
| 14 | Report | `bedrock-engineer` | `reports/<id>-orchestration.md` with a reproducibility path per step |

---

## Stage 1 — Intake

Decompose the request into three orthogonal facts:

- **Feature**: what must be true in the world. ("a titanium ore that drops raw titanium")
- **Artifact type**: Block / Item / Entity / Script / UI / Animation, one or more.
- **Target runtime**: an explicit version, or "current stable per registry".

Anything ambiguous is resolved by asking, **not** by assuming. A wrong artifact type sends the
whole pipeline down the wrong branch and wastes every later stage.

> Anti-pattern: "make me a cool sword mod" → accepted immediately.
> Correct: → item + script + recipe + texture; runtime resolved from registry; acceptance
> criteria written down before any file is created.

---

## Stage 2 — Version arbitration

Read the local registry, do not recall it:

```bash
cat registry/runtime.json          # current stable + preview targets
cat registry/compatibility.json    # which combos are legal
```

Emit a **triple**, and never mix stable with preview on any axis:

```
runtime        : 1.26.51.1
samples        : bedrock-samples@1.26.50.4
schema package : @minecraft/bedrock-schemas@1.26.50
script API cap : @minecraft/server 2.10.0
```

Mixing axes is the second most common source of "it validates but does nothing".
If the user names a version that disagrees with the registry, arbitrate with `bedrock-version`
and record the decision. **Never silently edit the registry.**

---

## Stage 3 — Evidence retrieval

Produce a bundle, not a memory. For each fact you intend to rely on, record:

```yaml
- claim: "custom blocks support the mineable component"
  level: L2
  source: bedrock-schemas/1.26.50/block_components.json
  path_sha: <hash>
```

Rules:

- **L8 (model memory) is forbidden.** If you cannot cite L1–L7, you do not have the fact.
- An L6/L7 source may *suggest* an approach; it may never *conclude* one.
- Community cases (L5) are accepted only with a source manifest.

---

## Stage 4 — Skeleton and the Design Contract

`design.yaml` is written **before** any pack file. This is the single highest-leverage rule in
the whole pipeline: it converts "the agent's plan" from an implicit thing in its context window
into a reviewable artifact.

```yaml
project: titanium-ore
goal: "Mineable ore that drops raw titanium in survival"
runtime: "1.26.51.1"
artifacts: [block, item, recipe, texture]
inputs:  { namespace: mymod }
outputs:
  - behavior_pack/blocks/titanium_ore.json
  - resource_pack/textures/blocks/titanium_ore.png
dependencies:
  - "@minecraft/server@2.10.0"
tests:
  - id: ore_placeable
    layer: B
    expect: "setblock succeeds and block appears in testforblock"
  - id: ore_drops
    layer: B
    expect: "breaking with netherite pickaxe yields raw_titanium"
  - id: ore_visual
    layer: C
    expect: "texture renders with correct tint in client"
acceptance:
  - "A and B all PASS"
  - "C marked MANUAL_GATE until client evidence exists"
```

See [`DESIGN-CONTRACT.md`](DESIGN-CONTRACT.md).

---

## Stages 5–7 — Implement, validate, build

Implementation is delegated by artifact type. Every generated JSON file cites its schema path
in a header comment or a sibling `.source.json`. Then four validation layers:

| Layer | Checks | Missing-layer policy |
|---|---|---|
| 1. File | exists, parses, correct path, no stray files | FAIL |
| 2. Schema | validated against the **pinned** schema package | FAIL |
| 3. Consistency | UUIDs unique across BP/RP, manifest dependencies resolvable, versions agree | FAIL |
| 4. Script static | TypeScript compiles, imports resolve against `index.d.ts` | `N/A` if no scripts |

A layer that does not apply is written as `N/A` with a reason. **Silent skipping is a FAIL.**

---

## Stages 8–11 — Runtime and the three-layer test

Bring up BDS in **your** slot only:

```bash
shctl claim alice && shctl start alice
shctl bot alice alice_bot          # bot pinned to alice's discovery port
```

Then run the layers. Layer B is the one that has value; see [`TESTING.md`](TESTING.md).

---

## Stage 12 — Debug loop

Rules that keep debugging from becoming rewriting:

1. **Reproduce first.** A failure without a reproduction is not a bug report.
2. **Minimal patch only.** No whole-project rewrites.
3. **One variable at a time.** Never change version *and* code *and* world in one iteration —
   you lose the ability to attribute the fix.
4. **Re-enter at stage 6.** After a patch, re-validate and re-test; do not jump to packaging.
5. **Record the case.** A new failure class becomes a `cases/` entry so the next run does not
   rediscover it.

---

## Stages 13–14 — Package and report

```bash
bedrock-flow package     # → artifacts/<project>-<version>.mcaddon
bedrock-flow report      # → reports/<project>-orchestration.md
```

The orchestration report must contain, for every stage: **which skill ran, its verdict,
and a path or command that reproduces the evidence.** "It looked right" is not a report.

---

## Anti-pattern catalogue

These are the failure modes the pipeline exists to prevent. Each one has been observed in
production and each one is explicitly forbidden in a `SKILL.md`.

| Anti-pattern | Why it fails | Enforced by |
|---|---|---|
| Write code first, check docs later | Guarantees hallucinated field names | stage 3 before stage 5 |
| Trust `mct validate` as "done" | Schema-valid ≠ works in world | stage 10 mandatory |
| Report visual PASS without a client | Poisons the entire result set | layer C `MANUAL_GATE` |
| Rewrite the project to fix one bug | Destroys working parts, loses attribution | stage 12 minimal patch |
| Two agents sharing one BDS | Mutual world corruption | slot board |
| Copy a community snippet as authority | L6/L7 is not evidence | evidence hierarchy |
| Reuse an old fix without checking version | Silent incompatibility | stage 2 re-resolve |
| Invent a CLI subcommand | Silent no-op that looks like success | `UNKNOWN:` protocol |