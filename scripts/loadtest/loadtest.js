import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics for easier interpretation in exported summaries.
export const apiErrorRate = new Rate('api_error_rate');
export const vehiclesLatency = new Trend('vehicles_latency');
export const vehiclesNearLatency = new Trend('vehicles_near_latency');
export const routeVehiclesLatency = new Trend('route_vehicles_latency');

// Required environment variable.
// Example:
//   BASE_URL="https://wimbac.com" k6 run scripts/loadtest/loadtest.js
const BASE_URL = __ENV.BASE_URL;

if (!BASE_URL) {
  throw new Error('BASE_URL environment variable is required. Example: BASE_URL="https://wimbac.com"');
}

// Keep these easy to edit if your endpoint names or query params differ.
const ENDPOINTS = {
  vehicles: '/api/vehicles',
  vehiclesNear: '/api/vehicles_near?lat=41.4993&lon=-81.6944&radius=1000',
  routeVehicles: '/api/vehicles?route=15',
};

// Realistic traffic mix for a transit-monitoring app:
// - general vehicle map/data loads
// - nearby lookups around a user-selected location
// - route-filtered lookups
const TRAFFIC_MIX = [
  { name: 'vehicles', path: ENDPOINTS.vehicles, weight: 0.50, metric: vehiclesLatency },
  { name: 'vehicles_near', path: ENDPOINTS.vehiclesNear, weight: 0.30, metric: vehiclesNearLatency },
  { name: 'route_vehicles', path: ENDPOINTS.routeVehicles, weight: 0.20, metric: routeVehiclesLatency },
];

export const options = {
  stages: [
    { duration: '1m', target: 5 },   // warm-up
    { duration: '3m', target: 20 },  // moderate load
    { duration: '4m', target: 100 },  // heavier load
    { duration: '2m', target: 10 },  // cooldown
    { duration: '1m', target: 0 },   // ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],
    api_error_rate: ['rate<0.05'],
    http_req_duration: ['p(95)<1500', 'p(99)<3000'],
    vehicles_latency: ['p(95)<1500'],
    vehicles_near_latency: ['p(95)<2000'],
    route_vehicles_latency: ['p(95)<1500'],
    checks: ['rate>0.95'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
  userAgent: 'wimbac-k6-loadtest/1.0',
};

function chooseEndpoint() {
  const r = Math.random();
  let cumulative = 0;

  for (const endpoint of TRAFFIC_MIX) {
    cumulative += endpoint.weight;
    if (r <= cumulative) {
      return endpoint;
    }
  }

  return TRAFFIC_MIX[TRAFFIC_MIX.length - 1];
}

export default function () {
  const endpoint = chooseEndpoint();
  const url = `${BASE_URL}${endpoint.path}`;

  const params = {
    headers: {
      Accept: 'application/json',
    },
    timeout: '10s',
  };

  const res = http.get(url, params);

  endpoint.metric.add(res.timings.duration);

  const ok = check(res, {
    [`${endpoint.name}: status is 200`]: (r) => r.status === 200,
    [`${endpoint.name}: response time under 2000ms`]: (r) => r.timings.duration < 2000,
    [`${endpoint.name}: content-type is json-like`]: (r) => {
      const ctype = r.headers['Content-Type'] || r.headers['content-type'] || '';
      return ctype.includes('application/json') || ctype.includes('text/json');
    },
  });

  apiErrorRate.add(!ok || res.status >= 400);

  // Small think time to avoid making the traffic unrealistically robotic.
  sleep(Math.random() * 2 + 0.5);
}

export function handleSummary(data) {
  return {
    stdout: textSummary(data),
  };
}

function textSummary(data) {
  const m = data.metrics;

  function metricLine(name, label) {
    if (!m[name]) return `${label}: n/a`;
    const vals = m[name].values || {};
    return `${label}: avg=${fmt(vals.avg)} p95=${fmt(vals['p(95)'])} p99=${fmt(vals['p(99)'])}`;
  }

  const lines = [
    '',
    '========== WIMBAC LOAD TEST SUMMARY ==========\n',
    `iterations: ${safeVal(m.iterations, 'count')}`,
    `http requests: ${safeVal(m.http_reqs, 'count')}`,
    `throughput (req/s): ${fmt(safeVal(m.http_reqs, 'rate'))}`,
    `avg latency (ms): ${fmt(safeVal(m.http_req_duration, 'avg'))}`,
    `p95 latency (ms): ${fmt(safeVal(m.http_req_duration, 'p(95)'))}`,
    `p99 latency (ms): ${fmt(safeVal(m.http_req_duration, 'p(99)'))}`,
    `error rate: ${fmtPct(safeVal(m.http_req_failed, 'rate'))}`,
    `check pass rate: ${fmtPct(safeVal(m.checks, 'rate'))}`,
    '',
    metricLine('vehicles_latency', 'vehicles'),
    metricLine('vehicles_near_latency', 'vehicles_near'),
    metricLine('route_vehicles_latency', 'route_vehicles'),
    '',
  ];

  return lines.join('\n');
}

function safeVal(metric, key) {
  if (!metric || !metric.values || metric.values[key] === undefined) return null;
  return metric.values[key];
}

function fmt(v) {
  return v === null ? 'n/a' : Number(v).toFixed(2);
}

function fmtPct(v) {
  return v === null ? 'n/a' : `${(Number(v) * 100).toFixed(2)}%`;
}