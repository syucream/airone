FROM python:3.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git libldap2-dev libsasl2-dev libxmlsec1-dev \
    default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
ENV UV_PROJECT_ENVIRONMENT=/opt/worker-venv \
    PATH=/opt/worker-venv/bin:$PATH \
    UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
COPY plugin ./plugin
RUN uv sync --locked --extra dev --no-install-project
COPY . .
