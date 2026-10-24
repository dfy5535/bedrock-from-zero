---
name: bedrock-package
description: Addon 打包与交付物产出流程（任务书 §41 §42 §44）。当所有必需测试通过后，需要生成 .mcaddon、build report、test report、manifest 并保证产物可追溯到 git commit 与版本三元组时使用。
whenToUse: 用户说「打包/出包/给我 mcaddon」「这个包能不能发布」，或 bedrock-test 全部 PASS、准备交付时。
---

# bedrock-package — 打包与交付

本技能**只定义打包前置条件、产物结构与追溯要求**。包内结构必须符合官方样例约定（对照 `bedrock-samples`），不得自创布局。

## 0. 现状事实（只读引用）

| 项 | 值 |
|---|---|
| 产物目录 | `/opt/bedrock-flow/artifacts/`（**已有 24 项**：11 个 `.mcaddon` 成品 + build/test/validate 报告） |
| 统一 CLI（若已实现） | `bedrock-flow package` |
| 构建清单 | `projects/<id>/reports/build-manifest.json`（由 `bedrock-build` 产出） |
| 测试报告 | `projects/<id>/reports/test-report.json`（由 `bedrock-test` 产出） |
| 官方包结构对照 | `/opt/bedrock-flow/sources/official/bedrock-samples/`（`behavior_pack/` + `resource_pack/` + `manifest.json`） |
| 工程根 | `/opt/bedrock-flow/`（git repo，`main` 分支） |

## 1. 什么时候使用

- A 层与 B 层测试全部 PASS，需要产出交付物。
- 需要生成 `.mcaddon`、build report、test report、manifest。
- 需要验证"这个包可以追溯到哪个 commit / 哪个版本"。
- 用户要求发布/交付。

**不适用**：测试未通过时（先回 `bedrock-debug`）；构建清单未生成时（先 `bedrock-build`）。

## 2. 检查顺序

1. **前置闸门**（任一不满足即拒绝打包）：
   - `design.yaml` 存在且验收条件已定义。
   - `reports/build-manifest.json` 存在，`validation == "PASS"`。
   - `reports/test-report.json` 存在，A 层与 B 层 `status == "PASS"`。
   - C 层为 `MANUAL_GATE`（**允许**打包，但报告必须显式标注视觉未验证）。
   - git 工作区干净，有对应 commit（`test-pass` / `package-pass`）。
2. **确认包结构**：BP + RP 各自含合法 `manifest.json`，结构对照官方样例。
3. **确认版本三元组**：与 `registry/compatibility.json` 一致；stable/preview 未混用。
4. **打包**：生成 `.mcaddon`（BP + RP 的组合包）。
5. **生成交付物四件套**（§42）。
6. **追溯校验**：`.mcaddon` ↔ `build-manifest.json` ↔ `test-report.json` ↔ git commit 四者互相对应。
7. **git 提交** `package-pass`。
8. **报告**：`bedrock-flow report`。

## 3. 工具调用顺序

```bash
# 1) 前置闸门
ssh gz "cat /opt/bedrock-flow/projects/<id>/reports/build-manifest.json"
ssh gz "cat /opt/bedrock-flow/projects/<id>/reports/test-report.json"
ssh gz "cd /opt/bedrock-flow && git status --short"

# 2) 包结构对照
ssh gz "ls -R /opt/bedrock-flow/projects/<id>/behavior_pack /opt/bedrock-flow/projects/<id>/resource_pack | head -40"
ssh gz "cat /opt/bedrock-flow/projects/<id>/behavior_pack/manifest.json"

# 3) 打包
bedrock-flow package
# 回退（若 CLI 未实现）：按官方包结构手动归档
ssh gz "cd /opt/bedrock-flow/projects/<id> && zip -r /opt/bedrock-flow/artifacts/<id>.mcaddon behavior_pack resource_pack"

# 4) 校验产物
ssh gz "ls -la /opt/bedrock-flow/artifacts/"
ssh gz "unzip -l /opt/bedrock-flow/artifacts/<id>.mcaddon | head -40"

# 5) 追溯与提交
ssh gz "cd /opt/bedrock-flow && git rev-parse HEAD"
ssh gz "cd /opt/bedrock-flow && git add projects/<id> artifacts && git commit -m 'package-pass: <id>'"

# 6) 报告
bedrock-flow report
```

