import os
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
    points = []

    for row in merged_data:
        vehicle_id = _safe_str(row.get("vehicle_id"))
        route_id = _safe_str(row.get("route_id"))

        # These are the minimum tags that make the data analytically useful.
        point = Point("vehicle_status")

        if vehicle_id:
            point = point.tag("vehicle_id", vehicle_id)
        if route_id:
            point = point.tag("route_id", route_id)

        trip_id = _safe_str(row.get("trip_id"))
        if trip_id:
            point = point.tag("trip_id", trip_id)

        direction_id = row.get("direction_id")
        if direction_id is not None and direction_id != "":
            point = point.tag("direction_id", str(direction_id))

        start_date = _safe_str(row.get("start_date"))
        if start_date:
            point = point.tag("start_date", start_date)

        vehicle_label = _safe_str(row.get("vehicle_label"))
        if vehicle_label:
            point = point.tag("vehicle_label", vehicle_label)

        stop_id = _safe_str(row.get("stop_id"))
        if stop_id:
            point = point.tag("stop_id", stop_id)

        lat = _safe_float(row.get("lat"))
        lon = _safe_float(row.get("lon"))
        if lat is not None:
            point = point.field("lat", lat)
        if lon is not None:
            point = point.field("lon", lon)

        bearing = _safe_float(row.get("bearing"))
        if bearing is not None:
            point = point.field("bearing", bearing)

        speed_mps = _safe_float(row.get("speed_mps"))
        if speed_mps is not None:
            point = point.field("speed_mps", speed_mps)

        current_status = row.get("current_status")
        if current_status is not None and current_status != "":
            point = point.field("current_status", int(current_status))

        current_stop_sequence = _safe_int(row.get("current_stop_sequence"))
        if current_stop_sequence is not None:
            point = point.field("current_stop_sequence", current_stop_sequence)

        vp_timestamp = _safe_int(row.get("vp_timestamp"))
        if vp_timestamp is not None:
            point = point.field("vp_timestamp", vp_timestamp)

        tu_timestamp = _safe_int(row.get("tu_timestamp"))
        if tu_timestamp is not None:
            point = point.field("tu_timestamp", tu_timestamp)

        stop_time_updates = row.get("stop_time_updates") or []
        if stop_time_updates:
            first_update = stop_time_updates[0]

            delay = (
                first_update.get("arrival", {}).get("delay")
                or first_update.get("departure", {}).get("delay")
            )
            delay = _safe_int(delay)
            if delay is not None:
                point = point.field("delay_seconds", delay)

            next_stop_id = _safe_str(first_update.get("stop_id"))
            if next_stop_id:
                point = point.tag("next_stop_id", next_stop_id)

            next_stop_sequence = _safe_int(first_update.get("stop_sequence"))
            if next_stop_sequence is not None:
                point = point.field("next_stop_sequence", next_stop_sequence)

            scheduled_arrival = _safe_int(first_update.get("arrival", {}).get("time"))
            if scheduled_arrival is not None:
                point = point.field("scheduled_arrival_time", scheduled_arrival)

            scheduled_departure = _safe_int(first_update.get("departure", {}).get("time"))
            if scheduled_departure is not None:
                point = point.field("scheduled_departure_time", scheduled_departure)

        # Prefer feed timestamps over write time so analytics reflect observed event time.
        point_time = vp_timestamp or tu_timestamp
        if point_time is not None:
            point = point.time(point_time, WritePrecision.S)
        else:
            # Fallback if neither feed timestamp exists
            point = point.time(_safe_int(__import__("time").time()), WritePrecision.S)

        points.append(point)

    if points:
        write_api.write(bucket=bucket, org=org, record=points)