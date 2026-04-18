# Concurrency torture — 100 parallel requests per scenario

Target: http://127.0.0.1:18400


## POST /api/v1/orders — same body × 100
- N = 100, OK = 20, non-2xx = 80, errors = 0
- status codes: {200: 20, 500: 80}
- p50 / p95 / p99 = 2287ms / 3607ms / 3714ms

## POST /api/v1/webhooks/identity/created — unsigned × 100
- N = 100, OK = 0, non-2xx = 100, errors = 0
- status codes: {403: 100}
- p50 / p95 / p99 = 1285ms / 1349ms / 1351ms

## GET /api/v1/legacy/stats × 100
- N = 100, OK = 100, non-2xx = 0, errors = 0
- status codes: {200: 100}
- p50 / p95 / p99 = 1046ms / 1226ms / 1227ms
