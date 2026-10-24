---
name: bedrock-engineer
description: Bedrock Addon 工程的总入口与编排者。当用户提出任何「做/改/修/验证/打包一个 Minecraft Bedrock Addon、方块、物品、实体、脚本、UI」类端到端需求，需要按「证据→版本→Schema→代码→Build→Runtime→Test→Report」串联并分派给其它 bedrock-* 技能时使用。
whenToUse: 用户说「我要做某某 MOD」「帮我加一个自定义方块/物品/实体/脚本」「这个 addon 跑不起来」「帮我从零建一个工程并打包」等尚未确定该走哪条子流程的端到端请求时，先加载本技能。
---

# bedrock-engineer — 总入口 / 编排者

本技能**只定义流程**，不承载 Minecraft 知识。任何具体 API、组件名、format_version、Schema 细节一律去官方源现查，禁止凭记忆填写。

## 0. 权威事实源（只读引用，不得重述为"我的知识"）

| 用途 | 位置 |
|---|---|
| 版本 / 运行时 / API 上限 | `/opt/bedrock-flow/registry/VERSION_REGISTRY.json`、`registry/runtime.json`、`registry/api.json`、`registry/compatibility.json` |
| 官方源清单与 revision | `/opt/bedrock-flow/sources/SOURCE_MANIFEST.json` |
| 官方 BP/RP 样例 | `/opt/bedrock-flow/sources/official/bedrock-samples/`（含 `metadata/script_modules/`、`metadata/json_schemas/`） |
| 官方 JSON Schema | `/opt/bedrock-flow/sources/official/bedrock-schemas/` |
| 校验工具（ajv + bedrock-schemas 已装） | `/opt/bedrock-flow/tools/validate/` |
| 工程根 | `/opt/bedrock-flow/`（广州，经 `ssh gz "<命令>"` 操作，免密） |

**铁律：本技能内出现的任何版本号都只是"上次取证结果"。动手前必须重新读 registry，以文件内容为唯一权威。**
若 registry 缺失或与预期不符 → 走 `bedrock-version`，不要自行推断。

## 1. 什么时候使用

- 用户给出一个**功能目标**（而不是一条具体命令）：做 MOD、加方块、加物品、加实体、加脚本、加 UI、加动画。
- 用户给出一个**失败现象**但根因未定：「BDS 启动报错」「addon 加载失败」「测试不过」→ 先本技能定性，再转 `bedrock-debug`。
- 用户要求**端到端交付**：设计 + 实现 + 测试 + 打包。

**不适用**：单点查询（"这个 API 在哪个版本有"）→ 直接 `bedrock-research`；单纯起停 BDS → `bedrock-bds`。

## 2. 检查顺序（严格串行，前一步不 PASS 不进下一步）

1. **接单与解析**：把用户原话拆成「功能 / 产物类型 / 目标运行时」三项。产物类型必须归入 Block / Item / Entity / Script / UI / Animation 之一或多个。
2. **目标运行时确认**：读 `registry/runtime.json`。若用户未指定版本 → 用 registry 的当前 stable 目标；若用户指定了与 registry 不同的版本 → 转 `bedrock-version` 做仲裁，**不得擅自改 registry**。
3. **证据检索**：转 `bedrock-research`，产出兼容性证据包（schema + docs + sample + 版本）。
4. **版本解析**：转 `bedrock-version`，产出 resolved 版本三元组（runtime / samples baseline / schema 包）与 script API 上限。
5. **工程骨架**：转 `bedrock-project`，产出 `projects/<id>/` 与 `design.yaml`（Design Contract）。
6. **实现**：按产物类型分派 `bedrock-block` / `bedrock-item` / `bedrock-entity` / `bedrock-script`。
7. **校验**：`bedrock-build` 前先跑多层 Validate（文件层 → Schema 层 → 工程一致性 → 脚本静态分析）。
8. **构建**：转 `bedrock-build`，产出 Build Manifest。
9. **运行时**：转 `bedrock-bds` 起服 + `bedrock-test` 跑 B 层。
10. **测试判定**：转 `bedrock-test`，A 层 AUTO、B 层 AUTO、C 层 `MANUAL_GATE`。
11. **失败回流**：任何 FAIL → 转 `bedrock-debug`，禁止在本技能里直接改代码。
12. **打包**：全绿后转 `bedrock-package`。
13. **报告**：`bedrock-flow report` + 最终 REPORT。

## 3. 工具调用顺序

