import { readFile } from "node:fs/promises";
import { argv, cwd, exit } from "node:process";

const CONFIG_PATH = ".releaserc.json";
const PLUGIN_NAME = "@semantic-release/release-notes-generator";

const SAMPLE_COMMITS = [
  {
    hash: "0000000000000000000000000000000000000001",
    message: "feat(rules): add a rule\n\nBody text.",
    subject: "add a rule",
    committerDate: "2026-01-01",
  },
  {
    hash: "0000000000000000000000000000000000000002",
    message: "fix(hooks): stop a misfire",
    subject: "stop a misfire",
    committerDate: "2026-01-02",
  },
  {
    hash: "0000000000000000000000000000000000000003",
    message: "perf(hooks): cut startup cost\n\nBREAKING CHANGE: removes a bypass.",
    subject: "cut startup cost",
    committerDate: "2026-01-03",
  },
];

async function readPluginConfig() {
  const raw = JSON.parse(await readFile(CONFIG_PATH, "utf8"));
  const entry = (raw.plugins ?? []).find(
    (plugin) => plugin === PLUGIN_NAME || (Array.isArray(plugin) && plugin[0] === PLUGIN_NAME),
  );
  if (!entry) {
    throw new Error(`${PLUGIN_NAME} is not configured in ${CONFIG_PATH}`);
  }
  return Array.isArray(entry) ? (entry[1] ?? {}) : {};
}

function buildContext() {
  return {
    cwd: cwd(),
    options: { repositoryUrl: "https://github.com/gufranco/claude-engineering-rules" },
    lastRelease: { gitTag: "v0.1.0", version: "0.1.0" },
    nextRelease: { gitTag: "v0.2.0", version: "0.2.0", type: "minor" },
    commits: SAMPLE_COMMITS,
    logger: { log: () => {}, error: () => {} },
  };
}

function assertRendered(notes) {
  if (typeof notes !== "string" || notes.trim() === "") {
    throw new Error("the generator produced empty release notes");
  }
  const missing = ["add a rule", "stop a misfire"].filter((text) => !notes.includes(text));
  if (missing.length > 0) {
    throw new Error(`rendered notes omitted expected commits: ${missing.join(", ")}`);
  }
}

async function main() {
  const pluginConfig = await readPluginConfig();
  const { generateNotes } = await import(PLUGIN_NAME);
  const notes = await generateNotes(pluginConfig, buildContext());
  assertRendered(notes);
  if (argv.includes("--print")) {
    console.log(notes);
  }
  console.log(`release notes render with preset "${pluginConfig.preset ?? "angular"}"`);
}

main().catch((error) => {
  console.error(`verify-release-notes failed: ${error.message}`);
  exit(1);
});
