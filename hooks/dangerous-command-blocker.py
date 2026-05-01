#!/usr/bin/env python3
"""Block catastrophic and dangerous bash commands at runtime.

Three severity levels:
  Level 1 BLOCK: Catastrophic, irreversible system damage
  Level 2 BLOCK: Critical path protection and destructive operations
  Level 3 WARN:  Suspicious patterns that might be intentional

Categories covered:
  - Filesystem destruction (rm, dd, mkfs, shred, wipe)
  - Privilege escalation (sudo, setuid, capabilities, sudoers)
  - Reverse shells and remote code execution
  - Git destructive operations (force push, reset, filter-branch, reflog)
  - Cloud CLI (AWS, GCP, Azure, Vercel, Netlify, Firebase, Cloudflare, Fly.io)
  - Container and orchestration (Docker, Podman, Kubernetes, Helm)
  - Database CLI (Redis, MongoDB, PostgreSQL, MySQL, SQLite, Cassandra)
  - Infrastructure as Code (Terraform, Pulumi, Ansible, CDK, Serverless)
  - SQL destructive statements (DROP, TRUNCATE, DELETE, UPDATE without WHERE)
  - Secret exfiltration via command arguments (curl headers, inline creds)
  - Cron and systemd manipulation

Receives Bash tool input as JSON on stdin.
Exit 0 = allow, exit 2 = block.

Cross-platform: works on macOS and Linux (Ubuntu).
"""

import json
import os
import re
import subprocess
import sys

# Best-effort import of the shared audit log helper. Silent fallback keeps the
# hook functional even if the script directory is not on sys.path.
sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover
    def _audit(**_fields):  # type: ignore
        return None

# ---------------------------------------------------------------------------
# Safe cleanup commands. Bypass all checks — these are harmless.
# ---------------------------------------------------------------------------
SAFE_CLEANUP = [
    r"\brm\s+(-[a-zA-Z]*\s+)*node_modules(/|$|\s*$)",    # rm -rf node_modules
    r"\brm\s+(-[a-zA-Z]*\s+)*dist(/|$|\s*$)",             # rm -rf dist
    r"\brm\s+(-[a-zA-Z]*\s+)*\.next(/|$|\s*$)",           # rm -rf .next
    r"\brm\s+(-[a-zA-Z]*\s+)*\.nuxt(/|$|\s*$)",           # rm -rf .nuxt
    r"\brm\s+(-[a-zA-Z]*\s+)*build(/|$|\s*$)",            # rm -rf build
    r"\brm\s+(-[a-zA-Z]*\s+)*coverage(/|$|\s*$)",         # rm -rf coverage
    r"\brm\s+(-[a-zA-Z]*\s+)*\.turbo(/|$|\s*$)",          # rm -rf .turbo
    r"\brm\s+(-[a-zA-Z]*\s+)*out(/|$|\s*$)",              # rm -rf out
]

