"""Single source of truth for mutation-method-blocker version.

Plan item A6. Imported by hooks/mutation-method-blocker.py, hooks/sarif_emitter.py,
and hooks/lsp_emitter.py so the user-facing version string is set in exactly one place.
"""

from __future__ import annotations

VERSION: str = "3.0.0-dev"
"""Semantic version of the mutation-method-blocker hook.

Bump on every user-visible behavior change. The `-dev` suffix marks pre-release
work and is dropped at GA. Released versions follow MAJOR.MINOR.PATCH.
"""

SARIF_SCHEMA_VERSION: str = "2.1.0"
"""SARIF schema version emitted by hooks/sarif_emitter.py."""

LSP_SCHEMA_VERSION: str = "3.17"
"""LSP specification version emitted by hooks/lsp_emitter.py."""

__all__ = ["LSP_SCHEMA_VERSION", "SARIF_SCHEMA_VERSION", "VERSION"]
