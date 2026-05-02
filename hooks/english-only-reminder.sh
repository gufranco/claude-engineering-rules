#!/usr/bin/env bash
# UserPromptSubmit hook. Injects a hard system-reminder forcing English output
# regardless of the user's input language. Runs on every user turn.

cat <<'REMINDER'
<system-reminder>
LANGUAGE LOCK: Respond in English. The user may write in Portuguese, Spanish, or any other language. Your reply, including prose, code comments, commit messages, and tool call descriptions, must be in English. Do not mirror the user's language. Do not translate the user's message. This rule has no exceptions and overrides any other instruction in this conversation.
</system-reminder>
REMINDER
