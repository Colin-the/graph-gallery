"""
Build a new graphs_manifest.json from all PNGs currently in static/graphs/.

Usage:
    python scripts/build_new_manifest.py

Strategy:
  - Jupyter-extracted records: carry metadata from existing manifest by
    (notebook slug mapping + output index). Counts matched exactly so this
    is safe.
  - Marimo-extracted records (EHR-Dataset-Processing): match by id to
    existing manifest, then fall back to slug parsing.
  - Everything else: auto_named with null optional fields.

Writes graphs_manifest.json at the repo root.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
GRAPHS_DIR = REPO_ROOT / "static" / "graphs"
MANIFEST_PATH = REPO_ROOT / "graphs_manifest.json"
SIDECAR_PATH = Path(__file__).parent / "extracted_jupyter_metadata.json"

NULL_PLACEHOLDER = "—"  # em dash used in option_tree for null values

# Maps new notebook slug → old notebook slug (for metadata carryover)
NOTEBOOK_SLUG_MAP = {
    "curated_mimic_iii_analysis": "curated_mimic_iii_analysis_copy2",
    "experiment_statistics": "experiment_statistics",
    "mimic_extract_analysis": "mimic_extract_analysis",
    "pipeline_comparison": "pipeline_comparison",
}

# Pipeline → dataset (for Jupyter notebooks; Marimo records carry dataset in path)
JUPYTER_DATASET = {
    "MIMIC_Extract": "mimic-iii",
    "Comparison": "mimic-iii",
}

# EHR pipeline dataset path segment → dataset value
EHR_DATASET_MAP = {
    "mimic-iii": "mimic-iii",
    "mimic-iv": "mimic-iv",
    "eicu": "eicu",
}

# Known aggregation token → canonical value
AGGREGATION_TOKENS = {
    "mean": "mean",
    "median": "median",
    "std": "standard deviation",
    "standard_deviation": "standard deviation",
    "mean_deviation": "mean deviation",
    "maximum_deviation": "maximum deviation",
    "maxrange": "maximum deviation",
}

# Known filter/vital tokens → canonical value
VITAL_TOKENS = {
    "heart_rate": "heart rate",
    "systolic": "systolic blood pressure",
    "systolic_blood_pressure": "systolic blood pressure",
    "diastolic": "diastolic blood pressure",
    "diastolic_blood_pressure": "diastolic blood pressure",
    "mean_bp": "mean blood pressure",
    "mean_blood_pressure": "mean blood pressure",
    "respiration": "respiration rate",
    "respiration_rate": "respiration rate",
    "temperature": "temperature",
    "spo2": "SpO2",
    "o2_saturation": "SpO2",
}

FILTER_TOKENS = {
    "heart_rate": "heart rate",
    "systolic": "systolic blood pressure",
    "diastolic": "diastolic blood pressure",
    "mean_bp": "mean blood pressure",
    "respiration": "respiration rate",
    "temperature": "temperature",
    "spo2": "SpO2",
    "fill_missing": "fill missing data",
    "long_missing": "long missing segments",
    "long_gaps": "long gaps",
    "high_invalid": "high invalid data",
}


def load_existing_manifest() -> dict[str, dict]:
    """Return mapping id → record from the current manifest (reference only)."""
    if not MANIFEST_PATH.exists():
        return {}
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {r["id"]: r for r in data.get("records", [])}


def load_sidecar() -> dict[str, dict]:
    """Return mapping (notebook, output_index) → sidecar entry."""
    if not SIDECAR_PATH.exists():
        return {}
    entries = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    return {(e["notebook"], e["output_index"]): e for e in entries}


def parse_ehr_slug(slug: str) -> dict:
    """Best-effort parse of EHR-Dataset-Processing filename slugs."""
    tokens = slug.lower().split("_")
    result = {
        "category": None,
        "plot_type": None,
        "label": None,
        "aggregation": None,
        "vital": None,
        "filter": None,
        "title": slug.replace("_", " ").title(),
    }

    # Detect aggregation
    for i, tok in enumerate(tokens):
        if tok in AGGREGATION_TOKENS:
            result["aggregation"] = AGGREGATION_TOKENS[tok]
            break
        combo = "_".join(tokens[i:i+2])
        if combo in AGGREGATION_TOKENS:
            result["aggregation"] = AGGREGATION_TOKENS[combo]
            break

    # Detect category / plot type from leading tokens
    if tokens[0] in ("surface", "heatmap", "kde", "bar", "violin", "pca"):
        result["plot_type"] = tokens[0]
    if "centroid_shift" in slug:
        result["category"] = "Centroid Shift"
        result["plot_type"] = result["plot_type"] or "bar"
    elif "centroid" in slug or "centroid_density" in slug:
        result["category"] = "Centroid Density"
        result["plot_type"] = result["plot_type"] or "kde"
    elif "surface" in slug:
        result["category"] = "Surface Plot"
        result["plot_type"] = "surface"
    elif "heatmap" in slug:
        result["category"] = "Heatmap"
        result["plot_type"] = "heatmap"
    elif "filter_impact" in slug or "impact" in slug:
        result["category"] = "Filter Impact"
        result["plot_type"] = "bar"
    elif "mcnemar" in slug:
        result["category"] = "McNemar Significance"
        result["plot_type"] = "heatmap"

    # Detect filter token (appears after aggregation in slug)
    for tok_key, tok_val in FILTER_TOKENS.items():
        if tok_key in slug:
            result["filter"] = tok_val
            break

    return result


def build_record(png_path: Path, existing: dict[str, dict], sidecar: dict) -> dict:
    """Build a manifest record for a single PNG file."""
    rel = png_path.relative_to(GRAPHS_DIR)
    parts = rel.parts  # e.g. ['MIMIC_Extract', 'experiment_statistics', 'exp..._0000.png']

    pipeline = parts[0]
    stem = png_path.stem  # e.g. 'experiment_statistics_0000'

    # Determine notebook slug and dataset
    if pipeline in ("MIMIC_Extract", "Comparison"):
        notebook = parts[1] if len(parts) > 2 else stem
        dataset = JUPYTER_DATASET.get(pipeline, "mimic-iii")
        source = "extracted"
    elif pipeline == "EHR-Dataset-Processing":
        dataset_seg = parts[1] if len(parts) > 2 else "mimic-iii"
        dataset = EHR_DATASET_MAP.get(dataset_seg, dataset_seg)
        notebook = "notebook_py_marimo"
        source = "rendered"
    else:
        notebook = parts[1] if len(parts) > 2 else stem
        dataset = "mimic-iii"
        source = "extracted"

    record_id = stem

    # Build file paths
    file_path = "graphs/" + "/".join(rel.parts)
    thumb_path = (
        "graphs/"
        + "/".join(rel.parts[:-1])
        + "/thumbs/"
        + stem
        + "_thumb.png"
    )

    # Start with defaults
    record = {
        "id": record_id,
        "pipeline": pipeline,
        "dataset": dataset,
        "notebook": notebook,
        "category": None,
        "plot_type": None,
        "label": None,
        "aggregation": None,
        "vital": None,
        "scenario": None,
        "filter": None,
        "title": record_id.replace("_", " ").title(),
        "description": "",
        "file": file_path,
        "svg": None,
        "thumb": thumb_path,
        "auto_named": True,
        "superseded": False,
        "source": source,
        "suggested_pairs": [],
    }

    # Carry over from existing manifest by direct id match
    if record_id in existing:
        ref = existing[record_id]
        for field in ("category", "plot_type", "label", "aggregation", "vital",
                      "filter", "title", "description", "auto_named"):
            record[field] = ref.get(field, record[field])
        return record

    # Jupyter: try to match via notebook slug mapping + index
    if source == "extracted":
        old_notebook = NOTEBOOK_SLUG_MAP.get(notebook)
        if old_notebook:
            # Extract index from stem, e.g. curated_mimic_iii_analysis_0007 → 7
            m = re.search(r"_(\d{4})$", stem)
            if m:
                idx = int(m.group(1))
                old_id = f"{old_notebook}_{idx:04d}"
                if old_id in existing:
                    ref = existing[old_id]
                    for field in ("category", "plot_type", "label", "aggregation",
                                  "vital", "filter", "title", "description", "auto_named"):
                        record[field] = ref.get(field, record[field])
                    return record

    # EHR-Dataset-Processing: try marimo_ prefix match in existing
    if source == "rendered":
        marimo_id = f"marimo_{stem}" if not stem.startswith("marimo_") else stem
        if marimo_id in existing:
            ref = existing[marimo_id]
            for field in ("category", "plot_type", "label", "aggregation",
                          "vital", "filter", "title", "description", "auto_named"):
                record[field] = ref.get(field, record[field])
            return record
        # Fall back to slug parsing
        parsed = parse_ehr_slug(stem)
        record.update({k: v for k, v in parsed.items() if v is not None})
        record["auto_named"] = True

    return record


def score_pair(a: dict, b: dict) -> int:
    s = 0
    if a["plot_type"]   == b["plot_type"]:   s += 4
    if a["label"]       == b["label"]:       s += 3
    if a["aggregation"] == b["aggregation"]: s += 3
    if a["vital"]       == b["vital"]:       s += 2
    if a["filter"]      == b["filter"]:      s += 2
    return s


def suggestion_why(a: dict, b: dict) -> str:
    shared = []
    if a["aggregation"] and a["aggregation"] == b["aggregation"]:
        shared.append(a["aggregation"])
    if a["vital"] and a["vital"] == b["vital"]:
        shared.append(a["vital"])
    if a["label"] and a["label"] == b["label"]:
        shared.append(a["label"] + " label")
    if a["filter"] and a["filter"] == b["filter"]:
        shared.append(a["filter"] + " filter")
    return "Same " + (" · ".join(shared) if shared else (a["category"] or "category"))


def compute_suggested_pairs(records: list[dict]) -> None:
    """Mutate records in-place, setting suggested_pairs."""
    for rec in records:
        candidates = [
            r for r in records
            if r["id"]       != rec["id"]
            and r["pipeline"] != rec["pipeline"]
            and r["dataset"]  == rec["dataset"]
            and r["category"] == rec["category"]
            and rec["category"] is not None
        ]
        if not candidates:
            rec["suggested_pairs"] = []
            continue
        scored = sorted(
            [{"id": c["id"], "score": score_pair(rec, c), "why": suggestion_why(rec, c)}
             for c in candidates],
            key=lambda x: -x["score"],
        )
        rec["suggested_pairs"] = [{"id": s["id"], "why": s["why"]} for s in scored[:6]]


def build_option_tree(records: list[dict]) -> dict:
    tree: dict = {}
    for r in records:
        if r["superseded"]:
            continue
        ds = r["dataset"] or "unknown"
        pl = r["pipeline"] or "unknown"
        cat = r["category"] or "Uncategorized"
        lbl = r["label"] or NULL_PLACEHOLDER
        agg = r["aggregation"] or NULL_PLACEHOLDER

        tree.setdefault(ds, {}).setdefault(pl, {}).setdefault(cat, {}).setdefault(lbl, {}).setdefault(agg, []).append(r["id"])
    return tree


def main():
    print("Loading existing manifest for metadata reference...")
    existing = load_existing_manifest()
    print(f"  {len(existing)} existing records loaded")

    print("Discovering PNG files in static/graphs/...")
    png_files = [
        p for p in sorted(GRAPHS_DIR.rglob("*.png"))
        if "thumbs" not in p.parts
    ]
    print(f"  {len(png_files)} PNG files found")

    sidecar = load_sidecar()

    print("Building records...")
    records = [build_record(p, existing, sidecar) for p in png_files]

    print("Computing suggested pairs...")
    compute_suggested_pairs(records)

    curated = sum(1 for r in records if not r["auto_named"])
    auto = sum(1 for r in records if r["auto_named"])
    superseded = sum(1 for r in records if r["superseded"])
    pipelines = sorted({r["pipeline"] for r in records})
    datasets = sorted({r["dataset"] for r in records})

    manifest = {
        "records": records,
        "stats": {
            "total": len(records),
            "curated": curated,
            "auto_named": auto,
            "superseded": superseded,
            "pipelines": pipelines,
            "datasets": datasets,
        },
        "option_tree": build_option_tree(records),
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(f"\nDone. {len(records)} records written to {MANIFEST_PATH}")
    print(f"  curated={curated}, auto_named={auto}, superseded={superseded}")
    print(f"  pipelines: {pipelines}")
    print(f"  datasets:  {datasets}")


if __name__ == "__main__":
    main()
