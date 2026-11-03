# dlexport

## Context

`dlexport` is a CLI utility for exporting metadata from UCLA Library's digital collections database. It is intended to be used by software developers within the UCLA Library. It is not for general use.

## Developer Information

### Overview of environment

The development environment requires:
* `git` (at least version 2)
* `docker` (version 25+) and `docker compose` (version 2+)

### Dev container

This project comes with a basic dev container definition, in `.devcontainer/devcontainer.json`. It's known to work with VS Code,
and may work with other IDEs like PyCharm.  For VS Code, it also installs the following extensions:
- Python (which includes our type checker, pyright, as part of the pylance language server)
- ruff (formatter and linter)

When prompted by VS Code, click "Reopen in container".  This will (re)build the container, `dlexport`. It will also
(re)build a copy of that container, `vsc-dlexport-<long_hash>-uid`, install VS Code development tools & extensions within that container,
and start the `docker compose` system.  VS Code will be connected to the Django container, with all code available for editing in that context.

### Python environment

This project uses `uv` (see [docs](https://docs.astral.sh/uv/)) for managing Python virtual environments and dependencies, including within the dev container.

### PostgreSQL database

The Compose stack includes a PostgreSQL database service. Local-only connection settings are saved in `.docker-compose_db.env`. This file is safe for version control as it only contains development credentials.

A production data snapshot can be loaded into the Postgres development database using the included import script. First, ask a teammate for a copy of the production database archive, then place the archive file in the project root and run the importer:

```bash
./docker_scripts/import_prod_db.sh pg_dlcs_archive-YYYY-MM-DD.tar.gz
```

Database archives contain production data; do not commit them to version control.

## Running the program

From within the dev container, run the following commands using `uv` to interact with the application.

Show usage:

```bash
uv run python dlexport.py -h
```

To export metadata from the Aldous Huxley Collection in the local database to 'myFile.csv', for example:

```bash
uv run python dlexport.py -d dlexport_db -c huxle > myFile.csv
```

or, in long form:

```bash
uv run python dlexport.py --database dlexport_db --collection huxle > myFile.csv
```

### Testing

Run unit tests with:

```bash
uv run python -m unittest
```

### Running via Docker Compose from outside dev container

To run the program from outside the dev container using Docker Compose, simply append `docker compose exec dlexport` before the commands above. For example:

```bash
docker compose exec dlexport uv run python dlexport.py -h
```
