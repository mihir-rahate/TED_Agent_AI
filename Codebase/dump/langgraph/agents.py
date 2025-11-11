"""Light-weight agent implementations for roadmap and quiz flows.
These are designed to be orchestrated by MultiAgentManager.
This module uses existing helpers in `fastapi.agent` (S3, Pinecone, OpenAI wrappers).
"""
from typing import List, Dict, Any
import json
import time
from .. import agent as core_agent
from .learner_profile import LearnerProfileAgent


class QuizAgent:
    """Agent responsible for quiz generation and evaluation."""

    def __init__(self, llm_client=None):
        self.llm = llm_client or core_agent
        self.profile_agent = LearnerProfileAgent(llm_client)

    def generate_quiz(self, user_id: str, video_slug: str, num_questions: int = 5) -> Dict[str, Any]:
        """Generate quiz for a video using the core agent helper."""
        quiz = core_agent.generate_quiz_for_slug(video_slug, user_id, num_questions)
        return quiz

    def evaluate_quiz(self, user_id: str, video_slug: str, answers: Dict[str, int]) -> Dict[str, Any]:
        """Evaluate quiz and provide personalized feedback with remedial content suggestions."""
        # Get base evaluation
        result = core_agent.evaluate_quiz_submission(user_id, video_slug, answers)
        
        # Update learner profile
        self.profile_agent.update_profile(user_id, result)
        
        # Add remedial suggestions for missed topics
        suggestions = {}
        for question in result["questions"]:
            if question["user_answer"] != question["correct_answer"]:
                topic = question["topic"]
                if topic not in suggestions:
                    suggested_videos = self.profile_agent.get_topic_suggestions(user_id, topic)
                    if suggested_videos:
                        suggestions[topic] = suggested_videos
        
        result["remedial_suggestions"] = suggestions
        return result


class RoadmapAgent:
    """Agent that builds personalized learning roadmaps using LLM + retrieval."""

    def __init__(self, llm_client=None):
        self.llm = llm_client or core_agent
        self.profile_agent = LearnerProfileAgent(llm_client)

    def generate_roadmap(self, user_id: str, topic: str, depth: int = 6) -> Dict[str, Any]:
        """Return a personalized roadmap considering learner's profile."""
        # Get learner profile
        profile = self.profile_agent.get_profile(user_id)
        
        # 1) Generate base roadmap steps
        prompt = (
            f"Create a concise {depth}-step learning roadmap for '{topic}'.\n"
            "Each step should be a 5-12 word learning objective.\n"
            f"Current knowledge state: {json.dumps(profile['topic_mastery'])}\n"
            "Return as JSON: {\"steps\": [\"step1\", ...]}"
        )

        raw = core_agent.query_openai(prompt)
        try:
            parsed = json.loads(raw)
            steps = parsed.get("steps") or parsed.get("roadmap") or []
        except Exception:
            steps = [s.strip() for s in raw.splitlines() if s.strip()] or [topic]

        # 2) For each step, find matching talks considering profile
        enriched = []
        for step in steps[:depth]:
            try:
                # Adjust search based on mastery level
                related_topics = [t for t, v in profile["topic_mastery"].items() 
                                if any(t.lower() in step.lower() for t in t.split())]
                
                difficulty = "beginner"
                if related_topics:
                    avg_mastery = sum(profile["topic_mastery"][t]["mastery_level"] 
                                    for t in related_topics) / len(related_topics)
                    difficulty = "advanced" if avg_mastery > 0.8 else \
                               "intermediate" if avg_mastery > 0.4 else "beginner"
                
                search_res = core_agent.search_talks_agent(f"{difficulty} {step}")
                candidates = [
                    video for video in search_res.get("results", [])[:3]
                    if video["slug"] not in profile["completed_videos"]
                ][:2]
            except Exception:
                candidates = []
            
            enriched.append({
                "step": step,
                "suggested_videos": candidates,
                "difficulty": difficulty
            })

        return {
            "user_id": user_id,
            "topic": topic,
            "roadmap": enriched,
            "generated_at": int(time.time())
        }
