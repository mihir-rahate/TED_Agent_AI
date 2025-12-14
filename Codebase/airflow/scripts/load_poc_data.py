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
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Data Path
POC_DATA_PATH = r"C:\Users\mihir\OneDrive\Desktop\NEU\Sem 4\TED_AI - DAMG\ted_ai_project\airflow\PoC\ted_talks_transcripts_updated.csv"

# AWS Config
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")

# Snowflake Config
SNOWFLAKE_ACCOUNT = 'VOB68402'
SNOWFLAKE_USER = 'GIRAFFE'
SNOWFLAKE_WAREHOUSE = 'TED_AGENT_WH'
SNOWFLAKE_DATABASE = 'TED_DB'
SNOWFLAKE_SCHEMA = 'TED_SCHEMA'
SNOWFLAKE_ROLE = 'TRAINING_ROLE'
KEY_PATH = r"C:\Users\mihir\OneDrive\Desktop\NEU\Sem 4\TED_AI - DAMG\ted_ai_project\airflow\dags\snowflake_key.pem"

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

def upload_to_s3():
    logging.info("Starting S3 upload...")
    if not os.path.exists(POC_DATA_PATH):
        logging.error(f"File not found: {POC_DATA_PATH}")
        return

    df = pd.read_csv(POC_DATA_PATH)
    logging.info(f"Loaded {len(df)} records for S3 upload")
    
    df.columns = df.columns.str.strip().str.lower()
    
    if "transcript" not in df.columns:
        logging.warning("No 'transcript' column found")
        # Check if we can proceed without it or map it?? 
        # For now assume scraper logic which skips no transcript
    
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    upload_count = 0
    for index, row in df.iterrows():
        try:
            # Prepare metadata
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

def load_to_snowflake():
    logging.info("Starting Snowflake load...")
    if not os.path.exists(POC_DATA_PATH):
        logging.error(f"File not found: {POC_DATA_PATH}")
        return

    df = pd.read_csv(POC_DATA_PATH, dtype=str)
    logging.info(f"Loaded {len(df)} records for Snowflake")

    df.columns = df.columns.str.strip().str.lower()
    required_cols = ['id', 'slug', 'speakers', 'title', 'url', 'transcript']
    
    # Ensure columns exist
    for c in required_cols:
        if c not in df.columns:
            df[c] = ''

    # Clean data
    for col in required_cols:
        df[col] = df[col].fillna('').astype(str).replace('nan', '')

    # Gzip
    gz_file = 'ted_talks_poc_load.csv.gz'
    with gzip.open(gz_file, "wt", newline='', encoding='utf-8') as gz:
        writer = csv.writer(gz, quoting=csv.QUOTE_ALL, escapechar='\\')
        writer.writerow(required_cols)
        for _, row in df[required_cols].iterrows():
            writer.writerow([row[col] for col in required_cols])
            
    logging.info(f"Created gzipped CSV: {gz_file}")

    conn = get_snowflake_conn()
    cursor = conn.cursor()
    
    try:
        # Create Table if not exists
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
        
        # Create File Format
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
        
        # Create Stage
        cursor.execute("""
        CREATE OR REPLACE STAGE TED_DB.TED_SCHEMA.ted_stage
        COMMENT = 'Stage for TED transcripts uploads';
        """)

        # PUT
        put_stmt = f"PUT file://{os.path.abspath(gz_file)} @TED_DB.TED_SCHEMA.ted_stage AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        cursor.execute(put_stmt)
        logging.info("PUT file to stage complete")

        # COPY
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
        if os.path.exists(gz_file):
            os.remove(gz_file)

if __name__ == "__main__":
    # Uncomment to run
    # upload_to_s3()
    load_to_snowflake()
