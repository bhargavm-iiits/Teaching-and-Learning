"""
Agent A: User Assessment Agent

Purpose: Evaluate the student's initial and ongoing understanding.

Inputs:
- Subject
- Topic
- MCQ answers
- Descriptive answers (text or speech-to-text)

Outputs:
- Topic-wise mastery score
- Confidence level
- Misconception summaries
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from models.schemas import (
    AssessmentResult,
    AssessmentStage,
    DescriptiveEvaluation,
    MasteryLevel,
    Question,
    QuestionResponse,
    QuestionType,
)


class AssessmentAgent(BaseAgent):
    """
    Agent A: Evaluates student understanding through assessments.
    
    Responsibilities:
    - Generate diagnostic questions (LLM decides count based on stage)
    - Evaluate MCQ answers
    - Evaluate descriptive answers with rubric-based grading
    - Identify misconceptions from wrong answers
    - Calculate mastery level and confidence
    """

    def __init__(self, temperature: float = 0.2):
        super().__init__(temperature=temperature)

    def _build_system_prompt(self) -> str:
        return """You are the Assessment Agent, an expert educational evaluator for Class 10 students (ages 15-16).

Your role is to:
1. Generate appropriate assessment questions based on the learning stage
2. Evaluate student answers accurately and fairly
3. Identify conceptual misunderstandings and misconceptions
4. Provide constructive feedback that helps learning

You are knowledgeable in Physics, Mathematics, and Chemistry at the Class 10 level.
Always be encouraging yet accurate in your evaluations."""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method. Dispatches to specific methods based on action.
        
        Args:
            input_data: Must contain 'action' key with one of:
                - 'generate_questions': Generate diagnostic questions
                - 'evaluate_mcq': Evaluate MCQ answers
                - 'evaluate_descriptive': Evaluate descriptive answer
                - 'identify_misconceptions': Analyze wrong answers for misconceptions
                - 'calculate_result': Calculate final assessment result
        """
        action = input_data.get("action")
        
        if action == "generate_questions":
            return await self.generate_diagnostic_questions(
                subject_code=input_data["subject_code"],
                topic_code=input_data.get("topic_code"),
                topic_name=input_data.get("topic_name"),
                stage=AssessmentStage(input_data.get("stage", "initial")),
                context=input_data.get("context"),
            )
        elif action == "evaluate_mcq":
            return await self.evaluate_mcq_answers(
                questions=input_data["questions"],
                responses=input_data["responses"],
            )
        elif action == "evaluate_descriptive":
            return await self.evaluate_descriptive_answer(
                question=input_data["question"],
                student_answer=input_data["student_answer"],
            )
        elif action == "identify_misconceptions":
            return await self.identify_misconceptions(
                topic_name=input_data["topic_name"],
                wrong_answers=input_data["wrong_answers"],
            )
        elif action == "calculate_result":
            return await self.calculate_assessment_result(
                student_id=input_data["student_id"],
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
                topic_name=input_data.get("topic_name"),
                evaluations=input_data["evaluations"],
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    async def generate_diagnostic_questions(
        self,
        subject_code: str,
        topic_code: Optional[str] = None,
        topic_name: Optional[str] = None,
        stage: AssessmentStage = AssessmentStage.INITIAL,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate diagnostic questions for a subject/topic.
        LLM decides the number and types of questions based on the stage.
        
        Args:
            subject_code: Subject code (e.g., "physics")
            topic_code: Optional specific topic
            topic_name: Human-readable topic name
            stage: Assessment stage (initial, mid-lesson, post-lesson)
            context: Optional additional context (syllabus content, etc.)
        
        Returns:
            Dictionary with 'questions' list
        """
        stage_guidance = {
            AssessmentStage.INITIAL: """For INITIAL diagnostic assessment:
- Generate 8-12 questions covering breadth of the topic/subject
- Mix of difficulties: 30% easy, 50% medium, 20% hard
- Include 6-8 MCQs, 2-3 short descriptive, 1-2 numerical (if applicable)
- Purpose: Understand baseline knowledge and identify gaps""",
            
            AssessmentStage.MID_LESSON: """For MID-LESSON concept check:
- Generate 3-5 quick questions
- Focus on the concept just taught
- Mostly MCQs (2-3) with 1-2 very short descriptive
- Purpose: Verify understanding before proceeding""",
            
            AssessmentStage.POST_LESSON: """For POST-LESSON comprehensive review:
- Generate 6-10 questions
- Cover all subtopics taught in the lesson
- Mix: 4-6 MCQs, 2-3 descriptive, 1-2 application-based
- Purpose: Confirm mastery and identify remaining gaps""",
        }

        topic_str = topic_name or topic_code or "general concepts"
        
        prompt = self._format_prompt(
            task=f"""Generate diagnostic questions for Class 10 {subject_code.upper()} on "{topic_str}".

{stage_guidance[stage]}

For each question, provide:
- question_id: Unique ID (e.g., "q1", "q2")
- question_type: "mcq", "descriptive", or "numerical"
- question_text: Clear, specific question
- difficulty: "weak" (easy), "developing" (medium), "proficient" (hard)
- For MCQ: options (array of 4 choices with A), B), C), D) prefixes) and correct_answer
- For descriptive: expected_keywords (key terms for grading) and model_answer
- For numerical: correct_answer, tolerance, and unit
- max_marks: Point value (1 for MCQ, 2-5 for descriptive/numerical)

