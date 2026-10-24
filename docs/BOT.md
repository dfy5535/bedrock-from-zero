# The Bot — a real player over the Bedrock protocol

This is the load-bearing component of the whole pipeline. Without it, "runtime testing"
is just a schema check with extra steps.

---

## The problem it solves

```
You write an Add-On  →  deploy to BDS  →  ❌  who actually walks in and verifies it?
                                            A BDS cannot play a player.
```

`mct validate` checks **structure**. It cannot tell you:

- Does the custom block register at runtime?
- Does breaking it in survival yield the right drop?
- Does the container open and give the right item?
- Does the entity pathfind, or does it stand still forever?
- Does the script event fire, or silently never register?

A headless bot is a **real Bedrock client** speaking the real protocol. It spawns, loads
chunks, reads blocks, opens containers, takes items, drops items, attacks entities, and
sends chat — and every one of those actions produces **server-side** evidence.

> **The honest framing:** the bot is the *actuator*, the server is the *witness*.
> A bot printing `SUCCESS` proves nothing. A server log line proves it.

---

## Stack

| Component | Role |
|---|---|
| `bedrock-protocol` | The protocol implementation: auth, encryption, packet codecs |
| `nethernet` | The transport used by modern BDS (replaces RakNet for LAN discovery) |
| `prismarine-chunk` / `prismarine-block` | Chunk decoding, block state resolution |
| `vec3` | Position math |

The bot layer wraps these into a task-oriented API. The wrapper matters because the raw
API is full of traps — see the pitfalls section, every one of which cost real hours.

---

## Layer 1 — connect and become a player in the world

```js
const { Client } = require('bedrock-protocol')
const { BotState } = require('./pb-src')

// 1. discover the server (nethernet broadcasts on a host-global UDP port)
const nid = await discover()          // returns BigInt network id from a pong

// 2. connect
const bot = new BotState({
  host: '127.0.0.1',
  port: 20031,                        // the slot's game port
  username: 'probe_bot',
  offline: true,                      // no Xbox auth needed for local testing
  version: '1.26.51',
  transport: 'nethernet',             // NOT raknet, for modern BDS
  nethernet: {
    networkId: nid,
    signalling: 'lan',
  },
  skipPing: true,
  connectTimeout: 20000,
  worldDecodeEnabled: true,
})

bot.start()
```

`discover()` is the part everyone gets wrong:

```js
function discover() {
  return new Promise((resolve, reject) => {
    const s = new Client(0n, '255.255.255.255', {})
    const t = setTimeout(() => reject(new Error('timeout')), 30000)
    s.on('pong', (p) => {
      clearTimeout(t)
      try { s.close() } catch {}
      resolve(BigInt(p.sender_id))
    })
    s.on('error', () => {})
  })
}
```

It broadcasts to the **discovery port**, which is `7551` unless the server lost the race for it.
If you do not set `NETH_DISCOVERY_PORT`, you broadcast to `7551` and connect to whichever server
happened to win it. This is the #1 cause of "the bot joined the wrong world" — see
[`SLOT-ISOLATION.md`](SLOT-ISOLATION.md).

---

## Layer 2 — read the world

```js
await bot.ready({ timeoutMs: 30000, settleMs: 2000 })
// → { position, columns, sections }

// a single block
const blk = await bot.getBlock(x, y, z)
console.log(blk.name)             // e.g. 'mymod:titanium_ore' or 'minecraft:stone'

// a whole column
const col = await bot.scanColumn(x, z, { from: 0, to: 320 })
// → { total: 320, types: { 'minecraft:stone': 280, 'mymod:titanium_ore': 3 } }
```

`scanColumn` is how you prove **ore generation** actually ran. A block existing when you
`setblock` it proves the block is registered; a block appearing in a naturally generated
column proves worldgen works. Those are different claims.

---

## Layer 3 — the server console channel

The bot cannot do everything. Some checks need a privileged command. The console is reached
through `tmux`:

```js
function con(cmd) {
  spawnSync('tmux', ['send-keys', '-t', SESSION, cmd, 'Enter'], { encoding: 'utf8' })
}

con(`give "${NAME}" minecraft:netherite_pickaxe 1`)
con(`gamemode survival "${NAME}"`)
con(`tp "${NAME}" 100 64 100`)
con(`weather clear`)
```

The response comes back **in the log**, not on stdout. So every console call must be paired
with a log read:

```js
function waitFor(pattern, ms = 2000) {
  const start = Date.now()
  while (Date.now() - start < ms) {
    const out = tailLog(pattern, 1)
    if (out.length) return out[0]
  }
  return null
}
```

> **Why tmux and not a socket:** BDS reads stdin. A tmux session is the most reliable way to
> feed it commands that survive reconnects, and it gives you replayable scrollback for evidence.

---

## Layer 4 — real input packets (the honest test)

This is what separates a real verification from a fake one. Do **not** verify mining with
`setblock X Y Z air`.

```js
let phase = 0
const t0 = Date.now()

bot.onPlayerAuthInputPreSend((packet) => {
  packet.input_data = packet.input_data || {}
  packet.input_data.block_action = true

  const elapsed = Date.now() - t0
  if (phase === 0) {
    packet.block_action = [{ action: 'start_break', position: target, face: 1 }]
    phase = 1
  } else if (phase === 1 && elapsed >= 4000) {
    packet.block_action = [{ action: 'predict_break', position: target, face: 1 }]
    phase = 2
  }
})
```

This path exercises the real game logic:

- **hardness** — the server validates the break duration
- **tool tier** — whether the held item can harvest this block
- **loot table** — what actually drops
- **block state** — whether the right variant was targeted

