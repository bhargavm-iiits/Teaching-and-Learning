"""
Models package for the AI-Driven Personalized VR Teaching System.
Contains Pydantic schemas and VR contracts.
EXTENSIBLE DESIGN: Supports dynamic classes and subjects.
"""

from models.schemas import (
    # Class & Subject models (dynamic, not enum)
    ClassInfo,
    SubjectInfo,
    TopicInfo,
    # Core enums
    MasteryLevel,
    QuestionType,
    LearningStyle,
    AssessmentStage,
    # Core models
    TopicKnowledge,
    LearnerProfile,
    # Assessment models
    Question,
    QuestionResponse,
    AssessmentResult,
    DescriptiveEvaluation,
    # Curriculum models
    CurriculumPlan,
    PedagogyPlan,
    # Exam models
    Exam,
    ExamResponse,
    ExamResult,
)
from models.vr_contracts import (
    AvatarActionType,
    AvatarAction,
    VoiceEmotion,
    VoiceCommand,
    VisualCommand,
    InteractionType,
    InteractionCommand,
    AssessmentType,
    AssessmentCommand,
    VRInstruction,
)

__all__ = [
    # Class & Subject
    "ClassInfo",
    "SubjectInfo",
    "TopicInfo",
    # Enums
    "MasteryLevel",
    "QuestionType",
    "LearningStyle",
    "AssessmentStage",
    # Core models
    "TopicKnowledge",
    "LearnerProfile",
    # Assessment
    "Question",
    "QuestionResponse",
    "AssessmentResult",
    "DescriptiveEvaluation",
    # Curriculum
    "CurriculumPlan",
    "PedagogyPlan",
    # Exam
    "Exam",
    "ExamResponse",
    "ExamResult",
    # VR Contracts
    "AvatarActionType",
    "AvatarAction",
    "VoiceEmotion",
    "VoiceCommand",
    "VisualCommand",
    "InteractionType",
    "InteractionCommand",
    "AssessmentType",
    "AssessmentCommand",
    "VRInstruction",
]
