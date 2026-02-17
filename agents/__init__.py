"""
Agents package for the AI-Driven Personalized VR Teaching System.
Contains all 6 agents for the multi-agent architecture.

Agent Mapping:
- Agent A: AssessmentAgent - Evaluates student understanding
- Agent B: LearnerProfileAgent - Maintains student learning profile
- Agent C: CurriculumAgent - Decides what to teach next
- Agent D: PedagogyAgent - Decides how to teach (analogies, approach)
- Agent E: VRInstructionAgent - Generates Unity VR instructions
- Agent F: EvaluationAgent - Grades exams and provides feedback
"""

from agents.base_agent import BaseAgent
from agents.assessment_agent import AssessmentAgent
from agents.learner_profile_agent import LearnerProfileAgent
from agents.curriculum_agent import CurriculumAgent
from agents.pedagogy_agent import PedagogyAgent
from agents.vr_instruction_agent import VRInstructionAgent
from agents.evaluation_agent import EvaluationAgent

__all__ = [
    "BaseAgent",
    # Agent A
    "AssessmentAgent",
    # Agent B
    "LearnerProfileAgent",
    # Agent C
    "CurriculumAgent",
    # Agent D
    "PedagogyAgent",
    # Agent E
    "VRInstructionAgent",
    # Agent F
    "EvaluationAgent",
]
