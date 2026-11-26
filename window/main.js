// rcy-window: a slicing window for drum breaks (WINDOW.md, rcy-window/spec-v1).
//
// Bundled after the SDK by `node rcy-sdk/dist/bundle.cjs output/main.js
// output/rcy-window`; the constant `rcySdk` is defined above this file. The
// main process validates the launch (W03), reads the source, hands the page
// the samples and writes the manifest on Save (W04). Every edit, the undo
// history, drawing, audition and onset detection live in the page, so that
// rcyWindowState() reflects an edit as soon as its event handler returns.
(function rcyWindow() {
  "use strict";

  const fs = require("node:fs");
  const path = require("node:path");
  const electron = require("electron");
  const { app, BrowserWindow, ipcMain, Menu } = electron;

  // ---------------------------------------------------------------------
  // Constants (WINDOW.md, Constants table). Each is defined here only; the
  // page receives them with the samples.
  // ---------------------------------------------------------------------

  // MIDI key number. The key of the first slice after a split, as rcy-export assigns it.
  const FIRST_KEY = 60;
  // MIDI key number. The highest MIDI key; no edit may produce a higher one.
  const LAST_KEY = 127;
  // Frames. The narrowest view: wide enough to see a zero crossing, narrow
  // enough that one frame is many pixels wide, so a cut lands on one frame.
  const MIN_VIEW_FRAMES = 32;
  // Ratio of spans (unitless). One zoom-in key press halves the visible span; zoom-out doubles it.
  const ZOOM_STEP = 0.5;
  // CSS pixels. A press within this distance of a boundary's line acts on that boundary.
  const PICK_PIXELS = 6;
  // CSS pixels. Width of the L and R flags in the strip; a press on a flag acts
  // on its locator, so the flag a person sees is the handle they grab.
  const FLAG_PIXELS = 12;
  // Milliseconds. Audition ends each slice with a fade to zero of this length, the value rcy uses.
  const TAIL_FADE_MS = 3;
  // Exponent (unitless). The fade gain is t^3 for t falling from 1 to 0, rcy's "exponential" curve.
  const TAIL_FADE_POWER = 3;
  // Slices per measure. Initial value of the resolution control.
  const DEFAULT_RESOLUTION = 4;
  // Sensitivity units (0 to 99). Initial value of the sensitivity control.
  const DEFAULT_SENSITIVITY = 50;
  // Characters (keyboard keys). Key i (0-based) in this string plays slice i + 1.
  const AUDITION_KEYS = "1234567890qwertyuiop";
  // Decimal places. The tempo control shows the tempo rounded to this many
  // places, the precision rcy-export prints a tempo with. The stored tempo is
  // not rounded.
  const TEMPO_DECIMALS = 2;

  // A tempo as the command line or the control gives it: digits, optionally a
  // point and more digits.
  const TEMPO_GRAMMAR = /^\d+(\.\d+)?$/;

  const CONSTANTS = {
    FIRST_KEY, LAST_KEY, MIN_VIEW_FRAMES, ZOOM_STEP, PICK_PIXELS, FLAG_PIXELS, TAIL_FADE_MS,
    TAIL_FADE_POWER, DEFAULT_RESOLUTION, DEFAULT_SENSITIVITY, AUDITION_KEYS, TEMPO_DECIMALS,
  };

  // ---------------------------------------------------------------------
  // Launch checks (W01 to W03). They run synchronously, before Electron is
  // ready and before any window exists.
  // ---------------------------------------------------------------------

  function refuse(message) {
    try {
      fs.writeSync(2, `rcy-window: ${message}\n`);
    } catch (_) {
      // stderr closed; the exit code still tells the caller.
    }
    app.exit(2);
    process.exit(2);
  }

  function realOrResolved(p) {
    try {
      return fs.realpathSync(path.resolve(p));
    } catch (_) {
      return path.resolve(p);
    }
  }

  // W01: the program's arguments follow its own path in process.argv.
  // Electron's switches (and Playwright's) come before that path.
  function programArguments() {
    const self = realOrResolved(__filename);
    for (let i = 1; i < process.argv.length; i++) {
      const a = process.argv[i];
      if (a.startsWith("-")) continue;
      if (realOrResolved(a) === self) return process.argv.slice(i + 1);
    }
    // SPEC-GAP: the program's own path was not found in process.argv (a
    // packaged run); fall back to Electron's convention for where it is.
    return process.argv.slice(process.defaultApp ? 2 : 1);
  }

  let launchOptions = null;
  const startedAt = new Date();

  function parseArguments(args) {
    const opts = { manifest: null, out: null, record: null, split: null, resolution: null, sensitivity: null,
                   bpm: null, view: null, select: null, task: null, "expect-slices": null };
    const VALUE_OPTIONS = Object.keys(opts).map((k) => "--" + k);
    for (let i = 0; i < args.length; i++) {
      const a = args[i];
      let name = null;
      let value = null;
      if (VALUE_OPTIONS.includes(a)) {
        name = a.slice(2);
        if (i + 1 >= args.length) refuse(`${a} needs a value`);
        value = args[++i];
      } else if (a.includes("=") && VALUE_OPTIONS.includes(a.slice(0, a.indexOf("=")))) {
        // SPEC-GAP: W02 shows `--manifest FILE`; the `--manifest=FILE`
        // spelling is accepted as the same option.
        name = a.slice(2, a.indexOf("="));
        value = a.slice(a.indexOf("=") + 1);
      } else {
        refuse(`unknown argument: ${a}`);
      }
      if (value === "" || (name !== "task" && value.startsWith("--"))) refuse(`--${name} needs a value`);
      if (opts[name] !== null) refuse(`--${name} is given twice`);
      opts[name] = value;
    }
    if (opts.manifest === null) refuse("--manifest FILE is required");
    if (opts.record === null) refuse("--record FILE is required");
    const whole = (name, lo, hi) => {
      if (opts[name] === null) return;
      if (!/^\d+$/.test(opts[name]) || Number(opts[name]) < lo || Number(opts[name]) > hi) refuse(`--${name} must be a whole number from ${lo} to ${hi}`);
      opts[name] = Number(opts[name]);
    };
    if (opts.split !== null && opts.split !== "measures" && opts.split !== "transients") refuse("--split must be measures or transients");
    whole("sensitivity", 0, 99);
    whole("select", 0, 128);
    whole("expect-slices", 1, 128);
    if (opts.resolution !== null && !["1", "2", "4", "8", "16", "32"].includes(opts.resolution)) refuse("--resolution must be 1, 2, 4, 8, 16 or 32");
    if (opts.bpm !== null) {
      if (!TEMPO_GRAMMAR.test(opts.bpm)) refuse("--bpm must be a decimal number of beats per minute");
      opts.bpm = Number(opts.bpm);
    }
    if (opts.view !== null) {
      const m = /^(\d+):(\d+)$/.exec(opts.view);
      if (!m || Number(m[1]) >= Number(m[2])) refuse("--view must be START:END in frames with START below END");
      opts.view = [Number(m[1]), Number(m[2])];
    }
    launchOptions = opts;
    return opts;
  }

  function isPlainObject(v) {
    return v !== null && typeof v === "object" && !Array.isArray(v);
  }

  function loadLaunch() {
    const opts = parseArguments(programArguments());
    // Paths are made absolute lexically; symbolic links are not resolved.
    const manifestPath = path.resolve(opts.manifest);
    const outPath = opts.out === null ? manifestPath : path.resolve(opts.out);

    // 2. FILE exists and is valid JSON holding an object.
    let text;
    try {
      text = fs.readFileSync(manifestPath, "utf8");
    } catch (e) {
      refuse(`cannot read manifest ${manifestPath}: ${e.code || e.message}`);
    }
    let m;
    try {
      m = JSON.parse(text);
    } catch (e) {
      refuse(`manifest is not valid JSON: ${e.message}`);
    }
    if (!isPlainObject(m)) refuse("manifest does not hold a JSON object");

    // 3. rcy equals MANIFEST_VERSION.
    if (m.rcy !== rcySdk.MANIFEST_VERSION) {
      refuse(`manifest rcy is ${JSON.stringify(m.rcy)}, expected ${rcySdk.MANIFEST_VERSION}`);
    }

    // 4. boundaries.
    const b = m.boundaries;
    if (!Array.isArray(b) || b.length < 2) refuse("boundaries must be an array of at least two integers");
    for (let i = 0; i < b.length; i++) {
      if (typeof b[i] !== "number" || !Number.isInteger(b[i])) refuse(`boundary ${i} is not an integer`);
      if (i > 0 && !(b[i] > b[i - 1])) refuse(`boundaries are not strictly increasing at index ${i}`);
    }
    if (b[0] < 0) refuse("the first boundary is below 0");

    // 5. slices.
    const s = m.slices;
    if (!Array.isArray(s) || s.length !== b.length - 1) {
      refuse(`slices must be an array of ${b.length - 1} objects, one per pair of neighbouring boundaries`);
    }
    const slices = [];
    for (let i = 0; i < s.length; i++) {
      const sl = s[i];
      if (!isPlainObject(sl)) refuse(`slice ${i + 1} is not an object`);
      if (typeof sl.key !== "number" || !Number.isInteger(sl.key) || sl.key < 0 || sl.key > LAST_KEY) {
        refuse(`slice ${i + 1} key is not an integer from 0 to ${LAST_KEY}`);
      }
      if (typeof sl.file !== "string") refuse(`slice ${i + 1} file is not a string`);
      if (sl.role !== undefined && typeof sl.role !== "string") refuse(`slice ${i + 1} role is not a string`);
      slices.push({ key: sl.key, file: sl.file, role: sl.role === undefined ? "" : sl.role });
    }

    // 5a. order (W25): absent, or each slice number from 1 to the slice count once.
    let order = slices.map((_, i) => i);
    if (Object.prototype.hasOwnProperty.call(m, "order")) {
      const o = m.order;
      const ok = Array.isArray(o) && o.length >= 1 &&
        o.every((v) => typeof v === "number" && Number.isInteger(v) && v >= 1 && v <= slices.length);
      if (!ok) refuse(`order must be a list of slice numbers from 1 to ${slices.length}`);
      order = o.map((v) => v - 1);
    }

    // 6. source.
    if (typeof m.source !== "string" || m.source === "") refuse("source is not a file name");
    const sourcePath = path.resolve(path.dirname(manifestPath), m.source);
    let wav;
    try {
      wav = rcySdk.parseWav(fs.readFileSync(sourcePath));
    } catch (e) {
      if (e instanceof rcySdk.WavFormatError) refuse(`source ${sourcePath} is not a usable WAV file: ${e.message}`);
      refuse(`cannot read source ${sourcePath}: ${e.code || e.message}`);
    }
    if (wav.bitsPerSample !== 16) refuse(`source has ${wav.bitsPerSample} bits per sample; 16 are required`);

    // 7. the last boundary is at most N.
    if (b[b.length - 1] > wav.frames) {
      refuse(`the last boundary ${b[b.length - 1]} is beyond the source's ${wav.frames} frames`);
    }

    // 8. bpm, measures, sample_rate, channels.
    if (typeof m.bpm !== "number" || !Number.isFinite(m.bpm) || !(m.bpm > 0)) refuse("bpm is not a finite number above 0");
    if (typeof m.measures !== "number" || !Number.isInteger(m.measures) || m.measures < 1) {
      refuse("measures is not an integer of at least 1");
    }
    const hasRate = Object.prototype.hasOwnProperty.call(m, "sample_rate");
    const hasChannels = Object.prototype.hasOwnProperty.call(m, "channels");
    if (hasRate && m.sample_rate !== wav.sampleRate) {
      refuse(`sample_rate ${JSON.stringify(m.sample_rate)} differs from the source's ${wav.sampleRate}`);
    }
    if (hasChannels && m.channels !== wav.channels) {
      refuse(`channels ${JSON.stringify(m.channels)} differs from the source's ${wav.channels}`);
    }

    return {
      manifestPath,
      outPath,
      sourcePath,
      wav,
      // Kept as read; replaced by the source's values on save only when absent.
      sampleRate: hasRate ? m.sample_rate : wav.sampleRate,
      channels: hasChannels ? m.channels : wav.channels,
      bpm: m.bpm,
      measures: m.measures,
      bufferMs: Number.isInteger(m.buffer_ms) && m.buffer_ms > 0 ? m.buffer_ms : 0,
      boundaries: b.slice(),
      slices,
      order,
    };
  }

  const launch = loadLaunch();
  if (launchOptions.view && launchOptions.view[1] > launch.wav.frames) refuse(`--view ends beyond the source's ${launch.wav.frames} frames`);
  // A new tempo must be in the range rcy-export applies (SPEC.md R15), so the
  // window is never launched towards a manifest the export refuses. A --bpm
  // equal to the manifest's tempo changes nothing and is not checked.
  if (launchOptions.bpm !== null && launchOptions.bpm !== launch.bpm && !rcySdk.tempoWritable(launchOptions.bpm)) {
    refuse(`--bpm ${launchOptions.bpm} cannot be written to MIDI`);
  }
  const recordPath = path.resolve(launchOptions.record);

  // ---------------------------------------------------------------------
  // Save (W04).
  // ---------------------------------------------------------------------

  function validEdit(boundaries, slices) {
    if (!Array.isArray(boundaries) || !Array.isArray(slices)) return false;
    if (boundaries.length < 2 || slices.length !== boundaries.length - 1) return false;
    for (let i = 0; i < boundaries.length; i++) {
      if (!Number.isInteger(boundaries[i])) return false;
      if (i > 0 && boundaries[i] <= boundaries[i - 1]) return false;
    }
    if (boundaries[0] < 0 || boundaries[boundaries.length - 1] > launch.wav.frames) return false;
    return slices.every((s) => s && Number.isInteger(s.key) && s.key >= 0 && s.key <= LAST_KEY &&
      typeof s.file === "string" && typeof s.role === "string");
  }

  // A tempo the person or the command line set must be one rcy-export can
  // write; the tempo as read is saved unchanged whatever it is.
  function validTempo(bpm) {
    if (bpm === launch.bpm) return true;
    return typeof bpm === "number" && Number.isFinite(bpm) && rcySdk.tempoWritable(bpm);
  }

  function saveManifest(boundaries, slices, bpm, order) {
    if (!validEdit(boundaries, slices)) return { ok: false, error: "the edit is not a valid manifest" };
    if (!Array.isArray(order) || order.length < 1 ||
        !order.every((v) => Number.isInteger(v) && v >= 0 && v < slices.length)) {
      return { ok: false, error: "the slice order is not valid" };
    }
    if (!validTempo(bpm)) return { ok: false, error: "the tempo cannot be written to MIDI" };
    const rel = path.relative(path.dirname(launch.outPath), launch.sourcePath).split(path.sep).join("/");
    let text;
    try {
      text = rcySdk.manifestText({
        source: rel,
        sampleRate: launch.sampleRate,
        channels: launch.channels,
        bpm,
        measures: launch.measures,
        bufferMs: launch.bufferMs,
        boundaries,
        slices: slices.map((s) => ({ key: s.key, file: s.file, role: s.role })),
        order: order.map((v) => v + 1),
      });
    } catch (e) {
      return { ok: false, error: e.message };
    }
    try {
      fs.writeFileSync(launch.outPath, Buffer.from(text, "utf8"));
    } catch (e) {
      return { ok: false, error: `${launch.outPath}: ${e.code ? e.code + " " : ""}${e.message}` };
    }
    return { ok: true };
  }

  // ---------------------------------------------------------------------
  // The page. pageProgram runs in the renderer; its source is embedded in a
  // data: URL, so the window reads no other file and loads nothing remote.
  // ---------------------------------------------------------------------

  function pageProgram() {
    "use strict";
    const { ipcRenderer } = require("electron");

    // Layout in CSS pixels (appearance only; not part of the spec's table).
    const MARGIN = 14; // left and right margin around the plot, so locators at 0 and N stay pickable
    const STRIP_H = 26; // marker strip above the plots: triangles, L/R flags, slice numbers
    const AXIS_H = 20; // time axis under the plots
    const OVER_H = 38; // overview of the whole file
    const CH_GAP = 6; // gap between channel plots

    let K = null; // the constants, as the main process defines them
    let ready = false;
    let N = 0;
    let sr = 44100;
    let nch = 1;
    // f32, i16 and pyramid hold the audio as the window shows and plays it:
    // the source, with the slices between L and R laid out in play order (W25).
    let f32 = []; // per channel, -1..1
    let i16 = []; // per channel, the stored values
    let pyramid = []; // per channel, min/max/sum-of-squares levels for drawing
    let srcF32 = []; // the source as read, per channel
    let srcI16 = [];
    let srcPyramid = [];
    let srcN = 0; // the source's frame count; N is the length of the audio as shown
    let base = null; // { b, s }: the manifest's boundaries and slices while the order is not source order
    let slot = null; // the selected slot (index into order), for copy, paste, duplicate and cut
    let clip = null; // the copied slice (source index)
    // W26: the loop is slots loopA to loopE - 1. L is drawn at the start of slot loopA and R at the end of slot loopE - 1.
    let loopA = 0;
    let loopE = 0;
    const ORDER_MAX_SLOTS = 256; // parameter: longest order paste and duplicate build; bounds the audio laid out
    let arrangedKey = ""; // names the order and cuts f32 was laid out for; empty for source order
    let info = null;

    // boundaries and slices are in play order, as shown: slot i of the plot
    // holds source slice order[i] (0-based). In source order they are the
    // manifest's own; toSource() gives the manifest's at any time.
    let boundaries = [];
    let slices = [];
    let order = [];
    let bpm = 0; // beats per minute; the manifest's value until the tempo control or --bpm changes it
    let tempoSession = null; // the history position of the latest edit while it is a tempo change
    let history = []; // snapshots; history[0] is the manifest as read
    let hpos = 0;
    let selected = null;
    let viewStart = 0;
    let viewEnd = 0;
    let transientSession = null; // set while the latest edit is a Split by Transients
    let candidates = null;

    // ---- elements
    const $ = (id) => document.getElementById(id);
    const area = $("area");
    const waveCanvas = $("wave");
    const overCanvas = $("over");
    const btnMeasures = $("split-measures");
    const btnTransients = $("split-transients");
    const selResolution = $("resolution");
    const rngSensitivity = $("sensitivity");
    const sensValue = $("sens-value");
    const fldTempo = $("bpm");
    const statusReadout = $("status-readout");
    const statusMsg = $("status-msg");
    const dialog = $("discard-confirm");

    let layout = { plot: { x: 0, y: 0, width: 1, height: 1 }, plots: [], cssW: 1, cssH: 1, dpr: 1 };

    window.rcyWindowState = function rcyWindowState() {
      const p = layout.plot;
      return {
        ready,
        frames: srcN,
        shownFrames: N,
        slot,
        boundaries: toSource().b,
        slices: toSource().s,
        order: order.map((v) => v + 1),
        loop: [loopA + 1, loopE],
        shown: boundaries.slice(),
        viewStart,
        viewEnd,
        plot: { x: p.x, y: p.y, width: p.width, height: p.height },
        selected,
        cursor: editCursor,
        playing: voice !== null,
        bpm,
        dirty: hpos !== 0,
      };
    };

    // ------------------------------------------------------------------
    // Edits and history
    // ------------------------------------------------------------------

    const pad3 = (n) => String(n).padStart(3, "0") + ".wav";
    const copySlices = (ss) => ss.map((s) => ({ key: s.key, file: s.file, role: s.role }));
    const identity = (n) => Array.from({ length: n }, (_, i) => i);
    const reordered = () => base !== null;
    const isIdentity = (o, n) => o.length === n && o.every((v, i) => v === i);
    const orderText = (o) => o.map((v) => v + 1).join(" ");
    // The manifest's boundaries and slices: the shown ones put back in source order.
    function toSource() {
      if (base === null) return { b: boundaries.slice(), s: copySlices(slices) };
      return { b: base.b.slice(), s: copySlices(base.s) };
    }
    // A snapshot holds source-order boundaries and slices, the tempo and the order.
    const snapshot = () => { const src = toSource(); return { b: src.b, s: src.s, bpm, o: order.slice(), l: [loopA, loopE] }; };
    // W25: a shown line stands for a source cut: the start of the slice in the slot on its
    // right, and the last line for the end of the last slot's slice.
    function sourceCut(i) {
      return i < order.length ? order[i] : order[order.length - 1] + 1;
    }
    // The order after source slices lo..hi (0-based) merge into slice lo. Slots that
    // played the merged slices one after another become one slot. first[k] and last[k]
    // are the new slots old slot k became.
    function orderAfterMerge(o, lo, hi) {
      const out = [], first = [], last = [];
      let prev = null;
      for (const v of o) {
        const merged = v >= lo && v <= hi;
        const follows = merged && prev !== null && prev >= lo && prev <= hi && v === prev + 1;
        if (!follows) out.push(v < lo ? v : merged ? lo : v - (hi - lo));
        first.push(out.length - 1); last.push(out.length - 1);
        prev = v;
      }
      return { o: out, first, last };
    }
    // The order after source slice j splits in two: each slot of j plays both halves.
    function orderAfterSplit(o, j) {
      const out = [], first = [], last = [];
      for (const v of o) {
        first.push(out.length);
        if (v < j) out.push(v); else if (v === j) out.push(j, j + 1); else out.push(v + 1);
        last.push(out.length - 1);
      }
      return { o: out, first, last };
    }
    // W26: the loop holds the same slots after the order was rewritten.
    const loopAfter = (m) => [m.first[loopA], m.last[loopE - 1] + 1];
    const REGION_END = "The first and last line are the ends of the sliced region and stay where they are";
    // W26: what Save keeps. The loop's slots name source slices lo to hi; the kit
    // holds those slices and the order is the loop's slots numbered within them.
    function kept() {
      const src = toSource();
      const o = order.slice(loopA, loopE);
      const lo = Math.min(...o), hi = Math.max(...o);
      const wasDefault = namesDefault(src.s);
      const s = copySlices(src.s.slice(lo, hi + 1));
      s.forEach((x, j) => { x.key -= lo; if (wasDefault) x.file = pad3(j + 1); });
      return { b: src.b.slice(lo, hi + 2), s, o: o.map((v) => v - lo) };
    }
    // Both splits replace every slice, so they start from source order.
    function toSourceOrder() {
      if (!reordered()) return;
      const src = toSource();
      applySnapshot({ b: src.b, s: src.s, bpm, o: identity(src.s.length) });
      slot = null; clip = null;
    }
    // Lays the audio out for the order: before L and after R as the source, between them the
    // slots end to end. The shown audio is longer or shorter than the source when slices repeat or are left out.
    function arrange(srcB) {
      const key = reordered() ? order.join(",") + "|" + srcB.join(",") : "";
      if (key === arrangedKey) return;
      arrangedKey = key;
      const oldN = N;
      if (key === "") { f32 = srcF32; i16 = srcI16; pyramid = srcPyramid; N = srcN; }
      else {
        const L = srcB[0];
        const R = srcB[srcB.length - 1];
        let total = 0;
        for (const v of order) total += srcB[v + 1] - srcB[v];
        const n = srcN - (R - L) + total;
        const lay = (src, Type) => src.map((x) => {
          const d = new Type(n);
          d.set(x.subarray(0, L), 0);
          let pos = L;
          for (const v of order) {
            const seg = x.subarray(srcB[v], srcB[v + 1]);
            d.set(seg, pos);
            pos += seg.length;
          }
          d.set(x.subarray(R), pos);
          return d;
        });
        f32 = lay(srcF32, Float32Array);
        i16 = lay(srcI16, Int16Array);
        pyramid = f32.map(buildPyramid);
        N = n;
      }
      if (ready && N !== oldN) {
        const full = viewStart <= 0 && viewEnd >= oldN;
        if (full) { viewStart = 0; viewEnd = N; } else setView(Math.min(viewStart, Math.max(0, N - 1)), Math.min(viewEnd, N) - Math.min(viewStart, Math.max(0, N - 1)));
      }
      stopAudio();
      fullBuffer = null;
      candidates = null;
      overviewCache = null;
      if (ready) scheduleWave();
    }
    const tempoText = (v) => String(Number(v.toFixed(K.TEMPO_DECIMALS)));
    let tempoRefused = false; // the press or key now being handled made the control refuse its text
    let tempoTouched = false; // the person typed or stepped in the tempo control since the window last wrote it
    function showTempo() { fldTempo.value = tempoText(bpm); tempoTouched = false; }
    const namesDefault = (ss) => ss.every((s, i) => s.file === pad3(i + 1));

    function applySnapshot(snap) {
      const o = snap.o;
      const b = [snap.b[0]];
      const s = [];
      for (let i = 0; i < o.length; i++) { b.push(b[i] + snap.b[o[i] + 1] - snap.b[o[i]]); s.push(snap.s[o[i]]); }
      boundaries = b;
      slices = copySlices(s);
      order = o.slice();
      // a snapshot without a loop has the whole order as its loop
      const l = snap.l || [0, o.length];
      loopA = Math.min(Math.max(l[0], 0), o.length - 1);
      loopE = Math.min(Math.max(l[1], loopA + 1), o.length);
      base = isIdentity(o, snap.s.length) ? null : { b: snap.b.slice(), s: copySlices(snap.s) };
      if (slot !== null && slot >= order.length) slot = null;
      arrange(snap.b);
      bpm = snap.bpm;
      showTempo();
      if (selected !== null && selected >= boundaries.length) selected = null;
    }

    function commit(b, s, sel, o, l) {
      history.length = hpos + 1;
      history.push({ b: b.slice(), s: copySlices(s), bpm, o: o ? o.slice() : identity(s.length), l: l ? l.slice() : null });
      hpos = history.length - 1;
      applySnapshot(history[hpos]);
      selected = sel === undefined ? selected : sel;
      if (selected !== null && selected >= boundaries.length) selected = null;
      transientSession = null;
      tempoSession = null;
      const rec = { what: "", boundaries: toSource().b, slices: toSource().s.length, bpm };
      if (reordered()) rec.order = order.map((v) => v + 1);
      lastEdit = logEvent("edit", rec);
      changed();
    }
    // W08: source cut c moves by delta frames, limited by its neighbours in the source.
    // The order and the loop are kept. Returns false when nothing changed.
    function moveSourceCut(c, delta, sel) {
      const src = toSource(), n = src.b.length - 1;
      if (c <= 0 || c >= n) { message(REGION_END); return false; }
      const f = Math.min(Math.max(src.b[c] + delta, src.b[c - 1] + 1), src.b[c + 1] - 1);
      if (f === src.b[c]) return false;
      const nb = src.b.slice();
      nb[c] = f;
      commit(nb, src.s, sel, order, [loopA, loopE]);
      message(`Moved cut ${c} to frame ${f}`);
      return true;
    }
    // W26: L or R goes to a slice edge. Nothing else changes.
    function setLoop(a, e, from) {
      if (a === from[0] && e === from[1]) { changed(); return; }
      const looping = voice !== null && voice.loop;
      loopA = a; loopE = e;
      history.length = hpos + 1;
      history.push(snapshot());
      hpos = history.length - 1;
      transientSession = null;
      tempoSession = null;
      const text = `Loop: slot ${a + 1} to slot ${e} (${e - a} slice${e - a === 1 ? "" : "s"})`;
      lastEdit = logEvent("edit", { what: text, boundaries: toSource().b, slices: toSource().s.length, bpm, order: order.map((v) => v + 1), loop: [a + 1, e] });
      if (looping) playLoop();
      message(text);
      changed();
    }

    // W24: a tempo change is an edit. One that directly follows another
    // replaces it, so a run of steps on the control is one undo step.
    function setTempo(value) {
      if (value === bpm) return;
      const follows = tempoSession !== null && tempoSession === hpos && hpos === history.length - 1;
      // Back at the text the run started from: the run is removed, which
      // restores the exact tempo that text was showing.
      if (follows && tempoText(history[hpos - 1].bpm) === tempoText(value)) {
        history.length = hpos;
        hpos--;
        tempoSession = null;
      } else {
        if (follows) history[hpos].bpm = value;
        else {
          history.length = hpos + 1;
          history.push(Object.assign(snapshot(), { bpm: value }));
          hpos = history.length - 1;
        }
        tempoSession = hpos;
      }
      applySnapshot(history[hpos]);
      transientSession = null;
      logEvent("edit", { what: `Tempo ${tempoText(bpm)} bpm`, boundaries: toSource().b, slices: slices.length, bpm });
      message(`Tempo ${tempoText(bpm)} bpm`);
      changed();
    }

    // The control shows a rounded tempo, so its text is read only after the
    // person typed or stepped in it; an untouched tempo stays exact.
    // Returns false when the text was refused.
    function onTempo() {
      if (!ready || !tempoTouched) return true;
      const text = fldTempo.value.trim();
      if (text === tempoText(bpm)) { showTempo(); return true; }
      const v = Number(text);
      if (!info.tempoGrammar.test(text) || !ipcRenderer.sendSync("rcy-tempo-writable", v)) {
        showTempo();
        tempoRefused = true;
        message("Tempo not changed: it must be a decimal number of beats per minute that a MIDI file can hold", true);
        return false;
      }
      tempoTouched = false;
      setTempo(v);
      return true;
    }

    function undo() {
      if (drag) return;
      transientSession = null;
      tempoSession = null;
      if (hpos === 0) { message("Nothing to undo"); return; }
      hpos--;
      applySnapshot(history[hpos]);
      logEvent("undo", { boundaries: toSource().b, order: order.map((v) => v + 1), loop: [loopA + 1, loopE], bpm });
      message("Undo");
      changed();
    }

    function redo() {
      if (drag) return;
      transientSession = null;
      tempoSession = null;
      if (hpos >= history.length - 1) { message("Nothing to redo"); return; }
      hpos++;
      applySnapshot(history[hpos]);
      logEvent("redo", { boundaries: toSource().b, order: order.map((v) => v + 1), loop: [loopA + 1, loopE], bpm });
      message("Redo");
      changed();
    }

    // W25: a new order is one edit. o holds source slice indexes in play order.
    function setOrder(o, text, newSlot, l) {
      const src = toSource();
      const looping = voice !== null && voice.loop; // the L-to-R loop goes on in the new order
      history.length = hpos + 1;
      history.push({ b: src.b, s: src.s, bpm, o: o.slice(), l: l === undefined ? [loopA, loopE] : l });
      hpos = history.length - 1;
      applySnapshot(history[hpos]);
      if (looping) playLoop();
      slot = newSlot === undefined || newSlot === null || newSlot >= order.length ? null : newSlot;
      selected = null;
      editCursor = null;
      transientSession = null;
      tempoSession = null;
      lastEdit = logEvent("edit", { what: text, boundaries: src.b, slices: slices.length, bpm, order: order.map((v) => v + 1) });
      message(text);
      changed();
    }
    // Moves the slice in slot i so that it sits before the slice now in slot j (j = slice count: last).
    function moveSlice(i, j) {
      if (j === i || j === i + 1) return;
      const o = order.slice();
      const v = o.splice(i, 1)[0];
      o.splice(j > i ? j - 1 : j, 0, v);
      setOrder(o, `Order ${orderText(o)}`, j > i ? j - 1 : j);
    }
    function sourceOrder() {
      if (!reordered()) return;
      setOrder(identity(toSource().s.length), "Source order", null, null);
    }
    // W25: copy, paste, duplicate and cut act on the selected slot.
    function insertAfter(v, at, what) {
      if (order.length >= ORDER_MAX_SLOTS) { message(`${what} not applied: the order already holds ${ORDER_MAX_SLOTS} slices`, true); return; }
      const o = order.slice();
      o.splice(at + 1, 0, v);
      const l = at < loopA ? [loopA + 1, loopE + 1] : at < loopE ? [loopA, loopE + 1] : [loopA, loopE];
      setOrder(o, `${what} slice ${v + 1}: order ${orderText(o)}`, at + 1, l);
    }
    function copySlot() {
      if (slot === null) { message("Click a slice's number to select it first"); return; }
      clip = order[slot];
      message(`Copied slice ${clip + 1}`);
    }
    function pasteSlot() {
      if (clip === null) { message("Nothing copied"); return; }
      if (clip >= toSource().s.length) { message("The copied slice no longer exists"); return; }
      insertAfter(clip, slot === null ? order.length - 1 : slot, "Pasted");
    }
    function duplicateSlot() {
      if (slot === null) { message("Click a slice's number to select it first"); return; }
      insertAfter(order[slot], slot, "Duplicated");
    }
    function cutSlot() {
      if (slot === null) { message("Click a slice's number to select it first"); return; }
      if (order.length === 1) { message("The last slice can't be cut"); return; }
      clip = order[slot];
      const o = order.slice();
      o.splice(slot, 1);
      // a loop left with no slot becomes the whole order
      const l = slot < loopA ? [loopA - 1, loopE - 1] : slot < loopE ? (loopE - 1 > loopA ? [loopA, loopE - 1] : null) : [loopA, loopE];
      setOrder(o, `Cut slice ${clip + 1}: order ${orderText(o)}`, Math.min(slot, o.length - 1), l);
    }
    // The slot a slice dropped at x goes before: the number of slices whose middle is left of x.
    function dropSlot(x) {
      let j = 0;
      for (let i = 0; i < slices.length; i++) if ((xOfFrame(boundaries[i]) + xOfFrame(boundaries[i + 1])) / 2 < x) j++;
      return j;
    }

    function clampMove(i, f, b) {
      const lo = i === 0 ? 0 : b[i - 1] + 1;
      const hi = i === b.length - 1 ? N : b[i + 1] - 1;
      return Math.min(Math.max(f, lo), hi);
    }

    // W08: a move changes that cut only; slices keep key, file and role.
    function moveBy(i, delta) {
      moveSourceCut(sourceCut(i), delta, i);
    }

    // W09
    function addCut(f) {
      const shown = boundaries;
      if (!(f > shown[0] && f < shown[shown.length - 1])) { message("A cut must lie inside the sliced region"); return; }
      let k = 1;
      while (shown[k] < f) k++;
      if (shown[k] === f) { message(`Frame ${f} already is a boundary`); return; }
      // W25: the pointer is in slot k-1; the cut goes the same distance into that slot's slice
      const src = toSource();
      const b = src.b;
      const at = k - 1;
      const j = order[at];
      f = b[j] + (f - shown[at]);
      k = j + 1;
      const m = orderAfterSplit(order, j);
      if (m.o.length > ORDER_MAX_SLOTS) { message(`No cut added: the order would hold more than ${ORDER_MAX_SLOTS} slices`, true); return; }
      // the new cut goes between b[k-1] and b[k]; slice index k-1 (0-based) splits
      const wasDefault = namesDefault(src.s);
      const left = src.s[k - 1];
      const s = copySlices(src.s);
      const right = { key: left.key + 1, file: "", role: "" };
      for (let j = k; j < s.length; j++) s[j].key += 1;
      s.splice(k, 0, right);
      if (s.some((x) => x.key > K.LAST_KEY)) {
        message(`No cut added: a slice key would exceed ${K.LAST_KEY}`);
        return;
      }
      if (wasDefault) {
        s.forEach((x, i) => { x.file = pad3(i + 1); });
      } else {
        const used = new Set(s.map((x) => x.file));
        let n = s.length;
        while (used.has(pad3(n))) n++;
        right.file = pad3(n);
      }
      const nb = b.slice();
      nb.splice(k, 0, f);
      slot = null; clip = null;
      commit(nb, s, m.first[at] + 1, m.o, loopAfter(m));
      message(`Cut added at frame ${f}`);
    }

    // W10
    function removeCut(i) {
      const src = toSource();
      // W25: the line is the start of the slice on its right; that slice merges into the one before it in the source
      i = sourceCut(i);
      if (i <= 0 || i >= src.b.length - 1) { message("The ends of the sliced region can't be removed"); return; }
      const m = orderAfterMerge(order, i - 1, i);
      const wasDefault = namesDefault(src.s);
      const s = copySlices(src.s);
      s.splice(i, 1); // the slice on the cut's right merges into the one on its left
      for (let j = i; j < s.length; j++) s[j].key -= 1;
      // SPEC-GAP: W10 lowers every later key by one without a floor; a key
      // below 0 would make the manifest invalid, so such a removal is refused.
      if (s.some((x) => x.key < 0)) { message("Cut not removed: a slice key would fall below 0"); return; }
      if (wasDefault) s.forEach((x, j) => { x.file = pad3(j + 1); });
      const nb = src.b.slice();
      const f = nb[i];
      nb.splice(i, 1);
      slot = null; clip = null;
      commit(nb, s, null, m.o, loopAfter(m));
      message(`Cut at frame ${f} removed`);
    }

    function splitSlices(nb) {
      const s = [];
      for (let k = 1; k < nb.length; k++) s.push({ key: K.FIRST_KEY + k - 1, file: pad3(k), role: "" });
      return s;
    }

    // W11
    function splitByMeasures() {
      toSourceOrder();
      const m = info.measures;
      const r = Number(selResolution.value);
      const L = boundaries[0];
      const R = boundaries[boundaries.length - 1];
      if (!Number.isInteger(m) || m < 1) { message(`Split by Measures: measures ${m} is not a positive integer`); return; }
      const n = m * r;
      if (n > R - L) { message(`Split by Measures: ${n} slices don't fit in the ${R - L} frames between L and R`); return; }
      if (K.FIRST_KEY + n - 1 > K.LAST_KEY) {
        message(`Split by Measures: ${m} × ${r} = ${n} slices would need keys up to ${K.FIRST_KEY + n - 1}, above ${K.LAST_KEY}`);
        return;
      }
      const nb = [];
      const span = BigInt(R - L);
      const bn = BigInt(n);
      for (let i = 0; i <= n; i++) nb.push(L + Number((BigInt(i) * span) / bn));
      commit(nb, splitSlices(nb), null);
      message(`Split by Measures: ${n} slices (${m} measure${m === 1 ? "" : "s"} × ${r})`);
    }

    // W12
    function transientSnapshot(sens, L, R) {
      const cand = ensureCandidates();
      const theta = thresholdFor(sens);
      let cuts = cand.filter((c) => c.odf >= theta && c.frame > L && c.frame + 1 < R);
      const maxCuts = K.LAST_KEY - K.FIRST_KEY;
      let dropped = 0;
      if (cuts.length > maxCuts) {
        dropped = cuts.length - maxCuts;
        cuts = cuts.slice().sort((a, b) => b.loud - a.loud || a.frame - b.frame).slice(0, maxCuts);
        cuts.sort((a, b) => a.frame - b.frame);
      }
      const nb = [L].concat(cuts.map((c) => c.frame), [R]);
      return { b: nb, s: splitSlices(nb), dropped };
    }

    function splitByTransients() {
      toSourceOrder();
      const L = boundaries[0];
      const R = boundaries[boundaries.length - 1];
      const sens = Number(rngSensitivity.value);
      const snap = transientSnapshot(sens, L, R);
      commit(snap.b, snap.s, null);
      transientSession = { hpos, sens };
      transientMessage(snap, sens);
    }

    function transientMessage(snap, sens) {
      const n = snap.b.length - 2;
      message(`Split by Transients: ${n} cut${n === 1 ? "" : "s"} at sensitivity ${sens}` +
        (snap.dropped ? `; ${snap.dropped} quietest onset${snap.dropped === 1 ? "" : "s"} dropped to stay within key ${K.LAST_KEY}` : ""));
    }

    function onSensitivity() {
      const sens = Number(rngSensitivity.value);
      sensValue.textContent = String(sens);
      if (!transientSession || transientSession.hpos !== hpos || hpos !== history.length - 1) return;
      if (transientSession.sens === sens) return;
      // Runs the split again; the new result replaces the previous split as one undo step.
      const L = boundaries[0];
      const R = boundaries[boundaries.length - 1];
      const snap = transientSnapshot(sens, L, R);
      history[hpos] = { b: snap.b, s: snap.s, bpm, o: identity(snap.s.length) };
      applySnapshot(history[hpos]);
      selected = null;
      transientSession.sens = sens;
      transientMessage(snap, sens);
      changed();
    }

    // ------------------------------------------------------------------
    // Onset detection (W12). Built once per source; sensitivity only moves a
    // threshold over a fixed list of candidates, so raising it can never
    // remove a cut.
    //
    // Method: the mono mix is split into four bands (high-passed broadband,
    // low, mid, high). For each band, the energy in a short window after a
    // hop is compared, in dB, with the energy in a window before it; the
    // onset curve is the largest rise over the bands. Peaks of that curve are
    // candidates. Each candidate is then placed at sample accuracy: the first
    // frame where the signal (or the band that rose) clearly exceeds the
    // level of the moments before, walked back to the start of that
    // half-cycle, minus one frame. The cut thus sits at or just before the
    // first frame of the attack and always before the hit's peak.
    // ------------------------------------------------------------------

    // dB of rise needed at sensitivity 0 and at 99; geometric in between.
    const RISE_AT_0 = 24;
    const RISE_AT_99 = 1.5;
    // The largest strength an onset without a located attack gets: the
    // threshold at sensitivity 75, so such onsets appear only above it.
    const IMPRECISE_RISE = RISE_AT_0 * Math.pow(RISE_AT_99 / RISE_AT_0, 75 / 99);
    function thresholdFor(sens) {
      const s = Math.min(99, Math.max(0, sens));
      return RISE_AT_0 * Math.pow(RISE_AT_99 / RISE_AT_0, s / 99);
    }

    function ensureCandidates() {
      if (!candidates) candidates = detectOnsets(f32, sr, N);
      return candidates;
    }

    // ---- detect begin
    function detectOnsets(chans, rate, frames, trace) {
      const nc = chans.length;
      const LSB = 1 / 32768;
      const ms = (x) => Math.max(1, Math.round((x * rate) / 1000));
      const mono = new Float32Array(frames);
      for (let c = 0; c < nc; c++) {
        const x = chans[c];
        for (let i = 0; i < frames; i++) mono[i] += x[i] / nc;
      }
      const absAt = (i) => {
        let m = 0;
        for (let c = 0; c < nc; c++) { const v = Math.abs(chans[c][i]); if (v > m) m = v; }
        return m;
      };

      function biquad(type, f0, q) {
        const w0 = (2 * Math.PI * Math.min(f0, rate * 0.45)) / rate;
        const cw = Math.cos(w0);
        const alpha = Math.sin(w0) / (2 * q);
        let b0, b1, b2;
        if (type === "lp") { b0 = (1 - cw) / 2; b1 = 1 - cw; b2 = (1 - cw) / 2; }
        else if (type === "hp") { b0 = (1 + cw) / 2; b1 = -(1 + cw); b2 = (1 + cw) / 2; }
        else { b0 = alpha; b1 = 0; b2 = -alpha; }
        const a0 = 1 + alpha;
        return { b0: b0 / a0, b1: b1 / a0, b2: b2 / a0, a1: (-2 * cw) / a0, a2: (1 - alpha) / a0 };
      }
      // cascaded biquads; each stage reads the previous stage's output in place
      function filter(x, cs) {
        const y = new Float32Array(x.length);
        for (let st = 0; st < cs.length; st++) {
          const k = cs[st];
          let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
          const src = st === 0 ? x : y;
          for (let i = 0; i < x.length; i++) {
            const xi = src[i];
            let yi = k.b0 * xi + k.b1 * x1 + k.b2 * x2 - k.a1 * y1 - k.a2 * y2;
            if (Math.abs(yi) < 1e-25) yi = 0; // no denormal tails
            x2 = x1; x1 = xi; y2 = y1; y1 = yi;
            y[i] = yi;
          }
        }
        return y;
      }

      const hop = Math.max(8, Math.round(rate * 0.0007));
      const nb = Math.ceil(frames / hop);
      const bands = [
        { cs: [biquad("hp", 150, Math.SQRT1_2)], A: 6, B: 10, keep: false },
        { cs: [biquad("lp", 160, Math.SQRT1_2), biquad("lp", 160, Math.SQRT1_2)], A: 16, B: 30, quad: 2 * Math.PI * 80, keep: false },
        { cs: [biquad("bp", 1200, 0.8)], A: 8, B: 12, keep: true },
        { cs: [biquad("hp", 5000, Math.SQRT1_2)], A: 3, B: 8, keep: true },
      ];
      const kept = [];
      const peaks = []; // [hop, rise in dB] from every band
      let maxA = 0;
      for (const band of bands) {
        const y = filter(mono, band.cs);
        const P = new Float64Array(nb + 1);
        for (let j = 0; j < nb; j++) {
          const i0 = j * hop;
          const i1 = Math.min(frames, i0 + hop);
          let s = 0;
          if (band.quad) {
            const g = rate / band.quad;
            for (let i = i0; i < i1; i++) { const d = (y[i] - (i > 0 ? y[i - 1] : 0)) * g; s += y[i] * y[i] + d * d; }
            s *= 0.5;
          } else {
            for (let i = i0; i < i1; i++) s += y[i] * y[i];
          }
          P[j + 1] = P[j] + s;
        }
        const A = Math.max(1, Math.round(ms(band.A) / hop));
        const B = Math.max(1, Math.round(ms(band.B) / hop));
        maxA = Math.max(maxA, A * hop);
        const ea = new Float64Array(nb);
        let emax = 0;
        for (let j = 0; j < nb; j++) {
          ea[j] = (P[Math.min(nb, j + A)] - P[j]) / (A * hop);
          if (ea[j] > emax) emax = ea[j];
        }
        // floor: a low percentile of the band's energy, or far below its loudest moment
        const sample = [];
        const stride = Math.max(1, Math.floor(nb / 20000));
        for (let j = 0; j < nb; j += stride) sample.push(ea[j]);
        sample.sort((p, q) => p - q);
        const pct = sample.length ? sample[Math.floor(sample.length * 0.1)] : 0;
        const eps = Math.max(2 * pct, emax * 1e-7, 4 * LSB * LSB);
        const rise = new Float32Array(nb);
        for (let j = 0; j < nb; j++) {
          const eb = (P[j] - P[Math.max(0, j - B)]) / (B * hop);
          rise[j] = 10 * Math.log10((ea[j] + eps) / (eb + eps));
        }
        // peak picking per band: local maxima within the band's own window
        const M = Math.max(2, A);
        for (let j = 1; j < nb; j++) {
          const v = rise[j];
          if (v < RISE_AT_99) continue;
          let isPeak = true;
          for (let k = 1; k <= M && isPeak; k++) {
            if (j - k >= 0 && rise[j - k] >= v) isPeak = false;
            if (j + k < nb && rise[j + k] > v) isPeak = false;
          }
          if (isPeak) peaks.push([j, v]);
        }
        if (band.keep) kept.push(y);
      }

      // loudness after each hop: broadband mono energy over 10 ms
      const PL = new Float64Array(nb + 1);
      for (let j = 0; j < nb; j++) {
        let s = 0;
        for (let i = j * hop, e = Math.min(frames, j * hop + hop); i < e; i++) s += mono[i] * mono[i];
        PL[j + 1] = PL[j] + s;
      }
      const LW = Math.max(1, Math.round(ms(10) / hop));

      const back = ms(12);
      const floorWin = ms(15);
      const fwd = maxA + ms(12);
      const walkLimit = ms(2);
      const jw = ms(1);
      const sw = ms(2);
      const lw = ms(5);
      const out = [];
      for (const [j, rise] of peaks) {
        const t = j * hop;
        const start = Math.max(0, t - back);
        const end = Math.min(frames, t + fwd);
        const f0 = Math.max(0, start - floorWin);
        // The attack's first frame: the first frame that is more than twice
        // as loud as everything in the millisecond before it (any non-zero
        // frame after digital silence). Looked for in the signal itself and
        // in the mid and high bands, which can jump under a louder
        // low-frequency tail; the earliest wins.
        // `jumpAt` returns the frame with the strongest sustained jump in
        // [from, to) and its strength: a frame more than twice as loud as the
        // millisecond before it (or any sound after digital silence) whose
        // next 2 ms climb to at least four times that level. The strength is
        // that climb's ratio; the real attack outranks noise and flicker.
        const jumpAt = (get, from, to) => {
          const dq = new Int32Array(jw + 2); // running maximum of the preceding jw frames
          let h0 = 0, h1 = 0;
          const base = Math.max(0, from - jw);
          const vals = new Float32Array(Math.max(0, to - base));
          for (let i = base; i < to; i++) vals[i - base] = get(i);
          let zeros = 0;
          let bestI = -1, bestR = 0;
          for (let i = base; i < to; i++) {
            const v = vals[i - base];
            if (i >= from) {
              while (h1 > h0 && dq[h0 % dq.length] < i - jw) h0++;
              const m = zeros >= 3 ? 0 : h1 > h0 ? vals[dq[h0 % dq.length] - base] : 0;
              if (v > 2 * m && v > 0.5 * LSB) {
                let fwdMax = 0;
                for (let k = i, e = Math.min(frames, i + sw); k < e; k++) { const u = get(k); if (u > fwdMax) fwdMax = u; }
                if (fwdMax >= 4 * m && fwdMax >= 2 * LSB) {
                  const r = fwdMax / (m + 0.5 * LSB);
                  if (r > bestR * 1.05) { bestR = r; bestI = i; }
                }
              }
            }
            zeros = v === 0 ? zeros + 1 : 0;
            while (h1 > h0 && vals[dq[(h1 - 1) % dq.length] - base] <= v) h1--;
            dq[h1 % dq.length] = i;
            h1++;
          }
          return [bestI, bestR];
        };
        let [n, nr] = jumpAt(absAt, start, end);
        for (const y of kept) {
          // a band can show an attack hidden under a louder low-frequency tail
          const [m, mr] = jumpAt((i) => Math.abs(y[i]), start, n >= 0 ? n : end);
          if (m >= 0 && mr >= 8 && absAt(m) > 0.5 * LSB && (n < 0 || nr < 8 || m < n)) { n = m; nr = mr; }
        }
        // No sustained jump: a swell, a soft note under a louder tail, or a
        // sound stopping. Kept at its energy rise, but only for the highest
        // sensitivities (see the cap below).
        const precise = n >= 0;
        if (n < 0) n = Math.min(frames - 1, t);
        // walk back to the start of this half-cycle
        let ch = 0;
        let best = -1;
        for (let c = 0; c < nc; c++) { const v = Math.abs(chans[c][n]); if (v > best) { best = v; ch = c; } }
        const x = chans[ch];
        let a = n;
        const lim = Math.max(1, n - walkLimit, f0);
        while (a > lim) {
          const p = x[a - 1];
          const q = x[a];
          if (p === 0 || (p > 0) !== (q > 0) || Math.abs(p) >= Math.abs(q)) break;
          a--;
        }
        const frame = a - 1;
        if (frame < 0) continue;

        // A hit makes the level climb: the 5 ms after the attack must be
        // louder than the millisecond before it, in the signal or in a band. This
        // drops peaks caused by a sound stopping abruptly, and flicker.
        const levelRatio = (get) => {
          let pre = 0, post = 0;
          for (let i = Math.max(0, a - jw); i < a; i++) { const v = get(i); if (v > pre) pre = v; }
          for (let i = a, e = Math.min(frames, a + lw); i < e; i++) { const v = get(i); if (v > post) post = v; }
          return post < 2 * LSB ? 0 : post / (pre + 0.5 * LSB);
        };
        let grows = levelRatio(absAt) >= 1.5;
        if (!grows) {
          // a band may grow under a louder tail, but the sound as a whole
          // must not be stopping (an abrupt end makes the bands ring)
          let e0 = 0, e1 = 0;
          for (let i = Math.max(0, a - lw); i < a; i++) e0 += mono[i] * mono[i];
          for (let i = a, e = Math.min(frames, a + lw); i < e; i++) e1 += mono[i] * mono[i];
          if (e1 >= 0.5 * e0) for (const y of kept) if (!grows && levelRatio((i) => Math.abs(y[i])) >= 2) grows = true;
        }
        if (trace) trace({ t, start, end, n, nr, a, rise, grows });
        if (!grows) continue;
        const jl = Math.min(nb - 1, Math.floor(a / hop));
        const le = (PL[Math.min(nb, jl + LW)] - PL[jl]) / (LW * hop);
        out.push({ frame, odf: rise, loud: 10 * Math.log10(le + 1e-20), precise });
      }
      // Sound after digital silence (frames of exact zero in every channel)
      // is an onset. A long silence (5 ms or more) counts whatever came
      // before it; a short one only if the sound after it is at least twice
      // as loud as the 2 ms before the silence, since a quiet low tone has
      // short runs of zero samples at its zero crossings. The strength is
      // how far the next 5 ms rise above one step of the source.
      let zrun = 0;
      const longSilence = ms(5);
      const ctx = ms(2);
      for (let i = 0; i < frames; i++) {
        const v = absAt(i);
        if (v === 0) { zrun++; continue; }
        if (zrun >= 3 && i >= 1) {
          let post = 0;
          for (let k = i, e = Math.min(frames, i + lw); k < e; k++) { const u = absAt(k); if (u > post) post = u; }
          let before = 0;
          if (zrun < longSilence) {
            for (let k = Math.max(0, i - zrun - ctx); k < i - zrun; k++) { const u = absAt(k); if (u > before) before = u; }
          }
          if (post >= 8 * LSB && post >= 2 * before) {
            const jl = Math.min(nb - 1, Math.floor(i / hop));
            const le = (PL[Math.min(nb, jl + LW)] - PL[jl]) / (LW * hop);
            out.push({ frame: i - 1, odf: Math.min(60, 20 * Math.log10(post / LSB)), loud: 10 * Math.log10(le + 1e-20), precise: true });
          }
        }
        zrun = 0;
      }
      out.sort((p, q) => p.frame - q.frame);
      // One hit seen by several peaks: keep one candidate, at the earliest
      // precisely located frame (or the earliest frame if none is precise).
      const merged = [];
      const mergeGap = ms(1.5);
      for (const c of out) {
        const last = merged[merged.length - 1];
        if (last && c.frame - last.end < mergeGap) {
          last.odf = Math.max(last.odf, c.odf);
          last.loud = Math.max(last.loud, c.loud);
          last.end = c.frame;
          if (c.precise && !last.precise) { last.frame = c.frame; last.precise = true; }
        } else {
          merged.push({ frame: c.frame, end: c.frame, odf: c.odf, loud: c.loud, precise: c.precise });
        }
      }
      // An onset without a located attack counts only far from located ones
      // (not within 25 ms after or 5 ms before one), and only from the
      // sensitivity where the threshold falls to IMPRECISE_RISE.
      const located = merged.filter((c) => c.precise).map((c) => c.frame);
      const after = ms(25);
      const before = ms(5);
      const result = [];
      let li = 0;
      for (const c of merged) {
        if (!c.precise) {
          while (li < located.length && located[li] < c.frame - after) li++;
          if (li < located.length && located[li] <= c.frame + before) continue;
        }
        if (result.length && c.frame <= result[result.length - 1].frame) continue;
        result.push({ frame: c.frame, odf: c.precise ? c.odf : Math.min(c.odf, IMPRECISE_RISE), loud: c.loud });
      }
      return result;
    }
    // ---- detect end

    // ------------------------------------------------------------------
    // Audition (W18)
    // ------------------------------------------------------------------

    let actx = null;
    let fullBuffer = null;
    let voice = null; // { src, t0, w0, from, to, loop, L, R, timer }

    function audioInit() {
      try {
        actx = new AudioContext({ sampleRate: sr, latencyHint: "interactive" });
      } catch (_) {
        // SPEC-GAP: a context at the source's rate is refused by this device;
        // the buffers still carry the source's rate, so Web Audio resamples
        // and the pitch and length stay right.
        actx = new AudioContext({ latencyHint: "interactive" });
      }
    }

    function stopAudio() {
      if (!voice) return;
      const v = voice;
      voice = null;
      clearTimeout(v.timer);
      try { v.src.onended = null; v.src.stop(); } catch (_) { /* already stopped */ }
      try { v.src.disconnect(); } catch (_) { /* already disconnected */ }
      scheduleOverlay();
    }

    function startVoice(src, from, to, loop, L, R) {
      stopAudio(); // one voice: a hard cut
      if (actx.state === "suspended") actx.resume().catch(() => {});
      src.connect(actx.destination);
      const v = { src, t0: actx.currentTime, w0: performance.now(), from, to, loop, L, R, timer: 0 };
      src.onended = () => { if (voice === v) { voice = null; scheduleOverlay(); } };
      voice = v;
      if (!loop) {
        // in case the audio clock doesn't run (no output device), end by the wall clock
        v.timer = setTimeout(() => { if (voice === v) stopAudio(); }, ((to - from) / sr) * 1000 + 400);
      }
      scheduleOverlay();
      animatePlayhead();
    }

    // Plays frames [from, to) exactly, ending with the tail fade.
    function playRange(from, to) {
      if (!(to > from)) return;
      logEvent("play", { from, to });
      const len = to - from;
      const buf = actx.createBuffer(nch, len, sr);
      const fadeLen = Math.min(len, Math.max(1, Math.round((K.TAIL_FADE_MS * sr) / 1000)));
      for (let c = 0; c < nch; c++) {
        const d = f32[c].slice(from, to);
        for (let i = 0; i < fadeLen; i++) {
          // t falls from 1 at the fade's first frame to 0 at the slice's last frame
          const t = fadeLen === 1 ? 0 : 1 - i / (fadeLen - 1);
          d[len - fadeLen + i] *= Math.pow(t, K.TAIL_FADE_POWER);
        }
        buf.copyToChannel(d, c);
      }
      const src = actx.createBufferSource();
      src.buffer = buf;
      src.start();
      startVoice(src, from, to, false, from, to);
    }

    function playSlice(k) { // k 0-based
      if (k < 0 || k >= slices.length) return;
      playRange(boundaries[k], boundaries[k + 1]);
    }

    function playLoop() {
      const L = boundaries[loopA];
      const R = boundaries[loopE];
      if (!fullBuffer) {
        fullBuffer = actx.createBuffer(nch, N, sr);
        for (let c = 0; c < nch; c++) fullBuffer.copyToChannel(f32[c], c);
      }
      const src = actx.createBufferSource();
      src.buffer = fullBuffer;
      // SPEC-GAP: W18's tail fade is for slices; the L-to-R loop plays the
      // region's frames unfaded, so the loop point is heard as recorded.
      src.loop = true;
      src.loopStart = L / sr;
      src.loopEnd = R / sr;
      src.start(0, L / sr);
      startVoice(src, L, R, true, L, R);
    }

    function playheadFrame() {
      if (!voice) return null;
      const el = actx.state === "running" ? actx.currentTime - voice.t0 : (performance.now() - voice.w0) / 1000;
      const d = Math.max(0, el) * sr;
      if (voice.loop) return voice.L + (d % (voice.R - voice.L));
      return Math.min(voice.to, voice.from + d);
    }

    let playheadAnimating = false;
    function animatePlayhead() {
      if (playheadAnimating) return;
      playheadAnimating = true;
      const step = () => {
        drawOverlay();
        if (voice) requestAnimationFrame(step);
        else { playheadAnimating = false; drawOverlay(); }
      };
      requestAnimationFrame(step);
    }

    function sliceAt(f) {
      const b = boundaries;
      if (f < b[0] || f >= b[b.length - 1]) return -1;
      let lo = 0;
      let hi = b.length - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (b[mid] <= f) lo = mid; else hi = mid;
      }
      return lo;
    }

    // ------------------------------------------------------------------
    // View
    // ------------------------------------------------------------------

    function setView(start, span) {
      const minSpan = Math.min(K.MIN_VIEW_FRAMES, N);
      span = Math.min(N, Math.max(minSpan, span));
      start = Math.min(Math.max(0, start), N - span);
      viewStart = start;
      viewEnd = start + span;
      scheduleWave();
    }

    function frameAtX(x) {
      const p = layout.plot;
      return viewStart + ((x - p.x) / p.width) * (viewEnd - viewStart);
    }
    function xOfFrame(f) {
      const p = layout.plot;
      return p.x + ((f - viewStart) / (viewEnd - viewStart)) * p.width;
    }

    function pointerOverPlot() {
      if (!pointer.inside) return false;
      const p = layout.plot;
      return pointer.x >= p.x && pointer.x <= p.x + p.width && pointer.y >= layout.plotsTop && pointer.y <= layout.plotsBottom;
    }

    function zoomBy(factor, anchorX) {
      const span = viewEnd - viewStart;
      const p = layout.plot;
      let f;
      let u;
      if (anchorX !== null) {
        f = frameAtX(anchorX);
        u = (anchorX - p.x) / p.width;
      } else {
        f = (viewStart + viewEnd) / 2;
        u = 0.5;
      }
      let ns = factor < 1 ? Math.max(span * factor, K.MIN_VIEW_FRAMES) : span * factor;
      ns = Math.min(N, ns);
      setView(f - u * ns, ns);
    }

    function zoomKey(zoomIn) {
      const anchor = pointerOverPlot() ? pointer.x : null;
      zoomBy(zoomIn ? K.ZOOM_STEP : 1 / K.ZOOM_STEP, anchor);
    }

    function fitSliceUnderPointer() {
      // SPEC-GAP: with the pointer away from the plot, `z` fits the slice at
      // the centre of the view.
      const f = pointerOverPlot() ? frameAtX(pointer.x) : (viewStart + viewEnd) / 2;
      const k = sliceAt(Math.floor(f));
      if (k < 0) { message("No slice under the pointer"); return; }
      const a = boundaries[k];
      const b = boundaries[k + 1];
      const span = Math.max(b - a, Math.min(K.MIN_VIEW_FRAMES, N));
      setView((a + b) / 2 - span / 2, span);
    }

    // ------------------------------------------------------------------
    // Pointer
    // ------------------------------------------------------------------

    const pointer = { x: 0, y: 0, inside: false };
    const t0 = performance.now();
    let events = [];
    let opening = null;
    let lastEdit = null;
    function logEvent(kind, detail) {
      const e = Object.assign({ t_ms: Math.round(performance.now() - t0), kind }, detail);
      events.push(e);
      return e;
    }
    function runReport() {
      const k = kept();
      return { opening, events, final: { boundaries: k.b, slices: k.s, order: k.o.map((v) => v + 1), bpm, dirty: hpos !== 0 } };
    }
    let expectSlices = null;
    let editCursor = null; // frame of the last click on the waveform; where Add cut puts a cut
    let drag = null; // { kind: "boundary", index, origin, x0 } or { kind: "overview" }

    function inPlotArea(x, y) {
      const p = layout.plot;
      return x >= p.x - K.PICK_PIXELS && x <= p.x + p.width + K.PICK_PIXELS &&
        y >= layout.stripTop && y <= layout.plotsBottom;
    }
    function inOverview(x, y) {
      const o = layout.over;
      return x >= o.x && x <= o.x + o.width && y >= o.y && y <= o.y + o.height;
    }

    // W26: a press on the L or R flag in the strip; each flag reaches FLAG_PIXELS into the loop from its line.
    function pickFlag(x, y) {
      if (!(y >= layout.stripTop && y < layout.stripTop + STRIP_H)) return null;
      const dl = x - xOfFrame(boundaries[loopA]);
      const dr = xOfFrame(boundaries[loopE]) - x;
      // a flag takes at most half of a narrow slot, so the slot can still be pressed to reorder
      const wl = Math.min(K.FLAG_PIXELS, (xOfFrame(boundaries[loopA + 1]) - xOfFrame(boundaries[loopA])) / 2);
      const wr = Math.min(K.FLAG_PIXELS, (xOfFrame(boundaries[loopE]) - xOfFrame(boundaries[loopE - 1])) / 2);
      const onL = dl >= 0 && dl <= wl;
      const onR = dr >= 0 && dr <= wr;
      if (onL && onR) return dl <= dr ? "L" : "R";
      return onL ? "L" : onR ? "R" : null;
    }
    // The slice edge nearest x, as an index into the shown boundaries.
    function nearestEdge(x) {
      let best = 0;
      for (let i = 1; i < boundaries.length; i++) if (Math.abs(xOfFrame(boundaries[i]) - x) < Math.abs(xOfFrame(boundaries[best]) - x)) best = i;
      return best;
    }
    function pickBoundary(x, y) {
      let best = null;
      let bestD = Infinity;
      const b = boundaries;
      // only boundaries near the visible span can be within reach
      for (let i = 0; i < b.length; i++) {
        const d = Math.abs(xOfFrame(b[i]) - x);
        if (d <= K.PICK_PIXELS && (d < bestD || (d === bestD && best !== null && Math.abs(b[i] - frameAtX(x)) < Math.abs(b[best] - frameAtX(x))))) {
          best = i;
          bestD = d;
        }
      }
      return best;
    }

    function pointerFrame(x) {
      return Math.min(N, Math.max(0, Math.round(frameAtX(x))));
    }

    function onMouseDown(e) {
      if (e.button !== 0) return;
      if (!ready || dialogOpen()) return;
      const x = e.clientX;
      const y = e.clientY;
      if (inOverview(x, y)) {
        e.preventDefault();
        drag = { kind: "overview" };
        overviewTo(x);
        return;
      }
      if (!inPlotArea(x, y)) return;
      e.preventDefault();
      if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
      const flag = e.altKey || e.shiftKey || e.metaKey || e.ctrlKey ? null : pickFlag(x, y);
      if (flag) {
        drag = { kind: "loop", which: flag, from: [loopA, loopE] };
        changed();
        return;
      }
      const pick = pickBoundary(x, y);
      if (e.altKey) {
        if (e.metaKey || e.ctrlKey) return;
        if (pick === null) addCut(pointerFrame(x));
        else removeCut(pick);
        return;
      }
      if (e.metaKey || e.ctrlKey) return;
      if (e.shiftKey) {
        // SPEC-GAP: Shift-click plays from the clicked frame even on a
        // boundary's line; its table row, unlike the others, names no exception.
        const f = pointerFrame(x);
        const k = sliceAt(f);
        if (k >= 0) playRange(f, boundaries[k + 1]);
        return;
      }
      if (pick !== null) {
        // W25: the line follows the pointer and the source cut it stands for moves on release
        const c = sourceCut(pick), src = toSource(), n = src.b.length - 1;
        selected = pick;
        if (c <= 0 || c >= n) { message(REGION_END); changed(); return; }
        drag = { kind: "boundary", index: pick, origin: boundaries[pick], x0: x, src: c, delta: 0, moved: false,
                 lo: src.b[c - 1] + 1 - src.b[c], hi: src.b[c + 1] - 1 - src.b[c] };
        changed();
        return;
      }
      editCursor = pointerFrame(x);
      changed();
      const k = sliceAt(Math.min(N - 1, Math.max(0, Math.floor(frameAtX(x)))));
      // W25: a press on a slice in the strip above the plots may become a drag that reorders.
      // Audio already playing goes on until the release shows whether it was a click.
      const onHandle = k >= 0 && slices.length > 1 && y < layout.stripTop + STRIP_H;
      if (onHandle) { slot = k; drag = { kind: "slice", index: k, x0: x, moved: false, target: k, wasPlaying: voice !== null }; }
      else if (y < layout.stripTop + STRIP_H) slot = k >= 0 ? k : null;
      if (voice) { if (!onHandle) stopAudio(); return; }
      if (k >= 0) playSlice(k);
    }

    // Double-click adds a cut on the waveform and removes the cut it lands on.
    function onDoubleClick(e) {
      if (!ready || dialogOpen() || e.altKey || e.metaKey || e.ctrlKey || e.shiftKey) return;
      if (!inPlotArea(e.clientX, e.clientY)) return;
      e.preventDefault();
      if (pickFlag(e.clientX, e.clientY)) return;
      const pick = pickBoundary(e.clientX, e.clientY);
      if (pick === null) { stopAudio(); addCut(pointerFrame(e.clientX)); }
      else removeCut(pick);
    }

    function canAddAtCursor() {
      return editCursor !== null && editCursor > boundaries[0] && editCursor < boundaries[boundaries.length - 1] &&
        !boundaries.includes(editCursor);
    }

    function updateButtons() {
      $("add-cut").disabled = !canAddAtCursor();
      $("delete-cut").disabled = !(selected !== null && selected > 0 && selected < boundaries.length - 1);
      $("source-order").disabled = !reordered();
      $("save").classList.toggle("dirty", hpos !== 0);
      $("unsaved").hidden = hpos === 0;
      if (expectSlices !== null) {
        const slices = kept().s;
        const ok = slices.length === expectSlices;
        $("save").disabled = !ok;
        $("expect").textContent = ok ? `${expectSlices} slices, as asked` : `${slices.length} slices now, ${expectSlices} asked`;
        $("expect").className = ok ? "ok" : "short";
      }
    }

    function onMouseMove(e) {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
      pointer.inside = true;
      if (drag && drag.kind === "boundary") {
        if (e.clientX !== drag.x0) drag.moved = true;
        if (drag.moved) {
          drag.delta = Math.min(Math.max(pointerFrame(e.clientX) - drag.origin, drag.lo), drag.hi);
          boundaries[drag.index] = drag.origin + drag.delta;
        }
      } else if (drag && drag.kind === "loop") {
        const i = nearestEdge(e.clientX);
        if (drag.which === "L") loopA = Math.min(Math.max(i, 0), loopE - 1);
        else loopE = Math.min(Math.max(i, loopA + 1), order.length);
      } else if (drag && drag.kind === "slice") {
        if (Math.abs(e.clientX - drag.x0) > K.PICK_PIXELS) drag.moved = true;
        if (drag.moved) drag.target = dropSlot(e.clientX);
      } else if (drag && drag.kind === "overview") {
        overviewTo(e.clientX);
      }
      updateCursor();
      updateReadout();
      scheduleOverlay();
    }

    function onMouseUp(e) {
      if (!drag) return;
      const d = drag;
      drag = null;
      if (d.kind === "boundary") {
        const i = d.index;
        boundaries[i] = d.origin;
        if (!moveSourceCut(d.src, d.delta, i)) changed();
      } else if (d.kind === "loop") {
        const to = [loopA, loopE];
        loopA = d.from[0]; loopE = d.from[1];
        setLoop(to[0], to[1], d.from);
      } else if (d.kind === "slice") {
        if (d.moved) moveSlice(d.index, d.target);
        else if (d.wasPlaying) stopAudio(); // a click while audio plays stops it
      }
      onMouseMove(e);
    }

    function onWheel(e) {
      if (!ready) return;
      const x = e.clientX;
      const y = e.clientY;
      if (!inPlotArea(x, y) && !inOverview(x, y)) return;
      e.preventDefault();
      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
      let dx = e.deltaX * unit;
      let dy = e.deltaY * unit;
      if (e.shiftKey && dx === 0) { dx = dy; dy = 0; }
      const span = viewEnd - viewStart;
      if (Math.abs(dx) > Math.abs(dy)) {
        setView(viewStart + (dx * span) / layout.plot.width, span);
      } else if (dy !== 0) {
        const k = e.ctrlKey ? 0.01 : 0.0025; // pinch arrives as ctrl+wheel with small deltas
        const factor = Math.exp(dy * k);
        const anchor = Math.min(layout.plot.x + layout.plot.width, Math.max(layout.plot.x, x));
        const f = frameAtX(anchor);
        const u = (anchor - layout.plot.x) / layout.plot.width;
        const ns = Math.min(N, Math.max(Math.min(K.MIN_VIEW_FRAMES, N), span * factor));
        setView(f - u * ns, ns);
      }
      updateReadout();
    }

    function overviewTo(x) {
      const o = layout.over;
      const f = ((x - o.x) / o.width) * N;
      const span = viewEnd - viewStart;
      setView(f - span / 2, span);
    }

    function updateCursor() {
      let c = "default";
      if (drag && drag.kind === "boundary") c = "ew-resize";
      else if (drag && drag.kind === "slice") c = "grabbing";
      else if (ready && inPlotArea(pointer.x, pointer.y)) {
        c = pickBoundary(pointer.x, pointer.y) !== null ? "ew-resize"
          : pointer.y < layout.stripTop + STRIP_H && slices.length > 1 ? "grab" : "crosshair";
      }
      else if (ready && inOverview(pointer.x, pointer.y)) c = "pointer";
      if (overCanvas.style.cursor !== c) overCanvas.style.cursor = c;
    }

    // ------------------------------------------------------------------
    // Keys. One capture-phase listener: every key acts whichever element has
    // focus, except Left and Right while the sensitivity control has it and
    // plain keys while the tempo control has it.
    // ------------------------------------------------------------------

    function onKeyDown(e) {
      if (e.isComposing) return;
      tempoRefused = false;
      const key = e.key;
      const lower = key.length === 1 ? key.toLowerCase() : key;
      const code = e.code || "";
      // SPEC-GAP: Cmd is the shortcut modifier on macOS and Ctrl elsewhere;
      // either is accepted on every platform, so a driver can't pick wrong.
      const inTempo = document.activeElement === fldTempo;
      if ((e.metaKey || e.ctrlKey) && !e.altKey) {
        // Save and Close first apply a tempo still being typed and do not act
        // if it is refused; Undo and Redo discard it.
        if (inTempo && (lower === "s" || lower === "w")) {
          const ok = onTempo();
          fldTempo.blur();
          if (!ok) { e.preventDefault(); e.stopPropagation(); return; }
        }
        if (inTempo && lower === "z") { showTempo(); fldTempo.blur(); }
        if (lower === "s" || code === "KeyS") { e.preventDefault(); e.stopPropagation(); if (!e.repeat) save(); return; }
        if (lower === "w" || code === "KeyW") { e.preventDefault(); e.stopPropagation(); if (!e.repeat) requestClose(); return; }
        if (lower === "z" || code === "KeyZ") {
          e.preventDefault(); e.stopPropagation();
          if (e.shiftKey) redo(); else undo();
          return;
        }
        // W25: copy, paste, duplicate and cut the selected slot; the tempo control keeps its own while it has focus
        if (!inTempo && !e.shiftKey && ready && !drag && "cvdx".indexOf(lower) >= 0 && lower.length === 1) {
          e.preventDefault(); e.stopPropagation();
          if (e.repeat) return;
          if (lower === "c") copySlot(); else if (lower === "v") pasteSlot(); else if (lower === "d") duplicateSlot(); else cutSlot();
          return;
        }
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (inTempo) {
        if (key === "Enter") { e.preventDefault(); onTempo(); fldTempo.blur(); }
        else if (key === "Escape") { e.preventDefault(); showTempo(); fldTempo.blur(); }
        return;
      }
      if ((key === "ArrowLeft" || key === "ArrowRight") && document.activeElement === rngSensitivity) return;
      if (!ready) return;
      let handled = true;
      if (key === "ArrowLeft" || key === "ArrowRight") {
        if (selected !== null && !drag) {
          const step = e.shiftKey ? Math.max(1, Math.round((viewEnd - viewStart) / layout.plot.width)) : 1;
          moveBy(selected, key === "ArrowLeft" ? -step : step);
        }
      } else if (key === "Delete" || key === "Backspace") {
        if (selected !== null && !drag) {
          removeCut(selected);
        }
      } else if (key === " " || code === "Space") {
        if (!e.repeat) { if (voice) stopAudio(); else playLoop(); }
      } else if (key === "=" || key === "+") {
        zoomKey(true);
      } else if (key === "-" || key === "_") {
        zoomKey(false);
      } else if (lower === "f") {
        setView(0, N);
      } else if (lower === "z") {
        fitSliceUnderPointer();
      } else if (key.length === 1 && K.AUDITION_KEYS.indexOf(lower) >= 0) {
        if (!e.repeat) playSlice(order.indexOf(K.AUDITION_KEYS.indexOf(lower)));
      } else {
        handled = false;
      }
      if (handled) {
        e.preventDefault();
        e.stopPropagation();
        updateReadout();
        scheduleOverlay();
      }
    }

    function onKeyUp(e) {
      // a focused button activates on Space's keyup; Space belongs to playback
      if ((e.key === " " || e.code === "Space") && !(e.metaKey || e.ctrlKey || e.altKey)) e.preventDefault();
    }

    // ------------------------------------------------------------------
    // Save and close (W04, W05)
    // ------------------------------------------------------------------

    let saving = false;
    async function save() {
      if (saving || !ready) return;
      const k = kept();
      if (expectSlices !== null && k.s.length !== expectSlices) {
        message(`Not saved: this task needs ${expectSlices} slices and the loop holds ${k.s.length}`, true);
        return;
      }
      saving = true;
      message("Saving…");
      let r;
      try {
        r = await ipcRenderer.invoke("rcy-save", { boundaries: k.b, slices: k.s, order: k.o, bpm, report: runReport() });
      } catch (err) {
        r = { ok: false, error: String(err && err.message ? err.message : err) };
      }
      if (!r || !r.ok) {
        message(`Not saved: ${r ? r.error : "no answer"}`, true);
        saving = false;
      }
    }

    function dialogOpen() { return !dialog.hidden; }

    function requestClose() {
      if (hpos === 0) { ipcRenderer.send("rcy-exit", 3, runReport()); return; }
      dialog.hidden = false;
    }

    // ------------------------------------------------------------------
    // Status line (W16): a readout part and a message part
    // ------------------------------------------------------------------

    function message(text, isError) {
      if (lastEdit && lastEdit.what === "") lastEdit.what = text;
      lastEdit = null;
      statusMsg.textContent = text;
      statusMsg.className = isError ? "error" : "";
    }

    function boundaryName(i) {
      if (i === 0) return "region start";
      if (i === boundaries.length - 1) return "region end";
      return `line ${i}`;
    }

    function valuesAt(f) {
      const fi = Math.min(N - 1, Math.max(0, Math.floor(f)));
      const names = nch === 2 ? ["L", "R"] : null;
      const parts = [];
      for (let c = 0; c < nch; c++) parts.push(`${names ? names[c] : "ch" + (c + 1)} ${i16[c][fi]}`);
      return parts.join("  ");
    }

    const fmtTime = (f) => (f / sr).toFixed(4) + " s";

    function updateReadout() {
      if (!ready) return;
      let s = "";
      if (pointer.inside && inPlotArea(pointer.x, pointer.y)) {
        const f = pointerFrame(pointer.x);
        s += `Pointer ${f}  ${fmtTime(f)}  [${valuesAt(f)}]`;
      } else {
        s += "Pointer –";
      }
      if (selected !== null && selected < boundaries.length) {
        const f = boundaries[selected];
        // SPEC-GAP: "each channel's sample value at that frame" is read as
        // the selected boundary's frame; the pointer's frame gets its values too.
        s += `   ·   Selected ${boundaryName(selected)} ${f}  ${fmtTime(f)}  [${valuesAt(f)}]`;
      } else {
        s += "   ·   Selected –";
      }
      s += `   ·   ${slices.length} slice${slices.length === 1 ? "" : "s"}`;
      statusReadout.textContent = s;
    }

    function changed() {
      updateButtons();
      updateReadout();
      scheduleOverlay();
    }

    // ------------------------------------------------------------------
    // Drawing
    // ------------------------------------------------------------------

    const COLORS = {
      bg: "#0f1216",
      plotBg: "#151a21",
      plotBgOut: "#0c0f13",
      grid: "rgba(255,255,255,0.05)",
      zero: "rgba(170,200,220,0.28)",
      zeroStrong: "rgba(190,215,235,0.55)",
      env: "#2f7f78",
      rms: "#6fd0c4",
      line: "#8fe8dc",
      dot: "#e4fffb",
      cut: "#f3c04f",
      cutSel: "#ff6b5e",
      loc: "#5aaeff",
      label: "#c8d2dc",
      labelDim: "#7d8995",
      play: "#ffffff",
      hover: "rgba(255,255,255,0.35)",
      axis: "#7d8995",
      view: "rgba(120,190,255,0.22)",
      viewEdge: "rgba(140,200,255,0.8)",
    };

    function buildPyramid(x) {
      const levels = [];
      let size = 16;
      let prev = null;
      while (true) {
        const count = Math.ceil(x.length / size);
        const mn = new Float32Array(count);
        const mx = new Float32Array(count);
        const ss = new Float32Array(count);
        if (!prev) {
          for (let k = 0; k < count; k++) {
            let a = Infinity, b = -Infinity, s = 0;
            for (let i = k * size, e = Math.min(x.length, i + size); i < e; i++) {
              const v = x[i];
              if (v < a) a = v;
              if (v > b) b = v;
              s += v * v;
            }
            mn[k] = a; mx[k] = b; ss[k] = s;
          }
        } else {
          for (let k = 0; k < count; k++) {
            let a = Infinity, b = -Infinity, s = 0;
            for (let i = k * 4, e = Math.min(prev.mn.length, i + 4); i < e; i++) {
              if (prev.mn[i] < a) a = prev.mn[i];
              if (prev.mx[i] > b) b = prev.mx[i];
              s += prev.ss[i];
            }
            mn[k] = a; mx[k] = b; ss[k] = s;
          }
        }
        const lev = { size, mn, mx, ss };
        levels.push(lev);
        if (count <= 1) break;
        prev = lev;
        size *= 4;
      }
      return levels;
    }

    const stats = { mn: 0, mx: 0, ss: 0, n: 0 };
    // min, max and sum of squares of channel c over frames [a, b)
    function rangeStats(c, a, b) {
      const x = f32[c];
      const levels = pyramid[c];
      let mn = Infinity, mx = -Infinity, ss = 0;
      let pos = a;
      while (pos < b) {
        let used = false;
        for (let L = levels.length - 1; L >= 0; L--) {
          const lev = levels[L];
          const sz = lev.size;
          if (pos % sz === 0 && pos + sz <= b) {
            const k = pos / sz;
            if (lev.mn[k] < mn) mn = lev.mn[k];
            if (lev.mx[k] > mx) mx = lev.mx[k];
            ss += lev.ss[k];
            pos += sz;
            used = true;
            break;
          }
        }
        if (!used) {
          const v = x[pos];
          if (v < mn) mn = v;
          if (v > mx) mx = v;
          ss += v * v;
          pos++;
        }
      }
      stats.mn = mn; stats.mx = mx; stats.ss = ss; stats.n = b - a;
      return stats;
    }

    function computeLayout() {
      const r = area.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const cssW = Math.max(200, Math.floor(r.width));
      const cssH = Math.max(160, Math.floor(r.height));
      const plotsTop = r.top + STRIP_H;
      const overTop = r.top + cssH - OVER_H - 4;
      const axisTop = overTop - 6 - AXIS_H;
      const plotsBottom = axisTop;
      const totalH = plotsBottom - plotsTop;
      const h = Math.max(20, (totalH - CH_GAP * (nch - 1)) / nch);
      const plots = [];
      for (let c = 0; c < nch; c++) plots.push({ x: r.left + MARGIN, y: plotsTop + c * (h + CH_GAP), width: cssW - 2 * MARGIN, height: h });
      layout = {
        left: r.left, top: r.top, cssW, cssH, dpr,
        plot: plots[0], plots, plotsTop, plotsBottom,
        stripTop: r.top, axisTop,
        over: { x: r.left + MARGIN, y: overTop, width: cssW - 2 * MARGIN, height: OVER_H },
      };
      for (const cv of [waveCanvas, overCanvas]) {
        cv.width = Math.round(cssW * dpr);
        cv.height = Math.round(cssH * dpr);
        cv.style.width = cssW + "px";
        cv.style.height = cssH + "px";
      }
      overviewCache = null;
    }

    let overviewCache = null;
    function drawOverviewCache() {
      const dpr = layout.dpr;
      const o = layout.over;
      const w = Math.max(1, Math.round(o.width * dpr));
      const h = Math.max(1, Math.round(o.height * dpr));
      const cv = document.createElement("canvas");
      cv.width = w;
      cv.height = h;
      const g = cv.getContext("2d");
      g.fillStyle = COLORS.plotBg;
      g.fillRect(0, 0, w, h);
      g.fillStyle = COLORS.env;
      const mid = h / 2;
      for (let i = 0; i < w; i++) {
        const a = Math.floor((i * N) / w);
        const b = Math.max(a + 1, Math.floor(((i + 1) * N) / w));
        let mn = Infinity, mx = -Infinity;
        for (let c = 0; c < nch; c++) {
          const s = rangeStats(c, a, Math.min(N, b));
          if (s.mn < mn) mn = s.mn;
          if (s.mx > mx) mx = s.mx;
        }
        const y0 = mid - mx * (mid - 1);
        const y1 = mid - mn * (mid - 1);
        g.fillRect(i, y0, 1, Math.max(1, y1 - y0));
      }
      overviewCache = cv;
    }

    let waveQueued = false;
    let overlayQueued = false;
    function scheduleWave() {
      if (waveQueued) return;
      waveQueued = true;
      requestAnimationFrame(() => { waveQueued = false; drawWave(); drawOverlay(); });
    }
    function scheduleOverlay() {
      if (overlayQueued || waveQueued) return;
      overlayQueued = true;
      requestAnimationFrame(() => { overlayQueued = false; drawOverlay(); });
    }

    function niceStep(raw) {
      const p = Math.pow(10, Math.floor(Math.log10(raw)));
      for (const m of [1, 2, 5, 10]) if (m * p >= raw) return m * p;
      return 10 * p;
    }

    function drawWave() {
      if (!N) return;
      const g = waveCanvas.getContext("2d");
      const dpr = layout.dpr;
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.fillStyle = COLORS.bg;
      g.fillRect(0, 0, waveCanvas.width, waveCanvas.height);
      const span = viewEnd - viewStart;
      const ox = layout.left;
      const oy = layout.top;
      for (let c = 0; c < nch; c++) {
        const p = layout.plots[c];
        const px = Math.round((p.x - ox) * dpr);
        const py = Math.round((p.y - oy) * dpr);
        const pw = Math.round(p.width * dpr);
        const ph = Math.round(p.height * dpr);
        g.fillStyle = COLORS.plotBg;
        g.fillRect(px, py, pw, ph);
        const half = ph / 2 - 2 * dpr;
        const mid = py + ph / 2;
        const yOf = (v) => mid - v * half;
        const fpp = span / pw; // frames per device pixel
        const cssPpf = p.width / span; // CSS pixels per frame
        // amplitude grid at ±0.5
        g.fillStyle = COLORS.grid;
        g.fillRect(px, Math.round(yOf(0.5)), pw, 1);
        g.fillRect(px, Math.round(yOf(-0.5)), pw, 1);
        // frame grid when frames are wide
        if (cssPpf >= 6) {
          g.fillStyle = COLORS.grid;
          const f0 = Math.ceil(viewStart);
          for (let f = f0; f <= viewEnd; f++) {
            const x = px + ((f - viewStart) / span) * pw;
            g.fillRect(Math.round(x), py, 1, ph);
          }
        }
        const zoomed = span < p.width; // fewer frames than the plot has pixels
        // zero line
        g.fillStyle = zoomed ? COLORS.zeroStrong : COLORS.zero;
        g.fillRect(px, Math.round(mid), pw, Math.max(1, Math.round(dpr)));
        g.save();
        g.beginPath();
        g.rect(px, py, pw, ph);
        g.clip();
        if (!zoomed) {
          // each device-pixel column: min to max, and the RMS inside it
          const env = new Path2D();
          const rms = new Path2D();
          for (let i = 0; i < pw; i++) {
            const fa = viewStart + i * fpp;
            let a = Math.floor(fa);
            let b = Math.floor(fa + fpp);
            if (b <= a) b = a + 1;
            if (a > 0) a -= 1; // join with the previous column
            if (b > N) b = N;
            if (a >= b) continue;
            const s = rangeStats(c, a, b);
            const y0 = yOf(s.mx);
            const y1 = yOf(s.mn);
            env.rect(px + i, y0, 1, Math.max(1, y1 - y0));
            const r = Math.sqrt(s.ss / s.n);
            const r0 = Math.max(y0, yOf(r));
            const r1 = Math.min(y1, yOf(-r));
            if (r1 > r0) rms.rect(px + i, r0, 1, r1 - r0);
          }
          g.fillStyle = COLORS.env;
          g.fill(env);
          g.fillStyle = COLORS.rms;
          g.fill(rms);
        } else {
          // samples as points joined by lines
          const x = f32[c];
          const fa = Math.max(0, Math.floor(viewStart) - 1);
          const fb = Math.min(N - 1, Math.ceil(viewEnd) + 1);
          const xOf = (f) => px + ((f - viewStart + 0.0) / span) * pw;
          g.strokeStyle = COLORS.line;
          g.lineWidth = Math.max(1, 1.25 * dpr);
          g.lineJoin = "round";
          g.beginPath();
          for (let f = fa; f <= fb; f++) {
            const X = xOf(f);
            const Y = yOf(x[f]);
            if (f === fa) g.moveTo(X, Y); else g.lineTo(X, Y);
          }
          g.stroke();
          if (cssPpf >= 4) {
            const rad = Math.min(3.2, cssPpf / 5) * dpr;
            g.fillStyle = COLORS.dot;
            g.beginPath();
            for (let f = fa; f <= fb; f++) {
              const X = xOf(f);
              const Y = yOf(x[f]);
              g.moveTo(X + rad, Y);
              g.arc(X, Y, rad, 0, Math.PI * 2);
            }
            g.fill();
          }
        }
        g.restore();
        // channel label
        if (nch > 1) {
          g.fillStyle = COLORS.labelDim;
          g.font = `${10 * dpr}px -apple-system, system-ui, sans-serif`;
          g.textBaseline = "top";
          g.fillText(nch === 2 ? (c === 0 ? "L ch" : "R ch") : `ch ${c + 1}`, px + 4 * dpr, py + 3 * dpr);
        }
      }
      drawAxis(g);
      // overview
      if (!overviewCache) drawOverviewCache();
      const o = layout.over;
      g.drawImage(overviewCache, Math.round((o.x - ox) * dpr), Math.round((o.y - oy) * dpr));
    }

    function drawAxis(g) {
      const dpr = layout.dpr;
      const p = layout.plot;
      const span = viewEnd - viewStart;
      const y = (layout.axisTop - layout.top) * dpr;
      g.fillStyle = COLORS.axis;
      g.font = `${10 * dpr}px -apple-system, system-ui, sans-serif`;
      g.textBaseline = "top";
      const minPx = 90;
      const useFrames = span <= 2000;
      const unitSpan = useFrames ? span : span / sr;
      const step = niceStep((unitSpan * minPx) / p.width);
      const startU = useFrames ? viewStart : viewStart / sr;
      const endU = useFrames ? viewEnd : viewEnd / sr;
      const digits = useFrames ? 0 : Math.max(0, -Math.floor(Math.log10(step)));
      for (let u = Math.ceil(startU / step) * step; u <= endU + 1e-9; u += step) {
        const f = useFrames ? u : u * sr;
        const X = (p.x - layout.left + ((f - viewStart) / span) * p.width) * dpr;
        g.fillRect(Math.round(X), y, Math.max(1, Math.round(dpr)), 4 * dpr);
        const label = useFrames ? String(Math.round(u)) : u.toFixed(digits) + " s";
        g.fillText(label, X + 3 * dpr, y + 5 * dpr);
      }
    }

    function drawOverlay() {
      if (!N) return;
      const g = overCanvas.getContext("2d");
      const dpr = layout.dpr;
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, overCanvas.width, overCanvas.height);
      g.setTransform(dpr, 0, 0, dpr, -layout.left * dpr, -layout.top * dpr);
      const p = layout.plot;
      const top = layout.stripTop;
      const bottom = layout.plotsBottom;
      const right = p.x + p.width;
      const b = boundaries;
      const L = b[loopA];
      const R = b[loopE];
      const XL = xOfFrame(L);
      const XR = xOfFrame(R);
      // shade outside the locators
      g.fillStyle = "rgba(0,0,0,0.45)";
      for (const pl of layout.plots) {
        if (XL > p.x) g.fillRect(p.x, pl.y, Math.min(XL, right) - p.x, pl.height);
        if (XR < right) g.fillRect(Math.max(XR, p.x), pl.y, right - Math.max(XR, p.x), pl.height);
      }
      // strip background
      g.fillStyle = "#12161b";
      g.fillRect(p.x, top, p.width, STRIP_H - 2);

      // slice labels: number and role
      g.font = "11px -apple-system, system-ui, sans-serif";
      g.textBaseline = "alphabetic";
      for (let k = 0; k < slices.length; k++) {
        const xa = Math.max(xOfFrame(b[k]), p.x);
        const xb = Math.min(xOfFrame(b[k + 1]), right);
        if (xb - xa < 10) continue;
        const role = slices[k].role;
        g.save();
        g.beginPath();
        g.rect(xa + 1, top, xb - xa - 2, STRIP_H);
        g.clip();
        const dragged = drag && drag.kind === "slice" && drag.moved && drag.index === k;
        if (dragged) { g.fillStyle = "rgba(243,192,79,0.25)"; g.fillRect(xa, top, xb - xa, STRIP_H - 2); }
        else if (slot === k) { g.fillStyle = "rgba(90,174,255,0.28)"; g.fillRect(xa, top, xb - xa, STRIP_H - 2); }
        let tx = xa + (k === loopA ? 14 : 7);
        // the handle: six dots, where a press starts a reorder drag (W25)
        if (slices.length > 1 && xb - xa >= 34) {
          g.fillStyle = dragged ? COLORS.cut : COLORS.labelDim;
          for (let hx = 0; hx < 2; hx++) for (let hy = 0; hy < 3; hy++) g.fillRect(tx + hx * 4, top + 10 + hy * 4, 2, 2);
          tx += 12;
        }
        const num = String(order[k] + 1); // a slice keeps its source number wherever it plays
        g.fillStyle = order[k] === k ? COLORS.label : COLORS.cut;
        g.fillText(num, tx, top + 19);
        if (role) {
          const w = g.measureText(num).width;
          g.fillStyle = COLORS.labelDim;
          g.fillText(role, tx + w + 5, top + 19);
        }
        g.restore();
      }

      // boundaries
      const hoverPick = !drag && pointer.inside && inPlotArea(pointer.x, pointer.y) ? pickBoundary(pointer.x, pointer.y) : null;
      for (let i = 0; i < b.length; i++) {
        const X = xOfFrame(b[i]);
        if (X < p.x - 8 || X > right + 8) continue;
        const isLoc = i === loopA || i === loopE;
        const isSel = i === selected;
        const xs = Math.round(X * dpr) / dpr + 0.5 / dpr;
        let col = isLoc ? COLORS.loc : COLORS.cut;
        if (isSel) col = COLORS.cutSel;
        const w = isSel || i === hoverPick ? 2 : 1;
        g.strokeStyle = col;
        g.lineWidth = w;
        g.beginPath();
        g.moveTo(xs, top + 6);
        g.lineTo(xs, bottom);
        g.stroke();
        g.fillStyle = col;
        if (isLoc) {
          // a flag with its letter, pointing into the region
          const left = i === loopA;
          const fw = K.FLAG_PIXELS;
          g.beginPath();
          if (left) { g.moveTo(xs, top + 2); g.lineTo(xs + fw, top + 2); g.lineTo(xs + fw, top + 14); g.lineTo(xs, top + 18); }
          else { g.moveTo(xs, top + 2); g.lineTo(xs - fw, top + 2); g.lineTo(xs - fw, top + 14); g.lineTo(xs, top + 18); }
          g.closePath();
          g.fill();
          g.fillStyle = "#08111c";
          g.font = "bold 10px -apple-system, system-ui, sans-serif";
          g.textBaseline = "alphabetic";
          g.fillText(left ? "L" : "R", left ? xs + 3 : xs - fw + 3, top + 12);
        } else {
          // a small triangle at the top of the line
          g.beginPath();
          g.moveTo(xs - 5, top + 2);
          g.lineTo(xs + 5, top + 2);
          g.lineTo(xs, top + 10);
          g.closePath();
          g.fill();
        }
      }

      // the place a dragged slice would drop
      if (drag && drag.kind === "slice" && drag.moved) {
        const X = Math.min(right, Math.max(p.x, xOfFrame(b[drag.target])));
        g.fillStyle = COLORS.cutSel;
        g.fillRect(X - 1.5, top, 3, bottom - top);
      }

      // hover: the frame a press would act on
      if (!drag && pointer.inside && pointerOverPlot()) {
        const f = pointerFrame(pointer.x);
        const X = Math.round(xOfFrame(f) * dpr) / dpr + 0.5 / dpr;
        g.strokeStyle = COLORS.hover;
        g.lineWidth = 1;
        g.setLineDash([3, 3]);
        g.beginPath();
        g.moveTo(X, layout.plotsTop);
        g.lineTo(X, bottom);
        g.stroke();
        g.setLineDash([]);
        const span = viewEnd - viewStart;
        if (span < p.width && f < N) {
          for (let c = 0; c < nch; c++) {
            const pl = layout.plots[c];
            const Y = pl.y + pl.height / 2 - f32[c][f] * (pl.height / 2 - 2);
            g.strokeStyle = "#ffffff";
            g.lineWidth = 1.5;
            g.beginPath();
            g.arc(X, Y, 5, 0, Math.PI * 2);
            g.stroke();
          }
        }
      }

      // cursor line: where Add cut puts a cut
      if (editCursor !== null) {
        const X = xOfFrame(editCursor);
        if (X >= p.x && X <= right) {
          g.strokeStyle = "#8a96a3";
          g.lineWidth = 1;
          g.setLineDash([2, 4]);
          g.beginPath();
          g.moveTo(X, layout.plotsTop);
          g.lineTo(X, bottom);
          g.stroke();
          g.setLineDash([]);
        }
      }

      // playback line
      const ph = playheadFrame();
      if (ph !== null) {
        const X = xOfFrame(ph);
        if (X >= p.x && X <= right) {
          g.strokeStyle = COLORS.play;
          g.lineWidth = 1.5;
          g.beginPath();
          g.moveTo(X, layout.plotsTop);
          g.lineTo(X, bottom);
          g.stroke();
        }
      }

      // overview: locators, cuts, the view
      const o = layout.over;
      const oxOf = (f) => o.x + (f / N) * o.width;
      g.fillStyle = "rgba(0,0,0,0.45)";
      g.fillRect(o.x, o.y, oxOf(L) - o.x, o.height);
      g.fillRect(oxOf(R), o.y, o.x + o.width - oxOf(R), o.height);
      g.fillStyle = "rgba(243,192,79,0.55)";
      for (let i = 1; i < b.length - 1; i++) g.fillRect(Math.round(oxOf(b[i]) * dpr) / dpr, o.y, 1 / dpr, o.height);
      g.fillStyle = COLORS.loc;
      g.fillRect(oxOf(L), o.y, 1, o.height);
      g.fillRect(oxOf(R) - 1, o.y, 1, o.height);
      const vx0 = oxOf(viewStart);
      const vx1 = Math.max(vx0 + 2, oxOf(viewEnd));
      g.fillStyle = COLORS.view;
      g.fillRect(vx0, o.y, vx1 - vx0, o.height);
      g.strokeStyle = COLORS.viewEdge;
      g.lineWidth = 1;
      g.strokeRect(vx0 + 0.5, o.y + 0.5, vx1 - vx0 - 1, o.height - 1);
      if (ph !== null) {
        g.fillStyle = COLORS.play;
        g.fillRect(oxOf(ph), o.y, 1, o.height);
      }
    }

    function onResize() {
      if (!N) return;
      computeLayout();
      drawWave();
      drawOverlay();
    }

    // ------------------------------------------------------------------
    // Start
    // ------------------------------------------------------------------

    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("keyup", onKeyUp, true);
    overCanvas.addEventListener("mousedown", onMouseDown);
    overCanvas.addEventListener("dblclick", onDoubleClick);
    $("add-cut").addEventListener("click", () => { $("add-cut").blur(); if (ready && canAddAtCursor()) addCut(editCursor); });
    $("delete-cut").addEventListener("click", () => { $("delete-cut").blur(); if (ready && selected !== null) removeCut(selected); });
    // A press on a button first ends typing in the tempo control; if that
    // text was refused, the button does not act.
    window.addEventListener("mousedown", () => { tempoRefused = false; }, true);
    $("save").addEventListener("click", () => { $("save").blur(); if (!tempoRefused) save(); });
    $("close").addEventListener("click", () => { $("close").blur(); if (!tempoRefused) requestClose(); });
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    document.addEventListener("mouseleave", () => { pointer.inside = false; updateReadout(); scheduleOverlay(); });
    overCanvas.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("contextmenu", (e) => e.preventDefault());
    window.addEventListener("resize", onResize);
    // the toolbar can grow by a line (the unsaved mark appearing); the plots follow the area
    new ResizeObserver(() => { if (ready) onResize(); }).observe(area);
    window.addEventListener("dragover", (e) => e.preventDefault());
    window.addEventListener("drop", (e) => e.preventDefault());

    btnMeasures.addEventListener("click", () => { btnMeasures.blur(); if (ready) splitByMeasures(); });
    btnTransients.addEventListener("click", () => { btnTransients.blur(); if (ready) splitByTransients(); });
    $("source-order").addEventListener("click", () => { $("source-order").blur(); if (ready) sourceOrder(); });
    selResolution.addEventListener("change", () => { selResolution.blur(); });
    rngSensitivity.addEventListener("input", onSensitivity);
    rngSensitivity.addEventListener("change", onSensitivity);
    fldTempo.addEventListener("input", () => { tempoTouched = true; });
    fldTempo.addEventListener("change", onTempo);
    // A press on the waveform ends typing in the tempo control.
    overCanvas.addEventListener("mousedown", () => { if (document.activeElement === fldTempo) { onTempo(); fldTempo.blur(); } }, true);
    $("discard-yes").addEventListener("click", () => ipcRenderer.send("rcy-exit", 3, runReport()));
    $("discard-no").addEventListener("click", () => { dialog.hidden = true; $("discard-no").blur(); });
    ipcRenderer.on("rcy-close-request", () => requestClose());

    ipcRenderer.invoke("rcy-init").then((init) => {
      K = init.constants;
      info = init;
      N = init.frames;
      sr = init.sampleRate;
      nch = init.channels;
      selResolution.value = String(K.DEFAULT_RESOLUTION);
      rngSensitivity.value = String(K.DEFAULT_SENSITIVITY);
      sensValue.textContent = String(K.DEFAULT_SENSITIVITY);
      const bytes = init.pcm;
      const all = new Int16Array(bytes.buffer, bytes.byteOffset, (bytes.byteLength / 2) | 0);
      for (let c = 0; c < nch; c++) {
        const a = new Int16Array(N);
        const f = new Float32Array(N);
        for (let i = 0, j = c; i < N; i++, j += nch) { a[i] = all[j]; f[i] = all[j] / 32768; }
        i16.push(a);
        f32.push(f);
      }
      pyramid = f32.map(buildPyramid);
      srcF32 = f32; srcI16 = i16; srcPyramid = pyramid; srcN = N;
      applySnapshot({ b: init.boundaries, s: init.slices, bpm: init.bpm, o: init.order });
      history = [snapshot()];
      hpos = 0;
      viewStart = 0;
      viewEnd = N;
      $("file-name").textContent = init.title;
      $("file-info").textContent = `${(N / sr).toFixed(3)} s · ${sr} Hz · ${nch === 1 ? "mono" : nch === 2 ? "stereo" : nch + " ch"} · ${init.measures} measure${init.measures === 1 ? "" : "s"}`;
      audioInit();
      computeLayout();
      drawWave();
      drawOverlay();
      ready = true;
      updateReadout();
      message("Click a slice to hear it · drag a line to move it · Alt-click to add or remove a cut · = and - zoom · Space plays L to R");
      // The opening state the command line asks for.
      const o = init.options;
      if (o.resolution !== null) selResolution.value = String(o.resolution);
      if (o.sensitivity !== null) { rngSensitivity.value = String(o.sensitivity); sensValue.textContent = String(o.sensitivity); }
      if (o["expect-slices"] !== null) expectSlices = o["expect-slices"];
      if (o.bpm !== null) setTempo(o.bpm);
      if (o.split === "measures") splitByMeasures();
      if (o.split === "transients") splitByTransients();
      if (o.view !== null) setView(o.view[0], o.view[1] - o.view[0]);
      if (o.select !== null && o.select < boundaries.length) selected = o.select;
      if (o.task !== null) { $("task-text").textContent = o.task; $("task").hidden = false; }
      if (o.task !== null || expectSlices !== null) { $("task").hidden = false; onResize(); }
      events = [];
      tempoSession = null;
      opening = { boundaries: toSource().b, slices: toSource().s, order: order.map((v) => v + 1), bpm, viewStart, viewEnd, selected,
                  resolution: Number(selResolution.value), sensitivity: Number(rngSensitivity.value) };
      changed();
      setTimeout(() => { ensureCandidates(); }, 30);
    });
  }

  // ---------------------------------------------------------------------
  // Page document
  // ---------------------------------------------------------------------

  const PAGE_CSS = `
    * { box-sizing: border-box; }
    html, body { margin: 0; height: 100%; background: #0f1216; color: #c8d2dc;
      font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; overflow: hidden;
      user-select: none; -webkit-user-select: none; }
    body { display: flex; flex-direction: column; }
    #toolbar { display: flex; align-items: center; gap: 10px; padding: 8px 14px; background: #181d24;
      border-bottom: 1px solid #232a33; flex: 0 0 auto; }
    #toolbar .group { display: flex; align-items: center; gap: 6px; padding-right: 12px; border-right: 1px solid #2a323c; }
    #toolbar label { color: #8a96a3; }
    button { font: inherit; color: #e6edf3; background: #27303b; border: 1px solid #36414e; border-radius: 5px;
      padding: 4px 10px; cursor: pointer; }
    button:hover { background: #303b48; }
    button:disabled { opacity: 0.4; cursor: default; }
    #toolbar .group.end { border-right: 0; padding-right: 0; padding-left: 12px; border-left: 1px solid #2a323c; }
    #save { background: #2f6f4f; border-color: #3d8a63; font-weight: 600; }
    #save.dirty { background: #3c9a6a; }
    #unsaved { color: #f0c05a; }
    #task { flex: 0 0 auto; display: flex; gap: 16px; padding: 7px 14px; background: #1f2a36; border-bottom: 1px solid #2f3d4d;
      color: #e6edf3; font-size: 14px; }
    #task[hidden] { display: none; }
    #expect { margin-left: auto; }
    #expect.ok { color: #6fd39b; } #expect.short { color: #f0c05a; }
    #hint { flex: 0 0 auto; padding: 4px 14px; color: #8a96a3; background: #14181e; border-top: 1px solid #232a33;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    button:active { background: #3a4757; }
    select { font: inherit; color: #e6edf3; background: #27303b; border: 1px solid #36414e; border-radius: 5px; padding: 3px 4px; }
    input[type=range] { width: 140px; accent-color: #f3c04f; }
    input[type=number] { font: inherit; color: #e6edf3; background: #27303b; border: 1px solid #36414e; border-radius: 5px;
      padding: 3px 4px; width: 9ch; font-variant-numeric: tabular-nums; user-select: text; -webkit-user-select: text; }
    #sens-value { display: inline-block; width: 2ch; text-align: right; color: #e6edf3; font-variant-numeric: tabular-nums; }
    #file { margin-left: auto; text-align: right; line-height: 1.25; }
    #file-name { color: #e6edf3; font-weight: 600; }
    #file-info { color: #7d8995; font-size: 11px; }
    #area { position: relative; flex: 1 1 auto; min-height: 160px; }
    #area canvas { position: absolute; left: 0; top: 0; }
    #status { flex: 0 0 auto; display: flex; gap: 16px; padding: 5px 14px; background: #181d24; border-top: 1px solid #232a33;
      font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; }
    #status-readout { color: #c8d2dc; }
    #status-msg { color: #8a96a3; margin-left: auto; overflow: hidden; text-overflow: ellipsis; }
    #status-msg.error { color: #ff7b6e; }
    #discard-confirm { position: fixed; inset: 0; background: rgba(5,8,12,0.6); display: flex; align-items: center; justify-content: center; }
    #discard-confirm[hidden] { display: none; }
    #discard-box { background: #1c222a; border: 1px solid #3a4553; border-radius: 8px; padding: 18px 20px; width: 340px;
      box-shadow: 0 10px 40px rgba(0,0,0,0.5); }
    #discard-box p { margin: 0 0 14px; font-size: 13px; color: #e6edf3; }
    #discard-box .buttons { display: flex; justify-content: flex-end; gap: 8px; }
    #discard-yes { background: #6b2a25; border-color: #8a3a33; }
  `;

  function pageHtml() {
    return `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>rcy-window</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:">
<style>${PAGE_CSS}</style></head>
<body>
<div id="toolbar">
  <div class="group">
    <button id="split-measures" type="button" tabindex="-1">Split by Measures</button>
    <label for="resolution">per measure</label>
    <select id="resolution" tabindex="-1">
      <option value="1">1</option><option value="2">2</option><option value="4">4</option>
      <option value="8">8</option><option value="16">16</option><option value="32">32</option>
    </select>
  </div>
  <div class="group">
    <button id="split-transients" type="button" tabindex="-1">Split by Transients</button>
    <label for="sensitivity">sensitivity</label>
    <input id="sensitivity" type="range" min="0" max="99" step="1" value="50">
    <span id="sens-value">50</span>
  </div>
  <div class="group">
    <label for="bpm">tempo</label>
    <input id="bpm" type="number" step="any" min="0" tabindex="-1" title="Beats per minute saved with the kit; the audio is not changed">
    <label for="bpm">bpm</label>
  </div>
  <div class="group">
    <button id="add-cut" type="button" tabindex="-1" disabled title="Adds a cut where you last clicked the waveform">Add cut</button>
    <button id="delete-cut" type="button" tabindex="-1" disabled title="Removes the selected cut">Delete cut</button>
    <button id="source-order" type="button" tabindex="-1" disabled title="Puts reordered slices back in the order they have in the source">Source order</button>
  </div>
  <div id="file"><div id="file-name"></div><div id="file-info"></div></div>
  <div class="group end">
    <span id="unsaved" hidden>unsaved edits</span>
    <button id="close" type="button" tabindex="-1">Close without saving ⌘W</button>
    <button id="save" type="button" tabindex="-1">Save ⌘S</button>
  </div>
</div>
<div id="task" hidden><span id="task-text"></span><span id="expect"></span></div>
<div id="area"><canvas id="wave"></canvas><canvas id="over"></canvas></div>
<div id="hint">Click a slice to hear it · drag a line to move it · drag a slice's number to reorder, ⌘C ⌘V ⌘D ⌘X copy, paste, duplicate, cut it · double-click the waveform to add a cut, double-click a cut to remove it · scroll or = and − to zoom, F for the whole file · Space plays L to R · Save when done</div>
<div id="status"><span id="status-readout">Loading…</span><span id="status-msg"></span></div>
<div id="discard-confirm" hidden><div id="discard-box">
  <p>The slices have unsaved edits. Close and discard them?</p>
  <div class="buttons"><button id="discard-no" type="button" tabindex="-1">Keep editing</button>
  <button id="discard-yes" type="button" tabindex="-1">Discard</button></div>
</div></div>
<script>(${pageProgram.toString()})();</script>
</body></html>`;
  }

  // ---------------------------------------------------------------------
  // Main process
  // ---------------------------------------------------------------------

  let win = null;
  let exiting = false;

  // W20: every run leaves a record of what was asked, what the person did and
  // what came out, whichever way the window ends.
  let pageReport = null;
  function exitWith(code) {
    if (exiting) return;
    exiting = true;
    const ended = new Date();
    const record = {
      rcy_window_run: 1,
      arguments: programArguments(),
      started_at: startedAt.toISOString(),
      ended_at: ended.toISOString(),
      duration_ms: ended - startedAt,
      exit_code: code,
      outcome: code === 0 ? "saved" : "closed without saving",
      manifest: launch.manifestPath,
      manifest_read: { boundaries: launch.boundaries, slices: launch.slices, bpm: launch.bpm, measures: launch.measures },
      opening: pageReport ? pageReport.opening : null,
      events: pageReport ? pageReport.events : [],
      final: pageReport ? pageReport.final : null,
    };
    try {
      fs.writeFileSync(recordPath, JSON.stringify(record, null, 2) + "\n");
    } catch (err) {
      process.stderr.write(`rcy-window: run record not written: ${err.message}\n`);
      app.exit(1);
      return;
    }
    app.exit(code);
  }

  app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");

  ipcMain.handle("rcy-init", () => ({
    constants: CONSTANTS,
    frames: launch.wav.frames,
    sampleRate: launch.wav.sampleRate,
    channels: launch.wav.channels,
    pcm: new Uint8Array(launch.wav.data), // a copy of the frames only
    boundaries: launch.boundaries,
    slices: launch.slices,
    order: launch.order,
    bpm: launch.bpm,
    measures: launch.measures,
    tempoGrammar: TEMPO_GRAMMAR,
    title: path.basename(launch.manifestPath),
    options: launchOptions,
  }));

  ipcMain.handle("rcy-save", (_e, edit) => {
    const r = saveManifest(edit && edit.boundaries, edit && edit.slices, edit && edit.bpm, edit && edit.order);
    if (r.ok) { pageReport = edit.report; setImmediate(() => exitWith(0)); }
    return r;
  });

  // The page asks before it accepts a typed tempo: the range is the SDK's.
  ipcMain.on("rcy-tempo-writable", (e, v) => { e.returnValue = typeof v === "number" && Number.isFinite(v) && rcySdk.tempoWritable(v); });

  ipcMain.on("rcy-exit", (_e, code, report) => { pageReport = report || null; exitWith(code === 0 ? 0 : 3); });

  app.on("window-all-closed", () => exitWith(3));
  // SPEC-GAP: quitting the app (Dock menu, logout) is treated as Close (W05):
  // it is held and the page decides, asking first if there are unsaved edits.
  app.on("before-quit", (e) => {
    if (exiting) return;
    e.preventDefault();
    if (win && !win.isDestroyed()) win.webContents.send("rcy-close-request");
    else exitWith(3);
  });

  app.whenReady().then(() => {
    // No application menu: its default shortcuts (Cmd+W, Cmd+Z, Cmd+Q) would
    // bypass W05 and W13. Every key reaches the page instead.
    Menu.setApplicationMenu(null);
    win = new BrowserWindow({
      width: 1280,
      height: 760,
      minWidth: 640,
      minHeight: 360,
      backgroundColor: "#0f1216",
      title: `rcy-window — ${path.basename(launch.manifestPath)}`,
      autoHideMenuBar: true,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        sandbox: false,
        spellcheck: false,
        backgroundThrottling: false,
        autoplayPolicy: "no-user-gesture-required",
      },
    });
    win.on("page-title-updated", (e) => e.preventDefault());
    win.on("close", (e) => {
      if (exiting) return;
      e.preventDefault();
      win.webContents.send("rcy-close-request");
    });
    win.webContents.on("will-navigate", (e) => e.preventDefault());
    win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    win.webContents.on("render-process-gone", () => exitWith(3));
    win.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(pageHtml()));
  });
})();
