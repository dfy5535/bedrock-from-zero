# Declarative Generation — `createMinecraftContent`

Instead of hand-writing dozens of JSON files, describe the content **once** in a declarative
shape and let Minecraft Creator Tools write the files. This is the fastest correct path, provided
you know exactly where it stops being correct.

> **The rule that governs this entire document:**
> the generator is a *drafting tool*, not an authority. It does not report everything it skipped.
> You must open what it produced and compare it against what you asked for.

---

## When to use this vs. hand-writing

| Situation | Approach |
|---|---|
| New item, block, or mob from a plain description | **Use the generator** — it writes BP + RP + texture + recipe in one call |
| Changing an existing generated file | **Hand-edit** — re-running does not update existing files |
| Custom 3D block shape | Not supported. Hand-write. |
| Custom script behaviour (right-click teleport, etc.) | Generator creates the shell; you add scripting |
| World generation beyond ores | Not fully supported. See the gap list. |

---

## Shape of the call

One call. `outputPath` is the **project folder itself** — not a subfolder.

```json
{
  "schemaVersion": "1.0.0",
  "namespace": "gems",
  "itemTypes": [ ... ],
  "blockTypes": [ ... ],
  "entityTypes": [ ... ],
  "recipes": [ ... ],
  "features": [ ... ]
}
```

All sections are optional. Include only what you need.

---

## Items

