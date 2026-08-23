# Table Lens — Testing

## Status
Canon. Update whenever the test layout, markers, or run commands change.
Build/rollout progress lives in `docs/PROGRESS.md`, not here.

## Backend (`backend/tests/`, pytest)

Layout mirrors `backend/app/`, one subdirectory per subsystem:
```
tests/
├── api/          # route-level tests, FastAPI TestClient, DB/LLM fully mocked
├── db/           # connection, migrations, saved_charts/dashboards round-trips
├── discovery/    # introspection, profiling, relationships, embeddings, LLM, orchestrator
├── generator/    # DDL/schema generation for the synthetic demo data
├── query/        # SQL guard (injection/DDL rejection)
├── utils/        # logger
└── visualize/    # chart guard (structural validation of LLM-produced chart specs)
```

### Three tiers, by marker

1. **Default (no marker)** — pure/mocked tests. No network, no real DB or
   LLM calls. This is the bulk of the suite (~81 tests) and runs in about
   2 seconds.
2. **`requires_db` / `requires_llm` / `requires_full_stack`** — real
   integration tests that hit a live Supabase database and/or a live
   OpenRouter LLM call. Skipped by default. Gated on an explicit opt-in
   flag, **not** on credential presence — a root `.env` with real
   credentials is expected to exist locally for the app itself to run, so
   gating on "is `SUPABASE_DB_URL` set" would never actually skip anything.
   Run them with:
   ```bash
   RUN_LIVE_TESTS=1 uv run pytest
   ```
   These write real rows to `saved_charts`/`dashboards`/`table_embeddings`/
   `column_embeddings` (cleaned up in a `finally` block, not transactionally
   isolated) and make real LLM calls — run deliberately, not as part of
   routine local iteration or CI-on-every-push.
3. **`@pytest.mark.slow`** — one genuine end-to-end test
   (`test_run_discovery_completes_and_reports_status`): a full discovery
   run against the live stack, every loaded table and column. Deselected
   by default (`addopts = "-m 'not slow'"` in `pyproject.toml`). Also
   requires `RUN_LIVE_TESTS=1` (it's marked `requires_full_stack` too). Run
   explicitly:
   ```bash
   RUN_LIVE_TESTS=1 uv run pytest -m slow
   ```

### Running

```bash
cd backend
uv run pytest                           # default: fast tier only, ~81 tests, ~2s
uv run pytest --durations=10            # see the slowest tests in the run
RUN_LIVE_TESTS=1 uv run pytest          # fast + live-DB/LLM tiers (~94 tests)
RUN_LIVE_TESTS=1 uv run pytest -m slow  # the one full end-to-end test too
```

Never trigger the live tiers from an automated/CI context using shared or
production-adjacent credentials without dedicated test infrastructure — they
currently run against whatever `SUPABASE_DB_URL`/`OPENROUTER_API_KEY` are in
scope, with real cost and real writes.

## Frontend (`frontend/`, vitest)

Minimal today — one test file, `frontend/lib/logger.test.ts`, covering the
logger's level-prefixing and prod-mode debug suppression. Run with:
```bash
cd frontend
bun run test          # runs the vitest suite
bun x tsc --noEmit    # the main correctness gate for the frontend today
```
Most frontend correctness currently comes from TypeScript's type checker
and manual verification, not automated tests — stated plainly here rather
than implying broader coverage than exists.
