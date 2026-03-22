# Caching Strategy

WIMBAC uses a two-layer caching strategy to stabilize load and reduce redundant computation across both external APIs and internal services.

## 1. GTFS Fetch Cache (Upstream Protection)

The system maintains an in-memory snapshot of the most recent vehicle data:

```

LATEST_VEHICLES
LATEST_VEHICLES_TS

```

### Behavior

```

if cache is fresh:
return cached data
else:
fetch GTFS feeds
update cache

```

### Purpose

- Prevent repeated requests to GTFS-Realtime APIs  
- Align system updates with feed refresh cadence (~30s)  
- Ensure all clients share the same dataset  

## 2. API Response Cache (Internal Protection)

Certain API endpoints cache computed responses for a short duration.

### Purpose

- Reduce repeated database queries  
- Avoid recomputing identical requests  
- Improve latency under concurrent load  

### Effect

- Lower CPU usage  
- Reduced database pressure  
- Consistent response times during traffic bursts  

## Why Two Layers?

| Cache Type        | Protects                    |
|------------------|-----------------------------|
| GTFS Fetch Cache | External transit APIs       |
| API Cache        | Internal DB + application   |

Each layer addresses a different bottleneck.

## Impact

Moving ingestion off the request path and serving cached data resulted in:

- ~45× reduction in average latency  
- ~60× reduction in p95 latency  
- Stable performance at 100 concurrent users  

## Future Improvements

- Redis or Memcached for distributed caching  
- Event-driven cache invalidation  
- Route-level cache strategies  
- Adaptive TTLs based on feed timing  
```