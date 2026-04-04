# Documentation Generation

## API Documentation

### OpenAPI (REST APIs)

- Every REST API must have an OpenAPI spec. Hand-written or generated from code annotations
- Generate from code as the primary strategy. Decorators or annotations produce the spec as a build artifact. The spec never drifts from the implementation
- Validate the spec in CI: `openapi-generator validate` or `spectral lint`. A spec with warnings is a failing build

| Framework | Generation method |
|-----------|------------------|
| NestJS | `@nestjs/swagger` decorators on controllers and DTOs |
| Express | `swagger-jsdoc` with JSDoc comments, or `tsoa` for code-first |
| FastAPI | Automatic from type hints and Pydantic models |
| Go (Gin/Echo) | `swaggo/swag` from comments, or code-first with `ogen` |

Rules:
- Every endpoint has a description, request/response schema, and error responses documented
- Use `$ref` for shared schemas. No inline schema duplication
- Include example values for every field. Consumers should understand the API from the spec alone
- Version the spec alongside the code. Tag releases with the spec version

### AsyncAPI (Event-Driven APIs)

For message-based APIs (Kafka topics, RabbitMQ exchanges, WebSocket channels):

- Define message schemas with AsyncAPI spec
- Include channel bindings (topic name, exchange type, routing key)
- Document message ordering guarantees and delivery semantics
- Generate consumer SDKs from the spec when consumers are external

### GraphQL

- The schema IS the documentation. Introspection provides the spec
- Add descriptions to every type, field, and argument in the schema definition
- Use `@deprecated(reason: "...")` directive for deprecated fields
- Generate a static reference site from the schema for external consumers

## Code Documentation

### TypeDoc (TypeScript)

- Document public interfaces, exported functions, and module entry points
- Skip internal implementation details. If a function is not exported, it does not need a doc comment
- Use `@param`, `@returns`, `@throws`, and `@example` tags
- Generate HTML or Markdown output as a CI artifact

### Other Languages

| Language | Tool | Standard |
|----------|------|----------|
| Python | Sphinx with autodoc, or mkdocstrings | Google or NumPy docstring style |
| Go | godoc (built-in) | Package-level comments + exported function comments |
| Rust | rustdoc (built-in) | `///` doc comments with examples that compile |
| Java/Kotlin | Javadoc / Dokka | Every public class and method documented |

## Documentation as Code

- Store documentation in the repository alongside the code it describes
- Use Markdown for prose documentation. It renders on GitHub/GitLab, works with static site generators, and diffs cleanly
- CI builds the documentation site on every push. Broken links and missing references are build failures
- Deploy documentation automatically on merge to main

## Versioning

- Documentation versions must match software versions. v2 docs for v2 API
- Keep previous versions accessible. Users on v1 need v1 docs
- Use a version selector in the documentation site (Docusaurus, MkDocs Material, GitBook all support this)
- When deprecating a version, add a banner linking to the latest version. Do not delete old docs

## Validation in CI

| Check | Tool | What it catches |
|-------|------|-----------------|
| OpenAPI spec validity | spectral, openapi-generator validate | Schema errors, missing required fields |
| Markdown links | markdown-link-check, lychee | Broken internal and external links |
| Code examples | doctest (Python), rustdoc --test (Rust) | Examples that no longer compile or produce wrong output |
| Spelling | cspell, aspell | Typos in documentation |
| API/code sync | Compare OpenAPI spec against route definitions | Drift between docs and implementation |

## Related Standards

- `standards/api-design.md`: API Design
- `standards/graphql-api-design.md`: GraphQL API Design
