#!/usr/bin/env python3
"""
Headless renderer for EHR-Dataset-Processing Marimo notebook.py plots (mimic-iii only).

Mirrors the plotting cells of Experiments/notebook.py (origin/optimization_refactor) using
the existing Data/mimic-iii/ caches — no GPU, no DB, no Marimo server needed.

Functions from Managers/visualization_manager_v2 all return matplotlib Figures and are called
exactly as the notebook does; figures are saved to static/graphs/EHR-Dataset-Processing/mimic-iii/.
A manifest fragment is written to static/graphs/EHR-Dataset-Processing/marimo_fragment.json.

Usage:
    MPLBACKEND=Agg python render_marimo_mimic_iii.py [--section length|impact|centroid|all]
"""

import argparse
import json
import os
import pickle
import sys
from pathlib import Path
from types import ModuleType

# ── Paths ─────────────────────────────────────────────────────────────────────
WORK = Path("/home/ccampb47/work")
GALLERY = Path(__file__).parent.resolve()
EHR_ROOT = WORK / "EHR-Dataset-Processing"
DATA_ROOT = EHR_ROOT / "Data" / "mimic-iii"
OUT_DIR = GALLERY / "static" / "graphs" / "EHR-Dataset-Processing" / "mimic-iii"
OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "thumbs").mkdir(exist_ok=True)

# ── Matplotlib must be Agg before any other import ───────────────────────────
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Stubs for GPU/torch deps so RecordEHR can be unpickled ───────────────────
def _make_stub(name: str) -> ModuleType:
    m = ModuleType(name)
    m.__spec__ = None

    class _Anything:
        def __init__(self, *a, **kw): pass
        def __call__(self, *a, **kw): return self
        def __getattr__(self, n): return _Anything()
        def __iter__(self): return iter([])
        def __len__(self): return 0

    m._Anything = _Anything
    sys.modules[name] = m

    # Make attribute access return _Anything instances
    class _StubMod(ModuleType):
        def __getattr__(self, n):
            return _Anything()
    m.__class__ = _StubMod
    return m

for _stub in ("torch", "torch.nn", "torch.optim", "torch.utils", "torch.utils.data",
              "cupy", "cudf", "cuml", "cuml.ensemble", "cuml.model_selection",
              "cuml.metrics", "cugraph"):
    if _stub not in sys.modules:
        _make_stub(_stub)

# ── Add EHR project to sys.path ───────────────────────────────────────────────
if str(EHR_ROOT) not in sys.path:
    sys.path.insert(0, str(EHR_ROOT))

# ── Import EHR visualization functions ────────────────────────────────────────
from Managers.visualization_manager_v2 import (  # noqa: E402
    surface_plot, heatmap,
    filter_impact_plot, mcnemar_plot,
    centroid_shift_plot, centroid_plot,
)

# ── Constants mirrored from notebook.py ───────────────────────────────────────
DATASET_NAME = "mimic-iii"
PLOT_THEME = "#191a1c"

VITALS = {
    "heart rate":             [(1, 599), "bpm"],
    "systolic blood pressure": [(1, 399), "mmHg"],
    "diastolic blood pressure": [(1, 299), "mmHg"],
    "mean blood pressure":    [(1, 299), "mmHg"],
    "respiration rate":       [(1, 69),  "breaths/min"],
    "temperature":            [(21, 49), "C"],
    "oxygen saturation":      [(1, 99),  "%"],
}
VITAL_NAMES = list(VITALS.keys())
VITAL_UNITS = [v[-1] for v in VITALS.values()]

AGGREGATION_METHODS = ["mean", "median", "standard deviation", "mean deviation", "maximum deviation"]
LABELS = ["icu", "mortality"]

