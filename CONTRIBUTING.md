# 🤝 Contributing to RCY

Welcome! RCY is more than just a waveform editor — it's a model for building thoughtful, opinionated, and maintainable software for musicians and producers. If you're interested in contributing, this guide will help you understand how to participate in a way that aligns with the project's values.

---

## 🌱 Guiding Principles

- **Taste matters**: RCY prioritizes meaningful defaults, not endless options. Our presets, UI feel, and aesthetic decisions are intentional.
- **Refactor for clarity**: Code should be expressive and modular. Don't pile features into tangled conditionals — split them out.
- **Be explicit**: Avoid clever abstractions unless they make behavior easier to understand.
- **UX before feature count**: Even small visual details (like marker gravity or triangle direction) are critical to the experience.
- **Preserve lineage**: Breakbeat culture and classic workflows matter. Features that honor historic workflows (e.g., S1000 slicing styles) are encouraged.

---

## 📐 How to Contribute

### 1. Clone & Setup

```bash
git clone https://github.com/tnn1t1s/rcy.git
cd rcy
pip install -r requirements.txt
python src/python/main.py
```

Ensure you're using Python 3.10+ and PyQt6.

---

### 2. Follow the Branching Strategy

- **Feature branches**: `feature/your-feature-name`
- **Bugfix branches**: `fix/bug-description`
- **Cleanup/refactor**: `cleanup/target-area`

Use clear names and link to GitHub issues when opening PRs.

---

### 3. Testing Expectations

RCY has growing test coverage. For now:

- **Write tests** for non-UI modules (e.g. audio processing, slicing, preview)
- **Use visual regression** (screenshot comparison) for UI when possible
- **Manual testing is OK** for UX/feel features — just document what you tried

---

### 4. Design-First Contributions

Big changes should follow this pattern:

1. Open an issue with a detailed spec (see [issue #68](https://github.com/tnn1t1s/rcy/issues/68) for a good example)
2. Link to a `designs/*.md` file if applicable
3. Wait for discussion before implementation (especially architectural changes)

---

## ✅ Good First Tasks

- Improve UI responsiveness (see `rcy_view.py`)
- Enhance preset metadata (add more presets with artist/measure info)
- Add hover/loop interaction polish
- Write markdown docs for existing features (e.g. split-by-transients)

---

## 🧠 Learn from RCY

RCY is also a **teaching tool** — it's here to demonstrate:

- How to structure UIs that respect legacy workflows
- How to use config, tests, and careful design decisions
- How to write software *with intent*

If you're new to Qt, audio tooling, or breakbeat culture — welcome! We're building something that remembers where it came from.

---

Thanks for being here. Let's make beautiful, playable tools.

— abrilstudios / @tnn1t1s