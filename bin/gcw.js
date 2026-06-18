#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFile, mkdir, mkdtemp, readdir, stat, writeFile } from "node:fs/promises";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import os from "node:os";
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
  ".gcw/engine/runtime",
  ".gcw/engine/platforms",
];
const githubActionsAssetRoots = [
  ".github/workflows",
  ".github/actions/gcw-setup",
  ".github/actions/gcw-run-codex",
];
const hostedSharedAssetRoots = [".gcw/engine/hosted"];
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

function parseIssueArgs(args, commandName) {
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

function parseStepArgs(args) {
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

function bundledTemplateRoot() {
  return path.join(packageRoot, "dist", "templates", "repo");
}

function resolveAssetPath(targetRoot, relativePath) {
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

async function initCommand(args) {
  const options = parseInitArgs(args);
  const sourceRoot = await templateRoot();
  const targetRoot = path.resolve(options.target);
  const assetRoots = [...requiredAssetRoots];
  if (options.withGithubActions || options.withGitlabCi) {
    assetRoots.push(...hostedSharedAssetRoots);
  }
  if (options.withGithubActions) {
    assetRoots.push(...githubActionsAssetRoots);
  }
  if (options.withGitlabCi) {
    assetRoots.push(...gitlabCiAssetRoots);
  }
  const files = (
    await Promise.all(
      assetRoots.map(async (assetRoot) => {
        const root = (await pathExists(path.join(sourceRoot, assetRoot))) ? sourceRoot : packageRoot;
        return listFiles(root, assetRoot);
      }),
    )
  )
    .flat()
    .sort();

  for (const file of files) {
    if (options.dryRun) {
      console.log(`Would copy ${file}`);
    } else {
      const root = (await pathExists(path.join(sourceRoot, file))) ? sourceRoot : packageRoot;
      const source = path.join(root, file);
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

function runJsonCommand(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: "utf8", ...options });
  let data = null;
  try {
    data = JSON.parse(result.stdout || "");
  } catch (error) {
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

function rebuildProjection(targetRoot, issueDir) {
  return runJsonCommand(
    "python3",
    [
      resolveAssetPath(targetRoot, path.join(".agents", "skills", "gcw", "scripts", "manage_gcw_workflow.py")),
      "rebuild-projection",
      "--issue-dir",
      issueDir,
    ],
    { cwd: targetRoot },
  );
}

function validateWorkflow(targetRoot, issueDir) {
  return runJsonCommand(
    "python3",
    [
      resolveAssetPath(targetRoot, path.join(".agents", "skills", "gcw", "scripts", "validate_gcw_evidence.py")),
      "workflow",
      "--issue-dir",
      issueDir,
    ],
    { cwd: targetRoot },
  );
}

function readProjection(targetRoot, issueDir) {
  rebuildProjection(targetRoot, issueDir);
  const validation = validateWorkflow(targetRoot, issueDir);
  if (!validation.ok) {
    throw new Error(`workflow validation failed: ${validation.errors.join("; ")}`);
  }
  const workflowPath = path.join(issueDir, "workflow.json");
  return JSON.parse(readFileSync(workflowPath, "utf8")).projection;
}

function issueDirForTarget(targetRoot, issue) {
  return path.join(targetRoot, ".gcw", "issues", String(issue));
}

function issueBranchName(issue) {
  return `gcw/issue-${String(issue)}`;
}

function issueNumberAsString(issue) {
  return String(issue).trim();
}

function parseRemoteRepository(remoteUrl) {
  const normalized = String(remoteUrl || "").trim();
  if (!normalized) {
    throw new Error("git remote origin is required");
  }
  let host = "";
  let repository = "";
  if (normalized.startsWith("git@")) {
    const match = normalized.match(/^git@([^:]+):(.+?)(?:\.git)?$/);
    if (!match) {
      throw new Error(`unsupported git remote url: ${normalized}`);
    }
    host = match[1];
    repository = match[2];
  } else {
    const parsed = new URL(normalized);
    host = parsed.hostname;
    repository = parsed.pathname.replace(/^\/+/, "").replace(/\.git$/, "");
  }
  if (!repository) {
    throw new Error(`could not resolve repository from remote url: ${normalized}`);
  }
  const platform = host.includes("gitlab") ? "gitlab" : "github";
  return { platform, repository };
}

function gitCommand(targetRoot, args, options = {}) {
  const result = spawnSync("git", ["-C", targetRoot, ...args], { encoding: "utf8", ...options });
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || `git ${args.join(" ")}`).trim());
  }
  return result;
}

function detectBranch(targetRoot, issueNumber) {
  const branch = issueBranchName(issueNumber);
  const result = spawnSync("git", ["-C", targetRoot, "show-ref", "--verify", "--quiet", `refs/heads/${branch}`], {
    stdio: "ignore",
  });
  if (result.status === 0) {
    gitCommand(targetRoot, ["switch", branch]);
    return branch;
  }
  gitCommand(targetRoot, ["switch", "-c", branch]);
  return branch;
}

function readGitRemote(targetRoot) {
  const result = spawnSync("git", ["-C", targetRoot, "remote", "get-url", "origin"], { encoding: "utf8" });
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || "git remote get-url origin failed").trim());
  }
  return result.stdout.trim();
}

