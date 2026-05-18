"""
Agent Orchestrator - Coordinates all agents for the VR Teaching System.

This is the main entry point for the multi-agent system.
It manages the flow of information between agents and maintains session state.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from agents.assessment_agent import AssessmentAgent
from agents.curriculum_agent import CurriculumAgent
from agents.evaluation_agent import EvaluationAgent
from agents.learner_profile_agent import LearnerProfileAgent
from agents.pedagogy_agent import PedagogyAgent
from agents.scene_builder_agent import SceneBuilderAgent
from agents.vr_instruction_agent import VRInstructionAgent
from db.supabase_client import supabase_manager
from models.schemas import AssessmentStage


class AgentOrchestrator:
    """
    Orchestrates the multi-agent system for personalized VR teaching.

    Flow:
    1. Agent A (Assessment) → Evaluate student
    2. Agent B (Profile) → Update learner profile
    3. Agent C (Curriculum) → Decide what to teach
    4. Agent D (Pedagogy) → Decide how to teach
    5. Agent E (VR) → Author Lesson Manifest (components + state machine JSON)
    6. Agent F (Evaluation) → Provide feedback (during/after)
    7. Agent G (SceneBuilder) → Generate VR scene descriptions (legacy, optional)
    """

    def __init__(self):
        self.assessment_agent = AssessmentAgent()
        self.profile_agent = LearnerProfileAgent()
        self.curriculum_agent = CurriculumAgent()
        self.pedagogy_agent = PedagogyAgent()
        self.scene_builder = SceneBuilderAgent()
        self.vr_agent = VRInstructionAgent()
        self.evaluation_agent = EvaluationAgent()

    async def start_session(
        self,
        student_id: str,
        subject_code: str,
    ) -> Dict[str, Any]:
        """
        Start a new learning session for a student.

        This is the main entry point that coordinates all agents.

        Returns:
            Complete VR session with instructions
        """
        session_id = str(uuid.uuid4())

        # Step 1: Get current learner profile (Agent B)
        profile_result = await self.profile_agent.process(
            {
                "action": "get_profile",
                "student_id": student_id,
            }
        )

        if "error" in profile_result:
            return {"error": profile_result["error"], "session_id": session_id}

        # Step 2: Determine what to teach (Agent C - Curriculum)
        curriculum_result = await self.curriculum_agent.process(
            {
                "action": "get_next_topic",
                "student_id": student_id,
                "subject_code": subject_code,
            }
        )

        if (
            "message" in curriculum_result
            and "All topics mastered" in curriculum_result.get("message", "")
        ):
            return {
                "session_id": session_id,
                "status": "completed",
                "message": curriculum_result["message"],
            }

        # Step 3: Determine how to teach (Agent D - Pedagogy)
        pedagogy_result = await self.pedagogy_agent.process(
            {
                "action": "get_teaching_plan",
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": curriculum_result.get("topic_code"),
                "topic_name": curriculum_result.get("topic_name"),
            }
        )

        # Step 4: Generate actual teaching content
        lesson_content = await self.pedagogy_agent.generate_lesson_content(
            topic_name=curriculum_result.get("topic_name", ""),
            subject_code=subject_code,
            subtopics=curriculum_result.get("subtopics", []),
            pedagogy_plan=pedagogy_result,
            learning_style=profile_result.get("learning_style"),
        )

        return {
            "session_id": session_id,
            "status": "ready",
            "topic": curriculum_result.get("topic_name"),
            "subject": subject_code,
            "curriculum_plan": curriculum_result,
            "pedagogy_plan": pedagogy_result,
            "lesson_content": lesson_content,
        }

    async def run_initial_assessment(
        self,
        student_id: str,
        subject_code: str,
        topic_code: Optional[str] = None,
        topic_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run an initial diagnostic assessment for a student.

        Returns:
            Assessment questions and session info
        """
        # Get VR analogy context for visual question enrichment
        analogy_context = None
        if topic_code:
            analogy_context = self.pedagogy_agent.get_vr_elements(
                subject_code, topic_code
            )

        # Generate diagnostic questions (Agent A)
        questions_result = await self.assessment_agent.process(
            {
                "action": "generate_questions",
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": topic_name,
                "stage": AssessmentStage.INITIAL.value,
                "analogy_context": analogy_context,
            }
        )

        return {
            "assessment_id": str(uuid.uuid4()),
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "questions": questions_result.get("questions", []),
            "total_marks": questions_result.get("total_marks", 0),
            "estimated_time_minutes": questions_result.get(
                "estimated_time_minutes", 15
            ),
        }

    async def submit_assessment(
        self,
        student_id: str,
        assessment_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str],
        questions: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Submit assessment responses and get results.

        Returns:
            Assessment result with feedback
        """
        # Step 1: Evaluate MCQ answers (Agent A)
        mcq_result = await self.assessment_agent.process(
            {
                "action": "evaluate_mcq",
                "questions": questions,
                "responses": responses,
            }
        )

        # Step 2: Evaluate descriptive answers (Agent A)
        descriptive_results = []
        for q in questions:
            if q["question_type"] in ["descriptive", "numerical"]:
                response = next(
                    (r for r in responses if r["question_id"] == q["question_id"]), None
                )
                if response:
                    eval_result = await self.assessment_agent.process(
                        {
                            "action": "evaluate_descriptive",
                            "question": q,
                            "student_answer": response["answer"],
                        }
                    )
                    descriptive_results.append(eval_result)

        # Step 3: Identify misconceptions (Agent A)
        misconceptions = {}
        if mcq_result.get("wrong_answers"):
            misconceptions = await self.assessment_agent.process(
                {
                    "action": "identify_misconceptions",
                    "topic_name": topic_name or topic_code,
                    "wrong_answers": mcq_result["wrong_answers"],
                }
            )

        # Step 4: Calculate final result (Agent A)
        assessment_result = await self.assessment_agent.process(
            {
                "action": "calculate_result",
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": topic_name,
                "evaluations": {
                    "mcq_results": mcq_result,
                    "descriptive_results": descriptive_results,
                    "misconceptions": misconceptions,
                },
            }
        )

        # Step 5: Update learner profile (Agent B)
        await self.profile_agent.process(
            {
                "action": "update_from_assessment",
                "student_id": student_id,
                "assessment_result": assessment_result,
            }
        )

        # Step 6: Store assessment in database
        await supabase_manager.store_assessment(
            result=type("Obj", (), assessment_result)()  # Convert dict to object-like
        )

        # Step 7: Get remediation if needed (Agent F)
        remediation = None
        if assessment_result.get("misconceptions"):
            remediation = await self.evaluation_agent.process(
                {
                    "action": "get_remediation",
                    "student_id": student_id,
                    "misconceptions": assessment_result["misconceptions"],
                }
            )

        return {
            "assessment_id": assessment_id,
            "result": assessment_result,
            "remediation": remediation,
        }

    async def get_learning_path(
        self,
        student_id: str,
        subject_code: str,
    ) -> Dict[str, Any]:
        """
        Get the complete learning path for a student in a subject.
        """
        return await self.curriculum_agent.process(
            {
                "action": "get_learning_path",
                "student_id": student_id,
                "subject_code": subject_code,
            }
        )

    async def generate_exam(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str] = None,
        num_questions: int = 10,
    ) -> Dict[str, Any]:
        """
        Generate an exam for a topic.
        """
        # Get VR analogy context for visual question enrichment
        analogy_context = self.pedagogy_agent.get_vr_elements(subject_code, topic_code)

        return await self.evaluation_agent.process(
            {
                "action": "generate_exam",
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": topic_name,
                "num_questions": num_questions,
                "analogy_context": analogy_context,
            }
        )

    async def grade_exam(
        self,
        exam: Dict[str, Any],
        responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Grade an exam and provide feedback.
        """
        return await self.evaluation_agent.process(
            {
                "action": "evaluate_exam",
                "exam": exam,
                "responses": responses,
            }
        )

    async def get_student_recommendations(
        self,
        student_id: str,
    ) -> Dict[str, Any]:
        """
        Get personalized learning recommendations for a student.
        """
        return await self.profile_agent.process(
            {
                "action": "get_recommendations",
                "student_id": student_id,
            }
        )

    async def run_onboarding_assessment(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
    ) -> Dict[str, Any]:
        """
        Run an onboarding assessment for a student on a specific topic.

        Generates diagnostic questions for the given topic to establish
        baseline knowledge.

        Returns:
            Assessment with questions covering the specified topic
        """
        # Get syllabus to find the topic
        syllabus = self.curriculum_agent.get_syllabus(subject_code)
        if "error" in syllabus:
            return syllabus

        # Find the specific topic
        all_topics = syllabus.get("topics", [])
        target_topic = None
        for t in all_topics:
            if t["topic_code"] == topic_code:
                target_topic = t
                break

        if not target_topic:
            return {
                "error": f"Topic '{topic_code}' not found in subject '{subject_code}'"
            }

        # Generate diagnostic questions for this topic
        all_questions = []
        total_marks = 0

        # Get VR analogy context for visual question enrichment
        analogy_context = self.pedagogy_agent.get_vr_elements(
            subject_code, target_topic["topic_code"]
        )

        questions_result = await self.assessment_agent.process(
            {
                "action": "generate_questions",
                "subject_code": subject_code,
                "topic_code": target_topic["topic_code"],
                "topic_name": target_topic["topic_name"],
                "stage": AssessmentStage.INITIAL.value,
                "context": f"Generate 20-25 diagnostic questions for onboarding on topic: {target_topic['topic_name']}. Cover subtopics thoroughly: {', '.join(target_topic.get('subtopics', []))}. Ensure broad coverage across all subtopics.",
                "analogy_context": analogy_context,
            }
        )

        for q in questions_result.get("questions", []):
            q["source_topic"] = target_topic["topic_code"]
            all_questions.append(q)
            total_marks += q.get("max_marks", 1)

        return {
            "assessment_id": str(uuid.uuid4()),
            "assessment_type": "onboarding",
            "student_id": student_id,
            "subject_code": subject_code,
            "subject_name": syllabus.get("subject_name"),
            "topic_code": target_topic["topic_code"],
            "topic_name": target_topic["topic_name"],
            "questions": all_questions,
            "total_marks": total_marks,
            "total_questions": len(all_questions),
            "topics_covered": [target_topic["topic_code"]],
            "estimated_time_minutes": max(10, len(all_questions) * 2),
        }

    async def submit_onboarding_assessment(
        self,
        student_id: str,
        assessment_id: str,
        subject_code: str,
        topic_code: str,
        questions: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Submit onboarding assessment for a specific topic and get results.

        Returns:
            Profile update + topic score + recommended learning path
        """
        # Evaluate MCQ answers
        mcq_result = await self.assessment_agent.process(
            {
                "action": "evaluate_mcq",
                "questions": questions,
                "responses": responses,
            }
        )

        percentage = mcq_result.get("percentage", 0)
        topic_scores = {
            topic_code: {
                "score": percentage,
                "correct": mcq_result.get("correct_count", 0),
                "total": mcq_result.get("total_questions", 0),
            }
        }

        # Classify topic strength
        all_weak_topics = []
        all_strong_topics = []
        if percentage >= 70:
            all_strong_topics.append(topic_code)
        elif percentage < 40:
            all_weak_topics.append(topic_code)

        # Update profile with results
        await self.profile_agent.process(
            {
                "action": "update_from_assessment",
                "student_id": student_id,
                "assessment_result": {
                    "subject_code": subject_code,
                    "topic_code": topic_code,
                    "weak_concepts": all_weak_topics,
                    "strong_concepts": all_strong_topics,
                },
            }
        )

        # Get personalized learning path
        learning_path = await self.curriculum_agent.process(
            {
                "action": "get_learning_path",
                "student_id": student_id,
                "subject_code": subject_code,
            }
        )

        return {
            "assessment_id": assessment_id,
            "topic_code": topic_code,
            "profile_updated": True,
            "topic_scores": topic_scores,
            "overall_percentage": percentage,
            "strong_topics": all_strong_topics,
            "weak_topics": all_weak_topics,
            "learning_path": learning_path,
        }

    async def generate_teaching_content(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate complete teaching content for a topic with VR instructions.

        This is the main content delivery endpoint.

        Returns:
            Lesson content with pedagogy plan and VR session
        """
        # Get learner profile
        profile_result = await self.profile_agent.process(
            {
                "action": "get_profile",
                "student_id": student_id,
            }
        )

        # Get curriculum plan for the topic
        curriculum_plan = {
            "topic_code": topic_code,
            "topic_name": topic_name or topic_code,
            "subject_code": subject_code,
            "depth": "conceptual+visual",
            "subtopics": [],
        }

        # Get syllabus details for the topic
        syllabus = self.curriculum_agent.get_syllabus(subject_code)
        if "topics" in syllabus:
            for t in syllabus["topics"]:
                if t["topic_code"] == topic_code:
                    curriculum_plan["subtopics"] = t.get("subtopics", [])
                    curriculum_plan["topic_name"] = t.get("topic_name", topic_name)
                    curriculum_plan["estimated_duration_minutes"] = t.get(
                        "estimated_minutes", 30
                    )
                    break

        # Get pedagogy plan (how to teach)
        pedagogy_result = await self.pedagogy_agent.process(
            {
                "action": "get_teaching_plan",
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": curriculum_plan["topic_name"],
            }
        )

        # Generate actual lesson content
        lesson_content = await self.pedagogy_agent.generate_lesson_content(
            topic_name=curriculum_plan["topic_name"],
            subject_code=subject_code,
            subtopics=curriculum_plan.get("subtopics", []),
            pedagogy_plan=pedagogy_result,
            learning_style=profile_result.get("learning_style"),
        )

        # Build VR scene plan (Agent G)
        lesson_id = str(uuid.uuid4())
        scene_plan = await self.scene_builder.process(
            {
                "action": "build_scene",
                "session_id": lesson_id,
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": curriculum_plan["topic_name"],
                "pedagogy_plan": pedagogy_result,
                "learner_profile": profile_result,
            }
        )

        return {
            "lesson_id": lesson_id,
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": curriculum_plan["topic_name"],
            "curriculum_plan": curriculum_plan,
            "pedagogy_plan": pedagogy_result,
            "lesson_content": lesson_content,
            "scene_plan": scene_plan,
            "learning_style": profile_result.get("learning_style"),
        }

    def get_syllabus(self, subject_code: str) -> Dict[str, Any]:
        """Get syllabus for a subject."""
        return self.curriculum_agent.get_syllabus(subject_code)

    # ========================================================================
    # STREAMING METHODS (async generators yielding progress events)
    # ========================================================================

    async def run_onboarding_assessment_stream(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
    ):
        """Stream onboarding assessment generation for a specific topic."""
        yield {"event": "progress", "step": "Loading syllabus...", "progress": 5}

        syllabus = self.curriculum_agent.get_syllabus(subject_code)
        if "error" in syllabus:
            yield {"event": "error", "error": syllabus["error"]}
            return

        # Find the specific topic
        all_topics = syllabus.get("topics", [])
        target_topic = None
        for t in all_topics:
            if t["topic_code"] == topic_code:
                target_topic = t
                break

        if not target_topic:
            yield {
                "event": "error",
                "error": f"Topic '{topic_code}' not found in subject '{subject_code}'",
            }
            return

        yield {
            "event": "progress",
            "step": f"Generating questions for {target_topic['topic_name']}...",
            "progress": 20,
        }

        all_questions = []
        total_marks = 0

        # Get VR analogy context for visual question enrichment
        analogy_context = self.pedagogy_agent.get_vr_elements(
            subject_code, target_topic["topic_code"]
        )

        questions_result = await self.assessment_agent.process(
            {
                "action": "generate_questions",
                "subject_code": subject_code,
                "topic_code": target_topic["topic_code"],
                "topic_name": target_topic["topic_name"],
                "stage": AssessmentStage.INITIAL.value,
                "context": f"Generate 20-25 diagnostic questions for onboarding on topic: {target_topic['topic_name']}. Cover subtopics thoroughly: {', '.join(target_topic.get('subtopics', []))}. Ensure broad coverage across all subtopics.",
                "analogy_context": analogy_context,
            }
        )

        for q in questions_result.get("questions", []):
            q["source_topic"] = target_topic["topic_code"]
            all_questions.append(q)
            total_marks += q.get("max_marks", 1)

        yield {
            "event": "progress",
            "step": f"✓ {target_topic['topic_name']} — {len(all_questions)} questions generated",
            "progress": 80,
        }

        result = {
            "assessment_id": str(uuid.uuid4()),
            "assessment_type": "onboarding",
            "student_id": student_id,
            "subject_code": subject_code,
            "subject_name": syllabus.get("subject_name"),
            "topic_code": target_topic["topic_code"],
            "topic_name": target_topic["topic_name"],
            "questions": all_questions,
            "total_marks": total_marks,
            "total_questions": len(all_questions),
            "topics_covered": [target_topic["topic_code"]],
            "estimated_time_minutes": max(10, len(all_questions) * 2),
        }

        yield {"event": "result", "data": result, "progress": 100}

    async def submit_onboarding_stream(
        self,
        student_id: str,
        assessment_id: str,
        subject_code: str,
        topic_code: str,
        questions: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ):
        """Stream onboarding submission for a specific topic with progress events."""
        yield {
            "event": "progress",
            "step": f"Evaluating {topic_code}...",
            "progress": 10,
        }

        # Evaluate MCQ answers
        mcq_result = await self.assessment_agent.process(
            {
                "action": "evaluate_mcq",
                "questions": questions,
                "responses": responses,
            }
        )

        percentage = mcq_result.get("percentage", 0)
        topic_scores = {
            topic_code: {
                "score": percentage,
                "correct": mcq_result.get("correct_count", 0),
                "total": mcq_result.get("total_questions", 0),
            }
        }

        # Classify topic strength
        all_weak_topics = []
        all_strong_topics = []
        if percentage >= 70:
            all_strong_topics.append(topic_code)
        elif percentage < 40:
            all_weak_topics.append(topic_code)

        yield {
            "event": "progress",
            "step": "Updating learner profile...",
            "progress": 50,
        }

        await self.profile_agent.process(
            {
                "action": "update_from_assessment",
                "student_id": student_id,
                "assessment_result": {
                    "subject_code": subject_code,
                    "topic_code": topic_code,
                    "weak_concepts": all_weak_topics,
                    "strong_concepts": all_strong_topics,
                },
            }
        )

        yield {
            "event": "progress",
            "step": "Generating learning path...",
            "progress": 75,
        }

        learning_path = await self.curriculum_agent.process(
            {
                "action": "get_learning_path",
                "student_id": student_id,
                "subject_code": subject_code,
            }
        )

        result = {
            "assessment_id": assessment_id,
            "topic_code": topic_code,
            "profile_updated": True,
            "topic_scores": topic_scores,
            "overall_percentage": percentage,
            "strong_topics": all_strong_topics,
            "weak_topics": all_weak_topics,
            "learning_path": learning_path,
        }

        yield {"event": "result", "data": result, "progress": 100}

    async def start_session_stream(
        self,
        student_id: str,
        subject_code: str,
    ):
        """Stream session start with progress events."""
        session_id = str(uuid.uuid4())

        yield {
            "event": "progress",
            "step": "Loading learner profile...",
            "progress": 10,
        }

        profile_result = await self.profile_agent.process(
            {
                "action": "get_profile",
                "student_id": student_id,
            }
        )

        if "error" in profile_result:
            yield {"event": "error", "error": profile_result["error"]}
            return

        yield {"event": "progress", "step": "Determining next topic...", "progress": 30}

        curriculum_result = await self.curriculum_agent.process(
            {
                "action": "get_next_topic",
                "student_id": student_id,
                "subject_code": subject_code,
            }
        )

        if (
            "message" in curriculum_result
            and "All topics mastered" in curriculum_result.get("message", "")
        ):
            yield {
                "event": "result",
                "data": {
                    "session_id": session_id,
                    "status": "completed",
                    "message": curriculum_result["message"],
                },
                "progress": 100,
            }
            return

        yield {
            "event": "progress",
            "step": f"Planning pedagogy for {curriculum_result.get('topic_name', '')}...",
            "progress": 55,
        }

        pedagogy_result = await self.pedagogy_agent.process(
            {
                "action": "get_teaching_plan",
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": curriculum_result.get("topic_code"),
                "topic_name": curriculum_result.get("topic_name"),
            }
        )

        yield {
            "event": "progress",
            "step": "Generating lesson content...",
            "progress": 75,
        }

        lesson_content = await self.pedagogy_agent.generate_lesson_content(
            topic_name=curriculum_result.get("topic_name", ""),
            subject_code=subject_code,
            subtopics=curriculum_result.get("subtopics", []),
            pedagogy_plan=pedagogy_result,
            learning_style=profile_result.get("learning_style"),
        )

        result = {
            "session_id": session_id,
            "status": "ready",
            "topic": curriculum_result.get("topic_name"),
            "subject": subject_code,
            "curriculum_plan": curriculum_result,
            "pedagogy_plan": pedagogy_result,
            "lesson_content": lesson_content,
        }

        yield {"event": "result", "data": result, "progress": 100}

    async def generate_teaching_content_stream(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str] = None,
    ):
        """
        Stream teaching content generation with ACTUAL content chunks.

        Events emitted (in order):
        - profile:       learner profile data
        - curriculum:    curriculum plan
        - pedagogy:      pedagogy plan (analogy, approach, strategies)
        - section:       one event per lesson section (subtopic content)
        - scene_preload: {environment_id, theme, teacher_greeting} — Unity loads scene now
        - progress:      "Authoring lesson manifest..."
        - manifest:      full LessonManifest JSON — Unity walks state machine
        - complete:      summary metadata
        """
        # 1. Load learner profile
        profile_result = await self.profile_agent.process(
            {
                "action": "get_profile",
                "student_id": student_id,
            }
        )
        yield {"event": "profile", "data": profile_result}

        # 2. Build curriculum plan
        curriculum_plan = {
            "topic_code": topic_code,
            "topic_name": topic_name or topic_code,
            "subject_code": subject_code,
            "depth": "conceptual+visual",
            "subtopics": [],
        }

        syllabus = self.curriculum_agent.get_syllabus(subject_code)
        if "topics" in syllabus:
            for t in syllabus["topics"]:
                if t["topic_code"] == topic_code:
                    curriculum_plan["subtopics"] = t.get("subtopics", [])
                    curriculum_plan["topic_name"] = t.get("topic_name", topic_name)
                    curriculum_plan["estimated_duration_minutes"] = t.get(
                        "estimated_minutes", 30
                    )
                    break

        yield {"event": "curriculum", "data": curriculum_plan}

        # 3. Generate pedagogy plan
        pedagogy_result = await self.pedagogy_agent.process(
            {
                "action": "get_teaching_plan",
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": curriculum_plan["topic_name"],
            }
        )
        yield {"event": "pedagogy", "data": pedagogy_result}

        # 4. Generate lesson content and stream each section
        lesson_content = await self.pedagogy_agent.generate_lesson_content(
            topic_name=curriculum_plan["topic_name"],
            subject_code=subject_code,
            subtopics=curriculum_plan.get("subtopics", []),
            pedagogy_plan=pedagogy_result,
            learning_style=profile_result.get("learning_style"),
        )

        # Yield each section individually
        sections = lesson_content.get("sections", [])
        for idx, section in enumerate(sections):
            yield {
                "event": "section",
                "data": section,
                "index": idx,
                "total": len(sections),
            }

        # 5. Agent E: author the lesson manifest (scene_preload → manifest)
        lesson_id = str(uuid.uuid4())
        student_name = profile_result.get("name") or profile_result.get("display_name", student_id)

        async for event in self.vr_agent.author_manifest_stream(
            session_id=lesson_id,
            student_id=student_id,
            student_name=student_name,
            curriculum_plan={**curriculum_plan, "session_id": lesson_id, "student_id": student_id},
            pedagogy_plan=pedagogy_result,
            learner_profile=profile_result,
        ):
            yield event

        # 6. Final completion event
        yield {
            "event": "complete",
            "data": {
                "lesson_id": lesson_id,
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": curriculum_plan["topic_name"],
                "learning_style": profile_result.get("learning_style"),
                "total_sections": len(sections),
            },
        }

    async def generate_assessment_stream(
        self,
        student_id: str,
        subject_code: str,
        topic_code: Optional[str] = None,
        topic_name: Optional[str] = None,
    ):
        """Stream assessment generation with progress events."""
        yield {
            "event": "progress",
            "step": "Generating diagnostic questions...",
            "progress": 20,
        }

        # Get VR analogy context for visual question enrichment
        analogy_context = None
        if topic_code:
            analogy_context = self.pedagogy_agent.get_vr_elements(
                subject_code, topic_code
            )

        questions_result = await self.assessment_agent.process(
            {
                "action": "generate_questions",
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": topic_name,
                "stage": AssessmentStage.INITIAL.value,
                "analogy_context": analogy_context,
            }
        )

        result = {
            "assessment_id": str(uuid.uuid4()),
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "questions": questions_result.get("questions", []),
            "total_marks": questions_result.get("total_marks", 0),
            "estimated_time_minutes": questions_result.get(
                "estimated_time_minutes", 15
            ),
        }

        yield {"event": "result", "data": result, "progress": 100}

    async def submit_assessment_stream(
        self,
        student_id: str,
        assessment_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str],
        questions: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ):
        """Stream assessment submission with progress events."""
        yield {"event": "progress", "step": "Evaluating MCQ answers...", "progress": 10}

        mcq_result = await self.assessment_agent.process(
            {
                "action": "evaluate_mcq",
                "questions": questions,
                "responses": responses,
            }
        )

        yield {
            "event": "progress",
            "step": "Evaluating descriptive answers...",
            "progress": 30,
        }

        descriptive_results = []
        for q in questions:
            if q["question_type"] in ["descriptive", "numerical"]:
                response = next(
                    (r for r in responses if r["question_id"] == q["question_id"]), None
                )
                if response:
                    eval_result = await self.assessment_agent.process(
                        {
                            "action": "evaluate_descriptive",
                            "question": q,
                            "student_answer": response["answer"],
                        }
                    )
                    descriptive_results.append(eval_result)

        yield {
            "event": "progress",
            "step": "Identifying misconceptions...",
            "progress": 50,
        }

        misconceptions = {}
        if mcq_result.get("wrong_answers"):
            misconceptions = await self.assessment_agent.process(
                {
                    "action": "identify_misconceptions",
                    "topic_name": topic_name or topic_code,
                    "wrong_answers": mcq_result["wrong_answers"],
                }
            )

        yield {
            "event": "progress",
            "step": "Calculating final result...",
            "progress": 65,
        }

        assessment_result = await self.assessment_agent.process(
            {
                "action": "calculate_result",
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": topic_name,
                "evaluations": {
                    "mcq_results": mcq_result,
                    "descriptive_results": descriptive_results,
                    "misconceptions": misconceptions,
                },
            }
        )

        yield {
            "event": "progress",
            "step": "Updating learner profile...",
            "progress": 80,
        }

        await self.profile_agent.process(
            {
                "action": "update_from_assessment",
                "student_id": student_id,
                "assessment_result": assessment_result,
            }
        )

        yield {"event": "progress", "step": "Storing assessment...", "progress": 85}

        await supabase_manager.store_assessment(
            result=type("Obj", (), assessment_result)()
        )

        remediation = None
        if assessment_result.get("misconceptions"):
            yield {
                "event": "progress",
                "step": "Getting remediation suggestions...",
                "progress": 92,
            }
            remediation = await self.evaluation_agent.process(
                {
                    "action": "get_remediation",
                    "student_id": student_id,
                    "misconceptions": assessment_result["misconceptions"],
                }
            )

        result = {
            "assessment_id": assessment_id,
            "result": assessment_result,
            "remediation": remediation,
        }

        yield {"event": "result", "data": result, "progress": 100}

    async def generate_exam_stream(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str] = None,
        num_questions: int = 10,
    ):
        """Stream exam generation with progress events."""
        yield {
            "event": "progress",
            "step": "Generating exam questions...",
            "progress": 20,
        }

        # Get VR analogy context for visual question enrichment
        analogy_context = self.pedagogy_agent.get_vr_elements(subject_code, topic_code)

        result = await self.evaluation_agent.process(
            {
                "action": "generate_exam",
                "student_id": student_id,
                "subject_code": subject_code,
                "topic_code": topic_code,
                "topic_name": topic_name,
                "num_questions": num_questions,
                "analogy_context": analogy_context,
            }
        )

        yield {"event": "result", "data": result, "progress": 100}

    async def grade_exam_stream(
        self,
        exam: Dict[str, Any],
        responses: List[Dict[str, Any]],
    ):
        """Stream exam grading with progress events."""
        yield {"event": "progress", "step": "Grading exam...", "progress": 20}

        result = await self.evaluation_agent.process(
            {
                "action": "evaluate_exam",
                "exam": exam,
                "responses": responses,
            }
        )

        yield {"event": "result", "data": result, "progress": 100}


# Singleton instance
orchestrator = AgentOrchestrator()
