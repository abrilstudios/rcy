# Claude Guidance for RCY Project

This directory contains structured guidance for Claude AI to effectively assist with RCY project issues.

## Purpose

These files provide context, implementation plans, testing strategies, and prompt suggestions to help Claude effectively work on specific issues even with limited context windows or across multiple sessions.

## Directory Structure

Each issue has its own dedicated directory:

```
/claude-guidance/
  ├── README.md
  ├── 144/                 # Issue #144: MVC Architecture Refactoring
  │   ├── overview.md      # Issue overview and implementation plan
  │   ├── prompt-guide.md  # Suggested prompts and best practices
  │   ├── key-concepts.md  # Core concepts and patterns
  │   ├── implementation-progress.md  # Current status and next steps
  │   └── testing-guide.md # Testing strategies and examples
  └── [other-issue-number]/
      └── ...
```

## How to Use

### For Users

1. Reference these files when asking Claude to work on specific issues:
   ```
   Please read the guidance in /claude-guidance/144/ to understand the 
   one-way data flow architecture refactoring issue, then help me implement
   the RcyStore class.
   ```

2. Update the implementation-progress.md file as tasks are completed:
   ```
   Now that we've completed implementing the RcyStore class, please update
   the /claude-guidance/144/implementation-progress.md file to reflect
   this progress.
   ```

### For Claude

1. Start by reading the overview.md file for the relevant issue to understand the context and goals

2. Consult the prompt-guide.md file for suggested response patterns 

3. Reference key-concepts.md for specific architectural patterns and principles

4. Check implementation-progress.md for current status and next tasks

5. Use testing-guide.md when implementing or verifying functionality

## Contribution

When completing significant portions of an issue or starting new issues:

1. Create a new issue directory if needed
2. Update the implementation-progress.md file
3. Add any new concepts or patterns to key-concepts.md
4. Document testing approaches in testing-guide.md

## Current Issues

- **#144**: Refactor MVC Architecture to Remove Circular Dependencies
  - Status: Design phase complete, implementation not started
  - Goal: Implement one-way data flow architecture to resolve circular dependencies in the zoom functionality
  - Key Files: See /claude-guidance/144/overview.md