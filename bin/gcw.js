#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { copyFile, mkdir, readdir, stat } from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packageJson = JSON.parse(readFileSync(path.join(packageRoot, "package.json"), "utf8"));
const requiredAssetRoots = [
  ".agents/skills/gcw",
  ".agents/skills/gcw-issue-intake",
  ".agents/skills/gcw-issue-triage",
  ".agents/skills/gcw-issue-clarify",
  ".agents/skills/gcw-issue-to-spec",
  ".agents/skills/gcw-spec-check",
  ".agents/skills/gcw-implement",
  ".agents/skills/gcw-implement-check",
  ".agents/skills/gcw-pr-publish",
  ".agents/skills/gcw-pr-review",
  ".agents/skills/planning-with-files",
  ".gcw/runtime",
];
const githubActionsAssetRoots = [
  ".github/workflows",
  ".github/actions/gcw-setup",
  ".github/actions/gcw-run-codex",
  ".github/scripts",
];
const gitlabCiAssetRoots = [".gitlab-ci.yml"];

function printVersion() {
  console.log(packageJson.version);
}

function parseInitArgs(args) {
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

function parseTargetArgs(args, commandName) {
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

async function listFiles(root, relativeRoot) {
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

async function pathExists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

async function templateRoot() {
  const builtTemplateRoot = path.join(packageRoot, "dist", "templates", "repo");
  try {
    await stat(builtTemplateRoot);
    return builtTemplateRoot;
  } catch {
    return packageRoot;
  }
}

async function initCommand(args) {
  const options = parseInitArgs(args);
  const sourceRoot = await templateRoot();
  const targetRoot = path.resolve(options.target);
  const assetRoots = options.withGithubActions
    ? [...requiredAssetRoots, ...githubActionsAssetRoots]
    : requiredAssetRoots;
  if (options.withGitlabCi) {
    assetRoots.push(...gitlabCiAssetRoots);
  }
  const files = (await Promise.all(assetRoots.map((assetRoot) => listFiles(sourceRoot, assetRoot))))
    .flat()
    .sort();

  for (const file of files) {
    if (options.dryRun) {
      console.log(`Would copy ${file}`);
    } else {
      const source = path.join(sourceRoot, file);
      const target = path.join(targetRoot, file);
      const exists = await pathExists(target);
      if (exists && !options.force) {
        console.log(`Skipped ${file}`);
        continue;
      }
      await mkdir(path.dirname(target), { recursive: true });
      await copyFile(source, target);
      console.log(`${exists ? "Overwrote" : "Copied"} ${file}`);
    }
  }
  if (options.dryRun) {
    console.log(`Dry run complete for ${targetRoot}`);
  }
  return 0;
}

function commandOk(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: "ignore", ...options });
  return result.status === 0;
}

async function doctorCommand(args) {
  const options = parseTargetArgs(args, "doctor");
  const targetRoot = path.resolve(options.target);
  const checks = [
    {
      label: "Git repository",
      ok: commandOk("git", ["-C", targetRoot, "rev-parse", "--is-inside-work-tree"]),
    },
    {
      label: "GCW assets",
      ok:
        (await pathExists(path.join(targetRoot, ".agents", "skills", "gcw", "SKILL.md"))) &&
        (await pathExists(path.join(targetRoot, ".gcw", "runtime", "gcw_workflow_contracts.py"))),
    },
    {
      label: "python3",
      ok: commandOk("python3", ["--version"]),
    },
    {
      label: "gh",
      ok: commandOk("gh", ["--version"]),
      optional: true,
    },
    {
      label: "glab",
      ok: commandOk("glab", ["--version"]),
      optional: true,
    },
  ];

  for (const check of checks) {
    const status = check.ok ? "ok" : check.optional ? "missing (optional)" : "missing";
    console.log(`${check.label}: ${status}`);
  }
  return checks.every((check) => check.ok || check.optional) ? 0 : 1;
}

async function main(argv = process.argv.slice(2)) {
  const [command, ...args] = argv;
  if (command === "--version" || command === "-v" || command === "version") {
    printVersion();
    return 0;
  }
  if (command === "init") {
    return initCommand(args);
  }
  if (command === "doctor") {
    return doctorCommand(args);
  }

  console.error("Usage: gcw <init|doctor|--version>");
  return 1;
}

const exitCode = await main();
process.exitCode = exitCode;
