# rcy behaviours recorded in pull requests, docs and commit history

Research date 2026-11-21. Repository `abrilstudios/rcy`, a local clone, branch `main` at 9263d92.

## 1. Sources and coverage

- Pull requests: all 64 (61 merged, #145 closed unmerged, #189 and #190 open). Titles, bodies and comments were read from raw JSON saved under `/private/tmp/rcy-prs/`. Nine bodies are empty (#15, #64, #72, #78, #95, #109, #114, #153, #162); for those the evidence is the branch commit message. Two API endpoints (per-PR `reviews` and the repo-wide review-comments list) both returned zero reviews and zero inline comments. Only #106, #111 and #134 carry issue comments, all written by the PR author.
- Docs: the 47 `*.md` files outside `.venv`, `node_modules` and `ep133-poc/` (repo root, `docs/`, `src/python/`, `presets/`, `sample-packs/`, `tests/`, `tools/bin/`), plus `config/config.json`, `config/presets/core.json`, `config/presets/rhythm-lab.json` and `config/skins/*.json`.
- Read in part or keyword-searched only (patterns: latency, ms, fade, click, pop, timeout, retry): `tests/TESTING.md`, `docs/menu_bar_integration.md`, `docs/l1_l2_workflow.md`, `src/python/s2800/agent/README.md`, `docs/issues/issue_93_gui_testing.md`, `docs/issues/issue_92_downsampling_tests.md`, `docs/issues/issue_doc.md`, `docs/INDEX.md`, `tools/bin/README.md`, `docs/github_setup.md`, `docs/pat_instructions.md`, and the phase-3 and phase-4 refactoring docs. `docs/drum_and_bass_sample_techniques.md` was read and is genre history with no tool behaviour. `docs/REORGANIZATION_NOTES.md` says an `ARCHITECTURE.md` was created at the root; no such file exists on main.
- The `designs/` directory no longer exists. Commit 355dde4 (2025-11-23) deleted it; those docs were read with `git show 355dde4^:<path>` and are marked "deleted doc" below. They record intent at the time, and several are contradicted by later commits.
- Commit history: `git log --format='%h %ad %s' --date=short` (354 commits, 2024-10-05 to 2026-09-02), with bodies read for about 60 commits.
- Python source: docstrings and named constants only, in `ring_buffer_audio.py`, `audio_processor.py`, `segment_manager.py`, `timestretch.py`, `audio_utils.py`. Four facts in section 3 came from function bodies in those files and are labelled.
- Excluded: `.venv`, `node_modules`, and `ep133-poc/` (untracked, a separate MCP-server project with its own environment; only the first 30 lines of its brief were read, to confirm it is a different project).
- Status labels used below: "main" means merged; "open" means PR #189 or #190, not on main; "removed" means the feature was later deleted; "deleted doc" as above.

Kinds: HEURISTIC is library code with a known right answer or a simple rule. AGENT is a judgment a model could do better or worse and an automated test can score. HUMAN is the owner's taste. The kind column is my proposal, an inference in every row; the sources never use these terms.

## 2. Behaviours

Columns: id, requirement, evidence (reference and verbatim quote), literal values, how judged, proposed kind and reason.

### 2.1 Slicing and markers

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| S1 | The L and R locators define the region that slicing, playback and export all operate on. | 276d424: "Markers now define the working region for all operations, matching ReCycle's locator functionality" | none | not stated | HEURISTIC, a containment rule |
| S2 | Segments are stored as one ordered boundary list in which N boundaries give N-1 segments, with start and end always present. | `segment_manager.py` docstring: "Enforces invariant: N boundaries = N-1 segments" | start boundary 0, end boundary total_samples | test (14 tests, 059df80) | HEURISTIC, an invariant |
| S3 | The user splits the region into equal slices per measure. | AGENTS.md `--resolution R`; PR #44 subdivisions; no quotable sentence | resolutions 1, 2, 4, 8, 16 per measure; default 4 | test (PR #187: "/slice 4, asserts four segments") | HEURISTIC, arithmetic |
| S4 | Changing measures or resolution re-splits at once. | 4b84481: "Measures: re-split on measures/resolution change" | none | not stated | HEURISTIC, an event rule |
| S5 | The user can add a boundary at a position and remove the nearest one. | PR #150: "Updated remove_segment_boundary to find closest boundary instead of exact match" | removal tolerance 0.1 s (`segment_manager.py`) | not stated | HEURISTIC, nearest-neighbour rule |
| S6 | A marker dropped near the file start or end snaps to it. | PR #55: "Start marker snaps to 0.0s when within 50ms threshold" | snapThreshold 0.05 s | not stated | HEURISTIC, threshold rule |
| S7 | The focused marker moves by keyboard nudges in three step sizes and cannot cross its neighbour. | PR #170: "Nudge operations with constraint clamping (L < R, min region size)" | README: about 10 ms, Shift about 1 ms, Ctrl about 100 ms | test (27 tests, PR #170) | HEURISTIC, clamped arithmetic |
| S8 | Segment recomputation after marker moves is debounced. | PR #170: "50ms debounced recomputation for segment changes" | 50 ms | test | HEURISTIC, timer |
| S9 | Cutting to the selected region replaces the audio and resets segments and tempo. | PR #11: "Reset segments, tempo, and state after trimming" | none | not stated | HEURISTIC, state reset |
| S10 | Importing a file resets markers, segments and zoom. | 7384551: "Fix /import to fully reset state (markers, segments, zoom)" | none | looking (manual checklist in `docs/issues/debug_file_import_issues.md`) | HEURISTIC, state reset |
| S11 | Clicking inside segment N and pressing key N play the same audio. | deleted doc `design/segments.md`: "Clicking in segment N should play same audio as pressing key N" | none | test | HEURISTIC, one lookup path |
| S12 | The segment count is capped. | `docs/design/segments/segment-manager-design.md`: "Maximum 36 segments" | 36 segments; 20 reachable by key | not stated | HEURISTIC, a limit; the number is a parameter |
| S13 | A preset can carry slice points chosen by an artist. | `docs/breakbeat-science.md`: "Use **someone else's slices**" | none | listening (inference from the doc's framing as a cultural decision) | HUMAN, the slices are a person's choices |
| S14 | The user can place each slice by hand. | `docs/breakbeat-science.md`: "Place each slice **by hand** where it sounds right" | none | listening | HUMAN, "where it sounds right" |
| S15 | Cut positions can be written in samples, seconds or bar.beat.sixteenth. Open. | PR #190 body (cut lists; `0.44s`, 1-based `bar.beat.sixteenth`); no quotable sentence | none | test (389 tests reported) | HEURISTIC, unit conversion |
| S16 | Each slice can carry a role name that is written into SFZ comments and MIDI text events. Open. | PR #190: "one cut per line, a position then an optional role" | none | not stated | unsure; writing the role is HEURISTIC, and the cut-list author chooses it |
| S17 | DEL deletes the focused marker and a marker can be placed at a bar.beat position. | cbda589 commit body; no quotable sentence | none | not stated | HEURISTIC |

### 2.2 Transient detection

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| T1 | The user splits the region at detected onsets with one sensitivity number. | README: `/slice --transients n`; no quotable sentence | n from 0 to 100 | not stated | AGENT, onset placement can be scored against a reference chop |
| T2 | Detection parameters are read from config. | PR #71: "Added configurable transient detection parameters in audio.json" | threshold 0.2, waitTime 1, preMax 1, postMax 1, deltaFactor 0.1 (units not stated) | test, plus "adjust the threshold slider" (looking) | HEURISTIC for the plumbing; the values are untested defaults |
| T3 | The sensitivity control is mapped non-linearly to the threshold. Removed with the GUI. | 4b84481: "Changed from linear to exponential mapping (power of 5)" | exponent 5; range of interest 0.0 to 0.5 | not stated | HUMAN, a feel adjustment |
| T4 | A grid cut moves to just before a nearby onset, otherwise stays and warns. Open. | PR #190: `--snap-onsets [MS]`; no quotable sentence | 3 ms before the onset; search window half a sixteenth | test against the approved chop | AGENT, scored against the owner's fixture |
| T5 | A second detector gives onset positions fine enough for cutting. Open. | PR #190: "64-sample hop and backtracking for cutting" | hop 64 samples | test | AGENT, same reason |
| T6 | The tool reproduces the owner's 12-slice Amen chop exactly. Open. | PR #190: "All 12 boundaries equal the owner-approved manifest sample for sample" | 12 slices; 71 onsets; 137.72 BPM; 4 measures | test | HUMAN, the reference is the owner's choice |

### 2.3 Tempo and measures

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| M1 | Source tempo is computed from measure count and duration; nothing listens for the beat. | `src/python/bpm_analysis.md`: "BPM = (60 × total_beats) / duration_in_seconds"; PR #188: "no beat tracking added" | amen.wav 6.97 s, 4 measures, 137.72 BPM | test | HEURISTIC, a formula |
| M2 | The measure count comes from the preset or the user; an import assumes a default. | `bpm_analysis.md`: "auto-detection would be ideal but more complex" | default 4 measures | not stated | AGENT, measure count can be scored against the preset catalog (about 899 entries with `measures`) |
| M3 | A preset's measure count applies before the tempo display is filled. | PR #50: "amen_classic displayed incorrect tempo (34 BPM instead of 137 BPM)" | 34 vs 137 BPM | looking | HEURISTIC, ordering |
| M4 | Moving a locator recalculates the source tempo. | PR #134 title and body; no quotable sentence | 12 s and 4 measures give 80 BPM (deleted doc `designs/tempo-calculation-system.md`) | test | HEURISTIC |
| M5 | A target tempo the user set survives marker moves and segment edits. | PR #136: "Ensures user preferences for playback tempo are preserved when markers are moved" | 19e0771: stays at 160 BPM | test and manual check | HEURISTIC, state ownership |
| M6 | The user can type any BPM. | PR #133: "Fixed issue where imported files always had tempo set to 80 BPM" | default targetBpm 120 | not stated | HEURISTIC |
| M7 | Every measure has four beats. | `audio_processor.py`: "Standard 4/4 time for breakbeats" | 4 beats per measure | not stated | HEURISTIC, a stated default |
| M8 | The unit is called "measures" in the code and manifest and "bars" in TUI commands. | PR #43: "to align with proper musical terminology"; README `/set bars` | none | not stated | HUMAN, naming |

### 2.4 Playback and audio engine

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| P1 | Triggering a slice cuts off whatever is playing and starts the new one. | `ring_buffer_audio.py`: "immediately replaces any currently playing audio" | none | test (41 tests, 02b4fcf) | HEURISTIC |
| P2 | Number and letter keys trigger slices. | PR #147: "keys 1-9,0,q-p → segments 1-20" | 20 keys; see conflict K4 | test | HEURISTIC, a key map |
| P3 | Key input is modal so typing and triggering do not collide. | README: "This modal approach eliminates conflicts between typing and playback keys." | ESC enters SEGMENT mode, `i` enters INSERT | looking | HUMAN, an interaction choice |
| P4 | Space plays or stops the whole sample. | README key table; PR #37 for the toggle; no quotable sentence | none | not stated | HEURISTIC |
| P5 | A slice or region can loop without a gap. | `ring_buffer_audio.py`: "Gapless looping"; 528cf04: "This eliminates timing drift in loop playback" | none | test | HEURISTIC, sample-exact wrap |
| P6 | Each slice starts and ends with a short fade to prevent clicks. | PR #150: "Implemented 2ms exponential fades at stream start/stop transitions"; `docs/tui-guide.md`: "to prevent clicks" | engine default 3.0 ms in, 3.0 ms tail, exponential; see conflict K1 | listening (inference; PR #149 reports "pops") | HEURISTIC for the mechanism, HUMAN for the length and curve |
| P7 | Changing tempo changes the playback sample rate, so pitch moves with tempo. | `ring_buffer_audio.py`: "via sample rate adjustment (S1000 style)"; 53b8794: "tempo and pitch change together" | rate scaled by target BPM over source BPM (deleted doc `designs/tempo-calculation-system.md`: "The ratio between target and source BPM that determines actual playback speed") | listening (PR #81: "Verified exports match playback in sound") | HUMAN, the vintage-sampler behaviour is a chosen sound |
| P8 | Tempo can only change while stopped. | `ring_buffer_audio.py`: "This is only allowed when stopped or idle." | none | test | HEURISTIC |
| P9 | The engine runs one fixed format and input files must be 44100 Hz. | `ring_buffer_audio.py`: "Fixed engine format: 44.1kHz, stereo, float32"; AGENTS.md: "Input must be 44100 Hz" | 44100 Hz, 2 channels, float32 | test | HEURISTIC, validation |
| P10 | A buffer underrun produces silence and playback continues. | `ring_buffer_audio.py`: "Graceful underruns (silence, continue)" | none | test | HEURISTIC |
| P11 | Mono sources play at their original loudness in both channels. | `ring_buffer_audio.py`: "No amplitude scaling is applied" | gain 1.0 | not stated | HEURISTIC |
| P12 | Playback is good enough for auditioning slices; it is not a DAW transport. | `ring_buffer_audio.py`: "feels good for auditioning" | none | listening | HUMAN, "feels good" |
| P13 | Reverse playback as a mode does not exist. Removed. | 41c83ce: "The feature was not working correctly and added unnecessary complexity" | none | not stated | HUMAN, a scope decision by the owner |
| P14 | The audio engine starts before the TUI and is reused across preset changes. | 4e7e6b9 commit body; no quotable sentence | none | looking (a stray `p` character at startup) | HEURISTIC, ordering |
| P15 | The playing slice is highlighted until it ends. GUI, removed. | PR #65 body; no quotable sentence | colour #cccccc | looking | HUMAN, colour; HEURISTIC, timing |

### 2.5 Time-stretch and pitch

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| X1 | Tempo-adjusted audio is resampled by linear interpolation so it sounds like an old sampler. | `audio_utils.py`: "Uses simple linear interpolation for tempo adjustment"; 2896b08: "Creates characteristic vintage sampler artifacts" | export target 44100 Hz | listening (inference) | HUMAN, the artifacts are wanted |
| X2 | A time-stretch module offers four algorithms. Not in the live path (inference: no doc or PR describes a command that uses it). | `timestretch.py` docstrings; no quotable sentence | default phase vocoder; grain size default 50 ms | listening (02a691b: "some testing. doesnt sound great") | HUMAN, judged by ear and rejected |
| X3 | Akai S1000 style cyclic time-stretch is not provided. Removed. | PR #46: "unused AKAI S1000 time stretching implementation" | deleted doc `AKAIS1000.md`: grains 10 to 50 ms | not stated | unsure |

### 2.6 Export formats

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| E1 | Export writes one WAV per slice plus an SFZ and a MIDI file named after the output directory. | PR #124 body; README; no quotable sentence | `001.wav` to `NNN.wav`, `<dir>.sfz`, `<dir>.mid` | test | HEURISTIC |
| E2 | Exported audio equals what playback produced, resampled to a standard rate. | PR #81: "Follows 'what you hear is what you export' principle" | 44100 Hz | listening and test | HEURISTIC, one shared pipeline |
| E3 | SFZ regions map slices to consecutive keys. | AGENTS.md: "keys chromatic from C3 (60)" | first key 60; see conflict K5 | test | HEURISTIC |
| E4 | MIDI notes are back to back, each starting where the previous ends. | PR #125: "Ensures each note starts exactly when the previous one ends" | none | test; "Manually verified in validation/think-160-5 directory" | HEURISTIC |
| E5 | The MIDI file carries the adjusted tempo and a 4/4 signature. | dfef94d, 2befbf3 commit subjects; no quotable sentence | 4/4 | not stated | HEURISTIC |
| E6 | WAV lengths, SFZ regions and MIDI notes describe the same boundaries. | PR #118: "Verifies consistency between WAV files, SFZ regions, and MIDI notes" | 8 tests | test | HEURISTIC |
| E7 | Export writes a manifest; editing it and re-exporting is the headless edit loop, and an unedited manifest reproduces identical WAVs. | PR #188: "Editing that file and re-running the export is the complete headless edit loop"; AGENTS.md: "Re-exporting an unedited manifest reproduces the slice WAVs byte for byte" | file `<name>.rcy.json` | test (SHA-256) | HEURISTIC, determinism |
| E8 | An invalid manifest is refused, not repaired. | PR #188: "Validation refuses an inconsistent edit rather than repairing it" | keys 0..127; boundaries strictly increasing; slices = boundaries - 1 | test | HEURISTIC |
| E9 | The SFZ can reference one file per slice or offsets into the source file. | PR #188 (dialects `files` and `offsets`); no quotable sentence | two dialects | test | HEURISTIC |
| E10 | SFZ sample paths are relative. | 1f155f1: "Improves privacy" | none | not stated | HEURISTIC |
| E11 | Export includes the first and last segments and skips zero-length ones. | 60d40df: "the start (0) and end of the audio file in segments"; 21304cd | none | not stated | HEURISTIC |
| E12 | Stereo sources export as stereo; the user can convert to mono from left, right or a mix. | PR #47 body; 436322e; no quotable sentence | three methods | not stated | HEURISTIC |
| E13 | Export runs without the TUI. | PR #186 (`rcy-export`, headless smoke); no quotable sentence | "259 passed, 30 deselected" | test | HEURISTIC |
| E14 | Export prints a per-slice table. Open. | PR #190 body; no quotable sentence | none | looking | HEURISTIC |
| E15 | A standalone tool builds an SFZ from a directory of WAVs. | PR #93; `src/python/utils/sfz/README.md`; no quotable sentence | start key 36 | not stated | HEURISTIC |

### 2.7 Sampler hardware

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| H1 | Upload to an EP-133 needs an explicit slot. | e839b6f: "Require explicit slot for upload to prevent accidental overwrites" | 999 slots; "USER1: 700-799 recommended" | not stated | HEURISTIC, a required argument |
| H2 | EP-133 pads map to fixed note ranges. | `ep133-s2800-bridge.md` (repo root); no quotable sentence, values from its tables | A 36-47, B 48-59, C 60-71, D 72-83 | not stated | HEURISTIC, device fact |
| H3 | Samples reach Akai S2800 and MPC2000XL through MIDI Sample Dump with offset-binary encoding. | `src/python/mpc2000xl/README.md`: "Silence is `0x8000`, not `0x0000`" | 120 data bytes per packet; handshake timeout 5.0 s; packet timeout 2.0 s; 3 retries | listening ("inverted and heavily distorted" without it) | HEURISTIC, protocol |
| H4 | The MPC2000XL ignores slot numbers and names. | b4adb8c: "MPC ignores slot number and SDS name extension" | names MIDI_1, MIDI_2 | observation on device | HEURISTIC, device fact |
| H5 | S2800 drum programs get fixed voice defaults. | 5e8aefa: "32-voice polyphony, OLDEST voice assignment, mute group OFF" | 32 voices | not stated | HUMAN, sound-design defaults |
| H6 | Several S2800 programs play at once when they share a program number and differ in MIDI channel. | repo `CLAUDE.md`, Pattern 3; no quotable sentence | PRGNUM equal, PMCHAN distinct | observation on device | HEURISTIC, device fact |
| H7 | The 909-style web controller sends a parameter when the knob is released and confirms it by reading back. | 226f4e4: "SysEx only on mouseup"; "500ms readback confirmation" | 500 ms | looking | HEURISTIC |
| H8 | Core writes files only; devices are reached through separate push plugins. Open. | PR #189: "RCY core now writes files and talks to no hardware" | `rcy-push <device> --manifest KIT.rcy.json`; exit 2 if plugin missing | test | HEURISTIC, a process boundary |

### 2.8 UI, keys and layout

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| U1 | The interface is a terminal UI; the desktop GUI is gone. | PR #165: "Remove the legacy PyQt6 GUI from RCY, simplifying the codebase to focus on the TUI (Textual) interface." | 43 files, about 8,500 lines | not stated | HUMAN, direction |
| U2 | Colour skins are selectable. | README `/skin`; `config/skins/*.json`; no quotable sentence | default, high-contrast, monochrome, hacienda | looking | HUMAN, colours |
| U3 | The GUI used a fixed palette and typeface. Removed. | PR #22: "inspired by New Order's Movement, brutalist design, and hauntological software" | markers #007fa3, slices #7f8fa6, background #cbe9f3, selection #ff3366 | looking | HUMAN |
| U4 | Marker handles have a fixed screen size. GUI, removed. | PR #28: "Triangles remain fixed in size and don't scale with zoom" | see conflict K8 | looking | HUMAN |
| U5 | The waveform display keeps short hits visible when reduced. | deleted doc `designs/downsampling-strategy.md`: "Ensures ghost notes and fast hi-hats still appear as blips" | targetLength 2000, minLength 1000, maxLength 5000 points | looking | HEURISTIC, max-min envelope |
| U6 | The view zooms in steps around its centre. | deleted doc `designs/zoom-and-scroll.md`; README `/zoom`; no quotable sentence | factor 1.25; 0.5x to 10x | looking | HEURISTIC |
| U7 | Slash commands run without a model; other text goes to a language model. | README: "lazy-loaded on first natural language input to avoid startup lag" | OpenRouter `anthropic/claude-sonnet-4`; temperature 0.3; max_tokens 1024 | not stated | AGENT, mapping free text to commands is scoreable |
| U8 | The main window shows no permanent help text. GUI, removed. | PR #13: "Removed permanent tooltips from main window" | none | looking | HUMAN |
| U9 | Stereo files show two stacked waveforms. GUI, removed. | PR #47 body; config `stereoDisplay` true; no quotable sentence | none | looking | HUMAN |
| U10 | Segment add and remove use modifier clicks. GUI, removed. | PR #48: "Alt+Click adds segments, Alt+Cmd+Click removes segments" | PR #70 adds Ctrl+Click, Ctrl+Alt+Click | looking | HUMAN |
| U11 | Notebook pages (Bank, Sounds, Pick/Hold/Drop) do not exist. Removed. | PR #187: "This PR removes the feature instead of recreating it" | none | test (import works again) | HUMAN, scope |
| U12 | Waveform redraw is fast enough to drag markers smoothly. GUI, removed. | deleted doc `designs/pyqtgraph-migration.md`; no quotable sentence | Matplotlib 210-280 ms redraw, 5-8 FPS; PyQtGraph 15-25 ms, 55-60 FPS | measurement, method not stated | HEURISTIC, a latency budget |

### 2.9 Config and presets

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| C1 | Presets are catalog entries with name, file path and measure count. | PR #33: "Validated that measures and tempo are correctly set from preset metadata" | core: amen_classic 4, apache_break 2, apache_L 2, apache_R 2 | test | HEURISTIC |
| C2 | The Amen break loads at startup. | PR #17: "Load Amen break (audio/amen.wav) by default on startup" | default preset `amen_classic` | looking | HUMAN, which break |
| C3 | A large preset catalog ships without its audio. | `config/presets/rhythm-lab.json`; sample-pack README; no quotable sentence | about 899 presets; `rl_` prefix | not stated | HEURISTIC |
| C4 | Preset notes teach the history of each break. | PR #20: "making RCY not just a tool but an educational resource for producers" | none | not stated | HUMAN |
| C5 | Files are opened with `/preset` or `/import`. | 7384551 (removes `/open`); earlier PR #85; no quotable sentence | none | not stated | HEURISTIC |
| C6 | Log files rotate. | `config/config.json`; no quotable sentence | 10485760 bytes; 3 backups; level INFO | not stated | HEURISTIC |

### 2.10 Tooling and dev process

| id | requirement | evidence | values | judged | kind |
|---|---|---|---|---|---|
| D1 | The project installs and runs through uv and `just`. | PR #186 body; repo `CLAUDE.md`; no quotable sentence | `just run`, `just test`, `just doctor`, `just smoke` | test | HEURISTIC |
| D2 | Behaviour whose quality is a feeling may be tested by hand if written down. | CONTRIBUTING.md: "**Manual testing is OK** for UX/feel features" | none | listening or looking | HUMAN, by the doc's own statement |
| D3 | Tests do not assert against the live audio thread with sleeps. Open. | PR #189: "sleeps 20 ms and asserts against the live audio callback thread" | 20 ms | test | HEURISTIC |
| D4 | CI covers macOS and Linux only. | PR #186 (Windows dropped); no quotable sentence | none | not stated | HEURISTIC |
| D5 | Hardware protocol questions go to a specialist agent that holds the spec. | `src/python/s2800/README.md`: "orchestrators coordinate, specialists execute" | 175+ parameters, 35-page spec | not stated | AGENT, protocol answers can be checked against the spec |
| D6 | Reported test counts. | PR #186, AGENTS.md, PR #190; no quotable sentence | 259, 311, 389 (open) | test | not a behaviour; context |

### 2.11 Counts

Rows per area: slicing/markers 17, transient detection 6, tempo/measures 8, playback/engine 15, time-stretch/pitch 3, export 15, hardware 8, UI 12, config/presets 6, tooling 6. Total 96.

Kinds by first label in the kind column: HEURISTIC 63, HUMAN 24, AGENT 6, unsure 2, context 1. Rows with a second label (P6, P15, S16, T2) are counted once by the first.

## 3. Named constants and defaults that change audio behaviour

From docstrings, dataclass defaults and function signatures in the five permitted modules, and from `config/config.json`. "No reason stated" means neither the comment nor any doc I read gives one.

| where | name | value | unit | reason given |
|---|---|---|---|---|
| `ring_buffer_audio.py` EngineConfig | sample_rate | 44100 | Hz | "Fixed engine format" (no further reason) |
| same | channels | 2 | channels | no reason stated |
| same | blocksize | 256 | frames | "Low latency block size" (comment in `audio_processor.py`) |
| same | ring_buffer_ms | 250 | ms | no reason stated |
| same | low_watermark_ms | 50 | ms | no reason stated |
| same | high_watermark_ms | 150 | ms | no reason stated |
| same | fade_in_ms | 3.0 | ms | "anti-click" (module docstring) |
| same | tail_fade_ms | 3.0 | ms | no reason stated |
| same | fade_curve | exponential | n/a | no reason stated |
| same | autostop_one_shot | True | bool | no reason stated |
| `audio_processor.py` | required input rate | 44100 | Hz | "RCY requires 44100 Hz audio files." |
| same | source_bpm default | 120.0 | BPM | no reason stated |
| same | beats_per_measure | 4 | beats | "Standard 4/4 time for breakbeats" |
| same | default preset | amen_classic | n/a | no reason stated |
| same, `split_by_transients` | threshold | 0.2 | 0 to 1 | no reason stated |
| same | waitTime, preMax, postMax | 1, 1, 1 | not stated | no reason stated |
| same | deltaFactor | 0.1 | ratio | no reason stated |
| `segment_manager.py` | removal tolerance | 0.1 | s | "Maximum distance in seconds to consider a click \"on\" a marker" |
| same | sample_rate default | 44100.0 | Hz | no reason stated |
| `timestretch.py` | default algorithm | phase vocoder | n/a | no reason stated |
| same | grain_size_ms | 50 | ms | "Default grain size is 50ms" |
| `audio_utils.py`, `apply_tail_fade` | enabled, duration_ms, curve | False, 10, exponential | ms | no reason stated |
| same | resample target | 44100 | Hz | compatibility with DAWs (deleted doc `designs/playback-export-pipelines.md`) |
| `config/config.json` | tailFade | enabled true, 3, exponential | ms | no reason stated |
| same | playback.mode | one-shot | n/a | no reason stated |
| same | playbackTempo | enabled false, targetBpm 120 | BPM | no reason stated |
| same | transientDetection | 0.2, 1, 1, 1, 0.1 | as above | no reason stated |
| same | markerSnapping.snapThreshold | 0.05 | s | no reason stated |
| same | downsampling (display only) | 2000 target, 1000 min, 5000 max, method envelope | points | keep transients visible (deleted doc) |

Four facts I saw in function bodies, outside the docstring-and-constant allowance, reported so the caller can discard them: detection runs on the left channel only; the detector's delta is threshold × deltaFactor (0.02 at defaults); the exponential fade ramp is a cube (t³); the output stream opens with `latency='low'`.

## 4. Transient detection as documented

Method. The docs name it twice. `docs/design/segments/segment-mutation-inventory.md` calls the transient split "AI-based onset detection using librosa". PR #190 (open) describes `onsets.detect_onsets()` as "librosa onset strength + peak picker". No doc describes the algorithm beyond that.

Parameters and defaults on main: threshold 0.2, waitTime 1, preMax 1, postMax 1, deltaFactor 0.1, all from `config/config.json`, introduced by PR #71. No source states the units of waitTime, preMax or postMax, and none gives a reason for any value. No hop size is named on main; reading it as librosa's default would be inference. The user-facing control is `/slice --transients n` with n from 0 to 100. The docstring says the split happens "within a region"; a code comment (outside the allowance) says only onsets strictly inside L-R are kept.

Stated dissatisfaction. I found no sentence saying "transient detection is bad". The evidence is indirect:
- PR #190: the producer validation run "had to write its own onset detection, grid math, manifest builder and verification table".
- 4b84481 remapped the slider because useful values sit in a narrow band: "Concentrates control in useful threshold range (0.0-0.5)".
- `docs/breakbeat-science.md` recommends the opposite of transient slicing as the first workflow: "Chop the loop by **time**, not transients".
- CONTRIBUTING.md asks for docs that do not exist yet: "Write markdown docs for existing features (e.g. split-by-transients)".

What PR #190 would add, if merged: a second detector with a 64-sample hop and backtracking; `--snap-onsets` (default 3 ms before the nearest onset, only within half a sixteenth, otherwise leave and warn); `--grid-offset MS`; and the owner-approved 12-slice Amen chop as a fixture that the tool must match sample for sample. That fixture is the only scored reference for cut placement in any source I read.

## 5. What the playback engine promises

Current engine: RingBufferAudioEngine (02b4fcf, 2025-12-29, 41 tests).

- Purpose: "aligned with \"feels good for auditioning\", not DAW-grade transport. Designed for EP-133 oriented workflows."
- Format: 44.1 kHz, stereo, float32 only. Input files at other rates are rejected.
- One-shot: hard cut. A new trigger replaces the current sound. No voice overlap is promised anywhere.
- Fades: fade-in 3.0 ms and tail fade 3.0 ms by engine default, exponential; `/set release <ms>` changes the tail (README, default 3 ms). Conflicts in K1.
- Loop: "Gapless looping". 528cf04 made the pattern player wait for an engine event instead of sleeping, which "eliminates timing drift in loop playback".
- Tempo change: sample-rate change, "S1000 style". Pitch rises and falls with tempo. Allowed only when stopped or idle. (That it restarts the stream is from a function body, outside the allowance.) One deleted doc says otherwise (K2).
- Reverse: no user-facing reverse. Loop-and-Reverse was added in PR #72 and removed in 41c83ce. `play_segment` still has a `reverse` parameter in its signature; bddf833 removed reverse from the playback pipeline "(no UI support)".
- Underrun: silence, then continue.
- Latency: no number is promised for the current engine. The only stated design values are blocksize 256 frames (5.8 ms at 44.1 kHz, my arithmetic), a 250 ms ring buffer and 50/150 ms watermarks.
- Performance numbers on record, all for earlier engines or for targets:
  - `docs/issues/issue_128_*.md`: a table row giving loop latency as ~50-100ms for the old engine and <5ms for the new one, and "Sub-5ms audio callback execution (tested)". These describe ImprovedAudioEngine, which 02b4fcf deleted.
  - `segment-manager-design.md`: "**Keyboard Query**: < 1ms response time", mouse query under 5 ms, bulk update under 10 ms for 100+ segments. These are targets; no measurement is recorded.
  - PR #149 states the motivating failure: "This causes latency + pops that destroy musical playability".

## 6. Conflicts between sources

Listed without picking a winner.

- K1 Tail fade. `config/config.json`: enabled, 3 ms, exponential. `docs/tui-guide.md`: curve "linear". `docs/CONFIGURATION_GUIDE.md`: disabled, 10 ms. `audio_utils.apply_tail_fade` defaults: disabled, 10 ms. PR #150 used 2 ms.
- K2 Tempo and pitch. Deleted doc `designs/tempo-calculation-system.md`: "effectively changes the speed without altering pitch". Deleted doc `designs/playback-export-pipelines.md`: "changes pitch and tempo by changing sample rate". The engine docstring and 53b8794 agree with the second.
- K3 Manifest slices. PR #188 body says validation cross-checks slice start and end against boundaries. AGENTS.md on main says "`boundaries` is authoritative" and slice start/end are ignored on load. Inference: a follow-up changed it after the PR body was written.
- K4 Segment keys. PR #147 maps q-p to segments 11-20. README reserves `i` and maps the remaining letters to 11-19. The table in `docs/tui-guide.md` lists q=11 to u=17, o=19, p=20 and has no key for 18.
- K5 Key naming. AGENTS.md: "C3 (60)". `ep133-s2800-bridge.md` lists note 60 as "C4 (Middle C)". The SFZ generator utility defaults to 36 and calls it C1.
- K6 Stale preset. README lists `think_break` (1 bar). 4e7e6b9 removed it: "48000Hz sample rate not supported".
- K7 Sample rate. PR #47: "Handle non-44100 Hz sample rates". AGENTS.md and `audio_processor.py`: 44100 Hz required.
- K8 Marker handles. `config/config.json`: flag, 10 wide by 16 high. `docs/CONFIGURATION_GUIDE.md`: rectangle 8 by 14. PR #28: "16px base × 10px height". PR #53: "2% of total duration".
- K9 Nudge size. README says about 10 ms; 7916d45 defines fine as 0.1x and coarse as 10x of a base step. No doc states the base step in samples.

## 7. Design decisions with a recorded reason

1. Tempo by sample rate, no stretch: "It does what the Akai S1000 did" (deleted doc `designs/playback-export-pipelines.md`); 53b8794: "This replicates old-school sampler behavior".
2. Export resamples to 44100 Hz because other software "May not support non-standard rates like 51235 Hz" (same deleted doc).
3. Linear interpolation over FFT resampling, for the sound: 2896b08.
4. Timing precision as the reason for one pipeline: "Shifting a snare by 1 ms can kill a groove." (same deleted doc).
5. Max-min envelope for display, with striding rejected as "fast but often hides detail" and RMS as "visually smooth but poor for transient work".
6. One SegmentManager, because click and keyboard paths computed segments separately and disagreed by one (deleted doc `design/segments.md`; 059df80).
7. New audio engine because pops were structural: "\"Audio pops\" aren't tech debt - they're architectural" (PR #149).
8. Modal input to stop key conflicts (README).
9. Grid slicing first: "Chop the loop by **time**, not transients" (`docs/breakbeat-science.md`).
10. Explicit EP-133 slot "to prevent accidental overwrites" (e839b6f).
11. Relative SFZ paths: "Improves privacy" (1f155f1).
12. No beat tracking: "BPM is measures over duration, as the CLI already did; no beat tracking added" (PR #188).
13. Refuse, do not repair, an inconsistent manifest (PR #188).
14. Notebook pages removed, not rebuilt (PR #187).
15. Hardware out of core (PR #189, open).
16. GUI removed to focus on the TUI (PR #165); Matplotlib replaced by PyQtGraph for speed (PR #67, benchmark in section 2.8 U12).
17. Opinionated presets: "RCY isn't. It has a point of view." (`presets/README.md`).

## 8. Reversed decisions

| # | first position | reversal |
|---|---|---|
| R1 | Markers and segments independent; export ignores markers (`docs/design/segments/segments_and_markers.md`, 2025-04-08: "segments and markers operate independently") | L/R region governs everything (276d424, 2025-11-23; a3d6a3b, 2025-12-05) |
| R2 | Resampler kaiser_fast, "not configurable by design" (deleted doc `designs/playback-export-pipelines.md`) | kaiser_best (PR #147, 2025-05-24), then linear interpolation (2896b08, 2025-11-23) |
| R3 | Playback tempo for "playback only (not export)" (PR #75) | export uses the same processing (PR #81) |
| R4 | Tempo applied per segment by resampling (PR #81 pipeline) | tempo applied as engine sample rate (777ae55, c224989, 2025-05-25); c224989 gives the reason "pops and latency during playback" |
| R5 | Marker move force-enables tempo adjustment (fix quoted in `docs/issues/issue_description.md`) | user setting preserved (PR #136) |
| R6 | Loop-and-Reverse mode added (PR #72, b9f6203) | removed (41c83ce) |
| R7 | MIDI "original" timing mode kept beside "continuous" (PR #125) | removed (PR #139) |
| R8 | Tail fade added (PR #81), fades at segment ends (PR #150) | commented out (PR #152), later enabled by default at 3 ms in `config/config.json` |
| R9 | "bars" renamed "measures" (PR #43) | TUI commands say "bars" again (9fbd1c9, README) |
| R10 | Changing resolution "without triggering splits" (PR #44) | live re-split (4b84481) |
| R11 | Non-44100 Hz files handled (PR #47) | 44100 Hz enforced (4e7e6b9, AGENTS.md) |
| R12 | Matplotlib GUI (5d16d2d, 2024-10-05, first draft) | PyQtGraph (PR #67, #78), then GUI removed (PR #165) |
| R13 | Grain time-stretch experiments (7700f88, 744d3e1, 2024-10-14/15) | "doesnt sound great" (02a691b); S1000 stretch file deleted (PR #46) |
| R14 | Notebook pages added (5e8aefa, 2026-02-14) | removed (PR #187) |
| R15 | Hardware drivers in core (EP-133 092016d, S2800 8fb0bf1, MPC2000XL b4adb8c) | moved out (PR #189, open) |
| R16 | Ctrl+Click sets end marker (PR #11) | Ctrl+Click adds a segment (PR #70) |
| R17 | SFZ with absolute default_path (632134a) | relative paths (1f155f1, same day) |
| R18 | Fallback audio engine kept beside the fast one (`docs/issues/issue_128_final_update.md`: "Traditional engine remains as fallback") | removed (a15e909); that engine then replaced (02b4fcf) |
| R19 | `/open` and Open-session vs Import (PR #85) | `/preset` plus `/import` (7384551) |

## 9. Timeline

1. 2024-10-05 to 10-14: first draft; SFZ and MIDI export; grain time-stretch tried and judged poor.
2. 2025-04-05/06: start/end markers and Cut; presets; palette.
3. 2025-04-07: measure subdivisions, stereo display, marker snapping.
4. 2025-04-11/12: PyQtGraph replaces Matplotlib; transient config; playback modes; tempo by sample rate.
5. 2025-04-13: one pipeline for playback and export; export resampled to 44100 Hz.
6. 2025-04-28: export naming; MIDI continuous timing.
7. 2025-05-23 to 05-26: low-latency engine; slice keys; SegmentManager; pop fixes.
8. 2025-11-23: locators govern all operations; linear-interpolation resampling; live re-split; Loop-and-Reverse removed; design docs deleted.
9. 2025-11-29: Textual TUI.
10. 2025-12-04/05: GUI removed; EP-133 support; modal input and language-model agent; marker focus and nudge.
11. 2025-12-28/29: Rhythm Lab catalog; ring-buffer engine; skins; `/import`.
12. 2026-02-14 to 02-20: Akai S2800 support; 909 controller; notebook pages.
13. 2026-03-17: MPC2000XL sample transfer.
14. 2026-09-02: uv packaging and headless export (#186); notebook pages removed (#187); kit manifest (#188).
15. Open: hardware moved to plugins (#189); cut lists, onset snapping and the approved Amen fixture (#190).

## 10. Not found

Each search ran over one text file holding every source above (683 kB). Each pattern matches known text elsewhere, so the query works; the specific fact is what is missing.

- A latency figure for the current ring-buffer engine. Pattern `latency`: 15 hits, all about the earlier engine, the `Low latency block size` comment, or startup lag.
- Units for waitTime, preMax and postMax. Patterns `frames` (65 hits) and `hop` (31 hits): none beside those parameter names.
- Backtracking on main. Pattern `backtrack`: 1 hit, in PR #190 (open).
- Any reviewer other than the PR author: two GitHub endpoints agree on zero reviews.
