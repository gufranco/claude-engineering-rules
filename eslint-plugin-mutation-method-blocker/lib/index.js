'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const PLUGIN_NAME = 'mutation-method-blocker';
const PLUGIN_VERSION = '3.0.0';
const DEFAULT_HOOK = path.resolve(
  __dirname,
  '..',
  '..',
  'hooks',
  'mutation-method-blocker.py'
);

function resolveHookPath(options) {
  if (options && typeof options.hookPath === 'string' && options.hookPath.length > 0) {
    return path.resolve(options.hookPath);
  }
  const fromEnv = process.env.MUTATION_METHOD_HOOK_PATH;
  if (fromEnv && fromEnv.length > 0) {
    return path.resolve(fromEnv);
  }
  return DEFAULT_HOOK;
}

function levelToSeverity(level) {
  if (level === 'error') {
    return 2;
  }
  if (level === 'warning') {
    return 1;
  }
  return 1;
}

function runHook(hookPath, filename) {
  const env = Object.assign({}, process.env, {
    MUTATION_METHOD_BATCH_MODE: '1',
    MUTATION_METHOD_OUTPUT: 'sarif',
  });
  const result = spawnSync('python3', [hookPath], {
    input: filename + '\n',
    env,
    encoding: 'utf8',
    timeout: 15000,
  });
  if (result.error) {
    return { ok: false, error: result.error.message };
  }
  if (result.status !== 0 && result.status !== 2) {
    return { ok: false, error: `hook exited with code ${result.status}: ${result.stderr}` };
  }
  try {
    return { ok: true, document: JSON.parse(result.stdout || '{}') };
  } catch (parseError) {
    return { ok: false, error: `failed to parse SARIF output: ${parseError.message}` };
  }
}

function diagnosticForResult(result, ruleById, absoluteFilename) {
  const location = result.locations && result.locations[0];
  if (!location) {
    return null;
  }
  const physical = location.physicalLocation;
  if (!physical) {
    return null;
  }
  const uri = (physical.artifactLocation && physical.artifactLocation.uri) || '';
  if (uri && path.resolve(uri) !== absoluteFilename) {
    return null;
  }
  const region = physical.region || {};
  const rule = ruleById.get(result.ruleId) || {};
  return {
    ruleId: `${PLUGIN_NAME}/${result.ruleId}`,
    severity: levelToSeverity(
      result.level || (rule.defaultConfiguration && rule.defaultConfiguration.level)
    ),
    message: (result.message && result.message.text) || rule.name || 'mutation detected',
    line: region.startLine || 1,
    column: region.startColumn || 1,
    nodeType: null,
    source: (region.snippet && region.snippet.text) || null,
  };
}

function diagnosticsForFile(document, absoluteFilename) {
  if (!document || !Array.isArray(document.runs)) {
    return [];
  }
  return document.runs.flatMap((run) => {
    const rules = (run.tool && run.tool.driver && run.tool.driver.rules) || [];
    const ruleById = new Map(rules.map((rule) => [rule.id, rule]));
    return (run.results || [])
      .map((result) => diagnosticForResult(result, ruleById, absoluteFilename))
      .filter((entry) => entry !== null);
  });
}

function buildProcessor() {
  const findingsByFilename = new Map();
  return {
    preprocess(text, filename) {
      const absoluteFilename = path.resolve(filename);
      const hookPath = resolveHookPath();
      if (!fs.existsSync(hookPath)) {
        findingsByFilename.set(absoluteFilename, []);
        return [text];
      }
      const outcome = runHook(hookPath, absoluteFilename);
      if (!outcome.ok) {
        findingsByFilename.set(absoluteFilename, []);
        return [text];
      }
      findingsByFilename.set(
        absoluteFilename,
        diagnosticsForFile(outcome.document, absoluteFilename)
      );
      return [text];
    },
    postprocess(messages, filename) {
      const absoluteFilename = path.resolve(filename);
      const fromHook = findingsByFilename.get(absoluteFilename) || [];
      findingsByFilename.delete(absoluteFilename);
      const fromEslint = (messages && messages[0]) || [];
      return [...fromEslint, ...fromHook];
    },
    supportsAutofix: false,
  };
}

const processor = buildProcessor();

const rules = {
  'no-mutation': {
    meta: {
      type: 'problem',
      docs: {
        description:
          'Report in-place mutations detected by the mutation-method-blocker hook.',
        category: 'Possible Errors',
        recommended: true,
        url: 'https://github.com/onyxodds/dot-claude/blob/main/rules/lang/typescript-immutability.md',
      },
      schema: [],
      messages: {
        mutation: '{{ message }}',
      },
    },
    create() {
      return {};
    },
  },
};

const configs = {
  recommended: {
    plugins: [PLUGIN_NAME],
    processor: `${PLUGIN_NAME}/wrap`,
    rules: {
      [`${PLUGIN_NAME}/no-mutation`]: 'error',
    },
  },
};

const internal = {
  buildProcessor,
  diagnosticsForFile,
  diagnosticForResult,
  levelToSeverity,
  resolveHookPath,
};

Object.assign(module.exports, { // claude-allow-mutation -- CommonJS module export, no functional alternative
  meta: { name: PLUGIN_NAME, version: PLUGIN_VERSION },
  rules,
  processors: { wrap: processor },
  configs,
  internal,
});
