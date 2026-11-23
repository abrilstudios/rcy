Feature: Logic Pro Sampler instrument, written with --exs

  @R18 @R23 @R24 @baseline_red
  Scenario: exs-instrument-maps-every-slice-to-its-key
    The instrument holds one zone per slice on that slice's key, played from
    start to end, and each sample entry describes the slice file beside it.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with arguments:
      """
      ["--input", "in.wav", "--measures", "1", "--out", "kit", "--exs"]
      """
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "cut", "code": 0, "stdout_lines": 7, "stderr_lines": 0},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 5, "text": "midi: $WORK/kit/kit.mid"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 6, "text": "exs: $WORK/kit/kit.exs"},
        {"event": "output_line", "name": "cut", "stream": "stdout", "index": 7, "text": "manifest: $WORK/kit/kit.rcy.json"},
        {"event": "directory", "dir": "kit", "files": 8, "dirs": 0},
        {"event": "exs", "file": "kit/kit.exs", "name": "kit.exs", "zones": 4, "groups": 1, "samples": 4, "params": 1,
         "order": ["instrument", "zone", "group", "sample", "params"],
         "declared_zones": 4, "declared_groups": 1, "declared_samples": 4},
        {"event": "exs_layout", "file": "kit/kit.exs",
         "header_flags": {"instrument": [64], "zone": [0], "group": [536870912], "sample": [537001984], "params": [0]},
         "sizes": {"instrument": [80], "zone": [140], "group": [132], "sample": [592], "params": [1108]},
         "group_sha256": "648fd2dee0c97d3e79344d8b03b20efa022c9d268346d4052a461a31b3edce28",
         "params_sha256": "af792e700d584bcae75c92cf7524b84fce311004cf19d583a119794f9d420af8",
         "zone_word_84": [1200000]},
        {"event": "exs_zone", "file": "kit/kit.exs", "index": 0, "one_shot": true, "reverse": false, "root": 60,
         "key_low": 60, "key_high": 60, "velocity_low": 0, "velocity_high": 127, "tune": 0, "pan": 0, "volume": 0,
         "start": 0, "end": 22050, "loop_on": false, "group": 0, "sample": 0},
        {"event": "exs_zone", "file": "kit/kit.exs", "index": 1, "one_shot": true, "root": 61, "key_low": 61, "key_high": 61, "sample": 1},
        {"event": "exs_zone", "file": "kit/kit.exs", "index": 3, "one_shot": true, "root": 63, "key_low": 63, "key_high": 63, "end": 22050, "sample": 3},
        {"event": "exs_sample", "file": "kit/kit.exs", "index": 0, "name": "001.wav", "block_name": "001.wav", "folder": "$WORK/kit",
         "type": "EVAW", "frames": 22050, "rate": 44100, "width": 16, "channels": 1, "exists": true, "matches_wav": true},
        {"event": "exs_sample", "file": "kit/kit.exs", "index": 3, "name": "004.wav", "folder": "$WORK/kit", "exists": true, "matches_wav": true}
      ]
      """
    And the recorded trace has these counts:
      """
      [{"match": {"event": "exs_sample", "file": "kit/kit.exs", "matches_wav": true}, "equals": 4}]
      """

  @R23 @R24 @baseline_red
  Scenario: no-exs-file-without-the-option
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "kit"]
    And the client runs the command as "again" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "kit2", "--exs"]
    And the observer reads the directory "kit"
    And the observer reads the directory "kit2"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "cut", "code": 0, "stdout_lines": 6},
        {"event": "directory", "dir": "kit", "files": 7},
        {"event": "directory", "dir": "kit2", "files": 8},
        {"event": "file", "file": "kit2/kit2.exs"}
      ]
      """
    And the recorded trace has these counts:
      """
      [{"match": {"event": "file", "file": "kit/kit.exs"}, "equals": 0}]
      """

  @R20 @R24 @baseline_red
  Scenario: exs-from-a-manifest-uses-its-keys-and-file-names
    A stereo source rebuilt from a hand-written manifest: zones take the
    manifest's keys and the samples its file names.

    Given a 2-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    And a file "m.json" containing:
      """
      {
        "rcy": 1, "source": "in.wav", "sample_rate": 44100, "channels": 2,
        "bpm": 120, "measures": 1,
        "region": {"start": 1000, "end": 45100},
        "boundaries": [1000, 20000, 45100],
        "slices": [
          {"index": 1, "key": 36, "file": "kick.wav", "role": "kick"},
          {"index": 2, "key": 38, "file": "snare 1.wav", "role": ""}
        ]
      }
      """
    When the client runs the command as "rebuild" with arguments:
      """
      ["--from-manifest", "m.json", "--out", "deep/My Kit", "--exs"]
      """
    And the observer reads the directory "deep"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "rebuild", "code": 0, "stdout_lines": 7},
        {"event": "output_line", "name": "rebuild", "stream": "stdout", "index": 6, "text": "exs: $WORK/deep/My Kit/My Kit.exs"},
        {"event": "exs", "file": "deep/My Kit/My Kit.exs", "name": "My Kit.exs", "zones": 2, "samples": 2},
        {"event": "exs_zone", "index": 0, "root": 36, "key_low": 36, "key_high": 36, "end": 19000, "sample": 0},
        {"event": "exs_zone", "index": 1, "root": 38, "key_low": 38, "key_high": 38, "end": 25100, "sample": 1},
        {"event": "exs_sample", "index": 0, "name": "kick.wav", "folder": "$WORK/deep/My Kit", "frames": 19000, "channels": 2, "matches_wav": true},
        {"event": "exs_sample", "index": 1, "name": "snare 1.wav", "frames": 25100, "channels": 2, "matches_wav": true}
      ]
      """

  @R03 @R09 @R24 @baseline_red
  Scenario Outline: exs-refusal-when-cutting
    A name the instrument format can't hold is a refusal before anything is
    written; the same cut without --exs is not refused.

    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "refused" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "<out>", "--exs"]
    And the client runs the command as "plain" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "ok/<out>"]
    And the observer reads the directory "<out>"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: cannot write EXS instrument: <text>"
    And the recorded trace contains:
      """
      [
        {"event": "directory_absent", "dir": "<out>"},
        {"event": "process_exit", "name": "plain", "code": 0}
      ]
      """

    Examples:
      | out                                                          | text                                                                                                          |
      | bär                                                          | instrument name is not printable ASCII: bär                                                                   |
      | kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk | instrument name is longer than 59 bytes: kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk          |
      | für/kit                                                      | folder is not printable ASCII: $WORK/für/kit                                                                  |
      | dddddddddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddddddddd/kit | folder is longer than 255 bytes: $WORK/dddddddddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddddddddd/dddddddddddddddddddddddddddddddddddddddddddddddddd/kit |

  @R22 @R24 @baseline_red
  Scenario Outline: exs-refusal-from-a-manifest
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "kit"]
    And the client derives "kit/edited.json" from "kit/kit.rcy.json" setting <dotted> to <value>
    And the client runs the command as "refused" with the arguments ["--from-manifest", "kit/edited.json", "--out", "kit2", "--exs"]
    And the observer reads the directory "kit2"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: <message>"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit2"}]
      """

    Examples:
      | dotted        | value        | message                                                                         |
      | slices.1.file | "snäre.wav"  | cannot write EXS instrument: sample file name is not printable ASCII: snäre.wav |
      | slices.2.file | "kit2.exs"   | slice 3 file 'kit2.exs' is a kit file name                                      |
      | slices.1.file | "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav" | cannot write EXS instrument: sample file name is longer than 63 bytes: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav |

  @R09 @R24 @baseline_red
  Scenario: exs-check-comes-after-the-other-refusals-when-cutting
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "refused" with the arguments ["--input", "in.wav", "--measures", "1", "--resolution", "69", "--out", "bär", "--exs"]
    And the observer reads the directory "bär"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: slice 69 key 128 is not a MIDI note (0..127)"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "bär"}]
      """

  @R22 @R24 @baseline_red
  Scenario: exs-check-comes-after-the-other-refusals-from-a-manifest
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "cut" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "kit"]
    And the client derives "kit/edited.json" from "kit/kit.rcy.json" with:
      """
      {"slices.1.file": "snäre.wav", "sample_rate": 48000}
      """
    And the client runs the command as "refused" with the arguments ["--from-manifest", "kit/edited.json", "--out", "kit2", "--exs"]
    And the observer reads the directory "kit2"
    Then the recorded trace shows run "refused" exited 2 with the single stderr line "error: manifest sample_rate 48000 != source 44100 ($WORK/in.wav)"
    And the recorded trace contains:
      """
      [{"event": "directory_absent", "dir": "kit2"}]
      """

  @R19 @R24 @baseline_red
  Scenario: a-run-without-exs-removes-an-earlier-instrument
    Given a 1-channel 44100 Hz 16-bit WAV "in.wav" of 88200 frames
    When the client runs the command as "first" with the arguments ["--input", "in.wav", "--measures", "1", "--out", "kit", "--exs"]
    And the client runs the command as "second" with the arguments ["--input", "in.wav", "--measures", "1", "--resolution", "2", "--out", "kit"]
    And the observer reads the directory "kit"
    Then the recorded trace contains:
      """
      [
        {"event": "process_exit", "name": "first", "code": 0, "stdout_lines": 7},
        {"event": "process_exit", "name": "second", "code": 0, "stdout_lines": 6},
        {"event": "directory", "dir": "kit", "files": 7},
        {"event": "file", "file": "kit/004.wav"}
      ]
      """
    And the recorded trace has these counts:
      """
      [{"match": {"event": "file", "file": "kit/kit.exs"}, "equals": 0}]
      """
