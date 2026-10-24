# Evidence Hierarchy

The rule that makes everything else trustworthy: **a claim without a citable level is not a fact.**

---

## The levels

| Level | Name | What it is | May it conclude? |
|---|---|---|---|
| **L0** | Runtime proof | A log line from a running BDS; a `BF_TEST_RESULT` record; a captured server response | **Yes — the only authority** |
| **L1** | Type definitions | The target version's `index.d.ts` for each `@minecraft/*` module | Yes, for API surface |
| **L2** | JSON Schema | Official `bedrock-schemas` package, pinned to a version | Yes, for file structure |
| **L3** | Official documentation | Microsoft Learn, minecraft.net docs | Yes, for intent and semantics |
| **L4** | Official samples | Microsoft's `bedrock-samples` / `minecraft-samples` repos | Yes, for idiom |
| **L5** | Verified community case | A reproducible case **with a source manifest** | Yes, scoped to the cited version |
| **L6** | Third-party mod | Someone's shipped `.mcaddon` / `.mcpack` | **No** — reference only |
| **L7** | Articles and blogs | Tutorials, forum posts, videos | **No** — a lead only |
| **L8** | Model memory | What the model "remembers" | **Forbidden entirely** |

---

## Conflict resolution

Higher level always wins. No exceptions.

```
L0  beats everything
L1  beats L2..L8
L2  beats L3..L8
...
L6/L7 can never beat anything, including another L6/L7 — they are not evidence.
```

A concrete example that happens constantly:

```
L7 says:  "use poly_mesh for custom models"
L2 says:  poly_mesh is [Deprecated] in the pinned schema
L0 says:  the model loads and renders with cubes+bones

→ Verdict: cubes+bones. The L7 claim is wrong for this version.
```

If you had trusted L7 you would ship a model that produces content errors on load.

---

## Why L8 is banned

Model memory is not merely unreliable — it is **systematically** unreliable in a way that is hard
to detect, because the output looks confident and syntactically plausible.

Typical failures:

| Memory says | Reality |
|---|---|
| `format_version: "1.20.0"` | The target version expects a different pair of versions per file type |
| Component `minecraft:destructible_by_mining` with a flat number | It expects an object with `seconds_to_destroy` |
| `"minecraft:block"` as the identifier prefix | Namespaced identifiers are required; the namespace is yours, not `minecraft` |
| A script API method that existed in 1.20 | Renamed or removed in the target module version |
| `poly_mesh` for geometry | Deprecated; triggers content errors |

Every one of these produces a file that **parses**, sometimes even **loads**, and then
**silently does nothing**. That is the worst possible failure mode: no error to chase.

The ban is therefore absolute. If a fact cannot be cited to L1–L7, the correct output is
"I need to look this up", followed by an actual lookup.

---

## How to record evidence

Per claim:

```yaml
- claim: "custom blocks can drop a specific item"
  level: L2
  source: "bedrock-schemas@1.26.50/block_components.json"
  selector: "minecraft:loot"
  verified_at: "2026-01-15T10:22:00Z"
  note: "loot table path is relative to the BP root"
```

Per runtime proof:

```yaml
- claim: "the block breaks in survival with a netherite pickaxe"
  level: L0
  source: "evidence/bds-A.log:11842"
  excerpt: "[INFO] block at 100,64,100 was broken by probe_bot"
  test_id: ore_breaks
```

The excerpt matters. A path alone is not reproducible by a reader who cannot access your machine;
the excerpt is the part that survives.

---

## Evidence bundles

A stage-3 evidence bundle is a single file per project:

```
projects/<id>/evidence/
├── bundle.yaml           # the claims above
├── sources.json          # what was fetched, with revisions and hashes
└── excerpts/             # raw snippets, so the bundle is self-contained
    ├── schema-loot.json
    └── log-ore_breaks.txt
```

Rules:

- **Every fact used in the implementation appears in the bundle.**
- **Sources are pinned by revision or hash**, not by URL alone — URLs drift.
- **Excerpts are stored**, not referenced. A link is not evidence; a copy is.
- If a source is unavailable at review time, the bundle must still be readable.

---

## Practical lookups

These are the lookups you will do most often. Bookmark the *habit*, not the paths —
paths differ per deployment.

```bash
# what version variables exist
cat registry/runtime.json
cat registry/compatibility.json

# what a block component actually looks like
python3 -m json.tool schemas/block_components.json | less

# what the API surface is for a module
grep -A5 "class Player" types/@minecraft/server/index.d.ts

# what the official samples do for a comparable feature
grep -rl "minecraft:loot" samples/ | head
```

---

## Enforcement

Every `SKILL.md` in this framework contains a "forbidden" section that names L8 explicitly.
The gate is social and procedural, not automatic — which is why it is stated so bluntly:

> **If you cannot cite it, you do not know it.**
> Not knowing is fine. Guessing is not.