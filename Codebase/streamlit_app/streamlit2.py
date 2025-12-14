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
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = True  # Set to True for debugging
if 'debug_logs' not in st.session_state:
    st.session_state.debug_logs = []

# Debug logging helper
def debug_log(message, level="INFO"):
    """Log debug messages"""
    import traceback
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    log_entry = f"[{timestamp}] [{level}] {message}"
    
    if st.session_state.debug_mode:
        st.session_state.debug_logs.append(log_entry)
        
        # Display in UI based on level
        if level == "ERROR":
            st.error(f"🐛 {message}")
            # Show stack trace in expander
            with st.expander("📋 Stack Trace"):
                st.code(traceback.format_exc())
        elif level == "WARNING":
            st.warning(f"⚠️ {message}")
        elif level == "SUCCESS":
            st.success(f"✅ {message}")
        else:
            st.info(f"ℹ️ {message}")

# Get Snowflake session
@st.cache_resource
def get_snowflake_session():
    """Get active Snowflake session"""
    try:
        debug_log("Attempting to get Snowflake session...")
        session = get_active_session()
        debug_log("Snowflake session acquired successfully", "SUCCESS")
        return session
    except Exception as e:
        debug_log(f"Failed to get Snowflake session: {str(e)}", "ERROR")
        raise

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

def search_talks(search_query):
    """Search TED talks by keyword"""
    session = get_snowflake_session()
    escaped_query = search_query.replace("'", "''")
    query = f"""
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
        WHERE 
            LOWER(t.TITLE) LIKE LOWER('%{escaped_query}%')
            OR LOWER(t.SPEAKERS) LIKE LOWER('%{escaped_query}%')
            OR LOWER(t.TAGS) LIKE LOWER('%{escaped_query}%')
        ORDER BY t.PUBLISHED_DATE DESC
        LIMIT 20
    """
    try:
        df = session.sql(query).to_pandas()
        return df
    except Exception as e:
        st.error(f"Error searching: {e}")
        return pd.DataFrame()

def get_all_talks():
    """Fetch all TED talks from Snowflake"""
    session = get_snowflake_session()
    query = """
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
        ORDER BY t.PUBLISHED_DATE DESC
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
            t.TALK_ID,
            t.TITLE,
            t.SPEAKERS as SPEAKER,
            t.TAGS,
            t.PUBLISHED_DATE,
            t.DURATION_SEC / 60.0 as DURATION_MINUTES,
            t.URL,
            YEAR(t.PUBLISHED_DATE) as PUBLISHED_YEAR
        FROM ted_db.raw.ted_talks_raw t
        WHERE t.TALK_ID = '{talk_id}'
    """
    try:
        df = session.sql(query).to_pandas()
        return df.iloc[0] if not df.empty else None
    except Exception as e:
        st.error(f"Error fetching talk: {e}")
        return None

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

def get_user_recommendations(user_id):
    """Get personalized recommendations"""
    session = get_snowflake_session()
    query = f"""
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
        ORDER BY RANDOM()
        LIMIT 9
    """
    try:
        df = session.sql(query).to_pandas()
        return df
    except Exception as e:
        return get_all_talks().head(9)

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
        'business': '💼',
        'art': '🎨',
        'environment': '🌍',
    }
    
    for keyword, emoji in emoji_map.items():
        if keyword in tags_str:
            return emoji
    
    return '🎤'

# ==================== AI AGENT FUNCTIONS ====================

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
    """Route user query to appropriate agent"""
    query_lower = user_query.lower()
    
    if any(kw in query_lower for kw in ['summary', 'summarize']):
        return 'summary'
    elif any(kw in query_lower for kw in ['compare', 'versus', 'vs']):
        return 'comparison'
    else:
        return 'recommendation'

def summary_agent(talk_id):
    """Generate summary of a talk"""
    talk = get_talk_by_id(talk_id)
    if talk is None:
        return "Talk not found."
    
    prompt = f"Provide a brief summary of this TED talk: {talk['TITLE']} by {talk['SPEAKER']}"
    summary = call_cortex_llm(prompt)
    
    return f"""### 📝 Summary: "{talk['TITLE']}"
**Speaker:** {talk['SPEAKER']}

{summary}
"""

def compare_agent(talk_titles):
    """Compare two or more talks"""
    if len(talk_titles) < 2:
        return "Please provide at least 2 talks to compare."
    
    result = f"### ⚖️ Comparison of TED Talks\n\n"
    result += f"Comparing: {' vs '.join(talk_titles)}\n\n"
    result += "Comparison analysis will be generated using AI..."
    
    return result

