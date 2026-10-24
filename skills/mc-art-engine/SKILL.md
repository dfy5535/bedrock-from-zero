---
name: mc-art-engine
description: Minecraft 像素美术的官方确定性引擎（mc-art）。34 个 Python 模块、182 个测试、18 个子命令，能扫资产根、出参考证据、光栅化 plan、按游戏方式渲染、度量像素。**已全局可用**：任何 shell 里直接敲 mc-art。当需要生成/审查/度量 16×16 图标、方块贴图、实体贴图、资源包，或判断"这图灰了没有/和参考像不像/族内是否一致"时使用。
whenToUse: 用户说「画个图标/贴图」「这图发灰/发暗/饱和度不够」「和原版像不像」「族内风格不统一」「钻石和铁分不清」「渲染出来跟贴图不一样」，或任何涉及 Minecraft 像素资产的生成与验收时。**动手画像素之前先加载本技能，用引擎度量而不是靠眼睛。**
---

# mc-art-engine — 官方像素美术引擎（已全局可用）

> **这是第三方开源引擎**（`github.com/GMH13552/dsh-mc-art`），随 `dsh-mc-art-panel` 插件分发。
> AUTHOR 于 2026-10-12 完成全局激活。**它是"确定性引擎"——里面没有 AI，所有判断归你。**

---

## 0. 最重要的一件事：它已经能直接用了

```bash
mc-art --help
```

**不需要任何 PATH 设置、不需要激活、不需要进特定预设。** 直接在 shell 里敲。

```bash
$ mc-art doctor
  platform      linux
  modules       34
interpreter
  using /opt/dsh/py/bin/python3     ← 自动找到
entry points  OK
```

**安装结构**（三层，各司其职）：

| 层 | 位置 | 作用 |
|---|---|---|
| 命令 | `/opt/dsh/bin/mc-art` | wrapper，PATH 第一顺位，持久化 |
| Python | `/opt/dsh/py/` | 便携式 3.11.13 + Pillow + numpy，持久化 |
| 引擎 | `/var/agent/profiles/web/node_modules/dsh-mc-art-panel/preset/mc-studio/skills/mc-art` | 34 个模块本体 |

**持久化**：`/opt/dsh` 是 bind mount（宿主机 `/opt/dsh-docker/programs`）→ **容器重启不丢**。

---

## 1. 分工契约（作者写在预设里，必须遵守）

```
美丑、参考选哪张、族内边界、命名        → 你（AI）判断
像素度量、jar 扫描、退出码、可重复光栅化 → 交给引擎
```

**头号规矩**：**抓不到错的检查不算检查。** 做完要说清验证了什么、没验证什么。

**两条禁令**：
- 别把审美推给脚本（它只会取第一张名字对得上的参考，深渊石会参考成浅层石）
- 别用眼睛代替度量（眼睛会被色调映射骗）

---

## 2. 十八个子命令速查

```bash
mc-art <subcommand> [args]
```

| 子命令 | 作用 |
|---|---|
| `doctor` | **自检**：解释器、入口、行尾符、可写性、引擎副本 |
| `measure` | 度量帧间/族内一致性（需两张以上） |
| `evidence` | 出参考证据（扫资产根，**不调模型**） |
| `render` | 光栅化你写的 plan，验证并打包 |
| `audit` | 审查生成的素材 |
| `ingame` | **按游戏的方式渲染**（验证交付物） |
| `index-vanilla` | 从资产根建本地贴图索引 |
| `list-groups` | 列出逻辑资产名（一个名 = 它全部贴图） |
| `why-reference` | 说明哪张参考会画进你的画布、其它候选打了多少分 |
| `refclass` | 参考分类表（class/layer） |
| `gap-from-refs` | 量参考的「强调色↔底色」亮度差 |
| `block` | 方块相关 |
| `layouts` | 原版 UV 布局 |
| `boxes` / `uv` | 模型盒 / UV 映射 |
| `pack` | 打包资源包 |
| `model` | 模型处理 |
| `entity` | 实体规划 |

**先跑这个**：`mc-art doctor`

---

## 3. 像素度量（最常用，也是本技能的核心价值）

### 3.1 用 CLI

```bash
mc-art measure <图1.png> <图2.png>          # 一致性对比
mc-art measure --baseline <基准.png> <图...>  # 带基准
```

### 3.2 直接用 Python 模块（单图分析）

```python
import sys
sys.path.insert(0, "/var/agent/profiles/web/node_modules/dsh-mc-art-panel/preset/mc-studio/skills/mc-art")
from mc_art import metrics

r = metrics.sprite_palette_profile("/path/to/sprite.png")
# → {"opaque": N, "quantised": [...], "grey_ratio": 0.38,
#    "dark_ratio": 0.07, "mean_saturation": 0.486}
```

**`metrics` 模块的四个公开函数**：

