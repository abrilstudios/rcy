// RIFF WAVE with integer PCM. The reader reports what the header says and
// leaves policy (which rates, widths and channel counts to accept) to the caller.

export class WavFormatError extends Error {}

export interface Wav {
  /** Format tag; 1 is integer PCM, the only tag the reader accepts. */
  formatTag: number;
  channels: number;
  /** Frames per second. */
  sampleRate: number;
  bitsPerSample: number;
  /** Bytes per frame. */
  blockAlign: number;
  /** Whole frames in `data`. */
  frames: number;
  /** Byte offset of the first frame inside the file. */
  dataOffset: number;
  /** The frames, interleaved little-endian, trimmed to whole frames. */
  data: Uint8Array;
}

const ascii = (b: Uint8Array, at: number) => String.fromCharCode(b[at], b[at + 1], b[at + 2], b[at + 3]);

/**
 * Reads the first `fmt ` chunk and the first `data` chunk after it; every
 * other chunk is skipped. Throws WavFormatError when the bytes aren't a RIFF
 * WAVE file with format tag 1 and at least one whole frame.
 */
export function parseWav(bytes: Uint8Array): Wav {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (bytes.length < 12 || ascii(bytes, 0) !== "RIFF" || ascii(bytes, 8) !== "WAVE") {
    throw new WavFormatError("not a RIFF WAVE file");
  }
  let fmt: Omit<Wav, "frames" | "data" | "dataOffset"> | null = null;
  let data: Uint8Array | null = null;
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
export function encodeWav(wav: { channels: number; sampleRate: number; bitsPerSample: number; data: Uint8Array }): Uint8Array {
  const blockAlign = wav.channels * (wav.bitsPerSample / 8);
  if (!Number.isInteger(blockAlign) || blockAlign < 1 || wav.data.length % blockAlign !== 0) {
    throw new RangeError("data is not a whole number of frames");
  }
  const out = new Uint8Array(44 + wav.data.length);
  const view = new DataView(out.buffer);
  const tag = (at: number, s: string) => { for (let i = 0; i < 4; i++) out[at + i] = s.charCodeAt(i); };
  tag(0, "RIFF"); view.setUint32(4, 36 + wav.data.length, true); tag(8, "WAVE");
  tag(12, "fmt "); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, wav.channels, true);
  view.setUint32(24, wav.sampleRate, true); view.setUint32(28, wav.sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true); view.setUint16(34, wav.bitsPerSample, true);
  tag(36, "data"); view.setUint32(40, wav.data.length, true);
  out.set(wav.data, 44);
  return out;
}
