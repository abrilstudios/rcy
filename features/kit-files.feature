Feature: the files of a kit

  @R13
  Scenario: sfz-files-dialect
    One region per slice WAV, newline separated, with no final newline.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "text", "file": "kit/kit.sfz", "lines": 4, "final_newline": false},
        {"event": "text_line", "file": "kit/kit.sfz", "index": 1, "text": "<region> sample=001.wav key=60"},
        {"event": "text_line", "file": "kit/kit.sfz", "index": 2, "text": "<region> sample=002.wav key=61"},
        {"event": "text_line", "file": "kit/kit.sfz", "index": 3, "text": "<region> sample=003.wav key=62"},
        {"event": "text_line", "file": "kit/kit.sfz", "index": 4, "text": "<region> sample=004.wav key=63"}
      ]
      """

  @R14
  Scenario: sfz-offsets-dialect
    Regions address the source by frame offsets, the end offset being the
    last frame played, and the slice WAV files are still written.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit", "--sfz-dialect", "offsets"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 4, "text": "sfz: $WORK/kit/kit.sfz (offsets)"},
        {"event": "text", "file": "kit/kit.sfz", "lines": 4, "final_newline": false},
        {"event": "text_line", "file": "kit/kit.sfz", "index": 1, "text": "<region> sample=../in.wav start=0 end=22049 key=60"},
        {"event": "text_line", "file": "kit/kit.sfz", "index": 4, "text": "<region> sample=../in.wav start=66150 end=88199 key=63"},
        {"event": "wav", "file": "kit/004.wav", "frames": 22050}
      ]
      """

  @R15
  Scenario: midi-replays-the-slices-in-order
    Format 1, 960 ticks per quarter note, tempo and 4/4 in the first track,
    one note per slice in the second.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "midi", "file": "kit/kit.mid", "format": 1, "tracks": 2, "division": 960},
        {"event": "midi_event", "track": 0, "tick": 0, "kind": "tempo", "microseconds": 500000},
        {"event": "midi_event", "track": 0, "tick": 0, "kind": "time_signature", "numerator": 4, "denominator": 4},
        {"event": "midi_event", "track": 1, "tick": 0, "kind": "note_on", "channel": 0, "key": 60, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 960, "kind": "note_off", "channel": 0, "key": 60},
        {"event": "midi_event", "track": 1, "tick": 960, "kind": "note_on", "channel": 0, "key": 61, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 2880, "kind": "note_on", "channel": 0, "key": 63, "velocity": 100},
        {"event": "midi_event", "track": 1, "tick": 3840, "kind": "note_off", "channel": 0, "key": 63},
        {"event": "midi_event", "track": 0, "kind": "end_of_track"},
        {"event": "midi_event", "track": 1, "kind": "end_of_track"}
      ]
      """
    And the recorded trace has these counts:
      """
      [
        {"match": {"event": "midi_event", "kind": "note_on"}, "equals": 4},
        {"match": {"event": "midi_event", "kind": "note_off"}, "equals": 4},
        {"match": {"event": "midi_event", "kind": "tempo"}, "equals": 1}
      ]
      """

  @R16 @R17
  Scenario: manifest-records-the-cut
    The manifest is two-space indented JSON with members in a fixed order,
    and one object per slice.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "json", "file": "kit/kit.rcy.json", "indent2": true,
         "keys": ["rcy", "source", "sample_rate", "channels", "bpm", "measures", "region", "boundaries", "slices"],
         "data.rcy": 1, "data.source": "../in.wav", "data.sample_rate": 44100, "data.channels": 1,
         "data.slices.length": 4,
         "data.slices.0": {"index": 1, "start": 0, "end": 22050, "key": 60, "file": "001.wav", "role": ""},
         "data.slices.3": {"index": 4, "start": 66150, "end": 88200, "key": 63, "file": "004.wav", "role": ""}},
        {"event": "text_line", "file": "kit/kit.rcy.json", "index": 6, "text": "  \"bpm\": 120.0,"},
        {"event": "text_line", "file": "kit/kit.rcy.json", "index": 9, "text": "    \"start\": 0,"},
        {"event": "text_line", "file": "kit/kit.rcy.json", "index": 13, "text": "    0,"},
        {"event": "text_line", "file": "kit/kit.rcy.json", "index": 21, "text": "      \"index\": 1,"},
        {"event": "text_line", "file": "kit/kit.rcy.json", "index": 25, "text": "      \"file\": \"001.wav\","},
        {"event": "text_line", "file": "kit/kit.rcy.json", "index": 26, "text": "      \"role\": \"\""}
      ]
      """

  @R15 @baseline_red
  Scenario: midi-ticks-sit-on-the-grid-for-a-long-source
    1817184 frames as two measures of sixteenth notes: slice starts fall on
    multiples of 240 ticks, which a floor of floating-point products misses.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 1817184 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "2", "--resolution", "16", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "midi_event", "track": 0, "tick": 0, "kind": "tempo", "microseconds": 5150748},
        {"event": "midi_event", "track": 1, "tick": 240, "kind": "note_on", "key": 61},
        {"event": "midi_event", "track": 1, "tick": 720, "kind": "note_on", "key": 63},
        {"event": "midi_event", "track": 1, "tick": 720, "kind": "note_off", "key": 62},
        {"event": "midi_event", "track": 1, "tick": 7680, "kind": "note_off", "key": 91}
      ]
      """

  @R23
  Scenario: the-same-cut-twice-writes-identical-files
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "one" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "a/kit"]
    And the client runs the command as "two" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "b/kit"]
    And the observer compares the bytes of "a/kit/kit.mid" and "b/kit/kit.mid"
    And the observer compares the bytes of "a/kit/kit.rcy.json" and "b/kit/kit.rcy.json"
    And the observer compares the bytes of "a/kit/kit.sfz" and "b/kit/kit.sfz"
    And the observer compares the bytes of "a/kit/003.wav" and "b/kit/003.wav"
    Then the recorded trace has these counts:
      """
      [{"match": {"event": "files_compared", "equal": true}, "equals": 4}]
      """
