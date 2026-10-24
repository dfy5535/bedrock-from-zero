---
name: bedrock-entity
description: 自定义实体（BP entity + RP client_entity/几何/动画/渲染控制器/刷怪与掉落）的实现流程与校验规则。当需要在 addon 中新增/修改自定义实体、实体行为、模型动画绑定、生成规则或掉落表时使用。
whenToUse: 用户说「加一个自定义生物/实体」「实体不生成/不显示/动画不播/掉落不对」，或 Design Contract 的产物层含 Entity 时。
---

# bedrock-entity — 自定义实体产物层

本技能**只定义流程**。实体组件、行为、动画控制器语法一律从官方 schema 与官方样例现查，**禁止凭记忆写 JSON**。实体是跨 BP/RP 最多的产物层，**引用链最长，必须逐环验证**。

## 0. 权威事实源

| 用途 | 位置 |
|---|---|
| 官方 entity JSON Schema | `/opt/bedrock-flow/sources/official/bedrock-schemas/schemas/`（先读 `catalog.json`） |
| 官方样例内 schema 副本 | `sources/official/bedrock-samples/metadata/json_schemas/{server,client,client_server}/` |
| 官方 BP 实体样例 | `sources/official/bedrock-samples/behavior_pack/entities/` |
| 官方 RP 客户端实体样例 | `sources/official/bedrock-samples/resource_pack/entity/` |
| 官方模型/动画 | `sources/official/bedrock-samples/resource_pack/{models,animations,animation_controllers,render_controllers}/` |
| 官方掉落表 | `sources/official/bedrock-samples/behavior_pack/loot_tables/` |
| 版本与格式 | `registry/runtime.json`、`registry/compatibility.json` |
| 校验工具 | `/opt/bedrock-flow/tools/validate/` |

## 1. 什么时候使用

- 用户要求新增/修改自定义实体、生物、投射物、载具。
- 实体加载失败、不生成、不显示、动画不播、掉落异常。
- 需要写 `entities/*.json`、`entity/*.json`（客户端）、geometry、animation、animation_controller、render_controller、spawn_rules、loot_table。
- Design Contract 的产物层含 Entity。

**不适用**：实体的脚本逻辑（`bedrock-script`）；纯方块/物品（`bedrock-block` / `bedrock-item`）。

## 2. 检查顺序（跨 BP/RP，逐环串行）

1. **前置**：`design.yaml` 存在且 Entity 层已列入；版本三元组已解析。
2. **查 schema**：分别定位服务端实体 schema 与客户端实体 schema。
3. **查样例**：找**最接近的同类实体**（行为包 + 客户端包 + 模型 + 动画 + 渲染控制器 + 掉落表**整套**），记录每个文件的实际 `format_version`。
4. **定标识符**：实体 identifier（`namespace:name`）；客户端实体标识符必须与 BP 侧一致。
5. **设计引用链**（这是实体层的关键）：
   ```
   BP entities/<id>.json  (identifier)
     → RP entity/<id>.entity.json   (client entity，引用 geometry / texture / render_controller / animation)
       → RP models/entity/<geo>.geo.json
       → RP textures/entity/<tex>.png
       → RP render_controllers/<rc>.json
       → RP animations/<anim>.animation.json
       → RP animation_controllers/<ac>.json
     → BP spawn_rules/<id>.json（若需自然生成）
     → BP loot_tables/entities/<id>.json（若需掉落）
   ```
6. **逐环写入**并在每一步核对标识符字符串完全一致（大小写、命名空间、下划线）。
7. **静态校验**：JSON syntax → schema → **引用链完整性**（每个引用的文件必须存在）→ UUID。
8. **B 层运行时**：实体注册 + 生成 + 基础行为。
9. **C 层视觉**：模型/贴图/动画由客户端证明 → `MANUAL_GATE`。

## 3. 工具调用顺序

```bash
# 1) schema
ssh gz "cat /opt/bedrock-flow/sources/official/bedrock-schemas/catalog.json"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/metadata/json_schemas/server/entity"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/metadata/json_schemas/client"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/metadata/json_schemas/client_server"

# 2) 官方样例（整套引用链）
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/entities | head -20"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/resource_pack/entity | head -20"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/resource_pack/{models,animations,animation_controllers,render_controllers}"

# 3) 引用链自检（每个被引用的文件名都必须真实存在）
ssh gz "cd /opt/bedrock-flow/projects/<id> && grep -rho '\"[a-z_]*:[a-z_/.]*\"' resource_pack/entity/ | sort -u"

# 4) 静态校验
bedrock-flow validate

# 5) 运行时 + 测试
bedrock-flow bds start && bedrock-flow test
```

