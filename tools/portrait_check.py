#!/usr/bin/env python3
"""Reproducible 9:16 check of style demos: render landscape and portrait stills from scratch copies, with the fonts and
footage the demos need (they are gitignored, so a fresh clone cannot render most demos as they are).

  python3 tools/portrait_check.py [slug ...] [--t 12.0 30.5] [--footage] [--out DIR] [--compare REF] [--lib PATH]
                                  [--dry-run]

For each slug (default: every style whose style.json says "portrait": "native", plus the reframe sample
art-deco, hd-2d, microgame):

  1. copy styles/<slug>/ (without films) to <cache>/portrait-check/styles/<slug>/; files fetched earlier stay, so the
     second run is offline. <cache> is $WORDFILM_CACHE, else ~/.cache/wordfilm. The copy records the files it took
     from the library (.portrait-check-files.json) and drops the ones the library no longer has, so a --lib run and
     a run of this checkout each render a clean tree (only fetched fonts and footage are shared).
  2. fonts: the demo's own fetcher when it has one (tools/fonts.py, tools/fetch_fonts.py, tools/fonts.sh), the
     controller's fetch_fonts for caption-news / swiss-motion / pictogram-motion, then every @font-face file still
     missing from Google Fonts (css2 API, whole font, cached in <cache>/portrait-check/fontcache). All OFL.
  3. footage, only with --footage (large downloads): the demo's documented fetch + prep steps for the styles listed
     in FOOTAGE (caption-news about 400 MB, white-model about 55 MB). Without --footage those styles are skipped
     (listed at the end) unless their footage is already in the copy. Styles that need footage nobody automated
     here are reported, not guessed.
  4. stills with core/render/still.mjs at the style frame (style.json frame_sec) or --t times: 1920x1080 into
     <out>/<slug>/land/ and 1080x1920 into <out>/<slug>/port/ (native or reframed, as style.json says).
  5. contact sheets <out>/sheet-land.jpg and <out>/sheet-port.jpg (core/render/sheet.py, needs Pillow).
  6. --compare REF: cmp every landscape still against REF/<slug>/land/<same name>; exit 1 on any difference, and on
     any REF still of a checked slug that this run did not produce (skipped style, missing time point).
     Make REF from another checkout (a git worktree of the old commit, with node_modules linked in). Name the
     slugs when the old checkout's style.json files have no "portrait" field yet:
       python3 tools/portrait_check.py --lib ../wordfilm-old --out ~/.cache/wordfilm/portrait-check/ref [slug ...]
       python3 tools/portrait_check.py --compare ~/.cache/wordfilm/portrait-check/ref

--dry-run prints the plan (copies, font and footage steps, render commands) and touches nothing: no network, no files.
Exit 0 when every style rendered all its stills (and matched with --compare); 1 on a failure, a missing still or
reference, or when nothing rendered at all; 2 on a usage error; 3 when the rest passed but some styles were skipped
(footage missing: run again with --footage).
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SAMPLE = ('art-deco', 'hd-2d', 'microgame')          # reframe styles checked by default (each renders without footage)
CONTROLLER_FONTS = ('caption-news', 'swiss-motion', 'pictogram-motion')
DEMO_FONT_TOOLS = (('tools/fonts.py', 'py'), ('tools/fetch_fonts.py', 'py'), ('tools/fonts.sh', 'sh'))
# footage: (marker that says it is there, [shell steps run in the demo copy]); the same steps as the demo's build.sh / DEMO.md
WM_BBOX = '91500,435200,94300,438000'
FOOTAGE = {
    # marker: the last picture prep.sh writes. prep.sh renders the report page with pdftoppm (poppler) unless
    # raw/report/page-01.png exists; without poppler, PyMuPDF renders it at the same 220 dpi.
    'caption-news': ('assets/img/queen.jpg', [
        'sh tools/fetch_sources.sh',
        'command -v pdftoppm >/dev/null || [ -s raw/report/page-01.png ] || { mkdir -p raw/report && "$PY" -c "'
        "import pymupdf; pymupdf.open('raw/doc_nass.pdf')[0].get_pixmap(dpi=220).save('raw/report/page-01.png')"
        '"; } || { echo "needs pdftoppm (poppler) or PyMuPDF (pip install pymupdf)"; exit 1; }',
        'sh tools/prep.sh']),
    'white-model': ('data/zshadow.png', [          # data/model.json is committed; prep.py adds the images
        'mkdir -p assets/raw data out',
        '[ -s assets/raw/l13_0.json ] || curl -sf -m 600 -o assets/raw/l13_0.json "https://data.3dbag.nl/api/BAG3D/wfs?service=WFS'
        f'&version=2.0.0&request=GetFeature&typeNames=BAG3D:lod13&count=20000&startIndex=0&outputFormat=application/json&bbox={WM_BBOX},EPSG:28992&sortBy=fid"',
        *(f'[ -s assets/raw/{c}.json ] || curl -sf -m 300 -o assets/raw/{c}.json "https://api.pdok.nl/lv/bgt/ogc/v1/collections/{c}/items'
          f'?bbox={WM_BBOX}&bbox-crs=http://www.opengis.net/def/crs/EPSG/0/28992&crs=http://www.opengis.net/def/crs/EPSG/0/28992&limit=1000&f=json"'
          for c in ('waterdeel', 'overbruggingsdeel')),
        '"$PY" -I tools/prep.py . > out/prep.log']),
}
UA = 'curl/8.0'          # Google Fonts css2 answers this with one whole TTF per face (no unicode-range slices)


def cache_root():
    return os.path.abspath(os.path.expanduser(os.environ.get('WORDFILM_CACHE') or os.path.join('~', '.cache', 'wordfilm')))


def style_meta(lib):
    out = {}
    for f in sorted(glob.glob(os.path.join(lib, 'styles', '*', 'style.json'))):
        slug = os.path.basename(os.path.dirname(f))
        if slug.startswith('_'): continue
        out[slug] = json.load(open(f, encoding='utf-8'))
    return out


def font_faces(demo):
    """[(css file, family, weight spec, italic, local path)] for every @font-face src that is a local file."""
    faces = []
    for css in sorted(set(glob.glob(os.path.join(demo, '*.css')) + glob.glob(os.path.join(demo, 'fonts', '*.css'))
                          + glob.glob(os.path.join(demo, '*.html')))):
        text = open(css, encoding='utf-8', errors='replace').read()
        for blk in re.findall(r'@font-face\s*\{(.*?)\}', text, re.S):
            fam = re.search(r"font-family:\s*['\"]?([^;'\"]+)", blk)
            src = re.search(r"url\(\s*['\"]?([^)'\"]+)", blk)
            if not fam or not src or re.match(r'(data:|https?:|//)', src.group(1)): continue
            wm = re.search(r'font-weight:\s*([0-9]+)(?:\s+([0-9]+))?', blk)
            wt = f'{wm.group(1)}..{wm.group(2)}' if wm and wm.group(2) else (wm.group(1) if wm else '400')
            it = 1 if re.search(r'font-style:\s*italic', blk) else 0
            path = os.path.normpath(os.path.join(os.path.dirname(css), urllib.parse.unquote(src.group(1).split('?')[0])))
            faces.append((css, fam.group(1).strip(), wt, it, path))
    return faces


def missing_fonts(demo):
    return [f for f in font_faces(demo) if not (os.path.isfile(f[4]) and os.path.getsize(f[4]) > 1000)]


def family_names(fam, path):
    """Google Fonts family names to try: from the file name (B612Mono-Regular -> B612 Mono, IBMPlexMono-500 -> IBM Plex Mono,
    JosefinSans[wght] -> Josefin Sans), then the CSS family (often an alias such as 'Josefin')."""
    base = re.split(r'[-\[_.]', os.path.basename(path))[0]
    cands = []
    if not re.fullmatch(r'[A-Za-z0-9]{0,3}|[a-z]+[0-9]*|[A-Za-z0-9]{20,}', base):   # f0, sc900, it800, hashes: no name
        cands.append(re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', base))
    cands.append(fam)
    return [c for i, c in enumerate(cands) if c and c not in cands[:i]]


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60).read()


def google_font(fam, wt, it, path, cache):
    """whole font for (family, weight, italic) from the Google Fonts css2 API, cached by face; True when written."""
    os.makedirs(cache, exist_ok=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for name in family_names(fam, path):
        key = re.sub(r'[^A-Za-z0-9.]+', '_', f'{name}_{wt}_{it}')
        hit = next(iter(glob.glob(os.path.join(cache, key + '.*'))), None)
        if hit:
            shutil.copyfile(hit, path); return True
        for spec in (f':ital,wght@{it},{wt}', f':wght@{wt}', ''):
            try:
                css = get('https://fonts.googleapis.com/css2?family=' + urllib.parse.quote(name) + spec).decode()
                url = re.search(r'url\((https://[^)]+)\)', css).group(1)
                data = get(url)
            except Exception:
                continue
            ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or '.ttf'
            open(os.path.join(cache, key + ext), 'wb').write(data)
            open(path, 'wb').write(data)
            return True
    return False


MANIFEST = '.portrait-check-files.json'


def sync_copy(src, copy):
    """copy src over copy (no *.mp4) and delete the files an earlier copy took from a library that src lacks.
    Files the copy gained on its own (fetched fonts, footage) are kept. Returns (stale files removed, had a list)."""
    skip = shutil.ignore_patterns('*.mp4')
    files = set()
    for d, dirs, names in os.walk(src, followlinks=True):
        ign = skip(d, dirs + names)
        dirs[:] = [x for x in dirs if x not in ign]
        files.update(os.path.relpath(os.path.join(d, n), src) for n in names if n not in ign)
    man = os.path.join(copy, MANIFEST)
    try: old = set(json.load(open(man, encoding='utf-8')))
    except (OSError, ValueError): old = None
    shutil.copytree(src, copy, dirs_exist_ok=True, ignore=skip)
    removed = 0
    for rel in sorted((old or set()) - files):
        f = os.path.join(copy, rel)
        if os.path.isfile(f) or os.path.islink(f):
            os.remove(f); removed += 1
    with open(man, 'w', encoding='utf-8') as fh: json.dump(sorted(files), fh, indent=0)
    return removed, old is not None


def run(cmd, cwd, log, env=None):
    with open(log, 'a', encoding='utf-8') as lf:
        lf.write(f'$ {cmd if isinstance(cmd, str) else " ".join(cmd)}\n'); lf.flush()
        r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), stdout=lf, stderr=subprocess.STDOUT, env=env)
    return r.returncode


def tail(log, n=6):
    try: return ''.join(open(log, encoding='utf-8', errors='replace').readlines()[-n:]).rstrip()
    except OSError: return ''


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('slugs', nargs='*', help='styles to check (default: the native 9:16 styles + %s)' % ', '.join(SAMPLE))
    ap.add_argument('--t', nargs='+', help='time points in seconds (default: style.json frame_sec)')
    ap.add_argument('--footage', action='store_true', help='also run the footage fetch + prep steps (large downloads)')
    ap.add_argument('--out', help='output folder (default <cache>/portrait-check/out)')
    ap.add_argument('--compare', metavar='REF', help='cmp landscape stills against REF/<slug>/land/')
    ap.add_argument('--lib', help='render with this library checkout (its styles/ and core/render) instead of this one')
    ap.add_argument('--dry-run', action='store_true', help='print the plan; no network, no files')
    a = ap.parse_args()

    lib = os.path.abspath(a.lib) if a.lib else ROOT
    meta = style_meta(lib)
    slugs = a.slugs or [s for s, m in meta.items() if m.get('portrait') == 'native'] + [s for s in SAMPLE if s in meta]
    unknown = [s for s in slugs if s not in meta]
    if unknown:
        print(f'✗ no style called {", ".join(unknown)} in {lib}/styles', file=sys.stderr); return 2
    if a.t and not all(re.fullmatch(r'[0-9]+(\.[0-9]+)?', t) for t in a.t):
        print(f'✗ --t takes seconds, e.g. --t 12 30.5 (got {" ".join(a.t)})', file=sys.stderr); return 2
    if not os.path.isfile(os.path.join(lib, 'core', 'render', 'still.mjs')):
        print(f'✗ {lib} is not a library checkout (no core/render/still.mjs)', file=sys.stderr); return 2
    if not a.dry_run and not os.path.isdir(os.path.join(lib, 'node_modules', 'playwright-core')):
        print(f'✗ {lib}/node_modules has no playwright-core: npm install there, or for a worktree: '
              f'ln -s {ROOT}/node_modules {lib}/node_modules', file=sys.stderr); return 2
    cache = cache_root()
    work = os.path.join(cache, 'portrait-check')
    out = os.path.abspath(os.path.expanduser(a.out)) if a.out else os.path.join(work, 'out')
    still = os.path.join(lib, 'core', 'render', 'still.mjs')
    env = dict(os.environ, PY=sys.executable, LIB=lib)
    py = sys.executable

    print(f'portrait check: {len(slugs)} styles from {lib}; copies in {work}/styles; stills in {out}'
          + (' (dry run: nothing is fetched or written)' if a.dry_run else ''))
    results, problems, skipped = [], [], []
    for slug in slugs:
        m = meta[slug]
        times = a.t or [str(m.get('frame_sec') or 12.0)]
        src = os.path.join(lib, 'styles', slug)
        copy = os.path.join(work, 'styles', slug)
        demo = os.path.join(copy, 'demo')
        log = os.path.join(work, 'logs', slug + '.log')
        tools = [(t, k) for t, k in DEMO_FONT_TOOLS if os.path.isfile(os.path.join(src, 'demo', t))]
        foot = FOOTAGE.get(slug)
        needs = sorted(os.path.relpath(p, os.path.join(src, 'demo')) for p in glob.glob(os.path.join(src, 'demo', 'tools', 'fetch_*'))
                       if not foot)
        land, port = os.path.join(out, slug, 'land'), os.path.join(out, slug, 'port')
        cmds = [['node', still, demo, *times, '--out', land, '--prefix', 'l_'],
                ['node', still, demo, *times, '--size', '1080x1920', '--out', port, '--prefix', 'p_']]
        print(f'\n{slug}: portrait {m.get("portrait") or "unset"}, t = {" ".join(times)}')
        if a.dry_run:
            print(f'  copy   styles/{slug}/ -> {copy}/ (keeps files fetched before, drops library files {lib} lacks, skips *.mp4)')
            steps = [f'{t} (demo fetcher)' for t, _ in tools] + (['fetch_fonts.ensure_fonts (controller)'] if slug in CONTROLLER_FONTS else [])
            print(f'  fonts  {", ".join(steps + ["Google Fonts css2 for any @font-face file still missing"])}'
                  f' ({len(font_faces(os.path.join(src, "demo")))} @font-face files)')
            if foot:
                print(f'  footage {"" if a.footage else "(only with --footage) "}until {foot[0]} exists:')
                for s in foot[1]: print('           ' + (s if len(s) <= 100 else s[:97] + '...'))
            if needs: print(f'  footage not automated: {", ".join(needs)} (see styles/{slug}/DEMO.md)')
            for c in cmds: print('  render ' + ' '.join(os.path.relpath(x, lib) if x.startswith(lib + os.sep) else x for x in c))
            continue

        os.makedirs(os.path.dirname(log), exist_ok=True)
        open(log, 'w').close()
        fresh = not os.path.isdir(copy)
        removed, listed = sync_copy(src, copy)
        if removed: print(f'  copy   dropped {removed} file(s) an earlier copy took from another library')
        elif not listed and not fresh:
            print(f'  ! copy made before file lists: files from another library may linger; delete {copy} for a clean tree')
        if foot and not a.footage and not os.path.exists(os.path.join(demo, foot[0])):
            # the demo cannot render without its footage: skip it rather than report a render failure
            print(f'  - skipped: footage missing ({foot[0]}); add --footage to fetch it (large)')
            skipped.append(slug); continue
        # fonts
        for t, kind in tools:
            if not missing_fonts(demo): break
            cmd = [py, '-I', t, demo] if kind == 'py' else ['sh', t]
            if run(cmd, demo, log, env): print(f'  ! {t} failed (see {log})')
        if slug in CONTROLLER_FONTS and missing_fonts(demo):
            sys.path.insert(0, os.path.join(lib, 'tools', 'deepseek-controller'))
            try:
                from pathlib import Path
                from fetch_fonts import ensure_fonts
                ensure_fonts(Path(demo) / 'fonts', slug)
            except Exception as e:
                print(f'  ! fetch_fonts: {e}')
        miss = missing_fonts(demo)
        fetched = sum(google_font(fam, wt, it, p, os.path.join(work, 'fontcache')) for _, fam, wt, it, p in miss)
        miss = missing_fonts(demo)
        print(f'  fonts  {len(font_faces(demo))} faces, {fetched} fetched from Google Fonts'
              + (f', still missing: {", ".join(sorted(set(f[1] for f in miss)))}' if miss else ', all present'))
        # footage
        if foot and not os.path.exists(os.path.join(demo, foot[0])):
            for step in foot[1]:
                if run(step, demo, log, env):
                    problems.append(f'{slug}: footage step failed: {step[:60]}'); break
            ready = os.path.exists(os.path.join(demo, foot[0]))
            print(f'  footage {"ready" if ready else "NOT ready"}')
            if not ready:
                if not any(p.startswith(slug + ': footage') for p in problems):
                    problems.append(f'{slug}: footage not ready ({foot[0]} missing, see {log})')
                continue
        if needs: print(f'  ! needs footage this tool does not fetch: {", ".join(needs)}')
        # stills
        ok = True
        for c, d in zip(cmds, (land, port)):
            shutil.rmtree(d, ignore_errors=True)
            if run(c, lib, log, env):
                ok = False; problems.append(f'{slug}: {"landscape" if d == land else "portrait"} render failed: {tail(log, 3)}')
        logged = open(log, encoding='utf-8', errors='replace').read().splitlines()
        for ln in sorted(set(ln.strip() for ln in logged if '[reframe]' in ln)): print('  ' + ln)
        # the controller overlays (edl/texts/beats_runtime.json) are optional by design; anything else is worth a look
        gaps = sorted(set(re.sub(r'^.*?/@film/', '', ln.split(' (')[0]) for ln in logged if 'optional file missing' in ln
                          and not re.search(r'/(edl|texts|beats)_runtime\.json', ln)))
        if gaps: print(f'  ! optional files missing: {", ".join(gaps[:8])}' + (' ...' if len(gaps) > 8 else ''))
        shots = sorted(glob.glob(os.path.join(land, '*.jpg'))), sorted(glob.glob(os.path.join(port, '*.jpg')))
        print(f'  stills {len(shots[0])} landscape, {len(shots[1])} portrait' + ('' if ok else f'  ✗ (see {log})'))
        for kind, got in zip(('landscape', 'portrait'), shots):
            if ok and len(got) < len(times):
                problems.append(f'{slug}: {len(got)} of {len(times)} {kind} stills written (see {log})')
        results.append((slug, shots))
        if a.compare:
            for f in shots[0]:
                ref = os.path.join(os.path.abspath(os.path.expanduser(a.compare)), slug, 'land', os.path.basename(f))
                same = os.path.isfile(ref) and open(ref, 'rb').read() == open(f, 'rb').read()
                print(f'  compare {os.path.basename(f)}: ' + ('identical' if same else ('DIFFERENT' if os.path.isfile(ref) else f'no reference {ref}')))
                if not same: problems.append(f'{slug}: {os.path.basename(f)} differs from {ref}' if os.path.isfile(ref) else f'{slug}: no reference {ref}')

    if a.dry_run: return 0
    if a.compare:
        # a REF still this run did not produce (skipped slug, failed render, missing time point) is a problem too
        for slug in slugs:
            refdir = os.path.join(os.path.abspath(os.path.expanduser(a.compare)), slug, 'land')
            now = os.path.join(out, slug, 'land')
            for ref in sorted(glob.glob(os.path.join(refdir, '*.jpg'))):
                if slug in skipped or not os.path.isfile(os.path.join(now, os.path.basename(ref))):
                    problems.append(f'{slug}: reference {os.path.basename(ref)} has no still in this run'
                                    + (' (skipped)' if slug in skipped else ''))
    if not results and not problems:
        problems.append('nothing rendered: every style was skipped')
    sheet = os.path.join(lib, 'core', 'render', 'sheet.py')
    for i, (name, cols, w) in enumerate((('sheet-land.jpg', 4, 480), ('sheet-port.jpg', 6, 270))):
        files = [f for _, shots in results for f in shots[i]]
        if not files: continue
        r = subprocess.run([py, sheet, os.path.join(out, name), *files, '--cols', str(cols), '--w', str(w)], capture_output=True, text=True)
        print(('  sheet ' + r.stdout.strip()) if r.returncode == 0 else f'  ! contact sheet {name} not written: {(r.stderr or r.stdout).strip()[-200:]}')
    print()
    for p in problems: print('  ✗ ' + p)
    if skipped: print(f'  - skipped (footage missing, run again with --footage): {", ".join(skipped)}')
    if problems: return 1
    print(f'  ✓ {len(results)} styles rendered in 16:9 and 9:16' + (', landscape identical to the reference' if a.compare else '')
          + (f'; {len(skipped)} skipped, so not every style was checked (exit 3)' if skipped else ''))
    return 3 if skipped else 0


if __name__ == '__main__':
    sys.exit(main())
