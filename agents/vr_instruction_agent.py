"""
Agent E: VR Instruction Agent (agentAR-style autonomous C# script generator)

Purpose:
    Convert pedagogy and curriculum plans into actual Unity C# MonoBehaviour
    scripts using an autonomous ReAct (Reason + Act) loop inspired by the
    agentAR paper ("Creating Augmented Reality Applications with Tool-Augmented
    LLM-based Autonomous Agents").

Inputs:
    - CurriculumPlan from Agent C
    - PedagogyPlan from Agent D
    - FullScenePlan (with asset_bindings) from Agent G

Outputs:
    - UnityScriptPackage: a bundle of C# scripts Unity compiles and runs
    - Assessment instructions (VRInstruction JSON, unchanged) for MCQ panels

ReAct loop per lesson:
    THINK → ACT (generate_csharp_script)
          → OBSERVE (validate_csharp_syntax)
          → OBSERVE (review_script_pedagogically)
          → [patch if needed]
          → repeat until done
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from agents.base_agent import BaseAgent
from agents.vr_tools import VRToolRegistry
from models.vr_contracts import (
    # Assessment-only contracts (unchanged)
    AssessmentCommand,
    AssessmentType,
    AvatarAction,
    AvatarActionType,
    InputMode,
    VoiceCommand,
    VoiceEmotion,
    VRInstruction,
    # New C# script contracts (used by type hints / return annotation)
    UnityScriptPackage,
)


# ---------------------------------------------------------------------------
# Expected lesson flow: step_type sequence the _think() LLM should follow
# ---------------------------------------------------------------------------
_LESSON_FLOW = [
    ("session_manager", "Orchestrates all lesson steps in sequence"),
    ("intro", "Welcome student and orient them in the scene"),
    ("demonstration", "Visually demonstrate the core concept"),
    ("interaction", "Student manipulates a parameter and observes the result"),
    ("assessment", "Quick in-lesson knowledge check (MCQ panel)"),
    ("summary", "Recap key visuals and fire LessonComplete event"),
]


class VRInstructionAgent(BaseAgent):
    """
    Agent E: VR Instruction Agent — agentAR-style autonomous C# generator.

    Operates a ReAct loop:
      1. THINK  — LLM decides which C# script to generate next
      2. ACT    — tools.generate_csharp_script()
      3. OBSERVE — tools.validate_csharp_syntax()  [regex, no LLM]
                 — tools.patch_csharp_script() if errors (up to max_patch_retries)
      4. OBSERVE — tools.review_script_pedagogically() [LLM]
                 — tools.patch_csharp_script() if score < 7
      5. Repeat until done or max_iterations reached
      6. tools.assemble_unity_package() → UnityScriptPackage

    Assessment panels (MCQ/descriptive) still use the original VRInstruction
    JSON format via generate_assessment_instructions() — that method is unchanged.
    """

    def __init__(self, temperature: float = 0.3):
        super().__init__(temperature=temperature)
        self.tools = VRToolRegistry(self.llm)
        # In-memory store: session_id → {"scripts": [...], "plans": {...}}
        # Used by apply_unity_feedback() when Unity reports compile errors.
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self.max_iterations: int = 20
        self.max_patch_retries: int = 3
        self.min_pedagogy_score: int = 7

    def _build_system_prompt(self) -> str:
        return (
            "You are Agent E — the VR Instruction Agent for an AI-driven educational "
            "VR system targeting Class 10 students (age ~15). Your job is to plan and "
            "generate Unity C# MonoBehaviour scripts that implement an interactive "
            "lesson inside a VR scene. You think step-by-step about what each script "
            "needs to do, then direct the tool registry to generate it."
        )

    # =========================================================================
    # process() dispatcher
    # =========================================================================

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatcher for Agent E actions.

        Actions:
          'create_session'    → create_session()
          'generate_lesson'   → generate_lesson_instructions()   [ReAct loop]
          'generate_assessment' → generate_assessment_instructions()  [unchanged]
        """
        action = input_data.get("action")

        if action == "create_session":
            return await self.create_session(
                student_id=input_data["student_id"],
                curriculum_plan=input_data["curriculum_plan"],
                pedagogy_plan=input_data["pedagogy_plan"],
                scene_plan=input_data.get("scene_plan", {}),
            )
        elif action == "generate_lesson":
            return await self.generate_lesson_instructions(
                curriculum_plan=input_data["curriculum_plan"],
                pedagogy_plan=input_data["pedagogy_plan"],
                scene_plan=input_data.get("scene_plan", {}),
            )
        elif action == "generate_assessment":
            return self.generate_assessment_instructions(
                questions=input_data["questions"],
                assessment_type=input_data.get("assessment_type", "concept_check"),
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    # =========================================================================
    # create_session  (thin wrapper, kept for backward compatibility)
    # =========================================================================

    async def create_session(
        self,
        student_id: str,
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
        scene_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new VR teaching session and return a UnityScriptPackage.
        """
        session_id = str(uuid.uuid4())
        curriculum_plan = {**curriculum_plan, "session_id": session_id}
        package = await self.generate_lesson_instructions(
            curriculum_plan=curriculum_plan,
            pedagogy_plan=pedagogy_plan,
            scene_plan=scene_plan or {},
        )
        # Inject student_id (generate_lesson_instructions may not have it)
        package["student_id"] = student_id
        return package

    # =========================================================================
    # generate_lesson_instructions — the agentAR ReAct loop
    # =========================================================================

    async def generate_lesson_instructions(
        self,
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
        scene_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Autonomous ReAct loop that generates one C# script per lesson step.

        Returns a UnityScriptPackage dict ready for SSE streaming to Unity.
        """
        session_id = curriculum_plan.get("session_id", str(uuid.uuid4()))
        topic = curriculum_plan.get("topic_name") or curriculum_plan.get(
            "topic_code", "unknown"
        )
        subject = curriculum_plan.get("subject_code", "unknown")
        topic_code = curriculum_plan.get("topic_code", "unknown")
        estimated_minutes = curriculum_plan.get("estimated_duration_minutes", 30)
        asset_bindings: Dict[str, str] = scene_plan.get("asset_bindings", {})

        generated_scripts: List[Dict[str, Any]] = []
        iteration = 0

        while iteration < self.max_iterations:
            # ── THINK ────────────────────────────────────────────────────────
            action = await self._think(
                generated_so_far=generated_scripts,
                curriculum_plan=curriculum_plan,
                pedagogy_plan=pedagogy_plan,
                scene_plan=scene_plan,
            )

            if action.get("done"):
                break

            class_name = action["class_name"]
            step_type = action["step_type"]
            description = action["description"]
            learning_objective = action["learning_objective"]
            attach_to = action.get("attach_to", "TeachingManager")
            is_manager = step_type == "session_manager"

            # ── ACT: generate script ─────────────────────────────────────────
            code = await self.tools.generate_csharp_script(
                class_name=class_name,
                description=description,
                step_type=step_type,
                learning_objective=learning_objective,
                attach_to=attach_to,
                scene_context=scene_plan,
                pedagogy_context=pedagogy_plan,
                topic=topic,
                asset_bindings=asset_bindings,
                is_session_manager=is_manager,
            )

            # ── OBSERVE: syntax validation (regex) ───────────────────────────
            validation = self.tools.validate_csharp_syntax(code)
            if not validation["valid"]:
                for _attempt in range(self.max_patch_retries):
                    code = await self.tools.patch_csharp_script(
                        code=code,
                        errors=validation["errors"],
                        instruction="Fix all syntax and structural errors listed above.",
                    )
                    validation = self.tools.validate_csharp_syntax(code)
                    if validation["valid"]:
                        break

            # ── OBSERVE: pedagogical review (LLM) — skip for manager ─────────
            pedagogy_score = 10  # default for session_manager
            if not is_manager:
                review = await self.tools.review_script_pedagogically(
                    code=code,
                    learning_objective=learning_objective,
                    topic_code=topic_code,
                )
                pedagogy_score = review.get("score", 5)
                if pedagogy_score < self.min_pedagogy_score and review.get("issues"):
                    suggestions = review.get("suggestions", [])
                    patch_instruction = (
                        f"Improve pedagogical quality to better teach: {learning_objective}. "
                        f"Suggestions: {'; '.join(suggestions)}"
                    )
                    code = await self.tools.patch_csharp_script(
                        code=code,
                        errors=review["issues"],
                        instruction=patch_instruction,
                    )
                    # Re-validate after pedagogical patch
                    validation = self.tools.validate_csharp_syntax(code)

            generated_scripts.append(
                {
                    "filename": f"{class_name}.cs",
                    "class_name": class_name,
                    "code": code,
                    "attach_to": attach_to,
                    "step_type": step_type,
                    "learning_objective": learning_objective,
                    "dependencies": action.get("dependencies", []),
                    "validation_passed": validation["valid"],
                    "pedagogy_score": pedagogy_score,
                }
            )

            iteration += 1

        # ── Assemble final package ────────────────────────────────────────────
        package = self.tools.assemble_unity_package(
            scripts=generated_scripts,
            scene_manifest=scene_plan,
            session_id=session_id,
            student_id=curriculum_plan.get("student_id", ""),
            topic=topic,
            subject=subject,
            estimated_minutes=estimated_minutes,
        )

        # Store in memory for apply_unity_feedback()
        self._sessions[session_id] = {
            "scripts": {s["filename"]: s for s in generated_scripts},
            "curriculum_plan": curriculum_plan,
            "pedagogy_plan": pedagogy_plan,
            "scene_plan": scene_plan,
        }

        return package

    # =========================================================================
    # generate_lesson_instructions_stream — token-by-token streaming ReAct loop
    # =========================================================================

    async def generate_lesson_instructions_stream(
        self,
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
        scene_plan: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming version of the ReAct loop.

        Yields SSE-ready event dicts as each script is generated token by token,
        instead of blocking until all scripts are complete.

        Event sequence per script:
            csharp_thinking        — THINK decision (atomic, JSON)
            csharp_script_start    — generation about to start
            csharp_script_token    — one token from the LLM
            [csharp_patch_start    — only if syntax validation fails]
            [csharp_patch_token    — patch tokens]
            [csharp_patch_complete — patch result]
            progress               — "Reviewing <ClassName>..." (before review)
            csharp_review          — pedagogical score (atomic)
            [csharp_patch_start/token/complete — only if score < min_pedagogy_score]
            csharp_script_complete — full script data including code

        Final internal event (consumed by orchestrator, not forwarded to client):
            __package__            — the assembled UnityScriptPackage dict
        """
        session_id = curriculum_plan.get("session_id", str(uuid.uuid4()))
        topic = curriculum_plan.get("topic_name") or curriculum_plan.get(
            "topic_code", "unknown"
        )
        subject = curriculum_plan.get("subject_code", "unknown")
        topic_code = curriculum_plan.get("topic_code", "unknown")
        estimated_minutes = curriculum_plan.get("estimated_duration_minutes", 30)
        asset_bindings: Dict[str, str] = scene_plan.get("asset_bindings", {})
        generated_scripts: List[Dict[str, Any]] = []
        iteration = 0

        while iteration < self.max_iterations:
            # ── THINK (atomic LLM call — short JSON decision, not streamed) ──
            action = await self._think(
                generated_so_far=generated_scripts,
                curriculum_plan=curriculum_plan,
                pedagogy_plan=pedagogy_plan,
                scene_plan=scene_plan,
            )
            if action.get("done"):
                break

            class_name = action["class_name"]
            step_type = action["step_type"]
            description = action["description"]
            learning_objective = action["learning_objective"]
            attach_to = action.get("attach_to", "TeachingManager")
            is_manager = step_type == "session_manager"
            script_id = f"script_{iteration}"

            # Announce THINK decision so client knows what is being generated next
            yield {
                "event": "csharp_thinking",
                "data": {
                    "script_index": iteration,
                    "class_name": class_name,
                    "step_type": step_type,
                    "learning_objective": learning_objective,
                    "attach_to": attach_to,
                },
            }

            # ── ACT: stream script generation tokens ─────────────────────────
            yield {
                "event": "csharp_script_start",
                "id": script_id,
                "meta": {
                    "class_name": class_name,
                    "filename": f"{class_name}.cs",
                    "step_type": step_type,
                    "index": iteration,
                },
            }

            full_code = ""
            async for item in self.tools.generate_csharp_script_stream(
                class_name=class_name,
                description=description,
                step_type=step_type,
                learning_objective=learning_objective,
                attach_to=attach_to,
                scene_context=scene_plan,
                pedagogy_context=pedagogy_plan,
                topic=topic,
                asset_bindings=asset_bindings,
                is_session_manager=is_manager,
            ):
                if isinstance(item, dict) and item.get("__done__"):
                    full_code = item["code"]
                else:
                    token_str = str(item)
                    full_code += token_str
                    yield {
                        "event": "csharp_script_token",
                        "id": script_id,
                        "token": token_str,
                    }

            # ── OBSERVE: syntax validation (regex, instant) ──────────────────
            validation = self.tools.validate_csharp_syntax(full_code)

            for attempt in range(self.max_patch_retries):
                if validation["valid"]:
                    break
                patch_id = f"patch_{script_id}_a{attempt}"
                yield {
                    "event": "csharp_patch_start",
                    "id": patch_id,
                    "meta": {
                        "errors": validation["errors"],
                        "warnings": validation["warnings"],
                        "attempt": attempt + 1,
                    },
                }
                patched_code = ""
                async for item in self.tools.patch_csharp_script_stream(
                    code=full_code,
                    errors=validation["errors"],
                    instruction="Fix all syntax and structural errors listed above.",
                ):
                    if isinstance(item, dict) and item.get("__done__"):
                        patched_code = item["code"]
                    else:
                        token_str = str(item)
                        patched_code += token_str
                        yield {
                            "event": "csharp_patch_token",
                            "id": patch_id,
                            "token": token_str,
                        }
                full_code = patched_code
                validation = self.tools.validate_csharp_syntax(full_code)
                yield {
                    "event": "csharp_patch_complete",
                    "id": patch_id,
                    "data": {
                        "valid": validation["valid"],
                        "errors_remaining": validation["errors"],
                    },
                }

            # ── OBSERVE: pedagogical review (atomic LLM call — returns JSON) ─
            pedagogy_score = 10  # default for session_manager
            if not is_manager:
                yield {
                    "event": "progress",
                    "step": f"Reviewing {class_name} for pedagogical quality...",
                    "progress": -1,  # -1 = indeterminate
                }
                review = await self.tools.review_script_pedagogically(
                    code=full_code,
                    learning_objective=learning_objective,
                    topic_code=topic_code,
                )
                pedagogy_score = review.get("score", 5)
                yield {
                    "event": "csharp_review",
                    "id": script_id,
                    "data": {
                        "score": pedagogy_score,
                        "issues": review.get("issues", []),
                        "suggestions": review.get("suggestions", []),
                    },
                }
                # If score too low, stream a pedagogical patch
                if pedagogy_score < self.min_pedagogy_score and review.get("issues"):
                    suggestions = review.get("suggestions", [])
                    patch_id = f"patch_{script_id}_pedagogy"
                    patch_instr = (
                        f"Improve pedagogical quality to better teach: {learning_objective}. "
                        f"Suggestions: {'; '.join(suggestions)}"
                    )
                    yield {
                        "event": "csharp_patch_start",
                        "id": patch_id,
                        "meta": {"errors": review["issues"], "type": "pedagogy"},
                    }
                    patched_code = ""
                    async for item in self.tools.patch_csharp_script_stream(
                        code=full_code,
                        errors=review["issues"],
                        instruction=patch_instr,
                    ):
                        if isinstance(item, dict) and item.get("__done__"):
                            patched_code = item["code"]
                        else:
                            token_str = str(item)
                            patched_code += token_str
                            yield {
                                "event": "csharp_patch_token",
                                "id": patch_id,
                                "token": token_str,
                            }
                    full_code = patched_code
                    validation = self.tools.validate_csharp_syntax(full_code)
                    yield {
                        "event": "csharp_patch_complete",
                        "id": patch_id,
                        "data": {"valid": validation["valid"], "type": "pedagogy"},
                    }

            # ── Script complete — emit full data ─────────────────────────────
            script_entry = {
                "filename": f"{class_name}.cs",
                "class_name": class_name,
                "code": full_code,
                "attach_to": attach_to,
                "step_type": step_type,
                "learning_objective": learning_objective,
                "dependencies": action.get("dependencies", []),
                "validation_passed": validation["valid"],
                "pedagogy_score": pedagogy_score,
            }
            generated_scripts.append(script_entry)
            yield {
                "event": "csharp_script_complete",
                "id": script_id,
                "data": script_entry,  # includes full .code
            }

            iteration += 1

        # ── Assemble package and store for apply_unity_feedback() ────────────
        package = self.tools.assemble_unity_package(
            scripts=generated_scripts,
            scene_manifest=scene_plan,
            session_id=session_id,
            student_id=curriculum_plan.get("student_id", ""),
            topic=topic,
            subject=subject,
            estimated_minutes=estimated_minutes,
        )
        self._sessions[session_id] = {
            "scripts": {s["filename"]: s for s in generated_scripts},
            "curriculum_plan": curriculum_plan,
            "pedagogy_plan": pedagogy_plan,
            "scene_plan": scene_plan,
        }
        # Internal sentinel consumed by the orchestrator — not forwarded to client
        yield {"event": "__package__", "data": package}

    # =========================================================================
    # _think — reasoning step: decide next script to generate
    # =========================================================================

    async def _think(
        self,
        generated_so_far: List[Dict[str, Any]],
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
        scene_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        THINK step: ask the LLM which C# script to generate next.

        Returns a dict describing the next action, or {"done": True} when
        all required scripts have been generated.
        """
        topic = curriculum_plan.get("topic_name") or curriculum_plan.get(
            "topic_code", "unknown"
        )
        subject = curriculum_plan.get("subject_code", "").upper()
        subtopics = curriculum_plan.get("subtopics", [])
        analogy = pedagogy_plan.get("analogy", "real-world examples")
        approach = pedagogy_plan.get("approach", "intuition-first")
        asset_ids = list(scene_plan.get("asset_bindings", {}).keys())[:10]

        done_steps = [
            {"class_name": s["class_name"], "step_type": s["step_type"]}
            for s in generated_so_far
        ]
        done_types = {s["step_type"] for s in generated_so_far}

        # Build the expected flow list with done markers
        flow_status = []
        for stype, sdesc in _LESSON_FLOW:
            status = "DONE" if stype in done_types else "PENDING"
            flow_status.append(f"  [{status}] {stype}: {sdesc}")
        flow_str = "\n".join(flow_status)

        prompt = f"""{self._build_system_prompt()}

## Lesson Planning — THINK step

You are planning a VR lesson for Class 10 {subject} on the topic: "{topic}".

Teaching analogy : {analogy}
Teaching approach: {approach}
Subtopics        : {subtopics}
Available assets : {asset_ids}

## Required lesson flow (6 scripts total):
{flow_str}

## Scripts generated so far ({len(generated_so_far)}/6):
{done_steps if done_steps else "None yet"}

## Your task:
Decide which script to generate NEXT based on the flow above.
If all 6 step types are marked DONE, return {{"done": true}}.
Otherwise, return a JSON object describing the next script:

{{
  "done": false,
  "class_name": "ExactClassName",
  "step_type": "one of: session_manager|intro|demonstration|interaction|assessment|summary",
  "description": "2-3 sentence description of what this script does",
  "learning_objective": "What the student learns from this script",
  "attach_to": "GameObjectName",
  "dependencies": ["OtherClassName"]
}}

Rules for class_name:
- Use PascalCase
- SessionManager script: "{topic.replace(" ", "")}SessionManager"
- Other scripts: descriptive name ending in Controller, Demo, Step, or Handler
- No spaces, no special characters

Return ONLY the JSON object, no additional text."""

        result = await self._invoke_llm_json(prompt)
        return result

    # =========================================================================
    # apply_unity_feedback — called by /vr/script-feedback endpoint
    # =========================================================================

    async def apply_unity_feedback(
        self,
        session_id: str,
        script_filename: str,
        errors: List[str],
    ) -> Dict[str, Any]:
        """
        Unity reported compilation errors for a generated script.
        Patch the script and return the corrected version.

        Args:
            session_id:      The session that generated this script.
            script_filename: e.g. "ProjectileMotionController.cs"
            errors:          List of compiler error strings from Unity.

        Returns:
            {"filename": str, "code": str}  — the patched script.

        Raises:
            KeyError: if session_id or script_filename not found.
        """
        session = self._sessions[session_id]  # raises KeyError if absent
        script_entry = session["scripts"][script_filename]  # raises KeyError if absent

        patched_code = await self.tools.patch_csharp_script(
            code=script_entry["code"],
            errors=errors,
            instruction="Fix Unity compilation errors reported by the Unity Editor compiler.",
        )

        # Re-validate and store updated code
        validation = self.tools.validate_csharp_syntax(patched_code)
        script_entry["code"] = patched_code
        script_entry["validation_passed"] = validation["valid"]

        return {"filename": script_filename, "code": patched_code}

    # =========================================================================
    # generate_assessment_instructions — UNCHANGED from original
    # =========================================================================

    def generate_assessment_instructions(
        self,
        questions: List[Dict[str, Any]],
        assessment_type: str = "concept_check",
    ) -> Dict[str, Any]:
        """
        Generate VR instructions for in-lesson MCQ assessments.

        Assessment UI panels remain as VRInstruction JSON (not C# scripts)
        because they are driven by Unity's built-in UI system, not custom logic.
        """
        type_map = {
            "concept_check": AssessmentType.CONCEPT_CHECK,
            "mcq": AssessmentType.MCQ,
            "descriptive": AssessmentType.DESCRIPTIVE,
        }

        instructions = []

        # Intro step
        intro = VRInstruction(
            step_id="assess_intro",
            sequence_order=0,
            avatar=AvatarAction(action=AvatarActionType.QUESTION),
            voice=VoiceCommand(
                text="Let's check your understanding! Answer these questions.",
                emotion=VoiceEmotion.ENCOURAGING,
            ),
        )
        instructions.append(intro.model_dump())

        # Question steps
        for i, q in enumerate(questions):
            question_step = VRInstruction(
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
            )
            instructions.append(question_step.model_dump())

        # Completion step
        done = VRInstruction(
            step_id="assess_done",
            sequence_order=len(questions) + 1,
            avatar=AvatarAction(action=AvatarActionType.CELEBRATE),
            voice=VoiceCommand(
                text="Great job! Let's see how you did.",
                emotion=VoiceEmotion.ENCOURAGING,
            ),
        )
        instructions.append(done.model_dump())

        return {
            "assessment_type": assessment_type,
            "total_questions": len(questions),
            "instructions": instructions,
        }
