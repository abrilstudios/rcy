import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import * as source from "../src/index.ts";

// Every test runs twice: on the TypeScript source and on dist/rcy-sdk.js, the
// file a generated program embeds.
const here = import.meta.dirname;
const distPath = path.join(here, "../dist/rcy-sdk.js");
const dist = new Function(fs.readFileSync(distPath, "utf8") + "\nreturn rcySdk;")() as typeof source;

test("dist/rcy-sdk.js is what bin/build.cjs writes from src/", () => {
  const out = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "rcy-sdk-")), "rcy-sdk.js");
  execFileSync(process.execPath, [path.join(here, "../bin/build.cjs"), out]);
  assert.ok(fs.readFileSync(out).equals(fs.readFileSync(distPath)), "run `node bin/build.cjs`");
});

for (const [label, sdk] of [["src", source], ["dist", dist]] as const) {
const { encodeExs, encodeMidi, encodeWav, exsDefect, fixed, manifestText, parseWav, sfzText, slicePoints, bufferFrames, shortestWithPoint, significant, tempoMicros, tempoWritable, tickAtFrame } = sdk;
const isWavFormatError = (e: unknown) => (e as Error).constructor.name === "WavFormatError";

test(label + " " + "numbers: exact rounding and plain notation", () => {
  assert.equal(fixed(120.125, 2), "120.13"); // an exact tie rounds up
  assert.equal(fixed(137.71790859793566, 2), "137.72");
  assert.equal(shortestWithPoint(120), "120.0");
  assert.equal(shortestWithPoint(137.71790859793566), "137.71790859793566");
  assert.equal(significant(8 / 3, 6), "2.66667");
  assert.equal(significant(4, 6), "4");
  assert.equal(significant(0.5, 6), "0.5");
});

test(label + " " + "wav: encode then parse returns the frames", () => {
  const data = Uint8Array.from([1, 0, 2, 0, 3, 0, 4, 0]);
  const bytes = encodeWav({ channels: 2, sampleRate: 44100, bitsPerSample: 16, data });
  assert.equal(bytes.length, 52);
  const wav = parseWav(bytes);
  assert.deepEqual([wav.channels, wav.sampleRate, wav.bitsPerSample, wav.blockAlign, wav.frames], [2, 44100, 16, 4, 2]);
  assert.deepEqual([...wav.data], [...data]);
});

test(label + " " + "wav: skips other chunks, honours pad bytes, ignores a trailing partial frame", () => {
  const plainWav = encodeWav({ channels: 1, sampleRate: 44100, bitsPerSample: 16, data: Uint8Array.from([5, 0, 6, 0]) });
  const list = Uint8Array.from([0x4c, 0x49, 0x53, 0x54, 3, 0, 0, 0, 9, 9, 9, 0]); // "LIST", length 3, pad
  const bytes = new Uint8Array([...plainWav.subarray(0, 36), ...list, ...plainWav.subarray(36), 7]);
  new DataView(bytes.buffer).setUint32(bytes.length - 9, 5, true); // data length 5: two frames and one stray byte
  const wav = parseWav(bytes);
  assert.equal(wav.frames, 2);
  assert.deepEqual([...wav.data], [5, 0, 6, 0]);
});

test(label + " " + "wav: refuses non-PCM, truncated and frameless files", () => {
  const ok = encodeWav({ channels: 1, sampleRate: 44100, bitsPerSample: 16, data: Uint8Array.from([1, 0]) });
  const extensible = ok.slice(); new DataView(extensible.buffer).setUint16(20, 0xfffe, true);
  const truncated = ok.subarray(0, ok.length - 1);
  const empty = encodeWav({ channels: 1, sampleRate: 44100, bitsPerSample: 16, data: new Uint8Array(0) });
  for (const bad of [extensible, truncated, empty, new TextEncoder().encode("not a wav")]) {
    assert.throws(() => parseWav(bad), isWavFormatError);
  }
});

test(label + " " + "midi: ticks are the nearest tick, on the grid for even cuts", () => {
  const bpm = (60 * 2 * 4) / (1817184 / 44100);
  assert.deepEqual([0, 1, 2, 3, 4].map((i) => tickAtFrame((i * 1817184) / 32, bpm, 960, 44100)), [0, 240, 480, 720, 960]);
  assert.equal(tickAtFrame(20000, 100, 960, 44100), 726);
  assert.equal(tempoMicros(70), 857142);
  assert.equal(tempoWritable(3), false);
  assert.equal(tempoWritable(70000000), false);
});

test(label + " " + "midi: file bytes", () => {
  const bytes = encodeMidi({ division: 960, bpm: 120, notes: [{ key: 60, velocity: 100, onTick: 0, offTick: 960 }, { key: 61, velocity: 100, onTick: 960, offTick: 1920 }] });
  const hex = Buffer.from(bytes).toString("hex");
  assert.equal(hex,
    "4d546864000000060001000203c0" +
    "4d54726b00000013" + "00ff580404021808" + "00ff5103" + "07a120" + "00ff2f00" +
    "4d54726b00000016" + "00903c64" + "8740803c40" + "00903d64" + "8740803d40" + "00ff2f00");
});

test(label + " " + "manifest and sfz text", () => {
  const m = { source: "../in.wav", sampleRate: 44100, channels: 1, bpm: 120, measures: 1, boundaries: [0, 100, 250],
    slices: [{ key: 60, file: "001.wav", role: "" }, { key: 61, file: "snäre.wav", role: "snare" }] };
  const text = manifestText(m);
  assert.deepEqual(JSON.parse(text).slices[1], { index: 2, start: 100, end: 250, key: 61, file: "snäre.wav", role: "snare" });
  const lines = text.split("\n");
  assert.equal(lines[5], '  "bpm": 120.0,');
  assert.equal(lines[12], "    0,");
  assert.ok(text.includes('"file": "sn\\u00e4re.wav",'));
  assert.ok(text.endsWith("}\n"));
  assert.equal(sfzText(m, "files"), "<region> sample=001.wav key=60\n<region> sample=snäre.wav key=61");
  assert.equal(sfzText(m, "offsets"), "<region> sample=../in.wav start=0 end=99 key=60\n<region> sample=../in.wav start=100 end=249 key=61 // snare");
});

test(label + " " + "a kit with a buffer", () => {
  const m = { source: "../in.wav", sampleRate: 44100, channels: 1, bpm: 120, measures: 1, boundaries: [10, 100, 250], bufferMs: 1,
    slices: [{ key: 60, file: "001.wav", role: "" }, { key: 61, file: "002.wav", role: "" }] };
  assert.equal(bufferFrames(1, 44100), 44);
  assert.equal(bufferFrames(20, 44100), 882);
  // the first slice's file starts at the source's first frame, the last one's ends at its last
  assert.deepEqual(slicePoints(m, 0, 260), { fileStart: 0, fileEnd: 144, offset: 10, end: 100 });
  assert.deepEqual(slicePoints(m, 1, 260), { fileStart: 56, fileEnd: 260, offset: 44, end: 194 });
  assert.equal(manifestText(m).split("\n")[7], '  "buffer_ms": 1,');
  assert.equal(manifestText({ ...m, bufferMs: 0 }), manifestText({ ...m, bufferMs: undefined }));
  // order: source order adds no member; another order is written after slices; a bad one throws
  assert.equal(manifestText({ ...m, order: [1, 2] }), manifestText(m));
  assert.ok(manifestText({ ...m, order: [2, 1] }).endsWith('  ],\n  "order": [\n    2,\n    1\n  ]\n}\n'));
  assert.deepEqual(JSON.parse(manifestText({ ...m, order: [2, 1] })).order, [2, 1]);
  assert.deepEqual(JSON.parse(manifestText({ ...m, order: [1, 1, 2] })).order, [1, 1, 2]);
  assert.deepEqual(JSON.parse(manifestText({ ...m, order: [2] })).order, [2]);
  assert.equal(manifestText({ ...m, order: [] }), manifestText(m));
  assert.throws(() => manifestText({ ...m, order: [0, 1] }), RangeError);
  assert.throws(() => manifestText({ ...m, order: [3] }), RangeError);
  assert.equal(sfzText(m, "files", 260), "<region> sample=001.wav offset=10 end=99 key=60\n<region> sample=002.wav offset=44 end=193 key=61");
  assert.throws(() => sfzText(m, "files"), RangeError);
  const sample = { key: 60, fileName: "001.wav", dataOffset: 44, frames: 144, sampleRate: 44100, bitsPerSample: 16, channels: 1, fileSize: 332 };
  const inst = { name: "k", folder: "/k", samples: [{ ...sample, start: 10, end: 100 }] };
  const zone = new DataView(encodeExs(inst).buffer, 84 + 80 + 84);
  assert.deepEqual([zone.getUint32(12, true), zone.getUint32(16, true)], [10, 100]);
  assert.equal(exsDefect({ ...inst, samples: [{ ...sample, start: 100, end: 145 }] }), "sample 001.wav plays frames 100..145, outside its 144 frames");
});

test(label + " " + "exs: block layout", () => {
  const sample = (i: number) => ({ key: 60 + i, fileName: `00${i + 1}.wav`, dataOffset: 44, frames: 1000 + i, sampleRate: 44100, bitsPerSample: 16, channels: 2, fileSize: 44 + 4 * (1000 + i) });
  const bytes = encodeExs({ name: "kit", folder: "/tmp/kit", samples: [sample(0), sample(1)] });
  assert.equal(bytes.length, 84 * 7 + 80 + 2 * 140 + 132 + 2 * 592 + 1108);
  const view = new DataView(bytes.buffer);
  const text = (at: number, n: number) => Buffer.from(bytes.subarray(at, at + n)).toString("latin1").replace(/\0+$/, "");
  assert.deepEqual([...bytes.subarray(0, 4)], [1, 1, 0, 0]);
  assert.equal(text(16, 4), "TBOS");
  assert.equal(text(20, 64), "kit.exs");
  assert.deepEqual([4, 8, 12, 16].map((o) => view.getUint32(84 + o, true)), [2, 1, 2, 1]);
  const zone2 = 164 + 224 + 84;
  assert.deepEqual([...bytes.subarray(zone2, zone2 + 11)], [1, 61, 0, 0, 0, 0, 61, 61, 0, 0, 127]);
  assert.deepEqual([16, 24, 92].map((o) => view.getUint32(zone2 + o, true)), [1001, 1001, 1]);
  const sample1 = 164 + 2 * 224 + 216 + 84;
  assert.deepEqual([0, 4, 8, 12, 16, 20, 32].map((o) => view.getUint32(sample1 + o, true)), [44, 1000, 44100, 16, 2, 2, 4044]);
  assert.equal(text(sample1 + 28, 4), "EVAW");
  assert.equal(text(sample1 + 80, 256), "/tmp/kit");
  assert.equal(text(sample1 + 336, 256), "001.wav");
  assert.throws(() => encodeExs({ name: "kit", folder: "tmp/kit", samples: [sample(0)] }), RangeError);
  assert.throws(() => encodeExs({ name: "kit", folder: "/tmp/kit", samples: [{ ...sample(0), fileName: "snäre.wav" }] }), RangeError);
  assert.throws(() => encodeExs({ name: "kit", folder: "/tmp/kit", samples: [{ ...sample(0), key: 128 }] }), RangeError);
});

test(label + " exs: same bytes as the instrument Logic Pro 11.2.2 loaded", () => {
  // The fixture is that file with its folder fields rewritten to "/kit".
  const kit = JSON.parse(fs.readFileSync(path.join(here, "fixtures/amen-rcy.json"), "utf8"));
  const b: number[] = kit.boundaries;
  const samples = b.slice(1).map((end, i) => {
    const frames = end - b[i];
    return { key: 60 + i, fileName: String(i + 1).padStart(3, "0") + ".wav", dataOffset: 44, frames, sampleRate: 44100,
      bitsPerSample: 16, channels: kit.channels, fileSize: 44 + frames * kit.channels * 2 };
  });
  const bytes = encodeExs({ name: "amen-rcy", folder: "/kit", samples });
  assert.ok(Buffer.from(bytes).equals(fs.readFileSync(path.join(here, "fixtures/amen-rcy.exs"))));
});

test(label + " exs: defects, first one wins", () => {
  const sample = { key: 60, fileName: "001.wav", dataOffset: 44, frames: 10, sampleRate: 44100, bitsPerSample: 16, channels: 1, fileSize: 64 };
  const inst = { name: "kit", folder: "/a/kit", samples: [sample] };
  assert.equal(exsDefect(inst), null);
  assert.equal(exsDefect({ ...inst, name: "k".repeat(59) }), null);
  assert.equal(exsDefect({ ...inst, name: "k".repeat(60), folder: "x" }), "instrument name is longer than 59 bytes: " + "k".repeat(60));
  assert.equal(exsDefect({ ...inst, name: "b\u00e4r" }), "instrument name is not printable ASCII: b\u00e4r");
  assert.equal(exsDefect({ ...inst, folder: "/a/" + "d".repeat(253) }), "folder is longer than 255 bytes: /a/" + "d".repeat(253));
  assert.equal(exsDefect({ ...inst, folder: "a/kit" }), "folder is not an absolute path without a trailing slash: a/kit");
  assert.equal(exsDefect({ ...inst, samples: [sample, { ...sample, fileName: "s".repeat(60) + ".wav" }] }), "sample file name is longer than 63 bytes: " + "s".repeat(60) + ".wav");
  assert.equal(exsDefect({ ...inst, samples: [{ ...sample, key: 128 }] }), "key 128 is not a MIDI note (0..127)");
  assert.equal(exsDefect({ ...inst, samples: [] }), "an instrument needs at least one sample");
  assert.throws(() => encodeExs({ ...inst, name: "b\u00e4r" }), RangeError);
});
}
