"""
Database Helper Functions
Handles all Snowflake database operations
"""

import streamlit as st
from snowflake.snowpark.context import get_active_session
import pandas as pd
import uuid
import hashlib
import re


@st.cache_resource
def get_snowflake_session():
    """Get active Snowflake session"""
    return get_active_session()


# ==================== CHAT PERSISTENCE (PHASE 12) ====================

def create_chat_session(user_id):
    """Creates a new empty chat session"""
    try:
        session = get_snowflake_session()
        session_id = str(uuid.uuid4())
        query = f"""
        INSERT INTO TED_DB.APP.USER_CHAT_SESSIONS (session_id, user_id, title)
        VALUES ('{session_id}', '{user_id}', 'New Chat')
        """
        session.sql(query).collect()
        return session_id
    except Exception as e:
        st.error(f"Error creating session: {e}")
        return str(uuid.uuid4()) # Fallback

def update_chat_title(session_id, title):
    """Updates the title of a chat session"""
    try:
        session = get_snowflake_session()
        safe_title = title.replace("'", "''")
        query = f"""
        UPDATE TED_DB.APP.USER_CHAT_SESSIONS
        SET title = '{safe_title}'
        WHERE session_id = '{session_id}'
        """
        session.sql(query).collect()
    except Exception as e:
        print(f"Error updating title: {e}")

def save_chat_message(user_id, session_id, role, content):
    """Save message to CHAT_MESSAGES and update session timestamp"""
    try:
        session = get_snowflake_session()
        msg_id = str(uuid.uuid4())
        escaped_content = content.replace("'", "''")
        
        # 1. Insert Message
        q_insert = f"""
            INSERT INTO TED_DB.APP.CHAT_MESSAGES 
            (message_id, session_id, role, content)
            VALUES ('{msg_id}', '{session_id}', '{role}', '{escaped_content}')
        """
        session.sql(q_insert).collect()
        
        # 2. Update Session Timestamp
        q_update = f"""
            UPDATE TED_DB.APP.USER_CHAT_SESSIONS
            SET updated_at = CURRENT_TIMESTAMP()
            WHERE session_id = '{session_id}'
        """
        session.sql(q_update).collect()
        return True
    except Exception as e:
        # If session doesn't exist (legacy), try creating it first (Self-Healing)
        if "Foreign key constraint" in str(e):
            st.warning("Repairing session link...")
            create_chat_session_query = f"""
            INSERT INTO TED_DB.APP.USER_CHAT_SESSIONS (session_id, user_id, title)
            VALUES ('{session_id}', '{user_id}', 'Restored Session')
            """
            try:
                session.sql(create_chat_session_query).collect()
                # Retry saving message
                session.sql(q_insert).collect()
                return True
            except:
                pass
        
        st.error(f"Error saving chat: {e}")
        return False

def get_session_messages(session_id):
    """Get full history for a session"""
    try:
        session = get_snowflake_session()
        query = f"""
        SELECT role, content
        FROM TED_DB.APP.CHAT_MESSAGES
        WHERE session_id = '{session_id}'
        ORDER BY created_at ASC
        """
        df = session.sql(query).to_pandas()
        df.columns = [c.lower() for c in df.columns]
        return df.to_dict('records')
    except Exception as e:
        # Fallback to old table if new one empty/fails? 
        # For now, just return empty list to avoid complexity.
        return []

def get_user_sessions(user_id):
    """Get all chat sessions for sidebar"""
    try:
        session = get_snowflake_session()
        query = f"""
        SELECT session_id, title, updated_at
        FROM TED_DB.APP.USER_CHAT_SESSIONS
        WHERE user_id = '{user_id}'
        ORDER BY updated_at DESC
        """
        df = session.sql(query).to_pandas()
        df.columns = [c.lower() for c in df.columns]
        return df.to_dict('records')
    except Exception as e:
        st.error(f"Error loading sessions: {e}")
        return []

# Legacy wrapper for compatibility if needed elsewhere
def get_chat_history(user_id, session_id):
    return get_session_messages(session_id)


# ==================== AUTHENTICATION FUNCTIONS ====================

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def validate_email(email):
    """Validate email format"""
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(email_pattern, email) is not None


