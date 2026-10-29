# Language

## Absolute Rule

**Respond in English. Always. Without exception.**

This rule is enforced by [`hooks/english-only-reminder.py`](../hooks/english-only-reminder.py), which injects a system-reminder on every user prompt. It is also stated in the always-loaded core [`rules/language.md`](../rules/language.md) and in full here. Three layers because past sessions drifted into Portuguese when the user wrote in Portuguese.

## Specifics

- Every assistant message: English.
- Every tool call description: English.
- Every code comment, commit message, PR title and body, review comment, branch name: English.
- Every file you author, including spec folders, ADRs, and READMEs: English.
- One exception: a localized artifact the user asked for is written in its target language. That covers a `README.<tag>.md` produced by `/readme --languages` and the locale files of an internationalized app. Its English source stays English, and every message about it stays English.

## Behavior When User Writes in Another Language

- The user may write in Portuguese, Spanish, French, German, or any other language. Your reply is still in English.
- Do not mirror the user's language. Do not switch mid-response. Do not translate the user's message back to them.
- Do not apologize for replying in English. Do not ask permission. Just answer.

## Self-Check Before Sending

Before every response, scan the draft for non-English words or phrases. Common drift points:

- Acknowledgments: "Pronto", "Feito", "Beleza" become "Done", "Ready"
- Connectors: "Faz sentido", "Vou fazer", "Aqui está" become "Makes sense", "On it", "Here"
- Tool descriptions: "Verificar diff", "Criar commit" become "Check diff", "Create commit"

If any non-English text appears, rewrite before sending.

## Why This Rule Exists

A user may write in another language for speed while consuming technical output in English: PR descriptions, commit messages, documentation read by international teammates and tooling. Mixed-language output forces a translation before sharing. English-only output is shareable as-is.

## Enforcement

Enforced by: [`hooks/english-only-reminder.py`](../hooks/english-only-reminder.py).
