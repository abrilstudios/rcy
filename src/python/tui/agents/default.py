"""Default agent that requires no LLM - pure command dispatch."""

import re
import shlex
from typing import Any

from .base import BaseAgent, AgentResponse, ToolRegistry
from .tools import TOOL_SCHEMAS, TOOL_ALIASES


class DefaultAgent(BaseAgent):
    """Default agent that dispatches commands without an LLM.

    This agent parses commands prefixed with ! or / and dispatches
    them directly to registered tools. No API key or LLM required.

    Command formats:
        !slice 4           -> slice with measures=4
        !preset amen       -> load preset
        /slice --clear     -> clear slices (legacy / format supported)
    """

    @property
    def name(self) -> str:
        return "default"

    @property
    def requires_llm(self) -> bool:
        return False

    def process(self, user_input: str) -> AgentResponse:
        """Process user input by parsing and dispatching commands.

        Args:
            user_input: User input string starting with ! or /

        Returns:
            AgentResponse with result message
        """
        user_input = user_input.strip()

        # Record in history
        self.add_to_history("user", user_input)

        # Check for command prefix
        if not user_input:
            return AgentResponse(
                message="",
                success=True
            )

        # Support both ! and / prefixes
        if user_input.startswith("!") or user_input.startswith("/"):
            user_input = user_input[1:]
        else:
            # Not a command - just echo back
            response = AgentResponse(
                message=f"Unknown input. Use !help for commands.",
                success=False
            )
            self.add_to_history("assistant", response.message)
            return response

        # Parse the command
        try:
            result = self._parse_and_execute(user_input)
            self.add_to_history("assistant", result.message, result.tool_calls)
            return result
        except Exception as e:
            response = AgentResponse(
                message=f"Error: {e}",
                success=False,
                error=str(e)
            )
            self.add_to_history("assistant", response.message)
            return response

    def _parse_and_execute(self, cmd_str: str) -> AgentResponse:
        """Parse command string and execute tool.

        Args:
            cmd_str: Command string without prefix (e.g., "slice 4")

        Returns:
            AgentResponse with result
        """
        try:
            tokens = shlex.split(cmd_str)
        except ValueError as e:
            return AgentResponse(
                message=f"Parse error: {e}",
                success=False,
                error=str(e)
            )

        if not tokens:
            return AgentResponse(
                message="Empty command",
                success=False,
                error="Empty command"
            )

        cmd_name = tokens[0].lower()
        args = tokens[1:]

        # Resolve aliases
        cmd_name = TOOL_ALIASES.get(cmd_name, cmd_name)

        # Check if tool exists
        schema = TOOL_SCHEMAS.get(cmd_name)
        if not schema:
            return AgentResponse(
                message=f"Unknown command: {cmd_name}. Use !help for available commands.",
                success=False,
                error=f"Unknown command: {cmd_name}"
            )

        # Parse arguments into kwargs
        kwargs = self._parse_args(args, schema)

        # Validate with Pydantic
        try:
            validated = schema(**kwargs)
        except Exception as e:
            return AgentResponse(
                message=f"Invalid arguments: {e}",
                success=False,
                error=str(e)
            )

        # Call the tool via registry
        tool_call = {
            "tool": cmd_name,
            "args": validated.model_dump(exclude_none=True)
        }

        try:
            result = self.tools.call(cmd_name, **validated.model_dump(exclude_none=True))
            return AgentResponse(
                message=result if isinstance(result, str) else str(result),
                tool_calls=[tool_call],
                success=True
            )
        except ValueError as e:
            # Tool not registered - return the validated call for the TUI to handle
            return AgentResponse(
                message=f"Execute: {cmd_name}",
                tool_calls=[tool_call],
                success=True
            )

    def _parse_args(self, args: list[str], schema: type) -> dict[str, Any]:
        """Parse command arguments into kwargs for the schema.

        Supports:
            - Positional args mapped to schema fields
            - --flag style boolean flags
            - --key value style options

        Args:
            args: List of argument strings
            schema: Pydantic model to infer field types

        Returns:
            Dict of kwargs for the schema
        """
        kwargs: dict[str, Any] = {}
        schema_fields = schema.model_fields

        # Get field names and their types
        field_names = list(schema_fields.keys())
        positional_fields = [
            name for name in field_names
            if not schema_fields[name].default and schema_fields[name].default is not False
        ]

        i = 0
        positional_idx = 0

        while i < len(args):
            arg = args[i]

            if arg.startswith("--"):
                # Flag or option
                key = arg[2:].replace("-", "_")

                if key in schema_fields:
                    field_info = schema_fields[key]
                    field_type = field_info.annotation

                    # Check if it's a boolean flag
                    if field_type == bool:
                        kwargs[key] = True
                        i += 1
                    elif i + 1 < len(args) and not args[i + 1].startswith("--"):
                        # Has a value
                        value = args[i + 1]
                        kwargs[key] = self._convert_value(value, field_type)
                        i += 2
                    else:
                        # Boolean flag
                        kwargs[key] = True
                        i += 1
                else:
                    i += 1
            else:
                # Positional argument - try to match to first unfilled field
                # Special case: if arg looks like a list [1,2,3], parse it
                if arg.startswith("[") and arg.endswith("]"):
                    # Parse as list
                    list_content = arg[1:-1]
                    items = [int(x.strip()) for x in list_content.split(",") if x.strip()]
                    # Find a list field
                    for name, field_info in schema_fields.items():
                        if name not in kwargs:
                            annotation = field_info.annotation
                            # Check if it's a list type
                            if hasattr(annotation, "__origin__") and annotation.__origin__ == list:
                                kwargs[name] = items
                                break
                else:
                    # Map to positional field based on schema order
                    for name, field_info in schema_fields.items():
                        if name not in kwargs and not name.startswith("_"):
                            annotation = field_info.annotation
                            # Skip boolean and list fields for positional
                            if annotation == bool:
                                continue
                            if hasattr(annotation, "__origin__") and annotation.__origin__ == list:
                                continue
                            kwargs[name] = self._convert_value(arg, annotation)
                            break

                i += 1

        return kwargs

    def _convert_value(self, value: str, target_type: type) -> Any:
        """Convert string value to target type.

        Args:
            value: String value
            target_type: Target Python type

        Returns:
            Converted value
        """
        # Handle Optional types
        origin = getattr(target_type, "__origin__", None)
        if origin is type(None) or str(origin) == "typing.Union":
            # Get the non-None type from Optional
            args = getattr(target_type, "__args__", ())
            for arg in args:
                if arg is not type(None):
                    target_type = arg
                    break

        if target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        elif target_type == bool:
            return value.lower() in ("true", "1", "yes")
        elif target_type == str:
            return value
        else:
            return value
