// Scenes: pictogram-motion style version finance-v003 (v002 + per-line visual scene library from content/viz.json;
// shots with s.viz draw their own vector scene; finale = last line's scene + end-card tail)
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
  // VaR-style loss threshold label (金融专家 2026-10-30): 「亏损门槛 <金额>」, not the bare 门槛+amount.
  // brand.thresholdLabel overrides the whole label; brand.thresholdAmount just the amount (default 100万).
  const LOSS_TH = brandStr('thresholdLabel', '亏损门槛 ' + brandStr('thresholdAmount', '100万'));
  const CREDIT = brandStr('credit', 'LemoLab × DeepSeek Flash');
  // finance-v002: per-term labels (plan.brand → brand_strings.json). Explicit "" hides a line.
  const brandOpt = (k, fallback) => (typeof BR[k] === 'string' ? BR[k] : fallback);
  const EYEBROW = brandStr('eyebrow', 'PORTFOLIO CONSTRUCTION');
  const EYEBROW_TOP = brandStr('eyebrowTop', BR.eyebrow || 'PORTFOLIO  ·  ASSET ALLOCATION');
  const END_TITLE = brandStr('endTitle', TITLE_EN);
  const END_LINE = brandOpt('endLine', TITLE_ZH + '   ·   ' + YEAR);
  // Never uppercase a mixed-case acronym (VaR ≠ VAR, the vector-autoregression model).
  const KEEP = new Set(Array.isArray(BR.keepCase) ? BR.keepCase : []);
  const isMixed = (w) => /[a-z]/.test(w) && /^.+[A-Z]/.test(w) && /[A-Z]/.test(w.slice(1));
  const upKeep = (str) => String(str || '').replace(/[A-Za-z][A-Za-z0-9]*/g, (w) => (KEEP.has(w) || isMixed(w) ? w : w.toUpperCase()));
  G.upKeep = upKeep;
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
    G.typeText(ctx, 'CHAPTER ' + s.no + '   ·   ' + upKeep(s.cname || PAL[s.pk].name), tx + 4, by + 70, F.mono(22), rgba(fg, 0.7), inv(0.15, 0.6, lt), { ls: '4px', caret: false });
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
      G.typeText(ctx, EYEBROW_TOP, W / 2, 140, F.mono(22), rgba(G.CREAM, 0.7), inv(p1 * 0.35, p1 * 0.7, u), { ls: '8px', align: 'center', caret: false });
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
      G.typeText(ctx, EYEBROW, W / 2, by + 78, F.mono(24), rgba(G.CREAM, 0.72), inv(0.3, Math.min(1.8, span * 0.5), q), { ls: '10px', align: 'center', caret: false });
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
      if (brandOpt('sloganJp', SLOGAN_JP)) G.maskText(ctx, brandOpt('sloganJp', SLOGAN_JP), W / 2, 815, F.jp(700, 48), G.INK, inv(0.3, 1.0, l), { ls: '14px', align: 'center' });
      if (!EJ) G.maskText(ctx, SLOGAN_ZH, W / 2, 885, F.zh(500, 34), rgba(G.INK, 0.7), inv(0.5, 1.2, l), { ls: '18px', align: 'center' });
    } else {
      const l = (q - split) * BEAT;
      const epx = Math.min(120, G.fitFont(ctx, END_TITLE, 'en', 900, 120, 1500, -0.02));
      G.maskText(ctx, END_TITLE, W / 2, 700, F.en(900, epx), G.INK, inv(0, 0.5, l), { ls: '-3px', align: 'center' });
      if (END_LINE) G.maskText(ctx, END_LINE, W / 2, 800, F2(700, 48), G.INK, inv(0.15, 0.7, l), { ls: '6px', align: 'center' });
      if (!BR.endLine) G.maskText(ctx, SLOGAN_ZH, W / 2, 870, F2(700, 36), G.INK, inv(0.25, 0.9, l), { ls: '8px', align: 'center' });
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
    if (s.viz) { if (!(s.kind === 'finale' && lt >= (s.vizDur || s.dur))) vizHud(ctx, s, lt); return; }
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


  // ═════════ finance-v003: per-line visual scene library (shot.viz from content/viz.json) ═════════
  // Every line gets its own vector scene + motion (no sport poses). Data (curves, steps) comes from
  // viz_pick.py so the content-visual lint checks exactly what is drawn. Local canvas only.
  const VIZ = (G.VIZ = {});
  const VPAL = { plunge: 'red', swing_label: 'purple', step_blocks: 'green', waves: 'gold', boat: 'ochre', mirror_updown: 'ink', coaster: 'cream' };
  const vcol = (sc) => {
    const k = VPAL[sc] || 'ink';
    if (k === 'cream') return { bg: G.CREAM, fg: G.INK, dim: rgba(G.INK, 0.55), acc: PAL.red.t[2], soft: '#e9e0cf', alt: PAL.purple.t[1] };
    const P = PAL[k];
    return { bg: P.t[2], fg: P.fg, dim: rgba(P.fg, 0.6), acc: k === 'ink' ? PAL.gold.t[2] : lightFg(k) ? P.t[4] : P.deep, soft: P.t[1], alt: k === 'ink' ? PAL.red.t[3] : (lightFg(k) ? G.INK : G.CREAM), deep: P.deep };
  };
  // Curve helper: pts in grid cells (y up); reveal 0..1; returns the head point
  function curvePath(ctx, pts, x0, x1, yc, cell, rev = 1, off = 0) {
    const n = pts.length, k = clamp(rev) * (n - 1);
    let hx = x0, hy = yc - pts[0] * cell;
    ctx.beginPath();
    for (let i = 0; i <= Math.ceil(k) && i < n; i++) {
      const f = Math.min(i, k);
      const a = pts[Math.floor(f)], b = pts[Math.min(n - 1, Math.floor(f) + 1)];
      const v = lerp(a, b, f - Math.floor(f));
      const x = lerp(x0, x1, f / (n - 1)), y = yc - (v + off) * cell;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      hx = x; hy = y;
    }
    return [hx, hy];
  }
  function strokeCurve(ctx, pts, x0, x1, yc, cell, rev, w, col, off = 0) {
    ctx.save(); ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = col; ctx.lineWidth = w;
    const h = curvePath(ctx, pts, x0, x1, yc, cell, rev, off); ctx.stroke(); ctx.restore(); return h;
  }
  function gridLines(ctx, x0, x1, y0, y1, cell, col) {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 1.5;
    for (let x = x0; x <= x1 + 1; x += cell) { ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y1); ctx.stroke(); }
    for (let y = y0; y <= y1 + 1; y += cell) { ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke(); }
    ctx.restore();
  }
  function tag(ctx, text, x, y, C, p, o = {}) { // pill label
    if (p <= 0) return;
    ctx.save(); ctx.font = o.font || F.zh(900, o.px || 40); ctx.letterSpacing = '2px';
    const w = ctx.measureText(text).width + 44, h = (o.px || 40) + 26;
    ctx.globalAlpha = clamp(p * 2);
    const sc = E.oBack(clamp(p)); ctx.translate(x, y); ctx.scale(sc, sc);
    ctx.fillStyle = o.bg || C.fg; ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, h / 2); ctx.fill();
    ctx.fillStyle = o.fg || C.bg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, 0, 2);
    ctx.restore();
  }
  function arrowV(ctx, x, ya, yb, col, w = 6, p = 1) { // double-headed vertical bracket
    const yb2 = lerp(ya, yb, clamp(p));
    ctx.save(); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = w; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x, ya); ctx.lineTo(x, yb2); ctx.stroke();
    const hd = (y, d) => { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 16, y - 22 * d); ctx.lineTo(x + 16, y - 22 * d); ctx.closePath(); ctx.fill(); };
    if (p > 0.95) { hd(ya, Math.sign(ya - yb) || 1); hd(yb2, Math.sign(yb - ya) || 1); }
    ctx.restore();
  }
  // Caption block (term / key word for this line): top-left, inside title-safe
  function vizCaption(ctx, s, lt, C, o = {}) {
    const x = o.x ?? 150, y = o.y ?? 250;
    const zh = s.zh || '', en = s.en || '';
    const zpx = Math.min(108, G.fitFont(ctx, zh, 'zh', 900, 108, 900, 0.02));
    G.maskText(ctx, zh, x, y, F.zh(900, zpx), C.fg, inv(0.05, 0.6, lt), { ls: '3px', align: o.align || 'left' });
    if (en) G.typeText(ctx, upKeep(en), x, y + 58, F.mono(26), C.dim, inv(0.2, 0.8, lt), { ls: '4px', align: o.align || 'left', caret: false });
  }
  function shake(lt, at, amp = 14) { const k = Math.max(0, 1 - Math.abs(lt - at) / 0.35); return [Math.sin(lt * 71) * amp * k, Math.cos(lt * 53) * amp * 0.6 * k]; }

  VIZ.plunge = (ctx, s, lt, C) => {
    const d = s.viz.data, D = s.vizDur, cell = 110, x0 = 260, x1 = 1660, yc = 560;
    gridLines(ctx, 240, 1680, 340, 1000, cell, rgba(C.fg, 0.1));
    const rev = E.io(inv(0.1, D * 0.72, lt));
    const dropT = 0.1 + d.dropAt * (D * 0.72 - 0.1);
    const [sx, sy] = shake(lt, dropT + 0.25);
    ctx.save(); ctx.translate(sx, sy);
    const hm = strokeCurve(ctx, d.curves.market, x0, x1, yc, cell, rev, 7, rgba(C.fg, 0.85));
    const hs = strokeCurve(ctx, d.curves.stock, x0, x1, yc, cell, rev, 22, G.INK);
    G.disc(ctx, hs[0], hs[1], 18, G.INK); G.disc(ctx, hm[0], hm[1], 9, C.fg);
    const lp = inv(0.3, 0.9, lt);
    tag(ctx, '大盘', 330, yc - 170, C, lp, { px: 34 });
    tag(ctx, '个股', 330, yc + 170, C, inv(0.45, 1.05, lt), { px: 34, bg: G.INK, fg: C.fg });
    if (rev > 0.98) {
      const p = E.o3(inv(D * 0.74, D * 0.92, lt));
      arrowV(ctx, x1 + 40, hm[1], hs[1], C.fg, 6, p);
      tag(ctx, '一大截', x1 - 120, (hm[1] + hs[1]) / 2, C, inv(D * 0.8, D * 0.95, lt), { px: 38 });
    }
    ctx.restore();
    vizCaption(ctx, s, lt, C);
  };

  VIZ.swing_label = (ctx, s, lt, C) => {
    const cell = 90, x0 = 200, x1 = 1720, yc = 640;
    const am = Math.max(...s.viz.data.curves.market.map(Math.abs)), as = Math.max(...s.viz.data.curves.stock.map(Math.abs));
    const ph = lt * 1.6, N = 64;
    const grow = E.o3(inv(0.1, 1.0, lt));
    const mk = Array.from({ length: N }, (_, i) => am * grow * Math.sin(i / (N - 1) * Math.PI * 5 - ph));
    const st = Array.from({ length: N }, (_, i) => as * grow * Math.sin(i / (N - 1) * Math.PI * 5 - ph));
    ctx.save(); ctx.strokeStyle = rgba(C.fg, 0.18); ctx.lineWidth = 2; ctx.setLineDash([10, 14]);
    ctx.beginPath(); ctx.moveTo(x0, yc); ctx.lineTo(x1, yc); ctx.stroke(); ctx.restore();
    strokeCurve(ctx, mk, x0, x1, yc, cell, 1, 7, rgba(C.fg, 0.8));
    strokeCurve(ctx, st, x0, x1, yc, cell, 1, 20, C.acc);
    const p = E.o3(inv(0.6, 1.4, lt));
    arrowV(ctx, 140, yc - as * cell * grow, yc + as * cell * grow, C.acc, 6, p);
    arrowV(ctx, 1780, yc - am * cell * grow, yc + am * cell * grow, C.fg, 4, p);
    // centre label: the term, shown once with its English name
    const lp = inv(0.35, 1.0, lt);
    tag(ctx, '贝塔', W / 2, yc, C, lp, { px: 78, bg: C.fg, fg: PAL.purple.t[1] });
    if (lp > 0.5) G.typeText(ctx, upKeep(s.en || ''), W / 2, yc + 110, F.mono(30), C.fg, inv(0.7, 1.3, lt), { ls: '6px', align: 'center', caret: false });
    vizCaption(ctx, { zh: '跟大盘晃多猛', en: 'SWING VS MARKET' }, lt, C, { y: 220 });
  };

  VIZ.step_blocks = (ctx, s, lt, C) => {
    const d = s.viz.data, D = s.vizDur, cell = 96, base = 660;
    const cols = [{ x: 720, k: d.market, name: '大盘', col: rgba(C.fg, 0.85) }, { x: 1200, k: d.stock, name: '个股', col: G.INK }];
    gridLines(ctx, 480, 1440, base - cell * 3, base + cell * 3, cell, rgba(C.fg, 0.16));
    ctx.save(); ctx.strokeStyle = rgba(C.fg, 0.6); ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(470, base); ctx.lineTo(1450, base); ctx.stroke(); ctx.restore();
    // phase 1: up (market +1, stock +2); phase 2: down (−1 / −2)
    const half = D * 0.5;
    for (const c of cols) {
      const pu = E.oBack(inv(0.35, half * 0.75, lt), 1.2), pd = E.oBack(inv(half + 0.1, half + half * 0.6, lt), 1.2);
      const off = lt < half ? c.k[0] * pu : lerp(c.k[0], c.k[1], pd);
      const y = base - off * cell;
      ctx.fillStyle = c.col; ctx.fillRect(c.x - cell * 1.5, y - cell / 2, cell * 3, cell);
      // ticks showing how many cells it moved
      const n = Math.abs(Math.round(off));
      for (let i = 1; i <= n; i++) {
        const ty = base - Math.sign(off) * (i - 0.5) * cell;
        ctx.fillStyle = rgba(C.fg, 0.35); ctx.fillRect(c.x + cell * 1.7, ty - 4, 26, 8);
      }
      tag(ctx, c.name, c.x, base + cell * 3 + 60 > 1000 ? 990 : base + cell * 3 + 60, C, inv(0.1, 0.6, lt), { px: 34, bg: c.col === G.INK ? G.INK : C.fg, fg: c.col === G.INK ? C.fg : C.bg });
    }
    const mul = lt < half ? '1 → 2' : '−1 → −2';
    G.maskText(ctx, mul, 1700, 560, F.en(900, 64), C.fg, inv(0.6, 1.1, lt % half), { align: 'right' });
    vizCaption(ctx, s, lt, C);
  };

  VIZ.waves = (ctx, s, lt, C) => {
    const d = s.viz.data, yc = 700, cell = 100, ph = lt * 0.9;
    const N = d.curves.big.length;
    const fillWave = (pts, col, off, dx) => {
      ctx.beginPath(); ctx.moveTo(-40, H + 10);
      for (let i = 0; i < N; i++) { const x = lerp(-40, W + 40, i / (N - 1)) + dx; ctx.lineTo(x, yc - (pts[i] + off) * cell); }
      ctx.lineTo(W + 80, H + 10); ctx.closePath(); ctx.fillStyle = col; ctx.fill();
    };
    const rise = E.io3(inv(0.2, s.vizDur * 0.7, lt));
    const small = d.curves.small.map((v, i) => v * Math.cos(ph * 0.5) + 0.15 * Math.sin(i * 0.4 + ph));
    const big = d.curves.big.map((v, i) => v * lerp(0.35, 1, rise) * Math.cos(ph * 0.5 - 0.3) + 0.2 * Math.sin(i * 0.3 - ph));
    fillWave(small, rgba(G.INK, 0.25), 0.6, Math.sin(ph) * 30);
    fillWave(big, G.INK, -0.6, -Math.sin(ph) * 40);
    tag(ctx, '小浪 · 大盘', 1500, 330, C, inv(0.2, 0.8, lt), { px: 32, bg: rgba(G.INK, 0.25), fg: G.INK });
    tag(ctx, '大浪 · 个股', 1500, 420, C, inv(0.5, 1.1, lt), { px: 32, bg: G.INK, fg: C.bg });
    G.maskText(ctx, '贝塔 > 1', 150, 420, F.zh(900, 84), G.INK, inv(0.4, 1.0, lt));
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };

  VIZ.boat = (ctx, s, lt, C) => {
    const d = s.viz.data, yc = 720, cell = 80, N = d.curves.water.length, ph = lt * 0.6;
    const wv = (i) => d.curves.water[i] * Math.cos(ph) + 0.08 * Math.sin(i * 0.5 + ph * 2);
    ctx.beginPath(); ctx.moveTo(-20, H);
    for (let i = 0; i < N; i++) ctx.lineTo(lerp(-20, W + 20, i / (N - 1)), yc - wv(i) * cell);
    ctx.lineTo(W + 20, H); ctx.closePath(); ctx.fillStyle = C.soft; ctx.fill();
    // little boat bobbing gently on the calm surface
    const bi = Math.round((N - 1) * 0.55), bx = lerp(-20, W + 20, bi / (N - 1)) + Math.sin(lt * 0.7) * 30, by = yc - wv(bi) * cell;
    const tilt = (wv(bi + 1) - wv(bi - 1)) * 0.18;
    const ent = E.o3(inv(0.0, 0.8, lt));
    ctx.save(); ctx.translate(bx, by - 6 + (1 - ent) * 80); ctx.rotate(tilt);
    G.poly(ctx, [[-150, -10], [150, -10], [100, 60], [-100, 60]], C.fg);
    ctx.fillStyle = C.fg; ctx.fillRect(-6, -230, 12, 222);
    G.poly(ctx, [[12, -220], [12, -30], [130, -30]], C.fg);
    G.poly(ctx, [[-12, -190], [-12, -30], [-100, -30]], rgba(C.fg, 0.7));
    ctx.restore();
    // ripples = small swing
    for (let k = 0; k < 3; k++) { const r = ((lt * 60 + k * 70) % 210); ctx.save(); ctx.globalAlpha = 0.5 * (1 - r / 210); G.ring(ctx, bx, by + 40, r + 160, 3, C.fg); ctx.restore(); }
    G.maskText(ctx, '贝塔 < 1', 1770, 420, F.zh(900, 84), C.fg, inv(0.4, 1.0, lt), { align: 'right' });
    vizCaption(ctx, s, lt, C);
  };

  VIZ.mirror_updown = (ctx, s, lt, C) => {
    const d = s.viz.data, D = s.vizDur, cell = 85, x0 = 330, x1 = 1590, yc = 600;
    ctx.save(); ctx.strokeStyle = rgba(C.fg, 0.25); ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(250, yc); ctx.lineTo(1670, yc); ctx.stroke(); ctx.restore();
    const rev = E.io(inv(0.15, D * 0.7, lt));
    const N = d.curves.stock.length, pk = d.peakAt;
    // highlight bands: up half and down half, same height (symmetric)
    const top = Math.max(...d.curves.stock), bot = Math.min(...d.curves.stock);
    const hp = E.o3(inv(D * 0.35, D * 0.6, lt)), hd = E.o3(inv(D * 0.7, D * 0.9, lt));
    const xm = lerp(x0, x1, pk);
    ctx.fillStyle = rgba(C.fg, 0.1 * hp); ctx.fillRect(x0, yc - top * cell, xm - x0, top * cell);
    ctx.fillStyle = rgba(PAL.red.t[2], 0.35 * hd); ctx.fillRect(xm, yc, x1 - xm, (-bot) * cell);
    strokeCurve(ctx, d.curves.market, x0, x1, yc, cell, rev, 6, rgba(C.fg, 0.55));
    const h = strokeCurve(ctx, d.curves.stock, x0, x1, yc, cell, rev, 20, C.acc);
    G.disc(ctx, h[0], h[1], 16, C.acc);
    arrowV(ctx, x0 - 60, yc, yc - top * cell, C.fg, 6, hp);
    arrowV(ctx, x1 + 60, yc, yc - bot * cell, PAL.red.t[3], 6, hd);
    tag(ctx, '涨得高', x0 + 120, yc - top * cell - 10, C, hp, { px: 34 });
    tag(ctx, '跌得深', x1 - 120, yc - bot * cell + 10, C, hd, { px: 34, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 230, align: 'right' });
  };

  VIZ.coaster = (ctx, s, lt, C) => {
    const d = s.viz.data, D = s.vizDur, trk = d.curves.track, N = trk.length;
    // slow push-in toward the crest; the car stops right before the drop
    const z = lerp(1, 1.18, E.io(inv(0, D, lt)));
    const cell = 95, x0 = 140, x1 = 1780, yc = 640;
    const tStop = d.stopAt;
    const pos = lerp(0.05, tStop, E.o3(inv(0.2, D * 0.75, lt)));
    const px = lerp(x0, x1, pos), fi = pos * (N - 1);
    const val = (f) => lerp(trk[Math.floor(f)], trk[Math.min(N - 1, Math.floor(f) + 1)], f - Math.floor(f));
    const py = yc - val(fi) * cell;
    ctx.save(); ctx.translate(px, py); ctx.scale(z, z); ctx.translate(-px, -py);
    // supports
    ctx.strokeStyle = rgba(G.INK, 0.25); ctx.lineWidth = 6;
    for (let i = 0; i < N; i += 3) { const x = lerp(x0, x1, i / (N - 1)), y = yc - trk[i] * cell; ctx.beginPath(); ctx.moveTo(x, y + 14); ctx.lineTo(x, H + 100); ctx.stroke(); }
    strokeCurve(ctx, trk, x0, x1, yc, cell, 1, 26, G.INK);
    strokeCurve(ctx, trk, x0, x1, yc, cell, 1, 8, C.soft, 0);
    // car + seated pictogram rider
    const ang = Math.atan2(-(val(Math.min(N - 1, fi + 0.5)) - val(Math.max(0, fi - 0.5))) * cell, (x1 - x0) / (N - 1));
    ctx.save(); ctx.translate(px, py - 16); ctx.rotate(ang);
    ctx.fillStyle = C.acc; ctx.beginPath(); ctx.roundRect(-90, -70, 180, 70, 14); ctx.fill();
    G.disc(ctx, -55, 4, 16, G.INK); G.disc(ctx, 55, 4, 16, G.INK);
    ctx.save(); ctx.translate(-10, -62); ctx.scale(150, 150);
    const grip = 0.5 + 0.5 * Math.sin(lt * 3);
    G.drawFigure(ctx, G.joints({ x: 0, y: 0, torso: -8, head: -6, lL1: 80, lL2: 10, lR1: 86, lR2: 14, aL1: 72 + grip * 4, aL2: 92, aR1: 78 + grip * 4, aR2: 96 }), G.INK, rgba(G.INK, 0.6));
    ctx.restore();
    ctx.restore();
    ctx.restore();
    // the drop ahead
    tag(ctx, '下坡前', Math.min(1700, px + 260), Math.min(980, py + 160), C, inv(D * 0.75, D * 0.95, lt), { px: 36, bg: C.acc, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };

  // ───────── finance-v003 scene library, batch 2 (CAPM / ERM / VaR plain / 风险偏好, 2026-10-29) ─────────
  // One scene per draft `visual` (viz_pick.py RULES). Vector only, no tickers / K-lines / casino props,
  // no rising-only curves. VaR: losses point DOWN from a zero line; the 100万 line is a threshold,
  // not the worst case (the tail can go deeper — tail_avg draws the average of the worst days lower).
  Object.assign(VPAL, {
    scale_half: 'ochre', ruler: 'purple', rain_wind: 'ink', one_egg: 'cream', many_eggs: 'green', basket_wave: 'red', wave_tag: 'gold',
    dept_smoke: 'ink', frame_gather: 'green', ledgers_merge: 'cream', bag_shield: 'purple', car_pedals: 'red', round_table: 'ochre', beam_hold: 'gold',
    big_number_x: 'red', threshold_line: 'ink', days_below: 'gold', calendar_100: 'cream', red_breach: 'purple', dark_below: 'ink', tail_avg: 'ochre',
    platform_rope: 'purple', knob: 'gold', hand_line: 'green', bag_split: 'cream', ground_shake: 'red', carry_pole: 'ochre', bed_awake: 'ink',
  });
  const pop = (lt, a, b) => E.oBack(clamp(inv(a, b, lt)), 1.4);
  function figAt(ctx, x, y, sc, pose, col, far) { // y = feet (ground) line
    ctx.save(); ctx.translate(x, y - 0.5 * sc); ctx.scale(sc, sc); G.drawFigure(ctx, G.joints(pose), col, far || rgba(col, 0.6)); ctx.restore();
  }
  function egg(ctx, x, y, r, col, crack = 0, crackCol = G.INK) {
    ctx.save(); ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(x, y, r * 0.78, r, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = rgba(G.INK, 0.35); ctx.lineWidth = Math.max(2, r * 0.05); ctx.stroke();
    if (crack > 0) {
      ctx.strokeStyle = crackCol; ctx.lineWidth = Math.max(3, r * 0.08); ctx.lineJoin = 'round'; ctx.beginPath();
      const pts = [[-0.7, -0.05], [-0.35, 0.12], [-0.1, -0.12], [0.15, 0.1], [0.4, -0.1], [0.72, 0.06]];
      const n = Math.max(2, Math.ceil(pts.length * clamp(crack)));
      pts.slice(0, n).forEach((p, i) => (i ? ctx.lineTo(x + p[0] * r * 0.78, y + p[1] * r) : ctx.moveTo(x + p[0] * r * 0.78, y + p[1] * r)));
      ctx.stroke();
    }
    ctx.restore();
  }
  function basket(ctx, x, y, w, h, col, rot = 0) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
    G.poly(ctx, [[-w / 2, 0], [w / 2, 0], [w * 0.38, h], [-w * 0.38, h]], col);
    ctx.strokeStyle = rgba(G.INK, 0.25); ctx.lineWidth = 4;
    for (let i = 1; i < 4; i++) { const yy = h * i / 4; ctx.beginPath(); ctx.moveTo(-w / 2 + (w * 0.12) * i / 4, yy); ctx.lineTo(w / 2 - (w * 0.12) * i / 4, yy); ctx.stroke(); }
    ctx.lineWidth = 10; ctx.strokeStyle = col; ctx.beginPath(); ctx.ellipse(0, 0, w * 0.42, h * 0.9, 0, Math.PI, 0); ctx.stroke();
    ctx.restore();
  }
  function moneyBag(ctx, x, y, r, col, sym = '¥', symCol) {
    G.disc(ctx, x, y, r, col); G.poly(ctx, [[x - r * 0.35, y - r * 0.85], [x + r * 0.35, y - r * 0.85], [x + r * 0.55, y - r * 1.25], [x - r * 0.55, y - r * 1.25]], col);
    ctx.save(); ctx.font = F.en(900, r * 0.95); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = symCol || G.CREAM; ctx.fillText(sym, x, y + r * 0.08); ctx.restore();
  }
  function bolt(ctx, x, y, s, col) { G.poly(ctx, [[x, y], [x + 0.5 * s, y], [x + 0.2 * s, y + 0.8 * s], [x + 0.6 * s, y + 0.8 * s], [x - 0.15 * s, y + 1.9 * s], [x + 0.05 * s, y + 1.05 * s], [x - 0.3 * s, y + 1.05 * s]], col); }
  function building(ctx, x, y, w, h, col, win) {
    ctx.fillStyle = col; ctx.fillRect(x - w / 2, y - h, w, h);
    ctx.fillStyle = win; for (let r = 0; r < 6; r++) for (let c = 0; c < 4; c++) ctx.fillRect(x - w / 2 + 24 + c * (w - 48) / 4, y - h + 30 + r * (h - 60) / 6, (w - 48) / 4 - 18, (h - 60) / 6 - 18);
  }
  function smoke(ctx, x, y, lt, k, col) {
    for (let i = 0; i < 7; i++) { const u = ((lt * 0.6 + i / 7) % 1); ctx.save(); ctx.globalAlpha = k * (1 - u) * 0.8; G.disc(ctx, x + Math.sin(i * 2.1 + lt) * 60 * u, y - u * 360, 40 + u * 90, col); ctx.restore(); }
  }

  // ── CAPM ──
  VIZ.scale_half = (ctx, s, lt, C) => {
    const D = s.vizDur, cx = W / 2, py = 470, arm = 520;
    const tilt = -0.11 * E.oBack(inv(0.6, D * 0.6, lt), 1.6) + 0.015 * Math.sin(lt * 3) * inv(0.6, 1.2, lt);
    G.poly(ctx, [[cx - 40, py], [cx + 40, py], [cx + 120, 960], [cx - 120, 960]], C.fg);
    ctx.fillRect(cx - 220, 950, 440, 30);
    ctx.save(); ctx.translate(cx, py); ctx.rotate(tilt);
    ctx.fillStyle = C.fg; ctx.fillRect(-arm, -10, arm * 2, 20); G.disc(ctx, 0, 0, 28, C.fg);
    for (const [sx, lab, col] of [[-arm, '冒险', C.acc], [arm, '回报', G.CREAM]]) {
      const yy = 0; ctx.save(); ctx.translate(sx, yy); ctx.rotate(-tilt);
      ctx.strokeStyle = C.fg; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-110, 190); ctx.moveTo(0, 0); ctx.lineTo(110, 190); ctx.stroke();
      ctx.fillStyle = C.fg; ctx.beginPath(); ctx.ellipse(0, 200, 150, 34, 0, 0, Math.PI); ctx.fill();
      tag(ctx, lab, 0, 150, C, inv(0.2, 0.8, lt), { px: 40, bg: col, fg: G.INK });
      ctx.restore();
    }
    ctx.restore();
    tag(ctx, '只对一半', 1560, 380, C, inv(D * 0.55, D * 0.8, lt), { px: 40, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ruler = (ctx, s, lt, C) => {
    const D = s.vizDur, x0 = 260, x1 = 1660, y = 640, p = E.io(inv(0.1, 0.9, lt));
    ctx.save(); ctx.translate(W / 2, y); ctx.rotate(-0.06); ctx.translate(-W / 2, -y);
    ctx.fillStyle = G.CREAM; ctx.fillRect(x0, y - 70, (x1 - x0) * p, 140);
    ctx.fillStyle = G.INK;
    for (let i = 0; i <= 28; i++) { const x = x0 + i * (x1 - x0) / 28; if (x > x0 + (x1 - x0) * p) break; ctx.fillRect(x - 2, y - 70, 4, i % 4 === 0 ? 60 : 30); }
    const m = lerp(x0 + 60, x1 - 60, E.io(inv(D * 0.3, D * 0.85, lt)));
    G.poly(ctx, [[m, y + 70], [m - 30, y + 120], [m + 30, y + 120]], C.acc);
    ctx.restore();
    tag(ctx, '风险', x0 + 90, y + 210, C, inv(0.4, 0.9, lt), { px: 40, bg: C.fg, fg: C.bg });
    tag(ctx, '该要的回报', x1 - 150, y - 200, C, inv(0.7, 1.2, lt), { px: 40, bg: C.fg, fg: C.bg });
    G.maskText(ctx, 'CAPM', W / 2, y + 26, F.en(900, 80), C.bg, inv(0.9, 1.5, lt) * (p > 0.6 ? 1 : 0), { align: 'center', ls: '10px' });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.rain_wind = (ctx, s, lt, C) => {
    const D = s.vizDur, mid = W / 2;
    ctx.fillStyle = rgba(C.fg, 0.06); ctx.fillRect(mid, 330, W / 2 - 120, 680);
    ctx.strokeStyle = rgba(C.fg, 0.35); ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(mid, 340); ctx.lineTo(mid, 1000); ctx.stroke();
    // left: light rain, a figure under an umbrella stays dry
    ctx.strokeStyle = rgba(C.fg, 0.55); ctx.lineWidth = 4;
    for (let i = 0; i < 26; i++) { const x = 200 + (i * 67) % 700, yy = 340 + ((lt * 380 + i * 91) % 560); ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x - 8, yy + 30); ctx.stroke(); }
    const ux = 560, uy = 690, up = E.oBack(inv(0.3, 0.9, lt));
    ctx.fillStyle = C.acc; ctx.beginPath(); ctx.arc(ux, uy, 170 * up, Math.PI, 0); ctx.fill(); ctx.fillRect(ux - 4, uy, 8, 150);
    figAt(ctx, ux - 30, 960, 230, { torso: 0, aR1: -150, aR2: -150 }, C.fg);
    tag(ctx, '躲得开', ux, 1000, C, inv(0.5, 1.0, lt), { px: 34, bg: C.acc, fg: G.INK });
    // right: strong wind, streaks + leaning figure
    const k = E.io(inv(D * 0.3, D * 0.6, lt));
    ctx.strokeStyle = rgba(C.fg, 0.8); ctx.lineCap = 'round';
    for (let i = 0; i < 11; i++) { const yy = 380 + i * 55, ph = ((lt * 900 + i * 173) % 900); ctx.lineWidth = 6 + (i % 3) * 3; ctx.beginPath(); ctx.moveTo(mid + 40 + ph * k, yy); ctx.lineTo(mid + 40 + ph * k + 180 * k, yy); ctx.stroke(); }
    figAt(ctx, 1450, 960, 230, { torso: -28 * k, head: -10, aL1: 60, aR1: 80, aL2: 80, aR2: 100, lL1: -20, lR1: 14 }, C.fg);
    tag(ctx, '躲不掉', 1450, 1000, C, inv(D * 0.45, D * 0.75, lt), { px: 34, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.one_egg = (ctx, s, lt, C) => {
    const D = s.vizDur, cx = W / 2 + 120, by = 760;
    basket(ctx, cx, by, 560, 220, PAL.ochre.t[3]);
    const cr = inv(D * 0.4, D * 0.7, lt), [sx] = shake(lt, D * 0.45, 10);
    egg(ctx, cx + sx, by - 60, 130, '#f3e6cc', cr);
    if (cr > 0.6) { ctx.save(); ctx.globalAlpha = inv(D * 0.6, D * 0.8, lt); G.disc(ctx, cx + 40, by + 250, 60, PAL.gold.t[2]); ctx.restore(); }
    tag(ctx, '只买一家', 520, 520, C, inv(0.2, 0.8, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    tag(ctx, '它出事，你就亏', 1560, 900, C, inv(D * 0.6, D * 0.85, lt), { px: 36, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };
  VIZ.many_eggs = (ctx, s, lt, C) => {
    const D = s.vizDur, cx = W / 2, by = 700;
    basket(ctx, cx, by, 1100, 260, PAL.ochre.t[3]);
    let n = 0;
    for (let r = 0; r < 2; r++) for (let c = 0; c < 9; c++) {
      const x = cx - 440 + c * 110 + (r ? 55 : 0), y = by - 40 - r * 85, p = pop(lt, 0.1 + n * 0.04, 0.6 + n * 0.04);
      const bad = r === 0 && c === 6;
      if (p > 0) egg(ctx, x, y + (1 - p) * -120, 58, bad ? '#e9d6b0' : G.CREAM, bad ? inv(D * 0.45, D * 0.7, lt) : 0);
      n++;
    }
    // impact bar: one cracked egg = a small slice of the whole basket
    const bx = 460, bw = 1000, yy = 1010, pp = E.o3(inv(D * 0.6, D * 0.85, lt));
    ctx.fillStyle = rgba(C.fg, 0.25); ctx.fillRect(bx, yy - 14, bw, 28);
    ctx.fillStyle = PAL.red.t[2]; ctx.fillRect(bx, yy - 14, bw / 18 * pp, 28);
    tag(ctx, '影响很小', bx + bw + 130, yy, C, pp, { px: 32 });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.basket_wave = (ctx, s, lt, C) => {
    const D = s.vizDur, k = E.io3(inv(D * 0.2, D * 0.65, lt));
    const rot = lerp(0, 1.9, k), bx = lerp(900, 1180, k), by = lerp(640, 560, k);
    for (let i = 0; i < 8; i++) { const fl = E.o3(inv(D * 0.45 + i * 0.05, D * 0.8 + i * 0.05, lt)); egg(ctx, bx - 160 + i * 50 + fl * (120 + i * 40), by - 40 + fl * (330 + (i % 3) * 40), 42, G.CREAM, fl > 0.8 ? 1 : 0); }
    basket(ctx, bx, by, 520, 200, PAL.ochre.t[1], rot);
    // the big wave rises from the left and sweeps across
    const N = 60, crest = lerp(-300, 1200, k);
    ctx.beginPath(); ctx.moveTo(-40, H + 10);
    for (let i = 0; i <= N; i++) { const x = lerp(-40, W + 40, i / N), d = (x - crest) / 380; ctx.lineTo(x, 900 - 420 * Math.exp(-d * d) - 30 * Math.sin(i * 0.5 + lt * 2)); }
    ctx.lineTo(W + 40, H + 10); ctx.closePath(); ctx.fillStyle = G.INK; ctx.fill();
    tag(ctx, '整个大盘一起跌', 1480, 380, C, inv(0.3, 0.9, lt), { px: 38 });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.wave_tag = (ctx, s, lt, C) => {
    const D = s.vizDur, ph = lt * 1.2;
    ctx.fillStyle = rgba(G.INK, 0.08); ctx.fillRect(0, 330, W / 2 - 60, 700);
    ctx.beginPath(); ctx.moveTo(W / 2 + 40, H);
    for (let i = 0; i <= 40; i++) { const x = lerp(W / 2 + 40, W + 20, i / 40); ctx.lineTo(x, 760 - 260 * Math.sin(i / 40 * Math.PI) - 20 * Math.sin(i * 0.6 + ph)); }
    ctx.lineTo(W + 20, H); ctx.closePath(); ctx.fillStyle = G.INK; ctx.fill();
    ctx.strokeStyle = rgba(G.INK, 0.35); ctx.lineWidth = 5; ctx.beginPath();
    for (let i = 0; i <= 30; i++) { const x = lerp(120, W / 2 - 120, i / 30); ctx.lineTo(x, 860 - 30 * Math.sin(i * 0.7 + ph)); } ctx.stroke();
    G.maskText(ctx, '躲得开', 380, 760, F.zh(900, 56), rgba(G.INK, 0.45), inv(0.2, 0.7, lt), { align: 'center' });
    const glow = E.o3(inv(0.3, 1.0, lt));
    ctx.save(); ctx.globalAlpha = 0.35 * glow; G.disc(ctx, 1400, 470, 260, G.CREAM); ctx.restore();
    tag(ctx, '该多要回报', 1400, 470, C, glow, { px: 56, bg: G.CREAM, fg: G.INK });
    tag(ctx, '≠ 一定多赚', 1400, 600, C, inv(D * 0.55, D * 0.8, lt), { px: 44, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };

  // ── ERM ──
  VIZ.dept_smoke = (ctx, s, lt, C) => {
    const D = s.vizDur, k = inv(D * 0.45, D * 0.7, lt);
    building(ctx, 1380, 1000, 420, 600, C.soft, rgba(C.fg, 0.12 + 0.3 * k));
    if (k > 0) smoke(ctx, 1380, 400, lt, E.o3(k), rgba(C.fg, 0.5));
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) {
      const x = 260 + c * 200, y = 420 + r * 190, p = pop(lt, 0.1 + (r * 3 + c) * 0.06, 0.5 + (r * 3 + c) * 0.06);
      if (p <= 0) continue;
      ctx.fillStyle = rgba(C.fg, 0.14); ctx.fillRect(x, y, 160, 150);
      G.disc(ctx, x + 80, y + 70, 34 * p, PAL.green.t[3]);
    }
    tag(ctx, '各自没雷', 560, 1010, C, inv(0.4, 0.9, lt), { px: 34, bg: PAL.green.t[3], fg: G.CREAM });
    tag(ctx, '公司照样炸', 1380, 330, C, inv(D * 0.6, D * 0.85, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.frame_gather = (ctx, s, lt, C) => {
    const D = s.vizDur, k = E.io3(inv(0.2, D * 0.6, lt));
    const fx = 560, fy = 380, fw = 800, fh = 520;
    for (let i = 0; i < 8; i++) {
      const a = i / 8 * Math.PI * 2, sx = W / 2 + Math.cos(a) * 760, sy = 640 + Math.sin(a) * 360;
      const tx = fx + 60 + (i % 4) * 180, ty = fy + 80 + Math.floor(i / 4) * 200;
      ctx.fillStyle = i % 3 === 0 ? G.CREAM : rgba(C.fg, 0.75); ctx.fillRect(lerp(sx, tx, k) - 70, lerp(sy, ty, k) - 60, 140, 120);
    }
    const fp = E.o3(inv(D * 0.5, D * 0.8, lt));
    ctx.save(); ctx.strokeStyle = C.fg; ctx.lineWidth = 12; ctx.setLineDash([(fw + fh) * 2 * fp, 9999]); ctx.strokeRect(fx - 20, fy - 20, fw + 40, fh + 40); ctx.restore();
    tag(ctx, '全面风险管理', W / 2, fy - 20, C, inv(D * 0.65, D * 0.9, lt), { px: 50, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.ledgers_merge = (ctx, s, lt, C) => {
    const D = s.vizDur, k = E.io3(inv(0.3, D * 0.65, lt));
    const book = (x, y, w, h, col, rot) => { ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.fillStyle = col; ctx.fillRect(-w / 2, -h / 2, w, h); ctx.fillStyle = rgba(G.INK, 0.2); for (let i = 0; i < 5; i++) ctx.fillRect(-w / 2 + 30, -h / 2 + 50 + i * (h - 80) / 5, w - 60, 6); ctx.fillStyle = rgba(G.INK, 0.6); ctx.fillRect(-w / 2, -h / 2, 18, h); ctx.restore(); };
    const cols = [PAL.red.t[2], PAL.green.t[2], PAL.purple.t[3], PAL.gold.t[2]];
    for (let i = 0; i < 4; i++) {
      const sx = 330 + i * 420, sy = 640 + (i % 2) * 60;
      book(lerp(sx, W / 2, k), lerp(sy, 650, k) - i * 6 * k, lerp(260, 300, k), lerp(330, 380, k), cols[i], lerp((i - 1.5) * 0.12, 0, k));
    }
    if (k > 0.95) { const p = pop(lt, D * 0.7, D * 0.9); tag(ctx, '一本账', W / 2, 920, C, p, { px: 44, bg: G.INK, fg: G.CREAM }); }
    else tag(ctx, '各算各的', W / 2, 960, C, inv(0.1, 0.5, lt) * (1 - k), { px: 36, bg: rgba(G.INK, 0.7), fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };
  VIZ.bag_shield = (ctx, s, lt, C) => {
    const D = s.vizDur, cx = W / 2, hy = 980;
    const lift = E.oBack(inv(0.2, 0.9, lt)), FS = 360;
    const pose = { torso: 0, aL1: lerp(-120, -165, lift), aL2: lerp(-130, -175, lift), aR1: 95, aR2: 95, lL1: -8, lR1: 8 };
    figAt(ctx, cx, hy, FS, pose, C.fg, C.fg);
    const J = G.joints(pose), hand = (A) => [cx + A[2][0] * FS, hy - 0.5 * FS + A[2][1] * FS];
    const [bx, by] = hand(J.aL), [sx0, sy0] = hand(J.aR);
    moneyBag(ctx, bx, by - 80, 72, PAL.gold.t[2], '¥', G.INK);
    // shield on the other hand; lightning bolts fly in and break on it
    const sx = sx0 + 70, sy = sy0;
    G.poly(ctx, [[sx - 90, sy - 130], [sx + 90, sy - 130], [sx + 90, sy + 20], [sx, sy + 140], [sx - 90, sy + 20]], G.CREAM);
    G.poly(ctx, [[sx - 60, sy - 100], [sx + 60, sy - 100], [sx + 60, sy + 10], [sx, sy + 100], [sx - 60, sy + 10]], C.acc);
    for (let i = 0; i < 2; i++) {
      const t0 = D * (0.35 + i * 0.25), u = inv(t0, t0 + 0.6, lt);
      if (u > 0 && u < 1) bolt(ctx, lerp(1820, sx + 110, u), lerp(330 + i * 120, sy - 90 + i * 60, u), 70, PAL.gold.t[3]);
      if (u >= 1) { const f = 1 - inv(t0 + 0.6, t0 + 1.0, lt); if (f > 0) { ctx.save(); ctx.globalAlpha = f; G.ring(ctx, sx + 100, sy - 40 + i * 50, 60 + (1 - f) * 80, 6, PAL.gold.t[3]); ctx.restore(); } }
    }
    tag(ctx, '赚钱', bx - 170, by - 90, C, inv(0.4, 0.9, lt), { px: 34, bg: PAL.gold.t[2], fg: G.INK });
    tag(ctx, '挡雷', sx, sy + 210, C, inv(D * 0.35, D * 0.6, lt), { px: 34, bg: C.acc, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.car_pedals = (ctx, s, lt, C) => {
    const D = s.vizDur, cx = W / 2, cy = 640, jitter = Math.sin(lt * 18) * 6 * inv(D * 0.3, D * 0.5, lt);
    ctx.save(); ctx.translate(jitter, 0);
    ctx.fillStyle = G.CREAM; ctx.beginPath(); ctx.roundRect(cx - 460, cy - 120, 920, 200, 60); ctx.fill();
    ctx.beginPath(); ctx.roundRect(cx - 260, cy - 250, 480, 150, 50); ctx.fill();
    ctx.fillStyle = rgba(G.INK, 0.25); ctx.fillRect(cx - 220, cy - 220, 190, 100); ctx.fillRect(cx + 10, cy - 220, 170, 100);
    G.disc(ctx, cx - 280, cy + 90, 80, G.INK); G.disc(ctx, cx + 280, cy + 90, 80, G.INK);
    G.disc(ctx, cx - 280, cy + 90, 30, C.soft); G.disc(ctx, cx + 280, cy + 90, 30, C.soft);
    ctx.restore();
    // two feet: gas (forward arrow) vs hand-brake (stop)
    const pa = inv(0.3, 0.9, lt), pb = inv(D * 0.35, D * 0.7, lt);
    if (pa > 0) { const L = 200 * E.o3(pa), ax = 1440, ay = 900; G.poly(ctx, [[ax, ay - 18], [ax + L, ay - 18], [ax + L, ay - 46], [ax + L + 64, ay], [ax + L, ay + 46], [ax + L, ay + 18], [ax, ay + 18]], G.CREAM); }
    tag(ctx, '销售 · 踩油门', 1620, 1010, C, pa, { px: 32, bg: G.CREAM, fg: G.INK });
    ctx.save(); ctx.globalAlpha = clamp(pb * 2); G.disc(ctx, 360, 900, 70, G.INK); ctx.fillStyle = G.CREAM; ctx.fillRect(320, 890, 80, 20); ctx.restore();
    tag(ctx, '风控 · 拉手刹', 360, 1010, C, pb, { px: 32, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.round_table = (ctx, s, lt, C) => {
    const D = s.vizDur, cx = W / 2, cy = 680, rx = 560, ry = 230;
    for (let i = 0; i < 6; i++) { const a = Math.PI + i / 5 * Math.PI; G.disc(ctx, cx + Math.cos(a) * (rx + 90), cy + Math.sin(a) * (ry + 70) - 40, 46, rgba(G.INK, 0.75)); }
    ctx.fillStyle = G.INK; ctx.beginPath(); ctx.ellipse(cx, cy + 30, rx, ry, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = C.soft; ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2); ctx.fill();
    const names = ['销售', '风控', '财务', '运营', '采购'];
    names.forEach((n, i) => {
      const p = E.o3(inv(0.2 + i * 0.25, 0.8 + i * 0.25, lt)), a = -Math.PI / 2 + (i - 2) * 0.55;
      const tx = cx + Math.cos(a + Math.PI) * 0 + (i - 2) * 190, ty = cy - 10 + (i % 2) * 50;
      const sx = cx + (i - 2) * 420, sy = 1080;
      ctx.save(); ctx.translate(lerp(sx, tx, p), lerp(sy, ty, p)); ctx.rotate((i - 2) * 0.06 * (1 - p));
      ctx.fillStyle = G.CREAM; ctx.fillRect(-75, -55, 150, 110); ctx.fillStyle = G.INK; ctx.font = F.zh(900, 34); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(n, 0, 2); ctx.restore();
    });
    tag(ctx, '一起看', cx, 390, C, inv(D * 0.7, D * 0.9, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };
  VIZ.beam_hold = (ctx, s, lt, C) => {
    // steelyard: the company hangs on the short arm, the shock pushes on the long arm — does the beam hold?
    const D = s.vizDur, px = 760, py = 420, push = E.io(inv(D * 0.25, D * 0.65, lt));
    const ang = 0.05 * push + 0.012 * Math.sin(lt * 7) * push;
    ctx.fillStyle = G.INK; ctx.fillRect(px - 8, 330, 16, 90);
    ctx.save(); ctx.translate(px, py); ctx.rotate(ang);
    ctx.fillStyle = G.INK; ctx.fillRect(-360, -12, 1260, 24); G.disc(ctx, 0, 0, 22, G.CREAM);
    ctx.strokeStyle = G.INK; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(-320, 0); ctx.lineTo(-320, 140); ctx.stroke();
    ctx.restore();
    building(ctx, px - 320 * Math.cos(ang), py + 140 - 320 * Math.sin(-ang) + 300, 280, 300, G.INK, rgba(C.bg, 0.6));
    // shock arrows pressing down on the long arm
    const ax = px + 820, ay = py + 820 * Math.sin(ang);
    for (let i = 0; i < 3; i++) { const yy = ay - 200 + ((lt * 200 + i * 70) % 200) * push; G.poly(ctx, [[ax - 30, yy - 80], [ax + 30, yy - 80], [ax + 30, yy - 20], [ax + 60, yy - 20], [ax, yy + 30], [ax - 60, yy - 20], [ax - 30, yy - 20]], rgba(PAL.red.t[2], 0.9 - i * 0.2)); }
    tag(ctx, '整家公司', px - 320, 990, C, inv(0.2, 0.8, lt), { px: 34, bg: G.INK, fg: G.CREAM });
    tag(ctx, '冲击', ax - 190, ay - 200, C, inv(D * 0.3, D * 0.6, lt), { px: 34, bg: PAL.red.t[2], fg: G.CREAM });
    tag(ctx, '扛不扛得住？', 1420, 900, C, inv(D * 0.6, D * 0.85, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };

  // ── VaR (plain) — loss axis points down from 0; threshold = 100万 ──
  VIZ.big_number_x = (ctx, s, lt, C) => {
    const D = s.vizDur;
    G.maskText(ctx, '100万', 820, 760, F.en(900, 300), C.fg, inv(0.1, 0.7, lt), { align: 'center' });
    tag(ctx, '最多', 1500, 560, C, inv(D * 0.35, D * 0.6, lt), { px: 70, bg: G.CREAM, fg: G.INK });
    const xp = E.o3(inv(D * 0.55, D * 0.85, lt));
    ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 22; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(1380, 450); ctx.lineTo(lerp(1380, 1620, xp), lerp(450, 670, xp)); ctx.stroke();
    if (xp > 0.5) { const q = (xp - 0.5) * 2; ctx.beginPath(); ctx.moveTo(1620, 450); ctx.lineTo(lerp(1620, 1380, q), lerp(450, 670, q)); ctx.stroke(); }
    ctx.restore();
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.threshold_line = (ctx, s, lt, C) => {
    const D = s.vizDur, y0 = 420, yt = 760, p = E.io(inv(0.2, 1.0, lt));
    ctx.fillStyle = rgba(C.fg, 0.5); ctx.fillRect(200, y0 - 2, 1520, 4);
    G.typeText(ctx, '0', 170, y0 + 10, F.mono(30), C.dim, 1, { align: 'right', caret: false });
    G.typeText(ctx, '亏 ↓', 170, y0 + 200, F.zh(700, 34), C.dim, inv(0.2, 0.6, lt), { align: 'right', caret: false });
    ctx.fillStyle = C.acc; ctx.fillRect(200, yt - 6, 1520 * p, 12);
    tag(ctx, '100万', 330, yt + 70, C, inv(0.8, 1.3, lt), { px: 40, bg: C.acc, fg: G.INK });
    tag(ctx, '风险价值', 1500, yt - 80, C, inv(D * 0.45, D * 0.75, lt), { px: 50, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.days_below = (ctx, s, lt, C) => {
    // most days: the loss bar hangs from 0 and stops short of the 100万 line
    const D = s.vizDur, y0 = 400, yt = 820, n = 14;
    ctx.fillStyle = rgba(G.INK, 0.5); ctx.fillRect(160, y0 - 2, 1600, 4);
    ctx.setLineDash([24, 16]); ctx.strokeStyle = PAL.red.t[2]; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(160, yt); ctx.lineTo(1760, yt); ctx.stroke(); ctx.setLineDash([]);
    for (let i = 0; i < n; i++) {
      const h = (0.25 + 0.6 * Math.abs(Math.sin(i * 1.7 + 0.4))) * (yt - y0 - 40), p = E.oBack(inv(0.15 + i * 0.12, 0.6 + i * 0.12, lt));
      ctx.fillStyle = PAL.green.t[2]; ctx.fillRect(200 + i * 110, y0, 80, h * clamp(p));
    }
    tag(ctx, '亏不过这条线', 1470, yt + 80, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    tag(ctx, '100万', 250, yt + 80, C, inv(0.3, 0.8, lt), { px: 32, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) }, { y: 230 });
  };
  VIZ.calendar_100 = (ctx, s, lt, C) => {
    const D = s.vizDur, x0 = 560, y0 = 340, c = 64;
    for (let i = 0; i < 100; i++) {
      const r = Math.floor(i / 10), k = i % 10, p = clamp(inv(0.1 + i * 0.018, 0.4 + i * 0.018, lt) * 1.5);
      if (p <= 0) continue;
      const red = i === 73, fl = red ? 0.5 + 0.5 * Math.sin(lt * 10) : 1;
      ctx.fillStyle = red ? rgba(PAL.red.t[2], 0.45 + 0.55 * fl) : PAL.green.t[2];
      const sz = (c - 10) * E.oBack(p);
      ctx.fillRect(x0 + k * c + (c - 10 - sz) / 2, y0 + r * c + (c - 10 - sz) / 2, sz, sz);
    }
    G.maskText(ctx, '99', 1440, 600, F.en(900, 140), PAL.green.t[1], inv(D * 0.45, D * 0.7, lt));
    G.maskText(ctx, '1', 1440, 800, F.en(900, 140), PAL.red.t[2], inv(D * 0.6, D * 0.85, lt));
    G.typeText(ctx, '天 · 亏不过 100万', 1440, 660, F.zh(700, 32), C.dim, inv(D * 0.5, D * 0.8, lt), { caret: false });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.red_breach = (ctx, s, lt, C) => {
    const D = s.vizDur, y0 = 380, yt = 620, x = 1100;
    ctx.fillStyle = rgba(C.fg, 0.4); ctx.fillRect(200, y0 - 2, 1520, 4);
    const crack = inv(D * 0.3, D * 0.45, lt);
    ctx.fillStyle = G.CREAM; ctx.fillRect(200, yt - 6, x - 260 - 200 + 60 * (1 - crack), 12); ctx.fillRect(x + 60 - 60 * (1 - crack) + 60, yt - 6, 1720 - x - 120, 12);
    for (let i = 0; i < 6; i++) { ctx.fillStyle = rgba(G.CREAM, 0.35); ctx.fillRect(320 + i * 110, y0, 70, 80 + (i * 37) % 120); }
    const fall = E.i3 ? E.i3(inv(D * 0.3, D * 0.85, lt)) : Math.pow(inv(D * 0.3, D * 0.85, lt), 2);
    const h = lerp(140, 620, fall);
    ctx.fillStyle = PAL.red.t[3]; ctx.fillRect(x - 50, y0, 100, h);
    arrowV(ctx, x + 120, yt, y0 + h, PAL.red.t[4], 6, inv(D * 0.6, D * 0.9, lt));
    tag(ctx, '可能亏得更多', 1460, 900, C, inv(D * 0.6, D * 0.85, lt), { px: 40, bg: PAL.red.t[3], fg: G.CREAM });
    tag(ctx, '100万', 290, yt + 60, C, inv(0.2, 0.6, lt), { px: 30, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.dark_below = (ctx, s, lt, C) => {
    const D = s.vizDur, yt = 560;
    const g = ctx.createLinearGradient(0, yt, 0, H); g.addColorStop(0, 'rgba(0,0,0,0.2)'); g.addColorStop(1, 'rgba(0,0,0,0.95)');
    ctx.fillStyle = g; ctx.fillRect(0, yt, W, H - yt);
    const glow = 0.6 + 0.4 * Math.sin(lt * 4);
    ctx.save(); ctx.shadowColor = PAL.gold.t[3]; ctx.shadowBlur = 40 * glow; ctx.fillStyle = PAL.gold.t[3]; ctx.fillRect(140, yt - 8, 1640 * E.io(inv(0.1, 0.8, lt)), 16); ctx.restore();
    tag(ctx, '只报门槛', 1500, yt - 90, C, inv(0.3, 0.8, lt), { px: 40, bg: PAL.gold.t[3], fg: G.INK });
    const q = pop(lt, D * 0.4, D * 0.75);
    if (q > 0) { ctx.save(); ctx.translate(W / 2, 830); ctx.scale(q, q); ctx.font = F.en(900, 260); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = rgba(G.CREAM, 0.9); ctx.fillText('?', 0, 0); ctx.restore(); }
    G.typeText(ctx, '翻过去有多惨', 300, 900, F.zh(700, 40), rgba(G.CREAM, 0.6), inv(D * 0.6, D * 0.9, lt), { caret: false });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.tail_avg = (ctx, s, lt, C) => {
    // camera pushes down past the 100万 line to the worst days; their average sits lower still
    const D = s.vizDur, cam = E.io(inv(0.1, D * 0.55, lt)), off = -260 * cam;
    ctx.save(); ctx.translate(0, off);
    const y0 = 380, yt = 640;
    ctx.fillStyle = rgba(C.fg, 0.4); ctx.fillRect(200, y0 - 2, 1520, 4);
    ctx.fillStyle = rgba(C.fg, 0.8); ctx.fillRect(200, yt - 5, 1520, 10);
    G.typeText(ctx, '100万', 210, yt - 20, F.en(800, 32), C.fg, 1, { caret: false });
    const worst = [0.55, 0.85, 0.7, 1.0, 0.62];
    worst.forEach((w, i) => { ctx.fillStyle = PAL.red.t[2 + (i % 2)]; ctx.fillRect(620 + i * 150, y0, 100, (yt - y0) + w * 420 * E.o3(inv(0.2 + i * 0.1, 0.9 + i * 0.1, lt))); });
    const avg = worst.reduce((a, b) => a + b, 0) / worst.length, ya = yt + avg * 420, ap = E.io(inv(D * 0.55, D * 0.85, lt));
    ctx.setLineDash([30, 14]); ctx.strokeStyle = G.INK; ctx.lineWidth = 10; ctx.beginPath(); ctx.moveTo(520, ya); ctx.lineTo(520 + 900 * ap, ya); ctx.stroke(); ctx.setLineDash([]);
    tag(ctx, '最惨几档 · 平均', 1540, ya, C, inv(D * 0.65, D * 0.9, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    ctx.restore();
    vizCaption(ctx, s, lt, C, { y: 230 });
  };

  // ── 风险偏好 ──
  VIZ.platform_rope = (ctx, s, lt, C) => {
    const D = s.vizDur;
    ctx.fillStyle = C.fg; ctx.fillRect(160, 560, 620, 34); ctx.fillRect(240, 594, 40, 480); ctx.fillRect(660, 594, 40, 480);
    const lean = 10 + 8 * Math.sin(lt * 2) * inv(0.5, 1.2, lt);
    figAt(ctx, 690, 560, 280, { torso: lean, head: 10, aL1: -40, aR1: -30, aL2: -60, aR2: -50, lL1: -6, lR1: 6 }, C.fg);
    // thin rope from the hip down past the edge, fraying
    const sw = Math.sin(lt * 2.6) * 24;
    ctx.save(); ctx.strokeStyle = G.CREAM; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(700, 480); ctx.quadraticCurveTo(900 + sw, 760, 860 + sw * 0.5, 1060); ctx.stroke(); ctx.restore();
    const fr = inv(D * 0.45, D * 0.8, lt);
    if (fr > 0) { ctx.save(); ctx.strokeStyle = PAL.red.t[4]; ctx.lineWidth = 3; for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.moveTo(880 + sw * 0.7, 820); ctx.lineTo(880 + sw * 0.7 + (i - 1.5) * 20 * fr, 840 + 16 * fr); ctx.stroke(); } ctx.restore(); }
    tag(ctx, '敢跳', 520, 1000, C, inv(0.3, 0.8, lt), { px: 34, bg: C.fg, fg: C.bg });
    tag(ctx, '绳子很细', 1180, 840, C, inv(D * 0.45, D * 0.75, lt), { px: 36, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.knob = (ctx, s, lt, C) => {
    const D = s.vizDur, cx = W / 2, cy = 660, R = 230;
    const a = lerp(-2.3, 2.3, E.io3(inv(0.3, D * 0.75, lt)));
    for (let i = 0; i <= 20; i++) { const t = lerp(-2.3, 2.3, i / 20) - Math.PI / 2, on = lerp(-2.3, 2.3, i / 20) <= a; ctx.save(); ctx.translate(cx + Math.cos(t) * (R + 70), cy + Math.sin(t) * (R + 70)); ctx.rotate(t); ctx.fillStyle = on ? G.INK : rgba(G.INK, 0.2); ctx.fillRect(-8, -18 - i * 1.6, 16, 36 + i * 3.2); ctx.restore(); }
    G.disc(ctx, cx, cy, R, G.INK); G.disc(ctx, cx, cy, R - 30, C.soft);
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(a); ctx.fillStyle = G.INK; ctx.beginPath(); ctx.roundRect(-14, -R + 40, 28, 120, 14); ctx.fill(); ctx.restore();
    G.typeText(ctx, '小', cx - R - 130, cy + R + 40, F.zh(900, 44), G.INK, inv(0.2, 0.6, lt), { caret: false });
    G.typeText(ctx, '大', cx + R + 90, cy + R + 40, F.zh(900, 44), G.INK, inv(0.2, 0.6, lt), { caret: false });
    tag(ctx, '风险偏好', cx, cy + R + 140, C, inv(D * 0.4, D * 0.7, lt), { px: 48, bg: G.INK, fg: C.soft });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };
  VIZ.hand_line = (ctx, s, lt, C) => {
    const D = s.vizDur, raise = E.oBack(inv(0.2, 0.9, lt));
    const lp = E.io(inv(D * 0.3, D * 0.8, lt));
    ctx.save(); ctx.strokeStyle = G.CREAM; ctx.lineWidth = 10; ctx.lineCap = 'round'; ctx.setLineDash([2, 26]);
    ctx.beginPath(); for (let i = 0; i <= 40 * lp; i++) { const x = lerp(240, 1700, i / 40), y = 760 + 40 * Math.sin(i * 0.45); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); ctx.restore();
    figAt(ctx, 760, 1000, 380, { torso: 0, aR1: lerp(10, -170, raise), aR2: lerp(10, -175, raise), aL1: -10, aL2: -6 }, C.fg);
    if (raise > 0.6) tag(ctx, '我愿意', 1040, 420, C, inv(0.6, 1.1, lt), { px: 44, bg: G.CREAM, fg: G.INK });
    tag(ctx, '自己划的线', 1500, 700, C, inv(D * 0.6, D * 0.85, lt), { px: 34, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.bag_split = (ctx, s, lt, C) => {
    const D = s.vizDur, k = E.io3(inv(D * 0.25, D * 0.65, lt));
    for (let i = 0; i < 8; i++) {
      const left = i < 3, sx = W / 2 + (i % 4 - 1.5) * 120, sy = 620 + Math.floor(i / 4) * 140;
      const tx = left ? 560 + (i % 3 - 1) * 130 : 1260 + ((i - 3) % 3 - 1) * 130, ty = left ? 700 : 640 + Math.floor((i - 3) / 3) * 150;
      moneyBag(ctx, lerp(sx, tx, k), lerp(sy, ty, k), 52, left ? PAL.gold.t[2] : PAL.green.t[2], '¥', G.INK);
    }
    tag(ctx, '拿去投资', 560, 900, C, inv(D * 0.6, D * 0.85, lt), { px: 38, bg: PAL.gold.t[2], fg: G.INK });
    tag(ctx, '留在手里', 1260, 980, C, inv(D * 0.6, D * 0.85, lt), { px: 38, bg: PAL.green.t[2], fg: G.CREAM });
    tag(ctx, '压多少？', W / 2, 430, C, inv(0.2, 0.7, lt) * (1 - k * 0.6), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };
  VIZ.ground_shake = (ctx, s, lt, C) => {
    const D = s.vizDur, q = inv(D * 0.3, D * 0.55, lt), [sx, sy] = [Math.sin(lt * 37) * 14 * q, Math.cos(lt * 29) * 8 * q];
    ctx.save(); ctx.translate(sx, sy);
    ctx.fillStyle = C.fg; ctx.beginPath(); ctx.moveTo(0, 900);
    for (let i = 0; i <= 30; i++) ctx.lineTo(i * W / 30, 900 + Math.sin(i * 1.3 + lt * 9) * 22 * q);
    ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = C.bg; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(900, 905); ctx.lineTo(940, 960); ctx.lineTo(910, 1010); ctx.lineTo(960, 1080); ctx.stroke();
    ctx.restore();
    figAt(ctx, 930 + sx * 0.6, 900, 380, { torso: 6 * Math.sin(lt * 8) * q, aL1: -30 - 20 * q, aR1: 30 + 20 * q, aL2: -60, aR2: 60, lL1: -14, lR1: 14 }, C.fg);
    tag(ctx, '愿意', 930, 380, C, inv(0.2, 0.7, lt), { px: 48, bg: C.fg, fg: C.bg });
    tag(ctx, '扛得住？', 1500, 760, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.carry_pole = (ctx, s, lt, C) => {
    const D = s.vizDur, bend = E.io(inv(0.3, D * 0.7, lt)), cx = W / 2, sy = 520;
    figAt(ctx, cx, 960, 420, { torso: 4, aL1: -150, aR1: 150, aL2: -170, aR2: 170, lL1: -14, lR1: 14, lL2: -4, lR2: 4 }, C.fg);
    const L = 640, sag = 40 + 150 * bend + 6 * Math.sin(lt * 6) * bend;
    ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 22; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(cx - L, sy + sag); ctx.quadraticCurveTo(cx, sy - sag * 0.9, cx + L, sy + sag); ctx.stroke(); ctx.restore();
    for (const d of [-1, 1]) { const x = cx + d * (L - 30), y = sy + sag; ctx.strokeStyle = G.INK; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y + 150); ctx.stroke(); ctx.fillStyle = G.INK; ctx.fillRect(x - 90, y + 150, 180, 160); }
    if (bend > 0.8) { const f = inv(D * 0.7, D * 0.9, lt); ctx.save(); ctx.globalAlpha = f; ctx.strokeStyle = PAL.red.t[3]; ctx.lineWidth = 6; for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.moveTo(cx - 40 + i * 30, sy - sag * 0.45 - 30); ctx.lineTo(cx - 60 + i * 30, sy - sag * 0.45 - 80); ctx.stroke(); } ctx.restore(); }
    tag(ctx, '风险承受能力', cx, 1010, C, inv(D * 0.4, D * 0.7, lt), { px: 46, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) });
  };
  VIZ.bed_awake = (ctx, s, lt, C) => {
    const D = s.vizDur;
    ctx.fillStyle = rgba(C.fg, 0.15); ctx.fillRect(360, 640, 1200, 40);
    ctx.fillStyle = C.fg; ctx.fillRect(330, 470, 40, 420); ctx.fillRect(1550, 600, 40, 290); ctx.fillRect(330, 680, 1260, 70);
    ctx.fillStyle = PAL.purple.t[3]; ctx.beginPath(); ctx.roundRect(560, 560, 980, 130, 40); ctx.fill();
    G.disc(ctx, 470, 600, 62, G.CREAM);
    // eyes open, blink never comes
    ctx.fillStyle = G.INK; ctx.fillRect(440, 590, 18, 10); ctx.fillRect(482, 590, 18, 10);
    // headboard number ticking down (account value, not a market chart)
    const v = Math.round(lerp(100, 72, E.io(inv(0.3, D * 0.85, lt))));
    ctx.fillStyle = rgba(C.fg, 0.12); ctx.fillRect(160, 330, 380, 110);
    G.maskText(ctx, v + '万', 350, 420, F.en(900, 84), PAL.red.t[3], inv(0.1, 0.6, lt), { align: 'center' });
    G.typeText(ctx, '↓', 560, 420, F.en(900, 70), PAL.red.t[3], inv(0.4, 0.8, lt), { caret: false });
    tag(ctx, '睡得着吗？', 1300, 420, C, inv(D * 0.5, D * 0.8, lt), { px: 44, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };

  // ───────── finance-v003 scene library, batch 3 (VaR long, 14 lines, 2026-10-30) ─────────
  // Film-wide metaphor (金融专家): 0 line on top, losses point DOWN, the gold 100万 line is a threshold
  // (门槛), never a floor or a cap — the tail below it has no drawn bottom. Days = tiles. No tickers,
  // no bank names, no K-lines, no casino props, no rising-only curves. Each scene has its own layout.
  Object.assign(VPAL, {
    cap_crossed: 'gold', bank_report: 'purple', three_slots: 'cream', slots_filled: 'ink', grid_10x10: 'green',
    square_over: 'red', year_strip: 'ochre', red_cluster: 'ink', bottomless: 'purple', old_ledger: 'cream',
    sky_change: 'ink', expect_actual: 'red', tail_dots_es: 'gold', bank_on_line: 'ochre',
  });
  const GOLD = PAL.gold.t[2], REDT = PAL.red.t[2];
  function clockIcon(ctx, x, y, r, col, hand, lt) {
    G.ring(ctx, x, y, r, r * 0.12, col);
    ctx.save(); ctx.strokeStyle = col; ctx.lineCap = 'round'; ctx.lineWidth = r * 0.1;
    const a = -Math.PI / 2 + lt * 1.6;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * r * 0.7, y + Math.sin(a) * r * 0.7); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + r * 0.45, y); ctx.stroke(); ctx.restore();
    G.disc(ctx, x, y, r * 0.1, hand || col);
  }
  function gauge(ctx, x, y, r, col, p, accent) {
    ctx.save(); ctx.lineCap = 'round';
    ctx.strokeStyle = rgba(col, 0.25); ctx.lineWidth = r * 0.16; ctx.beginPath(); ctx.arc(x, y, r, Math.PI, 2 * Math.PI); ctx.stroke();
    ctx.strokeStyle = accent; ctx.beginPath(); ctx.arc(x, y, r, Math.PI, Math.PI + Math.PI * 0.99 * clamp(p)); ctx.stroke();
    ctx.fillStyle = col; for (let i = 0; i <= 10; i++) { const a = Math.PI + Math.PI * i / 10; ctx.fillRect(x + Math.cos(a) * r * 1.18 - 3, y + Math.sin(a) * r * 1.18 - 3, 6, 6); }
    ctx.restore();
    ctx.save(); ctx.font = F.en(900, r * 0.55); ctx.textAlign = 'center'; ctx.fillStyle = col; ctx.fillText('%', x, y - r * 0.05); ctx.restore();
  }
  function tile(ctx, x, y, sz, col, k = 1) { const z = sz * k; ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(x + (sz - z) / 2, y + (sz - z) / 2, z, z, Math.max(2, z * 0.14)); ctx.fill(); }
  function goldLine(ctx, x0, x1, y, p = 1, w = 12, col = GOLD, glow = 0) {
    ctx.save(); if (glow) { ctx.shadowColor = col; ctx.shadowBlur = glow; }
    ctx.fillStyle = col; ctx.fillRect(x0, y - w / 2, (x1 - x0) * clamp(p), w); ctx.restore();
  }

  VIZ.cap_crossed = (ctx, s, lt, C) => { // 大大的「100万」，下面一条线被打上叉，标「上限」
    const D = s.vizDur, cx = 1060;
    G.maskText(ctx, '100万', cx, 640, F.en(900, 250), C.fg, inv(0.05, 0.6, lt), { align: 'center' });
    const lp = E.io(inv(0.35, 1.0, lt));
    ctx.fillStyle = C.fg; ctx.fillRect(cx - 520, 760, 1040 * lp, 14);
    tag(ctx, '上限', cx + 600, 767, C, inv(0.6, 1.1, lt), { px: 44, bg: C.fg, fg: C.bg });
    const xp = E.o3(inv(D * 0.45, D * 0.8, lt)), [sx, sy] = shake(lt, D * 0.62, 10);
    ctx.save(); ctx.translate(sx, sy); ctx.strokeStyle = REDT; ctx.lineWidth = 30; ctx.lineCap = 'round';
    const L = cx - 170, R = cx + 170, T = 680, B = 850;
    ctx.beginPath(); ctx.moveTo(L, T); ctx.lineTo(lerp(L, R, Math.min(1, xp * 2)), lerp(T, B, Math.min(1, xp * 2))); ctx.stroke();
    if (xp > 0.5) { const q = (xp - 0.5) * 2; ctx.beginPath(); ctx.moveTo(R, T); ctx.lineTo(lerp(R, L, q), lerp(T, B, q)); ctx.stroke(); }
    ctx.restore();
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.bank_report = (ctx, s, lt, C) => { // 不写名字的银行大楼 + 只有一个数字的报告卡，卡角标「VaR」
    const D = s.vizDur, gy = 960, bp = E.o3(inv(0.05, 0.7, lt));
    ctx.fillStyle = rgba(C.fg, 0.2); ctx.fillRect(140, gy, 1640, 6);
    ctx.save(); ctx.translate(560, gy); ctx.scale(1, bp); ctx.translate(-560, -gy);
    G.poly(ctx, [[330, 500], [790, 500], [560, 380]], G.CREAM);
    ctx.fillStyle = G.CREAM; ctx.fillRect(340, 510, 440, 30); ctx.fillRect(340, 910, 440, 50);
    for (let i = 0; i < 5; i++) ctx.fillRect(365 + i * 88, 555, 42, 340);
    ctx.restore();
    const cp = E.oBack(inv(D * 0.25, D * 0.6, lt)), cx = 1330, cy = 650;
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.04 * (1 - cp)); ctx.scale(cp, cp);
    ctx.fillStyle = G.CREAM; ctx.beginPath(); ctx.roundRect(-300, -220, 600, 440, 26); ctx.fill();
    ctx.fillStyle = rgba(G.INK, 0.15); for (let i = 0; i < 3; i++) ctx.fillRect(-240, 110 + i * 32, 480 - i * 120, 12);
    ctx.font = F.en(900, 150); ctx.textAlign = 'center'; ctx.fillStyle = G.INK; ctx.fillText('100万', 0, 40);
    ctx.fillStyle = PAL.purple.t[2]; ctx.beginPath(); ctx.roundRect(150, -200, 130, 64, 14); ctx.fill();
    ctx.font = F.en(900, 40); ctx.fillStyle = G.CREAM; ctx.fillText('VaR', 215, -153);
    ctx.restore();
    ctx.save(); ctx.globalAlpha = inv(D * 0.5, D * 0.8, lt); ctx.strokeStyle = rgba(C.fg, 0.6); ctx.lineWidth = 5; ctx.setLineDash([14, 12]);
    ctx.beginPath(); ctx.moveTo(800, 700); ctx.lineTo(1010, 680); ctx.stroke(); ctx.restore();
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.three_slots = (ctx, s, lt, C) => { // 三个格子依次亮起：钱袋、时钟、百分比刻度
    const D = s.vizDur, y = 680, xs = [500, 960, 1420], labs = ['金额', '时间', '把握'];
    xs.forEach((x, i) => {
      const on = E.oBack(inv(0.3 + i * D * 0.2, 0.75 + i * D * 0.2, lt)), lit = clamp(on);
      ctx.fillStyle = lit > 0.05 ? mix('#e9e0cf', PAL.gold.t[4], lit) : '#e9e0cf';
      ctx.beginPath(); ctx.roundRect(x - 190, y - 220, 380, 380, 36); ctx.fill();
      ctx.strokeStyle = rgba(G.INK, 0.6 * lit + 0.15); ctx.lineWidth = 8; ctx.stroke();
      if (lit > 0) {
        ctx.save(); ctx.globalAlpha = lit; ctx.translate(x, y - 30); ctx.scale(on, on); ctx.translate(-x, -(y - 30));
        if (i === 0) moneyBag(ctx, x, y - 10, 100, PAL.ochre.t[1], '¥', G.CREAM);
        else if (i === 1) clockIcon(ctx, x, y - 30, 110, G.INK, REDT, lt);
        else gauge(ctx, x, y + 40, 120, G.INK, inv(D * 0.6, D * 0.95, lt), PAL.green.t[2]);
        ctx.restore();
      }
      tag(ctx, labs[i], x, y + 230, C, inv(0.5 + i * D * 0.2, 0.9 + i * D * 0.2, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) }, { y: 230 });
  };
  VIZ.slots_filled = (ctx, s, lt, C) => { // 三个格子里填上「一天」「99%」「100万（假设）」 — rows, not columns
    const D = s.vizDur, rows = [['时间', '一天'], ['把握', '99%'], ['金额', '100万']], x0 = 560, x1 = 1720;
    rows.forEach(([k, v], i) => {
      const y = 430 + i * 185, ap = E.o3(inv(0.1 + i * 0.15, 0.6 + i * 0.15, lt)), fp = inv(0.5 + i * D * 0.22, 0.9 + i * D * 0.22, lt);
      ctx.fillStyle = rgba(C.fg, 0.08); ctx.fillRect(x0, y - 70, (x1 - x0) * ap, 140);
      ctx.strokeStyle = rgba(C.fg, 0.35); ctx.lineWidth = 3; ctx.strokeRect(x0, y - 70, (x1 - x0) * ap, 140);
      G.typeText(ctx, k, x0 + 40, y + 16, F.zh(700, 44), C.dim, ap, { caret: false });
      G.maskText(ctx, v, x0 + 340, y + 34, F.en(900, 96), i === 2 ? GOLD : C.fg, fp);
      if (i === 2) tag(ctx, '假设', x1 - 130, y, C, inv(D * 0.75, D * 0.95, lt), { px: 38, bg: GOLD, fg: G.INK });
    });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.grid_10x10 = (ctx, s, lt, C) => { // 一百个日历方块十乘十：九十九个没过门槛，一个红色
    const D = s.vizDur, c = 52, x0 = 1060, y0 = 340, red = 46;
    for (let i = 0; i < 100; i++) {
      const r = Math.floor(i / 10), k = i % 10, p = clamp(inv(0.1 + (r + k) * 0.05, 0.45 + (r + k) * 0.05, lt) * 1.4);
      if (p <= 0) continue;
      const isRed = i === red && lt > D * 0.45;
      tile(ctx, x0 + k * c, y0 + r * c, c - 8, isRed ? REDT : rgba(G.CREAM, 0.88), E.oBack(p) * (isRed ? 1 + 0.12 * Math.sin(lt * 9) : 1));
    }
    goldLine(ctx, x0 - 30, x0 + 10 * c + 22, y0 + 10 * c + 26, inv(0.4, 1.1, lt), 12);
    G.typeText(ctx, '门槛', x0 + 10 * c + 40, y0 + 10 * c + 40, F.zh(800, 36), GOLD, inv(0.8, 1.2, lt), { caret: false });
    G.maskText(ctx, '99', 330, 700, F.en(900, 220), C.fg, inv(D * 0.2, D * 0.5, lt));
    G.typeText(ctx, '天没过线', 340, 790, F.zh(800, 46), C.dim, inv(D * 0.35, D * 0.6, lt), { caret: false });
    G.maskText(ctx, '/ 100', 640, 700, F.en(800, 80), C.dim, inv(D * 0.3, D * 0.55, lt));
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.square_over = (ctx, s, lt, C) => { // 那个红色方块越过门槛线，标「超线」
    const D = s.vizDur, yt = 600, x = 960, sz = 220;
    goldLine(ctx, 160, 1760, yt, E.io(inv(0.05, 0.6, lt)), 16, PAL.gold.t[3]);
    tag(ctx, LOSS_TH, 300, yt + 70, C, inv(0.3, 0.7, lt), { px: 32, bg: PAL.gold.t[3], fg: G.INK });
    const f = E.io3(inv(D * 0.2, D * 0.7, lt)), y = lerp(330, yt + 110, f), [sx, sy] = shake(lt, D * 0.48, 8);
    ctx.save(); ctx.translate(sx, sy);
    ctx.fillStyle = PAL.red.deep; ctx.beginPath(); ctx.roundRect(x - sz / 2, y, sz, sz, 24); ctx.fill();
    ctx.strokeStyle = G.CREAM; ctx.lineWidth = 8; ctx.stroke();
    ctx.restore();
    arrowV(ctx, x + 200, yt, y + sz, G.CREAM, 6, inv(D * 0.65, D * 0.85, lt));
    tag(ctx, '超线', x + 360, yt + 150, C, inv(D * 0.6, D * 0.85, lt), { px: 56, bg: G.CREAM, fg: PAL.red.deep });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.year_strip = (ctx, s, lt, C) => { // 一整年日历条，约二百五十格，零散亮起两三个红格
    const D = s.vizDur, cols = 50, rows = 5, x0 = 150, cw = 32.4, y0 = 470, ch = 70, reds = new Set([37, 141, 212]);
    for (let i = 0; i < cols * rows; i++) {
      const r = Math.floor(i / cols), k = i % cols, p = inv(0.05 + k * 0.022, 0.3 + k * 0.022, lt);
      if (p <= 0) continue;
      const red = reds.has(i) && lt > D * 0.4 + [...reds].indexOf(i) * D * 0.12;
      ctx.fillStyle = red ? PAL.red.t[1] : rgba(G.INK, 0.78);
      ctx.fillRect(x0 + k * cw, y0 + r * ch, cw - 6, (ch - 10) * E.o3(p));
    }
    G.typeText(ctx, '一年 ≈ 250 个交易日', x0, y0 + rows * ch + 60, F.zh(800, 40), G.INK, inv(0.4, 1.0, lt), { caret: false });
    tag(ctx, '平均 2~3 天超线', 1540, y0 + rows * ch + 46, C, inv(D * 0.7, D * 0.92, lt), { px: 38, bg: PAL.red.t[1], fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) }, { y: 230 });
  };
  VIZ.red_cluster = (ctx, s, lt, C) => { // 红格不再零散，而是几个挤在一起连着亮 — one zoomed row
    const D = s.vizDur, n = 16, cw = 100, x0 = 160, y = 600, cl = [7, 8, 9, 10, 11];
    for (let k = 0; k < n; k++) {
      const p = E.oBack(inv(0.05 + k * 0.04, 0.4 + k * 0.04, lt)), j = cl.indexOf(k);
      const on = j >= 0 && lt > D * 0.3 + j * D * 0.08, fl = on ? 0.75 + 0.25 * Math.sin(lt * 8 + j) : 1;
      ctx.save(); if (on) { ctx.shadowColor = REDT; ctx.shadowBlur = 40 * fl; }
      tile(ctx, x0 + k * cw, y - 60, 84, on ? rgba(REDT, 0.6 + 0.4 * fl) : rgba(G.CREAM, 0.18), clamp(p));
      ctx.restore();
    }
    const bp = E.io(inv(D * 0.75, D * 0.95, lt));
    if (bp > 0) { ctx.strokeStyle = G.CREAM; ctx.lineWidth = 6; const a = x0 + 7 * cw, b = x0 + 12 * cw - 16;
      ctx.beginPath(); ctx.moveTo(a, y + 60); ctx.lineTo(a, y + 90); ctx.lineTo(lerp(a, b, bp), y + 90); if (bp > 0.98) ctx.lineTo(b, y + 60); ctx.stroke(); }
    tag(ctx, '扎堆来', x0 + 9.5 * cw, y + 170, C, inv(D * 0.8, D * 0.98, lt), { px: 48, bg: REDT, fg: G.CREAM });
    G.typeText(ctx, '不保证哪天安全', 1760, 420, F.zh(800, 40), C.dim, inv(D * 0.2, D * 0.5, lt), { align: 'right', caret: false });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.bottomless = (ctx, s, lt, C) => { // 门槛线下面没有底，一片看不到头的黑，红格往下掉 — a deep shaft
    const D = s.vizDur, yt = 470, sx0 = 780, sx1 = 1140;
    const g = ctx.createLinearGradient(0, yt, 0, H); g.addColorStop(0, PAL.purple.deep); g.addColorStop(1, '#000');
    ctx.fillStyle = g; ctx.fillRect(sx0, yt, sx1 - sx0, H - yt);
    ctx.fillStyle = PAL.purple.t[3]; ctx.fillRect(140, yt, sx0 - 140, H - yt); ctx.fillRect(sx1, yt, 1780 - sx1, H - yt);
    goldLine(ctx, 140, 1780, yt, E.io(inv(0.05, 0.6, lt)), 14, GOLD, 24);
    for (let i = 0; i < 4; i++) {
      const t0 = D * 0.25 + i * D * 0.14, f = Math.max(0, lt - t0), y = yt - 60 + 260 * f * f;
      if (lt < t0 || y > H + 80) continue;
      tile(ctx, sx0 + 70 + (i % 2) * 140, y, 80, rgba(REDT, Math.max(0.15, 1 - (y - yt) / 700)));
    }
    ctx.fillStyle = rgba(G.CREAM, 0.5); for (let k = 1; k < 6; k++) ctx.fillRect(sx1 + 20, yt + k * 100, 40, 4);
    G.maskText(ctx, '?', sx1 + 210, 900, F.en(900, 180), rgba(G.CREAM, 0.85), inv(D * 0.55, D * 0.8, lt));
    tag(ctx, '亏多深，它不管', 1500, yt - 80, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.old_ledger = (ctx, s, lt, C) => { // 一本旧账本翻开，数字飘出来拼成那条门槛线
    const D = s.vizDur, bx = 960, by = 900, op = E.o3(inv(0.05, 0.6, lt));
    ctx.save(); ctx.translate(bx, by);
    for (const sg of [-1, 1]) { ctx.save(); ctx.scale(sg, 1); ctx.transform(1, 0, -0.18 * op, 1, 0, 0);
      G.poly(ctx, [[0, 0], [380 * op, -30], [400 * op, -260], [0, -250]], '#d9c9a6');
      ctx.fillStyle = rgba(G.INK, 0.25); for (let i = 0; i < 6; i++) ctx.fillRect(40 * op, -220 + i * 34, 300 * op, 6); ctx.restore(); }
    ctx.fillStyle = PAL.ochre.deep; ctx.fillRect(-6, -255, 12, 260); ctx.restore();
    const yt = 430, digits = '3170482596';
    for (let i = 0; i < 18; i++) {
      const t0 = 0.4 + i * D * 0.03, f = E.io(inv(t0, t0 + D * 0.35, lt)), sx = bx - 300 + (i * 97) % 600, tx = 280 + i * 80;
      if (f <= 0) continue;
      const x = lerp(sx, tx, f), y = lerp(by - 220, yt, f) - Math.sin(f * Math.PI) * 120;
      ctx.save(); ctx.globalAlpha = 1 - 0.6 * clamp((f - 0.9) * 10); ctx.font = F.mono(46); ctx.fillStyle = G.INK; ctx.textAlign = 'center';
      ctx.fillText(digits[i % 10], x, y); ctx.restore();
    }
    goldLine(ctx, 240, 1700, yt + 24, inv(D * 0.7, D * 0.92, lt), 12, PAL.ochre.t[1]);
    tag(ctx, '过去的数据', 1520, 760, C, inv(D * 0.35, D * 0.6, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) }, { y: 230 });
  };
  VIZ.sky_change = (ctx, s, lt, C) => { // 天色骤变，门槛线开始抖动、变虚
    const D = s.vizDur, k = E.io(inv(D * 0.2, D * 0.5, lt)), yt = 760;
    ctx.fillStyle = mix('#7fb4d9', '#1b1d2a', k); ctx.fillRect(0, 320, W, yt - 320);
    if (k < 0.9) { ctx.save(); ctx.globalAlpha = 1 - k; G.disc(ctx, 1560, 460, 80, PAL.gold.t[3]); ctx.restore(); }
    ctx.save(); ctx.globalAlpha = k;
    for (const [x, y, r] of [[700, 430, 110], [820, 400, 140], [960, 440, 120], [1220, 420, 130], [1350, 450, 100]]) G.disc(ctx, x, y, r, '#3d3f52');
    ctx.restore();
    if (lt > D * 0.45 && (Math.floor(lt * 6) % 4 === 0)) bolt(ctx, 1000, 470, 150, PAL.gold.t[4]);
    ctx.fillStyle = PAL.ink.t[3]; ctx.fillRect(0, yt, W, H - yt);
    const jit = k * 18, dash = k > 0.3;
    ctx.save(); ctx.globalAlpha = 1 - 0.55 * k; ctx.strokeStyle = GOLD; ctx.lineWidth = 12; if (dash) ctx.setLineDash([40, 26]);
    ctx.beginPath(); for (let i = 0; i <= 40; i++) { const x = 160 + i * 40, y = yt - 40 + Math.sin(i * 1.3 + lt * 20) * jit; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); ctx.restore();
    tag(ctx, '容易低估', 1520, yt + 110, C, inv(D * 0.6, D * 0.85, lt), { px: 44, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.expect_actual = (ctx, s, lt, C) => { // 预期的两三个红格旁边，实际亮起一大片红格 — two panels
    const D = s.vizDur, c = 40, panels = [[260, '预期', [12, 57]], [1040, '实际', null]];
    panels.forEach(([x0, lab, reds], pi) => {
      ctx.fillStyle = rgba(G.CREAM, 0.12); ctx.fillRect(x0 - 30, 380, 12 * c + 60, 8 * c + 60);
      for (let i = 0; i < 96; i++) {
        const r = Math.floor(i / 12), k = i % 12;
        const red = reds ? reds.includes(i) : ((i * 37) % 96 < 34) && lt > D * 0.35 + ((i * 13) % 20) * D * 0.02;
        tile(ctx, x0 + k * c, 410 + r * c, c - 6, red ? (pi ? PAL.red.deep : G.CREAM) : rgba(G.CREAM, 0.28), clamp(inv(0.05 + pi * D * 0.25, 0.5 + pi * D * 0.25, lt) * 1.3));
      }
      tag(ctx, lab, x0 + 6 * c, 900, C, inv(0.2 + pi * D * 0.25, 0.6 + pi * D * 0.25, lt), { px: 44, bg: pi ? G.CREAM : rgba(G.CREAM, 0.3), fg: pi ? PAL.red.deep : G.CREAM });
    });
    G.maskText(ctx, '>', 890, 620, F.en(900, 120), G.CREAM, inv(D * 0.6, D * 0.8, lt), { align: 'center' });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.tail_dots_es = (ctx, s, lt, C) => { // 推到最深的几个红格，取平均画一条更低的线，标「预期尾部损失 ES」
    const D = s.vizDur, z = 1 + 0.35 * E.io(inv(0.1, D * 0.5, lt)), yt = 440;
    ctx.save(); ctx.translate(W / 2, yt); ctx.scale(z, z); ctx.translate(-W / 2, -yt);
    ctx.fillStyle = rgba(G.INK, 0.8); ctx.fillRect(260, yt - 4, 1400, 8);
    G.typeText(ctx, LOSS_TH, 360, yt - 24, F.zh(800, 28), G.INK, 1, { caret: false });
    const deep = [[520, 0.35], [700, 0.8], [880, 0.5], [1060, 1.0], [1240, 0.62], [1420, 0.45]];
    deep.forEach(([x, d], i) => { const p = E.oBack(inv(0.2 + i * 0.08, 0.6 + i * 0.08, lt)); ctx.strokeStyle = rgba(G.INK, 0.3); ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x, yt); ctx.lineTo(x, yt + 60 + d * 360); ctx.stroke(); tile(ctx, x - 30, yt + 30 + d * 360, 60, REDT, clamp(p)); });
    const avg = deep.reduce((a, b) => a + b[1], 0) / deep.length, ya = yt + 60 + avg * 360, ap = E.io(inv(D * 0.45, D * 0.75, lt));
    ctx.setLineDash([28, 14]); ctx.strokeStyle = PAL.purple.t[1]; ctx.lineWidth = 10; ctx.beginPath(); ctx.moveTo(420, ya); ctx.lineTo(420 + 1140 * ap, ya); ctx.stroke(); ctx.setLineDash([]);
    ctx.restore();
    tag(ctx, '预期尾部损失 ES', 1480, 960, C, inv(D * 0.65, D * 0.9, lt), { px: 42, bg: PAL.purple.t[1], fg: G.CREAM });
    tag(ctx, '坏日子平均', 460, 960, C, inv(D * 0.55, D * 0.8, lt), { px: 36, bg: G.INK, fg: GOLD });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.bank_on_line = (ctx, s, lt, C) => { // 银行大楼立在门槛线上，低头看线下那片黑，画面停住
    const D = s.vizDur, yt = 700, cx = 960, f = E.io(inv(0.05, D * 0.6, lt));
    const g = ctx.createLinearGradient(0, yt, 0, H); g.addColorStop(0, '#2a1d0c'); g.addColorStop(1, '#000');
    ctx.fillStyle = g; ctx.fillRect(0, yt, W, H - yt);
    goldLine(ctx, 0, W, yt, 1, 16, GOLD, 30 * (0.6 + 0.4 * Math.sin(lt * 3)));
    ctx.save(); ctx.translate(cx, yt); ctx.rotate(0.05 * f); ctx.translate(-cx, -yt);
    G.poly(ctx, [[cx - 210, yt - 330], [cx + 210, yt - 330], [cx, yt - 440]], G.INK);
    ctx.fillStyle = G.INK; ctx.fillRect(cx - 200, yt - 325, 400, 26); ctx.fillRect(cx - 200, yt - 44, 400, 44);
    for (let i = 0; i < 4; i++) ctx.fillRect(cx - 175 + i * 100, yt - 290, 50, 240);
    ctx.restore();
    ctx.save(); ctx.globalAlpha = 0.5 * f; ctx.strokeStyle = G.CREAM; ctx.setLineDash([10, 14]); ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(cx + 40, yt + 30); ctx.lineTo(cx + 120, yt + 260); ctx.stroke(); ctx.restore();
    tag(ctx, '扛得住吗？', 1460, 860, C, inv(D * 0.4, D * 0.7, lt), { px: 48, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };

  // ───────── finance-v003 scene library, batch 6 (risk family, 2026-10-30) ─────────
  // #6 系统性风险 · #7 非系统性风险 · #8 套利定价理论 APT · #9 道德风险 · #10 逆向选择 — 53 scenes, one per line.
  // 金融专家 rules: losses/falls always drawn DOWNWARD, no real company / fund / institution names, no formulas
  // (APT readings stack into a column — no sum sign, no factor algebra), no rising-only return curves, no casino props.
  // Each scene has its own layout so the series visual-dupe gate (dHash + layout corr) stays clean;
  // the "回到开头" finales mirror / recolour their hook scene instead of repeating it.
  Object.assign(VPAL, {
    umbrella_holes: 'ink', sea_title: 'purple', boats_sink: 'cream', street_dim: 'ochre', gears_dial: 'green', lines_offset: 'cream',
    lines_bundle: 'red', net_holes: 'purple', boats_split: 'gold', umbrella_look: 'ochre',
    rock_split: 'ink', shop_street: 'green', tea_sign: 'cream', shutter_down: 'purple', basket_break: 'red', ten_baskets: 'gold',
    hooks_colors: 'ochre', wind_baskets: 'ink', pits_fill: 'cream',
    dial_needles: 'ink', mixer_title: 'purple', mixer_one: 'cream', mixer_faders: 'green', receipt_jar: 'ochre', rope_strain: 'red',
    cars_road: 'gold', springs: 'purple', faders_sum: 'cream', apple_stalls: 'green', tags_converge: 'ink', mover_slip: 'red',
    ruler_fog: 'ochre', dial_all: 'gold',
    net_step: 'ink', policy_title: 'gold', car_lane: 'cream', care_bar: 'green', airbag_tower: 'purple', coins_bricks: 'red',
    deductible: 'ochre', timeline_after: 'ink', footprints_edge: 'cream',
    door_queue: 'ink', door_title: 'gold', counter_cough: 'cream', price_jump: 'red', queue_leave: 'green', two_keys: 'purple',
    magnifier_mid: 'ochre', cars_leave: 'ink', table_light: 'purple', timeline_before: 'gold', queue_front: 'red',
  });
  const b6fr = (v) => v - Math.floor(v);
  const b6rnd = (i, s = 0) => b6fr(Math.sin(i * 12.9898 + s * 78.233) * 43758.5453);
  function b6title(ctx, txt, x, y, px, col, p, maxW = 1500) { // big on-screen term title (acronyms keep case)
    const t = upKeep(txt), z = G.fitFont(ctx, t, 'en', 900, px, maxW, 0.01);
    G.maskText(ctx, t, x, y, F.en(900, z), col, p, { align: 'center', ls: '4px' });
  }
  function b6down(ctx, x, y0, y1, col, w = 10, p = 1) { // single arrow pointing DOWN (losses go down)
    if (p <= 0) return; const y = lerp(y0, y1, clamp(p));
    ctx.save(); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = w; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y - w * 2); ctx.stroke();
    G.poly(ctx, [[x, y + w], [x - w * 2.6, y - w * 2.4], [x + w * 2.6, y - w * 2.4]], col); ctx.restore();
  }
  function b6upArrow(ctx, x, y0, y1, col, w = 10, p = 1) {
    if (p <= 0) return; const y = lerp(y0, y1, clamp(p));
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y + w * 2); ctx.stroke();
    G.poly(ctx, [[x, y - w], [x - w * 2.6, y + w * 2.4], [x + w * 2.6, y + w * 2.4]], col); ctx.restore();
  }
  function b6sea(ctx, y, amp, lt, col, ph = 0, k = 0.006, x0 = 0, x1 = W) {
    ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(x0, H);
    for (let x = x0; x <= x1; x += 16) ctx.lineTo(x, y + amp * Math.sin(x * k + lt * 2 + ph));
    ctx.lineTo(x1, H); ctx.closePath(); ctx.fill();
  }
  function b6boat(ctx, x, y, w, col, tilt = 0) { // y = waterline, hull below, sail above
    ctx.save(); ctx.translate(x, y); ctx.rotate(tilt);
    G.poly(ctx, [[-w / 2, -w * 0.06], [w / 2, -w * 0.06], [w * 0.34, w * 0.24], [-w * 0.34, w * 0.24]], col);
    ctx.fillStyle = col; ctx.fillRect(-4, -w * 0.62, 8, w * 0.58);
    G.poly(ctx, [[8, -w * 0.6], [w * 0.36, -w * 0.12], [8, -w * 0.12]], col); ctx.restore();
  }
  function b6rain(ctx, x0, x1, y0, y1, lt, col, n = 40, seed = 1) {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 5; ctx.lineCap = 'round';
    for (let i = 0; i < n; i++) {
      const x = lerp(x0, x1, b6rnd(i, seed)), y = y0 + b6fr(lt * 1.1 + b6rnd(i, seed + 3)) * (y1 - y0);
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 6, y + 34); ctx.stroke();
    }
    ctx.restore();
  }
  function b6canopy(ctx, x, y, r) { // umbrella canopy path (y = rim)
    ctx.beginPath(); ctx.moveTo(x - r, y); ctx.quadraticCurveTo(x - r, y - r * 0.95, x, y - r * 0.95); ctx.quadraticCurveTo(x + r, y - r * 0.95, x + r, y);
    for (let i = 0; i < 4; i++) { const a = x + r - i * r / 2, b = a - r / 2; ctx.quadraticCurveTo((a + b) / 2, y - r * 0.16, b, y); }
    ctx.closePath();
  }
  function b6umbrella(ctx, x, y, r, col, holes, bg) {
    ctx.fillStyle = col; b6canopy(ctx, x, y, r); ctx.fill();
    ctx.fillRect(x - 5, y - r * 0.95, 10, r * 0.95 + r * 0.55);
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 10; ctx.lineCap = 'round'; ctx.beginPath(); ctx.arc(x - 26, y + r * 0.55, 26, 0, Math.PI); ctx.stroke(); ctx.restore();
    holes.forEach(([hx, hy, hr]) => { if (hr > 0) G.disc(ctx, x + hx * r, y + hy * r, hr * r, bg); });
  }
  function b6shop(ctx, x, y, w, h, col, awn, win, sign) { // y = ground
    ctx.fillStyle = col; ctx.fillRect(x - w / 2, y - h, w, h);
    for (let i = 0; i < 6; i++) { const c = i % 2 ? G.CREAM : awn, a = x - w / 2 - 10 + i * (w + 20) / 6, b = a + (w + 20) / 6; G.poly(ctx, [[a, y - h * 0.62], [b, y - h * 0.62], [b, y - h * 0.5], [a, y - h * 0.5]], c); }
    ctx.fillStyle = win; ctx.fillRect(x - w * 0.36, y - h * 0.42, w * 0.42, h * 0.3); ctx.fillRect(x + w * 0.12, y - h * 0.42, w * 0.22, h * 0.42);
    if (sign) { ctx.fillStyle = sign; ctx.fillRect(x - w * 0.38, y - h * 0.92, w * 0.76, h * 0.2); }
  }
  function b6cart(ctx, x, y, s, col) { // y = wheels
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 8; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x - s * 0.7, y - s * 0.95); ctx.lineTo(x - s * 0.5, y - s * 0.95); ctx.lineTo(x - s * 0.3, y - s * 0.3); ctx.lineTo(x + s * 0.55, y - s * 0.3); ctx.lineTo(x + s * 0.7, y - s * 0.8); ctx.lineTo(x - s * 0.42, y - s * 0.8); ctx.stroke();
    for (let i = 1; i < 4; i++) { ctx.beginPath(); ctx.moveTo(x - s * 0.42 + i * s * 0.28, y - s * 0.8); ctx.lineTo(x - s * 0.36 + i * s * 0.25, y - s * 0.3); ctx.stroke(); }
    ctx.restore(); G.disc(ctx, x - s * 0.2, y - s * 0.08, s * 0.09, col); G.disc(ctx, x + s * 0.45, y - s * 0.08, s * 0.09, col);
  }
  function b6gear(ctx, x, y, r, teeth, rot, col, hole) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.fillStyle = col; ctx.beginPath();
    for (let i = 0; i < teeth * 2; i++) { const a = i / (teeth * 2) * Math.PI * 2, rr = i % 2 ? r : r * 1.22; ctx.lineTo(Math.cos(a - 0.12) * rr, Math.sin(a - 0.12) * rr); ctx.lineTo(Math.cos(a + 0.12) * rr, Math.sin(a + 0.12) * rr); }
    ctx.closePath(); ctx.fill(); G.disc(ctx, 0, 0, r * 0.35, hole); ctx.restore();
  }
  function b6car(ctx, x, y, w, col, win, wheel) { // side view, y = road
    ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(x - w / 2, y - w * 0.36, w, w * 0.24, w * 0.06); ctx.fill();
    G.poly(ctx, [[x - w * 0.28, y - w * 0.36], [x + w * 0.18, y - w * 0.36], [x + w * 0.06, y - w * 0.56], [x - w * 0.2, y - w * 0.56]], col);
    G.poly(ctx, [[x - w * 0.18, y - w * 0.4], [x + w * 0.1, y - w * 0.4], [x + w * 0.03, y - w * 0.52], [x - w * 0.14, y - w * 0.52]], win);
    G.disc(ctx, x - w * 0.3, y - w * 0.1, w * 0.1, wheel || G.INK); G.disc(ctx, x + w * 0.3, y - w * 0.1, w * 0.1, wheel || G.INK);
  }
  function b6doc(ctx, x, y, w, h, col, line, p = 1) { // paper with text lines, (x,y) = centre
    ctx.save(); ctx.translate(x, y); ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 14); ctx.fill();
    ctx.fillStyle = line; for (let i = 0; i < 6; i++) { const lw = (w - 90) * (i % 3 === 2 ? 0.6 : 0.92) * clamp(p * 6 - i); if (lw > 0) ctx.fillRect(-w / 2 + 45, -h / 2 + 70 + i * (h - 130) / 6, lw, 12); }
    ctx.restore();
  }
  function b6person(ctx, x, y, sc, col, o = {}) { figAt(ctx, x, y, sc, Object.assign({ torso: 0 }, o), col, o.far || (col[0] === '#' ? rgba(col, 0.6) : col)); }
  function b6spring(ctx, x0, y0, x1, y1, n, amp, w, col) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L;
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineJoin = 'round'; ctx.beginPath(); ctx.moveTo(x0, y0);
    for (let i = 1; i < n * 2; i++) { const f = i / (n * 2), sg = i % 2 ? 1 : -1; ctx.lineTo(x0 + dx * f + nx * amp * sg, y0 + dy * f + ny * amp * sg); }
    ctx.lineTo(x1, y1); ctx.stroke(); ctx.restore();
  }
  function b6key(ctx, x, y, s, col, rust) {
    ctx.save(); ctx.translate(x, y); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(-s * 0.55, 0, s * 0.32, 0, Math.PI * 2); ctx.fill();
    ctx.fillRect(-s * 0.3, -s * 0.07, s * 1.1, s * 0.14); ctx.fillRect(s * 0.55, 0, s * 0.1, s * 0.22); ctx.fillRect(s * 0.7, 0, s * 0.1, s * 0.16);
    G.disc(ctx, -s * 0.55, 0, s * 0.13, rust ? rgba(G.INK, 0.6) : rgba(G.INK, 0.35));
    if (rust) for (let i = 0; i < 9; i++) G.disc(ctx, -s * 0.7 + b6rnd(i, 4) * s * 1.5, (b6rnd(i, 5) - 0.5) * s * 0.4, s * (0.03 + 0.04 * b6rnd(i, 6)), '#5a3a1a');
    ctx.restore();
  }
  function b6crate(ctx, x, y, s, col, line) {
    ctx.fillStyle = col; ctx.fillRect(x - s / 2, y - s / 2, s, s); ctx.strokeStyle = line; ctx.lineWidth = 6; ctx.strokeRect(x - s / 2 + 8, y - s / 2 + 8, s - 16, s - 16);
    ctx.beginPath(); ctx.moveTo(x - s / 2 + 8, y - s / 2 + 8); ctx.lineTo(x + s / 2 - 8, y + s / 2 - 8); ctx.stroke();
  }
  function b6wheel(ctx, x, y, r, col, rot, hands, handCol) { // steering wheel + 1 or 2 hands
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.strokeStyle = col; ctx.lineWidth = r * 0.16; ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.stroke();
    ctx.lineWidth = r * 0.12; ctx.beginPath(); ctx.moveTo(-r, 0); ctx.lineTo(r, 0); ctx.moveTo(0, 0); ctx.lineTo(0, r); ctx.stroke(); G.disc(ctx, 0, 0, r * 0.22, col);
    const hp = hands === 2 ? [[-r, -r * 0.05], [r, -r * 0.05]] : [[r * 0.5, -r * 0.87]];
    hp.forEach(([hx, hy]) => { ctx.fillStyle = handCol; ctx.beginPath(); ctx.ellipse(hx, hy, r * 0.2, r * 0.27, 0, 0, Math.PI * 2); ctx.fill(); });
    ctx.restore();
  }
  function b6timeline(ctx, x0, x1, y, p, col) { ctx.fillStyle = col; ctx.fillRect(x0, y - 4, (x1 - x0) * clamp(p), 8); if (p > 0.98) G.poly(ctx, [[x1 + 34, y], [x1, y - 22], [x1, y + 22]], col); }
  function b6sign(ctx, x, y, col, fg, p) { // signature mark on a timeline
    if (p <= 0) return; G.disc(ctx, x, y, 26 * E.oBack(clamp(p)), col);
    ctx.save(); ctx.strokeStyle = fg; ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x - 12, y + 2); ctx.quadraticCurveTo(x - 4, y - 14, x + 2, y + 4); ctx.quadraticCurveTo(x + 8, y + 14, x + 14, y - 6); ctx.stroke(); ctx.restore();
  }
  function b6fader(ctx, x, y0, y1, v, col, knob, lab, C, p) { // vertical fader slot, v 0..1 (1 = top)
    ctx.fillStyle = rgba(col, 0.35); ctx.fillRect(x - 6, y0, 12, y1 - y0);
    const ky = lerp(y1, y0, v); ctx.fillStyle = knob; ctx.beginPath(); ctx.roundRect(x - 42, ky - 22, 84, 44, 10); ctx.fill();
    ctx.fillStyle = rgba(G.INK, 0.5); ctx.fillRect(x - 32, ky - 3, 64, 6);
    if (lab) tag(ctx, lab, x, y1 + 50, C, p, { px: 30, bg: knob, fg: G.INK });
  }
  function b6console(ctx, x0, y0, x1, y1, col, top) { ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(x0, y0, x1 - x0, y1 - y0, 28); ctx.fill(); ctx.fillStyle = top; ctx.fillRect(x0 + 30, y0 + 24, x1 - x0 - 60, 14); }
  function b6pit(ctx, x, w, d, y, col) { // a pit in the ground at y, drawn downward
    if (w <= 1) return; ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(x - w / 2, y); ctx.quadraticCurveTo(x, y + d * 2, x + w / 2, y); ctx.closePath(); ctx.fill();
  }
  function b6piggy(ctx, x, y, r, col, eye) {
    ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(x, y, r * 1.25, r, 0, 0, Math.PI * 2); ctx.fill();
    G.poly(ctx, [[x - r * 0.5, y - r * 0.85], [x - r * 0.25, y - r * 1.3], [x - r * 0.05, y - r * 0.9]], col);
    ctx.fillRect(x - r * 0.8, y + r * 0.6, r * 0.28, r * 0.55); ctx.fillRect(x + r * 0.5, y + r * 0.6, r * 0.28, r * 0.55);
    ctx.beginPath(); ctx.ellipse(x + r * 1.3, y, r * 0.22, r * 0.3, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = eye; ctx.fillRect(x - r * 0.25, y - r * 0.98, r * 0.5, r * 0.1); G.disc(ctx, x + r * 0.7, y - r * 0.3, r * 0.08, eye);
  }
  function b6gaugeArc(ctx, x, y, r, col, w) {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.beginPath(); ctx.arc(x, y, r, Math.PI, 0); ctx.stroke();
    for (let i = 0; i <= 10; i++) { const a = Math.PI + i / 10 * Math.PI; ctx.beginPath(); ctx.moveTo(x + Math.cos(a) * (r - 40), y + Math.sin(a) * (r - 40)); ctx.lineTo(x + Math.cos(a) * (r - 12), y + Math.sin(a) * (r - 12)); ctx.lineWidth = 6; ctx.stroke(); }
    ctx.restore();
  }
  function b6needle(ctx, x, y, len, a, w, col) { ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len); ctx.stroke(); ctx.restore(); }
  function b6cough(ctx, x, y, lt, col) { for (let i = 0; i < 3; i++) { const u = b6fr(lt * 1.4 + i / 3); ctx.save(); ctx.globalAlpha = (1 - u) * 0.8; G.disc(ctx, x + u * 70, y - u * 20 + i * 6, 8 + u * 16, col); ctx.restore(); } }
  function b6door(ctx, x, y, w, h, open, frame, panel, light) { // y = floor
    ctx.fillStyle = light; ctx.fillRect(x - w / 2, y - h, w, h);
    ctx.fillStyle = frame; ctx.fillRect(x - w / 2 - 22, y - h - 22, w + 44, 22); ctx.fillRect(x - w / 2 - 22, y - h, 22, h); ctx.fillRect(x + w / 2, y - h, 22, h);
    const pw = w * (1 - 0.72 * open); G.poly(ctx, [[x - w / 2, y - h], [x - w / 2 + pw, y - h + 40 * open], [x - w / 2 + pw, y - 40 * open], [x - w / 2, y]], panel);
    G.disc(ctx, x - w / 2 + pw - 22, y - h / 2, 10, frame);
  }
  function b6netBelow(ctx, x0, x1, y, sag, col, p) {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 5; ctx.globalAlpha = clamp(p);
    for (let j = 0; j < 4; j++) { ctx.beginPath(); ctx.moveTo(x0, y + j * 30); ctx.quadraticCurveTo((x0 + x1) / 2, y + j * 30 + sag, x1, y + j * 30); ctx.stroke(); }
    for (let i = 0; i <= 10; i++) { const x = lerp(x0, x1, i / 10), d = sag * (1 - Math.pow((i / 10) * 2 - 1, 2)) / 2; ctx.beginPath(); ctx.moveTo(x, y + d); ctx.lineTo(x, y + 90 + d); ctx.stroke(); }
    ctx.restore();
  }

  // ── #6 系统性风险 Systematic Risk ──
  VIZ.umbrella_holes = (ctx, s, lt, C) => { // 一张撑开的大伞，伞面破洞，雨照样漏下来
    const D = s.vizDur, x = 1180, y = 600, r = 400, hp = E.oBack(inv(0.3, D * 0.5, lt));
    const holes = [[-0.5, -0.32, 0.09 * hp], [0.12, -0.6, 0.075 * hp], [0.55, -0.22, 0.085 * hp]];
    b6rain(ctx, 560, 1800, 330, y - r * 0.6, lt, rgba(G.CREAM, 0.55), 46, 2);
    ctx.save(); ctx.beginPath(); ctx.rect(0, y, x - r, H); ctx.rect(x + r, y, W - x - r, H);
    holes.forEach(([hx, , hr]) => { if (hr > 0) ctx.rect(x + hx * r - hr * r, y, hr * r * 2, 400); }); ctx.clip();
    b6rain(ctx, 300, 1800, y - 40, 990, lt, rgba(G.CREAM, 0.75), 120, 7); ctx.restore();
    b6umbrella(ctx, x, y, r, PAL.red.t[2], holes, C.bg);
    b6person(ctx, x + 70, 980, 300, G.CREAM, { aR1: 150, aR2: 160, head: 8 });
    tag(ctx, '照样漏', 1560, 820, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.sea_title = (ctx, s, lt, C) => { // 屏幕标题「Systematic Risk」，下方一整片海面
    const D = s.vizDur, k = E.io(inv(0.1, D * 0.5, lt));
    b6title(ctx, 'Systematic Risk', W / 2, 560, 150, C.fg, inv(0.2, 0.9, lt));
    b6sea(ctx, lerp(1000, 760, k), 26, lt, PAL.purple.t[4], 0, 0.005);
    b6sea(ctx, lerp(1040, 820, k), 22, lt, PAL.purple.t[3], 1.6, 0.007);
    b6sea(ctx, lerp(1080, 890, k), 18, lt, PAL.purple.t[0], 3.1, 0.009);
    tag(ctx, '整片市场', W / 2, 680, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.CREAM, fg: PAL.purple.t[1] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.boats_sink = (ctx, s, lt, C) => { // 海面上一排小船，同一个浪打来，全部一起往下沉
    const D = s.vizDur, d = 210 * E.io3(inv(D * 0.3, D * 0.85, lt)), wy = 620;
    ctx.fillStyle = rgba(G.INK, 0.12); ctx.fillRect(160, wy - 6, 1600, 4);
    for (let i = 0; i < 6; i++) b6boat(ctx, 330 + i * 250, wy + d + 8 * Math.sin(lt * 2 + i), 150, G.INK, 0.05 * Math.sin(lt * 2.2 + i));
    ctx.save(); ctx.globalAlpha = 0.88; b6sea(ctx, wy + 10, 22 + 30 * inv(D * 0.2, D * 0.5, lt), lt, PAL.purple.t[2], 0, 0.004); ctx.restore();
    b6down(ctx, 1760, 640, 900, G.CREAM, 10, inv(D * 0.35, D * 0.7, lt));
    tag(ctx, '同一个浪', 1450, 400, C, inv(0.3, 0.9, lt), { px: 40, bg: PAL.purple.t[2], fg: G.CREAM });
    tag(ctx, '一起往下沉', 700, 940, C, inv(D * 0.6, D * 0.85, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.street_dim = (ctx, s, lt, C) => { // 商店街灯一盏盏暗下去，购物车空着
    const D = s.vizDur, gy = 900;
    ctx.fillStyle = rgba(G.INK, 0.25); ctx.fillRect(120, gy, 1680, 10);
    for (let i = 0; i < 5; i++) {
      const x = 300 + i * 290, lit = 1 - clamp(inv(D * (0.2 + i * 0.12), D * (0.3 + i * 0.12), lt));
      b6shop(ctx, x, gy, 230, 330, G.INK, PAL.red.t[3], mix(G.INK, '#ffe9a8', lit));
      ctx.fillStyle = G.INK; ctx.fillRect(x + 130, gy - 460, 8, 460);
      if (lit > 0.02) { ctx.save(); ctx.globalAlpha = 0.5 * lit; G.disc(ctx, x + 134, gy - 470, 70, '#fff3c4'); ctx.restore(); }
      G.disc(ctx, x + 134, gy - 470, 20, lit > 0.05 ? '#fff3c4' : rgba(G.INK, 0.7));
    }
    b6cart(ctx, 1640, 1000, 180, G.INK);
    tag(ctx, '空的', 1640, 770, C, inv(D * 0.6, D * 0.85, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.gears_dial = (ctx, s, lt, C) => { // 一个大旋钮被猛拧，旁边所有小齿轮跟着一起转
    const D = s.vizDur, tw = E.oBack(inv(D * 0.2, D * 0.45, lt), 2.2), a = lerp(-2.2, 0.9, tw), kx = 520, ky = 650;
    G.disc(ctx, kx, ky, 230, rgba(G.INK, 0.25)); G.disc(ctx, kx, ky, 190, G.CREAM);
    for (let i = 0; i < 12; i++) { ctx.fillStyle = G.CREAM; ctx.save(); ctx.translate(kx, ky); ctx.rotate(-2.6 + i / 11 * 4.2); ctx.fillRect(210, -4, 30, 8); ctx.restore(); }
    b6needle(ctx, kx, ky, 160, a, 22, PAL.red.t[2]); G.disc(ctx, kx, ky, 40, G.INK);
    tag(ctx, '利率', kx, ky + 290, C, inv(0.2, 0.7, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    const spin = tw * 5 + lt * 0.3;
    [[1000, 480, 80], [1230, 470, 64], [1450, 520, 90], [1660, 470, 60], [1080, 760, 70], [1330, 740, 96], [1600, 780, 76]].forEach(([x, y, r], i) =>
      b6gear(ctx, x, y, r, 9, spin * (i % 2 ? -1 : 1) * (100 / r), i % 3 ? G.INK : PAL.green.t[0], C.bg));
    tag(ctx, '借钱成本', 1330, 930, C, inv(D * 0.45, D * 0.75, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.lines_offset = (ctx, s, lt, C) => { // 几条线有上有下，交错着，总线大致平稳
    const D = s.vizDur, x0 = 200, x1 = 1720, yc = 640, rev = E.io(inv(0.1, D * 0.8, lt)), n = 80;
    ctx.save(); ctx.setLineDash([14, 12]); ctx.strokeStyle = rgba(G.INK, 0.3); ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x0, yc); ctx.lineTo(x1, yc); ctx.stroke(); ctx.restore();
    const cols = [PAL.red.t[2], PAL.purple.t[3], PAL.green.t[2], PAL.gold.t[1]];
    const f = (k, u) => 150 * Math.sin(u * 9 + k * Math.PI / 2) + 40 * Math.sin(u * 23 + k);
    for (let k = 0; k < 4; k++) { ctx.save(); ctx.strokeStyle = cols[k]; ctx.lineWidth = 8; ctx.lineJoin = 'round'; ctx.beginPath();
      for (let i = 0; i <= n * rev; i++) { const u = i / n, y = yc - f(k, u); i ? ctx.lineTo(lerp(x0, x1, u), y) : ctx.moveTo(x0, y); } ctx.stroke(); ctx.restore(); }
    ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 20; ctx.lineCap = 'round'; ctx.beginPath();
    for (let i = 0; i <= n * rev; i++) { const u = i / n; let v = 0; for (let k = 0; k < 4; k++) v += f(k, u); const y = yc - v / 4 * 0.6; i ? ctx.lineTo(lerp(x0, x1, u), y) : ctx.moveTo(x0, y); }
    ctx.stroke(); ctx.restore();
    tag(ctx, '合起来大致平稳', 1400, 900, C, inv(D * 0.6, D * 0.85, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.lines_bundle = (ctx, s, lt, C) => { // 几条线同时掉头往下，挤成一束
    const D = s.vizDur, x0 = 180, x1 = 1740, yc = 470, rev = E.io(inv(0.1, D * 0.8, lt)), n = 80, k0 = 0.5;
    ctx.fillStyle = rgba(G.CREAM, 0.3); ctx.fillRect(x0, yc - 2, x1 - x0, 4);
    for (let k = 0; k < 4; k++) { ctx.save(); ctx.strokeStyle = k ? rgba(G.CREAM, 0.55 + k * 0.12) : G.CREAM; ctx.lineWidth = 9; ctx.lineJoin = 'round'; ctx.beginPath();
      for (let i = 0; i <= n * rev; i++) { const u = i / n, pre = 70 * Math.sin(u * 10 + k * 1.6), dn = u < k0 ? 0 : E.io(clamp((u - k0) / 0.4)); const y = yc - pre * (1 - dn) + dn * (400 + k * 14); i ? ctx.lineTo(lerp(x0, x1, u), y) : ctx.moveTo(x0, y); }
      ctx.stroke(); ctx.restore(); }
    ctx.save(); ctx.globalAlpha = 0.25; ctx.fillStyle = G.INK; ctx.fillRect(lerp(x0, x1, k0), 340, 6, 620); ctx.restore();
    tag(ctx, '危机', lerp(x0, x1, k0), 370, C, inv(D * 0.3, D * 0.5, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    tag(ctx, '挤成一束', 1450, 940, C, inv(D * 0.7, D * 0.9, lt), { px: 36, bg: G.CREAM, fg: PAL.red.t[1] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.net_holes = (ctx, s, lt, C) => { // 一张安全网的网眼被撑大，接不住往下掉的东西
    const D = s.vizDur, st = E.io(inv(D * 0.2, D * 0.6, lt)), cy = 700, cx = W / 2;
    const gx = (i) => cx + (i - 6) * lerp(90, 90 + 70 * Math.exp(-Math.abs(i - 6) / 2), st);
    ctx.save(); ctx.strokeStyle = G.CREAM; ctx.lineWidth = 6;
    for (let i = 0; i <= 12; i++) { const x = gx(i); ctx.beginPath(); ctx.moveTo(x, cy - 110); ctx.quadraticCurveTo(x, cy + 30, x, cy + 110); ctx.stroke(); }
    for (let j = -2; j <= 2; j++) { ctx.beginPath(); for (let i = 0; i <= 12; i++) { const x = gx(i), y = cy + j * lerp(52, 60, st) + 30 * Math.cos((i - 6) / 6 * Math.PI / 2); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
    ctx.restore();
    for (let i = 0; i < 5; i++) { const u = clamp((lt - D * (0.35 + i * 0.1)) / 1.4); if (u <= 0) continue; b6crate(ctx, cx + (i - 2) * 140, lerp(360, 1040, E.i3(u)), 60, i % 2 ? GOLD : PAL.red.t[3], rgba(G.INK, 0.4)); }
    b6down(ctx, 1700, 420, 900, G.CREAM, 9, inv(D * 0.4, D * 0.7, lt));
    tag(ctx, '网眼撑大', 1480, 420, C, inv(D * 0.3, D * 0.6, lt), { px: 38, bg: G.CREAM, fg: PAL.purple.t[1] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.boats_split = (ctx, s, lt, C) => { // 左：一艘船漏水，其他船托住；右：大浪把所有船一起压下去
    const D = s.vizDur, d = 180 * E.io3(inv(D * 0.35, D * 0.85, lt)), wy = 640;
    ctx.fillStyle = rgba(G.INK, 0.35); ctx.fillRect(W / 2 - 3, 330, 6, 660);
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W / 2 - 3, H); ctx.clip();
    b6sea(ctx, wy + 20, 10, lt, rgba(G.INK, 0.25), 0, 0.01, 0, W / 2);
    [300, 520, 740].forEach((x, i) => b6boat(ctx, x, wy + (i === 1 ? 30 : 0), 150, i === 1 ? PAL.red.t[2] : G.INK, i === 1 ? 0.12 * Math.sin(lt * 2) : 0));
    ctx.strokeStyle = G.INK; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(360, wy - 10); ctx.lineTo(460, wy + 10); ctx.moveTo(580, wy + 10); ctx.lineTo(680, wy - 10); ctx.stroke();
    for (let i = 0; i < 3; i++) { const u = b6fr(lt + i / 3); G.disc(ctx, 520 + (i - 1) * 30, wy + 50 + u * 80, 8, rgba(PAL.purple.t[2], 1 - u)); }
    ctx.restore();
    ctx.save(); ctx.beginPath(); ctx.rect(W / 2 + 3, 0, W, H); ctx.clip();
    [1150, 1400, 1650].forEach((x, i) => b6boat(ctx, x, wy + d, 150, G.INK, 0.04 * Math.sin(lt * 2 + i)));
    ctx.globalAlpha = 0.85; b6sea(ctx, wy + 10, 20 + 40 * inv(D * 0.2, D * 0.5, lt), lt, PAL.purple.t[2], 0.5, 0.005, W / 2, W); ctx.restore();
    tag(ctx, '一家出事，托得住', 520, 900, C, inv(0.3, 0.9, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    tag(ctx, '一起跌，托不住', 1400, 940, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.umbrella_look = (ctx, s, lt, C) => { // 回到开头的破伞，伞下的人抬头看天 — umbrella left, sky + clouds right
    const D = s.vizDur, x = 600, y = 640, r = 300, look = E.io(inv(0.3, D * 0.5, lt));
    for (let i = 0; i < 3; i++) { const cx = 1200 + i * 220 + 20 * Math.sin(lt * 0.6 + i), cy = 430 + (i % 2) * 50; G.disc(ctx, cx, cy, 120, rgba(G.INK, 0.55)); G.disc(ctx, cx + 90, cy + 20, 90, rgba(G.INK, 0.55)); }
    b6rain(ctx, 1050, 1800, 520, 990, lt, rgba(G.INK, 0.45), 60, 9);
    b6umbrella(ctx, x, y, r, G.INK, [[-0.45, -0.35, 0.09], [0.15, -0.62, 0.075], [0.5, -0.2, 0.085]], C.bg);
    b6person(ctx, x + 40, 990, 340, G.CREAM, { head: -32 * look, torso: -8 * look, aR1: 150, aR2: 160 });
    G.maskText(ctx, '?', 1560, 820, F.en(900, 220), G.CREAM, inv(D * 0.4, D * 0.7, lt), { align: 'center' });
    tag(ctx, '一起跌时扛得住吗', 1400, 940, C, inv(D * 0.55, D * 0.85, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };

  // ── #7 非系统性风险 Unsystematic Risk ──
  VIZ.rock_split = (ctx, s, lt, C) => { // 一大块石头被敲成许多小碎块，散到很多篮子里
    const D = s.vizDur, br = E.io(inv(D * 0.25, D * 0.75, lt)), rx = W / 2, ry = 520;
    if (br < 0.05) G.poly(ctx, [[rx - 220, ry + 120], [rx - 260, ry - 30], [rx - 120, ry - 150], [rx + 90, ry - 160], [rx + 250, ry - 40], [rx + 220, ry + 120]], PAL.ochre.t[2]);
    else for (let i = 0; i < 15; i++) {
      const bx = 380 + (i % 5) * 290, sx = rx + (b6rnd(i, 1) - 0.5) * 380, sy = ry + (b6rnd(i, 2) - 0.5) * 220, z = 54;
      const x = lerp(sx, bx + (Math.floor(i / 5) - 1) * 40, br), y = lerp(sy, 830 - Math.floor(i / 5) * 26, br) - Math.sin(br * Math.PI) * 120;
      G.poly(ctx, [[x - z * 0.6, y + z * 0.4], [x - z * 0.5, y - z * 0.3], [x + z * 0.1, y - z * 0.5], [x + z * 0.6, y], [x + z * 0.3, y + z * 0.45]], PAL.ochre.t[2 + (i % 3)]);
    }
    if (lt < D * 0.3) { const hx = rx + 320, hy = 330 + 60 * Math.abs(Math.sin(lt * 6)); ctx.fillStyle = G.CREAM; ctx.fillRect(hx - 70, hy - 30, 140, 60); ctx.fillRect(hx - 8, hy, 16, 160); }
    for (let i = 0; i < 5; i++) basket(ctx, 380 + i * 290, 860, 200, 110, G.CREAM);
    tag(ctx, '散到很多篮子', 1500, 400, C, inv(D * 0.6, D * 0.85, lt), { px: 38, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.shop_street = (ctx, s, lt, C) => { // 屏幕标题「Unsystematic Risk」，下方一条街上的几家小店
    const gy = 980, awn = [PAL.red.t[2], PAL.gold.t[2], PAL.purple.t[3], PAL.ochre.t[2], PAL.red.t[4]];
    b6title(ctx, 'Unsystematic Risk', W / 2, 500, 140, C.fg, inv(0.2, 0.9, lt));
    ctx.fillStyle = rgba(G.INK, 0.3); ctx.fillRect(120, gy - 4, 1680, 8);
    for (let i = 0; i < 5; i++) { const p = pop(lt, 0.3 + i * 0.12, 0.8 + i * 0.12); if (p <= 0) continue; ctx.save(); ctx.translate(380 + i * 290, gy); ctx.scale(1, p); b6shop(ctx, 0, 0, 220, 300, G.CREAM, awn[i], '#fff3c4', rgba(G.INK, 0.8)); ctx.restore(); }
    vizCaption(ctx, s, lt, C);
  };
  VIZ.tea_sign = (ctx, s, lt, C) => { // 一家奶茶店招牌歪了，门口排队的人散开，其他店照常营业
    const D = s.vizDur, gy = 920, tilt = 0.32 * E.oBack(inv(D * 0.2, D * 0.45, lt), 2), sc = E.io(inv(D * 0.35, D * 0.85, lt));
    ctx.fillStyle = rgba(G.INK, 0.3); ctx.fillRect(120, gy - 4, 1680, 8);
    [360, 1240, 1600].forEach((x) => b6shop(ctx, x, gy, 260, 380, PAL.green.t[2], PAL.gold.t[2], '#fff3c4'));
    b6shop(ctx, 800, gy, 300, 420, PAL.purple.t[3], PAL.red.t[3], rgba(G.INK, 0.6));
    ctx.save(); ctx.translate(680, gy - 440); ctx.rotate(tilt); ctx.fillStyle = G.INK; ctx.fillRect(0, -36, 240, 72);
    G.poly(ctx, [[96, -24], [144, -24], [136, 26], [104, 26]], G.CREAM); ctx.fillStyle = G.CREAM; ctx.fillRect(116, -34, 6, 14); ctx.restore();
    for (let i = 0; i < 5; i++) { const dir = i % 2 ? 1 : -1, x = 800 + (i - 2) * 60 + dir * sc * (200 + i * 60); ctx.save(); ctx.globalAlpha = 1 - 0.6 * sc; b6person(ctx, x, gy + 60, 150, G.INK, { lL1: 20 * Math.sin(lt * 8 + i) * sc, lR1: -20 * Math.sin(lt * 8 + i) * sc }); ctx.restore(); }
    tag(ctx, '配方翻车', 800, 370, C, inv(D * 0.3, D * 0.55, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    tag(ctx, '照常营业', 1420, 400, C, inv(D * 0.55, D * 0.8, lt), { px: 34, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.shutter_down = (ctx, s, lt, C) => { // 那家店门口拉下卷帘门，旁边的店灯还亮着
    const D = s.vizDur, gy = 960, k = E.io(inv(D * 0.2, D * 0.7, lt));
    [[440, 1], [W / 2, 0], [1480, 1]].forEach(([x, lit]) => {
      ctx.fillStyle = rgba(G.CREAM, 0.15); ctx.fillRect(x - 230, gy - 560, 460, 560);
      ctx.fillStyle = lit ? '#fff3c4' : rgba(G.INK, 0.6); ctx.fillRect(x - 190, gy - 440, 380, 440);
      if (lit) { ctx.save(); ctx.globalAlpha = 0.25 + 0.05 * Math.sin(lt * 4 + x); G.disc(ctx, x, gy - 220, 260, '#fff3c4'); ctx.restore(); }
    });
    const sh = 440 * k; ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(W / 2 - 200, gy - 450, 400, sh);
    ctx.fillStyle = rgba(G.INK, 0.35); for (let y = gy - 450 + 22; y < gy - 450 + sh; y += 30) ctx.fillRect(W / 2 - 200, y, 400, 6);
    ctx.fillStyle = G.INK; ctx.fillRect(W / 2 - 220, gy - 470, 440, 26);
    tag(ctx, '只连累这一家', W / 2, 360, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.CREAM, fg: PAL.purple.t[1] });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.basket_break = (ctx, s, lt, C) => { // 一个人只提一个篮子，篮子破了，东西全掉到地上（往下落）
    const D = s.vizDur, gy = 990, bt = D * 0.35, x = 1000, by = 560;
    b6person(ctx, 760, gy, 520, G.CREAM, { aR1: 70, aR2: 60 });
    ctx.strokeStyle = G.CREAM; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(900, 520); ctx.lineTo(x, by); ctx.stroke();
    basket(ctx, x, by, 240, 150, G.CREAM, lt > bt ? 0.08 * Math.sin(lt * 9) * Math.exp(-(lt - bt)) : 0);
    if (lt > bt) G.poly(ctx, [[x - 60, by + 152], [x + 70, by + 152], [x + 40, by + 110], [x, by + 135], [x - 30, by + 105]], C.bg);
    for (let i = 0; i < 7; i++) { const u = clamp((lt - bt - i * 0.06) / 0.9), y0 = by + 70, y = u > 0 ? lerp(y0, gy - 26, E.i3(u)) : y0 - 40 + (i % 3) * 18; G.disc(ctx, x - 60 + (i % 4) * 40 + u * (i - 3) * 50, y, 26, [GOLD, PAL.green.t[3], G.CREAM][i % 3]); }
    ctx.fillStyle = rgba(G.CREAM, 0.4); ctx.fillRect(500, gy, 1100, 6);
    b6down(ctx, 1300, 620, 920, G.CREAM, 9, inv(bt, bt + 0.8, lt));
    tag(ctx, '全落你身上', 1450, 420, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.CREAM, fg: PAL.red.t[1] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ten_baskets = (ctx, s, lt, C) => { // 一个人提十个小篮子，其中一个漏了，只掉一点
    const D = s.vizDur, gy = 990, by = 600, lx = 400 + 7 * 124;
    b6person(ctx, W / 2, gy, 420, G.INK, { aL1: 100, aL2: 100, aR1: 100, aR2: 100 });
    ctx.fillStyle = G.INK; ctx.fillRect(360, by - 12, 1200, 16);
    for (let i = 0; i < 10; i++) { const x = 400 + i * 124; ctx.strokeStyle = G.INK; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x, by); ctx.lineTo(x, by + 50); ctx.stroke(); basket(ctx, x, by + 50, 90, 70, i === 7 ? PAL.red.t[2] : G.CREAM, 0.04 * Math.sin(lt * 2 + i)); }
    for (let i = 0; i < 2; i++) { const u = clamp((lt - D * 0.4 - i * 0.5) / 0.8); if (u > 0) G.disc(ctx, lx + i * 14, lerp(by + 130, gy - 14, E.i3(u)), 14, G.INK); }
    tag(ctx, '只掉一点', lx + 230, 900, C, inv(D * 0.55, D * 0.85, lt), { px: 36, bg: G.INK, fg: GOLD });
    G.typeText(ctx, '× 10', 1650, 520, F.en(900, 64), G.INK, inv(0.3, 0.8, lt), { caret: false, align: 'right' });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hooks_colors = (ctx, s, lt, C) => { // 十个篮子用不同颜色、挂在不同的钩子上，不是串在同一根绳上
    const D = s.vizDur, cols = [PAL.red.t[2], PAL.purple.t[3], PAL.green.t[2], GOLD, G.CREAM, PAL.red.t[4], PAL.purple.t[1], PAL.green.t[4], G.INK, PAL.ochre.t[0]];
    ctx.fillStyle = rgba(G.INK, 0.35); ctx.fillRect(170, 400, 470, 6);
    ctx.strokeStyle = G.INK; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(200, 420); for (let i = 0; i < 4; i++) ctx.lineTo(260 + i * 110, 560); ctx.stroke();
    for (let i = 0; i < 4; i++) basket(ctx, 260 + i * 110, 560, 80, 60, rgba(G.INK, 0.6));
    crossOut(ctx, 405, 590, 120, inv(D * 0.4, D * 0.65, lt));
    tag(ctx, '同一根绳', 405, 760, C, inv(D * 0.4, D * 0.65, lt), { px: 30, bg: G.INK, fg: G.CREAM });
    ctx.fillStyle = G.INK; ctx.fillRect(760, 400, 1000, 14);
    for (let i = 0; i < 10; i++) { const x = 800 + (i % 5) * 230, y = 470 + Math.floor(i / 5) * 260, p = pop(lt, 0.2 + i * 0.08, 0.6 + i * 0.08); if (p <= 0) continue;
      ctx.strokeStyle = G.INK; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(x, 410); ctx.lineTo(x, y - 20); ctx.stroke(); ctx.beginPath(); ctx.arc(x, y - 6, 14, -Math.PI / 2, Math.PI * 0.8); ctx.stroke();
      basket(ctx, x, y + 10, 120 * p, 80 * p, cols[i], 0.05 * Math.sin(lt * 1.6 + i * 1.3)); }
    tag(ctx, '各挂各的钩', 1260, 940, C, inv(D * 0.55, D * 0.85, lt), { px: 34, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.wind_baskets = (ctx, s, lt, C) => { // 一阵大风把十个篮子同时吹得往下晃
    const D = s.vizDur, gust = E.io(inv(D * 0.25, D * 0.6, lt)), cols = [PAL.red.t[2], PAL.purple.t[3], PAL.green.t[2], GOLD, G.CREAM];
    for (let i = 0; i < 9; i++) { const u = b6fr(lt * 0.9 + i / 9); ctx.save(); ctx.globalAlpha = gust * (1 - u) * 0.6; ctx.fillStyle = G.CREAM; ctx.fillRect(lerp(120, 1700, u), 380 + i * 60, 220, 6); ctx.restore(); }
    ctx.fillStyle = G.CREAM; ctx.fillRect(220, 360, 1480, 12);
    for (let i = 0; i < 10; i++) { const x = 290 + i * 150, L = 120 + 140 * gust, a = 0.5 * gust + 0.06 * Math.sin(lt * 7 + i) * gust, bx = x + Math.sin(a) * L, by = 370 + Math.cos(a) * L;
      ctx.strokeStyle = G.CREAM; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x, 372); ctx.lineTo(bx, by); ctx.stroke(); basket(ctx, bx, by, 100, 70, cols[i % 5], a * 0.6); }
    b6down(ctx, 1780, 450, 880, G.CREAM, 9, inv(D * 0.35, D * 0.7, lt));
    tag(ctx, '大盘一起跌', 960, 920, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { x: 1700, y: 250, align: 'right' });
  };
  VIZ.pits_fill = (ctx, s, lt, C) => { // 回到碎石块：一块大坑被填平成许多浅浅的小坑 — cross-section, pits go down
    const D = s.vizDur, gy = 560, k = E.io(inv(D * 0.2, D * 0.75, lt));
    ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(140, gy, 1640, 400);
    b6pit(ctx, 960, lerp(700, 120, k), lerp(170, 30, k), gy, C.bg);
    for (let i = 0; i < 10; i++) { if (i === 4) continue; b6pit(ctx, 260 + i * 155, 110 * k, 26 * k, gy, C.bg); }
    for (let i = 0; i < 10; i++) { const x = 260 + i * 155, z = 34; if (k > 0.02) G.poly(ctx, [[x - z, gy - 4], [x - z * 0.5, gy - z], [x + z * 0.6, gy - z * 0.8], [x + z, gy - 4]], rgba(G.INK, 0.6 * k)); }
    tag(ctx, '一家的坑', 960, 880, C, inv(0.2, 0.7, lt) * (1 - k), { px: 38, bg: G.INK, fg: G.CREAM });
    tag(ctx, '摊成许多浅坑', 960, 760, C, inv(D * 0.6, D * 0.85, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };

  // ── #8 套利定价理论 APT ──
  const APT_F = [['大盘', G.CREAM], ['通胀', PAL.red.t[3]], ['利率', PAL.purple.t[4]], ['增长', PAL.green.t[3]]];
  VIZ.dial_needles = (ctx, s, lt, C) => { // 一个仪表盘上只有一根指针「大盘」，旁边又亮起几根新指针
    const D = s.vizDur, x = 1100, y = 920, r = 480, angs = [-1.9, -1.35, -0.95, -0.5];
    b6gaugeArc(ctx, x, y, r, rgba(G.CREAM, 0.5), 10);
    APT_F.forEach(([lab, col], i) => { const p = i ? E.oBack(inv(D * (0.3 + i * 0.12), D * (0.45 + i * 0.12), lt)) : 1; if (p <= 0) return;
      const a = angs[i] + 0.04 * Math.sin(lt * 2 + i); b6needle(ctx, x, y, (r - 60) * p, a, i ? 12 : 22, col);
      tag(ctx, lab, x + Math.cos(a) * (r + 40), y + Math.sin(a) * (r + 40), C, p, { px: 34, bg: col, fg: G.INK }); });
    G.disc(ctx, x, y, 40, G.CREAM);
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mixer_title = (ctx, s, lt, C) => { // 屏幕标题「APT」，下方一块多旋钮的调音台
    b6title(ctx, 'APT', W / 2, 560, 240, C.fg, inv(0.2, 0.8, lt));
    b6console(ctx, 360, 660, 1560, 960, G.INK, PAL.purple.t[3]);
    for (let r = 0; r < 2; r++) for (let i = 0; i < 8; i++) { const x = 470 + i * 140, y = 750 + r * 120, q = r * 8 + i, p = pop(lt, 0.4 + q * 0.04, 0.8 + q * 0.04); if (p <= 0) continue;
      G.disc(ctx, x, y, 40 * p, G.CREAM); b6needle(ctx, x, y, 34 * p, -1.6 + Math.sin(i * 1.7 + r + lt * 0.8) * 1.1, 8, G.INK); }
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mixer_one = (ctx, s, lt, C) => { // 一个调音台只有一个推子「大盘」
    const D = s.vizDur, y0 = 420, y1 = 860;
    b6console(ctx, 420, 360, 1500, 1000, G.INK, GOLD);
    for (let i = 1; i < 5; i++) { const x = 560 + i * 200; ctx.save(); ctx.setLineDash([10, 10]); ctx.strokeStyle = rgba(G.CREAM, 0.25); ctx.lineWidth = 3; ctx.strokeRect(x - 40, y0, 80, y1 - y0); ctx.restore(); }
    b6fader(ctx, 560, y0, y1, 0.5 + 0.3 * Math.sin(lt * 1.3), G.CREAM, GOLD, '大盘', C, inv(0.3, 0.8, lt));
    tag(ctx, '只有一个', 1640, 520, C, inv(D * 0.45, D * 0.75, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.mixer_faders = (ctx, s, lt, C) => { // 调音台上多出几个推子，标「通胀」「利率」「增长」
    const D = s.vizDur, y0 = 420, y1 = 820;
    b6console(ctx, 300, 360, 1620, 960, G.INK, PAL.green.t[4]);
    APT_F.forEach(([lab, col], i) => { const p = i ? pop(lt, D * (0.2 + i * 0.12), D * (0.35 + i * 0.12)) : 1; if (p <= 0) return;
      ctx.save(); ctx.globalAlpha = clamp(p); b6fader(ctx, 520 + i * 300, y0, y1, 0.5 + 0.35 * Math.sin(lt * (1 + i * 0.4) + i * 1.3), G.CREAM, col, lab, C, p); ctx.restore(); });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.receipt_jar = (ctx, s, lt, C) => { // 购物小票越拉越长，一个存钱罐的分量往下掉
    const D = s.vizDur, L = lerp(80, 480, E.io(inv(0.2, D * 0.8, lt))), w = E.io(inv(D * 0.2, D * 0.85, lt));
    ctx.fillStyle = G.INK; ctx.fillRect(300, 360, 360, 70);
    ctx.fillStyle = G.CREAM; ctx.fillRect(350, 430, 260, L);
    ctx.fillStyle = rgba(G.INK, 0.5); for (let y = 460; y < 430 + L - 20; y += 40) { ctx.fillRect(375, y, 140, 8); ctx.fillRect(545, y, 40, 8); }
    for (let i = 0; i < 8; i++) G.poly(ctx, [[350 + i * 32.5, 430 + L], [366 + i * 32.5, 444 + L], [382 + i * 32.5, 430 + L]], G.CREAM);
    b6piggy(ctx, 1150, 560 + 200 * w, 150, PAL.red.t[4], G.INK);
    ctx.fillStyle = rgba(G.INK, 0.25); ctx.fillRect(1520, 380, 70, 560); ctx.fillStyle = G.INK; const hh = 560 * (1 - 0.6 * w); ctx.fillRect(1520, 940 - hh, 70, hh);
    b6down(ctx, 1680, 420, 860, G.INK, 9, inv(D * 0.3, D * 0.7, lt));
    tag(ctx, '物价涨得快', 480, 960, C, inv(0.3, 0.9, lt), { px: 34, bg: G.INK, fg: G.CREAM });
    tag(ctx, '分量往下掉', 1150, 400, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.rope_strain = (ctx, s, lt, C) => { // 一根借款绳越绷越紧，绳上挂的箱子往下坠
    const D = s.vizDur, k = E.io(inv(D * 0.2, D * 0.8, lt)), ax = 760, ay = 360, cy = lerp(560, 840, k);
    ctx.fillStyle = G.CREAM; ctx.fillRect(560, ay - 30, 400, 30);
    ctx.save(); ctx.strokeStyle = mix(G.CREAM, G.INK, k * 0.6); ctx.lineWidth = lerp(16, 6, k); ctx.beginPath(); ctx.moveTo(ax, ay);
    for (let i = 1; i <= 12; i++) ctx.lineTo(ax + Math.sin(i * 2.4) * 10 * (1 - k), lerp(ay, cy - 110, i / 12)); ctx.stroke(); ctx.restore();
    ctx.save(); ctx.translate(ax, cy); ctx.rotate(0.03 * Math.sin(lt * 9) * k); b6crate(ctx, 0, 0, 220, PAL.ochre.t[2], rgba(G.INK, 0.5)); ctx.restore();
    b6down(ctx, 1000, 560, 900, G.CREAM, 9, inv(D * 0.3, D * 0.7, lt));
    tag(ctx, '借钱变贵', 1300, 420, C, inv(0.2, 0.8, lt), { px: 40, bg: G.CREAM, fg: PAL.red.t[1] });
    tag(ctx, '压力大', 1300, 760, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.cars_road = (ctx, s, lt, C) => { // 几辆小车在同一条路上，路速变化时有的快有的慢
    const D = s.vizDur, ys = [600, 760, 920], sp = [1.0, 0.55, 0.25];
    ctx.fillStyle = rgba(G.INK, 0.85); ctx.fillRect(100, 470, 1720, 500);
    ctx.fillStyle = GOLD; for (let j = 0; j < 2; j++) for (let x = 120 - (lt * 160) % 120; x < 1800; x += 120) if (x > 100) ctx.fillRect(x, 676 + j * 160, 60, 8);
    const prog = (k) => 260 + lt * 160 * sp[k] + (lt > D * 0.4 ? (lt - D * 0.4) * 280 * (sp[k] - 0.5) : 0);
    ys.forEach((y, k) => b6car(ctx, clamp(prog(k), 240, 1660), y, 200, [PAL.red.t[2], G.CREAM, PAL.green.t[3]][k], rgba(G.INK, 0.6), G.INK));
    tag(ctx, lt > D * 0.4 ? '经济放慢' : '经济增长', 1500, 400, C, inv(0.2, 0.7, lt), { px: 36, bg: G.INK, fg: GOLD });
    tag(ctx, '各家反应不同', 600, 400, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.springs = (ctx, s, lt, C) => { // 一个组合连着几根弹簧，每根弹簧粗细不同
    const D = s.vizDur, cx = W / 2 + 40 * Math.sin(lt * 2.2) * inv(D * 0.4, D * 0.6, lt), cy = 680 + 20 * Math.sin(lt * 3.1);
    const A = [[300, 680, '通胀', 6, PAL.red.t[3]], [W / 2, 380, '利率', 14, PAL.gold.t[2]], [1620, 680, '增长', 24, PAL.green.t[3]]];
    A.forEach(([x, y, lab, w, col], i) => { const p = E.io(inv(0.2 + i * 0.2, 0.8 + i * 0.2, lt));
      b6spring(ctx, x, y, lerp(x, cx, p), lerp(y, cy, p), 9, 26, w, col); G.disc(ctx, x, y, 22, G.CREAM);
      tag(ctx, lab, x + (i === 1 ? 160 : 0), y + (i === 1 ? 0 : 110), C, p, { px: 34, bg: col, fg: G.INK }); });
    ctx.fillStyle = G.CREAM; ctx.beginPath(); ctx.roundRect(cx - 120, cy - 80, 240, 160, 22); ctx.fill();
    ctx.fillStyle = G.INK; ctx.font = F.zh(900, 44); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('组合', cx, cy + 2);
    tag(ctx, '粗细不同', W / 2, 930, C, inv(D * 0.6, D * 0.85, lt), { px: 36, bg: G.CREAM, fg: PAL.purple.t[1] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.faders_sum = (ctx, s, lt, C) => { // 几根推子的读数汇成一个总数，标「该要的回报（假设）」 — blocks stack, no formula
    const D = s.vizDur, hs = [90, 120, 70, 100], cols = [rgba(G.INK, 0.8), PAL.red.t[3], PAL.purple.t[4], PAL.green.t[3]], yb = 880;
    ctx.fillStyle = rgba(G.INK, 0.3); ctx.fillRect(200, yb, 1520, 6);
    let acc = 0;
    hs.forEach((h, i) => { const x0 = 330 + i * 190, f = E.io3(inv(D * (0.2 + i * 0.12), D * (0.4 + i * 0.12), lt)), tx = 1380;
      const x = lerp(x0, tx, f), y = lerp(yb - h, yb - acc - h, f) - Math.sin(f * Math.PI) * 120; ctx.fillStyle = cols[i]; ctx.fillRect(x - 70, y, 140, h);
      if (f < 0.1) tag(ctx, APT_F[i][0], x0, yb + 50, C, inv(0.2, 0.6, lt), { px: 28, bg: G.INK, fg: G.CREAM }); acc += h; });
    ctx.save(); ctx.strokeStyle = rgba(G.INK, 0.5); ctx.lineWidth = 4; ctx.setLineDash([12, 10]); ctx.strokeRect(1300, yb - acc - 10, 160, acc + 10); ctx.restore();
    tag(ctx, '该要的回报（假设）', 1380, yb - acc - 70, C, inv(D * 0.7, D * 0.9, lt), { px: 34, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.apple_stalls = (ctx, s, lt, C) => { // 同样一个苹果，两个摊位标价不同，有人在中间搬运
    const D = s.vizDur, gy = 960, u = 0.5 - 0.5 * Math.cos(lt * 1.6);
    [[360, '¥3'], [1560, '¥5']].forEach(([x, pr], i) => { ctx.fillStyle = G.CREAM; ctx.fillRect(x - 200, gy - 260, 400, 260);
      for (let k = 0; k < 6; k++) { ctx.fillStyle = k % 2 ? G.CREAM : PAL.red.t[2]; ctx.fillRect(x - 220 + k * 73, gy - 360, 73, 70); }
      G.disc(ctx, x, gy - 160, 60, PAL.red.t[2]); ctx.fillStyle = PAL.green.t[0]; ctx.fillRect(x - 4, gy - 240, 8, 30);
      tag(ctx, pr, x, gy - 450, C, inv(0.2 + i * 0.3, 0.7 + i * 0.3, lt), { px: 52, bg: G.INK, fg: G.CREAM, font: F.en(900, 52) }); });
    const px = lerp(660, 1260, u); b6person(ctx, px, gy, 300, G.INK, { aR1: 100, aR2: 110, aL1: 90, aL2: 100, lL1: 18 * Math.sin(lt * 9), lR1: -18 * Math.sin(lt * 9) });
    b6crate(ctx, px + 70, gy - 210, 90, PAL.ochre.t[2], rgba(G.INK, 0.5)); G.disc(ctx, px + 70, gy - 270, 22, PAL.red.t[2]);
    tag(ctx, '赚差价', W / 2, 400, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.tags_converge = (ctx, s, lt, C) => { // 两个摊位的价签慢慢靠拢到同一个数
    const D = s.vizDur, k = E.io(inv(D * 0.2, D * 0.8, lt)), y = 640;
    const lx = lerp(420, 760, k), rx = lerp(1500, 1160, k), lv = lerp(3, 4, k), rv = lerp(5, 4, k);
    [[lx, lv, G.CREAM], [rx, rv, GOLD]].forEach(([x, v, col]) => { ctx.save(); ctx.translate(x, y); ctx.rotate(-0.06); G.poly(ctx, [[-170, -110], [140, -110], [210, 0], [140, 110], [-170, 110]], col); G.disc(ctx, 140, 0, 18, C.bg);
      ctx.fillStyle = G.INK; ctx.font = F.en(900, 100); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('¥' + v.toFixed(1), -20, 6); ctx.restore(); });
    ctx.save(); ctx.strokeStyle = rgba(G.CREAM, 0.5); ctx.lineWidth = 6; ctx.setLineDash([16, 12]); ctx.beginPath(); ctx.moveTo(W / 2, 420); ctx.lineTo(W / 2, 860); ctx.stroke(); ctx.restore();
    tag(ctx, '拉回来', W / 2, 920, C, inv(D * 0.6, D * 0.85, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mover_slip = (ctx, s, lt, C) => { // 搬运的人脚下一滑，箱子往下掉
    const D = s.vizDur, t0 = D * 0.3, sl = E.io(inv(t0, t0 + 0.5, lt)), fl = E.i3(clamp((lt - t0 - 0.2) / 0.9)), gy = 700;
    ctx.fillStyle = G.CREAM; ctx.fillRect(160, gy, 1600, 10);
    ctx.fillStyle = rgba(G.CREAM, 0.35); ctx.beginPath(); ctx.ellipse(900, gy + 6, 140, 18, 0, 0, Math.PI * 2); ctx.fill();
    b6person(ctx, 860 + 60 * sl, gy, 320, G.CREAM, { rot: -40 * sl, torso: -10 * sl, aR1: lerp(100, 160, sl), aL1: lerp(90, 170, sl), lR1: lerp(0, 70, sl), lL1: lerp(0, -30, sl) });
    const cx = lerp(990, 1150, fl), cy = lerp(gy - 260, 910, fl); ctx.save(); ctx.translate(cx, cy); ctx.rotate(fl * 1.4); b6crate(ctx, 0, 0, 120, PAL.ochre.t[3], rgba(G.INK, 0.5)); ctx.restore();
    b6down(ctx, 1400, 560, 940, G.CREAM, 9, inv(t0 + 0.2, t0 + 1.1, lt));
    tag(ctx, '套利也可能亏', 1450, 420, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.CREAM, fg: PAL.red.t[1] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ruler_fog = (ctx, s, lt, C) => { // 一把尺子放在调音台上，旁边一团雾
    const D = s.vizDur;
    b6console(ctx, 220, 640, 1000, 940, G.INK, GOLD);
    for (let i = 0; i < 4; i++) b6fader(ctx, 330 + i * 190, 700, 900, 0.4 + 0.1 * i, G.CREAM, APT_F[i][1], null, C, 0);
    ctx.save(); ctx.translate(610, 610); ctx.rotate(-0.08); ctx.fillStyle = G.CREAM; ctx.fillRect(-380, -60, 760, 70); ctx.fillStyle = G.INK; for (let i = 0; i <= 30; i++) ctx.fillRect(-370 + i * 24.5, -60, 4, i % 5 ? 20 : 36); ctx.restore();
    for (let i = 0; i < 9; i++) { ctx.save(); ctx.globalAlpha = 0.25 + 0.15 * Math.sin(lt + i); G.disc(ctx, 1380 + Math.sin(lt * 0.5 + i * 1.7) * 140, 620 + Math.cos(lt * 0.4 + i * 2.3) * 140, 150 + (i % 3) * 40, G.CREAM); ctx.restore(); }
    G.maskText(ctx, '?', 1380, 700, F.en(900, 200), rgba(G.INK, 0.5), inv(D * 0.3, D * 0.6, lt), { align: 'center' });
    tag(ctx, '不是预测', 1380, 940, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.dial_all = (ctx, s, lt, C) => { // 回到仪表盘，几根指针一起亮着 — smaller gauge left + legend right
    const D = s.vizDur, x = 640, y = 900, r = 380, p = E.io(inv(0.2, D * 0.5, lt)), angs = [-2.3, -1.7, -1.15, -0.6];
    b6gaugeArc(ctx, x, y, r, rgba(G.INK, 0.4), 10);
    APT_F.forEach(([lab, col], i) => { const a = angs[i] + 0.05 * Math.sin(lt * 2 + i); b6needle(ctx, x, y, (r - 50) * p, a, 16, i ? col : G.INK);
      const ly = 440 + i * 120, lp = inv(D * (0.2 + i * 0.1), D * (0.4 + i * 0.1), lt); G.disc(ctx, 1240, ly, 28 * clamp(lp * 2), i ? col : G.INK);
      G.maskText(ctx, lab, 1300, ly + 20, F.zh(900, 60), G.INK, lp); });
    G.disc(ctx, x, y, 34, G.INK);
    tag(ctx, '怕哪几样', 1500, 940, C, inv(D * 0.6, D * 0.85, lt), { px: 38, bg: G.INK, fg: GOLD });
    vizCaption(ctx, s, lt, C);
  };

  // ── #9 道德风险 Moral Hazard ──
  VIZ.net_step = (ctx, s, lt, C) => { // 一个人站在高处，身后多了一张大网，他往前迈了一步
    const D = s.vizDur, py = 560, np = E.o3(inv(D * 0.15, D * 0.45, lt)), st = E.io(inv(D * 0.5, D * 0.8, lt));
    ctx.fillStyle = G.CREAM; ctx.fillRect(200, py, 720, 24); ctx.fillStyle = rgba(G.CREAM, 0.25); ctx.fillRect(260, py + 24, 40, 420); ctx.fillRect(820, py + 24, 40, 420);
    b6netBelow(ctx, 900, 1700, 820, 90, GOLD, np);
    b6person(ctx, 760 + 110 * st, py, 330, G.CREAM, { lR1: 40 * Math.sin(st * Math.PI), lR2: 10, torso: 6 * st, aR1: 20, aL1: -20 });
    tag(ctx, '有人兜底', 1300, 760, C, np, { px: 38, bg: GOLD, fg: G.INK });
    tag(ctx, '往前一步', 1000, 380, C, inv(D * 0.65, D * 0.9, lt), { px: 36, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.policy_title = (ctx, s, lt, C) => { // 屏幕标题「Moral Hazard」，下方一张保单
    const D = s.vizDur, p = E.o3(inv(D * 0.2, D * 0.6, lt));
    b6title(ctx, 'Moral Hazard', W / 2, 500, 150, C.fg, inv(0.2, 0.9, lt));
    ctx.save(); ctx.translate(W / 2, lerp(1200, 790, p)); ctx.rotate(-0.04); b6doc(ctx, 0, 0, 560, 300, G.CREAM, rgba(G.INK, 0.35), inv(D * 0.4, D * 0.8, lt));
    ctx.font = F.zh(900, 44); ctx.fillStyle = G.INK; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText('保单', -235, -100); G.disc(ctx, 190, 80, 54, rgba(PAL.red.t[2], 0.85)); ctx.restore();
    vizCaption(ctx, s, lt, C);
  };
  VIZ.car_lane = (ctx, s, lt, C) => { // 一辆小车贴着车道线开，司机单手扶方向盘，角标「假设」 — top-down road + inset wheel
    const D = s.vizDur, drift = 50 * Math.sin(lt * 1.4) + 60 * inv(0.3, D * 0.5, lt);
    ctx.fillStyle = G.INK; ctx.fillRect(150, 470, 1150, 400);
    ctx.fillStyle = G.CREAM; for (let x = 150 - (lt * 300) % 160; x < 1300; x += 160) if (x > 150) ctx.fillRect(x, 666, 80, 10);
    ctx.save(); ctx.translate(700, 580 + drift); ctx.rotate(0.05 * Math.cos(lt * 1.4)); ctx.fillStyle = PAL.red.t[2]; ctx.beginPath(); ctx.roundRect(-130, -55, 260, 110, 30); ctx.fill(); ctx.fillStyle = rgba(G.INK, 0.6); ctx.fillRect(10, -42, 60, 84); ctx.restore();
    G.disc(ctx, 1530, 680, 210, rgba(G.INK, 0.08));
    b6wheel(ctx, 1530, 680, 150, G.INK, 0.15 * Math.sin(lt * 1.4), 1, PAL.ochre.t[3]);
    tag(ctx, '假设', 1650, 400, C, inv(0.2, 0.6, lt), { px: 32, bg: G.INK, fg: G.CREAM });
    tag(ctx, '单手', 1530, 940, C, inv(D * 0.45, D * 0.75, lt), { px: 34, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.care_bar = (ctx, s, lt, C) => { // 司机身边的「小心」进度条一点点往下降
    const D = s.vizDur, k = E.io(inv(D * 0.15, D * 0.85, lt)), v = Math.round(lerp(100, 30, k));
    b6person(ctx, 600, 990, 560, G.CREAM, { aR1: 70, aR2: 80, aL1: 60, aL2: 70, torso: 4 });
    b6wheel(ctx, 840, 700, 90, G.INK, 0, 1, G.CREAM);
    const x = 1240, y0 = 360, y1 = 940; ctx.fillStyle = rgba(G.INK, 0.25); ctx.beginPath(); ctx.roundRect(x - 70, y0, 140, y1 - y0, 20); ctx.fill();
    const top = lerp(y0, y1, 1 - v / 100); ctx.fillStyle = G.CREAM; ctx.beginPath(); ctx.roundRect(x - 60, top + 10, 120, Math.max(0, y1 - top - 20), 14); ctx.fill();
    b6down(ctx, x + 150, 420, lerp(440, 880, k), G.INK, 8, inv(D * 0.2, D * 0.4, lt));
    G.maskText(ctx, '小心', x + 260, 520, F.zh(900, 64), G.INK, inv(0.2, 0.6, lt));
    G.maskText(ctx, v + '%', x + 260, 640, F.en(900, 80), G.CREAM, inv(0.3, 0.7, lt));
    vizCaption(ctx, s, lt, C);
  };
  VIZ.airbag_tower = (ctx, s, lt, C) => { // 一座无名小楼下面垫着一个大气垫，楼越盖越歪
    const D = s.vizDur, n = 1 + Math.floor(7 * E.io(inv(0.2, D * 0.85, lt))), cx = 1100, gy = 860;
    ctx.fillStyle = PAL.gold.t[3]; ctx.beginPath(); ctx.roundRect(cx - 420, gy, 840, 120, 60); ctx.fill();
    ctx.fillStyle = rgba(G.INK, 0.25); for (let i = 1; i < 5; i++) ctx.fillRect(cx - 420 + i * 168, gy + 20, 6, 80);
    let y = gy; for (let i = 0; i < n; i++) { const w = 300 - i * 14, h = 64, lean = i * 18 + 4 * Math.sin(lt * 2) * i / 4; ctx.fillStyle = G.CREAM; ctx.fillRect(cx + lean - w / 2, y - h, w, h - 6);
      ctx.fillStyle = PAL.purple.t[1]; for (let k = 0; k < 3; k++) ctx.fillRect(cx + lean - w / 2 + 30 + k * (w - 60) / 3, y - h + 14, (w - 60) / 3 - 20, 28); y -= h; }
    tag(ctx, '出事有人救', 500, 600, C, inv(0.3, 0.8, lt), { px: 38, bg: PAL.gold.t[3], fg: G.INK });
    tag(ctx, '越盖越歪', 500, 760, C, inv(D * 0.55, D * 0.85, lt), { px: 36, bg: G.CREAM, fg: PAL.purple.t[1] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.coins_bricks = (ctx, s, lt, C) => { // 一个人抱走金币，另一群人在下面接住掉下来的砖
    const D = s.vizDur, gy = 980, w = E.io(inv(D * 0.2, D * 0.8, lt)), ax = lerp(640, 330, w);
    b6person(ctx, ax, gy, 380, G.CREAM, { aR1: 80, aR2: 120, aL1: 70, aL2: 110, lL1: 20 * Math.sin(lt * 7), lR1: -20 * Math.sin(lt * 7) });
    for (let i = 0; i < 5; i++) { ctx.fillStyle = GOLD; ctx.beginPath(); ctx.ellipse(ax + 120, gy - 230 - i * 22, 52, 14, 0, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillStyle = rgba(G.CREAM, 0.4); ctx.fillRect(W / 2, 360, 6, 620);
    [1150, 1350, 1550].forEach((x) => b6person(ctx, x, gy, 300, G.INK, { aR1: 170, aR2: 175, aL1: 165, aL2: 170, head: -10 }));
    for (let i = 0; i < 6; i++) { const u = b6fr(lt * 0.5 + i / 6), x = 1150 + (i % 3) * 200, y = lerp(340, 640, E.i3(u)); ctx.fillStyle = PAL.ochre.t[2]; ctx.fillRect(x - 50, y - 24, 100, 48); ctx.strokeStyle = rgba(G.INK, 0.4); ctx.lineWidth = 4; ctx.strokeRect(x - 50, y - 24, 100, 48); }
    tag(ctx, '好处自己拿', 480, 440, C, inv(0.3, 0.8, lt), { px: 36, bg: GOLD, fg: G.INK });
    tag(ctx, '坏处别人扛', 1350, 700, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: G.CREAM, fg: PAL.red.t[1] });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.deductible = (ctx, s, lt, C) => { // 保单上一格写「自己先出一部分」，司机重新双手握方向盘
    const D = s.vizDur, hi = inv(D * 0.2, D * 0.45, lt), g = E.io(inv(D * 0.5, D * 0.8, lt));
    ctx.save(); ctx.translate(620, 650); ctx.rotate(-0.05); b6doc(ctx, 0, 0, 640, 520, G.CREAM, rgba(G.INK, 0.25), 1);
    ctx.fillStyle = rgba(PAL.red.t[2], 0.9 * clamp(hi * 2)); ctx.fillRect(-270, 80, 540, 110);
    G.maskText(ctx, '自己先出一部分', 0, 155, F.zh(900, 52), G.CREAM, hi, { align: 'center' }); ctx.restore();
    b6wheel(ctx, 1400, 650, 200, G.INK, 0.12 * Math.sin(lt * 1.4) * (1 - g), g > 0.5 ? 2 : 1, G.CREAM);
    tag(ctx, '双手握好', 1400, 940, C, inv(D * 0.6, D * 0.85, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.timeline_after = (ctx, s, lt, C) => { // 一条时间线：先签字，之后才出现行为变化的标记
    const D = s.vizDur, y = 660, x0 = 220, x1 = 1640, xs = lerp(x0, x1, 0.38), xb = lerp(x0, x1, 0.74), bp = inv(D * 0.55, D * 0.75, lt);
    b6timeline(ctx, x0, x1, y, E.io(inv(0.1, D * 0.4, lt)), rgba(G.CREAM, 0.8));
    if (bp > 0) { ctx.save(); ctx.globalAlpha = 0.25 * bp; ctx.fillStyle = PAL.red.t[2]; ctx.fillRect(xs + 30, y - 120, x1 - xs - 30, 240); ctx.restore(); G.disc(ctx, xb, y, 30 * E.oBack(bp), PAL.red.t[2]); }
    b6sign(ctx, xs, y, GOLD, G.INK, inv(D * 0.3, D * 0.45, lt));
    tag(ctx, '签字', xs, y + 100, C, inv(D * 0.3, D * 0.5, lt), { px: 36, bg: GOLD, fg: G.INK });
    tag(ctx, '行为变了', xb, y - 110, C, bp, { px: 36, bg: PAL.red.t[2], fg: G.CREAM });
    tag(ctx, '之后', lerp(xs, x1, 0.5), y + 180, C, inv(D * 0.65, D * 0.9, lt), { px: 34, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.footprints_edge = (ctx, s, lt, C) => { // 回到开头：网在身后，人的脚印越走越靠边 — top-down platform
    const D = s.vizDur, k = inv(0.2, D * 0.85, lt), n = Math.floor(14 * k);
    ctx.fillStyle = rgba(G.INK, 0.12); ctx.fillRect(200, 360, 1100, 620);
    ctx.fillStyle = G.INK; ctx.fillRect(1296, 360, 10, 620);
    ctx.save(); ctx.strokeStyle = GOLD; ctx.lineWidth = 4; for (let i = 0; i < 8; i++) { ctx.beginPath(); ctx.moveTo(1330 + i * 60, 360); ctx.lineTo(1330 + i * 60, 980); ctx.stroke(); } for (let j = 0; j < 11; j++) { ctx.beginPath(); ctx.moveTo(1330, 380 + j * 60); ctx.lineTo(1760, 380 + j * 60); ctx.stroke(); } ctx.restore();
    for (let i = 0; i < n; i++) { const f = i / 13, x = lerp(420, 1250, f * f), y = lerp(920, 420, f) + (i % 2 ? -24 : 24); ctx.fillStyle = rgba(G.INK, 0.4 + 0.6 * f); ctx.beginPath(); ctx.ellipse(x, y, 20, 32, -0.9 + 0.5 * f, 0, Math.PI * 2); ctx.fill(); }
    tag(ctx, '越走越靠边', 760, 930, C, inv(D * 0.55, D * 0.85, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    tag(ctx, '网', 1545, 420, C, inv(0.2, 0.6, lt), { px: 34, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };

  // ── #10 逆向选择 Adverse Selection ──
  VIZ.door_queue = (ctx, s, lt, C) => { // 一扇门口排队，最前面的人最着急
    const D = s.vizDur, gy = 980;
    b6door(ctx, 1560, gy, 230, 520, 0.2, G.CREAM, rgba(G.CREAM, 0.7), rgba(GOLD, 0.6));
    for (let i = 0; i < 6; i++) { const x = 1340 - i * 190, front = i === 0, j = front ? 10 * Math.sin(lt * 18) : 0, p = pop(lt, 0.1 + i * 0.08, 0.5 + i * 0.08); if (p <= 0) continue;
      b6person(ctx, x + j, gy, front ? 315 : 285, front ? G.CREAM : rgba(G.CREAM, 0.55), front ? { torso: 22, aR1: 110, aR2: 130, aL1: 60 } : {}); }
    G.maskText(ctx, '!!', 1360, 600, F.en(900, 110), GOLD, inv(D * 0.3, D * 0.5, lt), { align: 'center' });
    tag(ctx, '最着急', 1340, 400, C, inv(D * 0.45, D * 0.75, lt), { px: 38, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.door_title = (ctx, s, lt, C) => { // 屏幕标题「Adverse Selection」，下方一扇半开的门
    const D = s.vizDur;
    b6title(ctx, 'Adverse Selection', W / 2, 470, 140, C.fg, inv(0.2, 0.9, lt));
    b6door(ctx, W / 2, 990, 260, 400, 0.5 * E.io(inv(D * 0.3, D * 0.7, lt)), G.INK, rgba(G.INK, 0.75), G.CREAM);
    ctx.save(); ctx.globalAlpha = 0.35 * inv(D * 0.4, D * 0.8, lt); G.poly(ctx, [[W / 2 - 130, 990], [W / 2 + 130, 990], [W / 2 + 330, 1030], [W / 2 - 330, 1030]], G.CREAM); ctx.restore();
    vizCaption(ctx, s, lt, C);
  };
  VIZ.counter_cough = (ctx, s, lt, C) => { // 保险柜台前，咳嗽的人挤在最前面，角标「假设」
    const D = s.vizDur, gy = 980;
    ctx.fillStyle = G.INK; ctx.fillRect(1380, 720, 380, 260); ctx.fillStyle = PAL.green.t[2]; ctx.fillRect(1380, 700, 380, 30);
    ctx.fillStyle = G.INK; ctx.fillRect(1440, 440, 260, 90); G.maskText(ctx, '保险', 1570, 485, F.zh(900, 56), G.CREAM, inv(0.1, 0.5, lt), { align: 'center' });
    for (let i = 0; i < 5; i++) { const x = 1220 - i * 200 + (i < 2 ? 8 * Math.sin(lt * 10 + i) : 0), sick = i < 3, p = pop(lt, 0.1 + i * 0.08, 0.5 + i * 0.08); if (p <= 0) continue;
      b6person(ctx, x, gy, 300, sick ? G.INK : PAL.green.t[2], sick ? { torso: 18, head: 14, aR1: 40, aR2: 110 } : {}); if (sick) b6cough(ctx, x + 50, gy - 250, lt + i * 0.3, rgba(G.INK, 0.4)); }
    tag(ctx, '假设', 1330, 485, C, inv(0.2, 0.6, lt), { px: 32, bg: G.INK, fg: G.CREAM });
    tag(ctx, '身体差的挤在最前', 700, 420, C, inv(D * 0.45, D * 0.75, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.price_jump = (ctx, s, lt, C) => { // 柜台上的价签往上跳
    const D = s.vizDur, steps = Math.min(3, Math.floor(4 * inv(D * 0.15, D * 0.8, lt))), v = [100, 120, 140, 160][steps], hop = Math.abs(Math.sin(lt * 5)) * 30 * (steps < 3 ? 1 : 0);
    ctx.fillStyle = rgba(G.INK, 0.85); ctx.fillRect(300, 820, 1320, 160); ctx.fillStyle = G.CREAM; ctx.fillRect(300, 800, 1320, 24);
    ctx.save(); ctx.translate(W / 2 - 60, 640 - steps * 70 - hop); ctx.rotate(-0.05); G.poly(ctx, [[-260, -120], [200, -120], [290, 0], [200, 120], [-260, 120]], G.CREAM); G.disc(ctx, 200, 0, 20, C.bg);
    ctx.fillStyle = G.INK; ctx.font = F.en(900, 140); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('¥' + v, -40, 8); ctx.restore();
    b6upArrow(ctx, 1500, 760, 380, G.CREAM, 10, inv(D * 0.2, D * 0.6, lt));
    tag(ctx, '分不清，只好涨价', 600, 900, C, inv(D * 0.5, D * 0.8, lt), { px: 34, bg: G.CREAM, fg: PAL.red.t[1] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.queue_leave = (ctx, s, lt, C) => { // 队伍里健康的人摇头离开，队伍变短
    const D = s.vizDur, gy = 980, k = E.io(inv(D * 0.25, D * 0.8, lt)), q = [1, 0, 1, 0, 0, 1];
    ctx.fillStyle = G.INK; ctx.fillRect(1560, 640, 220, 340);
    let pos = 0;
    q.forEach((sick, i) => { const x0 = 1440 - i * 180;
      if (sick) { b6person(ctx, lerp(x0, 1440 - pos * 180, k), gy, 280, G.INK, { torso: 16, head: 12 }); pos++; }
      else { ctx.save(); ctx.globalAlpha = 1 - 0.5 * k; b6person(ctx, x0 - k * (500 + i * 80), gy, 280, G.CREAM, { head: 14 * Math.sin(lt * 9) * k, lL1: 20 * Math.sin(lt * 7) * k, lR1: -20 * Math.sin(lt * 7) * k }); ctx.restore(); } });
    tag(ctx, '不划算，走了', 520, 480, C, inv(D * 0.4, D * 0.7, lt), { px: 36, bg: G.CREAM, fg: G.INK });
    tag(ctx, '队伍变短', 1300, 440, C, inv(D * 0.6, D * 0.85, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.two_keys = (ctx, s, lt, C) => { // 卖家手里拿着两把钥匙，一把亮、一把锈
    const D = s.vizDur, p = E.oBack(inv(0.2, D * 0.5, lt));
    b6person(ctx, 620, 990, 560, G.CREAM, { aR1: 100, aR2: 120, aL1: 80, aL2: 110 });
    if (p > 0) { ctx.save(); ctx.translate(1180, 560); ctx.rotate(-0.15 + 0.03 * Math.sin(lt * 2)); ctx.scale(p, p); b6key(ctx, 0, 0, 260, GOLD, false); ctx.restore();
      ctx.save(); ctx.translate(1240, 820); ctx.rotate(0.12); ctx.scale(p, p); b6key(ctx, 0, 0, 260, '#8a5a2b', true); ctx.restore(); }
    for (let i = 0; i < 4; i++) { const r = 20 + 12 * Math.sin(lt * 4 + i); ctx.save(); ctx.globalAlpha = 0.8 * clamp(p); ctx.fillStyle = G.CREAM; ctx.translate(1060 + i * 110, 430 + (i % 2) * 40); ctx.rotate(lt * 2 + i * 1.6); ctx.fillRect(-r, -3, r * 2, 6); ctx.fillRect(-3, -r, 6, r * 2); ctx.restore(); }
    tag(ctx, '好车', 1600, 520, C, inv(D * 0.4, D * 0.6, lt), { px: 34, bg: GOLD, fg: G.INK });
    tag(ctx, '坏车', 1620, 820, C, inv(D * 0.5, D * 0.7, lt), { px: 34, bg: '#8a5a2b', fg: G.CREAM });
    tag(ctx, '卖家心里有数', 640, 370, C, inv(D * 0.6, D * 0.85, lt), { px: 34, bg: G.CREAM, fg: PAL.purple.t[1] });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.magnifier_mid = (ctx, s, lt, C) => { // 买家拿放大镜也看不清，报价牌停在中间
    const D = s.vizDur, gy = 900, m = E.io(inv(D * 0.3, D * 0.8, lt)), mx = 760 + 90 * Math.sin(lt * 1.5), my = 700 + 30 * Math.cos(lt * 1.9);
    ctx.save(); ctx.filter = 'blur(10px)'; b6car(ctx, 780, gy, 460, G.INK, rgba(G.CREAM, 0.4)); ctx.restore();
    ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 20; ctx.beginPath(); ctx.arc(mx, my, 110, 0, Math.PI * 2); ctx.stroke(); ctx.lineWidth = 30; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(mx + 80, my + 80); ctx.lineTo(mx + 190, my + 190); ctx.stroke(); ctx.restore();
    G.maskText(ctx, '?', mx, my + 50, F.en(900, 140), rgba(G.INK, 0.7), inv(0.3, 0.7, lt), { align: 'center' });
    const bx0 = 1220, bx1 = 1720, by = 560; ctx.fillStyle = G.INK; ctx.fillRect(bx0, by - 6, bx1 - bx0, 12);
    ctx.font = F.zh(900, 32); ctx.fillStyle = G.INK; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('低', bx0, by + 50); ctx.fillText('高', bx1, by + 50);
    const px = lerp(bx0 + 40, (bx0 + bx1) / 2, m) + (1 - m) * 160 * Math.sin(lt * 3); G.poly(ctx, [[px, by - 14], [px - 28, by - 64], [px + 28, by - 64]], PAL.red.t[2]);
    tag(ctx, '中间价', (bx0 + bx1) / 2, by + 150, C, inv(D * 0.65, D * 0.9, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.cars_leave = (ctx, s, lt, C) => { // 亮车开出市场，场里剩下的锈车越来越多
    const D = s.vizDur, k = inv(D * 0.15, D * 0.85, lt), rusty = 2 + Math.floor(6 * k);
    ctx.save(); ctx.strokeStyle = rgba(G.CREAM, 0.5); ctx.lineWidth = 6; ctx.setLineDash([20, 14]); ctx.strokeRect(180, 380, 1180, 580); ctx.restore();
    ctx.fillStyle = C.bg; ctx.fillRect(1350, 440, 20, 160);
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, 1830, H); ctx.clip();
    for (let i = 0; i < 4; i++) { const u = clamp((k - i / 4) * 2.4), x = u > 0 ? lerp(420 + i * 230, 2000, E.i3(u)) : 420 + i * 230; b6car(ctx, x, 580, 200, GOLD, rgba(G.INK, 0.5), G.INK); }
    ctx.restore();
    for (let i = 0; i < rusty; i++) { const x = 330 + (i % 4) * 260, y = 760 + Math.floor(i / 4) * 160; b6car(ctx, x, y, 200, '#8a5a2b', rgba(G.INK, 0.6), G.INK); for (let j = 0; j < 4; j++) G.disc(ctx, x - 60 + b6rnd(i * 4 + j, 2) * 120, y - 50 - b6rnd(i * 4 + j, 3) * 20, 7, '#5a3a1a'); }
    tag(ctx, '好车开走', 1600, 400, C, inv(D * 0.3, D * 0.6, lt), { px: 36, bg: GOLD, fg: G.INK });
    tag(ctx, '剩下锈车', 1600, 880, C, inv(D * 0.6, D * 0.85, lt), { px: 36, bg: '#8a5a2b', fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.table_light = (ctx, s, lt, C) => { // 桌子一边灯很亮，另一边一片暗
    const D = s.vizDur, k = E.io(inv(0.2, D * 0.5, lt));
    ctx.save(); ctx.globalAlpha = 0.85 * k; G.poly(ctx, [[560, 340], [640, 340], [900, 820], [300, 820]], '#fff3c4'); ctx.restore();
    ctx.fillStyle = G.CREAM; ctx.fillRect(560, 320, 80, 30);
    ctx.fillStyle = rgba(G.INK, 0.7 * k); ctx.fillRect(W / 2, 330, 860, 650);
    ctx.fillStyle = PAL.ochre.t[2]; ctx.fillRect(300, 820, 1320, 40); ctx.fillRect(340, 860, 30, 120); ctx.fillRect(1550, 860, 30, 120);
    b6person(ctx, 420, 990, 360, G.CREAM, { aR1: 80, aR2: 90 }); b6doc(ctx, 700, 760, 200, 120, G.CREAM, rgba(G.INK, 0.4), 1);
    ctx.save(); ctx.translate(1500, 0); ctx.scale(-1, 1); b6person(ctx, 0, 990, 360, G.INK, { aR1: 30, aR2: 20, head: 10 }); ctx.restore();
    G.maskText(ctx, '?', 1500, 560, F.en(900, 140), rgba(G.CREAM, 0.6), inv(D * 0.4, D * 0.7, lt), { align: 'center' });
    tag(ctx, '知道得多', 620, 420, C, inv(D * 0.3, D * 0.6, lt), { px: 34, bg: G.INK, fg: '#fff3c4' });
    tag(ctx, '蒙在鼓里', 1300, 420, C, inv(D * 0.5, D * 0.8, lt), { px: 34, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.timeline_before = (ctx, s, lt, C) => { // 一条时间线：签字之前的位置亮起标记，签字之后那段是灰的 — vertical, top = earlier
    const D = s.vizDur, x = 760, y0 = 360, y1 = 960, ys = lerp(y0, y1, 0.55), ym = lerp(y0, y1, 0.25), p = E.io(inv(0.1, D * 0.4, lt)), mp = inv(D * 0.45, D * 0.7, lt);
    ctx.fillStyle = G.INK; ctx.fillRect(x - 5, y0, 10, (ys - y0) * clamp(p * 1.8));
    if (p > 0.5) { ctx.fillStyle = rgba(G.INK, 0.25); ctx.fillRect(x - 5, ys, 10, (y1 - ys) * clamp(p * 2 - 1)); }
    b6sign(ctx, x, ys, G.INK, GOLD, inv(D * 0.25, D * 0.4, lt));
    tag(ctx, '签字', x + 160, ys, C, inv(D * 0.25, D * 0.45, lt), { px: 34, bg: G.INK, fg: GOLD });
    if (mp > 0) { ctx.save(); ctx.globalAlpha = 0.25 * mp; G.disc(ctx, x, ym, 120, G.CREAM); ctx.restore(); G.disc(ctx, x, ym, 32 * E.oBack(mp), PAL.red.t[2]); }
    tag(ctx, '签约之前', x + 230, ym, C, mp, { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    ctx.save(); ctx.globalAlpha = 0.45; tag(ctx, '之后', x + 160, lerp(ys, y1, 0.6), C, inv(D * 0.6, D * 0.85, lt), { px: 30, bg: G.INK, fg: G.CREAM }); ctx.restore();
    G.maskText(ctx, '逆向选择', 1450, 620, F.zh(900, 72), G.INK, inv(D * 0.55, D * 0.8, lt), { align: 'center' });
    G.maskText(ctx, '道德风险在之后', 1450, 720, F.zh(700, 40), rgba(G.INK, 0.55), inv(D * 0.65, D * 0.9, lt), { align: 'center' });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.queue_front = (ctx, s, lt, C) => { // 回到开头的门口队伍，镜头停在最前面那个人身上 — zoomed, spotlight
    const D = s.vizDur, z = E.io(inv(0.1, D * 0.6, lt)), fx = lerp(1300, 1350, z);
    for (let i = 1; i < 5; i++) { ctx.save(); ctx.globalAlpha = 0.35 * (1 - z * 0.6); b6person(ctx, lerp(1100 - i * 200, 1500 - i * 260, z), 990, lerp(300, 380, z), G.INK); ctx.restore(); }
    ctx.save(); ctx.globalAlpha = 0.35 * z; G.disc(ctx, fx, 640, 360, '#fff3c4'); ctx.restore();
    b6person(ctx, fx, 1000, lerp(300, 620, z), G.CREAM, { torso: 20, aR1: 110, aR2: 130, aL1: 60 });
    tag(ctx, '谁最想来？', 620, 560, C, inv(D * 0.5, D * 0.8, lt), { px: 48, bg: G.CREAM, fg: PAL.red.t[1] });
    vizCaption(ctx, s, lt, C);
  };

  // ───────── finance-v003 scene library, batch 7 (governance cases + distributions, 2026-10-30) ─────────
  // #11 三道防线 · #12 巴林银行 · #13 长期资本管理公司 · #14 正态分布 · #15 肥尾 — 57 scenes, one per line.
  // 金融专家 rules: losses drawn DOWNWARD / loss tail to the LEFT, no rising-only curves, no tickers or chart candles,
  // Barings: no gambling props, the earthquake only as a map with seismic rings (no people hurt), 「88888」 on screen.
  Object.assign(VPAL, {
    gates_three: 'ink', gates_title: 'purple', gate_worker: 'cream', gate_tower: 'green', gate_audit: 'ochre', gate_locks: 'red',
    desk_split: 'cream', desk_merge: 'red', gates_catch: 'ink', oldbank_gate: 'gold',
    bank_crack: 'ink', bank_plate: 'purple', desk_leeson: 'cream', nikkei_board: 'ochre', ledger_drawer: 'green', drawer_88888: 'red',
    two_hands: 'purple', empty_chair: 'cream', quake_map: 'ink', snowball_down: 'red', pounds_sink: 'ochre', capital_floor: 'cream',
    coin_keys: 'gold', gates_dark: 'ink',
    gauge_car: 'cream', ltcm_title: 'purple', medal_manual: 'ochre', gap_lines: 'ink', lever_rock: 'green', coins_25: 'gold',
    iou_torn: 'cream', gap_widen: 'red', rock_drop: 'ink', ring_14: 'purple', hand_catch: 'ochre', manual_wave: 'green', car_stuck: 'red',
    balls_pile: 'ink', normal_title: 'purple', bell_outline: 'cream', bell_peak: 'green', bell_tails: 'ochre', calc_bell: 'gold',
    calc_tick: 'cream', dots_outliers: 'red', tail_shadow: 'ink',
    calendar_circled: 'cream', fat_title: 'gold', thin_bell: 'green', balls_ends: 'ink', tails_overlay: 'purple', left_tail_drag: 'red',
    threshold_q: 'ochre', tail_zoom: 'cream', wall_push: 'purple', calc_crack: 'gold', calendar_two: 'ink',
  });
  const b7N = (u) => Math.exp(-u * u / 2);            // thin-tailed bell (peak 1)
  const b7T = (u) => Math.pow(1 + u * u / 3, -2);      // fat-tailed bell (peak 1)
  function b7curve(ctx, x0, x1, yb, h, f, p, col, w, fill, U = 3.6, from = 'left') { // bell-shaped curve over [x0,x1], baseline yb
    const n = 120, pts = [];
    for (let i = 0; i <= n; i++) { const u = -U + 2 * U * i / n; pts.push([lerp(x0, x1, i / n), yb - h * f(u)]); }
    let a = 0, b = n; const q = clamp(p);
    if (from === 'left') b = Math.round(n * q); else { a = Math.round(n / 2 * (1 - q)); b = n - a; }
    if (b - a < 1) return pts;
    if (fill) { ctx.fillStyle = fill; ctx.beginPath(); ctx.moveTo(pts[a][0], yb); for (let i = a; i <= b; i++) ctx.lineTo(pts[i][0], pts[i][1]); ctx.lineTo(pts[b][0], yb); ctx.closePath(); ctx.fill(); }
    if (col) { ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.beginPath(); for (let i = a; i <= b; i++) (i === a ? ctx.moveTo : ctx.lineTo).call(ctx, pts[i][0], pts[i][1]); ctx.stroke(); ctx.restore(); }
    return pts;
  }
  function b7area(ctx, x0, x1, yb, h, f, xa, xb, col, U = 3.6) { // fill under curve between xa..xb
    const n = 80; ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(xa, yb);
    for (let i = 0; i <= n; i++) { const x = lerp(xa, xb, i / n), u = -U + 2 * U * (x - x0) / (x1 - x0); ctx.lineTo(x, yb - h * f(u)); }
    ctx.lineTo(xb, yb); ctx.closePath(); ctx.fill();
  }
  function b7gate(ctx, x, y, h, col, open, lamp, on) { // turnstile gate, y = floor; open 0 shut … 1 bar raised
    ctx.fillStyle = col; ctx.fillRect(x - 110, y - h, 30, h); ctx.fillRect(x + 80, y - h, 30, h);
    ctx.save(); ctx.translate(x - 80, y - h * 0.55); ctx.rotate(-1.35 * clamp(open)); ctx.fillStyle = col; ctx.fillRect(0, -12, 170, 24); ctx.restore();
    if (lamp) { G.disc(ctx, x + 95, y - h - 26, 24, on > 0 ? lamp : rgba(G.INK, 0.45)); if (on > 0) { ctx.save(); ctx.globalAlpha = 0.25 * clamp(on); G.disc(ctx, x + 95, y - h - 26, 60, lamp); ctx.restore(); } }
  }
  function b7bank(ctx, x, y, w, h, col, win) { // generic old stone building with columns (no name, no logo), y = ground
    G.poly(ctx, [[x - w / 2 - 30, y - h], [x + w / 2 + 30, y - h], [x, y - h - h * 0.28]], col);
    ctx.fillStyle = col; ctx.fillRect(x - w / 2 - 30, y - h, w + 60, h * 0.08); ctx.fillRect(x - w / 2 - 40, y - h * 0.07, w + 80, h * 0.07);
    const n = 6; for (let i = 0; i < n; i++) { const cx = lerp(x - w / 2 + 20, x + w / 2 - 20, i / (n - 1)); ctx.fillStyle = col; ctx.fillRect(cx - w * 0.035, y - h * 0.92, w * 0.07, h * 0.85); }
    if (win) { ctx.fillStyle = win; for (let i = 0; i < n - 1; i++) { const cx = lerp(x - w / 2 + 20, x + w / 2 - 20, (i + 0.5) / (n - 1)); ctx.fillRect(cx - w * 0.04, y - h * 0.7, w * 0.08, h * 0.22); } }
  }
  function b7calc(ctx, x, y, w, h, col, scr, key) { // calculator, (x,y) = centre; returns screen centre
    ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(x - w / 2, y - h / 2, w, h, 30); ctx.fill();
    ctx.fillStyle = scr; ctx.fillRect(x - w / 2 + 34, y - h / 2 + 34, w - 68, h * 0.28);
    for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) { ctx.fillStyle = key; ctx.beginPath(); ctx.roundRect(x - w / 2 + 40 + c * (w - 80) / 4, y - h / 2 + h * 0.4 + r * h * 0.14, (w - 80) / 4 - 16, h * 0.1, 10); ctx.fill(); }
    return [x, y - h / 2 + 34 + h * 0.14];
  }
  function b7cal(ctx, x0, y0, cols, rows, cell, col, line, head) { // calendar sheet
    ctx.fillStyle = col; ctx.fillRect(x0, y0, cols * cell, rows * cell + 70); ctx.fillStyle = head; ctx.fillRect(x0, y0, cols * cell, 70);
    ctx.save(); ctx.strokeStyle = line; ctx.lineWidth = 3;
    for (let i = 0; i <= cols; i++) { ctx.beginPath(); ctx.moveTo(x0 + i * cell, y0 + 70); ctx.lineTo(x0 + i * cell, y0 + 70 + rows * cell); ctx.stroke(); }
    for (let j = 0; j <= rows; j++) { ctx.beginPath(); ctx.moveTo(x0, y0 + 70 + j * cell); ctx.lineTo(x0 + cols * cell, y0 + 70 + j * cell); ctx.stroke(); }
    ctx.restore(); [0.25, 0.75].forEach((f) => G.disc(ctx, x0 + cols * cell * f, y0 + 4, 14, line));
  }
  function b7rings(ctx, x, y, r, col, w, p, tilt = -0.2) { if (p <= 0) return; ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.beginPath(); ctx.ellipse(x, y, r * 1.15, r * 0.85, tilt, 0, Math.PI * 2 * clamp(p)); ctx.stroke(); ctx.restore(); }
  function b7hand(ctx, x, y, s, col, rot = 0) { // open palm, fingers up, (x,y) = palm centre
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.fillStyle = col;
    ctx.beginPath(); ctx.ellipse(0, 0, s * 0.55, s * 0.38, 0, 0, Math.PI * 2); ctx.fill();
    for (let i = 0; i < 4; i++) { ctx.beginPath(); ctx.roundRect(-s * 0.5 + i * s * 0.27, -s * 0.95, s * 0.2, s * 0.7, s * 0.1); ctx.fill(); }
    ctx.beginPath(); ctx.roundRect(s * 0.4, -s * 0.3, s * 0.55, s * 0.2, s * 0.1); ctx.fill();
    ctx.fillRect(-s * 0.4, s * 0.2, s * 0.8, s * 0.8); ctx.restore();
  }
  function b7chair(ctx, x, y, s, col) { ctx.fillStyle = col; ctx.fillRect(x - s * 0.4, y - s * 0.5, s * 0.8, s * 0.1); ctx.fillRect(x + s * 0.3, y - s * 1.2, s * 0.1, s * 1.2); ctx.fillRect(x - s * 0.4, y - s * 0.5, s * 0.08, s * 0.5); ctx.fillRect(x + s * 0.3, y - s * 0.5, s * 0.08, s * 0.5); }
  function b7tower(ctx, x, y, w, h, col, win) { // plain office tower, no logo, y = ground
    ctx.fillStyle = col; ctx.fillRect(x - w / 2, y - h, w, h); ctx.fillStyle = win;
    for (let r = 0; r < Math.floor((h - 30) / 70); r++) for (let c = 0; c < 4; c++) ctx.fillRect(x - w / 2 + 22 + c * (w - 30) / 4, y - h + 26 + r * 70, (w - 30) / 4 - 18, 34);
  }
  function b7balls(ctx, n, x0, x1, yb, r, f, p, col, U = 3.2) { // heap of balls following f (bell), dropped in by p
    const cols = Math.floor((x1 - x0) / (r * 2)); let k = 0;
    for (let c = 0; c < cols; c++) { const u = -U + 2 * U * (c + 0.5) / cols, hN = Math.round(n * f(u));
      for (let j = 0; j < hN; j++, k++) { const t = clamp(p * 1.6 - b6rnd(k, 2) * 0.5 - j * 0.012); if (t <= 0) continue;
        G.disc(ctx, x0 + r + c * r * 2, lerp(330, yb - r - j * r * 2, E.o3(t)), r * 0.9, col); } }
  }
  // ── #11 三道防线 ──
  VIZ.gates_three = (ctx, s, lt, C) => { // 一条通道上依次立着三道闸门
    const D = s.vizDur, gy = 900;
    G.poly(ctx, [[160, gy], [1760, gy], [1700, gy + 80], [220, gy + 80]], rgba(C.fg, 0.12));
    [560, 1000, 1440].forEach((x, i) => { const p = pop(lt, 0.2 + i * 0.35, 0.7 + i * 0.35); if (p <= 0) return; ctx.save(); ctx.translate(x, gy); ctx.scale(1, p); b7gate(ctx, 0, 0, 380, i === 1 ? C.acc : C.fg, 0, null); ctx.restore(); });
    const wx = lerp(220, 1700, E.io(inv(D * 0.35, D * 0.95, lt))), sw = Math.sin(lt * 7);
    b6person(ctx, wx, gy, 200, PAL.gold.t[2], { lL1: 22 * sw, lR1: -22 * sw, aL1: -20 * sw, aR1: 20 * sw });
    tag(ctx, '三道关', W / 2, 400, C, inv(D * 0.45, D * 0.8, lt), { px: 40, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.gates_title = (ctx, s, lt, C) => { // 屏幕标题「Three Lines of Defense」，三道闸门编号一二三
    const D = s.vizDur, gy = 960;
    b6title(ctx, 'Three Lines of Defense', W / 2, 430, 104, C.fg, inv(0.05, D * 0.45, lt));
    ['一', '二', '三'].forEach((t, i) => { const x = 620 + i * 340, p = pop(lt, D * 0.3 + i * 0.25, D * 0.3 + i * 0.25 + 0.5); if (p <= 0) return;
      ctx.save(); ctx.translate(x, gy); ctx.scale(0.75 * p, 0.75 * p); b7gate(ctx, 0, 0, 360, C.fg, 0, null); ctx.restore();
      tag(ctx, t, x, gy - 330, C, p, { px: 44, bg: C.acc, fg: C.fg }); });
  };
  VIZ.gate_worker = (ctx, s, lt, C) => { // 第一道闸门旁，业务员边干活边看风险表
    const D = s.vizDur, gy = 960;
    b7gate(ctx, 1500, gy, 400, C.fg, 0, null); tag(ctx, '一', 1500, gy - 470, C, pop(lt, 0.1, 0.5), { px: 40 });
    ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(560, gy - 260, 520, 30); ctx.fillRect(600, gy - 230, 24, 230); ctx.fillRect(1016, gy - 230, 24, 230);
    const hit = Math.sin(lt * 6); b6person(ctx, 700, gy, 300, G.INK, { aR1: 95 + 25 * hit, aR2: 100 + 20 * hit, head: inv(D * 0.4, D * 0.6, lt) * 20 });
    for (let i = 0; i < 3; i++) { ctx.fillStyle = PAL.purple.t[2]; ctx.fillRect(760 + i * 70, gy - 300 - i * 6, 60, 40); }
    const p = pop(lt, D * 0.3, D * 0.6); if (p > 0) { ctx.save(); ctx.translate(1010, gy - 440); ctx.scale(p, p); b6doc(ctx, 0, 0, 220, 280, G.CREAM, rgba(G.INK, 0.3), inv(D * 0.3, D * 0.9, lt));
      ctx.font = F.zh(900, 34); ctx.fillStyle = PAL.red.t[2]; ctx.textAlign = 'center'; ctx.fillText('风险表', 0, -100); ctx.restore(); }
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.gate_tower = (ctx, s, lt, C) => { // 第二道闸门上方一个独立的观察台，有人拿望远镜
    const D = s.vizDur, gy = 980, tx = 1220;
    b7gate(ctx, 760, gy, 360, C.fg, 0, null); tag(ctx, '二', 760, gy - 430, C, pop(lt, 0.1, 0.5), { px: 40 });
    const k = E.io(inv(0.1, D * 0.5, lt)), ty = lerp(gy, 600, k);
    ctx.fillStyle = G.INK; ctx.fillRect(tx - 160, ty, 26, gy - ty); ctx.fillRect(tx + 134, ty, 26, gy - ty); ctx.fillRect(tx - 190, ty - 20, 380, 30);
    if (k > 0.95) { b6person(ctx, tx, ty - 20, 240, G.CREAM, { aR1: 120, aR2: 95, aL1: -110, aL2: -95, head: -6 });
      ctx.save(); ctx.translate(tx - 70, ty - 222); ctx.rotate(-0.25); ctx.fillStyle = G.INK; ctx.fillRect(-90, -16, 110, 32); ctx.restore(); }
    tag(ctx, '独立观察', 1560, 400, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.CREAM, fg: PAL.green.t[3] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.gate_audit = (ctx, s, lt, C) => { // 第三道闸门旁，有人翻看前两道的记录本
    const D = s.vizDur, gy = 980;
    b7gate(ctx, 480, gy, 380, C.fg, 0, null); tag(ctx, '三', 480, gy - 450, C, pop(lt, 0.1, 0.5), { px: 40 });
    b6person(ctx, 820, gy, 300, G.INK, { aR1: 70, aR2: 40, aL1: -70, aL2: -40, head: 18 });
    const bx = 1340, by = 640, flip = b6fr(lt * 0.8);
    ctx.fillStyle = G.CREAM; ctx.fillRect(bx - 300, by - 170, 300, 340); ctx.fillRect(bx + 6, by - 170, 300, 340);
    ctx.fillStyle = rgba(G.INK, 0.3); for (let i = 0; i < 6; i++) { ctx.fillRect(bx - 270, by - 130 + i * 48, 240, 10); ctx.fillRect(bx + 36, by - 130 + i * 48, i === 3 ? 140 : 240, 10); }
    ctx.save(); ctx.translate(bx, by); ctx.scale(Math.cos(flip * Math.PI), 1); ctx.fillStyle = rgba(G.CREAM, 0.9); ctx.fillRect(0, -170, 300, 340); ctx.restore();
    tag(ctx, '一', bx - 150, by - 230, C, pop(lt, D * 0.3, D * 0.6), { px: 32, bg: G.INK, fg: C.bg });
    tag(ctx, '二', bx + 156, by - 230, C, pop(lt, D * 0.4, D * 0.7), { px: 32, bg: G.INK, fg: C.bg });
    G.disc(ctx, bx + 230, by + 14, 22, PAL.red.t[2]);
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.gate_locks = (ctx, s, lt, C) => { // 三道闸门各自有独立的锁，钥匙在三个人手里
    const D = s.vizDur, gy = 760;
    [560, 960, 1360].forEach((x, i) => { b7gate(ctx, x, gy, 300, C.fg, 0, null);
      const p = pop(lt, 0.2 + i * 0.25, 0.6 + i * 0.25); if (p > 0) { ctx.save(); ctx.translate(x, gy - 160); ctx.scale(p, p);
        ctx.strokeStyle = G.INK; ctx.lineWidth = 12; ctx.beginPath(); ctx.arc(0, -30, 30, Math.PI, 0); ctx.stroke(); ctx.fillStyle = G.INK; ctx.fillRect(-46, -30, 92, 70); G.disc(ctx, 0, 0, 9, C.bg); ctx.restore(); }
      const kp = inv(D * 0.4 + i * 0.2, D * 0.7 + i * 0.2, lt), col = [PAL.gold.t[2], G.CREAM, PAL.purple.t[1]][i];
      b6person(ctx, x, 1000, 170, col, { aR1: lerp(8, 70, kp), aR2: lerp(12, 80, kp) });
      if (kp > 0) b6key(ctx, x + 70, 840, 60, col); });
    tag(ctx, '三把锁 · 三个人', 1500, 380, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: PAL.red.t[3] });
    vizCaption(ctx, s, lt, C, { x: 150, y: 220 });
  };
  function b7desk(ctx, gy, wall) {
    ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(360, gy - 260, 1200, 34); ctx.fillRect(400, gy - 226, 26, 226); ctx.fillRect(1494, gy - 226, 26, 226);
    if (wall > 0) { ctx.fillStyle = rgba(G.INK, 0.85 * wall); ctx.fillRect(W / 2 - 14, gy - 620, 28, 394); }
  }
  VIZ.desk_split = (ctx, s, lt, C) => { // 一张桌子被隔板分成两边：左边下单，右边记账，坐着不同的人
    const D = s.vizDur, gy = 980;
    b7desk(ctx, gy, E.io(inv(0.1, D * 0.4, lt)));
    b6person(ctx, 640, gy, 300, PAL.purple.t[2], { aR1: 85, aR2: 70 }); b6person(ctx, 1280, gy, 300, PAL.green.t[3], { aL1: -85, aL2: -70 });
    b6doc(ctx, 810, gy - 300, 150, 90, G.CREAM, rgba(G.INK, 0.3)); b6doc(ctx, 1110, gy - 300, 150, 90, G.CREAM, rgba(G.INK, 0.3));
    tag(ctx, '下单', 640, 480, C, pop(lt, D * 0.35, D * 0.6), { px: 40, bg: PAL.purple.t[2], fg: G.CREAM });
    tag(ctx, '记账', 1280, 480, C, pop(lt, D * 0.5, D * 0.75), { px: 40, bg: PAL.green.t[3], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.desk_merge = (ctx, s, lt, C) => { // 隔板被拿走，一个人同时坐两边，账本上的红字被盖住
    const D = s.vizDur, gy = 980, k = E.io(inv(0.1, D * 0.35, lt));
    ctx.save(); ctx.translate(0, -k * 500); ctx.globalAlpha = 1 - k; b7desk(ctx, gy, 1); ctx.restore(); b7desk(ctx, gy, 0);
    b6person(ctx, W / 2, gy, 320, G.INK, { aR1: 95, aR2: 80, aL1: -95, aL2: -80 });
    const lx = 1280, ly = gy - 330; ctx.fillStyle = G.CREAM; ctx.fillRect(lx - 150, ly - 70, 300, 120);
    ctx.fillStyle = PAL.red.t[3]; for (let i = 0; i < 3; i++) ctx.fillRect(lx - 120, ly - 46 + i * 34, 240, 14);
    const c = E.io(inv(D * 0.45, D * 0.8, lt)); ctx.fillStyle = G.INK; ctx.fillRect(lx - 150, ly - 70, 300 * c, 120);
    b6doc(ctx, 640, gy - 300, 150, 90, G.CREAM, rgba(G.INK, 0.3));
    tag(ctx, '红字被盖住', lx, 470, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: PAL.red.t[3] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.gates_catch = (ctx, s, lt, C) => { // 三道闸门亮灯，一个红色小错块在第二道被拦下
    const D = s.vizDur, gy = 920, xs = [520, 960, 1400];
    xs.forEach((x, i) => b7gate(ctx, x, gy, 340, C.fg, 0, PAL.green.t[1], inv(0.1 + i * 0.25, 0.4 + i * 0.25, lt)));
    const tStop = D * 0.55, u = clamp(lt / tStop), bx = lerp(200, xs[1] - 150, E.io(u)) - (lt > tStop ? Math.sin((lt - tStop) * 18) * 18 * Math.max(0, 1 - (lt - tStop) * 2) : 0);
    ctx.fillStyle = PAL.red.t[2]; ctx.beginPath(); ctx.roundRect(bx - 40, gy - 230, 80, 80, 12); ctx.fill();
    tag(ctx, '拦下', xs[1], 460, C, inv(tStop, tStop + 0.5, lt), { px: 44, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.oldbank_gate = (ctx, s, lt, C) => { // 镜头拉远：一栋无名老楼的轮廓，门口只剩一道闸门
    const D = s.vizDur, sc = lerp(1.5, 1, E.io(inv(0, D * 0.7, lt)));
    ctx.save(); ctx.translate(1160, 980); ctx.scale(sc, sc); ctx.translate(-1160, -980);
    b7bank(ctx, 1300, 980, 600, 500, rgba(G.INK, 0.8), rgba(G.CREAM, 0.35));
    b7gate(ctx, 760, 980, 300, G.INK, 0, PAL.red.t[2], 0.6 + 0.4 * Math.sin(lt * 5));
    ctx.restore();
    tag(ctx, '只剩一道', 760, 560, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  // ── #12 巴林银行 ──
  VIZ.bank_crack = (ctx, s, lt, C) => { // 一个人的剪影站在一栋老银行大楼前，大楼出现裂缝
    const D = s.vizDur, gy = 990, k = E.io(inv(D * 0.3, D * 0.9, lt));
    b7bank(ctx, 1200, gy, 700, 520, rgba(G.CREAM, 0.85), rgba(G.INK, 0.5));
    const pts = [[1200, gy - 660], [1170, gy - 560], [1230, gy - 460], [1180, gy - 350], [1250, gy - 240], [1210, gy - 110]], n = Math.max(1, Math.ceil((pts.length - 1) * k));
    if (k > 0) { ctx.save(); ctx.strokeStyle = PAL.red.t[2]; ctx.lineWidth = 12; ctx.lineJoin = 'round'; ctx.beginPath(); pts.slice(0, n + 1).forEach((p, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, p[0], p[1])); ctx.stroke(); ctx.restore(); }
    b6person(ctx, 520, gy, 360, '#0d0d14', { head: 6 });
    tag(ctx, '一个人', 520, 560, C, inv(D * 0.2, D * 0.5, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.bank_plate = (ctx, s, lt, C) => { // 老楼门牌「巴林银行 1995」，门口落下卷帘门
    const D = s.vizDur;
    ctx.fillStyle = rgba(G.CREAM, 0.85); ctx.fillRect(560, 380, 800, 610); ctx.fillStyle = rgba(G.INK, 0.75); ctx.fillRect(760, 560, 400, 430);
    const p = pop(lt, 0.1, 0.6); if (p > 0) { ctx.save(); ctx.translate(W / 2, 470); ctx.scale(p, p); ctx.fillStyle = PAL.gold.t[2]; ctx.beginPath(); ctx.roundRect(-300, -56, 600, 112, 14); ctx.fill();
      ctx.font = F.zh(900, 52); ctx.fillStyle = G.INK; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('巴林银行 1995', 0, 4); ctx.restore(); }
    const sh = 430 * E.io(inv(D * 0.35, D * 0.85, lt)); ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(760, 560, 400, sh);
    ctx.fillStyle = rgba(G.INK, 0.4); for (let y = 584; y < 560 + sh; y += 30) ctx.fillRect(760, y, 400, 6);
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.desk_leeson = (ctx, s, lt, C) => { // 交易台前一个背影，屏幕标「Nick Leeson · 新加坡」
    const D = s.vizDur;
    ctx.fillStyle = G.INK; ctx.beginPath(); ctx.roundRect(560, 400, 800, 400, 20); ctx.fill(); ctx.fillStyle = '#1d2b3a'; ctx.fillRect(590, 430, 740, 340);
    ctx.fillStyle = G.INK; ctx.fillRect(930, 800, 60, 60); ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(420, 860, 1080, 30);
    G.maskText(ctx, 'Nick Leeson', W / 2, 570, F.en(900, 72), G.CREAM, inv(0.2, D * 0.5, lt), { align: 'center', ls: '3px' });
    G.maskText(ctx, '新加坡', W / 2, 690, F.zh(900, 60), PAL.gold.t[2], inv(D * 0.35, D * 0.7, lt), { align: 'center', ls: '4px' });
    G.disc(ctx, W / 2, 900, 64, '#0d0d14'); ctx.fillStyle = '#0d0d14'; ctx.beginPath(); ctx.roundRect(W / 2 - 150, 950, 300, 200, 60); ctx.fill();
    vizCaption(ctx, s, lt, C);
  };
  VIZ.nikkei_board = (ctx, s, lt, C) => { // 屏幕标「日经225 指数期货」，只有文字没有走势图
    const D = s.vizDur;
    ctx.fillStyle = G.INK; ctx.beginPath(); ctx.roundRect(360, 360, 1200, 420, 24); ctx.fill();
    G.maskText(ctx, '日经225', W / 2, 540, F.zh(900, 150), PAL.gold.t[1], inv(0.1, D * 0.45, lt), { align: 'center', ls: '6px' });
    G.maskText(ctx, '指数期货', W / 2, 700, F.zh(900, 72), G.CREAM, inv(D * 0.3, D * 0.7, lt), { align: 'center', ls: '8px' });
    for (let i = 0; i < 6; i++) { const p = pop(lt, D * 0.4 + i * 0.12, D * 0.4 + i * 0.12 + 0.4); if (p <= 0) continue; ctx.save(); ctx.translate(560 + i * 130, 900 - i * 4); ctx.rotate((i - 2.5) * 0.04); ctx.scale(p, p); b6doc(ctx, 0, 0, 120, 150, G.CREAM, rgba(G.INK, 0.3)); ctx.restore(); }
    tag(ctx, '合约越堆越多', 1500, 920, C, inv(D * 0.7, D * 0.95, lt), { px: 34, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C, { x: 150, y: 220 });
  };
  VIZ.ledger_drawer = (ctx, s, lt, C) => { // 一本账簿最后一页夹着一个隐藏的小抽屉，红字往里塞
    const D = s.vizDur, bx = W / 2, by = 560;
    ctx.fillStyle = G.CREAM; ctx.fillRect(bx - 420, by - 200, 410, 420); ctx.fillRect(bx + 10, by - 200, 410, 420);
    ctx.fillStyle = rgba(G.INK, 0.3); for (let i = 0; i < 7; i++) { ctx.fillRect(bx - 380, by - 160 + i * 50, 330, 10); ctx.fillRect(bx + 50, by - 160 + i * 50, 330, 10); }
    const dk = E.io(inv(0.2, D * 0.45, lt)), dy = by + 220 + dk * 120;
    ctx.fillStyle = G.INK; ctx.fillRect(bx - 180, by + 220, 360, dk * 140); ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(bx - 200, dy, 400, 30);
    for (let i = 0; i < 4; i++) { const u = clamp(inv(D * 0.4 + i * 0.35, D * 0.4 + i * 0.35 + 0.6, lt)); if (u <= 0) continue;
      ctx.save(); ctx.globalAlpha = 1 - u * 0.8; ctx.fillStyle = PAL.red.t[2]; ctx.fillRect(lerp(bx + 60, bx - 60, u), lerp(by - 120 + i * 60, by + 280, u), 200 * (1 - u * 0.5), 18); ctx.restore(); }
    tag(ctx, '藏起来', bx + 540, by + 300, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.drawer_88888 = (ctx, s, lt, C) => { // 抽屉标签「88888」
    const D = s.vizDur, k = E.io(inv(0, D * 0.4, lt)), sc = lerp(0.8, 1, k);
    ctx.save(); ctx.translate(W / 2, 620); ctx.scale(sc, sc);
    ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(-520, -230, 1040, 460); ctx.fillStyle = rgba(G.INK, 0.25); ctx.fillRect(-490, -200, 980, 400);
    ctx.fillStyle = G.CREAM; ctx.beginPath(); ctx.roundRect(-360, -110, 720, 220, 18); ctx.fill();
    G.typeText(ctx, '88888', 0, 56, F.mono(170), G.INK, inv(D * 0.1, D * 0.5, lt), { align: 'center', ls: '10px', caret: false });
    ctx.fillStyle = G.INK; ctx.fillRect(-90, 150, 180, 34); ctx.restore();
    tag(ctx, '错误账户', W / 2, 960, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: PAL.red.t[3] });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 220, align: 'right' });
  };
  VIZ.two_hands = (ctx, s, lt, C) => { // 同一个人左手下单、右手盖章结算
    const D = s.vizDur, gy = 990, st = Math.max(0, Math.sin(lt * 5));
    ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(420, gy - 300, 1080, 30);
    b6person(ctx, W / 2, gy, 340, G.CREAM, { aL1: -100, aL2: -80, aR1: 100, aR2: 95 + st * 30 });
    b6doc(ctx, 640, gy - 360, 170, 110, G.CREAM, rgba(G.INK, 0.3), inv(0.2, D * 0.6, lt));
    b6doc(ctx, 1280, gy - 330, 170, 110, G.CREAM, rgba(G.INK, 0.3));
    ctx.fillStyle = PAL.red.t[2]; ctx.fillRect(1250, gy - 470 + st * 90, 60, 80); ctx.fillRect(1230, gy - 400 + st * 90, 100, 20);
    if (st > 0.9) { ctx.strokeStyle = PAL.red.t[2]; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(1280, gy - 330, 40, 0, Math.PI * 2); ctx.stroke(); }
    tag(ctx, '下单', 640, 480, C, pop(lt, D * 0.25, D * 0.5), { px: 38, bg: G.CREAM, fg: PAL.purple.t[3] });
    tag(ctx, '结算', 1280, 480, C, pop(lt, D * 0.45, D * 0.7), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.empty_chair = (ctx, s, lt, C) => { // 本该站第二个人的位置是空椅子
    const D = s.vizDur, gy = 990;
    b7chair(ctx, 700, gy, 300, G.INK); b6person(ctx, 680, gy, 300, PAL.purple.t[2], { aR1: 80, aR2: 70 });
    b7chair(ctx, 1240, gy, 300, rgba(G.INK, 0.8));
    const p = inv(D * 0.3, D * 0.6, lt); if (p > 0) { ctx.save(); ctx.globalAlpha = clamp(p); ctx.setLineDash([18, 14]); ctx.strokeStyle = PAL.red.t[2]; ctx.lineWidth = 6; ctx.beginPath(); ctx.ellipse(1250, gy - 230, 190, 280, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); }
    ctx.save(); ctx.font = F.en(900, 140); ctx.fillStyle = rgba(PAL.red.t[2], clamp(inv(D * 0.4, D * 0.7, lt))); ctx.textAlign = 'center'; ctx.fillText('?', 1250, gy - 540); ctx.restore();
    tag(ctx, '没人复核', 1600, 420, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.quake_map = (ctx, s, lt, C) => { // 地图上日本神户一带震波扩散（只画地图与震波，不画人）
    const D = s.vizDur, ex = 1040, ey = 690;
    const isl = [[[1380, 380], [1460, 440], [1420, 520], [1340, 470]], [[1180, 500], [1330, 540], [1300, 640], [1150, 700], [1010, 720], [860, 760], [760, 820], [800, 760], [960, 680], [1100, 600]], [[880, 800], [990, 790], [960, 860], [870, 860]], [[620, 860], [740, 850], [720, 950], [600, 940]]];
    isl.forEach((pp) => G.poly(ctx, pp, rgba(G.CREAM, 0.8)));
    for (let i = 0; i < 4; i++) { const u = b6fr(lt * 0.6 + i / 4); ctx.save(); ctx.globalAlpha = (1 - u) * clamp(inv(0.2, 0.8, lt)); ctx.strokeStyle = PAL.red.t[2]; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(ex, ey, 30 + u * 380, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); }
    G.disc(ctx, ex, ey, 16, PAL.red.t[2]);
    tag(ctx, '神户 · 1995.1', ex - 260, ey + 160, C, inv(D * 0.3, D * 0.6, lt), { px: 36, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.snowball_down = (ctx, s, lt, C) => { // 红色亏损雪球往下坡滚，越滚越大
    const D = s.vizDur, k = E.io(inv(0.1, D * 0.95, lt));
    G.poly(ctx, [[160, 420], [1760, 980], [160, 980]], rgba(G.CREAM, 0.85));
    const x = lerp(300, 1480, k), r = lerp(30, 150, k), y = lerp(420, 980, (x - 160) / 1600) - r * 1.05;
    ctx.save(); ctx.translate(x, y); ctx.rotate(lt * 4); G.disc(ctx, 0, 0, r, G.INK); ctx.fillStyle = PAL.red.t[1]; ctx.fillRect(-r * 0.7, -r * 0.08, r * 1.4, r * 0.16); ctx.restore();
    tag(ctx, '越滚越大', 1400, 420, C, inv(D * 0.5, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.pounds_sink = (ctx, s, lt, C) => { // 屏幕数字「约 8.27 亿英镑」往下沉
    const D = s.vizDur, k = E.io(inv(D * 0.3, D * 0.95, lt)), y = lerp(560, 820, k);
    ctx.fillStyle = rgba(G.INK, 0.25); ctx.fillRect(96, 760, 1728, 266);
    G.maskText(ctx, '约 8.27 亿英镑', W / 2, y, F.zh(900, 140), G.INK, inv(0.05, D * 0.4, lt), { align: 'center', ls: '4px' });
    b6down(ctx, 1660, 400, 680, PAL.red.t[2], 14, inv(D * 0.3, D * 0.8, lt));
    vizCaption(ctx, s, lt, C);
  };
  VIZ.capital_floor = (ctx, s, lt, C) => { // 红色亏损柱往下压，越过了标着「银行资本」的地板线
    const D = s.vizDur, fy = 620, k = E.io(inv(0.1, D * 0.8, lt)), by = lerp(380, 920, k);
    ctx.fillStyle = PAL.ochre.t[3]; ctx.fillRect(260, fy, 1400, 34);
    tag(ctx, '银行资本', 440, fy + 100, C, pop(lt, 0.1, 0.5), { px: 38, bg: PAL.ochre.t[3], fg: G.CREAM });
    ctx.fillStyle = PAL.red.t[2]; ctx.fillRect(W / 2 - 110, 360, 220, by - 360); G.poly(ctx, [[W / 2 - 110, by], [W / 2 + 110, by], [W / 2, by + 60]], PAL.red.t[2]);
    if (by > fy) { ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 8; [-1, 1].forEach((d) => { ctx.beginPath(); ctx.moveTo(W / 2 + d * 110, fy + 17); ctx.lineTo(W / 2 + d * 220, fy - 10); ctx.lineTo(W / 2 + d * 300, fy + 30); ctx.stroke(); }); ctx.restore(); }
    tag(ctx, '压穿', 1460, 880, C, inv(D * 0.6, D * 0.9, lt), { px: 40, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.coin_keys = (ctx, s, lt, C) => { // 一枚一英镑硬币放在老楼钥匙旁
    const D = s.vizDur, gy = 820;
    ctx.fillStyle = rgba(G.INK, 0.2); ctx.fillRect(200, gy, 1520, 200);
    const p = pop(lt, D * 0.25, D * 0.6); if (p > 0) { ctx.save(); ctx.translate(760, gy - 140); ctx.scale(p, p); G.disc(ctx, 0, 0, 150, '#d9a62e'); G.disc(ctx, 0, 0, 122, '#f1c453');
      ctx.font = F.zh(900, 60); ctx.fillStyle = G.INK; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('1英镑', 0, 4); ctx.restore(); }
    ctx.save(); ctx.translate(1260, gy - 120); ctx.rotate(-0.15); b6key(ctx, 0, 0, 260, G.INK); ctx.restore();
    tag(ctx, '象征性价格', 1500, 400, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.gates_dark = (ctx, s, lt, C) => { // 回到三道闸门：三道全开着，没有一盏灯亮
    const D = s.vizDur;
    G.poly(ctx, [[560, 600], [760, 600], [1760, 1000], [1060, 1000]], rgba(G.CREAM, 0.08));
    [[680, 600, 0.5], [1000, 760, 0.72], [1420, 990, 1]].forEach(([x, y, sc], i) => { ctx.save(); ctx.translate(x, y); ctx.scale(sc, sc);
      b7gate(ctx, 0, 0, 380, rgba(G.CREAM, 0.8), E.io(inv(0.1 + i * 0.2, D * 0.5 + i * 0.2, lt)), PAL.green.t[1], 0); ctx.restore(); });
    tag(ctx, '全都开着', 1500, 420, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  // ── #13 长期资本管理公司 ──
  function b7car(ctx, x, y, s, col, rot = 0, gauge = 0) { // instrument car, (x,y) = ground under centre
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.fillStyle = col;
    ctx.beginPath(); ctx.roundRect(-s, -s * 0.62, s * 2, s * 0.42, 18); ctx.fill(); ctx.beginPath(); ctx.roundRect(-s * 0.55, -s * 0.95, s * 1.1, s * 0.4, 18); ctx.fill();
    G.disc(ctx, -s * 0.6, -s * 0.2, s * 0.22, G.INK); G.disc(ctx, s * 0.6, -s * 0.2, s * 0.22, G.INK);
    G.disc(ctx, 0, -s * 1.15, s * 0.26, G.CREAM); ctx.strokeStyle = G.INK; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(0, -s * 1.15); ctx.lineTo(Math.cos(-2.4 + gauge) * s * 0.2, -s * 1.15 + Math.sin(-2.4 + gauge) * s * 0.2); ctx.stroke();
    ctx.restore();
  }
  VIZ.gauge_car = (ctx, s, lt, C) => { // 一辆精密仪表车在平路上开得很稳，前方出现一个深坑
    const D = s.vizDur, gy = 900, k = E.io(inv(0, D * 0.9, lt));
    ctx.fillStyle = G.INK; ctx.fillRect(96, gy, 1300, 16); ctx.fillRect(1640, gy, 184, 16);
    const pk = E.io(inv(D * 0.3, D * 0.7, lt)); G.poly(ctx, [[1396, gy], [1640, gy], [1600, gy + 110 * pk], [1436, gy + 110 * pk]], rgba(G.INK, 0.85));
    b7car(ctx, lerp(300, 1100, k), gy, 130, PAL.purple.t[2], 0, Math.sin(lt * 2) * 0.1);
    tag(ctx, '深坑', 1518, 780, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ltcm_title = (ctx, s, lt, C) => { // 屏幕标题「LTCM」，一栋无标识写字楼
    const D = s.vizDur;
    b6title(ctx, 'LTCM', 700, 600, 220, C.fg, inv(0.05, D * 0.45, lt), 900);
    const p = E.io(inv(D * 0.2, D * 0.7, lt)); b7tower(ctx, 1440, 1000, 320, 640 * p, rgba(G.CREAM, 0.85), rgba(G.INK, 0.4));
  };
  VIZ.medal_manual = (ctx, s, lt, C) => { // 会议桌上放着一枚奖章和厚厚的模型手册，标「1994」
    const D = s.vizDur, gy = 820;
    ctx.fillStyle = PAL.ochre.t[4] || G.INK; ctx.fillRect(200, gy, 1520, 40); ctx.fillStyle = rgba(G.INK, 0.25); ctx.fillRect(260, gy + 40, 1400, 160);
    const mp = pop(lt, 0.2, 0.7); if (mp > 0) { ctx.save(); ctx.translate(640, gy - 150); ctx.scale(mp, mp); G.poly(ctx, [[-50, -150], [0, -60], [50, -150]], PAL.red.t[2]); G.disc(ctx, 0, 0, 100, '#d9a62e'); G.disc(ctx, 0, 0, 70, '#f1c453'); ctx.restore(); }
    const bp = E.io(inv(D * 0.25, D * 0.7, lt)); for (let i = 0; i < 8; i++) { if (i / 8 > bp) break; ctx.fillStyle = i % 2 ? G.CREAM : '#e6dcc6'; ctx.fillRect(1040, gy - 30 - i * 30, 420, 28); }
    ctx.fillStyle = PAL.purple.t[2]; ctx.fillRect(1030, gy - 30 - 8 * 30 * bp - 12, 440, 20);
    tag(ctx, '1994', 1250, 420, C, inv(D * 0.5, D * 0.8, lt), { px: 44, bg: G.INK, fg: C.bg, font: F.mono(44) });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.gap_lines = (ctx, s, lt, C) => { // 两条本该并拢的线中间有一道缝，箭头指向合拢
    const D = s.vizDur, k = E.io(inv(0.1, D * 0.5, lt)), gap = 70 + 20 * Math.sin(lt * 2);
    ctx.save(); ctx.lineCap = 'round'; ctx.lineWidth = 16;
    ctx.strokeStyle = G.CREAM; ctx.beginPath(); ctx.moveTo(260, 650 - gap); ctx.lineTo(lerp(260, 1660, k), 650 - gap); ctx.stroke();
    ctx.strokeStyle = C.acc; ctx.beginPath(); ctx.moveTo(260, 650 + gap); ctx.lineTo(lerp(260, 1660, k), 650 + gap); ctx.stroke(); ctx.restore();
    const ap = inv(D * 0.45, D * 0.8, lt); b6down(ctx, 960, 400, 540, G.CREAM, 10, ap); b6upArrow(ctx, 960, 900, 760, C.acc, 10, ap);
    tag(ctx, '等它合拢', 1500, 920, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.lever_rock = (ctx, s, lt, C) => { // 一根小撬棍撬起一块巨石
    const D = s.vizDur, gy = 960, k = E.io(inv(D * 0.2, D * 0.7, lt)), a = lerp(0.18, -0.22, k), fx = 760;
    G.poly(ctx, [[fx - 60, gy], [fx + 60, gy], [fx, gy - 100]], G.INK);
    ctx.save(); ctx.translate(fx, gy - 100); ctx.rotate(a); ctx.fillStyle = G.CREAM; ctx.fillRect(-460, -10, 1000, 20);
    ctx.fillStyle = rgba(G.INK, 0.85); ctx.beginPath(); ctx.ellipse(400, -170, 200, 160, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    const hx = fx - 430 * Math.cos(a), hy = gy - 100 - 430 * Math.sin(a);
    b6person(ctx, hx - 40, gy, 220, G.CREAM, { aR1: 60, aR2: 50, torso: 18 });
    tag(ctx, '小力撬大石', 1460, 400, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.CREAM, fg: PAL.green.t[3] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.coins_25 = (ctx, s, lt, C) => { // 天平一边一枚小硬币，另一边二十五枚叠起来的硬币，标「约25倍+」
    const D = s.vizDur, cx = W / 2, cy = 560, k = E.io(inv(D * 0.2, D * 0.7, lt)), a = 0.16 * k;
    ctx.fillStyle = G.INK; ctx.fillRect(cx - 14, cy, 28, 420); ctx.fillRect(cx - 160, 970, 320, 24);
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(a); ctx.fillStyle = G.INK; ctx.fillRect(-560, -10, 1120, 20);
    [-1, 1].forEach((d) => { ctx.fillStyle = G.INK; ctx.fillRect(d * 520 - 4, 0, 8, 140); ctx.fillRect(d * 520 - 130, 140, 260, 14); });
    ctx.restore();
    const L = [cx - 520 * Math.cos(a), cy - 520 * Math.sin(a) + 140], R = [cx + 520 * Math.cos(a), cy + 520 * Math.sin(a) + 140];
    ctx.fillStyle = '#f1c453'; ctx.beginPath(); ctx.ellipse(L[0], L[1] - 16, 60, 16, 0, 0, Math.PI * 2); ctx.fill();
    const n = Math.round(25 * E.io(inv(D * 0.1, D * 0.6, lt))); for (let i = 0; i < n; i++) { ctx.fillStyle = i % 2 ? '#d9a62e' : '#f1c453'; ctx.fillRect(R[0] - 60, R[1] - 14 - (i + 1) * 13, 120, 12); }
    tag(ctx, '约25倍+', R[0], 360, C, inv(D * 0.55, D * 0.85, lt), { px: 42, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.iou_torn = (ctx, s, lt, C) => { // 一张欠条被撕开，标「1998 俄罗斯违约」
    const D = s.vizDur, k = E.io(inv(D * 0.3, D * 0.8, lt)), cx = W / 2, cy = 620;
    [-1, 1].forEach((d) => { ctx.save(); ctx.translate(cx + d * k * 80, cy + k * 60); ctx.rotate(d * k * 0.12);
      ctx.fillStyle = '#e9dcbf'; ctx.strokeStyle = rgba(G.INK, 0.55); ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(0, -220); ctx.lineTo(d * 360, -220); ctx.lineTo(d * 360, 220); ctx.lineTo(0, 220);
      for (let i = 0; i < 8; i++) ctx.lineTo(d * (i % 2 ? 16 : -6), 220 - i * 55); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = rgba(G.INK, 0.3); for (let i = 0; i < 4; i++) ctx.fillRect(d > 0 ? 40 : -320, -60 + i * 50, 280, 10); ctx.restore(); });
    G.maskText(ctx, '欠条', cx, cy - 120, F.zh(900, 64), G.INK, inv(0.1, D * 0.3, lt), { align: 'center', ls: '8px' });
    tag(ctx, '1998 俄罗斯违约', cx, 940, C, inv(D * 0.45, D * 0.75, lt), { px: 40, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.gap_widen = (ctx, s, lt, C) => { // 那两条线不仅没合拢，缝隙越撕越宽
    const D = s.vizDur, k = E.io(inv(0.1, D * 0.9, lt)), n = 60, x0 = 260, x1 = 1660;
    ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = 14;
    const up = (u) => 560 - 40 * u * u, dn = (u) => 640 + 300 * u * u; const m = Math.max(1, Math.round(n * k));
    ctx.fillStyle = rgba(G.INK, 0.35); ctx.beginPath(); for (let i = 0; i <= m; i++) { const u = i / n; ctx.lineTo(lerp(x0, x1, u), up(u)); } for (let i = m; i >= 0; i--) { const u = i / n; ctx.lineTo(lerp(x0, x1, u), dn(u)); } ctx.fill();
    ctx.strokeStyle = G.CREAM; ctx.beginPath(); for (let i = 0; i <= m; i++) { const u = i / n; (i ? ctx.lineTo : ctx.moveTo).call(ctx, lerp(x0, x1, u), up(u)); } ctx.stroke();
    ctx.strokeStyle = G.INK; ctx.beginPath(); for (let i = 0; i <= m; i++) { const u = i / n; (i ? ctx.lineTo : ctx.moveTo).call(ctx, lerp(x0, x1, u), dn(u)); } ctx.stroke(); ctx.restore();
    b6down(ctx, 1700, 660, 940, G.INK, 10, inv(D * 0.5, D * 0.85, lt));
    tag(ctx, '越拉越大', 1400, 420, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.rock_drop = (ctx, s, lt, C) => { // 撬棍反弹，巨石往下砸，红色亏损线成倍下坠
    const D = s.vizDur, gy = 960, fx = 560, k = E.io(inv(0.1, D * 0.45, lt)), a = lerp(-0.22, 0.2, k);
    G.poly(ctx, [[fx - 50, gy], [fx + 50, gy], [fx, gy - 90]], G.CREAM);
    ctx.save(); ctx.translate(fx, gy - 90); ctx.rotate(a); ctx.fillStyle = G.CREAM; ctx.fillRect(-320, -9, 700, 18); ctx.restore();
    const ry = lerp(560, 860, E.i3 ? E.i3(k) : k * k); ctx.fillStyle = rgba(G.CREAM, 0.85); ctx.beginPath(); ctx.ellipse(fx + 300, ry, 150, 120, 0, 0, Math.PI * 2); ctx.fill();
    const lp = inv(D * 0.35, D * 0.95, lt), steps = [[1000, 420], [1140, 420], [1140, 480], [1280, 480], [1280, 600], [1420, 600], [1420, 840], [1640, 840]];
    const m = Math.max(1, Math.ceil((steps.length - 1) * lp)); if (lp > 0) { ctx.save(); ctx.strokeStyle = PAL.red.t[2]; ctx.lineWidth = 14; ctx.lineJoin = 'round'; ctx.beginPath(); steps.slice(0, m + 1).forEach((p, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, p[0], p[1])); ctx.stroke(); ctx.restore(); }
    tag(ctx, '成倍往下', 1420, 960, C, inv(D * 0.7, D * 0.95, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ring_14 = (ctx, s, lt, C) => { // 十四个无标识的小方块围成一圈，中间一个协调人
    const D = s.vizDur, cx = W / 2, cy = 640;
    for (let i = 0; i < 14; i++) { const p = pop(lt, 0.1 + i * 0.08, 0.5 + i * 0.08); if (p <= 0) continue; const a = -Math.PI / 2 + i / 14 * Math.PI * 2;
      ctx.save(); ctx.translate(cx + Math.cos(a) * 340, cy + Math.sin(a) * 300); ctx.scale(p, p); ctx.fillStyle = i % 2 ? G.CREAM : PAL.gold.t[1]; ctx.beginPath(); ctx.roundRect(-38, -38, 76, 76, 12); ctx.fill(); ctx.restore(); }
    b6person(ctx, cx, cy + 130, 240, G.CREAM, { aR1: 120 + 20 * Math.sin(lt * 3), aR2: 140, aL1: -120, aL2: -140 });
    tag(ctx, '十四家', 1540, 940, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: PAL.purple.t[3] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hand_catch = (ctx, s, lt, C) => { // 一只大手接住正在下坠的写字楼，标「约36亿美元」
    const D = s.vizDur, k = E.io(inv(0, D * 0.5, lt)), ty = lerp(560, 760, k), cx = 1000;
    ctx.save(); ctx.translate(cx, ty); ctx.rotate(0.12 * (1 - k)); b7tower(ctx, 0, 0, 240, 420, rgba(G.INK, 0.85), rgba(G.CREAM, 0.4)); ctx.restore();
    b7hand(ctx, cx, 900, 300, G.CREAM, 0);
    tag(ctx, '约36亿美元', 1520, 520, C, inv(D * 0.45, D * 0.75, lt), { px: 42, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.manual_wave = (ctx, s, lt, C) => { // 模型手册上写「极少发生」，窗外大浪拍来
    const D = s.vizDur;
    ctx.fillStyle = G.CREAM; ctx.beginPath(); ctx.roundRect(260, 460, 520, 500, 16); ctx.fill(); ctx.fillStyle = PAL.purple.t[2]; ctx.fillRect(260, 460, 40, 500);
    G.maskText(ctx, '极少发生', 545, 720, F.zh(900, 76), G.INK, inv(0.1, D * 0.4, lt), { align: 'center', ls: '4px' });
    const wx = 1000, wy = 380, ww = 720, wh = 600; ctx.fillStyle = '#cfe3ea'; ctx.fillRect(wx, wy, ww, wh);
    const k = E.io(inv(D * 0.3, D * 0.9, lt)), crest = lerp(wy + wh, wy + 60, k);
    ctx.save(); ctx.beginPath(); ctx.rect(wx, wy, ww, wh); ctx.clip(); ctx.fillStyle = '#1f4e79'; ctx.beginPath(); ctx.moveTo(wx, wy + wh);
    for (let x = 0; x <= ww; x += 20) ctx.lineTo(wx + x, crest + 60 * Math.sin(x / 90 + lt * 3) + (x / ww) * 80); ctx.lineTo(wx + ww, wy + wh); ctx.closePath(); ctx.fill(); ctx.restore();
    ctx.strokeStyle = G.INK; ctx.lineWidth = 20; ctx.strokeRect(wx, wy, ww, wh); ctx.beginPath(); ctx.moveTo(wx + ww / 2, wy); ctx.lineTo(wx + ww / 2, wy + wh); ctx.stroke();
    vizCaption(ctx, s, lt, C);
  };
  VIZ.car_stuck = (ctx, s, lt, C) => { // 回到开头：精密仪表车卡在深坑里，撬棍断在旁边
    const D = s.vizDur, gy = 760;
    ctx.fillStyle = G.INK; ctx.fillRect(96, gy, 600, 16); ctx.fillRect(1220, gy, 604, 16); G.poly(ctx, [[696, gy], [1220, gy], [1140, 1000], [776, 1000]], rgba(G.INK, 0.85));
    const k = E.io(inv(0, D * 0.4, lt)); b7car(ctx, 960, lerp(gy, 930, k), 150, G.CREAM, lerp(0, 0.35, k), 1.8);
    ctx.save(); ctx.translate(1420, gy - 20); ctx.rotate(-0.1); ctx.fillStyle = G.CREAM; ctx.fillRect(0, -10, 200, 20); ctx.restore();
    ctx.save(); ctx.translate(1640, gy - 26); ctx.rotate(0.5); ctx.fillStyle = G.CREAM; ctx.fillRect(0, -10, 150, 20); ctx.restore();
    tag(ctx, '扛不住', 1520, 520, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.CREAM, fg: PAL.red.t[3] });
    vizCaption(ctx, s, lt, C);
  };
  // ── #14 正态分布 ── (bell curves; the loss tail is the LEFT tail, labelled 大亏 / 大跌)
  const B7X0 = 300, B7X1 = 1620, B7YB = 920;
  VIZ.balls_pile = (ctx, s, lt, C) => { // 一堆小球从上方落下，大多数堆在中间
    const D = s.vizDur; ctx.fillStyle = rgba(C.fg, 0.4); ctx.fillRect(B7X0, B7YB, B7X1 - B7X0, 8);
    b7balls(ctx, 14, B7X0 + 200, B7X1 - 200, B7YB, 20, b7N, inv(0.1, D * 0.9, lt), C.acc);
    tag(ctx, '挤在中间', 1560, 420, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.normal_title = (ctx, s, lt, C) => { // 小球堆成钟形，屏幕标题「Normal Distribution」
    const D = s.vizDur;
    b7balls(ctx, 11, 560, 1360, 1000, 18, b7N, 1, rgba(G.CREAM, 0.75));
    b6title(ctx, 'Normal Distribution', W / 2, 440, 110, C.fg, inv(0.05, D * 0.5, lt));
  };
  VIZ.bell_outline = (ctx, s, lt, C) => { // 小球的轮廓变成一条平滑的钟形曲线
    const D = s.vizDur, k = inv(D * 0.2, D * 0.8, lt);
    ctx.save(); ctx.globalAlpha = 1 - 0.75 * clamp(k); b7balls(ctx, 13, B7X0 + 120, B7X1 - 120, B7YB, 20, b7N, 1, PAL.purple.t[1]); ctx.restore();
    ctx.fillStyle = rgba(G.INK, 0.5); ctx.fillRect(B7X0 - 60, B7YB, B7X1 - B7X0 + 120, 6);
    b7curve(ctx, B7X0, B7X1, B7YB, 560, b7N, k, G.INK, 12, null, 3.6, 'left');
    tag(ctx, '一口钟', 1560, 420, C, inv(D * 0.7, D * 0.95, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.bell_peak = (ctx, s, lt, C) => { // 钟形中间高耸处标「普通的一天」
    const D = s.vizDur;
    b7curve(ctx, B7X0, B7X1, B7YB, 520, b7N, 1, G.CREAM, 10, rgba(G.CREAM, 0.25));
    const p = pop(lt, D * 0.25, D * 0.6), px = (B7X0 + B7X1) / 2; if (p > 0) { ctx.fillStyle = G.CREAM; ctx.fillRect(px - 4, B7YB - 520 - 120 * p, 8, 120 * p); G.poly(ctx, [[px + 4, B7YB - 520 - 120 * p], [px + 70, B7YB - 520 - 95 * p], [px + 4, B7YB - 520 - 70 * p]], PAL.gold.t[2]); }
    tag(ctx, '普通的一天', px, B7YB - 160, C, inv(D * 0.4, D * 0.75, lt), { px: 40, bg: G.CREAM, fg: PAL.green.t[3] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.bell_tails = (ctx, s, lt, C) => { // 两边尾巴越来越细；左尾标「大亏」，右尾标「大赚」
    const D = s.vizDur;
    b7curve(ctx, B7X0, B7X1, B7YB, 500, b7N, 1, G.INK, 10, rgba(G.INK, 0.12));
    const lp = inv(D * 0.2, D * 0.55, lt), rp = inv(D * 0.4, D * 0.75, lt);
    if (lp > 0) b7area(ctx, B7X0, B7X1, B7YB, 500, b7N, B7X0, B7X0 + 300, rgba(PAL.red.t[2], clamp(lp)));
    if (rp > 0) b7area(ctx, B7X0, B7X1, B7YB, 500, b7N, B7X1 - 300, B7X1, rgba(PAL.green.t[2], clamp(rp)));
    tag(ctx, '大亏', B7X0 + 120, B7YB + 60, C, lp, { px: 38, bg: PAL.red.t[2], fg: G.CREAM }); b6down(ctx, B7X0 + 40, B7YB - 160, B7YB - 40, PAL.red.t[2], 8, lp);
    tag(ctx, '大赚', B7X1 - 120, B7YB + 60, C, rp, { px: 38, bg: PAL.green.t[3], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.calc_bell = (ctx, s, lt, C) => { // 一台计算器上贴着这条钟形曲线
    const D = s.vizDur, cx = 1160, cy = 640, [sx, sy] = b7calc(ctx, cx, cy, 520, 680, G.INK, '#cfe3d4', rgba(G.CREAM, 0.6));
    const p = pop(lt, D * 0.25, D * 0.6); if (p > 0) { ctx.save(); ctx.translate(sx, sy); ctx.rotate(-0.05); ctx.scale(p, p); ctx.fillStyle = G.CREAM; ctx.fillRect(-180, -70, 360, 140);
      b7curve(ctx, -160, 160, 50, 100, b7N, 1, PAL.purple.t[2], 6, null); ctx.restore(); }
    tag(ctx, '模型默认', 560, 640, C, inv(D * 0.5, D * 0.85, lt), { px: 40, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.calc_tick = (ctx, s, lt, C) => { // 计算器一按就出结果，屏幕打勾
    const D = s.vizDur, cx = 760, cy = 640, [sx, sy] = b7calc(ctx, cx, cy, 520, 680, PAL.purple.t[2], '#cfe3d4', rgba(G.CREAM, 0.7));
    const press = inv(D * 0.2, D * 0.35, lt); const fx = cx + 60, fy = lerp(cy + 120, cy + 170, Math.sin(Math.PI * clamp(press)));
    ctx.fillStyle = G.INK; ctx.beginPath(); ctx.roundRect(fx - 30, fy - 200, 60, 220, 30); ctx.fill();
    const tp = inv(D * 0.35, D * 0.6, lt); if (tp > 0) { ctx.save(); ctx.strokeStyle = PAL.green.t[3]; ctx.lineWidth = 18; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(sx - 60, sy); ctx.lineTo(sx - 15, sy + 40 * clamp(tp * 2)); if (tp > 0.5) ctx.lineTo(sx - 15 + 90 * (tp - 0.5) * 2, sy + 40 - 90 * (tp - 0.5) * 2); ctx.stroke(); ctx.restore(); }
    tag(ctx, '算起来方便', 1400, 640, C, inv(D * 0.5, D * 0.85, lt), { px: 40, bg: PAL.green.t[3], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.dots_outliers = (ctx, s, lt, C) => { // 真实数据点散落在钟形曲线旁，几个点落在左边很远处
    const D = s.vizDur;
    b7curve(ctx, B7X0 + 200, B7X1, B7YB, 480, b7N, 1, G.CREAM, 8, null);
    for (let i = 0; i < 40; i++) { const p = pop(lt, 0.1 + i * 0.03, 0.4 + i * 0.03); if (p <= 0) continue; const u = (b6rnd(i, 7) + b6rnd(i, 8) + b6rnd(i, 9) - 1.5) * 2.2;
      const x = lerp(B7X0 + 200, B7X1, (u + 3.6) / 7.2), y = B7YB - 480 * b7N(u) * b6rnd(i, 3); G.disc(ctx, x, y - 10, 12 * p, G.INK); }
    [[170, 900], [230, 880], [130, 910]].forEach(([x, y], i) => { const p = pop(lt, D * 0.45 + i * 0.2, D * 0.45 + i * 0.2 + 0.4); if (p > 0) { G.disc(ctx, x, y, 20 * p, G.CREAM); b7rings(ctx, x, y, 36, G.CREAM, 5, p); } });
    tag(ctx, '左边很远', 260, 760, C, inv(D * 0.7, D * 0.95, lt), { px: 36, bg: G.CREAM, fg: PAL.red.t[3] });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.tail_shadow = (ctx, s, lt, C) => { // 钟形左侧尾巴被一层阴影加厚，留个悬念
    const D = s.vizDur, k = E.io(inv(D * 0.25, D * 0.8, lt));
    const fz = (u) => (u < 0 ? lerp(b7N(u), b7T(u), k) : b7N(u));
    b7curve(ctx, B7X0, B7X1, B7YB, 500, fz, 1, null, 0, rgba(PAL.red.t[2], 0.45));
    b7curve(ctx, B7X0, B7X1, B7YB, 500, b7N, 1, G.CREAM, 10, rgba(G.CREAM, 0.15));
    ctx.save(); ctx.font = F.en(900, 120); ctx.fillStyle = rgba(G.CREAM, clamp(inv(D * 0.6, D * 0.9, lt))); ctx.textAlign = 'center'; ctx.fillText('?', B7X0 + 120, B7YB - 200); ctx.restore();
    tag(ctx, '尾巴更厚', B7X0 + 260, B7YB + 60, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  // ── #15 肥尾 ──
  VIZ.calendar_circled = (ctx, s, lt, C) => { // 日历上标着「极少发生」的那一天，被圈了好几次
    const D = s.vizDur, x0 = 560, y0 = 360, cell = 115;
    b7cal(ctx, x0, y0, 7, 5, cell, '#fbf6ea', rgba(G.INK, 0.3), PAL.red.t[2]);
    const cx = x0 + cell * 4.5, cy = y0 + 70 + cell * 2.5; ctx.save(); ctx.font = F.zh(900, 26); ctx.fillStyle = G.INK; ctx.textAlign = 'center'; ctx.fillText('极少发生', cx, cy + 9); ctx.restore();
    for (let i = 0; i < 4; i++) b7rings(ctx, cx, cy, 62 + i * 9, PAL.red.t[2], 6, inv(D * 0.2 + i * 0.3, D * 0.2 + i * 0.3 + 0.5, lt), -0.2 + i * 0.15);
    tag(ctx, '又来了', 1600, 940, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.fat_title = (ctx, s, lt, C) => { // 屏幕标题「Fat Tails」，一条钟形曲线的尾巴明显变粗
    const D = s.vizDur, k = E.io(inv(D * 0.3, D * 0.9, lt)), fz = (u) => lerp(b7N(u), b7T(u), k);
    b6title(ctx, 'Fat Tails', W / 2, 420, 150, C.fg, inv(0.05, D * 0.4, lt));
    b7curve(ctx, 360, 1560, 960, 380, fz, 1, G.INK, 12, rgba(G.INK, 0.15));
  };
  VIZ.thin_bell = (ctx, s, lt, C) => { // 细尾巴的钟形曲线，两端几乎贴着地面
    const D = s.vizDur;
    ctx.fillStyle = rgba(G.INK, 0.5); ctx.fillRect(160, B7YB, 1600, 8);
    b7curve(ctx, B7X0, B7X1, B7YB, 520, b7N, inv(0.1, D * 0.6, lt), G.CREAM, 10, null, 3.6, 'center');
    [B7X0 + 90, B7X1 - 90].forEach((x, i) => b7rings(ctx, x, B7YB - 6, 60, G.INK, 5, inv(D * 0.5 + i * 0.2, D * 0.8 + i * 0.2, lt), 0));
    tag(ctx, '贴着地面', 1560, 420, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: PAL.green.t[3] });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.balls_ends = (ctx, s, lt, C) => { // 真实数据小球不断落在两端，越堆越高
    const D = s.vizDur;
    b7curve(ctx, B7X0, B7X1, B7YB, 520, b7N, 1, rgba(G.CREAM, 0.6), 8, null);
    ctx.fillStyle = rgba(C.fg, 0.4); ctx.fillRect(160, B7YB, 1600, 8);
    [[B7X0 + 40, 0], [B7X1 - 80, 1]].forEach(([bx, side]) => { const n = Math.round(8 * E.io(inv(0.1 + side * 0.2, D * 0.85, lt)));
      for (let j = 0; j < n; j++) for (let c = 0; c < 2; c++) G.disc(ctx, bx + c * 40 + (side ? 0 : 0), B7YB - 20 - j * 40, 18, side ? PAL.gold.t[2] : PAL.red.t[2]);
      const fy = lerp(330, B7YB - 20 - n * 40, b6fr(lt * 1.3 + side * 0.5)); G.disc(ctx, bx + 20, fy, 18, side ? PAL.gold.t[2] : PAL.red.t[2]); });
    tag(ctx, '两端越堆越高', W / 2, 400, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { x: 150, y: 220 });
  };
  VIZ.tails_overlay = (ctx, s, lt, C) => { // 两条曲线叠在一起：细尾虚线、粗尾实线
    const D = s.vizDur;
    ctx.save(); ctx.setLineDash([22, 18]); b7curve(ctx, B7X0, B7X1, B7YB, 520, b7N, inv(0.1, D * 0.5, lt), G.CREAM, 8, null); ctx.restore();
    b7curve(ctx, B7X0, B7X1, B7YB, 520, b7T, inv(D * 0.3, D * 0.8, lt), PAL.gold.t[2], 12, null);
    tag(ctx, '细尾', 1560, 440, C, inv(D * 0.3, D * 0.6, lt), { px: 34, bg: G.CREAM, fg: PAL.purple.t[3] });
    tag(ctx, '粗尾', 1560, 530, C, inv(D * 0.6, D * 0.9, lt), { px: 34, bg: PAL.gold.t[2], fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.left_tail_drag = (ctx, s, lt, C) => { // 左侧亏损尾巴朝左下方拖长、加粗，标「大跌」
    const D = s.vizDur, k = E.io(inv(D * 0.15, D * 0.8, lt)), n = 120, x0 = 760, x1 = 1620, yb = 760;
    ctx.fillStyle = rgba(G.INK, 0.4); ctx.fillRect(160, yb, 1600, 6);
    const pts = []; for (let i = 0; i <= n; i++) { const u = -3.6 + 7.2 * i / n; pts.push([lerp(x0, x1, i / n), yb - 420 * (u < 0 ? lerp(b7N(u), b7T(u), k) : b7N(u))]); }
    const tail = []; for (let i = 0; i <= 30; i++) { const f = i / 30; tail.push([lerp(x0, lerp(x0, 200, k), f), lerp(pts[0][1], pts[0][1] + 220 * k, f * f)]); }
    ctx.fillStyle = rgba(G.INK, 0.25); ctx.beginPath(); ctx.moveTo(x1, yb); pts.slice().reverse().forEach((p) => ctx.lineTo(p[0], p[1])); tail.forEach((p) => ctx.lineTo(p[0], p[1])); ctx.lineTo(tail[30][0], yb); ctx.closePath(); ctx.fill();
    ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = G.INK; ctx.lineWidth = 10; ctx.beginPath(); pts.forEach((p, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, p[0], p[1])); ctx.stroke();
    ctx.lineWidth = lerp(10, 34, k); ctx.strokeStyle = G.CREAM; ctx.beginPath(); tail.forEach((p, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, p[0], p[1])); ctx.stroke(); ctx.restore();
    tag(ctx, '大跌', lerp(x0, 320, k), yb - 90, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.CREAM, fg: PAL.red.t[3] });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.threshold_q = (ctx, s, lt, C) => { // 一条门槛竖线，线外左侧粗尾区域被打上问号
    const D = s.vizDur, tx = 640;
    b7curve(ctx, B7X0, B7X1, B7YB, 520, b7T, 1, G.INK, 10, rgba(G.INK, 0.12));
    const ap = inv(D * 0.4, D * 0.7, lt); if (ap > 0) b7area(ctx, B7X0, B7X1, B7YB, 520, b7T, B7X0, tx, rgba(PAL.red.t[2], 0.8 * clamp(ap)));
    const lp = E.io(inv(0.1, D * 0.4, lt)); ctx.fillStyle = G.INK; ctx.fillRect(tx - 5, lerp(B7YB, 380, lp), 10, (B7YB - 380) * lp);
    tag(ctx, '门槛', tx, 360, C, lp, { px: 34, bg: G.INK, fg: C.bg });
    ctx.save(); ctx.font = F.en(900, 140); ctx.fillStyle = rgba(G.INK, clamp(inv(D * 0.55, D * 0.85, lt))); ctx.textAlign = 'center'; ctx.fillText('?', 440, 780); ctx.restore();
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.tail_zoom = (ctx, s, lt, C) => { // 镜头推进到门槛线外那块粗尾区域，颜色加深
    const D = s.vizDur, z = lerp(1, 2.6, E.io(inv(0, D * 0.7, lt))), tx = 640, dk = inv(D * 0.4, D * 0.9, lt);
    ctx.save(); ctx.translate(480, 860); ctx.scale(z, z); ctx.translate(-480, -860);
    b7curve(ctx, B7X0, B7X1, B7YB, 520, b7T, 1, G.INK, 8, rgba(G.INK, 0.08));
    b7area(ctx, B7X0, B7X1, B7YB, 520, b7T, B7X0, tx, mix ? mix(PAL.red.t[1], PAL.red.t[4] || PAL.red.deep, clamp(dk)) : PAL.red.t[3]);
    ctx.fillStyle = G.INK; ctx.fillRect(tx - 4, 380, 8, B7YB - 380); ctx.restore();
    tag(ctx, '藏在门槛外', 1500, 940, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.wall_push = (ctx, s, lt, C) => { // 一面写着「LTCM」的墙被一只从尾部伸出的手推倒
    const D = s.vizDur, gy = 960, wx = 1180, k = E.i3(inv(D * 0.35, D * 0.9, lt)), a = k * 1.2;
    b7curve(ctx, 140, 900, gy, 260, b7T, 1, G.CREAM, 8, rgba(G.CREAM, 0.15), 3.6);
    const hp = E.io(inv(0.1, D * 0.4, lt)); b7hand(ctx, lerp(300, 880, hp), gy - 150, 120, G.CREAM, Math.PI / 2);
    ctx.save(); ctx.translate(wx + 160, gy); ctx.rotate(a); ctx.fillStyle = '#b9a58a'; ctx.fillRect(-160, -520, 160, 520);
    ctx.fillStyle = rgba(G.INK, 0.25); for (let r = 0; r < 10; r++) ctx.fillRect(-160, -520 + r * 52, 160, 4);
    ctx.save(); ctx.translate(-80, -260); ctx.rotate(-Math.PI / 2); ctx.font = F.en(900, 90); ctx.fillStyle = G.INK; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('LTCM', 0, 4); ctx.restore(); ctx.restore();
    vizCaption(ctx, s, lt, C, { x: 1770, y: 250, align: 'right' });
  };
  VIZ.calc_crack = (ctx, s, lt, C) => { // 计算器上「安全」两个字被一道裂缝划开
    const D = s.vizDur, cx = 1100, cy = 640, [sx, sy] = b7calc(ctx, cx, cy, 560, 700, G.INK, '#cfe3d4', rgba(G.CREAM, 0.6));
    G.maskText(ctx, '安全', sx, sy + 34, F.zh(900, 96), PAL.green.t[3], inv(0.1, D * 0.35, lt), { align: 'center', ls: '10px' });
    const k = inv(D * 0.4, D * 0.85, lt); if (k > 0) { const pts = [[sx - 220, sy - 80], [sx - 120, sy - 10], [sx - 40, sy - 60], [sx + 30, sy + 40], [sx + 120, sy - 20], [sx + 220, sy + 90]], m = Math.max(1, Math.ceil(5 * k));
      ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 10; ctx.lineJoin = 'round'; ctx.beginPath(); pts.slice(0, m + 1).forEach((p, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, p[0], p[1])); ctx.stroke(); ctx.restore(); }
    tag(ctx, '不代表真安全', 540, 640, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.calendar_two = (ctx, s, lt, C) => { // 回到日历：圈了好几次的那一天，旁边并排两条曲线，细尾和粗尾
    const D = s.vizDur, x0 = 300, y0 = 420, cell = 90;
    b7cal(ctx, x0, y0, 7, 5, cell, '#fbf6ea', rgba(G.INK, 0.3), PAL.red.t[2]);
    const cx = x0 + cell * 4.5, cy = y0 + 70 + cell * 2.5; for (let i = 0; i < 3; i++) b7rings(ctx, cx, cy, 46 + i * 8, PAL.red.t[2], 5, 1, -0.2 + i * 0.15);
    const p1 = inv(D * 0.2, D * 0.6, lt), p2 = inv(D * 0.4, D * 0.8, lt);
    ctx.save(); ctx.setLineDash([16, 12]); b7curve(ctx, 1060, 1760, 600, 220, b7N, p1, G.CREAM, 8, null); ctx.restore();
    b7curve(ctx, 1060, 1760, 900, 220, b7T, p2, PAL.gold.t[2], 10, null);
    tag(ctx, '细尾', 1410, 650, C, p1, { px: 30, bg: G.CREAM, fg: G.INK }); tag(ctx, '粗尾', 1410, 950, C, p2, { px: 30, bg: PAL.gold.t[2], fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  // ───────── finance-v003 scene library, batch 8 (quant basics: volatility / correlation / covariance / regression / hypothesis tests, 2026-10-30) ─────────
  // #16 波动率 · #17 相关性 · #18 协方差 · #19 线性回归 · #20 假设检验 — 60 scenes, one per line.
  // 金融专家 rules: swings drawn up AND down (size, not direction), losses go DOWN, no formulas on screen (only the words
  // 「p 值」 and 「β（贝塔）」 as labels), no tickers or chart candles, the backtest is a fictional strategy with no profit implied.
  Object.assign(VPAL, {
    vol_boat: 'ochre', vol_title: 'purple', vol_band: 'cream', vol_devs: 'ink', vol_ab: 'green', vol_scale: 'gold',
    vol_dblarrow: 'red', vol_ruler: 'cream', vol_end: 'purple', vol_fog: 'ink', vol_boat_end: 'green',
    corr_walkers: 'cream', corr_title: 'purple', corr_together: 'ink', corr_ruler: 'gold', corr_plus1: 'green', corr_minus1: 'red',
    corr_zero: 'cream', corr_queues: 'ochre', corr_sun: 'gold', corr_nocause: 'ink', corr_slide: 'red', corr_balloons: 'purple', corr_downhill: 'green',
    cov_machine: 'ink', cov_title: 'gold', cov_bracket: 'cream', cov_signs: 'purple', cov_units: 'ochre', cov_cards_big: 'green',
    cov_wobble: 'red', cov_card_out: 'cream', cov_cards_ruler: 'ink', cov_machine_end: 'purple',
    reg_scatter: 'ink', reg_title: 'green', reg_candidates: 'cream', reg_xaxis: 'purple', reg_yaxis: 'ochre', reg_dots_fill: 'ink',
    reg_slope: 'gold', reg_beta: 'red', reg_step15: 'cream', reg_oldphoto: 'ochre', reg_fog: 'ink', reg_summary: 'purple',
    hyp_scale: 'cream', hyp_title: 'purple', hyp_backtest: 'ink', hyp_coin: 'gold', hyp_hill: 'green', hyp_pval: 'ink', hyp_scale_glow: 'ochre',
    hyp_tail_shade: 'cream', hyp_two_cards: 'purple', hyp_warn: 'red', hyp_lift: 'green', hyp_dashed: 'cream', hyp_fog: 'ink', hyp_end: 'gold',
  });
  const b8ser = (n, seed, amp, f = 1) => Array.from({ length: n }, (_, i) => amp * (0.6 * Math.sin(i * 0.55 * f + seed) + 0.4 * Math.sin(i * 1.37 * f + seed * 2.1)));
  function b8plot(ctx, ys, x0, x1, yc, col, w, p = 1, dash) { // ys = px offsets, + = up; returns head [x, y]
    const n = ys.length, k = clamp(p) * (n - 1); let hx = x0, hy = yc - ys[0];
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; if (dash) ctx.setLineDash(dash);
    ctx.beginPath();
    for (let i = 0; i <= Math.ceil(k) && i < n; i++) { const f = Math.min(i, k), a = ys[Math.floor(f)], b = ys[Math.min(n - 1, Math.floor(f) + 1)];
      const x = lerp(x0, x1, f / (n - 1)), y = yc - lerp(a, b, f - Math.floor(f)); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); hx = x; hy = y; }
    ctx.stroke(); ctx.restore(); return [hx, hy];
  }
  function b8dash(ctx, x0, y0, x1, y1, col, w = 5, d = [18, 14]) { ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.setLineDash(d); ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); ctx.restore(); }
  function b8txt(ctx, t, x, y, px, col, o = {}) { ctx.save(); ctx.font = o.en ? F.en(o.w || 900, px) : F.zh(o.w || 900, px); ctx.fillStyle = col; ctx.textAlign = o.align || 'center'; ctx.textBaseline = 'middle'; ctx.globalAlpha = o.a ?? 1; ctx.fillText(t, x, y); ctx.restore(); }
  function b8check(ctx, x, y, s, col, p = 1) { if (p <= 0) return; ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = s * 0.22; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.beginPath(); ctx.moveTo(x - s * 0.5, y); ctx.lineTo(x - s * 0.12, y + s * 0.4 * clamp(p * 2)); if (p > 0.5) ctx.lineTo(x - s * 0.12 + s * 0.7 * (p - 0.5) * 2, y + s * 0.4 - s * 0.85 * (p - 0.5) * 2); ctx.stroke(); ctx.restore(); }
  function b8cross(ctx, x, y, s, col, p = 1) { if (p <= 0) return; ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = s * 0.22; ctx.lineCap = 'round'; const a = clamp(p * 2), b = clamp(p * 2 - 1);
    ctx.beginPath(); ctx.moveTo(x - s / 2, y - s / 2); ctx.lineTo(x - s / 2 + s * a, y - s / 2 + s * a); if (b > 0) { ctx.moveTo(x + s / 2, y - s / 2); ctx.lineTo(x + s / 2 - s * b, y - s / 2 + s * b); } ctx.stroke(); ctx.restore(); }
  function b8fog(ctx, x, y, rx, ry, col, a, lt, n = 16) { ctx.save(); for (let i = 0; i < n; i++) { const u = b6rnd(i, 21), v = b6rnd(i, 22); ctx.globalAlpha = a * (0.5 + 0.5 * b6rnd(i, 23));
      G.disc(ctx, x + (u - 0.5) * rx * 2 + 18 * Math.sin(lt * 0.8 + i), y + (v - 0.5) * ry * 2, (0.35 + 0.4 * b6rnd(i, 24)) * Math.min(rx, ry * 1.6), col); } ctx.restore(); }
  function b8gauge(ctx, x0, x1, y, v, C, p = 1, o = {}) { // ruler −1 … 0 … 1 with a pointer at v
    ctx.fillStyle = o.bar || C.fg; ctx.fillRect(x0, y - 8, x1 - x0, 16);
    for (let i = 0; i <= 20; i++) { const x = lerp(x0, x1, i / 20), big = i % 10 === 0; ctx.fillRect(x - 3, y - (big ? 46 : 26), 6, big ? 46 : 26); }
    [['-1', 0], ['0', 0.5], ['1', 1]].forEach(([t, f]) => b8txt(ctx, t, lerp(x0, x1, f), y + 62, o.px || 52, o.bar || C.fg, { en: 1 }));
    if (p <= 0) return; const px = lerp(x0, x1, (clamp(v, -1, 1) + 1) / 2);
    ctx.save(); ctx.globalAlpha = clamp(p * 2); G.poly(ctx, [[px, y - 30], [px - 34, y - 100], [px + 34, y - 100]], o.ptr || C.acc); ctx.fillStyle = o.ptr || C.acc; ctx.fillRect(px - 5, y - 150, 10, 60); ctx.restore();
    return px;
  }
  function b8bal(ctx, x, y, s, tilt, col, pan) { // balance: post at x, beam centre y; tilt > 0 = LEFT pan down; pan(ctx, side, px, py) draws on each pan
    ctx.fillStyle = col; ctx.fillRect(x - 10, y, 20, s * 0.95); ctx.fillRect(x - s * 0.32, y + s * 0.95, s * 0.64, 20); G.poly(ctx, [[x, y - 34], [x - 26, y + 10], [x + 26, y + 10]], col);
    const a = -tilt * 0.32, dx = Math.cos(a) * s, dy = Math.sin(a) * s;
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 16; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x - dx, y + dy); ctx.lineTo(x + dx, y - dy); ctx.stroke(); ctx.restore();
    [[-1, x - dx, y + dy], [1, x + dx, y - dy]].forEach(([sd, px, py]) => {
      ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px - s * 0.3, py + s * 0.42); ctx.moveTo(px, py); ctx.lineTo(px + s * 0.3, py + s * 0.42); ctx.stroke(); ctx.restore();
      ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(px, py + s * 0.44, s * 0.36, s * 0.07, 0, 0, Math.PI * 2); ctx.fill();
      if (pan) pan(ctx, sd, px, py + s * 0.44);
    });
  }
  function b8card(ctx, x, y, w, h, bg, fg, txt, px, o = {}) { // label card, (x,y) = centre
    ctx.save(); ctx.translate(x, y); ctx.rotate(o.rot || 0); const sc = o.sc ?? 1; ctx.scale(sc, sc);
    if (o.dash) { ctx.strokeStyle = bg; ctx.lineWidth = 8; ctx.setLineDash([22, 16]); ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 22); ctx.stroke(); }
    else { ctx.fillStyle = bg; ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 22); ctx.fill(); }
    if (txt) { ctx.font = o.en ? F.en(900, px) : F.zh(900, px); ctx.fillStyle = o.dash ? bg : fg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(txt, 0, 4); }
    ctx.restore();
  }
  function b8corner(ctx, t, C, p, x = 1690, y = 150) { tag(ctx, t, x, y, C, p, { px: 34, bg: C.fg, fg: C.bg }); } // 「假设」 corner badge
  function b8machine(ctx, x, y, col, win, gearRot = 0, glow = 0) { // processing box, (x,y) = centre; hopper on the left, slot on the right
    ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(x - 250, y - 170, 500, 340, 34); ctx.fill();
    G.poly(ctx, [[x - 420, y - 250], [x - 230, y - 250], [x - 250, y - 60], [x - 330, y - 60]], col);
    if (glow > 0) { ctx.save(); ctx.globalAlpha = 0.45 * clamp(glow); G.poly(ctx, [[x - 440, y - 270], [x - 210, y - 270], [x - 240, y - 40], [x - 340, y - 40]], PAL.gold.t[2]); ctx.restore(); }
    ctx.fillStyle = win; ctx.fillRect(x + 250, y + 40, 40, 110); b6gear(ctx, x - 60, y - 10, 70, 9, gearRot, win, col); b6gear(ctx, x + 90, y + 40, 46, 7, -gearRot * 1.4, win, col);
    ctx.fillStyle = win; ctx.fillRect(x - 200, y - 140, 120, 18);
  }
  function b8axes(ctx, ox, oy, x0, x1, y0, y1, col, w = 6) { // cross axes through (ox, oy), arrows at x1 / y0
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(x0, oy); ctx.lineTo(x1, oy); ctx.moveTo(ox, y1); ctx.lineTo(ox, y0); ctx.stroke(); ctx.restore();
    G.poly(ctx, [[x1 + 30, oy], [x1, oy - 16], [x1, oy + 16]], col); G.poly(ctx, [[ox, y0 - 30], [ox - 16, y0], [ox + 16, y0]], col);
  }
  const b8pts = (n, seed, slope, sd) => Array.from({ length: n }, (_, i) => { const u = (b6rnd(i, seed) - 0.5) * 2; const e = (b6rnd(i, seed + 1) + b6rnd(i, seed + 2) + b6rnd(i, seed + 3) - 1.5) * sd; return [u, slope * u + e]; });
  function b8sun(ctx, x, y, r, col, lt, p = 1) { if (p <= 0) return; const k = E.oBack(clamp(p)); ctx.save(); ctx.translate(x, y); ctx.scale(k, k); ctx.rotate(lt * 0.3);
    ctx.fillStyle = col; for (let i = 0; i < 12; i++) { ctx.rotate(Math.PI / 6); ctx.fillRect(r * 1.2, -10, r * 0.45, 20); } ctx.restore(); G.disc(ctx, x, y, r * k, col); }
  function b8counter(ctx, x, y, w, col, sign, signFg, label, n, figCol, lt) { // shop counter seen from the front, y = floor; queue of n people on the left
    ctx.fillStyle = col; ctx.fillRect(x - w / 2, y - 220, w, 220); ctx.fillRect(x - w / 2 - 20, y - 240, w + 40, 26);
    ctx.fillStyle = sign; ctx.beginPath(); ctx.roundRect(x - w / 2, y - 400, w, 100, 18); ctx.fill(); b8txt(ctx, label, x, y - 348, 52, signFg);
    for (let i = 0; i < n; i++) b6person(ctx, x - w / 2 - 50 - i * 72, y, 150, figCol, { head: 4 * Math.sin(lt * 3 + i) });
  }
  // ── #16 波动率 ── (swings drawn both up and down; size only, never direction)
  VIZ.vol_boat = (ctx, s, lt, C) => { // 一艘小船在浪里大起大落，船上的人坐得稳稳的
    const D = s.vizDur, k = inv(0, D * 0.3, lt), bob = 110 * k * Math.sin(lt * 2.2), tilt = 0.16 * k * Math.sin(lt * 2.2 + 0.6);
    b6sea(ctx, 800 + bob * 0.4, 90 * k + 20, lt, rgba(C.fg, 0.25), 1.2, 0.005);
    ctx.save(); ctx.translate(980, 760 + bob); ctx.rotate(tilt); b6boat(ctx, 0, 0, 460, C.fg, 0);
    ctx.restore(); ctx.save(); ctx.translate(980, 760 + bob); ctx.rotate(tilt * 0.3); b6person(ctx, -110, -28, 210, G.CREAM, { aL1: 20, aR1: -20 }); ctx.restore();
    b6sea(ctx, 860 + bob * 0.6, 70 * k + 16, lt, C.fg, 0, 0.006);
    tag(ctx, '晃得多', 1540, 430, C, inv(D * 0.3, D * 0.6, lt), { px: 38, bg: C.fg, fg: C.bg });
    tag(ctx, '人坐得稳', 1540, 520, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_title = (ctx, s, lt, C) => { // 屏幕标题「Volatility」，下方一条上下起伏的线
    const D = s.vizDur; b6title(ctx, 'Volatility', W / 2, 430, 130, C.fg, inv(0.05, D * 0.5, lt));
    ctx.fillStyle = rgba(C.fg, 0.3); ctx.fillRect(300, 760, 1320, 4);
    b8plot(ctx, b8ser(40, 0.4, 150, 1.1), 300, 1620, 760, C.acc, 12, inv(D * 0.2, D * 0.9, lt));
  };
  VIZ.vol_band = (ctx, s, lt, C) => { // 线的起伏被上下两条虚线框住，标「晃动幅度」
    const D = s.vizDur, yc = 680, A = 170, ys = b8ser(44, 1.3, A * 0.9, 1);
    b8plot(ctx, ys, 260, 1500, yc, G.INK, 12, inv(0.1, D * 0.6, lt));
    const bp = inv(D * 0.45, D * 0.75, lt); if (bp > 0) { ctx.save(); ctx.globalAlpha = clamp(bp); b8dash(ctx, 240, yc - A, 1520, yc - A, C.acc, 7); b8dash(ctx, 240, yc + A, 1520, yc + A, C.acc, 7); ctx.restore(); }
    arrowV(ctx, 1600, yc - A, yc + A, C.acc, 8, bp);
    tag(ctx, '晃动幅度', 1600, yc + A + 90, C, inv(D * 0.6, D * 0.9, lt), { px: 40, bg: C.acc, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_devs = (ctx, s, lt, C) => { // 一条平均线，各个点到平均线拉出长短不一的竖线
    const D = s.vizDur, ym = 690, ys = b8ser(15, 2.2, 210, 2.1);
    ctx.fillStyle = C.fg; ctx.fillRect(260, ym - 4, 1400, 8); b8txt(ctx, '平均', 1720, ym, 40, C.fg);
    ys.forEach((v, i) => { const x = lerp(320, 1600, i / 14), p = inv(D * 0.15 + i * 0.08, D * 0.35 + i * 0.08, lt); if (p <= 0) return;
      ctx.fillStyle = v > 0 ? PAL.green.t[2] : PAL.red.t[2]; ctx.fillRect(x - 5, Math.min(ym, ym - v * p), 10, Math.abs(v * p)); G.disc(ctx, x, ym - v * p, 16, C.acc); });
    tag(ctx, '离平均多远', 1440, 420, C, inv(D * 0.6, D * 0.9, lt), { px: 40, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_ab = (ctx, s, lt, C) => { // 两条线：甲贴着平线微动，乙上下大幅摆动，角标「假设」
    const D = s.vizDur, p = inv(0.1, D * 0.7, lt);
    b8dash(ctx, 330, 520, 1640, 520, rgba(C.fg, 0.35), 3); b8dash(ctx, 330, 800, 1640, 800, rgba(C.fg, 0.35), 3);
    b8plot(ctx, b8ser(44, 0.9, 22, 1), 330, 1640, 520, C.fg, 10, p); b8plot(ctx, b8ser(44, 0.9, 175, 1), 330, 1640, 800, G.INK, 12, p);
    tag(ctx, '甲', 230, 520, C, inv(0.1, 0.6, lt), { px: 44, bg: C.fg, fg: C.bg }); tag(ctx, '乙', 230, 800, C, inv(0.3, 0.8, lt), { px: 44, bg: G.INK, fg: C.bg });
    b8corner(ctx, '假设', C, inv(0.2, 0.7, lt)); vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_scale = (ctx, s, lt, C) => { // 乙那条线旁的刻度条更长
    const D = s.vizDur, yb = 940, g = E.o3(inv(D * 0.15, D * 0.6, lt));
    [[820, 110, '甲', C.fg], [1180, 520, '乙', G.INK]].forEach(([x, h, t, col]) => {
      ctx.fillStyle = rgba(col, 0.18); ctx.fillRect(x - 70, yb - 560, 140, 560);
      ctx.fillStyle = col; ctx.fillRect(x - 70, yb - h * g, 140, h * g); for (let j = 1; j < 12; j++) ctx.fillRect(x + 76, yb - j * 46, j % 2 ? 18 : 34, 5);
      b8txt(ctx, t, x, yb + 52, 48, col); });
    tag(ctx, '波动率更高', 1180, yb - 600, C, inv(D * 0.55, D * 0.85, lt), { px: 40, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_dblarrow = (ctx, s, lt, C) => { // 一个上下双箭头，上下两端一样长
    const D = s.vizDur, yc = 660, L = 280 * E.o3(inv(0.1, D * 0.5, lt));
    ctx.fillStyle = rgba(C.fg, 0.4); ctx.fillRect(560, yc - 3, 800, 6);
    if (L > 10) arrowV(ctx, 960, yc - L, yc + L, C.fg, 14, 1);
    tag(ctx, '往上晃', 1240, yc - 200, C, inv(D * 0.4, D * 0.7, lt), { px: 38, bg: C.fg, fg: C.bg }); tag(ctx, '往下晃', 1240, yc + 200, C, inv(D * 0.45, D * 0.75, lt), { px: 38, bg: C.fg, fg: C.bg });
    tag(ctx, '一样长', 680, yc + 120, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.INK, fg: C.fg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_ruler = (ctx, s, lt, C) => { // 往上的点和往下的点都被同一把尺子量
    const D = s.vizDur, ym = 680, ys = [180, -150, 90, -220, 130, -60, 200, -170];
    ctx.fillStyle = rgba(G.INK, 0.6); ctx.fillRect(300, ym - 3, 1320, 6);
    const rx = lerp(300, 1620, inv(D * 0.15, D * 0.85, lt));
    ys.forEach((v, i) => { const x = lerp(400, 1520, i / 7), col = v > 0 ? PAL.green.t[3] : PAL.red.t[2]; G.disc(ctx, x, ym - v, 20, col);
      if (x < rx) { ctx.fillStyle = rgba(col, 0.8); ctx.fillRect(x - 3, Math.min(ym, ym - v), 6, Math.abs(v)); } });
    ctx.save(); ctx.globalAlpha = 0.9; ctx.fillStyle = PAL.gold.t[2]; ctx.fillRect(rx - 28, ym - 300, 56, 600); ctx.fillStyle = G.INK;
    for (let j = 0; j <= 20; j++) ctx.fillRect(rx - 28, ym - 300 + j * 30, j % 5 ? 16 : 30, 4); ctx.restore();
    tag(ctx, '都算进去', 1560, 400, C, inv(D * 0.6, D * 0.9, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_end = (ctx, s, lt, C) => { // 乙那条线晃得厉害，终点没有往下掉
    const D = s.vizDur, yc = 690, raw = b8ser(46, 0.9, 200, 1), ys = raw.map((v, i) => v - raw[45] * i / 45);
    b8dash(ctx, 300, yc, 1640, yc, rgba(C.fg, 0.45), 4);
    const [hx, hy] = b8plot(ctx, ys, 300, 1580, yc, G.CREAM, 12, inv(0.1, D * 0.7, lt)); G.disc(ctx, hx, hy, 22, C.acc);
    tag(ctx, '终点没往下掉', 1500, 420, C, inv(D * 0.65, D * 0.92, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_fog = (ctx, s, lt, C) => { // 前方的路被一团雾盖住，雾的范围随晃动变大
    const D = s.vizDur, g = inv(0, D * 0.9, lt);
    G.poly(ctx, [[520, 1080], [1400, 1080], [1000, 560], [920, 560]], rgba(G.CREAM, 0.22));
    for (let i = 0; i < 6; i++) { const f = b6fr(i / 6 + lt * 0.25), y = lerp(570, 1080, f * f); ctx.fillStyle = rgba(G.CREAM, 0.6); ctx.fillRect(960 - 6 - f * 14, y, 12 + f * 28, 20 + f * 40); }
    b8fog(ctx, 960, 560, 260 + 420 * g, 120 + 160 * g, G.CREAM, 0.55, lt, 22);
    tag(ctx, '难预料', 1540, 420, C, inv(D * 0.5, D * 0.85, lt), { px: 40, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.vol_boat_end = (ctx, s, lt, C) => { // 回到开头的小船，镜头停在船上的人身上
    const D = s.vizDur, z = lerp(1, 1.45, E.io(inv(0, D * 0.7, lt))), bob = 70 * Math.sin(lt * 2.2);
    ctx.save(); ctx.translate(960, 640); ctx.scale(z, z); ctx.translate(-960, -640);
    b6sea(ctx, 830 + bob * 0.4, 60, lt, rgba(C.fg, 0.25), 1.2, 0.005);
    ctx.save(); ctx.translate(960, 790 + bob); ctx.rotate(0.12 * Math.sin(lt * 2.2 + 0.6)); b6boat(ctx, 0, 0, 440, C.fg, 0); ctx.restore();
    b6person(ctx, 860, 762 + bob, 220, G.CREAM, { aL1: 20, aR1: -20 }); b6sea(ctx, 880 + bob * 0.6, 50, lt, C.fg, 0, 0.006); ctx.restore();
    tag(ctx, '坐得住吗？', 1520, 430, C, inv(D * 0.45, D * 0.8, lt), { px: 42, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  // ── #17 相关性 ── (a number from −1 to 1; correlation ≠ causation; in a crisis the lines bunch and go DOWN together)
  const b8walk = (lt, ph = 0, a = 24) => ({ lL1: a * Math.sin(lt * 6 + ph), lR1: -a * Math.sin(lt * 6 + ph), aL1: -16 * Math.sin(lt * 6 + ph), aR1: 16 * Math.sin(lt * 6 + ph) });
  VIZ.corr_walkers = (ctx, s, lt, C) => { // 两个小人并排同步走路，中间画着一个问号
    const D = s.vizDur, x = 760 + 60 * Math.sin(lt * 0.6);
    ctx.fillStyle = rgba(G.INK, 0.5); ctx.fillRect(200, 960, 1520, 6);
    b6person(ctx, x, 960, 380, G.INK, b8walk(lt)); b6person(ctx, x + 440, 960, 380, PAL.purple.t[2], b8walk(lt));
    const q = pop(lt, D * 0.3, D * 0.6); if (q > 0) { ctx.save(); ctx.translate(x + 220, 520); ctx.scale(q, q); b8txt(ctx, '?', 0, 0, 200, C.acc, { en: 1 }); ctx.restore(); }
    tag(ctx, '谁带谁？', 1560, 420, C, inv(D * 0.55, D * 0.85, lt), { px: 40, bg: C.acc, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_title = (ctx, s, lt, C) => { // 屏幕标题「Correlation」，两条线并排起伏
    const D = s.vizDur, ys = b8ser(40, 2.0, 90, 1.1), p = inv(D * 0.2, D * 0.9, lt);
    b6title(ctx, 'Correlation', W / 2, 420, 130, C.fg, inv(0.05, D * 0.5, lt));
    b8plot(ctx, ys, 300, 1620, 700, C.fg, 10, p); b8plot(ctx, ys.map((v) => v * 0.8), 300, 1620, 880, PAL.gold.t[2], 10, p);
  };
  VIZ.corr_together = (ctx, s, lt, C) => { // 两条线同时上、同时下
    const D = s.vizDur, ys = b8ser(40, 0.7, 130, 1.2), p = inv(0.1, D * 0.75, lt);
    [8, 19, 30].forEach((i, j) => { if (p * 39 > i) b8dash(ctx, lerp(300, 1620, i / 39), 400, lerp(300, 1620, i / 39), 1000, rgba(G.CREAM, 0.3), 3); });
    b8plot(ctx, ys, 300, 1620, 560, PAL.gold.t[2], 11, p); b8plot(ctx, ys.map((v) => v * 0.9), 300, 1620, 840, G.CREAM, 11, p);
    tag(ctx, '同时上', 1560, 380, C, inv(D * 0.45, D * 0.7, lt), { px: 36, bg: PAL.gold.t[2], fg: G.INK }); tag(ctx, '同时下', 1560, 1000, C, inv(D * 0.55, D * 0.8, lt), { px: 36, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_ruler = (ctx, s, lt, C) => { // 一根刻度尺，左端「-1」，中间「0」，右端「1」
    const D = s.vizDur, v = Math.sin(inv(D * 0.2, D * 0.95, lt) * Math.PI * 1.5) ;
    b8gauge(ctx, 360, 1560, 720, inv(D * 0.2, D * 0.95, lt) > 0 ? v : 0, C, inv(0.2, 0.7, lt), { bar: G.INK, ptr: G.CREAM, px: 64 });
    tag(ctx, '负一到一之间', 960, 940, C, inv(D * 0.4, D * 0.75, lt), { px: 40, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_plus1 = (ctx, s, lt, C) => { // 指针指向右端，两条线完全同步
    const D = s.vizDur, ys = b8ser(36, 1.6, 90, 1.2), p = inv(D * 0.2, D * 0.85, lt);
    b8gauge(ctx, 900, 1640, 440, lerp(0, 1, E.o3(inv(0.1, D * 0.4, lt))), C, 1, { bar: C.fg, ptr: PAL.gold.t[2], px: 44 });
    b8plot(ctx, ys, 300, 1620, 720, C.fg, 11, p); b8plot(ctx, ys, 300, 1620, 900, G.INK, 11, p);
    tag(ctx, '同涨同跌', 520, 470, C, inv(D * 0.5, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.fg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_minus1 = (ctx, s, lt, C) => { // 指针指向左端，两条线一上一下像跷跷板
    const D = s.vizDur, ys = b8ser(36, 0.3, 90, 1.2), p = inv(D * 0.2, D * 0.85, lt), r = 0.18 * Math.sin(lt * 2.4);
    b8gauge(ctx, 900, 1640, 440, lerp(0, -1, E.o3(inv(0.1, D * 0.4, lt))), C, 1, { bar: C.fg, ptr: G.INK, px: 44 });
    b8plot(ctx, ys, 300, 1300, 720, C.fg, 11, p); b8plot(ctx, ys.map((v) => -v), 300, 1300, 900, G.INK, 11, p);
    ctx.save(); ctx.translate(1530, 860); G.poly(ctx, [[0, 0], [-50, 90], [50, 90]], G.INK); ctx.rotate(r); ctx.fillStyle = C.fg; ctx.fillRect(-200, -16, 400, 22);
    G.disc(ctx, -170, -50, 30, C.fg); G.disc(ctx, 170, -50, 30, G.INK); ctx.restore();
    tag(ctx, '你涨我跌', 520, 470, C, inv(D * 0.5, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.fg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_zero = (ctx, s, lt, C) => { // 指针在中间，两条线各走各的
    const D = s.vizDur, p = inv(D * 0.2, D * 0.85, lt);
    b8gauge(ctx, 900, 1640, 440, 0.4 * Math.sin(lt * 3) * (1 - E.o3(inv(0.1, D * 0.5, lt))), C, 1, { bar: G.INK, ptr: C.acc, px: 44 });
    b8plot(ctx, b8ser(36, 0.3, 90, 1.2), 300, 1620, 720, G.INK, 11, p); b8plot(ctx, b8ser(36, 4.1, 90, 0.7), 300, 1620, 900, PAL.purple.t[2], 11, p);
    tag(ctx, '各走各的', 520, 470, C, inv(D * 0.5, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  function b8shops(ctx, lt, C, n, y = 960) { // ice-cream counter + air-conditioner counter, each with a queue
    b8counter(ctx, 820, y, 300, G.CREAM, PAL.purple.t[2], G.CREAM, '冰淇淋', n, G.INK, lt);
    b8counter(ctx, 1500, y, 300, G.CREAM, PAL.green.t[3], G.CREAM, '空调', n, G.INK, lt);
    ctx.fillStyle = rgba(G.INK, 0.4); ctx.fillRect(140, y, 1640, 6);
  }
  VIZ.corr_queues = (ctx, s, lt, C) => { // 冰淇淋柜和空调柜台前都排着长队，角标「假设」
    const D = s.vizDur; b8shops(ctx, lt, C, Math.min(4, Math.floor(inv(0, D * 0.6, lt) * 5)));
    b8corner(ctx, '假设', C, inv(0.2, 0.7, lt)); vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_sun = (ctx, s, lt, C) => { // 镜头上移，一个大太阳同时照着两个柜台
    const D = s.vizDur, up = E.io(inv(0, D * 0.5, lt)); ctx.save(); ctx.translate(0, 160 * up); b8shops(ctx, lt, C, 3, 900); ctx.restore();
    b8sun(ctx, 1160, 300, 90, G.CREAM, lt, inv(D * 0.2, D * 0.55, lt));
    const rp = inv(D * 0.45, D * 0.8, lt); if (rp > 0) { ctx.save(); ctx.globalAlpha = 0.5 * rp; b8dash(ctx, 1110, 420, 860, 640, G.CREAM, 6); b8dash(ctx, 1210, 420, 1480, 640, G.CREAM, 6); ctx.restore(); }
    tag(ctx, '因为天热', 1580, 260, C, inv(D * 0.55, D * 0.85, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_nocause = (ctx, s, lt, C) => { // 两个柜台之间画一条虚线，被打了个叉
    const D = s.vizDur; b8shops(ctx, lt, C, 0, 960);
    const dp = inv(D * 0.1, D * 0.45, lt); if (dp > 0) b8dash(ctx, 980, 600, lerp(980, 1340, dp), 600, PAL.gold.t[2], 8);
    b8cross(ctx, 1160, 600, 110, PAL.red.t[2], inv(D * 0.45, D * 0.7, lt));
    tag(ctx, '相关 ≠ 因果', 1160, 430, C, inv(D * 0.6, D * 0.9, lt), { px: 40, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_slide = (ctx, s, lt, C) => { // 刻度尺上的指针一下子往右端滑
    const D = s.vizDur, k = E.o3(inv(D * 0.3, D * 0.45, lt)), [sx, sy] = shake(lt, D * 0.38, 10);
    ctx.save(); ctx.translate(sx, sy); b8gauge(ctx, 360, 1560, 720, lerp(0.15, 0.92, k), C, 1, { bar: C.fg, ptr: G.INK, px: 64 }); ctx.restore();
    tag(ctx, '危机一来', 600, 470, C, inv(D * 0.2, D * 0.4, lt), { px: 40, bg: G.INK, fg: C.fg }); tag(ctx, '相关性变高', 1360, 940, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_balloons = (ctx, s, lt, C) => { // 几只原本各自漂着的小气球，被同一阵下沉气流一起压低
    const D = s.vizDur, k = E.io(inv(D * 0.3, D * 0.75, lt)), cols = [G.CREAM, PAL.gold.t[2], PAL.green.t[1], PAL.red.t[1], PAL.ochre.t[3]];
    const fx = [560, 820, 1080, 1340, 1560], fy = [520, 640, 470, 600, 540];
    const air = inv(D * 0.2, D * 0.5, lt); if (air > 0) { ctx.save(); ctx.globalAlpha = 0.35 * clamp(air); ctx.strokeStyle = G.CREAM; ctx.lineWidth = 8; ctx.lineCap = 'round';
      for (let i = 0; i < 6; i++) { const x = 480 + i * 230, y0 = 380 + b6fr(lt * 0.6 + i * 0.37) * 420; ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y0 + 120); ctx.stroke();
        G.poly(ctx, [[x, y0 + 150], [x - 18, y0 + 118], [x + 18, y0 + 118]], G.CREAM); } ctx.restore(); }
    cols.forEach((col, i) => { const ph = i * 1.7, x = fx[i] + 26 * Math.sin(lt * 0.9 + ph) * (1 - k), y = lerp(fy[i] + 34 * Math.sin(lt * 1.3 + ph), 790, k);
      ctx.save(); ctx.strokeStyle = rgba(G.CREAM, 0.7); ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(x, y + 62); ctx.quadraticCurveTo(x + 14, y + 110, x - 6, y + 150); ctx.stroke(); ctx.restore();
      ctx.save(); ctx.translate(x, y); ctx.scale(1, lerp(1, 0.86, k)); ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(0, 0, 50, 62, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      G.poly(ctx, [[x, y + 58], [x - 10, y + 72], [x + 10, y + 72]], col); });
    ctx.fillStyle = rgba(G.CREAM, 0.35); ctx.fillRect(300, 1020 - 60, 1400, 5);
    b6down(ctx, 1730, 420, 900, G.CREAM, 10, inv(D * 0.45, D * 0.75, lt));
    tag(ctx, '一起被压低', 1540, 360, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.corr_downhill = (ctx, s, lt, C) => { // 回到并排走路的两个小人，脚下的路突然变成下坡
    const D = s.vizDur, k = E.io(inv(D * 0.25, D * 0.55, lt)), gy = (x) => x < 700 ? 760 : 760 + (x - 700) * 0.32 * k;
    G.poly(ctx, [[120, 760], [700, 760], [1800, 760 + 352 * k], [1800, 1080], [120, 1080]], rgba(G.INK, 0.35));
    const x = 520 + 380 * inv(D * 0.3, D, lt); b6person(ctx, x, gy(x), 300, G.CREAM, b8walk(lt)); b6person(ctx, x + 320, gy(x + 320), 300, G.INK, b8walk(lt));
    b6down(ctx, 1560, 500, 760, G.INK, 10, inv(D * 0.5, D * 0.8, lt));
    tag(ctx, '路变下坡', 1560, 420, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.fg });
    vizCaption(ctx, s, lt, C);
  };
  // ── #18 协方差 ── (raw number; size depends on units; standardised → correlation in −1..1)
  function b8raw(ctx, x, y, lt, col, a = 1) { // heap of raw material (little blocks)
    ctx.save(); ctx.globalAlpha = a; for (let i = 0; i < 14; i++) { const u = b6rnd(i, 31), v = b6rnd(i, 32); ctx.fillStyle = i % 3 ? col : PAL.gold.t[2];
      ctx.save(); ctx.translate(x + (u - 0.5) * 220, y - v * 90 * (1 - Math.abs(u - 0.5))); ctx.rotate(u * 3 + Math.sin(lt + i) * 0.05); ctx.fillRect(-20, -20, 40, 40); ctx.restore(); } ctx.restore();
  }
  function b8scene_machine(ctx, lt, C, o = {}) { // machine centred at 1000,640; raw heap feeds in from the left, card slides out at the right
    const mx = o.mx || 1000, my = o.my || 660, feed = o.feed ?? 0, card = o.card ?? 0;
    b8raw(ctx, mx - 330, my - 290 + 120 * feed, lt, o.rawCol || C.fg, 1 - feed * 0.6);
    b8machine(ctx, mx, my, o.col || C.fg, o.win || C.bg, lt * 2, o.glow || 0);
    if (card > 0) { const cx = mx + 270 + 260 * E.o3(clamp(card)); b8card(ctx, cx, my + 95, 280, 170, PAL.gold.t[2], G.INK, o.cardTxt || '', o.cardPx || 44, { en: o.en }); }
  }
  VIZ.cov_card_out = (ctx, s, lt, C) => { // 原料进机器，出口吐出一张卡片，写着刻度「-1 到 1」
    const D = s.vizDur; b8scene_machine(ctx, lt, C, { feed: inv(0, D * 0.4, lt), card: inv(D * 0.35, D * 0.7, lt), cardTxt: '-1 到 1', cardPx: 48 });
    tag(ctx, '相关系数', 1530, 470, C, inv(D * 0.6, D * 0.9, lt), { px: 40, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.cov_machine = (ctx, s, lt, C) => { // 一台机器：进口塞进一堆原料，出口吐出一张小卡片
    const D = s.vizDur; b8scene_machine(ctx, lt, C, { feed: inv(D * 0.1, D * 0.5, lt), card: inv(D * 0.45, D * 0.8, lt), cardTxt: '?', cardPx: 80, en: 1 });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.cov_title = (ctx, s, lt, C) => { // 屏幕标题「Covariance」，机器进口那堆原料亮起来
    const D = s.vizDur; b6title(ctx, 'Covariance', W / 2, 260, 120, C.fg, inv(0.05, D * 0.5, lt));
    b8scene_machine(ctx, lt, C, { my: 760, glow: inv(D * 0.3, D * 0.6, lt) * (0.7 + 0.3 * Math.sin(lt * 5)), col: C.fg, win: C.bg });
  };
  VIZ.cov_bracket = (ctx, s, lt, C) => { // 两条线同向起伏，被一个括号框住
    const D = s.vizDur, ys = b8ser(40, 1.1, 90, 1.1), p = inv(0.1, D * 0.6, lt);
    b8plot(ctx, ys, 320, 1500, 560, C.fg, 11, p); b8plot(ctx, ys.map((v) => v * 0.85), 320, 1500, 820, G.INK, 11, p);
    const bp = inv(D * 0.45, D * 0.75, lt); if (bp > 0) { ctx.save(); ctx.globalAlpha = clamp(bp); ctx.strokeStyle = C.acc; ctx.lineWidth = 12; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(1560, 420); ctx.quadraticCurveTo(1620, 420, 1620, 500); ctx.lineTo(1620, 640); ctx.lineTo(1660, 690); ctx.lineTo(1620, 740); ctx.lineTo(1620, 880); ctx.quadraticCurveTo(1620, 960, 1560, 960); ctx.stroke(); ctx.restore(); }
    tag(ctx, '同向？', 1730, 600, C, inv(D * 0.6, D * 0.9, lt), { px: 36, bg: C.acc, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.cov_signs = (ctx, s, lt, C) => { // 左边同向的两条线标「+」，右边反向的标「-」
    const D = s.vizDur, ys = b8ser(22, 0.8, 70, 1.3), p = inv(0.1, D * 0.6, lt);
    b8plot(ctx, ys, 220, 860, 600, G.CREAM, 10, p); b8plot(ctx, ys, 220, 860, 820, PAL.gold.t[2], 10, p);
    b8plot(ctx, ys, 1060, 1700, 600, G.CREAM, 10, p); b8plot(ctx, ys.map((v) => -v), 1060, 1700, 820, PAL.red.t[1], 10, p);
    ctx.fillStyle = rgba(G.CREAM, 0.3); ctx.fillRect(958, 440, 4, 520);
    [[540, '+', PAL.green.t[1], 0.45], [1380, '-', PAL.red.t[1], 0.6]].forEach(([x, t, col, at]) => { const q = pop(lt, D * at, D * at + 0.5); if (q > 0) { ctx.save(); ctx.translate(x, 990); ctx.scale(q, q); G.disc(ctx, 0, 0, 62, col); b8txt(ctx, t, 0, 0, 110, G.INK, { en: 1 }); ctx.restore(); } });
    vizCaption(ctx, s, lt, C);
  };
  function b8rulerH(ctx, x0, x1, y, n, col, unit, p = 1) { ctx.fillStyle = col; ctx.fillRect(x0, y - 6, (x1 - x0) * p, 12); for (let i = 0; i <= n; i++) { const x = lerp(x0, x1, i / n); if (x > lerp(x0, x1, p)) break; ctx.fillRect(x - 3, y - (i % 5 ? 22 : 40), 6, i % 5 ? 22 : 40); } b8txt(ctx, unit, x1 + 70, y, 52, col); }
  VIZ.cov_units = (ctx, s, lt, C) => { // 同一段数据：一把尺子刻「元」，另一把刻「分」，读出来的数差很多
    const D = s.vizDur, ys = b8ser(26, 2.4, 80, 1), p = inv(0.05, D * 0.4, lt), xr = 1150;
    b8plot(ctx, ys, 220, 980, 690, G.INK, 10, p);
    b8rulerH(ctx, 1100, 1620, 560, 5, G.INK, '元', inv(D * 0.2, D * 0.5, lt)); b8rulerH(ctx, 1100, 1620, 820, 50, C.fg, '分', inv(D * 0.35, D * 0.65, lt));
    tag(ctx, '3', 1360, 460, C, inv(D * 0.55, D * 0.75, lt), { px: 48, bg: G.INK, fg: C.bg }); tag(ctx, '300', 1360, 930, C, inv(D * 0.65, D * 0.85, lt), { px: 48, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.cov_cards_big = (ctx, s, lt, C) => { // 两张写着不同大数的卡片，大小差得很远
    const D = s.vizDur, a = pop(lt, D * 0.1, D * 0.4), b = pop(lt, D * 0.35, D * 0.7);
    if (a > 0) b8card(ctx, 620, 720, 220, 150, G.INK, C.bg, '2', 80, { en: 1, sc: a });
    if (b > 0) b8card(ctx, 1240, 680, 720, 420, C.fg, C.bg, '20000', 170, { en: 1, sc: b });
    tag(ctx, '同一段数据', 620, 900, C, inv(D * 0.55, D * 0.85, lt), { px: 36, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.cov_wobble = (ctx, s, lt, C) => { // 两张卡片放上天平，天平乱晃，标「没法比」
    const D = s.vizDur, w = inv(D * 0.2, D * 0.4, lt), tilt = w * (0.9 * Math.sin(lt * 4.3) + 0.4 * Math.sin(lt * 7.1));
    b8bal(ctx, 960, 500, 420, tilt, G.CREAM, (c, sd, px, py) => b8card(c, px, py - 60, sd < 0 ? 160 : 260, sd < 0 ? 100 : 120, sd < 0 ? G.INK : PAL.gold.t[2], sd < 0 ? G.CREAM : G.INK, sd < 0 ? '2' : '20000', sd < 0 ? 56 : 58, { en: 1 }));
    tag(ctx, '没法比', 960, 1000, C, inv(D * 0.55, D * 0.85, lt), { px: 44, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.cov_cards_ruler = (ctx, s, lt, C) => { // 几张卡片整齐地排在同一根刻度尺上
    const D = s.vizDur; b8gauge(ctx, 360, 1560, 860, 0, C, 0, { bar: C.fg, px: 52 });
    [[-0.6, '-0.6'], [0.1, '0.1'], [0.5, '0.5'], [0.9, '0.9']].forEach(([v, t], i) => { const k = E.o3(inv(D * 0.15 + i * 0.35, D * 0.4 + i * 0.35, lt)); if (k <= 0) return;
      const x = lerp(360, 1560, (v + 1) / 2); b8card(ctx, x, lerp(460, 700, k), 170, 110, i % 2 ? PAL.gold.t[2] : C.fg, i % 2 ? G.INK : C.bg, t, 52, { en: 1 }); ctx.fillStyle = rgba(C.fg, 0.5 * k); ctx.fillRect(x - 3, 760, 6, 70); });
    tag(ctx, '能比了', 1560, 430, C, inv(D * 0.7, D * 0.92, lt), { px: 40, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.cov_machine_end = (ctx, s, lt, C) => { // 回到那台机器：左边原料，右边成品卡片
    const D = s.vizDur; b8scene_machine(ctx, lt, C, { mx: 960, card: 1, cardTxt: '-1 到 1', cardPx: 48 });
    tag(ctx, '原料', 620, 920, C, inv(D * 0.2, D * 0.5, lt), { px: 40, bg: G.CREAM, fg: G.INK }); tag(ctx, '成品', 1490, 920, C, inv(D * 0.4, D * 0.7, lt), { px: 40, bg: PAL.gold.t[2], fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  // ── #19 线性回归 ── (best-fit line; slope = beta; past fit ≠ future accuracy; negative-return dots sit BELOW)
  const R8 = { ox: 1010, oy: 690, sx: 480, sy: 290, k: 0.85 }, R8P = b8pts(64, 41, 0.85, 0.42);
  const r8x = (u) => R8.ox + u * R8.sx, r8y = (v) => R8.oy - v * R8.sy;
  function r8dots(ctx, col, n = R8P.length, a = 1, r = 13) { ctx.save(); ctx.globalAlpha = a; for (let i = 0; i < n; i++) { const [u, v] = R8P[i]; G.disc(ctx, r8x(u), r8y(v), r, v < 0 ? (col === 'neg' ? PAL.red.t[2] : col) : (col === 'neg' ? PAL.green.t[3] : col)); } ctx.restore(); }
  function r8line(ctx, k, col, w = 10, p = 1, u0 = -1.1, u1 = 1.1) { if (p <= 0) return; const ue = lerp(u0, u1, clamp(p)); ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(r8x(u0), r8y(k * u0)); ctx.lineTo(r8x(ue), r8y(k * ue)); ctx.stroke(); ctx.restore(); }
  function r8axes(ctx, col) { b8axes(ctx, R8.ox, R8.oy, R8.ox - 560, R8.ox + 560, R8.oy - 330, R8.oy + 340, col, 5); }
  VIZ.reg_scatter = (ctx, s, lt, C) => { // 满屏散落的小点，一条直线从中间穿过
    const D = s.vizDur; r8dots(ctx, C.fg, Math.round(R8P.length * clamp(inv(0, D * 0.4, lt) + 0.2)));
    r8line(ctx, R8.k, C.acc, 12, inv(D * 0.4, D * 0.8, lt)); vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_title = (ctx, s, lt, C) => { // 屏幕标题「Linear Regression」，直线微微倾斜
    const D = s.vizDur; b6title(ctx, 'Linear Regression', W / 2, 330, 120, C.fg, inv(0.05, D * 0.5, lt));
    const k = lerp(0, 0.35, E.io(inv(D * 0.3, D * 0.9, lt))); ctx.save(); ctx.translate(0, 90); r8line(ctx, k, PAL.gold.t[2], 12, 1); ctx.restore();
  };
  VIZ.reg_candidates = (ctx, s, lt, C) => { // 几条候选直线轮流出现，最后留下离点最近的那条
    const D = s.vizDur, ks = [-0.3, 1.8, 0.2, R8.k], seg = (D * 0.85) / ks.length, j = Math.min(ks.length - 1, Math.floor(lt / seg));
    r8dots(ctx, G.INK, R8P.length, 0.8, 11);
    ks.forEach((k, i) => { if (i < j) r8line(ctx, k, rgba(G.INK, 0.18), 6); });
    r8line(ctx, ks[j], j === ks.length - 1 ? PAL.red.t[2] : C.fg, 12, inv(j * seg, j * seg + 0.4, lt));
    tag(ctx, '最贴近', 1580, 380, C, inv(D * 0.85, D * 0.98, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_xaxis = (ctx, s, lt, C) => { // 横轴标「大盘收益」
    const D = s.vizDur, p = inv(0.05, D * 0.4, lt); ctx.save(); ctx.globalAlpha = clamp(p); r8axes(ctx, C.fg); ctx.restore();
    tag(ctx, '大盘收益', R8.ox + 440, R8.oy + 80, C, inv(D * 0.3, D * 0.6, lt), { px: 42, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_yaxis = (ctx, s, lt, C) => { // 竖轴标「这只股票的收益」，不出现真实名称和代码
    const D = s.vizDur; r8axes(ctx, C.fg); tag(ctx, '大盘收益', R8.ox + 440, R8.oy + 80, C, 1, { px: 42, bg: C.fg, fg: C.bg });
    tag(ctx, '这只股票的收益', R8.ox + 230, R8.oy - 300, C, inv(D * 0.25, D * 0.6, lt), { px: 42, bg: PAL.gold.t[2], fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_dots_fill = (ctx, s, lt, C) => { // 小点一个接一个落下，铺满坐标图，负收益的点在下方
    const D = s.vizDur, n = R8P.length; r8axes(ctx, rgba(G.INK, 0.7));
    for (let i = 0; i < n; i++) { const t0 = D * 0.8 * i / n, k = inv(t0, t0 + 0.35, lt); if (k <= 0) break; const [u, v] = R8P[i];
      G.disc(ctx, r8x(u), lerp(r8y(v) - 140, r8y(v), E.o3(k)), 13, v < 0 ? PAL.red.t[2] : PAL.green.t[3]); }
    tag(ctx, '负收益在下', 1640, 960, C, inv(D * 0.6, D * 0.9, lt), { px: 34, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  function r8step(ctx, C, p, col) { // little stair under the line: run 1 → rise k
    const u0 = 0.15, u1 = 0.65, x0 = r8x(u0), x1 = r8x(u1), y0 = r8y(R8.k * u0), y1 = r8y(R8.k * u1), a = clamp(p * 2), b = clamp(p * 2 - 1);
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 9; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(lerp(x0, x1, a), y0); if (b > 0) { ctx.moveTo(x1, y0); ctx.lineTo(x1, lerp(y0, y1, b)); } ctx.stroke(); ctx.restore();
    return [x1, (y0 + y1) / 2];
  }
  VIZ.reg_slope = (ctx, s, lt, C) => { // 直线旁画出一个小台阶，标「斜率」
    const D = s.vizDur; r8axes(ctx, rgba(C.fg, 0.4)); r8dots(ctx, C.fg, R8P.length, 0.35, 10); r8line(ctx, R8.k, G.INK, 12);
    const [sx, sy] = r8step(ctx, C, inv(D * 0.15, D * 0.6, lt), PAL.red.t[2]);
    tag(ctx, '斜率', sx + 120, sy, C, inv(D * 0.55, D * 0.85, lt), { px: 44, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_beta = (ctx, s, lt, C) => { // 小台阶旁亮起「β（贝塔）」
    const D = s.vizDur; r8axes(ctx, rgba(C.fg, 0.4)); r8dots(ctx, C.fg, R8P.length, 0.35, 10); r8line(ctx, R8.k, G.INK, 12);
    const [sx, sy] = r8step(ctx, C, 1, PAL.red.t[2]); const q = pop(lt, D * 0.2, D * 0.55);
    if (q > 0) { ctx.save(); ctx.translate(sx + 170, sy); ctx.scale(q, q); G.disc(ctx, 0, 0, 80, PAL.gold.t[2]); b8txt(ctx, 'β', 0, 4, 110, G.INK, { en: 1 }); ctx.restore(); }
    tag(ctx, '贝塔', sx + 170, sy + 130, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_step15 = (ctx, s, lt, C) => { // 大盘那边走一格，股票那边走一格半，角标「假设」 (then the same, downward)
    const D = s.vizDur, U = 240, c0 = 900, up = inv(D * 0.1, D * 0.45, lt), dn = inv(D * 0.55, D * 0.9, lt), t = dn > 0 ? up - 2 * dn : up; // +1 … then −1
    [[560, '大盘', 1, G.INK], [820, '这只股票', 1.5, C.fg]].forEach(([y, lab, f, col]) => {
      ctx.fillStyle = rgba(col, 0.25); ctx.fillRect(c0 - 1.7 * U, y - 4, 3.4 * U, 8);
      for (let g = -3; g <= 3; g++) { const half = g % 2 !== 0; ctx.fillRect(c0 + g * U / 2 - 3, y - (half ? 14 : 26), 6, half ? 28 : 52); }
      const cx = c0 + t * f * U; G.disc(ctx, cx, y, 34, t < 0 ? PAL.red.t[2] : col);
      b8txt(ctx, lab, 260, y - 80, 40, col, { align: 'left' }); });
    tag(ctx, '动 1', 1520, 560, C, inv(D * 0.2, D * 0.45, lt), { px: 40, bg: G.INK, fg: C.bg }); tag(ctx, '动 1.5', 1520, 820, C, inv(D * 0.3, D * 0.55, lt), { px: 40, bg: C.fg, fg: C.bg });
    b8corner(ctx, '假设', C, inv(0.1, 0.6, lt)); vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_oldphoto = (ctx, s, lt, C) => { // 所有点变成泛黄的旧照片
    const D = s.vizDur, k = inv(D * 0.15, D * 0.7, lt);
    ctx.save(); ctx.globalAlpha = 0.85 * k; ctx.fillStyle = PAL.ochre.t[1]; ctx.translate(R8.ox, R8.oy); ctx.rotate(-0.03 * k); ctx.beginPath(); ctx.roundRect(-620, -360, 1240, 720, 18); ctx.fill();
    ctx.strokeStyle = G.CREAM; ctx.lineWidth = 22; ctx.stroke(); ctx.restore();
    r8dots(ctx, k > 0.5 ? PAL.ochre.t[4] : G.INK, R8P.length, 1, 12); r8line(ctx, R8.k, k > 0.5 ? PAL.ochre.t[4] : G.INK, 10);
    tag(ctx, '过去的点', R8.ox + 470, R8.oy + 270, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_fog = (ctx, s, lt, C) => { // 直线往右延伸进一团雾里，新落下的点散得很开
    const D = s.vizDur; ctx.save(); ctx.translate(-260, 0); r8dots(ctx, G.INK, R8P.length, 0.85, 11); r8line(ctx, R8.k, G.INK, 10, 1, -1.1, 1.1);
    r8line(ctx, R8.k, rgba(G.INK, 0.6), 10, inv(D * 0.1, D * 0.45, lt), 1.1, 1.75); ctx.restore();
    for (let i = 0; i < 12; i++) { const k = inv(D * 0.4 + i * 0.12, D * 0.55 + i * 0.12, lt); if (k <= 0) continue; const x = 1460 + (b6rnd(i, 51) - 0.5) * 300, y = 400 + b6rnd(i, 52) * 580;
      G.disc(ctx, x, lerp(y - 120, y, E.o3(k)), 13, y > 700 ? PAL.red.t[2] : PAL.purple.t[2]); }
    b8fog(ctx, 1480, 680, 300, 330, G.CREAM, 0.5, lt, 20);
    tag(ctx, '将来？', 1480, 1000, C, inv(D * 0.6, D * 0.9, lt), { px: 40, bg: C.acc, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.reg_summary = (ctx, s, lt, C) => { // 回到满屏小点和那条直线，直线上写「总结」
    const D = s.vizDur; r8dots(ctx, 'neg', R8P.length, 0.9, 12); r8line(ctx, R8.k, C.fg, 14);
    const q = inv(D * 0.3, D * 0.6, lt); if (q > 0) { ctx.save(); ctx.translate(r8x(0.45), r8y(R8.k * 0.45) - 70); ctx.rotate(-Math.atan2(R8.k * R8.sy, R8.sx)); ctx.globalAlpha = clamp(q * 2); b8card(ctx, 0, 0, 220, 96, C.fg, C.bg, '总结', 52); ctx.restore(); }
    tag(ctx, '不是预言', 1600, 960, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  // ── #20 假设检验 ── (p-value ≠ P(null true); rejecting ≠ proving; fictional backtest, no profit implied)
  function h8bal(ctx, lt, C, tilt, o = {}) { // courtroom-style balance: left pan 「没效果」, right pan 「有效」
    const glow = o.glow || 0;
    b8bal(ctx, o.x || 960, o.y || 470, o.s || 430, tilt, o.col || C.fg, (c, sd, px, py) => {
      if (sd < 0) { if (glow > 0) { c.save(); c.globalAlpha = 0.45 * glow; G.disc(c, px, py - 60, 150, PAL.gold.t[2]); c.restore(); } b8card(c, px, py - 58, 250, 100, glow > 0.5 ? PAL.gold.t[2] : G.INK, glow > 0.5 ? G.INK : G.CREAM, '没效果', 46); }
      else if (!o.hideR) b8card(c, px, py - 58, 220, 100, o.col || C.fg, C.bg, '有效', 46, { dash: o.dash });
    });
  }
  VIZ.hyp_scale = (ctx, s, lt, C) => { // 法庭式的天平，一边放「没效果」，先压着
    const D = s.vizDur; h8bal(ctx, lt, C, E.oBack(clamp(inv(D * 0.2, D * 0.6, lt))), { dash: 1 });
    tag(ctx, '先假设', 520, 960, C, inv(D * 0.5, D * 0.85, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_title = (ctx, s, lt, C) => { // 屏幕标题「Hypothesis Testing」
    const D = s.vizDur; b6title(ctx, 'Hypothesis Testing', W / 2, 460, 120, C.fg, inv(0.05, D * 0.5, lt));
    ctx.save(); ctx.globalAlpha = 0.5 * inv(D * 0.3, D * 0.8, lt); h8bal(ctx, lt, C, 0.3 * Math.sin(lt * 1.5), { y: 700, s: 220, col: C.fg }); ctx.restore();
  };
  const h8bt = (n = 44) => { const r = b8ser(n, 3.3, 120, 1.05); return r.map((v, i) => v - r[n - 1] * i / (n - 1)); }; // up-and-down, ends where it started
  VIZ.hyp_backtest = (ctx, s, lt, C) => { // 一张纸上写「虚构策略」，旁边一条起起伏伏、有涨有跌的回测线，角标「假设」
    const D = s.vizDur; ctx.save(); ctx.translate(470, 680); ctx.rotate(-0.05); ctx.fillStyle = G.CREAM; ctx.beginPath(); ctx.roundRect(-220, -270, 440, 540, 16); ctx.fill();
    b8txt(ctx, '虚构策略', 0, -170, 60, G.INK); ctx.fillStyle = rgba(G.INK, 0.3); for (let j = 0; j < 5; j++) ctx.fillRect(-160, -60 + j * 60, 320 - (j % 2) * 80, 14); ctx.restore();
    b8dash(ctx, 820, 690, 1700, 690, rgba(G.CREAM, 0.35), 4);
    b8plot(ctx, h8bt(), 820, 1700, 690, PAL.gold.t[2], 11, inv(D * 0.2, D * 0.85, lt));
    tag(ctx, '回测', 1260, 980, C, inv(D * 0.4, D * 0.7, lt), { px: 38, bg: PAL.gold.t[2], fg: G.INK });
    b8corner(ctx, '假设', C, inv(0.1, 0.6, lt)); vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_coin = (ctx, s, lt, C) => { // 一枚硬币在空中翻转
    const D = s.vizDur, h = inv(0, D * 0.9, lt), y = 900 - 520 * 4 * h * (1 - h), sq = Math.cos(lt * 9);
    ctx.fillStyle = rgba(G.INK, 0.25); ctx.beginPath(); ctx.ellipse(960, 960, 130 * (1 - 0.5 * (900 - y) / 520), 22, 0, 0, Math.PI * 2); ctx.fill();
    ctx.save(); ctx.translate(960, y); ctx.scale(1, Math.max(0.06, Math.abs(sq))); G.disc(ctx, 0, 0, 130, G.INK); G.disc(ctx, 0, 0, 104, sq > 0 ? G.CREAM : PAL.ochre.t[1]); ctx.restore();
    tag(ctx, '只是运气？', 1500, 470, C, inv(D * 0.4, D * 0.75, lt), { px: 40, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  function h8hill(ctx, lt, C, p, o = {}) { // histogram of random outcomes, stacked blocks; returns right-edge x
    const n = 17, x0 = 420, bw = 64, yb = 940, col = o.col || C.fg;
    for (let i = 0; i < n; i++) { const z = (i - 8) / 3.2, h = Math.round(9 * Math.exp(-z * z / 2)); for (let j = 0; j < h; j++) { const k = inv(0, 1, p * (n * 1.2) - i * 0.6 - j * 0.15); if (k <= 0) continue;
      const shade = o.tail && i >= 15; ctx.fillStyle = shade ? (o.tailCol || PAL.red.t[2]) : rgba(col, 0.85); ctx.fillRect(x0 + i * bw + 4, yb - (j + 1) * 50 + 4, bw - 8, 42); } }
    ctx.fillStyle = col; ctx.fillRect(x0 - 20, yb, n * bw + 40, 6); return x0 + n * bw;
  }
  VIZ.hyp_hill = (ctx, s, lt, C) => { // 一堆随机结果堆成小山，策略的结果落在小山最边上
    const D = s.vizDur, xr = h8hill(ctx, lt, C, inv(0, D * 0.6, lt)), q = pop(lt, D * 0.6, D * 0.85);
    if (q > 0) { ctx.save(); ctx.translate(xr - 8, 870); ctx.scale(q, q); G.poly(ctx, [[0, 60], [-30, 0], [30, 0]], PAL.gold.t[2]); G.disc(ctx, 0, -20, 30, PAL.gold.t[2]); ctx.restore(); }
    tag(ctx, '策略的结果', xr - 8, 760, C, inv(D * 0.7, D * 0.92, lt), { px: 36, bg: PAL.gold.t[2], fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_pval = (ctx, s, lt, C) => { // 屏幕出现「p 值」，不出现公式
    const D = s.vizDur, q = pop(lt, D * 0.1, D * 0.45); if (q > 0) { ctx.save(); ctx.translate(960, 640); ctx.scale(q, q); b8card(ctx, 0, 0, 560, 300, C.fg, C.bg, '', 0);
      b8txt(ctx, 'p', -90, 0, 200, C.bg, { en: 1 }); b8txt(ctx, '值', 90, 6, 170, C.bg); ctx.restore(); }
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_scale_glow = (ctx, s, lt, C) => { // 天平上「没效果」那一边亮起
    const D = s.vizDur; h8bal(ctx, lt, C, 0.6, { glow: inv(D * 0.2, D * 0.55, lt) * (0.85 + 0.15 * Math.sin(lt * 5)), dash: 1 });
    tag(ctx, '假如真的没效果', 1440, 960, C, inv(D * 0.5, D * 0.85, lt), { px: 38, bg: PAL.gold.t[2], fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_tail_shade = (ctx, s, lt, C) => { // 小山边上那一小块被涂色，标「这么极端的概率」
    const D = s.vizDur, sh = inv(D * 0.25, D * 0.5, lt), xr = h8hill(ctx, lt, C, 1, { tail: sh > 0, tailCol: rgba(PAL.red.t[2], 0.4 + 0.6 * sh) });
    tag(ctx, '这么极端的概率', xr - 140, 620, C, inv(D * 0.5, D * 0.85, lt), { px: 38, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  function h8cards(ctx, lt, C, D, zoomR = 0) {
    const zr = 1 + 0.35 * zoomR, xl = lerp(620, 420, zoomR), xr = lerp(1300, 1180, zoomR);
    ctx.save(); ctx.globalAlpha = 1 - 0.6 * zoomR; b8card(ctx, xl, 660, 520, 260, G.CREAM, G.INK, '', 0); b8txt(ctx, '看到这种数据', xl, 610, 46, G.INK); b8txt(ctx, '的概率', xl, 680, 46, G.INK);
    b8check(ctx, xl, 900, 90, PAL.green.t[3], zoomR > 0 ? 1 : inv(D * 0.35, D * 0.6, lt)); ctx.restore();
    ctx.save(); ctx.translate(xr, 660); ctx.scale(zr, zr); b8card(ctx, 0, 0, 520, 260, G.INK, G.CREAM, '', 0); b8txt(ctx, '没效果的概率', 0, 0, 50, G.CREAM); ctx.restore();
    b8cross(ctx, xr, 660 + 240 * zr, 90, PAL.red.t[2], zoomR > 0 ? 1 : inv(D * 0.55, D * 0.8, lt));
  }
  VIZ.hyp_two_cards = (ctx, s, lt, C) => { // 两张卡片：左边「看到这种数据的概率」打勾，右边「没效果的概率」打叉
    h8cards(ctx, lt, C, s.vizDur, 0); vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_warn = (ctx, s, lt, C) => { // 右边那张打叉的卡片放大，旁边一个警示三角
    const D = s.vizDur; h8cards(ctx, lt, C, D, E.io(inv(0, D * 0.5, lt)));
    const q = pop(lt, D * 0.35, D * 0.65); if (q > 0) { ctx.save(); ctx.translate(1660, 420); ctx.scale(q, q); G.poly(ctx, [[0, -110], [-120, 95], [120, 95]], PAL.gold.t[2]); b8txt(ctx, '!', 0, 20, 130, G.INK, { en: 1 }); ctx.restore(); }
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_dashed = (ctx, s, lt, C) => { // 天平抬起了，另一边写「有效」的盒子仍然是虚线框
    const D = s.vizDur; h8bal(ctx, lt, C, -0.8, { dash: 1 });
    tag(ctx, '还没证明', 1420, 960, C, inv(D * 0.4, D * 0.75, lt), { px: 40, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_lift = (ctx, s, lt, C) => { // 天平上「没效果」那一边被抬起
    const D = s.vizDur; h8bal(ctx, lt, C, lerp(0.8, -0.8, E.oBack(clamp(inv(D * 0.3, D * 0.7, lt)))), { dash: 1 });
    tag(ctx, '推翻', 500, 960, C, inv(D * 0.55, D * 0.85, lt), { px: 42, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_fog = (ctx, s, lt, C) => { // 回测线延伸进雾里，有涨有跌，看不清
    const D = s.vizDur, a = h8bt(30), b = b8ser(22, 7.7, 140, 1.3).map((v) => v + a[29]);
    b8dash(ctx, 220, 690, 1700, 690, rgba(G.CREAM, 0.3), 4);
    b8plot(ctx, a, 220, 1000, 690, PAL.gold.t[2], 11, 1); b8plot(ctx, b, 1000, 1640, 690, rgba(PAL.gold.t[2], 0.8), 11, inv(D * 0.1, D * 0.75, lt));
    b8fog(ctx, 1380, 690, 360, 330, G.CREAM, 0.55, lt, 22);
    tag(ctx, '换个时期？', 1380, 1000, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.hyp_end = (ctx, s, lt, C) => { // 回到天平，镜头停在「没效果」那个标签上
    const D = s.vizDur, z = E.io(inv(0, D * 0.75, lt)), sc = lerp(1, 1.7, z), tilt = 0.6, a = -tilt * 0.32, lx = 960 - Math.cos(a) * 430, ly = 470 + Math.sin(a) * 430 + 430 * 0.44 - 58;
    ctx.save(); ctx.translate(lerp(0, 960 - lx, z), lerp(0, 600 - ly, z)); ctx.translate(lx, ly); ctx.scale(sc, sc); ctx.translate(-lx, -ly); h8bal(ctx, lt, C, tilt, { dash: 1, hideR: z > 0.04 }); ctx.restore();
    tag(ctx, '检验的是什么假设？', 1360, 960, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  // ───────── finance-v003 scene library, batch 9 (quant models: Monte Carlo / EWMA / GARCH / stationarity / skewness, 2026-10-30) ─────────
  // #21 蒙特卡洛模拟 · #22 EWMA · #23 GARCH · #24 平稳性 · #25 偏度 — 58 scenes, one per line.
  // 金融专家 rules: Monte Carlo = many forking paths (never casinos or dice), a map of possibilities, not a forecast; EWMA's λ = 0.94
  // appears only as the small on-screen corner note; GARCH is named on screen only; prices wander, returns stay in a range;
  // negative skew = the tail sits on the LOSS side (left / down), never "skew = losing money"; losses go DOWN, no formulas.
  Object.assign(VPAL, {
    mc_fork: 'ink', mc_title: 'purple', mc_screen: 'cream', mc_onepath: 'cream', mc_fan: 'ink', mc_hill: 'green', mc_worst: 'ink',
    mc_map: 'gold', mc_crystal: 'purple', mc_note: 'ochre', mc_wrong: 'cream', mc_signpost: 'green',
    ewma_steps: 'cream', ewma_title: 'green', ewma_meter: 'ink', ewma_equal: 'gold', ewma_grow: 'purple', ewma_fade: 'cream',
    ewma_ratio: 'ink', ewma_press: 'ochre', ewma_wave: 'red', ewma_settle: 'green', ewma_steps_end: 'purple',
    garch_pond: 'ink', garch_title: 'red', garch_gear: 'cream', garch_boxes: 'purple', garch_box1: 'gold', garch_box2: 'ink',
    garch_box3: 'ochre', garch_carry: 'cream', garch_cluster: 'ink', garch_revert: 'green', garch_ledger: 'ochre', garch_pond_end: 'purple',
    stat_map: 'gold', stat_title: 'ink', stat_mean: 'cream', stat_band: 'purple', stat_halves: 'green', stat_calc: 'ochre',
    stat_price: 'ink', stat_convert: 'cream', stat_bars: 'cream', stat_range: 'purple', stat_map_end: 'gold',
    skew_hill: 'purple', skew_title: 'ink', skew_sym: 'cream', skew_equal: 'gold', skew_left: 'cream', skew_bulk: 'green',
    skew_drop: 'cream', skew_bars: 'ink', skew_shadow: 'ochre', skew_fat: 'cream', skew_ruler: 'gold', skew_end: 'ink',
  });
  const B9LOSS = PAL.red.t[2];
  const b9walk = (n, seed, vol) => { let y = 0; const ys = [0]; for (let i = 1; i < n; i++) { y += vol * 1.4 * (b6rnd(i, seed) + b6rnd(i, seed + 0.31) + b6rnd(i, seed + 0.67) - 1.5); ys.push(y); } return ys; };
  const B9P = Array.from({ length: 360 }, (_, k) => b9walk(34, k * 1.37 + 3.1, 21));
  const B9END = B9P.map((ys) => ys[ys.length - 1]);
  const B9MIX = B9P.findIndex((ys) => Math.max(...ys) > 110 && Math.min(...ys) < -110 && Math.abs(ys[ys.length - 1]) < 80); // a path with clear ups AND downs
  function b9fan(ctx, n, x0, x1, yc, p, col, a, w = 3, sc = 1, from = 0) { // n random-walk paths from one root (x0, yc); + = up
    ctx.save(); ctx.globalAlpha = a; for (let k = from; k < Math.min(B9P.length, from + n); k++) b8plot(ctx, sc === 1 ? B9P[k] : B9P[k].map((v) => v * sc), x0, x1, yc, col, w, p); ctx.restore();
  }
  function b9hist(ctx, x0, x1, yb, hmax, p, col, o = {}) { // ends of B9P binned; LEFT = worse outcome; returns the worst-bin x
    const nb = o.bins || 22, lo = Math.min(...B9END), hi = Math.max(...B9END), cnt = new Array(nb).fill(0);
    B9END.forEach((v) => { cnt[Math.min(nb - 1, Math.floor((v - lo) / (hi - lo) * nb))]++; });
    const mx = Math.max(...cnt), bw = (x1 - x0) / nb, sk = o.skew || 0;
    for (let b = 0; b < nb; b++) { const h = hmax * cnt[b] / mx * E.o3(clamp(p * 1.4 - b * 0.02)); if (h <= 0) continue;
      const hh = sk ? h * (1 + sk * (b / nb - 0.5)) : h; ctx.fillStyle = (o.red && b < o.red) ? B9LOSS : col; ctx.fillRect(x0 + b * bw + 3, yb - hh, bw - 6, hh); }
    return x0 + bw * 0.5;
  }
  function b9screen(ctx, x, y, w, h, body, scr) { // monitor, (x,y) = screen centre
    ctx.fillStyle = body; ctx.beginPath(); ctx.roundRect(x - w / 2 - 26, y - h / 2 - 26, w + 52, h + 52, 26); ctx.fill();
    ctx.fillRect(x - 30, y + h / 2 + 26, 60, 90); ctx.fillRect(x - 170, y + h / 2 + 108, 340, 22);
    ctx.fillStyle = scr; ctx.fillRect(x - w / 2, y - h / 2, w, h);
  }
  function b9paper(ctx, x, y, w, h, col, fold) { // folded map sheet, (x,y) = centre
    ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(x - w / 2, y - h / 2, w, h, 12); ctx.fill();
    ctx.fillStyle = fold; for (let i = 1; i < 4; i++) ctx.fillRect(x - w / 2 + i * w / 4 - 2, y - h / 2, 4, h);
  }
  function b9weight(ctx, x, yb, s, col, a = 1) { // weight standing on yb, size s
    if (s < 2) return; ctx.save(); ctx.globalAlpha = a;
    G.poly(ctx, [[x - s * 0.5, yb], [x + s * 0.5, yb], [x + s * 0.36, yb - s * 0.8], [x - s * 0.36, yb - s * 0.8]], col);
    ctx.strokeStyle = col; ctx.lineWidth = Math.max(3, s * 0.1); ctx.beginPath(); ctx.arc(x, yb - s * 0.92, s * 0.16, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
  }
  function b9beam(ctx, x0, x1, yb, n, size, col, p = 1, o = {}) { // n weights on a bar; size(i) where i = n-1 is today (right)
    ctx.fillStyle = o.bar || col; ctx.fillRect(x0 - 40, yb, x1 - x0 + 80, 14);
    for (let i = 0; i < n; i++) { const x = lerp(x0, x1, i / (n - 1)), g = E.oBack(clamp(p * 1.5 - (n - 1 - i) * 0.04)); b9weight(ctx, x, yb, size(i) * g, col, o.alpha ? o.alpha(i) : 1); }
  }
  function b9meter(ctx, x, yb, h, v, col, track) { // vertical scale bar, filled to v (0..1)
    ctx.fillStyle = track; ctx.fillRect(x - 40, yb - h, 80, h); ctx.fillStyle = col; ctx.fillRect(x - 40, yb - h * clamp(v), 80, h * clamp(v));
    for (let j = 1; j < 10; j++) ctx.fillRect(x + 48, yb - j * h / 10, j % 5 ? 18 : 34, 5);
  }
  function b9foot(ctx, x, y, s, col, a, right) { // one footprint, s = length
    ctx.save(); ctx.globalAlpha = a; ctx.translate(x, y); ctx.rotate(right ? 0.12 : -0.12); ctx.fillStyle = col;
    ctx.beginPath(); ctx.ellipse(0, 0, s * 0.2, s * 0.36, 0, 0, Math.PI * 2); ctx.fill(); ctx.beginPath(); ctx.ellipse(0, s * 0.5, s * 0.16, s * 0.16, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  }
  function b9prints(ctx, lt, C, p, zoom = 0) { // a row of footprints: far = small + faint, near = big + clear
    const z = 1 + zoom * 0.7; ctx.save(); ctx.translate(960, 990); ctx.scale(z, z); ctx.translate(-960, -990);
    for (let i = 0; i < 9; i++) { const f = i / 8, y = lerp(420, 930, f * f), s = lerp(34, 150, f), a = lerp(0.12, 1, f) * clamp(p * 1.6 - (1 - f) * 0.6);
      b9foot(ctx, 960 + (i % 2 ? 1 : -1) * lerp(18, 80, f), y, s, C.fg, a, i % 2); }
    ctx.restore();
  }
  function b9pond(ctx, x, y, rx, ry, col, ring, lt, amp, n = 5, sp = 0.35) { // pond with expanding ripples, amp 0..1
    ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); ctx.fill(); if (amp <= 0) return;
    ctx.save(); ctx.strokeStyle = ring; ctx.lineWidth = 7;
    for (let i = 0; i < n; i++) { const f = b6fr(lt * sp + i / n); ctx.globalAlpha = (1 - f) * clamp(amp); ctx.beginPath(); ctx.ellipse(x, y, rx * 0.9 * f + 10, ry * 0.9 * f + 4, 0, 0, Math.PI * 2); ctx.stroke(); }
    ctx.restore();
  }
  function b9stone(ctx, x, y, r, col) { G.poly(ctx, [[x - r, y + r * 0.3], [x - r * 0.6, y - r * 0.7], [x + r * 0.5, y - r * 0.8], [x + r, y + r * 0.1], [x + r * 0.4, y + r * 0.8], [x - r * 0.5, y + r * 0.7]], col); }
  const b9wave = (n, seed, env) => Array.from({ length: n }, (_, i) => env(i / (n - 1)) * (0.65 * Math.sin(i * 0.9 + seed) + 0.35 * Math.sin(i * 2.3 + seed * 1.7)));
  function b9cells(ctx, C, lit, lt, o = {}) { // three input boxes for today's volatility; lit[i] 0..1
    const xs = [520, 960, 1400], y = o.y || 640, w = 360, h = 300, lab = ['长期水平', '昨天的冲击', '昨天的晃动'];
    xs.forEach((x, i) => { const L = clamp(lit[i] || 0);
      ctx.save(); ctx.strokeStyle = C.fg; ctx.lineWidth = 7; ctx.setLineDash([20, 14]); ctx.globalAlpha = 1 - L * 0.7; ctx.beginPath(); ctx.roundRect(x - w / 2, y - h / 2, w, h, 26); ctx.stroke(); ctx.restore();
      if (L <= 0) return; ctx.save(); ctx.globalAlpha = L; ctx.fillStyle = C.fg; ctx.beginPath(); ctx.roundRect(x - w / 2, y - h / 2, w, h, 26); ctx.fill();
      if (i === 0) { ctx.fillStyle = C.bg; ctx.fillRect(x - 130, y - 6, 260, 12); }
      if (i === 1) { b9pond(ctx, x, y + 50, 130, 40, rgba(C.bg, 0.35), C.bg, lt, 1, 3, 0.5); b9stone(ctx, x, y - 60 + 30 * Math.sin(lt * 3), 26, C.bg); }
      if (i === 2) b8plot(ctx, b9wave(20, 0.7, () => 80), x - 140, x + 140, y, C.bg, 9, 1);
      b8txt(ctx, lab[i], x, y + h / 2 + 50, 38, C.fg); ctx.restore(); });
  }
  const b9erf = (x) => { const s = Math.sign(x), a = Math.abs(x), t = 1 / (1 + 0.3275911 * a);
    return s * (1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-a * a)); };
  const b9snRaw = (u) => Math.exp(-u * u / 2) * (1 + b9erf(-4 * u / Math.SQRT2));
  const B9SKM = Math.max(...Array.from({ length: 400 }, (_, i) => b9snRaw(-4 + i / 50)));
  const b9S = (u) => b9snRaw((u - 2.0) / 1.7) / B9SKM; // negative skew, peak right of centre, long tail to the LEFT (loss side)
  const B9X0 = 300, B9X1 = 1620, B9YB = 900;
  function b9axis(ctx, C, col) { // outcome axis: 亏 on the left, 赚 on the right
    ctx.fillStyle = col; ctx.fillRect(B9X0 - 40, B9YB, B9X1 - B9X0 + 80, 6);
    b8txt(ctx, '亏', B9X0 - 10, B9YB + 50, 40, col); b8txt(ctx, '赚', B9X1 + 10, B9YB + 50, 40, col);
  }
  // ── #21 蒙特卡洛模拟 ── (many forking paths from one crossroads; a map of possibilities, not a forecast; garbage in → garbage out)
  VIZ.mc_fork = (ctx, s, lt, C) => { // 一个路口分出成千上万条细细的岔路
    const D = s.vizDur; b9fan(ctx, 360, 360, 1640, 640, inv(D * 0.05, D * 0.8, lt), C.fg, 0.16, 3);
    G.disc(ctx, 360, 640, 26, C.acc);
    tag(ctx, '成千上万条岔路', 1440, 400, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mc_title = (ctx, s, lt, C) => { // 屏幕标题「Monte Carlo Simulation」，下方一张岔路地图
    const D = s.vizDur; b6title(ctx, 'Monte Carlo Simulation', W / 2, 420, 104, C.fg, inv(0.05, D * 0.5, lt));
    b9paper(ctx, 960, 790, 900, 300, rgba(G.CREAM, 0.9), rgba(G.INK, 0.12));
    ctx.save(); ctx.beginPath(); ctx.rect(510, 640, 900, 300); ctx.clip(); b9fan(ctx, 120, 560, 1360, 790, inv(D * 0.2, D * 0.9, lt), G.INK, 0.3, 3, 0.45); ctx.restore();
  };
  VIZ.mc_screen = (ctx, s, lt, C) => { // 一台电脑屏幕上，一个小点沿岔路随机前进
    const D = s.vizDur; b9screen(ctx, 960, 620, 1000, 520, G.INK, G.CREAM);
    ctx.save(); ctx.beginPath(); ctx.rect(460, 360, 1000, 520); ctx.clip();
    b9fan(ctx, 40, 520, 1400, 620, 1, G.INK, 0.12, 3, 0.8);
    const [hx, hy] = b8plot(ctx, B9P[7].map((v) => v * 0.8), 520, 1400, 620, C.acc, 9, inv(D * 0.1, D * 0.9, lt)); G.disc(ctx, hx, hy, 18, C.acc); ctx.restore();
    tag(ctx, '随机走', 1600, 300, C, inv(D * 0.4, D * 0.7, lt), { px: 38, bg: G.INK, fg: G.CREAM });
  };
  VIZ.mc_onepath = (ctx, s, lt, C) => { // 一条岔路被点亮，有上有下，往下的部分往下画
    const D = s.vizDur, yc = 640, ys = B9P[Math.max(0, B9MIX)].map((v) => v * 1.25), p = inv(D * 0.1, D * 0.8, lt);
    b9fan(ctx, 60, 300, 1620, yc, 1, G.INK, 0.08, 3);
    b8dash(ctx, 300, yc, 1640, yc, rgba(G.INK, 0.4), 4);
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, yc); ctx.clip(); b8plot(ctx, ys, 300, 1620, yc, PAL.green.t[3], 12, p); ctx.restore();
    ctx.save(); ctx.beginPath(); ctx.rect(0, yc, W, H - yc); ctx.clip(); b8plot(ctx, ys, 300, 1620, yc, B9LOSS, 12, p); ctx.restore();
    G.disc(ctx, 300, yc, 20, G.INK);
    tag(ctx, '一种可能', 1500, 380, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mc_fan = (ctx, s, lt, C) => { // 成千上万条岔路一起亮起，像一把散开的扇子
    const D = s.vizDur, k = E.io(inv(D * 0.05, D * 0.7, lt));
    b9fan(ctx, 360, 360, 1640, 620, 1, C.acc, 0.05 + 0.2 * k, 3, lerp(0.15, 1.15, k));
    tag(ctx, '密密麻麻', 1460, 380, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mc_hill = (ctx, s, lt, C) => { // 所有岔路的终点落进下方的格子，堆成一座小山
    const D = s.vizDur; b9fan(ctx, 120, 400, 1520, 450, 1, C.fg, 0.1, 3, 0.5);
    ctx.fillStyle = C.fg; ctx.fillRect(360, 900, 1200, 8);
    b9hist(ctx, 380, 1540, 896, 280, inv(D * 0.15, D * 0.85, lt), G.CREAM);
    b8txt(ctx, '更差', 380, 950, 36, C.fg); b8txt(ctx, '更好', 1540, 950, 36, C.fg);
    tag(ctx, '怎么分布', 1640, 420, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: G.INK });
  };
  VIZ.mc_worst = (ctx, s, lt, C) => { // 小山最左下角那一小块被标红，标「最坏的 1%」
    const D = s.vizDur; ctx.fillStyle = C.fg; ctx.fillRect(360, 900, 1200, 8);
    const wx = b9hist(ctx, 380, 1540, 896, 380, 1, rgba(G.CREAM, 0.7), { red: inv(D * 0.2, D * 0.4, lt) > 0 ? 2 : 0 });
    b8txt(ctx, '更差', 380, 950, 36, C.fg); b8txt(ctx, '更好', 1540, 950, 36, C.fg);
    b6down(ctx, wx + 20, 620, 840, B9LOSS, 10, inv(D * 0.3, D * 0.6, lt));
    tag(ctx, '最坏的 1%', wx + 180, 560, C, inv(D * 0.4, D * 0.75, lt), { px: 40, bg: B9LOSS, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mc_map = (ctx, s, lt, C) => { // 整张岔路图缩成一张地图，标「可能性」
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.6, lt)), w = lerp(1500, 900, k), h = lerp(700, 460, k);
    b9paper(ctx, 960, 640, w, h, G.CREAM, rgba(G.INK, 0.12 * k));
    ctx.save(); ctx.beginPath(); ctx.rect(960 - w / 2, 640 - h / 2, w, h); ctx.clip(); b9fan(ctx, 200, 960 - w / 2 + 50, 960 + w / 2 - 50, 640, 1, G.INK, 0.14, 3, lerp(1, 0.6, k)); ctx.restore();
    tag(ctx, '可能性', 960, 640 + h / 2 + 70, C, inv(D * 0.55, D * 0.85, lt), { px: 42, bg: G.INK, fg: C.bg });
  };
  VIZ.mc_crystal = (ctx, s, lt, C) => { // 地图旁边一个水晶球被打了个叉
    const D = s.vizDur; b9paper(ctx, 640, 640, 640, 420, G.CREAM, rgba(G.INK, 0.12));
    ctx.save(); ctx.beginPath(); ctx.rect(320, 430, 640, 420); ctx.clip(); b9fan(ctx, 120, 360, 920, 640, 1, G.INK, 0.15, 3, 0.5); ctx.restore();
    G.poly(ctx, [[1240, 860], [1500, 860], [1450, 790], [1290, 790]], G.INK);
    G.disc(ctx, 1370, 640, 170, rgba(G.CREAM, 0.85)); G.disc(ctx, 1310, 580, 40, rgba(G.CREAM, 0.95));
    b8cross(ctx, 1370, 640, 300, B9LOSS, inv(D * 0.35, D * 0.7, lt));
    tag(ctx, '不是预测', 1370, 950, C, inv(D * 0.6, D * 0.9, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mc_note = (ctx, s, lt, C) => { // 电脑入口塞进一张纸条，写「假设」
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.6, lt)); b9screen(ctx, 1120, 600, 760, 420, G.INK, rgba(G.CREAM, 0.9));
    ctx.save(); ctx.beginPath(); ctx.rect(740, 390, 760, 420); ctx.clip(); b9fan(ctx, 60, 790, 1450, 600, 1, G.INK, 0.15, 3, 0.6); ctx.restore();
    ctx.fillStyle = G.INK; ctx.fillRect(690, 540, 30, 120);
    b8card(ctx, lerp(380, 640, k), 600, 240, 130, G.CREAM, G.INK, '假设', 56, { rot: lerp(-0.12, 0, k) });
    tag(ctx, '输入', 500, 760, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: G.INK, fg: G.CREAM });
  };
  VIZ.mc_wrong = (ctx, s, lt, C) => { // 纸条上的字是错的，出口那座小山整个歪掉
    const D = s.vizDur, k = E.io(inv(D * 0.3, D * 0.75, lt));
    b8card(ctx, 520, 600, 300, 160, G.INK, G.CREAM, '假设', 64, { rot: -0.06 });
    b8cross(ctx, 520, 600, 170, B9LOSS, inv(D * 0.1, D * 0.4, lt));
    ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 8; ctx.setLineDash([16, 12]); ctx.beginPath(); ctx.moveTo(700, 600); ctx.lineTo(980, 600); ctx.stroke(); ctx.restore();
    G.poly(ctx, [[1010, 600], [980, 584], [980, 616]], G.INK);
    ctx.save(); ctx.translate(1340, 860); ctx.rotate(-0.35 * k); ctx.fillStyle = G.INK; ctx.fillRect(-300, 0, 600, 8);
    b9hist(ctx, -290, 290, 0, 300, 1, rgba(G.INK, 0.7), { bins: 14, skew: 1.4 * k }); ctx.restore();
    tag(ctx, '没用', 1340, 400, C, inv(D * 0.6, D * 0.9, lt), { px: 42, bg: B9LOSS, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.mc_signpost = (ctx, s, lt, C) => { // 回到开头的路口，路牌上写「假设？」
    const D = s.vizDur; b9fan(ctx, 200, 760, 1700, 760, 1, C.fg, 0.14, 3, 0.9);
    ctx.fillStyle = G.INK; ctx.fillRect(744, 470, 32, 300);
    b8card(ctx, 760, 450, 340, 130, G.CREAM, G.INK, '假设？', 60, { sc: E.oBack(inv(D * 0.2, D * 0.55, lt)) });
    G.disc(ctx, 760, 770, 22, G.CREAM);
    vizCaption(ctx, s, lt, C);
  };
  // ── #22 EWMA ── (recent days weigh more, shrinking by a fixed ratio; λ = 0.94 only as the corner note)
  VIZ.ewma_steps = (ctx, s, lt, C) => { // 一排脚印，越靠近镜头的越清楚，越远的越淡
    const D = s.vizDur; b9prints(ctx, lt, C, inv(D * 0.05, D * 0.7, lt));
    tag(ctx, '越近越清楚', 1460, 760, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_title = (ctx, s, lt, C) => { // 屏幕标题「EWMA」
    const D = s.vizDur; b6title(ctx, 'EWMA', W / 2, 460, 200, C.fg, inv(0.05, D * 0.5, lt));
    b9beam(ctx, 560, 1360, 880, 9, (i) => 30 + 90 * Math.pow(0.8, 8 - i), rgba(C.fg, 0.8), inv(D * 0.3, D * 0.9, lt));
  };
  VIZ.ewma_meter = (ctx, s, lt, C) => { // 一条起伏的收益线，上方一个刻度条在跳
    const D = s.vizDur, ys = b8ser(40, 1.7, 130, 1.2);
    ctx.fillStyle = rgba(C.fg, 0.3); ctx.fillRect(300, 760, 1100, 4);
    b8plot(ctx, ys, 300, 1400, 760, C.fg, 10, inv(D * 0.05, D * 0.85, lt));
    b9meter(ctx, 1600, 900, 520, 0.45 + 0.18 * Math.sin(lt * 3.1) * Math.sin(lt * 1.3), C.acc, rgba(C.fg, 0.15));
    tag(ctx, '最近的波动率', 1600, 300, C, inv(D * 0.45, D * 0.8, lt), { px: 36, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_equal = (ctx, s, lt, C) => { // 一排砝码大小完全一样，放在一根横杆上
    const D = s.vizDur; b9beam(ctx, 380, 1540, 820, 9, () => 110, G.INK, inv(D * 0.05, D * 0.6, lt));
    tag(ctx, '一样重', 1460, 460, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_grow = (ctx, s, lt, C) => { // 砝码从右到左变小，最右边今天的那个最大
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.6, lt));
    b9beam(ctx, 380, 1540, 840, 9, (i) => lerp(110, 40 + 150 * Math.pow(0.82, 8 - i), k), C.fg, 1);
    tag(ctx, '今天', 1540, 920, C, inv(D * 0.4, D * 0.7, lt), { px: 38, bg: C.acc, fg: G.INK });
    tag(ctx, '权重越大', 1400, 420, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_fade = (ctx, s, lt, C) => { // 左边的砝码越来越小，最后几乎看不见
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.7, lt));
    b9beam(ctx, 300, 1620, 840, 12, (i) => 12 + 170 * Math.pow(lerp(0.85, 0.72, k), 11 - i), G.INK, 1, { alpha: (i) => lerp(1, 0.15 + 0.85 * i / 11, k) });
    tag(ctx, '越久越轻', 520, 620, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_ratio = (ctx, s, lt, C) => { // 砝码大小按同一个比例缩小，角落小字「λ = 0.94（日数据）」
    const D = s.vizDur, n = 10;
    b9beam(ctx, 380, 1540, 820, n, (i) => 190 * Math.pow(0.84, n - 1 - i), C.fg, inv(D * 0.05, D * 0.6, lt));
    for (let i = 1; i < n; i++) { const p = inv(D * 0.3 + (n - i) * 0.05, D * 0.5 + (n - i) * 0.05, lt); if (p <= 0) continue; const x0 = lerp(380, 1540, i / (n - 1)), x1 = lerp(380, 1540, (i - 1) / (n - 1));
      ctx.save(); ctx.globalAlpha = clamp(p); ctx.strokeStyle = C.acc; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(x0 - 20, 930); ctx.quadraticCurveTo((x0 + x1) / 2, 980, x1 + 20, 930); ctx.stroke(); ctx.restore(); }
    tag(ctx, '同一个比例', 1400, 420, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: C.acc, fg: G.INK });
    b8txt(ctx, 'λ = 0.94（日数据）', 1620, 1000, 30, C.dim, { a: inv(D * 0.4, D * 0.7, lt) });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_press = (ctx, s, lt, C) => { // 最右边的大砝码压得刻度条往上一跳
    const D = s.vizDur, drop = E.oBack(inv(D * 0.15, D * 0.4, lt)), jump = E.oBack(inv(D * 0.35, D * 0.6, lt));
    b9beam(ctx, 340, 1100, 860, 8, (i) => 26 + 70 * Math.pow(0.8, 7 - i), rgba(G.INK, 0.6), 1);
    b9weight(ctx, 1300, lerp(480, 860, drop), 210, G.INK); ctx.fillStyle = G.INK; ctx.fillRect(1160, 860, 300, 14);
    b9meter(ctx, 1640, 900, 560, lerp(0.3, 0.8, jump), C.fg, rgba(G.INK, 0.15));
    b6upArrow(ctx, 1760, 820, 420, G.INK, 9, jump);
    tag(ctx, '更算数', 1300, 380, C, inv(D * 0.55, D * 0.85, lt), { px: 40, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_wave = (ctx, s, lt, C) => { // 一道大浪打来，刻度条立刻拉高
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.45, lt));
    b6sea(ctx, 820, 40 + 150 * k, lt, rgba(G.CREAM, 0.5), 0.4, 0.006, 0, 1420);
    b6sea(ctx, 860, 30 + 110 * k, lt, G.CREAM, 0, 0.007, 0, 1420);
    b9meter(ctx, 1640, 900, 560, lerp(0.25, 0.9, E.oBack(inv(D * 0.2, D * 0.45, lt))), G.CREAM, rgba(G.INK, 0.2));
    tag(ctx, '反应更快', 1640, 270, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_settle = (ctx, s, lt, C) => { // 浪过去，刻度条跟着降下来
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.7, lt));
    b6sea(ctx, 840, lerp(140, 18, k), lt, rgba(G.CREAM, 0.5), 0.4, 0.006, 0, 1420);
    b6sea(ctx, 870, lerp(100, 12, k), lt, G.CREAM, 0, 0.007, 0, 1420);
    b9meter(ctx, 1640, 900, 560, lerp(0.9, 0.3, k), G.CREAM, rgba(G.INK, 0.2));
    b6down(ctx, 1770, 420, 780, G.INK, 9, k);
    tag(ctx, '很快回落', 1500, 300, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.ewma_steps_end = (ctx, s, lt, C) => { // 回到那排脚印，镜头停在最近、最清楚的那一个
    const D = s.vizDur; b9prints(ctx, lt, C, 1, E.io(inv(0, D * 0.7, lt)));
    tag(ctx, '最近', 1460, 560, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  // ── #23 GARCH ── (named on screen only; long-run level + yesterday's shock + yesterday's swing; clustering, slow reversion)
  VIZ.garch_pond = (ctx, s, lt, C) => { // 一池水里落下一块石头，波纹一圈接一圈
    const D = s.vizDur, fall = inv(0, D * 0.25, lt);
    b9pond(ctx, 960, 760, 640, 190, rgba(C.fg, 0.12), C.fg, lt, inv(D * 0.2, D * 0.35, lt), 6, 0.3);
    if (fall < 1) b9stone(ctx, 960, lerp(320, 750, fall * fall), 40, C.acc);
    tag(ctx, '一圈接一圈', 1500, 420, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.garch_title = (ctx, s, lt, C) => { // 屏幕标题「GARCH」，不念全称
    const D = s.vizDur; b6title(ctx, 'GARCH', W / 2, 460, 200, C.fg, inv(0.05, D * 0.5, lt));
    b8plot(ctx, b9wave(50, 0.3, (f) => 30 + 120 * Math.exp(-Math.pow((f - 0.3) * 6, 2)) + 90 * Math.exp(-Math.pow((f - 0.75) * 7, 2))), 300, 1620, 800, G.CREAM, 9, inv(D * 0.2, D * 0.9, lt));
  };
  VIZ.garch_gear = (ctx, s, lt, C) => { // 上一条的砝码横杆旁边，又多出一个齿轮
    const D = s.vizDur, g = E.oBack(inv(D * 0.25, D * 0.55, lt));
    b9beam(ctx, 320, 1000, 820, 7, (i) => 30 + 120 * Math.pow(0.8, 6 - i), rgba(G.INK, 0.7), 1);
    if (g > 0) { ctx.save(); ctx.translate(1380, 680); ctx.scale(g, g); b6gear(ctx, 0, 0, 150, 10, lt * 0.8, C.acc, C.bg); ctx.restore(); }
    tag(ctx, '多走一步', 1380, 940, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.garch_boxes = (ctx, s, lt, C) => { // 三个格子排开，等着被点亮
    const D = s.vizDur; b9cells(ctx, C, [0, 0, 0], lt);
    tag(ctx, '今天的波动率', 960, 380, C, inv(D * 0.3, D * 0.7, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.garch_box1 = (ctx, s, lt, C) => { const D = s.vizDur; b9cells(ctx, C, [inv(D * 0.1, D * 0.4, lt), 0, 0], lt); vizCaption(ctx, s, lt, C); }; // 第一个格子亮起：一条水平的长线
  VIZ.garch_box2 = (ctx, s, lt, C) => { const D = s.vizDur; b9cells(ctx, C, [0.35, inv(D * 0.1, D * 0.4, lt), 0], lt); vizCaption(ctx, s, lt, C); }; // 第二个格子亮起：一块石头砸进水里
  VIZ.garch_box3 = (ctx, s, lt, C) => { const D = s.vizDur; b9cells(ctx, C, [0.35, 0.35, inv(D * 0.1, D * 0.4, lt)], lt); vizCaption(ctx, s, lt, C); }; // 第三个格子亮起：一段剧烈起伏的波纹
  VIZ.garch_carry = (ctx, s, lt, C) => { // 波纹从昨天的格子延伸到今天的格子
    const D = s.vizDur, p = inv(D * 0.1, D * 0.75, lt);
    [[560, '昨天'], [1360, '今天']].forEach(([x, t]) => { ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 7; ctx.beginPath(); ctx.roundRect(x - 220, 480, 440, 320, 26); ctx.stroke(); ctx.restore(); b8txt(ctx, t, x, 860, 42, G.INK); });
    b8plot(ctx, b9wave(60, 1.1, (f) => lerp(120, 90, f)), 380, 1540, 640, C.acc, 10, p);
    tag(ctx, '接着晃', 960, 400, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.garch_cluster = (ctx, s, lt, C) => { // 一条时间线上，大波纹一簇一簇挤在一起，中间夹着平静段
    const D = s.vizDur, env = (f) => 14 + 150 * Math.exp(-Math.pow((f - 0.2) * 9, 2)) + 170 * Math.exp(-Math.pow((f - 0.62) * 8, 2)) + 60 * Math.exp(-Math.pow((f - 0.9) * 12, 2));
    ctx.fillStyle = rgba(C.fg, 0.3); ctx.fillRect(260, 660, 1400, 4);
    b8plot(ctx, b9wave(110, 0.4, env), 260, 1660, 660, C.fg, 7, inv(D * 0.05, D * 0.8, lt));
    tag(ctx, '扎堆', 540, 430, C, inv(D * 0.4, D * 0.7, lt), { px: 38, bg: C.acc, fg: G.INK }); tag(ctx, '扎堆', 1130, 410, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: C.acc, fg: G.INK });
    tag(ctx, '平静', 830, 900, C, inv(D * 0.6, D * 0.9, lt), { px: 34, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.garch_revert = (ctx, s, lt, C) => { // 波纹逐渐变小，落回那条水平的长线
    const D = s.vizDur; b8dash(ctx, 260, 680, 1660, 680, G.INK, 6);
    b8plot(ctx, b9wave(80, 2.2, (f) => 10 + 200 * Math.exp(-f * 3.2)), 260, 1660, 680, G.CREAM, 9, inv(D * 0.05, D * 0.8, lt));
    tag(ctx, '长期水平', 1500, 780, C, inv(D * 0.5, D * 0.8, lt), { px: 36, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.garch_ledger = (ctx, s, lt, C) => { // 三个格子的背面是一本旧账本
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.55, lt));
    [520, 960, 1400].forEach((x, i) => { const sx = Math.cos(k * Math.PI); ctx.save(); ctx.translate(x, 560); ctx.scale(Math.abs(sx) * 0.6 + 0.001, 0.6);
      ctx.fillStyle = sx > 0 ? G.INK : rgba(G.INK, 0.4); ctx.beginPath(); ctx.roundRect(-180, -150, 360, 300, 26); ctx.fill(); ctx.restore(); });
    const bk = inv(D * 0.4, D * 0.75, lt); if (bk > 0) { ctx.save(); ctx.globalAlpha = clamp(bk); b6doc(ctx, 820, 820, 300, 200, G.CREAM, rgba(G.INK, 0.4), 1); b6doc(ctx, 1100, 820, 300, 200, G.CREAM, rgba(G.INK, 0.4), 1); ctx.fillStyle = G.INK; ctx.fillRect(955, 720, 10, 200); ctx.restore(); }
    tag(ctx, '过去的数据', 1500, 900, C, inv(D * 0.6, D * 0.9, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.garch_pond_end = (ctx, s, lt, C) => { // 回到水池：先平静，再起波纹，再慢慢平静
    const D = s.vizDur, a = inv(D * 0.25, D * 0.4, lt) * (1 - inv(D * 0.6, D * 0.95, lt));
    b9pond(ctx, 960, 760, 640, 190, rgba(C.fg, 0.12), C.fg, lt, a, 6, 0.3);
    tag(ctx, '平静', 600, 480, C, inv(0, D * 0.2, lt), { px: 36, bg: C.fg, fg: C.bg }); tag(ctx, '起波纹', 960, 430, C, inv(D * 0.3, D * 0.5, lt), { px: 36, bg: C.acc, fg: G.INK });
    tag(ctx, '又平静', 1320, 480, C, inv(D * 0.7, D * 0.9, lt), { px: 36, bg: C.fg, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  // ── #24 平稳性 ── (steady mean + steady swing size; prices wander, so model returns; unstable patterns → weaker inference)
  function b9route(ctx, x, y, col, dx, dy, p = 1) { ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 12; ctx.lineCap = 'round'; ctx.setLineDash([26, 18]); ctx.beginPath();
    const pts = [[-360, 120], [-200, -40], [0, 60], [180, -90], [360, -20]]; pts.slice(0, 1 + Math.round(4 * clamp(p))).forEach(([a, b], i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, x + a + dx, y + b + dy)); ctx.stroke(); ctx.restore(); }
  VIZ.stat_map = (ctx, s, lt, C) => { // 一张地图上的路线在纸上慢慢漂移
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.9, lt));
    b9paper(ctx, 960, 640, 1100, 560, G.CREAM, rgba(G.INK, 0.1));
    b9route(ctx, 960, 640, rgba(G.INK, 0.2), 0, 0); b9route(ctx, 960, 640, PAL.red.t[2], 120 * k, 70 * k);
    tag(ctx, '路线在漂', 1500, 340, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.stat_title = (ctx, s, lt, C) => { // 屏幕标题「Stationarity」
    const D = s.vizDur; b6title(ctx, 'Stationarity', W / 2, 460, 150, C.fg, inv(0.05, D * 0.5, lt));
    b8dash(ctx, 360, 790, 1560, 790, rgba(C.fg, 0.5), 4); b8plot(ctx, b8ser(44, 2.6, 80, 1.3), 360, 1560, 790, C.acc, 9, inv(D * 0.2, D * 0.9, lt));
  };
  VIZ.stat_mean = (ctx, s, lt, C) => { // 一条线围着一根水平中线上下晃，中线不动
    const D = s.vizDur; ctx.fillStyle = G.INK; ctx.fillRect(260, 676, 1400, 8);
    b8plot(ctx, b8ser(50, 0.8, 150, 1.2), 260, 1660, 680, C.acc, 10, inv(D * 0.05, D * 0.8, lt));
    tag(ctx, '平均值不动', 1500, 400, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.stat_band = (ctx, s, lt, C) => { // 线的上下包络是两条平行的虚线
    const D = s.vizDur, bp = inv(D * 0.35, D * 0.7, lt);
    b8plot(ctx, b8ser(50, 0.8, 150, 1.2), 260, 1660, 680, G.CREAM, 10, inv(D * 0.05, D * 0.5, lt));
    if (bp > 0) { ctx.save(); ctx.globalAlpha = clamp(bp); b8dash(ctx, 240, 520, 1680, 520, C.acc, 7); b8dash(ctx, 240, 840, 1680, 840, C.acc, 7); ctx.restore(); }
    tag(ctx, '幅度差不多', 1500, 930, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.stat_halves = (ctx, s, lt, C) => { // 前半段和后半段的线，形状看起来差不多
    const D = s.vizDur, k = E.io(inv(D * 0.4, D * 0.8, lt)), ys = b8ser(24, 0.5, 130, 1.3);
    b8plot(ctx, ys, 260, 900, 680, G.INK, 10, inv(D * 0.05, D * 0.35, lt));
    b8plot(ctx, b8ser(24, 0.62, 125, 1.3), 1020, 1660, lerp(680, 680, k), G.INK, 10, inv(D * 0.2, D * 0.5, lt));
    b8dash(ctx, 960, 440, 960, 920, rgba(G.INK, 0.5), 5);
    tag(ctx, '前半段', 580, 950, C, inv(D * 0.3, D * 0.6, lt), { px: 34, bg: G.INK, fg: C.bg }); tag(ctx, '后半段', 1340, 950, C, inv(D * 0.4, D * 0.7, lt), { px: 34, bg: G.INK, fg: C.bg });
    tag(ctx, '差不多', 960, 400, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.stat_calc = (ctx, s, lt, C) => { // 一台计算器的入口写着「请放平稳的数据」
    const D = s.vizDur; b7calc(ctx, 1160, 660, 440, 580, G.INK, G.CREAM, rgba(G.CREAM, 0.4));
    ctx.fillStyle = G.INK; ctx.fillRect(880, 420, 60, 140);
    b8card(ctx, 600, 470, 460, 110, G.CREAM, G.INK, '请放平稳的数据', 42, { sc: E.oBack(inv(D * 0.15, D * 0.5, lt)) });
    b8plot(ctx, b8ser(16, 0.8, 30, 1.4), 420, 780, 640, G.CREAM, 7, inv(D * 0.4, D * 0.8, lt));
    vizCaption(ctx, s, lt, C);
  };
  VIZ.stat_price = (ctx, s, lt, C) => { // 一条价格线没有中线，有时漂高有时漂低，越走越远
    const D = s.vizDur, ys = B9P[23].map((v, i) => v * 1.6 + 120 * Math.sin(i * 0.16));
    ctx.save(); ctx.globalAlpha = 0.16; G.poly(ctx, [[300, 660], [1640, 330], [1640, 990]], G.CREAM); ctx.restore();
    const [hx, hy] = b8plot(ctx, ys, 300, 1640, 660, G.CREAM, 10, inv(D * 0.05, D * 0.85, lt)); G.disc(ctx, hx, hy, 18, C.acc);
    tag(ctx, '一路漂', 1460, 330, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.stat_convert = (ctx, s, lt, C) => { // 价格线被转换成一条围着零上下晃的线
    const D = s.vizDur, ys = B9P[23].map((v, i) => v * 0.8 + 60 * Math.sin(i * 0.16)), rs = ys.map((v, i) => (i ? v - ys[i - 1] : 0) * 4);
    b8plot(ctx, ys, 340, 1000, 520, rgba(G.INK, 0.8), 8, inv(D * 0.05, D * 0.35, lt));
    const p = inv(D * 0.35, D * 0.85, lt); ctx.fillStyle = rgba(G.INK, 0.4); ctx.fillRect(1100, 846, 560, 4);
    b8plot(ctx, rs, 1100, 1660, 848, C.acc, 8, p); b8txt(ctx, '0', 1060, 848, 40, G.INK, { en: 1, a: p });
    ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(1010, 600); ctx.quadraticCurveTo(1080, 700, 1090, 790); ctx.stroke(); ctx.restore();
    tag(ctx, '价格', 670, 740, C, inv(D * 0.2, D * 0.5, lt), { px: 34, bg: G.INK, fg: G.CREAM }); tag(ctx, '收益率', 1380, 640, C, inv(D * 0.5, D * 0.8, lt), { px: 34, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  const B9BARS = Array.from({ length: 24 }, (_, i) => 150 * (b6rnd(i, 41) + b6rnd(i, 42) - 1));
  function b9bars(ctx, x0, x1, yc, p, o = {}) { // daily return bars: up = gain (green), DOWN = loss (red)
    const n = B9BARS.length, bw = (x1 - x0) / n;
    B9BARS.forEach((v, i) => { const g = E.o3(clamp(p * 1.5 - i * 0.02)); if (g <= 0) return; const h = (o.v ? o.v(v, i) : v) * g;
      ctx.fillStyle = h >= 0 ? (o.up || PAL.green.t[3]) : (o.down || B9LOSS); ctx.fillRect(x0 + i * bw + 6, h >= 0 ? yc - h : yc, bw - 12, Math.abs(h)); });
  }
  VIZ.stat_bars = (ctx, s, lt, C) => { // 每天一根小柱，向上是涨、向下是跌
    const D = s.vizDur; ctx.fillStyle = G.INK; ctx.fillRect(280, 677, 1360, 6);
    b9bars(ctx, 300, 1620, 680, inv(D * 0.05, D * 0.7, lt));
    tag(ctx, '涨', 1700, 540, C, inv(D * 0.4, D * 0.7, lt), { px: 38, bg: PAL.green.t[3], fg: G.INK }); tag(ctx, '跌', 1700, 820, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: B9LOSS, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.stat_range = (ctx, s, lt, C) => { // 小柱基本落在上下两条虚线之间
    const D = s.vizDur; ctx.fillStyle = G.CREAM; ctx.fillRect(280, 677, 1360, 6);
    b9bars(ctx, 300, 1620, 680, 1, { up: G.CREAM, down: PAL.red.t[1] });
    const bp = inv(D * 0.2, D * 0.55, lt); if (bp > 0) { ctx.save(); ctx.globalAlpha = clamp(bp); b8dash(ctx, 260, 520, 1660, 520, C.acc, 7); b8dash(ctx, 260, 840, 1660, 840, C.acc, 7); ctx.restore(); }
    tag(ctx, '来回晃', 1500, 400, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.stat_map_end = (ctx, s, lt, C) => { // 回到漂移的地图，旧路线和新路面对不上
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.6, lt));
    b9paper(ctx, 960, 640, 1100, 560, G.CREAM, rgba(G.INK, 0.1));
    ctx.save(); ctx.strokeStyle = rgba(G.INK, 0.5); ctx.lineWidth = 40; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(560, 820); ctx.bezierCurveTo(800, 520, 1100, 820, 1360, 560); ctx.stroke(); ctx.restore();
    b9route(ctx, 960, 640, PAL.red.t[2], -60 * k, -110 * k);
    b8cross(ctx, 1500, 360, 90, G.INK, inv(D * 0.5, D * 0.8, lt));
    tag(ctx, '对不上', 1500, 960, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  // ── #25 偏度 ── (lopsided distributions; negative skew = long tail on the LOSS side, drawn LEFT and DOWN; shape, not "losing money")
  VIZ.skew_hill = (ctx, s, lt, C) => { // 一座小山的山顶偏向右边，左边拖出长长的斜坡
    const D = s.vizDur; b9axis(ctx, C, rgba(C.fg, 0.6));
    b7curve(ctx, B9X0, B9X1, B9YB, 480, b9S, inv(D * 0.05, D * 0.7, lt), C.fg, 10, rgba(C.fg, 0.25));
    tag(ctx, '歪向一边', 1500, 400, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_title = (ctx, s, lt, C) => { // 屏幕标题「Skewness」
    const D = s.vizDur; b6title(ctx, 'Skewness', W / 2, 420, 160, C.fg, inv(0.05, D * 0.5, lt));
    b7curve(ctx, 520, 1400, 950, 300, b9S, inv(D * 0.2, D * 0.9, lt), C.acc, 9, rgba(C.acc, 0.2));
  };
  VIZ.skew_sym = (ctx, s, lt, C) => { // 一座对称的钟形小山，中间一条竖线
    const D = s.vizDur; b9axis(ctx, C, rgba(G.INK, 0.6));
    b7curve(ctx, B9X0, B9X1, B9YB, 480, b7N, inv(D * 0.05, D * 0.6, lt), G.INK, 10, rgba(G.INK, 0.12), 3.6, 'mid');
    b8dash(ctx, 960, 360, 960, B9YB, C.acc, 7, [18, 14]);
    tag(ctx, '对称吗？', 1460, 420, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_equal = (ctx, s, lt, C) => { // 竖线两边的尾巴长度相同
    const D = s.vizDur, p = E.io(inv(D * 0.2, D * 0.6, lt)); b9axis(ctx, C, rgba(G.INK, 0.6));
    b7curve(ctx, B9X0, B9X1, B9YB, 480, b7N, 1, G.INK, 10, rgba(G.INK, 0.12));
    b8dash(ctx, 960, 360, 960, B9YB, rgba(G.INK, 0.5), 5);
    ctx.fillStyle = G.INK; ctx.fillRect(960 - 600 * p, B9YB + 100, 600 * p, 10); ctx.fillRect(960, B9YB + 100, 600 * p, 10);
    tag(ctx, '左右一样长', 1460, 420, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_left = (ctx, s, lt, C) => { // 小山向右歪，左边亏损一侧的尾巴拖得又细又长
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.6, lt)), f = (u) => lerp(b7N(u), b9S(u), k); b9axis(ctx, C, rgba(G.INK, 0.6));
    b7area(ctx, B9X0, B9X1, B9YB, 480, f, B9X0, 760, rgba(B9LOSS, 0.55 * k));
    b7curve(ctx, B9X0, B9X1, B9YB, 480, f, 1, G.INK, 10, null);
    tag(ctx, '亏损一侧', 520, 560, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: B9LOSS, fg: G.CREAM });
    tag(ctx, '尾巴又细又长', 600, 1000, C, inv(D * 0.6, D * 0.9, lt), { px: 34, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_bulk = (ctx, s, lt, C) => { // 小山右侧那一大堆，标「多数时候小赚」
    const D = s.vizDur, k = inv(D * 0.15, D * 0.5, lt); b9axis(ctx, C, rgba(G.INK, 0.6));
    b7curve(ctx, B9X0, B9X1, B9YB, 480, b9S, 1, G.INK, 10, rgba(G.INK, 0.12));
    if (k > 0) { ctx.save(); ctx.globalAlpha = clamp(k); b7area(ctx, B9X0, B9X1, B9YB, 480, b9S, 1080, 1500, G.CREAM); ctx.restore(); }
    tag(ctx, '多数时候小赚', 1320, 330, C, inv(D * 0.45, D * 0.8, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_drop = (ctx, s, lt, C) => { // 左边长尾末端一个红点往下落
    const D = s.vizDur, f = Math.pow(inv(D * 0.3, D * 0.7, lt), 2); b9axis(ctx, C, rgba(G.INK, 0.6));
    b7curve(ctx, B9X0, B9X1, B9YB, 420, b9S, 1, G.INK, 10, rgba(G.INK, 0.1));
    G.disc(ctx, 420, lerp(B9YB - 30, 1010, f), 26, B9LOSS); b6down(ctx, 520, 640, 860, B9LOSS, 9, inv(D * 0.3, D * 0.6, lt));
    tag(ctx, '偶尔大亏', 640, 560, C, inv(D * 0.5, D * 0.8, lt), { px: 38, bg: B9LOSS, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_bars = (ctx, s, lt, C) => { // 一排小小的向上柱，中间突然一根很长的向下柱，角标「假设」
    const D = s.vizDur, yc = 560, n = 18, bw = 1240 / n; ctx.fillStyle = rgba(G.CREAM, 0.5); ctx.fillRect(320, yc - 2, 1280, 4);
    for (let i = 0; i < n; i++) { const g = E.o3(clamp(inv(D * 0.05, D * 0.7, lt) * 1.5 - i * 0.03)); if (g <= 0) continue; const big = i === 11, h = (big ? 400 : 40 + 24 * b6rnd(i, 7)) * g;
      ctx.fillStyle = big ? B9LOSS : PAL.green.t[2]; ctx.fillRect(340 + i * bw + 8, big ? yc : yc - h, bw - 16, h); }
    b8corner(ctx, '假设', C, inv(0.2, 0.7, lt));
    tag(ctx, '一下亏掉一大块', 1340, 900, C, inv(D * 0.6, D * 0.9, lt), { px: 36, bg: B9LOSS, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_shadow = (ctx, s, lt, C) => { // 一条平均线看着平稳，下方拖着一条长影子
    const D = s.vizDur, k = E.io(inv(D * 0.25, D * 0.8, lt));
    ctx.save(); const gr = ctx.createLinearGradient(0, 600, 0, 600 + 420 * k + 1); gr.addColorStop(0, rgba(G.INK, 0.55)); gr.addColorStop(1, rgba(G.INK, 0));
    ctx.fillStyle = gr; G.poly(ctx, [[360, 600], [1560, 600], [1420, 600 + 420 * k], [500, 600 + 420 * k]], gr); ctx.restore();
    ctx.fillStyle = G.CREAM; ctx.fillRect(320, 592, 1280 * E.o3(inv(D * 0.05, D * 0.3, lt)), 16);
    tag(ctx, '平均', 1680, 600, C, inv(D * 0.2, D * 0.5, lt), { px: 36, bg: G.CREAM, fg: G.INK }); tag(ctx, '尾巴很长', 960, 940, C, inv(D * 0.6, D * 0.9, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_fat = (ctx, s, lt, C) => { // 左边的长尾巴同时也变粗了，旁边小字「Fat Tails」
    const D = s.vizDur, k = E.io(inv(D * 0.15, D * 0.6, lt)), f = (u) => b9S(u) + k * 0.14 * Math.exp(-Math.pow(u + 2.2, 2) / 1.4); b9axis(ctx, C, rgba(G.INK, 0.6));
    b7area(ctx, B9X0, B9X1, B9YB, 460, f, B9X0, 820, rgba(B9LOSS, 0.5));
    b7curve(ctx, B9X0, B9X1, B9YB, 460, f, 1, G.INK, 10, null);
    b8txt(ctx, 'Fat Tails', 560, 640, 40, G.INK, { en: 1, a: inv(D * 0.45, D * 0.75, lt) });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_ruler = (ctx, s, lt, C) => { // 一把尺子量的是小山的轮廓，不是钱包
    const D = s.vizDur, rx = lerp(B9X0, 1360, inv(D * 0.1, D * 0.7, lt)); b9axis(ctx, C, rgba(G.INK, 0.6));
    const pts = b7curve(ctx, B9X0, 1360, B9YB, 420, b9S, 1, G.INK, 10, null);
    ctx.fillStyle = rgba(G.INK, 0.85); ctx.fillRect(rx - 24, 380, 48, B9YB - 380); ctx.fillStyle = C.bg; for (let j = 0; j < 16; j++) ctx.fillRect(rx - 24, 400 + j * 32, j % 4 ? 14 : 28, 4);
    ctx.fillStyle = G.INK; ctx.beginPath(); ctx.roundRect(1480, 560, 220, 150, 20); ctx.fill(); ctx.fillStyle = C.bg; ctx.fillRect(1620, 615, 60, 40);
    b8cross(ctx, 1590, 635, 200, B9LOSS, inv(D * 0.45, D * 0.75, lt));
    tag(ctx, '量的是形状', 1100, 330, C, inv(D * 0.55, D * 0.85, lt), { px: 38, bg: G.INK, fg: C.bg });
    vizCaption(ctx, s, lt, C);
  };
  VIZ.skew_end = (ctx, s, lt, C) => { // 回到那座歪向一边的小山，镜头顺着左边尾巴往下移
    const D = s.vizDur, k = E.io(inv(D * 0.1, D * 0.85, lt)), z = lerp(1, 1.5, k);
    ctx.save(); ctx.translate(lerp(960, 640, k), lerp(640, 560, k)); ctx.scale(z, z); ctx.translate(-960, -640);
    ctx.fillStyle = rgba(C.fg, 0.6); ctx.fillRect(B9X0 - 40, B9YB, B9X1 - B9X0 + 80, 6); b7curve(ctx, B9X0, B9X1, B9YB, 480, b9S, 1, C.fg, 10, rgba(C.fg, 0.2));
    b7area(ctx, B9X0, B9X1, B9YB, 480, b9S, B9X0, 760, rgba(B9LOSS, 0.6 * k)); ctx.restore();
    b6down(ctx, 300, 640, 960, B9LOSS, 10, inv(D * 0.4, D * 0.8, lt));
    tag(ctx, '尾巴往哪拖？', 1440, 400, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: C.acc, fg: G.INK });
    vizCaption(ctx, s, lt, C);
  };
  // ───────── finance-v003 scene library, batch 4 (CAPM long, 13 lines, 2026-10-30) ─────────
  // Metaphor (金融专家): companies = unnamed small buildings, the market = the ground they stand on.
  // Company trouble = smoke on one roof (diluted by owning many); market risk = the whole ground sinks.
  // Required return = a pillar in two parts (起步价 + 补偿). No tickers, fund or company names,
  // no K-lines, no rising-only curves (the 晃动 curve oscillates), no dice/casino props.
  Object.assign(VPAL, {
    balance_half: 'cream', ruler_capm: 'ink', split_smoke: 'ochre', row_dilute: 'green', ground_sink: 'purple',
    all_sink: 'red', empty_box: 'gold', pillar_split: 'ink', pillar_base: 'cream', pillar_wiggle: 'purple',
    expect_dashed: 'ochre', ruler_crystal: 'green', balance_settle: 'gold',
  });
  function house(ctx, x, y, w, col, win) { // small unnamed company building, y = ground
    const h = w * 1.25;
    G.poly(ctx, [[x - w * 0.58, y - h], [x + w * 0.58, y - h], [x, y - h - w * 0.45]], col);
    ctx.fillStyle = col; ctx.fillRect(x - w / 2, y - h, w, h);
    ctx.fillStyle = win; for (let r = 0; r < 2; r++) for (let c = 0; c < 2; c++) ctx.fillRect(x - w * 0.32 + c * w * 0.4, y - h * 0.85 + r * h * 0.38, w * 0.24, h * 0.22);
  }
  function pans(ctx, cx, py, arm, tilt, labs, cols, C, lt, w = 120) { // beam balance, labels on the pans
    ctx.save(); ctx.translate(cx, py); ctx.rotate(tilt);
    ctx.fillStyle = C.fg; ctx.fillRect(-arm, -9, arm * 2, 18); G.disc(ctx, 0, 0, 24, C.fg);
    [-1, 1].forEach((sd, i) => {
      ctx.save(); ctx.translate(sd * arm, 0); ctx.rotate(-tilt);
      ctx.strokeStyle = C.fg; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-w * 0.75, 160); ctx.moveTo(0, 0); ctx.lineTo(w * 0.75, 160); ctx.stroke();
      ctx.fillStyle = C.fg; ctx.beginPath(); ctx.ellipse(0, 168, w, 28, 0, 0, Math.PI); ctx.fill();
      tag(ctx, labs[i], 0, 125, C, inv(0.2 + i * 0.2, 0.7 + i * 0.2, lt), { px: 36, bg: cols[i], fg: G.INK });
      ctx.restore();
    });
    ctx.restore();
  }
  function pillar(ctx, x, yb, w, hBase, hTop, pBase, pTop, C, o = {}) { // required-return pillar, yb = zero line
    ctx.save(); ctx.strokeStyle = rgba(C.fg, 0.55); ctx.lineWidth = 5; ctx.setLineDash(o.dash ? [16, 12] : []);
    ctx.strokeRect(x - w / 2, yb - hBase - hTop, w, hBase + hTop); ctx.restore();
    if (pBase > 0) { ctx.fillStyle = o.baseCol || PAL.green.t[2]; ctx.fillRect(x - w / 2, yb - hBase * pBase, w, hBase * pBase); }
    if (pTop > 0) { ctx.fillStyle = o.topCol || PAL.red.t[2]; ctx.fillRect(x - w / 2, yb - hBase - hTop * pTop, w, hTop * pTop); }
  }
  function crystal(ctx, x, y, r, col) {
    ctx.save(); const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.1, x, y, r);
    g.addColorStop(0, rgba(G.CREAM, 0.95)); g.addColorStop(1, col); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = G.INK; G.poly(ctx, [[x - r * 0.7, y + r * 0.85], [x + r * 0.7, y + r * 0.85], [x + r * 0.9, y + r * 1.25], [x - r * 0.9, y + r * 1.25]], G.INK); ctx.restore();
  }
  function crossOut(ctx, x, y, r, p, col = PAL.red.t[2]) {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 26; ctx.lineCap = 'round';
    const a = clamp(p * 2), b = clamp(p * 2 - 1);
    ctx.beginPath(); ctx.moveTo(x - r, y - r); ctx.lineTo(x - r + 2 * r * a, y - r + 2 * r * a); ctx.stroke();
    if (b > 0) { ctx.beginPath(); ctx.moveTo(x + r, y - r); ctx.lineTo(x + r - 2 * r * b, y - r + 2 * r * b); ctx.stroke(); }
    ctx.restore();
  }

  VIZ.balance_half = (ctx, s, lt, C) => { // 天平：风险 / 回报，只翘起一半 — fulcrum right of centre, big ½
    const D = s.vizDur, cx = 1240, py = 430;
    const tilt = -0.07 * E.oBack(inv(0.5, D * 0.55, lt), 1.4) + 0.01 * Math.sin(lt * 3);
    ctx.fillStyle = C.fg; G.poly(ctx, [[cx - 30, py], [cx + 30, py], [cx + 90, 930], [cx - 90, 930]], C.fg); ctx.fillRect(cx - 200, 925, 400, 26);
    pans(ctx, cx, py, 430, tilt, ['风险', '回报'], [PAL.red.t[3], PAL.green.t[3]], C, lt, 130);
    G.maskText(ctx, '½', 330, 800, F.en(900, 300), C.fg, inv(D * 0.45, D * 0.75, lt));
    tag(ctx, '不全对', 420, 900, C, inv(D * 0.55, D * 0.85, lt), { px: 44, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.ruler_capm = (ctx, s, lt, C) => { // 一把尺子：一头「风险」一头「该要的回报」，标 CAPM — vertical
    const D = s.vizDur, x = 1300, y0 = 980, y1 = 330, p = E.io(inv(0.1, 0.9, lt));
    const yt = lerp(y0, y1, p);
    ctx.fillStyle = G.CREAM; ctx.fillRect(x - 70, yt, 140, y0 - yt);
    ctx.fillStyle = G.INK; for (let i = 0; i <= 24; i++) { const y = y0 - i * (y0 - y1) / 24; if (y < yt) break; ctx.fillRect(x - 70, y - 2, i % 4 === 0 ? 60 : 30, 4); }
    ctx.save(); ctx.translate(x + 20, (y0 + y1) / 2); ctx.rotate(-Math.PI / 2);
    G.maskText(ctx, 'CAPM', 0, 22, F.en(900, 70), G.INK, inv(0.9, 1.5, lt) * (p > 0.7 ? 1 : 0), { align: 'center', ls: '10px' }); ctx.restore();
    tag(ctx, '风险', x + 230, y0 - 30, C, inv(0.4, 0.9, lt), { px: 40, bg: PAL.red.t[3], fg: G.INK });
    tag(ctx, '该要的回报', x + 300, y1 + 30, C, inv(D * 0.4, D * 0.7, lt), { px: 40, bg: GOLD, fg: G.INK });
    const m = lerp(y0 - 60, y1 + 60, E.io(inv(D * 0.4, D * 0.9, lt)));
    G.poly(ctx, [[x - 90, m], [x - 140, m - 30], [x - 140, m + 30]], GOLD);
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.split_smoke = (ctx, s, lt, C) => { // 一分为二：左边小楼冒烟，右边空着
    const D = s.vizDur, gy = 920, k = E.o3(inv(0.4, D * 0.6, lt));
    ctx.fillStyle = rgba(C.fg, 0.1); ctx.fillRect(140, 330, 780, 650); ctx.fillRect(1000, 330, 780, 650);
    ctx.fillStyle = rgba(C.fg, 0.4); ctx.fillRect(140, gy, 780, 8);
    house(ctx, 530, gy, 220, C.fg, C.bg);
    if (k > 0) smoke(ctx, 530, gy - 400, lt, k, rgba(G.INK, 0.45));
    ctx.save(); ctx.strokeStyle = rgba(C.fg, 0.5); ctx.lineWidth = 5; ctx.setLineDash([18, 14]); ctx.strokeRect(1060, 390, 660, 530); ctx.restore();
    G.maskText(ctx, '?', 1390, 720, F.en(900, 200), rgba(C.fg, 0.5), inv(D * 0.5, D * 0.8, lt), { align: 'center' });
    tag(ctx, '一家自己出事', 530, 1010, C, inv(0.5, 1.0, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.row_dilute = (ctx, s, lt, C) => { // 冒烟的小楼旁排出一整排小楼，烟被稀释
    const D = s.vizDur, gy = 900, n = 9, f = inv(D * 0.15, D * 0.7, lt);
    ctx.fillStyle = rgba(C.fg, 0.35); ctx.fillRect(120, gy, 1680, 8);
    for (let i = 0; i < n; i++) {
      const x = 220 + i * 185, p = i === 0 ? 1 : E.oBack(clamp(f * n - (i - 1)));
      if (p <= 0) continue;
      ctx.save(); ctx.translate(x, gy); ctx.scale(p, p); ctx.translate(-x, -gy); house(ctx, x, gy, 120, i ? rgba(C.fg, 0.85) : C.fg, C.bg); ctx.restore();
    }
    smoke(ctx, 220, gy - 230, lt, 1 - 0.85 * E.io(f), rgba(G.INK, 0.5));
    tag(ctx, '摊薄', 1500, 420, C, inv(D * 0.6, D * 0.85, lt), { px: 52, bg: G.CREAM, fg: G.INK });
    G.typeText(ctx, '1 / ' + Math.max(1, Math.round(1 + f * (n - 1))), 1440, 560, F.en(900, 72), C.fg, inv(D * 0.2, D * 0.4, lt), { caret: false });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.ground_sink = (ctx, s, lt, C) => { // 右边整片地面一起下沉，上面所有小楼一起往下走
    const D = s.vizDur, d = 170 * E.io3(inv(D * 0.25, D * 0.8, lt)), gy = 760 + d;
    ctx.fillStyle = rgba(C.fg, 0.12); ctx.fillRect(140, 760, 700, 300);
    house(ctx, 490, 760, 150, rgba(C.fg, 0.5), C.bg);
    ctx.fillStyle = C.fg; ctx.fillRect(900, gy, 900, H - gy);
    for (let i = 0; i < 5; i++) house(ctx, 990 + i * 170, gy, 110, G.CREAM, C.bg);
    ctx.strokeStyle = rgba(C.fg, 0.5); ctx.lineWidth = 4; ctx.setLineDash([12, 10]); ctx.beginPath(); ctx.moveTo(900, 760); ctx.lineTo(1800, 760); ctx.stroke(); ctx.setLineDash([]);
    arrowV(ctx, 1830, 770, gy - 10, C.fg, 6, inv(D * 0.3, D * 0.6, lt));
    tag(ctx, '经济不好', 1100, 420, C, inv(D * 0.2, D * 0.45, lt), { px: 34, bg: G.CREAM, fg: G.INK });
    tag(ctx, '利率大变', 1500, 480, C, inv(D * 0.3, D * 0.55, lt), { px: 34, bg: G.CREAM, fg: G.INK });
    tag(ctx, '整个市场', 1350, 1010, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.all_sink = (ctx, s, lt, C) => { // 小楼再多，地面下沉时全都跟着沉，一栋也没躲开 — 3 rows
    const D = s.vizDur, d = 130 * E.io3(inv(D * 0.3, D * 0.8, lt));
    for (let r = 0; r < 3; r++) {
      const gy = 560 + r * 170 + d * (0.7 + 0.15 * r);
      ctx.fillStyle = rgba(G.INK, 0.25 + 0.1 * r); ctx.fillRect(160, gy, 1600, 14);
      for (let i = 0; i < 10; i++) { const p = pop(lt, 0.05 + (r * 10 + i) * 0.02, 0.4 + (r * 10 + i) * 0.02); if (p > 0) house(ctx, 230 + i * 160 + (r % 2) * 40, gy, 70 * p, G.CREAM, C.bg); }
    }
    G.maskText(ctx, '躲开 0', 1500, 400, F.zh(900, 72), G.CREAM, inv(D * 0.6, D * 0.85, lt));
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.empty_box = (ctx, s, lt, C) => { // 左边的烟旁放一个空的奖励盒，盖子开着，里面什么都没有
    const D = s.vizDur, gy = 900, bx = 1180, lid = E.oBack(inv(0.4, D * 0.5, lt));
    house(ctx, 470, gy, 170, rgba(G.INK, 0.8), C.bg); smoke(ctx, 470, gy - 330, lt, 0.5, rgba(G.INK, 0.35));
    ctx.fillStyle = G.INK; ctx.fillRect(bx - 230, gy - 300, 460, 300);
    ctx.fillStyle = rgba(G.CREAM, 0.15); ctx.fillRect(bx - 200, gy - 280, 400, 260);
    ctx.save(); ctx.translate(bx - 240, gy - 300); ctx.rotate(-1.25 * lid); ctx.fillStyle = G.INK; ctx.fillRect(0, -40, 480, 40); ctx.restore();
    ctx.strokeStyle = G.CREAM; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(bx - 60, gy - 150); ctx.lineTo(bx + 60, gy - 150); ctx.stroke();
    tag(ctx, '空的', bx, gy - 150, C, inv(D * 0.5, D * 0.75, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    tag(ctx, '不多给回报', 1560, 420, C, inv(D * 0.6, D * 0.85, lt), { px: 44, bg: G.INK, fg: GOLD });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.pillar_split = (ctx, s, lt, C) => { // 一根回报柱子分成上下两段，先亮出分界线 — centred
    const D = s.vizDur, x = W / 2, yb = 980, p = E.io(inv(0.05, 0.6, lt)), cut = inv(D * 0.35, D * 0.6, lt);
    ctx.fillStyle = rgba(C.fg, 0.4); ctx.fillRect(500, yb, 920, 6);
    ctx.fillStyle = rgba(C.fg, 0.18); ctx.fillRect(x - 130, yb - 600 * p, 260, 600 * p);
    goldLine(ctx, x - 170, x + 170, yb - 300, cut, 14, GOLD, 24);
    G.maskText(ctx, '1', x + 220, yb - 120, F.en(900, 90), C.fg, inv(D * 0.55, D * 0.75, lt));
    G.maskText(ctx, '2', x + 220, yb - 420, F.en(900, 90), C.fg, inv(D * 0.65, D * 0.85, lt));
    tag(ctx, '两块', 560, 520, C, inv(D * 0.5, D * 0.8, lt), { px: 52, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.pillar_base = (ctx, s, lt, C) => { // 柱子底下那段亮起，标「起步价（如国债）」 — pillar left
    const D = s.vizDur, x = 560, yb = 980;
    ctx.fillStyle = rgba(G.INK, 0.4); ctx.fillRect(260, yb, 600, 6);
    pillar(ctx, x, yb, 240, 280, 300, E.o3(inv(D * 0.2, D * 0.6, lt)), 0, { fg: G.INK }, { baseCol: PAL.green.t[2] });
    ctx.fillStyle = rgba(G.INK, 0.6); ctx.fillRect(x - 160, yb - 282, 320, 4);
    ctx.strokeStyle = rgba(G.INK, 0.5); ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x + 140, yb - 140); ctx.lineTo(1060, yb - 140); ctx.stroke();
    tag(ctx, '起步价（如国债）', 1340, yb - 140, C, inv(D * 0.45, D * 0.75, lt), { px: 44, bg: PAL.green.t[2], fg: G.CREAM });
    G.typeText(ctx, '几乎没风险', 1150, yb - 260, F.zh(800, 40), rgba(G.INK, 0.7), inv(D * 0.6, D * 0.85, lt), { caret: false });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) }, { y: 230 });
  };
  VIZ.pillar_wiggle = (ctx, s, lt, C) => { // 柱子上面那段随晃动的曲线变高：晃得越猛，这段越高 (curve oscillates)
    const D = s.vizDur, amp = E.io(inv(D * 0.15, D * 0.85, lt)), yc = 680, x0 = 160, x1 = 1060;
    ctx.fillStyle = rgba(C.fg, 0.2); ctx.fillRect(x0, yc - 1, x1 - x0, 2);
    ctx.strokeStyle = G.CREAM; ctx.lineWidth = 8; ctx.lineJoin = 'round'; ctx.beginPath();
    for (let i = 0; i <= 120; i++) { const u = i / 120, x = lerp(x0, x1, u), a = 30 + 190 * amp * u; const y = yc + Math.sin(u * 22 + lt * 4) * a; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
    ctx.stroke();
    tag(ctx, '跟大盘一起晃', 450, 960, C, inv(0.2, 0.7, lt), { px: 36, bg: G.CREAM, fg: G.INK });
    const px = 1480, yb = 980;
    ctx.fillStyle = rgba(C.fg, 0.4); ctx.fillRect(1260, yb, 440, 6);
    pillar(ctx, px, yb, 220, 200, 400, 1, 0.15 + 0.85 * amp, C, { baseCol: rgba(PAL.green.t[2], 0.8), topCol: GOLD });
    tag(ctx, '补偿', px, yb - 200 - 400 * (0.15 + 0.85 * amp) - 50, C, inv(D * 0.3, D * 0.5, lt), { px: 40, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.expect_dashed = (ctx, s, lt, C) => { // 柱子变成虚线的「预期」，实际柱子有的矮一截、有的掉到零线以下
    const D = s.vizDur, y0 = 760, f = inv(D * 0.3, D * 0.8, lt);
    ctx.fillStyle = G.INK; ctx.fillRect(160, y0 - 3, 1600, 6);
    G.typeText(ctx, '0', 120, y0 + 14, F.en(900, 40), G.INK, 1, { caret: false });
    ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 6; ctx.setLineDash([16, 12]); ctx.strokeRect(330, y0 - 360, 200, 360); ctx.restore();
    tag(ctx, '预期', 430, y0 + 70, C, inv(0.2, 0.6, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    const act = [0.72, 0.4, -0.35, 0.9, 0.15, -0.6];
    act.forEach((h, i) => {
      const x = 760 + i * 170, p = E.o3(clamp(f * 6 - i)), hh = 360 * h * p;
      ctx.fillStyle = h < 0 ? PAL.red.t[2] : rgba(G.CREAM, 0.9);
      if (hh >= 0) ctx.fillRect(x, y0 - hh, 110, hh); else ctx.fillRect(x, y0, 110, -hh);
    });
    tag(ctx, '实际', 1270, 400, C, inv(D * 0.4, D * 0.7, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    tag(ctx, '可能亏', 1480, y0 + 280, C, inv(D * 0.65, D * 0.9, lt), { px: 36, bg: PAL.red.t[2], fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.ruler_crystal = (ctx, s, lt, C) => { // CAPM 尺子放在桌上，旁边一个水晶球被打叉
    const D = s.vizDur, ty = 860;
    ctx.fillStyle = rgba(G.INK, 0.35); ctx.fillRect(100, ty, 1720, 30);
    const p = E.io(inv(0.05, 0.6, lt));
    ctx.fillStyle = G.CREAM; ctx.fillRect(220, ty - 90, 820 * p, 90);
    ctx.fillStyle = G.INK; for (let i = 0; i <= 20; i++) { const x = 220 + i * 41; if (x > 220 + 820 * p) break; ctx.fillRect(x - 2, ty - 90, 4, i % 4 ? 26 : 50); }
    G.maskText(ctx, 'CAPM', 630, ty - 18, F.en(900, 56), G.INK, inv(0.5, 1.0, lt), { align: 'center', ls: '8px' });
    tag(ctx, '量该要多少', 630, ty - 190, C, inv(0.6, 1.1, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    crystal(ctx, 1420, ty - 260, 150, PAL.purple.t[2]);
    crossOut(ctx, 1420, ty - 230, 190, E.o3(inv(D * 0.4, D * 0.75, lt)));
    tag(ctx, '不预测涨跌', 1420, 330, C, inv(D * 0.6, D * 0.85, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.balance_settle = (ctx, s, lt, C) => { // 回到整片下沉的地面，天平稳稳翘向「躲不掉的风险」 — balance left, sunk ground
    const D = s.vizDur, gy = 900;
    ctx.fillStyle = rgba(G.INK, 0.85); ctx.fillRect(0, gy, W, H - gy);
    for (let i = 0; i < 6; i++) house(ctx, 1000 + i * 150, gy, 90, rgba(G.CREAM, 0.85), rgba(G.INK, 0.8));
    const cx = 560, py = 470, tilt = 0.16 * E.io3(inv(0.2, D * 0.6, lt));
    G.poly(ctx, [[cx - 26, py], [cx + 26, py], [cx + 80, gy], [cx - 80, gy]], C.fg);
    pans(ctx, cx, py, 330, tilt, ['躲得掉', '躲不掉的风险'], [rgba(G.CREAM, 0.7), PAL.red.t[2]], C, lt, 110);
    tag(ctx, '才该多要回报', 1380, 520, C, inv(D * 0.5, D * 0.8, lt), { px: 48, bg: G.INK, fg: GOLD });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };

  // ───────── finance-v003 scene library, batch 5 (Sharpe long, 13 lines, 2026-10-30) ─────────
  // Metaphor (台词教父 / 金融专家): two hypothetical portfolios 甲 / 乙 only (no real funds, no formulas).
  // Return = a pillar above the zero line; the 国债 base is cut off the bottom; risk = how much the return
  // line swings (drawn up AND down, losses below zero), carried as a sandbag (bigger bag = bigger swings).
  // Screen shows 'Sharpe' (mixed case), the voice says 夏普比率.
  Object.assign(VPAL, {
    twin_q: 'ochre', score_sharpe: 'ink', baskets_8: 'cream', calm_wild: 'purple', pillars_cut: 'green',
    remain_six: 'gold', swing_box: 'red', sandbags: 'cream', coin_stack: 'ink', score_fill: 'green',
    card_fog: 'purple', ruler_chair: 'ochre', bag_pillars: 'gold',
  });
  const SHARPE = 'Sharpe';
  const wigA = (u, lt) => 0.10 * Math.sin(u * 19 + lt * 1.5) + 0.06 * Math.sin(u * 41); // 甲: small ripples
  const wigB = (u, lt) => 0.95 * Math.sin(u * 13 + 0.6 + lt * 1.2) + 0.35 * Math.sin(u * 31 + 1.3); // 乙: big swings
  function zeroLine(ctx, x0, x1, y, col) { ctx.fillStyle = col; ctx.fillRect(x0, y - 2, x1 - x0, 4); }
  function retLine(ctx, f, x0, x1, yc, amp, rev, w, col, lt) { // oscillating return line, y up = gain
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.beginPath();
    const n = Math.max(2, Math.round(160 * clamp(rev)));
    for (let i = 0; i <= n; i++) { const u = i / 160, x = lerp(x0, x1, u), y = yc - f(u, lt) * amp; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
    ctx.stroke(); ctx.restore();
  }
  function sandbag(ctx, x, y, r, col, lab, labCol) { // tied sack, y = centre
    ctx.save(); ctx.fillStyle = col; ctx.beginPath();
    ctx.moveTo(x - r * 0.35, y - r * 0.9);
    ctx.bezierCurveTo(x - r * 1.15, y - r * 0.5, x - r * 1.1, y + r * 0.95, x, y + r * 0.95);
    ctx.bezierCurveTo(x + r * 1.1, y + r * 0.95, x + r * 1.15, y - r * 0.5, x + r * 0.35, y - r * 0.9);
    ctx.closePath(); ctx.fill();
    G.poly(ctx, [[x - r * 0.35, y - r * 0.9], [x + r * 0.35, y - r * 0.9], [x + r * 0.5, y - r * 1.25], [x - r * 0.5, y - r * 1.25]], col);
    ctx.fillStyle = rgba(G.INK, 0.35); ctx.fillRect(x - r * 0.42, y - r * 0.98, r * 0.84, Math.max(4, r * 0.1));
    if (lab) { ctx.font = F.zh(900, Math.max(22, r * 0.42)); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = labCol || G.INK; ctx.fillText(lab, x, y + r * 0.2); }
    ctx.restore();
  }
  function scoreCard(ctx, x, y, w, h, p, o = {}) { // card with a 'Sharpe' header, (x,y) = top-left
    if (p <= 0) return;
    ctx.save(); ctx.globalAlpha = clamp(p * 1.6);
    ctx.fillStyle = o.bg || G.CREAM; ctx.beginPath(); ctx.roundRect(x, y, w, h, 22); ctx.fill();
    ctx.fillStyle = o.head || G.INK; ctx.beginPath(); ctx.roundRect(x, y, w, Math.min(130, h * 0.3), [22, 22, 0, 0]); ctx.fill();
    ctx.restore();
    G.maskText(ctx, o.title || SHARPE, x + w / 2, y + Math.min(130, h * 0.3) / 2 + (o.tpx || 64) * 0.36, F.en(900, o.tpx || 64), o.titleCol || GOLD, inv(0.1, 0.5, p * 1.2), { align: 'center', ls: '4px' });
  }
  function twoPillars(ctx, xs, yb, w, hs, cols, ps) {
    xs.forEach((x, i) => { const hh = hs[i] * clamp(ps[i]); ctx.fillStyle = cols[i]; ctx.fillRect(x - w / 2, yb - hh, w, hh); });
  }

  VIZ.twin_q = (ctx, s, lt, C) => { // 两根一样高的收益柱子并排，中间一个问号
    const D = s.vizDur, yb = 960, g = E.o3(inv(0.1, D * 0.45, lt));
    zeroLine(ctx, 560, 1640, yb, rgba(C.fg, 0.5));
    twoPillars(ctx, [800, 1400], yb, 230, [520, 520], [G.CREAM, rgba(G.INK, 0.85)], [g, g]);
    ctx.save(); ctx.setLineDash([14, 12]); ctx.strokeStyle = rgba(C.fg, 0.6); ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(660, yb - 520 * g); ctx.lineTo(1540, yb - 520 * g); ctx.stroke(); ctx.restore();
    tag(ctx, '甲', 800, yb - 520 * g - 50, C, inv(D * 0.3, D * 0.5, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    tag(ctx, '乙', 1400, yb - 520 * g - 50, C, inv(D * 0.35, D * 0.55, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    const q = E.oBack(inv(D * 0.4, D * 0.7, lt), 1.6), bob = Math.sin(lt * 3) * 10;
    G.maskText(ctx, '?', 1100, 720 + bob, F.en(900, 300 * Math.max(0.01, q)), C.fg, q > 0 ? 1 : 0, { align: 'center' });
    tag(ctx, '一样高', 1100, 420, C, inv(D * 0.55, D * 0.85, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.score_sharpe = (ctx, s, lt, C) => { // 一张记分卡，卡头写「Sharpe」 — card tilts in from the right
    const D = s.vizDur, p = E.oBack(inv(0.15, D * 0.45, lt), 1.2), x = 1000, y = 340, w = 640, h = 600;
    ctx.save(); ctx.translate(x + w / 2, y + h / 2); ctx.rotate(0.06 * (1 - p) + 0.012 * Math.sin(lt * 2)); ctx.translate(-(x + w / 2), -(y + h / 2));
    scoreCard(ctx, x, y, w, h, p, { tpx: 76 });
    ctx.fillStyle = rgba(G.INK, 0.18); for (let i = 0; i < 4; i++) ctx.fillRect(x + 60, y + 200 + i * 90, w - 120, 22);
    ctx.restore();
    tag(ctx, '比的是什么？', 560, 760, C, inv(D * 0.5, D * 0.8, lt), { px: 44, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.baskets_8 = (ctx, s, lt, C) => { // 两个篮子贴「甲」「乙」，头顶各亮「+8%」，角标「假设」
    const D = s.vizDur, gy = 900;
    [[700, '甲', PAL.ochre.t[2]], [1300, '乙', PAL.purple.t[2]]].forEach(([x, lab, col], i) => {
      const k = E.oBack(inv(0.1 + i * 0.2, 0.6 + i * 0.2, lt));
      if (k <= 0) return;
      ctx.save(); ctx.translate(x, gy); ctx.scale(k, k); ctx.translate(-x, -gy);
      basket(ctx, x, gy - 260, 380, 260, col);
      ctx.restore();
      tag(ctx, lab, x, gy - 120, C, k, { px: 56, bg: G.CREAM, fg: G.INK });
      G.maskText(ctx, '+8%', x, gy - 380, F.en(900, 110), PAL.green.t[3] || G.INK, inv(D * 0.35 + i * 0.1, D * 0.6 + i * 0.1, lt), { align: 'center' });
    });
    tag(ctx, '假设', 1660, 380, C, inv(D * 0.5, D * 0.75, lt), { px: 34, bg: G.INK, fg: G.CREAM });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.calm_wild = (ctx, s, lt, C) => { // 两条收益线：甲贴着平线微微起伏，乙大起大落，跌的部分往下
    const D = s.vizDur, x0 = 300, x1 = 1700, rev = E.io(inv(0.1, D * 0.7, lt));
    const ya = 470, yb = 800;
    [[ya, '甲', wigA, 120, G.CREAM], [yb, '乙', wigB, 150, GOLD]].forEach(([yc, lab, f, amp, col]) => {
      zeroLine(ctx, x0, x1, yc, rgba(C.fg, 0.35));
      ctx.save(); ctx.beginPath(); ctx.rect(x0, yc, x1 - x0, 260); ctx.clip();
      ctx.fillStyle = rgba(PAL.red.t[2], 0.55); ctx.beginPath(); ctx.moveTo(x0, yc);
      const n = Math.round(160 * rev); for (let i = 0; i <= n; i++) { const u = i / 160; ctx.lineTo(lerp(x0, x1, u), yc - f(u, lt) * amp); }
      ctx.lineTo(lerp(x0, x1, n / 160), yc); ctx.closePath(); ctx.fill(); ctx.restore();
      retLine(ctx, f, x0, x1, yc, amp, rev, 8, col, lt);
      tag(ctx, lab, 200, yc, C, inv(0.1, 0.5, lt), { px: 44, bg: col, fg: G.INK });
    });
    tag(ctx, '稳', 1780, ya - 0, C, inv(D * 0.6, D * 0.8, lt), { px: 34, bg: G.CREAM, fg: G.INK });
    tag(ctx, '乱晃', 1760, yb - 0, C, inv(D * 0.65, D * 0.85, lt), { px: 34, bg: GOLD, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.pillars_cut = (ctx, s, lt, C) => { // 两根柱子底部各切下一小段，标「国债回报（起步价）」
    const D = s.vizDur, yb = 960, base = 130, top = 390, cut = E.io3(inv(D * 0.3, D * 0.65, lt)), drop = 70 * cut;
    zeroLine(ctx, 420, 1500, yb, rgba(G.INK, 0.5));
    [700, 1200].forEach((x, i) => {
      ctx.fillStyle = i ? rgba(G.INK, 0.85) : G.CREAM; ctx.fillRect(x - 115, yb - base - top - drop, 230, top);
      ctx.fillStyle = PAL.gold.t[2]; ctx.fillRect(x - 115 + 30 * cut * (i ? 1 : -1), yb - base, 230, base);
      tag(ctx, i ? '乙' : '甲', x, yb - base - top - drop - 50, C, inv(0.1, 0.5, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    });
    ctx.save(); ctx.strokeStyle = G.INK; ctx.lineWidth = 5; ctx.setLineDash([18, 12]);
    ctx.beginPath(); ctx.moveTo(540, yb - base - drop * 0.5); ctx.lineTo(1360, yb - base - drop * 0.5); ctx.stroke(); ctx.restore();
    tag(ctx, '国债回报（起步价）', 1560, yb - 70, C, inv(D * 0.45, D * 0.75, lt), { px: 40, bg: G.INK, fg: GOLD });
    G.typeText(ctx, '几乎没风险', 1460, yb - 190, F.zh(800, 38), rgba(G.INK, 0.7), inv(D * 0.6, D * 0.85, lt), { caret: false });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) }, { y: 230 });
  };
  VIZ.remain_six = (ctx, s, lt, C) => { // 切掉底部后剩下的两段一样高，各标「+6%」 — floating segments drop to zero
    const D = s.vizDur, yb = 940, hh = 390, f = E.oBack(inv(0.1, D * 0.45, lt), 1.1), lift = 160 * (1 - f);
    zeroLine(ctx, 400, 1520, yb, rgba(G.INK, 0.55));
    [720, 1200].forEach((x, i) => {
      ctx.fillStyle = i ? rgba(G.INK, 0.85) : G.CREAM; ctx.fillRect(x - 120, yb - hh - lift, 240, hh);
      G.maskText(ctx, '+6%', x, yb - hh - lift - 40, F.en(900, 84), G.INK, inv(D * 0.35, D * 0.6, lt), { align: 'center' });
    });
    ctx.save(); ctx.strokeStyle = rgba(G.INK, 0.7); ctx.lineWidth = 4; ctx.setLineDash([12, 10]);
    ctx.beginPath(); ctx.moveTo(560, yb - hh); ctx.lineTo(1380, yb - hh); ctx.stroke(); ctx.restore();
    tag(ctx, '冒险换来的', 1600, 600, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.INK, fg: GOLD });
    tag(ctx, '一样多', 1600, 700, C, inv(D * 0.6, D * 0.85, lt), { px: 40, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) }, { y: 230 });
  };
  VIZ.swing_box = (ctx, s, lt, C) => { // 乙那条线的上下摆动被一个上下双箭头框住，标「晃动」
    const D = s.vizDur, x0 = 200, x1 = 1380, yc = 660, amp = 230;
    zeroLine(ctx, x0, x1, yc, rgba(C.fg, 0.35));
    retLine(ctx, wigB, x0, x1, yc, amp, E.io(inv(0.05, D * 0.4, lt)), 9, G.CREAM, lt);
    const bx = inv(D * 0.4, D * 0.7, lt), top = yc - amp * 1.25, bot = yc + amp * 1.25;
    if (bx > 0) { ctx.save(); ctx.globalAlpha = clamp(bx * 2); ctx.strokeStyle = G.CREAM; ctx.lineWidth = 4; ctx.setLineDash([16, 10]); ctx.strokeRect(x0 - 20, top, x1 - x0 + 40, bot - top); ctx.restore(); }
    arrowV(ctx, 1500, top, bot, G.CREAM, 8, bx);
    tag(ctx, '晃动', 1660, yc, C, inv(D * 0.55, D * 0.8, lt), { px: 52, bg: G.CREAM, fg: PAL.red.t[2] });
    tag(ctx, '乙', 160, yc - 0, C, inv(0.1, 0.4, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    G.typeText(ctx, '不是亏没亏', 1500, bot + 70, F.zh(800, 36), rgba(C.fg, 0.8), inv(D * 0.65, D * 0.9, lt), { caret: false, align: 'center' });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.sandbags = (ctx, s, lt, C) => { // 甲背小沙袋、乙背大沙袋，手里拿同样大小的「+6%」 — bags on the backs
    const D = s.vizDur, gy = 920, k = E.oBack(inv(0.2, D * 0.55, lt));
    ctx.fillStyle = rgba(G.INK, 0.3); ctx.fillRect(220, gy, 1480, 6);
    [[620, 70, '甲', 0], [1260, 170, '乙', 1]].forEach(([x, r, lab, i]) => {
      const sway = Math.sin(lt * 2.4 + i) * 3, sq = i ? 22 : 0;  // the big bag bends 乙 forward
      sandbag(ctx, x - 70 - r * 0.55, gy - 330 - r * 0.15 + sq * 0.5, r * Math.max(0.01, k), PAL.ochre.t[2], '晃', G.INK);
      figAt(ctx, x, gy, 400, { torso: 8 + sq + sway, head: 10 + sq * 0.5, aL1: 70, aL2: 40, aR1: 80, aR2: 60, lL1: -10, lR1: 10 }, G.INK);
      tag(ctx, '+6%', x + 190, gy - 240, C, inv(D * 0.4, D * 0.65, lt), { px: 46, font: F.en(900, 46), bg: PAL.green.t[2], fg: G.CREAM });
      tag(ctx, lab, x + 150, gy - 40, C, inv(0.1, 0.4, lt), { px: 34, bg: G.INK, fg: G.CREAM });
    });
    tag(ctx, '甲更划算', 1600, 420, C, inv(D * 0.65, D * 0.9, lt), { px: 40, bg: G.INK, fg: GOLD });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.coin_stack = (ctx, s, lt, C) => { // 记分卡上「Sharpe」下面：一份晃动对应一摞小硬币
    const D = s.vizDur, x = 560, y = 340, w = 800, h = 640;
    scoreCard(ctx, x, y, w, h, inv(0.05, 0.4, lt), { tpx: 64 });
    const p = inv(D * 0.25, D * 0.5, lt);
    if (p > 0) sandbag(ctx, x + 210, y + 400, 85 * E.oBack(clamp(p)), PAL.ochre.t[2], '1份', G.INK);
    G.maskText(ctx, '→', x + w / 2, y + 430, F.en(900, 90), G.INK, inv(D * 0.4, D * 0.55, lt), { align: 'center' });
    const n = Math.round(7 * E.o3(inv(D * 0.45, D * 0.85, lt)));
    for (let i = 0; i < n; i++) { ctx.fillStyle = GOLD; ctx.beginPath(); ctx.ellipse(x + 600, y + 520 - i * 34, 80, 22, 0, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = rgba(G.INK, 0.4); ctx.lineWidth = 3; ctx.stroke(); }
    tag(ctx, '超额收益', x + 600, y + 150 + 60, C, inv(D * 0.6, D * 0.85, lt), { px: 34, bg: G.INK, fg: GOLD });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.score_fill = (ctx, s, lt, C) => { // 甲的记分卡分数格更满，乙的少一截
    const D = s.vizDur, y = 360, w = 520, h = 560;
    [[480, '甲', 8], [1100, '乙', 4]].forEach(([x, lab, full], i) => {
      scoreCard(ctx, x, y, w, h, inv(0.05 + i * 0.1, 0.45 + i * 0.1, lt), { tpx: 52 });
      const f = E.o3(inv(D * 0.25, D * 0.75, lt)) * full;
      for (let c = 0; c < 10; c++) { const cx = x + 40 + c * 45; ctx.fillStyle = c < f ? (i ? rgba(G.INK, 0.6) : PAL.green.t[2]) : rgba(G.INK, 0.12); ctx.fillRect(cx, y + 330, 34, 120); }
      tag(ctx, lab, x + w / 2, y + 210, C, inv(0.2, 0.6, lt), { px: 40, bg: G.INK, fg: G.CREAM });
    });
    tag(ctx, '同样晃动，换回更多', W / 2 + 100, 990, C, inv(D * 0.6, D * 0.85, lt), { px: 34, bg: G.CREAM, fg: G.INK });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.card_fog = (ctx, s, lt, C) => { // 记分卡背面是一本翻旧的账本，前方是一团雾
    const D = s.vizDur, flip = E.io(inv(0.2, D * 0.45, lt)), x = 520, y = 640, w = 520, h = 380;
    ctx.save(); ctx.translate(x, y); ctx.scale(Math.abs(Math.cos(flip * Math.PI)), 1);
    if (flip < 0.5) { scoreCard(ctx, -w / 2, -h / 2, w, h, 1, { tpx: 52 }); }
    else {
      ctx.fillStyle = '#b89a6a'; ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, 16); ctx.fill();
      ctx.fillStyle = '#e8dcc0'; ctx.fillRect(-w / 2 + 24, -h / 2 + 24, w / 2 - 34, h - 48); ctx.fillRect(10, -h / 2 + 24, w / 2 - 34, h - 48);
      ctx.fillStyle = rgba(G.INK, 0.35); for (let i = 0; i < 6; i++) { ctx.fillRect(-w / 2 + 44, -h / 2 + 60 + i * 46, w / 2 - 80, 8); ctx.fillRect(30, -h / 2 + 60 + i * 46, w / 2 - 80, 8); }
    }
    ctx.restore();
    tag(ctx, '过去', x, y + h / 2 + 50, C, inv(D * 0.45, D * 0.7, lt), { px: 38, bg: G.CREAM, fg: G.INK });
    const fg = inv(D * 0.4, D * 0.85, lt);
    for (let i = 0; i < 9; i++) { ctx.save(); ctx.globalAlpha = 0.22 * fg; G.disc(ctx, 1300 + Math.sin(i * 1.7 + lt * 0.5) * 220, 520 + (i % 3) * 150 + Math.cos(i + lt * 0.4) * 30, 150 + (i % 4) * 30, G.CREAM); ctx.restore(); }
    G.maskText(ctx, '以后？', 1330, 700, F.zh(900, 90), rgba(C.fg, 0.75), inv(D * 0.6, D * 0.9, lt), { align: 'center' });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.ruler_chair = (ctx, s, lt, C) => { // 一把放在桌上的尺子，旁边空着的椅子，没人替你按按钮
    const D = s.vizDur, ty = 700;
    ctx.fillStyle = rgba(G.INK, 0.8); ctx.fillRect(220, ty, 900, 26); ctx.fillRect(260, ty + 26, 22, 250); ctx.fillRect(1060, ty + 26, 22, 250);
    const p = E.io(inv(0.05, 0.5, lt));
    ctx.fillStyle = G.CREAM; ctx.fillRect(300, ty - 70, 620 * p, 70);
    ctx.fillStyle = G.INK; for (let i = 0; i <= 15; i++) { const xx = 300 + i * 41; if (xx > 300 + 620 * p) break; ctx.fillRect(xx - 2, ty - 70, 4, i % 5 ? 20 : 40); }
    tag(ctx, '把账比清楚', 610, ty - 160, C, inv(0.5, 1.0, lt), { px: 38, bg: G.CREAM, fg: G.INK });
    // empty chair
    const cx = 1480, cy = 975;
    ctx.fillStyle = G.INK; ctx.fillRect(cx - 110, cy - 230, 220, 24); ctx.fillRect(cx + 86, cy - 470, 24, 264); ctx.fillRect(cx - 110, cy - 206, 20, 206); ctx.fillRect(cx + 90, cy - 206, 20, 206);
    // button on the table edge, never pressed
    G.disc(ctx, 1000, ty - 34, 34, PAL.red.t[2]); G.ring(ctx, 1000, ty - 34, 42, 6, G.INK);
    tag(ctx, '空着', cx - 10, cy - 110, C, inv(D * 0.4, D * 0.65, lt), { px: 36, bg: G.INK, fg: G.CREAM });
    tag(ctx, '你自己定', 1480, 420, C, inv(D * 0.6, D * 0.85, lt), { px: 44, bg: G.INK, fg: GOLD });
    vizCaption(ctx, s, lt, C, { y: 230 });
  };
  VIZ.bag_pillars = (ctx, s, lt, C) => { // 回到开头两根一样高的柱子，这次各背着大小不同的沙袋
    const D = s.vizDur, yb = 960;
    zeroLine(ctx, 500, 1700, yb, rgba(G.INK, 0.5));
    twoPillars(ctx, [820, 1380], yb, 220, [480, 480], [G.CREAM, rgba(G.INK, 0.85)], [1, 1]);
    const k = E.oBack(inv(0.2, D * 0.5, lt));
    if (k > 0) { sandbag(ctx, 820 + 150, yb - 480 + 20, 62 * k, PAL.ochre.t[2], '晃', G.INK); sandbag(ctx, 1380 + 190, yb - 480 + 70, 150 * k, PAL.ochre.t[2], '晃', G.INK); }
    tag(ctx, '甲', 820, yb - 530, C, inv(0.1, 0.4, lt), { px: 38, bg: G.INK, fg: G.CREAM });
    tag(ctx, '乙', 1380, yb - 530, C, inv(0.1, 0.4, lt), { px: 38, bg: G.CREAM, fg: G.INK });
    tag(ctx, '每扛一份晃动，换回多少？', 1100, 400, C, inv(D * 0.5, D * 0.8, lt), { px: 40, bg: G.INK, fg: GOLD });
    vizCaption(ctx, { zh: s.zh, en: s.en }, lt, { fg: G.INK, dim: rgba(G.INK, 0.6) }, { y: 230 });
  };

  function vizScene(ctx, s, lt) {
    const sc = s.viz.scene, C = vcol(sc);
    ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
    const fn = VIZ[sc];
    if (!fn) { G.maskText(ctx, 'MISSING SCENE ' + sc, 150, 540, F.mono(40), C.fg, 1); return; }
    fn(ctx, s, lt, C);
  }
  function vizHud(ctx, s, lt) {
    const sc = s.viz.scene, C = vcol(sc);
    const fg = (sc === 'waves') ? G.INK : C.fg;
    ctx.save(); ctx.font = F.mono(18); ctx.letterSpacing = '4px'; ctx.fillStyle = rgba(fg, 0.75); ctx.textAlign = 'left';
    ctx.fillText(upKeep(EYEBROW), 150, 110);
    ctx.textAlign = 'right'; ctx.fillText(TITLE_ZH + '  ' + upKeep(TITLE_EN), W - 150, 110);
    const n = SH.length, x0 = 150, x1 = W - 150, y = H - 90;
    for (let i = 0; i < n; i++) {
      const x = lerp(x0, x1, i / Math.max(n - 1, 1)), now = i === s.i;
      ctx.fillStyle = rgba(fg, now ? 1 : i < s.i ? 0.7 : 0.25);
      ctx.fillRect(Math.round(x) - (now ? 22 : 10), y, now ? 44 : 20, now ? 6 : 4);
    }
    ctx.restore();
  }

  // finance-v003 end card (last outro seconds of the finale shot)
  function endCard(ctx, s, l) {
    ctx.fillStyle = G.CREAM; ctx.fillRect(0, 0, W, H);
    G.disc(ctx, W / 2, 360, 92 * E.oBack(inv(0, 0.5, l)), PAL.red.t[2]);
    rings(ctx, W / 2, 360, 130, 30, 14, (i) => E.io3(inv(i * 0.12, 0.7 + i * 0.12, l)), l * 0.18 + 0.5);
    const epx = Math.min(120, G.fitFont(ctx, END_TITLE, 'zh', 900, 120, 1500, -0.02));
    G.maskText(ctx, END_TITLE, W / 2, 700, F.zh(900, epx), G.INK, inv(0.05, 0.5, l), { ls: '2px', align: 'center' });
    if (END_LINE) G.maskText(ctx, END_LINE, W / 2, 800, F2(700, 48), G.INK, inv(0.15, 0.65, l), { ls: '6px', align: 'center' });
    G.maskText(ctx, CREDIT, W / 2, 960, F.mono(22), rgba(G.INK, 0.55), inv(0.3, 0.9, l), { ls: '4px', align: 'center' });
    const fo = E.io(inv(s.dur - (s.vizDur || 0) - 0.45, s.dur - (s.vizDur || 0) - 0.02, l));
    if (fo > 0) { ctx.fillStyle = rgba('#000000', fo); ctx.fillRect(0, 0, W, H); }
  }

  // ───────── Scene dispatch ─────────
  function drawShot(ctx, s, lt) {
    ctx.save();
    if (s.viz) {
      const vd = s.vizDur || s.dur;
      if (s.kind === 'finale' && lt >= vd) {
        const l = lt - vd, ip = E.io3(inv(0, 0.4, l));
        if (ip < 1) { vizScene(ctx, s, vd - 1e-3); ctx.save(); ctx.beginPath(); ctx.arc(W / 2, 360, 2300 * ip, 0, Math.PI * 2); ctx.clip(); endCard(ctx, s, l); ctx.restore(); }
        else endCard(ctx, s, l);
      } else vizScene(ctx, s, Math.min(lt, vd));
      ctx.restore(); return;
    }
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
    if (a.viz && b.viz) return ['slide', 'rows', 'iris', 'cols', 'quarter', 'flip'][b.i % 6];
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