| 函数 | 签名 | 用途 |
|---|---|---|
| `sprite_palette_profile` | `(sprite_path, limit=12)` | 单图调色板画像 |
| `sprite_palette_ramp` | `(sprite_path, count=8)` | 单图色阶 |
| `family_consistency` | `(anchor, members, limit=12, minimum_overlap=0.35, maximum_grey_delta=0.25)` | 族内一致性 |
| `frame_continuity` | `(sprites, baseline_sprites=None, ...)` | 帧间连续性 |

### 3.3 三个关键指标与阈值

| 指标 | 含义 | 引擎阈值 |
|---|---|---|
| `mean_saturation` | 平均饱和度（HSV 的 S） | **越高越好，≥0.55 健康** |
| `grey_ratio` | 灰像素占比 | **sat < 0.22 判灰** ⚠️ |
| `dark_ratio` | 暗像素占比 | **val < 0.22 判暗** ⚠️ |

> 引擎 docstring 原话：**"the sibling drifted to grey is a real failure"**
> （兄弟素材灰掉了，是**真实故障**）—— 它把灰化当故障，不是风格偏好。

### 3.4 实测基准（AUTHOR 2026-10-12 量）

| 样本 | mean_saturation | grey_ratio | dark_ratio |
|---|---|---|---|
| ❌ 踩坑：压缩矿物图标 | **0.4857** | **0.3802** ⚠️ | 0.0726 |
| ❌ 踩坑：钻石剑渲染 | **0.2372** | 0.0856 | **0.8907** ⚠️ |
| ✅ 定稿：幸运方块顶面 | **0.8262** | 0.1406 | 0.0000 |

---

## 4. 色彩铁律（与 bedrock-pixel-art 技能一致）

这三条是用真实废稿换来的，**不是审美偏好，是可测量的物理约束**：

### 铁律一：暖色族 B 通道 ≤ 28

```
暖色族（金/铜/木/皮革/红石）：B ≤ 28       ← 硬约束
冷色族（钻石/青金/绿宝）：   B > G > R      ← 且明度要够
```

**冷色族易错点**：不是压 B，是**提明度**。
`#166A7A` → RGB(22,106,122) 三通道全低 → 发灰。改成 `#3FC4D6` 才对。

### 铁律二：渲染必须 `neutral` + `outdoor`

`preset: "showcase"` 内部**硬编码 `toneMapping: "agx"`** —— AgX 是电影级色调映射，专做「高光去饱和 + 暗部抬灰」。实测 B 通道从 0 被拉到 97。

**MCP 的 `bbmodel_render` 只暴露 4 个预设，无法指定 lighting/tone-mapping。颜色验收必须走 CLI。**

### 铁律三：只从受光面取色

```
✅ 顶面（受光面）        → 可用
❌ 侧面（已 ×0.6 暗化）  → 不可用
❌ 侧面 + 周围方块 AO    → 更不可用
```

---

## 5. 标准工作流

```
1. mc-art doctor                    ← 先确认引擎健康
2. 定调色板，用 §3 度量验证          ← 数据说话
3. mc-art evidence --name <资产名>   ← 拿官方参考证据
4. mc-art why-reference              ← 确认参考选对了
5. 写 plan / 生成像素
6. mc-art render 或 mc-art audit     ← 引擎验证
7. mc-art measure / ingame           ← 度量 + 按游戏方式渲染
8. 最后才用视觉模型看一眼            ← 它是辅助，不是判据
```

**顺序不能颠倒**：先量数据，再问视觉模型。视觉模型会说"看起来还行"，数据不会骗你。

---

## 6. 完整官方手册

本技能目录下的 **`官方手册.md`** 是引擎自带的完整 SKILL.md（约 50KB），
包含：stage 0–7 通用流程、版本矩阵、美术规程、Windows 注意事项、踩过的坑。

**先读本文件，需要细节再查官方手册。**

---

## 7. 故障排查

| 现象 | 检查 |
|---|---|
| `mc-art: command not found` | `/opt/dsh/bin/mc-art` 是否存在且可执行 |
| `no working Python found` | `/opt/dsh/py/bin/python3 -c 'print(1)'` 是否输出 1 |
| `ModuleNotFoundError: PIL/numpy` | `/opt/dsh/py/bin/python3 -m pip install pillow numpy` |
| 引擎目录不存在 | 确认 `dsh-mc-art-panel` 插件已装（`ls /var/agent/profiles/web/node_modules/dsh-mc-art-panel`） |
| 容器重启后失效 | `/opt/dsh` 是否还是 bind mount（`docker inspect dsh`） |

**注意**：`/opt/dsh/bin` 是 `docker exec` 默认 PATH 第一顺位；但**登录 shell（`sh -lc`）的 PATH 不含它**。若在登录 shell 里用，需显式写全路径 `/opt/dsh/bin/mc-art` 或先 `export PATH=/opt/dsh/bin:$PATH`。

---

*maintainer ／ 2026-10-12 ／ 全局激活 mc-art 引擎*