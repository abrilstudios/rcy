# The rcy PyQt6 waveform window at `9696f12^`

This page describes the behaviour of the PyQt6 slicing window in the rcy repository at tree `9696f12^` (commit `2380399df2b4f51b1ac3d877e612872eaf472f13`), the parent of the commit that deleted it. Every `file:line` reference is a path under `src/python/` at that tree unless it starts with `config/` or `presets/` or is `Justfile`. Where a reference gives only a file name, the file is the one of that name in the list below; the names are unique. Config defaults are the values in `config/config.json` at the same tree.

Source files read: `main.py`, `rcy_view.py`, `ui/control_panel.py`, `ui/transport_controls.py`, `ui/menu_bar.py`, `ui/dialogs.py`, `ui/shortcuts.py`, `ui/waveform/*.py`, `controllers/*.py`, `view_state.py`, `segment_manager.py`, `audio_processor.py`, `audio_utils.py`, `high_performance_audio.py`, `utils/audio_preview.py`, `export_utils.py`, `commands.py`, `config_manager.py`, `enums.py`, `config/config.json`, `presets/presets.json`, `Justfile`. The file `src/python/waveform_view.py` is absent from this tree; the waveform widget lives in `ui/waveform/`.

Terms used below. A locator is one of the two movable vertical lines, labelled L and R, that bound a region of the file. A slice marker is a fixed vertical line at a segment boundary. A segment is the audio between two adjacent boundaries; the boundary list always contains sample 0 and the last sample, so N boundaries give N-1 segments (`segment_manager.py`).

## 1. Layout

`just run` starts `src/python/main.py` (`Justfile:26-27`). `main()` loads the preset `amen_classic` (`main.py:35`, 4 measures per `presets/presets.json:2-7`), builds the controller and the window, and loads `sys.argv[1]` as an audio file if one is given (`main.py:62-65`).

The window is a `QMainWindow` titled "RCY" (config `strings.ui.windowTitle`), opened at position (100, 100) with size 800 by 600 pixels (`rcy_view.py:185-186`). The central widget uses background `#cbe9f3` and text colour `#0a2239` (`rcy_view.py:203-208`, `config/config.json:3-15`) and the font "Futura PT Book" with substitutes Futura, Century Gothic, Avant Garde, Avenir, Gill Sans, Arial (`config_manager.py:121-134`). The code creates no status bar; menu actions set status tips that have no widget to appear in.

Regions from top to bottom (`rcy_view.py:184-258`):

| Order | Region | Contents | Reference |
|---|---|---|---|
| 0 | Menu bar | File, Process, Options, Help | `ui/menu_bar.py:91-95` |
| 1 | Control panel, row 1 | "Number of measures:" integer field (1 to 1000, initial "1", then set from the preset); "Tempo:" read-only field showing `NNN.NN BPM` or "N/A"; "Tempo Adjust:" checkbox (off); BPM integer field (40 to 300, placeholder "BPM", max width 80 px) | `ui/control_panel.py:63-131`, `:427` |
| 2 | Control panel, row 2 | "Sensitivity:" label; horizontal slider 0 to 99 with ticks every 10, initial value 80; a label showing the slider's integer value | `ui/control_panel.py:133-165` |
| 3 | Control panel, row 3 | Resolution combo box: Whole Note (1), Half Note (2), Quarter Note (4), Eighth Note (8), Sixteenth Note (16); initial Quarter Note (4) | `ui/control_panel.py:167-191` |
| 4 | Waveform | pyqtgraph `GraphicsLayoutWidget`; two stacked plots (left channel above right) when `audio.stereoDisplay` is true (the default), one plot otherwise | `ui/waveform/pyqtgraph_widget.py:94-195` |
| 5 | Scroll bar | Horizontal `QScrollBar`; `valueChanged` redraws the view | `rcy_view.py:245-247` |
| 6 | Transport row | Two checkable buttons: "Split by Measures" and "Split by Transients" | `ui/transport_controls.py:60-73` |

