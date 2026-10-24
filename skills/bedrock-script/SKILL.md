---
name: bedrock-script
description: Minecraft Script API 的版本锁定、依赖固定与脚本实现流程（任务书 §23）。当需要写 @minecraft/server 脚本、注册事件、做 UI、锁定模块版本、配置 manifest script_modules 或保证 npm ci 可重复构建时使用。
whenToUse: 用户说「加个脚本/事件/UI」「用 @minecraft/server 做某事」「script module 版本怎么写」「npm install 后跑不起来」，或 Design Contract 的产物层含 Script/UI 时。
---

# bedrock-script — Script API 层

本技能**只定义流程与锁定规则**。任何 API 名、方法签名、事件名、模块版本一律从官方模块元数据与官方样例现查，**禁止凭记忆写**。

## 0. 权威事实源

| 用途 | 位置 |
|---|---|
| 各 `@minecraft/*` 模块的 stable/beta 版本清单与 UUID | `/opt/bedrock-flow/registry/api.json` |
| 官方模块元数据（逐版本，含依赖关系） | `/opt/bedrock-flow/sources/official/bedrock-samples/metadata/script_modules/@minecraft/*.json` |
| 官方脚本样例 | `/opt/bedrock-flow/sources/official/bedrock-samples/`（`metadata/script_modules/` 与仓库内脚本样例）、`/opt/bedrock-flow/sources/official/minecraft-scripting-samples/` |
| 汇总版本视图 | `/opt/bedrock-flow/registry/VERSION_REGISTRY.json` → `script_api` |
| 校验工具 | `/opt/bedrock-flow/tools/validate/` |
| 工程内依赖锁定 | 项目 `package.json` + `package-lock.json`（`npm ci` 必须可重复） |

**上次取证结果（仅供参考，动手前必须重新读 `registry/api.json`）**：stable 上限为 `@minecraft/server` `2.10.0`、`@minecraft/server-ui` `2.2.0`、`@minecraft/common` `1.3.0`、`@minecraft/server-graphics` `1.0.0`。部分模块**仅有 beta**（如 `@minecraft/server-admin`、`server-net`、`server-gametest`、`diagnostics`、`debug-utilities`）。

## 1. 什么时候使用

- 需要写/改 Script API 代码（事件监听、方块/物品/实体交互、命令、UI）。
- 需要配置 `manifest.json` 的 `script_modules`（entry、version、UUID）。
- 需要锁定依赖版本、验证 `npm ci` 可重复构建。
- 脚本加载失败、模块版本报错、API 未定义。
- Design Contract 的产物层含 Script 或 UI。

**不适用**：BP/RP 静态产物本体（`bedrock-block` / `bedrock-item` / `bedrock-entity`）。

## 2. 检查顺序

1. **前置**：`design.yaml` 存在且 Script 层已列入；`registry/compatibility.json` 已解析。
2. **列需求 API**：把功能拆成需要的模块与能力（如事件订阅、维度操作、UI 表单）。
3. **逐项取证**：对每个 API/事件/类，在官方模块元数据（对应**版本**的 JSON）与官方样例中确认存在。**查不到 → 写 `UNKNOWN` 并给查证步骤，不得猜**。
4. **定模块版本**：取 `registry/api.json` 中该模块的 `stable_max`。
   - `stable_max` 为 `null`（仅 beta）→ **报 BLOCKER**，不得在 stable 项目中使用 beta 模块。
5. **锁依赖**：`package.json` 写**精确版本**（无 `^` `~` `latest`），生成 `package-lock.json`。
6. **验证可重复构建**：`npm ci` 成功且不改变 lockfile。
7. **写代码**：TypeScript 或 JavaScript（按项目约定）；入口文件与 manifest 的 entry 一致。
8. **接线 manifest**：`script_modules` 的 `entry`、`version`、`uuid`、`language` 与模块声明一致；UUID 唯一。
9. **静态分析**：syntax → TS compile（若用 TS）→ import 解析 → 依赖树。
10. **B 层运行时**：脚本 init 成功 + 事件注册成功 + 行为符合预期。
11. **C 层**：UI 外观属视觉，`MANUAL_GATE`。

## 3. 工具调用顺序

```bash
# 1) 模块版本（唯一权威）
ssh gz "cat /opt/bedrock-flow/registry/api.json"
ssh gz "python3 -c \"import json;d=json.load(open('/opt/bedrock-flow/registry/api.json'));[print(k, v['stable_max'], v['beta_max'], v['uuid']) for k,v in d['modules'].items()]\""

# 2) 官方模块元数据（确认 API 是否存在、依赖关系）
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/metadata/script_modules/@minecraft/ | grep '<模块名>'"

# 3) 官方脚本样例
ssh gz "ls /opt/bedrock-flow/sources/official/minecraft-scripting-samples/"

# 4) 依赖锁定与可重复构建（项目内）
ssh gz "cd /opt/bedrock-flow/projects/<id> && cat package.json && npm ci && git diff --exit-code package-lock.json"

# 5) 静态分析 / 构建
bedrock-flow validate
bedrock-flow build

# 6) 运行时
bedrock-flow bds start && bedrock-flow test
```

