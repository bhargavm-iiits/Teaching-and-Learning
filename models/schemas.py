"""
Core Pydantic models for the AI-Driven Personalized VR Teaching System.
These models define the data structures used by all agents.
EXTENSIBLE DESIGN: Supports dynamic classes and subjects.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ========================= ENUMS =========================

class MasteryLevel(str, Enum):
    """Student's mastery level for a topic."""
    WEAK = "weak"
    DEVELOPING = "developing"
    PROFICIENT = "proficient"
    MASTERED = "mastered"


class QuestionType(str, Enum):
    """Types of questions supported in assessments."""
    MCQ = "mcq"
    DESCRIPTIVE = "descriptive"
    NUMERICAL = "numerical"
    TRUE_FALSE = "true_false"


class LearningStyle(str, Enum):
    """Student's preferred learning style."""
    VISUAL = "visual"
    AUDITORY = "auditory"
    KINESTHETIC = "kinesthetic"
    VISUAL_ANALOGY = "visual+analogy"
    FORMULA_FIRST = "formula-first"
    INTUITION_FIRST = "intuition-first"


class AssessmentStage(str, Enum):
    """Stage of assessment to determine question generation strategy."""
    INITIAL = "initial"  # Diagnostic, full range
    MID_LESSON = "mid-lesson"  # Quick concept check
    POST_LESSON = "post-lesson"  # Comprehensive review


# ========================= CLASS & SUBJECT MODELS =========================

class ClassInfo(BaseModel):
    """Represents a class/grade level."""
    id: str
    class_name: str  # "Class 10"
    class_number: int  # 10
    description: Optional[str] = None
    is_active: bool = True


class SubjectInfo(BaseModel):
    """Represents a subject within a class."""
    id: str
    class_id: str
    subject_code: str  # "physics"
    subject_name: str  # "Physics"
    description: Optional[str] = None
    is_active: bool = True


class TopicInfo(BaseModel):
    """Represents a topic within a subject."""
    id: str
    subject_id: str
    topic_code: str  # "projectile_motion"
    topic_name: str  # "Projectile Motion"
    subtopics: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    order_index: int = 0
    estimated_duration_minutes: int = 30


# ========================= CORE MODELS =========================

class TopicKnowledge(BaseModel):
    """Per-topic knowledge state for a student."""
    topic_id: str
    topic_code: str
    topic_name: str
    subject_id: str
    subject_code: str
    mastery_level: MasteryLevel = MasteryLevel.WEAK
    score: int = Field(default=0, ge=0, le=100)
    questions_attempted: int = 0
    questions_correct: int = 0
    misconceptions: List[str] = Field(default_factory=list)
    last_assessed: Optional[datetime] = None

    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage."""
        if self.questions_attempted == 0:
            return 0.0
        return (self.questions_correct / self.questions_attempted) * 100


class LearnerProfile(BaseModel):
    """
    Agent B output: Complete learner profile.
    Continuously updated based on interactions.
    """
    student_id: str
    name: Optional[str] = None
    class_id: Optional[str] = None  # Which class the student is in
    class_number: Optional[int] = None  # e.g., 10
    
    # Learning preferences
    learning_style: LearningStyle = LearningStyle.VISUAL_ANALOGY
    preferred_analogies: List[str] = Field(
        default_factory=lambda: ["sports", "daily_life"]
    )
    
    # Topic mastery (keyed by subject_code:topic_code)
    weak_topics: List[str] = Field(default_factory=list)
    strong_topics: List[str] = Field(default_factory=list)
    topic_knowledge: Dict[str, TopicKnowledge] = Field(default_factory=dict)
    
    # Historical data
    historical_mistakes: List[str] = Field(default_factory=list)
    total_study_time_minutes: int = 0
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)



# ========================= ASSESSMENT MODELS =========================

class Question(BaseModel):
    """A single question in an assessment."""
    question_id: str
    question_type: QuestionType
    question_text: str
    topic_code: str
    topic_name: Optional[str] = None
    subject_id: Optional[str] = None
    subject_code: str  # "physics", "maths", etc.
    difficulty: MasteryLevel
    
    # For MCQ
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    
    # For descriptive/numerical
    expected_keywords: Optional[List[str]] = None
    model_answer: Optional[str] = None
    rubric: Optional[str] = None
    tolerance: Optional[float] = None  # For numerical answers
    unit: Optional[str] = None
    
    max_marks: int = 1

    # VR visual analogy context (optional)
    # Contains: analogy, scene, visual_objects, visualization_prompt
    vr_visual_context: Optional[Dict[str, Any]] = None


class QuestionResponse(BaseModel):
    """Student's response to a question."""
    question_id: str
    answer: str
    time_taken_seconds: Optional[int] = None


