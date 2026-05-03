from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
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


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/live")
def live_data():
    try:
        session = get_session(2026, "Miami", "R")

        # ONLY load laps (lightweight)
        session.load(laps=True, telemetry=False, weather=False, messages=False)

        leclerc_laps = session.laps.pick_driver("16")

        if leclerc_laps.empty:
            return {"status": "no-data"}

        latest_lap = leclerc_laps[leclerc_laps["LapTime"].notna()].iloc[-1]

        return {
            "status": "replay",
            "driver": "Charles Leclerc",
            "lap": int(latest_lap["LapNumber"]),
            "lap_time": str(latest_lap["LapTime"]),
            "sector1": str(latest_lap["Sector1Time"]),
            "sector2": str(latest_lap["Sector2Time"]),
            "sector3": str(latest_lap["Sector3Time"]),
        }

    except Exception as e:
        return {"error": str(e)}
