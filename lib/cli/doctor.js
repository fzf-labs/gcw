import path from "node:path";
import { commandOk, parseTargetArgs, pathExists } from "./common.js";

export async function doctorCommand(args) {
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
