# WIMBAC

**Web-Integrated Monitoring of Bus Activity in Cleveland**

WIMBAC is a lightweight real-time transit monitoring system that ingests GTFS-Realtime feeds, stores vehicle telemetry in InfluxDB, and exposes a web interface for exploring bus activity across Cleveland. Check it out at [WIMBAC](http://www.wimbac.com).

The project was built as an end-to-end exercise in data ingestion, time-series storage, backend API design, and production deployment.

# Overview

WIMBAC collects real-time transit feeds and exposes them through a backend API and map interface.

Core features:

- Real-time (20-30s intervals) ingestion of GTFS-Realtime feeds
- Storage of vehicle location data in a time-series database
- Query API for spatial proximity searches
- Web visualization using Leaflet
- Production deployment using Gunicorn + Nginx

The system currently runs on a low-cost VPS to explore how far a minimal infrastructure stack can scale before additional complexity is required.

# System Architecture

GTFS-Realtime Feeds -> ingestion pipeline -> InfluxDB -> Flask -> nginx + Gunicorn -> Leaflet

Each layer has a narrow responsibility:

| Layer              | Role                                            |
| ------------------ | ----------------------------------------------- |
| **Ingestion**      | Pull GTFS-RT feeds and normalize vehicle data   |
| **Storage**        | Persist vehicle telemetry as time-series points |
| **API**            | Query vehicles near a location                  |
| **Frontend**       | Display real-time map data                      |
| **Infrastructure** | Serve the application reliably                  |

This separation makes the system easier to extend and scale.

# Technology Stack

Backend:
- Python
- Flask
- InfluxDB (time-series database)

Frontend:
- Leaflet.js
- Vanilla JavaScript

Infrastructure:

- Debian 13 VPS
- Gunicorn
- Nginx
- systemd service management (may dockerize in the futre)

# Data Ingestion

WIMBAC ingests GTFS-Realtime feeds provided by the [Greater Cleveland Regional Transit Authority's data links](https://www.riderta.com/developers?tab=multi-section-tab3). WIMBAC currently merges Vehicle Positions and Trip Updates, which provide the following information:

| Feed              | Data                  |
| ----------------- | --------------------- |
| Vehicle Positions | latitude, longitude   |
| Trip Updates      | route, stop, schedule |

The ingestion process merges them to produce normalized vehicle objects.

Example normalized record:

```
{
  vehicle_id
  route_id
  next_stop_id
  lat
  lon
  timestamp
}
```

# Time-Series Storage

Vehicle telemetry is stored in InfluxDB, which was chosen because:

* Vehicle telemetry is time-series data
* Queries frequently involve recent windows
* High ingestion throughput is supported
* Built-in retention and aggregation capabilities

There's ongoing thought as to whether `next_stop_id` should be a tag or a
field, but this this the current structure:

```
measurement: vehicle_status

tags:
  vehicle_id
  route_id
  next_stop_id

fields:
  lat
  lon
```

This allows efficient queries such as:

* latest position per vehicle
* vehicle counts
* time-window analytics

# API Design

The Flask API provides endpoints used by the frontend.

Example:

```
/api/nearest_vehicles?lat=41.49&lon=-81.69
```

Returns vehicles near a given coordinate.

## Spatial Search

The current implementation uses a naïve nearest-neighbor scan:

1. Retrieve vehicles from cache
2. Compute distance using the Haversine formula
3. Sort by distance

This was chosen because:

- Dataset size is small (tens to hundreds of vehicles)
- Simpler to implement
- Faster than introducing spatial indexing prematurely

Future versions may explore k-d trees or R-trees.

# Caching Strategy

A key challenge with real-time feeds is API load. If every web request triggered a GTFS fetch, the system would collapse quickly. To avoid this, WIMBAC uses a shared memory cache:

```
LATEST_VEHICLES
LATEST_VEHICLES_TS
```

When a request arrives:

```
if cache fresh:
    return cached vehicles
else:
    fetch GTFS feeds
    update cache
```

This design ensures:

- multiple users share the same data
- external APIs are not spammed
- response latency remains low

---

# Frontend

The frontend is a simple Leaflet map.

Features:

- Map centered on Cleveland
- Stops displayed as markers, with clicked stops represented as empty circles
- Nearby vehicles enlarged
- Real-time updates via API calls

The frontend intentionally avoids heavy frameworks in order to keep the stack understandable.

# Deployment Architecture

The system runs on a Linux VPS. Deployment stack and key responsibilities:

| Component | Role               |
| --------- | ------------------ |
| Nginx     | reverse proxy      |
| Gunicorn  | Python WSGI server |
| Flask     | application logic  |
| InfluxDB  | telemetry storage  |

# Service Management

The backend currently runs as a systemd service.

Benefits:

- automatic restart on failure
- startup at boot
- centralized logging

Service file example:

```
/etc/systemd/system/wimbac.service
```

Environment variables (tokens, config) are stored outside the repo.

## Design Constraints

WIMBAC intentionally favors clarity and minimal infrastructure over early optimization. Several design decisions follow from the current scale of the system.

### Keep the system understandable

The current architecture uses:

- a single VPS  
- a Flask API  
- a naïve spatial search  
- a minimal frontend  

This keeps the full system understandable from ingestion to visualization. The entire pipeline—from GTFS ingestion to map rendering—can be traced through a small number of components.

### Avoid premature infrastructure

Many real-time systems introduce infrastructure such as Redis caches, message queues, and container orchestration early in development.

WIMBAC avoids these additions until they are justified by scale. For the current dataset (tens to hundreds of vehicles), simpler approaches remain faster to implement and easier to reason about.

### Design for replacement

Each layer of the system is loosely coupled so it can be replaced independently as requirements evolve.

| Layer            | Possible Upgrade                     |
|------------------|--------------------------------------|
| API              | FastAPI or Go service                |
| Cache            | Redis                                |
| Spatial queries  | PostGIS or spatial indexing          |
| Deployment       | Docker / container orchestration     |

This allows the system to evolve without requiring a full rewrite.

# Next Steps

## Immediate Fixes

- Dockerize the application(?)
- Improve vehicle-stop visualization
- Add route filtering
- Add map clustering
- Add error handling around GTFS feeds

### Main Features

- **ADD ROUTE ANALYTICS**
- Add monitoring dashboards
- Implement rate limiting
- Add user feedback (no account, simple text with optional name)
- Add historical playback
- Introduce spatial indexing
