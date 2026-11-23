# rcy-sdk

File-format code for rcy kits: reading and writing WAV, and writing Standard
MIDI Files, SFZ text, the kit manifest and Logic Pro Sampler instruments
(`.exs`). The SDK owns every byte of those formats. A program that uses it
decides what goes into a kit and when to refuse; it doesn't restate a byte
layout.

## Where the SDK ends

| The SDK owns | The program owns |
|---|---|
| RIFF chunk walking and the WAV header | Which rates, widths and channel counts it accepts |
| MIDI events, delta times and the tick formula | Which notes a kit holds |
| The manifest's member order and text layout | Reading and validating a manifest |
| SFZ region lines | File names, paths and the order files are written in |
| The `.exs` block layout and its name limits | Refusal messages and exit codes |
| Exact rounding and printing of doubles | Everything on the command line |

The SDK reads and writes no files. Its functions take and return bytes
(`Uint8Array`) and strings.

## Using it

`dist/rcy-sdk.js` is the whole SDK as one plain JavaScript file. It loads no
module and defines one constant, `rcySdk`, whose members are listed below.
`rcySdk.VERSION` is the version string. It runs on Node.js 22 and later.

`dist/bundle.cjs` joins a program with the SDK into one executable file:

```
node rcy-sdk/dist/bundle.cjs main.js rcy-export
```

The output is a `#!/usr/bin/env node` line, the bytes of `dist/rcy-sdk.js`
between two marker lines, then the bytes of `main.js`, with mode 0755.
`main.js` is CommonJS source that uses `rcySdk` directly; it must not start
with a `#!` line and must not define `rcySdk`.

## Functions

Types are written in TypeScript notation. `bytes` is `Uint8Array`; a Node
`Buffer` is accepted wherever bytes are taken.

### WAV

```ts
parseWav(bytes): {
  formatTag: number,      // always 1
  channels: number,
  sampleRate: number,     // frames per second
  bitsPerSample: number,
  blockAlign: number,     // bytes per frame
  frames: number,         // whole frames in data
  dataOffset: number,     // byte offset of the first frame inside the file
  data: bytes,            // the frames, trimmed to whole frames; a view, not a copy
}
```

Reads the first `fmt ` chunk and the first `data` chunk after it and skips
every other chunk. Throws `WavFormatError` when the bytes aren't a RIFF WAVE
file, when the format tag isn't 1 (integer PCM; the extensible tag 65534 is
refused), when a chunk is truncated, when the block align doesn't equal
channels times bytes per sample, or when there is no whole frame. It applies
no limit on rate, width or channel count. Test with
`error instanceof rcySdk.WavFormatError`.

```ts
encodeWav({ channels, sampleRate, bitsPerSample, data: bytes }): bytes
```

A 44-byte header followed by `data`, with no other chunk. Frame `a` up to
frame `b` of a parsed file is
`wav.data.subarray(a * wav.blockAlign, b * wav.blockAlign)`.

### MIDI

```ts
tempoMicros(bpm): number        // floor(60000000 / bpm), microseconds per quarter note
tempoWritable(bpm): boolean     // whether that value lies in 1..TEMPO_MAX (16777215)
tickAtFrame(frame, bpm, division, sampleRate): number
encodeMidi({ division, bpm, notes: [{ key, velocity, onTick, offTick }] }): bytes
```

`tickAtFrame` is the nearest tick to a frame offset,
`floor(frame * bpm * division / (60 * sampleRate) + 1/2)`, computed exactly
from the binary value of `bpm`.

`encodeMidi` writes a format 1 file with two tracks. The first holds a 4/4
time signature and the tempo at tick 0. The second holds the notes on channel
0 in the order given; they must not overlap and must ascend. A note may start
on the tick where the one before ends. It throws `RangeError` when
`tempoWritable(bpm)` is false.

### Manifest and SFZ

```ts
type Manifest = {
  source: string,          // path of the source audio relative to the manifest's directory
  sampleRate: number,
  channels: number,
  bpm: number,
  measures: number,
  boundaries: number[],    // frame positions, strictly increasing
  slices: { key: number, file: string, role: string }[],   // one per pair of neighbouring boundaries
  bufferMs?: number,       // source audio each slice file holds either side of its slice; absent means 0
}

manifestText(manifest): string
sfzText(manifest, "files" | "offsets", sourceFrames?): string
bufferFrames(ms, sampleRate): number
slicePoints(manifest, i, sourceFrames): { fileStart, fileEnd, offset, end }
```

