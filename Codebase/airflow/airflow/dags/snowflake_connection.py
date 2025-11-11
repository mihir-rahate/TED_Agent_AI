import snowflake.connector
import os
from dotenv import load_dotenv


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
# Load environment variables
load_dotenv()

def get_snowflake_connection():
    """Get Snowflake connection using environment variables"""
    try:
        conn = snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),  # This is your PAT token
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA")
        )
        return conn
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

def call_cortex_complete(prompt: str, model: str = 'claude-3-5-sonnet') -> str:
    """
    Call Snowflake Cortex Complete function with specified model
    
    Args:
        prompt: The prompt to send to the model
        model: The model to use (default: claude-3-5-sonnet)

    Returns:
        Generated response from the model
    """
    conn = get_snowflake_connection()
    if not conn:
        return "Connection failed"
    
    try:
        cursor = conn.cursor()
        
        # Escape single quotes
        escaped_prompt = prompt.replace("'", "''")
        
        query = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            '{model}',
            '{escaped_prompt}'
        ) as result
        """
        
        cursor.execute(query)
        result = cursor.fetchone()
        return result[0] if result else "No result"
    except Exception as e:
        return f"Error with model {model}: {e}"
    finally:
        conn.close()


        
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

create_snowflake_tables()