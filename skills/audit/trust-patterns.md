# Trust Patterns

Indicators of compromise catalog for untrusted-project safety scans. Consumed by `/audit trust` and `/onboard` Phase 0.

## How to use this file

The catalog is append-only. Patterns are not removed, only deprecated with a date stamp on the right-hand column. New IOCs land at the top of their section so the most recent threats are visible first.

Each section uses one table format:

| Pattern | Severity | Target | Rationale | Known false positives |

- **Pattern**: the literal regex, string, or shape to match.
- **Severity**: CRITICAL, HIGH, MEDIUM, LOW. Defined below.
- **Target**: the file glob or path the scanner walks for this pattern.
- **Rationale**: one-line why this is a signal.
- **Known false positives**: packages or contexts where this pattern is benign. The scanner suppresses the finding when both the pattern and the false-positive marker match.

Severity scale:

| Level | Definition | Example |
|-------|------------|---------|
| CRITICAL | Definitive IOC. Match on sight forces MALICIOUS verdict | Hard-coded Discord webhook URL, known-malicious package name |
| HIGH | Strong signal alone, or part of a likely-malicious cluster | `eval` of base64-decoded input, postinstall running `curl ... | bash` |
| MEDIUM | Suspicious but possibly legitimate. Two or more in the same file escalate to HIGH | Single `eval`, single non-default registry override |
| LOW | Noise floor. Recorded for transparency, does not affect verdict | Single `child_process` import in a config file |

Cluster rule: when two or more MEDIUM signals fire in the same file, the file escalates to HIGH. When two or more HIGH signals fire in the same file, the file escalates to CRITICAL. The verdict logic in `/audit trust` step 13 reads the per-file aggregate, not the raw line matches.

## Section A: Install-time hooks

Lifecycle scripts and install configs that run automatically before any application code is imported. Highest-priority targets because they run on first `npm install` / `pip install` / equivalent.

| Pattern | Severity | Target | Rationale | Known false positives |
|---------|----------|--------|-----------|----------------------|
| Lifecycle field (`preinstall`, `install`, `postinstall`, `prepare`, `prepublish`, `prepublishOnly`) value containing `curl`, `wget`, `\| bash`, `\| sh`, `node -e`, `python -c`, `base64 -d`, `xxd -r` | CRITICAL | `package.json` scripts block | These are the install-time RCE primitives | None. Legitimate packages do not pipe network downloads to a shell |
| Lifecycle field value running a script file the package itself ships, where that script invokes `eval`, `Function`, or `child_process` with dynamic input | HIGH | `package.json` scripts + the referenced script | Indirect form of the above | esbuild downloads its binary via `install` script; verify the destination domain is `esbuild.dev` or the official mirror |
| Lifecycle field with a network call to a domain not listed in the project README | HIGH | `package.json` scripts | Out-of-band binary download | bcrypt, sharp, sqlite3, canvas, node-sass, prebuild-install, esbuild |
| `.npmrc` containing `registry=` set to anything other than `https://registry.npmjs.org/` or a documented company registry | HIGH | `.npmrc` (project + user) | Dependency confusion or malicious mirror | Company internal registries |
| `.npmrc` containing `unsafe-perm=true` | MEDIUM | `.npmrc` | Removes the safety net that drops privileges during lifecycle scripts | Native build packages occasionally need this on Linux |
| `.npmrc` containing `ignore-scripts=false` as an explicit override (when project policy expects `true`) | HIGH | `.npmrc` | Deliberate re-enable of dangerous default | None |
| `.yarnrc.yml` containing `unsafePackagePatterns`, `enableScripts: true` overrides, or untrusted `plugins:` entries with URLs | HIGH | `.yarnrc.yml` | Yarn analog of the npm patterns above | Documented in-repo plugin |
| Setup hook in `pyproject.toml` `[tool.setuptools]` or `setup.py` `cmdclass` that imports `urllib`, `requests`, `subprocess`, or `socket` | HIGH | `pyproject.toml`, `setup.py`, `setup.cfg` | Python equivalent of postinstall payload | Project-specific build helpers documented in README |
| `setup.py` containing `os.system`, `subprocess.call`, `subprocess.run` with a string argument | HIGH | `setup.py` | Python install-time code execution | Native build steps |
| `.husky/`, `.git/hooks/`, `lefthook.yml`, `.pre-commit-config.yaml` with a hook that performs a network call or runs `eval`/`base64 -d` | HIGH | `.husky/*`, `.git/hooks/*`, `lefthook.yml`, `.pre-commit-config.yaml` | Triggers on git operations the user does without thinking | Project-specific lint hooks; verify the hook content |
| Cargo `build.rs` performing a network download or running `Command::new("curl")` | HIGH | `build.rs` | Rust install-time RCE primitive | Some legitimate crates download platform binaries; verify origin |
| Composer `scripts` field `post-install-cmd`, `post-update-cmd` running shell with dynamic input | HIGH | `composer.json` | PHP equivalent | Framework artifact generation |
| Bundler `Gemfile` containing `eval` or `system` calls | HIGH | `Gemfile`, `*.gemspec` | Ruby equivalent | None |
| Go `init()` function in a vendored dependency performing network calls | MEDIUM | Vendored Go files | Go does not have install scripts but `init()` runs on import | None definitive without context |

