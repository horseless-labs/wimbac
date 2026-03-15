from flask import Flask, render_template, jsonify, Response, request
import atexit
import os
import math

import time
import threading
import requests
import json

# TODO: make this less sloppy later
from merge_feeds import *
from stops import load_stops

app = Flask(__name__)

# vehicle position caching stuff
LATEST_LOCK = threading.Lock()

LATEST_VEHICLES = []
LATEST_VEHICLES_JSON = "[]"
LATEST_VEHICLES_TS = 0.0 # epoch seconds

REFRESH_THREAD = None
STOP_REFRESH = threading.Event()

VEHICLE_REFRESH_INTERVAL_S = 30
MAX_STALE_S = 5 * 60   # allow serving stale data up to 5 minutes
STOPS = load_stops()

# Calculates spherical distance between two points
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def refresh_latest_vehicles():
    global LATEST_VEHICLES, LATEST_VEHICLES_JSON, LATEST_VEHICLES_TS

    now = time.time()

    try:
        data = merge_trip_updates_and_positions(update_url, pos_url)
        valid = [v for v in data if v.get("lat") is not None and v.get("lon") is not None]
    except requests.RequestException as e:
        print(f"GTFS-RT fetch failed: {e}")

        with LATEST_LOCK:
            # Keep serving stale data if we have something reasonably recent
            if LATEST_VEHICLES and (now - LATEST_VEHICLES_TS) < MAX_STALE_S:
                return

            # No valid cache left
            LATEST_VEHICLES = []
            LATEST_VEHICLES_JSON = "[]"
            LATEST_VEHICLES_TS = now
        return
    except Exception as e:
        print(f"Vehicle refresh failed: {e}")
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
    
    refresh_latest_vehicles()

    REFRESH_THREAD = threading.Thread(
        target=vehicle_refresh_loop,
        name="vehicle-refresh-thread",
        daemon=True
    )
    REFRESH_THREAD.start()

def stop_vehicle_refresh_thread():
    STOP_REFRESH.set()
    global REFRESH_THREAD
    if REFRESH_THREAD is not None and REFRESH_THREAD.is_alive():
        REFRESH_THREAD.join(timeout=2)

atexit.register(stop_vehicle_refresh_thread)

@app.route('/')
def home():
    """Serves the actual map"""
    return render_template("index.html")

@app.route('/data')
def get_bus_data():
    with LATEST_LOCK:
        return Response(LATEST_VEHICLES_JSON, mimetype='application/json')

# TODO: add try/except block to catch GCRTA server being down
#       instead of a 500 internal server error page.
@app.route('/api/vehicles')
def api_vehicles():
    with LATEST_LOCK:
        return Response(LATEST_VEHICLES_JSON, mimetype='application/json')
    
@app.get("/api/vehicles_near")
def api_vehicles_near():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    r_m = request.args.get("r_m", default=800.0, type=float)
    debug = request.args.get("debug", default=0, type=int)

    if lat is None or lon is None:
        return jsonify({"error": "missing lat/lon"} if debug else [])

    with LATEST_LOCK:
        vehicles = list(LATEST_VEHICLES)
        cache_age_s = time.time() - LATEST_VEHICLES_TS if LATEST_VEHICLES_TS else None

    # Score all vehicles by distance
    scored = []
    for v in vehicles:
        try:
            vlat = float(v["lat"])
            vlon = float(v["lon"])
            d = haversine_m(lat, lon, vlat, vlon)
        except Exception:
            continue
        scored.append((d, v))

    scored.sort(key=lambda x: x[0])

    within = [v for (d, v) in scored if d <= r_m]

    if debug:
        nearest_preview = []
        for d, v in scored[:10]:
            vv = dict(v)
            vv["distance_m"] = round(d, 1)
            nearest_preview.append(vv)

        return jsonify({
            "query": {"lat": lat, "lon": lon, "r_m": r_m},
            "cache": {"vehicles_total": len(vehicles), "cache_age_s": None if cache_age_s is None else round(cache_age_s, 2)},
            "result": {"within_count": len(within)},
            "nearest_10": nearest_preview
        })

    return jsonify(within)

@app.get("/api/vehicles_nearest")
def api_vehicles_nearest():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    n = request.args.get("n", default=10, type=int)

    if lat is None or lon is None:
        return jsonify([])
    
    with LATEST_LOCK:
        vehicles = list(LATEST_VEHICLES)

    scored = []
    for v in vehicles:
        try:
            d = haversine_m(lat, lon, float(v["lat"]), float(v["lon"]))
        except Exception:
            continue
        scored.append((d, v))

    scored.sort(key=lambda x: x[0])

    out = []
    for d, v in scored[:max(0, n)]:
        vv = dict(v)
        vv["distance_m"] = round(d, 1)
        out.append(vv)

    return jsonify(out)

@app.get("/api/stops")
def api_stops():
    # otpional bbox filtering
    min_lat = request.args.get("min_lat", type=float)
    max_lat = request.args.get("max_lat", type=float)
    min_lon = request.args.get("min_lon", type=float)
    max_lon = request.args.get("max_lon", type=float)

    if None in (min_lat, max_lat, min_lon, max_lon):
        return jsonify(STOPS[:2000])
    
    out = [
        s for s in STOPS
        if (min_lat <= s["lat"] <= max_lat) and (min_lon <= s["lon"] <= max_lon)
        and s["location_type"] == 0
    ]

    return jsonify(out)

@app.route("/health")
def health():
    return Response(
        f"""
        <html>
            <head>
                <title>WIMBAC Health</title>
            </head>
            <body style="font-family: monospace; background:#111; color:#0f0;">
                <h1>WIMBAC is alive.</h1>
                <p>Host: {os.uname().nodename}</p>
                <p>Process ID: {os.getpid()}</p>
            </body>
        </html>
        """,
        mimetype="text/html",
    )

start_vehicle_refresh_thread()

if __name__ == '__main__':
    # 0.0.0.0 makes it accessible locally
    app.run(debug=True, host='0.0.0.0', port=5000)
