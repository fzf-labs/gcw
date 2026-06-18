import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { access, chmod, cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";

const execFileAsync = promisify(execFile);
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cliPath = path.join(repoRoot, "bin", "gcw.js");

async function runCli(args, options = {}) {
  return execFileAsync(process.execPath, [cliPath, ...args], {
    cwd: options.cwd ?? repoRoot,
    env: { ...process.env, ...(options.env ?? {}) },
  });
}

async function tempDir() {
  return mkdtemp(path.join(os.tmpdir(), "gcw-cli-test-"));
}

async function cleanup(dir) {
  await rm(dir, { recursive: true, force: true });
}

async function readPackage() {
  return JSON.parse(await readFile(path.join(repoRoot, "package.json"), "utf8"));
}

async function exists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function copyCompleteIssueFixture(targetRoot) {
  const fixtureRoot = path.join(repoRoot, ".agents", "skills", "gcw", "tests", "fixtures", "complete_issue");
  const issueDir = path.join(targetRoot, ".gcw", "issues", "42");
  await cp(fixtureRoot, issueDir, { recursive: true });
  return issueDir;
}

async function createFakeGhEnv(options = {}) {
  const binDir = await tempDir();
  const statePath = path.join(binDir, "gh-state.json");
  const repo = options.repo ?? "owner/repo";
  const issue = String(options.issue ?? "42");
  const title = options.title ?? "Add formal GCW CLI commands";
  const body =
    options.body ??
    `## What to build

Add formal terminal-first GCW commands.

## Acceptance criteria

- [ ] route the workflow

## Blocked by

None - can start immediately
`;
  const labels = options.labels ?? [];
  const issueUrl = options.issueUrl ?? `https://github.com/${repo}/issues/${issue}`;

  await writeFile(
    statePath,
    `${JSON.stringify({ repo, issue, title, body, labels, issueUrl, comments: 0, prs: [] }, null, 2)}\n`,
    "utf8",
  );

  const ghScript = path.join(binDir, "gh");
  await writeFile(
    ghScript,
    `#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");

const statePath = ${JSON.stringify(statePath)};
const args = process.argv.slice(2);
const state = JSON.parse(fs.readFileSync(statePath, "utf8"));

function save(next) {
  fs.writeFileSync(statePath, JSON.stringify(next, null, 2) + "\\n", "utf8");
}

function argValue(flag) {
  const index = args.indexOf(flag);
  return index === -1 ? "" : (args[index + 1] || "");
}

function printJson(value) {
  process.stdout.write(JSON.stringify(value));
}

if (args[0] === "--version") {
  process.stdout.write("gh fake\\n");
  process.exit(0);
}

if (args[0] === "issue" && args[1] === "view") {
  const jsonFields = argValue("--json");
  const jq = argValue("--jq");
  if (jsonFields === "labels" && jq === ".labels[].name") {
    process.stdout.write((state.labels || []).join("\\n"));
    process.exit(0);
  }
  if (jsonFields === "body" && jq === ".body") {
    process.stdout.write(state.body);
    process.exit(0);
  }
  printJson({
    title: state.title,
    body: state.body,
    labels: (state.labels || []).map((name) => ({ name })),
    url: state.issueUrl,
    html_url: state.issueUrl,
    number: Number(state.issue),
  });
  process.exit(0);
}

if (args[0] === "issue" && args[1] === "edit") {
  const addLabels = argValue("--add-label").split(",").map((x) => x.trim()).filter(Boolean);
  const removeLabels = argValue("--remove-label").split(",").map((x) => x.trim()).filter(Boolean);
  const next = { ...state, labels: [...(state.labels || [])] };
  for (const label of addLabels) {
    if (!next.labels.includes(label)) next.labels.push(label);
  }
  next.labels = next.labels.filter((label) => !removeLabels.includes(label));
  save(next);
  process.exit(0);
}

if (args[0] === "issue" && args[1] === "comment") {
  const next = { ...state, comments: Number(state.comments || 0) + 1 };
  save(next);
  process.stdout.write(\`https://github.com/\${state.repo}/issues/\${state.issue}#issuecomment-\${next.comments}\\n\`);
  process.exit(0);
}

if (args[0] === "api") {
  const endpoint = args[1] || "";
  if (endpoint === \`repos/\${state.repo}\`) {
    printJson({ id: 1 });
    process.exit(0);
  }
  printJson({});
  process.exit(0);
}

if (args[0] === "pr" && args[1] === "list") {
  if ((args.length - 2) % 2 !== 0) {
    process.stderr.write("unsupported fake gh invocation: " + args.join(" ") + "\\n");
    process.exit(1);
  }
  printJson(state.prs || []);
  process.exit(0);
}

if (args[0] === "pr" && args[1] === "create") {
  const head = argValue("--head");
  const title = argValue("--title");
  const url = \`https://github.com/\${state.repo}/pull/\${(state.prs || []).length + 1}\`;
  const next = { ...state, prs: [...(state.prs || []), { url, title, head }] };
  save(next);
  process.stdout.write(url + "\\n");
  process.exit(0);
}

if (args[0] === "pr" && args[1] === "edit") {
  process.exit(0);
}

process.stderr.write("unsupported fake gh invocation: " + args.join(" ") + "\\n");
process.exit(1);
`,
    "utf8",
  );
  await chmod(ghScript, 0o755);

  return {
    ...process.env,
    PATH: `${binDir}${path.delimiter}${process.env.PATH}`,
  };
}

test("gcw --version prints the package version", async () => {
  const pkg = await readPackage();

  const { stdout } = await runCli(["--version"]);

  assert.equal(stdout.trim(), pkg.version);
});

test("gcw init --dry-run reports required assets without writing them", async () => {
  const target = await tempDir();
  try {
    const { stdout } = await runCli(["init", "--target", target, "--dry-run"]);

    assert.match(stdout, /Would copy \.agents\/skills\/gcw\/SKILL\.md/);
    assert.match(stdout, /Would copy \.gcw\/engine\/runtime\/gcw_workflow_contracts\.py/);
    assert.equal(await exists(path.join(target, ".agents", "skills", "gcw", "SKILL.md")), false);
    assert.equal(await exists(path.join(target, ".gcw", "engine", "runtime", "gcw_workflow_contracts.py")), false);
  } finally {
    await cleanup(target);
  }
});

test("gcw init copies required repo-local assets", async () => {
  const target = await tempDir();
  try {
    const { stdout } = await runCli(["init", "--target", target]);

    assert.match(stdout, /Copied \.agents\/skills\/gcw\/SKILL\.md/);
    assert.equal(await exists(path.join(target, ".agents", "skills", "gcw", "SKILL.md")), true);
    assert.equal(await exists(path.join(target, ".gcw", "engine", "runtime", "gcw_workflow_contracts.py")), true);
    assert.equal(await exists(path.join(target, ".gcw", "engine", "platforms", "github.py")), true);
    assert.equal(await exists(path.join(target, ".gcw", "issues")), false);
  } finally {
    await cleanup(target);
  }
});

test("gcw init skips existing files unless --force is set", async () => {
  const target = await tempDir();
  const skillPath = path.join(target, ".agents", "skills", "gcw", "SKILL.md");
  try {
    await runCli(["init", "--target", target]);
    await writeFile(skillPath, "local edit\n", "utf8");

    const skipped = await runCli(["init", "--target", target]);
    assert.match(skipped.stdout, /Skipped \.agents\/skills\/gcw\/SKILL\.md/);
    assert.equal(await readFile(skillPath, "utf8"), "local edit\n");

    const forced = await runCli(["init", "--target", target, "--force"]);
    assert.match(forced.stdout, /Overwrote \.agents\/skills\/gcw\/SKILL\.md/);
    assert.notEqual(await readFile(skillPath, "utf8"), "local edit\n");
  } finally {
    await cleanup(target);
  }
});

test("gcw init installs GitHub Actions assets only when requested", async () => {
  const defaultTarget = await tempDir();
  const hostedTarget = await tempDir();
  try {
    await runCli(["init", "--target", defaultTarget]);
    assert.equal(await exists(path.join(defaultTarget, ".github", "workflows", "gcw-spec-check.yml")), false);

    const { stdout } = await runCli(["init", "--target", hostedTarget, "--with-github-actions"]);
    assert.match(stdout, /Copied \.github\/workflows\/gcw-spec-check\.yml/);
    assert.match(stdout, /Copied \.gcw\/engine\/hosted\/prepare_gcw_hosted_step\.py/);
    assert.equal(await exists(path.join(hostedTarget, ".github", "workflows", "gcw-spec-check.yml")), true);
    assert.equal(await exists(path.join(hostedTarget, ".github", "actions", "gcw-setup", "action.yml")), true);
    assert.equal(await exists(path.join(hostedTarget, ".gcw", "engine", "hosted", "prepare_gcw_hosted_step.py")), true);
  } finally {
    await cleanup(defaultTarget);
    await cleanup(hostedTarget);
  }
});

test("gcw init installs GitLab CI template only when requested", async () => {
  const defaultTarget = await tempDir();
  const gitlabTarget = await tempDir();
  try {
    await runCli(["init", "--target", defaultTarget]);
    assert.equal(await exists(path.join(defaultTarget, ".gitlab-ci.yml")), false);

    const { stdout } = await runCli(["init", "--target", gitlabTarget, "--with-gitlab-ci"]);
    assert.match(stdout, /Copied \.gitlab-ci\.yml/);
    assert.match(stdout, /Copied \.gcw\/engine\/hosted\/prepare_gcw_hosted_step\.py/);
    assert.equal(await exists(path.join(gitlabTarget, ".gitlab-ci.yml")), true);
    assert.equal(await exists(path.join(gitlabTarget, ".gcw", "engine", "hosted", "prepare_gcw_hosted_step.py")), true);
  } finally {
    await cleanup(defaultTarget);
    await cleanup(gitlabTarget);
  }
});

test("gcw doctor reports initialized repository health", async () => {
  const target = await tempDir();
  try {
    await execFileAsync("git", ["init"], { cwd: target });
    await runCli(["init", "--target", target]);

    const { stdout } = await runCli(["doctor", "--target", target]);

    assert.match(stdout, /Git repository: ok/);
    assert.match(stdout, /GCW assets: ok/);
    assert.match(stdout, /python3: ok/);
  } finally {
    await cleanup(target);
  }
});

test("gcw status prints the current projection phase and next steps", async () => {
  const target = await tempDir();
  try {
    await copyCompleteIssueFixture(target);

    const { stdout } = await runCli(["status", "42"], { cwd: target });

    assert.match(stdout, /Issue: 42/);
    assert.match(stdout, /Phase: ready-for-review/);
    assert.match(stdout, /Last completed step: gcw-implement-check/);
    assert.match(stdout, /Next allowed steps: gcw-pr-publish/);
  } finally {
    await cleanup(target);
  }
});

test("gcw next prints the next allowed step for a planned issue", async () => {
  const target = await tempDir();
  try {
    const issueDir = await copyCompleteIssueFixture(target);
    await rm(path.join(issueDir, "events", "004-gcw-spec-check.json"));
    await rm(path.join(issueDir, "events", "005-gcw-implement.json"));
    await rm(path.join(issueDir, "events", "006-gcw-implement-check.json"));
    await execFileAsync(
      "python3",
      [path.join(repoRoot, ".agents", "skills", "gcw", "scripts", "manage_gcw_workflow.py"), "rebuild-projection", "--issue-dir", issueDir],
      { cwd: target },
    );

    const { stdout } = await runCli(["next", "42"], { cwd: target });

    assert.match(stdout, /Issue: 42/);
    assert.match(stdout, /Phase: planned/);
    assert.match(stdout, /Next step: gcw-spec-check/);
  } finally {
    await cleanup(target);
  }
});

test("gcw step runs one supported step from the current phase", async () => {
  const target = await tempDir();
  try {
    const issueDir = await copyCompleteIssueFixture(target);
    const env = await createFakeGhEnv();
    await rm(path.join(issueDir, "events", "004-gcw-spec-check.json"));
    await rm(path.join(issueDir, "events", "005-gcw-implement.json"));
    await rm(path.join(issueDir, "events", "006-gcw-implement-check.json"));
    await execFileAsync(
      "python3",
      [path.join(repoRoot, ".agents", "skills", "gcw", "scripts", "manage_gcw_workflow.py"), "rebuild-projection", "--issue-dir", issueDir],
      { cwd: target, env },
    );

    const { stdout } = await runCli(["step", "gcw-spec-check", "42"], { cwd: target, env });

    assert.match(stdout, /Executed: gcw-spec-check/);
    assert.match(stdout, /Phase: ready-for-implementation/);
    assert.match(stdout, /Last completed step: gcw-spec-check/);
    assert.match(stdout, /Next allowed steps: gcw-implement/);
  } finally {
    await cleanup(target);
  }
});

test("gcw step returns a non-zero error for an illegal phase transition", async () => {
  const target = await tempDir();
  try {
    const issueDir = await copyCompleteIssueFixture(target);
    const env = await createFakeGhEnv();
    await rm(path.join(issueDir, "events", "004-gcw-spec-check.json"));
    await rm(path.join(issueDir, "events", "005-gcw-implement.json"));
    await rm(path.join(issueDir, "events", "006-gcw-implement-check.json"));
    await execFileAsync(
      "python3",
      [path.join(repoRoot, ".agents", "skills", "gcw", "scripts", "manage_gcw_workflow.py"), "rebuild-projection", "--issue-dir", issueDir],
      { cwd: target, env },
    );

    await assert.rejects(
      runCli(["step", "gcw-pr-publish", "42"], { cwd: target, env }),
      (error) => {
        assert.equal(error.code, 1);
        assert.match(error.stderr, /step gcw-pr-publish is not allowed in phase planned/);
        return true;
      },
    );
  } finally {
    await cleanup(target);
  }
});

test("gcw run routes from an existing issue to the planned handoff state", async () => {
  const target = await tempDir();
  try {
    await execFileAsync("git", ["init"], { cwd: target });
    await execFileAsync("git", ["config", "user.email", "gcw@example.com"], { cwd: target });
    await execFileAsync("git", ["config", "user.name", "GCW Test"], { cwd: target });
    await execFileAsync("git", ["remote", "add", "origin", "git@github.com:owner/repo.git"], { cwd: target });
    await runCli(["init", "--target", target]);
    const env = await createFakeGhEnv({
      repo: "owner/repo",
      issue: "24",
      title: "Add formal GCW CLI commands",
      body: `## What to build

Add formal terminal-first GCW commands so a user can run the main workflow.

## Acceptance criteria

- [ ] gcw run routes through the state machine
- [ ] gcw step runs exactly one step

## Blocked by

None - can start immediately
`,
    });

    const { stdout } = await runCli(["run", "24"], { cwd: target, env });

    assert.match(stdout, /Issue: 24/);
    assert.match(stdout, /Executed steps: gcw-issue-intake, gcw-issue-triage, gcw-issue-clarify, gcw-issue-to-spec/);
    assert.match(stdout, /Phase: planned/);
    assert.match(stdout, /Last completed step: gcw-issue-to-spec/);
    assert.match(stdout, /Next allowed steps: gcw-spec-check/);
    assert.match(stdout, /Stop reason: Waiting for human spec review before gcw-spec-check\./);
  } finally {
    await cleanup(target);
  }
});

test("gcw run continues from implementing to the reviewing handoff state", async () => {
  const target = await tempDir();
  try {
    const issueDir = await copyCompleteIssueFixture(target);
    const env = await createFakeGhEnv();
    await rm(path.join(issueDir, "events", "006-gcw-implement-check.json"));
    await execFileAsync(
      "python3",
      [path.join(repoRoot, ".agents", "skills", "gcw", "scripts", "manage_gcw_workflow.py"), "rebuild-projection", "--issue-dir", issueDir],
      { cwd: target, env },
    );

    const { stdout } = await runCli(["run", "42"], { cwd: target, env });

    assert.match(stdout, /Issue: 42/);
    assert.match(stdout, /Executed steps: gcw-implement-check, gcw-pr-publish/);
    assert.match(stdout, /Phase: reviewing/);
    assert.match(stdout, /Last completed step: gcw-pr-publish/);
    assert.match(stdout, /Stop reason: Waiting for hosted or human review after review request publication\./);
  } finally {
    await cleanup(target);
  }
});

test("npm build creates package templates without runtime issue state", async () => {
  await execFileAsync("npm", ["run", "build"], { cwd: repoRoot });

  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".agents", "skills", "gcw", "SKILL.md")), true);
  assert.equal(
    await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "engine", "runtime", "gcw_workflow_contracts.py")),
    true,
  );
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "issues")), false);
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "engine", "runtime", "__pycache__")), false);
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "engine", "hosted", "prepare_gcw_hosted_step.py")), true);
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "engine", "platforms", "github.py")), true);
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "scripts")), false);
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".github", "scripts")), false);
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".gitlab-ci.yml")), true);
});
