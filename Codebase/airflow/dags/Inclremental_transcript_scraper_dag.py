from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import logging
import os
import time

# --- Configuration ---
# SOURCE file containing video URLs (metadata only)
SOURCE_LIST_PATH = Variable.get("source_list_path", default_var="/opt/airflow/data/ted_talks_list.csv")

# DESTINATION file that will store transcripts (metadata + transcript column)
TRANSCRIPTS_PATH = Variable.get("transcripts_path", default_var="/opt/airflow/data/ted_talks_transcripts.csv")

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
}

def incremental_transcript_scraper():
    """
    Reads a source CSV of TED talks (with URLs).
    Reads an existing transcript CSV (if it exists).
    Identify missing transcripts.
    Scrapes ONLY the missing ones.
    Appends new data to the transcript CSV.
    """
    logging.info("Starting incremental transcript scraper...")
    
    # 1. Load Source List (URLs)
    if not os.path.exists(SOURCE_LIST_PATH):
        raise FileNotFoundError(f"Source file not found at {SOURCE_LIST_PATH}. Cannot scrape without URLs.")
    
    df_source = pd.read_csv(SOURCE_LIST_PATH)
    logging.info(f"Loaded {len(df_source)} talks from source list.")

    # 2. Load or Initialize Transcript File
    if os.path.exists(TRANSCRIPTS_PATH):
        df_transcripts = pd.read_csv(TRANSCRIPTS_PATH)
        logging.info(f"Loaded {len(df_transcripts)} existing transcripts.")
    else:
        # Create empty DataFrame with same columns as source + 'transcript'
        cols = list(df_source.columns)
        if 'transcript' not in cols:
            cols.append('transcript')
        df_transcripts = pd.DataFrame(columns=cols)
        logging.info("No existing transcript file found. Starting fresh.")

    # 3. Identify Missing Transcripts
    # Logic: Find IDs in df_source that are NOT in df_transcripts (or have empty transcript)
    
    # Ensure ID columns are strings for consistent merging
    df_source['id'] = df_source['id'].astype(str)
    # Ensure URL column is string
    if 'url' not in df_source.columns:
         raise ValueError("Source CSV must contain a 'url' column.")

    if not df_transcripts.empty:
        df_transcripts['id'] = df_transcripts['id'].astype(str)
        # Filter source to only those NOT in transcripts
        existing_ids = set(df_transcripts[df_transcripts['transcript'].str.len() > 0]['id'])
        talks_to_scrape = df_source[~df_source['id'].isin(existing_ids)].copy()
    else:
        talks_to_scrape = df_source.copy()

    logging.info(f"Found {len(talks_to_scrape)} talks that need transcripts.")

    if len(talks_to_scrape) == 0:
        logging.info("All talks already have transcripts. Nothing to do.")
        return

    # 4. Scrape Loop
    new_transcripts = []
    
    # Helper function
    def get_transcript_text(url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                logging.warning(f"HTTP {response.status_code} for {url}")
                return None
            
            soup = BeautifulSoup(response.content, "html.parser")
            # TED stores transcript in JSON-LD script tag
            script_tag = soup.find("script", type="application/ld+json")
            if script_tag:
                try:
                    data = json.loads(script_tag.string)
                    return data.get("transcript")
                except json.JSONDecodeError:
                    pass
            return None
        except Exception as e:
            logging.error(f"Error scraping {url}: {e}")
            return None

    # Limit batch size if needed (e.g., prevent timeouts). set to 50 for PoC, or remove limit for full run.
    # For now, we process all missing.
    processed_count = 0
    
    for index, row in talks_to_scrape.iterrows():
        url = row['url']
        talk_id = row['id']
        slug = row['slug'] # Assuming slug exists
        
        logging.info(f"Scraping transcript for ID {talk_id}: {url}")
        
        transcript_text = get_transcript_text(url)
        
        if transcript_text:
            # Create a record matching the transcript file structure
            record = row.to_dict()
            record['transcript'] = transcript_text
            new_transcripts.append(record)
            logging.info(f"Successfully scraped {len(transcript_text)} chars.")
        else:
            logging.warning(f"No transcript found for ID {talk_id}")
            # Optional: Add record with empty transcript so we don't retry forever? 
            # For now, we skip it so we retry next time.
        
        processed_count += 1
        time.sleep(1) # Be polite to the server
        
        # Periodic save (checkpointing) could go here
        
    # 5. Append and Save
    if new_transcripts:
        df_new = pd.DataFrame(new_transcripts)
        
        # Append to master file
        # Note: We append to file directly or concat DFs? 
        # Safest is concat DFs and write full file to avoid header issues, 
        # or append mode csv.
        
        # Let's concat and write.
        if os.path.exists(TRANSCRIPTS_PATH):
             # Read mostly to ensure we have headers right, but we can also just append
             df_transcripts = pd.read_csv(TRANSCRIPTS_PATH)
             df_final = pd.concat([df_transcripts, df_new], ignore_index=True)
        else:
             df_final = df_new

        df_final.to_csv(TRANSCRIPTS_PATH, index=False)
        logging.info(f"Saved {len(new_transcripts)} new transcripts to {TRANSCRIPTS_PATH}")
    else:
        logging.info("No valid transcripts were extracted from the missing set.")


with DAG(
    'incremental_transcript_scraper',
    default_args=default_args,
    description='Incrementally scrapes transcripts for new videos in ted_talks_list.csv',
    schedule_interval=None, # Run on demand or schedule
    catchup=False,
    tags=['ted_ai', 'scraper', 'transcripts']
) as dag:

    scrape_task = PythonOperator(
        task_id='scrape_missing_transcripts',
        python_callable=incremental_transcript_scraper
    )
