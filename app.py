from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import pandas as pd
import fastf1
from fastf1 import get_session

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


@app.get("/health")
def health():
    return {"ok": True}


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
            lap = leclerc_laps.iloc[-1]
        else:
            lap = completed.sort_values("LapNumber").iloc[-1]

        compound = clean(lap.get("Compound"))
        tyre_life = clean(lap.get("TyreLife"))
        stint = clean(lap.get("Stint"))
        fresh_tyre = clean(lap.get("FreshTyre"))

        return {
            "status": "replay",
            "session": "Miami Grand Prix",
            "driver": "Charles Leclerc",
            "driver_number": "16",
            "lap": int(lap["LapNumber"]) if clean(lap.get("LapNumber")) is not None else None,
            "lap_time": str(clean(lap.get("LapTime"))) if clean(lap.get("LapTime")) is not None else None,
            "sector1": str(clean(lap.get("Sector1Time"))) if clean(lap.get("Sector1Time")) is not None else None,
            "sector2": str(clean(lap.get("Sector2Time"))) if clean(lap.get("Sector2Time")) is not None else None,
            "sector3": str(clean(lap.get("Sector3Time"))) if clean(lap.get("Sector3Time")) is not None else None,
            "compound": compound,
            "tyre": compound,
            "tyre_life": int(tyre_life) if tyre_life is not None else None,
            "stint": int(stint) if stint is not None else None,
            "fresh_tyre": bool(fresh_tyre) if fresh_tyre is not None else None,
            "source": "FastF1 latest available lap + tyre data"
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
