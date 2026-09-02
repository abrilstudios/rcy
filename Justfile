# RCY Project Commands
# Usage: just <command>
# Install just: brew install just
# Install uv:   brew install uv   (or https://docs.astral.sh/uv/)

# Default recipe - show available commands
default:
    @just --list

# Install the project, all extras and dev tools into .venv
setup:
    uv sync --all-extras

# Install runtime dependencies only (no llm/viz extras)
install:
    uv sync --no-dev

# Report python, uv, presets and audio output
doctor:
    uv run python -m utils.doctor

# Headless end-to-end check: slice a bundled break, write WAV slices + SFZ + MIDI + manifest
smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    out="$(mktemp -d)/apache"
    uv run rcy-export --preset apache_break --out "$out"
    for f in 001.wav 008.wav apache.sfz apache.mid apache.rcy.json; do
        test -s "$out/$f" || { echo "smoke: missing $out/$f"; exit 1; }
    done
    uv run python -c "from kit_manifest import load_kit; m, a = load_kit('$out/apache.rcy.json'); print('smoke: manifest ok,', len(m.slices), 'slices from', a.path)"
    echo "smoke: ok ($out)"
    rm -rf "$(dirname "$out")"

# Run the RCY application (TUI) - pass any args (e.g., just run --skin ocean)
run *ARGS:
    uv run rcy {{ARGS}}

# Alias for run (TUI)
tui *ARGS:
    uv run rcy {{ARGS}}

# Run the TUI with a specific preset
tui-preset PRESET:
    uv run rcy --preset {{PRESET}}

# Slice a preset or WAV headlessly: just export --preset apache_break --out /tmp/apache
export *ARGS:
    uv run rcy-export {{ARGS}}

# Hand a kit manifest to an installed device plugin: just push ep133 --manifest out/apache/apache.rcy.json
push *ARGS:
    uv run rcy-push {{ARGS}}

# Run all tests
test:
    uv run pytest

# Run tests with coverage report
test-cov:
    uv run pytest --cov=src/python --cov-report=term-missing --cov-report=html

# Run specific test file
test-file FILE:
    uv run pytest {{FILE}}

# Run linter (ruff check)
lint:
    uv run ruff check .

# Fix linting issues automatically
lint-fix:
    uv run ruff check --fix .

# Format code with ruff
format:
    uv run ruff format .

# Run type checker (mypy)
typecheck:
    uv run mypy src/python

# Run all code quality checks (lint + typecheck)
check: lint typecheck

# Clean up build artifacts and cache
clean:
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info/ src/python/*.egg-info/
    rm -rf .pytest_cache/
    rm -rf .mypy_cache/
    rm -rf .ruff_cache/
    rm -rf htmlcov/
    rm -rf .coverage coverage.xml
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Clean everything including the virtualenv
clean-all: clean
    rm -rf .venv/

# Build wheel and sdist into dist/
build:
    uv build

# Show project info
info:
    @echo "RCY - Breakbeat Loop Slicer"
    @echo "Python: $(uv run python --version 2>/dev/null || echo 'not installed (run: just setup)')"
    @echo "Git branch: $(git branch --show-current)"
    @echo "Git status: $(git status --short | wc -l | xargs echo) files changed"
