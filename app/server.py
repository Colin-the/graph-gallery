#!/usr/bin/env python3
"""
Flask server for the Graph Gallery.
Routes:
  GET /                  -> index.html
  GET /api/manifest      -> graphs_manifest.json
  GET /graphs/<path>     -> static PNG/SVG images
"""

import json
import os
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, send_from_directory

GALLERY_ROOT = Path(__file__).parent.parent.resolve()
GRAPHS_DIR = GALLERY_ROOT / "static" / "graphs"
MANIFEST_PATH = GALLERY_ROOT / "graphs_manifest.json"

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
    static_url_path="/app-static",
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/manifest")
def manifest():
    if not MANIFEST_PATH.exists():
        abort(503, "graphs_manifest.json not found — run build_manifest.py first")
    with open(MANIFEST_PATH) as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/graphs/<path:filepath>")
def serve_graph(filepath):
    return send_from_directory(str(GRAPHS_DIR), filepath)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
