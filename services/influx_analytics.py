import os
from typing import Any, Dict, List

from influxdb_client import InfluxDBClient


class InfluxAnalyticsService:
    def __init__(self):
        self.url = os.environ["INFLUX_URL"]
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
        Returns observed vehicle counts grouped by hour.
        Assumes a measurement like `vehicle_positions`.
        Adjust `_measurement`, field names, and tags as needed.
        """
        flux = f"""
from(bucket: "{self.bucket}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r["_measurement"] == "vehicle_positions")
  |> filter(fn: (r) => r["_field"] == "vehicle_id")
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
        Summarizes observed telemetry by route over the last N hours.

        Assumes:
        - measurement: vehicle_positions
        - route_id stored as a tag or column
        - vehicle_id field exists

        If your schema differs, update the Flux query.
        """
        flux = f"""
from(bucket: "{self.bucket}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r["_measurement"] == "vehicle_positions")
  |> filter(fn: (r) => r["_field"] == "vehicle_id")
  |> group(columns: ["route_id"])
  |> count()
  |> keep(columns: ["route_id", "_value"])
  |> sort(columns: ["_value"], desc: true)
"""

        tables = self.query_api.query(query=flux, org=self.org)
        rows = []
        for table in tables:
            for record in table.records:
                route_id = record.values.get("route_id", "unknown")
                rows.append({
                    "route_id": route_id,
                    "observations": record.get_value(),
                })
        return rows

    def close(self) -> None:
        self.client.close()