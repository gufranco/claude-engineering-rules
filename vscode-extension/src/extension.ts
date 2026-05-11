import * as path from 'node:path';
import { spawn } from 'node:child_process';
import { text } from 'node:stream/consumers';
import {
  type Disposable,
  type ExtensionContext,
  type TextDocument,
  Diagnostic,
  DiagnosticSeverity,
  Range,
  Uri,
  languages,
  window,
  workspace,
} from 'vscode';

const COLLECTION_NAME = 'mutation-method-blocker';
const SUPPORTED_LANGUAGES: readonly string[] = Object.freeze([
  'typescript',
  'typescriptreact',
  'javascript',
  'javascriptreact',
]);

type LspSeverity = 1 | 2 | 3 | 4;

type LspDiagnostic = Readonly<{
  range: {
    start: { line: number; character: number };
    end: { line: number; character: number };
  };
  severity: LspSeverity;
  code: string;
  source: string;
  message: string;
  codeDescription?: { href: string };
}>;

type LspDocument = Readonly<{
  uri: string;
  diagnostics: readonly LspDiagnostic[];
}>;

const SEVERITY_MAP: Readonly<Record<LspSeverity, DiagnosticSeverity>> = Object.freeze({
  1: DiagnosticSeverity.Error,
  2: DiagnosticSeverity.Warning,
  3: DiagnosticSeverity.Information,
  4: DiagnosticSeverity.Hint,
});

function resolveHookPath(): string {
  const configured = workspace
    .getConfiguration('mutationMethodBlocker')
    .get<string>('hookPath');
  if (configured && configured.length > 0) {
    return configured;
  }
  return path.resolve(__dirname, '..', '..', '..', 'hooks', 'mutation-method-blocker.py');
}

async function scanDocument(doc: TextDocument): Promise<readonly LspDocument[]> {
  if (!SUPPORTED_LANGUAGES.includes(doc.languageId)) {
    return [];
  }
  const hookPath = resolveHookPath();
  const child = spawn('python3', [hookPath], {
    env: {
      ...process.env,
      MUTATION_METHOD_BATCH_MODE: '1',
      MUTATION_METHOD_OUTPUT: 'lsp',
    },
  });
  child.stdin.write(doc.uri.fsPath + '\n');
  child.stdin.end();
  try {
    const stdout = await text(child.stdout);
    return JSON.parse(stdout || '[]') as LspDocument[];
  } catch (error) {
    window.showErrorMessage(
      `mutation-method-blocker: ${(error as Error).message}`
    );
    return [];
  }
}

function toVsDiagnostic(diag: LspDiagnostic): Diagnostic {
  const range = new Range(
    diag.range.start.line,
    diag.range.start.character,
    diag.range.end.line,
    diag.range.end.character
  );
  const vsDiag = new Diagnostic(range, diag.message, SEVERITY_MAP[diag.severity]);
  // VS Code API exposes `code` and `source` as writable instance fields.
  // No constructor variant accepts them, so direct assignment is the only path.
  vsDiag.code = diag.code; // claude-allow-mutation -- vscode.Diagnostic instance fields
  vsDiag.source = diag.source; // claude-allow-mutation -- vscode.Diagnostic instance fields
  return vsDiag;
}

async function refreshDocument(
  doc: TextDocument,
  collection: ReturnType<typeof languages.createDiagnosticCollection>
): Promise<void> {
  const documents = await scanDocument(doc);
  const next = documents
    .filter((d) => d.uri === doc.uri.toString())
    .flatMap((d) => d.diagnostics.map(toVsDiagnostic));
  // DiagnosticCollection.set is the public VS Code API for publishing
  // diagnostics; there is no immutable alternative.
  collection.set(doc.uri, next); // claude-allow-mutation -- vscode.DiagnosticCollection API
}

export function activate(context: ExtensionContext): void {
  const collection = languages.createDiagnosticCollection(COLLECTION_NAME);
  const disposables: readonly Disposable[] = Object.freeze([
    collection,
    workspace.onDidSaveTextDocument((doc) => void refreshDocument(doc, collection)),
    workspace.onDidOpenTextDocument((doc) => void refreshDocument(doc, collection)),
    workspace.onDidCloseTextDocument((doc) => collection.delete(doc.uri)), // claude-allow-mutation -- vscode.DiagnosticCollection API
  ]);
  // context.subscriptions is the VS Code framework's disposal registry.
  // The host owns the array; extensions are expected to push into it.
  for (const disposable of disposables) {
    context.subscriptions.push(disposable); // claude-allow-mutation -- vscode.ExtensionContext.subscriptions framework receiver
  }
  if (window.activeTextEditor) {
    void refreshDocument(window.activeTextEditor.document, collection);
  }
}

export function deactivate(): void {
  // Disposal handled via context.subscriptions registered in activate().
}
