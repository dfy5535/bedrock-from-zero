---
name: bedrock-sources
description: 官方事实源的获取、校验与 SOURCE_MANIFEST 维护流程（任务书 §8 §10 §11）。当需要引入新的官方源、校验已下载源的完整性、更新源 revision、或把源从日本节点搬运到广州工程时使用。
whenToUse: 用户要求「拉官方 samples/schema」「更新官方源」「校验源是否完整」「SOURCE_MANIFEST 里的 revision 过期了」，或 bedrock-research 报告源缺失时。
---

# bedrock-sources — 官方源获取与清单维护

本技能**只定义获取与登记流程**。源的用途分类与 stable/preview 判定转 `bedrock-version`。

## 0. 现状事实（只读引用）

- 工程根：`/opt/bedrock-flow/`（广州；`ssh gz` 免密；`root:bfdev` 2775 setgid，`ubuntu` 在 `bfdev` 组可写）。
- 源清单（权威）：`/opt/bedrock-flow/sources/SOURCE_MANIFEST.json`。
- 官方源目录：`/opt/bedrock-flow/sources/official/`（已含 `bedrock-samples`、`bedrock-schemas`、`minecraft-samples`、`minecraft-scripting-samples`）。
- 归档原件：`/opt/bedrock-flow/sources/_archives/`（tarball + `SHA256SUMS`）。
- 社区源目录：`/opt/bedrock-flow/sources/community/`（1 项）。
- **出网路径**：广州直连 `www.minecraft.net` **不通**；`github.com` 通但大仓库约 20KB/s。正确做法是**日本节点下载 → `scp` 到广州**（已实测 BDS 94.9MB 在日本 2.8s 完成）。
- 广州 `127.0.0.1:1081` 为 gost HTTP 代理（凭据在 `/etc/gost.env`，需 sudo；**严禁回显凭据**）；小请求可通，大文件会截断。

## 1. 什么时候使用

- 需要引入一个**新的官方源**（如官方文档仓库、新版本 samples）。
- `SOURCE_MANIFEST.json` 中某源的 revision 与目标运行时不再匹配。
- 需要校验已有源是否被截断/损坏。
- `bedrock-research` 报"证据源缺失"。

**不适用**：判断该用哪个版本 → `bedrock-version`；查 API 是否存在 → `bedrock-research`。

## 2. 检查顺序

1. **读现状**：`SOURCE_MANIFEST.json` + `sources/_archives/SHA256SUMS` + `ls sources/official/`。
2. **判定是否需要新源**：若已有源能满足证据需求，**不新增**（§11：不允许全 GitHub 爬虫）。
3. **分类**：`official` / `official-sample-collection` / `community`。未分类的源不得落地（§9）。
4. **确定 revision**：优先 tag；无 tag 用**精确 commit SHA**（禁止浮动分支作生产源）。
5. **下载**：在日本节点完成（网络条件好），并当场计算 SHA256。
6. **搬运**：`scp` 到广州 `/opt/bedrock-flow/sources/_archives/`。
7. **双侧校验**：日本侧与广州侧 SHA256 必须一致，不一致即视为传输截断。
8. **解压落地**：解到 `sources/<分类>/<name>/`，保留 LICENSE。
9. **登记**：增量更新 `SOURCE_MANIFEST.json` 与 `SHA256SUMS`。
10. **复核**：重新读取清单，确认 revision、sha256、local_path 三者自洽。

## 3. 工具调用顺序

```bash
# 1) 现状
ssh gz "cat /opt/bedrock-flow/sources/SOURCE_MANIFEST.json"
ssh gz "ls -la /opt/bedrock-flow/sources/official/ /opt/bedrock-flow/sources/_archives/"
ssh gz "cat /opt/bedrock-flow/sources/_archives/SHA256SUMS"

# 2) 日本节点下载（按精确 tag/SHA 固定）
#    下载到 /workspace/bf-bootstrap/downloads/ 或临时目录
sha256sum <archive>

# 3) 搬运到广州
scp <archive> gz:/opt/bedrock-flow/sources/_archives/

# 4) 广州侧校验（必须与日本侧一致）
ssh gz "sha256sum /opt/bedrock-flow/sources/_archives/<archive>"

# 5) 解压落地
ssh gz "tar -xzf /opt/bedrock-flow/sources/_archives/<archive> -C /opt/bedrock-flow/sources/<分类>/ && mv ... <name>"

# 6) 登记（增量修改，不整文件重写）
ssh gz "cat /opt/bedrock-flow/sources/SOURCE_MANIFEST.json"

# 7) 统一 CLI（若存在）
bedrock-flow source sync
```

