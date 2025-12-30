"""TUI Application - Textual-based Terminal Interface for RCY.

A command-line interface for RCY breakbeat slicer with:
- ASCII waveform display
- Keyboard-driven segment playback (1-0, q-p keys)
- Command input (/import, /slice, /export, etc.)
- Agent-based interaction (!slice, !preset, etc.)
"""

import os
import threading
import time
from pathlib import Path
from typing import Optional
import logging

# Suppress noisy HTTP client loggers early (before any imports that might trigger them)
for _logger_name in ('httpx', 'httpcore', 'openai', 'pydantic_ai'):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

from textual.app import App, ComposeResult
from textual.widgets import Static, TextArea
from textual.binding import Binding

from logging_config import setup_logging

from audio_processor import WavAudioProcessor
from segment_manager import get_segment_manager
from config_manager import config
from export_utils import ExportUtils
from tui.widgets import WaveformWidget, CommandInput, CommandSuggester
from tui.widgets.bank import BankWidget
from tui.widgets.sounds import SoundsWidget
from tui.markers import MarkerManager, MarkerKind
from tui.page_manager import PageManager, PageType, SoundRef
from tui.agents import create_agent, BaseAgent
from tui.agents.base import ToolRegistry

# Pre-import ep133 module AND enumerate MIDI ports BEFORE Textual starts.
# Calling find_ports() inside Textual's event loop can cause issues with terminal.
try:
    from ep133 import EP133Device
    _EP133_AVAILABLE = True
    # Cache ports now, before Textual takes over the terminal
    _EP133_PORTS = EP133Device.find_ports()
except ImportError:
    _EP133_AVAILABLE = False
    _EP133_PORTS = (None, None)

logger = logging.getLogger(__name__)

# Key mappings for segment playback
SEGMENT_KEYS = {
    '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
    '6': 6, '7': 7, '8': 8, '9': 9, '0': 10,
    'q': 11, 'w': 12, 'e': 13, 'r': 14, 't': 15,
    'y': 16, 'u': 17, 'i': 18, 'o': 19, 'p': 20,
}


