"""
Airflow DAG for granular execution of dbt models.

This DAG runs models one by one, allowing for finer control and debugging.
Models are executed in a logical sequence:
1. Talks (Metadata)
2. Transcripts (Content)
3. Chunks (Vector embedding preparation)
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="04_dbt_granular_execution",
    description="Run dbt models one by one",
    default_args=default_args,
    schedule_interval=None,  # distinct from daily run, manual trigger primarily
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["dbt", "snowflake", "granular"],
) as dag:

    # 1. Run stg_ted_talks
    run_talks = BashOperator(
        task_id="run_stg_ted_talks",
        bash_command="cd /opt/airflow/dbt && dbt run --select stg_ted_talks --profiles-dir /opt/airflow/dbt/profiles",
        doc_md="Run only the talks staging model"
    )

    # 2. Run stg_ted_transcripts
    run_transcripts = BashOperator(
        task_id="run_stg_ted_transcripts",
        bash_command="cd /opt/airflow/dbt && dbt run --select stg_ted_transcripts --profiles-dir /opt/airflow/dbt/profiles",
        doc_md="Run only the transcripts staging model"
    )

    # 3. Run stg_ted_transcript_chunks
    # This likely depends on transcripts being clean
    run_chunks = BashOperator(
        task_id="run_stg_ted_transcript_chunks",
        bash_command="cd /opt/airflow/dbt && dbt run --select stg_ted_transcript_chunks --profiles-dir /opt/airflow/dbt/profiles",
        doc_md="Run the chunking model for vector embeddings"
    )

    # 4. Optional: Run tests for each independently? 
    # For now, let's keep it simple and just run logic. 
    # We can add a final test all task.
    test_all = BashOperator(
        task_id="test_all_models",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir /opt/airflow/dbt/profiles",
        doc_md="Run all tests after individual model runs"
    )

    # Set dependencies
    # We assume chunks depends on transcripts. Talks is likely independent but good practice to load first.
    run_talks >> run_transcripts >> run_chunks >> test_all