There are no play, stop, zoom or cut buttons. The docstring of `ui/transport_controls.py:3-7` names Cut Selection and Zoom In/Out, and the config holds strings for them, but the file creates neither.

Menus (`ui/menu_bar.py`):

| Menu | Item | Shortcut | Behaviour | Reference |
|---|---|---|---|---|
| File | Open Session | Ctrl+O | Shows a "Coming Soon" message box | `:99-131`, `rcy_view.py:947-954` |
| File | Import Audio | Ctrl+I | File dialog, filter `*.wav *.mp3 *.ogg *.flac *.aif *.aiff`, then loads the file | `rcy_view.py:956-969` |
| File | Open Preset (submenu) | | One entry per preset in `presets/presets.json`; loads it | `:373-387` |
| File | Export | Ctrl+E | Directory dialog, then export (section 8) | `rcy_view.py:166-178` |
| File | Save As | | Handler body is `pass` | `rcy_view.py:180-182` |
| Process | Export as One Sample (checkable) | | TODO stub | `:210` |
| Process | Silence Selected (checkable) | | TODO stub | `:215` |
| Process | Normalize... | | TODO stub | `:220` |
| Process | Convert to Mono | | Converts using the method chosen under Options; disabled for mono files | `:230-234`, `:422-429` |
| Process | Convert Sample Format... | | TODO stub | `:239` |
| Process | Crop Loop | Ctrl+T | Crops the file to the L and R locators, recalculates tempo, resets locators | `:241-274`, `controllers/application_controller.py:681-715` |
| Process | Remove DC | | TODO stub | `:279` |
| Process | Re-Analyze | | TODO stub | `:284` |
| Process | Add Slices at 1/16ths | | TODO stub | `:289` |
| Options | Playback Tempo > Enable Tempo Adjustment (checkable) | | Mirrors the Tempo Adjust checkbox | `:291-357` |
| Options | Playback Mode > One-Shot / Loop (exclusive) | | Default One-Shot (config `audio.playback.mode`) | `:291-357` |
| Options | Convert to Mono > Left Channel / Right Channel / Mix (Blend) (exclusive) | | Default Mix | `:291-357` |
| Help | Keyboard Shortcuts | | Dialog with a static text (section 9) | `ui/dialogs.py:58-85` |
| Help | About | | Dialog | `:359-371` |

Stereo and mono differ only in the number of plots. With `stereoDisplay` true and a mono file, the second plot is hidden (`ui/waveform/plot_rendering.py:94-108`).

## 2. Waveform drawing

Each plot draws one polyline of amplitude against time in seconds, pen colour `waveform` (`#0a2239`), width 1, antialiased (`pyqtgraph_widget.py:53`, `:104-105`). The plot background is the palette `background` colour (`:77`). The bottom (time) axis is hidden; the code doesn't touch the left axis, which pyqtgraph shows by default (`:140-145`). No grid is drawn, although a `gridLines` colour exists in the config.

On every redraw the x range is set to the first and last time of the data passed in, with no padding, and the y range to plus and minus the maximum absolute sample value of the visible data with 10 % padding (`plot_rendering.py:84-91`). The vertical scale therefore changes with the scroll position.

Display downsampling (`controllers/view_controller.py:34-91`, `utils/audio_preview.py`): the controller slices the raw samples for the visible window, then, with `audio.downsampling.enabled` true (default), reduces them to `target_length = min(max(2 × widget width in px, minLength), maxLength)` points, where `minLength` is 1000 and `maxLength` is 5000. The config key `targetLength` (2000) is not read by this path. With method `envelope` (default) each channel is cut into `target_length / 2` equal bins and the bin maximum and minimum are written as adjacent points (`utils/audio_preview.py:34-74`); with method `simple` every k-th sample is kept (`:7-31`). The time array is always decimated by striding (`:104`). If the visible slice already has no more than `target_length` samples, the raw samples are drawn unchanged (`:46-47`).

Per-slice display:

