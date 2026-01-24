"""
Agent B: Learner Profile Agent

Purpose: Build and continuously update the student model.

Inputs:
- Assessment results from Agent A
- Learning behavior signals (time spent, retries, confusion indicators)

Outputs:
- Updated learner profile
- Learning style recommendations
- Topic mastery updates
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from db.supabase_client import supabase_manager
from models.schemas import (
    AssessmentResult,
    LearnerProfile,
    LearningStyle,
    MasteryLevel,
    TopicKnowledge,
)


class LearnerProfileAgent(BaseAgent):
    """
    Agent B: Maintains and updates the student's learning profile.
    
    Responsibilities:
    - Initialize new learner profiles
    - Update topic mastery based on assessments
    - Infer learning style preferences
    - Track historical mistakes and patterns
    - Identify weak and strong topics
    - Update study time and engagement metrics
    """

    def __init__(self, temperature: float = 0.1):
        super().__init__(temperature=temperature)

    def _build_system_prompt(self) -> str:
        return """You are the Learner Profile Agent, an educational psychologist AI specializing in personalized learning for Class 10 students.

Your role is to:
1. Analyze student performance patterns to understand their learning profile
2. Identify optimal learning styles based on performance data
3. Track progress and adapt recommendations
4. Provide insights about student strengths and weaknesses