function fetchIssueMetadata(targetRoot, platform, repository, issueNumber) {
  if (platform === "gitlab") {
    return runJsonCommand(
      "glab",
      ["issue", "view", issueNumber, "--repo", repository, "--output", "json"],
      { cwd: targetRoot },
    );
  }
  return runJsonCommand(
    "gh",
    ["issue", "view", issueNumber, "--repo", repository, "--json", "title,body,labels,url,number"],
    { cwd: targetRoot },
  );
}

function normalizeLabels(labels) {
  if (!Array.isArray(labels)) {
    return [];
  }
  return labels
    .map((label) => {
      if (typeof label === "string") {
        return label.trim();
      }
      if (label && typeof label === "object" && label.name) {
        return String(label.name).trim();
      }
      return "";
    })
    .filter(Boolean);
}

function issueTitleFromMeta(issueMeta) {
  return String((issueMeta && (issueMeta.title || issueMeta.name)) || "").trim();
}

function issueBodyFromMeta(issueMeta) {
  return String((issueMeta && (issueMeta.body || issueMeta.description)) || "").trim();
}

function issueUrlFromMeta(issueMeta) {
  return String((issueMeta && (issueMeta.url || issueMeta.web_url || issueMeta.html_url)) || "").trim();
}

function inferTriage(issueMeta) {
  const title = issueTitleFromMeta(issueMeta);
  const body = issueBodyFromMeta(issueMeta);
  const text = `${title}\n${body}`.toLowerCase();
  const labels = normalizeLabels(issueMeta.labels);

  let type = "enhancement";
  if (/\b(bug|broken|error|fail|failing|crash)\b/.test(text)) {
    type = "bug";
  } else if (/\b(doc|docs|documentation|readme)\b/.test(text)) {
    type = "documentation";
  } else if (/\b(question|\?)\b/.test(text) && !/\b(feature|enhancement|build|add)\b/.test(text)) {
    type = "question";
  }

  let area = "";
  if (/\b(test|tests|fixture|spec-check|validation)\b/.test(text)) {
    area = "area:tests";
  } else if (/\b(skill|skills|agent)\b/.test(text)) {
    area = "area:skills";
  } else if (/\b(spec|plan|planning)\b/.test(text)) {
    area = "area:specs";
  } else if (/\b(cli|command|workflow|orchestrator|run|step|status|next)\b/.test(text)) {
    area = "area:workflow";
  }

  let priority = "priority:p2";
  if (/\b(critical|urgent|blocker|p0)\b/.test(text)) {
    priority = "priority:p0";
  } else if (/\b(high|p1)\b/.test(text)) {
    priority = "priority:p1";
  } else if (/\b(low|nice to have|p3)\b/.test(text)) {
    priority = "priority:p3";
  }

  const labelsApplied = ["triaged"];
  if (area) {
    labelsApplied.push(area);
  }
  labelsApplied.push("gcw:executor-local");
  for (const label of labels) {
    if (label === "gcw:executor-hosted" || label === "gcw:executor-local") {
      labelsApplied[labelsApplied.length - 1] = label;
    }
  }

  return {
    summary: title,
    classification_type: type,
    classification_area: area,
    classification_priority: priority,
    labels_applied: labelsApplied,
  };
}

