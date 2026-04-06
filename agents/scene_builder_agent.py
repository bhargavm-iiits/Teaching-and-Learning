"""
Agent G: Scene Builder Agent

Purpose: Generate detailed VR scene descriptions that Unity can use to
         construct immersive, pedagogically-aligned learning environments.

Inputs:
- PedagogyPlan (analogy, recommended_scene, key_objects)
- CurriculumPlan (topic_code, subject_code, depth)
- LearnerProfile (learning_style, preferred_analogies)
- Optional: existing VRSession context for continuity

Outputs:
- SceneDescription: Full narrative + structured layout for a VR scene
- SceneAssetManifest: List of required Unity assets with placement data
- SceneTransition: How to move from one scene to the next
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from models.vr_contracts import (
    AvatarAction,
    AvatarActionType,
    AvatarCharacter,
    SceneCommand,
    SceneType,
    VoiceCommand,
    VoiceEmotion,
    VoicePace,
    VisualCommand,
    MotionType,
)


# ========================= SCENE BUILDER MODELS =========================


class AssetPlacement(BaseModel):
    """A single Unity asset with its position and configuration."""

    asset_id: str
    label: str
    position: Dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}
    )
    rotation: Dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}
    )
    scale: float = 1.0
    interactive: bool = False
    highlight_on_start: bool = False
    tooltip: Optional[str] = None


class SceneAssetManifest(BaseModel):
    """
    Complete list of Unity assets needed to render a VR scene.
    Produced alongside the narrative SceneDescription so Unity knows
    exactly which prefabs to instantiate.
    """

    scene_id: SceneType
    assets: List[AssetPlacement] = Field(default_factory=list)
    ambient_sound: Optional[str] = None  # e.g. "cricket_crowd_ambient"
    background_music: Optional[str] = None  # e.g. "upbeat_science_loop"
    lighting_preset: str = "day_natural"  # Unity lighting preset name
    skybox: Optional[str] = None  # Unity skybox asset name


class SceneDescription(BaseModel):
    """
    Human-readable + structured description of a VR scene.
    Used both for Unity construction and for TTS narration.
    """

    scene_id: SceneType
    title: str
    narrative: str  # Full teacher narration for scene intro
    environment_summary: str  # 1-2 line Unity brief
    key_learning_objects: List[str] = Field(default_factory=list)
    interaction_hints: List[str] = Field(default_factory=list)
    teacher_position: str = "center"  # "center", "left", "right", "podium"
    student_focus_point: Optional[str] = (
        None  # Asset ID the camera should look at first
    )
    estimated_time_minutes: int = 5


class SceneTransition(BaseModel):
    """
    Instructions for moving between two VR scenes.
    Provides both the visual effect and the teacher's bridge dialogue.
    """

    from_scene: SceneType
    to_scene: SceneType
    transition_effect: str = (
        "fade_black"  # "fade_black", "portal", "dissolve", "teleport"
    )
    bridge_dialogue: str = ""  # What the teacher says during transition
    duration_seconds: float = 2.0


class FullScenePlan(BaseModel):
    """
    Agent G's complete output: everything needed to build a lesson's VR environment.
    """

    session_id: str
    topic_code: str
    subject_code: str
    scenes: List[SceneDescription] = Field(default_factory=list)
    asset_manifests: List[SceneAssetManifest] = Field(default_factory=list)
    transitions: List[SceneTransition] = Field(default_factory=list)
    opening_scene: SceneCommand
    opening_avatar: AvatarAction
    opening_voice: VoiceCommand


# ========================= SCENE KNOWLEDGE BASE =========================

# Maps (subject_code, topic_code) → recommended scene sequence with asset hints
SCENE_KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    "physics": {
        "projectile_motion": {
            "primary_scene": SceneType.CRICKET_GROUND,
            "secondary_scene": SceneType.PHYSICS_LAB,
            "primary_assets": [
                "cricket_bat",
                "cricket_ball",
                "trajectory_arc",
                "velocity_vector_arrow",
                "gravity_vector_arrow",
                "angle_protractor_overlay",
                "range_marker",
            ],
            "secondary_assets": [
                "lab_bench",
                "launch_cannon",
                "angle_dial",
                "velocity_slider",
                "graph_board_x_range",
            ],
            "ambient": "cricket_crowd_distant",
            "lighting": "afternoon_sun",
        },
        "laws_of_motion": {
            "primary_scene": SceneType.OUTDOOR_FIELD,
            "secondary_scene": SceneType.PHYSICS_LAB,
            "primary_assets": [
                "football",
                "player_avatar",
                "goal_post",
                "force_arrow",
                "acceleration_indicator",
            ],
            "secondary_assets": [
                "wooden_block",
                "spring_scale",
                "frictionless_table",
                "hanging_mass",
                "pulley",
            ],
            "ambient": "outdoor_wind",
            "lighting": "day_natural",
        },
        "gravitation": {
            "primary_scene": SceneType.SPACE,
            "secondary_scene": SceneType.OUTDOOR_FIELD,
            "primary_assets": [
                "earth_model",
                "moon_orbit_path",
                "apple_fall_animation",
                "planet_mass_labels",
                "gravitational_field_lines",
            ],
            "secondary_assets": [
                "apple_tree",
                "falling_apple",
                "weight_scale",
            ],
            "ambient": "space_ambience",
            "lighting": "space_stars",
        },
        "kinematics": {
            "primary_scene": SceneType.OUTDOOR_FIELD,
            "secondary_scene": SceneType.PHYSICS_LAB,
            "primary_assets": [
                "running_track",
                "sprinter",
                "stopwatch",
                "displacement_vector",
                "distance_path_overlay",
            ],
            "secondary_assets": [
                "velocity_time_graph",
                "position_time_graph",
                "ticker_tape",
                "trolley",
            ],
            "ambient": "athletics_crowd",
            "lighting": "afternoon_sun",
        },
        "work_energy": {
            "primary_scene": SceneType.PLAYGROUND,
            "secondary_scene": SceneType.PHYSICS_LAB,
            "primary_assets": [
                "swing",
                "roller_coaster_mini",
                "energy_bar_indicator",
                "potential_energy_label",
                "kinetic_energy_label",
            ],
            "secondary_assets": [
                "spring_compressed",
                "mass_on_incline",
                "work_done_gauge",
            ],
            "ambient": "playground_sounds",
            "lighting": "day_natural",
        },
    },
    "chemistry": {
        "atomic_structure": {
            "primary_scene": SceneType.CHEMISTRY_LAB,
            "secondary_scene": SceneType.SPACE,
            "primary_assets": [
                "bohr_atom_model",
                "nucleus_sphere",
                "electron_orbit_rings",
                "proton_label",
                "neutron_label",
                "electron_label",
            ],
            "secondary_assets": [
                "solar_system_analogy",
                "planet_orbit_paths",
            ],
            "ambient": "lab_hum",
            "lighting": "lab_fluorescent",
        },
        "matter": {
            "primary_scene": SceneType.CHEMISTRY_LAB,
            "secondary_scene": None,
            "primary_assets": [
                "solid_lattice_model",
                "liquid_particle_model",
                "gas_particle_model",
                "temperature_slider",
                "phase_change_indicator",
            ],
            "secondary_assets": [],
            "ambient": "lab_hum",
            "lighting": "lab_fluorescent",
        },
        "atoms_molecules": {
            "primary_scene": SceneType.CHEMISTRY_LAB,
            "secondary_scene": None,
            "primary_assets": [
                "lego_block_hydrogen",
                "lego_block_oxygen",
                "water_molecule_assembled",
                "bond_formation_animation",
                "periodic_table_panel",
            ],
            "secondary_assets": [],
            "ambient": "lab_hum",
            "lighting": "lab_natural",
        },
    },
    "maths": {
        "coordinate_geometry": {
            "primary_scene": SceneType.MATH_ROOM,
            "secondary_scene": None,
            "primary_assets": [
                "3d_coordinate_axes",
                "movable_point_marker",
                "grid_floor",
                "distance_line_segment",
                "midpoint_indicator",
            ],
            "secondary_assets": [],
            "ambient": "quiet_room",
            "lighting": "bright_indoor",
        },
        "linear_equations": {
            "primary_scene": SceneType.MATH_ROOM,
            "secondary_scene": SceneType.CLASSROOM,
            "primary_assets": [
                "graph_board_xy",
                "movable_line",
                "slope_indicator",
                "y_intercept_marker",
                "equation_panel",
            ],
            "secondary_assets": [
                "taxi_model",
                "fare_meter",
                "distance_strip",
            ],
            "ambient": "quiet_room",
            "lighting": "bright_indoor",
        },
        "triangles": {
            "primary_scene": SceneType.MATH_ROOM,
            "secondary_scene": SceneType.OUTDOOR_FIELD,
            "primary_assets": [
                "congruent_triangle_pair",
                "similarity_overlay",
                "angle_arc_markers",
                "side_length_labels",
            ],
            "secondary_assets": [
                "bridge_truss",
                "triangle_highlight_overlay",
            ],
            "ambient": "quiet_room",
            "lighting": "bright_indoor",
        },
        "number_systems": {
            "primary_scene": SceneType.STADIUM,
            "secondary_scene": SceneType.MATH_ROOM,
            "primary_assets": [
                "pizza_fraction_wheel",
                "number_line_track",
                "boundary_rope_circle",
                "scoreboard_display",
                "temperature_thermometer",
                "rational_number_flag",
                "irrational_number_flag",
                "pi_symbol_banner",
                "sqrt2_indicator",
                "fraction_pizza_slices",
                "cricket_run_rate_display",
                "decimal_scoreboard",
            ],
            "secondary_assets": [
                "coordinate_grid",
                "venn_diagram_rational_irrational",
                "number_line_infinite_zoom",
                "repeating_decimal_animation",
                "non_terminating_decimal_visual",
            ],
            "ambient": "stadium_crowd_cheering",
            "lighting": "afternoon_sun",
        },
    },
}

# Fallback scene for unknown topics
DEFAULT_SCENE_DATA: Dict[str, Any] = {
    "primary_scene": SceneType.CLASSROOM,
    "secondary_scene": None,
    "primary_assets": ["whiteboard", "teacher_desk", "student_seats"],
    "secondary_assets": [],
    "ambient": "classroom_ambient",
    "lighting": "day_natural",
}


class SceneBuilderAgent(BaseAgent):
    """
    Agent G: Scene Builder Agent.

    Generates rich, structured VR scene descriptions for Unity by combining:
    - Pedagogical strategy from Agent D (PedagogyPlan)
    - Curriculum context from Agent C (CurriculumPlan)
    - Student profile from Agent B (LearnerProfile)

    Unlike Agent E (VRInstructionAgent) which produces step-by-step VRInstruction
    packets, this agent focuses entirely on the *environment* — the scene layout,
    assets, lighting, ambient audio, teacher positioning, and transition narration
    that frames the learning experience.
    """

    def __init__(self, temperature: float = 0.3):
        super().__init__(temperature=temperature)
        self.scene_kb = SCENE_KNOWLEDGE_BASE

    def _build_system_prompt(self) -> str:
        return """You are the Scene Builder Agent for an AI-driven VR teaching system targeting Class 10 students.

