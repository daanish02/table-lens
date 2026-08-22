INSERT INTO public.saved_charts (title, question, sql, chart_type, chart_config, result_cache)
VALUES (:title, :question, :sql, :chart_type, CAST(:chart_config AS jsonb), CAST(:result_cache AS jsonb))
RETURNING id, created_at
