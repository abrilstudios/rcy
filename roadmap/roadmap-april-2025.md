# 🛣️ RCY Roadmap (April 2025)

This document outlines the current and near-future priorities for the RCY application as it matures into a performance-grade audio slicing and breakbeat preparation tool. Each phase is based on recent implementation progress, design alignment, and ongoing user feedback.

---

## ✅ Completed (Mar–Apr 2025)

- [x] Implemented segment slicing by bars and transients
- [x] Added start/end markers with draggable triangle handles
- [x] Introduced segment highlighting, delete buttons on hover
- [x] Configurable tail-fade with linear/exponential decay options
- [x] Refactored slicing logic to separate markers from segments
- [x] Created `presets/` system for artist-authored waveform splits
- [x] Implemented mono/stereo waveform handling
- [x] Introduced real-time playback engine with segment preview
- [x] Integrated waveform downsampling for fast, faithful display
- [x] Separated model/view concerns and introduced full test coverage
- [x] Design documentation written for key features and decisions

---

## 🧱 In Progress

- [ ] PyQtGraph rendering backend (replacing Matplotlib)
- [ ] UI cleanup pass: sizing, spacing, control unification
- [ ] Visual overlay improvements (highlight active slice, hover fade, etc.)
- [ ] Smarter zoom/scroll ergonomics
- [ ] Optional loop playback between start/end markers

---

## 🧪 Upcoming (Mid-April 2025)

- [ ] Add waveform editing tools (insert, delete, reassign slices)
- [ ] Keyboard control of slices (`QWERTYUIOP` mapping for top-row triggers)
- [ ] Preset browser with auto-load + metadata (tempo, artist, tags)
- [ ] Skins and UI themes (e.g. Jungle, IDM, Classic Sampler, New Order)
- [ ] Slice-to-MIDI export
- [ ] Export to SFZ/SF2 directly

---

## 🧭 Strategic

- [ ] Distributable desktop build (macOS, eventually Windows)
- [ ] Shift to agent-assisted CLI for CLI slicing workflows
- [ ] Educational content + tutorial demos for each preset
- [ ] Expand presets library with historic breakbeats (Think, Apache, etc.)
- [ ] Contributor guide + plugin system (e.g. for custom slicing agents)

---

RCY aims to be a next-generation waveform editor that balances *aesthetic quality*, *configurable behavior*, and *historical respect for breakbeat culture*. Every feature serves the dual purpose of helping users work faster and *hear more deeply*.