# Pitfalls — Runtime Engine (the fatal ones)

This is the chapter where the two worst bugs lived. One made a core feature completely
non-functional. The other **hung the server and got it killed by the watchdog.**

Both have the same root cause.

---

## The first principle

> **An event callback is not a safe place to write.**

Everything below follows from that one sentence.

---

## Bug 1 — writing during an inventory transaction gets overwritten

### Symptom

`/give minecraft:iron_sword` → the item is **not** transformed. Manual testing occasionally worked;
batch testing almost always failed.

That intermittency is the tell: it is a timing/ordering problem, not a logic problem.

### Root cause

`playerInventoryItemChange` fires **while the inventory transaction is still in progress**.
Writing `container.setItem(ev.slot, newStack)` inside the handler is overwritten when the
transaction commits.

### Wrong

```ts
world.afterEvents.playerInventoryItemChange.subscribe((ev) => {
  const item = container.getItem(ev.slot);
  if (shouldConvert(item)) {
    container.setItem(ev.slot, convert(item));   // overwritten by the commit
  }
});
```

### Right

```ts
const pending = new Map<string, { player: Player; slot: number }>();
let writing = false;

world.afterEvents.playerInventoryItemChange.subscribe((ev) => {
  pending.set(`${ev.player.id}:${ev.slot}`, { player: ev.player, slot: ev.slot });
});

system.runInterval(() => {
  if (writing) return;                    // re-entry guard
  writing = true;
  try {
    for (const [k, w] of pending) {
      pending.delete(k);
      const cur = read(w);                // re-read AFTER the transaction
      if (isTarget(cur)) write(w, build(cur));
    }
  } finally {
    writing = false;
  }
}, 1);
```

---

## Bug 2 — writing inside an event caused an infinite recursion and hung the server

### Symptom

```
[Watchdog] Unhandled critical exception of type 'Hang' in behavior pack '<BP>'
[Scripting] Watchdog shutting down server
```

The server did not crash from an error. It **stopped making progress** and the watchdog killed it.

### Root cause

Calling `eq.setEquipment(slot, item)` inside `entityHurt` or `playerBreakBlock`.
`setEquipment` emits further events → the same handler runs again → **infinite recursion**.

### Right

Same pattern as bug 1, plus an explicit re-entry guard:

```ts
let writing = false;
const pendingWrites = new Map<string, { player: Player; slot: EquipmentSlot; target: ItemStack }>();

function correctSlot(/* ... */) {
  // only compute; never write
  if (needChange) pendingWrites.set(key, { player, slot, target });
}

function flushWrites() {
  if (writing) return;                    // ← this line prevents the hang
  writing = true;
  try {
    for (const [k, w] of pendingWrites) {
      pendingWrites.delete(k);
      // write here
    }
  } finally {
    writing = false;
  }
}

system.runInterval(flushWrites, 1);
```

### The lesson that took two bugs to learn

Both bugs are the same bug. The first time it was diagnosed as "transaction overwrite". The second
time it looked like something else.

> **The general rule: an event callback is not a safe write point.**
> Not for inventory. Not for equipment. Not for anything that can emit an event.

---

## Why queue-and-defer solves all four problems at once

| Problem | How queue + defer fixes it |
|---|---|
| Transaction overwrite | The write happens after the transaction commits |
| Event chaining | Nothing is written inside the event stack, so no nested events |
| Infinite recursion | The `writing` flag blocks re-entry |
| Stale data | Re-read immediately before writing |

That is why it is the standard pattern rather than a per-case fix.

---

## Scenario 1 — inventory rewrite (the backpack path)

**Trigger:** `playerInventoryItemChange` — covers `/give`, crafting, pickup.

```ts
world.afterEvents.playerInventoryItemChange.subscribe((ev) => {
  const container = ev.player.getComponent("minecraft:inventory")?.container;
  if (!container) return;
  const slot = ev.slot;

  system.run(() => {                       // defer one tick
    const cur = container.getItem(slot);   // re-read
    if (!cur || !eligible(cur)) return;    // player may have moved it
    const res = ensureSpec(cur, true);
    if (res) container.setItem(slot, res.stack);
  });
});
```

---

## The trap: a try/catch that hides everything

```ts
try {
  for (const it of ev.items) { /* ... */ }   // ev.items is sometimes undefined
} catch (e) {
  /* swallowed */
}
```

`TypeError: value is not iterable` — the entire drop-handling chain is dead, and the player notices
nothing. Silent, permanent failure.

### Right

```ts
const dropped = Array.isArray(ev.items) ? ev.items : [];
if (!dropped.length) return;
```

### The rule

> **A swallowed exception is the most dangerous kind.** The feature silently fails every time and
> nothing surfaces.
> **Every `catch` must log.**

---

## `setEquipment(Mainhand)` silently fails on simulated players

No error. The equipment simply does not change.

