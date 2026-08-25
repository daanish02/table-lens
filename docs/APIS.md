# Table Lens — API Surface

## Status
Canon. Update whenever an endpoint is added, changed, or removed. Build/
rollout progress lives in `docs/PROGRESS.md`, not here.

## Discovery
```
POST /api/discover                          # trigger discovery agent on connected DB
GET  /api/discover/status/{run_id}          # check a specific run's progress
GET  /api/discover/results                  # list per-table discovery results (latest run)
GET  /api/discover/results/{table_name}     # discovery result for one table
GET  /api/discover/overview                 # summary across all discovered tables
```

`POST /api/discover` — no request body; profiles the DB connected via
`SUPABASE_DB_URL`. Idempotent per-column (see `SCHEMAS.md`'s
`content_hash` note) — unchanged columns aren't re-described. Async: kicks
off discovery, returns `202` with `{ "run_id": string }`; poll status
separately. Rate-limited tighter than other routes (see Cross-cutting)
since it's the most expensive route. Returns `409` with
`{ "message": string, "run_id": string }` if a run is already in progress.

`GET /api/discover/status/{run_id}` — returns current run state (status,
step, `total_tables`/`tables_done`, and on failure the last error). `404`
for an unknown `run_id`.

`GET /api/discover/results`, `GET /api/discover/results/{table_name}`,
`GET /api/discover/overview` — read the persisted output of the most recent
discovery run (table/column descriptions, profiles) — used by the frontend's
data-overview and table-detail views.

## Query
```
POST /api/query              # submit NL question + history, streams the agent's work as SSE
```

`POST /api/query` — body: `{ "question": string, "history": [{ "role": string, "content": string }] }`.
Response is a `text/event-stream` (Server-Sent Events), not a single JSON
body — the client consumes it incrementally as the agent works. Event
types, in the order they can occur:
- `tool_call` — `{ "tool": string, "args": ... }`, whenever the agent calls
  `search_tables`/`search_columns`/`run_sql`.
- `tool_result` — `{ "tool": string, "summary": ... }`, that tool call's
  outcome.
- `answer_delta` — `{ "text": string }`, streamed chunks of the agent's
  final natural-language answer.
- `done` (terminal) — `{ "answer": string, "sql": string, "columns": [...],
  "rows": [...], "row_count": int, "headline": string, "elapsed_ms": int }`.

## Visualize
```
POST /api/visualize          # turn a query result into a chart spec
```

`POST /api/visualize` — body: `{ "question": string, "sql": string,
"headline": string, "columns": [...], "rows": [...], "theme": string }`.
Returns `{ "title": string, "chart_type": string, "option": object|null,
"elapsed_ms": number }` — a validated ECharts option assembled by the
visualize agent (see `ARCHITECTURE.md` for the descriptor→builder→guard
pipeline). `elapsed_ms` is the wall time for the full chart-generation step.

## Data
```
GET /api/data/{table_name}   # paginated raw row browser
```

`GET /api/data/{table_name}?page=&page_size=` — returns a page of raw rows
from the given demo-schema table. `404` for an unknown table.

## Charts & Dashboards
```
POST /api/charts                    # save a chart
GET  /api/charts                    # list saved charts
GET  /api/charts/{chart_id}         # fetch one saved chart
POST /api/dashboards                # save a dashboard (a named set of chart ids)
GET  /api/dashboards                # list saved dashboards
GET  /api/dashboards/{dashboard_id} # fetch one saved dashboard
```

Backed by the `saved_charts`/`dashboards` tables — see `SCHEMAS.md`.
Dashboards are a flat list of chart ids under a title; there is no persisted
layout (no drag-and-drop positioning).

## Health
```
GET /health                  # liveness check, used by the Docker HEALTHCHECK
```

## Cross-cutting
- Rate limiting: IP-based, `20/minute` by default on every route, except
  `POST /api/discover` which is tightened to `5/hour` given its LLM cost.
  No auth.
- All endpoints under `/api/` (except `/health`), versioning deferred until
  a breaking change is actually needed (YAGNI).
