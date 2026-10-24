#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portctl — BDS 端口租约与段隔离（游戏服 <BDS_HOST> 重建版）
AUTHOR @ Bedrock Flow Lab

回答三个问题：
  1. 哪个端口被占用？   → list / doctor
  2. 哪个端口没被占用？ → list 的空闲段 / claim auto
  3. 谁（身份）在用？   → claim 时登记 identity/install/world

机制（对齐旧广州版五道防线）：
  ① 段隔离     SEGMENTS 多段，区间真正不重叠，reserved 不入段
  ② 端口租约   flock 原子写 ports.json，冲突响亮报错，绝不静默抢绑
  ③ 不退让     claim auto 只在本身份段内找空位
  ④ 暗门已封   enable-lan-visibility=false（doctor 会检查）
  ⑤ 对账       doctor 把「有监听无租约」报为野进程
"""
import os, sys, json, time, fcntl, subprocess, argparse

STATE_DIR  = "/opt/bedrock-flow/state"
PORTS_FILE = os.path.join(STATE_DIR, "ports.json")
LOCK_FILE  = os.path.join(STATE_DIR, "ports.lock")

# 端口段（业务端口 20031-20059 内划段；20031/20032 保留给主 BDS）
SEGMENTS = {
    "bf":   [(20033, 20040)],
    "dsh":    [(20041, 20048)],
    "shared": [(20049, 20049)],
    "lab":    [(20050, 20059)],
}
RESERVED = {20031, 20032}
PORT_LO, PORT_HI = 20031, 20059
GRACE = 90  # 秒：刚 claim 但 BDS 还没绑定的宽限期


# ---------- 段工具 ----------
def seg_ports(ident):
    out = []
    for lo, hi in SEGMENTS.get(ident, []):
        out.extend(range(lo, hi + 1))
    return out

def seg_str(ident):
    return ", ".join(f"{lo}-{hi}" for lo, hi in SEGMENTS.get(ident, []))

def in_segment(ident, port):
    return port in seg_ports(ident)

def verify_segments():
    errors = []
    seen = {}
    for ident, segs in SEGMENTS.items():
        for lo, hi in segs:
            if lo > hi or lo < PORT_LO or hi > PORT_HI:
                errors.append(f"区间非法: {ident} {lo}-{hi}")
            for p in range(lo, hi + 1):
                if p in seen:
                    errors.append(f"重叠: {p} 同时属于 {seen[p]} 与 {ident}")
                seen[p] = ident
                if p in RESERVED:
                    errors.append(f"reserved {p} 落入 {ident} 段内")
    return errors


# ---------- 状态读写 ----------
def _ensure():
    os.makedirs(STATE_DIR, exist_ok=True)

def load_ports():
    _ensure()
    if not os.path.exists(PORTS_FILE):
        return {"leases": {}}
    try:
        with open(PORTS_FILE) as f:
            d = json.load(f)
        d.setdefault("leases", {})
        return d
    except Exception:
        return {"leases": {}}

def save_ports(d):
    _ensure()
    tmp = PORTS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PORTS_FILE)

class Lock:
    def __enter__(self):
        _ensure()
        self.fh = open(LOCK_FILE, "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self
    def __exit__(self, *a):
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
            self.fh.close()
        except Exception:
            pass


# ---------- 实际监听 ----------
def actual_listeners():
    """返回 {port: {"proto":..., "proc":...}}，只统计我们关心的段内端口 + reserved"""
    res = {}
    for proto, flag in (("udp", "-lunp"), ("tcp", "-ltnp")):
        try:
            out = subprocess.run(["ss", flag], capture_output=True, text=True, timeout=8).stdout
        except Exception:
            continue
        for line in out.splitlines()[1:]:
            cols = line.split()
            if len(cols) < 5:
                continue
            local = cols[3]
            port = local.rsplit(":", 1)[-1]
            try:
                port = int(port)
            except ValueError:
                continue
            if not (PORT_LO <= port <= PORT_HI or port in (19132, 19133)):
                continue
            proc = ""
            if "users:" in line:
                proc = line.split("users:", 1)[1].strip().strip('"')
            key = port
            # TCP/UDP 同号并存时都记录
            if key in res and res[key]["proto"] != proto:
                res[key]["proto"] = "tcp+udp"
            else:
                res[key] = {"proto": proto, "proc": proc}
    return res


# ---------- 外部署名（与上海号牌系统 shctl 跨系统对账）----------
SH_SLOTS = os.path.join(STATE_DIR, "sh_slots.json")


def external_leases():
    """号牌系统(shctl)当前在跑/持有的槽位端口，视为已署名。
    只读、无副作用；文件不存在返回 {}（美国机/无号牌机优雅降级）。"""
    if not os.path.exists(SH_SLOTS):
        return {}
    try:
        with open(SH_SLOTS) as f:
            d = json.load(f)
    except Exception:
        return {}
    out = {}
    for slot, info in (d.get("slots") or {}).items():
        if not isinstance(info, dict):
            continue
        port = info.get("game")
        try:
            port = int(port)
        except (TypeError, ValueError):
            continue
        out[port] = {"system": "shctl", "slot": slot,
                     "owner": info.get("owner"), "world": info.get("world")}
    return out


def pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


# ---------- 命令 ----------
def cmd_verify(args):
    errors = verify_segments()
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors,
                          "segments": {k: seg_str(k) for k in SEGMENTS},
                          "reserved": sorted(RESERVED)}, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    print("== portctl verify · 段定义自检 ==")
    for ident in SEGMENTS:
        ps = seg_ports(ident)
        print(f"  {ident:<8} {seg_str(ident):<24} ({len(ps)} 个端口)")
    print(f"  reserved {min(RESERVED)}-{max(RESERVED)}")
    if errors:
        print("\n  ❌ 发现错误:")
        for e in errors:
            print("    -", e)
        return 1
    print("  ✅ 段之间无重叠、reserved 未落入任何段、区间合法")
    return 0


def cmd_claim(args):
    ident, port = args.identity, args.port
    with Lock():
        d = load_ports()
        leases = d["leases"]
        if port == "auto":
            taken = set(int(p) for p in leases)
            for p in seg_ports(ident):
                if p not in taken:
                    port = p
                    break
            if port == "auto":
                print(f"FAIL: 身份 {ident} 的段 {seg_str(ident)} 已无空位", file=sys.stderr)
                return 6
            port = int(port)
        else:
            try:
                port = int(port)
            except ValueError:
                print("FAIL: 端口必须是整数或 auto", file=sys.stderr)
                return 2
        if port in RESERVED:
            print(f"FAIL: 端口 {port} 是保留端口（主测试服），不允许租用", file=sys.stderr)
            return 4
        if not in_segment(ident, port):
            print(f"FAIL: 端口 {port} 不在身份 {ident} 的段 {seg_str(ident)} 内（拒绝跨段租用）", file=sys.stderr)
            return 7
        if str(port) in leases:
            L = leases[str(port)]
            print(f"FAIL: 端口 {port} 已被租用 → identity={L.get('identity')} "
                  f"install={L.get('install')} world={L.get('world')} since={L.get('ts')}", file=sys.stderr)
            return 3
        leases[str(port)] = {
            "identity": ident,
            "install": args.install or "",
            "world": args.world or "",
            "pid": args.pid or 0,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "epoch": int(time.time()),
        }
        save_ports(d)
        if args.json:
            print(json.dumps({"ok": True, "port": port, "lease": leases[str(port)]}, ensure_ascii=False))
        else:
            print(f"OK: {ident} 已租用端口 {port}")
        return 0


def cmd_release(args):
    port = int(args.port)
    with Lock():
        d = load_ports()
        leases = d["leases"]
        key = str(port)
        if key not in leases:
            print(f"FAIL: 端口 {port} 没有租约", file=sys.stderr)
            return 5
        L = leases[key]
        live = actual_listeners()
        if port in live and not args.force:
            print(f"FAIL: 端口 {port} 正被实际监听（BDS 在跑），拒绝释放以免误删活租约。", file=sys.stderr)
            print(f"      占用: identity={L.get('identity')} install={L.get('install')} "
                  f"world={L.get('world')}  (加 --force 强制)", file=sys.stderr)
            return 8
        del leases[key]
        save_ports(d)
        print(f"OK: 已释放端口 {port}")
        return 0


def cmd_list(args):
    d = load_ports()
    leases = d["leases"]
    live = actual_listeners()
    ext = external_leases()
    if args.json:
        free = {i: [p for p in seg_ports(i) if str(p) not in leases] for i in SEGMENTS}
        print(json.dumps({"leases": leases, "listeners": live, "free": free,
                          "segments": {k: seg_str(k) for k in SEGMENTS}}, ensure_ascii=False, indent=2))
        return 0
    print("== portctl list · 租约 + 机器实况 ==")
    if not leases:
        print("  (无租约)")
    for p, L in sorted(leases.items(), key=lambda x: int(x[0])):
        mark = "●LIVE" if int(p) in live else "  idle"
        print(f"  {mark} :{p}  identity={L.get('identity')} install={L.get('install')} "
              f"world={L.get('world')} since={L.get('ts')}")
    print("\n  -- 段空闲情况 --")
    for ident in SEGMENTS:
        used = [p for p in seg_ports(ident) if str(p) in leases or p in ext]
        free = [p for p in seg_ports(ident) if str(p) not in leases and p not in ext]
        print(f"  {ident:<8} 已用={used or '无'}  空闲={free or '无'}")
    if ext:
        print("\n  -- 号牌系统署名（shctl）--")
        for p, v in sorted(ext.items()):
            mark = "●LIVE" if int(p) in live else "  idle"
            print(f"  {mark} :{p}  slot={v['slot']} owner={v['owner']} world={v['world']}")
    print(f"  reserved {sorted(RESERVED)} (主测试服)")
    return 0


def cmd_doctor(args):
    d = load_ports()
    leases = d["leases"]
    live = actual_listeners()
    errors = verify_segments()
    # 野进程：有监听但无租约
    ext = external_leases()
    orphans = [p for p in live if str(p) not in leases and p not in RESERVED
               and p not in ext]
    # 僵尸租约：有租约但既不监听、pid 也不活
    stale = []
    now = int(time.time())
    for p, L in leases.items():
        pi = int(p)
        if pi in live:
            continue
        if pid_alive(L.get("pid")) and (now - L.get("epoch", 0)) < GRACE:
            continue
        if not pid_alive(L.get("pid")) and (now - L.get("epoch", 0)) > GRACE:
            stale.append(p)
    # 暗门检查：本版 BDS(1.26.51 nethernet) 不依赖也不偷绑 19132，
    # 但 19132 若真被监听则说明有别的 BDS 抢占了标准端口 —— 那才是问题。
    lan_danger = []
    lans = [p for p in live.keys() if p in (19132, 19133)]
    if lans:
        lan_danger = lans
    ok = not errors and not orphans and not stale and not lan_danger
    if args.json:
        print(json.dumps({"ok": ok, "seg_errors": errors, "orphans": orphans,
                          "stale_leases": stale, "external_leases": ext,
                          "lan_visibility_danger": lan_danger,
                          "listeners": live, "leases": leases}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    print("== portctl doctor · 对账 ==")
    print(f"  段自检      : {'✅ 通过' if not errors else '❌ ' + str(errors)}")
    print(f"  野进程      : {orphans if orphans else '✅ 无（所有监听都有租约）'}")
    print(f"  僵尸租约    : {stale if stale else '✅ 无'}")
    if ext:
        print(f"  号牌署名    : " + ", ".join(f":{p} slot={v['slot']}/{v['owner']}" for p, v in sorted(ext.items())))
    else:
        print("  号牌署名    : (无号牌系统或全部空闲)")
    print(f"  19132占用  : {'⚠️ ' + str(lan_danger) if lan_danger else '✅ 无（标准端口未被抢占）'}")
    print(f"\n  判定: {'✅ 健康' if ok else '⚠️ 需处理'}")
    return 0 if ok else 1


def cmd_status(args):
    d = load_ports()
    leases = d["leases"]
    live = actual_listeners()
    free = {}
    for i in SEGMENTS:
        free[i] = [p for p in seg_ports(i) if str(p) not in leases]
    snap = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "segments": {k: seg_str(k) for k in SEGMENTS},
        "reserved": sorted(RESERVED),
        "leases": leases,
        "free": free,
        "listening": live,
        "external": external_leases(),
        "orphans": [p for p in live if str(p) not in leases and p not in RESERVED
                    and p not in external_leases()],
        "healthy": not verify_segments(),
    }
    print(json.dumps(snap, ensure_ascii=False, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(prog="portctl", description="BDS 端口租约与段隔离")
    sub = ap.add_subparsers(dest="cmd")

    for name, fn in (("verify", cmd_verify), ("list", cmd_list), ("doctor", cmd_doctor), ("status", cmd_status)):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)

    sp = sub.add_parser("claim")
    sp.add_argument("identity", choices=list(SEGMENTS.keys()))
    sp.add_argument("port")                       # 端口号或 auto
    sp.add_argument("install", nargs="?", default="")
    sp.add_argument("world", nargs="?", default="")
    sp.add_argument("--pid", type=int, default=0)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_claim)

    sp = sub.add_parser("release")
    sp.add_argument("port")
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_release)

    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
