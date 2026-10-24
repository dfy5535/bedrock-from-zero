# Testing

The test framework exists for one reason: **to make it impossible to claim success without
proof.** Everything below is downstream of that.

---

## The three layers

### Layer A — Static

No server. No world. Pure file truth.

| Check | Failure it catches |
|---|---|
| JSON parses | Trailing commas, BOM, smart quotes |
| Schema validation against **pinned** package | Invented components, wrong `format_version` |
| Path layout (`blocks/`, `items/`, `entities/`) | Files that load in dev but not in pack import |
| UUID uniqueness across BP and RP manifests | Duplicate UUIDs silently drop one pack |
| Manifest dependency resolution | Version mismatch between packs and script modules |
| TypeScript compile against `index.d.ts` | API calls that do not exist in the target version |

Layer A is necessary and **nowhere near sufficient**. A pack can pass all of layer A and have
a completely invisible block.

### Layer B — Server runtime

This is the layer that has value. The method:

1. Start a BDS **in your own slot**.
2. Load the pack.
3. Spawn a **real player** (headless bot), not a fake entity.
4. Drive the actual behavior — real input packets for mining, real interaction packets for
   containers, real client commands for chat.
5. Read the verdict **out of the server log**.

The critical discipline: *do not trust the bot's stdout.* The bot is the actuator; the server is
the witness. A bot that prints `SUCCESS` proves nothing. A BDS log line that says the block at
`100,64,100` broke and the player received an item — that is evidence.

#### Why real input packets matter

A very common shortcut is to verify "mining works" by running `/setblock X Y Z air`. That proves
the command works. It proves nothing about your block, your tool requirements, your loot table,
or your hardness value.

The honest test injects the client-side block-break sequence:

```js
// phase 0 → start_break, phase 1 (after ~4s) → predict_break
// sent as player_auth_input.block_action, exactly as a real client would
bot.onPlayerAuthInputPreSend((packet) => {
  packet.input_data = packet.input_data || {}
  packet.input_data.block_action = true
  packet.block_action = [{ action: 'start_break', position: target, face: 1 }]
})
```

That path exercises hardness, tool tier, loot table, and drop behavior — the actual game logic.

#### Machine-readable results

Every case emits exactly one line into the server log:

```
BF_TEST_RESULT {"id":"ore_drops","layer":"B","expect":"item_dropped","actual":"item_dropped","result":"PASS"}
```

Parsing is then trivial and unambiguous:

```bash
grep -a 'BF_TEST_RESULT' evidence/bds-A.log \
  | sed 's/.*BF_TEST_RESULT //' \
  | python3 -c 'import sys,json; [print(json.loads(l)["result"]) for l in sys.stdin]'
```

**Rule: a case with no `BF_TEST_RESULT` line is not a PASS. It is `MISSING`, and `MISSING`
counts as `FAIL`.**

### Layer C — Client / visual

Marked `MANUAL_GATE`. Always.

| Status | Meaning |
|---|---|
| `MANUAL_GATE` | No client evidence yet. **Not** a pass. |
| `PASS` | A human (or a captured client screenshot) confirmed it |
| `FAIL` | Confirmed visually wrong |

The framework is deliberately willing to finish with an overall status of `PARTIAL`.
A `PARTIAL` that tells the truth is worth more than a `PASS` that does not.

---

## What to test for each artifact type

### Block

| Case | Layer | Method |
|---|---|---|
| Places and exists | B | `setblock` → `testforblock` |
| Breaks with the right tool tier | B | real `block_action` packets with and without a valid tool |
| Drops the correct item | B | break, then inspect inventory / log |
| Hardness feels right | B | measure break duration from packet timing |
| Texture and tint render | C | client |

### Item

| Case | Layer | Method |
|---|---|---|
| Obtainable | B | `give` succeeds, item exists in inventory |
| Registers with the right max stack | B | give > max, inspect the resulting stack |
| Use behavior fires | B | real use packets, assert the server-side effect |
| Recipe resolves | B | `recipe` / craft simulation |
| Icon renders | C | client |

### Entity

| Case | Layer | Method |
|---|---|---|
| Summons | B | `summon` succeeds |
| Has the right components | B | behavior assertion (moves, attacks, despawns) |
| Drops loot | B | kill, inspect drops |
| Animates and renders | C | client |

### Script

| Case | Layer | Method |
|---|---|---|
| Loads without error | B | grep the BDS log for script exceptions |
| Event handlers fire | B | trigger the event, assert a server-visible effect |
| No unhandled promise rejection | B | log scan |
| No tick-time blowup | B | measure tick latency under load |

---

## Test discipline rules

1. **One variable per iteration.** Change code or version or world — never two at once.
2. **Fresh world for destructive tests.** Never run a break-block test in a world you care about.
3. **Assert on the server, not the actuator.**
4. **A missing result line is a failure**, not a skip.
5. **Never re-use a previous run's log.** Truncate or timestamp-delimit before each run;
   otherwise you will read yesterday's PASS.
6. **Record the reproduction.** Every test case stores the exact command and the exact
   log excerpt that produced the verdict.

---

## Timing pitfalls

These are real and they will bite you:

| Pitfall | Symptom | Fix |
|---|---|---|
| Reading the log too early | `MISSING` on a case that actually passes | Sleep for the expected game-tick duration plus a margin, then re-read |
| Discovery port race | Bot joins the wrong server | Always pass the detected discovery port explicitly |
| World still loading | `setblock` fails with "no chunk" | Wait for the spawn event, then wait again |
| Packet pacing | Break completes instantly or never | Gate on real elapsed time between `start_break` and `predict_break` |

---

## Reporting format

```json
{
  "project": "titanium-ore",
  "runtime": "1.26.51.1",
  "layers": {
    "A": {"result": "PASS", "cases": 14, "failed": 0},
    "B": {"result": "PASS", "cases": 9,  "failed": 0, "missing": 0},
    "C": {"result": "MANUAL_GATE", "cases": 3}
  },
  "overall": "PARTIAL"
}
```

`overall` is `PASS` only when A and B pass **and** C is either `PASS` or explicitly excluded by
the design contract. Otherwise it is `PARTIAL` or `FAIL`. There is no fourth option.