You base your analysis on concrete performance data and educational psychology principles."""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method. Dispatches based on action.
        
        Actions:
        - 'get_profile': Retrieve current profile
        - 'update_from_assessment': Update profile based on assessment result
        - 'infer_learning_style': Analyze and suggest learning style
        - 'get_recommendations': Get personalized recommendations
        - 'update_study_time': Update study time metrics
        """
        action = input_data.get("action")
        
        if action == "get_profile":
            return await self.get_profile(
                student_id=input_data["student_id"],
            )
        elif action == "update_from_assessment":
            return await self.update_from_assessment(
                student_id=input_data["student_id"],
                assessment_result=input_data["assessment_result"],
            )
        elif action == "infer_learning_style":
            return await self.infer_learning_style(
                student_id=input_data["student_id"],
                behavior_signals=input_data.get("behavior_signals", {}),
            )
        elif action == "get_recommendations":
            return await self.get_recommendations(
                student_id=input_data["student_id"],
            )
        elif action == "update_study_time":
            return await self.update_study_time(
                student_id=input_data["student_id"],
                minutes=input_data["minutes"],
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    async def get_profile(self, student_id: str) -> Dict[str, Any]:
        """
        Get the current learner profile.
        
        Args:
            student_id: The student's ID
            
        Returns:
            LearnerProfile as dictionary, or None if not found
        """
        profile = await supabase_manager.get_learner_profile(student_id)
        
        if profile is None:
            return {"error": "Profile not found", "student_id": student_id}
        
        return profile.model_dump()

    async def update_from_assessment(
        self,
        student_id: str,
        assessment_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update the learner profile based on an assessment result.
        
        Args:
            student_id: The student's ID
            assessment_result: AssessmentResult as dictionary
            
        Returns:
            Updated profile data
        """
        # Get current profile
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Profile not found"}
        
        # Parse assessment result
        result = AssessmentResult(**assessment_result)
        topic_key = f"{result.subject_code}:{result.topic_code}"
        
        # Update topic knowledge
        existing_tk = profile.topic_knowledge.get(topic_key)
        
        if existing_tk:
            # Update existing knowledge
            new_attempts = existing_tk.questions_attempted + result.questions_attempted
            new_correct = existing_tk.questions_correct + result.questions_correct
            
            # Weighted average of scores (more recent = higher weight)
            old_weight = 0.3
            new_weight = 0.7
            new_score = int(existing_tk.score * old_weight + result.score * new_weight)
            
            existing_tk.score = new_score
            existing_tk.questions_attempted = new_attempts
            existing_tk.questions_correct = new_correct
            existing_tk.mastery_level = result.level
            existing_tk.misconceptions.extend(result.misconceptions)
            existing_tk.last_assessed = datetime.now()
        else:
            # Create new topic knowledge
            profile.topic_knowledge[topic_key] = TopicKnowledge(
                topic_id=result.topic_code,
                topic_code=result.topic_code,
                topic_name=result.topic_name or result.topic_code,
                subject_id=result.subject_id or "",
                subject_code=result.subject_code,
                mastery_level=result.level,
                score=result.score,
                questions_attempted=result.questions_attempted,
                questions_correct=result.questions_correct,
                misconceptions=result.misconceptions,
                last_assessed=datetime.now(),
            )
        
        # Update weak/strong topics
        if result.level in [MasteryLevel.WEAK, MasteryLevel.DEVELOPING]:
            if topic_key not in profile.weak_topics:
                profile.weak_topics.append(topic_key)
            if topic_key in profile.strong_topics:
                profile.strong_topics.remove(topic_key)
        elif result.level in [MasteryLevel.PROFICIENT, MasteryLevel.MASTERED]:
            if topic_key not in profile.strong_topics:
                profile.strong_topics.append(topic_key)
            if topic_key in profile.weak_topics:
                profile.weak_topics.remove(topic_key)
        
        # Track historical mistakes
        for misconception in result.misconceptions:
            if misconception and misconception not in profile.historical_mistakes:
                profile.historical_mistakes.append(misconception)
        
        # Keep only last 50 mistakes
        profile.historical_mistakes = profile.historical_mistakes[-50:]
        
        # Update profile in database
        profile.updated_at = datetime.now()
        await supabase_manager.update_learner_profile(student_id, profile)
        
        return {
            "success": True,
            "topic_key": topic_key,
            "new_score": profile.topic_knowledge[topic_key].score,
            "new_level": profile.topic_knowledge[topic_key].mastery_level.value,
            "weak_topics_count": len(profile.weak_topics),
            "strong_topics_count": len(profile.strong_topics),
        }

    async def infer_learning_style(
        self,
        student_id: str,
        behavior_signals: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Analyze performance and behavior to infer optimal learning style.
        
        Args:
            student_id: The student's ID
            behavior_signals: Optional behavior data (time patterns, interaction types)
            
        Returns:
            Learning style analysis and recommendation
        """
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Profile not found"}
        
        # Get assessment history for all subjects
        assessment_history = await supabase_manager.get_assessment_history(
            student_id, limit=20
        )
        
        if len(assessment_history) < 3:
            return {
                "current_style": profile.learning_style.value,
                "recommendation": profile.learning_style.value,
                "confidence": 0.3,
                "reason": "Not enough data yet. Need at least 3 assessments.",
                "preferred_analogies": profile.preferred_analogies,
            }
        
        # Prepare data for LLM analysis
        performance_summary = self._summarize_performance(assessment_history)
        
        prompt = self._format_prompt(
            task=f"""Analyze this Class 10 student's learning patterns to recommend the best learning style.

## Current Profile
- Current learning style: {profile.learning_style.value}
- Preferred analogies: {profile.preferred_analogies}
- Study time: {profile.total_study_time_minutes} minutes total
- Weak topics: {profile.weak_topics[:5]}
- Strong topics: {profile.strong_topics[:5]}

## Performance Summary
{performance_summary}

## Behavior Signals
{behavior_signals or 'No behavior data available'}

## Available Learning Styles
1. visual: Learns best through diagrams, charts, visualizations
2. auditory: Learns best through verbal explanations, discussions
3. kinesthetic: Learns best through hands-on activities
4. visual+analogy: Combines visual learning with real-world analogies (recommended for VR)
5. formula-first: Prefers to learn formulas first, then applications
6. intuition-first: Prefers intuitive understanding before formulas

## Instructions
1. Analyze the student's performance patterns
2. Consider which topics they struggle/excel in
3. Recommend the optimal learning style
4. Suggest 3 analogy categories that would help this student""",
            output_format="""{
  "recommended_style": "visual+analogy",
  "confidence": 0.75,
  "reason": "Student performs better on visual conceptual questions...",
  "suggested_analogies": ["sports", "gaming", "cooking"],
  "teaching_tips": ["Start with real-world examples", "Use interactive simulations"]
}"""
        )

        result = await self._invoke_llm_json(prompt)
        
        # Update profile if confidence is high
        if result.get("confidence", 0) > 0.6:
            try:
                new_style = LearningStyle(result.get("recommended_style", profile.learning_style.value))
                await supabase_manager.update_learning_style(student_id, new_style)
                result["profile_updated"] = True
            except ValueError:
                result["profile_updated"] = False
        
        return result

    def _summarize_performance(self, assessments: List[AssessmentResult]) -> str:
        """Summarize assessment performance for LLM analysis."""
        if not assessments:
            return "No assessments available"
        
        lines = []
        by_subject = {}
        
        for a in assessments:
            subject = a.subject_code
            if subject not in by_subject:
                by_subject[subject] = {"scores": [], "levels": [], "misconceptions": []}
            by_subject[subject]["scores"].append(a.score)
            by_subject[subject]["levels"].append(a.level.value)
            by_subject[subject]["misconceptions"].extend(a.misconceptions[:2])
        
        for subject, data in by_subject.items():
            avg_score = sum(data["scores"]) / len(data["scores"])
            lines.append(f"**{subject.upper()}**: Avg score {avg_score:.1f}%, " +
                        f"Levels: {', '.join(set(data['levels']))}, " +
                        f"Recent misconceptions: {data['misconceptions'][:3]}")
        
        return "\n".join(lines)

    async def get_recommendations(self, student_id: str) -> Dict[str, Any]:
        """
        Get personalized learning recommendations for a student.
        
        Args:
            student_id: The student's ID
            
        Returns:
            Personalized recommendations
        """
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Profile not found"}
        
        # Get recent assessments
        recent_assessments = await supabase_manager.get_assessment_history(
            student_id, limit=10
        )
        
        # Prepare context
        weak_topics_str = ", ".join(profile.weak_topics[:5]) or "None identified yet"
        strong_topics_str = ", ".join(profile.strong_topics[:5]) or "None identified yet"
        recent_mistakes_str = ", ".join(profile.historical_mistakes[-5:]) or "None recorded"
        
        prompt = self._format_prompt(
            task=f"""Generate personalized learning recommendations for this Class 10 student.

## Student Profile
- Learning style: {profile.learning_style.value}
- Preferred analogies: {profile.preferred_analogies}
- Total study time: {profile.total_study_time_minutes} minutes
- Weak topics: {weak_topics_str}
- Strong topics: {strong_topics_str}
- Recent misconceptions: {recent_mistakes_str}
- Topics covered: {len(profile.topic_knowledge)}

## Instructions
1. Identify the most critical topics to work on
2. Suggest specific learning activities
3. Recommend VR scenarios that would help
4. Provide study schedule suggestions
5. Suggest analogies for weak topics""",
            output_format="""{
  "priority_topics": ["topic1", "topic2"],
  "learning_activities": [
    {"activity": "Watch VR simulation of projectile motion", "topic": "physics:projectile_motion", "duration_minutes": 15}
  ],
  "vr_scenarios": ["cricket_ground", "basketball_court"],
  "study_schedule": {
    "daily_goal_minutes": 30,
    "recommended_session_length": 20,
    "suggested_order": ["review weak topics first", "then practice problems"]
  },
  "analogies_for_weak_topics": {
    "physics:projectile_motion": "Think of throwing a cricket ball - the angle determines range"
  },
  "motivation_message": "..."
}"""
        )

        result = await self._invoke_llm_json(prompt)
        return result

    async def update_study_time(
        self,
        student_id: str,
        minutes: int,
    ) -> Dict[str, Any]:
        """
        Update the student's total study time.
        
        Args:
            student_id: The student's ID
            minutes: Minutes to add
            
        Returns:
            Update confirmation
        """
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Profile not found"}
        
        profile.total_study_time_minutes += minutes
        profile.updated_at = datetime.now()
        
        await supabase_manager.update_learner_profile(student_id, profile)
        
        return {
            "success": True,
            "added_minutes": minutes,
            "total_study_time": profile.total_study_time_minutes,
        }
