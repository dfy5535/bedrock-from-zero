# Scripts — the Script API

When a block or item needs to *do* something (respond to interaction, track state, spawn effects,
build UI), you need a script module. This document covers the wiring and the traps.

---

## Wiring: three things, all required

A script that never runs is almost always missing one of these.

### 1. The module in the manifest

```json
{
  "format_version": 2,
  "header": {
    "name": "MyDemo BP",
    "description": "with scripting",
    "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e01",
    "version": [1, 0, 0],
    "min_engine_version": [1, 26, 0]
  },
  "modules": [
    { "type": "data",   "uuid": "7c9e6a12-3b4d-4f8a-9e21-5a6b7c8d9e02", "version": [1, 0, 0] },
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

### 2. The dependency — this is the one people forget

Without `dependencies`, the script module is **silently ignored**. No error, no warning, the file
just never executes.

```json
"dependencies": [
  { "module_name": "@minecraft/server", "version": "2.10.0" }
]
```

The version must be an **exact** module version. `"latest"`, `"^2.10.0"`, `"~2.10.0"` are not
valid here — they are not semver ranges in this context.

### 3. The file at the declared path

`entry` is relative to the pack root. `"scripts/main.js"` means
`behavior_pack/scripts/main.js` must exist.

---

## Minimal working script

```js
import { world, system } from "@minecraft/server";

// Runs once when the world loads
world.afterEvents.worldLoad.subscribe(() => {
  world.sendMessage("§aAdd-On loaded.");
});

// Runs when a player breaks a block
world.afterEvents.playerBreakBlock.subscribe((ev) => {
  const { player, brokenBlockPermutation, block } = ev;
  if (brokenBlockPermutation.type.id !== "mydemo:ruby_block") return;

  player.sendMessage(`§eYou broke a ruby block at ${block.x}, ${block.y}, ${block.z}`);
  player.runCommand(`give @s minecraft:diamond 1`);
});
```

---

## The event model

| Namespace | Meaning |
|---|---|
| `world.beforeEvents.*` | Fires before the action; **read-only** — you cannot mutate world state here |
| `world.afterEvents.*` | Fires after; safe to mutate |
| `system.beforeEvents.*` | System-level, before |
| `system.afterEvents.*` | System-level, after |
| `world.afterEvents.worldLoad` | World finished loading |
| `system.run(cb)` | Run on the next tick |
| `system.runInterval(cb, ticks)` | Repeat every N ticks (20 ticks ≈ 1 s) |
| `system.runTimeout(cb, ticks)` | Run once after N ticks |

### The `beforeEvents` trap

`beforeEvents` handlers run in a **read-only** context. Attempting to change the world there throws
`Error: cannot modify world state in read-only mode`.

```js
// ✗ throws
world.beforeEvents.playerBreakBlock.subscribe((ev) => {
  ev.block.setType("minecraft:air");   // read-only context
});

// ✓ defer to the next tick
world.beforeEvents.playerBreakBlock.subscribe((ev) => {
  const pos = ev.block.location;
  system.run(() => {
    world.getDimension("overworld").setBlockType(pos, "minecraft:air");
  });
});
```

This is the single most common script error.

### `system.run` is how you get write access

Anything that mutates the world must run inside `system.run*` when triggered from a read-only
context, or from an `afterEvents` handler directly.

---

## Block interaction

Custom components can call an event, but real logic belongs in script.

```js
world.afterEvents.playerInteractWithBlock.subscribe((ev) => {
  const { player, block, itemStack } = ev;
  if (block.typeId !== "mydemo:ruby_block") return;

  player.runCommand("give @s minecraft:diamond 1");
  player.playSound("random.orb");
  world.getDimension("overworld").spawnParticle("minecraft:happy_villager", {
    x: block.x + 0.5, y: block.y + 1, z: block.z + 0.5
  });
});
```

### Custom block components calling script

From the block JSON:

```json
"minecraft:on_player_placing": { "event": "mydemo:on_placed" }
```

```json
"events": {
  "mydemo:on_placed": {
    "run_command": { "command": ["say placed"] }
  }
}
```

`run_command` is enough for simple effects. For anything stateful, use script — the
component event can only run commands.

---

## Item use

```js
world.afterEvents.itemUse.subscribe((ev) => {
  const { source: player, itemStack } = ev;
  if (itemStack?.typeId !== "mydemo:ruby_wand") return;

  const view = player.getViewDirection();
  const loc = player.location;
  const target = {
    x: loc.x + view.x * 5,
    y: loc.y + view.y * 5,
    z: loc.z + view.z * 5,
  };

  player.teleport(target);
});
```

> `itemUse` fires for the item in the **main hand**. Off-hand use fires separately and less
> reliably — do not depend on it for acceptance tests.

---

## Persistence: dynamic properties

The supported way to store state per-entity or per-world. No file I/O.

```js
// world-scoped
world.setDynamicProperty("mydemo:counter", 42);
const n = world.getDynamicProperty("mydemo:counter");   // 42

// entity-scoped (including players)
player.setDynamicProperty("mydemo:charges", 3);
const c = player.getDynamicProperty("mydemo:charges");
```

Rules:

- Namespace your keys: `mydemo:counter`, never a bare name.
- Types are preserved: string, number, boolean.
- Objects must be serialized: `JSON.stringify`.
- **Not** a database — keep payloads small.

```js
// storing an object
player.setDynamicProperty("mydemo:stats", JSON.stringify({ kills: 3, deaths: 1 }));
const stats = JSON.parse(player.getDynamicProperty("mydemo:stats") ?? "{}");
```

---

## UI

```js
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";

