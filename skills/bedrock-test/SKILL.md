---
name: bedrock-test
description: Bedrock Addon 的三层测试执行与机器可读结果判定流程（任务书 §21 §26 §27 §28）。当需要跑静态测试、BDS 运行时测试、采集 BF_TEST_RESULT 行、生成测试报告或判定 PASS/FAIL 时使用。
whenToUse: 用户说「测一下」「跑测试」「验证 addon 是否真的能用」「测试报告在哪」，或构建完成后需要证明产物在 BDS 中真实工作、以及需要区分自动测试与人工视觉闸门时。
---

# bedrock-test — 三层测试与结果判定

本技能**只定义测试分层、证据格式与判定规则**。具体测试手段（GameTest / 脚本事件 / 控制台命令 / functions）必须按目标版本实测确认（§28 B 层明确要求）。

## 0. 现状事实（只读引用）

| 项 | 值 |
|---|---|
| 测试工具目录 | `/opt/bedrock-flow/tools/test/`（当前为空 → 未定型） |
| 测试世界 | `/opt/bedrock-flow/test-worlds/` |
| BDS Runner | `bedrock-flow`（`/opt/bedrock-flow/tools/bds/bds.sh`） |
| 日志目录 | `/opt/bedrock-flow/logs/` |
| 报告目录 | `/opt/bedrock-flow/reports/`（含 `errors/`） |
| 产物目录 | `/opt/bedrock-flow/artifacts/` |
| 统一 CLI（若已实现） | `bedrock-flow test`、`bedrock-flow report` |

**第一阶段固定策略（§28）**：`SERVER_RUNTIME = AUTO`，`VISUAL = MANUAL_GATE`。**禁止伪造视觉 PASS。**

## 1. 什么时候使用

- 构建通过后需要证明产物**在 BDS 中真实工作**。
- 需要产出机器可读测试结果供统计。
- 需要区分"自动可判定"与"必须人工看客户端"的验收项。
- 需要生成 test report。

**不适用**：构建与校验（`bedrock-build`）；失败后的定位与修补（`bedrock-debug`）。

## 2. 检查顺序

1. **确认前置**：`design.yaml` 的 `tests` 段已定义每个用例的 `id` / `layer` / `expect`；Validate 已 PASS。
2. **A 层 静态测试**（无需 BDS）：
   - JSON syntax、Schema、paths、UUID、TypeScript、dependencies、package。
3. **准备 B 层环境**：`bedrock-flow` 起服（转 `bedrock-bds`），使用可丢弃测试世界。
4. **B 层 服务器运行时测试**（在 BDS 中）：
   - Addon loading、Script init、block/item/entity existence、event registration、behavior、loot、recipe、commands、data state。
   - 测试手段（Script test harness / GameTest / server console command / custom script event / functions）**必须按目标版本确认后再用**（§28）。
5. **采集证据**：从日志中 `grep BF_TEST_RESULT` → JSON parse → 统计。
6. **C 层 客户端/视觉测试**：标记为 `MANUAL_GATE`，**在无客户端证据前不得写 PASS**。
7. **判定**：按 §6 规则给出每个用例与整体的 PASS/FAIL。
8. **生成报告**并交 `bedrock-report`（`bedrock-flow report`）/ `bedrock-package`。
9. **任何 FAIL** → 转 `bedrock-debug`。

## 3. 工具调用顺序

```bash
# 1) 统一入口（若已实现）
bedrock-flow test
bedrock-flow report

# 2) A 层（等价于 validate）
bedrock-flow validate

# 3) B 层环境
ssh gz "bedrock-flow reset-world <测试世界名>"
ssh gz "bedrock-flow start"
ssh gz "bedrock-flow status"

# 4) 执行运行时用例（手段按目标版本确认），随后采集
ssh gz "bedrock-flow log 500 > /tmp/bf-test.log"
ssh gz "grep -o 'BF_TEST_RESULT {.*}' /tmp/bf-test.log"

# 5) 本地解析（JSON parse 每行）
#    注意：日志行可能含其他前缀，需按固定前缀精确匹配

# 6) 收尾
ssh gz "bedrock-flow stop"
```

