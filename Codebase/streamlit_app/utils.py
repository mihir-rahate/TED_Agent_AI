"""
Utility Functions
Helper functions for formatting, AI agents, and general utilities
"""

import pandas as pd
from db import call_cortex_llm, get_talk_by_id, search_talks


# ==================== FORMATTING HELPERS ====================

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
