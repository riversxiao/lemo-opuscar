// Portrait reframe for styles without a native 9:16 layout.
// styles/<slug>/style.json says "portrait": "native" (the page lays itself out from innerWidth/innerHeight) or "reframe"
// (the demo is a 16:9 film with a fixed 1920x1080 layout). For a portrait --size (height > width) and a reframe style, the page
// is rendered at 1920x1080 and each frame is composed into the requested WxH: the whole 16:9 picture scaled to the width,
// vertically centred (nothing is cropped, so no text is lost), over a fill. The fill is a scaled-up, darkened, blurred copy
// of the same frame, or a flat colour when style.json gives "portraitFill": "#rrggbb". The ffmpeg filter is deterministic.
// --reframe / --native on the command line override style.json. Folders with no style.json (a user's film) are native: their
// page gets the requested size, as before. Landscape sizes are never reframed.
import fs from 'fs'; import path from 'path'; import { spawn } from 'child_process';

export const LAND = { w: 1920, h: 1080 };
export const MODES = ['native', 'reframe'];
const HEX = /^#[0-9a-fA-F]{6}$/;
const even = n => Math.max(2, Math.round(n / 2) * 2);

// style.json of a demo folder: <dir>/style.json, else <dir>/../style.json (styles/<slug>/demo, or a copy of styles/<slug>)
export function styleMeta(dir) {
  for (const p of [path.join(dir, 'style.json'), path.join(dir, '..', 'style.json')]) {
    try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch {}
  }
  return null;
}

// removes --reframe / --native from args; returns 'reframe', 'native' or null (follow style.json)
export function takeMode(args) {
  const pick = k => { const i = args.indexOf(k); if (i < 0) return false; args.splice(i, 1); return true; };
  const r = pick('--reframe'), n = pick('--native');
  if (r && n) { console.error('--reframe and --native exclude each other: pick one'); process.exit(2); }
  return r ? 'reframe' : n ? 'native' : null;
}

// → { view: {w, h} to open the page at, reframe: null | {w, h, fill, slug} to compose each frame into }
export function planFrame(dir, size, force = null) {
  if (!(size.h > size.w)) return { view: size, reframe: null };
  const meta = styleMeta(dir) || {};
  const mode = force || (meta.portrait === 'reframe' ? 'reframe' : 'native');
  if (mode !== 'reframe') return { view: size, reframe: null };
  const fill = HEX.test(meta.portraitFill || '') ? meta.portraitFill : 'blur';
  const slug = meta.slug || path.basename(path.resolve(dir));
  console.error(`[reframe] ${slug} has no native ${size.w}x${size.h} layout: the page renders at ${LAND.w}x${LAND.h} and the whole 16:9 frame ` +
    `is placed in ${size.w}x${size.h} over a ${fill === 'blur' ? 'blurred copy of itself' : fill + ' fill'} (--native renders the page at ${size.w}x${size.h} instead)`);
  return { view: { ...LAND }, reframe: { w: size.w, h: size.h, fill, slug } };
}

// the foreground band: the full landscape frame scaled to the output width, vertically centred
export function band({ w, h }, src = LAND) {
  const fh = Math.min(h, even(w * src.h / src.w)), y = even((h - fh) / 2);
  return { x: 0, y, w, h: fh };
}

// ffmpeg simple filtergraph (one input, one output): landscape frame → WxH portrait frame
export function reframeFilter(r, src = LAND) {
  const b = band(r, src), fg = `scale=${b.w}:${b.h}:flags=lanczos`;
  if (r.fill !== 'blur') return `${fg},pad=${r.w}:${r.h}:0:${b.y}:color=${r.fill}`;
  const bw = even(r.w / 8), bh = even(r.h / 8);   // blur at 1/8 size: cheap, and the upscale smooths it further
  return `split[a][b];[a]scale=${bw}:${bh}:force_original_aspect_ratio=increase,crop=${bw}:${bh},gblur=sigma=4,` +
    `eq=brightness=-0.16:saturation=0.8,scale=${r.w}:${r.h}:flags=bilinear[bg];[b]${fg}[fg];[bg][fg]overlay=0:${b.y}`;
}

// one still: an image buffer (png or jpeg) → a WxH jpeg written to file (through a pipe, so no ffmpeg path syntax applies)
export function composeStill(buf, r, file, { q = 2, src = LAND } = {}) {
  return new Promise((resolve, reject) => {
    const ff = spawn('ffmpeg', ['-loglevel', 'error', '-f', 'image2pipe', '-i', '-', '-vf', reframeFilter(r, src) + ',scale=out_range=full,format=yuvj420p',
      '-frames:v', '1', '-c:v', 'mjpeg', '-q:v', String(q), '-f', 'image2pipe', '-'], { stdio: ['pipe', 'pipe', 'inherit'] });
    const out = [];
    ff.on('error', e => reject(new Error(e.code === 'ENOENT' ? 'ffmpeg is not installed (or not on PATH): portrait reframe needs it' : e.message)));
    ff.stdout.on('data', d => out.push(d));
    ff.on('close', code => {
      if (code !== 0 || !out.length) return reject(new Error(`ffmpeg could not reframe the still (exit code ${code}; its message, if any, is above)`));
      fs.writeFileSync(file, Buffer.concat(out)); resolve(file);
    });
    ff.stdin.on('error', () => {});
    ff.stdin.end(buf);
  });
}