# ---------------------------------------------------------------------------
# Level 1: Catastrophic commands. Always block. No legitimate use case.
# ---------------------------------------------------------------------------
CATASTROPHIC = [
    # Filesystem destruction
    r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\s*$",          # rm -rf /
    r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\s+",            # rm -rf / <anything>
    r"\bsudo\s+rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/",        # sudo rm -rf /
    r"\bdd\s+.*\bof=/dev/[sh]d",                           # dd to disk device
    r"\bdd\s+.*\bof=/dev/nvme",                            # dd to NVMe device
    r"\bsudo\s+dd\s+.*\bof=/dev/",                         # sudo dd to any device
    r"\bmkfs\b",                                            # format filesystem
    r"\bsudo\s+mkfs\b",                                     # sudo format filesystem
    r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;",                     # fork bomb
    r"\bchmod\s+(-[a-zA-Z]*\s+)?777\s+/\s*$",             # chmod 777 /
    r"\bchmod\s+(-[a-zA-Z]*\s+)?777\s+/[a-z]",            # chmod 777 /etc, /usr...
    r">\s*/dev/[sh]d",                                      # write to raw disk
    r"\bshred\s+.*(/dev/|/boot/|/etc/)",                   # shred system paths
    r"\bwipefs\b.*(/dev/[sh]d|/dev/nvme)",                 # wipe filesystem signatures
    r"\bdd\s+.*\bof=/dev/(disk|rdisk|loop|md|mapper)",     # dd to additional device classes
    r"\bfind\s+[/~]\S*\s+.*-delete\b",                      # find / -delete or find ~ -delete
    r"\bfind\s+[/~]\S*\s+.*-exec\s+rm\b",                   # find -exec rm on system roots
    r"\bxargs\s+(-[a-zA-Z0]*\s+)*rm\s+(-[a-zA-Z]*[rRf])",  # xargs rm -rf pipelines
    r"\btar\s+.*--absolute-(names|paths)\b.*\bx",           # tar extract with absolute paths
    # Remote code execution and reverse shells
    r"\bwget\b.*\|\s*(ba)?sh",                              # pipe remote script to shell
    r"\bcurl\b.*\|\s*(ba)?sh",                              # pipe remote script to shell
    r"\bbash\s+-i\s+>&\s*/dev/tcp/",                       # bash reverse shell
    r"\bnc\s+.*-e\s+/bin/(ba)?sh",                         # netcat reverse shell
    r"\bncat\s+.*-e\s+/bin/(ba)?sh",                       # ncat reverse shell
    r"\bsocat\s+.*EXEC.*sh",                                # socat reverse shell
    r"\bpython3?\s+-c\s+.*socket.*connect",                # python reverse shell
    r"\bperl\s+-e\s+.*socket.*connect",                    # perl reverse shell
    r"\bruby\s+-rsocket\s+-e",                              # ruby reverse shell
    # Privilege escalation
    r".*>>\s*/etc/sudoers",                                 # append to sudoers
    r"\bsudo\s+chmod\s+[ugo]\+s\b",                       # sudo setuid/setgid
    r"\bsudo\s+visudo\b",                                   # editing sudoers
]

