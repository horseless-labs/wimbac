from flask import Flask, render_template, jsonify, Response, request
import os
import math

# vehicle position caching stuff
import time
import threading

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

# Refreshes vehicle position cache
def refresh_latest_vehicles_if_stale():
    global LATEST_VEHICLES, LATEST_VEHICLES_TS

    now = time.time()

    # cache still fresh
    with LATEST_LOCK:
        if (now - LATEST_VEHICLES_TS) < VEHICLE_CACHE_TTL_S and LATEST_VEHICLES:
            return
    
    # Refresh outside the lock (avoid blocking readers)
    data = merge_trip_updates_and_positions(update_url, pos_url)

    # Keep only mappable vehicles
    valid = [v for v in data if v.get("lat") is not None and v.get("lon") is not None]

    # Write once per refresh, not once per client
    try:
        save_to_influx(valid)
        print("Transit data saved to Influx")
    except Exception as e:
        print(f"Influx write failed: {e}")
    
    # update cache automatically
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

    if lat is None or lon is None:
        return jsonify([])
    
    refresh_latest_vehicles_if_stale()

    with LATEST_LOCK:
        vehicles = list(LATEST_VEHICLES)
    
    out = []
    for v in vehicles:
        try:
            d = haversine_m(lat, lon, float(v["lat"]), float(v["long"]))
        except Exception:
            continue
        if d <= r_m:
            out.append(v)
    
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
