"""What the generator receives: the contract identifier, the pinned inputs and the prompt.

Nothing from features/, harness/ or reports/ is ever listed here.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "rcy-export/spec-v1"
ARTIFACT = "rcy-export"
# The SDK's interface document and built file. Its source, tests and layout
# notes aren't generator inputs.
SDK_BUILD = "rcy-sdk/dist/rcy-sdk.js"
INPUTS = ["SPEC.md", "INVARIANTS.md", "rcy-sdk/README.md", SDK_BUILD, "rcy-sdk/dist/bundle.cjs"]
PROMPT = ROOT / "bin/prompt.md"
# Paths in this repository the generating agent is denied read access to.
WITHHELD = ["features", "harness", "reports", "rcy-sdk", "BASELINE.md", "DEFERRED.md", "VALIDATION.md", "README.md", ".git"]


def arguments():
    args = ["--contract", CONTRACT, "--root", str(ROOT), "--prompt", str(PROMPT),
            "--spec", "SPEC.md", "--artifact", ARTIFACT]
    for name in INPUTS:
        args += ["--input", name]
    return args
