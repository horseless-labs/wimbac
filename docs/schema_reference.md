## WIMBAC InfluxDB Schema Reference (Updated 2026-03-29)

This reference defines the `vehicle_status` measurement used for real-time transit tracking and historical analysis in the WIMBAC system.

### Measurement
* **`vehicle_status`**: The primary bucket for all real-time GTFS-Realtime telemetry.

### Fields (Time-Series Values)
Fields are the actual data points being measured. In Flux, these are accessed via `r._field` and `r._value`.

* **`lat`** (float): Latitude of the vehicle.
* **`lon`** (float): Longitude of the vehicle.
* **`bearing`** (float): Direction of travel (0–359 degrees).
* **`speed_mps`** (float): Current speed in meters per second.
* **`occupancy_status`** (int/string): Current passenger load level (added for Weresense analytics).
* **`congestion_level`** (int): Local traffic delay index derived from GTFS offsets.

> **Note:** We no longer treat `trip_id` as a field. It has been migrated entirely to **Tags** to ensure consistent series identity and faster filtering.

### Tags (Indexed Metadata)
Tags are indexed dimensions used for high-performance filtering and grouping.

* **`vehicle_id`**: Persistent unique identifier for the bus hardware.
* **`vehicle_label`**: The human-readable fleet number (e.g., "3201").
* **`route_id`**: The GTFS route identifier (e.g., "55-55A").
* **`trip_id`**: **(Primary Index)** The unique GTFS trip instance identifier. 
* **`direction_id`**: Binary route direction (0 or 1).
* **`current_status`**: The vehicle's relationship to the next stop (e.g., `IN_TRANSIT_TO`, `STOPPED_AT`).
* **`stop_id`**: The identifier for the upcoming or current stop.

> **Architecture Tip:** Every unique combination of these tags creates a new **Series**. Avoid adding high-cardinality tags (like raw timestamps) here.

### Updated Common Query Patterns

**Pivot to Row-Based Format**
Since Influx stores fields separately, use this pattern to get a "Standard SQL" style row for the API:
```flux
from(bucket: "wimbac_telemetry")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "vehicle_status")
  |> pivot(rowKey:["_time", "vehicle_id"], columnKey: ["_field"], valueColumn: "_value")
```

**Filter by Active Trip**
```flux
|> filter(fn: (r) => r.trip_id == "9876543")
|> filter(fn: (r) => r._field == "speed_mps")
```

### Mental Model: The "Series" Concept


* **Data is a Stream:** Think of each `vehicle_id` + `trip_id` as a single ribbon of data moving through time.
* **The Pivot is Key:** Until you `pivot()`, your latitude and longitude are technically in two different tables. 
* **Tag vs Field:** If you need to `group()` by it (like showing all buses on Route 22), it **must** be a Tag.