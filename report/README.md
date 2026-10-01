# Report

LaTeX source for the assessment report. The driver is [main.tex](main.tex); each
section lives under [sections/](sections/) and is `\input` from `main.tex`.

## Building

```bash
cd report
latexmk -pdf main.tex     # produces main.pdf
```

CI also builds the PDF on every change to `report/` or `model/artefacts/` and
uploads it as an artifact (see [.github/workflows/report.yml](../.github/workflows/report.yml)).

## Figures

Architecture figures in [figures/](figures/) are PDF renders of the authoritative
d2 diagram sources under [`../model/artefacts/`](../model/artefacts/). They are
committed so the report builds without extra tooling. If you edit a diagram,
regenerate them (requires [d2](https://d2lang.com)):

```bash
report/figures/render.sh
```
