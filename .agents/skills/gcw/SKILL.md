---
name: gcw
description: Orchestrate the Git Collaboration Workflow from an existing GitHub or GitLab issue through the eight GCW step skills, stopping at clarification, blockers, review feedback, or review completion. Use when the user invokes /gcw or asks to process an issue through GCW.
---

# GCW

Top-level orchestrator for the Git Collaboration Workflow. Use this skill only to choose and run the next `gcw-*` step skill; do not duplicate step details here.

## Contract

Before doing anything, read `docs/workflow.md`. It is the source of truth for steps, states, Action roles, and stop conditions.

## Steps

1. `gcw-issue-intake`
2. `gcw-issue-prepare`
3. `gcw-issue-to-spec`
4. `gcw-spec-check`
5. `gcw-implement`
6. `gcw-implement-check`
7. `gcw-pr-publish`
8. `gcw-pr-review`

Each step owns its inputs, procedure, state transition, and stop conditions.

## State Routing

| Current state | Next step |
| --- | --- |
| Existing Issue outside GCW | `gcw-issue-intake` |
| `issue-opened` | `gcw-issue-prepare` |
| `issue-clarifying` | Stop until the missing answer is available, then `gcw-issue-prepare` |
| `ready-for-planning` | `gcw-issue-to-spec` |
| `planned` | `gcw-spec-check` |
| `ready-for-implementation` | `gcw-implement` |
| `implementing` | `gcw-implement` or `gcw-implement-check`, depending on whether implementation work is still needed |
| `ready-for-review` | `gcw-pr-publish` |
| `reviewing` | `gcw-pr-review` for automatic review; platform human review remains an external event |
| `changes-requested` | `gcw-implement` with `feedback_source` metadata preserved |
| `blocked` | Stop until the blocker is resolved, then resume from `resume_state` / `resume_step` |
| `review-complete` | Stop; the workflow is closed |

## Rules

1. Start from exactly one existing GitHub or GitLab issue.
2. Never skip ahead of the current state.
3. Do not create implementation changes before `gcw-spec-check` reaches `ready-for-implementation`.
4. Do not publish a review request before `gcw-implement-check` reaches `ready-for-review`.
5. Do not run human review actions locally; human review happens on GitHub/GitLab and is recorded as platform events.
6. Preserve `feedback_source` when moving from `changes-requested` back into implementation.
7. Preserve `resume_state` / `resume_step` when a step enters `blocked`.
8. Stop and report clearly when the workflow enters `issue-clarifying`, `blocked`, or `review-complete`.

## Reporting

After each step, report only: step executed, state before/after, key artifact or blocker, and next step.
