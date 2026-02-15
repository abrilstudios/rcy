# S2800 SysEx Expert Agent

An AI agent that is a genuine expert on the Akai S2800/S3000/S3200 MIDI System Exclusive protocol. Built with Google's Agent Development Kit (ADK) and Gemini 2.5 Pro.

## Agent design, not database design

This is not a parameter lookup tool with an LLM bolted on. The agent carries the **complete 3,298-line specification text** in its context window, giving it the ability to reason over protocol details that no structured database captures: message sequencing rules, model-specific edge cases, the interaction between voice assignment and mute groups, why certain parameter combinations produce unexpected behavior.

The structured tools (`spec.py`, `tools.py`) exist to give the agent precise, non-hallucinated data points -- exact offsets, byte sizes, valid ranges. But the reasoning happens against the raw specification. When you ask "why are my drums cutting each other off?", the agent:

1. Uses `read_program_summary` to pull the current device state
2. Uses `read_keygroup_parameter` to check mute groups on each keygroup
3. Cross-references against the spec text to understand mute group semantics
4. Identifies the conflict (all keygroups in group 0 = mutual cancellation)
5. Uses `write_keygroup_parameter` to fix it
6. Reads back to confirm the change

Steps 1, 2, 5, and 6 are tool calls. Steps 3 and 4 are reasoning -- the part that makes this an agent rather than a script.

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

**agent.py** defines a single `Agent` object. It loads the full specification text into the system prompt, giving Gemini the raw document to reason over. It registers 13 tools that the agent calls for precise operations.

**spec.py** encodes the specification as Python dataclasses: `Parameter` (name, offset, size, range, models), `HeaderSpec` (program/keygroup/sample headers with their parameters), `OpCode` (the 12 SysEx operations), `ModulationSource`, and `ModelDifferences`. This is the structured knowledge layer that prevents hallucination on factual questions.

**tools.py** contains two categories of tools:

*Spec tools* (6) query the structured data:
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

Device tools share a singleton `_SamplerConnection` that lazily connects on first use and keeps the MIDI connection open across tool calls. This matters because the agent often chains multiple reads (check polyphony, then mute groups, then voice assignment) and reconnecting each time adds latency and risks losing device state.

### Write safety

Write tools follow a read-before-write-read-back pattern:
1. Read the current value
2. Write the new value
3. Read back to confirm the change took effect
4. Return before/after values so the agent (and user) can verify

## Running

```bash
# CLI (called from Claude Code or terminal)
s2800-agent param FILFRQ              # Spec lookup
s2800-agent read POLYPH               # Read from device
s2800-agent write POLYPH 15 0         # Write to device
s2800-agent summary                   # Full program overview

# ADK (programmatic)
from s2800.agent import agent
# Use with ADK runner or pass to another agent framework
```

## Why Gemini 2.5 Pro?

The specification is ~50KB of dense technical text. Gemini 2.5 Pro has the context window to hold it alongside a multi-turn conversation, and the reasoning capability to trace through protocol interactions that span multiple sections of the document. The model choice is about context capacity and reasoning depth over a technical domain, not brand preference.
