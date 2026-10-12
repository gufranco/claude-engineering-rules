# Documentation Generation

## API Documentation

### OpenAPI (REST APIs)

- Every REST API must have an OpenAPI spec. Hand-written or generated from code annotations
- Generate from code as the primary strategy. Decorators or annotations produce the spec as a build artifact. The spec never drifts from the implementation
- Validate the spec in CI: `openapi-generator validate` or `spectral lint`. A spec with warnings is a failing build

| Framework | Generation method |
|-----------|------------------|
| NestJS | `@nestjs/swagger` decorators on controllers and DTOs |
| Express | `tsoa` for code-first. `swagger-jsdoc` is rejected: it drives the spec from JSDoc prose |
| FastAPI | Automatic from type hints and Pydantic models |
| Go (Gin/Echo) | `ogen` for code-first. `swaggo/swag` is rejected: it drives the spec from comments |

Rules:
- Every endpoint has a description, request/response schema, and error responses documented
- Use `$ref` for shared schemas. No inline schema duplication
- Include example values for every field. Consumers should understand the API from the spec alone
- Version the spec alongside the code. Tag releases with the spec version

### AsyncAPI (Event-Driven APIs)

For message-based APIs, Kafka topics, RabbitMQ exchanges, WebSocket channels:

- Define message schemas with AsyncAPI spec
- Include channel bindings such as topic name, exchange type, or routing key
- Document message ordering guarantees and delivery semantics
- Generate consumer SDKs from the spec when consumers are external

### GraphQL

- The schema IS the documentation. Introspection provides the spec
- Add descriptions to every type, field, and argument in the schema definition
- Use `@deprecated(reason: "...")` directive for deprecated fields
- Generate a static reference site from the schema for external consumers

## Code Documentation

Doc comments and docstrings are comments, and comments are banned in every language per [`code-style.md`](../rules/code-style.md). Code reference documentation is therefore generated from names, signatures, and types alone, and the prose lives in Markdown files beside the code.

### TypeDoc (TypeScript)

- Generate the reference for public interfaces, exported functions, and module entry points from their signatures and types
- Put usage prose and examples in the module's Markdown guide, never in a doc comment
- Generate HTML or Markdown output as a CI artifact

### Other Languages

| Language | Tool | Standard |
|----------|------|----------|
| Python | mkdocs with mkdocstrings | Reference from type hints and signatures; prose in Markdown pages, no docstrings |
| Go | pkgsite or `go doc` | Reference from exported identifiers and types; prose in a per-package Markdown guide, no doc comments |
| Rust | rustdoc (built-in) | Reference from signatures; prose and compiled examples in the crate's Markdown guide pulled in with the `include_str!` doc attribute, no `///` blocks |
| Java/Kotlin | Javadoc / Dokka | Reference from public signatures; prose in Markdown module docs, no Javadoc blocks |

## Documentation as Code

- Store documentation in the repository alongside the code it describes
- Use Markdown for prose documentation. It renders on GitHub/GitLab, works with static site generators, and diffs cleanly
- CI builds the documentation site on every push. Broken links and missing references are build failures
- Deploy documentation automatically on merge to main

## Versioning

- Documentation versions must match software versions. v2 docs for v2 API
- Keep previous versions accessible. Users on v1 need v1 docs
- Use a version selector in the documentation site such as Docusaurus, MkDocs Material, or GitBook all support this
- When deprecating a version, add a banner linking to the latest version. Do not delete old docs

## Validation in CI

| Check | Tool | What it catches |
|-------|------|-----------------|
| OpenAPI spec validity | spectral, openapi-generator validate | Schema errors, missing required fields |
| Markdown links | markdown-link-check, lychee | Broken internal and external links |
| Code examples | `pytest --doctest-glob='*.md'` (Python), `cargo test --doc` over included Markdown (Rust) | Examples that no longer compile or produce wrong output |
| Spelling | cspell, aspell | Typos in documentation |
| API/code sync | Compare OpenAPI spec against route definitions | Drift between docs and implementation |

## Related Standards

- [`standards/api-design.md`](api-design.md): API Design
- [`standards/graphql-api-design.md`](graphql-api-design.md): GraphQL API Design