## Section B: Code-level red flags

Patterns inside source code itself. Match alone is rarely a verdict, but clustering with Section C or D matches escalates fast.

| Pattern | Severity | Target | Rationale | Known false positives |
|---------|----------|--------|-----------|----------------------|
| `eval(` immediately following a base64 decode (`atob(`, `Buffer.from(<arg>, 'base64').toString()`, `base64.b64decode`) | CRITICAL | All source files | The canonical malicious-package payload pattern | None. Real code does not eval base64 strings |
| `new Function(` or `Function(...)()`  with a base64 decode result as argument | CRITICAL | All source files | Same as above, alternate syntax | None |
| `eval(` with any dynamic argument | HIGH | All source files | Even without base64, dynamic eval is a flag | Some templating engines, REPL utilities |
| `new Function(`, `Function(`, or `vm.runInNewContext` with dynamic input | HIGH | All source files | Dynamic code construction | Templating engines, plugin loaders |
| `String.fromCharCode(...)` with eight or more comma-separated integer arguments | HIGH | All source files | Common obfuscator output | Unicode test fixtures, internationalization libraries |
| `\x[0-9a-f]{2}` hex escape sequences accounting for 30% or more of a string literal | HIGH | All source files | Obfuscated identifier or payload | Binary protocol parsers; legitimate when paired with documented constants |
| Variable names matching `_0x[a-f0-9]{4,}` | HIGH | All source files | Default obfuscator naming | Minified bundles in `dist/`; scanner skips build output dirs |
| Variable names matching `[a-zA-Z]{16,}` with no vowels or pronounceable structure | MEDIUM | All source files | Obfuscator output less common pattern | Some hash constants |
| String literal of 100+ chars with Shannon entropy above 4.5 and no hex/base64-like structure | MEDIUM | All source files | High-entropy payload | UUIDs, JWT examples, test fixtures |
| String concatenation hiding shell keywords: `"po" + "wer" + "shell"`, `"chi" + "ld_pr" + "ocess"`, `"e" + "val"`, `"fro" + "mCharCode"`, `"req" + "uire"` | HIGH | All source files | Evasion of grep-based scanners | Test fixtures for those exact scanners |
| `child_process.exec`, `child_process.execSync`, `child_process.spawn`, `child_process.spawnSync` with a dynamic string argument | HIGH | All source files | Command injection primitive | CLI utilities; verify the input is sanitized |
| `subprocess.Popen`, `subprocess.run`, `os.system`, `os.popen` with a dynamic string argument | HIGH | Python files | Command injection primitive | CLI utilities |
| `require('child_process')`, `import child_process`, `from subprocess import` at the top of a file named `config.js`, `setup.js`, `init.js`, or a `*.json` JSON-import wrapper | HIGH | Source files matching the file-name patterns | Process spawning from a config-looking file | Build scripts named that way; manually verify |
| `process.env` access concatenated into a URL or POST body | HIGH | All source files | Environment exfiltration | Telemetry libraries; verify the destination domain |
| `Object.keys(process.env)`, `dict(os.environ)` followed by a network call within 50 lines | HIGH | All source files | Bulk env extraction | Logging libraries that redact secrets; verify redaction |
| Reflective module access: `require(decoded)`, `__import__(decoded)`, `eval("require")` | CRITICAL | All source files | Hides which module is loaded | None |
| `Buffer.from(<long-hex>, 'hex')` followed by `eval` or `Function` | CRITICAL | All source files | Hex-encoded payload variant | None |
| `WebAssembly.instantiate` with a base64-decoded buffer where the source has no other WASM-related code | MEDIUM | All source files | WASM payload smuggling | Genuine WASM projects |

