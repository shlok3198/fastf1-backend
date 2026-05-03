from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import re
import pandas as pd
import fastf1
from fastf1 import get_session
from fastf1.events import get_event_schedule

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("./cache", exist_ok=True)
fastf1.Cache.enable_cache("./cache")


def clean(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def safe_int(value):
    value = clean(value)
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def safe_str(value):
    value = clean(value)
    if value is None:
        return None
    return str(value)


def format_td(value):
    value = clean(value)
    if value is None:
        return None

    # pandas / datetime timedelta
    try:
        total_seconds = value.total_seconds()
    except Exception:
        text = str(value)

        # FastF1/pandas can serialize Timedelta as ISO duration: P0DT0H1M49.834S
        iso = re.match(r"^P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?([\d.]+)S$", text)
        if iso:
            hours = int(iso.group(1) or 0)
            minutes = int(iso.group(2) or 0)
            seconds_float = float(iso.group(3) or 0)
            total_seconds = hours * 3600 + minutes * 60 + seconds_float
        else:
            if text.startswith("0 days "):
                text = text.replace("0 days ", "")
            return text

    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    ms = int(round((total_seconds - int(total_seconds)) * 1000))

    if ms == 1000:
        seconds += 1
        ms = 0

    if minutes > 0:
        return f"{minutes}:{seconds:02d}.{ms:03d}"
    return f"{seconds}.{ms:03d}"


def pick_tyres(leclerc_laps, lap):
    compound = clean(lap.get("Compound"))
    tyre_life = safe_int(lap.get("TyreLife"))
    stint = safe_int(lap.get("Stint"))
    fresh_tyre = clean(lap.get("FreshTyre"))

    if compound is None or tyre_life is None or stint is None:
        history = leclerc_laps[leclerc_laps["LapNumber"].notna()].sort_values("LapNumber", ascending=False)
        for _, row in history.iterrows():
            if compound is None:
                compound = clean(row.get("Compound"))
            if tyre_life is None:
                tyre_life = safe_int(row.get("TyreLife"))
            if stint is None:
                stint = safe_int(row.get("Stint"))
            if fresh_tyre is None:
                fresh_tyre = clean(row.get("FreshTyre"))
            if compound is not None and tyre_life is not None and stint is not None:
                break

    return compound, tyre_life, stint, fresh_tyre


def miami_is_complete():
    try:
        session = get_session(2026, "Miami", "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps.pick_driver("16")
        if laps is None or laps.empty:
            return False
        completed = laps[laps["LapTime"].notna()]
        if completed.empty:
            return False
        return int(completed["LapNumber"].max()) >= 50
    except Exception:
        return False


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/next")
def next_session():
    try:
        schedule = get_event_schedule(2026, include_testing=False)
        now_utc = pd.Timestamp.utcnow()

        schedule = schedule.copy()
        schedule["EventDateUtc"] = pd.to_datetime(schedule["EventDate"], utc=True, errors="coerce")

        if miami_is_complete():
            miami_rows = schedule[schedule["EventName"].astype(str).str.contains("Miami", case=False, na=False)]
            if not miami_rows.empty:
                miami_idx = miami_rows.index[0]
                upcoming = schedule.loc[schedule.index > miami_idx].copy()
            else:
                upcoming = schedule[schedule["EventDateUtc"] > now_utc].copy()
        else:
            upcoming = schedule[schedule["EventDateUtc"] > now_utc].copy()

        upcoming = upcoming[upcoming["EventDateUtc"].notna()].sort_values("EventDateUtc")

        if upcoming.empty:
            return {"status": "no-upcoming"}

        event = upcoming.iloc[0]
        event_time = event["EventDateUtc"]
        event_name = safe_str(event.get("EventName")) or "Next Grand Prix"
        location = safe_str(event.get("Location")) or safe_str(event.get("Country")) or "Track"

        return {
            "raceName": event_name,
            "eventName": event_name,
            "circuitName": location,
            "iso": event_time.isoformat(),
            "dateText": event_time.strftime("%b %-d · %-I:%M %p UTC"),
            "source": "FastF1 event schedule"
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/live")
def live_data():
    try:
        session = get_session(2026, "Miami", "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)

        leclerc_laps = session.laps.pick_driver("16")

        if leclerc_laps is None or leclerc_laps.empty:
            return {"status": "no-data", "message": "No Leclerc laps available yet."}

        completed = leclerc_laps[leclerc_laps["LapTime"].notna()]
        if completed.empty:
            lap = leclerc_laps.sort_values("LapNumber").iloc[-1]
        else:
            lap = completed.sort_values("LapNumber").iloc[-1]

        compound, tyre_life, stint, fresh_tyre = pick_tyres(leclerc_laps, lap)

        return {
            "status": "replay",
            "session": "Miami Grand Prix",
            "driver": "Charles Leclerc",
            "driver_number": "16",
            "lap": safe_int(lap.get("LapNumber")),
            "lap_time": format_td(lap.get("LapTime")),
            "sector1": format_td(lap.get("Sector1Time")),
            "sector2": format_td(lap.get("Sector2Time")),
            "sector3": format_td(lap.get("Sector3Time")),
            "compound": safe_str(compound),
            "tyre": safe_str(compound),
            "tyre_life": tyre_life,
            "stint": stint,
            "fresh_tyre": bool(fresh_tyre) if fresh_tyre is not None else None,
            "source": "FastF1 latest available lap + tyre data"
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}
