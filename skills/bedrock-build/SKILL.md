---
name: bedrock-build
description: Addon 的多层校验、构建与 Build Manifest 生成流程（任务书 §22 §39 §41）。当需要执行 Validate（文件层/Schema/工程一致性/脚本静态分析）、产出构建产物、生成可追溯的 Build Manifest 或选择构建工具时使用。
whenToUse: 用户说「构建/打包前先校验」「build 失败」「生成 build manifest」，或 Design Contract 实现完成后需要进入 BDS 运行前时。
---

# bedrock-build — 校验与构建

本技能**只定义校验层、构建流程与清单格式**。构建工具选择必须经最小 POC 验证，不得因"听起来高级"引入依赖（§39）。

## 0. 权威事实源

| 用途 | 位置 |
|---|---|
| 校验工具（ajv + 官方 schema，已装） | `/opt/bedrock-flow/tools/validate/`（`@minecraft/bedrock-schemas` 1.26.50 exact、`ajv` 8.18.0 exact、`ajv-formats` 3.0.1 exact） |
| 构建工具目录 | `/opt/bedrock-flow/tools/build/`（当前为空 → 未定型，见 §2.5） |
| 官方 JSON Schema | `/opt/bedrock-flow/sources/official/bedrock-schemas/schemas/` |
| 官方样例（工程一致性对照） | `/opt/bedrock-flow/sources/official/bedrock-samples/` |
| 版本前提 | `/opt/bedrock-flow/registry/{runtime,compatibility,api}.json` |
| 工具链实测版本 | `/opt/bedrock-flow/registry/tools.json` → `toolchain` |
| 产物目录 | `/opt/bedrock-flow/artifacts/` |
| 统一 CLI（若已实现） | `bedrock-flow validate` / `bedrock-flow build` |

**工具链实测值（见 `registry/tools.json`，可能变化）**：Ubuntu 24.04、Node v22.23.2、npm 10.9.8、Python 3.12.3、git 2.43.0、jq 1.7。

## 1. 什么时候使用

- 实现完成，进入 BDS 运行**之前**（铁律第 6 条：Validate before BDS）。
- 需要生成 Build Manifest（§41）。
- 构建失败、schema 校验失败、引用路径缺失。
- 需要决定构建工具链。

**不适用**：运行时测试（`bedrock-test`）；打包交付（`bedrock-package`）。

## 2. 检查顺序

1. **确认前置**：`design.yaml` 存在；版本三元组已解析；依赖已锁定。
2. **Level 1 文件层**：JSON syntax、UTF-8、文件名、目录结构、必需文件、引用路径、PNG/geometry/animation 文件存在性、UUID 格式、UUID 唯一性。
3. **Level 2 Schema**：用 `@minecraft/bedrock-schemas`（1.26.50 exact）做 JSON Schema 校验。**不得自己发明 schema 取代官方 schema**（§22）。
4. **Level 3 工程一致性**：检查 BP manifest dependency RP、RP manifest、script module、module version、`textures.json`、`terrain_texture.json`、`item_texture.json`、client entity、geometry、animation、controller、loot、recipe、functions。**仅检查真正存在的内容**，不存在的显式标注 N/A。
5. **Level 4 脚本静态分析**：JS/TS syntax、TypeScript compile、module import、依赖树。
6. **构建工具决策**（§39）：优先调查官方 workflow 最接近的方式（如 Microsoft `just-scripts`、`@minecraft/core-build-tasks`、Regolith）。
   - 若当前版本**已验证** → 使用。
   - 若版本/行为**不明确** → 先用**最小 POC 验证**，通过后才纳入。
   - 不得为了"工具听起来高级"增加依赖。
7. **执行构建**，产出构建产物到项目 `build/` 或约定目录。
8. **生成 Build Manifest**（§41）。
9. **git 提交**：`build-pass`（构建通过后）。
10. **移交**：交 `bedrock-bds` / `bedrock-test` 做运行时验证。

## 3. 工具调用顺序

