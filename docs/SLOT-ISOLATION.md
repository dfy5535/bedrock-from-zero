# Slot Isolation

Why two agents cannot share one Bedrock server — and how the slot board fixes it.

---

## The root cause

`nethernet` (the transport used by modern Bedrock Dedicated Server) broadcasts a discovery
service on **a single host-global UDP port** — `7551` in the current implementation.

```js
// nethernet/src/server.js — the port is hard-coded
socket.bind(7551)
```

Consequences, all observed in production:

1. **Only one BDS on a host can own `7551`.** The second instance that starts loses the race and
   is silently pushed to a random ephemeral port (e.g. `44431`).
2. **A headless bot discovers by broadcasting to `7551`.** It therefore always finds
   *whichever server won the race* — which is usually not the one its owner started.
3. **The bot then joins the wrong world.** If both agents share a directory, they also share
   world files and the game port, and the two runs corrupt each other.

Symptom in practice: agent A runs a test, sees an unexpected result, and discovers its bot was
inside agent B's world the entire time. Hours of "debugging" a bug that never existed.

---

## The fix: three things per slot, plus a detected port

Each slot must own three resources, and must communicate the fourth:

| Resource | Why |
|---|---|
| **Distinct game port** | Two servers cannot bind the same TCP/UDP port |
| **Distinct world directory** | Shared directories = shared world files = corruption |
| **Distinct save/install copy** | A BDS install with a live `worlds/` lock is not shareable |
| **Detected discovery port** | The bot must broadcast to *this* server, not to the default |

That last row is the one everyone forgets. It cannot be configured statically, because whether a
given server gets `7551` or an ephemeral port depends on start order. It must be **probed after
the server is up**.

---

## The board

```
┌──────────────────────────────────────────────────────────────┐
│  SLOT BOARD                                                  │
│  A  20031  bot-world    discovery=33010  owner=alice   ●run  │
│  B  20041  dsh-test     discovery=7551   owner=bob     ●run  │
│  C  20051  spare-world  discovery=-      owner=(free)  ○stop │
└──────────────────────────────────────────────────────────────┘
```

Commands:

```bash
shctl board                  # human-readable board (this is what you screenshot into a report)
shctl status --json          # machine-readable
shctl claim alice            # take a free slot; flock-protected, idempotent per owner
shctl start alice            # copy/prepare the slot's install, start BDS, detect discovery port
shctl bot   alice alice_bot  # start a bot pinned to alice's detected discovery port
shctl stop  alice            # stop that slot's BDS
shctl release alice          # give the slot back (auto-stops first if still running)
shctl reap                   # reclaim slots claimed but idle for too long
```

---

## The critical mechanism: discovery-port injection

`nethernet` reads the discovery port from the environment **at module load time**:

```js
// nethernet/src/client.js
const DISCOVERY_PORT = Number(process.env.NETH_DISCOVERY_PORT || 7551)
```

And uses it as the broadcast target:

```js
// client.js — the broadcast destination
socket.send(msg, 0, msg.length, DISCOVERY_PORT, '255.255.255.255')
```

Therefore **no bot source change is needed.** The board simply exports the right value:

```bash
NETH_DISCOVERY_PORT=33010 BOT_PORT=20031 BOT_NAME=alice_bot node bf-netbot.js
```

`wbot` does this automatically by consuming `shctl env`:

```bash
eval "$(shctl env alice)"
# WORKER_SLOT=A  BOT_PORT=20031  NETH_DISCOVERY_PORT=33010 ...
```

> **Rule: never start a bot without `NETH_DISCOVERY_PORT`.** A bot on the default port is not
> "usually fine" — it is a coin flip that silently corrupts someone's run.

---

## Detection: how the board finds the real port

After starting a slot's BDS, the board inspects the actual UDP sockets owned by that process:

```bash
ss -ulnp | grep "pid=$BDS_PID"
#   UNCONN 0 0 *:7551  *:*  users:(("bedrock_server",pid=1234,fd=18))
#   UNCONN 0 0 *:33010 *:*  users:(("bedrock_server",pid=1234,fd=15))
```

It must distinguish the **discovery** socket from the **game** socket. Current heuristic:

- The game sockets bind the configured `server-port` / `server-portv6`.
- Any remaining UDP socket owned by the process is the discovery port.

If detection fails, the board returns `None` and **refuses to guess**. The earlier version of
this tool defaulted to `7551` on failure — which is precisely how a bot gets pointed into a
stranger's world. `None` is a safe answer; a guess is not.

---

## Reaping: why slots leak

An agent crashes, or a user closes a terminal. The slot stays claimed and the BDS keeps running,
consuming 300–800 MB. Then the next agent finds "no free slots" on a machine that is actually idle.

`sh-guard` runs on a timer and enforces two rules:

| Condition | Action |
|---|---|
| Slot claimed but BDS not running for > 60 min | Release the claim |
| Slot running but no interaction for > 30 min | Stop the BDS, then release |

"Running" is determined by **RSS**, not by the presence of a tmux session. A leftover tmux
window with a dead process is the single most common false-positive in this whole system:

```python
# a tmux session is not evidence of life
running = rss_kb > RSS_MIN_KB     # ~50 MB
```

---

## Port leasing (optional, complementary)

`portctl` is a second, finer-grained layer for non-BDS services that share the same port range.
It provides:

- **Segment isolation** — each identity owns a disjoint port range.
- **Leases** — a `flock`-protected JSON ledger; conflicts raise loudly instead of racing.
- **Orphan detection** — a listening port with no lease is reported as a wild process.

```
bf     20033-20040     shared   20049
dsh      20041-20048     lab      20050-20059
reserved 20031-20032     (never leased)
```

`portctl` and `shctl` are **independent by design**. `shctl` governs whole BDS instances;
`portctl` governs auxiliary services. If both run, `portctl doctor` will report the slot's BDS
port as an "orphan" — that is expected, and the report should say so rather than alarming.

---

## Failure modes and what they look like

| Symptom | Likely cause | Check |
|---|---|---|
| Bot connects to the wrong world | Missing `NETH_DISCOVERY_PORT` | `tr '\0' '\n' < /proc/<botpid>/environ \| grep NETH` |
| Two bots fight over one world | Two slots point at the same directory | `shctl status --json` |
| Board says free, nothing starts | Stale claim, process gone | `shctl reap` |
| Bot reports SPAWNED but no world effect | Right server, wrong slot's world | compare `BOT_PORT` with the slot's game port |
| Discovery port is `None` | Server still booting, or detection regex stale | wait, re-run `shctl start`, then `ss -ulnp` manually |