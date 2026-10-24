---
name: bedrock-debug
description: 从 FAIL 到最小补丁的调试闭环流程（任务书 §29 §30 §31）。当出现任何校验失败、BDS 加载失败、脚本报错、测试 FAIL，需要捕获证据、定位根因、做最小补丁并复测时使用。
whenToUse: 用户说「报错了/跑不起来/加载失败/测试挂了/日志里有 ERROR」，或 bedrock-test 产出了 FAIL、bedrock-build 校验不通过时。
---

# bedrock-debug — FAIL → 证据 → 定位 → 根因 → 最小补丁 → 复测

本技能**只定义调试闭环**。根因分析必须基于原始证据，不得靠"历史案例看起来像"就套用旧解（§31 末句明确禁止）。

## 0. 权威事实源

| 用途 | 位置 |
|---|---|
| 错误报告目录 | `/opt/bedrock-flow/reports/errors/`（**已有 23 条**：`ERR-0001`~`ERR-0013` + `ERR-ZE-0001`~`ERR-ZE-0010`；速查表见 `11-错误索引.md`） |
| 工程记忆/案例库 | `/opt/bedrock-flow/cases/`（§31 结构） |
| BDS 日志 | `/opt/bedrock-flow/logs/`（`bedrock-flow log <n>` 读取） |
| 测试证据行 | 日志中的 `BF_TEST_RESULT {...}`（§27） |
| 官方 schema | `/opt/bedrock-flow/sources/official/bedrock-schemas/schemas/` |
| 官方样例（正确写法对照） | `/opt/bedrock-flow/sources/official/bedrock-samples/` |
| 版本前提 | `/opt/bedrock-flow/registry/{runtime,compatibility,api}.json` |

## 1. 什么时候使用

- Validate 任一层 FAIL。
- BDS 日志出现 addon 加载错误、脚本错误、组件解析错误。
- `BF_TEST_RESULT` 出现 `"status":"FAIL"`。
- 打包/构建失败。
- 用户描述一个失败现象但根因未知。

**不适用**：正常流程编排（`bedrock-engineer`）；单纯环境起停问题（先 `bedrock-bds`）。

## 2. 检查顺序（§29 固定顺序，不可跳步）

```
FAIL
 ↓ 1. capture evidence      —— 原样保存原始错误，不改写、不省略
 ↓ 2. identify affected file —— 定位到具体文件（+ 行号，若可得）
 ↓ 3. root cause            —— 判定错误类型与根本原因
 ↓ 4. minimal patch         —— 只改根因，一次尽量只改一个根因
 ↓ 5. validate              —— 重跑静态校验
 ↓ 6. build                 —— 重新构建
 ↓ 7. restart / reset       —— 重启 BDS / 重置测试世界
 ↓ 8. same test             —— 跑**同一个**测试（不得换用例）
```

补充要求：
- 若第 3 步无法确定根因 → 允许增加**只读诊断**（更多日志、schema 比对、官方样例对照），但**不得**先改代码试探。
- 若修复涉及版本/通道判断 → 转 `bedrock-version`，不得就地改版本号蒙混。
- 若修复涉及"某 API 是否存在" → 转 `bedrock-research` 取证。

## 3. 工具调用顺序

```bash
# 1) 捕获证据（原样，不改写）
ssh gz "bedrock-flow log 500" > /tmp/bf-fail-<n>.log
ssh gz "grep -n 'ERROR\\|error\\|FAIL\\|BF_TEST_RESULT' /tmp/bf-fail-<n>.log"

# 2) 定位受影响文件
ssh gz "grep -rn '<错误中出现的标识符>' /opt/bedrock-flow/projects/<id>/"

# 3) 根因取证：与官方 schema / 官方样例对照
ssh gz "cat /opt/bedrock-flow/sources/official/bedrock-schemas/catalog.json"
ssh gz "ls /opt/bedrock-flow/sources/official/bedrock-samples/behavior_pack/blocks/"

# 4) 最小补丁（只改必要行）
#    使用 edit 工具做精确替换；禁止整文件重写

# 5) 复测链（严格同序）
bedrock-flow validate
bedrock-flow build
ssh gz "bedrock-flow restart"      # 或 reset-world + start
bedrock-flow test              # 同一个用例

# 6) 落盘错误记录
#    reports/errors/ERR-XXXX.yaml（见 §5）
```

