"""Default agent that requires no LLM - pure command dispatch."""

import re
import shlex
from typing import Any

from .base import BaseAgent, AgentResponse, ToolRegistry
from .tools import TOOL_SCHEMAS, TOOL_ALIASES

# Command expansions - commands that expand to other commands with args
COMMAND_EXPANSIONS = {
    "loop": "play --loop",
    "l": "play --loop",
}

# Key-to-segment mappings (same as keyboard shortcuts in TUI)
KEY_TO_SEGMENT = {
    '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
    '6': 6, '7': 7, '8': 8, '9': 9, '0': 10,
    'q': 11, 'w': 12, 'e': 13, 'r': 14, 't': 15,
    'y': 16, 'u': 17, 'i': 18, 'o': 19, 'p': 20,
}


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
        # Check for command expansions first (e.g., "loop" -> "play --loop")
        first_word = cmd_str.split()[0].lower() if cmd_str.split() else ""
        if first_word in COMMAND_EXPANSIONS:
            # Replace the command with its expansion, preserving any additional args
            rest = cmd_str[len(first_word):].strip()
            cmd_str = COMMAND_EXPANSIONS[first_word] + (" " + rest if rest else "")

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
                            if self._is_list_type(field_info.annotation):
                                kwargs[name] = items
                                break
                else:
                    # Check if this is a segment key (1-0, q-p) and there's an unfilled list field
                    if arg.lower() in KEY_TO_SEGMENT or arg.isdigit():
                        # Check if there's an unfilled list field to collect into
                        list_field_name = None
                        for name, field_info in schema_fields.items():
                            if name not in kwargs and self._is_list_type(field_info.annotation):
                                list_field_name = name
                                break

                        if list_field_name:
                            # Collect all remaining segment key args into a list
                            list_items = []
                            while i < len(args):
                                a = args[i].lower()
                                if a in KEY_TO_SEGMENT:
                                    list_items.append(KEY_TO_SEGMENT[a])
                                    i += 1
                                elif a.isdigit():
                                    list_items.append(int(a))
                                    i += 1
                                else:
                                    break
                            kwargs[list_field_name] = list_items
                            continue  # Skip the i += 1 at end since we already advanced

                    # Map to positional field based on schema order
                    for name, field_info in schema_fields.items():
                        if name not in kwargs and not name.startswith("_"):
                            annotation = field_info.annotation
                            # Skip boolean and list fields for positional
                            if annotation == bool:
                                continue
                            if self._is_list_type(annotation):
                                continue
                            kwargs[name] = self._convert_value(arg, annotation)
                            break

                i += 1

        return kwargs

    def _is_list_type(self, annotation: type) -> bool:
        """Check if annotation is a list type (including Optional[list[...]])."""
        origin = getattr(annotation, "__origin__", None)
        if origin is list:
            return True
        # Handle Optional[list[...]] which is Union[list[...], None]
        if str(origin) == "typing.Union":
            args = getattr(annotation, "__args__", ())
            for arg in args:
                if getattr(arg, "__origin__", None) is list:
                    return True
        return False

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
