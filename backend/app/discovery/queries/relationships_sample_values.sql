SELECT {from_col}
FROM {schema}.{from_table}
WHERE {from_col} IS NOT NULL
ORDER BY random()
LIMIT {sample_size}
