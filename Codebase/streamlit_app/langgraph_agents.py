"""
LangGraph Multi-Agent System with Router
Architecture: Hub-and-Spoke
- Router Agent (Dispatcher)
  |-- Recommendation Pipeline (Intent -> Search -> Rank -> Reason -> Final)
  |-- Playlist Agent (Stub)
  |-- Unknown Handler
"""

import streamlit as st
from typing import TypedDict, List, Dict, Any, Optional, Literal
import json
import re
from db import call_cortex_llm, search_talks
import logging

# ==================== GUARDRAILS MODULE ====================
# Purpose: Ensure safe, professional, and grounded AI behavior
# Design: "Deliberately limited, not broken"

# --- Constants ---
MIN_QUERY_LENGTH = 3
MAX_QUERY_LENGTH = 2000
MAX_OUTPUT_LENGTH = 15000
DISCLAIMER_TEXT = "\n\n---\n*Responses are generated based on TED Talk transcripts and metadata.*"

# Phrases to avoid in outputs (absolute/authoritative language)
FORBIDDEN_PHRASES = ["guaranteed", "always correct", "100%", "definitely the best", "proven fact"]

# --- 1. Input Guardrails ---
def validate_input(query: str) -> tuple[bool, str]:
    """
    Validate user input before any processing.
    Returns: (is_valid, sanitized_query_or_error_message)
    """
    if not query or not isinstance(query, str):
        return False, "Please enter a question or request about TED Talks."
    
    # Strip and normalize
    query = query.strip()
    
    # Length checks
    if len(query) < MIN_QUERY_LENGTH:
        return False, "Your message is too short. Please provide more detail about what you're looking for."
    
    if len(query) > MAX_QUERY_LENGTH:
        return False, "Your message is too long. Please try a shorter, more focused question."
    
    # Check for meaningless input (only special chars or numbers)
    if not any(c.isalpha() for c in query):
        return False, "I didn't quite understand that. Could you rephrase your question about TED Talks?"
    
    return True, query

def sanitize_input(query: str) -> str:
    """Normalize and clean user input safely."""
    if not query:
        return ""
    # Remove excessive whitespace
    query = " ".join(query.split())
    # Remove potential injection patterns (conservative)
    query = query.replace("```", "").replace("<<<", "").replace(">>>", "")
    return query[:MAX_QUERY_LENGTH]

# --- 2. Output Guardrails ---
def sanitize_output(output: str, add_disclaimer: bool = False) -> str:
    """
    Clean and validate agent output before returning to user.
    Removes internal terminology and ensures professional tone.
    """
    if not output:
        return "I apologize, but I couldn't generate a response. Please try rephrasing your question."
    
    # Truncate if too long
    if len(output) > MAX_OUTPUT_LENGTH:
        output = output[:MAX_OUTPUT_LENGTH] + "\n\n*[Response truncated for readability]*"
    
    # Remove internal agent terminology
    internal_terms = ["ROUTER", "AGENT", "LangGraph", "node", "state", "pipeline"]
    for term in internal_terms:
        output = re.sub(rf'\b{term}\b', '', output, flags=re.IGNORECASE)
    
    # Soften absolute language
    for phrase in FORBIDDEN_PHRASES:
        output = output.replace(phrase, "likely")
    
    # Add disclaimer once per session if requested
    if add_disclaimer and DISCLAIMER_TEXT not in output:
        output += DISCLAIMER_TEXT
    
    return output.strip()

def format_error_gracefully(error: Exception, context: str = "") -> str:
    """Convert exceptions to user-friendly messages without exposing internals."""
    logging.error(f"Guardrail caught error in {context}: {error}")
    return (
        "I encountered an issue processing your request. "
        "Please try again or rephrase your question. "
        "If the problem persists, try a simpler query."
    )

# --- 3. State Guardrails ---
def ensure_safe_state(state: dict) -> dict:
    """Ensure all required state fields have safe defaults."""
    defaults = {
        'user_query': '',
        'user_id': 'anonymous',
        'routing_decision': 'unknown',
        'router_metadata': {},
        'intent': {},
        'candidates': [],
        'ranked_talks': [],
        'playlist_plan': {},
        'final_output': '',
        'error': None
    }
    for key, default in defaults.items():
        if key not in state or state[key] is None:
            state[key] = default
    return state

def validate_routing_confidence(response_data: dict) -> bool:
    """Check if routing decision has sufficient confidence."""
    destination = response_data.get('destination', '')
    topic = response_data.get('primary_topic', '')
    
    # If destination is empty or topic is too vague, route to unknown
    if not destination or destination not in [
        'recommendation_agent', 'playlist_agent', 'comparison_agent',
        'qa_specific_talk', 'summarize_talk', 'unknown'
    ]:
        return False
    
    # For QA/Summary, require a target talk identifier
    if destination in ['qa_specific_talk', 'summarize_talk']:
        if not response_data.get('target_talk'):
            return False
    
    return True

