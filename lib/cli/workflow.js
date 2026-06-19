import path from "node:path";
import { parseIssueArgs, parseStepArgs, runJsonCommand, resolveAssetPath } from "./common.js";

function terminalCliPath(targetRoot) {
  return resolveAssetPath(targetRoot, path.join(".agents", "skills", "gcw", "scripts", "gcw_terminal_cli.py"));
}

export async function statusCommand(args) {
  const options = parseIssueArgs(args, "status");
  const targetRoot = path.resolve(options.target);
  const result = runJsonCommand("python3", [terminalCliPath(targetRoot), "status", "--target", targetRoot, options.issue], {
    cwd: targetRoot,
  });
  console.log(`Issue: ${result.issue}`);
  console.log(`Phase: ${result.phase}`);
  console.log(`Last completed step: ${result.last_completed_step || "(none)"}`);
  console.log(`Next allowed steps: ${(result.next_allowed_steps || []).join(", ") || "(none)"}`);
  return 0;
}

export async function nextCommand(args) {
  const options = parseIssueArgs(args, "next");
  const targetRoot = path.resolve(options.target);
  const result = runJsonCommand("python3", [terminalCliPath(targetRoot), "next", "--target", targetRoot, options.issue], {
    cwd: targetRoot,
  });
  console.log(`Issue: ${result.issue}`);
  console.log(`Phase: ${result.phase}`);
  const nextSteps = result.next_allowed_steps || [];
  console.log(`Next step: ${nextSteps[0] || "(none)"}`);
  return 0;
}

export async function stepCommand(args) {
  const options = parseStepArgs(args);
  const targetRoot = path.resolve(options.target);
  const result = runJsonCommand("python3", [terminalCliPath(targetRoot), "step", "--target", targetRoot, options.step, options.issue], {
    cwd: targetRoot,
  });
  console.log(`Executed: ${options.step}`);
  console.log(`Issue: ${result.issue}`);
  console.log(`Phase: ${result.phase}`);
  console.log(`Last completed step: ${result.last_completed_step || "(none)"}`);
  console.log(`Next allowed steps: ${(result.next_allowed_steps || []).join(", ") || "(none)"}`);
  return 0;
}

export async function runCommand(args) {
  const options = parseIssueArgs(args, "run");
  const targetRoot = path.resolve(options.target);
  const result = runJsonCommand("python3", [terminalCliPath(targetRoot), "run", "--target", targetRoot, options.issue], {
    cwd: targetRoot,
  });
  console.log(`Issue: ${result.issue}`);
  console.log(`Executed steps: ${(result.executed_steps || []).join(", ") || "(none)"}`);
  console.log(`Phase: ${result.phase}`);
  console.log(`Last completed step: ${result.last_completed_step || "(none)"}`);
  console.log(`Next allowed steps: ${(result.next_allowed_steps || []).join(", ") || "(none)"}`);
  if (result.stop_reason) {
    console.log(`Stop reason: ${result.stop_reason}`);
  }
  return 0;
}
