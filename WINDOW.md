# rcy-window

A slicing window. It shows a source WAV file with the cuts a kit manifest
holds, lets a person correct the cuts by eye and ear, and writes the manifest
back. A program or agent starts it with a manifest and reads the result when
it exits. It cuts no audio files; `rcy-export --from-manifest` does that from
the manifest this window saves.

The window is one file, `rcy-window`: the SDK followed by the program, as
`rcy-sdk/dist/bundle.cjs` writes it. Electron runs that file as its main
script; the page and everything it needs are inside it. Where the SDK offers
a function for something this document asks for, the program calls it.

This document is written against rcy-sdk 0.1.0, the file
`rcy-sdk/dist/rcy-sdk.js` with SHA-256
`fd976bc2b709c41e1db25f4b9aeccc5dec99f24c90755561e19769a92403d6a9`,
described by `rcy-sdk/README.md` with SHA-256
`47f210129fa0c1eaa95fffd3ac8d6f336d6d1819e3c2149edc1a18efd6f82da3`.

## Terms

- **Frame**: one sample instant across all channels. Positions are integer
  frame numbers; `N` is the source's frame count.
- **Boundaries**: the strictly increasing list of frame positions in the
  manifest. The first and last are the **locators**, drawn as L and R; the
  others are **cuts**. Slice `k` (1-based) covers `boundary[k-1]` up to but
  not including `boundary[k]`.
- **The plot**: the rectangle in which horizontal position maps linearly to
  frames. Its left edge is frame `viewStart` and its right edge is frame
  `viewEnd`.

## Constants

| Name | Value | Class | Reason |
|---|---|---|---|
| `FIRST_KEY` | 60 | default | MIDI key of the first slice after a split, as in `rcy-export`. |
| `LAST_KEY` | 127 | invariant | The highest MIDI key; no edit may produce a higher one. |
| `MIN_VIEW_FRAMES` | 32 frames | parameter | Narrowest view; wide enough to see a zero crossing, narrow enough to place a cut on one frame. |
| `ZOOM_STEP` | 0.5 | parameter | One zoom-in key press halves the visible span; zoom-out doubles it. |
| `PICK_PIXELS` | 6 px | parameter | A press within this distance of a boundary's line acts on that boundary. |
| `TAIL_FADE_MS` | 3 ms | default | Audition ends each slice with a fade to zero of this length, the value rcy uses. |
| `TAIL_FADE_POWER` | 3 | default | The fade gain is `t^3` for `t` falling from 1 to 0, rcy's "exponential" curve. |
| `DEFAULT_RESOLUTION` | 4 slices per measure | default | Initial value of the resolution control. |
| `DEFAULT_SENSITIVITY` | 50 | default | Initial value of the sensitivity control, range 0 to 99. |
| `AUDITION_KEYS` | `1234567890qwertyuiop` | default | Key `i` (0-based) in this string plays slice `i + 1`. |

## Launch

```
electron rcy-window --manifest FILE --record FILE [--out FILE]
                     [--split {measures,transients}] [--resolution R] [--sensitivity S]
                     [--view START:END] [--select I] [--task TEXT] [--expect-slices K]
```

The command line is the whole statement of a run: the state the window
opens in and the state its result must be in when it is saved. The window
asks the person for nothing the command line could have said.

**W01.** The program's arguments are those that follow its own path in
`process.argv`. Electron's own switches before that path are ignored.

**W02.** `--manifest FILE` and `--record FILE` are required. `--out FILE` names the file Save
writes; without it Save writes `FILE`.

**W03.** Before any window is created the program checks, in this order, and
on the first failure writes one line to stderr, exits with code 2 and creates
or changes no file:

1. the arguments are well formed (W02, no unknown option);
2. `FILE` exists and is valid JSON holding an object;
3. its `rcy` member equals `rcySdk.MANIFEST_VERSION`;
4. `boundaries` is an array of at least two integers, strictly increasing,
   the first at least 0;
5. `slices` is an array with one object per pair of neighbouring boundaries,
   each with an integer `key` from 0 to `LAST_KEY`, a string `file`, and a
   `role` that is a string or absent (absent reads as the empty string);
6. `source`, resolved against the manifest's directory when relative, is a
   file `rcySdk.parseWav` accepts with 16 bits per sample;
