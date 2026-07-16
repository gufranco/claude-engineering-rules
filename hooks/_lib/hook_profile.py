"""Hook profile gating.

Every hook in ~/.claude/hooks/ should import `should_run` and short-circuit
at the top of `main()`:

    from _lib.hook_profile import should_run
    if not should_run("dangerous-command-blocker"):
        sys.exit(0)

The profile is read from `CLAUDE_HOOK_PROFILE` (default `standard`).
Profiles are additive supersets:

  - minimal:  always-on safety hooks only
  - standard: minimal + quality hooks (formatters, linters, banned phrases)
  - strict:   standard + experimental hooks (gateguard-fact-force, mcp-health-check)

Per-ID disable via `CLAUDE_DISABLED_HOOKS=<csv>` overrides the profile.
Per-ID enable via `CLAUDE_ENABLED_HOOKS=<csv>` also overrides.

The hook ID matches the filename without extension by default. Hooks can
pass an explicit ID when their filename does not match.
"""

from __future__ import annotations

import os

# Always-on safety floor.
MINIMAL_HOOKS = frozenset(
    {
        "dangerous-command-blocker",
        "env-file-guard",
        "secret-scanner",
        "git-author-guard",
        "aws-profile-guard",
        "gcloud-config-guard",
        "kubectl-context-guard",
        "docker-context-guard",
        "terraform-workspace-guard",
        "mise-global-guard",
        "settings-hygiene",
        "internal-config-leakage",
        "ai-attribution-blocker",
        "ai-process-leak-blocker",
        "large-file-blocker",
        "english-only-reminder",
        "config-protection",
    }
)

# Standard = minimal + quality and discipline hooks.
STANDARD_HOOKS = MINIMAL_HOOKS | frozenset(
    {
        "banned-phrases-blocker",
        "banned-prose-chars",
        "normative-keyword-discipline",
        "console-log-blocker",
        "as-any-blocker",
        "mock-internal-blocker",
        "todo-marker-blocker",
        "found-fix-rationalization-blocker",
        "mutation-method-blocker",
        "redis-atomicity",
        "drizzle-raw-sql-blocker",
        "drizzle-schema-sync",
        "prisma-raw-sql-blocker",
        "prisma-schema-sync",
        "sequelize-raw-sql-blocker",
        "sequelize-schema-sync",
        "typeorm-raw-sql-blocker",
        "typeorm-schema-sync",
        "migration-idempotency",
        "dockerfile-compose-quality",
        "markdown-link-discipline",
        "conventional-commits",
        "smart-formatter",
        "edit-accumulator",
        "stop-format-typecheck",
        "compact-context-saver",
        "notify-webhook",
        "bulk-resolve-blocker",
        "force-push-during-review",
        "gh-token-guard",
        "glab-token-guard",
        "retro-pointer",
        "review-state-guard",
        "rtk-rewrite",
        "subagent-brief-quality",
        "mcp-health-check",
    }
)

# Strict = standard + experimental hooks.
STRICT_HOOKS = STANDARD_HOOKS | frozenset(
    {
        "gateguard-fact-force",
    }
)

PROFILES = {
    "minimal": MINIMAL_HOOKS,
    "standard": STANDARD_HOOKS,
    "strict": STRICT_HOOKS,
}


def _csv_set(env_var: str) -> frozenset[str]:
    value = os.environ.get(env_var, "")
    if not value:
        return frozenset()
    return frozenset(token.strip() for token in value.split(",") if token.strip())


def should_run(hook_id: str) -> bool:
    """Return True when this hook should execute under the current profile."""
    profile = os.environ.get("CLAUDE_HOOK_PROFILE", "standard").lower()
    if profile not in PROFILES:
        # Unknown profile: fail open to avoid bricking the user's harness.
        # The settings-hygiene hook will catch an invalid profile setting on
        # the next settings.json edit.
        return True

    enabled = _csv_set("CLAUDE_ENABLED_HOOKS")
    disabled = _csv_set("CLAUDE_DISABLED_HOOKS")

    if hook_id in disabled:
        return False
    if hook_id in enabled:
        return True
    return hook_id in PROFILES[profile]
