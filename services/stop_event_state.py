from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from influxdb_client import Point, WritePrecision


@dataclass
class VehicleSnapshot:
    vehicle_id: str
    trip_id: str
    route_id: str
    next_stop_id: str
    observed_at: datetime

    start_date: Optional[str] = None
    direction_id: Optional[str] = None
    vehicle_label: Optional[str] = None
    next_stop_sequence: Optional[int] = None
    delay_seconds: Optional[int] = None


@dataclass
class StopEvent:
    stop_id: str
    trip_id: str
    route_id: str
    vehicle_id: str
    observed_at: datetime

    start_date: Optional[str] = None
    direction_id: Optional[str] = None
    vehicle_label: Optional[str] = None
    stop_sequence: Optional[int] = None
    delay_seconds: Optional[int] = None
    on_time: Optional[int] = None


class StopEventTracker:
    """
    Detects stop events by tracking transitions in next_stop_id.

    Core idea:
    - If a vehicle/trip was previously approaching stop A
    - and is now approaching stop B
    - then we infer it has just served stop A

    This emits one derived stop event per detected transition.
    """

    def __init__(
        self,
        on_time_threshold_seconds: int = 60,
        stale_after_hours: int = 8,
    ) -> None:
        self.on_time_threshold_seconds = on_time_threshold_seconds
        self.stale_after = timedelta(hours=stale_after_hours)

        self._last_snapshot: Dict[Tuple[str, str, str], VehicleSnapshot] = {}
        self._last_emitted_stop: Dict[Tuple[str, str, str], str] = {}

    def _key(self, snapshot: VehicleSnapshot) -> Tuple[str, str, str]:
        return (
            snapshot.vehicle_id or "",
            snapshot.trip_id or "",
            snapshot.start_date or "",
        )

    def prune_stale_state(self, now: Optional[datetime] = None) -> None:
        if now is None:
            now = datetime.now(timezone.utc)

        dead_keys = []
        for key, snapshot in self._last_snapshot.items():
            age = now - snapshot.observed_at
            if age > self.stale_after:
                dead_keys.append(key)

        for key in dead_keys:
            self._last_snapshot.pop(key, None)
            self._last_emitted_stop.pop(key, None)

    def process_snapshot(self, snapshot: VehicleSnapshot) -> Optional[StopEvent]:
        """
        Feed one normalized vehicle snapshot into the tracker.

        Returns:
            StopEvent if a stop transition was detected, else None.
        """
        if not snapshot.vehicle_id or not snapshot.trip_id or not snapshot.next_stop_id:
            return None

        if snapshot.observed_at.tzinfo is None:
            snapshot.observed_at = snapshot.observed_at.replace(tzinfo=timezone.utc)

        self.prune_stale_state(snapshot.observed_at)

        key = self._key(snapshot)
        previous = self._last_snapshot.get(key)
        self._last_snapshot[key] = snapshot

        if previous is None:
            return None

        if not previous.next_stop_id:
            return None

        # No transition, still approaching same stop.
        if previous.next_stop_id == snapshot.next_stop_id:
            return None

        # Optional sanity check:
        # if stop sequence is available and did not advance, ignore noisy reversals.
        if (
            previous.next_stop_sequence is not None
            and snapshot.next_stop_sequence is not None
            and snapshot.next_stop_sequence <= previous.next_stop_sequence
        ):
            return None

        # Dedupe: avoid emitting the same stop twice for the same vehicle/trip/start_date.
        last_emitted = self._last_emitted_stop.get(key)
        if last_emitted == previous.next_stop_id:
            return None

        delay_seconds = (
            previous.delay_seconds
            if previous.delay_seconds is not None
            else snapshot.delay_seconds
        )

        on_time = None
        if delay_seconds is not None:
            on_time = int(abs(delay_seconds) <= self.on_time_threshold_seconds)

        event = StopEvent(
            stop_id=previous.next_stop_id,
            trip_id=previous.trip_id,
            route_id=previous.route_id,
            vehicle_id=previous.vehicle_id,
            observed_at=snapshot.observed_at,  # event detected at the transition time
            start_date=previous.start_date,
            direction_id=previous.direction_id,
            vehicle_label=previous.vehicle_label,
            stop_sequence=previous.next_stop_sequence,
            delay_seconds=delay_seconds,
            on_time=on_time,
        )

        self._last_emitted_stop[key] = previous.next_stop_id
        return event


def build_stop_event_point(event: StopEvent) -> Point:
    point = (
        Point("stop_events")
        .tag("stop_id", event.stop_id)
        .tag("trip_id", event.trip_id)
        .tag("route_id", event.route_id)
        .tag("vehicle_id", event.vehicle_id)
        .time(event.observed_at, WritePrecision.S)
    )

    if event.start_date:
        point = point.tag("start_date", event.start_date)
    if event.direction_id:
        point = point.tag("direction_id", str(event.direction_id))
    if event.vehicle_label:
        point = point.tag("vehicle_label", event.vehicle_label)
    if event.stop_sequence is not None:
        point = point.field("stop_sequence", int(event.stop_sequence))
    if event.delay_seconds is not None:
        point = point.field("delay_seconds", int(event.delay_seconds))
    if event.on_time is not None:
        point = point.field("on_time", int(event.on_time))

    return point