- 若 `tools/test/` 为空且 `bedrock-flow test` 不存在 → 记 `UNKNOWN: 测试 harness 未定型`，**先做最小 POC**（用已确认可用的手段跑通一个用例），把 POC 原始输出写入报告，再逐步扩展；**不得**为了凑齐用例而伪造结果。
- 测试用例的 `id` 必须与 `design.yaml` 中声明的一致。

## 4. 禁止做什么

1. **禁止伪造视觉 PASS**（§28：第一阶段 `VISUAL = MANUAL_GATE`）。
2. 禁止只做静态校验就宣布完成（铁律第 6 条）。
3. 禁止用"BDS 能启动"当作 Addon 正确（铁律第 8 条）。
4. 禁止"看起来应该成功"式判定（§27 明文禁止）；必须有 `BF_TEST_RESULT` 证据行。
5. 禁止使用用户世界做测试世界（铁律第 7 条）。
6. 禁止为让测试通过而放宽断言、删用例或改期望值。
7. 禁止篡改日志或事后补写结果行。
8. 禁止在证据不足时把状态写成 PASS；只能是 `FAIL` / `PENDING` / `MANUAL_GATE`。
9. 禁止测试后不清理（应停服并保留失败现场用于复现）。
10. 禁止在报告中写入凭据。

## 5. 输出格式

### 日志中的机器可读前缀（§27，固定不可改）

```
BF_TEST_RESULT {"id":"...","status":"PASS","duration_ms":123}
BF_TEST_RESULT {"id":"...","status":"FAIL","error":"..."}
```

### 测试报告 `projects/<id>/reports/test-report.json`

```json
{
  "project": "<id>",
  "generated_at": "<ISO8601 UTC>",
  "runtime": {
    "minecraft": "<registry/runtime.json>",
    "bds": "<BDS 自报版本>",
    "script_api": "<实际锁定版本>"
  },
  "layers": {
    "A_static":  { "mode": "AUTO", "status": "PASS|FAIL", "cases": [] },
    "B_runtime": { "mode": "AUTO", "status": "PASS|FAIL", "cases": [] },
    "C_visual":  { "mode": "MANUAL_GATE", "status": "MANUAL_GATE", "cases": [] }
  },
  "cases": [
    { "id": "<用例 id>", "layer": "A|B|C", "status": "PASS|FAIL|MANUAL_GATE", "duration_ms": 0,
      "evidence": "<日志行 / 文件路径>", "error": null }
  ],
  "summary": { "total": 0, "passed": 0, "failed": 0, "manual_gate": 0 },
  "overall": "PASS|FAIL|PARTIAL"
}
```

### 测试目录（§26）

```
projects/<project_id>/tests/
├── smoke/       # 最小冒烟
├── runtime/     # B 层用例
└── expected/    # 期望结果基线
```

## 6. 验证规则（怎么算 PASS）

**A 层（AUTO）**
- [ ] JSON / Schema / 路径 / UUID / TypeScript / 依赖 / 包结构全部通过。

**B 层（AUTO）**
- [ ] 每个 B 层用例在日志中都有**对应的** `BF_TEST_RESULT` 行，且 JSON 可解析。
- [ ] `id` 与 `design.yaml` 声明一致；无缺失用例、无重复 id。
- [ ] 所有 B 层用例 `status == "PASS"`。
- [ ] 用例是在**可丢弃测试世界**中运行，且服务器日志无 addon 加载错误。

**C 层（MANUAL_GATE）**
- [ ] 状态为 `MANUAL_GATE`，且报告中明确写出"需要客户端证据"。
- [ ] **无客户端证据时不得出现 C 层 PASS**。

**整体判定**
- [ ] A + B 全 PASS 且 C 为 `MANUAL_GATE` → `overall = PASS`（但最终报告必须显式标注视觉未验证）。
- [ ] 任一 A/B 用例 FAIL → `overall = FAIL`，转 `bedrock-debug`。
- [ ] 缺少证据行 → 该用例视为 `FAIL`（不是"跳过"）。

## 7. 转交

- 环境问题 → `bedrock-bds`
- 任何 FAIL → `bedrock-debug`
- 全 PASS → `bedrock-package`（打包）+ 报告归档

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 04 | `experience/mod-experience/04-踩坑大全-测试侧.md` |
| 教材 08 | `experience/mod-experience/08-测试方法论.md` |
| 错误 | `11-错误索引.md` A 组（SimulatedPlayer 系列陷阱） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
