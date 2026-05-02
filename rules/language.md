# Language

## Absolute Rule

**Respond in English. Always. Without exception.**

This rule is enforced by `hooks/english-only-reminder.sh`, which injects a system-reminder on every user prompt. It is also restated in `CLAUDE.md` and reinforced here. Three layers because past sessions drifted into Portuguese when the user wrote in Portuguese.

## Specifics

- Every assistant message: English.
- Every tool call description: English.
- Every code comment, commit message, PR title and body, review comment, branch name: English.
- Every file you author, including spec folders, ADRs, and READMEs: English.

## Behavior When User Writes in Another Language

- The user may write in Portuguese, Spanish, French, German, or any other language. Your reply is still in English.
- Do not mirror the user's language. Do not switch mid-response. Do not translate the user's message back to them.
- Do not apologize for replying in English. Do not ask permission. Just answer.

## Self-Check Before Sending

Before every response, scan the draft for non-English words or phrases. Common drift points:

- Acknowledgments: "Pronto", "Feito", "Beleza" → "Done", "Ready"
- Connectors: "Faz sentido", "Vou fazer", "Aqui está" → "Makes sense", "On it", "Here"
- Tool descriptions: "Verificar diff", "Criar commit" → "Check diff", "Create commit"

If any non-English text appears, rewrite before sending.

## Why This Rule Exists

The user is Brazilian and writes in Portuguese for speed. They consume technical output in English (PR descriptions, commit messages, documentation read by international teammates and tooling). Mixed-language output forces them to translate before sharing. English-only output is shareable as-is.
