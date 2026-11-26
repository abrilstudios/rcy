// rcy-sdk 0.1.0. Built from src/ by bin/build.cjs; don't edit.
const rcySdk = (() => {
"use strict";
const m_numbers = (() => {
// Exact handling of IEEE 754 doubles, so no result depends on the order or
// rounding of floating-point operations.

/** |x| = mant * 2^exp exactly, for a finite double. */
function decompose(x        )                                              {
  if (!Number.isFinite(x)) throw new RangeError(`not a finite double: ${x}`);
  const dv = new DataView(new ArrayBuffer(8));
  dv.setFloat64(0, x);
  const hi = dv.getUint32(0);
  const lo = dv.getUint32(4);
  const biased = (hi >>> 20) & 0x7ff;
  let mant = (BigInt(hi & 0xfffff) << 32n) | BigInt(lo);
  let exp = -1074;
  if (biased !== 0) {
    mant |= 1n << 52n;
    exp = biased - 1075;
  }
  return { neg: hi >>> 31 === 1, mant, exp };
}

/** floor(x * num / den + 1/2) for a non-negative double x, in exact arithmetic. */
function roundScaled(x        , num        , den        )         {
  const p = decompose(x);
  if (p.neg && p.mant !== 0n) throw new RangeError(`negative value: ${x}`);
  let n = p.mant * num;
  let d = den;
  if (p.exp >= 0) n <<= BigInt(p.exp);
  else d <<= BigInt(-p.exp);
  return (2n * n + d) / (2n * d);
}

/** The exact binary value rounded to `decimals` places; an exact tie rounds away from zero. */
function fixed(x        , decimals        )         {
  const q = roundScaled(Math.abs(x), 10n ** BigInt(decimals), 1n);
  let s = q.toString().padStart(decimals + 1, "0");
  if (decimals > 0) s = s.slice(0, -decimals) + "." + s.slice(-decimals);
  return (x < 0 && q !== 0n ? "-" : "") + s;
}

/** Rewrites exponent notation ("1.25e+22") as plain decimal digits. */
function plain(s        )         {
  const m = /^(-?)(\d+)(?:\.(\d+))?e([+-]\d+)$/.exec(s);
  if (!m) return s;
  const digits = m[2] + (m[3] ?? "");
  const point = m[2].length + Number(m[4]);
  if (point <= 0) return m[1] + "0." + "0".repeat(-point) + digits;
  if (point >= digits.length) return m[1] + digits + "0".repeat(point - digits.length);
  return m[1] + digits.slice(0, point) + "." + digits.slice(point);
}

/** Shortest digits that read back to the same double, plain notation, ".0" when integral. */
function shortestWithPoint(x        )         {
  if (!Number.isFinite(x)) throw new RangeError(`not a finite double: ${x}`);
  const s = plain(String(x));
  return s.includes(".") ? s : s + ".0";
}

/** At most `digits` significant digits, no trailing zeros or point, never exponent form. */
function significant(x        , digits        )         {
  if (!Number.isFinite(x)) throw new RangeError(`not a finite double: ${x}`);
  const s = plain(x.toPrecision(digits));
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
}
return { decompose, roundScaled, fixed, plain, shortestWithPoint, significant };
})();
const m_wav = (() => {
// RIFF WAVE with integer PCM. The reader reports what the header says and
// leaves policy (which rates, widths and channel counts to accept) to the caller.

class WavFormatError extends Error {}

                      
                                                                       
                    
                   
                           
                     
                        
                         
                     
                                
                 
                                                        
                     
                                                                        
                   
 

const ascii = (b            , at        ) => String.fromCharCode(b[at], b[at + 1], b[at + 2], b[at + 3]);

/**
 * Reads the first `fmt ` chunk and the first `data` chunk after it; every
 * other chunk is skipped. Throws WavFormatError when the bytes aren't a RIFF
 * WAVE file with format tag 1 and at least one whole frame.
 */
function parseWav(bytes            )      {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (bytes.length < 12 || ascii(bytes, 0) !== "RIFF" || ascii(bytes, 8) !== "WAVE") {
    throw new WavFormatError("not a RIFF WAVE file");
  }
  let fmt                                                     = null;
  let data                    = null;
  let at = 12;
  while (at + 8 <= bytes.length) {
    const id = ascii(bytes, at);
    const length = view.getUint32(at + 4, true);
    const body = at + 8;
    if (fmt === null && id === "fmt ") {
      if (length < 16 || body + 16 > bytes.length) throw new WavFormatError("fmt chunk shorter than 16 bytes");
      fmt = {
        formatTag: view.getUint16(body, true),
        channels: view.getUint16(body + 2, true),
        sampleRate: view.getUint32(body + 4, true),
        blockAlign: view.getUint16(body + 12, true),
        bitsPerSample: view.getUint16(body + 14, true),
      };
    } else if (fmt !== null && id === "data") {
      if (body + length > bytes.length) throw new WavFormatError("data chunk runs past the end of the file");
      data = bytes.subarray(body, body + length);
      break;
    }
    at = body + length + (length & 1);
  }
  if (fmt === null) throw new WavFormatError("no fmt chunk");
  if (data === null) throw new WavFormatError("no data chunk after the fmt chunk");
  if (fmt.formatTag !== 1) throw new WavFormatError(`format tag ${fmt.formatTag} is not integer PCM`);
  if (fmt.channels < 1 || fmt.blockAlign !== fmt.channels * Math.ceil(fmt.bitsPerSample / 8)) {
    throw new WavFormatError("block align doesn't match the channel count and sample width");
  }
  const frames = Math.floor(data.length / fmt.blockAlign);
  if (frames < 1) throw new WavFormatError("no frames");
  return { ...fmt, frames, dataOffset: data.byteOffset - bytes.byteOffset, data: data.subarray(0, frames * fmt.blockAlign) };
}

/** A 44-byte header followed by the frames, with no other chunk. */
function encodeWav(wav                                                                                   )             {
  const blockAlign = wav.channels * (wav.bitsPerSample / 8);
  if (!Number.isInteger(blockAlign) || blockAlign < 1 || wav.data.length % blockAlign !== 0) {
    throw new RangeError("data is not a whole number of frames");
  }
  const out = new Uint8Array(44 + wav.data.length);
  const view = new DataView(out.buffer);
  const tag = (at        , s        ) => { for (let i = 0; i < 4; i++) out[at + i] = s.charCodeAt(i); };
  tag(0, "RIFF"); view.setUint32(4, 36 + wav.data.length, true); tag(8, "WAVE");
  tag(12, "fmt "); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, wav.channels, true);
  view.setUint32(24, wav.sampleRate, true); view.setUint32(28, wav.sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true); view.setUint16(34, wav.bitsPerSample, true);
  tag(36, "data"); view.setUint32(40, wav.data.length, true);
  out.set(wav.data, 44);
  return out;
}
return { WavFormatError, parseWav, encodeWav };
})();
const m_midi = (() => {
// Standard MIDI File, format 1: a tempo track and one note track.
const { roundScaled } = m_numbers;

/** The largest value the three-byte tempo meta-event holds, in microseconds per quarter note. */
const TEMPO_MAX = 0xffffff;

/** Microseconds per quarter note: the floor of one double division. */
function tempoMicros(bpm        )         {
  return Math.floor(60_000_000 / bpm);
}

/** Whether the tempo fits the tempo meta-event. */
function tempoWritable(bpm        )          {
  const t = tempoMicros(bpm);
  return t >= 1 && t <= TEMPO_MAX;
}

/** Nearest tick to a frame offset: floor(frame * bpm * division / (60 * sampleRate) + 1/2), exactly. */
function tickAtFrame(frame        , bpm        , division        , sampleRate        )         {
  return Number(roundScaled(bpm, BigInt(frame) * BigInt(division), 60n * BigInt(sampleRate)));
}

                                                                                        

function quantity(v        )           {
  const bytes = [v & 0x7f];
  for (v = Math.floor(v / 128); v > 0; v = Math.floor(v / 128)) bytes.unshift((v & 0x7f) | 0x80);
  return bytes;
}

function chunk(id        , body          )           {
  const n = body.length;
  return [...id].map((c) => c.charCodeAt(0)).concat([(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255], body);
}

/**
 * Track 1 holds a 4/4 time signature and the tempo at tick 0. Track 2 holds
 * the notes on channel 0 in the order given, which must be non-overlapping
 * and ascending; a note-off is status 0x80 with velocity 64. No running status.
 */
function encodeMidi(song                                                  )             {
  if (!tempoWritable(song.bpm)) throw new RangeError(`tempo ${song.bpm} BPM doesn't fit the MIDI tempo event`);
  const t = tempoMicros(song.bpm);
  const tempoTrack = [
    0, 0xff, 0x58, 4, 4, 2, 24, 8,
    0, 0xff, 0x51, 3, (t >>> 16) & 255, (t >>> 8) & 255, t & 255,
    0, 0xff, 0x2f, 0,
  ];
  const noteTrack           = [];
  let now = 0;
  for (const note of song.notes) {
    if (note.onTick < now || note.offTick < note.onTick) throw new RangeError("notes must be ascending and must not overlap");
    noteTrack.push(...quantity(note.onTick - now), 0x90, note.key, note.velocity);
    noteTrack.push(...quantity(note.offTick - note.onTick), 0x80, note.key, 64);
    now = note.offTick;
  }
  noteTrack.push(0, 0xff, 0x2f, 0);
  const header = chunk("MThd", [0, 1, 0, 2, (song.division >>> 8) & 255, song.division & 255]);
  return Uint8Array.from([...header, ...chunk("MTrk", tempoTrack), ...chunk("MTrk", noteTrack)]);
}
return { TEMPO_MAX, tempoMicros, tempoWritable, tickAtFrame, encodeMidi };
})();
const m_manifest = (() => {
// The kit manifest (`<stem>.rcy.json`, schema version 1) as text, and SFZ regions.
const { shortestWithPoint } = m_numbers;

const MANIFEST_VERSION = 1;

                                                                  

                           
                                                                                      
                 
                     
                   
              
                   
                                                                                                  
                       
                                                 
                  
     
                                                                            
                                                                 
     
                    
     
                                                                            
                                                                             
                                           
     
                   
 

/** The whole number of frames nearest `ms` milliseconds at `sampleRate`. */
function bufferFrames(ms        , sampleRate        )         {
  return Math.round(ms * sampleRate / 1000);
}

/**
 * Where slice `i` lies inside its own file when the file holds the kit's
 * buffer: `offset` is the slice's first frame in the file, `end` the frame
 * after its last, and `fileStart`..`fileEnd` the source frames the file holds.
 */
function slicePoints(m          , i        , sourceFrames        )                                                                      {
  const pad = bufferFrames(m.bufferMs ?? 0, m.sampleRate);
  const fileStart = Math.max(0, m.boundaries[i] - pad);
  const fileEnd = Math.min(sourceFrames, m.boundaries[i + 1] + pad);
  return { fileStart, fileEnd, offset: m.boundaries[i] - fileStart, end: m.boundaries[i + 1] - fileStart };
}

/** A JSON string literal with every character outside printable ASCII as a lower-case \uXXXX escape. */
function jsonString(s        )         {
  const short                         = { 0x22: '\\"', 0x5c: "\\\\", 0x0a: "\\n", 0x0d: "\\r", 0x09: "\\t", 0x08: "\\b", 0x0c: "\\f" };
  let out = '"';
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    out += short[c] ?? (c < 0x20 || c > 0x7e ? "\\u" + c.toString(16).padStart(4, "0") : s[i]);
  }
  return out + '"';
}

/** Two-space indented text with members in schema order, one element per line and a final newline. */
function manifestText(m          )         {
  if (m.slices.length !== m.boundaries.length - 1) throw new RangeError("slices must number one fewer than boundaries");
  const b = m.boundaries;
  const comma = (i        , n        ) => (i < n - 1 ? "," : "");
  const order = m.order ?? [];
  if (order.length > 0) {
    if (order.some((v) => !Number.isInteger(v) || v < 1 || v > m.slices.length)) {
      throw new RangeError("order must hold slice numbers");
    }
  }
  const reordered = order.length > 0 && (order.length !== m.slices.length || order.some((v, i) => v !== i + 1));
  const lines = [
    "{",
    `  "rcy": ${MANIFEST_VERSION},`,
    `  "source": ${jsonString(m.source)},`,
    `  "sample_rate": ${m.sampleRate},`,
    `  "channels": ${m.channels},`,
    `  "bpm": ${shortestWithPoint(m.bpm)},`,
    `  "measures": ${m.measures},`,
    ...((m.bufferMs ?? 0) > 0 ? [`  "buffer_ms": ${m.bufferMs},`] : []),
    '  "region": {',
    `    "start": ${b[0]},`,
    `    "end": ${b[b.length - 1]}`,
    "  },",
    '  "boundaries": [',
    ...b.map((v, i) => `    ${v}${comma(i, b.length)}`),
    "  ],",
    '  "slices": [',
    ...m.slices.flatMap((s, i) => [
      "    {",
      `      "index": ${i + 1},`,
      `      "start": ${b[i]},`,
      `      "end": ${b[i + 1]},`,
      `      "key": ${s.key},`,
      `      "file": ${jsonString(s.file)},`,
      `      "role": ${jsonString(s.role)}`,
      `    }${comma(i, m.slices.length)}`,
    ]),
    ...(reordered ? ["  ],", '  "order": [', ...order.map((v, i) => `    ${v}${comma(i, order.length)}`), "  ]"] : ["  ]"]),
    "}",
  ];
  return lines.join("\n") + "\n";
}

/**
 * SFZ regions, newline separated, with no final newline. `files` names one
 * sample file per slice; `offsets` addresses the source by first and last frame.
 * When the kit has a buffer, a `files` line also carries `offset` and `end`,
 * the slice's first and last frame inside its file, and `sourceFrames` (the
 * source's length) is required.
 */
function sfzText(m          , dialect                     , sourceFrames         )         {
  return m.slices.map((s, i) => {
    if (dialect === "files") {
      if ((m.bufferMs ?? 0) === 0) return `<region> sample=${s.file} key=${s.key}`;
      if (sourceFrames === undefined) throw new RangeError("a kit with a buffer needs the source's frame count");
      const p = slicePoints(m, i, sourceFrames);
      return `<region> sample=${s.file} offset=${p.offset} end=${p.end - 1} key=${s.key}`;
    }
    const line = `<region> sample=${m.source} start=${m.boundaries[i]} end=${m.boundaries[i + 1] - 1} key=${s.key}`;
    return s.role === "" ? line : `${line} // ${s.role}`;
  }).join("\n");
}
return { MANIFEST_VERSION, bufferFrames, slicePoints, jsonString, manifestText, sfzText };
})();
const m_exs = (() => {
// Logic Pro Sampler instrument (.exs), little-endian block layout: one zone
// per sample on its own key, played from start to end regardless of note length.
//
// Apple doesn't publish the format. Block sizes and every constant byte below
// are observations: they copy a one-shot drum instrument that Logic Pro 11.2.2
// loads, cross-checked against the open-source readers listed in docs/exs.md.

/** Bytes before each block's content. */
const HEADER_SIZE = 84;
/** Block names hold at most this many bytes before the terminating NUL. */
const EXS_NAME_MAX = 63;
/** The folder field holds at most this many bytes before the terminating NUL. */
const EXS_PATH_MAX = 255;

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
const PARAMS_DEFAULT                     = [
  [7, 0], [3, 2], [4, -1], [5, 16], [44, 0], [30, 1000], [29, 0], [90, -60], [81, 127], [82, 0], [83, 0], [84, 0],
];

                            
                                                  
              
                                                                                                                   
                   
                                                        
                     
                 
                     
                        
                   
                                               
                   
                                                    
                 
                                                                        
               
 

                                
                                                                                            
               
                                                                             
                 
                                                 
                       
 

function ascii(text        )             {
  return Uint8Array.from(text, (c) => c.charCodeAt(0));
}

function fieldDefect(what        , text        , max        )                {
  if (!/^[\x20-\x7e]*$/.test(text)) return `${what} is not printable ASCII: ${text}`;
  if (text.length > max) return `${what} is longer than ${max} bytes: ${text}`;
  return null;
}

/**
 * The first reason the instrument can't be written, or null. Checked in this
 * order: the instrument name (which with ".exs" must fit a block name), the
 * folder, then each sample's file name and key in sample order.
 */
function exsDefect(inst               )                {
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

function block(type        , index        , name        )                                                    {
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
function encodeExs(inst               )             {
  const defect = exsDefect(inst);
  if (defect !== null) throw new RangeError(defect);
  const folder = ascii(inst.folder);
  const blocks               = [];

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
return { EXS_NAME_MAX, EXS_PATH_MAX, exsDefect, encodeExs };
})();
return Object.freeze({ VERSION: "0.1.0", ...m_numbers, ...m_wav, ...m_midi, ...m_manifest, ...m_exs });
})();
