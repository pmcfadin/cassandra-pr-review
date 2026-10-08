# Report fonts

Red Hat Text and Red Hat Mono, variable weight, woff2, from the `@fontsource-variable/red-hat-text`
and `@fontsource-variable/red-hat-mono` 5.3.0 npm packages (upstream:
https://github.com/RedHatOfficial/RedHatFont). Licensed under the SIL Open Font License 1.1, see
`OFL.txt`.

`cpr/render.py` embeds these files in every report as base64 `@font-face` data, so the report needs
no network. `FONTS` in `render.py` lists each file with its family and unicode range.
