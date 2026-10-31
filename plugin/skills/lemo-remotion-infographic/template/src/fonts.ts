// Self-hosted fonts, same strategy as the library: font files live in the project
// (public/fonts/, filled by scripts/setup.sh), nothing is fetched from Google at render time.
//   Inter Tight + Noto Sans SC: the text pair the controller engines use
//     (tools/deepseek-controller/fetch_fonts.py, pack "remotion-infographic").
//   core/fonts: the library display families, read from the library's own fonts.css
//     (copied to public/fonts/core/), so the family names are exactly the ones in core/fonts/fonts.css.
// A missing or broken font cancels the render instead of silently drawing fallback glyphs.
import { cancelRender, continueRender, delayRender, staticFile } from "remotion";

const TEXT_FONTS = [
  { family: "Inter Tight", file: "fonts/InterTightwght.ttf", weight: "100 900" },
  { family: "Noto Sans SC", file: "fonts/NotoSansSCwght.ttf", weight: "100 900" },
];

const prop = (block: string, name: string) => {
  const m = block.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  return m ? m[1].trim() : undefined;
};

async function coreFaces(): Promise<FontFace[]> {
  const res = await fetch(staticFile("fonts/core/fonts.css"));
  if (!res.ok) throw new Error(`public/fonts/core/fonts.css missing (${res.status}); run scripts/setup.sh`);
  const css = await res.text();
  const faces: FontFace[] = [];
  for (const m of css.matchAll(/@font-face\s*{([^}]*)}/g)) {
    const block = m[1];
    const family = prop(block, "font-family")?.replace(/^['"]|['"]$/g, "");
    const src = prop(block, "src")?.match(/url\(([^)]+)\)/)?.[1]?.replace(/^['"]|['"]$/g, "");
    if (!family || !src) continue;
    const desc: FontFaceDescriptors = {};
    const style = prop(block, "font-style");
    const weight = prop(block, "font-weight");
    const range = prop(block, "unicode-range");
    if (style) desc.style = style;
    if (weight) desc.weight = weight;
    if (range) desc.unicodeRange = range;
    faces.push(new FontFace(family, `url(${staticFile(`fonts/core/${src}`)})`, desc));
  }
  return faces;
}

export function loadFonts(): void {
  const handle = delayRender("Loading WordFilm fonts", { timeoutInMilliseconds: 120000 });
  const text = TEXT_FONTS.map(
    (f) => new FontFace(f.family, `url(${staticFile(f.file)})`, { weight: f.weight })
  );
  coreFaces()
    .then((core) => Promise.all([...text, ...core].map((f) => f.load())))
    .then((loaded) => {
      loaded.forEach((f) => document.fonts.add(f));
      continueRender(handle);
    })
    .catch((err) => cancelRender(new Error(`font loading failed: ${err} (run scripts/setup.sh)`)));
}