## Section C: Sensitive file access

References to filesystem paths that contain credentials. Match in production code is a signal even without a clear network call, because it indicates the package is interested in those paths.

| Pattern | Severity | Target | Rationale | Known false positives |
|---------|----------|--------|-----------|----------------------|
| Read of `~/.ssh/`, `~/.ssh/id_rsa`, `~/.ssh/id_ed25519`, `~/.ssh/known_hosts` | HIGH | All source files | SSH key theft | SSH client libraries with documented use; backup tools |
| Read of `~/.aws/credentials`, `~/.aws/config` | HIGH | All source files | AWS credential theft | AWS SDK plugins that re-read the credentials file are flagged but legitimate |
| Read of `~/.gnupg/`, `~/.gnupg/private-keys-v1.d` | HIGH | All source files | GPG key theft | gpg wrapper libraries |
| Read of `~/.docker/config.json` | HIGH | All source files | Docker registry credential theft | Docker SDKs |
| Read of `~/.kube/config` | HIGH | All source files | Kubernetes credential theft | k8s client libraries |
| Read of `~/.npmrc`, `~/.yarnrc` from a non-npm-tool package | HIGH | All source files | npm auth token theft | npm CLI tools |
| Read of `~/.gitconfig`, `~/.git-credentials` | HIGH | All source files | Git credential theft | git wrapper libraries |
| Read of `~/.config/gh/hosts.yml`, `~/.config/glab-cli/config.yml` | HIGH | All source files | GitHub/GitLab CLI token theft | gh/glab wrapper libraries |
| Read of `~/.cargo/credentials`, `~/.cargo/credentials.toml` | HIGH | All source files | crates.io token theft | cargo tooling |
| Read of `~/.pypirc` | HIGH | Python files | PyPI token theft | Publishing tools |
| Read of OS keyring paths: `~/.local/share/keyrings/`, `/run/user/*/keyring`, macOS `Keychain`, Windows `CredentialManager` | HIGH | All source files | Credential store theft | Password manager integrations |
| Read of browser cookie databases: `Library/Application Support/Google/Chrome/`, `Library/Application Support/Firefox/`, Windows `AppData\Local\Google\Chrome`, Linux `~/.config/google-chrome` | CRITICAL | All source files | Browser cookie theft | Browser automation libraries (puppeteer, playwright) declared as direct dependencies |
| Read of `wallet.dat`, `keystore`, `*.wallet`, `Electrum/wallets/` | CRITICAL | All source files | Cryptocurrency wallet theft | Crypto wallet libraries declared as direct dependencies |
| Write to `~/.bashrc`, `~/.zshrc`, `~/.profile`, `~/.bash_profile`, `~/.config/fish/config.fish` | HIGH | All source files | Persistence via shell rc | Dotfile managers |
| Write to `~/.config/autostart/`, `~/Library/LaunchAgents/`, `~/AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup` | HIGH | All source files | Persistence via autostart | None for typical libraries |
| Write to `/etc/`, `/usr/local/bin/`, `/usr/bin/`, `/System/` | CRITICAL | All source files | System-level persistence | Installer scripts that the project documents |
| PATH modification: `process.env.PATH = ...`, `os.environ["PATH"] = ...`, `setx PATH` | HIGH | All source files | Persistence and supply-chain pivot | Build wrappers |

## Section D: Network exfiltration endpoints

Hard-coded destinations associated with stolen-data drop sites. Distinct from generic API clients because legitimate packages do not POST data to Discord webhooks.

