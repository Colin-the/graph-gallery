#!/usr/bin/env python3
"""
Assign research-question tags to all graphs in graphs_manifest.json.

Writes tags.json in the format expected by the Flask server:
  {"tags": [...], "assignments": {"graph_id": ["tag1", ...], ...}}
"""

import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
MANIFEST_PATH = REPO_ROOT / "graphs_manifest.json"
TAGS_PATH = REPO_ROOT / "tags.json"

TAGS = [
    "filtering-effects",
    "data-distribution",
    "ml-task-impact",
    "preprocessing-shift",
    "pipeline-transparency",
]

CATEGORY_TAGS = {
    # Q1 — filter effects on statistical structure
    "Filter Impact":                   ["filtering-effects"],
    "Length Analysis":                 ["filtering-effects"],
    "EHR Filter Pipeline":             ["filtering-effects"],
    "MIMIC_Extract Scenario Analysis": ["filtering-effects"],
    # Q1 supporting — the distribution itself
    "Centroid Density":                ["data-distribution"],
    # Q2 — ML task difficulty
    "Pipeline Comparison":             ["ml-task-impact"],
    "McNemar Significance":            ["ml-task-impact", "preprocessing-shift"],
    # Q3 — detecting preprocessing shifts
    "Centroid Shift":                  ["preprocessing-shift"],
    "Centroid Shift PCA":              ["preprocessing-shift"],
    "Cross-Pipeline Deviation":        ["preprocessing-shift"],
    # Q4 — pipeline transparency / explainability
    "Exploratory":                     ["pipeline-transparency"],
    "Vital Statistics":                ["pipeline-transparency"],
    "Cohort Statistics":               ["pipeline-transparency"],
    "Lens Plots":                      ["pipeline-transparency"],
}


def main():
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    records = manifest.get("records", [])
    assignments = {}
    unmapped = defaultdict(int)

    for record in records:
        graph_id = record["id"]
        category = record.get("category", "")
        tags = CATEGORY_TAGS.get(category)
        if tags:
            assignments[graph_id] = tags
        else:
            unmapped[category] += 1

    if unmapped:
        print("WARNING — unmapped categories (no tag assigned):")
        for cat, count in sorted(unmapped.items()):
            print(f"  {cat!r}: {count} records")
    else:
        print("All categories mapped.")

    tag_counts = defaultdict(int)
    for tags in assignments.values():
        for t in tags:
            tag_counts[t] += 1

    print(f"\nAssigned tags to {len(assignments)}/{len(records)} records:")
    for tag in TAGS:
        print(f"  {tag}: {tag_counts[tag]}")

    output = {"tags": TAGS, "assignments": assignments}
    with open(TAGS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {TAGS_PATH}")


if __name__ == "__main__":
    main()
