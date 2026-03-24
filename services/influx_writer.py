import os
from pathlib import Path
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from services.stop_event_state import (
    StopEventTracker,
    VehicleSnapshot,
    build_stop_event_point,
)

# Initialize Tracker
stop_event_tracker = StopEventTracker(on_time_threshold_seconds=60)

# InfluxDB Config
org = os.getenv("INFLUX_ORG", "Horseless Labs")
bucket = os.getenv("INFLUX_BUCKET", "wimbac")
influx_token = os.getenv("INFLUX_TOKEN")

if not influx_token:
    token_path = Path("influx_token.txt")
    if token_path.exists():
        influx_token = token_path.read_text().strip()

client = InfluxDBClient(url="http://localhost:8086", token=influx_token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

def safe_str(value):
    if value is None: return None
    value = str(value).strip()
    return value if value else None

def safe_int(value):
    if value is None or value == "": return None
    try: return int(value)
    except: return None

def safe_float(value):
    if value is None or value == "": return None
    try: return float(value)
    except: return None

def parse_dt(value):
    if value is None or value == "": return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except: return None

def save_to_influx(merged_data):
    points = []
    
    for item in merged_data:
        vehicle_id = safe_str(item.get("vehicle_id"))
        if not vehicle_id:
            continue

        # ALIGNMENT FIX: Pulling keys as defined in gtfs.py
        route_id = safe_str(item.get("route_id"))
        trip_id = safe_str(item.get("trip_id"))
        start_date = safe_str(item.get("start_date"))
        vehicle_label = safe_str(item.get("vehicle_label"))
        
        # Key Fix 1: next_stop_id comes from gtfs.py as 'stop_id'
        next_stop_id = safe_str(item.get("stop_id")) 
        
        # Key Fix 2: next_stop_sequence comes from gtfs.py as 'current_stop_sequence'
        next_stop_sequence = safe_int(item.get("current_stop_sequence"))
        
        delay_seconds = safe_int(item.get("delay_seconds"))
        direction_id = safe_str(item.get("direction_id"))

        lat = safe_float(item.get("lat"))
        lon = safe_float(item.get("lon"))
        bearing = safe_float(item.get("bearing"))
        speed_mps = safe_float(item.get("speed_mps"))

        vp_dt = parse_dt(item.get("vp_timestamp"))
        tu_dt = parse_dt(item.get("tu_timestamp"))
        point_time = vp_dt or tu_dt or datetime.now(timezone.utc)

        # Build Main Vehicle Status Point
        point = Point("vehicle_status").tag("vehicle_id", vehicle_id).time(point_time, WritePrecision.S)

        # Tags (for filtering)
        if route_id: point.tag("route_id", route_id)
        if trip_id: point.tag("trip_id", trip_id)
        if next_stop_id: point.tag("next_stop_id", next_stop_id)
        if start_date: point.tag("start_date", start_date)
        if direction_id: point.tag("direction_id", direction_id)
        if vehicle_label: point.tag("vehicle_label", vehicle_label)

        # Fields (for data)
        if lat is not None: point.field("lat", lat)
        if lon is not None: point.field("lon", lon)
        if bearing is not None: point.field("bearing", bearing)
        if speed_mps is not None: point.field("speed_mps", speed_mps)
        if next_stop_sequence is not None: point.field("next_stop_sequence", next_stop_sequence)
        
        # Default delay to 0 if missing to satisfy the frontend
        point.field("delay_seconds", delay_seconds if delay_seconds is not None else 0)

        points.append(point)

        # Derived stop-event detection
        if trip_id and next_stop_id:
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
            if stop_event:
                points.append(build_stop_event_point(stop_event))

    if points:
        write_api.write(bucket=bucket, org=org, record=points)
        if len(points) > 100:
            print(f"Batch written: {len(points)} points (inc. potential stop_events)")