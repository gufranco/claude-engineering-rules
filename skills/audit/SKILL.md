---
name: audit
description: Run a full security audit across dependencies, secrets, Dockerfiles, and code patterns.
---

Run a multi-layer security audit of the current project. Orchestrates dependency vulnerability scanning, secret detection across the full repo, Dockerfile security checks, and code pattern analysis for common vulnerabilities. Produces a single prioritized report.

## When to use

- Before a release or deploy to production.
- During periodic security reviews.
- When onboarding into a new codebase and want a security baseline.
- After a dependency update to verify nothing introduced vulnerabilities.

## When NOT to use

- For a single dependency check. Use `/deps` instead.
- For reviewing a specific PR. Use `/review` instead.

## Arguments

This skill accepts optional arguments after `/audit`:

- No arguments: run all audit layers.
- `--deps`: only run dependency vulnerability scanning.
- `--secrets`: only run secret scanning across the full repo.
- `--docker`: only run Dockerfile security checks.
- `--code`: only run code pattern analysis.

## Steps

1. **Detect project type and available tools.** Run these **in parallel**:
   - Identify languages and frameworks from manifest files: `package.json`, `go.mod`, `Cargo.toml`, `pyproject.toml`, `Gemfile`, `requirements.txt`, `pom.xml`, `build.gradle`.
   - Check for Dockerfiles: `Dockerfile`, `docker-compose.yml`, `docker-compose.yaml`.
   - Check available scanning tools: `which npm`, `which pnpm`, `which pip-audit`, `which cargo-audit`, `which trivy`, `which grype`, `which semgrep`, `which bandit`.
   - Read `.env.example` to understand expected environment variables.

2. **Dependency vulnerability scan.** For each detected language:
   - **Node.js:** run `pnpm audit --json 2>/dev/null || npm audit --json 2>/dev/null`. Parse results by severity.
   - **Python:** run `pip-audit --format json` if available, else `pip install pip-audit && pip-audit --format json`.
   - **Go:** run `govulncheck ./...` if available.
   - **Rust:** run `cargo audit --json` if available.
   - **Ruby:** run `bundle audit check` if available.
   - For each vulnerability found, record: package name, installed version, fixed version, severity, CVE ID, description.

3. **Secret scanning.** Scan the entire repository for leaked secrets:
   - Use the same patterns from `~/.claude/hooks/secret-scanner.py` but scan all tracked files, not just staged changes.
   - Run: `git ls-files` to get all tracked files.
   - For each file, skip binary files, lockfiles, and vendored code.
   - Scan for all patterns defined in the secret scanner.
   - Also check `.gitignore` to verify that `.env`, `*.pem`, `*.key`, and credential files are listed.
   - Check if `.env.example` exists and documents all required env vars.

4. **Dockerfile security checks.** For each Dockerfile found:
   - Check base image: is it pinned to a specific digest or tag, or using `latest`?
   - Check for `USER` directive: running as root is a finding.
   - Check for `COPY` of sensitive files: `.env`, `*.key`, `*.pem`, `credentials.*`.
   - Check for `apt-get install` without `--no-install-recommends`.
   - Check for missing `HEALTHCHECK` directive.
   - Check for exposed ports that should not be public.
   - If `trivy` is available, run `trivy image --severity HIGH,CRITICAL <image>` on built images.

5. **Code pattern analysis.** Scan source files for common vulnerability patterns:
   - **SQL injection:** look for string concatenation in SQL queries, template literals with user input in queries.
   - **Command injection:** look for `exec`, `spawn`, `system`, `eval` with dynamic input.
   - **XSS:** look for `dangerouslySetInnerHTML`, `innerHTML`, `document.write` with user input.
   - **Path traversal:** look for user input in file path construction without validation.
   - **Hardcoded secrets:** look for assignments to variables named `password`, `secret`, `token`, `api_key` with string literals.
   - **Insecure randomness:** look for `Math.random()` used for security purposes like tokens or IDs.
   - **Missing error handling:** look for empty catch blocks.
   - If `semgrep` is available, run `semgrep --config auto --json` for deeper analysis.
   - If `bandit` is available and Python code exists, run `bandit -r . --format json`.

6. **Compile the report.** Organize findings by severity:

   ```
   ## Security Audit Report

   **Project:** <name>
   **Date:** <date>
   **Layers scanned:** dependencies, secrets, docker, code

   ---

   ### Critical (fix immediately)

   <findings with severity critical>

   ### High (fix before next release)

   <findings with severity high>

   ### Medium (schedule fix)

   <findings with severity medium>

   ### Low (backlog)

   <findings with severity low>

   ---

   ### Summary

   | Layer | Critical | High | Medium | Low |
   |-------|----------|------|--------|-----|
   | Dependencies | N | N | N | N |
   | Secrets | N | N | N | N |
   | Docker | N | N | N | N |
   | Code patterns | N | N | N | N |

   ### Missing safeguards

   - [ ] .gitignore covers .env and credential files
   - [ ] .env.example documents all required env vars
   - [ ] Dockerfiles use non-root user
   - [ ] Dependencies have no critical vulnerabilities
   ```

7. **Suggest next steps.** Based on findings:
   - If critical vulnerabilities: suggest immediate fixes with specific commands.
   - If secrets found: suggest removing them from git history with `git filter-repo`.
   - If Docker issues: suggest Dockerfile improvements.
   - If missing tooling: suggest installing `trivy`, `semgrep`, or language-specific audit tools.

## Rules

- Never install scanning tools without asking first. Report what is and is not available.
- Never modify code or fix vulnerabilities automatically. Report findings and let the user decide.
- Never expose actual secret values in the report. Show the file, line number, and pattern name only.
- Always scan `.env.example`, never `.env` files directly.
- If no vulnerabilities are found in any layer, say so clearly. A clean audit is a valid result.
- Do not generate false positives. If a pattern match looks like a false positive based on context, note it as such.
- Classify findings by actual severity, not by quantity. One critical SQL injection matters more than ten low-priority style issues.

## Related skills

- `/deps` - Deeper dependency analysis with outdated package detection.
- `/review` - Security-aware code review of specific changes.
- `/test` - Run tests to verify security fixes do not break functionality.
