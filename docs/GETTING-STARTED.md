# Getting Started — from zero to a passing test

This is the operational path. No theory, no architecture discussion. Follow it in order and you
will have a server, a bot, and a green test run.

**Time:** ~20 minutes on a fresh Ubuntu host, most of it waiting for downloads.

---

## 0. What you need

| Requirement | Why |
|---|---|
| Ubuntu 22.04 / 24.04 (or similar) | the scripts assume `apt`, `tmux`, `ss` |
| **2 GB RAM minimum, 4 GB comfortable** | BDS alone takes ~400 MB; each bot ~150 MB |
| ~2 GB disk | BDS ≈ 400 MB, node_modules ≈ 300 MB, worlds grow |
| Node 20+ | the protocol stack requires it |
| Root or sudo | to install to `/opt` and create `/usr/local/bin/shctl` |

> **On a 1 GB host, do not run this.** BDS plus a bot plus your shell will OOM, and the OOM
> killer will probably take `sshd` with it. See `PITFALLS-ENVIRONMENT.md`.

---

## 1. Install

```bash
git clone <this-repo> bedrock-flow
cd bedrock-flow

sudo ./tools/bootstrap.sh
```

That script does six things:

1. verifies prerequisites and installs what is missing
2. creates `/opt/bedrock-flow/` with `bds/ slots/ state/ evidence/ tools/`
3. downloads Bedrock Dedicated Server
4. installs the bot runtime (`bedrock-protocol`, `nethernet`, `prismarine-chunk`)
5. installs `shctl` to `/usr/local/bin/`
6. runs a readiness check

### The one check that matters

Near the end it prints:

```
==> verifying chunk decoder coverage
    available: 0.14  1.0  1.18  1.3  common
```

**If that list does not contain your BDS version's major.minor, stop here.**