`manifestText` returns the complete text of a `.rcy.json` file, schema
version `MANIFEST_VERSION` (1): members `rcy`, `source`, `sample_rate`,
`channels`, `bpm`, `measures`, `region`, `boundaries`, `slices`, in that
order. `region` is the first and last boundary. Each slice object carries
`index` (its 1-based position), `start` and `end` (from `boundaries`), `key`,
`file` and `role`. `bpm` prints as the shortest digits that read back to the
same double, with `.0` when integral. A `bufferMs` above 0 adds the member
`buffer_ms` after `measures`; a kit without a buffer has no such member.
Encode the text as UTF-8.

`bufferFrames` is the whole number of frames nearest `ms` milliseconds.
`slicePoints` says where slice `i` (0-based) lies when its file holds the
kit's buffer: the file holds source frames `fileStart` up to `fileEnd`, which
is the slice widened by `bufferFrames(bufferMs, sampleRate)` either side and
cut off at frame 0 and at `sourceFrames`; `offset` is the slice's first frame
inside the file and `end` the frame after its last.

`sfzText` returns one `<region>` line per slice, separated by `\n`, with no
final newline. `files` names each slice's file; `offsets` addresses `source`
by first and last frame and appends ` // <role>` for a non-empty role. For a
kit with a buffer, a `files` line reads
`<region> sample=<file> offset=<offset> end=<end - 1> key=<key>` with the
values of `slicePoints`, and `sourceFrames` is required.

### EXS

```ts
type ExsInstrument = {
  name: string,            // instrument name without ".exs"
  folder: string,          // absolute folder holding every sample file, no trailing slash
  samples: {
    key: number,           // the MIDI note that plays the sample
    fileName: string,      // with extension
    dataOffset: number, frames: number, sampleRate: number,
    bitsPerSample: number, channels: number,   // as parseWav reports them for that file
    fileSize: number,      // size of the whole file in bytes
    start?: number,        // first frame the zone plays; absent means 0
    end?: number,          // frame after the last one played; absent means frames
  }[],
}

exsDefect(instrument): string | null
encodeExs(instrument): bytes
```

`encodeExs` returns the bytes of a `.exs` file with one zone per sample. Each
zone sits on its sample's key alone and plays the sample from `start` to
`end` whatever the note's length. The facts about a sample file are what `parseWav` reports for
that file's bytes, and `fileSize` is the length of those bytes.

`exsDefect` returns the first reason an instrument can't be written, or null.
It checks the name, then the folder, then each sample's file name, key and
played range in order. Its texts are:

| Text | When |
|---|---|
| `instrument name is not printable ASCII: <name>` | a character outside 0x20..0x7E |
| `instrument name is longer than 59 bytes: <name>` | |
| `folder is not printable ASCII: <folder>` | |
| `folder is longer than 255 bytes: <folder>` | |
| `folder is not an absolute path without a trailing slash: <folder>` | |
| `sample file name is not printable ASCII: <fileName>` | |
| `sample file name is longer than 63 bytes: <fileName>` | |
| `key <key> is not a MIDI note (0..127)` | |
| `sample <fileName> plays frames <start>..<end>, outside its <frames> frames` | also when `start` isn't below `end` |
| `an instrument needs at least one sample` | checked first |

`encodeExs` throws `RangeError` with the same text. `docs/exs.md` describes
the layout and what in it is observed and what is unknown.

### Numbers

```ts
fixed(x, decimals): string       // exact binary value rounded to that many decimals; a tie rounds away from zero
significant(x, digits): string   // at most that many significant digits, no trailing zeros, never exponent form
shortestWithPoint(x): string     // shortest round-trip digits, plain notation, ".0" when integral
jsonString(s): string            // JSON string literal, characters outside printable ASCII as lower-case \uXXXX
```

`fixed(137.71790859793566, 2)` is `137.72`; `significant(8 / 3, 6)` is
`2.66667`; `shortestWithPoint(120)` is `120.0`.

## Changing the SDK

Source is TypeScript under `src/`, run directly by Node.js 23.6 or later.

```
node bin/build.cjs      # rewrites dist/rcy-sdk.js from src/
npm test                # every test runs on src/ and on dist/rcy-sdk.js
```

A change to a byte format needs a test that pins the bytes. A change to the
`.exs` layout also needs the result loaded in Logic Pro, since no published
description of that format exists to test against.
