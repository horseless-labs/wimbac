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