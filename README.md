# RCY

**RCY** is a terminal-based breakbeat slicer for cutting drum loops into samples and exporting them in the **SFZ** format for samplers like **TAL-Sampler**. Inspired by New Order's Movement, brutalist design, and hauntological software.

```
┌──────────────────────────────────────────────────────────────────────┐
│ amen.wav  137.7 BPM  4 bars  4 slices                                │
├──────────────────────────────────────────────────────────────────────┤
│L                ▼                ▼                ▼                 R│
│▇▄▆▁▅▂▂▂▂▂▂▃▅▅▁▂▁▆▃▄▅▁▅▁▁▂▂▂▃▅▅▄▁▂▁▆▂▆▂▅▃▂▁▂▂▂▇▁▃▁▅▂▂▂▃▄▆▅▁▂▂▂▃▇▃▃▂▅▃▃│
│▇▄▆▁▅▂▂▂▂▂▂▃▅▅▁▂▁▆▃▄▅▁▅▁▁▂▂▂▃▅▅▄▁▂▁▆▂▆▂▅▃▂▁▂▂▂▇▁▃▁▅▂▂▂▃▄▆▅▁▂▂▂▃▇▃▃▂▅▃▃│
│        1                2                 3                4         │
│0.00s                            3.49s                           6.97s│
└──────────────────────────────────────────────────────────────────────┘
```

## Quick Start

