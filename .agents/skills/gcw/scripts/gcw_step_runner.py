from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gcw_step_adapters import (
    DryRunAdapter,
    PlatformAdapter,
    render_progress_artifacts,
    render_review_request_artifacts,
)
from gcw_workflow_lib import (
    PLANNING_FILES,
    WorkflowError,
    assert_projection_current,
    find_latest_event,
    load_projection,
)
from manage_gcw_workflow import (
    record_implement_check,
    record_issue_prepare,
    record_issue_to_spec,
    record_pr_publish,
    record_pr_review,
    record_spec_check,
)
from validate_gcw_evidence import (
    implement_check_errors,
    pr_publish_errors,
    workflow_errors,
)

SUPPORTED_STEPS = (
    "gcw-issue-prepare",
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
        validation, artifacts, stop_reason = handler.validate_and_render(issue_dir, options)
        if stop_reason:
            return StepResult(
                ok=False,
                step=step,
                phase_before=phase_before,
                phase_after=phase_before,
                artifacts=artifacts,
                validation=validation,
                stop_reason=stop_reason,
            )

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
            progress_url = handler.publish(self.adapter, issue_dir, artifacts, options)
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
            handler.record(issue_dir, progress_url, options)
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

    def validate_and_render(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
        raise NotImplementedError

    def publish(
        self,
        adapter: PlatformAdapter,
        issue_dir: Path,
        artifacts: dict[str, Any],
        options: dict[str, Any],
    ) -> str:
        result = adapter.publish_progress_comment(issue_dir, dry_run=False)
        if not result.get("ok"):
            raise WorkflowError("progress comment publication failed")
        url = str(result.get("progress_comment_url", "")).strip()
        if not url:
            raise WorkflowError("progress comment publication did not return a URL")
        return url

    def record(self, issue_dir: Path, progress_url: str, options: dict[str, Any]) -> None:
        raise NotImplementedError


class _PrepareStepHandler(_StepHandler):
    step = "gcw-issue-prepare"

    def validate_and_render(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
        gate_file = options.get("gate_file")
        if not gate_file:
            return [], {}, "blocked"
        gate_path = Path(str(gate_file))
        if not gate_path.is_file():
            return [], {}, "blocked"
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        validation = [_run_validation("prepare_gate", [] if gate.get("ok") else gate.get("errors", ["gate failed"]))]
        if not gate.get("ok"):
            return validation, {"gate": gate}, "clarifying" if options.get("ready") is False else "validation_failed"
        artifacts = render_progress_artifacts(issue_dir)
        artifacts["gate"] = gate
        return validation, artifacts, None

    def record(self, issue_dir: Path, progress_url: str, options: dict[str, Any]) -> None:
        gate_file = Path(str(options["gate_file"]))
        args = _namespace(
            issue_dir,
            ready=bool(options.get("ready")),
            gate_file=gate_file,
            progress_comment_url=progress_url,
            question=options.get("question", ""),
            summary=options.get("summary", ""),
            classification_type=options.get("classification_type", ""),
            classification_area=options.get("classification_area", ""),
            classification_priority=options.get("classification_priority", ""),
            labels_applied=options.get("labels_applied", ""),
            remote_sync_file=Path(str(options["remote_sync_file"])) if options.get("remote_sync_file") else "",
        )
        record_issue_prepare(args)


class _ToSpecStepHandler(_StepHandler):
    step = "gcw-issue-to-spec"

    def validate_and_render(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
        errors = workflow_errors(issue_dir)
        missing = [name for name in PLANNING_FILES if not (issue_dir / name).is_file()]
        errors.extend(f"missing planning file: {name}" for name in missing)
        validation = [_run_validation("workflow + planning_files", errors)]
        if errors:
            return validation, {}, "validation_failed"
        shas = _planning_shas(issue_dir)
        artifacts = {**render_progress_artifacts(issue_dir), "spec_refs": shas}
        if options.get("planning_commit_pushed") is False:
            return validation, artifacts, "validation_failed"
        return validation, artifacts, None

    def record(self, issue_dir: Path, progress_url: str, options: dict[str, Any]) -> None:
        shas = _planning_shas(issue_dir)
        record_issue_to_spec(
            _namespace(
                issue_dir,
                planning_commit_pushed=bool(options.get("planning_commit_pushed", True)),
                progress_comment_url=progress_url,
                task_plan_sha=shas["task_plan_sha"],
                findings_sha=shas["findings_sha"],
                progress_sha=shas["progress_sha"],
            )
        )


class _SpecCheckStepHandler(_StepHandler):
    step = "gcw-spec-check"

    def validate_and_render(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
        errors = workflow_errors(issue_dir)
        missing = [name for name in PLANNING_FILES if not (issue_dir / name).is_file()]
        errors.extend(f"missing planning file: {name}" for name in missing)
        errors.extend(_verify_spec_refs_from_to_spec(issue_dir))
        validation = [_run_validation("pre-spec-check", errors)]
        if errors:
            return validation, render_progress_artifacts(issue_dir), "validation_failed"
        result = options.get("result", "passed")
        if result not in ("passed", "clarifying", "blocked"):
            return validation, {}, "validation_failed"
        return validation, render_progress_artifacts(issue_dir), None

    def record(self, issue_dir: Path, progress_url: str, options: dict[str, Any]) -> None:
        record_spec_check(
            _namespace(
                issue_dir,
                result=str(options.get("result", "passed")),
                progress_comment_url=progress_url,
                question=options.get("question", ""),
                reason=options.get("reason", ""),
            )
        )


class _ImplementCheckStepHandler(_StepHandler):
    step = "gcw-implement-check"

    def validate_and_render(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
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
            return validation, {}, "validation_failed"
        return validation, render_progress_artifacts(issue_dir), None

    def record(self, issue_dir: Path, progress_url: str, options: dict[str, Any]) -> None:
        record_implement_check(
            _namespace(
                issue_dir,
                payload_file=Path(str(options["payload_file"])),
                progress_comment_url=progress_url,
            )
        )


class _PrPublishStepHandler(_StepHandler):
    step = "gcw-pr-publish"

    def validate_and_render(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
        errors = implement_check_errors(issue_dir)
        validation = [_run_validation("implement-check evidence", errors)]
        if errors:
            return validation, {}, "validation_failed"
        artifacts = render_review_request_artifacts(issue_dir)
        review_url = str(options.get("review_request_url", "")).strip()
        if not review_url:
            errors = ["review_request_url is required in options"]
            return [_run_validation("pr-publish options", errors)], artifacts, "validation_failed"
        artifacts["review_request_url"] = review_url
        return validation, artifacts, None

    def publish(
        self,
        adapter: PlatformAdapter,
        issue_dir: Path,
        artifacts: dict[str, Any],
        options: dict[str, Any],
    ) -> str:
        progress_url = super().publish(adapter, issue_dir, artifacts, options)
        return progress_url

    def record(self, issue_dir: Path, progress_url: str, options: dict[str, Any]) -> None:
        body_hash_value = str(options.get("body_hash", "")).strip()
        if not body_hash_value:
            body_hash_value = render_review_request_artifacts(issue_dir)["review_request_body_hash"]
        record_pr_publish(
            _namespace(
                issue_dir,
                review_request_url=str(options["review_request_url"]),
                progress_comment_url=progress_url,
                body_hash=body_hash_value,
                target=str(options.get("target", "github_pr")),
                rendered_from_event_id=str(options.get("rendered_from_event_id", "")),
                effect_kind=str(options.get("effect_kind", "github_pr_upsert")),
                operation_id=str(options.get("operation_id", "gcw-pr-publish")),
                remote_updated_at=str(options.get("remote_updated_at", "")),
            )
        )


class _PrReviewStepHandler(_StepHandler):
    step = "gcw-pr-review"

    def validate_and_render(self, issue_dir: Path, options: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
        errors = pr_publish_errors(issue_dir)
        result = options.get("result", "passed")
        if result not in ("passed", "changes-requested", "blocked"):
            errors.append("result must be passed, changes-requested, or blocked")
        validation = [_run_validation("pre-pr-review", errors)]
        if errors:
            return validation, render_progress_artifacts(issue_dir), "validation_failed"
        return validation, render_progress_artifacts(issue_dir), None

    def record(self, issue_dir: Path, progress_url: str, options: dict[str, Any]) -> None:
        record_pr_review(
            _namespace(
                issue_dir,
                result=str(options.get("result", "passed")),
                progress_comment_url=progress_url,
                feedback_source=str(options.get("feedback_source", "pr-review")),
                reason=str(options.get("reason", "")),
            )
        )


_STEP_HANDLERS: dict[str, _StepHandler] = {
    handler.step: handler()
    for handler in (
        _PrepareStepHandler,
        _ToSpecStepHandler,
        _SpecCheckStepHandler,
        _ImplementCheckStepHandler,
        _PrPublishStepHandler,
        _PrReviewStepHandler,
    )
}
