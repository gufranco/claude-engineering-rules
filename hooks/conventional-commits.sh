#!/usr/bin/env bash
# Validate that git commit messages follow conventional commit format.
#
# Intercepts Bash tool calls that run git commit. Extracts the commit
# message and validates it against the conventional commit pattern.
#
# Receives Bash tool input as JSON on stdin.
# Exit 0 = allow, exit 2 = block.

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "${INPUT}" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('input', {}).get('command', ''))
except:
    pass
" 2>/dev/null)

# Only check git commit commands
if ! echo "${COMMAND}" | grep -qE '\bgit\s+commit\b'; then
    exit 0
fi

# Skip amend, merge, and squash commits (they reuse existing messages)
if echo "${COMMAND}" | grep -qE '\-\-amend|\-\-no-edit|\-\-squash'; then
    exit 0
fi

# Extract message from -m flag (handles both 'single' and "double" quotes)
MESSAGE=$(echo "${COMMAND}" | python3 -c "
import re, sys
cmd = sys.stdin.read()
# Match heredoc format: cat <<'DELIM' or cat <<DELIM
# Closing delimiter must appear at the start of a line (bash rule), preventing
# a word like EOF inside the body from being mistaken for the closing delimiter.
heredoc = re.search(r\"cat <<'?(\w+)'?\\n(.+?)\\n^\\1\\s*$\", cmd, re.DOTALL | re.MULTILINE)
if heredoc:
    print(heredoc.group(2).strip())
    sys.exit(0)
# Match -m with quotes
m_flag = re.search(r'-m\s+[\x22\x27](.+?)[\x22\x27]', cmd)
if m_flag:
    print(m_flag.group(1).strip())
    sys.exit(0)
# Match -m with \$() substitution containing heredoc
m_sub = re.search(r'-m\s+\"\\\$\\(cat <<', cmd)
if m_sub:
    content = re.search(r\"cat <<'?(\w+)'?\\n(.+?)\\n\\s*\\1\", cmd, re.DOTALL)
    if content:
        print(content.group(2).strip())
        sys.exit(0)
" 2>/dev/null)

# If we couldn't extract a message, allow (might be interactive or --allow-empty-message)
if [[ -z "${MESSAGE}" ]]; then
    exit 0
fi

# Get the first line (subject)
SUBJECT=$(echo "${MESSAGE}" | head -1)

# Validate conventional commit format
PATTERN='^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)(\(.+\))?(!)?: .+'
if ! echo "${SUBJECT}" | grep -qE "${PATTERN}"; then
    echo "BLOCKED: Commit message does not follow conventional commit format."
    echo ""
    echo "  Got: ${SUBJECT}"
    echo ""
    echo "  Expected: <type>(<scope>): <subject>"
    echo "  Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert"
    echo "  Example: feat(auth): add SSO login with Google provider"
    exit 2
fi

# Validate subject length (max 50 chars for subject line, per git-workflow rule)
SUBJECT_LENGTH=${#SUBJECT}
if [[ "${SUBJECT_LENGTH}" -gt 50 ]]; then
    echo "BLOCKED: Commit subject line is ${SUBJECT_LENGTH} characters (max 50)."
    echo ""
    echo "  Got: ${SUBJECT}"
    echo ""
    echo "  Keep the subject concise. Use the body for details."
    exit 2
fi

# Validate decision trailers format (optional, but must be correct when present)
TRAILER_PATTERN='^(Rejected|Constraint|Risk): .+'
REJECTED_PATTERN='^Rejected: .+ \| .+'

while IFS= read -r trailer_line; do
    [[ -z "${trailer_line}" ]] && continue

    # Check if line looks like a trailer (Key: value)
    if echo "${trailer_line}" | grep -qE '^(Rejected|Constraint|Risk):'; then
        # Validate general trailer format
        if ! echo "${trailer_line}" | grep -qE "${TRAILER_PATTERN}"; then
            echo "BLOCKED: Malformed decision trailer."
            echo ""
            echo "  Got: ${trailer_line}"
            echo ""
            echo "  Expected: <Trailer>: <description>"
            exit 2
        fi

        # Validate Rejected trailer has pipe separator
        if echo "${trailer_line}" | grep -qE '^Rejected:'; then
            if ! echo "${trailer_line}" | grep -qE "${REJECTED_PATTERN}"; then
                echo "BLOCKED: Rejected trailer must include reason after pipe."
                echo ""
                echo "  Got: ${trailer_line}"
                echo ""
                echo "  Expected: Rejected: <alternative> | <reason>"
                exit 2
            fi
        fi
    fi
done <<< "${MESSAGE}"

exit 0
