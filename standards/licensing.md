# Licensing

## Core Rule

Every source file must declare its license with an SPDX-License-Identifier header and a copyright notice. A root LICENSE file covers the repository. Per-file identifiers cover individual files when they travel outside the repository: vendored into other projects, shared as snippets, extracted into new repos, or scanned by compliance tooling.

## SPDX-License-Identifier Format

Place the identifier as the first possible comment line in the file. For scripts with a shebang (`#!`), use the second line.

| File type | Format | Rationale |
|-----------|--------|-----------|
| TypeScript, JavaScript, Go, Rust, C, C++, Device Tree | `// SPDX-License-Identifier: MIT` | C++ style comment |
| C headers, Assembly | `/* SPDX-License-Identifier: MIT */` | Block comment for compatibility with older assemblers and preprocessors |
| Python, Ruby, Shell, YAML, TOML | `# SPDX-License-Identifier: MIT` | Hash comment |
| HTML, XML, SVG | `<!-- SPDX-License-Identifier: MIT -->` | HTML comment |
| CSS | `/* SPDX-License-Identifier: MIT */` | Block comment |
| SQL | `-- SPDX-License-Identifier: MIT` | SQL comment |
| reStructuredText | `.. SPDX-License-Identifier: MIT` | RST comment |
| Markdown | Not required. Documentation, not source code |
| JSON, JSONC | Not possible. Use REUSE.toml or `.license` sidecar |
| Generated files | Not required. Machine-generated output is excluded |
| Binary files (images, fonts, PDFs) | Not possible. Use `.license` sidecar file |

The expression must be on a single line. No line breaks in the middle of the expression.

### Sidecar `.license` Files

For files that cannot contain comments, create a sidecar file with the same name plus `.license`:

```
logo.png           # binary, no comments possible
logo.png.license   # contains SPDX metadata
```

Sidecar file content:

```
SPDX-FileCopyrightText: 2026 Gustavo Franco
SPDX-License-Identifier: MIT
```

Use sidecar files for: images, fonts, PDFs, compiled binaries, data files, and any format that does not support comments.

## SPDX-FileCopyrightText

Use `SPDX-FileCopyrightText` as the copyright tag. This is the REUSE 3.3 recommended format, machine-readable by compliance tools.

```typescript
// SPDX-FileCopyrightText: 2026 Gustavo Franco
// SPDX-License-Identifier: MIT
```

Format: `SPDX-FileCopyrightText: [year] [holder] <[contact]>`

| Scenario | Format |
|----------|--------|
| Single author | `SPDX-FileCopyrightText: 2026 Gustavo Franco` |
| Year range | `SPDX-FileCopyrightText: 2024-2026 Gustavo Franco` |
| With contact | `SPDX-FileCopyrightText: 2026 Gustavo Franco <gus@example.com>` |
| Organization | `SPDX-FileCopyrightText: 2026 Acme Corp` |
| Multiple holders | One `SPDX-FileCopyrightText` line per holder |
| No copyright (machine-generated) | `SPDX-FileCopyrightText: NONE` |

`Copyright` and the copyright symbol are also accepted for backward compatibility, but prefer `SPDX-FileCopyrightText` for new files.

Do not add a full license text block. The identifier plus the root LICENSE file is sufficient.

## License Expressions

