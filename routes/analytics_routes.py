from datetime import datetime, timezone
from typing import Dict, Any
from flask import Blueprint, jsonify, request

from services.influx_analytics import InfluxAnalyticsService

analytics_bp = Blueprint("analytics_bp", __name__)

@analytics_bp.route("/api/analytics/vehicles-by-hour", methods=["GET"])
def vehicles_by_hour():
    hours = request.args.get("hours", default=72, type=int)
    hours = max(1, min(hours, 24 * 30))

    service = InfluxAnalyticsService()
    try:
        data = service.vehicles_by_hour(hours=hours)
        return jsonify({
            "hours": hours,
            "points": data,
            "count": len(data),
        }), 200
    except Exception as exc:
        return jsonify({
            "error": "Failed to query vehicles-by-hour analytics",
            "details": str(exc),
        }), 500
    finally:
        service.close()


@analytics_bp.route("/api/analytics/routes-summary", methods=["GET"])
def routes_summary():
    hours = request.args.get("hours", default=24, type=int)
    hours = max(1, min(hours, 24 * 30))

    service = InfluxAnalyticsService()
    try:
        data = service.routes_summary(hours=hours)
        return jsonify({
            "hours": hours,
            "routes": data,
            "count": len(data),
        }), 200
    except Exception as exc:
        return jsonify({
            "error": "Failed to query routes-summary analytics",
            "details": str(exc),
        }), 500
    finally:
        service.close()

@analytics_bp.route("/api/analytics/stop-reliability", methods=["GET"])
def stop_reliability():
    stop_id = request.args.get("stop_id")
    route_id = request.args.get("route_id") # Optional
    
    if not stop_id:
        return jsonify({"error": "stop_id is required"}), 400

    # Get current hour for the time-of-day filter
    current_hour = datetime.now(timezone.utc).hour 
    
    service = InfluxAnalyticsService()
    try:
        stats = service.get_stop_reliability(
            stop_id=stop_id,
            target_hour=current_hour,
            route_id=route_id
        )
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        service.close()