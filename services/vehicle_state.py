import json
import threading
import time

import requests

from services.gtfs import merge_trip_updates_and_positions
from services.influx_writer import save_to_influx
from services.stops import load_stops
from services.telemetry import telemetry
from config import update_url, pos_url


LATEST_LOCK = threading.Lock()

LATEST_VEHICLES = []
LATEST_VEHICLES_JSON = "[]"
LATEST_VEHICLES_TS = 0.0  # epoch seconds

REFRESH_THREAD = None
STOP_REFRESH = threading.Event()

VEHICLE_REFRESH_INTERVAL_S = 30
MAX_STALE_S = 5 * 60   # allow serving stale data up to 5 minutes
STOPS = load_stops()

def refresh_latest_vehicles():
    global LATEST_VEHICLES, LATEST_VEHICLES_JSON, LATEST_VEHICLES_TS

    now = time.time()

    # Cache miss: we are attempting a fresh fetch
    telemetry.record_cache_miss()

    try:
        data = merge_trip_updates_and_positions(update_url, pos_url)
        valid = [v for v in data if v.get("lat") is not None and v.get("lon") is not None]
    except requests.RequestException as e:
        print(f"GTFS-RT fetch failed: {e}")
        telemetry.record_gtfs_fetch_failure(str(e))

        with LATEST_LOCK:
            # Keep serving stale data if we have something reasonably recent
            if LATEST_VEHICLES and (now - LATEST_VEHICLES_TS) < MAX_STALE_S:
                return

            # No valid cache left
            LATEST_VEHICLES = []
            LATEST_VEHICLES_JSON = "[]"
            LATEST_VEHICLES_TS = now
            telemetry.update_cache_state(
                item_count=0,
                updated_ts=LATEST_VEHICLES_TS,
            )
        return
    except Exception as e:
        print(f"Vehicle refresh failed: {e}")
        telemetry.record_gtfs_fetch_failure(str(e))
        return

    # Influx write should never block serving logic conceptually,
    # but in this version it's already off the request path, so this is okay here.
    try:
        save_to_influx(valid)
    except Exception as e:
        print(f"Influx write failed: {e}")

    # Pre-serialize once so requests don't keep paying JSON encoding cost
    try:
        payload_json = json.dumps(valid, separators=(",", ":"))
    except Exception as e:
        print(f"JSON serialization failed during refresh: {e}")
        return

    with LATEST_LOCK:
        LATEST_VEHICLES = valid
        LATEST_VEHICLES_JSON = payload_json
        LATEST_VEHICLES_TS = now

    telemetry.record_gtfs_fetch_success()
    telemetry.update_cache_state(
        item_count=len(valid),
        updated_ts=LATEST_VEHICLES_TS,
    )

def get_latest_vehicles():
    now = time.time()

    with LATEST_LOCK:
        if (
            LATEST_VEHICLES is not None
            and LATEST_VEHICLES_TS is not None
            and (now - LATEST_VEHICLES_TS) < VEHICLE_REFRESH_INTERVAL_S
        ):
            telemetry.record_cache_hit()
            return LATEST_VEHICLES

    with LATEST_LOCK:
        telemetry.record_cache_hit()
        return list(LATEST_VEHICLES)

def get_latest_vehicles_json():
    with LATEST_LOCK:
        telemetry.record_cache_hit()
        return LATEST_VEHICLES_JSON

def vehicle_refresh_loop():
    while not STOP_REFRESH.is_set():
        started = time.perf_counter()
        refresh_latest_vehicles()
        elapsed = time.perf_counter() - started
        sleep_for = max(0, VEHICLE_REFRESH_INTERVAL_S - elapsed)
        STOP_REFRESH.wait(timeout=sleep_for)

def start_vehicle_refresh_thread():
    global REFRESH_THREAD
    if REFRESH_THREAD is not None and REFRESH_THREAD.is_alive():
        return

    STOP_REFRESH.clear()
    refresh_latest_vehicles()

    REFRESH_THREAD = threading.Thread(
        target=vehicle_refresh_loop,
        name="vehicle-refresh-thread",
        daemon=True
    )
    REFRESH_THREAD.start()

def stop_vehicle_refresh_thread():
    global REFRESH_THREAD
    STOP_REFRESH.set()
    if REFRESH_THREAD is not None and REFRESH_THREAD.is_alive():
        REFRESH_THREAD.join(timeout=2)