- 脚本入口路径必须与 `manifest.json` 的 `script_modules[].entry` 完全一致。
- 模块 UUID 必须使用官方 `registry/api.json` 中记录的对应模块 UUID，**不得自行编造**（以官方元数据为准）。
- 若 `bedrock-flow build` 不存在 → 记 `UNKNOWN`，用项目内已锁定的构建脚本执行并记录原始输出。

## 4. 禁止做什么

1. 禁止**凭记忆**使用 API / 事件名 / 方法签名（铁律第 11 条：无证据不得声称 API 支持某版本）。
2. 禁止在 stable 项目中使用 beta 模块（`2.11.0-beta` 等）或 `-beta` 版本号。
3. 禁止浮动依赖：`^` / `~` / `latest` / 无版本（§23）。
4. 禁止 `npm install` 无锁地把最新包拉进生产工程（§23）；生产走 `npm ci`。
5. 禁止自行编造模块 UUID 或 `script_modules` 字段。
6. 禁止把 `main` 分支的官方仓库当 stable 事实源。
7. 禁止只做静态分析就宣布脚本可用。
8. 禁止用"BDS 能启动"证明脚本逻辑正确（必须看到脚本 init 与行为证据）。
9. 禁止伪造 UI 视觉 PASS。
10. 禁止整项目重写来修一个脚本错误。

## 5. 输出格式

```
projects/<project_id>/
├── behavior_pack/
│   ├── manifest.json                 # script_modules: entry/version/uuid/language
│   └── scripts/<entry>.js|ts
├── package.json                      # 精确版本依赖
├── package-lock.json                 # 锁定
└── reports/
    └── script-deps.lock.json         # 记录 runtime + script API + node/npm/ts 版本
```

`script-deps.lock.json`（§23 要求记录）：

```json
{
  "minecraft_runtime": "<registry/runtime.json>",
  "script_api": {
    "@minecraft/server": "<stable_max>",
    "@minecraft/server-ui": "<stable_max，若使用>"
  },
  "node": "<node -v>",
  "npm": "<npm -v>",
  "typescript": "<tsc -v，若使用>",
  "build_tools": "<工具名@精确版本，若有>",
  "manifest_script_modules": [
    { "module_name": "@minecraft/server", "version": "<stable_max>", "uuid": "<官方 UUID>" }
  ]
}
```

脚本级证据条目：

```yaml
feature: <feature_id>
layer: Script
apis:
  - symbol: "<API/事件名>"
    module: "@minecraft/server"
    version: "<stable_max>"
    evidence: "<官方模块元数据相对路径 或 官方样例相对路径>"
tests:
  - id: script_init_ok        # B 层：无加载错误、脚本已初始化
    layer: B
  - id: event_registered      # B 层：事件注册成功
    layer: B
  - id: behavior_expected     # B 层：行为符合 acceptance
    layer: B
  - id: ui_visual             # C 层（若含 UI）
    layer: C
    gate: MANUAL_GATE
```

## 6. 验证规则（怎么算 PASS）

**A 层（静态，自动）**
- [ ] 所有使用的 API/事件都能在官方模块元数据（对应版本）或官方样例中找到依据，并记录证据路径。
- [ ] 所有模块版本 ≤ `registry/api.json` 的 `stable_max`，且**无 beta**。
- [ ] `package.json` 无浮动版本；`npm ci` 成功且 lockfile 无变更。
- [ ] TS 编译（若用 TS）无错误；import 全部可解析；依赖树无缺失。
- [ ] `manifest.json` 的 `script_modules` entry/version/uuid 与实际一致，UUID 合法且唯一。

**B 层（BDS 运行时，自动）**
- [ ] 服务器日志无脚本加载/模块版本错误。
- [ ] 脚本初始化完成、事件注册成功。
- [ ] 行为符合 Design Contract 的 acceptance，且有 `BF_TEST_RESULT {"id":"...","status":"PASS",...}` 证据行。

**C 层（视觉，人工闸门）**
- [ ] UI/图形效果由客户端验证；无客户端证据时为 `MANUAL_GATE`。

任一自动层 FAIL → `FAIL`，转 `bedrock-debug`。

## 7. 转交

- API 是否存在/叫法 → `bedrock-research`
- 模块版本与通道判定 → `bedrock-version`
- 构建与锁 → `bedrock-build`；运行时 → `bedrock-bds`；测试 → `bedrock-test`
- 失败定位 → `bedrock-debug`

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 07 | `experience/mod-experience/07-运行时引擎.md`（事件接线三条铁律） |
| 错误 | `11-错误索引.md` A 组（写回必须在事件之外） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
