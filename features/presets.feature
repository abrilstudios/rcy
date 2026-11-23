Feature: cut a kit from a preset

  @R10
  Scenario: preset-supplies-source-and-measures
    The apache_L preset is a two-measure mono break of 176400 frames.

    Given a copy of the repository's "presets" at "presets"
    When the client runs the command as "cut" with environment {"RCY_PRESETS": "presets"} and arguments:
      """
      ["--preset", "apache_L", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    And the observer compares "kit/008.wav" with frames 154350 to 176400 of "presets/apache-L.wav"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "cut", "code": 0, "stdout_lines": 6, "stderr_lines": 0},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 2, "text": "tempo: 120.00 BPM (2 measures x 4)"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 3, "text": "slices: 8"},
        {"event": "wav", "file": "kit/001.wav", "channels": 1, "rate": 44100, "width": 16, "frames": 22050},
        {"event": "frames_compared", "file": "kit/008.wav", "equal": true}
      ]
      """

  @R10
  Scenario: measures-option-replaces-the-preset-measure-count
    Given a copy of the repository's "presets" at "presets"
    When the client runs the command as "cut" with environment {"RCY_PRESETS": "presets"} and arguments:
      """
      ["--preset", "apache_L", "--measures", "1", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 2, "text": "tempo: 60.00 BPM (1 measures x 4)"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 3, "text": "slices: 4"},
        {"event": "wav", "file": "kit/001.wav", "frames": 44100}
      ]
      """

  @R10 @R17 @baseline_red
  Scenario: catalog-directory-comes-from-the-environment
    A catalog the scenario writes itself, holding an id no built-in list has.

    Given a 1-channel 44100 Hz 16-bit WAV "cat/ramp.wav" of 88200 frames
    And a file "cat/presets.json" containing:
      """
      {"ramp": {"file": "ramp.wav", "name": "Ramp", "artist": "Fixture", "measures": 1}}
      """
    When the client runs the command as "cut" with environment {"RCY_PRESETS": "cat"} and arguments:
      """
      ["--preset", "ramp", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "cut", "code": 0},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 1, "text": "source: $WORK/cat/ramp.wav"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 3, "text": "slices: 4"},
        {"event": "json", "file": "kit/kit.rcy.json", "data.source": "../cat/ramp.wav"}
      ]
      """

  @R03 @R11
  Scenario Outline: preset-refusal
    Given a copy of the repository's "presets" at "presets"
    When the client runs the command as "refused" with environment {"RCY_PRESETS": "presets"} and arguments:
      """
      <args>
      """
    And the observer reads the directory "kit"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: <message>"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit"}]
      """

    Examples:
      | args                                                      | message                                      |
      | ["--preset", "apache_L"]                                  | --out is required with --preset or --input   |
      | ["--preset", "nope", "--out", "kit"]                      | preset 'nope' not found                      |
      | ["--preset", "apache_L", "--measures", "0", "--out", "kit"] | --measures and --resolution must be positive |

  @R11 @baseline_red
  Scenario: preset-without-a-catalog-variable
    Given a copy of the repository's "presets" at "presets"
    When the client runs the command as "refused" with arguments:
      """
      ["--preset", "apache_L", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: RCY_PRESETS is not set; it must name the preset catalog directory"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit"}]
      """

  @R11 @baseline_red
  Scenario: preset-catalog-file-missing
    When the client runs the command as "refused" with environment {"RCY_PRESETS": "nowhere"} and arguments:
      """
      ["--preset", "apache_L", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: preset catalog not found: nowhere/presets.json"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit"}]
      """

  @R11 @baseline_red
  Scenario: preset-entry-without-measures
    Given a 1-channel 44100 Hz 16-bit WAV "cat/bare.wav" of 88200 frames
    And a file "cat/presets.json" containing:
      """
      {"bare": {"file": "bare.wav", "name": "Bare", "artist": "Fixture"}}
      """
    When the client runs the command as "refused" with environment {"RCY_PRESETS": "cat"} and arguments:
      """
      ["--preset", "bare", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: preset 'bare' has no measures; pass --measures"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit"}]
      """

  @R11 @baseline_red
  Scenario: preset-catalog-unreadable-or-audio-missing
    Given a file "cat/presets.json" containing:
      """
      {"ghost": {"file": "ghost.wav", "measures": 1}}
      """
    And a file "broken/presets.json" containing:
      """
      {nope
      """
    When the client runs the command as "ghost" with environment {"RCY_PRESETS": "cat"} and arguments:
      """
      ["--preset", "ghost", "--out", "kit"]
      """
    And the client runs the command as "broken" with environment {"RCY_PRESETS": "broken"} and arguments:
      """
      ["--preset", "ghost", "--out", "kit"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace shows run "ghost" exited 2 with the single stderr line "error: preset audio not found: $WORK/cat/ghost.wav"
    And the recorded trace shows run "broken" exited 2 with the single stderr line "error: preset catalog not found: broken/presets.json"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit"}]
      """
