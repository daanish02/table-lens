SELECT {column} AS bucket_min, COUNT(*) AS cnt
FROM {source}
WHERE {column} IS NOT NULL
GROUP BY {column}
ORDER BY {column}
