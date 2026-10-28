import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  MARKETPLACE_MANIFEST,
  PLUGIN_MANIFESTS,
  parseRequestedVersion,
  run,
  withNestedPluginVersions,
} from "../../scripts/sync-plugin-versions.mjs";

const SCRIPT = fileURLToPath(new URL("../../scripts/sync-plugin-versions.mjs", import.meta.url));

async function writeJson(root, relative, value) {
  const path = join(root, relative);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, JSON.stringify(value), "utf8");
}

async function fixtureRoot(marketplace) {
  const root = await mkdtemp(join(tmpdir(), "sync-versions-"));
  await writeJson(root, MARKETPLACE_MANIFEST, marketplace);
  for (const relative of PLUGIN_MANIFESTS) {
    await writeJson(root, relative, { name: relative, version: "0.0.1" });
  }
  return root;
}

function collector() {
  const lines = [];
  return { lines, push: (line) => lines.push(line) };
}

test("parseRequestedVersion rejects a missing or malformed version", () => {
  // Arrange
  const cases = [[], ["v1"]];

  // Act
  const messages = cases.map((args) => {
    try {
      parseRequestedVersion(args);
      return "";
    } catch (error) {
      return error.message;
    }
  });

  // Assert
  assert.deepEqual(messages, [
    "usage: sync-plugin-versions.mjs <semver>",
    "not a semantic version: v1",
  ]);
});

test("withNestedPluginVersions leaves a marketplace without plugins alone", () => {
  // Arrange
  const marketplace = { name: "m" };

  // Act
  const result = withNestedPluginVersions(marketplace, "1.2.3");

  // Assert
  assert.equal(result, marketplace);
});

test("run writes every manifest and reports each one", async () => {
  // Arrange
  const root = await fixtureRoot({ name: "m", plugins: [{ name: "a" }, { name: "b" }] });
  const out = collector();

  // Act
  const code = await run(root, ["1.2.3"], out.push, out.push);

  // Assert
  const marketplace = JSON.parse(await readFile(join(root, MARKETPLACE_MANIFEST), "utf8"));
  assert.equal(code, 0);
  assert.deepEqual(marketplace.plugins.map((plugin) => plugin.version), ["1.2.3", "1.2.3"]);
  assert.deepEqual(out.lines, [
    `${MARKETPLACE_MANIFEST} -> 1.2.3 (2 nested)`,
    ...PLUGIN_MANIFESTS.map((relative) => `${relative} -> 1.2.3`),
  ]);
});

test("run counts zero nested plugins when the marketplace has none", async () => {
  // Arrange
  const root = await fixtureRoot({ name: "m" });
  const out = collector();

  // Act
  await run(root, ["2.0.0"], out.push, out.push);

  // Assert
  assert.equal(out.lines[0], `${MARKETPLACE_MANIFEST} -> 2.0.0 (0 nested)`);
});

test("run reports a manifest it cannot read", async () => {
  // Arrange
  const root = await mkdtemp(join(tmpdir(), "sync-versions-"));
  const out = collector();

  // Act
  const code = await run(root, ["1.0.0"], out.push, out.push);

  // Assert
  assert.equal(code, 1);
  assert.match(out.lines[0], /^sync-plugin-versions failed: cannot read manifest /);
});

test("the script runs as a program", async () => {
  // Arrange
  const root = await fixtureRoot({ name: "m", plugins: [] });

  // Act
  const result = spawnSync(process.execPath, [SCRIPT, "3.0.0"], { cwd: root, encoding: "utf8" });

  // Assert
  assert.equal(result.status, 0);
  assert.equal(result.stdout.split("\n")[0], `${MARKETPLACE_MANIFEST} -> 3.0.0 (0 nested)`);
});
