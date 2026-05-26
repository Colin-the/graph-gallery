"""
Assign meaningful metadata to EHR-Dataset-Processing graph records.

The Marimo notebook generates images in a fixed, deterministic sequence:
  0-9:   Length Analysis  (5 stat methods x 2 plot types)
  10-24: ICU Filter Impact (5 agg methods x 3 plot types)
  25-39: Mortality Filter Impact (5 agg methods x 3 plot types)
  40+:   Centroid Analysis (5 agg x 12 filters x 3 plot types, some fail)

Usage:
    python scripts/assign_ehr_metadata.py

Reads graphs_manifest.json, updates EHR records with proper metadata, writes back.
"""

import json
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = REPO_ROOT / "graphs_manifest.json"
GRAPHS_DIR = REPO_ROOT / "static" / "graphs"

AGGREGATION_METHODS = [
    "mean",
    "median",
    "standard deviation",
    "mean deviation",
    "maximum deviation",
]
FILTERS = [
    "heart rate",
    "systolic blood pressure",
    "diastolic blood pressure",
    "mean blood pressure",
    "respiration rate",
    "temperature",
    "oxygen saturation",
    "fill missing data",
    "long missing segment",
    "long gap",
    "high invalid data",
    "all vitals",
]
LENGTH_STAT_METHODS = ["mean", "median", "std", "max", "min"]
RAW_BASELINE_COUNT = len(AGGREGATION_METHODS) * 2  # 10: 5 agg x 2 (normal + percentile)


def classify(width: int, height: int) -> str:
    ratio = width / height
    if ratio < 1.3:
        return "length"
    if ratio < 1.9:
        return "filter_impact"
    if ratio < 2.2:
        return "mcnemar"
    if ratio < 2.52:
        return "centroid_shift"
    return "centroid_density"


def build_metadata(idx: int, ptype: str, dataset: str) -> dict:
    """Return a metadata dict for image at position idx with classified ptype."""

    # ── Length Analysis (images 0–9) ──────────────────────────────────────
    if idx < 10:
        method_idx = idx // 2
        is_surface = (idx % 2 == 0)
        stat = LENGTH_STAT_METHODS[method_idx]
        label = "3D Surface" if is_surface else "Heatmap"
        return {
            "category": "Length Analysis",
            "plot_type": "surface" if is_surface else "heatmap",
            "aggregation": stat,
            "label": None,
            "filter": None,
            "title": f"{label} — Observation Count by Hour ({stat.title()})",
            "auto_named": False,
        }

    # ── ICU Filter Impact (images 10–24) ──────────────────────────────────
    if idx < 25:
        j = idx - 10            # 0..14
        agg_idx = j // 3
        plot_in_triplet = j % 3
        agg = AGGREGATION_METHODS[agg_idx]

        if plot_in_triplet == 2:
            return {
                "category": "McNemar Significance",
                "plot_type": "heatmap",
                "aggregation": agg,
                "label": "icu",
                "filter": None,
                "title": f"McNemar Significance — ICU ({agg.title()})",
                "auto_named": False,
            }
        metric = "Accuracy" if plot_in_triplet == 0 else "F1"
        return {
            "category": "Filter Impact",
            "plot_type": "bar",
            "aggregation": agg,
            "label": "icu",
            "filter": None,
            "title": f"Filter Impact — ICU Testing {metric} ({agg.title()})",
            "auto_named": False,
        }

    # ── Mortality Filter Impact (images 25–39) ────────────────────────────
    if idx < 40:
        j = idx - 25            # 0..14
        agg_idx = j // 3
        plot_in_triplet = j % 3
        agg = AGGREGATION_METHODS[agg_idx]

        if plot_in_triplet == 2:
            return {
                "category": "McNemar Significance",
                "plot_type": "heatmap",
                "aggregation": agg,
                "label": "mortality",
                "filter": None,
                "title": f"McNemar Significance — Mortality ({agg.title()})",
                "auto_named": False,
            }
        metric = "Accuracy" if plot_in_triplet == 0 else "F1"
        return {
            "category": "Filter Impact",
            "plot_type": "bar",
            "aggregation": agg,
            "label": "mortality",
            "filter": None,
            "title": f"Filter Impact — Mortality Testing {metric} ({agg.title()})",
            "auto_named": False,
        }

    # ── Centroid Analysis (images 40+) ────────────────────────────────────
    centroid_i = idx - 40
    group_idx = centroid_i // 3      # which (agg, filter) group
    subtype = centroid_i % 3         # 0=shift, 1=density, 2=density_percentile

    category = "Centroid Shift" if subtype == 0 else "Centroid Density"
    plot_type = "bar" if subtype == 0 else "kde"

    # agg/filter assignment: reliable for mimic-iii/iv (only ~3 failures/60 groups)
    # too many failures for eicu (27/60), so skip agg/filter there
    if dataset in ("mimic-iii", "mimic-iv"):
        agg_idx = group_idx // len(FILTERS)
        filter_idx = group_idx % len(FILTERS)
        agg = AGGREGATION_METHODS[agg_idx] if agg_idx < len(AGGREGATION_METHODS) else None
        filter_name = FILTERS[filter_idx] if filter_idx < len(FILTERS) else None
    else:
        agg = None
        filter_name = None

    parts = [category]
    if filter_name:
        parts.append(filter_name.title())
    if agg:
        parts.append(f"({agg.title()})")
    suffix = " Percentile" if subtype == 2 else ""

    return {
        "category": category,
        "plot_type": plot_type,
        "aggregation": agg,
        "label": None,
        "filter": filter_name,
        "title": " — ".join(parts) + suffix,
        "auto_named": False,
    }


