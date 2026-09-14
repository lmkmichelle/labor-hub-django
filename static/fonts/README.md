# LMSans10 (Latin Modern Sans)

`LMSans10-Regular.ttf` and `LMSans10-Bold.ttf` are used by `publications/covers.py` to render
the discussion-paper cover page, matching the typeface the original `Cover_page_DP.tex`
template selects via `\usepackage{lmodern}` + `\renewcommand{\familydefault}{\sfdefault}`.

**Source:** converted from the OpenType (CFF-flavoured) originals shipped with TeX Live 2025 —

```
texmf-dist/fonts/opentype/public/lm/lmsans10-regular.otf
texmf-dist/fonts/opentype/public/lm/lmsans10-bold.otf
```

— to TrueType outlines with `otf2ttf` (ReportLab's `TTFont` cannot load CFF/PostScript
outlines directly; it needs a `glyf` table).

**Licence:** GUST Font License (GFL), a Latin Modern/OFL-style licence permitting
redistribution and modification, including format conversion. See
https://www.gust.org.pl/projects/e-foundry/latin-modern/ for the full text and font family.
