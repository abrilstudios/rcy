# S2800 SysEx Expert Agent

A dedicated specialist agent for the Akai S2800/S3000/S3200 MIDI System Exclusive protocol. Built with Google's Agent Development Kit (ADK) and Gemini 2.5 Pro.

## The case for specialist agents

An orchestrator agent (Claude Code, Cursor, Aider) coordinates complex workflows across files, tools, and systems. It is good at breadth. It is bad at holding 36 pages of dense binary protocol specification in context while simultaneously reasoning about Python code, git state, test results, and user intent. When you force an orchestrator to be the domain expert, you get diluted context and hallucinated byte offsets.

This agent exists because **one agent doing one thing well beats one agent doing everything poorly.**

The S2800 SysEx spec is ~50KB of dense technical text: 175+ parameters across 3 header types, nibble encoding rules, 12 opcodes, model-specific behavior for 3 hardware variants, and subtle interactions between settings (mute groups vs. polyphony vs. voice assignment vs. priority). No orchestrator should carry this in its working memory. Instead:

- **The orchestrator** knows that a specialist exists and how to call it. It translates user intent ("my drums are cutting each other off") into specialist queries (`s2800-agent summary`, `s2800-agent read-kg kgmute`).
- **The specialist** holds the complete spec, reasons over it, reads/writes the hardware, and returns precise answers. It never manages files, plans refactors, or handles git.

This is how you scale agent workflows without drowning any single agent in context. Each specialist is a self-contained unit with its own model, its own tools, and its own domain knowledge. The orchestrator's context stays clean. The specialist's context stays focused. Hallucinations die because the ground truth is always in scope for the agent that needs it.

## How it works

The agent carries the **complete 3,298-line specification text** in its context window alongside structured parameter data. The spec text enables reasoning; the structured data prevents hallucination on facts.

When you ask "why are my drums cutting each other off?", the agent:

1. Uses `read_program_summary` to pull current device state
2. Uses `read_keygroup_parameter` to check mute groups on each keygroup
3. Reasons against the spec text to understand mute group semantics
4. Identifies the conflict (all keygroups in group 0 = mutual cancellation)
5. Uses `write_keygroup_parameter` to fix it
6. Reads back to confirm

Steps 1, 2, 5, and 6 are tool calls (precision). Steps 3 and 4 are reasoning over the raw spec (understanding). A database lookup tool can do the first set. Only an agent with the spec in context can do the second.

## Architecture

```
agent/
  agent.py                 Agent definition: model, system prompt, tool registration
  spec.py                  Structured spec data as Python dataclasses
  tools.py                 13 tool functions the agent can call
  s2800_sysex_spec.txt     Complete specification text (loaded into context)
  .env                     Gemini API key (gitignored)
```

### How the pieces fit together

**agent.py** defines a single `Agent` object. It loads the full specification text into the system prompt, giving Gemini the raw document to reason over. It registers 13 tools for precise operations. This is the only file that touches ADK.

**spec.py** encodes the specification as Python dataclasses: `Parameter` (name, offset, size, range, models), `HeaderSpec` (program/keygroup/sample headers with all their parameters), `OpCode` (the 12 SysEx operations), `ModulationSource`, and model differences. This structured layer is what makes tool responses exact rather than approximate.

**tools.py** has two categories:

*Spec tools* (6) query structured data, no hardware required:
- `lookup_parameter` -- find a parameter by name (exact or fuzzy)
- `lookup_by_offset` -- reverse lookup: what lives at byte 34 of the keygroup header?
- `list_parameters` -- list/filter parameters for a header type
- `build_sysex_message` -- construct a complete SysEx message from high-level params
- `decode_sysex_message` -- parse raw hex into human-readable breakdown
- `compare_models` -- show S2800/S3000/S3200 differences

*Device tools* (7) talk to real hardware over MIDI:
- `read_device_programs` -- list programs on the connected sampler
- `read_device_samples` -- list samples on the connected sampler
- `read_program_parameter` -- read a single program parameter value
- `read_keygroup_parameter` -- read a single keygroup parameter value
- `read_program_summary` -- read key settings for a full program overview
- `write_program_parameter` -- write a program parameter (with read-back confirmation)
- `write_keygroup_parameter` -- write a keygroup parameter (with read-back confirmation)

### Persistent connection

Device tools share a singleton `_SamplerConnection` that lazily connects on first use and keeps the MIDI connection open across tool calls. The agent often chains multiple reads (polyphony, then mute groups, then voice assignment) and reconnecting each time would add latency and risk losing device state.

### Write safety

Write tools follow a read-before-write-read-back pattern: read current value, write new value, read back to confirm, return before/after. The agent and user both see what changed.

## Running

```bash
# Spec queries (no hardware needed)
s2800-agent param FILFRQ
s2800-agent list keygroup filter
s2800-agent decode "F0 47 00 27 48 ..."

# Live device (S2800 connected via MIDI)
s2800-agent programs
s2800-agent summary
s2800-agent read-kg FILFRQ 0 0
s2800-agent write-kg kgmute 255 0 0
```

## Why Gemini 2.5 Pro?

Context capacity. The spec is ~50KB. A multi-turn diagnostic conversation adds another 10-20KB. Gemini 2.5 Pro holds all of it without truncation, and its reasoning traces through protocol interactions that span multiple sections of the document. The model was chosen for its ability to serve as a dedicated specialist with a large, stable context, not as a general-purpose orchestrator.