# --- 4. Logging Guardrails ---
def log_internal(message: str, level: str = "info"):
    """Internal logging only - never shown to users."""
    if level == "error":
        logging.error(f"[INTERNAL] {message}")
    elif level == "warning":
        logging.warning(f"[INTERNAL] {message}")
    else:
        logging.info(f"[INTERNAL] {message}")

def user_progress(message: str):
    """User-facing progress messages - high-level and descriptive."""
    # Remove any internal terminology before showing
    clean_msg = message
    for term in ["agent", "node", "pipeline", "state"]:
        clean_msg = clean_msg.replace(term, "step")
    st.write(clean_msg)

# --- 5. Content Guardrails ---
def is_grounded_response(output: str, transcript: str) -> bool:
    """Check if response appears grounded in provided transcript."""
    if not transcript:
        return False
    # Simple heuristic: response should share significant text overlap
    output_words = set(output.lower().split())
    transcript_words = set(transcript.lower().split()[:500])  # Sample
    overlap = len(output_words.intersection(transcript_words))
    return overlap > 5  # At least some overlap

def scope_disclaimer() -> str:
    """Return a polite scope limitation message."""
    return (
        "I'm designed to help you explore TED Talk content. "
        "For questions outside this scope, I may not be able to provide accurate answers."
    )

# ==================== STATE DEFINITION ====================

class AgentState(TypedDict):
    """State object passed between LangGraph nodes"""
    user_query: str
    user_id: str
    # Router Outputs
    routing_decision: str  # 'recommendation_agent', 'playlist_agent', 'unknown'
    router_metadata: Dict[str, Any] # 'primary_topic', 'constraints'
    # Recommendation Agent Outputs
    intent: Dict[str, Any]
    candidates: List[Dict]
    ranked_talks: List[Dict]
    # Playlist Outputs
    playlist_plan: Dict[str, Any]
    # Final Outputs
    final_output: str
    error: Optional[str]

# ==================== 0. ROUTER AGENT ====================

def router_agent_node(state: AgentState) -> AgentState:
    """
    0. Router Agent
    Responsibility: Analyze query and route to correct downstream agent.
    """
    user_progress("Analyzing your request...")
    
    prompt = f"""
    You are a routing classifier for a TED Talks assistant.
    Analyze the user query and classify intent:
    - 'recommendation_agent': For browsing, lists, suggestions, "best talks on X".
    - 'playlist_agent': For learning paths, curriculums, "learn X in order", "beginner to advanced".
    - 'comparison_agent': For comparing multiple talks, "vs", "difference between X and Y".
    - 'qa_specific_talk': For asking a question about a SPECIFIC video/talk. User MUST mention the video/speaker.
    - 'summarize_talk': For requesting a summary, TLDR, or key takeaways of a specific video.
    - 'unknown': If intent is unclear, unsupported, or not related to TED Talks.
    
    IMPORTANT: When uncertain, prefer 'unknown' over guessing. Be conservative.
    
    User Query: "{state['user_query']}"
    
    Output JSON ONLY:
    {{
        "destination": "recommendation_agent" | "playlist_agent" | "comparison_agent" | "qa_specific_talk" | "summarize_talk" | "unknown",
        "primary_topic": "string",
        "target_talk": "string (Title or Speaker mentioned for QA/Sum, or empty)",
        "confidence": "high" | "medium" | "low",
        "constraints": ["string"]
    }}
    """
    
    try:
        response = call_cortex_llm(prompt, model="llama3.1-405b")
        log_internal(f"Router raw response: {response[:200]}")
        
        # Parse JSON
        json_str = response.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
             json_str = json_str.split("```")[1].split("```")[0].strip()
        
        data = json.loads(json_str)
        
        # === GUARDRAIL: Routing Confidence Check ===
        if not validate_routing_confidence(data):
            log_internal(f"Routing confidence check failed: {data}")
            state['routing_decision'] = 'unknown'
            state['router_metadata'] = {"reason": "low_confidence"}
        else:
            # Additional guardrail: If confidence is "low", route to unknown
            if data.get('confidence', 'high') == 'low':
                state['routing_decision'] = 'unknown'
                state['router_metadata'] = {"reason": "explicit_low_confidence"}
            else:
                state['routing_decision'] = data.get('destination', 'unknown')
                state['router_metadata'] = {
                    "topic": data.get('primary_topic'),
                    "target_talk": data.get('target_talk'),
                    "constraints": data.get('constraints', [])
                }
        
        user_progress(f"Understanding your request...")
        
    except Exception as e:
        # === GUARDRAIL: Fail safely to unknown ===
        log_internal(f"Router error: {e}", "error")
        state['routing_decision'] = 'unknown'
        state['router_metadata'] = {"error": "routing_failed"}

    return state


