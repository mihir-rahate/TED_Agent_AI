"""MultiAgentManager - orchestrator that routes tasks to registered agents.
This is a LangGraph-like orchestrator that manages the learning experience workflow.
"""
from typing import Dict, Any, Callable
from .agents import QuizAgent, RoadmapAgent
from .learner_profile import LearnerProfileAgent


class MultiAgentManager:
    def __init__(self, llm_client=None):
        # instantiate default agents (llm_client can be injected for testing)
        self.quiz_agent = QuizAgent(llm_client=llm_client)
        self.roadmap_agent = RoadmapAgent(llm_client=llm_client)
        self.profile_agent = LearnerProfileAgent(llm_client=llm_client)
        self.registry = {
            "quiz": self.quiz_agent,
            "roadmap": self.roadmap_agent,
            "profile": self.profile_agent
        }

    # Quiz-related APIs
    def generate_quiz(self, user_id: str, video_slug: str, num_questions: int = 5) -> Dict[str, Any]:
        return self.quiz_agent.generate_quiz(user_id=user_id, video_slug=video_slug, num_questions=num_questions)

    def evaluate_quiz(self, user_id: str, video_slug: str, answers: Dict[str, int]) -> Dict[str, Any]:
        """Evaluate quiz and update learner profile with remedial suggestions."""
        result = self.quiz_agent.evaluate_quiz(user_id=user_id, video_slug=video_slug, answers=answers)
        
        # If there are topics that need improvement, suggest next steps
        if result.get("remedial_suggestions"):
            next_videos = []
            for topic, videos in result["remedial_suggestions"].items():
                next_videos.extend(videos)
            result["next_steps"] = {
                "message": "Based on your quiz performance, we recommend watching these videos:",
                "suggested_videos": next_videos[:2]  # Limit to top 2 suggestions
            }
        return result

    # Roadmap API
    def generate_roadmap(self, user_id: str, topic: str, depth: int = 6) -> Dict[str, Any]:
        """Generate a personalized learning roadmap."""
        return self.roadmap_agent.generate_roadmap(user_id=user_id, topic=topic, depth=depth)

    # Profile API
    def get_learner_profile(self, user_id: str) -> Dict[str, Any]:
        """Get the current state of the learner's knowledge profile."""
        return self.profile_agent.get_profile(user_id)

    def get_topic_status(self, user_id: str, topic: str) -> Dict[str, Any]:
        """Get detailed status of a learner's progress in a specific topic."""
        profile = self.profile_agent.get_profile(user_id)
        mastery = profile["topic_mastery"].get(topic, {
            "correct": 0,
            "total": 0,
            "mastery_level": 0.0
        })
        
        # Get recent quiz history for this topic
        relevant_quizzes = [
            quiz for quiz in profile["quiz_history"]
            if topic in quiz["topics"]
        ][-5:]  # Last 5 quizzes
        
        return {
            "topic": topic,
            "mastery_level": mastery["mastery_level"],
            "total_questions": mastery["total"],
            "correct_answers": mastery["correct"],
            "recent_quizzes": relevant_quizzes,
            "completed_videos": [
                video for video in profile["completed_videos"]
                if topic.lower() in video.lower()
            ]
        }
