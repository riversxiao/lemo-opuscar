// Scenes: pictogram-motion style version finance-v001
// Maintainer overlay: content-driven intro/finale/HUD (EDL + optional window.__BRAND_STRINGS).
// Engine.js / poses / pattern math unchanged. Demo lock path still uses styles/.../demo/scenes.js.
// Opening / chapter cards / event cards / athletics long take / ending / transitions / HUD
(function () {
  const G = window.G, E = G.E, EDL = window.EDL, POSES = window.POSES;
  const { W, H, clamp, lerp, inv, PAL, mix, rgba, F, CELL } = G;
  const BEAT = EDL.BEAT;
  const EJ = new URLSearchParams(location.search).get('lang') === 'ej';
  G.EJ = EJ;
  // Large second language: Chinese version = Chinese; English/Japanese version = Japanese
  const big2 = (s) => (EJ ? s.jpBig || s.jp : s.zh);
  const F2 = (w, px) => (EJ ? F.jp(w, px) : F.zh(w, px));
  const SH = EDL.shots;
  const CARDS = SH.filter((s) => s.kind === 'card');
  const TRACK = SH.filter((s) => s.track);
  const CHAPTERS = SH.filter((s) => s.kind === 'chapter');
  const TOTALN = Math.max(CARDS.length, 1);
  const BR = window.__BRAND_STRINGS || {};
  const brandStr = (k, fallback) => {
    const v = BR[k];
    return (typeof v === 'string' && v) ? v : fallback;
  };
  const TITLE_EN = brandStr('titleEn', (SH.find((x) => x.kind === 'intro') || {}).en || 'DIVERSIFY');
  const TITLE_ZH = brandStr('titleZh', (SH.find((x) => x.kind === 'intro') || {}).zh || '分散投资');
  const YEAR = brandStr('year', '2026');
  const SLOGAN_EN = brandStr('sloganEn', 'STAY DIVERSIFIED');
  const SLOGAN_ZH = brandStr('sloganZh', '鸡蛋不要放进同一个篮子');
  const SLOGAN_JP = brandStr('sloganJp', '分散投資');
  const CREDIT = brandStr('credit', 'LemoLab × DeepSeek Flash');
  SH.forEach((s, i) => (s.i = i));

  // Palette for each card
  for (const s of SH) {
    if (s.kind === 'card') s.pk = s.pal === 'multi' ? G.CYCLE[s.ci % 5] : s.pal;
    else if (s.kind === 'chapter') s.pk = s.pal === 'multi' ? 'purple' : s.pal;
  }

  const lightFg = (pk) => PAL[pk].fg === G.CREAM;
  const colorsFor = (pk, bg) => {
    const P = PAL[pk]; bg = bg || P.t[2];
    return {
      fg: P.fg, bg,
      far: mix(P.fg, bg, 0.42), far2: mix(P.fg, bg, 0.6),
      acc: pk === 'ink' ? PAL.gold.t[2] : lightFg(pk) ? P.t[4] : P.deep,
      line: mix(P.fg, bg, 0.55),
    };
  };
  G.colorsFor = colorsFor;

  // ───────── Figures ─────────
  const bufFig = G.canvas();
  function poseOf(def, u) { return def.pose ? def.pose(u) : G.keyPose(def.keys, u, def.loop); }
  function drawFigUnits(ctx, def, u, C) {
    const J = G.joints(poseOf(def, u));
    ctx.save();
    if (def.fig) { ctx.translate(def.fig.x || 0, def.fig.y || 0); if (def.fig.s) ctx.scale(def.fig.s, def.fig.s); }
    if (def.back) def.back(ctx, J, u, C);
    if (def.second) {
      const J2 = G.joints(def.second(u));
      ctx.save(); const o = def.secondX || [0, 0]; ctx.translate(o[0], o[1]); if (def.secondFace === -1) ctx.scale(-1, 1);
      G.drawFigure(ctx, J2, C.far2, mix(C.far2, C.bg, 0.35)); ctx.restore();
    }
    G.drawFigure(ctx, J, C.fg, C.far);
    if (def.front) def.front(ctx, J, u, C);
    ctx.restore();
  }
  G.drawFigUnits = drawFigUnits;
  // Draw the figure on the stage; asm = assembly progress (0 = cut into horizontal strips and offset, 1 = whole)
  // mask = { x0, x1, y1, f }: keeps the figure layer (including environment such as water surface and ramps) out of the text area, with an f-pixel soft edge
  function stageFigure(ctx, name, u, C, x, y, U, asm = 1, mask) {
    const def = POSES[name];
    const f = bufFig.getContext('2d');
    f.setTransform(1, 0, 0, 1, 0, 0); f.globalCompositeOperation = 'source-over'; f.clearRect(0, 0, W, H);
    f.save(); f.translate(x, y); f.scale(U, U);
    if (def) drawFigUnits(f, def, u, C); else G.drawFigure(f, G.joints({}), C.fg, C.far);
    f.restore();
    if (mask) {
      const fd = mask.f || 90;
      f.globalCompositeOperation = 'destination-in';
      if (mask.x0 != null || mask.x1 != null) {
        const g = f.createLinearGradient(0, 0, W, 0);
        const a0 = mask.x0 != null ? mask.x0 : -1e3, a1 = mask.x1 != null ? mask.x1 : W + 1e3;
        const st = (v) => clamp(v / W, 0, 1);
        g.addColorStop(0, 'rgba(0,0,0,0)');
        if (mask.x0 != null) { g.addColorStop(st(a0 - fd), 'rgba(0,0,0,0)'); g.addColorStop(st(a0), 'rgba(0,0,0,1)'); }
        else g.addColorStop(0, 'rgba(0,0,0,1)');
        if (mask.x1 != null) { g.addColorStop(st(a1), 'rgba(0,0,0,1)'); g.addColorStop(st(a1 + fd), 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0)'); }
        else g.addColorStop(1, 'rgba(0,0,0,1)');
        f.fillStyle = g; f.fillRect(0, 0, W, H);
      }
      if (mask.y1 != null) {
        const g = f.createLinearGradient(0, 0, 0, H);
        g.addColorStop(0, 'rgba(0,0,0,1)'); g.addColorStop(clamp((mask.y1 - fd) / H), 'rgba(0,0,0,1)'); g.addColorStop(clamp(mask.y1 / H), 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0)');
        f.fillStyle = g; f.fillRect(0, 0, W, H);
      }
      f.globalCompositeOperation = 'source-over';
    }
    if (asm >= 0.999) { ctx.drawImage(bufFig, 0, 0); return; }
    const band = 54, k = 1 - asm;
    ctx.save();
    for (let yy = 0, j = 0; yy < H; yy += band, j++) {
      const dx = k * (j % 2 ? 1 : -1) * (90 + ((j * 37) % 5) * 40);
      ctx.globalAlpha = clamp(asm * 3);
      ctx.drawImage(bufFig, 0, yy, W, band, dx, yy, W, band);
    }
    ctx.restore();
  }

  // ───────── Background: pattern with whole-row offsets ─────────
  function patBg(ctx, pk, seed, lt, o = {}) {
    const pat = G.pattern(pk, seed, { spread: o.spread ?? 0.5, density: o.density ?? 0.42 });
    const amp = o.amp ?? 22, sp = o.sp ?? 26;
    G.drawPattern(ctx, pat, (j) => (j % 2 ? 1 : -1) * (lt * sp) + Math.sin(j * 1.7 + seed) * amp + (o.step ? o.step(j) : 0));
  }
  function multiBg(ctx, seed, offs, spread = 0.9) {
    const rows = Math.ceil(H / CELL);
    for (let j = 0; j < rows; j++) {
      const pk = G.CYCLE[(j + seed) % 5];
      const pat = G.pattern(pk, seed + j, { spread, density: 0.5 });
      ctx.save(); ctx.beginPath(); ctx.rect(0, j * CELL, W, CELL); ctx.clip();
      G.drawPattern(ctx, pat, (jj) => (jj === j ? offs(j) : 0));
      ctx.restore();
    }
  }

  // ───────── Text block ─────────
  function textBlock(ctx, s, lt, x, y, o = {}) {
    const P = PAL[s.pk], fg = o.fg || P.fg, dim = o.dim || rgba(fg, 0.72);
    const k = s.beats <= 2 ? 0.7 : 1;
    const maxW = o.maxW || 860;
    const al = o.align || 'left';
    // family / number
    const no = String(s.n).padStart(2, '0');
    const meta = (s.family ? s.family + '   ' : '') + no + ' / ' + TOTALN;
    G.typeText(ctx, meta, x, y - (o.titlePx || 170) - 40, F.mono(22), dim, inv(0.02, 0.3 * k, lt), { ls: '3px', align: al, caret: false });
    // big title
    const px = G.fitFont(ctx, s.title, 'en', 900, o.titlePx || 170, maxW, -0.02);
    G.maskText(ctx, s.title, x, y, F.en(900, px), fg, inv(0.0, 0.5 * k, lt), { ls: -0.02 * px + 'px', align: al });
    // Chinese
    const zpx = EJ ? G.fitFont(ctx, big2(s), 'jp', 900, o.zhPx || 92, maxW, 0.02) : (o.zhPx || 92);
    G.maskText(ctx, big2(s), x, y + zpx + 34, F2(900, zpx), fg, inv(0.08 * k, 0.55 * k, lt), { ls: '2px', align: al });
    // small Japanese line (in the English/Japanese version Japanese is already the big text, so skip this line)
    if (!EJ) G.maskText(ctx, s.jp, x, y + zpx + 96, F.jp(500, 28), dim, inv(0.16 * k, 0.6 * k, lt), { ls: '5px', align: al });
    // corner tag
    if (s.tag) {
      ctx.save(); ctx.font = F.mono(20); ctx.letterSpacing = '3px';
      const tw = ctx.measureText(s.tag).width + 28;
      const p = E.oExp(inv(0.2 * k, 0.5 * k, lt));
      const tx = al === 'right' ? x - tw : al === 'center' ? x - tw / 2 : x;
      const ty = y + zpx + 130;
      ctx.fillStyle = s.tag === 'NEW' ? PAL.red.t[2] : fg; ctx.globalAlpha = p;
      if (s.tag === 'NEW' && s.pk === 'red') ctx.fillStyle = G.CREAM;
      ctx.fillRect(tx, ty, tw * p, 38);
      ctx.fillStyle = s.tag === 'NEW' ? (s.pk === 'red' ? PAL.red.t[2] : G.CREAM) : PAL[s.pk].t[2];
      ctx.fillText(s.tag, tx + 14, ty + 27);
      ctx.restore();
    }
  }

  // ───────── Event card ─────────
  function layoutOf(s) {
    // A run of 2-beat fast cuts uses the same layout; otherwise layouts rotate by order within the chapter
    if (s.beats <= 2) return s.racket ? 'B' : 'A';
    const order = { ball: 'ACBAB', combat: 'CAMBC', power: 'BCA', nature: 'CABAC', asia: 'ABCM', aqua: 'CAB' }[s.chap] || 'ACB';
    return order[s.ci % order.length];
  }
  function cardScene(ctx, s, lt) {
    const P = PAL[s.pk], u = lt / BEAT;
    const L = layoutOf(s);
    const asm = E.o3(inv(0, s.beats <= 2 ? 0.28 : 0.42, lt));
    ctx.fillStyle = P.t[2]; ctx.fillRect(0, 0, W, H);
    patBg(ctx, s.pk, s.i, lt, { spread: 0.42 });
    const discCol = s.pk === 'ink' ? P.t[3] : lightFg(s.pk) ? P.t[1] : P.t[4];
    const C = colorsFor(s.pk, discCol);
    const no = String(s.n).padStart(2, '0');
    const dp = E.o5(inv(0, 0.5, lt));
    if (L === 'A' || L === 'M') {
      const mir = L === 'M';
      const wide = s.water && !mir; // swimming lies horizontal, so move the stage further right
      const cx = mir ? 640 : wide ? 1370 : 1290, cy = 540;
      bigNumber(ctx, no, mir ? 80 : 1850, 1000, P, lt, mir ? 'left' : 'right');
      sun(ctx, cx, cy, 380 * lerp(0.82, 1, dp), discCol, P, lt);
      stageFigure(ctx, s.pose, u, C, cx, cy + 20, 560, asm, mir ? { x1: 1060, f: 110 } : { x0: wide ? 960 : 880, f: 110 });
      textBlock(ctx, s, lt, mir ? 1800 : 130, 610, { align: mir ? 'right' : 'left', maxW: wide ? 700 : 820 });
    } else if (L === 'B') {
      // Title fills the frame, figure sits on top of the text
      const px = G.fitFont(ctx, s.title, 'en', 900, 330, 1760, -0.03);
      const ghost = lightFg(s.pk) ? P.t[1] : P.t[4];
      G.maskText(ctx, s.title, W / 2, 700, F.en(900, px), ghost, inv(0, 0.5, lt), { ls: -0.03 * px + 'px', align: 'center' });
      sun(ctx, W / 2, 470, 250 * lerp(0.8, 1, dp), discCol, P, lt);
      stageFigure(ctx, s.pose, u, C, W / 2, 470, 520, asm, { y1: 850, f: 70 });
      // Bottom info bar
      const k = s.beats <= 2 ? 0.7 : 1;
      const zpx = 80;
      G.maskText(ctx, big2(s), 130, 930, F2(900, zpx), P.fg, inv(0.06 * k, 0.5 * k, lt), { ls: '2px' });
      ctx.font = F2(900, zpx); ctx.letterSpacing = '2px';
      const zw = ctx.measureText(big2(s)).width;
      G.maskText(ctx, s.title, 130 + zw + 40, 930, F.en(800, 44), P.fg, inv(0.1 * k, 0.55 * k, lt), { ls: '0px' });
      if (!EJ) G.maskText(ctx, s.jp, 130 + zw + 42, 876, F.jp(500, 24), rgba(P.fg, 0.7), inv(0.14 * k, 0.6 * k, lt), { ls: '4px' });
      G.typeText(ctx, (s.family ? s.family + '   ' : '') + no + ' / ' + TOTALN + (s.tag ? '   ·   ' + s.tag : ''), 1790, 930, F.mono(22), rgba(P.fg, 0.75), inv(0.05, 0.3 * k, lt), { ls: '3px', align: 'right', caret: false });
    } else if (L === 'C') {
      // Solid panel on the left + pattern and figure on the right
      const pw = 820 * E.o5(inv(0, 0.4, lt));
      const panel = lightFg(s.pk) ? P.t[0] : P.t[4];
      ctx.fillStyle = panel; ctx.fillRect(0, 0, pw, H);
      // Thin line grid on the panel (a small detail that reads as premium)
      ctx.save(); ctx.beginPath(); ctx.rect(0, 0, pw, H); ctx.clip();
      ctx.strokeStyle = rgba(P.fg, 0.1); ctx.lineWidth = 1;
      for (let x = 90; x < 820; x += 90) { ctx.beginPath(); ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, H); ctx.stroke(); }
      bigNumber(ctx, no, 110, 1000, P, lt, 'left', panel);
      textBlock(ctx, s, lt, 110, 560, { maxW: 640, titlePx: 150, zhPx: 84 });
      ctx.restore();
      const cx = 1370, cy = 530;
      sun(ctx, cx, cy, 360 * lerp(0.82, 1, dp), discCol, P, lt);
      stageFigure(ctx, s.pose, u, C, cx, cy + 20, 540, asm, { x0: 820 + 110, f: 110 });
    }
  }
  // Sun disc: solid circle + a slowly sweeping highlight
  function sun(ctx, x, y, r, col, P, lt) {
    G.disc(ctx, x, y, r, col);
    ctx.save(); ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.clip();
    const sx = x - r * 1.6 + (lt * 0.5 % 1) * 0 + E.o3(inv(0.05, 1.1, lt)) * r * 3.2;
    const g = ctx.createLinearGradient(sx - r * 0.5, y - r, sx + r * 0.5, y + r);
    g.addColorStop(0, rgba('#ffffff', 0)); g.addColorStop(0.5, rgba('#ffffff', 0.09)); g.addColorStop(1, rgba('#ffffff', 0));
    ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2);
    ctx.restore();
  }
  // Big outlined number
  function bigNumber(ctx, no, x, y, P, lt, align = 'left') {
    ctx.save();
    ctx.font = F.en(800, 300); ctx.letterSpacing = '-10px'; ctx.textAlign = align;
    ctx.strokeStyle = rgba(P.fg, 0.2 * E.o3(inv(0.05, 0.5, lt))); ctx.lineWidth = 2;
    ctx.strokeText(no, x, y + (1 - E.oExp(inv(0, 0.6, lt))) * 60);
    ctx.restore();
  }

  // ───────── Chapter card ─────────
  function chapterScene(ctx, s, lt) {
    const P = PAL[s.pk], u = lt / BEAT;
    ctx.fillStyle = P.t[2]; ctx.fillRect(0, 0, W, H);
    // In the second bar, whole rows jump one cell every beat (on the drum hits)
    const step = (j) => {
      let v = 0;
      for (let b = 4; b <= 7; b++) v += E.oExp(inv(b, b + 0.35, u)) * (j % 2 ? 1 : -1) * CELL * 0.25;
      return v;
    };
    if (s.pal === 'multi') multiBg(ctx, 3, (j) => (j % 2 ? 1 : -1) * lt * 30 + step(j), 0.95);
    else patBg(ctx, s.pk, 100 + s.i, lt, { spread: s.pk === 'ink' ? 1 : 0.95, density: 0.55, step, sp: 30 });
    // Solid band in the middle (two rows tall)
    const bp = E.o5(inv(0.05, 0.5, lt));
    const band = s.pal === 'multi' ? G.INK : lightFg(s.pk) ? P.t[0] : P.t[4];
    const fg = s.pal === 'multi' ? G.CREAM : P.fg;
    const by = 2 * CELL - 90, bh = 2 * CELL;
    ctx.fillStyle = band; ctx.fillRect(W / 2 - (W / 2) * bp, by, W * bp, bh);
    ctx.save(); ctx.beginPath(); ctx.rect(0, by, W, bh); ctx.clip();
    // Outlined chapter number
    ctx.font = F.en(800, 330); ctx.letterSpacing = '-14px';
    ctx.strokeStyle = rgba(fg, 0.85); ctx.lineWidth = 2.5;
    const ny = by + bh - 34 + (1 - E.oExp(inv(0.1, 0.7, lt))) * 300;
    ctx.strokeText(s.no, 110, ny);
    const tx = 560;
    G.typeText(ctx, 'CHAPTER ' + s.no + '   ·   ' + (s.cname || PAL[s.pk].name).toUpperCase(), tx + 4, by + 70, F.mono(22), rgba(fg, 0.7), inv(0.15, 0.6, lt), { ls: '4px', caret: false });
    const px = G.fitFont(ctx, s.en, 'en', 900, 170, 1250, -0.02);
    G.maskText(ctx, s.en, tx, by + 222, F.en(900, px), fg, inv(0.12, 0.7, lt), { ls: -0.02 * px + 'px' });
    G.maskText(ctx, big2(s), tx + 4, by + 312, F2(900, 66), fg, inv(0.25, 0.8, lt), { ls: '6px' });
    if (!EJ) {
      ctx.font = F.zh(900, 66); ctx.letterSpacing = '6px';
      const zw = ctx.measureText(s.zh).width;
      G.maskText(ctx, s.jp, tx + zw + 40, by + 310, F.jp(500, 28), rgba(fg, 0.7), inv(0.35, 0.9, lt), { ls: '6px' });
    }
    ctx.restore();
    // Thin lines above and below the band
    G.hair(ctx, W / 2 - (W / 2) * bp, by - 10, W * bp, rgba(fg, 0.5), 1, 2);
    G.hair(ctx, W / 2 - (W / 2) * bp, by + bh + 8, W * bp, rgba(fg, 0.5), 1, 2);
  }

  // ───────── Athletics long take ─────────
  const T_OUT = 0.14, T_IN = 0.24; // whip-pan window: before / after the beat
  const TV = 42; // constant drift, px/s
  const SPEC = { sprint: '100M', hurdles: '110M H', relay: '4×100M', distance: '1500M', steeple: '3000M SC', marathon: '42.195 KM', walk: '20 KM', highjump: 'HJ', polevault: 'PV', longjump: 'LJ · TJ', shot: '7.26 KG', discus: '2 KG', hammer: '7.26 KG', javelin: '800 G' };
  const RUNNING = { sprint: 1, hurdles: 1, relay: 1, distance: 0.7, steeple: 0.7, marathon: 0.5, walk: 0.35 };
  function trackCam(t) {
    const T0 = TRACK[0].t0;
    let c = TV * (t - T0);
    for (let k = 1; k < TRACK.length; k++) c += W * E.ioExp(inv(TRACK[k].t0 - T_OUT, TRACK[k].t0 + T_IN, t));
    return c;
  }
  function stationX(k) { // the moment the camera faces the middle of this station
    const s = TRACK[k]; const T0 = TRACK[0].t0;
    return TV * (s.t0 + s.dur / 2 - T0) + k * W;
  }
  function trackScene(ctx, s, lt) {
    const t = s.t0 + lt;
    const P = PAL.red;
    const cam = trackCam(t);
    const ci = TRACK.indexOf(s);
    ctx.fillStyle = P.t[2]; ctx.fillRect(0, 0, W, H);
    // Two rows of large cells in the distance, parallax at different speeds = the whole-row offset of the official graphic
    const rows = [{ y: -80, S: 360, par: 0.28 }, { y: 280, S: 360, par: 0.42 }];
    const T = P.t.map((c) => mix(P.t[2], c, 0.5));
    rows.forEach((R, ri) => {
      const off = cam * R.par;
      const i0 = Math.floor(off / R.S) - 1;
      for (let i = i0; i < i0 + Math.ceil(W / R.S) + 3; i++) {
        const r = G.rng(i * 131 + ri * 7 + 5);
        const pick = () => T[Math.floor(r() * 5)];
        let a = pick(), b = pick(); while (b === a) b = pick();
        G.motif(ctx, Math.floor(r() * 14), Math.round(i * R.S - off), R.y, R.S, [a, b, pick(), T[4]], r);
      }
    });
    // Track
    const ty = 780;
    // Each station's sun (rises behind the track)
    for (let k = Math.max(0, ci - 1); k <= Math.min(TRACK.length - 1, ci + 1); k++) {
      const x = stationX(k) - cam + 1250;
      if (x < -600 || x > W + 600) continue;
      const lk = t - TRACK[k].t0;
      G.disc(ctx, x, ty - 60, 330 * lerp(0.9, 1, E.o5(inv(-0.1, 0.6, lk))), P.t[0]);
    }
    ctx.fillStyle = P.deep; ctx.fillRect(0, ty, W, H - ty);
    const lanes = [0, 44, 98, 162, 236, 320];
    ctx.fillStyle = rgba(G.CREAM, 0.5);
    lanes.forEach((y) => ctx.fillRect(0, ty + y, W, 3));
    // Ticks / start lines on the track, moving with the world; extra scrolling for a sense of speed
    const run = s.pose in RUNNING ? RUNNING[s.pose] : 0.15;
    const roll = cam + t * 900 * run;
    ctx.fillStyle = rgba(G.CREAM, 0.28);
    for (let li = 0; li < lanes.length - 1; li++) {
      const y = ty + lanes[li] + 3, h = lanes[li + 1] - lanes[li] - 3;
      const sp = 260 + li * 70;
      for (let x = -((roll * (1 + li * 0.18)) % sp); x < W; x += sp) ctx.fillRect(x, y + h * 0.42, 56 + li * 10, Math.max(3, h * 0.12));
    }
    // Each station: spec text painted on the track, figure, text
    for (let k = Math.max(0, ci - 1); k <= Math.min(TRACK.length - 1, ci + 1); k++) {
      const st = TRACK[k];
      const ox = stationX(k) - cam;
      if (ox < -W * 1.2 || ox > W * 1.2) continue;
      const lk = t - st.t0;
      ctx.save(); ctx.translate(ox, 0);
      // Track text
      ctx.font = F.en(900, 150); ctx.letterSpacing = '-4px'; ctx.textAlign = 'left';
      ctx.fillStyle = rgba(G.CREAM, 0.12);
      ctx.save(); ctx.translate(820, 1060); ctx.transform(1, 0, -0.35, 1, 0, 0); ctx.fillText(SPEC[st.pose] || '', 0, 0); ctx.restore();
      // Figure
      const C = colorsFor('red', P.t[0]);
      stageFigure(ctx, st.pose, Math.max(0, lk) / BEAT, C, 1250, ty + 10 - 0.46 * 480, 480, E.o3(inv(0, 0.45, lk)), { x0: 900, f: 120 });
      // Text
      if (lk > -0.3) {
        const ss = Object.assign({}, st, { pk: 'red' });
        textBlock(ctx, ss, Math.max(0, lk), 130, 420, { maxW: 820, titlePx: 160, zhPx: 88 });
      }
      ctx.restore();
    }
  }

  // ───────── Opening (finance-v001: scales to shot beats; stats from EDL) ─────────
  const RINGS = ['red', 'purple', 'gold', 'green', 'ochre'];
  function rings(ctx, x, y, r0, gap, w, prog, rot, alpha = 1, cols) {
    for (let i = 0; i < 5; i++) {
      const p = clamp(prog(i));
      if (p <= 0) continue;
      const r = r0 + i * gap;
      const a0 = rot * (i % 2 ? -1 : 1) + i * 1.3 - Math.PI / 2;
      ctx.strokeStyle = cols ? cols[i] : PAL[RINGS[i]].t[2]; ctx.globalAlpha = alpha; ctx.lineWidth = w; ctx.lineCap = 'butt';
      ctx.beginPath(); ctx.arc(x, y, r, a0, a0 + Math.PI * 2 * p); ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  function introScene(ctx, s, lt) {
    // Fit full narrative into this intro shot's beat budget (controller intros are often ~8–12 beats).
    const beats = Math.max(s.beats || 8, 4);
    const u = lt / BEAT;
    const INK = PAL.ink.t[0];
    const p1 = Math.max(2, Math.floor(beats * 0.35));
    const p2 = Math.max(p1 + 2, Math.floor(beats * 0.7));
    const p3 = Math.max(p2 + 1, beats - 1);

    if (u < p1) {
      ctx.fillStyle = INK; ctx.fillRect(0, 0, W, H);
      let pulse = 0;
      for (let b = 0; b < p1; b += 2) pulse += Math.exp(-Math.max(0, u - b) * 5) * (u >= b ? 1 : 0);
      for (let b = 0; b < p1; b += 4) {
        const q = u - b; if (q < 0 || q > 4) continue;
        G.ring(ctx, W / 2, H / 2, 90 + q * 260, 1.5, rgba(PAL.red.t[2], 0.5 * (1 - q / 4)));
      }
      const r = 78 * E.oBack(inv(0, Math.min(1.2, p1 * 0.35), u), 2.2) * (1 + 0.08 * pulse) * (1 - 0.25 * E.i3(inv(p1 - 0.6, p1, u)));
      G.disc(ctx, W / 2, H / 2, r, PAL.red.t[2]);
      const rp = (i) => E.io3(inv(p1 * 0.45 + i * 0.25, p1 * 0.85 + i * 0.15, u));
      const squeeze = 1 - 0.18 * E.i3(inv(p1 - 0.5, p1, u));
      rings(ctx, W / 2, H / 2, 150 * squeeze, 58 * squeeze, 30, rp, u * 0.35);
      G.typeText(ctx, TITLE_ZH + '  ·  ' + TITLE_EN, W / 2, H - 120, F.mono(22), rgba(G.CREAM, 0.7), inv(0.4, Math.min(2.5, p1 * 0.6), u), { ls: '6px', align: 'center', caret: false });
      G.typeText(ctx, 'PORTFOLIO  ·  ASSET ALLOCATION', W / 2, 140, F.mono(22), rgba(G.CREAM, 0.7), inv(p1 * 0.35, p1 * 0.7, u), { ls: '8px', align: 'center', caret: false });
      if (u > p1 - 0.4) { ctx.fillStyle = rgba(G.CREAM, E.i3(inv(p1 - 0.4, p1, u)) * 0.9); ctx.fillRect(0, 0, W, H); }
      return;
    }

    if (u < p2) {
      const q = u - p1;
      const span = Math.max(p2 - p1, 1);
      multiBg(ctx, 11, (j) => {
        const dir = j % 2 ? 1 : -1;
        const inn = (1 - E.oExp(inv(j * 0.08, 0.9 + j * 0.08, q))) * W * 0.9 * dir;
        return clamp(inn, -CELL, CELL) + q * 6 * dir;
      });
      for (let j = 0; j < 6; j++) {
        const k = 1 - E.oExp(inv(j * 0.08, 1.0 + j * 0.08, q));
        if (k <= 0.001) continue;
        const dir = j % 2 ? 1 : -1;
        ctx.fillStyle = G.CREAM;
        if (dir > 0) ctx.fillRect(0, j * CELL, W * k, CELL); else ctx.fillRect(W * (1 - k), j * CELL, W * k, CELL);
      }
      const bp = E.o5(inv(0.2, Math.min(1.4, span * 0.45), q));
      const by = 2 * CELL - 60, bh = 2 * CELL + 120;
      ctx.fillStyle = INK; ctx.fillRect(W / 2 - (W / 2) * bp, by, W * bp, bh);
      ctx.save(); ctx.beginPath(); ctx.rect(0, by, W, bh); ctx.clip();
      G.typeText(ctx, 'PORTFOLIO CONSTRUCTION', W / 2, by + 78, F.mono(24), rgba(G.CREAM, 0.72), inv(0.3, Math.min(1.8, span * 0.5), q), { ls: '10px', align: 'center', caret: false });
      const px = Math.min(168, G.fitFont(ctx, TITLE_EN, 'en', 900, 168, 1600, -0.02));
      G.maskText(ctx, TITLE_EN, W / 2, by + 280, F.en(900, px), G.CREAM, inv(0.2, Math.min(1.6, span * 0.45), q), { ls: '-4px', align: 'center' });
      G.maskText(ctx, TITLE_ZH + '  ·  ' + YEAR, W / 2, by + 380, F2(800, 50), G.CREAM, inv(0.4, Math.min(2.0, span * 0.55), q), { ls: '8px', align: 'center' });
      G.maskText(ctx, SLOGAN_ZH, W / 2, by + 440, F.mono(24), rgba(G.CREAM, 0.65), inv(0.55, Math.min(2.2, span * 0.65), q), { ls: '6px', align: 'center' });
      ctx.restore();
      return;
    }

    if (u < p3) {
      // Count-up: assets / chapters / seconds — from this film's EDL, not Olympics hardcodes
      const span = Math.max(p3 - p2, 1);
      const slot = Math.min(2, Math.floor(((u - p2) / span) * 3));
      const ql = ((u - p2) - (slot * span) / 3) * BEAT;
      const D = [
        { n: TOTALN, pk: 'red', en: 'ASSETS', zh: EJ ? '資産' : '类资产', jp: EJ ? '' : '資産' },
        { n: Math.max(CHAPTERS.length, 1), pk: 'purple', en: 'CHAPTERS', zh: EJ ? '章' : '个章节', jp: EJ ? '' : '章' },
        { n: Math.max(1, Math.round(EDL.DUR || window.DUR || beats * BEAT)), pk: 'green', en: 'SECS', zh: EJ ? '秒' : '秒', jp: EJ ? '' : '秒' },
      ][slot];
      const P = PAL[D.pk];
      ctx.fillStyle = P.t[2]; ctx.fillRect(0, 0, W, H);
      patBg(ctx, D.pk, 40 + slot, ql, { spread: 0.9, density: 0.5, amp: 0 });
      const bp = E.o5(inv(0, 0.35, ql));
      ctx.fillStyle = P.t[2]; ctx.fillRect(0, CELL * 0.5 + (1 - bp) * CELL * 2, W, (H - CELL) * bp);
      ctx.fillStyle = P.t[1]; ctx.fillRect(0, CELL * 0.5 + (1 - bp) * CELL * 2, W, 3);
      const cnt = Math.round(D.n * E.o3(inv(0, 0.5, ql)));
      ctx.save();
      ctx.font = F.en(900, 520); ctx.letterSpacing = '-24px'; ctx.textAlign = 'right'; ctx.fillStyle = P.fg;
      const nx = 1060;
      ctx.beginPath(); ctx.rect(0, 180, W, 720); ctx.clip();
      ctx.fillText(String(cnt), nx, 740 + (1 - E.oExp(inv(0, 0.35, ql))) * 500);
      ctx.restore();
      G.maskText(ctx, D.en, 1130, 560, F.en(900, 150), P.fg, inv(0.05, 0.45, ql), { ls: '-3px' });
      G.maskText(ctx, D.zh, 1136, 660, F2(900, 64), P.fg, inv(0.1, 0.5, ql), { ls: '4px' });
      G.maskText(ctx, D.jp, 1138, 722, F.jp(500, 28), rgba(P.fg, 0.7), inv(0.15, 0.55, ql), { ls: '6px' });
      return;
    }

    // Ready cue (no race-start metaphor)
    const q = u - p3;
    ctx.fillStyle = INK; ctx.fillRect(0, 0, W, H);
    const lines = [[0, 'READY', EJ ? '準備' : '准备'], [1.2, 'ALLOCATE', EJ ? '配分' : '配置']];
    for (const [b, en, zh] of lines) {
      if (q < b || q >= b + 1.15) continue;
      const l = (q - b) * BEAT;
      G.maskText(ctx, en, W / 2, 560, F.en(900, b ? 200 : 170), G.CREAM, inv(0, 0.3, l), { ls: '-4px', align: 'center' });
      G.maskText(ctx, zh, W / 2, 680, F2(800, 54), rgba(G.CREAM, 0.8), inv(0.05, 0.35, l), { ls: '20px', align: 'center' });
    }
    for (let i = 0; i < 5; i++) {
      const on = q >= i * 0.35;
      ctx.fillStyle = on ? PAL[RINGS[i]].t[2] : rgba(G.CREAM, 0.08);
      ctx.fillRect(W / 2 - 170 + i * 70, 800, 50, 12);
    }
  }

  // ───────── Ending (finance-v001: grid sized to card count) ─────────
  function finaleGrid(n) {
    // Compact catalogue wall for N items (+ sun / ALL-N cells)
    const need = Math.max(n + 2, 4);
    let cols = Math.ceil(Math.sqrt(need * 1.6));
    cols = Math.max(3, Math.min(cols, 6));
    let rows = Math.ceil(need / cols);
    rows = Math.max(2, Math.min(rows, 4));
    while (cols * rows < need && rows < 5) rows++;
    while (cols * rows < need && cols < 8) cols++;
    return { cols, rows };
  }
  function finaleScene(ctx, s, lt) {
    const beats = Math.max(s.beats || 12, 6);
    const u = lt / BEAT;
    const GRID = finaleGrid(TOTALN);
    const cw = W / GRID.cols, ch = H / GRID.rows;
    const firsts = [];
    for (const c of CARDS) if (!firsts.find((f) => f.n === c.n)) firsts.push(c);
    const gridBeats = Math.max(3, Math.floor(beats * 0.55));

    if (u < gridBeats) {
      ctx.fillStyle = PAL.ink.t[0]; ctx.fillRect(0, 0, W, H);
      const zoom = lerp(1, 0.92, E.io3(inv(gridBeats * 0.55, gridBeats * 0.85, u)));
      const gap = 10 * E.io3(inv(gridBeats * 0.55, gridBeats * 0.85, u));
      const collapse = E.i3(inv(gridBeats * 0.82, gridBeats, u));
      ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(zoom, zoom); ctx.translate(-W / 2, -H / 2);
      const midR = Math.floor(GRID.rows / 2), midC = Math.floor(GRID.cols / 2);
      let idx = 0;
      const cells = GRID.cols * GRID.rows;
      for (let r = 0; r < GRID.rows; r++) for (let c = 0; c < GRID.cols; c++) {
        const special = (r === midR && c === midC) ? 'sun' : (r === midR && c === midC - 1) ? 'yr' : null;
        const card = special ? null : firsts[idx++];
        const order = special ? -1.5 : idx - 1;
        const t0 = (order + 1.5) * (gridBeats * 0.65 / Math.max(cells, 1));
        const fp = E.o3(inv(t0, t0 + 0.7, u));
        const allRed = E.io3(inv(gridBeats * 0.75 + (Math.abs(c - midC) + Math.abs(r - midR)) * 0.12, gridBeats * 0.9 + (Math.abs(c - midC) + Math.abs(r - midR)) * 0.12, u));
        let x = c * cw + gap / 2, y = r * ch + gap / 2, w = cw - gap, h = ch - gap;
        if (collapse > 0) {
          const cx = x + w / 2, cy = y + h / 2;
          const k = 1 - collapse;
          x = lerp(W / 2, cx, k) - (w * k) / 2; y = lerp(H / 2, cy, k) - (h * k) / 2; w *= k; h *= k;
        }
        if (fp <= 0) continue;
        const pk = card ? card.pk : 'red';
        const P = PAL[pk];
        ctx.save();
        ctx.translate(x + w / 2, y + h / 2); ctx.scale(1, fp < 1 ? Math.max(0.02, fp) : 1); ctx.translate(-(x + w / 2), -(y + h / 2));
        const bg = mix(P.t[(c + r) % 2 ? 2 : 1], PAL.red.t[2], allRed);
        ctx.fillStyle = bg; ctx.fillRect(x, y, w, h);
        ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
        const fg = allRed > 0.5 ? G.CREAM : P.fg;
        if (card) {
          const def = POSES[card.pose];
          const C = colorsFor(pk, bg); C.fg = fg; C.far = mix(fg, bg, 0.42); C.far2 = mix(fg, bg, 0.6); C.line = mix(fg, bg, 0.55);
          if (allRed > 0.5) C.acc = PAL.red.t[4];
          ctx.save(); ctx.translate(x + w / 2, y + h * 0.5); const U = h * 0.66 * (w / (cw - gap || cw)); ctx.scale(U, U);
          if (def) drawFigUnits(ctx, def, def.iconU ?? 1, C); else G.drawFigure(ctx, G.joints({}), C.fg, C.far);
          ctx.restore();
          ctx.font = F.mono(Math.max(1, 13 * w / cw)); ctx.letterSpacing = '1px'; ctx.fillStyle = rgba(fg, 0.75);
          if (collapse < 0.3) ctx.fillText(String(card.n).padStart(2, '0') + '  ' + String(card.en || '').split(' · ')[0], x + 12, y + h - 14);
        } else if (special === 'sun') {
          G.disc(ctx, x + w / 2, y + h / 2, h * 0.28, allRed > 0.5 ? G.CREAM : PAL.red.t[2]);
        } else if (special === 'yr') {
          ctx.font = F.en(900, Math.max(28, 54 * w / cw)); ctx.letterSpacing = '-2px'; ctx.textAlign = 'center'; ctx.fillStyle = G.CREAM;
          ctx.fillText('ALL ' + TOTALN, x + w / 2, y + h / 2 + 18 * w / cw);
        }
        ctx.restore();
      }
      ctx.restore();
      if (u > gridBeats * 0.88) {
        const rr = 150 * E.oExp(inv(gridBeats * 0.9, gridBeats, u));
        G.disc(ctx, W / 2, H / 2, rr, PAL.red.t[2]);
      }
      return;
    }

    // Slogan + end card — always reachable within short finale shots
    const q = u - gridBeats;
    const sloganSpan = Math.max(beats - gridBeats, 2);
    ctx.fillStyle = G.CREAM; ctx.fillRect(0, 0, W, H);
    const up = E.io3(inv(0.4, Math.min(2.2, sloganSpan * 0.45), q));
    const sx = W / 2, sy = lerp(H / 2, 330, up);
    const sc = lerp(1, 0.62, up);
    G.disc(ctx, sx, sy, 150 * sc, PAL.red.t[2]);
    rings(ctx, sx, sy, 210 * sc, 48 * sc, 24 * sc, (i) => E.io3(inv(i * 0.25, 1.6 + i * 0.25, q)), q * 0.18 + 0.5);
    const split = Math.max(1.2, sloganSpan * 0.55);
    if (q < split) {
      const l = Math.max(0, q - 0.3) * BEAT;
      G.maskText(ctx, SLOGAN_EN, W / 2, 720, F.en(900, 120), G.INK, inv(0, 0.8, l), { ls: '-3px', align: 'center' });
      G.maskText(ctx, SLOGAN_JP, W / 2, 815, F.jp(700, 48), G.INK, inv(0.3, 1.0, l), { ls: '14px', align: 'center' });
      if (!EJ) G.maskText(ctx, SLOGAN_ZH, W / 2, 885, F.zh(500, 34), rgba(G.INK, 0.7), inv(0.5, 1.2, l), { ls: '18px', align: 'center' });
    } else {
      const l = (q - split) * BEAT;
      G.maskText(ctx, TITLE_EN, W / 2, 700, F.en(900, 120), G.INK, inv(0, 0.5, l), { ls: '-3px', align: 'center' });
      G.maskText(ctx, TITLE_ZH + '   ·   ' + YEAR, W / 2, 780, F.mono(26), rgba(G.INK, 0.7), inv(0.15, 0.7, l), { ls: '6px', align: 'center' });
      G.maskText(ctx, SLOGAN_ZH, W / 2, 850, F2(700, 36), G.INK, inv(0.25, 0.9, l), { ls: '8px', align: 'center' });
      for (let i = 0; i < 5; i++) {
        const p = E.o5(inv(0.2 + i * 0.05, 0.9 + i * 0.05, l));
        ctx.fillStyle = PAL[RINGS[i]].t[2]; ctx.fillRect(W / 2 - 300 + i * 120, 920, 110 * p, 10);
      }
      G.maskText(ctx, CREDIT, W / 2, 1000, F.mono(24), rgba(G.INK, 0.6), inv(0.4, 1.0, l), { ls: '4px', align: 'center' });
      const fo = E.io(inv((s.dur || beats * BEAT) - 1.0, (s.dur || beats * BEAT) - 0.05, lt));
      if (fo > 0) { ctx.fillStyle = rgba('#000000', fo); ctx.fillRect(0, 0, W, H); }
    }
  }

  // ───────── HUD (persistent overlay) ─────────
  function hud(ctx, s, lt) {
    if (s.kind !== 'card' && s.kind !== 'chapter') return;
    const pk = s.pk;
    const fg = s.kind === 'chapter' && s.pal === 'multi' ? G.CREAM : PAL[pk].fg;
    const a = 0.8;
    ctx.save();
    ctx.font = F.mono(17); ctx.letterSpacing = '3px'; ctx.fillStyle = rgba(fg, a);
    ctx.textAlign = 'left';
    ctx.fillText(TITLE_EN, 64, 70); ctx.fillText(TITLE_ZH, 64, 96);
    ctx.textAlign = 'right';
    const ch = SH.filter((x) => x.kind === 'chapter' && x.t0 <= s.t0).pop();
    if (ch) ctx.fillText('CH.' + ch.no + '  ' + (ch.en || ch.cname || ''), W - 64, 70);
    ctx.fillText('BPM ' + Math.round(EDL.BPM || 150), W - 64, 96);
    const x0 = 64, x1 = W - 64, y = H - 58;
    const cur = s.kind === 'card' ? s.n : 0;
    const ticks = Math.max(TOTALN, 1);
    const denom = Math.max(ticks - 1, 1);
    for (let i = 1; i <= ticks; i++) {
      const x = lerp(x0, x1, (i - 1) / denom);
      const done = i < cur, now = i === cur;
      ctx.fillStyle = rgba(fg, now ? 1 : done ? 0.75 : 0.28);
      ctx.fillRect(Math.round(x) - (now ? 2 : 1), y - (now ? 14 : 6), now ? 4 : 2, now ? 20 : 12);
    }
    ctx.restore();
  }

  // ───────── Scene dispatch ─────────
  function drawShot(ctx, s, lt) {
    ctx.save();
    if (s.kind === 'intro') introScene(ctx, s, lt);
    else if (s.kind === 'chapter') chapterScene(ctx, s, lt);
    else if (s.kind === 'finale') finaleScene(ctx, s, lt);
    else if (s.track) trackScene(ctx, s, lt);
    else cardScene(ctx, s, lt);
    ctx.restore();
  }

  // ───────── Transitions ─────────
  const TA = 0.12, TB = 0.26;
  function transType(a, b) {
    if (a.track && b.track) return 'none';
    if (a.kind === 'intro') return 'rows';
    if (b.kind === 'chapter') return 'rows';
    if (b.kind === 'finale') return 'quarter';
    if (a.kind === 'chapter') return 'cols';
    if (b.beats <= 2 || a.beats <= 2) return b.racket ? 'slide' : 'cols';
    return ['quarter', 'rows', 'iris', 'flip', 'cols'][b.ci % 5];
  }
  const bufA = G.canvas(), bufB = G.canvas();
  function composite(ctx, type, p, A, B, b) {
    const S = CELL;
    if (type === 'rows') {
      ctx.drawImage(A, 0, 0);
      for (let j = 0; j < 6; j++) {
        const pj = E.ioExp(clamp(p * 1.5 - j * 0.1));
        const dir = j % 2 ? 1 : -1;
        ctx.drawImage(A, 0, j * S, W, S, dir * W * 0.25 * pj, j * S, W, S);
        ctx.drawImage(B, 0, j * S, W, S, -dir * W * (1 - pj), j * S, W, S);
      }
    } else if (type === 'cols') {
      const cw = 240;
      ctx.drawImage(A, 0, 0);
      for (let i = 0; i < 8; i++) {
        const pj = E.ioExp(clamp(p * 1.5 - i * 0.07));
        const dir = i % 2 ? 1 : -1;
        ctx.drawImage(B, i * cw, 0, cw, H, i * cw, -dir * H * (1 - pj), cw, H);
      }
    } else if (type === 'slide') {
      const pj = E.ioExp(p);
      ctx.drawImage(A, -W * 0.3 * pj, 0);
      ctx.drawImage(B, W * (1 - pj), 0);
      ctx.fillStyle = rgba('#000', 0.15 * (1 - Math.abs(pj - 0.5) * 2)); ctx.fillRect(W * (1 - pj) - 8, 0, 8, H);
    } else if (type === 'quarter') {
      ctx.drawImage(A, 0, 0);
      ctx.save(); ctx.beginPath();
      for (let j = 0; j < 6; j++) for (let i = 0; i < 11; i++) {
        const d = (i + j) * 0.035;
        const r = S * 1.42 * E.o3(clamp((p - d) / 0.55));
        if (r <= 0) continue;
        const corner = (i + j) % 4;
        const cx = i * S + (corner === 1 || corner === 2 ? S : 0), cy = j * S + (corner >= 2 ? S : 0);
        ctx.save(); ctx.rect(i * S, j * S, S, S); ctx.restore();
        ctx.moveTo(cx, cy); ctx.arc(cx, cy, r, 0, Math.PI * 2);
      }
      ctx.clip();
      // Should take effect only inside each cell: clipping again with the cell rectangle is awkward, so a size limit approximates it (r ≤ 1.42S covers this cell and spills slightly into neighbours, which looks more organic)
      ctx.drawImage(B, 0, 0);
      ctx.restore();
    } else if (type === 'iris') {
      ctx.drawImage(A, 0, 0);
      const cx = b.x || W / 2, cy = b.y || H / 2;
      const r = 1300 * E.ioExp(p);
      ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.clip(); ctx.drawImage(B, 0, 0); ctx.restore();
      G.ring(ctx, cx, cy, r, 22 * (1 - p), b.ring || G.CREAM);
    } else if (type === 'flip') {
      const cols = 11, rows = 6;
      // Behind the flipping card, first lay a darkened B so no black shows when the card is edge-on
      ctx.drawImage(B, 0, 0); ctx.fillStyle = rgba('#000', 0.45); ctx.fillRect(0, 0, W, H);
      for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
        const d = ((i * 0.6 + j) / (cols * 0.6 + rows)) * 0.5;
        const pc = clamp((p - d) / 0.5);
        const src = pc < 0.5 ? A : B;
        const sx = Math.abs(Math.cos(pc * Math.PI));
        const x = i * S, y = j * S;
        const w = S * sx;
        ctx.drawImage(src, x, y, S, S, x + (S - w) / 2, y, Math.max(1, w), S);
        if (pc > 0 && pc < 1) { ctx.fillStyle = rgba('#000', 0.35 * (1 - sx)); ctx.fillRect(x + (S - w) / 2, y, w, S); }
      }
    }
  }

  // ───────── Frame ─────────
  function shotAt(t) {
    let lo = 0, hi = SH.length - 1;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (SH[m].t0 <= t) lo = m; else hi = m - 1; }
    return lo;
  }
  function frame(ctx, t) {
    t = clamp(t, 0, EDL.DUR - 1e-6);
    let i = shotAt(t);
    let s = SH[i];
    // Which transition window does this fall in?
    let tr = null;
    const nx = SH[i + 1];
    if (nx && t >= nx.t0 - TA) tr = [s, nx];
    else if (i > 0 && t < s.t0 + TB) tr = [SH[i - 1], s];
    if (tr) {
      const [a, b] = tr, type = transType(a, b);
      if (type !== 'none') {
        const p = clamp((t - (b.t0 - TA)) / (TA + TB));
        const ca = bufA.getContext('2d'), cb = bufB.getContext('2d');
        ca.setTransform(1, 0, 0, 1, 0, 0); cb.setTransform(1, 0, 0, 1, 0, 0);
        drawShot(ca, a, t - a.t0); drawShot(cb, b, Math.max(0, t - b.t0));
        const info = { x: a.kind === 'card' && !a.track ? (layoutOf(a) === 'B' ? W / 2 : layoutOf(a) === 'M' ? 640 : layoutOf(a) === 'C' ? 1370 : 1290) : W / 2, y: 540, ring: PAL[b.pk || 'red'] ? PAL[b.pk || 'red'].t[4] : G.CREAM };
        composite(ctx, type, p, bufA, bufB, info);
        hud(ctx, p < 0.5 ? a : b, t - (p < 0.5 ? a : b).t0);
        return;
      }
      s = t < b.t0 ? a : b;
    }
    drawShot(ctx, s, t - s.t0);
    hud(ctx, s, t - s.t0);
  }
  // Moments that need motion blur: transition windows, athletics whip pans, opening impacts
  function isFast(t) {
    const i = shotAt(t), s = SH[i], nx = SH[i + 1];
    if (nx && t >= nx.t0 - TA - 0.02) return true;
    if (i > 0 && t < s.t0 + TB + 0.02) return true;
    return false;
  }
  const bufSub = G.canvas();
  G.renderFrame = function (ctx, t) {
    if (!isFast(t)) { ctx.setTransform(1, 0, 0, 1, 0, 0); frame(ctx, t); return; }
    const N = 5, shutter = 0.5 / 60;
    const sc = bufSub.getContext('2d');
    for (let k = 0; k < N; k++) {
      sc.setTransform(1, 0, 0, 1, 0, 0);
      frame(sc, t - shutter / 2 + (shutter * k) / (N - 1));
      ctx.globalAlpha = 1 / (k + 1);
      ctx.drawImage(bufSub, 0, 0);
    }
    ctx.globalAlpha = 1;
  };
  G.layoutOf = layoutOf;
})();
