SELECT {column} AS bucket_min, {column} AS bucket_max, COUNT(*) AS cnt
FROM {source}
WHERE {column} IS NOT NULL
GROUP BY {column}
ORDER BY {column}
