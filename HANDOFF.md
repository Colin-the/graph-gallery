# Graph Gallery — Handoff

**Date:** 2026-05-18  
**Repo:** https://github.com/Colin-the/graph-gallery  
**Built on:** `l5.nibi.sharcnet` (Compute Canada), primary nibi working dir `/home/ccampb47/work/graph-gallery/`

---

## What this is

A self-contained browser-based gallery for all research graphs produced by the ICU-EHR pipeline
comparison project. It bundles **888 graphs** from three sources into a single
Flask app with cascading dropdowns, a help menu, side-by-side comparison, and suggested pairings:

| Source | Graphs | Notes |
|---|---|---|
| MIMIC_Extract notebooks (Experiment_Statistics + curated copy 2 + mimic_extract_analysis + baselines) | 153 | MIMIC-III only |
| EHR-Dataset-Processing analysis notebooks (branch `origin/optimization_refactor`) | 460 | mimic-iii, mimic-iv, eICU |
| `pipeline_comparison.ipynb` + EHR Marimo `notebook.py` regen (mimic-iii) | 275 | Cross-pipeline + canonical Marimo plots |

**52 graphs are hand-curated** (accurate descriptive names); the rest are auto-named from cell
source / markdown headings (marked with `*` in the UI and hidden by default behind **Show All**).

---

## Running on a Docker host

Clone the repo (images are committed — first clone is large, ~1 GB):

```bash
git clone https://github.com/Colin-the/graph-gallery.git
cd graph-gallery
docker compose up --build
# → http://localhost:8000
```

That's it. No external data, no database, no other pipeline code needed.

To use a different port:
```yaml
# edit docker-compose.yml: ports: ["9000:8000"]
```

---

## Running without Docker

```bash
git clone https://github.com/Colin-the/graph-gallery.git
cd graph-gallery
./run.sh           # auto-creates .venv/ with Flask on first run
```

Requires Python 3.9+ and pip (any standard Linux/macOS machine).

---

## Project structure

```
graph-gallery/
  app/
    server.py            # Flask: serves /, /api/manifest, /graphs/<path>
    templates/index.html # Single-page UI
    static/app.js        # Cascading dropdowns, side-by-side, suggestions
    static/style.css     # Aurora theme (#191a1c / #724ed5 / #4ED595)
  static/graphs/         # 888 PNG images + SVGs (committed to git)
  graphs_manifest.json   # Catalog: id, title, dataset, pipeline, category,
                         #   label, aggregation, vital, filter, suggested_pairs
  requirements.txt       # flask, gunicorn (runtime only)
  run.sh                 # Standalone startup script
  Dockerfile
  docker-compose.yml
```

The manifest is the single source of truth for the UI — all dropdowns and suggestion pairs
are computed from it at page load.

---

## Current state & known issues

### Working
- 888 graphs browsable via cascading dropdowns (Dataset → Pipeline → Category → Label →
  Aggregation → Graph)
- Side-by-side comparison with auto-suggested cross-pipeline pairings
- Help modal explaining datasets, pipelines, aggregations, labels, plot types
- Aurora dark theme matching the research notebooks
- Docker + standalone `run.sh` startup

### Open issues

1. **Marimo mimic-iv/eICU not regenerated** — the 460 EHR graphs for mimic-iv and eICU come
   from the legacy `*-analysis.ipynb` notebooks (auto-named, accuracy varies). Regenerating
   them from the canonical Marimo `notebook.py` requires the Docker GPU + DB environment that
   wasn't available on nibi. These should be regenerated once the Docker host is set up.

2. **McNemar cell in `pipeline_comparison.ipynb` is unreliable** — as documented in
   `HANDOFF.md` under `/home/ccampb47/work/.claude/`, the EHR predictions used for the McNemar
   test in the comparison notebook still come from a dummy (NaN-feature) classifier. The other
   metrics (accuracy, F1, AUC) are correct (sourced from pre-computed cuML results). See
   pipeline_comparison.ipynb cell 20 / open issues section in `.claude/HANDOFF.md`.

3. **Auto-named graph titles** — 625 of 888 graphs have titles derived from cell source
   heuristics. Many are accurate but some are generic ("Plot"). Improving them means extending
   the `CURATED_CATALOG` dict in `extract_notebook_graphs.py` (on nibi) and re-running the
   extraction + manifest build.

4. **`static/graphs/` in git** — the images (888 PNGs + SVGs + thumbs) total ~1 GB. This
   makes the first clone slow. If the repo grows further, consider Git LFS:
   ```bash
   git lfs install
   git lfs track "static/graphs/**/*.png" "static/graphs/**/*.svg"
   ```

