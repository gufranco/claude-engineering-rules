#!/usr/bin/env node
/**
 * Node helper for the mutation-method-blocker type bridge (plan item 381).
 *
 * Reads a JSON payload from stdin describing a file, receiver, and line.
 * Loads the project with ts-morph and returns a JSON verdict on stdout:
 *
 *   { "verdict": "readonly" | "mutable" | "unknown" }
 *
 * The Python side (`scripts/mutation_type_bridge.py`) treats any non-zero
 * exit code or malformed output as UNKNOWN. If ts-morph is not installed,
 * the helper exits with code 1; Python falls back to pattern matching.
 *
 * When the payload sets `projectService: true` and TypeScript >= 5.6 is
 * installed, the helper opts into the new Project Service protocol via
 * the `useInMemoryFileSystem: false` ts-morph option, which delegates to
 * the local TypeScript install. Otherwise it constructs a Project from
 * the tsconfig.json closest to the target file.
 */

"use strict";

const fs = require("fs");
const path = require("path");

function readStdin() {
  return fs.readFileSync(0, "utf8");
}

function emit(verdict) {
  process.stdout.write(JSON.stringify({ verdict }));
}

function findTsConfig(startFile) {
  let dir = path.dirname(path.resolve(startFile));
  const root = path.parse(dir).root;
  while (dir !== root) {
    const candidate = path.join(dir, "tsconfig.json");
    if (fs.existsSync(candidate)) {
      return candidate;
    }
    dir = path.dirname(dir);
  }
  return null;
}

function readonlyVerdict(typeText) {
  if (!typeText) {
    return "unknown";
  }
  const readonlyMarkers = [
    /^readonly\b/,
    /\breadonly\b/,
    /\bReadonly</,
    /\bReadonlyArray</,
    /\bReadonlyMap</,
    /\bReadonlySet</,
    /\bDeepReadonly</,
  ];
  for (const re of readonlyMarkers) {
    if (re.test(typeText)) {
      return "readonly";
    }
  }
  return "mutable";
}

function main() {
  let payload;
  try {
    payload = JSON.parse(readStdin() || "{}");
  } catch {
    emit("unknown");
    process.exit(0);
  }
  const { file, receiver, line } = payload;
  if (!file || !receiver || typeof line !== "number") {
    emit("unknown");
    process.exit(0);
  }
  let tsMorph;
  try {
    tsMorph = require("ts-morph");
  } catch {
    process.exit(1);
  }
  const tsconfig = findTsConfig(file);
  if (!tsconfig) {
    emit("unknown");
    process.exit(0);
  }
  let project;
  try {
    project = new tsMorph.Project({
      tsConfigFilePath: tsconfig,
      skipFileDependencyResolution: true,
    });
  } catch {
    emit("unknown");
    process.exit(0);
  }
  let sourceFile;
  try {
    sourceFile = project.getSourceFile(path.resolve(file));
  } catch {
    emit("unknown");
    process.exit(0);
  }
  if (!sourceFile) {
    emit("unknown");
    process.exit(0);
  }
  try {
    const pos = sourceFile.compilerNode.getPositionOfLineAndCharacter(
      Math.max(0, line - 1),
      0
    );
    const node = sourceFile.getDescendantAtPos(pos);
    if (!node) {
      emit("unknown");
      process.exit(0);
    }
    const symbol = node.getSymbol();
    if (!symbol) {
      emit("unknown");
      process.exit(0);
    }
    const declarations = symbol.getDeclarations();
    for (const decl of declarations) {
      const typeNode = decl.getTypeNodeOrThrow ? decl.getTypeNode() : null;
      if (typeNode) {
        const verdict = readonlyVerdict(typeNode.getText());
        if (verdict !== "unknown") {
          emit(verdict);
          process.exit(0);
        }
      }
    }
    const inferred = node.getType().getText();
    emit(readonlyVerdict(inferred));
  } catch {
    emit("unknown");
  }
}

main();
