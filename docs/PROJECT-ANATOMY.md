# Anatomy of a Real Project

`FIRST-ADDON.md` shows the minimum. This document shows what a project looks like once it has grown
past one block — the structure that survives real iteration.

It is derived from production projects, stripped of their content.

---

## The full tree

```
projects/<project_id>/
├── design.yaml                     # the contract (written first)
├── package.json                    # pinned deps, no ranges
├── README.md                       # what this is, and its current verdict
│
├── behavior_pack/
│   ├── manifest.json
│   ├── pack_icon.png
│   ├── blocks/
│   │   └── <name>.json
│   ├── items/
│   │   └── <name>.json
│   ├── entities/
│   │   └── <name>.json
│   ├── loot_tables/
│   │   ├── blocks/<name>.json
│   │   └── entities/<name>.json
│   ├── recipes/
│   │   └── <name>.json
│   ├── features/
│   │   └── <name>.json
│   ├── feature_rules/
│   │   └── <name>.json
│   ├── spawn_rules/
│   │   └── <name>.json
│   ├── functions/
│   │   └── <name>.mcfunction
│   ├── scripts/
│   │   ├── main.js
│   │   └── lib/
│   │       └── <module>.js
│   └── texts/
│       ├── en_US.lang
│       └── zh_CN.lang
│
├── resource_pack/
│   ├── manifest.json
│   ├── pack_icon.png
│   ├── blocks.json                 # block sound / isotropic config
│   ├── textures/
│   │   ├── terrain_texture.json    # block atlas keys
│   │   ├── item_texture.json       # item atlas keys
│   │   ├── flipbook_textures.json  # animated textures
│   │   ├── blocks/
│   │   │   └── <name>.png
│   │   └── items/
│   │       └── <name>.png
│   ├── models/
│   │   ├── entity/
│   │   │   └── <name>.geo.json
│   │   └── blocks/
│   │       └── <name>.geo.json
│   ├── entity/
│   │   └── <name>.entity.json      # client entity, render controllers
│   ├── animations/
│   │   └── <name>.animation.json
│   ├── animation_controllers/
│   │   └── <name>.ac.json
│   ├── render_controllers/
│   │   └── <name>.rc.json
│   ├── attachables/
│   │   └── <name>.json
│   ├── particles/
│   │   └── <name>.json
│   ├── sounds/
│   │   ├── sound_definitions.json
│   │   └── <name>.ogg
│   └── texts/
│       ├── en_US.lang
│       └── zh_CN.lang
│
├── tests/
│   ├── smoke/                      # layer A helpers
│   │   └── lint.sh
│   ├── runtime/                    # layer B scripts
│   │   ├── harness.js
│   │   └── cases/
│   │       └── <case>.js
│   └── expected/                   # golden outputs
│       └── <case>.expected.json
│
├── evidence/                       # raw proof, never edited
│   ├── bds-A.log
│   └── excerpts/
│
├── reports/
│   ├── acceptance.md               # the human-readable verdict
│   └── errors/
│       └── <error-id>.md
│
└── artifacts/
    └── <project>-<version>.mcaddon
```

---

## Why each piece exists

### `design.yaml`

Written before any pack file. It is what makes "done" falsifiable.

```yaml
feature:
  id: ruby_gear
goal: >
  Player mines ruby ore underground, smelts it into ingots, crafts a ruby sword
  with 9 damage and 800 durability. Breaking the ore in survival yields 1-3 rubies.
inputs:
  - mine ruby_ore with an iron pickaxe or better
  - craft ruby_sword from 2 rubies + 1 stick
outputs:
  - ruby ore appears in generated columns between y=-32 and y=16
  - breaking it drops 1-3 items of gems:ruby
  - ruby_sword exists, deals 9 damage, has 800 durability
files:
  bp:
    - blocks/ruby_ore.json
    - items/ruby.json
    - items/ruby_sword.json
    - loot_tables/blocks/ruby_ore.json
    - recipes/ruby_sword.json
    - features/ruby_ore_feature.json
    - feature_rules/ruby_ore_rule.json
  rp:
    - textures/blocks/ruby_ore.png
    - textures/items/ruby.png
    - textures/items/ruby_sword.png
    - texts/en_US.lang
dependencies:
  - "@minecraft/server@2.10.0"
runtime:
  minecraft: 1.26.51.1
  channel: stable
  samples_baseline: bedrock-samples@1.26.50.4
  schema_package: "@minecraft/bedrock-schemas@1.26.50"
tests:
  - id: ore_registers
    layer: A
    expect: block JSON validates against pinned schema
  - id: ore_generates
    layer: B
    expect: scanColumn in a fresh world finds gems:ruby_ore
  - id: ore_drops
    layer: B
    expect: break with iron pickaxe yields 1-3 gems:ruby
  - id: sword_crafts
    layer: B
    expect: recipe resolves and produces gems:ruby_sword
  - id: sword_damage
    layer: B
    expect: attacking a target applies 9 damage
  - id: textures
    layer: C
    expect: ore and sword render with correct art
acceptance:
  - "A and B all PASS, zero MISSING"
  - "C marked MANUAL_GATE until client evidence"
```

