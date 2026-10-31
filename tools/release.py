"""Maintainer tool: keep git small, put films and large assets on GitHub Releases.

  python3 tools/release.py check [--strict] [slug ...]
                                what git would commit: fails on big files, local paths, secrets and incomplete styles.
                                Warnings (missing web cut, broken still links, images nothing names, demo files nothing
                                leads to, process wording such as PRODUCTION_LOG) fail only with --strict, which also checks
                                the style format (style.json, STYLE.md, DEMO.md, no sign-off in STYLE.md). Slugs limit
                                the per-style checks to those styles: the gate for a new style is `check --strict <slug>`.
  python3 tools/release.py pack      build the asset packs in .release/ and write tools/assets.json (their size and sha256)
  python3 tools/release.py upload    upload what the releases lack: packs whose sha256 differs, films and web cuts whose size differs
  python3 tools/release.py verify    list what upload would do; exit 1 if anything is missing or different. Changes nothing
  python3 tools/release.py pages [owner/repo]
                                is GitHub Pages on for the repo (default REPO) and deployed by GitHub Actions (pages.yml)?
                                exit 0 only then; otherwise says what a repo admin has to switch on. pages.yml runs it first

Needs the GitHub CLI (`gh auth login`) for upload and verify. Usually run through tools/publish.sh.

Which GitHub repo: films and web cuts go to $WORDFILM_RELEASE_REPO (default riversxiao/wordfilm, this fork). The asset
packs stay on the repo that already hosts them, the `repo` field of tools/assets.json (today the upstream
lemomo-ai/lemo-opuscar, which tools/fetch.sh downloads from); `pack` keeps that field. Only an explicitly set
WORDFILM_RELEASE_REPO moves the packs: then pack writes it into assets.json and upload/verify use it for the packs too.
Films the upstream already hosts keep their upstream links: upload/verify compare each film and web cut against the repo
tools/films.json names for it (the file's default, the upstream, when it is not listed) and push to REPO only what that host
lacks or holds at another size. upload records each film it puts on REPO in tools/films.json (commit it; verify warns while
it is uncommitted), styleboard/build.py links every full film from there, and pages.yml lays REPO's web cuts over the
upstream's and checks that every full-quality link is on its release.
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, tarfile, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
REPO = os.environ.get('WORDFILM_RELEASE_REPO') or 'riversxiao/wordfilm'   # films and web cuts
OUT = os.path.join(ROOT, '.release')
MANIFEST = os.path.join(ROOT, 'tools', 'assets.json')
FILM_HOSTS = os.path.join(ROOT, 'tools', 'films.json')   # {default: repo, films: {slug: repo}}: where each full film is
MAX_MB = 5
SAMPLE_LIBS = ('freepats', 'karoryfer', 'salamander', 'vcsl', 'vsco2ce')

# Packs downloaded by tools/fetch.sh (paths relative to the repo root). Every instruments pack carries index.json.
PACKS = {
    'voice': ['core/tts/kokoro-v1.0.onnx', 'core/tts/voices-v1.0.bin'],
    'hdri': ['core/assets/polyhaven/lythwood_lounge_2k.hdr', 'core/assets/polyhaven/photo_studio_loft_hall_2k.hdr'],
    **{f'instruments-{lib}': ['core/audio/instruments/index.json', f'core/audio/instruments/{lib}'] for lib in SAMPLE_LIBS},
}
ASPECT = re.compile(r'[1-9][0-9]*:[1-9][0-9]*')
STYLE_FIELDS = ('slug', 'en', 'cn', 'category_en', 'category_cn', 'film', 'line', 'line_cn', 'frame_sec')
SIGN_OFF = re.compile(r'(?i:lemolab)|Opus 5\.5|Sign-off')
# a home folder may be `Alice Smith` (up to three words, none ending in a dot, so a sentence isn't swallowed); /root/ counts when a path follows it
LOCAL_PATH = re.compile(rb'/Users/[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_-])?(?: [A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_-])?){0,2}/|/priv' rb'ate/tmp/|/home/[A-Za-z0-9_][A-Za-z0-9_.-]*/|(?<![A-Za-z0-9_.~-])/ro' rb'ot/[A-Za-z0-9_.~-]|/Volum' rb'es/|[A-Z]:\\Users\\')
SECRET = re.compile(rb'(sk-ant-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AIza[0-9A-Za-z_-]{30,}|gh[opsur]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{30,}|xox[bp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIV' rb'ATE KEY-----)')
BINARY = re.compile(r'\.(jpe?g|png|gif|webp|ico|mp4|mov|mp3|wav|ogg|flac|woff2?|ttf|otf|hdr|exr|glb|bin|onnx|npy|npz|pyc|nbi|nbc|zip|tar|gz|tgz|pdf|wasm)$', re.I)
IMG = r'[A-Za-z0-9_.*?<>{}-]+(?:/[A-Za-z0-9_.*?<>{}-]+)*\.(?:jpe?g|png|webp|gif)'
STILL_PATH = re.compile(r'(?:styles/([a-z0-9-]+)/)?demo/stills/(' + IMG + ')', re.I)
STILL_NAME = re.compile(r'(?<![\w/.*-])([A-Za-z0-9_][A-Za-z0-9_.*-]*\.(?:jpe?g|png|webp|gif))(?![\w/*-])', re.I)


def git(*a):
    """git in the repo; before `git init` a throwaway index is used so the checks work anyway."""
    if os.path.isdir(os.path.join(ROOT, '.git')):
        cmd = ['git', '-C', ROOT]
    else:
        gd = os.path.join(tempfile.gettempdir(), 'wordfilm-probe.git')
        if not os.path.isdir(gd): subprocess.run(['git', 'init', '-q', '--bare', gd], check=True)
        cmd = ['git', f'--git-dir={gd}', f'--work-tree={ROOT}']
    return subprocess.run(cmd + list(a), cwd=ROOT, capture_output=True, text=True, check=True).stdout.split('\0')


def committed():
    return sorted(f for f in git('ls-files', '-z', '-co', '--exclude-standard') if f and os.path.isfile(os.path.join(ROOT, f)))


def style_slugs():
    """The styles of the library: every folder under styles/ with a STYLE.md (names starting with _ are templates or drafts)."""
    base = os.path.join(ROOT, 'styles')
    return sorted(s for s in os.listdir(base) if not s.startswith(('_', '.')) and os.path.isfile(os.path.join(base, s, 'STYLE.md')))


def load(rel, default):
    p = os.path.join(ROOT, rel)
    return json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else default


def still_refs(slug, text):
    """{(style, path under demo/stills)} of the images a doc points to. A written-out path always counts. A bare file name
    on the same line counts when such a file exists in that style's demo/stills (so `poster.jpg` elsewhere isn't taken for one)."""
    refs = set()
    pattern = re.compile(r'[*?<>{}]')                         # `t_*.png`, `alt_<n>.jpg`: a pattern or a placeholder, not a file
    for line in text.splitlines():
        paths = STILL_PATH.findall(line)
        for other, ref in paths:
            if not pattern.search(ref): refs.add((other or slug, ref))
        if paths:
            style = paths[0][0] or slug
            for name in STILL_NAME.findall(line):
                if not pattern.search(name) and os.path.isfile(os.path.join(ROOT, 'styles', style, 'demo', 'stills', name)): refs.add((style, name))
    return refs


def film_seconds(path):
    """Length of a film in seconds; None when ffprobe can't read it, 'no-ffprobe' when there is no ffprobe to ask."""
    if not shutil.which('ffprobe'): return 'no-ffprobe'
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path], capture_output=True, text=True)
    try: d = float(r.stdout)
    except ValueError: return None
    return d if d > 0 else None


