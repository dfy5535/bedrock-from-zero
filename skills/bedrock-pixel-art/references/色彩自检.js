#!/usr/bin/env node
/**
 * 色彩自检.js — 量 PNG 的像素色彩指标
 *
 * 用法：
 *   node 色彩自检.js <图片.png> [更多图片...]
 *
 * ⚠️ 关键前提：**只对"主体占比高"的图有效**（纯贴图 / 接触表 / 白底渲染）。
 *    渲染图若带大面积深色背景，背景会拉低平均饱和度、拉高暗像素占比，
 *    此时请改用 --ignore-bg 自动剔除背景色。
 *
 * 用法（带背景剔除）：
 *   node 色彩自检.js --ignore-bg <图片.png>
 *
 * 验收阈值（基岩像素美术）：
 *   平均饱和度 ≥ 0.55    灰像素 ≤ 10%    鲜艳 ≥ 40%    暗像素 ≤ 30%
 */
const zlib = require('zlib'), fs = require('fs');

function decodePNG(buf) {
  let p = 8, w = 0, h = 0, bd = 0, ct = 0;
  const idat = [];
  while (p < buf.length) {
    const len = buf.readUInt32BE(p);
    const type = buf.toString('ascii', p + 4, p + 8);
    const data = buf.subarray(p + 8, p + 8 + len);
    if (type === 'IHDR') { w = data.readUInt32BE(0); h = data.readUInt32BE(4); bd = data[8]; ct = data[9]; }
    else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    p += 12 + len;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const ch = ct === 6 ? 4 : ct === 2 ? 3 : ct === 0 ? 1 : 4;
  const bpp = ch * (bd / 8), stride = w * bpp;
  const out = Buffer.alloc(w * h * ch);
  let prev = Buffer.alloc(stride), o = 0;
  for (let y = 0; y < h; y++) {
    const ft = raw[o++];
    const line = Buffer.from(raw.subarray(o, o + stride));
    o += stride;
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? line[i - bpp] : 0;
      const b = prev[i];
      const c = i >= bpp ? prev[i - bpp] : 0;
      let v = line[i];
      if (ft === 1) v += a;
      else if (ft === 2) v += b;
      else if (ft === 3) v += (a + b) >> 1;
      else if (ft === 4) {
        const pp = a + b - c;
        const pa = Math.abs(pp - a), pb = Math.abs(pp - b), pc = Math.abs(pp - c);
        v += (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
      }
      line[i] = v & 0xff;
    }
    line.copy(out, y * stride);
    prev = line;
  }
  return { w, h, ch, data: out };
}

/** 找背景色：取四角 5x5 的平均，若四角接近则认为是背景 */
function detectBg(w, h, ch, data) {
  const sample = (x0, y0) => {
    let r = 0, g = 0, b = 0, n = 0;
    for (let y = y0; y < Math.min(y0 + 5, h); y++)
      for (let x = x0; x < Math.min(x0 + 5, w); x++) {
        const i = (y * w + x) * ch;
        r += data[i]; g += data[i + 1]; b += data[i + 2]; n++;
      }
    return [Math.round(r / n), Math.round(g / n), Math.round(b / n)];
  };
  const corners = [sample(0, 0), sample(w - 5, 0), sample(0, h - 5), sample(w - 5, h - 5)];
  // 四角是否互相接近（容差 24）
  const near = (a, b) => Math.abs(a[0] - b[0]) < 24 && Math.abs(a[1] - b[1]) < 24 && Math.abs(a[2] - b[2]) < 24;
  const consistent = near(corners[0], corners[1]) && near(corners[0], corners[2]) && near(corners[0], corners[3]);
  return consistent ? corners[0] : null;
}

function audit(path, ignoreBg) {
  if (!fs.existsSync(path)) { console.log('❌ 文件不存在: ' + path); return; }
  let w, h, ch, data;
  try {
    ({ w, h, ch, data } = decodePNG(fs.readFileSync(path)));
  } catch (e) {
    console.log('❌ 解码失败 ' + path + ' : ' + e.message);
    return;
  }

  let bg = null, bgNote = '';
  if (ignoreBg) {
    bg = detectBg(w, h, ch, data);
    if (bg) bgNote = '  [已剔除背景 RGB(' + bg.join(',') + ')]';
    else bgNote = '  [四角不一致，未剔除背景]';
  }

  let n = 0, r = 0, g = 0, b = 0, satSum = 0, gray = 0, vivid = 0, dark = 0, skipped = 0;
  const hist = {};
  for (let i = 0; i < data.length; i += ch) {
    const R = data[i], G = data[i + 1], B = data[i + 2];
    const A = ch > 3 ? data[i + 3] : 255;
    if (A < 128) continue;
    if (bg) {
      const d = Math.abs(R - bg[0]) + Math.abs(G - bg[1]) + Math.abs(B - bg[2]);
      if (d < 40) { skipped++; continue; }
    }
    n++; r += R; g += G; b += B;
    const mx = Math.max(R, G, B), mn = Math.min(R, G, B);
    const sat = mx === 0 ? 0 : (mx - mn) / mx;
    const lum = 0.299 * R + 0.587 * G + 0.114 * B;
    satSum += sat;
    if (lum < 60) dark++;
    if (sat < 0.15) gray++;
    if (sat > 0.5) vivid++;
    const key = (R >> 4) + ',' + (G >> 4) + ',' + (B >> 4);
    hist[key] = (hist[key] || 0) + 1;
  }
  if (n === 0) { console.log('\n### ' + path + '  → 无有效像素'); return; }

  const avgSat = satSum / n;
  const pGray = gray / n * 100, pVivid = vivid / n * 100, pDark = dark / n * 100;
  const ok = (c) => c ? '✅' : '❌';

  console.log('\n### ' + path + bgNote);
  console.log('  尺寸 ' + w + 'x' + h + ' / 计入像素 ' + n + (skipped ? ' (剔除 ' + skipped + ')' : ''));
  console.log('  平均 RGB(' + Math.round(r / n) + ',' + Math.round(g / n) + ',' + Math.round(b / n) + ')');
  console.log('  ' + ok(avgSat >= 0.55) + ' 平均饱和度 ' + avgSat.toFixed(3) + '        [目标 ≥ 0.55]');
  console.log('  ' + ok(pGray <= 10) + ' 灰像素占比 ' + pGray.toFixed(1) + '%      [目标 ≤ 10%]');
  console.log('  ' + ok(pVivid >= 40) + ' 鲜艳占比   ' + pVivid.toFixed(1) + '%      [目标 ≥ 40%]');
  console.log('  ' + ok(pDark <= 30) + ' 暗像素占比 ' + pDark.toFixed(1) + '%      [目标 ≤ 30%]');

  const top = Object.entries(hist).sort((a, b2) => b2[1] - a[1]).slice(0, 5);
  console.log('  主色簇:');
  top.forEach(([k, v]) => {
    const [R, G, B] = k.split(',').map(x => (x << 4) + 8);
    const mx = Math.max(R, G, B), mn = Math.min(R, G, B);
    console.log('    #' + [R, G, B].map(x => x.toString(16).padStart(2, '0')).join('') +
      '  RGB(' + R + ',' + G + ',' + B + ')  占 ' + (v / n * 100).toFixed(1) +
      '%  sat=' + ((mx - mn) / mx).toFixed(2));
  });
}

let args = process.argv.slice(2);
let ignoreBg = false;
if (args[0] === '--ignore-bg') { ignoreBg = true; args = args.slice(1); }

if (args.length === 0) {
  console.log('用法: node 色彩自检.js [--ignore-bg] <图片.png> [更多图片...]');
  console.log('');
  console.log('  --ignore-bg   自动检测并剔除四角背景色（渲染图建议加）');
  console.log('');
  console.log('验收阈值:');
  console.log('  平均饱和度 ≥ 0.55    灰像素 ≤ 10%    鲜艳 ≥ 40%    暗像素 ≤ 30%');
  process.exit(1);
}
args.forEach(p => audit(p, ignoreBg));
console.log('');