// Caption News · style version diversify-v001 ·《分散投资 Diversify》— 1920×1080, 30 fps, 32 s
// Maintainer overlay: content-driven SHOTS/TEXTS for the diversification plan (no bee demo labels).
// Demo lock path still uses styles/caption-news/demo/main.js. index.html / build.sh stay demo-locked.
// One timeline (SHOTS + timeline.json CAPS/VO) drives picture, captions, and mix length.
const W = 1920, H = 1080, FPS = 30, DUR = 32;
const cv = document.getElementById('out'), ctx = cv.getContext('2d');

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const eo = t => 1 - Math.pow(1 - clamp(t), 3);
const ei = t => Math.pow(clamp(t), 3);
const eio = t => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const back = (t, s = 1.8) => { t = clamp(t) - 1; return 1 + t * t * ((s + 1) * t + s); };

const C = { bg: '#0E0E0C', panel: '#151512', ink: '#F7F5EF', honey: '#FFC21A', loss: '#FF4A3D', grey: '#8D8B83', rule: 'rgba(255,255,255,.045)', margin: 'rgba(255,74,61,.38)', dim: 'rgba(247,245,239,.74)' };
const F = { zh9: "'SC9'", zh5: "'SC5'", n8: "'IT8','SC9'", n5: "'IT5','SC5'", it: "'IT6I','IT5'" };
const CAP = { x: 120, zhY: 948, zh: 88, enY: 1014, en: 33 };

// Half-beat grid (120 BPM). Story beats match fixtures/plan-caption-news.json VO.
const SHOTS = [
  { a: 0.0,  b: 4.0,  k: 'hook' },
  { a: 4.0,  b: 7.0,  k: 'sting' },
  { a: 7.0,  b: 12.0, k: 'split' },
  { a: 12.0, b: 17.0, k: 'stress' },
  { a: 17.0, b: 22.0, k: 'timing' },
  { a: 22.0, b: 27.0, k: 'cash' },
  { a: 27.0, b: 32.0, k: 'end' },
];
let TL = null, CAPS = [], HOOK_CUE = [], VO = {};
const shotAt = t => SHOTS.find(s => t >= s.a && t < s.b) || SHOTS[SHOTS.length - 1];

