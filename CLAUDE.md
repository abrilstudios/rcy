# RCY Development Guide

Core principles for working effectively in this codebase.

---

## 🎯 Core Principle: Use Tools, Not Scripts

**CRITICAL: Prefer composable CLI tools over writing Python code.**

### Bad (writing Python for everything):
```python
from s2800 import S2800
s = S2800()
s.open()
for kg in range(12):
    # inline parameter writes...
s.close()
```

### Good (using existing tools):
```bash
for kg in {0..11}; do
  just s2800-agent write-kg ZPLAY1 4 1 $kg
  just s2800-agent write-kg VPANO1 0 1 $kg
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
- `just setup` - Set up virtual environment
- `./tools/bin/env` - Show environment info

### Hardware Tools
- `tools/bin/ep133` - EP-133 device operations
- `tools/bin/s2800` - S2800 sample upload/list/delete
- `just s2800-agent` - S2800 protocol spec and live device parameters
- `just controller [PROG]` - TR-909 web GUI for real-time S2800 sound design (no server required)
- `just agent-start` / `just agent-stop` - ADK agent server
- `just ask <agent> <query>` - Query a running ADK agent

### Audio Tools
- `audio-trim <file.wav>` - Analyze and suggest trim points for drum samples
- `audio-viz <file.wav> --open` - Visualize waveform with trim analysis

---

## 🎹 S2800 Agent Tool

The s2800-agent is your primary interface for S2800 protocol work. **Use it instead of writing Python.**

### Common Operations

```bash
# Spec lookup (fast, offline)
just s2800-agent param ZPLAY1           # What is ZPLAY1?
just s2800-agent list keygroup pan      # Find pan-related params
just s2800-agent offset keygroup 53     # What's at byte offset 53?

# Device operations (requires S2800 connected)
just s2800-agent programs               # List programs
just s2800-agent samples                # List samples
just s2800-agent read-kg ZPLAY1 1 0     # Read prog 1, keygroup 0, ZPLAY1
just s2800-agent write-kg ZPLAY1 4 1 0  # Write value 4 to ZPLAY1
just s2800-agent summary 1              # Full program 1 summary
```

### Example: Configure 12 Keygroups for One-Shot Playback

```bash
# Set all keygroups to play-to-end mode with center pan
for kg in {0..11}; do
  just s2800-agent write-kg ZPLAY1 4 1 $kg    # Play to end
  just s2800-agent write-kg VPANO1 0 1 $kg    # Center pan
  just s2800-agent write-kg CP1 1 1 $kg       # Constant pitch
  echo "Configured keygroup $kg"
done
```

### When to Write Python vs Use Tools

| Task | Use |
|------|-----|
| Upload samples | `tools/bin/s2800 upload` |
| Configure keygroup params | `just s2800-agent write-kg` in a loop |
| Read current settings | `just s2800-agent read-kg` |
| Look up protocol details | `just s2800-agent param` |
| Create new S2800 features | Write Python (then expose as CLI tool) |

---

## 📋 Task Lists for Fault Tolerance

**CRITICAL: Break long operations into tasks that call CLI tools. Never write monolithic Python.**

### Bad (monolithic Python):
```python
# One giant script -- if it fails at step 15, you restart from scratch
s = S2800(); s.open()
for path, pitch, name in drum_map:
    audio = librosa.load(path, ...)
    s.upload_sample(pcm, 44100, name)
s.create_program("606 KIT", keygroups, ...)
# ... 50 more lines
s.close()
```

### Good (task list + CLI tools):
```
Task 1: "Delete all programs"     -> s2800 delete-all
Task 2: "Upload KICK"             -> s2800 upload sounds/606-trimmed/606_01_kick.wav
Task 3: "Upload SNARE"            -> s2800 upload sounds/606-trimmed/606_03_snare.wav
...
Task 13: "Upload THK 001"         -> s2800 upload exports/think_break/001.wav
...
Task 21: "Create 606 KIT program" -> (create_program call)
Task 22: "Create THINK BRK"       -> (create_program call)
Task 23: "Set PRGNUM=0 on all"    -> just s2800-agent write PRGNUM 0 0 && just s2800-agent write PRGNUM 0 1
Task 24: "Set PANPOS center"      -> just s2800-agent write PANPOS 0 1 && just s2800-agent write PANPOS 0 2
Task 25: "Set pan center on KGs"  -> for kg in {0..11}; do just s2800-agent write-kg VPANO1 0 1 $kg; done
```

Each task is atomic: if task 13 fails, tasks 1-12 are already complete. Resume
from task 13 instead of restarting everything.

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
- Uploading 12 samples to S2800 (~4-5 minutes)
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
- Use absolute imports: `from s2800 import S2800`

---

## 🎛️ S2800 Workflow Patterns

### Pattern 1: Check Before Upload
```bash
# Always list samples first
./venv/bin/python3 tools/bin/s2800 list

# Only upload if needed
if ! grep -q "KICK" samples.txt; then
  ./venv/bin/python3 tools/bin/s2800 upload sounds/kick.wav --name "KICK"
fi
```

### Pattern 2: Programs vs Samples
**Samples and programs are independent.**
- Samples persist in S2800 memory
- Programs reference samples by name
- Changing a program mapping does NOT require re-uploading samples

```bash
# GOOD: Just change the program
# (samples already exist)
delete_program(2)
create_program("NEW MAPPING", new_keygroups)

# BAD: Don't do this!
delete_all_samples()           # Wastes time
upload_all_samples()           # Wastes 4-5 minutes
create_program(...)
```

### Pattern 3: Multi-Timbral Setup (Multiple Programs via MIDI)
The S2800 (non-XL) has no dedicated MULTI mode. To play multiple programs
simultaneously on different MIDI channels:

1. Set all programs to the **same PRGNUM**
2. Give each program a **different PMCHAN**
3. **Select that PRGNUM on the front panel** (critical -- the S2800 only plays
   programs matching the currently selected program number)

```bash
# Set all 4 programs to PRGNUM=0
for prog in 0 1 2 3; do
  just s2800-agent write PRGNUM 0 $prog
done

# Verify channels are distinct
for prog in 0 1 2 3; do
  just s2800-agent read PMCHAN $prog
done

# Then select program 0 on the S2800 front panel
```

If you group programs under PRGNUM=0 but the front panel still shows an old
program number (e.g., 3), only the program that was at PRGNUM=3 will respond.
You must re-select the shared PRGNUM after grouping.

### Pattern 4: Verify Settings
```bash
# After configuring keygroups, spot-check a few
for kg in 0 5 11; do
  just s2800-agent read-kg ZPLAY1 1 $kg
  just s2800-agent read-kg VPANO1 1 $kg
done
```

---

## 🧪 Testing

```bash
just test                          # Run all tests
just test-file tests/test_s2800.py # Run specific file
pytest -m s2800                    # Run S2800 hardware tests
```

- Write tests for new features
- Run tests before committing
- Hardware tests require devices connected

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
3. **Check before acting** - List samples/programs before uploading/creating
4. **Use s2800-agent** - Don't guess protocol values, look them up
5. **Bash loops > Python loops** - For simple iterations, bash is clearer
6. **Ask before long ops** - Get permission for >5 minute operations
7. **just run** - That's how you run the app. Period.

---

## 🔍 When You're Stuck

1. Check available tools: `just --list`
2. Read tool help: `just s2800-agent --help`
3. Look up parameters: `just s2800-agent param <name>`
4. Ask the user before writing new Python code