FILTER_NAMES = [
    "heart rate", "systolic blood pressure", "diastolic blood pressure",
    "mean blood pressure", "respiration rate", "temperature", "oxygen saturation",
    "fill missing data", "long missing segment", "long gap", "high invalid data",
    "all vitals",
]
LENGTH_METHODS = ["mean", "median", "std", "max", "min"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_pkl(path: Path):
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def save_fig(fig, stem: str, manifest: list, meta: dict):
    """Save a matplotlib Figure as PNG + SVG, append manifest record."""
    if fig is None:
        print(f"    [skip] {stem}: figure is None")
        return

    png_path = OUT_DIR / f"{stem}.png"
    svg_path = OUT_DIR / f"{stem}.svg"
    thumb_path = OUT_DIR / "thumbs" / f"{stem}_thumb.png"

    try:
        fig.savefig(str(png_path), dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
        fig.savefig(str(svg_path), bbox_inches="tight", facecolor=fig.get_facecolor())
    except Exception as e:
        print(f"    [ERROR] {stem}: {e}")
        plt.close(fig)
        return

    # Thumbnail via matplotlib rescale
    try:
        import matplotlib.image as mpimg
        import numpy as np
        img = mpimg.imread(str(png_path))
        h, w = img.shape[:2]
        scale = min(300 / w, 200 / h)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        thumb_fig, thumb_ax = plt.subplots(figsize=(new_w / 100, new_h / 100))
        thumb_ax.imshow(img)
        thumb_ax.axis("off")
        thumb_fig.savefig(str(thumb_path), dpi=100, bbox_inches="tight")
        plt.close(thumb_fig)
    except Exception:
        pass  # thumbnail is optional

    plt.close(fig)

    manifest.append({
        "id": f"marimo_{stem}",
        "pipeline": "EHR-Dataset-Processing",
        "dataset": "mimic-iii",
        "notebook": "notebook_py_marimo",
        "source": "rendered",
        "auto_named": False,
        "superseded": False,
        "file": f"graphs/EHR-Dataset-Processing/mimic-iii/{stem}.png",
        "svg": f"graphs/EHR-Dataset-Processing/mimic-iii/{stem}.svg",
        "thumb": f"graphs/EHR-Dataset-Processing/mimic-iii/thumbs/{stem}_thumb.png",
        **meta,
    })
    print(f"    saved {stem}.png")


def attempt(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"      [attempt failed] {fn.__name__}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Section A: Length surface + heatmap plots
# ─────────────────────────────────────────────────────────────────────────────

def render_length_plots(manifest: list):
    print("\n=== Section A: Length plots ===")
    print("Loading processed_record_ehr.pkl ...", flush=True)
    import numpy as np
    import pandas as pd

    pkl_path = DATA_ROOT / "processed_record_ehr.pkl"
    if not pkl_path.exists():
        print(f"  [SKIP] {pkl_path} not found")
        return

    records = load_pkl(pkl_path)
    print(f"  Loaded {len(records)} RecordEHR objects")

    # Mirror notebook.py cell: build per-record length DataFrame
    # record.timeseries is a DataFrame(index=hour 0-23, columns=vitals)
    # each cell is a list/array of measurements for that hour
    print("  Building length matrices ...", flush=True)
    length_dfs = []
    for rec in records:
        try:
            ldf = rec.timeseries.map(
                lambda x: x.size if hasattr(x, "size") else (len(x) if isinstance(x, list) else 0)
            )
            length_dfs.append(ldf)
        except Exception:
            pass

    if not length_dfs:
        print("  [SKIP] no length DataFrames built")
        return

    print(f"  Aggregating across {len(length_dfs)} records ...")
    try:
        combined = pd.concat(length_dfs)
        aggregated = {m: combined.groupby(level=0).agg(m) for m in LENGTH_METHODS}
    except Exception as e:
        print(f"  [ERROR] aggregation failed: {e}")
        return

    for method in LENGTH_METHODS:
        df = aggregated[method]
        stem_s = f"length_{method}_surface"
        stem_h = f"length_{method}_heatmap"
        meta_base = {
            "category": "Timeseries Length",
            "plot_type": "surface",
            "label": None, "aggregation": None, "vital": None,
            "scenario": None, "filter": None,
            "description": f"3D surface plot of {method} observation-count length per vital per hour across all mimic-iii ICU stays.",
        }
        meta_hm = {**meta_base,
                   "plot_type": "heatmap",
                   "description": f"Heatmap of {method} observation-count length per vital per hour across all mimic-iii ICU stays.",
                   }
        meta_s = {**meta_base, "title": f"{method.capitalize()} Observation Length 3D Surface (mimic-iii)"}
        meta_h = {**meta_hm, "title": f"{method.capitalize()} Observation Length Heatmap (mimic-iii)"}

        fig_s = attempt(surface_plot, df,
                        title=f"{method.capitalize()} 3D Surface",
                        y_title="Hour",
                        z_title=f"{method.capitalize()} Length",
                        background_colour=PLOT_THEME)
        save_fig(fig_s, stem_s, manifest, meta_s)

        fig_h = attempt(heatmap, df,
                        title=f"{method.capitalize()} Heatmap",
                        y_title="Hour",
                        background_colour=PLOT_THEME)
        save_fig(fig_h, stem_h, manifest, meta_h)


# ─────────────────────────────────────────────────────────────────────────────
# Section B+C: Filter impact (accuracy, F1) and McNemar plots
# ─────────────────────────────────────────────────────────────────────────────

def render_impact_plots(manifest: list):
    print("\n=== Section B+C: Filter impact / McNemar plots ===")

    for label in LABELS:
        for agg in AGGREGATION_METHODS:
            pkl_path = DATA_ROOT / agg / f"{label}_filter_impact.pkl"
            results = load_pkl(pkl_path)
            if results is None:
                print(f"  [SKIP] {pkl_path}")
                continue

            print(f"  {label}/{agg} ...", flush=True)
            agg_slug = agg.replace(" ", "_")
            label_display = label.upper()

            # Testing accuracy deviation bar
            stem = f"filter_impact_{label}_{agg_slug}_test_accuracy"
            fig = attempt(filter_impact_plot,
                          results[1], list(FILTER_NAMES),
                          label_display, "Testing Accuracy", agg,
                          background=PLOT_THEME)
            save_fig(fig, stem, manifest, {
                "title": f"{label_display} Filter Impact — Testing Accuracy Deviation ({agg.title()} Agg)",
                "description": f"Bar chart of test accuracy deviation from raw baseline for each filter, label={label}, aggregation={agg}.",
                "category": "Filter Impact",
                "plot_type": "bar",
                "label": label, "aggregation": agg,
                "vital": None, "scenario": None, "filter": None,
            })

            # Testing F1 deviation bar
            stem = f"filter_impact_{label}_{agg_slug}_test_f1"
            fig = attempt(filter_impact_plot,
                          results[3], list(FILTER_NAMES),
                          label_display, "Testing F1", agg,
                          background=PLOT_THEME)
            save_fig(fig, stem, manifest, {
                "title": f"{label_display} Filter Impact — Testing F1 Deviation ({agg.title()} Agg)",
                "description": f"Bar chart of test F1 deviation from raw baseline for each filter, label={label}, aggregation={agg}.",
                "category": "Filter Impact",
                "plot_type": "bar",
                "label": label, "aggregation": agg,
                "vital": None, "scenario": None, "filter": None,
            })

            # McNemar significance
            try:
                # results[-1] is a list of (stat, p_value) tuples, index 0 = raw (skip)
                p_values = [x[1] for x in results[-1]][1:]
            except Exception as e:
                print(f"    [SKIP McNemar] {label}/{agg}: {e}")
                continue

            stem = f"mcnemar_{label}_{agg_slug}"
            fig = attempt(mcnemar_plot,
                          p_values, list(FILTER_NAMES),
                          label_display, agg,
                          background=PLOT_THEME)
            save_fig(fig, stem, manifest, {
                "title": f"{label_display} McNemar Significance ({agg.title()} Aggregation)",
                "description": f"−log₁₀(p) bar chart of McNemar test for each filter vs raw baseline, label={label}, aggregation={agg}.",
                "category": "McNemar Significance",
                "plot_type": "bar",
                "label": label, "aggregation": agg,
                "vital": None, "scenario": None, "filter": None,
            })


# ─────────────────────────────────────────────────────────────────────────────
# Section D: Centroid plots
# ─────────────────────────────────────────────────────────────────────────────

def load_all_centroids():
    """Load all centroid .pkl files into nested dict [label][agg][filter][sign]."""
    centroids = {}
    points = {}

    for label in LABELS:
        centroids[label] = {}
        points[label] = {}
        for agg in AGGREGATION_METHODS:
            centroids[label][agg] = {}
            points[label][agg] = {}
            cent_dir = DATA_ROOT / agg / "centroids"
            all_filters = ["raw"] + FILTER_NAMES

            for filter_name in all_filters:
                centroids[label][agg][filter_name] = {}
                points[label][agg][filter_name] = {}
                for sign in ["pos", "neg"]:
                    pkl_path = cent_dir / f"{label}_{filter_name}_{sign}.pkl"
                    data = load_pkl(pkl_path)
                    if data is not None:
                        c, p = data
                        centroids[label][agg][filter_name][sign] = c
                        points[label][agg][filter_name][sign] = p

    return centroids, points


def get_centroid_pairs(centroids, agg, filter_name):
    """Mirror notebook's get_centroid_pairs: 4-tuple (baseline,filtered) for icu+mort × pos+neg."""
    try:
        return [
            (centroids["icu"][agg]["raw"]["pos"],  centroids["icu"][agg][filter_name]["pos"]),
            (centroids["icu"][agg]["raw"]["neg"],  centroids["icu"][agg][filter_name]["neg"]),
            (centroids["mortality"][agg]["raw"]["pos"], centroids["mortality"][agg][filter_name]["pos"]),
            (centroids["mortality"][agg]["raw"]["neg"], centroids["mortality"][agg][filter_name]["neg"]),
        ]
    except KeyError:
        return None


def get_point_pairs(points, agg, filter_name):
    try:
        return [
            (points["icu"][agg]["raw"]["pos"],  points["icu"][agg][filter_name]["pos"]),
            (points["icu"][agg]["raw"]["neg"],  points["icu"][agg][filter_name]["neg"]),
            (points["mortality"][agg]["raw"]["pos"], points["mortality"][agg][filter_name]["pos"]),
            (points["mortality"][agg]["raw"]["neg"], points["mortality"][agg][filter_name]["neg"]),
        ]
    except KeyError:
        return None


def render_centroid_plots(manifest: list):
    print("\n=== Section D: Centroid plots ===")
    print("Loading centroid caches ...", flush=True)
    centroids, points = load_all_centroids()
    print("  Done loading centroids")

    categories = ["icu pos", "icu neg", "mortality pos", "mortality neg"]
    centroid_plot_categories = [
        "Raw ICU Pos", "Raw ICU Neg", "Raw Mort Pos", "Raw Mort Neg",
        "Filt ICU Pos", "Filt ICU Neg", "Filt Mort Pos", "Filt Mort Neg",
    ]

    for agg in AGGREGATION_METHODS:
        agg_slug = agg.replace(" ", "_")
        for filter_name in FILTER_NAMES:
            filter_slug = filter_name.replace(" ", "_")
            print(f"  {agg}/{filter_name} ...", flush=True)

            cp = get_centroid_pairs(centroids, agg, filter_name)
            pp = get_point_pairs(points, agg, filter_name)

            if cp is None:
                print(f"    [SKIP] missing centroid data")
                continue

            # Centroid shift bar chart
            stem = f"centroid_shift_{agg_slug}_{filter_slug}"
            fig = attempt(centroid_shift_plot,
                          cp, categories, filter_name, VITAL_NAMES,
                          background=PLOT_THEME)
            save_fig(fig, stem, manifest, {
                "title": f"Centroid Deviations — {filter_name.title()} Filter ({agg.title()} Agg)",
                "description": f"Grouped bar chart of centroid deviations per vital for ICU+Mortality × pos+neg groups, filter={filter_name}, aggregation={agg}.",
                "category": "Centroid Shift",
                "plot_type": "bar",
                "label": None, "aggregation": agg,
                "vital": None, "scenario": None, "filter": filter_name,
            })

            if pp is None:
                continue

            # Centroid density (max range)
            all_c = [x for pair in cp for x in pair]
            all_p = [x for pair in pp for x in pair]

            stem = f"centroid_density_maxrange_{agg_slug}_{filter_slug}"
            fig = attempt(centroid_plot,
                          all_c, all_p, VITAL_NAMES, VITAL_UNITS,
                          centroid_plot_categories,
                          use_percentile=False,
                          background=PLOT_THEME)
            save_fig(fig, stem, manifest, {
                "title": f"Centroid Distribution (Max Range) — {filter_name.title()} Filter ({agg.title()} Agg)",
                "description": f"8-panel density violin plot of raw vs filtered centroids for ICU+Mortality × pos+neg, max-distance limit, filter={filter_name}, agg={agg}.",
                "category": "Centroid Distribution",
                "plot_type": "violin",
                "label": None, "aggregation": agg,
                "vital": None, "scenario": None, "filter": filter_name,
            })

            # Centroid density (95th percentile)
            stem = f"centroid_density_p95_{agg_slug}_{filter_slug}"
            fig = attempt(centroid_plot,
                          all_c, all_p, VITAL_NAMES, VITAL_UNITS,
                          centroid_plot_categories,
                          use_percentile=True,
                          background=PLOT_THEME)
            save_fig(fig, stem, manifest, {
                "title": f"Centroid Distribution (95th Pct) — {filter_name.title()} Filter ({agg.title()} Agg)",
                "description": f"8-panel density violin plot (95th-percentile distance limit) for filter={filter_name}, agg={agg}.",
                "category": "Centroid Distribution",
                "plot_type": "violin",
                "label": None, "aggregation": agg,
                "vital": None, "scenario": None, "filter": filter_name,
            })


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default="all",
                    choices=["all", "length", "impact", "centroid"],
                    help="Which section to render (default: all)")
    args = ap.parse_args()

    manifest = []

    if args.section in ("all", "length"):
        render_length_plots(manifest)

    if args.section in ("all", "impact"):
        render_impact_plots(manifest)

    if args.section in ("all", "centroid"):
        render_centroid_plots(manifest)

    # Write manifest fragment
    frag_path = GALLERY / "static" / "graphs" / "marimo_manifest_fragment.json"
    frag_path.parent.mkdir(parents=True, exist_ok=True)
    with open(frag_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest fragment written: {frag_path}  ({len(manifest)} records)")


if __name__ == "__main__":
    main()
