import streamlit as st
from datetime import datetime
from snowflake.snowpark.context import get_active_session
import pandas as pd
import json
import uuid
import hashlib
import re

from db import (
    search_talks, get_talk_by_id, create_user_account, 
    verify_user_login, log_watch_history, get_user_recommendations,
    save_chat_message,
    create_chat_session, update_chat_title, get_user_sessions, get_session_messages,
    validate_email, validate_password,
    save_user_playlist, get_user_playlists,
    save_conversation_note, get_saved_notes, get_note_content,
<<<<<<< HEAD
    call_cortex_summarize, # Using summarize for titles
    get_transcript # Phase 13
=======
    call_cortex_summarize,
    get_transcript
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
)
from langgraph_agents import run_agent_pipeline, run_qa_pipeline

# Page configuration
st.set_page_config(
    page_title="TED Talks Analytics",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

<<<<<<< HEAD
# Initialize global state (NOT per-session variables like messages)
=======
# Initialize global state
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'sidebar_open' not in st.session_state:
    st.session_state.sidebar_open = True

# Session-specific State
if 'viewing_note' not in st.session_state:
    st.session_state.viewing_note = False
if 'current_note_title' not in st.session_state:
    st.session_state.current_note_title = ""
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = None 

<<<<<<< HEAD
# ==================== MAIN UI COMPONENTS ====================

def new_chat():
    """Start a new chat session (Create in DB immediately)"""
=======
# ==================== ENHANCED CUSTOM CSS ====================

def apply_enhanced_styles():
    """Apply modern, interactive CSS styles"""
    st.markdown("""
        <style>
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* Global Styles */
        * {
            font-family: 'Inter', sans-serif;
        }
        
        /* Hide Streamlit Branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Main Container */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 10rem;
            max-width: 1400px;
        }
        
        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
            padding-top: 2rem;
        }
        
        [data-testid="stSidebar"] * {
            color: white !important;
        }
        
        /* Sidebar Buttons */
        [data-testid="stSidebar"] button {
            background: rgba(255, 255, 255, 0.1) !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 12px !important;
            transition: all 0.3s ease !important;
            margin-bottom: 8px !important;
            font-weight: 500 !important;
        }
        
        [data-testid="stSidebar"] button:hover {
            background: rgba(255, 43, 6, 0.2) !important;
            border-color: #ff2b06 !important;
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(255, 43, 6, 0.3) !important;
        }
        
        /* Primary Button (New Chat) */
        [data-testid="stSidebar"] button[kind="primary"] {
            background: linear-gradient(135deg, #ff2b06 0%, #e74c3c 100%) !important;
            border: none !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 12px rgba(255, 43, 6, 0.4) !important;
        }
        
        [data-testid="stSidebar"] button[kind="primary"]:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 16px rgba(255, 43, 6, 0.5) !important;
        }
        
        /* Chat Messages */
        .stChatMessage {
            background: white !important;
            border-radius: 16px !important;
            padding: 20px !important;
            margin-bottom: 16px !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
            border: 1px solid #f0f0f0 !important;
            transition: all 0.3s ease !important;
        }
        
        .stChatMessage:hover {
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12) !important;
            transform: translateY(-2px);
        }
        
        /* User Message */
        [data-testid="stChatMessageContent"] {
            background: transparent !important;
        }
        
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageContent"]:first-child) {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
        }
        
        /* Assistant Message */
        div[data-testid="stChatMessage"]:not(:has(div[data-testid="stChatMessageContent"]:first-child)) {
            background: white !important;
            border-left: 4px solid #ff2b06 !important;
        }
        
        /* Chat Input */
        .stChatInput {
            padding-bottom: 2rem !important;
        }
        
        .stChatInput > div {
            border-radius: 50px !important;
            border: 2px solid #e0e0e0 !important;
            background: white !important;
            overflow: hidden !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
        }
        
        .stChatInput textarea {
            font-size: 1.05rem !important;
            min-height: 3.5rem !important;
            border: none !important;
            border-radius: 50px !important;
            padding: 16px 24px !important;
            transition: all 0.3s ease !important;
            background: transparent !important;
        }
        
        .stChatInput textarea:focus {
            outline: none !important;
            box-shadow: none !important;
        }
        
        .stChatInput > div:focus-within {
            border-color: #667eea !important;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2) !important;
        }
        
        /* Send Button - Make it Blue */
        .stChatInput button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            border: none !important;
            border-radius: 50% !important;
            width: 48px !important;
            height: 48px !important;
            min-width: 48px !important;
            padding: 0 !important;
            transition: all 0.3s ease !important;
        }
        
        .stChatInput button:hover {
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%) !important;
            transform: scale(1.1) !important;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
        }
        
        .stChatInput button svg {
            fill: white !important;
        }
        
        /* Bottom spacing fix */
        .main .block-container {
            padding-bottom: 8rem !important;
        }
        
        /* Status Container */
        .stStatus {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%) !important;
            border-radius: 12px !important;
            border: none !important;
            padding: 16px !important;
        }
        
        /* Headers */
        h1, h2, h3 {
            color: #1a1a2e !important;
            font-weight: 700 !important;
        }
        
        /* Dividers */
        hr {
            margin: 2rem 0;
            border: none;
            height: 1px;
            background: linear-gradient(to right, transparent, #e0e0e0, transparent);
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: transparent;
        }
        
        .stTabs [data-baseweb="tab"] {
            border-radius: 12px;
            padding: 12px 24px;
            background: white;
            border: 2px solid #e0e0e0;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            border-color: #ff2b06;
            transform: translateY(-2px);
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #ff2b06 0%, #e74c3c 100%);
            color: white !important;
            border-color: #ff2b06;
        }
        
        /* Input Fields */
        input {
            border-radius: 12px !important;
            border: 2px solid #e0e0e0 !important;
            padding: 12px !important;
            transition: all 0.3s ease !important;
        }
        
        input:focus {
            border-color: #ff2b06 !important;
            box-shadow: 0 0 0 4px rgba(255, 43, 6, 0.1) !important;
        }
        
        /* Buttons */
        button {
            border-radius: 12px !important;
            font-weight: 600 !important;
            transition: all 0.3s ease !important;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        }
        
        /* Form Buttons */
        .stButton button {
            background: linear-gradient(135deg, #ff2b06 0%, #e74c3c 100%) !important;
            color: white !important;
            border: none !important;
            padding: 14px 28px !important;
            font-size: 16px !important;
        }
        
        .stButton button:hover {
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%) !important;
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            border-radius: 12px !important;
            background: #f8f9fa !important;
            font-weight: 600 !important;
        }
        
        /* Success/Error/Warning Messages */
        .stSuccess, .stError, .stWarning, .stInfo {
            border-radius: 12px !important;
            padding: 16px !important;
            border: none !important;
        }
        
        /* Multiselect */
        .stMultiSelect > div {
            border-radius: 12px !important;
        }
        
        /* Playlist Cards */
        .playlist-card {
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            border: 2px solid #e0e0e0;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .playlist-card:hover {
            border-color: #ff2b06;
            box-shadow: 0 4px 12px rgba(255, 43, 6, 0.2);
            transform: translateX(5px);
        }
        
        /* Animation */
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .stChatMessage {
            animation: fadeIn 0.5s ease;
        }
        </style>
    """, unsafe_allow_html=True)

# ==================== MAIN UI COMPONENTS ====================

def new_chat():
    """Start a new chat session"""
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
    st.session_state.session_id = create_chat_session(st.session_state.user_id)
    st.session_state.messages = []
    st.session_state.viewing_note = False 
    st.rerun()

def load_chat_session(session_id):
<<<<<<< HEAD
    """Load a specific chat session detailed history"""
=======
    """Load a specific chat session"""
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
    st.session_state.session_id = session_id
    st.session_state.messages = get_session_messages(session_id)
    st.session_state.viewing_note = False
    st.rerun()

def process_user_query(query, user_id):
    """Process query using LangGraph Pipeline"""
    result = run_agent_pipeline(query, user_id)
    if result['success']:
        return result['output']
    else:
        return f"⚠️ Error: {result.get('error', 'Unknown error')}"

def generate_title_if_needed(prompt):
    """Auto-generate title for new chats"""
<<<<<<< HEAD
    # Simply check if it's the first message and title is redundant
    # We can rely on message count. If len(messages) == 2 (User + AI), we generate.
    if len(st.session_state.messages) == 2:
        try:
            summary = call_cortex_summarize(prompt)
            # Cortex summarize might be too long, let's just clip it or use it.
            # Ideally we'd use COMPLETE but SUMMARIZE is cheaper/faster often. 
            # Let's take first 5 words or so? Or just use prompt.
            # Let's try to be smarter: "Analysis of [Subject]"
=======
    if len(st.session_state.messages) == 2:
        try:
            summary = call_cortex_summarize(prompt)
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
            title = f"{summary[:40]}..." if len(summary) > 40 else summary
            update_chat_title(st.session_state.session_id, title)
        except:
            pass

def main_app():
<<<<<<< HEAD
    """Main Chat Interface"""
    
    # Custom CSS for Chat UI
    # Custom CSS for Chat UI
    st.markdown("""
        <style>
        /* Increase bottom padding so content doesn't get hidden behind input */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 5rem;
        }
        
        /* Style the bottom chat input container */
        .stChatInput {
            bottom: 20px;
            padding-bottom: 20px;
        }
        
        /* Make the actual input text area larger and more readable */
        .stChatInput textarea {
            font-size: 1.1rem !important;
            min-height: 3rem !important;
            border-radius: 12px;
        }
        </style>
    """, unsafe_allow_html=True)

=======
    """Main Chat Interface with Enhanced Layout"""
    
    apply_enhanced_styles()
    
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
    # Ensure valid session exists
    if not st.session_state.session_id:
        st.session_state.session_id = create_chat_session(st.session_state.user_id)
        st.session_state.messages = []
    
<<<<<<< HEAD
    # --- Sidebar (History & Menu) ---
    with st.sidebar:
        st.title("🤖 TED AI Agent")
        
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            new_chat()
            
        # --- PLAYLISTS SECTION ---
        st.markdown("---")
=======
    # --- Enhanced Sidebar ---
    with st.sidebar:
        # Header with Icon
        st.markdown("""
            <div style="text-align: center; padding: 20px 0;">
                <div style="font-size: 48px; margin-bottom: 10px;">🤖</div>
                <h2 style="margin: 0; color: white;">TED AI Agent</h2>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            new_chat()
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- PLAYLISTS SECTION ---
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
        st.markdown("### 🗂️ My Playlists")
        playlists = get_user_playlists(st.session_state.user_id)
        if not playlists.empty:
            for _, row in playlists.iterrows():
                topic = row['topic'] if row['topic'] else "Untitled Playlist"
                date_str = row['created_at'].strftime("%b %d")
<<<<<<< HEAD
                label = f"📚 {topic} ({date_str})"
                if st.button(label, key=f"pl_{row['playlist_id']}", use_container_width=True):
=======
                
                # Enhanced playlist card
                st.markdown(f"""
                    <div style="background: rgba(255, 255, 255, 0.1); 
                                border-radius: 12px; 
                                padding: 12px; 
                                margin-bottom: 8px;
                                border: 1px solid rgba(255, 255, 255, 0.2);
                                transition: all 0.3s ease;">
                        <div style="font-size: 20px;">📚</div>
                        <div style="font-weight: 600; margin: 8px 0;">{topic}</div>
                        <div style="font-size: 12px; opacity: 0.7;">{date_str}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                if st.button("View", key=f"pl_{row['playlist_id']}", use_container_width=True):
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"📜 **Opening Saved Playlist:**\n\n{row['content_markdown']}"
                    })
                    st.session_state.viewing_note = False
                    st.rerun()
        else:
