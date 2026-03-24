## WIMBAC Influx Schema Reference

This section lists the key fields and tags available in the `vehicle_status` measurement for use in Flux queries.

### Measurement

* `vehicle_status`
  Primary time-series dataset containing vehicle telemetry and GTFS-derived metadata.

---

### Fields (values stored over time)

Fields are accessed via `_field` and `_value`, or via `pivot()`.

* `lat` — latitude (float)
* `lon` — longitude (float)
* `bearing` — direction of travel in degrees (float)
* `speed_mps` — vehicle speed in meters per second (float)
* `trip_id` — GTFS trip identifier (string, sometimes treated as field depending on ingestion)

Notes:

* Each field is stored as a separate time-series.
* Multiple fields at the same timestamp require `pivot()` to reconstruct a full “row.”

---

### Tags (indexed dimensions for filtering/grouping)

Tags define series identity and are used in `filter()` and `group()`.

* `vehicle_id` — unique vehicle identifier (string)
* `vehicle_label` — human-readable vehicle number (string)
* `route_id` — transit route identifier (string)
* `trip_id` — GTFS trip identifier (string)
* `direction_id` — route direction (string/int, GTFS-specific)
* `start_date` — service date in `YYYYMMDD` format (string)
* `next_stop_id` — upcoming stop identifier (string) *(if present in ingestion)*

Notes:

* A **unique combination of tags + field = one time-series (series)**.
* Adding more tags increases series cardinality and affects query behavior.

---

### Special Columns (Flux system columns)

These exist on every record:

* `_time` — timestamp of the datapoint
* `_measurement` — measurement name (`vehicle_status`)
* `_field` — field name (e.g., `lat`, `speed_mps`)
* `_value` — field value
* `_start`, `_stop` — query time bounds

---

### Common Query Patterns

**Filter by tag**

```flux
|> filter(fn: (r) => r.vehicle_id == "4058")
```

**Filter by field**

```flux
|> filter(fn: (r) => r._field == "lat")
```

**Group by tag**

```flux
|> group(columns: ["route_id"])
```

**Reconstruct full records**

```flux
|> pivot(
    rowKey: ["_time"],
    columnKey: ["_field"],
    valueColumn: "_value"
)
```

---

### Mental Model (important)

* Data is stored as **time-series, not rows**
* Each `(field + tag set)` = its own series
* Queries operate on **tables of series**, not a single table

If output looks duplicated or fragmented, it is usually due to:

* multiple series being returned
* missing `group()` or `pivot()`

---

If you want, next step I’d strongly recommend is adding a tiny section right after this:

> “Common mistakes / gotchas”

Because you’ve already hit like 3 of the classic ones (and you’ll hit them again at 2am otherwise).
