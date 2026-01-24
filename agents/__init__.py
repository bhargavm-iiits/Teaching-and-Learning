"""
Agents package for the AI-Driven Personalized VR Teaching System.
Contains all 6 agents for the multi-agent architecture.
"""

from agents.base_agent import BaseAgent
from agents.assessment_agent import AssessmentAgent
from agents.learner_profile_agent import LearnerProfileAgent

__all__ = [
    "BaseAgent",
    "AssessmentAgent",
    "LearnerProfileAgent",
]
