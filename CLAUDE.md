# 🧭 RCY Coding Standards & Session Initialization Guidance

This document outlines best practices and session setup expectations for contributing to the RCY codebase. It is primarily written for Claude (and other code agents) to follow during development, review, and refactoring tasks. It can also be used by human contributors to ensure consistency and clarity in the codebase.

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