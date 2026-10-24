# BDS — running the server that proves things

Bedrock Dedicated Server is the witness. This document is how to run it so that its testimony
is trustworthy and so that it does not destroy the machine it runs on.

---

## Why BDS is non-negotiable

No BDS ⇒ no layer B ⇒ no runtime evidence ⇒ only `STATIC_VERIFIED` at best.
A pack that has never been loaded into a real server is an **unverified pack**, no matter how
many schemas it passes.

---

## Version and transport

Modern BDS (1.26.x and later) uses **`nethernet`** transport, not RakNet.

```
transport        : nethernet
discovery        : UDP broadcast, host-global port (7551 by default)
game             : the configured game port(s)
```

Implications:

1. **A bot must speak `nethernet`**, or it will not connect at all.
2. **Discovery is LAN-scoped.** A bot on the same host works; a bot across the internet needs
   different arrangements entirely.
3. **The discovery port is a shared resource.** This is the origin of the whole slot-isolation
   problem — see [`SLOT-ISOLATION.md`](SLOT-ISOLATION.md).

> There is a common belief that a given 1.26.x build "needs no patches". Treat that as
> **unverified** until you have loaded it and read the log. Chunk decoding in particular has
> historically required attention (`sub_chunk_count=0` producing zero decoded sections). If
> `columns` or `sections` come back as 0 in the bot's `ready()` result, that is the symptom.

---

## Directory layout per instance

```
slots/A/
├── bedrock_server              # the binary
├── server.properties           # config (per slot!)
├── allowlist.json
├── permissions.json
├── behavior_packs/             # <-- your Add-On's BP
├── resource_packs/             # <-- your Add-On's RP
├── worlds/
│   └── <world-name>/
│       ├── level.dat
│       ├── world_behavior_packs.json
│       ├── world_resource_packs.json
│       └── db/
└── logs/
```

**Never share a directory between slots.** Two servers reading/writing one `worlds/` directory is
the fastest way to corrupt a world and to produce unfalsifiable test results.

---

## `server.properties` — the settings that matter

```properties
server-name=test-A
server-port=20031
server-portv6=20032

# World
level-name=bot-world
gamemode=creative
difficulty=normal
max-players=2

# Discovery
enable-lan-visibility=true

# Auth
online-mode=false
allow-cheats=true

# Load
view-distance=32
```

### `enable-lan-visibility=true` — do not turn this off

There is widespread advice to set this to `false` as a "security hardening" step. In the
`nethernet` era that advice is **wrong** and will break your bots:

| Setting | Effect |
|---|---|
| `true` | Server answers discovery broadcasts → bots find it |
| `false` | Server does not answer → bot reports **"30s, server not discovered"** |

It does **not** cause the server to hijack `19132`/`19133`. Verify that claim rather than
believing it:

```bash
ss -tulnp | grep -E '19132|19133'    # expect: no output
```

> **Verified behaviour:** with `enable-lan-visibility=true`, discovery works and `19132` remains
> unbound. Keep it `true`.

### `online-mode` and `allow-cheats`

For a local, isolated test server these are acceptable:

```properties
online-mode=false
allow-cheats=true
```

> **Never expose this configuration to the public internet.** `allow-cheats=true` plus
> `online-mode=false` means any player who connects can run arbitrary commands.

### `max-players`

Set it to the number of bots plus real players you expect. On a small VPS, **2** is the honest
number: each player costs memory, and the third connection is a common way to OOM the host.

---

## Starting it

BDS reads stdin. Long-lived, reattachable stdin is what you need, which is what `tmux` provides.

```bash
tmux new-session -d -s bdsA -c /opt/bedrock-flow/slots/A
tmux send-keys -t bdsA './bedrock_server' Enter
```

Then pin the log:

```bash
# follow
tail -f /opt/bedrock-flow/evidence/bds-A.log

# or redirect inside the session:
tmux send-keys -t bdsA './bedrock_server 2>&1 | tee -a /opt/bedrock-flow/evidence/bds-A.log' Enter
```

### Sending console commands

```bash
tmux send-keys -t bdsA 'list' Enter
tmux send-keys -t bdsA 'say hello' Enter
tmux send-keys -t bdsA 'give probe_bot diamond 5' Enter
```

Read the answer from the **log**, always. `tmux send-keys` has no return value.