SPDX license expressions combine identifiers with operators. Use the exact identifier from the [SPDX License List](https://spdx.org/licenses/).

### Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| (none) | Single license | `MIT` |
| `+` | "Or later version" | `GPL-2.0-or-later` (preferred) or `GPL-2.0+` |
| `WITH` | License with exception | `GPL-2.0-only WITH Classpath-exception-2.0` |
| `AND` | Must comply with both | `MIT AND Apache-2.0` |
| `OR` | Choice between licenses | `MIT OR Apache-2.0` |

### Operator Precedence (highest to lowest)

1. `+` (unary suffix, no whitespace before it)
2. `WITH`
3. `AND`
4. `OR`

`LGPL-2.1-only OR BSD-3-Clause AND MIT` evaluates as `LGPL-2.1-only OR (BSD-3-Clause AND MIT)` because AND binds tighter than OR. Use parentheses to override: `(LGPL-2.1-only OR BSD-3-Clause) AND MIT`.

### Syntax Rules

- Operators are case-sensitive: use all uppercase (`AND`, `OR`, `WITH`) or all lowercase (`and`, `or`, `with`). Do not mix
- No whitespace between license-id and `+`
- Whitespace required on both sides of `WITH`, `AND`, `OR`
- Expression must be a single line. No line breaks
- Parentheses to override precedence

### GNU License Suffix Rule

Never use bare GNU identifiers. Always append `-only` or `-or-later`:

| Wrong | Correct |
|-------|---------|
| `GPL-2.0` | `GPL-2.0-only` or `GPL-2.0-or-later` |
| `GPL-3.0` | `GPL-3.0-only` or `GPL-3.0-or-later` |
| `LGPL-2.1` | `LGPL-2.1-only` or `LGPL-2.1-or-later` |
| `AGPL-3.0` | `AGPL-3.0-only` or `AGPL-3.0-or-later` |

The bare forms are deprecated in the SPDX License List.

### Custom Licenses

For licenses not on the SPDX list, use `LicenseRef-` prefix:

```
SPDX-License-Identifier: LicenseRef-Proprietary
SPDX-License-Identifier: LicenseRef-CompanyName-Internal
```

Provide the full license text in the `LICENSES/` directory as `LicenseRef-<name>.txt`.

## Content-Type License Mapping

Different content types have different licensing needs:

| Content type | Recommended license | SPDX identifier |
|-------------|-------------------|-----------------|
| Source code | MIT, Apache-2.0 | `MIT`, `Apache-2.0` |
| Documentation | Creative Commons Attribution | `CC-BY-4.0` |
| Data and datasets | Community Data License Agreement | `CDLA-Permissive-2.0` |
| Specifications | Community Specification | `Community-Spec-1.0` |
| Media assets (images, fonts) | Same as project or CC-BY-4.0 | Varies |
| Configuration and metadata | Same as project | Same as project |

When a project uses different licenses for different content types, each file's SPDX identifier must match its governing license.

## When to Add the Header

| Situation | Action |
|-----------|--------|
| Creating a new source file | Add SPDX-FileCopyrightText + SPDX-License-Identifier on the first lines |
| Modifying an existing file that lacks the header | Add it in the same commit as the change |
| Binary files (images, fonts, PDFs) | Create a `.license` sidecar file |
| Generated files (Prisma client, compiled output, lockfiles) | Skip. Machine-generated |
| Third-party vendored files | Preserve the original license header. Never replace with yours |
| Configuration files (JSON, .env) | Use REUSE.toml for bulk assignment or `.license` sidecar |
| Test files | Add the header. Tests are source code |
| Migration files | Add the header. Migrations are source code |
| Minified JavaScript/CSS | Use the minifier's option to preserve the header comment. If unavailable, use `.license` sidecar |

## Snippet Tags

When a file contains code under a different license from the rest of the file, use SPDX snippet tags:

```typescript
// SPDX-SnippetBegin
// SPDX-SnippetCopyrightText: 2024 Other Author
// SPDX-License-Identifier: Apache-2.0

function borrowedFunction() {
  // code under Apache-2.0
}

// SPDX-SnippetEnd
```

Rules:
- Every `SPDX-SnippetBegin` must have a matching `SPDX-SnippetEnd`
- Snippets must contain both a copyright notice and a license identifier
- Snippets can nest (inner tags apply to innermost snippet)
- Use snippet tags only when the license genuinely differs. Do not tag every function

## Ignore Blocks

When license identifiers appear in documentation, examples, or output (not as actual file licensing), wrap them in ignore blocks to prevent false positives from compliance tools:

```markdown
<!-- REUSE-IgnoreStart -->
Example: `SPDX-License-Identifier: MIT`
<!-- REUSE-IgnoreEnd -->
```

## LICENSES/ Directory

Store the full license text for every license referenced in the project. Place files in a `LICENSES/` directory at the project root:

```
LICENSES/
  MIT.txt
  Apache-2.0.txt
  CC-BY-4.0.txt
  LicenseRef-Proprietary.txt
```

File naming: `<SPDX-identifier>.<extension>`. Plain text format.

Every license identifier and exception used in any SPDX expression in the project must have a corresponding file in `LICENSES/`. This enables automated verification.

For single-license projects, a root `LICENSE` file is sufficient. The `LICENSES/` directory is required when the project uses multiple licenses or when adopting full REUSE compliance.

## License Compatibility

When combining code under different licenses, verify compatibility before mixing.

### Compatibility Rules

| Combination | Compatible? | Notes |
|-------------|------------|-------|
| Permissive + Permissive | Yes | MIT, BSD, ISC, Apache-2.0 all combine freely |
| Permissive + Copyleft | Usually | Combined work distributed under copyleft terms. Permissive obligations (attribution) must also be met |
| Apache-2.0 + GPL-2.0-only | Disputed | Some view Apache-2.0 patent clause as GPL-2.0 incompatible. Apache-2.0 + GPL-3.0 is compatible |
| Copyleft + Copyleft (different) | Rarely | GPL-2.0-only and GPL-3.0-only are incompatible with each other unless `-or-later` is used |
| Any + Proprietary | Depends | Permissive licenses allow it. Copyleft licenses require releasing combined work under copyleft |
| CC licenses + Code | No | Creative Commons licenses are not designed for software. Use for docs and media only |

### When to Check Compatibility

- Adding a vendored file with a different license
- Incorporating code from a Stack Overflow answer, blog post, or external project
- Adding a dependency with a copyleft license to a permissive project
- Dual-licensing a file or project

When in doubt, consult legal counsel. License compatibility is context-specific.

## REUSE.toml Configuration

REUSE.toml replaces the deprecated `.reuse/dep5` format. Use it for bulk licensing of files that cannot contain comments.

```toml
version = 1

[[annotations]]
path = "assets/**"
SPDX-FileCopyrightText = "2026 Gustavo Franco"
SPDX-License-Identifier = "CC-BY-4.0"

[[annotations]]
path = ["*.json", "*.env.example", ".gitignore"]
SPDX-FileCopyrightText = "2026 Gustavo Franco"
SPDX-License-Identifier = "MIT"

[[annotations]]
path = "vendor/**"
precedence = "override"
SPDX-FileCopyrightText = "2024 Third Party Corp"
SPDX-License-Identifier = "Apache-2.0"
```

### Precedence

| Value | Behavior |
|-------|----------|
| `closest` (default) | File's own header preferred. Falls back to nearest REUSE.toml |
| `aggregate` | Combines file header with REUSE.toml annotations |
| `override` | REUSE.toml replaces file header. Use for vendored files with incorrect headers |

### Rules

- REUSE.toml and DEP5 are mutually exclusive. Never use both
- REUSE.toml can be placed in subdirectories for monorepo structures
- Multiple REUSE.toml files allowed in different directories
- Glob patterns: `*` matches except slashes, `**` matches including slashes
- Must include `version = 1`

### Migrating from DEP5

```bash
reuse convert-dep5
```

This converts `.reuse/dep5` to `REUSE.toml` and deletes the old file.

## CI Enforcement

### GitHub Actions

```yaml
name: REUSE Compliance

on: [push, pull_request]

permissions:
  contents: read

jobs:
  reuse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: fsfe/reuse-action@v6
```

Additional commands:

```yaml
# Generate SPDX SBOM
- uses: fsfe/reuse-action@v6
  with:
    args: spdx

# Include submodules
- uses: fsfe/reuse-action@v6
  with:
    args: --include-submodules lint
```

### GitLab CI

```yaml
reuse:
  image: fsfe/reuse:latest
  script:
    - reuse lint
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/fsfe/reuse-tool
    rev: v6.0.0
    hooks:
      - id: reuse
```

### Local Verification

```bash
# Install
pipx install reuse

# Check compliance
reuse lint

# Add headers to files
reuse annotate --license MIT --copyright "Gustavo Franco" src/main.ts

# Generate SPDX SBOM
reuse spdx -o project.spdx

# Migrate from DEP5
reuse convert-dep5
```

Integrate `reuse lint` into CI to prevent unlicensed files from being merged.

## Connection to SBOM

SPDX-License-Identifier headers feed into SBOM generation. When a CI pipeline generates an SBOM in SPDX or CycloneDX format, per-file license declarations produce accurate, granular license inventories. Without per-file headers, the SBOM tool must guess licenses from the root LICENSE file, which fails for multi-license projects and vendored code.

The `reuse spdx` command generates a complete SPDX document from the project's license metadata, suitable for inclusion in CI artifacts.

## What Not to Do

- Do not add the full license text to every file. The SPDX identifier replaces boilerplate headers
- Do not invent license identifiers. Use only identifiers from the SPDX License List or the `LicenseRef-` prefix
- Do not add SPDX headers to files you do not own. Preserve original headers on vendored or third-party code
- Do not use bare GNU identifiers (`GPL-2.0`, `LGPL-2.1`). Always append `-only` or `-or-later`
- Do not use `SPDX-License-Identifier: UNLICENSED`. Use `LicenseRef-Proprietary` for proprietary code
- Do not skip the header because "it is just a config file." If it supports comments and contains logic you wrote, it gets a header
- Do not break expressions across lines. The entire expression must be a single line
- Do not use Creative Commons licenses for source code. CC licenses lack patent grants and are not designed for software
- Do not use `.reuse/dep5`. It is deprecated. Use REUSE.toml instead
- Do not mix REUSE.toml and DEP5 in the same project
