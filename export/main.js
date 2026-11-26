// rcy-export: cuts a drum break into equal slices and writes a kit.
// The SDK constant `rcySdk` is defined above this file by the bundler.
(function rcyExportMain() {
  "use strict";

  const NODE_MAJOR_REQUIRED = 22;
  const nodeMajor = Number(String(process.versions.node).split(".")[0]);
  if (!(nodeMajor >= NODE_MAJOR_REQUIRED)) {
    process.stderr.write(`rcy-export requires Node.js ${NODE_MAJOR_REQUIRED} or later (running ${process.versions.node})\n`);
    process.exitCode = 1;
    return;
  }

  const fs = require("node:fs");
  const path = require("node:path");

  // ---- Constants (SPEC.md, Constants table) ----

  /** Hz. The only rate the program accepts and writes; it does not resample. */
  const SAMPLE_RATE = 44100;
  /** bits per sample, signed little-endian PCM. The only format accepted and written, so slices are byte copies of the source. */
  const SAMPLE_WIDTH = 16;
  /** beats per measure. Every source is treated as 4/4. */
  const BEATS_PER_MEASURE = 4;
  /** MIDI key (middle C). Key of the first slice; later slices take the following keys. */
  const FIRST_KEY = 60;
  /** MIDI key. The highest MIDI key; a kit cut from audio holds at most LAST_KEY - FIRST_KEY + 1 slices. */
  const LAST_KEY = 127;
  /** slices per measure. One slice per quarter note. */
  const DEFAULT_RESOLUTION = 4;
  /** ticks per quarter note. Value written by the original implementation, so old and new MIDI files share a grid. */
  const MIDI_DIVISION = 960;
  /** MIDI velocity (1..127). Note-on velocity for every slice. */
  const MIDI_VELOCITY = 100;
  /** milliseconds. Default: source audio kept either side of each slice in its file when neither the command line nor the manifest states a buffer. 0 keeps a kit's files exactly the slices. */
  const DEFAULT_BUFFER_MS = 0;
  /** milliseconds. Parameter bound: the largest --buffer-ms accepted; longer than any drum hit's attack or tail needs. */
  const MAX_BUFFER_MS = 1000;
  // MANIFEST_VERSION is rcySdk.MANIFEST_VERSION and is used from there.

  // ---- Errors ----

  /** A refusal: exit 2, one stderr line "error: <message>". */
  class Refusal extends Error {
    /** @param {string} message */
    constructor(message) {
      super(message);
      this.name = "Refusal";
    }
  }

  /** A command-line syntax error (R01): exit 2, a line on stderr. */
  class UsageError extends Error {
    /** @param {string} message */
    constructor(message) {
      super(message);
      this.name = "UsageError";
    }
  }

  const USAGE =
    "usage: rcy-export (--input WAV | --preset ID | --from-manifest FILE) [--out DIR] [--measures M] [--resolution R] [--sfz-dialect {files,offsets}] [--exs] [--buffer-ms N]";

  // ---- Helpers ----

  /**
   * Absolute path: lexical normalisation, no symlink resolution, no trailing separator.
   * @param {string} p
   * @returns {string}
   */
  function absPath(p) {
    return path.resolve(p);
  }

  /**
   * @param {string} p
   * @returns {boolean} whether p names an existing regular file (symlinks followed)
   */
  function isExistingFile(p) {
    try {
      return fs.statSync(p).isFile();
    } catch {
      return false;
    }
  }

  /**
   * @param {string} p
   * @returns {boolean} whether p names an existing path that is not a directory
   */
  function existsNotDirectory(p) {
    let st;
    try {
      st = fs.statSync(p);
    } catch {
      return false;
    }
    return !st.isDirectory();
  }

  /**
   * @param {unknown} v
   * @returns {boolean} JSON integer: a number with integral value of magnitude below 2^53
   */
  function isInteger(v) {
    return typeof v === "number" && Number.isSafeInteger(v);
  }

  /**
   * @param {unknown} v
   * @returns {boolean}
   */
  function isNumber(v) {
    return typeof v === "number" && Number.isFinite(v);
  }

  /**
   * @param {unknown} v
   * @returns {boolean}
   */
  function isPlainObject(v) {
    return typeof v === "object" && v !== null && !Array.isArray(v);
  }

  /**
   * Compact JSON of a value; `undefined` (a missing member) prints as null.
   * @param {unknown} v
   * @returns {string}
   */
  function compactJson(v) {
    if (v === undefined || v === null) return "null";
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "number") {
      // SPEC-GAP: "shortest form" for numbers at or above 1e21 or below 1e-6 is
      // taken as JavaScript's shortest round-trip form (exponent notation, e.g. 1e+21).
      if (Object.is(v, -0)) return "0";
      return String(v);
    }
    if (typeof v === "string") return rcySdk.jsonString(v);
    if (Array.isArray(v)) return "[" + v.map(compactJson).join(",") + "]";
    if (typeof v === "object") {
      return (
        "{" +
        Object.keys(v)
          .map((k) => rcySdk.jsonString(k) + ":" + compactJson(/** @type {any} */ (v)[k]))
          .join(",") +
        "}"
      );
    }
    return "null";
  }

  /**
   * JSON.parse that also rejects numbers that overflow to infinity.
   * @param {string} text
   * @returns {{ok: true, value: any} | {ok: false}}
   */
  function parseJson(text) {
    let finite = true;
    let value;
    try {
      value = JSON.parse(text, function (_k, v) {
        if (typeof v === "number" && !Number.isFinite(v)) finite = false;
        return v;
      });
    } catch {
      return { ok: false };
    }
    // SPEC-GAP: a number literal too large for a double (e.g. 1e400) parses to
    // Infinity in JavaScript; since the Infinity literal makes a file invalid
    // JSON, such a file is treated as invalid JSON too.
    if (!finite) return { ok: false };
    return { ok: true, value };
  }

  // ---- Command line (R01, R02) ----

  /**
   * @typedef {{
   *   input?: string, preset?: string, fromManifest?: string, out?: string,
   *   measures?: bigint, resolution?: bigint, dialect: "files" | "offsets", exs: boolean
   * }} Options
   */

  /**
   * @param {string} text
   * @param {string} name
   * @returns {bigint}
   */
  function parseIntArg(text, name) {
    // SPEC-GAP: surrounding whitespace and a leading sign are accepted in an
    // integer option value.
    const t = text.trim();
    if (!/^[+-]?[0-9]+$/.test(t)) throw new UsageError(`argument ${name}: invalid int value: '${text}'`);
    return BigInt(t);
  }

  /**
   * @param {string[]} argv
   * @returns {Options}
   */
  function parseArgs(argv) {
    /** @type {Record<string, string>} */
    const valueOptions = {
      "--input": "input",
      "-i": "input",
      "--preset": "preset",
      "-p": "preset",
      "--from-manifest": "fromManifest",
      "-f": "fromManifest",
      "--out": "out",
      "-o": "out",
      "--measures": "measures",
      "-m": "measures",
      "--resolution": "resolution",
      "-r": "resolution",
      "--sfz-dialect": "dialect",
      "--buffer-ms": "bufferMs",
    };
    /** @type {Record<string, string>} */
    const raw = {};
    let exs = false;
    for (let i = 0; i < argv.length; i++) {
      const arg = argv[i];
      if (arg === "--exs") {
        exs = true;
        continue;
      }
      let name = arg;
      /** @type {string | undefined} */
      let value;
      // SPEC-GAP: the `--option=value` and `-iVALUE` spellings are accepted as
      // well as `--option value`.
      const eq = arg.indexOf("=");
      if (arg.startsWith("--") && eq > 2) {
        name = arg.slice(0, eq);
        value = arg.slice(eq + 1);
        if (name === "--exs") throw new UsageError("argument --exs: ignored explicit argument");
      } else if (/^-[a-z]./.test(arg) && !arg.startsWith("--") && Object.hasOwn(valueOptions, arg.slice(0, 2))) {
        name = arg.slice(0, 2);
        value = arg.slice(2);
      }
      if (!Object.hasOwn(valueOptions, name)) {
        if (arg.startsWith("-") && arg !== "-") throw new UsageError(`unrecognized arguments: ${arg}`);
        throw new UsageError(`unrecognized arguments: ${arg}`);
      }
      if (value === undefined) {
        if (i + 1 >= argv.length) throw new UsageError(`argument ${name}: expected one argument`);
        const next = argv[i + 1];
        // SPEC-GAP: a following token that starts with "-" and is not a negative
        // number is not taken as a value; the option then lacks its value (R01).
        // A following token that looks like an option (and not a negative number) is not a value.
        if (next.startsWith("-") && next.length > 1 && !/^-[0-9]/.test(next)) {
          throw new UsageError(`argument ${name}: expected one argument`);
        }
        value = next;
        i++;
      }
      // SPEC-GAP: an option given twice keeps its last value (only giving two
      // different source options is a conflict under R01).
      raw[valueOptions[name]] = value;
    }

    const sources = ["input", "preset", "fromManifest"].filter((k) => Object.hasOwn(raw, k));
    if (sources.length !== 1) {
      throw new UsageError("exactly one of --input, --preset and --from-manifest is required");
    }

    /** @type {Options} */
    const opts = { dialect: "files", exs };
    if (Object.hasOwn(raw, "input")) opts.input = raw.input;
    if (Object.hasOwn(raw, "preset")) opts.preset = raw.preset;
    if (Object.hasOwn(raw, "fromManifest")) opts.fromManifest = raw.fromManifest;
    if (Object.hasOwn(raw, "out")) opts.out = raw.out;
    // SPEC-GAP: a non-integer --measures or --resolution is a syntax error in every
    // mode, including --from-manifest where the values are otherwise ignored.
    if (Object.hasOwn(raw, "measures")) opts.measures = parseIntArg(raw.measures, "--measures");
    if (Object.hasOwn(raw, "resolution")) opts.resolution = parseIntArg(raw.resolution, "--resolution");
    if (Object.hasOwn(raw, "dialect")) {
      const d = raw.dialect;
      if (d !== "files" && d !== "offsets") {
        throw new UsageError(`argument --sfz-dialect: invalid choice: '${d}' (choose from 'files', 'offsets')`);
      }
      opts.dialect = d;
    }
    if (Object.hasOwn(raw, "bufferMs")) {
      if (!/^[0-9]+$/.test(raw.bufferMs) || Number(raw.bufferMs) > MAX_BUFFER_MS) {
        throw new UsageError(`argument --buffer-ms: expected a whole number from 0 to ${MAX_BUFFER_MS}, got '${raw.bufferMs}'`);
      }
      opts.bufferMs = Number(raw.bufferMs);
    }
    return opts;
  }

  // ---- Reading the source (R05) ----

  /**
   * @typedef {ReturnType<typeof rcySdk.parseWav>} Wav
   */

  /**
   * Reads and checks the source audio.
   * @param {string} srcAbs absolute path of the source
   * @returns {Wav}
   */
  function readSource(srcAbs) {
    let bytes;
    try {
      bytes = fs.readFileSync(srcAbs);
    } catch {
      // SPEC-GAP: a source that exists but cannot be read is reported with the
      // "cannot read audio file" message.
      throw new Refusal(`cannot read audio file: ${srcAbs}`);
    }
    /** @type {Wav} */
    let wav;
    try {
      wav = rcySdk.parseWav(bytes);
    } catch (e) {
      if (e instanceof rcySdk.WavFormatError) throw new Refusal(`cannot read audio file: ${srcAbs}`);
      throw e;
    }
    if (wav.formatTag !== 1 || wav.frames < 1) throw new Refusal(`cannot read audio file: ${srcAbs}`);
    if (wav.sampleRate !== SAMPLE_RATE) {
      throw new Refusal(`Unsupported sample rate: ${wav.sampleRate} Hz. RCY requires 44100 Hz audio files.`);
    }
    if (wav.bitsPerSample !== SAMPLE_WIDTH) {
      throw new Refusal(`unsupported sample width: ${wav.bitsPerSample} bits. RCY requires 16-bit PCM audio files.`);
    }
    if (wav.channels > 2) {
      throw new Refusal(`unsupported channel count: ${wav.channels}. RCY requires mono or stereo audio files.`);
    }
    return wav;
  }

  // ---- Kit model ----

  /**
   * @typedef {{
   *   srcAbs: string, wav: Wav, outAbs: string, stem: string,
   *   bpm: number, measures: number, boundaries: number[],
   *   slices: {key: number, file: string, role: string}[],
   *   bufferMs?: number, order?: number[] | null
   * }} KitPlan
   */

  /**
   * @param {number} bpm
   * @returns {void}
   */
  function checkTempo(bpm) {
    if (!rcySdk.tempoWritable(bpm)) {
      throw new Refusal(`tempo ${rcySdk.fixed(bpm, 2)} BPM cannot be written to MIDI`);
    }
  }

  /**
   * @param {string} outAbs
   * @returns {string}
   */
  function stemOf(outAbs) {
    return path.basename(outAbs);
  }

  /**
   * R09 overwrite check, R24 check (via buildOutputs).
   * @param {KitPlan} plan
   * @returns {void}
   */
  function checkNoOverwrite(plan) {
    for (let k = 0; k < plan.slices.length; k++) {
      const file = plan.slices[k].file;
      if (absPath(path.join(plan.outAbs, file)) === plan.srcAbs) {
        throw new Refusal(`slice ${k + 1} file '${file}' would overwrite the source`);
      }
    }
  }

  /**
   * Cut a source into equal slices (R07, R08, R09).
   * @param {string} srcAbs
   * @param {string} outAbs
   * @param {bigint} measures
   * @param {bigint} resolution
   * @returns {KitPlan}
   */
  function planFromAudio(srcAbs, outAbs, measures, resolution) {
    const wav = readSource(srcAbs);
    const N = wav.frames;
    const n = measures * resolution;
    if (n > BigInt(N)) throw new Refusal(`cannot cut ${N} frames into ${n} slices`);
    const maxSlices = BigInt(LAST_KEY - FIRST_KEY + 1);
    if (n > maxSlices) {
      const k = LAST_KEY - FIRST_KEY + 2;
      throw new Refusal(`slice ${k} key ${FIRST_KEY + k - 1} is not a MIDI note (0..127)`);
    }
    const measuresNum = Number(measures);
    const bpm = (60 * measuresNum * BEATS_PER_MEASURE) / (N / SAMPLE_RATE);
    checkTempo(bpm);
    const count = Number(n);
    const bigN = BigInt(N);
    /** @type {number[]} */
    const boundaries = [];
    for (let i = 0n; i <= n; i++) boundaries.push(Number((i * bigN) / n));
    const slices = [];
    for (let k = 1; k <= count; k++) {
      slices.push({ key: FIRST_KEY + k - 1, file: String(k).padStart(3, "0") + ".wav", role: "" });
    }
    /** @type {KitPlan} */
    const plan = { srcAbs, wav, outAbs, stem: stemOf(outAbs), bpm, measures: measuresNum, boundaries, slices };
    checkNoOverwrite(plan);
    return plan;
  }

  // ---- Outputs ----

  /**
   * @typedef {{
   *   slices: {file: string, bytes: Uint8Array}[],
   *   sfzName: string, sfz: string, midName: string, mid: Uint8Array,
   *   exsName: string, exs: Uint8Array | null,
   *   manifestName: string, manifest: string, sliceCount: number
   * }} Outputs
   */

  /**
   * Builds every output in memory; makes the R24 refusal. Writes nothing.
   * @param {KitPlan} plan
   * @param {"files" | "offsets"} dialect
   * @param {boolean} withExs
   * @returns {Outputs}
   */
  function buildOutputs(plan, dialect, withExs) {
    const { wav, boundaries } = plan;
    const source = path.relative(plan.outAbs, plan.srcAbs).split(path.sep).join("/");
    const kit = {
      source,
      sampleRate: SAMPLE_RATE,
      channels: wav.channels,
      bpm: plan.bpm,
      measures: plan.measures,
      boundaries: boundaries.slice(),
      slices: plan.slices.map((s) => ({ key: s.key, file: s.file, role: s.role })),
      bufferMs: plan.bufferMs,
      order: plan.order ?? undefined,
    };

    const sliceFiles = plan.slices.map((s, idx) => {
      const points = rcySdk.slicePoints(kit, idx, wav.frames);
      const data = wav.data.subarray(points.fileStart * wav.blockAlign, points.fileEnd * wav.blockAlign);
      const bytes = rcySdk.encodeWav({ channels: wav.channels, sampleRate: SAMPLE_RATE, bitsPerSample: SAMPLE_WIDTH, data });
      return { file: s.file, key: s.key, bytes, points };
    });

    /** @type {Uint8Array | null} */
    let exs = null;
    if (withExs) {
      const instrument = {
        name: plan.stem,
        folder: plan.outAbs,
        samples: sliceFiles.map((sf) => {
          const info = rcySdk.parseWav(sf.bytes);
          return {
            key: sf.key,
            fileName: sf.file,
            dataOffset: info.dataOffset,
            frames: info.frames,
            sampleRate: info.sampleRate,
            bitsPerSample: info.bitsPerSample,
            channels: info.channels,
            fileSize: sf.bytes.length,
            start: sf.points.offset,
            end: sf.points.end,
          };
        }),
      };
      const defect = rcySdk.exsDefect(instrument);
      if (defect !== null && defect !== undefined) throw new Refusal(`cannot write EXS instrument: ${defect}`);
      exs = rcySdk.encodeExs(instrument);
    }

    // R15: one note per slot of the play order, laid end to end from the region start.
    const playOrder = plan.order ?? plan.slices.map((_, idx) => idx + 1);
    let at = 0; // frames from the region start to the slot's start
    const notes = playOrder.map((number) => {
      const idx = number - 1;
      const s = at;
      at += boundaries[idx + 1] - boundaries[idx];
      return {
        key: plan.slices[idx].key,
        velocity: MIDI_VELOCITY,
        onTick: rcySdk.tickAtFrame(s, plan.bpm, MIDI_DIVISION, SAMPLE_RATE),
        offTick: rcySdk.tickAtFrame(at, plan.bpm, MIDI_DIVISION, SAMPLE_RATE),
      };
    });
    // SPEC-GAP: if encodeMidi throws for notes the spec allows (e.g. ticks that
    // collide in a hand-edited manifest), the run fails with exit 1 before any write.
    const mid = rcySdk.encodeMidi({ division: MIDI_DIVISION, bpm: plan.bpm, notes });
    const sfz = rcySdk.sfzText(kit, dialect, wav.frames);
    const manifest = rcySdk.manifestText(kit);

    return {
      slices: sliceFiles.map((sf) => ({ file: sf.file, bytes: sf.bytes })),
      sfzName: `${plan.stem}.sfz`,
      sfz,
      midName: `${plan.stem}.mid`,
      mid,
      exsName: `${plan.stem}.exs`,
      exs,
      manifestName: `${plan.stem}.rcy.json`,
      manifest,
      sliceCount: plan.slices.length,
    };
  }

  /**
   * Writes the kit (R23, R19). Manifest last.
   * @param {string} outAbs
   * @param {Outputs} o
   * @returns {void}
   */
  function writeOutputs(outAbs, o) {
    fs.mkdirSync(outAbs, { recursive: true });
    for (const s of o.slices) fs.writeFileSync(path.join(outAbs, s.file), s.bytes);
    // SPEC-GAP: the SFZ and MIDI files are written after the slice files and
    // before the EXS file; the spec fixes only EXS after slices and manifest last.
    fs.writeFileSync(path.join(outAbs, o.sfzName), Buffer.from(o.sfz, "utf8"));
    fs.writeFileSync(path.join(outAbs, o.midName), o.mid);
    const exsPath = path.join(outAbs, o.exsName);
    if (o.exs !== null) {
      fs.writeFileSync(exsPath, o.exs);
    } else {
      // SPEC-GAP: only a non-directory entry named <stem>.exs is removed; a
      // directory of that name is left alone.
      let st = null;
      try {
        st = fs.lstatSync(exsPath);
      } catch {
        st = null;
      }
      if (st !== null && !st.isDirectory()) fs.unlinkSync(exsPath);
    }
    fs.writeFileSync(path.join(outAbs, o.manifestName), Buffer.from(o.manifest, "utf8"));
  }

  // ---- Modes ----

  /**
   * @param {Options} opts
   * @returns {{plan: KitPlan, resolutionValue: number}}
   */
  function modeInput(opts) {
    if (opts.out === undefined) throw new Refusal("--out is required with --preset or --input");
    if (existsNotDirectory(opts.out)) throw new Refusal(`output path is not a directory: ${opts.out}`);
    if (opts.measures === undefined) throw new Refusal("--measures is required with --input");
    const input = /** @type {string} */ (opts.input);
    if (!isExistingFile(input)) throw new Refusal(`input file not found: ${input}`);
    const resolution = opts.resolution === undefined ? BigInt(DEFAULT_RESOLUTION) : opts.resolution;
    if (opts.measures < 1n || resolution < 1n) throw new Refusal("--measures and --resolution must be positive");
    const plan = planFromAudio(absPath(input), absPath(opts.out), opts.measures, resolution);
    return { plan, resolutionValue: plan.slices.length / plan.measures };
  }

  /**
   * @param {Options} opts
   * @returns {{plan: KitPlan, resolutionValue: number}}
   */
  function modePreset(opts) {
    if (opts.out === undefined) throw new Refusal("--out is required with --preset or --input");
    if (existsNotDirectory(opts.out)) throw new Refusal(`output path is not a directory: ${opts.out}`);
    const catalogDir = process.env.RCY_PRESETS;
    if (catalogDir === undefined || catalogDir === "") {
      throw new Refusal("RCY_PRESETS is not set; it must name the preset catalog directory");
    }
    const catalogMsg = `preset catalog not found: ${catalogDir}/presets.json`;
    const catalogAbs = absPath(catalogDir);
    let text;
    try {
      text = fs.readFileSync(path.join(catalogAbs, "presets.json"), "utf8");
    } catch {
      throw new Refusal(catalogMsg);
    }
    const parsed = parseJson(text);
    if (!parsed.ok || !isPlainObject(parsed.value)) throw new Refusal(catalogMsg);
    const catalog = parsed.value;
    const id = /** @type {string} */ (opts.preset);
    // SPEC-GAP: an entry that is not a JSON object is treated as no entry for the id.
    if (!Object.hasOwn(catalog, id) || !isPlainObject(catalog[id])) throw new Refusal(`preset '${id}' not found`);
    const entry = catalog[id];
    /** @type {bigint} */
    let measures;
    if (opts.measures !== undefined) {
      measures = opts.measures;
    } else {
      // SPEC-GAP: a catalog `measures` that is absent, null or not an integer
      // counts as "has no measures".
      if (!isInteger(entry.measures)) throw new Refusal(`preset '${id}' has no measures; pass --measures`);
      measures = BigInt(entry.measures);
    }
    const resolution = opts.resolution === undefined ? BigInt(DEFAULT_RESOLUTION) : opts.resolution;
    if (measures < 1n || resolution < 1n) throw new Refusal("--measures and --resolution must be positive");
    // SPEC-GAP: a `file` member that is missing or not a string names no audio
    // file; it is reported as preset audio not found at the catalog directory.
    const audioAbs = typeof entry.file === "string" && entry.file !== "" ? path.resolve(catalogAbs, entry.file) : catalogAbs;
    // SPEC-GAP: an audio path that exists but is not a regular file (e.g. a
    // directory) is reported as "preset audio not found".
    if (!isExistingFile(audioAbs)) throw new Refusal(`preset audio not found: ${audioAbs}`);
    const plan = planFromAudio(audioAbs, absPath(opts.out), measures, resolution);
    return { plan, resolutionValue: plan.slices.length / plan.measures };
  }

  /**
   * @param {Options} opts
   * @returns {{plan: KitPlan, resolutionValue: number}}
   */
  function modeManifest(opts) {
    const given = /** @type {string} */ (opts.fromManifest);
    const manifestAbs = absPath(given);
    // SPEC-GAP: a manifest path that exists but is not a regular file is
    // reported as "manifest not found".
    if (!isExistingFile(manifestAbs)) throw new Refusal(`manifest not found: ${given}`);
    const manifestDir = path.dirname(manifestAbs);
    if (opts.out !== undefined && existsNotDirectory(opts.out)) {
      throw new Refusal(`output path is not a directory: ${opts.out}`);
    }
    const outAbs = opts.out !== undefined ? absPath(opts.out) : manifestDir;
    const stem = stemOf(outAbs);

    let text;
    try {
      text = fs.readFileSync(manifestAbs, "utf8");
    } catch {
      // SPEC-GAP: a manifest file that exists but cannot be read is reported
      // as "manifest not found".
      throw new Refusal(`manifest not found: ${given}`);
    }
    const parsed = parseJson(text);
    if (!parsed.ok) throw new Refusal(`${given}: invalid JSON`);
    const m = parsed.value;
    if (!isPlainObject(m)) throw new Refusal("manifest must be a JSON object");

    /** @param {string} k */
    const get = (k) => (Object.hasOwn(m, k) ? m[k] : undefined);

    const rcy = get("rcy");
    if (!isInteger(rcy) || rcy !== rcySdk.MANIFEST_VERSION) {
      throw new Refusal(`unsupported manifest version ${compactJson(rcy)}, expected ${rcySdk.MANIFEST_VERSION}`);
    }
    const region = get("region");
    if (!isPlainObject(region)) throw new Refusal("region must be an object with start and end");
    const slices = get("slices");
    if (!Array.isArray(slices)) throw new Refusal("slices must be a list");
    const boundaries = get("boundaries");
    if (!Array.isArray(boundaries) || !boundaries.every(isInteger)) {
      throw new Refusal("boundaries must be a list of integers");
    }
    const b = boundaries.length;
    if (slices.length !== b - 1) {
      throw new Refusal(`${b} boundaries define ${b - 1} slices, but ${slices.length} slices are listed`);
    }
    const source = get("source");
    if (typeof source !== "string") throw new Refusal(`source must be a string, got ${compactJson(source)}`);
    const regionStart = Object.hasOwn(region, "start") ? region.start : undefined;
    const regionEnd = Object.hasOwn(region, "end") ? region.end : undefined;
    /** @type {[string, unknown][]} */
    const intMembers = [
      ["sample_rate", get("sample_rate")],
      ["channels", get("channels")],
      ["measures", get("measures")],
      ["start", regionStart],
      ["end", regionEnd],
    ];
    for (const [name, v] of intMembers) {
      if (!isInteger(v)) throw new Refusal(`${name} must be an integer, got ${compactJson(v)}`);
    }
    const sampleRate = /** @type {number} */ (get("sample_rate"));
    const channels = /** @type {number} */ (get("channels"));
    const measures = /** @type {number} */ (get("measures"));
    const start = /** @type {number} */ (regionStart);
    const end = /** @type {number} */ (regionEnd);
    const bpm = get("bpm");
    if (!isNumber(bpm)) throw new Refusal(`bpm must be a number, got ${compactJson(bpm)}`);

    // SPEC-GAP: each row of the R22 table is checked across all slices before
    // the next row, so the first defect is found row by row, then slice by slice;
    // within the index/key row a slice's index is checked before its key.
    for (const s of slices) {
      if (!isPlainObject(s)) throw new Refusal("each slice must be a JSON object");
    }
    /** @param {any} s @param {string} k */
    const sget = (s, k) => (Object.hasOwn(s, k) ? s[k] : undefined);
    for (const s of slices) {
      for (const k of ["index", "key"]) {
        const v = sget(s, k);
        if (!isInteger(v)) throw new Refusal(`${k} must be an integer, got ${compactJson(v)}`);
      }
    }
    for (const s of slices) {
      const v = sget(s, "file");
      if (typeof v !== "string") throw new Refusal(`file must be a string, got ${compactJson(v)}`);
    }
    for (const s of slices) {
      if (Object.hasOwn(s, "role") && typeof s.role !== "string") {
        throw new Refusal(`slice role must be a string, got ${compactJson(s.role)}`);
      }
    }
    if (source === "") throw new Refusal("source must be a non-empty path");
    if (sampleRate <= 0) throw new Refusal(`sample_rate must be positive, got ${compactJson(sampleRate)}`);
    if (channels !== 1 && channels !== 2) throw new Refusal(`channels must be 1 or 2, got ${compactJson(channels)}`);
    if (bpm <= 0) throw new Refusal(`bpm must be a positive number, got ${compactJson(bpm)}`);
    const bufferMs = get("buffer_ms");
    if (bufferMs !== undefined && (!isInteger(bufferMs) || bufferMs < 0 || bufferMs > MAX_BUFFER_MS)) {
      throw new Refusal(`buffer_ms must be an integer from 0 to ${MAX_BUFFER_MS}, got ${compactJson(bufferMs)}`);
    }
    if (measures < 1) throw new Refusal(`measures must be >= 1, got ${compactJson(measures)}`);
    if (start < 0) throw new Refusal(`region start must be >= 0, got ${compactJson(start)}`);
    if (b < 2) throw new Refusal("boundaries must hold at least the region start and end");
    for (let i = 1; i < b; i++) {
      if (!(boundaries[i] > boundaries[i - 1])) throw new Refusal("boundaries must be strictly increasing");
    }
    if (boundaries[0] !== start || boundaries[b - 1] !== end) {
      throw new Refusal(
        `boundaries must run from region start ${start} to region end ${end}, got ${boundaries[0]}..${boundaries[b - 1]}`
      );
    }
    slices.forEach((s, p) => {
      if (s.index !== p + 1) {
        throw new Refusal(`slice at position ${p + 1} has index ${s.index}; indices are 1-based and sequential`);
      }
    });
    for (const s of slices) {
      if (s.key < 0 || s.key > LAST_KEY) throw new Refusal(`slice ${s.index} key ${s.key} is not a MIDI note (0..127)`);
    }
    for (const s of slices) {
      if (s.file === "") throw new Refusal(`slice ${s.index} has an empty file name`);
    }
    for (const s of slices) {
      const f = s.file;
      if (f.includes("/") || f.includes("\\") || f === "." || f === "..") {
        throw new Refusal(`slice ${s.index} file '${f}' must be a bare file name`);
      }
    }
    const seen = new Set();
    for (const s of slices) {
      if (seen.has(s.file)) throw new Refusal(`slice file '${s.file}' is used by more than one slice`);
      seen.add(s.file);
    }
    const kitNames = new Set([`${stem}.sfz`, `${stem}.mid`, `${stem}.rcy.json`, `${stem}.exs`]);
    for (const s of slices) {
      if (kitNames.has(s.file)) throw new Refusal(`slice ${s.index} file '${s.file}' is a kit file name`);
    }
    // R22: order, when present, lists slice numbers in play order (WINDOW.md W25).
    let order = null;
    if (Object.hasOwn(m, "order")) {
      const o = m.order;
      const ok = Array.isArray(o) && o.length >= 1 &&
        o.every((v) => isInteger(v) && v >= 1 && v <= slices.length);
      if (!ok) throw new Refusal(`order must be a list of slice numbers from 1 to ${slices.length}`);
      order = o.slice();
    }
    checkTempo(bpm);

    const srcAbs = path.resolve(manifestDir, source);
    // SPEC-GAP: a source path that exists but is not a regular file is
    // reported as "source audio not found".
    if (!isExistingFile(srcAbs)) throw new Refusal(`source audio not found: ${srcAbs}`);
    const wav = readSource(srcAbs);
    if (sampleRate !== wav.sampleRate) {
      throw new Refusal(`manifest sample_rate ${sampleRate} != source ${wav.sampleRate} (${srcAbs})`);
    }
    if (channels !== wav.channels) {
      throw new Refusal(`manifest channels ${channels} != source ${wav.channels} (${srcAbs})`);
    }
    if (end > wav.frames) throw new Refusal(`region end ${end} exceeds source length ${wav.frames} (${srcAbs})`);

    /** @type {KitPlan} */
    const plan = {
      srcAbs,
      wav,
      outAbs,
      stem,
      bpm,
      measures,
      boundaries: boundaries.slice(),
      slices: slices.map((s) => ({ key: s.key, file: s.file, role: Object.hasOwn(s, "role") ? s.role : "" })),
      bufferMs,
      order,
    };
    checkNoOverwrite(plan);
    return { plan, resolutionValue: plan.slices.length / plan.measures };
  }

  // ---- Main ----

  /**
   * @param {string[]} argv
   * @returns {number} exit code
   */
  function run(argv) {
    /** @type {Options} */
    let opts;
    try {
      opts = parseArgs(argv);
    } catch (e) {
      if (e instanceof UsageError) {
        process.stderr.write(`${USAGE}\nrcy-export: error: ${e.message}\n`);
        return 2;
      }
      throw e;
    }
    try {
      const { plan, resolutionValue } =
        opts.input !== undefined ? modeInput(opts) : opts.preset !== undefined ? modePreset(opts) : modeManifest(opts);
      // The command line's buffer wins over the manifest's, which wins over the default.
      plan.bufferMs = opts.bufferMs ?? plan.bufferMs ?? DEFAULT_BUFFER_MS;
      const outputs = buildOutputs(plan, opts.dialect, opts.exs);
      writeOutputs(plan.outAbs, outputs);
      const lines = [
        `source: ${plan.srcAbs}`,
        `tempo: ${rcySdk.fixed(plan.bpm, 2)} BPM (${plan.measures} measures x ${rcySdk.significant(resolutionValue, 6)})`,
        `slices: ${outputs.sliceCount}`,
        `sfz: ${path.join(plan.outAbs, outputs.sfzName)} (${opts.dialect})`,
        `midi: ${path.join(plan.outAbs, outputs.midName)}`,
      ];
      if (opts.exs) lines.push(`exs: ${path.join(plan.outAbs, outputs.exsName)}`);
      lines.push(`manifest: ${path.join(plan.outAbs, outputs.manifestName)}`);
      process.stdout.write(lines.join("\n") + "\n");
      return 0;
    } catch (e) {
      if (e instanceof Refusal) {
        // SPEC-GAP: a CR or LF inside a refusal message (e.g. from a path) is
        // replaced by a space so the refusal stays exactly one stderr line.
        process.stderr.write(`error: ${e.message.replace(/[\r\n]/g, " ")}\n`);
        return 2;
      }
      throw e;
    }
  }

  try {
    process.exitCode = run(process.argv.slice(2));
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    process.stderr.write(`rcy-export: ${msg.replace(/[\r\n]/g, " ")}\n`);
    process.exitCode = 1;
  }
})();
