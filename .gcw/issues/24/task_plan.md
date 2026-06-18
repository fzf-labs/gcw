# Task Plan: Formal GCW CLI Orchestration Commands

## Goal
Add formal terminal-first GCW CLI commands so users can run, inspect, and route the GCW main workflow from the `gcw` binary without depending on IDE skill routing.

## Current Phase
Phase 5

## Phases

### Phase 1: Requirements & Workflow Discovery
- [x] Confirm the target workflow outcome from Issue #24
- [x] Inspect the current npm CLI surface and GCW runtime entrypoints
- [x] Capture constraints and reusable components in findings.md
- **Status:** complete

### Phase 2: CLI Surface & Runtime Integration Plan
- [x] Define the supported CLI commands and argument shape
- [x] Decide how Node CLI delegates to existing GCW runtime and step runners
- [x] Define state discovery, routing, and error-handling behavior
- **Status:** complete

### Phase 3: Command Implementation
- [x] Add CLI parsing and handlers for `run`, `step`, `status`, and `next`
- [x] Reuse existing workflow validation, projection rebuild, and step runner logic
- [x] Preserve existing `init`, `doctor`, and version behavior
- **Status:** complete

### Phase 4: Tests & Documentation
- [x] Add command parsing and orchestration coverage
- [x] Add at least one happy-path workflow test and one invalid-phase failure test
- [x] Update README, quickstart, and contributing docs for terminal-first usage
- **Status:** complete

### Phase 5: Verification & Delivery
- [x] Run relevant npm and GCW tests
- [x] Verify the new CLI commands behave correctly in an initialized repo
- [ ] Prepare implementation summary and follow-up risks
- **Status:** in_progress

## Key Questions
1. How should the Node CLI invoke GCW runtime behavior without duplicating phase-routing rules?
2. Which command outputs should be human-readable summaries versus structured machine-friendly output?
3. How much orchestration logic belongs in `bin/gcw.js` versus a reusable runtime wrapper module?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Reuse the existing Python GCW runtime and step-runner contracts instead of recreating the workflow state machine in Node | The repository already encodes routing, projection validation, and milestone semantics in the GCW runtime, so the CLI should act as a thin orchestration layer. |
| Scope the first slice to `run`, `step`, `status`, and `next` only | These commands cover the core terminal-first workflow promised by Issue #24 while keeping the implementation independently shippable. |
| Preserve current `init` and `doctor` as existing top-level commands | The package already exposes those entrypoints and the issue explicitly requires backward compatibility. |
| Let `gcw run` stop at the documented GCW human handoff states even in terminal-first mode | This keeps CLI orchestration aligned with the top-level GCW contract instead of silently pushing through review or clarification gates. |
| Keep `gcw step` and `gcw run` thin over Python runtime commands, with small Node-side helpers for repo detection and default payload wiring | This minimizes drift while still giving terminal users a first-class entrypoint. |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `verify_remote_triage.py` required an existing `gcw-issue-triage` event before verification | 1 | Continued with the repository’s actual step-runner flow and noted the mismatch between skill prose and implementation in findings.md. |
| CLI tests for step execution tried to publish progress comments to the fixture repository `owner/repo` | 1 | Added a fake `gh` test environment so the Node CLI still drives the real Python runtime while remote side effects stay local and deterministic. |

## Notes
- Implementation should keep the CLI usable in repos initialized by `gcw init`.
- Terminal-first flow must still stop at GCW human handoff states, while allowing automatic continuation through terminal-safe steps such as `gcw-implement-check` and `gcw-pr-publish`.
- The current terminal-first path can intake an existing issue, drive triage/clarify/spec planning, continue implementation into review publication, and execute explicit steps through the Python runtime from the `gcw` binary.