| Pattern | Severity | Target | Rationale | Known false positives |
|---------|----------|--------|-----------|----------------------|
| URL matching `discord(app)?.com/api/webhooks/\d+/` | CRITICAL | All source files | Discord webhook exfiltration channel | Test fixtures for webhook libraries; documented chat integrations |
| URL matching `hooks.slack.com/services/` | HIGH | All source files | Slack webhook exfiltration channel | Documented Slack integrations |
| URL matching `t\.me/`, `api\.telegram\.org/bot[0-9]+:` | CRITICAL | All source files | Telegram bot exfiltration | Documented Telegram bots |
| URL matching `pastebin\.com/raw/`, `hastebin\.com/raw/`, `ghostbin\.com/`, `paste\.ee/r/`, `dpaste\.com/` | HIGH | All source files | Anonymous paste sites for secondary payload hosting | Test fixtures |
| URL matching `raw\.githubusercontent\.com/[^/]+/[^/]+/[0-9a-f]{40}/` to a domain other than the project's own org | MEDIUM | All source files | Pinned raw payload from an unknown repo | Documented fixture downloads |
| URL matching shortener domains: `bit\.ly/`, `tinyurl\.com/`, `is\.gd/`, `t\.co/`, `goo\.gl/`, `ow\.ly/`, `tiny\.cc/` | HIGH | All source files | URL shorteners obfuscate destination | Documentation links |
| URL matching DDNS providers: `\.duckdns\.org`, `\.no-ip\.com`, `\.ddns\.net`, `\.dynu\.com`, `\.hopto\.org` | HIGH | All source files | Dynamic-DNS endpoints used by C2 | None typical |
| Hard-coded IPv4 outside private ranges in a string literal followed by HTTP/HTTPS or socket connect | HIGH | All source files | Direct IP exfiltration | Internal services use private CIDRs |
| Hard-coded IPv6 outside the `fe80::/10` link-local and `fc00::/7` ULA ranges | MEDIUM | All source files | Same as above for IPv6 | None typical |
| `fetch(`, `axios.post(`, `requests.post(`, `urllib.request.urlopen(` with an interpolated `process.env` or `os.environ` value in the body | HIGH | All source files | Environment exfiltration | Telemetry; verify the destination is documented |
| File upload to an anonymous storage endpoint: `transfer\.sh/`, `file\.io/`, `0x0\.st/`, `tmpfiles\.org/`, `bashupload\.com/` | HIGH | All source files | Anonymous file drops | Documented temporary-share integrations |
| GitHub API call creating a new repo with `private: false` from a package that has no documented GitHub integration | CRITICAL | All source files | Shai-Hulud signature: malware creates a public repo to dump credentials | gh wrapper libraries with documented use |
| HTTP `User-Agent` set to a hard-coded value that resembles a browser when the package is a backend library | MEDIUM | All source files | Evasion of bot detection | Scraping libraries that document this |

## Section E: CI/CD attack patterns

Workflow and pipeline files. Match patterns associated with documented supply-chain CVEs.

| Pattern | Severity | Target | Rationale | Known false positives |
|---------|----------|--------|-----------|----------------------|
| Workflow trigger `pull_request_target` combined with a `actions/checkout` step that checks out the PR ref (`github.event.pull_request.head.sha`, `${{ github.head_ref }}`) | CRITICAL | `.github/workflows/*.yml` | The "Pwn Request" pattern. Runs PR-supplied code with write permissions | Workflows that explicitly checkout the base ref and only read PR metadata |
| `actions/checkout`, `actions/setup-*`, or any third-party action pinned to a branch (`@main`, `@master`) or a moving tag (`@v4`) in a workflow that uses secrets | HIGH | `.github/workflows/*.yml` | Tag-pointer hijack risk. Pin to full commit SHA | Workflows that never use secrets |
| `actions/checkout` or third-party action pinned to a tag without a corresponding SHA comment | MEDIUM | `.github/workflows/*.yml` | Same as above, weaker signal | None |
| `run:` step that pipes `$GITHUB_TOKEN`, `secrets.*`, or `env.*` to `curl`, `wget`, or any network tool | CRITICAL | `.github/workflows/*.yml` | Direct token exfiltration | None |
| Workflow `permissions:` block set to `write-all` or omitted entirely when secrets are used | HIGH | `.github/workflows/*.yml` | Overly broad token scope | Workflows that need write access and document why |
| Self-hosted runner reference on a public repository | HIGH | `.github/workflows/*.yml` | Hostile PRs run on your hardware | Private forks |
| `.gitlab-ci.yml` `script:` block fetching a remote payload (`curl`, `wget`) and piping to `bash`/`sh` | CRITICAL | `.gitlab-ci.yml` | GitLab equivalent of postinstall RCE | None |
| `.gitlab-ci.yml` `image:` field referring to a non-pinned tag with secrets in the job | HIGH | `.gitlab-ci.yml` | Image-tag hijack | None |
| `.circleci/config.yml` `orbs:` entries pinned to a major version only (e.g., `circleci/aws-cli@1`) | MEDIUM | `.circleci/config.yml` | Floating orb version | Internal orbs |
| `Jenkinsfile` with `sh "..."` interpolating a `params` value without sanitization | HIGH | `Jenkinsfile` | Command injection | Parameter validation present |
| Workflow uses `${{ github.event.issue.title }}`, `${{ github.event.pull_request.title }}`, `${{ github.event.comment.body }}`, or `${{ github.head_ref }}` inside a `run:` script without quoting | CRITICAL | `.github/workflows/*.yml` | Script injection via untrusted user content | Quoted env var usage |

