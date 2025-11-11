"""LearnerProfile agent for managing user knowledge state and progression."""
from typing import Dict, Any, List
from .. import agent as core_agent
import json
import time

class LearnerProfileAgent:
    """Agent responsible for maintaining and updating learner knowledge profiles."""
    
    def __init__(self, llm_client=None):
        self.llm = llm_client or core_agent
        
    def get_profile(self, user_id: str) -> Dict[str, Any]:
        """Retrieve learner profile from storage."""
        try:
            profile = core_agent.get_learner_profile(user_id)
            return profile
        except Exception:
            # Initialize new profile if none exists
            return {
                "user_id": user_id,
                "knowledge_graph": {},
                "completed_videos": [],
                "quiz_history": [],
                "topic_mastery": {},
                "created_at": int(time.time()),
                "updated_at": int(time.time())
            }
    
    def update_profile(self, user_id: str, quiz_result: Dict[str, Any]) -> Dict[str, Any]:
        """Update learner profile based on quiz results."""
        profile = self.get_profile(user_id)
        video_slug = quiz_result["video_slug"]
        
        # Update topic mastery based on quiz performance
        for question in quiz_result["questions"]:
            topic = question["topic"]
            is_correct = question["user_answer"] == question["correct_answer"]
            
            if topic not in profile["topic_mastery"]:
                profile["topic_mastery"][topic] = {
                    "correct": 0,
                    "total": 0,
                    "mastery_level": 0.0
                }
            
            profile["topic_mastery"][topic]["total"] += 1
            if is_correct:
                profile["topic_mastery"][topic]["correct"] += 1
            
            # Update mastery level (0.0 to 1.0)
            correct = profile["topic_mastery"][topic]["correct"]
            total = profile["topic_mastery"][topic]["total"]
            profile["topic_mastery"][topic]["mastery_level"] = correct / total
        
        # Add to quiz history
        profile["quiz_history"].append({
            "video_slug": video_slug,
            "timestamp": int(time.time()),
            "score": quiz_result["score"],
            "topics": list(set(q["topic"] for q in quiz_result["questions"]))
        })
        
        # Add to completed videos if score meets threshold
        if quiz_result["score"] >= 0.8:  # 80% threshold for completion
            if video_slug not in profile["completed_videos"]:
                profile["completed_videos"].append(video_slug)
        
        profile["updated_at"] = int(time.time())
        
        # Persist updated profile
        core_agent.save_learner_profile(user_id, profile)
        return profile
    
    def get_topic_suggestions(self, user_id: str, topic: str) -> List[str]:
        """Get personalized video suggestions for topics needing improvement."""
        profile = self.get_profile(user_id)
        topic_mastery = profile["topic_mastery"].get(topic, {"mastery_level": 0.0})
        
        if topic_mastery["mastery_level"] < 0.7:  # Below 70% mastery
            # Search for remedial content
            search_results = core_agent.search_talks_agent(
                f"beginner {topic} fundamental concepts"
            )
            return [r["slug"] for r in search_results.get("results", [])][:2]
        return []