class PatternPlayer:
    """Plays a pattern of segments with optional looping."""

    def __init__(self, app: 'RCYApp'):
        self.app = app
        self.pattern: list[int] = []
        self.loop = False
        self.playing = False
        self.current_index = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self, pattern: list[int], loop: bool) -> None:
        """Start playing a pattern."""
        self.stop()  # Stop any existing playback

        self.pattern = pattern
        self.loop = loop
        self.current_index = 0
        self.playing = True
        self._stop_event.clear()

        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop pattern playback."""
        self._stop_event.set()
        self.playing = False
        if self.app.model:
            self.app.model.stop_playback()

    def _play_loop(self) -> None:
        """Background thread for pattern playback."""
        # Cache boundaries and times outside the loop
        boundaries = self.app.segment_manager.get_boundaries()
        if len(boundaries) < 2:
            self.playing = False
            return

        sample_rate = self.app.model.sample_rate
        times = [b / sample_rate for b in boundaries]
        num_segments = len(times) - 1

        pattern_len = len(self.pattern)

        while not self._stop_event.is_set():
            if not self.pattern:
                break

            segment_index = self.pattern[self.current_index]

            if segment_index < 1 or segment_index > num_segments:
                self.current_index = (self.current_index + 1) % pattern_len
                continue

            start_time = times[segment_index - 1]
            end_time = times[segment_index]

            # Play the segment (no UI update during loop - too slow)
            self.app.model.play_segment(start_time, end_time)

            # Wait for audio engine to signal playback completion
            # Use a timeout to allow checking stop_event periodically
            while not self._stop_event.is_set():
                if self.app.model.playback_ended_event.wait(timeout=0.05):
                    break  # Playback ended

            if self._stop_event.is_set():
                break

            self.current_index += 1
            if self.current_index >= pattern_len:
                if self.loop:
                    self.current_index = 0
                else:
                    break

        self.playing = False


class RCYApp(App):
    """Main Textual TUI application for RCY."""

    CSS_PATH = "rcy.tcss"

    BINDINGS = [
        Binding("space", "play_selection", "Play L→R", show=False),
        Binding("escape", "stop", "Stop", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
        # Marker focus bindings
        Binding("[", "cycle_focus_prev", "Prev Marker", show=False),
        Binding("]", "cycle_focus_next", "Next Marker", show=False),
    ]

    def __init__(self, model: WavAudioProcessor, ep133_device=None):
        super().__init__()
        self.model = model  # Pre-initialized before Textual starts
        self.preset_id = model.preset_id
        self.segment_manager = get_segment_manager()

        # Marker manager - unified focus model for L/R and segment markers
        self.marker_manager = MarkerManager(
            debounce_ms=50.0,
            nudge_samples=441,  # ~10ms at 44100Hz
            min_region_samples=441,  # ~10ms minimum region
        )

        # View state (legacy - kept for compatibility, synced from marker_manager)
        self.start_marker = 0.0
        self.end_marker = 0.0
        self.zoom_start = 0.0
        self.zoom_end = 0.0
        self.num_measures = 1
        self.playback_mode = "loop"
        self.target_bpm: Optional[float] = None

        # Pattern player
        self.pattern_player = PatternPlayer(self)

        # Page manager for notebook-style page switching
        self.page_manager = PageManager()

        # EP-133 device state (passed in pre-connected to avoid terminal issues)
        self._ep133_device = ep133_device
        self._ep133_project = 1  # Default project
        self._ep133_sounds: list = []  # Cached sounds list
        self._ep133_banks: dict = {}  # Cached bank assignments

        # Agent system
        self.agent: Optional[BaseAgent] = None

        # Status message
        self._status = "Welcome to RCY TUI. Type /help for commands."

    def compose(self) -> ComposeResult:
        """Create the application layout."""
        # Page widgets - only one visible at a time (notebook model)
        yield WaveformWidget(id="waveform")
        yield BankWidget(id="bank", classes="hidden")
        yield SoundsWidget(id="sounds", classes="hidden")

        output = TextArea(id="output", read_only=True, soft_wrap=True)
        output.can_focus = False
        yield output
        suggester = CommandSuggester(config_manager=config)
        yield CommandInput(id="command", suggester=suggester)

    def on_mount(self) -> None:
        """Initialize when app is mounted.

        Note: Audio model is pre-initialized in main() before Textual starts.
        This avoids terminal output issues from PortAudio initialization.
        """
        self._init_agent()
        self._append_output(self._status)
        self._try_ep133_autoconnect()
        # Model already loaded in main(), just sync UI state
        self._sync_model_to_ui()
        self._update_waveform()
        self.query_one("#command", CommandInput).focus()

    def _sync_model_to_ui(self) -> None:
        """Sync pre-initialized model state to UI components."""
        if not self.model:
            return
        self.end_marker = self.model.total_time
        self.zoom_end = self.model.total_time
        self.segment_manager.set_audio_context(
            len(self.model.data_left),
            self.model.sample_rate
        )
        self._cached_segment_times = None
        self.marker_manager.set_audio_context(
            len(self.model.data_left),
            self.model.sample_rate
        )
        self._sync_markers_from_manager()
        if self.model.preset_info:
            self.num_measures = self.model.preset_info.get('measures', 1)
        self.update_status(f"Loaded: {os.path.basename(self.model.filename)}")

    def _init_agent(self) -> None:
        """Initialize default agent. LLM agent is lazy-loaded on first use."""
        self._tool_registry = ToolRegistry()
        self._register_agent_tools(self._tool_registry)

        # Create default agent for fast /command processing
        self.default_agent = create_agent("default", self._tool_registry)

        # LLM agent loaded lazily on first natural language input
        self._llm_agent = None
        self._llm_agent_initialized = False

        logger.info("Initialized default agent for /commands")

    def _try_ep133_autoconnect(self) -> None:
        """Load EP-133 data if device is connected."""
        if not _EP133_AVAILABLE:
            logger.debug("EP-133 module not available (mido not installed)")
            return

        # Device is pre-connected in main() before Textual starts
        if self._ep133_device and self._ep133_device.is_connected:
            try:
                self._load_ep133_data()
                # Sync with ep133_handler module
                from tui import ep133_handler
                ep133_handler._device = self._ep133_device
            except Exception as e:
                logger.warning(f"EP-133 data load failed: {e}")

    def _load_ep133_data(self) -> None:
        """Fetch sounds and bank assignments from EP-133."""
        if not self._ep133_device or not self._ep133_device.is_connected:
            return

        # Fetch sounds list (slots 1-999)
        self._ep133_sounds = self._fetch_sounds_list()

        # Fetch bank assignments for current project
        self._ep133_banks = self._fetch_bank_assignments()

    def _fetch_sounds_list(self) -> list:
        """Get all sounds from EP-133 /sounds/ directory."""
        from tui.widgets.sounds import SoundInfo

        sounds = []
        try:
            # node 1000 = /sounds/ directory
            entries = self._ep133_device.list_directory(1000)
            for entry in entries:
                if not entry.get('is_dir', False):
                    # Extract slot number from node_id or name
                    node_id = entry.get('node_id', 0)
                    name = entry.get('name', '')
                    # node_id format varies, try to extract slot from name if numeric
                    slot = node_id - 1000 if node_id > 1000 else 0
                    sounds.append(SoundInfo(
                        slot=slot,
                        name=name,
                        duration_ms=None,
                    ))
        except Exception as e:
            logger.warning(f"Failed to list EP-133 sounds: {e}")

        return sounds

    def _fetch_bank_assignments(self) -> dict:
        """Get pad assignments for all banks in current project."""
        from tui.widgets.bank import PadInfo
        from ep133.pad_mapping import pad_to_node_id

        banks = {}
        project = self._ep133_project

        for bank in ['A', 'B', 'C', 'D']:
            pads = []
            for pad_num in range(1, 13):
                try:
                    node_id = pad_to_node_id(project, bank, pad_num)
                    metadata = self._ep133_device.get_metadata(node_id)
                    sound_slot = metadata.get('sym') if metadata else None
                    sound_name = self._get_sound_name(sound_slot) if sound_slot else None
                    pads.append(PadInfo(
                        pad_number=pad_num,
                        sound_name=sound_name,
                        sound_slot=sound_slot,
                    ))
                except Exception:
                    pads.append(PadInfo(pad_number=pad_num))
            banks[bank] = pads

        return banks

    def _get_sound_name(self, slot: int) -> str:
        """Look up sound name from cached sounds list."""
        for sound in self._ep133_sounds:
            if sound.slot == slot:
                return sound.name
        return f"Sound {slot}"

    def _populate_sounds_widget(self) -> None:
        """Push sounds data to SoundsWidget."""
        try:
            sounds_widget = self.query_one("#sounds", SoundsWidget)
            sounds_widget.set_sounds(self._ep133_sounds)
        except Exception:
            pass

    def _populate_bank_widget(self) -> None:
        """Push bank data to BankWidget."""
        try:
            bank_widget = self.query_one("#bank", BankWidget)
            bank = self.page_manager.bank_focus
            if bank in self._ep133_banks:
                bank_widget.set_pads(self._ep133_banks[bank])
        except Exception:
            pass

    def _refresh_ep133_data(self) -> None:
        """Re-fetch data after device mutation."""
        self._load_ep133_data()
        self._populate_sounds_widget()
        self._populate_bank_widget()

    def _register_agent_tools(self, registry: ToolRegistry) -> None:
        """Register tool handlers with the agent's tool registry."""
        from tui.agents.tools import (
            SliceTool, PresetTool, ImportTool, MarkersTool,
            SetTool, TempoTool, PlayTool, StopTool, ExportTool,
            ZoomTool, ModeTool, HelpTool, PresetsTool, QuitTool, CutTool, NudgeTool,
            SkinTool, EP133Tool, ViewTool, PickTool, DropTool,
        )
        from tui.ep133_handler import ep133_handler

        registry.register("slice", SliceTool, self._agent_slice)
        registry.register("preset", PresetTool, self._agent_preset)
        registry.register("import", ImportTool, self._agent_import)
        registry.register("markers", MarkersTool, self._agent_markers)
        registry.register("set", SetTool, self._agent_set)
        registry.register("tempo", TempoTool, self._agent_tempo)
        registry.register("play", PlayTool, self._agent_play)
        registry.register("stop", StopTool, self._agent_stop)
        registry.register("export", ExportTool, self._agent_export)
        registry.register("zoom", ZoomTool, self._agent_zoom)
        registry.register("mode", ModeTool, self._agent_mode)
        registry.register("help", HelpTool, self._agent_help)
        registry.register("presets", PresetsTool, self._agent_presets)
        registry.register("quit", QuitTool, self._agent_quit)
        registry.register("cut", CutTool, self._agent_cut)
        registry.register("nudge", NudgeTool, self._agent_nudge)
        registry.register("skin", SkinTool, self._agent_skin)

        # EP-133 unified command
        registry.register("ep133", EP133Tool, lambda args: ep133_handler(args, self))

        # Notebook page commands
        registry.register("view", ViewTool, self._agent_view)
        registry.register("pick", PickTool, self._agent_pick)
        registry.register("drop", DropTool, self._agent_drop)

    # Agent tool handlers
    def _agent_slice(self, args) -> str:
        if not self.model:
            return "No audio loaded"
        if args.clear:
            self._on_slice(None, None)
            return "Cleared all slices"
        self._on_slice(args.measures, args.transients)
        if args.measures:
            return f"Sliced by {args.measures} measures"
        elif args.transients is not None:
            num_segs = len(self.segment_manager.get_boundaries()) - 1
            return f"Found {num_segs} transients"
        return "Sliced"

    def _agent_preset(self, args) -> str:
        self._on_preset(args.preset_id)
        # Return the current status which was set by _on_preset
        return self._status

    def _agent_import(self, args) -> str:
        import soundfile as sf
        filepath = args.filepath
        try:
            info = sf.info(filepath)
            if info.samplerate != 44100:
                return f"Error: File must be 44100Hz (got {info.samplerate}Hz)"
            self._on_import(filepath)
            return f"Imported: {filepath}"
        except Exception as e:
            return f"Error importing file: {e}"

    def _agent_markers(self, args) -> str:
        if args.reset:
            self._on_markers(None, None)
            return "Reset markers to full file"
        self._on_markers(args.start, args.end)
        return f"Markers set: L={args.start:.2f}s R={args.end:.2f}s"

    def _agent_set(self, args) -> str:
        return self._on_set(args.setting, args.value)

    def _agent_tempo(self, args) -> str:
        self._on_tempo(args.bpm, args.measures)
        if args.measures:
            return f"Tempo calculated from {args.measures} measures"
        elif args.bpm:
            return f"Tempo set to {args.bpm:.1f} BPM"
        return "Tempo updated"

    def _agent_play(self, args) -> str:
        pattern = args.pattern
        if pattern is None:
            boundaries = self.segment_manager.get_boundaries()
            num_segments = len(boundaries) - 1
            if num_segments < 1:
                return "No segments to play"
            pattern = list(range(1, num_segments + 1))
        self._on_play(pattern, args.loop)
        loop_str = " (looping)" if args.loop else ""
        return f"Playing pattern: {pattern}{loop_str}"

    def _agent_stop(self, args) -> str:
        self._on_stop()
        return "Stopped"

    def _agent_export(self, args) -> str:
        self._on_export(args.directory, args.format)
        return f"Exported to {args.directory}"

    def _agent_zoom(self, args) -> str:
        self._on_zoom(args.direction)
        return f"Zoomed {args.direction}"

    def _agent_mode(self, args) -> str:
        self._on_mode(args.mode)
        return f"Playback mode: {args.mode}"

    def _agent_help(self, args) -> str:
        return """Commands (use ! or / prefix):
  /slice <n>              Slice by measures
  /preset <id>            Load preset
  /presets                List presets
  /set bars <n>           Set bars
  /set release <ms>       Tail decay to zero crossing (default: 3ms)
  /markers <s> <e>        Set markers
  /cut                    Cut audio to L/R region
  /nudge left|right       Nudge marker (--mode fine|coarse)
  /tempo <bpm>            Set tempo
  /play 1 2 3 4           Play pattern (1-0 for 1-10)
  /play q w e r           Play 11-14 (q-p for 11-20)
  /play 1 q --loop        Mix keys, loop pattern
  /loop                   Loop all segments
  /stop                   Stop playback
  /export <dir>           Export SFZ
  /zoom in|out            Zoom view
  /help                   Show help
  /quit                   Exit

EP-133 Commands:
  /ep133 connect        Connect to EP-133
  /ep133 disconnect     Disconnect from EP-133
  /ep133 status         Show connection status
  /ep133 list           List sounds on device
  /ep133 upload <bank>  Upload segments to bank (A/B/C/D)
  /ep133 clear <bank>   Clear pad assignments in bank"""

    def _agent_presets(self, args) -> str:
        return self._on_presets()

    def _agent_quit(self, args) -> str:
        self.exit()
        return "Goodbye!"

    def _agent_cut(self, args) -> str:
        """Handler for /cut command."""
        return self._on_cut()

    def _on_cut(self) -> str:
        """Cut audio to L/R region in-place."""
        if not self.model:
            return "No audio loaded"

        if self.start_marker >= self.end_marker:
            return "Error: L marker must be before R marker"

        old_duration = self.model.total_time
        new_duration = self.end_marker - self.start_marker

        # Use existing crop_to_time_range method
        success = self.model.crop_to_time_range(self.start_marker, self.end_marker)

        if success:
            # Reset to full file state (same as fresh load)
            self.start_marker = 0.0
            self.end_marker = self.model.total_time
            self.zoom_start = 0.0
            self.zoom_end = self.model.total_time

            # Sync marker manager with new audio context
            self.marker_manager.set_audio_context(
                len(self.model.data_left),
                self.model.sample_rate
            )

            # Clear segment cache
            self._cached_segment_times = None

            # Update display
            self._update_waveform()

            return f"Cut: {old_duration:.2f}s → {new_duration:.2f}s"
        else:
            return "Cut failed"

    def _agent_nudge(self, args) -> str:
        """Handler for /nudge command."""
        focused = self.marker_manager.focused_marker
        if not focused:
            return "No marker focused"

        base = self.marker_manager._nudge_samples
        if args.mode == "fine":
            delta = max(1, base // 10)
        elif args.mode == "coarse":
            delta = base * 3
        else:
            delta = base

        if args.direction == "left":
            delta = -delta

        if self.marker_manager.nudge_focused_marker(delta):
            self._on_marker_nudged()
            return f"[{focused.id}] moved {abs(delta)} samples"
        return "Nudge failed"

    def _agent_skin(self, args) -> str:
        """Handler for /skin command."""
        from tui.skin_manager import get_skin_manager

        skin_manager = get_skin_manager()

        if args.skin_name == "list":
            skins = skin_manager.list_skins()
            current = skin_manager.get_current_skin()
            lines = ["Available skins:"]
            for skin_name in skins:
                info = skin_manager.get_skin_info(skin_name)
                desc = info['description'] if info else ''
                marker = " (current)" if skin_name == current else ""
                lines.append(f"  {skin_name}{marker}: {desc}")
            return "\n".join(lines)

        if skin_manager.load_skin(args.skin_name):
            self._update_waveform()
            return f"Switched to skin: {args.skin_name}"
        else:
            available = ", ".join(skin_manager.list_skins())
            return f"Skin '{args.skin_name}' not found. Available: {available}"

    def _agent_view(self, args) -> str:
        """Handler for /view command - switch notebook page."""
        page_map = {
            "waveform": PageType.WAVEFORM,
            "bank": PageType.BANK,
            "sounds": PageType.SOUNDS,
        }
        page = page_map.get(args.page)
        if not page:
            return f"Unknown page: {args.page}"

        self.page_manager.switch_page(page, args.bank)
        self._update_page_visibility()

        if page == PageType.BANK and args.bank:
            return f"Switched to Bank {args.bank.upper()}"
        return f"Switched to {args.page} page"

    def _agent_pick(self, args) -> str:
        """Handler for /pick command - pick up a sound from current context."""
        page = self.page_manager.current_page

        if page == PageType.WAVEFORM:
            # Pick current slice as a sound (placeholder - needs segment context)
            return "Pick from waveform not yet implemented"
        elif page == PageType.BANK:
            # Pick sound assigned to focused pad
            return "Pick from bank not yet implemented"
        elif page == PageType.SOUNDS:
            # Pick focused sound from inventory
            try:
                sounds_widget = self.query_one("#sounds", SoundsWidget)
                sound = sounds_widget.get_focused_sound()
                if sound and sound.name:
                    self.page_manager.pick(SoundRef(slot=sound.slot, name=sound.name))
                    self._update_held_indicator()
                    return f"Picked: [{sound.slot:03d}] {sound.name}"
                else:
                    return "No sound at focused position"
            except Exception:
                return "Pick failed"
        return "Pick not available on this page"

    def _agent_drop(self, args) -> str:
        """Handler for /drop command - drop held sound onto current target."""
        if not self.page_manager.is_holding():
            return "Nothing held. Use /pick first."

        page = self.page_manager.current_page
        held = self.page_manager.held_sound

        if page == PageType.BANK:
            # Drop onto focused pad
            bank = self.page_manager.bank_focus
            pad = self.page_manager.bank_pad_focus
            # Actually assign would go here (EP-133 integration)
            self.page_manager.drop()
            self._update_held_indicator()
            return f"Assigned {held.name} to {bank}{pad:02d}"
        elif page == PageType.SOUNDS:
            # Drop into empty slot
            return "Drop to sounds page not yet implemented"
        else:
            return "Cannot drop on this page"

    def _update_page_visibility(self) -> None:
        """Update which page widget is visible based on PageManager state."""
        page = self.page_manager.current_page
        try:
            waveform = self.query_one("#waveform", WaveformWidget)
            bank = self.query_one("#bank", BankWidget)
            sounds = self.query_one("#sounds", SoundsWidget)
            command_input = self.query_one("#command", CommandInput)

            # Toggle visibility via CSS class
            waveform.set_class(page != PageType.WAVEFORM, "hidden")
            bank.set_class(page != PageType.BANK, "hidden")
            sounds.set_class(page != PageType.SOUNDS, "hidden")

            # Update command input placeholder to reflect current page
            command_input.set_page(page.value)

            # Update bank widget state with live data
            if page == PageType.BANK:
                bank.set_bank(self.page_manager.bank_focus)
                bank.set_focused_pad(self.page_manager.bank_pad_focus)
                bank.set_holding(self.page_manager.is_holding())
                # Populate with live EP-133 data
                if self._ep133_banks and self.page_manager.bank_focus in self._ep133_banks:
                    bank.set_pads(self._ep133_banks[self.page_manager.bank_focus])

            # Update sounds widget with category state and live data
            if page == PageType.SOUNDS:
                sounds.set_category(self.page_manager.sounds_category)
                sounds.set_category_focus(self.page_manager.sounds_category_focus)
                sounds.set_holding(self.page_manager.is_holding())
                if self._ep133_sounds:
                    sounds.set_sounds(self._ep133_sounds)
        except Exception:
            pass  # Widgets may not exist yet

    def _update_held_indicator(self) -> None:
        """Update visual indicators when held sound changes."""
        try:
            bank = self.query_one("#bank", BankWidget)
            sounds = self.query_one("#sounds", SoundsWidget)
            is_holding = self.page_manager.is_holding()
            bank.set_holding(is_holding)
            sounds.set_holding(is_holding)
        except Exception:
            pass

    def process_command(self, command: str) -> str:
        """Process /command through default agent (fast path)."""
        if not self.default_agent:
            return "Agent not initialized"
        response = self.default_agent.process(command)
        return response.message

    def _get_llm_agent(self):
        """Lazy-load LLM agent on first use."""
        if not self._llm_agent_initialized:
            self._llm_agent_initialized = True
            openrouter_cfg = config.get_setting("agent", "openrouter", {})
            try:
                self._llm_agent = create_agent(
                    "openrouter",
                    self._tool_registry,
                    model=openrouter_cfg.get("default_model", "anthropic/claude-sonnet-4"),
                    temperature=openrouter_cfg.get("temperature", 0.3),
                    max_tokens=openrouter_cfg.get("max_tokens", 1024),
                )
                logger.info(f"Initialized LLM agent: {self._llm_agent.name}")
            except ValueError as e:
                logger.warning(f"LLM agent not available: {e}")
                self._llm_agent = None
        return self._llm_agent

    def process_natural_language(self, text: str) -> str:
        """Process natural language through LLM agent."""
        llm_agent = self._get_llm_agent()
        if not llm_agent:
            return "LLM agent not available. Use /commands or set OPENROUTER_API_KEY."
        response = llm_agent.process(text)
        return response.message

    # Model initialization and handlers
    def _sync_markers_from_manager(self) -> None:
        """Sync legacy start/end_marker from marker_manager."""
        l_marker = self.marker_manager.get_marker("L")
        r_marker = self.marker_manager.get_marker("R")
        if l_marker and self.model:
            self.start_marker = l_marker.position / self.model.sample_rate
        if r_marker and self.model:
            self.end_marker = r_marker.position / self.model.sample_rate

    def _on_import(self, filepath: str) -> None:
        """Import a WAV file directly without preset metadata."""
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        self.preset_id = base_name
        # Create fresh model
        self.model = WavAudioProcessor()
        self.model.set_filename(filepath)
        # Reset markers to full file
        self.start_marker = 0.0
        self.end_marker = self.model.total_time
        self.zoom_start = 0.0
        self.zoom_end = self.model.total_time
        # Reset marker manager with new audio length
        self.marker_manager = MarkerManager(
            total_samples=len(self.model.data_left),
            sample_rate=self.model.sample_rate
        )
        # Clear segments
        self.segment_manager.set_audio_context(
            len(self.model.data_left), self.model.sample_rate
        )
        self._update_waveform()
        self.update_status(f"Imported: {base_name}")

    def _on_slice(self, measures: Optional[int], transients: Optional[int]) -> None:
        if not self.model:
            return

        if measures is None and transients is None:
            self.segment_manager.set_audio_context(
                len(self.model.data_left), self.model.sample_rate
            )
        elif measures:
            # Pass L/R markers as region bounds
            self.model.split_by_measures(
                measures,
                measure_resolution=1,
                start_time=self.start_marker,
                end_time=self.end_marker
            )
        elif transients is not None:
            threshold = transients / 100.0
            # Pass L/R markers as region bounds for transient detection
            self.model.split_by_transients(
                threshold,
                start_time=self.start_marker,
                end_time=self.end_marker
            )

        # Sync segment boundaries to MarkerManager for unified focus/nudge
        boundaries = self.segment_manager.get_boundaries()
        self.marker_manager.sync_from_boundaries(boundaries)

        # Invalidate segment cache after slicing
        self._cached_segment_times = None
        self._update_waveform()

    def _on_markers(self, start: Optional[float], end: Optional[float]) -> None:
        if not self.model:
            return

        if start is None and end is None:
            self.start_marker = 0.0
            self.end_marker = self.model.total_time
            self.update_status("Markers reset to full file")
        else:
            if start is not None:
                self.start_marker = max(0.0, start)
            if end is not None:
                max_time = self.model.total_time
                self.end_marker = min(end, max_time)
            self.update_status(f"Markers: L={self.start_marker:.2f}s R={self.end_marker:.2f}s")

        # Sync to MarkerManager
        start_samples = int(self.start_marker * self.model.sample_rate)
        end_samples = int(self.end_marker * self.model.sample_rate)
        self.marker_manager.set_region_markers(start_samples, end_samples)

        # Remove segments outside new region
        self._remove_segments_outside_region()

        # Sync boundaries to segment_manager
        new_boundaries = self.marker_manager.get_boundaries()
        self.segment_manager.set_boundaries(new_boundaries)

        # Invalidate cache
        self._cached_segment_times = None

        self._update_waveform()

    def _on_tempo(self, bpm: Optional[float], measure_count: Optional[int]) -> None:
        if not self.model:
            self.update_status("No audio loaded")
            return

        if measure_count:
            self.num_measures = measure_count
            # Pass L/R region for tempo calculation
            calculated_bpm = self.model.get_tempo(
                measure_count,
                start_time=self.start_marker,
                end_time=self.end_marker
            )
            self.model.calculate_source_bpm(
                measure_count,
                start_time=self.start_marker,
                end_time=self.end_marker
            )
            region_duration = self.end_marker - self.start_marker
            self.update_status(
                f"Source tempo: {calculated_bpm:.1f} BPM ({measure_count} bars in {region_duration:.2f}s)"
            )
        elif bpm:
            self.target_bpm = bpm
            self.model.set_playback_tempo(True, int(bpm))
            ratio = bpm / self.model.source_bpm if self.model.source_bpm > 0 else 1.0
            self.update_status(f"Playback tempo: {bpm:.0f} BPM (source: {self.model.source_bpm:.1f}, ratio: {ratio:.2f}x)")

    def _on_play(self, pattern: list[int], loop: bool) -> None:
        if not self.model:
            self.update_status("No audio loaded")
            return

        boundaries = self.segment_manager.get_boundaries()
        num_segments = len(boundaries) - 1

        if num_segments < 1:
            self.update_status("No segments defined. Use /slice first.")
            return

        for seg in pattern:
            if seg < 1 or seg > num_segments:
                self.update_status(f"Invalid segment {seg}. Valid range: 1-{num_segments}")
                return

        self.pattern_player.start(pattern, loop)
        loop_str = " (looping)" if loop else ""
        self.update_status(f"Playing pattern: {pattern}{loop_str}")

    def _on_stop(self) -> None:
        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()
        self.update_status("Stopped")

    def _on_presets(self) -> str:
        preset_list = config.get_preset_list()
        if not preset_list:
            return "No presets available"
        lines = ["Available presets:"]
        for preset_id, name in preset_list:
            lines.append(f"  {preset_id}: {name}")
        return "\n".join(lines)

    def _on_preset(self, preset_id: str) -> None:
        preset_info = config.get_preset_info(preset_id)
        if not preset_info:
            self.update_status(f"Unknown preset: {preset_id}")
            return

        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()

        # Swap audio data without recreating audio engine
        try:
            self.model.load_preset(preset_id)
            self.preset_id = preset_id
            self._sync_model_to_ui()
            self.update_status(f"Loaded preset: {preset_id}")
        except Exception as e:
            self.update_status(f"Failed to load {preset_id}: {e}")

        self._update_waveform()

    def _on_export(self, directory: str, fmt: str) -> None:
        if not self.model:
            self.update_status("No audio loaded")
            return

        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)

        try:
            stats = ExportUtils.export_segments(
                model=self.model,
                tempo=self.model.source_bpm,
                num_measures=self.num_measures,
                directory=directory,
                start_marker_pos=self.start_marker,
                end_marker_pos=self.end_marker
            )
            self.update_status(f"Exported {stats['segment_count']} segments to {directory}")
        except Exception as e:
            self.update_status(f"Export failed: {e}")

    def _on_mode(self, mode: str) -> None:
        self.playback_mode = mode
        if self.model:
            from enums import PlaybackMode
            pm = PlaybackMode.LOOP if mode == "loop" else PlaybackMode.ONE_SHOT
            self.model.audio_engine.set_playback_mode(pm)
        self.update_status(f"Playback mode: {mode}")

    def _on_zoom(self, direction: str) -> None:
        if not self.model:
            return

        duration = self.zoom_end - self.zoom_start
        center = (self.zoom_start + self.zoom_end) / 2

        if direction == "in":
            new_duration = duration / 2
        else:
            new_duration = min(duration * 2, self.model.total_time)

        self.zoom_start = max(0, center - new_duration / 2)
        self.zoom_end = min(self.model.total_time, center + new_duration / 2)
        self.update_status(f"View: {self.zoom_start:.2f}s - {self.zoom_end:.2f}s")
        self._update_waveform()

    def _on_set(self, setting: str, value) -> str:
        if setting in ('bars', 'measures'):
            if not isinstance(value, int) or value < 1:
                return "Error: bars must be a positive integer"

            if not self.model:
                return "No audio loaded"

            self.num_measures = value
            # Use L/R region for tempo calculation
            self.model.calculate_source_bpm(
                value,
                start_time=self.start_marker,
                end_time=self.end_marker
            )
            self._update_waveform()
            region_duration = self.end_marker - self.start_marker
            return f"Set bars={value}, BPM={self.model.source_bpm:.1f} ({region_duration:.2f}s region)"
        elif setting == 'release':
            if not isinstance(value, (int, float)) or value < 0:
                return "Error: release must be a positive number (ms)"

            # Update config in memory
            config.set_setting("audio", "tailFade", {
                "enabled": value > 0,
                "durationMs": int(value),
                "curve": "exponential"
            })

            # Update cached config in audio engine
            if self.model:
                self.model.audio_engine.update_tail_fade_config()

            return f"Set release={value}ms"
        else:
            return f"Unknown setting: {setting}. Available: bars, release"

    # UI update methods
    def _append_output(self, message: str) -> None:
        """Append a message to the output TextArea."""
        try:
            output = self.query_one("#output", TextArea)
            current = output.text
            if current:
                output.text = current + "\n" + message
            else:
                output.text = message
            # Scroll to bottom
            output.scroll_end(animate=False)
        except Exception:
            pass  # Widget may not exist yet

    def update_status(self, message: str) -> None:
        """Write a message to the output log."""
        # Avoid duplicate consecutive messages
        if message == self._status:
            return
        self._status = message
        self._append_output(message)

    def _update_waveform(self) -> None:
        """Update the waveform widget."""
        try:
            waveform = self.query_one("#waveform", WaveformWidget)
            if self.model:
                waveform.set_audio_data(self.model.data_left, self.model.sample_rate)
                waveform.filename = os.path.basename(self.model.filename)
                waveform.bpm = self.model.source_bpm
                waveform.bars = self.num_measures
                waveform.set_markers(self.start_marker, self.end_marker)
                waveform.set_view_range(self.zoom_start, self.zoom_end)

                boundaries = self.segment_manager.get_boundaries()
                slices = [b / self.model.sample_rate for b in boundaries]
                waveform.set_slices(slices)
                # Set internal segment markers only (exclude L/R) for focus indication
                internal_segments = slices[1:-1] if len(slices) > 2 else []
                waveform.set_segment_markers(internal_segments)

                # Set focused marker for visual indication
                waveform.set_focused_marker(self.marker_manager.focused_marker_id)
        except Exception:
            pass  # Widget may not exist yet

    # Segment playback - optimized for low latency key response
    def play_segment_by_index(self, index: int) -> None:
        """Play a segment by its 1-based index. Optimized for fast key response."""
        if not self.model:
            return

        # Use cached segment times if available
        if not hasattr(self, '_cached_segment_times') or self._cached_segment_times is None:
            self._update_segment_cache()

        if self._cached_segment_times is None or len(self._cached_segment_times) < 2:
            return

        num_segments = len(self._cached_segment_times) - 1
        if index < 1 or index > num_segments:
            return

        start_time = self._cached_segment_times[index - 1]
        end_time = self._cached_segment_times[index]

        # Direct call to audio engine - skip status update for speed
        self.model.play_segment(start_time, end_time)

    def _update_segment_cache(self) -> None:
        """Update cached segment times for fast playback."""
        if not self.model:
            self._cached_segment_times = None
            return
        boundaries = self.segment_manager.get_boundaries()
        if len(boundaries) < 2:
            self._cached_segment_times = None
            return
        sample_rate = self.model.sample_rate
        self._cached_segment_times = [b / sample_rate for b in boundaries]

    # Actions
    def action_play_selection(self) -> None:
        """Play the current L to R marker selection."""
        if not self.model:
            self.update_status("No audio loaded")
            return
        self.model.play_segment(self.start_marker, self.end_marker)
        self.update_status(f"Playing: {self.start_marker:.2f}s - {self.end_marker:.2f}s")

    def action_stop(self) -> None:
        """Stop playback."""
        self._on_stop()

    def action_nudge_left(self) -> None:
        """Nudge focused marker left."""
        if self.marker_manager.nudge_left():
            self._on_marker_nudged()

    def action_nudge_right(self) -> None:
        """Nudge focused marker right."""
        if self.marker_manager.nudge_right():
            self._on_marker_nudged()

    def _on_marker_nudged(self) -> None:
        """Handle marker position change after nudge."""
        focused = self.marker_manager.focused_marker

        # Always sync for visual feedback first
        self._sync_markers_from_manager()

        if focused and focused.kind in (MarkerKind.REGION_START, MarkerKind.REGION_END):
            # L or R changed - delete segments outside new region
            self._remove_segments_outside_region()

            # Recalculate tempo for new region
            if self.num_measures > 0 and self.model:
                self.model.calculate_source_bpm(
                    self.num_measures,
                    start_time=self.start_marker,
                    end_time=self.end_marker
                )

        # Sync marker boundaries back to segment_manager for playback
        new_boundaries = self.marker_manager.get_boundaries()
        self.segment_manager.set_boundaries(new_boundaries)

        self._cached_segment_times = None  # Invalidate cache
        self._update_waveform()

    def _remove_segments_outside_region(self) -> None:
        """Delete segment markers that fall outside L/R region."""
        l_marker = self.marker_manager.get_marker("L")
        r_marker = self.marker_manager.get_marker("R")
        if not l_marker or not r_marker:
            return

        l_pos = l_marker.position
        r_pos = r_marker.position

        # Find segment markers outside the region
        to_remove = []
        for marker in self.marker_manager.get_segment_markers():
            if marker.position <= l_pos or marker.position >= r_pos:
                to_remove.append(marker.id)

        # Remove them
        for marker_id in to_remove:
            self.marker_manager.remove_segment_marker(marker_id)

    def action_cycle_focus_next(self) -> None:
        """Cycle focus to next marker (by position)."""
        if self.marker_manager.cycle_focus(reverse=False):
            self._update_waveform()

    def action_cycle_focus_prev(self) -> None:
        """Cycle focus to previous marker (by position)."""
        if self.marker_manager.cycle_focus(reverse=True):
            self._update_waveform()

    # Event handlers
    def on_command_input_segment_key_pressed(self, event: CommandInput.SegmentKeyPressed) -> None:
        """Handle segment key pressed from CommandInput.

        Behavior depends on current page:
        - Waveform: play segment
        - Bank: select pad (1-12 only)
        - Sounds: select sound on current page (1-20)
        """
        if event.key not in SEGMENT_KEYS:
            return

        index = SEGMENT_KEYS[event.key]
        page = self.page_manager.current_page

        if page == PageType.WAVEFORM:
            self.play_segment_by_index(index)
        elif page == PageType.BANK:
            # Bank has 12 pads, keys 1-9,0,q,w map to pads 1-12
            if 1 <= index <= 12:
                self.page_manager.bank_pad_focus = index
                self._update_page_visibility()
        elif page == PageType.SOUNDS:
            # Select item on current page (1-12 = first 12 items on page)
            if 1 <= index <= 12:
                current_page = self.page_manager.get_sounds_page()
                new_focus = current_page * self.page_manager.sounds_per_page + (index - 1)
                category_size = self.page_manager.get_category_size()
                if new_focus < category_size:
                    self.page_manager.sounds_category_focus = new_focus
                    self._update_page_visibility()

    def on_command_input_marker_nudge(self, event: CommandInput.MarkerNudge) -> None:
        """Handle arrow keys from CommandInput.

        Behavior depends on current page:
        - Waveform: ←→ nudge markers, ↑↓ scroll output
        - Bank: ←→ cycle pads, ↑↓ cycle banks
        - Sounds: ←→ cycle sounds, ↑↓ cycle categories
        """
        page = self.page_manager.current_page

        if page == PageType.WAVEFORM:
            # Up/down scroll output on waveform page
            if event.direction in ("up", "down"):
                try:
                    output = self.query_one("#output", TextArea)
                    if event.direction == "up":
                        output.scroll_relative(y=-1)
                    else:
                        output.scroll_relative(y=1)
                except Exception:
                    pass
                return

            # Left/right nudge markers
            mode = getattr(event, 'mode', 'normal')

            base = self.marker_manager._nudge_samples
            if mode == "fine":
                delta = max(1, base // 10)
            elif mode == "coarse":
                delta = base * 10
            else:
                delta = base

            if event.direction == "left":
                delta = -delta

            if self.marker_manager.nudge_focused_marker(delta):
                self._on_marker_nudged()

        elif page == PageType.BANK:
            if event.direction == "left":
                # Previous pad (wraps 1 -> 12)
                pad = self.page_manager.bank_pad_focus
                self.page_manager.bank_pad_focus = 12 if pad == 1 else pad - 1
                self._update_page_visibility()
            elif event.direction == "right":
                # Next pad (wraps 12 -> 1)
                pad = self.page_manager.bank_pad_focus
                self.page_manager.bank_pad_focus = 1 if pad == 12 else pad + 1
                self._update_page_visibility()
            elif event.direction == "up":
                self.page_manager.prev_bank()
                self._update_page_visibility()
            elif event.direction == "down":
                self.page_manager.next_bank()
                self._update_page_visibility()

        elif page == PageType.SOUNDS:
            if event.direction == "left":
                self.page_manager.move_sounds_focus(-1)
                self._update_page_visibility()
            elif event.direction == "right":
                self.page_manager.move_sounds_focus(1)
                self._update_page_visibility()
            elif event.direction == "up":
                self.page_manager.prev_sounds_category()
                self._update_page_visibility()
            elif event.direction == "down":
                self.page_manager.next_sounds_category()
                self._update_page_visibility()

    def on_command_input_marker_cycle_focus(self, event: CommandInput.MarkerCycleFocus) -> None:
        """Handle [ and ] keys from CommandInput.

        Behavior depends on current page:
        - Waveform: cycle marker focus
        - Bank: switch banks (A/B/C/D)
        - Sounds: switch categories
        """
        page = self.page_manager.current_page

        if page == PageType.WAVEFORM:
            if event.reverse:
                self.action_cycle_focus_prev()
            else:
                self.action_cycle_focus_next()
        elif page == PageType.BANK:
            if event.reverse:
                self.page_manager.prev_bank()
            else:
                self.page_manager.next_bank()
            self._update_page_visibility()
        elif page == PageType.SOUNDS:
            if event.reverse:
                self.page_manager.prev_sounds_category()
            else:
                self.page_manager.next_sounds_category()
            self._update_page_visibility()

    def on_command_input_space_pressed(self, event: CommandInput.SpacePressed) -> None:
        """Handle space pressed in segment mode - toggle play/stop full sample."""
        if not self.model:
            return
        # Toggle: if playing, stop. Otherwise play full sample.
        if self.model.is_playing:
            self.model.stop_playback()
            self.update_status("Stopped")
        else:
            self.model.play_segment(0.0, self.model.total_time)
            self.update_status("Playing full sample")

    def on_command_input_page_cycle(self, event: CommandInput.PageCycle) -> None:
        """Handle Tab/Shift+Tab in segment mode - cycle notebook pages."""
        if event.reverse:
            self.page_manager.prev_page()
        else:
            self.page_manager.next_page()
        self._update_page_visibility()

    def on_input_submitted(self, event) -> None:
        """Handle command submission from Input widget."""
        text = event.value.strip()
        if not text:
            return

        if text.startswith('/') or text.startswith('!'):
            # Fast path: direct command processing (no LLM)
            result = self.process_command(text)
        else:
            # Natural language: route to LLM
            result = self.process_natural_language(text)

        self.update_status(result)
        # Clear the input
        event.input.value = ""

    def on_unmount(self) -> None:
        """Cleanup on exit."""
        self.pattern_player.stop()
        if self.model:
            self.model.stop_playback()
            self.model.audio_engine.stop_stream()


def main():
    """Entry point for TUI application."""
    import sys
    import argparse
    from tui.skin_manager import get_skin_manager

    parser = argparse.ArgumentParser(description='RCY TUI - Terminal Interface for Breakbeat Slicing')
    parser.add_argument('--preset', '-p', default='amen_classic',
                        help='Initial preset to load (default: amen_classic)')
    parser.add_argument('--skin', '-s', default='default',
                        help='Color skin to use (default: default). Use --skin list to show available.')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable debug logging')
    args = parser.parse_args()

    # Initialize centralized logging (suppresses console noise, logs to file)
    setup_logging()

    if args.debug:
        # Override console level for debug mode
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize skin manager and load requested skin
    skin_manager = get_skin_manager()

    if args.skin == 'list':
        print("Available skins:")
        for skin_name in skin_manager.list_skins():
            info = skin_manager.get_skin_info(skin_name)
            desc = info['description'] if info else ''
            print(f"  {skin_name}: {desc}")
        return

    if not skin_manager.load_skin(args.skin):
        print(f"Warning: Skin '{args.skin}' not found. Using default.")
        skin_manager.load_skin('default')

    # Pre-connect EP133 BEFORE Textual starts to avoid terminal issues
    ep133_device = None
    if _EP133_AVAILABLE:
        in_port, out_port = _EP133_PORTS
        if in_port and out_port:
            print("Connecting to EP-133...")
            try:
                ep133_device = EP133Device()
                ep133_device.connect()
                print(f"EP-133 connected: {in_port}")
            except Exception as e:
                print(f"EP-133 connection failed: {e}")
                ep133_device = None

    # Pre-initialize audio BEFORE Textual starts to avoid 'p' character bug
    # (PortAudio/sounddevice outputs to terminal when creating first stream)
    print(f"Loading preset: {args.preset}...")
    try:
        model = WavAudioProcessor(preset_id=args.preset)
    except Exception as e:
        print(f"Failed to load preset '{args.preset}': {e}")
        return

    app = RCYApp(model=model, ep133_device=ep133_device)
    app.run()


if __name__ == '__main__':
    main()
