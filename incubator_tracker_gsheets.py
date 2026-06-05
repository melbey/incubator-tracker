from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

APP_TITLE = "Incubator Tracker"
APP_VERSION = "google-sheets-v1"
DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M"
MEDIA_INTERVAL_DAYS = 2
SPLIT_CHECK_INTERVAL_DAYS = 2
INFECTION_T0_OFFSET_HOURS = 12
INFECTION_TARGET_HOURS = [72, 84, 96, 108, 120, 132, 144]
SHEET_COLUMNS = [
    "id", "cell_line", "plate_count", "plated_date", "revived_date", "current_pd", "pd_date",
    "last_media_change", "last_split_check", "drug_name", "drug_added_datetime", "infection_active",
    "first_infection_datetime", "notes", "updated_at",
]


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
    updated_at: str = ""

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Culture":
        d = asdict(Culture())
        d.update({k: v for k, v in data.items() if k in d})
        try:
            d["plate_count"] = int(float(d.get("plate_count") or 0))
        except Exception:
            d["plate_count"] = 0
        try:
            d["current_pd"] = float(d.get("current_pd") or 0)
        except Exception:
            d["current_pd"] = 0.0
        val = d.get("infection_active")
        if isinstance(val, str):
            d["infection_active"] = val.strip().lower() in {"true", "1", "yes", "y", "on"}
        else:
            d["infection_active"] = bool(val)
        return Culture(**d)

    def _date(self, value: str) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.strptime(str(value), DATE_FMT).date()
        except Exception:
            return None

    def _datetime(self, value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.strptime(str(value), DATETIME_FMT)
        except Exception:
            return None

    def plated(self) -> Optional[date]: return self._date(self.plated_date)
    def pd_record_date(self) -> Optional[date]: return self._date(self.pd_date)
    def last_media(self) -> Optional[date]: return self._date(self.last_media_change) or self.plated()
    def last_split(self) -> Optional[date]: return self._date(self.last_split_check) or self.plated()
    def drug_added(self) -> Optional[datetime]: return self._datetime(self.drug_added_datetime)
    def first_infection(self) -> Optional[datetime]: return self._datetime(self.first_infection_datetime)

    def next_media_due(self) -> Optional[date]:
        d = self.last_media()
        return d + timedelta(days=MEDIA_INTERVAL_DAYS) if d else None

    def next_split_check_due(self) -> Optional[date]:
        d = self.last_split()
        return d + timedelta(days=SPLIT_CHECK_INTERVAL_DAYS) if d else None

    def effective_pd_today(self) -> float:
        pd_day = self.pd_record_date()
        if pd_day is None:
            return self.current_pd
        return self.current_pd + max(0, (date.today() - pd_day).days)

    def infection_timepoints(self) -> List[tuple[str, datetime]]:
        first = self.first_infection()
        if not first or not self.infection_active:
            return []
        t0 = first + timedelta(hours=INFECTION_T0_OFFSET_HOURS)
        rows = [("t=0", t0)]
        rows.extend((f"{h} h", t0 + timedelta(hours=h)) for h in INFECTION_TARGET_HOURS)
        return rows


def now_str() -> str:
    return datetime.now().strftime(DATETIME_FMT)


def date_to_str(d: Optional[date]) -> str:
    return d.strftime(DATE_FMT) if d else ""


def datetime_to_str(dt: Optional[datetime]) -> str:
    return dt.strftime(DATETIME_FMT) if dt else ""


def parse_date(value: str, field: str, required: bool = False) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        if required: raise ValueError(f"{field} is required.")
        return None
    try:
        return datetime.strptime(value, DATE_FMT).date()
    except ValueError:
        raise ValueError(f"{field} must be YYYY-MM-DD.")


def parse_datetime(value: str, field: str, required: bool = False) -> Optional[datetime]:
    value = (value or "").strip()
    if not value:
        if required: raise ValueError(f"{field} is required.")
        return None
    try:
        return datetime.strptime(value, DATETIME_FMT)
    except ValueError:
        raise ValueError(f"{field} must be YYYY-MM-DD HH:MM.")


def status_from_due(due: Optional[date]) -> str:
    if not due: return "Not set"
    delta = (due - date.today()).days
    if delta < 0: return f"OVERDUE by {-delta} day(s)"
    if delta == 0: return "Due today"
    if delta == 1: return "Due tomorrow"
    return f"Due in {delta} days"


def action_status(last_done: Optional[date], due_date: Optional[date]) -> str:
    if last_done == date.today() and due_date:
        delta = (due_date - date.today()).days
        if delta == 1: return "Done today; next tomorrow"
        return f"Done today; next in {delta} days"
    return status_from_due(due_date)


def human_duration_since(dt: Optional[datetime]) -> str:
    if not dt: return ""
    delta = datetime.now().replace(second=0, microsecond=0) - dt
    future = delta.total_seconds() < 0
    if future: delta = -delta
    minutes = int(delta.total_seconds() // 60)
    days, rem = divmod(minutes, 24 * 60)
    hours, mins = divmod(rem, 60)
    if days: text = f"{days} d {hours} h" if hours else f"{days} d"
    elif hours: text = f"{hours} h {mins} min" if mins else f"{hours} h"
    else: text = f"{mins} min"
    return f"in {text}" if future else text


def drug_status(c: Culture) -> str:
    if not c.drug_name.strip(): return "None"
    added = c.drug_added()
    return f"{c.drug_name.strip()} — {human_duration_since(added)}" if added else c.drug_name.strip()


@st.cache_resource(show_spinner=False)
def get_worksheet():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Missing [gcp_service_account] in Streamlit secrets.")
    if "sheet_id" not in st.secrets:
        raise RuntimeError("Missing sheet_id in Streamlit secrets.")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(st.secrets["sheet_id"])
    worksheet_name = st.secrets.get("worksheet_name", "cultures")
    try:
        ws = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(SHEET_COLUMNS))
        ws.append_row(SHEET_COLUMNS)
    ensure_header(ws)
    return ws


def ensure_header(ws):
    vals = ws.row_values(1)
    if vals != SHEET_COLUMNS:
        ws.resize(rows=max(ws.row_count, 1000), cols=len(SHEET_COLUMNS))
        ws.update("A1", [SHEET_COLUMNS])


def load_cultures() -> List[Culture]:
    ws = get_worksheet()
    records = ws.get_all_records(default_blank="")
    return [Culture.from_dict(r) for r in records if str(r.get("id", "")).strip()]


def save_cultures(cultures: List[Culture]) -> None:
    ws = get_worksheet()
    rows = []
    for c in cultures:
        data = asdict(c)
        data["infection_active"] = "TRUE" if c.infection_active else "FALSE"
        rows.append([data.get(col, "") for col in SHEET_COLUMNS])
    ws.clear()
    ws.update("A1", [SHEET_COLUMNS] + rows, value_input_option="USER_ENTERED")


def upsert_culture(culture: Culture):
    cultures = load_cultures()
    culture.updated_at = now_str()
    for i, c in enumerate(cultures):
        if c.id == culture.id:
            cultures[i] = culture
            save_cultures(cultures)
            return
    cultures.append(culture)
    save_cultures(cultures)


def delete_cultures(ids: List[str]):
    cultures = [c for c in load_cultures() if c.id not in set(ids)]
    save_cultures(cultures)


def table_rows(cultures: List[Culture]) -> pd.DataFrame:
    rows = []
    for c in sorted(cultures, key=lambda x: x.cell_line.lower()):
        media = action_status(c.last_media(), c.next_media_due())
        split = action_status(c.last_split(), c.next_split_check_due())
        rows.append({
            "select": False,
            "id": c.id,
            "Cell line": c.cell_line,
            "Plates": c.plate_count,
            "PD": round(c.effective_pd_today(), 1),
            "Media": media,
            "Split": split,
            "Drug exposure": drug_status(c),
            "Inf.": "Yes" if c.infection_active else "No",
            "Notes": c.notes,
        })
    return pd.DataFrame(rows)


def selected_ids_from_editor(df: pd.DataFrame) -> List[str]:
    if df is None or df.empty or "select" not in df.columns:
        return []
    return df[df["select"] == True]["id"].astype(str).tolist()


def culture_form(culture: Optional[Culture] = None, duplicate: bool = False):
    c = culture or Culture(pd_date=date_to_str(date.today()))
    if duplicate:
        c = Culture.from_dict(asdict(c))
        c.id = str(uuid.uuid4())
        c.cell_line = f"{c.cell_line} copy" if c.cell_line else ""

    with st.form("culture_form", clear_on_submit=False):
        st.subheader("Edit culture" if culture and not duplicate else "Add culture")
        cell_line = st.text_input("Cell line", value=c.cell_line)
        col1, col2, col3 = st.columns(3)
        plate_count = col1.number_input("Number of plates", min_value=0, step=1, value=int(c.plate_count))
        current_pd = col2.number_input("Current PD", value=float(c.current_pd), step=0.1)
        pd_date = col3.text_input("PD date", value=c.pd_date, placeholder="YYYY-MM-DD")

        col1, col2 = st.columns(2)
        plated_date = col1.text_input("Date plated", value=c.plated_date, placeholder="YYYY-MM-DD")
        revived_date = col2.text_input("Date revived", value=c.revived_date, placeholder="YYYY-MM-DD")
        col1, col2 = st.columns(2)
        last_media = col1.text_input("Last media change", value=c.last_media_change, placeholder="YYYY-MM-DD")
        last_split = col2.text_input("Last split check", value=c.last_split_check, placeholder="YYYY-MM-DD")

        col1, col2 = st.columns(2)
        drug_name = col1.text_input("Drug name", value=c.drug_name)
        drug_added = col2.text_input("Drug added", value=c.drug_added_datetime, placeholder="YYYY-MM-DD HH:MM")

        infection_active = st.checkbox("Infection active / calculate infection timepoints", value=bool(c.infection_active))
        first_infection = st.text_input("1st infection", value=c.first_infection_datetime, placeholder="YYYY-MM-DD HH:MM")
        notes = st.text_area("Notes", value=c.notes, height=100)

        submitted = st.form_submit_button("Save culture", type="primary")
        if submitted:
            try:
                if not cell_line.strip(): raise ValueError("Cell line is required.")
                new = Culture(
                    id=c.id,
                    cell_line=cell_line.strip(),
                    plate_count=int(plate_count),
                    plated_date=date_to_str(parse_date(plated_date, "Date plated")),
                    revived_date=date_to_str(parse_date(revived_date, "Date revived")),
                    current_pd=float(current_pd),
                    pd_date=date_to_str(parse_date(pd_date, "PD date")),
                    last_media_change=date_to_str(parse_date(last_media, "Last media change")),
                    last_split_check=date_to_str(parse_date(last_split, "Last split check")),
                    drug_name=drug_name.strip(),
                    drug_added_datetime=datetime_to_str(parse_datetime(drug_added, "Drug added")),
                    infection_active=bool(infection_active),
                    first_infection_datetime=datetime_to_str(parse_datetime(first_infection, "1st infection")),
                    notes=notes.strip(),
                    updated_at=now_str(),
                )
                upsert_culture(new)
                st.success("Saved.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(str(e))


def import_json_widget():
    st.subheader("Import from old JSON")
    uploaded = st.file_uploader("Upload incubator_tracker_data.json", type=["json"])
    if uploaded and st.button("Import JSON into Google Sheet"):
        try:
            raw = json.load(uploaded)
            items = raw.get("cultures", raw if isinstance(raw, list) else [])
            cultures = load_cultures()
            existing = {c.id for c in cultures}
            added = 0
            for item in items:
                c = Culture.from_dict(item)
                if not c.id or c.id in existing:
                    c.id = str(uuid.uuid4())
                c.updated_at = now_str()
                cultures.append(c)
                existing.add(c.id)
                added += 1
            save_cultures(cultures)
            st.success(f"Imported {added} culture(s).")
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption(f"{APP_VERSION} · data saved to Google Sheets")

    with st.sidebar:
        st.header("Google Sheets")
        st.write("This app reads/writes your culture data from the Google Sheet configured in Streamlit secrets.")
        if st.button("Reload from Google Sheet"):
            st.cache_resource.clear()
            st.rerun()
        with st.expander("Migration tools"):
            import_json_widget()

    try:
        cultures = load_cultures()
    except Exception as e:
        st.error("Could not connect to Google Sheets.")
        st.exception(e)
        st.info("Check README.md: add Streamlit secrets, enable Sheets API, and share the sheet with your service-account email.")
        return

    df = table_rows(cultures)
    st.subheader("Cultures / Plates")
    edited = st.data_editor(
        df,
        hide_index=True,
        disabled=[c for c in df.columns if c != "select"] if not df.empty else None,
        column_config={
            "select": st.column_config.CheckboxColumn("Select"),
            "id": None,
            "Notes": st.column_config.TextColumn("Notes", width="medium"),
        },
        use_container_width=True,
        key="culture_table",
    ) if not df.empty else pd.DataFrame(columns=["select", "id"])

    selected_ids = selected_ids_from_editor(edited)
    selected = [c for c in cultures if c.id in selected_ids]
    st.caption(f"Selected: {len(selected_ids)}")

    col1, col2, col3, col4 = st.columns(4)
    if col1.button("Media changed today", disabled=not selected_ids):
        for c in selected: c.last_media_change = date_to_str(date.today()); c.updated_at = now_str()
        save_cultures(cultures); st.rerun()
    if col2.button("Split checked today", disabled=not selected_ids):
        for c in selected: c.last_split_check = date_to_str(date.today()); c.updated_at = now_str()
        save_cultures(cultures); st.rerun()
    if col3.button("Record split today", disabled=not selected_ids):
        for c in selected:
            c.current_pd = c.effective_pd_today(); c.pd_date = date_to_str(date.today()); c.plated_date = date_to_str(date.today()); c.last_split_check = date_to_str(date.today()); c.updated_at = now_str()
        save_cultures(cultures); st.rerun()
    if col4.button("1st infection now", disabled=not selected_ids):
        for c in selected: c.infection_active = True; c.first_infection_datetime = now_str(); c.updated_at = now_str()
        save_cultures(cultures); st.rerun()

    tab_add, tab_edit, tab_alerts, tab_infection, tab_manage = st.tabs(["Add", "Edit/Duplicate", "Due today", "Infection schedule", "Manage"])
    with tab_add:
        culture_form(None)
    with tab_edit:
        if len(selected) == 1:
            culture_form(selected[0])
            if st.button("Duplicate selected culture"):
                c = Culture.from_dict(asdict(selected[0])); c.id = str(uuid.uuid4()); c.cell_line += " copy"; c.updated_at = now_str(); upsert_culture(c); st.rerun()
        elif len(selected) > 1:
            st.info("Select only one culture to edit or duplicate.")
        else:
            st.info("Select one culture in the table first.")
    with tab_alerts:
        alerts = []
        for c in cultures:
            md = c.next_media_due(); sd = c.next_split_check_due()
            if md and md <= date.today(): alerts.append(f"• {c.cell_line}: media change {status_from_due(md).lower()}.")
            if sd and sd <= date.today(): alerts.append(f"• {c.cell_line}: split check {status_from_due(sd).lower()}.")
            if c.infection_active:
                for label, dt in c.infection_timepoints():
                    if dt.date() == date.today() and dt >= datetime.now():
                        alerts.append(f"• {c.cell_line}: infection {label} today at {dt.strftime('%H:%M')}.")
        st.write("\n".join(alerts) if alerts else "No due or overdue tasks today.")
    with tab_infection:
        rows = []
        for c in cultures:
            for label, dt in c.infection_timepoints():
                rows.append({"Cell line": c.cell_line, "Timepoint": label, "Date/time": dt.strftime(DATETIME_FMT), "When": human_duration_since(dt)})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with tab_manage:
        if selected_ids and st.button("Delete selected culture(s)", type="secondary"):
            delete_cultures(selected_ids); st.rerun()
        st.download_button(
            "Download backup JSON",
            data=json.dumps({"version": 2, "saved_at": now_str(), "cultures": [asdict(c) for c in cultures]}, indent=2),
            file_name="incubator_tracker_backup.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