| Element | Drawn as | Colour key and default | Reference |
|---|---|---|---|
| Slice marker line | Non-movable vertical `InfiniteLine`, width 1, at every boundary including file start and end, on both plots | `sliceActive` `#7f8fa6` | `ui/waveform/segment_visualization.py:81-92` |
| Slice marker triangle | Downward-pointing triangle, 12 px (`ui.sliceMarkers.width`), at the top edge of the top plot only, for internal boundaries only (boundaries within 0.001 s of file start or end get none) | `sliceActive` | `ui/waveform/slice_markers.py:15-94` |
| Active segment | `LinearRegionItem` spanning the playing range on both plots, non-movable | `activeSegmentHighlight` `#cccccc`, alpha 64 | `segment_visualization.py:152-197` |
| Temporary highlight | Same item type | `selectionHighlight` `#ff3366`, alpha 75 | `segment_visualization.py:221-278` |

The code draws no slice numbers and no text labels on slices. The palette keys `sliceHover`, `gridLines` and `cutButton` are not read by any drawing code I found.

## 3. Markers

### Locators (L and R)

Each plot gets a start and an end `InfiniteLine`, movable, width 3 (5 on hover), colours `startMarker` and `endMarker` (both `#007fa3`) (`pyqtgraph_widget.py:112-131`). Below each locator on the top plot sits a square handle box, 10 px wide (`ui.markerHandles.width`), carrying the letter "L" or "R" in bold 8 pt text coloured as the background. The L box sits just right of its line and the R box just left of its line, a few pixels above the bottom of the plot (`ui/waveform/marker_handles.py:92-269`).

A locator moves in two ways, both with the left mouse button:

| Gesture | Path | Constraints applied |
|---|---|---|
| Drag the line itself | pyqtgraph's own `InfiniteLine` dragging; `on_marker_dragged` then clamps | Start within [0, end − 0.01 s]; end within [start + 0.01 s, total time]; mirrored to the other plot (`ui/waveform/marker_interactions.py:13-91`) |
| Drag the L or R handle box | `DraggableHandle` press, move, release (`marker_handles.py:23-89`), routed to `_on_handle_clicked` (`pyqtgraph_widget.py:516-561`) and `set_start_marker` / `set_end_marker` | Same 0.01 s minimum gap; start snaps to 0.0 when it lands below the snap threshold; clamped to the visible data range (`marker_interactions.py:134-333`) |

Releasing a locator emits `start_marker_changed` or `end_marker_changed`, and the tempo controller recalculates tempo from the locator span (section 7). Hit-testing for both gestures is done by pyqtgraph on the item's own shape; the code sets no pick distance. Locators can't be deleted. `clear_markers` resets them to 0 and the file length (`rcy_view.py:814-827`), and loading or cropping a file does the same.

When slices are redrawn, a locator span shorter than 0.1 s causes the end locator to jump to the end of the file (`rcy_view.py:459-461`, `segment_visualization.py:69-71`).

### Slice markers

Slice markers are not draggable. They change only through these actions:

| Action | Gesture | Rule | Reference |
|---|---|---|---|
| Add | Left click on the waveform with Ctrl or Alt held, not within 0.1 s of an existing slice | Boundary added at the click time; positions at or beyond file start or end are ignored; duplicates are dropped | `ui/waveform/plot_interactions.py:112-136`, `segment_manager.py:73-74` |
| Remove | Left click with Ctrl or Alt held within 0.1 s of an existing internal slice | The nearest internal boundary within 0.1 s is removed | `plot_interactions.py:116-126`, `segment_manager.py:206-249` |
| Replace all | Split by Measures or Split by Transients | Section 6 | |

The modifier test is `ControlModifier` or `AltModifier` (`plot_interactions.py:112`). In Qt on macOS `ControlModifier` is the Command key and `AltModifier` is Option; the code's own comment at `:110-111` states a different mapping. Shift and Meta are not tested. Only the left button is handled (`:63-65`), and the context menu is disabled.

