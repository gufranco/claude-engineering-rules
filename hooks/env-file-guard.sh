#!/usr/bin/env bash
# env-file-guard.sh — Block Write/Edit operations on environment files.
#
# PreToolUse hook for Write, Edit, and MultiEdit.
# Prevents Claude from modifying .env files that may contain secrets.
# Complements the deny rules in settings.json with runtime enforcement.
#
# Receives tool input as JSON on stdin.
# Exit 0 = allow, exit 2 = block.

INPUT=$(cat)

PARSED=$(echo "${INPUT}" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    tool = data.get('tool_name', '')
    path = data.get('input', {}).get('file_path', '')
    print(f'{tool}\n{path}')
except Exception:
    pass
" 2>/dev/null)

TOOL=$(echo "${PARSED}" | head -1)
FILE_PATH=$(echo "${PARSED}" | tail -1)

# Only check Write, Edit, and MultiEdit
case "${TOOL}" in
    Write|Edit|MultiEdit) ;;
    *) exit 0 ;;
esac

[[ -z "${FILE_PATH}" ]] && exit 0

BASENAME=$(basename "${FILE_PATH}")

# Block .env files (except .env.example and .env.template)
case "${BASENAME}" in
    .env|.env.local|.env.production|.env.staging|.env.development|.env.testing|.env.ci|.env.docker)
        echo "BLOCKED: Cannot modify ${BASENAME}. Environment files may contain secrets."
        echo "  File: ${FILE_PATH}"
        echo ""
        echo "  If you need to document a new env var, update .env.example instead."
        exit 2
        ;;
    .env.example|.env.template|.env.sample|.env.defaults)
        exit 0
        ;;
    *) ;;
esac

# Block files in secrets directories
case "${FILE_PATH}" in
    */secrets/*|*/credentials/*)
        echo "BLOCKED: Cannot modify files in secrets directory."
        echo "  File: ${FILE_PATH}"
        exit 2
        ;;
    *) ;;
esac

# Block private key files
case "${BASENAME}" in
    *.pem|*.key|id_rsa|id_ed25519|id_ecdsa)
        echo "BLOCKED: Cannot modify private key files."
        echo "  File: ${FILE_PATH}"
        exit 2
        ;;
    *) ;;
esac

exit 0
