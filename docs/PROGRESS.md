# table-lens — Progress

## Status
Canon. Sole place build/rollout status lives — HLD docs (PRD, ARCHITECTURE,
SCHEMAS, APIS) describe the system as a whole and carry no stage tags.
Update this file whenever a stage's status changes.

See `docs/diagrams/roadmap.excalidraw` for the visual timeline.

## Stages

| Stage | What | Status |
|---|---|---|
| 0 | Synthetic seed data generator | Built |
| 1a | Discovery agent (schema profiling + embeddings) | Not started — spec: `specs/2026-08-22-foundation-stage1a-design.md` |
| 1b | Query agent (NL → SQL) | Not started |
| 2 | Chat + chart UI | Not started |
| 3 | Dashboard builder | Not started |
| 4 | RBAC / multi-tenant | Not scheduled |

## Current Focus
Foundation + Stage 1a — repo restructure (flat `backend/`/`frontend/`,
generator relocation) and discovery agent build.
