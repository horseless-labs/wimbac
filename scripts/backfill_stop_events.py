#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from services.stop_event_state import (
    StopEventTracker,
    VehicleSnapshot,
    build_stop_event_point,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backfill derived stop_events from historical vehicle_status data."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="How many days back to scan (default: 30)",
    )
    parser.add_argument(
        "--threshold-seconds",
        type=int,
        default=60,
        help="On-time threshold in seconds (default: 60)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="How many derived stop_events to buffer before writing (default: 5000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and count stop_events without writing them",
    )
    return parser.parse_args()


def get_client() -> InfluxDBClient:
    url = os.environ.get("INFLUX_URL", "http://localhost:8086")
    org = os.getenv("INFLUX_ORG", "Horseless Labs")
    bucket = os.getenv("INFLUX_BUCKET", "wimbac")

    influx_token = os.getenv("INFLUX_TOKEN")
    if influx_token:
        print(f"Using token from Environment (starts with: {influx_token[:5]}...)")
    else:
        token_path = Path("../influx_token.txt")
        if token_path.exists():
            influx_token = token_path.read_text().strip()
            print(f"Using token from File (starts with: {influx_token[:5]}...)")

    return InfluxDBClient(
        url=url,
        token=influx_token,
        org=org,
        timeout=120000,
    )


def build_flux(bucket: str, start_iso: str) -> str:
    # We only need:
    # - tags: vehicle_id, trip_id, route_id, next_stop_id, start_date, direction_id, vehicle_label
    # - fields: delay_seconds, next_stop_sequence
    #
    # Pivot turns separate field rows into one snapshot row per timestamp/tag combo.
    return f"""
from(bucket: "{bucket}")
  |> range(start: time(v: "{start_iso}"))
  |> filter(fn: (r) => r["_measurement"] == "vehicle_status")
  |> filter(fn: (r) => r["_field"] == "delay_seconds" or r["_field"] == "next_stop_sequence")
  |> keep(columns: [
      "_time",
      "_field",
      "_value",
      "vehicle_id",
      "trip_id",
      "route_id",
      "next_stop_id",
      "start_date",
      "direction_id",
      "vehicle_label"
  ])
  |> pivot(
      rowKey: ["_time", "vehicle_id", "trip_id", "route_id", "next_stop_id", "start_date", "direction_id", "vehicle_label"],
      columnKey: ["_field"],
      valueColumn: "_value"
  )
  |> sort(columns: ["vehicle_id", "trip_id", "start_date", "_time"])
"""


def parse_record_time(record) -> datetime:
    dt = record.get_time()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def safe_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def main():
    args = parse_args()

    # bucket = os.environ["INFLUX_BUCKET"]
    # org = os.environ["INFLUX_ORG"]
    org = os.getenv("INFLUX_ORG", "Horseless Labs")
    bucket = os.getenv("INFLUX_BUCKET", "wimbac")

    start_dt = datetime.now(timezone.utc) - timedelta(days=args.days)
    start_iso = start_dt.isoformat()

    tracker = StopEventTracker(
        on_time_threshold_seconds=args.threshold_seconds,
        stale_after_hours=12,
    )

    client = get_client()
    query_api = client.query_api()
    write_api = client.write_api(write_options=SYNCHRONOUS)

    flux = build_flux(bucket=bucket, start_iso=start_iso)

    print(f"Backfilling stop_events from vehicle_status since {start_iso}")
    print(f"Bucket: {bucket}")
    print(f"Dry run: {args.dry_run}")
    print("Querying historical snapshots...")

    tables = query_api.query(query=flux, org=org)

    derived_points: List = []
    rows_seen = 0
    events_detected = 0
    events_written = 0

    try:
        for table in tables:
            for record in table.records:
                rows_seen += 1

                values = record.values

                vehicle_id = values.get("vehicle_id")
                trip_id = values.get("trip_id")
                next_stop_id = values.get("next_stop_id")
                route_id = values.get("route_id")

                if not vehicle_id or not trip_id or not next_stop_id:
                    continue

                snapshot = VehicleSnapshot(
                    vehicle_id=str(vehicle_id),
                    trip_id=str(trip_id),
                    route_id=str(route_id) if route_id is not None else "",
                    next_stop_id=str(next_stop_id),
                    observed_at=parse_record_time(record),
                    start_date=str(values.get("start_date")) if values.get("start_date") not in (None, "") else None,
                    direction_id=str(values.get("direction_id")) if values.get("direction_id") not in (None, "") else None,
                    vehicle_label=str(values.get("vehicle_label")) if values.get("vehicle_label") not in (None, "") else None,
                    next_stop_sequence=safe_int(values.get("next_stop_sequence")),
                    delay_seconds=safe_int(values.get("delay_seconds")),
                )

                stop_event = tracker.process_snapshot(snapshot)
                if stop_event is None:
                    continue

                events_detected += 1

                if args.dry_run:
                    if events_detected <= 10:
                        print(
                            f"[sample event] stop_id={stop_event.stop_id} "
                            f"route_id={stop_event.route_id} "
                            f"trip_id={stop_event.trip_id} "
                            f"vehicle_id={stop_event.vehicle_id} "
                            f"delay={stop_event.delay_seconds} "
                            f"time={stop_event.observed_at.isoformat()}"
                        )
                    continue

                derived_points.append(build_stop_event_point(stop_event))

                if len(derived_points) >= args.batch_size:
                    write_api.write(bucket=bucket, org=org, record=derived_points)
                    events_written += len(derived_points)
                    print(f"Wrote {events_written} stop_events so far...")
                    derived_points.clear()

        if not args.dry_run and derived_points:
            write_api.write(bucket=bucket, org=org, record=derived_points)
            events_written += len(derived_points)
            derived_points.clear()

        print("\nDone.")
        print(f"Rows scanned:      {rows_seen}")
        print(f"Events detected:   {events_detected}")
        if args.dry_run:
            print("No writes performed (dry run).")
        else:
            print(f"Events written:    {events_written}")

    finally:
        client.close()


if __name__ == "__main__":
    main()