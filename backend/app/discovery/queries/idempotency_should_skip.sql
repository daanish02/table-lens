SELECT 1 FROM public.discovery_runs WHERE schema_hash = :h AND status = 'done' LIMIT 1
