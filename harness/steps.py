"""Step wordings for a command-line candidate. Assertions come from riemann_harness.steps.

Given and When steps append one plan entry each, which the session executes at
once. Nothing here names a slice, a tempo or a kit.
"""
import json
import time
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from harness.session import CommandSession, UnboundCommandSession


def pytest_addoption(parser):
    parser.getgroup("rcy").addoption(
        "--rcy-unbound", action="store_true",
        help="Run a candidate that has no build manifest; every report records the waiver")
    parser.getgroup("rcy").addoption(
        "--rcy-interpreter", help="Absolute path to the node a `#!/usr/bin/env node` candidate runs on")


def pytest_configure(config):
    config._rcy_started = time.time()


@pytest.fixture
def harness_session_class(request):
    cls = UnboundCommandSession if request.config.getoption("--rcy-unbound") else CommandSession
    cls.interpreter = request.config.getoption("--rcy-interpreter")
    return cls


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if not config.getoption("--harness-command"):
        return
    out = Path(config.getoption("--harness-out")).resolve()
    reports = []
    for path in sorted(out.glob("*/report.json")):
        if path.stat().st_mtime < config._rcy_started:
            continue
        r = json.loads(path.read_text())
        reports.append({"scenario": r.get("scenario_name", r["scenario"]), "category": r["category"],
                        "assertions_passed": r["assertions_passed"], "assertions_total": r["assertions_total"],
                        "error": r.get("error"), "report_dir": str(path.parent)})
    if not reports:
        return
    green = sum(1 for r in reports if r["category"] == "GREEN")
    (out / "summary.json").write_text(json.dumps({
        "command": json.loads(config.getoption("--harness-command")),
        "unbound": config.getoption("--rcy-unbound"),
        "interpreter": config.getoption("--rcy-interpreter"),
        "total": len(reports), "green": green, "scenarios": reports}, indent=2) + "\n")


# ---- fixtures ----------------------------------------------------------------

@given(parsers.parse('a {channels:d}-channel {rate:d} Hz {width:d}-bit WAV "{file}" of {frames:d} frames'))
def wav(arena, channels, rate, width, file, frames):
    arena.action({"op": "wav", "file": file, "channels": channels, "rate": rate,
                  "width": width, "frames": frames})


@given(parsers.parse('a {channels:d}-channel {rate:d} Hz {width:d}-bit extensible-format WAV "{file}" of {frames:d} frames'))
def wav_extensible(arena, channels, rate, width, file, frames):
    arena.action({"op": "wav", "file": file, "channels": channels, "rate": rate,
                  "width": width, "frames": frames, "extensible": True})


@given(parsers.parse('a file "{file}" containing:'))
def write(arena, file, docstring):
    arena.action({"op": "write", "file": file, "text": docstring})


@given(parsers.parse('a copy of the repository\'s "{source}" at "{to}"'))
def copy(arena, source, to):
    arena.action({"op": "copy", "source": source, "to": to})


@when(parsers.parse('the client derives "{file}" from "{source}" setting {dotted} to {value}'))
def derive_one(arena, file, source, dotted, value):
    arena.action({"op": "derive", "file": file, "source": source, "set": {dotted: json.loads(value)}})


@when(parsers.parse('the client derives "{file}" from "{source}" with:'))
def derive(arena, file, source, docstring):
    arena.action({"op": "derive", "file": file, "source": source, "set": json.loads(docstring)})


# ---- running and reading back --------------------------------------------------

@when(parsers.parse('the client runs the command as "{name}" with arguments:'))
def run(arena, name, docstring):
    arena.action({"op": "run", "name": name, "args": json.loads(docstring)})


@when(parsers.parse('the client runs the command as "{name}" with the arguments {args}'))
def run_inline(arena, name, args):
    arena.action({"op": "run", "name": name, "args": json.loads(args)})


@when(parsers.parse('the client runs the command as "{name}" with environment {env} and arguments:'))
def run_env(arena, name, env, docstring):
    arena.action({"op": "run", "name": name, "args": json.loads(docstring), "env": json.loads(env)})


@when(parsers.parse('the observer reads the directory "{directory}"'))
def read(arena, directory):
    arena.action({"op": "observe", "dir": directory})


@when(parsers.parse('the observer compares "{file}" with frames {start:d} to {end:d} of "{source}"'))
def frames(arena, file, start, end, source):
    arena.action({"op": "compare", "file": file, "source": source, "start": start, "end": end})


@when(parsers.parse('the observer compares the bytes of "{first}" and "{second}"'))
def same_bytes(arena, first, second):
    arena.action({"op": "identical", "first": first, "second": second})


# ---- shorthand for one recurring pair of trace assertions ----------------------

@then(parsers.parse('the recorded trace shows run "{name}" exited {code:d} with the single stderr line "{text}"'))
def single_error(arena, name, code, text):
    arena.assertion("contains", [
        {"event": "process_exit", "name": name, "code": code, "stdout_lines": 0, "stderr_lines": 1},
        {"event": "output_line", "name": name, "stream": "stderr", "index": 1, "text": text}])
