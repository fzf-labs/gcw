import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { access, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
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
    assert.match(stdout, /Would copy \.gcw\/runtime\/gcw_workflow_contracts\.py/);
    assert.equal(await exists(path.join(target, ".agents", "skills", "gcw", "SKILL.md")), false);
    assert.equal(await exists(path.join(target, ".gcw", "runtime", "gcw_workflow_contracts.py")), false);
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
    assert.equal(await exists(path.join(target, ".gcw", "runtime", "gcw_workflow_contracts.py")), true);
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
    assert.equal(await exists(path.join(hostedTarget, ".github", "workflows", "gcw-spec-check.yml")), true);
    assert.equal(await exists(path.join(hostedTarget, ".github", "actions", "gcw-setup", "action.yml")), true);
  } finally {
    await cleanup(defaultTarget);
    await cleanup(hostedTarget);
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

test("npm build creates package templates without runtime issue state", async () => {
  await execFileAsync("npm", ["run", "build"], { cwd: repoRoot });

  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".agents", "skills", "gcw", "SKILL.md")), true);
  assert.equal(
    await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "runtime", "gcw_workflow_contracts.py")),
    true,
  );
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "issues")), false);
  assert.equal(await exists(path.join(repoRoot, "dist", "templates", "repo", ".gcw", "runtime", "__pycache__")), false);
});
