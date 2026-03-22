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
  |> filter(fn: (r) => r["_measurement"] == "vehicle_status")
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
    route_id: str = None,
    target_hour: int,
    lookback_days: int = 14,
    threshold_seconds: int = 60,
) -> Dict[str, Any]:
        flux = f"""
    import "date"
    
    from(bucket: "{self.bucket}")
    |> range(start: -{lookback_days}d)
    |> filter(fn: (r) => r["_measurement"] == "vehicle_status")
    |> filter(fn: (r) => r["_field"] == "delay_seconds")
    |> filter(fn: (r) => r["next_stop_id"] == "{stop_id}")
    |> filter(fn: (r) => r["route_id"] == "{route_id}")
    |> map(fn: (r) => ({{
        r with hour: date.hour(t: r._time)
    }}))
    |> filter(fn: (r) => r.hour >= {target_hour - 1} and r.hour <= {target_hour + 1})
    |> group(columns: ["trip_id"])
    |> last()
    |> keep(columns: ["trip_id", "_time", "_value"])
    """

        tables = self.query_api.query(query=flux, org=self.org)

        total = 0
        on_time_count = 0

        for table in tables:
            for record in table.records:
                delay = record.get_value()
                if delay is None:
                    continue

                total += 1

                if abs(delay) <= threshold_seconds:
                    on_time_count += 1

        percentage = None if total == 0 else round((on_time_count / total) * 100, 2)

        return {
            "stop_id": stop_id,
            "route_id": route_id,
            "lookback_days": lookback_days,
            "threshold_seconds": threshold_seconds,
            "sample_size": total,
            "on_time_percentage": percentage,
        }