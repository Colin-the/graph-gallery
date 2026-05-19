"""
Extract pre-rendered PNG images from Marimo WASM HTML exports.

The HTML files are interactive Marimo notebooks whose cell outputs (matplotlib
figures) are embedded as base64 PNGs in the __MARIMO_MOUNT_CONFIG__ JavaScript
object. This script reads each HTML file, extracts those PNGs, and saves them
into static/graphs/EHR-Dataset-Processing/{dataset}/.

Usage:
    python scripts/extract_marimo_html.py
"""

import base64
import re
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).parent.parent
SOURCE_DIR = Path(r"C:\Users\legoc\school\research\Data pre-processing html")
GRAPHS_DIR = REPO_ROOT / "static" / "graphs"
THUMB_WIDTH = 512

HTML_FILES = [
    ("eicu_analysis.html",                "eicu"),
    ("mimic_iii_analysis_uptpdate.html",  "mimic-iii"),
    ("mimic_iv_analysis.html",            "mimic-iv"),
]

PIPELINE = "EHR-Dataset-Processing"

# Matches the start of a base64-encoded PNG (iVBOR is the first 4 bytes of
# every PNG file encoded in base64).  We capture all valid base64 characters
# that follow so we don't need to worry about the JS/HTML encoding around it.
PNG_B64_RE = re.compile(r"iVBOR([A-Za-z0-9+/=]*)")


def safe_b64decode(b64str: str) -> bytes | None:
    """Decode base64, adding padding if needed. Returns None on failure."""
    pad = len(b64str) % 4
    if pad:
        b64str += "=" * (4 - pad)
    try:
        return base64.b64decode(b64str)
    except Exception:
        return None


def make_thumbnail(src_path: Path, thumb_path: Path) -> None:
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src_path) as img:
        w, h = img.size
        new_h = int(h * THUMB_WIDTH / w)
        thumb = img.resize((THUMB_WIDTH, new_h), Image.LANCZOS)
        thumb.save(thumb_path, "PNG", optimize=True)


def extract_html(html_file: str, dataset: str) -> int:
    src = SOURCE_DIR / html_file
    if not src.exists():
        print(f"  MISSING: {src}", file=sys.stderr)
        return 0

    out_dir = GRAPHS_DIR / PIPELINE / dataset
    thumb_dir = out_dir / "thumbs"
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Reading {html_file} ({src.stat().st_size / 1e6:.1f} MB)...")
    with open(src, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    raw_matches = PNG_B64_RE.findall(content)
    saved = 0
    for i, suffix in enumerate(raw_matches):
        png_bytes = safe_b64decode("iVBOR" + suffix)
        if png_bytes is None:
            print(f"    Warning: skipping image {i} (decode error)")
            continue

        slug = f"{dataset.replace('-', '_')}_{saved:04d}"
        png_path = out_dir / f"{slug}.png"
        thumb_path = thumb_dir / f"{slug}_thumb.png"

        png_path.write_bytes(png_bytes)
        make_thumbnail(png_path, thumb_path)
        saved += 1

    return saved


def main():
    total = 0
    for html_file, dataset in HTML_FILES:
        print(f"Processing {html_file} -> {dataset}...")
        n = extract_html(html_file, dataset)
        print(f"  {dataset}: {n} images saved")
        total += n
    print(f"\nTotal: {total} Marimo images extracted")


if __name__ == "__main__":
    main()