<<<<<<< HEAD
            st.caption("No saved playlists yet.")
            
        # --- RECENT CHATS (PRODUCTION PERSISTENCE) ---
        st.markdown("---")
=======
            st.markdown("""
                <div style="text-align: center; padding: 20px; opacity: 0.7;">
                    <div style="font-size: 32px; margin-bottom: 8px;">📋</div>
                    <div>No saved playlists yet</div>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- RECENT CHATS ---
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
        st.markdown("### 🕒 Recent Chats")
        sessions = get_user_sessions(st.session_state.user_id)
        if sessions:
            for sess in sessions:
<<<<<<< HEAD
                # Highlight active session
=======
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
                is_active = (sess['session_id'] == st.session_state.session_id)
                icon = "🟢" if is_active else "💬"
                label = f"{icon} {sess['title']}"
                
                if st.button(label, key=sess['session_id'], use_container_width=True):
                    load_chat_session(sess['session_id'])
        else:
<<<<<<< HEAD
            st.info("Start a new chat!")
            
        st.markdown("---")
        st.markdown(f"👤 **{st.session_state.username}**")
=======
            st.markdown("""
                <div style="text-align: center; padding: 20px; opacity: 0.7;">
                    <div style="font-size: 32px; margin-bottom: 8px;">💭</div>
                    <div>Start a new chat!</div>
                </div>
            """, unsafe_allow_html=True)
        
        # Footer
        st.markdown("<br>" * 3, unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"""
            <div style="text-align: center; padding: 16px;">
                <div style="font-size: 24px; margin-bottom: 8px;">👤</div>
                <div style="font-weight: 600;">{st.session_state.username}</div>
                <div style="font-size: 12px; opacity: 0.7; margin-top: 4px;">
                    {datetime.now().strftime('%B %d, %Y')}
                </div>
            </div>
        """, unsafe_allow_html=True)
        
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.messages = []
            st.session_state.session_id = None
            st.rerun()

<<<<<<< HEAD
    # --- Main Chat Area ---
=======
    # --- Main Chat Area with Welcome Message ---
    if len(st.session_state.messages) == 0:
        st.markdown("""
            <div style="text-align: center; padding: 60px 20px;">
                <div style="font-size: 80px; margin-bottom: 20px;">🎤</div>
                <h1 style="margin-bottom: 16px;">Welcome to TED Talks AI Assistant</h1>
                <p style="font-size: 18px; color: #666; max-width: 600px; margin: 0 auto;">
                    Ask me anything about TED talks, get personalized recommendations, 
                    create learning playlists, and explore the world of ideas!
                </p>
                <div style="margin-top: 40px; display: flex; gap: 20px; justify-content: center; flex-wrap: wrap;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                color: white; padding: 20px 30px; border-radius: 16px; 
                                max-width: 300px; text-align: left;">
                        <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
                        <div style="font-weight: 600; margin-bottom: 8px;">Search & Discover</div>
                        <div style="font-size: 14px; opacity: 0.9;">Find talks on any topic</div>
                    </div>
                    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                                color: white; padding: 20px 30px; border-radius: 16px; 
                                max-width: 300px; text-align: left;">
                        <div style="font-size: 32px; margin-bottom: 8px;">📚</div>
                        <div style="font-weight: 600; margin-bottom: 8px;">Create Playlists</div>
                        <div style="font-size: 14px; opacity: 0.9;">Curated learning paths</div>
                    </div>
                    <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                                color: white; padding: 20px 30px; border-radius: 16px; 
                                max-width: 300px; text-align: left;">
                        <div style="font-size: 32px; margin-bottom: 8px;">✨</div>
                        <div style="font-weight: 600; margin-bottom: 8px;">AI Recommendations</div>
                        <div style="font-size: 14px; opacity: 0.9;">Personalized for you</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
    
    # Display Chat History
    for msg in st.session_state.messages:
        role = msg.get('role', 'user').lower()
        content = msg.get('content', '')
        with st.chat_message(role):
            st.markdown(content)
<<<<<<< HEAD
            
    # Chat Input
    if prompt := st.chat_input("Ask me about any TED talk..."):
        # 1. User Message
=======
    
    # Chat Input
    if prompt := st.chat_input("Ask me about any TED talk..."):
        # User Message
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
<<<<<<< HEAD
        # Save User Message & Update Title
        save_chat_message(st.session_state.user_id, st.session_state.session_id, "user", prompt)
        
        # 2. Assistant Response
        with st.chat_message("assistant"):
            # Professional Status Container
            with st.status("Processing your request...", expanded=True) as status:
                st.write("Connecting to AI Agent Network...")
                response_data = process_user_query(prompt, st.session_state.user_id)
                status.update(label="Complete!", state="complete", expanded=False)
            
            st.markdown(response_data)
                
            # Store & Save Assistant Message
            st.session_state.messages.append({"role": "assistant", "content": response_data})
            save_chat_message(st.session_state.user_id, st.session_state.session_id, "assistant", response_data)
            
            # Auto-Title (if new chat)
            try: 
               generate_title_if_needed(prompt)
            except:
               pass
                
            # 3. Save Playlist Logic
            if "Learning Playlist" in response_data:
                topic_match = re.search(r"Learning Playlist: (.*)", response_data)
                topic = topic_match.group(1).strip() if topic_match else "Custom Playlist"
                if st.button("💾 Save Playlist to Library", key=f"save_btn_{len(st.session_state.messages)}"):
                    success = save_user_playlist(st.session_state.user_id, topic, response_data)
                    if success:
                        st.success(f"✅ Saved playlist: {topic}")
                        st.rerun()
                    else:
                        st.error("Check logs.")


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
=======
        save_chat_message(st.session_state.user_id, st.session_state.session_id, "user", prompt)
        
        # Assistant Response
        with st.chat_message("assistant"):
            with st.status("🤖 Processing your request...", expanded=True) as status:
                st.write("🔍 Analyzing your query...")
                st.write("🧠 Consulting AI agents...")
                response_data = process_user_query(prompt, st.session_state.user_id)
                st.write("✅ Generating response...")
                status.update(label="✨ Complete!", state="complete", expanded=False)
            
            st.markdown(response_data)
            
            st.session_state.messages.append({"role": "assistant", "content": response_data})
            save_chat_message(st.session_state.user_id, st.session_state.session_id, "assistant", response_data)
            
            try: 
                generate_title_if_needed(prompt)
            except:
                pass
            
            # Save Playlist Logic
            if "Learning Playlist" in response_data:
                topic_match = re.search(r"Learning Playlist: (.*)", response_data)
                topic = topic_match.group(1).strip() if topic_match else "Custom Playlist"
                
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("💾 Save Playlist to Library", 
                                key=f"save_btn_{len(st.session_state.messages)}", 
                                use_container_width=True):
                        success = save_user_playlist(st.session_state.user_id, topic, response_data)
                        if success:
                            st.success(f"✅ Saved playlist: {topic}")
                            st.rerun()
                        else:
                            st.error("Error saving playlist")


def login_page():
    """Enhanced Login Page"""
    
    apply_enhanced_styles()
    
    # Hero Header
    st.markdown("""
        <div style="text-align: center; padding: 40px 20px;">
            <div style="font-size: 80px; margin-bottom: 20px;">🎤</div>
            <h1 style="font-size: 48px; margin-bottom: 16px; 
                       background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                       -webkit-background-clip: text;
                       -webkit-text-fill-color: transparent;">
                TED Talks AI Analytics
            </h1>
            <p style="font-size: 20px; color: #666;">
                Discover, Learn, and Explore with AI-Powered Insights
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Login", "✨ Create Account"])
    
    with tab1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### Login to Your Account")
            
            with st.form("login_form"):
                email = st.text_input("📧 Email Address", placeholder="your.email@example.com")
                password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("Login", use_container_width=True)
                
                if submit:
                    if not email or not password:
                        st.warning("⚠️ Please enter both email and password")
                    elif not validate_email(email):
                        st.error("❌ Please enter a valid email address")
                    else:
                        with st.spinner("Logging in..."):
                            success, user_data = verify_user_login(email, password)
                            if success:
                                st.session_state.logged_in = True
                                st.session_state.username = user_data['FULL_NAME']
                                st.session_state.user_id = user_data['USER_ID']
                                st.session_state.user_email = user_data['EMAIL']
                                st.session_state.user_topics = user_data['TOPICS_OF_INTEREST']
                                st.success(f"✅ Welcome back, {user_data['FULL_NAME']}!")
                                st.rerun()
                            else:
                                st.error("❌ Invalid email or password. Please try again.")
    
    with tab2:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### Create Your Account")
            
            with st.form("create_account_form"):
                full_name = st.text_input("👤 Full Name *", placeholder="John Doe")
                email = st.text_input("📧 Email Address *", placeholder="john.doe@example.com")
                
                password = st.text_input("🔒 Password *", type="password", 
                                        help="Must contain: uppercase, lowercase, number, special character")
                confirm_password = st.text_input("🔒 Confirm Password *", type="password")
                
                st.markdown("**🎯 Topics of Interest** *(optional)*")
                topic_options = [
                    "Science", "Technology", "Psychology", "Education", 
                    "Health", "Business", "Art", "Design", "Entertainment",
                    "Environment", "Politics", "Culture", "Innovation"
                ]
                
                selected_topics = st.multiselect(
                    "Choose topics you'd like to explore",
                    options=topic_options,
                    default=[],
                    label_visibility="collapsed"
                )
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("Create Account", use_container_width=True)
                
                if submit:
                    errors = []
                    
                    if not full_name or not email or not password or not confirm_password:
                        errors.append("Please fill in all required fields")
                    
                    if not validate_email(email):
                        errors.append("Please enter a valid email address")
                    
                    if password != confirm_password:
                        errors.append("Passwords do not match")
                    
                    is_valid, msg = validate_password(password)
                    if not is_valid:
                        errors.append(msg)
                    
                    if errors:
                        for error in errors:
                            st.error(f"❌ {error}")
                    else:
                        topics_str = ", ".join(selected_topics) if selected_topics else "Not specified"
                        
                        with st.spinner("Creating your account..."):
                            success, message, user_id = create_user_account(
                                full_name, email, password, topics_str
                            )
                            
                            if success:
                                st.success(f"✅ {message}")
                                st.info("🎉 Account created! Please go to the Login tab to sign in.")
                                st.balloons()
                            else:
                                st.error(f"❌ {message}")
            
            with st.expander("🔐 Password Requirements"):
                st.markdown("""
                Your password must contain:
                - ✓ At least 8 characters
                - ✓ One uppercase letter (A-Z)
                - ✓ One lowercase letter (a-z)
                - ✓ One number (0-9)
                - ✓ One special character (!@#$%^&*)
                """)
>>>>>>> 137e32497b150395531ba55e991498158f5f2ca4

def main():
    if st.session_state.get('logged_in'):
        main_app()
    else:
        login_page()

if __name__ == "__main__":
    main()