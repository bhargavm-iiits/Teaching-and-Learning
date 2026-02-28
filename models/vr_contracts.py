"""
VR Interface Contracts for Unity.
These models define the ONLY JSON structures that Unity consumes.
All fields use strict enums - no free-form values allowed.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Literal, Any, Dict
from pydantic import BaseModel, Field


# ========================= AVATAR CONTRACTS =========================

class AvatarActionType(str, Enum):
    """Allowed avatar actions in VR."""
    IDLE = "idle"
    WALK = "walk"
    EXPLAIN = "explain"
    POINT = "point"
    GESTURE_LEFT = "gesture_left"
    GESTURE_RIGHT = "gesture_right"
    WAVE = "wave"
    THINK = "think"
    CELEBRATE = "celebrate"
    QUESTION = "question"  # For asking questions during assessment
    GREET = "greet"
    DEMONSTRATE = "demonstrate"
    ENCOURAGE = "encourage"


class AvatarCharacter(str, Enum):
    """Available avatar characters."""
    TEACHER = "teacher"
    ASSISTANT = "assistant"
    STUDENT_HELPER = "student_helper"


class AvatarAction(BaseModel):
    """
    Avatar control instruction for Unity.
    Unity handles: animation playback, IK, positioning.
    """
    character: AvatarCharacter = AvatarCharacter.TEACHER
    action: AvatarActionType
    target: Optional[str] = None  # Object to point at, look at, etc.
    duration_seconds: Optional[float] = None


# ========================= VOICE CONTRACTS =========================

class VoiceEmotion(str, Enum):
    """Emotion for TTS voice synthesis."""
    NEUTRAL = "neutral"
    ENCOURAGING = "encouraging"
    FRIENDLY = "friendly"
    SERIOUS = "serious"
    EXCITED = "excited"
    CURIOUS = "curious"
    CALM = "calm"


class VoicePace(str, Enum):
    """Speaking pace."""
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


class VoiceCommand(BaseModel):
    """
    Voice/dialogue instruction for Unity.
    Unity handles: TTS synthesis, lip sync, audio playback.
    """
    text: str
    emotion: VoiceEmotion = VoiceEmotion.FRIENDLY
    pace: VoicePace = VoicePace.NORMAL
    
    # Optional: specific pronunciation hints
    phonetic_hints: Optional[Dict[str, str]] = None
    
    # Timing
    delay_before_seconds: float = 0.0
    wait_for_completion: bool = True


# ========================= VISUAL CONTRACTS =========================

class MotionType(str, Enum):
    """Types of physics motions for simulations."""
    PROJECTILE = "projectile"
    LINEAR = "linear"
    CIRCULAR = "circular"
    OSCILLATION = "oscillation"
    FREE_FALL = "free_fall"
    STATIC = "static"


class VisualCommand(BaseModel):
    """
    Visual/physics instruction for Unity.
    Unity handles: object spawning, physics simulation, rendering.
    """
    object: str  # Object identifier (must exist in Unity asset library)
    
    # Motion parameters
    motion: Optional[MotionType] = None
    angle: Optional[float] = None  # degrees
    velocity: Optional[float] = None  # m/s
    acceleration: Optional[float] = None  # m/s²
    
    # Display options
    show_trajectory: bool = False
    show_vectors: bool = False
    show_labels: bool = False
    highlight: bool = False
    
    # Position (relative to scene origin)
    position: Optional[Dict[str, float]] = None  # {x, y, z}
    rotation: Optional[Dict[str, float]] = None  # {x, y, z} in degrees
    scale: Optional[float] = 1.0
    
    # Animation
    animate: bool = True
    loop_animation: bool = False
    animation_speed: float = 1.0


# ========================= INTERACTION CONTRACTS =========================

class InteractionType(str, Enum):
    """Types of user interactions in VR."""
    SLIDER = "slider"
    BUTTON = "button"
    GRAB = "grab"
    VOICE_INPUT = "voice_input"
    GAZE_SELECT = "gaze_select"
    TOUCH = "touch"
    TELEPORT = "teleport"
    MULTIPLE_CHOICE = "multiple_choice"


class InteractionCommand(BaseModel):
    """
    Interaction setup instruction for Unity.
    Unity handles: UI rendering, input capture, event handling.
    """
    type: InteractionType
    parameter: str  # What this interaction controls (e.g., "angle", "velocity")
    
    # For slider/numerical inputs
    range: Optional[List[float]] = None  # [min, max]
    default: Optional[float] = None
    step: Optional[float] = None
    
    # For button/selection
    options: Optional[List[str]] = None
    
    # Display
    label: Optional[str] = None
    tooltip: Optional[str] = None
    position: Optional[str] = None  # "left", "right", "center", "floating"
    
    # Behavior
    required: bool = False
    timeout_seconds: Optional[float] = None


# ========================= ASSESSMENT CONTRACTS =========================

class AssessmentType(str, Enum):
    """Types of in-VR assessments."""
    MCQ = "mcq"
    DESCRIPTIVE = "descriptive"
    NUMERICAL = "numerical"
    CONCEPT_CHECK = "concept_check"  # Quick yes/no understanding check
    VOICE_RESPONSE = "voice_response"


class InputMode(str, Enum):
    """Input modes for assessment responses."""
    TEXT = "text"
    VOICE = "voice"
    SELECTION = "selection"
    GESTURE = "gesture"
    GAZE = "gaze"


class AssessmentCommand(BaseModel):
    """
    Assessment trigger instruction for Unity.
    Unity handles: UI display, input capture, response collection.
    """
    type: AssessmentType
    question_id: Optional[str] = None  # Unique ID for tracking responses
    
    # Question content
    question: Optional[str] = None
    prompt: Optional[str] = None  # For descriptive
    
    # For MCQ
    options: Optional[List[str]] = None
    
    # For numerical
    unit: Optional[str] = None
    placeholder: Optional[str] = None
    
    # Input configuration
    input_mode: InputMode = InputMode.SELECTION
    
    # Timing
    time_limit_seconds: Optional[int] = None
    
    # Feedback (filled by AI after response)
    show_immediate_feedback: bool = True


# ========================= SCENE CONTRACTS =========================

class SceneType(str, Enum):
    """Available VR scenes."""
    CLASSROOM = "classroom"
    CRICKET_GROUND = "cricket_ground"
    PHYSICS_LAB = "physics_lab"
    CHEMISTRY_LAB = "chemistry_lab"
    MATH_ROOM = "math_room"
    OUTDOOR_FIELD = "outdoor_field"
    SPACE = "space"
    PLAYGROUND = "playground"


class SceneCommand(BaseModel):
    """
    Scene setup instruction for Unity.
    Unity handles: scene loading, environment setup.
    """
    scene_id: SceneType
    
    # Environment settings
    time_of_day: Optional[str] = "day"  # day, evening, night
    weather: Optional[str] = "clear"  # clear, cloudy, rain
    
    # Camera
    initial_camera_position: Optional[str] = None  # Preset position name
    allow_free_movement: bool = True


# ========================= COMPLETE VR INSTRUCTION =========================

class VRInstruction(BaseModel):
    """
    Complete VR instruction packet.
    This is the ONLY structure Unity consumes from the AI system.
    Agent E produces a list of these for each teaching session.
    """
    step_id: str
    sequence_order: int = 0
    
    # Scene (only needed for first step or scene changes)
    scene: Optional[SceneCommand] = None
    
    # Avatar behavior
    avatar: AvatarAction
    
    # Dialogue
    voice: VoiceCommand
    
    # Visual elements (optional)
    visual: Optional[VisualCommand] = None
    
    # User interaction (optional)
    interaction: Optional[InteractionCommand] = None
    
    # Assessment (optional)
    assessment: Optional[AssessmentCommand] = None
    
    # Flow control
    wait_for_voice: bool = True
    wait_for_interaction: bool = False
    auto_advance_seconds: Optional[float] = None
    
    # Metadata
    topic: Optional[str] = None
    concept: Optional[str] = None
    
    def to_unity_json(self) -> dict:
        """Export as Unity-compatible JSON (excludes None values)."""
        return self.model_dump(exclude_none=True)


# ========================= SESSION CONTRACTS =========================

class VRSession(BaseModel):
    """Complete VR teaching session."""
    session_id: str
    student_id: str
    subject: str
    topic: str
    
    instructions: List[VRInstruction]
    total_steps: int
    estimated_duration_minutes: int
    
    # State tracking
    current_step: int = 0
    completed: bool = False


class VRInteractionResponse(BaseModel):
    """Response from Unity when user interacts."""
    session_id: str
    step_id: str
    interaction_type: InteractionType
    
    # Response data
    value: Optional[Any] = None  # Slider value, button choice, etc.
    text_input: Optional[str] = None  # For voice/text input
    
    # Timing
    response_time_seconds: float
