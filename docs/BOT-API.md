# Bot API Reference

A task-oriented wrapper over `bedrock-protocol`. 17 methods, grouped by what you are trying to
prove. Every method's purpose is to produce a **server-side observable**, not a self-report.

---

## Construction

```js
const { createLabKit } = require('./labkit')

const lab = createLabKit({
  host: '127.0.0.1',
  port: 20031,                                   // the slot's game port
  username: 'probe_' + Math.random().toString(36).slice(2, 5),
  version: '1.26.51',
  transport: 'nethernet',
  skipPing: true,
  tmuxSock: '/opt/bedrock-flow/state/tmux-A.sock',
  tmuxSession: 'bdsA',
  bdsLogPath: '/opt/bedrock-flow/evidence/bds-A.log',
})

lab.observe()   // start event collection — REQUIRED, or events stay empty
```

`observe()` is not optional. Without it `lab.events` never populates and your assertions silently
read empty arrays, which look like failures.

---

## 1. Connection

| Method | Purpose | Returns |
|---|---|---|
| `await lab.ready({timeoutMs, settleMs})` | Connect, wait for spawn and chunk load | `{position, columns, sections}` |
| `lab.isAlive()` | Is the connection healthy | `bool` (`status === 4`) |
| `await lab.close()` | Disconnect cleanly | — |

`ready()` returning `columns: 0` or `sections: 0` means **chunk decoding failed**, not that the
world is empty. That is a version/decoder problem, and it will make every world-reading test lie.

---

## 2. World reading

| Method | Purpose |
|---|---|
| `await lab.getBlock(x, y, z)` | Read one block → `{name, states, ...}` |
| `await lab.blockAt(vec3)` | Same, takes a `Vec3` |
| `await lab.scanColumn(x, z, {from, to})` | Scan a vertical column → `{total, types}` |

`scanColumn` is the only honest way to verify **worldgen**. A block you placed proves registration;
a block found in a generated column proves generation.

```js
const col = await lab.scanColumn(100, 100, { from: -64, to: 320 })
// { total: 384, types: { 'minecraft:stone': 331, 'mymod:titanium_ore': 4, ... } }
```

---

## 3. Containers

| Method | Purpose | Returns |
|---|---|---|
| `await lab.openChest(pos)` | Open a container (3 retries) | `chest` handle |
| `await lab.chestItems(chest, n)` | Read the first n slots | `[{slot, name, count}]` |
| `await lab.take(chest, slot)` | Move slot into the bot's inventory | — |
| `chest.close()` | Close it | — |

Containers are the **most reliable** test surface. They exercise the item system without
depending on the physics or input machinery that makes mining flaky.

---

## 4. Inventory

| Method | Purpose | Returns |
|---|---|---|
| `lab.inventory()` | Snapshot the bot's inventory | `[{slot, name, count}]` |
| `lab.findSlot(name)` | Find an item by name | slot index, or `-1` |
| `await lab.give(name, count)` | Server gives an item (via console) | — |
| `await lab.drop(slot, {isolateTo})` | Drop an item | `{ok, entitySpawned, pickedBackUp}` |
| `await lab.move(from, to)` | Move between slots | — |
| `await lab.clearInventory()` | Empty the inventory | — |
| `await lab.clearGround()` | Remove ground drops | — |

### `drop` and the pickup race

`drop()` returns `entitySpawned` **and** `pickedBackUp` separately, precisely because the bot stands
on the drop and re-collects it immediately.

```js
const r = await lab.drop(slot)
// ✓ correct assertion
assert('drops', r.entitySpawned === true)
// ✗ wrong assertion
assert('drops', lab.inventory().length === 0)   // lies: it dropped AND was picked up
```

`isolateTo` moves the bot somewhere the item cannot be reclaimed before asserting.

---

## 5. Server-authoritative probes

| Method | Purpose | Returns |
|---|---|---|
| `await lab.serverHasItem(name)` | Does the **server** think the player has it | `{present, count, raw}` |
| `await lab.serverItemCount(name)` | Count, server-side | `number` |

Mechanism: run `/clear <player> <item> 0` and read the result from the log.

> **Warning: this is destructive in some versions.** The `0` argument is meant to mean
> "count only", but that behaviour is not reliable across builds. Use it only when you are already
> verifying that the inventory should be empty, or on a disposable world.

Use these to resolve the bot-client-cache problem: after a script modifies an item, the bot's
cached `stack_id` can be stale while the server's view is correct. A server-authoritative probe
tells you which side is wrong.

---

## 6. Utilities

| Method | Purpose |
|---|---|
| `lab.con(cmd)` | Send a console command through tmux |
| `lab.makeChest(pos, items)` | Build and fill a container |
| `lab.events` | `{itemStackResponses, itemEntities, pickups}` |
| `lab.bot` | The raw `BotState` (150 methods) |
| `lab.sleep(ms)` | Await a delay |
| `lab.Vec3` | Vector constructor |

---

