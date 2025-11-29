"""Base agent interface and response types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from pydantic import BaseModel


@dataclass
class AgentResponse:
    """Response from an agent.

    Attributes:
        message: The text response to display to the user
        tool_calls: List of tool calls that were made
        success: Whether the operation succeeded
        error: Error message if success is False
    """
    message: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


@dataclass
class ConversationMessage:
    """A message in the conversation history.

    Attributes:
        role: 'user' or 'assistant'
        content: The message content
        tool_calls: Any tool calls made in this message
    """
    role: str  # 'user' or 'assistant'
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class ToolRegistry:
    """Registry for tools that agents can call.

    Tools are registered with a name, schema, and handler function.
    The schema is a Pydantic model that validates tool arguments.
    """

    def __init__(self):
        self._tools: dict[str, tuple[type[BaseModel], Callable]] = {}

    def register(
        self,
        name: str,
        schema: type[BaseModel],
        handler: Callable
    ) -> None:
        """Register a tool.

        Args:
            name: Tool name (e.g., 'slice', 'preset')
            schema: Pydantic model for validating arguments
            handler: Function to call with validated arguments
        """
        self._tools[name] = (schema, handler)

    def get(self, name: str) -> Optional[tuple[type[BaseModel], Callable]]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_schema(self, name: str) -> Optional[type[BaseModel]]:
        """Get the schema for a tool."""
        tool = self._tools.get(name)
        return tool[0] if tool else None

    def call(self, name: str, **kwargs) -> Any:
        """Call a tool with arguments.

        Args:
            name: Tool name
            **kwargs: Tool arguments

        Returns:
            Result from the tool handler

        Raises:
            ValueError: If tool not found or validation fails
        """
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        schema, handler = tool
        validated = schema(**kwargs)
        return handler(validated)


class BaseAgent(ABC):
    """Abstract base class for TUI agents.

    Agents process user input and return responses, optionally
    calling tools to perform actions.
    """

    def __init__(self, tool_registry: ToolRegistry):
        """Initialize with a tool registry.

        Args:
            tool_registry: Registry of available tools
        """
        self.tools = tool_registry
        self.history: list[ConversationMessage] = []

    @abstractmethod
    def process(self, user_input: str) -> AgentResponse:
        """Process user input and return a response.

        Args:
            user_input: The user's input string

        Returns:
            AgentResponse with message and any tool calls
        """
        pass

    def add_to_history(self, role: str, content: str, tool_calls: list[dict[str, Any]] = None) -> None:
        """Add a message to conversation history.

        Args:
            role: 'user' or 'assistant'
            content: Message content
            tool_calls: Any tool calls made
        """
        self.history.append(ConversationMessage(
            role=role,
            content=content,
            tool_calls=tool_calls or []
        ))

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for display."""
        pass

    @property
    @abstractmethod
    def requires_llm(self) -> bool:
        """Whether this agent requires an LLM."""
        pass
