# i18n Regional Variants

## Core Problem

Languages spoken in multiple countries have regional differences. "Colour" is British English, "color" is American English. "Autocarro" is Portuguese from Portugal, "onibus" is Brazilian Portuguese. "Ordenador" is Spanish from Spain, "computadora" is Mexican Spanish. Using the wrong regional variant is incorrect, not a style preference.

## Rule

Every translation file must use the correct regional variant for its target locale. A `pt-BR.json` file must use Brazilian Portuguese vocabulary, not European Portuguese. An `en.json` targeting US users must use American English spelling.

## Regional Variant Differences

### English: en-US vs en-GB

| Category | en-US | en-GB |
|----------|-------|-------|
| Spelling -or/-our | color, favor, honor | colour, favour, honour |
| Spelling -ize/-ise | organize, customize | organise, customise |
| Spelling -er/-re | center, meter, fiber | centre, metre, fibre |
| Spelling -og/-ogue | catalog, dialog | catalogue, dialogue |
| Spelling -ense/-ence | license, defense | licence, defence |
| Vocabulary | apartment, elevator, truck | flat, lift, lorry |
| Date format | MM/DD/YYYY | DD/MM/YYYY |

### Portuguese: pt-BR vs pt-PT

| Category | pt-BR | pt-PT |
|----------|-------|-------|
| Gerund vs infinitive | "estou fazendo" | "estou a fazer" |
| Vocabulary | onibus, celular, tela, arquivo | autocarro, telemovel, ecra, ficheiro |
| Vocabulary | mouse, deletar, salvar | rato, apagar, guardar |
| Pronoun placement | "me diga" (before verb) | "diga-me" (after verb) |
| Address | "voce" (informal) | "voce" (formal) or "tu" |
| Tech terms | computador, download, site | computador, transferencia, sitio |

### Spanish: es-MX/es-AR vs es-ES

| Category | es-MX/Latin America | es-ES |
|----------|---------------------|-------|
| Vocabulary | computadora, celular, carro | ordenador, movil, coche |
| Vocabulary | platicar, manejar, boleto | charlar, conducir, billete |
| "You" informal | "ustedes" (always) | "vosotros" (plural informal) |
| Past tense preference | preterite: "hable" | present perfect: "he hablado" |
| Tech terms | aplicacion, correo, enlace | aplicacion, correo, enlace (mostly same) |

## Verification Strategy

### Tier 1: Curated flagged word lists (mandatory)

Maintain a list of words that belong to the WRONG variant for each locale. Add these to the project's linting configuration.

For a `pt-BR` project, flag pt-PT words:

```json
{
  "flagWords": ["autocarro", "telemovel", "ecra", "ficheiro", "guardar", "apagar", "sitio", "diga-me", "estou a fazer"]
}
```

For an `en-US` project, flag en-GB words:

```json
{
  "flagWords": ["colour", "favour", "honour", "organise", "customise", "centre", "metre", "catalogue", "licence", "defence"]
}
```

For an `es` project targeting Latin America, flag es-ES words:

```json
{
  "flagWords": ["ordenador", "movil", "coche", "vosotros", "habeis", "conducir"]
}
```

### Tier 2: Dictionary-based verification (recommended)

Use Hunspell dictionaries via `nspell` or `cspell` to validate words against the correct regional dictionary.

**Tools:**

| Tool | Purpose | Install |
|------|---------|---------|
| `cspell` | CLI spellchecker with per-file locale overrides | `pnpm add -D cspell` |
| `@cspell/dict-pt-br` | Brazilian Portuguese dictionary | `pnpm add -D @cspell/dict-pt-br` |
| `@cspell/dict-en-gb` | British English dictionary (for flagging) | `pnpm add -D @cspell/dict-en-gb` |
| `@cspell/dict-es-es` | Spanish dictionary | `pnpm add -D @cspell/dict-es-es` |
| `nspell` | Programmatic Hunspell spellchecker | `pnpm add -D nspell` |
| `dictionary-pt` | Brazilian Portuguese Hunspell dict | `pnpm add -D dictionary-pt` |
| `dictionary-pt-pt` | European Portuguese Hunspell dict | `pnpm add -D dictionary-pt-pt` |
| `dictionary-en` | American English Hunspell dict | `pnpm add -D dictionary-en` |
| `dictionary-en-gb` | British English Hunspell dict | `pnpm add -D dictionary-en-gb` |

**Approach:** Load two regional dictionaries for the same language via `nspell`. A word that is valid in pt-PT but invalid in pt-BR is a pt-PT-only word. Flag it in `pt-BR.json` files.

### Tier 3: Custom validation script (for CI)

Write a test or lint script that:

1. Extracts all string values from each `messages/{locale}.json` file
2. Tokenizes them into words
3. Checks each word against the curated flagged word list (Tier 1)
4. Optionally checks against the regional dictionary (Tier 2)
5. Fails if any word from the wrong variant is found

Example test structure:

```typescript
describe('i18n regional variants', () => {
  it('pt-BR translations must not contain pt-PT words', () => {
    const ptBR = loadMessages('pt-BR');
    const flagged = checkForFlaggedWords(ptBR, PT_PT_FLAG_LIST);
    expect(flagged).toEqual([]);
  });
});
```

## Process for New Translations

1. Identify the target locale's regional variant (e.g., pt-BR, not generic pt)
2. Write translations using the correct regional vocabulary, grammar, and spelling
3. Run accent verification (see `rules/code-style.md` section "i18n Accent and Diacritical Marks")
4. Run regional variant check against the flagged word list
5. For uncertain words, verify against the regional dictionary or native speaker review

## When to Use Generic vs Regional

- File naming: always use the regional variant code. `pt-BR.json`, not `pt.json`. `en-US.json` or `en.json` with a documented assumption of which variant
- When a project supports only one variant of a language, document which variant in the project's CLAUDE.md or i18n config
- When a project supports multiple variants of the same language (e.g., pt-BR and pt-PT), each must have its own file with correct regional vocabulary

## Common Mistakes

| Mistake | Why it happens | How to catch |
|---------|---------------|-------------|
| Machine translation produces generic Portuguese | Translation tools default to the most common form | Flagged word list + human review |
| British spelling in US-targeted app | Developer or AI is British English native | cspell with en-US dictionary + flagWords for en-GB |
| Spain Spanish in Latin American app | Default Spanish resources tend to be es-ES | Flagged word list for vosotros, ordenador, movil |
| Missing accents on regional-specific words | Copy-paste from ASCII-only sources | Accent verification tests |
