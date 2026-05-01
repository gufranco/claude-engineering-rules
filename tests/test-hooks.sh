#!/usr/bin/env bash
# test-hooks.sh — Smoke tests for Claude Code hooks.
#
# Feeds JSON fixtures to each hook and verifies exit codes.
# Exit 0 = all tests pass, exit 1 = at least one failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES="${SCRIPT_DIR}/fixtures"
HOOKS="${SCRIPT_DIR}/../hooks"
PASS=0
FAIL=0

run_test() {
    local description="$1"
    local hook="$2"
    local fixture="$3"
    local expected_exit="$4"

    local actual_exit=0
    "${hook}" < "${fixture}" >/dev/null 2>&1 || actual_exit=$?

    if [[ "${actual_exit}" -eq "${expected_exit}" ]]; then
        echo "  PASS: ${description} (exit ${actual_exit})"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: ${description} (expected exit ${expected_exit}, got ${actual_exit})"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "=== Dangerous Command Blocker ==="

run_test "allows safe commands" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-safe-command.json" 0

run_test "blocks rm -rf /" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-catastrophic-rm.json" 2

run_test "blocks git push --force" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-force-push.json" 2

run_test "blocks curl pipe to shell" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-pipe-to-shell.json" 2

run_test "blocks rm -rf .git" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-delete-git.json" 2

run_test "warns on git reset --hard (recoverable)" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-git-reset-hard.json" 0

run_test "blocks fork bomb" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-fork-bomb.json" 2

run_test "handles malformed JSON gracefully" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/malformed-json.txt" 0

echo ""
echo "=== Dangerous Command Blocker: Privilege Escalation ==="

run_test "blocks sudo rm -rf" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-sudo-rm.json" 2

run_test "blocks reverse shell" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-reverse-shell.json" 2

echo ""
echo "=== Dangerous Command Blocker: Cloud CLI ==="

run_test "blocks aws s3 bucket deletion" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-aws-s3-delete.json" 2

run_test "blocks aws ec2 terminate" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-aws-ec2-terminate.json" 2

run_test "blocks gcloud instance deletion" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-gcloud-delete.json" 2

run_test "blocks az resource group deletion" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-az-group-delete.json" 2

run_test "allows safe aws commands" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-safe-aws.json" 0

echo ""
echo "=== Dangerous Command Blocker: Containers and K8s ==="

run_test "blocks docker privileged mode" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-docker-privileged.json" 2

run_test "blocks kubectl delete namespace" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-kubectl-delete-ns.json" 2

run_test "blocks helm uninstall" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-helm-uninstall.json" 2

run_test "allows safe kubectl commands" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-safe-kubectl.json" 0

run_test "allows safe docker commands" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-safe-docker.json" 0

echo ""
echo "=== Dangerous Command Blocker: Database CLI ==="

run_test "blocks redis FLUSHALL" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-redis-flushall.json" 2

run_test "blocks dropdb" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-dropdb.json" 2

echo ""
echo "=== Dangerous Command Blocker: IaC ==="

run_test "blocks terraform destroy" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-terraform-destroy.json" 2

run_test "blocks pulumi destroy" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-pulumi-destroy.json" 2

run_test "allows safe terraform commands" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-safe-terraform.json" 0

echo ""
echo "=== Dangerous Command Blocker: SQL and Misc ==="

run_test "blocks SQL DROP TABLE" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-sql-drop-table.json" 2

run_test "blocks crontab -r" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-crontab-remove.json" 2

run_test "blocks credential exfiltration via curl" \
    "${HOOKS}/dangerous-command-blocker.py" \
    "${FIXTURES}/bash-curl-exfil.json" 2

echo ""
echo "=== Conventional Commits ==="

run_test "allows valid conventional commit" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/commit-valid.json" 0

run_test "blocks non-conventional commit message" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/commit-invalid.json" 2

run_test "ignores non-commit commands" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/commit-not-a-commit.json" 0

run_test "blocks commit with subject over 72 chars" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/bash-commit-long-subject.json" 2

run_test "allows valid heredoc commit" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/bash-commit-heredoc.json" 0

run_test "handles malformed JSON gracefully" \
    "${HOOKS}/conventional-commits.sh" \
    "${FIXTURES}/malformed-json.txt" 0

echo ""
echo "=== Secret Scanner ==="

run_test "ignores non-commit commands" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/commit-not-a-commit.json" 0

run_test "allows safe commands" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/bash-safe-command.json" 0

# Note: positive secret detection requires staged files with actual secrets
# in a real git repo. The scanner correctly skips when there are no staged files.
run_test "allows commit when no staged files have secrets" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/commit-with-secret.json" 0

run_test "handles malformed JSON gracefully" \
    "${HOOKS}/secret-scanner.py" \
    "${FIXTURES}/malformed-json.txt" 0

echo ""
echo "=== Smart Formatter ==="

run_test "handles nonexistent file gracefully" \
    "${HOOKS}/smart-formatter.sh" \
    "${FIXTURES}/edit-nonexistent-file.json" 0

echo ""
echo "=== Large File Blocker ==="

run_test "allows safe commands" \
    "${HOOKS}/large-file-blocker.sh" \
    "${FIXTURES}/bash-safe-command.json" 0

run_test "allows non-commit commands" \
    "${HOOKS}/large-file-blocker.sh" \
    "${FIXTURES}/commit-not-a-commit.json" 0

# Note: positive large file detection requires staged files exceeding 5MB
# in a real git repo. The blocker correctly passes when there are no large staged files.
run_test "allows commit when no staged files are large" \
    "${HOOKS}/large-file-blocker.sh" \
    "${FIXTURES}/commit-valid.json" 0

echo ""
echo "=== Env File Guard ==="

run_test "blocks writing to .env" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-env-file.json" 2

run_test "allows writing to .env.example" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-env-example.json" 0

run_test "blocks editing private key files" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/edit-private-key.json" 2

run_test "blocks writing to secrets directory" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-secrets-dir.json" 2

run_test "blocks writing to .env.staging" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-env-staging.json" 2

run_test "blocks writing to .env.testing" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-env-testing.json" 2

run_test "allows writing to .env.defaults" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-env-defaults.json" 0

run_test "allows safe file writes" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-tool-input.json" 0

run_test "ignores non-Write/Edit tools" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/bash-safe-command.json" 0

run_test "handles malformed JSON gracefully" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/malformed-json.txt" 0

echo ""
echo "=== Env File Guard: Credential Files ==="

run_test "blocks writing to .aws/credentials" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-aws-credentials.json" 2

run_test "blocks writing to .kube/config" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-kube-config.json" 2

run_test "blocks writing to .docker/config.json" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-docker-config.json" 2

run_test "blocks writing to .npmrc" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-npmrc.json" 2

run_test "blocks writing to .tfstate" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-tfstate.json" 2

run_test "blocks writing to .tfvars" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-tfvars.json" 2

run_test "blocks writing to .ssh key" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-ssh-key.json" 2

run_test "blocks writing to service account JSON" \
    "${HOOKS}/env-file-guard.sh" \
    "${FIXTURES}/write-service-account.json" 2

echo ""
echo "=== GH Token Guard ==="

run_test "allows gh with GH_TOKEN set" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-gh-with-token.json" 0

run_test "blocks gh without GH_TOKEN" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-gh-without-token.json" 2

run_test "blocks gh auth switch" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-gh-auth-switch.json" 2

run_test "allows gh auth token as exempt command" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-gh-auth-token.json" 0

run_test "allows non-gh commands" \
    "${HOOKS}/gh-token-guard.py" \
    "${FIXTURES}/bash-safe-command.json" 0

echo ""
echo "=== GLab Token Guard ==="

run_test "allows glab with GITLAB_TOKEN set" \
    "${HOOKS}/glab-token-guard.py" \
    "${FIXTURES}/bash-glab-with-token.json" 0

run_test "blocks glab without GITLAB_TOKEN" \
    "${HOOKS}/glab-token-guard.py" \
    "${FIXTURES}/bash-glab-without-token.json" 2

run_test "blocks glab auth login" \
    "${HOOKS}/glab-token-guard.py" \
    "${FIXTURES}/bash-glab-auth-login.json" 2

run_test "allows non-glab commands" \
    "${HOOKS}/glab-token-guard.py" \
    "${FIXTURES}/bash-safe-command.json" 0

echo ""
echo "=== Docker Context Guard ==="

run_test "blocks docker context use" \
    "${HOOKS}/docker-context-guard.py" \
    "${FIXTURES}/bash-docker-context-use.json" 2

run_test "allows docker --context flag" \
    "${HOOKS}/docker-context-guard.py" \
    "${FIXTURES}/bash-docker-context-flag.json" 0

run_test "allows DOCKER_CONTEXT env" \
    "${HOOKS}/docker-context-guard.py" \
    "${FIXTURES}/bash-docker-context-env.json" 0

run_test "allows docker context ls" \
    "${HOOKS}/docker-context-guard.py" \
    "${FIXTURES}/bash-docker-context-ls.json" 0

run_test "allows bare docker commands" \
    "${HOOKS}/docker-context-guard.py" \
    "${FIXTURES}/bash-docker-bare.json" 0

echo ""
echo "=== Kubectl Context Guard ==="

run_test "blocks kubectl config use-context" \
    "${HOOKS}/kubectl-context-guard.py" \
    "${FIXTURES}/bash-kubectl-use-context.json" 2

run_test "allows kubectl --context flag" \
    "${HOOKS}/kubectl-context-guard.py" \
    "${FIXTURES}/bash-kubectl-context-flag.json" 0

run_test "allows kubectl config current-context" \
    "${HOOKS}/kubectl-context-guard.py" \
    "${FIXTURES}/bash-kubectl-current.json" 0

run_test "blocks kubectx <name>" \
    "${HOOKS}/kubectl-context-guard.py" \
    "${FIXTURES}/bash-kubectx-switch.json" 2

run_test "allows bare kubectx (list)" \
    "${HOOKS}/kubectl-context-guard.py" \
    "${FIXTURES}/bash-kubectx-list.json" 0

run_test "allows KUBECONFIG env" \
    "${HOOKS}/kubectl-context-guard.py" \
    "${FIXTURES}/bash-kubectl-kubeconfig.json" 0

echo ""
echo "=== AWS Profile Guard ==="

run_test "blocks aws configure set without --profile" \
    "${HOOKS}/aws-profile-guard.py" \
    "${FIXTURES}/bash-aws-configure-set-default.json" 2

run_test "allows aws configure set with --profile" \
    "${HOOKS}/aws-profile-guard.py" \
    "${FIXTURES}/bash-aws-configure-set-profile.json" 0

run_test "allows aws --profile flag" \
    "${HOOKS}/aws-profile-guard.py" \
    "${FIXTURES}/bash-aws-with-profile.json" 0

run_test "allows AWS_PROFILE env" \
    "${HOOKS}/aws-profile-guard.py" \
    "${FIXTURES}/bash-aws-bare-readonly.json" 0

run_test "allows bare aws read-only" \
    "${HOOKS}/aws-profile-guard.py" \
    "${FIXTURES}/bash-aws-without-profile.json" 0

echo ""
echo "=== Gcloud Config Guard ==="

run_test "blocks gcloud config set account" \
    "${HOOKS}/gcloud-config-guard.py" \
    "${FIXTURES}/bash-gcloud-set-account.json" 2

run_test "blocks gcloud config set project" \
    "${HOOKS}/gcloud-config-guard.py" \
    "${FIXTURES}/bash-gcloud-set-project.json" 2

run_test "blocks gcloud config configurations activate" \
    "${HOOKS}/gcloud-config-guard.py" \
    "${FIXTURES}/bash-gcloud-activate-config.json" 2

run_test "allows gcloud --configuration flag" \
    "${HOOKS}/gcloud-config-guard.py" \
    "${FIXTURES}/bash-gcloud-with-config-flag.json" 0

run_test "allows gcloud config configurations list" \
    "${HOOKS}/gcloud-config-guard.py" \
    "${FIXTURES}/bash-gcloud-config-list.json" 0

echo ""
echo "=== Terraform Workspace Guard ==="

run_test "blocks terraform workspace select" \
    "${HOOKS}/terraform-workspace-guard.py" \
    "${FIXTURES}/bash-terraform-workspace-select.json" 2

run_test "allows TF_WORKSPACE env" \
    "${HOOKS}/terraform-workspace-guard.py" \
    "${FIXTURES}/bash-terraform-workspace-env.json" 0

run_test "allows terraform workspace list" \
    "${HOOKS}/terraform-workspace-guard.py" \
    "${FIXTURES}/bash-terraform-workspace-list.json" 0

run_test "allows terraform workspace show" \
    "${HOOKS}/terraform-workspace-guard.py" \
    "${FIXTURES}/bash-terraform-workspace-show.json" 0

echo ""
echo "=== Mise Global Guard ==="

run_test "blocks mise use --global" \
    "${HOOKS}/mise-global-guard.py" \
    "${FIXTURES}/bash-mise-use-global.json" 2

run_test "blocks mise use -g" \
    "${HOOKS}/mise-global-guard.py" \
    "${FIXTURES}/bash-mise-use-g-short.json" 2

run_test "blocks mise unuse --global" \
    "${HOOKS}/mise-global-guard.py" \
    "${FIXTURES}/bash-mise-unuse-global.json" 2

run_test "allows mise use (project-local)" \
    "${HOOKS}/mise-global-guard.py" \
    "${FIXTURES}/bash-mise-use-local.json" 0

run_test "allows mise install" \
    "${HOOKS}/mise-global-guard.py" \
    "${FIXTURES}/bash-mise-install.json" 0

run_test "allows mise exec" \
    "${HOOKS}/mise-global-guard.py" \
    "${FIXTURES}/bash-mise-exec.json" 0

run_test "allows mise current" \
    "${HOOKS}/mise-global-guard.py" \
    "${FIXTURES}/bash-mise-current.json" 0

echo ""
echo "=== Migration Idempotency ==="

run_test "blocks CREATE TABLE without IF NOT EXISTS" \
    "${HOOKS}/migration-idempotency.py" \
    "${FIXTURES}/migration-create-table-bad.json" 2

run_test "allows CREATE TABLE IF NOT EXISTS" \
    "${HOOKS}/migration-idempotency.py" \
    "${FIXTURES}/migration-create-table-good.json" 0

run_test "blocks DROP TABLE without IF EXISTS" \
    "${HOOKS}/migration-idempotency.py" \
    "${FIXTURES}/migration-drop-bad.json" 2

run_test "blocks CREATE INDEX without CONCURRENTLY" \
    "${HOOKS}/migration-idempotency.py" \
    "${FIXTURES}/migration-create-index-blocking.json" 2

run_test "allows CREATE INDEX CONCURRENTLY IF NOT EXISTS" \
    "${HOOKS}/migration-idempotency.py" \
    "${FIXTURES}/migration-create-index-concurrently.json" 0

run_test "ignores DDL outside migration paths" \
    "${HOOKS}/migration-idempotency.py" \
    "${FIXTURES}/migration-non-migration-path.json" 0

echo ""
echo "=== Git Author Guard ==="

LOCAL_OVERRIDE_REPO="/tmp/git-author-guard-fixture-local-override"
PLACEHOLDER_COMMIT_REPO="/tmp/git-author-guard-fixture-placeholder-commit"
NO_IDENTITY_REPO="/tmp/git-author-guard-fixture-no-identity"
trap 'rm -rf "${LOCAL_OVERRIDE_REPO}" "${PLACEHOLDER_COMMIT_REPO}" "${NO_IDENTITY_REPO}"' EXIT

# Repo with a [user] block in .git/config (local override).
rm -rf "${LOCAL_OVERRIDE_REPO}"
git init -q "${LOCAL_OVERRIDE_REPO}"
git -C "${LOCAL_OVERRIDE_REPO}" config --local user.email "override@example.com"
git -C "${LOCAL_OVERRIDE_REPO}" config --local user.name "Override"

# Repo with a placeholder author email on HEAD (drives the push test).
rm -rf "${PLACEHOLDER_COMMIT_REPO}"
git init -q "${PLACEHOLDER_COMMIT_REPO}"
GIT_AUTHOR_NAME="Placeholder" GIT_AUTHOR_EMAIL="placeholder@example.com" \
GIT_COMMITTER_NAME="Placeholder" GIT_COMMITTER_EMAIL="placeholder@example.com" \
    git -C "${PLACEHOLDER_COMMIT_REPO}" commit --allow-empty -q -m "placeholder commit"

# Repo with no identity at all (no local override, runner forces empty global).
rm -rf "${NO_IDENTITY_REPO}"
git init -q "${NO_IDENTITY_REPO}"

run_test "blocks commit with env override on command line" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-commit-env-injection.json" 2

run_test "blocks commit when local [user] block overrides identity" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-commit-local-override.json" 2

# This case must run with empty global config so user.email resolves to empty.
echo -n "  "
ACTUAL_NO_ID=0
HOME="${NO_IDENTITY_REPO}" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    "${HOOKS}/git-author-guard.py" < "${FIXTURES}/bash-git-commit-no-identity.json" \
    >/dev/null 2>&1 || ACTUAL_NO_ID=$?
if [[ "${ACTUAL_NO_ID}" -eq 2 ]]; then
    echo "PASS: blocks commit when user.email is unset (exit 2)"
    PASS=$((PASS + 1))
else
    echo "FAIL: blocks commit when user.email is unset (expected 2, got ${ACTUAL_NO_ID})"
    FAIL=$((FAIL + 1))
fi

run_test "allows commit with resolved identity" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-commit-resolved-identity.json" 0

run_test "allows clean push" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-push-clean.json" 0

run_test "blocks push when commit has placeholder author" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-push-placeholder.json" 2

run_test "blocks git config --local user.email" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-config-local-user.json" 2

run_test "allows git config --global user.email" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-config-global-user.json" 0

run_test "blocks unscoped git config user.email" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-config-user-email-no-scope.json" 2

run_test "allows git config --get user.email" \
    "${HOOKS}/git-author-guard.py" \
    "${FIXTURES}/bash-git-config-get-user.json" 0

echo ""
echo "=== Results ==="
echo "  Passed: ${PASS}"
echo "  Failed: ${FAIL}"
echo ""

if [[ "${FAIL}" -gt 0 ]]; then
    exit 1
fi
