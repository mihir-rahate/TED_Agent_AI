-- =====================================================================
-- 02. CURATED SCHEMA DDL
-- Source: Data Transformation (DBT)
-- =====================================================================

USE ROLE TRAINING_ROLE;
USE WAREHOUSE TED_AGENT_WH;
USE DATABASE TED_DB;
CREATE SCHEMA IF NOT EXISTS CURATED;
USE SCHEMA CURATED;

-- 1. DIM_TED_TALKS (Primary Dimension Table)
-- Note: This table is managed by DBT model (dim_ted_talks.sql)
CREATE TABLE IF NOT EXISTS DIM_TED_TALKS (
    TALK_ID         STRING PRIMARY KEY,
    SLUG            STRING,
    TITLE           STRING,
    DESCRIPTION     STRING,
    SPEAKERS        STRING,
    PRESENTER       STRING,
    DURATION        NUMBER,
    PUBLISHED_AT    TIMESTAMP_NTZ,
    TALK_URL        STRING,
    IMAGE_URL       STRING,
    TAGS            STRING, -- LISTAGG produces comma-separated string, not ARRAY
    LOADED_AT       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
