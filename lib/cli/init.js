import path from "node:path";
import { copyFile, mkdir } from "node:fs/promises";
import { pathExists, listFiles, requiredAssetRoots, hostedSharedAssetRoots, githubActionsAssetRoots, gitlabCiAssetRoots, templateRoot, packageRoot, resolveAssetPath, parseInitArgs } from "./common.js";

export async function initCommand(args) {
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

export { resolveAssetPath };
