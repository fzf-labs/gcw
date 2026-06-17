---
name: gcw
description: Orchestrate the Git Collaboration Workflow from an existing GitHub or GitLab issue by routing through the nine current `gcw-*` step skills. Use when the user invokes /gcw or asks to process an issue through GCW; stop at clarification, blockers, review feedback, or review completion.
---

# GCW

Top-level orchestrator for the Git Collaboration Workflow. Use this skill only to identify the current workflow state, choose the next `gcw-*` step skill, and run it. Continue through automatically runnable states until the workflow reaches a human-review state. Each step skill owns its own inputs, procedure, state transition, and stop conditions.

## Contract

This skill is self-contained. It includes the GCW steps, states, Action roles, pipelines, and stop conditions. Do not read any external workflow document as the contract source before running GCW.

GCW starts from exactly one existing GitHub or GitLab issue. It does not start from implementation. The issue may be created by a human on the platform or by an agent before GCW starts. The GCW main flow intakes the issue, classifies it, clarifies requirements, and decides whether it is ready for development.

After GCW intake starts, stable workflow facts are appended under `.gcw/issues/<issue-id>/events/` on the issue branch. `.gcw/issues/<issue-id>/workflow.json` is a generated projection cache; validate it against the event log before using it for routing.

GCW has three collaborators:

- **Human**: makes key decisions and business judgments on GitHub or GitLab.
- **Agent**: Codex, Cursor, Claude Code, or similar AI coding tools; handles work requiring judgment and code capability, either locally or inside an Action.
- **Action**: GitHub Actions, GitLab CI, or another hosted pipeline; triggered by platform events and responsible for remote automation, gates, and records.

## State Discovery

Before routing, identify the current workflow state in this order:

1. If `.gcw/issues/<issue-id>/events/` exists on the issue branch or current worktree, treat the event log as the authoritative state source.
2. Validate `.gcw/issues/<issue-id>/workflow.json` with the GCW validation scripts; if it is missing or stale, rebuild it from events before routing.
3. If event files do not exist yet, infer state from issue comments, labels, and the current conversation or handoff context.
4. If a PR/MR exists, inspect platform metadata and review/check results to distinguish `reviewing`, `changes-requested`, and `review-complete`.
5. If state is ambiguous or sources conflict, stop and ask the user to resolve the state before running a step.

## Steps

1. `gcw-issue-intake`
2. `gcw-issue-triage`
3. `gcw-issue-clarify`
4. `gcw-issue-to-spec`
5. `gcw-spec-check`
6. `gcw-implement`
7. `gcw-implement-check`
8. `gcw-pr-publish`
9. `gcw-pr-review`

Main flow:

```text
Existing Issue
  -> gcw-issue-intake
  -> gcw-issue-triage
  -> gcw-issue-clarify
  -> gcw-issue-to-spec
  -> gcw-spec-check
  -> gcw-implement
  -> gcw-implement-check
  -> gcw-pr-publish
  -> gcw-pr-review
  -> wait for GitHub/GitLab human review and final platform outcome
```

Spec files are not uploaded directly to the issue. They are committed under `.gcw/issues/<issue-id>/` on the issue branch, pushed to the remote branch, and linked from an issue comment. Current spec files are `task_plan.md`, `findings.md`, and `progress.md`.

If `gcw-spec-check` finds that the issue is still unclear, return to `issue-clarifying`. Existing spec files remain as drafts and are updated by rerunning `gcw-issue-to-spec` after clarification.

## Step Roles

