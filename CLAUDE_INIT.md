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

- Create feature branches from main for new work
- Follow the git commit message conventions
- Use pull requests for code review
- Ensure tests pass before merging
- Update documentation when changing functionality