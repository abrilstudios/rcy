"""Agent system for TUI interaction.

This module provides an agent-based interaction layer for the TUI.
The default agent requires no LLM and simply dispatches commands.
LLM-powered agents can be enabled via config for richer interactions.
"""

from .base import BaseAgent, AgentResponse
from .default import DefaultAgent
from .factory import create_agent, get_available_agents

# OpenRouterAgent imported lazily to avoid requiring pydantic-ai
# when using default agent only

__all__ = [
    "BaseAgent",
    "AgentResponse",
    "DefaultAgent",
    "create_agent",
    "get_available_agents",
]
