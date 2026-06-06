"""
Supabase client for the AI-Driven Personalized VR Teaching System.
Handles all database operations for users, profiles, assessments, and progress.
EXTENSIBLE DESIGN: Uses subject_code strings instead of hardcoded Subject enum.
"""

from __future__ import annotations

import os
import json
import uuid
import httpx
import logging
import functools
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

logger = logging.getLogger(__name__)


def handle_supabase_query(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        # Ensure connectivity state is initialized
        self.check_connectivity()
        
        # If online, try the query
        if not self._offline_mode:
            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                err_msg = str(e).lower()
                is_network_err = any(x in err_msg for x in [
                    "connect", "timeout", "getaddrinfo", "host", "connection", "unreachable", "dns", "api_key"
                ])
                if is_network_err or "execute" in err_msg:
                    logger.warning(f"[SupabaseManager] Live query to '{func.__name__}' failed due to connectivity: {e}. Falling back to offline mode.")
                    self._offline_mode = True
                else:
                    raise e

        # If offline, fall back to mock handler
        fallback_name = f"_offline_{func.__name__}"
        fallback_func = getattr(self, fallback_name, None)
        if fallback_func:
            return await fallback_func(*args, **kwargs)
        else:
            raise NotImplementedError(f"Offline fallback for '{func.__name__}' is not implemented.")

    return wrapper


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
        self._offline_mode: Optional[bool] = None
        self._local_db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "db", 
            "local_mock_db.json"
        )
        self._local_db = {
            "classes": [],
            "subjects": [],
            "users": {},
            "learner_profiles": {},
            "assessments": {},
            "topic_progress": {},
            "misconceptions": {}
        }
        self._load_local_db()

    def _normalize_subject_code(self, subject_code: Optional[str]) -> Optional[str]:
        if not subject_code:
            return subject_code
        code = subject_code.lower().strip()
        if code in ["phy", "physics"]:
            return "physics"
        if code in ["chem", "chemistry"]:
            return "chemistry"
        if code in ["math", "maths", "mathematics"]:
            return "maths"
        return code

    def _normalize_topic_code(self, topic_code: Optional[str]) -> Optional[str]:
        if not topic_code:
            return topic_code
        code = topic_code.lower().strip()
        if code in ["motion_speed", "motion", "speed"]:
            return "motion"
        return code

    def check_connectivity(self) -> bool:
        """Check if Supabase is online. If not, toggle offline mode."""
        if self._offline_mode is not None:
            return not self._offline_mode
        
        # Manual bypass via environment variable
        if os.getenv("OFFLINE_MODE", "false").lower() == "true":
            logger.info("[SupabaseManager] Forced OFFLINE_MODE=true via env. Enabling offline fallback.")
            self._offline_mode = True
            return False

        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            logger.warning("[SupabaseManager] Supabase configuration variables are missing. Enabling offline fallback.")
            self._offline_mode = True
            return False

        try:
            # Send a quick request to the Supabase REST endpoint with a 1.5-second timeout
            headers = {"apikey": config.SUPABASE_KEY}
            response = httpx.get(
                f"{config.SUPABASE_URL}/rest/v1/", 
                headers=headers, 
                timeout=1.5
            )
            # 200 OK or 401 Unauthorized or 404 is reachable
            if response.status_code in [200, 401, 404]:
                logger.info("[SupabaseManager] Successfully connected to Supabase.")
                self._offline_mode = False
                return True
            else:
                logger.warning(f"[SupabaseManager] Supabase returned status code {response.status_code}. Enabling offline fallback.")
                self._offline_mode = True
                return False
        except Exception as e:
            logger.warning(f"[SupabaseManager] Failed to connect to Supabase: {e}. Enabling offline fallback.")
            self._offline_mode = True
            return False

    def _load_local_db(self):
        if os.path.exists(self._local_db_path):
            try:
                with open(self._local_db_path, "r") as f:
                    self._local_db = json.load(f)
            except Exception as e:
                logger.warning(f"[SupabaseManager] Error loading local mock DB: {e}. Reinitializing.")
        
        # Ensure structural keys exist
        for key in ["classes", "subjects", "users", "learner_profiles", "assessments", "topic_progress", "misconceptions"]:
            if key not in self._local_db:
                self._local_db[key] = [] if key in ["classes", "subjects"] else {}

        # Seed initial classes if empty
        if not self._local_db["classes"]:
            self._local_db["classes"] = [
                {
                    "id": "c1000000-0000-0000-0000-000000000010",
                    "class_name": "Class 10",
                    "class_number": 10,
                    "description": "High School - Grade 10 (Board)",
                    "is_active": True
                }
            ]
        
        # Seed initial subjects if empty
        if not self._local_db["subjects"]:
            self._local_db["subjects"] = [
                {
                    "id": "s1000000-0000-0000-0000-000000000001",
                    "class_id": "c1000000-0000-0000-0000-000000000010",
                    "subject_code": "physics",
                    "subject_name": "Physics",
                    "description": "Study of matter, energy, and their interactions",
                    "is_active": True
                },
                {
                    "id": "s1000000-0000-0000-0000-000000000002",
                    "class_id": "c1000000-0000-0000-0000-000000000010",
                    "subject_code": "chemistry",
                    "subject_name": "Chemistry",
                    "description": "Study of substances and their properties",
                    "is_active": True
                },
                {
                    "id": "s1000000-0000-0000-0000-000000000003",
                    "class_id": "c1000000-0000-0000-0000-000000000010",
                    "subject_code": "maths",
                    "subject_name": "Mathematics",
                    "description": "Study of numbers, quantities, and shapes",
                    "is_active": True
                }
            ]
            self._save_local_db()

    def _save_local_db(self):
        try:
            with open(self._local_db_path, "w") as f:
                json.dump(self._local_db, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"[SupabaseManager] Error saving local mock DB: {e}")

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

    @handle_supabase_query
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

    async def _offline_get_classes(self, active_only: bool = True) -> List[ClassInfo]:
        classes = self._local_db.get("classes", [])
        if active_only:
            classes = [c for c in classes if c.get("is_active", True)]
        return [
            ClassInfo(
                id=row["id"],
                class_name=row["class_name"],
                class_number=row["class_number"],
                description=row.get("description"),
                is_active=row.get("is_active", True),
            )
            for row in classes
        ]

    @handle_supabase_query
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

    async def _offline_get_subjects_for_class(
        self, class_id: str, active_only: bool = True
    ) -> List[SubjectInfo]:
        subjects = self._local_db.get("subjects", [])
        filtered = [s for s in subjects if s.get("class_id") == class_id]
        if active_only:
            filtered = [s for s in filtered if s.get("is_active", True)]
        return [
            SubjectInfo(
                id=row["id"],
                class_id=row["class_id"],
                subject_code=row["subject_code"],
                subject_name=row["subject_name"],
                description=row.get("description"),
                is_active=row.get("is_active", True),
            )
            for row in filtered
        ]

    @handle_supabase_query
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

    async def _offline_get_class_by_number(self, class_number: int) -> Optional[ClassInfo]:
        classes = self._local_db.get("classes", [])
        for row in classes:
            if row.get("class_number") == class_number:
                return ClassInfo(
                    id=row["id"],
                    class_name=row["class_name"],
                    class_number=row["class_number"],
                    description=row.get("description"),
                )
        return None

    # ========================= USER OPERATIONS =========================

    @handle_supabase_query
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

    async def _offline_create_user(
        self,
        name: str,
        class_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> str:
        import uuid
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "name": name,
            "class_id": class_id,
            "email": email,
            "created_at": datetime.now().isoformat(),
        }
        self._local_db["users"][user_id] = user_data
        
        # Initialize learner profile
        profile_data = {
            "student_id": user_id,
            "name": name,
            "learning_style": LearningStyle.VISUAL_ANALOGY.value,
            "preferred_analogies": ["sports", "daily_life"],
            "weak_topics": [],
            "strong_topics": [],
            "topic_knowledge": {},
            "historical_mistakes": [],
            "total_study_time_minutes": 0,
            "updated_at": datetime.now().isoformat(),
        }
        self._local_db["learner_profiles"][user_id] = profile_data
        self._save_local_db()
        return user_id

    @handle_supabase_query
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

    async def _offline_get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        if user_id not in self._local_db["users"]:
            if user_id == "test_student_123":
                await self._offline_create_user("Test Student", None, "test@example.com")
                profile = self._local_db["learner_profiles"].pop(list(self._local_db["learner_profiles"].keys())[-1])
                user = self._local_db["users"].pop(list(self._local_db["users"].keys())[-1])
                profile["student_id"] = "test_student_123"
                user["id"] = "test_student_123"
                self._local_db["learner_profiles"]["test_student_123"] = profile
                self._local_db["users"]["test_student_123"] = user
                self._save_local_db()
            else:
                return None
        return self._local_db["users"].get(user_id)

    async def user_exists(self, user_id: str) -> bool:
        """Check if a user exists."""
        user = await self.get_user(user_id)
        return user is not None

    # ========================= LEARNER PROFILE OPERATIONS =========================

    @handle_supabase_query
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

    async def _offline_get_learner_profile(self, student_id: str) -> Optional[LearnerProfile]:
        await self._offline_get_user(student_id)
        data = self._local_db["learner_profiles"].get(student_id)
        if not data:
            return None
            
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

    @handle_supabase_query
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

    async def _offline_update_learner_profile(
        self,
        student_id: str,
        profile: LearnerProfile,
    ) -> None:
        topic_knowledge_dict = {
            k: v.model_dump() for k, v in profile.topic_knowledge.items()
        }
        update_data = {
            "student_id": student_id,
            "name": profile.name,
            "learning_style": profile.learning_style.value,
            "preferred_analogies": profile.preferred_analogies,
            "weak_topics": profile.weak_topics,
            "strong_topics": profile.strong_topics,
            "topic_knowledge": topic_knowledge_dict,
            "historical_mistakes": profile.historical_mistakes,
            "total_study_time_minutes": profile.total_study_time_minutes,
            "updated_at": datetime.now().isoformat(),
        }
        self._local_db["learner_profiles"][student_id] = update_data
        self._save_local_db()

    @handle_supabase_query
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

    async def _offline_update_learning_style(
        self,
        student_id: str,
        learning_style: LearningStyle,
    ) -> None:
        if student_id in self._local_db["learner_profiles"]:
            self._local_db["learner_profiles"][student_id]["learning_style"] = learning_style.value
            self._local_db["learner_profiles"][student_id]["updated_at"] = datetime.now().isoformat()
            self._save_local_db()

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

    @handle_supabase_query
    async def store_assessment(
        self,
        result: AssessmentResult,
    ) -> str:
        """Store an assessment result. Returns assessment_id."""
        result.subject_code = self._normalize_subject_code(result.subject_code)
        result.topic_code = self._normalize_topic_code(result.topic_code)
        
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

    async def _offline_store_assessment(self, result: AssessmentResult) -> str:
        result.subject_code = self._normalize_subject_code(result.subject_code)
        result.topic_code = self._normalize_topic_code(result.topic_code)
        
        assessment_id = result.assessment_id
        assessment_data = {
            "id": assessment_id,
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
        self._local_db["assessments"][assessment_id] = assessment_data
        self._save_local_db()
        
        # Update topic progress
        await self._update_topic_progress_from_assessment(result)
        return assessment_id

    @handle_supabase_query
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

    async def _offline_get_assessment(self, assessment_id: str) -> Optional[AssessmentResult]:
        data = self._local_db["assessments"].get(assessment_id)
        if not data:
            return None
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

    @handle_supabase_query
    async def get_assessment_history(
        self,
        student_id: str,
        subject_code: Optional[str] = None,
        topic_code: Optional[str] = None,
        limit: int = 50,
    ) -> List[AssessmentResult]:
        """Get assessment history for a student."""
        subject_code = self._normalize_subject_code(subject_code)
        topic_code = self._normalize_topic_code(topic_code)
        
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

    async def _offline_get_assessment_history(
        self,
        student_id: str,
        subject_code: Optional[str] = None,
        topic_code: Optional[str] = None,
        limit: int = 50,
    ) -> List[AssessmentResult]:
        assessments = list(self._local_db["assessments"].values())
        filtered = [a for a in assessments if a["student_id"] == student_id]
        
        if subject_code:
            norm_sub = self._normalize_subject_code(subject_code)
            filtered = [a for a in filtered if self._normalize_subject_code(a["subject_code"]) == norm_sub]
        if topic_code:
            norm_top = self._normalize_topic_code(topic_code)
            filtered = [a for a in filtered if self._normalize_topic_code(a["topic_code"]) == norm_top]
            
        filtered.sort(key=lambda x: x["created_at"], reverse=True)
        filtered = filtered[:limit]
        
        return [
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
            for data in filtered
        ]

    # ========================= TOPIC PROGRESS OPERATIONS =========================

    @handle_supabase_query
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

    async def _offline__update_topic_progress_from_assessment(
        self,
        result: AssessmentResult,
    ) -> None:
        subject_id = result.subject_id or "default_subject_id"
        key = f"{result.student_id}:{subject_id}:{result.topic_code}"
        
        existing = self._local_db["topic_progress"].get(key)
        if existing:
            new_attempts = existing["attempts"] + 1
            new_score = (existing["mastery_score"] * existing["attempts"] + result.score) / new_attempts
            existing["mastery_score"] = new_score
            existing["attempts"] = new_attempts
            existing["last_attempt"] = datetime.now().isoformat()
        else:
            self._local_db["topic_progress"][key] = {
                "student_id": result.student_id,
                "subject_id": subject_id,
                "topic_code": result.topic_code,
                "mastery_score": float(result.score),
                "attempts": 1,
                "last_attempt": datetime.now().isoformat(),
            }
        self._save_local_db()

    @handle_supabase_query
    async def get_topic_progress(
        self,
        student_id: str,
        subject_code: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Get all topic progress for a student in a subject."""
        response = (
            self.client.table("topic_progress")
            .select("*")
            .eq("student_id", student_id)
            .execute()
        )
        
        return {row["topic_code"]: row for row in response.data}

    async def _offline_get_topic_progress(
        self,
        student_id: str,
        subject_code: str,
    ) -> Dict[str, Dict[str, Any]]:
        progress_data = {}
        for key, val in self._local_db["topic_progress"].items():
            if val["student_id"] == student_id:
                progress_data[val["topic_code"]] = val
        return progress_data

    @handle_supabase_query
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

    async def _offline_get_weak_topics(
        self,
        student_id: str,
        subject_id: str,
        threshold: float = 50.0,
    ) -> List[str]:
        results = []
        for key, val in self._local_db["topic_progress"].items():
            if val["student_id"] == student_id and val["subject_id"] == subject_id:
                if val["mastery_score"] < threshold:
                    results.append(val["topic_code"])
        return results

    # ========================= MISCONCEPTION TRACKING =========================

    @handle_supabase_query
    async def store_misconception(
        self,
        student_id: str,
        subject_id: str,
        topic_code: str,
        misconception: str,
    ) -> None:
        """Store a detected misconception."""
        topic_code = self._normalize_topic_code(topic_code)
        
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

    async def _offline_store_misconception(
        self,
        student_id: str,
        subject_id: str,
        topic_code: str,
        misconception: str,
    ) -> None:
        import uuid
        misc_id = str(uuid.uuid4())
        self._local_db["misconceptions"][misc_id] = {
            "id": misc_id,
            "student_id": student_id,
            "subject_id": subject_id,
            "topic_code": self._normalize_topic_code(topic_code),
            "misconception": misconception,
            "resolved": False,
            "detected_at": datetime.now().isoformat(),
        }
        self._save_local_db()

    @handle_supabase_query
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

    async def _offline_get_misconceptions(
        self,
        student_id: str,
        subject_id: Optional[str] = None,
        resolved: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        misc = list(self._local_db["misconceptions"].values())
        filtered = [m for m in misc if m["student_id"] == student_id]
        if subject_id:
            filtered = [m for m in filtered if m["subject_id"] == subject_id]
        if resolved is not None:
            filtered = [m for m in filtered if m["resolved"] == resolved]
        return filtered

    @handle_supabase_query
    async def resolve_misconception(self, misconception_id: str) -> None:
        """Mark a misconception as resolved."""
        self.client.table("misconceptions").update(
            {
                "resolved": True,
                "resolved_at": datetime.now().isoformat(),
            }
        ).eq("id", misconception_id).execute()

    async def _offline_resolve_misconception(self, misconception_id: str) -> None:
        if misconception_id in self._local_db["misconceptions"]:
            self._local_db["misconceptions"][misconception_id]["resolved"] = True
            self._local_db["misconceptions"][misconception_id]["resolved_at"] = datetime.now().isoformat()
            self._save_local_db()

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
