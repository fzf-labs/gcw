import { spawnSync } from "node:child_process";
import { copyFile, mkdir, mkdtemp, readdir, stat, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";

export const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const packageJson = JSON.parse(readFileSync(path.join(packageRoot, "package.json"), "utf8"));

export const requiredAssetRoots = [
  ".agents/skills/gcw",
  ".agents/skills/gcw-issue-triage",
  ".agents/skills/gcw-issue-clarify",
  ".agents/skills/gcw-issue-to-spec",
  ".agents/skills/gcw-spec-check",
  ".agents/skills/gcw-implement",
  ".agents/skills/gcw-implement-check",
  ".agents/skills/gcw-pr-publish",
  ".agents/skills/gcw-pr-review",
  ".agents/skills/planning-with-files",
  ".gcw/engine/runtime",
  ".gcw/engine/platforms",
];

export const githubActionsAssetRoots = [
  ".github/workflows",
  ".github/actions/gcw-setup",
  ".github/actions/gcw-run-codex",
];

export const hostedSharedAssetRoots = [".gcw/engine/hosted"];
export const gitlabCiAssetRoots = [".gitlab-ci.yml"];

export function printVersion() {
  console.log(packageJson.version);
}

export function printHelp() {
  console.log(`GCW workflow orchestrator

Usage:
  gcw <init|doctor|run|step|status|next|help|--version>

Formal commands:
  gcw init <options>         Bootstrap repo-local GCW assets
  gcw doctor <options>       Check local GCW readiness
  gcw status <issue>         Show current workflow state
  gcw next <issue>           Show the next allowed workflow step
  gcw step <step> <issue>    Execute exactly one GCW step
  gcw run <issue>            Advance the workflow until a handoff state
`);
}

export function parseInitArgs(args) {
  const options = {
    target: process.cwd(),
    dryRun: false,
    force: false,
    withGithubActions: false,
    withGitlabCi: false,
  };

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--dry-run") {
      options.dryRun = true;
    } else if (arg === "--force") {
      options.force = true;
    } else if (arg === "--with-github-actions") {
      options.withGithubActions = true;
    } else if (arg === "--with-gitlab-ci") {
      options.withGitlabCi = true;
    } else if (arg === "--target") {
      const value = args[i + 1];
      if (!value) {
        throw new Error("--target requires a path");
      }
      options.target = value;
      i += 1;
    } else {
      throw new Error(`unknown init option: ${arg}`);
    }
  }

  return options;
}

export function parseTargetArgs(args, commandName) {
  const options = { target: process.cwd() };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--target") {
      const value = args[i + 1];
      if (!value) {
        throw new Error("--target requires a path");
      }
      options.target = value;
      i += 1;
    } else {
      throw new Error(`unknown ${commandName} option: ${arg}`);
    }
  }
  return options;
}

export function parseIssueArgs(args, commandName) {
  const options = { target: process.cwd(), issue: "" };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--target") {
      const value = args[i + 1];
      if (!value) {
        throw new Error("--target requires a path");
      }
      options.target = value;
      i += 1;
    } else if (!options.issue) {
      options.issue = arg;
    } else {
      throw new Error(`unknown ${commandName} option: ${arg}`);
    }
  }
  if (!options.issue) {
    throw new Error(`${commandName} requires an issue number`);
  }
  return options;
}

export function parseStepArgs(args) {
  const options = { target: process.cwd(), step: "", issue: "" };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--target") {
      const value = args[i + 1];
      if (!value) {
        throw new Error("--target requires a path");
      }
      options.target = value;
      i += 1;
    } else if (!options.step) {
      options.step = arg;
    } else if (!options.issue) {
      options.issue = arg;
    } else {
      throw new Error(`unknown step option: ${arg}`);
    }
  }
  if (!options.step) {
    throw new Error("step requires a step name");
  }
  if (!options.issue) {
    throw new Error("step requires an issue number");
  }
  return options;
}

export async function listFiles(root, relativeRoot) {
  const fullPath = path.join(root, relativeRoot);
  const info = await stat(fullPath);
  if (info.isFile()) {
    return [relativeRoot];
  }

  const entries = await readdir(fullPath, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const child = path.posix.join(relativeRoot, entry.name);
    if (entry.name === "__pycache__" || entry.name.endsWith(".pyc")) {
      continue;
    }
    if (entry.isDirectory()) {
      files.push(...(await listFiles(root, child)));
    } else if (entry.isFile()) {
      files.push(child);
    }
  }
  return files;
}

export async function pathExists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function templateRoot() {
  const builtTemplateRoot = path.join(packageRoot, "dist", "templates", "repo");
  try {
    await stat(builtTemplateRoot);
    return builtTemplateRoot;
  } catch {
    return packageRoot;
  }
}

export function bundledTemplateRoot() {
  return path.join(packageRoot, "dist", "templates", "repo");
}

export function resolveAssetPath(targetRoot, relativePath) {
  const targetPath = path.join(targetRoot, relativePath);
  if (existsSync(targetPath)) {
    return targetPath;
  }
  const bundledPath = path.join(bundledTemplateRoot(), relativePath);
  if (existsSync(bundledPath)) {
    return bundledPath;
  }
  const packagePath = path.join(packageRoot, relativePath);
  if (existsSync(packagePath)) {
    return packagePath;
  }
  throw new Error(`required GCW asset is missing: ${relativePath}`);
}

export function commandOk(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: "ignore", ...options });
  return result.status === 0;
}

export function runJsonCommand(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: "utf8", ...options });
  let data = null;
  try {
    data = JSON.parse(result.stdout || "");
  } catch {
    if (result.status === 0) {
      throw new Error(`failed to parse JSON output from ${command}`);
    }
  }
  if (result.status !== 0 || (data && data.ok === false)) {
    const message =
      (data && Array.isArray(data.errors) && data.errors.length > 0
        ? data.errors.join("; ")
        : (result.stderr || result.stdout || `${command} failed`).trim()) || `${command} failed`;
    throw new Error(message);
  }
  if (data === null) {
    throw new Error(`failed to parse JSON output from ${command}`);
  }
  return data;
}

export function summarizeProjection(projection, stepLabel = "Phase") {
  console.log(`Issue: ${projection.issue}`);
  console.log(`${stepLabel}: ${projection.phase}`);
  if (projection.last_completed_step) {
    console.log(`Last completed step: ${projection.last_completed_step}`);
  }
  console.log(`Next allowed steps: ${(projection.next_allowed_steps || []).join(", ") || "(none)"}`);
}

export function issueDirForTarget(targetRoot, issue) {
  return path.join(targetRoot, ".gcw", "issues", String(issue));
}

export function issueBranchName(issue) {
  return `gcw/issue-${String(issue)}`;
}

export function issueNumberAsString(issue) {
  return String(issue).trim();
}

export function fileSha256(filePath) {
  const digest = createHash("sha256").update(readFileSync(filePath)).digest("hex");
  return `sha256:${digest}`;
}

export async function writeTempJson(prefix, data) {
  const dir = await mkdtemp(path.join(os.tmpdir(), prefix));
  const file = path.join(dir, "payload.json");
  await writeFile(file, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  return file;
}
