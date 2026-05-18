/* ─── Graph Gallery App ─────────────────────────────────────────────────── */
"use strict";

let MANIFEST = null;       // full manifest JSON from /api/manifest
let RECORDS_BY_ID = {};    // id -> record
let SHOW_ALL = false;      // include superseded + auto_named
let COMPARE_MODE = false;

// ─── Bootstrap ───────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", async () => {
  await loadManifest();
  initDropdowns("", ["sel-dataset", "sel-pipeline", "sel-category", "sel-label", "sel-agg", "sel-graph"]);
  initDropdowns("cmp-", ["cmp-dataset-left", "cmp-pipeline-left", "cmp-category-left",
                         "cmp-label-left", "cmp-agg-left", "cmp-graph-left"], "left");
  initDropdowns("cmp-", ["cmp-dataset-right", "cmp-pipeline-right", "cmp-category-right",
                         "cmp-label-right", "cmp-agg-right", "cmp-graph-right"], "right");
  populateDataset("sel-dataset");
  populateDataset("cmp-dataset-left");
  populateDataset("cmp-dataset-right");

  document.getElementById("btn-help").addEventListener("click", () => showModal(true));
  document.getElementById("btn-close-help").addEventListener("click", () => showModal(false));
  document.getElementById("help-modal").addEventListener("click", e => {
    if (e.target === document.getElementById("help-modal")) showModal(false);
  });
  document.getElementById("btn-compare").addEventListener("click", toggleCompare);
  document.getElementById("btn-show-old").addEventListener("click", toggleShowAll);
  document.getElementById("btn-swap-left").addEventListener("click", swapPanes);

  updateStats();
});

async function loadManifest() {
  try {
    const res = await fetch("/api/manifest");
    MANIFEST = await res.json();
    RECORDS_BY_ID = {};
    for (const r of MANIFEST.records) RECORDS_BY_ID[r.id] = r;
  } catch (e) {
    console.error("Failed to load manifest:", e);
    document.getElementById("graph-placeholder").innerHTML =
      "<p style='color:#bd3140'>⚠ Could not load manifest. Run build_manifest.py first.</p>";
  }
}

// ─── Dropdown population helpers ─────────────────────────────────────────────

function visibleRecords() {
  if (!MANIFEST) return [];
  return MANIFEST.records.filter(r => {
    if (r.superseded && !SHOW_ALL) return false;
    if (r.auto_named && !SHOW_ALL && r.category === "Exploratory") return false;
    return !!r.file;
  });
}

function uniqueSorted(arr) {
  return [...new Set(arr.filter(Boolean))].sort();
}

function setOptions(selId, values, placeholder = "— any —") {
  const sel = document.getElementById(selId);
  const cur = sel.value;
  sel.innerHTML = `<option value="">${placeholder}</option>`;
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    sel.appendChild(opt);
  }
  if (values.includes(cur)) sel.value = cur;
  sel.disabled = values.length === 0;
}

function populateDataset(selId) {
  const records = visibleRecords();
  const datasets = uniqueSorted(records.map(r => r.dataset));
  setOptions(selId, datasets, "— select —");
}

// ─── Cascading dropdown logic (shared for main + compare panes) ───────────────

function initDropdowns(prefix, ids, pane = null) {
  // pane: null = main, "left" | "right" = compare pane
  const selIds = {
    dataset:  `${prefix}${pane ? "dataset-" + pane  : "dataset"}`,
    pipeline: `${prefix}${pane ? "pipeline-" + pane : "pipeline"}`,
    category: `${prefix}${pane ? "category-" + pane : "category"}`,
    label:    `${prefix}${pane ? "label-" + pane    : "label"}`,
    agg:      `${prefix}${pane ? "agg-" + pane      : "agg"}`,
    graph:    `${prefix}${pane ? "graph-" + pane    : "graph"}`,
  };

  const $ = id => document.getElementById(id);

  function filtered(upTo) {
    let recs = visibleRecords();
    if (upTo !== "dataset"  && $(selIds.dataset).value)  recs = recs.filter(r => r.dataset   === $(selIds.dataset).value);
    if (upTo !== "pipeline" && $(selIds.pipeline).value) recs = recs.filter(r => r.pipeline  === $(selIds.pipeline).value);
    if (upTo !== "category" && $(selIds.category).value) recs = recs.filter(r => r.category  === $(selIds.category).value);
    if (upTo !== "label"    && $(selIds.label).value)    recs = recs.filter(r => r.label     === $(selIds.label).value);
    if (upTo !== "agg"      && $(selIds.agg).value)      recs = recs.filter(r => r.aggregation === $(selIds.agg).value);
    return recs;
  }

  function refreshPipeline() {
    const recs = filtered("pipeline");
    setOptions(selIds.pipeline, uniqueSorted(recs.map(r => r.pipeline)), "— select —");
    refreshCategory();
  }
  function refreshCategory() {
    const recs = filtered("category");
    setOptions(selIds.category, uniqueSorted(recs.map(r => r.category)), "— select —");
    refreshLabel();
  }
  function refreshLabel() {
    const recs = filtered("label");
    const labels = uniqueSorted(recs.map(r => r.label).filter(Boolean));
    setOptions(selIds.label, labels, "— any —");
    refreshAgg();
  }
  function refreshAgg() {
    const recs = filtered("agg");
    const aggs = uniqueSorted(recs.map(r => r.aggregation).filter(Boolean));
    setOptions(selIds.agg, aggs, "— any —");
    refreshGraph();
  }
  function refreshGraph() {
    const recs = filtered("graph");
    const sortedRecs = [...recs].sort((a, b) => a.title.localeCompare(b.title));
    const sel = $(selIds.graph);
    sel.innerHTML = `<option value="">— select graph —</option>`;
    for (const r of sortedRecs) {
      const opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = r.title + (r.auto_named ? " *" : "");
      sel.appendChild(opt);
    }
    sel.disabled = sortedRecs.length === 0;
    // Auto-select if only one option
    if (sortedRecs.length === 1) {
      sel.value = sortedRecs[0].id;
      onGraphSelected(selIds.graph, pane);
    } else {
      onGraphSelected(selIds.graph, pane);  // clear if nothing selected
    }
  }

  $(selIds.dataset).addEventListener("change",  refreshPipeline);
  $(selIds.pipeline).addEventListener("change", refreshCategory);
  $(selIds.category).addEventListener("change", refreshLabel);
  $(selIds.label).addEventListener("change",    refreshAgg);
  $(selIds.agg).addEventListener("change",      refreshGraph);
  $(selIds.graph).addEventListener("change",    () => onGraphSelected(selIds.graph, pane));
}

