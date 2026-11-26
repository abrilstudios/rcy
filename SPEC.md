# rcy-export specification

`rcy-export` is a command-line program that cuts a drum break into equal
slices and writes a kit: one WAV per slice, an SFZ instrument, a MIDI file
that replays the slices in order, and a JSON manifest that records the cut
points. On request it also writes a Logic Pro Sampler instrument with every
slice mapped to its key. A user edits the manifest by hand or with another
tool and runs `rcy-export` again to rebuild the kit from it.

The bytes of every file format are produced by `rcy-sdk`, which is described
in `rcy-sdk/README.md`. Where this document names a function as
`rcySdk.<name>`, the program must call it and write what it returns, and must
not reimplement it.

This document is written against rcy-sdk 0.1.0, the file
`rcy-sdk/dist/rcy-sdk.js` with SHA-256
`09bd1d3fb303b8d6e1028956cab71af3b933e99867a673830d058250501d81cd`,
described by `rcy-sdk/README.md` with SHA-256
`a8e6ef80d5863c90719cd1b16dbecaa2a38c610232e3dcf2f11c3b917ac05dd5`.

Each requirement carries an identifier (`R01`, `R02`, ...). A scenario under
`features/` is tagged with the identifiers it checks, and `bin/check-coverage`
fails when an identifier has no scenario.

## Terms

- A frame is one sample instant across all channels. Positions and lengths in
  this document are frame counts unless a unit is given.
- The source is the WAV file a kit is cut from, and `N` is its length in frames.
- The absolute path of a path P is P itself when P is absolute, otherwise the
  working directory joined with P; in both cases `.` and `..` components are
  removed lexically and there is no trailing separator. Symbolic links are
  not resolved. (`kit/../in.wav` run from `/w` is `/w/in.wav`.)
- The output directory is the directory named by `--out`. Its stem is the last
  component of its absolute path.
- `floor(x)` rounds down to an integer.
- A double is an IEEE 754 binary64 number. A double printed with two decimals
  is `rcySdk.fixed(x, 2)`.

## Constants

| Name | Value | Class | Reason |
|---|---|---|---|
| `SAMPLE_RATE` | 44100 Hz | invariant | The only rate the program accepts and writes. It does not resample. |
| `SAMPLE_WIDTH` | 16 bits, signed little-endian PCM | default | The only sample format accepted and written, so that slices are byte copies of the source. Accepting another width means writing slices at the source's width and recording the width in the manifest. |
| `BEATS_PER_MEASURE` | 4 | invariant | Every source is treated as 4/4. |
| `FIRST_KEY` | 60 (middle C) | default | MIDI key of the first slice; later slices take the following keys. |
| `LAST_KEY` | 127 | invariant | The highest MIDI key. A kit cut from audio holds at most `LAST_KEY - FIRST_KEY + 1` slices. |
| `DEFAULT_RESOLUTION` | 4 slices per measure | default | One slice per quarter note. |
| `DEFAULT_BUFFER_MS` | 0 ms | default | A kit's files are exactly its slices unless the command line or the manifest states a buffer. |
| `MAX_BUFFER_MS` | 1000 ms | parameter | The largest buffer accepted; longer than a drum hit's attack or tail needs. |
| `MIDI_DIVISION` | 960 ticks per quarter note | default | The value written by the implementation this specification was derived from; kept so existing MIDI files and new ones share a grid. |
| `MIDI_VELOCITY` | 100 | default | Note-on velocity for every slice. |
| `MANIFEST_VERSION` | `rcySdk.MANIFEST_VERSION` (1) | invariant | The schema the SDK writes and the only one the program reads. |

## Command line

```
rcy-export (--input WAV | --preset ID | --from-manifest FILE)
           [--out DIR] [--measures M] [--resolution R]
           [--sfz-dialect {files,offsets}] [--exs] [--buffer-ms N]
```

Short forms: `-i`, `-p`, `-f`, `-o`, `-m`, `-r`.

**R01.** Exactly one of `--input`, `--preset` and `--from-manifest` must be
given. With none or more than one, or with any other command-line syntax
error (an unknown option, a non-integer `--measures` or `--resolution`, an
unknown dialect), the program exits with code 2, writes at least one line to
stderr, prints nothing on stdout and creates no file. The wording of these
messages is not specified.

