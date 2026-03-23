import os
from pathlib import Path

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from services.stop_event_state import (
    StopEventTracker,
    VehicleSnapshot,
    build_stop_event_point,
)

stop_event_tracker = StopEventTracker(on_time_threshold_seconds=60)

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


def _safe_str(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def _safe_float(value):
    if value is None or value == "":
        return None
    return float(value)


def _safe_int(value):
    if value is None or value == "":
        return None
    return int(value)

def save_to_influx(merged_data):
    from datetime import datetime, timezone

    from influxdb_client import Point, WritePrecision

    from services.stop_event_state import (
        VehicleSnapshot,
        build_stop_event_point,
    )

    points = []

    def parse_dt(value):
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def safe_str(value):
        if value is None:
            return None
        value = str(value).strip()
        return value if value else None

    def safe_int(value):
        if value is None or value == "":
            return None
        try:
            return int(value)
        except Exception:
            return None

    def safe_float(value):
        if value is None or value == "":
            return None
        try:
            return float(value)
        except Exception:
            return None

    for item in merged_data:
        vehicle_id = safe_str(item.get("vehicle_id"))
        if not vehicle_id:
            continue

        vehicle_label = safe_str(item.get("vehicle_label"))
        route_id = safe_str(item.get("route_id"))
        trip_id = safe_str(item.get("trip_id"))
        start_date = safe_str(item.get("start_date"))

        direction_id_raw = item.get("direction_id")
        direction_id = None if direction_id_raw in (None, "") else str(direction_id_raw)

        next_stop_id = safe_str(item.get("next_stop_id"))
        next_stop_sequence = safe_int(item.get("next_stop_sequence"))
        delay_seconds = safe_int(item.get("delay_seconds"))

        lat = safe_float(item.get("lat"))
        lon = safe_float(item.get("lon"))
        bearing = safe_float(item.get("bearing"))
        speed_mps = safe_float(item.get("speed_mps"))

        vp_timestamp = item.get("vp_timestamp")
        tu_timestamp = item.get("tu_timestamp")
        scheduled_departure_unix = safe_int(item.get("scheduled_departure_unix"))

        vp_dt = parse_dt(vp_timestamp)
        tu_dt = parse_dt(tu_timestamp)

        point_time = vp_dt or tu_dt or datetime.now(timezone.utc)

        point = (
            Point("vehicle_status")
            .tag("vehicle_id", vehicle_id)
            .time(point_time, WritePrecision.S)
        )

        if vehicle_label is not None:
            point = point.tag("vehicle_label", vehicle_label)
        if route_id is not None:
            point = point.tag("route_id", route_id)
        if trip_id is not None:
            point = point.tag("trip_id", trip_id)
        if start_date is not None:
            point = point.tag("start_date", start_date)
        if direction_id is not None:
            point = point.tag("direction_id", direction_id)
        if next_stop_id is not None:
            point = point.tag("next_stop_id", next_stop_id)

        if lat is not None:
            point = point.field("lat", lat)
        if lon is not None:
            point = point.field("lon", lon)
        if bearing is not None:
            point = point.field("bearing", bearing)
        if speed_mps is not None:
            point = point.field("speed_mps", speed_mps)
        if delay_seconds is not None:
            point = point.field("delay_seconds", delay_seconds)
        if next_stop_sequence is not None:
            point = point.field("next_stop_sequence", next_stop_sequence)
        if scheduled_departure_unix is not None:
            point = point.field("scheduled_departure_unix", scheduled_departure_unix)
        if vp_dt is not None:
            point = point.field("vp_timestamp", int(vp_dt.timestamp()))
        if tu_dt is not None:
            point = point.field("tu_timestamp", int(tu_dt.timestamp()))

        points.append(point)

        # Derived stop-event detection:
        # emit one stop_events point when a vehicle/trip transitions away from a stop.
        if trip_id is not None and next_stop_id is not None:
            snapshot = VehicleSnapshot(
                vehicle_id=vehicle_id,
                trip_id=trip_id,
                route_id=route_id or "",
                next_stop_id=next_stop_id,
                observed_at=point_time,
                start_date=start_date,
                direction_id=direction_id,
                vehicle_label=vehicle_label,
                next_stop_sequence=next_stop_sequence,
                delay_seconds=delay_seconds,
            )

            stop_event = stop_event_tracker.process_snapshot(snapshot)
            if stop_event is not None:
                points.append(build_stop_event_point(stop_event))

    if points:
        write_api.write(bucket=bucket, org=org, record=points)