# ==================== BRANCH A: PLAYLIST AGENT ====================

def playlist_agent_node(state: AgentState) -> AgentState:
    """
    Branch A: Playlist Agent
    Responsibility: Transform ranked talks into a structured learning playlist.
    Ordered: Foundations -> Core -> Advanced -> Future.
    """
    candidates = state.get('candidates', [])
    if not candidates:
        state['final_output'] = "⚠️ No talks found to build a playlist. Please try a different topic."
        return state

    st.write(f"Designing a structured learning playlist from {len(candidates)} talks...")

    # Prepare Context for LLM
    # Limit to 20 candidates to fit in context window while giving good variety
    pool = candidates[:20]
    talks_context = ""
    for i, t in enumerate(pool):
        # Include URL in context so the LLM can generate the link
        url = t.get('url', t.get('talk_url', '#'))
        talks_context += f"ID {i}: '{t.get('title')}' by {t.get('speaker')} (URL: {url})\n"

    # System Prompt for Playlist generation
    prompt = f"""
    You are an expert Curriculum Designer.
    Goal: Create a "Learning Playlist" for the topic: "{state['router_metadata'].get('topic', state['user_query'])}".
    
    INPUT TALKS:
    {talks_context}
    
    INSTRUCTIONS:
    1. Select 5-7 distinct talks from the list.
    2. Group them into disjoint learning stages: "Foundations", "Core Concepts", "Advanced/Future".
    3. Order them logically (Intro -> Deep Dive).
    
    OUTPUT FORMAT (Strict Markdown):
    
    ## 📚 Learning Playlist: [Topic]
    
    ### 1️⃣ Foundations
    **Talk:** ([Title])([URL]) 
    **Why first:** [1 sentence explanation]
    
    ### 2️⃣ Core Concepts
    ...
    
    ### 3️⃣ Advanced Perspectives
    ...
    
    Constraints:
    - Use ONLY the provided talks.
    - Title AND URL must match the input list exactly.
    - Ensure the link is clickable: [Title](URL)
    """
    
    try:
        response = call_cortex_llm(prompt, model="llama3.1-405b")
        state['final_output'] = response
        st.write("Playlist generated successfully.")
        
    except Exception as e:
        st.error(f"⚠️ PLAYLIST Error: {e}")
        state['final_output'] = "Error generating playlist. Please try again."

    return state


# ==================== BRANCH B: UNKNOWN AGENT ====================

def unknown_agent_node(state: AgentState) -> AgentState:
    """
    Branch B: Unknown/Fallback
    Responsibility: Handle unclear or out-of-scope requests gracefully.
    GUARDRAIL: Never sound like an error - explain scope clearly.
    """
    # === GUARDRAIL: User-friendly progress (no internal terms) ===
    user_progress("Let me help you find what you're looking for...")
    
    # Templated, polite response guiding user to supported features
    # No mention of "agent", "system", "routing" - feels natural
    response = """
### I'd love to help! 🎯

I specialize in **TED Talk discovery and analysis**. Here are some things I can do:

**🔍 Find Talks**
> "Show me talks about artificial intelligence" or "Inspiring videos for entrepreneurs"

**📚 Create Learning Paths**
> "Create a playlist to learn about climate change" or "Beginner to advanced talks on leadership"

**⚖️ Compare Speakers**
> "Compare Simon Sinek's talk with Brené Brown's"

**❓ Answer Questions**
> "What does Ken Robinson say about creativity?" (mention the speaker or video title)

**📝 Summarize Videos**
> "Summarize 'Do schools kill creativity'"

Try one of these approaches, and I'll do my best to help!
    """
    
    state['final_output'] = response.strip()
    return state


# ==================== BRANCH C: RECOMMENDATION PIPELINE ====================

def intent_agent_node(state: AgentState) -> AgentState:
    """1. Intent Understanding Agent"""
    st.write("Identifying core topics and user intent...")
    
    # Use router metadata to seed the intent if possible
    router_topic = state.get('router_metadata', {}).get('topic', '')
    
    prompt = f"""
    Analyze user query for recommendation details.
    User Query: "{state['user_query']}"
    Context Topic: "{router_topic}"
    
    Extract: core_topic, sub_topics, intent_type (Educational/Inspirational/etc), keywords.
    Return JSON: {{ "core_topic": "", "sub_topics": [], "intent_type": "", "keywords": [] }}
    """
    
    try:
        response = call_cortex_llm(prompt, model="llama3.1-405b")
        # Robust JSON extraction
        json_str = response.strip()
        if "```json" in json_str: json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str: json_str = json_str.split("```")[1].split("```")[0].strip()
        
        # Cleanup
        if not json_str.endswith('}'):
             match = re.search(r'\{.*\}', json_str, re.DOTALL)
             if match: json_str = match.group(0)

        intent = json.loads(json_str)
        state['intent'] = intent
        st.write(f"Intent identified: {intent.get('core_topic')}")
        
    except Exception as e:
        st.error(f"⚠️ INTENT Error: {e}")
        state['intent'] = {"core_topic": state['user_query'], "keywords": [state['user_query']]}
    
    return state

