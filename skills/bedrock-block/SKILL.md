---
name: bedrock-block
description: 自定义方块（Behavior Pack block + Resource Pack 纹理）的实现流程与校验规则。当需要在 addon 中新增/修改自定义方块、方块的 format_version、组件、纹理引用或方块相关 Schema 校验时使用。
whenToUse: 用户说「加一个自定义方块」「这个方块不显示/贴图错/放不下去」「block 的 format_version 该写多少」，或 Design Contract 的产物层含 Block 时。
---

# bedrock-block — 自定义方块产物层

本技能**只定义流程**。方块的组件名、字段、`format_version` 取值一律从官方 schema 与官方样例现查，**禁止凭记忆写 JSON**。

## 0. 权威事实源

| 用途 | 位置 |
|---|---|
| 官方 block JSON Schema | `/opt/bedrock-flow/sources/official/bedrock-schemas/schemas/`（先读 `catalog.json` 定位） |
| 官方 BP 方块样例 | `/opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/blocks/` |
| 官方样例内的 schema 副本 | `/opt/bedrock-flow/sources/official/bedrock-samples/metadata/json_schemas/server/block/` |
| 观测到的 block `format_version` | `registry/runtime.json` → `pack_formats.observed_file_format_versions.block`（**只是观测值，须按目标内容类型选择**） |
| 校验工具 | `/opt/bedrock-flow/tools/validate/`（ajv 8.18.0 + `@minecraft/bedrock-schemas` 1.26.50 精确版本） |

**注意**：`format_version` 是**文件级**，不是包级；registry 里列的是"观测到的取值集合"，不是"唯一正确值"。必须以官方样例中**同类方块**的实际取值为准。

## 1. 什么时候使用

- 用户要求新增/修改自定义方块。
- 方块在 BDS 里加载失败、贴图丢失、无法放置、组件无效。
- 需要为方块写 `blocks/*.json`、方块纹理、`terrain_texture.json` 引用。
- Design Contract 的 `files.bp` / `files.rp` 含方块产物。

**不适用**：纯脚本逻辑（交互用 `bedrock-script`）；实体（`bedrock-entity`）。

## 2. 检查顺序

1. **前置**：确认 `projects/<id>/design.yaml` 存在且 Block 层已列入；`registry/compatibility.json` 已解析。
2. **查 schema**：定位官方 block schema 文件，读其 `format_version` 约束与组件枚举。
3. **查样例**：在官方 `behavior_pack/blocks/` 找**同类型**方块（如自定义普通方块 vs 多方块状态），读其实际结构与 `format_version`。
4. **定标识符**：命名空间 + 名称；检查与 vanilla / 已用标识符不冲突。
5. **定组件集**：逐个组件在 schema 里确认存在且字段合法；**没有 schema 依据的组件不得写入**。
6. **写 BP 文件**：`behavior_pack/blocks/<name>.json`。
7. **写 RP 资源**：纹理 PNG + `textures/terrain_texture.json` 条目 + `textures/textures_list.json`（若项目约定使用）。
8. **接线**：确认 BP manifest 已声明该模块/包，路径引用一致。
9. **静态校验**：JSON syntax → schema → 引用路径 → UUID。
10. **运行时校验**：交 `bedrock-test` 跑 B 层（方块存在性 + 放置行为）。
11. **视觉**：交 C 层 `MANUAL_GATE`（贴图/模型是否正确只能由客户端证明）。

## 3. 工具调用顺序

```bash
# 1) schema 定位
ssh gz "cat /opt/bedrock-flow/sources/official/bedrock-schemas/catalog.json"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-schemas/schemas"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/metadata/json_schemas/server/block/"

# 2) 官方样例（看真实结构与 format_version）
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/blocks/ | head -30"
ssh gz "grep -h 'format_version' /opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/blocks/*.json | sort | uniq -c"

# 3) 观测值（辅助，不是权威）
ssh gz "python3 -c \"import json;d=json.load(open('/opt/bedrock-flow/registry/runtime.json'));print(d['pack_formats']['observed_file_format_versions']['block'])\""

# 4) 写文件后：静态校验
bedrock-flow validate
# 或直接用已装工具（tools/validate 下）
ssh gz "cd /opt/bedrock-flow/tools/validate && node <校验脚本>"

# 5) 运行时（B 层）
bedrock-flow bds start
bedrock-flow test
```

