---
name: bedrock-version
description: Bedrock 目标运行时解析与版本冲突仲裁流程（任务书 §12 §13 §14 §15）。当需要确定目标 Minecraft 运行时、选择官方 stable samples/schema baseline、判定 stable 与 preview 通道、或按优先级链仲裁版本冲突时使用。
whenToUse: 用户指定了版本、需要切换版本、发现 samples/schema/BDS/script API 版本不一致、或要写入/更新 registry 版本字段时。
---

# bedrock-version — 版本解析与冲突仲裁

本技能**只定义解析流程与优先级**。版本值一律从 registry 与官方源现读，禁止凭记忆写。

## 0. 权威事实源

| 文件 | 作用 |
|---|---|
| `/opt/bedrock-flow/registry/runtime.json` | 运行时（Minecraft/BDS/channel）、包格式观测值、vanilla `min_engine_version` |
| `/opt/bedrock-flow/registry/VERSION_REGISTRY.json` | 汇总视图：runtime / server / pack_formats / script_api / references |
| `/opt/bedrock-flow/registry/compatibility.json` | baseline 解析结论、被排除项、preview 可用项、证据状态 |
| `/opt/bedrock-flow/registry/api.json` | 各 `@minecraft/*` 模块的 stable/beta 版本清单与 UUID |
| `/opt/bedrock-flow/sources/SOURCE_MANIFEST.json` | 各源的实际 revision |
| `/opt/bedrock-flow/bds/` | 已安装的 BDS 版本目录 + `current` 软链 |
| `/opt/bedrock-flow/tools/bds/bds.sh` | `bedrock-flow versions` 可列已装版本 |

**上次取证结果（仅供参考，动手前必须重新读文件确认）**：目标运行时为 BDS `1.26.52.3` (stable)；官方 stable samples baseline 为 `v1.26.50.4`；stable schema 包为 `@minecraft/bedrock-schemas@1.26.50`；stable Script API 上限 `@minecraft/server` `2.10.0`、`@minecraft/server-ui` `2.2.0`。**这些值若与 registry 不一致，以 registry 为准。**

## 1. 什么时候使用

- 用户说「用 1.26.x」「升级到最新版」「为什么 samples 是 26.50 而服务器是 26.52」。
- 需要为 `design.yaml` 的 `runtime` 段定值。
- 出现任一冲突：samples tag ≠ BDS 版本、schema 包版本 ≠ samples tag、script module 版本 > stable 上限。
- 需要新增/修改 registry 中的版本记录。

**不适用**：拉取源文件本体 → `bedrock-sources`；查某个 API 是否存在 → `bedrock-research`。

## 2. 检查顺序

1. **读现状**：`runtime.json` + `compatibility.json` + `api.json`。
2. **确认目标通道**：`stable` 或 `preview`，二选一并写死；不允许"两个都要"。
3. **确认目标运行时**：用户显式指定的优先；未指定则用 registry 当前 stable 目标。
4. **找官方 baseline**：
   - samples：在官方 bedrock-samples 仓库中找**该运行时最近的 stable tag**（`prerelease=false`）。
   - schema：在 npm 上找与 baseline 对应的 stable 版本。
   - **官方不存在对应 tag 时，不得假装存在**（§15）；选择最近 stable baseline 并在 `resolution.reason` 中写明理由。
5. **确认 Add-On / Script API 变化**：读目标版本 changelog，判断是否有影响本功能的变更。
6. **对 script 模块逐个取 stable 上限**：以 `api.json` 的 `stable_max` 为准。
7. **写回 registry**：更新 `compatibility.json` 的 `resolution` 与 `evidence`；把 `runtime_verified` 保持 `false` 直到 BDS 实测通过。
8. **产出 resolved 三元组**并交给 `bedrock-research` / `bedrock-build`。

## 3. 工具调用顺序

```bash
# 现状
ssh gz "cat /opt/bedrock-flow/registry/runtime.json"
ssh gz "cat /opt/bedrock-flow/registry/compatibility.json"
ssh gz "cat /opt/bedrock-flow/registry/api.json"

# 统一 CLI（若存在）
bedrock-flow version resolve

# 已装 BDS 版本与当前指向
bedrock-flow versions
ssh gz "ls -l /opt/bedrock-flow/bds/current"

# BDS 自报版本（权威运行时证据）
ssh gz "bedrock-flow status; bedrock-flow log 40 | grep -i 'version\\|build'"

# samples 仓库真实 tag（需要出网时在日本节点查官方 releases API）
# 记录 tag、commit SHA、prerelease 标志

# schema 包 stable 版本
ssh gz "cat /opt/bedrock-flow/tools/validate/package.json"
ssh gz "cat /opt/bedrock-flow/tools/validate/node_modules/@minecraft/bedrock-schemas/package.json"
```

