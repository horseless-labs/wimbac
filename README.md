# WIMBAC

**Web-Integrated Monitoring of Bus Activity in Cleveland**

WIMBAC is a lightweight real-time transit monitoring system that ingests GTFS-Realtime feeds, stores vehicle telemetry in InfluxDB, and exposes a web interface for exploring bus activity across Cleveland.

Live: https://www.wimbac.com

## Overview

WIMBAC collects real-time transit feeds and exposes them through a backend API and map interface.

Core features:

- Real-time (20–30s interval) GTFS-RT ingestion  
- Time-series storage of vehicle telemetry (InfluxDB)  
- Spatial query API (nearest vehicles)  
- Leaflet-based frontend visualization  
- Production deployment (Gunicorn + Nginx on VPS)  

The system is designed as an end-to-end exercise in ingestion, storage, API design, and deployment.

## System Architecture

```

GTFS-RT Feeds → ingestion pipeline → InfluxDB → Flask API → Nginx + Gunicorn → Leaflet frontend

```

| Layer           | Role                                            |
|-----------------|-------------------------------------------------|
| Ingestion       | Pull + normalize GTFS-RT feeds                  |
| Storage         | Persist telemetry as time-series data           |
| API             | Serve real-time + historical queries            |
| Frontend        | Visualize vehicles and stops                    |
| Infrastructure  | Serve reliably in production                    |

## Technology Stack

**Backend**
- Python  
- Flask  
- InfluxDB  

**Frontend**
- Leaflet.js  
- Vanilla JavaScript  

**Infrastructure**
- Debian VPS  
- Gunicorn  
- Nginx  
- systemd  

## Data Ingestion

WIMBAC ingests GTFS-Realtime feeds from the Greater Cleveland RTA.

Merged feeds:

| Feed              | Data                  |
|-------------------|-----------------------|
| Vehicle Positions | latitude, longitude   |
| Trip Updates      | route, stop, schedule |

Normalized record:

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

## Storage (InfluxDB)

Measurement: `vehicle_status`

**Tags**
- vehicle_id  
- route_id  
- next_stop_id  

**Fields**
- lat  
- lon  

Supports:
- latest vehicle positions  
- time-window queries  
- route/stop analytics (in progress)  

## API

Example:

```
/api/nearest_vehicles?lat=41.49&lon=-81.69

```

### Spatial Search

- In-memory dataset  
- Haversine distance  
- Sorted nearest-neighbor results  

Chosen for simplicity given current scale (tens–hundreds of vehicles).

## System Behavior

- GTFS ingestion runs asynchronously  
- API reads from in-memory cache (real-time)  
- Historical queries use InfluxDB  

This removes feed processing from request paths and stabilizes latency.

## Frontend

- Leaflet-based map centered on Cleveland  
- Stop markers + interactive selection  
- Nearby vehicles highlighted  
- Periodic refresh via API  

## Deployment

| Component | Role               |
|----------|--------------------|
| Nginx    | Reverse proxy      |
| Gunicorn | WSGI server        |
| Flask    | Application logic  |
| InfluxDB | Data storage       |

## Performance (Summary)

- Stable performance under 100 concurrent users  
- 0% error rate across all tests  
- ~45× latency reduction after caching  

See:
- `/docs/caching.md`  
- `/docs/load-testing.md`  

## Design Principles

- Keep the system understandable end-to-end  
- Avoid premature infrastructure  
- Build components to be replaceable  

## Next Steps

- Add route and stop-level analytics  
- Implement on-time performance metrics  
- Improve frontend interactions  
- Add filtering and clustering  
- Introduce monitoring dashboards  
```