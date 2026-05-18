"""
Lesson Manifest — the contract between Agent E (ManifestAuthorAgent) and Unity.

Unity renders this. Agent E authors it. No C# generated at runtime.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Environment / scene
# ──────────────────────────────────────────────────────────────────────────────


class EnvironmentId(str, Enum):
    INDOOR = "env_indoor"
    OUTDOOR = "env_outdoor"
    ABSTRACT = "env_abstract"


# Valid theme values per environment — Unity team builds exactly these.
INDOOR_THEMES = {"lab", "classroom", "library"}
OUTDOOR_THEMES = {"field", "playground", "cricket_ground", "stadium"}
ABSTRACT_THEMES = {"dark_grid", "light_grid", "space"}

THEME_MAP: Dict[EnvironmentId, set] = {
    EnvironmentId.INDOOR: INDOOR_THEMES,
    EnvironmentId.OUTDOOR: OUTDOOR_THEMES,
    EnvironmentId.ABSTRACT: ABSTRACT_THEMES,
}


class TimeOfDay(str, Enum):
    DAY = "day"
    EVENING = "evening"
    NIGHT = "night"


class SceneSpec(BaseModel):
    environment_id: EnvironmentId
    theme: str
    time_of_day: TimeOfDay = TimeOfDay.DAY


# ──────────────────────────────────────────────────────────────────────────────
# Components
# ──────────────────────────────────────────────────────────────────────────────


class ComponentType(str, Enum):
    # Teacher & Display
    TEACHER_AVATAR = "teacher_avatar"
    WHITEBOARD = "whiteboard"
    LABEL_BUBBLE = "label_bubble"
    INFO_PANEL = "info_panel"
    FORMULA_DISPLAY = "formula_display"
    # Interactive Controls
    SLIDER_CONTROL = "slider_control"
    TOGGLE_SWITCH = "toggle_switch"
    BUTTON_ARRAY = "button_array"
    DIAL_PAD = "dial_pad"
    # Physics Visualizers
    TRAJECTORY_3D = "trajectory_3d"
    FORCE_VECTOR = "force_vector"
    OSCILLATOR = "oscillator"
    # Chemistry Visualizers
    MOLECULE_BUILDER = "molecule_builder"
    REACTION_STAGE = "reaction_stage"
    # Math Visualizers
    GRAPH_3D = "graph_3d"
    GEOMETRIC_SHAPE = "geometric_shape"
    # Quiz & Feedback
    QUIZ_POPUP = "quiz_popup"
    # Effects
    HIGHLIGHT_RING = "highlight_ring"
    ARROW_POINTER = "arrow_pointer"
    PARTICLE_EFFECT = "particle_effect"


# All valid anchor names Unity exposes in every environment.
VALID_ANCHORS: List[str] = (
    ["AnchorTeacher", "AnchorStudent", "AnchorWhiteboard", "AnchorStage"]
    + [f"AnchorPanel_{i}" for i in range(6)]
    + [f"AnchorInteract_{i}" for i in range(4)]
    + [f"AnchorLabel_{i}" for i in range(10)]
)


class ComponentInstance(BaseModel):
    component_id: str
    component_type: ComponentType
    anchor: str  # must be in VALID_ANCHORS
    config: Dict[str, Any]


# ──────────────────────────────────────────────────────────────────────────────
# State machine
# ──────────────────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    NARRATION = "narration"
    DEMO = "demo"
    INTERACTION = "interaction"
    QUIZ = "quiz"
    BRANCH = "branch"
    SUMMARY = "summary"
    WAIT = "wait"


class NarrationSpec(BaseModel):
    speaker_id: str = "teacher_main"
    text: str
    emotion: str = "friendly"
    gesture: str = "idle"
    gaze_target: Optional[str] = None


class ActionSpec(BaseModel):
    # Verb: spawn | despawn | play_animation | update_config | highlight | clear_highlights | move_camera
    type: str
    component_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class WaitFor(BaseModel):
    parameter_id: Optional[str] = None
    min_changes: Optional[int] = None
    timeout_seconds: Optional[float] = None


class Transition(BaseModel):
    to: str  # node_id or "END"
    condition: str = "always"


class StateMachineNode(BaseModel):
    node_id: str
    type: NodeType
    narration: Optional[NarrationSpec] = None
    actions: Optional[List[ActionSpec]] = None
    wait_for: Optional[WaitFor] = None
    # Quiz nodes inline their popup config here so Unity doesn't need a pre-declared component
    quiz_id: Optional[str] = None
    quiz_config: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[float] = None
    transitions: List[Transition]


class StateMachine(BaseModel):
    start_node_id: str
    nodes: List[StateMachineNode]


# ──────────────────────────────────────────────────────────────────────────────
# Student / lesson metadata
# ──────────────────────────────────────────────────────────────────────────────


class StudentSpec(BaseModel):
    id: str
    display_name: str
    learning_style: str = "visual"


class LessonSpec(BaseModel):
    topic_code: str
    topic_title: str
    estimated_duration_seconds: int = 480


class TelemetryConfig(BaseModel):
    gaze_targets: List[str] = Field(default_factory=list)
    gaze_sample_rate_hz: float = 1.0
    batch_interval_seconds: float = 2.0


# ──────────────────────────────────────────────────────────────────────────────
# Full manifest
# ──────────────────────────────────────────────────────────────────────────────


class LessonManifest(BaseModel):
    manifest_version: str = "1.0"
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student: StudentSpec
    lesson: LessonSpec
    scene: SceneSpec
    components: List[ComponentInstance]
    state_machine: StateMachine
    telemetry_config: TelemetryConfig = Field(default_factory=TelemetryConfig)


# ──────────────────────────────────────────────────────────────────────────────
# Patch operations (mid-lesson adaptation from telemetry)
# ──────────────────────────────────────────────────────────────────────────────


class PatchOp(str, Enum):
    ADD_NODE = "add_node"
    UPDATE_TRANSITION = "update_transition"
    UPDATE_COMPONENT = "update_component"
    DESPAWN_COMPONENT = "despawn_component"


class ManifestPatch(BaseModel):
    op: PatchOp
    # add_node
    node: Optional[Dict[str, Any]] = None
    # update_transition
    from_node: Optional[str] = None
    transition_index: Optional[int] = None
    to: Optional[str] = None
    # update_component / despawn_component
    component_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
