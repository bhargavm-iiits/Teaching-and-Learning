"""
Agent F: Evaluation & Feedback Agent

Purpose: Generate exams and provide detailed feedback.

Inputs:
- Assessment results from Agent A
- Learner profile from Agent B
- Exam responses

Outputs:
- Graded exams with detailed feedback
- Conceptual feedback
- Next steps recommendations
- Misconception remediation suggestions
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from db.supabase_client import supabase_manager
from models.schemas import (
    Exam,
    ExamResult,
    MasteryLevel,
    Question,
    QuestionType,
)


class EvaluationAgent(BaseAgent):
    """
    Agent F: Evaluation & Feedback Agent.
    
    Generates comprehensive feedback based on:
    - Assessment performance
    - Historical patterns
    - Identified misconceptions
    - Learning goals
    """

    def __init__(self, temperature: float = 0.2):
        super().__init__(temperature=temperature)

    def _build_system_prompt(self) -> str:
        return """You are the Evaluation & Feedback Agent, an expert in educational assessment and constructive feedback for Class 10 students.

Your role is to:
1. Evaluate student performance holistically
2. Provide specific, actionable feedback
3. Identify patterns in mistakes
4. Generate personalized recommendations for improvement
5. Create supportive, encouraging feedback that motivates learning

You believe every student can improve with the right guidance."""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method.
        
        Actions:
        - 'generate_exam': Create an exam for a topic
        - 'evaluate_exam': Grade an exam and provide feedback
        - 'get_feedback': Get detailed feedback on performance
        - 'get_remediation': Get remediation suggestions for misconceptions
        """
        action = input_data.get("action")
        
        if action == "generate_exam":
            return await self.generate_exam(
                student_id=input_data["student_id"],
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
                topic_name=input_data.get("topic_name"),
                num_questions=input_data.get("num_questions", 10),
                analogy_context=input_data.get("analogy_context"),
            )
        elif action == "evaluate_exam":
            return await self.evaluate_exam(
                exam=input_data["exam"],
                responses=input_data["responses"],
            )
        elif action == "get_feedback":
            return await self.get_detailed_feedback(
                student_id=input_data["student_id"],
                assessment_results=input_data.get("assessment_results", []),
            )
        elif action == "get_remediation":
            return await self.get_remediation_plan(
                student_id=input_data["student_id"],
                misconceptions=input_data["misconceptions"],
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    async def generate_exam(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str] = None,
        num_questions: int = 10,
        analogy_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive exam for a topic.
        
        Returns:
            Exam object with questions
        """
        # Get learner profile for personalization
        profile = await supabase_manager.get_learner_profile(student_id)

        # Build analogy hint section for VR visual context
        analogy_hint = ""
        if analogy_context:
            analogy_hint = f"""\n\n## VR Visual Analogy Context (use this to create visual context for each question)
The topic uses this analogy for VR teaching: "{analogy_context.get('analogy', 'real-world analogy')}"
Recommended VR scene: {analogy_context.get('scene', 'virtual_classroom')}
Available VR objects: {analogy_context.get('objects', [])}

For EACH question, also generate a "vr_visual_context" block with:
- analogy: A short VR-friendly analogy/scenario related to the concept being tested (1-2 sentences)
- scene: A VR scene name where this question can be visualized (e.g., "cricket_ground", "classroom", "lab")
- visual_objects: List of 2-4 3D objects to render in VR alongside the question
- visualization_prompt: Brief description of what the VR environment should show while asking this question (1-2 sentences)"""

        # Use LLM to generate exam
        prompt = self._format_prompt(
            task=f"""Create a {num_questions}-question exam for Class 10 {subject_code.upper()} on "{topic_name or topic_code}".

## Student Context
{self._format_student_context(profile) if profile else "New student - use standard difficulty"}

## Exam Requirements
- Total questions: {num_questions}
- Mix of types: 60% MCQ, 25% Descriptive, 15% Numerical
- Difficulty distribution: 30% Easy, 50% Medium, 20% Hard
- Include questions that test:
  * Recall of key concepts
  * Understanding of relationships
  * Application to new situations
  * Problem-solving skills

For each question provide:
- question_id: Unique ID
- question_type: "mcq", "descriptive", or "numerical"
- question_text: Clear question
- difficulty: "weak", "developing", or "proficient"
- For MCQ: options (array) and correct_answer
- For descriptive: expected_keywords and model_answer
- For numerical: correct_answer, tolerance, unit
- max_marks: 1-5 based on complexity
{analogy_hint}""",
            output_format="""{
  "exam_title": "Kinematics - Comprehensive Test",
  "questions": [
    {
      "question_id": "q1",
      "question_type": "mcq",
      "question_text": "What is the SI unit of acceleration?",
      "difficulty": "weak",
      "options": ["A) m/s", "B) m/s²", "C) m²/s", "D) s/m"],
      "correct_answer": "B) m/s²",
      "max_marks": 1,
      "vr_visual_context": {
        "analogy": "Watch a car speedometer as it accelerates from rest — the needle moves faster and faster",
        "scene": "city_street",
        "visual_objects": ["car", "speedometer", "road"],
        "visualization_prompt": "Show a car accelerating on a road with a speedometer display changing in real-time"
      }
    }
  ],
  "total_marks": 25,
  "time_limit_minutes": 30
}"""
        )

        result = await self._invoke_llm_json(prompt)
        
        # Convert to Question objects
        questions = []
        for q in result.get("questions", []):
            # Coerce types
            correct_answer = q.get("correct_answer")
            if correct_answer is not None and not isinstance(correct_answer, str):
                correct_answer = str(correct_answer)
            
            questions.append(Question(
                question_id=q["question_id"],
                question_type=QuestionType(q["question_type"]),
                question_text=q["question_text"],
                topic_code=topic_code,
                topic_name=topic_name,
                subject_code=subject_code,
                difficulty=MasteryLevel(q["difficulty"]),
                options=q.get("options"),
                correct_answer=correct_answer,
                expected_keywords=q.get("expected_keywords"),
                model_answer=q.get("model_answer"),
                tolerance=q.get("tolerance"),
                unit=q.get("unit"),
                max_marks=q.get("max_marks", 1),
                vr_visual_context=q.get("vr_visual_context"),
            ))
        
        exam = Exam(
            exam_id=str(uuid.uuid4()),
            student_id=student_id,
            subject_code=subject_code,
            topic_code=topic_code,
            topic_name=topic_name,
            questions=questions,
            total_marks=result.get("total_marks", sum(q.max_marks for q in questions)),
            time_limit_minutes=result.get("time_limit_minutes", 30),
        )
        
        return exam.model_dump()

    def _format_student_context(self, profile) -> str:
        """Format student profile for exam generation context."""
        if not profile:
            return "No profile available"
        
        return f"""- Learning style: {profile.learning_style.value}
- Weak topics: {profile.weak_topics[:3]}
- Historical mistakes: {profile.historical_mistakes[-3:]}
- Total study time: {profile.total_study_time_minutes} minutes"""

    async def evaluate_exam(
        self,
        exam: Dict[str, Any],
        responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Grade an exam and provide detailed feedback.
        
        Returns:
            ExamResult with scores, feedback, and recommendations
        """
        # Build response lookup
        response_map = {r["question_id"]: r["answer"] for r in responses}
        
        question_results = []
        total_score = 0
        max_score = 0
        misconceptions = []
        
        for q in exam.get("questions", []):
            qid = q["question_id"]
            student_answer = response_map.get(qid, "")
            max_marks = q.get("max_marks", 1)
            
            if q["question_type"] == "mcq":
                # Evaluate MCQ
                correct = q.get("correct_answer", "")
                is_correct = self._compare_answers(student_answer, correct)
                score = max_marks if is_correct else 0
                
                result = {
                    "question_id": qid,
                    "is_correct": is_correct,
                    "score": score,
                    "max_score": max_marks,
                    "student_answer": student_answer,
                    "correct_answer": correct,
                    "feedback": "Correct!" if is_correct else f"The correct answer was: {correct}",
                }
            else:
                # Use LLM to evaluate descriptive/numerical
                eval_result = await self._evaluate_with_llm(q, student_answer)
                score = eval_result.get("score", 0)
                result = {
                    "question_id": qid,
                    "is_correct": score >= max_marks * 0.5,
                    "score": score,
                    "max_score": max_marks,
                    "student_answer": student_answer,
                    "correct_answer": q.get("model_answer") or q.get("correct_answer"),
                    "feedback": eval_result.get("feedback", ""),
                    "misconceptions": eval_result.get("misconceptions", []),
                }
                misconceptions.extend(eval_result.get("misconceptions", []))
            
            question_results.append(result)
            total_score += score
            max_score += max_marks
        
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        # Generate overall feedback
        overall_feedback = await self._generate_overall_feedback(
            percentage=percentage,
            question_results=question_results,
            topic=exam.get("topic_name") or exam.get("topic_code"),
        )
        
        exam_result = ExamResult(
            exam_id=exam["exam_id"],
            student_id=exam["student_id"],
            total_score=total_score,
            max_score=max_score,
            percentage=round(percentage, 1),
            question_results=question_results,
            overall_feedback=overall_feedback["feedback"],
            misconceptions=list(set(misconceptions)),
            recommendations=overall_feedback.get("recommendations", []),
            suggested_topics=overall_feedback.get("suggested_topics", []),
            mastery_update=self._calculate_mastery(percentage),
        )
        
        return exam_result.model_dump()

    def _compare_answers(self, student: str, correct: str) -> bool:
        """Compare MCQ answers, handling different formats."""
        if not student or not correct:
            return False
        
        # Normalize: extract letter only
        student_letter = student.strip().upper()[:1]
        correct_letter = correct.strip().upper()[:1]
        
        return student_letter == correct_letter

    async def _evaluate_with_llm(
        self,
        question: Dict[str, Any],
        student_answer: str,
    ) -> Dict[str, Any]:
        """Use LLM to evaluate descriptive/numerical answers."""
        prompt = self._format_prompt(
            task=f"""Evaluate this student's answer.

## Question
{question['question_text']}

## Expected Answer
{question.get('model_answer') or question.get('correct_answer')}

## Expected Keywords
{question.get('expected_keywords', [])}

## Student's Answer
{student_answer}

## Max Marks: {question.get('max_marks', 3)}

Evaluate fairly, giving partial credit where appropriate.""",
            output_format="""{
  "score": 2,
  "feedback": "Good explanation of the concept, but missed the mathematical relationship",
  "misconceptions": ["Confused velocity with speed"],
  "correct_parts": ["Understood direction matters"],
  "missing_parts": ["Did not mention vector nature"]
}"""
        )

        return await self._invoke_llm_json(prompt)

    def _calculate_mastery(self, percentage: float) -> MasteryLevel:
        """Calculate mastery level from percentage."""
        if percentage >= 85:
            return MasteryLevel.MASTERED
        elif percentage >= 65:
            return MasteryLevel.PROFICIENT
        elif percentage >= 40:
            return MasteryLevel.DEVELOPING
        else:
            return MasteryLevel.WEAK

    async def _generate_overall_feedback(
        self,
        percentage: float,
        question_results: List[Dict],
        topic: str,
    ) -> Dict[str, Any]:
        """Generate overall feedback and recommendations."""
        wrong_count = sum(1 for q in question_results if not q.get("is_correct"))
        
        prompt = self._format_prompt(
            task=f"""Generate encouraging, constructive feedback for a Class 10 student who scored {percentage:.1f}% on a {topic} exam.

## Performance Summary
- Score: {percentage:.1f}%
- Questions wrong: {wrong_count}/{len(question_results)}
- Mastery level: {self._calculate_mastery(percentage).value}

## Question Results Summary
{self._summarize_results(question_results)}

## Instructions
1. Start with something positive
2. Be specific about what to improve
3. Suggest 2-3 concrete next steps
4. End encouragingly""",
            output_format="""{
  "feedback": "Great effort! You showed strong understanding of... To improve, focus on...",
  "recommendations": ["Review velocity vs speed", "Practice graphical problems"],
  "suggested_topics": ["Graphical representation of motion"],
  "study_tips": ["Draw diagrams for each problem", "Practice with real-world examples"]
}"""
        )

        return await self._invoke_llm_json(prompt)

    def _summarize_results(self, results: List[Dict]) -> str:
        """Summarize question results for feedback generation."""
        lines = []
        for r in results:
            status = "✓" if r.get("is_correct") else "✗"
            lines.append(f"- {status} Q{r['question_id']}: {r.get('feedback', '')[:50]}")
        return "\n".join(lines[:5])  # Limit to 5 for brevity

    async def get_detailed_feedback(
        self,
        student_id: str,
        assessment_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Get comprehensive feedback based on multiple assessments.
        """
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Student profile not found"}
        
        # Analyze patterns across assessments
        total_attempted = sum(a.get("questions_attempted", 0) for a in assessment_results)
        total_correct = sum(a.get("questions_correct", 0) for a in assessment_results)
        avg_score = sum(a.get("score", 0) for a in assessment_results) / len(assessment_results) if assessment_results else 0
        
        all_misconceptions = []
        for a in assessment_results:
            all_misconceptions.extend(a.get("misconceptions", []))
        
        prompt = self._format_prompt(
            task=f"""Provide comprehensive learning feedback for this Class 10 student.

## Learning Profile
- Learning style: {profile.learning_style.value}
- Weak topics: {profile.weak_topics}
- Strong topics: {profile.strong_topics}
- Study time: {profile.total_study_time_minutes} minutes

## Performance Summary
- Total questions: {total_attempted}
- Correct: {total_correct}
- Accuracy: {(total_correct/total_attempted*100) if total_attempted > 0 else 0:.1f}%
- Average score: {avg_score:.1f}%

## Identified Misconceptions
{list(set(all_misconceptions))}

Provide holistic feedback and a learning plan.""",
            output_format="""{
  "overall_assessment": "You're making good progress...",
  "strengths": ["Strong conceptual understanding", "Good at MCQs"],
  "areas_to_improve": ["Numerical problems", "Multi-step derivations"],
  "personalized_tips": ["Based on your visual learning style, try..."],
  "weekly_goals": ["Master one weak topic", "Practice 10 numerical problems"],
  "motivation": "Keep up the great work!..."
}"""
        )

        return await self._invoke_llm_json(prompt)

    async def get_remediation_plan(
        self,
        student_id: str,
        misconceptions: List[str],
    ) -> Dict[str, Any]:
        """
        Generate a remediation plan to address specific misconceptions.
        """
        if not misconceptions:
            return {"message": "No misconceptions to remediate"}
        
        prompt = self._format_prompt(
            task=f"""Create a remediation plan to address these student misconceptions:

## Misconceptions
{misconceptions}

For each misconception, provide:
1. Why it's wrong (briefly)
2. The correct understanding
3. A simple analogy to remember
4. A practice activity
""",
            output_format="""{
  "remediations": [
    {
      "misconception": "Higher angle = greater range",
      "why_wrong": "Range depends on sin(2θ), which maximizes at 45°",
      "correct_understanding": "45° gives maximum range because sin(90°) = 1",
      "analogy": "Think of a water fountain - too high or too low and water doesn't go far",
      "practice": "Calculate range for 30°, 45°, 60° and compare"
    }
  ],
  "overall_approach": "Focus on visualization and hands-on practice",
  "estimated_time_minutes": 20
}"""
        )

        return await self._invoke_llm_json(prompt)
