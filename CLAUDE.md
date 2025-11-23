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

## 📝 Issue Management

- When working on issues, always update the issue with your progress
- After resolving an issue, add a detailed comment explaining the solution
- Link to relevant commits in your issue comments
- Update the issue description if needed to reflect the actual problem and solution
- **Important**: You do not get credit for your work if you don't update the issue!

## 🤖 L1/L2 Workflow

RCy uses a tiered approach for AI assistants:

- **Claude (L2)**: Handles complex tasks, system design, and code reviews
- **Claude Jr. (L1)**: Handles simpler, well-defined tasks like documentation updates and routine code changes

### Guidelines for L1/L2 Interaction

- Issues are labeled as `L1` or `L2` based on complexity
- L2 can hand off appropriate subtasks to L1 by creating new issues
- L1 submits work for review using the `review-needed` label
- L2 provides feedback and approval for L1's work
- Final integration and system-wide changes are managed by L2

This workflow allows for efficient division of labor while maintaining quality control.