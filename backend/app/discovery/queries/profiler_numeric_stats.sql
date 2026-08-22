SELECT MIN({column}), MAX({column}), AVG({column}),
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {column}),
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {column})
FROM {source}
