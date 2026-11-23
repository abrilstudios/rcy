"""A riemann_harness session for a candidate that is a command, not a server.

The generic Session launches one long-running process and waits for an HTTP
readiness answer. A command-line candidate runs once per `run` step instead,
so the adapter here starts nothing and the session's own steps write fixture
files, run the command in the trial's work directory, and read back what it
wrote. All grading still goes through the trace and the five generic matcher
operators.
"""
import json
import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from riemann_harness.session import Session

from harness.observe import compare, identical, observe

REPO = Path(__file__).resolve().parents[1]
WORK_TOKEN = "$WORK"  # stands for the trial work directory in recorded output lines


class _NeverExits:
    """Stands in for the long-running process the generic close() polls."""

    def poll(self):
        return None


class NoServiceAdapter:
    def __init__(self, directory):
        self.process = _NeverExits()
        self.log_path = Path(directory + ".absent-log")

    def start(self):
        pass

    def ready(self):
        return True

    def stop(self):
        pass


def fixture_sample(frame, channel):
    """Deterministic 16-bit sample; distinct across channels and across any two
    equal-length windows whose start frames differ by less than 2001."""
    return ((frame * 7 + channel * 13) % 2001) - 1000


class CommandSession(Session):
    steps = {
        "wav": ({"file", "channels", "rate", "frames", "width", "extensible"},
                {"file", "channels", "rate", "frames"}),
        "identical": ({"first", "second"}, {"first", "second"}),
        "write": ({"file", "text"}, {"file", "text"}),
        "copy": ({"source", "to"}, {"source", "to"}),
        "derive": ({"file", "source", "set"}, {"file", "source", "set"}),
        "run": ({"name", "args", "env"}, {"name", "args"}),
        "observe": ({"dir"}, {"dir"}),
        "compare": ({"file", "source", "start", "end"}, {"file", "source", "start", "end"}),
    }
    profiles = ("spec",)
    interpreter = None  # set from --rcy-interpreter; required, no default
    work_prefix = "rcy-trial-"
    evidence = "files the candidate wrote, read back with stdlib wave/json and the harness MIDI and EXS readers"

    def make_adapter(self, listen, directory):
        self.root = Path(directory).resolve()
        self.runs = []
        return NoServiceAdapter(directory)

    def inside(self, name):
        path = (self.root / name).resolve()
        if self.root != path and self.root not in path.parents:
            raise ValueError("fixture path escapes the work directory: " + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def extra_step(self, step):
        op = step["op"]
        if op == "wav":
            width = step.get("width", 16) // 8
            with wave.open(str(self.inside(step["file"])), "wb") as w:
                w.setnchannels(step["channels"])
                w.setframerate(step["rate"])
                w.setsampwidth(width)
                if width == 2:
                    w.writeframes(b"".join(struct.pack("<h", fixture_sample(i, c))
                                           for i in range(step["frames"]) for c in range(step["channels"])))
                else:
                    w.writeframes(bytes(step["frames"] * step["channels"] * width))
            if step.get("extensible"):
                # Rewrite the header as WAVE_FORMAT_EXTENSIBLE (tag 65534) with the
                # PCM subformat; the sample data is unchanged.
                path = self.inside(step["file"])
                raw = path.read_bytes()
                frames = raw[44:]
                channels, rate = step["channels"], step["rate"]
                fmt = struct.pack("<HHIIHHHHI16s", 0xFFFE, channels, rate, rate * channels * width,
                                  channels * width, width * 8, 22, width * 8, 0,
                                  bytes.fromhex("0100000000001000800000aa00389b71"))
                body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(frames)) + frames
                path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
        elif op == "identical":
            identical(self.trace, self.root, step["first"], step["second"])
        elif op == "write":
            self.inside(step["file"]).write_text(step["text"])
        elif op == "copy":
            source = (REPO / step["source"]).resolve()
            if REPO not in source.parents:
                raise ValueError("copy source must be inside the repository")
            target = self.inside(step["to"])
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target)
        elif op == "derive":
            data = json.loads((self.root / step["source"]).read_text())
            for dotted, value in step["set"].items():
                node, keys = data, dotted.split(".")
                for key in keys[:-1]:
                    node = node[int(key)] if isinstance(node, list) else node[key]
                last = keys[-1]
                if isinstance(node, list):
                    node[int(last)] = value
                else:
                    node[last] = value
            self.inside(step["file"]).write_text(json.dumps(data, indent=2) + "\n")
        elif op == "run":
            self.run(step)
        elif op == "observe":
            observe(self.trace, self.root, step["dir"])
        elif op == "compare":
            compare(self.trace, self.root, step["file"], step["source"], step["start"], step["end"])
        else:
            raise ValueError("unknown step op: " + repr(op))

    def run(self, step):
        # The candidate sees only the variables the scenario names, plus what a
        # process needs to start. Nothing from the operator's shell leaks in.
        # PATH starts with the pinned interpreter's directory, so a candidate whose
        # first line is `#!/usr/bin/env node` runs on that interpreter with no
        # view of the harness's own environment.
        if not self.interpreter:
            raise ValueError("no interpreter given: pass --rcy-interpreter /abs/path/to/node")
        interpreter = Path(self.interpreter)
        if not interpreter.is_absolute() or interpreter.name != "node" or not interpreter.is_file():
            raise ValueError("--rcy-interpreter must be an absolute path to a file named node")
        env = {"PATH": f"{interpreter.parent}:/usr/bin:/bin", "HOME": str(self.root)}
        env.update(step.get("env", {}))
        result = subprocess.run(self.command + step["args"], cwd=self.root, env=env,
                                capture_output=True, timeout=max(1, self.remaining(60)))
        streams = {}
        for stream, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
            text = raw.decode(errors="replace")
            for real in sorted({str(self.root), self.work.name}, key=len, reverse=True):
                text = text.replace(real, WORK_TOKEN)
            streams[stream] = text.splitlines()
        self.runs.append((step, result.returncode, streams))
        self.trace.record("process_exit", name=step["name"], code=result.returncode,
                          stdout_lines=len(streams["stdout"]), stderr_lines=len(streams["stderr"]))
        for stream, lines in streams.items():
            for index, text in enumerate(lines, start=1):
                self.trace.record("output_line", name=step["name"], stream=stream, index=index, text=text)

    def after_stop(self):
        parts = []
        for step, code, streams in getattr(self, "runs", []):
            parts.append(f"$ {json.dumps(step['args'])}  -> exit {code}")
            parts += ["  out| " + line for line in streams["stdout"]]
            parts += ["  err| " + line for line in streams["stderr"]]
        self.log = "\n".join(parts) + "\n"


class UnboundCommandSession(CommandSession):
    """Runs a candidate that has no build manifest, such as the reference
    implementation. The profile name lands in every report."""
    profiles = ("unbound", "spec")
    evidence = CommandSession.evidence + "; artifact not bound to a spec by a build manifest"
