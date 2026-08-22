SELECT id, title, question, sql, chart_type, chart_config, result_cache, created_at
FROM public.saved_charts
WHERE id = ANY(CAST(:ids AS uuid[]))