```bash
tail -20 /opt/bedrock-flow/evidence/bds-A.log | grep -i 'players online'
```

### Stopping it cleanly

```bash
tmux send-keys -t bdsA 'stop' Enter
sleep 5
tmux kill-session -t bdsA 2>/dev/null
```

`stop` (the console command) flushes the world. `Ctrl-C` may not. **Always `stop` first** — a
killed server can leave a world lock behind and the next start will hang forever with no error.

---

## Worlds: create, reset, isolate

Test in a throwaway world. Never test destructive behaviour in a world you care about.

```bash
# fresh world for a test run
rm -rf slots/A/worlds/bot-world

# then start; BDS regenerates it from scratch
```

A regenerated world is also the only reliable way to test **worldgen**: if the ore already exists
because you placed it, you proved nothing about generation.

---

## Resource discipline (this is where people lose their SSH)

Bedrock Dedicated Server is memory-hungry and unbounded by default. On a 1–4 GB VPS, one runaway
instance can trigger the OOM killer, which frequently takes `sshd` with it — and then you have
lost access to the machine and need a provider console to recover.

### Always cap it

```bash
systemd-run --scope \
  -p MemoryMax=3G \
  -p MemorySwapMax=1G \
  -p MemoryHigh=2.4G \
  -p TasksMax=768 \
  ./bedrock_server
```

| Limit | Purpose |
|---|---|
| `MemoryMax` | Hard ceiling; the cgroup is killed, not the host |
| `MemoryHigh` | Soft ceiling; throttles before the hard kill |
| `MemorySwapMax` | Prevents swap thrash from stalling everything |
| `TasksMax` | Contains thread explosion |

### Use early OOM

Install `earlyoom` so the kernel kills the *server* before it kills your session:

```bash
earlyoom -m 10 -s 10 --prefer '(bedrock_server|node)' --avoid '(sshd|systemd)'
```

### Never do this on a small VPS

```bash
du -sh /          # walks the whole disk
find / -name '*'  # same
systemd-analyze blame   # allocates heavily
```

Any of these, run concurrently with a BDS, has caused real OOM-kills of `sshd`. On a
memory-constrained host, run them **serially** and ideally when the server is stopped.

---

## Reading the log — what actually counts as evidence

The log is the only witness. These are the lines worth grepping:

| Question | Grep |
|---|---|
| Did the pack load? | `behavior_pack` / `resource_pack` / `Pack` |
| Did the block register? | `registered` / `custom block` |
| Did the block break? | `block at <x>,<y>,<z>` |
| Did something drop? | `Item entity spawned` |
| Did the player get it? | `Player .* received` |
| Did the script run? | `[Scripting]` / script exception traces |
| Did a script event fire? | `Script event <ns>:<name>` |
| How many players? | `players online` |
| What version? | `Version: ` |

### Machine-readable results

Have the test harness emit one line per case directly into the log:

```
BF_TEST_RESULT {"id":"ore_drops","layer":"B","expect":"item_dropped","actual":"item_dropped","result":"PASS"}
```

Then:

```bash
grep -a 'BF_TEST_RESULT' evidence/bds-A.log \
  | sed 's/.*BF_TEST_RESULT //' \
  | python3 -c 'import sys,json;[print(json.loads(l)["result"]) for l in sys.stdin]'
```

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Process alive, port not listening | World lock from an unclean shutdown | `stop` properly; `rm` the lock file if wedged |
| Starts then exits immediately | Port already bound by another instance | `ss -tulnp \| grep <port>` |
| Bot cannot discover server | `enable-lan-visibility=false`, or wrong discovery port | Set `true`; set `NETH_DISCOVERY_PORT` |
| `setblock` fails "no chunk" | World still loading | Wait for spawn, then wait again |
| Everything dies at once, SSH lost | OOM killer | Cap the cgroup; install `earlyoom` |
| Two servers fight | Shared directory or shared port | One slot per instance |
| World corrupted after a test | Killed instead of `stop` | Always `stop` |

---

## What BDS proves and does not prove

**Proves:** registration, runtime behaviour, loot, recipes, events, persistence, worldgen.

**Does not prove:** textures, models, particles, UI layout, sound, "does it look right".

That boundary is not a limitation of this framework. It is a limitation of running a server.
Which is exactly why layer C is `MANUAL_GATE` and never auto-passed.