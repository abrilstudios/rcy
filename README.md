# RCY

**RCY** is a tool designed to process breakbeat loops, enabling users to slice and export them in the **SFZ** format for seamless integration with samplers like the **TAL-Sampler**. Inspired by the aesthetics of New Order's Movement, brutalist design, and hauntological software, RCY combines utility with an appreciation for drum break history.

<img width="800" alt="RCY Screenshot" src="screenshots/rcy.png">

## Features

- **Breakbeat Slicing**: Automatically detects transients in breakbeat loops and slices them into individual hits
- **Manual Editing**: Precisely place slice points for customized break cutting patterns
- **Selection & Trimming**: Trim audio with start/end markers for perfect loop isolation
- **SFZ Export**: Generate SFZ files with mappings corresponding to the sliced samples for easy import into samplers
- **Historically-Informed Presets**: Access artist-specific slice patterns based on classic jungle and drum & bass techniques
- **Terminal Interface (TUI)**: Keyboard-driven interface with ASCII waveform, pattern playback, and command history
- **Cohesive Design Language**: Distinctive aesthetic based on a consistent color palette and typography

## Design Philosophy

RCY isn't just a tool—it's a perspective on breakbeat culture. The design references hauntological approaches to music technology, with:

- A color palette inspired by New Order's Movement album artwork
- Brutalist interface elements that emphasize function and clarity
- A typography system based on Futura PT Book
- A careful balance between utility and historical resonance

Read our [Breakbeat Science](docs/breakbeat-science.md) guide to understand the three core workflows that shaped jungle, drum & bass, and big beat, and how they're implemented in RCY. For those interested in the history and techniques of sampling in drum & bass, check out our comprehensive [Drum & Bass Sampling Techniques](docs/drum_and_bass_sample_techniques.md) document.

## Requirements

- **Python 3.11+**: RCY requires Python 3.11 or higher
- **Dependencies**: Install necessary Python packages using the provided `requirements.txt` file
  - For Python 3.13+ support, use `requirements-py313.txt` instead

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/tnn1t1s/rcy.git
   cd rcy
   ```

2. **Install Dependencies**:
   ```bash
   # For Python 3.11-3.12
   pip install -r requirements.txt

   # For Python 3.13+
   pip install -r requirements-py313.txt
   ```

## Development Setup

RCY uses modern Python development tools:

- **Code Quality**: [ruff](https://github.com/astral-sh/ruff) for linting and formatting
- **Type Checking**: [mypy](https://www.mypy-lang.org/) for static type analysis
- **Package Management**: `pyproject.toml` configuration
- **Testing**: pytest for unit and integration tests

For development details, see [CONTRIBUTING.md](CONTRIBUTING.md) and [CLAUDE.md](CLAUDE.md).

## Architecture

RCY follows a Model-View-Controller (MVC) pattern with clear separation of concerns. For detailed information about the system architecture and modernization phases, see [docs/mvc-current-flow.md](docs/mvc-current-flow.md).

## Usage

### GUI Application

1. **Launch the Application**:
   ```bash
   just run
   ```

2. **Work with Audio**:
   - The application loads with the Amen break by default
   - Load custom audio with File > Open
   - Set slice points automatically with "Split by Transients" or manually with Alt+Click
   - Adjust the Onset Threshold slider to control automatic transient detection sensitivity
   - Use the measure-based slicing for rhythmically perfect divisions

3. **Selection and Trimming**:
   - Set a start marker with Shift+Click (blue)
   - Set an end marker with Ctrl+Click (blue) 
   - Click the "Cut Selection" button to trim audio to just the selected region

4. **Export Results**:
   - Export your sliced samples and SFZ file using File > Export
   - Choose a destination directory for all exported files

### Terminal User Interface (TUI)

RCY also includes a terminal-based interface for keyboard-driven workflow and remote/headless operation.

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

**Launch the TUI**:
```bash
just tui                    # Load default preset
just tui-preset think_break # Load specific preset
```

**Keyboard Controls**:
- `1-0` - Play segments 1-10
- `q-p` - Play segments 11-20
- `Space` - Play L to R selection
- `Escape` - Stop playback
- `/` - Enter command mode

**Commands** (type `/help` for full list):
```
/open <file.wav>          Load audio file
/presets                  List available presets
/preset <id>              Load preset by ID
/slice --measures <n>     Slice by measure count
/slice --transients <n>   Slice by transients (0-100)
/markers <start> <end>    Set L/R markers (seconds)
/tempo <bpm>              Set adjusted playback tempo
/tempo --measures <n>     Calculate source tempo from measures
/play [1,2,3,4]           Play pattern once
/play --loop [1,4,2,3]    Play pattern looping
/stop                     Stop playback
/export <dir>             Export SFZ + samples
/zoom in|out              Zoom view
/quit                     Exit
```

**Command History**:
- `Up/Down` arrows - Navigate through previous commands
- `Ctrl-R` - Reverse search through history (bash-style)

## Historical Presets

The `presets/` directory contains historically-informed breakbeat slice patterns based on specific artists:

- **Amen Break**: Dillinja and LTJ Bukem cutting styles
- **Think Break**: Source Direct and Paradox approaches
- **Apache Break**: Photek-inspired edits

Each preset includes documentation about the artistic context and technical approach. For a deeper understanding of the cultural and technical foundations of these presets, see our [Breakbeat Science](docs/breakbeat-science.md) document. To learn about the technical design of RCY's audio processing, check our [Playback and Export Pipelines](designs/playback-export-pipelines.md) documentation.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your enhancements or bug fixes.

## License

This project is licensed under the [MIT License](LICENSE).