def validate_password(password):
    """Validate password requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    special_chars = r'[!@#$%^&*(),.?":{}|<>]'
    if not re.search(special_chars, password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"


def create_user_account(full_name, email, password, topics_of_interest):
    """Create a new user account in Snowflake"""
    session = get_snowflake_session()
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    
    full_name = full_name.replace("'", "''")
    email = email.replace("'", "''")
    topics_of_interest = topics_of_interest.replace("'", "''")
    
    query = f"""
        INSERT INTO TED_DB.APP.USERS 
        (user_id, full_name, email, password_hash, topics_of_interest, created_at)
        VALUES ('{user_id}', '{full_name}', '{email}', '{password_hash}', 
                '{topics_of_interest}', CURRENT_TIMESTAMP())
    """
    
    try:
        session.sql(query).collect()
        return True, "Account created successfully!", user_id
    except Exception as e:
        error_msg = str(e)
        if 'duplicate key' in error_msg.lower() or 'unique' in error_msg.lower():
            return False, "Email already registered.", None
        return False, f"Error creating account: {error_msg}", None


def verify_user_login(email, password):
    """Verify user credentials"""
    session = get_snowflake_session()
    password_hash = hash_password(password)
    email_escaped = email.replace("'", "''")
    
    query = f"""
        SELECT user_id, full_name, email, topics_of_interest
        FROM TED_DB.APP.USERS
        WHERE email = '{email_escaped}' AND password_hash = '{password_hash}'
    """
    
    try:
        result = session.sql(query).collect()
        if result and len(result) > 0:
            user_id = result[0]['USER_ID']
            session.sql(f"""
                UPDATE TED_DB.APP.USERS 
                SET last_login = CURRENT_TIMESTAMP()
                WHERE user_id = '{user_id}'
            """).collect()
            
            return True, result[0]
        return False, None
    except Exception as e:
        st.error(f"Login error: {e}")
        return False, None


# ==================== TED TALKS QUERY FUNCTIONS ====================

def search_talks(search_query, limit=20):
    """Search TED talks by keyword or semantic similarity"""
    try:
        st.write(f"🔍 DB: Searching for: '{search_query}'")
        session = get_snowflake_session()
        escaped_query = search_query.replace("'", "''")

        # --- DIAGNOSTICS ---
        try:
            count_talks = session.sql("SELECT COUNT(*) FROM TED_DB.CURATED.DIM_TED_TALKS").collect()[0][0]
            st.write(f"📊 DB Diagnostic: DIM_TED_TALKS has {count_talks} rows")
            
            try:
                count_embeds = session.sql("SELECT COUNT(*) FROM TED_DB.SEMANTIC.SEMANTIC_TALK_EMBEDDINGS").collect()[0][0]
                st.write(f"📊 DB Diagnostic: SEMANTIC_TALK_EMBEDDINGS has {count_embeds} rows")
            except:
                st.error("❌ DB Diagnostic: SEMANTIC_TALK_EMBEDDINGS table likely missing or inaccessible")
                count_embeds = 0
                
            if count_talks == 0:
                st.error("CRITICAL: DIM_TED_TALKS is empty! Run your DBT pipeline or data loading scripts.")
                return pd.DataFrame()
        except Exception as diag_err:
            st.write(f"⚠️ Diagnostic check failed: {diag_err}")
        # -------------------
        
        # 1. EXACT MATCH SHORTCUT (Title or Slug)
        # Often users copy-paste titles or slugs (with underscores)
        # We try strict match first for high precision Resolver
        
        # Handle "this_is_a_slug" -> "this is a slug" approximation for title check
        potential_slug = escaped_query
        normalized_query = escaped_query.replace("_", " ") # For Title ILIKE
        
        exact_query = f"""
            SELECT 
                d.talk_id,
                d.title,
                d.speakers as speaker,
                d.tags,
                d.published_at,
                d.duration / 60.0 as duration_minutes,
                d.talk_url,
                YEAR(d.published_at) as published_year,
                1.0 as similarity_score
            FROM TED_DB.CURATED.DIM_TED_TALKS d
            WHERE 
                LOWER(d.title) = LOWER('{normalized_query}')
                OR LOWER(d.slug) = LOWER('{potential_slug}')
                OR LOWER(d.title) = LOWER('{escaped_query}') 
                -- Also try strict ILIKE for partials if very specific
                OR LOWER(d.slug) ILIKE LOWER('%{potential_slug}%')
            LIMIT 1
        """
        try:
             df_exact = session.sql(exact_query).to_pandas()
             if not df_exact.empty:
                 st.write(f"✅ DB: Exact match found: '{df_exact.iloc[0]['TITLE']}'")
                 df_exact.columns = [c.lower() for c in df_exact.columns]
                 return df_exact
        except Exception as e:
             pass # Fallback to vector if exact fails
        
        # 2. Semantic Search using Vector Similarity
        query = f"""
            WITH query_embedding AS (
                SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                    'snowflake-arctic-embed-m', 
                    '{escaped_query}'
                ) as q_vector
            ),
            top_matches AS (
                SELECT 
                    e.talk_id,
                    VECTOR_COSINE_SIMILARITY(e.embedding_vector, (SELECT q_vector FROM query_embedding)) as similarity_score
                FROM TED_DB.SEMANTIC.SEMANTIC_TALK_EMBEDDINGS e
                ORDER BY similarity_score DESC
                LIMIT {limit}
            )
            SELECT 
                d.talk_id,
                d.title,
                d.speakers as speaker,
                d.tags,
                d.published_at,
                d.duration / 60.0 as duration_minutes,
                d.talk_url,
                YEAR(d.published_at) as published_year,
                t.similarity_score
            FROM TED_DB.CURATED.DIM_TED_TALKS d
            JOIN top_matches t ON d.talk_id = t.talk_id
            WHERE t.similarity_score > 0.25
            ORDER BY t.similarity_score DESC
        """
        
        st.write(f"📊 DB: Executing Semantic Vector Search...")
        df = session.sql(query).to_pandas()
        
        # Fallback if no relevant semantic matches found
        if df.empty:
             st.warning("⚠️ Semantic search returned 0 highly relevant results. Trying keyword search...")
             query_fallback = f"""
                SELECT 
                    d.talk_id,
                    d.title,
                    d.speakers as speaker,
                    d.tags,
                    d.published_at,
                    d.duration / 60.0 as duration_minutes,
                    d.talk_url,
                    YEAR(d.published_at) as published_year,
                    0.0 as similarity_score
                FROM TED_DB.CURATED.DIM_TED_TALKS d
                WHERE 
                    LOWER(d.title) LIKE LOWER('%{escaped_query}%')
                    OR LOWER(d.speakers) LIKE LOWER('%{escaped_query}%')
                    OR LOWER(d.tags) LIKE LOWER('%{escaped_query}%')
                ORDER BY d.published_at DESC
                LIMIT {limit}
            """
             df = session.sql(query_fallback).to_pandas()
        
        st.success(f"✅ DB: Found {len(df)} talks")
        df.columns = [c.lower() for c in df.columns]
        return df
        
    except Exception as e:
        st.error(f"❌ DB Error in search_talks: {e}")
        st.write("Debug Info:")
        if 'query' in locals():
            st.code(query)
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame()


def get_all_talks():
    """Fetch all TED talks from Snowflake"""
    session = get_snowflake_session()
    query = """
        SELECT 
            d.talk_id,
            d.title,
            d.speakers as speaker,
            d.tags,
            d.published_at,
            d.duration / 60.0 as duration_minutes,
            d.talk_url,
            YEAR(d.published_at) as published_year
        FROM TED_DB.CURATED.DIM_TED_TALKS d
        ORDER BY d.published_at DESC
        LIMIT 50
    """
    try:
        df = session.sql(query).to_pandas()
        return df
    except Exception as e:
        st.error(f"Error fetching talks: {e}")
        return pd.DataFrame()


def get_talk_by_id(talk_id):
    """Get specific talk details including transcript"""
    session = get_snowflake_session()
    query = f"""
        SELECT 
            d.talk_id,
            d.title,
            d.speakers as speaker,
            d.tags,
            d.published_at,
            d.duration / 60.0 as duration_minutes,
            d.talk_url,
            YEAR(d.published_at) as published_year,
            CAST(NULL AS TEXT) AS transcript,
            CAST(NULL AS INTEGER) AS transcript_length
        FROM TED_DB.CURATED.DIM_TED_TALKS d
        WHERE d.talk_id = '{talk_id}'
    """
    try:
        df = session.sql(query).to_pandas()
        return df.iloc[0] if not df.empty else None
    except Exception as e:
        st.error(f"Error fetching talk: {e}")
        return None


def get_user_recommendations(user_id):
    """Get personalized recommendations"""
    session = get_snowflake_session()
    query = f"""
        SELECT 
            d.talk_id,
            d.title,
            d.speakers as speaker,
            d.tags,
            d.published_at,
            d.duration / 60.0 as duration_minutes,
            d.talk_url,
            YEAR(d.published_at) as published_year
        FROM TED_DB.CURATED.DIM_TED_TALKS d
        ORDER BY RANDOM()
        LIMIT 9
    """
    try:
        df = session.sql(query).to_pandas()
        return df
    except Exception as e:
        return get_all_talks().head(9)


# ==================== LOGGING FUNCTIONS ====================

def log_search_history(user_id, search_query, results_count):
    """Log user search to database"""
    session = get_snowflake_session()
    search_id = str(uuid.uuid4())
    escaped_query = search_query.replace("'", "''")
    query = f"""
        INSERT INTO TED_DB.APP.USER_SEARCH_HISTORY 
        (search_id, user_id, search_query, results_count, searched_at)
        VALUES ('{search_id}', '{user_id}', '{escaped_query}', {results_count}, CURRENT_TIMESTAMP())
    """
    try:
        session.sql(query).collect()
    except:
        pass


def log_watch_history(user_id, talk_id, watch_duration, total_duration):
    """Log watch history"""
    try:
        session = get_snowflake_session()
        watch_id = str(uuid.uuid4())
        query = f"""
            INSERT INTO TED_DB.APP.USER_WATCH_HISTORY 
            (watch_id, user_id, talk_id, watch_duration_seconds, total_duration_seconds, watched_at)
            VALUES ('{watch_id}', '{user_id}', '{talk_id}', {watch_duration}, {total_duration}, CURRENT_TIMESTAMP())
        """
        session.sql(query).collect()
    except:
        pass


# ==================== AI FUNCTIONS ====================

def call_cortex_llm(prompt, model="llama3.1-405b"):
    """Call Snowflake Cortex LLM"""
    try:
        st.write(f"🤖 AI: Calling Cortex LLM with model: {model}")
        st.write(f"📝 AI: Prompt length: {len(prompt)} chars")
        
        session = get_snowflake_session()
        escaped_prompt = prompt.replace("'", "''")
        
        if len(escaped_prompt) > 100000:
            st.warning(f"⚠️ AI: Prompt truncated from {len(escaped_prompt)} to 100000 chars")
            escaped_prompt = escaped_prompt[:100000] + "..."
        
        query = f"""
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                '{model}',
                '{escaped_prompt}'
            ) AS response
        """
        
        st.write(f"⏳ AI: Sending request to Snowflake Cortex...")
        result = session.sql(query).collect()
        response = result[0]['RESPONSE']
        st.success(f"✅ AI: Received response ({len(response)} chars)")
        return response
        
    except Exception as e:
        error_msg = f"❌ AI Error in call_cortex_llm: {str(e)}"
        st.error(error_msg)
        import traceback
        st.code(traceback.format_exc())
        return f"Error calling LLM: {str(e)}"


def call_cortex_summarize(text):
    """Call Snowflake Cortex SUMMARIZE function"""
    try:
        st.write(f"📄 SUMMARIZE: Processing text ({len(text)} chars)")
        
        session = get_snowflake_session()
        escaped_text = text.replace("'", "''")
        
        if len(escaped_text) > 10000:
            st.warning(f"⚠️ SUMMARIZE: Text truncated from {len(escaped_text)} to 10000 chars")
            escaped_text = escaped_text[:10000] + "..."
        
        query = f"""
            SELECT SNOWFLAKE.CORTEX.SUMMARIZE('{escaped_text}') AS summary
        """
        
        st.write("⏳ SUMMARIZE: Calling Snowflake Cortex...")
        result = session.sql(query).collect()
        summary = result[0]['SUMMARY']
        st.success(f"✅ SUMMARIZE: Generated summary ({len(summary)} chars)")
        return summary
        
    except Exception as e:
        error_msg = f"❌ SUMMARIZE Error: {str(e)}"
        st.error(error_msg)
        import traceback
        st.code(traceback.format_exc())
        return f"Error calling SUMMARIZE: {str(e)}"

def save_user_playlist(user_id, topic, content):
    """
    Saves a generated playlist to the USER_PLAYLISTS table.
    """
    try:
        session = get_snowflake_session()
        # Escaping single quotes for SQL safety 
        safe_content = content.replace("'", "''")
        safe_topic = topic.replace("'", "''")
        
        query = f"""
        INSERT INTO TED_DB.APP.USER_PLAYLISTS (user_id, topic, content_markdown)
        VALUES ('{user_id}', '{safe_topic}', '{safe_content}')
        """
        session.sql(query).collect()
        return True
    except Exception as e:
        st.error(f"Error saving playlist: {e}")
        return False

def get_user_playlists(user_id):
    """
    Retrieves all saved playlists for a user.
    """
    try:
        session = get_snowflake_session()
        query = f"""
        SELECT playlist_id, topic, content_markdown, created_at
        FROM TED_DB.APP.USER_PLAYLISTS
        WHERE user_id = '{user_id}'
        ORDER BY created_at DESC
        """
        df = session.sql(query).to_pandas()
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error getting playlists: {e}")
        import pandas as pd
        return pd.DataFrame()

# ==================== SAVED NOTES FUNCTIONS (PHASE 11) ====================

def save_conversation_note(user_id, title, messages):
    """
    Saves the entire conversation history as a JSON note.
    """
    try:
        session = get_snowflake_session()
        note_id = str(uuid.uuid4())
        safe_title = title.replace("'", "''")
        
        # Serialize messages to JSON string, escaping for SQL
        # We use json.dumps and then replace single quotes specifically for the SQL string wrapper
        json_data = json.dumps(messages)
        safe_json = json_data.replace("'", "''")
        
        metadata = json.dumps({"msg_count": len(messages)})
        
        query = f"""
        INSERT INTO TED_DB.APP.USER_SAVED_NOTES 
        (note_id, user_id, note_title, conversation_data, metadata)
        VALUES ('{note_id}', '{user_id}', '{safe_title}', PARSE_JSON('{safe_json}'), PARSE_JSON('{metadata}'))
        """
        session.sql(query).collect()
        return True
    except Exception as e:
        st.error(f"Error saving note: {e}")
        return False

def get_saved_notes(user_id):
    """
    Get list of saved notes headers.
    """
    try:
        session = get_snowflake_session()
        query = f"""
        SELECT note_id, note_title, created_at, metadata
        FROM TED_DB.APP.USER_SAVED_NOTES
        WHERE user_id = '{user_id}'
        ORDER BY created_at DESC
        """
        df = session.sql(query).to_pandas()
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error loading notes: {e}")
        import pandas as pd
        return pd.DataFrame()

def get_note_content(note_id):
    """
    Get full content of a specific note.
    """
    try:
        session = get_snowflake_session()
        query = f"""
        SELECT conversation_data
        FROM TED_DB.APP.USER_SAVED_NOTES
        WHERE note_id = '{note_id}'
        """
        result = session.sql(query).collect()
        if result:
            # Snowflake returns VARIANT as string or dict depend on connector
            # Snowpark usually returns it as a JSON string or Dict
            data = result[0]['CONVERSATION_DATA']
            if isinstance(data, str):
                return json.loads(data)
            return data
    except Exception as e:
        return None

# ==================== QA RETRIEVAL FUNCTIONS (PHASE 13) ====================

def get_transcript(talk_id):
    """
    Fetch full transcript for a specific talk.
    """
    try:
        session = get_snowflake_session()
        query = f"""
        SELECT transcript
        FROM TED_DB.RAW.TED_TALKS_TRANSCRIPTS
        WHERE id = '{talk_id}'
        """
        result = session.sql(query).collect()
        if result and len(result) > 0:
            return result[0]['TRANSCRIPT']
        return None
    except Exception as e:
        st.error(f"Error fetching transcript: {e}")
        return None
        return []
    except Exception as e:
        st.error(f"Error loading note content: {e}")
        return []
