# Mutation Method Blocker (VS Code)

Surfaces mutation-method-blocker findings inline in VS Code by running the Python hook in LSP output mode and converting the diagnostics into the editor's native `vscode.Diagnostic` collection.

## Status

This is scaffolding only. The publish-to-marketplace step is a follow-up. The extension compiles, activates, and posts diagnostics when run from a development host.

## Run from source

```bash
cd vscode-extension
pnpm install
pnpm run compile
```

Open the folder in VS Code, press F5 to launch the Extension Development Host, and open a TypeScript file. The extension scans on open and on save.

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `mutationMethodBlocker.hookPath` | `""` | Absolute path to the Python hook. Empty means the extension resolves to the sibling `hooks/` directory. |
| `mutationMethodBlocker.severity` | `"warning"` | Minimum confidence surfaced as a diagnostic. |
| `mutationMethodBlocker.experimentalDetectors` | `[]` | List of `MUTATION_METHOD_EXPERIMENTAL_*` flags to enable for the host. |

## Limitations

- Spawns a Python subprocess per scan. For very large files (>10k lines), the latency is noticeable. CI is still the canonical enforcement surface.
- Does not deduplicate against ESLint findings. If you also use `eslint-plugin-mutation-method-blocker`, expect each finding to appear twice. Pick one integration per project.
- The Diagnostic `code` field is set via direct assignment because the VS Code Diagnostic constructor does not accept it. This is the canonical pattern in the VS Code samples.
