#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

RUNTIME_ROOT = Path(__file__).resolve().parents[1] / ".gcw" / "engine" / "runtime"


def load_contracts() -> dict[str, Any]:
    namespace: dict[str, Any] = {}
    exec((RUNTIME_ROOT / "gcw_workflow_contracts.py").read_text(encoding="utf-8"), namespace)
    return namespace


def table_lines(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def render_main_step_order(contracts: dict[str, Any]) -> str:
    rows = [[str(index + 1), step] for index, step in enumerate(contracts["MAIN_STEP_ORDER"])]
    return "\n".join(table_lines(["#", "Step"], rows))


def render_states(contracts: dict[str, Any]) -> str:
    state_summaries = {
        "issue-triaged": "Issue 已完成分类和远端 metadata 同步，但还没完成可执行性判断。",
        "issue-clarifying": "Issue 信息不足或边界不清，需要通过评论继续讨论。",
        "ready-for-planning": "Issue 已经讨论清楚，可以开始从 Issue 生成 spec files。",
        "planned": "spec files 已提交并推送，Issue 评论已经链接到远程文件。",
        "ready-for-implementation": "实现前检查通过，可以开始开发。",
        "implementing": "agent 正在实现功能、修复问题、补测试，或处理 PR review / 人审反馈。",
        "ready-for-review": "分支已经通过实现自查，且最新 `gcw-implement-check` 事件 payload 完整，具备创建或更新 review request 的条件。",
        "reviewing": "PR/MR 已创建或更新，正在经历自动检查或等待人类 reviewer 审查。",
        "changes-requested": "PR review 或人类 reviewer 要求修改。",
        "blocked": "当前无法继续推进，例如缺权限、缺依赖、外部服务不可用或需要人类决策。",
        "review-complete": "人类审查已经结束，结果已记录。",
    }
    rows = []
    for state in contracts["STATES"]:
        next_steps = ", ".join(contracts["NEXT_ALLOWED_STEPS"].get(state, [])) or "无"
        rows.append([state, state_summaries.get(state, "workflow state"), next_steps])
    return "\n".join(table_lines(["State", "Meaning", "Typical next step"], rows))


def render_next_allowed_steps(contracts: dict[str, Any]) -> str:
    rows = [[state, ", ".join(steps) or "(none)"] for state, steps in contracts["NEXT_ALLOWED_STEPS"].items()]
    return "\n".join(table_lines(["State", "Next allowed steps"], rows))


def render_human_handoff_states(contracts: dict[str, Any]) -> str:
    handoff_reasons = {
        "planned": "Waiting for human spec review before gcw-spec-check.",
        "issue-clarifying": "Waiting for issue clarification before GCW can continue.",
        "blocked": "Workflow is blocked and needs human intervention.",
        "reviewing": "Waiting for hosted or human review after review request publication.",
        "review-complete": "Workflow is complete.",
    }
    rows = [[state, handoff_reasons.get(state, "stop automatic GCW progression")] for state in contracts["HUMAN_REVIEW_REQUIRED_STATES"]]
    return "\n".join(table_lines(["State", "Reason"], rows))


def render_step_matrix(contracts: dict[str, Any]) -> str:
    rows = []
    for step in contracts["MAIN_STEP_ORDER"]:
        workflow_file = f"{step}.yml"
        rows.append(
            [
                step,
                workflow_file,
                contracts["STEP_TRIGGER_LABELS"].get(step, ""),
            ]
        )
    return "\n".join(table_lines(["GCW step", "Workflow file", "Trigger label"], rows))


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
    if not pattern.search(text):
        raise RuntimeError(f"missing markers {start_marker} ... {end_marker}")
    return pattern.sub(f"{start_marker}\n{replacement}\n{end_marker}", text)


def render_docs() -> dict[Path, str]:
    contracts = load_contracts()
    return {
        Path(__file__).resolve().parents[1] / "README.md": replace_block(
            (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8"),
            "<!-- gcw-contract:main-step-order:start -->",
            "<!-- gcw-contract:main-step-order:end -->",
            render_main_step_order(contracts),
        ),
        Path(__file__).resolve().parents[1] / "docs" / "workflow.md": replace_block(
            (Path(__file__).resolve().parents[1] / "docs" / "workflow.md").read_text(encoding="utf-8"),
            "<!-- gcw-contract:states:start -->",
            "<!-- gcw-contract:states:end -->",
            render_states(contracts),
        ),
        Path(__file__).resolve().parents[1] / "docs" / "hosted-agent.md": replace_block(
            (Path(__file__).resolve().parents[1] / "docs" / "hosted-agent.md").read_text(encoding="utf-8"),
            "<!-- gcw-contract:step-matrix:start -->",
            "<!-- gcw-contract:step-matrix:end -->",
            render_step_matrix(contracts),
        ),
        Path(__file__).resolve().parents[1] / ".agents" / "skills" / "gcw" / "SKILL.md": replace_block(
            (Path(__file__).resolve().parents[1] / ".agents" / "skills" / "gcw" / "SKILL.md").read_text(encoding="utf-8"),
            "<!-- gcw-contract:human-handoff:start -->",
            "<!-- gcw-contract:human-handoff:end -->",
            render_human_handoff_states(contracts),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render GCW contract docs from canonical runtime constants.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rendered = render_docs()
    if args.check and not args.write:
        changed = []
        for path, new_text in rendered.items():
            if path.read_text(encoding="utf-8") != new_text:
                changed.append(str(path))
        if changed:
            raise SystemExit("contract docs drifted: " + ", ".join(changed))
        return 0
    if args.write:
        for path, new_text in rendered.items():
            path.write_text(new_text, encoding="utf-8")
        return 0
    for path, new_text in rendered.items():
        path.write_text(new_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