def semantic_search_node(state: AgentState) -> AgentState:
    """2. Semantic Search Agent"""
    st.write("Searching database for relevant content...")
    intent = state['intent']
    keywords = intent.get('keywords', [])
    core_topic = intent.get('core_topic', state['user_query'])
    
    search_term = f"{core_topic} {' '.join(keywords)}"
    if len(search_term) < 3: search_term = state['user_query']

    try:
        # Fetch more candidates for playlists to ensure good structural variety
        limit = 40 if state.get('routing_decision') == 'playlist_agent' else 30
        df = search_talks(search_term, limit=limit)
        
        if not df.empty:
            raw_candidates = df.to_dict('records')
            # Deduplicate
            seen_ids = set()
            candidates = []
            for c in raw_candidates:
                tid = c.get('talk_id') or c.get('title') # Fallback if ID invalid
                if tid and tid not in seen_ids:
                    candidates.append(c)
                    seen_ids.add(tid)
            
            state['candidates'] = candidates
            st.write(f"Found {len(candidates)} potential candidates.")
        else:
            state['candidates'] = []
            st.warning("⚠️ SEARCH: No results found.")
    except Exception as e:
        state['candidates'] = []
        state['error'] = str(e)
    return state

def ranking_agent_node(state: AgentState) -> AgentState:
    """3. Relevance Ranking Agent"""
    if not state['candidates']: return state
    st.write(f"Evaluating top {len(state['candidates'])} candidates for quality...")
    
    top_candidates = state['candidates'][:15]
    intent_json = json.dumps(state['intent'])
    
    candidates_list = ""
    for i, t in enumerate(top_candidates):
        candidates_list += f"[{i}] {t.get('title')} by {t.get('speaker')}\n"

    prompt = f"""
    Rank top 5 candidates for Intent: {intent_json}
    Candidates:
    {candidates_list}
    Return JSON list of distinct indices: [0, 2, ...]
    """
    
    try:
        response = call_cortex_llm(prompt, model="llama3.1-405b")
        match = re.search(r'\[(.*?)\]', response)
        indices = [int(x.strip()) for x in match.group(1).split(',') if x.strip().isdigit()] if match else []
        
        seen_titles = set()
        ranked = []
        for ix in indices:
            if 0 <= ix < len(top_candidates):
                t = top_candidates[ix]
                if t.get('title') not in seen_titles:
                    ranked.append(t)
                    seen_titles.add(t.get('title'))
        
        state['ranked_talks'] = ranked if ranked else top_candidates[:5]
        st.write(f"Selected top {len(state['ranked_talks'])} talks.")
    except:
        state['ranked_talks'] = top_candidates[:5]
    return state

def reasoning_agent_node(state: AgentState) -> AgentState:
    """4. Reasoning Agent with JSON Output"""
    if not state['ranked_talks']: return state
    st.write("Generating personalized explanations...")
    
    talks_context = "\n".join([f"{i}: {t.get('title')}" for i, t in enumerate(state['ranked_talks'])])
    prompt = f"""
    Write 1-sentence personalized reason for each talk for Query: "{state['user_query']}"
    Talks:
    {talks_context}
    Return JSON mapping index to reason: {{ "0": "...", "1": "..." }}
    """
    
    try:
        response = call_cortex_llm(prompt, model="llama3.1-405b")
        json_str = response.strip()
        if "```json" in json_str: json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str: json_str = json_str.split("```")[1].split("```")[0].strip()
        
        reasons_map = json.loads(json_str)
        for i, talk in enumerate(state['ranked_talks']):
            talk['reason'] = reasons_map.get(str(i), "Recommended for you.")
            
        st.write("Reasoning complete.")
    except:
        for t in state['ranked_talks']: t['reason'] = "Great match."
    return state