Needs [uv](https://docs.astral.sh/uv/) and, optionally, [just](https://github.com/casey/just).

```bash
git clone https://github.com/tnn1t1s/rcy.git
cd rcy
just setup                       # uv sync --all-extras
just doctor                      # python, presets, audio output
just smoke                       # slice the bundled Apache break headlessly
just tui                         # Launch with Amen break
just tui-preset apache_break     # Launch with Apache break
```

Without `just`, run `uv sync --all-extras` and then `uv run rcy`.

## Usage

### Launch

```bash
just run                    # Load default (Amen break)
just run --skin hacienda    # Load with hacienda color skin
just run --preset think_break  # Load specific preset
just run --skin list        # List available skins
```

### Modal Input System

RCY uses a **vim-style modal input** with two modes:

| Mode | Status Bar | Description |
|------|------------|-------------|
| **INSERT** | `[INSERT]` | Type commands (`/slice 4`) or natural language queries |
| **SEGMENT** | `[SEGMENT]` | Keys directly trigger segment playback |

**Mode switching:**
- **ESC** (in INSERT) → SEGMENT mode
- **i** (in SEGMENT) → INSERT mode

### Keyboard Controls

**SEGMENT Mode** (direct playback):

| Key | Action |
|-----|--------|
| `1-0` | Play segments 1-10 |
| `qwertyuop` | Play segments 11-19 (`i` reserved for mode switch) |
| `←/→` | Nudge focused marker (~10ms) |
| `Shift+←/→` | Fine nudge (~1ms) |
| `Ctrl+←/→` | Coarse nudge (~100ms) |
| `[` / `]` | Cycle focus through markers (L, segments, R) |
| `i` | Switch to INSERT mode |
| `ESC` | Switch to INSERT mode |

**INSERT Mode** (text input):

| Key | Action |
|-----|--------|
| `/` | Start a command |
| `Up/Down` | Navigate command history |
| `Ctrl-R` | Reverse search history |
| `Enter` | Submit command |
| `ESC` | Switch to SEGMENT mode |

### Commands

Type `/` to enter command mode, then:

```
/preset <id>              Load preset by ID
/presets                  List available presets
/import <file.wav>        Load audio file (44100Hz)

/slice <n>                Slice by measure count
/slice --transients <n>   Slice by transients (0-100)
/slice --clear            Clear all slices

/set bars <n>             Set number of bars (recalculates BPM)
/set release <ms>         Set tail fade duration (default: 3ms)
/markers <start> <end>    Set L/R markers (seconds)
/markers --reset          Reset markers to full file
/cut                      Cut audio to L/R region in-place
/nudge left|right         Nudge focused marker (use with --fine or --coarse)

/tempo <bpm>              Set adjusted playback tempo
/tempo --measures <n>     Calculate source tempo from measures

/play 1 2 3 4             Play pattern once (1-0 = segments 1-10)
/play q w e r             Play segments 11-14 (q-p = segments 11-20)
/play 1 q 2 w --loop      Mix numbers and keys, loop pattern
/loop                     Loop all segments (shortcut for /play --loop)
/stop                     Stop playback

/export <dir>             Export SFZ + samples
/zoom in|out              Zoom view
/skin                     List available color skins
/skin <name>              Switch to skin (default, high-contrast, monochrome, hacienda)
/help                     Show help
/quit                     Exit
```

## Presets

RCY includes classic breakbeats ready to slice:

### Core Breaks

| ID | Name | Artist | Bars |
|----|------|--------|------|
| `amen_classic` | Amen Break | The Winstons | 4 |
| `think_break` | Think (About It) | Lyn Collins | 1 |
| `apache_break` | Apache | Incredible Bongo Band | 2 |
| `apache_L` | Apache (Left Channel) | Incredible Bongo Band | 2 |
| `apache_R` | Apache (Right Channel) | Incredible Bongo Band | 2 |

### Rhythm Lab Collection

Download additional breaks from [rhythm-lab.com](https://rhythm-lab.com/breakbeats/):

```bash
./venv/bin/python sample-packs/rhythm-lab/setup.py          # Download all
./venv/bin/python sample-packs/rhythm-lab/setup.py --list   # List available
```

Available presets after download:

| ID | Name | Artist |
|----|------|--------|
| `rl_hot_pants` | Hot Pants | 20th Century |
| `rl_walk_this_way` | Walk This Way | Aerosmith |
| `rl_black_water_gold` | Black Water Gold | African Music Machine |
| `rl_house_rising_funk_1` | House Of Rising Funk (part1) | Afrique |
| `rl_house_rising_funk_2` | House Of Rising Funk (part2) | Afrique |
| `rl_cramp_your_style` | Cramp Your Style | All The People |
| `rl_keep_on_dancing` | Keep On Dancing | Alvin Cash |
| `rl_the_get_away` | The Get Away | Alvin Cash |
| `rl_no_good` | You Know I'm No Good | Amy Winehouse |
| `rl_the_rock` | The Rock | Atomic Rooster |
| `rl_its_moral_issue` | It's a Moral Issue | Baader Meinhof |
| `rl_keep_your_distance` | Keep Your Distance | Babe Ruth |
| `rl_listen_to_me` | Listen to Me | Baby Huey & The Babysitters |
| `rl_shack_up` | Shack Up | Banbarra |
| `rl_big_beat` | Big Beat | Billy Squier |
| `rl_blackbyrds_theme` | Blackbyrds Theme | Blackbyrds |
| `rl_take_me_mardi_gras` | Take Me To the Mardi Gras | Bob James |
| `rl_i_know_got_soul` | I Know You Got Soul | Bobby Byrd |

## Export

### SFZ Export

Export sliced samples to SFZ format for software samplers like TAL-Sampler:

```
/export ~/Desktop/my_break
```

Creates an SFZ file with all sliced samples mapped chromatically starting at C3.

The same export runs headlessly:

```bash
uv run rcy-export --preset apache_break --out exports/apache
uv run rcy-export --input break.wav --measures 2 --resolution 4 --out exports/break
```

Output is `001.wav ... NNN.wav`, `<dir>.sfz`, `<dir>.mid` and the kit manifest
`<dir>.rcy.json` inside `--out`. See [AGENTS.md](AGENTS.md) for flags and the full CLI list.

## Plugins

RCY core writes files and talks to no hardware. Sending a kit to a sampler is
the job of a plugin: an executable named `rcy-push-<device>` on your PATH that
takes `--manifest KIT.rcy.json`, reads the slice WAVs beside it, prints one JSON
object on stdout and exits non-zero on failure. `rcy-push <device> --manifest
KIT.rcy.json [plugin flags]` finds that executable and runs it; with nothing
installed it exits 2 and names what it looked for.

```bash
uv run rcy-export --preset apache_break --out exports/apache
uv run rcy-push ep133 --manifest exports/apache/apache.rcy.json --project 9 --bank A
```

Plugins live in their own repositories with their own dependencies:

- [abrilstudios/rcy-akai](https://github.com/abrilstudios/rcy-akai): Akai S2800 (`rcy-push-s2800`) and MPC2000XL (`rcy-push-mpc`)
- [abrilstudios/rcy-teenage-engineering](https://github.com/abrilstudios/rcy-teenage-engineering): EP-133 K.O. II (`rcy-push-ep133`)

## Features

- **Breakbeat Slicing**: Slice by measures or transient detection
- **Pattern Playback**: Play segments in custom sequences with looping
- **ASCII Waveform**: Visual display with L/R markers and slice points
- **Vim-Style Modal Input**: SEGMENT mode for instant playback, INSERT mode for commands
- **Marker Nudging**: Fine-tune slice points with arrow keys (normal/fine/coarse)
- **SFZ Export**: Generate SFZ files for software samplers
- **Command History**: Bash-style history with reverse search
- **Preset System**: Quick access to 900+ classic breaks (core + Rhythm Lab collection)
- **Configurable Skins**: Switch color themes at runtime or via CLI (`--skin hacienda`)
- **Agent Architecture**: Extensible command system with Pydantic validation

## Architecture

### Agent System

RCY uses an agent-based architecture for command processing. Commands are validated through Pydantic schemas before execution, enabling:

- **Type-safe command parsing**: Arguments are validated against schemas
- **Extensible tool registry**: New commands can be added as tool schemas
- **LLM integration**: Natural language commands via OpenRouter

The agent system lives in `src/python/tui/agents/`:

```
agents/
├── base.py        # BaseAgent class and ToolRegistry
├── default.py     # DefaultAgent - dispatches commands without LLM
├── openrouter.py  # OpenRouterAgent - LLM-powered natural language
├── tools.py       # Pydantic schemas for all commands
└── factory.py     # Agent factory for selecting agent type
```

**Default Agent**: Parses commands like `/slice 4` or `/play 1 2 3 --loop`, validates arguments against Pydantic schemas, and dispatches to registered handlers. No API key required.

**OpenRouter Agent**: Enables natural language interaction (e.g., "slice this into 8 pieces"). Uses Claude Sonnet via OpenRouter API. Requires API key.

**Configuration** (`config/config.json`):
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

To use the OpenRouter agent, create a `.env` file:
```
OPENROUTER_API_KEY=your-key-here
```

**Routing**: Commands starting with `/` always use the fast DefaultAgent. Natural language input is routed to the LLM agent when configured.

## Documentation

- [TUI User Guide](docs/tui-guide.md) - Complete guide to the terminal interface
- [Breakbeat Science](docs/breakbeat-science.md) - Core workflows that shaped jungle, drum & bass, and big beat

## Requirements

- Python 3.11 or newer (uv installs 3.12 from `.python-version`)
- uv; dependencies are declared in `pyproject.toml` and pinned in `uv.lock`
- Extras: `llm` (OpenRouter agent in the TUI), `viz` (plots). `just setup` installs both.

## Development

```bash
just test    # Run tests
just lint    # Run linter
just check   # lint + typecheck
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

[MIT License](LICENSE)