function text(s, x, y, font, color, align = 'left', base = 'alphabetic') {
  ctx.font = font; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = base; ctx.fillText(s, x, y);
}
function tw(s, font) { ctx.font = font; return ctx.measureText(s).width; }
function num(s, x, y, size, color, align = 'left', font = F.n8) {
  const f = `800 ${size}px ${font}`; ctx.font = f; const cw = ctx.measureText('0').width;
  const wOf = ch => /[0-9]/.test(ch) ? cw : ctx.measureText(ch).width;
  let total = 0; for (const ch of s) total += wOf(ch);
  let cx = align === 'right' ? x - total : align === 'center' ? x - total / 2 : x;
  ctx.fillStyle = color; ctx.textBaseline = 'alphabetic';
  for (const ch of s) { const w = wOf(ch); ctx.textAlign = 'center'; ctx.fillText(ch, cx + w / 2, y); cx += w; }
  return total;
}
function shade(top = 560, a = .84) {
  const g = ctx.createLinearGradient(0, top, 0, H); g.addColorStop(0, 'rgba(14,14,12,0)'); g.addColorStop(.55, `rgba(14,14,12,${a * .7})`); g.addColorStop(1, `rgba(14,14,12,${a})`);
  ctx.fillStyle = g; ctx.fillRect(0, top, W, H - top);
  const r = ctx.createRadialGradient(0, H, 0, 0, H, 1100); r.addColorStop(0, 'rgba(14,14,12,.45)'); r.addColorStop(1, 'rgba(14,14,12,0)'); ctx.fillStyle = r; ctx.fillRect(0, 0, W, H);
}
function topShade() { const g = ctx.createLinearGradient(0, 0, 0, 200); g.addColorStop(0, 'rgba(14,14,12,.55)'); g.addColorStop(1, 'rgba(14,14,12,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, 200); }
function veil() { shade(); topShade(); }
function ledger(t, a, slide = true) {
  const k = slide ? eo(seg(t, a, a + .18)) : 1, ox = (1 - k) * 140;
  ctx.fillStyle = C.panel; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.translate(ox, 0);
  ctx.strokeStyle = C.rule; ctx.lineWidth = 2;
  for (let y = 120; y < H; y += 54) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  ctx.strokeStyle = C.margin; ctx.lineWidth = 2; [78, 86].forEach(x => { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); });
  ctx.restore();
  if (slide && k < 1) { ctx.fillStyle = `rgba(255,194,26,${(1 - k) * .5})`; for (let i = 0; i < 6; i++) ctx.fillRect(W - (1 - k) * 900 - i * 120, 140 + i * 150, 600 * (1 - k), 3); }
  return ox;
}
function camPush(t, a, b, z0 = 1, z1 = 1.03, cx = W / 2, cy = H / 2) {
  const z = lerp(z0, z1, eio(seg(t, a, b))); ctx.translate(cx, cy); ctx.scale(z, z); ctx.translate(-cx, -cy);
}
function bug(t) {
  const k = eo(seg(t, 6.85, 7.1)); if (k <= 0) return;
  ctx.save(); ctx.globalAlpha = k; const x = 96, y = 52;
  ctx.fillStyle = C.honey; ctx.fillRect(x, y, 92, 46); text('简闻', x + 46, y + 34, `900 30px ${F.zh9}`, C.bg, 'center');
  ctx.fillStyle = 'rgba(14,14,12,.62)'; ctx.fillRect(x + 92, y, 300, 46);
  text('分散', x + 108, y + 33, `900 26px ${F.zh9}`, C.ink); text('DIVERSIFY', x + 200, y + 31, `800 17px ${F.n8}`, C.honey);
  ctx.restore();
  TX.push({ id: 'title', text: '分散', x0: x, y0: y, x1: x + 392, y1: y + 46 });
  TX.push({ id: 'title-en', text: 'DIVERSIFY', x0: x, y0: y, x1: x + 392, y1: y + 46 });
}
function sourceTag(t, t0, label = 'CONTROLLER · PLAN') {
  const k = eo(seg(t, t0, t0 + .2)); if (k <= 0) return; ctx.save(); ctx.globalAlpha = k; const x = 96 - (1 - k) * 40, y = 108;
  const w1 = tw('来源', `900 22px ${F.zh9}`) + 20, w2 = tw(label, `500 21px ${F.n5}`) + 22;
  ctx.fillStyle = C.ink; ctx.fillRect(x, y, w1, 36); text('来源', x + 10, y + 26, `900 22px ${F.zh9}`, C.bg);
  ctx.fillStyle = 'rgba(14,14,12,.82)'; ctx.fillRect(x + w1, y, w2, 36); text(label, x + w1 + 11, y + 25, `500 21px ${F.n5}`, C.ink); ctx.restore();
}
function credit(s) {
  if (!s) return; const f = `500 19px ${F.zh5}`; const w = tw(s, f);
  ctx.fillStyle = 'rgba(14,14,12,.5)'; ctx.fillRect(W - 72 - w - 16, 54, w + 16, 30); text(s, W - 80, 75, f, 'rgba(247,245,239,.86)', 'right');
}
function capCard(c, t) {
  const [a, b, zh, en, big = 1] = c; if (t < a || t >= b) return;
  const size = CAP.zh * big, parts = zh.split('|'); let cx = CAP.x; const y = CAP.zhY - (big > 1 ? 40 : 0);
  parts.forEach((p, i) => {
    const t0 = a + .04 + i * .12, k = seg(t, t0, t0 + .13); if (t < t0) { cx += chunkW(p, size) + size * .05; return; }
    const sc = lerp(1.3, 1, back(k, 1.6));
    ctx.save(); ctx.translate(cx, y); ctx.scale(sc, sc); ctx.globalAlpha = clamp(k * 3);
    let x = 0;
    for (const q of p.split(/(\{[^}]+\})/).filter(Boolean)) {
      const hot = q[0] === '{', s = hot ? q.slice(1, -1) : q, f = `900 ${size}px ${F.zh9}`, w = tw(s, f);
      if (hot) { const wk = eo(seg(t, t0 + .05, t0 + .17)); ctx.fillStyle = C.honey; ctx.fillRect(x - 12, -size * .9, (w + 24) * wk, size * 1.1); }
      else { ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 20; ctx.shadowOffsetY = 4; }
      text(s, x, 0, f, hot ? C.bg : C.ink); ctx.shadowColor = 'transparent'; x += w + (hot ? 24 : 0);
    }
    ctx.restore(); cx += chunkW(p, size) + size * .05;
  });
  const ke = eo(seg(t, a + .1, a + .28));
  ctx.save(); ctx.globalAlpha = ke; ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = 12;
  text(en, CAP.x, CAP.enY + (big > 1 ? 4 : 0) + (1 - ke) * 10, `500 ${CAP.en}px ${F.n5}`, C.ink); ctx.restore();
}
function chunkW(p, size) {
  let w = 0;
  for (const q of p.split(/(\{[^}]+\})/).filter(Boolean)) {
    const hot = q[0] === '{';
    w += tw(hot ? q.slice(1, -1) : q, `900 ${size}px ${F.zh9}`) + (hot ? 24 : 0);
  }
  return w;
}

