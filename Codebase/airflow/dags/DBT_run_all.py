"""Airflow DAG for TED Talks ETL with dbt orchestration.

This DAG orchestrates:
1. Scraping TED talks data
2. Cleaning transcripts
3. Loading to Snowflake
4. Running dbt models for transformation
5. Running dbt tests for data quality
"""
from datetime import datetime, timedelta
import sys
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.trigger_rule import TriggerRule

# Add parent directory to path for imports
sys.path.insert(0, "/opt/airflow")

from scripts.scrape_ted import scrape
from scripts.clean_transcript import clean_transcripts
from scripts.loader_support import load_to_snowflake

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="dbt_run_all",
    default_args=default_args,
    description="Scrape TED talks, clean transcripts, load to Snowflake, and run dbt models",
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["ted", "etl", "dbt", "snowflake"],
) as dag:

    # ETL Tasks
    scrape_task = PythonOperator(
        task_id="scrape_ted_talks",
        python_callable=scrape,
        doc_md="Scrape TED talks data from source"
    )

    clean_task = PythonOperator(
        task_id="clean_transcripts",
        python_callable=clean_transcripts,
        doc_md="Clean and normalize transcript text"
    )

    load_task = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=load_to_snowflake,
        doc_md="Load cleaned data to Snowflake raw tables"
    )

    # dbt Tasks
    dbt_debug_task = BashOperator(
        task_id="dbt_debug",
        bash_command="cd /opt/airflow/dbt && dbt debug --profiles-dir /opt/airflow/dbt/profiles",
        doc_md="Validate dbt project setup and Snowflake connection"
    )

    dbt_run_task = BashOperator(
        task_id="dbt_run_models",
        bash_command="cd /opt/airflow/dbt && dbt run --profiles-dir /opt/airflow/dbt/profiles",
        doc_md="Execute dbt models to transform raw data into staging/mart layers"
    )

    dbt_test_task = BashOperator(
        task_id="dbt_test_data_quality",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir /opt/airflow/dbt/profiles",
        doc_md="Run dbt tests to validate data quality and integrity"
    )

    dbt_docs_task = BashOperator(
        task_id="dbt_generate_docs",
        bash_command="cd /opt/airflow/dbt && dbt docs generate --profiles-dir /opt/airflow/dbt/profiles",
        trigger_rule=TriggerRule.ALL_DONE,
        doc_md="Generate dbt documentation (manifest, catalog)"
    )

    # Task Dependencies
    # ETL pipeline: scrape -> clean -> load
    scrape_task >> clean_task >> load_task
    
    # After raw data is loaded, run dbt transformations
    load_task >> dbt_debug_task >> dbt_run_task >> dbt_test_task >> dbt_docs_task
