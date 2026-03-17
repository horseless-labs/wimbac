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