function bgMesh(t) {
  ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
  const g = ctx.createRadialGradient(W * .72, H * .28, 40, W * .55, H * .45, 900);
  g.addColorStop(0, 'rgba(255,194,26,.10)'); g.addColorStop(1, 'rgba(14,14,12,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = 'rgba(255,255,255,.035)'; ctx.lineWidth = 2;
  for (let i = 0; i < 12; i++) {
    const y = 80 + i * 90 + Math.sin(t * 1.2 + i) * 4;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y + 40); ctx.stroke();
  }
}

function shotHook(s, t) {
  bgMesh(t);
  veil();
  const L = 120, out = eo(seg(t, 3.85, 4.0));
  ctx.save(); ctx.translate(-out * 1100, 0);
  const k0 = seg(t, 0.08, 0.22);
  ctx.save(); ctx.translate(L, 420); const sc0 = lerp(1.28, 1, back(k0, 1.55)); ctx.scale(sc0, sc0); ctx.globalAlpha = clamp(k0 * 3);
  ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 22; text('一块钱', 0, 0, `900 92px ${F.zh9}`, C.ink); ctx.restore();
  const k1 = seg(t, 0.28, 0.44);
  if (t >= 0.28) {
    ctx.save(); ctx.translate(L, 620); const sc1 = lerp(1.35, 1, back(k1, 1.45)); ctx.scale(sc1, sc1); ctx.globalAlpha = clamp(k1 * 3);
    ctx.fillStyle = C.honey; ctx.fillRect(-18, -118, tw('放着会怎样', `900 110px ${F.zh9}`) + 48, 150);
    text('放着会怎样', 6, 0, `900 110px ${F.zh9}`, C.bg); ctx.restore();
  }
  const ke = eo(seg(t, 0.55, 0.75)); ctx.save(); ctx.globalAlpha = ke; ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = 12;
  text(HOOK_CUE[3] || '一块钱，放着不动会怎样？', L, 760, `500 ${CAP.en}px ${F.n5}`, C.ink); ctx.restore();
  ctx.restore();
  if (t >= 0.45 && out === 0) TX.push({ id: 'hook', text: '一块钱≠起点', x0: L - 20, y0: 340, x1: 1400, y1: 700 });
}

