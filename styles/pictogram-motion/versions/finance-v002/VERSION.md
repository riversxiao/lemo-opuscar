# pictogram-motion · style version `finance-v002`

`finance-v001` + per-term labels for the FRM core100 series. v001 stays byte-identical (delivered
films keep their `versionSha256`).

## Deltas vs finance-v001 (`scenes.js` only)

| v001 | v002 | plan / brand_strings.json key |
|---|---|---|
| intro eyebrow hardcoded `PORTFOLIO CONSTRUCTION` | per term | `brand.eyebrow` (e.g. `RISK MEASUREMENT`) |
| intro top label `PORTFOLIO · ASSET ALLOCATION` | per term (defaults to `eyebrow`) | `brand.eyebrowTop` |
| end card `TITLE_EN` + `TITLE_ZH · YEAR` + slogan | `endTitle` + `endLine` (slogan hidden when `endLine` set) | `brand.endTitle`, `brand.endLine` |
| chapter label `cname.toUpperCase()` | `upKeep()`: mixed-case acronyms (VaR, CVaR, CoVaR) and `brand.keepCase` stay as written | `brand.keepCase` (auto-adds every mixed-case word in the plan) |
| slogan JP line always drawn | `brand.sloganJp: ""` hides it | `brand.sloganJp` |

Python side: `apply_pictogram_edl._en_title` uses `common.upper_keep` (no `str.upper()` on titles),
and writes `brand_strings.json.caseViolations`; `quality.py` check `acronym_case` FAILs when any
drawable string shows `VAR` for a plan that writes `VaR`, or when `scenes.js` uppercases outside `upKeep`.

```bash
python3 tools/deepseek-controller/apply_pictogram_style_version.py --project "$PROJ" --version finance-v002
```

Worked example: `/workspace/films/var-template-v002/`.
