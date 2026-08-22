SELECT width_bucket({column}, {min_val}, {max_val}, {buckets}) AS bucket, COUNT(*) AS cnt
FROM {source}
WHERE {column} IS NOT NULL
GROUP BY bucket
ORDER BY bucket
