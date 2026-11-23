"""What the generator of rcy-window receives.

Nothing from features/, harness/ or reports/ is ever listed here.
"""
from harness.inputs import ROOT, SDK_BUILD, WITHHELD  # noqa: F401

CONTRACT = "rcy-window/spec-v1"
ARTIFACT = "rcy-window"
SPEC = "WINDOW.md"
INPUTS = [SPEC, "rcy-sdk/README.md", SDK_BUILD, "rcy-sdk/dist/bundle.cjs"]
PROMPT = ROOT / "bin/window-prompt.md"
# Electron and playwright-core, installed by `npm ci` in this directory. The
# agent runs them from here; they are tools, not inputs, so they aren't pinned
# into the input directory.
RUNTIME = ROOT / "tools/window-runtime"


def arguments():
    args = ["--contract", CONTRACT, "--root", str(ROOT), "--prompt", str(PROMPT),
            "--spec", SPEC, "--artifact", ARTIFACT]
    for name in INPUTS:
        args += ["--input", name]
    return args
