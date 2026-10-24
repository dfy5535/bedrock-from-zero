# Hello Block — a complete, copyable Add-On

This document takes you from an empty directory to a working `.mcaddon` that you have **verified
on a real server**. Every file is shown in full. Nothing is elided.

Read it once, then just follow it.

> **Version note.** The version numbers below were correct for one specific target
> (`runtime 1.26.x`, `@minecraft/server 2.10.0`). They are **last-observed values, not eternal
> truths**. Before you build anything real, confirm against your own registry:
>
> ```bash
> cat registry/runtime.json
> cat registry/compatibility.json
> ```
>
> The *structure* is stable. The *numbers* drift.

---

## What we are building

A single custom block:

- identifier: `mydemo:ruby_block`
- shows up in the creative construction menu
- breaks in 0.5 s by hand
- drops itself when mined
- gives you 1 diamond when you interact with it

That is deliberately small. It touches: manifest, block definition, loot table, texture entry,
pack icon, and a packaging step. Everything else is a variation on this shape.

---

## Step 0 — Directory layout

Create exactly this. The names are not arbitrary; the game looks for specific folders.

```bash
mkdir -p mydemo/{behavior_pack,resource_pack}
mkdir -p mydemo/behavior_pack/blocks
mkdir -p mydemo/behavior_pack/loot_tables/blocks
mkdir -p mydemo/resource_pack/textures/blocks
```

```
mydemo/
├── behavior_pack/
│   ├── manifest.json
│   ├── pack_icon.png
│   ├── blocks/
│   │   └── ruby_block.json
│   └── loot_tables/
│       └── blocks/
│           └── ruby_block.json
└── resource_pack/
    ├── manifest.json
    ├── pack_icon.png
    └── textures/
        ├── terrain_texture.json
        └── blocks/
            └── ruby_block.png
```

Two packs. The **behavior pack** (BP) is the logic. The **resource pack** (RP) is the appearance.
A block needs a file in each, or it renders as a missing-texture cube.

---

## Step 1 — Generate four UUIDs

Each pack needs two UUIDs: one for the header, one for the module. **Four total, all distinct.**

```bash
python3 -c "import uuid;[print(uuid.uuid4()) for _ in range(4)]"
```

Example output (yours will differ):

```
7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e01
7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e02
7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e03
7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e04
```

> **Rule:** duplicate UUIDs silently cause one pack to be dropped at load. There is no error
> message. This is the single most common reason "my pack does nothing at all".

---

## Step 2 — `behavior_pack/manifest.json`

```json
{
  "format_version": 2,
  "header": {
    "name": "MyDemo BP",
    "description": "A minimal custom block demo",
    "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e01",
    "version": [1, 0, 0],
    "min_engine_version": [1, 26, 0]
  },
  "modules": [
    {
      "type": "data",
      "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e02",
      "version": [1, 0, 0]
    }
  ]
}
```

Field notes:

| Field | Meaning |
|---|---|
| `format_version: 2` | The **manifest** schema version. Not the pack version. Leave it at 2. |
| `header.uuid` | This pack's identity. Must be unique across everything installed. |
| `header.version` | Your pack's version, `[major, minor, patch]`. |
| `min_engine_version` | Minimum game version that may load this. |
| `modules[].type: "data"` | This is a behavior pack (logic, blocks, loot). |
| `modules[].uuid` | Module identity. Must differ from the header UUID. |

### If you add a script later

Add a second module **and** the dependency:

```json
{
  "format_version": 2,
  "header": {
    "name": "MyDemo BP",
    "description": "A minimal custom block demo with scripting",
    "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e01",
    "version": [1, 0, 0],
    "min_engine_version": [1, 26, 0]
  },
  "modules": [
    {
      "type": "data",
      "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e02",
      "version": [1, 0, 0]
    },
    {
      "type": "script",
      "language": "javascript",
      "entry": "scripts/main.js",
      "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e05",
      "version": [1, 0, 0]
    }
  ],
  "dependencies": [
    { "module_name": "@minecraft/server", "version": "2.10.0" }
  ]
}
```

Three things people get wrong here:

1. **`entry` is relative to the pack root**, and the file must actually exist at that path.
2. **The dependency version is pinned.** `"latest"`, `"^2.10.0"` and `"~2.10.0"` are invalid —
   they are not semver ranges in this context, they are exact module versions.
3. **A script module needs a dependency.** Without it the module is ignored with no error.

---

## Step 3 — `behavior_pack/blocks/ruby_block.json`

This is a real, working block definition:

