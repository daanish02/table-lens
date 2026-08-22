UPDATE public.discovery_runs SET status = 'done', finished_at = :now WHERE run_id = :id
