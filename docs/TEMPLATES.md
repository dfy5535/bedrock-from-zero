# Reusable Templates

Production-verified code. **Copy these; do not reinvent them.** Every template fixes a bug that
cost hours.

TypeScript, targeting `@minecraft/server`.

---

## 1. Safe writes — the most important template

Fixes: writes overwritten by a transaction, and event recursion hanging the server.

```ts
// ============================================================
// Queue writes in events, flush on a safe tick.
// ============================================================
type WriteTask = () => void;

const writeQueue: WriteTask[] = [];
let flushing = false;

/** Call this from an event handler. Never write directly. */
export function scheduleWrite(task: WriteTask): void {
  writeQueue.push(task);
}

/** Register once at startup. */
export function installWriteFlusher(system: System): void {
  system.runInterval(() => {
    if (flushing) return;              // ← re-entry guard: prevents the hang
    if (writeQueue.length === 0) return;

    flushing = true;
    try {
      const budget = Math.min(writeQueue.length, 16);   // ← per-tick budget
      for (let i = 0; i < budget; i++) {
        const task = writeQueue.shift();
        if (!task) break;
        try {
          task();
        } catch (e) {
          zlog("write:error", { error: String(e) });    // ← never swallow
        }
      }
    } finally {
      flushing = false;
    }
  }, 1);
}
```

**Usage:**

```ts
world.afterEvents.playerInventoryItemChange.subscribe((ev) => {
  const player = ev.player;
  const slot = ev.slot;

  scheduleWrite(() => {
    const inv = player.getComponent("minecraft:inventory")?.container;
    if (!inv) return;
    const cur = inv.getItem(slot);       // ← re-read after the transaction
    if (!cur) return;                    // player may have moved it
    if (!eligible(cur)) return;
    const res = ensureSpec(cur, true);
    if (res) inv.setItem(slot, res.stack);
  });
});
```

---

## 2. Capability probing

Fixes: hard-coded version strings lying in the log.

```ts
// ============================================================
// Probe what the running API actually supports.
// ============================================================
export interface Capabilities {
  blockContainerOpened: boolean;
  playerInteractWithBlock: boolean;
  entityItemDrop: boolean;
  module: string;
}

export function probeCapabilities(): Capabilities {
  const ae = world.afterEvents as unknown as Record<string, { subscribe?: unknown } | undefined>;
  const has = (name: string) => typeof ae[name]?.subscribe === "function";

  const blockContainerOpened = has("blockContainerOpened");

  return {
    blockContainerOpened,
    playerInteractWithBlock: has("playerInteractWithBlock"),
    entityItemDrop: has("entityItemDrop"),
    // infer the generation from API presence, not from a hard-coded string
    module: blockContainerOpened ? "@minecraft/server 2.8.0+" : "@minecraft/server <=2.7.0",
  };
}

/** Subscribe only if the event exists on this version. */
export function subscribeIfAvailable(
  name: string,
  handler: (...args: unknown[]) => void,
): boolean {
  const ae = world.afterEvents as unknown as Record<string, { subscribe?: Function } | undefined>;
  const sig = ae[name];
  if (sig && typeof sig.subscribe === "function") {
    sig.subscribe(handler);
    return true;
  }
  zlog("capability:missing", { event: name });
  return false;
}
```

---

## 3. Poll with a timeout

Fixes: fixed `sleep` being too short when busy and wasteful when idle.

```ts
export async function waitFor<T>(
  probe: () => T | null | undefined | false,
  opts: { tries?: number; intervalMs?: number; label?: string } = {},
): Promise<T | null> {
  const tries = opts.tries ?? 24;
  const intervalMs = opts.intervalMs ?? 500;

  for (let i = 0; i < tries; i++) {
    const r = probe();
    if (r) return r as T;
    await sleep(intervalMs);
  }

  if (opts.label) zlog("wait:timeout", { label: opts.label, tries, intervalMs });
  return null;
}
```

---

## 4. Server-truth collection

Fixes: client cache not reflecting server-side changes.

