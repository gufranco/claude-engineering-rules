# eslint-plugin-mutation-method-blocker

ESLint plugin that surfaces mutation-method-blocker findings as ESLint diagnostics, so editors that highlight ESLint output (VS Code, IntelliJ, Neovim) show the same warnings as CI.

The plugin shells out to `hooks/mutation-method-blocker.py` in batch mode with `MUTATION_METHOD_OUTPUT=sarif`, parses the SARIF document, and emits one diagnostic per finding.

## Install

```bash
pnpm add -D eslint-plugin-mutation-method-blocker
```

Peer dependency: `eslint >= 8.0.0`. Requires `python3` on `PATH`.

## Configure

Flat config (`eslint.config.js`):

```javascript
import mutation from 'eslint-plugin-mutation-method-blocker';

export default [
  mutation.configs.recommended,
];
```

Legacy config (`.eslintrc.cjs`):

```javascript
module.exports = {
  plugins: ['mutation-method-blocker'],
  extends: ['plugin:mutation-method-blocker/recommended'],
};
```

## Hook path resolution

Resolution order for the Python hook script:

1. `options.hookPath` passed to `resolveHookPath`.
2. `MUTATION_METHOD_HOOK_PATH` environment variable.
3. Relative path resolved from the plugin install location: `../../hooks/mutation-method-blocker.py`.

Override the location when the plugin is installed outside the dot-claude repo:

```bash
export MUTATION_METHOD_HOOK_PATH=/path/to/mutation-method-blocker.py
```

## How findings map to ESLint severity

| SARIF level | ESLint severity |
|-------------|-----------------|
| `error` | 2 (error) |
| `warning` | 1 (warn) |
| `note` | 1 (warn) |

The plugin does not provide autofixes. Apply the suggested replacement from the `message` field manually, or rely on the hook's stderr output for the full fix hint.

## Performance

Each file is scanned by spawning a Python subprocess. For projects with thousands of files, prefer running the hook directly in CI with the SARIF output uploaded to GitHub code scanning. The ESLint plugin is best for inner-loop editor feedback.