### Pacing

The break only completes if packets keep flowing. Elapsed gating (`elapsed >= 4000`) is
mandatory: sending `start_break` and `predict_break` in the same tick does nothing, and the
server silently ignores it. Same for `placeBlock` — equip first:

```js
await bot.equipInventorySlot(itemSlot, 0)     // into hotbar slot 0
await bot.placeBlock(new Vec3(tx, ty, tz), 1) // face: 0=bottom 1=top 2=z- 3=z+ 4=x- 5=x+
```

---

## Layer 5 — evidence extraction

The bot's job ends when the log is written. Then:

```bash
# machine-readable test results
grep -a 'BF_TEST_RESULT' evidence/bds-A.log | tail -20

# did the block break?
grep -a 'block at 100,64,100' evidence/bds-A.log

# what dropped?
grep -a 'Item entity spawned' evidence/bds-A.log

# did the script event fire?
grep -a 'scriptevent' evidence/bds-A.log

# did the player get the item?
grep -a 'Player .* received' evidence/bds-A.log
```

Design the test so each case emits exactly one line into the log. Then the verdict is a grep,
not an interpretation.

---

## The pitfalls — every one of these is real

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | `bot.moveInventoryItem is not a function` | Wrong method name | Use `moveInventorySlot(from, to)` |
| 2 | `setPosition` moves 0.00 m | Only updates the client's local position | Use `setControlState('forward', true)` — it sends `PlayerAuthInput` |
| 3 | `Invalid control up` | There is no `up` | Only these 8 exist: `forward`, `back`, `left`, `right`, `jump`, `sprint`, `sneak`, `swim` |
| 4 | `Cannot dig block: undefined` | Passed coordinates instead of a block | Pass the **block object**: `await bot.dig(await bot.getBlock(x,y,z))` |
| 5 | `No item in the active hotbar slot` | `placeBlock` with empty hand | `equipInventorySlot(slot, 0)` first |
| 6 | `bot.world` becomes `undefined` after `tp` | Chunk state lost on long teleport | Do not teleport far; build a platform where you stand |
| 7 | `~` resolves to `0,0,0` after `setPosition` | Server never learned the bot's real position | Never mix client-side position with server-side `~` |
| 8 | Entity filter `'cow'` finds nothing | `type` is a **broad class** (`'animal'`) | Match on `identifier` for the specific mob |
| 9 | `@e[type=zombie]` → "No targets matched" | Selector mismatch from a bot-driven world | Use `scriptevent` instead of selectors |
| 10 | Item dropped at feet vanishes | Auto-pickup race | Assert on `entitySpawned`, not "inventory is empty" |
| 11 | `Timed out waiting for dig completion` | Idle → PAI packets become sparse | Keep input flowing; prefer container paths over mining |
| 12 | Everything is slow when idle | No packet stream | Maintain a heartbeat by moving/rotating periodically |

### The two that will really hurt you

**Pitfall 11 — dig timeouts on idle bots.** `dig` depends on a continuous stream of
`PlayerAuthInput`. An idle bot sends few, so the server's break-progress timeout fires. Worse:
observed dig time for stone was a constant ~7500 ms regardless of the held tool, meaning
tool-tier was not being factored in the way a real client does.

> **Practical rule: for Add-On acceptance, prefer the container / item / drop paths.
> Only rely on real mining when the test is specifically about mining.**

**Pitfall 10 — the auto-pickup race.** You drop an item to test that it drops. The bot is
standing on the drop spot, picks it up instantly, and your "did it drop" assertion reads an empty
inventory and a clean ground. You then "fix" a nonexistent bug.

```js
// ✗ wrong conclusion
if (inventory.length === 0) → "item did not drop"   // it dropped and was picked up

// ✓ correct assertion
if (result.entitySpawned === true) → "item dropped"  // then check pickup separately
```

---

## What the bot cannot do

Be honest about the boundary. This list is why layer C exists.

| Capability | Status | Why |
|---|---|---|
| Full crafting UI flow | ⚠️ Unreliable | The protocol library cannot parse `crafting_data` on some versions; recipes come back as 0 |
| Precise movement | ⚠️ Approximate | Server-side collision makes displacement inexact |
| Reliable mining timing | ⚠️ Degraded when idle | PAI sparsity, and tool tier may not apply |
| Client-side cache coherence | ⚠️ Stale | After a script `setItem`, the bot's cached `stack_id` can be stale; a real client receives an inventory update |
| Anything visual | ❌ Impossible | No renderer |

That last row is permanent. **A bot can never validate a texture, a model, a particle effect,
or a UI layout.** Those are layer C, and layer C is `MANUAL_GATE`. Forever.

> A `BLOCKED` result from the bot is **not** the same as a MOD defect. It usually means the
> test *tooling* lacks the capability. Distinguishing "product is broken" from "harness cannot
> measure it" is the single most important judgement call in this whole framework — and the one
> most easily gotten wrong.

---

## Standard workflow

```
1. Is the test server up?
   labctl status

2. Is the bot itself working?  (never skip this)
   run-acceptance.sh          → verdict=PASS before anything else

3. Run your Add-On acceptance
   node your-test.js

4. Parse the JSON, write the report with an evidence level per case

5. Fix only the FAIL cases, then re-run from step 3
```

Step 2 is not optional. If the harness is broken, every downstream result is noise, and you will
spend hours debugging a MOD that is fine.

---

## Known-good baseline

What a healthy bot looks like, so you can tell "harness broken" from "product broken":

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

If any of these fail, **stop and fix the harness.** Do not proceed to product acceptance.