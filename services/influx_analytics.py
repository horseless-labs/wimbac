import os
from typing import Any, Dict, List

from influxdb_client import InfluxDBClient


class InfluxAnalyticsService:
    def __init__(self):
        self.url = os.environ.get("INFLUX_URL", "http://localhost:8086")
        self.token = os.environ["INFLUX_TOKEN"]
        self.org = os.environ["INFLUX_ORG"]
        self.bucket = os.environ["INFLUX_BUCKET"]

        self.client = InfluxDBClient(
            url=self.url,
            token=self.token,
            org=self.org,
            timeout=30000,
        )
        self.query_api = self.client.query_api()

    def vehicles_by_hour(self, hours: int = 72) -> List[Dict[str, Any]]:
        """
        Counts vehicle_status points by hour.
        Uses lat field because every written point has lat/lon fields.
        """
        flux = f"""
from(bucket: "{self.bucket}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r["_measurement"] == "stop_events")
  |> filter(fn: (r) => r["_field"] == "lat")
  |> aggregateWindow(every: 1h, fn: count, createEmpty: false)
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
"""

        tables = self.query_api.query(query=flux, org=self.org)
        rows = []
        for table in tables:
            for record in table.records:
                rows.append({
                    "time": record.get_time().isoformat(),
                    "vehicle_count": record.get_value(),
                })
        return rows

    def routes_summary(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Counts observations by route_id over the last N hours.
        Uses lat field because each point has it, and route_id is a tag.
        """
        flux = f"""
from(bucket: "{self.bucket}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r["_measurement"] == "vehicle_status")
  |> filter(fn: (r) => r["_field"] == "lat")
  |> group(columns: ["route_id"])
  |> count()
  |> keep(columns: ["route_id", "_value"])
  |> sort(columns: ["_value"], desc: true)
"""

        tables = self.query_api.query(query=flux, org=self.org)
        rows = []
        for table in tables:
            for record in table.records:
                rows.append({
                    "route_id": record.values.get("route_id", "unknown"),
                    "observations": record.get_value(),
                })
        return rows

    def close(self) -> None:
        self.client.close()

    def stop_ontime_percentage(
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
    |> filter(fn: (r) => r["_measurement"] == "stop_events")
    |> filter(fn: (r) => r["stop_id"] == "{stop_id}")
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
    |> filter(fn: (r) => r["_field"] == "delay_seconds" or r["_field"] == "on_time")
    |> pivot(
        rowKey: ["_time", "trip_id", "stop_id", "route_id", "vehicle_id"],
        columnKey: ["_field"],
        valueColumn: "_value"
    )
    |> group(columns: ["trip_id"])
    |> sort(columns: ["_time"], desc: true)
    |> first()
    |> keep(columns: ["trip_id", "stop_id", "route_id", "vehicle_id", "_time", "delay_seconds", "on_time"])
    '''
            return flux

        def summarize(tables, lookback_days_used: int, time_filter_applied: bool) -> Dict[str, Any]:
            total = 0
            on_time_count = 0
            matched_routes = set()
            trip_ids = set()

            for table in tables:
                for record in table.records:
                    trip_id = record.values.get("trip_id")
                    if not trip_id:
                        continue

                    trip_ids.add(str(trip_id))
                    total += 1

                    record_route_id = record.values.get("route_id")
                    if record_route_id is not None:
                        matched_routes.add(str(record_route_id))

                    on_time_value = record.values.get("on_time")
                    delay_value = record.values.get("delay_seconds")

                    if on_time_value is not None:
                        try:
                            if int(on_time_value) == 1:
                                on_time_count += 1
                        except Exception:
                            pass
                    elif delay_value is not None:
                        try:
                            if abs(int(delay_value)) <= threshold_seconds:
                                on_time_count += 1
                        except Exception:
                            pass

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
            "distinct_trip_count": 0,
            "on_time_percentage": None,
            "time_filter_applied": False,
            "lookback_days_used": 30,
            "confidence": "none",
        }