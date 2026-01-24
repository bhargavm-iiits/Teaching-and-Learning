"""
Supabase client for the AI-Driven Personalized VR Teaching System.
Handles all database operations for users, profiles, assessments, and progress.
EXTENSIBLE DESIGN: Uses subject_code strings instead of hardcoded Subject enum.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from supabase import create_client, Client

from config import config
from models.schemas import (
    MasteryLevel,
    LearnerProfile,
    TopicKnowledge,
    AssessmentResult,
    LearningStyle,
    ClassInfo,
    SubjectInfo,
)


class SupabaseManager:
    """
    Manages all Supabase database operations.
    
    Tables:
    - classes: Class/grade levels
    - subjects: Subjects per class
    - users: Basic user information
    - learner_profiles: Learning preferences and topic mastery
    - assessments: Assessment history and results
    - topic_progress: Per-topic mastery tracking
    - misconceptions: Tracked misconceptions per student
    """

    def __init__(self):
        self._client: Optional[Client] = None

    @property
    def client(self) -> Client:
        """Lazy initialization of Supabase client."""
        if self._client is None:
            if not config.SUPABASE_URL or not config.SUPABASE_KEY:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_KEY must be set in environment variables"
                )
            self._client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        return self._client

    # ========================= CLASS & SUBJECT OPERATIONS =========================

    async def get_classes(self, active_only: bool = True) -> List[ClassInfo]:
        """Get all available classes."""
        query = self.client.table("classes").select("*").order("class_number")
        if active_only:
            query = query.eq("is_active", True)
        response = query.execute()
        
        return [
            ClassInfo(
                id=row["id"],
                class_name=row["class_name"],
                class_number=row["class_number"],
                description=row.get("description"),
                is_active=row.get("is_active", True),
            )
            for row in response.data
        ]

    async def get_subjects_for_class(
        self, class_id: str, active_only: bool = True
    ) -> List[SubjectInfo]:
        """Get all subjects for a specific class."""
        query = (
            self.client.table("subjects")
            .select("*")
            .eq("class_id", class_id)
        )
        if active_only:
            query = query.eq("is_active", True)
        response = query.execute()
        
        return [
            SubjectInfo(
                id=row["id"],
                class_id=row["class_id"],
                subject_code=row["subject_code"],
                subject_name=row["subject_name"],
                description=row.get("description"),
                is_active=row.get("is_active", True),
            )
            for row in response.data
        ]

    async def get_class_by_number(self, class_number: int) -> Optional[ClassInfo]:
        """Get class info by class number (e.g., 10 for Class 10)."""
        response = (
            self.client.table("classes")
            .select("*")
            .eq("class_number", class_number)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        row = response.data[0]
        return ClassInfo(
            id=row["id"],
            class_name=row["class_name"],
            class_number=row["class_number"],
            description=row.get("description"),
        )

    # ========================= USER OPERATIONS =========================

    async def create_user(
        self,
        name: str,
        class_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> str:
        """
        Create a new user and initialize their learner profile.
        Returns the user_id.
        """
        user_id = str(uuid.uuid4())
        
        # Create user record
        user_data = {
            "id": user_id,
            "name": name,
            "class_id": class_id,
            "email": email,
            "created_at": datetime.now().isoformat(),
        }
        
        self.client.table("users").insert(user_data).execute()
        
        # Initialize learner profile
        profile_data = {
            "student_id": user_id,
            "learning_style": LearningStyle.VISUAL_ANALOGY.value,
            "preferred_analogies": ["sports", "daily_life"],
            "weak_topics": [],
            "strong_topics": [],
            "topic_knowledge": {},
            "historical_mistakes": [],
            "total_study_time_minutes": 0,
            "updated_at": datetime.now().isoformat(),
        }
        
        self.client.table("learner_profiles").insert(profile_data).execute()
        
        return user_id

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        response = (
            self.client.table("users")
            .select("*")
            .eq("id", user_id)
            .execute()
        )
        
        if response.data:
            return response.data[0]
        return None

    async def user_exists(self, user_id: str) -> bool:
        """Check if a user exists."""
        user = await self.get_user(user_id)
        return user is not None

    # ========================= LEARNER PROFILE OPERATIONS =========================

    async def get_learner_profile(self, student_id: str) -> Optional[LearnerProfile]:
        """Get the complete learner profile for a student."""
        response = (
            self.client.table("learner_profiles")
            .select("*")
            .eq("student_id", student_id)
            .execute()
        )
        
        if not response.data:
            return None
        
        data = response.data[0]
        
        # Convert topic_knowledge dict to TopicKnowledge objects
        topic_knowledge = {}
        if data.get("topic_knowledge"):
            for topic_id, tk_data in data["topic_knowledge"].items():
                topic_knowledge[topic_id] = TopicKnowledge(**tk_data)
        
        return LearnerProfile(
            student_id=data["student_id"],
            name=data.get("name"),
            learning_style=LearningStyle(data.get("learning_style", "visual+analogy")),
            preferred_analogies=data.get("preferred_analogies", []),
            weak_topics=data.get("weak_topics", []),
            strong_topics=data.get("strong_topics", []),
            topic_knowledge=topic_knowledge,
            historical_mistakes=data.get("historical_mistakes", []),
            total_study_time_minutes=data.get("total_study_time_minutes", 0),
        )

    async def update_learner_profile(
        self,
        student_id: str,
        profile: LearnerProfile,
    ) -> None:
        """Update a learner's profile."""
        # Convert TopicKnowledge objects to dicts
        topic_knowledge_dict = {
            k: v.model_dump() for k, v in profile.topic_knowledge.items()
        }
        
        update_data = {
            "learning_style": profile.learning_style.value,
            "preferred_analogies": profile.preferred_analogies,
            "weak_topics": profile.weak_topics,
            "strong_topics": profile.strong_topics,
            "topic_knowledge": topic_knowledge_dict,
            "historical_mistakes": profile.historical_mistakes,
            "total_study_time_minutes": profile.total_study_time_minutes,
            "updated_at": datetime.now().isoformat(),
        }
        
        self.client.table("learner_profiles").update(update_data).eq(
            "student_id", student_id
        ).execute()

    async def update_learning_style(
        self,
        student_id: str,
        learning_style: LearningStyle,
    ) -> None:
        """Update just the learning style."""
        self.client.table("learner_profiles").update(
            {
                "learning_style": learning_style.value,
                "updated_at": datetime.now().isoformat(),
            }
        ).eq("student_id", student_id).execute()

    async def add_weak_topic(self, student_id: str, topic: str) -> None:
        """Add a topic to weak topics list. Format: 'subject_code:topic_code'"""
        profile = await self.get_learner_profile(student_id)
        if profile and topic not in profile.weak_topics:
            profile.weak_topics.append(topic)
            if topic in profile.strong_topics:
                profile.strong_topics.remove(topic)
            await self.update_learner_profile(student_id, profile)

    async def add_strong_topic(self, student_id: str, topic: str) -> None:
        """Add a topic to strong topics list. Format: 'subject_code:topic_code'"""
        profile = await self.get_learner_profile(student_id)
        if profile and topic not in profile.strong_topics:
            profile.strong_topics.append(topic)
            if topic in profile.weak_topics:
                profile.weak_topics.remove(topic)
            await self.update_learner_profile(student_id, profile)

    # ========================= ASSESSMENT OPERATIONS =========================

    async def store_assessment(
        self,
        result: AssessmentResult,
    ) -> str:
        """Store an assessment result. Returns assessment_id."""
        assessment_data = {
            "id": result.assessment_id,
            "student_id": result.student_id,
            "subject_id": result.subject_id,
            "subject_code": result.subject_code,
            "topic_code": result.topic_code,
            "topic_name": result.topic_name,
            "score": result.score,
            "max_score": result.max_score,
            "level": result.level.value,
            "confidence": result.confidence,
            "misconceptions": result.misconceptions,
            "weak_concepts": result.weak_concepts,
            "strong_concepts": result.strong_concepts,
            "questions_attempted": result.questions_attempted,
            "questions_correct": result.questions_correct,
            "time_taken_seconds": result.time_taken_seconds,
            "created_at": result.created_at.isoformat(),
        }
        
        self.client.table("assessments").insert(assessment_data).execute()
        
        # Update topic progress
        await self._update_topic_progress_from_assessment(result)
        
        return result.assessment_id

    async def get_assessment(self, assessment_id: str) -> Optional[AssessmentResult]:
        """Get a specific assessment by ID."""
        response = (
            self.client.table("assessments")
            .select("*")
            .eq("id", assessment_id)
            .execute()
        )
        
        if not response.data:
            return None
        
        data = response.data[0]
        return AssessmentResult(
            assessment_id=data["id"],
            student_id=data["student_id"],
            subject_id=data.get("subject_id"),
            subject_code=data["subject_code"],
            topic_code=data["topic_code"],
            topic_name=data.get("topic_name"),
            score=data["score"],
            max_score=data["max_score"],
            level=MasteryLevel(data["level"]),
            confidence=data["confidence"],
            misconceptions=data.get("misconceptions", []),
            weak_concepts=data.get("weak_concepts", []),
            strong_concepts=data.get("strong_concepts", []),
            questions_attempted=data.get("questions_attempted", 0),
            questions_correct=data.get("questions_correct", 0),
            time_taken_seconds=data.get("time_taken_seconds"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    async def get_assessment_history(
        self,
        student_id: str,
        subject_code: Optional[str] = None,
        topic_code: Optional[str] = None,
        limit: int = 50,
    ) -> List[AssessmentResult]:
        """Get assessment history for a student."""
        query = (
            self.client.table("assessments")
            .select("*")
            .eq("student_id", student_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        
        if subject_code:
            query = query.eq("subject_code", subject_code)
        if topic_code:
            query = query.eq("topic_code", topic_code)
        
        response = query.execute()
        
        results = []
        for data in response.data:
            results.append(
                AssessmentResult(
                    assessment_id=data["id"],
                    student_id=data["student_id"],
                    subject_id=data.get("subject_id"),
                    subject_code=data["subject_code"],
                    topic_code=data["topic_code"],
                    topic_name=data.get("topic_name"),
                    score=data["score"],
                    max_score=data["max_score"],
                    level=MasteryLevel(data["level"]),
                    confidence=data["confidence"],
                    misconceptions=data.get("misconceptions", []),
                    weak_concepts=data.get("weak_concepts", []),
                    strong_concepts=data.get("strong_concepts", []),
                    questions_attempted=data.get("questions_attempted", 0),
                    questions_correct=data.get("questions_correct", 0),
                    created_at=datetime.fromisoformat(data["created_at"]),
                )
            )
        return results

    # ========================= TOPIC PROGRESS OPERATIONS =========================

    async def _update_topic_progress_from_assessment(
        self,
        result: AssessmentResult,
    ) -> None:
        """Internal: Update topic progress after an assessment."""
        # Skip if no subject_id (can't track progress without it)
        if not result.subject_id:
            return
        
        # Check if progress exists
        response = (
            self.client.table("topic_progress")
            .select("*")
            .eq("student_id", result.student_id)
            .eq("subject_id", result.subject_id)
            .eq("topic_code", result.topic_code)
            .execute()
        )
        
        if response.data:
            existing = response.data[0]
            new_attempts = existing["attempts"] + 1
            new_score = (
                existing["mastery_score"] * existing["attempts"] + result.score
            ) / new_attempts
            
            self.client.table("topic_progress").update(
                {
                    "mastery_score": new_score,
                    "attempts": new_attempts,
                    "last_attempt": datetime.now().isoformat(),
                }
            ).eq("student_id", result.student_id).eq(
                "subject_id", result.subject_id
            ).eq("topic_code", result.topic_code).execute()
        else:
            self.client.table("topic_progress").insert(
                {
                    "student_id": result.student_id,
                    "subject_id": result.subject_id,
                    "topic_code": result.topic_code,
                    "mastery_score": result.score,
                    "attempts": 1,
                    "last_attempt": datetime.now().isoformat(),
                }
            ).execute()

    async def get_topic_progress(
        self,
        student_id: str,
        subject_code: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Get all topic progress for a student in a subject."""
        # First get subject_id from subject_code
        response = (
            self.client.table("topic_progress")
            .select("*")
            .eq("student_id", student_id)
            .execute()
        )
        
        return {row["topic_code"]: row for row in response.data}

    async def get_weak_topics(
        self,
        student_id: str,
        subject_id: str,
        threshold: float = 50.0,
    ) -> List[str]:
        """Get topics where mastery is below threshold."""
        response = (
            self.client.table("topic_progress")
            .select("topic_code")
            .eq("student_id", student_id)
            .eq("subject_id", subject_id)
            .lt("mastery_score", threshold)
            .execute()
        )
        
        return [row["topic_code"] for row in response.data]

    # ========================= MISCONCEPTION TRACKING =========================

    async def store_misconception(
        self,
        student_id: str,
        subject_id: str,
        topic_code: str,
        misconception: str,
    ) -> None:
        """Store a detected misconception."""
        self.client.table("misconceptions").insert(
            {
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "subject_id": subject_id,
                "topic_code": topic_code,
                "misconception": misconception,
                "resolved": False,
                "detected_at": datetime.now().isoformat(),
            }
        ).execute()

    async def get_misconceptions(
        self,
        student_id: str,
        subject_id: Optional[str] = None,
        resolved: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get misconceptions for a student."""
        query = (
            self.client.table("misconceptions")
            .select("*")
            .eq("student_id", student_id)
        )
        
        if subject_id:
            query = query.eq("subject_id", subject_id)
        if resolved is not None:
            query = query.eq("resolved", resolved)
        
        response = query.execute()
        return response.data

    async def resolve_misconception(self, misconception_id: str) -> None:
        """Mark a misconception as resolved."""
        self.client.table("misconceptions").update(
            {
                "resolved": True,
                "resolved_at": datetime.now().isoformat(),
            }
        ).eq("id", misconception_id).execute()

    # ========================= ANALYTICS =========================

    async def get_progress_analytics(
        self,
        student_id: str,
    ) -> Dict[str, Any]:
        """Get comprehensive progress analytics for a student."""
        profile = await self.get_learner_profile(student_id)
        
        # Get user to find their class
        user = await self.get_user(student_id)
        if not user:
            return {"error": "User not found"}
        
        analytics = {
            "student_id": student_id,
            "subjects": {},
        }
        
        # If user has a class, get subjects for that class
        if user.get("class_id"):
            subjects = await self.get_subjects_for_class(user["class_id"])
            
            for subject in subjects:
                progress = await self.get_topic_progress(student_id, subject.subject_code)
                assessments = await self.get_assessment_history(
                    student_id, subject_code=subject.subject_code, limit=100
                )
                misconceptions = await self.get_misconceptions(
                    student_id, subject_id=subject.id, resolved=False
                )
                
                if progress or assessments:
                    scores = [a.score for a in assessments]
                    analytics["subjects"][subject.subject_code] = {
                        "subject_name": subject.subject_name,
                        "topics_covered": len(progress),
                        "total_assessments": len(assessments),
                        "average_score": sum(scores) / len(scores) if scores else 0,
                        "weak_topics": await self.get_weak_topics(student_id, subject.id),
                        "active_misconceptions": len(misconceptions),
                    }
        
        analytics["learning_style"] = profile.learning_style.value if profile else None
        analytics["total_study_time"] = (
            profile.total_study_time_minutes if profile else 0
        )
        
        return analytics


# Singleton instance
supabase_manager = SupabaseManager()
