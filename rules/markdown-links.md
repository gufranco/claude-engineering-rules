# Markdown Link Discipline

Every file mention in repo markdown prose is a clickable relative link when the file exists.

- Use plain or code-styled link text; paths resolve relative to the containing document and are case-sensitive.
- Exempt: fenced code, command spans, front matter, HTML comments, and generic names like `package.json`.
- Link only the first mention per section. Check with `python3 .github/scripts/validate-markdown-links.py`.

Full rule, examples, and rationale: [`standards/markdown-links.md`](../standards/markdown-links.md). Read it before editing repo markdown heavily.
