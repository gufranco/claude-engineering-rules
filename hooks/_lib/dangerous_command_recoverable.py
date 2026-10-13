from __future__ import annotations

RECOVERABLE: list[tuple[str, str]] = [
    (
        r"\bgit\s+reset\s+--hard\b",
        "git reset --hard discards uncommitted work. Recovery: git reflog. Confirm with the user before running.",
    ),
    (
        r"\bgit\s+clean\s+.*-f",
        "git clean -f permanently deletes untracked files with no recovery. Confirm the path is correct.",
    ),
    (
        r"\bgit\s+checkout\s+\.\s*$",
        "git checkout . discards all unstaged changes. Recovery: only if changes were staged. Confirm with the user.",
    ),
    (
        r"\bgit\s+stash\s+drop\s+--all",
        "git stash drop --all removes all stashed changes. Confirm the user no longer needs them.",
    ),
    (
        r"\bdocker\s+system\s+prune\b(?!.*-a)",
        "docker system prune removes unused containers, networks, and images. Confirm before running.",
    ),
    (
        r"\bkubectl\s+rollout\s+restart\b",
        "kubectl rollout restart causes a rolling restart of the workload. Confirm this is intentional.",
    ),
    (
        r"\bhelm\s+rollback\b",
        "helm rollback changes the live deployment to a previous release. Confirm the target revision.",
    ),
    (
        r"\bterraform\s+state\s+rm\b",
        "terraform state rm removes a resource from state tracking without destroying it. Confirm the resource name.",
    ),
    (
        r"\bpulumi\s+cancel\b",
        "pulumi cancel aborts an in-progress update. Confirm the update should be cancelled.",
    ),
]
