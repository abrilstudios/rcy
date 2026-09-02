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

# Install runtime dependencies only (no hardware/agent/llm/viz extras)
install:
    uv sync --no-dev

# Report python, uv, presets, audio output and MIDI hardware
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

# Run all tests (hardware-marked tests are deselected by default)
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

# S2800 SysEx protocol tool (spec lookup, device read/write, presets)
s2800-agent *ARGS:
    uv run rcy-s2800-agent {{ARGS}}

# S2800 sample upload/list/delete over MIDI
s2800 *ARGS:
    uv run rcy-s2800 {{ARGS}}

# MPC2000XL sample upload via MIDI SDS (requires SHIFT+MIDI/SYNC > DUMP [F2] on MPC)
mpc *ARGS:
    uv run rcy-mpc {{ARGS}}

# Start the ADK agent server (needs the agent extra and OPENROUTER/Google credentials in .env)
agent-start PORT="8000":
    uv run adk api_server \
        --session_service_uri "sqlite:///.agent-sessions.db" \
        --auto_create_session --port {{PORT}} \
        src/python/s2800

# Stop the ADK agent server
agent-stop:
    pkill -f "adk api_server" && echo "Stopped." || echo "Not running."

# Send a query to a running ADK agent
ask AGENT QUERY SESSION="default":
    tools/bin/agent-ask {{AGENT}} {{QUERY}} {{SESSION}}

# Launch TR-909 style web controller for an S2800 program (standalone HTML, no server)
# LOOK options: default, neworder, kaws, zooyork, basquiat, supreme, futura, stash, obey, barneys, moma
controller PROG="3" LOOK="default":
    open -a "Google Chrome" "file://{{justfile_directory()}}/tools/bin/909-controller.html?program={{PROG}}&look={{LOOK}}"

# Show project info
info:
    @echo "RCY - Breakbeat Loop Slicer"
    @echo "Python: $(uv run python --version 2>/dev/null || echo 'not installed (run: just setup)')"
    @echo "Git branch: $(git branch --show-current)"
    @echo "Git status: $(git status --short | wc -l | xargs echo) files changed"
