import csv
from pathlib import Path

STOPS_PATH = Path("data/raw/gtfs/stops.txt")

def load_stops():
    stops = []
    with STOPS_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        for r in reader:
            try:
                stops.append({
                    "stop_id": r["stop_id"],
                    "stop_code": r.get("stop_code") or "",
                    "stop_name": r.get("stop_name") or "",
                    "lat": float(r["stop_lat"]),
                    "lon": float(r["stop_lon"]),
                    "location_type": int(r.get("location_type") or 0),
                    "parent_station": r.get("parent_station") or "",
                    "wheelchair_boarding": r.get("wheelchair_boarding") or "",
                })
            except (KeyError, ValueError):
                continue
    return stops


if __name__ == '__main__':
    print(load_stops())