A click of any kind within 0.1 s of either locator is discarded (`plot_interactions.py:101-107`). With the locators at their default positions this covers the first and last 0.1 s of the file.

All the distances above (0.1 s, 0.01 s, 0.001 s) are in seconds of audio and don't scale with the visible span.

### Snapping

One snap exists: the start locator moves to exactly 0.0 when set to a position below `ui.markerSnapping.snapThreshold`, 0.05 s by default (code fallback 0.025 s) (`marker_interactions.py:169-170`, `config/config.json:105-107`). It applies to handle-box drags and programmatic sets, and not to dragging the line itself. There is no snapping to a grid, to transients or to zero crossings, for locators or for slices. Slice positions are stored as `int(time × sample_rate)`.

## 4. Zoom and scroll

The window offers no zoom gesture. Mouse interaction on each plot's view box is disabled for both axes (`pyqtgraph_widget.py:140-145`), which removes pyqtgraph's wheel zoom and drag pan; no wheel handler, zoom button, menu item or key is connected to `zoom_in` or `zoom_out`.

The zoom code that exists is unreachable from the window: `ViewController.zoom_in` multiplies the visible time by 0.97 and `zoom_out` by 1.03, both anchored at the centre of the view (`controllers/view_controller.py:93-123`, `commands.py:21-53`). `ViewState.zoom(factor, anchor_frac=0.5)` keeps the anchor time fixed and clamps the visible time to [0, total time] (`view_state.py:22-27`, `:60-77`). It has no lower floor, so nothing in the code ties a minimum zoom to a sample count.

The visible window is fixed at `min(10 s, file length)`: `visible_time` starts at 10.0 (`view_controller.py:31`, `application_controller.py:90`). A file of 10 s or less is shown whole. For longer files the scroll bar moves the window, with `start = (total − visible) × scroll_bar.value() / 100` (`view_controller.py:58`, `view_state.py:38`). Every redraw resets the visible time to the controller's stored 10 s before clamping it to the file length (`view_controller.py:56-57`), so a short file doesn't shrink the window for the next one. The code never sets the scroll bar's range; on file load, preset load and cut it sets the page step to `int(visible / total × 100)` (`rcy_view.py:873-880`, `application_controller.py:267`, `:303`, `:654`).

At the fixed window, whether individual samples are visible depends on the file: the raw samples are drawn only when the visible slice holds no more than the target point count (1000 to 5000). At 44.1 kHz that is a file of at most about 0.11 s.

## 5. Audition

| Trigger | What plays | Reference |
|---|---|---|
| Left click on the waveform, no modifier | If audio is playing, playback stops and nothing starts. Otherwise the segment containing the click plays from its start, with start and end clamped to the L and R locators, and that range is highlighted | `plot_interactions.py:136`, `controllers/playback_controller.py:91-163` |
| Space | If audio is playing, stop. Otherwise play from the L locator to the R locator and highlight that range | `rcy_view.py:591-622` |
| Keys 1 to 9, 0, Q W E R T Y U I O P | Play segment 1 to 20 by index (0 is segment 10, Q to P are 11 to 20), clamped to the locators. A key press while audio is playing replaces the current sound; it doesn't stop it | `rcy_view.py:33-38`, `:541-589`, `high_performance_audio.py:431-460` |

Playback goes through a `sounddevice` output stream with 2 channels and a block size of 512 frames (`audio_processor.py:81-85`, `high_performance_audio.py:228-234`). The segment plays as cut: the tail fade call is commented out in both processing functions (`audio_utils.py:342-344`, `:398-400`), so the `audio.tailFade` config has no effect, and there is no reverse path in playback.

One-Shot mode (default) plays the range once. A 100 ms timer polls for the end of playback and then clears the highlight (`application_controller.py:136-138`, `:463-484`). In Loop mode the audio engine re-queues the same range each time its queue empties, and continues until something stops it (`high_performance_audio.py:297-300`, `:351-357`, `:462-467`).

