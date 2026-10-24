# The Design Contract (`design.yaml`)

Written **before** any pack file exists. This is the highest-leverage rule in the pipeline.

---

## Why it exists

Without a contract, the agent's plan lives in a context window: invisible, unversioned, and
rewritten silently every time the conversation shifts. Three failures follow immediately:

1. **Drift.** The implementation quietly diverges from what was asked.
2. **No acceptance criteria.** "Done" becomes an opinion instead of a check.
3. **No review surface.** A human cannot review a plan that was never written down.

`design.yaml` fixes all three by turning intent into a **file under version control** that both
the agent and the human can be held to.

---

## Required fields

```yaml
project: titanium-ore           # slug, matches the directory name
goal: "A mineable ore that drops raw titanium in survival"
runtime: "1.26.51.1"            # resolved triple, not a guess

artifacts:                      # one or more
  - block
  - item
  - recipe
  - texture

inputs:
  namespace: mymod              # your namespace, never "minecraft"

outputs:                        # exact paths that will exist at the end
  - behavior_pack/blocks/titanium_ore.json
  - behavior_pack/items/raw_titanium.json
  - behavior_pack/recipes/titanium_ingot.json
  - resource_pack/textures/blocks/titanium_ore.png
  - resource_pack/textures/items/raw_titanium.png

dependencies:
  - "@minecraft/server@2.10.0"  # only if scripts are used

tests:                          # every test case, with an expected outcome
  - id: ore_placeable
    layer: B
    expect: "setblock succeeds and testforblock confirms the block"
  - id: ore_breaks
    layer: B
    expect: "breaking with a netherite pickaxe succeeds"
  - id: ore_drops
    layer: B
    expect: "breaking yields minecraft:raw_titanium"
  - id: ore_visual
    layer: C
    expect: "texture renders with the correct tint in a real client"

acceptance:                     # how the overall verdict is computed
  - "A and B all PASS"
  - "C remains MANUAL_GATE until client evidence exists"
```

---

## Field-by-field guidance

### `goal`

One sentence describing **observable behaviour**, not implementation.

| Bad | Good |
|---|---|
| "add a titanium block" | "A titanium ore that generates underground and drops raw titanium when mined with an iron-tier pickaxe or better" |
| "make a cool sword" | "A sword with 8 attack damage that sets the target on fire for 3 seconds on hit" |

The good versions are testable. The bad versions are not.

### `runtime`

The **resolved triple**, copied out of the registry after arbitration — never typed from memory.

```yaml
runtime: "1.26.51.1"
samples_baseline: "bedrock-samples@1.26.50.4"
schema_package: "@minecraft/bedrock-schemas@1.26.50"
script_api_cap: "@minecraft/server@2.10.0"
```

Recording all four prevents the single most common silent failure: mixing a stable runtime with a
preview schema and wondering why a component is rejected.

### `outputs`

**Exact paths**, not directories. This is what makes the "no stray files" validation layer
possible: anything produced that is not listed here is a bug, and anything listed that is missing
is a failure.

### `tests`

Every test needs `id`, `layer`, and `expect`. No exceptions — an untested output is an
unverified output, and an unverified output is not deliverable under this framework.

| Layer | Use for |
|---|---|
| `A` | File/schema/UUID/compile assertions |
| `B` | Anything that requires the server to actually run |
| `C` | Anything that requires eyes on a client |

### `acceptance`

State the verdict algebra explicitly. Default:

```yaml
acceptance:
  - "A: all cases PASS"
  - "B: all cases PASS, zero MISSING"
  - "C: PASS or MANUAL_GATE (never fake a pass)"
  - "overall: PASS only if A and B pass"
```

If a project legitimately cannot reach `PASS` (e.g. it is a backend-only script with no visuals),
say so here rather than quietly marking layer C as passed.

---

## Anti-patterns

| Anti-pattern | Why it breaks |
|---|---|
| Writing `design.yaml` after the code | You are documenting what you built, not what was asked |
| Listing a directory instead of paths | "No stray files" becomes unenforceable |
| Omitting `tests` "because it's simple" | Every unverified output fails at the worst moment |
| Leaving `runtime` as `"latest"` | Unpinned = unreproducible |
| Marking layer C as `AUTO` | Guarantees a fake pass |
| Adding fields nobody reads | Contract rot; keep it minimal and enforced |

---

## Lifecycle

```
stage 4   written     → reviewed by the human, committed
stage 5-7 unchanged   → implementation is measured against it
stage 12  amended     → ONLY by explicit human approval, with a note on why
stage 14  referenced  → the report cites the contract version it satisfied
```

The contract is not immutable — requirements change. What is forbidden is **silent** change.
Any amendment gets a line in the report:

```
CONTRACT AMENDMENT 2026-01-15: added ore_drops test after discovering the loot table
was not being exercised by ore_breaks.
```

---

## A complete minimal example

```yaml
project: glow-torch
goal: "A torch variant that emits light level 14 and can be placed on walls"
runtime: "1.26.51.1"
samples_baseline: "bedrock-samples@1.26.50.4"
schema_package: "@minecraft/bedrock-schemas@1.26.50"

artifacts: [block]
inputs:  { namespace: mymod }
outputs:
  - behavior_pack/blocks/glow_torch.json
  - resource_pack/textures/blocks/glow_torch.png
  - resource_pack/blocks.json

dependencies: []

tests:
  - id: torch_places
    layer: B
    expect: "place_block succeeds on a wall face"
  - id: torch_light
    layer: B
    expect: "light level at the adjacent air block is 14"
  - id: torch_visual
    layer: C
    expect: "renders as a torch, correct emissive look"

acceptance:
  - "A and B all PASS"
  - "C marked MANUAL_GATE until a client screenshot exists"
```

That is enough to implement, test, and honestly report. Nothing more is needed, and nothing
here is optional.