-- The newest applied migration. Raises undefined_table on a database that was never migrated.
SELECT version, name
FROM schema_migrations
ORDER BY version DESC
LIMIT 1;
