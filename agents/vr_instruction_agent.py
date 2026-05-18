"""
Agent E: Manifest Author Agent

Purpose:
    Given curriculum plan, pedagogy plan, and learner profile, author a
    LessonManifest JSON that Unity's state machine runtime renders directly.
    No C# generated at runtime. No ReAct loop. One structured LLM call.

Inputs:
    - CurriculumPlan from Agent C
    - PedagogyPlan from Agent D
    - LearnerProfile from Agent B (student name, learning_style, misconceptions)

Outputs:
    - LessonManifest: full JSON Unity consumes via WebSocket
    - ManifestPatch[]: real-time delta updates driven by student telemetry
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

from agents.base_agent import BaseAgent
from models.manifest import (
    VALID_ANCHORS,
    ComponentInstance,
    ComponentType,
    EnvironmentId,
    LessonManifest,
    LessonSpec,
    ManifestPatch,
    NarrationSpec,
    PatchOp,
    SceneSpec,
    StateMachine,
    StateMachineNode,
    StudentSpec,
    TelemetryConfig,
    TimeOfDay,
)
# Assessment instructions (VRInstruction JSON) for in-lesson MCQ panels —
# generation logic preserved from original Agent E.
from models.vr_contracts import (
    AssessmentCommand,
    AssessmentType,
    AvatarAction,
    AvatarActionType,
    InputMode,
    VoiceCommand,
    VoiceEmotion,
    VRInstruction,
)

logger = logging.getLogger(__name__)

_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", "scene_registry.json")


def _load_registry() -> Dict[str, Any]:
    try:
        with open(_REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_REGISTRY = _load_registry()

_COMPONENT_TYPES = list(ComponentType)
_ENVIRONMENT_IDS = [e.value for e in EnvironmentId]


class VRInstructionAgent(BaseAgent):
    """
    Agent E: Lesson Manifest Author.

    Replaces the old agentAR C# ReAct loop.  One LLM call produces a complete
    LessonManifest; a second lightweight call produces ManifestPatch[] when
    Unity reports student telemetry.

    Public API:
        author_manifest_stream()   — streams scene_preload → manifest events
        patch_from_telemetry()     — returns patches for mid-lesson adaptation
        generate_assessment_instructions()  — unchanged, still used by MCQ panels
    """

    def __init__(self, temperature: float = 0.4):
        super().__init__(temperature=temperature)
        # session_id → LessonManifest (for telemetry patching)
        self._sessions: Dict[str, LessonManifest] = {}

    # =========================================================================
    # process() dispatcher — preserved signature for orchestrator compat
    # =========================================================================

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        action = input_data.get("action")
        if action == "author_manifest":
            manifest = await self.author_manifest(
                session_id=input_data["session_id"],
                student_id=input_data["student_id"],
                student_name=input_data.get("student_name", "Student"),
                curriculum_plan=input_data["curriculum_plan"],
                pedagogy_plan=input_data["pedagogy_plan"],
                learner_profile=input_data.get("learner_profile", {}),
            )
            return manifest.model_dump()
        elif action == "generate_assessment":
            return self.generate_assessment_instructions(
                questions=input_data["questions"],
                assessment_type=input_data.get("assessment_type", "concept_check"),
            )
        raise ValueError(f"Unknown action: {action}")

    # =========================================================================
    # author_manifest — the core method
    # =========================================================================

    async def author_manifest(
        self,
        session_id: str,
        student_id: str,
        student_name: str,
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
        learner_profile: Dict[str, Any],
    ) -> LessonManifest:
        """
        Single LLM call → full LessonManifest.

        Validates anchors and component types before returning.  Falls back
        to a minimal safe manifest on parse failure.
        """
        prompt = self._build_manifest_prompt(
            session_id=session_id,
            student_id=student_id,
            student_name=student_name,
            curriculum_plan=curriculum_plan,
            pedagogy_plan=pedagogy_plan,
            learner_profile=learner_profile,
        )

        raw = await self._invoke_llm_json(prompt)
        manifest = self._coerce_manifest(
            raw=raw,
            session_id=session_id,
            student_id=student_id,
            student_name=student_name,
            curriculum_plan=curriculum_plan,
            learner_profile=learner_profile,
        )
        self._sessions[session_id] = manifest
        return manifest

    # =========================================================================
    # author_manifest_stream — streaming wrapper for orchestrator
    # =========================================================================

    async def author_manifest_stream(
        self,
        session_id: str,
        student_id: str,
        student_name: str,
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
        learner_profile: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yields two events:
          1. scene_preload  — within ~0ms (no LLM, just registry lookup)
                             Unity loads the scene + shows teacher greeting
          2. manifest       — after the LLM call completes (~3-6s)
                             Unity starts walking the state machine
        """
        topic_code = curriculum_plan.get("topic_code", "")
        subject_prefix = topic_code.split("_")[0] if "_" in topic_code else "PHY"
        env_hint = _REGISTRY.get("topic_environment_hints", {}).get(subject_prefix, {})
        overrides = env_hint.get("overrides", {}).get(topic_code, {})
        preload_env = overrides.get("environment") or env_hint.get(
            "default_environment", "env_indoor"
        )
        preload_theme = overrides.get("theme") or env_hint.get("default_theme", "lab")

        yield {
            "event": "scene_preload",
            "session_id": session_id,
            "environment_id": preload_env,
            "theme": preload_theme,
            "teacher_greeting": f"Hi {student_name}, getting your lesson ready...",
        }

        yield {"event": "progress", "step": "Authoring lesson manifest...", "progress": 60}

        manifest = await self.author_manifest(
            session_id=session_id,
            student_id=student_id,
            student_name=student_name,
            curriculum_plan=curriculum_plan,
            pedagogy_plan=pedagogy_plan,
            learner_profile=learner_profile,
        )

        yield {
            "event": "manifest",
            "session_id": session_id,
            "manifest": manifest.model_dump(),
        }

    # =========================================================================
    # patch_from_telemetry — mid-lesson adaptation
    # =========================================================================

    async def patch_from_telemetry(
        self,
        session_id: str,
        telemetry_events: List[Dict[str, Any]],
    ) -> List[ManifestPatch]:
        """
        Receives batched telemetry events from Unity, returns manifest patches.

        Lightweight Haiku call (<2s).  Returns [] if no adaptation is needed.
        """
        manifest = self._sessions.get(session_id)
        if not manifest:
            return []

        summary = self._summarise_telemetry(telemetry_events)
        if not summary.get("needs_adaptation"):
            return []

        prompt = self._build_patch_prompt(manifest=manifest, telemetry_summary=summary)
        raw = await self._invoke_llm_json(prompt)

        patches = []
        for p in raw.get("patches", []):
            try:
                patches.append(ManifestPatch(**p))
            except Exception:
                continue
        return patches

    # =========================================================================
    # Internal: prompt builders
    # =========================================================================

    def _build_manifest_prompt(
        self,
        session_id: str,
        student_id: str,
        student_name: str,
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
        learner_profile: Dict[str, Any],
    ) -> str:
        topic_name = curriculum_plan.get("topic_name", curriculum_plan.get("topic_code", ""))
        topic_code = curriculum_plan.get("topic_code", "")
        subject_code = curriculum_plan.get("subject_code", "")
        subtopics = curriculum_plan.get("subtopics", [])
        duration_min = curriculum_plan.get("estimated_duration_minutes", 8)

        learning_style = learner_profile.get("learning_style", "visual")
        misconceptions = learner_profile.get("misconceptions", [])
        analogy = pedagogy_plan.get("analogy", "")
        approach = pedagogy_plan.get("approach", "intuition-first")

        valid_component_types = [c.value for c in ComponentType]
        hint = _REGISTRY.get("topic_environment_hints", {}).get(
            subject_code.upper(), {}
        )
        env_hint_str = json.dumps(hint, indent=2)

        return f"""You are Agent E — the Lesson Manifest Author for a VR STEM education system.

Your job is to produce a complete LessonManifest JSON for a Class 10 student. Unity will render this directly — you are the content author, Unity is the renderer.

## Student
- ID: {student_id}
- Name: {student_name}
- Learning style: {learning_style}
- Known misconceptions: {misconceptions if misconceptions else "none"}

## Lesson
- Topic: {topic_name} (code: {topic_code})
- Subject: {subject_code}
- Subtopics: {subtopics}
- Duration: {duration_min} minutes (~{duration_min * 60} seconds)
- Teaching analogy: {analogy}
- Approach: {approach}

## Environment hints from registry
{env_hint_str}

## Valid component types (use ONLY these exact strings)
{valid_component_types}

## Valid anchor names (use ONLY these exact strings)
{VALID_ANCHORS}

## Rules
1. Every component_id you invent must be unique within this manifest.
2. Every anchor you use must be from the valid list above.
3. Every component_type must be from the valid list above.
4. State machine must start at start_node_id and every node must have at least one transition.
5. The final node must have a transition to "END".
6. At least one quiz_popup node must be present.
7. teacher_avatar must be in the components list with component_id "teacher_main" at anchor "AnchorTeacher".
8. Narration text must be warm, simple, and student-friendly (age ~15).
9. If the student has misconceptions, add a remediation node that corrects them.
10. telemetry_config.gaze_targets must list the component_ids of the main visualizer components.

## Mandatory lesson structure (state machine nodes in order)
intro → demo (spawns main visualizer) → interaction (spawns slider/toggle) → quiz → summary → END

You may add remediation nodes between quiz and summary if misconceptions are known.

## Output format
Return ONLY the JSON manifest — no extra text, no markdown fences.

Schema:
{{
  "manifest_version": "1.0",
  "session_id": "{session_id}",
  "student": {{
    "id": "{student_id}",
    "display_name": "{student_name}",
    "learning_style": "{learning_style}"
  }},
  "lesson": {{
    "topic_code": "{topic_code}",
    "topic_title": "{topic_name}",
    "estimated_duration_seconds": {duration_min * 60}
  }},
  "scene": {{
    "environment_id": "<one of: env_indoor | env_outdoor | env_abstract>",
    "theme": "<valid theme for chosen environment>",
    "time_of_day": "day"
  }},
  "components": [
    {{
      "component_id": "teacher_main",
      "component_type": "teacher_avatar",
      "anchor": "AnchorTeacher",
      "config": {{"character": "teacher", "gesture": "idle"}}
    }},
    ... more components
  ],
  "state_machine": {{
    "start_node_id": "intro",
    "nodes": [
      {{
        "node_id": "intro",
        "type": "narration",
        "narration": {{
          "speaker_id": "teacher_main",
          "text": "...",
          "emotion": "friendly",
          "gesture": "wave"
        }},
        "duration_seconds": 6,
        "transitions": [{{"to": "demo", "condition": "always"}}]
      }},
      ... more nodes
    ]
  }},
  "telemetry_config": {{
    "gaze_targets": ["<component_ids of main visualizers>"],
    "gaze_sample_rate_hz": 1.0,
    "batch_interval_seconds": 2.0
  }}
}}"""

    def _build_patch_prompt(
        self,
        manifest: LessonManifest,
        telemetry_summary: Dict[str, Any],
    ) -> str:
        current_nodes = [
            {"node_id": n.node_id, "type": n.type}
            for n in manifest.state_machine.nodes
        ]
        return f"""You are Agent E adapting a live VR lesson based on student behavior.

## Current state machine nodes
{json.dumps(current_nodes, indent=2)}

## Telemetry summary
{json.dumps(telemetry_summary, indent=2)}

## Your task
Return a JSON object with a "patches" array. Each patch has an "op" field:
- "add_node": add a new node. Include "node" (full node object).
- "update_transition": redirect a transition. Include "from_node", "transition_index", "to".
- "update_component": update a component's config. Include "component_id", "config".
- "despawn_component": remove a component. Include "component_id".

If no adaptation is needed, return {{"patches": []}}.

Return ONLY the JSON object."""

    # =========================================================================
    # Internal: coerce raw LLM output → LessonManifest with validation
    # =========================================================================

    def _coerce_manifest(
        self,
        raw: Dict[str, Any],
        session_id: str,
        student_id: str,
        student_name: str,
        curriculum_plan: Dict[str, Any],
        learner_profile: Dict[str, Any],
    ) -> LessonManifest:
        """
        Attempt to parse the LLM output into a LessonManifest.
        Fixes common issues (invalid anchors, invalid component types) in place.
        Falls back to a minimal manifest on unrecoverable failure.
        """
        try:
            raw["session_id"] = session_id

            # Fix invalid anchors
            for comp in raw.get("components", []):
                if comp.get("anchor") not in VALID_ANCHORS:
                    comp["anchor"] = "AnchorPanel_0"
                if comp.get("component_type") not in [c.value for c in ComponentType]:
                    comp["component_type"] = "info_panel"

            return LessonManifest(**raw)
        except Exception as e:
            logger.warning("Manifest parse failed (%s), using fallback.", e)
            return self._fallback_manifest(
                session_id=session_id,
                student_id=student_id,
                student_name=student_name,
                curriculum_plan=curriculum_plan,
                learner_profile=learner_profile,
            )

    def _fallback_manifest(
        self,
        session_id: str,
        student_id: str,
        student_name: str,
        curriculum_plan: Dict[str, Any],
        learner_profile: Dict[str, Any],
    ) -> LessonManifest:
        """Minimal valid manifest used when LLM output is unrecoverable."""
        topic_name = curriculum_plan.get("topic_name", curriculum_plan.get("topic_code", "This Topic"))
        topic_code = curriculum_plan.get("topic_code", "UNKNOWN")
        learning_style = learner_profile.get("learning_style", "visual")

        return LessonManifest(
            session_id=session_id,
            student=StudentSpec(id=student_id, display_name=student_name, learning_style=learning_style),
            lesson=LessonSpec(
                topic_code=topic_code,
                topic_title=topic_name,
                estimated_duration_seconds=480,
            ),
            scene=SceneSpec(environment_id=EnvironmentId.INDOOR, theme="classroom"),
            components=[
                ComponentInstance(
                    component_id="teacher_main",
                    component_type=ComponentType.TEACHER_AVATAR,
                    anchor="AnchorTeacher",
                    config={"character": "teacher", "gesture": "idle"},
                ),
                ComponentInstance(
                    component_id="main_whiteboard",
                    component_type=ComponentType.WHITEBOARD,
                    anchor="AnchorWhiteboard",
                    config={"title": topic_name, "body_text": "Let's explore this topic together."},
                ),
            ],
            state_machine=StateMachine(
                start_node_id="intro",
                nodes=[
                    StateMachineNode(
                        node_id="intro",
                        type="narration",
                        narration=NarrationSpec(
                            speaker_id="teacher_main",
                            text=f"Welcome {student_name}! Today we're learning about {topic_name}. Let's get started.",
                            emotion="friendly",
                            gesture="wave",
                        ),
                        duration_seconds=6,
                        transitions=[{"to": "summary", "condition": "always"}],
                    ),
                    StateMachineNode(
                        node_id="summary",
                        type="summary",
                        narration=NarrationSpec(
                            speaker_id="teacher_main",
                            text=f"Great work today, {student_name}! You've taken the first step with {topic_name}.",
                            emotion="friendly",
                            gesture="celebrate",
                        ),
                        transitions=[{"to": "END", "condition": "always"}],
                    ),
                ],
            ),
            telemetry_config=TelemetryConfig(gaze_targets=["main_whiteboard"]),
        )

    # =========================================================================
    # Internal: telemetry summariser (no LLM — rule-based)
    # =========================================================================

    def _summarise_telemetry(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert raw telemetry events into a summary that drives patch decisions.
        Pure Python — no LLM cost.
        """
        quiz_wrong = any(
            e.get("type") == "quiz_attempt" and not e.get("data", {}).get("correct")
            for e in events
        )
        idle_duration = sum(
            e.get("data", {}).get("duration_ms", 0)
            for e in events
            if e.get("type") == "idle"
        )
        replay_requests = sum(1 for e in events if e.get("type") == "replay_request")
        low_engagement = idle_duration > 20_000 or replay_requests >= 2

        needs_adaptation = quiz_wrong or low_engagement

        return {
            "needs_adaptation": needs_adaptation,
            "quiz_wrong": quiz_wrong,
            "low_engagement": low_engagement,
            "idle_duration_ms": idle_duration,
            "replay_requests": replay_requests,
            "raw_event_count": len(events),
        }

    # =========================================================================
    # generate_assessment_instructions — unchanged from original Agent E
    # =========================================================================

    def generate_assessment_instructions(
        self,
        questions: List[Dict[str, Any]],
        assessment_type: str = "concept_check",
    ) -> Dict[str, Any]:
        """Generate VR instructions for in-lesson MCQ assessments."""
        type_map = {
            "concept_check": AssessmentType.CONCEPT_CHECK,
            "mcq": AssessmentType.MCQ,
            "descriptive": AssessmentType.DESCRIPTIVE,
        }

        instructions = []

        instructions.append(
            VRInstruction(
                step_id="assess_intro",
                sequence_order=0,
                avatar=AvatarAction(action=AvatarActionType.QUESTION),
                voice=VoiceCommand(
                    text="Let's check your understanding! Answer these questions.",
                    emotion=VoiceEmotion.ENCOURAGING,
                ),
            ).model_dump()
        )

        for i, q in enumerate(questions):
            instructions.append(
                VRInstruction(
                    step_id=f"assess_q{i + 1}",
                    sequence_order=i + 1,
                    avatar=AvatarAction(action=AvatarActionType.QUESTION),
                    voice=VoiceCommand(
                        text=q.get("question_text", ""),
                        emotion=VoiceEmotion.CALM,
                    ),
                    assessment=AssessmentCommand(
                        type=type_map.get(assessment_type, AssessmentType.MCQ),
                        question_id=q.get("question_id", f"q{i + 1}"),
                        question=q.get("question_text", ""),
                        options=q.get("options"),
                        input_mode=(
                            InputMode.GAZE
                            if q.get("question_type") == "mcq"
                            else InputMode.VOICE
                        ),
                        time_limit_seconds=q.get("time_limit", 60),
                    ),
                ).model_dump()
            )

        instructions.append(
            VRInstruction(
                step_id="assess_done",
                sequence_order=len(questions) + 1,
                avatar=AvatarAction(action=AvatarActionType.CELEBRATE),
                voice=VoiceCommand(
                    text="Great job! Let's see how you did.",
                    emotion=VoiceEmotion.ENCOURAGING,
                ),
            ).model_dump()
        )

        return {
            "assessment_type": assessment_type,
            "total_questions": len(questions),
            "instructions": instructions,
        }
