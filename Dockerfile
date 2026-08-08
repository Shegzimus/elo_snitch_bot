ARG AIRFLOW_VERSION=3.0.2
ARG PYTHON_VERSION=3.11

FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

# AIRFLOW_HOME (/opt/airflow) and the airflow user (uid 50000) are already set
# by the base image. The previous ARG AIRFLOW_UID=${AIRFLOW_UID} /
# ENV AIRFLOW_HOME=${AIRFLOW_HOME} pair was self-referential, resolved to empty,
# and left WORKDIR pointing at /.

USER root

# psql for the migrations in sql/migrations/
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# pip must run as airflow, not root: the base image installs into that user's
# environment, and root-owned site-packages break at runtime.
USER airflow

# Project dependencies only -- see the header of the requirements file.
#
# Installed against Airflow's official constraints so pip cannot move a package
# the Airflow install depends on. Without this, pinning pandas/SQLAlchemy to the
# local venv's versions pulls SQLAlchemy to 2.0 and breaks apache-airflow-core,
# flask-appbuilder and marshmallow-sqlalchemy, which all require <2.0.
ARG AIRFLOW_VERSION
ARG PYTHON_VERSION
COPY --chown=airflow:root config/requirements.project.txt /tmp/requirements.project.txt
RUN pip install --no-cache-dir -r /tmp/requirements.project.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# DAGs are bind-mounted by docker-compose in local dev; baking them in keeps the
# image usable on its own. src/python is copied because the DAG tasks execute
# those scripts.
COPY --chown=airflow:root dags/ ${AIRFLOW_HOME}/dags/
COPY --chown=airflow:root src/python/ ${AIRFLOW_HOME}/src/python/

WORKDIR ${AIRFLOW_HOME}
