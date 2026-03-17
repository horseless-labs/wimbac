import json

from config import update_url, pos_url
from services.gtfs import merge_trip_updates_and_positions
from services.influx_writer import save_to_influx


if __name__ == "__main__":
    merged = merge_trip_updates_and_positions(update_url, pos_url)
    save_to_influx(merged)

    for row in merged[:1]:
        print(json.dumps(row, indent=2, sort_keys=True, default=str))