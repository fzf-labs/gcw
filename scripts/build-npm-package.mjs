import { copyFile, mkdir, readdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const templateRoot = path.join(repoRoot, "dist", "templates", "repo");

const assetRoots = [
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
  ".gitlab-ci.yml",
  ".github/workflows",
  ".github/actions/gcw-setup",
  ".github/actions/gcw-run-codex",
  ".github/scripts",
];

function shouldSkip(entryName) {
  return entryName === "__pycache__" || entryName.endsWith(".pyc");
}

async function copyTree(relativePath) {
  const source = path.join(repoRoot, relativePath);
  const info = await stat(source);
  if (info.isFile()) {
    const target = path.join(templateRoot, relativePath);
    await mkdir(path.dirname(target), { recursive: true });
    await copyFile(source, target);
    return;
  }

  const entries = await readdir(source, { withFileTypes: true });
  for (const entry of entries) {
    if (shouldSkip(entry.name)) {
      continue;
    }
    await copyTree(path.posix.join(relativePath, entry.name));
  }
}

await rm(templateRoot, { recursive: true, force: true });
await mkdir(templateRoot, { recursive: true });

for (const assetRoot of assetRoots) {
  await copyTree(assetRoot);
}

console.log(`Built GCW npm templates at ${path.relative(repoRoot, templateRoot)}`);
