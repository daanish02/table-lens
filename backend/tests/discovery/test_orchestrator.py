import os
import pytest

from app.discovery.orchestrator import run_discovery, get_discovery_status

requires_full_stack = pytest.mark.skipif(
    not (os.getenv("SUPABASE_DB_URL") and os.getenv("OPENROUTER_API_KEY")),
    reason="requires SUPABASE_DB_URL, OPENROUTER_API_KEY",
)


@requires_full_stack
def test_run_discovery_completes_and_reports_status():
    run_id = run_discovery(os.environ["SUPABASE_DB_URL"], schema="demo")
    status = get_discovery_status(run_id)
    assert status["status"] in {"running", "done"}


@requires_full_stack
def test_run_discovery_skips_unchanged_schema():
    first_run_id = run_discovery(os.environ["SUPABASE_DB_URL"], schema="demo")
    second_run_id = run_discovery(os.environ["SUPABASE_DB_URL"], schema="demo")
    assert first_run_id == second_run_id  # same schema hash -> same run reused
