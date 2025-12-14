"""
Constants and Configuration
Application-wide constants and configuration values
"""

# ==================== APP CONFIGURATION ====================

APP_TITLE = "TED Talks Analytics"
APP_ICON = "🎤"
APP_LAYOUT = "wide"

# ==================== DATABASE CONFIGURATION ====================

# Database
DB_NAME = "TED_DB"

# Schemas
SCHEMA_RAW = "RAW"
SCHEMA_SEMANTIC = "SEMANTIC"
SCHEMA_TED = "TED_SCHEMA"
SCHEMA_CURATED = "TED_SCHEMA_CURATED"
SCHEMA_APP = "APP"
SCHEMA_CURATED_SIMPLE = "CURATED"

# RAW Schema Tables
TABLE_TED_TALKS_RAW = f"{DB_NAME}.{SCHEMA_RAW}.TED_TALKS_RAW"
TABLE_TED_TRANSCRIPTS_RAW = f"{DB_NAME}.{SCHEMA_RAW}.TED_TRANSCRIPTS_RAW"
TABLE_TED_TRANSCRIPT_SEGMENTS_RAW = f"{DB_NAME}.{SCHEMA_RAW}.TED_TRANSCRIPT_SEGMENTS_RAW"
TABLE_STG_TED_TRANSCRIPT_CHUNKS = f"{DB_NAME}.{SCHEMA_RAW}.STG_TED_TRANSCRIPT_CHUNKS"

# RAW Schema Views
VIEW_STG_TED_TALKS = f"{DB_NAME}.{SCHEMA_RAW}.STG_TED_TALKS"
VIEW_STG_TED_TRANSCRIPTS = f"{DB_NAME}.{SCHEMA_RAW}.STG_TED_TRANSCRIPTS"

# SEMANTIC Schema Tables
TABLE_TED_EMBEDDINGS = f"{DB_NAME}.{SCHEMA_SEMANTIC}.TED_EMBEDDINGS"

# TED_SCHEMA_CURATED Tables
TABLE_FCT_TED_EMBEDDINGS = f"{DB_NAME}.{SCHEMA_CURATED}.FCT_TED_EMBEDDINGS"
TABLE_FCT_TED_TALKS = f"{DB_NAME}.{SCHEMA_CURATED}.FCT_TED_TALKS"
TABLE_USERS = f"{DB_NAME}.{SCHEMA_CURATED}.USERS"
TABLE_USER_FAVORITES = f"{DB_NAME}.{SCHEMA_CURATED}.USER_FAVORITES"
TABLE_SEARCH_HISTORY = f"{DB_NAME}.{SCHEMA_CURATED}.USER_SEARCH_HISTORY"
TABLE_WATCH_HISTORY = f"{DB_NAME}.{SCHEMA_CURATED}.USER_WATCH_HISTORY"

# APP Schema Views
VIEW_TED_TALKS = f"{DB_NAME}.{SCHEMA_APP}.TED_TALKS_VIEW"

# CURATED Schema Tables
TABLE_TED_TALKS_CURATED = f"{DB_NAME}.{SCHEMA_CURATED_SIMPLE}.TED_TALKS"
TABLE_TED_TRANSCRIPT_CHUNKS = f"{DB_NAME}.{SCHEMA_CURATED_SIMPLE}.TED_TRANSCRIPT_CHUNKS"

# Default table to use for main queries (choose based on your preference)
TABLE_TED_TALKS = TABLE_TED_TALKS_RAW  # or use TABLE_TED_TALKS_CURATED or VIEW_TED_TALKS

# ==================== AI CONFIGURATION ====================

DEFAULT_LLM_MODEL = "llama3.1-405b"
MAX_PROMPT_LENGTH = 10000
MAX_SEARCH_RESULTS = 20
MAX_TALKS_DISPLAY = 50
MAX_RECOMMENDATIONS = 9

# ==================== TOPIC CATEGORIES ====================

TOPIC_OPTIONS = [
    "Science",
    "Technology",
    "Psychology",
    "Education",
    "Health",
    "Business",
    "Art",
    "Design",
    "Entertainment",
    "Environment",
    "Politics",
    "Culture",
    "Innovation"
]

# ==================== EMOJI MAPPINGS ====================

TOPIC_EMOJI_MAP = {
    'science': '🔬',
    'technology': '💻',
    'psychology': '🧠',
    'education': '🎓',
    'health': '🏥',
    'business': '💼',
    'art': '🎨',
    'environment': '🌍',
    'design': '🎨',
    'entertainment': '🎭',
    'politics': '🏛️',
    'culture': '🌐',
    'innovation': '💡'
}

DEFAULT_EMOJI = '🎤'

# ==================== PASSWORD VALIDATION ====================

PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIREMENTS = """
Your password must contain:
- At least 8 characters
- One uppercase letter (A-Z)
- One lowercase letter (a-z)
- One number (0-9)
- One special character (!@#$%^&*(),.?":{}|<>)
"""

# ==================== AGENT TYPES ====================

AGENT_TYPES = {
    'QA': 'qa',
    'SUMMARY': 'summary',
    'COMPARISON': 'comparison',
    'RECOMMENDATION': 'recommendation',
    'PLAYLIST': 'playlist'
}

# ==================== UI MESSAGES ====================

MESSAGES = {
    'welcome': "🎤 Discover TED Talks",
    'search_placeholder': "🔍 Search for TED talks or ask AI: 'Find talks about AI' / 'Compare creativity talks' / 'I want to learn everything about climate change'",
    'no_results': "No talks found. Try different keywords or check your spelling.",
    'loading': "Loading...",
    'processing': "🤖 AI Agent processing your request...",
    'login_required': "Please log in to continue.",
    'account_created': "Account created! Please go to the Login tab to sign in.",
    'logout_success': "You have been logged out successfully."
}

# ==================== COLOR SCHEME ====================

COLORS = {
    'primary': '#ff2b06',  # TED Red
    'secondary': '#e74c3c',
    'background': '#f8f9fa',
    'text': '#333333',
    'text_light': '#666666',
    'border': '#e0e0e0',
    'success': '#28a745',
    'warning': '#ffc107',
    'error': '#dc3545'
}