**R02.** `--measures` and `--resolution` are integers; `--resolution` defaults
to `DEFAULT_RESOLUTION` and `--sfz-dialect` defaults to `files`. `--exs`
takes no value.

## Refusals

**R03.** A refusal is any case this document gives a message for in a table
or in running text as `code like this`. On a refusal the program must exit
with code 2, print nothing on stdout, and write exactly one line to stderr:
`error: ` followed by the message. It must not create the output directory or
write any file. Every refusal check, including those that depend on the
source's contents, is made before the first write.

A path inside a message is written as stated with that message: either
exactly as the user gave it, or as an absolute path.

**R04.** The program must not write or create anything outside the output
directory, on success or on refusal. It keeps no log file and creates no
temporary file.

## Reading the source

**R05.** The source must be a RIFF WAVE file whose format tag is 1 (integer
PCM), at `SAMPLE_RATE` and `SAMPLE_WIDTH`, with 1 or 2 channels and at least
one frame. The checks run in this order and the first failure is the refusal:

| Condition | Message |
|---|---|
| Not a RIFF WAVE file, a format tag other than 1 (including the extensible tag 65534), or no frames | `cannot read audio file: <path>` |
| The sample rate is not 44100 | `Unsupported sample rate: <rate> Hz. RCY requires 44100 Hz audio files.` |
| The sample width is not 16 bits | `unsupported sample width: <bits> bits. RCY requires 16-bit PCM audio files.` |
| More than 2 channels | `unsupported channel count: <count>. RCY requires mono or stereo audio files.` |

`<path>` is the absolute path of the source.

The file is read with `rcySdk.parseWav`. A file for which it throws
`WavFormatError` is not a RIFF WAVE file with at least one frame, and gets the
first message. `N` is the `frames` value it returns.

## Cutting from audio: `--input`

**R06.** With `--input`, these refusals apply, checked in this order:

| Condition | Message |
|---|---|
| `--out` absent | `--out is required with --preset or --input` |
| `--measures` absent | `--measures is required with --input` |
| The input path is not an existing file | `input file not found: <path as given>` |
| `--measures` < 1 or `--resolution` < 1 | `--measures and --resolution must be positive` |

The source checks of R05 follow, then the checks of R09.

**R07.** The tempo in beats per minute is the double-precision value of

```
bpm = (60 * measures * BEATS_PER_MEASURE) / (N / SAMPLE_RATE)
```

**R08.** The slice count is `n = measures * resolution`. The boundaries are
the `n + 1` frame positions

```
boundary[i] = floor(i * N / n)        for i = 0 .. n
```

computed in exact integer arithmetic, so `boundary[0]` is 0 and `boundary[n]`
is `N`. Slice `k` (1-based) covers frames `boundary[k-1]` up to but not
including `boundary[k]`. Its file name is `k` as three decimal digits followed
by `.wav` (`001.wav`), its key is `FIRST_KEY + k - 1`, and its role is the
empty string. The region is the whole source, `0` to `N`.

**R09.** After R05 and before anything is written, in this order: if `n`
exceeds `N`, the program refuses with `cannot cut <N> frames into <n> slices`;
if a slice's key would exceed `LAST_KEY`, it refuses with
`slice <k> key <key> is not a MIDI note (0..127)`, naming the first such
slice; if the tempo fails the range check of R15, it refuses with that
message; if a slice file's absolute path in the output directory is the
source's absolute path, it refuses with
`slice <k> file '<file>' would overwrite the source`; with `--exs`, the check
of R24 comes last.

## Cutting from a preset: `--preset`

**R10.** `--preset ID` reads the source and its measure count from a preset
catalog. The environment variable `RCY_PRESETS` names the catalog directory,
which holds `presets.json`:

```json
{
  "apache_L": {"file": "apache-L.wav", "name": "Apache (Left Channel)",
               "artist": "Incredible Bongo Band", "measures": 2}
}
```

`file` is relative to the catalog directory. The program reads `file` and
`measures` and ignores other members. `--measures`, when given, replaces the
catalog's measure count. Once the source and measure count are known,
everything follows R05 and R07 to R09.

