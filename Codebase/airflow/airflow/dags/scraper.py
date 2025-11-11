from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from airflow.models import Connection
from airflow import settings
from datetime import datetime, timedelta
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import json
import boto3
import logging
import snowflake.connector

# Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")

# Global variables
max_page = 10  # Reduced for testing
sleep_time = 2
import base64
from cryptography.hazmat.primitives import serialization

def create_snowflake_connection():
    """Create or update Snowflake connection using key-pair authentication"""
    try:
        dag_directory = "/opt/airflow/dags"
        key_path = os.path.join(dag_directory, 'snowflake_key.pem')

        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Private key not found: {key_path}")

        # 🔑 Load private key and convert to DER bytes
        with open(key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,  # or provide passphrase if encrypted
            )

        private_key_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Encode to base64 so we can safely store it in Airflow connection
        private_key_b64 = base64.b64encode(private_key_der).decode("utf-8")

        conn = Connection(
            conn_id="snowflake_default",
            conn_type="snowflake",
            host="SFEDU02-VOB68402.snowflakecomputing.com",
            login="GIRAFFE",
            schema="TED_SCHEMA",
            extra=json.dumps({
                "account": "VOB68402",
                "warehouse": "TED_AGENT_WH",
                "database": "TED_DB",
                "schema": "TED_SCHEMA",
                "role": "TRAINING_ROLE",
                "private_key": private_key_b64,  # ✅ base64-encoded DER
            })
        )

        session = settings.Session()
        existing_conn = session.query(Connection).filter(Connection.conn_id == conn.conn_id).first()
        if existing_conn:
            existing_conn.conn_type = conn.conn_type
            existing_conn.host = conn.host
            existing_conn.login = conn.login
            existing_conn.schema = conn.schema
            existing_conn.extra = conn.extra
            print(f"🔁 Updated existing connection: {conn.conn_id}")
        else:
            session.add(conn)
            print(f"✅ Created new connection: {conn.conn_id}")

        session.commit()
        session.close()

    except Exception as e:
        print(f"❌ Error creating Snowflake connection: {e}")
        raise

#PAT connection
def create_snowflake_pat_connection():
    """Create or update Snowflake connection using Programmatic Access Token"""
    try:
        # ⚙️ Load token securely from environment variables or mounted secret
        # Recommended env var names: SNOWFLAKE_ACCESS_TOKEN or SNOWFLAKE_PAT
        access_token = os.getenv("SNOWFLAKE_ACCESS_TOKEN") or os.getenv("SNOWFLAKE_PAT")
        if not access_token:
            raise ValueError("Access token not found. Set SNOWFLAKE_ACCESS_TOKEN or SNOWFLAKE_PAT environment variable.")

        conn = Connection(
            conn_id="snowflake_default",
            conn_type="snowflake",
            host="SFEDU02-VOB68402.snowflakecomputing.com",
            login="GIRAFFE",
            schema="TED_SCHEMA",
            password=access_token,
            extra=json.dumps({
                "account": "SFEDU02-VOB68402",
                "warehouse": "TED_AGENT_WH",
                "database": "TED_DB",
                "schema": "TED_SCHEMA",
                "role": "TRAINING_ROLE",
                "authenticator": "oauth",
                "token": access_token
            })
        )

        session = settings.Session()
        existing_conn = session.query(Connection).filter(Connection.conn_id == conn.conn_id).first()

        if existing_conn:
            existing_conn.conn_type = conn.conn_type
            existing_conn.host = conn.host
            existing_conn.login = conn.login
            existing_conn.schema = conn.schema
            existing_conn.extra = conn.extra
            print(f"🔁 Updated existing connection: {conn.conn_id}")
        else:
            session.add(conn)
            print(f"✅ Created new connection: {conn.conn_id}")

        session.commit()
        session.close()

    except Exception as e:
        print(f"❌ Error creating Snowflake PAT connection: {e}")
        raise




# def create_snowflake_connection():
#     """Get Snowflake connection using environment variables"""
#     try:
#         conn = snowflake.connector.connect(
#             user=os.getenv("SNOWFLAKE_USER"),
#             password=os.getenv("SNOWFLAKE_PASSWORD"),  # This is your PAT token
#             account=os.getenv("SNOWFLAKE_ACCOUNT"),
#             warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
#             database=os.getenv("SNOWFLAKE_DATABASE"),
#             schema=os.getenv("SNOWFLAKE_SCHEMA")
#         )
#         return conn
#     except Exception as e:
#         print(f"Connection failed: {e}")
#         return None

