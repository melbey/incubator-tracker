#!/usr/bin/env python3
"""
Incubator Tracker - Streamlit + Google Apps Script backend

This app stores culture data in a Google Sheet through a Google Apps Script web app.
No service account JSON key is required.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st


APP_TITLE = "Incubator Tracker"
APP_VERSION = "online-apps-script-v1.3-sweden-time-import-fix"

DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M"
MEDIA_INTERVAL_DAYS = 2
SPLIT_CHECK_INTERVAL_DAYS = 2
INFECTION_T0_OFFSET_HOURS = 12
INFECTION_TARGET_HOURS = [72, 84, 96, 108, 120, 132, 144]

SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def sweden_now() -> datetime:
    """Current date/time in Sweden, independent of Streamlit server timezone."""
    return datetime.now(SWEDEN_TZ).replace(second=0, microsecond=0).replace(tzinfo=None)


def sweden_today() -> date:
    """Current date in Sweden, independent of Streamlit server timezone."""
    return sweden_now().date()


@dataclass
class Culture:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cell_line: str = ""
    plate_count: int = 1
    plated_date: str = ""
    revived_date: str = ""
    current_pd: float = 0.0
    pd_date: str = ""
    last_media_change: str = ""
    last_split_check: str = ""
    drug_name: str = ""
    drug_added_datetime: str = ""
    infection_active: bool = False
    first_infection_datetime: str = ""
    notes: str = ""

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Culture":
        """Load one culture from either the online format or the old local JSON format."""
        raw = dict(data or {})

        # Keep only known Culture fields. This lets old JSON contain extra metadata safely.
        defaults = asdict(Culture())
        for key in list(raw.keys()):
            if key not in defaults:
                raw.pop(key, None)

        defaults.update(raw)
        defaults["id"] = str(defaults.get("id") or str(uuid.uuid4()))

        try:
            defaults["plate_count"] = int(float(defaults.get("plate_count") or 0))
        except Exception:
            defaults["plate_count"] = 0

        try:
            defaults["current_pd"] = float(defaults.get("current_pd") or 0)
        except Exception:
            defaults["current_pd"] = 0.0

        active = defaults.get("infection_active")
        if isinstance(active, str):
            defaults["infection_active"] = active.strip().lower() in {"true", "1", "yes", "y", "on"}
        else:
            defaults["infection_active"] = bool(active)

        # Normalize blank/None date-like fields to empty strings.
        for key in [
            "cell_line",
            "plated_date",
            "revived_date",
            "pd_date",
            "last_media_change",
            "last_split_check",
            "drug_name",
            "drug_added_datetime",
            "first_infection_datetime",
            "notes",
        ]:
            defaults[key] = "" if defaults.get(key) is None else str(defaults.get(key))

        return Culture(**defaults)

    def date_value(self, attr: str) -> Optional[date]:
        value = str(getattr(self, attr) or "").strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, DATE_FMT).date()
        except ValueError:
            return None

    def datetime_value(self, attr: str) -> Optional[datetime]:
        value = str(getattr(self, attr) or "").strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, DATETIME_FMT)
        except ValueError:
            return None

    def plated(self) -> Optional[date]:
        return self.date_value("plated_date")

    def pd_record_date(self) -> Optional[date]:
        return self.date_value("pd_date")

    def last_media(self) -> Optional[date]:
        return self.date_value("last_media_change") or self.plated()

    def last_split(self) -> Optional[date]:
        return self.date_value("last_split_check") or self.plated()

    def drug_added(self) -> Optional[datetime]:
        return self.datetime_value("drug_added_datetime")

    def first_infection(self) -> Optional[datetime]:
        return self.datetime_value("first_infection_datetime")

    def next_media_due(self) -> Optional[date]:
        d = self.last_media()
        return d + timedelta(days=MEDIA_INTERVAL_DAYS) if d else None

    def next_split_due(self) -> Optional[date]:
        d = self.last_split()
        return d + timedelta(days=SPLIT_CHECK_INTERVAL_DAYS) if d else None

    def effective_pd_today(self) -> float:
        d = self.pd_record_date()
        if d is None:
            return self.current_pd
        return self.current_pd + max(0, (sweden_today() - d).days)

    def infection_timepoints(self) -> List[tuple[str, datetime]]:
        first = self.first_infection()
        if not first or not self.infection_active:
            return []
        t0 = first + timedelta(hours=INFECTION_T0_OFFSET_HOURS)
        rows = [("t=0", t0)]
        for h in INFECTION_TARGET_HOURS:
            rows.append((f"{h} h", t0 + timedelta(hours=h)))
        return rows


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def backend_url() -> str:
    return get_secret("APPS_SCRIPT_URL", "").strip()


def backend_token() -> str:
    return get_secret("APPS_SCRIPT_TOKEN", "").strip()


def api_call(action: str, cultures: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    url = backend_url()
    if not url:
        raise RuntimeError("Missing APPS_SCRIPT_URL in Streamlit secrets.")

    payload: Dict[str, Any] = {
        "action": action,
        "token": backend_token(),
    }
    if cultures is not None:
        payload["cultures"] = cultures

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Unknown backend error."))

    return data


@st.cache_data(ttl=10, show_spinner=False)
def load_cultures_cached() -> List[Dict[str, Any]]:
    return api_call("load").get("cultures", [])


def load_cultures() -> List[Culture]:
    return [Culture.from_dict(item) for item in load_cultures_cached()]


def save_cultures(cultures: List[Culture]) -> None:
    api_call("save", [asdict(c) for c in cultures])
    load_cultures_cached.clear()


def status_from_due(due: Optional[date]) -> str:
    if due is None:
        return "Not set"
    delta = (due - sweden_today()).days
    if delta < 0:
        return f"OVERDUE by {-delta} day(s)"
    if delta == 0:
        return "Due today"
    if delta == 1:
        return "Due tomorrow"
    return f"Due in {delta} days"


def action_status(last_done: Optional[date], due: Optional[date]) -> str:
    if last_done == sweden_today() and due is not None:
        delta = (due - sweden_today()).days
        if delta == 1:
            return "Done today; next tomorrow"
        return f"Done today; next in {delta} days"
    return status_from_due(due)


def human_duration_since(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    delta = sweden_now() - dt
    future = delta.total_seconds() < 0
    if future:
        delta = -delta

    minutes_total = int(delta.total_seconds() // 60)
    days, rem = divmod(minutes_total, 24 * 60)
    hours, minutes = divmod(rem, 60)

    if days:
        text = f"{days} d {hours} h" if hours else f"{days} d"
    elif hours:
        text = f"{hours} h {minutes} min" if minutes else f"{hours} h"
    else:
        text = f"{minutes} min"
    return f"in {text}" if future else text


def drug_status(c: Culture) -> str:
    if not c.drug_name.strip():
        return "None"
    added = c.drug_added()
    if not added:
        return c.drug_name.strip()
    return f"{c.drug_name.strip()} — {human_duration_since(added)}"


def culture_table(cultures: List[Culture]) -> pd.DataFrame:
    rows = []
    for c in sorted(cultures, key=lambda x: x.cell_line.lower()):
        rows.append({
            "Select": False,
            "id": c.id,
            "Cell line": c.cell_line,
            "Plates": c.plate_count,
            "PD today": round(c.effective_pd_today(), 1),
            "Media": action_status(c.last_media(), c.next_media_due()),
            "Split": action_status(c.last_split(), c.next_split_due()),
            "Drug exposure": drug_status(c),
            "Infection": "Yes" if c.infection_active else "No",
        })
    return pd.DataFrame(rows)


def selected_cultures_from_editor(df: pd.DataFrame, cultures: List[Culture]) -> List[Culture]:
    if df.empty or "Select" not in df.columns:
        return []
    selected_ids = set(df.loc[df["Select"] == True, "id"].astype(str).tolist())
    return [c for c in cultures if c.id in selected_ids]


def upsert_culture(cultures: List[Culture], culture: Culture) -> List[Culture]:
    for i, existing in enumerate(cultures):
        if existing.id == culture.id:
            cultures[i] = culture
            return cultures
    cultures.append(culture)
    return cultures


def date_input_or_blank(label: str, value: str, key: str) -> str:
    return st.text_input(label, value=value or "", key=key, placeholder="YYYY-MM-DD")


def datetime_input_or_blank(label: str, value: str, key: str) -> str:
    return st.text_input(label, value=value or "", key=key, placeholder="YYYY-MM-DD HH:MM")


def validate_date(value: str, label: str, required: bool = False) -> str:
    value = value.strip()
    if not value:
        if required:
            raise ValueError(f"{label} is required.")
        return ""
    datetime.strptime(value, DATE_FMT)
    return value


def validate_datetime(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        return ""
    datetime.strptime(value, DATETIME_FMT)
    return value


def render_form(cultures: List[Culture], editing: Optional[Culture] = None, form_key: str = "form") -> None:
    c = editing or Culture(pd_date=sweden_today().strftime(DATE_FMT))
    title = "Edit culture" if editing else "Add culture"
    key_prefix = f"{form_key}_{c.id}"
    with st.form(f"{title}_{key_prefix}"):
        st.subheader(title)
        cell_line = st.text_input("Cell line", c.cell_line, key=f"{key_prefix}_cell_line")
        plate_count = st.number_input("Number of plates", min_value=0, value=int(c.plate_count), step=1, key=f"{key_prefix}_plate_count")
        plated_date = date_input_or_blank("Date plated", c.plated_date, f"{key_prefix}_plated_date")
        revived_date = date_input_or_blank("Date revived", c.revived_date, f"{key_prefix}_revived_date")
        current_pd = st.number_input("Current PD", value=float(c.current_pd), step=0.5, key=f"{key_prefix}_current_pd")
        pd_date = date_input_or_blank("PD date", c.pd_date, f"{key_prefix}_pd_date")
        last_media = date_input_or_blank("Last media change", c.last_media_change, f"{key_prefix}_last_media")
        last_split = date_input_or_blank("Last split check", c.last_split_check, f"{key_prefix}_last_split")
        drug_name = st.text_input("Drug name", c.drug_name, key=f"{key_prefix}_drug_name")
        drug_added = datetime_input_or_blank("Drug added", c.drug_added_datetime, f"{key_prefix}_drug_added")
        infection_active = st.checkbox("Infection active", value=bool(c.infection_active), key=f"{key_prefix}_infection_active")
        first_infection = datetime_input_or_blank("1st infection", c.first_infection_datetime, f"{key_prefix}_first_infection")
        notes = st.text_area("Notes", c.notes, key=f"{key_prefix}_notes")
        submitted = st.form_submit_button("Save")

    if submitted:
        try:
            if not cell_line.strip():
                raise ValueError("Cell line is required.")
            c.cell_line = cell_line.strip()
            c.plate_count = int(plate_count)
            c.plated_date = validate_date(plated_date, "Date plated")
            c.revived_date = validate_date(revived_date, "Date revived")
            c.current_pd = float(current_pd)
            c.pd_date = validate_date(pd_date, "PD date")
            c.last_media_change = validate_date(last_media, "Last media change")
            c.last_split_check = validate_date(last_split, "Last split check")
            c.drug_name = drug_name.strip()
            c.drug_added_datetime = validate_datetime(drug_added, "Drug added")
            c.infection_active = bool(infection_active)
            c.first_infection_datetime = validate_datetime(first_infection, "1st infection")
            c.notes = notes.strip()

            save_cultures(upsert_culture(cultures, c))
            st.success("Saved.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def render_alerts(cultures: List[Culture]) -> None:
    alerts = []
    for c in cultures:
        media_due = c.next_media_due()
        split_due = c.next_split_due()
        if media_due and media_due <= sweden_today():
            alerts.append(f"{c.cell_line}: media change {status_from_due(media_due).lower()}.")
        if split_due and split_due <= sweden_today():
            alerts.append(f"{c.cell_line}: split check {status_from_due(split_due).lower()}.")
        if c.infection_active:
            now = sweden_now()
            for label, dt in c.infection_timepoints():
                if dt.date() == sweden_today() and dt >= now:
                    alerts.append(f"{c.cell_line}: infection {label} today at {dt.strftime('%H:%M')}.")
    if not alerts:
        st.info("No due or overdue tasks today.")
    else:
        for alert in alerts:
            st.warning(alert)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption(f"{APP_VERSION} · Sweden time: {sweden_now().strftime(DATETIME_FMT)}")

    try:
        cultures = load_cultures()
    except Exception as exc:
        st.error(f"Could not load data from Google Sheets backend: {exc}")
        st.stop()

    tab_dashboard, tab_add, tab_edit, tab_infection, tab_raw = st.tabs(
        ["Dashboard", "Add culture", "Edit selected", "Infection timepoints", "Raw data"]
    )

    with tab_dashboard:
        st.header("Due / overdue today")
        render_alerts(cultures)

        st.header("Cultures / Plates")
        df = culture_table(cultures)
        edited = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            disabled=[col for col in df.columns if col != "Select"],
            column_config={"id": None, "Select": st.column_config.CheckboxColumn("Select")},
            key="culture_selector",
        )

        selected = selected_cultures_from_editor(edited, cultures)
        st.write(f"Selected: {len(selected)}")

        col1, col2, col3, col4, col5 = st.columns(5)
        today_str = sweden_today().strftime(DATE_FMT)
        now_str = sweden_now().strftime(DATETIME_FMT)

        if col1.button("Media changed today", disabled=not selected):
            for c in selected:
                c.last_media_change = today_str
            save_cultures(cultures)
            st.rerun()

        if col2.button("Split checked today", disabled=not selected):
            for c in selected:
                c.last_split_check = today_str
            save_cultures(cultures)
            st.rerun()

        if col3.button("Record split today", disabled=not selected):
            for c in selected:
                c.current_pd = c.effective_pd_today()
                c.pd_date = today_str
                c.plated_date = today_str
                c.last_split_check = today_str
            save_cultures(cultures)
            st.rerun()

        if col4.button("1st infection now", disabled=not selected):
            for c in selected:
                c.infection_active = True
                c.first_infection_datetime = now_str
            save_cultures(cultures)
            st.rerun()

        if col5.button("Refresh"):
            load_cultures_cached.clear()
            st.rerun()

        if selected:
            st.subheader("Selected details")
            for c in selected:
                with st.expander(c.cell_line):
                    st.json(asdict(c))

    with tab_add:
        render_form(cultures, form_key="add")

    with tab_edit:
        df = culture_table(cultures)
        choices = {f"{c.cell_line} ({c.id[:8]})": c for c in sorted(cultures, key=lambda x: x.cell_line.lower())}
        if not choices:
            st.info("No cultures yet.")
        else:
            label = st.selectbox("Choose culture to edit", list(choices.keys()))
            c = choices[label]
            render_form(cultures, c, form_key="edit")

            col_dup, col_delete = st.columns(2)
            if col_dup.button("Duplicate this culture"):
                copied = Culture.from_dict(asdict(c))
                copied.id = str(uuid.uuid4())
                copied.cell_line = copied.cell_line + " copy"
                save_cultures(upsert_culture(cultures, copied))
                st.rerun()

            if col_delete.button("Delete this culture", type="secondary"):
                save_cultures([x for x in cultures if x.id != c.id])
                st.rerun()

    with tab_infection:
        rows = []
        for c in cultures:
            for label, dt in c.infection_timepoints():
                rows.append({
                    "Cell line": c.cell_line,
                    "Timepoint": label,
                    "Date/time": dt.strftime(DATETIME_FMT),
                    "Status": "past" if dt < sweden_now() else "upcoming",
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No active infection timepoints.")

    with tab_raw:
        st.download_button(
            "Download JSON backup",
            data=json.dumps([asdict(c) for c in cultures], indent=2),
            file_name="incubator_tracker_backup.json",
            mime="application/json",
        )

        uploaded = st.file_uploader("Import JSON backup", type=["json"])
        if uploaded is not None:
            try:
                data = json.loads(uploaded.read().decode("utf-8"))

                # Accept both backup formats:
                # 1) New online format: [ {culture}, {culture}, ... ]
                # 2) Old local app format: {"version": 2, "cultures": [ ... ]}
                if isinstance(data, dict):
                    if isinstance(data.get("cultures"), list):
                        data = data["cultures"]
                    else:
                        raise ValueError("This JSON object does not contain a 'cultures' list.")
                elif not isinstance(data, list):
                    raise ValueError("The JSON file must contain either a list of cultures or an object with a 'cultures' list.")

                imported = [Culture.from_dict(item) for item in data]
                st.success(f"Ready to import {len(imported)} culture record(s). Due dates will be calculated using Sweden time.")

                if st.button("Replace Google Sheet data with uploaded JSON"):
                    save_cultures(imported)
                    st.success("Imported into Google Sheet.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not import JSON: {exc}")

        st.dataframe(pd.DataFrame([asdict(c) for c in cultures]), use_container_width=True)


if __name__ == "__main__":
    main()