world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId !== "mydemo:ruby_wand") return;

  new ActionFormData()
    .title("Ruby Wand")
    .body("Choose an action")
    .button("Heal me")
    .button("Give diamonds")
    .show(ev.source)
    .then((res) => {
      if (res.canceled) return;
      if (res.selection === 0) ev.source.runCommand("effect @s instant_health 1 4");
      if (res.selection === 1) ev.source.runCommand("give @s diamond 5");
    });
});
```

> **UI cannot be verified by a bot.** `@minecraft/server-ui` renders on the client. Layer C,
> always. Do not write a test that claims to verify a form's appearance.

---

## Timers and loops

```js
// every second
const id = system.runInterval(() => {
  // ...
}, 20);

// cancel it
system.clearRun(id);

// once, after 5 seconds
system.runTimeout(() => {
  world.sendMessage("5 seconds passed");
}, 100);
```

**Always keep the handle.** An interval you cannot cancel leaks and keeps running after the
feature is disabled.

### Tick budget

20 ticks per second. If your `runInterval` callback does heavy work, you drop TPS and the whole
server stutters. Rules:

- Do not iterate all entities every tick. Use events.
- Do not scan blocks in a loop every tick.
- Batch work across ticks:

```js
// ✗ one tick, blocks the server
for (let x = 0; x < 100; x++)
  for (let z = 0; z < 100; z++)
    world.getDimension("overworld").getBlock({ x, y: 64, z });

// ✓ chunked across ticks
let i = 0;
system.runInterval(() => {
  for (let n = 0; n < 20 && i < 100; n++, i++) {
    for (let z = 0; z < 100; z++)
      world.getDimension("overworld").getBlock({ x: i, y: 64, z });
  }
  if (i >= 100) { /* done */ }
}, 1);
```

---

## Test hooks: emitting evidence

For layer B, scripts are the cleanest way to emit machine-readable results. Use
`console.warn` — it lands in the server log where you can grep it.

```js
const PREFIX = "BF_TEST_RESULT ";

function emit(payload) {
  console.warn(PREFIX + JSON.stringify(payload));
}

world.afterEvents.playerBreakBlock.subscribe((ev) => {
  if (!ev.brokenBlockPermutation.type.id.startsWith("mydemo:")) return;
  emit({
    id: "block_broke",
    layer: "B",
    block: ev.brokenBlockPermutation.type.id,
    by: ev.player.name,
    result: "PASS",
  });
});
```

Then:

```bash
grep -a 'BF_TEST_RESULT' evidence/bds-A.log | tail -20
```

### `scriptevent` as a test trigger

`scriptevent` is more reliable than entity selectors when driving a bot-controlled world:

```js
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (ev.id === "mydemo:selftest") {
    emit({ id: "selftest", layer: "A", result: "PASS" });
  }
  if (ev.id === "mydemo:dump") {
    const players = world.getAllPlayers();
    emit({ id: "player_dump", count: players.length, names: players.map(p => p.name) });
  }
});
```

```bash
tmux send-keys -t bdsA 'scriptevent mydemo:selftest' Enter
```

> `@e[type=zombie]` frequently matches nothing in a bot-driven world. Prefer `scriptevent`.

---

## What scripts cannot do

| Not possible | Note |
|---|---|
| Read or write files | No filesystem access |
| Make arbitrary HTTP requests | Requires `@minecraft/server-net`, which is **BDS-only** and a separate beta module |
| Access the network at all without that module | No `fetch` in the base API |
| Render or inspect visuals | No client access |
| Run on a client | Server-side only |

The `@minecraft/server-net` module does exist and exports an `HttpClient`, but it is a **beta**
module, only runs on BDS, and must be added as a dependency separately. On a normal world, a
behavior pack's Script API has no built-in HTTP.

---

## Debugging

| Symptom | Look for |
|---|---|
| Script never runs | missing `dependencies`, wrong `entry` path, or the module is not in `modules` |
| `cannot modify world state` | you are in a `beforeEvents` handler — wrap in `system.run` |
| `undefined is not a function` | the method does not exist in your pinned module version — check `index.d.ts` |
| Nothing in the log at all | the script threw during load; look for the first `[Scripting]` error |
| Works once, then stops | an interval was cleared, or an exception killed a handler |

### The first thing to check

```bash
grep -a -i 'script' evidence/bds-A.log | head -20
grep -a -i 'error\|exception' evidence/bds-A.log | head -20
```

If the module failed to load, you will see it there. If you see nothing about scripting at all,
the module is not wired — go back to the three requirements at the top of this document.

---

## Anti-patterns

| Anti-pattern | Cost |
|---|---|
| Mutating world state in `beforeEvents` | Throws; the whole feature silently fails |
| Heavy work in `runInterval(cb, 1)` | Drops TPS for everyone |
| `getAllEntities()` every tick | On a busy world, this alone can halve TPS |
| Storing state in JS variables only | Lost on world reload — use dynamic properties |
| Unnamed dynamic property keys | Collide with other packs |
| Verifying UI with a bot | Impossible; produces a fake result |
| Assuming a script API method exists | It may not in your module version — check `index.d.ts` |

---

## Checklist before you call a script done

- [ ] module declared in manifest with `type: "script"`
- [ ] `dependencies` contains the exact `@minecraft/server` version
- [ ] `entry` path exists
- [ ] no world mutation inside a `beforeEvents` handler
- [ ] every interval has a stored handle and a clear path
- [ ] dynamic property keys are namespaced
- [ ] the script emits at least one `BF_TEST_RESULT` line for its acceptance case
- [ ] layer C items (UI, particles) are explicitly marked `MANUAL_GATE`

A script whose acceptance case has no emitted result line is **not tested**, regardless of how
correct it looks.