def final_recommendation_node(state: AgentState) -> AgentState:
    """5. Final Recommendation Agent"""
    if not state['ranked_talks']:
        state['final_output'] = "No matches found."
        return state

    st.write("Finalizing recommendations...")
    intent = state.get('intent', {})
    topic = intent.get('core_topic', state['user_query']).title()
    
    output = f"### 🎯 Top Recommendations: {topic}\n"
    output += f"*{intent.get('intent_type', 'General')} Focus*\n\n---\n"
    
    for i, talk in enumerate(state['ranked_talks'], 1):
        url = talk.get('url', talk.get('talk_url', '#'))
        output += f"#### {i}. [{talk.get('title')}]({url})\n"
        output += f"👤 **{talk.get('speaker')}** | 📅 {talk.get('published_year')} | ⏳ {int(float(talk.get('duration_minutes',0)))} min\n"
        output += f"> 💡 *{talk.get('reason')}*\n\n"
        
    output += "---\n*Powered by TED AI Agent Network*"
    state['final_output'] = output
    return state


# ==================== BRANCH D: COMPARISON AGENT ====================

def comparison_agent_node(state: AgentState) -> AgentState:
    """
    Branch D: Comparison Agent
    Responsibility: Compare multiple talks on the same topic.
    Goal: Select 2-4 talks and compare dimensions (depth, focus, level).
    """
    candidates = state.get('candidates', [])
    if not candidates or len(candidates) < 2:
        state['final_output'] = "⚠️ Need at least 2 relevant talks to perform a comparison. Found fewer."
        return state

    st.write(f"Analyzing {len(candidates)} talks for comparison...")
    
    # 1. Pass ALL candidates (limit 10) to the LLM
    pool = candidates[:10]
    talks_context = ""
    for i, t in enumerate(pool):
        url = t.get('url', t.get('talk_url', '#'))
        talks_context += f"Talk {chr(65+i)}: '{t.get('title')}' by {t.get('speaker')}\n"
        
    topic = state['router_metadata'].get('topic', state['user_query'])

    # 2. Comparison System Prompt
    prompt = f"""
    You are an expert Content Analyst.
    Goal: Identify the relevant talks from the list below and compare them on topic: "{topic}".
    User Request: "{state['user_query']}"
    
    AVAILABLE CANDIDATES:
    {talks_context}
    
    INSTRUCTIONS:
    1. FILTER: Did the user ask to compare specific videos?
       - YES: Select ONLY those specific videos from the list. Ignore the rest.
       - NO: Select the top 3-4 most relevant talks.
    2. Suggest which talk is best for different user goals.
    3. Compare the SELECTED talks across distinct dimensions (e.g., Depth, Focus, Audience, Tone).
    
    OUTPUT FORMAT (Strict Markdown):
    
    ## 🔍 TED Talk Comparison: {topic}
    
    ### Talks Compared
    - **Talk A**: [Title](url) — Speaker
    - **Talk B**: [Title](url) — Speaker
    ...
    
    ### Comparison Breakdown
    | Dimension | Talk A | Talk B | ... |
    |-----------|--------|--------|-----|
    | **Focus** | Practical | Theoretical | ... |
    | **Level** | Beginner | Advanced | ... |
    
    ### Key Takeaways
    - Talk A is great for...
    - Talk B focuses on...
    
    ### Which Should You Watch?
    - **If you want [Goal X]** → Watch **Talk A**
    - **If you want [Goal Y]** → Watch **Talk B**
    """

    try:
        response = call_cortex_llm(prompt, model="llama3.1-405b")
        state['final_output'] = response
        st.write("Comparison analysis complete.")
        
    except Exception as e:
        st.error(f"⚠️ COMPARISON Error: {e}")
        state['final_output'] = "Error generating comparison. Please try again."

    return state
    
# ==================== BRANCH E: QA PIPELINE WRAPPER (PHASE 13) ====================

def resolve_talk_node(state: AgentState) -> AgentState:
    """
    Branch E: User asks about a specific talk.
    Step 1: Resolve the 'target_talk' string to a real Talk ID using Search.
    """
    target = state['router_metadata'].get('target_talk')
    
    if not target:
        state['final_output'] = "I understood you want to ask about a specific talk, but I couldn't identify which one. Please name the speaker or title."
        return state
        
    st.write(f"Identifying the spoken talk '{target}'...")
    
    # Reuse search logic but aim for top 1
    try:
        df = search_talks(target, limit=5)
        if not df.empty:
            best_match = df.iloc[0] # Take top result
            # DB returns lowercase columns
            talk_id = best_match.get('talk_id') or best_match.get('TALK_ID')
            title = best_match.get('title') or best_match.get('TITLE')
            
            if talk_id:
                st.write(f"Identified: '{title}'")
                
                # Store ID in state for the QA Pipeline
                state['router_metadata']['resolved_talk_id'] = talk_id
                state['router_metadata']['resolved_talk_title'] = title
                
                # Fetch Transcript here for Summarization Agent (and QA) to use
                # This fulfills the requirement: state.metadata["transcript"]
                from db import get_transcript
                transcript = get_transcript(talk_id)
                if transcript:
                    state['router_metadata']['transcript'] = transcript
                else:
                    state['error'] = "Transcript not found"
            else:
                 state['final_output'] = "Found talk but ID was missing."
        else:
             state['final_output'] = f"I couldn't find any talk matching '{target}'. Try checking the spelling or title."
             state['error'] = "Talk not found"
    except Exception as e:
        state['final_output'] = "Error searching for talk."
        state['error'] = str(e)
        
    return state