// ─── Graph display ────────────────────────────────────────────────────────────

function onGraphSelected(graphSelId, pane = null) {
  const sel = document.getElementById(graphSelId);
  const id = sel ? sel.value : null;
  const record = id ? RECORDS_BY_ID[id] : null;

  if (pane === "left")  renderPane("left",  record);
  else if (pane === "right") renderPane("right", record);
  else                  renderMainPane(record);
}

function renderMainPane(record) {
  const img    = document.getElementById("graph-img-main");
  const title  = document.getElementById("graph-title-main");
  const desc   = document.getElementById("graph-desc-main");
  const tags   = document.getElementById("graph-tags-main");
  const ph     = document.getElementById("graph-placeholder");
  const dlLink = document.getElementById("link-download-main");
  const svgLink= document.getElementById("link-svg-main");
  const sugPan = document.getElementById("suggestions-panel");
  const sugList= document.getElementById("suggestions-list");

  if (!record) {
    img.style.display = "none";
    ph.style.display = "";
    dlLink.style.display = "none";
    svgLink.style.display = "none";
    sugPan.style.display = "none";
    title.textContent = "Select a graph from the sidebar";
    desc.textContent = "";
    tags.innerHTML = "";
    return;
  }

  ph.style.display = "none";
  title.textContent = record.title;
  desc.textContent = record.description || "";
  tags.innerHTML = buildTags(record);

  img.style.display = "";
  img.src = "/" + record.file;
  img.alt = record.title;

  dlLink.style.display = "";
  dlLink.href = "/" + record.file;
  dlLink.download = record.id + ".png";

  if (record.svg) {
    svgLink.style.display = "";
    svgLink.href = "/" + record.svg;
  } else {
    svgLink.style.display = "none";
  }

  // Suggestions
  if (record.suggested_pairs && record.suggested_pairs.length > 0) {
    sugList.innerHTML = "";
    for (const s of record.suggested_pairs.slice(0, 6)) {
      const peer = RECORDS_BY_ID[s.id];
      if (!peer) continue;
      const li = document.createElement("li");
      li.innerHTML = `<button>
        <div>${escHtml(peer.title)}</div>
        <div class="why">${escHtml(s.why)} · ${escHtml(peer.pipeline)}</div>
      </button>`;
      li.querySelector("button").addEventListener("click", () => {
        if (COMPARE_MODE) {
          prefillComparePane("right", peer.id);
        } else {
          openInMain(peer.id);
        }
      });
      sugList.appendChild(li);
    }
    sugPan.style.display = "";
  } else {
    sugPan.style.display = "none";
  }
}