**R11.** Refusals for `--preset`, in this order:

| Condition | Message |
|---|---|
| `--out` absent | `--out is required with --preset or --input` |
| `RCY_PRESETS` unset or empty | `RCY_PRESETS is not set; it must name the preset catalog directory` |
| `presets.json` missing, not valid JSON, or not a JSON object | `preset catalog not found: <RCY_PRESETS as given>/presets.json` |
| No entry for the id | `preset '<id>' not found` |
| Entry has no `measures` and `--measures` absent | `preset '<id>' has no measures; pass --measures` |
| Measures < 1 or `--resolution` < 1 | `--measures and --resolution must be positive` |
| The entry's audio file doesn't exist | `preset audio not found: <absolute path>` |

## The kit

**R23. Output directory.** On success the output directory exists, created
with any missing parents, and holds the slice files and the three files named
`<stem>.sfz`, `<stem>.mid` and `<stem>.rcy.json`, where `<stem>` is the output
directory's stem. With `--exs` it also holds `<stem>.exs`. When the directory
didn't exist or was empty before the run, it holds nothing else. If `--out` names an existing path that is not a
directory, the program refuses with
`output path is not a directory: <path as given>`; this check comes directly
after the `--out` check of R06 and R11 and, with `--from-manifest`, directly
after the manifest-not-found check. The manifest is the last file written.

**R25. Buffer.** A slice file can hold source audio either side of its
slice, so that a cut placed slightly late or early loses nothing and the
sampler's start and end points stay adjustable. `--buffer-ms N` is a whole
number of milliseconds from 0 to `MAX_BUFFER_MS`; any other value is a
command-line error (R01). The kit's buffer is the command line's value; without one,
the `buffer_ms` of the manifest read by `--from-manifest`; without that,
`DEFAULT_BUFFER_MS`. With buffer `B = rcySdk.bufferFrames(ms, SAMPLE_RATE)`
frames, the file of a slice from `s` to `e` holds source frames
`max(0, s - B)` up to `min(N, e + B)`, `N` being the source's length, so
the first and last files of a kit can hold less than `B` on their outer side.
The slice then starts `s - max(0, s - B)` frames into its file; these are
the values `rcySdk.slicePoints` returns. The buffer changes the slice files,
the `files` SFZ, the EXS zones and one manifest member. Boundaries, keys and
the MIDI file are the same at every buffer.

