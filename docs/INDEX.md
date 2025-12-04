# Documentation Index

This is the main documentation directory for RCY. Below is an organized index of all available documentation.

## Core Documentation

- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture, MVC pattern, and component descriptions
- **[README.md](../README.md)** - Project overview, installation, and basic usage
- **[TUI User Guide](tui-guide.md)** - Complete guide to the terminal user interface
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Contribution guidelines and development workflow
- **[CLAUDE.md](../CLAUDE.md)** - Coding standards and AI assistant guidelines

## Architecture & Design

### Modernization Phases

- **[Phase 2: View-State Extraction](phase-2-view-state.md)** - Separating UI window parameters from data state
- **[Phase 3: Command Pattern](phase-3-command-pattern.md)** - Using command objects for user actions
- **[Phase 4: One-Way Data Flow](phase-4-one-way-data-flow.md)** - Establishing strict unidirectional data flow
- **[MVC Current Flow](mvc-current-flow.md)** - Current state of Model-View-Controller implementation

### Component Design Documents

- **[Playback and Export Pipelines](../designs/playback-export-pipelines.md)** - Audio playback and SFZ export architecture
- **[Downsampling Strategy](../designs/downsampling-strategy.md)** - Waveform data downsampling for display
- **[Zoom and Scroll](../designs/zoom-and-scroll.md)** - View window management and interaction
- **[Tempo Calculation System](../designs/tempo-calculation-system.md)** - Time-stretching and BPM calculations
- **[OSC-Based Architecture](../designs/osc-based-architecture.md)** - Open Sound Control integration design
- **[PyQtGraph Migration](../designs/pyqtgraph-migration.md)** - Migration to PyQtGraph for visualization
- **[Stereo to Mono Conversion](../designs/stereo-to-mono-conversion.md)** - Audio channel handling
- **[RCY-Orca Integration](../designs/rcy_orca_integration.md)** - Integration with Orca livecoding environment

### Segment Management Design

- **[Segment Manager Design](design/segments/segment-manager-design.md)** - Segment storage and manipulation
- **[Segment Mutation Inventory](design/segments/segment-mutation-inventory.md)** - Operations and state transitions
- **[Segments and Markers](design/segments/segments_and_markers.md)** - Relationship between segments and UI markers

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

- **[Issue 92: Downsampling Tests](issues/issue_92_downsampling_tests.md)** - Audio waveform downsampling testing
- **[Issue 93: GUI Testing](issues/issue_93_gui_testing.md)** - PyQt GUI testing in headless environments
- **[Issue 128 Updates](issues/issue_128_update.md)** & **[Final](issues/issue_128_final_update.md)** - High performance audio playback implementation
- **[Issue: MVC Refactoring](issues/issue_mvc_refactoring.md)** - Removing circular dependencies from MVC
- **[Issue: Marker Tempo](issues/issue_description.md)** - Marker movement and tempo adjustment behavior
- **[Issue: Playback Tempo Fixes](issues/issue_doc.md)** - Playback tempo synchronization fixes
- **[Debug: File Import Issues](issues/debug_file_import_issues.md)** - Debugging file import display issues

## Directory Structure

```
docs/
├── INDEX.md (this file)
├── tui-guide.md
├── ARCHITECTURE.md (linked from root)
├── README.md (linked from root)
├── CONTRIBUTING.md (linked from root)
├── CLAUDE.md (linked from root)
├── breakbeat-science.md
├── drum_and_bass_sample_techniques.md
├── mvc-current-flow.md
├── phase-2-view-state.md
├── phase-3-command-pattern.md
├── phase-4-one-way-data-flow.md
├── github_setup.md
├── pat_instructions.md
├── l1_l2_workflow.md
├── design/
│   └── segments/
│       ├── segment-manager-design.md
│       ├── segment-mutation-inventory.md
│       └── segments_and_markers.md
├── issues/
│   ├── debug_file_import_issues.md
│   ├── issue_92_downsampling_tests.md
│   ├── issue_93_gui_testing.md
│   ├── issue_128_update.md
│   ├── issue_128_final_update.md
│   ├── issue_description.md
│   ├── issue_doc.md
│   └── issue_mvc_refactoring.md
└── (design documents linked from ../designs/)
```

## Quick Links

- **For New Users**: Start with the [TUI User Guide](tui-guide.md)
- **For New Contributors**: Start with [CONTRIBUTING.md](../CONTRIBUTING.md)
- **For Understanding RCY**: Read [README.md](../README.md) and [Breakbeat Science](breakbeat-science.md)
- **For Architecture Details**: See [ARCHITECTURE.md](../ARCHITECTURE.md) and modernization phases
- **For Development Setup**: See [GitHub Setup](github_setup.md) and [PAT Instructions](pat_instructions.md)
- **For Issue Context**: Browse [issues/](issues/) directory
