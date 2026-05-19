# ICU-EHR Graph Gallery

A browser-based viewer for research graphs produced by the ICU-EHR pipeline comparison project. The gallery covers 888 graphs across three datasets (MIMIC-III, MIMIC-IV, eICU) and two preprocessing pipelines (MIMIC_Extract and EHR-Dataset-Processing), plus a cross-pipeline comparison notebook.

## Running the application

The application runs entirely in Docker — no dependencies to install beyond Docker itself.

```bash
git clone https://github.com/Colin-the/graph-gallery.git
cd graph-gallery
docker compose up --build
```

Then open **http://localhost:8000** in your browser.

To use a different port, edit `docker-compose.yml` before running:

```yaml
ports:
  - "9000:8000"   # change 9000 to any port you want
```

To stop the application:

```bash
docker compose down
```

## Using the gallery

### Browsing graphs

Use the **Browse Graphs** panel on the left to filter down to a specific graph. The dropdowns cascade in order:

1. **Dataset** — MIMIC-III, MIMIC-IV, or eICU
2. **Pipeline** — which preprocessing pipeline produced the graph
3. **Category** — the type of analysis (e.g. Cohort Statistics, Filter Impact)
4. **Label** — the prediction target (ICU length of stay or mortality), if applicable
5. **Aggregation** — the feature aggregation method, if applicable
6. **Graph** — the specific graph to display

The counter below the filters updates live as you make selections, showing how many graphs match your current criteria.

Graph titles marked with `*` were automatically named from the notebook cell source rather than hand-curated.

### Side-by-side comparison

Click **Side-by-Side** in the header to open two independent graph panes. Each pane has its own set of filters. Use the **⇄ Swap**, **Copy →**, and **← Copy** buttons to rearrange what is shown on each side.

Click **Hide Controls** to collapse the filter dropdowns and focus on the graphs themselves.

### Suggested comparisons

When a graph has a counterpart in the other pipeline, a **Suggested Comparisons** panel appears in the sidebar. Clicking a suggestion opens the side-by-side view with the current graph on the left and the suggested match on the right.

### Show All

By default, superseded (older duplicate) graphs are hidden. Click **Show All** to include them.
