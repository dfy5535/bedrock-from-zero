#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcreg — BDS 世界注册表 + 无头 Bot 注册表（游戏服 <BDS_HOST>）
AUTHOR @ Bedrock Flow Lab

回答：
  • 哪个世界正在运行？      → world / status
  • 现在有几个无头 Bot？     → bot / status
  • 每个 Bot 在哪个端口/tmux？→ bot / status
  • DSH 要一份完整快照       → snapshot（JSON）

世界锁对齐旧广州版：/opt/bedrock-flow/state/world.lock
Bot 事实来源：真实进程 + tmux + 端口探测（不靠自报）
"""
import os, sys, json, time, fcntl, subprocess, argparse

STATE_DIR  = "/opt/bedrock-flow/state"
WORLD_LOCK = os.path.join(STATE_DIR, "world.lock")
WORLD_LOCK_GUARD = os.path.join(STATE_DIR, "world.lock.guard")
BOT_FILE   = os.path.join(STATE_DIR, "bots.json")
TOOLS      = "/opt/bedrock-flow/tools"
EVID       = "/opt/bedrock-flow/lab/evidence"

# Bot 槽位 → 端口（对齐 mcctl.sh 的 BOT_SLOTS）
BOT_SLOTS = {
    "bot1": {"port": 20031, "session": "bot_bot1", "log": f"{EVID}/bot1.log"},
    "bot2": {"port": 20032, "session": "bot_bot2", "log": f"{EVID}/bot2.log"},
}


def _ensure():
    os.makedirs(STATE_DIR, exist_ok=True)


class WorldGuard:
    def __enter__(self):
        _ensure()
        self.fh = open(WORLD_LOCK_GUARD, "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self
    def __exit__(self, *a):
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN); self.fh.close()
        except Exception:
            pass


def read_world_lock():
    if not os.path.exists(WORLD_LOCK):
        return None
    try:
        with open(WORLD_LOCK) as f:
            return json.load(f)
    except Exception:
        return {"raw": "unreadable"}


def write_world_lock(install, world, server_name="", port=None, pid=None):
    _ensure()
    d = {
        "install": install, "world": world, "server_name": server_name,
        "port": port, "pid": pid or 0,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": int(time.time()),
    }
    with open(WORLD_LOCK, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    return d


def clear_world_lock():
    try:
        os.remove(WORLD_LOCK)
        return True
    except FileNotFoundError:
        return False


def running_bds():
    out = []
    try:
        ps = subprocess.run(["pgrep", "-x", "bedrock_server"], capture_output=True, text=True, timeout=8).stdout
        pids = [int(x) for x in ps.split() if x.isdigit()]
    except Exception:
        return out
    for pid in pids:
        install = ""
        try:
            install = os.readlink(f"/proc/{pid}/cwd")
        except Exception:
            pass
        info = {"pid": pid, "install": install, "world": "", "port": None, "server_name": ""}
        sp = os.path.join(install, "server.properties") if install else ""
        if sp and os.path.exists(sp):
            try:
                with open(sp) as f:
                    for l in f:
                        l = l.strip()
                        if l.startswith("level-name="):
                            info["world"] = l.split("=", 1)[1]
                        elif l.startswith("server-port="):
                            try: info["port"] = int(l.split("=", 1)[1])
                            except Exception: pass
                        elif l.startswith("server-name="):
                            info["server_name"] = l.split("=", 1)[1]
            except Exception:
                pass
        out.append(info)
    return out


def tmux_sessions():
    try:
        o = subprocess.run(["tmux", "ls"], capture_output=True, text=True, timeout=8)
        if o.returncode != 0:
            return []
        return [l.split(":", 1)[0] for l in o.stdout.splitlines() if ":" in l]
    except Exception:
        return []


def bot_procs():
    try:
        ps = subprocess.run(["pgrep", "-f", "bf-netbot"], capture_output=True, text=True, timeout=8).stdout
        return [int(x) for x in ps.split() if x.isdigit()]
    except Exception:
        return []


def _scan_running_bots():
    """动态发现真实在跑的 bf-netbot：以 /proc 为准，不依赖 tmux 会话名。"""
    found = {}
    try:
        ps = subprocess.run(["pgrep", "-f", "bf-netbot"], capture_output=True, text=True, timeout=8).stdout
        pids = [int(x) for x in ps.split() if x.isdigit()]
    except Exception:
        pids = []
    for pid in pids:
        try:
            comm = open("/proc/%d/comm" % pid).read().strip()
        except Exception:
            continue
        if comm != "node":
            continue
        try:
            cmd = open("/proc/%d/cmdline" % pid, "rb").read().decode("utf-8", "replace")
        except Exception:
            cmd = ""
        if "bf-netbot" not in cmd:
            continue
        env = {}
        try:
            raw = open("/proc/%d/environ" % pid, "rb").read().decode("utf-8", "replace")
            for item in raw.split("\0"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    env[k] = v
        except Exception:
            pass
        port = env.get("BOT_PORT", "")
        disc = env.get("NETH_DISCOVERY_PORT", "")
        found[pid] = {
            "pid": pid,
            "name": env.get("BOT_NAME") or ("pid%d" % pid),
            "port": int(port) if port.isdigit() else None,
            "discovery_port": int(disc) if disc.isdigit() else None,
            "hold": env.get("HOLD", "") == "1",
        }
    return found


def bot_facts():
    sessions = set(tmux_sessions())
    procs = bot_procs()
    facts = {}
    for name, meta in BOT_SLOTS.items():
        running = meta["session"] in sessions
        facts[name] = {
            "name": name, "port": meta["port"], "tmux_session": meta["session"],
            "log": meta["log"], "running": running,
            "log_size": os.path.getsize(meta["log"]) if os.path.exists(meta["log"]) else 0,
            "last_line": _last_line(meta["log"]),
        }
    for pid, info in _scan_running_bots().items():
        nm = info["name"]
        key = nm if nm not in facts else ("%s#%d" % (nm, pid))
        facts[key] = {
            "name": nm, "port": info["port"], "tmux_session": nm,
            "log": "", "running": True, "log_size": 0, "last_line": "",
            "pid": pid, "discovery_port": info["discovery_port"],
            "dynamic": True,
        }
    return facts, len(procs), procs


def _last_line(path):
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END); size = f.tell()
            block = min(4096, size); f.seek(size - block)
            data = f.read().decode("utf-8", "replace")
        lines = [l for l in data.splitlines() if l.strip()]
        return lines[-1] if lines else ""
    except Exception:
        return ""


def cmd_world(args):
    live = running_bds()
    lock = read_world_lock()
    if args.set:
        install, world = args.set
        with WorldGuard():
            cur = read_world_lock()
            if cur and cur.get("world") and cur.get("world") != world and not args.force:
                print(f"FAIL: 世界锁已被 {cur.get('world')} 占用（install={cur.get('install')}）。"
                      f"同一时刻只允许一个世界。加 --force 强制覆盖。", file=sys.stderr)
                return 2
            d = write_world_lock(install, world)
        print(json.dumps({"ok": True, "world_lock": d}, ensure_ascii=False, indent=2) if args.json
              else f"OK: 世界锁 = {world} @ {install}")
        return 0
    if args.clear:
        with WorldGuard():
            ok = clear_world_lock()
        print("OK: 世界锁已清除" if ok else "世界锁本就为空")
        return 0
    snap = {"world_lock": lock, "running_worlds": live,
            "only_one": len(live) <= 1}
    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2)); return 0
    print("== mcreg world · 世界注册表 ==")
    if lock:
        print(f"  世界锁: {lock.get('world')}  @ {lock.get('install')}  since {lock.get('ts')}")
    else:
        print("  世界锁: (未占用)")
    if live:
        for w in live:
            print(f"  运行中: pid={w['pid']} world={w['world'] or '?'} port={w['port']} "
                  f"install={w['install']}  name={w['server_name']}")
    else:
        print("  运行中: (无 BDS 进程)")
    return 0


def cmd_bot(args):
    facts, nproc, procs = bot_facts()
    active = [n for n, f in facts.items() if f["running"]]
    snap = {"declared_slots": list(BOT_SLOTS.keys()), "slots": facts,
            "active_bots": active, "count": len(active), "netbot_procs": nproc, "pids": procs}
    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2)); return 0
    print("== mcreg bot · 无头 Bot 注册表 ==")
    for n, f in facts.items():
        mark = "🟢 运行中" if f["running"] else "⚪ 未运行"
        print(f"  {n:<6} {mark}  端口={f['port']}  tmux={f['tmux_session']}  日志={f['log_size']}B")
        if f["last_line"]:
            print(f"          └ 最新: {f['last_line'][:90]}")
    print(f"\n  活跃 Bot 数: {len(active)}  | netbot 进程: {nproc}")
    return 0


def cmd_snapshot(args):
    live_worlds = running_bds()
    lock = read_world_lock()
    facts, nproc, procs = bot_facts()
    active = [n for n, f in facts.items() if f["running"]]
    try:
        pout = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "portctl.py"),
                               "status"], capture_output=True, text=True, timeout=15).stdout
        ports = json.loads(pout) if pout.strip() else {}
    except Exception:
        ports = {}
    snap = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": os.uname().nodename,
        "world": {"lock": lock, "running": live_worlds, "only_one": len(live_worlds) <= 1},
        "bots": {"active": active, "count": len(active), "slots": facts, "netbot_procs": nproc},
        "ports": {"reserved": ports.get("reserved"), "segments": ports.get("segments"),
                  "leases": ports.get("leases"), "free": ports.get("free"),
                  "listening": ports.get("listening"), "orphans": ports.get("orphans")},
        "healthy": (len(live_worlds) <= 1),
    }
    print(json.dumps(snap, ensure_ascii=False, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(prog="mcreg", description="BDS 世界 + 无头 Bot 注册表")
    sub = ap.add_subparsers(dest="cmd")

    sp = sub.add_parser("world"); sp.add_argument("--json", action="store_true")
    sp.add_argument("--set", nargs=2, metavar=("INSTALL", "WORLD"))
    sp.add_argument("--clear", action="store_true"); sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_world)

    sp = sub.add_parser("bot"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_bot)

    sp = sub.add_parser("snapshot"); sp.add_argument("--json", action="store_true", default=True)
    sp.set_defaults(func=cmd_snapshot)

    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        ap.print_help(); return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())