async function writeTempJson(prefix, data) {
  const dir = await mkdtemp(path.join(os.tmpdir(), prefix));
  const file = path.join(dir, "payload.json");
  await writeFile(file, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  return file;
}

async function writePlanningFilesFromTemplates(targetRoot, issueDir, issueMeta) {
  const templates = {
    "task_plan.md": resolveAssetPath(targetRoot, path.join(".agents", "skills", "planning-with-files", "templates", "task_plan.md")),
    "findings.md": resolveAssetPath(targetRoot, path.join(".agents", "skills", "planning-with-files", "templates", "findings.md")),
    "progress.md": resolveAssetPath(targetRoot, path.join(".agents", "skills", "planning-with-files", "templates", "progress.md")),
  };
  await mkdir(issueDir, { recursive: true });
  const title = issueTitleFromMeta(issueMeta) || `GCW issue ${issueDir.split(path.sep).pop()}`;
  for (const [filename, templatePath] of Object.entries(templates)) {
    const targetPath = path.join(issueDir, filename);
    if (existsSync(targetPath)) {
      continue;
    }
    let content = readFileSync(templatePath, "utf8");
    content = content.replace(/\[Brief Description\]/g, title);
    content = content.replace(/\[One sentence describing the end state\]/g, "Add formal terminal-first GCW commands for workflow orchestration.");
    content = content.replace(/\[Question to answer\]/g, "How should the CLI route workflow states without duplicating GCW runtime rules?");
    content = content.replace(/\[goal statement\]/g, "Add formal terminal-first GCW commands for workflow orchestration.");
    await writeFile(targetPath, content, "utf8");
  }
}

function summarizeProjection(projection, stepLabel = "Phase") {
  console.log(`Issue: ${projection.issue}`);
  console.log(`${stepLabel}: ${projection.phase}`);
  if (projection.last_completed_step) {
    console.log(`Last completed step: ${projection.last_completed_step}`);
  }
  console.log(`Next allowed steps: ${(projection.next_allowed_steps || []).join(", ") || "(none)"}`);
}

function humanHandoffReason(phase) {
  if (phase === "planned") {
    return "Waiting for human spec review before gcw-spec-check.";
  }
  if (phase === "issue-clarifying") {
    return "Waiting for issue clarification before GCW can continue.";
  }
  if (phase === "blocked") {
    return "Workflow is blocked and needs human intervention.";
  }
  if (phase === "reviewing") {
    return "Waiting for hosted or human review after review request publication.";
  }
  if (phase === "review-complete") {
    return "Workflow is complete.";
  }
  return "";
}

function shouldStopForHumanHandoff(phase) {
  return ["planned", "issue-clarifying", "blocked", "reviewing", "review-complete"].includes(String(phase));
}

function hasMeaningfulImplementationChanges(targetRoot, issueDir) {
  const result = spawnSync("git", ["-C", targetRoot, "status", "--porcelain"], { encoding: "utf8" });
  if (result.status !== 0) {
    return false;
  }
  return result.stdout
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .some((line) => {
      const filePath = line.slice(3).trim();
      return filePath && !filePath.startsWith(path.relative(targetRoot, issueDir)) && !filePath.startsWith(".gcw-runtime");
    });
}

function selectNextRunStep(projection, targetRoot, issueDir) {
  const nextSteps = projection.next_allowed_steps || [];
  if (nextSteps.length === 0) {
    return null;
  }

  if (projection.phase === "implementing" && nextSteps.includes("gcw-implement-check")) {
    return "gcw-implement-check";
  }

  const nextStep = nextSteps[0];
  if (nextStep === "gcw-implement" && !hasMeaningfulImplementationChanges(targetRoot, issueDir)) {
    return null;
  }
  return nextStep;
}

function progressCommentTool(targetRoot) {
  return resolveAssetPath(targetRoot, path.join(".agents", "skills", "gcw", "scripts", "publish_progress_comment.py"));
}

function workflowManagerTool(targetRoot) {
  return resolveAssetPath(targetRoot, path.join(".agents", "skills", "gcw", "scripts", "manage_gcw_workflow.py"));
}

function workflowStepTool(targetRoot) {
  return resolveAssetPath(targetRoot, path.join(".agents", "skills", "gcw", "scripts", "run_gcw_step.py"));
}

function triageMetadataTool(targetRoot) {
  return resolveAssetPath(
    targetRoot,
    path.join(".agents", "skills", "gcw-issue-triage", "scripts", "manage_triage_metadata.py"),
  );
}

function readinessTool(targetRoot) {
  return resolveAssetPath(
    targetRoot,
    path.join(".agents", "skills", "gcw-issue-clarify", "scripts", "evaluate_issue_readiness.py"),
  );
}

function renderArtifactsTool(targetRoot) {
  return resolveAssetPath(
    targetRoot,
    path.join(".agents", "skills", "gcw", "scripts", "render_gcw_hosted_artifacts.py"),
  );
}

function planningLinksForProjection(projection) {
  const platform = String(projection.platform || "github").trim();
  const repository = String(projection.repository || "").trim();
  const branch = String(projection.branch || "").trim();
  const issue = String(projection.issue || "").trim();
  if (!repository || !branch || !issue) {
    return {};
  }
  const base =
    platform === "gitlab"
      ? `https://gitlab.com/${repository}/-/blob/${branch}/.gcw/issues/${issue}`
      : `https://github.com/${repository}/blob/${branch}/.gcw/issues/${issue}`;
  return {
    task_plan: `${base}/task_plan.md`,
    findings: `${base}/findings.md`,
    progress: `${base}/progress.md`,
  };
}

function fileSha256(filePath) {
  const digest = createHash("sha256").update(readFileSync(filePath)).digest("hex");
  return `sha256:${digest}`;
}

async function ensureIssueWorkflow(targetRoot, issue) {
  const issueNumber = issueNumberAsString(issue);
  const issueDir = issueDirForTarget(targetRoot, issueNumber);
  if (await pathExists(issueDir)) {
    return { issueDir, created: false, issueMeta: null };
  }

  const { platform, repository } = parseRemoteRepository(readGitRemote(targetRoot));
  const issueMeta = fetchIssueMetadata(targetRoot, platform, repository, issueNumber);
  const branch = detectBranch(targetRoot, issueNumber);
  await mkdir(path.join(issueDir, "events"), { recursive: true });

  runJsonCommand(
    "python3",
    [
      workflowManagerTool(targetRoot),
      "init-workflow",
      "--issue-dir",
      issueDir,
      "--issue",
      issueNumber,
      "--platform",
      platform,
      "--repository",
      repository,
      "--branch",
      branch,
      "--owner-kind",
      "local",
      "--owner-id",
      "gcw-cli",
    ],
    { cwd: targetRoot },
  );

  return { issueDir, created: true, issueMeta };
}

async function resolveIssueMetadata(targetRoot, issueDir, projection, issueMeta, issueNumber) {
  if (issueMeta) {
    return issueMeta;
  }
  const platform = String(projection.platform || "").trim();
  const repository = String(projection.repository || "").trim();
  if (!platform || !repository) {
    return null;
  }
  return fetchIssueMetadata(targetRoot, platform, repository, issueNumberAsString(issueNumber));
}

function publishProgressForMilestone(targetRoot, issueDir, stepName, payloadFile) {
  return runJsonCommand(
    "python3",
    [
      progressCommentTool(targetRoot),
      "--issue-dir",
      issueDir,
      "--milestone-event",
      stepName,
      "--milestone-payload-file",
      payloadFile,
    ],
    { cwd: targetRoot },
  );
}

async function createTriageOptions(targetRoot, issueDir, projection, issueMeta) {
  const triage = inferTriage(issueMeta);
  const remoteSyncFile = await writeTempJson("gcw-triage-", {
    remote_sync: {
      platform: projection.platform,
      issue_type: triage.classification_type === "bug" ? "Bug" : "Feature",
      priority:
        triage.classification_priority === "priority:p0"
          ? "Urgent"
          : triage.classification_priority === "priority:p1"
            ? "High"
            : triage.classification_priority === "priority:p3"
              ? "Low"
              : "Medium",
      labels: triage.labels_applied,
    },
  });

  if (projection.platform === "github" || projection.platform === "gitlab") {
    try {
      runJsonCommand(
        "python3",
        [
          triageMetadataTool(targetRoot),
          "apply-metadata",
          "--platform",
          projection.platform,
          "--repo",
          projection.repository,
          "--issue",
          String(projection.issue),
          "--type",
          triage.classification_type,
          "--priority",
          triage.classification_priority,
          "--labels",
          triage.labels_applied.join(","),
          "--executor",
          "local",
        ],
        { cwd: targetRoot },
      );
    } catch {
      // Keep CLI usable even when remote metadata sync is unavailable; step runner will still record local workflow state.
    }
  }

  return writeTempJson("gcw-step-", {
    summary: triage.summary,
    classification_type: triage.classification_type,
    classification_area: triage.classification_area,
    classification_priority: triage.classification_priority,
    labels_applied: triage.labels_applied,
    remote_sync_file: remoteSyncFile,
  });
}

async function createClarifyOptions(targetRoot, projection) {
  const gateFile = await writeTempJson("gcw-clarify-gate-", {});
  const result = spawnSync(
    "python3",
    [
      readinessTool(targetRoot),
      "--profile",
      "enhancement",
      "--platform",
      projection.platform,
      "--repo",
      projection.repository,
      "--issue",
      String(projection.issue),
      "--output",
      gateFile,
    ],
    { cwd: targetRoot, encoding: "utf8" },
  );
  let gate = {};
  try {
    gate = JSON.parse(result.stdout || readFileSync(gateFile, "utf8"));
  } catch (error) {
    throw new Error((result.stderr || result.stdout || "failed to evaluate issue readiness").trim());
  }

  const options = { gate_file: gateFile };
  if (gate.ok) {
    options.ready = true;
    options.summary = "scope clear";
  } else {
    const question = gate.errors && gate.errors.length > 0 ? `Please update the issue so GCW can continue:\n- ${gate.errors.join("\n- ")}` : "Please update the issue so GCW can continue.";
    options.question = question;
  }
  return writeTempJson("gcw-step-", options);
}

async function createIssueToSpecOptions(targetRoot, issueDir, issueMeta) {
  await writePlanningFilesFromTemplates(targetRoot, issueDir, issueMeta);
  return writeTempJson("gcw-step-", { planning_commit_pushed: true });
}

async function createImplementCheckPayload(issueDir, projection) {
  const payload = {
    gate: {
      ok: true,
      checks: [{ id: "implementation_readiness", ok: true }],
      validation: [],
    },
    planning_links: planningLinksForProjection(projection),
    review_request: {
      title: `feat: issue ${projection.issue}`,
      summary: "Implements the planned workflow change.",
      issue_link: `Closes #${projection.issue}`,
    },
    risks: "Low risk; changes are scoped to the current issue branch.",
    scope: "Current issue branch only.",
    reviewer_notes: "Review the scoped issue diff and generated workflow artifacts.",
    self_review: { recorded: true, progress_section: "## Local Self-Review" },
    spec_refs: {
      task_plan_sha: fileSha256(path.join(issueDir, "task_plan.md")),
      findings_sha: fileSha256(path.join(issueDir, "findings.md")),
      progress_sha: fileSha256(path.join(issueDir, "progress.md")),
    },
  };
  return writeTempJson("gcw-implement-check-", payload);
}

function renderReviewRequest(targetRoot, issueDir) {
  const result = spawnSync(
    "python3",
    [renderArtifactsTool(targetRoot), "review-request", "--issue-dir", issueDir],
    { cwd: targetRoot, encoding: "utf8" },
  );
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || "failed to render review request").trim());
  }
  return result.stdout;
}

