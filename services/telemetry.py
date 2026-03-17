import os
import time
import math
import threading
from collections import defaultdict, deque
from typing import Any, Dict, Optional


class Telemetry:
    """
    In-process telemetry store for WIMBAC.

    Notes:
    - This is per-process memory. Under Gunicorn with multiple workers,
      each worker will keep its own telemetry. That's okay for now for
      a portfolio project and early observability.
    - If you later want global aggregation, push these metrics into
      InfluxDB, Prometheus, Redis, or a shared backend.
    """

    def __init__(self, max_latency_samples: int = 5000):
        self._lock = threading.Lock()
        self.start_time = time.time()

        self.total_requests = 0
        self.total_errors = 0

        self.endpoint_counts = defaultdict(int)
        self.endpoint_errors = defaultdict(int)

        self.latency_samples = deque(maxlen=max_latency_samples)
        self.endpoint_latencies = defaultdict(lambda: deque(maxlen=max_latency_samples))

        self.cache_hits = 0
        self.cache_misses = 0

        self.gtfs_fetch_success = 0
        self.gtfs_fetch_failure = 0
        self.last_gtfs_refresh_ts: Optional[float] = None
        self.last_gtfs_error: Optional[str] = None

        self.cache_last_update_ts: Optional[float] = None
        self.cache_item_count: int = 0

    def record_request(self, endpoint: str, duration_ms: float, status_code: int) -> None:
        with self._lock:
            self.total_requests += 1
            self.endpoint_counts[endpoint] += 1
            self.latency_samples.append(duration_ms)
            self.endpoint_latencies[endpoint].append(duration_ms)

            if status_code >= 400:
                self.total_errors += 1
                self.endpoint_errors[endpoint] += 1

    def record_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def update_cache_state(self, item_count: int, updated_ts: Optional[float] = None) -> None:
        with self._lock:
            self.cache_item_count = item_count
            self.cache_last_update_ts = updated_ts if updated_ts is not None else time.time()

    def record_gtfs_fetch_success(self) -> None:
        with self._lock:
            self.gtfs_fetch_success += 1
            self.last_gtfs_refresh_ts = time.time()
            self.last_gtfs_error = None

    def record_gtfs_fetch_failure(self, error_message: str) -> None:
        with self._lock:
            self.gtfs_fetch_failure += 1
            self.last_gtfs_error = error_message

    def _percentile(self, values, pct: float) -> Optional[float]:
        if not values:
            return None
        if len(values) == 1:
            return float(values[0])

        sorted_vals = sorted(values)
        idx = (len(sorted_vals) - 1) * pct
        lower = math.floor(idx)
        upper = math.ceil(idx)

        if lower == upper:
            return float(sorted_vals[int(idx)])

        lower_val = sorted_vals[lower]
        upper_val = sorted_vals[upper]
        frac = idx - lower
        return float(lower_val + (upper_val - lower_val) * frac)

    def _latency_summary(self, values) -> Dict[str, Optional[float]]:
        if not values:
            return {
                "avg_ms": None,
                "min_ms": None,
                "max_ms": None,
                "p95_ms": None,
                "p99_ms": None,
            }

        vals = list(values)
        return {
            "avg_ms": round(sum(vals) / len(vals), 3),
            "min_ms": round(min(vals), 3),
            "max_ms": round(max(vals), 3),
            "p95_ms": round(self._percentile(vals, 0.95), 3),
            "p99_ms": round(self._percentile(vals, 0.99), 3),
        }

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime_sec = round(time.time() - self.start_time, 3)
            cache_total = self.cache_hits + self.cache_misses
            cache_hit_rate = (self.cache_hits / cache_total) if cache_total > 0 else None

            endpoint_metrics = {}
            for endpoint, count in self.endpoint_counts.items():
                endpoint_metrics[endpoint] = {
                    "requests": count,
                    "errors": self.endpoint_errors.get(endpoint, 0),
                    "latency": self._latency_summary(self.endpoint_latencies[endpoint]),
                }

            now = time.time()
            cache_age_sec = (
                round(now - self.cache_last_update_ts, 3)
                if self.cache_last_update_ts is not None
                else None
            )
            gtfs_refresh_age_sec = (
                round(now - self.last_gtfs_refresh_ts, 3)
                if self.last_gtfs_refresh_ts is not None
                else None
            )

            return {
                "service": {
                    "name": os.getenv("APP_NAME", "wimbac"),
                    "environment": os.getenv("APP_ENV", "production"),
                    "uptime_sec": uptime_sec,
                },
                "requests": {
                    "total": self.total_requests,
                    "errors": self.total_errors,
                    "latency": self._latency_summary(self.latency_samples),
                },
                "cache": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_rate": round(cache_hit_rate, 4) if cache_hit_rate is not None else None,
                    "item_count": self.cache_item_count,
                    "last_update_ts": self.cache_last_update_ts,
                    "age_sec": cache_age_sec,
                },
                "gtfs": {
                    "fetch_success": self.gtfs_fetch_success,
                    "fetch_failure": self.gtfs_fetch_failure,
                    "last_refresh_ts": self.last_gtfs_refresh_ts,
                    "refresh_age_sec": gtfs_refresh_age_sec,
                    "last_error": self.last_gtfs_error,
                },
                "endpoints": endpoint_metrics,
            }


telemetry = Telemetry()