function shotSting(s, t) {
  const off = eio(seg(t, 6.7, 7.0));
  if (off > 0) { bgMesh(t); veil(); }
  else { ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H); }
  const PW = 900, kin = eo(seg(t, 4.02, 4.22));
  ctx.save(); ctx.translate(-off * 1920, 0);
  // right panel abstract flow
  ctx.save(); ctx.beginPath(); ctx.rect(PW, 0, W - PW, H); ctx.clip();
  bgMesh(t + 1.2);
  ctx.fillStyle = 'rgba(255,194,26,.08)'; ctx.fillRect(PW, 0, W - PW, H);
  ctx.restore();
  ctx.save(); ctx.beginPath(); ctx.rect(0, 0, PW * kin, H); ctx.clip();
  ctx.fillStyle = C.honey; ctx.fillRect(0, 0, PW, H);
  ctx.strokeStyle = 'rgba(14,14,12,.13)'; ctx.lineWidth = 2;
  for (let i = 0; i < 18; i++) {
    const y = 120 + i * 54, kl = eo(seg(t, 4.2 + i * .02, 4.5 + i * .02));
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(PW * kl, y); ctx.stroke();
  }
  ctx.strokeStyle = 'rgba(200,40,30,.5)'; [78, 86].forEach(x => {
    const kl = eo(seg(t, 4.25, 4.65)); ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H * kl); ctx.stroke();
  });
  const kt = seg(t, 4.3, 4.45);
  if (t > 4.3) {
    ctx.save(); ctx.translate(124, 520); const sc = lerp(1.35, 1, back(kt, 1.5)); ctx.scale(sc, sc); ctx.globalAlpha = clamp(kt * 3);
    text('分散', 0, 0, `900 168px ${F.zh9}`, C.bg); ctx.restore();
  }
  const k2 = eo(seg(t, 4.75, 4.95)); ctx.save(); ctx.globalAlpha = k2;
  text('DIVERSIFY', 128 + (1 - k2) * 30, 610, `800 58px ${F.n8}`, C.bg); ctx.restore();
  const k3 = eo(seg(t, 4.75, 4.95)); if (k3 > 0) {
    ctx.save(); ctx.globalAlpha = k3; const lab = 'CAPTION NEWS  ·  2026', wl = tw(lab, `800 28px ${F.n8}`);
    ctx.fillStyle = C.bg; ctx.fillRect(128, 670, wl + 70, 52); ctx.fillStyle = C.loss; ctx.beginPath(); ctx.arc(152, 696, 8, 0, 7); ctx.fill();
    text(lab, 172, 707, `800 28px ${F.n8}`, C.honey); ctx.restore();
  }
  ctx.restore(); ctx.restore();
  if (t > 4.3 && off === 0) {
    TX.push({ id: 'title', text: '分散', x0: 120, y0: 380, x1: 840, y1: 580 });
    TX.push({ id: 'title-en', text: 'DIVERSIFY', x0: 120, y0: 560, x1: 840, y1: 640 });
  }
}

function shotSplit(s, t) {
  ledger(t, s.a); ctx.save(); camPush(t, s.a, s.b, 1, 1.025);
  text('三类资产', 120, 220, `900 64px ${F.zh9}`, C.ink);
  text('Stocks · bonds · cash move differently', 122, 270, `500 24px ${F.n5}`, C.grey);
  const mid = W / 2, divK = eo(seg(t, s.a + .15, s.a + .35));
  ctx.fillStyle = C.honey; ctx.fillRect(mid - 2, 300, 4, 520 * divK);
  // left: cash
  const kL = eo(seg(t, s.a + .25, s.a + .55));
  ctx.save(); ctx.globalAlpha = kL;
  ctx.fillStyle = 'rgba(255,194,26,.12)'; ctx.fillRect(120, 320, mid - 160, 460);
  text('股票', 160, 420, `900 72px ${F.zh9}`, C.honey);
  text('STOCKS', 164, 470, `800 28px ${F.n8}`, C.dim);
  num('↑↓', 160, 620, 100, C.ink);
  text('波动大', 160, 700, `900 40px ${F.zh9}`, C.ink);
  ctx.restore();
  // right: house
  const kR = eo(seg(t, s.a + .45, s.a + .75));
  ctx.save(); ctx.globalAlpha = kR;
  ctx.fillStyle = 'rgba(255,74,61,.10)'; ctx.fillRect(mid + 40, 320, mid - 160, 460);
  text('债券', mid + 80, 420, `900 72px ${F.zh9}`, C.loss);
  text('BONDS', mid + 84, 470, `800 28px ${F.n8}`, C.dim);
  num('稳', mid + 80, 620, 100, C.ink);
  text('不同步', mid + 80, 700, `900 40px ${F.zh9}`, C.ink);
  ctx.restore();
  ctx.restore();
  sourceTag(t, s.a + .2, 'PLAN · cashDays / houseDays');
  if (t > s.a + .5) {
    TX.push({ id: 'cash', text: '股票波动大', x0: 140, y0: 360, x1: mid - 40, y1: 720 });
    TX.push({ id: 'house', text: '债券不同步', x0: mid + 60, y0: 360, x1: W - 120, y1: 720 });
    TX.push({ id: 'splitT', text: '三类资产', x0: 110, y0: 170, x1: 420, y1: 240 });
  }
}

