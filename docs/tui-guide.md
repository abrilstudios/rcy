# RCY TUI User Guide

The RCY TUI (Terminal User Interface) is the primary interface for slicing, playing, and exporting breakbeats. This guide covers all features and workflows.

## Quick Start

```bash
just run                     # Launch with default preset (Amen break)
just tui-preset think_break  # Launch with specific preset
```

## Modal Input System

RCY uses a **vim-style modal input system** with two modes:

### INSERT Mode (Default)

When you see `[INSERT]` in the status bar:
- Type naturally to compose AI queries or commands
- Start with `/` for direct commands (e.g., `/slice 4`)
- Press **Enter** to submit
- Press **ESC** to switch to SEGMENT mode

### SEGMENT Mode

When you see `[SEGMENT]` in the status bar:
- Keys directly trigger segment playback (no typing required)
- Press **i** to return to INSERT mode
- Press **ESC** to return to INSERT mode

This modal approach eliminates conflicts between typing and playback keys.

## Keyboard Reference

### Segment Playback Keys (SEGMENT Mode Only)

| Key | Segment |
|-----|---------|
| `1` | Segment 1 |
| `2` | Segment 2 |
| `3` | Segment 3 |
| `4` | Segment 4 |
| `5` | Segment 5 |
| `6` | Segment 6 |
| `7` | Segment 7 |
| `8` | Segment 8 |
| `9` | Segment 9 |
| `0` | Segment 10 |
| `q` | Segment 11 |
| `w` | Segment 12 |
| `e` | Segment 13 |
| `r` | Segment 14 |
| `t` | Segment 15 |
| `y` | Segment 16 |
| `u` | Segment 17 |
| `o` | Segment 19 |
| `p` | Segment 20 |

Note: `i` is reserved for switching to INSERT mode.

### Marker Navigation (SEGMENT Mode Only)

| Key | Action |
|-----|--------|
| `←/→` | Nudge focused marker (~10ms) |
| `Shift+←/→` | Fine nudge (~1ms) |
| `Ctrl+←/→` | Coarse nudge (~100ms) |
| `[` / `]` | Cycle focus through markers (L, segments, R) |

Focused markers are highlighted with brackets: `[L]`, `[R]`, or `◆` for segments.

### Mode Switching

| Key | Action |
|-----|--------|
| `ESC` (in INSERT) | Switch to SEGMENT mode, clear input |
| `i` (in SEGMENT) | Switch to INSERT mode |
| `ESC` (in SEGMENT) | Switch to INSERT mode |

### Navigation (INSERT Mode)

| Key | Action |
|-----|--------|
| `Up` | Previous command in history |
| `Down` | Next command in history |
| `Ctrl-R` | Reverse search history |
| `Ctrl-S` | Forward search (in search mode) |
| `Enter` | Submit command |

## Commands

All commands start with `/` and are entered in INSERT mode.

### File Operations

```
/open <file.wav>          Load an audio file
/preset <id>              Load a preset by ID
/presets                  List available presets
```

### Slicing

```
/slice <n>                Slice into n equal parts by measures
/slice --transients <n>   Slice by transient detection (0-100 sensitivity)
/slice --clear            Clear all slices
```

### Playback

```
/play 1 2 3 4             Play segments in sequence
/play q w e r             Play segments 11-14
/play 1 q 2 w             Mix number and letter keys
/play 1 2 3 --loop        Loop the pattern
/loop                     Play all segments in a loop
/stop                     Stop playback
```

### Tempo & Timing

```
/tempo <bpm>              Set adjusted playback tempo
/tempo --measures <n>     Calculate source tempo from measure count
/set bars <n>             Set number of bars (recalculates BPM)
/set release <ms>         Set tail fade duration in milliseconds
```

### Markers & Editing

```
/markers <start> <end>    Set L/R markers (in seconds)
/markers --reset          Reset markers to full file
/cut                      Cut audio to L/R region in-place
/nudge left|right         Nudge focused marker programmatically
```

Note: In SEGMENT mode, use arrow keys for nudging and `[`/`]` for focus cycling.

### Export

```
/export <directory>       Export SFZ + WAV samples to directory
```

### View

```
/zoom in                  Zoom in on waveform
/zoom out                 Zoom out on waveform
```

### System

```
/help                     Show help information
/quit                     Exit RCY
```

## AI-Powered Commands

RCY supports natural language input through an LLM agent. Instead of memorizing command syntax, you can type naturally:

```
slice this into 8 pieces
play the first four segments
export to my desktop
what's the current tempo?
```

### Configuring the AI Agent

The AI agent uses OpenRouter. To enable:

1. Get an API key from [OpenRouter](https://openrouter.ai/)
2. Create a `.env` file in the project root:
   ```
   OPENROUTER_API_KEY=your-key-here
   ```
3. Set the agent type in `config/config.json`:
   ```json
   {
     "agent": {
       "type": "openrouter",
       "openrouter": {
         "default_model": "anthropic/claude-sonnet-4",
         "temperature": 0.3,
         "max_tokens": 1024
       }
     }
   }
   ```

The LLM agent is lazy-loaded on first natural language input to avoid startup lag.

### Routing

- Commands starting with `/` are always handled by the fast DefaultAgent
- Natural language input is routed to the LLM agent (if configured)
- If no LLM is configured, use `/` commands

## Workflow Examples

### Basic Slicing Workflow

1. Load a break: `/preset amen_classic`
2. Slice it: `/slice 16`
3. Press **ESC** to enter SEGMENT mode
4. Press keys `1-0` and `q-p` to audition segments
5. Press **i** to return to INSERT mode
6. Export: `/export ~/samples/amen`

### Pattern Creation

1. Slice your break: `/slice 8`
2. Create a pattern: `/play 1 1 5 5 3 3 7 7 --loop`
3. Experiment with variations
4. Stop when done: `/stop`

### Working with Tempo

1. Load audio: `/open my_break.wav`
2. Set the bar count: `/set bars 4`
3. Adjust playback tempo: `/tempo 170`

### Using History

1. Press `Ctrl-R` to search history
2. Type part of a previous command
3. Press `Ctrl-R` again to cycle through matches
4. Press `Enter` to select, `ESC` to cancel

## Configuration

Configuration is stored in `config/config.json`. Key settings:

```json
{
  "audio": {
    "tailFade": {
      "enabled": true,
      "durationMs": 3,
      "curve": "linear"
    }
  },
  "agent": {
    "type": "default"
  }
}
```

### Tail Fade

The tail fade applies a short fade-out at the end of each segment to prevent clicks:

- `enabled`: Turn tail fade on/off
- `durationMs`: Fade duration (default: 3ms)
- `curve`: Fade curve type ("linear")

Adjust with `/set release <ms>`.

## Troubleshooting

### Segment keys not working

Make sure you're in SEGMENT mode (status shows `[SEGMENT]`). Press **ESC** to switch from INSERT mode.

### Commands not recognized

Ensure commands start with `/`. Natural language requires the LLM agent to be configured.

### Audio not playing

Check that the audio file is loaded and sliced. The waveform display should show segment markers.

### LLM agent errors

Verify your `OPENROUTER_API_KEY` is valid in the `.env` file.
