---
name: bedrock-research
description: Bedrock 功能需求的资料检索与兼容性证据收集流程（任务书 §36 §13）。当需要确认某个方块/物品/实体/脚本/UI/动画能力在当前目标运行时是否有官方依据，或需要产出 feature 级兼容性证据包时使用。
whenToUse: 用户提出新功能、问「这个能不能做/这个组件叫什么/这个 API 在目标版本有没有」、或在写任何 JSON/TS 之前需要官方 schema + docs + sample 三方证据时。
---

# bedrock-research — 需求解析与官方证据检索

本技能**只定义检索流程与证据格式**，不预置任何 Minecraft 知识。查到什么写什么，查不到写 `UNKNOWN`。

## 0. 权威事实源与检索优先级

证据源（全部位于广州 `/opt/bedrock-flow/`，经 `ssh gz` 访问）：

| 优先级 | 源 | 路径 / 访问 |
|---|---|---|
| 1 | 版本注册表（决定"查哪个版本"） | `registry/VERSION_REGISTRY.json`、`registry/compatibility.json` |
| 2 | 官方 JSON Schema | `sources/official/bedrock-schemas/`（仓库副本）+ `tools/validate/node_modules/@minecraft/bedrock-schemas` |
| 3 | 官方样例 | `sources/official/bedrock-samples/`（BP/RP 结构、`metadata/json_schemas/`、`metadata/script_modules/`） |
| 4 | 官方 Script 模块元数据 | `sources/official/bedrock-samples/metadata/script_modules/@minecraft/*.json` |
| 5 | 官方文档 | `https://learn.microsoft.com/minecraft/creator/`（日本节点可达；广州直连 minecraft.net 不通） |
| 6 | 官方样例集合 | `sources/official/minecraft-samples/`、`sources/official/minecraft-scripting-samples/` |
| 7 | 已验证案例 | `cases/` |
| 8 | 社区 | `sources/community/`（仅参考，**不得**作为结论唯一依据） |

源 revision 一律以 `sources/SOURCE_MANIFEST.json` 为准；引用证据必须带上 revision。

## 1. 什么时候使用

- 用户说「我要做某某 MOD」→ 这是 §36 的触发点，**第一步就必须是本技能**。
- 不确定某个组件 / 事件 / API / 文件字段是否存在或叫法是否正确。
- 需要为 `design.yaml` 的 `compatibility` 段填证据。
- 需要判断某个 GitHub 上的写法是否适用于当前目标版本。

**不适用**：纯粹版本号仲裁 → `bedrock-version`；拉取新官方源 → `bedrock-sources`。

## 2. 检查顺序（§36 的九步，顺序不可换）

1. **提取功能**：用一句话写清"玩家做什么 → 发生什么 → 如何判定成功"。
2. **判断涉及层**：Block / Item / Entity / Script / UI / Animation（可多选，必须显式列出）。
3. **查询对应官方资料**：先 schema，再 docs。
4. **查询对应 Schema**：在官方 schema 里定位到具体定义文件（记录相对路径）。
5. **查官方 Sample**：在 `bedrock-samples` 里找到**同类型**的真实样例文件（记录相对路径 + 其 `format_version`）。
6. **查已验证案例**：`cases/` 下按错误签名/功能签名检索。
7. **确认目标版本**：读 `registry/compatibility.json`，确认 stable baseline 与 script API 上限。
8. **设计**：交回 `bedrock-engineer` / `bedrock-project` 出 Design Contract。
9. **实现**：由对应的产物技能执行。

**禁止**「先写代码 → 遇到错误再查资料」。

## 3. 工具调用顺序

```bash
# 1) 版本前提
ssh gz "cat /opt/bedrock-flow/registry/compatibility.json"

# 2) Schema：先看 catalog，再定位具体 schema
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-schemas/schemas"
ssh gz "cat /opt/bedrock-flow/sources/official/bedrock-schemas/catalog.json"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/metadata/json_schemas/server"

# 3) Sample：找同类型真实样例（以 block 为例）
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/blocks | head"

# 4) Script 模块可用版本（stable 上限的唯一依据）
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/metadata/script_modules/@minecraft/"

# 5) 源 revision
ssh gz "cat /opt/bedrock-flow/sources/SOURCE_MANIFEST.json"

# 6) 文档（在日本节点出网查）
#    使用 web_search / web_fetch 访问 learn.microsoft.com/minecraft/creator/
```

- 若需要精确检索文件内容，用 grep 工具（经 `ssh gz` 读取远端内容或先 `scp` 到本机再 grep），**不要凭印象断言某个字段存在**。
- 大文件/大目录只在广州侧检索，不要整体拉回日本节点。

## 4. 禁止做什么

1. 禁止把**社区/论坛/博客/视频**当作结论的唯一依据；它们只在优先级 8，且必须标注为"未验证"。
2. 禁止把 `bedrock-schemas` 仓库 **main 分支**当作 stable 事实源（其 package.json 已实测为 preview 版本）。
3. 禁止把 preview 的 samples/schema/API 结果套到 stable 目标上。
4. 禁止"全 GitHub 爬虫"式收集（§11）；每引入一个源都必须分类 + 记 manifest。
5. 禁止在证据里省略 revision / 路径 —— 无路径的结论视为无证据。
6. 禁止编造 API 名、组件名、字段名；查不到就写 `UNKNOWN` 并写出查证步骤。
7. 禁止把本技能变成 Minecraft 知识库：只允许输出**指向官方源的路径与引用**。

## 5. 输出格式

产出**兼容性证据包**（写入 `projects/<id>/reports/evidence-<feature_id>.yaml`，或作为 `design.yaml` 的 `compatibility` 段）：

```yaml
feature:
  id: <feature_id>
compatibility:
  target_runtime: <读 registry，不手写>
evidence:
  schema:
    source: bedrock-schemas
    revision: <manifest 中的 revision>
    path: <schema 相对路径>
  docs:
    source: learn.microsoft.com
    url: <具体页面 URL>
  sample:
    source: bedrock-samples
    revision: <manifest 中的 revision>
    path: <样例相对路径>
    observed_format_version: <该样例文件里的实际值>
  runtime_test:
    bds_version: <registry/runtime.json 中的值>
    result: PENDING      # 只有 BDS 实测后才能改 PASS
classification:
  layers: [Block, Script, ...]
unknowns:
  - question: <未解决的问题>
    how_to_verify: <具体查证步骤>
```

## 6. 验证规则（怎么算 PASS）

- [ ] 每个涉及层都至少有 **schema + sample** 两条独立证据，路径可复核。
- [ ] 所有引用都带 revision，且 revision 与 `SOURCE_MANIFEST.json` 一致。
- [ ] sample 中观察到的 `format_version` 是**实际读到**的，不是推断的。
- [ ] stable/preview 通道标注明确且单一。
- [ ] 无法证实的内容全部落入 `unknowns`，且每条都有可执行的查证步骤。
- [ ] **未做 BDS 实测前，`runtime_test.result` 只能是 `PENDING`**，不得写 PASS。

任一项不满足 → `FAIL`，不得交给实现层。

## 7. 转交

- 版本前提不明 → `bedrock-version`
- 官方源缺失/revision 过期 → `bedrock-sources`
- 证据齐备 → `bedrock-project`（出 Design Contract）→ 对应产物技能

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 09 | `experience/mod-experience/09-文档阅读与协作.md` |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
