---
name: bedrock-project
description: Bedrock Addon 工程骨架、Design Contract 与 git 版本管理流程（任务书 §26 §37 §40 §41）。当需要新建一个 addon 项目、补齐 design.yaml、建立 main/dev 分支与基础提交、或整理项目目录结构时使用。
whenToUse: 用户说「新建一个工程/项目」「建个 PoC」「这个项目结构不对」「补一下 Design Contract」，或 bedrock-engineer 在证据齐备后需要落地工程骨架时。
---

# bedrock-project — 工程骨架 / Design Contract / Git

本技能**只定义目录结构、契约字段与提交流程**，不写任何 Minecraft 内容。

## 0. 现状事实（只读引用）

- 工程根：`/opt/bedrock-flow/`（广州，`ssh gz` 免密），已是 git repo，`branch main`，初始提交 `bcdf96d bootstrap: 工程底座建立 (Phase 0-9)`。
- 项目目录：`/opt/bedrock-flow/projects/`（**已有 11 个项目**：example-project 系列、example-food、example-loot、zombie-evolution、example-block-smoke 等）。
- 测试世界：`/opt/bedrock-flow/test-worlds/`（当前含 `bf-smoke`）；**绝不使用用户世界**。
- 报告目录：`/opt/bedrock-flow/reports/`（含 `errors/`）。
- 产物目录：`/opt/bedrock-flow/artifacts/`。
- 案例目录：`/opt/bedrock-flow/cases/`。
- 版本前提来自 `registry/runtime.json` 与 `registry/compatibility.json`。

## 1. 什么时候使用

- 用户说「新建项目 / 建 PoC / 从零做一个 addon」。
- 已有项目缺少 `design.yaml`（Design Contract）。
- 需要为项目建立 git 分支与基础提交节点。
- 需要新增测试目录结构（`tests/smoke|runtime|expected`）。

**不适用**：往项目里写方块/物品/实体/脚本内容 → 对应产物技能。

## 2. 检查顺序

1. **确认前置**：`registry/compatibility.json` 已解析出稳定三元组；未解析 → 先转 `bedrock-version`。
2. **确认证据**：`bedrock-research` 的证据包已存在。
3. **定 project_id**：小写字母/数字/连字符（如 `example-block-smoke`）；不得与 `projects/` 下已有目录重名。
4. **创建目录骨架**（见 §5）。
5. **写 `design.yaml`**（Design Contract，§37）——**这是实现前的强制产物**。
6. **git 初始化**：项目内 `main` + `dev`；工程根仓库保持既有约定。
7. **建立基础提交节点**（§40）：`initial-project` → 后续由 build/test/package 阶段追加 `build-pass`、`bds-load-pass`、`test-pass`、`package-pass`。
8. **产出结构自检报告**。

## 3. 工具调用顺序

```bash
# 前置
ssh gz "cat /opt/bedrock-flow/registry/compatibility.json"
ssh gz "ls /opt/bedrock-flow/projects/"

# 创建骨架（在 /opt/bedrock-flow/projects/<id>/ 下）
ssh gz "mkdir -p /opt/bedrock-flow/projects/<id>/{behavior_pack,resource_pack,tests/smoke,tests/runtime,tests/expected,reports}"

# 写入 design.yaml（本地写好再 scp，避免 heredoc 引号问题）
scp design.yaml gz:/opt/bedrock-flow/projects/<id>/design.yaml

# git
ssh gz "cd /opt/bedrock-flow && git status --short && git add projects/<id> && git commit -m 'initial-project: <id>'"
ssh gz "cd /opt/bedrock-flow/projects/<id> && git init -q && git checkout -q -b main && git add -A && git commit -q -m 'initial-project' && git checkout -q -b dev"
```

- 若工程根 git 存在未提交的他人改动 → **只 `git add` 本项目路径**，禁止 `git add -A` 或 `git commit -a` 扫入无关改动。
- 禁止 `git push --force`、禁止改写历史。

## 4. 禁止做什么

1. 禁止**跳过 `design.yaml` 直接生成成品文件**（§37 §38）。
2. 禁止把用户世界当测试世界（铁律第 7 条）；项目只引用 `/opt/bedrock-flow/test-worlds/`。
3. 禁止在 `design.yaml` 里手写版本号而不注明来源（必须与 `registry/` 一致）。
4. 禁止在项目目录内写入凭据 / token / 私钥。
5. 禁止 `git add -A` 扫入 `projects/` 之外的改动。
6. 禁止删除或覆盖已有项目的文件来"重建"。
7. 禁止使用浮动依赖（`^` / `~` / `latest`）写 `package.json`（§23）。
8. 禁止创建与 `registry` 冲突的第二份版本事实（版本只有一个权威源）。

## 5. 输出格式

### 目录骨架（§26）

```
projects/<project_id>/
├── design.yaml
├── behavior_pack/
├── resource_pack/
├── tests/
│   ├── smoke/
│   ├── runtime/
│   └── expected/
├── reports/
└── package.json
```

### `design.yaml`（Design Contract，§37 字段齐全）

```yaml
feature:
  id: <feature_id>
goal: >
  <玩家做什么 → 发生什么 → 如何判定成功>
inputs:
  - <触发输入>
outputs:
  - <可观察输出>
files:
  bp:
    - <相对路径>
  rp:
    - <相对路径>
  script:
    - <相对路径>
dependencies:
  - <固定版本依赖，非浮动>
runtime:
  minecraft: <读 registry/runtime.json>
  channel: stable
  script_api:
    "@minecraft/server": <读 registry/api.json 的 stable_max>
    "@minecraft/server-ui": <同上，若用到>
compatibility:
  # bedrock-research 的证据包
tests:
  - id: <test_id>
    layer: A | B | C
    expect: <判定条件>
acceptance:
  - <可机械判定的验收条件>
```

### 基础提交节点（§40）

`initial-project` → `build-pass` → `bds-load-pass` → `test-pass` → `package-pass`。每次自动修复尽量形成可回滚 commit。

## 6. 验证规则（怎么算 PASS）

- [ ] 目录骨架与 §5 完全一致（不缺 `tests/expected`）。
- [ ] `design.yaml` 含 `feature / goal / inputs / outputs / files / dependencies / runtime / tests / acceptance` 全部字段，无空值。
- [ ] `runtime.minecraft` 与 `registry/runtime.json` **逐字符一致**；`script_api` 值不超过 `registry/api.json` 的 `stable_max`。
- [ ] `dependencies` 中无 `^` / `~` / `latest` / 空版本。
- [ ] git 分支 `main` 与 `dev` 均存在，且 `initial-project` 提交已落地、工作区干净。
- [ ] 项目目录内不含凭据类文件。
- [ ] 未触碰用户世界与无关服务。

任一项不满足 → `FAIL`。

## 7. 转交

- 版本前提缺失 → `bedrock-version`
- 证据缺失 → `bedrock-research`
- 骨架就绪 → `bedrock-block` / `bedrock-item` / `bedrock-entity` / `bedrock-script`

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 12 | `experience/mod-experience/12-可复用模板.md` |
| 教材 10 | `experience/mod-experience/10-交付检查清单.md` |
| 案例 | `cases/example-block-smoke-custom-block-smoke/`（工程骨架范例） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