## Section F: Editor and tooling auto-run

IDE and shell-tooling configs that execute code automatically when the project is opened.

| Pattern | Severity | Target | Rationale | Known false positives |
|---------|----------|--------|-----------|----------------------|
| `.vscode/settings.json` containing `terminal.integrated.automationProfile.<os>` with a custom path or args | HIGH | `.vscode/settings.json` | Automation profile runs when integrated terminal opens | Documented dev-container configs |
| `.vscode/settings.json` containing `task.allowAutomaticTasks: "on"` paired with auto-run tasks | HIGH | `.vscode/settings.json` | Tasks may auto-execute on folder open | None |
| `.vscode/tasks.json` with `"runOptions": { "runOn": "folderOpen" }` | HIGH | `.vscode/tasks.json` | Explicit auto-run on open | Documented dev-container bootstraps |
| `.idea/workspace.xml` containing `<RunConfiguration ...>` with `RUN_ON_OPEN="true"` | HIGH | `.idea/workspace.xml` | JetBrains auto-run | None typical |
| `.envrc` containing `eval`, `source <(curl ...)`, or any download piped to a shell | CRITICAL | `.envrc` | direnv auto-executes on `cd`; `direnv allow` is a one-time check the user may forget | Documented direnv setups that source only local files |
| `.envrc` sourcing a file outside the project root | HIGH | `.envrc` | Cross-project leakage | Symlink farm setups |
| `.devcontainer/devcontainer.json` `postCreateCommand`, `postStartCommand`, `postAttachCommand` containing `curl`, `wget`, `eval`, `base64 -d` | HIGH | `.devcontainer/devcontainer.json` | Dev container auto-runs these on first open | Documented bootstraps |
| `Makefile` default target that runs network commands or unpacks base64 payloads | HIGH | `Makefile` | A naive `make` invocation runs the default | Documented setup targets |

## Section G: Dependency red flags

Properties of declared dependencies, evaluated against metadata available offline (lockfile) and optionally online (`npm view`, `pip show`).

| Pattern | Severity | Target | Rationale | Known false positives |
|---------|----------|--------|-----------|----------------------|
| Direct dependency name matching the known-malicious package list at the end of this file | CRITICAL | Manifest dependencies | Definitive IOC | None |
| Direct dependency name within Levenshtein distance 1 of a top-1000 package and not matching any known scope | HIGH | Manifest dependencies | Typosquat | Internal-scoped packages with intentional similar names |
| Direct dependency published less than 7 days ago | HIGH | Manifest dependencies + `npm view` data | Most malicious packages are caught and removed within days; fresh packages are higher risk | Patched stable libraries during a security release window |
| Direct dependency published less than 30 days ago | MEDIUM | Manifest dependencies + `npm view` data | Same signal weaker | New libraries with no prior releases |
| Direct dependency with fewer than 100 weekly downloads relative to a stated download count over 10000 | HIGH | `npm view` data | Sudden drop or fresh malicious package | Internal packages |
| Direct dependency where the package manifest's `repository.url` returns 404, points to a deleted repo, or contains no commits | HIGH | `npm view` data | Backing source code missing | Private libraries |
| Direct dependency where the maintainer changed in the last 30 days and the new maintainer has no prior package history | HIGH | `npm view` data | Account takeover signal | New maintainers with verifiable identity |
| Direct dependency with a single maintainer and no organization scope | MEDIUM | `npm view` data | Single-point-of-failure for compromise | Many legitimate small packages fit this |
| Lockfile resolves a direct dependency to a different version than the manifest range | HIGH | Lockfile vs manifest | Possible lockfile tampering | Intentional version pinning via lockfile |
| Lockfile resolves any package to a non-default registry without a documented company registry config | CRITICAL | Lockfile | Dependency confusion attack | Documented private registry |
| Lockfile has no integrity hash (`integrity:` field empty or missing) for a package | HIGH | Lockfile | Lockfile cannot verify package content | Local-path or git-protocol dependencies |
| Package `bin` field that registers a binary with a name matching a system command (`ls`, `cd`, `git`, `npm`, `node`, `python`) | HIGH | Direct dependency `package.json` | PATH hijack | None |
| Package `engines` field claiming compatibility with EOL Node.js, Python, or other runtime versions | LOW | Manifest engines | Quality signal, possible compatibility issues | Legacy projects |

