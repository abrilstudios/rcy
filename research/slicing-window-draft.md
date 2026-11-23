# Slicing window: draft specification

Status: draft for the owner to read. Nothing is generated or installed from
it. The file name, its location and the command name `<window>` are
placeholders.

## Purpose

One window with one job: show a source file with the cuts a manifest
proposes, let a person correct those cuts by eye and ear, and write the
manifest back. An agent starts the window with a manifest it has prepared and
reads the result when the window exits. The window has no file browser, no
settings and no export; cutting the kit stays with `rcy-export
--from-manifest`.

## Where each behaviour comes from

| Behaviour | Source |
|---|---|
| Stacked left and right channel plots, one plot for mono | rcy window (`research/rcy-waveform-window.md` section 1) |
| Slice lines with a triangle at the top | rcy window, section 2 |
| L and R locators that bound the region | rcy window, section 3 |
| Click plays the slice under the pointer; Space plays L to R; keys 1 to 0 and Q to P play slices 1 to 20 | rcy window, section 5 |
| Add or remove a cut with a modified click | rcy window, section 3 |
| Drag a slice marker | ReCycle convention; the rcy window had no slice drag |
| Zoom to single samples | owner's request; the rcy window had no reachable zoom, and an earlier layout had Zoom In and Zoom Out buttons |
| Save writes the manifest | owner's request; the rcy window exported a kit instead |
| Started and preset from the command line by an agent | owner's request |
| Zero crossings visible, no snapping | rcy record: snapping to zero crossings was rejected, clicks are handled by the tail fade |
| Playhead line during playback | new; the rcy window drew only a highlight |

## Launch

`<window> --manifest FILE [--out FILE]`

- `FILE` is a manifest as `rcy-export` writes it. Its `source` is resolved
  against the manifest's directory, as in SPEC.md R20.
- `--out` names where Save writes. Without it Save writes `FILE` in place.
- A manifest that `rcy-export --from-manifest` would refuse is refused here
  with the same message and exit code 2, before any window opens.

## Exit

| Outcome | Exit code | Files |
|---|---|---|
| Saved, then closed | 0 | the output manifest is written |
| Closed without saving | 3 | nothing is written or changed |
| Refused at launch | 2 | nothing is written |

Save closes the window. Closing with unsaved edits asks once before
discarding them.

## What the window may change

The window edits `boundaries` and the `slices` list, and nothing else.
`source`, `sample_rate`, `channels`, `bpm` and `measures` are written back
as read.

The locators move `region.start` and `region.end`, which are the first and
last boundary. Moving a locator does not recompute `bpm`: the rcy window did,
and a region that disagrees with `measures` produces a wrong tempo line in
`rcy-export`, so tempo stays the agent's value. (Default, open to change.)

Slice list after an edit:

- Move: only that boundary changes. Every slice keeps its `key`, `file` and
  `role`.
- Add: the slice that contains the new cut is split. The left part keeps the
  slice's `key`, `file` and `role`. The right part gets an empty role, and
  every later slice's key rises by one. Files are renamed by position only
  when every file name in the manifest read was the default `NNN.wav`;
  otherwise the new slice's file name is asked for.
- Remove: the slice to the right of the removed cut is merged into the one on
  its left, which keeps its `key`, `file` and `role`. Later keys fall by one.

Boundaries are integers, strictly increasing, inside the source's frame
count. An edit that would break this is not applied.

## Display

- Each visible pixel column shows the minimum and maximum sample it covers.
  When the view holds fewer frames than pixels, individual samples are drawn
  as points joined by lines, with the zero line visible.
- Zoom is anchored at the pointer. Widest view: the whole file. Narrowest
  view: 32 frames across the plot (parameter; small enough to place a cut on
  one sample).
- Zoom by wheel or pinch, and by keys `+` and `-`. Scroll by horizontal wheel
  or by dragging the scroll bar. `F` fits the whole file, `Z` fits the slice
  under the pointer.
- Each slice shows its number and, when it has one, its role.
- A status line shows the pointer position in frames, the selected marker's
  frame and the sample value at that frame.

## Markers

- Drag a slice marker with the left button. It cannot pass its neighbours.
- With a marker selected, Left and Right move it one frame; with Shift, one
  pixel column at the current zoom.
- Option-click on the waveform adds a cut at that frame. Option-click on a
  marker, or Delete with a marker selected, removes it.
- Undo and redo cover every move, add and remove since launch.
- No snapping of any kind.

Pick distance for a marker: 6 pixels (parameter). The rcy window used fixed
distances in seconds of audio, which stop working once zoom exists.

## Audition

- Click inside a slice plays it from its start to its end. Click while audio
  plays stops it.
- Space plays from L to R and loops until stopped.
- Keys 1 to 9, 0 and Q to P play slices 1 to 20. A key press while audio
  plays replaces the sound: one voice, hard cut.
- Shift-click plays from the clicked frame to the end of that slice, for
  checking a cut point.
- Playback is the slice as cut, at the source's own rate, with the 3 ms tail
  fade the pattern renderer uses (default: rcy's `tailFade.durationMs`).
- A playhead line follows playback.

## Shell and driver

The window is an Electron application. Scenarios drive it with Playwright's
Electron support: real pointer drags, clicks and key presses against the
running window, with the written manifest read back from disk. The window has
no scripting interface of its own.

## Floor scenarios

Each starts from the seven-hit amen manifest.

1. Open and save with no edit. The written manifest equals the one read,
   byte for byte.
2. Move the second boundary by 100 frames and save. The written manifest
   differs from the one read in that boundary and in the `start` and `end`
   values of the two slices that share it.
3. Add a cut inside slice 3 and save. There are eight slices; slices 1 to 3
   keep their keys, and the keys after the new slice are one higher.
4. Remove the cut between slices 3 and 4 and save. There are six slices and
   the merged slice has slice 3's key, file and role.
5. Close without saving. The exit code is 3 and the manifest file's bytes and
   modification time are unchanged.
6. Launch with a manifest whose boundaries decrease. The exit code is 2, the
   message is the one `rcy-export` prints, and no window opens.
7. After scenarios 2, 3 and 4, `rcy-export --from-manifest` accepts the
   written manifest and its slice WAVs have the lengths the boundaries give.
8. Press key 2. The audio handed to the output starts with the source frames
   at slice 2's start.

## Measured goals

These are scored above the floor and reported per generated candidate.

- Frame time while zooming and scrolling the 7 s amen file.
- Time from key press to the first non-zero output frame.
- Time from launch to a drawn waveform.

## Open items

- How scenario 8 observes audio: an output device stand-in, or a render of
  the audition to a file.
- Whether the window also proposes cuts (split by measures, split by
  transients, as the rcy window did) or leaves all proposing to the agent.
  This draft leaves it to the agent.
