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
    5. Agent E (VR) → Generate VR instructions
    6. Agent F (Evaluation) → Provide feedback (during/after)
    """

    def __init__(self):
        self.assessment_agent = AssessmentAgent()
        self.profile_agent = LearnerProfileAgent()
        self.curriculum_agent = CurriculumAgent()
        self.pedagogy_agent = PedagogyAgent()
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
        profile_result = await self.profile_agent.process({
            "action": "get_profile",
            "student_id": student_id,
        })
        
        if "error" in profile_result:
            return {"error": profile_result["error"], "session_id": session_id}
        
        # Step 2: Determine what to teach (Agent C - Curriculum)
        curriculum_result = await self.curriculum_agent.process({
            "action": "get_next_topic",
            "student_id": student_id,
            "subject_code": subject_code,
        })
        
        if "message" in curriculum_result and "All topics mastered" in curriculum_result.get("message", ""):
            return {
                "session_id": session_id,
                "status": "completed",
                "message": curriculum_result["message"],
            }
        
        # Step 3: Determine how to teach (Agent D - Pedagogy)
        pedagogy_result = await self.pedagogy_agent.process({
            "action": "get_teaching_plan",
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": curriculum_result.get("topic_code"),
            "topic_name": curriculum_result.get("topic_name"),
        })
        
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
        # Generate diagnostic questions (Agent A)
        questions_result = await self.assessment_agent.process({
            "action": "generate_questions",
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": topic_name,
            "stage": AssessmentStage.INITIAL.value,
        })
        
        return {
            "assessment_id": str(uuid.uuid4()),
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "questions": questions_result.get("questions", []),
            "total_marks": questions_result.get("total_marks", 0),
            "estimated_time_minutes": questions_result.get("estimated_time_minutes", 15),
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
        mcq_result = await self.assessment_agent.process({
            "action": "evaluate_mcq",
            "questions": questions,
            "responses": responses,
        })
        
        # Step 2: Evaluate descriptive answers (Agent A)
        descriptive_results = []
        for q in questions:
            if q["question_type"] in ["descriptive", "numerical"]:
                response = next(
                    (r for r in responses if r["question_id"] == q["question_id"]),
                    None
                )
                if response:
                    eval_result = await self.assessment_agent.process({
                        "action": "evaluate_descriptive",
                        "question": q,
                        "student_answer": response["answer"],
                    })
                    descriptive_results.append(eval_result)
        
        # Step 3: Identify misconceptions (Agent A)
        misconceptions = {}
        if mcq_result.get("wrong_answers"):
            misconceptions = await self.assessment_agent.process({
                "action": "identify_misconceptions",
                "topic_name": topic_name or topic_code,
                "wrong_answers": mcq_result["wrong_answers"],
            })
        
        # Step 4: Calculate final result (Agent A)
        assessment_result = await self.assessment_agent.process({
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
        })
        
        # Step 5: Update learner profile (Agent B)
        await self.profile_agent.process({
            "action": "update_from_assessment",
            "student_id": student_id,
            "assessment_result": assessment_result,
        })
        
        # Step 6: Store assessment in database
        await supabase_manager.store_assessment(
            result=type('Obj', (), assessment_result)()  # Convert dict to object-like
        )
        
        # Step 7: Get remediation if needed (Agent F)
        remediation = None
        if assessment_result.get("misconceptions"):
            remediation = await self.evaluation_agent.process({
                "action": "get_remediation",
                "student_id": student_id,
                "misconceptions": assessment_result["misconceptions"],
            })
        
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
        return await self.curriculum_agent.process({
            "action": "get_learning_path",
            "student_id": student_id,
            "subject_code": subject_code,
        })

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
        return await self.evaluation_agent.process({
            "action": "generate_exam",
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": topic_name,
            "num_questions": num_questions,
        })

    async def grade_exam(
        self,
        exam: Dict[str, Any],
        responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Grade an exam and provide feedback.
        """
        return await self.evaluation_agent.process({
            "action": "evaluate_exam",
            "exam": exam,
            "responses": responses,
        })

    async def get_student_recommendations(
        self,
        student_id: str,
    ) -> Dict[str, Any]:
        """
        Get personalized learning recommendations for a student.
        """
        return await self.profile_agent.process({
            "action": "get_recommendations",
            "student_id": student_id,
        })

    async def run_onboarding_assessment(
        self,
        student_id: str,
        subject_code: str,
    ) -> Dict[str, Any]:
        """
        Run a comprehensive onboarding assessment for a NEW student.
        
        This tests across ALL topics in a subject to establish baseline knowledge.
        Used when a student first selects a subject.
        
        Returns:
            Assessment with questions covering all topics
        """
        # Get syllabus to know all topics
        syllabus = self.curriculum_agent.get_syllabus(subject_code)
        if "error" in syllabus:
            return syllabus
        
        all_topics = syllabus.get("topics", [])
        
        # Generate 2-3 questions per topic for broad coverage
        all_questions = []
        total_marks = 0
        
        for topic in all_topics[:5]:  # Limit to first 5 topics for reasonable length
            questions_result = await self.assessment_agent.process({
                "action": "generate_questions",
                "subject_code": subject_code,
                "topic_code": topic["topic_code"],
                "topic_name": topic["topic_name"],
                "stage": AssessmentStage.INITIAL.value,
                "context": "Generate only 3 quick diagnostic questions for onboarding.",
            })
            
            for q in questions_result.get("questions", [])[:3]:  # Max 3 per topic
                q["source_topic"] = topic["topic_code"]
                all_questions.append(q)
                total_marks += q.get("max_marks", 1)
        
        return {
            "assessment_id": str(uuid.uuid4()),
            "assessment_type": "onboarding",
            "student_id": student_id,
            "subject_code": subject_code,
            "subject_name": syllabus.get("subject_name"),
            "questions": all_questions,
            "total_marks": total_marks,
            "total_questions": len(all_questions),
            "topics_covered": [t["topic_code"] for t in all_topics[:5]],
            "estimated_time_minutes": max(15, len(all_questions) * 2),
        }

    async def submit_onboarding_assessment(
        self,
        student_id: str,
        assessment_id: str,
        subject_code: str,
        questions: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Submit onboarding assessment and get personalized learning path.
        
        Returns:
            Profile update + recommended learning path
        """
        # Group questions by topic
        topics_results = {}
        
        for q in questions:
            topic = q.get("source_topic", "general")
            if topic not in topics_results:
                topics_results[topic] = {"questions": [], "responses": []}
            topics_results[topic]["questions"].append(q)
            
            # Find matching response
            response = next(
                (r for r in responses if r["question_id"] == q["question_id"]),
                None
            )
            if response:
                topics_results[topic]["responses"].append(response)
        
        # Evaluate each topic
        topic_scores = {}
        all_weak_topics = []
        all_strong_topics = []
        
        for topic_code, data in topics_results.items():
            # Evaluate MCQs
            mcq_result = await self.assessment_agent.process({
                "action": "evaluate_mcq",
                "questions": data["questions"],
                "responses": data["responses"],
            })
            
            percentage = mcq_result.get("percentage", 0)
            topic_scores[topic_code] = {
                "score": percentage,
                "correct": mcq_result.get("correct_count", 0),
                "total": mcq_result.get("total_questions", 0),
            }
            
            # Classify topic
            if percentage >= 70:
                all_strong_topics.append(topic_code)
            elif percentage < 40:
                all_weak_topics.append(topic_code)
        
        # Update profile with results
        await self.profile_agent.process({
            "action": "update_from_assessment",
            "student_id": student_id,
            "assessment_result": {
                "subject_code": subject_code,
                "weak_concepts": all_weak_topics,
                "strong_concepts": all_strong_topics,
            },
        })
        
        # Get personalized learning path
        learning_path = await self.curriculum_agent.process({
            "action": "get_learning_path",
            "student_id": student_id,
            "subject_code": subject_code,
        })
        
        # Determine recommended starting topic
        recommended_start = all_weak_topics[0] if all_weak_topics else (
            learning_path.get("learning_path", [{}])[0].get("topic_code", "motion")
        )
        
        return {
            "assessment_id": assessment_id,
            "profile_updated": True,
            "topic_scores": topic_scores,
            "overall_percentage": sum(t["score"] for t in topic_scores.values()) / len(topic_scores) if topic_scores else 0,
            "strong_topics": all_strong_topics,
            "weak_topics": all_weak_topics,
            "recommended_start": recommended_start,
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
        profile_result = await self.profile_agent.process({
            "action": "get_profile",
            "student_id": student_id,
        })
        
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
                    curriculum_plan["estimated_duration_minutes"] = t.get("estimated_minutes", 30)
                    break
        
        # Get pedagogy plan (how to teach)
        pedagogy_result = await self.pedagogy_agent.process({
            "action": "get_teaching_plan",
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": curriculum_plan["topic_name"],
        })
        
        # Generate actual lesson content
        lesson_content = await self.pedagogy_agent.generate_lesson_content(
            topic_name=curriculum_plan["topic_name"],
            subject_code=subject_code,
            subtopics=curriculum_plan.get("subtopics", []),
            pedagogy_plan=pedagogy_result,
            learning_style=profile_result.get("learning_style"),
        )
        
        return {
            "lesson_id": str(uuid.uuid4()),
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": curriculum_plan["topic_name"],
            "curriculum_plan": curriculum_plan,
            "pedagogy_plan": pedagogy_result,
            "lesson_content": lesson_content,
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
    ):
        """Stream onboarding assessment generation with progress events."""
        yield {"event": "progress", "step": "Loading syllabus...", "progress": 5}

        syllabus = self.curriculum_agent.get_syllabus(subject_code)
        if "error" in syllabus:
            yield {"event": "error", "error": syllabus["error"]}
            return

        all_topics = syllabus.get("topics", [])
        topics_to_test = all_topics[:5]
        total_steps = len(topics_to_test) + 1  # +1 for VR instructions

        yield {"event": "progress", "step": f"Found {len(topics_to_test)} topics to assess", "progress": 10}

        all_questions = []
        total_marks = 0

        for i, topic in enumerate(topics_to_test):
            pct = 10 + int((i / total_steps) * 80)
            yield {"event": "progress", "step": f"Generating questions for {topic['topic_name']}...", "progress": pct}

            questions_result = await self.assessment_agent.process({
                "action": "generate_questions",
                "subject_code": subject_code,
                "topic_code": topic["topic_code"],
                "topic_name": topic["topic_name"],
                "stage": AssessmentStage.INITIAL.value,
                "context": "Generate only 3 quick diagnostic questions for onboarding.",
            })

            for q in questions_result.get("questions", [])[:3]:
                q["source_topic"] = topic["topic_code"]
                all_questions.append(q)
                total_marks += q.get("max_marks", 1)

            yield {"event": "progress", "step": f"✓ {topic['topic_name']} — {len(questions_result.get('questions', [])[:3])} questions", "progress": pct + 5}

        result = {
            "assessment_id": str(uuid.uuid4()),
            "assessment_type": "onboarding",
            "student_id": student_id,
            "subject_code": subject_code,
            "subject_name": syllabus.get("subject_name"),
            "questions": all_questions,
            "total_marks": total_marks,
            "total_questions": len(all_questions),
            "topics_covered": [t["topic_code"] for t in topics_to_test],
            "estimated_time_minutes": max(15, len(all_questions) * 2),
        }

        yield {"event": "result", "data": result, "progress": 100}

    async def submit_onboarding_stream(
        self,
        student_id: str,
        assessment_id: str,
        subject_code: str,
        questions: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ):
        """Stream onboarding submission with progress events."""
        yield {"event": "progress", "step": "Grouping questions by topic...", "progress": 5}

        # Group questions by topic
        topics_results = {}
        for q in questions:
            topic = q.get("source_topic", "general")
            if topic not in topics_results:
                topics_results[topic] = {"questions": [], "responses": []}
            topics_results[topic]["questions"].append(q)
            response = next(
                (r for r in responses if r["question_id"] == q["question_id"]),
                None
            )
            if response:
                topics_results[topic]["responses"].append(response)

        topic_scores = {}
        all_weak_topics = []
        all_strong_topics = []
        topic_list = list(topics_results.items())

        for i, (topic_code, data) in enumerate(topic_list):
            pct = 10 + int((i / len(topic_list)) * 50)
            yield {"event": "progress", "step": f"Evaluating {topic_code}...", "progress": pct}

            mcq_result = await self.assessment_agent.process({
                "action": "evaluate_mcq",
                "questions": data["questions"],
                "responses": data["responses"],
            })

            percentage = mcq_result.get("percentage", 0)
            topic_scores[topic_code] = {
                "score": percentage,
                "correct": mcq_result.get("correct_count", 0),
                "total": mcq_result.get("total_questions", 0),
            }

            if percentage >= 70:
                all_strong_topics.append(topic_code)
            elif percentage < 40:
                all_weak_topics.append(topic_code)

        yield {"event": "progress", "step": "Updating learner profile...", "progress": 70}

        await self.profile_agent.process({
            "action": "update_from_assessment",
            "student_id": student_id,
            "assessment_result": {
                "subject_code": subject_code,
                "weak_concepts": all_weak_topics,
                "strong_concepts": all_strong_topics,
            },
        })

        yield {"event": "progress", "step": "Generating learning path...", "progress": 85}

        learning_path = await self.curriculum_agent.process({
            "action": "get_learning_path",
            "student_id": student_id,
            "subject_code": subject_code,
        })

        recommended_start = all_weak_topics[0] if all_weak_topics else (
            learning_path.get("learning_path", [{}])[0].get("topic_code", "motion")
        )

        result = {
            "assessment_id": assessment_id,
            "profile_updated": True,
            "topic_scores": topic_scores,
            "overall_percentage": sum(t["score"] for t in topic_scores.values()) / len(topic_scores) if topic_scores else 0,
            "strong_topics": all_strong_topics,
            "weak_topics": all_weak_topics,
            "recommended_start": recommended_start,
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

        yield {"event": "progress", "step": "Loading learner profile...", "progress": 10}

        profile_result = await self.profile_agent.process({
            "action": "get_profile",
            "student_id": student_id,
        })

        if "error" in profile_result:
            yield {"event": "error", "error": profile_result["error"]}
            return

        yield {"event": "progress", "step": "Determining next topic...", "progress": 30}

        curriculum_result = await self.curriculum_agent.process({
            "action": "get_next_topic",
            "student_id": student_id,
            "subject_code": subject_code,
        })

        if "message" in curriculum_result and "All topics mastered" in curriculum_result.get("message", ""):
            yield {"event": "result", "data": {
                "session_id": session_id, "status": "completed",
                "message": curriculum_result["message"],
            }, "progress": 100}
            return

        yield {"event": "progress", "step": f"Planning pedagogy for {curriculum_result.get('topic_name', '')}...", "progress": 55}

        pedagogy_result = await self.pedagogy_agent.process({
            "action": "get_teaching_plan",
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": curriculum_result.get("topic_code"),
            "topic_name": curriculum_result.get("topic_name"),
        })

        yield {"event": "progress", "step": "Generating lesson content...", "progress": 75}

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
        """Stream teaching content generation with progress events."""
        yield {"event": "progress", "step": "Loading learner profile...", "progress": 10}

        profile_result = await self.profile_agent.process({
            "action": "get_profile",
            "student_id": student_id,
        })

        yield {"event": "progress", "step": "Fetching curriculum plan...", "progress": 25}

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
                    curriculum_plan["estimated_duration_minutes"] = t.get("estimated_minutes", 30)
                    break

        yield {"event": "progress", "step": f"Designing pedagogy for {curriculum_plan['topic_name']}...", "progress": 40}

        pedagogy_result = await self.pedagogy_agent.process({
            "action": "get_teaching_plan",
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": curriculum_plan["topic_name"],
        })

        yield {"event": "progress", "step": "Generating lesson content...", "progress": 65}

        lesson_content = await self.pedagogy_agent.generate_lesson_content(
            topic_name=curriculum_plan["topic_name"],
            subject_code=subject_code,
            subtopics=curriculum_plan.get("subtopics", []),
            pedagogy_plan=pedagogy_result,
            learning_style=profile_result.get("learning_style"),
        )

        result = {
            "lesson_id": str(uuid.uuid4()),
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": curriculum_plan["topic_name"],
            "curriculum_plan": curriculum_plan,
            "pedagogy_plan": pedagogy_result,
            "lesson_content": lesson_content,
            "learning_style": profile_result.get("learning_style"),
        }

        yield {"event": "result", "data": result, "progress": 100}

    async def generate_assessment_stream(
        self,
        student_id: str,
        subject_code: str,
        topic_code: Optional[str] = None,
        topic_name: Optional[str] = None,
    ):
        """Stream assessment generation with progress events."""
        yield {"event": "progress", "step": "Generating diagnostic questions...", "progress": 20}

        questions_result = await self.assessment_agent.process({
            "action": "generate_questions",
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": topic_name,
            "stage": AssessmentStage.INITIAL.value,
        })

        result = {
            "assessment_id": str(uuid.uuid4()),
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "questions": questions_result.get("questions", []),
            "total_marks": questions_result.get("total_marks", 0),
            "estimated_time_minutes": questions_result.get("estimated_time_minutes", 15),
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

        mcq_result = await self.assessment_agent.process({
            "action": "evaluate_mcq",
            "questions": questions,
            "responses": responses,
        })

        yield {"event": "progress", "step": "Evaluating descriptive answers...", "progress": 30}

        descriptive_results = []
        for q in questions:
            if q["question_type"] in ["descriptive", "numerical"]:
                response = next(
                    (r for r in responses if r["question_id"] == q["question_id"]),
                    None
                )
                if response:
                    eval_result = await self.assessment_agent.process({
                        "action": "evaluate_descriptive",
                        "question": q,
                        "student_answer": response["answer"],
                    })
                    descriptive_results.append(eval_result)

        yield {"event": "progress", "step": "Identifying misconceptions...", "progress": 50}

        misconceptions = {}
        if mcq_result.get("wrong_answers"):
            misconceptions = await self.assessment_agent.process({
                "action": "identify_misconceptions",
                "topic_name": topic_name or topic_code,
                "wrong_answers": mcq_result["wrong_answers"],
            })

        yield {"event": "progress", "step": "Calculating final result...", "progress": 65}

        assessment_result = await self.assessment_agent.process({
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
        })

        yield {"event": "progress", "step": "Updating learner profile...", "progress": 80}

        await self.profile_agent.process({
            "action": "update_from_assessment",
            "student_id": student_id,
            "assessment_result": assessment_result,
        })

        yield {"event": "progress", "step": "Storing assessment...", "progress": 85}

        await supabase_manager.store_assessment(
            result=type('Obj', (), assessment_result)()
        )

        remediation = None
        if assessment_result.get("misconceptions"):
            yield {"event": "progress", "step": "Getting remediation suggestions...", "progress": 92}
            remediation = await self.evaluation_agent.process({
                "action": "get_remediation",
                "student_id": student_id,
                "misconceptions": assessment_result["misconceptions"],
            })

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
        yield {"event": "progress", "step": "Generating exam questions...", "progress": 20}

        result = await self.evaluation_agent.process({
            "action": "generate_exam",
            "student_id": student_id,
            "subject_code": subject_code,
            "topic_code": topic_code,
            "topic_name": topic_name,
            "num_questions": num_questions,
        })

        yield {"event": "result", "data": result, "progress": 100}

    async def grade_exam_stream(
        self,
        exam: Dict[str, Any],
        responses: List[Dict[str, Any]],
    ):
        """Stream exam grading with progress events."""
        yield {"event": "progress", "step": "Grading exam...", "progress": 20}

        result = await self.evaluation_agent.process({
            "action": "evaluate_exam",
            "exam": exam,
            "responses": responses,
        })

        yield {"event": "result", "data": result, "progress": 100}


# Singleton instance
orchestrator = AgentOrchestrator()
