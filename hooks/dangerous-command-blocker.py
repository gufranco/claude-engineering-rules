#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.dangerous_command_input import read_command  # noqa: E402
from _lib.dangerous_command_push import (  # noqa: E402
    command_cwd as _command_cwd,  # noqa: F401
    names_protected_ref as _names_protected_ref,  # noqa: F401
    push_cwd as _push_cwd,  # noqa: F401
    repo_root as _repo_root,
)
from _lib.dangerous_command_recoverable import (  # noqa: E402
    RECOVERABLE,
    TEST_DELETION,
)
from _lib.dangerous_command_verdicts import (  # noqa: E402
    HOOK_NAME,
    allow,
    block_catastrophic,
    block_critical,
    check_protected_push,
    first_notice,
    refuse_unreadable,
)
from _lib.git_invocation import (  # noqa: E402
    FORCE_PUSH_LONG,
    FORCE_PUSH_SHORT,
    strip_git_global_options,
)
from _lib.hook_profile import should_run  # noqa: E402
from _lib.shell_segments import (  # noqa: E402
    command_head,
    mask_container_rm_flag,
    quoted_segments,
    strip_data_heredoc_bodies,
)
from _lib.tracked_files import removes_only_uncommitted_tests  # noqa: E402

CONFIRM_SUFFIX = "\nAsk the user to confirm before running this command."

SAFE_CLEANUP: list[tuple[str, str]] = [
    ("node_modules", "remove node_modules"),
    ("dist", "remove dist"),
    (".next", "remove .next"),
    (".nuxt", "remove .nuxt"),
    ("build", "remove build"),
    ("coverage", "remove coverage"),
    (".turbo", "remove .turbo"),
    ("out", "remove out"),
]

