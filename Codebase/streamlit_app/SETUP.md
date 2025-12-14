# Streamlit Application Setup Guide

This guide walks you through setting up and running the TED Talks Streamlit application.

## Prerequisites

1. ✅ Snowflake database with `TED_DB` populated (via DBT pipeline)
2. ✅ Python 3.11+ installed
3. ✅ Snowflake credentials configured

## Step 1: Run Snowflake Setup Scripts

Execute this SQL script in your Snowflake worksheet:

### 1.1 Create User Management Tables
```bash
# Open and run: snowflake/13_user_management_tables.sql
```
This creates in `TED_DB.APP`:
- `USERS`
- `USER_SEARCH_HISTORY`
- `USER_WATCH_HISTORY`

**Verification**: Run this query to confirm:
```sql
SHOW TABLES IN TED_DB.APP;
-- Should show USERS, USER_SEARCH_HISTORY, USER_WATCH_HISTORY
```

---

## Step 2: Install Python Dependencies

Navigate to the `streamlit_app/` directory:

```bash
cd "c:\Users\mihir\OneDrive\Desktop\NEU\Sem 4\TED_AI - DAMG\ted_ai_project\streamlit_app"
```

Install requirements:
```bash
pip install -r requirements.txt
```

**Expected packages**:
- `streamlit`
- `snowflake-snowpark-python`
- `pandas`
- `langgraph` (for AI agents)

---

## Step 3: Configure Snowflake Connection

The app uses `get_active_session()` which works in two modes:

### Option A: Run in Snowflake (Recommended)
Upload `streamlit_app.py` to Snowflake and run as a **Snowflake Native App**. No configuration needed.

### Option B: Run Locally
Create a `.streamlit/secrets.toml` file:

```toml
[connections.snowflake]
account = "VOB68402"
user = "GIRAFFE"
password = "your_password"  # or use key-pair auth
warehouse = "TED_AGENT_WH"
database = "TED_DB"
schema = "RAW"
role = "TRAINING_ROLE"
```

---

## Step 4: Run the Application

```bash
streamlit run streamlit_app.py
```

The app will open in your browser at `http://localhost:8501`.

---

## Step 5: Test Core Features

### 5.1 User Authentication
1. Click "Create Account" tab
2. Fill in:
   - Full Name
   - Email
   - Password (must meet requirements)
   - Topics of Interest (optional)
3. Click "Create Account"
4. Switch to "Login" tab and sign in

### 5.2 Search for Talks
1. Use the search bar: `"Find talks about AI"`
2. The LangGraph agent will route your query
3. Results will display with talk cards

### 5.3 View Talk Details
1. Click "▶️ Watch" on any talk
2. View transcript (if available)
3. Click "✨ Generate AI Summary" to use Snowflake Cortex

### 5.4 AI Assistant
1. Click "🤖 AI Assistant" in the sidebar
2. Ask questions like:
   - "Recommend science talks"
   - "Find talks about creativity"

---

## Troubleshooting

### Issue: "No module named 'langgraph'"
**Solution**: The app falls back to simple search if LangGraph is not installed. To enable AI agents:
```bash
pip install langgraph langchain
```

### Issue: "Failed to get Snowflake session"
**Solution**: 
- Verify your Snowflake credentials in `.streamlit/secrets.toml`
- Ensure your IP is whitelisted in Snowflake network policies
- Check that `TED_AGENT_WH` warehouse is running

### Issue: "Table 'USERS' does not exist"
**Solution**: Run `snowflake/13_user_management_tables.sql` in Snowflake

### Issue: No talks showing up
**Solution**: Verify data exists:
```sql
SELECT COUNT(*) FROM TED_DB.CURATED.DIM_TED_TALKS;
```
If count is 0, re-run your DBT pipeline: `dbt run`

---

## Next Steps

### Enable Transcripts (Optional)
To enable AI summaries, you need transcripts:

1. Run the transcript scraper DAG in Airflow:
   ```bash
   # Trigger: 02_transcript_scraper_dag
   ```

2. Add transcript column to `DIM_TED_TALKS`:
   ```sql
   ALTER TABLE TED_DB.CURATED.DIM_TED_TALKS 
   ADD COLUMN TRANSCRIPT TEXT;
   ```

3. Update DBT model to join transcripts

### Deploy to Snowflake (Production)
1. Upload `streamlit_app.py` to Snowflake stage
2. Create Streamlit app in Snowflake UI
3. Grant permissions to `TED_DB` schemas

---

## File Structure
```
streamlit_app/
├── streamlit_app.py       # Main application
├── langgraph_agents.py    # AI agent logic
├── db.py                  # Database utilities
├── utils.py               # Helper functions
├── constants.py           # Configuration
├── requirements.txt       # Dependencies
└── .env                   # Environment variables (gitignored)
```

---

## Support

If you encounter issues:
1. Check debug logs in the app (bottom of page)
2. Verify Snowflake tables exist
3. Ensure DBT pipeline has run successfully