7. the last boundary is at most `N`;
8. `bpm` is a finite number above 0 and `measures` is an integer of at least
   1; `sample_rate` and `channels`, when present, equal the source's.

Paths are made absolute lexically; symbolic links are not resolved, here or
in W04.

The wording of the line is not specified. `sample_rate`, `channels`, `bpm`
and `measures` are read and kept as they are; `sample_rate` and `channels`
are replaced by the source's own values on save only if they were absent.

## Declared opening state and end condition

**W20.** After the source is loaded and before `ready` becomes true, in this
order: `--resolution` and `--sensitivity` set their controls; `--split` runs
W11 or W12 once, as an undoable edit, so the window opens with unsaved edits;
`--view` sets `viewStart` and `viewEnd` in frames; `--select` selects that
boundary index if it exists; `--task` is shown in an element with id `task`
above the plot. `--resolution` is one of the control's values, `--sensitivity`
a whole number from 0 to 99, `--view` two whole numbers with the first below
the second and the second at most `N`. A value outside these is a W03
refusal.

**W21.** With `--expect-slices K`, Save is refused while the slice count is
not `K`: the `save` button is disabled, the shortcut writes nothing and the
status line says why. The `task` element shows the count asked for and the
current count. Exit code 0 therefore means the declared end condition held.

**W22. Run record.** `--record FILE` is required. On every exit after
launch, whether saved or closed, the program writes `FILE` as JSON:
`rcy_window_run` (1), `arguments`, `started_at`, `ended_at`, `duration_ms`,
`exit_code`, `outcome`, `manifest`, `manifest_read` (boundaries, slices, bpm,
measures as read), `opening` (boundaries, slices, view, selection and control
values once W20 is applied), `events` and `final` (boundaries, slices, and
whether edits were unsaved). `events` lists, in order with `t_ms` since the
page started, every edit (`kind` "edit", a description, the boundaries after
it), undo, redo and audition (`kind` "play", `from`, `to`) the person made.
If the record can't be written the program writes a line to stderr and exits
with code 1. A W03 refusal writes no record.

**W23.** A manifest's `buffer_ms` member, when present, is written unchanged
to the saved manifest. The window never shows or edits it; the buffer
belongs to the export (SPEC.md R25).

## Exit

| Outcome | Exit code | Files |
|---|---|---|
| Saved | 0 | the output file is written, then the program exits |
| Closed without saving | 3 | only the run record is written |
| Refused at launch (W03) | 2 | nothing is written or changed |

**W04. Save** is Cmd+S (Ctrl+S elsewhere). It writes the output file as the
UTF-8 text `rcySdk.manifestText` returns for: `source`, the source's path
relative to the output file's directory with `/` separators; `sampleRate`,
`channels`, `bpm` and `measures` as read; and the current `boundaries` and
`slices`. The program then exits with code 0. If the file can't be written,
the status line says why, nothing exits and the edits stay unsaved. A save with no edit, writing in
place, leaves a manifest written by `rcy-export` byte for byte the same.

**W05. Close** is Cmd+W (Ctrl+W elsewhere) or the window's close button. With
no unsaved edit the program exits with code 3. With unsaved edits it shows,
inside the page, an element with id `discard-confirm` holding buttons with
ids `discard-yes` and `discard-no`; `discard-yes` exits with code 3 and
`discard-no` returns to editing. No native dialog is used anywhere.

## What the window changes

**W06.** The window changes `boundaries` and `slices` and nothing else.
Moving a locator does not change `bpm` or `measures`.

**W07. Default names.** The file names are *default* when slice `k`'s file is
`k` as three decimal digits followed by `.wav`, for every slice.

**W08. Move a cut.** Moving a cut changes that boundary only. A cut stays at
least one frame from each neighbour. Every slice keeps its `key`, `file` and
`role`.

**W08a. Move a locator.** A locator moves freely between 0 and `N`, except
that L stays at least one frame below R. It is not stopped by cuts: every cut
at or beyond the locator's new position (at or below L, at or above R) is
removed as W10 describes. During a drag the result is computed from the
boundaries and slices as they were at the press, so dragging back over a cut
within the same drag restores it. The whole drag is one undo step.