```ts
import { readFileSync } from "node:fs";

const LOG_PATH = "/path/to/bds.log";

function logLineCount(): number {
  try {
    return readFileSync(LOG_PATH, "utf8").split("\n").length;
  } catch {
    return 0;
  }
}

/**
 * Grab the last matching JSON line from the log.
 * @param tag    marker, e.g. "dumpinv"
 * @param since  line number taken BEFORE sending the command
 * @param player optional filter on the payload's player field
 */
export function grabJson<T = unknown>(
  tag: string,
  since: number,
  player?: string,
): T | null {
  let raw = "";
  try {
    raw = readFileSync(LOG_PATH, "utf8");
  } catch {
    return null;
  }

  const lines = raw.split("\n").slice(Math.max(0, since - 1));

  for (let i = lines.length - 1; i >= 0; i--) {
    if (!lines[i].includes(tag)) continue;
    const m = lines[i].match(new RegExp(tag + " (\\{.*\\})\\s*$"));
    if (!m) continue;
    try {
      const obj = JSON.parse(m[1]) as T & { player?: string };
      if (!player || obj.player === player) return obj;
    } catch {
      /* keep looking further back */
    }
  }
  return null;
}

/** Standard usage. */
export async function dumpInventory(lab: any, player: string): Promise<any | null> {
  const since = logLineCount();
  lab.con(`execute as "${player}" run scriptevent app:dumpinv`);
  return waitFor(() => grabJson("app:dumpinv", since, player), {
    tries: 20,
    intervalMs: 450,
    label: "dumpinv",
  });
}
```

### What a dump command should emit

```
slot        slot index
type        item identifier
nameTag     display name (including prefixes)
lore        lore line count
rpg         whether it was transformed
quality     tier
score       score
instance    instance id        ← ★ identity continuity
origin      source
enchants    enchantment list   ← ★ data fidelity
dynBytes    dynamic property byte count
tags        item tags
```

> **The fields your debug command emits determine what you are able to verify.**
> Missing `instance` is what caused a false pass (see `PITFALLS-TESTING.md`).
> **Emit every field you might ever want to check.**

---

## 5. Five-state reporting

Fixes: BLOCKED being counted as FAIL.

```ts
export type Status = "PASS" | "FAIL" | "BLOCKED" | "UNSUPPORTED" | "UNTESTED";

export interface Result {
  id: string;
  status: Status;
  detail?: unknown;
}

export class Report {
  readonly results: Result[] = [];

  /** cond may be a boolean (auto-converted) or an explicit status. */
  add(id: string, cond: boolean | Status, detail?: unknown): void {
    const status: Status =
      typeof cond === "boolean" ? (cond ? "PASS" : "FAIL") : cond;

    this.results.push({ id, status, detail });

    const mark = { PASS: "✓", FAIL: "✗", BLOCKED: "⛔", UNSUPPORTED: "⊘", UNTESTED: "?" }[status];
    console.log(`  ${mark} ${id}  ${JSON.stringify(detail ?? "").slice(0, 140)}`);
  }

  summary() {
    const c = { PASS: 0, FAIL: 0, BLOCKED: 0, UNSUPPORTED: 0, UNTESTED: 0 };
    for (const r of this.results) c[r.status]++;

    return {
      total: this.results.length,
      ...c,
      // ★ BLOCKED or UNTESTED means it is not complete
      FINAL:
        c.FAIL === 0 && c.BLOCKED === 0 && c.UNTESTED === 0
          ? "COMPLETE"
          : "NOT COMPLETE",
    };
  }
}
```

---

## 6. Assertions that cannot be fooled

Fixes: `undefined === undefined`, empty-set universals, and miscounted conservation.

```ts
/** Assert 1: prove there is a value. */
export function assertPresent<T>(v: T | null | undefined, label: string): asserts v is T {
  if (v === null || v === undefined) {
    throw new Error(`[assertPresent] ${label} is empty — downstream assertion is meaningless`);
  }
}

/** Assert 2: prove there is a sample. */
export function assertNonEmpty<T>(arr: T[] | null | undefined, label: string): T[] {
  if (!Array.isArray(arr) || arr.length === 0) {
    throw new Error(`[assertNonEmpty] ${label} is an empty collection — universal assertion is vacuous`);
  }
  return arr;
}

/** Assert 3: instance ids are all distinct (proves "no duplication"). */
export function assertNoDuplicates(
  items: Array<{ instance?: string | null }>,
  label: string,
): void {
  const ids = items.map((i) => i.instance).filter(Boolean) as string[];
  const dup = ids.length - new Set(ids).size;
  if (dup > 0) {
    throw new Error(`[assertNoDuplicates] ${label} has ${dup} duplicate instance ids`);
  }
}
```

