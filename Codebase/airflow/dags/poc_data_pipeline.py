from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
import pandas as pd
import json
import boto3
import logging
import snowflake.connector
import gzip
import csv
import base64
from cryptography.hazmat.primitives import serialization

# Configuration
# Ideally these are in Airflow Variables/Connections, but keeping inline for PoC as requested
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")

# Snowflake Config - Use Environment Variables (Best Practice)
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")
SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE")

# Paths
DAG_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(DAG_FOLDER, '..', '..'))
POC_DATA_PATH = os.path.join(PROJECT_ROOT, 'airflow', 'PoC', 'ted_talks_transcripts_updated.csv')
KEY_PATH = os.path.join(DAG_FOLDER, 'snowflake_key.pem')

def get_snowflake_conn():
    try:
        with open(KEY_PATH, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
            )
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        conn = snowflake.connector.connect(
            account=SNOWFLAKE_ACCOUNT,
            user=SNOWFLAKE_USER,
            private_key=private_key_bytes,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA,
            role=SNOWFLAKE_ROLE
        )
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to Snowflake: {e}")
        raise

def upload_to_s3(**context):
    logging.info("Starting S3 upload...")
    if not os.path.exists(POC_DATA_PATH):
        raise FileNotFoundError(f"File not found: {POC_DATA_PATH}")

    df = pd.read_csv(POC_DATA_PATH)
    logging.info(f"Loaded {len(df)} records for S3 upload")
    
    df.columns = df.columns.str.strip().str.lower()
    
    if "transcript" not in df.columns:
        logging.warning("No 'transcript' column found - skipping S3 upload")
        return

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    upload_count = 0
    for index, row in df.iterrows():
        try:
            if pd.isna(row.get("transcript")) or not row.get("transcript"):
                continue

            metadata = {
                "id": str(row["id"]) if "id" in row and not pd.isna(row["id"]) else None,
                "slug": row["slug"] if "slug" in row and not pd.isna(row["slug"]) else None,
                "speakers": row["speakers"] if "speakers" in row and not pd.isna(row["speakers"]) else None,
                "title": row["title"] if "title" in row and not pd.isna(row["title"]) else None,
                "url": row["url"] if "url" in row and not pd.isna(row["url"]) else None,
                "transcript": row["transcript"] if "transcript" in row and not pd.isna(row["transcript"]) else None,
            }

            folder_name = row["slug"] if "slug" in row and not pd.isna(row["slug"]) else f"talk_{row['id']}"
            file_name = "metadata.json"
            json_data = json.dumps(metadata, indent=4, ensure_ascii=False)
            
            s3_path = f"ted-transcripts/{folder_name}/{file_name}"
            
            s3_client.put_object(
                Bucket=S3_BUCKET, 
                Key=s3_path, 
                Body=json_data,
                ContentType='application/json'
            )
            upload_count += 1
            if upload_count % 100 == 0:
                logging.info(f"Uploaded {upload_count} files...")
                
        except Exception as e:
            logging.error(f"Error uploading talk {index}: {e}")
            continue

    logging.info(f"S3 upload completed. Uploaded {upload_count} files")

def load_to_snowflake(**context):
    logging.info("Starting Snowflake load...")
    if not os.path.exists(POC_DATA_PATH):
        raise FileNotFoundError(f"File not found: {POC_DATA_PATH}")

    df = pd.read_csv(POC_DATA_PATH, dtype=str)
    logging.info(f"Loaded {len(df)} records for Snowflake")

    df.columns = df.columns.str.strip().str.lower()
    required_cols = ['id', 'slug', 'speakers', 'title', 'url', 'transcript']
    
    for c in required_cols:
        if c not in df.columns:
            df[c] = ''

    for col in required_cols:
        df[col] = df[col].fillna('').astype(str).replace('nan', '')

    # Create temporary gzip file
    gz_file = os.path.join(os.path.dirname(POC_DATA_PATH), 'ted_talks_poc_load.csv.gz')
    
    with gzip.open(gz_file, "wt", newline='', encoding='utf-8') as gz:
        writer = csv.writer(gz, quoting=csv.QUOTE_ALL, escapechar='\\')
        writer.writerow(required_cols)
        for _, row in df[required_cols].iterrows():
            writer.writerow([row[col] for col in required_cols])
            
    logging.info(f"Created gzipped CSV: {gz_file}")

    conn = get_snowflake_conn()
    cursor = conn.cursor()
    
    try:
        # 1. Create Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS TED_DB.TED_SCHEMA.ted_talks (
            id VARCHAR(50) PRIMARY KEY,
            slug VARCHAR(255),
            title VARCHAR(500),
            speakers VARCHAR(500),
            url VARCHAR(500),
            transcript TEXT,
            embedding VECTOR(FLOAT, 768),
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        );
        """)
        
        # 2. Create Format
        cursor.execute("""
        CREATE OR REPLACE FILE FORMAT TED_DB.TED_SCHEMA.TED_CSV_FORMAT
        TYPE = 'CSV'
        FIELD_DELIMITER = ','
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        SKIP_HEADER = 1
        ESCAPE = '\\\\'
        TRIM_SPACE = TRUE
        NULL_IF = ('', 'NULL');
        """)
        
        # 3. Create Stage
        cursor.execute("""
        CREATE OR REPLACE STAGE TED_DB.TED_SCHEMA.ted_stage
        COMMENT = 'Stage for TED transcripts uploads';
        """)

        # 4. PUT
        # Use abs path for proper PUT command
        put_stmt = f"PUT file://{gz_file} @TED_DB.TED_SCHEMA.ted_stage AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        cursor.execute(put_stmt)
        logging.info("PUT file to stage complete")

        # 5. COPY
        copy_sql = """
        COPY INTO TED_DB.TED_SCHEMA.ted_talks (id, slug, speakers, title, url, transcript)
        FROM @TED_DB.TED_SCHEMA.ted_stage
        PATTERN = '.*ted_talks_poc_load\\.csv\\.gz$'
        FILE_FORMAT = (FORMAT_NAME = 'TED_DB.TED_SCHEMA.TED_CSV_FORMAT')
        ON_ERROR = 'CONTINUE';
        """
        cursor.execute(copy_sql)
        logging.info("COPY INTO executed")
        
    finally:
        cursor.close()
        conn.close()
        # Cleanup
        if os.path.exists(gz_file):
            os.remove(gz_file)

# Define DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    '00_poc_data_pipeline',
    default_args=default_args,
    description='One-time load of PoC data to S3 and Snowflake',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['poc', 'snowflake', 's3'],
) as dag:

    t1 = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_to_s3,
    )

    t2 = PythonOperator(
        task_id='load_to_snowflake',
        python_callable=load_to_snowflake,
    )

    [t1, t2]