**W09. Add.** Adding a cut at frame `f` strictly between two neighbouring
boundaries splits that slice. The left part keeps the slice's `key`, `file`
and `role`; the right part has the next key and the empty role; every later
slice's key rises by one. If the names were default before the edit, all
files are renamed by position (W07); otherwise the new slice's file is the
first name `NNN.wav`, counting `NNN` up from the new slice count, that no
slice uses. An add that would give any slice a key above `LAST_KEY`, or at a
frame that already is a boundary or lies outside the locators, is not
applied.

**W10. Remove.** Removing a cut merges the slice on its right into the slice
on its left, which keeps its `key`, `file` and `role`. Every later slice's
key falls by one. If the names were default before the edit, all files are
renamed by position. Locators can't be removed.

**W11. Split by Measures** replaces every cut. With `L` and `R` the locators,
`m` the manifest's `measures` and `r` the resolution control's value,
`n = m * r` and

```
boundary[i] = L + floor(i * (R - L) / n)        for i = 0 .. n
```

in exact integer arithmetic. Slice `k` gets key `FIRST_KEY + k - 1`, the
default file name and the empty role. If `m` is not a positive integer, `n`
exceeds `R - L`, or a key would exceed `LAST_KEY`, nothing changes and the
status line says why.

**W12. Split by Transients** replaces every cut with one cut at each
detected hit onset strictly between the locators, and names the slices as W11
does. The detection method is the program's own. It must satisfy:

- a cut is placed at or just before the first frame of a hit's attack, never
  after its peak;
- for material made of hits separated by digital silence, at
  `DEFAULT_SENSITIVITY` there is exactly one cut per hit, excluding a hit that
  starts at the L locator;
- raising the sensitivity control never reduces the number of cuts for the
  same audio and locators;
- if the cuts found would put a key above `LAST_KEY`, the quietest onsets are
  dropped until they fit.

On a recorded drum break, sensitivity 99 gives more cuts than sensitivity 0.

Changing the sensitivity control after a Split by Transients, with no other
edit in between, runs the split again before the control's event handler
returns; the new result replaces the previous split as one undo step.

**W13. Undo** is Cmd+Z and **redo** Shift+Cmd+Z (Ctrl elsewhere). Each move,
add, remove and split is one step; a drag from press to release is one move. Undoing every step leaves the boundaries
and slices as read, and the window then has no unsaved edit.

## Display

**W14.** One plot per channel, stacked, sharing the horizontal axis; one plot
for a mono source. The reference is ReCycle's main window: a waveform across
the full width, a vertical line with a small triangle at its top for each
cut, and the two locators marked L and R.

**W15.** Each pixel column draws the minimum and maximum sample it covers.
When the view holds fewer frames than the plot has pixels, the samples are
drawn as points joined by lines and each channel's zero line is drawn, so
zero crossings can be read. Drawing is sharp on high-density displays.

**W16.** Each slice shows its number and, when it has one, its role. A status
line shows the frame under the pointer, the selected boundary's frame, and
each channel's sample value at that frame. A line follows playback.

**W17.** On launch the view is the whole file: `viewStart` 0, `viewEnd` `N`.

## Pointer and keys

A horizontal position `x` in the plot is frame
`viewStart + (x - plot.x) / plot.width * (viewEnd - viewStart)`; a boundary
moved or added by the pointer takes that value rounded to the nearest
integer, then limited by W08 or W09.

| Input | Effect |
|---|---|
| Press within `PICK_PIXELS` of a boundary's line, anywhere in the plot's height, and drag | Moves that boundary (W08, W08a); it follows the pointer. The boundary becomes the selected one. Where a locator and a cut are both within reach, the nearer line wins. |
| Press and release on a boundary without moving | Selects it. |
| Left or Right with a boundary selected | Moves it one frame. With Shift, the number of frames one pixel covers, at least one. |
| Double-click, or Option-click (Alt-click), in the plot, not on a boundary | Adds a cut at that frame (W09) and selects it. Audio the first click of a double-click started is stopped. |
| Double-click or Option-click on a cut, or Delete or Backspace with a cut selected | Removes it (W10). |
| Click in the plot, not on a boundary, no modifier | Sets the cursor to that frame. If audio is playing, stops it. Otherwise plays the slice under the pointer from its start. |
| Shift-click in the plot | Plays from the clicked frame to the end of that slice. |
| Space | If audio is playing, stops it. Otherwise plays from L to R, looping until stopped. |
| A key in `AUDITION_KEYS` | Plays that slice from its start. A press while audio plays replaces the sound. |
| `=` | Zooms in by `ZOOM_STEP`, keeping the frame under the pointer at the same pixel when the pointer is over the plot, otherwise the frame at the plot's centre. The new span is `max(span * ZOOM_STEP, MIN_VIEW_FRAMES)`. |
| `-` | Zooms out the same way. The view never extends outside 0 to `N`. |
| Wheel or pinch over the plot | Vertical wheel zooms about the pointer; horizontal wheel scrolls. |
| `f` | Shows the whole file. |
| `z` | Fits the view to the slice under the pointer. |

