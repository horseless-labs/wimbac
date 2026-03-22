# Load Testing

WIMBAC was tested using k6 to evaluate API performance under increasing concurrency.

---

# Test Setup

Load ramp:
- 5 → 50 users (baseline)
- up to 100 users (stress test)

Metrics collected:
- latency (avg, median, p95, p99)
- error rate
- system resource usage

---

# Baseline Results (50 users)

- Average latency: ~285 ms
- Median latency: ~107 ms
- p95 latency: ~1.4 s
- p99 latency: ~1.9 s
- Error rate: 0%

Observation:
- Gradual latency increase due to Gunicorn worker saturation

---

# Stress Test (100 users)

- Average latency: ~1006 ms
- Median latency: ~486 ms
- p95 latency: ~3.4 s
- p99 latency: ~4.7 s
- Error rate: 0%

Observation:
- Significant queueing under load
- System degraded gracefully (no failures)

---

# After Caching Optimization

- Average latency: ~22 ms
- Median latency: ~12 ms
- p95 latency: ~56 ms
- p99 latency: ~170 ms
- Error rate: 0%

---

# Key Improvements

- ~45× reduction in average latency
- ~60× reduction in p95 latency
- ~27× reduction in p99 latency

---

# Key Insight

The primary bottleneck was performing GTFS ingestion during request handling.

Moving ingestion to a background process and serving cached data:

- removed upstream dependency from request path
- stabilized latency under load
- enabled higher concurrency without scaling infrastructure

---

# Conclusion

The current single-VPS deployment:

- handles moderate concurrency reliably
- fails gracefully under heavy load
- performs efficiently with caching

This establishes a baseline for future scaling (horizontal or cloud deployment).