# EXS instrument layout

Apple doesn't publish the `.exs` format. `src/exs.ts` writes the little-endian
layout described here. Every size and constant is an observation taken from
instrument files Logic Pro loads and from open-source readers; none is a
documented guarantee.

## What the writer produces

One instrument block, one zone per sample, one group, one sample block per
audio file and one parameter block, in that order. Zones refer to samples and
groups by position in the file.

| Block | Type code | Content bytes |
|---|---|---|
| Instrument | 0 | 80 |
| Zone | 1 | 140 |
| Group | 2 | 132 |
| Sample | 3 | 592 |
| Parameters | 4 | 1108 |

Each block starts with an 84-byte header: byte-order marker `01`, version
`01 00`, type code, content size, index, a flag word, the magic `TBOS` and a
64-byte NUL-padded name.

Each zone covers a single key that is also its root key, spans velocities 0 to
127, and has the one-shot flag set, so a note plays the whole sample whatever
its length. Sample start (zone offset 12) and sample end (offset 16) hold the frames the
zone plays, the whole file unless the sample states a range; loop end holds
the frame count. The start field's position is taken from the open-source
readers and no instrument with a start above 0 has been loaded in Logic Pro.

Each sample block stores the byte offset of the first frame, the frame count,
rate, width and channel count, the file size, the folder as an absolute path
and the file name. Logic looks in the stored folder and, when the file isn't
there, searches by file name, so sample file names should be unique on the
machine.

## Limits

- Names, folders and file names are printable ASCII; the writer throws on
  anything else. The instrument name holds 59 bytes, a sample file name 63
  and the folder 255.
- Audio files are WAV. The file type word is written as `EVAW`.
- Logic's newer saves append fields and two property-list blocks holding
  interface state. The writer omits them.

## Unknown fields copied from real files

- Header flag words: `0x40` on the instrument, `0x20000000` on groups,
  `0x20020000` on samples.
- Zone offset 84: the value 1,200,000.
- Group offsets 3, 8 and 91: the values 1, 255 and 1.

## Sources

Format facts only; no code was copied.

- ConvertWithMoss, `format/exs/` (LGPL-3.0): reader and writer.
- surge-synthesizer/shortcircuit-xt, `exs_import.cpp` (MIT): reader.
- gradetwo/exs2sfz, `src/exs/parse.rs` (MIT): reader.
- Apple, Logic Pro User Guide, Sampler chapters: supported formats, instrument
  and sample locations, the sample search.
