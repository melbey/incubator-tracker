#!/usr/bin/env python3
"""
Incubator Tracker - Instant browser UI + Google Apps Script sync

This version avoids Streamlit reruns for most interactions.
The UI runs in browser JavaScript and syncs to Google Sheets through Apps Script.

Important security note:
- APPS_SCRIPT_URL and APPS_SCRIPT_TOKEN are sent to the browser so JavaScript can sync directly.
- Anyone who can open the public app can potentially inspect/use the token.
- Use this only if the app/data are not highly sensitive, or keep the Streamlit app private.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components


APP_TITLE = "Incubator Tracker"
APP_VERSION = "instant-browser-v1.1-no-alert-layer"
SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def sweden_now_str() -> str:
    return datetime.now(SWEDEN_TZ).replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 1rem;
            max-width: 100%;
        }
        [data-testid="stStatusWidget"] {
            display: none !important;
        }
        iframe {
            border: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def app_html(apps_script_url: str, apps_script_token: str) -> str:
    url_js = json.dumps(apps_script_url)
    token_js = json.dumps(apps_script_token)

    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
:root {{
  color-scheme: light dark;
  --bg: #0e1117;
  --panel: #161b22;
  --panel2: #1f2630;
  --text: #f0f3f6;
  --muted: #9ca3af;
  --border: rgba(255,255,255,.12);
  --accent: #ff4b4b;
  --accent2: #2563eb;
  --good: #22c55e;
  --warn: #f59e0b;
  --danger: #ef4444;
  --button: #262d38;
  --button-hover: #303847;
}}

* {{
  box-sizing: border-box;
}}

html, body {{
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}

body {{
  padding: 10px 12px 60px;
}}

.header {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}}

h1 {{
  font-size: clamp(1.7rem, 4vw, 2.6rem);
  margin: 0 0 .25rem;
}}

h2 {{
  margin: 1.3rem 0 .7rem;
}}

.subtitle {{
  color: var(--muted);
  font-size: .9rem;
}}

.toolbar {{
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  align-items: center;
  justify-content: flex-end;
}}

button {{
  border: 1px solid var(--border);
  background: var(--button);
  color: var(--text);
  padding: .55rem .75rem;
  border-radius: .55rem;
  cursor: pointer;
  font-weight: 650;
  min-height: 38px;
}}

button:hover {{
  background: var(--button-hover);
}}

button.primary {{
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}}

button.blue {{
  background: var(--accent2);
  border-color: var(--accent2);
  color: white;
}}

button.danger {{
  color: #fecaca;
}}

button:disabled {{
  opacity: .45;
  cursor: not-allowed;
}}

.status {{
  color: var(--muted);
  font-size: .86rem;
  min-height: 1.4rem;
  margin-bottom: .6rem;
}}

.tabs {{
  display: flex;
  flex-wrap: wrap;
  gap: .35rem;
  border-bottom: 1px solid var(--border);
  margin: 1rem 0;
}}

.tab {{
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
}}

.tab.active {{
  color: #ff7777;
  border-bottom-color: var(--accent);
}}

.panel {{
  display: none;
}}

.panel.active {{
  display: block;
}}

.alerts {{
  display: flex;
  flex-direction: column;
  gap: .5rem;
  margin-bottom: 1rem;
}}

.alert {{
  border: 1px solid var(--border);
  background: rgba(37, 99, 235, .12);
  border-radius: .6rem;
  padding: .8rem 1rem;
}}

.alert.warn {{
  background: rgba(245, 158, 11, .14);
}}

.alert.danger {{
  background: rgba(239, 68, 68, .14);
}}

.table-wrap {{
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: .75rem;
  max-height: 58vh;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  min-width: 980px;
}}

th, td {{
  border-bottom: 1px solid var(--border);
  padding: .55rem .65rem;
  text-align: left;
  white-space: nowrap;
}}

th {{
  position: sticky;
  top: 0;
  background: var(--panel2);
  z-index: 2;
  color: var(--muted);
  font-weight: 700;
}}

tr.selected {{
  background: rgba(255, 75, 75, .13);
}}

tr.overdue td {{
  color: #fecaca;
}}

tr.due td {{
  color: #fde68a;
}}

.quick-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  margin: .9rem 0;
  align-items: center;
}}

.selected-count {{
  color: var(--muted);
  margin-right: .5rem;
}}

.form-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: .8rem;
  max-width: 950px;
}}

label {{
  display: block;
  color: var(--muted);
  font-size: .85rem;
  margin-bottom: .25rem;
}}

input, textarea, select {{
  width: 100%;
  background: var(--panel);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: .55rem;
  padding: .65rem .75rem;
  font-size: 1rem;
  min-height: 42px;
}}

textarea {{
  min-height: 110px;
  resize: vertical;
}}

.full {{
  grid-column: 1 / -1;
}}

.form-actions {{
  display: flex;
  gap: .5rem;
  flex-wrap: wrap;
  margin-top: .9rem;
}}

.card {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: .75rem;
  padding: 1rem;
  margin-bottom: .8rem;
}}

.raw-pre {{
  white-space: pre-wrap;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: .75rem;
  padding: 1rem;
  max-height: 60vh;
  overflow: auto;
}}

.hidden {{
  display: none !important;
}}

@media (max-width: 850px) {{
  body {{
    padding: 8px 8px 80px;
  }}

  .header {{
    display: block;
  }}

  .toolbar {{
    justify-content: flex-start;
    margin-top: .75rem;
  }}

  .form-grid {{
    grid-template-columns: 1fr;
  }}

  .quick-actions button {{
    flex: 1 1 45%;
  }}
}}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Incubator Tracker</h1>
      <div class="subtitle">{html.escape(APP_VERSION)} · Sweden time: <span id="swedenTime"></span></div>
    </div>
    <div class="toolbar">
      <button id="reloadBtn">Reload</button>
      <button id="saveBtn" class="primary">Save now</button>
      <button id="exportBtn">Export JSON</button>
      <button id="importBtn">Import JSON</button>
      <input id="importFile" type="file" accept=".json,application/json" style="display:none" />
    </div>
  </div>

  <div id="status" class="status">Starting...</div>

  <div class="tabs">
    <button class="tab active" data-tab="dashboard">Dashboard</button>
    <button class="tab" data-tab="add">Add culture</button>
    <button class="tab" data-tab="edit">Edit selected</button>
    <button class="tab" data-tab="infection">Infection timepoints</button>
    <button class="tab" data-tab="raw">Raw data</button>
  </div>

  <section id="dashboard" class="panel active">
    <h2>Cultures / Plates</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Select</th>
            <th>Cell line</th>
            <th>Plates</th>
            <th>PD today</th>
            <th>Media</th>
            <th>Split</th>
            <th>Drug exposure</th>
            <th>Infection</th>
          </tr>
        </thead>
        <tbody id="cultureRows"></tbody>
      </table>
    </div>

    <div class="quick-actions">
      <span class="selected-count">Selected: <span id="selectedCount">0</span></span>
      <button id="mediaTodayBtn" disabled>Media changed today</button>
      <button id="splitTodayBtn" disabled>Split checked today</button>
      <button id="recordSplitBtn" disabled>Record split today</button>
      <button id="infectionNowBtn" disabled>1st infection now</button>
      <button id="repairDatesBtn">Repair missing dates</button>
    </div>

    <div id="selectedDetails"></div>
  </section>

  <section id="add" class="panel">
    <h2>Add culture</h2>
    <div id="addForm"></div>
  </section>

  <section id="edit" class="panel">
    <h2>Edit selected culture</h2>
    <div id="editEmpty" class="card">Select one culture from the dashboard first.</div>
    <div id="editForm"></div>
  </section>

  <section id="infection" class="panel">
    <h2>Infection timepoints</h2>
    <div id="infectionRows" class="card"></div>
  </section>

  <section id="raw" class="panel">
    <h2>Raw data</h2>
    <pre id="rawData" class="raw-pre"></pre>
  </section>

<script>
const APPS_SCRIPT_URL = {url_js};
const APPS_SCRIPT_TOKEN = {token_js};

const DATE_FMT_RE = /^\\d{{4}}-\\d{{2}}-\\d{{2}}$/;
const DATETIME_FMT_RE = /^\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}$/;
const MEDIA_INTERVAL_DAYS = 2;
const SPLIT_CHECK_INTERVAL_DAYS = 2;
const INFECTION_T0_OFFSET_HOURS = 12;
const INFECTION_TARGET_HOURS = [72, 84, 96, 108, 120, 132, 144];

let cultures = [];
let selectedIds = new Set();
let saveTimer = null;
let saving = false;
let dirty = false;
let lastSavedJson = "";

function uuid() {{
  if (crypto && crypto.randomUUID) return crypto.randomUUID();
  return "culture-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
}}

function setStatus(text, kind="") {{
  const el = document.getElementById("status");
  el.textContent = text;
  el.style.color = kind === "error" ? "#f87171" : kind === "ok" ? "#86efac" : "var(--muted)";
}}

function swedenDateObj() {{
  const parts = new Intl.DateTimeFormat("sv-SE", {{
    timeZone: "Europe/Stockholm",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }}).formatToParts(new Date());

  const get = type => parts.find(p => p.type === type).value;
  return new Date(Number(get("year")), Number(get("month")) - 1, Number(get("day")), Number(get("hour")), Number(get("minute")));
}}

function swedenTodayString() {{
  const d = swedenDateObj();
  return formatDate(d);
}}

function swedenNowString() {{
  const d = swedenDateObj();
  return formatDatetime(d);
}}

function pad(n) {{
  return String(n).padStart(2, "0");
}}

function formatDate(d) {{
  return `${{d.getFullYear()}}-${{pad(d.getMonth() + 1)}}-${{pad(d.getDate())}}`;
}}

function formatDatetime(d) {{
  return `${{formatDate(d)}} ${{pad(d.getHours())}}:${{pad(d.getMinutes())}}`;
}}

function parseDate(value) {{
  value = normalizeDateString(value);
  if (!value || !DATE_FMT_RE.test(value)) return null;
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}}

function parseDatetime(value) {{
  value = normalizeDatetimeString(value);
  if (!value || !DATETIME_FMT_RE.test(value)) return null;
  const [datePart, timePart] = value.split(" ");
  const [y, m, d] = datePart.split("-").map(Number);
  const [hh, mm] = timePart.split(":").map(Number);
  return new Date(y, m - 1, d, hh, mm);
}}

function addDays(d, days) {{
  const copy = new Date(d);
  copy.setDate(copy.getDate() + days);
  return copy;
}}

function addHours(d, hours) {{
  const copy = new Date(d);
  copy.setHours(copy.getHours() + hours);
  return copy;
}}

function daysBetween(a, b) {{
  const aa = new Date(a.getFullYear(), a.getMonth(), a.getDate());
  const bb = new Date(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((aa - bb) / (1000 * 60 * 60 * 24));
}}

function normalizeDateString(value) {{
  if (value === null || value === undefined) return "";
  let text = String(value).trim();
  if (!text || ["none", "nan", "nat"].includes(text.toLowerCase())) return "";
  if (DATE_FMT_RE.test(text)) return text;
  if (text.length >= 10 && text[4] === "-" && text[7] === "-") return text.slice(0, 10);
  return text;
}}

function normalizeDatetimeString(value) {{
  if (value === null || value === undefined) return "";
  let text = String(value).trim();
  if (!text || ["none", "nan", "nat"].includes(text.toLowerCase())) return "";
  if (DATETIME_FMT_RE.test(text)) return text;
  if (text.length >= 16 && text[4] === "-" && text[7] === "-") return text.slice(0, 16).replace("T", " ");
  return text;
}}

function normalizeCulture(item) {{
  item = item || {{}};
  const activeRaw = item.infection_active;
  let infectionActive = false;
  if (typeof activeRaw === "string") {{
    infectionActive = ["true", "1", "yes", "y", "on"].includes(activeRaw.trim().toLowerCase());
  }} else {{
    infectionActive = Boolean(activeRaw);
  }}

  return {{
    id: String(item.id || uuid()),
    cell_line: String(item.cell_line || ""),
    plate_count: Number(item.plate_count || 0),
    plated_date: normalizeDateString(item.plated_date),
    revived_date: normalizeDateString(item.revived_date),
    current_pd: Number(item.current_pd || 0),
    pd_date: normalizeDateString(item.pd_date),
    last_media_change: normalizeDateString(item.last_media_change),
    last_split_check: normalizeDateString(item.last_split_check),
    drug_name: String(item.drug_name || ""),
    drug_added_datetime: normalizeDatetimeString(item.drug_added_datetime),
    infection_active: infectionActive,
    first_infection_datetime: normalizeDatetimeString(item.first_infection_datetime),
    notes: String(item.notes || "")
  }};
}}

async function api(action, payload={{}}) {{
  const res = await fetch(APPS_SCRIPT_URL, {{
    method: "POST",
    headers: {{ "Content-Type": "text/plain;charset=utf-8" }},
    body: JSON.stringify({{
      action,
      token: APPS_SCRIPT_TOKEN,
      ...payload
    }})
  }});

  if (!res.ok) throw new Error("HTTP " + res.status);
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "Unknown backend error");
  return data;
}}

async function loadCultures() {{
  try {{
    setStatus("Loading from Google Sheets...");
    const data = await api("load");
    cultures = (data.cultures || []).map(normalizeCulture);
    lastSavedJson = JSON.stringify(cultures);
    dirty = false;
    selectedIds.clear();
    renderAll();
    setStatus("Loaded. Ready.", "ok");
  }} catch (err) {{
    setStatus("Could not load: " + err.message, "error");
    renderAll();
  }}
}}

async function saveCultures(force=false) {{
  if (saving) return;
  const currentJson = JSON.stringify(cultures);
  if (!force && currentJson === lastSavedJson) {{
    dirty = false;
    return;
  }}

  saving = true;
  setStatus("Saving...");
  try {{
    await api("save", {{ cultures }});
    lastSavedJson = JSON.stringify(cultures);
    dirty = false;
    setStatus("Saved.", "ok");
  }} catch (err) {{
    setStatus("Save failed: " + err.message, "error");
  }} finally {{
    saving = false;
  }}
}}

function scheduleSave(delay=650) {{
  dirty = true;
  setStatus("Changed locally. Saving soon...");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => saveCultures(false), delay);
}}

function statusFromDue(due) {{
  if (!due) return "Not set";
  const delta = daysBetween(due, swedenDateObj());
  if (delta < 0) return `OVERDUE by ${{-delta}} day(s)`;
  if (delta === 0) return "Due today";
  if (delta === 1) return "Due tomorrow";
  return `Due in ${{delta}} days`;
}}

function actionStatus(lastDone, due) {{
  const today = swedenTodayString();
  if (lastDone && normalizeDateString(lastDone) === today && due) {{
    const delta = daysBetween(due, swedenDateObj());
    if (delta === 1) return "Done today; next tomorrow";
    return `Done today; next in ${{delta}} days`;
  }}
  return statusFromDue(due);
}}

function lastMedia(c) {{
  return parseDate(c.last_media_change) || parseDate(c.plated_date);
}}

function lastSplit(c) {{
  return parseDate(c.last_split_check) || parseDate(c.plated_date);
}}

function nextMediaDue(c) {{
  const d = lastMedia(c);
  return d ? addDays(d, MEDIA_INTERVAL_DAYS) : null;
}}

function nextSplitDue(c) {{
  const d = lastSplit(c);
  return d ? addDays(d, SPLIT_CHECK_INTERVAL_DAYS) : null;
}}

function effectivePdToday(c) {{
  const pdDate = parseDate(c.pd_date);
  if (!pdDate) return Number(c.current_pd || 0);
  const elapsed = Math.max(0, daysBetween(swedenDateObj(), pdDate));
  return Number(c.current_pd || 0) + elapsed;
}}

function humanDurationSince(dt) {{
  if (!dt) return "";
  let deltaMs = swedenDateObj() - dt;
  const future = deltaMs < 0;
  if (future) deltaMs = -deltaMs;

  const totalMinutes = Math.floor(deltaMs / (1000 * 60));
  const days = Math.floor(totalMinutes / (24 * 60));
  const rem = totalMinutes % (24 * 60);
  const hours = Math.floor(rem / 60);
  const minutes = rem % 60;

  let text;
  if (days >= 1) text = hours ? `${{days}} d ${{hours}} h` : `${{days}} d`;
  else if (hours >= 1) text = minutes ? `${{hours}} h ${{minutes}} min` : `${{hours}} h`;
  else text = `${{minutes}} min`;
  return future ? `in ${{text}}` : text;
}}

function drugStatus(c) {{
  if (!c.drug_name.trim()) return "None";
  const dt = parseDatetime(c.drug_added_datetime);
  if (!dt) return c.drug_name.trim();
  return `${{c.drug_name.trim()}} — ${{humanDurationSince(dt)}}`;
}}

function infectionTimepoints(c) {{
  const first = parseDatetime(c.first_infection_datetime);
  if (!first || !c.infection_active) return [];
  const t0 = addHours(first, INFECTION_T0_OFFSET_HOURS);
  const rows = [{{ label: "t=0", dt: t0 }}];
  INFECTION_TARGET_HOURS.forEach(h => rows.push({{ label: `${{h}} h`, dt: addHours(t0, h) }}));
  return rows;
}}

function selectedCultures() {{
  return cultures.filter(c => selectedIds.has(c.id));
}}

function sortCultures(list) {{
  return [...list].sort((a, b) => a.cell_line.toLowerCase().localeCompare(b.cell_line.toLowerCase()));
}}

function renderAll() {{
  renderAlerts();
  renderTable();
  renderQuickActions();
  renderSelectedDetails();
  renderEditForm();
  renderInfection();
  renderRaw();
}}

function renderAlerts() {{
  // Alert layer removed. Due/overdue status is shown by table highlighting.
}}

function renderTable() {{
  const tbody = document.getElementById("cultureRows");
  tbody.innerHTML = "";

  sortCultures(cultures).forEach(c => {{
    const mediaStatus = actionStatus(c.last_media_change || c.plated_date, nextMediaDue(c));
    const splitStatus = actionStatus(c.last_split_check || c.plated_date, nextSplitDue(c));

    const tr = document.createElement("tr");
    if (selectedIds.has(c.id)) tr.classList.add("selected");
    if (mediaStatus.includes("OVERDUE") || splitStatus.includes("OVERDUE")) tr.classList.add("overdue");
    else if (mediaStatus === "Due today" || splitStatus === "Due today") tr.classList.add("due");

    const checkboxCell = document.createElement("td");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = selectedIds.has(c.id);
    cb.addEventListener("change", () => {{
      if (cb.checked) selectedIds.add(c.id);
      else selectedIds.delete(c.id);
      renderAll();
    }});
    checkboxCell.appendChild(cb);
    tr.appendChild(checkboxCell);

    [
      c.cell_line,
      String(c.plate_count),
      effectivePdToday(c).toFixed(1),
      mediaStatus,
      splitStatus,
      drugStatus(c),
      c.infection_active ? "Yes" : "No"
    ].forEach(text => {{
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }});

    tbody.appendChild(tr);
  }});
}}

function renderQuickActions() {{
  const selected = selectedCultures();
  document.getElementById("selectedCount").textContent = String(selected.length);
  ["mediaTodayBtn", "splitTodayBtn", "recordSplitBtn", "infectionNowBtn"].forEach(id => {{
    document.getElementById(id).disabled = selected.length === 0;
  }});
}}

function renderSelectedDetails() {{
  const root = document.getElementById("selectedDetails");
  root.innerHTML = "";
  const selected = selectedCultures();
  if (!selected.length) return;

  selected.forEach(c => {{
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<strong>${{escapeHtml(c.cell_line)}}</strong><br>
      Plates: ${{c.plate_count}} · PD today: ${{effectivePdToday(c).toFixed(1)}}<br>
      Plated: ${{escapeHtml(c.plated_date || "Not set")}} · Media: ${{escapeHtml(c.last_media_change || "Not set")}} · Split: ${{escapeHtml(c.last_split_check || "Not set")}}<br>
      Notes: ${{escapeHtml(c.notes || "")}}`;
    root.appendChild(card);
  }});
}}

function renderInfection() {{
  const root = document.getElementById("infectionRows");
  root.innerHTML = "";
  const rows = [];

  cultures.forEach(c => {{
    infectionTimepoints(c).forEach(tp => {{
      rows.push({{
        cell_line: c.cell_line,
        timepoint: tp.label,
        datetime: formatDatetime(tp.dt),
        status: tp.dt < swedenDateObj() ? "past" : "upcoming"
      }});
    }});
  }});

  if (!rows.length) {{
    root.textContent = "No active infection timepoints.";
    return;
  }}

  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>Cell line</th><th>Timepoint</th><th>Date/time</th><th>Status</th></tr></thead>";
  const tbody = document.createElement("tbody");
  rows.forEach(r => {{
    const tr = document.createElement("tr");
    [r.cell_line, r.timepoint, r.datetime, r.status].forEach(text => {{
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }});
    tbody.appendChild(tr);
  }});
  table.appendChild(tbody);
  root.appendChild(table);
}}

function renderRaw() {{
  document.getElementById("rawData").textContent = JSON.stringify(cultures, null, 2);
}}

function renderEditForm() {{
  const selected = selectedCultures();
  const empty = document.getElementById("editEmpty");
  const root = document.getElementById("editForm");

  root.innerHTML = "";
  if (selected.length !== 1) {{
    empty.textContent = selected.length > 1 ? "Select only one culture to edit." : "Select one culture from the dashboard first.";
    empty.classList.remove("hidden");
    return;
  }}

  empty.classList.add("hidden");
  root.appendChild(cultureForm(selected[0], false));
}}

function cultureForm(culture=null, isAdd=true) {{
  const c = culture ? {{...culture}} : normalizeCulture({{ pd_date: swedenTodayString(), plate_count: 1 }});
  const wrap = document.createElement("div");

  wrap.innerHTML = `
    <div class="form-grid">
      ${{fieldHtml("Cell line", "cell_line", c.cell_line, "text", true)}}
      ${{fieldHtml("Number of plates", "plate_count", c.plate_count, "number")}}
      ${{fieldHtml("Date plated", "plated_date", c.plated_date, "text", false, "YYYY-MM-DD")}}
      ${{fieldHtml("Date revived", "revived_date", c.revived_date, "text", false, "YYYY-MM-DD")}}
      ${{fieldHtml("Current PD", "current_pd", c.current_pd, "number")}}
      ${{fieldHtml("PD date", "pd_date", c.pd_date, "text", false, "YYYY-MM-DD")}}
      ${{fieldHtml("Last media change", "last_media_change", c.last_media_change, "text", false, "YYYY-MM-DD")}}
      ${{fieldHtml("Last split check", "last_split_check", c.last_split_check, "text", false, "YYYY-MM-DD")}}
      ${{fieldHtml("Drug name", "drug_name", c.drug_name)}}
      ${{fieldHtml("Drug added", "drug_added_datetime", c.drug_added_datetime, "text", false, "YYYY-MM-DD HH:MM")}}
      <div>
        <label>Infection active</label>
        <select data-field="infection_active">
          <option value="false" ${{!c.infection_active ? "selected" : ""}}>No</option>
          <option value="true" ${{c.infection_active ? "selected" : ""}}>Yes</option>
        </select>
      </div>
      ${{fieldHtml("1st infection", "first_infection_datetime", c.first_infection_datetime, "text", false, "YYYY-MM-DD HH:MM")}}
      <div class="full">
        <label>Notes</label>
        <textarea data-field="notes">${{escapeHtml(c.notes)}}</textarea>
      </div>
    </div>
    <div class="form-actions">
      <button class="primary" data-action="save">${{isAdd ? "Add culture" : "Save changes"}}</button>
      ${{!isAdd ? '<button data-action="duplicate">Duplicate</button><button class="danger" data-action="delete">Delete</button>' : ""}}
      <button data-action="clear">Clear</button>
    </div>
  `;

  wrap.querySelector('[data-action="save"]').addEventListener("click", () => {{
    try {{
      const newCulture = readCultureFromForm(wrap, c.id);
      if (isAdd) {{
        cultures.push(newCulture);
        selectedIds.clear();
        selectedIds.add(newCulture.id);
        showTab("dashboard");
      }} else {{
        const idx = cultures.findIndex(x => x.id === culture.id);
        if (idx >= 0) cultures[idx] = newCulture;
      }}
      renderAll();
      scheduleSave();
    }} catch (err) {{
      alert(err.message);
    }}
  }});

  const clear = wrap.querySelector('[data-action="clear"]');
  clear.addEventListener("click", () => {{
    if (isAdd) {{
      document.getElementById("addForm").innerHTML = "";
      document.getElementById("addForm").appendChild(cultureForm(null, true));
    }} else {{
      renderEditForm();
    }}
  }});

  const dup = wrap.querySelector('[data-action="duplicate"]');
  if (dup) {{
    dup.addEventListener("click", () => {{
      const copy = normalizeCulture({{...culture, id: uuid(), cell_line: culture.cell_line + " copy" }});
      cultures.push(copy);
      selectedIds.clear();
      selectedIds.add(copy.id);
      showTab("dashboard");
      renderAll();
      scheduleSave();
    }});
  }}

  const del = wrap.querySelector('[data-action="delete"]');
  if (del) {{
    del.addEventListener("click", () => {{
      if (confirm(`Delete “${{culture.cell_line}}”?`)) {{
        cultures = cultures.filter(x => x.id !== culture.id);
        selectedIds.delete(culture.id);
        showTab("dashboard");
        renderAll();
        scheduleSave();
      }}
    }});
  }}

  return wrap;
}}

function fieldHtml(label, field, value, type="text", required=false, placeholder="") {{
  return `<div>
    <label>${{escapeHtml(label)}}</label>
    <input data-field="${{field}}" type="${{type}}" value="${{escapeHtml(String(value || ""))}}" placeholder="${{escapeHtml(placeholder)}}" ${{required ? "required" : ""}} />
  </div>`;
}}

function readCultureFromForm(root, existingId) {{
  const get = field => {{
    const el = root.querySelector(`[data-field="${{field}}"]`);
    return el ? el.value.trim() : "";
  }};

  const c = normalizeCulture({{
    id: existingId || uuid(),
    cell_line: get("cell_line"),
    plate_count: Number(get("plate_count") || 0),
    plated_date: get("plated_date"),
    revived_date: get("revived_date"),
    current_pd: Number(get("current_pd") || 0),
    pd_date: get("pd_date"),
    last_media_change: get("last_media_change"),
    last_split_check: get("last_split_check"),
    drug_name: get("drug_name"),
    drug_added_datetime: get("drug_added_datetime"),
    infection_active: get("infection_active") === "true",
    first_infection_datetime: get("first_infection_datetime"),
    notes: get("notes")
  }});

  if (!c.cell_line) throw new Error("Cell line is required.");

  ["plated_date", "revived_date", "pd_date", "last_media_change", "last_split_check"].forEach(field => {{
    if (c[field] && !DATE_FMT_RE.test(c[field])) throw new Error(`${{field}} must be YYYY-MM-DD.`);
  }});

  ["drug_added_datetime", "first_infection_datetime"].forEach(field => {{
    if (c[field] && !DATETIME_FMT_RE.test(c[field])) throw new Error(`${{field}} must be YYYY-MM-DD HH:MM.`);
  }});

  return c;
}}

function repairMissingDates() {{
  const today = swedenTodayString();
  let changed = 0;
  cultures.forEach(c => {{
    if (!normalizeDateString(c.plated_date)) {{
      c.plated_date = today;
      changed++;
    }}
    if (!normalizeDateString(c.last_media_change)) {{
      c.last_media_change = c.plated_date || today;
      changed++;
    }}
    if (!normalizeDateString(c.last_split_check)) {{
      c.last_split_check = c.plated_date || today;
      changed++;
    }}
  }});
  renderAll();
  scheduleSave();
  alert(`Repaired ${{changed}} missing date field(s).`);
}}

function exportJson() {{
  const blob = new Blob([JSON.stringify(cultures, null, 2)], {{ type: "application/json" }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "incubator_tracker_backup.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}}

function importJsonFile(file) {{
  const reader = new FileReader();
  reader.onload = () => {{
    try {{
      let data = JSON.parse(reader.result);
      if (data && !Array.isArray(data) && Array.isArray(data.cultures)) data = data.cultures;
      if (!Array.isArray(data)) throw new Error("JSON must be a list of cultures or an object with a cultures list.");
      const imported = data.map(normalizeCulture);
      if (confirm(`Replace current cultures with ${{imported.length}} imported culture(s)?`)) {{
        cultures = imported;
        selectedIds.clear();
        if (confirm("Fill missing plated/media/split dates with today in Sweden?")) {{
          repairMissingDates();
        }} else {{
          renderAll();
          scheduleSave();
        }}
      }}
    }} catch (err) {{
      alert("Import failed: " + err.message);
    }}
  }};
  reader.readAsText(file);
}}

function showTab(id) {{
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === id));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === id));
  if (id === "add") {{
    document.getElementById("addForm").innerHTML = "";
    document.getElementById("addForm").appendChild(cultureForm(null, true));
  }}
  if (id === "edit") renderEditForm();
  if (id === "infection") renderInfection();
  if (id === "raw") renderRaw();
}}

function escapeHtml(s) {{
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}}

document.querySelectorAll(".tab").forEach(tab => {{
  tab.addEventListener("click", () => showTab(tab.dataset.tab));
}});

document.getElementById("reloadBtn").addEventListener("click", () => {{
  if (dirty && !confirm("You have unsaved local changes. Reload anyway?")) return;
  loadCultures();
}});
document.getElementById("saveBtn").addEventListener("click", () => saveCultures(true));
document.getElementById("exportBtn").addEventListener("click", exportJson);
document.getElementById("importBtn").addEventListener("click", () => document.getElementById("importFile").click());
document.getElementById("importFile").addEventListener("change", e => {{
  if (e.target.files && e.target.files[0]) importJsonFile(e.target.files[0]);
  e.target.value = "";
}});

document.getElementById("mediaTodayBtn").addEventListener("click", () => {{
  const today = swedenTodayString();
  selectedCultures().forEach(c => c.last_media_change = today);
  renderAll();
  scheduleSave();
}});
document.getElementById("splitTodayBtn").addEventListener("click", () => {{
  const today = swedenTodayString();
  selectedCultures().forEach(c => c.last_split_check = today);
  renderAll();
  scheduleSave();
}});
document.getElementById("recordSplitBtn").addEventListener("click", () => {{
  const today = swedenTodayString();
  selectedCultures().forEach(c => {{
    c.current_pd = effectivePdToday(c);
    c.pd_date = today;
    c.plated_date = today;
    c.last_split_check = today;
  }});
  renderAll();
  scheduleSave();
}});
document.getElementById("infectionNowBtn").addEventListener("click", () => {{
  const now = swedenNowString();
  selectedCultures().forEach(c => {{
    c.infection_active = true;
    c.first_infection_datetime = now;
  }});
  renderAll();
  scheduleSave();
}});
document.getElementById("repairDatesBtn").addEventListener("click", repairMissingDates);

window.addEventListener("beforeunload", () => {{
  if (dirty) saveCultures(true);
}});

function updateSwedenClock() {{
  const formatter = new Intl.DateTimeFormat("sv-SE", {{
    timeZone: "Europe/Stockholm",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }});
  document.getElementById("swedenTime").textContent = formatter.format(new Date());
}}

setInterval(updateSwedenClock, 15000);
updateSwedenClock();
document.getElementById("addForm").appendChild(cultureForm(null, true));
loadCultures();
</script>
</body>
</html>
"""


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_css()

    apps_script_url = get_secret("APPS_SCRIPT_URL", "").strip()
    apps_script_token = get_secret("APPS_SCRIPT_TOKEN", "").strip()

    if not apps_script_url:
        st.error("Missing APPS_SCRIPT_URL in Streamlit secrets.")
        st.stop()

    if not apps_script_token:
        st.error("Missing APPS_SCRIPT_TOKEN in Streamlit secrets.")
        st.stop()

    components.html(
        app_html(apps_script_url, apps_script_token),
        height=1050,
        scrolling=True,
    )


if __name__ == "__main__":
    main()
