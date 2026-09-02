# RCY Development Guide

Core principles for working effectively in this codebase.

---

## 🎯 Core Principle: Use Tools, Not Scripts

**CRITICAL: Prefer composable CLI tools over writing Python code.**

### Bad (writing Python for everything):
```python
from audio_processor import WavAudioProcessor
from export_utils import ExportUtils
model = WavAudioProcessor(preset_id="apache_break")
# inline slicing, SFZ writing, MIDI writing...
```

### Good (using existing tools):
```bash
for preset in amen_classic apache_break; do
  uv run rcy-export --preset $preset --out exports/$preset
done
```

**Why this matters:**
- Tools are composable and reusable
- Each command is visible and debuggable
- Failures are isolated and recoverable
- No import boilerplate or error handling needed
- Easier to modify and adapt

---

## 🔧 Available Tools

### Project Tools
- `just run` - Run the TUI application (**always use this, never run Python directly**)
- `just test` - Run all tests
- `just test-file <file>` - Run specific test file
- `just setup` - Install the project and all extras with uv
- `just doctor` - Check python, presets and audio output
- `just smoke` - Headless slice and export of a bundled break
- `just export ...` - Headless slice and export (`rcy-export`)
- `just push <device> --manifest KIT.rcy.json` - Hand a kit to an installed device plugin (`rcy-push`)
- `./tools/bin/env` - Show environment info

### Audio Tools
- `audio-trim <file.wav>` - Analyze and suggest trim points for drum samples
- `audio-viz <file.wav> --open` - Visualize waveform with trim analysis

### Device Plugins
Core writes files and talks to no hardware. `rcy-push <device>` runs an
executable named `rcy-push-<device>` from PATH and exits 2 when none is
installed. Plugins are separate repositories: abrilstudios/rcy-akai and
abrilstudios/rcy-teenage-engineering. See AGENTS.md, "Pushing to hardware".

---

## 📋 Task Lists for Fault Tolerance

**CRITICAL: Break long operations into tasks that call CLI tools. Never write monolithic Python.**

### Bad (monolithic Python):
```python
# One giant script -- if it fails at step 15, you restart from scratch
for preset in presets:
    model = WavAudioProcessor(preset_id=preset)
    # slice, write WAVs, write SFZ, write MIDI, write manifest ...
    # then shell out to a device plugin
# ... 50 more lines
```

### Good (task list + CLI tools):
```
Task 1: "Export amen, 8 slices"   -> uv run rcy-export --preset amen_classic --resolution 2 --out exports/amen
Task 2: "Export apache, 8 slices" -> uv run rcy-export --preset apache_break --out exports/apache
Task 3: "Move first amen cut"     -> edit boundaries[1] in exports/amen/amen.rcy.json
Task 4: "Re-render amen"          -> uv run rcy-export --from-manifest exports/amen/amen.rcy.json
Task 5: "Push amen to bank A"     -> uv run rcy-push ep133 --manifest exports/amen/amen.rcy.json --project 9 --bank A
Task 6: "Push apache to bank B"   -> uv run rcy-push ep133 --manifest exports/apache/apache.rcy.json --project 9 --bank B
```

Each task is atomic: if task 5 fails, tasks 1-4 are already complete and their
files are on disk. Resume from task 5 instead of restarting everything.

**Benefits:**
- Progress is preserved across failures
- Easy to see what's done vs pending
- Can resume from interruption
- User can see progress in real-time
- Each step is visible and debuggable
- No monolithic Python with import boilerplate

---

## 🚨 Critical Rules

### Running the Application
```bash
just run
```
**That's it.** Don't use `python3 -m main`, don't activate venv, don't set PYTHONPATH manually.

### Before Long Operations
**Ask the user before operations >5 minutes.**

Examples:
- Pushing a full kit to a device plugin over MIDI
- Running full test suite
- Bulk audio processing

### Git Workflow
- Never commit without explicit permission or passing tests
- Never work directly on main unless requested
- Use descriptive branch names: `feature/`, `fix/`, `enhancement/`

### Error Handling
- Never use `hasattr()` to check if a method exists
- Let errors fail explicitly rather than silently degrade
- Better to crash with a clear error than skip functionality

---

## 🏗️ Project Structure

```
src/python/          # All source code (use absolute imports)
config/              # JSON configuration files
tests/               # Test files
tools/bin/           # CLI tools (prefer these over writing Python)
```

### Import Hygiene
- All imports at the top of the file
- Never modify `sys.path` dynamically
- Use absolute imports: `from export_utils import ExportUtils`

---

## 🧪 Testing

```bash
just test                                  # Run all tests
just test-file tests/test_kit_manifest.py  # Run specific file
```

- Write tests for new features
- Run tests before committing
- No test needs a device; tests that open the audio output do so the same way the export path does

---

## 🎵 Audio Sample Workflow

### Analyzing Samples
```bash
# Check if sample needs trimming
audio-trim sounds/606/kick.wav

# Visualize the waveform
audio-viz sounds/606/kick.wav --open

# Trim if needed
audio-trim sounds/606/kick.wav --trim sounds/606-trimmed/kick.wav
```

### Playing Samples Locally
```bash
afplay sounds/606-trimmed/kick.wav
```

---

## 📝 Key Takeaways

1. **Use tools, not scripts** - CLI tools are composable and debuggable
2. **Break into tasks** - Long operations should use task lists
3. **Check before acting** - Look at the manifest and output directory before re-exporting or pushing
4. **The manifest is the contract** - Plugins read `KIT.rcy.json`; edit it, don't bypass it
5. **Bash loops > Python loops** - For simple iterations, bash is clearer
6. **Ask before long ops** - Get permission for >5 minute operations
7. **just run** - That's how you run the app. Period.

---

## 🔍 When You're Stuck

1. Check available tools: `just --list`
2. Read tool help: `uv run rcy-export --help`, `uv run rcy-push --help`
3. Read AGENTS.md for the manifest format and CLI flags
4. Ask the user before writing new Python code