# ---------------------------------------------------------------------------
# Level 2: Destructive operations. Block with explanation.
# ---------------------------------------------------------------------------
CRITICAL_PATHS = [
    # --- Filesystem critical paths ---
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.git\b", "Deleting .git/ destroys repository history"),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.env\b", "Deleting .env removes environment configuration"),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.claude\b", "Deleting .claude/ removes Claude configuration"),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.ssh\b", "Deleting .ssh/ destroys SSH keys and config"),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.aws\b", "Deleting .aws/ removes AWS credentials and config"),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.gnupg\b", "Deleting .gnupg/ destroys GPG keys"),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.kube\b", "Deleting .kube/ removes Kubernetes configuration"),
    (r"\bsudo\s+rm\s+(-[a-zA-Z]*\s+)?.*\.(git|env|ssh|aws|gnupg|kube)\b",
     "sudo rm on critical dotfiles"),

    # --- Git destructive ---
    (r"\bgit\s+push\s+.*--force(\s|$)", "Use --force-with-lease instead of --force"),
    (r"\bgit\s+push\s+.*\s-f(\s|$)", "Use --force-with-lease instead of -f"),
    (r"\bgit\s+filter-branch\b", "git filter-branch rewrites history destructively"),
    (r"\bgit\s+reflog\s+expire\b", "git reflog expire removes recovery points"),
    (r"\bgit\s+push\s+.*\borigin\s+:", "git push origin :ref deletes a remote branch"),
    (r"\bgit\s+push\s+.*\borigin\s+\+", "git push origin +ref force-pushes a branch"),
    (r"\bgit\s+update-ref\s+-d\b", "git update-ref -d deletes a ref"),
    (r"\bgit\s+replace\b", "git replace rewrites object history"),
    (r"\bgit\s+gc\s+.*--prune=now", "git gc --prune=now immediately removes unreachable objects"),

    # --- AWS destructive ---
    (r"\baws\s+s3\s+rb\b", "AWS S3 bucket deletion"),
    (r"\baws\s+s3\s+rm\s+.*--recursive\b", "AWS S3 recursive object deletion"),
    (r"\baws\s+ec2\s+terminate-instances\b", "AWS EC2 instance termination"),
    (r"\baws\s+rds\s+delete-db-(instance|cluster)\b", "AWS RDS database deletion"),
    (r"\baws\s+lambda\s+delete-function\b", "AWS Lambda function deletion"),
    (r"\baws\s+cloudformation\s+delete-stack\b", "AWS CloudFormation stack deletion"),
    (r"\baws\s+iam\s+delete-(user|role|policy|group)\b", "AWS IAM resource deletion"),
    (r"\baws\s+eks\s+delete-cluster\b", "AWS EKS cluster deletion"),
    (r"\baws\s+route53\s+delete-hosted-zone\b", "AWS Route53 hosted zone deletion"),
    (r"\baws\s+dynamodb\s+delete-table\b", "AWS DynamoDB table deletion"),
    (r"\baws\s+sqs\s+delete-queue\b", "AWS SQS queue deletion"),
    (r"\baws\s+sns\s+delete-topic\b", "AWS SNS topic deletion"),
    (r"\baws\s+ecr\s+delete-repository\b", "AWS ECR repository deletion"),
    (r"\baws\s+elasticache\s+delete-(cache-cluster|replication-group)\b",
     "AWS ElastiCache deletion"),
    (r"\baws\s+secretsmanager\s+delete-secret\b", "AWS Secrets Manager secret deletion"),
    (r"\baws\s+kms\s+schedule-key-deletion\b", "AWS KMS key scheduled for deletion"),
    (r"\baws\s+cognito-idp\s+delete-user-pool\b", "AWS Cognito user pool deletion"),
    (r"\baws\s+logs\s+delete-log-group\b", "AWS CloudWatch log group deletion"),

    # --- GCP destructive ---
    (r"\bgcloud\s+projects\s+delete\b", "GCP project deletion"),
    (r"\bgcloud\s+compute\s+instances\s+delete\b", "GCP VM instance deletion"),
    (r"\bgcloud\s+sql\s+instances\s+delete\b", "GCP Cloud SQL deletion"),
    (r"\bgcloud\s+container\s+clusters\s+delete\b", "GCP GKE cluster deletion"),
    (r"\bgcloud\s+functions\s+delete\b", "GCP Cloud Function deletion"),
    (r"\bgcloud\s+run\s+services\s+delete\b", "GCP Cloud Run service deletion"),
    (r"\bgcloud\s+pubsub\s+(topics|subscriptions)\s+delete\b", "GCP Pub/Sub deletion"),
    (r"\bgcloud\s+firestore\s+databases\s+delete\b", "GCP Firestore database deletion"),
    (r"\bgcloud\s+storage\s+(rm|buckets\s+delete)\b", "GCP Cloud Storage deletion"),

    # --- Azure destructive ---
    (r"\baz\s+group\s+delete\b", "Azure resource group deletion"),
    (r"\baz\s+vm\s+delete\b", "Azure VM deletion"),
    (r"\baz\s+sql\s+server\s+delete\b", "Azure SQL Server deletion"),
    (r"\baz\s+aks\s+delete\b", "Azure AKS cluster deletion"),
    (r"\baz\s+webapp\s+delete\b", "Azure Web App deletion"),
    (r"\baz\s+functionapp\s+delete\b", "Azure Function App deletion"),
    (r"\baz\s+storage\s+account\s+delete\b", "Azure Storage account deletion"),
    (r"\baz\s+keyvault\s+delete\b", "Azure Key Vault deletion"),
    (r"\baz\s+cosmosdb\s+delete\b", "Azure Cosmos DB deletion"),

    # --- Platform CLI destructive ---
    (r"\bvercel\s+(rm|remove)\b", "Vercel project deletion"),
    (r"\bnetlify\s+sites:delete\b", "Netlify site deletion"),
    (r"\bfirebase\s+projects:delete\b", "Firebase project deletion"),
    (r"\bfirebase\s+hosting:disable\b", "Firebase hosting disable"),
    (r"\bwrangler\s+delete\b", "Cloudflare Worker deletion"),
    (r"\bfly\s+(apps\s+)?destroy\b", "Fly.io app destruction"),
    (r"\bheroku\s+apps:destroy\b", "Heroku app destruction"),
    (r"\brailway\s+delete\b", "Railway project deletion"),
    (r"\bsupabase\s+projects\s+delete\b", "Supabase project deletion"),

    # --- Docker destructive ---
    (r"\bdocker\s+run\s+.*--privileged", "Docker privileged mode is a security risk"),
    (r"\bdocker\s+system\s+prune\s+.*-a", "Docker system prune -a removes all unused data"),
    (r"\bdocker\s+rm\s+.*-f", "Docker forced container removal"),
    (r"\bdocker\s+rmi\s+.*-f", "Docker forced image removal"),
    (r"\bdocker\s+volume\s+(rm|prune)\b", "Docker volume removal destroys persistent data"),
    (r"\bdocker\s+network\s+rm\b", "Docker network removal"),
    (r"\bdocker(-|\s+)compose\s+down\s+.*-v", "Docker Compose down -v destroys volumes"),
    (r"\bpodman\s+run\s+.*--privileged", "Podman privileged mode is a security risk"),
    (r"\bpodman\s+system\s+prune\s+.*-a", "Podman system prune -a removes all unused data"),

    # --- Kubernetes destructive ---
    (r"\bkubectl\s+delete\s+(namespace|node|pv|pvc|clusterrole)\b",
     "Kubernetes critical resource deletion"),
    (r"\bkubectl\s+delete\s+.*--all\b", "Kubernetes mass resource deletion"),
    (r"\bkubectl\s+drain\b", "Kubernetes node drain evicts all pods"),
    (r"\bkubectl\s+cordon\b", "Kubernetes node cordon prevents new pod scheduling"),
    (r"\bkubectl\s+replace\s+--force\b", "Kubernetes forced resource replacement"),
    (r"\bkubectl\s+edit\s+(clusterrole|secret)\b",
     "Kubernetes cluster-wide resource edit"),

    # --- Helm destructive ---
    (r"\bhelm\s+uninstall\b", "Helm release uninstallation"),

    # --- Redis destructive ---
    (r"\bredis-cli\s+.*\bFLUSHALL\b", "Redis FLUSHALL destroys all data in all databases"),
    (r"\bredis-cli\s+.*\bFLUSHDB\b", "Redis FLUSHDB destroys current database"),
    (r"\bredis-cli\s+.*\bDEBUG\s+SET-ACTIVE-EXPIRE\b", "Redis DEBUG command is dangerous"),
    (r"\bredis-cli\s+.*\bCONFIG\s+SET\b", "Redis runtime config change"),

    # --- MongoDB destructive ---
    (r"\bmongo(sh)?\b.*\b(dropDatabase|dropCollection)\b", "MongoDB database/collection drop"),
    (r"\bmongo(sh)?\b.*\bdeleteMany\s*\(\s*\{\s*\}\s*\)", "MongoDB deleteMany({}) deletes all documents"),

    # --- PostgreSQL destructive ---
    (r"\bdropdb\b", "PostgreSQL database drop via CLI"),
    (r"\bpsql\b.*\bDROP\s+(DATABASE|SCHEMA|TABLE|INDEX)\b", "PostgreSQL destructive DDL"),
    (r"\bpg_dump\b.*\|.*\bpsql\b", "Piping pg_dump output, verify the target database"),

    # --- MySQL destructive ---
    (r"\bmysqladmin\b.*\bdrop\b", "MySQL database drop via CLI"),
    (r"\bmysql\b.*-e\s*.*\bDROP\s+(DATABASE|TABLE)\b", "MySQL destructive DDL via CLI"),
    (r"\bmysql\b.*-e\s*.*\bTRUNCATE\b", "MySQL TRUNCATE via CLI"),

    # --- SQLite destructive ---
    (r"\bsqlite3?\b.*\.quit.*DROP\b", "SQLite destructive operation"),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.sqlite3?\b", "Deleting SQLite database file"),

    # --- Terraform destructive ---
    (r"\bterraform\s+destroy\b", "Terraform destroy removes all managed infrastructure"),
    (r"\bterraform\s+apply\s+.*-auto-approve", "Terraform apply without manual review"),
    (r"\bterraform\s+taint\b", "Terraform taint marks resources for forced recreation"),
    (r"\bterraform\s+force-unlock\b", "Terraform force-unlock breaks state locking"),
    (r"\bterraform\s+import\b.*-allow-missing-config",
     "Terraform import with missing config can corrupt state"),
    (r"\btofu\s+destroy\b", "OpenTofu destroy removes all managed infrastructure"),
    (r"\btofu\s+apply\s+.*-auto-approve", "OpenTofu apply without manual review"),

    # --- Pulumi destructive ---
    (r"\bpulumi\s+destroy\b", "Pulumi destroy removes all managed infrastructure"),
    (r"\bpulumi\s+stack\s+rm\b", "Pulumi stack removal"),

    # --- Ansible destructive ---
    (r"\bansible-playbook\b.*(-i|--inventory)\s+.*prod",
     "Ansible playbook targeting production inventory"),
    (r"\bansible\s+.*-m\s+(shell|command|raw)\b.*prod",
     "Ansible ad-hoc command on production"),

    # --- CDK / Serverless destructive ---
    (r"\bcdk\s+destroy\b", "AWS CDK destroy removes all stack resources"),
    (r"\bserverless\s+remove\b", "Serverless Framework removes the deployed service"),
    (r"\bsam\s+delete\b", "AWS SAM delete removes the deployed stack"),
    (r"\bcopilot\s+app\s+delete\b", "AWS Copilot app deletion"),

    # --- SQL in command strings (case-insensitive) ---
    (r"(?i)\bDELETE\s+FROM\s+\w+\s*;", "DELETE without WHERE clause deletes all rows"),
    (r"(?i)\bTRUNCATE\s+(TABLE\s+)?\w+", "TRUNCATE removes all rows without logging"),
    (r"(?i)\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|FUNCTION|PROCEDURE)\s+",
     "DROP permanently destroys the object"),
    (r"(?i)\bUPDATE\s+\w+\s+SET\s+(?!.*\bWHERE\b).*[;'\"]",
     "UPDATE without WHERE clause modifies all rows"),
    (r"(?i)\bALTER\s+TABLE\s+\w+\s+DROP\s+(COLUMN|CONSTRAINT)\b",
     "ALTER TABLE DROP removes a column or constraint"),
    (r"(?i)\bGRANT\s+ALL\s+.*TO\b", "GRANT ALL gives full permissions"),
    (r"(?i)\bREVOKE\s+ALL\s+.*FROM\b", "REVOKE ALL removes all permissions"),

    # --- Cron and systemd ---
    (r"\bcrontab\s+-r\b", "crontab -r deletes all cron jobs for the user"),
    (r"\bsudo\s+systemctl\s+(stop|disable|mask)\s+", "Stopping/disabling a systemd service"),

    # --- Secret exfiltration via commands ---
    (r"\bcurl\b.*(-d|--data)\s+.*@\.(env|ssh|aws|gnupg|kube)",
     "curl sending credential file contents to a remote server"),
    (r"\bscp\b.*\.(env|pem|key)\s+.*@",
     "scp sending credential files to a remote host"),
    (r"\brsync\b.*\.(env|pem|key|ssh)\b.*@",
     "rsync syncing credential files to a remote host"),
]

