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
    
    def get_stop_reliability(
        self,
        stop_id: str,
        target_hour: int,
        route_id=None,
        threshold_seconds: int = 60,
        hour_window: int = 1,
    ) -> Dict[str, Any]:
        search_id = str(stop_id).strip().zfill(5) if str(stop_id).strip().isdigit() else str(stop_id).strip()

        def build_flux(lookback_days: int, use_hour_filter: bool) -> str:
            min_hour = (target_hour - hour_window) % 24
            max_hour = (target_hour + hour_window) % 24

            flux = f'''
            import "date"
            from(bucket: "{self.bucket}")
            |> range(start: -{lookback_days}d)
            |> filter(fn: (r) => r["_measurement"] == "vehicle_status")
            |> filter(fn: (r) => r["_field"] == "delay_seconds")
            # Use vehicle_id for grouping since trip_id is currently a field (slow)
            |> filter(fn: (r) => r["next_stop_id"] == "{search_id}")
            '''
            
            if route_id:
                flux += f'  |> filter(fn: (r) => r["route_id"] == "{route_id}")\n'

            if use_hour_filter:
                # Standard hour filtering logic
                if min_hour < max_hour:
                    flux += f'  |> filter(fn: (r) => date.hour(t: r._time) >= {min_hour} and date.hour(t: r._time) <= {max_hour})\n'
                else:
                    flux += f'  |> filter(fn: (r) => date.hour(t: r._time) >= {min_hour} or date.hour(t: r._time) <= {max_hour})\n'

            # THE PERFORMANCE + ACCURACY FIX:
            # 1. Group by vehicle_id (since it's a tag) to separate individual bus runs.
            # 2. Use 'max' or 'last' to pick the single most representative ping for that stop visit.
            flux += '''
            |> group(columns: ["vehicle_id", "route_id"])
            |> last()
            |> group() 
            '''
            return flux

        query_plans = [(7, True), (14, False), (30, False)]
        
        for days, use_filter in query_plans:
            flux = build_flux(days, use_filter)
            try:
                tables = self.query_api.query(org=self.org, query=flux)
            except Exception as e:
                print(f"Query failed: {e}")
                continue
            
            delays = []
            for table in tables:
                for record in table.records:
                    val = record.get_value()
                    if val is not None:
                        # We use the raw value for late/early. 
                        # abs() is fine if you only care about 'off-schedule'
                        delays.append(abs(val))

            if not delays:
                continue

            sample_size = len(delays)
            on_time_count = sum(1 for d in delays if d <= threshold_seconds)
            
            return {
                "stop_id": search_id,
                "on_time_percentage": round((on_time_count / sample_size) * 100, 1),
                "sample_size": sample_size,
                "confidence": "strong" if sample_size > 15 else "limited" if sample_size > 3 else "low",
                "lookback_days": days,
                "time_filter_active": use_filter
            }

        return {"sample_size": 0, "confidence": "none", "stop_id": search_id}