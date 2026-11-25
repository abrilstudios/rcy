// Floor scenarios for rcy-window (WINDOW.md), driven through Playwright's
// Electron support with real pointer and key events.
//
// Usage: node scenarios.js ELECTRON ARTIFACT RCY_EXPORT AMEN_WAV [name-filter]
// Requires playwright-core on NODE_PATH. Prints one JSON line per scenario
// and exits 1 if any floor scenario fails.
"use strict";
const { _electron } = require("playwright-core");
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const assert = require("node:assert/strict");

const [ELECTRON, ARTIFACT, RCY_EXPORT, AMEN, FILTER] = process.argv.slice(2);
if (!AMEN) { console.error("usage: scenarios.js ELECTRON ARTIFACT RCY_EXPORT AMEN_WAV [filter]"); process.exit(2); }

const READY_TIMEOUT_MS = 15000;   // parameter: launch to drawn waveform; the stub took 3 s
const EXIT_TIMEOUT_MS = 8000;     // parameter: key press to process exit
const DRAG_PIXELS = 40;           // parameter: pointer travel in the move scenario
const RATE = 44100;
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "rcy-window-"));

function exportKit(dir, args) {
  const r = spawnSync("node", [RCY_EXPORT, ...args, "--out", dir], { encoding: "utf8" });
  assert.equal(r.status, 0, "rcy-export failed: " + r.stderr);
  return path.join(dir, path.basename(dir) + ".rcy.json");
}

// Six decaying 220 Hz bursts with digital silence between; the first starts at frame 0.
const BURST_STARTS = [0, 11025, 19845, 33075, 44100, 59535];
const BURST_FRAMES = 3528;        // 80 ms
const BURST_TOTAL = 70560;        // 1.6 s
function writeBursts(file) {
  const data = Buffer.alloc(BURST_TOTAL * 4);
  for (const s of BURST_STARTS) for (let i = 0; i < BURST_FRAMES; i++) {
    const v = Math.round(26000 * Math.exp(-i / 800) * Math.sin(2 * Math.PI * 220 * i / RATE + Math.PI / 2));
    data.writeInt16LE(v, (s + i) * 4); data.writeInt16LE(v, (s + i) * 4 + 2);
  }
  const h = Buffer.alloc(44);
  h.write("RIFF", 0); h.writeUInt32LE(36 + data.length, 4); h.write("WAVEfmt ", 8); h.writeUInt32LE(16, 16);
  h.writeUInt16LE(1, 20); h.writeUInt16LE(2, 22); h.writeUInt32LE(RATE, 24); h.writeUInt32LE(RATE * 4, 28);
  h.writeUInt16LE(4, 32); h.writeUInt16LE(16, 34); h.write("data", 36); h.writeUInt32LE(data.length, 40);
  fs.writeFileSync(file, Buffer.concat([h, data]));
}

const amenManifest = exportKit(path.join(scratch, "amen"), ["--input", AMEN, "--measures", "4", "--resolution", "4"]);
const amen8 = JSON.parse(fs.readFileSync(exportKit(path.join(scratch, "amen8"), ["--input", AMEN, "--measures", "4", "--resolution", "8"])));
const burstsWav = path.join(scratch, "bursts-src.wav"); writeBursts(burstsWav);
const burstsManifest = exportKit(path.join(scratch, "bursts"), ["--input", burstsWav, "--measures", "1", "--resolution", "1"]);

let runs = 0;
async function open(manifest, out, extra) {
  const record = path.join(scratch, "run-" + (runs++) + ".json");
  const args = [ARTIFACT, "--manifest", manifest, "--record", record].concat(out ? ["--out", out] : [], extra || []);
  const app = await _electron.launch({ executablePath: ELECTRON, args });
  const exit = new Promise((resolve) => app.process().on("exit", (code) => resolve(code)));
  const page = await app.firstWindow();
  await page.waitForFunction(() => typeof rcyWindowState === "function" && rcyWindowState().ready, null, { timeout: READY_TIMEOUT_MS });
  const state = () => page.evaluate(() => rcyWindowState());
  const exitCode = () => Promise.race([exit, new Promise((_, rej) => setTimeout(() => rej(new Error("window did not exit")), EXIT_TIMEOUT_MS))]);
  return { app, page, state, exitCode, record, kill: () => { try { app.process().kill("SIGKILL"); } catch (e) {} } };
}
const xOf = (s, frame) => s.plot.x + (frame - s.viewStart) / (s.viewEnd - s.viewStart) * s.plot.width;
const frameAt = (s, x) => s.viewStart + (x - s.plot.x) / s.plot.width * (s.viewEnd - s.viewStart);
// The process may exit before Playwright hears back from the action that ended it.
const leave = (action) => action.catch(() => {});
const midY = (s) => s.plot.y + s.plot.height / 2;
const read = (f) => JSON.parse(fs.readFileSync(f, "utf8"));
const meta = (m) => m.slices.map((s) => [s.key, s.file, s.role]);
const near = (a, b, tol, what) => assert.ok(Math.abs(a - b) <= tol, `${what}: ${a} vs ${b} (tolerance ${tol})`);
function acceptedByExport(manifest) {
  const dir = path.join(scratch, "re-" + path.basename(manifest, ".json"));
  const r = spawnSync("node", [RCY_EXPORT, "--from-manifest", manifest, "--out", dir], { encoding: "utf8" });
  assert.equal(r.status, 0, "rcy-export refused the saved manifest: " + r.stderr);
  const m = read(manifest);
  for (const s of m.slices) {
    const bytes = fs.statSync(path.join(dir, s.file)).size - 44;
    assert.equal(bytes / (2 * m.channels), s.end - s.start, "length of " + s.file);
  }
}