const STRESS = [
  ['单一股票', 12, 'one stock'],
  ['单一行业', 18, 'one sector'],
  ['全押一把', 27, 'all-in'],
  ['踩坑放大', 41, 'blow-up'],
];
function shotStress(s, t) {
  ledger(t, s.a); ctx.save(); camPush(t, s.a, s.b, 1, 1.02);
  text('单一押注堆风险', 120, 220, `900 64px ${F.zh9}`, C.ink);
  text('One bet · risk piles in one place', 122, 270, `500 24px ${F.n5}`, C.grey);
  const maxV = 41, x0 = 160, y0 = 340, bw = 1200, bh = 64, gap = 92;
  STRESS.forEach((row, i) => {
    const [zh, v, en] = row;
    const t0 = s.a + .25 + i * .28;
    const k = eo(seg(t, t0, t0 + .35));
    const w = bw * (v / maxV) * k;
    ctx.fillStyle = i === STRESS.length - 1 ? C.loss : (i >= 2 ? 'rgba(255,194,26,.85)' : 'rgba(247,245,239,.28)');
    ctx.fillRect(x0, y0 + i * gap, w, bh);
    ctx.fillStyle = C.ink; text(zh, x0, y0 + i * gap - 12, `900 28px ${F.zh9}`, C.ink);
    text(en, x0 + tw(zh, `900 28px ${F.zh9}`) + 16, y0 + i * gap - 10, `500 22px ${F.n5}`, C.grey);
    if (k > .2) num(String(v), x0 + w + 18, y0 + i * gap + 48, 36, i === STRESS.length - 1 ? C.loss : C.honey);
  });
  ctx.restore();
  sourceTag(t, s.a + .2, 'PLAN · stress series');
  if (t > s.a + .4) TX.push({ id: 'stressT', text: '单一押注堆风险', x0: 110, y0: 170, x1: 620, y1: 240 });
}