def committed_catalog():
    """{slug: dur} of styleboard/catalog.json as it is in HEAD; {} when there is no HEAD or no such file."""
    r = subprocess.run(['git', '-C', ROOT, 'show', 'HEAD:styleboard/catalog.json'], capture_output=True, text=True)
    try: return {e['slug']: e.get('dur', 0) for e in json.loads(r.stdout)} if r.returncode == 0 else {}
    except (ValueError, KeyError, TypeError): return {}


def style_format(slugs, bad):
    """--strict: the file layout every style folder must have (folders starting with _ are drafts and skipped)."""
    base = os.path.join(ROOT, 'styles')
    for slug in slugs:
        d, probs = os.path.join(base, slug), []
        for f in ('style.json', 'STYLE.md', 'DEMO.md'):
            if not os.path.isfile(os.path.join(d, f)): probs.append(f'no {f}')
        try:
            meta = json.load(open(os.path.join(d, 'style.json'), encoding='utf-8'))
            miss = [k for k in STYLE_FIELDS if meta.get(k) in (None, '')]
            if miss: probs.append('style.json lacks ' + ', '.join(miss))
            elif meta['slug'] != slug: probs.append(f'style.json says slug "{meta["slug"]}"')
            asp = meta.get('aspects')   # optional: the frame shapes the demo has its own layout for (default ["16:9"])
            if asp is not None and not (isinstance(asp, list) and asp and all(isinstance(a, str) and ASPECT.fullmatch(a) for a in asp)):
                probs.append('style.json aspects must be a non-empty list like ["16:9", "9:16"]')
            # portrait: "native" = the demo has its own 9:16 layout, "reframe" = core/render/reframe.mjs letterboxes the 16:9 frame
            por, has916 = meta.get('portrait'), '9:16' in (asp or [])
            if por not in ('native', 'reframe'): probs.append('style.json portrait must be "native" or "reframe"')
            elif (por == 'native') != has916: probs.append('style.json portrait "native" goes with "9:16" in aspects, "reframe" without it')
            fill = meta.get('portraitFill')
            if fill is not None and not (fill == 'blur' or (isinstance(fill, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', fill))):
                probs.append('style.json portraitFill must be "blur" or a colour like "#101010"')
        except FileNotFoundError: pass
        except ValueError as e: probs.append(f'style.json is not valid JSON ({e})')
        if os.path.isfile(os.path.join(d, 'STYLE.md')):
            hits = sorted({m.group(0) for m in SIGN_OFF.finditer(open(os.path.join(d, 'STYLE.md'), encoding='utf-8').read())})
            if hits: probs.append('STYLE.md mentions ' + ' / '.join(hits) + ' (the sign-off belongs in DEMO.md only)')
        if probs: bad.append(f'{slug}: not in the style format yet: ' + '; '.join(probs))


def completeness(have, bad, warn, slugs):
    """Everything a style needs to be publishable. `have` = the files git would commit."""
    catalog = {e.get('slug'): e for e in load('styleboard/catalog.json', [])}
    before, ffprobe_warned = committed_catalog(), []
    if not any(e.get('dur', 0) > 0 for e in catalog.values()) and style_slugs():
        bad.append('styleboard/catalog.json lists no film for any style (every dur is 0): the gallery would have no videos. '
                   'build.py was probably run on a machine without the films; restore catalog.json (git checkout styleboard/catalog.json)')
    for slug in slugs:
        s = f'styles/{slug}'
        for rel, what in ((f'{s}/poster.jpg', 'poster.jpg'), (f'{s}/demo/stills/styleframe.jpg', 'demo/stills/styleframe.jpg (see .gitignore)'), (f'{s}/demo/CREDITS', 'demo/CREDITS')):
            if rel not in have: bad.append(f'{slug}: {what} is missing or ignored by git')
        if slug not in catalog: bad.append(f'{slug}: not in styleboard/catalog.json (run python3 styleboard/build.py)')
        film = os.path.join(ROOT, s, slug + '.mp4')
        if not os.path.isfile(film): warn.append(f'{slug}: no film {s}/{slug}.mp4 here')
        else:
            secs = film_seconds(film)
            if secs == 'no-ffprobe':
                if not ffprobe_warned: warn.append('ffprobe is not installed: the films could not be checked for readability'); ffprobe_warned.append(1)
            elif secs is None: bad.append(f'{slug}: {s}/{slug}.mp4 exists but ffprobe cannot read its duration (a half-rendered file?): render it again or move it away')
            if not os.path.isfile(os.path.join(OUT, 'web', slug + '.mp4')): warn.append(f'{slug}: no web cut in .release/web/ (sh tools/web_cuts.sh)')
        if before.get(slug, 0) > 0 and catalog.get(slug, {}).get('dur', 1) == 0:
            bad.append(f'{slug}: styleboard/catalog.json says dur 0 now, but the committed catalog has {before[slug]}: the gallery card would lose its video (build.py on a machine without the film?)')
        if glob.glob(os.path.join(ROOT, s, 'demo', 'voices', '*.wav')) and f'{s}/{slug}.srt' not in have:
            warn.append(f'{slug}: the demo has a voice track but no {slug}.srt')
        for doc in ('STYLE.md', 'DEMO.md', 'demo/TREATMENT.md', 'TREATMENT.md'):   # stills the committed docs point to must be committable too
            if f'{s}/{doc}' not in have: continue
            text = open(os.path.join(ROOT, s, doc), encoding='utf-8', errors='replace').read()
            for other, ref in sorted(still_refs(slug, text)):
                path = f'styles/{other}/demo/stills/{ref}'
                if path in have: continue
                if not os.path.isfile(os.path.join(ROOT, path)): warn.append(f'{slug}: {doc} points to demo/stills/{ref}, which does not exist here')
                else: warn.append(f'{slug}: {doc} points to demo/stills/{ref}, which git would not commit (add `!{path}` to .gitignore)')


# Clutter and internal notes a commit should not carry. All three are warnings (failures with --strict) and lean towards
# silence: a file that might be loaded counts as used.
IMAGE = re.compile(r'\.(?:jpe?g|png|webp|gif)$', re.I)
CONVENTION_FILES = ('poster.jpg', 'demo/stills/styleframe.jpg')        # used by the gallery build without being named
REF_TEXT = re.compile(r'\.(?:md|js|mjs|cjs|ts|py|sh|html|json|css|txt|srt)$|(?:^|/)(?:CREDITS|FACTS)$', re.I)
STYLE_ENTRIES = CONVENTION_FILES + ('STYLE.md', 'DEMO.md', 'style.json', 'demo/build.sh', 'demo/build.py', 'demo/index.html',
                                    'demo/CREDITS')
# kept by name: licences, notes on sources, package manifests (files named in core/, which its tools write, are kept too)
KEEP_NAME = re.compile(r'(?i)^(?:OFL|LICEN[CS]E|COPYING|NOTICE|README|SOURCES|CREDITS|FACTS)|[_-](?:OFL|LICEN[CS]E)\b|^__init__\.py$|^\.gitignore$|^package(?:-lock)?\.json$|^requirements[\w.-]*\.txt$|^pyproject\.toml$')
CODE = re.compile(r'\.(?:js|mjs|cjs|ts|py)$')
NAME_TOKEN = re.compile(r'(?<![\w.-])[\w-]+(?:\.[\w-]+)+')
WORD_TOKEN = re.compile(r'[\w-]+')
# a folder named as a prefix (`scenes/` before a quote, `${`, `*`, a `+` or the end of a line): globs, readdir and dynamic imports
DIR_END = re.compile(r'''/(?=[\s'"`)$*{,\]]|$|\s*['"`]?\s*\+)''', re.M)
DIR_NAME = re.compile(r'([\w.-]+)$')
WILD_TOKEN = re.compile(r'''(?<![^\s'"`(),;:=|])[^\s'"`(),;:=|]*?\.(?:jpe?g|png|webp|gif|m?js|cjs|py|json|txt|svg|wav|mp3|srt|css|html)\b''', re.I)
PLACEHOLDER = re.compile(r'\$\{[^}]*\}|\{[^}]*\}|<[^>]*>|%0?\d*d|\[[^\]]*\]|\*+|\?')    # alt_*, alt_<n>, alt_{n}, alt_${n}, alt_%03d, alt_[0-9]
# internal process wording that belongs in local notes, not in the library (add words here)
PROCESS_WORDS = ('PRODUCTION_LOG', '返修', '定稿版', '定稿片', '审片', '用户说', '用户选', r'v[0-9] 的意见', '(?i:reviewer note)',
                 'LemoOpuscarTrial', r'lemomo\.studio')
PROCESS = re.compile('|'.join(PROCESS_WORDS))
PROCESS_EXEMPT = re.compile(r'(?:^|/)\.gitignore$|^MAINTAINING\.md$|^tools/release\.py$')   # files that state the rules


def text_index(t):
    """what a text can point at: names with a dot (`foo.js`), bare words (`foo`, imports without the extension), folders named
    as a prefix, and file-name patterns (`alt_*.jpg`, `frame_${i}.png`, `still_%03d.jpg`) as regexes."""
    dirs = set()
    for m in DIR_END.finditer(t):
        d = DIR_NAME.search(t, max(0, m.start() - 80), m.start())
        if d and d.group(1).strip('.'): dirs.add(d.group(1).strip('.'))
    pats = []
    for tok in WILD_TOKEN.findall(t):
        parts = PLACEHOLDER.split(tok.rsplit('/', 1)[-1])
        if len(parts) > 1 and len(''.join(parts).strip('.')) >= 4:
            pats.append(re.compile('.*'.join(re.escape(p) for p in parts) + '$', re.I))
    return set(NAME_TOKEN.findall(t)), set(WORD_TOKEN.findall(t)), dirs, pats


def hygiene(files, slugs, warn):
    """Images nothing names, demo files no entry reaches, and process wording, in what git would commit."""
    texts, index = {}, {}
    for f in files:
        if BINARY.search(f): continue
        try: texts[f] = open(os.path.join(ROOT, f), encoding='utf-8').read()
        except (UnicodeDecodeError, OSError): pass
    def idx(f):
        if f not in index: index[f] = text_index(texts[f])
        return index[f]
    chosen = tuple(f'styles/{s}/' for s in slugs)
    # 1. images under styles/ that no committed text names, by file name or by a pattern
    refs = [idx(f) for f in texts if REF_TEXT.search(f)]
    names = set().union(*(r[0] for r in refs))
    pats = [p for r in refs for p in r[3]]
    orphans = set()
    for f in files:
        if not (f.startswith(chosen) and IMAGE.search(f)) or f.split('/', 2)[2] in CONVENTION_FILES: continue
        b = os.path.basename(f)
        if b not in names and not any(p.match(b) for p in pats):
            orphans.add(f); warn.append(f'{f}: no committed doc or code names this image (by name or pattern): delete it or link it')
    # 2. files of a style that nothing reaches from its entries (by name, import, folder prefix or pattern)
    paths = {m.rstrip('.') for t in texts.values() for m in re.findall(r'styles/[\w./-]+', t)}
    folders = tuple({p.rstrip('/') + '/' for p in paths if p.rstrip('/').count('/') >= 3})   # styles/<slug>/demo/<folder>, not demo/ itself
    made = {n for f, t in texts.items() if f.startswith('core/') for n in idx(f)[0]}  # what core tools write (events.json, words.json)
    for slug in slugs:
        pre = f'styles/{slug}/'
        own = [f for f in files if f.startswith(pre)]
        reach = {f for f in own if f[len(pre):] in STYLE_ENTRIES + (f'{slug}.srt',) or KEEP_NAME.search(os.path.basename(f))
                 or os.path.basename(f) in made or f in paths or f.startswith(folders)}
        todo = list(reach)
        while todo:
            g = todo.pop()
            if g not in texts: continue
            n, words, dirs, ps = idx(g)
            for f in own:
                if f in reach: continue
                b, below = os.path.basename(f), os.path.dirname(f)[len(pre):].split('/')[1:]   # folders below demo/
                if b in n or (CODE.search(b) and os.path.splitext(b)[0] in words) or dirs.intersection(below) or any(p.match(b) for p in ps):
                    reach.add(f); todo.append(f)
        for f in sorted(set(own) - reach - orphans):
            warn.append(f'{f}: nothing in {slug} leads to this file (STYLE.md, DEMO.md, build.sh, index.html and what they load): delete it or link it')
    # 3. process wording
    for f, t in sorted(texts.items()):
        if PROCESS_EXEMPT.search(f): continue
        for i, line in enumerate(t.splitlines(), 1):
            m = PROCESS.search(line)
            if m: warn.append(f'{f}:{i}: process wording "{m.group(0)}" (internal notes stay local)')


def check():
    args = [a for a in sys.argv[2:] if not a.startswith('--')]
    strict = '--strict' in sys.argv
    unknown = [a for a in args if not os.path.isdir(os.path.join(ROOT, 'styles', a))]
    if unknown: sys.exit(f'✗ no style called {", ".join(unknown)}')
    files, bad, warn = committed(), [], []
    have = set(files)
    size = 0
    for f in files:
        p = os.path.join(ROOT, f)
        n = os.path.getsize(p); size += n
        if n > MAX_MB * 1e6: bad.append(f'too big ({n / 1e6:.1f} MB): {f}')
        elif not BINARY.search(f):
            b = open(p, 'rb').read()
            if LOCAL_PATH.search(b): bad.append(f'local path: {f}')
            if SECRET.search(b): bad.append(f'possible secret: {f}')
    print(f'git would hold {len(files)} files, {size / 1e6:.0f} MB')
    completeness(have, bad, warn, [s for s in style_slugs() if not args or s in args])
    hygiene(files, [s for s in style_slugs() if not args or s in args], warn)
    if strict:
        style_format([s for s in style_slugs() if not args or s in args], bad)
        bad += [f'(--strict) {w}' for w in warn]; warn = []
    for w in warn: print('  !', w)
    for b in bad: print('  ✗', b)
    if bad: sys.exit(1)
    print('  ✓ no files over %d MB, no local paths, no secrets; every %sstyle has its poster, style frame, CREDITS and gallery entry%s' % (MAX_MB, 'selected ' if args else '', '; style format ok; no warnings' if strict else ''))


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def tar(name, paths):
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, name)
    with tarfile.open(dst + '.part', 'w') as t:
        for p in paths:
            t.add(os.path.join(ROOT, p), arcname=p, filter=lambda i: None if i.name.endswith('.DS_Store') or '__pycache__' in i.name else i)
    os.replace(dst + '.part', dst)
    return dst


def pack():
    old, man = load('tools/assets.json', {}).get('packs', {}), {}
    for name, paths in PACKS.items():
        if not all(os.path.exists(os.path.join(ROOT, p)) for p in paths):
            if name in old: man[name] = old[name]; print(f'  ! {name}: its files are not here, keeping the published entry')
            else: print(f'  ! {name}: its files are not here, so it is not in the manifest')
            continue
        dst = tar(f'{name}.tar', paths)
        man[name] = dict(file=f'{name}.tar', size=os.path.getsize(dst), sha256=sha(dst))
        print(f'  {name}.tar  {man[name]["size"] / 1e6:.0f} MB')
    json.dump(dict(repo=asset_repo(), tag='assets', packs=man), open(MANIFEST, 'w'), indent=1)
    print(f'→ {os.path.relpath(MANIFEST, ROOT)}')


def asset_repo():
    """the repo hosting the asset packs: an explicit $WORDFILM_RELEASE_REPO, else the one tools/assets.json names, else REPO."""
    return os.environ.get('WORDFILM_RELEASE_REPO') or load('tools/assets.json', {}).get('repo') or REPO


def gh(*a, check=True, repo=None):
    r = subprocess.run(['gh', *a, '--repo', repo or REPO], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode: sys.exit(f'✗ gh {" ".join(a[:3])} failed: {(r.stderr or r.stdout).strip()[:300]}')
    return r


def remote(tag, repo=None):
    """{name: (size, sha256 or None)} of a release (on REPO, or asset_repo() for the packs); {} when it doesn't exist yet."""
    r = gh('release', 'view', tag, '--json', 'assets', check=False, repo=repo or (asset_repo() if tag == 'assets' else REPO))
    if r.returncode: return {}
    return {a['name']: (a['size'], (a.get('digest') or '').removeprefix('sha256:') or None) for a in json.loads(r.stdout).get('assets', [])}


def film_host(slug):
    """the repo whose films/web releases host <slug> today: its tools/films.json entry, else the file's default."""
    hosts = load('tools/films.json', {})
    return hosts.get('films', {}).get(slug) or hosts.get('default') or 'lemomo-ai/lemo-opuscar'


def plan():
    """[(tag, local path, why)] of everything the releases lack. Packs are compared by sha256 (a changed tar is often the
    same size), films and web cuts by size, against the repo tools/films.json names for that film: a film its host (the
    upstream, say) already has at this size is left there; one it lacks, or holds at another size, goes to REPO."""
    if not shutil.which('gh'): sys.exit('✗ the GitHub CLI (gh) is needed: https://cli.github.com, then gh auth login')
    rel = {t: remote(t) for t in ('assets', 'films', 'web')}
    hosted = {}                                                          # (tag, repo) -> remote(tag, repo), fetched once
    def on(tag, repo): return rel[tag] if repo == REPO else hosted.setdefault((tag, repo), remote(tag, repo))
    todo = []
    styles = style_slugs()
    features = [os.path.basename(f)[:-4] for f in glob.glob(os.path.join(OUT, 'films', '*.mp4')) if os.path.basename(f)[:-4] not in styles]
    for slug in styles + sorted(features):
        film = os.path.join(ROOT, 'styles', slug, slug + '.mp4') if slug in styles else os.path.join(OUT, 'films', slug + '.mp4')
        if not os.path.isfile(film): continue                            # unfinished, or its film is on another machine
        for tag, path in (('films', film), ('web', os.path.join(OUT, 'web', slug + '.mp4'))):
            if not os.path.isfile(path): todo.append((tag, None, f'{slug}.mp4: no local file (sh tools/web_cuts.sh)')); continue
            host = film_host(slug)
            have = on(tag, host).get(slug + '.mp4')
            if have and have[0] == os.path.getsize(path): continue
            if host != REPO:                                             # not on its host as it is here: does REPO have it?
                have = rel[tag].get(slug + '.mp4')
                if have and have[0] == os.path.getsize(path):
                    if tag == 'films': todo.append(('films.json', path, f'on {REPO} but tools/films.json names {host}'))
                    continue
            todo.append((tag, path, 'missing' if not have else 'size differs'))
    for p in load('tools/assets.json', {}).get('packs', {}).values():
        have, path = rel['assets'].get(p['file']), os.path.join(OUT, p['file'])
        if have and (have[1] == p['sha256'] if have[1] else have[0] == p['size']): continue
        if not os.path.isfile(path) or os.path.getsize(path) != p['size']: todo.append(('assets', None, f'{p["file"]}: not built here (python3 tools/release.py pack)'))
        else: todo.append(('assets', path, 'missing' if not have else 'content differs'))
    return todo


def upload():
    todo = plan()
    blocked = [w for t, p, w in todo if p is None]
    if blocked: sys.exit('✗ nothing uploaded; first fix:\n  ' + '\n  '.join(blocked))
    for tag, title in (('assets', 'Assets (fetched by tools/fetch.sh)'), ('films', 'Films (full quality)'), ('web', 'Web cuts (720p, copied into the gallery)')):
        repo = asset_repo() if tag == 'assets' else REPO
        if gh('release', 'view', tag, check=False, repo=repo).returncode:
            gh('release', 'create', tag, '--title', title, '--notes', 'Rolling release, updated by tools/publish.sh.', '--latest=false', repo=repo)
    for tag, path, why in sorted(todo, key=lambda x: x[0] == 'assets'):   # films first: the gallery streams them
        if tag == 'films.json': record_film_host(os.path.basename(path)[:-4]); continue   # already uploaded, just not recorded
        if tag == 'assets' and sha(path) != next(p['sha256'] for p in load('tools/assets.json', {})['packs'].values() if p['file'] == os.path.basename(path)):
            sys.exit(f'✗ {path} changed since `pack`: run python3 tools/release.py pack again')
        print(f'  ↑ {tag}/{os.path.basename(path)}  {os.path.getsize(path) / 1e6:.0f} MB  ({why})')
        gh('release', 'upload', tag, path, '--clobber', repo=asset_repo() if tag == 'assets' else REPO)
        if tag == 'films': record_film_host(os.path.basename(path)[:-4])
    print('  ✓ releases up to date')


def record_film_host(slug, repo=None):
    """note in tools/films.json that REPO's films release now hosts <slug>.mp4 (the gallery links it from there)."""
    repo = repo or REPO
    hosts = json.load(open(FILM_HOSTS, encoding='utf-8')) if os.path.isfile(FILM_HOSTS) else {'default': 'lemomo-ai/lemo-opuscar', 'films': {}}
    films = hosts.setdefault('films', {})
    if films.get(slug) == repo or (slug not in films and hosts.get('default') == repo): return
    films[slug] = repo
    hosts['films'] = dict(sorted(films.items()))
    with open(FILM_HOSTS, 'w', encoding='utf-8') as f: json.dump(hosts, f, indent=1, ensure_ascii=False); f.write('\n')
    print(f'  → tools/films.json: {slug} on {repo} (commit it so the gallery links the film there)')


def verify():
    todo = plan()
    for tag, path, why in todo: print(f'  ✗ {tag}: ' + (f'{os.path.basename(path)} {why}' if path else why))
    if any(x.strip() for x in git('status', '--porcelain', '--', 'tools/films.json')):   # upload just recorded films there
        print('  ! tools/films.json has uncommitted changes: commit it with this release, or the gallery keeps linking those'
              ' films to a repo that does not host them')
    if todo: sys.exit(1)
    print('  ✓ the releases hold every pack in tools/assets.json and every film and web cut on this machine')


PAGES_FIX = ('a repo admin opens https://github.com/{repo}/settings/pages and sets Build and deployment > Source to'
             ' "GitHub Actions" (or runs: gh api -X POST repos/{repo}/pages -f build_type=workflow), then re-runs the'
             ' gallery workflow; the site is then https://{owner}.github.io/{name}/')


def pages_status(repo):
    """(state, info) of the repo's GitHub Pages site: state is 'workflow' (deployed by pages.yml), 'legacy' (built from a
    branch, so pages.yml's deploy is ignored), 'disabled' (404: Pages is off), 'served' (no gh: the site answers, build
    type unknown) or 'unknown' (403, network, no gh and no site...)."""
    if shutil.which('gh'):
        r = subprocess.run(['gh', 'api', f'repos/{repo}/pages'], cwd=ROOT, capture_output=True, text=True)
        out, err = r.stdout.strip(), (r.stderr or '').strip()
        if r.returncode == 0:
            try: info = json.loads(out)
            except ValueError: return 'unknown', {'error': f'gh api returned no JSON: {out[:200]}'}
            return ('workflow' if info.get('build_type') == 'workflow' else 'legacy'), info
        code = re.search(r'HTTP (\d{3})', err + out)
        code = int(code.group(1)) if code else None
    else:
        # no gh: the REST endpoint answers 404 to anonymous callers even when Pages is on, so only the site itself can be
        # probed. That tells served or not, never how it is built.
        import urllib.error, urllib.request
        owner, _, name = repo.partition('/')
        url = f'https://{owner.lower()}.github.io/{name}/'
        try:
            urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=15)
            return 'served', {'html_url': url}
        except urllib.error.HTTPError as e:
            return 'unknown', {'http': e.code, 'error': f'no gh CLI, and {url} answers HTTP {e.code}'}
        except OSError as e:
            return 'unknown', {'error': f'no gh CLI, and {url} could not be fetched: {e}'}
    if code == 404: return 'disabled', {'http': 404}
    return 'unknown', {'http': code, 'error': err[:300]}


def pages():
    """python3 tools/release.py pages [owner/repo]: is GitHub Pages on, and deployed by pages.yml? exit 0 only then."""
    repo = next((a for a in sys.argv[2:] if not a.startswith('--')), None) or REPO
    owner, _, name = repo.partition('/')
    fix = PAGES_FIX.format(repo=repo, owner=owner.lower(), name=name)
    def fail(msg):
        if os.environ.get('GITHUB_ACTIONS'): print('::error title=GitHub Pages::' + msg.removeprefix('✗ '))
        sys.exit(msg)
    state, info = pages_status(repo)
    if state == 'workflow':
        print(f'  ✓ GitHub Pages is on for {repo}, deployed by GitHub Actions (pages.yml): {info.get("html_url") or "?"}')
        return
    if state == 'served':
        print(f'  ✓ {info["html_url"]} is served (no gh CLI, so whether pages.yml deploys it is not checked; gh auth login'
              ' and re-run to see the build type)')
        return
    if state == 'legacy':
        src = info.get('source') or {}
        fail(f'✗ GitHub Pages on {repo} builds from the branch {src.get("branch")}:{src.get("path")} (build_type '
             f'{info.get("build_type")}), so the gallery pages.yml deploys are not served: {fix}')
    if state == 'disabled':
        fail(f'✗ GitHub Pages is not enabled for {repo} (GET repos/{repo}/pages: 404): {fix}')
    fail(f'✗ cannot tell whether GitHub Pages is on for {repo} ({info.get("http") or "no answer"}: '
         f'{info.get("error") or "?"}). Check https://github.com/{repo}/settings/pages; to enable it: {fix}')


if __name__ == '__main__':
    {'check': check, 'pack': pack, 'upload': upload, 'verify': verify, 'pages': pages}[sys.argv[1] if len(sys.argv) > 1 else 'check']()
