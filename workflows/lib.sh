# Shared by the workflow scripts in this directory; sourced, not run.
# Each workflow is one agent-launched task: the script states everything on
# the window's command line, a person places cuts and saves, and the script
# acts on the window's exit code.

set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
RCY_EXPORT="$ROOT/export/rcy-export"
RCY_WINDOW="$ROOT/window/rcy-window"

# Parameter: milliseconds of source audio kept either side of each slice in
# its file. Default 20: a cut placed a few milliseconds into a hit keeps its
# attack, and the start point stays adjustable in the sampler. The value comes
# from one amen kit cut by ear, not from a comparison of values.
BUFFER_MS=${RCY_BUFFER_MS:-20}

# The Electron binary. RCY_ELECTRON names another one; the default is where
# `npm ci --prefix tools/window-runtime` puts it on macOS.
ELECTRON=${RCY_ELECTRON:-$ROOT/tools/window-runtime/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron}

die() { echo "$(basename "$0"): $*" >&2; exit 2; }

require_tools() {
  command -v node >/dev/null || die "node is not on PATH"
  [ -x "$ELECTRON" ] || die "no Electron binary at $ELECTRON; run: npm ci --prefix tools/window-runtime"
}

# new_task_dir DIR: the task directory must not exist, so one task never
# overwrites another's run record.
new_task_dir() {
  [ ! -e "$1" ] || die "$1 already exists; name a new task directory"
  mkdir -p "$1"
}

# edit_then_cut MANIFEST DIR [window options...]
# Opens the window on MANIFEST. On Save (exit 0) cuts the kit from the saved
# manifest into DIR/<name of DIR>. On any other exit code writes no kit and
# exits with that code. DIR/run.json is written in every case.
edit_then_cut() {
  manifest=$1; dir=$2; shift 2
  kit="$dir/$(basename "$dir")"
  set +e
  "$ELECTRON" "$RCY_WINDOW" --manifest "$manifest" \
      --out "$dir/edited.rcy.json" --record "$dir/run.json" "$@"
  code=$?
  set -e
  case $code in
    0) node "$RCY_EXPORT" --from-manifest "$dir/edited.rcy.json" --out "$kit" --exs --buffer-ms "$BUFFER_MS"
       echo "kit: $kit"
       echo "run record: $dir/run.json" ;;
    3) echo "$(basename "$0"): closed without saving; no kit written. Run record: $dir/run.json" >&2
       exit 3 ;;
    *) echo "$(basename "$0"): the window exited with code $code; no kit written" >&2
       exit "$code" ;;
  esac
}