# ---------------------------------------------------------------------------
# Level 2.5: Recoverable operations. Ask (warn via stderr) but allow.
# These commands are destructive but have recovery paths (reflog, restart,
# rollback). Claude should confirm with the user before proceeding.
# ---------------------------------------------------------------------------
RECOVERABLE = [
    (r"\bgit\s+reset\s+--hard\b",
     "git reset --hard discards uncommitted work. Recovery: git reflog. Confirm with the user before running."),
    (r"\bgit\s+clean\s+.*-f",
     "git clean -f permanently deletes untracked files with no recovery. Confirm the path is correct."),
    (r"\bgit\s+checkout\s+\.\s*$",
     "git checkout . discards all unstaged changes. Recovery: only if changes were staged. Confirm with the user."),
    (r"\bgit\s+stash\s+drop\s+--all",
     "git stash drop --all removes all stashed changes. Confirm the user no longer needs them."),
    (r"\bdocker\s+system\s+prune\b(?!.*-a)",
     "docker system prune removes unused containers, networks, and images. Confirm before running."),
    (r"\bkubectl\s+rollout\s+restart\b",
     "kubectl rollout restart causes a rolling restart of the workload. Confirm this is intentional."),
    (r"\bhelm\s+rollback\b",
     "helm rollback changes the live deployment to a previous release. Confirm the target revision."),
    (r"\bterraform\s+state\s+rm\b",
     "terraform state rm removes a resource from state tracking without destroying it. Confirm the resource name."),
    (r"\bpulumi\s+cancel\b",
     "pulumi cancel aborts an in-progress update. Confirm the update should be cancelled."),
]

