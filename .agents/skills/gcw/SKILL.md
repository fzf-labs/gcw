---
name: gcw
description: Orchestrate the Git Collaboration Workflow from an existing GitHub or GitLab issue by routing through the eight `gcw-*` step skills. Use when the user invokes /gcw or asks to process an issue through GCW; stop at clarification, blockers, review feedback, or review completion.
---

# GCW

Top-level orchestrator for the Git Collaboration Workflow. Use this skill only to identify the current workflow state, choose the next `gcw-*` step skill, and run it. Each step skill owns its own inputs, procedure, state transition, and stop conditions.

## Contract

This skill is self-contained. It includes the GCW steps, states, Action roles, pipelines, and stop conditions. Do not read any external workflow document as the contract source before running GCW.

GCW starts from exactly one existing GitHub or GitLab issue. It does not start from implementation. The issue may be created by a human on the platform or by an agent before GCW starts. The GCW main flow intakes the issue, classifies it, clarifies it, and decides whether it is ready for development.

After the spec files stage starts, stable state is written to `.gcw/issues/<issue-id>/state.json` on the issue branch. Before that point, state may be carried by issue comments, labels, or agent context.

GCW has three collaborators:

- **Human**: makes key decisions and business judgments on GitHub or GitLab.
- **Agent**: Codex, Cursor, Claude Code, or similar AI coding tools; handles work requiring judgment and code capability, either locally or inside an Action.
- **Action**: GitHub Actions, GitLab CI, or another hosted pipeline; triggered by platform events and responsible for remote automation, gates, and records.

## State Discovery

Before routing, identify the current workflow state in this order:

1. If `.gcw/issues/<issue-id>/state.json` exists on the issue branch or current worktree, treat it as the authoritative state source.
2. If spec files do not exist yet, infer state from issue comments, labels, and the current conversation or handoff context.
3. If a PR/MR exists, inspect platform metadata and review/check results to distinguish `reviewing`, `changes-requested`, and `review-complete`.
4. If state is ambiguous or sources conflict, stop and ask the user to resolve the state before running a step.

## Steps

1. `gcw-issue-intake`
2. `gcw-issue-prepare`
3. `gcw-issue-to-spec`
4. `gcw-spec-check`
5. `gcw-implement`
6. `gcw-implement-check`
7. `gcw-pr-publish`
8. `gcw-pr-review`

Main flow:

