#!/usr/bin/env python3
"""
Merge all manifest fragments into a single graphs_manifest.json.

Sources:
  static/graphs/extracted_manifest_fragment.json  -- from extract_notebook_graphs.py
  static/graphs/marimo_manifest_fragment.json      -- from render_marimo_mimic_iii.py (if exists)

Outputs:
  graphs_manifest.json  (at gallery root)

Also computes suggested_pairs: cross-pipeline pairings where the same
(dataset, aggregation, label, category) appears in both MIMIC_Extract and
EHR-Dataset-Processing, and for each pipeline_comparison graph its single-pipeline
source counterparts.
"""

import json
import os
from pathlib import Path
from typing import Optional

GALLERY = Path(__file__).parent.resolve()
STATIC = GALLERY / "static" / "graphs"

FRAGMENT_PATHS = [
    STATIC / "extracted_manifest_fragment.json",
    STATIC / "marimo_manifest_fragment.json",
]

OUT_PATH = GALLERY / "graphs_manifest.json"


# ─── Pairing heuristics ───────────────────────────────────────────────────────

def _key_cross_pipeline(r: dict) -> Optional[tuple]:
    """Key used to match records across MIMIC_Extract and EHR-Dataset-Processing."""
    if not r.get("dataset") or not r.get("category"):
        return None
    return (
        r.get("dataset"),
        r.get("category"),
        r.get("label"),
        r.get("aggregation"),
        r.get("vital"),
        r.get("plot_type"),
    )


def _key_cross_label(r: dict) -> Optional[tuple]:
    """Key to find the same plot for the other label (icu vs mortality)."""
    if not r.get("label"):
        return None
    return (
        r.get("dataset"),
        r.get("pipeline"),
        r.get("category"),
        r.get("aggregation"),
        r.get("vital"),
        r.get("plot_type"),
    )


def compute_suggestions(records: list) -> dict:
    """Return {id: [{"id": peer_id, "why": str}, ...]} suggestion map."""
    # Index by cross-pipeline key
    by_cross = {}
    for r in records:
        if r.get("superseded"):
            continue
        k = _key_cross_pipeline(r)
        if k:
            by_cross.setdefault(k, []).append(r)

    # Index by cross-label key
    by_label = {}
    for r in records:
        if r.get("superseded"):
            continue
        k = _key_cross_label(r)
        if k:
            by_label.setdefault(k, []).append(r)

    suggestions: dict = {}

    # Cross-pipeline pairings: MIMIC_Extract <-> EHR-Dataset-Processing
    for k, group in by_cross.items():
        pipelines = {r["pipeline"] for r in group}
        if "MIMIC_Extract" in pipelines and "EHR-Dataset-Processing" in pipelines:
            mimic_ids = [r["id"] for r in group if r["pipeline"] == "MIMIC_Extract"]
            ehr_ids = [r["id"] for r in group if r["pipeline"] == "EHR-Dataset-Processing"]
            for mid in mimic_ids:
                for eid in ehr_ids:
                    suggestions.setdefault(mid, []).append({"id": eid, "why": "Same plot type from EHR-Dataset-Processing"})
                    suggestions.setdefault(eid, []).append({"id": mid, "why": "Same plot type from MIMIC_Extract"})

    # Cross-label pairings (ICU vs Mortality for same pipeline/agg)
    for k, group in by_label.items():
        labels = {r["label"] for r in group if r.get("label")}
        if "icu" in labels and "mortality" in labels:
            icu_ids = [r["id"] for r in group if r.get("label") == "icu"]
            mort_ids = [r["id"] for r in group if r.get("label") == "mortality"]
            for iid in icu_ids:
                for mid in mort_ids:
                    suggestions.setdefault(iid, []).append({"id": mid, "why": "Same plot for Mortality label"})
                    suggestions.setdefault(mid, []).append({"id": iid, "why": "Same plot for ICU label"})

    # Comparison graphs paired with single-pipeline sources
    comp_records = [r for r in records if r.get("pipeline") == "Comparison" and not r.get("superseded")]
    for cr in comp_records:
        k = _key_cross_pipeline(cr)
        if k and k in by_cross:
            for peer in by_cross[k]:
                if peer["id"] != cr["id"] and peer["pipeline"] != "Comparison":
                    suggestions.setdefault(cr["id"], []).append({
                        "id": peer["id"],
                        "why": f"Single-pipeline source from {peer['pipeline']}"
                    })

    # De-duplicate suggestion lists
    for rid in suggestions:
        seen = set()
        deduped = []
        for s in suggestions[rid]:
            if s["id"] not in seen:
                seen.add(s["id"])
                deduped.append(s)
        suggestions[rid] = deduped[:6]  # cap at 6 per graph

    return suggestions


# ─── Dropdown option tree ─────────────────────────────────────────────────────

def build_option_tree(records: list) -> dict:
    """
    Returns a nested dict that drives the UI dropdowns:
    {
      dataset: {
        pipeline: {
          category: {
            label: {
              aggregation: [record_ids]
            }
          }
        }
      }
    }
    """
    tree: dict = {}
    for r in records:
        if r.get("superseded") or not r.get("file"):
            continue
        d = r.get("dataset") or "unknown"
        p = r.get("pipeline") or "unknown"
        c = r.get("category") or "Misc"
        lbl = r.get("label") or "—"
        agg = r.get("aggregation") or "—"

        tree.setdefault(d, {}).setdefault(p, {}).setdefault(c, {}).setdefault(lbl, {}).setdefault(agg, []).append(r["id"])

    return tree


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    all_records = []
    seen_ids: set = set()

    for frag_path in FRAGMENT_PATHS:
        if not frag_path.exists():
            print(f"[skip] {frag_path} not found")
            continue
        with open(frag_path) as f:
            frag = json.load(f)
        added = 0
        for r in frag:
            if r["id"] not in seen_ids:
                # Verify the image file exists (skip ghost records)
                if r.get("file"):
                    img_path = GALLERY / "static" / r["file"]
                    if not img_path.exists():
                        continue
                seen_ids.add(r["id"])
                all_records.append(r)
                added += 1
        print(f"Loaded {added} records from {frag_path.name}")

    print(f"\nTotal records: {len(all_records)}")

    suggestions = compute_suggestions(all_records)
    for r in all_records:
        r["suggested_pairs"] = suggestions.get(r["id"], [])

    option_tree = build_option_tree(all_records)

    manifest = {
        "records": all_records,
        "option_tree": option_tree,
        "stats": {
            "total": len(all_records),
            "curated": sum(1 for r in all_records if not r.get("auto_named")),
            "auto_named": sum(1 for r in all_records if r.get("auto_named")),
            "superseded": sum(1 for r in all_records if r.get("superseded")),
            "pipelines": sorted({r.get("pipeline") for r in all_records if r.get("pipeline")}),
            "datasets": sorted({r.get("dataset") for r in all_records if r.get("dataset")}),
        },
    }

    with open(OUT_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest written to {OUT_PATH}")
    print(f"  curated: {manifest['stats']['curated']}, auto_named: {manifest['stats']['auto_named']}")
    print(f"  datasets: {manifest['stats']['datasets']}")
    print(f"  pipelines: {manifest['stats']['pipelines']}")

    # Validation
    errors = 0
    for r in all_records:
        if r.get("file"):
            p = GALLERY / "static" / r["file"]
            if not p.exists():
                print(f"  [WARN] missing file: {r['file']}")
                errors += 1
    if errors:
        print(f"\n  {errors} missing image files")
    else:
        print("\n  All image files present ✓")


if __name__ == "__main__":
    main()
