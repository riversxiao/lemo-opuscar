// Render stills: node core/render/still.mjs <demo> <t> [<t> ...] [--range a:b:step] [--q 'k=v&..'] [--prefix t_] [--out dir] [--size 1920x1080] [--native | --reframe]
// <demo> = the folder that holds index.html (e.g. styles/<slug>/demo, films/<name>); the page must expose window.READY and window.render(t).
// A page error or a 404 on a required file exits immediately (non-zero); giving no time points is a usage error
// A portrait --size for a style whose style.json says "portrait": "reframe" renders the page at 1920x1080 and places the whole frame
// in the portrait still over a fill (reframe.mjs); --native renders the page at the requested size instead, --reframe forces the reframe
import fs from 'fs'; import path from 'path';
import { openDemo, closeServer, requireDemo, takeSize } from './page.mjs';
import { takeMode, planFrame, composeStill } from './reframe.mjs';
const args = process.argv.slice(2);
const take = k => { const i = args.indexOf(k); return i >= 0 ? args.splice(i, 2)[1] : null; };
const size = takeSize(args), mode = takeMode(args), out = take('--out'), q = take('--q') || '', prefix = take('--prefix') || 't_', rg = take('--range');
const [dir, ...times] = args;
requireDemo(dir);
const { view: { w, h }, reframe } = planFrame(dir, size, mode);
if (rg) {
  const [a, b, st] = rg.split(':').map(Number);
  if (![a, b, st].every(Number.isFinite) || !(st > 0) || b < a) { console.error(`bad --range "${rg}": use a:b:step with step > 0 (e.g. 0:50:2.5)`); process.exit(2); }
  for (let x = a; x <= b + 1e-9; x += st) times.push(x.toFixed(2));
}
if (!times.length || times.some(t => !Number.isFinite(parseFloat(t)))) { console.error('usage: node core/render/still.mjs <demo> <t> [<t> ...] [--range a:b:step] [--q k=v] [--prefix t_] [--out dir] [--size WxH] [--native | --reframe]'); process.exit(2); }
const outDir = out || path.join(dir, 'stills'); fs.mkdirSync(outDir, { recursive: true });
const { browser, page } = await openDemo(dir, { w, h, q, warnings: true });   // one page, many stills
for (const ts of times) {
  const t0 = Date.now();
  await page.evaluate(t => window.render(t), parseFloat(ts));
  const f = path.join(outDir, `${prefix}${ts}.jpg`);
  if (reframe) await composeStill(await page.screenshot({ type: 'png' }), reframe, f).catch(e => { console.error(e.message); process.exit(1); });
  else await page.screenshot({ path: f, type: 'jpeg', quality: 92 });
  console.log(f, Date.now() - t0 + 'ms');
}
await browser.close(); closeServer();
