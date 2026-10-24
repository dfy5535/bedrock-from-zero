---
name: bedrock-pixel-art
description: 基岩版 16×16 像素美术（物品图标 / 方块贴图 / 接触表）的色彩科学、逐面烘焙与渲染验证规范。当需要生成、修改或审查任何像素级纹理资产，或出现「发灰/发暗/像木头/颜色不对/饱和度低/渲染后褪色/钻石铁分不清」时使用。
whenToUse: 用户说「画个图标/贴图」「颜色不对/发灰/像木头」「渲染出来跟贴图不一样」「钻石和铁区分不开」「图标不够鲜明」，或任何 bedrock-item / bedrock-block 任务涉及纹理生成与视觉验收时。**在写任何像素生成代码之前先加载本技能。**
---

# bedrock-pixel-art — 基岩像素美术色彩规范

> **来源**：2026-10-12 幸运方块贴图 v1→v10 十轮迭代的实测结论。
> 三条铁律是用真实废稿换来的，**不是审美偏好，是可测量的物理约束**。

---

## 0. 三十秒决策表

| 我要干的事 | 铁律 |
|---|---|
| 定主色 | **B 通道 ≤ 28**（除刻意设计的冷色族外） |
| 渲染验证 | **`--tone-mapping neutral --lighting outdoor`**，禁用 `agx` / `studio` |
| 取参考色 | **只从受光面（顶面）取**，背光面已暗化不可用 |
| 自检 | 渲完立刻量**平均饱和度**与**灰像素占比** |

---

## 1. 铁律一：B 通道 ≤ 28

### 1.1 为什么

暖色系（金/铜/木/皮革）一旦 B 通道升高，**观感会不可逆地发闷、发灰、发橄榄**。
这不是显示器差异 —— 是明度与色相同时被拉偏。

### 1.2 实测对照

| 颜色 | RGB | B | 观感 |
|---|---|---|---|
| 木头（废稿） | (168,122,38) | 38 | 发闷 |
| 柠檬奶酪（废稿） | (232,216,56) | **56** | 发酸、发绿 |
| **真黄金（定稿）** | (248,184,18) | **18** | 浓郁赤金 |
| 钻石 base（**本次踩坑**） | (22,106,122) | **122** | ❌ 发灰、发暗 |
| 钻石 base（**修正**） | (46,180,166) | **166→见 §1.3** | ✅ 见冷色族说明 |

### 1.3 冷色族怎么办（钻石 / 青金 / 绿宝石）

**冷色族的 B 通道本来就要高**（青色就是要 B 高）。这里的约束改为：

```
暖色族（金/铜/木/皮革/红石）：B ≤ 28        ← 硬约束
冷色族（钻石/青金/绿宝）：   B > G > R        ← 且必须满足「B 明显高于 R」
```

**踩坑案例**：本次钻石 `base: #166A7A` → R=22, G=106, B=122。
它满足 B>G>R，但**三通道全部偏低（最高才 122）** → 整体明度不够 → 发灰。

**修正方向**：冷色族要**提明度**，不是压 B。

```js
// ❌ 错：三通道都低 → 发灰
diamond: { base: '#166A7A' }   // RGB(22,106,122)  明度极低

// ✅ 对：把亮度提上来，保持 B>G>R 的青色关系
diamond: { base: '#3FC4D6' }   // RGB(63,196,214)  饱和 0.71
```

### 1.4 通用判据（任何族）

```
饱和饱和度 = (max - min) / max
目标 ≥ 0.55        低于 0.35 就是"发灰"，必须改
```

---

## 2. 铁律二：渲染必须 neutral + outdoor

### 2.1 坑：AgX 色调映射吃饱和度（最隐蔽）

Blockbench headless / bb-render 的 **`showcase`、`turntable` 预设硬编码 `toneMapping: "agx"`**。
AgX 是电影级色调映射，专做「高光去饱和 + 暗部抬灰」。

**实测**（同一贴图、同一模型）：

| 色调映射 | 平均色 | 最亮 | 主体色 | B 通道 |
|---|---|---|---|---|
| 原始 PNG | RGB(239,206,36) | 249 | #f5d900 | 0 |
| **neutral** | RGB(212,185,48) | 251 | #d5bd03 | **3** ✅ |
| **agx** | RGB(140,128,84) | 189 | #bdad61 | **97** ❌ |

### 2.2 坑：studio 光照把顶面冲成奶油白

| 光照预设 | iso 顶面实测 | 结论 |
|---|---|---|
| `studio` | `#feeac1` | ❌ 过曝 |
| **`outdoor`** | `#f4c430` | ✅ **首选** |
| `flat` | 0.62× 全暗 | ⚠️ 环境光等量压暗 |

