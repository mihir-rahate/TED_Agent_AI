"""
UI Layout Components
Reusable layout components and styling
"""

import streamlit as st


# ==================== CUSTOM CSS STYLES ====================

def apply_custom_styles():
    """Apply custom CSS styles to the app"""
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


# ==================== REUSABLE COMPONENTS ====================

def render_talk_card(talk, emoji, duration, button_key, on_click_callback):
    """Render a talk card component"""
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
    
    if st.button("▶️ Watch", key=button_key, use_container_width=True):
        on_click_callback(talk['TALK_ID'])


def render_recommended_card(talk, emoji, duration, button_key, on_click_callback):
    """Render a recommended talk card component"""
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
    
    if st.button("▶️ Watch", key=button_key, use_container_width=True):
        on_click_callback(talk['TALK_ID'])


def render_video_player(talk, duration_display):
    """Render video player component"""
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


def render_sidebar_menu(username, on_logout):
    """Render sidebar menu"""
    from datetime import datetime
    
    st.markdown("### 👤 User Profile")
    st.markdown("---")
    st.markdown(f"**{username}**")
    st.markdown(f"*{datetime.now().strftime('%Y-%m-%d')}*")
    
    st.markdown("")
    st.markdown("### 📊 Menu")
    
    menu_items = {
        'home': ('🏠 Home', 'home'),
        'assistant': ('🤖 AI Assistant', 'assistant'),
        'compare': ('⚖️ Compare Talks', 'compare')
    }
    
    selected_page = None
    for key, (label, page) in menu_items.items():
        if st.button(label, use_container_width=True, key=f"menu_{key}"):
            selected_page = page
    
    st.markdown("<br>" * 5, unsafe_allow_html=True)
    
    if st.button("🚪 Logout", use_container_width=True, type="primary"):
        on_logout()
    
    return selected_page
