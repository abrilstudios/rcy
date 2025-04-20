# L1/L2 Workflow Setup: GitHub Organization Roles

This document outlines the setup required for implementing an L1/L2 workflow in the RCy project, with different roles for junior (L1) and senior (L2) AI assistants.

## 1. GitHub User Roles

Create a separate user account for L1 work:

- **Username**: `claude-jr`
- **Role**: Junior developer (L1)
- **Permissions**: Read/write access to repositories, can create issues and PRs

## 2. Issue Labels

Create the following labels in the repository:

| Label | Color | Description |
|-------|-------|-------------|
| `L1` | `#E99695` | Tasks appropriate for Claude Jr. (simple, well-defined) |
| `L2` | `#FBCA04` | Tasks requiring Claude's expertise (complex, design decisions) |
| `review-needed` | `#D93F0B` | Work completed by L1 that needs L2 review |

## 3. Simple Workflow

1. **Task Assignment**:
   - Label new issues as either `L1` or `L2` based on complexity
   - Assign L1 tasks to the claude-jr user

2. **Handoff Process**:
   - L2 creates issues with clear requirements for L1
   - L1 implements changes and creates PRs
   - L1 adds the `review-needed` label when ready for review
   - L2 reviews and provides feedback

3. **Task Examples**:
   - **L1 Tasks**: Documentation updates, simple bug fixes, test case additions
   - **L2 Tasks**: Feature development, architecture changes, performance optimizations

## Implementation Checklist

- [ ] Create `claude-jr` GitHub user
- [ ] Add user to organization with appropriate permissions
- [ ] Create the issue labels described above
- [ ] Update CLAUDE.md with the L1/L2 workflow section
- [ ] Test the workflow with a simple handoff task