"""
Agent E: VR Instruction Agent (CRITICAL)

Purpose: Convert pedagogy and curriculum plans into VR-executable JSON instructions.
This is the ONLY output that Unity VR client consumes.

Inputs:
- CurriculumPlan from Agent C
- PedagogyPlan from Agent D
- Learner profile

Outputs:
- VRInstruction JSON packets for Unity
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from db.supabase_client import supabase_manager
from models.schemas import CurriculumPlan, PedagogyPlan
from models.vr_contracts import (
    AssessmentCommand,
    AssessmentType,
    AvatarAction,
    AvatarActionType,
    AvatarCharacter,
    InputMode,
    InteractionCommand,
    InteractionType,
    MotionType,
    SceneCommand,
    SceneType,
    VisualCommand,
    VoiceCommand,
    VoiceEmotion,
    VoicePace,
    VRInstruction,
    VRSession,
)


class VRInstructionAgent(BaseAgent):
    """
    Agent E: VR Instruction Agent.
    
    The critical bridge between AI planning and Unity VR execution.
    Converts high-level teaching plans into structured VR commands.
    
    Output is the strict JSON contract that Unity understands.
    """

    def __init__(self, temperature: float = 0.2):
        super().__init__(temperature=temperature)

    def _build_system_prompt(self) -> str:
        return """You are the VR Instruction Agent, responsible for creating immersive educational VR experiences.

Your role is to:
1. Convert teaching plans into VR-executable instructions
2. Design engaging, interactive VR sequences
3. Control avatar actions, voice, visuals, and interactions
4. Create assessment checkpoints within VR

