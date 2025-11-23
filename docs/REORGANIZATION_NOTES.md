# Documentation Reorganization - Phase 5.1

This document describes the documentation cleanup and organization completed in Phase 5.1 of the RCY modernization project.

## Overview

The documentation structure has been reorganized to improve clarity, discoverability, and maintainability. This involved:

1. Creating a dedicated `docs/issues/` directory for issue-specific documentation
2. Removing outdated documentation
3. Consolidating duplicate content
4. Updating references and links
5. Creating architecture documentation
6. Establishing a documentation index

## Changes Made

### New Directories

- **`docs/issues/`** - Dedicated directory for issue-related documentation and debugging notes
  - Contains historical issue documentation, resolution details, and debug findings
  - Keeps the root directory clean while preserving issue context

### Files Moved to `docs/issues/`

The following issue-specific files were moved from the root directory to `docs/issues/`, preserving git history via `git mv`:

| Original Location | New Location | Purpose |
|---|---|---|
| `issue_92_downsampling_tests.md` | `docs/issues/issue_92_downsampling_tests.md` | Audio downsampling testing |
| `issue_93_gui_testing.md` | `docs/issues/issue_93_gui_testing.md` | PyQt GUI testing documentation |
| `issue_128_update.md` | `docs/issues/issue_128_update.md` | Audio playback implementation progress |
| `issue_128_final_update.md` | `docs/issues/issue_128_final_update.md` | Audio playback final status |
| `issue_description.md` | `docs/issues/issue_description.md` | Marker and tempo issue description |
| `issue_doc.md` | `docs/issues/issue_doc.md` | Playback tempo fixes documentation |
| `issue_mvc_refactoring.md` | `docs/issues/issue_mvc_refactoring.md` | MVC refactoring specification |
| `debug_file_import_issues.md` | `docs/issues/debug_file_import_issues.md` | File import debugging notes |

### Files Moved to `docs/`

Configuration and setup documentation was moved to `docs/` for better organization:

| Original Location | New Location | Purpose |
|---|---|---|
| `github_setup.md` | `docs/github_setup.md` | GitHub authentication setup |
| `pat_instructions.md` | `docs/pat_instructions.md` | Personal access token creation |
| `l1_l2_workflow.md` | `docs/l1_l2_workflow.md` | L1/L2 AI assistant workflow |
| `drum_and_bass_sample_techniques.md` | `docs/drum_and_bass_sample_techniques.md` | Domain knowledge documentation |

### Files Removed

**`CODEX.md`** - Deleted
- Documentation about OpenAI's deprecated Codex API
- No longer relevant to the project
- Replaced by CLAUDE.md for AI assistant guidance

**`LAST.md`** - Deleted
- Duplicate of `docs/issues/debug_file_import_issues.md`
- Consolidated to single source of truth

### Files Created

**`ARCHITECTURE.md`** - New file at project root
- Comprehensive system architecture documentation
- Documents MVC pattern and component responsibilities
- Explains modernization phases (2, 3, and 4)
- Links to design documents and specifications
- Establishes architectural principles and guidelines

**`docs/INDEX.md`** - New file
- Central documentation index
- Organizes all documentation by category
- Provides quick navigation to related documents
- Maps documentation structure for new contributors

### Files Updated

**`README.md`**
- Updated Python requirement from "3.x" to "3.11+"
- Added note about Python 3.13+ support
- Added "Development Setup" section describing modern tooling (ruff, mypy, pyproject.toml, pytest)
- Added "Architecture" section linking to documentation
- Fixed link to drum_and_bass_sample_techniques.md to use new location

**`CONTRIBUTING.md`**
- Updated Python requirement from "3.10+" to "3.11+"

**`CLAUDE.md`**
- No changes required (still accurate)

## Documentation Structure

### Root Level

```
/
├── README.md               # Project overview and setup
├── CONTRIBUTING.md         # Contribution guidelines
├── CLAUDE.md              # AI assistant guidelines
├── ARCHITECTURE.md        # System architecture (NEW)
```

### docs/ Directory

```
docs/
├── INDEX.md               # Documentation index (NEW)
├── REORGANIZATION_NOTES.md # This file (NEW)
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
└── issues/                # NEW DIRECTORY
    ├── issue_92_downsampling_tests.md
    ├── issue_93_gui_testing.md
    ├── issue_128_update.md
    ├── issue_128_final_update.md
    ├── issue_description.md
    ├── issue_doc.md
    ├── issue_mvc_refactoring.md
    └── debug_file_import_issues.md
```

## Link Updates

All references to moved files have been updated:

- `README.md`: Links to `docs/drum_and_bass_sample_techniques.md` (previously linked to root)
- Issue documentation is now referenced as `docs/issues/[filename]`

## Benefits of Reorganization

1. **Cleaner Root Directory**: Root contains only critical project documentation
2. **Better Organization**: Issue documentation is grouped logically
3. **Improved Discoverability**: INDEX.md provides comprehensive navigation
4. **Clear Architecture**: ARCHITECTURE.md documents system design
5. **Git History Preserved**: All moves used `git mv` to maintain commit history
6. **Single Source of Truth**: Eliminated duplicate documentation (LAST.md)
7. **Modern Standards**: Updated Python version requirements across documentation

## Navigation Guide for Contributors

1. **New to the project**: Start with `README.md`
2. **Want to contribute**: Read `CONTRIBUTING.md`
3. **Understanding architecture**: See `ARCHITECTURE.md` and `docs/INDEX.md`
4. **AI assistant work**: Reference `CLAUDE.md`
5. **Looking for specific documentation**: Use `docs/INDEX.md` as a map
6. **Need issue context**: Browse `docs/issues/`

## Future Documentation Considerations

1. Consider creating INSTALLATION.md for detailed platform-specific setup
2. Document testing strategies and CI/CD pipeline
3. Add troubleshooting guide for common issues
4. Create quick-start guide for common tasks
5. Document release process and version management
