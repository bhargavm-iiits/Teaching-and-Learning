"""
Agent D: Pedagogy & Analogy Agent

Purpose: Decide HOW to teach a topic.

Inputs:
- Topic from Curriculum Agent (Agent C)
- Learner profile (learning style, preferences)
- Historical mistakes

Outputs:
- Analogy to use (cricket, cooking, gaming, etc.)
- Visualization strategy
- Interaction style for VR
- Teaching approach (intuition-first vs formula-first)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)
from db.supabase_client import supabase_manager
from models.schemas import (
    LearningStyle,
    PedagogyPlan,
)


# Analogy mappings for different topics
ANALOGY_BANK = {
    "physics": {
        "motion": {
            "sports": {
                "analogy": "Think of a sprinter running a 100m race - the starting line is the origin, and their position changes as they run",
                "objects": ["running_track", "sprinter", "stopwatch"],
                "scene": "sports_stadium",
            },
            "daily_life": {
                "analogy": "Like walking to school - the path you take is distance, but the straight line from home to school is displacement",
                "objects": ["house", "school", "walking_path"],
                "scene": "neighborhood",
            },
            "gaming": {
                "analogy": "In a racing game, your speedometer shows speed (scalar), but the mini-map shows your direction too (velocity - vector)",
                "objects": ["race_car", "speedometer", "track_map"],
                "scene": "racing_game",
            },
        },
        "kinematics": {
            "sports": {
                "analogy": "A cricket bowler's run-up: starts slow, accelerates, and releases at maximum speed",
                "objects": ["cricket_bowler", "cricket_pitch", "ball"],
                "scene": "cricket_ground",
            },
            "daily_life": {
                "analogy": "A car starting from a traffic light - accelerates from rest, maintains speed, then decelerates at the next light",
                "objects": ["car", "traffic_light", "road"],
                "scene": "city_street",
            },
        },
        "projectile_motion": {
            "sports": {
                "analogy": "A cricket ball hit for a six follows a parabolic path - horizontal velocity stays constant while vertical velocity changes due to gravity",
                "objects": ["cricket_bat", "ball_trajectory", "fielder"],
                "scene": "cricket_ground",
            },
            "daily_life": {
                "analogy": "Throwing water from a hose - angle it up and the water arcs through the air before landing",
                "objects": ["water_hose", "water_arc", "garden"],
                "scene": "backyard",
            },
            "gaming": {
                "analogy": "Angry Birds! The angle and force you launch the bird determines where it lands",
                "objects": ["slingshot", "bird", "target"],
                "scene": "angry_birds_inspired",
            },
        },
        "laws_of_motion": {
            "sports": {
                "analogy": "Kicking a football - the harder you kick, the faster it goes (F=ma). The ball resists being kicked (inertia). Your foot hurts too (action-reaction)!",
                "objects": ["football", "player", "goal_post"],
                "scene": "football_field",
            },
            "daily_life": {
                "analogy": "On a bus that suddenly brakes - you lurch forward because your body wants to keep moving (inertia)",
                "objects": ["bus", "passengers", "seats"],
                "scene": "bus_interior",
            },
        },
        "gravitation": {
            "sports": {
                "analogy": "A basketball shot's arc is determined by gravity pulling it down - higher on the Moon, lower on Jupiter",
                "objects": ["basketball", "hoop", "planet_comparison"],
                "scene": "basketball_court_space",
            },
            "daily_life": {
                "analogy": "An apple falling from a tree - the same force that makes it fall keeps the Moon orbiting Earth",
                "objects": ["apple_tree", "falling_apple", "moon_earth"],
                "scene": "orchard_with_sky",
            },
        },
        "work_energy": {
            "sports": {
                "analogy": "Lifting weights in a gym - more weight and more height means more work done. Your muscles convert chemical energy to mechanical energy",
                "objects": ["weights", "barbell", "athlete"],
                "scene": "gym",
            },
            "daily_life": {
                "analogy": "Pushing a shopping cart - work is done only when it moves. Pushing against a wall does no work!",
                "objects": ["shopping_cart", "supermarket_aisle", "wall"],
                "scene": "supermarket",
            },
        },
    },
    "chemistry": {
        "matter": {
            "daily_life": {
                "analogy": "Ice (solid), water (liquid), steam (gas) - same molecules, different arrangements based on temperature",
                "objects": ["ice_cube", "water_glass", "steam_kettle"],
                "scene": "kitchen",
            },
            "cooking": {
                "analogy": "Making tea - water evaporates when heated, sugar dissolves creating a solution",
                "objects": ["tea_pot", "sugar", "tea_cup"],
                "scene": "kitchen",
            },
        },
        "atoms_molecules": {
            "gaming": {
                "analogy": "Atoms are like LEGO blocks - they combine in specific ways to build different molecules",
                "objects": ["lego_blocks", "molecular_models", "assembly_guide"],
                "scene": "chemistry_lab_playful",
            },
            "daily_life": {
                "analogy": "H₂O is like a tiny code name - 2 hydrogen atoms and 1 oxygen atom always combine this way to make water",
                "objects": ["water_molecule", "atom_spheres", "bonds"],
                "scene": "3d_molecule_space",
            },
        },
        "atomic_structure": {
            "sports": {
                "analogy": "The atom is like a solar system - nucleus is the sun, electrons orbit like planets",
                "objects": ["nucleus", "electron_orbits", "solar_system_comparison"],
                "scene": "space_atom_model",
            },
            "daily_life": {
                "analogy": "Think of a crowded stadium - the nucleus is the tiny stage in the center, electrons are people scattered in the stands",
                "objects": ["stadium", "stage", "crowd"],
                "scene": "stadium_atom",
            },
        },
    },
    "maths": {
        "coordinate_geometry": {
            "gaming": {
                "analogy": "Video game maps use coordinates! X and Y tell you exactly where your character is",
                "objects": ["game_map", "character_marker", "coordinates_grid"],
                "scene": "2d_game_world",
            },
            "daily_life": {
                "analogy": "Finding a seat in a cinema - row number is Y, seat number is X",
                "objects": ["cinema_seats", "ticket", "grid"],
                "scene": "cinema_hall",
            },
        },
        "linear_equations": {
            "daily_life": {
                "analogy": "A taxi fare = base rate + (rate per km × distance). This is a linear equation!",
                "objects": ["taxi", "fare_meter", "graph"],
                "scene": "city_with_graph",
            },
        },
        "polynomials": {
            "daily_life": {
                "analogy": "Stacking boxes - one box is linear (x), two stacked is quadratic (x²), three is cubic (x³)",
                "objects": ["stacked_boxes", "dimension_labels", "graph"],
                "scene": "warehouse",
            },
        },
        "triangles": {
            "daily_life": {
                "analogy": "The triangles in bridges and trusses make them strong. Congruent triangles distribute weight evenly",
                "objects": ["bridge", "truss", "triangle_overlay"],
                "scene": "bridge_scene",
            },
            "sports": {
                "analogy": "Billiard shots form triangles - the angle you hit determines where the ball goes",
                "objects": ["billiard_table", "balls", "angle_lines"],
                "scene": "billiard_room",
            },
        },
    },
}


class PedagogyAgent(BaseAgent):
    """
    Agent D: Pedagogy & Analogy Agent.

    Determines the optimal teaching approach based on:
    - Student's learning style
    - Topic characteristics
    - Available analogies
    - Historical performance
    """

    def __init__(self, temperature: float = 0.3):
        super().__init__(temperature=temperature)
        self.analogy_bank = ANALOGY_BANK

    def _build_system_prompt(self) -> str:
        return """You are the Pedagogy & Analogy Agent, an expert in teaching methodologies and making abstract concepts concrete for Class 10 students.

