---
name: bedrock-experience
description: 开工前检索历史经验、案例与错误库的流程。当开始任何 Bedrock 任务前、需要确认某做法是否经过验证、或遇到疑似"以前见过"的现象时使用。定义"先查后做"的顺序、案例匹配方法、以及新经验的沉淀格式。
whenToUse: 任何 bedrock 任务开始时；用户说「以前做过类似的」「这个之前不是踩过坑吗」；或需要确认某个做法/版本组合是否有已验证依据时。
---

# bedrock-experience — 经验检索与沉淀

本技能**只定义经验闭环流程**，不承载 Minecraft 知识。

## 0. 三个事实源

| 源 | 路径 | 内容 |
|---|---|---|
| 教材 | `/opt/bedrock-flow/experience/mod-experience/` | 13 章，按主题分（产品/环境/测试侧、运行时、方法论…） |
| 案例库 | `/opt/bedrock-flow/cases/` | 每案含 `problem.md` / `solution.md` / `VERSION.yaml` / `TESTS.yaml` / `RESULT.json` |
| 错误库 | `/opt/bedrock-flow/reports/errors/` | 23 条（`ERR-0001`~`0013` + `ERR-ZE-0001`~`0010`）+ `registry/error-signatures.json` |

## 1. 什么时候使用

- **任何任务开工前**（强制）。
- 遇到 FAIL 且怀疑"以前见过"。
- 需要确认某版本组合是否已验证。

## 2. 检查顺序（不可跳）

```
1. 读教材索引 README.md → 定位相关章节
2. 读相关章节全文
3. 列 cases/ → 按 problem.md 匹配历史案例
4. 命中案例 → 读 solution.md + TESTS.yaml 看验证状态
5. 查 reports/errors/ 与 error-signatures.json → 看是否有已知错误签名
6. 汇总结论：哪些【已验证】可复用 / 哪些【未验证】需重验 / 哪些是【新问题】
7. 把结论写进实施计划的「前提与依据」段
```

## 3. 工具调用顺序

```bash
# 1) 教材索引
ssh gz "cat /opt/bedrock-flow/experience/mod-experience/README.md"
# 2) 案例列表
ssh gz "ls /opt/bedrock-flow/cases/"
# 3) 匹配案例
ssh gz "grep -rl '<关键词>' /opt/bedrock-flow/cases/*/problem.md"
# 4) 错误签名
ssh gz "grep -i '<错误关键词>' /opt/bedrock-flow/registry/error-signatures.json"
# 5) 版本登记
ssh gz "cat /opt/bedrock-flow/registry/compatibility.json"
```

## 4. 禁止做什么

1. 禁止**跳过检索直接动手**。
2. 禁止因"看起来像"就套用历史案例（§31 末句）。
3. 禁止把【未验证】的旧解当成【已验证】复用 —— 版本不同必须重验。
4. 禁止只读案例标题不读 `solution.md` 与 `TESTS.yaml`。
5. 禁止检索完不写结论 —— 必须留下「前提与依据」。

## 5. 输出格式

在实施计划中插入：

```markdown
## 前提与依据
### 已验证（可直接复用）
- <结论> ← cases/<id>/solution.md，TESTS.yaml 状态 PASS，适用版本 <v>
### 未验证（需重新验证）
- <结论> ← 仅静态验证，runtime_verified: false
### 新问题（无历史）
- <描述> → 完成后按 cases/ 结构沉淀
```

## 6. 验证规则（怎么算 PASS）

- [ ] 教材相关章节已读（能引用章节号）。
- [ ] `cases/` 已列，匹配结果明确（命中 / 未命中）。
- [ ] 命中案例已读 `solution.md` + `TESTS.yaml`。
- [ ] 错误库已查（含 `error-signatures.json`）。
- [ ] 结论按【已验证/未验证/新问题】三分类写出。
- [ ] 复用项已核对 `compatibility.json` 的适用版本。

## 7. 转交

| 情形 | 转交 |
|---|---|
| 命中案例但需最小补丁 | `bedrock-debug` |
| 涉及版本冲突 | `bedrock-version` |
| 涉及 API 是否存在 | `bedrock-research` |
| 需新建工程落地 | `bedrock-project` |