function shotTiming(s, t) {
  ledger(t, s.a); ctx.save(); camPush(t, s.a, s.b, 1, 1.03);
  text('多一类少踩坑', 120, 220, `900 64px ${F.zh9}`, C.ink);
  text('Add a class · cut one landmine', 122, 270, `500 24px ${F.n5}`, C.grey);
  const pts = [[0, 78], [1, 70], [2, 55], [3, 32], [4, 18]];
  const x0 = 220, y0 = 780, ww = 1400, hh = 420;
  ctx.strokeStyle = 'rgba(255,255,255,.12)'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0 + ww, y0); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0, y0 - hh); ctx.stroke();
  const drawK = eo(seg(t, s.a + .3, s.a + 1.6));
  ctx.strokeStyle = C.honey; ctx.lineWidth = 6; ctx.lineJoin = 'round';
  ctx.beginPath();
  pts.forEach((p, i) => {
    const x = x0 + (i / (pts.length - 1)) * ww;
    const y = y0 - (p[1] / 80) * hh;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.save(); ctx.setLineDash([ww * drawK, ww]); ctx.stroke(); ctx.restore();
  pts.forEach((p, i) => {
    const appear = eo(seg(t, s.a + .35 + i * .18, s.a + .55 + i * .18));
    if (appear <= 0) return;
    const x = x0 + (i / (pts.length - 1)) * ww;
    const y = y0 - (p[1] / 80) * hh;
    ctx.globalAlpha = appear;
    ctx.fillStyle = i === pts.length - 1 ? C.loss : C.honey;
    ctx.beginPath(); ctx.arc(x, y, i === pts.length - 1 ? 14 : 9, 0, 7); ctx.fill();
    if (i === pts.length - 1) {
      ctx.strokeStyle = C.loss; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(x, y, 26 * appear, 0, 7); ctx.stroke();
      text('踩坑', x + 36, y + 10, `900 40px ${F.zh9}`, C.loss);
    }
    ctx.globalAlpha = 1;
  });
  text('分散', x0, y0 + 48, `500 24px ${F.n5}`, C.grey);
  text('集中', x0 + ww - 60, y0 + 48, `500 24px ${F.n5}`, C.grey);
  ctx.restore();
  sourceTag(t, s.a + .2, 'PLAN · timing contrast');
  if (t > s.a + .5) TX.push({ id: 'timingT', text: '多一类少踩坑', x0: 110, y0: 170, x1: 720, y1: 240 });
}

function shotCash(s, t) {
  ledger(t, s.a); ctx.save(); camPush(t, s.a, s.b, 1, 1.025);
  text('留下余地', 120, 240, `900 72px ${F.zh9}`, C.ink);
  text('Cash buffer is diversification too', 122, 300, `500 26px ${F.n5}`, C.grey);
  const items = [
    ['股票', 'equity', '波动'],
    ['债券', 'bonds', '对冲'],
    ['现金', 'cash', '余地'],
    ['别押一把', 'no all-in', '分散'],
  ];
  items.forEach((row, i) => {
    const [zh, en, tag] = row;
    const t0 = s.a + .25 + i * .22;
    const k = eo(seg(t, t0, t0 + .3));
    const y = 380 + i * 100;
    ctx.save(); ctx.globalAlpha = k; ctx.translate((1 - k) * 80, 0);
    ctx.fillStyle = i === 0 ? 'rgba(255,194,26,.18)' : 'rgba(255,255,255,.04)';
    ctx.fillRect(140, y, 1500, 84);
    ctx.fillStyle = i === 0 ? C.honey : C.ink;
    ctx.fillRect(140, y, 10, 84);
    text(zh, 180, y + 54, `900 40px ${F.zh9}`, C.ink);
    text(en, 780, y + 52, `500 28px ${F.n5}`, C.grey);
    const twTag = tw(tag, `900 28px ${F.zh9}`);
    ctx.fillStyle = i === 0 ? C.honey : 'rgba(247,245,239,.14)';
    ctx.fillRect(1520 - twTag - 36, y + 20, twTag + 36, 44);
    text(tag, 1520 - twTag - 18, y + 52, `900 28px ${F.zh9}`, i === 0 ? C.bg : C.ink);
    ctx.restore();
  });
  ctx.restore();
  sourceTag(t, s.a + .2, 'PLAN · live cash buffer');
  if (t > s.a + .4) TX.push({ id: 'cashT', text: '留下余地', x0: 110, y0: 180, x1: 520, y1: 260 });
}

function shotEnd(s, t) {
  bgMesh(t);
  const kd = eo(seg(t, s.a, s.a + .4));
  ctx.fillStyle = `rgba(14,14,12,${0.55 + .3 * kd})`; ctx.fillRect(0, 0, W, H);
  const g = ctx.createLinearGradient(0, 0, W * .7, 0); g.addColorStop(0, 'rgba(14,14,12,.88)'); g.addColorStop(1, 'rgba(14,14,12,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  const L = 120, k1 = seg(t, s.a + .15, s.a + .3);
  if (t > s.a + .15) {
    ctx.save(); ctx.translate(L, 330); const sc = lerp(1.3, 1, back(k1, 1.5)); ctx.scale(sc, sc); ctx.globalAlpha = clamp(k1 * 3);
    text('分散投资', 0, 0, `900 120px ${F.zh9}`, C.ink); ctx.restore();
  }
  const k2 = eo(seg(t, s.a + .3, s.a + .5)); ctx.save(); ctx.globalAlpha = k2;
  text('Diversify', L + 4, 418, `800 62px ${F.n8}`, C.honey);
  ctx.fillStyle = 'rgba(247,245,239,.5)'; ctx.fillRect(L + 4, 462, 720 * eo(seg(t, s.a + .4, s.a + .8)), 2);
  text('CAPTION NEWS', L + 4, 528, `800 32px ${F.n8}`, C.ink);
  text('· 字幕新闻', L + 4 + tw('CAPTION NEWS', `800 32px ${F.n8}`) + 14, 528, `900 32px ${F.zh9}`, C.ink);
  text('LemoLab × DeepSeek Flash', L + 4, 584, `500 32px ${F.n5}`, C.dim);
  ctx.restore();
  const k3 = eo(seg(t, s.a + .55, s.a + .85)); ctx.save(); ctx.globalAlpha = k3 * .92;
  const CR = [
    'Graphics: caption-news style version diversify-v001 (controller maintainer overlay)',
    'Voice: zh-CN-YunxiNeural · Music: deepseek-controller music_bed soft-pulse (placeholder)',
    'Demo bee footage unused — picture matches 分散 / diversify VO',
    'Locked demo main.js hash unchanged for liudong-controller-e2e scaffold path',
  ];
  CR.forEach((l, i) => text(l, L + 4, 820 + i * 36, `500 22px ${F.n5}`, C.dim));
  ctx.restore();
  if (t > s.a + .3) {
    TX.push({ id: 'endT', text: '分散投资', x0: L, y0: 200, x1: 860, y1: 350 });
    TX.push({ id: 'endE', text: 'Diversify', x0: L, y0: 360, x1: 760, y1: 430 });
    TX.push({ id: 'endS', text: 'CAPTION NEWS · 字幕新闻', x0: L, y0: 490, x1: 760, y1: 540 });
  }
}

let TX = [];
function draw(t) {
  TX = []; ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.filter = 'none';
  ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
  const s = shotAt(t);
  if (s.k === 'hook') shotHook(s, t);
  else if (s.k === 'sting') shotSting(s, t);
  else if (s.k === 'split') shotSplit(s, t);
  else if (s.k === 'stress') shotStress(s, t);
  else if (s.k === 'timing') shotTiming(s, t);
  else if (s.k === 'cash') shotCash(s, t);
  else if (s.k === 'end') shotEnd(s, t);
  for (const c of CAPS) capCard(c, t);
  if (s.k !== 'end' && s.k !== 'hook' && s.k !== 'sting') bug(t);
  if (s.k === 'sting' && t > 6.85) bug(t);
}

window.DUR = DUR;
async function render(t) {
  draw(t);
}
window.render = render;
window.TEXTS = () => TX;
function buildEV() {
  return [
    ...SHOTS.map(s => ({ t: s.a, type: 'cut', k: s.k })),
    ...CAPS.flatMap(c => String(c[2]).split('|').map((_, i) => ({ t: +(c[0] + .04 + i * .12).toFixed(3), type: 'slam', big: c[4] || 1 }))),
    { t: 0.08, type: 'slam' }, { t: 0.28, type: 'hook' },
    { t: 3.5, type: 'sting' }, { t: 3.8, type: 'slam', big: 1.5 },
    { t: 7.0, type: 'whoosh' }, { t: 12.0, type: 'whoosh' }, { t: 17.0, type: 'whoosh' },
    { t: 22.0, type: 'whoosh' }, { t: 27.0, type: 'end' },
  ].sort((a, b) => a.t - b.t);
}
(async () => {
  await Promise.all([[900, 'SC9'], [500, 'SC5'], [800, 'IT8'], [500, 'IT5']].map(([w, f]) => document.fonts.load(`${w} 40px ${f}`)));
  await document.fonts.load(`italic 600 40px IT6I`);
  TL = await (await fetch('timeline.json')).json();
  VO = TL.vo || {};
  HOOK_CUE = [TL.hook.t0, TL.hook.t1, TL.hook.zh, TL.hook.en];
  CAPS = (TL.caps || []).map(c => [c.t0, c.t1, c.zh, c.en, c.big || 1]);
  window.EV = buildEV();
  await render(0);
  window.READY = true;
})();
