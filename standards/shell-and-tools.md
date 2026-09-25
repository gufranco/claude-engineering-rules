# External Tools and Shell Safety

Full text of the External Tools section of the global instructions. [`CLAUDE.md`](../CLAUDE.md) carries the always-loaded summary.

Before using any external tool or CLI command:

1. **Verify tool is installed.** Run `which <tool>` or `<tool> --version`.
2. **If not installed.** Ask before installing.
3. **Never assume availability.** Even common tools like gh, docker, and aws may not be installed.
4. **Linux package management.** Never use Homebrew on Linux. Use the distribution's native package manager.
5. **Preferred package manager.** Use pnpm for JavaScript and TypeScript projects. Never default to npm.
6. **Respect rate limits.** Before polling any API or service in a loop, check the rate limit first. For GitHub: `gh api rate_limit`. For other services: check headers or docs. Never use tight polling loops (e.g. every 3 seconds) without confirming sufficient quota. When rate limited, wait for the reset window instead of retrying immediately.
7. **Local binaries first.** Never run a CLI tool through Docker when a local binary exists or can be installed. Check `which <tool>` first. If not installed, ask to install it locally (e.g., `brew install postgresql` for `psql`). Only fall back to Docker when local installation is not viable or the user explicitly prefers it. Docker wrappers add complexity, consume extra tokens, and obscure errors. When the user accepts a brew install, check `~/.dotfiles/Brewfile` and ask whether the package should be added there.
8. **Clone over fetch.** When analyzing source from a repo not already on disk, clone it to a `mktemp -d` directory and work locally. Never fetch source files one at a time via `gh api .../contents`, `gh repo view`, or `raw.githubusercontent.com`. The break-even is two files; at three, clone. Full rule, carve-outs, and subagent briefing: [`rules/repo-analysis.md`](../rules/repo-analysis.md).
9. **Name the account on every multi-account CLI call.** `gh`, `glab`, `docker`, `kubectl`, `aws`, `gcloud`, and `terraform` each resolve a globally active account that another terminal can change mid-task, so the ambient one is never trustworthy. Read the account from `git remote get-url origin`, then pass it per command: `GH_TOKEN=$(gh auth token --user <account>) gh ...`. This applies to the first call of a session, including a throwaway status check. Per-tool detail: [`standards/multi-account-cli.md`](multi-account-cli.md).
10. **A real engine is always available for rendered output.** `agent-browser` is provisioned globally through mise, so there is no case where a UI claim has to rest on reading source. `agent-browser open <url>`, then `eval` for computed style on `document.activeElement`, `snapshot -i` for the accessibility tree, `set device "iPhone 12"` for viewport. Simulators for mobile through `xcrun simctl` and `adb`. Run `agent-browser skills get core --full` before a longer flow instead of guessing flags. The obligation this serves: [`rules/frontend-render-gate.md`](../rules/frontend-render-gate.md).

## Shell Alias Safety

Commands may be aliased (e.g., `du`→`dust` or `ls`→`eza`), changing flags and output. Always prefix with `command` to bypass: `command du -sh`, `command ls -la`. Applies to any command where you rely on standard flags or output format.

**`command` does not fix the implementation.** It bypasses aliases and functions, never PATH order. A bare tool name resolves to whichever implementation sits earliest on PATH, and that is often not the platform's stock one: GNU coreutils installed alongside a BSD userland, busybox applets on a minimal image, or a language shim ahead of the system binary. The silent case is a flag both implementations accept with different meanings, which yields wrong output instead of an error. `stat -f` selects a format string in the BSD implementation and filesystem mode in the GNU one; `sed -i` takes a mandatory suffix argument in one and an optional one in the other. Never infer flag semantics from the operating system. Resolve the name first with `command -v`, pin the absolute path when a specific implementation is required, or choose a form with no split at all, such as `wc -c <file` in place of either `stat`. This also bounds what a local run proves: a script exercised where PATH front-loads one implementation has not been tested against a host shipping the other, so cross-platform claims need a run per target.

