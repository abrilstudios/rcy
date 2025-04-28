# RCY + Orca + Logic: Getting Started

[![PyPI version](https://img.shields.io/pypi/v/rcy)](https://pypi.org/project/rcy/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)]()

**Quickly preview amen-break sequences with Orca, then finalize composition and mix in Logic Pro using RCY.**

---

## 1. Overview

Leverage RCY’s powerful slice-based engine, Orca’s ASCII-grid sequencer, and Logic Pro’s mixing workflow:

1. **Prototype rhythms** in Orca via OSC.  
2. **Capture MIDI** or audio loops of your slices.  
3. **Refine, arrange, and mix** in Logic Pro.

---

## 2. Prerequisites

- **RCY** v1.x installed (`pip install rcy`)  
- **Orca** desktop or in-browser build ([hundredrabbits/Orca](https://github.com/hundredrabbits/Orca))  
- **Python-OSC** library (`pip install python-osc`)  
- **Logic Pro** (or any DAW that accepts audio/MIDI)

---

## 3. Installation

```bash
# Install RCY and python-osc
pip install rcy python-osc

# Clone Orca (if desktop)
git clone https://github.com/hundredrabbits/Orca.git
cd Orca/desktop && npm install && npm start
```

---

## 4. Load Your Sample

Slice an amen break (or any WAV):

```bash
# Slice into 8 pieces
rcy load path/to/amen.wav --slices 8
```

---

## 5. Start RCY with OSC

Run RCY’s OSC engine on port 57120:

```bash
rcy play --osc-port 57120
```

---

## 6. Orca Patch for Preview

Open Orca and set OSC target to `127.0.0.1:57120`. Paste:

```
t   0   1   2   3   4   5   6   7
> > > > > > > > S   S   S   S   S   S   S   S
```

Hit **Run** to preview slices live.

---

![Orca → RCY Demo](path/to/demo.gif)

---

## 7. Capture into Logic

1. In Logic Pro, create a new **External MIDI** track and set its input from a **Loopback** or **IAC Bus** receiving from RCY’s virtual MIDI port.  
2. Or record audio outputs directly from RCY into an audio track.  
3. Record a 4‐bar loop while you tweak Orca patterns.

---

## 8. Test Case Snippet

Sample pytest to validate OSC trigger:

```python
import pytest
from rcy.engines.osc_engine import OscEngine

def test_osc_trigger(monkeypatch):
    calls = []
    class Dummy:
        def play_slice(self, idx):
            calls.append(idx)
    eng = OscEngine(Dummy(), port=9000)
    eng._on_trigger(None, 3.0)
    assert calls == [3]
```

---

## 9. Tips & Variations

- Use `?` in Orca for random slice selection.  
- Increase `--slices` for micro-slice granularity.  
- Route RCY MIDI output into Logic’s software instruments for extra processing.  

---

## 10. Next Steps

- Embed this in your webpage with an Orca iframe.  
- Share a short GIF on social channels to showcase live-coding.  
- Extend RCY client to include GUI sliders for filter, pitch, and envelope.

---

Enjoy prototyping breakbeat patterns in code, then bring them into Logic for the final polish!