- "生成实体 / 查询实体"的运行时手段**必须按目标版本实测确认**（控制台命令或脚本 API），不得凭记忆写。
- 纹理与模型路径大小写敏感；`textures/entity/...` 必须在 `textures_list.json`（若项目约定）与实体文件中一致。

## 4. 禁止做什么

1. 禁止凭记忆写实体组件、行为、动画控制器 JSON。
2. 禁止只写 BP 侧而漏掉 RP 客户端实体（实体不会显示）。
3. 禁止**悬空引用**：geometry / texture / animation / render_controller / loot_table 任一不存在即 FAIL。
4. 禁止客户端与服务端 identifier 不一致。
5. 禁止自行发明 schema 替代官方 schema。
6. 禁止混用 preview 实体特性到 stable 目标。
7. 禁止修改 vanilla 核心包来实现自定义实体。
8. 禁止只做静态校验就宣布完成；禁止用"BDS 能启动"证明实体正确。
9. 禁止伪造视觉 PASS。
10. 禁止整项目重写来修一个实体错误。

## 5. 输出格式

```
projects/<project_id>/
├── behavior_pack/
│   ├── manifest.json
│   ├── entities/<id>.json
│   ├── spawn_rules/<id>.json              # 若需自然生成
│   └── loot_tables/entities/<id>.json     # 若需掉落
└── resource_pack/
    ├── manifest.json
    ├── entity/<id>.entity.json
    ├── models/entity/<geo>.geo.json
    ├── textures/entity/<tex>.png
    ├── render_controllers/<rc>.json
    ├── animations/<anim>.animation.json
    ├── animation_controllers/<ac>.json
    └── texts/<lang>.lang                  # 实体显示名
```

实体级证据条目（追加到项目 `reports/`）：

```yaml
feature: <feature_id>
layer: Entity
identifier: "<namespace:name>"
reference_chain:
  - from: "resource_pack/entity/<id>.entity.json"
    to: "models/entity/<geo>.geo.json"
    verified: true
  # 每条引用一行
tests:
  - id: entity_exists          # B 层：已注册
    layer: B
  - id: entity_spawn_behavior  # B 层：生成 + 基础行为
    layer: B
  - id: entity_visual          # C 层：模型/贴图/动画
    layer: C
    gate: MANUAL_GATE
```

## 6. 验证规则（怎么算 PASS）

**A 层（静态，自动）**
- [ ] 所有 JSON 语法合法、UTF-8、目录结构符合官方样例惯例。
- [ ] BP 实体与 RP 客户端实体均通过对应官方 schema 校验。
- [ ] **引用链每一环的目标文件真实存在**（geometry / texture / animation / animation_controller / render_controller / loot_table / spawn_rules）。
- [ ] BP 与 RP 的 identifier 完全一致。
- [ ] UUID 合法且唯一。

**B 层（BDS 运行时，自动）**
- [ ] 服务器日志无实体加载/组件解析错误。
- [ ] 实体可被生成（手段以目标版本实测为准）。
- [ ] 基础行为（移动/交互/掉落，按 Design Contract 的 acceptance）符合预期，且有 `BF_TEST_RESULT {...}` 证据行。

**C 层（视觉，人工闸门）**
- [ ] 模型、贴图、动画、渲染控制器效果由客户端验证；无客户端证据时为 `MANUAL_GATE`。

任一自动层 FAIL → `FAIL`，转 `bedrock-debug`。

## 7. 转交

- 组件/动画语法依据 → `bedrock-research`
- 版本与 `format_version` 冲突 → `bedrock-version`
- 脚本行为 → `bedrock-script`
- 校验/构建 → `bedrock-build`；运行时 → `bedrock-bds`；测试 → `bedrock-test`
- 失败定位 → `bedrock-debug`

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 02 | `experience/mod-experience/02-踩坑大全-产品侧.md` |
| 教材 07 | `experience/mod-experience/07-运行时引擎.md` |
| 错误 | `reports/errors/ERR-ZE-0002-system-pack-no-entity-override.md` |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
