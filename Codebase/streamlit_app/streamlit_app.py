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
    call_cortex_summarize, # Using summarize for titles
    get_transcript # Phase 13
)
from langgraph_agents import run_agent_pipeline, run_qa_pipeline

# Page configuration
st.set_page_config(
    page_title="TED Talks Analytics",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize global state (NOT per-session variables like messages)
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

# ==================== MAIN UI COMPONENTS ====================

def new_chat():
    """Start a new chat session (Create in DB immediately)"""
    st.session_state.session_id = create_chat_session(st.session_state.user_id)
    st.session_state.messages = []
    st.session_state.viewing_note = False 
    st.rerun()

def load_chat_session(session_id):
    """Load a specific chat session detailed history"""
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
    # Simply check if it's the first message and title is redundant
    # We can rely on message count. If len(messages) == 2 (User + AI), we generate.
    if len(st.session_state.messages) == 2:
        try:
            summary = call_cortex_summarize(prompt)
            # Cortex summarize might be too long, let's just clip it or use it.
            # Ideally we'd use COMPLETE but SUMMARIZE is cheaper/faster often. 
            # Let's take first 5 words or so? Or just use prompt.
            # Let's try to be smarter: "Analysis of [Subject]"
            title = f"{summary[:40]}..." if len(summary) > 40 else summary
            update_chat_title(st.session_state.session_id, title)
        except:
            pass

def main_app():
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

    # Ensure valid session exists
    if not st.session_state.session_id:
        st.session_state.session_id = create_chat_session(st.session_state.user_id)
        st.session_state.messages = []
    
    # --- Sidebar (History & Menu) ---
    with st.sidebar:
        st.title("🤖 TED AI Agent")
        
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            new_chat()
            
        # --- PLAYLISTS SECTION ---
        st.markdown("---")
        st.markdown("### 🗂️ My Playlists")
        playlists = get_user_playlists(st.session_state.user_id)
        if not playlists.empty:
            for _, row in playlists.iterrows():
                topic = row['topic'] if row['topic'] else "Untitled Playlist"
                date_str = row['created_at'].strftime("%b %d")
                label = f"📚 {topic} ({date_str})"
                if st.button(label, key=f"pl_{row['playlist_id']}", use_container_width=True):
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"📜 **Opening Saved Playlist:**\n\n{row['content_markdown']}"
                    })
                    st.session_state.viewing_note = False
                    st.rerun()
        else:
            st.caption("No saved playlists yet.")
            
        # --- RECENT CHATS (PRODUCTION PERSISTENCE) ---
        st.markdown("---")
        st.markdown("### 🕒 Recent Chats")
        sessions = get_user_sessions(st.session_state.user_id)
        if sessions:
            for sess in sessions:
                # Highlight active session
                is_active = (sess['session_id'] == st.session_state.session_id)
                icon = "🟢" if is_active else "💬"
                label = f"{icon} {sess['title']}"
                
                if st.button(label, key=sess['session_id'], use_container_width=True):
                    load_chat_session(sess['session_id'])
        else:
            st.info("Start a new chat!")
            
        st.markdown("---")
        st.markdown(f"👤 **{st.session_state.username}**")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.messages = []
            st.session_state.session_id = None
            st.rerun()

    # --- Main Chat Area ---
    
    # Display Chat History
    for msg in st.session_state.messages:
        role = msg.get('role', 'user').lower()
        content = msg.get('content', '')
        with st.chat_message(role):
            st.markdown(content)
            
    # Chat Input
    if prompt := st.chat_input("Ask me about any TED talk..."):
        # 1. User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
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

def main():
    if st.session_state.get('logged_in'):
        main_app()
    else:
        login_page()

if __name__ == "__main__":
    main()