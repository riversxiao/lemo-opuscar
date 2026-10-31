// Re-render a frame range only: node render_range.mjs <film> --fps 30 --from F0 --to F1 --out seg.mp4 [--size WxH]
// --size defaults to 1920x1080; visual_check.py passes the size of the video it splices into (1080x1920 for 9:16).
// Same capture path and encoder settings as core/render/video.mjs (jpeg q95 → libx264 medium crf14 yuv420p),
// so the segment can be spliced losslessly at keyframes (visual_check.py rework). Engine files untouched.
import { spawn } from 'child_process';
import { openDemo, closeServer, requireDemo, takeSize } from '../../core/render/page.mjs';
const args = process.argv.slice(2), { w: W, h: H } = takeSize(args), opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const dir = args[0]; requireDemo(dir);
const FPS = +opt('--fps', 24), A = +opt('--from', 0), B = +opt('--to', 0), OUT = opt('--out', '');
if (!(B > A) || !OUT) { console.error('need --from < --to and --out'); process.exit(2); }
const { browser, page } = await openDemo(dir, { w: W, h: H, q: '' });
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', OUT], { stdio: ['pipe', 'inherit', 'inherit'] });
const closed = new Promise(r => ff.on('close', r));
for (let f = A; f < B; f++) {
  await page.evaluate(t => window.render(t), f / FPS);
  const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
}
ff.stdin.end(); const code = await closed; await browser.close(); closeServer();
if (code !== 0) { console.error('ffmpeg failed'); process.exit(1); }
console.log(`range ${A}-${B} → ${OUT}`);
