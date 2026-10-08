## 1. Fonts

- [x] 1.1 Red Hat Text (latin, latin-ext) and Red Hat Mono (latin) variable woff2 files and the OFL in `cpr/assets/fonts/`
- [x] 1.2 `render.py` inlines them as `@font-face` data at the template's font marker (test: rules present, base64 sources, no network references)

## 2. Template

- [x] 2.1 Colour tokens for light and dark, dark navigation, square status tags with glyph and word
- [x] 2.2 Summary: compact header, status card with sentence and merge steps, collapsed "To do" grouped by owner with optional items, effort and reviewers cards, collapsed "Every check", glossary
- [x] 2.3 Navigation "To do" link and `#todo` routing
- [x] 2.4 Print expands the "To do" list and optional items

## 3. Tests and docs

- [x] 3.1 Browser tests: blocked summary (sentence, per-owner counts), finding to-do item, every-check deep link, `#todo`, print, dark theme colour
- [x] 3.2 Browser test: unreviewed PR says code review has not run; no-reasons PR says nothing to do
- [x] 3.3 `docs/report/summary.md` describes the new layout
