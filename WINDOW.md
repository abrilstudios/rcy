# rcy-window

A slicing window. It shows a source WAV file with the cuts a kit manifest
holds, lets a person correct the cuts by eye and ear and set the tempo, and writes the manifest
back. A program or agent starts it with a manifest and reads the result when
it exits. It cuts no audio files; `rcy-export --from-manifest` does that from
the manifest this window saves.

The window is one file, `rcy-window`: the SDK followed by the program, as
`rcy-sdk/dist/bundle.cjs` writes it. Electron runs that file as its main
script; the page and everything it needs are inside it. Where the SDK offers
a function for something this document asks for, the program calls it.

This document is written against rcy-sdk 0.1.0, the file
`rcy-sdk/dist/rcy-sdk.js` with SHA-256
`09bd1d3fb303b8d6e1028956cab71af3b933e99867a673830d058250501d81cd`,
described by `rcy-sdk/README.md` with SHA-256
`a8e6ef80d5863c90719cd1b16dbecaa2a38c610232e3dcf2f11c3b917ac05dd5`.

## Terms

- **Frame**: one sample instant across all channels. Positions are integer
  frame numbers; `N` is the source's frame count.
- **Boundaries**: the strictly increasing list of frame positions in the
  manifest. The first and last are the ends of the **sliced
  region**; the others are **cuts**. Slice `k` (1-based) covers `boundary[k-1]` up to but
  not including `boundary[k]`.
- **Locators**: the two loop markers, drawn as L and R. Each stands on a
  slice edge and they mark what plays as a loop and what Save keeps (W26).
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
| `PICK_PIXELS` | 6 px | parameter | A press within this distance of a boundary's line acts on that boundary; a press on the strip becomes a reorder drag (W25) after more than this travel. |
| `FLAG_PIXELS` | 12 px | parameter | Width of the L and R flags in the strip above the plots. Each flag reaches this far into the loop from its locator's line, or half the width of the slot it stands in when that is less, and a press on a flag moves that locator (W26). |
| `TAIL_FADE_MS` | 3 ms | default | Audition ends each slice with a fade to zero of this length, the value rcy uses. |
| `TAIL_FADE_POWER` | 3 | default | The fade gain is `t^3` for `t` falling from 1 to 0, rcy's "exponential" curve. |
| `DEFAULT_RESOLUTION` | 4 slices per measure | default | Initial value of the resolution control. |
| `DEFAULT_SENSITIVITY` | 50 | default | Initial value of the sensitivity control, range 0 to 99. |
| `AUDITION_KEYS` | `1234567890qwertyuiop` | default | Key `i` (0-based) in this string plays slice `i + 1`. |
| `ORDER_MAX_SLOTS` | 256 slots | parameter | Longest order paste and duplicate build (W25); it bounds the audio the window lays out. A manifest's own longer order is read as it is. |
| `TEMPO_DECIMALS` | 2 decimal places | default | The tempo control shows the tempo rounded to this many places. Display only: the stored tempo is not rounded. Two places is what `rcy-export` prints (SPEC.md R18); the two need not match. |

## Launch

