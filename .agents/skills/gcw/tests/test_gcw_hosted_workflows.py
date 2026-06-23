from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import yaml
import json

ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = ROOT / ".github" / "workflows"
CODEX_ACTION = ROOT / ".github" / "actions" / "gcw-run-codex" / "action.yml"
SCRIPTS = ROOT / ".gcw" / "engine" / "hosted"
GITLAB_CI = ROOT / ".gitlab-ci.yml"
sys.path.insert(0, str(ROOT / ".gcw" / "engine" / "runtime"))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/scripts"))

from prepare_gcw_hosted_step import prepare  # noqa: E402
from gcw_executor_gate import EXECUTOR_HOSTED, EXECUTOR_LOCAL  # noqa: E402
from gcw_skip_diagnostics import (  # noqa: E402
    SKIP_GATE_EXECUTOR,
    SKIP_GATE_IDEMPOTENT,
    SKIP_GATE_PHASE,
    attach_skip_gate,
    classify_skip_gate,
    format_skip_summary,
)
from report_gcw_skip import main as report_skip_main  # noqa: E402


EXPECTED_WORKFLOWS = {
    "gcw-issue-triage.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "gcw-run-codex",
            "apply_triage_from_handoff.py",
            "run_gcw_step.py --step gcw-issue-triage",
        ],
    },
    "gcw-issue-clarify.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "gcw-run-codex",
            "build_clarify_options.py",
            "run_gcw_step.py --step gcw-issue-clarify",
        ],
    },
    "gcw-issue-to-spec.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "prepare_issue_handoff_context.py",
            "gcw-run-codex",
            "finalize_gcw_hosted_step.py",
            "run_gcw_step.py --step gcw-issue-to-spec",
        ],
    },
    "gcw-spec-check.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "validate_gcw_evidence.py workflow",
            "run_gcw_step.py --step gcw-spec-check",
        ],
    },
    "gcw-implement.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "gcw-run-codex",
            "record_implement_milestone.py",
        ],
    },
    "gcw-implement-check.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "gcw-run-codex",
            "run_gcw_step.py --step gcw-implement-check",
        ],
    },
    "gcw-pr-publish.yml": {
        "permissions": {"contents": "read", "issues": "write", "pull-requests": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "finalize_gcw_hosted_step.py upsert-pr",
            "run_gcw_step.py --step gcw-pr-publish",
        ],
    },
    "gcw-pr-review.yml": {
        "permissions": {"contents": "write", "issues": "write", "pull-requests": "read"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "validate_gcw_evidence.py workflow",
            "run_gcw_step.py --step gcw-pr-review",
        ],
    },
}

HOSTED_AGENT_WORKFLOWS = {
    "gcw-issue-triage.yml",
    "gcw-issue-clarify.yml",
    "gcw-issue-to-spec.yml",
    "gcw-implement.yml",
    "gcw-implement-check.yml",
}

CODEX_WORKFLOWS = HOSTED_AGENT_WORKFLOWS | {"gcw-pr-review.yml"}


def workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def workflow_data(name: str) -> dict:
    return yaml.safe_load(workflow_text(name))


def workflow_triggers(name: str) -> dict:
    data = workflow_data(name)
    return data.get("on") or data[True]