| Step | GitHub Action file | Goal | Owner | Action role | Next state |
| --- | --- | --- | --- | --- | --- |
| `gcw-issue-intake` | none | Intake an existing issue, create/switch `gcw/issue-<id>`, bootstrap `.gcw/issues/<id>/events/`, and initialize GCW state. | Human / agent | Not needed. Issue intake is initiated by a human or agent, not by a hosted pipeline. | `issue-opened` |
| `gcw-issue-triage` | `gcw-issue-triage.yml` | Classify the issue and apply structured remote triage metadata. | Human / agent / Action | Needed. Run agent classification, sync labels/fields, verify remote metadata, and record state. | `issue-triaged` |
| `gcw-issue-clarify` | `gcw-issue-clarify.yml` | Check whether issue information is sufficient for spec writing and organize clarification questions. | Human / agent / Action | Needed. Run the structural readiness gate and publish structured clarification or readiness progress without replacing human business judgment. | `ready-for-planning` or `issue-clarifying` |
| `gcw-issue-to-spec` | `gcw-issue-to-spec.yml` | Create an isolated worktree, generate spec files from the issue, commit and push them, and link them from an issue comment. | Agent / Action | Recommended. Generate and persist planning files, then record the planning milestone. | `planned` |
| `gcw-spec-check` | `gcw-spec-check.yml` | Check that spec files were generated and pushed, the issue comment links them, and the content is sufficient for implementation. | Agent / Action | Should exist. This is the remote gate before implementation. | `ready-for-implementation`, `issue-clarifying`, or `blocked` |
| `gcw-implement` | `gcw-implement.yml` | Modify code according to the plan, add tests, and update necessary documentation. | Agent / Action | Optional. Advance implementation work and record progress evidence. | `implementing` |
| `gcw-implement-check` | `gcw-implement-check.yml` | Before creating a review request, check diff boundaries, commits, risks, validation results, and spec files; append the implement-check event payload used for PR rendering. | Agent / Action | Should exist. This is the remote gate before creating or updating a review request. | `ready-for-review` |
| `gcw-pr-publish` | `gcw-pr-publish.yml` | Idempotently create or update the PR/MR with summary, issue link, validation results, and risk notes. | Agent / Action | Recommended. Create or update the review request and record the published URL. | `reviewing` |
| `gcw-pr-review` | `gcw-pr-review.yml` | Trigger CI, static checks, remote artifact verification, optional AI review, and summarize PR review results. | Action | Required. The hosted Action owns the automatic review gate; a local agent may summarize existing remote checks and review evidence, but must not replace the gate. | `reviewing`, `changes-requested`, or `blocked` |

Human review and `review-complete` are not main workflow steps. They happen on GitHub or GitLab and are produced by reviewers, merge policy, or platform events.

## State Routing

| Current state | Next step |
| --- | --- |
| Existing Issue outside GCW | `gcw-issue-intake` |
| `issue-opened` | `gcw-issue-triage` |
| `issue-triaged` | `gcw-issue-clarify` |
| `issue-clarifying` | Stop until the missing answer is available, then run `gcw-issue-clarify` |
| `ready-for-planning` | `gcw-issue-to-spec` |
| `planned` | Stop for human spec review; after approval run `gcw-spec-check` |
| `ready-for-implementation` | `gcw-implement` |
| `implementing` | `gcw-implement` or `gcw-implement-check`, depending on whether implementation work is still needed |
| `ready-for-review` | `gcw-pr-publish` |
| `reviewing` | Stop for platform review; `gcw-pr-review` may summarize automatic review evidence, but platform human review remains external |
| `changes-requested` | Run `gcw-implement` with `feedback_source` metadata preserved |
| `blocked` | Stop until the blocker is resolved, then resume from `resume_phase` / `resume_step` |
| `review-complete` | Stop; the workflow is closed |

## Automatic Continuation

When the user invokes `/gcw` without asking for a single specific step, keep routing and running the next allowed step until one of these human-review states is reached:

- `planned` — spec files have been generated and must be reviewed by a human before `gcw-spec-check`.
- `issue-clarifying` — missing product or requirement information must be supplied by a human.
- `blocked` — an external, permission, environment, or workflow blocker must be resolved by a human.
- `reviewing` — the PR/MR has entered platform review; human review and merge decisions happen on GitHub/GitLab.
- `review-complete` — terminal state; no further GCW step should run.

Also stop if state sources conflict, remote metadata cannot be trusted, or the next step requires a business, product, or architecture decision that is not already present in the Issue or spec files.

`reviewing` only means the review request has entered review. After automatic PR review passes, the state remains `reviewing` until a platform human-review event produces `review-complete` or `changes-requested`. When entering `changes-requested`, distinguish the feedback source in metadata, for example `feedback_source: pr-review` or `feedback_source: human-review`.