```text
Existing Issue
  -> gcw-issue-intake
  -> gcw-issue-prepare
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
| `gcw-issue-intake` | none | Intake an existing issue, record its URL, number, and initial context, and initialize GCW state. | Human / agent | Not needed. Issue intake is initiated by a human or agent, not by a hosted pipeline. | `issue-opened` |
| `gcw-issue-prepare` | `gcw-issue-prepare.yml` | Classify the issue, collect discussion, and check whether the information is sufficient for spec writing. | Human / agent / Action | Needed. Collect context, run agent classification, organize clarification questions, and record discussion and state. It must not replace key business judgment. | `ready-for-planning` or `issue-clarifying` |
| `gcw-issue-to-spec` | `gcw-issue-to-spec.yml` | Create an isolated worktree, generate spec files from the issue, commit and push them, and link them from an issue comment. | Agent / Action | Recommended. Run an agent to generate the spec, or receive local agent output and complete push plus issue comment. | `planned` |
| `gcw-spec-check` | `gcw-spec-check.yml` | Check that spec files were generated and pushed, the issue comment links them, and the content is sufficient for implementation. | Agent / Action | Should exist. This is the remote gate before implementation. | `ready-for-implementation`, `issue-clarifying`, or `blocked` |
| `gcw-implement` | `gcw-implement.yml` | Modify code according to the plan, add tests, and update necessary documentation. | Agent / Action | Optional. Run an agent inside a runner, or record handoff from a local agent through repo / issue / PR artifacts. | `implementing` |
| `gcw-implement-check` | `gcw-implement-check.yml` | Before creating a review request, check diff boundaries, commits, risks, validation results, and spec files; generate or verify readiness evidence. | Agent / Action | Should exist. This is the remote gate before creating or updating a review request. | `ready-for-review` |
| `gcw-pr-publish` | `gcw-pr-publish.yml` | Idempotently create or update the PR/MR with summary, issue link, validation results, and risk notes. | Agent / Action | Recommended. Handles PR/MR creation or update, issue link, and summary publishing. | `reviewing` |
| `gcw-pr-review` | `gcw-pr-review.yml` | Trigger CI, static checks, remote artifact verification, optional AI review, and summarize PR review results. | Action | Required. The hosted Action owns the automatic review gate; a local agent may summarize existing remote checks and review evidence, but must not replace the gate. | `reviewing`, `changes-requested`, or `blocked` |

Human review and `review-complete` are not main workflow steps. They happen on GitHub or GitLab and are produced by reviewers, merge policy, or platform events.

## State Routing

| Current state | Next step |
| --- | --- |
| Existing Issue outside GCW | `gcw-issue-intake` |
| `issue-opened` | `gcw-issue-prepare` |
| `issue-clarifying` | Stop until the missing answer is available, then run `gcw-issue-prepare` |
| `ready-for-planning` | `gcw-issue-to-spec` |
| `planned` | `gcw-spec-check` |
| `ready-for-implementation` | `gcw-implement` |
| `implementing` | `gcw-implement` or `gcw-implement-check`, depending on whether implementation work is still needed |
| `ready-for-review` | `gcw-pr-publish` |
| `reviewing` | Run `gcw-pr-review` for automatic review; platform human review remains external |
| `changes-requested` | Run `gcw-implement` with `feedback_source` metadata preserved |
| `blocked` | Stop until the blocker is resolved, then resume from `resume_state` / `resume_step` |
| `review-complete` | Stop; the workflow is closed |

`reviewing` only means the review request has entered review. After automatic PR review passes, the state remains `reviewing` until a platform human-review event produces `review-complete` or `changes-requested`. When entering `changes-requested`, distinguish the feedback source in metadata, for example `feedback_source: pr-review` or `feedback_source: human-review`.

`gcw-block` and `gcw-clarify` are not main steps; they are feedback-loop actions. `gcw-block` can move any non-terminal state to `blocked` and must record `resume_state` / `resume_step` in metadata. After the blocker is resolved, resume from that point. `gcw-clarify` can move any stage needing more issue information to `issue-clarifying`.

Initial implementation and feedback fixes both finish through `gcw-implement` -> `gcw-implement-check` -> `gcw-pr-publish` -> `gcw-pr-review`. Feedback fixes differ only because they start from `changes-requested`, return to `implementing`, and then repeat the same closing chain. `gcw-pr-publish` must be idempotent: both first-time review request creation and later updates go through it.

## Action Pipelines

Main steps are the smallest workflow units. Except for `gcw-issue-intake`, main steps that need an Action should have a same-named workflow file. An Action pipeline may group consecutive main steps into one automation entrypoint; this only changes orchestration granularity and does not change main-step state semantics.

| Pipeline | Included steps | Human role | Agent role | Action role | Output state |
| --- | --- | --- | --- | --- | --- |
| Intake and preparation | `gcw-issue-intake`, `gcw-issue-prepare` | Create or confirm the issue and answer key business questions. | Intake, classify, draft discussion, and check readiness. | Does not run `gcw-issue-intake`; in preparation, collects context, runs agent classification, organizes clarification questions, and records discussion plus state. | `ready-for-planning` or `issue-clarifying` |
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
7. Preserve `resume_state` / `resume_step` when a step enters `blocked`.
8. Stop and report clearly when the workflow enters `issue-clarifying`, `blocked`, or `review-complete`.

## Reporting

After each step, report only: step executed, state before/after, key artifact or blocker, and next step.
