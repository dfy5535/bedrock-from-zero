---
name: bedrock-item
description: 自定义物品（Behavior Pack item + Resource Pack 图标/贴图）的实现流程与校验规则。当需要在 addon 中新增/修改自定义物品、物品组件、物品 format_version、item_texture.json 引用或物品 Schema 校验时使用。
whenToUse: 用户说「加一个自定义物品/装备/食物」「物品图标不显示」「item 的 format_version 写多少」，或 Design Contract 的产物层含 Item 时。
---

# bedrock-item — 自定义物品产物层

本技能**只定义流程**。物品组件名、字段、`format_version` 一律从官方 schema 与官方样例现查，**禁止凭记忆写 JSON**。

## 0. 权威事实源

| 用途 | 位置 |
|---|---|
| 官方 item JSON Schema | `/opt/bedrock-flow/sources/official/bedrock-schemas/schemas/`（先读 `catalog.json` 定位） |
| 官方 BP 物品样例 | `/opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/items/` |
| 官方样例内 schema 副本 | `/opt/bedrock-flow/sources/official/bedrock-samples/metadata/json_schemas/server/item/` |
| 观测到的 item `format_version` | `registry/runtime.json` → `pack_formats.observed_file_format_versions.item` |
| 校验工具 | `/opt/bedrock-flow/tools/validate/` |

**注意**：registry 中 item 的观测值分布较广（多个历史版本并存），**不得**据此随手挑一个；必须在官方样例中找**同类物品**（如普通物品 / 可食用 / 装备）并采用其实际取值。

## 1. 什么时候使用

- 用户要求新增/修改自定义物品（含食物、工具、装备类）。
- 物品在 BDS 中加载失败、图标缺失、组件不生效。
- 需要写 `items/*.json`、物品图标 PNG、`item_texture.json` 引用。
- Design Contract 的产物层含 Item。

**不适用**：方块（`bedrock-block`）；物品的脚本逻辑（`bedrock-script`，但仍需本技能定义物品本体）。

## 2. 检查顺序

1. **前置**：`projects/<id>/design.yaml` 存在且 Item 层已列入；版本三元组已解析。
2. **查 schema**：定位官方 item schema，读 `format_version` 约束与可用组件枚举。
3. **查样例**：在官方 `behavior_pack/items/` 找同类型物品，读其结构与 `format_version`。
4. **定标识符**：命名空间 + 名称，检查与 vanilla / 已用标识符不冲突。
5. **定组件集**：逐个组件在 schema 中确认；无 schema 依据的组件不得写入。
6. **写 BP 文件**：`behavior_pack/items/<name>.json`。
7. **写 RP 资源**：图标 PNG + `textures/item_texture.json` 条目（键名与物品标识符一致）+ `textures/textures_list.json`（若项目约定）。
8. **接线**：BP/RP manifest 声明与路径引用一致。
9. **静态校验** → **B 层运行时** → **C 层视觉闸门**。

## 3. 工具调用顺序

```bash
# 1) schema 定位
ssh gz "cat /opt/bedrock-flow/sources/official/bedrock-schemas/catalog.json"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/metadata/json_schemas/server/item/"

# 2) 官方样例
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/items/ | head -30"
ssh gz "grep -h 'format_version' /opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/items/*.json | sort | uniq -c"

# 3) 观测值（辅助）
ssh gz "python3 -c \"import json;d=json.load(open('/opt/bedrock-flow/registry/runtime.json'));print(d['pack_formats']['observed_file_format_versions']['item'])\""

# 4) 静态校验
bedrock-flow validate

# 5) 运行时 + 测试
bedrock-flow bds start && bedrock-flow test
```

- 需要"给予物品 / 检查物品存在"的运行时手段（控制台命令或脚本 API）**必须按目标版本实际支持情况确认**，不得凭记忆写命令。查证入口：`bedrock-research`。

## 4. 禁止做什么

1. 禁止凭记忆写物品 JSON、组件名、字段、`format_version`。
2. 禁止自行发明 schema 替代官方 schema（§22）。
3. 禁止混用 preview 物品特性到 stable 目标。
4. 禁止引用不存在的图标/贴图路径；禁止大小写不符。
5. 禁止 UUID 重复或格式非法。
6. 禁止修改 vanilla 核心包来实现自定义物品。
7. 禁止只做静态校验就宣布完成。
8. 禁止用"BDS 能启动"证明物品正确。
9. 禁止伪造视觉 PASS（图标外观属 C 层 `MANUAL_GATE`）。
10. 禁止整项目重写来修一个物品错误。

## 5. 输出格式

```
projects/<project_id>/
├── behavior_pack/
│   ├── manifest.json
│   └── items/<name>.json                 # format_version + minecraft:item
└── resource_pack/
    ├── manifest.json
    ├── textures/
    │   ├── items/<name>.png
    │   ├── item_texture.json             # 图标条目，键名 = 物品标识符
    │   └── textures_list.json
    └── texts/<lang>.lang                 # 显示名
```

物品级证据条目（追加到项目 `reports/`）：

```yaml
feature: <feature_id>
layer: Item
files: [ <bp/rp 相对路径> ]
identifier: "<namespace:name>"
format_version: "<实测于官方样例>"
components:
  - name: "<组件>"
    schema_ref: "<schema 相对路径>"
    sample_ref: "<官方样例相对路径>"
tests:
  - id: item_exists          # B 层
    layer: B
  - id: item_behavior        # B 层：使用/装备触发预期行为
    layer: B
  - id: item_icon_visual     # C 层
    layer: C
    gate: MANUAL_GATE
```

## 6. 验证规则（怎么算 PASS）

**A 层（静态，自动）**
- [ ] JSON 语法、UTF-8、目录结构符合官方样例惯例。
- [ ] 通过官方 item schema 校验。
- [ ] 图标与贴图路径真实存在；`item_texture.json` 键名与物品标识符一致。
- [ ] UUID 合法且唯一。

**B 层（BDS 运行时，自动）**
- [ ] 服务器日志无物品加载错误。
- [ ] 物品已注册（给予/查询手段以目标版本实测为准）。
- [ ] 预期行为触发，且有 `BF_TEST_RESULT {"id":"...","status":"PASS",...}` 证据行。

**C 层（视觉，人工闸门）**
- [ ] 图标/模型外观由客户端验证；无客户端证据时状态为 `MANUAL_GATE`。

任一自动层 FAIL → `FAIL`，转 `bedrock-debug`。

## 7. 转交

- 组件/字段依据 → `bedrock-research`
- 版本冲突 → `bedrock-version`
- 校验/构建 → `bedrock-build`；运行时 → `bedrock-bds`；测试 → `bedrock-test`
- 失败定位 → `bedrock-debug`

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 02 | `experience/mod-experience/02-踩坑大全-产品侧.md` |
| 错误 | `reports/errors/ERR-ZE-0009-item-texture-array.md` |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