---

## 7. Batched processing

Fixes: 324 items in one tick freezing the server for 4.4 s.

```ts
const BATCH_PER_TICK = 4;
const queue: ItemStack[] = [];

system.runInterval(() => {
  for (let i = 0; i < BATCH_PER_TICK && queue.length; i++) {
    const it = queue.shift()!;
    try {
      process(it);
    } catch (e) {
      zlog("batch:error", { error: String(e) });
    }
  }
}, 1);
```

---

## 8. Online player enumeration

Fixes: `getAllPlayers()` returning stale entries, `[undefined]`, and missing simulated players.

```ts
export function onlinePlayers(): Player[] {
  const out: Player[] = [];

  for (const p of world.getAllPlayers()) {
    if (p && p.isValid) out.push(p);        // dual check
  }

  if (!out.length) {                        // fallback: scan dimensions
    for (const dim of ["overworld", "nether", "the_end"]) {
      for (const e of world.getDimension(dim).getEntities({ type: "minecraft:player" })) {
        if (e.typeId === "minecraft:player") out.push(e as Player);
      }
    }
  }

  return out;
}
```

---

## 9. Test-result emission (layer B evidence)

Fixes: robots grading their own homework.

```ts
const PREFIX = "BF_TEST_RESULT ";

function emit(payload: Record<string, unknown>): void {
  console.warn(PREFIX + JSON.stringify(payload));   // console.warn lands in the server log
}

// a self-test hook, triggered by scriptevent
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (ev.id !== "app:selftest") return;

  emit({ id: "selftest", layer: "A", result: "PASS" });
  emit({ id: "capabilities", layer: "A", ...probeCapabilities() });
});
```

Then, on the host:

```bash
grep -a 'BF_TEST_RESULT' evidence/bds-A.log | tail -20
```

> `scriptevent` is far more reliable than `@e[type=...]` selectors in a bot-driven world.

---

## 10. Item classification skeleton

A three-stage detection chain with safe defaults. This shape solved a third-party compatibility
failure where three separate gates each rejected the item.

```ts
export type DetectSource = "vanilla" | "keyword" | "tag";

export interface DetectResult {
  accepted: boolean;
  source: DetectSource | null;
  reason: string;
}

const NEGATIVE_KEYWORDS = ["food", "potion", "arrow", "banner", "banner_pattern"];

export function classify(id: string, tags: string[] = []): DetectResult {
  // 1. vanilla items are never taken over
  if (id.startsWith("minecraft:")) {
    return { accepted: false, source: "vanilla", reason: "vanilla item" };
  }

  // 2. explicit negative keywords veto immediately
  for (const k of NEGATIVE_KEYWORDS) {
    if (id.includes(k)) return { accepted: false, source: "keyword", reason: `neg:${k}` };
  }

  // 3. explicit opt-in tag wins
  if (tags.includes("app:managed")) {
    return { accepted: true, source: "tag", reason: "explicit tag" };
  }

  // 4. keyword inference
  if (/(sword|axe|pickaxe|shovel|hoe|spear|hammer)/.test(id)) {
    return { accepted: true, source: "keyword", reason: "tool keyword" };
  }

  // 5. default: do nothing
  return { accepted: false, source: null, reason: "no match — default is no" };
}
```

> **The default must be "do not take over."**
> Silently transforming an item the user did not intend to change is worse than missing one.

**All gates must use the same classifier.** A path with three interception points that each make
their own decision is how one third-party item passed gate 1 and died at gate 3.

---

## The rule behind all of these

Every template here exists because a specific bug cost hours. They are not style preferences.

| Template | Bug it prevents |
|---|---|
| Safe write queue | Transaction overwrite; watchdog hang |
| Capability probe | Log lying about the runtime |
| Poll with timeout | Flaky timing-dependent tests |
| Server-truth dump | Client cache mistaken for truth |
| Five-state report | "Couldn't" reported as "broken" |
| Foolproof assertions | False passes |
| Batched processing | Server freeze |
| Online player wrapper | Crash on stale entries |
| Result emission | Fabricated verification |
| Explicit classifier | Silent data corruption |