"""
Agent C: Curriculum Planning Agent

Purpose: Decide WHAT to teach next and in what order.

Inputs:
- Learner profile (from Agent B)
- Assessment results (from Agent A)
- Syllabus structure

Outputs:
- Topic plan (what to teach next)
- Depth of explanation needed
- Prerequisites to cover
- Estimated duration
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from db.supabase_client import supabase_manager
from models.schemas import (
    CurriculumPlan,
    LearnerProfile,
    MasteryLevel,
)


# Class 10 syllabus structure (can be moved to database later)
CLASS_10_SYLLABUS = {
    "physics": {
        "name": "Physics",
        "topics": [
            {
                "topic_code": "motion",
                "topic_name": "Motion",
                "subtopics": ["Distance and Displacement", "Speed and Velocity", "Uniform and Non-uniform Motion", "Graphical Representation"],
                "prerequisites": [],
                "order": 1,
                "estimated_minutes": 45,
            },
            {
                "topic_code": "kinematics",
                "topic_name": "Equations of Motion",
                "subtopics": ["First Equation", "Second Equation", "Third Equation", "Graphical Derivation"],
                "prerequisites": ["motion"],
                "order": 2,
                "estimated_minutes": 60,
            },
            {
                "topic_code": "projectile_motion",
                "topic_name": "Projectile Motion",
                "subtopics": ["Horizontal Projectile", "Angular Projectile", "Maximum Height", "Maximum Range"],
                "prerequisites": ["kinematics"],
                "order": 3,
                "estimated_minutes": 60,
            },
            {
                "topic_code": "laws_of_motion",
                "topic_name": "Laws of Motion",
                "subtopics": ["Newton's First Law", "Newton's Second Law", "Newton's Third Law", "Applications"],
                "prerequisites": ["motion"],
                "order": 4,
                "estimated_minutes": 75,
            },
            {
                "topic_code": "gravitation",
                "topic_name": "Gravitation",
                "subtopics": ["Universal Law of Gravitation", "Free Fall", "Weight and Mass", "Gravitational Acceleration"],
                "prerequisites": ["laws_of_motion"],
                "order": 5,
                "estimated_minutes": 60,
            },
            {
                "topic_code": "work_energy",
                "topic_name": "Work and Energy",
                "subtopics": ["Work", "Kinetic Energy", "Potential Energy", "Conservation of Energy", "Power"],
                "prerequisites": ["laws_of_motion"],
                "order": 6,
                "estimated_minutes": 75,
            },
        ],
    },
    "chemistry": {
        "name": "Chemistry",
        "topics": [
            {
                "topic_code": "matter",
                "topic_name": "Matter in Our Surroundings",
                "subtopics": ["States of Matter", "Change of State", "Evaporation"],
                "prerequisites": [],
                "order": 1,
                "estimated_minutes": 45,
            },
            {
                "topic_code": "pure_substances",
                "topic_name": "Is Matter Around Us Pure",
                "subtopics": ["Elements", "Compounds", "Mixtures", "Solutions", "Separation Techniques"],
                "prerequisites": ["matter"],
                "order": 2,
                "estimated_minutes": 60,
            },
            {
                "topic_code": "atoms_molecules",
                "topic_name": "Atoms and Molecules",
                "subtopics": ["Laws of Chemical Combination", "Atoms", "Molecules", "Mole Concept"],
                "prerequisites": ["pure_substances"],
                "order": 3,
                "estimated_minutes": 75,
            },
            {
                "topic_code": "atomic_structure",
                "topic_name": "Structure of the Atom",
                "subtopics": ["Thomson's Model", "Rutherford's Model", "Bohr's Model", "Electron Configuration"],
                "prerequisites": ["atoms_molecules"],
                "order": 4,
                "estimated_minutes": 60,
            },
        ],
    },
    "maths": {
        "name": "Mathematics",
        "topics": [
            {
                "topic_code": "number_systems",
                "topic_name": "Number Systems",
                "subtopics": ["Rational Numbers", "Irrational Numbers", "Real Numbers", "Laws of Exponents"],
                "prerequisites": [],
                "order": 1,
                "estimated_minutes": 60,
            },
            {
                "topic_code": "polynomials",
                "topic_name": "Polynomials",
                "subtopics": ["Polynomials in One Variable", "Zeroes of Polynomial", "Remainder Theorem", "Factorization"],
                "prerequisites": ["number_systems"],
                "order": 2,
                "estimated_minutes": 75,
            },
            {
                "topic_code": "linear_equations",
                "topic_name": "Linear Equations in Two Variables",
                "subtopics": ["Linear Equations", "Solution of Linear Equation", "Graph of Linear Equation"],
                "prerequisites": ["polynomials"],
                "order": 3,
                "estimated_minutes": 60,
            },
            {
                "topic_code": "coordinate_geometry",
                "topic_name": "Coordinate Geometry",
                "subtopics": ["Cartesian System", "Plotting Points", "Distance Formula"],
                "prerequisites": ["linear_equations"],
                "order": 4,
                "estimated_minutes": 60,
            },
            {
                "topic_code": "triangles",
                "topic_name": "Triangles",
                "subtopics": ["Congruence of Triangles", "Properties of Triangles", "Inequalities in Triangles"],
                "prerequisites": [],
                "order": 5,
                "estimated_minutes": 75,
            },
        ],
    },
}


class CurriculumAgent(BaseAgent):
    """
    Agent C: Curriculum Planning Agent.
    
    Decides what to teach next based on:
    - Student's current mastery levels
    - Syllabus prerequisites
    - Weak topics that need reinforcement
    - Logical learning progression
    """

    def __init__(self, temperature: float = 0.1):
        super().__init__(temperature=temperature)
        self.syllabus = CLASS_10_SYLLABUS

    def _build_system_prompt(self) -> str:
        return """You are the Curriculum Planning Agent, an expert in educational sequencing and personalized learning paths for Class 10 students.

