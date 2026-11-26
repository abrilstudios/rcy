// Takes the README's screenshots of rcy-window from the real program.
//
// Usage: node docs/screenshots/capture.js ELECTRON
// Requires playwright-core on NODE_PATH (tools/window-runtime/node_modules).
// Each window is launched with the same options a workflow script passes.
"use strict";
const { _electron } = require("playwright-core");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const ELECTRON = process.argv[2];
if (!ELECTRON) { console.error("usage: capture.js ELECTRON"); process.exit(2); }

const ROOT = path.resolve(__dirname, "..", "..");
const OUT = __dirname;
const READY_TIMEOUT_MS = 15000;  // parameter: launch to drawn waveform
const MAX_ZOOM_STEPS = 12;      // parameter: most presses of "=" for the close-up
const CUTS_IN_CLOSE_UP = 2;      // parameter: zoom in until at most this many cuts are in view
const DRAG_PIXELS = 30;          // parameter: pointer travel in the close-up
const PICK_COUNT = 5;            // parameter: pads asked for in the exact-count shots
const LAUNCH_BPM = "165";        // parameter: tempo stated at launch in the tempo shots
const REFUSED_BPM = "1";         // parameter: a tempo a MIDI file can't hold, typed to show the refusal
const VIEW_SLICES = 3;           // parameter: slices in view in the --view and --select shot
const SELECTED = 9;              // parameter: the slice --select names in that shot
const ARRANGE_RESOLUTION = 4;    // parameter: slices per measure in the arranging shots, wide enough to read their numbers
const MOVED_SLICE = 6;           // parameter: the slice dragged to the front in the arranging shots
const REPEATED_SLOT = 3;         // parameter: the slot duplicated in the arranging shots
const LOOP_SLOTS = 8;            // parameter: slots left in the loop after R is brought in

const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "rcy-shots-"));
const r = spawnSync("node", [path.join(ROOT, "export", "rcy-export"), "--input", path.join(ROOT, "presets", "amen.wav"),
  "--measures", "4", "--resolution", "1", "--out", path.join(scratch, "amen")], { encoding: "utf8" });
if (r.status !== 0) { console.error(r.stderr); process.exit(1); }
const manifest = path.join(scratch, "amen", "amen.rcy.json");

async function open(name, options) {
  const args = [path.join(ROOT, "window", "rcy-window"), "--manifest", manifest,
    "--out", path.join(scratch, name + ".rcy.json"), "--record", path.join(scratch, name + ".run.json")].concat(options);
  const app = await _electron.launch({ executablePath: ELECTRON, args });
  const page = await app.firstWindow();
  await page.waitForFunction(() => typeof rcyWindowState === "function" && rcyWindowState().ready, null, { timeout: READY_TIMEOUT_MS });
  const state = () => page.evaluate(() => rcyWindowState());
  const shot = (file) => page.screenshot({ path: path.join(OUT, file), scale: "css" });
  const close = () => { try { app.process().kill("SIGKILL"); } catch (e) {} };
  return { page, state, shot, close };
}
const xOf = (s, frame) => s.plot.x + (frame - s.viewStart) / (s.viewEnd - s.viewStart) * s.plot.width;
const midY = (s) => s.plot.y + s.plot.height / 2;

