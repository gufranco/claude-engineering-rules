# Mutation Method Blocker (JetBrains)

JetBrains IDE plugin that wraps the mutation-method-blocker hook so WebStorm, IntelliJ IDEA Ultimate, and PyCharm Professional show mutation findings as native inspections.

## Status

This is scaffolding only. The publish step uses `signPlugin` and `publishPlugin` Gradle tasks, but credentials are not bundled. Publishing happens in a follow-up.

## Build

```bash
cd jetbrains-plugin
./gradlew buildPlugin
```

The output `.zip` lands in `build/distributions/`. Install it in a running IDE via `Settings -> Plugins -> Install Plugin from Disk...`.

## Compatibility

- Requires IDE 2024.1 or later (build number 241+). 2024.1 introduced first-class LSP support.
- JavaScript plugin is mandatory. Bundled in WebStorm; an add-on for IDEA Ultimate.
- Untested in IDEA Community because the JavaScript plugin is not available there.

## Configuration

`Settings -> Tools -> Mutation Method Blocker` exposes:

- **Hook path**: absolute path to the Python script. Falls back to the user-level installation under the dot-claude config repo.

The plugin reads `MUTATION_METHOD_HOOK_PATH` from the IDE environment if the setting is empty.

## Internals

The plugin implements `ExternalAnnotator` and calls the Python hook via `ProcessBuilder` with `MUTATION_METHOD_OUTPUT=lsp`. The LSP `Diagnostic[]` payload is parsed with `kotlinx.serialization` and converted to IDE annotations.

Performance: the IDE re-runs annotators on a debounce after typing pauses. For large files (>10k lines), expect a 200-500ms scan latency, the same ballpark as the SARIF-based CI run.
