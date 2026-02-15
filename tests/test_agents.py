"""Tests for TUI agent system.

Uses Pydantic AI testing patterns:
- Direct tool schema validation
- Agent response verification
- Command parsing tests
"""

import pytest
from pydantic import ValidationError

# Import agent components
import sys
sys.path.insert(0, "src/python")

from tui.agents.base import ToolRegistry, AgentResponse
from tui.agents.default import DefaultAgent
from tui.agents.factory import create_agent, get_available_agents
from tui.agents.tools import (
    SliceTool, PresetTool, ImportTool, MarkersTool,
    SetTool, TempoTool, PlayTool, ExportTool, ZoomTool,
    TOOL_SCHEMAS, TOOL_ALIASES
)


class TestToolSchemas:
    """Test Pydantic tool schema validation."""

    def test_slice_tool_measures(self):
        """SliceTool accepts valid measures."""
        tool = SliceTool(measures=4)
        assert tool.measures == 4
        assert tool.transients is None
        assert tool.clear is False

    def test_slice_tool_transients(self):
        """SliceTool accepts valid transient threshold."""
        tool = SliceTool(transients=50)
        assert tool.transients == 50

    def test_slice_tool_transients_bounds(self):
        """SliceTool rejects out-of-range transients."""
        with pytest.raises(ValidationError):
            SliceTool(transients=101)
        with pytest.raises(ValidationError):
            SliceTool(transients=-1)

    def test_slice_tool_clear(self):
        """SliceTool clear flag."""
        tool = SliceTool(clear=True)
        assert tool.clear is True

    def test_preset_tool(self):
        """PresetTool requires preset_id."""
        tool = PresetTool(preset_id="amen_classic")
        assert tool.preset_id == "amen_classic"

    def test_preset_tool_required(self):
        """PresetTool preset_id is required."""
        with pytest.raises(ValidationError):
            PresetTool()

    def test_markers_tool(self):
        """MarkersTool accepts start/end times."""
        tool = MarkersTool(start=0.5, end=3.2)
        assert tool.start == 0.5
        assert tool.end == 3.2

    def test_markers_tool_reset(self):
        """MarkersTool reset flag."""
        tool = MarkersTool(reset=True)
        assert tool.reset is True

    def test_markers_tool_negative_rejected(self):
        """MarkersTool rejects negative times."""
        with pytest.raises(ValidationError):
            MarkersTool(start=-1.0)

    def test_set_tool(self):
        """SetTool accepts setting and value."""
        tool = SetTool(setting="bars", value=4)
        assert tool.setting == "bars"
        assert tool.value == 4

    def test_tempo_tool_bpm(self):
        """TempoTool accepts BPM."""
        tool = TempoTool(bpm=140.5)
        assert tool.bpm == 140.5

    def test_tempo_tool_measures(self):
        """TempoTool accepts measures for calculation."""
        tool = TempoTool(measures=4)
        assert tool.measures == 4

    def test_play_tool(self):
        """PlayTool accepts pattern."""
        tool = PlayTool(pattern=[1, 2, 3, 4])
        assert tool.pattern == [1, 2, 3, 4]
        assert tool.loop is False

    def test_play_tool_loop(self):
        """PlayTool loop flag."""
        tool = PlayTool(pattern=[1, 4, 2, 3], loop=True)
        assert tool.loop is True

    def test_play_tool_empty_pattern_rejected(self):
        """PlayTool rejects empty pattern."""
        with pytest.raises(ValidationError):
            PlayTool(pattern=[])

    def test_export_tool(self):
        """ExportTool accepts directory and format."""
        tool = ExportTool(directory="/tmp/output", format="wav")
        assert tool.directory == "/tmp/output"
        assert tool.format == "wav"

    def test_export_tool_invalid_format(self):
        """ExportTool rejects invalid format."""
        with pytest.raises(ValidationError):
            ExportTool(directory="/tmp", format="mp3")

    def test_zoom_tool(self):
        """ZoomTool accepts direction."""
        tool = ZoomTool(direction="in")
        assert tool.direction == "in"

    def test_zoom_tool_invalid_direction(self):
        """ZoomTool rejects invalid direction."""
        with pytest.raises(ValidationError):
            ZoomTool(direction="left")


