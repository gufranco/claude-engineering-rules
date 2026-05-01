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
    path = data.get('tool_input', data.get('input', {})).get('file_path', '')
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

# Block .env files. Whitelist documentation forms first, then block any
# remaining .env* file by suffix match. Suffix matching catches .env.shared,
# .env.team, .env.docker.local, .env.production.local, etc.
case "${BASENAME}" in
    .env.example|.env.template|.env.sample|.env.defaults)
        exit 0
        ;;
    .env|.env.*)
        echo "BLOCKED: Cannot modify ${BASENAME}. Environment files may contain secrets."
        echo "  File: ${FILE_PATH}"
        echo ""
        echo "  If you need to document a new env var, update .env.example instead."
        exit 2
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
    *.pem|*.key|id_rsa|id_ed25519|id_ecdsa|id_dsa)
        echo "BLOCKED: Cannot modify private key files."
        echo "  File: ${FILE_PATH}"
        exit 2
        ;;
    *) ;;
esac

# Block cloud and tool credential files
case "${BASENAME}" in
    credentials|config.json)
        case "${FILE_PATH}" in
            */.aws/credentials|*/.docker/config.json)
                echo "BLOCKED: Cannot modify cloud/tool credential files."
                echo "  File: ${FILE_PATH}"
                exit 2
                ;;
        esac
        ;;
    .npmrc|.pypirc|.netrc|.pgpass|.mysql_history)
        echo "BLOCKED: Cannot modify credential/auth config files."
        echo "  File: ${FILE_PATH}"
        exit 2
        ;;
    *) ;;
esac

# Block Kubernetes config
case "${FILE_PATH}" in
    */.kube/config)
        echo "BLOCKED: Cannot modify Kubernetes config (contains cluster credentials)."
        echo "  File: ${FILE_PATH}"
        exit 2
        ;;
    *) ;;
esac

# Block Terraform state and variable files with secrets
case "${BASENAME}" in
    *.tfstate|*.tfstate.backup)
        echo "BLOCKED: Cannot modify Terraform state files (contain infrastructure secrets)."
        echo "  File: ${FILE_PATH}"
        exit 2
        ;;
    *.tfvars|*.tfvars.json)
        echo "BLOCKED: Cannot modify Terraform variable files (may contain secrets)."
        echo "  File: ${FILE_PATH}"
        echo ""
        echo "  Use terraform.tfvars.example for documentation instead."
        exit 2
        ;;
    *) ;;
esac

# Block GCP and generic credential JSON files
case "${BASENAME}" in
    *-credentials.json|*_credentials.json|service-account*.json)
        echo "BLOCKED: Cannot modify credential JSON files."
        echo "  File: ${FILE_PATH}"
        exit 2
        ;;
    *) ;;
esac

# Block SSH and GPG directories
case "${FILE_PATH}" in
    */.ssh/*|*/.gnupg/*)
        echo "BLOCKED: Cannot modify SSH/GPG configuration and keys."
        echo "  File: ${FILE_PATH}"
        exit 2
        ;;
    *) ;;
esac

exit 0
