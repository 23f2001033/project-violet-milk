# Project Violet Milk - single container, single port.
#
# The application already serves the built SPA from the same FastAPI process
# (see _mount_frontend at the bottom of backend/app/main.py), so hosting is one
# image rather than a frontend and a backend that have to find each other.
#
# Three stages: build the SPA, build the Python environment, then a runtime
# that carries neither Node nor a compiler.

# --------------------------------------------------------------- build the SPA
FROM node:22-slim AS frontend

WORKDIR /build/frontend

# Manifests first, so a source-only change does not reinstall every dependency.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# VITE_USE_MOCKS is deliberately NOT set. api.js treats anything other than the
# string "true" as live, so the deployed app talks to the real engines. Setting
# it here would ship fixtures dressed up as a working system.
RUN npm run build


# ------------------------------------------------- build the Python environment
# Several dependencies - ckzg, bitarray, cytoolz, pycryptodome, regex - have
# historically shipped incomplete manylinux wheel coverage. Without a compiler
# available, a single missing wheel fails the whole build with a gcc error
# halfway through a deploy. Building in a stage that HAS a toolchain removes
# that class of failure; the toolchain is then left behind.
FROM python:3.11-slim AS pybuild

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


# ------------------------------------------------------------------- runtime
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=pybuild /opt/venv /opt/venv

WORKDIR /app

# The committed live_cache and ai_cache travel with the image, which is what
# makes LIVE_CACHE_FIRST work on a host with no persistent disk.
COPY backend/ ./backend/
COPY --from=frontend /build/frontend/dist ./frontend/dist

# Written to at runtime. Without a mounted disk these are ephemeral - the demo
# case re-seeds itself at import, so a restart is self-healing.
RUN mkdir -p backend/generated_reports backend/app/data/anchors

EXPOSE 8000

# Render and most container hosts inject $PORT. Defaulting to 8000 keeps the
# same image runnable locally with `docker run -p 8000:8000`.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