---

## Continuing development

### On the Docker host

After `docker compose up --build`:

- The Flask app is at `http://localhost:8000`.
- To debug the frontend, edit `app/static/app.js` or `app/templates/index.html` and
  restart: `docker compose restart`.
- To run with live reload: `FLASK_DEBUG=1 python app/server.py` (outside Docker).

The frontend is a single `app.js` (vanilla JS, no build step). Key functions:
- `initDropdowns()` — wires the 5-level cascading selects, data-driven from manifest
- `renderMainPane()` / `renderPane()` — display a graph record + suggestions
- `toggleCompare()` — switches between single and side-by-side layout
- `onGraphSelected()` — called on every dropdown change, dispatches to render functions

### Adding new graphs

Graphs come from two paths — both run on nibi, not on the Docker host:

**A. New executed notebook** (add to the `NOTEBOOKS` list in `extract_notebook_graphs.py`):
```bash
# on nibi:
source /home/ccampb47/work/MIMIC_Extract/.venv_stats/bin/activate
python extract_notebook_graphs.py
python build_manifest.py
git add static/graphs/ graphs_manifest.json && git commit -m "add <notebook>"
git push
# on Docker host: git pull && docker compose up --build
```

**B. New Marimo notebook.py section** (add plotting calls to `render_marimo_mimic_iii.py`):
```bash
# on nibi:
sbatch render_marimo.sbatch
# wait for job, then:
python build_manifest.py
git add static/graphs/EHR-Dataset-Processing/mimic-iii/ graphs_manifest.json && git commit -m "..."
git push
```

**C. Fix a graph name** (improve an auto-named title):  
Add an entry to `CURATED_CATALOG` in `extract_notebook_graphs.py` and re-run extraction.
The key is `(notebook_slug, output_index)` — output indices are in the `id` field of
`graphs_manifest.json` (e.g. `experiment_statistics_0003` → slug=`experiment_statistics`, idx=3).

### Manifest schema

Each record in `graphs_manifest.json["records"]`:

```json
{
  "id":             "experiment_statistics_0000",
  "pipeline":       "MIMIC_Extract" | "EHR-Dataset-Processing" | "Comparison",
  "dataset":        "mimic-iii" | "mimic-iv" | "eicu",
  "notebook":       "experiment_statistics",
  "category":       "Cohort Statistics",
  "plot_type":      "bar" | "heatmap" | "error-bar" | "kde" | "pca-scatter" | "line" | "surface" | "violin",
  "label":          "icu" | "mortality" | null,
  "aggregation":    "mean" | "median" | "standard deviation" | "mean deviation" | "maximum deviation" | null,
  "vital":          "heart rate" | ... | null,
  "scenario":       "age35_range5" | ... | null,
  "filter":         "heart rate" | "fill missing data" | ... | null,
  "title":          "ICU Stays per Scenario",
  "description":    "...",
  "file":           "graphs/MIMIC_Extract/experiment_statistics/experiment_statistics_0000.png",
  "svg":            "graphs/.../....svg" | null,
  "thumb":          "graphs/.../thumbs/..._thumb.png" | null,
  "auto_named":     false,
  "superseded":     false,
  "suggested_pairs": [{"id": "...", "why": "Same plot type from EHR-Dataset-Processing"}]
}
```

---

## nibi context (for regenerating graphs)

All graph generation runs on `l5.nibi.sharcnet` (Compute Canada HPC). Key paths:

| Resource | Path |
|---|---|
| Graph gallery repo | `/home/ccampb47/work/graph-gallery/` |
| Python venv (matplotlib, flask, nbconvert, scipy) | `/home/ccampb47/work/MIMIC_Extract/.venv_stats/` |
| MIMIC_Extract notebooks + H5 data | `/home/ccampb47/work/MIMIC_Extract/` |
| EHR pipeline caches (mimic-iii only) | `/home/ccampb47/work/EHR-Dataset-Processing/Data/mimic-iii/` |
| EHR canonical branch | `git -C EHR-Dataset-Processing show origin/optimization_refactor:<path>` |
| Pipeline comparison notebook | `/home/ccampb47/work/pipeline_comparison.ipynb` |
| SLURM account | `def-wzhang25_cpu` / `def-wzhang25_gpu` |

Build scripts (`extract_notebook_graphs.py`, `render_marimo_mimic_iii.py`, `build_manifest.py`)
are gitignored — they contain nibi-specific absolute paths and are only needed to regenerate
the graph images. They live at `/home/ccampb47/work/graph-gallery/` on nibi.
