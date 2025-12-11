import streamlit as st
from datetime import datetime
from snowflake.snowpark.context import get_active_session
import pandas as pd
import json
import uuid
import hashlib
import re

# Page configuration
st.set_page_config(
    page_title="TED Talks Analytics",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'sidebar_open' not in st.session_state:
    st.session_state.sidebar_open = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'home'
if 'search_query' not in st.session_state:
    st.session_state.search_query = ''
if 'selected_talk' not in st.session_state:
    st.session_state.selected_talk = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'user_topics' not in st.session_state:
    st.session_state.user_topics = None

# Get Snowflake session
@st.cache_resource
def get_snowflake_session():
    """Get active Snowflake session"""
    return get_active_session()

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
        INSERT INTO ted_db.ted_schema_curated.users 
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
        FROM ted_db.ted_schema_curated.users
        WHERE email = '{email_escaped}' AND password_hash = '{password_hash}'
    """
    
    try:
        result = session.sql(query).collect()
        if result and len(result) > 0:
            user_id = result[0]['USER_ID']
            session.sql(f"""
                UPDATE ted_db.ted_schema_curated.users 
                SET last_login = CURRENT_TIMESTAMP()
                WHERE user_id = '{user_id}'
            """).collect()
            
            return True, result[0]
        return False, None
    except Exception as e:
        st.error(f"Login error: {e}")
        return False, None

# ==================== DATABASE FUNCTIONS ====================

def get_all_talks():
    """Fetch all TED talks from Snowflake"""
    session = get_snowflake_session()
    query = """
        WITH transcript_info AS (
            SELECT 
                TALK_ID,
                SUM(LENGTH(TEXT_SEGMENT)) as TRANSCRIPT_LENGTH
            FROM ted_db.raw.ted_transcript_segments_raw
            GROUP BY TALK_ID
        )
        SELECT 
            t.TALK_ID,
            t.TITLE,
            t.SPEAKERS as SPEAKER,
            t.TAGS,
            t.PUBLISHED_DATE,
            t.DURATION_SEC / 60.0 as DURATION_MINUTES,
            t.URL,
            t.SLUG,
            YEAR(t.PUBLISHED_DATE) as PUBLISHED_YEAR,
            ti.TRANSCRIPT_LENGTH
        FROM ted_db.raw.ted_talks_raw t
        INNER JOIN transcript_info ti ON t.TALK_ID = ti.TALK_ID
        ORDER BY t.PUBLISHED_DATE DESC
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
        WITH full_transcript AS (
            SELECT 
                TALK_ID,
                LISTAGG(TEXT_SEGMENT, ' ') WITHIN GROUP (ORDER BY SEGMENT_INDEX) as TRANSCRIPT,
                SUM(LENGTH(TEXT_SEGMENT)) as TRANSCRIPT_LENGTH
            FROM ted_db.raw.ted_transcript_segments_raw
            WHERE TALK_ID = '{talk_id}'
            GROUP BY TALK_ID
        )
        SELECT 
            t.TALK_ID,
            t.SLUG,
            t.TITLE,
            t.SPEAKERS as SPEAKER,
            t.TAGS,
            t.PUBLISHED_DATE,
            t.DURATION_SEC / 60.0 as DURATION_MINUTES,
            t.URL,
            ft.TRANSCRIPT,
            ft.TRANSCRIPT_LENGTH,
            YEAR(t.PUBLISHED_DATE) as PUBLISHED_YEAR
        FROM ted_db.raw.ted_talks_raw t
        LEFT JOIN full_transcript ft ON t.TALK_ID = ft.TALK_ID
        WHERE t.TALK_ID = '{talk_id}'
    """
    try:
        df = session.sql(query).to_pandas()
        return df.iloc[0] if not df.empty else None
    except Exception as e:
        st.error(f"Error fetching talk: {e}")
        return None

def get_talk_by_title(title):
    """Get talk by title"""
    session = get_snowflake_session()
    escaped_title = title.replace("'", "''")
    query = f"""
        WITH full_transcript AS (
            SELECT 
                TALK_ID,
                LISTAGG(TEXT_SEGMENT, ' ') WITHIN GROUP (ORDER BY SEGMENT_INDEX) as TRANSCRIPT
            FROM ted_db.raw.ted_transcript_segments_raw
            GROUP BY TALK_ID
        )
        SELECT 
            t.TALK_ID,
            t.TITLE,
            t.SPEAKERS as SPEAKER,
            t.TAGS,
            t.PUBLISHED_DATE,
            t.DURATION_SEC / 60.0 as DURATION_MINUTES,
            t.URL,
            ft.TRANSCRIPT,
            YEAR(t.PUBLISHED_DATE) as PUBLISHED_YEAR
        FROM ted_db.raw.ted_talks_raw t
        LEFT JOIN full_transcript ft ON t.TALK_ID = ft.TALK_ID
        WHERE t.TITLE = '{escaped_title}'
        LIMIT 1
    """
    try:
        df = session.sql(query).to_pandas()
        return df.iloc[0] if not df.empty else None
    except Exception as e:
        st.error(f"Error fetching talk: {e}")
        return None

def search_talks(search_query):
    """Search TED talks by keyword"""
    session = get_snowflake_session()
    escaped_query = search_query.replace("'", "''")
    query = f"""
        WITH transcript_search AS (
            SELECT DISTINCT TALK_ID
            FROM ted_db.raw.ted_transcript_segments_raw
            WHERE LOWER(TEXT_SEGMENT) LIKE LOWER('%{escaped_query}%')
        ),
        transcript_info AS (
            SELECT 
                TALK_ID,
                SUM(LENGTH(TEXT_SEGMENT)) as TRANSCRIPT_LENGTH
            FROM ted_db.raw.ted_transcript_segments_raw
            GROUP BY TALK_ID
        )
        SELECT 
            t.TALK_ID,
            t.TITLE,
            t.SPEAKERS as SPEAKER,
            t.TAGS,
            t.PUBLISHED_DATE,
            t.DURATION_SEC / 60.0 as DURATION_MINUTES,
            t.URL,
            ti.TRANSCRIPT_LENGTH,
            YEAR(t.PUBLISHED_DATE) as PUBLISHED_YEAR
        FROM ted_db.raw.ted_talks_raw t
        LEFT JOIN transcript_info ti ON t.TALK_ID = ti.TALK_ID
        WHERE 
            LOWER(t.TITLE) LIKE LOWER('%{escaped_query}%')
            OR LOWER(t.SPEAKERS) LIKE LOWER('%{escaped_query}%')
            OR LOWER(t.TAGS) LIKE LOWER('%{escaped_query}%')
            OR t.TALK_ID IN (SELECT TALK_ID FROM transcript_search)
        ORDER BY t.PUBLISHED_DATE DESC
    """
    try:
        df = session.sql(query).to_pandas()
        return df
    except Exception as e:
        st.error(f"Error searching: {e}")
        return pd.DataFrame()

def log_search_history(user_id, search_query, results_count):
    """Log user search to database"""
    session = get_snowflake_session()
    search_id = str(uuid.uuid4())
    escaped_query = search_query.replace("'", "''")
    query = f"""
        INSERT INTO ted_db.ted_schema_curated.user_search_history 
        (search_id, user_id, search_query, results_count, searched_at)
        VALUES ('{search_id}', '{user_id}', '{escaped_query}', {results_count}, CURRENT_TIMESTAMP())
    """
    try:
        session.sql(query).collect()
    except:
        pass

def log_watch_history(user_id, talk_id, watch_duration, total_duration):
    """Log user watch activity"""
    session = get_snowflake_session()
    watch_id = str(uuid.uuid4())
    watch_percentage = (watch_duration / total_duration * 100) if total_duration > 0 else 0
    completed = 'TRUE' if watch_percentage >= 90 else 'FALSE'
    
    query = f"""
        INSERT INTO ted_db.ted_schema_curated.user_watch_history 
        (watch_id, user_id, talk_id, watch_duration_seconds, total_duration_seconds, 
         watch_percentage, watched_at, completed)
        VALUES ('{watch_id}', '{user_id}', '{talk_id}', {watch_duration}, {total_duration}, 
                {watch_percentage}, CURRENT_TIMESTAMP(), {completed})
    """
    try:
        session.sql(query).collect()
    except:
        pass

def get_user_recommendations(user_id):
    """Get personalized recommendations based on user's topics of interest"""
    session = get_snowflake_session()
    
    # First, get user's topics of interest
    try:
        user_query = f"""
            SELECT topics_of_interest 
            FROM ted_db.ted_schema_curated.users
            WHERE user_id = '{user_id}'
        """
        user_result = session.sql(user_query).collect()
        
        if user_result and len(user_result) > 0:
            topics_of_interest = user_result[0]['TOPICS_OF_INTEREST']
        else:
            topics_of_interest = None
    except:
        topics_of_interest = None
    
    # Build query based on topics of interest
    if topics_of_interest and topics_of_interest != 'Not specified':
        # Convert topics string to searchable format
        # e.g., "Science, Technology, Psychology" -> search for these in tags
        topics_list = [topic.strip().lower() for topic in topics_of_interest.split(',')]
        
        # Build LIKE conditions for each topic
        topic_conditions = " OR ".join([f"LOWER(t.TAGS) LIKE '%{topic}%'" for topic in topics_list])
        
        query = f"""
            WITH watched_talks AS (
                SELECT DISTINCT talk_id
                FROM ted_db.ted_schema_curated.user_watch_history
                WHERE user_id = '{user_id}'
            ),
            transcript_info AS (
                SELECT 
                    TALK_ID,
                    COUNT(*) as segment_count
                FROM ted_db.raw.ted_transcript_segments_raw
                GROUP BY TALK_ID
            ),
            matching_talks AS (
                SELECT 
                    t.TALK_ID,
                    t.TITLE,
                    t.SPEAKERS as SPEAKER,
                    t.TAGS,
                    t.PUBLISHED_DATE,
                    t.DURATION_SEC / 60.0 as DURATION_MINUTES,
                    t.URL,
                    YEAR(t.PUBLISHED_DATE) as PUBLISHED_YEAR
                FROM ted_db.raw.ted_talks_raw t
                INNER JOIN transcript_info ti ON t.TALK_ID = ti.TALK_ID
                WHERE ({topic_conditions})
                AND t.TALK_ID NOT IN (SELECT talk_id FROM watched_talks)
                ORDER BY t.PUBLISHED_DATE DESC
            )
            SELECT * FROM matching_talks
            LIMIT 9
        """
    else:
        # Fallback to random talks if no topics specified
        query = f"""
            WITH watched_talks AS (
                SELECT DISTINCT talk_id
                FROM ted_db.ted_schema_curated.user_watch_history
                WHERE user_id = '{user_id}'
            ),
            transcript_info AS (
                SELECT 
                    TALK_ID,
                    COUNT(*) as segment_count
                FROM ted_db.raw.ted_transcript_segments_raw
                GROUP BY TALK_ID
            )
            SELECT 
                t.TALK_ID,
                t.TITLE,
                t.SPEAKERS as SPEAKER,
                t.TAGS,
                t.PUBLISHED_DATE,
                t.DURATION_SEC / 60.0 as DURATION_MINUTES,
                t.URL,
                YEAR(t.PUBLISHED_DATE) as PUBLISHED_YEAR
            FROM ted_db.raw.ted_talks_raw t
            INNER JOIN transcript_info ti ON t.TALK_ID = ti.TALK_ID
            WHERE t.TALK_ID NOT IN (SELECT talk_id FROM watched_talks)
            ORDER BY RANDOM()
            LIMIT 9
        """
    
    try:
        df = session.sql(query).to_pandas()
        return df
    except Exception as e:
        st.error(f"Error getting recommendations: {e}")
        # Fallback to all talks
        return get_all_talks().head(9)

# ==================== AI AGENTS ====================

def call_cortex_llm(prompt, model="mistral-large"):
    """Call Snowflake Cortex LLM"""
    session = get_snowflake_session()
    escaped_prompt = prompt.replace("'", "''")
    
    if len(escaped_prompt) > 10000:
        escaped_prompt = escaped_prompt[:10000] + "..."
    
    query = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            '{model}',
            '{escaped_prompt}'
        ) AS response
    """
    
    try:
        result = session.sql(query).collect()
        return result[0]['RESPONSE']
    except Exception as e:
        return f"Error calling LLM: {str(e)}"

def router_agent(user_query):
    """Determine which agent should handle the query"""
    query_lower = user_query.lower()
    
    summary_keywords = ['summary', 'summarize', 'overview', 'explain', 'what is', 'tell me about']
    compare_keywords = ['compare', 'difference', 'versus', 'vs', 'contrast', 'similar']
    recommend_keywords = ['recommend', 'find', 'suggest', 'show me', 'looking for', 'talks about', 'search']
    
    if any(keyword in query_lower for keyword in summary_keywords):
        return 'summary'
    elif any(keyword in query_lower for keyword in compare_keywords):
        return 'compare'
    elif any(keyword in query_lower for keyword in recommend_keywords):
        return 'recommend'
    else:
        router_prompt = f"""You are a routing assistant. Analyze this query and respond with ONLY ONE WORD.