Your role is to:
1. Select the best analogy/metaphor for explaining a concept
2. Design interactive VR experiences that match the student's learning style
3. Determine whether to teach formula-first or intuition-first
4. Create engaging, memorable learning experiences

You specialize in STEM education and understand that different students learn differently."""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method.

        Actions:
        - 'get_teaching_plan': Get complete pedagogy plan for a topic
        - 'select_analogy': Select best analogy for a topic
        - 'get_vr_elements': Get VR scene and object recommendations
        """
        action = input_data.get("action")

        if action == "get_teaching_plan":
            return await self.get_teaching_plan(
                student_id=input_data["student_id"],
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
                topic_name=input_data.get("topic_name"),
            )
        elif action == "select_analogy":
            return await self.select_analogy(
                student_id=input_data["student_id"],
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
            )
        elif action == "get_vr_elements":
            return self.get_vr_elements(
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
                analogy_category=input_data.get("analogy_category", "daily_life"),
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    async def get_teaching_plan(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a complete pedagogy plan for teaching a topic.

        Returns:
            PedagogyPlan as dictionary
        """
        # Get learner profile
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Student profile not found"}

        # Get available analogies for this topic
        available_analogies = self._get_available_analogies(subject_code, topic_code)

        # Determine preferred analogy category based on student preferences
        preferred_category = self._select_best_category(
            profile.preferred_analogies,
            list(available_analogies.keys()),
        )

        # Get analogy details
        analogy_data = available_analogies.get(preferred_category, {})

        # Use LLM to create detailed teaching plan
        # NOTE: Use direct f-string (not _format_prompt) to avoid the wrapper
        # appending its own output_format block which confuses the LLM into
        # generating trailing commas or other invalid JSON.
        prompt = f"""{self._build_system_prompt()}

Create a concise teaching plan for "{topic_name or topic_code}" in Class 10 {subject_code.upper()}.

Student profile:
- Learning style: {profile.learning_style.value}
- Preferred analogies: {profile.preferred_analogies}

Available analogy: {analogy_data.get("analogy", "General explanation")}
Analogy category: {preferred_category}
Scene objects available: {analogy_data.get("objects", [])}

Return a single raw JSON object. No markdown fences, no trailing commas, no extra text.
Use exactly this structure:
{{
  "approach": "intuition-first or formula-first",
  "approach_reason": "one sentence why",
  "visualization": "one sentence describing the 3D visualization",
  "interaction": "one sentence describing student interaction",
  "key_objects": ["object1", "object2", "object3"],
  "interaction_points": [
    "Point 1: description",
    "Point 2: description",
    "Point 3: description",
    "Point 4: description"
  ],
  "teaching_sequence": [
    "Step 1",
    "Step 2",
    "Step 3",
    "Step 4",
    "Step 5"
  ],
  "emphasize_visual": true,
  "use_examples_first": true
}}"""

        raw = await self._invoke_llm(prompt)
        logger.debug("[get_teaching_plan] raw response: %d chars", len(raw))
        result = self._parse_json(raw)

        return PedagogyPlan(
            topic=topic_code,
            analogy=analogy_data.get("analogy", f"Teaching {topic_name or topic_code}"),
            analogy_category=preferred_category,
            visualization=result.get("visualization", "Interactive 3D model"),
            interaction=result.get("interaction", "Hands-on practice"),
            approach=result.get("approach", "intuition-first"),
            use_examples_first=result.get("use_examples_first", True),
            emphasize_visual=result.get("emphasize_visual", True),
            recommended_scene=analogy_data.get("scene", "classroom"),
            key_objects=result.get("key_objects", analogy_data.get("objects", [])),
            interaction_points=result.get("interaction_points", []),
        ).model_dump()

    async def generate_lesson_content(
        self,
        topic_name: str,
        subject_code: str,
        subtopics: List[str],
        pedagogy_plan: Dict[str, Any],
        learning_style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate actual teaching content (explanations, examples, practice).

        Calls the LLM once per subtopic instead of asking for all sections
        in one prompt. This keeps each response small (~1500 tokens) and
        completely eliminates the truncation issue that caused JSON parse
        failures when all 4+ subtopics were requested in a single call.
        """
        import asyncio as _asyncio

        analogy = pedagogy_plan.get("analogy", "real-world examples")
        approach = pedagogy_plan.get("approach", "intuition-first")
        visualization = pedagogy_plan.get("visualization", "interactive 3D")
        style = learning_style or "visual"

        if not subtopics:
            subtopics = ["General Overview"]

        # ── Step 1: Generate the lesson introduction (one small call) ─────────
        intro_prompt = f"""{self._build_system_prompt()}

Write a single engaging introduction paragraph for a Class 10 {subject_code.upper()} lesson on "{topic_name}".

Teaching analogy to use: {analogy}
Student learning style: {style}

Rules:
- 3-5 sentences maximum
- Hook the student immediately using the analogy
- Conversational tone, age 15
- No markdown, no JSON — plain text only
"""
        intro_text = await self._invoke_llm(intro_prompt)
        intro_text = intro_text.strip()
        logger.debug("[generate_lesson_content] intro: %d chars", len(intro_text))

        # ── Step 2: Generate each section independently ───────────────────────
        sections: List[Dict[str, Any]] = []
        for subtopic in subtopics:
            section_prompt = f"""{self._build_system_prompt()}

Generate a lesson section for ONE subtopic only.

Topic: {topic_name} (Class 10 {subject_code.upper()})
Subtopic: {subtopic}
Teaching approach: {approach}
Analogy to weave in: {analogy}
Student learning style: {style}

Return a single raw JSON object — no markdown fences, no extra text.
Use exactly this structure:
{{
  "subtopic": "{subtopic}",
  "explanation": "2-3 paragraph explanation, conversational, Class 10 level",
  "example": {{
    "problem": "one worked example problem",
    "solution": "step-by-step solution"
  }},
  "real_world_connection": "1-2 sentences connecting to real life using the analogy"
}}"""

            raw = await self._invoke_llm(section_prompt)
            logger.debug(
                "[generate_lesson_content] section '%s': %d chars", subtopic, len(raw)
            )
            try:
                section = self._parse_json(raw)
                # Ensure subtopic key is always present
                section.setdefault("subtopic", subtopic)
                sections.append(section)
            except Exception as e:
                logger.warning(
                    "[generate_lesson_content] section '%s' parse failed: %s — using fallback",
                    subtopic,
                    e,
                )
                sections.append(
                    {
                        "subtopic": subtopic,
                        "explanation": raw[:500] if raw else "Content unavailable.",
                        "example": {"problem": "", "solution": ""},
                        "real_world_connection": "",
                    }
                )

        # ── Step 3: Generate takeaways + practice problems (one small call) ───
        subtopics_summary = ", ".join(subtopics)
        summary_prompt = f"""{self._build_system_prompt()}

A Class 10 {subject_code.upper()} lesson on "{topic_name}" covered: {subtopics_summary}.

Return a single raw JSON object — no markdown fences, no extra text:
{{
  "key_takeaways": [
    "concise takeaway 1",
    "concise takeaway 2",
    "concise takeaway 3"
  ],
  "practice_problems": [
    {{
      "question": "practice question 1",
      "answer": "answer 1"
    }},
    {{
      "question": "practice question 2",
      "answer": "answer 2"
    }}
  ]
}}"""

        raw_summary = await self._invoke_llm(summary_prompt)
        logger.debug("[generate_lesson_content] summary: %d chars", len(raw_summary))
        try:
            summary = self._parse_json(raw_summary)
        except Exception as e:
            logger.warning("[generate_lesson_content] summary parse failed: %s", e)
            summary = {"key_takeaways": [], "practice_problems": []}

        return {
            "title": f"{topic_name} — {subject_code.upper()} Lesson",
            "introduction": intro_text,
            "sections": sections,
            "key_takeaways": summary.get("key_takeaways", []),
            "practice_problems": summary.get("practice_problems", []),
        }

    async def select_analogy(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
    ) -> Dict[str, Any]:
        """
        Select the best analogy for teaching a topic to a specific student.
        """
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Student profile not found"}

        available = self._get_available_analogies(subject_code, topic_code)

        if not available:
            return {
                "topic_code": topic_code,
                "message": "No predefined analogies found, using default explanation",
                "selected_category": "general",
                "analogy": f"Let's explore {topic_code} step by step",
            }

        # Score each category based on student preferences
        scores = {}
        for category in available.keys():
            score = 0
            if category in profile.preferred_analogies:
                score += 10
            if category == "daily_life":  # Universal fallback
                score += 3
            if (
                profile.learning_style == LearningStyle.KINESTHETIC
                and category == "sports"
            ):
                score += 5
            if profile.learning_style == LearningStyle.VISUAL and category in [
                "gaming",
                "daily_life",
            ]:
                score += 5
            scores[category] = score

        best_category = max(scores, key=scores.get)
        selected = available[best_category]

        return {
            "topic_code": topic_code,
            "selected_category": best_category,
            "analogy": selected["analogy"],
            "scene": selected.get("scene"),
            "objects": selected.get("objects", []),
            "alternatives": list(available.keys()),
        }

    def _get_available_analogies(
        self, subject_code: str, topic_code: str
    ) -> Dict[str, Any]:
        """Get all available analogies for a topic."""
        if subject_code not in self.analogy_bank:
            return {}
        if topic_code not in self.analogy_bank[subject_code]:
            return {}
        return self.analogy_bank[subject_code][topic_code]

    def _select_best_category(
        self,
        preferred: List[str],
        available: List[str],
    ) -> str:
        """Select the best analogy category based on preferences."""
        for pref in preferred:
            if pref in available:
                return pref
        if "daily_life" in available:
            return "daily_life"
        return available[0] if available else "general"

    def get_vr_elements(
        self,
        subject_code: str,
        topic_code: str,
        analogy_category: str = "daily_life",
    ) -> Dict[str, Any]:
        """Get VR scene and object recommendations."""
        analogies = self._get_available_analogies(subject_code, topic_code)

        if analogy_category in analogies:
            data = analogies[analogy_category]
            return {
                "scene": data.get("scene", "virtual_classroom"),
                "objects": data.get("objects", []),
                "analogy": data.get("analogy"),
            }

        return {
            "scene": "virtual_classroom",
            "objects": ["whiteboard", "teacher_avatar"],
            "analogy": None,
        }
