"""Scraper for TED talks (skeleton).

Replace the scraping logic with a robust implementation. This module
exposes a `scrape` callable for Airflow and a `scrape_ted` function
which can be used standalone.
"""
from typing import List
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def scrape_ted() -> List[dict]:
    # Create directory when needed (during execution, not import)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # TODO: implement real scraping from TED website or API
    sample = [{"talk_id": "sample-1", "title": "Sample Talk", "transcript": "Hello world"}]
    out = OUTPUT_DIR / "sample_talks.json"
    with out.open("w", encoding="utf8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)
    return sample


def scrape():
    print("Starting scrape (skeleton)")
    records = scrape_ted()
    print(f"Scraped {len(records)} talks")
    return True


if __name__ == "__main__":
    scrape()