```
electron rcy-window --manifest FILE --record FILE [--out FILE]
                     [--split {measures,transients}] [--resolution R] [--sensitivity S]
                     [--bpm B]
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
   `order`, when present, is a non-empty array of integers from 1 to the
   slice count (W25);
6. `source`, resolved against the manifest's directory when relative, is a
   file `rcySdk.parseWav` accepts with 16 bits per sample;
7. the last boundary is at most `N`;
8. `bpm` is a finite number above 0 and `measures` is an integer of at least
   1; `sample_rate` and `channels`, when present, equal the source's.

Paths are made absolute lexically; symbolic links are not resolved, here or
in W04.

The wording of the line is not specified. `sample_rate`, `channels` and
`measures` are read and kept as they are, and `bpm` is kept unless W24
changes it; `sample_rate` and `channels`
are replaced by the source's own values on save only if they were absent.

## Declared opening state and end condition

**W20.** After the source is loaded and before `ready` becomes true, in this
order: `--resolution` and `--sensitivity` set their controls; `--bpm` sets
the tempo (W24) as an undoable edit when it differs from the manifest's;
`--split` runs W11 or W12 once, as an undoable edit (after either of these
edits the window opens with unsaved edits);
`--view` sets `viewStart` and `viewEnd` in frames; `--select` selects that
boundary index if it exists; `--task` is shown in an element with id `task`
above the plot. `--resolution` is one of the control's values, `--sensitivity`
a whole number from 0 to 99, `--view` two whole numbers with the first below
the second and the second at most `N`, `--bpm` a decimal number (digits,
optionally a point and more digits) that either equals the manifest's `bpm`
or makes `rcySdk.tempoWritable` true. A value outside these is a W03 refusal.

**W21.** With `--expect-slices K`, Save is refused while the slice count is
not `K`: the `save` button is disabled, the shortcut writes nothing and the
status line says why. The `task` element shows the count asked for and the
current count. Exit code 0 therefore means the declared end condition held.

**W22. Run record.** `--record FILE` is required. On every exit after
launch, whether saved or closed, the program writes `FILE` as JSON:
`rcy_window_run` (1), `arguments`, `started_at`, `ended_at`, `duration_ms`,
`exit_code`, `outcome`, `manifest`, `manifest_read` (boundaries, slices, bpm,
measures as read), `opening` (boundaries, slices, bpm, view, selection and
control values once W20 is applied), `events` and `final` (boundaries, slices,
bpm, and whether edits were unsaved). `events` lists, in order with `t_ms`
since the page started, every edit (`kind` "edit", a description, the
boundaries and `bpm` after it), undo, redo (each with the boundaries and `bpm`
after it) and audition (`kind` "play", `from`, `to`) the person made.
`opening`, `final` and each reorder, undo and redo event also hold `order`
(W25); boundaries in the record are the manifest's, in source order, and a
"play" event's `from` and `to` are frames of the audio as shown.
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
`channels` and `measures` as read; and the current `bpm`, with the `boundaries`,
`slices` and `order` the loop keeps (W26). The program then exits with code 0. If the file can't be written,
the status line says why, nothing exits and the edits stay unsaved. A save with no edit, writing in
place, leaves a manifest written by `rcy-export` byte for byte the same.

**W05. Close** is Cmd+W (Ctrl+W elsewhere) or the window's close button. With
no unsaved edit the program exits with code 3. With unsaved edits it shows,
inside the page, an element with id `discard-confirm` holding buttons with
ids `discard-yes` and `discard-no`; `discard-yes` exits with code 3 and
`discard-no` returns to editing. No native dialog is used anywhere.

## What the window changes

**W06.** The window changes `boundaries`, `slices`, `bpm` and `order` and
nothing else. Only W24 changes `bpm`. Moving a locator changes none of them while the
window is open; at Save the locators decide which slices are written (W26).

**W07. Default names.** The file names are *default* when slice `k`'s file is
`k` as three decimal digits followed by `.wav`, for every slice.

**W08. Move a cut.** Moving a cut changes that boundary only. A cut stays at
least one frame from each neighbour. Every slice keeps its `key`, `file` and
`role`.

**W08a. The ends of the sliced region stay.** The first and last boundary
are not moved or removed by any edit.

**W09. Add.** Adding a cut at frame `f` strictly between two neighbouring
boundaries splits that slice. The left part keeps the slice's `key`, `file`
and `role`; the right part has the next key and the empty role; every later
slice's key rises by one. If the names were default before the edit, all
files are renamed by position (W07); otherwise the new slice's file is the
first name `NNN.wav`, counting `NNN` up from the new slice count, that no
slice uses. An add that would give any slice a key above `LAST_KEY`, or at a
frame that already is a boundary or lies outside the sliced region, is not
applied.

**W10. Remove.** Removing a cut merges the slice on its right into the slice
on its left, which keeps its `key`, `file` and `role`. Every later slice's
key falls by one. If the names were default before the edit, all files are
renamed by position.

**W11. Split by Measures** replaces every cut. With `L` and `R` the ends of the sliced region,
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
detected hit onset strictly inside the sliced region, and names the slices as W11
does. The detection method is the program's own. It must satisfy:

- a cut is placed at or just before the first frame of a hit's attack, never
  after its peak;
- for material made of hits separated by digital silence, at
  `DEFAULT_SENSITIVITY` there is exactly one cut per hit, excluding a hit that
  starts at the start of the sliced region;
- raising the sensitivity control never reduces the number of cuts for the
  same audio and sliced region;
- if the cuts found would put a key above `LAST_KEY`, the quietest onsets are
  dropped until they fit.

On a recorded drum break, sensitivity 99 gives more cuts than sensitivity 0.

Changing the sensitivity control after a Split by Transients, with no other
edit (a tempo change is one) in between, runs the split again before the control's event handler
returns; the new result replaces the previous split as one undo step.

**W13. Undo** is Cmd+Z and **redo** Shift+Cmd+Z (Ctrl elsewhere). Each move,
add, remove, split and run of tempo changes (W24) is one step; a drag from press to release is one move. Undoing every step leaves the boundaries,
slices and tempo as read, and the window then has no unsaved edit.

**W24. Tempo.** The tempo is the `bpm` the saved manifest will hold: the
manifest's value at launch, then whatever `--bpm` or the `bpm` control last
set. `rcy-export --from-manifest` takes it from the manifest (SPEC.md R21)
and writes it to the kit's MIDI file (R15). Changing it changes no boundary,
no slice and nothing about audition (W18).

The `bpm` control shows the tempo rounded to `TEMPO_DECIMALS` places, without
trailing zeros (`165.5`, `137.72`). Its `step` attribute is `any`, so one
press of the element's arrows adds or subtracts 1 from the shown value. When
the control reports a change after the person typed or stepped in it:

- text equal to the shown text is no change;
- text in the `--bpm` form (W20) whose number makes `rcySdk.tempoWritable`
  true becomes the tempo, exactly as typed and unrounded, as one edit;
- any other text is refused: the tempo is unchanged, the control shows the
  tempo again and the status line says why.

The range check applies to a new tempo only. A manifest tempo that fails it
is shown, and saved unchanged, like any other.

A tempo the control never changed is saved as the exact number read, so W04's
byte-for-byte rule holds for a manifest whose tempo has more decimal places
than the control shows.

A tempo change made through the control that directly follows another, with
no other edit, undo or redo between them, replaces it, so a run of changes is
one undo step. If a change brings the shown text back to the text shown
before the run, the run is removed and the tempo is again the exact number it
was before the run. `--bpm` is not part of a run.

**W25. Order.** The order is the sequence the slices play in: a list of
slice numbers (1-based, by position in the source), each entry a **slot**. A
slice may fill several slots or none. It is the manifest's `order` member at
launch, source order (every slice once, ascending) when the manifest has
none, and the saved manifest holds it as `rcySdk.manifestText` writes it: no
member for source order. W03 refuses a manifest whose `order` is anything else.

The window shows and plays the audio in that order. Inside the sliced region
the slots are laid end to end, each with its slice's own frames and length;
outside it the audio is the source's. With repeats or slices left out the
shown audio is longer or shorter than the source, and the shown length is
`shownFrames` (W19). The waveform, the cut lines, the playback line, a click
on a slice and Space (L to R, looping) all follow this layout, so Space plays
the loop as arranged. Only the edits in this section change the order;
moving a locator never does. A slice keeps its
number, `key`, `file` and `role` wherever it plays; a slice shown away from
its source position has its number in the cut colour. The manifest's
`boundaries` and `slices` stay in source order: reordering changes `order`
and nothing else.

Each slice wide enough shows a handle of six dots before its number. Dragging
a slice by the strip moves it to the drop line: before the first slice whose
middle is right of the pointer, or last. A drop that leaves the order
unchanged is no edit. A reorder is one undo step and clears the selection and
the cursor. A press on the strip while audio plays does not stop it until
the release shows the press was a click; when the L-to-R loop is playing at
a reorder, it starts again from L in the new order, and any other sound stops.

A click on a slice in the strip selects its slot, shown with a tint; a click
in the strip outside every slice clears the selection. With a slot selected:

| Key | Effect |
|---|---|
| Cmd+C (Ctrl elsewhere) | Copies the slot's slice. No edit. |
| Cmd+V | Inserts the copied slice after the selected slot, or last when none is selected, and selects the new slot. |
| Cmd+D | Inserts the slot's slice again directly after it and selects the new slot. |
| Cmd+X | Copies the slot's slice and removes the slot. The only slot can't be cut. |

Each is one undo step. Paste and duplicate are not applied when the order
already holds `ORDER_MAX_SLOTS` slots. While the `bpm` control has focus
these keys belong to it.

Cuts are edited in any order. A shown line stands for a source cut: each
line is the start of the slice in the slot on its right, and the last line is
the end of the last slot's slice. A line that stands for an end of the sliced
region can't be moved or removed (W08a). An edit changes the source cuts and
the order follows:

- **Move** (drag or arrow keys). The source cut moves by the number of frames
  the pointer or key moved it, limited as W08 limits it against its
  neighbours in the source. During a drag only the dragged line moves; the
  release lays the slots out again, and every slot of the two slices that
  meet at that cut takes its new length.
- **Add.** A cut added at a point in a slot goes the same distance into that
  slot's slice. The slice splits as in W09, and every slot of it becomes two
  slots, the two halves in source order. The cut is not added when the order
  would exceed `ORDER_MAX_SLOTS` slots.
- **Remove.** Removing a line merges the slice on its right into the slice
  before it in the source, as in W10. Each slot of either slice plays the
  merged slice, and two slots that played them one after the other become
  one.
- **Split by Measures and Split by Transients** replace every slice, so the
  order returns to source order; the split and that return are one undo step.

An edit that changes the number of slices clears the slot selection and the
copied slice. The edit's entry in the run record holds the source
`boundaries`, and `order` when the order is not source order.

**W26. Loop.** L and R are loop markers on the arranged slices. The loop is
a run of one or more neighbouring slots: L stands at the start of its first
slot and R at the end of its last. At launch, and after either split or
Source order, the loop is every slot.

Dragging a locator's flag moves that locator to the slice edge nearest the
pointer, and L stays at least one slot before R. Moving a locator changes no
cut, no slice and no slot of the order: it changes what Space plays, what is
shaded as outside the loop, and what Save keeps. A move is one undo step, and
its entry in the run record has `loop`, the numbers of the loop's first and
last slot. When the loop is playing at the release it starts again from the
new L.

The loop keeps its slots through other edits. A reorder drag leaves L and R
at their positions, so the slots between them may change. A slot pasted or
duplicated inside the loop lengthens it; a slot cut from it shortens it, and a
loop left with no slot becomes every slot. A cut added or removed leaves the
loop over the same audio.

Save keeps the loop and discards the rest. With `lo` and `hi` the lowest and
highest slice numbers among the loop's slots, the written manifest has the
boundaries of slices `lo` to `hi`, those slices with each `key` lowered by
`lo - 1` and renamed by position when the names were default (W07), and an
`order` that lists the loop's slots numbered from `lo` as 1. A slice between
`lo` and `hi` that no slot of the loop plays stays in the kit, because a
manifest's boundaries are one unbroken run of the source. `--expect-slices`
(W21) and the run record's `final` count and hold what Save writes.

The joins between reordered slices are played as cut, with no fade.
`rcy-export` writes the kit's MIDI file in this order and keeps `order` in the kit's manifest (SPEC.md R15, R21).

## Display

**W14.** One plot per channel, stacked, sharing the horizontal axis; one plot
for a mono source. The reference is ReCycle's main window: a waveform across
the full width, a vertical line with a small triangle at its top for each
cut, and the two locators marked L and R (W26).

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
| Press within `PICK_PIXELS` of a boundary's line, anywhere in the plot's height, and drag | Moves that cut (W08, W25); it follows the pointer. The boundary becomes the selected one. A press on an end of the sliced region selects it and moves nothing (W08a). |
| Press on a locator's flag in the strip above the plots (`FLAG_PIXELS`) and drag | Moves that locator to the slice edge nearest the pointer (W26). The flag wins over a cut's line and over a slice's handle under it; where the two flags overlap, the nearer locator's line wins. |
| Press and release on a boundary without moving | Selects it. |
| Left or Right with a boundary selected | Moves it one frame. With Shift, the number of frames one pixel covers, at least one. |
| Double-click, or Option-click (Alt-click), in the plot, not on a boundary | Adds a cut at that frame (W09) and selects it. Audio the first click of a double-click started is stopped. |
| Double-click or Option-click on a cut, or Delete or Backspace with a cut selected | Removes it (W10). |
| Press on a slice in the strip above the plots (its handle and number), not on a boundary, and drag more than `PICK_PIXELS` | Reorders (W25): a line shows where the slice would drop, and the release moves it there. A press released without that travel is a click in the plot. |
| Click in the plot, not on a boundary, no modifier | Sets the cursor to that frame. If audio is playing, stops it. Otherwise plays the slice under the pointer from its start. |
| Shift-click in the plot | Plays from the clicked frame to the end of that slice. |
| Space | If audio is playing, stops it. Otherwise plays from L to R, looping until stopped. |
| A key in `AUDITION_KEYS` | Plays the slice with that number (W25) from its start. A press while audio plays replaces the sound. |
| `=` | Zooms in by `ZOOM_STEP`, keeping the frame under the pointer at the same pixel when the pointer is over the plot, otherwise the frame at the plot's centre. The new span is `max(span * ZOOM_STEP, MIN_VIEW_FRAMES)`. |
| `-` | Zooms out the same way. The view never extends outside 0 to `N`. |
| Wheel or pinch over the plot | Vertical wheel zooms about the pointer; horizontal wheel scrolls. |
| `f` | Shows the whole file. |
| `z` | Fits the view to the slice under the pointer. |

`viewStart` and `viewEnd` may be fractional. No boundary ever snaps to
anything.

Every key in this document, including Save, Close, Undo and Redo, acts when
its `keydown` event reaches the page, whichever element has focus, except
that Left and Right belong to the sensitivity control while it has focus, and
that every key pressed without Cmd or Ctrl belongs to the `bpm` control while
it has focus. There, Enter applies the typed tempo (W24) and Escape restores
the shown tempo, and both release focus; a press in the plot applies the typed
tempo and releases focus. Save and Close, by key or by button, apply the
typed tempo first and do not act if it is refused. Undo and Redo discard the
typed text and then act. An
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
| `bpm` | `input type="number"` | The tempo in beats per minute (W24); typed, or stepped with the element's own arrows |
| `status` | any | The status line (W16) |
| `add-cut` | button | Adds a cut at the cursor (W09) and selects it. Disabled while there is no cursor or a cut can't be added there. |
| `delete-cut` | button | Removes the selected cut (W10). Disabled unless a cut is selected. |
| `source-order` | button | Puts the slices back in source order (W25), as one edit. Disabled while they are in source order. |
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
  boundaries: number[],      // the manifest's, in source order
  slices: { key, file, role }[],
  order: number[],           // slice numbers in play order (W25)
  loop: [number, number],    // the loop's first and last slot, 1-based (W26)
  shown: number[],           // the boundaries as drawn, one more than the order has slots; equal to boundaries in source order
  shownFrames: number,       // length of the audio as shown; equal to frames in source order
  slot: number | null,       // the selected slot, 0-based index into order
  viewStart: number,
  viewEnd: number,
  plot: { x, y, width, height },   // CSS pixels in the viewport; the top channel's plot
  selected: number | null,   // index into boundaries
  cursor: number | null,     // frame
  playing: boolean,
  bpm: number,               // the applied tempo (W24); text still being typed in the control is not in it
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
measure editing, playing or stretching audio at another tempo, effects,
settings, and any network access.