Your role is to design immersive, educationally purposeful VR environments. You:
1. Translate pedagogical plans into vivid, concrete scene descriptions
2. Select assets and their 3D placements to maximise learning clarity
3. Write teacher narration that greets students and orients them in the scene
4. Design seamless transitions between scenes that reinforce learning continuity
5. Ensure scenes match the student's preferred analogy (sports, gaming, daily life, etc.)

Guiding principles:
- Every object in the scene must serve a learning purpose
- Scenes should feel familiar and exciting, not clinical or sterile
- Use the student's analogy preference to make the environment emotionally resonant
- Keep narration conversational, warm, and pitched at a 15-year-old
- Avoid cluttering the scene — 3-6 key objects is enough to stay focused"""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main dispatcher.

        Actions:
        - 'build_scene': Generate a complete FullScenePlan for a topic
        - 'describe_scene': Generate a single SceneDescription for one scene type
        - 'build_asset_manifest': Generate the asset manifest for a given scene
        - 'build_transition': Generate a SceneTransition between two scenes
        - 'get_scene_for_topic': Quick lookup — returns recommended SceneType(s) for a topic
        """
        action = input_data.get("action")

        if action == "build_scene":
            return await self.build_scene(
                session_id=input_data["session_id"],
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
                topic_name=input_data.get("topic_name"),
                pedagogy_plan=input_data.get("pedagogy_plan", {}),
                learner_profile=input_data.get("learner_profile", {}),
            )
        elif action == "describe_scene":
            return await self.describe_scene(
                scene_type=SceneType(input_data["scene_type"]),
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
                topic_name=input_data.get("topic_name"),
                analogy=input_data.get("analogy", ""),
                learning_style=input_data.get("learning_style", "visual"),
            )
        elif action == "build_asset_manifest":
            return self.build_asset_manifest(
                scene_type=SceneType(input_data["scene_type"]),
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
                extra_assets=input_data.get("extra_assets", []),
            ).model_dump()
        elif action == "build_transition":
            return await self.build_transition(
                from_scene=SceneType(input_data["from_scene"]),
                to_scene=SceneType(input_data["to_scene"]),
                topic_name=input_data.get("topic_name", ""),
                context=input_data.get("context", ""),
            )
        elif action == "get_scene_for_topic":
            return self.get_scene_for_topic(
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    # ========================= PUBLIC METHODS =========================

    async def build_scene(
        self,
        session_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str] = None,
        pedagogy_plan: Optional[Dict[str, Any]] = None,
        learner_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a complete FullScenePlan for a teaching session.

        This is the primary method — it produces:
        - All SceneDescriptions (primary + optional secondary)
        - All SceneAssetManifests
        - All SceneTransitions between scenes
        - The opening SceneCommand / AvatarAction / VoiceCommand for Unity

        Returns:
            FullScenePlan as a dictionary
        """
        pedagogy_plan = pedagogy_plan or {}
        learner_profile = learner_profile or {}

        scene_data = self._get_scene_data(subject_code, topic_code)
        primary_scene = scene_data["primary_scene"]
        secondary_scene = scene_data.get("secondary_scene")

        analogy = pedagogy_plan.get("analogy", "")
        analogy_category = pedagogy_plan.get("analogy_category", "daily_life")
        learning_style = learner_profile.get("learning_style", "visual")
        display_name = topic_name or topic_code.replace("_", " ").title()

        # Build descriptions for each scene
        primary_desc_data = await self.describe_scene(
            scene_type=primary_scene,
            subject_code=subject_code,
            topic_code=topic_code,
            topic_name=display_name,
            analogy=analogy,
            learning_style=learning_style,
        )
        primary_desc = SceneDescription(**primary_desc_data)

        scenes: List[SceneDescription] = [primary_desc]
        manifests: List[SceneAssetManifest] = [
            self.build_asset_manifest(primary_scene, subject_code, topic_code)
        ]
        transitions: List[SceneTransition] = []

        if secondary_scene:
            secondary_desc_data = await self.describe_scene(
                scene_type=secondary_scene,
                subject_code=subject_code,
                topic_code=topic_code,
                topic_name=display_name,
                analogy=analogy,
                learning_style=learning_style,
            )
            secondary_desc = SceneDescription(**secondary_desc_data)
            scenes.append(secondary_desc)
            manifests.append(
                self.build_asset_manifest(secondary_scene, subject_code, topic_code)
            )

            # Build transition between the two scenes
            transition_data = await self.build_transition(
                from_scene=primary_scene,
                to_scene=secondary_scene,
                topic_name=display_name,
                context=analogy,
            )
            transitions.append(SceneTransition(**transition_data))

        # Opening commands for Unity
        opening_scene = SceneCommand(
            scene_id=primary_scene,
            time_of_day="day",
            weather="clear",
            allow_free_movement=True,
        )
        opening_avatar = AvatarAction(
            character=AvatarCharacter.TEACHER,
            action=AvatarActionType.GREET,
            duration_seconds=3.0,
        )
        opening_voice = VoiceCommand(
            text=primary_desc.narrative,
            emotion=VoiceEmotion.FRIENDLY,
            pace=VoicePace.NORMAL,
            delay_before_seconds=0.5,
        )

        plan = FullScenePlan(
            session_id=session_id,
            topic_code=topic_code,
            subject_code=subject_code,
            scenes=scenes,
            asset_manifests=manifests,
            transitions=transitions,
            opening_scene=opening_scene,
            opening_avatar=opening_avatar,
            opening_voice=opening_voice,
        )
        return plan.model_dump()

    async def describe_scene(
        self,
        scene_type: SceneType,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str] = None,
        analogy: str = "",
        learning_style: str = "visual",
    ) -> Dict[str, Any]:
        """
        Generate a SceneDescription for a single scene type.

        Uses the LLM to write the teacher's opening narration, environment
        summary, interaction hints, and student focus guidance.

        Returns:
            SceneDescription as a dictionary
        """
        scene_data = self._get_scene_data(subject_code, topic_code)
        assets = (
            scene_data.get("primary_assets", [])
            if scene_type == scene_data.get("primary_scene")
            else scene_data.get("secondary_assets", [])
        )
        display_name = topic_name or topic_code.replace("_", " ").title()

        prompt = self._format_prompt(
            task=f"""Design a VR scene for teaching "{display_name}" (Class 10 {subject_code.upper()}).

## Scene Details
- Scene type: {scene_type.value}
- Available assets: {assets}
- Teaching analogy: {analogy or "general real-world examples"}
- Student learning style: {learning_style}

## Instructions
1. Write a teacher's opening narration (3-5 sentences) that:
   - Welcomes the student to the scene using the analogy
   - Briefly previews what they will discover
   - Sounds warm, conversational, and age-appropriate (15-year-old)
2. Write a 1-2 sentence environment summary (for the Unity developer)
3. List 3-5 key learning objects the student should interact with (from the available assets)
4. List 2-3 interaction hints (e.g. "Try grabbing the velocity slider to change launch speed")
5. Suggest where the teacher avatar should stand
6. Identify which asset the camera should focus on first
7. Estimate scene time in minutes (3-10)""",
            output_format="""{
  "title": "Cricket Ground — Projectile Motion in Action",
  "narrative": "Welcome to Eden Gardens! Today we're going to discover how every six a batsman hits is secretly a physics experiment. Watch that ball fly — can you spot the invisible forces guiding it?",
  "environment_summary": "A daytime cricket ground with a batsman, live trajectory arc, and force-vector overlays for a projectile motion lesson.",
  "key_learning_objects": ["cricket_ball", "trajectory_arc", "velocity_vector_arrow", "gravity_vector_arrow", "angle_protractor_overlay"],
  "interaction_hints": [
    "Grab the angle dial and change the launch angle — watch how the range changes!",
    "Point at the ball mid-flight to see its horizontal and vertical velocity components.",
    "Move to the fielder's position to predict where the ball will land."
  ],
  "teacher_position": "left",
  "student_focus_point": "cricket_ball",
  "estimated_time_minutes": 6
}""",
        )

        result = await self._invoke_llm_json(prompt)

        return SceneDescription(
            scene_id=scene_type,
            title=result.get(
                "title",
                f"{scene_type.value.replace('_', ' ').title()} — {display_name}",
            ),
            narrative=result.get(
                "narrative", f"Welcome! Today we'll explore {display_name} right here."
            ),
            environment_summary=result.get(
                "environment_summary", f"A {scene_type.value} scene for {display_name}."
            ),
            key_learning_objects=result.get("key_learning_objects", assets[:5]),
            interaction_hints=result.get("interaction_hints", []),
            teacher_position=result.get("teacher_position", "center"),
            student_focus_point=result.get("student_focus_point"),
            estimated_time_minutes=result.get("estimated_time_minutes", 5),
        ).model_dump()

    def build_asset_manifest(
        self,
        scene_type: SceneType,
        subject_code: str,
        topic_code: str,
        extra_assets: Optional[List[str]] = None,
    ) -> SceneAssetManifest:
        """
        Build the Unity asset manifest for a scene.

        Pulls from the knowledge base and assigns default 3D placements.
        Extra assets passed in are appended at the end.

        Returns:
            SceneAssetManifest (Pydantic model, call .model_dump() for dict)
        """
        scene_data = self._get_scene_data(subject_code, topic_code)
        is_primary = scene_type == scene_data.get("primary_scene")
        raw_assets = (
            scene_data.get("primary_assets", [])
            if is_primary
            else scene_data.get("secondary_assets", [])
        )

        # Merge extra assets without duplication
        all_asset_ids = list(raw_assets)
        for ea in extra_assets or []:
            if ea not in all_asset_ids:
                all_asset_ids.append(ea)

        placements: List[AssetPlacement] = []
        for idx, asset_id in enumerate(all_asset_ids):
            # Spread assets in a shallow arc in front of the teacher
            x_offset = (idx - len(all_asset_ids) / 2) * 1.5
            placements.append(
                AssetPlacement(
                    asset_id=asset_id,
                    label=asset_id.replace("_", " ").title(),
                    position={"x": x_offset, "y": 0.0, "z": 3.0},
                    rotation={"x": 0.0, "y": 0.0, "z": 0.0},
                    scale=1.0,
                    interactive=idx < 3,  # First 3 assets are interactive
                    highlight_on_start=idx == 0,  # Highlight the primary asset
                    tooltip=f"Interact with {asset_id.replace('_', ' ')}",
                )
            )

        return SceneAssetManifest(
            scene_id=scene_type,
            assets=placements,
            ambient_sound=scene_data.get("ambient"),
            lighting_preset=scene_data.get("lighting", "day_natural"),
        )

    async def build_transition(
        self,
        from_scene: SceneType,
        to_scene: SceneType,
        topic_name: str = "",
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a SceneTransition including bridge dialogue.

        The bridge dialogue is the teacher's narration that bridges the two
        environments and maintains pedagogical continuity.

        Returns:
            SceneTransition as a dictionary
        """
        prompt = self._format_prompt(
            task=f"""Write a brief scene transition for a VR teaching session.

## Transition Details
- Moving from: {from_scene.value.replace("_", " ")}
- Moving to: {to_scene.value.replace("_", " ")}
- Topic being taught: {topic_name or "the current lesson"}
- Analogy context: {context or "real-world examples"}

## Instructions
Write 2-3 sentences of teacher dialogue that:
1. Naturally closes the current scene ("Great observations here at the cricket ground!")
2. Teases what the student will discover in the next scene
3. Maintains excitement and continuity

Also suggest a transition visual effect: one of fade_black, portal, dissolve, teleport.
Estimate the transition duration in seconds (1.5 – 4.0).""",
            output_format="""{
  "bridge_dialogue": "Excellent work spotting those patterns on the cricket ground! Now let's step into the physics lab where we can slow everything down and measure exactly what's happening. Ready to become a scientist?",
  "transition_effect": "portal",
  "duration_seconds": 2.5
}""",
        )

        result = await self._invoke_llm_json(prompt)

        return SceneTransition(
            from_scene=from_scene,
            to_scene=to_scene,
            transition_effect=result.get("transition_effect", "fade_black"),
            bridge_dialogue=result.get(
                "bridge_dialogue",
                f"Let's move to the next environment to explore {topic_name} further.",
            ),
            duration_seconds=float(result.get("duration_seconds", 2.0)),
        ).model_dump()

    def get_scene_for_topic(
        self,
        subject_code: str,
        topic_code: str,
    ) -> Dict[str, Any]:
        """
        Quick synchronous lookup — returns recommended scene type(s) for a topic.
        No LLM call required.

        Returns:
            dict with 'primary_scene', 'secondary_scene', and 'known' flag
        """
        scene_data = self._get_scene_data(subject_code, topic_code)
        primary = scene_data["primary_scene"]
        secondary = scene_data.get("secondary_scene")
        known = (
            subject_code in self.scene_kb and topic_code in self.scene_kb[subject_code]
        )

        return {
            "subject_code": subject_code,
            "topic_code": topic_code,
            "primary_scene": primary.value,
            "secondary_scene": secondary.value if secondary else None,
            "known": known,
        }

    # ========================= PRIVATE HELPERS =========================

    def _get_scene_data(self, subject_code: str, topic_code: str) -> Dict[str, Any]:
        """
        Retrieve scene knowledge base entry, falling back to the classroom default.
        """
        return self.scene_kb.get(subject_code, {}).get(topic_code, DEFAULT_SCENE_DATA)

    def get_asset_bindings(self, subject_code: str, topic_code: str) -> Dict[str, str]:
        """
        Return a mapping of {asset_id: prefab_path} for all assets in a topic's scene.

        Used by Agent E's VRToolRegistry to embed correct Unity prefab paths in
        generated C# scripts via [SerializeField] references.

        Convention:
            Assets/Prefabs/{SubjectCode}/{asset_id}.prefab

        Args:
            subject_code: e.g. "physics", "chemistry", "maths"
            topic_code:   e.g. "projectile_motion", "atomic_structure"

        Returns:
            dict mapping asset_id strings to Unity project-relative prefab paths.
        """
        scene_data = self._get_scene_data(subject_code, topic_code)
        all_assets = scene_data.get("primary_assets", []) + scene_data.get(
            "secondary_assets", []
        )
        subject_folder = subject_code.capitalize()
        return {
            asset_id: f"Assets/Prefabs/{subject_folder}/{asset_id}.prefab"
            for asset_id in all_assets
        }
