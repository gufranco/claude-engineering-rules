# Clean Room Implementation

## Core Rule

Every implementation that uses external projects, codebases, articles, or any third-party source as inspiration, reference, or knowledge must pass a clean room verification before completion. No exceptions. A clean implementation means: the output is independently created from abstract requirements, not derived from copying or close adaptation of someone else's work.

## Why This Exists

Using external sources for ideas is normal engineering practice. The risk is not learning from others. The risk is producing output that is substantially similar to the source, which creates exposure to copyright infringement claims, license violation lawsuits, trade secret misappropriation, and patent disputes. "I changed the variable names" is not a defense. "I rewrote it in a different language" is not a defense. Courts use structural similarity tests that look past surface differences.

## The Clean Room Process

### Phase 1: Research (study the source)

1. Read the external source to understand WHAT it does and WHY.
2. Extract only abstract concepts: functional requirements, algorithmic ideas, data flow patterns, architectural decisions.
3. Document these as plain-language requirements with no code snippets, no structure copies, no naming from the source.
4. Close the source. Do not refer to it again during implementation.

### Phase 2: Implementation (work from requirements only)

1. Implement from the plain-language requirements alone.
2. Use your own naming conventions, your own structure, your own control flow.
3. Make independent design decisions at every level: file organization, function decomposition, error handling, data structures.
4. When multiple valid approaches exist, prefer one that diverges from the source's approach.

### Phase 3: Verification (prove independence)

Run every check in the verification checklist below. All must pass.

## Verification Checklist

### A. Structural Independence

| Check | What to verify | How |
|-------|---------------|-----|
| A1. File structure | Your file/module organization differs from the source | Compare directory trees side by side. Identical hierarchies fail |
| A2. Function decomposition | Functions are split and grouped differently | List function names and responsibilities from both. Identical decomposition fails |
| A3. Class/module hierarchy | Inheritance chains, composition patterns, and module boundaries are your own design | Map both hierarchies. Mirror structures fail |
| A4. Data flow | The sequence of transformations and data passing differs | Trace data through both systems. Identical pipelines fail |
| A5. API surface | Public interfaces (routes, exports, method signatures) are independently designed | Compare public APIs. Identical signatures with identical parameter ordering fail |

### B. Naming Independence

| Check | What to verify | How |
|-------|---------------|-----|
| B1. Variable names | No variable or constant names copied from the source | Grep for distinctive names from the source. Any match requires renaming to something independently chosen |
| B2. Function names | Function and method names are your own | Compare function name lists. Identical non-standard names fail (standard names like `get`, `set`, `parse` are exempt) |
| B3. Type/class names | Types, interfaces, classes, and enums use your own naming | Compare type name lists. Identical domain-specific names fail |
| B4. File names | Source files are named independently | Compare file name lists. Identical non-conventional names fail (conventional names like `index.ts`, `main.go` are exempt) |
| B5. String literals | Error messages, log messages, and user-facing text are original | Search for distinctive string literals from the source. Any match fails |
| B6. Comments | No comments copied or closely paraphrased from the source | Compare comment text. Identical or near-identical phrasing fails |

### C. Logic Independence

| Check | What to verify | How |
|-------|---------------|-----|
| C1. Algorithm expression | Algorithms are expressed in your own way, even if the abstract algorithm is the same | Compare implementations of the same algorithm. Identical variable names, loop structures, and conditional ordering in combination fail |
| C2. Control flow | Branching logic, guard clauses, and loop structures differ | Compare control flow graphs. Identical branching patterns with identical conditions fail |
| C3. Error handling | Error types, messages, and recovery strategies are independently designed | Compare error handling blocks. Identical error hierarchies and messages fail |
| C4. Edge case handling | Edge cases are handled based on your own analysis, not copied from the source | List edge cases handled in both. Identical edge case lists with identical handling fail |
| C5. Validation logic | Input validation rules are derived from requirements, not copied | Compare validation sequences. Identical validation ordering and messages fail |
| C6. State management | State shape, transitions, and storage are independently designed | Compare state structures. Identical state shapes with identical transition logic fail |

### D. Configuration and Infrastructure Independence

| Check | What to verify | How |
|-------|---------------|-----|
| D1. Config structure | Configuration files use your own structure and key names | Compare config schemas. Identical non-standard keys and nesting fail |
| D2. Build configuration | Build scripts and tool configuration are independently written | Compare build configs. Identical custom scripts or non-default settings in the same combination fail |
| D3. Database schema | Table names, column names, and relationships are your own design | Compare schemas. Identical non-obvious column names and relationship patterns fail |
| D4. Test structure | Tests verify the same requirements but are structured independently | Compare test files. Identical test descriptions, identical setup sequences, and identical assertion patterns in combination fail |

### E. License and Legal Compliance