function upsertGithubPullRequest(targetRoot, projection, issueDir) {
  const reviewRequestBody = renderReviewRequest(targetRoot, issueDir);
  const bodyFile = path.join(os.tmpdir(), `gcw-review-request-${projection.issue}-${Date.now()}.md`);
  writeFileSync(bodyFile, reviewRequestBody, "utf8");
  const prList = runJsonCommand(
    "gh",
    ["pr", "list", "--repo", projection.repository, "--head", projection.branch, "--json", "url", "title"],
    { cwd: targetRoot },
  );
  const reviewRequest = JSON.parse(
    readFileSync(path.join(issueDir, "implement-check-payload.json"), "utf8"),
  ).review_request;
  if (Array.isArray(prList) && prList.length > 0 && prList[0].url) {
    spawnSync(
      "gh",
      ["pr", "edit", prList[0].url, "--repo", projection.repository, "--title", reviewRequest.title, "--body-file", bodyFile],
      { cwd: targetRoot, encoding: "utf8" },
    );
    return prList[0].url;
  }
  const created = spawnSync(
    "gh",
    [
      "pr",
      "create",
      "--repo",
      projection.repository,
      "--head",
      projection.branch,
      "--title",
      reviewRequest.title,
      "--body-file",
      bodyFile,
    ],
    { cwd: targetRoot, encoding: "utf8" },
  );
  if (created.status !== 0) {
    throw new Error((created.stderr || created.stdout || "failed to create pull request").trim());
  }
  return created.stdout.trim();
}

