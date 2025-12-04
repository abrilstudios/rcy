# Documentation Index

This is the main documentation directory for RCY. Below is an organized index of all available documentation.

## Core Documentation

- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture and component descriptions
- **[README.md](../README.md)** - Project overview, installation, and basic usage
- **[TUI User Guide](tui-guide.md)** - Complete guide to the terminal user interface
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Contribution guidelines and development workflow
- **[CLAUDE.md](../CLAUDE.md)** - Coding standards and AI assistant guidelines

## Architecture & Design

### Component Design Documents

- **[Playback and Export Pipelines](../designs/playback-export-pipelines.md)** - Audio playback and SFZ export architecture
- **[Tempo Calculation System](../designs/tempo-calculation-system.md)** - Time-stretching and BPM calculations
- **[Stereo to Mono Conversion](../designs/stereo-to-mono-conversion.md)** - Audio channel handling
- **[RCY-Orca Integration](../designs/rcy_orca_integration.md)** - Integration with Orca livecoding environment

### Segment Management Design

- **[Segment Manager Design](design/segments/segment-manager-design.md)** - Segment storage and manipulation
- **[Segment Mutation Inventory](design/segments/segment-mutation-inventory.md)** - Operations and state transitions
- **[Segments and Markers](design/segments/segments_and_markers.md)** - Relationship between segments and markers

## Reference & History

### Domain Knowledge

- **[Breakbeat Science](breakbeat-science.md)** - Understanding breakbeat workflows and history
- **[Drum & Bass Sampling Techniques](drum_and_bass_sample_techniques.md)** - Historical context of sampling techniques

### Development Setup

- **[GitHub Setup](github_setup.md)** - GitHub authentication and multi-user configuration
- **[PAT Instructions](pat_instructions.md)** - Creating and using GitHub Personal Access Tokens
- **[L1/L2 Workflow](l1_l2_workflow.md)** - Junior and senior AI assistant collaboration workflow

## Issue Documentation

Historical issue documentation and resolution details are stored in [`issues/`](issues/):

- **[Issue 128 Updates](issues/issue_128_update.md)** & **[Final](issues/issue_128_final_update.md)** - High performance audio playback implementation
- **[Issue: Marker Tempo](issues/issue_description.md)** - Marker movement and tempo adjustment behavior
- **[Issue: Playback Tempo Fixes](issues/issue_doc.md)** - Playback tempo synchronization fixes

## Directory Structure

```
docs/
├── INDEX.md (this file)
├── tui-guide.md
├── breakbeat-science.md
├── drum_and_bass_sample_techniques.md
├── github_setup.md
├── pat_instructions.md
├── l1_l2_workflow.md
├── design/
│   └── segments/
│       ├── segment-manager-design.md
│       ├── segment-mutation-inventory.md
│       └── segments_and_markers.md
├── issues/
│   ├── issue_128_update.md
│   ├── issue_128_final_update.md
│   ├── issue_description.md
│   └── issue_doc.md
└── (design documents linked from ../designs/)
```

## Quick Links

- **For New Users**: Start with the [TUI User Guide](tui-guide.md)
- **For New Contributors**: Start with [CONTRIBUTING.md](../CONTRIBUTING.md)
- **For Understanding RCY**: Read [README.md](../README.md) and [Breakbeat Science](breakbeat-science.md)
- **For Architecture Details**: See [ARCHITECTURE.md](../ARCHITECTURE.md) and modernization phases
- **For Development Setup**: See [GitHub Setup](github_setup.md) and [PAT Instructions](pat_instructions.md)
- **For Issue Context**: Browse [issues/](issues/) directory
