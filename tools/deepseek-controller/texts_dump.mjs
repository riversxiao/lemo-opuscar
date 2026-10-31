// Dump the page's on-screen text registry: node texts_dump.mjs <film> [--step 0.1] [--times 1,2.5] [--size WxH]
// --size defaults to 1920x1080; visual_check.py passes the project's render size (content/engine.lock.json aspect).
// Prints JSON {dur, W, H, frames:[{t, texts:[{id,text,x0,y0,x1,y1}]}]} using the same window.TEXTS(t)
// contract readcheck.mjs uses (core/render/readcheck.mjs header). Read-only; engine files untouched.
import { openDemo, closeServer, requireDemo, takeSize } from '../../core/render/page.mjs';
const args = process.argv.slice(2), { w: VW, h: VH } = takeSize(args), opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const dir = args[0]; requireDemo(dir);
const STEP = +opt('--step', 0.1), TIMES = opt('--times', '');
const { browser, page } = await openDemo(dir, { w: VW, h: VH, q: '' });
const res = await page.evaluate(({ STEP, TIMES }) => {
  if (typeof window.TEXTS !== 'function') return { noTexts: true };
  const ts = TIMES ? TIMES.split(',').map(Number) : [];
  if (!ts.length) for (let t = 0; t <= window.DUR + 1e-9; t += STEP) ts.push(+t.toFixed(3));
  const frames = ts.map(t => { window.render(t); return { t, texts: (window.TEXTS(t) || []).map(b => ({ id: String(b.id), text: b.text, x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1 })) }; });
  return { dur: window.DUR, W: innerWidth, H: innerHeight, frames };
}, { STEP, TIMES });
await browser.close(); closeServer();
if (res.noTexts) { console.error('texts_dump: page has no window.TEXTS(t)'); process.exit(2); }
process.stdout.write(JSON.stringify(res));