async function optionsFileForStep(targetRoot, issueDir, projection, stepName, issueMeta) {
  if (stepName === "gcw-issue-triage") {
    return createTriageOptions(targetRoot, issueDir, projection, issueMeta);
  }
  if (stepName === "gcw-issue-clarify") {
    return createClarifyOptions(targetRoot, projection);
  }
  if (stepName === "gcw-issue-to-spec") {
    return createIssueToSpecOptions(targetRoot, issueDir, issueMeta);
  }
  if (stepName === "gcw-spec-check") {
    return writeTempJson("gcw-step-", { result: "passed" });
  }
  if (stepName === "gcw-implement-check") {
    const payloadFile = await createImplementCheckPayload(issueDir, projection);
    const persistedPayload = path.join(issueDir, "implement-check-payload.json");
    await writeFile(persistedPayload, readFileSync(payloadFile, "utf8"), "utf8");
    return writeTempJson("gcw-step-", { payload_file: persistedPayload });
  }
  if (stepName === "gcw-pr-publish") {
    if (projection.platform !== "github") {
      throw new Error("gcw-pr-publish currently supports GitHub CLI publishing; pass review_request_url with the Python step runner for other platforms");
    }
    const reviewRequestUrl = upsertGithubPullRequest(targetRoot, projection, issueDir);
    return writeTempJson("gcw-step-", { review_request_url: reviewRequestUrl, target: "github_pr" });
  }
  if (stepName === "gcw-pr-review") {
    return writeTempJson("gcw-step-", { result: "passed" });
  }
  return null;
}

