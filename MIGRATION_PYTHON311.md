# Python 3.11+ Migration Guide

## Overview

This document describes the modernization of RCY's Python development environment from Python 3.8+ to Python 3.11+.

## What Changed

### 1. Requirements Files

**requirements.txt**
- Updated to Python 3.11+ compatible versions
- Removed Python 3.8-specific version constraints
- Added clear categorization of dependencies
- Restored `numba` and `llvmlite` (previously removed for Python 3.13 compatibility)
- All dependencies now use `>=` constraints for flexibility while maintaining stability

**requirements-dev.txt** (NEW)
- Moved development dependencies to separate file
- Added modern tooling: `ruff`, `mypy`, `pre-commit`
- Includes type stubs for external libraries
- Separated from production dependencies for cleaner deployment

**requirements-py313.txt** (REMOVED)
- No longer needed with unified Python 3.11+ approach
- All dependencies now compatible with Python 3.11-3.14+

### 2. Build Configuration

**pyproject.toml** (NEW)
- Modern Python project configuration standard (PEP 518, PEP 621)
- Replaces setup.py for project metadata
- Centralizes all tool configurations in one file
- Includes:
  - Project metadata and dependencies
  - Ruff configuration (linting and formatting)
  - Mypy configuration (type checking)
  - Pytest configuration (testing)
  - Coverage configuration

### 3. Code Quality Tools

**Ruff** (replaces Flake8, Black, isort, pyupgrade)
- Extremely fast linter and formatter written in Rust
- All-in-one replacement for multiple tools
- Configured with strict rules for code quality
- Line length: 100 characters
- Enabled rule sets: E, F, I, N, UP, ANN, S, B, A, C4, DTZ, T20, RUF

**Mypy** (type checking)
- Strict type checking enabled
- Helps catch bugs at development time
- Configured to ignore missing imports for third-party libraries without stubs
- Does not check test files (less strict for tests)

**Pre-commit** (git hooks)
- Automatically runs checks before commits
- Catches issues early in development
- Includes: ruff format, ruff lint, mypy, trailing whitespace, file cleanup
- Security checks with Bandit

### 4. Continuous Integration

**.github/workflows/ci.yml** (NEW)
- Three parallel jobs: lint, typecheck, test
- Matrix testing across Python 3.11 and 3.12
- Multi-OS support: Ubuntu, macOS, Windows
- Coverage reporting and artifact uploads
- Codecov integration for coverage tracking

## Setup Instructions

### For New Contributors

```bash
# Clone the repository
git clone https://github.com/tnn1t1s/rcy.git
cd rcy

# Create and activate virtual environment (recommended)
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
PYTHONPATH=src pytest
```

### For Existing Contributors

```bash
# Update your Python version to 3.11 or higher
python3 --version  # Should be 3.11+

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run pre-commit on all files (optional, to see what would change)
pre-commit run --all-files
```

## Development Workflow

### Running Linter

```bash
# Check code
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Running Type Checker

```bash
# Check types
mypy src/python
```

### Running Tests

```bash
# Run all tests
PYTHONPATH=src pytest

# Run with coverage
PYTHONPATH=src pytest --cov=src/python --cov-report=term-missing

# Run specific test file
PYTHONPATH=src pytest tests/test_specific.py
```

### Pre-commit Hooks

```bash
# Run all hooks on staged files
pre-commit run

# Run all hooks on all files
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate
```

## Compatibility Notes

### Python Version Support

- **Minimum:** Python 3.11
- **Recommended:** Python 3.11 or 3.12
- **Tested:** Python 3.11, 3.12, 3.14 (on maintainer's machine)

### Breaking Changes

**None for existing code.** This migration only updates the development environment and build system. All application code remains compatible.

### Type Hints Modernization (Future Work)

Several files use old-style type hints that could be modernized:
- `Dict[str, Any]` → `dict[str, Any]` (Python 3.9+ syntax)
- `List[int]` → `list[int]` (Python 3.9+ syntax)
- `Optional[str]` → `str | None` (Python 3.10+ syntax)
- `Union[str, int]` → `str | int` (Python 3.10+ syntax)

Files to consider updating:
- `src/python/high_performance_audio.py`
- `src/python/utils/sfz/generate_sfz.py`
- `src/python/utils/midi_analyzer.py`
- `src/python/utils/audio_preview.py`
- `src/python/segment_manager.py`
- `src/python/config_manager.py`

**Note:** These updates are optional and can be done incrementally. The old syntax still works in Python 3.11+.

## Configuration Reference

### Ruff Rules

- **E**: pycodestyle errors
- **F**: pyflakes
- **I**: isort (import sorting)
- **N**: pep8-naming
- **UP**: pyupgrade (modern Python syntax)
- **ANN**: flake8-annotations (type hints)
- **S**: flake8-bandit (security)
- **B**: flake8-bugbear (common bugs)
- **A**: flake8-builtins (shadowing builtins)
- **C4**: flake8-comprehensions (list/dict comprehensions)
- **DTZ**: flake8-datetimez (datetime usage)
- **T20**: flake8-print (print statements)
- **RUF**: Ruff-specific rules

### Ignored Rules

- **ANN101**: Missing type annotation for `self` (not needed)
- **ANN102**: Missing type annotation for `cls` (not needed)
- **ANN401**: Dynamically typed expressions (Any) allowed
- **S101**: Assert statements allowed (required for pytest)
- **T201**: Print statements allowed (for now)

## Troubleshooting

### Pre-commit fails with "command not found"

```bash
# Ensure tools are installed
pip install -r requirements-dev.txt

# Reinstall hooks
pre-commit clean
pre-commit install
```

### Mypy reports "Library stubs not installed"

```bash
# Install type stubs
pip install types-requests types-python-dateutil
```

### Tests can't find modules

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=src  # Linux/macOS
set PYTHONPATH=src     # Windows cmd
$env:PYTHONPATH="src"  # Windows PowerShell
```

### Ruff and Mypy have conflicting opinions

- Ruff is configured to be permissive in some areas where Mypy is strict
- If conflicts arise, Mypy takes precedence for type safety
- Use `# type: ignore` or `# noqa` sparingly and with comments explaining why

## Resources

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Mypy Documentation](https://mypy.readthedocs.io/)
- [Pre-commit Documentation](https://pre-commit.com/)
- [Pytest Documentation](https://docs.pytest.org/)
- [PEP 621 - Project Metadata](https://peps.python.org/pep-0621/)

## Questions?

For questions or issues with the migration, please open an issue on GitHub.
