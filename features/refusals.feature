Feature: refusals when cutting from a WAV file

  @R01
  Scenario: exactly-one-mode-is-required
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    And a file "m.json" containing:
      """
      {}
      """
    When the client runs the command as "none" with arguments:
      """
      ["--out", "kit"]
      """
    And the client runs the command as "two" with arguments:
      """
      ["--input", "in.wav", "--from-manifest", "m.json", "--measures", "1", "--out", "kit"]
      """
    And the client runs the command as "word" with the arguments ["--input", "in.wav", "--measures", "x", "--out", "kit"]
    And the client runs the command as "dialect" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "kit", "--sfz-dialect", "wav"]
    And the client runs the command as "option" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "kit", "--loud"]
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "none", "code": 2, "stdout_lines": 0},
        {"event": "process_exit", "name": "two", "code": 2, "stdout_lines": 0},
        {"event": "process_exit", "name": "word", "code": 2, "stdout_lines": 0},
        {"event": "process_exit", "name": "dialect", "code": 2, "stdout_lines": 0},
        {"event": "process_exit", "name": "option", "code": 2, "stdout_lines": 0},
        {"event": "output_line", "name": "none", "stream": "stderr", "index": 1},
        {"event": "output_line", "name": "two", "stream": "stderr", "index": 1},
        {"event": "directory_absent", "dir": "kit"}
      ]
      """

  @R03 @R05 @R06 @R09
  Scenario Outline: input-refusal
    Each refusal exits 2 with one stderr line, an empty stdout, and no output
    directory.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    And a 1-channel 48000 Hz 16-bit WAV "r48.wav" of 48000 frames
    And a 3-channel 48000 Hz 24-bit WAV "r48w24.wav" of 48000 frames
    And a file "junk.wav" containing:
      """
      not a wav
      """
    When the client runs the command as "refused" with the arguments <args>
    And the observer reads the directory "kit"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: <message>"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit"}]
      """

    Examples:
      | args                                                                  | message                                                                 |
      | ["--input", "in.wav", "--measures", "1"]                              | --out is required with --preset or --input                              |
      | ["--input", "in.wav", "--out", "kit"]                                 | --measures is required with --input                                     |
      | ["--input", "nope.wav", "--measures", "1", "--out", "kit"]            | input file not found: nope.wav                                          |
      | ["--input", "in.wav", "--measures", "0", "--out", "kit"]              | --measures and --resolution must be positive                            |
      | ["--input", "in.wav", "--measures", "1", "--resolution", "0", "--out", "kit"] | --measures and --resolution must be positive                    |
      | ["--input", "r48.wav", "--measures", "1", "--out", "kit"]             | Unsupported sample rate: 48000 Hz. RCY requires 44100 Hz audio files.   |
      | ["--input", "r48w24.wav", "--measures", "1", "--out", "kit"]          | Unsupported sample rate: 48000 Hz. RCY requires 44100 Hz audio files.   |
      | ["--input", "nope.wav"]                                               | --out is required with --preset or --input                              |
      | ["--input", "nope.wav", "--out", "kit"]                               | --measures is required with --input                                     |
      | ["--input", "nope.wav", "--measures", "0", "--out", "kit"]            | input file not found: nope.wav                                          |
      | ["--input", "junk.wav", "--measures", "0", "--out", "kit"]            | --measures and --resolution must be positive                            |

  @R03 @R05 @R09 @R23 @baseline_red
  Scenario Outline: input-refusal-for-unreadable-or-unsupported-audio
    Given a file "junk.wav" containing:
      """
      not a wav
      """
    And a 1-channel 44100 Hz 24-bit WAV "w24.wav" of 44100 frames
    And a 3-channel 44100 Hz 16-bit WAV "ch3.wav" of 44100 frames
    And a 1-channel 44100 Hz 16-bit WAV "tiny.wav" of 3 frames
    And a 1-channel 44100 Hz 16-bit WAV "empty.wav" of 0 frames
    And a 1-channel 44100 Hz 16-bit WAV "001.wav" of 88200 frames
    And a 1-channel 44100 Hz 16-bit extensible-format WAV "ext.wav" of 44100 frames
    And a 3-channel 44100 Hz 24-bit WAV "w24ch3.wav" of 44100 frames
    And a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "refused" with the arguments <args>
    And the observer reads the directory "kit"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: <message>"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit"}]
      """

    Examples:
      | args                                                        | message                                                                      |
      | ["--input", "junk.wav", "--measures", "1", "--out", "kit"]  | cannot read audio file: $WORK/junk.wav                                       |
      | ["--input", "w24.wav", "--measures", "1", "--out", "kit"]   | unsupported sample width: 24 bits. RCY requires 16-bit PCM audio files.      |
      | ["--input", "ch3.wav", "--measures", "1", "--out", "kit"]   | unsupported channel count: 3. RCY requires mono or stereo audio files.       |
      | ["--input", "tiny.wav", "--measures", "1", "--out", "kit"]  | cannot cut 3 frames into 4 slices                                            |
      | ["--input", "empty.wav", "--measures", "1", "--out", "kit"] | cannot read audio file: $WORK/empty.wav                                      |
      | ["--input", "ext.wav", "--measures", "1", "--out", "kit"]   | cannot read audio file: $WORK/ext.wav                                        |
      | ["--input", "w24ch3.wav", "--measures", "1", "--out", "kit"] | unsupported sample width: 24 bits. RCY requires 16-bit PCM audio files.     |
      | ["--input", "in.wav", "--measures", "1", "--out", "in.wav"] | output path is not a directory: in.wav                                       |
      | ["--input", "001.wav", "--measures", "1", "--out", "."]     | slice 1 file '001.wav' would overwrite the source                            |
      | ["--input", "tiny.wav", "--measures", "1", "--resolution", "200", "--out", "kit"] | cannot cut 3 frames into 200 slices                    |
      | ["--input", "in.wav", "--measures", "1", "--resolution", "69", "--out", "kit"] | slice 69 key 128 is not a MIDI note (0..127) |

  @R04 @baseline_red
  Scenario: a-refusal-writes-nothing
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "refused" with arguments:
      """
      ["--input", "in.wav", "--measures", "0", "--out", "kit"]
      """
    And the observer reads the directory "."
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "refused", "code": 2},
        {"event": "directory", "dir": ".", "files": 1, "dirs": 0}
      ]
      """

