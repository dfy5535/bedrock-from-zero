# Pitfalls — Environment

> Environment debugging consumed roughly **30% of total project time** — more than writing code.

Everything here was measured on a real host. None of it is theoretical.

---

## 1. "This version needs no patches" — it did

A claim in the internal handbook said a given 1.26.x build required no patches because it was the
upstream default.

**Measured:**

| State | `totalSections` | `nonAirFound` | Block underfoot |
|---|---|---|---|
| no patch | **0** | **0** | unreadable |
| `subchunk-polling` applied | `nonEmptySections=4222` | — | **sand** |

**Root cause**

```js
// upstream world.js
if (sectionCount >= 0 && !packet.cache_enabled) { ... }
else if (sectionCount < 0) { ... }
```

`>= 0` swallows `== 0` into the "full decode" branch, so `networkDecodeNoCache(payload, 0)` decodes
**zero sections**. And both 1.26.51 and 1.26.52 servers emit `sub_chunk_count=0`.

**How the wrong claim was produced**

```
reasoning: 1.26.51 is the upstream default → upstream tested it → no patch needed
```

Every step is plausible. **The conclusion is false.**
`DEFAULT_BEDROCK_VERSION = '1.26.51'` is a **declaration**, not a verified compatibility proof.

> **A correct protocol number does not mean identical behaviour.**
> 1.26.51 and 1.26.52 share protocol 2193, but **the chunk delivery changed**.
> **Any sentence starting with "should be fine" needs real-machine evidence.**

---

## 2. Silent dependency downgrade (the most hidden one)

**Symptom:** the bot connects, reads inventory, opens containers — **but the decoded world is all air.**

**Root cause**

`package.json` declared fork dependencies:

```json
"prismarine-chunk": "github:.../prismarine-chunk#bedrock-1.26-compat",
"prismarine-recipe": "github:.../prismarine-recipe#bedrock-fix"
```

But `npm install --ignore-scripts` **silently fell back to the official version**:

```
$ ls node_modules/prismarine-chunk/src/bedrock/
0.14  1.0  1.18  1.3  common        ← no 1.26!
```

The official package's 1.26 decode path produces no blocks.

**Fix**

```bash
npm install --ignore-scripts
# ★ verify ★
ls node_modules/prismarine-chunk/src/bedrock/     # MUST contain a 1.26 directory
npm rebuild raknet-native                          # native binding separately
```

> **After installing dependencies you must verify you got the one you asked for.**
> `npm install` succeeding ≠ installed correctly.
> **Checkpoint:** does `src/bedrock/` contain `1.26`?

---

## 3. `crafting_data` parsed into zero recipes

```
hasCraftingData : true      ← the server really did send it
recipesCount    : 0         ← the library parsed nothing
```

All crafting unusable.

> **"The server sent it" ≠ "the client can parse it."**
> Debug this class in layers:
> - Did the server send it? (log / packet capture)
> - Did the library receive it? (events)
> - What did parsing produce? (result)
>
> Three layers checked separately is the only way to find which one is broken.

---

## 4. Version ↔ API compatibility (measured)

| BDS version | `@minecraft/server` supported | Note |
|---|---|---|
| 1.26.20.5 | 2.0.0 – **2.7.0** | 2.8.0+ rejected |
| 1.26.45.1 | — | `minecraft-data` has no block data |
| 1.26.51.1 | 2.0.0 – **2.7.0+** | `blockContainerOpened` needs 2.8.0+ |
| 1.26.52.3 | 2.0.0 – **2.10.0** | production target |

Known specifics:
- `blockContainerOpened` requires **2.8.0+**
- `playerCraftRecipe` exists in **2.12.0-beta** — **not in 2.10.0 stable**

> **Never copy from "latest beta docs" into a stable-version project.**
> Check the **actual `.d.ts` of your target version.**

---

## 5. `min_engine_version` too high → the whole pack is rejected

```
The property '/header/min_engine_version' has a version of '1.26.52'
which is too high. The highest value we accept is '1.26.51'.
```

→ `Pack Stack - None`, pack **entirely unloaded**.

`min_engine_version` must be **≤ the actually running BDS version**. It is a **hard gate**, not a
hint. When shipping to others, declare the **lowest** supported version.

---

## 6. `allowlist.json` blocks startup

```
ERROR: Using an allowlist without online authentication can be dangerous and is not allowed.
```

An `allowlist.json` present with `online-mode=false` → refuses to start.

**Fix:** `allow-list=false` in `server.properties`, and delete `allowlist.json`.

---

## 7. `setblock` fails in a fresh world

```
ERROR: The block couldn't be placed
```

even at perfectly valid coordinates.

**Cause:** the spawn chunks of a **newly created world are not ticking**, so the block update is
dropped.

**Fix:**

```
tickingarea add <x0> 0 <z0> <x1> 0 <z1> <name>
```

> **"Correct syntax" ≠ "the command will succeed."**
> Fresh world / unloaded chunk / insufficient permission all make `setblock` fail silently.

---

## 8. Port conflict — and the far worse consequence

```
Port [19162] may be in use by another process.
Exiting program
```

Then it crashes.

