#!/usr/bin/env python3
import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

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
        "--measurement",
        type=str,
        default="stop_events_backfill_test",
        help="Measurement name to write to (default: stop_events_backfill_test)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and count stop_events without writing them",
    )
    return parser.parse_args()


def get_client() -> InfluxDBClient:
    url = os.environ.get("INFLUX_URL", "http://localhost:8086")
    org = os.environ.get("INFLUX_ORG", "Horseless Labs")

    token = os.environ.get("INFLUX_TOKEN")
    if not token:
        token_path = Path("influx_token.txt")
        if token_path.exists():
            token = token_path.read_text().strip()

    if not token:
        raise RuntimeError("No INFLUX_TOKEN found in environment or influx_token.txt")

    return InfluxDBClient(
        url=url,
        token=token,
        org=org,
        timeout=120000,
    )


def build_flux(bucket: str, start_iso: str) -> str:
    # Only depend on columns known to exist in older data:
    # vehicle_id, route_id, next_stop_id, _time
    #
    # We intentionally do NOT require trip_id/start_date/direction_id/vehicle_label
    # in the pivot row key, because older rows may not have them.
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
      "route_id",
      "next_stop_id"
  ])
  |> pivot(
      rowKey: ["_time", "vehicle_id", "route_id", "next_stop_id"],
      columnKey: ["_field"],
      valueColumn: "_value"
  )
  |> sort(columns: ["vehicle_id", "route_id", "_time"])
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


def make_synthetic_trip_id(
    observed_at: datetime,
    vehicle_id: str,
    route_id: str,
) -> str:
    # Fallback identity for older data without trip_id.
    # Not perfect, but usually good enough to keep one vehicle's service day
    # from bleeding into the next.
    service_day = observed_at.strftime("%Y%m%d")
    return f"synthetic:{route_id}:{vehicle_id}:{service_day}"


def build_point_for_measurement(event, measurement_name: str):
    point = build_stop_event_point(event)
    # Rewrite measurement name without changing the helper module.
    point._name = measurement_name
    return point


def main():
    args = parse_args()

    bucket = os.environ.get("INFLUX_BUCKET", "wimbac")
    org = os.environ.get("INFLUX_ORG", "Horseless Labs")

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

    print(f"Backfilling {args.measurement} from vehicle_status since {start_iso}")
    print(f"Bucket: {bucket}")
    print(f"Org: {org}")
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
                observed_at = parse_record_time(record)

                vehicle_id = values.get("vehicle_id")
                route_id = values.get("route_id")
                next_stop_id = values.get("next_stop_id")

                if not vehicle_id or not route_id or not next_stop_id:
                    continue

                # Older data may not have trip_id.
                # Use a synthetic one for state tracking during backfill.
                trip_id = make_synthetic_trip_id(
                    observed_at=observed_at,
                    vehicle_id=str(vehicle_id),
                    route_id=str(route_id),
                )

                snapshot = VehicleSnapshot(
                    vehicle_id=str(vehicle_id),
                    trip_id=trip_id,
                    route_id=str(route_id),
                    next_stop_id=str(next_stop_id),
                    observed_at=observed_at,
                    start_date=None,
                    direction_id=None,
                    vehicle_label=None,
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

                derived_points.append(
                    build_point_for_measurement(stop_event, args.measurement)
                )

                if len(derived_points) >= args.batch_size:
                    write_api.write(bucket=bucket, org=org, record=derived_points)
                    events_written += len(derived_points)
                    print(f"Wrote {events_written} events so far...")
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
            print(f"Measurement:       {args.measurement}")

    finally:
        client.close()


if __name__ == "__main__":
    main()