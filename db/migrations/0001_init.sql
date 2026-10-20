-- 0001_init: the migration runner's own bookkeeping table.
--
-- The runner records every migration it applies here. This table is created by the first
-- migration instead of by the runner itself, so the whole schema — bookkeeping included —
-- comes from files in db/migrations/.

CREATE TABLE schema_migrations (
    version    integer     PRIMARY KEY,
    name       text        NOT NULL,
    -- SHA-256 of the file as applied. If the file changes later, the runner refuses to go on.
    checksum   text        NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT now()
);
