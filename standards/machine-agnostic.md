# Machine-Agnostic Output

Everything a repository holds and everything published from it must read the same for any person on any machine. A value from the machine that wrote it is a leak twice over: it exposes the author, and it breaks or misleads every other user.

## What counts as a machine identifier

| Kind | Shape | Neutral replacement |
|---|---|---|
| Home directory path | `/Users/<login>/...`, `/home/<login>/...`, the dashed project slug Claude Code derives from it | `$HOME/...` built at runtime, `/home/user` in a fixture |
| Login name | the account name as a plain argument or path segment | `user`, `octocat` for a GitHub user in a demo |
| Host name | the computer name, the local host name | `localhost`, `example-host` |
| Real name | the owner's name in a fixture, a CLI flag, a test expectation | a seeded faker name |
| Personal email | a mailbox address outside authorship | `user@example.com` |
| Local folder name | client or employer folders, private category folders above the repository | `work`, `project`, `clients/acme` |
| Terminal window or session name | tmux window and session names copied from the live layout | `main`, `editor`, `two words` |
| Live session id | the id of the running agent session | `00000000-0000-4000-8000-000000000000` or `uuid4()` |
| Machine temp path | `/var/folders/<xx>/...`, the agent scratch folder carrying the real uid | `tempfile.mkdtemp()`, `mktemp -d` |

## Where identity is allowed

Authorship is public by design. The owner's name, forge handle and public contact address may appear in:

- `LICENSE`, `COPYING`, `NOTICE`, `AUTHORS`, `CITATION.cff`, `CODEOWNERS`, `FUNDING.yml`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- copyright and SPDX header lines
- package author, maintainer and owner fields
- forge URLs and repository slugs, such as `github.com/<handle>/<repo>`, `<handle>/tap`, `@<handle>` mentions and the forge `noreply` address

Machine kinds, meaning paths, hosts, folders, windows, session ids and temp paths, are never allowed, not even on an authorship line.

## How leaks happen

| Path | Example | Prevention |
|---|---|---|
| Fixture copied from real data | a restore test built from the live tmux layout carries its window names and project folders | rename every value before writing the fixture |
| Generated report committed | an analysis JSON stores the absolute path of each input | write paths relative to the repository root |
| Help output pasted into a README | a default printed as its expansion on the author's machine | show the expression, `$HOME/Docker` |
| Demo recording | a terminal recording types the author's handle | use `octocat` |
| Agent notes in `AGENTS.md` | a note naming the folder the author keeps the checkout in | state the generic condition, such as a checkout inside a file-sync folder |
| Commit or pull request text | an Evidence section pasting a path from the author's machine | replace the prefix with `$HOME` or the repository-relative path |

## Enforcement

[`hooks/machine-leak-guard.py`](../hooks/machine-leak-guard.py) runs before every `git commit` and every `gh` call that publishes text. It discovers the identifiers from the running machine at check time, so the guard itself carries no personal value:

- home path and its dashed slug, login name, host names
- the account's full name and the git `user.name`, with dictionary words dropped
- every `user.email` in the global git config and its conditional includes, except forge `noreply` addresses
- folder names between the home directory and the repository, plus the sibling folders of those ancestors, stopping at the first ancestor that is itself a repository
- tmux session and window names, live agent session ids, the agent scratch folder and the macOS temp root

It scans only lines the commit adds, the commit message, files named by a `git add` in the same command, and `gh` titles, bodies, notes and API fields. A command it cannot parse is scanned whole.

Generic names are skipped: words shorter than three letters, words in the system dictionary and their plurals, common folder words such as `work` or `projects`, file-sync product names, and names of commands on `PATH`.

Machine-local tuning lives in `machine-identifiers.txt` inside the Claude config directory, which is never committed. Copy [`machine-identifiers.example.txt`](../machine-identifiers.example.txt) to start:

```text
# one extra identifier per line
OldEmployerName
# a leading ! exempts a public name that matches a local folder
!Some Product
```

## Auditing existing repositories

[`tools/machine-leak-scan.py`](../tools/machine-leak-scan.py) runs the same matcher over every tracked line of each repository given, and exits 1 when it finds anything:

```bash
python3 tools/machine-leak-scan.py path/to/repo another/repo
```

A leak already in history stays there after the fix. Rewriting published history needs a force push, which is never done; treat what was published as disclosed.
