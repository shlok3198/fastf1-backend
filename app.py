from fastapi import FastAPI
import os
import fastf1
from fastf1 import get_session

app = FastAPI()

os.makedirs("./cache", exist_ok=True)
fastf1.Cache.enable_cache("./cache")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/live")
def live_data():
    try:
        session = get_session(2026, 'Miami', 'R')
        session.load()

        driver = session.laps.pick_driver('16').pick_fastest()

        if driver is None:
            return {"status": "no-data"}

        telemetry = driver.get_car_data().add_distance()
        latest = telemetry.iloc[-1]

        return {
            "status": "live",
            "speed": float(latest['Speed']),
            "throttle": float(latest['Throttle']),
            "brake": float(latest['Brake']),
            "gear": int(latest['nGear'])
        }

    except Exception as e:
        return {"error": str(e)}
