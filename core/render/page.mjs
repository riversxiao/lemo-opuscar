// Open a demo page (the repo root is the static server root; film projects outside the library are mounted under /@film/) and wait for window.READY
// Fail loudly: a JS error in the page, or a failed load of a script (<script>, module import; resourceType script) or of the page itself (document), exits immediately (non-zero).
// Other types (fetch / xhr / images / fonts…) only print a one-line warning on 404: many demos fetch an optional voices/dur.json and use defaults when it's missing
import { chromium } from 'playwright-core';
import fs from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
import { serve, pageURL } from './serve.mjs';
import { EXE, ARGS, warnIfSoftwareGL } from './browser.mjs';
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
let srv = null;
export async function server() { if (!srv) srv = await serve(ROOT); return srv; }
// every entry script calls this before creating any output directory
export function requireDemo(dir) {
  if (!dir || dir.startsWith('--')) { console.error('usage: <demo> is the folder that holds index.html (see core/README.md)'); process.exit(2); }
  if (!fs.existsSync(path.join(dir, 'index.html'))) { console.error(`no index.html in "${dir}": the demo folder is wrong or the page isn't there yet`); process.exit(2); }
}
// --size WxH (default 1920x1080): removes the pair from args and returns { w, h }. Width and height must be even (an H.264 yuv420p requirement), 16–8192
export function takeSize(args) {
  const i = args.indexOf('--size'); if (i < 0) return { w: 1920, h: 1080 };
  const v = args.splice(i, 2)[1] || '', m = /^(\d+)x(\d+)$/.exec(v), w = m && +m[1], h = m && +m[2];
  if (!m || [w, h].some(n => n < 16 || n > 8192 || n % 2)) { console.error(`bad --size "${v}": use WxH with even numbers from 16 to 8192, e.g. 1080x1920`); process.exit(2); }
  return { w, h };
}
const warned = new Set();   // each optional file warns only once per process (video.mjs opens several pages)
const FATAL = new Set(['script', 'document']);   // things the page must have; module imports also have type script
export async function openDemo(dir, { w = 1920, h = 1080, q = '', warnings = false } = {}) {
  requireDemo(dir);
  const { port } = await server();
  const browser = await chromium.launch({ executablePath: EXE, args: ARGS });
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const log = [];   // recent errors, printed together if READY is slow to arrive
  const note = s => { log.push(s); if (log.length > 8) log.shift(); console.error(s); };
  page.on('console', m => {
    const t = m.text();
    if (m.type() === 'error' && /^Failed to load resource/.test(t)) return;   // printed with its URL by the response event below
    if (m.type() === 'error' || (warnings && m.type() === 'warning')) note('[page] ' + t.slice(0, 300));
  });
  page.on('pageerror', e => { console.error('[pageerror]', e.message); process.exit(1); });   // stop on an error during rendering, so no broken film is produced
  page.on('response', r => {
    if (r.status() < 400) return;
    const u = r.url(), p = new URL(u).pathname, type = r.request().resourceType();
    if (p === '/favicon.ico') return;
    if (FATAL.has(type)) {
      note(`[page] ${r.status()} ${u}`);
      console.error(`the page needs ${p} (a ${type}) but the server answered ${r.status()}. Check the path: pages use absolute URLs like /core/lib.js (see core/README.md)`); process.exit(1);
    }
    if (!warned.has(u)) { warned.add(u); note(`[page] optional file missing: ${u} (${r.status()}, requested by ${type === 'fetch' || type === 'xhr' ? 'fetch/xhr' : type}; fine if the page has a fallback)`); }
  });
  page.on('requestfailed', r => { if (!/favicon/.test(r.url()) && r.failure()?.errorText !== 'net::ERR_ABORTED') note(`[page] request failed ${r.url()} (${r.failure()?.errorText})`); });
  await page.goto(pageURL(ROOT, port, dir) + (q ? '?' + q : ''));
  const hint = setTimeout(() => {
    console.error(`still waiting for window.READY after 20 s. The page has to set window.READY = true once fonts and images are loaded.\n` +
      (log.length ? '  problems seen so far:\n    ' + log.join('\n    ') + '\n' : '  no console errors so far: is the <script> closed, does it reach the line that sets window.READY?\n') +
      `  debug: node core/render/still.mjs ${dir} 0, or open the page in a normal browser (the tools serve the library root on 127.0.0.1)`);
  }, 20000);
  const t0 = Date.now();
  try { await page.waitForFunction(() => window.READY === true, null, { timeout: 180000 }); }
  catch (e) { console.error(`window.READY never became true (waited ${((Date.now() - t0) / 1000).toFixed(0)} s, limit 180 s): ${e.message.split('\n')[0]}`); process.exit(1); }
  finally { clearTimeout(hint); }
  await warnIfSoftwareGL(page);
  // Pictogram controller bridge: touchable edl_runtime.json replaces window.EDL after READY,
  // then re-evals scenes.js so its SH/CARDS closures rebuild. Protected edl.js/scenes.js hashes unchanged.
  // Optional brand_strings.json rewrites Olympics HUD/intro/finale *literals* in the eval'd
  // source only (disk scenes.js untouched). Other styles ignore (no edl_runtime.json / no window.EDL).
  try {
    const applied = await page.evaluate(async () => {
      const r = await fetch('edl_runtime.json', { cache: 'no-store' });
      if (!r.ok) return false;
      const runtime = await r.json();
      if (!runtime || !Array.isArray(runtime.shots) || !runtime.shots.length) return false;
      if (!window.EDL || typeof window.EDL !== 'object') return false;
      window.EDL = runtime;
      if (typeof runtime.DUR === 'number' && runtime.DUR > 0) window.DUR = runtime.DUR;
      const sr = await fetch('scenes.js', { cache: 'no-store' });
      if (!sr.ok) throw new Error('scenes.js fetch ' + sr.status);
      let code = await sr.text();
      let brandApplied = false;
      try {
        const br = await fetch('brand_strings.json', { cache: 'no-store' });
        if (br.ok) {
          const brand = await br.json();
          window.__BRAND_STRINGS = brand;
          // Style-version scenes (finance-v001) already carry content strings — skip
          // Olympics literal rewrite (short tokens like SET→GO would corrupt ASSET).
          const applyLiterals = brand && brand.applyLiterals !== false;
          if (applyLiterals) {
            const reps = Array.isArray(brand && brand.replace) ? brand.replace.slice() : [];
            reps.sort((a, b) => String((b && b.from) || '').length - String((a && a.from) || '').length);
            for (const row of reps) {
              const frm = row && row.from, to = row && row.to;
              if (typeof frm !== 'string' || typeof to !== 'string' || !frm) continue;
              if (code.includes(frm)) { code = code.split(frm).join(to); brandApplied = true; }
            }
            const ticks = brand && brand.hudTicks;
            if (Number.isFinite(ticks) && ticks >= 1) {
              const n = Math.floor(ticks);
              const denom = Math.max(n - 1, 1);
              const before = code;
              code = code.replace(/for \(let i = 1; i <= 43; i\+\+\)/, `for (let i = 1; i <= ${n}; i++)`);
              code = code.replace(/\(i - 1\) \/ 42/g, `(i - 1) / ${denom}`);
              if (code !== before) brandApplied = true;
            }
          } else {
            brandApplied = false;
            window.__BRAND_FIELDS_ONLY = true;
          }
        }
      } catch (_) { /* brand optional */ }
      (0, eval)(code);
      window.__EDL_RUNTIME_APPLIED = true;
      window.__BRAND_STRINGS_APPLIED = brandApplied;
      return { ok: true, brand: brandApplied, brandFields: !!window.__BRAND_FIELDS_ONLY };
    });
    if (applied && applied.ok) {
      console.error('[edl_runtime] applied content EDL overlay (edl.js hash untouched)' +
        (applied.brand ? '; brand_strings rewrite on eval(scenes.js)' :
          (applied.brandFields ? '; __BRAND_STRINGS fields only (no literal rewrite)' : '')));
    }
  } catch (e) {
    console.error('[edl_runtime] bridge failed:', (e && e.message) ? e.message.split('\n')[0] : e);
    process.exit(1);
  }
  // Swiss controller bridge: touchable texts_runtime.json installs window.TEXTS(t) after READY
  // when the locked demo never registered it. film.js/main.js hashes unchanged. No-op if TEXTS
  // already exists (caption / style versions) or the JSON is absent.
  try {
    const textsApplied = await page.evaluate(async () => {
      if (typeof window.TEXTS === 'function') return { ok: false, reason: 'already' };
      const r = await fetch('texts_runtime.json', { cache: 'no-store' });
      if (!r.ok) return { ok: false, reason: 'missing' };
      const runtime = await r.json();
      const entries = runtime && Array.isArray(runtime.entries) ? runtime.entries : [];
      if (!entries.length) return { ok: false, reason: 'empty' };
      window.__TEXTS_RUNTIME = runtime;
      window.TEXTS = (t) => {
        const out = [];
        for (const e of entries) {
          if (!e || t < e.t0 || t > e.t1) continue;
          out.push({
            id: String(e.id),
            text: String(e.text || ''),
            x0: +e.x0, y0: +e.y0, x1: +e.x1, y1: +e.y1,
          });
        }
        return out;
      };
      window.__TEXTS_RUNTIME_APPLIED = true;
      return { ok: true, n: entries.length, holdPad: (runtime.holdPad || []).length };
    });
    if (textsApplied && textsApplied.ok) {
      console.error(`[texts_runtime] installed window.TEXTS (${textsApplied.n} entries` +
        (textsApplied.holdPad ? `, holdPad=${textsApplied.holdPad}` : '') +
        '; film.js/main.js hash untouched)');
    }
  } catch (e) {
    console.error('[texts_runtime] bridge failed:', (e && e.message) ? e.message.split('\n')[0] : e);
    process.exit(1);
  }
  // Beats bridge (pacing P1, every style): touchable beats_runtime.json (tools/deepseek-controller/beats.py)
  // wraps window.render(t) with a deterministic CSS reframe on <body> (sub-beats of long shots, rework
  // drift windows) and a keyword emphasis pulse (1.5 % pull-back thump + accent border on an overlay outside <body>).
  // window.TEXTS boxes are mapped through the same transform and the scale is limited so every text box
  // that is on screen during a beat stays fully in frame. No new on-screen text. No-op without the JSON.
  try {
    const beatsApplied = await page.evaluate(async ([W, H]) => {
      const r = await fetch('beats_runtime.json', { cache: 'no-store' });
      if (!r.ok) return { ok: false, reason: 'missing' };
      const rt = await r.json();
      const beats = (rt && Array.isArray(rt.beats)) ? rt.beats : [];
      const emph = (rt && Array.isArray(rt.emphasis)) ? rt.emphasis : [];
      const drift = (rt && Array.isArray(rt.drift)) ? rt.drift : [];
      if (!beats.length && !emph.length && !drift.length) return { ok: false, reason: 'empty' };
      if (typeof window.render !== 'function') return { ok: false, reason: 'no-render' };
      const M = 4, SX = 0.05 * W + 4, SY = 0.05 * H + 4, cx = W / 2, cy = H / 2, PUNCH = Number.isFinite(+rt.punch) ? +rt.punch : -0.015, BORDER = +rt.border || 6;
      const origTexts = typeof window.TEXTS === 'function' ? window.TEXTS : null;
      const texts = t => { try { return origTexts ? (origTexts(t) || []) : []; } catch (_) { return []; } };
      const unionOf = (t0, t1) => {
        let u = null;
        for (let t = t0; t <= t1 + 1e-6; t += 0.2) for (const b of texts(Math.min(t, t1))) {
          if (![b.x0, b.y0, b.x1, b.y1].every(Number.isFinite)) continue;
          u = u ? [Math.min(u[0], b.x0), Math.min(u[1], b.y0), Math.max(u[2], b.x1), Math.max(u[3], b.y1)] : [b.x0, b.y0, b.x1, b.y1];
        }
        return u;
      };
      for (const b of beats) b._u = unionOf(+b.t0, +b.t1);
      const beatAt = t => { for (const b of beats) if (t >= b.t0 && t < b.t1) return b; return beats.length && t >= beats[beats.length - 1].t1 ? beats[beats.length - 1] : null; };
      const fit = (S, ox, oy, u) => {   // clamp offsets: keep the frame covered and the text union inside
        const cvx = Math.abs(S - 1) * cx, cvy = Math.abs(S - 1) * cy;   // push-in: stay covered; pull-back: bg fills
        let lo = -cvx, hi = cvx, loy = -cvy, hiy = cvy;
        if (u) {   // title-safe: text never moves into the 5 % margin (or further out than it already was)
          const L = Math.min(u[0], SX) - 2, R = Math.max(u[2], W - SX) + 2, T = Math.min(u[1], SY) - 2, B = Math.max(u[3], H - SY) + 2;
          lo = Math.max(lo, Math.max(M, L) - cx - (u[0] - cx) * S); hi = Math.min(hi, Math.min(W - M, R) - cx - (u[2] - cx) * S);
          loy = Math.max(loy, Math.max(M, T) - cy - (u[1] - cy) * S); hiy = Math.min(hiy, Math.min(H - M, B) - cy - (u[3] - cy) * S);
        }
        if (lo > hi + 1e-6 || loy > hiy + 1e-6) return null;
        return [S, Math.min(hi, Math.max(lo, ox)), Math.min(hiy, Math.max(loy, oy))];
      };
      const xf = t => {
        const b = beatAt(t);
        let S = b ? (+b.scale || 1) : 1, ox = b ? (+b.ox || 0) : 0, oy = b ? (+b.oy || 0) : 0;
        const dr = (b && +b.drift) || 0;
        if (dr && b.t1 > b.t0) S *= 1 + dr * (t - b.t0) / (b.t1 - b.t0);
        for (const w of drift) if (t >= w.t0 && t < w.t1) { const a = Number.isFinite(+w.amount) ? +w.amount : -0.015; S *= 1 + a * (t - w.t0) / Math.max(0.1, w.t1 - w.t0); ox += (+w.dx || 0) * (t - w.t0) / Math.max(0.1, w.t1 - w.t0); }
        let pulse = 0;
        for (const e of emph) {
          const d = +e.dur || 0.4, rise = Math.min(0.06, d / 3), k = t - e.t;
          if (k < 0 || k > d) continue;
          pulse = Math.max(pulse, k < rise ? k / rise : 1 - (k - rise) / (d - rise));
        }
        S *= 1 + PUNCH * pulse;
        const u = b ? b._u : null;
        let f = null;
        if (S < 1) f = fit(S, ox, oy, u) || [S, 0, 0];
        else for (let s = S; s >= 1 - 1e-9 && !(f = fit(s, ox, oy, u)); s -= 0.003);
        return { f: f || [1, 0, 0], pulse };
      };
      const body = document.body, br = body.getBoundingClientRect();
      const bgOf = el => { const c = el && getComputedStyle(el).backgroundColor; return c && !/rgba\(0, 0, 0, 0\)|transparent/.test(c) ? c : null; };
      const fill = rt.background || bgOf(body) || bgOf(document.documentElement) || bgOf(body.firstElementChild) || '#000';
      document.documentElement.style.background = fill;   // revealed edge on a pull-back
      body.style.transformOrigin = `${cx - br.left}px ${cy - br.top}px`;
      const ov = document.createElement('div');
      ov.id = '__beats_overlay';
      ov.style.cssText = `position:fixed;left:0;top:0;width:${W}px;height:${H}px;box-sizing:border-box;` +
        `border:${BORDER}px solid ${rt.accent || '#FFC21A'};opacity:0;pointer-events:none;z-index:2147483647`;
      document.documentElement.appendChild(ov);
      const orig = window.render;
      window.render = function (t, ...rest) {
        const out = orig.call(this, t, ...rest);
        const { f: [S, ox, oy], pulse } = xf(+t);
        body.style.transform = (S === 1 && !ox && !oy) ? '' : `translate(${ox.toFixed(2)}px,${oy.toFixed(2)}px) scale(${S.toFixed(5)})`;
        ov.style.opacity = pulse > 0 ? (0.9 * pulse).toFixed(3) : '0';
        return out;
      };
      if (origTexts) window.TEXTS = t => {
        const { f: [S, ox, oy] } = xf(+t);
        return texts(t).map(b => ({ ...b,
          x0: cx + (b.x0 - cx) * S + ox, x1: cx + (b.x1 - cx) * S + ox,
          y0: cy + (b.y0 - cy) * S + oy, y1: cy + (b.y1 - cy) * S + oy }));
      };
      window.__BEATS_RUNTIME = rt; window.__BEATS_XF = xf; window.__BEATS_RUNTIME_APPLIED = true;
      return { ok: true, beats: beats.filter(b => b.kind === 'reframe').length, emph: emph.length, drift: drift.length };
    }, [w, h]);
    if (beatsApplied && beatsApplied.ok) {
      console.error(`[beats_runtime] reframes=${beatsApplied.beats} emphasis=${beatsApplied.emph} drift=${beatsApplied.drift} (render/TEXTS wrapped; style files untouched)`);
    }
  } catch (e) {
    console.error('[beats_runtime] bridge failed:', (e && e.message) ? e.message.split('\n')[0] : e);
    process.exit(1);
  }
  return { browser, page };
}
export function closeServer() { if (srv) srv.server.close(); }
