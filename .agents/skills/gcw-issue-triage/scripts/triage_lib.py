from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
LABELS_FILE = SKILL_DIR / "labels.json"
MAPPINGS_FILE = SKILL_DIR / "triage_mappings.json"
GROUPS_WITH_SINGLE_VALUE = {"type", "area", "priority", "readiness", "triage"}
GITHUB_LEGACY_LABEL_GROUPS = {"type", "priority"}
GITHUB_API_VERSION = "2026-03-10"


def load_labels() -> dict[str, dict[str, Any]]:
    data = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    labels = data.get("labels", {})
    if not isinstance(labels, dict) or not labels:
        raise ValueError(f"{LABELS_FILE} must define a non-empty labels object")
    return labels


def load_mappings() -> dict[str, Any]:
    return json.loads(MAPPINGS_FILE.read_text(encoding="utf-8"))


def label_platforms(meta: dict[str, Any]) -> list[str]:
    platforms = meta.get("platforms")
    if isinstance(platforms, list) and platforms:
        return [str(item) for item in platforms]
    return ["github", "gitlab"]


def labels_for_platform(labels: dict[str, dict[str, Any]], platform: str) -> dict[str, dict[str, Any]]:
    return {
        name: meta
        for name, meta in labels.items()
        if platform in label_platforms(meta)
    }