Query: {user_query}

Choose ONE:
- summary (if asking about a specific talk's content)
- compare (if comparing multiple talks)
- recommend (if looking for talk suggestions)

Response (one word only):"""
        
        response = call_cortex_llm(router_prompt, model="mistral-large").strip().lower()
        
        if 'summary' in response:
            return 'summary'
        elif 'compare' in response:
            return 'compare'
        else:
            return 'recommend'

def summary_agent(talk_id):
    """Generate summary of a TED talk"""
    talk = get_talk_by_id(talk_id)
    
    if talk is None:
        return "Talk not found."
    
    transcript = talk['TRANSCRIPT']
    title = talk['TITLE']
    speaker = talk['SPEAKER']
    
    if pd.isna(transcript) or not transcript:
        return f"No transcript available for '{title}' by {speaker}."
    
    max_transcript_length = 4000
    truncated_transcript = transcript[:max_transcript_length]
    if len(transcript) > max_transcript_length:
        truncated_transcript += "..."
    
    summary_prompt = f"""Summarize this TED talk concisely.

Title: {title}
Speaker: {speaker}

Transcript:
{truncated_transcript}

Provide a clear 3-4 paragraph summary covering:
1. Main topic and thesis
2. Key insights and arguments
3. Practical takeaways

Summary:"""
    
    summary = call_cortex_llm(summary_prompt, model="mistral-large")
    
    result = f"""### 📝 Summary: "{title}"
**Speaker:** {speaker}

{summary}
"""
    
    return result

def compare_agent(talk_titles):
    """Compare two or more TED talks"""
    if len(talk_titles) < 2:
        return "Please provide at least 2 talk titles to compare."
    
    talks = []
    for title in talk_titles:
        talk = get_talk_by_title(title)
        if talk is not None:
            talks.append(talk)
    
    if len(talks) < 2:
        return "Could not find enough talks. Please check the titles."
    
    talks_info = ""
    for i, talk in enumerate(talks[:2], 1):
        transcript_excerpt = talk['TRANSCRIPT'][:1000] if not pd.isna(talk['TRANSCRIPT']) else "No transcript"
        
        talks_info += f"""
Talk {i}:
Title: {talk['TITLE']}
Speaker: {talk['SPEAKER']}
Year: {talk['PUBLISHED_YEAR']}
Tags: {talk['TAGS']}
Transcript excerpt: {transcript_excerpt}...

"""
    
    compare_prompt = f"""Compare these TED talks in detail:

{talks_info}

Provide a comparison covering:
1. Main topics and themes
2. Key similarities and differences in approach
3. Unique insights from each talk
4. Which audiences might prefer each talk

Comparison:"""
    
    comparison = call_cortex_llm(compare_prompt, model="mistral-large")
    
    result = f"""### ⚖️ Comparison of TED Talks

**Talk 1:** {talks[0]['TITLE']} by {talks[0]['SPEAKER']}
**Talk 2:** {talks[1]['TITLE']} by {talks[1]['SPEAKER']}

{comparison}
"""
    
    return result

def recommend_agent(user_query, user_id):
    """Recommend TED talks based on query"""
    talks_df = search_talks(user_query)
    
    if talks_df.empty:
        return f"No talks found matching '{user_query}'. Try different keywords."
    
    result = f"### 🎯 Recommended TED Talks for: '{user_query}'\n\n"
    
    for idx, talk in talks_df.head(4).iterrows():
        result += f"""**{idx+1}. {talk['TITLE']}**
   - Speaker: {talk['SPEAKER']}
   - Year: {talk['PUBLISHED_YEAR']} | Duration: {talk['DURATION_MINUTES']:.1f} min
   - Tags: {talk['TAGS']}

"""
    
    result += "\n💡 Click on any talk from the search results to watch!"
    
    return result

def process_user_query(user_query, user_id, context=None):
    """Main function to process user queries"""
    
    agent_type = router_agent(user_query)
    
    if agent_type == 'summary':
        if context and 'talk_id' in context:
            return summary_agent(context['talk_id'])
        else:
            return "To generate a summary, please watch a specific talk and click the 'Generate Summary' button."
    
    elif agent_type == 'compare':
        if context and 'talk_titles' in context:
            return compare_agent(context['talk_titles'])
        else:
            return "To compare talks, please go to the 'Compare Talks' page and select talks to compare."
    
    elif agent_type == 'recommend':
        return recommend_agent(user_query, user_id)
    
    else:
        return recommend_agent(user_query, user_id)

# ==================== HELPER FUNCTIONS ====================

def format_duration(minutes):
    """Format duration from minutes to MM:SS"""
    if pd.isna(minutes):
        return "N/A"
    total_seconds = int(minutes * 60)
    mins = total_seconds // 60
    secs = total_seconds % 60
    return f"{mins}:{secs:02d}"

def get_topic_emoji(tags):
    """Get emoji based on talk tags"""
    if pd.isna(tags) or not tags:
        return "🎤"
    
    tags_str = str(tags).lower()
    
    emoji_map = {
        'science': '🔬',
        'technology': '💻',
        'psychology': '🧠',
        'education': '🎓',
        'health': '🏥',
        'biology': '🧬',
        'animals': '🦎',
        'environment': '🌍',
        'business': '💼',
        'art': '🎨',
        'music': '🎵',
        'design': '✨',
        'entertainment': '🎭',
        'creativity': '💡',
    }
    
    for keyword, emoji in emoji_map.items():
        if keyword in tags_str:
            return emoji
    
    return '🎤'

# ==================== UI PAGES ====================

def login_page():
    """Display login and create account page"""
    st.title("🎤 TED Talks AI Analytics")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    
    with tab1:
        st.subheader("Login to Your Account")
        with st.form("login_form"):
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.warning("Please enter both email and password")
                elif not validate_email(email):
                    st.error("Please enter a valid email address")
                else:
                    success, user_data = verify_user_login(email, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = user_data['FULL_NAME']
                        st.session_state.user_id = user_data['USER_ID']
                        st.session_state.user_email = user_data['EMAIL']
                        st.session_state.user_topics = user_data['TOPICS_OF_INTEREST']
                        st.success(f"Welcome back, {user_data['FULL_NAME']}!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password. Please try again.")
    
    with tab2:
        st.subheader("Create New Account")
        
        with st.form("create_account_form"):
            full_name = st.text_input("Full Name *", placeholder="John Doe")
            email = st.text_input("Email Address *", placeholder="john.doe@example.com")
            
            col1, col2 = st.columns(2)
            with col1:
                password = st.text_input("Password *", type="password", 
                                        help="Must contain: uppercase, lowercase, number, special character")
            with col2:
                confirm_password = st.text_input("Confirm Password *", type="password")
            
            st.markdown("**Topics of Interest**")
            st.markdown("*Select topics you'd like to explore (optional)*")
            
            topic_options = [
                "Science", "Technology", "Psychology", "Education", 
                "Health", "Business", "Art", "Design", "Entertainment",
                "Environment", "Politics", "Culture", "Innovation"
            ]
            
            selected_topics = st.multiselect(
                "Choose your interests",
                options=topic_options,
                default=[],
                label_visibility="collapsed"
            )
            
            submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")
            
            if submit:
                errors = []
                
                if not full_name or not email or not password or not confirm_password:
                    errors.append("Please fill in all required fields")
                
                if not validate_email(email):
                    errors.append("Please enter a valid email address (must contain @)")
                
                if password != confirm_password:
                    errors.append("Passwords do not match")
                
                is_valid, msg = validate_password(password)
                if not is_valid:
                    errors.append(msg)
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    topics_str = ", ".join(selected_topics) if selected_topics else "Not specified"
                    
                    with st.spinner("Creating your account..."):
                        success, message, user_id = create_user_account(
                            full_name, email, password, topics_str
                        )
                        
                        if success:
                            st.success(message)
                            st.info("Account created! Please go to the Login tab to sign in.")
                            st.balloons()
                        else:
                            st.error(message)
        
        with st.expander("Password Requirements"):
            st.markdown("""
            Your password must contain:
            - At least 8 characters
            - One uppercase letter (A-Z)
            - One lowercase letter (a-z)
            - One number (0-9)
            - One special character
            """)

def main_app():
    """Display main application after login"""
    
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        .talk-card {
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 20px;
            height: 280px;
            transition: all 0.3s ease;
            cursor: pointer;
            background: white;
        }
        .talk-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.15);
            border-color: #ff2b06;
        }
        
        .recommended-card {
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
            cursor: pointer;
            background: white;
        }
        .recommended-card:hover {
            transform: translateX(10px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border-color: #ff2b06;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col_menu, col_spacer = st.columns([1, 20])
    with col_menu:
        if st.button("☰", key="menu_toggle"):
            st.session_state.sidebar_open = not st.session_state.sidebar_open
    
    if st.session_state.sidebar_open:
        left_col, right_col = st.columns([3, 7])
        
        with left_col:
            st.markdown("### 👤 User Profile")
            st.markdown("---")
            st.markdown(f"**{st.session_state.username}**")
            st.markdown(f"*{datetime.now().strftime('%Y-%m-%d')}*")
            
            st.markdown("")
            st.markdown("### 📊 Menu")
            
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.current_page = 'home'
                st.rerun()
            
            if st.button("🤖 AI Assistant", use_container_width=True):
                st.session_state.current_page = 'assistant'
                st.rerun()
            
            if st.button("⚖️ Compare Talks", use_container_width=True):
                st.session_state.current_page = 'compare'
                st.rerun()
            
            st.markdown("<br>" * 5, unsafe_allow_html=True)
            
            if st.button("🚪 Logout", use_container_width=True, type="primary"):
                st.session_state.logged_in = False
                st.session_state.username = None
                st.session_state.user_id = None
                st.session_state.sidebar_open = False
                st.session_state.current_page = 'home'
                st.rerun()
    else:
        right_col = st.container()
    
    with right_col:
        if st.session_state.current_page == 'home':
            show_home_page()
        elif st.session_state.current_page == 'search':
            show_search_results()
        elif st.session_state.current_page == 'talk_detail':
            show_talk_detail()
        elif st.session_state.current_page == 'assistant':
            show_ai_assistant()
        elif st.session_state.current_page == 'compare':
            show_compare_talks()

def show_home_page():
    """Home page with search and talks"""
    st.title("🎤 Discover TED Talks")
    st.markdown("---")
    
    col1, col2 = st.columns([8, 2])
    with col1:
        search_input = st.text_input(
            "search", 
            placeholder="🔍 Search for TED talks...", 
            label_visibility="collapsed"
        )
    with col2:
        search_button = st.button("Search", use_container_width=True, type="primary")
    
    if search_button and search_input:
        st.session_state.search_query = search_input
        st.session_state.current_page = 'search'
        talks_df = search_talks(search_input)
        log_search_history(st.session_state.user_id, search_input, len(talks_df))
        st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.spinner("Loading personalized recommendations..."):
        rec_talks = get_user_recommendations(st.session_state.user_id)
        
        if not rec_talks.empty:
            # Show user's topics if available
            if st.session_state.user_topics and st.session_state.user_topics != 'Not specified':
                st.markdown(f"### 🌟 Recommended Based on Your Interests: *{st.session_state.user_topics}*")
            else:
                st.markdown("### 🌟 Recommended for You")
            st.markdown("---")
            
            # Display 9 recommendations in 3x3 grid
            num_recs = len(rec_talks)
            num_rows = (num_recs + 2) // 3
            
            rec_idx = 0
            for row in range(num_rows):
                cols = st.columns(3)
                for col_idx, col in enumerate(cols):
                    if rec_idx < num_recs:
                        talk = rec_talks.iloc[rec_idx]
                        emoji = get_topic_emoji(talk['TAGS'])
                        duration = format_duration(talk['DURATION_MINUTES'])
                        
                        with col:
                            st.markdown(f"""
                                <div class="recommended-card">
                                    <div style="text-align: center; font-size: 50px; margin-bottom: 10px;">
                                        {emoji}
                                    </div>
                                    <h5 style="margin-bottom: 8px;">{talk['TITLE'][:50]}...</h5>
                                    <p style="color: #666; font-size: 14px;"><strong>{talk['SPEAKER']}</strong></p>
                                    <p style="color: #999; font-size: 13px;">
                                        {talk['PUBLISHED_YEAR']} • {duration}
                                    </p>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button("▶️ Watch", key=f"rec_{rec_idx}", use_container_width=True):
                                st.session_state.selected_talk = talk['TALK_ID']
                                st.session_state.current_page = 'talk_detail'
                                st.rerun()
                        
                        rec_idx += 1
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    with st.spinner("Loading all talks..."):
        talks_df = get_all_talks()
    
    if not talks_df.empty:
        st.markdown("### 📚 All TED Talks")
        st.markdown("---")
        
        num_talks = len(talks_df)
        num_rows = (num_talks + 2) // 3
        
        talk_idx = 0
        for row in range(num_rows):
            cols = st.columns(3)
            for col_idx, col in enumerate(cols):
                if talk_idx < num_talks:
                    talk = talks_df.iloc[talk_idx]
                    emoji = get_topic_emoji(talk['TAGS'])
                    duration = format_duration(talk['DURATION_MINUTES'])
                    
                    with col:
                        st.markdown(f"""
                            <div class="talk-card">
                                <div style="text-align: center; font-size: 60px; margin-bottom: 10px;">
                                    {emoji}
                                </div>
                                <h5 style="margin-bottom: 8px;">{talk['TITLE'][:60]}</h5>
                                <p style="color: #666; font-size: 14px;"><strong>{talk['SPEAKER']}</strong></p>
                                <p style="color: #999; font-size: 13px;">
                                    {talk['PUBLISHED_YEAR']} • {duration}
                                </p>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("▶️ Watch", key=f"watch_{talk_idx}", use_container_width=True):
                            st.session_state.selected_talk = talk['TALK_ID']
                            st.session_state.current_page = 'talk_detail'
                            st.rerun()
                    
                    talk_idx += 1

def show_search_results():
    """Search results page"""
    st.title(f"🔍 Search Results")
    st.markdown(f"*'{st.session_state.search_query}'*")
    st.markdown("---")
    
    col1, col2 = st.columns([2, 8])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()
    
    with st.spinner("Searching..."):
        filtered_talks = search_talks(st.session_state.search_query)
    
    if not filtered_talks.empty:
        st.markdown(f"### Found {len(filtered_talks)} talk(s)")
        st.markdown("---")
        
        for idx, (_, talk) in enumerate(filtered_talks.iterrows()):
            emoji = get_topic_emoji(talk['TAGS'])
            duration = format_duration(talk['DURATION_MINUTES'])
            
            col1, col2 = st.columns([8, 2])
            with col1:
                st.markdown(f"### {emoji} {talk['TITLE']}")
                st.markdown(f"**{talk['SPEAKER']}** • {talk['PUBLISHED_YEAR']} • {duration}")
            with col2:
                if st.button("▶️ Watch", key=f"search_{idx}", use_container_width=True):
                    st.session_state.selected_talk = talk['TALK_ID']
                    st.session_state.current_page = 'talk_detail'
                    st.rerun()
            st.markdown("---")
    else:
        st.warning(f"No talks found for '{st.session_state.search_query}'")

def show_talk_detail():
    """Talk detail page with video and summary"""
    talk = get_talk_by_id(st.session_state.selected_talk)
    
    if talk is None:
        st.error("Talk not found")
        return
    
    col1, col2 = st.columns([2, 8])
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()
    
    st.title(f"{talk['TITLE']}")
    
    duration_display = format_duration(talk['DURATION_MINUTES']) if not pd.isna(talk['DURATION_MINUTES']) else "N/A"
    st.markdown(f"**{talk['SPEAKER']}** • {talk['PUBLISHED_YEAR']} • Duration: {duration_display}")
    
    if not pd.isna(talk['TAGS']) and talk['TAGS']:
        tags_str = str(talk['TAGS']).replace('[', '').replace(']', '').replace('"', '').replace("'", "")
        st.markdown(f"**Topics:** {tags_str}")
    
    st.markdown("---")
    
    st.markdown("### 🎬 Watch the Talk")
    
    col_video, col_side = st.columns([7, 3])
    
    with col_video:
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); 
                        border-radius: 15px; 
                        padding: 40px; 
                        text-align: center;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                        min-height: 400px;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;">
                <div style="font-size: 100px; margin-bottom: 20px;">🎥</div>
                <h2 style="color: white; margin-bottom: 15px; font-size: 24px;">
                    {talk['TITLE'][:60]}{'...' if len(talk['TITLE']) > 60 else ''}
                </h2>
                <p style="color: rgba(255,255,255,0.9); font-size: 18px; margin-bottom: 25px;">
                    by {talk['SPEAKER']}
                </p>
                <a href="{talk['URL']}" 
                   target="_blank" 
                   style="background: white; 
                          color: #e74c3c; 
                          padding: 18px 45px; 
                          border-radius: 50px; 
                          text-decoration: none; 
                          font-weight: bold; 
                          font-size: 20px;
                          box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                          display: inline-block;">
                    ▶️ Watch on TED.com
                </a>
                <p style="color: rgba(255,255,255,0.7); margin-top: 20px; font-size: 14px;">
                    Duration: {duration_display}
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_side:
        st.markdown("### 📊 Details")
        transcript_length_display = f"{talk['TRANSCRIPT_LENGTH']:,}" if not pd.isna(talk['TRANSCRIPT_LENGTH']) else "N/A"
        st.markdown(f"""
        **Speaker:** {talk['SPEAKER']}
        
        **Year:** {talk['PUBLISHED_YEAR']}
        
        **Duration:** {duration_display}
        
        **Transcript:** {transcript_length_display} chars
        """)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### 📄 Transcript")
    if not pd.isna(talk['TRANSCRIPT']) and talk['TRANSCRIPT']:
        with st.expander("Click to view full transcript"):
            transcript_html = f"""
                <div style="background: #f8f9fa; 
                            border-left: 4px solid #e74c3c; 
                            padding: 20px; 
                            border-radius: 8px; 
                            max-height: 400px; 
                            overflow-y: auto;
                            font-family: Georgia, serif;
                            line-height: 1.8;
                            font-size: 16px;">
                    {talk['TRANSCRIPT'].replace(chr(10), '<br>')}
                </div>
            """
            st.markdown(transcript_html, unsafe_allow_html=True)
    else:
        st.warning("No transcript available for this talk.")
    
    st.markdown("---")
    
    st.markdown("### 🤖 AI-Powered Summary")
    st.markdown("Get an instant summary generated by Snowflake Cortex AI")
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        if st.button("✨ Generate AI Summary", use_container_width=True, type="primary", key="gen_summary"):
            with st.spinner("🧠 Analyzing transcript with Snowflake Cortex AI..."):
                result = summary_agent(talk['TALK_ID'])
                
                st.markdown("---")
                st.markdown(result)
                
                duration_seconds = int(talk['DURATION_MINUTES'] * 60) if not pd.isna(talk['DURATION_MINUTES']) else 300
                log_watch_history(
                    st.session_state.user_id,
                    talk['TALK_ID'],
                    duration_seconds,
                    duration_seconds
                )
                
                st.success("✅ Summary generated successfully!")

def show_ai_assistant():
    """AI Assistant page with router"""
    st.title("🤖 AI Assistant")
    st.markdown("Ask me anything about TED talks!")
    st.markdown("---")
    
    user_input = st.text_area(
        "Your question:",
        placeholder="e.g., 'Find talks about creativity' or 'Recommend science talks'",
        height=100,
        key="ai_input"
    )
    
    if st.button("Send", type="primary", use_container_width=True) and user_input:
        with st.spinner("Processing..."):
            result = process_user_query(user_input, st.session_state.user_id)
            
            st.markdown("---")
            st.markdown("### Response:")
            st.markdown(result)
            
            st.session_state.chat_history.append({
                "user": user_input,
                "assistant": result
            })
    
    if st.session_state.chat_history:
        st.markdown("---")
        st.markdown("### Recent Conversations")
        for chat in reversed(st.session_state.chat_history[-3:]):
            with st.expander(f"💬 {chat['user'][:50]}..."):
                st.markdown(f"**You:** {chat['user']}")
                st.markdown(f"**Assistant:** {chat['assistant']}")

def show_compare_talks():
    """Compare talks page"""
    st.title("⚖️ Compare TED Talks")
    st.markdown("Select two talks to compare")
    st.markdown("---")
    
    talks_df = get_all_talks()
    
    if talks_df.empty:
        st.error("No talks available")
        return
    
    talk_titles = talks_df['TITLE'].tolist()
    
    col1, col2 = st.columns(2)
    
    with col1:
        talk1 = st.selectbox("Select First Talk", talk_titles, key="talk1")
    
    with col2:
        talk2 = st.selectbox("Select Second Talk", talk_titles, key="talk2")
    
    if st.button("Compare Talks", type="primary", use_container_width=True):
        if talk1 == talk2:
            st.warning("Please select two different talks")
        else:
            with st.spinner("Comparing talks..."):
                result = compare_agent([talk1, talk2])
                st.markdown(result)

def main():
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()

if __name__ == "__main__":
    main()