- 若 `bedrock-flow source sync` 不存在 → 记 `UNKNOWN`，按上述手工步骤执行，**不得发明参数**。
- 目录权限：新建目录应继承 `2775` setgid 与 `root:bfdev`；若属主异常，先确认再修正，**不得 `chown -R` 到无关路径**。

## 4. 禁止做什么

1. 禁止**全 GitHub 爬虫**式收集（§11）；每引入一个源必须有明确用途。
2. 禁止引入未分类的第三方仓库（§9 第 15 条铁律）。
3. 禁止使用浮动分支（`main` / `master` / `HEAD`）作为**生产**事实源；必须固定到精确 commit SHA。
4. 禁止使用来路不明的第三方 BDS 压缩包（§16）。
5. 禁止跳过 SHA256 校验就落地。
6. 禁止在日志/文件中回显 `/etc/gost.env` 或任何凭据。
7. 禁止把 preview 源放进 stable 用途目录而不标注通道。
8. 禁止删除 `sources/_archives/` 中的归档原件（它们是可追溯性的基础）。
9. 禁止手工删除不明目录（§6.7 / 铁律）。

## 5. 输出格式

`SOURCE_MANIFEST.json` 中每个源一条记录（保持既有 schema，增量更新）：

```json
{
  "name": "<repo 名>",
  "upstream": "<https URL>",
  "revision": "<commit SHA>",
  "revision_type": "tag | commit",
  "requested_ref": "<tag 或 ref>",
  "channel": "stable | preview | official-sample-collection",
  "license": "<SPDX>",
  "license_file": "<相对路径>",
  "retrieved_at": "<ISO8601 UTC>",
  "archive_file": "<tarball 文件名>",
  "archive_sha256": "<64 hex>",
  "purpose": "<为什么需要它>",
  "minecraft_target": "<目标运行时>",
  "script_api_target": null,
  "verified": false,
  "local_path": "/opt/bedrock-flow/sources/official/<name>",
  "notes": ["<关键限制，例如 main 为 preview 故固定到该 SHA>"]
}
```

并在 `sources/_archives/SHA256SUMS` 追加一行 `<sha256>  <archive>`。

## 6. 验证规则（怎么算 PASS）

- [ ] 日本侧与广州侧 SHA256 **逐字节一致**。
- [ ] 归档文件大小非 0 且与源站 Content-Length（若可得）一致（防代理截断）。
- [ ] `revision` 为精确 SHA（40 hex），`revision_type` 与之一致。
- [ ] `local_path` 实际存在，且解压后的目录结构完整（含 LICENSE 与预期顶层目录）。
- [ ] `SOURCE_MANIFEST.json` 与 `SHA256SUMS` 均已更新，且 `name` 无重复。
- [ ] `channel` 已标注；stable 用途目录中**不含** preview 源。
- [ ] `purpose` 非空 —— 无用途的源视为违规引入。

任一项不满足 → `FAIL`；已落地的可疑源应移入隔离区而非直接删除。

## 7. 转交

- 通道/版本判定 → `bedrock-version`
- 源就绪后 → `bedrock-research`（用新源取证据）

---

## 经验回查（开工前必读）

**动手前先查历史经验 —— 这里有踩过的坑、验证过的做法、可复用的模板。**

教材目录：`/opt/bedrock-flow/experience/mod-experience/`（13 章）｜案例库：`/opt/bedrock-flow/cases/`｜错误库：`/opt/bedrock-flow/reports/errors/`

| 与本技能相关 | 位置 |
|---|---|
| 教材 03 | `experience/mod-experience/03-踩坑大全-环境侧.md` |

**四条铁律**：
1. **先读后做** —— 相关章节与案例的 `problem.md` / `solution.md` 读完再动手。
2. **核对版本** —— 复用旧解前必须查 `registry/compatibility.json`；版本不同则重新验证，不得直接照搬。
3. **禁止类比套用** —— 不得因"看起来像"就套用历史案例（AGENTS.md 第 19 条 / §31 末句）。
4. **完成后沉淀** —— 若产生新经验，按 `cases/` 既有结构落一条案例。
