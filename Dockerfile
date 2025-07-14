FROM apache/airflow:3.0.2-python3.11


ARG AIRFLOW_UID=${AIRFLOW_UID}

ENV AIRFLOW_HOME=${AIRFLOW_HOME}

WORKDIR $AIRFLOW_HOME

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project requirements
COPY requirements.project.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.project.txt

# Copy DAGs
COPY dags /opt/airflow/dags

USER airflow
