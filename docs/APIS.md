# Table Lens — API Surface

## Status
Canon. Update whenever an endpoint is added, changed, or removed. Build/
rollout progress lives in `docs/PROGRESS.md`, not here.

## Discovery
```
POST /api/discover          # trigger discovery agent on connected DB
GET  /api/discover/status   # check discovery progress
```

`POST /api/discover` — body: `{ "db_url": string }`. Idempotent — skips
re-profiling if schema hash is unchanged since the last successful run.
Async: kicks off discovery, returns immediately; poll status separately.

`GET /api/discover/status` — returns current run state (pending / running /
step-level progress / done / failed) and, on failure, the last error.

## Query
```
POST /api/query             # submit NL question, returns SQL + results + headline
GET  /api/query/{id}/csv    # download results as CSV
POST /api/query/{id}/retry  # retry with user feedback
```

`POST /api/query` — body: `{ "question": string, "conversation_id"?: string }`.
Returns generated SQL, result rows (capped, default LIMIT 1000), and a
plain-English headline. May return a clarifying question instead of results
if the question is ambiguous.

`GET /api/query/{id}/csv` — streams the full (unpaged) result set as CSV.

`POST /api/query/{id}/retry` — body: `{ "feedback": string }`. Regenerates
SQL using the original question + user feedback + prior error context.

## Cross-cutting
- Rate limiting: IP-based, 20 requests/minute per endpoint, no auth.
- All endpoints under `/api/`, versioning deferred until a breaking change is
  actually needed (YAGNI).

## Not Yet Designed
Chart persistence (`saved_charts`) and dashboard composition (`dashboards`)
endpoints will be added once their design is worked out. Not speculated
here.