The bot will connect, read inventory, open containers — and decode the entire world as **air**.
No error. Every world-reading assertion silently fails. See
[`PITFALLS-ENVIRONMENT.md`](PITFALLS-ENVIRONMENT.md#2-silent-dependency-downgrade-the-most-hidden-one).

```bash
# what do I actually have?
ls /opt/bedrock-flow/tools/pb-src/node_modules/prismarine-chunk/src/bedrock/
```

If your version is missing, you need a `prismarine-chunk` build that supports it. This is a hard
dependency, not something you can work around.

---

## 2. Generate a template world

The slot board copies a known-good world into each slot. Create it once.

```bash
cd /opt/bedrock-flow/bds
LD_LIBRARY_PATH=. ./bedrock_server
```

Wait for:

```
[INFO] Server started.
```

Then at the prompt:

```
stop
```

Now preserve it:

```bash
cp -r worlds/bot-world worlds/bot-world.template
```

> The template must be a **freshly generated, never-played** world. If you copy a world you have
> been testing in, every slot inherits your leftover blocks and item entities, and every scenario
> starts dirty.

---

## 3. Start a slot

```bash
sudo -u ubuntu shctl board
```

```
+======================================================================+
|                    BEDROCK FLOW  ·  slot board                       |
+======================================================================+
|  primary A/B + spare C  |  updated 10-24 14:12:33                   |
|  rule: claim -> start -> bot ; stop when done ; never touch another's slot
+======================================================================+

  slot role   state    owner       world         game   disc   pid    bots
  --------------------------------------------------------------------------
  A    main   down     (free)      bot-world     20031  -      -      -
  B    main   down     (free)      dsh-test      20041  -      -      -
  C    spare  down     (free)      spare-world   20051  -      -      -

  free slots: A, B, C
  memory available: 3821 MB
```

Claim and start:

```bash
shctl claim alice
```

```
OK: alice claimed slot A  world=bot-world  game=20031
```

```bash
shctl start alice
```

```
slot A starting (world bot-world game 20031) ...
OK: slot A pid=48213 game=20031 disc=7551 world=bot-world
```

**Write down the `disc=` value.** That is the discovery port, read from the live process, not
guessed. It is the single most important number in this whole system — see
[`SLOT-ISOLATION.md`](SLOT-ISOLATION.md).

### If `disc` is `-`

```
WARN: slot A is up but no discovery port was found — bots will refuse to connect
```

The server may still be booting. Check:

```bash
ss -ulnp | grep 7551
tail -30 /opt/bedrock-flow/evidence/bds-A.log
```

Wait for `Server started` in the log, then re-run `shctl status`.

---

## 4. Connect a bot

```bash
shctl bot alice probe1
```

```
OK: bot 'probe1' -> slot A (game=20031 disc=7551) log /opt/bedrock-flow/evidence/bot-probe1.log
```

Watch it work:

```bash
tail -f /opt/bedrock-flow/evidence/bot-probe1.log
```

A healthy run looks like this:

```
[0.00s] nethernet bot starting | target 127.0.0.1:20031 | version 1.26.51 | name probe1 | HOLD=1
[0.00s] discovery port: 7551
[0.00s] step 1: broadcasting for networkId ...
[0.31s] discovered networkId=12345678901234567
[0.31s] step 2: connecting over nethernet ...
[1.24s] connect_allowed
[1.28s] session
[2.10s] join
[2.44s] SPAWNED as probe1
[5.44s] step 3: capability probe
[5.44s]   entities: 4
[5.44s]   position: 12.5, 64.0, -8.5
[5.44s]   inventory slots: 36
[5.44s]   probe complete
[5.44s] HOLD mode: staying online (heartbeat every 30s, Ctrl-C to quit)
```

### Reading a failure

| Log line | Meaning | Fix |
|---|---|---|
| `no server discovered within 30s` | wrong discovery port, or server not up | check `shctl status` for `disc=` |
| `connect_allowed` never appears | transport mismatch — server is `nethernet`, bot used another | version/transport check |
| `kicked: ...` | server rejected the login | `online-mode=false`? name conflict? |
| `probe error:` | connected but the API shape differs | version mismatch: bot lib vs server |
| connects, but world reads as air | **chunk decoder missing your version** | back to §1 |

---

## 5. Prove the harness works

**Do this before you test your own Add-On.** If the harness is broken, every downstream result
is noise.

```bash
# did the bot actually spawn?
grep -a 'SPAWNED' /opt/bedrock-flow/evidence/bot-probe1.log

# does the server see it?
shctl status --json | python3 -m json.tool
```

```json
{
  "slots": {
    "A": {
      "slot": "A",
      "running": true,
      "pid": 48213,
      "discovery_port": 7551,
      "bots": ["probe1"]
    }
  }
}
```

If `bots` is empty but the log says SPAWNED, the process died — check the tail of the bot log.

### The known-good baseline

A green harness looks like this. Anything less means fix the harness first.

```
✓ connect / spawn          SPAWNED in the log
✓ world decode             entities > 0, position sane
✓ inventory                slots = 36
✓ server sees the bot      bots: ["probe1"] in shctl status
```

---

## 6. Now load an Add-On

Follow [`FIRST-ADDON.md`](FIRST-ADDON.md) to build one, then:

```bash
# copy the packs into the running slot
cp -r mydemo/behavior_pack/*  /opt/bedrock-flow/slots/A/behavior_packs/mydemo_bp/
cp -r mydemo/resource_pack/* /opt/bedrock-flow/slots/A/resource_packs/mydemo_rp/

# register them on the world
cat > /opt/bedrock-flow/slots/A/worlds/bot-world/world_behavior_packs.json <<'EOF'
[ { "pack_id": "<your-bp-header-uuid>", "version": [1,0,0] } ]
EOF

cat > /opt/bedrock-flow/slots/A/worlds/bot-world/world_resource_packs.json <<'EOF'
[ { "pack_id": "<your-rp-header-uuid>", "version": [1,0,0] } ]
EOF

# restart so the packs load
shctl stop alice
shctl start alice
shctl bot alice probe1
```

Then assert against the **server log**, not the bot's output:

```bash
grep -a 'mydemo' /opt/bedrock-flow/evidence/bds-A.log
```

---

## 7. Clean up

```bash
shctl stop alice
shctl release alice
```

> **Always stop.** A running BDS holds ~400 MB. Three idle slots plus a couple of bots will eat a
> 2 GB host, and the OOM killer does not care that you were only testing.

`shctl close` stops every running slot, for when you forget which one is yours.

---

## 8. What to read next

| You want to | Read |
|---|---|
| build an Add-On, all files shown | [`FIRST-ADDON.md`](FIRST-ADDON.md) |
| generate blocks/items/mobs declaratively | [`GENERATOR.md`](GENERATOR.md) |
| write script logic without the common traps | [`SCRIPTS.md`](SCRIPTS.md) |
| copy verified code | [`TEMPLATES.md`](TEMPLATES.md) |
| understand why the tests are shaped this way | [`PITFALLS-TESTING.md`](PITFALLS-TESTING.md) |
| run several workers without collisions | [`SLOT-ISOLATION.md`](SLOT-ISOLATION.md) |
| know what the agent is and is not allowed to do | [`AI-START.md`](AI-START.md) |

---

## Troubleshooting quick table

| Symptom | Most likely cause | Go to |
|---|---|---|
| `shctl: command not found` | bootstrap did not symlink it | `sudo ln -sf /opt/bedrock-flow/tools/shctl.py /usr/local/bin/shctl` |
| `FAIL: board full` | three slots claimed and not released | `shctl board`, then `shctl release <owner>` |
| server starts then exits | port already bound | `ss -ulnp \| grep 2003` |
| `disc=-` forever | server not finished booting, or discovery disabled in properties | check log, check `enable-lan-visibility=true` |
| bot joins the wrong world | discovery port not passed | always use `shctl bot`, never run `netbot.js` by hand |
| everything dies, SSH gone | OOM | `PITFALLS-ENVIRONMENT.md` §10 |
| world reads as air | chunk decoder missing | §1 above |

---

## The one rule

> **Never start a server by hand while the slot board thinks the slot is free.**

That single discipline prevents port collisions, world corruption, and — worst of all — testing
against a server you did not think you were testing against.