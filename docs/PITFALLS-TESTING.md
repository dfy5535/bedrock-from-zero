# Pitfalls — Testing (the most dangerous kind)

> A product bug makes a feature fail, and you can see it.
> **A test bug makes a failed feature look like it passed, and you cannot.**

Every entry below once **masked a real problem** or wasted hours chasing a phantom.

---

## Part 1 — False passes

### `undefined === undefined` passes

**Scenario:** verify that an item's instance id survives a chest round-trip.

```js
const before = item.instance;    // read from a server dump
const after = item2.instance;
expect(after).toBe(before);
```

**Problem:** the dump command never emitted an `instance` field. Both sides are `undefined`.
`undefined === undefined` → **PASS**.

The mechanism was fine. **The test never measured it.**

**Fix:**

```js
expect(before).toBeTruthy();      // ← prove there IS a value first
expect(after).toBe(before);
```

> **For every assertion, ask: "if this field were `undefined`, would the test still pass?"**

---

### A universal assertion on an empty set is always true

```js
const plain = items.filter(i => i.rpg !== true);
expect(plain.length).toBe(0);      // "nothing was missed"
```

**Problem:** if `items` is `[]`, `plain.length === 0` holds trivially → PASS.

**Fix:**

```js
expect(items.length).toBeGreaterThan(0);   // ← prove there is something to check
expect(plain.length).toBe(0);
```

> **Universal assertions ("all X satisfy Y") are vacuously true on an empty set.**
> Always assert sample size first.

---

### `finish()` collapsed BLOCKED into FAIL

```js
const ok = ev.assertions.every(a => a.status === 'PASS' || a.status === 'UNSUPPORTED');
return ev.finish(ok ? 'PASS' : 'FAIL');
```

`BLOCKED` (environment could not do it) was counted as `FAIL` → **statistics were wrong**, and an
environment limitation got reported as a product defect.

**Fix:**

```js
const failed  = ev.assertions.some(a => a.status === 'FAIL');
const blocked = ev.assertions.some(a => a.status === 'BLOCKED');
return ev.finish(failed ? 'FAIL' : blocked ? 'BLOCKED' : 'PASS');
```

> **PASS / FAIL / BLOCKED / UNSUPPORTED / UNTESTED are five different things.**
> Compressing them into a boolean destroys the report's only value:
> distinguishing "we couldn't" from "we broke it".

---

## Part 2 — False failures

### `bot.entities` is a Map, not an object

```js
const zs = Object.values(bot.entities || {}).filter(e => e.type === 'zombie');
// always [] — Object.values on a Map returns nothing
```

Combat tests failed 100% while the combat was fine.

**Fix:**

```js
const all = bot.entities && typeof bot.entities.values === 'function'
  ? [...bot.entities.values()]
  : [];
```

> **Before using a third-party library, confirm the type of its core data structures.**
> `x instanceof Map` — one line, saves hours.

---

### The conservation assertion counted unrelated drops

```js
expect(entityCount).toBe(swordCount);
// entityCount: 42, swordCount: 5 → FAIL
```

42 item entities nearby, only 5 swords. The rest were **rotten flesh from zombies**.
This was not "the conversion duplicated items" — there were simply other drops around.

**Fix:** conservation means **"nothing was created from nothing"**, not "counts are equal":

```js
const insts = rpg.map(s => s.instance).filter(Boolean);
const dup = insts.length - new Set(insts).size;
expect(dup).toBe(0);
```

> **Designing an assertion, first ask: what unrelated factor could disturb this measure?**

---

### The bot picked the item back up

```js
const dropped = groundItems.find(i => i.type === 'diamond_sword');
expect(dropped).toBeTruthy();     // FAIL
```

The bot dropped the item **while standing on the drop point**, so the server instantly auto-collected
it. Standard Minecraft physics, not a bug.

**Fix:** cover both legal paths.

```js
let where = 'ground';
let dropped = groundItems.find(...);
if (!dropped) {
  const back = invItems.find(...);
  if (back) { dropped = back; where = 'picked-back-up'; }
}
```

> **Tests must understand the game's physics.**
> "Dropping at your feet gets auto-collected" is standard behaviour.
> **The assertion must cover every legal path.**

---

### Scenario leakage

`craft` finished, then `chest` timed out forever.

**Cause:** the previous scenario left blocks, item entities, and a moved bot behind.

**Fix:**

1. **A fresh bot session per scenario** (disconnect and reconnect)
2. Reset the test area before each scenario (clear inventory, flatten, teleport to anchor)

> **Test isolation is a requirement.**
> A test's result must never depend on what a previous test left behind.
> **Strongest isolation = separate process / separate session.**

---

## Part 3 — Timing

### Waiting too little

`give` then immediately reading inventory → empty.

