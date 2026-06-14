from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
READINESS_DIR = SKILL_DIR / "readiness"
KNOWN_PROFILES = frozenset({"enhancement"})
KNOWN_RUBRIC_VERSIONS = frozenset({"issue-clarify-readiness/v1"})

BLOCKER_CLEAR_PATTERNS = (
    re.compile(r"^\s*none\b", re.IGNORECASE),
    re.compile(r"can\s+start\s+immediately", re.IGNORECASE),
    re.compile(r"no\s+blockers?", re.IGNORECASE),
)


def load_rubric(profile: str) -> dict[str, Any]:
    if profile not in KNOWN_PROFILES:
        raise ValueError(f"unknown readiness profile: {profile}")
    path = READINESS_DIR / f"{profile}.json"
    if not path.is_file():
        raise FileNotFoundError(f"readiness rubric not found: {path}")
    rubric = json.loads(path.read_text(encoding="utf-8"))
    version = str(rubric.get("rubric_version", ""))
    if version not in KNOWN_RUBRIC_VERSIONS:
        raise ValueError(f"unsupported rubric_version: {version}")
    return rubric


def rubric_check_ids(rubric: dict[str, Any]) -> list[str]:
    checks = rubric.get("checks")
    if not isinstance(checks, list):
        return []
    return [str(item["id"]) for item in checks if isinstance(item, dict) and item.get("id")]


def parse_markdown_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_title: str | None = None
    current_lines: list[str] = []

    for line in body.splitlines():
        if line.startswith("## "):
            if current_title is not None:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = line[3:].strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        sections[current_title] = "\n".join(current_lines).strip()
    return sections


def _section_content(sections: dict[str, str], title: str) -> str:
    for key, value in sections.items():
        if key.casefold() == title.casefold():
            return value
    return ""