# ==================== VIDEO SUMMARIZATION AGENT (PHASE 14) ====================

def video_summarization_agent_node(state: AgentState) -> AgentState:
    """
    Video Summarization Agent
    Generates a grounded summary strictly from the transcript.
    GUARDRAIL: Use ONLY transcript content, no external knowledge.
    """
    # === GUARDRAIL: User-friendly progress ===
    user_progress("Reading the video transcript...")
    
    transcript = state['router_metadata'].get('transcript')
    title = state['router_metadata'].get('resolved_talk_title', 'Selected Video')
    
    if not transcript:
        state['final_output'] = "❌ Error: Could not retrieve transcript for summarization."
        return state

    # User query might ask for specific style
    user_query = state['user_query']
    
    # Limit transcript to ~100k chars (approx 25k tokens) to fit in context safely
    # TED talks are rarely this long, but good for safety.
    MAX_CHARS = 100000
    
    transcript_text = transcript[:MAX_CHARS]
    if len(transcript) > MAX_CHARS:
        transcript_text += "\n[...TRANSCRIPT TRUNCATED DUE TO LENGTH...]"
    
    prompt = f"""
    You are an expert Video Summarization Agent.
    Your task is to generate a summary of the video titled "{title}" STRICTLY based on the provided transcript.
    
    Context:
    - User Query: "{user_query}"
    - Video Title: "{title}"
    
    Transcript:
    \"\"\"{transcript_text}\"\"\"
    
    Instructions:
    1. Analyze the user's request to determine the desired style (Short, Detailed, or Key Takeaways).
       - If not specified, default to a balanced summary + key takeaways.
    2. Write the summary using ONLY facts from the transcript. Do not use external knowledge.
    3. Output strictly in Markdown format as follows:

    ## 🎥 Video Summary: {title}
    <3-5 sentence overview>

    ## 🧠 Key Takeaways
    - <Point 1>
    - <Point 2>
    - <Point 3>
    
    (Optional: Add ## Detailed Notes if requested)

    Constraint: Do NOT hallucinate. match the tone of the speaker.
    """
    
    try:
        summary = call_cortex_llm(prompt, model="llama3.1-405b")
        state['final_output'] = summary
        st.write("Summary generated.")
    except Exception as e:
        state['final_output'] = f"Error generating summary: {e}"
        st.error(f"Summarization failed: {e}")
        
    return state

# ==================== BUILD GRAPH (UPDATED) ====================


def qa_pipeline_node(state: AgentState) -> AgentState:
    """
    Branch E: Execute QA Graph
    Step 2: Run the QA Subgraph with the resolved ID.
    """
    talk_id = state['router_metadata'].get('resolved_talk_id')
    if not talk_id:
        if not state.get('final_output'):
             state['final_output'] = "Could not resolve talk to answer questions."
        return state

    st.write("Consulting the Knowledge Base...")
    
    # Fetch Transcript (Ideally this would be inside the subgraph, but we pass it for now)
    from db import get_transcript
    
    transcript = get_transcript(talk_id)
    if not transcript:
         state['final_output'] = "Sorry, I found the talk but the transcript is missing/unavailable."
         return state
         
    # Run the separate QA Graph
    answer = run_qa_pipeline(state['user_query'], talk_id, transcript)
    
    # Format the output with context
    title = state['router_metadata'].get('resolved_talk_title', 'this talk')
    state['final_output'] = f"### 💬 Answer for: *{title}*\n\n{answer}"
    
    return state


# ==================== GRAPH BUILDER ====================

def router_node_decision(state: AgentState) -> Literal["intent", "unknown"]:
    """Entry Router Decision"""
    decision = state.get('routing_decision', 'unknown')
    # All active agents (Rec, Playlist, Comparison) need search
    if decision in ['recommendation_agent', 'playlist_agent', 'comparison_agent']:
        return "intent"
    else:
        return "unknown"

def post_search_decision(state: AgentState) -> Literal["rank", "playlist", "comparison"]:
    """Decision after retrieval"""
    decision = state.get('routing_decision', 'recommendation_agent')
    if decision == 'playlist_agent':
        return "playlist"
    elif decision == 'comparison_agent':
        return "comparison"
    else:
        return "rank"

def resolve_router_decision(state: AgentState) -> Literal["qa_pipeline", "summarization", "end"]:
    """
    Decides where to go after talk resolution: QA or Summarization
    """
    if not state['router_metadata'].get('resolved_talk_id'):
        return "end" # Resolution failed
        
    intent = state.get('routing_decision')
    if intent == 'qa_specific_talk':
        return "qa_pipeline"
    elif intent == 'summarize_talk':
        return "summarization"
    else:
        return "end"

def build_graph():
    try:
        from langgraph.graph import StateGraph, END
    except ImportError: return None

    workflow = StateGraph(AgentState)
    
    # 0. Router
    workflow.add_node("router", router_agent_node)
    
    # Branch A: Playlist
    workflow.add_node("playlist", playlist_agent_node)
    
    # Branch B: Unknown
    workflow.add_node("unknown", unknown_agent_node)
    
    # Branch D: Comparison
    workflow.add_node("comparison", comparison_agent_node)
    
    # Branch E: QA & Summarization Pipeline (Phase 13/14)
    workflow.add_node("resolve_talk", resolve_talk_node)
    workflow.add_node("qa_pipeline", qa_pipeline_node)
    workflow.add_node("summarization", video_summarization_agent_node)
    
    # Branch C: Recommendation Pipeline
    workflow.add_node("intent", intent_agent_node)
    workflow.add_node("search", semantic_search_node)
    workflow.add_node("rank", ranking_agent_node)
    workflow.add_node("reason", reasoning_agent_node)
    workflow.add_node("final", final_recommendation_node)
    
    # Edges
    workflow.set_entry_point("router")
    
    # 1. Router -> (Intent, Unknown, or QA Resolver)
    def router_edge_logic(state):
        d = state.get('routing_decision', 'unknown')
        if d in ['qa_specific_talk', 'summarize_talk']: return "resolve_talk"
        if d in ['recommendation_agent', 'playlist_agent', 'comparison_agent']: return "intent"
        return "unknown"

    workflow.add_conditional_edges(
        "router",
        router_edge_logic,
        {
            "intent": "intent",
            "resolve_talk": "resolve_talk",
            "unknown": "unknown"
        }
    )
    
    # 2. Intent -> Search
    workflow.add_edge("intent", "search")
    
    # 3. Search -> (Rank, Playlist, or Comparison)
    workflow.add_conditional_edges(
        "search",
        post_search_decision,
        {
            "rank": "rank",
            "playlist": "playlist",
            "comparison": "comparison"
        }
    )
    
    # 4. Resolver Branch Edges (QA vs Summarization)
    workflow.add_conditional_edges(
        "resolve_talk",
        resolve_router_decision,
        {
            "qa_pipeline": "qa_pipeline",
            "summarization": "summarization",
            "end": END
        }
    )
    workflow.add_edge("qa_pipeline", END)
    workflow.add_edge("summarization", END)
    
    # 5. Finish Rec Pipeline
    workflow.add_edge("rank", "reason")
    workflow.add_edge("reason", "final")
    workflow.add_edge("final", END)
    
    # Finish Branches
    workflow.add_edge("playlist", END)
    workflow.add_edge("unknown", END)
    workflow.add_edge("comparison", END)
    
    return workflow.compile()

def run_agent_pipeline(user_query: str, user_id: str) -> Dict[str, Any]:
    """
    Execute Pipeline with Guardrails
    Input validation -> Agent execution -> Output sanitization
    """
    # === GUARDRAIL: Input Validation ===
    is_valid, validated_query = validate_input(user_query)
    if not is_valid:
        return {
            "success": True,  # Not an error, just scope limitation
            "output": validated_query,  # Contains the user-friendly message
            "agent_type": "input_guard"
        }
    
    # Sanitize input
    clean_query = sanitize_input(validated_query)
    
    app = build_graph()
    if not app:
        log_internal("LangGraph compilation failed", "error")
        return {"success": False, "output": "Service temporarily unavailable. Please try again.", "agent_type": "error"}
    
    initial_state = AgentState(
        user_query=clean_query, user_id=user_id,
        routing_decision="", router_metadata={},
        intent={}, candidates=[], ranked_talks=[],
        playlist_plan={}, final_output="", error=None
    )
    
    try:
        final = app.invoke(initial_state)
        # === GUARDRAIL: Ensure state is safe ===
        final = ensure_safe_state(final)
        
        # === GUARDRAIL: Output Sanitization ===
        sanitized_output = sanitize_output(final['final_output'], add_disclaimer=True)
        
        return {"success": True, "output": sanitized_output, "agent_type": final.get('routing_decision', 'unknown')}
        
    except Exception as e:
        # === GUARDRAIL: Graceful Error Handling ===
        log_internal(f"Pipeline execution error: {e}", "error")
        return {
            "success": False,
            "output": format_error_gracefully(e, "agent pipeline"),
            "agent_type": "error"
        }

