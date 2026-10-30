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