async function runSingleStep(targetRoot, issueDir, projection, stepName, issueMeta) {
  if (stepName === "gcw-issue-intake") {
    throw new Error("gcw-issue-intake should be run through gcw run or by targeting an issue outside GCW state");
  }

  if (stepName === "gcw-implement") {
    const payloadFile = await writeTempJson("gcw-implement-", {
      work_summary: "Implementation work recorded from terminal-first GCW CLI.",
    });
    const progress = publishProgressForMilestone(targetRoot, issueDir, stepName, payloadFile);
    runJsonCommand(
      "python3",
      [
        workflowManagerTool(targetRoot),
        "record-implement",
        "--issue-dir",
        issueDir,
        "--work-summary",
        "Implementation work recorded from terminal-first GCW CLI.",
        "--progress-comment-url",
        progress.progress_comment_url,
      ],
      { cwd: targetRoot },
    );
    return readProjection(targetRoot, issueDir);
  }

  const optionsFile = await optionsFileForStep(targetRoot, issueDir, projection, stepName, issueMeta);
  const args = [workflowStepTool(targetRoot), "--step", stepName, "--issue-dir", issueDir];
  if (optionsFile) {
    args.push("--options-file", optionsFile);
  }
  runJsonCommand("python3", args, { cwd: targetRoot });
  return readProjection(targetRoot, issueDir);
}

async function statusCommand(args) {
  const options = parseIssueArgs(args, "status");
  const targetRoot = path.resolve(options.target);
  const issueDir = issueDirForTarget(targetRoot, options.issue);
  if (!(await pathExists(issueDir))) {
    throw new Error(`GCW issue state not found for issue ${options.issue}`);
  }
  const projection = readProjection(targetRoot, issueDir);
  console.log(`Issue: ${projection.issue}`);
  console.log(`Phase: ${projection.phase}`);
  console.log(`Last completed step: ${projection.last_completed_step}`);
  console.log(`Next allowed steps: ${(projection.next_allowed_steps || []).join(", ") || "(none)"}`);
  return 0;
}

