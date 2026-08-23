SELECT date_trunc('{granularity}', {column}) AS bucket_min, COUNT(*) AS cnt
FROM {source}
WHERE {column} IS NOT NULL
GROUP BY bucket_min
ORDER BY bucket_min