Your role is to:
1. Analyze student mastery levels and identify gaps
2. Determine the optimal next topic to teach
3. Consider prerequisites and logical progression
4. Adapt the learning path based on student performance

You follow pedagogical best practices for sequencing STEM content."""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method.
        
        Actions:
        - 'get_next_topic': Determine what to teach next
        - 'get_learning_path': Generate full learning path for a subject
        - 'check_prerequisites': Check if student is ready for a topic
        - 'get_syllabus': Get syllabus structure for a subject
        """
        action = input_data.get("action")
        
        if action == "get_next_topic":
            return await self.get_next_topic(
                student_id=input_data["student_id"],
                subject_code=input_data["subject_code"],
            )
        elif action == "get_learning_path":
            return await self.get_learning_path(
                student_id=input_data["student_id"],
                subject_code=input_data["subject_code"],
            )
        elif action == "check_prerequisites":
            return await self.check_prerequisites(
                student_id=input_data["student_id"],
                subject_code=input_data["subject_code"],
                topic_code=input_data["topic_code"],
            )
        elif action == "get_syllabus":
            return self.get_syllabus(
                subject_code=input_data["subject_code"],
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    async def get_next_topic(
        self,
        student_id: str,
        subject_code: str,
    ) -> Dict[str, Any]:
        """
        Determine the next topic to teach based on student progress.
        
        Algorithm:
        1. Get student's current mastery for all topics
        2. Find topics where prerequisites are met but topic not mastered
        3. Prioritize weak topics that need reinforcement
        4. Use LLM to make final decision considering learning context
        
        Returns:
            CurriculumPlan as dictionary
        """
        # Get learner profile
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Student profile not found"}
        
        # Get syllabus for subject
        if subject_code not in self.syllabus:
            return {"error": f"Unknown subject: {subject_code}"}
        
        subject_data = self.syllabus[subject_code]
        topics = subject_data["topics"]
        
        # Analyze student progress
        topic_status = []
        for topic in topics:
            topic_key = f"{subject_code}:{topic['topic_code']}"
            knowledge = profile.topic_knowledge.get(topic_key)
            
            # Check prerequisites
            prereqs_met = all(
                f"{subject_code}:{prereq}" in profile.strong_topics
                for prereq in topic["prerequisites"]
            )
            
            status = {
                "topic_code": topic["topic_code"],
                "topic_name": topic["topic_name"],
                "order": topic["order"],
                "prerequisites": topic["prerequisites"],
                "prereqs_met": prereqs_met,
                "mastery": knowledge.mastery_level.value if knowledge else "not_started",
                "score": knowledge.score if knowledge else 0,
                "is_weak": topic_key in profile.weak_topics,
                "is_strong": topic_key in profile.strong_topics,
            }
            topic_status.append(status)
        
        # Identify candidates
        candidates = []
        
        # Priority 1: Weak topics that need reinforcement
        for ts in topic_status:
            if ts["is_weak"] and ts["prereqs_met"]:
                candidates.append({**ts, "priority": "reinforce_weak"})
        
        # Priority 2: Not started topics where prereqs are met
        for ts in topic_status:
            if ts["mastery"] == "not_started" and ts["prereqs_met"]:
                candidates.append({**ts, "priority": "new_topic"})
        
        # Priority 3: Developing topics that can be improved
        for ts in topic_status:
            if ts["mastery"] == "developing" and ts["prereqs_met"]:
                candidates.append({**ts, "priority": "improve_developing"})
        
        if not candidates:
            return {
                "message": "All topics mastered or no eligible topics found",
                "recommendation": "Consider moving to next subject or advanced topics",
                "all_topics_status": topic_status,
            }
        
        # Use LLM to make intelligent selection
        prompt = self._format_prompt(
            task=f"""Select the best next topic to teach for this Class 10 {subject_data['name']} student.

## Student Profile
- Learning style: {profile.learning_style.value}
- Total study time: {profile.total_study_time_minutes} minutes
- Weak topics: {profile.weak_topics}
- Historical mistakes: {profile.historical_mistakes[-5:]}

## Candidate Topics
{self._format_candidates(candidates)}

## Instructions
1. Consider the student's weak areas and learning style
2. Prefer reinforcing weak topics if they're foundational
3. Prefer new topics if weak topics are advanced
4. Consider the logical sequence of topics
5. Select ONE topic and explain why""",
            output_format="""{
  "selected_topic_code": "kinematics",
  "selected_topic_name": "Equations of Motion",
  "priority": "reinforce_weak",
  "reason": "Student struggled with motion basics, needs reinforcement before advancing",
  "depth": "conceptual+visual",
  "subtopics_to_cover": ["First Equation", "Second Equation"],
  "estimated_duration_minutes": 45,
  "teaching_notes": "Start with graphical derivation since student is visual learner"
}"""
        )

        result = await self._invoke_llm_json(prompt)
        
        # Find the selected topic data
        selected_topic = None
        for topic in topics:
            if topic["topic_code"] == result.get("selected_topic_code"):
                selected_topic = topic
                break
        
        if not selected_topic:
            # Fallback to first candidate
            selected_topic = next(
                (t for t in topics if t["topic_code"] == candidates[0]["topic_code"]),
                topics[0]
            )
            result["selected_topic_code"] = selected_topic["topic_code"]
            result["selected_topic_name"] = selected_topic["topic_name"]
        
        return CurriculumPlan(
            topic_code=result["selected_topic_code"],
            topic_name=result.get("selected_topic_name", selected_topic["topic_name"]),
            subject_code=subject_code,
            priority=result.get("priority", "high"),
            depth=result.get("depth", "conceptual+visual"),
            subtopics=result.get("subtopics_to_cover", selected_topic.get("subtopics", [])),
            prerequisites=selected_topic.get("prerequisites", []),
            estimated_duration_minutes=result.get("estimated_duration_minutes", selected_topic.get("estimated_minutes", 30)),
            order_in_syllabus=selected_topic.get("order", 1),
        ).model_dump()

    def _format_candidates(self, candidates: List[Dict]) -> str:
        """Format candidate topics for LLM."""
        lines = []
        for c in candidates:
            lines.append(f"- **{c['topic_name']}** ({c['topic_code']})")
            lines.append(f"  Priority: {c['priority']}, Mastery: {c['mastery']}, Score: {c['score']}")
            if c['is_weak']:
                lines.append(f"  ⚠️ Marked as WEAK topic")
        return "\n".join(lines)

    async def get_learning_path(
        self,
        student_id: str,
        subject_code: str,
    ) -> Dict[str, Any]:
        """
        Generate a complete learning path for a subject.
        
        Returns ordered list of topics with estimated times and priorities.
        """
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Student profile not found"}
        
        if subject_code not in self.syllabus:
            return {"error": f"Unknown subject: {subject_code}"}
        
        subject_data = self.syllabus[subject_code]
        topics = subject_data["topics"]
        
        # Build learning path
        path = []
        total_time = 0
        
        for topic in sorted(topics, key=lambda x: x["order"]):
            topic_key = f"{subject_code}:{topic['topic_code']}"
            knowledge = profile.topic_knowledge.get(topic_key)
            
            status = "not_started"
            if topic_key in profile.strong_topics:
                status = "mastered"
            elif topic_key in profile.weak_topics:
                status = "needs_work"
            elif knowledge:
                status = knowledge.mastery_level.value
            
            # Estimate time based on mastery
            time_multiplier = {
                "not_started": 1.0,
                "weak": 1.5,
                "needs_work": 1.3,
                "developing": 0.8,
                "proficient": 0.5,
                "mastered": 0.0,  # Skip if mastered
            }
            
            estimated_time = int(topic["estimated_minutes"] * time_multiplier.get(status, 1.0))
            
            if status != "mastered":
                total_time += estimated_time
            
            path.append({
                "order": topic["order"],
                "topic_code": topic["topic_code"],
                "topic_name": topic["topic_name"],
                "status": status,
                "estimated_minutes": estimated_time,
                "subtopics": topic["subtopics"],
                "prerequisites": topic["prerequisites"],
            })
        
        return {
            "subject_code": subject_code,
            "subject_name": subject_data["name"],
            "learning_path": path,
            "total_estimated_minutes": total_time,
            "topics_remaining": len([p for p in path if p["status"] != "mastered"]),
            "topics_mastered": len([p for p in path if p["status"] == "mastered"]),
        }

    async def check_prerequisites(
        self,
        student_id: str,
        subject_code: str,
        topic_code: str,
    ) -> Dict[str, Any]:
        """
        Check if student has met prerequisites for a topic.
        """
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            return {"error": "Student profile not found"}
        
        if subject_code not in self.syllabus:
            return {"error": f"Unknown subject: {subject_code}"}
        
        topic = None
        for t in self.syllabus[subject_code]["topics"]:
            if t["topic_code"] == topic_code:
                topic = t
                break
        
        if not topic:
            return {"error": f"Unknown topic: {topic_code}"}
        
        prereqs_status = []
        all_met = True
        
        for prereq in topic["prerequisites"]:
            prereq_key = f"{subject_code}:{prereq}"
            is_met = prereq_key in profile.strong_topics
            if not is_met:
                all_met = False
            
            prereqs_status.append({
                "topic_code": prereq,
                "is_met": is_met,
                "current_mastery": profile.topic_knowledge.get(prereq_key, {}).get("mastery_level", "not_started"),
            })
        
        return {
            "topic_code": topic_code,
            "topic_name": topic["topic_name"],
            "prerequisites": prereqs_status,
            "all_prerequisites_met": all_met,
            "can_proceed": all_met or len(topic["prerequisites"]) == 0,
        }

    def get_syllabus(self, subject_code: str) -> Dict[str, Any]:
        """Get syllabus structure for a subject."""
        if subject_code not in self.syllabus:
            return {"error": f"Unknown subject: {subject_code}"}
        
        return {
            "subject_code": subject_code,
            "subject_name": self.syllabus[subject_code]["name"],
            "topics": self.syllabus[subject_code]["topics"],
            "total_topics": len(self.syllabus[subject_code]["topics"]),
        }
