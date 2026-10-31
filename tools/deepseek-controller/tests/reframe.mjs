// core/render/reframe.mjs: (1) which frames get reframed (planFrame), (2) every styles/*/style.json declares portrait
// native|reframe (native goes with "9:16" in aspects), (3) with ffmpeg: a synthetic 1920x1080 frame composed into 1080x1920
// keeps the whole frame in the centre band (left half red, right half green, scaled) over a darker blurred fill or a flat
// colour, and the video filter gives a WxH stream. Prints one line per check; exit 1 on any failure, 77 when only the
// ffmpeg part could not run (the harness reports SKIP for it).
import fs from 'fs'; import os from 'os'; import path from 'path'; import { execFileSync } from 'child_process'; import { fileURLToPath } from 'url';
import { planFrame, band, reframeFilter, composeStill, LAND } from '../../../core/render/reframe.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
let failed = 0;
const check = (cond, msg) => { console.log((cond ? 'ok ' : 'not ok ') + msg); if (!cond) failed++; };
const err = console.error; console.error = () => {};   // planFrame's one-line notice

// (1) planFrame
const tmp = fs.mkdtempSync(path.join(process.env.WORK || os.tmpdir(), 'reframe-'));
const mk = (name, meta) => { const d = path.join(tmp, name, 'demo'); fs.mkdirSync(d, { recursive: true }); if (meta) fs.writeFileSync(path.join(tmp, name, 'style.json'), JSON.stringify(meta)); return d; };
const R = mk('r', { slug: 'r', portrait: 'reframe' }), N = mk('n', { slug: 'n', portrait: 'native' }), U = mk('u', null), F = mk('f', { slug: 'f', portrait: 'reframe', portraitFill: '#102030' });
const P = { w: 1080, h: 1920 }, L = { w: 1920, h: 1080 };
let p = planFrame(R, P);
check(p.reframe && p.view.w === 1920 && p.view.h === 1080 && p.reframe.w === 1080 && p.reframe.h === 1920 && p.reframe.fill === 'blur', 'reframe style, 1080x1920: page 1920x1080, output 1080x1920, blur fill');
check(planFrame(R, L).reframe === null && planFrame(R, L).view === L, 'reframe style, landscape: untouched');
check(planFrame(N, P).reframe === null && planFrame(N, P).view === P, 'native style, portrait: page at the requested size');
check(planFrame(U, P).reframe === null, 'no style.json (a user film): native');
check(planFrame(R, P, 'native').reframe === null, '--native overrides "reframe"');
check(planFrame(N, P, 'reframe').reframe !== null, '--reframe overrides "native"');
check(planFrame(F, P).reframe.fill === '#102030', 'portraitFill colour is used');
console.error = err;
const b = band(P);
check(b.w === 1080 && b.h === 608 && b.y === 656, `band for 1080x1920 is 1080x608 at y=656 (got ${b.w}x${b.h} at ${b.y})`);

// (2) style.json lint
const slugs = fs.readdirSync(path.join(ROOT, 'styles')).filter(s => fs.existsSync(path.join(ROOT, 'styles', s, 'style.json')));
const badStyles = slugs.filter(s => {
  const j = JSON.parse(fs.readFileSync(path.join(ROOT, 'styles', s, 'style.json'), 'utf8'));
  return !['native', 'reframe'].includes(j.portrait) || (j.portrait === 'native') !== (j.aspects || []).includes('9:16');
});
check(slugs.length > 50 && !badStyles.length, `every styles/*/style.json (${slugs.length}) declares portrait native|reframe matching aspects${badStyles.length ? ': bad ' + badStyles.join(', ') : ''}`);

// (3) ffmpeg compose
let haveFF = true; try { execFileSync('ffmpeg', ['-version'], { stdio: 'ignore' }); execFileSync('ffprobe', ['-version'], { stdio: 'ignore' }); } catch { haveFF = false; }
if (!haveFF) { console.log('skip ffmpeg compose checks: ffmpeg/ffprobe not on PATH'); fs.rmSync(tmp, { recursive: true, force: true }); process.exit(failed ? 1 : 77); }
const src = path.join(tmp, 'src.png');
execFileSync('ffmpeg', ['-loglevel', 'error', '-f', 'lavfi', '-i', `color=c=red:s=960x1080,format=rgb24`, '-f', 'lavfi', '-i', `color=c=lime:s=960x1080,format=rgb24`,
  '-filter_complex', '[0][1]hstack', '-frames:v', '1', src]);
const raw = f => { const buf = execFileSync('ffmpeg', ['-loglevel', 'error', '-i', f, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 64 << 20 });
  const [w, h] = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', f]).toString().trim().split(',').map(Number);
  return { w, h, px: (x, y) => [...buf.subarray((y * w + x) * 3, (y * w + x) * 3 + 3)] }; };
const mean = (img, x0, y0, x1, y1) => { const s = [0, 0, 0]; let n = 0; for (let y = y0; y < y1; y += 4) for (let x = x0; x < x1; x += 4) { const c = img.px(x, y); s[0] += c[0]; s[1] += c[1]; s[2] += c[2]; n++; } return s.map(v => v / n); };
for (const fill of ['blur', '#102030']) {
  const out = path.join(tmp, `out-${fill === 'blur' ? 'blur' : 'flat'}.jpg`);
  await composeStill(fs.readFileSync(src), { w: 1080, h: 1920, fill }, out);
  const im = raw(out), tag = `still ${fill}`;
  check(im.w === 1080 && im.h === 1920, `${tag}: output ${im.w}x${im.h} == 1080x1920`);
  const fgL = mean(im, 20, b.y + 20, 500, b.y + b.h - 20), fgR = mean(im, 580, b.y + 20, 1060, b.y + b.h - 20);
  check(fgL[0] > 245 && fgL[1] < 10 && fgR[1] > 245 && fgR[0] < 10, `${tag}: band shows the whole frame, red left / green right (${fgL.map(Math.round)} / ${fgR.map(Math.round)})`);
  const top = mean(im, 0, 0, 1080, b.y - 8), bot = mean(im, 0, b.y + b.h + 8, 1080, 1920);
  if (fill === 'blur') {
    const lum = c => c[0] + c[1] + c[2];
    check(lum(top) < lum(fgL) * .95 && lum(bot) < lum(fgL) * .95, `${tag}: fill is darker than the picture (${Math.round(lum(top))} / ${Math.round(lum(bot))} vs ${Math.round(lum(fgL))})`);
    const mid = im.px(540, 200);
    check(mid[0] > 30 && mid[1] > 30, `${tag}: fill is a blurred copy (red and green mix at the seam: ${mid})`);
  } else {
    const near = c => Math.abs(c[0] - 16) < 8 && Math.abs(c[1] - 32) < 8 && Math.abs(c[2] - 48) < 8;
    check(near(top) && near(bot), `${tag}: fill is the flat colour (${top.map(Math.round)} / ${bot.map(Math.round)})`);
  }
}
const mp4 = path.join(tmp, 'v.mp4');
execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'lavfi', '-i', `testsrc2=s=${LAND.w}x${LAND.h}:r=24:d=0.25`, '-vf', reframeFilter({ w: 720, h: 1280, fill: 'blur' }), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', mp4]);
const v = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', mp4]).toString().trim();
check(v === '720,1280', `video filter: 1920x1080 stream → ${v.replace(',', 'x')} (want 720x1280)`);
fs.rmSync(tmp, { recursive: true, force: true });
process.exit(failed ? 1 : 0);
