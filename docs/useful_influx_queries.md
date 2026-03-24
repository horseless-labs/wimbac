## Ingestion health

### Recent data exists (cleaned)

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -2m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> keep(columns: ["_time", "_field", "_value", "vehicle_id"])
  |> rename(columns: {
      _time: "timestamp",
      _field: "metric",
      _value: "metric_value"
  })
  |> sort(columns: ["timestamp"], desc: true)
  |> limit(n: 20)
'
```

---

### Total points (last 2 min)

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -2m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> group()
  |> count()
  |> sum()
  |> rename(columns: { _value: "total_points_last_2m" })
'
```

---

### Recent ingestion volume

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> count()
  |> rename(columns: { _value: "points_per_series_last_10m" })
'
```

---

### Detect ingestion gaps

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -30m)
  |> aggregateWindow(every: 1m, fn: count, createEmpty: true)
  |> rename(columns: {
      _time: "minute_bucket",
      _value: "points_in_minute"
  })
'
```

---

## System state

### Latest datapoint per vehicle (cleaned)

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> group(columns: ["vehicle_id"])
  |> last()
  |> rename(columns: {
      _time: "timestamp",
      _value: "value",
      _field: "metric"
  })
'
```

---

### Vehicles per route (this one benefits a LOT from naming)

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -15m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> group(columns: ["route_id"])
  |> distinct(column: "vehicle_id")
  |> count()
  |> rename(columns: {
      route_id: "route",
      _value: "vehicle_count"
  })
'
```

---

## Distribution weirdness

### Records per vehicle

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> group(columns: ["vehicle_id"])
  |> count()
  |> rename(columns: {
      vehicle_id: "vehicle",
      _value: "records_in_window"
  })
'
```

---

### Distinct vehicles seen

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -15m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> keep(columns: ["vehicle_id"])
  |> distinct(column: "vehicle_id")
  |> rename(columns: { vehicle_id: "active_vehicle_id" })
'
```

---

## Pivoted views (already good, just polish timestamp)

You were already close to ideal here. Just normalize naming:

```bash
|> rename(columns: { _time: "timestamp" })
```

That’s honestly enough once pivoted.

---

## Schema checks

### Fields present

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> keep(columns: ["_field"])
  |> distinct(column: "_field")
  |> rename(columns: { _field: "field_name" })
'
```

---

### Trip ID check

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> filter(fn: (r) => r._field == "trip_id")
  |> rename(columns: {
      _time: "timestamp",
      _value: "trip_id"
  })
  |> limit(n: 10)
'
```

---

## Time analytics

### 1-minute buckets

```bash
influx query '
from(bucket: "wimbac")
  |> range(start: -1h)
  |> aggregateWindow(every: 1m, fn: count, createEmpty: false)
  |> rename(columns: {
      _time: "minute",
      _value: "points_in_minute"
  })
'
```

Clean names
```flux
|> rename(columns: {
  _time: "timestamp",
  _value: "value",
  _field: "metric"
})
```

Or after aggregation:

```flux
|> rename(columns: { _value: "record_count" })
```
