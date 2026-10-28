import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { argv, cwd, exit } from "node:process";

export const MARKETPLACE_MANIFEST = ".claude-plugin/marketplace.json";
export const PLUGIN_MANIFESTS = [
  "plugins/compliance-pack/.claude-plugin/plugin.json",
  "plugins/ts-strictness-pack/.claude-plugin/plugin.json",
];
const SEMVER = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

export function parseRequestedVersion(args) {
  const [version] = args;
  if (!version) {
    throw new Error("usage: sync-plugin-versions.mjs <semver>");
  }
  if (!SEMVER.test(version)) {
    throw new Error(`not a semantic version: ${version}`);
  }
  return version;
}

async function readManifest(path) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    throw new Error(`cannot read manifest ${path}: ${error.message}`);
  }
}

async function writeManifest(path, manifest) {
  await writeFile(path, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
}

function withVersion(manifest, version) {
  return { ...manifest, version };
}

export function withNestedPluginVersions(marketplace, version) {
  if (!Array.isArray(marketplace.plugins)) {
    return marketplace;
  }
  return {
    ...marketplace,
    plugins: marketplace.plugins.map((plugin) => withVersion(plugin, version)),
  };
}

async function syncMarketplace(root, version) {
  const path = join(root, MARKETPLACE_MANIFEST);
  const current = await readManifest(path);
  const updated = withNestedPluginVersions(withVersion(current, version), version);
  await writeManifest(path, updated);
  return `${MARKETPLACE_MANIFEST} -> ${version} (${updated.plugins?.length ?? 0} nested)`;
}

async function syncPlugin(root, relative, version) {
  const path = join(root, relative);
  await writeManifest(path, withVersion(await readManifest(path), version));
  return `${relative} -> ${version}`;
}

export async function syncVersions(root, args) {
  const version = parseRequestedVersion(args);
  return [
    await syncMarketplace(root, version),
    ...(await Promise.all(
      PLUGIN_MANIFESTS.map((relative) => syncPlugin(root, relative, version)),
    )),
  ];
}

export async function run(root, args, log, fail) {
  try {
    for (const line of await syncVersions(root, args)) {
      log(line);
    }
    return 0;
  } catch (error) {
    fail(`sync-plugin-versions failed: ${error.message}`);
    return 1;
  }
}

if (import.meta.main) {
  exit(await run(cwd(), argv.slice(2), console.log, console.error));
}
