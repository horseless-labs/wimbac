from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

import requests
from datetime import datetime, timezone

import json

# Endpoint to check
pos_url = "https://gtfs-rt.gcrta.vontascloud.com/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb"
update_url = "https://gtfs-rt.gcrta.vontascloud.com/TMGTFSRealTimeWebService/TripUpdate/TripUpdates.pb"
alert_url = "https://gtfs-rt.gcrta.vontascloud.com/TMGTFSRealTimeWebService/Alert/Alerts.pb"

# InfluxDB stuff
with open("influx_token.txt") as f:
    influx_token = f.read().strip()

org = "Horseless Labs"
bucket = "wimbac"
client = InfluxDBClient(url="http://localhost:8086", token=influx_token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

# TODO: add headers and retries to solve potential ConnectionResetErrors
def load_feed(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed

def trip_key_from_trip(trip):
    # (trip_id, start_date) to avoid collisions or interlined trips
    trip_id = getattr(trip, "trip_id", "") or ""
    start_date = getattr(trip, "start_date", "") or ""
    return (trip_id, start_date)

def vehicle_key_from_desc(desc):
    vid = getattr(desc, "id", "") or ""
    vlabel = getattr(desc, "label", "") or ""
    return vid or vlabel or ""

def to_iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None

def index_vehicle_positions(pos_feed):
    """
    Return two indices:
     - by_trip[(trip_id, start_date)] -> VehiclePosition
     - by_vehicle[vehicle_key] -> VehiclePosition
    """

    by_trip, by_vehicle = {}, {}
    for e in pos_feed.entity:
        if not e.HasField("vehicle"):
            continue

        vp = e.vehicle
        tkey = trip_key_from_trip(vp.trip) if vp.HasField("trip") else ("", "")
        vkey = vehicle_key_from_desc(vp.vehicle) if vp.HasField("vehicle") else ""

        if any(tkey):
            by_trip[tkey] = vp
        if vkey:
            by_vehicle[vkey] = vp
    return by_trip, by_vehicle


def parse_trip_update(tu):
    """Flatten the parts of a TripUpdate we care about into a dict."""
    trip = tu.trip if tu.HasField("trip") else None
    vdesc = tu.vehicle if tu.HasField("vehicle") else None
    d = {
        "trip_id": getattr(trip, "trip_id", None) if trip else None,
        "route_id": getattr(trip, "route_id", None) if trip else None,
        "direction_id": getattr(trip, "direction_id", None) if trip else None,
        "start_date": getattr(trip, "start_date", None) if trip else None,
        "start_time": getattr(trip, "start_time", None) if trip else None,
        "tu_timestamp": getattr(tu, "timestamp", None),
        "tu_timestamp_iso": to_iso(getattr(tu, "timestamp", 0) or 0),
        "tu_vehicle_id": getattr(vdesc, "id", None) if vdesc else None,
        "tu_vehicle_label": getattr(vdesc, "label", None) if vdesc else None,
        # keep stop_time_updates if you want them downstream
        "stop_time_updates": [MessageToDict(stu, preserving_proto_field_name=True)
                              for stu in tu.stop_time_update],
    }
    return d

def parse_vehicle_position(vp):
    """Flatten VehiclePosition into a dict."""
    trip = vp.trip if vp.HasField("trip") else None
    pos = vp.position if vp.HasField("position") else None
    vdesc = vp.vehicle if vp.HasField("vehicle") else None
    d = {
        "vp_trip_id": getattr(trip, "trip_id", None) if trip else None,
        "vp_start_date": getattr(trip, "start_date", None) if trip else None,
        "vp_route_id": getattr(trip, "route_id", None) if trip else None,
        "vp_direction_id": getattr(trip, "direction_id", None) if trip else None,
        "vehicle_id": getattr(vdesc, "id", None) if vdesc else None,
        "vehicle_label": getattr(vdesc, "label", None) if vdesc else None,
        "lat": getattr(pos, "latitude", None) if pos else None,
        "lon": getattr(pos, "longitude", None) if pos else None,
        "bearing": getattr(pos, "bearing", None) if pos else None,
        "speed_mps": getattr(pos, "speed", None) if pos else None,
        "vp_timestamp": getattr(vp, "timestamp", None),
        "vp_timestamp_iso": to_iso(getattr(vp, "timestamp", 0) or 0),
        "current_status": getattr(vp, "current_status", None) if vp.HasField("current_status") else None,
        "current_stop_sequence": getattr(vp, "current_stop_sequence", None) if vp.HasField("current_stop_sequence") else None,
        "stop_id": getattr(vp, "stop_id", None) if vp.HasField("stop_id") else None,
    }
    return d

def merge_trip_updates_and_positions(update_url, pos_url):
    upd_feed = load_feed(update_url)
    pos_feed = load_feed(pos_url)

    by_trip, by_vehicle = index_vehicle_positions(pos_feed)

    merged = []
    for e in upd_feed.entity:
        if not e.HasField("trip_update"):
            continue
        tu = e.trip_update
        tu_dict = parse_trip_update(tu)

        tkey = trip_key_from_trip(tu.trip) if tu.HasField("trip") else ("","")
        vkey = vehicle_key_from_desc(tu.vehicle) if tu.HasField("vehicle") else ""

        vp = None
        # Join priority: (trip_id,start_date) → vehicle_id/label fallback
        if any(tkey) and tkey in by_trip:
            vp = by_trip[tkey]
        elif vkey and vkey in by_vehicle:
            vp = by_vehicle[vkey]

        vp_dict = parse_vehicle_position(vp) if vp else {}

        # Merge with preference: TU trip fields, VP vehicle/position fields
        merged_row = {
            # Trip identity (prefer TU)
            "trip_id": tu_dict["trip_id"] or vp_dict.get("vp_trip_id"),
            "start_date": tu_dict["start_date"] or vp_dict.get("vp_start_date"),
            "route_id": tu_dict["route_id"] or vp_dict.get("vp_route_id"),
            "direction_id": tu_dict["direction_id"] or vp_dict.get("vp_direction_id"),

            # Vehicle identity (prefer VP.id, then VP.label, then TU)
            "vehicle_id": vp_dict.get("vehicle_id") or tu_dict["tu_vehicle_id"],
            "vehicle_label": vp_dict.get("vehicle_label") or tu_dict["tu_vehicle_label"],

            # Position (from VP only)
            "lat": vp_dict.get("lat"),
            "lon": vp_dict.get("lon"),
            "bearing": vp_dict.get("bearing"),
            "speed_mps": vp_dict.get("speed_mps"),

            # Timestamps for traceability
            "vp_timestamp": vp_dict.get("vp_timestamp"),
            "vp_timestamp_iso": vp_dict.get("vp_timestamp_iso"),
            "tu_timestamp": tu_dict["tu_timestamp"],
            "tu_timestamp_iso": tu_dict["tu_timestamp_iso"],

            # Optional extras
            "current_status": vp_dict.get("current_status"),
            "current_stop_sequence": vp_dict.get("current_stop_sequence"),
            "stop_id": vp_dict.get("stop_id"),

            # Keep stop_time_updates if you need prediction details
            "stop_time_updates": tu_dict["stop_time_updates"],
        }
        merged.append(merged_row)

    return merged

def save_to_influx(merged_data):
    points = []
    for row in merged_data:
        # Vehicle data
        point = Point("vehicle_status") \
            .tag("vehicle_id", row["vehicle_id"]) \
            .tag("route_id", row["route_id"]) \
            .field("lat", float(row["lat"]) if row["lat"] else 0.0) \
            .field("lon", float(row["lon"]) if row["lon"] else 0.0) \
            .time(datetime.now(timezone.utc), WritePrecision.NS)

        # 2. Add delay from the first relevant StopTimeUpdate
        if row["stop_time_updates"]:
            first_update = row["stop_time_updates"][0]
            # Capture the delay (usually in seconds) if provided
            delay = first_update.get("arrival", {}).get("delay") or \
                    first_update.get("departure", {}).get("delay", 0)
            point.field("delay_seconds", int(delay))
            point.tag("next_stop_id", first_update.get("stop_id"))

        points.append(point)
    
    write_api.write(bucket=bucket, org=org, record=points)

if __name__ == '__main__':
    merged = merge_trip_updates_and_positions(update_url, pos_url)
    save_to_influx(merged)
    # Only output a single updated line (they are quite long)
    for row in merged[:1]:
        print(json.dumps(row, indent=2, sort_keys=True, default=str))