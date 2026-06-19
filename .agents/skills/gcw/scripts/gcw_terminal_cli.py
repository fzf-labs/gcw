#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _bootstrap import add_repo_root

add_repo_root()

from gcw_artifacts import render_review_request
from gcw_terminal_workflow import human_handoff_reason, select_next_run_step, should_stop_for_human_handoff
from gcw_workflow_commands import init_workflow, record_implement, rebuild_projection
from gcw_workflow_contracts import PLANNING_FILES
from gcw_workflow_errors import WorkflowError
from gcw_workflow_lib import assert_projection_current, load_projection, validate_event_log
from progress import publish_milestone_progress_comment
from run_gcw_step import run_step as run_single_step

REPO_ROOT = next(
    candidate
    for candidate in Path(__file__).resolve().parents
    if (candidate / ".gcw" / "engine" / "runtime" / "gcw_workflow_contracts.py").is_file()
)


def emit(result: dict[str, Any]) -> int:
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{path.name} is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise WorkflowError(f"{path.name} must contain a JSON object")
    return data


def write_json_temp(prefix: str, data: dict[str, Any]) -> Path:
    directory = Path(tempfile.mkdtemp(prefix=prefix))
    path = directory / "payload.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_json_command(command: str, args: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    result = subprocess.run(
        [command, *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        data = json.loads(result.stdout or "")
    except json.JSONDecodeError:
        data = None
    if result.returncode != 0 or (isinstance(data, dict) and data.get("ok") is False):
        errors = data.get("errors", []) if isinstance(data, dict) else []
        message = "; ".join(str(item) for item in errors) if errors else (result.stderr or result.stdout or f"{command} failed").strip()
        raise WorkflowError(message)
    if not isinstance(data, dict):
        raise WorkflowError(f"failed to parse JSON output from {command}")
    return data


def issue_dir_for_target(target_root: Path, issue: str | int) -> Path:
    return target_root / ".gcw" / "issues" / str(issue)


def issue_number_as_string(issue: str | int) -> str:
    return str(issue).strip()


def issue_branch_name(issue: str | int) -> str:
    return f"gcw/issue-{issue_number_as_string(issue)}"


def parse_issue_args(args: list[str], command_name: str) -> tuple[Path, str]:
    target = Path.cwd()
    issue = ""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--target":
            if i + 1 >= len(args):
                raise WorkflowError("--target requires a path")
            target = Path(args[i + 1])
            i += 2
            continue
        if not issue:
            issue = arg
        else:
            raise WorkflowError(f"unknown {command_name} option: {arg}")
        i += 1
    if not issue:
        raise WorkflowError(f"{command_name} requires an issue number")
    return target, issue


def parse_step_args(args: list[str]) -> tuple[Path, str, str]:
    target = Path.cwd()
    step = ""
    issue = ""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--target":
            if i + 1 >= len(args):
                raise WorkflowError("--target requires a path")
            target = Path(args[i + 1])
            i += 2
            continue
        if not step:
            step = arg
        elif not issue:
            issue = arg
        else:
            raise WorkflowError(f"unknown step option: {arg}")
        i += 1
    if not step:
        raise WorkflowError("step requires a step name")
    if not issue:
        raise WorkflowError("step requires an issue number")
    return target, step, issue


def parse_remote_repository(remote_url: str) -> tuple[str, str]:
    normalized = remote_url.strip()
    if not normalized:
        raise WorkflowError("git remote origin is required")
    host = ""
    repository = ""
    if normalized.startswith("git@"):
        match = re.match(r"^git@([^:]+):(.+?)(?:\.git)?$", normalized)
        if not match:
            raise WorkflowError(f"unsupported git remote url: {normalized}")
        host = match.group(1)
        repository = match.group(2)
    else:
        from urllib.parse import urlparse

        parsed = urlparse(normalized)
        host = parsed.hostname or ""
        repository = parsed.path.lstrip("/").removesuffix(".git")
    if not repository:
        raise WorkflowError(f"could not resolve repository from remote url: {normalized}")
    platform = "gitlab" if "gitlab" in host else "github"
    return platform, repository


def git_command(target_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", "-C", str(target_root), *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise WorkflowError((result.stderr or result.stdout or f"git {' '.join(args)}").strip())
    return result


def read_git_remote(target_root: Path) -> str:
    result = subprocess.run(["git", "-C", str(target_root), "remote", "get-url", "origin"], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise WorkflowError((result.stderr or result.stdout or "git remote get-url origin failed").strip())
    return result.stdout.strip()


def detect_branch(target_root: Path, issue_number: str) -> str:
    branch = issue_branch_name(issue_number)
    result = subprocess.run(
        ["git", "-C", str(target_root), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        git_command(target_root, ["switch", branch])
        return branch
    git_command(target_root, ["switch", "-c", branch])
    return branch


def command_ok(command: str, args: list[str]) -> bool:
    return subprocess.run([command, *args], text=True, capture_output=True, check=False).returncode == 0


def git_changed_paths(target_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(target_root), "status", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) >= 4:
            path_text = line[3:].strip().replace("\\", "/")
            if path_text:
                paths.append(path_text)
    return paths


def fetch_issue_metadata(target_root: Path, platform: str, repository: str, issue_number: str) -> dict[str, Any]:
    if platform == "gitlab":
        return run_json_command("glab", ["issue", "view", issue_number, "--repo", repository, "--output", "json"], cwd=target_root)
    return run_json_command(
        "gh",
        ["issue", "view", issue_number, "--repo", repository, "--json", "title,body,labels,url,number"],
        cwd=target_root,
    )


def normalize_labels(labels: Any) -> list[str]:
    if not isinstance(labels, list):
        return []
    normalized: list[str] = []
    for label in labels:
        if isinstance(label, str):
            value = label.strip()
        elif isinstance(label, dict) and label.get("name"):
            value = str(label.get("name", "")).strip()
        else:
            value = ""
        if value:
            normalized.append(value)
    return normalized


def issue_title_from_meta(issue_meta: dict[str, Any] | None) -> str:
    return str((issue_meta or {}).get("title") or (issue_meta or {}).get("name") or "").strip()


def issue_body_from_meta(issue_meta: dict[str, Any] | None) -> str:
    return str((issue_meta or {}).get("body") or (issue_meta or {}).get("description") or "").strip()


def issue_url_from_meta(issue_meta: dict[str, Any] | None) -> str:
    return str((issue_meta or {}).get("url") or (issue_meta or {}).get("web_url") or (issue_meta or {}).get("html_url") or "").strip()


def infer_triage(issue_meta: dict[str, Any] | None) -> dict[str, Any]:
    title = issue_title_from_meta(issue_meta)
    body = issue_body_from_meta(issue_meta)
    text = f"{title}\n{body}".lower()
    labels = normalize_labels((issue_meta or {}).get("labels"))

    issue_type = "enhancement"
    if re.search(r"\b(bug|broken|error|fail|failing|crash)\b", text):
        issue_type = "bug"
    elif re.search(r"\b(doc|docs|documentation|readme)\b", text):
        issue_type = "documentation"
    elif re.search(r"\b(question|\?)\b", text) and not re.search(r"\b(feature|enhancement|build|add)\b", text):
        issue_type = "question"

    area = ""
    if re.search(r"\b(test|tests|fixture|spec-check|validation)\b", text):
        area = "area:tests"
    elif re.search(r"\b(skill|skills|agent)\b", text):
        area = "area:skills"
    elif re.search(r"\b(spec|plan|planning)\b", text):
        area = "area:specs"
    elif re.search(r"\b(cli|command|workflow|orchestrator|run|step|status|next)\b", text):
        area = "area:workflow"

    priority = "priority:p2"
    if re.search(r"\b(critical|urgent|blocker|p0)\b", text):
        priority = "priority:p0"
    elif re.search(r"\b(high|p1)\b", text):
        priority = "priority:p1"
    elif re.search(r"\b(low|nice to have|p3)\b", text):
        priority = "priority:p3"

    labels_applied = ["triaged"]
    if area:
        labels_applied.append(area)
    labels_applied.append("gcw:executor-local")
    for label in labels:
        if label in {"gcw:executor-hosted", "gcw:executor-local"}:
            labels_applied[-1] = label

    return {
        "summary": title,
        "classification_type": issue_type,
        "classification_area": area,
        "classification_priority": priority,
        "labels_applied": labels_applied,
    }


def resolve_asset_path(target_root: Path, relative_path: str) -> Path:
    candidates = [target_root / relative_path, REPO_ROOT / relative_path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise WorkflowError(f"required GCW asset is missing: {relative_path}")


def template_root() -> Path:
    built = REPO_ROOT / "dist" / "templates" / "repo"
    return built if built.exists() else REPO_ROOT


def list_files(root: Path, relative_root: str) -> list[str]:
    full_path = root / relative_root
    if full_path.is_file():
        return [relative_root]
    files: list[str] = []
    for entry in sorted(full_path.iterdir(), key=lambda item: item.name):
        if entry.name == "__pycache__" or entry.name.endswith(".pyc"):
            continue
        child = f"{relative_root}/{entry.name}"
        if entry.is_dir():
            files.extend(list_files(root, child))
        elif entry.is_file():
            files.append(child)
    return files


def write_planning_files_from_templates(target_root: Path, issue_dir: Path, issue_meta: dict[str, Any] | None) -> None:
    templates = {
        "task_plan.md": resolve_asset_path(target_root, ".agents/skills/planning-with-files/templates/task_plan.md"),
        "findings.md": resolve_asset_path(target_root, ".agents/skills/planning-with-files/templates/findings.md"),
        "progress.md": resolve_asset_path(target_root, ".agents/skills/planning-with-files/templates/progress.md"),
    }
    issue_dir.mkdir(parents=True, exist_ok=True)
    title = issue_title_from_meta(issue_meta) or f"GCW issue {issue_dir.name}"
    for filename, template_path in templates.items():
        target_path = issue_dir / filename
        if target_path.exists():
            continue
        content = template_path.read_text(encoding="utf-8")
        content = content.replace("[Brief Description]", title)
        content = content.replace("[One sentence describing the end state]", "Add formal terminal-first GCW commands for workflow orchestration.")
        content = content.replace("[Question to answer]", "How should the CLI route workflow states without duplicating GCW runtime rules?")
        content = content.replace("[goal statement]", "Add formal terminal-first GCW commands for workflow orchestration.")
        target_path.write_text(content, encoding="utf-8")


def file_sha256(file_path: Path) -> str:
    return f"sha256:{hashlib.sha256(file_path.read_bytes()).hexdigest()}"


def planning_links_for_projection(projection: dict[str, Any]) -> dict[str, str]:
    platform = str(projection.get("platform", "github")).strip()
    repository = str(projection.get("repository", "")).strip()
    branch = str(projection.get("branch", "")).strip()
    issue = str(projection.get("issue", "")).strip()
    if not repository or not branch or not issue:
        return {}
    base = (
        f"https://gitlab.com/{repository}/-/blob/{branch}/.gcw/issues/{issue}"
        if platform == "gitlab"
        else f"https://github.com/{repository}/blob/{branch}/.gcw/issues/{issue}"
    )
    return {
        "task_plan": f"{base}/task_plan.md",
        "findings": f"{base}/findings.md",
        "progress": f"{base}/progress.md",
    }


def create_triage_options(target_root: Path, projection: dict[str, Any], issue_meta: dict[str, Any] | None) -> Path:
    triage = infer_triage(issue_meta)
    remote_sync = {
        "remote_sync": {
            "platform": projection.get("platform"),
            "issue_type": "Bug" if triage["classification_type"] == "bug" else "Feature",
            "priority": (
                "Urgent"
                if triage["classification_priority"] == "priority:p0"
                else "High"
                if triage["classification_priority"] == "priority:p1"
                else "Low"
                if triage["classification_priority"] == "priority:p3"
                else "Medium"
            ),
            "labels": triage["labels_applied"],
        }
    }
    remote_sync_file = write_json_temp("gcw-triage-", remote_sync)
    if projection.get("platform") in {"github", "gitlab"}:
        try:
            run_json_command(
                "python3",
                [
                    str(resolve_asset_path(target_root, ".agents/skills/gcw-issue-triage/scripts/manage_triage_metadata.py")),
                    "apply-metadata",
                    "--platform",
                    str(projection.get("platform")),
                    "--repo",
                    str(projection.get("repository")),
                    "--issue",
                    str(projection.get("issue")),
                    "--type",
                    triage["classification_type"],
                    "--priority",
                    triage["classification_priority"],
                    "--labels",
                    ",".join(triage["labels_applied"]),
                    "--executor",
                    "local",
                ],
                cwd=target_root,
            )
        except Exception:
            pass
    return write_json_temp(
        "gcw-step-",
        {
            "summary": triage["summary"],
            "classification_type": triage["classification_type"],
            "classification_area": triage["classification_area"],
            "classification_priority": triage["classification_priority"],
            "labels_applied": triage["labels_applied"],
            "remote_sync_file": str(remote_sync_file),
        },
    )


def create_clarify_options(target_root: Path, projection: dict[str, Any]) -> Path:
    gate_file = write_json_temp("gcw-clarify-gate-", {})
    result = subprocess.run(
        [
            "python3",
            str(resolve_asset_path(target_root, ".agents/skills/gcw-issue-clarify/scripts/evaluate_issue_readiness.py")),
            "--profile",
            "enhancement",
            "--platform",
            str(projection.get("platform")),
            "--repo",
            str(projection.get("repository")),
            "--issue",
            str(projection.get("issue")),
            "--output",
            str(gate_file),
        ],
        cwd=str(target_root),
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        gate = json.loads(result.stdout or gate_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError((result.stderr or result.stdout or "failed to evaluate issue readiness").strip()) from exc

    options: dict[str, Any] = {"gate_file": str(gate_file)}
    if gate.get("ok"):
        options["ready"] = True
        options["summary"] = "scope clear"
    else:
        question = gate.get("errors") or []
        options["question"] = "Please update the issue so GCW can continue." if not question else "Please update the issue so GCW can continue:\n- " + "\n- ".join(question)
    return write_json_temp("gcw-step-", options)


def create_issue_to_spec_options(target_root: Path, issue_dir: Path, issue_meta: dict[str, Any] | None) -> Path:
    write_planning_files_from_templates(target_root, issue_dir, issue_meta)
    return write_json_temp("gcw-step-", {"planning_commit_pushed": True})


def create_implement_check_payload(issue_dir: Path, projection: dict[str, Any]) -> Path:
    payload = {
        "gate": {
            "ok": True,
            "checks": [{"id": "implementation_readiness", "ok": True}],
            "validation": [],
        },
        "planning_links": planning_links_for_projection(projection),
        "review_request": {
            "title": f"feat: issue {projection['issue']}",
            "summary": "Implements the planned workflow change.",
            "issue_link": f"Closes #{projection['issue']}",
        },
        "risks": "Low risk; changes are scoped to the current issue branch.",
        "scope": "Current issue branch only.",
        "reviewer_notes": "Review the scoped issue diff and generated workflow artifacts.",
        "self_review": {"recorded": True, "progress_section": "## Local Self-Review"},
        "spec_refs": {
            "task_plan_sha": file_sha256(issue_dir / "task_plan.md"),
            "findings_sha": file_sha256(issue_dir / "findings.md"),
            "progress_sha": file_sha256(issue_dir / "progress.md"),
        },
    }
    return write_json_temp("gcw-implement-check-", payload)


def render_review_request_body(issue_dir: Path) -> str:
    return render_review_request(argparse.Namespace(issue_dir=issue_dir))


def upsert_github_pull_request(target_root: Path, projection: dict[str, Any], issue_dir: Path) -> str:
    review_request_body = render_review_request_body(issue_dir)
    body_file = Path(tempfile.mkdtemp(prefix=f"gcw-review-request-{projection['issue']}-")) / "body.md"
    body_file.write_text(review_request_body, encoding="utf-8")
    pr_list_result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            str(projection["repository"]),
            "--head",
            str(projection["branch"]),
            "--json",
            "url,title",
        ],
        cwd=str(target_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if pr_list_result.returncode != 0:
        raise WorkflowError((pr_list_result.stderr or pr_list_result.stdout or "gh pr list failed").strip())
    try:
        pr_list = json.loads(pr_list_result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise WorkflowError("failed to parse JSON output from gh") from exc
    review_request = {
        "title": f"feat: issue {projection['issue']}",
    }
    payload_path = issue_dir / "implement-check-payload.json"
    if payload_path.is_file():
        try:
            implement_payload = read_json(payload_path)
            if isinstance(implement_payload.get("review_request"), dict):
                review_request.update(implement_payload["review_request"])
        except WorkflowError:
            pass
    if isinstance(pr_list, list) and pr_list and pr_list[0].get("url"):
        subprocess.run(
            [
                "gh",
                "pr",
                "edit",
                str(pr_list[0]["url"]),
                "--repo",
                str(projection["repository"]),
                "--title",
                str(review_request.get("title", "")),
                "--body-file",
                str(body_file),
            ],
            cwd=str(target_root),
            text=True,
            capture_output=True,
            check=True,
        )
        return str(pr_list[0]["url"])
    created = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            str(projection["repository"]),
            "--head",
            str(projection["branch"]),
            "--title",
            str(review_request.get("title", "")),
            "--body-file",
            str(body_file),
        ],
        cwd=str(target_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if created.returncode != 0:
        raise WorkflowError((created.stderr or created.stdout or "failed to create pull request").strip())
    return created.stdout.strip()


def upsert_gitlab_merge_request(target_root: Path, projection: dict[str, Any], issue_dir: Path) -> str:
    review_request_body = render_review_request_body(issue_dir)
    body_file = Path(tempfile.mkdtemp(prefix=f"gcw-review-request-{projection['issue']}-")) / "body.md"
    body_file.write_text(review_request_body, encoding="utf-8")
    review_request = {
        "title": f"feat: issue {projection['issue']}",
        "description": review_request_body,
    }
    payload_path = issue_dir / "implement-check-payload.json"
    if payload_path.is_file():
        try:
            implement_payload = read_json(payload_path)
            if isinstance(implement_payload.get("review_request"), dict):
                review_request.update(implement_payload["review_request"])
        except WorkflowError:
            pass
    existing_result = subprocess.run(
        [
            "glab",
            "mr",
            "list",
            "--repo",
            str(projection["repository"]),
            "--source-branch",
            str(projection["branch"]),
            "--output",
            "json",
        ],
        cwd=str(target_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if existing_result.returncode != 0:
        raise WorkflowError((existing_result.stderr or existing_result.stdout or "glab mr list failed").strip())
    try:
        mr_list = json.loads(existing_result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise WorkflowError("failed to parse JSON output from glab") from exc
    existing_url = ""
    if isinstance(mr_list, list) and mr_list:
        first = mr_list[0] if isinstance(mr_list[0], dict) else {}
        existing_url = str(first.get("web_url") or first.get("url") or "").strip()
        existing_ref = str(first.get("iid") or first.get("source_branch") or first.get("sourceBranch") or existing_url).strip()
    else:
        existing_ref = ""
    if existing_ref:
        subprocess.run(
            [
                "glab",
                "mr",
                "update",
                existing_ref,
                "--repo",
                str(projection["repository"]),
                "--title",
                str(review_request.get("title", "")),
                "--description",
                str(review_request.get("description", review_request_body)),
                "--source-branch",
                str(projection["branch"]),
                "--target-branch",
                str(review_request.get("target_branch", "main")),
                "-y",
            ],
            cwd=str(target_root),
            text=True,
            capture_output=True,
            check=True,
        )
        return existing_url
    created = subprocess.run(
        [
            "glab",
            "mr",
            "create",
            "--repo",
            str(projection["repository"]),
            "--source-branch",
            str(projection["branch"]),
            "--target-branch",
            str(review_request.get("target_branch", "main")),
            "--title",
            str(review_request.get("title", "")),
            "--description",
            str(review_request.get("description", review_request_body)),
            "-y",
        ],
        cwd=str(target_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if created.returncode != 0:
        raise WorkflowError((created.stderr or created.stdout or "failed to create merge request").strip())
    url = created.stdout.strip()
    if not url:
        fallback_list = subprocess.run(
            [
                "glab",
                "mr",
                "list",
                "--repo",
                str(projection["repository"]),
                "--source-branch",
                str(projection["branch"]),
                "--output",
                "json",
            ],
            cwd=str(target_root),
            text=True,
            capture_output=True,
            check=False,
        )
        if fallback_list.returncode != 0:
            raise WorkflowError((fallback_list.stderr or fallback_list.stdout or "glab mr list failed").strip())
        try:
            mr_list = json.loads(fallback_list.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise WorkflowError("failed to parse JSON output from glab") from exc
        if isinstance(mr_list, list) and mr_list:
            first = mr_list[0] if isinstance(mr_list[0], dict) else {}
            url = str(first.get("web_url") or first.get("url") or "").strip()
    if not url:
        raise WorkflowError("failed to resolve merge request URL after upsert")
    return url


def options_file_for_step(target_root: Path, issue_dir: Path, projection: dict[str, Any], step_name: str, issue_meta: dict[str, Any] | None) -> Path | None:
    if step_name == "gcw-issue-triage":
        return create_triage_options(target_root, projection, issue_meta)
    if step_name == "gcw-issue-clarify":
        return create_clarify_options(target_root, projection)
    if step_name == "gcw-issue-to-spec":
        return create_issue_to_spec_options(target_root, issue_dir, issue_meta)
    if step_name == "gcw-spec-check":
        return write_json_temp("gcw-step-", {"result": "passed"})
    if step_name == "gcw-implement-check":
        payload_file = create_implement_check_payload(issue_dir, projection)
        persisted_payload = issue_dir / "implement-check-payload.json"
        persisted_payload.write_text(payload_file.read_text(encoding="utf-8"), encoding="utf-8")
        return write_json_temp("gcw-step-", {"payload_file": str(persisted_payload)})
    if step_name == "gcw-pr-publish":
        platform = str(projection.get("platform", "github"))
        if platform == "gitlab":
            review_request_url = upsert_gitlab_merge_request(target_root, projection, issue_dir)
            return write_json_temp("gcw-step-", {"review_request_url": review_request_url, "target": "gitlab_mr"})
        review_request_url = upsert_github_pull_request(target_root, projection, issue_dir)
        return write_json_temp("gcw-step-", {"review_request_url": review_request_url, "target": "github_pr"})
    if step_name == "gcw-pr-review":
        return write_json_temp("gcw-step-", {"result": "passed"})
    return None


def ensure_issue_workflow(target_root: Path, issue: str) -> tuple[Path, bool, dict[str, Any] | None]:
    issue_dir = issue_dir_for_target(target_root, issue)
    if issue_dir.exists():
        return issue_dir, False, None
    platform, repository = parse_remote_repository(read_git_remote(target_root))
    issue_meta = fetch_issue_metadata(target_root, platform, repository, issue)
    branch = detect_branch(target_root, issue)
    (issue_dir / "events").mkdir(parents=True, exist_ok=True)
    init_workflow(
        argparse.Namespace(
            issue_dir=issue_dir,
            issue=issue_number_as_string(issue),
            platform=platform,
            repository=repository,
            branch=branch,
            owner_kind="local",
            owner_id="gcw-cli",
            actor_kind="local",
            actor_id="gcw-cli",
            expected_last_seq=None,
            parent_projection_hash="",
        )
    )
    return issue_dir, True, issue_meta


def resolve_issue_metadata(target_root: Path, issue_dir: Path, projection: dict[str, Any], issue_meta: dict[str, Any] | None, issue_number: str) -> dict[str, Any] | None:
    if issue_meta is not None:
        return issue_meta
    platform = str(projection.get("platform", "")).strip()
    repository = str(projection.get("repository", "")).strip()
    if not platform or not repository:
        return None
    return fetch_issue_metadata(target_root, platform, repository, issue_number_as_string(issue_number))


def read_projection(target_root: Path, issue_dir: Path) -> dict[str, Any]:
    rebuild_projection(argparse.Namespace(issue_dir=issue_dir))
    validation = assert_projection_current(issue_dir)
    if not validation["ok"]:
        raise WorkflowError(f"workflow validation failed: {'; '.join(validation['errors'])}")
    workflow = load_projection(issue_dir)
    return workflow["projection"]


def summarize_projection_result(projection: dict[str, Any], executed_steps: list[str] | None = None, stop_reason: str = "") -> dict[str, Any]:
    return {
        "ok": True,
        "issue": str(projection.get("issue", "")),
        "phase": str(projection.get("phase", "")),
        "last_completed_step": str(projection.get("last_completed_step", "")),
        "next_allowed_steps": list(projection.get("next_allowed_steps") or []),
        "executed_steps": executed_steps or [],
        "stop_reason": stop_reason,
        "errors": [],
    }


def run_step_command(target_root: Path, issue_dir: Path, projection: dict[str, Any], requested_step: str, issue_meta: dict[str, Any] | None) -> dict[str, Any]:
    if requested_step == "gcw-issue-intake":
        raise WorkflowError("gcw-issue-intake should be run through gcw run or by targeting an issue outside GCW state")

    if requested_step == "gcw-implement":
        payload = write_json_temp("gcw-implement-", {"work_summary": "Implementation work recorded from terminal-first GCW CLI."})
        progress = publish_milestone_progress_comment(
            issue_dir,
            requested_step,
            {"work_summary": "Implementation work recorded from terminal-first GCW CLI."},
            dry_run=False,
        )
        record_implement(
            argparse.Namespace(
                issue_dir=issue_dir,
                work_summary="Implementation work recorded from terminal-first GCW CLI.",
                progress_comment_url=progress["progress_comment_url"],
                feedback_source="",
                feedback_ref="",
                actor_kind="local",
                actor_id="gcw-cli",
                expected_last_seq=None,
                parent_projection_hash="",
            )
        )
        updated = read_projection(target_root, issue_dir)
        result = summarize_projection_result(updated, [requested_step])
        result["progress_comment_url"] = progress["progress_comment_url"]
        return result

    options_file = options_file_for_step(target_root, issue_dir, projection, requested_step, issue_meta)
    args = argparse.Namespace(
        step=requested_step,
        issue_dir=issue_dir,
        dry_run=False,
        adapter="github",
        options_file=options_file,
    )
    step_result = run_single_step(args)
    if step_result["ok"] is not True:
        return {
            "ok": False,
            "issue": str(projection.get("issue", "")),
            "phase": str(projection.get("phase", "")),
            "last_completed_step": str(projection.get("last_completed_step", "")),
            "next_allowed_steps": list(projection.get("next_allowed_steps") or []),
            "executed_steps": [],
            "stop_reason": str(step_result.get("stop_reason", "blocked")),
            "errors": [str(item) for item in step_result.get("validation", [])] or [f"{requested_step} failed"],
        }
    updated = read_projection(target_root, issue_dir)
    return summarize_projection_result(updated, [requested_step])


def status_command(target_root: Path, issue: str) -> dict[str, Any]:
    issue_dir = issue_dir_for_target(target_root, issue)
    if not issue_dir.exists():
        raise WorkflowError(f"GCW issue state not found for issue {issue}")
    projection = read_projection(target_root, issue_dir)
    return summarize_projection_result(projection)


def next_command(target_root: Path, issue: str) -> dict[str, Any]:
    summary = status_command(target_root, issue)
    return summary


def step_command(target_root: Path, issue: str, requested_step: str) -> dict[str, Any]:
    issue_number = issue_number_as_string(issue)
    issue_dir, created, issue_meta = ensure_issue_workflow(target_root, issue_number)
    projection = read_projection(target_root, issue_dir)
    resolved_issue_meta = resolve_issue_metadata(target_root, issue_dir, projection, issue_meta, issue_number)
    if requested_step == "gcw-issue-intake":
        if created:
            created_projection = read_projection(target_root, issue_dir)
            return summarize_projection_result(created_projection, [requested_step])
        raise WorkflowError(f"step {requested_step} is not allowed in phase {projection['phase']}")
    if requested_step not in (projection.get("next_allowed_steps") or []):
        raise WorkflowError(f"step {requested_step} is not allowed in phase {projection['phase']}")
    if requested_step == "gcw-implement" and not has_meaningful_implementation_changes(target_root, issue_dir):
        raise WorkflowError("gcw-implement requires code or documentation changes in the working tree before recording implementation progress")
    return run_step_command(target_root, issue_dir, projection, requested_step, resolved_issue_meta)


def has_meaningful_implementation_changes(target_root: Path, issue_dir: Path) -> bool:
    changed_paths = git_changed_paths(target_root)
    issue_prefix = f"{issue_dir.relative_to(target_root)}".replace("\\", "/") + "/"
    for file_path in changed_paths:
        if file_path.startswith(issue_prefix):
            continue
        if file_path.startswith(".gcw-runtime"):
            continue
        return True
    return False


def run_command(target_root: Path, issue: str) -> dict[str, Any]:
    issue_number = issue_number_as_string(issue)
    issue_dir, created, issue_meta = ensure_issue_workflow(target_root, issue_number)
    projection = read_projection(target_root, issue_dir)
    resolved_issue_meta = resolve_issue_metadata(target_root, issue_dir, projection, issue_meta, issue_number)
    executed: list[str] = []
    if created:
        executed.append("gcw-issue-intake")

    while not should_stop_for_human_handoff(str(projection.get("phase", ""))):
        next_step = select_next_run_step(projection, git_changed_paths(target_root), str(issue_dir))
        if not next_step:
            break
        step_result = run_step_command(target_root, issue_dir, projection, next_step, resolved_issue_meta)
        if not step_result.get("ok"):
            return step_result
        executed.append(next_step)
        projection = read_projection(target_root, issue_dir)
        if should_stop_for_human_handoff(str(projection.get("phase", ""))):
            break

    stop_reason = human_handoff_reason(str(projection.get("phase", "")))
    if not stop_reason and (projection.get("next_allowed_steps") or [None])[0] == "gcw-implement":
        stop_reason = "Waiting for implementation changes before recording gcw-implement."
    summary = summarize_projection_result(projection, executed, stop_reason)
    return summary


def render_status(summary: dict[str, Any]) -> None:
    print(f"Issue: {summary['issue']}")
    print(f"Phase: {summary['phase']}")
    if summary.get("last_completed_step"):
        print(f"Last completed step: {summary['last_completed_step']}")
    print(f"Next allowed steps: {', '.join(summary.get('next_allowed_steps') or []) or '(none)'}")


def render_next(summary: dict[str, Any]) -> None:
    print(f"Issue: {summary['issue']}")
    print(f"Phase: {summary['phase']}")
    next_steps = summary.get("next_allowed_steps") or []
    print(f"Next step: {next_steps[0] if next_steps else '(none)'}")


def render_step(summary: dict[str, Any], requested_step: str) -> None:
    print(f"Executed: {requested_step}")
    print(f"Issue: {summary['issue']}")
    print(f"Phase: {summary['phase']}")
    if summary.get("last_completed_step"):
        print(f"Last completed step: {summary['last_completed_step']}")
    print(f"Next allowed steps: {', '.join(summary.get('next_allowed_steps') or []) or '(none)'}")


def render_run(summary: dict[str, Any]) -> None:
    print(f"Issue: {summary['issue']}")
    print(f"Executed steps: {', '.join(summary.get('executed_steps') or []) or '(none)'}")
    print(f"Phase: {summary['phase']}")
    if summary.get("last_completed_step"):
        print(f"Last completed step: {summary['last_completed_step']}")
    print(f"Next allowed steps: {', '.join(summary.get('next_allowed_steps') or []) or '(none)'}")
    if summary.get("stop_reason"):
        print(f"Stop reason: {summary['stop_reason']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Terminal GCW workflow entrypoint.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--target", default=str(Path.cwd()))
    status.add_argument("issue")
    status.set_defaults(handler=handle_status)

    next_parser = subparsers.add_parser("next")
    next_parser.add_argument("--target", default=str(Path.cwd()))
    next_parser.add_argument("issue")
    next_parser.set_defaults(handler=handle_next)

    step = subparsers.add_parser("step")
    step.add_argument("--target", default=str(Path.cwd()))
    step.add_argument("step")
    step.add_argument("issue")
    step.set_defaults(handler=handle_step)

    run = subparsers.add_parser("run")
    run.add_argument("--target", default=str(Path.cwd()))
    run.add_argument("issue")
    run.set_defaults(handler=handle_run)
    return parser


def handle_status(args: argparse.Namespace) -> dict[str, Any]:
    return status_command(Path(args.target), args.issue)


def handle_next(args: argparse.Namespace) -> dict[str, Any]:
    return next_command(Path(args.target), args.issue)


def handle_step(args: argparse.Namespace) -> dict[str, Any]:
    return step_command(Path(args.target), args.issue, args.step)


def handle_run(args: argparse.Namespace) -> dict[str, Any]:
    return run_command(Path(args.target), args.issue)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
        return emit(result)
    except (WorkflowError, ValueError) as exc:
        return emit(
            {
                "ok": False,
                "issue": "",
                "phase": "",
                "last_completed_step": "",
                "next_allowed_steps": [],
                "executed_steps": [],
                "stop_reason": "",
                "errors": [str(exc)],
            }
        )


if __name__ == "__main__":
    sys.exit(main())