- 若 `bedrock-flow package` 不存在 → 记 `UNKNOWN: package 子命令未实现`，使用已实测可用的归档工具（`zip`）手动打包，并把原始命令与输出写入 build report。
- **不得**发明 CLI 参数。

## 4. 禁止做什么

1. 禁止在 A/B 层未 PASS 时打包（铁律第 17 条：包只有在必需测试通过后才算完成）。
2. 禁止把 C 层视觉写成 PASS 来"凑齐全绿"（§28 / §44）。
3. 禁止只交付一个 `.mcaddon` 就结束（§42：必须四件套）。
4. 禁止在 build manifest 中留空或填写推测值。
5. 禁止产物无法追溯到 git commit（§41）。
6. 禁止使用浮动依赖参与 release 构建（铁律第 16 条）。
7. 禁止混用 stable/preview 产物。
8. 禁止把用户世界、测试世界数据或日志打进交付包。
9. 禁止在交付物中写入凭据 / token / 私钥。
10. 禁止覆盖已有同名产物而不留旧版；应保留版本区分或归档。
11. 禁止 `git add -A` 扫入无关改动。

## 5. 输出格式

### 产物四件套（§42）

```
/opt/bedrock-flow/artifacts/
├── <project_id>.mcaddon                    # BP + RP 组合包
├── <project_id>-manifest.json              # = build-manifest 的交付副本（含 git_commit）
├── <project_id>-test-report.json           # = test-report 的交付副本
└── <project_id>-build-report.md            # 人读版构建/测试/限制说明
```

### `<project_id>-build-report.md` 必备内容

```markdown
# <project_id> Build Report

## 追溯
- git_commit: <sha>
- minecraft_runtime: <registry/runtime.json>
- bds_version: <BDS 自报版本>
- script_api: <实际锁定版本>
- schema_version: <@minecraft/bedrock-schemas@版本>
- node / npm / typescript: <实测值>

## 校验与测试
| 层 | 模式 | 状态 |
|---|---|---|
| A 静态 | AUTO | PASS/FAIL |
| B 运行时 | AUTO | PASS/FAIL |
| C 视觉 | MANUAL_GATE | MANUAL_GATE |

## 已知限制
- 视觉未验证（需客户端证据）
- <其它限制 / UNKNOWN 项>

## 复现步骤
1. <命令>
2. <命令>
```

## 6. 验证规则（怎么算 PASS）

- [ ] `design.yaml` 的 `acceptance` 每条都有对应测试结论。
- [ ] `build-manifest.json`：`validation == "PASS"`，字段全部实取。
- [ ] `test-report.json`：A 层与 B 层全 PASS；C 层为 `MANUAL_GATE`。
- [ ] `.mcaddon` 可被 `unzip -l` 正常列出，且包含 BP + RP 各自的 `manifest.json`。
- [ ] 包内**不含**测试世界数据、日志、凭据。
- [ ] 四件套齐全且文件名与 `<project_id>` 一致。
- [ ] **追溯闭合**：`.mcaddon` → `<id>-manifest.json` → `git_commit` → 仓库中该 commit 真实存在（`git cat-file -e <sha>`）。
- [ ] `build-report.md` 显式写出"视觉未验证"这一限制（若 C 层为 `MANUAL_GATE`）。
- [ ] 已提交 `package-pass`，工作区干净。

任一项不满足 → `FAIL`，不得宣布交付完成。

## 7. 与 §44 验收清单的关系

打包完成只覆盖 §44 中的以下项：`mcaddon package` / `Build manifest` / `Test report`。

`BEDROCK_ENGINEERING_CORE_V1 = PASS` 需要 §44 的**全部**条目通过，其中 `[MANUAL] Client visual verification` 在无客户端证据时**不能**写 PASS。**打包成功 ≠ 项目整体验收通过。**

## 8. 转交

- 前置闸门不满足 → `bedrock-debug`（或回 `bedrock-build` / `bedrock-test`）
- 版本追溯不一致 → `bedrock-version`
- 交付完成后 → `bedrock-engineer`（汇总最终 REPORT）

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 10 | `experience/mod-experience/10-交付检查清单.md` |
| 产物 | `artifacts/`（24 项，可对照结构） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
