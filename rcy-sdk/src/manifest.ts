// The kit manifest (`<stem>.rcy.json`, schema version 1) as text, and SFZ regions.
import { shortestWithPoint } from "./numbers.ts";

export const MANIFEST_VERSION = 1;

export interface Slice { key: number; file: string; role: string }

export interface Manifest {
  /** Path of the source audio relative to the manifest's directory, `/` separated. */
  source: string;
  sampleRate: number;
  channels: number;
  bpm: number;
  measures: number;
  /** Frame positions, strictly increasing; slice k covers boundaries[k] up to boundaries[k+1]. */
  boundaries: number[];
  /** One per pair of neighbouring boundaries. */
  slices: Slice[];
  /**
   * Milliseconds of source audio each slice file holds before its start and
   * after its end, as far as the source reaches. Absent means 0.
   */
  bufferMs?: number;
}

/** The whole number of frames nearest `ms` milliseconds at `sampleRate`. */
export function bufferFrames(ms: number, sampleRate: number): number {
  return Math.round(ms * sampleRate / 1000);
}

/**
 * Where slice `i` lies inside its own file when the file holds the kit's
 * buffer: `offset` is the slice's first frame in the file, `end` the frame
 * after its last, and `fileStart`..`fileEnd` the source frames the file holds.
 */
export function slicePoints(m: Manifest, i: number, sourceFrames: number): { fileStart: number; fileEnd: number; offset: number; end: number } {
  const pad = bufferFrames(m.bufferMs ?? 0, m.sampleRate);
  const fileStart = Math.max(0, m.boundaries[i] - pad);
  const fileEnd = Math.min(sourceFrames, m.boundaries[i + 1] + pad);
  return { fileStart, fileEnd, offset: m.boundaries[i] - fileStart, end: m.boundaries[i + 1] - fileStart };
}

/** A JSON string literal with every character outside printable ASCII as a lower-case \uXXXX escape. */
export function jsonString(s: string): string {
  const short: Record<number, string> = { 0x22: '\\"', 0x5c: "\\\\", 0x0a: "\\n", 0x0d: "\\r", 0x09: "\\t", 0x08: "\\b", 0x0c: "\\f" };
  let out = '"';
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    out += short[c] ?? (c < 0x20 || c > 0x7e ? "\\u" + c.toString(16).padStart(4, "0") : s[i]);
  }
  return out + '"';
}

/** Two-space indented text with members in schema order, one element per line and a final newline. */
export function manifestText(m: Manifest): string {
  if (m.slices.length !== m.boundaries.length - 1) throw new RangeError("slices must number one fewer than boundaries");
  const b = m.boundaries;
  const comma = (i: number, n: number) => (i < n - 1 ? "," : "");
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
    "  ]",
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
export function sfzText(m: Manifest, dialect: "files" | "offsets", sourceFrames?: number): string {
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
