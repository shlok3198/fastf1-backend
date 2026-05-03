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
    """
    Returns latest available Leclerc telemetry for the Miami race.

    During/after a session this behaves as replay/latest data:
    - status = live-ish/latest when timing is available
    - status = no-data when Leclerc data is not available yet
    """
    try:
        session = get_session(2026, "Miami", "R")
        session.load(laps=True, telemetry=True, weather=False, messages=False)

        leclerc_laps = session.laps.pick_driver("16")

        if leclerc_laps is None or leclerc_laps.empty:
            return {
                "status": "no-data",
                "message": "No Leclerc laps available yet."
            }

        # Prefer the latest completed lap. Fall back to fastest if needed.
        completed = leclerc_laps[leclerc_laps["LapTime"].notna()]
        if completed.empty:
            lap = leclerc_laps.pick_fastest()
        else:
            lap = completed.sort_values("LapNumber").iloc[-1]

        telemetry = lap.get_car_data().add_distance()

        if telemetry is None or telemetry.empty:
            return {
                "status": "no-telemetry",
                "driver": "Charles Leclerc",
                "driver_number": "16",
                "lap": int(lap["LapNumber"]) if "LapNumber" in lap else None,
                "message": "Lap exists, but telemetry is not available."
            }

        latest = telemetry.iloc[-1]

        return {
            "status": "replay",
            "session": "Miami Grand Prix",
            "driver": "Charles Leclerc",
            "driver_number": "16",
            "lap": int(lap["LapNumber"]),
            "speed": float(latest.get("Speed", 0)),
            "throttle": float(latest.get("Throttle", 0)),
            "brake": bool(latest.get("Brake", False)),
            "gear": int(latest.get("nGear", 0)),
            "distance": float(latest.get("Distance", 0)),
            "source": "FastF1 latest available telemetry"
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