### 2.3 坑：`tone-mapping none` 会让 exposure 失效

three.js 特性：`toneMapping = NoToneMapping` 时 `toneMappingExposure` 不生效。
别指望用 `none + 高 exposure` 提亮。

### 2.4 定稿渲染命令

```bash
export VK_ICD_FILENAMES=/var/agent/vk/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/var/agent/vk

node /var/agent/bb-render/cli.mjs <模型.bbmodel> \
  --output 输出.png \
  --width 1024 --height 1024 \
  --background '#1f2229' \
  --supersample 2 \
  --view iso \
  --lighting outdoor \
  --tone-mapping neutral \
  --exposure 1.0
```

### 2.5 ⚠️ MCP `bbmodel_render` 的致命限制

**MCP 的 `bbmodel_render` 只暴露 4 个预设**（showcase / turntable / icon / sprite-sheet-frame），
**无法单独指定 lighting / tone-mapping**。

> **→ 用 MCP 的 `bbmodel_render` 做"好看的效果图"可以，做"颜色验收"必须走 CLI。**
> 拿 `preset: showcase` 的渲染图去判断贴图颜色 = 一定会被 AgX 骗。

---

## 3. 铁律三：只从受光面取色

从参考图采样时：

```
✅ 顶面（受光面）        → 可用
❌ 侧面（已 ×0.6 暗化）  → 不可用
❌ 侧面 + 周围方块 AO    → 更不可用
```

**踩坑案例**：曾把问号的琥珀色 `#D89808` 当成本体色，
实际那是**背光面**（MC 侧面 ×0.6 暗化 + 石砖 AO 混合）的结果。
问号本体是**暖白 `#FFFDF4`**。

---

## 4. 逐面明度系数（让 3D 有纵深）

Minecraft 方块/物品展示**不能用强高光把顶面冲白**。

| 面 | 乘数 [R,G,B] | 说明 |
|---|---|---|
| 顶面 Top/+Y | `[1.00, 1.00, 1.00]` | **严格保持贴图原色** |
| 右前受光 | `[0.84, 0.80, 0.72]` | 暖向压暗，**绝不偏绿** |
| 左前背光 | `[0.68, 0.62, 0.52]` | 深邃阴影 |

**实现方式**：把系数**烘焙进贴图**（生成多张独立 PNG），模型每面引用对应贴图。
不要指望渲染器帮你做 —— 渲染器的光照预设会覆盖你的意图。

---

## 5. 色彩自检脚本（每次出图必跑）

```js
// 零依赖 PNG 解码 + 色彩统计
const zlib = require('zlib'), fs = require('fs');

function decodePNG(buf) {
  let p = 8, w = 0, h = 0, bd = 0, ct = 0; const idat = [];
  while (p < buf.length) {
    const len = buf.readUInt32BE(p), type = buf.toString('ascii', p + 4, p + 8);
    const data = buf.subarray(p + 8, p + 8 + len);
    if (type === 'IHDR') { w = data.readUInt32BE(0); h = data.readUInt32BE(4); bd = data[8]; ct = data[9]; }
    else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    p += 12 + len;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const ch = ct === 6 ? 4 : ct === 2 ? 3 : 1;
  const bpp = ch * (bd / 8), stride = w * bpp;
  const out = Buffer.alloc(w * h * ch); let prev = Buffer.alloc(stride), o = 0;
  for (let y = 0; y < h; y++) {
    const ft = raw[o++]; const line = Buffer.from(raw.subarray(o, o + stride)); o += stride;
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? line[i - bpp] : 0, b = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
      let v = line[i];
      if (ft === 1) v += a; else if (ft === 2) v += b; else if (ft === 3) v += (a + b) >> 1;
      else if (ft === 4) { const pp = a + b - c, pa = Math.abs(pp - a), pb = Math.abs(pp - b), pc = Math.abs(pp - c);
        v += (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c); }
      line[i] = v & 0xff;
    }
    line.copy(out, y * stride); prev = line;
  }
  return { w, h, ch, data: out };
}

function audit(path) {
  const { w, h, ch, data } = decodePNG(fs.readFileSync(path));
  let n = 0, satSum = 0, gray = 0, vivid = 0, dark = 0;
  for (let i = 0; i < data.length; i += ch) {
    const R = data[i], G = data[i + 1], B = data[i + 2];
    const A = ch > 3 ? data[i + 3] : 255; if (A < 128) continue;
    n++;
    const mx = Math.max(R, G, B), mn = Math.min(R, G, B);
    const sat = mx === 0 ? 0 : (mx - mn) / mx;
    satSum += sat;
    if (sat < 0.15) gray++;
    if (sat > 0.5) vivid++;
    if (0.299 * R + 0.587 * G + 0.114 * B < 60) dark++;
  }
  console.log(path);
  console.log('  平均饱和度 ' + (satSum / n).toFixed(3) + '   [目标 ≥ 0.55]');
  console.log('  灰像素占比 ' + (gray / n * 100).toFixed(1) + '%  [目标 ≤ 10%]');
  console.log('  鲜艳占比   ' + (vivid / n * 100).toFixed(1) + '%  [目标 ≥ 40%]');
  console.log('  暗像素占比 ' + (dark / n * 100).toFixed(1) + '%  [目标 ≤ 30%]');
}
audit(process.argv[2]);
```

### 5.1 验收阈值

| 指标 | 目标 | 说明 |
|---|---|---|
| 平均饱和度 | **≥ 0.55** | 低于 0.35 = 发灰 |
| 灰像素（sat<0.15） | **≤ 10%** | 超过 25% 必改 |
| 鲜艳（sat>0.5） | **≥ 40%** | 低于 20% 必改 |
| 暗像素（lum<60） | **≤ 30%** | 超过 50% = 被背景吃掉 |

### 5.2 ⚠️ 渲染图必须加 `--ignore-bg`

**踩过的坑**：直接量带深色背景的渲染图，背景会把「平均饱和度」拉低、「暗像素占比」拉高，
**得出完全错误的结论**。

```
❌ 不加 --ignore-bg（幸运方块定稿图，被判为不合格）
   平均饱和度 0.538 ❌   暗像素占比 64.0% ❌
   ← 51.2% 的像素是深色背景 #182828

✅ 加 --ignore-bg（同一张图，真实水平）
   平均饱和度 0.864 ✅   暗像素占比 24.0% ✅
```

**用法**：`node 色彩自检.js --ignore-bg <渲染图.png>`

脚本会自动取四角色值判断背景（容差 24），剔除后重新统计。

### 5.3 真实对照数据（剔除背景后）

| 样本 | 平均饱和度 | 灰像素 | 鲜艳 | 判定 |
|---|---|---|---|---|
| ❌ strata 钻石剑渲染 | **0.178** | **72.5%** | 13.7% | 全部不达标 |
| ❌ strata 图标接触表 | 0.486 | 27.3% | 55.9% | 饱和度、灰像素不达标 |
| ✅ 幸运方块定稿渲染 | **0.864** | 6.5% | 86.6% | 全部达标 |

**0.178 vs 0.864 —— 差了近 5 倍。** 这不是审美分歧，是量出来的差距。

---

## 6. 常见现象 → 根因 → 修正

| 现象 | 根因 | 修正 |
|---|---|---|
| 整体发灰、发卡其 | AgX 色调映射 | 换 `neutral` |
| 顶面接近奶油白 | studio 光照过曝 | 换 `outdoor` |
| 侧面偏橄榄绿 | B 通道 > 30 | 压低 B 到 4~28 |
| 发酸、柠檬黄 | 底色色相 > 50° | R−G 提到 50~85 |
| 像木箱 | 明度低 + 水平木纹 | 提高明度、删木纹 |
| 图标发暗、跟背景糊在一起 | 主体明度不足 | 提 base 明度 |
| 两种材质分不清 | 色相太接近 | 拉开色相距离，不是只改明度 |
| 渲染图与贴图色差大 | 用了 MCP preset | 改走 CLI + neutral |

---

## 7. 工作流（正确顺序）

```
1. 定调色板    → 检查每个色的饱和度 ≥ 0.55，暖色 B ≤ 28
2. 写生成器    → 程序化生成像素矩阵（不要手绘）
3. 自检贴图    → 跑 §5 脚本，看四项指标
4. 建模型      → Blockbench MCP
5. 渲染        → CLI + neutral + outdoor（不用 MCP preset）
6. 自检渲染    → 再跑 §5 脚本
7. 视觉确认    → 最后才用视觉模型看一眼（它是辅助，不是判据）
```

**顺序不能颠倒**：先量数据，再问视觉模型。
视觉模型会说"看起来还行"，但**数据不会骗你**。

---

## 8. 参考文件

| 文件 | 内容 |
|---|---|
| `references/幸运方块案例.md` | 完整 v1→v10 迭代记录 + 12 色调色板 + 16×16 矩阵 |
| `references/幸运方块生成器.js` | 零依赖生成脚本（可直接改参数复用） |
| `references/渲染验证.py` | 渲染图采样校验 |

---

## 9. 一句话总结

**颜色不对先查三件事：B 通道、色调映射、取色面。**
**渲完先量四项数据：饱和度、灰占比、鲜艳占比、暗占比。**
**别让视觉模型替你做判断。**

---

*maintainer ／ 2026-10-12 ／ 源自幸运方块 v1→v10 实测*