**The dangerous part is not the crash.** Several rounds of "1.26.51 testing" were actually connected
to the **old 1.26.52 server**, because the old process never exited. **Every conclusion from those
rounds was invalid.**

**Fix**

```bash
tmux -S <sock> send-keys -t <session> 'stop' Enter
sleep 10
ss -lunp | grep 19162          # confirm the port is really free
pkill -9 -x bedrock_server     # only if still alive
```

> **Before starting a new server, confirm the port is genuinely free and the process genuinely dead.**
> Otherwise you get results that **look normal but are measuring the wrong server** — worse than a
> crash.

---

## 9. `transport=raknet` binds default ports regardless of config

```properties
server-port=19162
```

yet the server **also** binds 19132/19133.

Consequences: it steals the production server's port, runs a second 387 MB BDS, and can trigger a
system-wide OOM.

> **Never run multiple BDS instances at once.**
> Iron rule: **one BDS instance at a time.** Check with a guard script before every start.

---

## 10. The OOM incident

**Timeline**

```
10:17  kernel OOM killer fired
       Out of memory: Killed process <service>
10:17-10:32  continuous "Under memory pressure, flushing caches"
10:32  journal logging interrupted (system wedged)
10:57  provider forced a reboot
```

The host was effectively dead for ~40 minutes.

**Memory ledger**

```
active_anon:   1.62 GB
inactive_anon: 1.59 GB
anonymous total ≈ 3.26 GB    ← all process heap
active_file:   104 KB        ← ★ page cache crushed to near zero = proof of exhaustion
free:          14 MB
```

**Culprit:** 5 node test processes (~1.6 GB) + 1 BDS (387 MB) ≈ **2.03 GB** on a 4 GB host.

**Three-layer fix**

| Layer | Change |
|---|---|
| swap | 2 GB → **4 GB** |
| earlyoom | `-m 8 -M 4`, protect sshd/systemd/nginx, prefer killing bedrock/node/python3 |
| cgroup | BDS-specific slice `MemoryMax=1500M` |

> **The diagnostic signal is `active_file` near zero** — that means memory exhaustion, not a leak.
> **A test server must be stopped when done.** Do not leave it running.

---

## 11. tmux socket owned by the wrong user

```
error connecting to /.../tmux-12651.sock (Permission denied)
```

**Cause:** the session was created with `sudo` (root), so the socket is owned by root, while the
service runs as `bedrock`.

**Fix**

```bash
sudo rm -f <sock>
sudo -u bedrock tmux -S <sock> new-session -d -s <name> ...
```

> **Whatever user the service runs as, that user must create its resources.**
> Creating them as root locks out every subsequent operation.

---

## 12. Nested-quote hell

Writing a JSON/TS file through `ssh host "...heredoc..."` silently ate the quotes:

```json
{ format_version: 2, header: { name: probe } }   ← all quotes gone
```

**Fix — write locally, then copy:**

```bash
# ✗ fragile
ssh gz "cat > /tmp/x.json <<'EOF'
{\"a\":1}
EOF"

# ✓ reliable
cat > /tmp/x.json <<'EOF'
{"a":1}
EOF
scp /tmp/x.json gz:/tmp/
```

> **For structured data crossing layers, use a file, not a command string.**
> Quotes get consumed by bash → ssh → remote bash.

---

## 13. Manually copied directories are owned by root

```
PermissionError: [Errno 13] Permission denied: 'recipes'
```

A `sudo cp` of the pack directory made root the owner, while the test harness runs as an
unprivileged user and cannot delete it.

> **Do not race your automation for directory ownership.**
> If the harness deploys it, let the harness deploy it.

---

## 14. Global registry disagrees with what is actually deployed

Validation failed permanently:

```
[FAIL] L3.min_engine_version
```

**Cause:** the validator reads the **global** `registry/runtime.json` claiming `1.26.52.3`, but the
**actually deployed** BDS is `1.26.51.1`.

→ manifest declared `[1,26,52]` → the production server rejected the pack
→ the test harness collected zero results

**Fix — align three places:**

1. `registry/runtime.json` → the deployed version (back it up first)
2. `design.yaml` → `runtime.minecraft`
3. both `manifest.json` → `min_engine_version`

> **"The version your config declares" and "the version actually deployed" must match.**
> Otherwise the tool validates one thing and the server loads another — they fight, and you never
> pass.
> **When they disagree, change the config to match reality. Not the reverse.**

---

## Checklists

### Before every work session

```bash
pgrep -x bedrock_server                    # 1. any server already running?
ss -lunp | grep -E '191[0-9]{2}'           # 2. ports occupied?
free -m                                    # 3. enough memory?
<guard script> guard                       # 4. guard passes?
```

### After every deploy

```bash
grep -m1 'Version:' <log>                  # 1. right version?
grep 'Pack Stack' <log>                    # 2. pack loaded?
grep '\[Scripting\] ERROR' <log>           # 3. script errors?
grep 'booted' <log>                        # 4. self-test started?
```

### When a test fails

```
suspect the test → then the environment → then the product
```

The order matters. See [`PITFALLS-TESTING.md`](PITFALLS-TESTING.md).