```json
{
  "format_version": "1.26.0",
  "minecraft:block": {
    "description": {
      "identifier": "mydemo:ruby_block",
      "menu_category": {
        "category": "construction"
      }
    },
    "components": {
      "minecraft:geometry": "minecraft:geometry.full_block",
      "minecraft:material_instances": {
        "*": {
          "texture": "ruby_block",
          "render_method": "opaque"
        }
      },
      "minecraft:destructible_by_mining": {
        "seconds_to_destroy": 0.5
      },
      "minecraft:destructible_by_explosion": {
        "explosion_resistance": 1
      },
      "minecraft:loot": "loot_tables/blocks/ruby_block.json"
    },
    "events": {
      "mydemo:on_use": {
        "run_command": {
          "command": ["say Ruby block used!"]
        }
      }
    }
  }
}
```

### Field notes — every line explained

| Field | Why it matters |
|---|---|
| `"format_version": "1.26.0"` | **File-level** schema version. A string, and it is per file type. Not a number, not the pack version. |
| `identifier` | Must be `namespace:name`. The namespace is **yours** — never `minecraft`. |
| `menu_category.category` | Without this the block does not appear in the creative menu at all. |
| `minecraft:geometry` | `minecraft:geometry.full_block` is a built-in cube. No model file needed. |
| `material_instances["*"]` | The `*` means "all faces". `texture` refers to a key in `terrain_texture.json`, **not** a file path. |
| `render_method: "opaque"` | Solid, no transparency. Use `alpha_test` for cutout textures. |
| `destructible_by_mining` | An **object** with `seconds_to_destroy`. A bare number here is the classic mistake. |
| `minecraft:loot` | Path **relative to the BP root**, no leading slash. |
| `events` | Named event targets. Referenced by components, or triggered by script. |

### The three most common block errors

```json
// ✗ WRONG — a number instead of an object
"minecraft:destructible_by_mining": 0.5

// ✓ RIGHT
"minecraft:destructible_by_mining": { "seconds_to_destroy": 0.5 }
```

```json
// ✗ WRONG — no namespace, or claiming the vanilla one
"identifier": "ruby_block"
"identifier": "minecraft:ruby_block"

// ✓ RIGHT
"identifier": "mydemo:ruby_block"
```

```json
// ✗ WRONG — texture is a file path here
"minecraft:material_instances": {
  "*": { "texture": "textures/blocks/ruby_block", "render_method": "opaque" }
}

// ✓ RIGHT — texture is a KEY into terrain_texture.json
"minecraft:material_instances": {
  "*": { "texture": "ruby_block", "render_method": "opaque" }
}
```

That last one produces a **purple/black checkerboard** block. It loads, it works, it looks broken.
That is layer C territory — no server test will catch it.

---

## Step 4 — `behavior_pack/loot_tables/blocks/ruby_block.json`

Without this, breaking the block drops **nothing**.

```json
{
  "pools": [
    {
      "rolls": 1,
      "entries": [
        {
          "type": "item",
          "name": "mydemo:ruby_block",
          "weight": 1
        }
      ]
    }
  ]
}
```

If you want it to drop a *different* item, change `name`:

```json
{ "type": "item", "name": "minecraft:diamond", "weight": 1 }
```

### Loot table with a count range

```json
{
  "pools": [
    {
      "rolls": 1,
      "entries": [
        {
          "type": "item",
          "name": "minecraft:diamond",
          "weight": 1,
          "functions": [
            {
              "function": "set_count",
              "count": { "min": 1, "max": 3 }
            }
          ]
        }
      ]
    }
  ]
}
```

> The `minecraft:loot` path is **relative to the behavior pack root**:
> `"loot_tables/blocks/ruby_block.json"`. A leading `/`, or `behavior_pack/loot_tables/...`,
> resolves to nothing and the block drops nothing — with no error.

---

## Step 5 — `resource_pack/manifest.json`

```json
{
  "format_version": 2,
  "header": {
    "name": "MyDemo RP",
    "description": "Textures for the minimal custom block demo",
    "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e03",
    "version": [1, 0, 0],
    "min_engine_version": [1, 26, 0]
  },
  "modules": [
    {
      "type": "resources",
      "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e04",
      "version": [1, 0, 0]
    }
  ]
}
```

The only differences from the BP manifest: `type` is **`resources`** (not `data`), and the UUIDs
must be different from the BP's.

---

## Step 6 — `resource_pack/textures/terrain_texture.json`

This file is the bridge between your block's `texture` key and the actual PNG.

```json
{
  "resource_pack_name": "mydemo",
  "texture_name": "atlas.terrain",
  "padding": 8,
  "num_mip_levels": 4,
  "texture_data": {
    "ruby_block": {
      "textures": "textures/blocks/ruby_block"
    }
  }
}
```

