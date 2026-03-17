import os
from datetime import datetime, timezone
from pathlib import Path

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


org = os.getenv("INFLUX_ORG", "Horseless Labs")
bucket = os.getenv("INFLUX_BUCKET", "wimbac")

influx_token = os.getenv("INFLUX_TOKEN")
if influx_token:
    print(f"Using token from Environment (starts with: {influx_token[:5]}...)")
else:
    token_path = Path("influx_token.txt")
    if token_path.exists():
        influx_token = token_path.read_text().strip()
        print(f"Using token from File (starts with: {influx_token[:5]}...)")

client = InfluxDBClient(url="http://localhost:8086", token=influx_token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)


def save_to_influx(merged_data):
    points = []
    for row in merged_data:
        point = (
            Point("vehicle_status")
            .tag("vehicle_id", row["vehicle_id"])
            .tag("route_id", row["route_id"])
            .field("lat", float(row["lat"]) if row["lat"] else 0.0)
            .field("lon", float(row["lon"]) if row["lon"] else 0.0)
            .time(datetime.now(timezone.utc), WritePrecision.NS)
        )

        if row["stop_time_updates"]:
            first_update = row["stop_time_updates"][0]
            delay = (
                first_update.get("arrival", {}).get("delay")
                or first_update.get("departure", {}).get("delay", 0)
            )
            point.field("delay_seconds", int(delay))
            point.tag("next_stop_id", first_update.get("stop_id"))

        points.append(point)

    write_api.write(bucket=bucket, org=org, record=points)