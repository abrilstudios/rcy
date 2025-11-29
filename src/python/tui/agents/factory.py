"""Factory for creating agents based on configuration."""

from typing import Optional

from .base import BaseAgent, ToolRegistry
from .default import DefaultAgent


def create_agent(
    agent_type: str = "default",
    tool_registry: Optional[ToolRegistry] = None,
    **kwargs
) -> BaseAgent:
    """Create an agent based on configuration.

    Args:
        agent_type: Type of agent to create ('default', 'deepseek', etc.)
        tool_registry: Optional tool registry (created if not provided)
        **kwargs: Additional arguments for specific agent types

    Returns:
        Configured agent instance

    Raises:
        ValueError: If agent type is unknown
    """
    if tool_registry is None:
        tool_registry = ToolRegistry()

    agent_type = agent_type.lower()

    if agent_type == "default":
        return DefaultAgent(tool_registry)
    else:
        raise ValueError(
            f"Unknown agent type: {agent_type}. "
            f"Available: default"
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
        # Future agents:
        # {
        #     "type": "deepseek",
        #     "name": "DeepSeek Helper",
        #     "description": "AI assistant for breakbeat workflow",
        #     "requires_llm": True,
        # },
    ]