# ---------------------------------------------------------------------------
# Level 3: Suspicious patterns. Warn but allow.
# ---------------------------------------------------------------------------
SUSPICIOUS = [
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\*", "rm with wildcard, double-check the path"),
    (r"\bfind\b.*-delete\b", "find -delete permanently removes matched files"),
    (r"\bxargs\s+rm\b", "xargs rm can delete unexpected files"),
    (r">\s*/etc/", "Writing to /etc/ modifies system configuration"),
    (r"\bkillall\b", "killall terminates all processes with that name"),
    (r"\bkill\s+-9\b", "kill -9 force-terminates without cleanup"),
    (r"\bsudo\b", "sudo elevates privileges, verify this is intentional"),
    (r"\bdocker\s+exec\b", "docker exec runs commands in a running container"),
    (r"\bkubectl\s+exec\b", "kubectl exec runs commands in a pod"),
    (r"\bkubectl\s+apply\b", "kubectl apply modifies cluster resources"),
    (r"\bkubectl\s+delete\s+(deployment|service|configmap|secret|pod|ingress|statefulset|"
     r"daemonset|job|cronjob|hpa|networkpolicy)\b",
     "kubectl delete removes a cluster resource"),
    (r"\bterraform\s+apply\b(?!.*-auto-approve)", "terraform apply modifies infrastructure"),
    (r"\bchown\s+(-[a-zA-Z]*\s+)?.*\s+/", "chown on system paths changes ownership"),
    (r"\bchmod\s+(-[a-zA-Z]*R)", "recursive chmod changes permissions on many files"),
    (r"\bgit\s+stash\s+drop\b", "git stash drop removes a stash entry"),
    (r"\bgit\s+branch\s+-D\b", "git branch -D force-deletes an unmerged branch"),
    (r"\bansible-playbook\b", "ansible-playbook modifies remote infrastructure"),
    (r"\bhelm\s+upgrade\b", "helm upgrade changes a live deployment"),
    (r"\bdocker\s+stop\b", "docker stop halts a running container"),
    (r"\bnpm\s+publish\b", "npm publish pushes a package to the registry"),
    (r"\bgit\s+tag\s+-d\b", "git tag -d deletes a local tag"),
]


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", data.get("input", {})).get("command", "")
    if not command:
        sys.exit(0)

    # Safe cleanup allowlist: bypass all checks
    for pattern in SAFE_CLEANUP:
        if re.search(pattern, command):
            sys.exit(0)

    # Level 1: Catastrophic
    for pattern in CATASTROPHIC:
        if re.search(pattern, command):
            _audit(hook="dangerous-command-blocker", decision="block",
                   level="catastrophic", pattern=pattern, command=command[:300])
            print(f"BLOCKED: Catastrophic command detected.\nCommand: {command}")
            sys.exit(2)

    # Level 2: Critical paths and destructive operations
    for pattern, reason in CRITICAL_PATHS:
        if re.search(pattern, command):
            _audit(hook="dangerous-command-blocker", decision="block",
                   level="critical", pattern=pattern, reason=reason,
                   command=command[:300])
            print(f"BLOCKED: {reason}\nCommand: {command}")
            sys.exit(2)

    # Level 2.5: Recoverable operations — ask the user, do not block
    for pattern, guidance in RECOVERABLE:
        if re.search(pattern, command):
            print(
                f"CONFIRM REQUIRED: {guidance}\nCommand: {command}\n"
                "Ask the user to confirm before running this command.",
                file=sys.stderr,
            )
            break

    # Level 2.5: Protected branch push detection
    if re.search(r"\bgit\s+push\b", command) and not re.search(r"--force", command):
        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            branch = ""

        protected = re.compile(r"\b(main|master|develop)\b")
        targets_protected = (
            re.search(r"\borigin\s+", command)
            and protected.search(command.split("origin", 1)[-1])
        ) or (
            branch in ("main", "master", "develop")
            and not re.search(r"\borigin\s+\w", command)
        )
        if targets_protected:
            if os.environ.get("ALLOW_PROTECTED_BRANCH_PUSH") == "1":
                _audit(hook="dangerous-command-blocker", decision="bypass",
                       level="protected-branch", branch=branch, command=command[:300])
            else:
                _audit(hook="dangerous-command-blocker", decision="block",
                       level="protected-branch", branch=branch, command=command[:300])
                print(
                    f"BLOCKED: Direct push to protected branch ({branch or 'main/develop'}).\n"
                    "Use a feature branch and create a PR instead.\n"
                    "Bypass (rare, e.g. personal config repo): ALLOW_PROTECTED_BRANCH_PUSH=1.\n"
                    f"Command: {command}"
                )
                sys.exit(2)

    # Level 3: Suspicious (warn via stderr, allow)
    for pattern, reason in SUSPICIOUS:
        if re.search(pattern, command):
            print(f"WARNING: {reason}\nCommand: {command}", file=sys.stderr)
            break

    sys.exit(0)


if __name__ == "__main__":
    main()
