---
name: rules-lang-readme
description: Language-specific rules subdir. Place per-language guidance here when the rule applies to one language only.
---

# Language-Specific Rules

This directory holds rules that apply to a single programming language. Cross-language rules stay in the parent `rules/` directory.

## When to add a file here

| Place a rule here | Place a rule in parent rules/ |
|------------------|------------------------------|
| Applies to one language (TypeScript, Rust, Go, Python, etc.) | Applies to multiple languages |
| Names a language-specific tool (cargo, gofmt, ruff) | Names cross-cutting concepts (security, testing, performance) |
| Encodes idioms, syntax, or runtime semantics | Encodes process, design, or workflow |

## Index integration

When you add a file here, register it in `rules/index.yml` under the `on_demand` section with triggers that match the language name and its tooling. The file is not auto-loaded; the assistant pulls it when triggers match.

## Naming convention

`<language-slug>.md` where the slug matches the language name in lowercase, kebab-case for multi-word names. Examples: `typescript.md`, `rust.md`, `python.md`, `c-sharp.md`.

## Existing flat rules

The flat files in `standards/` (`go.md`, `rust.md`, `jvm.md`, `postgresql.md`, `typescript-5x.md`) are not moved. They remain authoritative until superseded by entries here. New language guidance goes here going forward.
