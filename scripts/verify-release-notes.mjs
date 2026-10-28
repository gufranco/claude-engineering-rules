import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { argv, cwd, exit } from "node:process";

export const CONFIG_PATH = ".releaserc.json";
export const PLUGIN_NAME = "@semantic-release/release-notes-generator";

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

export async function readPluginConfig(root) {
  const raw = JSON.parse(await readFile(join(root, CONFIG_PATH), "utf8"));
  const entry = (raw.plugins ?? []).find(
    (plugin) => plugin === PLUGIN_NAME || (Array.isArray(plugin) && plugin[0] === PLUGIN_NAME),
  );
  if (!entry) {
    throw new Error(`${PLUGIN_NAME} is not configured in ${CONFIG_PATH}`);
  }
  return Array.isArray(entry) ? (entry[1] ?? {}) : {};
}

export function buildContext(root) {
  return {
    cwd: root,
    options: { repositoryUrl: "https://github.com/gufranco/claude-engineering-rules" },
    lastRelease: { gitTag: "v0.1.0", version: "0.1.0" },
    nextRelease: { gitTag: "v0.2.0", version: "0.2.0", type: "minor" },
    commits: SAMPLE_COMMITS,
    logger: { log: () => {}, error: () => {} },
  };
}

export function assertRendered(notes) {
  if (typeof notes !== "string" || notes.trim() === "") {
    throw new Error("the generator produced empty release notes");
  }
  const missing = ["add a rule", "stop a misfire"].filter((text) => !notes.includes(text));
  if (missing.length > 0) {
    throw new Error(`rendered notes omitted expected commits: ${missing.join(", ")}`);
  }
}

export async function verify(root, args, generateNotes, log) {
  const pluginConfig = await readPluginConfig(root);
  const notes = await generateNotes(pluginConfig, buildContext(root));
  assertRendered(notes);
  if (args.includes("--print")) {
    log(notes);
  }
  log(`release notes render with preset "${pluginConfig.preset ?? "angular"}"`);
}

export async function run(root, args, generateNotes, log, fail) {
  try {
    await verify(root, args, generateNotes, log);
    return 0;
  } catch (error) {
    fail(`verify-release-notes failed: ${error.message}`);
    return 1;
  }
}

if (import.meta.main) {
  const { generateNotes } = await import(PLUGIN_NAME);
  exit(await run(cwd(), argv.slice(2), generateNotes, console.log, console.error));
}
