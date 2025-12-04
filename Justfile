# RCY Project Commands
# Usage: just <command>
# Install just: brew install just

# Default recipe - show available commands
default:
    @just --list

# Set up Python virtual environment and install dependencies
setup:
    python3.11 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
    ./venv/bin/pip install -r requirements-dev.txt
    ./venv/bin/pre-commit install

# Install production dependencies only
install:
    ./venv/bin/pip install -r requirements.txt

# Install development dependencies
install-dev:
    ./venv/bin/pip install -r requirements-dev.txt

# Run the RCY application (TUI)
run:
    PYTHONPATH=src/python ./venv/bin/python -m tui.app

# Alias for run (TUI)
tui:
    PYTHONPATH=src/python ./venv/bin/python -m tui.app

# Run the TUI with a specific preset
tui-preset PRESET:
    PYTHONPATH=src/python ./venv/bin/python -m tui.app --preset {{PRESET}}


# Run all tests with coverage
test:
    PYTHONPATH=src/python ./venv/bin/pytest

# Run tests with coverage report
test-cov:
    PYTHONPATH=src/python ./venv/bin/pytest --cov=src/python --cov-report=term-missing --cov-report=html

# Run specific test file
test-file FILE:
    PYTHONPATH=src/python ./venv/bin/pytest {{FILE}}

# Run linter (ruff check)
lint:
    ./venv/bin/ruff check .

# Fix linting issues automatically
lint-fix:
    ./venv/bin/ruff check --fix .

# Format code with ruff
format:
    ./venv/bin/ruff format .

# Run type checker (mypy)
typecheck:
    ./venv/bin/mypy src/python

# Run all code quality checks (lint + typecheck)
check: lint typecheck

# Run pre-commit hooks on all files
pre-commit:
    ./venv/bin/pre-commit run --all-files

# Clean up build artifacts and cache
clean:
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info/
    rm -rf .pytest_cache/
    rm -rf .mypy_cache/
    rm -rf .ruff_cache/
    rm -rf htmlcov/
    rm -rf .coverage
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Clean everything including venv
clean-all: clean
    rm -rf venv/

# Build package
build:
    ./venv/bin/python -m build

# Show project info
info:
    @echo "RCY - Breakbeat Loop Slicer"
    @echo "Python version: $(python3.11 --version)"
    @echo "Virtual env: $(if [ -d venv ]; then echo 'exists'; else echo 'not found (run: just setup)'; fi)"
    @echo "Git branch: $(git branch --show-current)"
    @echo "Git status: $(git status --short | wc -l | xargs echo) files changed"