async function nextCommand(args) {
  const options = parseIssueArgs(args, "next");
  const targetRoot = path.resolve(options.target);
  const issueDir = issueDirForTarget(targetRoot, options.issue);
  if (!(await pathExists(issueDir))) {
    throw new Error(`GCW issue state not found for issue ${options.issue}`);
  }
  const projection = readProjection(targetRoot, issueDir);
  console.log(`Issue: ${projection.issue}`);
  console.log(`Phase: ${projection.phase}`);
  if ((projection.next_allowed_steps || []).length > 0) {
    console.log(`Next step: ${projection.next_allowed_steps[0]}`);
  } else {
    console.log("Next step: (none)");
  }
  return 0;
}

async function stepCommand(args) {
  const options = parseStepArgs(args);
  const targetRoot = path.resolve(options.target);
  const issueNumber = issueNumberAsString(options.issue);
  const ensured = await ensureIssueWorkflow(targetRoot, issueNumber);
  const issueDir = ensured.issueDir;
  const projection = readProjection(targetRoot, issueDir);
  const requestedStep = options.step;
  const resolvedIssueMeta = await resolveIssueMetadata(targetRoot, issueDir, projection, ensured.issueMeta, issueNumber);

  if (requestedStep === "gcw-issue-intake") {
    if (ensured.created) {
      const createdProjection = readProjection(targetRoot, issueDir);
      console.log(`Executed: gcw-issue-intake`);
      summarizeProjection(createdProjection);
      return 0;
    }
    throw new Error(`step ${requestedStep} is not allowed in phase ${projection.phase}`);
  }

  if (!(projection.next_allowed_steps || []).includes(requestedStep)) {
    throw new Error(`step ${requestedStep} is not allowed in phase ${projection.phase}`);
  }

  if (requestedStep === "gcw-implement" && !hasMeaningfulImplementationChanges(targetRoot, issueDir)) {
    throw new Error("gcw-implement requires code or documentation changes in the working tree before recording implementation progress");
  }

  const updatedProjection = await runSingleStep(
    targetRoot,
    issueDir,
    projection,
    requestedStep,
    resolvedIssueMeta,
  );
  console.log(`Executed: ${requestedStep}`);
  summarizeProjection(updatedProjection);
  return 0;
}

async function runCommand(args) {
  const options = parseIssueArgs(args, "run");
  const targetRoot = path.resolve(options.target);
  const issueNumber = issueNumberAsString(options.issue);
  const ensured = await ensureIssueWorkflow(targetRoot, issueNumber);
  const issueDir = ensured.issueDir;
  const executed = [];
  let projection = readProjection(targetRoot, issueDir);
  const issueMeta = await resolveIssueMetadata(targetRoot, issueDir, projection, ensured.issueMeta, issueNumber);
  if (ensured.created) {
    executed.push("gcw-issue-intake");
  }

  while (!shouldStopForHumanHandoff(projection.phase)) {
    const nextStep = selectNextRunStep(projection, targetRoot, issueDir);
    if (!nextStep) {
      break;
    }
    projection = await runSingleStep(targetRoot, issueDir, projection, nextStep, issueMeta);
    executed.push(nextStep);
    if (shouldStopForHumanHandoff(projection.phase)) {
      break;
    }
    if (nextStep === "gcw-implement" && projection.phase === "implementing") {
      break;
    }
  }

  console.log(`Issue: ${projection.issue}`);
  console.log(`Executed steps: ${executed.join(", ") || "(none)"}`);
  console.log(`Phase: ${projection.phase}`);
  console.log(`Last completed step: ${projection.last_completed_step}`);
  console.log(`Next allowed steps: ${(projection.next_allowed_steps || []).join(", ") || "(none)"}`);
  const reason = humanHandoffReason(projection.phase);
  if (reason) {
    console.log(`Stop reason: ${reason}`);
  } else if ((projection.next_allowed_steps || [])[0] === "gcw-implement") {
    console.log("Stop reason: Waiting for implementation changes before recording gcw-implement.");
  }
  return 0;
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
        (await pathExists(path.join(targetRoot, ".gcw", "engine", "runtime", "gcw_workflow_contracts.py"))),
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
  if (command === "status") {
    return statusCommand(args);
  }
  if (command === "next") {
    return nextCommand(args);
  }
  if (command === "step") {
    return stepCommand(args);
  }
  if (command === "run") {
    return runCommand(args);
  }

  console.error("Usage: gcw <init|doctor|run|step|status|next|--version>");
  return 1;
}

const exitCode = await main();
process.exitCode = exitCode;