# def call_cortex_complete(prompt: str, model: str = 'claude-3-5-sonnet') -> str:
#     """
#     Call Snowflake Cortex Complete function with specified model
    
#     Args:
#         prompt: The prompt to send to the model
#         model: The model to use (default: claude-3-5-sonnet)

#     Returns:
#         Generated response from the model
#     """
#     conn = create_snowflake_connection()
#     if not conn:
#         return "Connection failed"
    
#     try:
#         cursor = conn.cursor()
        
#         # Escape single quotes
#         escaped_prompt = prompt.replace("'", "''")
        
#         query = f"""
#         SELECT SNOWFLAKE.CORTEX.COMPLETE(
#             '{model}',
#             '{escaped_prompt}'
#         ) as result
#         """
        
#         cursor.execute(query)
#         result = cursor.fetchone()
#         return result[0] if result else "No result"
#     except Exception as e:
#         return f"Error with model {model}: {e}"
#     finally:
#         conn.close()

def test_snowflake_connection():
    """Test Snowflake connection before creating tables"""
    try:
        logging.info("Testing Snowflake connection...")
        
        hook = SnowflakeHook(snowflake_conn_id='snowflake_default')
        
        # Test with a simple query
        result = hook.get_first("SELECT CURRENT_VERSION()")
        logging.info(f"✅ Snowflake connection successful! Version: {result[0]}")
        
        # Test database access
        result = hook.get_first("SHOW DATABASES LIKE 'TED_DB'")
        if result:
            logging.info(f"✅ TED_DB exists: {result}")
        else:
            logging.info("ℹ️ TED_DB doesn't exist yet")
            
        return True
        
    except Exception as e:
        logging.error(f"❌ Snowflake connection failed: {e}")
        raise

def create_snowflake_tables():
    """Create Snowflake tables with proper error handling"""
    try:
        hook = SnowflakeHook(snowflake_conn_id='snowflake_default')
        
        # Create schema if it doesn't exist
        create_schema_sql = """
        CREATE SCHEMA IF NOT EXISTS TED_DB.TED_SCHEMA;
        """
        hook.run(create_schema_sql)
        logging.info("Successfully created/verified schema")
        
        # Create main talks table
        create_talks_table_sql = """
        CREATE TABLE IF NOT EXISTS TED_DB.TED_SCHEMA.ted_talks (
            id VARCHAR(50) PRIMARY KEY,
            slug VARCHAR(255),
            title VARCHAR(500),
            speakers VARCHAR(500),
            url VARCHAR(500),
            transcript TEXT,                                      
            loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
        """
        hook.run(create_talks_table_sql)
        logging.info("Successfully created/verified ted_talks table")
        
        # Create stage for file uploads
        create_stage_sql = """
        CREATE STAGE IF NOT EXISTS TED_DB.TED_SCHEMA.ted_stage 
        FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);
        """
        hook.run(create_stage_sql)
        logging.info("Successfully created/verified ted_stage")
        
    except Exception as e:
        logging.error(f"Failed to create Snowflake tables: {e}")
        raise