(async () => {
  // workflows/new-kit: the break arrives already split into eighth notes.
  let w = await open("new-kit", ["--split", "measures", "--resolution", "8",
    "--task", "Move each cut onto the start of its hit. Delete cuts you don't want, then Save."]);
  await w.shot("new-kit-opening.png");

  // The same task, zoomed in on one cut while it is being dragged.
  let s = await w.state();
  await w.page.mouse.click(xOf(s, (s.boundaries[4] + s.boundaries[5]) / 2), midY(s));
  const inView = (t) => t.boundaries.filter((b) => b > t.viewStart && b < t.viewEnd);
  for (let i = 0; i < MAX_ZOOM_STEPS && inView(s).length > CUTS_IN_CLOSE_UP; i++) {
    await w.page.keyboard.press("=");
    const next = await w.state();
    if (inView(next).length === 0) { await w.page.keyboard.press("-"); break; }
    s = next;
  }
  s = await w.state();
  const cut = inView(s)[0];
  if (cut === undefined) throw new Error("no cut in view after zooming");
  const x = xOf(s, cut);
  await w.page.mouse.move(x, midY(s)); await w.page.mouse.down();
  await w.page.mouse.move(x - DRAG_PIXELS / 2, midY(s)); await w.page.mouse.move(x - DRAG_PIXELS, midY(s));
  await w.shot("moving-a-cut.png");
  await w.page.mouse.up();
  w.close();

  // workflows/pick-hits: Save is unavailable until the slice count matches.
  w = await open("pick-hits", ["--split", "transients", "--sensitivity", "50", "--expect-slices", String(PICK_COUNT),
    "--task", `Cut this break into exactly ${PICK_COUNT} slices, one per pad. Put each cut at the start of a hit.`]);
  s = await w.state();
  if (s.slices.length === PICK_COUNT) throw new Error("the opening split already has the expected count");
  await w.shot("pick-hits-count-unmet.png");
  while (s.slices.length > PICK_COUNT) {
    await w.page.mouse.dblclick(xOf(s, s.boundaries[1]), midY(s));
    s = await w.state();
  }
  if (s.slices.length !== PICK_COUNT) throw new Error("could not reach the expected count");
  await w.page.mouse.move(xOf(s, s.frames / 2), s.plot.y + 4);
  await w.shot("pick-hits-count-met.png");
  w.close();

  // A launch that states the tempo, then a tempo the control refuses.
  w = await open("tempo", ["--split", "measures", "--resolution", "4", "--bpm", LAUNCH_BPM,
    "--task", "Check the tempo against the break, correct it if it is wrong, then Save."]);
  await w.shot("tempo-control.png");
  await w.page.click("#bpm");
  await w.page.keyboard.press("Meta+a");
  await w.page.keyboard.type(REFUSED_BPM);
  await w.page.keyboard.press("Enter");
  if ((await w.state()).bpm !== Number(LAUNCH_BPM)) throw new Error("the refused tempo was applied");
  await w.shot("tempo-refused.png");
  w.close();

  // A launch that points the person at one slice: --view and --select.
  const perSlice = Math.floor(s.frames / 32);
  const from = (SELECTED - 2) * perSlice, to = from + VIEW_SLICES * perSlice;
  w = await open("one-cut", ["--split", "measures", "--resolution", "8",
    "--view", from + ":" + to, "--select", String(SELECTED),
    "--task", "The selected slice starts late. Move its left cut onto the hit, then Save."]);
  await w.shot("one-cut-in-view.png");
  w.close();

  // Arranging in place: a slice dragged to the front, one repeated, then R brought in to set the loop.
  w = await open("arrange", ["--split", "measures", "--resolution", String(ARRANGE_RESOLUTION),
    "--task", "Arrange the slices into the loop you want, put L and R around it, then Save."]);
  s = await w.state();
  const stripY = s.plot.y - 12;
  const slotMid = (t, k) => (xOf(t, t.shown[k - 1]) + xOf(t, t.shown[k])) / 2;
  await w.page.mouse.move(slotMid(s, MOVED_SLICE), stripY); await w.page.mouse.down();
  await w.page.mouse.move(xOf(s, s.shown[0]) + 14, stripY, { steps: 6 }); await w.page.mouse.up();
  s = await w.state();
  await w.page.mouse.click(slotMid(s, REPEATED_SLOT), stripY);
  await w.page.keyboard.press("Meta+d");
  s = await w.state();
  if (s.order[0] !== MOVED_SLICE || s.order[REPEATED_SLOT] !== s.order[REPEATED_SLOT - 1]) throw new Error("the order is not the one the shot shows: " + s.order);
  await w.shot("arranged-in-place.png");
  const xR = xOf(s, s.shown[s.shown.length - 1]) - 5;
  await w.page.mouse.move(xR, stripY); await w.page.mouse.down();
  await w.page.mouse.move(xOf(s, s.shown[LOOP_SLOTS]) + 3, stripY, { steps: 8 }); await w.page.mouse.up();
  s = await w.state();
  if (s.loop[0] !== 1 || s.loop[1] !== LOOP_SLOTS) throw new Error("the loop is " + s.loop);
  await w.page.mouse.move(xOf(s, s.shownFrames / 2), midY(s));
  await w.shot("loop-markers.png");
  w.close();
  console.log("wrote 9 screenshots to " + OUT);
})().catch((e) => { console.error(e); process.exit(1); });
