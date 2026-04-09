from flask import Flask, render_template, jsonify, Response, request, g
from flask_cors import CORS
import atexit
import os
import math

import time
import threading
import requests
import json

# TODO: make this less sloppy later
from merge_feeds import *
from services.stops import load_stops
from services.telemetry import telemetry
from routes.system_routes import system_bp
from routes.analytics_routes import analytics_bp

from utils.geo import haversine_m
import services.vehicle_state as vehicle_state

app = Flask(__name__)
CORS(app)

atexit.register(vehicle_state.stop_vehicle_refresh_thread)

# Register blueprints
app.register_blueprint(system_bp)
app.register_blueprint(analytics_bp)

@app.before_request
def start_request_timer():
    g.request_start_time = time.perf_counter()


@app.after_request
def record_request_metrics(response):
    try:
        start = getattr(g, "request_start_time", None)
        if start is not None:
            duration_ms = (time.perf_counter() - start) * 1000.0
            endpoint = request.path
            telemetry.record_request(
                endpoint=endpoint,
                duration_ms=duration_ms,
                status_code=response.status_code,
            )
    except Exception:
        # Never let telemetry break the request path.
        pass

    return response

@app.route('/')
def home():
    """Serves the actual map"""
    return render_template("index.html")

@app.route('/data')
def get_bus_data():
    return Response(vehicle_state.get_latest_vehicles_json(), mimetype='application/json')

# TODO: add try/except block to catch GCRTA server being down
#       instead of a 500 internal server error page.
@app.route('/api/vehicles')
def api_vehicles():
    return Response(vehicle_state.get_latest_vehicles_json(), mimetype='application/json')

@app.get("/api/vehicles_near")
def api_vehicles_near():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    r_m = request.args.get("r_m", default=800.0, type=float)
    debug = request.args.get("debug", default=0, type=int)

    if lat is None or lon is None:
        return jsonify({"error": "missing lat/lon"} if debug else [])

    vehicles = list(vehicle_state.get_latest_vehicles())
    cache_age_s = time.time() - vehicle_state.LATEST_VEHICLES_TS if vehicle_state.LATEST_VEHICLES_TS else None

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

    vehicles = list(vehicle_state.get_latest_vehicles())

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
        return jsonify(vehicle_state.STOPS[:2000])
    
    out = [
        s for s in vehicle_state.STOPS
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

vehicle_state.start_vehicle_refresh_thread()

if __name__ == '__main__':
    # 0.0.0.0 makes it accessible locally
    app.run(debug=True, host='0.0.0.0', port=5000)
