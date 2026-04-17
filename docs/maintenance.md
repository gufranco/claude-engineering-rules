# Maintenance Schedule

Quarterly tasks that keep the configuration healthy and up-to-date.

---

## Q1 (January)

### Dependencies and runtimes

- [ ] Update all MCP server packages: `npx -y <package>@latest` for each entry in `settings.json`
- [ ] Check for new Claude Code releases: `claude --version`
- [ ] Review `standards/` files for outdated version references (Node.js LTS, Python, Go, Rust)
- [ ] Run `python3 scripts/validate-checklist-counts.py` and fix any count mismatches in README.md and CLAUDE.md

### Hook health

- [ ] Run `bash scripts/mcp-health-check.sh` — fix any FAIL entries
- [ ] Run `bash scripts/hook-benchmark.sh` — investigate any hook exceeding 500ms
- [ ] Verify all hooks in `settings.json` reference files that still exist in `hooks/`

### Memory hygiene

- [ ] Run `python3 scripts/stale-memory-detector.py` — review all WARN entries
- [ ] Delete or update memory files flagged as nearly empty or referencing non-existent paths
- [ ] Archive memory files older than 180 days if content is no longer relevant

---

## Q2 (April)

### Rule and standard review

- [ ] Read every file in `rules/` — remove rules that are now obvious defaults in Claude Code
- [ ] Read every file in `standards/` — check that examples match current library versions
- [ ] Review `rules/index.yml` trigger keywords — add or remove entries for changed rules and standards
- [ ] Check for Claude Code configuration schema updates at the Claude Code changelog

### Hook pattern updates

- [ ] Review `hooks/dangerous-command-blocker.py` CATASTROPHIC and CRITICAL_PATHS lists — add new cloud services and tools
- [ ] Review `hooks/secret-scanner.py` patterns — add new API key formats
- [ ] Run `hooks/conventional-commits.sh` on edge case commit messages to verify correctness

### Agent output format audit

- [ ] Run each custom agent on a sample task and verify JSON output matches the schema in its frontmatter
- [ ] Check that all agents in `agents/` appear in the agent table in README.md
- [ ] Verify `agents/TEMPLATE.md` reflects any new frontmatter fields added since last quarter

---

## Q3 (July)

### Checklist and skill review

- [ ] Audit `checklists/checklist.md` — add items for new OWASP entries or updated CWE classifications
- [ ] Review each skill in `skills/` — check subcommand examples against current Claude Code behavior
- [ ] Run each skill with `--help` equivalent and verify it matches the documentation in README.md
- [ ] Check `/pentest` skill checklists (BB-* and WB-*) for new vulnerability classes

### Security review

- [ ] Run `hooks/secret-scanner.py` against the `~/.claude/` directory itself — ensure no secrets landed in config files
- [ ] Verify all `mcpServers` entries in `settings.json` use `${ENV_VAR}` for credentials, never hardcoded values
- [ ] Check that `.gitignore` excludes all sensitive file patterns
- [ ] Review supply chain: check each npm package in `mcpServers` for known vulnerabilities

---

## Q4 (October)

### Annual retrospective

- [ ] Run `/retro` on a representative session and save findings to `rules/` or `standards/`
- [ ] Review memory files in `~/.claude/projects/*/memory/` — update stale facts, delete outdated entries
- [ ] Compare README.md feature counts (rules, standards, skills, hooks, agents) against actual file counts
- [ ] Archive spec folders older than 6 months: `mv specs/2024-*/ archive/specs/`

### Performance and token audit

- [ ] Measure context size at session start with and without on-demand standards — verify savings claim in README
- [ ] Run `rtk gain --history` to review token savings trend
- [ ] Identify any rule or standard that loads frequently and could be merged into CLAUDE.md
- [ ] Check `scripts/context-monitor.py` thresholds against current Claude context window sizes

---

## Ad-hoc triggers

Run these outside the quarterly schedule when specific events occur:

| Event | Action |
|:------|:-------|
| New Claude Code major version | Read changelog, update `autoUpdatesChannel` if beta channel is needed for testing |
| New MCP server released | Evaluate against existing servers, add to `settings.json` if it adds distinct capability |
| Security advisory for an MCP package | Immediately update or remove the affected server |
| Hook causes false positive | Add pattern to SAFE_CLEANUP (for rm) or update SUSPICIOUS threshold |
| New team member onboards | Walk through README.md workflows together, identify gaps |
| CI failure rate spikes | Review recent hook changes, check if a new pattern is too aggressive |
| Token costs increase unexpectedly | Run `rtk discover` to find commands not going through RTK |

---

## Maintenance log

Record completed maintenance runs here. Most recent first.

| Date | Who | What |
|:-----|:----|:-----|
| 2026-04-16 | — | Initial maintenance document created |
