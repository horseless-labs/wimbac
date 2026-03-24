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

@analytics_bp.route("/api/analytics/stop-ontime", methods=["GET"])
def stop_ontime(
    self,
    stop_id: str,
    target_hour: int,
    route_id=None,
    threshold_seconds: int = 60,
    hour_window: int = 1,
) -> Dict[str, Any]:
    def build_flux(lookback_days: int, use_hour_filter: bool) -> str:
        min_hour = max(0, target_hour - hour_window)
        max_hour = min(23, target_hour + hour_window)

        flux = f'''
import "date"

from(bucket: "{self.bucket}")
  |> range(start: -{lookback_days}d)
  |> filter(fn: (r) => r["_measurement"] == "vehicle_status")
  |> filter(fn: (r) => r["_field"] == "delay_seconds")
  |> filter(fn: (r) => r["next_stop_id"] == "{stop_id}")
  |> filter(fn: (r) => exists r.trip_id)
'''

        if route_id:
            flux += f'''  |> filter(fn: (r) => r["route_id"] == "{route_id}")
'''

        if use_hour_filter:
            flux += f'''  |> map(fn: (r) => ({{
      r with hour: date.hour(t: r._time)
  }}))
  |> filter(fn: (r) => r.hour >= {min_hour} and r.hour <= {max_hour})
'''

        flux += '''
  |> group(columns: ["vehicle_id", "next_stop_id"])
  |> sort(columns: ["_time"], desc: true)
  |> first()
  |> keep(columns: ["vehicle_id", "next_stop_id", "_time", "_value", "route_id", "trip_id"])
'''
        return flux

    def summarize(
        tables,
        lookback_days_used: int,
        time_filter_applied: bool,
    ) -> Dict[str, Any]:
        total = 0
        on_time_count = 0
        matched_routes = set()
        vehicle_ids = set()
        trip_ids = set()

        for table in tables:
            for record in table.records:
                vehicle_id = record.values.get("vehicle_id")
                if not vehicle_id:
                    continue

                trip_id = record.values.get("trip_id")
                if not trip_id:
                    continue

                delay = record.get_value()
                if delay is None:
                    continue

                vehicle_ids.add(str(vehicle_id))
                trip_ids.add(str(trip_id))
                total += 1

                record_route_id = record.values.get("route_id")
                if record_route_id is not None:
                    matched_routes.add(str(record_route_id))

                try:
                    if abs(int(delay)) <= threshold_seconds:
                        on_time_count += 1
                except Exception:
                    continue

        percentage = None if total == 0 else round((on_time_count / total) * 100, 2)

        if total == 0:
            confidence = "none"
        elif total < 3:
            confidence = "low"
        elif total < 10:
            confidence = "limited"
        else:
            confidence = "strong"

        return {
            "stop_id": stop_id,
            "route_id": route_id,
            "matched_route_ids": sorted(matched_routes),
            "threshold_seconds": threshold_seconds,
            "sample_size": total,
            "distinct_vehicle_count": len(vehicle_ids),
            "distinct_trip_count": len(trip_ids),
            "on_time_percentage": percentage,
            "time_filter_applied": time_filter_applied,
            "lookback_days_used": lookback_days_used,
            "confidence": confidence,
        }

    query_plans = [
        (14, True),
        (14, False),
        (30, False),
    ]

    for lookback_days, use_hour_filter in query_plans:
        flux = build_flux(lookback_days, use_hour_filter)
        tables = self.query_api.query(query=flux, org=self.org)
        result = summarize(
            tables,
            lookback_days_used=lookback_days,
            time_filter_applied=use_hour_filter,
        )
        if result["sample_size"] > 0:
            return result

    return {
        "stop_id": stop_id,
        "route_id": route_id,
        "matched_route_ids": [],
        "threshold_seconds": threshold_seconds,
        "sample_size": 0,
        "distinct_vehicle_count": 0,
        "distinct_trip_count": 0,
        "on_time_percentage": None,
        "time_filter_applied": False,
        "lookback_days_used": 30,
        "confidence": "none",
    }