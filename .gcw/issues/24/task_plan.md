# Task Plan: Formal GCW CLI Orchestration Commands

## Goal
Add formal terminal-first GCW CLI commands so users can run, inspect, and route the GCW main workflow from the `gcw` binary without depending on IDE skill routing.

## Current Phase
Phase 2

## Phases

### Phase 1: Requirements & Workflow Discovery
- [x] Confirm the target workflow outcome from Issue #24
- [x] Inspect the current npm CLI surface and GCW runtime entrypoints
- [x] Capture constraints and reusable components in findings.md
- **Status:** complete

### Phase 2: CLI Surface & Runtime Integration Plan
- [ ] Define the supported CLI commands and argument shape
- [ ] Decide how Node CLI delegates to existing GCW runtime and step runners
- [ ] Define state discovery, routing, and error-handling behavior
- **Status:** in_progress

### Phase 3: Command Implementation
- [ ] Add CLI parsing and handlers for `run`, `step`, `status`, and `next`
- [ ] Reuse existing workflow validation, projection rebuild, and step runner logic
- [ ] Preserve existing `init`, `doctor`, and version behavior
- **Status:** pending

### Phase 4: Tests & Documentation
- [ ] Add command parsing and orchestration coverage
- [ ] Add at least one happy-path workflow test and one invalid-phase failure test
- [ ] Update README, quickstart, and contributing docs for terminal-first usage
- **Status:** pending

### Phase 5: Verification & Delivery
- [ ] Run relevant npm and GCW tests
- [ ] Verify the new CLI commands behave correctly in an initialized repo
- [ ] Prepare implementation summary and follow-up risks
- **Status:** pending

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

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `verify_remote_triage.py` required an existing `gcw-issue-triage` event before verification | 1 | Continued with the repository’s actual step-runner flow and noted the mismatch between skill prose and implementation in findings.md. |

## Notes
- Implementation should keep the CLI usable in repos initialized by `gcw init`.
- Terminal-first flow must stop at GCW human handoff states instead of continuing into implementation or human review automatically.