You output structured JSON that the Unity VR client directly executes."""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method.
        
        Actions:
        - 'create_session': Create a new VR teaching session
        - 'generate_lesson': Generate VR instructions for a lesson
        - 'generate_step': Generate a single VR instruction step
        - 'generate_assessment': Generate VR assessment instructions
        """
        action = input_data.get("action")
        
        if action == "create_session":
            return await self.create_session(
                student_id=input_data["student_id"],
                curriculum_plan=input_data["curriculum_plan"],
                pedagogy_plan=input_data["pedagogy_plan"],
            )
        elif action == "generate_lesson":
            return await self.generate_lesson_instructions(
                curriculum_plan=input_data["curriculum_plan"],
                pedagogy_plan=input_data["pedagogy_plan"],
            )
        elif action == "generate_step":
            return self.generate_instruction_step(
                step_type=input_data["step_type"],
                content=input_data["content"],
                **input_data.get("options", {}),
            )
        elif action == "generate_assessment":
            return self.generate_assessment_instructions(
                questions=input_data["questions"],
                assessment_type=input_data.get("assessment_type", "concept_check"),
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    async def create_session(
        self,
        student_id: str,
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new VR teaching session.
        
        Returns:
            VRSession with all instructions
        """
        # Generate lesson instructions
        instructions = await self.generate_lesson_instructions(
            curriculum_plan=curriculum_plan,
            pedagogy_plan=pedagogy_plan,
        )
        
        session = VRSession(
            session_id=str(uuid.uuid4()),
            student_id=student_id,
            topic=curriculum_plan.get("topic_code", "unknown"),
            subject=curriculum_plan.get("subject_code", "unknown"),
            instructions=instructions.get("instructions", []),
            total_steps=len(instructions.get("instructions", [])),
        )
        
        return session.model_dump()

    async def generate_lesson_instructions(
        self,
        curriculum_plan: Dict[str, Any],
        pedagogy_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a complete sequence of VR instructions for a lesson.
        
        Uses LLM to create an engaging lesson flow based on:
        - Topic and subtopics
        - Teaching approach
        - Analogy and visualization
        """
        topic = curriculum_plan.get("topic_name") or curriculum_plan.get("topic_code")
        subject = curriculum_plan.get("subject_code", "").upper()
        
        prompt = self._format_prompt(
            task=f"""Create a VR lesson sequence for teaching "{topic}" in Class 10 {subject}.

## Curriculum Plan
- Topic: {topic}
- Subtopics: {curriculum_plan.get('subtopics', [])}
- Duration: {curriculum_plan.get('estimated_duration_minutes', 30)} minutes
- Depth: {curriculum_plan.get('depth', 'conceptual+visual')}

## Pedagogy Plan
- Approach: {pedagogy_plan.get('approach', 'intuition-first')}
- Analogy: {pedagogy_plan.get('analogy', 'N/A')}
- Scene: {pedagogy_plan.get('recommended_scene', 'classroom')}
- Key objects: {pedagogy_plan.get('key_objects', [])}
- Interaction points: {pedagogy_plan.get('interaction_points', [])}

## VR Lesson Structure
Create 6-10 instruction steps following this flow:
1. Introduction (welcome, topic overview)
2. Hook (engaging analogy/demonstration)
3. Core Concept 1 (with visualization)
4. Interaction 1 (student practice)
5. Core Concept 2 (build on first)
6. Interaction 2 (deeper practice)
7. Concept Check (quick assessment)
8. Summary & Next Steps

For each step, specify:
- step_type: "intro", "explanation", "demonstration", "interaction", "assessment", "summary"
- avatar_action: "greet", "explain", "point", "demonstrate", "question", "encourage", "wave"
- voice_text: What the teacher says
- voice_emotion: "friendly", "excited", "calm", "encouraging"
- visual_objects: Objects to show/animate
- interaction_type: null or "slider", "button", "grab", "voice_input"
""",
            output_format="""{
  "lesson_title": "Understanding Projectile Motion",
  "steps": [
    {
      "step_type": "intro",
      "avatar_action": "greet",
      "voice_text": "Welcome! Today we'll discover why cricket sixes make such beautiful arcs!",
      "voice_emotion": "friendly",
      "visual_objects": [],
      "interaction_type": null
    },
    {
      "step_type": "demonstration",
      "avatar_action": "point",
      "voice_text": "Watch this ball's path when we throw it at different angles",
      "voice_emotion": "excited",
      "visual_objects": ["ball", "trajectory_arc", "angle_indicator"],
      "motion": {"object": "ball", "type": "projectile", "angle": 45}
    }
  ]
}"""
        )

        result = await self._invoke_llm_json(prompt)
        
        # Convert to VRInstruction objects
        instructions = []
        for i, step in enumerate(result.get("steps", [])):
            instruction = self._step_to_instruction(
                step_num=i + 1,
                step_data=step,
                scene=pedagogy_plan.get("recommended_scene", "virtual_classroom"),
            )
            instructions.append(instruction.model_dump())
        
        return {
            "lesson_title": result.get("lesson_title", topic),
            "instructions": instructions,
            "total_steps": len(instructions),
            "estimated_duration_minutes": curriculum_plan.get("estimated_duration_minutes", 30),
        }

    def _step_to_instruction(
        self,
        step_num: int,
        step_data: Dict[str, Any],
        scene: str,
    ) -> VRInstruction:
        """Convert a step dictionary to VRInstruction object."""
        
        # Map step types to avatar actions
        action_map = {
            "greet": AvatarActionType.GREET,
            "explain": AvatarActionType.EXPLAIN,
            "point": AvatarActionType.POINT,
            "demonstrate": AvatarActionType.DEMONSTRATE,
            "question": AvatarActionType.QUESTION,
            "encourage": AvatarActionType.ENCOURAGE,
            "celebrate": AvatarActionType.CELEBRATE,
            "wave": AvatarActionType.WAVE,
            "think": AvatarActionType.THINK,
        }
        
        emotion_map = {
            "friendly": VoiceEmotion.FRIENDLY,
            "excited": VoiceEmotion.EXCITED,
            "calm": VoiceEmotion.CALM,
            "encouraging": VoiceEmotion.ENCOURAGING,
            "serious": VoiceEmotion.SERIOUS,
        }
        
        interaction_map = {
            "slider": InteractionType.SLIDER,
            "button": InteractionType.BUTTON,
            "grab": InteractionType.GRAB,
            "voice_input": InteractionType.VOICE_INPUT,
            "multiple_choice": InteractionType.MULTIPLE_CHOICE,
        }
        
        # Build avatar action
        avatar_action_str = step_data.get("avatar_action", "explain")
        avatar = AvatarAction(
            action=action_map.get(avatar_action_str, AvatarActionType.EXPLAIN),
        )
        
        # Build voice command
        voice = VoiceCommand(
            text=step_data.get("voice_text", ""),
            emotion=emotion_map.get(step_data.get("voice_emotion", "friendly"), VoiceEmotion.FRIENDLY),
        )
        
        # Build visual command if objects present
        visual = None
        if step_data.get("visual_objects"):
            motion_data = step_data.get("motion", {})
            visual = VisualCommand(
                objects=step_data["visual_objects"],
                motion=MotionType(motion_data.get("type", "static")) if motion_data.get("type") else None,
                highlight=motion_data.get("highlight"),
            )
        
        # Build interaction command if present
        interaction = None
        if step_data.get("interaction_type"):
            interaction = InteractionCommand(
                type=interaction_map.get(step_data["interaction_type"], InteractionType.BUTTON),
                target=step_data.get("interaction_target", "parameter"),
                prompt=step_data.get("interaction_prompt", "Try adjusting this!"),
            )
        
        # Build scene command for first step
        scene_cmd = None
        if step_num == 1:
            scene_cmd = SceneCommand(
                scene_id=scene,
                scene_type=SceneType.LESSON,
            )
        
        return VRInstruction(
            step_id=f"step_{step_num:03d}",
            avatar=avatar,
            voice=voice,
            visual=visual,
            interaction=interaction,
            scene=scene_cmd,
        )

    def generate_instruction_step(
        self,
        step_type: str,
        content: str,
        emotion: str = "friendly",
        objects: Optional[List[str]] = None,
        interaction_type: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a single VR instruction step.
        
        Args:
            step_type: Type of step (intro, explanation, demonstration, etc.)
            content: The spoken content
            emotion: Voice emotion
            objects: Visual objects to display
            interaction_type: Type of interaction if any
        """
        action_for_type = {
            "intro": AvatarActionType.GREET,
            "explanation": AvatarActionType.EXPLAIN,
            "demonstration": AvatarActionType.DEMONSTRATE,
            "interaction": AvatarActionType.QUESTION,
            "assessment": AvatarActionType.QUESTION,
            "summary": AvatarActionType.WAVE,
        }
        
        emotion_map = {
            "friendly": VoiceEmotion.FRIENDLY,
            "excited": VoiceEmotion.EXCITED,
            "calm": VoiceEmotion.CALM,
            "encouraging": VoiceEmotion.ENCOURAGING,
        }
        
        instruction = VRInstruction(
            step_id=str(uuid.uuid4())[:8],
            avatar=AvatarAction(
                action=action_for_type.get(step_type, AvatarActionType.EXPLAIN),
            ),
            voice=VoiceCommand(
                text=content,
                emotion=emotion_map.get(emotion, VoiceEmotion.FRIENDLY),
            ),
            visual=VisualCommand(objects=objects) if objects else None,
            interaction=InteractionCommand(
                type=InteractionType(interaction_type),
                prompt=kwargs.get("interaction_prompt", "Your turn!"),
            ) if interaction_type else None,
        )
        
        return instruction.model_dump()

    def generate_assessment_instructions(
        self,
        questions: List[Dict[str, Any]],
        assessment_type: str = "concept_check",
    ) -> Dict[str, Any]:
        """
        Generate VR instructions for in-lesson assessments.
        
        Returns a sequence of VR instructions that presents questions
        and collects responses.
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
                step_id=f"assess_q{i+1}",
                avatar=AvatarAction(action=AvatarActionType.QUESTION),
                voice=VoiceCommand(
                    text=q.get("question_text", ""),
                    emotion=VoiceEmotion.CALM,
                ),
                assessment=AssessmentCommand(
                    type=type_map.get(assessment_type, AssessmentType.MCQ),
                    question_id=q.get("question_id", f"q{i+1}"),
                    options=q.get("options"),
                    input_mode=InputMode.GAZE if q.get("question_type") == "mcq" else InputMode.VOICE,
                    time_limit_seconds=q.get("time_limit", 60),
                ),
            )
            instructions.append(question_step.model_dump())
        
        # Completion step
        done = VRInstruction(
            step_id="assess_done",
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