- 若 `bedrock-flow validate|build|test` 不存在 → 用等价已实测手段（`tools/validate`、项目构建脚本、`bedrock-flow` + 日志 grep），并记 `UNKNOWN`。

## 4. 禁止做什么

1. **禁止整项目重写**（§29 明文禁止）。
2. 禁止一次修多个根因（§29：一次错误尽量只改一个根因）。
3. 禁止未取证就改代码"试试看"。
4. 禁止为了通过而放宽测试、删用例、改期望值、或修改测试世界以外的东西。
5. 禁止篡改日志或事后补写 `BF_TEST_RESULT`。
6. 禁止因历史案例成功就直接复制旧补丁（§31）；必须**先验证当前版本是否相同**。
7. 禁止删除失败现场；失败状态必须保留以便复现（铁律第 11 条）。
8. 禁止修改 BDS 二进制 / vanilla 核心包来"绕过"错误。
9. 禁止手删不明目录（先隔离，后处理）。
10. 禁止在错误报告中写入凭据或无关敏感信息。
11. 禁止跳过复测直接宣布修复（必须重跑**同一个**测试）。

## 5. 输出格式

### 错误报告（§30）`/opt/bedrock-flow/reports/errors/ERR-XXXX.yaml`

```yaml
id: ERR-0001
time: <ISO8601 UTC>
runtime:
  minecraft: <registry/runtime.json>
  bds: <BDS 自报版本>
  script_api: <实际锁定版本>
project: <project_id>
test: <用例 id>

error:
  raw: |
    <原始错误文本，原样粘贴，不修饰>

location:
  file: <相对路径>
  line: <行号或 null>

diagnosis:
  type: <schema|reference|version|script|runtime|packaging|...>
  root_cause: <一句话根因>

patch:
  changed_files:
    - <相对路径>
  summary: <改了什么、为什么>

verification:
  validate: PASS
  build: PASS
  test: PASS

confidence: HIGH | MEDIUM | LOW
```

### 工程记忆案例（§31，成功修复后）`/opt/bedrock-flow/cases/<case_id>/`

```
case/
├── problem.md
├── solution.md
├── patch.diff
├── VERSION.yaml
├── TESTS.yaml
├── RESULT.json
└── SOURCE_MANIFEST.json
```

未来复用流程（§31）：

```
当前错误 → 错误签名 → 过去成功案例 → 参考解决方法 → 验证当前版本是否相同 → 尝试 patch
```

**注意**：`VERSION.yaml` 必须记录该案例适用的版本；版本不同则**不得直接套用**。

### git

每次修复尽量形成**可回滚** commit（§40），消息含错误编号，例如 `fix(ERR-0001): <一句话>`。

## 6. 验证规则（怎么算 PASS）

- [ ] 原始错误已**原样**保存（有文件路径或日志片段可复核）。
- [ ] 受影响文件已精确定位（文件级；行号可得则必须给出）。
- [ ] 根因陈述可被证据支持，且**不是**"改了就好了"式描述。
- [ ] 补丁为**最小**改动：`changed_files` 中每一项都能对应到同一根因。
- [ ] 复测链完整执行：validate → build → restart/reset → **同一个** test。
- [ ] 复测证据为 `BF_TEST_RESULT {"id":"<原用例 id>","status":"PASS",...}`。
- [ ] `reports/errors/ERR-XXXX.yaml` 已落盘，字段齐全，`confidence` 已标注。
- [ ] 失败现场保留（日志、原文件版本或 diff）。
- [ ] 若根因涉及版本，已附 `bedrock-version` 的仲裁结论。
- [ ] 修复已提交为可回滚 commit。

任一项不满足 → 修复**未完成**，不得标记 PASS。

## 7. 转交

- 根因是版本/通道 → `bedrock-version`
- 根因是"某 API/组件无官方依据" → `bedrock-research`
- 根因是官方源缺失/过期 → `bedrock-sources`
- 根因是环境/起停 → `bedrock-bds`
- 修复完成后 → 回到 `bedrock-test` 复测 → `bedrock-package`

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 11 | `experience/mod-experience/11-错误索引.md`（速查表） |
| 错误库 | `reports/errors/`（23 条：ERR-0001~0013 + ERR-ZE-0001~0010） |
| 签名库 | `registry/error-signatures.json` |
| 案例 | `cases/`（problem.md + solution.md） |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
