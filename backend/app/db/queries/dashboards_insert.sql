INSERT INTO public.dashboards (title, chart_ids)
VALUES (:title, CAST(:chart_ids AS uuid[]))
RETURNING id, created_at
