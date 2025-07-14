from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 12),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Create the DAG
dag = DAG(
    'elo_pipeline',
    default_args=default_args,
    description='ELO tracking pipeline',
    schedule_interval=timedelta(hours=1),
    catchup=False
)

# Define the Python functions for each task
def fetch_google_forms_data():
    """Execute fetch_google_forms_data.py"""
    os.system('python fetch_google_forms_data.py')

def generate_puuid():
    """Execute generate_puuid.py"""
    os.system('python generate_puuid.py')

def check_elo():
    """Execute elo_check.py"""
    os.system('python elo_check.py')

def track_elo():
    """Execute elo_tracker.py"""
    os.system('python elo_tracker.py')

# Create the tasks
task_fetch_google_forms = PythonOperator(
    task_id='fetch_google_forms_data',
    python_callable=fetch_google_forms_data,
    dag=dag
)

task_generate_puuid = PythonOperator(
    task_id='generate_puuid',
    python_callable=generate_puuid,
    dag=dag
)

task_check_elo = PythonOperator(
    task_id='check_elo',
    python_callable=check_elo,
    dag=dag
)

task_track_elo = PythonOperator(
    task_id='track_elo',
    python_callable=track_elo,
    dag=dag
)

# Set task dependencies
task_fetch_google_forms >> task_generate_puuid >> task_check_elo >> task_track_elo