Generate questions appropriate for 15-16 year old students.""",
            context={"topic": topic_str, "subject": subject_code, "stage": stage.value}
                    if context is None else {"topic": topic_str, "subject": subject_code, "stage": stage.value, "additional_context": context},
            output_format="""{
  "questions": [
    {
      "question_id": "q1",
      "question_type": "mcq",
      "question_text": "...",
      "difficulty": "developing",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_answer": "B) ...",
      "max_marks": 1
    },
    {
      "question_id": "q2",
      "question_type": "descriptive",
      "question_text": "...",
      "difficulty": "proficient",
      "expected_keywords": ["keyword1", "keyword2"],
      "model_answer": "...",
      "max_marks": 3
    }
  ],
  "total_marks": 15,
  "estimated_time_minutes": 20
}"""
        )

        result = await self._invoke_llm_json(prompt)
        
        # Convert to Question objects for validation
        questions = []
        for q in result.get("questions", []):
            # Coerce types - LLM sometimes returns numeric values
            correct_answer = q.get("correct_answer")
            if correct_answer is not None and not isinstance(correct_answer, str):
                correct_answer = str(correct_answer)
            
            tolerance = q.get("tolerance")
            if tolerance is not None and isinstance(tolerance, str):
                try:
                    tolerance = float(tolerance)
                except ValueError:
                    tolerance = None
            
            questions.append(Question(
                question_id=q["question_id"],
                question_type=QuestionType(q["question_type"]),
                question_text=q["question_text"],
                topic_code=topic_code or "general",
                topic_name=topic_name,
                subject_code=subject_code,
                difficulty=MasteryLevel(q["difficulty"]),
                options=q.get("options"),
                correct_answer=correct_answer,
                expected_keywords=q.get("expected_keywords"),
                model_answer=q.get("model_answer"),
                tolerance=tolerance,
                unit=q.get("unit"),
                max_marks=q.get("max_marks", 1),
            ))
        
        return {
            "questions": [q.model_dump() for q in questions],
            "total_marks": result.get("total_marks", sum(q.max_marks for q in questions)),
            "estimated_time_minutes": result.get("estimated_time_minutes", 15),
        }

    async def evaluate_mcq_answers(
        self,
        questions: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluate MCQ answers.
        
        Args:
            questions: List of question dictionaries
            responses: List of QuestionResponse dictionaries
            
        Returns:
            Evaluation results with scores and analysis
        """
        # Build response lookup
        response_map = {r["question_id"]: r["answer"] for r in responses}
        
        results = []
        correct_count = 0
        total_marks = 0
        earned_marks = 0
        wrong_answers = []
        
        for q in questions:
            if q["question_type"] != "mcq":
                continue
                
            qid = q["question_id"]
            student_answer = response_map.get(qid, "")
            correct_answer = q.get("correct_answer", "")
            max_marks = q.get("max_marks", 1)
            
            # Normalize answers for comparison
            student_normalized = student_answer.strip().upper()[:2] if student_answer else ""
            correct_normalized = correct_answer.strip().upper()[:2] if correct_answer else ""
            
            is_correct = student_normalized == correct_normalized
            
            total_marks += max_marks
            if is_correct:
                correct_count += 1
                earned_marks += max_marks
            else:
                wrong_answers.append({
                    "question_id": qid,
                    "question_text": q["question_text"],
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "topic": q.get("topic_name") or q.get("topic_code"),
                })
            
            results.append({
                "question_id": qid,
                "is_correct": is_correct,
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "marks_earned": max_marks if is_correct else 0,
                "max_marks": max_marks,
            })
        
        return {
            "question_results": results,
            "correct_count": correct_count,
            "total_questions": len(results),
            "earned_marks": earned_marks,
            "total_marks": total_marks,
            "percentage": (earned_marks / total_marks * 100) if total_marks > 0 else 0,
            "wrong_answers": wrong_answers,
        }

    async def evaluate_descriptive_answer(
        self,
        question: Dict[str, Any],
        student_answer: str,
    ) -> Dict[str, Any]:
        """
        Evaluate a descriptive answer using LLM with rubric-based grading.
        
        Args:
            question: Question dictionary with expected_keywords, model_answer, rubric
            student_answer: Student's written answer
            
        Returns:
            DescriptiveEvaluation as dictionary
        """
        prompt = self._format_prompt(
            task=f"""Evaluate this Class 10 student's descriptive answer.

## Question
{question['question_text']}

## Expected Key Points
{', '.join(question.get('expected_keywords', []))}

## Model Answer
{question.get('model_answer', 'Not provided')}

## Rubric
- Full marks: All key concepts covered correctly with good explanation
- Partial marks: Some key concepts covered or minor errors
- Minimal marks: Shows basic understanding but missing major points
- Zero marks: Completely incorrect or irrelevant

## Student's Answer
{student_answer}

## Grading Instructions
1. Identify which expected keywords/concepts the student mentioned correctly
2. Identify missing key points
3. Detect any misconceptions (incorrect understanding)
4. Provide specific, constructive feedback
5. Score out of {question.get('max_marks', 3)} marks""",
            output_format="""{
  "score": 2,
  "max_score": 3,
  "matched_keywords": ["concept1", "concept2"],
  "missing_keywords": ["concept3"],
  "misconceptions_detected": ["student believes X when actually Y"],
  "feedback": "Good attempt! You correctly explained... However, you missed... To improve..."
}"""
        )

        result = await self._invoke_llm_json(prompt)
        
        return DescriptiveEvaluation(
            question_id=question["question_id"],
            score=result.get("score", 0),
            max_score=result.get("max_score", question.get("max_marks", 3)),
            matched_keywords=result.get("matched_keywords", []),
            missing_keywords=result.get("missing_keywords", []),
            misconceptions_detected=result.get("misconceptions_detected", []),
            feedback=result.get("feedback", ""),
        ).model_dump()

    async def identify_misconceptions(
        self,
        topic_name: str,
        wrong_answers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze wrong answers to identify common misconceptions.
        
        Args:
            topic_name: Topic being assessed
            wrong_answers: List of wrong answer details
            
        Returns:
            List of identified misconceptions with explanations
        """
        if not wrong_answers:
            return {"misconceptions": [], "patterns": []}

        prompt = self._format_prompt(
            task=f"""Analyze these wrong answers from a Class 10 student on "{topic_name}" to identify misconceptions.

## Wrong Answers
{self._format_wrong_answers(wrong_answers)}

## Instructions
1. Identify specific conceptual misunderstandings (not just careless errors)
2. Group similar errors into patterns
3. Suggest what the student likely believes incorrectly
4. Provide the correct understanding for each misconception""",
            output_format="""{
  "misconceptions": [
    {
      "misconception": "Student believes higher angle always gives greater range",
      "evidence": "Answered 60° instead of 45° for maximum range question",
      "correct_understanding": "Maximum range occurs at 45° due to sin(2θ) relationship",
      "severity": "high"
    }
  ],
  "patterns": ["Confusion about optimization problems", "Weak trigonometry foundation"],
  "recommended_focus": ["Projectile motion fundamentals", "sin(2θ) derivation"]
}"""
        )

        result = await self._invoke_llm_json(prompt)
        return result

    def _format_wrong_answers(self, wrong_answers: List[Dict[str, Any]]) -> str:
        """Format wrong answers for the prompt."""
        lines = []
        for i, wa in enumerate(wrong_answers, 1):
            lines.append(f"{i}. Question: {wa.get('question_text', 'N/A')}")
            lines.append(f"   Student answered: {wa.get('student_answer', 'N/A')}")
            lines.append(f"   Correct answer: {wa.get('correct_answer', 'N/A')}")
            lines.append("")
        return "\n".join(lines)

    async def calculate_assessment_result(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
        topic_name: Optional[str],
        evaluations: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate the final assessment result from all evaluations.
        
        Args:
            student_id: Student ID
            subject_code: Subject code
            topic_code: Topic code
            topic_name: Topic name
            evaluations: Combined evaluation data (MCQ + descriptive results)
            
        Returns:
            AssessmentResult as dictionary
        """
        mcq_results = evaluations.get("mcq_results", {})
        descriptive_results = evaluations.get("descriptive_results", [])
        misconceptions = evaluations.get("misconceptions", {})
        
        # Calculate total score
        total_earned = mcq_results.get("earned_marks", 0)
        total_max = mcq_results.get("total_marks", 0)
        
        for dr in descriptive_results:
            total_earned += dr.get("score", 0)
            total_max += dr.get("max_score", 0)
        
        percentage = (total_earned / total_max * 100) if total_max > 0 else 0
        
        # Determine mastery level
        if percentage >= 85:
            level = MasteryLevel.MASTERED
        elif percentage >= 65:
            level = MasteryLevel.PROFICIENT
        elif percentage >= 40:
            level = MasteryLevel.DEVELOPING
        else:
            level = MasteryLevel.WEAK
        
        # Calculate confidence (based on consistency)
        questions_attempted = mcq_results.get("total_questions", 0) + len(descriptive_results)
        questions_correct = mcq_results.get("correct_count", 0)
        
        # Add descriptive that scored > 50%
        for dr in descriptive_results:
            if dr.get("score", 0) > dr.get("max_score", 1) / 2:
                questions_correct += 1
        
        confidence = questions_correct / questions_attempted if questions_attempted > 0 else 0.5
        
        # Collect all misconceptions
        all_misconceptions = []
        for m in misconceptions.get("misconceptions", []):
            all_misconceptions.append(m.get("misconception", ""))
        for dr in descriptive_results:
            all_misconceptions.extend(dr.get("misconceptions_detected", []))
        
        # Collect weak and strong concepts
        weak_concepts = misconceptions.get("recommended_focus", [])
        strong_concepts = []  # Could be inferred from correct answers
        
        result = AssessmentResult(
            assessment_id=str(uuid.uuid4()),
            student_id=student_id,
            subject_code=subject_code,
            topic_code=topic_code,
            topic_name=topic_name,
            score=int(percentage),
            max_score=100,
            level=level,
            confidence=round(confidence, 2),
            misconceptions=all_misconceptions,
            weak_concepts=weak_concepts,
            strong_concepts=strong_concepts,
            questions_attempted=questions_attempted,
            questions_correct=questions_correct,
            created_at=datetime.now(),
        )
        
        return result.model_dump()
