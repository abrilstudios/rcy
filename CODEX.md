# CODEX.md – A Comprehensive Guide for the Codex Coding Agent in RCy

Table of Contents
-----------------

1. [Introduction](#introduction)
2. [Development Environment Setup](#development-environment-setup)
3. [Working with RCy Code](#working-with-rcy-code)
4. [Common Tasks Guide](#common-tasks-guide)
5. [Troubleshooting & Debugging](#troubleshooting--debugging)
6. [Best Practices for AI-Agent Prompting](#best-practices-for-ai-agent-prompting)
7. [Related Documentation](#related-documentation)

Introduction
------------

What is Codex?

Codex is OpenAI’s coding assistant that helps generate, refactor, and review code. In the context of RCy, you can interact naturally with the codebase, ask for changes, and apply patches via the Codex CLI.

Why use Codex with RCy?

- Speeds up development by automating boilerplate tasks
- Maintains consistency with project standards
- Provides examples and corrections in real time

Development Environment Setup
-----------------------------

Prerequisites

- Python 3.8 or higher
- Git CLI
- `gh` GitHub CLI (optional for issue management)
- `pre-commit` for linting and formatting

Setup Steps

```bash
# Clone the repository
git clone git@github.com:your_org/rcy.git
cd rcy

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export PYTHONPATH=$(pwd)/src/python

# Install pre-commit hooks
pre-commit install
```

Launching and Testing

- Run the main application:
  ```bash
  python -m src.python.main
  ```
- Run the full test suite:
  ```bash
  pytest --maxfail=1 --disable-warnings -q
  ```

Working with RCy Code
----------------------

Project Structure

- `src/python/`: application source code
- `config/`: JSON configuration files
- `tests/`: unit and integration tests

Import Conventions

- Use absolute imports based on `src/python` (no local `sys.path` modifications)

Example: Adding a new audio transform

1. Create a new module under `src/python/audio/`
2. Implement your class and add tests under `tests/`
3. Run tests and ensure coverage
4. Use `apply_patch` to update code:
   ```bash
   # In conversation with Codex:
   apply_patch: {"cmd": ["apply_patch", "
   *** Begin Patch
   *** Update File: src/python/audio_processor.py
   @@ def process_audio(...):
   -    pass
   +    # new transform logic
   *** End Patch
   "] }
   ```

Common Tasks Guide
------------------

Feature Branch Workflow

1. Create a descriptive branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Implement changes and write tests
3. Stage and commit:
   ```bash
   git add .
   git commit -m "feat: add your feature

- Summary of changes
- Reference issue #XYZ
"```
4. Push and open a pull request

Running Specific Hooks

- Run a specific pre-commit hook:
  ```bash
  pre-commit run --hook-type pre-commit --files src/python/rcy_controller.py
  ```

Troubleshooting & Debugging
---------------------------

Pre-commit Failures

- If a hook fails, review the error message
- Auto-fix formatting issues:
  ```bash
  pre-commit run --all-files
  ```

Import Errors

- Verify `PYTHONPATH` includes `src/python`

Session Logs (when enabled)

- If Session Logger is configured (issue #100), review `session_summary.log` for a timeline of actions

Best Practices for AI-Agent Prompting
-------------------------------------

- Be explicit about file paths and functions to modify
- Provide clear examples or snippets for context
- Scope requests narrowly to avoid unintended changes
- Use the patch format when asking Codex to modify code

Example prompt:
```text
Apply a patch to src/python/rcy_controller.py to simplify bounds checking:

apply_patch: {"cmd": ["apply_patch", "
*** Begin Patch
*** Update File: src/python/rcy_controller.py
@@ def adjust_index(...):
-    if index < 0 or index >= len(items):
-        return None
+    if not (0 <= index < len(items)):
+        return None
*** End Patch
"] }
```

Related Documentation
---------------------

- [CLAUDE.md](CLAUDE.md): Guidelines for working with the Claude agent  
- [README.md](README.md): Project overview and basic setup  
