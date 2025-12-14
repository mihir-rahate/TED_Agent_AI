-- =====================================================================
-- 03. SEMANTIC SCHEMA DDL
-- Source: Cortex AI Embeddings
-- =====================================================================

USE ROLE TRAINING_ROLE;
USE WAREHOUSE TED_AGENT_WH;
USE DATABASE TED_DB;
CREATE SCHEMA IF NOT EXISTS SEMANTIC;
USE SCHEMA SEMANTIC;

-- 1. SEMANTIC_TALK_EMBEDDINGS
-- Stores vector embeddings for semantic search
CREATE TABLE IF NOT EXISTS SEMANTIC_TALK_EMBEDDINGS (
    TALK_ID VARCHAR PRIMARY KEY,
    EMBEDDING_VECTOR VECTOR(FLOAT, 768), -- Dimension depends on model (768 for arctic-embed-m)
    EMBEDDED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
