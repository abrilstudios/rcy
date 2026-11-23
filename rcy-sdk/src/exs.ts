// Logic Pro Sampler instrument (.exs), little-endian block layout: one zone
// per sample on its own key, played from start to end regardless of note length.
//
// Apple doesn't publish the format. Block sizes and every constant byte below
// are observations: they copy a one-shot drum instrument that Logic Pro 11.2.2
// loads, cross-checked against the open-source readers listed in docs/exs.md.

/** Bytes before each block's content. */
const HEADER_SIZE = 84;
/** Block names hold at most this many bytes before the terminating NUL. */
export const EXS_NAME_MAX = 63;
/** The folder field holds at most this many bytes before the terminating NUL. */
export const EXS_PATH_MAX = 255;

const INSTRUMENT = 0, ZONE = 1, GROUP = 2, SAMPLE = 3, PARAMS = 4;
const SIZE = { [INSTRUMENT]: 80, [ZONE]: 140, [GROUP]: 132, [SAMPLE]: 592, [PARAMS]: 1108 };
/** Header flag words seen on each block type in files Logic wrote; meaning unknown. */
const HEADER_FLAGS = { [INSTRUMENT]: 0x40, [ZONE]: 0, [GROUP]: 0x20000000, [SAMPLE]: 0x20020000, [PARAMS]: 0 };
/** Zone flag bit 0: play the whole sample, ignoring note length. */
const ZONE_ONE_SHOT = 0x01;
/** Value at zone offset 84 in Logic-written files; meaning unknown. */
const ZONE_OFFSET_84 = 1_200_000;
/** Slots in the parameter block: 100 one-byte ids, then 200 two-byte ids. */
const PARAM_SLOTS = 100, PARAM_WIDE_SLOTS = 200;
/**
 * Instrument-wide settings as [parameter id, value]: master volume 0 dB, pitch
 * bend +2 semitones and down linked, 16 voices, filter off with cutoff fully
 * open, velocity range -60 dB, envelope 1 sustain at maximum with zero attack,
 * decay and hold.
 */
const PARAMS_DEFAULT: [number, number][] = [
  [7, 0], [3, 2], [4, -1], [5, 16], [44, 0], [30, 1000], [29, 0], [90, -60], [81, 127], [82, 0], [83, 0], [84, 0],
];

export interface ExsSample {
  /** MIDI note that plays this sample, 0..127. */
  key: number;
  /** File name with extension; printable ASCII, at most EXS_NAME_MAX bytes. Logic finds the audio by this name. */
  fileName: string;
  /** Byte offset of the first frame inside the file. */
  dataOffset: number;
  frames: number;
  sampleRate: number;
  bitsPerSample: number;
  channels: number;
  /** Size of the whole audio file in bytes. */
  fileSize: number;
  /** First frame the zone plays. Absent means 0. */
  start?: number;
  /** Frame after the last one the zone plays. Absent means `frames`. */
  end?: number;
}

export interface ExsInstrument {
  /** Instrument name without extension; printable ASCII, at most EXS_NAME_MAX - 4 bytes. */
  name: string;
  /** Absolute folder holding every sample file, without a trailing slash. */
  folder: string;
  /** WAV files, one zone each, in zone order. */
  samples: ExsSample[];
}

function ascii(text: string): Uint8Array {
  return Uint8Array.from(text, (c) => c.charCodeAt(0));
}

function fieldDefect(what: string, text: string, max: number): string | null {
  if (!/^[\x20-\x7e]*$/.test(text)) return `${what} is not printable ASCII: ${text}`;
  if (text.length > max) return `${what} is longer than ${max} bytes: ${text}`;
  return null;
}

/**
 * The first reason the instrument can't be written, or null. Checked in this
 * order: the instrument name (which with ".exs" must fit a block name), the
 * folder, then each sample's file name and key in sample order.
 */
export function exsDefect(inst: ExsInstrument): string | null {
  if (inst.samples.length < 1) return "an instrument needs at least one sample";
  const first = fieldDefect("instrument name", inst.name, EXS_NAME_MAX - ".exs".length)
    ?? fieldDefect("folder", inst.folder, EXS_PATH_MAX);
  if (first !== null) return first;
  if (!inst.folder.startsWith("/") || (inst.folder.length > 1 && inst.folder.endsWith("/"))) {
    return `folder is not an absolute path without a trailing slash: ${inst.folder}`;
  }
  for (const s of inst.samples) {
    const defect = fieldDefect("sample file name", s.fileName, EXS_NAME_MAX);
    if (defect !== null) return defect;
    if (!Number.isInteger(s.key) || s.key < 0 || s.key > 127) return `key ${s.key} is not a MIDI note (0..127)`;
    const from = s.start ?? 0, to = s.end ?? s.frames;
    if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to > s.frames || from >= to) {
      return `sample ${s.fileName} plays frames ${from}..${to}, outside its ${s.frames} frames`;
    }
  }
  return null;
}