Playback stops on Space, on an unmodified click on the waveform, or at the end of the range in One-Shot mode. Changing the playback tempo restarts the output stream, which also ends playback (`high_performance_audio.py:194-209`, `:242-257`).

No playhead is drawn. The only playback indication is the static highlight over the playing range. The engine exposes `get_playback_position` (`high_performance_audio.py:485-497`), and the view never calls it.

## 6. Slicing actions

The two transport buttons are mutually exclusive toggles (`ui/transport_controls.py:78-98`). Checking one unchecks the other and runs its split; unchecking the active one emits a clear request. Loading a file unchecks both without emitting (`:152-169`, `controllers/audio_controller.py:142`).

Split by Measures (`controllers/segment_controller.py:52-90`, `segment_manager.py:165-189`): the number of divisions is `measures × resolution`, where resolution is the combo box value (default 4). The span is divided into that many equal lengths of time, and the internal boundaries replace every existing slice. The span is the whole file when the locators are at their defaults, and the L-to-R region otherwise (`segment_controller.py:75-83`). While the button is checked, committing a new measures value or choosing another resolution re-runs the split (`rcy_view.py:401-421`).

Split by Transients (`audio_processor.py:296-332`): librosa computes onset strength on the left channel, then `onset_detect` with `delta = threshold × 0.1` (`deltaFactor`), `wait = 1`, `pre_max = 1`, `post_max = 1`; the detected onsets replace every existing slice. It always analyses the whole file. The threshold starts at the config value 0.2 (`application_controller.py:100`). Moving the Sensitivity slider sets `threshold = (1 − value / 99)^5` (`ui/control_panel.py:226-251`), so a higher slider value gives a lower threshold. Detection re-runs when the slider is released, and only while the Split by Transients button is checked (`rcy_view.py:392-399`).

Clear (unchecking the active button) calls `on_clear_segments` (`rcy_view.py:423-431`), which redraws slice lines only and leaves the stored boundaries in place; see defect D1.

Manual add and remove are described in section 3. Neither split touches the locators, apart from the 0.1 s rule in section 3.

## 7. Tempo and measures

Tempo is derived, never typed: `BPM = measures × 4 / (duration in minutes)`, with 4 beats per measure fixed in code (`audio_processor.py:255-271`, `controllers/tempo_controller.py:214`). The duration is the whole file while the locators are at their defaults and the L-to-R span once either has moved (`tempo_controller.py:71-152`, `:186-261`). The Tempo field shows the result to two decimals.

Editing "Number of measures" (committed on Enter or focus loss) recalculates the tempo and, if Split by Measures is checked, re-splits. An invalid entry resets the field to "1" (`ui/control_panel.py:210`). Releasing a locator recalculates the tempo from the new span. Neither action changes the waveform drawing or the locators.

Tempo Adjust changes playback and export speed and has no effect on the display. When enabled with a target BPM, the output stream is reopened at `int(sample_rate × target / source)` Hz, so pitch and speed change together (`high_performance_audio.py:194-209`). Typing a BPM enables the checkbox automatically; an invalid entry resets the field to "120" (`ui/control_panel.py:292-306`). Loading a file sets the target to the rounded source tempo and turns the adjustment off (`application_controller.py:242-275`).

## 8. Export and save

File > Export (Ctrl+E) asks for a directory and writes (`controllers/export_controller.py`, `export_utils.py`):

| File | Content | Reference |
|---|---|---|
| `001.wav`, `002.wav`, ... | One WAV per segment, for every segment in the file. Segments are not clamped to the L and R locators. With Tempo Adjust on, each segment is resampled by linear interpolation to the target tempo and written at the file's original sample rate; with it off, samples are written unchanged | `export_utils.py:97`, `:278-303`, `audio_utils.py:53-106`, `:326-333` |
| `<directory name>.sfz` | One line per segment: `<region> sample=NNN.wav key=K`, where K is 60 for `001.wav` and rises by 1 per segment | `export_utils.py:306`, `:354-357` |
| `<directory name>.mid` | One track, 4/4, tempo equal to the target BPM if Tempo Adjust is on and the source BPM otherwise; one note per segment, pitch 60 for the first segment and rising by 1, velocity 100, laid end to end. Each note lasts as long as its segment; with Tempo Adjust on, that length is multiplied by source BPM / target BPM | `export_utils.py:139-146`, `:185-233`, `:360-363` |