function renderPane(side, record) {
  const img   = document.getElementById(`graph-img-${side}`);
  const title = document.getElementById(`graph-title-${side}`);
  const ph    = document.getElementById(`placeholder-${side}`);
  const dl    = document.getElementById(`dl-${side}`);
  const badge = document.getElementById(`compare-badge-${side}`);

  if (!record) {
    img.style.display = "none";
    ph.style.display = "";
    dl.style.display = "none";
    title.textContent = "—";
    if (badge) badge.style.display = "none";
    return;
  }

  ph.style.display = "none";
  img.style.display = "";
  img.src = "/" + record.file;
  img.alt = record.title;
  title.textContent = record.title;
  dl.style.display = "";
  dl.href = "/" + record.file;
  dl.download = record.id + ".png";

  // When left pane selects a new graph, auto-suggest the right pane
  if (side === "left" && record.suggested_pairs && record.suggested_pairs.length > 0) {
    const best = record.suggested_pairs[0];
    const peer = RECORDS_BY_ID[best.id];
    if (peer) {
      prefillComparePane("right", peer.id);
      const rb = document.getElementById("compare-badge-right");
      if (rb) { rb.textContent = "Suggested"; rb.style.display = ""; }
    }
  }
  if (badge && side === "right") {
    // Badge is set by auto-suggest logic above; clear it when user manually changes
    // (the change event fires, we clear it here since this is a manual selection)
    const selId = `cmp-graph-${side}`;
    const sel = document.getElementById(selId);
    if (sel && sel.value !== "" && badge.textContent === "Suggested") {
      // Keep badge — it was set by suggestion logic. Clear on next manual change.
    }
  }
}

function buildTags(r) {
  const items = [
    r.dataset    ? `<span class="tag">${escHtml(r.dataset)}</span>` : "",
    r.pipeline   ? `<span class="tag">${escHtml(r.pipeline)}</span>` : "",
    r.label      ? `<span class="tag">label: ${escHtml(r.label)}</span>` : "",
    r.aggregation? `<span class="tag">agg: ${escHtml(r.aggregation)}</span>` : "",
    r.vital      ? `<span class="tag">vital: ${escHtml(r.vital)}</span>` : "",
    r.filter     ? `<span class="tag">filter: ${escHtml(r.filter)}</span>` : "",
    r.plot_type  ? `<span class="tag">${escHtml(r.plot_type)}</span>` : "",
    r.auto_named ? `<span class="tag" style="color:#888">auto-named</span>` : "",
  ];
  return items.filter(Boolean).join("");
}

function openInMain(id) {
  const record = RECORDS_BY_ID[id];
  if (!record) return;
  // Set the graph selector in the main view to this record's id, then render
  const sel = document.getElementById("sel-graph");
  if (sel) {
    // Try to directly set and trigger
    for (const opt of sel.options) {
      if (opt.value === id) { sel.value = id; break; }
    }
  }
  renderMainPane(record);
}

function prefillComparePane(side, id) {
  const record = RECORDS_BY_ID[id];
  if (!record) return;
  renderPane(side, record);
  // Optionally update the selects in the compare pane to reflect the record
  const graphSel = document.getElementById(`cmp-graph-${side}`);
  if (graphSel) {
    for (const opt of graphSel.options) {
      if (opt.value === id) { graphSel.value = id; return; }
    }
    // Option not present — add it and select
    const opt = document.createElement("option");
    opt.value = id; opt.textContent = record.title;
    graphSel.appendChild(opt);
    graphSel.value = id;
  }
}

// ─── Compare / ShowAll toggles ─────────────────────────────────────────────

function toggleCompare() {
  COMPARE_MODE = !COMPARE_MODE;
  document.getElementById("single-view").style.display  = COMPARE_MODE ? "none" : "";
  document.getElementById("compare-view").style.display = COMPARE_MODE ? "" : "none";
  const btn = document.getElementById("btn-compare");
  btn.classList.toggle("active", COMPARE_MODE);
  btn.textContent = COMPARE_MODE ? "⬛ Single View" : "⬛ Side-by-Side";
  if (COMPARE_MODE) {
    populateDataset("cmp-dataset-left");
    populateDataset("cmp-dataset-right");
  }
}

function toggleShowAll() {
  SHOW_ALL = !SHOW_ALL;
  const btn = document.getElementById("btn-show-old");
  btn.classList.toggle("active", SHOW_ALL);
  btn.textContent = SHOW_ALL ? "📦 Hide Old" : "📦 Show All";
  // Refresh all selects
  populateDataset("sel-dataset");
  populateDataset("cmp-dataset-left");
  populateDataset("cmp-dataset-right");
  updateStats();
}

function swapPanes() {
  const leftImg   = document.getElementById("graph-img-left").src;
  const rightImg  = document.getElementById("graph-img-right").src;
  const leftTitle = document.getElementById("graph-title-left").textContent;
  const rightTitle= document.getElementById("graph-title-right").textContent;

  document.getElementById("graph-img-left").src   = rightImg;
  document.getElementById("graph-img-right").src  = leftImg;
  document.getElementById("graph-title-left").textContent  = rightTitle;
  document.getElementById("graph-title-right").textContent = leftTitle;
}

// ─── Help modal ────────────────────────────────────────────────────────────
function showModal(show) {
  document.getElementById("help-modal").style.display = show ? "flex" : "none";
}

// ─── Stats ─────────────────────────────────────────────────────────────────
function updateStats() {
  if (!MANIFEST) return;
  const vis = visibleRecords().length;
  const total = MANIFEST.stats.total;
  document.getElementById("gallery-stats").textContent =
    `${vis} graphs shown` + (SHOW_ALL ? "" : ` (${total - vis} hidden)`);
}

// ─── Utility ───────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