`viewStart` and `viewEnd` may be fractional. No boundary ever snaps to
anything.

Every key in this document, including Save, Close, Undo and Redo, acts when
its `keydown` event reaches the page, whichever element has focus, except
that Left and Right belong to the sensitivity control while it has focus. An
application menu item with the same shortcut, if there is one, does the same
thing. Closing through the window's own close event follows W05 too.

A row that names a plain key applies only when Cmd, Ctrl and Alt are up. A
key this document gives a meaning never also activates a focused button or
changes a focused `select`: Space after a click on a split button plays, and
does not split again.

## Controls

These are HTML elements with these ids, visible in the window:

| id | Element | Behaviour |
|---|---|---|
| `split-measures` | button | W11 |
| `split-transients` | button | W12 |
| `resolution` | `select` | Option values `1`, `2`, `4`, `8`, `16`, `32` (slices per measure); initial `DEFAULT_RESOLUTION` |
| `sensitivity` | `input type="range"` | `min` 0, `max` 99, step 1; initial `DEFAULT_SENSITIVITY` |
| `status` | any | The status line (W16) |
| `add-cut` | button | Adds a cut at the cursor (W09) and selects it. Disabled while there is no cursor or a cut can't be added there. |
| `delete-cut` | button | Removes the selected cut (W10). Disabled unless a cut is selected. |
| `save` | button | Save (W04). Its label includes the shortcut. |
| `close` | button | Close (W05), labelled so that it is clear nothing is saved. Its label includes the shortcut. |
| `hint` | any | One line, always visible, naming how to audition, move, add and remove a cut, zoom and save. |

The cursor is the frame of the most recent click in the plot that was not on
a boundary; there is none at launch. It is drawn as a thin line distinct from
cuts and from the playback line. `save` and `close` sit together at the top
right, and the window shows plainly when there are unsaved edits.

Everything a person needs in order to cut, correct and save a break is
reachable with the mouse alone from what is visible on screen; shortcuts are
an addition.

## Audition

**W18.** Audio plays through the Web Audio API at the source's own rate, one
voice, with a hard cut when a new sound replaces the current one. A slice
plays exactly its frames, ending with the tail fade (`TAIL_FADE_MS`,
`TAIL_FADE_POWER`). No time-stretch and no fade-in.

## State for a driver

**W19.** The page defines a global function `rcyWindowState()` that returns,
at any time after load:

```
{
  ready: boolean,            // true once the source is decoded and the first draw is done
  frames: number,            // N
  boundaries: number[],
  slices: { key, file, role }[],
  viewStart: number,
  viewEnd: number,
  plot: { x, y, width, height },   // CSS pixels in the viewport; the top channel's plot
  selected: number | null,   // index into boundaries
  cursor: number | null,     // frame
  playing: boolean,
  dirty: boolean,            // an unsaved edit exists
}
```

What it returns reflects an edit as soon as the event handler that made the
edit returns. The function only reports. The page offers no function that edits, saves or
closes; those happen through the pointer, the keys and the controls above.

## Page and main process

The page is created with `nodeIntegration: true` and `contextIsolation:
false` and talks to the main process through `ipcRenderer`; there is no
preload file. The main process reads the manifest and the source and hands
the page the samples; it writes no temporary file. The rule in W19 concerns
global functions a driver could call, not this channel.

## Out of scope

Opening another file, changing the source, export of audio or kit files,
tempo and measure editing, effects, settings, and any network access.
