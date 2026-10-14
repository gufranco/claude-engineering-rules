from __future__ import annotations


HOOK = "redis-atomicity"


def _redis_write(tool_use, content: str):
    return tool_use(
        "Write", {"file_path": "/repo/src/services/counter.ts", "content": content}
    )
