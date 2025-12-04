"""OpenRouter LLM-powered agent using Pydantic AI."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

# Suppress httpx/httpcore logging before importing pydantic_ai
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from dotenv import load_dotenv

from .base import BaseAgent, AgentResponse, ToolRegistry

# Load .env from project root (relocatable)
_project_root = Path(__file__).parent.parent.parent.parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class ToolCall(BaseModel):
    """Structured tool call from LLM."""

    tool: str = Field(..., description="Tool name to call")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class AgentOutput(BaseModel):
    """Structured output from the agent."""

    message: str = Field(..., description="Response message to user")
    tool_calls: list[ToolCall] = Field(default_factory=list)


class OpenRouterAgent(BaseAgent):
    """LLM-powered agent using OpenRouter API."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        model_name: str = "anthropic/claude-sonnet-4",
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ):
        """Initialize OpenRouter agent.

        Args:
            tool_registry: Registry of available tools
            model_name: OpenRouter model identifier
            temperature: LLM temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
        """
        super().__init__(tool_registry)

        # Get API key from environment
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. "
                "Set it in .env file or as environment variable."
            )

        self.temperature = temperature
        self.max_tokens = max_tokens
        self._model_name = model_name

        # Create OpenRouter model
        self.model = OpenAIModel(
            model_name,
            provider="openrouter",
        )

        # Build system prompt with tool descriptions
        system_prompt = self._build_system_prompt()

        # Create Pydantic AI agent
        self.agent = Agent(
            self.model,
            output_type=AgentOutput,
            system_prompt=system_prompt,
        )

    @property
    def name(self) -> str:
        """Agent display name."""
        return f"OpenRouter ({self._model_name})"

    @property
    def requires_llm(self) -> bool:
        """Whether this agent requires an LLM."""
        return True

    def _build_system_prompt(self) -> str:
        """Build system prompt with available tools."""
        tools_desc = []
        for name in self.tools.list_tools():
            schema = self.tools.get_schema(name)
            if schema:
                doc = schema.__doc__ or ""
                # Clean up multiline docstrings
                doc_lines = [line.strip() for line in doc.strip().split("\n")]
                doc_clean = " ".join(line for line in doc_lines if line and not line.startswith("Args:"))

                fields = schema.model_fields
                args_list = []
                for k, v in fields.items():
                    annotation = getattr(v.annotation, "__name__", str(v.annotation))
                    args_list.append(f"{k}: {annotation}")
                args = ", ".join(args_list)
                tools_desc.append(f"- {name}({args}): {doc_clean}")

        tools_text = "\n".join(tools_desc)

        return f"""You are an AI assistant for RCY, a breakbeat audio slicer and sampler.
Help users slice, play, and export audio samples.

Available tools:
{tools_text}

When the user asks to do something, respond with the appropriate tool call(s).
For simple commands, just execute them. For ambiguous requests, ask for clarification.
Keep responses brief and focused on the task.

Important:
- Use tool names exactly as shown (e.g., "slice", "preset", "play")
- For /slice commands, use the "measures" parameter
- For /play commands, use "pattern" as a list of segment numbers (1-based)
- Segment keys: 1-0 map to segments 1-10, q-p map to segments 11-20"""

    def process(self, user_input: str) -> AgentResponse:
        """Process user input through LLM.

        Args:
            user_input: User's command or query

        Returns:
            AgentResponse with message and tool calls
        """
        # Run async agent - handle both standalone and event loop contexts
        try:
            try:
                # Check if we're in an existing event loop (e.g., Textual)
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                # We're in an event loop - use nest_asyncio or create task
                import nest_asyncio
                nest_asyncio.apply()
                result = asyncio.run(self._process_async(user_input))
            else:
                # No event loop - use asyncio.run directly
                result = asyncio.run(self._process_async(user_input))
            return result
        except Exception as e:
            return AgentResponse(
                message=f"Agent error: {e}",
                tool_calls=[],
                success=False,
                error=str(e),
            )

    async def _process_async(self, user_input: str) -> AgentResponse:
        """Async processing of user input."""
        result = await self.agent.run(
            user_input,
            model_settings={
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
        )

        output = result.output
        tool_results = []

        # Execute tool calls
        for tc in output.tool_calls:
            try:
                result_msg = self.tools.call(tc.tool, **tc.args)
                tool_results.append({
                    "tool": tc.tool,
                    "args": tc.args,
                    "result": result_msg,
                })
            except Exception as e:
                tool_results.append({
                    "tool": tc.tool,
                    "args": tc.args,
                    "error": str(e),
                })

        # Build response message
        if tool_results:
            messages = []
            for tr in tool_results:
                if "result" in tr:
                    messages.append(str(tr["result"]))
                else:
                    messages.append(f"Error: {tr['error']}")
            final_message = "\n".join(messages)
        else:
            final_message = output.message

        return AgentResponse(
            message=final_message,
            tool_calls=tool_results,
            success=True,
        )