- 校验脚本若不存在 → 记 `UNKNOWN: 未找到 block 专用校验脚本`，并给出查证/补齐步骤，**不得**自己发明一套 schema 取代官方 schema（§22 Level 2）。
- 纹理文件必须在广州侧真实存在；引用路径大小写敏感。

## 4. 禁止做什么

1. 禁止**凭记忆**写方块 JSON、组件名、字段名、`format_version`。
2. 禁止自行发明 JSON Schema 替代官方 schema（§22）。
3. 禁止混用 preview 的方块特性到 stable 目标。
4. 禁止引用不存在的纹理 / 几何体路径（Level 1 会直接 FAIL）。
5. 禁止 UUID 重复或格式非法。
6. 禁止修改 vanilla 核心包来完成自定义方块（铁律第 10 条 / §1）。
7. 禁止只做静态校验就宣布方块完成（§1 第 6 条）。
8. 禁止用「BDS 能启动」证明方块正确（§1 第 7 条）。
9. 禁止伪造视觉 PASS。
10. 禁止整项目重写来修一个方块错误（转 `bedrock-debug` 做最小补丁）。

## 5. 输出格式

```
projects/<project_id>/
├── behavior_pack/
│   ├── manifest.json                     # 已声明该模块
│   └── blocks/<name>.json                # format_version + minecraft:block
└── resource_pack/
    ├── manifest.json
    ├── textures/
    │   ├── blocks/<name>.png
    │   ├── terrain_texture.json          # 方块纹理条目
    │   └── textures_list.json            # 若项目约定
    └── texts/<lang>.lang                 # 显示名（若需要）
```

同时产出方块级证据条目（追加到项目 `reports/`）：

```yaml
feature: <feature_id>
layer: Block
files: [ <bp/rp 相对路径> ]
identifier: "<namespace:name>"
format_version: "<实测于官方样例，非推断>"
components:
  - name: "<组件>"
    schema_ref: "<schema 相对路径>"
    sample_ref: "<官方样例相对路径>"
tests:
  - id: block_exists        # B 层：方块已注册
    layer: B
  - id: block_place_behavior # B 层：放置触发预期行为
    layer: B
  - id: block_texture_visual # C 层
    layer: C
    gate: MANUAL_GATE
```

## 6. 验证规则（怎么算 PASS）

**A 层（静态，自动）**
- [ ] 所有 JSON 语法合法、UTF-8、文件名与目录结构符合官方样例惯例。
- [ ] 通过官方 block schema 校验（`@minecraft/bedrock-schemas@1.26.50`）。
- [ ] 每个引用的纹理/几何体路径真实存在。
- [ ] UUID 格式合法且项目内唯一。

**B 层（BDS 运行时，自动）**
- [ ] 服务器日志中**无**方块加载错误。
- [ ] 方块已注册（通过控制台命令或脚本查询，具体手段以目标版本实际 API 为准）。
- [ ] 放置 → 预期行为被触发，且有 `BF_TEST_RESULT {"id":"...","status":"PASS",...}` 证据行。

**C 层（视觉，人工闸门）**
- [ ] 纹理/模型外观由客户端验证；未获客户端证据时状态必须是 `MANUAL_GATE`，**不得写 PASS**。

任一自动层 FAIL → `FAIL`，转 `bedrock-debug`。

## 7. 转交

- 组件/字段是否有官方依据 → `bedrock-research`
- `format_version` 与版本冲突 → `bedrock-version`
- 校验/构建 → `bedrock-build`；运行时 → `bedrock-bds`；测试 → `bedrock-test`
- 失败定位 → `bedrock-debug`

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 02 | `experience/mod-experience/02-踩坑大全-产品侧.md` |
| 案例 | `cases/example-block-smoke-custom-block-smoke/`（自定义方块实证） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
