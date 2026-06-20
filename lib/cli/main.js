import { doctorCommand } from "./doctor.js";
import { initCommand } from "./init.js";
import { nextCommand, runCommand, stepCommand, statusCommand } from "./workflow.js";
import { printHelp, printVersion } from "./common.js";

export default async function main(argv = process.argv.slice(2)) {
  const [command, ...args] = argv;
  if (command === "--version" || command === "-v" || command === "version") {
    printVersion();
    return 0;
  }
  if (command === "help" || command === "--help" || command === "-h") {
    printHelp();
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

  console.error("Usage: gcw <init|doctor|run|step|status|next|help|--version>");
  return 1;
}
