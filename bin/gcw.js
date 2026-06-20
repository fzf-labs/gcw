#!/usr/bin/env node

import main from "../lib/cli/main.js";

const exitCode = await main();
process.exitCode = exitCode;
