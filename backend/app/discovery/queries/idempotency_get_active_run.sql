SELECT run_id, status, started_at
FROM public.discovery_runs
WHERE status IN ('pending', 'running')
ORDER BY started_at DESC
LIMIT 1
