from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from base import (
    DryRunAdapter,
    PlatformAdapter,
    render_milestone_progress_artifacts,
    render_review_request_artifacts,
)
from gcw_workflow_contracts import PLANNING_FILES
from gcw_workflow_lib import (
    WorkflowError,
    assert_projection_current,
    find_latest_event,
    load_projection,
)
from gcw_workflow_commands import (
    record_implement_check,
    record_issue_clarify,
    record_issue_triage,
    record_issue_to_spec,
    record_pr_publish,
    record_pr_review,
    record_spec_check,
)
from gcw_evidence import (
    implement_check_errors,
    pr_publish_errors,
    workflow_errors,
)

SUPPORTED_STEPS = (
    "gcw-issue-triage",
    "gcw-issue-clarify",
    "gcw-issue-to-spec",
    "gcw-spec-check",
    "gcw-implement-check",
    "gcw-pr-publish",
    "gcw-pr-review",
)


@dataclass
class StepResult:
    ok: bool
    step: str
    phase_before: str
    phase_after: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    validation: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validation_entry(command: str, exit_code: int, *, result: str, errors: list[str] | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "command": command,
        "exit_code": exit_code,
        "result": result,
    }
    if errors:
        entry["errors"] = errors
    return entry


def _file_sha(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _planning_shas(issue_dir: Path) -> dict[str, str]:
    return {
        "task_plan_sha": _file_sha(issue_dir / "task_plan.md"),
        "findings_sha": _file_sha(issue_dir / "findings.md"),
        "progress_sha": _file_sha(issue_dir / "progress.md"),
    }


def _verify_spec_refs_from_to_spec(issue_dir: Path) -> list[str]:
    errors: list[str] = []
    to_spec = find_latest_event(issue_dir, "gcw-issue-to-spec")
    if to_spec is None:
        errors.append("no gcw-issue-to-spec event found")
        return errors
    payload = to_spec.get("payload") if isinstance(to_spec.get("payload"), dict) else {}
    spec_refs = payload.get("spec_refs")
    if not isinstance(spec_refs, dict):
        errors.append("gcw-issue-to-spec payload.spec_refs must be an object")
        return errors
    sha_map = {
        "task_plan_sha": "task_plan.md",
        "findings_sha": "findings.md",
        "progress_sha": "progress.md",
    }
    for sha_key, filename in sha_map.items():
        expected = spec_refs.get(sha_key)
        file_path = issue_dir / filename
        if not file_path.is_file():
            errors.append(f"missing planning file: {filename}")
            continue
        if not expected or not str(expected).startswith("sha256:"):
            errors.append(f"{sha_key} is required")
            continue
        actual = _file_sha(file_path)
        if actual != expected:
            errors.append(f"{sha_key} does not match actual {filename} content")
    return errors


def _run_validation(command: str, errors: list[str]) -> dict[str, Any]:
    return _validation_entry(
        command,
        0 if not errors else 1,
        result="passed" if not errors else "failed",
        errors=errors or None,
    )


def _namespace(issue_dir: Path, **kwargs: Any) -> argparse.Namespace:
    base = {
        "issue_dir": issue_dir,
        "actor_kind": "local",
        "actor_id": "cursor-session",
        "expected_last_seq": None,
        "parent_projection_hash": "",
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


class GcwStepRunner:
    def __init__(self, adapter: PlatformAdapter | None = None) -> None:
        self.adapter = adapter or DryRunAdapter()

    def run(self, step: str, issue_dir: Path, *, dry_run: bool = False, options: dict[str, Any] | None = None) -> StepResult:
        if step not in SUPPORTED_STEPS:
            raise WorkflowError(f"unsupported step: {step}")

        options = options or {}
        current = assert_projection_current(issue_dir)
        if not current["ok"]:
            return StepResult(
                ok=False,
                step=step,
                phase_before="",
                phase_after="",
                validation=[_run_validation("assert_projection_current", current["errors"])],
                stop_reason="blocked",
            )

        projection = current["projection"]
        phase_before = str(projection.get("phase", ""))
        allowed = projection.get("next_allowed_steps") or []
        if step not in allowed:
            return StepResult(
                ok=False,
                step=step,
                phase_before=phase_before,
                phase_after=phase_before,
                validation=[
                    _run_validation(
                        "phase_routing",
                        [f"step {step} not in next_allowed_steps {allowed}"],
                    )
                ],
                stop_reason="illegal_phase",
            )

        handler = _STEP_HANDLERS[step]
        validation, stop_reason = handler.validate(issue_dir, options)
        if stop_reason:
            return StepResult(
                ok=False,
                step=step,
                phase_before=phase_before,
                phase_after=phase_before,
                artifacts={},
                validation=validation,
                stop_reason=stop_reason,
            )

        try:
            milestone_payload = handler.milestone_payload(issue_dir, options)
        except WorkflowError as exc:
            return StepResult(
                ok=False,
                step=step,
                phase_before=phase_before,
                phase_after=phase_before,
                artifacts={},
                validation=validation + [_run_validation("milestone_payload", [str(exc)])],
                stop_reason="blocked",
            )

        artifacts = render_milestone_progress_artifacts(issue_dir, step, milestone_payload)
        artifacts.update(handler.extra_artifacts(issue_dir, options))

        if dry_run:
            return StepResult(
                ok=True,
                step=step,
                phase_before=phase_before,
                phase_after=phase_before,
                artifacts=artifacts,
                validation=validation,
                stop_reason=None,
            )

        try:
            result = self.adapter.publish_milestone_progress(
                issue_dir,
                step,
                milestone_payload,
                dry_run=False,
            )
            if not result.get("ok"):
                raise WorkflowError("progress comment publication failed")
            progress_url = str(result.get("progress_comment_url", "")).strip()
            if not progress_url:
                raise WorkflowError("progress comment publication did not return a URL")
        except WorkflowError:
            return StepResult(
                ok=False,
                step=step,
                phase_before=phase_before,
                phase_after=phase_before,
                artifacts=artifacts,
                validation=validation,
                stop_reason="publication_failed",
            )

        try:
            handler.record(issue_dir, progress_url, options, milestone_payload)
        except WorkflowError as exc:
            return StepResult(
                ok=False,
                step=step,
                phase_before=phase_before,
                phase_after=phase_before,
                artifacts=artifacts,
                validation=validation + [_run_validation("record_event", [str(exc)])],
                stop_reason="blocked",
            )

        updated = load_projection(issue_dir)["projection"]
        phase_after = str(updated.get("phase", phase_before))
        return StepResult(
            ok=True,
            step=step,
            phase_before=phase_before,
            phase_after=phase_after,
            artifacts={**artifacts, "progress_comment_url": progress_url},
            validation=validation,
            stop_reason=None,
        )


class _StepHandler:
    step: str = ""

    def validate(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        raise NotImplementedError

    def milestone_payload(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def extra_artifacts(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        return {}

    def record(
        self,
        issue_dir: Path,
        progress_url: str,
        options: dict[str, Any],
        milestone_payload: dict[str, Any],
    ) -> None:
        raise NotImplementedError


class _TriageStepHandler(_StepHandler):
    step = "gcw-issue-triage"

    def validate(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        remote_sync_file = options.get("remote_sync_file")
        if not remote_sync_file:
            return [], "blocked"
        remote_sync_path = Path(str(remote_sync_file))
        if not remote_sync_path.is_file():
            return [], "blocked"
        missing = [
            key
            for key in ("classification_type", "classification_priority", "labels_applied")
            if not options.get(key)
        ]
        validation = [_run_validation("triage_metadata", missing)]
        if missing:
            return validation, "validation_failed"
        return validation, None

    def milestone_payload(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if options.get("summary"):
            payload["summary"] = options["summary"]
        classification: dict[str, Any] = {}
        if options.get("classification_type"):
            classification["type"] = options["classification_type"]
        if options.get("classification_area"):
            classification["area"] = options["classification_area"]
        if options.get("classification_priority"):
            classification["priority"] = options["classification_priority"]
        if classification:
            payload["classification"] = classification
        labels = options.get("labels_applied")
        if labels:
            payload["labels_applied"] = labels if isinstance(labels, list) else [x.strip() for x in str(labels).split(",") if x.strip()]
        remote_sync_file = options.get("remote_sync_file")
        if remote_sync_file and Path(str(remote_sync_file)).is_file():
            remote_sync = json.loads(Path(str(remote_sync_file)).read_text(encoding="utf-8"))
            if isinstance(remote_sync.get("remote_sync"), dict):
                payload["remote_sync"] = remote_sync["remote_sync"]
            elif isinstance(remote_sync, dict) and remote_sync.get("platform"):
                payload["remote_sync"] = remote_sync
        return payload

    def record(
        self,
        issue_dir: Path,
        progress_url: str,
        options: dict[str, Any],
        milestone_payload: dict[str, Any],
    ) -> None:
        args = _namespace(
            issue_dir,
            progress_comment_url=progress_url,
            summary=str(options.get("summary", "")),
            classification_type=str(milestone_payload.get("classification", {}).get("type", "")),
            classification_area=str(milestone_payload.get("classification", {}).get("area", "")),
            classification_priority=str(milestone_payload.get("classification", {}).get("priority", "")),
            labels_applied=",".join(milestone_payload.get("labels_applied", [])),
            remote_sync_file=Path(str(options["remote_sync_file"])) if options.get("remote_sync_file") else "",
        )
        record_issue_triage(args)


class _ClarifyStepHandler(_StepHandler):
    step = "gcw-issue-clarify"

    def validate(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        gate_file = options.get("gate_file")
        if not gate_file:
            return [], "blocked"
        gate_path = Path(str(gate_file))
        if not gate_path.is_file():
            return [], "blocked"
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        validation = [_run_validation("clarify_gate", [] if gate.get("ok") else gate.get("errors", ["gate failed"]))]
        return validation, None

    def milestone_payload(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        gate_path = Path(str(options["gate_file"]))
        if not gate_path.is_file():
            raise WorkflowError("gate_file does not exist")
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        ready = bool(gate.get("ok")) if options.get("ready") is None else bool(options.get("ready"))
        payload: dict[str, Any] = {"ready": ready, "gate": gate}
        if options.get("summary"):
            payload["summary"] = options["summary"]
        if options.get("question"):
            payload["question"] = options["question"]
        elif not ready:
            payload["question"] = "Please update the issue so GCW can continue."
        return payload

    def record(
        self,
        issue_dir: Path,
        progress_url: str,
        options: dict[str, Any],
        milestone_payload: dict[str, Any],
    ) -> None:
        record_issue_clarify(
            _namespace(
                issue_dir,
                ready=bool(milestone_payload.get("ready")),
                gate_file=Path(str(options["gate_file"])),
                progress_comment_url=progress_url,
                question=str(milestone_payload.get("question", "")),
                summary=str(options.get("summary", "")),
            )
        )


class _ToSpecStepHandler(_StepHandler):
    step = "gcw-issue-to-spec"

    def validate(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        errors = workflow_errors(issue_dir)
        missing = [name for name in PLANNING_FILES if not (issue_dir / name).is_file()]
        errors.extend(f"missing planning file: {name}" for name in missing)
        validation = [_run_validation("workflow + planning_files", errors)]
        if errors:
            return validation, "validation_failed"
        if options.get("planning_commit_pushed") is False:
            return validation, "validation_failed"
        return validation, None

    def milestone_payload(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        shas = _planning_shas(issue_dir)
        return {
            "planning_commit_pushed": bool(options.get("planning_commit_pushed", True)),
            "spec_refs": shas,
        }

    def extra_artifacts(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        return {"spec_refs": _planning_shas(issue_dir)}

    def record(
        self,
        issue_dir: Path,
        progress_url: str,
        options: dict[str, Any],
        milestone_payload: dict[str, Any],
    ) -> None:
        shas = milestone_payload["spec_refs"]
        record_issue_to_spec(
            _namespace(
                issue_dir,
                planning_commit_pushed=bool(milestone_payload.get("planning_commit_pushed", True)),
                progress_comment_url=progress_url,
                task_plan_sha=shas["task_plan_sha"],
                findings_sha=shas["findings_sha"],
                progress_sha=shas["progress_sha"],
            )
        )


class _SpecCheckStepHandler(_StepHandler):
    step = "gcw-spec-check"

    def validate(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        errors = workflow_errors(issue_dir)
        missing = [name for name in PLANNING_FILES if not (issue_dir / name).is_file()]
        errors.extend(f"missing planning file: {name}" for name in missing)
        errors.extend(_verify_spec_refs_from_to_spec(issue_dir))
        validation = [_run_validation("pre-spec-check", errors)]
        if errors:
            return validation, "validation_failed"
        result = options.get("result", "passed")
        if result not in ("passed", "clarifying", "blocked"):
            return validation, "validation_failed"
        return validation, None

    def milestone_payload(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        result = str(options.get("result", "passed"))
        ok = result == "passed"
        payload: dict[str, Any] = {
            "result": result,
            "gate": {
                "ok": ok,
                "checks": [],
                "errors": [] if ok else [str(options.get("reason") or options.get("question") or "spec-check failed")],
            },
        }
        if options.get("question"):
            payload["question"] = options["question"]
        if options.get("reason"):
            payload["reason"] = options["reason"]
        return payload

    def record(
        self,
        issue_dir: Path,
        progress_url: str,
        options: dict[str, Any],
        milestone_payload: dict[str, Any],
    ) -> None:
        record_spec_check(
            _namespace(
                issue_dir,
                result=str(milestone_payload.get("result", "passed")),
                progress_comment_url=progress_url,
                question=str(milestone_payload.get("question", "")),
                reason=str(milestone_payload.get("reason", "")),
            )
        )


class _ImplementCheckStepHandler(_StepHandler):
    step = "gcw-implement-check"

    def validate(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        errors = workflow_errors(issue_dir)
        payload_file = options.get("payload_file")
        if not payload_file:
            errors.append("payload_file is required")
        elif not Path(str(payload_file)).is_file():
            errors.append("payload_file does not exist")
        else:
            payload = json.loads(Path(str(payload_file)).read_text(encoding="utf-8"))
            gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
            if gate.get("ok") is not True:
                errors.append("implement-check payload gate.ok must be true")
        validation = [_run_validation("pre-implement-check", errors)]
        if errors:
            return validation, "validation_failed"
        return validation, None

    def milestone_payload(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        payload_file = Path(str(options["payload_file"]))
        payload = json.loads(payload_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise WorkflowError("implement-check payload must be a JSON object")
        return payload

    def record(
        self,
        issue_dir: Path,
        progress_url: str,
        options: dict[str, Any],
        milestone_payload: dict[str, Any],
    ) -> None:
        record_implement_check(
            _namespace(
                issue_dir,
                payload_file=Path(str(options["payload_file"])),
                progress_comment_url=progress_url,
            )
        )


class _PrPublishStepHandler(_StepHandler):
    step = "gcw-pr-publish"

    def validate(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        errors = implement_check_errors(issue_dir)
        validation = [_run_validation("implement-check evidence", errors)]
        if errors:
            return validation, "validation_failed"
        if not str(options.get("review_request_url", "")).strip():
            return [_run_validation("pr-publish options", ["review_request_url is required in options"])], "validation_failed"
        return validation, None

    def milestone_payload(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        review_url = str(options["review_request_url"]).strip()
        body_hash_value = str(options.get("body_hash", "")).strip()
        if not body_hash_value:
            body_hash_value = render_review_request_artifacts(issue_dir)["review_request_body_hash"]
        return {
            "review_request_url": review_url,
            "body_hash": body_hash_value,
            "effects": [
                {
                    "kind": str(options.get("effect_kind", "github_pr_upsert")),
                    "operation_id": str(options.get("operation_id", "gcw-pr-publish")),
                    "target": str(options.get("target", "github_pr")),
                    "body_hash": body_hash_value,
                    "remote_updated_at": str(options.get("remote_updated_at", "")),
                    "status": "applied",
                }
            ],
        }

    def extra_artifacts(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        artifacts = render_review_request_artifacts(issue_dir)
        artifacts["review_request_url"] = str(options.get("review_request_url", "")).strip()
        return artifacts

    def record(
        self,
        issue_dir: Path,
        progress_url: str,
        options: dict[str, Any],
        milestone_payload: dict[str, Any],
    ) -> None:
        record_pr_publish(
            _namespace(
                issue_dir,
                review_request_url=str(milestone_payload["review_request_url"]),
                progress_comment_url=progress_url,
                body_hash=str(milestone_payload["body_hash"]),
                target=str(milestone_payload["effects"][0].get("target", "github_pr")),
                rendered_from_event_id=str(options.get("rendered_from_event_id", "")),
                effect_kind=str(milestone_payload["effects"][0].get("kind", "github_pr_upsert")),
                operation_id=str(milestone_payload["effects"][0].get("operation_id", "gcw-pr-publish")),
                remote_updated_at=str(milestone_payload["effects"][0].get("remote_updated_at", "")),
            )
        )


class _PrReviewStepHandler(_StepHandler):
    step = "gcw-pr-review"

    def validate(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        errors = pr_publish_errors(issue_dir)
        result = options.get("result", "passed")
        if result not in ("passed", "changes-requested", "blocked"):
            errors.append("result must be passed, changes-requested, or blocked")
        validation = [_run_validation("pre-pr-review", errors)]
        if errors:
            return validation, "validation_failed"
        return validation, None

    def milestone_payload(self, issue_dir: Path, options: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "result": str(options.get("result", "passed")),
            "feedback_source": str(options.get("feedback_source", "pr-review")),
        }
        reason = str(options.get("reason", "")).strip()
        if reason:
            payload["reason"] = reason
            payload["block_reason"] = reason
        return payload

    def record(
        self,
        issue_dir: Path,
        progress_url: str,
        options: dict[str, Any],
        milestone_payload: dict[str, Any],
    ) -> None:
        record_pr_review(
            _namespace(
                issue_dir,
                result=str(milestone_payload.get("result", "passed")),
                progress_comment_url=progress_url,
                feedback_source=str(milestone_payload.get("feedback_source", "pr-review")),
                reason=str(milestone_payload.get("reason", "")),
            )
        )


_STEP_HANDLERS: dict[str, _StepHandler] = {
    handler.step: handler()
    for handler in (
        _TriageStepHandler,
        _ClarifyStepHandler,
        _ToSpecStepHandler,
        _SpecCheckStepHandler,
        _ImplementCheckStepHandler,
        _PrPublishStepHandler,
        _PrReviewStepHandler,
    )
}