def process_user_query(user_query, user_id):
    """Process user query through agent pipeline"""
    agent_type = router_agent(user_query)
    
    if agent_type == 'summary':
        return "To generate a summary, please select a specific talk."
    elif agent_type == 'comparison':
        return "To compare talks, please use the Compare Talks page."
    else:
        # Recommendation
        talks_df = search_talks(user_query)
        if talks_df.empty:
            return f"No talks found matching '{user_query}'."
        
        result = f"### 🎯 Recommended Talks for: '{user_query}'\n\n"
        for idx, (_, talk) in enumerate(talks_df.head(5).iterrows(), 1):
            result += f"**{idx}. {talk['TITLE']}**\n"
            result += f"   - Speaker: {talk['SPEAKER']}\n"
            result += f"   - Year: {talk['PUBLISHED_YEAR']}\n\n"
        
        return result

def log_watch_history(user_id, talk_id, watch_duration, total_duration):
    """Log watch history"""
    try:
        session = get_snowflake_session()
        watch_id = str(uuid.uuid4())
        query = f"""
            INSERT INTO ted_db.ted_schema_curated.user_watch_history 
            (watch_id, user_id, talk_id, watch_duration_seconds, total_duration_seconds, watched_at)
            VALUES ('{watch_id}', '{user_id}', '{talk_id}', {watch_duration}, {total_duration}, CURRENT_TIMESTAMP())
        """
        session.sql(query).collect()
    except:
        pass

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
            placeholder="🔍 Search for TED talks or ask AI: 'Find talks about AI' / 'Compare creativity talks' / 'I want to learn everything about climate change'", 
            label_visibility="collapsed"
        )
    with col2:
        search_button = st.button("Search", use_container_width=True, type="primary")
    
    if search_button and search_input:
        st.session_state.search_query = search_input
        debug_log(f"Search initiated with query: '{search_input}'")
        debug_log(f"User ID: {st.session_state.user_id}")
        
        # Debug panel
        if st.session_state.debug_mode:
            debug_panel = st.expander("🔍 Debug Execution Flow", expanded=True)
        
        # Run LangGraph agent pipeline
        with st.spinner("🤖 AI Agent processing your request..."):
            try:
                debug_log("Step 1: Importing langgraph_agents module...")
                from langgraph_agents import run_agent_pipeline
                debug_log("✓ Module imported successfully", "SUCCESS")
                
                debug_log("Step 2: Calling run_agent_pipeline()...")
                result = run_agent_pipeline(search_input, st.session_state.user_id)
                debug_log(f"✓ Pipeline execution completed. Success: {result['success']}", "SUCCESS")
                
                if result['success']:
                    # Show agent type
                    agent_type = result['agent_type'].upper()
                    debug_log(f"Step 3: Routed to {agent_type} Agent", "SUCCESS")
                    st.info(f"Routed to: **{agent_type} Agent**")
                    
                    # Show search results count
                    results_count = len(result.get('search_results', []))
                    debug_log(f"Step 4: Found {results_count} search results")
                    
                    # Show output
                    debug_log("Step 5: Displaying agent output...")
                    st.markdown(result['output'])
                    debug_log("✓ Output displayed", "SUCCESS")
                    
                    # Log search history
                    debug_log("Step 6: Logging search history to Snowflake...")
                    try:
                        log_search_history(
                            st.session_state.user_id, 
                            search_input, 
                            results_count
                        )
                        debug_log("✓ Search logged successfully", "SUCCESS")
                    except Exception as log_error:
                        debug_log(f"Warning: Failed to log search history: {log_error}", "WARNING")
                    
                    # Store in session for reference
                    if 'search_history' not in st.session_state:
                        st.session_state.search_history = []
                    st.session_state.search_history.append({
                        'query': search_input,
                        'agent': result['agent_type'],
                        'output': result['output']
                    })
                    debug_log("Step 7: Stored in session state", "SUCCESS")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    debug_log(f"Agent pipeline failed: {error_msg}", "ERROR")
                    st.error(f"Error: {error_msg}")
                    
            except ImportError as ie:
                debug_log(f"ImportError: LangGraph not available - {str(ie)}", "WARNING")
                debug_log("Falling back to simple search mode...")
                # Fallback to simple search if LangGraph not available
                st.warning("⚠️ LangGraph not available. Using simple search mode.")
                st.session_state.current_page = 'search'
                try:
                    talks_df = search_talks(search_input)
                    log_search_history(st.session_state.user_id, search_input, len(talks_df))
                    debug_log(f"Simple search completed: {len(talks_df)} results", "SUCCESS")
                except Exception as search_error:
                    debug_log(f"Simple search failed: {str(search_error)}", "ERROR")
                st.rerun()
                
            except Exception as e:
                debug_log(f"Unexpected error in agent pipeline: {str(e)}", "ERROR")
                st.error(f"❌ Error processing request: {e}")
                debug_log("Attempting fallback to simple search...")
                # Fallback
                st.session_state.current_page = 'search'
                try:
                    talks_df = search_talks(search_input)
                    log_search_history(st.session_state.user_id, search_input, len(talks_df))
                    debug_log("Fallback search successful", "SUCCESS")
                except Exception as fallback_error:
                    debug_log(f"Fallback search failed: {str(fallback_error)}", "ERROR")
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
    
    if st.button("← Back to Home"):
        st.session_state.current_page = 'home'
        st.rerun()
    
    st.markdown("---")
    
    with st.spinner("Searching for talks..."):
        filtered_talks = search_talks(st.session_state.search_query)
    
    if not filtered_talks.empty:
        st.success(f"### ✅ Found {len(filtered_talks)} talk(s)")
        st.markdown("---")
        
        for idx, (_, talk) in enumerate(filtered_talks.iterrows()):
            emoji = get_topic_emoji(talk['TAGS'])
            duration = format_duration(talk['DURATION_MINUTES'])
            
            col1, col2 = st.columns([8, 2])
            with col1:
                st.markdown(f"### {emoji} {talk['TITLE']}")
                st.markdown(f"**Speaker:** {talk['SPEAKER']} • **Year:** {talk['PUBLISHED_YEAR']} • **Duration:** {duration}")
                if not pd.isna(talk['TAGS']) and talk['TAGS']:
                    st.caption(f"Tags: {talk['TAGS']}")
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("▶️ Watch", key=f"search_{idx}", use_container_width=True):
                    st.session_state.selected_talk = talk['TALK_ID']
                    st.session_state.current_page = 'talk_detail'
                    st.rerun()
            st.markdown("---")
    else:
        st.warning(f"❌ No talks found for '{st.session_state.search_query}'")
        st.info("Try different keywords or check your spelling.")

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

    if 'last_ai_response' not in st.session_state:
        st.session_state.last_ai_response = None
        st.session_state.last_ai_question = None
    if 'last_agent' not in st.session_state:
        st.session_state.last_agent = None
    if not st.session_state.get('user_id'):
        st.warning("Please log in before asking a question.")
        return
    
    user_input = st.text_area(
        "Your question:",
        placeholder="e.g., 'Find talks about creativity' or 'Recommend science talks'",
        height=100,
        key="ai_input"
    )
    
    if st.button("Send", type="primary", use_container_width=True) and user_input:
        with st.spinner("Processing..."):
            agent = None
            try:
                agent = router_agent(user_input)
                st.session_state.last_agent = agent
                result = process_user_query(user_input, st.session_state.user_id)
            except Exception as e:
                result = f"Error while processing your question: {e}"
                st.error(result)
            st.session_state.last_ai_question = user_input
            st.session_state.last_ai_response = result
            st.session_state.chat_history.append({
                "user": user_input,
                "assistant": result
            })

    if st.session_state.last_ai_response:
        st.markdown("---")
        st.markdown("### Response:")
        if st.session_state.last_agent:
            st.info(f"Routed to: {st.session_state.last_agent}")
        if st.session_state.last_ai_question:
            st.markdown(f"**You:** {st.session_state.last_ai_question}")
        st.markdown(st.session_state.last_ai_response)
    
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
    
    # Debug Panel at bottom (always visible in debug mode)
    if st.session_state.get('debug_mode', False):
        st.markdown("---")
        st.markdown("## 🔍 Debug Information")
        
        # Debug controls
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🗑️ Clear Debug Logs"):
                st.session_state.debug_logs = []
                st.rerun()
        with col2:
            if st.button("🔄 Toggle Debug Mode"):
                st.session_state.debug_mode = not st.session_state.debug_mode
                st.rerun()
        with col3:
            st.write(f"**Status:** {'✅ ON' if st.session_state.debug_mode else '❌ OFF'}")
        
        # Session state viewer
        with st.expander("📊 Session State", expanded=False):
            session_info = {
                'logged_in': st.session_state.get('logged_in'),
                'username': st.session_state.get('username'),
                'user_id': st.session_state.get('user_id'),
                'current_page': st.session_state.get('current_page'),
                'search_query': st.session_state.get('search_query'),
                'selected_talk': st.session_state.get('selected_talk'),
            }
            st.json(session_info)
        
        # Debug logs viewer
        with st.expander(f"📝 Debug Logs ({len(st.session_state.get('debug_logs', []))} entries)", expanded=False):
            if st.session_state.debug_logs:
                for log in reversed(st.session_state.debug_logs[-50:]):  # Show last 50
                    st.text(log)
            else:
                st.info("No debug logs yet")

if __name__ == "__main__":
    main()