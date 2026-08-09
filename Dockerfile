ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim

# psql for migrations in sql/migrations/
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY config/requirements.project.txt /tmp/requirements.project.txt
RUN pip install --no-cache-dir -r /tmp/requirements.project.txt

COPY src/python/ /app/src/python/
WORKDIR /app
