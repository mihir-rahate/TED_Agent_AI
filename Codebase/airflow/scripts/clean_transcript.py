"""Transcript cleaning utilities (skeleton).

Expose `clean_transcripts` callable for Airflow.
"""
from pathlib import Path
import json

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
CLEAN_DIR = Path(__file__).resolve().parents[2] / "data" / "cleaned"


def clean_transcript_record(record: dict) -> dict:
    text = record.get("transcript") or ""
    # very simple cleaning placeholder
    text = " ".join(text.split())
    record["transcript_clean"] = text
    return record


def clean_transcripts() -> bool:
    # Create directory when needed (during execution, not import)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    src = RAW_DIR / "sample_talks.json"
    if not src.exists():
        print("No raw input found; skipping clean step")
        return True
    with src.open("r", encoding="utf8") as f:
        items = json.load(f)
    cleaned = [clean_transcript_record(r) for r in items]
    out = CLEAN_DIR / "sample_talks_clean.json"
    with out.open("w", encoding="utf8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    print(f"Cleaned {len(cleaned)} records")
    return True


if __name__ == "__main__":
    clean_transcripts()
