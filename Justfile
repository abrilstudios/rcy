# rcy commands. Install just with `brew install just`.

default:
    @just --list

# Cut a kit from this repository's preset catalog or any WAV:
# just export --preset amen_classic --out /tmp/amen --exs --buffer-ms 20
export *ARGS:
    RCY_PRESETS="{{justfile_directory()}}/presets" node export/rcy-export {{ARGS}}

# Open the slicing window: just window --manifest KIT.rcy.json --record RUN.json --out OUT.rcy.json
window *ARGS:
    tools/window-runtime/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron window/rcy-window {{ARGS}}

# Play a kit's MIDI file against its slices, to check it by ear: just player KIT_DIR [LOOPS] [BPM] [--out FILE.wav]
player *ARGS:
    node player/rcy-player {{ARGS}}

# Install Electron and Playwright for the window and its scenarios
setup-window:
    npm ci --prefix tools/window-runtime

# Rebuild the SDK and both programs after editing rcy-sdk/src, export/main.js or window/main.js
build:
    node rcy-sdk/bin/build.cjs
    node rcy-sdk/dist/bundle.cjs export/main.js export/rcy-export
    node rcy-sdk/dist/bundle.cjs window/main.js window/rcy-window

# SDK tests and the window scenarios (the scenarios open real windows)
test:
    cd rcy-sdk && node --test "test/*.test.ts"
    NODE_PATH=tools/window-runtime/node_modules node features/window/scenarios.js \
        "$PWD/tools/window-runtime/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron" \
        "$PWD/window/rcy-window" "$PWD/export/rcy-export" "$PWD/presets/amen.wav"

# S2800 SysEx protocol tool (spec lookup, device read/write)
s2800-agent *ARGS:
    uv run --project hardware rcy-s2800-agent {{ARGS}}

# S2800 sample upload/list/delete over MIDI
s2800 *ARGS:
    uv run --project hardware rcy-s2800 {{ARGS}}

# MPC2000XL sample upload via MIDI SDS (requires SHIFT+MIDI/SYNC > DUMP [F2] on the MPC)
mpc *ARGS:
    uv run --project hardware rcy-mpc {{ARGS}}

# Start the ADK agent server (needs the agent extra and credentials in hardware/src/python/s2800/agent/.env)
agent-start PORT="8000":
    cd hardware && uv run adk api_server \
        --session_service_uri "sqlite:///.agent-sessions.db" \
        --auto_create_session --port {{PORT}} \
        src/python/s2800

# Stop the ADK agent server
agent-stop:
    pkill -f "adk api_server" && echo "Stopped." || echo "Not running."

# TR-909 style web controller for an S2800 program (standalone HTML, no server)
controller PROG="3" LOOK="default":
    open -a "Google Chrome" "file://{{justfile_directory()}}/hardware/tools/bin/909-controller.html?program={{PROG}}&look={{LOOK}}"
