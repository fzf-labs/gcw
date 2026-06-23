#!/usr/bin/env python3
"""Classify and format GCW hosted workflow skip reasons."""

from __future__ import annotations

SKIP_GATE_NONE = "none"
SKIP_GATE_EXECUTOR = "executor"
SKIP_GATE_PHASE = "phase"
SKIP_GATE_IDEMPOTENT = "idempotent"
SKIP_GATE_INFRASTRUCTURE = "infrastructure"

GATE_LABELS = {
    SKIP_GATE_NONE: "none",
    SKIP_GATE_EXECUTOR: "executor gate",
    SKIP_GATE_PHASE: "phase gate",
    SKIP_GATE_IDEMPOTENT: "idempotent no-op",
    SKIP_GATE_INFRASTRUCTURE: "infrastructure",
}

GATE_HINTS = {
    SKIP_GATE_EXECUTOR: (
        "Check Issue labels: need gcw:executor-hosted and not gcw:executor-local. "
        "For GitLab CI, set GCW_EXECUTOR=gcw:executor-hosted."
    ),
    SKIP_GATE_PHASE: (
        "Check workflow.json phase and next_allowed_steps on the issue branch. "
        "Confirm the trigger label matches the current phase."
    ),
    SKIP_GATE_IDEMPOTENT: (
        "The step already completed or was superseded by a later milestone. "
        "Inspect .gcw/issues/<id>/events/ last_completed_step."
    ),
    SKIP_GATE_INFRASTRUCTURE: (
        "Checkout the issue branch and confirm .gcw/issues/<id>/ exists with workflow.json."
    ),
}


def classify_skip_gate(skip_reason: str) -> str:
    reason = skip_reason.strip()
    if not reason:
        return SKIP_GATE_NONE
    lower = reason.lower()
    if "gcw:executor" in lower or "missing gcw:executor-hosted" in lower or "blocks hosted execution" in lower:
        return SKIP_GATE_EXECUTOR
    if "already completed" in lower or lower.startswith("superseded by"):
        return SKIP_GATE_IDEMPOTENT
    if "phase " in lower and " is not in [" in lower:
        return SKIP_GATE_PHASE
    if "issue directory not found" in lower or "missing workflow projection" in lower:
        return SKIP_GATE_INFRASTRUCTURE
    return SKIP_GATE_INFRASTRUCTURE


def attach_skip_gate(result: dict) -> dict:
    enriched = dict(result)
    if enriched.get("should_run"):
        enriched["skip_gate"] = SKIP_GATE_NONE
    else:
        enriched["skip_gate"] = classify_skip_gate(str(enriched.get("skip_reason", "")))
    return enriched


def format_skip_summary(
    *,
    step: str,
    skip_gate: str,
    skip_reason: str,
    phase: str = "",
) -> str:
    gate = skip_gate.strip() or classify_skip_gate(skip_reason)
    lines = [
        f"GCW hosted skip: {step}",
        f"Gate: {GATE_LABELS.get(gate, gate)}",
    ]
    if phase.strip():
        lines.append(f"Phase: {phase.strip()}")
    if skip_reason.strip():
        lines.append(f"Reason: {skip_reason.strip()}")
    hint = GATE_HINTS.get(gate)
    if hint:
        lines.append(f"What to check: {hint}")
    return "\n".join(lines)
