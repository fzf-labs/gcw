from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CLI = ROOT / ".agents/skills/gcw/scripts/gcw_terminal_cli.py"


class GcwTerminalCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)

    def run_cli(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def fake_gh_env(self) -> dict[str, str]:
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        state_path = Path(self.tmp.name) / "gh-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "repo": "owner/repo",
                    "issue": "42",
                    "title": "Add formal GCW CLI commands",
                    "body": "## What to build\n\nAdd formal terminal-first GCW commands.\n",
                    "labels": [],
                    "issueUrl": "https://github.com/owner/repo/issues/42",
                    "comments": 0,
                    "prs": [],
                }
            ),
            encoding="utf-8",
        )
        gh_script = bin_dir / "gh"
        gh_script.write_text(
            """#!/usr/bin/env node
const fs = require("node:fs");
const statePath = process.env.GCW_GH_STATE;
const state = JSON.parse(fs.readFileSync(statePath, "utf8"));
const args = process.argv.slice(2);
function save(next) { fs.writeFileSync(statePath, JSON.stringify(next, null, 2) + "\\n", "utf8"); }
function argValue(flag) { const index = args.indexOf(flag); return index === -1 ? "" : (args[index + 1] || ""); }
function printJson(value) { process.stdout.write(JSON.stringify(value)); }
if (args[0] === "issue" && args[1] === "view") {
  const jsonFields = argValue("--json");
  const jq = argValue("--jq");
  if (jsonFields === "labels" && jq === ".labels[].name") { process.stdout.write((state.labels || []).join("\\n")); process.exit(0); }
  if (jsonFields === "body" && jq === ".body") { process.stdout.write(state.body); process.exit(0); }
  printJson({ title: state.title, body: state.body, labels: (state.labels || []).map((name) => ({ name })), url: state.issueUrl, html_url: state.issueUrl, number: Number(state.issue) });
  process.exit(0);
}
if (args[0] === "issue" && args[1] === "comment") { const next = { ...state, comments: Number(state.comments || 0) + 1 }; save(next); process.stdout.write(`https://github.com/${state.repo}/issues/${state.issue}#issuecomment-${next.comments}\\n`); process.exit(0); }
if (args[0] === "api") { printJson({ id: 1 }); process.exit(0); }
if (args[0] === "pr" && args[1] === "list") { printJson(state.prs || []); process.exit(0); }
if (args[0] === "pr" && args[1] === "create") { const url = `https://github.com/${state.repo}/pull/${(state.prs || []).length + 1}`; const next = { ...state, prs: [...(state.prs || []), { url }] }; save(next); process.stdout.write(url + "\\n"); process.exit(0); }
if (args[0] === "pr" && args[1] === "edit") { process.exit(0); }
process.stderr.write("unsupported fake gh invocation: " + args.join(" ") + "\\n");
process.exit(1);
""",
            encoding="utf-8",
        )
        gh_script.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env["GCW_GH_STATE"] = str(state_path)
        return env

    def fake_glab_env(self) -> dict[str, str]:
        bin_dir = Path(self.tmp.name) / "bin-glab"
        bin_dir.mkdir(parents=True, exist_ok=True)
        state_path = Path(self.tmp.name) / "glab-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "repo": "group/project",
                    "issue": "42",
                    "title": "Add formal GCW CLI commands",
                    "body": "## What to build\n\nAdd formal terminal-first GCW commands.\n",
                    "labels": [],
                    "issueUrl": "https://gitlab.com/group/project/-/issues/42",
                    "comments": 0,
                    "mrs": [],
                }
            ),
            encoding="utf-8",
        )
        glab_script = bin_dir / "glab"
        glab_script.write_text(
            """#!/usr/bin/env node
const fs = require("node:fs");
const statePath = process.env.GCW_GLAB_STATE;
const state = JSON.parse(fs.readFileSync(statePath, "utf8"));
const args = process.argv.slice(2);
function save(next) { fs.writeFileSync(statePath, JSON.stringify(next, null, 2) + "\\n", "utf8"); }
function argValue(flag) { const index = args.indexOf(flag); return index === -1 ? "" : (args[index + 1] || ""); }
function printJson(value) { process.stdout.write(JSON.stringify(value)); }
if (args[0] === "issue" && args[1] === "view") {
  if (argValue("--output") === "json") {
    printJson({ title: state.title, description: state.body, labels: (state.labels || []).map((name) => ({ name })), web_url: state.issueUrl, iid: Number(state.issue) });
    process.exit(0);
  }
  process.stdout.write(state.body);
  process.exit(0);
}
if (args[0] === "issue" && args[1] === "note") { const next = { ...state, comments: Number(state.comments || 0) + 1 }; save(next); process.stdout.write(`https://gitlab.com/${state.repo}/-/issues/${state.issue}#note_${next.comments}\\n`); process.exit(0); }
if (args[0] === "mr" && args[1] === "list") { printJson(state.mrs || []); process.exit(0); }
if (args[0] === "mr" && args[1] === "create") { const url = `https://gitlab.com/${state.repo}/-/merge_requests/${(state.mrs || []).length + 1}`; const next = { ...state, mrs: [...(state.mrs || []), { url, title: argValue("--title"), sourceBranch: argValue("--source-branch") || argValue("-s"), targetBranch: argValue("--target-branch") || argValue("-b") || "main", description: argValue("--description") }] }; save(next); process.stdout.write(url + "\\n"); process.exit(0); }
if (args[0] === "mr" && args[1] === "update") { const next = { ...state, mrs: state.mrs || [] }; save(next); process.exit(0); }
process.stderr.write("unsupported fake glab invocation: " + args.join(" ") + "\\n");
process.exit(1);
""",
            encoding="utf-8",
        )
        glab_script.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env["GCW_GLAB_STATE"] = str(state_path)
        return env

    def test_status_requires_projection(self) -> None:
        result = self.run_cli("status", "--target", self.tmp.name, "42")
        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data["ok"])
        self.assertTrue(data["errors"])

    def test_run_emits_json_envelope(self) -> None:
        fixture = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        shutil.copytree(fixture, self.issue_dir, dirs_exist_ok=True)
        env = self.fake_gh_env()
        result = self.run_cli("run", "--target", self.tmp.name, "42", env=env)
        data = json.loads(result.stdout)
        self.assertIn("issue", data)
        self.assertIn("phase", data)
        self.assertIn("executed_steps", data)

    def test_run_publishes_gitlab_merge_request(self) -> None:
        fixture = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        shutil.copytree(fixture, self.issue_dir, dirs_exist_ok=True)
        triage_path = self.issue_dir / "events" / "000-gcw-issue-triage.json"
        triage = json.loads(triage_path.read_text(encoding="utf-8"))
        triage["payload"]["platform"] = "gitlab"
        triage["payload"]["repository"] = "group/project"
        triage["payload"]["remote_sync"]["platform"] = "gitlab"
        triage_path.write_text(json.dumps(triage, indent=2) + "\n", encoding="utf-8")
        env = self.fake_glab_env()
        result = self.run_cli("run", "--target", self.tmp.name, "42", env=env)
        data = json.loads(result.stdout)
        self.assertEqual(data["phase"], "reviewing")
        self.assertTrue(data["executed_steps"])


if __name__ == "__main__":
    unittest.main()