- 任何"官方是否存在某 tag"的结论都必须附上**查询动作 + 原始返回**，不能只写结论。
- 若 `bedrock-flow version resolve` 不存在 → 记为 `UNKNOWN`，按上述手工顺序读文件执行。

## 4. 禁止做什么

1. **禁止 stable 与 preview 混用**（BDS / samples / schema / script module 任一维度）。
2. 禁止使用 `bedrock-schemas` 仓库 **main 分支**作为 stable 生产事实源（已实测其 package.json 为 preview 版本）。
3. 禁止假设"26.52 一定存在完整官方 sample tag"；不存在就选最近 stable baseline 并说明（§15）。
4. 禁止用 `^` / `~` / `latest` 等浮动版本表达生产依赖。
5. 禁止在无证据时声称某 API 支持某版本。
6. 禁止把 BDS 启动成功当作 runtime 验证通过（`runtime_verified` 仍为 `false`）。
7. 禁止为迎合任务书而修改已取证的事实值。

## 5. 输出格式

写回 `registry/compatibility.json`（保持既有 schema，增量更新，不重写整文件）：

```json
{
  "target": { "minecraft": "<BDS 自报版本>", "channel": "stable" },
  "resolution": {
    "stable_samples_baseline": "<tag>",
    "reason": "<为什么选它，尤其当官方无对应 tag 时>",
    "stable_schema_package": "<npm 包@版本>",
    "rejected": { "<被排除项>": "<排除理由>" },
    "preview_available": { "bds": "...", "samples_tag": "...", "schema_npm": "..." }
  },
  "script_api_for_stable_target": { "<模块>": { "stable_max": "...", "beta_max": "..." } },
  "evidence": [ { "type": "...", "source": "...", "revision": "...", "status": "..." } ],
  "status": { "runtime_verified": false }
}
```

同时向调用方返回 **resolved 三元组**：

```
runtime        = <minecraft 版本> (stable)
samples baseline = <tag> @ <commit>
schema package = <包@版本>
script stable max = { <模块>: <版本>, ... }
```

## 6. 验证规则（怎么算 PASS）

- [ ] `target.channel` 单一且明确。
- [ ] `stable_samples_baseline` 有对应官方 tag 与 commit SHA 证据；无 tag 时 `reason` 明确说明。
- [ ] `stable_schema_package` 为 npm 上的 stable 精确版本，**非** beta 且**非** main 分支。
- [ ] 每个将要用到的 `@minecraft/*` 模块都取到了 `stable_max`；需要的模块若 `stable_max` 为 `null`（仅 beta 存在）→ 必须报 `BLOCKER`，不得降级使用 beta。
- [ ] 三元组内部自洽：samples baseline 与 schema 包同属一个 stable 系列，且不晚于目标运行时。
- [ ] `runtime_verified` 在无 BDS 实测证据时保持 `false`。

任一项不满足 → `FAIL`，不得进入实现阶段。

## 7. 冲突仲裁优先级（§14，高者胜）

```
1. 真实 BDS runtime test
2. 官方 Schema
3. 官方 Changelog
4. 官方 Documentation
5. 官方 Samples
6. 已验证 Community Case
7. 普通 Community
8. 论坛 / 博客 / 视频
```

- 低优先级来源与高优先级冲突时，**无条件以高优先级为准**，并在报告中记录冲突。
- 注意 §14 的补充：这**不是**"官方永远正确"。最终工程真相 = 理论正确 + Schema 正确 + 目标版本 + 真实 BDS 测试。四者缺一，结论标记为 `PARTIAL`。

## 8. 转交

- 需要新增/更新源文件 → `bedrock-sources`
- 版本确定后 → `bedrock-research`（证据包）或 `bedrock-build`（构建环境）

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 13 | `experience/mod-experience/13-版本降级与跨版本兼容.md` |
| 案例 | `cases/exampleproj-downgrade-2026-10/`（1.26.51→1.26.20 降级实证） |
| 登记 | `registry/compatibility.json` → `verified_downgrades` |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
