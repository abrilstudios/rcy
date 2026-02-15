# RCY TUI User Guide

The RCY TUI (Terminal User Interface) is the primary interface for slicing, playing, and exporting breakbeats. This guide covers all features and workflows.

## Quick Start

```bash
just run                     # Launch with default preset (Amen break)
just run --preset think_break  # Launch with specific preset
just run --skin hacienda     # Launch with color skin
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
- Arrow keys nudge markers
- Tab/Shift+Tab cycle through notebook pages
- Press **i** or **ESC** to return to INSERT mode

This modal approach eliminates conflicts between typing and playback keys.

## Notebook Pages

RCY uses a **notebook-style page system**. The top display area switches between three pages, like flipping through a notebook. Context (held sounds, playback, selection) is preserved when switching pages.

| Page | Command | Purpose |
|------|---------|---------|
| **Waveform** | `/view waveform` | Slice, audition, temporal editing |
| **Bank** | `/view bank [A-D]` | EP-133 pad layout and assignment |
| **Sounds** | `/view sounds` | EP-133 sound inventory (999 slots) |

### Page Switching

In SEGMENT mode:
- **Tab**: Next page (Waveform → Bank → Sounds → Waveform)
- **Shift+Tab**: Previous page

Or use commands:
- `/view waveform` or `/v waveform`
- `/view bank` or `/view bank A`
- `/view sounds`

### Waveform Page

The default page showing the audio waveform with:
- L/R markers defining the working region
- Slice markers dividing the region into segments
- Segment numbers for playback reference
- Time axis

### Bank Page

Shows EP-133 pad layout (4x3 grid = 12 pads per bank):
- Navigate with arrow keys
- Focused pad is highlighted
- Shows assigned sound name or empty state
- Drop target indicator when holding a sound

### Sounds Page

Paginated list of all EP-133 sounds (slots 1-999):
- Navigate with j/k or arrow keys
- Shows slot number, name, duration
- Pick sounds to hold for placement
- PgUp/PgDn for page navigation

## Pick / Hold / Drop

Move sounds between pages without losing context. This mirrors drag-and-drop with keyboard:

1. **Pick**: Select a sound (`/pick` or Enter on Sounds page)
2. **Hold**: Sound stays "held" while navigating pages
3. **Drop**: Assign held sound to target (`/drop` or Enter on Bank page)

Status bar shows: `Held: <sound_name>` when holding a sound.

Press **ESC** to cancel and clear the held sound.

### Example Workflow

```
1. /view sounds          # Go to sounds inventory
2. Navigate to a sound
3. /pick                  # Pick up the sound
4. Tab                    # Switch to Bank page
5. Navigate to target pad
6. /drop                  # Assign sound to pad
```

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

### Navigation & Editing (SEGMENT Mode Only)

| Key | Action |
|-----|--------|
| `←/→` | Nudge focused marker (~10ms) |
| `Shift+←/→` | Fine nudge (~1ms) |
| `Ctrl+←/→` | Coarse nudge (~100ms) |
| `[` / `]` | Cycle focus through markers (L, segments, R) |
| `Tab` | Next notebook page |
| `Shift+Tab` | Previous notebook page |
| `Space` | Play/stop full sample |
| `↑/↓` | Scroll output panel |

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
| `Tab` | Cycle through completions |
| `Shift+Tab` | Cycle backwards through completions |
| `Enter` | Submit command |

## Commands

All commands start with `/` and are entered in INSERT mode.

### File Operations

```
/import <file.wav>        Load an audio file (44100Hz required)
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
/nudge left --fine        Fine nudge (~1ms)
/nudge right --coarse     Coarse nudge (~100ms)
```

Note: In SEGMENT mode, use arrow keys for nudging and `[`/`]` for focus cycling.

### Notebook Pages

```
/view waveform            Switch to waveform page
/view bank                Switch to bank page (current bank)
/view bank A              Switch to bank page, focus bank A
/view sounds              Switch to sounds page
/pick                     Pick up sound from current context
/drop                     Drop held sound onto current target
```

### Export

```
/export <directory>       Export SFZ + WAV samples to directory
```

### View & Appearance

```
/zoom in                  Zoom in on waveform
/zoom out                 Zoom out on waveform
/skin                     List available color skins
/skin <name>              Switch skin (default, high-contrast, monochrome, hacienda)
```

### System

```
/help                     Show help information
/quit                     Exit RCY
```

## EP-133 K.O. II Integration

RCY includes direct integration with the Teenage Engineering EP-133 sampler via MIDI SysEx.

### Setup

Connect EP-133 via USB. No additional configuration needed.

### Commands

```
/ep133 connect              Connect to EP-133 (auto-detects MIDI)
/ep133 disconnect           Disconnect from EP-133
/ep133 status               Check connection status
/ep133 set project <1-9>    Set target project (must match your EP-133 selection)
/ep133 list                 List sounds on device
/ep133 upload <bank> <slot> Upload segments to bank (A/B/C/D) starting at slot
/ep133 clear <bank>         Clear all pad assignments in bank
```

### EP-133 Structure

- 9 projects (1-9) — set via `/ep133 set project <n>`
- 4 banks per project (A, B, C, D)
- 12 pads per bank
- 999 sound slots (USER1: 700-799 recommended)

### Workflow Example

```bash
/preset amen_classic       # Load the Amen break
/slice 8                   # Slice into 8 segments
/ep133 connect             # Connect to EP-133
/ep133 set project 9       # Target project 9 (match your EP-133 dial)
/ep133 upload A 700        # Upload segments to bank A, slots 700+
```

Samples are named `{preset}_{segment:03d}` (e.g., `amen_classic_001`) for easy identification on the device.

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

1. Import audio: `/import my_break.wav`
2. Set the bar count: `/set bars 4`
3. Adjust playback tempo: `/tempo 170`

### Marker Editing

1. Enter SEGMENT mode: **ESC**
2. Use `[` and `]` to focus on a marker
3. Nudge with arrow keys (Shift for fine, Ctrl for coarse)
4. Cut to region: `/cut`

### EP-133 Sound Placement (Notebook Pages)

1. Connect: `/ep133 connect`
2. Go to sounds: `/view sounds` or **Tab**
3. Navigate to desired sound
4. Pick it: `/pick`
5. Go to bank: `/view bank A` or **Tab**
6. Navigate to target pad
7. Drop it: `/drop`

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

### Color Skins

RCY includes several color skins:

- `default`: Standard colors
- `high-contrast`: Maximum visibility
- `monochrome`: Minimal grayscale
- `hacienda`: Inspired by The Hacienda

Switch at runtime with `/skin <name>` or launch with `--skin <name>`.

## Troubleshooting

### Segment keys not working

Make sure you're in SEGMENT mode (status shows `[SEGMENT]`). Press **ESC** to switch from INSERT mode.

### Commands not recognized

Ensure commands start with `/`. Natural language requires the LLM agent to be configured.

### Audio not playing

Check that the audio file is loaded and sliced. The waveform display should show segment markers.

### LLM agent errors

Verify your `OPENROUTER_API_KEY` is valid in the `.env` file.

### Import fails with sample rate error

RCY requires 44100Hz audio files. Convert your file before importing.

### Tab not cycling pages

Tab cycles pages only in SEGMENT mode. In INSERT mode, Tab is used for command completion.
