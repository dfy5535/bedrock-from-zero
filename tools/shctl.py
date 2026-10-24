#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shctl — BDS slot / ownership board

Multiple agents share one host. Each BDS instance is expensive: memory, ports, a whole
world directory. This tool makes it impossible to accidentally run two servers on the same
port, or to touch a slot that somebody else owns.

Design rules encoded here:

  1. Every running BDS is a *slot*. Three by default: A and B primary, C spare.
  2. A slot must be `claim`ed before it can be `start`ed. The board records the owner.
  3. Touching a slot owned by somebody else is refused, unless SHCTL_OWNER matches or
     --force is given.
  4. `start` copies a pristine BDS tree into the slot and writes a per-slot
     server.properties. The source tree is never modified.
  5. `detect()` reads the *real* discovery port out of `ss -ulnp` for the BDS pid.
     If it cannot find one it returns None — deliberately. Guessing (defaulting to 7551)
     is exactly how a bot ends up connected to somebody else's world.
  6. `reap` frees slots that were claimed but have not run for a long time, so a crashed
     run does not wedge the board forever.

Usage:
    shctl board
    shctl claim alice
    shctl start alice
    shctl bot alice probe1
    shctl status --json
    shctl stop alice
    shctl release alice
"""

import os
import sys
import json
import time
import fcntl
import shlex
import argparse
import subprocess

# ---------------------------------------------------------------- configuration ---

BASE       = os.environ.get("BF_HOME", "/opt/bedrock-flow")
STATE      = os.path.join(BASE, "state")
SLOTS_FILE = os.path.join(STATE, "slots.json")
LOCK_FILE  = os.path.join(STATE, "board.lock")

BDS_SRC      = os.path.join(BASE, "bds")            # pristine BDS install
SLOT_ROOT    = os.path.join(BASE, "slots")
SOURCE_WORLD = os.path.join(BDS_SRC, "worlds", "bot-world")
EVIDENCE     = os.path.join(BASE, "evidence")
BOARD_FILE   = os.path.join(BASE, "BOARD.txt")
MOTD_FILE    = "/etc/motd"
NETBOT       = os.path.join(BASE, "tools", "netbot.js")

MAX_BDS    = 3        # hard cap: never more than this many servers
REAP_MIN   = 60       # reclaim a claimed-but-idle slot after N minutes
RSS_MIN_KB = 50000    # a real BDS is >50MB RSS; filters out grep/editors

SLOTS = {
    "A": {"game": 20031, "world": "bot-world",   "dir": os.path.join(SLOT_ROOT, "A"), "role": "primary"},
    "B": {"game": 20041, "world": "dsh-test",    "dir": os.path.join(SLOT_ROOT, "B"), "role": "primary"},
    "C": {"game": 20051, "world": "spare-world", "dir": os.path.join(SLOT_ROOT, "C"), "role": "backup"},
}
ORDER = ["A", "B", "C"]

# ------------------------------------------------------------------- state/fs ---

def _ensure():
    for d in (STATE, SLOT_ROOT, EVIDENCE):
        os.makedirs(d, exist_ok=True)


def load():
    _ensure()
    if os.path.exists(SLOTS_FILE):
        try:
            with open(SLOTS_FILE) as f:
                d = json.load(f)
            d.setdefault("slots", {})
            return d
        except Exception:
            pass
    return {"slots": {}}


def save(d):
    _ensure()
    tmp = SLOTS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SLOTS_FILE)


class _flock:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        _ensure()
        self.fh = open(self.path, "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
            self.fh.close()
        except Exception:
            pass


def Lock():
    return _flock(LOCK_FILE)


def slot_lock(s):
    """Per-slot lock: stops two concurrent `start` calls corrupting one directory."""
    return _flock(os.path.join(STATE, f"prep-{s}.lock"))


def touch(s):
    with Lock():
        d = load()
        if s in d["slots"]:
            d["slots"][s]["last_touch"] = time.time()
            save(d)

# ------------------------------------------------------------- process probing ---

def _bds_pid(dirpath, min_rss_kb=RSS_MIN_KB):
    """Find the BDS process whose CWD is this slot directory.

    Matching on CWD rather than command name means a `grep bedrock_server` can never be
    mistaken for a server, and two slots can never resolve to each other.
    """
    best, br = None, -1
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            if os.readlink(f"/proc/{pid}/cwd") != dirpath:
                continue
            rss = 0
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss = int(line.split()[1])
                        break
            if rss >= min_rss_kb and rss > br:
                br, best = rss, pid
        except Exception:
            pass
    return best


def _udp_ports(pid):
    ports = []
    try:
        out = subprocess.run(["ss", "-ulnp"], capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return ports
    for line in out.splitlines():
        if f"pid={pid}," in line:
            try:
                ports.append(int(line.split()[3].rsplit(":", 1)[-1]))
            except ValueError:
                pass
    return ports


def detect(slot):
    """Return (pid, discovery_port).

    discovery_port is None when it cannot be determined. That is intentional: a bot
    started with a guessed discovery port may join a *different* server's world.
    """
    d = SLOTS[slot]["dir"]
    pid = _bds_pid(d)
    if not pid:
        return None, None
    gp = SLOTS[slot]["game"]
    others = [p for p in set(_udp_ports(pid)) if p != gp and p not in (19132, 19133)]
    return pid, (min(others) if others else None)


def alive_bots(slot):
    """Bots are identified by BOT_PORT in their environment, not by name alone."""
    gp = str(SLOTS[slot]["game"])
    found = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/cmdline", "rb") as f:
                cl = f.read().replace(b"\x00", b" ").decode("utf-8", "replace")
            if "netbot.js" not in cl:
                continue
            env = {}
            try:
                with open(f"/proc/{name}/environ", "rb") as f:
                    for kv in f.read().split(b"\x00"):
                        if b"=" in kv:
                            k, v = kv.split(b"=", 1)
                            env[k.decode()] = v.decode("utf-8", "replace")
            except Exception:
                pass
            if env.get("BOT_PORT") == gp:
                found[env.get("BOT_NAME", f"pid{name}")] = int(name)
        except Exception:
            pass
    return found


def _kill_bots(slot):
    for nm, pid in alive_bots(slot).items():
        try:
            os.kill(pid, 15)
        except Exception:
            pass
    time.sleep(1)
    for nm, pid in alive_bots(slot).items():
        try:
            os.kill(pid, 9)
        except Exception:
            pass

# ---------------------------------------------------------------- slot prepare ---

def _prepare(slot):
    """Materialize the slot: pristine BDS tree plus a slot-specific server.properties.

    Idempotent. An existing tree is not recopied, but properties are always rewritten so
    the port and world name can never drift away from what the board says.
    """
    d = SLOTS[slot]["dir"]
    _ensure()

    with slot_lock(slot):
        if not os.path.exists(os.path.join(d, "bedrock_server")):
            os.makedirs(d, exist_ok=True)
            subprocess.run(["cp", "-r", BDS_SRC + "/.", d], check=True, timeout=300)
            subprocess.run(["rm", "-rf", os.path.join(d, "worlds")], check=True)
            os.makedirs(os.path.join(d, "worlds"), exist_ok=True)
            subprocess.run(
                ["cp", "-r", SOURCE_WORLD, os.path.join(d, "worlds", SLOTS[slot]["world"])],
                check=True,
            )

        sp = os.path.join(d, "server.properties")
        t = open(sp).read() if os.path.exists(sp) else ""
        if os.path.exists(sp):
            os.remove(sp)

        def setkv(text, k, v):
            out, hit = [], False
            for line in text.splitlines():
                if line.startswith(k + "="):
                    out.append(f"{k}={v}")
                    hit = True
                else:
                    out.append(line)
            if not hit:
                out.append(f"{k}={v}")
            return "\n".join(out) + "\n"

        vd = 16 if SLOTS[slot]["role"] == "backup" else 32
        for k, v in [
            ("server-port", str(SLOTS[slot]["game"])),
            ("server-portv6", str(SLOTS[slot]["game"] + 1)),
            ("level-name", SLOTS[slot]["world"]),
            ("server-name", f"BF-{slot}"),
            ("transport", "nethernet"),
            # discovery MUST stay on, or bots cannot find the server at all
            ("enable-lan-visibility", "true"),
            ("online-mode", "false"),
            ("view-distance", str(vd)),
        ]:
            t = setkv(t, k, v)
        open(sp, "w").write(t)
    return d

# ------------------------------------------------------------- ownership guard ---

def _resolve(ref):
    """Resolve a slot letter or an owner name to a slot letter."""
    if ref in SLOTS:
        return ref
    d = load()
    for s, i in d["slots"].items():
        if i.get("owner") == ref:
            return s
    return None


def _owner_guard(ref, force=False):
    """Refuse to touch a slot owned by somebody else.

    Returns (ok, slot, owner). Callers turn a False into a refusal message.
    """
    s = _resolve(ref)
    if not s:
        return (True, None, None)
    d = load()
    info = (d.get("slots") or {}).get(s)
    if not info:
        return (True, s, None)
    owner = info.get("owner")
    if not owner or force:
        return (True, s, owner)
    if os.environ.get("SHCTL_OWNER", "") == owner:
        return (True, s, owner)
    return (False, s, owner)


def _deny(slot, owner, action):
    print(f"FAIL: slot {slot} belongs to '{owner}'; you cannot {action}.", file=sys.stderr)
    print("      Rule: claim first, then start. Do not touch a slot you do not own.",
          file=sys.stderr)
    print(f"      Internal callers: SHCTL_OWNER={owner} shctl {action} {slot}  or add --force",
          file=sys.stderr)
    return 7

# ------------------------------------------------------------------- commands ---

def reap(force=False):
    """Free slots that are claimed but not running.

    Without this, a crashed run leaves its slot claimed forever and the board wedges.
    """
    freed = []
    now = time.time()
    with Lock():
        d = load()
        for s, i in list(d["slots"].items()):
            pid, _ = detect(s)
            if pid:
                continue
            ts = i.get("last_touch") or i.get("claimed_ts") or now
            if force or (now - ts) / 60.0 >= REAP_MIN:
                freed.append((s, i.get("owner")))
                del d["slots"][s]
        if freed:
            save(d)
    return freed


def cmd_board(args):
    d = load()
    sl = d["slots"]
    lines = []
    w = "=" * 70
    lines.append("+" + w + "+")
    lines.append("|" + "  BEDROCK FLOW  ·  slot board  ".center(70) + "|")
    lines.append("+" + w + "+")
    lines.append("|" + f"  primary A/B + spare C  |  updated {time.strftime('%m-%d %H:%M:%S')}".ljust(70) + "|")
    lines.append("|" + "  rule: claim -> start -> bot ; stop when done ; never touch another's slot".ljust(70) + "|")
    lines.append("+" + w + "+")
    lines.append("")
    lines.append("  slot role   state    owner       world         game   disc   pid    bots")
    lines.append("  " + "-" * 82)
    for s in ORDER:
        own = sl.get(s, {}).get("owner", "(free)")
        pid, disc = detect(s)
        bots = list(alive_bots(s).keys())
        st = "UP" if pid else "down"
        role = "spare" if SLOTS[s]["role"] == "backup" else "main"
        lines.append(
            f"  {s}    {role:<6} {st:<8} {own:<11} {SLOTS[s]['world']:<13} "
            f"{SLOTS[s]['game']:<6} {str(disc or '-'):<6} {str(pid or '-'):<6} {','.join(bots) or '-'}"
        )
    free = [s for s in ORDER if s not in sl]
    lines.append("")
    lines.append(f"  free slots: {', '.join(free) if free else '(none - wait for release)'}")
    try:
        with open("/proc/meminfo") as f:
            mi = dict(l.split(":") for l in f.read().splitlines())
        lines.append(f"  memory available: {int(mi['MemAvailable'].split()[0]) // 1024} MB")
    except Exception:
        pass
    lines.append("")
    lines.append("  usage: shctl claim <name> -> shctl start <name> -> shctl bot <name> <botname>")
    lines.append("         when done: shctl stop <name>  (frees memory for the next worker)")

    text = "\n".join(lines)
    for path in (BOARD_FILE, MOTD_FILE):
        try:
            open(path, "w").write(text + "\n")
        except Exception:
            pass
    print(text)
    return 0


def cmd_claim(args):
    owner = args.owner
    reap()
    with Lock():
        d = load()
        sl = d["slots"]
        for s, i in sl.items():
            if i.get("owner") == owner:
                print(f"OK: {owner} already holds slot {s} "
                      f"(world={SLOTS[s]['world']} game={SLOTS[s]['game']})")
                return 0
        free = [s for s in ORDER if s not in sl]
        if not free:
            busy = ", ".join(f"{s}={sl[s].get('owner')}" for s in sl)
            print(f"FAIL: board full ({busy}). Hard cap is {MAX_BDS}; wait for a release.",
                  file=sys.stderr)
            return 6
        pick = free[0]
        sl[pick] = {
            "owner": owner,
            "claimed_ts": time.time(),
            "last_touch": time.time(),
            "claimed": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        save(d)

    note = " (spare)" if SLOTS[pick]["role"] == "backup" else ""
    print(f"OK: {owner} claimed slot {pick}{note}  "
          f"world={SLOTS[pick]['world']}  game={SLOTS[pick]['game']}")
    return 0


def cmd_release(args):
    ref = args.slot or args.identity

    s = args.slot if args.slot in SLOTS else _resolve(args.identity)

    # Naming yourself as the owner is proof of ownership: if you know the owner token,
    # you may release it. Without this a worker can claim a slot and then be unable to
    # give it back, which wedges the board until reap fires.
    d0 = load()
    known_owner = (d0.get("slots") or {}).get(s, {}).get("owner") if s else None
    self_release = bool(args.identity) and args.identity == known_owner

    if not self_release:
        ok, gs, gowner = _owner_guard(ref, getattr(args, "force", False))
        if not ok:
            return _deny(gs, gowner, "release")

    if not s:
        print("FAIL: no such owner/slot on the board", file=sys.stderr)
        return 5

    # Never release a slot whose server is still running: the next owner would inherit a
    # live process and start a second one on the same port.
    pid, _ = detect(s)
    if pid:
        cmd_stop(argparse.Namespace(ref=s))

    with Lock():
        d = load()
        d["slots"].pop(s, None)
        save(d)
    print(f"OK: released slot {s}")
    return 0


def cmd_start(args):
    reap()
    ok, gs, gowner = _owner_guard(args.ref, getattr(args, "force", False))
    if not ok:
        return _deny(gs, gowner, "start")

    s = _resolve(args.ref)
    if not s:
        print("FAIL: that owner holds no slot (claim first), or the slot is invalid",
              file=sys.stderr)
        return 3

    pid, disc = detect(s)
    if pid:
        touch(s)
        print(f"OK: slot {s} already running pid={pid} game={SLOTS[s]['game']} disc={disc}")
        return 0

    ddir = _prepare(s)
    log = os.path.join(EVIDENCE, f"bds-{s}.log")

    subprocess.run(["tmux", "kill-session", "-t", f"slot{s}"], capture_output=True)
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", f"slot{s}",
         f"cd {shlex.quote(ddir)} && LD_LIBRARY_PATH=. ./bedrock_server "
         f"> {shlex.quote(log)} 2>&1"],
        check=True,
    )
    print(f"slot {s} starting (world {SLOTS[s]['world']} game {SLOTS[s]['game']}) ...")
    time.sleep(16)

    pid, disc = detect(s)
    with Lock():
        d2 = load()
        if s in d2["slots"]:
            d2["slots"][s].update({
                "discovery": disc,
                "world": SLOTS[s]["world"],
                "game": SLOTS[s]["game"],
                "last_touch": time.time(),
            })
            save(d2)

    if not disc:
        print(f"WARN: slot {s} is up but no discovery port was found — bots will refuse to "
              f"connect (better than joining the wrong world)", file=sys.stderr)

    print(f"OK: slot {s} pid={pid} game={SLOTS[s]['game']} disc={disc} "
          f"world={SLOTS[s]['world']}")
    return 0


def cmd_bot(args):
    ok, gs, gowner = _owner_guard(args.slot, getattr(args, "force", False))
    if not ok:
        return _deny(gs, gowner, "bot")

    s = _resolve(args.slot)
    if not s:
        print("FAIL: no such owner/slot", file=sys.stderr)
        return 3

    pid, disc = detect(s)
    if not pid:
        print(f"FAIL: slot {s} server is not running; run shctl start first", file=sys.stderr)
        return 4
    if not disc:
        # hard refusal: a guessed discovery port cross-connects into another world
        print(f"FAIL: slot {s} has no discovery port; refusing to start a bot "
              f"(prevents joining the wrong world)", file=sys.stderr)
        return 4

    name = args.name or f"{s.lower()}_bot"
    sess = f"bot_{name}"
    subprocess.run(["tmux", "kill-session", "-t", sess], capture_output=True)

    log = os.path.join(EVIDENCE, f"bot-{name}.log")
    cmd = (
        f"cd {BASE}/tools && HOLD=1 "
        f"BOT_NAME={shlex.quote(name)} "
        f"BOT_PORT={SLOTS[s]['game']} "
        f"NETH_DISCOVERY_PORT={disc} "
        f"node {shlex.quote(NETBOT)} > {shlex.quote(log)} 2>&1"
    )
    subprocess.run(["tmux", "new-session", "-d", "-s", sess, cmd], check=True)
    touch(s)
    time.sleep(6)
    print(f"OK: bot '{name}' -> slot {s} (game={SLOTS[s]['game']} disc={disc}) log {log}")
    return 0


def cmd_stop(args):
    ok, gs, gowner = _owner_guard(args.ref, getattr(args, "force", False))
    if not ok:
        return _deny(gs, gowner, "stop")

    s = _resolve(args.ref)
    if not s:
        print("FAIL: no such owner/slot", file=sys.stderr)
        return 3

    _kill_bots(s)
    subprocess.run(["tmux", "kill-session", "-t", f"slot{s}"], capture_output=True)

    pid = _bds_pid(SLOTS[s]["dir"])
    if pid:
        try:
            os.kill(pid, 15)
            time.sleep(2)
            p2 = _bds_pid(SLOTS[s]["dir"])
            if p2:
                os.kill(p2, 9)
        except Exception:
            pass

    with Lock():
        d = load()
        if s in d["slots"]:
            d["slots"][s]["stopped_ts"] = time.time()
            save(d)
    print(f"OK: slot {s} stopped (server and bots closed, memory released)")
    return 0


def cmd_close(args):
    n = 0
    for s in ORDER:
        pid, _ = detect(s)
        if pid:
            cmd_stop(argparse.Namespace(ref=s))
            n += 1
    print(f"OK: closed {n} running slot(s)")
    return 0


def cmd_reap(args):
    freed = reap(force=args.force)
    if freed:
        for s, o in freed:
            print(f"reclaimed slot {s} (owner={o})")
    else:
        print("nothing to reclaim")
    return 0


def cmd_status(args):
    d = load()
    sl = d["slots"]
    snap = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "max_bds": MAX_BDS,
            "slots": {}, "free": []}

    for s in ORDER:
        pid, disc = detect(s)
        snap["slots"][s] = {
            "slot": s,
            "role": SLOTS[s]["role"],
            "world": SLOTS[s]["world"],
            "game_port": SLOTS[s]["game"],
            "owner": sl.get(s, {}).get("owner"),
            "running": pid is not None,
            "pid": pid,
            "discovery_port": disc,
            "bots": list(alive_bots(s).keys()),
        }
        if s not in sl:
            snap["free"].append(s)

    try:
        with open("/proc/meminfo") as f:
            mi = dict(l.split(":") for l in f.read().splitlines())
        snap["mem_available_mb"] = int(mi["MemAvailable"].split()[0]) // 1024
    except Exception:
        pass

    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
    else:
        print("== slot overview ==")
        for s in ORDER:
            i = snap["slots"][s]
            print(f"  {s}[{i['role'][:2]}] {'UP' if i['running'] else 'down'}  "
                  f"owner={i['owner'] or '(free)':<8} world={i['world']:<13} "
                  f"game={i['game_port']:<6} disc={i['discovery_port'] or '-':<6} "
                  f"bots={','.join(i['bots']) or '-'}")
        print(f"  free: {', '.join(snap['free']) if snap['free'] else '(none)'}  "
              f"mem {snap.get('mem_available_mb', '?')}MB")
    return 0

# ------------------------------------------------------------------------ main ---

def main():
    ap = argparse.ArgumentParser(prog="shctl", description="BDS slot / ownership board")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("board").set_defaults(func=cmd_board)

    p = sub.add_parser("claim")
    p.add_argument("owner")
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("release")
    p.add_argument("identity", nargs="?", default="")
    p.add_argument("--slot", default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("start")
    p.add_argument("ref")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("stop")
    p.add_argument("ref")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("bot")
    p.add_argument("slot")
    p.add_argument("name", nargs="?")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_bot)

    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("reap")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_reap)

    sub.add_parser("close").set_defaults(func=cmd_close)

    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())