# 🧭 RCY Coding Standards & Session Initialization Guidance

This document outlines best practices and session setup expectations for contributing to the RCY codebase. It is primarily written for Claude (and other code agents) to follow during development, review, and refactoring tasks. It can also be used by human contributors to ensure consistency and clarity in the codebase.

---

## 🚨 **HOW TO RUN THE APPLICATION**

**IMPORTANT: When asked to "run the app", ALWAYS use this exact command:**

```bash
just run
```

**That's it. Just use `just run`. Do not overthink it.**

**DO NOT:**
- Use `python3 -m main`
- Use system Python
- Use full paths to venv/bin/python
- Try to manually set PYTHONPATH
- Try to activate the virtual environment

**The Justfile handles everything. Just use `just run`.**

---

## 🔧 **Environment Information Tool**

For detailed environment information, run:

```bash
./tools/bin/env
```

This script provides:
- Python environment details
- How to run Python/pytest with the venv
- OS information
- Git status
- Installed dependencies

**Key Commands:**
- `just run` - Run the TUI application
- `just test` - Run all tests
- `just test-file <file>` - Run a specific test file
- `just setup` - Set up/reinstall the virtual environment

---

## 📦 Project Structure

RCY uses a modular directory layout with absolute imports and explicit runtime configuration.

- All source code lives under: `src/python/`
- All configuration lives under: `config/`
- Tests are under: `tests/`
- RCY expects `PYTHONPATH` to be set to the `src` directory when running any scripts or applications.

---

## ✅ Import Hygiene

- All `import` statements must appear at the **top of the file**, not inside functions or conditional blocks.
- **Do not modify `sys.path`** dynamically inside application files.
- Assume the developer has set `PYTHONPATH=rcy/src` (or equivalent) before running any scripts. Use absolute imports based on this setup.
- Do not add fallback import paths or multi-level resolution logic.
- Example of correct imports:
  ```python
  from config_manager import config
  from audio_processor import WavAudioProcessor
  ```

## 🛑 Error Handling

- **Never use `hasattr()` to condition on a method existing**
- Always explicitly call the function
- This makes code failures explicit rather than silently degrading
- It's better for the application to fail with a clear error than to silently skip functionality

---

## 🔄 Configuration Management

- Configuration files are stored in the `config/` directory in JSON format
- Use the `config_manager.py` module to access configuration values
- Avoid hardcoding configuration values in the application code
- Provide sensible defaults for all configuration parameters

---

## 🧪 Testing Practices

- All tests should be placed in the `tests/` directory
- When writing tests, ensure PYTHONPATH is correctly set to include the src directory
- Mock external dependencies when appropriate
- Include tests for new features and bug fixes
- Run tests before submitting pull requests

---

## 🚀 Development Workflow

- **Never do work directly on the main branch unless specifically requested to do so**
- Create feature branches from main for new work
- Use descriptive branch names with prefixes like `feature/`, `fix/`, `enhancement/`, etc.
- **CRITICAL: Never stage or commit code without explicit permission or successful tests**
  - Do not use `git add` or `git commit` before either:
    1. Running and validating that all relevant tests pass successfully, OR
    2. Receiving explicit confirmation from the developer that it's OK to commit
  - This prevents committing broken code and ensures the repository stays in a working state
  - Always prioritize testing and verification over committing changes
- Follow the git commit message conventions
- Use pull requests for code review
- Ensure tests pass before merging
- Update documentation when changing functionality

## S2800/S3000/S3200 SysEx Protocol Reference

When working on S2800/S3000/S3200 SysEx code, use `tools/bin/s2800-agent` to look up protocol details. This tool queries the complete specification and gives exact parameter offsets, sizes, ranges, and model differences. **Always use this instead of guessing protocol values.**

```bash
# Look up a parameter by name
tools/bin/s2800-agent param FILFRQ
tools/bin/s2800-agent param FILFRQ keygroup

# Reverse lookup: what parameter is at this byte offset?
tools/bin/s2800-agent offset keygroup 34

# List all parameters in a header (program, keygroup, or sample)
tools/bin/s2800-agent list program
tools/bin/s2800-agent list keygroup filter

# Build a SysEx message
tools/bin/s2800-agent build 0x27 0 0 0 3 12

# Decode a raw SysEx hex string
tools/bin/s2800-agent decode "F0 47 00 27 48 00 00 00 03 00 0C 00 F7"

# Compare model differences (S2800 vs S3000 vs S3200)
tools/bin/s2800-agent models
tools/bin/s2800-agent models OUTPUT

# Live device (requires S2800 connected via MIDI):
tools/bin/s2800-agent programs              # List programs on device
tools/bin/s2800-agent samples               # List samples on device
tools/bin/s2800-agent read POLYPH           # Read current polyphony from program 0
tools/bin/s2800-agent read LEGATO 0         # Read legato setting from program 0
tools/bin/s2800-agent read-kg FILFRQ 0 0    # Read filter freq from keygroup 0
tools/bin/s2800-agent summary               # Full summary of program 0 settings
```

The structured spec data lives in `src/python/s2800/agent/spec.py`. The tool functions are in `src/python/s2800/agent/tools.py`. The live device tools use the `S2800` class from `src/python/s2800/sampler.py` (read-only).

---

## 📝 Issue Management

- When working on issues, always update the issue with your progress
- After resolving an issue, add a detailed comment explaining the solution
- Link to relevant commits in your issue comments
- Update the issue description if needed to reflect the actual problem and solution
- **Important**: You do not get credit for your work if you don't update the issue!

