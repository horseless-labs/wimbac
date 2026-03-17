import os
import time
from flask import Blueprint, jsonify

from services.telemetry import telemetry

system_bp = Blueprint("system_bp", __name__)


@system_bp.route("/api/system/health", methods=["GET"])
def system_health():
    snap = telemetry.snapshot()

    gtfs_age = snap["gtfs"]["refresh_age_sec"]
    cache_age = snap["cache"]["age_sec"]
    last_gtfs_error = snap["gtfs"]["last_error"]

    # Tweak thresholds if your feed cadence is closer to 20s or 30s.
    gtfs_ok = gtfs_age is not None and gtfs_age < 120
    cache_ok = cache_age is not None and cache_age < 120

    status = "ok"
    reasons = []

    if not gtfs_ok:
        status = "degraded"
        reasons.append("GTFS refresh is stale or missing")

    if not cache_ok:
        status = "degraded"
        reasons.append("Vehicle cache is stale or missing")

    if last_gtfs_error:
        status = "degraded"
        reasons.append(f"Last GTFS fetch error: {last_gtfs_error}")

    payload = {
        "status": status,
        "service": os.getenv("APP_NAME", "wimbac"),
        "timestamp": time.time(),
        "checks": {
            "gtfs_fresh": gtfs_ok,
            "cache_fresh": cache_ok,
        },
        "details": {
            "gtfs_refresh_age_sec": gtfs_age,
            "cache_age_sec": cache_age,
            "cache_item_count": snap["cache"]["item_count"],
            "uptime_sec": snap["service"]["uptime_sec"],
        },
        "reasons": reasons,
    }

    code = 200 if status == "ok" else 503
    return jsonify(payload), code


@system_bp.route("/api/system/metrics", methods=["GET"])
def system_metrics():
    return jsonify(telemetry.snapshot()), 200