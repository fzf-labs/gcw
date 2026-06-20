# Findings & Decisions

## Requirements
- Add formal `gcw` terminal commands for workflow orchestration against an existing GitHub or GitLab issue.
- Support `gcw run <issue-number>`, `gcw step <step-name> <issue-number>`, `gcw status <issue-number>`, and `gcw next <issue-number>`.
- Use the authoritative GCW event log and projection to discover current phase, repair stale projection data when needed, and route legally.
- Keep `gcw init` and `gcw doctor` behavior intact.
- Cover command parsing plus at least one happy-path orchestration case and one invalid-phase failure case with automated tests.

## Research Findings
- The published npm CLI currently exposes only `init`, `doctor`, and version handling in `bin/gcw.js`, so the formal orchestration surface is still missing.
- The repository already has a Python runtime that manages workflow contracts, projection validation, event recording, and step routing under `.gcw/engine/runtime/`.
- `run_gcw_step.py` already executes milestone steps end-to-end for `gcw-issue-triage`, `gcw-issue-clarify`, `gcw-issue-to-spec`, `gcw-spec-check`, `gcw-implement-check`, `gcw-pr-publish`, and `gcw-pr-review`.
- `manage_gcw_workflow.py` already supports workflow initialization, direct event recording, and projection rebuilds, which makes it a natural backend for a terminal-first Node wrapper.
- The current `gcw` top-level skill routes automatically until a human handoff state (`planned`, `issue-clarifying`, `blocked`, `reviewing`, `review-complete`), which should guide `gcw run`.
- A practical terminal-first `gcw` can keep Node thin by delegating state discovery and milestone recording to Python while only adding repository detection, issue bootstrapping, and default payload wiring.
- The CLI can safely continue through terminal-friendly implementation gates such as `gcw-implement-check` and `gcw-pr-publish`, while still stopping at the documented GCW human handoff states.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Keep Node CLI orchestration thin and delegate workflow semantics to Python runtime commands | This avoids drift between IDE skill behavior and terminal behavior. |
| Treat `status` and `next` as state-discovery commands built on event log + projection validation | These commands are primarily read paths and should reflect the same authoritative state used by GCW routing. |
| Model `run` as repeated legal step execution until a GCW stop state is reached | This mirrors the existing `/gcw` automatic continuation contract. |
| Seed planning files and minimal implement-check payloads from local templates when the terminal-first path needs them | This lets the CLI walk the main GCW path in an initialized repo without depending on IDE skill orchestration. |
| Keep the terminal-first path bounded by documented human handoff states | This avoids over-automating review, clarification, and implementation decisions that belong to humans or hosted agents.

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| The triage verification script expects a previously recorded `gcw-issue-triage` event, so it cannot be used strictly before the first triage event exists. | Used the repository’s actual milestone runner flow to advance triage and noted the discrepancy for future cleanup. |

## Resources
- `bin/gcw.js`
- `.gcw/engine/runtime/gcw_steps.py`
- `.gcw/engine/runtime/gcw_workflow_commands.py`
- `.gcw/engine/runtime/gcw_workflow_contracts.py`
- `.agents/skills/gcw/scripts/manage_gcw_workflow.py`
- `.agents/skills/gcw/scripts/run_gcw_step.py`
- Issue #24: https://github.com/fzf-labs/gcw/issues/24

## Visual/Browser Findings
- None.