def assign_dataset(dataset: str, records_by_id: dict[str, dict]) -> int:
    ehr_dir = GRAPHS_DIR / "EHR-Dataset-Processing" / dataset
    pngs = sorted([p for p in ehr_dir.glob("*.png") if "thumbs" not in str(p)])
    total = len(pngs)

    # Raw baseline images (raw-only centroid density) are appended at the end of the
    # notebook output. Only mimic-iii/iv have them; eicu notebook not regenerated.
    has_raw_baseline = dataset in ("mimic-iii", "mimic-iv")
    raw_start = total - RAW_BASELINE_COUNT if has_raw_baseline else total + 1

    updated = 0
    for idx, png_path in enumerate(pngs):
        with Image.open(png_path) as img:
            ptype = classify(*img.size)

        if idx >= raw_start:
            raw_idx = idx - raw_start
            agg_idx = raw_idx // 2
            is_percentile = bool(raw_idx % 2)
            agg = AGGREGATION_METHODS[agg_idx] if agg_idx < len(AGGREGATION_METHODS) else None
            suffix = " Percentile" if is_percentile else ""
            meta = {
                "category": "Centroid Density",
                "plot_type": "kde",
                "aggregation": agg,
                "label": None,
                "filter": None,
                "title": (f"Centroid Density — Raw Baseline ({agg.title()}){suffix}"
                          if agg else f"Centroid Density — Raw Baseline{suffix}"),
                "auto_named": False,
            }
        else:
            meta = build_metadata(idx, ptype, dataset)

        rec_id = png_path.stem
        rec = records_by_id.get(rec_id)
        if rec is None:
            print(f"  Warning: no manifest record for {rec_id}")
            continue
        rec.update(meta)
        updated += 1

    return updated


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    records = manifest["records"]
    records_by_id = {r["id"]: r for r in records}

    total = 0
    for dataset in ("eicu", "mimic-iii", "mimic-iv"):
        print(f"Assigning metadata for EHR {dataset}...")
        n = assign_dataset(dataset, records_by_id)
        print(f"  {n} records updated")
        total += n

    # Recompute stats
    curated = sum(1 for r in records if not r["auto_named"])
    auto = sum(1 for r in records if r["auto_named"])
    manifest["stats"]["curated"] = curated
    manifest["stats"]["auto_named"] = auto

    # Recompute option_tree
    NULL = "—"
    tree: dict = {}
    for r in records:
        if r["superseded"]:
            continue
        ds = r["dataset"] or "unknown"
        pl = r["pipeline"] or "unknown"
        cat = r["category"] or "Uncategorized"
        lbl = r["label"] or NULL
        agg = r["aggregation"] or NULL
        tree.setdefault(ds, {}).setdefault(pl, {}).setdefault(cat, {}).setdefault(lbl, {}).setdefault(agg, []).append(r["id"])
    manifest["option_tree"] = tree

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(f"\nDone. {total} EHR records updated. curated={curated}, auto_named={auto}")


if __name__ == "__main__":
    main()