| Field | Note |
|---|---|
| `texture_name: "atlas.terrain"` | **Required, exact.** This is what makes it the block atlas. |
| `texture_data.<key>` | The key must match the `texture` value in your block JSON. |
| `textures` | Path to the PNG **without** the `.png` extension. |

`padding` and `num_mip_levels` are conventional; the values above are safe defaults.

---

## Step 7 — The texture itself

```bash
# needs a 16x16 PNG. Any image tool works.
python3 - <<'PY'
import zlib, struct

W = H = 16
r, g, b, a = 200, 30, 60, 255   # ruby red

raw = b''
for y in range(H):
    raw += b'\x00' + bytes([r, g, b, a] * W)

def chunk(tag, data):
    c = struct.pack('>I', len(data)) + tag + data
    return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

png = b'\x89PNG\r\n\x1a\n'
png += chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 6, 0, 0, 0))
png += chunk(b'IDAT', zlib.compress(raw, 9))
png += chunk(b'IEND', b'')

open('mydemo/resource_pack/textures/blocks/ruby_block.png', 'wb').write(png)
print('wrote ruby_block.png')
PY
```

Path must be exactly `textures/blocks/ruby_block.png`.

---

## Step 8 — Pack icons

Both packs want a `pack_icon.png` (any square PNG). Without it the pack shows a blank icon in the
game's pack list — harmless, but sloppy.

```bash
cp mydemo/resource_pack/textures/blocks/ruby_block.png mydemo/behavior_pack/pack_icon.png
cp mydemo/resource_pack/textures/blocks/ruby_block.png mydemo/resource_pack/pack_icon.png
```

---

## Step 9 — Validate before you package

```bash
# 1. every JSON parses
find mydemo -name '*.json' -exec python3 -m json.tool {} > /dev/null \; && echo "JSON OK"

# 2. UUIDs are unique
grep -rho '[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}' mydemo \
  | sort | uniq -d | grep . && echo "DUPLICATE UUIDs!" || echo "UUIDs OK"

# 3. referenced files exist
test -f mydemo/behavior_pack/blocks/ruby_block.json && \
test -f mydemo/behavior_pack/loot_tables/blocks/ruby_block.json && \
test -f mydemo/resource_pack/textures/blocks/ruby_block.png && \
test -f mydemo/resource_pack/textures/terrain_texture.json && echo "paths OK"

# 4. identifier is namespaced and not vanilla
grep -q '"identifier": "mydemo:ruby_block"' mydemo/behavior_pack/blocks/ruby_block.json && echo "identifier OK"
```

If you have the schema package installed, validate against it — that catches field-name typos that
a JSON parser cannot.

---

## Step 10 — Package into a `.mcaddon`

A `.mcaddon` is just a **zip** containing the pack folders:

```bash
cd mydemo
zip -r ../mydemo.mcaddon behavior_pack resource_pack -x '.*' -x '*/.*'
cd ..
ls -lh mydemo.mcaddon
```

Verify the structure inside is right:

```bash
unzip -l mydemo.mcaddon
```

```
  Length      Date    Time    Name
---------  ---------- -----   ----
      312  ...         behavior_pack/manifest.json
      980  ...         behavior_pack/blocks/ruby_block.json
      201  ...         behavior_pack/loot_tables/blocks/ruby_block.json
     1234  ...         behavior_pack/pack_icon.png
      271  ...         resource_pack/manifest.json
      345  ...         resource_pack/textures/terrain_texture.json
     4096  ...         resource_pack/textures/blocks/ruby_block.png
      1234  ...         resource_pack/pack_icon.png
```

> **Critical:** the zip must contain `behavior_pack/` and `resource_pack/` at the **top level**.
> If you zip from one directory too high, you get `mydemo/behavior_pack/...` and the game
> imports nothing. This is the #2 most common packaging failure after duplicate UUIDs.

---

## Step 11 — Load it into a real server and prove it

This is the step that distinguishes this framework from every "here's a template" repo.

```bash
# 1. take a slot (never share a server)
shctl claim alice
shctl start alice

# 2. copy the packs in
cp -r mydemo/behavior_pack/*  /opt/bedrock-flow/slots/A/behavior_packs/mydemo_bp/
cp -r mydemo/resource_pack/* /opt/bedrock-flow/slots/A/resource_packs/mydemo_rp/

# 3. register them on the world
cat > /opt/bedrock-flow/slots/A/worlds/bot-world/world_behavior_packs.json <<'EOF'
[ { "pack_id": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e01", "version": [1,0,0] } ]
EOF

cat > /opt/bedrock-flow/slots/A/worlds/bot-world/world_resource_packs.json <<'EOF'
[ { "pack_id": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e03", "version": [1,0,0] } ]
EOF

# 4. restart so the packs load
shctl stop alice && shctl start alice
```

