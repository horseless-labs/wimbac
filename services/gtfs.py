from datetime import datetime, timezone

import requests
from google.protobuf.json_format import MessageToDict
from google.transit import gtfs_realtime_pb2

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
        "stop_time_updates": [
            MessageToDict(stu, preserving_proto_field_name=True)
            for stu in tu.stop_time_update
        ],
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

        tkey = trip_key_from_trip(tu.trip) if tu.HasField("trip") else ("", "")
        vkey = vehicle_key_from_desc(tu.vehicle) if tu.HasField("vehicle") else ""

        vp = None
        # Join priority: (trip_id,start_date) → vehicle_id/label fallback
        if any(tkey) and tkey in by_trip:
            vp = by_trip[tkey]
        elif vkey and vkey in by_vehicle:
            vp = by_vehicle[vkey]

        vp_dict = parse_vehicle_position(vp) if vp else {}

        merged_row = {
            "trip_id": tu_dict["trip_id"] or vp_dict.get("vp_trip_id"),
            "start_date": tu_dict["start_date"] or vp_dict.get("vp_start_date"),
            "route_id": tu_dict["route_id"] or vp_dict.get("vp_route_id"),
            "direction_id": tu_dict["direction_id"] or vp_dict.get("vp_direction_id"),

            "vehicle_id": vp_dict.get("vehicle_id") or tu_dict["tu_vehicle_id"],
            "vehicle_label": vp_dict.get("vehicle_label") or tu_dict["tu_vehicle_label"],

            "lat": vp_dict.get("lat"),
            "lon": vp_dict.get("lon"),
            "bearing": vp_dict.get("bearing"),
            "speed_mps": vp_dict.get("speed_mps"),

            "vp_timestamp": vp_dict.get("vp_timestamp"),
            "vp_timestamp_iso": vp_dict.get("vp_timestamp_iso"),
            "tu_timestamp": tu_dict["tu_timestamp"],
            "tu_timestamp_iso": tu_dict["tu_timestamp_iso"],

            "current_status": vp_dict.get("current_status"),
            "current_stop_sequence": vp_dict.get("current_stop_sequence"),
            "stop_id": vp_dict.get("stop_id"),

            "stop_time_updates": tu_dict["stop_time_updates"],
        }
        merged.append(merged_row)

    return merged

if __name__ == "__main__":
    # Use your real URLs here or import from config
    import sys
    import os

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

    from config import update_url, pos_url
    print("Running GTFS debug check...\n")

    merged = merge_trip_updates_and_positions(update_url, pos_url)

    total = len(merged)
    with_trip_id = [row for row in merged if row.get("trip_id")]
    without_trip_id = [row for row in merged if not row.get("trip_id")]

    print(f"Total merged rows: {total}")
    print(f"Rows WITH trip_id: {len(with_trip_id)}")
    print(f"Rows WITHOUT trip_id: {len(without_trip_id)}")

    print("\n--- SAMPLE WITH trip_id ---")
    if with_trip_id:
        print(with_trip_id[0])
    else:
        print("None found")

    print("\n--- SAMPLE WITHOUT trip_id ---")
    if without_trip_id:
        print(without_trip_id[0])
    else:
        print("All rows have trip_id")

    # Extra: uniqueness check
    trip_ids = [row["trip_id"] for row in with_trip_id]
    unique_ids = set(trip_ids)

    print(f"\nUnique trip_id count: {len(unique_ids)}")

    if unique_ids:
        print("Sample trip_ids:")
        print(list(unique_ids)[:10])

    print("\nDone.")