# 🥁 RCY Breakbeat Slice Presets

This directory contains **historically-informed breakbeat slice presets** for use with RCY. Each folder includes:

- A **raw break** (`.wav`)
- One or more `.sfz` files with **named slice layouts** based on real producers' styles
- A `notes.md` file with **cultural and technical context**

These presets are curated to reflect the **actual edits** and **chop styles** used in seminal jungle, drum & bass, and hardcore records. The goal is to provide an **educational, remixable archive** rooted in the history of breakbeat culture.

## 📁 Directory Structure

```
presets/
├── amen/
│   ├── amen.wav
│   ├── dillinja.sfz
│   ├── bukem.sfz
│   └── notes.md
├── think/
│   ├── think.wav
│   ├── source_direct.sfz
│   ├── paradox.sfz
│   └── notes.md
├── apache/
│   ├── apache.wav
│   ├── photek.sfz
│   └── notes.md
```

## ✂️ SFZ Presets

Each `.sfz` file contains:
- Slice points corresponding to a specific artist's break edit
- Comments (`//`) explaining slice logic where applicable
- Region mappings usable directly in TAL Sampler

Example:

```sfz
// Dillinja-style Amen cuts
<region> sample=amen.wav start=2112 end=4608 key=36
<region> sample=amen.wav start=4609 end=6780 key=37
...
```

## 📚 Notes

Each `notes.md` file provides:
- Track references (e.g. *The Angels Fell*, *Music*, *Snake Style*)
- Links to discussions, analyses, or reconstructions
- Explanations of what makes this cut unique (e.g. reversed kicks, silence gaps)

## 🔥 Why This Matters

Most samplers and tools are agnostic. RCY isn't. It has a point of view. These presets turn RCY into a living document of jungle history — not just a slicer, but a way to **learn from the legends** and carry their work forward.

Pull requests welcome. Include attribution and documentation when submitting new presets.