### The actual assertions

```bash
# did the pack load at all?
grep -i 'mydemo' /opt/bedrock-flow/evidence/bds-A.log

# does the block exist as a registered type?
tmux send-keys -t bdsA 'setblock 100 64 100 mydemo:ruby_block' Enter
sleep 1
grep -a 'block at 100,64,100' /opt/bedrock-flow/evidence/bds-A.log
# expect: "Successfully found the block" on the next testforblock,
#    or  "The block at 100 64 100 could not be found" if it failed

# read it back
tmux send-keys -t bdsA 'testforblock 100 64 100 mydemo:ruby_block' Enter
sleep 1
tail -3 /opt/bedrock-flow/evidence/bds-A.log
```

Or do it properly with the bot, in one script:

```js
lab.con('setblock 100 64 100 mydemo:ruby_block')
await sleep(1000)

const blk = await lab.getBlock(100, 64, 100)
assert('block_registered', blk.name === 'mydemo:ruby_block', blk.name)

// break it with real input packets and check the drop
// (see docs/BOT.md — do not verify mining with setblock air)
```

### What each result means

| Result | Meaning |
|---|---|
| `setblock` says "could not be found" | Block did not register → check `identifier`, manifest, and that the pack loaded |
| `setblock` works, block is invisible | Texture path wrong, or `terrain_texture.json` key mismatch → **layer C** |
| `setblock` works, breaking drops nothing | `minecraft:loot` path wrong |
| Nothing in the log about mydemo | Pack did not load → check UUID duplicates, then `world_*_packs.json` |

---

## Step 12 — The honest report

```markdown
# mydemo — acceptance report

A: PASS (5/5)   B: PASS (3/3, 0 missing)   C: MANUAL_GATE (1)

| case | layer | verdict | evidence |
|---|---|---|---|
| json_valid | A | PASS | all files parsed |
| uuids_unique | A | PASS | 4 distinct |
| paths_exist | A | PASS | 5/5 files present |
| block_registers | B | PASS | bds-A.log:11840 "block at 100,64,100" |
| loot_table_resolves | B | PASS | bds-A.log:11842 "Item entity spawned" |
| texture_renders | C | MANUAL_GATE | needs a client screenshot |

Not verified: texture appearance, model shape, particles.
```

You shipped a real, verified block. That is the whole loop.

---

## Where to go next

Once `hello block` works, every other artifact is the same shape with a different middle:

| Want | Add to BP | Add to RP |
|---|---|---|
| Custom item | `items/ruby.json` | `textures/items/ruby.png` + `item_texture.json` |
| Custom entity | `entities/robot.json` + behavior | geometry + `entity/*.entity.json` + render controller |
| Custom recipe | `recipes/ruby_block.json` | — |
| Custom script logic | second module + `scripts/main.js` | — |
| Custom model | — | `.geo.json` in `models/entity/` |

### The rules that never change

1. **Everything in a behavior pack needs a manifest, and every manifest needs unique UUIDs.**
2. **Every `format_version` is per-file and comes from the schema, not from memory.**
3. **Identifiers are namespaced. Your namespace, never `minecraft`.**
4. **A texture key is a key in `terrain_texture.json`, not a file path.**
5. **Paths inside BC are relative to the pack root. No leading slash.**
6. **`.mcaddon` = zip with the pack folders at the top level.**
7. **A block that loads is not a block that looks right. Layer C always exists.**
8. **Nothing is "done" until a real server said so.**

---

## Self-check: can you reproduce this?

Answer these without looking back:

1. How many UUIDs does a two-pack Add-On need? → **4** (header + module per pack)
2. What is `minecraft:destructible_by_mining` supposed to contain? → **an object with `seconds_to_destroy`**
3. What does `"texture": "ruby_block"` refer to? → **a key in `terrain_texture.json`**
4. Where is the loot path relative to? → **the behavior pack root**
5. What does the zip's top level need to be? → **`behavior_pack/` and `resource_pack/`**
6. Why does a block show a checkerboard? → **texture key/path mismatch — layer C, not a server error**
7. Can a passing server test prove the texture is right? → **No. Never.**

If all seven are clear, you can build the next one without this document.

If any are not, re-read that step — because every one of them is a failure mode that produces
**no error message**, only a thing that silently does not work.