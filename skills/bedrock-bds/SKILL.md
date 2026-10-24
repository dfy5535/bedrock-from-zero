---
name: bedrock-bds
description: 广州 BDS 实验场的安装、起停、世界管理、控制台与日志取证流程（任务书 §16 §17 §18 §19 §20）。当需要启动/停止/重启 BDS、切换或重置测试世界、查看运行日志、向服务器发控制台命令、或安装新版本 BDS 时使用。
whenToUse: 用户说「起服务器/停服务器」「跑一下 BDS」「看日志」「换测试世界」「装个新版本 BDS」，或 bedrock-test 需要 B 层运行时环境时。
---

# bedrock-bds — BDS 运行时生命周期

本技能**只定义操作流程与安全边界**。BDS 的配置项、控制台命令语法以**目标版本实测**为准，不得凭记忆写。

## 0. 现状事实（只读引用）

| 项 | 值 |
|---|---|
| 工程根 | `/opt/bedrock-flow/`（广州，`ssh gz` 免密） |
| BDS 安装根 | `/opt/bedrock-flow/bds/`（含版本目录与 `current` 软链） |
| 运行用户 | `bedrock`（uid999，**无 sudo**） |
| Runner 脚本 | `/opt/bedrock-flow/tools/bds/bds.sh`，软链 `/usr/local/bin/bedrock-flow` |
| tmux 会话名 | `bedrock-flow`；socket `/opt/bedrock-flow/lab/tmux-bds.sock` |
| 世界目录 | `/opt/bedrock-flow/test-worlds/`（`worlds/` 为其软链，**绝不使用用户世界**） |
| 日志 | `/opt/bedrock-flow/logs/` |
| 资源状态 | `registry/tools.json` → `resource_status = BELOW_OFFICIAL_RAM_TARGET`（实测 RAM 3723 MiB；官方页面列 4 GB 档位） |
| BDS 实测内存 | RSS 约 333.8 MiB（view-distance=6, tick-distance=4, max-players=2, creative, peaceful） |

## 1. 什么时候使用

- 需要启动/停止/重启/查询 BDS 状态。
- 需要切换、重置、列举测试世界。
- 需要看日志、向服务器发控制台命令。
- 需要安装新版本 BDS（zip 已在手）。
- `bedrock-test` 要跑 B 层运行时测试。
- 需要排查 BDS 启动失败、OOM、端口异常。

**不适用**：addon 静态校验（`bedrock-build`）；测试判定与报告（`bedrock-test`）。

## 2. 检查顺序

1. **读现状**：`bedrock-flow status`、`bedrock-flow versions`、`ls -l /opt/bedrock-flow/bds/current`。
2. **确认目标版本**：与 `registry/runtime.json` 一致；不一致 → 转 `bedrock-version`。
3. **确认资源**：`free -m`；若可用内存过低，**先降配置**（view-distance / tick-distance / max-players），**不允许**用"继续加 swap"假装解决（§3 第 6 条）。
4. **确认世界**：只使用 `/opt/bedrock-flow/test-worlds/` 下的世界；需要干净环境时 `reset-world`。
5. **起服**：`bedrock-flow start`。
6. **取证启动成功**：从日志中读到版本自报行（`Version:` / build ID / commit）与"服务器已启动/接受连接"类证据；**不得只看进程存在**。
7. **执行控制台操作**：`bedrock-flow console "<命令>"`（命令语法须按目标版本确认）。
8. **收集日志**：`bedrock-flow log <n>`；运行时测试证据由 `bedrock-test` 提取。
9. **停服**：`bedrock-flow stop`（测试完成后默认停服，避免长期占用资源）。
10. **记录**：把版本自报、启动耗时、RSS 峰值、异常行写入项目报告。

## 3. 工具调用顺序

```bash
# 状态与版本
ssh gz "bedrock-flow status"
ssh gz "bedrock-flow versions"
ssh gz "ls -l /opt/bedrock-flow/bds/current"

# 资源（起服前）
ssh gz "free -m; df -h /"

# 世界
ssh gz "bedrock-flow worlds"
ssh gz "bedrock-flow reset-world <名>"
ssh gz "bedrock-flow set-world <名>"

# 起服 / 配置 / 重启
ssh gz "bedrock-flow configure"
ssh gz "bedrock-flow start"
ssh gz "bedrock-flow restart"

# 取证
ssh gz "bedrock-flow log 80"
ssh gz "bedrock-flow console \"<目标版本支持的服务器命令>\""

# 停服
ssh gz "bedrock-flow stop"
```

