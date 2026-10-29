# Context

`dlexport` is a CLI utility for exporting metadata from UCLA Library's digital collections database. It is intended to be used by software developers within the UCLA Library. It is not for general use.

# Developer Information

## Overview of environment

The development environment requires:
* `git` (at least version 2)
* `docker`(version 25+) and `docker compose` (version 2+)

### Dev container

This project comes with a basic dev container definition, in `.devcontainer/devcontainer.json`. It's known to work with VS Code,
and may work with other IDEs like PyCharm.  For VS Code, it also installs the following extensions:
- Python (which includes our type checker, pyright, as part of the pylance language server)
- ruff (formatter and linter)

When prompted by VS Code, click "Reopen in container".  This will (re)build the container, `dlexport`. It will also
(re)build a copy of that container, `vsc-dlexport-<long_hash>-uid`, install VS Code development tools & extensions within that container,
and start the `docker compose` system.  VS Code will be connected to the Django container, with all code available for editing in that context.

### Python Environment

This project uses `uv` (see [docs](https://docs.astral.sh/uv/)) for managing Python virtual environments and dependencies, including within the dev container.

### Secrets

TODO: Set up secrets files for development, once PostgreSQL swap with Oracle is complete.

# Running the program

TODO: Update the sections below as CLI is brought up-to-date with our current team practices.

## Authentication

So the application can access the database, open a SSH tunnel from your local machine according to step 1 in the Jdeveloper section of https://docs.library.ucla.edu/display/dlp/SSH+tunneling+to+access+DLCS+database+at+ITS, using port `9001` instead of `9000`.

## CLI

Keep the virtualenv running to use this utility at the command line.

Show usage with:

```Shell
python3 dlexport.py -h
```

For example, to export metadata (including thumbnail image names and master image names) from the Aldous Huxley Collection in the production DLCS database to 'myFile.csv':

```Shell
python3 dlexport.py -t -m -d lit106 -c huxle > myFile.csv
```

or, in long form:

```Shell
python3 dlexport.py --thumbnails --masters --database lit106 --collection huxle > myFile.csv
```

## Cleanup

To exit your virtual environment:

```Shell
deactivate
```

To destroy it forever:

```Shell
rm -rf venv-dlexport
```

## Test

To run the automated tests (with virtualenv up and running):

```Shell
python3 dlexport-test.py -v
```
