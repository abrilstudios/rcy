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
  ./venv/bin/python3 tools/bin/s2800-agent write-kg ZPLAY1 4 1 $kg
  ./venv/bin/python3 tools/bin/s2800-agent write-kg VPANO1 0 1 $kg
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
- `tools/bin/s2800-agent` - S2800 protocol spec and live device parameters

### Audio Tools
- `audio-trim <file.wav>` - Analyze and suggest trim points for drum samples
- `audio-viz <file.wav> --open` - Visualize waveform with trim analysis

---

## 🎹 S2800 Agent Tool

The s2800-agent is your primary interface for S2800 protocol work. **Use it instead of writing Python.**

### Common Operations

```bash
# Spec lookup (fast, offline)
tools/bin/s2800-agent param ZPLAY1           # What is ZPLAY1?
tools/bin/s2800-agent list keygroup pan      # Find pan-related params
tools/bin/s2800-agent offset keygroup 53     # What's at byte offset 53?

# Device operations (requires S2800 connected)
tools/bin/s2800-agent programs               # List programs
tools/bin/s2800-agent samples                # List samples
tools/bin/s2800-agent read-kg ZPLAY1 1 0     # Read prog 1, keygroup 0, ZPLAY1
tools/bin/s2800-agent write-kg ZPLAY1 4 1 0  # Write value 4 to ZPLAY1
tools/bin/s2800-agent summary 1              # Full program 1 summary
```

### Example: Configure 12 Keygroups for One-Shot Playback

```bash
# Set all keygroups to play-to-end mode with center pan
for kg in {0..11}; do
  ./venv/bin/python3 tools/bin/s2800-agent write-kg ZPLAY1 4 1 $kg    # Play to end
  ./venv/bin/python3 tools/bin/s2800-agent write-kg VPANO1 0 1 $kg    # Center pan
  ./venv/bin/python3 tools/bin/s2800-agent write-kg CP1 1 1 $kg       # Constant pitch
  echo "Configured keygroup $kg"
done
```

### When to Write Python vs Use Tools

| Task | Use |
|------|-----|
| Upload samples | `tools/bin/s2800 upload` |
| Configure keygroup params | `tools/bin/s2800-agent write-kg` in a loop |
| Read current settings | `tools/bin/s2800-agent read-kg` |
| Look up protocol details | `tools/bin/s2800-agent param` |
| Create new S2800 features | Write Python (then expose as CLI tool) |

---

## 📋 Task Lists for Fault Tolerance

**CRITICAL: Break long operations into tasks. Don't write monolithic scripts.**

### Bad (monolithic):
```python
# One big script that uploads 12 samples
# If it fails at sample 8, you lose all progress
for sample in samples:
    upload_sample(sample)  # 30 seconds each
```

### Good (task-based):
```python
# Create 12 separate tasks
for i, sample in enumerate(samples):
    TaskCreate(
        subject=f"Upload {sample.name}",
        description=f"Upload {sample.path} to S2800",
        activeForm=f"Uploading {sample.name}"
    )
# Then execute tasks one by one
# If task 8 fails, tasks 1-7 are already complete
```

**Benefits:**
- Progress is preserved across failures
- Easy to see what's done vs pending
- Can resume from interruption
- User can see progress in real-time

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

### Pattern 3: Verify Settings
```bash
# After configuring keygroups, spot-check a few
for kg in 0 5 11; do
  ./venv/bin/python3 tools/bin/s2800-agent read-kg ZPLAY1 1 $kg
  ./venv/bin/python3 tools/bin/s2800-agent read-kg VPANO1 1 $kg
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

1. Check available tools: `ls tools/bin/`
2. Read tool help: `tools/bin/s2800-agent help`
3. Look up parameters: `tools/bin/s2800-agent param <name>`
4. Ask the user before writing new Python code