```json
{
  "schemaVersion": "1.0.0",
  "namespace": "fungi",
  "itemTypes": [
    {
      "id": "magic_hammer",
      "displayName": "Magic Hammer",
      "traits": ["pickaxe"],
      "tool": { "durability": 500 },
      "weapon": { "damage": 7 },
      "glint": true,
      "color": "#8A5CFF"
    },
    {
      "id": "deluxe_stew",
      "displayName": "Deluxe Stew",
      "traits": ["food"],
      "maxStackSize": 1,
      "food": { "nutrition": 8, "saturation": 1.2 }
    },
    {
      "id": "vine_bow",
      "displayName": "Vine Bow",
      "traits": ["bow"],
      "projectile": { "projectile": "minecraft:arrow", "chargeable": true }
    }
  ],
  "recipes": [
    {
      "id": "magic_hammer",
      "type": "shaped",
      "pattern": ["III", " S ", " S "],
      "key": { "I": "minecraft:iron_ingot", "S": "minecraft:stick" },
      "result": "fungi:magic_hammer"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `traits` | Presets: `pickaxe`, `axe`, `shovel`, `sword`, `food`, `armor`, `bow`, `throwable` |
| `tool.durability` | Number of uses |
| `weapon.damage` | Attack damage |
| `maxStackSize` | 1–64. Food is usually 1 or 16. |
| `food.nutrition` | Hunger points restored |
| `food.saturation` | Saturation modifier |
| `color` | Hex; used to tint the generated icon |
| `glint` | Enchanted shimmer |

`recipes[].pattern` is a 3-row array of strings; a space means "empty". `key` maps each character
to an item identifier.

---

## Blocks

```json
{
  "schemaVersion": "1.0.0",
  "namespace": "gems",
  "itemTypes": [{ "id": "ruby", "displayName": "Ruby", "color": "#D01C3A" }],
  "blockTypes": [
    {
      "id": "ruby_ore",
      "displayName": "Ruby Ore",
      "traits": ["solid"],
      "destroyTime": 3,
      "mapColor": "#8C3A4A",
      "sounds": "stone",
      "drops": [{ "item": "gems:ruby" }]
    }
  ],
  "features": [
    {
      "id": "ruby_ore_feature",
      "spread": {
        "places": [
          {
            "type": "ore",
            "id": "gems:ruby_ore",
            "replacesBlocks": ["minecraft:stone", "minecraft:deepslate"],
            "count": 4
          }
        ],
        "count": 3,
        "heightPlacement": { "type": "range", "min": -32, "max": 16 },
        "biomes": ["overworld"]
      }
    }
  ]
}
```

### Block traits

```
solid  transparent  leaves  log  slab  stairs  fence  wall  door  trapdoor
container  workstation  light_source  gravity  button  lever  pressure_plate
redstone_signal
```

### Sound sets

```
stone  wood  gravel  grass  sand  glass  metal  cloth  snow  coral
```

### Blocks that change state

`states` + `permutations` (growth stages, on/off) require **native Minecraft JSON**, not traits.

---

## Mobs

A working mob spans seven files across both packs. One call writes all of them.

```json
{
  "schemaVersion": "1.0.0",
  "namespace": "swampy",
  "entityTypes": [
    {
      "id": "swamp_goblin",
      "displayName": "Swamp Goblin",
      "traits": ["humanoid", "hostile", "melee_attacker"],
      "behaviors": ["wander", "hide_from_sun", "look_at_player"],
      "health": 16,
      "attackDamage": 3,
      "scale": 0.5,
      "families": ["goblin", "monster"],
      "appearance": {
        "primaryColor": "#4F7A3A",
        "secondaryColor": "#6B4E2E",
        "textureStyle": "organic",
        "eyes": "glowing"
      },
      "drops": [
        { "item": "minecraft:brown_mushroom", "count": { "min": 1, "max": 2 } }
      ],
      "spawning": {
        "biomes": ["swamp"],
        "lightLevel": { "max": 7 },
        "weight": 20,
        "groupSize": { "min": 1, "max": 3 }
      }
    }
  ]
}
```

Files produced: BP entity, RP client entity, geometry, texture, render controller, loot table,
spawn rule.

Use `components` for anything traits do not cover — they are native Minecraft components and
override trait defaults.

---

## The gap list — read this every time

As of Creator Tools 0.17, these are **known and confirmed** deficiencies. Each one silently
produces something that does not work.

### 1. Unknown fields are silently dropped

A misspelled field is not an error. It simply does not appear in the output, so the feature is
missing with no diagnostic. **Check each value you passed against the tool's input schema**, then
open the generated files and confirm it landed.

### 2. A feature can be counted but produce no files

A `features` entry with the wrong shape appears in the summary count but writes nothing. Verify
that `features/` and `feature_rules/` files actually exist for each feature you declared.

### 3. Only ore world generation is complete

Other `spread` placement types, `scatter`, count ranges, and heights of exactly `0` are not
handled. Scatter features use an older layout that validation flags with a `JSONF` warning about a
missing `distribution` field.

### 4. Custom block drops are not wired up

The generator writes `loot_tables/blocks/<id>.json` **but the block does not point to it**, so the
block drops itself instead of your intended item. Fix by adding to the block's `components`:

```json
"minecraft:loot": "loot_tables/blocks/ruby_ore.json"
```

This is the single most common "the generator is broken" report. It is not broken; it is
incomplete, and the missing wire is yours to add.

### 5. Re-running does not update existing files

The generator will not overwrite a file that already exists. To change generated content, **edit
the file by hand**. Re-running is only for new content.

### 6. Mob `drops[].chance` is ignored

The probability is not applied. Add a condition to the entry in
`loot_tables/entities/<id>.json`:

```json
"conditions": [{ "condition": "random_chance", "chance": 0.3 }]
```

For "only when killed by a player":

```json
"conditions": [{ "condition": "killed_by_player" }]
```

### 7. Mob `spawning.timeOfDay` is ignored

For night-only or dark-only spawning, use light level instead:

```json
"lightLevel": { "max": 7 }
```

This produces a `minecraft:brightness_filter`, which does work.

### 8. `population_control` is always `animal`

For a hostile mob, change it to `monster` in `spawn_rules/<id>.json`. For an aquatic mob,
`water_animal`. Otherwise your mob competes for the wrong mob cap and will barely ever spawn.

### 9. Adding to an existing project rewrites both manifests

This is the most damaging gap. The behavior pack's dependency on its resource pack gets a **new
UUID that points at nothing**, and `header.name` is reset.

**Always copy the manifests before you run the generator on an existing project**, then restore:

```bash
cp behavior_packs/*/manifest.json /tmp/bp-manifest.bak
cp resource_packs/*/manifest.json /tmp/rp-manifest.bak
# ... run generator ...
diff /tmp/bp-manifest.bak behavior_packs/*/manifest.json
```

A broken dependency is reported as `[PACKDEP]` by validation. If you see that, this is why.

### 10. Tameable / rideable / breedable config is ignored

The config objects do not apply. Traits always use **bones to tame, wheat to breed, a saddle to
ride**. Edit the generated `minecraft:tameable`, `minecraft:breedable`, and `minecraft:rideable`
components directly.

### 11. Trait component groups can override your components

The `hostile` trait adds a `hostile_angry` group containing its own
`minecraft:behavior.nearest_attackable_target` targeting players. This **replaces** a targeting
component you defined in `components`. Merge your targets into the group's `entity_types` list
instead of defining the component twice.

### 12. No localization is generated

In game, the entity shows as `entity.<namespace>:<id>.name`. You must add the display name
yourself:

```bash
node <debug-addon-skill>/scripts/add-missing-names.mjs <project-folder> \
  --name "swampy:swamp_goblin=Swamp Goblin"
```

---

## The mandatory post-generation checklist

Run this every single time. It takes two minutes and prevents hours.

```bash
# 1. did the manifests survive?
git diff --stat -- '*manifest.json' 2>/dev/null || echo "not a git repo — compare backups"

# 2. are all declared files actually present?
ls behavior_packs/*/blocks/ behavior_packs/*/items/ behavior_packs/*/entities/ 2>/dev/null
ls behavior_packs/*/loot_tables/blocks/ behavior_packs/*/features/ 2>/dev/null
ls resource_packs/*/textures/ 2>/dev/null

# 3. does the block point at its loot table?
grep -L 'minecraft:loot' behavior_packs/*/blocks/*.json

# 4. is the spawn rule's population_control right?
grep -h 'population_control' behavior_packs/*/spawn_rules/*.json 2>/dev/null

# 5. do the UUIDs collide?
grep -rho '[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}' \
  behavior_packs resource_packs | sort | uniq -d

# 6. validate
mct validate --offline
```

Anything from step 3 or 5 that produces output is a real bug you must fix before testing.

---

## Why this document exists

The generator is genuinely useful — it produces seven correct files for a mob in one call, which
would take an hour by hand. But every one of the twelve gaps above produces **silence**: no error,
no warning, just a thing that does not work.

An agent that trusts the summary line will ship broken content and then debug its own JSON for an
hour. An agent that runs the checklist will catch it in two minutes.

> **Treat the generator as a fast first draft written by a confident intern.
> You still have to review the diff.**