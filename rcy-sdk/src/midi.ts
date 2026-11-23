// Standard MIDI File, format 1: a tempo track and one note track.
import { roundScaled } from "./numbers.ts";

/** The largest value the three-byte tempo meta-event holds, in microseconds per quarter note. */
export const TEMPO_MAX = 0xffffff;

/** Microseconds per quarter note: the floor of one double division. */
export function tempoMicros(bpm: number): number {
  return Math.floor(60_000_000 / bpm);
}

/** Whether the tempo fits the tempo meta-event. */
export function tempoWritable(bpm: number): boolean {
  const t = tempoMicros(bpm);
  return t >= 1 && t <= TEMPO_MAX;
}

/** Nearest tick to a frame offset: floor(frame * bpm * division / (60 * sampleRate) + 1/2), exactly. */
export function tickAtFrame(frame: number, bpm: number, division: number, sampleRate: number): number {
  return Number(roundScaled(bpm, BigInt(frame) * BigInt(division), 60n * BigInt(sampleRate)));
}

export interface Note { key: number; velocity: number; onTick: number; offTick: number }

function quantity(v: number): number[] {
  const bytes = [v & 0x7f];
  for (v = Math.floor(v / 128); v > 0; v = Math.floor(v / 128)) bytes.unshift((v & 0x7f) | 0x80);
  return bytes;
}

function chunk(id: string, body: number[]): number[] {
  const n = body.length;
  return [...id].map((c) => c.charCodeAt(0)).concat([(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255], body);
}

/**
 * Track 1 holds a 4/4 time signature and the tempo at tick 0. Track 2 holds
 * the notes on channel 0 in the order given, which must be non-overlapping
 * and ascending; a note-off is status 0x80 with velocity 64. No running status.
 */
export function encodeMidi(song: { division: number; bpm: number; notes: Note[] }): Uint8Array {
  if (!tempoWritable(song.bpm)) throw new RangeError(`tempo ${song.bpm} BPM doesn't fit the MIDI tempo event`);
  const t = tempoMicros(song.bpm);
  const tempoTrack = [
    0, 0xff, 0x58, 4, 4, 2, 24, 8,
    0, 0xff, 0x51, 3, (t >>> 16) & 255, (t >>> 8) & 255, t & 255,
    0, 0xff, 0x2f, 0,
  ];
  const noteTrack: number[] = [];
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