class HostedWorkflowYamlTest(unittest.TestCase):
    def test_all_expected_workflow_files_exist(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            self.assertTrue((WORKFLOWS / name).is_file(), msg=name)

    def test_workflows_use_workflow_dispatch_inputs(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            dispatch = workflow_triggers(name)["workflow_dispatch"]
            self.assertIn("issue_number", dispatch["inputs"], msg=name)
            self.assertIn("issue_branch", dispatch["inputs"], msg=name)
            self.assertIn("dry_run", dispatch["inputs"], msg=name)
            self.assertNotIn("execution_mode", dispatch["inputs"], msg=name)

    def test_workflows_are_hosted_agent_only(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            text = workflow_text(name)
            self.assertNotIn("execution_mode", text, msg=name)
            self.assertNotIn("local-handoff", text, msg=name)

    def test_workflows_declare_event_triggers(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            triggers = workflow_triggers(name)
            self.assertIn("issues", triggers, msg=name)
            self.assertIn("issue_comment", triggers, msg=name)

    def test_workflows_declare_permissions_and_required_commands(self) -> None:
        for name, expected in EXPECTED_WORKFLOWS.items():
            data = workflow_data(name)
            self.assertEqual(data["permissions"], expected["permissions"], msg=name)
            text = workflow_text(name)
            for command in expected["commands"]:
                self.assertIn(command, text, msg=f"{name}: {command}")

    def test_workflows_use_shared_gcw_hosted_directory(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            text = workflow_text(name)
            self.assertIn("python3 .gcw/engine/hosted/", text, msg=name)
            self.assertNotIn(".github/scripts", text, msg=name)
            self.assertNotIn(".gcw/scripts", text, msg=name)

    def test_shared_setup_action_is_used(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            self.assertIn("./.github/actions/gcw-setup", workflow_text(name), msg=name)

    def test_hosted_agent_workflows_include_codex_action(self) -> None:
        for name in HOSTED_AGENT_WORKFLOWS:
            self.assertIn("gcw-run-codex", workflow_text(name), msg=name)

    def test_codex_wrapper_passes_model_and_effort_variables(self) -> None:
        text = CODEX_ACTION.read_text(encoding="utf-8")
        self.assertIn("model: ${{ vars.CODEX_MODEL }}", text)
        self.assertIn("effort: ${{ vars.CODEX_EFFORT }}", text)

    def test_issue_event_workflows_gate_executor_labels_in_job_if(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            text = workflow_text(name)
            self.assertIn("contains(github.event.issue.labels.*.name, 'gcw:executor-hosted')", text, msg=name)
            self.assertIn("!contains(github.event.issue.labels.*.name, 'gcw:executor-local')", text, msg=name)

    def test_codex_workflows_upload_handoff_artifacts(self) -> None:
        for name in CODEX_WORKFLOWS:
            text = workflow_text(name)
            self.assertIn("actions/upload-artifact@", text, msg=name)
            self.assertIn(".gcw-runtime/handoff", text, msg=name)

    def test_pr_review_uses_preflight_job_before_review_work(self) -> None:
        data = workflow_data("gcw-pr-review.yml")
        jobs = data["jobs"]
        self.assertIn("preflight", jobs)
        self.assertIn("pr-review", jobs)
        self.assertEqual(jobs["pr-review"]["needs"], "preflight")
        self.assertIn("needs.preflight.outputs.should_trigger == 'true'", jobs["pr-review"]["if"])

    def test_triage_workflow_splits_preflight_classify_finalize(self) -> None:
        data = workflow_data("gcw-issue-triage.yml")
        jobs = data["jobs"]
        self.assertIn("preflight", jobs)
        self.assertIn("classify", jobs)
        self.assertIn("finalize", jobs)
        self.assertEqual(jobs["classify"]["needs"], "preflight")
        self.assertEqual(jobs["finalize"]["needs"], ["preflight", "classify"])

    def test_triage_workflow_bootstraps_missing_issue_branch(self) -> None:
        data = workflow_data("gcw-issue-triage.yml")
        preflight_steps = data["jobs"]["preflight"]["steps"]
        self.assertFalse(
            any(step.get("name") == "Checkout issue branch" for step in preflight_steps if isinstance(step, dict))
        )

        text = workflow_text("gcw-issue-triage.yml")
        self.assertIn("Create or switch issue branch", text)
        self.assertIn("git fetch origin \"$issue_branch:refs/remotes/origin/$issue_branch\"", text)
        self.assertIn("git switch --track -c \"$issue_branch\" \"origin/$issue_branch\"", text)
        self.assertIn("git switch -c \"$issue_branch\"", text)
        self.assertIn('"issue": "${{ needs.preflight.outputs.issue_number }}"', text)
        self.assertIn('"platform": "github"', text)
        self.assertIn('"repository": "${{ github.repository }}"', text)
        self.assertIn('"branch": "${{ needs.preflight.outputs.issue_branch }}"', text)
        self.assertIn('"owner_kind": "github-actions"', text)


class GitLabCiTemplateTest(unittest.TestCase):
    EXPECTED_JOBS = (
        "gcw:issue-triage",
        "gcw:issue-clarify",
        "gcw:issue-to-spec",
        "gcw:spec-check",
        "gcw:implement",
        "gcw:implement-check",
        "gcw:pr-publish",
        "gcw:pr-review",
    )

    def template_text(self) -> str:
        return GITLAB_CI.read_text(encoding="utf-8")

    def template_data(self) -> dict:
        return yaml.safe_load(self.template_text())

    def test_gitlab_ci_template_exists_with_gcw_jobs(self) -> None:
        self.assertTrue(GITLAB_CI.is_file())
        data = self.template_data()
        for job in self.EXPECTED_JOBS:
            self.assertIn(job, data)

    def test_gitlab_ci_template_defines_trigger_contract(self) -> None:
        text = self.template_text()
        for token in (
            "GCW_ISSUE_NUMBER",
            "GCW_ISSUE_BRANCH",
            "GCW_DRY_RUN",
            "GCW_EXECUTOR",
            "gcw:executor-hosted",
            "gcw:executor-local",
            "GLAB_TOKEN",
            "--issue-labels \"$GCW_EXECUTOR\"",
        ):
            self.assertIn(token, text)

    def test_gitlab_ci_template_delegates_to_existing_gcw_scripts(self) -> None:
        text = self.template_text()
        self.assertIn("python3 .gcw/engine/hosted/", text)
        self.assertNotIn(".github/scripts", text)
        self.assertNotIn(".gcw/scripts", text)
        for command in (
            "glab",
            "prepare_gcw_hosted_step.py",
            "validate_gcw_evidence.py workflow",
            "run_gcw_step.py --step gcw-issue-triage",
            "run_gcw_step.py --step gcw-issue-clarify",
            "run_gcw_step.py --step gcw-issue-to-spec",
            "run_gcw_step.py --step gcw-spec-check",
            "record_implement_milestone.py",
            "run_gcw_step.py --step gcw-implement-check",
            "run_gcw_step.py --step gcw-pr-publish",
            "run_gcw_step.py --step gcw-pr-review",
        ):
            self.assertIn(command, text)

    def test_gitlab_ci_triage_bootstraps_missing_issue_branch(self) -> None:
        text = self.template_text()
        self.assertIn('if git fetch origin "$GCW_RESOLVED_BRANCH:refs/remotes/origin/$GCW_RESOLVED_BRANCH"; then', text)
        self.assertIn('git switch --track -c "$GCW_RESOLVED_BRANCH" "origin/$GCW_RESOLVED_BRANCH"', text)
        self.assertIn('git switch -c "$GCW_RESOLVED_BRANCH"', text)
        self.assertIn('if [ "$GCW_STEP" != "gcw-issue-triage" ]; then', text)
        self.assertIn('"issue": os.environ["GCW_ISSUE_NUMBER"]', text)
        self.assertIn('"platform": "gitlab"', text)
        self.assertIn('"repository": os.environ["CI_PROJECT_PATH"]', text)
        self.assertIn('"branch": os.environ["GCW_RESOLVED_BRANCH"]', text)
        self.assertIn('"owner_kind": "gitlab-ci"', text)


class PrepareHostedStepTest(unittest.TestCase):
    def test_prepare_bootstraps_triage_when_issue_state_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / ".gcw" / "issues" / "88"
            result = prepare(
                "gcw-issue-triage",
                issue_dir,
                "88",
                "",
                issue_labels=[EXECUTOR_HOSTED],
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result["should_run"])
        self.assertEqual(result["phase"], "")
        self.assertEqual(result["issue_branch"], "gcw/issue-88")
        self.assertEqual(result["executor_gate"], EXECUTOR_HOSTED)

    def test_prepare_blocks_triage_bootstrap_with_local_executor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / ".gcw" / "issues" / "88"
            result = prepare(
                "gcw-issue-triage",
                issue_dir,
                "88",
                "",
                issue_labels=[EXECUTOR_HOSTED, EXECUTOR_LOCAL],
            )
        self.assertTrue(result["ok"])
        self.assertFalse(result["should_run"])
        self.assertIn(EXECUTOR_LOCAL, result["skip_reason"])

    def test_prepare_allows_implement_from_implementing(self) -> None:
        issue_dir = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        projection = json.loads((issue_dir / "workflow.json").read_text(encoding="utf-8"))
        projection["projection"]["phase"] = "implementing"
        projection["projection"]["last_completed_step"] = "gcw-implement"
        projection["projection"]["next_allowed_steps"] = ["gcw-implement", "gcw-implement-check"]
        with tempfile.TemporaryDirectory() as temp_root:
            temp_dir = Path(temp_root) / "prepare-implement"
            temp_dir.mkdir(parents=True, exist_ok=True)
            (temp_dir / "workflow.json").write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
            shutil.copytree(issue_dir / "events", temp_dir / "events")
            result = prepare("gcw-implement", temp_dir, "99", "gcw/issue-99", issue_labels=[EXECUTOR_HOSTED])
            self.assertTrue(result["should_run"])
            self.assertEqual(result["issue_branch"], "gcw/issue-99")

    def test_prepare_blocks_spec_check_while_implementing(self) -> None:
        issue_dir = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        projection = json.loads((issue_dir / "workflow.json").read_text(encoding="utf-8"))
        projection["projection"]["phase"] = "implementing"
        projection["projection"]["last_completed_step"] = "gcw-implement"
        with tempfile.TemporaryDirectory() as temp_root:
            temp_dir = Path(temp_root) / "prepare-spec-check"
            temp_dir.mkdir(parents=True, exist_ok=True)
            (temp_dir / "workflow.json").write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
            shutil.copytree(issue_dir / "events", temp_dir / "events")
            result = prepare("gcw-spec-check", temp_dir, "99", "", issue_labels=[EXECUTOR_HOSTED])
            self.assertFalse(result["should_run"])
            self.assertIn("superseded", result["skip_reason"])

    def test_prepare_blocks_without_executor_hosted(self) -> None:
        issue_dir = ROOT / ".gcw/issues/12"
        result = prepare(
            "gcw-spec-check",
            issue_dir,
            "12",
            "",
            issue_labels=[EXECUTOR_LOCAL],
        )
        self.assertFalse(result["should_run"])
        self.assertIn(EXECUTOR_LOCAL, result["skip_reason"])

    def test_prepare_accepts_explicit_issue_labels_for_gitlab_ci(self) -> None:
        fixture_dir = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        projection = json.loads((fixture_dir / "workflow.json").read_text(encoding="utf-8"))
        projection["projection"]["phase"] = "ready-for-implementation"
        projection["projection"]["last_completed_step"] = "gcw-spec-check"
        projection["projection"]["next_allowed_steps"] = ["gcw-implement"]
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / "issue"
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "workflow.json").write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
            result = prepare(
                "gcw-implement",
                issue_dir,
                "17",
                "",
                issue_labels=[EXECUTOR_HOSTED],
            )
            self.assertTrue(result["should_run"])
            self.assertEqual(result["executor_gate"], EXECUTOR_HOSTED)

    def test_prepare_allows_implement_with_executor_hosted(self) -> None:
        fixture_dir = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        projection = json.loads((fixture_dir / "workflow.json").read_text(encoding="utf-8"))
        projection["projection"]["phase"] = "ready-for-implementation"
        projection["projection"]["last_completed_step"] = "gcw-spec-check"
        projection["projection"]["next_allowed_steps"] = ["gcw-implement"]
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / "issue"
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "workflow.json").write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
            result = prepare(
                "gcw-implement",
                issue_dir,
                "17",
                "",
                issue_labels=[EXECUTOR_HOSTED],
            )
            self.assertTrue(result["should_run"])
            self.assertEqual(result["executor_gate"], EXECUTOR_HOSTED)

    def test_prepare_pr_review_verify_only_when_already_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / "issue"
            shutil.copytree(ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue", issue_dir)
            from manage_gcw_workflow import main as manage_main  # noqa: E402

            def run_manager(*args: str) -> None:
                manage_main(list(args))

            run_manager(
                "record-pr-publish",
                "--issue-dir",
                str(issue_dir),
                "--review-request-url",
                "https://github.com/owner/repo/pull/7",
                "--body-hash",
                "sha256:" + "a" * 64,
                "--target",
                "owner/repo#7",
                "--progress-comment-url",
                "https://github.com/owner/repo/issues/42#issuecomment-6",
            )
            run_manager(
                "record-pr-review",
                "--issue-dir",
                str(issue_dir),
                "--result",
                "passed",
                "--progress-comment-url",
                "https://github.com/owner/repo/issues/42#issuecomment-7",
            )
            result = prepare(
                "gcw-pr-review",
                issue_dir,
                "42",
                "",
                issue_labels=[EXECUTOR_HOSTED],
            )
        self.assertTrue(result["should_run"])
        self.assertEqual(result["run_mode"], "verify-only")
        self.assertEqual(result["validate_command"], "review-check")
        self.assertFalse(result["record_step"])

    def test_prepare_skips_completed_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / "issue"
            shutil.copytree(ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue", issue_dir)
            from manage_gcw_workflow import main as manage_main  # noqa: E402

            manage_main(
                [
                    "record-pr-publish",
                    "--issue-dir",
                    str(issue_dir),
                    "--review-request-url",
                    "https://github.com/owner/repo/pull/7",
                    "--body-hash",
                    "sha256:" + "a" * 64,
                    "--target",
                    "owner/repo#7",
                    "--progress-comment-url",
                    "https://github.com/owner/repo/issues/42#issuecomment-6",
                ]
            )
            result = prepare(
                "gcw-pr-publish",
                issue_dir,
                "42",
                "",
                issue_labels=[EXECUTOR_HOSTED],
            )
        self.assertFalse(result["should_run"])
        self.assertIn("already completed", result["skip_reason"])


class SkipDiagnosticsTest(unittest.TestCase):
    def test_classify_executor_local_skip(self) -> None:
        reason = f"{EXECUTOR_LOCAL} blocks hosted execution"
        self.assertEqual(classify_skip_gate(reason), SKIP_GATE_EXECUTOR)

    def test_classify_phase_skip(self) -> None:
        reason = "phase 'planned' is not in [ready-for-implementation] for gcw-implement"
        self.assertEqual(classify_skip_gate(reason), SKIP_GATE_PHASE)

    def test_classify_idempotent_skip(self) -> None:
        self.assertEqual(classify_skip_gate("gcw-spec-check already completed"), SKIP_GATE_IDEMPOTENT)
        self.assertEqual(classify_skip_gate("superseded by gcw-pr-publish"), SKIP_GATE_IDEMPOTENT)

    def test_format_skip_summary_includes_gate_label(self) -> None:
        summary = format_skip_summary(
            step="gcw-spec-check",
            skip_gate=SKIP_GATE_PHASE,
            skip_reason="phase 'planned' is not in [ready-for-implementation] for gcw-implement",
            phase="planned",
        )
        self.assertIn("Gate: phase gate", summary)
        self.assertIn("Phase: planned", summary)
        self.assertIn("What to check:", summary)

    def test_prepare_attaches_skip_gate_for_executor_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / ".gcw" / "issues" / "88"
            result = prepare(
                "gcw-issue-triage",
                issue_dir,
                "88",
                "",
                issue_labels=[EXECUTOR_LOCAL],
            )
        enriched = attach_skip_gate(result)
        self.assertEqual(enriched["skip_gate"], SKIP_GATE_EXECUTOR)

    def test_report_skip_reads_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            env_path = Path(temp_root) / "prepare.env"
            env_path.write_text(
                "\n".join(
                    [
                        "should_run=false",
                        "skip_gate=phase",
                        "skip_reason=phase 'planned' is not in [ready-for-implementation] for gcw-implement",
                        "phase=planned",
                        "step=gcw-implement",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            from io import StringIO

            captured = StringIO()
            with unittest.mock.patch("sys.stdout", captured):
                exit_code = report_skip_main(["--env-file", str(env_path)])
        self.assertEqual(exit_code, 0)
        output = captured.getvalue()
        self.assertIn("GCW hosted skip: gcw-implement", output)
        self.assertIn("Gate: phase gate", output)


if __name__ == "__main__":
    unittest.main()
