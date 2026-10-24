#!/usr/bin/env node
/**
 * 幸运方块贴图生成器 v1.0
 * ------------------------------------------------------------
 * 依据《幸运方块贴图制作教程》生成基岩版幸运方块贴图。
 * 零第三方依赖（只用 node:fs / node:zlib），Node.js >= 18。
 *
 * 用法:
 *   node bf_lucky_block.js [输出目录]
 *   node bf_lucky_block.js            # 默认输出到当前目录 ./out
 *
 * 产物:
 *   lucky_top16.png    lucky_top512.png     顶面（原色）
 *   lucky_right16.png  lucky_right512.png   右面（暖向压暗）
 *   lucky_left16.png   lucky_left512.png    左面（琥珀阴影）
 *   lucky_preview128.png                    8x 最近邻检查图（顶面）
 */

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

/* ========== 1. 12 色调色板（照抄教程，勿改） ========== */
const PALETTE = {
  'C': [152, 62, 4],    // #983E04 外框四角深铜色
  'B': [184, 82, 6],    // #B85206 外框深琥珀色 A
  'E': [202, 98, 8],    // #CA6208 外框深琥珀色 B（微纹理交替）
  'H': [255, 234, 92],  // #FFEA5C 四角内铆钉高光（亮金白）
  'R': [212, 110, 6],   // #D46E06 内角过渡 & 问号防漏边描线
  'O': [226, 134, 8],   // #E28608 外圈深橘金
  'D': [238, 158, 12],  // #EE9E0C 中外圈浓郁金
  'G': [248, 184, 18],  // #F8B812 中圈正黄金
  'M': [255, 208, 28],  // #FFD01C 中心区域高光亮金
  'S': [164, 70, 4],    // #A44604 问号左侧/下方深浮雕阴影槽
  'W': [255, 253, 244], // #FFFDF4 问号本体（高光暖白）
  'w': [255, 240, 200], // #FFF0C8 问号本体右下边缘（暖奶油白）
};

/* ========== 2. 16×16 精确像素矩阵（严格居中对称） ========== */
const MATRIX = [
  "C B E B E B E B E B E B E B B C", // y=0  上外框
  "B H R O O D D D D D D O O R H B", // y=1  内框圈 + 四角铆钉 H
  "E R O D S W W W W W w R D O R E", // y=2  问号顶横梁 x=5..10
  "B O D S W W W W W W W w R D O B", // y=3  问号顶弧外扩 x=4..11
  "E O D S W w S S S M W w R D O E", // y=4  左钩 + 内弧顶阴影 + 右弧
  "B D D S W w R M M S W w R D D B", // y=5
  "E D O R S S M M S W W w R O D E", // y=6  右弧向中心收拢
  "B D G G M M M S W W w R G G D B", // y=7  斜折向中心
  "E D G M M M S W w R M M G D D E", // y=8  中心竖杆 x=7..8
  "B D G M M M S W w R M M G D D B", // y=9
  "E D G M M M R S S R M M G D D E", // y=10 竖杆底阴影间隙 x=7..8
  "B O D G M M S W w R M G D D O B", // y=11 2×2 圆点（上排）
  "E O D G M M S W w R M G D D O E", // y=12 2×2 圆点（下排）
  "B R O D G G R S S R G D O R O B", // y=13 圆点底浮雕阴影
  "B H R O O D D D D D D O O R H B", // y=14 下内框圈 + 铆钉
  "C B E B E B E B E B E B E B B C", // y=15 下外框
];

/* ========== 3. 逐面明度系数（教程第 5 节） ========== */
const FACE_MULTIPLIERS = {
  top: [1.00, 1.00, 1.00],   // 顶面：严格保持贴图原色
  right: [0.84, 0.80, 0.72],  // 右前受光：暖向压暗，绝不偏绿
  left: [0.68, 0.62, 0.52],  // 左前背光：深邃琥珀金阴影
};

/* ========== 4. 极简 PNG 编码器（RGBA / 8-bit） ========== */
const CRC_TABLE = (() => {
  const t = new Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function pngChunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0);
  const t = Buffer.from(type, 'ascii');
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([t, data])), 0);
  return Buffer.concat([len, t, data, crc]);
}
function encodePNG(w, h, rgba) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;  // bit depth
  ihdr[9] = 6;  // color type: RGBA
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 4 + 1)] = 0; // filter: None
    rgba.copy(raw, y * (w * 4 + 1) + 1, y * w * 4, (y + 1) * w * 4);
  }
  return Buffer.concat([
    sig,
    pngChunk('IHDR', ihdr),
    pngChunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
    pngChunk('IEND', Buffer.alloc(0)),
  ]);
}

/* ========== 5. 生成逻辑 ========== */
const S = 16;
const rows = MATRIX.map(r => r.split(' '));

function validateMatrix() {
  const problems = [];
  if (rows.length !== 16) problems.push(`行数 ${rows.length} ≠ 16`);
  rows.forEach((r, y) => {
    if (r.length !== 16) problems.push(`第 ${y} 行 ${r.length} 格 ≠ 16`);
    r.forEach(c => { if (!PALETTE[c]) problems.push(`第 ${y} 行出现未定义字符 '${c}'`); });
  });
  return problems;
}

function buildFace(mult) {
  const px = Buffer.alloc(S * S * 4);
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const [R, G, B] = PALETTE[rows[y][x]];
      const i = (y * S + x) * 4;
      px[i] = Math.min(255, Math.round(R * mult[0]));
      px[i + 1] = Math.min(255, Math.round(G * mult[1]));
      px[i + 2] = Math.min(255, Math.round(B * mult[2]));
      px[i + 3] = 255;
    }
  }
  return px;
}

function nearestNeighbor(src, s, factor) {
  const D = s * factor;
  const out = Buffer.alloc(D * D * 4);
  for (let y = 0; y < D; y++) {
    for (let x = 0; x < D; x++) {
      const si = (Math.floor(y / factor) * s + Math.floor(x / factor)) * 4;
      const di = (y * D + x) * 4;
      out[di] = src[si]; out[di + 1] = src[si + 1]; out[di + 2] = src[si + 2]; out[di + 3] = 255;
    }
  }
  return encodePNG(D, D, out);
}

/* ========== 6. 主流程 ========== */
function main() {
  const outDir = path.resolve(process.argv[2] || './out');
  fs.mkdirSync(outDir, { recursive: true });

  const problems = validateMatrix();
  if (problems.length) {
    console.error('矩阵校验失败:');
    problems.forEach(p => console.error('  - ' + p));
    process.exit(1);
  }
  console.log('矩阵校验: 16x16 = true  未定义字符 = 无');

  const faces = {};
  for (const [name, mult] of Object.entries(FACE_MULTIPLIERS)) {
    faces[name] = buildFace(mult);
    fs.writeFileSync(path.join(outDir, `lucky_${name}16.png`), encodePNG(S, S, faces[name]));
    fs.writeFileSync(path.join(outDir, `lucky_${name}512.png`), nearestNeighbor(faces[name], S, 32));
  }
  fs.writeFileSync(path.join(outDir, 'lucky_preview128.png'), nearestNeighbor(faces.top, S, 8));
  console.log('PNG_GENERATED -> ' + outDir);
  console.log('  lucky_{top,right,left}16.png    16x16 RGBA');
  console.log('  lucky_{top,right,left}512.png   512x512 最近邻');
  console.log('  lucky_preview128.png            128x128 检查图');

  /* 调色板占比报告 */
  const cnt = new Map();
  for (let i = 0; i < S * S; i++) {
    const k = [faces.top[i * 4], faces.top[i * 4 + 1], faces.top[i * 4 + 2]].join(',');
    cnt.set(k, (cnt.get(k) || 0) + 1);
  }
  console.log('\n调色板占比（顶面）:');
  for (const [k, c] of [...cnt.entries()].sort((a, b) => b[1] - a[1])) {
    const [R, G, B] = k.split(',').map(Number);
    const code = Object.keys(PALETTE).find(kk => PALETTE[kk].join(',') === k) || '?';
    console.log(`  ${code}  #${[R, G, B].map(v => v.toString(16).padStart(2, '0')).join('')}  RGB(${R},${G},${B})  R-G=${R - G}  B=${B}  ${(100 * c / (S * S)).toFixed(1)}%`);
  }

  /* 三面主体金结果 */
  const hx = c => '#' + c.map(v => v.toString(16).padStart(2, '0')).join('');
  const base = PALETTE['G'];
  console.log('\n逐面明度系数（主体金 ' + hx(base) + '）:');
  for (const [name, mult] of Object.entries(FACE_MULTIPLIERS)) {
    console.log(`  ${name.padEnd(6)} x[${mult.join(', ')}] -> ${hx(base.map((v, i) => Math.min(255, Math.round(v * mult[i]))))}`);
  }

  /* ASCII 图案自检 */
  console.log('\n图案自检（顶面，字母=调色板代号）:');
  for (let y = 0; y < S; y++) console.log('  ' + rows[y].join(''));

  /* 验收提示 */
  console.log('\n验收提示:');
  console.log('  [ ] B 通道（除问号 W/w 外）全部 <= 28');
  console.log('  [ ] 主体金类（D/G/M/O）合计 >= 50%');
  console.log('  [ ] 顶面渲染应 ≈ #f4c430（outdoor + neutral）');
  console.log('\n渲染命令（需 bb-render 环境）:');
  console.log('  VK_ICD_FILENAMES=<icd.json> LD_LIBRARY_PATH=<vk dir> \\');
  console.log('    node /var/agent/bb-render/cli.mjs <模型.bbmodel> --output verify.png \\');
  console.log('      --width 1024 --height 1024 --background "#1f2229" --supersample 2 \\');
  console.log('      --view iso --lighting outdoor --tone-mapping neutral --exposure 1.0');
}

if (require.main === module) main();

module.exports = { PALETTE, MATRIX, FACE_MULTIPLIERS, encodePNG, nearestNeighbor, buildFace };