def labels_by_group(labels: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for name, meta in labels.items():
        group = str(meta.get("group", ""))
        grouped.setdefault(group, []).append(name)
    return grouped


def github_issue_type(gcw_type: str) -> str:
    mappings = load_mappings()["github"]["type_to_issue_type"]
    if gcw_type not in mappings:
        raise ValueError(f"unknown GCW type for GitHub mapping: {gcw_type}")
    return str(mappings[gcw_type])


def github_priority_value(gcw_priority: str) -> str:
    mappings = load_mappings()["github"]["priority_to_field_value"]
    if gcw_priority not in mappings:
        raise ValueError(f"unknown GCW priority for GitHub mapping: {gcw_priority}")
    return str(mappings[gcw_priority])


def gcw_type_label(gcw_type: str) -> str:
    return gcw_type


def gcw_priority_label(gcw_priority: str) -> str:
    return gcw_priority


def legacy_github_labels(labels: dict[str, dict[str, Any]]) -> list[str]:
    grouped = labels_by_group(labels)
    names: list[str] = []
    for group in GITHUB_LEGACY_LABEL_GROUPS:
        names.extend(grouped.get(group, []))
    return names


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def gh_api_json(endpoint: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    cmd = ["gh", "api", endpoint, "-H", f"X-GitHub-Api-Version: {GITHUB_API_VERSION}"]
    if method != "GET":
        cmd.extend(["-X", method])
    if payload is not None:
        cmd.extend(["--input", "-"])
        result = run(cmd, check=True)
        if not result.stdout.strip():
            return {}
        return json.loads(result.stdout)
    result = run(cmd, check=True)
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def repo_id(repo: str) -> int:
    data = gh_api_json(f"repos/{repo}")
    return int(data["id"])


def issue_labels_github(repo: str, issue: str) -> list[str]:
    result = run(
        [
            "gh",
            "issue",
            "view",
            issue,
            "--repo",
            repo,
            "--json",
            "labels",
            "--jq",
            ".labels[].name",
        ]
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def issue_labels_gitlab(repo: str, issue: str) -> list[str]:
    result = run(
        [
            "glab",
            "issue",
            "view",
            issue,
            "--repo",
            repo,
            "--output",
            "json",
        ]
    )
    data = json.loads(result.stdout or "{}")
    labels = data.get("labels", [])
    names: list[str] = []
    if isinstance(labels, list):
        for item in labels:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and item.get("title"):
                names.append(str(item["title"]))
    return names


def github_priority_field_id(org: str) -> int:
    field_name = str(load_mappings()["github"]["priority_field_name"])
    fields = gh_api_json(f"/orgs/{org}/issue-fields")
    if not isinstance(fields, list):
        raise ValueError(f"issue fields not found for org {org}")
    for item in fields:
        if isinstance(item, dict) and item.get("name") == field_name:
            return int(item["id"])
    raise ValueError(f"GitHub issue field {field_name} not found for org {org}")


def github_issue_metadata(repo: str, issue: str) -> dict[str, Any]:
    org = repo.split("/")[0]
    priority_field_id = github_priority_field_id(org)
    data = gh_api_json(f"repos/{repo}/issues/{issue}")
    issue_type = data.get("type") if isinstance(data.get("type"), dict) else {}
    priority_name = ""
    for item in data.get("issue_field_values", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("issue_field_id") != priority_field_id:
            continue
        option = item.get("single_select_option")
        if isinstance(option, dict) and option.get("name"):
            priority_name = str(option["name"])
            break
    return {
        "issue_type": str(issue_type.get("name", "")),
        "priority": priority_name,
        "labels": [label["name"] for label in data.get("labels", []) if isinstance(label, dict)],
    }


def apply_github_labels(repo: str, issue: str, add: list[str], remove: list[str]) -> None:
    cmd = ["gh", "issue", "edit", issue, "--repo", repo]
    if add:
        cmd.extend(["--add-label", ",".join(add)])
    if remove:
        cmd.extend(["--remove-label", ",".join(remove)])
    if len(cmd) > 6:
        run(cmd)


def apply_gitlab_labels(repo: str, issue: str, add: list[str], remove: list[str]) -> None:
    cmd = ["glab", "issue", "update", issue, "--repo", repo]
    if add:
        cmd.extend(["--label", ",".join(add)])
    if remove:
        cmd.extend(["--unlabel", ",".join(remove)])
    if len(cmd) > 6:
        run(cmd)


def resolve_replacements(
    labels: dict[str, dict[str, Any]],
    current: list[str],
    desired: list[str],
) -> tuple[list[str], list[str]]:
    grouped = labels_by_group(labels)
    desired_set = set(desired)
    remove: list[str] = []
    for group in GROUPS_WITH_SINGLE_VALUE:
        desired_in_group = [name for name in desired_set if name in grouped.get(group, [])]
        if not desired_in_group:
            continue
        keep = desired_in_group[0]
        for name in current:
            if name in grouped.get(group, []) and name != keep:
                remove.append(name)
    add = [name for name in desired if name not in current]
    remove = [name for name in remove if name not in desired_set]
    return add, remove


def expected_remote_sync(platform: str, classification: dict[str, Any], labels_applied: list[str]) -> dict[str, Any]:
    if platform == "github":
        gcw_type = str(classification.get("type", ""))
        gcw_priority = str(classification.get("priority", ""))
        return {
            "platform": "github",
            "issue_type": github_issue_type(gcw_type) if gcw_type else "",
            "priority": github_priority_value(gcw_priority) if gcw_priority else "",
            "labels": list(labels_applied),
        }
    desired = list(labels_applied)
    gcw_type = classification.get("type")
    gcw_priority = classification.get("priority")
    if gcw_type:
        desired.append(str(gcw_type))
    if gcw_priority:
        desired.append(str(gcw_priority))
    return {
        "platform": "gitlab",
        "labels": sorted(set(desired)),
    }


def validate_labels_applied_for_platform(
    platform: str,
    labels_applied: list[str],
    labels: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    labels = labels or load_labels()
    grouped = labels_by_group(labels)
    errors: list[str] = []
    if platform != "github":
        return errors
    for label in labels_applied:
        for group in GITHUB_LEGACY_LABEL_GROUPS:
            if label in grouped.get(group, []):
                errors.append(
                    f"labels_applied must not include {label} on github; use classification and remote_sync instead"
                )
    return errors
