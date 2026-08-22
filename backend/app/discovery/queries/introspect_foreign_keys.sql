SELECT tc.table_name, kcu.column_name, ccu.table_name AS fk_table, ccu.column_name AS fk_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.table_schema = :schema
  AND tc.constraint_type = 'FOREIGN KEY'