| Check | What to verify | How |
|-------|---------------|-----|
| E1. License compatibility | The source's license permits learning from it (most do, but some restrict derivative works) | Read the source's LICENSE file. Identify the license type. Verify it does not prohibit derivative works or require specific attribution for ideas |
| E2. Copyleft contamination | If the source uses GPL, AGPL, or similar copyleft licenses, your implementation is not a derivative work | Verify structural and expressive independence. Copyleft applies to derivative works. A clean room implementation of the same idea is not a derivative work if it passes checks A through D |
| E3. Patent exposure | The source does not contain patented algorithms that your implementation reproduces | Search for patent notices in the source's README, LICENSE, and PATENTS files. If patents exist, verify your implementation uses a different approach |
| E4. Trade secrets | If the source was accessed through NDA, employer access, or leaked materials, do not use it at all | Confirm the source is publicly available. If it was accessed through any restricted channel, stop and do not use any knowledge from it |
| E5. Attribution requirements | Some licenses (MIT, Apache 2.0, BSD) require attribution when you copy code, but not when you independently implement the same idea | If your implementation passes checks A through D, no attribution is required for idea-level inspiration. If any check fails, you may need attribution or a rewrite |
| E6. No code transplant | No function, class, or block was copied and pasted from the source, even partially | Search for any sequence of 4+ lines that matches the source. Any match fails unconditionally |

### F. Documentation Independence

| Check | What to verify | How |
|-------|---------------|-----|
| F1. README content | Your documentation describes your implementation in your own words | Compare documentation text. Identical paragraphs or closely paraphrased sections fail |
| F2. API documentation | Endpoint descriptions, parameter docs, and examples are original | Compare API docs. Identical descriptions fail |
| F3. Architecture docs | System design documentation reflects your own decisions | Compare architecture descriptions. Identical diagrams and explanations fail |
| F4. Code comments | Inline documentation is written from your understanding, not copied | Spot-check comments against source comments. Paraphrased copies fail |

### G. Output and Behavior Differentiation

| Check | What to verify | How |
|-------|---------------|-----|
| G1. User-facing output | Error messages, help text, CLI output, and UI text are original | Compare user-facing strings. Identical distinctive phrasing fails |
| G2. Logging format | Log message format and content differ from the source | Compare log patterns. Identical custom log formats fail |
| G3. Response format | API responses use your own envelope structure and field naming | Compare response shapes. Identical non-standard envelope structures fail |

## Similarity Thresholds

These thresholds guide judgment. They are not exact metrics, since similarity is qualitative. Use them to calibrate your assessment.

| Level | Meaning | Action |
|-------|---------|--------|
| Identical | Code blocks match character-for-character or with only whitespace/naming changes | Rewrite from scratch. This is copying |
| Substantially similar | Same structure, same logic flow, same decomposition, different surface syntax | Rewrite the similar sections. Choose different design decisions |
| Conceptually similar | Same abstract approach, but different expression, structure, and design choices | Acceptable. This is independent implementation of the same idea |
| Coincidentally similar | Small fragments (3-5 lines) that resemble the source due to language idioms or standard patterns | Acceptable. Standard patterns (for loops, null checks, common library usage) are not copyrightable |

## What Is Always Safe

These cannot be owned by the source and do not require clean room treatment:

- Programming language syntax and idioms
- Standard library usage
- Common design patterns (MVC, repository, factory, observer)
- Well-known algorithms (binary search, quicksort, BFS/DFS) implemented in your own way
- Framework conventions (NestJS module structure, React component patterns, Express middleware)
- Industry-standard protocols and formats (REST conventions, JWT structure, OAuth flows)
- Mathematical formulas and scientific facts
- Publicly documented API contracts and specifications

## What Is Never Safe

These always require clean room treatment, regardless of how small:

- Copying code blocks, even with variable renaming
- Copying file/folder structures that reflect creative design choices
- Copying error messages, help text, or user-facing strings
- Copying test cases (the specific inputs and expected outputs, not the concept of testing a feature)
- Copying configuration values that reflect non-obvious design decisions
- Copying documentation text or comments
- Translating code from one language to another while preserving structure and logic

## When to Apply This Rule

| Situation | Clean room required? |
|-----------|---------------------|
| Studying a competitor's open-source project for feature ideas | Yes |
| Reading a blog post about an algorithm and implementing it | Yes, for code examples in the post. No, for the abstract algorithm description |
| Using a library as a dependency (importing it) | No. Using a library is not copying it |
| Forking a project and modifying it | No. This is a derivative work governed by the fork's license, not clean room |
| Reading framework documentation and following its patterns | No. Framework conventions are not copyrightable |
| Porting a feature from your own previous project | Depends. If you own the code or have a license to it, no. If it was work-for-hire owned by an employer, yes |
| Studying a project's data model to understand the domain | Yes, for the specific schema design. No, for domain concepts (a "user has orders" relationship is not copyrightable) |
| Reading a patent and implementing the described method | Do not implement patented methods without a license, regardless of clean room process |

## Process for Each External Source

When you use any external project as a reference:

1. **Record the source.** Note what was consulted: URL, repo, article.
2. **Extract abstract requirements.** Write what you learned as plain-language functional requirements. No code, no structure diagrams from the source.
3. **Close the source.** Stop referring to it.
4. **Implement independently.** Work from your requirements document.
5. **Run the verification checklist.** All sections A through G.
6. **Document the result.** State what source was consulted and confirm clean room verification passed. This documentation protects you if questioned later.

## Enforcement

This rule applies to every deliverable: production code, tests, documentation, configuration, infrastructure-as-code, database schemas, and scripts. No output is exempt.

When a verification check fails, do not ship. Rewrite the failing section with genuinely independent design choices until all checks pass. "Close enough" is not passing.
