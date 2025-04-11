# 🎧 DESIGN NOTE: Downsampling Strategy for Efficient and Trustworthy Waveform Display

## 📌 Context

As RCY evolved from a personal tool to a more robust and modular application, it became clear that the waveform display needed to be both **fast** and **visually faithful** — especially for long or high-sample-rate files. Rendering full-resolution audio waveforms in real-time (especially with Matplotlib) introduced sluggishness and visual overload.

We needed a way to make the waveform feel **snappy**, **clear**, and **true to the source** — even when heavily zoomed out.

---

## 🎯 Goals of Downsampling

- ⚡ **Performance:** Prevent UI lag when rendering high-resolution audio
- 👁️ **Visual Clarity:** Ensure that transients, peaks, and valleys are not lost in simplification
- 🧠 **User Intuition:** Maintain user trust in what they're seeing — the waveform should *feel right* for slicing and interaction

---

## 🧠 Method Chosen: Max-Min Envelope

### What It Does

For every downsampling window:
- Instead of taking a single sample (as in naive striding), we keep:
  - The **maximum** and **minimum** values within the window
- This creates an envelope that **preserves peaks and transients**, even when zoomed out

### Why It Matters

Transients are critical in breakbeat slicing. Tools like ReCycle often relied on the visual shape of the waveform to make fast, intuitive decisions. The max-min method:
- Ensures ghost notes and fast hi-hats still appear as blips
- Gives a more faithful *shape* than simple striding
- Keeps the waveform *alive* under compression

---

## 🔧 Implementation Details

- Downsampling occurs in `utils/audio_preview.py`
- Used only for **visual rendering** — audio processing still uses the full-resolution signal
- Controlled via `config/audio.json`, with parameters:
  ```json
  "downsampling": {
    "enabled": true,
    "method": "envelope",
    "targetLength": 2000,
    "minLength": 1000,
    "maxLength": 5000,
    "alwaysApply": true
  }
  ```
- Target length is dynamically calculated based on the view width

---

## ✅ Results

- Rendering is fast even with multi-megabyte WAV files
- Transients remain visible and interactive
- Users can slice with confidence
- Prepares RCY for PyQtGraph rendering layer without architectural changes

---

## 🔄 Alternatives Considered

- Simple striding: fast but often hides detail
- RMS/mean-based downsampling: visually smooth but poor for transient work
- On-demand redrawing: complex and not suitable for Matplotlib backend

---

## 📁 Files Involved

- `utils/audio_preview.py`
- `controller.py` or `waveform_view.py`
- `config/audio.json`

---

## 🧭 Forward Outlook

This strategy is portable to the future PyQtGraph implementation and will also support:
- Dynamic zoom-based redownsampling
- GPU-accelerated region updates
- Offline rendering of waveform previews

This decision bridges user experience with performance, honoring RCY's design philosophy: *responsive tools with visual truth.*