## Raw `BotState` — the methods worth knowing

### Movement (there are traps)

```js
// ✗ client-side only; the server never learns the position
bot.setPosition(x, y, z)

// ✓ sends PlayerAuthInput; the server sees it
bot.setControlState('forward', true)
await sleep(2000)
bot.setControlState('forward', false)
```

The only valid control names:

```
forward  back  left  right  jump  sprint  sneak  swim
```

There is **no** `up`. `setControlState('up')` throws `Invalid control up`.

### Mining

```js
// ✗ throws "Cannot dig block: undefined"
await bot.dig(new Vec3(x, y, z))

// ✓ pass the block object
const blk = await lab.getBlock(x, y, z)
await bot.dig(blk)
```

`dig` requires a continuous `PlayerAuthInput` stream. An idle bot times out. Measured dig time for
stone was a flat ~7500 ms regardless of the held tool, which means tool tier was not applied the
way a real client applies it.

> For Add-On acceptance, prefer container/item/drop paths. Use real mining only when the test is
> specifically about mining behaviour.

### Placing

```js
await bot.equipInventorySlot(itemSlot, 0)      // must be in the hotbar first
await bot.placeBlock(new Vec3(tx, ty, tz), 1)  // face: 0=bottom 1=top 2=z- 3=z+ 4=x- 5=x+
```

### Inventory and containers

```js
await bot.moveInventorySlot(from, to)    // NOT moveInventoryItem
await bot.dropInventorySlot(slot)
await bot.equipInventorySlot(slot, hotbarSlot)
await bot.selectHotbarSlot(slot)
await bot.openContainer(pos)
```

### Entities

```js
const ent = bot.nearestEntity(e => String(e?.identifier).includes('mymod:scout_drone'))
await bot.attackEntity(ent)
await bot.interactEntity(ent)
await bot.swingArm()
```

Match on `identifier`, not `type`. `type` is a broad class such as `'animal'`; filtering for
`'cow'` finds nothing.

### Chat and commands

```js
bot.chat('hello')
bot.command('say hi')             // requires operator
bot.commandWithOutput('list')     // returns the server's reply
```

---

## Raw packet injection

For behaviour the high-level API cannot express, intercept the outgoing packet:

```js
bot.onPlayerAuthInputPreSend((packet) => {
  packet.input_data = packet.input_data || {}
  packet.input_data.block_action = true
  packet.block_action = [{ action: 'start_break', position: target, face: 1 }]
})

bot.onPlayerAuthInputPreSend((packet) => {
  packet.input_data = packet.input_data || {}
  packet.input_data.item_stack_request = true
  packet.item_stack_request = { ... }
})
```

This is how you exercise real client code paths. It is also where the elapsed-time gating matters:
the server validates break duration, so an instant `predict_break` is discarded.

---

## Test script template

```js
const { createLabKit } = require('./labkit')
const sleep = ms => new Promise(r => setTimeout(r, ms))

;(async () => {
  const lab = createLabKit({
    port: 20031,
    username: 'probe_' + Math.random().toString(36).slice(2, 5),
    version: '1.26.51',
    tmuxSession: 'bdsA',
    bdsLogPath: '/opt/bedrock-flow/evidence/bds-A.log',
  })
  lab.observe()

  const R = []
  const assert = (id, ok, detail) =>
    R.push({ id, status: ok ? 'PASS' : 'FAIL', detail: String(detail ?? '') })

  try {
    const info = await lab.ready()
    assert('T1.spawn', lab.isAlive(), `y=${info.position.y.toFixed(1)}`)
    assert('T2.chunks', info.columns > 0, `columns=${info.columns} sections=${info.sections}`)

    lab.con(`give "${lab.bot.username}" diamond 3`)
    await sleep(2500)
    const inv = lab.inventory()
    assert('T3.receive', inv.some(i => i.name.includes('diamond')), JSON.stringify(inv))

    // ── your Add-On assertions here ──
  } catch (e) {
    R.push({ id: 'FATAL', status: 'FAIL', detail: e.message })
  }

  const failed = R.filter(x => x.status === 'FAIL')
  console.log(JSON.stringify({
    verdict: failed.length ? 'FAIL' : 'PASS',
    summary: { total: R.length, pass: R.length - failed.length, fail: failed.length },
    results: R,
  }))

  await lab.close()
  process.exit(failed.length ? 2 : 0)
})()
```

Exit codes: `0` all pass, `2` failures, `3` environment error or timeout.

---

## Health baseline

Before trusting any Add-On result, confirm the harness itself:

```
✓ connect / spawn          status=4
✓ world decode             columns=113  sections=15
✓ read block               getBlock → stone
✓ inventory give/read/move diamond x5, slot0 → slot30
✓ container open/read/take slots=27, diamond x3, emerald x1
✓ entity sense             animal x4
✓ chat                     sent
✓ keepalive                status=4
```

Any failure here means **fix the harness first**. Every product result downstream is worthless
until this baseline is green.