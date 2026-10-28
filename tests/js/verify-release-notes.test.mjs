import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  CONFIG_PATH,
  PLUGIN_NAME,
  assertRendered,
  buildContext,
  readPluginConfig,
  run,
} from "../../scripts/verify-release-notes.mjs";

const SCRIPT = fileURLToPath(new URL("../../scripts/verify-release-notes.mjs", import.meta.url));
const REPO_ROOT = fileURLToPath(new URL("../../", import.meta.url));

async function rootWithConfig(config) {
  const root = await mkdtemp(join(tmpdir(), "release-notes-"));
  await writeFile(join(root, CONFIG_PATH), JSON.stringify(config), "utf8");
  return root;
}

function collector() {
  const lines = [];
  return { lines, push: (line) => lines.push(line) };
}

const GOOD_NOTES = async () => "## 0.2.0\n\n* add a rule\n* stop a misfire\n";

test("readPluginConfig accepts a bare plugin name", async () => {
  // Arrange
  const root = await rootWithConfig({ plugins: [PLUGIN_NAME] });

  // Act
  const config = await readPluginConfig(root);

  // Assert
  assert.deepEqual(config, {});
});

test("readPluginConfig reads the options of a tuple entry", async () => {
  // Arrange
  const root = await rootWithConfig({ plugins: ["other", [PLUGIN_NAME, { preset: "x" }]] });

  // Act
  const config = await readPluginConfig(root);

  // Assert
  assert.deepEqual(config, { preset: "x" });
});

test("readPluginConfig treats a tuple without options as empty", async () => {
  // Arrange
  const root = await rootWithConfig({ plugins: [[PLUGIN_NAME]] });

  // Act
  const config = await readPluginConfig(root);

  // Assert
  assert.deepEqual(config, {});
});

test("buildContext points at the given root with quiet loggers", () => {
  // Arrange
  const root = "/repo";

  // Act
  const context = buildContext(root);

  // Assert
  assert.equal(context.cwd, root);
  assert.equal(context.logger.log(), undefined);
  assert.equal(context.logger.error(), undefined);
});

test("assertRendered rejects empty notes and notes missing a commit", () => {
  // Arrange
  const cases = ["", 7, "* add a rule only"];

  // Act
  const messages = cases.map((notes) => {
    try {
      assertRendered(notes);
      return "";
    } catch (error) {
      return error.message;
    }
  });

  // Assert
  assert.deepEqual(messages, [
    "the generator produced empty release notes",
    "the generator produced empty release notes",
    "rendered notes omitted expected commits: stop a misfire",
  ]);
});

test("run prints the notes and the preset when asked", async () => {
  // Arrange
  const root = await rootWithConfig({ plugins: [[PLUGIN_NAME, { preset: "conventionalcommits" }]] });
  const out = collector();

  // Act
  const code = await run(root, ["--print"], GOOD_NOTES, out.push, out.push);

  // Assert
  assert.equal(code, 0);
  assert.deepEqual(out.lines, [
    await GOOD_NOTES(),
    'release notes render with preset "conventionalcommits"',
  ]);
});

test("run reports the default preset and a missing plugin", async () => {
  // Arrange
  const configured = await rootWithConfig({ plugins: [PLUGIN_NAME] });
  const missing = await rootWithConfig({});
  const ok = collector();
  const bad = collector();

  // Act
  const codes = [
    await run(configured, [], GOOD_NOTES, ok.push, ok.push),
    await run(missing, [], GOOD_NOTES, bad.push, bad.push),
  ];

  // Assert
  assert.deepEqual(codes, [0, 1]);
  assert.deepEqual(ok.lines, ['release notes render with preset "angular"']);
  assert.deepEqual(bad.lines, [
    `verify-release-notes failed: ${PLUGIN_NAME} is not configured in ${CONFIG_PATH}`,
  ]);
});

test("the script renders this repository's release notes", () => {
  // Arrange
  const options = { cwd: REPO_ROOT, encoding: "utf8" };

  // Act
  const result = spawnSync(process.execPath, [SCRIPT], options);

  // Assert
  assert.equal(result.status, 0);
  assert.match(result.stdout, /^release notes render with preset /);
});
