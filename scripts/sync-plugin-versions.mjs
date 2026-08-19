import { readFile, writeFile } from "node:fs/promises";
import { argv, exit } from "node:process";

const MARKETPLACE_MANIFEST = ".claude-plugin/marketplace.json";
const PLUGIN_MANIFESTS = [
  "plugins/compliance-pack/.claude-plugin/plugin.json",
  "plugins/ts-strictness-pack/.claude-plugin/plugin.json",
];
const SEMVER = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

function parseRequestedVersion(args) {
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

function withNestedPluginVersions(marketplace, version) {
  if (!Array.isArray(marketplace.plugins)) {
    return marketplace;
  }
  return {
    ...marketplace,
    plugins: marketplace.plugins.map((plugin) => withVersion(plugin, version)),
  };
}

async function syncMarketplace(version) {
  const current = await readManifest(MARKETPLACE_MANIFEST);
  const updated = withNestedPluginVersions(withVersion(current, version), version);
  await writeManifest(MARKETPLACE_MANIFEST, updated);
  return `${MARKETPLACE_MANIFEST} -> ${version} (${updated.plugins?.length ?? 0} nested)`;
}

async function syncPlugin(path, version) {
  const current = await readManifest(path);
  await writeManifest(path, withVersion(current, version));
  return `${path} -> ${version}`;
}

async function main() {
  const version = parseRequestedVersion(argv.slice(2));
  const results = [
    await syncMarketplace(version),
    ...(await Promise.all(PLUGIN_MANIFESTS.map((path) => syncPlugin(path, version)))),
  ];
  for (const result of results) {
    console.log(result);
  }
}

main().catch((error) => {
  console.error(`sync-plugin-versions failed: ${error.message}`);
  exit(1);
});