## Section H: Binary anomalies

Compiled artifacts in places that suggest they were added as payloads, not as build output.

| Pattern | Severity | Target | Rationale | Known false positives |
|---------|----------|--------|-----------|----------------------|
| Executable file (`+x` bit) in [`scripts/`](../../scripts), `bin`, `tools` without a corresponding source file in the same repo | HIGH | All files | Pre-compiled payload | Vendored tools documented in README |
| ELF, Mach-O, PE binary in a directory other than `dist`, `build`, `target`, `out`, `bin` | HIGH | All files | Foreign binary | Documented vendor binaries |
| Compressed archive (`.tar.gz`, `.zip`, `.7z`) committed to the repo with no extraction step in a build script | MEDIUM | All files | Hidden payload | Test fixtures |
| Shell script in a non-[`scripts/`](../../scripts), non-`.husky` directory | MEDIUM | All files | Unexpected location | Project conventions |
| Single-file installer (`*.sh`, `*.bat`, `*.ps1`) committed to a JavaScript or Python project | HIGH | All files | Cross-platform payload | Documented installers |
| WASM binary (`*.wasm`) committed without a corresponding `.wat` text source or a build script | MEDIUM | All files | Pre-compiled WASM payload | Documented WASM dependencies |

## Verdict Logic

1. Per-file aggregate: sum severities. Two MEDIUM in the same file equal one HIGH. Two HIGH in the same file equal one CRITICAL.
2. Project aggregate:
   - Any CRITICAL anywhere: **MALICIOUS**.
   - Any HIGH anywhere: **HIGH-RISK**.
   - Any MEDIUM anywhere: **SUSPICIOUS**.
   - Only LOW or no findings: **SAFE**.

The `/audit trust` skill prints the verdict and the worst three findings inline, then the full per-file table.

## Known-Malicious Package List (curated, append-only)

This list seeds the typosquat and definitive-IOC checks. Update as new attacks publish. Entries deprecate but are not removed; dates show when the entry was added.

| Package name | Ecosystem | Added | Notes |
|--------------|-----------|-------|-------|
| `@bitwarden/cli` versions 2026.4.0 | npm | 2026-05 | Mini Shai-Hulud impersonation, TeamPCP campaign |
| `plain-crypto-js` versions 4.2.1 | npm | 2026-03 | Axios compromise injected dependency, North Korean APT |
| Axios versions 1.14.1, 0.30.4 | npm | 2026-03 | Compromised maintainer release window 2026-03-31 |
| `durabletask` versions 1.4.1, 1.4.2, 1.4.3 | PyPI | 2026-05 | Microsoft package compromise, Linux wiper plus cloud credential stealer |
| `pytorch-lightning` and `lightning` versions 2.6.2, 2.6.3 | PyPI | 2026-04 | Bun runtime credential stealer |
| `@tanstack/*` published 2026-05-11 19:20-19:26 UTC, 84 versions | npm | 2026-05 | OIDC token extraction via GitHub Actions cache poisoning |
| Shai-Hulud sample list (571 packages, Sep 2025) | npm | 2025-09 | Reference: Sysdig and Unit 42 reports. Listed in references file |
| Mini Shai-Hulud sample list (169 packages, May 2026) | npm | 2026-05 | Reference: StepSecurity and CyberSec Guru reports |
| TrapDoor sample list (34 packages, 384 versions, May 2026) | npm, PyPI, Crates | 2026-05 | Reference: Cyber Kendra report |
| `undicy-http` | npm | 2026 | Screen-streaming RAT and browser injector |
| `mysql-dumpdiscord` and pattern variants | npm | Ongoing | Discord webhook exfiltration of `.env`, `config.json` |

The actual per-version lists are tracked in the originating advisories linked from the spec folder. This table holds the names the scanner matches against. When the user runs `/audit trust` and detects a match here, the verdict is **MALICIOUS** with no override.

## Maintenance

| Cadence | Action |
|---------|--------|
| Per attack disclosure | Add a row to the Known-Malicious Package List with the canonical advisory link |
| Quarterly | Review Section A through H against the latest threat-intelligence reports. Add new pattern rows |
| Annually | Sweep deprecated rows. Move them to an archive section at the bottom of this file, never delete |
