SELECT id, title, chart_ids, created_at
FROM public.dashboards
WHERE id = :id
