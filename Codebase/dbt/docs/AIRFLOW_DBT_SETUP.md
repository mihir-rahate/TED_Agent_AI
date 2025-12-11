# Airflow Setup & dbt Orchestration Guide

## Overview
You now have a complete Airflow DAG (`airflow/dags/dbt_snowflake_dag.py`) that orchestrates dbt models on Snowflake. The DAG includes:
- **dbt debug**: Validates Snowflake connection and dbt configuration.
- **dbt run**: Executes dbt models tagged with `tag:daily` (customize as needed).
- **dbt test**: Runs all dbt tests defined in your models.
- **dbt docs generate**: Generates dbt documentation for reference.

## Setup Instructions

### 1. Install Airflow & dbt Dependencies
Update `airflow/requirements.txt` with:
```
apache-airflow==2.6.3
apache-airflow-providers-snowflake==3.3.0
dbt-core==1.4.0
dbt-snowflake==1.4.0
snowflake-connector-python==3.1.4
python-dotenv==1.0.0
cryptography==41.0.3
```

Then install:
```powershell
pip install -r airflow/requirements.txt
```

### 2. Set Up Airflow Environment
Initialize Airflow database and create a user:
```powershell
# Set Airflow home (optional, defaults to ~/airflow)
$env:AIRFLOW_HOME = "C:\path\to\ted_ai_project\airflow"

# Initialize the database
airflow db init

# Create an Airflow user
airflow users create `
  --username admin `
  --firstname Admin `
  --lastname User `
  --role Admin `
  --email admin@example.com `
  --password admin_password
```

### 3. Configure Airflow Connection to Snowflake (Optional)
You can add a Snowflake connection in the Airflow UI or CLI:
```powershell
airflow connections add \
  --conn-type snowflake \
  --conn-host <SNOWFLAKE_ACCOUNT> \
  --conn-user <SNOWFLAKE_USER> \
  --conn-password <SNOWFLAKE_PASSWORD> \
  --conn-schema <SNOWFLAKE_SCHEMA> \
  --conn-extra '{"warehouse": "<SNOWFLAKE_WAREHOUSE>", "database": "<SNOWFLAKE_DATABASE>"}' \
  snowflake_conn
```

### 4. Ensure dbt Profiles Are Accessible
The DAG assumes:
- `dbt/profiles.yml` is configured with your Snowflake connection (using key-pair or password auth).
- Environment variables from `.env` are loaded (set `SNOWFLAKE_PRIVATE_KEY_PATH` and `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` if using key-pair).
- The DAG runs in a context where `/app/dbt/` is accessible (set `DBT_PROFILES_DIR=/app/dbt`).

### 5. Place the DAG in Airflow's DAG Folder
The DAG file `airflow/dags/dbt_snowflake_dag.py` should be in Airflow's DAGs directory:
- Default: `~/airflow/dags/`
- Or set `AIRFLOW__CORE__DAGS_FOLDER` env var to point to your `airflow/dags/` folder.

Example:
```powershell
# Copy or link the DAG
Copy-Item "airflow/dags/dbt_snowflake_dag.py" "$env:AIRFLOW_HOME/dags/"
```

### 6. Start Airflow Services
```powershell
# Start the web server (in one terminal)
airflow webserver --port 8080

# In another terminal, start the scheduler
airflow scheduler
```

Open the Airflow UI at `http://localhost:8080` and log in with the credentials you created.

### 7. Trigger the DAG
- In the Airflow UI, find `dbt_snowflake_orchestration` and click the play button to trigger a run.
- Or from CLI:
  ```powershell
  airflow dags trigger dbt_snowflake_orchestration
  ```

## DAG Task Flow
```
dbt_debug → dbt_run → dbt_test → dbt_docs_generate
```

- If `dbt_debug` fails, subsequent tasks won't run (connection issue).
- `dbt_docs_generate` runs regardless of prior task outcomes (TriggerRule: ALL_DONE) for documentation purposes.

## Customization

### Run Specific Models
Edit the `dbt_run` task bash_command to select specific models:
```python
bash_command="cd /app && dbt run --profiles-dir dbt --select stg_* marts.*",
```

### Run with Different Tags
If your dbt models have tags (e.g., `daily`, `weekly`):
```python
bash_command="cd /app && dbt run --profiles-dir dbt --select tag:weekly",
```

### Add More Tasks
Add additional BashOperator tasks for other dbt commands (e.g., `dbt snapshot`, `dbt seed`):
```python
dbt_snapshot = BashOperator(
    task_id="dbt_snapshot",
    bash_command="cd /app && dbt snapshot --profiles-dir dbt",
    dag=dag,
)
```

## Troubleshooting

### DAG Not Appearing in Airflow UI
- Ensure the file is in the correct DAGs folder (check `AIRFLOW__CORE__DAGS_FOLDER`).
- Check Airflow scheduler logs for syntax errors.
- Restart the scheduler: `airflow scheduler stop && airflow scheduler`.

### dbt Debug Task Fails
- Verify `dbt/profiles.yml` is correct and `dbt/snowflake_key.pem` is accessible.
- Ensure Snowflake credentials in `.env` are correct.
- Run `dbt debug --profiles-dir dbt` manually to see the exact error.

### dbt Run Task Fails
- Check dbt model syntax and SQL errors.
- Verify Snowflake tables/schemas exist.
- Review Airflow task logs in the UI (click the task → Logs).

### Import Errors in DAG
- Ensure `apache-airflow` is installed: `pip install apache-airflow==2.6.3`.
- Verify Python environment has Airflow installed: `python -m airflow --version`.

## Docker Usage (Optional)

If you prefer running Airflow in Docker:
```powershell
cd ted_ai_project
docker compose up -d airflow
docker compose run --rm airflow airflow db init
docker compose run --rm airflow airflow users create --username admin --role Admin --email admin@example.com --firstname Admin --lastname User --password admin_password
```

Then access Airflow at `http://localhost:8080`.