**R12. Slice files.** One WAV per slice, named by the slice's file name. Each
has the source's channel count, `SAMPLE_RATE`, `SAMPLE_WIDTH`, and exactly the
frames R25 gives the file (with no buffer, the slice's frames), byte for byte
as they are in the source. No fade, gain change
or dither is applied. The file's bytes are `rcySdk.encodeWav` of those frames.

**R13. `<stem>.sfz`, dialect `files`.** The file's text is
`rcySdk.sfzText(kit, "files", N)`: one line per slice naming the slice's file and
key and, when the kit has a buffer, the slice's first and last frame inside
that file as `offset` and `end`.

**R14. `<stem>.sfz`, dialect `offsets`.** The file's text is
`rcySdk.sfzText(kit, "offsets")`: one line per slice addressing the source by
frame range, where the source path is the manifest's `source` value (R17).
Slice WAV files are written in both dialects.

**R15. `<stem>.mid`.** The file's bytes are `rcySdk.encodeMidi` with division
`MIDI_DIVISION`, the kit's tempo, and one note per slot of the play order
with the slot's slice's key and velocity `MIDI_VELOCITY`. The play order is
the manifest's `order` (R21): a list of slice numbers, each entry a slot, in
which a slice may fill several slots or none. Without one it is every slice
once in slice order. The slots are laid end to end from the region start,
each as long as its slice, so the file replays the break from the region
start in play order, and in slice order it ends at the region end. A slot
that starts `s` frames and ends `e` frames after the region start in that
layout has

```
onTick  = rcySdk.tickAtFrame(s, bpm, MIDI_DIVISION, SAMPLE_RATE)
offTick = rcySdk.tickAtFrame(e, bpm, MIDI_DIVISION, SAMPLE_RATE)
```

so each note ends on the tick where the next begins. When
`rcySdk.tempoWritable(bpm)` is false the program refuses with
`tempo <bpm> BPM cannot be written to MIDI`, `<bpm>` printed with two decimals.

**R16. `<stem>.rcy.json`, the manifest.** The file's text, encoded as UTF-8,
is `rcySdk.manifestText` of the kit. The kit is the README's `Manifest`
value: `source` by R17, `sampleRate` `SAMPLE_RATE`, `channels` the source's
channel count, `bpm` the tempo, `measures` the measure count, `boundaries`,
`bufferMs` the kit's buffer, and for each slice its `key`, `file` and `role`.
The manifest has a `buffer_ms` member only when the buffer is above 0. R13 and R14 pass the same
value. The manifest records `MANIFEST_VERSION`.

**R17. The `source` member.** It is the path of the source relative to the
output directory, computed from the two absolute paths, with `/` separators,
so a kit directory and its source can move together.

**R18. Report.** On success the program exits with code 0, writes nothing to
stderr, and prints exactly these lines on stdout:

```
source: <absolute path of the source>
tempo: <bpm with two decimals> BPM (<measures> measures x <resolution>)
slices: <slice count>
sfz: <absolute path of the SFZ file> (<dialect>)
midi: <absolute path of the MIDI file>
manifest: <absolute path of the manifest>
```

With `--exs` a line `exs: <absolute path of the EXS file>` comes between the
`midi:` and `manifest:` lines, making seven.

`<resolution>` is `rcySdk.significant(q, 6)`, where `q` is the double nearest
the slice count divided by the measure count (`4`, `0.5`, `2.66667`).

**R19.** Running again into a directory that already holds files replaces the
files the new kit names and leaves every other file alone, including slice
files of an earlier kit that the new kit doesn't name. A run without `--exs` is the
exception for one file: it removes a file named `<stem>.exs` in the output
directory, at the point where R24 would write it, because that instrument
would no longer describe the slice files.

**R24. `<stem>.exs`, with `--exs`.** A Logic Pro Sampler instrument holding
one zone per slice, in slice order. The file's bytes are `rcySdk.encodeExs`
of an instrument whose `name` is the stem, whose `folder` is the output
directory's absolute path, and whose samples are the slice files as written:
each slice's key and file name, and for the rest what `rcySdk.parseWav`
reports for the bytes `rcySdk.encodeWav` returned for that slice (R12):
`dataOffset`, `frames`, `sampleRate`, `bitsPerSample` and `channels`;
`fileSize` is the length of those bytes; `start` and `end` are the slice's
`offset` and `end` inside its file (R25), which for a kit without a buffer
are 0 and the frame count. All slices are encoded in memory
before the first write, so the instrument and its check need no file on disk.
When `rcySdk.exsDefect` of that instrument returns a text, the program refuses with
`cannot write EXS instrument: <text>`. Like every refusal, it is made before
anything is written or any directory is created. The EXS file is written
after the slice files and before the manifest.

## Rebuilding from a manifest: `--from-manifest`

**R20.** `--from-manifest FILE` reads a manifest, reads its source, and
writes the kit described by the manifest. `--out` defaults to the manifest's
own directory. `--measures` and `--resolution` are ignored. `--exs` applies as
it does when cutting from audio. A relative
`source` is resolved against the manifest's directory.

**R21.** The rebuilt kit takes its buffer by R25, and `bpm`, `measures`, `region`, `boundaries` and
each slice's `key`, `file` and `role` from the manifest. Each slice's `start`
and `end` are taken from `boundaries`; the values stored in the slice objects
are ignored on read, may be absent, and are rewritten on write. A slice object
without `role` has the empty role. The written manifest's `source` is recomputed for the new
output directory by R17. The manifest's `order` member (WINDOW.md W25), when
present, is the play order of R15, and the written manifest holds it as
`rcySdk.manifestText` writes it: no member for slice order. It changes the
MIDI file and nothing else; the slice files, their keys and the SFZ and EXS
instruments are the same for every order.

**R22.** A manifest refusal names the first defect in this order. `<path>` is
the manifest path as given, `<source>` is the absolute path of the source, and
`<value>` is the offending value as compact JSON (`2.5`, `"x"`, `true`, `null`
for a missing member). Compact JSON has no whitespace outside strings; a number
prints in its shortest form, without `.0` when integral, and a string prints
as `rcySdk.jsonString` returns it. An integer is a JSON
number with an integral value of magnitude below 2^53, so `2.0` is the
integer 2. `true` and `false` are neither integers nor numbers.
The literals `NaN`, `Infinity` and `-Infinity` make the file invalid JSON.

| Condition | Message |
|---|---|
| The manifest file doesn't exist | `manifest not found: <path>` |
| Not valid JSON | `<path>: invalid JSON` |
| Not a JSON object | `manifest must be a JSON object` |
| `rcy` is not the integer 1 | `unsupported manifest version <value>, expected 1` |
| `region` is not an object | `region must be an object with start and end` |
| `slices` is not an array | `slices must be a list` |
| `boundaries` is not an array of integers | `boundaries must be a list of integers` |
| Slice count is not boundary count minus 1 | `<b> boundaries define <b-1> slices, but <s> slices are listed` |
| `source` is not a string | `source must be a string, got <value>` |
| `sample_rate`, `channels`, `measures`, `region.start` or `region.end` is not an integer (checked in that order; the last two are named `start` and `end`) | `<member> must be an integer, got <value>` |
| `bpm` is not a number | `bpm must be a number, got <value>` |
| A slice is not an object | `each slice must be a JSON object` |
| A slice's `index` or `key` is not an integer | `<member> must be an integer, got <value>` |
| A slice's `file` is not a string | `file must be a string, got <value>` |
| A slice's `role` is present and not a string | `slice role must be a string, got <value>` |
| `source` is empty | `source must be a non-empty path` |
| `sample_rate` <= 0 | `sample_rate must be positive, got <value>` |
| `channels` not 1 or 2 | `channels must be 1 or 2, got <value>` |
| `bpm` <= 0 | `bpm must be a positive number, got <value>` |
| `buffer_ms` present and not an integer from 0 to `MAX_BUFFER_MS` | `buffer_ms must be an integer from 0 to 1000, got <value>` |
| `measures` < 1 | `measures must be >= 1, got <value>` |
| Region start < 0 | `region start must be >= 0, got <value>` |
| Fewer than 2 boundaries | `boundaries must hold at least the region start and end` |
| Boundaries not strictly increasing | `boundaries must be strictly increasing` |
| First or last boundary differs from the region | `boundaries must run from region start <start> to region end <end>, got <first>..<last>` |
| A slice's `index` is not its 1-based position | `slice at position <p> has index <i>; indices are 1-based and sequential` |
| A slice's `key` is outside 0..127 | `slice <i> key <key> is not a MIDI note (0..127)` |
| A slice's `file` is empty | `slice <i> has an empty file name` |
| A slice's `file` contains `/` or `\`, or is `.` or `..` | `slice <i> file '<file>' must be a bare file name` |
| Two slices share a `file` | `slice file '<file>' is used by more than one slice` |
| A slice's `file` is `<stem>.sfz`, `<stem>.mid`, `<stem>.rcy.json` or `<stem>.exs` for the output directory | `slice <i> file '<file>' is a kit file name` |
| `order` is present and not a non-empty array of integers from 1 to the slice count | `order must be a list of slice numbers from 1 to <s>` |
| The tempo fails the range check of R15 | the R15 message |
| The source file doesn't exist | `source audio not found: <source>` |
| The source fails R05 | the R05 message |
| `sample_rate` differs from the source | `manifest sample_rate <m> != source <s> (<source>)` |
| `channels` differs from the source | `manifest channels <m> != source <s> (<source>)` |
| Region end is past the source's end | `region end <end> exceeds source length <N> (<source>)` |
| A slice file's absolute path in the output directory is the source's absolute path | `slice <i> file '<file>' would overwrite the source` |
| With `--exs`, the instrument can't be written | the R24 message |

## Out of scope

The program plays no audio, talks to no hardware sampler, has no interactive
interface, and doesn't detect transients, stretch time or resample. What
happens when a write fails part-way (a full disk, a directory without write
permission) is not specified beyond a non-zero exit code.
