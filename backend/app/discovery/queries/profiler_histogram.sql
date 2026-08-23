SELECT MIN({column}) AS bucket_min, COUNT(*) AS cnt
FROM {source}
WHERE {column} IS NOT NULL
GROUP BY width_bucket({column}, {min_val}, {max_val}, {buckets})
ORDER BY bucket_min