**Runner 已实测可用的子命令**：`install | configure | start | stop | restart | status | console | log | set-world | reset-world | worlds | versions`。

统一 CLI 等价形式（若已实现）：`bedrock-flow bds install|start|stop`。若不存在，使用 `bedrock-flow`，**不得发明子命令**。

## 4. 禁止做什么

1. **禁止修改 BDS 二进制**或 vanilla 核心包（铁律第 10 条 / §14）。
2. **禁止使用用户世界**作为测试世界（铁律第 7 条）；只允许 `/opt/bedrock-flow/test-worlds/`。
3. **禁止以 root 长期运行 BDS**（§16 第 9 条）；必须用 `bedrock` 用户。
4. 禁止用"继续加 swap"掩盖内存不足（§3 第 6 条）。
5. 禁止只看进程存在/端口监听就宣布启动成功；必须有日志自报版本证据。
6. 禁止手工删除不明目录或世界目录（先隔离，后处理）。
7. 禁止触碰广州上与本任务无关的服务（如其他端口的业务服务）。
8. 禁止在日志/报告中回显凭据（如 `/etc/gost.env` 内容）。
9. 禁止为了"让测试通过"而修改服务器行为、放宽测试条件或伪造日志。
10. 禁止把 BDS 启动成功等同于 Addon 正确（§1 第 7 条）。

## 5. 输出格式

项目报告 `projects/<id>/reports/runtime-<timestamp>.json`：

```json
{
  "project": "<id>",
  "bds": {
    "version_self_reported": "<日志中的 Version 行>",
    "build_id": "<日志中的 build id>",
    "commit": "<日志中的 commit>",
    "install_path": "/opt/bedrock-flow/bds/<版本>",
    "run_as_user": "bedrock"
  },
  "world": { "name": "<测试世界名>", "path": "/opt/bedrock-flow/test-worlds/<名>", "reset": true },
  "config": { "view_distance": null, "tick_distance": null, "max_players": null },
  "startup": { "started_at": "<ISO8601>", "ready_evidence": "<日志原文行>" },
  "resources": { "rss_peak_mib": null, "ram_available_mib": null },
  "console_commands": [ { "command": "<命令>", "raw_output": "<原始输出>" } ],
  "anomalies": [],
  "stopped": true
}
```

- 所有 `null` 必须替换为实测值；无法测得写 `UNKNOWN` 并说明原因。
- 日志原文片段必须保留（用于可复现）。

## 6. 验证规则（怎么算 PASS）

- [ ] `bedrock-flow status` 显示运行中，且**日志**中有版本自报证据。
- [ ] 自报版本与 `registry/runtime.json` 的 `runtime.minecraft` 一致（不一致 → `FAIL` 并转 `bedrock-version`）。
- [ ] 运行用户为 `bedrock`，非 root。
- [ ] 使用世界位于 `/opt/bedrock-flow/test-worlds/`，**未触及用户世界**。
- [ ] 起服前已确认内存；若不足已降配置，且**未新增 swap 掩盖**。
- [ ] 控制台命令的原始输出已保存。
- [ ] 测试结束后服务已停止（或明确说明保留原因）。
- [ ] 未修改 BDS 二进制 / vanilla 核心包（可用校验和或 mtime 佐证）。

任一不满足 → `FAIL`。

## 7. 已知 UNKNOWN（不得当作事实）

- UDP 端口观测：`ss -lunp` 显示 `7551`，而日志称 `Accepting clients on [::]:19132`，两者不一致，**尚未解明**。需要时按以下步骤查证并记录结论，**不得**直接断言其一正确：
  1. `ssh gz "bedrock-flow status"` 与 `ssh gz "ss -lunp | grep -i bedrock"` 同时取证；
  2. 检查 `server.properties` 中的端口设置与是否启用 IPv6；
  3. 记录原始输出到报告 `anomalies`。

## 8. 转交

- 版本不一致 → `bedrock-version`
- 需要新 BDS 包 → 从官方下载页取得（`registry/runtime.json` 的 `download_page`），日本节点下载后 `scp` 到广州
- 起服成功 → `bedrock-test`（B 层）
- 启动失败 → `bedrock-debug`

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 03 | `experience/mod-experience/03-踩坑大全-环境侧.md` |
| 教材 05 | `experience/mod-experience/05-无头Bot实验室.md` |
| 错误 | `11-错误索引.md` B 组坑 1~9（含 OOM 事故） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
