# GCW Phase 1 Completion Plan

## Goal

Complete the local, checkable GCW Phase 1 gaps before starting hosted apply or cloud implementation work.

## Scope

- Add state management commands for blocked, clarifying, local self-review, and ownership handoff.
- Support GitHub and GitLab planning links in readiness evidence.
- Add machine-readable JSON schemas for GCW evidence files.
- Add a representative `.gcw/issues/` fixture so CI exercises evidence validation.
- Wire schemas and fixture checks into CI and documentation.

## Out of Scope

- Hosted apply workflows that mutate branches or issues.
- GitLab CI parity.
- Cloud agent implementation or `/fix` loops.
- Remote API verification of progress comments or PR/MR bodies.

## Phases

1. Complete: Add behavior tests for the local state-machine gaps.
2. Complete: Implement the minimal state management changes.
3. Complete: Add schemas and fixture validation.
4. Complete: Update CI and docs.
5. Complete: Run validation and inspect the diff.
6. Complete: Add unified check/apply step runner.
7. Complete: Add read-only GitLab CI parity.
8. In progress: Validate the extended slice and inspect final status.

## Validation Plan

- `python3 -m unittest discover -s .agents/skills/gcw/tests`
- `python3 -m unittest discover -s .github/tests`
- CI script checks via the workflow unit tests.
