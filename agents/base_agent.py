"""
Base Agent class for the AI-Driven Personalized VR Teaching System.
All agents inherit from this class and use Anthropic Claude for LLM operations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from config import config

logger = logging.getLogger(__name__)

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
            max_tokens=8192,  # prevent truncation on large lesson content responses
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

        Handles both plain-string and list-of-content-blocks responses
        from Claude (the Anthropic API returns content as either a str
        or a list[dict] with {"type": "text", "text": "..."} entries).

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM's response as a plain string
        """
        response = await asyncio.get_event_loop().run_in_executor(
            None, self.llm.invoke, prompt
        )
        content = response.content if hasattr(response, "content") else response

        # Claude sometimes returns a list of content blocks instead of a plain string
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                elif hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.append(str(block))
            text = "".join(parts)
            logger.debug(
                "[_invoke_llm] content was a list (%d blocks) — joined to %d chars",
                len(content),
                len(text),
            )
            return text

        return str(content)

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
        Parse JSON from LLM output, handling all common formatting patterns.

        Pre-processing applied to every candidate before json.loads:
          - Strip trailing commas in arrays/objects  (LLM common mistake)
          - Normalize escaped single-quotes

        Parse strategies (in order):
          1. Direct parse — LLM returned clean JSON
          2. ```json ... ``` fence
          3. ``` ... ``` fence (no language tag)
          4. First { ... last } extraction
          5. First [ ... last ] extraction (wrapped as {"items": [...]})
        """
        text = text.strip()

        def _clean(s: str) -> str:
            """Remove trailing commas before ] or } — the #1 LLM JSON mistake."""
            # trailing comma before closing bracket/brace, with optional whitespace
            s = re.sub(r",\s*([\}\]])", r"\1", s)
            return s

        def _try(candidate: str, label: str):
            """Try json.loads on raw then cleaned candidate; log on failure."""
            # Raw attempt
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as e:
                logger.debug(
                    "[_parse_json] %s failed: %s (pos %s)", label, e.msg, e.pos
                )
            # Cleaned attempt (strip trailing commas)
            cleaned = _clean(candidate)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.debug(
                    "[_parse_json] %s (cleaned) failed: %s (pos %s)",
                    label,
                    e.msg,
                    e.pos,
                )
            return None

        # 1. Direct parse
        result = _try(text, "direct")
        if result is not None:
            return result

        # 2. ```json ... ``` block — rfind closing fence
        if "```json" in text:
            start = text.find("```json") + 7
            if start < len(text) and text[start] == "\n":
                start += 1
            end = text.rfind("```")
            if end > start:
                candidate = text[start:end].strip()
                result = _try(candidate, "```json fence")
                if result is not None:
                    return result

        # 3. ``` ... ``` block (no language tag)
        if text.startswith("```"):
            start = text.find("\n") + 1
            end = text.rfind("```")
            if end > start:
                candidate = text[start:end].strip()
                result = _try(candidate, "``` fence (no tag)")
                if result is not None:
                    return result

        # 4. First { ... last } — bare JSON object
        brace_start = text.find("{")
        brace_end = text.rfind("}") + 1
        if brace_start != -1 and brace_end > brace_start:
            result = _try(text[brace_start:brace_end], "brace extraction")
            if result is not None:
                return result

        # 5. First [ ... last ] — JSON array
        bracket_start = text.find("[")
        bracket_end = text.rfind("]") + 1
        if bracket_start != -1 and bracket_end > bracket_start:
            result = _try(text[bracket_start:bracket_end], "bracket extraction")
            if result is not None:
                return {"items": result}

        logger.error(
            "[_parse_json] ALL strategies failed (len=%d). First 300 chars:\n%s",
            len(text),
            text[:300],
        )
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
                    parts.append(
                        f"\n### {key}\n```json\n{json.dumps(value, indent=2)}\n```"
                    )
                else:
                    parts.append(f"\n### {key}\n{value}")

        if output_format:
            parts.append(
                f"\n## Output Format\nRespond with a valid JSON object matching this structure:\n{output_format}"
            )
            parts.append("\nReturn ONLY the JSON object, no additional text.")

        return "\n".join(parts)
