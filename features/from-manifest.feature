Feature: rebuild a kit from a manifest

  @R20 @R21 @R14 @R15
  Scenario: edited-manifest-rebuilds-the-kit
    Moving a boundary, renaming a slice, changing its key and role, and
    changing the tempo all carry into the rebuilt kit.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/edited.json" from "kit/kit.rcy.json" with:
      """
      {"boundaries.1": 20000, "bpm": 100.0, "slices.0.key": 36, "slices.0.file": "kick.wav", "slices.0.role": "kick"}
      """
    And the client runs the command as "rebuild" with arguments:
      """
      ["--from-manifest", "kit/edited.json", "--out", "kit2", "--sfz-dialect", "offsets", "--measures", "9", "--resolution", "9"]
      """
    And the observer reads the directory "kit2"
    And the observer compares "kit2/kick.wav" with frames 0 to 20000 of "in.wav"
    And the observer compares "kit2/002.wav" with frames 20000 to 44100 of "in.wav"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "rebuild", "code": 0, "stdout_lines": 6, "stderr_lines": 0},
        {"event": "output_line", "name": "rebuild", "stream": "stdout", "index": 1, "text": "source: $WORK/in.wav"},
        {"event": "output_line", "name": "rebuild", "stream": "stdout", "index": 2, "text": "tempo: 100.00 BPM (2 measures x 4)"},
        {"event": "output_line", "name": "rebuild", "stream": "stdout", "index": 3, "text": "slices: 8"},
        {"event": "directory", "dir": "kit2", "files": 11},
        {"event": "frames_compared", "file": "kit2/kick.wav", "equal": true},
        {"event": "frames_compared", "file": "kit2/002.wav", "equal": true},
        {"event": "json", "file": "kit2/kit2.rcy.json", "data.source": "../in.wav", "data.bpm": 100.0, "data.measures": 2,
         "data.slices.0": {"index": 1, "start": 0, "end": 20000, "key": 36, "file": "kick.wav", "role": "kick"},
         "data.slices.1": {"index": 2, "start": 20000, "end": 44100, "key": 61, "file": "002.wav", "role": ""}},
        {"event": "text_line", "file": "kit2/kit2.sfz", "index": 1, "text": "<region> sample=../in.wav start=0 end=19999 key=36 // kick"},
        {"event": "text_line", "file": "kit2/kit2.sfz", "index": 2, "text": "<region> sample=../in.wav start=20000 end=44099 key=61"},
        {"event": "midi_event", "track": 0, "tick": 0, "kind": "tempo", "microseconds": 600000},
        {"event": "midi_event", "track": 1, "tick": 0, "kind": "note_on", "key": 36, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 1600, "kind": "note_on", "key": 62, "velocity": 100}
      ]
      """

  @R15 @R21
  Scenario: midi-follows-the-manifest-order
    An order lists slice numbers in play order. A slice may fill several
    slots or none; the MIDI file lays the slots end to end from the region
    start, and the slice files are the same as without an order.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the client derives "kit/ordered.json" from "kit/kit.rcy.json" with:
      """
      {"order": [3, 1, 1]}
      """
    And the client runs the command as "rebuild" with arguments:
      """
      ["--from-manifest", "kit/ordered.json", "--out", "kit2"]
      """
    And the observer reads the directory "kit2"
    And the observer compares "kit2/001.wav" with frames 0 to 22050 of "in.wav"
    And the observer compares "kit2/003.wav" with frames 44100 to 66150 of "in.wav"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "rebuild", "code": 0, "stderr_lines": 0},
        {"event": "midi_event", "track": 1, "tick": 0, "kind": "note_on", "channel": 0, "key": 62, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 960, "kind": "note_off", "channel": 0, "key": 62},
        {"event": "midi_event", "track": 1, "tick": 960, "kind": "note_on", "channel": 0, "key": 60, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 1920, "kind": "note_off", "channel": 0, "key": 60},
        {"event": "midi_event", "track": 1, "tick": 1920, "kind": "note_on", "channel": 0, "key": 60, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 2880, "kind": "note_off", "channel": 0, "key": 60},
        {"event": "json", "file": "kit2/kit2.rcy.json", "data.order": [3, 1, 1]},
        {"event": "frames_compared", "file": "kit2/001.wav", "equal": true},
        {"event": "frames_compared", "file": "kit2/003.wav", "equal": true}
      ]
      """
    And the recorded trace has these counts:
      """
      [
        {"match": {"event": "midi_event", "kind": "note_on"}, "equals": 3},
        {"match": {"event": "file", "file": "kit2/004.wav"}, "equals": 1}
      ]
      """

  @R15 @baseline_red
  Scenario: midi-ticks-round-to-the-nearest-tick
    At 100 BPM frame 20000 is 725.6 ticks from the region start, so the first
    note ends and the second begins on tick 726; 70 BPM gives a tempo that
    floors to 857142 microseconds.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/edited.json" from "kit/kit.rcy.json" with:
      """
      {"boundaries.1": 20000, "bpm": 100.0}
      """
    And the client derives "kit/slow.json" from "kit/kit.rcy.json" setting bpm to 70
    And the client runs the command as "rebuild" with the arguments ["--from-manifest", "kit/edited.json", "--out", "kit2"]
    And the client runs the command as "slow" with the arguments ["--from-manifest", "kit/slow.json", "--out", "kit3"]
    And the observer reads the directory "kit2"
    And the observer reads the directory "kit3"
    Then the recorded trace contains:
      """
      [
        {"event": "midi_event", "file": "kit2/kit2.mid", "track": 1, "tick": 726, "kind": "note_off", "key": 60},
        {"event": "midi_event", "file": "kit2/kit2.mid", "track": 1, "tick": 726, "kind": "note_on", "key": 61},
        {"event": "midi_event", "file": "kit2/kit2.mid", "track": 1, "tick": 1600, "kind": "note_off", "key": 61},
        {"event": "midi_event", "file": "kit2/kit2.mid", "track": 1, "tick": 1600, "kind": "note_on", "key": 62},
        {"event": "midi_event", "file": "kit3/kit3.mid", "track": 0, "tick": 0, "kind": "tempo", "microseconds": 857142},
        {"event": "midi_event", "file": "kit3/kit3.mid", "track": 1, "tick": 560, "kind": "note_on", "key": 61}
      ]
      """

  @R18
  Scenario: report-prints-a-fractional-resolution-with-six-digits
    Eight slices over three measures.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/three.json" from "kit/kit.rcy.json" setting measures to 3
    And the client runs the command as "rebuild" with the arguments ["--from-manifest", "kit/three.json", "--out", "kit2"]
    Then the recorded trace contains:
      """
      [{"event": "output_line", "name": "rebuild", "stream": "stdout", "index": 2, "text": "tempo: 120.00 BPM (3 measures x 2.66667)"}]
      """

  @R20
  Scenario: output-defaults-to-the-manifest-directory
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/edited.json" from "kit/kit.rcy.json" setting slices.0.file to "kick.wav"
    And the client runs the command as "rebuild" with arguments:
      """
      ["-f", "kit/edited.json"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "rebuild", "code": 0},
        {"event": "output_line", "name": "rebuild", "stream": "stdout", "index": 6, "text": "manifest: $WORK/kit/kit.rcy.json"},
        {"event": "wav", "file": "kit/kick.wav", "frames": 22050},
        {"event": "json", "file": "kit/kit.rcy.json", "data.slices.0.file": "kick.wav"},
        {"event": "text_line", "file": "kit/kit.sfz", "index": 1, "text": "<region> sample=kick.wav key=60"}
      ]
      """

  @R18 @R21
  Scenario: hand-written-manifest-with-a-region-inside-the-source
    The region starts 1000 frames in; MIDI ticks count from the region start,
    slice extents come from the boundaries and the stored extents are ignored.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    And a file "m.json" containing:
      """
      {
        "rcy": 1, "source": "in.wav", "sample_rate": 44100, "channels": 1,
        "bpm": 120, "measures": 4,
        "region": {"start": 1000, "end": 45100},
        "boundaries": [1000, 23050, 45100],
        "slices": [
          {"index": 1, "start": 0, "end": 0, "key": 36, "file": "a.wav", "role": ""},
          {"index": 2, "start": 0, "end": 0, "key": 38, "file": "b.wav", "role": "snare"}
        ]
      }
      """
    When the client runs the command as "rebuild" with arguments:
      """
      ["--from-manifest", "m.json", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    And the observer compares "kit/a.wav" with frames 1000 to 23050 of "in.wav"
    And the observer compares "kit/b.wav" with frames 23050 to 45100 of "in.wav"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "rebuild", "code": 0},
        {"event": "output_line", "name": "rebuild", "stream": "stdout", "index": 2, "text": "tempo: 120.00 BPM (4 measures x 0.5)"},
        {"event": "directory", "dir": "kit", "files": 5},
        {"event": "frames_compared", "file": "kit/a.wav", "equal": true},
        {"event": "frames_compared", "file": "kit/b.wav", "equal": true},
        {"event": "json", "file": "kit/kit.rcy.json", "data.region": {"start": 1000, "end": 45100},
         "data.slices.1": {"index": 2, "start": 23050, "end": 45100, "key": 38, "file": "b.wav", "role": "snare"}},
        {"event": "text_line", "file": "kit/kit.sfz", "index": 2, "text": "<region> sample=b.wav key=38"},
        {"event": "midi_event", "track": 1, "tick": 0, "kind": "note_on", "key": 36, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 960, "kind": "note_on", "key": 38, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 1920, "kind": "note_off", "key": 38}
      ]
      """

  @R03 @R22
  Scenario Outline: manifest-refusal
    One member of a valid manifest is changed; the run names that defect.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/bad.json" from "kit/kit.rcy.json" setting <member> to <value>
    And the client runs the command as "refused" with arguments:
      """
      ["--from-manifest", "kit/bad.json", "--out", "kit2"]
      """
    And the observer reads the directory "kit2"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: <message>"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit2"}]
      """

    Examples:
      | member         | value     | message                                                                       |
      | rcy            | 2         | unsupported manifest version 2, expected 1                                    |
      | region         | 5         | region must be an object with start and end                                   |
      | slices         | 5         | slices must be a list                                                         |
      | boundaries     | "x"       | boundaries must be a list of integers                                         |
      | slices         | []        | 9 boundaries define 8 slices, but 0 slices are listed                         |
      | source         | ""        | source must be a non-empty path                                               |
      | sample_rate    | 0         | sample_rate must be positive, got 0                                           |
      | channels       | 3         | channels must be 1 or 2, got 3                                                |
      | bpm            | -1.5      | bpm must be a positive number, got -1.5                                       |
      | measures       | 0         | measures must be >= 1, got 0                                                  |
      | boundaries.2   | 10        | boundaries must be strictly increasing                                        |
      | boundaries.0   | 5         | boundaries must run from region start 0 to region end 176400, got 5..176400   |
      | slices.1.index | 7         | slice at position 2 has index 7; indices are 1-based and sequential           |
      | slices.1.key   | 128       | slice 2 key 128 is not a MIDI note (0..127)                                   |
      | slices.1.file  | ""        | slice 2 has an empty file name                                                |
      | slices.1.file  | "001.wav" | slice file '001.wav' is used by more than one slice                           |
      | sample_rate    | 48000     | manifest sample_rate 48000 != source 44100 ($WORK/in.wav)                     |
      | channels       | 2         | manifest channels 2 != source 1 ($WORK/in.wav)                                |
      | source         | 5          | source must be a string, got 5                    |
      | measures       | 2.5        | measures must be an integer, got 2.5              |
      | slices.0       | 5          | each slice must be a JSON object                  |
      | slices.1.file  | 7          | file must be a string, got 7                      |
      | slices.1.role  | 5          | slice role must be a string, got 5                |

  @R03 @R22 @R15 @baseline_red
  Scenario Outline: manifest-refusal-for-types-names-and-tempo
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/bad.json" from "kit/kit.rcy.json" setting <member> to <value>
    And the client runs the command as "refused" with arguments:
      """
      ["--from-manifest", "kit/bad.json", "--out", "kit2"]
      """
    And the observer reads the directory "kit2"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: <message>"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit2"}]
      """

    Examples:
      | member         | value      | message                                           |
      | measures       | true       | measures must be an integer, got true             |
      | sample_rate    | "x"        | sample_rate must be an integer, got "x"           |
      | region.start   | "a"        | start must be an integer, got "a"                 |
      | bpm            | "fast"     | bpm must be a number, got "fast"                  |
      | slices.1.key   | "60"       | key must be an integer, got "60"                  |
      | slices.1.file  | "a/b.wav"  | slice 2 file 'a/b.wav' must be a bare file name   |
      | slices.1.file  | ".."       | slice 2 file '..' must be a bare file name        |
      | order          | [0, 1]     | order must be a list of slice numbers from 1 to 8 |
      | order          | [9]        | order must be a list of slice numbers from 1 to 8 |
      | order          | []         | order must be a list of slice numbers from 1 to 8 |
      | order          | "2 1"      | order must be a list of slice numbers from 1 to 8 |
      | slices.1.file  | "kit2.sfz" | slice 2 file 'kit2.sfz' is a kit file name        |
      | slices.1.file  | "kit2.exs" | slice 2 file 'kit2.exs' is a kit file name        |
      | bpm            | 3          | tempo 3.00 BPM cannot be written to MIDI          |
      | bpm            | 70000000   | tempo 70000000.00 BPM cannot be written to MIDI   |

  @R22
  Scenario: manifest-refusal-names-the-first-defect
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/a.json" from "kit/kit.rcy.json" with:
      """
      {"rcy": 2, "region": 5}
      """
    And the client derives "kit/b.json" from "kit/kit.rcy.json" with:
      """
      {"sample_rate": 0, "channels": 3}
      """
    And the client derives "kit/c.json" from "kit/kit.rcy.json" with:
      """
      {"measures": 0, "slices.1.key": 128}
      """
    And the client runs the command as "a" with the arguments ["--from-manifest", "kit/a.json", "--out", "kit2"]
    And the client runs the command as "b" with the arguments ["--from-manifest", "kit/b.json", "--out", "kit2"]
    And the client runs the command as "c" with the arguments ["--from-manifest", "kit/c.json", "--out", "kit2"]
    Then the recorded trace contains:
      """
      [
        {"event": "output_line", "name": "a", "stream": "stderr", "index": 1, "text": "error: unsupported manifest version 2, expected 1"},
        {"event": "output_line", "name": "b", "stream": "stderr", "index": 1, "text": "error: sample_rate must be positive, got 0"},
        {"event": "output_line", "name": "c", "stream": "stderr", "index": 1, "text": "error: measures must be >= 1, got 0"}
      ]
      """

  @R22 @R04 @baseline_red
  Scenario: a-slice-file-cannot-replace-the-source
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/over.json" from "kit/kit.rcy.json" setting slices.1.file to "in.wav"
    And the client runs the command as "refused" with the arguments ["--from-manifest", "kit/over.json", "--out", "."]
    And the observer reads the directory "."
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: slice 2 file 'in.wav' would overwrite the source"
    And the recorded trace contains:
      """
      [{"event": "wav", "file": "in.wav", "frames": 176400}]
      """

  @R22
  Scenario: manifest-refusals-that-need-two-edits-or-none
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    And a file "list.json" containing:
      """
      [1]
      """
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/long.json" from "kit/kit.rcy.json" with:
      """
      {"region.end": 999999, "boundaries.8": 999999}
      """
    And the client derives "kit/short.json" from "kit/kit.rcy.json" with:
      """
      {"boundaries": [0], "slices": []}
      """
    And the client runs the command as "missing" with the arguments ["--from-manifest", "kit/none.json"]
    And the client runs the command as "list" with the arguments ["--from-manifest", "list.json", "--out", "kit2"]
    And the client runs the command as "long" with the arguments ["--from-manifest", "kit/long.json", "--out", "kit2"]
    And the client runs the command as "short" with the arguments ["--from-manifest", "kit/short.json", "--out", "kit2"]
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "missing", "code": 2, "stdout_lines": 0, "stderr_lines": 1},
        {"event": "output_line", "name": "missing", "stream": "stderr", "text": "error: manifest not found: kit/none.json"},
        {"event": "process_exit", "name": "list", "code": 2, "stdout_lines": 0, "stderr_lines": 1},
        {"event": "output_line", "name": "list", "stream": "stderr", "text": "error: manifest must be a JSON object"},
        {"event": "process_exit", "name": "long", "code": 2, "stdout_lines": 0, "stderr_lines": 1},
        {"event": "output_line", "name": "long", "stream": "stderr", "text": "error: region end 999999 exceeds source length 176400 ($WORK/in.wav)"},
        {"event": "process_exit", "name": "short", "code": 2, "stdout_lines": 0, "stderr_lines": 1},
        {"event": "output_line", "name": "short", "stream": "stderr", "text": "error: boundaries must hold at least the region start and end"}
      ]
      """

  @R22 @baseline_red
  Scenario: manifest-refusals-the-reference-reports-differently
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    And a file "bad.json" containing:
      """
      {nope
      """
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--out", "kit"]
      """
    And the client derives "kit/gone.json" from "kit/kit.rcy.json" setting source to "../gone.wav"
    And the client derives "kit/negative.json" from "kit/kit.rcy.json" with:
      """
      {"region.start": -5, "boundaries.0": -5}
      """
    And the client runs the command as "json" with the arguments ["--from-manifest", "bad.json", "--out", "kit2"]
    And the client runs the command as "gone" with the arguments ["--from-manifest", "kit/gone.json", "--out", "kit2"]
    And the client runs the command as "negative" with the arguments ["--from-manifest", "kit/negative.json", "--out", "kit2"]
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "json", "code": 2, "stdout_lines": 0, "stderr_lines": 1},
        {"event": "output_line", "name": "json", "stream": "stderr", "text": "error: bad.json: invalid JSON"},
        {"event": "process_exit", "name": "gone", "code": 2, "stdout_lines": 0, "stderr_lines": 1},
        {"event": "output_line", "name": "gone", "stream": "stderr", "text": "error: source audio not found: $WORK/gone.wav"},
        {"event": "process_exit", "name": "negative", "code": 2, "stdout_lines": 0, "stderr_lines": 1},
        {"event": "output_line", "name": "negative", "stream": "stderr", "text": "error: region start must be >= 0, got -5"}
      ]
      """