### `package.json`

Pinned. No `^`, no `~`, no `latest` — those are not valid module version specs and produce
non-reproducible builds.

```json
{
  "name": "ruby-gear",
  "version": "1.0.0",
  "private": true,
  "devDependencies": {
    "@minecraft/server": "2.10.0",
    "@minecraft/server-ui": "2.0.0",
    "@minecraft/bedrock-schemas": "1.26.50"
  }
}
```

### `texts/*.lang`

The single most-forgotten folder. Without it, players see raw identifiers:

```
# texts/en_US.lang
block.gems:ruby_ore=Ruby Ore
item.gems:ruby=Ruby
item.gems:ruby_sword=Ruby Sword
```

```
# texts/zh_CN.lang
block.gems:ruby_ore=红宝石矿石
item.gems:ruby=红宝石
item.gems:ruby_sword=红宝石剑
```

Both packs need their own `texts/`. A block name defined only in the BP will not display.

### `resource_pack/blocks.json`

Some block-level audio/visual settings live here, not in the block JSON:

```json
{
  "format_version": "1.21.40",
  "gems:ruby_ore": {
    "sound": "stone"
  }
}
```

### `tests/runtime/cases/*.js`

Each case is one assertion, and each emits exactly one result line:

```js
module.exports = {
  id: 'ore_drops',
  layer: 'B',
  async run(lab, assert) {
    lab.con('setblock 100 64 100 gems:ruby_ore')
    await lab.sleep(1000)

    const blk = await lab.getBlock(100, 64, 100)
    assert('placed', blk.name === 'gems:ruby_ore', blk.name)

    // real break, not setblock air
    const drop = await lab.breakBlock({ x: 100, y: 64, z: 100 })
    assert('dropped', drop.entitySpawned === true, JSON.stringify(drop))
  },
}
```

One case, one assertion, one evidence line. That is what makes the report mechanical.

### `reports/errors/<error-id>.md`

Every failure class gets a file, so the next run does not rediscover it:

```markdown
# ERR-0007 — loot table path resolves to nothing

## Symptom
Block breaks, drops nothing. No error in the log.

## Cause
`minecraft:loot` was `"behavior_pack/loot_tables/blocks/ruby_ore.json"`.
Paths are relative to the pack root, so this resolves to nothing.

## Fix
`"minecraft:loot": "loot_tables/blocks/ruby_ore.json"`

## Verification
Break with a real tool, assert `Item entity spawned`.
```

---

## The rules the structure encodes

| Rule | Where it shows up |
|---|---|
| Contract before code | `design.yaml` is at the root, written first |
| Evidence is separate from code | `evidence/` is never edited, only appended |
| Every failure becomes knowledge | `reports/errors/` |
| Tests are data, not prose | `tests/runtime/cases/*.js` emit machine-readable lines |
| Both packs need localization | two `texts/` folders |
| Dependencies are pinned | no ranges in `package.json` |
| Artifacts are outputs, not sources | `artifacts/` is in `.gitignore` |
| Worlds are never in the project | worlds live in the slot, not here |

---

## What is deliberately absent

| Not present | Why |
|---|---|
| `worlds/` | Worlds belong to slots, not projects. Copying a world into a project is how people accidentally ship 200 MB. |
| Build output | `artifacts/` is gitignored |
| Cached node_modules | gitignored |
| Screenshots | Live in `evidence/`, referenced from the report |
| The BDS binary | Never in a project |

---

## Starting from a real project

When you inherit a project you did not write:

```bash
# 1. is there a contract?
test -f design.yaml || echo "NO CONTRACT — write one before touching anything"

# 2. what does it claim to target?
grep -A5 'runtime:' design.yaml

# 3. is that still true?
cat registry/runtime.json

# 4. what is the current verdict?
cat reports/acceptance.md 2>/dev/null || echo "NEVER TESTED"

# 5. does it even validate?
mct validate --offline

# 6. are the manifests sane?
grep -rn 'uuid' behavior_pack/manifest.json resource_pack/manifest.json
```

If step 4 says "never tested", you do not know whether the project works — regardless of how
complete the files look. Treat it as unverified and run layer B before changing anything.

---

## Scaling notes

- **One project, one namespace.** Never mix `gems:` and `ruby:` in one project.
- **One project, one `design.yaml`.** If you need a second contract, you need a second project.
- **Cases accumulate.** A project with 40 test cases is healthier than one with 4, because it
  encodes what you have already learned.
- **Reports are append-only history.** Keep `reports/acceptance.md` for the current run; archive
  older ones with a date suffix rather than overwriting.