def scrape_ted_talks():
    """Scrape TED Talks metadata using only API"""
    logging.info("Starting TED Talks scraping via API...")
    
    final = []
    
    for page in range(0, max_page):
        logging.info(f"Scraping page {page + 1}/{max_page}")
        
        payload = [{
            "indexName": "newest",
            "params": {
                "attributeForDistinct": "objectID",
                "distinct": 1,
                "facets": ["subtitle_languages", "tags"],
                "highlightPostTag": "__/ais-highlight__",
                "highlightPreTag": "__ais-highlight__",
                "hitsPerPage": 24,
                "maxValuesPerFacet": 500,
                "page": page,
                "query": "",
                "tagFilters": ""
            }
        }]

        try:
            response = requests.post(
                'https://zenith-prod-alt.ted.com/api/search',
                headers={
                    'Content-type': 'application/json; charset=UTF-8',
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                my_tedx = response.json()['results'][0]["hits"]
                final.extend(my_tedx)
                logging.info(f"Page {page + 1}: Found {len(my_tedx)} talks")
            else:
                logging.warning(f"Page {page + 1}: HTTP {response.status_code}")
                
        except requests.RequestException as e:
            logging.error(f"Page {page + 1}: Request failed - {e}")
            continue
            
        time.sleep(sleep_time)

    # Process the results
    final_list = []
    for talk in final:
        try:
            slug = talk["slug"]
            speakers = talk["speakers"]
            if isinstance(speakers, list):
                speakers = ", ".join(speakers)
            
            final_list.append({
                'id': str(talk["objectID"]),
                'slug': str(talk["slug"]),
                'speakers': str(speakers),
                'title': str(talk["title"]),
                'url': f'https://www.ted.com/talks/{slug}'
            })
        except KeyError as e:
            logging.warning(f"Missing key in talk data: {e}")
            continue

    # Save to file
    if final_list:
        df = pd.DataFrame(final_list)
        df.to_csv('/tmp/ted_talks_list.csv', index=False)
        logging.info(f"Successfully saved {len(final_list)} talks to /tmp/ted_talks_list.csv")
        
        # Print sample for debugging
        print("Sample data:")
        print(df.head(3).to_string())
    else:
        logging.warning("No talks were scraped")
        pd.DataFrame(columns=['id', 'slug', 'speakers', 'title', 'url']).to_csv('/tmp/ted_talks_list.csv', index=False)

def scrape_transcripts():
    """Scrape transcripts from TED talks"""
    logging.info("Starting transcript scraping...")
    
    try:
        if not os.path.exists('/tmp/ted_talks_list.csv'):
            logging.error("Input file not found")
            pd.DataFrame(columns=['id', 'slug', 'speakers', 'title', 'url', 'transcript']).to_csv('/tmp/ted_talks_transcripts_updated.csv', index=False)
            return
        
        df = pd.read_csv('/tmp/ted_talks_list.csv')
        logging.info(f"Loaded {len(df)} talks for transcript extraction")
        
        if "transcript" not in df.columns:
            df["transcript"] = ""

        def extract_transcript_from_page(url):
            try:
                response = requests.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }, timeout=30)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser")
                    
                    # Check JSON-LD
                    script_tag = soup.find("script", type="application/ld+json")
                    if script_tag:
                        try:
                            data = json.loads(script_tag.string)
                            transcript = data.get("transcript")
                            if transcript:
                                return transcript
                        except json.JSONDecodeError:
                            pass
                    
                    return ""  # Return empty if no transcript found
                    
                else:
                    logging.warning(f"HTTP {response.status_code} for {url}")
                    return ""
                    
            except Exception as e:
                logging.error(f"Error fetching transcript from {url}: {e}")
                return ""

        # Process transcripts
        for index, row in df.iterrows():
            if pd.isna(row.get("transcript")) or not row.get("transcript"):
                transcript = extract_transcript_from_page(row["url"])
                df.at[index, "transcript"] = transcript or ""
                
            if (index + 1) % 5 == 0:
                logging.info(f"Processed {index + 1}/{len(df)} talks")
                
            time.sleep(1)

        # Save results
        df.to_csv('/tmp/ted_talks_transcripts_updated.csv', index=False)
        logging.info(f"Transcript scraping completed. Saved {len(df)} records")
        
    except Exception as e:
        logging.error(f"Transcript scraping failed: {e}")
        raise

def upload_to_s3():
    """Upload transcripts to S3"""
    logging.info("Starting S3 upload...")
    
    try:
        if not os.path.exists('/tmp/ted_talks_transcripts_updated.csv'):
            logging.error("Input file not found")
            return
        
        df = pd.read_csv('/tmp/ted_talks_transcripts_updated.csv')
        logging.info(f"Loaded {len(df)} records for S3 upload")
        
        df.columns = df.columns.str.strip().str.lower()

        if "transcript" not in df.columns:
            logging.warning("No 'transcript' column found")
            return

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
                
                s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
                )
                
                s3_client.put_object(
                    Bucket=S3_BUCKET, 
                    Key=s3_path, 
                    Body=json_data,
                    ContentType='application/json'
                )
                upload_count += 1
                logging.info(f"Uploaded: {s3_path}")
                
            except Exception as e:
                logging.error(f"Error uploading talk {row.get('id', 'unknown')}: {e}")
                continue

        logging.info(f"S3 upload completed. Uploaded {upload_count} files")
        
    except Exception as e:
        logging.error(f"S3 upload failed: {e}")
        raise