A completion dialog then lists the segment count, the SFZ and MIDI file names, time signature, tempo, duration and directory, with an "Open Folder" button (`ui/dialogs.py:155-226`).

No tail fade is applied on export, for the reason given in section 5. Save As does nothing, and Open Session is a placeholder, so the window has no way to save or reload slice positions. Process > Crop Loop and Process > Convert to Mono change the audio held in memory and write no file.

## 9. Keyboard shortcuts

Shortcuts that work at `9696f12^`:

| Key | Action | Scope | Reference |
|---|---|---|---|
| Space | Toggle playback of the L-to-R region | Application-wide event filter; fires even while a text field has focus | `ui/shortcuts.py:51-69`, `rcy_view.py:541-557` |
| 1 2 3 4 5 6 7 8 9 | Play segment 1 to 9 | Window key press | `rcy_view.py:33-38`, `:541-557` |
| 0 | Play segment 10 | Window key press | same |
| Q W E R T Y U I O P | Play segments 11 to 20 | Window key press | same |
| Ctrl+O | Open Session (placeholder dialog) | Menu | `ui/menu_bar.py:99-131` |
| Ctrl+I | Import Audio | Menu | same |
| Ctrl+E | Export | Menu | same |
| Ctrl+T | Crop Loop | Menu | `ui/menu_bar.py:133-204` |
| Ctrl or Alt + left click | Add a slice, or remove one within 0.1 s | Waveform | `ui/waveform/plot_interactions.py:112-136` |

Qt maps `Ctrl+` menu shortcuts to Command on macOS.

Defined in code and not reachable: Plus or Equal raises the sensitivity slider by 1 and Minus or Underscore lowers it by 1 (`ui/shortcuts.py:94-104`), but nothing calls `handle_key_press`. The Help > Keyboard Shortcuts dialog also lists "Shift+Click: play first segment" and "Alt+Cmd+Click or Ctrl+Alt+Click: remove segment" (`ui/dialogs.py:58-85`); the live click handler has no Shift case, and removal uses the same chord as addition.

## 10. Defects and TODO comments

| Id | Defect | Evidence |
|---|---|---|
| D1 | Unchecking a split button doesn't clear slices. `on_clear_segments` passes `[0.0, total_time]` (seconds) to `update_slices`, which divides each value by the sample rate, and never calls `SegmentManager.clear_segments`. The stored boundaries survive, so audition and export still use them and the next redraw shows them again | `rcy_view.py:423-435`, `segment_manager.py:251-255` |
| D2 | Zoom is implemented in the controller and command layer with no control wired to it | `view_controller.py:93-123`, section 4 |
| D3 | Dragging a locator line in the bottom (right-channel) plot moves only that line; drag signals are connected for the top plot's locators only | `pyqtgraph_widget.py:149-150`, `:213-218` |
| D4 | The sensitivity keys never fire (section 9) | `ui/shortcuts.py:71-113` |
| D5 | The initial slider position (80) and the initial threshold (0.2) don't correspond; 80 maps to about 0.0003 under the slider formula, so the first slider movement changes detection sharply | `ui/control_panel.py:147-154`, `:226-251`, `application_controller.py:100` |
| D6 | Clicks within 0.1 s of a locator are ignored, including the first and last 0.1 s of a file with default locators | `plot_interactions.py:101-107` |
| D7 | The Keyboard Shortcuts dialog describes click chords the handler doesn't implement | `ui/dialogs.py:58-85` |
| D8 | Import Audio shows an error dialog when the user cancels the file dialog | `rcy_view.py:965-969` |
| D9 | Tail fade is configured (`enabled: true`, 3 ms) and commented out in both processing functions | `audio_utils.py:342-344`, `:398-400` |
| D10 | Export ignores the L and R locators | `export_utils.py:97`, `:149-151` |
| D11 | `rcy_view.py` holds handlers that reference names the class and module don't define (`self.ax_left`, `self.ax_right`, `self.canvas`, `Polygon`) and that no signal is connected to: `on_plot_click`, `is_near_marker`, `on_button_release`, `on_motion_notify`, `on_key_press`, `_create_marker_handles`, `_update_marker_handle`, `_update_marker_visibility`. `on_cut_button_clicked` has no button | `rcy_view.py:261-381`, `:492-524`, `:624-693`, `:695-871` |
| D12 | The scroll position is `value / 100` and the code leaves the scroll bar at Qt's default range | `view_controller.py:58`, `rcy_view.py:873-883` |
| D13 | A stereo or mono mismatch between the data and the display mode logs a warning and continues | `plot_rendering.py:44-47` |
| D14 | `commands.py:9` imports types from a module `rcy_controller` that isn't in the tree (under `TYPE_CHECKING` only) | `commands.py:8-9` |