`gcw-block` and `gcw-clarify` are not main steps; they are feedback-loop actions. `gcw-block` can move any non-terminal state to `blocked` and must record `resume_phase` / `resume_step` in metadata. After the blocker is resolved, resume from that point. `gcw-clarify` can move any stage needing more issue information to `issue-clarifying`.

Initial implementation and feedback fixes both finish through `gcw-implement` -> `gcw-implement-check` -> `gcw-pr-publish` -> `gcw-pr-review`. Feedback fixes differ only because they start from `changes-requested`, return to `implementing`, and then repeat the same closing chain. `gcw-pr-publish` must be idempotent: both first-time review request creation and later updates go through it.

## Action Pipelines

Main steps are the smallest workflow units. Except for `gcw-issue-intake`, main steps that need an Action should have a same-named workflow file. An Action pipeline may group consecutive main steps into one automation entrypoint; this only changes orchestration granularity and does not change main-step state semantics.

| Pipeline | Included steps | Human role | Agent role | Action role | Output state |
| --- | --- | --- | --- | --- | --- |
| Intake, triage, and clarification | `gcw-issue-intake`, `gcw-issue-triage`, `gcw-issue-clarify` | Create or confirm the issue and answer key business questions. | Intake, classify, draft discussion, and check readiness. | Does not run `gcw-issue-intake`; triage syncs metadata, clarify runs readiness and records discussion plus state. | `ready-for-planning` or `issue-clarifying` |
| Planning | `gcw-issue-to-spec`, `gcw-spec-check` | Add clarification when spec information is insufficient. | Generate spec files and self-check content. | Run an agent to generate the spec, push the branch, and verify the hard gate. | `ready-for-implementation`, `issue-clarifying`, or `blocked` |
| Implementation | `gcw-implement`, `gcw-implement-check`, `gcw-pr-publish` | Intervene for decisions when needed. | Write code, add tests, self-check, and create the review request. | May run an implementation agent or receive local agent handoff; must own the check gate and should own PR/MR publication. | `reviewing` |
| Review | `gcw-pr-review` | Continue platform human review based on automatic check results; platform events may request changes or end review. | Return to the implementation pipeline when fixing feedback. Local agents may summarize existing remote checks and review evidence. | Run CI, static checks, AI review, and summarize results as the automatic review gate. | Automatic checks produce `reviewing`, `changes-requested`, or `blocked`; platform events may produce `review-complete` or `changes-requested` |

Any pipeline that hits a hard gate or needs human judgment must stop, hand control back to the human, or enter `issue-clarifying` / `blocked`.

## Rules

1. Start from exactly one existing GitHub or GitLab issue.
2. Never skip ahead of the current state.
3. Do not create implementation changes before `gcw-spec-check` reaches `ready-for-implementation`.
4. Do not publish a review request before `gcw-implement-check` reaches `ready-for-review`.
5. Do not run human review actions locally; human review happens on GitHub/GitLab and is recorded as platform events.
6. Preserve `feedback_source` when moving from `changes-requested` back into implementation.
7. Preserve `resume_phase` / `resume_step` when a step enters `blocked`.
8. Stop and report clearly when the workflow enters `planned`, `issue-clarifying`, `blocked`, `reviewing`, or `review-complete`.
9. At each milestone step completion (from `gcw-issue-triage` onward), publish a **new** Issue `<!-- gcw-progress -->` comment via `publish_progress_comment.py` with `--milestone-event` and `--milestone-payload-file` so the body matches the completing step **before** `record-*` appends the event; never edit an existing progress comment and never add a separate planning-links comment. Prefer `run_gcw_step.py` when available — it enforces publish-then-record ordering. Record `progress_comment_url` and the rendered `progress_comment_body_hash` on the completing event; `workflow.json` `refs.progress_comment_url` always points to the latest comment.
10. When a local agent completes `gcw-issue-triage`, the Issue and triage event must include `gcw:executor-local`; switch to `gcw:executor-hosted` only when handing the issue to hosted automation.

## Reporting

When a `/gcw` run stops, report only: steps executed, state before/after, key artifact or blocker, and next step or required human action.