class TestToolRegistry:
    """Test ToolRegistry functionality."""

    def test_register_and_get(self):
        """Register and retrieve a tool."""
        registry = ToolRegistry()
        handler = lambda x: f"sliced {x.measures}"
        registry.register("slice", SliceTool, handler)

        result = registry.get("slice")
        assert result is not None
        schema, h = result
        assert schema == SliceTool

    def test_list_tools(self):
        """List registered tools."""
        registry = ToolRegistry()
        registry.register("slice", SliceTool, lambda x: None)
        registry.register("preset", PresetTool, lambda x: None)

        tools = registry.list_tools()
        assert "slice" in tools
        assert "preset" in tools

    def test_call_tool(self):
        """Call a tool through registry."""
        registry = ToolRegistry()
        registry.register("slice", SliceTool, lambda x: f"sliced {x.measures}")

        result = registry.call("slice", measures=4)
        assert result == "sliced 4"

    def test_call_unknown_tool(self):
        """Calling unknown tool raises ValueError."""
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="Unknown tool"):
            registry.call("unknown")


class TestDefaultAgent:
    """Test DefaultAgent command parsing and dispatch."""

    @pytest.fixture
    def agent(self):
        """Create agent with mock registry."""
        registry = ToolRegistry()
        # Register a simple test handler
        registry.register("slice", SliceTool, lambda x: f"Sliced by {x.measures} measures")
        registry.register("preset", PresetTool, lambda x: f"Loaded {x.preset_id}")
        return DefaultAgent(registry)

    def test_agent_name(self, agent):
        """Agent has correct name."""
        assert agent.name == "default"

    def test_agent_no_llm_required(self, agent):
        """Agent doesn't require LLM."""
        assert agent.requires_llm is False

    def test_parse_slice_measures(self, agent):
        """Parse !slice 4 command."""
        response = agent.process("!slice 4")
        assert response.success
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["tool"] == "slice"
        assert response.tool_calls[0]["args"]["measures"] == 4

    def test_parse_slice_with_flag(self, agent):
        """Parse !slice --clear command."""
        response = agent.process("!slice --clear")
        assert response.success
        assert response.tool_calls[0]["args"]["clear"] is True

    def test_parse_preset(self, agent):
        """Parse !preset amen_classic command."""
        response = agent.process("!preset amen_classic")
        assert response.success
        assert response.tool_calls[0]["tool"] == "preset"
        assert response.tool_calls[0]["args"]["preset_id"] == "amen_classic"

    def test_parse_with_slash_prefix(self, agent):
        """Accept / prefix as well as !."""
        response = agent.process("/slice 4")
        assert response.success
        assert response.tool_calls[0]["tool"] == "slice"

    def test_unknown_command(self, agent):
        """Unknown command returns error."""
        response = agent.process("!unknown")
        assert not response.success
        assert "Unknown command" in response.message

    def test_no_prefix_error(self, agent):
        """Input without prefix returns error."""
        response = agent.process("slice 4")
        assert not response.success

    def test_alias_resolution(self, agent):
        """Aliases resolve to full command names."""
        response = agent.process("!s 4")  # 's' is alias for 'slice'
        assert response.success
        assert response.tool_calls[0]["tool"] == "slice"

    def test_history_tracking(self, agent):
        """Conversation history is tracked."""
        agent.process("!slice 4")
        agent.process("!preset amen")

        assert len(agent.history) == 4  # 2 user + 2 assistant
        assert agent.history[0].role == "user"
        assert agent.history[1].role == "assistant"

    def test_clear_history(self, agent):
        """History can be cleared."""
        agent.process("!slice 4")
        assert len(agent.history) > 0

        agent.clear_history()
        assert len(agent.history) == 0


class TestAgentFactory:
    """Test agent factory."""

    def test_create_default_agent(self):
        """Create default agent."""
        agent = create_agent("default")
        assert agent.name == "default"
        assert not agent.requires_llm

    def test_create_unknown_agent(self):
        """Unknown agent type raises error."""
        with pytest.raises(ValueError, match="Unknown agent type"):
            create_agent("unknown")

    def test_get_available_agents(self):
        """Get list of available agents."""
        agents = get_available_agents()
        assert len(agents) >= 1

        default = next(a for a in agents if a["type"] == "default")
        assert default["requires_llm"] is False


class TestToolAliases:
    """Test tool alias mappings."""

    def test_all_aliases_map_to_valid_tools(self):
        """All aliases point to valid tool names."""
        for alias, tool_name in TOOL_ALIASES.items():
            assert tool_name in TOOL_SCHEMAS, f"Alias '{alias}' -> '{tool_name}' not in TOOL_SCHEMAS"

    def test_common_aliases(self):
        """Common aliases are correct."""
        assert TOOL_ALIASES["s"] == "slice"
        assert TOOL_ALIASES["p"] == "preset"
        assert TOOL_ALIASES["h"] == "help"
        assert TOOL_ALIASES["q"] == "quit"