A search of `src/python` for TODO, FIXME, XXX and HACK finds only these seven comments. TODO stubs: Process menu items Export as One Sample, Silence Selected, Normalize, Convert Sample Format, Remove DC, Re-Analyze and Add Slices at 1/16ths (`ui/menu_bar.py:210`, `:215`, `:220`, `:239`, `:279`, `:284`, `:289`); File > Save As (`rcy_view.py:180-182`); File > Open Session (`rcy_view.py:947-954`).

## Screenshots in history

`git log --all --diff-filter=A --name-only -- '*.png' '*.jpg' '*.gif'` finds one window screenshot path, `screenshots/rcy.png`, added in `0c63abb` (2025-04-06), modified in `630731d` and `12bb202` (both 2025-04-13) and deleted in `355dde4` (2025-11-23). `.github/social_preview.png` (added in `a04d35a`) is the other image and was not opened.

Both screenshots predate the tree described here and show controls it lacks.

| Commit and path | What it shows |
|---|---|
| `12bb202:screenshots/rcy.png` (best) | Title "RCY"; "Number of measures" and "Tempo" fields; Split by Measures, Split by Transients and a "Quarter Note (4)" combo on one row; an "Onset Threshold" slider reading 0.10; two stacked waveform plots with a left amplitude axis ticked at 1, 0, −1; small triangles at the bottom corners of the top plot; a scroll bar; Zoom In, Zoom Out and a black Cut Selection button |
| `0c63abb:screenshots/rcy.png` | An earlier single-plot window titled "Recycle View" with dashed vertical slice lines, a boxed axis with amplitude ticks, and the same Zoom In, Zoom Out and Cut Selection buttons |

No image of the window as it stood at `9696f12^` exists in history.

## Not determinable from the code

- The rendered appearance at `9696f12^`: pane proportions, whether the left amplitude axis is visible, how the font substitution resolves, and how the L and R boxes look. The code was read and not run.
- The effective scroll bar range. The code relies on Qt's default for `QScrollBar` (0 to 99 by Qt's documentation), under which the window start can't reach `total − visible`.
- The pixel distance at which pyqtgraph picks up a locator line or handle for dragging; it is library behaviour.
- Which physical keys act as the add/remove modifier on macOS; this follows Qt's mapping, and the in-code comment contradicts Qt's documented one.
- Whether key presses reach `window_key_press` when a text field or the slider has focus, apart from Space, which the application-wide filter handles.
- Whether dragging a locator line (as opposed to its handle box) redraws the handle box during the drag.
- What librosa's onset detector returns for a given slider value on a given break, and therefore how many slices any sensitivity produces.
- Whether Loop mode loops cleanly in practice; the engine re-queues from inside the audio callback, and the code was not exercised.
- Whether any of the dead handlers in D11 raise at runtime; none is connected, so none should run.
