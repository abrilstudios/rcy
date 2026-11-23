# Behaviours expressed in the rcy issue tracker

Source: all 126 issues of `abrilstudios/rcy` (#1 to #185; the other 59 numbers in that range are pull requests), bodies and comments, exported with `gh` and read in full. No Python source was read. Two documents the issues point to were read: `docs/breakbeat-science.md` (#40) and `docs/design/segments/segments_and_markers.md` (#57). The design files named in #90 and #131 under `designs/` are not in the repository at that path and were not read.

Reading conventions used below:

- Every issue body and 151 of the 155 comments were posted by the owner's login `tnn1t1s`. Many of those comments are implementation reports written by a coding agent under that login. Short lowercase comments such as "works now." are treated as the owner's own verdict; long structured reports are treated as agent claims.
- GitHub marks 117 issues closed as completed. That flag does not mean the behaviour shipped: twelve issues (#27, #59, #90, #99, #103, #107, #122, #151, #154, #156, #157, #161) carry the closing comment "Closing: TUI-specific feature superseded by web pivot. See #171 for new direction." and are recorded here as abandoned.
- #164 removed the PyQt6 desktop interface and kept the terminal interface. Mouse and drawing behaviours built before that are recorded as implemented in the desktop GUI and removed with it. The issues do not say which of them the terminal interface kept, except where a later terminal issue is cited.
- Text in double quotes after an issue number is verbatim from that issue. Everything else is paraphrase. Sentences marked "Inference:" are mine, not the issues'.
- Kind is HEURISTIC (library code with a known rule), AGENT (a model could do it better or worse and a test could score it), HUMAN (only the owner's ears or eyes can judge), or unsure.

## Slicing/markers

### S1. The file start and file end always count as slice boundaries
- Requirement: The audio before the first marker and after the last marker are segments, and they play, show and export like any other segment.
- Area: slicing/markers
- Evidence: #1 "First slice not playable or exportable"; #61 "First segment doesn't play when clicked"; #86 (export with markers but no segments produced nothing); #116, #117 (segment count in the display differed from the exported count).
- Values: 2 user markers give 3 segments; zero-length segments are skipped.
- Judged: tests (#117 asks that MIDI note counts match WAV file counts for every slicing method).
- Outcome: implemented, after the same defect was fixed four times (#1, #61, #86, #116).
- Kind: HEURISTIC; a fixed boundary rule with a countable result.

### S2. A slice marker can be added by hand at a chosen position
- Requirement: The user can place a new slice marker anywhere in the waveform.
- Area: slicing/markers
- Evidence: #5 "should be able to mouse click to add a custom transient then delete if needed"; #69 (Ctrl+click adds); #169 (terminal command places a marker by bar and beat).
- Values: Alt+click, then Ctrl+click (#69); `/marker 3.2` means bar 3, beat 2 in 4/4, rounded to a grid resolution of 1/4, 1/8 or 1/16; an existing marker within a snap distance is moved instead of a new one being made (50 samples in the #169 text, 10 ms in its implementation report).
- Judged: #169 by unit tests (15 reported); earlier issues not stated.
- Outcome: implemented in the desktop GUI, GUI removed by #164; reimplemented for the terminal as #169.
- Kind: HEURISTIC; position arithmetic.

### S3. A slice marker can be deleted, and region markers cannot
- Requirement: The user can remove any slice marker; the start and end markers of the region stay.
- Area: slicing/markers
- Evidence: #3 "if user resets with slider then forget deleted transitent"; #69 (Ctrl+Option+click deletes); #59 (hover delete control); #168 (DEL key).
- Values: #59: within ±5 px of the marker, 200 ms hover delay. #168: DEL or Backspace; focus moves to the nearest remaining marker.
- Judged: #168 by unit tests (8 reported); others not stated.
- Outcome: gesture changed three times (Alt+Cmd+click, Ctrl+Option+click in #69, DEL in #168); #59 abandoned at the web pivot.
- Kind: HEURISTIC; list edit with a fixed constraint.

### S4. A start marker and an end marker are always present
- Requirement: Every loaded file shows a draggable start marker and end marker that bound the working region.
- Area: slicing/markers
- Evidence: #10 (draggable start/end markers); #52 "Removal of markers is no longer a required feature".
- Values: defaults are start = 0 s and end = file duration (#52). #10 set them with Shift+click and Ctrl+click and cleared them with the `r` key.
- Judged: not stated.
- Outcome: changed later; #52 made the markers permanent and dropped #10's clear action, citing ReCycle 2.5 as precedent.
- Kind: HEURISTIC; fixed defaults.

### S5. Cut trims the audio to the region and resets everything derived from it
- Requirement: A Cut action discards audio outside the region and clears slices, tempo and state.
- Area: slicing/markers
- Evidence: #10 "I want all slice markers, BPM/tempo, and state to reset after trimming."; #82 (Cut broke after the drawing library changed).
- Values: #82 lists edge cases: region under 0.1 s, markers in reverse order, a single marker.
- Judged: not stated.
- Outcome: implemented, broke once (#82), repaired. Inference: #158 later made the region the scope of every operation without trimming, which covers much of what Cut was for; no issue retires Cut.
- Kind: HEURISTIC; buffer trim.

### S6. Region markers snap to the file bounds
- Requirement: A start or end marker dropped close to the file edge lands exactly on the edge.
- Area: slicing/markers
- Evidence: #54 (title "Snap Start/End Markers to Waveform Bounds").
- Values: a snap distance is specified, but the number is missing from the stored issue text.
- Judged: not stated.
- Outcome: closed as completed; GUI removed by #164, carry-over not stated.
- Kind: HEURISTIC; threshold compare.

### S7. Slice evenly by musical subdivision
- Requirement: The user can split the region into equal slices per measure at standard subdivisions.
- Area: slicing/markers
- Evidence: #41 (extend "Split by Bars" to all standard subdivisions); #117 (tests at several resolutions); #171 (web tool `slice_by_measures`).
- Values: 1, 2, 4, 8, 16 slices per measure (#41); tests at 2, 4, 8, 16 (#117).
- Judged: tests (#117).
- Outcome: implemented.
- Kind: HEURISTIC; division of a known length.

### S8. The region between the start and end markers is the scope of every operation
- Requirement: Tempo, slicing, playback and export all act on the selected region, never silently on the whole file.
- Area: slicing/markers
- Evidence: #158 "make L/R region the atomic working context for all operations"; #86 "what you see selected is what gets exported".
- Values: #158 example: region 1.73 s inside a 6.97 s file.
- Judged: tests (#158 reports 5 in `tests/test_tempo_region_consistency.py`).
- Outcome: implemented 2025-12-07 after partial fixes in #86, #131, #138.
- Kind: HEURISTIC; one rule applied to all call sites. The earlier design note `docs/design/segments/segments_and_markers.md` states the opposite, that segments and the start/end markers operate independently; #158 is later.

### S9. One marker has focus and the arrow keys nudge it
- Requirement: The user picks one marker and moves it left or right in small fixed steps, and markers can never cross or leave the region.
- Area: slicing/markers
- Evidence: #167 "Pick a marker. Nudge it left/right in small steps."
- Values: step 100 samples by default (`waveform.nudge_samples`); recompute debounced 50 ms; Tab and Shift+Tab cycle focus (#169 summary).
- Judged: unit tests for constraints, focus and debounce (#167).
- Outcome: implemented.
- Kind: HEURISTIC; clamped integer moves. Inference: where the marker should end up is judged by ear (see S10), so the step size is a parameter the owner tunes.

### S10. Markers can be moved while a loop plays
- Requirement: Dragging or nudging a marker during loop playback changes the loop without a crash or a jump in tempo.
- Area: slicing/markers
- Evidence: #155 "move start/end markers based on feel and vibe while a loop is playing" (from a long analysis comment, so by the convention above an agent's wording that the owner did not contradict).
- Values: agent report says the fix was checked over "10+ iterations" of the loop.
- Judged: listening while adjusting (the workflow itself); the fix by manual run.
- Outcome: crash fixed. The proposal to hold tempo fixed during playback and recompute on stop is in a comment; the issue does not say whether it shipped.
- Kind: HEURISTIC for the no-crash rule; the marker position reached this way is HUMAN.

### S11. Slice positions are saved with the preset
- Requirement: Slices the user made survive switching presets or reloading the file.
- Area: slicing/markers
- Evidence: #160 "users lose all their carefully crafted segment work when switching presets or reloading files".
- Values: none fixed; ReCycle's RX2 file is the model; storage options listed are JSON plus audio, binary, or both.
- Judged: not stated.
- Outcome: still open.
- Kind: HEURISTIC; serialisation.

## Transient detection

### T1. Slice points are proposed automatically from the drum hits
- Requirement: The tool finds the hits in a break and puts slice markers on them well enough that the owner accepts the result.
- Area: transient detection
- Evidence: #2 "this first pass is not very good."; #171 (web tool `slice_by_transients`).
- Values: none in #2. No issue states a target such as hits found or timing error.
- Judged: not stated; the owner rejected the first attempt without giving a criterion.
- Outcome: #2 closed; #58 exposed the parameters instead of changing the method. No issue reports that detection quality became acceptable.
- Kind: AGENT. Inference: the issues give no rule that is known to be right, and a detector could be scored against hand-placed markers on the bundled breaks.

### T2. Detection sensitivity is adjustable
- Requirement: The user or the config can change how many hits the detector reports.
- Area: transient detection
- Evidence: #58 "Default values produce the same results as the current implementation"; #3 (a threshold slider already existed); #171 (sensitivity argument).
- Values: #58: threshold 0.2 (range 0.01 to 1.0), waitTime 1, preMax 1, postMax 1, deltaFactor 0.1 with delta = threshold × 0.1 (units not given). #171: sensitivity 0.0 to 1.0, default 0.5, plus a maximum slice count.
- Judged: #58 by equality with previous output.
- Outcome: implemented (#58); the #171 parameters are a proposal.
- Kind: HEURISTIC; parameter plumbing. The right value per break is AGENT or HUMAN.

### T3. Choosing chop points for groove
- Requirement: Chop points that make a break feel right are chosen by a person, beyond what even division or hit detection gives.
- Area: transient detection
- Evidence: #73 "but it cannot *groove*".
- Values: workflow test in #73 and #76 targets 160 BPM on a 10 s clip.
- Judged: listening.
- Outcome: stated as a finding in #73, not built as a feature.
- Kind: HUMAN; the issue itself assigns it to the person.

## Tempo/measures

### M1. Tempo is derived from region length and measure count
- Requirement: The displayed source tempo equals the number of beats in the region divided by its length in minutes, for presets and imported files alike.
- Area: tempo/measures
- Evidence: #6 (set the number of bars, update the tempo display); #32 (tempo from duration and measures); #131 "Current behavior always sets tempo to 80 for imported files."; #158 (measure change used the whole file length).
- Values: beats = measures × 4 (#158). #74 writes the formula as (60 × measures) / duration, without the factor of 4; the two disagree as written. Examples: 12 s and 4 measures give 80 BPM (#135); the Amen preset at 4 measures gives about 137.7 BPM (#49); a wrong path produced 34.43 BPM and 547 BPM (#158).
- Judged: tests (#158), and by reading the displayed BPM against the known tempo of the break.
- Outcome: implemented; it went wrong in #49, #77, #131, #138 and #158 before the region rule (S8) settled it.
- Kind: HEURISTIC; one formula.

### M2. Each preset carries the correct measure count
- Requirement: A bundled break loads with the number of measures it really contains, so the tempo is right on first load.
- Area: tempo/measures
- Evidence: #49 "works now."; #77 (Think break listed as 4 measures when it holds 1).
- Values: Amen 4 measures; Think break 1 measure, about 2.11 s, about 114 BPM instead of about 456.
- Judged: looking at the displayed BPM.
- Outcome: implemented by correcting the metadata by hand, twice.
- Kind: AGENT. Inference: the count was entered by hand and was wrong twice; an estimate of measures from the audio could be scored against the known tempo of each break.

### M3. Moving a region marker updates tempo and leaves the tempo-adjust switch alone
- Requirement: Dragging the start or end marker recomputes source tempo and never turns playback tempo adjustment on by itself.
- Area: tempo/measures
- Evidence: #131 "when markers update left and right, they should update the tempo accordingly."; #135 "Keep the current playback_tempo_enabled setting (preserve user choice)".
- Values: halving a 12 s, 4-measure region shows 160 BPM (#135).
- Judged: by using the app (the #135 report came from the owner's own session).
- Outcome: implemented; #135 was a regression introduced by the #131 fix.
- Kind: HEURISTIC; state must not change as a side effect.

### M4. Target tempo is typed as a number
- Requirement: The user enters any target BPM in a text field, and entering one turns tempo adjustment on.
- Area: tempo/measures
- Evidence: #132 "Add functionality to allow free-form input of target tempo."; #137 (title "Remove tempo adjust dropdown selector"); #171 (web tool `set_bpm`).
- Values: #74's dropdown offered 80 to 180 BPM; #132 asks for validation against a reasonable range without giving one.
- Judged: not stated.
- Outcome: changed later; #74 specified a dropdown, #132 added free entry, #137 removed the dropdown.
- Kind: HEURISTIC; numeric input.

## Playback/audio engine

### P1. Space and click start and stop audition
- Requirement: Space toggles playback of the region; clicking a segment plays that segment and a second click stops it.
- Area: playback/audio engine
- Evidence: #36 and #38 (space and click toggles); #56 "Do not play full audio if no segment is selected"; #127 (the click-again-to-stop behaviour regressed).
- Values: none.
- Judged: #56 says manual testing.
- Outcome: implemented; #38 said that with no markers the whole file plays and #56 contradicts that; #127 was closed as will-not-fix and folded into the engine rewrite #128. GUI removed by #164; terminal equivalents are the `/play` and `/loop` commands (#163).
- Kind: HEURISTIC; a small state machine.

### P2. Three global playback modes
- Requirement: Playback runs as one-shot, loop, or loop-and-reverse, and the mode applies to every segment.
- Area: playback/audio engine
- Evidence: #56 "Do not add per-segment playback modes"; #76 (loop-and-reverse used to imitate a known bassline).
- Values: default one-shot.
- Judged: manual testing (#56); listening (#76).
- Outcome: implemented. #175's goals list one-shot and loop only and do not mention loop-and-reverse.
- Kind: HEURISTIC; buffer ordering.

### P3. Keyboard keys trigger slices
- Requirement: Pressing a key plays the slice at that position, cutting off whatever was playing.
- Area: playback/audio engine
- Evidence: #146 (owner comment "works"); #163 (same mapping in the terminal); #171 (kept alongside the agent); #175 "Pressing slice key immediately cuts to new sound".
- Values: keys 1 to 9 play slices 1 to 9, 0 plays slice 10, q w e r t y u i o p play slices 11 to 20; an index with no slice is ignored.
- Judged: by playing (#146).
- Outcome: implemented and carried into every later interface. Inference: `r` was the clear-markers key in #10, which conflicts with slice 14.
- Kind: HEURISTIC; lookup table.

### P4. Audition responds without audible delay or pops
- Requirement: A key press produces sound fast enough, and cleanly enough, that the tool can be played like an instrument.
- Area: playback/audio engine
- Evidence: #128 "this is working but has performance issues."; #148 "audio pops and latency issues that make the tool unmusical"; #175 (ring-buffer rewrite); #176 "No audible clicks or gaps under expected use".
- Values: #128 targets: latency between segments below 10 ms, CPU under 10 %, block size 512 frames, 44100 Hz, 2 channels. #148 accepts about 100 ms for a stream restart on tempo change. #175 defaults: block size 256 frames, ring buffer 250 ms, low watermark 50 ms, high watermark 150 ms.
- Judged: listening and playing by the owner; #176 adds tests that run without audio hardware.
- Outcome: rewritten twice (#128, then #148 after the owner's verdict); a third rewrite, #175, is still open.
- Kind: HEURISTIC for the engine structure, which #176 specifies as tests; whether it feels playable is HUMAN.

### P5. One voice, hard cut on retrigger
- Requirement: A new trigger replaces the current sound at once; voices never overlap.
- Area: playback/audio engine
- Evidence: #175 "Hard-cut semantics with short configurable fade-in (anti-click)"; #176 (test: old audio does not leak into output).
- Values: fade-in 3 ms default (#175); #176 writes "3–5 ms".
- Judged: tests on rendered output (#176).
- Outcome: still open. #146 already stopped the current segment when a new key was pressed.
- Kind: HEURISTIC; buffer clear plus ramp.

### P6. A sequence of slices loops without gaps
- Requirement: The user names an ordered list of slices and hears it repeat with no silence between slices or at the loop point.
- Area: playback/audio engine
- Evidence: #163 (`/play [1,q,2,w]` and `/loop`); #175 "Gapless looping"; #176 (boundaries sample-accurate); #155 (loop stalled after about 3 passes).
- Values: example `/loop [4,8,2,9]`.
- Judged: tests comparing rendered samples (#176); listening.
- Outcome: implemented in the terminal interface (#163); the gapless guarantee is part of open #175.
- Kind: HEURISTIC; concatenation.

### P7. Clicks at slice edges are removed with a short fade
- Requirement: A slice does not click at its start or end, in audition and in exported files, and the fade does not change slice timing.
- Area: playback/audio engine
- Evidence: #8 (title: fade to zero to "avoid clicks at end"); #39 "Must not alter timing or sequencing"; #80 (tail fade in the export chain); #151 "replacing the current fixed 2ms fade"; #175 (fade-in and tail fade defaults).
- Values: #8: a slider in samples. #39: 0 to 20 ms, default 5 ms, linear by default. #80: 10 ms exponential. #151: fixed 2 ms exponential in the code at that time; proposed dial 0 to 100 ms. #175: fade-in 3 ms, tail fade 3 ms, exponential.
- Judged: listening for clicks; #176 adds a ramp-shape test.
- Outcome: changed repeatedly. #8 replaced by #39; #39 closed as a duplicate on 2025-05-25; #151 abandoned at the web pivot; #175 open.
- Kind: HEURISTIC for applying a fade; the length and curve are HUMAN (five different values and no measurement in the issues).

### P8. Fade amount is global or per slice
- Requirement: One fade setting applies to all slices (#39), or each slice can override a global default (#151).
- Area: playback/audio engine
- Evidence: #39 (global only, no per-slice fade); #151 (per-segment override; the fade drawn on the waveform must match what plays).
- Values: see P7.
- Judged: looking and listening (#151 asks that playback match the drawn fade curve).
- Outcome: abandoned; #151 reversed #39 on paper and neither shipped as specified. #175 has global values only.
- Kind: unsure; the two issues disagree and neither was built.

### P9. The engine runs at one fixed format
- Requirement: All audio is played as 44.1 kHz stereo float; mono files are duplicated to both channels at unchanged level.
- Area: playback/audio engine
- Evidence: #175 "Mono samples play at correct loudness when duplicated to stereo"; #176 (no gain change on duplication); #182 (a 48000 Hz preset was deleted as unsupported).
- Values: 44100 Hz, 2 channels, float32.
- Judged: tests (#176).
- Outcome: still open for the engine; #182 shows the 44100 Hz restriction already applied on 2025-12-30. #34 had asked for other sample rates to be handled.
- Kind: HEURISTIC; format conversion.

### P10. Playback fails quietly and repeats exactly
- Requirement: If audio data runs short the output is silence and playback continues; the same commands give bit-identical output on every run.
- Area: playback/audio engine
- Evidence: #176 "Output audio is bit-identical across runs"; #175 (underrun policy).
- Values: underrun policy "silence".
- Judged: tests (#176).
- Outcome: still open.
- Kind: HEURISTIC; deterministic buffer logic.

### P11. A sequencer of slice patterns follows a host clock
- Requirement: The pattern sequencer starts, stops and keeps tempo with a DAW over MIDI clock, with hits landing on the host grid.
- Area: playback/audio engine
- Evidence: #184 "Tracker hits sit on the DAW grid within a couple ms over a 4-bar bounce comparison."
- Values: 24 clock ticks per quarter note; a step every 12 ticks at eighth notes, every 6 at sixteenths.
- Judged: comparing a recorded 4-bar bounce against the grid; no clicks at start.
- Outcome: still open.
- Kind: HEURISTIC; clock following with a stated tolerance.

## Time-stretch/pitch

### R1. Tempo changes by resampling, with pitch following
- Requirement: Changing tempo speeds up or slows down the audio as an old sampler does, so pitch moves with it; there is no independent pitch or time control.
- Area: time-stretch/pitch
- Evidence: #74 "RCY will not support independent pitch/tempo adjustment"; #80 "Avoid time-stretching; preserve pitch shift via sample rate change"; #45 (time-stretch emulation code removed); #175 (S1000-style sample-rate change).
- Values: ratio = target BPM ÷ source BPM; #74 expects natural sound within about ±20 %.
- Judged: listening ("sounds natural", #74); #74 also records that there was no clear way to test it.
- Outcome: implemented. #74's first draft offered independent pitch and tempo and the owner's clarification removed it. Two loose ends: #148's body describes export as keeping original pitch at the new tempo, which contradicts #74 and #80, and #171 lists a tempo-stretching tool as a future item.
- Kind: HEURISTIC; rate conversion. The acceptable range is HUMAN.

### R2. Tempo cannot change during playback
- Requirement: A tempo change is accepted only while stopped; during playback it is refused or deferred with a message.
- Area: time-stretch/pitch
- Evidence: #175 (tempo: only allowed when stopped; mid-play tempo change is a non-goal); #176 (test for rejection).
- Values: none.
- Judged: tests (#176).
- Outcome: still open. Earlier, #155 discussed tempo changing as markers move during a loop.
- Kind: HEURISTIC; guard on state.

## Export formats

### X1. Exported slices match what was auditioned
- Requirement: Exported WAV slices have the tempo change and tail fade applied, exactly as heard, with no option to leave either off.
- Area: export formats
- Evidence: #74 "Export will use original tempo"; #79 (title "Export Slices with Pitch-Shifted Playback Applied"); #80 "Exported audio = what you hear".
- Values: export resampled to 44100 Hz; order slice, tempo, tail fade; example target 165 BPM (#80).
- Judged: #80 proposes comparing rendered files to stored reference fingerprints; #148 reports 22 tests.
- Outcome: changed later; #74 said export ignores tempo, #79 and #80, opened about seven hours later on the same day (2025-04-13), reversed that. #148 then split audition (no resampling, device rate changed) from export (resampled), so the two paths are no longer the same code.
- Kind: HEURISTIC; a fixed chain with file-level checks.

### X2. An SFZ instrument maps the slices to keys
- Requirement: Export writes an SFZ file that loads in other samplers on another machine.
- Area: export formats
- Evidence: #92 (SFZ generator from a folder of WAVs, configurable first key); #94 (paths relative, no user names in paths, loads in TAL Sampler).
- Values: `default_path` set in the control section.
- Judged: by loading in a sampler (#94).
- Outcome: implemented.
- Kind: HEURISTIC; text format.

### X3. A MIDI file replays the break from the slices
- Requirement: Export writes a MIDI file whose notes trigger the slices in order, cover the whole timeline without gaps, and use the adjusted tempo when tempo adjustment is on.
- Area: export formats
- Evidence: #7 (MIDI file that plays the generated instrument over the bars); #119 (MIDI ignored the tempo setting); #120 "Segment 1 should end exactly when segment 2 begins (minus 1 sample)"; #126 "inherently broken as it creates undesirable gaps between MIDI notes".
- Values: gaps of 498.83 ms were measured in #120; #119 example 160 BPM against a 120 BPM source.
- Judged: by inspecting the exported file (#119, #120); count check in #117.
- Outcome: implemented; #120 added a continuous timing mode beside the original one and #126 deleted the original.
- Kind: HEURISTIC; note timing arithmetic.

### X4. Export files are named after the export folder
- Requirement: Exporting to a folder named foo produces foo.sfz and foo.mid, and the user is told what was written.
- Area: export formats
- Evidence: #123 (naming and completion feedback).
- Values: previous fixed names were instrument.sfz and sequence.mid.
- Judged: file check.
- Outcome: implemented; the completion dialog was a desktop GUI element, GUI removed by #164.
- Kind: HEURISTIC; naming rule.

### X5. Slice layouts can be loaded from SFZ
- Requirement: An existing SFZ file, including the per-producer layouts shipped with a preset, can be opened to get its slice points.
- Area: export formats
- Evidence: #9 (load an SFZ file); #19 (preset loads WAV and SFZ slice points); #174 (the shipped SFZ files exist but nothing references them).
- Values: none.
- Judged: not stated.
- Outcome: #9 and #19 closed as completed; by #174 the SFZ layouts were unused. Carry-over not stated.
- Kind: HEURISTIC; parser.

## Sampler hardware

No issue mentions the S2800 or the MPC2000XL (a search of all issue text for those names returns nothing); hardware issues cover the EP-133 only, plus one abandoned plan for hardware controllers.

### H1. Slices upload to the EP-133 and land on pads
- Requirement: The user sends slices to numbered sound slots on the EP-133 and assigns them to pads, and a batch of uploads completes without errors.
- Area: sampler hardware
- Evidence: #177 (upload fails without a pause between chunks); #183 (upload failed on the second slice); #166 (bank argument A, B, C, D); #171 (upload and assign tools).
- Values: 20 ms pause between SysEx chunks; before about 80 % of batch uploads failed, after 12 of 12 succeeded (#177). Slots 1 to 999 (#171).
- Judged: on the device: 12 slices uploaded and assigned in a row (#177, #183).
- Outcome: implemented; #177 is still open although its text says the fix is in.
- Kind: HEURISTIC; protocol timing found by trial on the device.

### H2. The device and its own editor stay in step after bulk work
- Requirement: After an upload or clear, the EP-133's state is refreshed so other tools show the new contents without a manual reload.
- Area: sampler hardware
- Evidence: #173 (sync after long operations).
- Values: none.
- Judged: by looking at the vendor's sample tool.
- Outcome: implemented.
- Kind: HEURISTIC; one protocol call.

### H3. Long device operations show progress
- Requirement: While a multi-slice upload runs, the interface shows that it is running and how far it has got.
- Area: sampler hardware
- Evidence: #172 (no feedback while uploading 12 segments).
- Values: none.
- Judged: looking.
- Outcome: still open.
- Kind: HEURISTIC; progress callback.

### H4. A full EP-133 librarian in the terminal
- Requirement: Browse, upload, download, rename and delete samples; edit pad assignments; back up and restore projects, all offline.
- Area: sampler hardware
- Evidence: #179 (full feature specification).
- Values: 10 banks of 100 slots; 9 projects; 4 groups × 12 pads; 64 MB memory; 12 to 20 items on screen at once; confirm before delete.
- Judged: not stated.
- Outcome: still open.
- Kind: HEURISTIC for the operations; the screen layout limits are HUMAN preferences stated as numbers.

### H5. Hardware controllers drive the app over OSC
- Requirement: The interface becomes a client of an audio server so that hardware controllers can trigger it.
- Area: sampler hardware
- Evidence: #129 "Support hardware controllers like MPC".
- Values: none.
- Judged: not stated.
- Outcome: abandoned; closed with a pointer to the analysis in #128, which chose an in-process audio stream instead.
- Kind: unsure; never specified beyond the goal.

## UI/keys/layout

### U1. Shape of the start and end marker handles
- Requirement: The start and end markers have a grab handle at the bottom whose shape shows it is draggable and which keeps a fixed size on screen.
- Area: UI/keys/layout
- Evidence: #26 (triangles); #29, #30 (sizes moved to config); #51 "looks great."; #91 "Please revert to rectangular handles for now."; #154 (triangles again).
- Values: #26: 10 px × 6 px. #29/#30: 16 × 10, then 20 × 12 with 2 px offset. #91: rectangle 8 px × 14 px. #154: equilateral triangle, colour #003366, placed in pixels from the bottom of the plot, never outside the waveform area.
- Judged: looking, by the owner, each time.
- Outcome: changed four times, then abandoned: #154 closed at the web pivot and the GUI was removed by #164.
- Kind: HUMAN; every change was a visual verdict.

### U2. Colours and type
- Requirement: The interface uses a defined palette and typeface, and start and end markers are told apart by shape, not colour.
- Area: UI/keys/layout
- Evidence: #10 (green start, red end); #21 "remove the red/green affordance and rely on shape + icon"; #156 (flat design, different fonts); #178 (terminal skins).
- Values: #21: marker colour #007fa3, interaction colour #ff3366, typeface Futura PT Book. #156 names Inter or Roboto. #178 ships skins named default, high-contrast, monochrome, hacienda.
- Judged: looking.
- Outcome: #21 replaced #10's colours; #156 abandoned; #178 implemented for the terminal with runtime switching (`/skin`).
- Kind: HUMAN; palette choice. Loading a skin file is HEURISTIC.

### U3. Markers are easy to grab
- Requirement: A marker can be picked up without pixel-precise aim, and all markers look the same width.
- Area: UI/keys/layout
- Evidence: #14 (title "Update width of start/end markers to match segment markers").
- Values: line width 2 to 1; grab zone 2 % to 5 % of the visible width.
- Judged: not stated.
- Outcome: implemented in the desktop GUI, GUI removed by #164; the terminal uses focus and nudge (S9).
- Kind: HEURISTIC; hit-test tolerance, with the value a HUMAN preference.

### U4. Zoom into the waveform
- Requirement: The user can zoom the time axis in and out around the area of interest while the amplitude axis stays fixed.
- Area: UI/keys/layout
- Evidence: #4 "this sort of works but not really. needs help."; #27 (zoom specification); #156 (pinch and wheel zoom).
- Values: #27: step ×1.25, limits 0.5× to 10×, amplitude fixed at −1 to 1.
- Judged: by use (#4).
- Outcome: abandoned. The #27 attempt was backed out over a circular update between view and controller, #144 restructured for it, and #27 closed at the web pivot.
- Kind: HEURISTIC; view arithmetic.

### U5. The playing segment is highlighted
- Requirement: The segment being played is shaded briefly so the user sees what they triggered.
- Area: UI/keys/layout
- Evidence: #60 (title "Highlight Active Segment on Click"); #146 (highlight on key trigger).
- Values: colour #cccccc at 0.25 opacity, fade out over 250 ms.
- Judged: looking.
- Outcome: implemented in the desktop GUI, GUI removed by #164, carry-over not stated.
- Kind: HEURISTIC; the values are HUMAN preferences.

### U6. Wording and on-screen clutter
- Requirement: The interface says "measures", hides tooltips in the main window, lists shortcuts in a Help menu, and does not show a separate source-tempo panel.
- Area: UI/keys/layout
- Evidence: #42 (title "Use 'Measures' Instead of 'Bars' Consistently in UI and Code"); #12 (tooltips, Help menu); #110 (remove the Source window).
- Values: none.
- Judged: looking.
- Outcome: implemented. Later terminal issues use "bar" again (#169's `/marker` takes bar.beat and defines bar as measure).
- Kind: HUMAN; naming and layout preference.

### U7. Marker lines are continuous across stereo channels
- Requirement: In a stereo file one marker line runs through both channels and both halves move together.
- Area: UI/keys/layout
- Evidence: #154 (continuous line through left and right); #157 (right-channel markers did not follow when dragged).
- Values: 2 marker objects instead of 4.
- Judged: looking.
- Outcome: abandoned at the web pivot.
- Kind: HEURISTIC; drawing structure.

### U8. Pointer and playhead lines
- Requirement: A line follows the mouse with a time readout, and a moving line shows the playback position.
- Area: UI/keys/layout
- Evidence: #161 (cursor and playback position indicators); #156 (playback cursor).
- Values: time shown as 0:00.000.
- Judged: looking.
- Outcome: abandoned at the web pivot.
- Kind: HEURISTIC; drawing.

### U9. The waveform stays responsive on long files
- Requirement: Drawing and marker dragging stay smooth, using a reduced display copy while slicing and playback use full-resolution audio.
- Area: UI/keys/layout
- Evidence: #62 (move off Matplotlib for speed); #63 (downsampled view); #68 (Matplotlib removed).
- Values: display reduced to about 2000 points; tested on files over 1 M samples (agent report).
- Judged: by feel while dragging (#62 cites sluggish markers).
- Outcome: implemented in the desktop GUI, GUI removed by #164.
- Kind: HEURISTIC; min-max decimation.

### U10. Which interface the tool has
- Requirement: The tool has one interface at a time: desktop GUI first, then terminal only, with a browser version proposed.
- Area: UI/keys/layout
- Evidence: #164 "TUI is the active development focus"; #171 (browser port with agent, Web MIDI, Web Audio).
- Values: #171 estimates 8 weeks.
- Judged: not stated.
- Outcome: GUI removed 2025-12-04; #171 opened 2025-12-07 and still open. Issues after #171 (#172 to #183) keep working on the terminal interface and #184, #185 describe a separate Go tracker, so the web port has no implementation issue.
- Kind: HUMAN; a direction decision.

### U11. Commands are typed, with completion
- Requirement: Every operation is a slash command with short aliases, and Tab completes command names and arguments such as preset names.
- Area: UI/keys/layout
- Evidence: #163 (command dispatcher, aliases); #166 (tab completion).
- Values: `/pre` then Tab gives `/preset`; completion only in insert mode.
- Judged: unit tests (#163 reports 39).
- Outcome: implemented.
- Kind: HEURISTIC; prefix matching.

### U12. Plain-language control through a model
- Requirement: The user can type a request in ordinary words and a language model carries it out by calling the same commands.
- Area: UI/keys/layout
- Evidence: #163 (optional model-backed agents); #171 "LLM agent as a first-class feature".
- Values: the default agent needs no model or key (#163).
- Judged: not stated.
- Outcome: the tool registry and the no-model dispatcher shipped in #163; model-backed agents were listed as examples; #171 open.
- Kind: AGENT; the issues assign it to a model.

### U13. The terminal screen starts clean
- Requirement: Nothing is printed to the terminal before the interface draws.
- Area: UI/keys/layout
- Evidence: #180 (a stray "p" appeared at launch).
- Values: none.
- Judged: looking.
- Outcome: implemented by starting the audio device before the terminal UI.
- Kind: HEURISTIC; start-up ordering.

### U14. Pattern banks and scenes in the tracker
- Requirement: Each track holds several patterns, a scene stores which pattern each track plays, and switching either takes effect at the next bar.
- Area: UI/keys/layout
- Evidence: #185 "This is the Octatrack / MPC model, not Ableton clip slots".
- Values: up/down changes the pattern on the current track; Shift+up/down changes scene; `s` saves the active pattern only; example 172 BPM, 8 steps per bar.
- Judged: acceptance list in #185, checked by playing.
- Outcome: still open. Whether next-bar switching "feels right" is listed as a research question.
- Kind: HEURISTIC for the data model; swap timing is HUMAN by the issue's own wording.

### U15. Design overhaul wish list
- Requirement: A long list of interface additions: snapping markers to hits or a rhythm grid, tooltips with times, segment names and colours, a segment sidebar, tap tempo, grid overlay, dark mode.
- Area: UI/keys/layout
- Evidence: #156 (epic).
- Values: grid at eighths, triplets, sixteenths.
- Judged: #156 lists "Positive user feedback" as a criterion.
- Outcome: abandoned at the web pivot. Later terminal work covered two items independently: skins (#178) and a typed command line (#163).
- Kind: unsure; a list without acceptance detail.

## Config/presets

### C1. The app opens on a real break
- Requirement: On launch the Amen break is loaded and ready to slice.
- Area: config/presets
- Evidence: #16 (title "Initialize with Amen break audio instead of white noise").
- Values: none.
- Judged: looking and listening.
- Outcome: implemented.
- Kind: HEURISTIC; default value.

### C2. Bundled breaks are curated, with history
- Requirement: The tool ships a small set of classic breaks with notes and producer-style slice layouts, kept apart from bulk sample packs.
- Area: config/presets
- Evidence: #18 "Most samplers and tools are agnostic. RCY isn't. It has a point of view."; #19 (Presets menu); #174 "Core presets never overwritten by generators"; #182 (Think break removed).
- Values: 5 curated presets and 899 generated ones (#174).
- Judged: owner's choice of material.
- Outcome: implemented; the Think break preset was deleted in #182, and by #174 the producer-style layouts were unused files.
- Kind: HUMAN; curation.

### C3. A missing preset or config value stops with a message
- Requirement: If preset data or a required setting is absent, the tool reports it and does not substitute a built-in value.
- Area: config/presets
- Evidence: #32 "If presets is not found, error gracefully with message. do not try to hardcode defaults."; #174 (duplicate preset ID raises an error).
- Values: none.
- Judged: not stated.
- Outcome: implemented.
- Kind: HEURISTIC; explicit failure.

### C4. Opening a preset and importing audio are different actions
- Requirement: Open restores a saved session exactly; Import brings in raw audio with a fresh state and nothing carried over from the previous file.
- Area: config/presets
- Evidence: #84 "This behavior violates the principle of WYSIWYG and creates implicit state carryover between unrelated sessions."
- Values: the defect case was a 6.97 s duration kept from the previous file.
- Judged: not stated.
- Outcome: closed as completed. Session saving itself is still open as S11.
- Kind: HEURISTIC; state reset.

### C5. Mono, stereo and sample-rate handling of source files
- Requirement: Files of either channel count load correctly; the user can reduce stereo to its left or right channel.
- Area: config/presets
- Evidence: #34 (handle different sample rates and channel counts); #90 (stereo to mono by channel); #159 (mono test presets); #182 "Remove the preset entirely rather than converting it."
- Values: 44100 Hz required as of #182.
- Judged: #159 exists to test mono paths.
- Outcome: #34 closed as completed; #90 abandoned at the web pivot; #182 shows other sample rates are not supported.
- Kind: HEURISTIC; channel and rate conversion.

### C6. Tunable values live in config files, read-only at run time
- Requirement: Strings, handle sizes, detection parameters and playback defaults come from JSON config, and the running app does not write changes back.
- Area: config/presets
- Evidence: #24 (strings file); #29, #30 (handle sizes); #58 (detection); #108 (one merged config file); #56 "Do not write runtime changes back to config".
- Values: see T2 and U1.
- Judged: not stated.
- Outcome: implemented; file layout changed again in #174 (presets split into one file per source).
- Kind: HEURISTIC; config loading.

## Tooling/dev process

### D1. Code fails loudly and is not aware of tests
- Requirement: Missing methods and missing config raise errors, and production code contains no branches that detect a test environment.
- Area: tooling/dev process
- Evidence: #112 (remove `hasattr` guards); #130 (owner rejects environment-aware code as an anti-pattern; dependencies are passed in); #140 (config manager takes its paths as arguments).
- Values: none.
- Judged: code review.
- Outcome: implemented.
- Kind: HEURISTIC; a coding rule.

### D2. Tests fix behaviour, and the implementer may not bend them
- Requirement: Engine tests describe intended behaviour, run without sound hardware, and a failing test is fixed in the engine.
- Area: tooling/dev process
- Evidence: #176 "Do not change semantics to make tests pass."
- Values: none.
- Judged: test run.
- Outcome: still open with #175.
- Kind: HEURISTIC; process rule. The same issue says the tests should catch output that sounds wrong, which no listed test measures.

## Reversals

1. Export and tempo. #74 (owner's clarification): export keeps the original tempo. #79 and #80, opened the same day (2025-04-13): export must equal what is heard, tempo change included, with no switch. #148 then separated the audition path from the export path again for speed.
2. Independent pitch and tempo. #74's first draft offered both; the clarification in the same issue ruled them out. #45 had already deleted time-stretch emulation as no longer strategic. #171 lists tempo stretching as a future tool.
3. Marker handle shape. Triangle (#26), directional triangle approved in #51 "looks great.", rectangle on request (#91), equilateral triangle (#154), then dropped with the GUI.
4. Marker colours. Green start and red end (#10) became one colour for both with shape as the cue (#21).
5. Start and end markers. Optional and clearable (#10) became always present (#52).
6. Fade scope and length. Slider in samples (#8), global 0 to 20 ms knob with no per-slice setting (#39), per-slice override on a 0 to 100 ms dial (#151), global 3 ms defaults (#175). None of the first three shipped as written.
7. Tempo entry. Dropdown of 80 to 180 BPM (#74) became a text field (#132, #137).
8. MIDI timing. Original timing mode kept beside a continuous mode (#120), then deleted (#126).
9. Playback with nothing selected. Whole file plays (#38), against #56 "Do not play full audio if no segment is selected".
10. Marker add and delete gestures. Alt+click and Alt+Cmd+click, then Ctrl+click and Ctrl+Option+click (#69), a hover control (#59, never built), then focus plus DEL in the terminal (#167, #168).
11. Interface. Desktop GUI, then terminal only (#164), then a browser port declared the new direction (#171) while twelve issues were closed against it; work after that date stayed in the terminal.
12. Audio engine. Blocking playback, then a callback engine (#128), then a second path that bypasses processing for audition (#148), then a ring-buffer rewrite still open (#175). An OSC server design (#129) was dropped along the way.
13. Sample rates. #34 asked for varied rates to be handled; #182 deleted a 48000 Hz preset because only 44100 Hz is supported.
14. Think break. Shipped as a curated preset (#18, #77 fixed its tempo) and removed in #182.
15. Wording. "Measures" enforced over "bars" (#42); the terminal `/marker` command and `/set bars` speak of bars again (#169).

## Recurring pain

- Tempo arithmetic: #49, #77, #131, #135, #138, #158 are all the same quantity computed from the wrong length, the wrong measure count, or with a side effect on a switch. #135 was caused by the fix for #131.
- First and last segment: #1, #61, #86, #116. The implicit boundaries at file start and end were missed by playback, then by click handling, then by export, then by the segment count.
- Clicks and pops at slice edges: #8, #39, #80, #148, #151, #175, #176. Five different fade lengths appear and the open engine issue still lists anti-click fades as a goal.
- Audition latency and stability: #127, #128, #148, #155, #175. Two engine rewrites closed and a third is open.
- Drawing-library coupling: zoom (#4, #27, #144), handles (#35, #91, #154), stereo marker lines (#157) and Cut (#82) each broke or stalled on the desktop drawing layer before it was removed.
- EP-133 transfers: #177 and #183 are both batch-upload failures traced to device timing and unsolicited messages; #173 is a side effect of the same MIDI layer.

## Cutting position relative to the drum hit

What the issues say:

- Slice boundaries sit at detected hit positions, at even musical divisions, or where the user puts them (T1, S7, S2). #1 says the first slice needs a marker at zero.
- `docs/breakbeat-science.md` (#40) names three ways to cut: by grid ("Chop the loop by **time**, not transients"), by hand where it sounds right, and by loading another producer's slice layout. Automatic hit detection is not one of the three.
- The terminal `/marker` command places a cut on the tempo grid, not on a hit (#169). Snapping a dragged marker to the nearest hit was a wish in #156 and was never built.
- No issue says whether a cut should fall before, on, or after the onset of a hit. No issue specifies a pre-roll or look-back from a detected onset.
- Zero crossings appear once. #151 "natural zero crossings inadequate" gives the reason they are not relied on: breaks with cymbals and overlapping hits have no clean crossing near the cut. No issue asks for snapping cuts to zero crossings.
- Clicks are handled by fades, not by moving the cut. Tail fade: samples slider (#8), 5 ms default (#39), 10 ms exponential in export (#80), 2 ms exponential fixed in code (#151), 3 ms (#175). Fade-in at slice start appears only in #175 and #176, at 3 ms, with "3–5 ms" in the test text.
- Fades must not move anything in time: #39 "Must not alter timing or sequencing".
- Tails: a slice runs to the next boundary. In MIDI export each note lasts until the next begins (#120). In audition a new trigger cuts the previous slice off (#175, P5); there is no overlap or release tail.
- Loops join slices with no gap and sample-accurate boundaries (#176).
- Fine placement is by ear: markers are nudged in 100-sample steps (#167) while a loop plays (#155), and #73 puts chop choice with the person.

Inference: because the issues leave onset-relative placement unspecified and settle fade length by repeated change, a rebuild has no stated rule to copy for either; both are open parameters.

## Issues about dev process or tooling only

- #40: add the breakbeat-science document to docs.
- #57: review the segments and markers design document.
- #87: hand-off workflow for a junior coding agent on docs and hygiene tasks.
- #88: GitHub organisation roles for that two-level workflow.
- #89: extend CLAUDE.md with guidance for the second-level role.
- #96: remove debugging code and simplify marker handling.
- #97: runtime instrumentation layer for agent debugging; closed as not part of the project.
- #98: errors printed to stdout without modal dialogs, so an agent can read them.
- #99: route errors through one handler; closed at the web pivot.
- #100: session logger; closed in favour of piping output through tee.
- #101: guide file for a second coding agent.
- #102: remove debug code from the waveform view.
- #103: reduce duplication in marker handle methods; closed at the web pivot.
- #104: simplify bounds checking in the controller.
- #105: standardise error handling in the audio processor.
- #107: static typing with mypy; closed at the web pivot.
- #108: merge config JSON files into one.
- #112: remove `hasattr` guards (also D1).
- #121: application name in the macOS menu; closed as will not do.
- #122: macOS app bundle; closed at the web pivot.
- #130: test layout and dependency injection (also D1).
- #140: config manager testability (also D1).
- #144: restructure view and controller to one-way data flow.
- #159: mono presets for testing.
- #174: split the preset catalogue into one file per source.
- #181: separate preset loading from audio engine construction.

## Issues with no behaviour content beyond the above

- #35: a stray triangle drawn in the corner; a drawing defect of the handle work in U1.
- #73, #76: workflow trials on a named record. Their one behavioural statement is T3; the rest is a log of the trial.
- #138: a record of fixes already committed, covered by M1.
