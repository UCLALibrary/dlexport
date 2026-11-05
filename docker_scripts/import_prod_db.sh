#!/bin/bash

if [ -z "$1" ]; then
    echo Usage: $0 db_dump_file.tar.gz
    exit 1
else
    DB_FILE="$1"
fi

# Load local db info from .docker-compose_db.env
# DB user and DB name need to be the same as they are in production.
source .docker-compose_db.env

# Copy the db dump file to the running database container.
docker compose cp "${DB_FILE}" db:/tmp

# Build command to run inside container.
UNTAR_COMMAND="cd /tmp && tar xf ${DB_FILE}"
# DB_FILE variable value must be passed to docker compose.
docker compose exec -e DB_FILE="${DB_FILE}" db bash -c "${UNTAR_COMMAND}"

# Directory name is the first entry in the tar archive.
DB_DIR=`tar tf "${DB_FILE}" | head -1`
# Build command to run inside container.
PG_COMMAND="pg_restore --verbose --if-exists --clean -U ${POSTGRES_USER} -d ${POSTGRES_DB} /tmp/${DB_DIR}"
# DB_DIR variable value must be passed to docker compose.
docker compose exec -e DB_DIR="${DB_DIR}" db bash -c "${PG_COMMAND}"

# Convert all unlogged tables to logged tables after restoring the database,
# to ensure data persists after a crash or forced shutdown.
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" <<'SQL'
DO $$
DECLARE
    unlogged_table record;
    converted integer;
    total integer := 0;
BEGIN
    RAISE NOTICE 'Converting unlogged tables to logged...';
    -- A table can't be set LOGGED while it references an unlogged table,
    -- so each pass converts only tables whose referenced tables are logged.
    LOOP
        converted := 0;
        FOR unlogged_table IN
            SELECT n.nspname, c.relname
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE c.relpersistence = 'u'
              AND c.relkind IN ('r', 'p')
              AND NOT EXISTS (
                  SELECT 1
                  FROM pg_constraint AS con
                  JOIN pg_class AS ref ON ref.oid = con.confrelid
                  WHERE con.contype = 'f'
                    AND con.conrelid = c.oid
                    AND con.confrelid <> c.oid
                    AND ref.relpersistence = 'u'
              )
        LOOP
            RAISE NOTICE 'Setting %.% to LOGGED...',
                         unlogged_table.nspname, unlogged_table.relname;
            EXECUTE format('ALTER TABLE %I.%I SET LOGGED',
                           unlogged_table.nspname, unlogged_table.relname);
            converted := converted + 1;
            total := total + 1;
        END LOOP;
        EXIT WHEN converted = 0;
    END LOOP;

    RAISE NOTICE 'Finished: % table(s) set to LOGGED.', total;

    IF EXISTS (SELECT 1 FROM pg_class WHERE relpersistence = 'u' AND relkind IN ('r', 'p')) THEN
        RAISE EXCEPTION 'Some unlogged tables could not be set LOGGED (circular foreign keys?)';
    END IF;
END
$$;
SQL