class AssessmentResult(BaseModel):
    """
    Agent A output: Result of evaluating student answers.
    """
    assessment_id: str
    student_id: str
    subject_id: Optional[str] = None
    subject_code: str  # "physics", "maths", etc.
    topic_code: str
    topic_name: Optional[str] = None
    
    # Scores
    score: int = Field(ge=0, le=100)
    max_score: int = 100
    level: MasteryLevel
    confidence: float = Field(ge=0.0, le=1.0)
    
    # Analysis
    misconceptions: List[str] = Field(default_factory=list)
    weak_concepts: List[str] = Field(default_factory=list)
    strong_concepts: List[str] = Field(default_factory=list)
    
    # Details
    questions_attempted: int = 0
    questions_correct: int = 0
    time_taken_seconds: Optional[int] = None
    
    created_at: datetime = Field(default_factory=datetime.now)


class DescriptiveEvaluation(BaseModel):
    """Evaluation result for a descriptive answer."""
    question_id: str
    score: int
    max_score: int
    
    # Analysis
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    misconceptions_detected: List[str] = Field(default_factory=list)
    
    # Feedback
    feedback: str = ""
    model_answer_comparison: Optional[str] = None


# ========================= CURRICULUM MODELS =========================

class CurriculumPlan(BaseModel):
    """
    Agent C output: What to teach next.
    """
    topic_code: str
    topic_name: str
    subject_id: Optional[str] = None
    subject_code: str  # "physics", "maths", etc.
    priority: str = "high"  # high/medium/low
    depth: str = "conceptual+visual"  # conceptual/visual/mathematical
    
    subtopics: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    estimated_duration_minutes: int = 30
    
    # Teaching order
    order_in_syllabus: int = 1
    recommended_after: Optional[str] = None


class PedagogyPlan(BaseModel):
    """
    Agent D output: How to teach a topic.
    """
    topic: str
    
    # Teaching approach
    analogy: str
    analogy_category: str  # sports, gaming, daily_life, etc.
    visualization: str
    interaction: str
    
    # Strategy
    approach: str = "intuition-first"  # intuition-first / formula-first
    use_examples_first: bool = True
    emphasize_visual: bool = True
    
    # VR-specific
    recommended_scene: str
    key_objects: List[str] = Field(default_factory=list)
    interaction_points: List[str] = Field(default_factory=list)


# ========================= EXAM MODELS =========================

class Exam(BaseModel):
    """A complete exam with multiple questions."""
    exam_id: str
    student_id: str
    subject_id: Optional[str] = None
    subject_code: str  # "physics", "maths", etc.
    topic_code: str
    topic_name: Optional[str] = None
    
    questions: List[Question]
    total_marks: int
    time_limit_minutes: Optional[int] = None
    
    created_at: datetime = Field(default_factory=datetime.now)


class ExamResponse(BaseModel):
    """Student's complete exam submission."""
    exam_id: str
    student_id: str
    responses: List[QuestionResponse]
    submitted_at: datetime = Field(default_factory=datetime.now)


class ExamResult(BaseModel):
    """Complete exam result with detailed analysis."""
    exam_id: str
    student_id: str
    
    # Scores
    total_score: int
    max_score: int
    percentage: float
    
    # Question-wise results
    question_results: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Analysis
    overall_feedback: str = ""
    misconceptions: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # Next steps
    suggested_topics: List[str] = Field(default_factory=list)
    mastery_update: Optional[MasteryLevel] = None
