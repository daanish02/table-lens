SELECT run_id, status, started_at, finished_at, total_tables, tables_done
FROM public.discovery_runs
ORDER BY started_at DESC
LIMIT 1
