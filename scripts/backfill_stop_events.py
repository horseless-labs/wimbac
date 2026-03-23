#!/usr/bin/env python3
import argparse
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from services.stop_event_state import (
    StopEventTracker,
    VehicleSnapshot,
    build_stop_event_point,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backfill derived stop_events from historical vehicle_status data in day-sized chunks."
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
        "--progress-every",
        type=int,
        default=10000,
        help="Print progress every N rows within a day chunk (default: 10000)",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=1,
        help="Number of days per query chunk (default: 1)",
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


def build_count_flux(bucket: str, start_iso: str, stop_iso: str) -> str:
    return f"""
from(bucket: "{bucket}")
  |> range(start: time(v: "{start_iso}"), stop: time(v: "{stop_iso}"))
  |> filter(fn: (r) => r["_measurement"] == "vehicle_status")
  |> filter(fn: (r) => r["_field"] == "delay_seconds")
  |> filter(fn: (r) => exists r["vehicle_id"])
  |> filter(fn: (r) => exists r["route_id"])
  |> filter(fn: (r) => exists r["next_stop_id"])
  |> count()
"""


def get_total_rows(query_api, bucket: str, org: str, start_iso: str, stop_iso: str) -> int:
    flux = build_count_flux(bucket=bucket, start_iso=start_iso, stop_iso=stop_iso)
    tables = query_api.query(query=flux, org=org)

    total = 0
    for table in tables:
        for record in table.records:
            value = record.get_value()
            if value is not None:
                total += int(value)

    return total


def build_flux(bucket: str, start_iso: str, stop_iso: str) -> str:
    return f"""
from(bucket: "{bucket}")
  |> range(start: time(v: "{start_iso}"), stop: time(v: "{stop_iso}"))
  |> filter(fn: (r) => r["_measurement"] == "vehicle_status")
  |> filter(fn: (r) => r["_field"] == "delay_seconds")
  |> filter(fn: (r) => exists r["next_stop_id"])
  |> filter(fn: (r) => exists r["route_id"])
  |> filter(fn: (r) => exists r["vehicle_id"])
  |> keep(columns: [
      "_time",
      "_value",
      "vehicle_id",
      "route_id",
      "next_stop_id"
  ])
  |> sort(columns: ["_time"])
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
    service_day = observed_at.strftime("%Y%m%d")
    return f"synthetic:{route_id}:{vehicle_id}:{service_day}"


def build_point_for_measurement(event, measurement_name: str):
    point = build_stop_event_point(event)
    point._name = measurement_name
    return point


def format_eta(seconds_remaining: float) -> str:
    if seconds_remaining < 0:
        seconds_remaining = 0

    total_seconds = int(seconds_remaining)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def build_reverse_chunks(days: int, chunk_days: int) -> List[Tuple[datetime, datetime]]:
    """
    Build reverse-chronological [start, stop) windows.
    Most recent chunk comes first.
    """
    now = datetime.now(timezone.utc)
    chunks: List[Tuple[datetime, datetime]] = []

    current_stop = now
    remaining_days = days

    while remaining_days > 0:
        span = min(chunk_days, remaining_days)
        current_start = current_stop - timedelta(days=span)
        chunks.append((current_start, current_stop))
        current_stop = current_start
        remaining_days -= span

    return chunks


def main():
    args = parse_args()

    bucket = os.environ.get("INFLUX_BUCKET", "wimbac")
    org = os.environ.get("INFLUX_ORG", "Horseless Labs")

    tracker = StopEventTracker(
        on_time_threshold_seconds=args.threshold_seconds,
        stale_after_hours=12,
    )

    client = get_client()
    query_api = client.query_api()
    write_api = client.write_api(write_options=SYNCHRONOUS)

    chunks = build_reverse_chunks(days=args.days, chunk_days=args.chunk_days)

    print(f"Backfilling {args.measurement} from vehicle_status")
    print(f"Bucket: {bucket}")
    print(f"Org: {org}")
    print(f"Dry run: {args.dry_run}")
    print(f"Total lookback days: {args.days}")
    print(f"Chunk size (days): {args.chunk_days}")
    print(f"Chunk count: {len(chunks)}")
    print("Processing newest chunks first...\n")

    grand_rows_seen = 0
    grand_events_detected = 0
    grand_events_written = 0
    overall_started_at = time.time()

    try:
        for chunk_index, (chunk_start, chunk_stop) in enumerate(chunks, start=1):
            start_iso = chunk_start.isoformat()
            stop_iso = chunk_stop.isoformat()

            print(f"=== Chunk {chunk_index}/{len(chunks)} ===")
            print(f"Window: {start_iso} -> {stop_iso}")
            print("Counting total rows for chunk...")

            chunk_total_rows = get_total_rows(
                query_api=query_api,
                bucket=bucket,
                org=org,
                start_iso=start_iso,
                stop_iso=stop_iso,
            )

            print(f"Chunk rows to process: {chunk_total_rows}")

            if chunk_total_rows == 0:
                print("No rows in this chunk.\n")
                continue

            flux = build_flux(bucket=bucket, start_iso=start_iso, stop_iso=stop_iso)
            print("Querying historical snapshots for chunk...")

            tables = query_api.query(query=flux, org=org)

            chunk_rows_seen = 0
            chunk_events_detected = 0
            chunk_started_at = time.time()
            derived_points: List = []

            for table in tables:
                for record in table.records:
                    chunk_rows_seen += 1
                    grand_rows_seen += 1

                    if chunk_rows_seen % args.progress_every == 0:
                        elapsed = time.time() - chunk_started_at
                        rate = chunk_rows_seen / elapsed if elapsed > 0 else 0.0
                        pct = (chunk_rows_seen / chunk_total_rows) * 100 if chunk_total_rows > 0 else 0.0
                        remaining_rows = max(chunk_total_rows - chunk_rows_seen, 0)
                        eta_seconds = remaining_rows / rate if rate > 0 else 0

                        print(
                            f"Chunk {chunk_index}/{len(chunks)}: "
                            f"{chunk_rows_seen}/{chunk_total_rows} rows "
                            f"({pct:.2f}%) | {rate:.0f} rows/sec | ETA {format_eta(eta_seconds)}"
                        )

                    values = record.values
                    observed_at = parse_record_time(record)

                    vehicle_id = values.get("vehicle_id")
                    route_id = values.get("route_id")
                    next_stop_id = values.get("next_stop_id")

                    if not vehicle_id or not route_id or not next_stop_id:
                        continue

                    trip_id = make_synthetic_trip_id(
                        observed_at=observed_at,
                        vehicle_id=str(vehicle_id),
                        route_id=str(route_id),
                    )

                    delay_seconds = safe_int(record.get_value())

                    snapshot = VehicleSnapshot(
                        vehicle_id=str(vehicle_id),
                        trip_id=trip_id,
                        route_id=str(route_id),
                        next_stop_id=str(next_stop_id),
                        observed_at=observed_at,
                        start_date=None,
                        direction_id=None,
                        vehicle_label=None,
                        next_stop_sequence=None,
                        delay_seconds=delay_seconds,
                    )

                    stop_event = tracker.process_snapshot(snapshot)
                    if stop_event is None:
                        continue

                    chunk_events_detected += 1
                    grand_events_detected += 1

                    if args.dry_run:
                        if grand_events_detected <= 10:
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
                        grand_events_written += len(derived_points)
                        print(f"Wrote {grand_events_written} events so far...")
                        derived_points.clear()

            if not args.dry_run and derived_points:
                write_api.write(bucket=bucket, org=org, record=derived_points)
                grand_events_written += len(derived_points)
                derived_points.clear()

            chunk_elapsed = time.time() - chunk_started_at
            print(f"Chunk complete in {format_eta(chunk_elapsed)}")
            print(f"Chunk rows scanned:    {chunk_rows_seen}")
            print(f"Chunk events detected: {chunk_events_detected}\n")

        overall_elapsed = time.time() - overall_started_at

        print("Done.")
        print(f"Total rows scanned:      {grand_rows_seen}")
        print(f"Total events detected:   {grand_events_detected}")
        print(f"Total elapsed:           {format_eta(overall_elapsed)}")
        if args.dry_run:
            print("No writes performed (dry run).")
        else:
            print(f"Total events written:    {grand_events_written}")
            print(f"Measurement:             {args.measurement}")

    finally:
        client.close()


if __name__ == "__main__":
    main()