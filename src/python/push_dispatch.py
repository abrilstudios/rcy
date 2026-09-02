"""rcy-push: hand a kit manifest to a device plugin found on PATH.

A plugin is an executable named ``rcy-push-<device>`` that accepts
``--manifest KIT.rcy.json`` plus its own flags, reads the slice WAVs beside
the manifest, prints one JSON object on stdout and exits non-zero on failure.
Core ships with no plugins; this module only locates one and runs it.
"""

import argparse
import shutil
import subprocess
import sys

PLUGIN_REPOS = ("abrilstudios/rcy-akai", "abrilstudios/rcy-teenage-engineering")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rcy-push",
        description="Run the rcy-push-<device> plugin for DEVICE with a kit manifest.",
        allow_abbrev=False,
    )
    parser.add_argument("device", help="plugin name, e.g. ep133, s2800, mpc")
    parser.add_argument("--manifest", required=True, help="kit manifest (KIT.rcy.json)")
    args, passthrough = parser.parse_known_args(argv)

    executable = f"rcy-push-{args.device}"
    path = shutil.which(executable)
    if path is None:
        print(
            f"rcy-push: no plugin for '{args.device}': {executable} is not on PATH. "
            f"Plugins are installed separately; known ones: {', '.join(PLUGIN_REPOS)}.",
            file=sys.stderr,
        )
        return 2

    result = subprocess.run([path, "--manifest", args.manifest, *passthrough], check=False)  # noqa: S603
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