def _list_items(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if item.startswith("[ ]") or item.startswith("[x]") or item.startswith("[X]"):
                item = item[3:].strip()
            if item:
                items.append(item)
    return items


def check_has_what_to_build(sections: dict[str, str]) -> tuple[bool, str]:
    content = _section_content(sections, "What to build")
    if not content:
        return False, "missing or empty ## What to build section"
    return True, ""


def check_has_acceptance_criteria(sections: dict[str, str]) -> tuple[bool, str]:
    content = _section_content(sections, "Acceptance criteria")
    if not content:
        return False, "missing ## Acceptance criteria section"
    items = _list_items(content)
    if not items:
        return False, "no acceptance list items found"
    return True, ""


def check_blocker_resolved(sections: dict[str, str]) -> tuple[bool, str]:
    content = _section_content(sections, "Blocked by")
    if not content:
        return True, ""
    normalized = " ".join(content.split())
    for pattern in BLOCKER_CLEAR_PATTERNS:
        if pattern.search(normalized):
            return True, ""
    return False, "blocked by unresolved dependency or decision"


def check_body_not_placeholder(body: str) -> tuple[bool, str]:
    if "Not provided" in body:
        return False, "body contains Not provided placeholder"
    return True, ""


STRUCTURAL_CHECKERS = {
    "has_what_to_build": lambda body, sections: check_has_what_to_build(sections),
    "has_acceptance_criteria": lambda body, sections: check_has_acceptance_criteria(sections),
    "blocker_resolved": lambda body, sections: check_blocker_resolved(sections),
    "body_not_placeholder": lambda body, sections: check_body_not_placeholder(body),
}


def evaluate_structural_check(check_id: str, body: str, sections: dict[str, str]) -> tuple[bool, str]:
    checker = STRUCTURAL_CHECKERS.get(check_id)
    if checker is None:
        return False, f"unknown structural check: {check_id}"
    return checker(body, sections)


def evaluate_readiness(body: str, profile: str = "enhancement") -> dict[str, Any]:
    rubric = load_rubric(profile)
    sections = parse_markdown_sections(body)
    checks_out: list[dict[str, Any]] = []
    errors: list[str] = []

    for item in rubric.get("checks", []):
        if not isinstance(item, dict):
            continue
        check_id = str(item.get("id", ""))
        source = str(item.get("source", ""))
        blocking = bool(item.get("blocking", True))
        if source != "structural":
            raise ValueError(f"Phase 1 does not support source={source!r} for check {check_id}")

        ok, message = evaluate_structural_check(check_id, body, sections)
        check_result: dict[str, Any] = {
            "id": check_id,
            "ok": ok,
            "source": "structural",
        }
        if message:
            check_result["message"] = message
        checks_out.append(check_result)
        if blocking and not ok:
            errors.append(f"{check_id}: {message or 'check failed'}")

    return {
        "ok": not errors,
        "rubric_version": str(rubric["rubric_version"]),
        "profile": str(rubric["profile"]),
        "checks": checks_out,
        "errors": errors,
    }


def gate_to_question(gate: dict[str, Any]) -> str:
    if gate.get("ok") is True:
        return ""
    errors = gate.get("errors")
    if isinstance(errors, list) and errors:
        lines = ["Please update the issue so GCW can write the spec:"]
        for error in errors:
            lines.append(f"- {error}")
        return "\n".join(lines)
    failed = [
        str(item.get("message") or item.get("id"))
        for item in gate.get("checks", [])
        if isinstance(item, dict) and item.get("ok") is not True
    ]
    if failed:
        return "Please clarify: " + "; ".join(failed)
    return "Please provide the missing issue information required for spec writing."


def validate_gate_against_rubric(gate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    version = str(gate.get("rubric_version", ""))
    profile = str(gate.get("profile", ""))
    if version not in KNOWN_RUBRIC_VERSIONS:
        errors.append(f"unknown rubric_version: {version}")
    if profile not in KNOWN_PROFILES:
        errors.append(f"unknown readiness profile: {profile}")
    if version and profile:
        try:
            rubric = load_rubric(profile)
            expected_ids = set(rubric_check_ids(rubric))
        except (ValueError, FileNotFoundError) as exc:
            errors.append(str(exc))
            expected_ids = set()
        actual_ids = {
            str(item.get("id"))
            for item in gate.get("checks", [])
            if isinstance(item, dict) and item.get("id")
        }
        missing = expected_ids - actual_ids
        extra = actual_ids - expected_ids
        if missing:
            errors.append(f"gate.checks missing ids: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"gate.checks unexpected ids: {', '.join(sorted(extra))}")

    blocking_failed = False
    rubric_blocking: dict[str, bool] = {}
    if profile in KNOWN_PROFILES:
        try:
            for item in load_rubric(profile).get("checks", []):
                if isinstance(item, dict):
                    rubric_blocking[str(item.get("id", ""))] = bool(item.get("blocking", True))
        except (ValueError, FileNotFoundError):
            pass

    for item in gate.get("checks", []):
        if not isinstance(item, dict):
            continue
        check_id = str(item.get("id", ""))
        if item.get("ok") is not True and rubric_blocking.get(check_id, True):
            blocking_failed = True

    gate_ok = gate.get("ok") is True
    if blocking_failed and gate_ok:
        errors.append("gate.ok must be false when a blocking check failed")
    if not blocking_failed and not gate_ok and gate.get("errors"):
        pass
    elif not blocking_failed and gate_ok is False and not gate.get("errors"):
        errors.append("gate.errors must be non-empty when gate.ok is false")

    return errors


def fetch_issue_body(platform: str, repo: str, issue: str) -> str:
    if platform == "gitlab":
        result = subprocess.run(
            ["glab", "issue", "view", issue, "--repo", repo, "--output", "json"],
            check=True,
            text=True,
            capture_output=True,
        )
        data = json.loads(result.stdout or "{}")
        return str(data.get("description", ""))

    result = subprocess.run(
        ["gh", "issue", "view", issue, "--repo", repo, "--json", "body", "--jq", ".body"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout
