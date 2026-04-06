"""
VR Tool Registry for Agent E (VRInstructionAgent).

Implements the agentAR-style tool library:
  1. generate_csharp_script   — LLM generates a Unity C# MonoBehaviour
  2. validate_csharp_syntax   — Regex/heuristic syntax checker (no external deps)
  3. review_script_pedagogically — LLM reviews pedagogical quality
  4. patch_csharp_script      — LLM patches a script given errors/suggestions
  5. assemble_unity_package   — Bundles all scripts into a UnityScriptPackage

All LLM calls are async. validate_csharp_syntax and assemble_unity_package are
synchronous pure-Python (no LLM, no I/O).
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# C# code-generation prompt helpers
# ---------------------------------------------------------------------------

_CSHARP_SYSTEM_PREAMBLE = """\
You are an expert Unity C# developer specialising in educational XR experiences for Class 10 students (age ~15).

Rules you MUST follow:
1. Every script must have `using UnityEngine;` as the first using directive.
2. Every script must inherit from `MonoBehaviour` (optionally also `ILessonStep`).
3. Use `[SerializeField]` for asset references — never hard-code asset paths in code.
4. Null-check every `GetComponent<>()` call before use.
5. Use coroutines (`IEnumerator` / `StartCoroutine`) for timed sequences.
6. Keep scripts focused on a single responsibility (SRP).
7. Write clear inline comments explaining what each block does for the student.
8. Do NOT use `Thread.Sleep` — use `yield return new WaitForSeconds(t)`.
9. All public string/float parameters should have sensible defaults.
10. Output ONLY the raw C# source code — no markdown fences, no explanation.

ILessonStep interface (always implement for non-manager scripts):
    public interface ILessonStep
    {
        System.Collections.IEnumerator Execute();
    }
"""

_STEP_TYPE_HINTS: Dict[str, str] = {
    "intro": (
        "This is the INTRO step. The SessionManager will call Execute() first. "
        "It should: (a) play a welcome voice trigger event, (b) slowly enable the "
        "main scene objects, (c) position the teacher avatar at its start point, "
        "and (d) yield until the intro animation finishes."
    ),
    "demonstration": (
        "This is a DEMONSTRATION step. It should animate one or more physics/science "
        "objects to visually illustrate the learning objective. Include vector arrows, "
        "labels, or trajectory arcs where appropriate. Yield between animation phases "
        "so the student can observe each stage."
    ),
    "interaction": (
        "This is an INTERACTION step. The student must manipulate a parameter (slider, "
        "grab, or XR interactable) and observe the result. Use XRSimpleInteractable or "
        "a UI Slider. Wait until the student completes the interaction before yielding "
        "to the next step. Provide visual feedback on every value change."
    ),
    "assessment": (
        "This is an ASSESSMENT checkpoint. Show a simple floating MCQ panel (world-space "
        "Canvas). Wait for the student's gaze/controller selection. Fire a UnityEvent "
        "with the selected answer so the backend can evaluate it."
    ),
    "summary": (
        "This is the SUMMARY step. Briefly replay key visuals from earlier steps at "
        "reduced scale as a recap. Display a summary text panel. Fire a LessonComplete "
        "event at the end so the SessionManager knows the lesson is done."
    ),
}

_SESSION_MANAGER_TEMPLATE = """\
using UnityEngine;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// Auto-generated SessionManager for topic: {topic}.
/// Orchestrates all ILessonStep components in sequence.
/// Attach this to a persistent empty GameObject in the scene.
/// </summary>
public class {class_name} : MonoBehaviour
{{
    [Header("Lesson Steps (assign in Inspector or via JSON manifest)")]
    [SerializeField] private List<MonoBehaviour> lessonSteps = new List<MonoBehaviour>();

    [Header("Events")]
    public UnityEngine.Events.UnityEvent onLessonComplete;

    private void Start()
    {{
        StartCoroutine(RunLesson());
    }}

    private IEnumerator RunLesson()
    {{
        foreach (var step in lessonSteps)
        {{
            if (step is ILessonStep lessonStep)
            {{
                yield return StartCoroutine(lessonStep.Execute());
            }}
            else
            {{
                Debug.LogWarning($"[SessionManager] {{step.name}} does not implement ILessonStep — skipping.");
            }}
        }}
        Debug.Log("[SessionManager] Lesson complete.");
        onLessonComplete?.Invoke();
    }}
}}

/// <summary>
/// Implement this interface on every lesson step MonoBehaviour.
/// </summary>
public interface ILessonStep
{{
    IEnumerator Execute();
}}
"""


# ---------------------------------------------------------------------------
# VRToolRegistry
# ---------------------------------------------------------------------------


class VRToolRegistry:
    """
    Tool library for Agent E's agentAR-style ReAct loop.

    Instantiated once per VRInstructionAgent with the agent's LLM instance.
    All async methods use run_in_executor to keep FastAPI's event loop free.
    """

    def __init__(self, llm):
        """
        Args:
            llm: A LangChain ChatAnthropic (or compatible) instance from BaseAgent.
        """
        self.llm = llm

    # ------------------------------------------------------------------
    # Private prompt builders (pure functions, no LLM calls)
    # ------------------------------------------------------------------

    def _build_csharp_prompt(
        self,
        class_name: str,
        description: str,
        step_type: str,
        learning_objective: str,
        attach_to: str,
        pedagogy_context: Dict[str, Any],
        topic: str,
        asset_bindings: Dict[str, str],
    ) -> str:
        """Return the C# generation prompt string. No LLM call."""
        analogy = pedagogy_context.get("analogy", "real-world examples")
        approach = pedagogy_context.get("approach", "intuition-first")
        step_hint = _STEP_TYPE_HINTS.get(step_type, "")
        asset_list = "\n".join(
            f"  // {aid} → prefab at: {path}"
            for aid, path in list(asset_bindings.items())[:8]
        )
        return (
            f"{_CSHARP_SYSTEM_PREAMBLE}\n\n"
            f"// ─── TASK ───────────────────────────────────────────────────────────────────\n"
            f"// Generate a Unity C# MonoBehaviour class named exactly: {class_name}\n"
            f"// It implements ILessonStep (defined in the SessionManager script).\n"
            f"//\n"
            f"// Topic being taught : {topic}\n"
            f"// Teaching analogy   : {analogy}\n"
            f"// Teaching approach  : {approach}\n"
            f"// Step type          : {step_type}\n"
            f"// Learning objective : {learning_objective}\n"
            f"// Attach to GameObject: {attach_to}\n"
            f"//\n"
            f"// Step-type guidance:\n"
            f"// {step_hint}\n"
            f"//\n"
            f"// Available scene assets (use [SerializeField] references, not hard-coded paths):\n"
            f"{asset_list if asset_list else '  // (generic scene — no specific assets pre-mapped)'}\n"
            f"//\n"
            f"// Script description:\n"
            f"// {description}\n"
            f"//\n"
            f"// ─── OUTPUT ─────────────────────────────────────────────────────────────────\n"
            f"// Output ONLY the complete, compilable C# source. No markdown, no explanation.\n"
        )

    def _build_patch_prompt(
        self,
        code: str,
        errors: List[str],
        instruction: str,
    ) -> str:
        """Return the patch prompt string. No LLM call."""
        numbered_errors = "\n".join(f"  {i + 1}. {e}" for i, e in enumerate(errors))
        return (
            f"{_CSHARP_SYSTEM_PREAMBLE}\n\n"
            f"// ─── PATCH TASK ─────────────────────────────────────────────────────────────\n"
            f"// The following Unity C# script has errors or quality issues that must be fixed.\n"
            f"//\n"
            f"// Specific instruction: {instruction}\n"
            f"//\n"
            f"// Errors / issues to fix:\n"
            f"{numbered_errors}\n"
            f"//\n"
            f"// ─── ORIGINAL SCRIPT ────────────────────────────────────────────────────────\n"
            f"{code}\n"
            f"//\n"
            f"// ─── OUTPUT ─────────────────────────────────────────────────────────────────\n"
            f"// Return ONLY the complete corrected C# source. No markdown, no explanation.\n"
        )

    # ------------------------------------------------------------------
    # Tool 1a — generate_csharp_script_stream  (token-by-token, async generator)
    # ------------------------------------------------------------------

    async def generate_csharp_script_stream(
        self,
        class_name: str,
        description: str,
        step_type: str,
        learning_objective: str,
        attach_to: str,
        scene_context: Dict[str, Any],
        pedagogy_context: Dict[str, Any],
        topic: str,
        asset_bindings: Optional[Dict[str, str]] = None,
        is_session_manager: bool = False,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """
        Tool 1a: Async generator that streams C# source tokens as the LLM writes them.

        Yields:
            str  — raw text token from the LLM (forward to SSE as csharp_script_token)
            dict — final sentinel {"__done__": True, "code": "<full_clean_source>"}
                   when generation is complete
        """
        asset_bindings = asset_bindings or {}

        # SessionManager is a deterministic template — emit it instantly
        if is_session_manager:
            code = _SESSION_MANAGER_TEMPLATE.format(topic=topic, class_name=class_name)
            yield code
            yield {"__done__": True, "code": code}
            return

        prompt = self._build_csharp_prompt(
            class_name=class_name,
            description=description,
            step_type=step_type,
            learning_objective=learning_objective,
            attach_to=attach_to,
            pedagogy_context=pedagogy_context,
            topic=topic,
            asset_bindings=asset_bindings,
        )

        accumulated = ""
        async for chunk in self.llm.astream(prompt):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if isinstance(token, str) and token:
                accumulated += token
                yield token

        clean = _strip_markdown_fences(accumulated).strip()
        yield {"__done__": True, "code": clean}

    # ------------------------------------------------------------------
    # Tool 1b — generate_csharp_script  (non-streaming, backward compat)
    # ------------------------------------------------------------------

    async def generate_csharp_script(
        self,
        class_name: str,
        description: str,
        step_type: str,
        learning_objective: str,
        attach_to: str,
        scene_context: Dict[str, Any],
        pedagogy_context: Dict[str, Any],
        topic: str,
        asset_bindings: Optional[Dict[str, str]] = None,
        is_session_manager: bool = False,
    ) -> str:
        """
        Tool 1b: Non-streaming version (used by apply_unity_feedback and create_session).
        Collects the full stream and returns the assembled code string.
        """
        asset_bindings = asset_bindings or {}
        if is_session_manager:
            return _SESSION_MANAGER_TEMPLATE.format(topic=topic, class_name=class_name)

        prompt = self._build_csharp_prompt(
            class_name=class_name,
            description=description,
            step_type=step_type,
            learning_objective=learning_objective,
            attach_to=attach_to,
            pedagogy_context=pedagogy_context,
            topic=topic,
            asset_bindings=asset_bindings,
        )
        response = await asyncio.get_event_loop().run_in_executor(
            None, self.llm.invoke, prompt
        )
        code = response.content if hasattr(response, "content") else str(response)
        return _strip_markdown_fences(code).strip()

    # ------------------------------------------------------------------
    # Tool 2 — validate_csharp_syntax  (pure Python / regex, no LLM)
    # ------------------------------------------------------------------

    def validate_csharp_syntax(self, code: str) -> Dict[str, Any]:
        """
        Tool 2: Heuristic regex-based C# syntax validation.

        Checks (in order):
          1. `using UnityEngine;` is present
          2. Class inherits from MonoBehaviour
          3. Balanced braces { }
          4. Class declaration present
          5. At least one lifecycle/entry method
          6. Every GetComponent<T>() call has a nearby null check

        Returns:
            {"valid": bool, "errors": list[str], "warnings": list[str]}
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. using UnityEngine
        if not re.search(r"\busing\s+UnityEngine\s*;", code):
            errors.append("Missing `using UnityEngine;` directive.")

        # 2. MonoBehaviour inheritance
        if not re.search(r":\s*MonoBehaviour\b", code):
            errors.append(
                "Class does not inherit from MonoBehaviour. "
                "Add `: MonoBehaviour` to the class declaration."
            )

        # 3. Balanced braces
        open_count = code.count("{")
        close_count = code.count("}")
        if open_count != close_count:
            errors.append(
                f"Unbalanced braces: {open_count} opening '{{' vs {close_count} closing '}}'."
            )

        # 4. Class declaration
        if not re.search(r"\bclass\s+\w+", code):
            errors.append("No class declaration found.")

        # 5. At least one recognised entry point
        entry_methods = ["Start()", "Awake()", "Update()", "Execute()"]
        found_entry = any(
            re.search(
                rf"\b(void|IEnumerator)\s+{re.escape(m.rstrip('()'))}\s*\(\s*\)", code
            )
            for m in entry_methods
        )
        if not found_entry:
            warnings.append(
                "No recognised entry method found (Start, Awake, Update, Execute). "
                "Ensure the script has at least one."
            )

        # 6. GetComponent null checks
        get_component_calls = list(
            re.finditer(r"GetComponent\s*<[^>]+>\s*\(\s*\)", code)
        )
        lines = code.splitlines()
        for match in get_component_calls:
            # Find which line the call is on
            char_pos = match.start()
            line_num = code[:char_pos].count("\n")
            # Check the next 3 lines for a null / != null pattern
            window = "\n".join(lines[line_num : line_num + 4])
            if not re.search(
                r"(!=\s*null|==\s*null|if\s*\(|Debug\.LogWarning|Debug\.LogError)",
                window,
            ):
                var_name = lines[line_num].strip()[:60]
                warnings.append(
                    f"GetComponent call on line {line_num + 1} may lack a null check: `{var_name}`"
                )

        # 7. using System.Collections for coroutines
        if re.search(r"\bIEnumerator\b", code) and not re.search(
            r"\busing\s+System\.Collections\s*;", code
        ):
            errors.append(
                "Script uses IEnumerator but is missing `using System.Collections;`."
            )

        valid = len(errors) == 0
        return {"valid": valid, "errors": errors, "warnings": warnings}

    # ------------------------------------------------------------------
    # Tool 3 — review_script_pedagogically
    # ------------------------------------------------------------------

    async def review_script_pedagogically(
        self,
        code: str,
        learning_objective: str,
        topic_code: str,
    ) -> Dict[str, Any]:
        """
        Tool 3: LLM reviews whether the script effectively teaches the objective.

        Returns:
            {"score": int 0–10, "issues": list[str], "suggestions": list[str]}
        """
        prompt = f"""You are a VR educational content reviewer for Class 10 students (age ~15).

Review this Unity C# script that is intended to teach: "{learning_objective}" as part of the topic "{topic_code}".

## Script to review:
```csharp
{code[:3000]}
```

Evaluate on these criteria (score each 0–2, total out of 10):
1. Does the script clearly implement the learning objective?
2. Is there a meaningful student interaction (not just a passive animation)?
3. Is the pacing appropriate (neither too rushed nor too slow with yields)?
4. Are visual feedback cues provided (labels, arrows, highlights)?
5. Is the code readable enough for a Unity developer to understand and extend?

Return a JSON object with this exact structure:
{{
  "score": <integer 0-10>,
  "issues": ["issue 1", "issue 2"],
  "suggestions": ["suggestion 1", "suggestion 2"]
}}

Return ONLY the JSON object, no additional text."""

        response = await asyncio.get_event_loop().run_in_executor(
            None, self.llm.invoke, prompt
        )
        raw = response.content if hasattr(response, "content") else str(response)
        try:
            data = _parse_json_safe(raw)
            return {
                "score": int(data.get("score", 5)),
                "issues": data.get("issues", []),
                "suggestions": data.get("suggestions", []),
            }
        except Exception:
            # If parsing fails, return a neutral score so the loop continues
            return {"score": 6, "issues": [], "suggestions": []}

    # ------------------------------------------------------------------
    # Tool 4a — patch_csharp_script_stream  (token-by-token, async generator)
    # ------------------------------------------------------------------

    async def patch_csharp_script_stream(
        self,
        code: str,
        errors: List[str],
        instruction: str,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """
        Tool 4a: Async generator that streams the patched C# source token by token.

        Yields:
            str  — raw text token
            dict — final sentinel {"__done__": True, "code": "<full_clean_source>"}
        """
        prompt = self._build_patch_prompt(code, errors, instruction)
        accumulated = ""
        async for chunk in self.llm.astream(prompt):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if isinstance(token, str) and token:
                accumulated += token
                yield token
        clean = _strip_markdown_fences(accumulated).strip()
        yield {"__done__": True, "code": clean}

    # ------------------------------------------------------------------
    # Tool 4b — patch_csharp_script  (non-streaming, used by apply_unity_feedback)
    # ------------------------------------------------------------------

    async def patch_csharp_script(
        self,
        code: str,
        errors: List[str],
        instruction: str,
    ) -> str:
        """
        Tool 4b: Non-streaming patch — collects full response and returns string.
        Used by apply_unity_feedback() where streaming is not needed.
        """
        prompt = self._build_patch_prompt(code, errors, instruction)
        response = await asyncio.get_event_loop().run_in_executor(
            None, self.llm.invoke, prompt
        )
        patched = response.content if hasattr(response, "content") else str(response)
        return _strip_markdown_fences(patched).strip()

    # ------------------------------------------------------------------
    # Tool 5 — assemble_unity_package  (pure Python, no LLM)
    # ------------------------------------------------------------------

    def assemble_unity_package(
        self,
        scripts: List[Dict[str, Any]],
        scene_manifest: Dict[str, Any],
        session_id: str,
        student_id: str,
        topic: str,
        subject: str,
        estimated_minutes: int = 30,
    ) -> Dict[str, Any]:
        """
        Tool 5: Bundle all generated C# scripts into a UnityScriptPackage dict.

        - Assigns sequence_order based on step_type priority.
        - Identifies the SessionManager as entry_point.
        - Returns a dict matching UnityScriptPackage schema.
        """
        STEP_ORDER = {
            "session_manager": 0,
            "intro": 1,
            "demonstration": 2,
            "interaction": 3,
            "assessment": 4,
            "summary": 5,
        }

        entry_point = ""
        ordered_scripts = []

        for idx, s in enumerate(scripts):
            step_type = s.get("step_type", "demonstration")
            order = STEP_ORDER.get(step_type, 10) * 10 + idx
            ordered_scripts.append({**s, "sequence_order": order})

        # Sort by sequence_order
        ordered_scripts.sort(key=lambda x: x["sequence_order"])

        # Find SessionManager entry point
        for s in ordered_scripts:
            if s.get("step_type") == "session_manager" or "SessionManager" in s.get(
                "class_name", ""
            ):
                entry_point = s["class_name"]
                break

        # Fallback: use first script
        if not entry_point and ordered_scripts:
            entry_point = ordered_scripts[0].get("class_name", "")

        return {
            "session_id": session_id,
            "student_id": student_id,
            "topic": topic,
            "subject": subject,
            "entry_point": entry_point,
            "scripts": ordered_scripts,
            "scene_manifest": scene_manifest,
            "total_scripts": len(ordered_scripts),
            "estimated_duration_minutes": estimated_minutes,
            "completed": False,
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _strip_markdown_fences(text: str) -> str:
    """Remove ```csharp ... ``` or ``` ... ``` fences from LLM output."""
    # Remove ```csharp fence
    text = re.sub(r"^```(?:csharp|cs|unity)?\s*\n?", "", text, flags=re.MULTILINE)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    return text


def _parse_json_safe(text: str) -> Dict[str, Any]:
    """Parse JSON from LLM output, tolerating markdown fences."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try bare JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Cannot parse JSON from: {text[:200]}")
