"""Factory for creating agents based on configuration."""

import logging
from typing import Optional

from .base import BaseAgent, ToolRegistry
from .default import DefaultAgent

logger = logging.getLogger(__name__)


def create_agent(
    agent_type: str = "default",
    tool_registry: Optional[ToolRegistry] = None,
    **kwargs
) -> BaseAgent:
    """Create an agent based on configuration.

    Args:
        agent_type: Type of agent to create ('default', 'openrouter', etc.)
        tool_registry: Optional tool registry (created if not provided)
        **kwargs: Additional arguments for specific agent types
            - model: Model name for OpenRouter (e.g., 'anthropic/claude-sonnet-4')
            - temperature: LLM temperature (0.0-1.0)
            - max_tokens: Maximum tokens in response

    Returns:
        Configured agent instance

    Raises:
        ValueError: If agent type is unknown or required config is missing
    """
    if tool_registry is None:
        tool_registry = ToolRegistry()

    agent_type = agent_type.lower()

    if agent_type == "default":
        return DefaultAgent(tool_registry)
    elif agent_type == "openrouter":
        from .openrouter import OpenRouterAgent

        model = kwargs.get("model", "anthropic/claude-sonnet-4")
        temperature = kwargs.get("temperature", 0.3)
        max_tokens = kwargs.get("max_tokens", 1024)

        return OpenRouterAgent(
            tool_registry,
            model_name=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        raise ValueError(
            f"Unknown agent type: {agent_type}. "
            f"Available: default, openrouter"
        )


def get_available_agents() -> list[dict]:
    """Get list of available agent types with metadata.

    Returns:
        List of dicts with agent info
    """
    return [
        {
            "type": "default",
            "name": "Default",
            "description": "Command dispatcher (no LLM required)",
            "requires_llm": False,
        },
        {
            "type": "openrouter",
            "name": "OpenRouter",
            "description": "LLM-powered assistant (requires API key)",
            "requires_llm": True,
        },
    ]
