# 🤝 Contributing to RCY
### 1. Clone & Setup

```bash
git clone https://github.com/tnn1t1s/rcy.git
cd rcy
pip install -r requirements.txt
python src/python/main.py
```

Ensure you're using Python 3.11+ 

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

— abrilstudios / @tnn1t1s
