#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sh-guard — 上海 BDS 空闲守卫 + 僵尸号牌回收  v2
AUTHOR @ Bedrock Flow Lab

两条规则：
  【空闲停服】某槽满足全部条件并持续 ≥ IDLE_MIN(30) 分钟 → 自动停服（还内存）：
      ① 没有 Bot 在线；② 游戏口没有已建立连接；③ 距上次指令(last_touch) ≥ 30 分钟。
      —— 即「30 分钟没有任何指令」就停。
  【僵尸回收】某槽已被 claim 但一直没在跑，且距 last_touch ≥ REAP_MIN(60) 分钟
      → 释放号牌（防止员工中途跑了却永久占位 → 别人分不到槽）。

由 systemd timer 每 5 分钟拉起一次。
"""
import os, sys, time, subprocess, json

BASE = "/opt/bedrock-flow"
STATE = os.path.join(BASE, "state")
IDLE_FILE = os.path.join(STATE, "idle.json")
SLOTS_FILE = os.path.join(STATE, "sh_slots.json")
IDLE_MIN = 30
REAP_MIN = 60
SHCTL = os.path.join(BASE, "tools", "shctl.py")
PORTS = {"A": 20031, "B": 20041, "C": 20051}


def running_slots():
    dirs = {s: os.path.join(BASE, "slots", s) for s in PORTS}
    found = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
            rss = 0
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss = int(line.split()[1]); break
            if rss < 50000:
                continue
            for s, d in dirs.items():
                if cwd == d:
                    found[s] = pid
        except Exception:
            pass
    return found


def has_bot(gp):
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/cmdline", "rb") as f:
                if b"bf-netbot.js" not in f.read():
                    continue
            with open(f"/proc/{name}/environ", "rb") as f:
                env = dict(kv.split(b"=", 1) for kv in f.read().split(b"\x00") if b"=" in kv)
            if env.get(b"BOT_PORT", b"").decode() == str(gp):
                return True
        except Exception:
            pass
    return False


def has_conn(gp):
    try:
        out = subprocess.run(["ss", "-tn"], capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return False
    return any("ESTAB" in l and f":{gp}" in l for l in out.splitlines())


def load_slots():
    try:
        return json.load(open(SLOTS_FILE)).get("slots", {})
    except Exception:
        return {}


def main():
    os.makedirs(STATE, exist_ok=True)
    try:
        idle = json.load(open(IDLE_FILE))
    except Exception:
        idle = {}
    now = time.time()
    run = running_slots()
    claims = load_slots()

    # ① 空闲停服
    for s, gp in PORTS.items():
        if s not in run:
            idle.pop(s, None)
            continue
        touch = claims.get(s, {}).get("last_touch", 0)
        fresh = (now - touch) < IDLE_MIN * 60 if touch else False
        if has_bot(gp) or has_conn(gp) or fresh:
            idle.pop(s, None)
            continue
        idle.setdefault(s, now)
        mins = (now - idle[s]) / 60.0
        if mins >= IDLE_MIN:
            print(f"[guard] 槽{s} 无指令且空闲 {mins:.0f} 分钟 → 自动停服")
            subprocess.run([sys.executable, SHCTL, "stop", s])
            idle.pop(s, None)
        else:
            print(f"[guard] 槽{s} 空闲 {mins:.0f}/{IDLE_MIN} 分钟")
    json.dump(idle, open(IDLE_FILE, "w"))

    # ② 僵尸号牌回收
    freed = []
    for s, i in list(claims.items()):
        if s in run:
            continue
        ts = i.get("last_touch") or i.get("claimed_ts") or now
        if (now - ts) / 60.0 >= REAP_MIN:
            freed.append((s, i.get("owner")))
    if freed:
        subprocess.run([sys.executable, SHCTL, "reap"])
        for s, o in freed:
            print(f"[guard] 回收僵尸号牌 槽{s}（负责人={o}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())