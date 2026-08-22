UPDATE public.discovery_runs SET status = 'failed', error = :err, finished_at = :now WHERE run_id = :id
