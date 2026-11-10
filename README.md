# dlexport

## Context

`dlexport` is a CLI utility for exporting metadata from UCLA Library's digital collections database. It is intended to be used by software developers within the UCLA Library. It is not for general use.

## Development setup

The project requires Python 3.13, `uv`, Git, Docker 25 or later, and Docker Compose v2. The supplied
dev container provides Python and `uv`, and is the recommended way to work on the project.

In VS Code, open the project and choose **Reopen in Container** when prompted. The dev container starts
the `dlexport` development service and its PostgreSQL service. The container configuration includes
the Python and Ruff VS Code extensions. The project uses [`uv`](https://docs.astral.sh/uv/) to manage
dependencies and its virtual environment.

### PostgreSQL database

The Compose stack includes a PostgreSQL database service. Local connection settings are in
`.docker-compose_db.env`; its credentials are for development only.

To load data into the development database, first start the Compose stack, then ask a teammate for a
production database archive and place it in the project root. Run the importer with the TAR archive name:

```bash
./docker_scripts/import_prod_db.sh pg_dlcs_archive-YYYY-MM-DD.tar.gz
```

The TAR archive contains production data; do not commit it to version control.

## Usage

Run commands from the project root, preferably within the dev container.

Show help:

```bash
uv run dlexport --help
```

Export the Aldous Huxley Collection (`huxle`) to CSV:

```bash
uv run dlexport --database dlexport_db --collection huxle --format csv --output-path myFile.csv
```

Use `--format json` for JSON output. The format defaults to CSV. The short options are:

  - `-d` for `--database`
  - `-c` for `--collection`
  - `-f` for `--format`
  - `-o` for `--output-path`

Short form:

```bash
uv run dlexport -d dlexport_db -c huxle -f json -o huxle.json
```

If `--output-path` is omitted, the export is written to `output/dlexport_TIMESTAMP.FORMAT`. The output directory is created if needed.

### Testing

Run the test suite with:

```bash
uv run python -m unittest
```

Database integration tests use the local Compose database and expect it to contain the `huxle`
collection. They are skipped when the database host and name environment variables are not set.

### Running from outside the dev container

Use `docker compose exec dlexport` to run a command in the development container:

```bash
docker compose exec dlexport uv run dlexport --help
docker compose exec dlexport uv run dlexport -d dlexport_db -c huxle
```
