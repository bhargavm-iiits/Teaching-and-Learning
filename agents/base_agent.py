"""
Base Agent class for the AI-Driven Personalized VR Teaching System.
All agents inherit from this class and use Anthropic Claude for LLM operations.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from config import config

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    
    Each agent has a single responsibility and communicates
    via structured inputs/outputs (Pydantic models).
    
    Uses Anthropic Claude as the LLM provider.
    """

    def __init__(
        self,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ):
        """
        Initialize the agent with an LLM instance.
        
        Args:
            temperature: LLM temperature (0.0 = deterministic, 1.0 = creative)
            model: Model name (defaults to config.ANTHROPIC_MODEL)
        """
        self.llm = ChatAnthropic(
            model=model or config.ANTHROPIC_MODEL,
            api_key=config.ANTHROPIC_API_KEY,
            base_url=config.ANTHROPIC_BASE_URL if config.ANTHROPIC_BASE_URL else None,
            temperature=temperature,
        )
        self._name = self.__class__.__name__

    @property
    def name(self) -> str:
        """Agent name for logging and identification."""
        return self._name

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method. Each agent implements its own logic.
        
        Args:
            input_data: Input parameters as a dictionary
            
        Returns:
            Output as a dictionary (can be converted to Pydantic model)
        """
        pass

    async def _invoke_llm(self, prompt: str) -> str:
        """
        Invoke the LLM with a prompt and return the response text.
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            The LLM's response as a string
        """
        response = await asyncio.get_event_loop().run_in_executor(
            None, self.llm.invoke, prompt
        )
        return response.content if hasattr(response, "content") else str(response)

    async def _invoke_llm_json(self, prompt: str) -> Dict[str, Any]:
        """
        Invoke the LLM and parse the response as JSON.
        
        Args:
            prompt: The prompt (should instruct LLM to return JSON)
            
        Returns:
            Parsed JSON as a dictionary
        """
        response = await self._invoke_llm(prompt)
        return self._parse_json(response)

    async def _invoke_llm_structured(
        self,
        prompt: str,
        output_model: Type[T],
    ) -> T:
        """
        Invoke the LLM and parse the response into a Pydantic model.
        
        Args:
            prompt: The prompt (should instruct LLM to return JSON matching the model)
            output_model: The Pydantic model class to parse into
            
        Returns:
            An instance of the output_model
        """
        response = await self._invoke_llm(prompt)
        data = self._parse_json(response)
        return output_model(**data)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM output, handling common formatting issues.
        
        Args:
            text: Raw LLM response text
            
        Returns:
            Parsed JSON dictionary
        """
        text = text.strip()
        
        # Try direct parsing first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass
        
        # Try to find any JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON array
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                return {"items": json.loads(text[start:end])}
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Failed to parse JSON from LLM response: {text[:200]}...")

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for this agent.
        Override in subclasses for agent-specific system prompts.
        """
        return f"You are {self.name}, an AI agent in an educational system."

    def _format_prompt(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        output_format: Optional[str] = None,
    ) -> str:
        """
        Format a prompt with consistent structure.
        
        Args:
            task: The main task/instruction
            context: Optional context data
            output_format: Optional JSON schema description
            
        Returns:
            Formatted prompt string
        """
        parts = [self._build_system_prompt(), "", task]
        
        if context:
            parts.append("\n## Context")
            for key, value in context.items():
                if isinstance(value, (dict, list)):
                    parts.append(f"\n### {key}\n```json\n{json.dumps(value, indent=2)}\n```")
                else:
                    parts.append(f"\n### {key}\n{value}")
        
        if output_format:
            parts.append(f"\n## Output Format\nRespond with a valid JSON object matching this structure:\n{output_format}")
            parts.append("\nReturn ONLY the JSON object, no additional text.")
        
        return "\n".join(parts)