def load_to_snowflake():
    """Load data into Snowflake"""
    logging.info("Starting Snowflake data load...")
    
    try:
        if not os.path.exists('/tmp/ted_talks_transcripts_updated.csv'):
            logging.error("Input file not found")
            return
        
        # Read the data
        df = pd.read_csv('/tmp/ted_talks_transcripts_updated.csv')
        logging.info(f"Loaded {len(df)} records for Snowflake")
        
        # Prepare data for Snowflake
        snowflake_df = df[['id', 'slug', 'title', 'speakers', 'url', 'transcript']].copy()
        
        # Ensure string types and handle NaN
        for col in snowflake_df.columns:
            snowflake_df[col] = snowflake_df[col].astype(str).replace('nan', '')
        
        # Save as CSV for Snowflake
        snowflake_file = '/tmp/ted_talks_for_snowflake.csv'
        snowflake_df.to_csv(snowflake_file, index=False, quoting=1)  # quoting=1 means quote all fields
        
        # Load to Snowflake
        hook = SnowflakeHook(snowflake_conn_id='snowflake_default')
        
        # First upload file to stage
        put_sql = f"PUT file://{snowflake_file} @TED_DB.TED_SCHEMA.ted_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
        hook.run(put_sql)
        logging.info("File uploaded to Snowflake stage")
        
        # Use COPY command for efficient loading
        copy_sql = """
        COPY INTO TED_DB.TED_SCHEMA.ted_talks (id, slug, title, speakers, url, transcript)
        FROM @TED_DB.TED_SCHEMA.ted_stage/ted_talks_for_snowflake.csv
        FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1)
        ON_ERROR = 'CONTINUE';
        """
        
        # Then copy into table
        result = hook.run(copy_sql)
        logging.info(f"COPY command executed: {result}")
        
        # Verify the load
        count_result = hook.get_first("SELECT COUNT(*) FROM TED_DB.TED_SCHEMA.ted_talks")
        logging.info(f"Total records in Snowflake: {count_result[0]}")
        
        # Show sample of loaded data
        sample_result = hook.get_pandas_df("SELECT id, slug, title FROM TED_DB.TED_SCHEMA.ted_talks LIMIT 5")
        logging.info(f"Sample loaded data:\n{sample_result}")
        
    except Exception as e:
        logging.error(f"Snowflake load failed: {e}")
        raise

# Define the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=3),
}

dag = DAG(
    'ted_talks_complete_pipeline',
    default_args=default_args,
    description='Complete TED Talks pipeline: Scrape → S3 → Snowflake',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2024, 12, 1),
    catchup=False,
    tags=['ted', 'snowflake', 'etl']
)

# Tasks
# create_connection_task = PythonOperator(
#     task_id='create_snowflake_pat_connection',
#     python_callable=create_snowflake_pat_connection,
#     dag=dag,
# )

# call_cortex_task = PythonOperator(
#     task_id= 'call_cortex_complete',
#     python_callable=call_cortex_complete
#     dag=dag
# )

# test_connection_task = PythonOperator(
#     task_id='test_snowflake_connection',
#     python_callable=test_snowflake_connection,
#     dag=dag,
# )

create_tables_task = PythonOperator(
    task_id='create_snowflake_tables',
    python_callable=create_snowflake_tables,
    dag=dag,
)

scrape_ted_talks_task = PythonOperator(
    task_id='scrape_ted_talks_metadata',
    python_callable=scrape_ted_talks,
    dag=dag,
)

scrape_transcripts_task = PythonOperator(
    task_id='scrape_ted_talks_transcripts',
    python_callable=scrape_transcripts,
    dag=dag,
)

upload_to_s3_task = PythonOperator(
    task_id='upload_transcripts_to_s3',
    python_callable=upload_to_s3,
    dag=dag,
)

load_to_snowflake_task = PythonOperator(
    task_id='load_data_to_snowflake',
    python_callable=load_to_snowflake,
    dag=dag,
)

# # Set up dependencies
# create_connection_task >> 

create_tables_task >> scrape_ted_talks_task >> scrape_transcripts_task
scrape_transcripts_task >> [upload_to_s3_task, load_to_snowflake_task]