```bash
# 0) 环境自检
bedrock-flow doctor
# 1) 读权威事实（只读）
ssh gz "cat /opt/bedrock-flow/registry/runtime.json"
ssh gz "cat /opt/bedrock-flow/registry/compatibility.json"
# 2) 源同步 / 版本解析
bedrock-flow source sync
bedrock-flow version resolve
# 3) 校验 → 构建
bedrock-flow validate
bedrock-flow build
# 4) 运行时
bedrock-flow bds start
# 5) 测试 → 报告 → 打包
bedrock-flow test
bedrock-flow report
bedrock-flow package
```

- 统一 CLI 由主 agent 同期实现；**若某子命令不存在**：记录 `UNKNOWN: bedrock-flow <子命令> 未实现`，改用已实测可用的等价手段（如 `bedrock-flow install|configure|start|stop|restart|status|console|log|set-world|reset-world|worlds|versions`），**禁止自行发明子命令或参数**。
- 所有涉及广州的操作必须显式走 `ssh gz "<命令>"`；不要把广州路径当成日本本机路径直接读写。

## 4. 禁止做什么

1. 禁止**先写代码再查资料**（§36 明确禁止）。
2. 禁止 stable 与 preview **混用**（samples / schema / BDS / script module 任一维度）。
3. 禁止凭记忆写任何 Minecraft JSON、组件名、format_version、UUID。
4. 禁止跳过 `design.yaml`（Design Contract）直接产出成品文件（§37 §38）。
5. 禁止"只做静态校验就宣布完成"、"BDS 能启动就宣布 Addon 正确"（§1）。
6. 禁止伪造 C 层（视觉）PASS：第一阶段 `VISUAL = MANUAL_GATE`。
7. 禁止整项目重写；只允许最小补丁（§29）。
8. 禁止手删不明目录、修改 BDS 二进制/vanilla 核心、下载无关仓库。
9. 禁止在文件或日志中写入密码 / token / 私钥。
10. 禁止触碰广州上与本任务无关的服务。

## 5. 输出格式

每个需求在 `projects/<project_id>/` 下产出，且阶段产物齐全（§38：PLAN / DESIGN / IMPLEMENTATION / VALIDATION / RUNTIME / TEST / REPORT 缺一不可）：

```
projects/<project_id>/
├── design.yaml            # Design Contract（§37）
├── behavior_pack/
├── resource_pack/
├── tests/{smoke,runtime,expected}/
├── reports/
└── package.json
```

编排层额外产出：
- `reports/<project_id>-orchestration.md`：分派记录（每步交给哪个技能、结论、证据路径）。
- 最终交付物由 `bedrock-package` 落到 `/opt/bedrock-flow/artifacts/`。

## 6. 验证规则（怎么算 PASS）

本技能自身 PASS 的判定：

- [ ] `design.yaml` 存在且含 feature/goal/inputs/outputs/files/dependencies/runtime/tests/acceptance（§37 字段齐全）。
- [ ] 每一步都有**可复现证据路径**（文件路径或命令 + 原始输出），不是"看起来对"。
- [ ] 版本三元组来自 `registry/`，且 stable/preview 未混用。
- [ ] Validate 四层中**实际存在的内容**都跑过（不存在的层要显式标注 N/A，而不是静默跳过）。
- [ ] B 层测试有 `BF_TEST_RESULT {...}` 机器可读行作为证据。
- [ ] C 层标注 `MANUAL_GATE`（未获客户端证据时**不得**写 PASS）。
- [ ] 失败项均已生成 `/opt/bedrock-flow/reports/errors/` 下的错误记录。

任一项不满足 → 整体状态 `FAIL` 或 `PARTIAL`，**不得**上报完成。

## 7. 分派表（转给谁）

| 情形 | 转交 |
|---|---|
| 需要查 API/组件/格式是否有官方依据 | `bedrock-research` |
| 版本选择、冲突、stable/preview 判定 | `bedrock-version` |
| 官方源缺失 / 需要拉新源 / 更新 SOURCE_MANIFEST | `bedrock-sources` |
| 新建工程骨架、Design Contract、git | `bedrock-project` |
| 自定义方块 | `bedrock-block` |
| 自定义物品 | `bedrock-item` |
| 自定义实体 | `bedrock-entity` |
| Script API / UI / 事件逻辑 | `bedrock-script` |
| 校验 + 构建 + Build Manifest | `bedrock-build` |
| BDS 安装/起停/世界/日志 | `bedrock-bds` |
| 三层测试与机器可读结果 | `bedrock-test` |
| 任何 FAIL 的定位与最小补丁 | `bedrock-debug` |
| 打包与交付物 | `bedrock-package` |

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 01 | `experience/mod-experience/01-全景时间线.md`（知道会经历什么） |
| 教材 10 | `experience/mod-experience/10-交付检查清单.md`（交付标准） |
| 案例库 | `cases/`（全部历史案例） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
