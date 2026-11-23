Feature: cut a kit from a WAV file

  @R02 @R07 @R08 @R18
  Scenario: mono-source-quarter-notes
    A two-second mono source cut as one measure gives 120 BPM and four slices
    of 22050 frames, and the report names every file written.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "cut", "code": 0, "stdout_lines": 6, "stderr_lines": 0},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 1, "text": "source: $WORK/in.wav"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 2, "text": "tempo: 120.00 BPM (1 measures x 4)"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 3, "text": "slices: 4"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 4, "text": "sfz: $WORK/kit/kit.sfz (files)"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 5, "text": "midi: $WORK/kit/kit.mid"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 6, "text": "manifest: $WORK/kit/kit.rcy.json"},
        {"event": "json", "file": "kit/kit.rcy.json", "data.bpm": 120.0, "data.measures": 1,
         "data.boundaries": [0, 22050, 44100, 66150, 88200], "data.region": {"start": 0, "end": 88200}}
      ]
      """

  @R12 @R23
  Scenario: slice-files-hold-the-source-frames
    Each slice file has the source's format and exactly its own frames, and
    the output directory holds the slices and three named files only.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    And the observer compares "kit/001.wav" with frames 0 to 22050 of "in.wav"
    And the observer compares "kit/002.wav" with frames 22050 to 44100 of "in.wav"
    And the observer compares "kit/004.wav" with frames 66150 to 88200 of "in.wav"
    Then the recorded trace contains:
      """
      [
        {"event": "directory", "dir": "kit", "files": 7},
        {"event": "file", "file": "kit/kit.sfz"},
        {"event": "file", "file": "kit/kit.mid"},
        {"event": "file", "file": "kit/kit.rcy.json"},
        {"event": "wav", "file": "kit/001.wav", "channels": 1, "rate": 44100, "width": 16, "frames": 22050},
        {"event": "wav", "file": "kit/003.wav", "channels": 1, "rate": 44100, "width": 16, "frames": 22050},
        {"event": "frames_compared", "file": "kit/001.wav", "equal": true},
        {"event": "frames_compared", "file": "kit/002.wav", "equal": true},
        {"event": "frames_compared", "file": "kit/004.wav", "equal": true}
      ]
      """

  @R08 @R12
  Scenario: stereo-source-uneven-length
    A stereo source whose length is not a multiple of the slice count gets
    floor boundaries and stereo slices of differing lengths.

    Given a 2-channel 44100 Hz 16-bit WAV "in.wav" of 88203 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    And the observer compares "kit/002.wav" with frames 22050 to 44101 of "in.wav"
    And the observer compares "kit/004.wav" with frames 66152 to 88203 of "in.wav"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "cut", "code": 0},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 2, "text": "tempo: 120.00 BPM (1 measures x 4)"},
        {"event": "json", "file": "kit/kit.rcy.json", "data.channels": 2,
         "data.boundaries": [0, 22050, 44101, 66152, 88203]},
        {"event": "wav", "file": "kit/001.wav", "channels": 2, "rate": 44100, "width": 16, "frames": 22050},
        {"event": "wav", "file": "kit/002.wav", "channels": 2, "rate": 44100, "width": 16, "frames": 22051},
        {"event": "frames_compared", "file": "kit/002.wav", "equal": true},
        {"event": "frames_compared", "file": "kit/004.wav", "equal": true}
      ]
      """

  @R08 @baseline_red
  Scenario: boundaries-are-exact-integer-floors
    51999 frames in 7 slices: the last boundary is the source length, so the
    last slice keeps the source's final frame.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 51999 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--resolution", "7", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    And the observer compares "kit/007.wav" with frames 44570 to 51999 of "in.wav"
    Then the recorded trace contains:
      """
      [
        {"event": "json", "file": "kit/kit.rcy.json",
         "data.boundaries": [0, 7428, 14856, 22285, 29713, 37142, 44570, 51999]},
        {"event": "wav", "file": "kit/007.wav", "frames": 7429},
        {"event": "frames_compared", "file": "kit/007.wav", "equal": true}
      ]
      """

  @R02 @R08
  Scenario: resolution-and-short-options
    Two measures at two slices per measure, given with the short options.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 176400 frames
    When the client runs the command as "cut" with arguments:
      """
      ["-i", "in.wav", "-m", "2", "-r", "2", "-o", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 2, "text": "tempo: 120.00 BPM (2 measures x 2)"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 3, "text": "slices: 4"},
        {"event": "json", "file": "kit/kit.rcy.json", "data.boundaries": [0, 44100, 88200, 132300, 176400]},
        {"event": "text", "file": "kit/kit.sfz", "lines": 4}
      ]
      """

  @R23 @R17
  Scenario: nested-output-directory
    Missing parent directories are created, the stem is the last path
    component, and the manifest reaches the source by a relative path.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "deep/a/b"]
      """
    And the observer reads the directory "deep"
    Then the recorded trace contains:
      """
      [
        {"event": "directory", "dir": "deep", "files": 7},
        {"event": "file", "file": "deep/a/b/b.sfz"},
        {"event": "file", "file": "deep/a/b/b.mid"},
        {"event": "json", "file": "deep/a/b/b.rcy.json", "data.source": "../../../in.wav"}
      ]
      """

  @R19
  Scenario: rerun-replaces-kit-files-and-keeps-others
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    And a file "kit/notes.txt" containing:
      """
      keep me
      """
    When the client runs the command as "first" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--resolution", "8", "--out", "kit"]
      """
    And the client runs the command as "second" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "second", "code": 0},
        {"event": "text_line", "file": "kit/notes.txt", "index": 1, "text": "keep me"},
        {"event": "wav", "file": "kit/001.wav", "frames": 22050},
        {"event": "wav", "file": "kit/008.wav", "frames": 11025},
        {"event": "text", "file": "kit/kit.sfz", "lines": 4},
        {"event": "json", "file": "kit/kit.rcy.json", "data.slices.length": 4}
      ]
      """

  @R04 @baseline_red
  Scenario: nothing-is-written-outside-the-output-directory
    After a successful run the work directory holds the source and the kit,
    with no log file or other stray output.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "."
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "cut", "code": 0},
        {"event": "directory", "dir": ".", "files": 8, "dirs": 1}
      ]
      """