```bash
# 0) 工具链事实
ssh gz "cat /opt/bedrock-flow/registry/tools.json"
ssh gz "cd /opt/bedrock-flow/tools/validate && cat package.json && ls node_modules/@minecraft"

# 1) 四层校验（统一 CLI 优先）
bedrock-flow validate
# 回退：直接调用已装工具
ssh gz "cd /opt/bedrock-flow/tools/validate && node <校验入口>"

# 2) 构建
bedrock-flow build
# 回退：项目内已锁定的构建脚本
ssh gz "cd /opt/bedrock-flow/projects/<id> && npm ci && npm run build"

# 3) 可重复构建自检（§23）
ssh gz "cd /opt/bedrock-flow/projects/<id> && git diff --exit-code package-lock.json"

# 4) 提交
ssh gz "cd /opt/bedrock-flow && git add projects/<id> && git commit -m 'build-pass: <id>'"
```

- 若 `tools/build/` 为空且 `bedrock-flow build` 不存在 → 记 `UNKNOWN: 构建工具未定型`，**先做最小 POC**，把 POC 结论与原始输出写入报告后再固化，不得凭猜测选型。
- 校验脚本不存在时同样记 `UNKNOWN` 并给出补齐步骤；**禁止**用自制 schema 顶替官方 schema。

## 4. 禁止做什么

1. 禁止跳过 Validate 直接进 BDS（铁律第 6 条）。
2. 禁止自行发明 schema 取代官方 schema（§22 Level 2）。
3. 禁止使用浮动依赖参与 release 构建（铁律第 16 条 / §23）。
4. 禁止为了"高级感"引入未经验证的构建工具（§39）。
5. 禁止把 N/A 的检查层伪装成 PASS；不存在的层必须显式标注。
6. 禁止只做静态校验就宣布 Addon 完成（铁律第 6 条）。
7. 禁止在 Build Manifest 中留空或写推测值（`node`/`npm`/`typescript` 等必须实取）。
8. 禁止修改 BDS 二进制或 vanilla 核心包。
9. 禁止 `git add -A` 扫入无关改动。
10. 禁止在报告里写入凭据。

## 5. 输出格式

### 校验报告 `projects/<id>/reports/validate-report.json`

```json
{
  "project": "<id>",
  "levels": {
    "L1_files":     { "status": "PASS|FAIL|N/A", "details": [] },
    "L2_schema":    { "status": "PASS|FAIL|N/A", "schema_package": "<包@版本>", "details": [] },
    "L3_consistency": { "status": "PASS|FAIL|N/A", "checked": [], "not_applicable": [] },
    "L4_script":    { "status": "PASS|FAIL|N/A", "details": [] }
  },
  "overall": "PASS|FAIL"
}
```

### Build Manifest（§41）`projects/<id>/reports/build-manifest.json`

```json
{
  "project": "<id>",
  "git_commit": "<实际 commit sha>",
  "minecraft_runtime": "<registry/runtime.json>",
  "bds_version": "<BDS 自报版本>",
  "script_api": "<实际锁定版本>",
  "node": "<node -v 实测>",
  "npm": "<npm -v 实测>",
  "typescript": "<tsc -v 实测，若无则 null>",
  "schema_version": "<@minecraft/bedrock-schemas@版本>",
  "build_time": "<ISO8601 UTC>",
  "validation": "PASS|FAIL",
  "runtime_test": "PENDING|PASS|FAIL"
}
```

- `runtime_test` 在未做 BDS 测试前必须是 `PENDING`。
- 最终 `.mcaddon` 必须能追溯到该 manifest（由 `bedrock-package` 保证）。

## 6. 验证规则（怎么算 PASS）

- [ ] L1–L4 四层中**实际存在**的内容全部 PASS；不存在的内容显式 `N/A` 且理由可查。
- [ ] Schema 校验使用的是**官方** `@minecraft/bedrock-schemas` 精确版本，而非自制 schema。
- [ ] 所有引用的外部文件（纹理/几何/动画/掉落表等）真实存在。
- [ ] UUID 格式合法且全局唯一。
- [ ] `npm ci` 可重复构建，lockfile 无漂移。
- [ ] Build Manifest 字段**全部实取**，无空值、无推测；`git_commit` 与实际一致。
- [ ] 构建工具若为新引入，附有最小 POC 的原始输出证据。
- [ ] 产物目录内容与 manifest 描述一致。

任一项不满足 → `FAIL`；**不得**进入 BDS 运行时验证阶段。

## 7. 转交

- 校验失败 → `bedrock-debug`（最小补丁）
- 构建通过 → `bedrock-bds`（起服）+ `bedrock-test`（B 层）
- 全部 PASS → `bedrock-package`

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 03 | `experience/mod-experience/03-踩坑大全-环境侧.md` |
| 错误 | `reports/errors/ERR-0013`（产物非字节可重复） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
