from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import datetime as dt
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
    if hasattr(value, "isoformat"):
        return value.isoformat()
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


def pick_tyres(leclerc_laps, lap):
    compound = clean(lap.get("Compound"))
    tyre_life = safe_int(lap.get("TyreLife"))
    stint = safe_int(lap.get("Stint"))
    fresh_tyre = clean(lap.get("FreshTyre"))

    # FastF1 sometimes has blanks on the final classified lap. Search backwards.
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


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/next")
def next_session():
    try:
        schedule = get_event_schedule(2026, include_testing=False)
        now_utc = pd.Timestamp.utcnow()

        # Prefer the next event whose race date is still in the future.
        upcoming = schedule[schedule["EventDate"].notna()].copy()
        upcoming["EventDateUtc"] = pd.to_datetime(upcoming["EventDate"], utc=True, errors="coerce")
        upcoming = upcoming[upcoming["EventDateUtc"] > now_utc].sort_values("EventDateUtc")

        if upcoming.empty:
            return {"status": "no-upcoming"}

        event = upcoming.iloc[0]
        event_time = event["EventDateUtc"]

        location = safe_str(event.get("Location")) or safe_str(event.get("Country")) or "Track"
        event_name = safe_str(event.get("EventName")) or "Next Grand Prix"

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

        # Lightweight: load lap timing only. Full car telemetry can crash free Render.
        session.load(laps=True, telemetry=False, weather=False, messages=False)

        leclerc_laps = session.laps.pick_driver("16")

        if leclerc_laps is None or leclerc_laps.empty:
            return {
                "status": "no-data",
                "message": "No Leclerc laps available yet."
            }

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
            "lap_time": safe_str(lap.get("LapTime")),
            "sector1": safe_str(lap.get("Sector1Time")),
            "sector2": safe_str(lap.get("Sector2Time")),
            "sector3": safe_str(lap.get("Sector3Time")),
            "compound": compound,
            "tyre": compound,
            "tyre_life": tyre_life,
            "stint": stint,
            "fresh_tyre": bool(fresh_tyre) if fresh_tyre is not None else None,
            "source": "FastF1 latest available lap + tyre data"
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
