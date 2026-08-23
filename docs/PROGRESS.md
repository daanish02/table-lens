# Table Lens — Progress

## Status
Canon. Sole place build/rollout status lives — HLD docs (PRD, ARCHITECTURE,
SCHEMAS, APIS) describe the system as a whole and carry no stage tags.
Update this file whenever a stage's status changes.

See `docs/diagrams/roadmap.excalidraw` for the visual timeline.

## Stages

| Stage | What | Status |
|---|---|---|
| 0 | Synthetic seed data generator | Built |
| 1a | Discovery agent (schema profiling + embeddings) | Built — relationship inference is computed but not yet persisted/consumed (see `PRD.md`) |
| 1b | Query agent (NL → SQL) | Built |
| 2 | Chat + chart UI | Built — split across `/ask` (chat + SQL/results) and `/visualize` (chat + chart cards), not a single unified split screen as originally scoped |
| 3 | Dashboard builder | Built at reduced scope — save-a-named-chart-set only; no drag-and-drop layout, no NL composition |
| 4 | RBAC / multi-tenant | Not scheduled |

## Current Focus
Reconciling `docs/` (PRD, ARCHITECTURE, SCHEMAS, APIS) with the actual
implementation — those docs had drifted significantly behind the built
system, in both directions (undocumented endpoints/tables, and described
features that were never built).