const scenarios = {
  "01 save with no edit is byte-identical": async () => {
    const before = fs.readFileSync(amenManifest);
    const w = await open(amenManifest);
    await leave(w.page.keyboard.press("Meta+s"));
    assert.equal(await w.exitCode(), 0);
    assert.ok(before.equals(fs.readFileSync(amenManifest)), "manifest bytes changed");
  },
  "02 drag moves one boundary": async () => {
    const out = path.join(scratch, "moved.rcy.json"), before = fs.readFileSync(amenManifest), a = read(amenManifest);
    const w = await open(amenManifest, out);
    const s = await w.state();
    assert.equal(s.frames, 307411); assert.deepEqual(s.boundaries, a.boundaries);
    assert.equal(s.viewStart, 0); assert.equal(s.viewEnd, 307411);
    const x0 = xOf(s, s.boundaries[2]), x1 = x0 + DRAG_PIXELS;
    await w.page.mouse.move(x0, midY(s)); await w.page.mouse.down();
    await w.page.mouse.move(x0 + DRAG_PIXELS / 2, midY(s)); await w.page.mouse.move(x1, midY(s)); await w.page.mouse.up();
    const t = await w.state();
    near(t.boundaries[2], frameAt(s, x1), (s.viewEnd - s.viewStart) / s.plot.width + 1, "dragged boundary");
    assert.equal(t.selected, 2); assert.equal(t.dirty, true);
    await leave(w.page.keyboard.press("Meta+s"));
    assert.equal(await w.exitCode(), 0);
    const b = read(out);
    assert.deepEqual(b.boundaries.filter((_, i) => i !== 2), a.boundaries.filter((_, i) => i !== 2));
    assert.equal(b.boundaries[2], t.boundaries[2]);
    assert.deepEqual(meta(b), meta(a)); assert.equal(b.bpm, a.bpm); assert.equal(b.measures, a.measures);
    assert.equal(path.resolve(path.dirname(out), b.source), path.resolve(AMEN));
    assert.ok(before.equals(fs.readFileSync(amenManifest)), "input manifest changed");
    acceptedByExport(out);
  },
  "03 option-click adds a cut": async () => {
    const out = path.join(scratch, "added.rcy.json"), a = read(amenManifest);
    const w = await open(amenManifest, out);
    const s = await w.state();
    const x = xOf(s, (a.boundaries[2] + a.boundaries[3]) / 2);
    await w.page.keyboard.down("Alt"); await w.page.mouse.click(x, midY(s)); await w.page.keyboard.up("Alt");
    const t = await w.state();
    assert.equal(t.boundaries.length, 18);
    near(t.boundaries[3], frameAt(s, x), (s.viewEnd - s.viewStart) / s.plot.width + 1, "added cut");
    await leave(w.page.keyboard.press("Meta+s"));
    assert.equal(await w.exitCode(), 0);
    const b = read(out);
    assert.deepEqual(b.slices.map((v) => v.key), Array.from({ length: 17 }, (_, i) => 60 + i));
    assert.deepEqual(b.slices.map((v) => v.file), Array.from({ length: 17 }, (_, i) => String(i + 1).padStart(3, "0") + ".wav"));
    acceptedByExport(out);
  },
  "04 delete removes the selected cut": async () => {
    const out = path.join(scratch, "removed.rcy.json"), a = read(amenManifest);
    const w = await open(amenManifest, out);
    const s = await w.state();
    await w.page.mouse.click(xOf(s, a.boundaries[3]), midY(s));
    assert.equal((await w.state()).selected, 3);
    await w.page.keyboard.press("Delete");
    await leave(w.page.keyboard.press("Meta+s"));
    assert.equal(await w.exitCode(), 0);
    const b = read(out);
    assert.deepEqual(b.boundaries, a.boundaries.filter((_, i) => i !== 3));
    assert.deepEqual(b.slices.map((v) => v.key), Array.from({ length: 15 }, (_, i) => 60 + i));
    acceptedByExport(out);
  },
  "05 close without saving exits 3 and writes nothing": async () => {
    const before = fs.readFileSync(amenManifest), mtime = fs.statSync(amenManifest).mtimeMs;
    let w = await open(amenManifest);
    await leave(w.page.keyboard.press("Meta+w"));
    assert.equal(await w.exitCode(), 3, "clean close by key");
    w = await open(amenManifest);
    const s = await w.state();
    await w.page.keyboard.down("Alt"); await w.page.mouse.click(xOf(s, 100000), midY(s)); await w.page.keyboard.up("Alt");
    assert.equal((await w.state()).dirty, true);
    await w.app.evaluate(({ BrowserWindow }) => { BrowserWindow.getAllWindows()[0].close(); });
    await w.page.locator("#discard-confirm").waitFor({ state: "visible", timeout: 3000 });
    await w.page.locator("#discard-no").click();
    assert.equal((await w.state()).boundaries.length, 18, "edit survives discard-no");
    await w.page.keyboard.press("Meta+w");
    await leave(w.page.locator("#discard-yes").click());
    assert.equal(await w.exitCode(), 3, "discarded close");
    assert.ok(before.equals(fs.readFileSync(amenManifest))); assert.equal(fs.statSync(amenManifest).mtimeMs, mtime);
  },
  "06 a manifest with decreasing boundaries is refused": async () => {
    const bad = path.join(scratch, "amen", "bad.rcy.json"), m = read(amenManifest);
    [m.boundaries[2], m.boundaries[3]] = [m.boundaries[3], m.boundaries[2]];
    fs.writeFileSync(bad, JSON.stringify(m)); const before = fs.readFileSync(bad);
    for (const args of [["--manifest", bad, "--record", path.join(scratch, "r.json")], [], ["--manifest", amenManifest], ["--manifest", path.join(scratch, "absent.json"), "--record", path.join(scratch, "r.json")], ["--manifest", amenManifest, "--record", path.join(scratch, "r.json"), "--bogus"], ["--manifest", amenManifest, "--record", path.join(scratch, "r.json"), "--view", "5:999999999"], ["--manifest", amenManifest, "--record", path.join(scratch, "r.json"), "--bpm", "fast"], ["--manifest", amenManifest, "--record", path.join(scratch, "r.json"), "--bpm", "1"]]) {
      const child = spawn(ELECTRON, [ARTIFACT, ...args], { stdio: ["ignore", "ignore", "pipe"] });
      let err = ""; child.stderr.on("data", (d) => { err += d; });
      const code = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => { child.kill("SIGKILL"); reject(new Error("no exit for args " + args.join(" "))); }, EXIT_TIMEOUT_MS);
        child.on("exit", (c) => { clearTimeout(timer); resolve(c); });
      });
      assert.equal(code, 2, "exit code for args " + args.join(" "));
      assert.ok(err.trim().length > 0, "stderr line for args " + args.join(" "));
    }
    assert.ok(before.equals(fs.readFileSync(bad)));
  },
  "07 zoom reaches 32 frames about the pointer and arrows move one frame": async () => {
    const w = await open(amenManifest);
    const s = await w.state();
    const x = Math.round(xOf(s, s.boundaries[5])), anchor = frameAt(s, x);
    await w.page.mouse.click(x, midY(s));
    assert.equal((await w.state()).selected, 5);
    await w.page.keyboard.press("=");
    let t = await w.state();
    near(t.viewEnd - t.viewStart, 307411 / 2, 1, "span after one zoom step");
    near(frameAt(t, x), anchor, (t.viewEnd - t.viewStart) / t.plot.width, "anchor after one step");
    for (let i = 0; i < 16; i++) await w.page.keyboard.press("=");
    t = await w.state();
    near(t.viewEnd - t.viewStart, 32, 1e-6, "narrowest span");
    near(frameAt(t, x), anchor, 1, "anchor at narrowest view");
    await w.page.keyboard.press("ArrowRight");
    assert.equal((await w.state()).boundaries[5], s.boundaries[5] + 1);
    await w.page.keyboard.press("ArrowLeft"); await w.page.keyboard.press("ArrowLeft");
    assert.equal((await w.state()).boundaries[5], s.boundaries[5] - 1);
    await w.page.keyboard.press("f");
    t = await w.state();
    assert.equal(t.viewStart, 0); assert.equal(t.viewEnd, 307411);
    for (let i = 0; i < 3; i++) await w.page.keyboard.press("-");
    t = await w.state();
    assert.equal(t.viewStart, 0); assert.equal(t.viewEnd, 307411);
    w.kill();
  },
  "08 split by measures equals rcy-export's cut": async () => {
    const out = path.join(scratch, "split8.rcy.json");
    const w = await open(amenManifest, out);
    await w.page.locator("#resolution").selectOption("8");
    await w.page.locator("#split-measures").click();
    assert.deepEqual((await w.state()).boundaries, amen8.boundaries);
    await leave(w.page.keyboard.press("Meta+s"));
    assert.equal(await w.exitCode(), 0);
    const b = read(out);
    assert.deepEqual(b.boundaries, amen8.boundaries); assert.deepEqual(meta(b), meta(amen8));
    acceptedByExport(out);
  },
  "09 split by transients finds each burst": async () => {
    const w = await open(burstsManifest);
    assert.equal((await w.page.locator("#sensitivity").inputValue()), "50");
    await w.page.locator("#split-transients").click();
    const t = await w.state();
    assert.equal(t.boundaries.length, BURST_STARTS.length + 1, "cuts: " + JSON.stringify(t.boundaries));
    BURST_STARTS.slice(1).forEach((start, i) => {
      const cut = t.boundaries[i + 1], previousEnd = BURST_STARTS[i] + BURST_FRAMES;
      assert.ok(cut > previousEnd && cut <= start + 1, `cut ${cut} for burst at ${start}`);
    });
    assert.deepEqual(t.slices.map((v) => v.key), [60, 61, 62, 63, 64, 65]);
    w.kill();
  },
  "10 more sensitivity never gives fewer cuts": async () => {
    const w = await open(amenManifest);
    await w.page.locator("#split-transients").click();
    const counts = [];
    await w.page.locator("#sensitivity").focus();
    for (let i = 0; i < 50; i++) await w.page.keyboard.press("ArrowLeft");
    for (let v = 0; v <= 99; v += 9) {
      assert.equal(await w.page.locator("#sensitivity").inputValue(), String(v));
      const t = await w.state();
      counts.push(t.boundaries.length - 2);
      assert.ok(t.slices.every((s) => s.key <= 127));
      for (let i = 0; i < 9; i++) await w.page.keyboard.press("ArrowRight");
    }
    for (let i = 1; i < counts.length; i++) assert.ok(counts[i] >= counts[i - 1], "counts " + counts.join(","));
    assert.ok(counts[counts.length - 1] > counts[0], "sensitivity has no effect: " + counts.join(","));
    console.log(JSON.stringify({ info: "amen cuts at sensitivity 0,9,..,99", counts }));
    w.kill();
  },
  "11 undo returns to the manifest read": async () => {
    const a = read(amenManifest);
    const w = await open(amenManifest);
    const s = await w.state();
    await w.page.locator("#resolution").selectOption("8");
    await w.page.locator("#split-measures").click();
    await w.page.keyboard.down("Alt"); await w.page.mouse.click(xOf(s, 100000), midY(s)); await w.page.keyboard.up("Alt");
    assert.equal((await w.state()).dirty, true);
    await w.page.keyboard.press("Meta+z"); await w.page.keyboard.press("Meta+z");
    let t = await w.state();
    assert.deepEqual(t.boundaries, a.boundaries); assert.deepEqual(t.slices.map((v) => [v.key, v.file, v.role]), meta(a));
    assert.equal(t.dirty, false);
    await w.page.keyboard.press("Shift+Meta+z");
    assert.equal((await w.state()).dirty, true);
    await w.page.keyboard.press("Meta+z");
    await leave(w.page.keyboard.press("Meta+w"));
    assert.equal(await w.exitCode(), 3, "no confirmation after full undo");
  },
  "12 audition reports playing (not verified by audio)": async () => {
    const w = await open(amenManifest);
    await w.page.keyboard.press("2");
    await w.page.waitForFunction(() => rcyWindowState().playing, null, { timeout: 2000 });
    await w.page.waitForFunction(() => !rcyWindowState().playing, null, { timeout: 3000 });
    await w.page.keyboard.press("Space");
    await w.page.waitForFunction(() => rcyWindowState().playing, null, { timeout: 2000 });
    await w.page.keyboard.press("Space");
    await w.page.waitForFunction(() => !rcyWindowState().playing, null, { timeout: 2000 });
    w.kill();
  },
  "13 a locator passes cuts and removes them": async () => {
    const out = path.join(scratch, "locator.rcy.json"), a = read(amenManifest);
    const w = await open(amenManifest, out);
    const s = await w.state(), y = midY(s);
    const xR = xOf(s, 307411), xIn = xOf(s, (a.boundaries[13] + a.boundaries[14]) / 2);
    await w.page.mouse.move(xR, y); await w.page.mouse.down();
    await w.page.mouse.move((xR + xIn) / 2, y); await w.page.mouse.move(xIn, y);
    let t = await w.state();
    assert.deepEqual(t.boundaries.slice(0, 14), a.boundaries.slice(0, 14));
    assert.equal(t.boundaries.length, 15, "two cuts passed: " + JSON.stringify(t.boundaries));
    near(t.boundaries[14], frameAt(s, xIn), (s.viewEnd - s.viewStart) / s.plot.width + 1, "R locator");
    await w.page.mouse.move(xOf(s, (a.boundaries[15] + a.boundaries[16]) / 2), y);
    assert.equal((await w.state()).boundaries.length, 17, "cuts restored within the drag");
    await w.page.mouse.move(xIn, y); await w.page.mouse.up();
    const xL = xOf(s, 0), xL2 = xOf(s, (a.boundaries[1] + a.boundaries[2]) / 2);
    await w.page.mouse.move(xL, y); await w.page.mouse.down();
    await w.page.mouse.move((xL + xL2) / 2, y); await w.page.mouse.move(xL2, y); await w.page.mouse.up();
    t = await w.state();
    assert.equal(t.boundaries.length, 14);
    assert.deepEqual(t.boundaries.slice(1, 13), a.boundaries.slice(2, 14));
    assert.deepEqual(t.slices.map((v) => v.key), Array.from({ length: 13 }, (_, i) => 60 + i));
    await w.page.keyboard.press("Meta+z"); await w.page.keyboard.press("Meta+z");
    assert.deepEqual((await w.state()).boundaries, a.boundaries);
    await w.page.keyboard.press("Shift+Meta+z"); await w.page.keyboard.press("Shift+Meta+z");
    await leave(w.page.locator("#save").click());
    assert.equal(await w.exitCode(), 0, "save button");
    assert.deepEqual(read(out).boundaries, t.boundaries);
    acceptedByExport(out);
  },
  "14 double-click and the buttons add and remove cuts": async () => {
    const a = read(amenManifest);
    const w = await open(amenManifest);
    const s = await w.state(), y = midY(s), tol = (s.viewEnd - s.viewStart) / s.plot.width + 1;
    assert.equal(s.cursor, null);
    assert.equal(await w.page.locator("#add-cut").isDisabled(), true);
    assert.equal(await w.page.locator("#delete-cut").isDisabled(), true);
    for (const id of ["save", "close", "hint", "add-cut", "delete-cut"]) assert.equal(await w.page.locator("#" + id).isVisible(), true, id + " visible");
    const x1 = xOf(s, (a.boundaries[4] + a.boundaries[5]) / 2);
    await w.page.mouse.dblclick(x1, y);
    let t = await w.state();
    assert.equal(t.boundaries.length, 18); near(t.boundaries[5], frameAt(s, x1), tol, "double-click cut");
    assert.equal(t.selected, 5);
    await w.page.waitForFunction(() => !rcyWindowState().playing, null, { timeout: 500 });
    await w.page.locator("#delete-cut").click();
    assert.deepEqual((await w.state()).boundaries, a.boundaries);
    await w.page.mouse.dblclick(xOf(s, a.boundaries[8]), y);
    assert.deepEqual((await w.state()).boundaries, a.boundaries.filter((_, i) => i !== 8));
    const x2 = xOf(s, (a.boundaries[10] + a.boundaries[11]) / 2);
    await w.page.mouse.click(x2, y);
    near((await w.state()).cursor, frameAt(s, x2), tol, "cursor");
    await w.page.locator("#add-cut").click();
    t = await w.state();
    assert.equal(t.boundaries.length, 17); near(t.boundaries[10], frameAt(s, x2), tol, "button cut");
    await w.page.locator("#close").click();
    await leave(w.page.locator("#discard-yes").click());
    assert.equal(await w.exitCode(), 3, "close button");
  },
  "15 the command line sets the opening state and the end condition, and the run is recorded": async () => {
    const out = path.join(scratch, "declared.rcy.json");
    const w = await open(amenManifest, out, ["--split", "measures", "--resolution", "8", "--view", "100000:200000", "--select", "3",
      "--task", "Remove one cut", "--expect-slices", "31"]);
    const s = await w.state();
    assert.deepEqual(s.boundaries, amen8.boundaries);
    assert.equal(s.viewStart, 100000); assert.equal(s.viewEnd, 200000); assert.equal(s.selected, 3);
    assert.equal(await w.page.locator("#task").innerText().then((v) => v.includes("Remove one cut")), true);
    assert.equal(await w.page.locator("#save").isDisabled(), true);
    await w.page.keyboard.press("Meta+s");
    assert.equal((await w.state()).ready, true, "save refused while the slice count is wrong");
    assert.equal(fs.existsSync(out), false);
    await w.page.keyboard.press("2");
    await w.page.keyboard.press("Delete");
    await leave(w.page.locator("#save").click());
    assert.equal(await w.exitCode(), 0);
    assert.equal(read(out).slices.length, 31);
    const r = read(w.record);
    assert.equal(r.exit_code, 0); assert.equal(r.outcome, "saved");
    assert.deepEqual(r.opening.boundaries, amen8.boundaries);
    assert.deepEqual(r.events.map((e) => e.kind), ["play", "edit"]);
    assert.deepEqual(r.final.boundaries, read(out).boundaries);
    assert.ok(r.arguments.includes("--expect-slices"));
    const c = await open(amenManifest);
    await leave(c.page.keyboard.press("Meta+w"));
    assert.equal(await c.exitCode(), 3);
    assert.equal(read(c.record).exit_code, 3);
  },
  "16 a manifest's buffer survives a save": async () => {
    const src = path.join(scratch, "buffered.rcy.json");
    const text = fs.readFileSync(amenManifest, "utf8").replace(/("measures": \d+,\n)/, '$1  "buffer_ms": 20,\n');
    assert.ok(text.includes('"buffer_ms": 20'));
    fs.writeFileSync(src, text);
    const out = path.join(path.dirname(amenManifest), "buffered-out.rcy.json");
    fs.copyFileSync(src, path.join(path.dirname(amenManifest), "buffered-in.rcy.json"));
    const w = await open(path.join(path.dirname(amenManifest), "buffered-in.rcy.json"), out);
    await leave(w.page.keyboard.press("Meta+s"));
    assert.equal(await w.exitCode(), 0);
    assert.equal(fs.readFileSync(out, "utf8"), text);
  },
  "17 the tempo is set at launch and by the control, undone, and saved": async () => {
    const out = path.join(scratch, "tempo.rcy.json"), a = read(amenManifest);
    const w = await open(amenManifest, out, ["--bpm", "165.5"]);
    const type = async (text, end) => {
      await w.page.locator("#bpm").click(); await w.page.keyboard.press("Meta+a");
      await w.page.keyboard.type(text); await w.page.keyboard.press(end);
    };
    let t = await w.state();
    assert.equal(t.bpm, 165.5); assert.equal(t.dirty, true);
    assert.equal(await w.page.locator("#bpm").inputValue(), "165.5");
    await type("170", "Enter");
    t = await w.state();
    assert.equal(t.bpm, 170); assert.equal(t.playing, false, "digits typed in the control play nothing");
    assert.deepEqual(t.boundaries, a.boundaries);
    assert.equal(await w.page.evaluate(() => document.activeElement.id), "", "Enter releases focus");
    await type("172.25", "Enter");
    assert.equal((await w.state()).bpm, 172.25);
    await type("1", "Enter");
    assert.equal((await w.state()).bpm, 172.25, "a tempo MIDI cannot hold is not taken");
    assert.equal(await w.page.locator("#bpm").inputValue(), "172.25");
    await w.page.locator("#bpm").click();
    for (let i = 0; i < 3; i++) await w.page.keyboard.press("ArrowUp");
    await w.page.keyboard.press("Enter");
    assert.equal((await w.state()).bpm, 175.25, "three steps of the control's arrows");
    await type("172.25", "Enter");
    await type("90", "Escape");
    assert.equal((await w.state()).bpm, 172.25, "Escape restores");
    await w.page.keyboard.press("Meta+z");
    assert.equal((await w.state()).bpm, 165.5, "two changes on the control are one undo step");
    await w.page.keyboard.press("Meta+z");
    t = await w.state();
    assert.equal(t.bpm, a.bpm); assert.equal(t.dirty, false);
    await w.page.keyboard.press("Shift+Meta+z"); await w.page.keyboard.press("Shift+Meta+z");
    assert.equal((await w.state()).bpm, 172.25);
    await leave(type("174", "Meta+s"));
    assert.equal(await w.exitCode(), 0);
    const b = read(out);
    assert.equal(b.bpm, 174, "Save applies the typed tempo"); assert.equal(b.measures, a.measures);
    assert.deepEqual(b.boundaries, a.boundaries); assert.deepEqual(meta(b), meta(a));
    const r = read(w.record);
    assert.equal(r.manifest_read.bpm, a.bpm); assert.equal(r.opening.bpm, 165.5); assert.equal(r.final.bpm, 174);
    assert.deepEqual(r.events.filter((e) => e.kind === "edit").map((e) => e.bpm), [170, 172.25, 173.25, 174.25, 175.25, 172.25, 174]);
    acceptedByExport(out);
  },
  "18 an untouched or restored tempo stays exact, and a refused tempo stops Save": async () => {
    const out = path.join(scratch, "tempo-exact.rcy.json"), a = read(amenManifest);
    assert.notEqual(a.bpm, Number(a.bpm.toFixed(2)), "the fixture's tempo has more than two decimals");
    const w = await open(amenManifest, out);
    const bpmField = w.page.locator("#bpm");
    await bpmField.click(); await w.page.keyboard.press("Enter");
    assert.equal((await w.state()).dirty, false, "Enter on untouched text");
    await bpmField.click(); await w.page.keyboard.press("ArrowUp");
    await w.page.keyboard.press("Enter");
    let t = await w.state();
    assert.equal(t.dirty, true); near(t.bpm, Number(a.bpm.toFixed(2)) + 1, 1e-9, "one step from the shown value");
    await bpmField.click(); await w.page.keyboard.press("ArrowDown"); await w.page.keyboard.press("Enter");
    t = await w.state();
    assert.equal(t.bpm, a.bpm, "back at the shown text restores the exact tempo"); assert.equal(t.dirty, false);
    await bpmField.click(); await w.page.keyboard.press("Meta+a"); await w.page.keyboard.type("1");
    await w.page.keyboard.press("Meta+s");
    assert.equal((await w.state()).ready, true); assert.equal(fs.existsSync(out), false, "Save by key with a refused tempo");
    await bpmField.click(); await w.page.keyboard.press("Meta+a"); await w.page.keyboard.type("1e2");
    await w.page.locator("#save").click();
    assert.equal((await w.state()).bpm, a.bpm); assert.equal(fs.existsSync(out), false, "Save by button with a refused tempo");
    await leave(w.page.locator("#save").click());
    assert.equal(await w.exitCode(), 0);
    const bpmLine = (f) => fs.readFileSync(f, "utf8").split("\n").find((l) => l.includes('"bpm"'));
    assert.equal(bpmLine(out), bpmLine(amenManifest), "the saved tempo is the text read");
  },
  "19 dragging a slice's handle reorders playback; cuts are locked until Source order": async () => {
    const out = path.join(scratch, "ordered.rcy.json"), a = read(amenManifest);
    const w = await open(amenManifest, out);
    const errors = []; w.page.on("pageerror", (e) => errors.push(String(e)));
    let s = await w.state();
    assert.deepEqual(s.order, a.slices.map((_, i) => i + 1)); assert.deepEqual(s.shown, a.boundaries);
    const stripY = s.plot.y - 12, mid = (k) => (xOf(s, s.shown[k - 1]) + xOf(s, s.shown[k])) / 2;
    // slice 2's handle, dropped just right of slice 3's middle: 1 3 2 4 ...
    await w.page.mouse.move(mid(2), stripY); await w.page.mouse.down();
    await w.page.mouse.move(mid(3) + 4, stripY, { steps: 6 }); await w.page.mouse.up();
    s = await w.state();
    const want = a.slices.map((_, i) => i + 1); want[1] = 3; want[2] = 2;
    assert.deepEqual(s.order, want); assert.deepEqual(s.boundaries, a.boundaries, "the manifest's boundaries stay in source order");
    assert.equal(s.shown[2] - s.shown[1], a.boundaries[3] - a.boundaries[2], "slot 2 shows slice 3");
    assert.equal(s.dirty, true);
    // a cut can't be added while reordered
    await w.page.mouse.dblclick(xOf(s, s.shown[4] + 9000), midY(s));
    assert.equal((await w.state()).boundaries.length, a.boundaries.length);
    // a second drag straight after, made while Space loops: slice 1 to after slot 2; the loop goes on
    await w.page.keyboard.press("Space"); assert.equal((await w.state()).playing, true);
    s = await w.state();
    await w.page.mouse.move(mid(1), stripY); await w.page.mouse.down();
    await w.page.mouse.move(mid(2) + 4, stripY, { steps: 6 }); await w.page.mouse.up();
    const first = want.slice(); want[0] = 3; want[1] = 1;
    s = await w.state();
    assert.deepEqual(s.order, want); assert.equal(s.playing, true, "the loop plays on in the new order");
    if (process.env.RCY_SHOT) await w.page.screenshot({ path: process.env.RCY_SHOT });
    await w.page.keyboard.press("Space"); assert.equal((await w.state()).playing, false);
    // each reorder is one undo step (after the pointer work: Electron's menu takes the shortcut's key release)
    await w.page.keyboard.press("Meta+z"); assert.deepEqual((await w.state()).order, first);
    await w.page.keyboard.press("Meta+Shift+z"); assert.deepEqual((await w.state()).order, want);
    assert.deepEqual(errors, []);
    await leave(w.page.keyboard.press("Meta+s"));
    assert.equal(await w.exitCode(), 0);
    const m = read(out);
    assert.deepEqual(m.order, want); assert.deepEqual(m.boundaries, a.boundaries); assert.deepEqual(meta(m), meta(a));
    assert.deepEqual(read(w.record).final.order, want);
    acceptedByExport(out);
    // reopened, the order is as saved; Source order removes it
    const out2 = path.join(scratch, "ordered2.rcy.json");
    const w2 = await open(out, out2);
    assert.deepEqual((await w2.state()).order, want);
    await w2.page.locator("#source-order").click();
    assert.deepEqual((await w2.state()).order, a.slices.map((_, i) => i + 1));
    await leave(w2.page.keyboard.press("Meta+s"));
    assert.equal(await w2.exitCode(), 0);
    assert.equal("order" in read(out2), false, "source order is written as no order member");
  },
  "20 copy, paste, duplicate and cut build an order with repeats and gaps": async () => {
    const out = path.join(scratch, "repeats.rcy.json"), a = read(amenManifest), n = a.slices.length;
    const w = await open(amenManifest, out);
    const errors = []; w.page.on("pageerror", (e) => errors.push(String(e)));
    let s = await w.state();
    const stripY = s.plot.y - 12, mid = (k) => (xOf(s, s.shown[k - 1]) + xOf(s, s.shown[k])) / 2;
    const ident = a.slices.map((_, i) => i + 1), len = (k) => a.boundaries[k] - a.boundaries[k - 1];
    await w.page.mouse.click(mid(2), stripY);
    assert.equal((await w.state()).slot, 1);
    await w.page.keyboard.press("Meta+d");                      // 1 2 2 3 ...
    s = await w.state();
    assert.deepEqual(s.order, [1, 2, 2].concat(ident.slice(2))); assert.equal(s.slot, 2);
    assert.equal(s.shownFrames, s.frames + len(2)); assert.equal(s.shown.length, n + 2);
    assert.deepEqual(s.boundaries, a.boundaries);
    await w.page.keyboard.press("Meta+c");
    await w.page.mouse.click(mid(1), stripY);
    await w.page.keyboard.press("Meta+v");                      // 1 2 2 2 3 ...
    s = await w.state();
    assert.deepEqual(s.order, [1, 2, 2, 2].concat(ident.slice(2))); assert.equal(s.slot, 1);
    await w.page.keyboard.press("Meta+x");                      // 1 2 2 3 ...
    await w.page.mouse.click(mid(1), stripY);
    await w.page.keyboard.press("Meta+x");                      // 2 2 3 ...: slice 1 plays nowhere
    s = await w.state();
    assert.deepEqual(s.order, [2, 2].concat(ident.slice(2)));
    assert.equal(s.shownFrames, s.frames + len(2) - len(1));
    await w.page.keyboard.press("Space"); assert.equal((await w.state()).playing, true);
    await w.page.keyboard.press("Space");
    await w.page.keyboard.press("Meta+z"); assert.deepEqual((await w.state()).order, [1, 2, 2].concat(ident.slice(2)));
    await w.page.keyboard.press("Meta+Shift+z");
    assert.deepEqual(errors, []);
    await leave(w.page.keyboard.press("Meta+s"));
    assert.equal(await w.exitCode(), 0);
    const m = read(out);
    assert.deepEqual(m.order, [2, 2].concat(ident.slice(2))); assert.deepEqual(m.boundaries, a.boundaries); assert.deepEqual(meta(m), meta(a));
    acceptedByExport(out);
    const w2 = await open(out, path.join(scratch, "repeats2.rcy.json"));
    const s2 = await w2.state();
    assert.deepEqual(s2.order, m.order); assert.equal(s2.shownFrames, s2.frames + len(2) - len(1));
    w2.kill();
  },
};

(async () => {
  let failed = 0;
  for (const [name, run] of Object.entries(scenarios)) {
    if (FILTER && !name.includes(FILTER)) continue;
    const started = Date.now();
    try { await run(); console.log(JSON.stringify({ scenario: name, pass: true, ms: Date.now() - started })); }
    catch (e) { failed++; console.log(JSON.stringify({ scenario: name, pass: false, ms: Date.now() - started, why: String(e.message || e).slice(0, 400) })); }
    spawnSync("pkill", ["-f", ARTIFACT]);
  }
  console.log(JSON.stringify({ failed, scratch }));
  process.exit(failed ? 1 : 0);
})();