# ==================== QA RETRIEVAL PIPELINE (PHASE 13) ====================

class QAState(TypedDict):
    """
    Dedicated State for QA Pipeline
    Simple Linear Flow: Start -> Retrieval -> GroundedAnswer -> End
    """
    user_query: str
    talk_id: str
    transcript: str
    retrieved_quotes: List[str]
    final_answer: str
    error: Optional[str]

def retrieval_agent_node(state: QAState) -> QAState:
    """
    Agent 1: Transcript Retrieval Agent
    Purpose: Select only the transcript segments relevant to the question.
    """
    st.write("Scanning transcript for relevant evidence...")
    query = state['user_query']
    transcript = state['transcript']
    
    # System Prompt with strict constraints
    prompt = f"""
    You are a Transcript Retrieval Agent.
    Input: User Question and Full Transcript.
    Goal: Select 3-5 short excerpts from the transcript that contain the answer.
    
    User Question: "{query}"
    
    Transcript:
    \"\"\"{transcript[:50000]}\"\"\" (Truncated to fit context if needed)
    
    Constraints:
    - Output JSON list of strings ONLY: ["quote1", "quote2", ...]
    - NO paraphrasing. Exact text only.
    - If no relevant text found, return empty list: []
    """
    
    try:
        response = call_cortex_llm(prompt, model="llama3.1-405b")
        
        # Robust Regex Extraction for [...]
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            json_str = match.group(0)
            quotes = json.loads(json_str)
            if isinstance(quotes, list):
                state['retrieved_quotes'] = quotes
                st.write(f"Found {len(quotes)} relevant excerpts.")
            else:
                state['retrieved_quotes'] = []
        else:
            st.warning("⚠️ RETRIEVAL: No JSON list found in response")
            state['retrieved_quotes'] = []
            
    except Exception as e:
        st.warning(f"⚠️ RETRIEVAL Warning: {e}")
        # Log response for debug only if needed, or keep succinct
        state['retrieved_quotes'] = []
        
    return state

def grounded_answer_agent_node(state: QAState) -> QAState:
    """
    Agent 2: Grounded Answer Agent
    Purpose: Answer using ONLY the retrieved quotes.
    """
    st.write("Synthesizing grounded answer...")
    quotes = state.get('retrieved_quotes', [])
    
    if not quotes:
        state['final_answer'] = "❌ This information is not mentioned in the talk."
        return state
        
    quotes_text = "\n".join([f"- \"{q}\"" for q in quotes])
    
    prompt = f"""
    You are a Grounded Answer Agent.
    Goal: Answer the user question using ONLY the provided transcript excerpts.
    
    User Question: "{state['user_query']}"
    
    Relevant Excerpts:
    {quotes_text}
    
    Constraints:
    - You must answer using only the provided transcript excerpts.
    - If the answer cannot be found verbatim or clearly inferred from them, respond:
      "This information is not mentioned in the talk."
    - Output Format:
      ## Answer
      <short answer>

      ## Evidence from Transcript
      - "<exact quote>"
      - "<exact quote>"
    """
    
    try:
        response = call_cortex_llm(prompt, model="llama3.1-405b")
        state['final_answer'] = response
        st.success("✅ GROUNDING: Answer generated")
    except Exception as e:
        state['final_answer'] = "Error generating grounded answer."
        
    return state

def build_qa_graph():
    """Build the Simple & Safe QA Graph"""
    try:
        from langgraph.graph import StateGraph, END
    except ImportError: return None

    workflow = StateGraph(QAState)
    
    workflow.add_node("retrieval", retrieval_agent_node)
    workflow.add_node("grounded_answer", grounded_answer_agent_node)
    
    workflow.set_entry_point("retrieval")
    workflow.add_edge("retrieval", "grounded_answer")
    workflow.add_edge("grounded_answer", END)
    
    return workflow.compile()

def run_qa_pipeline(user_query: str, talk_id: str, transcript: str) -> str:
    """Execute QA Pipeline"""
    app = build_qa_graph()
    if not app: return "LangGraph missing."
    
    initial_state = QAState(
        user_query=user_query,
        talk_id=talk_id,
        transcript=transcript,
        retrieved_quotes=[],
        final_answer="",
        error=None
    )
    
    try:
        final = app.invoke(initial_state)
        return final.get('final_answer', "No answer generated.")
    except Exception as e:
        return f"QA Pipeline Error: {e}"
