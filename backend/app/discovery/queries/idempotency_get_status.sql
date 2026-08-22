SELECT run_id, status, step, error, total_tables, tables_done FROM public.discovery_runs WHERE run_id = :id