```js
async function waitFor(predicate, { tries = 24, intervalMs = 500 } = {}) {
  for (let i = 0; i < tries; i++) {
    const r = await predicate();
    if (r) return r;
    await sleep(intervalMs);
  }
  return null;
}
```

> **A fixed `sleep` is the most fragile form of waiting.** Too short when busy, wasteful when idle.
> **Poll with a timeout.**

### Waiting too much, or in the wrong order

Dropping an item, teleporting to it, waiting 3 s, teleporting back — the item was never collected,
then the bot left.

**Fix — order matters:**

```js
lab.con(`tp "${NAME}" ${itemX} ${itemY} ${itemZ}`);
await sleep(6000);            // stand long enough for auto-pickup
const d = await inv(NAME);    // CHECK first
lab.con(`tp "${NAME}" ${anchorX} ...`);   // change the environment LAST
```

> **Order: perform the action → check → then change the environment.**
> The original order was action → change environment → check. The middle step destroyed the state
> being checked.

---

### Client cache is not server truth

After the MOD rewrote an item, dropping it returned `status 49`.

| Group | Item | Rewritten by MOD | Drop result |
|---|---|---|---|
| control | diamond | **no** | ✅ fine |
| experiment | iron sword | **yes** | ❌ `status 49` |

**Conclusion:** the MOD's `setItem` left the bot's cached `stack_id` stale. A real client receives an
`InventorySlot` update; the protocol library does not handle that packet.

**This is a bot-library limitation, not a MOD defect.**

> **Client cache ≠ server truth.**
> Judge item state from a **server-side dump**, never from `bot.inventory`.
> **Attribution requires a controlled experiment** (one variable different).

---

## Part 4 — Bugs in the test harness itself

| Symptom | Cause | Note |
|---|---|---|
| `Cannot read properties of undefined (reading 'position')` | the wrapper has no `.self`; position is at `lab.bot.self.position` | **Read the wrapper's interface before guessing property names** |
| statistics show `{"true": 6}` | `add()` received a boolean where a status string was expected | Defend the type: `typeof x === 'boolean' ? (x?'PASS':'FAIL') : x` |
| freshly edited code was overwritten | local copy was older; `tar` restored it over the server | **Establish a single source of truth** — edit locally then sync, or edit remotely then pull. **Never mix.** |

---

## Part 5 — The three levels of test failure

### Level 1 — the test did not cover it

A third-party compatibility path was broken. Unit tests used ids **I had defined myself**
(`minecraft:iron_sword`, `compat:rpg_sword`). The real third-party pack used `othermod:katana` — an
id I never thought of.

White-box tests can never find this.

**Fix:** introduce **external data** — real third-party packs, real protocol clients, unfamiliar
namespaces.

### Level 2 — the assertion was wrong

The test ran, data arrived, but the measure was wrong → false failure.

**Fix — ask three questions when designing any assertion:**

1. If the field were `undefined`, would it pass?
2. If the sample were empty, would it pass?
3. What unrelated factor could disturb this measure?

### Level 3 — the environment was wrong

A port conflict meant the "1.26.51 test" was actually connected to 1.26.52. The test logic was
perfect; the conclusion was entirely wrong.

**Fix:** confirm the environment before every run, and **record an environment fingerprint** in the
report (BDS version, API version, bot version).

---

## Part 6 — The order of suspicion

> ### When a test fails: **test script → environment → product code.**

Why this order:

- A test bug **disguises itself as a product bug** (you go fix working code)
- An environment problem **disguises itself as a product bug** (same waste)
- A product bug usually has **clear characteristics** (an exception, a log line)

> The biggest mistake in the project was **suspecting the product first** — and burning hours
> "fixing" things that were never broken.

---

## Part 7 — Checklists

### When writing a test

- [ ] every assertion proves "there is a value" first
- [ ] every universal assertion proves "sample size > 0" first
- [ ] the measure cannot be disturbed by unrelated factors
- [ ] every legal path is covered (including auto-pickup)
- [ ] the status machine is complete (5 states, not 2)
- [ ] **counter-test: deliberately break the feature — does the test go red?**

### When running a test

- [ ] environment confirmed (version / port / pack loaded)
- [ ] scenarios isolated (fresh session / reset)
- [ ] poll with timeout, never a fixed sleep
- [ ] order: action → check → change environment

### When reading results

- [ ] on failure: suspect test first, environment second, product last
- [ ] on pass: ask "could this assertion actually fail?"
- [ ] the report records the environment fingerprint

---

## The single most useful question

> ### "If this feature were completely broken, would my test fail?"

If the answer is "no" or "maybe not", the test is decorative.

That question catches `undefined === undefined`, empty-set universals, wrong measures, and
uncovered paths — all four at once.