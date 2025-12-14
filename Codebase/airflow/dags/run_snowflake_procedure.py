"""
Airflow DAG to execute a Snowflake Stored Procedure.

This DAG uses the SnowflakeOperator to call a stored procedure.
It relies on the 'snowflake_default' connection being configured (which is handled by scraper.py or manually).
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="06_run_snowflake_procedure",
    default_args=default_args,
    description="Execute a specific Snowflake stored procedure",
    schedule_interval=None,  # Manual trigger
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["snowflake", "procedure"],
) as dag:

    call_procedure = SnowflakeOperator(
        task_id="call_stored_procedure",
        snowflake_conn_id="snowflake_default",
        # REPLACE WITH YOUR PROCEDURE CALL
        # Example: CALL TED_DB.TED_SCHEMA.PROCESS_LOGS();
        sql="CALL TED_DB.SEMANTIC.REFRESH_TED_EMBEDDINGS();",
        # You can also pass parameters dynamically if needed
    )

    call_procedure
