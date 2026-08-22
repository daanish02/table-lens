SELECT {column}, COUNT(*) c
FROM {source}
WHERE {column} IS NOT NULL
GROUP BY {column}
ORDER BY c DESC
LIMIT {limit}
