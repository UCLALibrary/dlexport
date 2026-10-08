# Use a Python image with uv pre-installed
FROM python:3.13-slim-bookworm AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/

ARG APP_USER_UID=1000

# Set correct local and timezone
RUN ln -sf /usr/share/zoneinfo/America/Los_Angeles /etc/localtime

# Create generic app user
RUN useradd --comment "generic app user" \
    --home-dir /home/app_user \
    --shell /bin/bash \
    --uid ${APP_USER_UID} \
    --create-home \
    app_user

# Switch to application directory, creating it if needed
WORKDIR /home/app_user/project

# Make sure app_user owns app directory, if WORKDIR created it:
# https://github.com/docker/docs/issues/13574
RUN chown -R app_user:app_user /home/app_user

# Change context to app_user for remaining steps
USER app_user

# Keep virtualenv out of the project directory
ENV UV_PROJECT_ENVIRONMENT=/home/app_user/venv
# "activate" the virtualenv
ENV PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

# Install requirements for this application
COPY --chown=app_user:app_user pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/home/app_user/.cache/uv,uid=${APP_USER_UID} \
    uv sync --locked --no-dev

FROM base AS dev

USER root
# Install git so its accessible within container and libatomic1 for pyright dependency
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends git libatomic1 \
    && rm -rf /var/lib/apt/lists/*
USER app_user

# add the dev requirements
RUN --mount=type=cache,target=/home/app_user/.cache/uv,uid=${APP_USER_UID} \
    uv sync --locked --group=dev