function block(type: number, index: number, name: string): { bytes: Uint8Array; view: DataView; at: number } {
  const bytes = new Uint8Array(HEADER_SIZE + SIZE[type]);
  const view = new DataView(bytes.buffer);
  bytes.set([1, 1, 0, type]); // little-endian marker, version 1.0, block type
  view.setUint32(4, SIZE[type], true);
  view.setUint32(8, index >>> 0, true);
  view.setUint32(12, HEADER_FLAGS[type], true);
  bytes.set(ascii("TBOS"), 16);
  bytes.set(ascii(name), 20);
  return { bytes, view, at: HEADER_SIZE };
}

/** The bytes of an .exs file. Throws RangeError with the text of exsDefect when that isn't null. */
export function encodeExs(inst: ExsInstrument): Uint8Array {
  const defect = exsDefect(inst);
  if (defect !== null) throw new RangeError(defect);
  const folder = ascii(inst.folder);
  const blocks: Uint8Array[] = [];

  const head = block(INSTRUMENT, -1, inst.name + ".exs");
  head.view.setUint32(head.at + 4, inst.samples.length, true); // zones
  head.view.setUint32(head.at + 8, 1, true); // groups
  head.view.setUint32(head.at + 12, inst.samples.length, true); // samples
  head.view.setUint32(head.at + 16, 1, true); // parameter blocks
  blocks.push(head.bytes);

  inst.samples.forEach((s, i) => {
    const z = block(ZONE, i, s.fileName.replace(/\.[^.]*$/, ""));
    const c = z.at;
    z.bytes[c] = ZONE_ONE_SHOT;
    z.bytes[c + 1] = s.key; // root key
    z.bytes[c + 6] = s.key; // lowest key
    z.bytes[c + 7] = s.key; // highest key
    z.bytes[c + 10] = 127; // highest velocity; lowest stays 0
    z.view.setUint32(c + 12, s.start ?? 0, true); // sample start
    z.view.setUint32(c + 16, s.end ?? s.frames, true); // sample end
    z.view.setUint32(c + 24, s.frames, true); // loop end, set even with looping off
    z.view.setUint32(c + 84, ZONE_OFFSET_84, true);
    z.view.setInt32(c + 88, 0, true); // group index
    z.view.setUint32(c + 92, i, true); // sample index, by position in the file
    z.view.setInt32(c + 112, -1, true); // no release-tail sample
    blocks.push(z.bytes);
  });

  const g = block(GROUP, 0, "Slices");
  g.bytes[g.at + 3] = 1; // options byte as Logic writes it
  g.bytes[g.at + 6] = 127; // highest velocity
  g.bytes[g.at + 8] = 0xff;
  g.bytes[g.at + 38] = 80; // enable-by-tempo range, BPM, unused while enable-by is off
  g.bytes[g.at + 39] = 140;
  g.view.setInt32(g.at + 80, -1, true); // no round-robin position
  g.bytes[g.at + 89] = 127; // highest note
  g.bytes[g.at + 91] = 1;
  blocks.push(g.bytes);

  inst.samples.forEach((s, i) => {
    const b = block(SAMPLE, i, s.fileName);
    const c = b.at;
    b.view.setUint32(c, s.dataOffset, true);
    b.view.setUint32(c + 4, s.frames, true);
    b.view.setUint32(c + 8, s.sampleRate, true);
    b.view.setUint32(c + 12, s.bitsPerSample, true);
    b.view.setUint32(c + 16, s.channels, true);
    b.view.setUint32(c + 20, s.channels, true);
    b.bytes.set(ascii("EVAW"), c + 28); // "WAVE" as a little-endian word
    b.view.setUint32(c + 32, s.fileSize, true);
    b.bytes.set(folder, c + 80);
    b.bytes.set(ascii(s.fileName), c + 336);
    blocks.push(b.bytes);
  });

  const p = block(PARAMS, 0, "Default Param");
  p.view.setUint32(p.at, PARAM_SLOTS, true);
  PARAMS_DEFAULT.forEach(([id, value], i) => {
    p.bytes[p.at + 4 + i] = id;
    p.view.setInt16(p.at + 4 + PARAM_SLOTS + 2 * i, value, true);
  });
  p.view.setUint32(p.at + 4 + 3 * PARAM_SLOTS, PARAM_WIDE_SLOTS, true);
  blocks.push(p.bytes);

  const out = new Uint8Array(blocks.reduce((n, b) => n + b.length, 0));
  let at = 0;
  for (const b of blocks) { out.set(b, at); at += b.length; }
  return out;
}
