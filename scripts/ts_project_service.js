#!/usr/bin/env node
/**
 * TypeScript Project Service helper for mutation-method-blocker.
 *
 * Plan item 394. Long-running Node process spawned by
 * scripts/mutation_ts_project_service.py. Reads NDJSON requests on
 * stdin and writes NDJSON responses to stdout. Uses the TypeScript
 * Project Service (TS 5.6+) to resolve receiver types at the mutation
 * site.
 *
 * Request shape:
 *
 *   { "id": "<uuid>", "file": "<abs path>", "line": <1-based>,
 *     "col": <0-based> }
 *
 * Response shape:
 *
 *   { "id": "<uuid>",
 *     "type": "<canonical type name>",
 *     "readonly": <boolean>,
 *     "kind": "array" | "map" | "set" | "typed-array" |
 *             "url-params" | "headers" | "form-data" | "other",
 *     "error": "<optional message>" }
 *
 * The helper falls back silently when:
 *   - typescript is not installed
 *   - the file is outside any tsconfig.json scope
 *   - position resolution fails
 *
 * Errors return `error` instead of `type`; the Python wrapper treats
 * any error as "not enough information" and continues with regex-only
 * analysis.
 */

'use strict';

let ts;
try {
  ts = require('typescript');
} catch (err) {
  process.stdout.write(
    JSON.stringify({ id: 'startup', error: 'typescript not installed' }) + '\n'
  );
  process.exit(0);
}

const TYPED_ARRAY_NAMES = new Set([
  'Int8Array', 'Uint8Array', 'Uint8ClampedArray',
  'Int16Array', 'Uint16Array',
  'Int32Array', 'Uint32Array',
  'Float16Array', 'Float32Array', 'Float64Array',
  'BigInt64Array', 'BigUint64Array',
]);

const READONLY_PATTERNS = [
  /^Readonly(?:Array|Map|Set)</,
  /^readonly\s+/,
  /\breadonly\s+\[/,
];

const PROJECT_CACHE_SENTINEL = Symbol('miss');
const projectCache = new Map();

function findTsConfig(filePath) {
  let dir = filePath;
  for (let i = 0; i < 64; i += 1) {
    dir = require('path').dirname(dir);
    if (!dir || dir === '/' || dir === '.') return null;
    const candidate = require('path').join(dir, 'tsconfig.json');
    if (require('fs').existsSync(candidate)) return candidate;
  }
  return null;
}

function loadProject(tsconfigPath) {
  const cached = projectCache.get(tsconfigPath);
  if (cached !== undefined) {
    return cached === PROJECT_CACHE_SENTINEL ? null : cached;
  }
  const cfg = ts.readConfigFile(tsconfigPath, ts.sys.readFile);
  if (cfg.error) {
    projectCache.set(tsconfigPath, PROJECT_CACHE_SENTINEL);
    return null;
  }
  const parsed = ts.parseJsonConfigFileContent(
    cfg.config, ts.sys, require('path').dirname(tsconfigPath)
  );
  const host = ts.createCompilerHost(parsed.options, true);
  const program = ts.createProgram({
    rootNames: parsed.fileNames,
    options: parsed.options,
    host,
  });
  const checker = program.getTypeChecker();
  const project = { program, checker, options: parsed.options };
  projectCache.set(tsconfigPath, project);
  return project;
}

function getNodeAtPosition(sourceFile, line, col) {
  const lineStarts = sourceFile.getLineStarts();
  const lineIdx = Math.max(0, Math.min(line - 1, lineStarts.length - 1));
  const lineStart = lineStarts[lineIdx];
  const lineEnd = lineIdx + 1 < lineStarts.length
    ? lineStarts[lineIdx + 1] : sourceFile.getEnd();
  const pos = Math.min(lineEnd - 1, lineStart + col);
  return findNodeAtPos(sourceFile, pos);
}

function findNodeAtPos(parent, pos) {
  let result = parent;
  parent.forEachChild((child) => {
    if (child.getStart() <= pos && pos < child.getEnd()) {
      const inner = findNodeAtPos(child, pos);
      if (inner) result = inner;
    }
  });
  return result;
}

function findReceiverNode(node) {
  let current = node;
  while (current && current.parent) {
    if (current.parent.kind === ts.SyntaxKind.PropertyAccessExpression) {
      return current.parent.expression;
    }
    if (current.parent.kind === ts.SyntaxKind.ElementAccessExpression) {
      return current.parent.expression;
    }
    current = current.parent;
  }
  return null;
}

function classify(typeText) {
  if (TYPED_ARRAY_NAMES.has(typeText)) return 'typed-array';
  for (const name of TYPED_ARRAY_NAMES) {
    if (typeText.startsWith(`${name}`)) return 'typed-array';
  }
  if (typeText === 'URLSearchParams' || typeText.startsWith('URLSearchParams<')) {
    return 'url-params';
  }
  if (typeText === 'Headers') return 'headers';
  if (typeText === 'FormData') return 'form-data';
  if (typeText.startsWith('Array<') || typeText.endsWith('[]')) return 'array';
  if (typeText.startsWith('ReadonlyArray<') || typeText.startsWith('readonly ')) {
    return 'array';
  }
  if (typeText.startsWith('Map<') || typeText.startsWith('ReadonlyMap<')) return 'map';
  if (typeText.startsWith('Set<') || typeText.startsWith('ReadonlySet<')) return 'set';
  return 'other';
}

function isReadonly(typeText) {
  return READONLY_PATTERNS.some((re) => re.test(typeText));
}

function answer(request) {
  const { id, file, line, col } = request;
  if (!file || typeof line !== 'number' || typeof col !== 'number') {
    return { id, error: 'invalid request shape' };
  }
  const tsconfig = findTsConfig(file);
  if (!tsconfig) return { id, error: 'tsconfig not found' };
  const project = loadProject(tsconfig);
  if (!project) return { id, error: 'project load failed' };
  const source = project.program.getSourceFile(file);
  if (!source) return { id, error: 'file not in project' };
  const node = getNodeAtPosition(source, line, col);
  if (!node) return { id, error: 'node not found' };
  const receiverNode = findReceiverNode(node);
  if (!receiverNode) {
    return { id, type: '', readonly: false, kind: 'other' };
  }
  try {
    const type = project.checker.getTypeAtLocation(receiverNode);
    const typeText = project.checker.typeToString(type);
    return {
      id,
      type: typeText,
      readonly: isReadonly(typeText),
      kind: classify(typeText),
    };
  } catch (err) {
    return { id, error: String(err && err.message ? err.message : err) };
  }
}

const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin, terminal: false });

rl.on('line', (raw) => {
  if (!raw || !raw.trim()) return;
  let request;
  try {
    request = JSON.parse(raw);
  } catch (err) {
    process.stdout.write(
      JSON.stringify({ id: 'parse', error: 'invalid json' }) + '\n'
    );
    return;
  }
  const response = answer(request);
  process.stdout.write(JSON.stringify(response) + '\n');
});

rl.on('close', () => process.exit(0));