**zsh special parameters.** zsh ties several lowercase names to shell state, and `local` does not shield them: `local path=...` inside a function replaces `PATH` for that scope, so every external command stops resolving and the error names the command rather than the cause, `command not found: head`. `local status=...` fails differently, as `read-only variable: status`. Treat `path`, `status`, `argv`, `cdpath`, `fpath`, `manpath`, `mailpath`, `module_path`, `fignore`, `psvar`, and `watch` as reserved names and pick `target`, `file`, or `dir` instead. This binds any script that zsh sources, whatever its shebang says, so a file written as portable shell still needs to avoid these names.

**zsh parameter modifiers.** The shell is zsh, where a colon after a variable introduces a modifier rather than literal text. `:r`, `:h`, `:e`, `:t`, `:s`, `:a`, and `:l` are all consumed. `git show $BRANCH:readme.md` silently drops the leading `r` and passes a mangled ref, and the error names a path nobody wrote. Brace and quote whenever a variable is followed by a colon: `git show "${BRANCH}:readme.md"`. The safest form for a git ref is to write it literally rather than build it from a variable.

**zsh unquoted globs.** zsh expands a glob wherever it appears on the command line, including inside a flag argument, and aborts the entire command when nothing matches instead of passing the pattern through. `grep -rn "x" --include=*.ts .` fails with `no matches found: --include=*.ts` and runs nothing, because no file by that name exists in the current directory. The same shape bites `find . -name *.py` and `git log -- *.md`, and it bites any tool that expects to receive the pattern itself rather than the shell's expansion of it. Quote every pattern meant for the tool: `--include="*.ts"`, `-name '*.py'`. The error text names the flag rather than the shell, so it reads as the tool rejecting an option it in fact supports, which is what sends the next attempt looking in the wrong place.

## Shell Argument Safety (MANDATORY)

Bash history expansion converts `!` to `\!` in double-quoted strings. Variable expansion, backtick execution, and backslash processing also apply. Any text payload passed through a double-quoted shell argument, code snippets, Markdown, prose with punctuation, will be silently corrupted.

**Rule: always use a single-quoted heredoc delimiter when passing text content to any CLI tool.**

```bash
# WRONG: Bash history expansion corrupts ! and backticks
gh api ... --field body="if (!x) { return; }"

# CORRECT: single-quoted delimiter disables ALL shell expansion inside
gh api ... --field body="$(cat <<'PAYLOAD'
if (!x) { return; }
PAYLOAD
)"
```

Applies to: `gh api`, `curl -d`, `jq --arg`, `git commit -m` with multi-line bodies, and any invocation where text content flows through a shell command substitution or argument string. The single-quoted form `<<'PAYLOAD'` is the only fully safe one. The unquoted form `<<PAYLOAD` still expands `$var` and backticks.

**Author files with the Write tool, never a Bash heredoc, when the content contains command-like text.** Hooks inspect the raw command string before the shell runs it, and nothing in that string separates source text inside a heredoc from a command about to execute. A file whose body legitimately contains a privileged device write, a filesystem-format call, or a forced delete is therefore refused when authored through `cat > file <<'EOF'`, and the refusal covers the entire call, so nothing is written and no earlier part of the command ran either. The Write tool carries the same bytes and is evaluated as file content, which makes it the correct tool for authoring any script, fixture, or test harness. The trap is wider than a script: a CI workflow that sets a bot's git identity, and a rule or standard that quotes a protected-branch push as an example, are both prose, and both are refused through a heredoc for the same reason. If the content you are about to write would be blocked when executed, author it with a file tool. The single-quoted heredoc rule above still governs payloads that must genuinely flow through a CLI argument, such as a commit body. The neighbouring case, an audit grep that spells out the pattern it hunts for, is covered under Hook Bypass Discipline; there the fix is building the literal from fragments, never a bypass.

**Config repo paths in Bash.** When operating on the personal Claude config repo from a Bash command, write `$HOME/.claude` or the absolute path (`/Users/<user>/.claude`). Never the literal token `~/.claude` in the command string. The internal-config-leakage hook scans the raw Bash command before the shell expands the tilde, so a tilde-prefixed path triggers a block even when the operation is purely local. The `CONFIG_LEAKAGE_DISABLE=1` env var also fails to bypass when set inline because the hook reads the command string before assignments take effect; export it in a parent shell or use `$HOME/.claude` instead.
