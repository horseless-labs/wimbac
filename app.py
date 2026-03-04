from flask import Flask, render_template, jsonify, Response, request
import os
import math

# vehicle position caching stuff
import time
import threading
import requests

# TODO: make this less sloppy later
from merge_feeds import *
from stops import load_stops

app = Flask(__name__)

# vehicle position caching stuff
LATEST_VEHICLES = []
LATEST_VEHICLES_TS = 0.0 # epoch seconds
LATEST_LOCK = threading.Lock()
VEHICLE_CACHE_TTL_S = 30 # site throttles with updates <30s

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

# vehicle position cache stuff
LATEST_VEHICLES = []
LATEST_VEHICLES_TS = 0.0
LATEST_LOCK = threading.Lock()

VEHICLE_CACHE_TTL_S = 15
MAX_STALE_S = 5 * 60   # allow serving stale data up to 5 minutes

def refresh_latest_vehicles_if_stale():
    global LATEST_VEHICLES, LATEST_VEHICLES_TS

    now = time.time()

    with LATEST_LOCK:
        fresh = (now - LATEST_VEHICLES_TS) < VEHICLE_CACHE_TTL_S and bool(LATEST_VEHICLES)
        if fresh:
            return

    try:
        data = merge_trip_updates_and_positions(update_url, pos_url)
        valid = [v for v in data if v.get("lat") is not None and v.get("lon") is not None]
    except requests.RequestException as e:
        # Upstream GTFS-RT is failing. Serve stale cache rather than 500ing.
        print(f"GTFS-RT fetch failed: {e}")

        with LATEST_LOCK:
            # If we have anything reasonably recent, just keep serving it.
            if LATEST_VEHICLES and (now - LATEST_VEHICLES_TS) < MAX_STALE_S:
                return

        # No cache to fall back to
        with LATEST_LOCK:
            LATEST_VEHICLES = []
            LATEST_VEHICLES_TS = now
        return
    except Exception as e:
        print(f"Vehicle refresh failed: {e}")
        return

    # Influx write should never take down serving
    try:
        save_to_influx(valid)
    except Exception as e:
        print(f"Influx write failed: {e}")

    with LATEST_LOCK:
        LATEST_VEHICLES = valid
        LATEST_VEHICLES_TS = now

@app.route('/')
def home():
    """Serves the actual map"""
    return render_template("index.html")

@app.route('/data')
def get_bus_data():
    """The API endpoint the map calls every X seconds"""
    # Call existing merge function
    merged_data = merge_trip_updates_and_positions(update_url, pos_url)

    # Only use vehicles that have a map location
    live_vehicles = [v for v in merged_data if v.get('lat')]

    return jsonify(live_vehicles)

# TODO: add try/except block to catch GCRTA server being down
#       instead of a 500 internal server error page.
@app.route('/api/vehicles')
def api_vehicles():
    refresh_latest_vehicles_if_stale()
    with LATEST_LOCK:
        return jsonify(LATEST_VEHICLES)
    
@app.get("/api/vehicles_near")
def api_vehicles_near():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    r_m = request.args.get("r_m", default=800.0, type=float)
    debug = request.args.get("debug", default=0, type=int)

    if lat is None or lon is None:
        return jsonify({"error": "missing lat/lon"} if debug else [])

    # IMPORTANT: make sure this is the SAME refresh function used everywhere
    refresh_latest_vehicles_if_stale()

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

    refresh_latest_vehicles_if_stale()

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

if __name__ == '__main__':
    # 0.0.0.0 makes it accessible locally
    app.run(debug=True, host='0.0.0.0', port=5000)