```ts
// does nothing on a SimulatedPlayer
eq.setEquipment(EquipmentSlot.Mainhand, item);

// works: write the container slot and set the selected slot
container.setItem(0, item);
player.selectedSlotIndex = 0;
```

> **"No error" is not "it worked."** For any critical operation, **read it back and verify.**

---

## `getAllPlayers()` returns junk

| Symptom | Cause |
|---|---|
| `TypeError: cannot read property 'name' of undefined` — scan loop dies | returns stale entries |
| returns `[undefined]` | SimulatedPlayer special case |
| `playerSpawn` never fires | SimulatedPlayer does not follow the normal spawn path |

### One wrapper that handles all three

```ts
export function onlinePlayers(): Player[] {
  const out: Player[] = [];
  for (const p of world.getAllPlayers()) {
    if (p && p.isValid) out.push(p);       // dual check: truthy AND valid
  }
  if (!out.length) {                       // fallback: scan dimensions
    for (const dim of ["overworld", "nether", "the_end"]) {
      for (const e of world.getDimension(dim).getEntities({ type: "minecraft:player" })) {
        if (e.typeId === "minecraft:player") out.push(e as Player);
      }
    }
  }
  return out;
}
```

> **Official APIs return arrays that may contain `undefined` or stale objects.**
> Always `if (x && x.isValid)`.

---

## The first-state blind spot (differential algorithms)

### Symptom

A chestplate with `durabilitySave=100` (100% wear immunity) was hit 5 times and **still lost 1
durability point**.

### Root cause

Durability correction used a snapshot-difference approach: remember the last seen `damage`, correct
the delta when an event arrives.

But **the first time it sees an item, it only records the snapshot — it does not correct anything**,
because there is no "previous" to compare against.

→ the first wear is always missed.

### Right

```ts
// prime the snapshot every tick for newly equipped items
function primeSnapshots() {
  for (const p of onlinePlayers()) {
    const eq = p.getComponent("minecraft:equippable");
    for (const slot of SLOTS) {
      const it = eq?.getEquipment(slot);
      if (it && !snapshots.has(key(p, slot))) snapshots.set(key(p, slot), read(it));
    }
  }
}
system.runInterval(primeSnapshots, 1);
```

> **"First state" is the blind spot of every differential algorithm.**
> Whenever you compare before/after, ask: **what happens the first time?**

---

## Batch processing blocks the server

### Symptom

Transforming 324 items froze the server for **4.4 seconds**.

### Root cause

One item takes ~13.7 ms (generate + write lore + write dynamic properties).
324 × 13.7 ms = 4.4 s, all inside a single tick.

### Right

```ts
const BATCH_PER_TICK = 4;
system.runInterval(() => {
  for (let i = 0; i < BATCH_PER_TICK && queue.length; i++) process(queue.shift());
}, 1);
```

> **The script API is single-threaded.** Any "loop over N items" needs the question:
> **what happens when N is large?**
> A player's chest has 27 slots. A world has many chests.

---

## Event-driven + periodic sweep = reliable

Item transformation occasionally missed drops, because `entitySpawn` does not fire on every path
(explosions, script-spawned items).

```ts
// periodic fallback sweep
system.runInterval(sweepWorldItems, 60);   // every 60 ticks, budget 64 items
```

But the sweep **must not depend on players being online** — that fails in simulated-player
scenarios. Use a hybrid: sweep near players when any are online, sweep all dimensions when none are.

> **Event-driven plus periodic fallback = reliable.**
> Events alone miss. Polling alone is expensive. **Combine them.**

---

## Normal races are not exceptions

`entity removed` between "query" and "process" is a **normal race**, not an error.

Logging it as WARN floods the log and **drowns the real exceptions**.

> **Distinguish "exception" from "normal race."**
> Turning normal races into errors makes the log useless.

---

## The eight laws extracted from these bugs

1. **An event callback is not a safe write point** — read and compute only; queue the write
2. **All gates on a path must be opened** — opening one is the same as opening none
3. **"No error" ≠ "success"** — read back and verify critical operations
4. **API return values may contain `undefined`/stale objects** — dual check
5. **The first state is a differential algorithm's blind spot** — prime it
6. **A tooltip is a promise to the player** — show only what actually happens
7. **A swallowed exception is the most dangerous** — always log
8. **Separate normal races from exceptions** — or the log becomes noise

---

## Checklist before you ship a runtime feature

- [ ] no writes inside any event callback
- [ ] every write goes through a queue flushed on a safe tick
- [ ] a re-entry guard exists (`writing` flag or equivalent)
- [ ] the write re-reads its target before writing
- [ ] every `catch` logs
- [ ] array-returning APIs are guarded with `if (x && x.isValid)`
- [ ] critical writes are read back and verified
- [ ] differential logic primes its first snapshot
- [ ] batch loops have a per-tick budget
- [ ] there is a periodic fallback for event paths that can be missed