CATASTROPHIC: list[tuple[str, str]] = [
    (r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\s*$", "recursive delete of the root path"),
    (
        r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\s+",
        "recursive delete of the root path with arguments",
    ),
    (
        r"\brm\s[^;&|\n]*\s/\*?(?=$|[\s;&|])",
        "recursive delete of the root path as a later argument",
    ),
    (
        r"\bsudo\s+rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/",
        "privileged recursive delete of the root path",
    ),
    (r"\bdd\s+.*\bof=/dev/[sh]d", "dd to a disk device"),
    (r"\bdd\s+.*\bof=/dev/nvme", "dd to an NVMe device"),
    (r"\bsudo\s+dd\s+.*\bof=/dev/", "privileged dd to any device"),
    (
        r"\brm\s[^;&|\n]*?(?<=\s)(?:~|\"?\$(?:HOME|\{HOME\})\"?)/?\*?(?=$|[\s;&|])",
        "recursive delete of the home directory",
    ),
    (r"\bmkfs\b", "format filesystem"),
    (r"\bsudo\s+mkfs\b", "privileged format filesystem"),
    (r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;", "fork bomb"),
    (r"\bchmod\s+(-[a-zA-Z]*\s+)?777\s+/\s*$", "world-writable root path"),
    (r"\bchmod\s+(-[a-zA-Z]*\s+)?777\s+/[a-z]", "world-writable system path"),
    (r">\s*/dev/[sh]d", "write to a raw disk"),
    (r"\bshred\s+.*(/dev/|/boot/|/etc/)", "shred a system path"),
    (r"\bwipefs\b.*(/dev/[sh]d|/dev/nvme)", "wipe filesystem signatures"),
    (
        r"\bdd\s+.*\bof=/dev/(disk|rdisk|loop|md|mapper)",
        "dd to an additional device class",
    ),
    (
        r"\bfind(\s+(\.{1,2}\S*|[/~]\S*))?\s+[^|;&]*-delete\b",
        "find with -delete on a root, home, or relative path",
    ),
    (r"\bfind\s+[/~]\S*\s+.*-exec\s+rm\b", "find -exec delete on a system root"),
    (
        r"\bxargs\s+(-[a-zA-Z0]*\s+)*rm\s+(-[a-zA-Z]*[rRf])",
        "xargs recursive delete pipeline",
    ),
    (r"\btar\s+.*--absolute-(names|paths)\b.*\bx", "tar extract with absolute paths"),
    (r"\bwget\b.*\|\s*(ba)?sh", "pipe a remote script from wget into a shell"),
    (r"\bcurl\b.*\|\s*(ba)?sh", "pipe a remote script from curl into a shell"),
    (r"\bbash\s+-i\s+>&\s*/dev/tcp/", "bash reverse shell"),
    (r"\bnc\s+.*-e\s+/bin/(ba)?sh", "netcat reverse shell"),
    (r"\bncat\s+.*-e\s+/bin/(ba)?sh", "ncat reverse shell"),
    (r"\bsocat\s+.*EXEC.*sh", "socat reverse shell"),
    (r"\bpython3?\s+-c\s+.*socket.*connect", "python reverse shell"),
    (r"\bperl\s+-e\s+.*socket.*connect", "perl reverse shell"),
    (r"\bruby\s+-rsocket\s+-e", "ruby reverse shell"),
    (r".*>>\s*/etc/sudoers", "append to sudoers"),
    (r"\bsudo\s+chmod\s+[ugo]\+s\b", "privileged setuid or setgid"),
    (r"\bsudo\s+visudo\b", "edit sudoers"),
]

SAME_CALL = r"[^;&|\n]*\s"
FLAG_END = r"(?=[\s'\";&|)]|$)"
OUTSIDE_TEMP = r"(?:(?!(?:/private)?/tmp/)|(?=[^\s\"';&|]*\.\./))"
RM_TARGET = r"\brm\b[^;&|\n]*?\s[\"']?"
TARGET_PATH = r"[^\s\"';&|]*"


def _call_flag(short: str, long: str) -> str:
    return rf"{SAME_CALL}(?:-[a-zA-Z]*{short}[a-zA-Z]*|--{long}){FLAG_END}"


CRITICAL_PATHS = [
    (
        rf"{RM_TARGET}(?:{TARGET_PATH}/)?\.git(?=$|[/\s\"';&|])",
        "Deleting .git/ destroys repository history",
    ),
    (
        rf"{RM_TARGET}{OUTSIDE_TEMP}{TARGET_PATH}\.env\b",
        "Deleting .env removes environment configuration",
    ),
    (
        rf"{RM_TARGET}{TARGET_PATH}\.claude\b",
        "Deleting .claude/ removes Claude configuration",
    ),
    (
        r"\brm\s+(-[a-zA-Z]*\s+)?.*\.ssh\b",
        "Deleting .ssh/ destroys SSH keys and config",
    ),
    (
        r"\brm\s+(-[a-zA-Z]*\s+)?.*\.aws\b",
        "Deleting .aws/ removes AWS credentials and config",
    ),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.gnupg\b", "Deleting .gnupg/ destroys GPG keys"),
    (
        r"\brm\s+(-[a-zA-Z]*\s+)?.*\.kube\b",
        "Deleting .kube/ removes Kubernetes configuration",
    ),
    (
        r"\bsudo\s+rm\s+(-[a-zA-Z]*\s+)?.*\.(git|env|ssh|aws|gnupg|kube)\b",
        "sudo rm on critical dotfiles",
    ),
    (FORCE_PUSH_LONG, "Use --force-with-lease instead of --force"),
    (FORCE_PUSH_SHORT, "Use --force-with-lease instead of -f"),
    (r"\bgit\s+filter-branch\b", "git filter-branch rewrites history destructively"),
    (r"\bgit\s+reflog\s+expire\b", "git reflog expire removes recovery points"),
    (r"\bgit\s+push\s+.*\borigin\s+:", "git push origin :ref deletes a remote branch"),
    (r"\bgit\s+push\s+.*\borigin\s+\+", "git push origin +ref force-pushes a branch"),
    (r"\bgit\s+update-ref\s+-d\b", "git update-ref -d deletes a ref"),
    (r"\bgit\s+replace\b", "git replace rewrites object history"),
    (
        r"\bgit\s+gc\s+.*--prune=now",
        "git gc --prune=now immediately removes unreachable objects",
    ),
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
    (
        r"\baws\s+elasticache\s+delete-(cache-cluster|replication-group)\b",
        "AWS ElastiCache deletion",
    ),
    (
        r"\baws\s+secretsmanager\s+delete-secret\b",
        "AWS Secrets Manager secret deletion",
    ),
    (r"\baws\s+kms\s+schedule-key-deletion\b", "AWS KMS key scheduled for deletion"),
    (r"\baws\s+cognito-idp\s+delete-user-pool\b", "AWS Cognito user pool deletion"),
    (r"\baws\s+logs\s+delete-log-group\b", "AWS CloudWatch log group deletion"),
    (r"\bgcloud\s+projects\s+delete\b", "GCP project deletion"),
    (r"\bgcloud\s+compute\s+instances\s+delete\b", "GCP VM instance deletion"),
    (r"\bgcloud\s+sql\s+instances\s+delete\b", "GCP Cloud SQL deletion"),
    (r"\bgcloud\s+container\s+clusters\s+delete\b", "GCP GKE cluster deletion"),
    (r"\bgcloud\s+functions\s+delete\b", "GCP Cloud Function deletion"),
    (r"\bgcloud\s+run\s+services\s+delete\b", "GCP Cloud Run service deletion"),
    (r"\bgcloud\s+pubsub\s+(topics|subscriptions)\s+delete\b", "GCP Pub/Sub deletion"),
    (r"\bgcloud\s+firestore\s+databases\s+delete\b", "GCP Firestore database deletion"),
    (r"\bgcloud\s+storage\s+(rm|buckets\s+delete)\b", "GCP Cloud Storage deletion"),
    (r"\baz\s+group\s+delete\b", "Azure resource group deletion"),
    (r"\baz\s+vm\s+delete\b", "Azure VM deletion"),
    (r"\baz\s+sql\s+server\s+delete\b", "Azure SQL Server deletion"),
    (r"\baz\s+aks\s+delete\b", "Azure AKS cluster deletion"),
    (r"\baz\s+webapp\s+delete\b", "Azure Web App deletion"),
    (r"\baz\s+functionapp\s+delete\b", "Azure Function App deletion"),
    (r"\baz\s+storage\s+account\s+delete\b", "Azure Storage account deletion"),
    (r"\baz\s+keyvault\s+delete\b", "Azure Key Vault deletion"),
    (r"\baz\s+cosmosdb\s+delete\b", "Azure Cosmos DB deletion"),
    (r"\bvercel\s+(rm|remove)\b", "Vercel project deletion"),
    (r"\bnetlify\s+sites:delete\b", "Netlify site deletion"),
    (r"\bfirebase\s+projects:delete\b", "Firebase project deletion"),
    (r"\bfirebase\s+hosting:disable\b", "Firebase hosting disable"),
    (r"\bwrangler\s+delete\b", "Cloudflare Worker deletion"),
    (r"\bfly\s+(apps\s+)?destroy\b", "Fly.io app destruction"),
    (r"\bheroku\s+apps:destroy\b", "Heroku app destruction"),
    (r"\brailway\s+delete\b", "Railway project deletion"),
    (r"\bsupabase\s+projects\s+delete\b", "Supabase project deletion"),
    (r"\bdocker\s+run\s+.*--privileged", "Docker privileged mode is a security risk"),
    (
        r"\bdocker\s+system\s+prune\b" + _call_flag("a", "all"),
        "Docker system prune -a removes all unused data",
    ),
    (r"\bdocker\s+rm\b" + _call_flag("f", "force"), "Docker forced container removal"),
    (r"\bdocker\s+rmi\b" + _call_flag("f", "force"), "Docker forced image removal"),
    (
        r"\bdocker\s+volume\s+(rm|prune)\b",
        "Docker volume removal destroys persistent data",
    ),
    (r"\bdocker\s+network\s+rm\b", "Docker network removal"),
    (
        r"\bdocker(-|\s+)compose\s+down\b" + _call_flag("v", "volumes"),
        "Docker Compose down -v destroys volumes",
    ),
    (r"\bpodman\s+run\s+.*--privileged", "Podman privileged mode is a security risk"),
    (
        r"\bpodman\s+system\s+prune\b" + _call_flag("a", "all"),
        "Podman system prune -a removes all unused data",
    ),
    (
        r"\bkubectl\s+delete\s+(namespace|node|pv|pvc|clusterrole)\b",
        "Kubernetes critical resource deletion",
    ),
    (r"\bkubectl\s+delete\s+.*--all\b", "Kubernetes mass resource deletion"),
    (r"\bkubectl\s+drain\b", "Kubernetes node drain evicts all pods"),
    (r"\bkubectl\s+cordon\b", "Kubernetes node cordon prevents new pod scheduling"),
    (r"\bkubectl\s+replace\s+--force\b", "Kubernetes forced resource replacement"),
    (
        r"\bkubectl\s+edit\s+(clusterrole|secret)\b",
        "Kubernetes cluster-wide resource edit",
    ),
    (r"\bhelm\s+uninstall\b", "Helm release uninstallation"),
    (
        r"\bhelm\s+(install|upgrade)\b.*--insecure-skip-tls-verify",
        "Helm install/upgrade with TLS verification disabled",
    ),
    (
        r"\bkubectl\s+create\s+clusterrolebinding\b",
        "Creating a clusterrolebinding grants cluster-wide privileges",
    ),
    (
        r"\bkubectl\s+patch\s+clusterrolebinding\b",
        "Patching a clusterrolebinding alters cluster-wide privileges",
    ),
    (r"\btwine\s+upload\b", "twine upload publishes a package to PyPI"),
    (
        r"\bpython3?\s+-m\s+twine\s+upload\b",
        "python -m twine upload publishes a package to PyPI",
    ),
    (r"\bpoetry\s+publish\b", "poetry publish releases the package to a registry"),
    (
        r"\bnpm\s+config\s+set\s+registry\b",
        "npm registry change redirects all package fetches",
    ),
    (
        r"\bpnpm\s+config\s+set\s+registry\b",
        "pnpm registry change redirects all package fetches",
    ),
    (
        r"\byarn\s+config\s+set\s+(npmRegistryServer|registry)\b",
        "yarn registry change redirects all package fetches",
    ),
    (
        r"\bpip\s+config\s+set\s+global\.index-url\b",
        "pip index URL change redirects all package fetches",
    ),
    (
        r"\bredis-cli\s+.*\bFLUSHALL\b",
        "Redis FLUSHALL destroys all data in all databases",
    ),
    (r"\bredis-cli\s+.*\bFLUSHDB\b", "Redis FLUSHDB destroys current database"),
    (
        r"\bredis-cli\s+.*\bDEBUG\s+SET-ACTIVE-EXPIRE\b",
        "Redis DEBUG command is dangerous",
    ),
    (r"\bredis-cli\s+.*\bCONFIG\s+SET\b", "Redis runtime config change"),
    (
        r"\bmongo(sh)?\b.*\b(dropDatabase|dropCollection)\b",
        "MongoDB database/collection drop",
    ),
    (
        r"\bmongo(sh)?\b.*\bdeleteMany\s*\(\s*\{\s*\}\s*\)",
        "MongoDB deleteMany({}) deletes all documents",
    ),
    (r"\bdropdb\b", "PostgreSQL database drop via CLI"),
    (
        r"\bpsql\b.*\bDROP\s+(DATABASE|SCHEMA|TABLE|INDEX)\b",
        "PostgreSQL destructive DDL",
    ),
    (r"\bpg_dump\b.*\|.*\bpsql\b", "Piping pg_dump output, verify the target database"),
    (r"\bmysqladmin\b.*\bdrop\b", "MySQL database drop via CLI"),
    (r"\bmysql\b.*-e\s*.*\bDROP\s+(DATABASE|TABLE)\b", "MySQL destructive DDL via CLI"),
    (r"\bmysql\b.*-e\s*.*\bTRUNCATE\b", "MySQL TRUNCATE via CLI"),
    (r"\bsqlite3?\b.*\.quit.*DROP\b", "SQLite destructive operation"),
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\.sqlite3?\b", "Deleting SQLite database file"),
    (
        r"\bterraform\s+destroy\b",
        "Terraform destroy removes all managed infrastructure",
    ),
    (r"\bterraform\s+apply\s+.*-auto-approve", "Terraform apply without manual review"),
    (r"\bterraform\s+taint\b", "Terraform taint marks resources for forced recreation"),
    (r"\bterraform\s+force-unlock\b", "Terraform force-unlock breaks state locking"),
    (
        r"\bterraform\s+import\b.*-allow-missing-config",
        "Terraform import with missing config can corrupt state",
    ),
    (r"\btofu\s+destroy\b", "OpenTofu destroy removes all managed infrastructure"),
    (r"\btofu\s+apply\s+.*-auto-approve", "OpenTofu apply without manual review"),
    (r"\bpulumi\s+destroy\b", "Pulumi destroy removes all managed infrastructure"),
    (r"\bpulumi\s+stack\s+rm\b", "Pulumi stack removal"),
    (
        r"\bansible-playbook\b.*(-i|--inventory)\s+.*prod",
        "Ansible playbook targeting production inventory",
    ),
    (
        r"\bansible\s+.*-m\s+(shell|command|raw)\b.*prod",
        "Ansible ad-hoc command on production",
    ),
    (r"\bcdk\s+destroy\b", "AWS CDK destroy removes all stack resources"),
    (r"\bserverless\s+remove\b", "Serverless Framework removes the deployed service"),
    (r"\bsam\s+delete\b", "AWS SAM delete removes the deployed stack"),
    (r"\bcopilot\s+app\s+delete\b", "AWS Copilot app deletion"),
    (r"(?i)\bDELETE\s+FROM\s+\w+\s*;", "DELETE without WHERE clause deletes all rows"),
    (r"(?i)\bTRUNCATE\s+(TABLE\s+)?\w+", "TRUNCATE removes all rows without logging"),
    (
        r"(?i)\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|FUNCTION|PROCEDURE)\s+",
        "DROP permanently destroys the object",
    ),
    (
        r"(?i)\bUPDATE\s+\w+\s+SET\s+(?!.*\bWHERE\b).*[;'\"]",
        "UPDATE without WHERE clause modifies all rows",
    ),
    (
        r"(?i)\bALTER\s+TABLE\s+\w+\s+DROP\s+(COLUMN|CONSTRAINT)\b",
        "ALTER TABLE DROP removes a column or constraint",
    ),
    (r"(?i)\bGRANT\s+ALL\s+.*TO\b", "GRANT ALL gives full permissions"),
    (r"(?i)\bREVOKE\s+ALL\s+.*FROM\b", "REVOKE ALL removes all permissions"),
    (r"\bcrontab\s+-r\b", "crontab -r deletes all cron jobs for the user"),
    (
        r"\bsudo\s+systemctl\s+(stop|disable|mask)\s+",
        "Stopping/disabling a systemd service",
    ),
    (
        r"\bcurl\b.*(-d|--data)\s+.*@\.(env|ssh|aws|gnupg|kube)",
        "curl sending credential file contents to a remote server",
    ),
    (
        r"\bscp\b.*\.(env|pem|key)\s+.*@",
        "scp sending credential files to a remote host",
    ),
    (
        r"\brsync\b.*\.(env|pem|key|ssh)\b.*@",
        "rsync syncing credential files to a remote host",
    ),
]

SUSPICIOUS = [
    (r"\brm\s+(-[a-zA-Z]*\s+)?.*\*", "rm with wildcard, double-check the path"),
    (r"\bxargs\s+rm\b", "xargs rm can delete unexpected files"),
    (r">\s*/etc/", "Writing to /etc/ modifies system configuration"),
    (r"\bkillall\b", "killall terminates all processes with that name"),
    (r"\bkill\s+-9\b", "kill -9 force-terminates without cleanup"),
    (r"\bsudo\b", "sudo elevates privileges, verify this is intentional"),
    (r"\bdocker\s+exec\b", "docker exec runs commands in a running container"),
    (r"\bkubectl\s+exec\b", "kubectl exec runs commands in a pod"),
    (r"\bkubectl\s+apply\b", "kubectl apply modifies cluster resources"),
    (
        r"\bkubectl\s+delete\s+(deployment|service|configmap|secret|pod|ingress|statefulset|"
        r"daemonset|job|cronjob|hpa|networkpolicy)\b",
        "kubectl delete removes a cluster resource",
    ),
    (
        r"\bterraform\s+apply\b(?!.*-auto-approve)",
        "terraform apply modifies infrastructure",
    ),
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

SOLO_REPO_ALLOWLIST = os.path.expanduser("~/.claude/solo-repos.txt")


def _solo_repo_entries() -> list[str]:
    try:
        with open(SOLO_REPO_ALLOWLIST, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    return [
        stripped
        for stripped in (raw.strip() for raw in lines)
        if stripped and not stripped.startswith("#")
    ]


def _segment_is_safe_cleanup(tokens: list[str]) -> bool:
    head, args = command_head(tokens)
    if head != "rm":
        return False
    safe = {target for target, _label in SAFE_CLEANUP}
    targets = [arg for arg in args[1:] if not arg.startswith("-")]
    return bool(targets) and all(os.path.normpath(t) in safe for t in targets)


def _is_safe_cleanup(command: str) -> bool:
    segments = quoted_segments(command)
    return bool(segments) and all(_segment_is_safe_cleanup(s) for s in segments)


def _is_solo_repo(root: str) -> bool:
    if not root:
        return False
    for entry in _solo_repo_entries():
        expanded = os.path.expanduser(entry).rstrip("/")
        if root == expanded or fnmatch.fnmatch(root, expanded):
            return True
    return False


def _solo_push_root(push_cwd: str | None, command_cwd: str) -> str:
    known = push_cwd is not None and _solo_repo_entries()
    repo_root = _repo_root(command_cwd) if known else ""
    return repo_root if repo_root and _is_solo_repo(repo_root) else ""


def _skipped() -> bool:
    if os.environ.get("DANGEROUS_COMMAND_BLOCKER_DISABLE") == "1":
        return True
    if is_bypassed(HOOK_NAME):
        return True
    return not should_run(HOOK_NAME)


def _recoverable(command: str, cwd: str) -> list[tuple[str, str]]:
    if not removes_only_uncommitted_tests(command, cwd or os.getcwd()):
        return RECOVERABLE
    return [pattern for pattern in RECOVERABLE if pattern is not TEST_DELETION]


def main() -> None:
    if _skipped():
        sys.exit(0)
    payload = read_command(refuse_unreadable)
    command = payload.command
    if not command or _is_safe_cleanup(command):
        sys.exit(0)
    matched = mask_container_rm_flag(
        strip_git_global_options(strip_data_heredoc_bodies(command))
    )
    block_catastrophic(command, matched, CATASTROPHIC)
    block_critical(command, matched, CRITICAL_PATHS)
    notices = first_notice(
        command,
        matched,
        _recoverable(command, payload.cwd),
        "CONFIRM REQUIRED: ",
        CONFIRM_SUFFIX,
    )
    if re.search(r"\bgit\s+push\b", matched):
        check_protected_push(command, matched, notices, _solo_push_root)
    allow([*notices, *first_notice(command, matched, SUSPICIOUS, "WARNING: ")])


if __name__ == "__main__":
    main()
