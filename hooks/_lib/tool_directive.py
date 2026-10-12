from __future__ import annotations

import re

TOOL_DIRECTIVE = re.compile(
    r"""^(?:
        eslint- (?: disable | enable ) \b
      | eslint-env \b
      | eslint \s+ [\w@/-]+ \s* :
      | oxlint- (?: disable | enable ) \b
      | biome-ignore \b
      | prettier-ignore \b
      | stylelint- (?: disable | enable ) \b
      | deno- (?: lint | fmt ) -ignore \b
      | tslint:
      | jshint \s
      | jslint \s
      | @ts- (?: expect-error | ignore | nocheck | check ) \b
      | @jsx \w* \b
      | @flow \b
      | @ (?: jest | vitest ) -environment \b
      | @formatter: \s* (?: off | on ) \b
      | / \s* <reference \b
      | \#\s* source (?: MappingURL | URL ) =
      | \#__ (?: PURE | NO_SIDE_EFFECTS ) __
      | (?-i: \# \s* (?: LANGUAGE | OPTIONS_GHC | OPTIONS_HADDOCK | INLINE | NOINLINE
          | INLINABLE | SPECIALI[SZ]E | UNPACK | NOUNPACK | COMPLETE | MINIMAL
          | OVERLAPP (?: ING | ABLE | S ) | INCOHERENT | DEPRECATED | WARNING
          | SOURCE | RULES | ANN | SCC ) \b )
      | webpack (?: ChunkName | Ignore | Mode | Prefetch | Preload ) \b
      | (?: @ )? vite-ignore \b
      | svelte-ignore \b
      | istanbul \s+ ignore \b
      | [cv]8 \s+ ignore \b
      | go: (?: build | generate | embed | linkname | noinline | nosplit ) \b
      | \+build \b
      | nolint \b
      | NOLINT (?: NEXTLINE | BEGIN | END ) \b
      | clang-format \s+ (?: off | on ) \b
      | swiftlint: (?: disable | enable ) \b
      | swiftformat:
      | ktlint- (?: disable | enable ) \b
      | detekt:
      | solhint- (?: disable | enable ) \b
      | buf:lint:ignore \b
      | NOPMD \b
      | NOSONAR \b
      | CHECKSTYLE: (?: OFF | ON ) \b
      | noinspection \b
      | ReSharper \s+ (?: disable | restore ) \b
      | ignore (?: _for_file )? : \s* \S
      | noqa \s* (?: : \s* \S+ )? \s* $
      | nosec \b (?: \s+ B\d+ )* \s* $
      | type: \s* ignore \b
      | pragma: \s* \S
      | mypy:
      | pyright:
      | ruff:
      | flake8:
      | pylint: \s* (?: disable | enable | skip-file ) \b
      | fmt: \s* (?: off | on | skip ) \b
      | yapf: \s* (?: disable | enable ) \b
      | isort:
      | coverage: \s* ignore \b
      | (?: en )? coding [:=] \s* [-\w.]+ \s* $
      | shellcheck \s+ (?: disable | enable | shell | source | source-path
          | external-sources ) \b
      | shfmt:
      | -\*- \s* coding: \s* \S
      | SAFETY:
      | SPDX- [\w-]+ :
      | REUSE-Ignore (?: Start | End ) \b
      | cSpell:
      | spell-checker:
      | codespell:
      | gitleaks:allow \b
      | editorconfig-checker- (?: disable | enable ) \b
      | yaml-language-server: \s
      | yamllint \s+ (?: disable | enable ) \b
      | zizmor: \s* ignore \b
      | renovate: \s
      | hadolint \s+ (?: ignore | shell | global ) \b
      | (?: syntax | escape | check ) = \S
      | tflint-ignore \b
      | tfsec: \s* ignore \b
      | checkov: \s* skip \b
      | trivy: \s* ignore \b
      | kics-scan \s
      | sqlfluff:
      | squawk-ignore \b
      | name: \s* \w+ \s+ :\w+
      | \+goose \s+ \w+
      | \+migrate \s+ (?: Up | Down | StatementBegin | StatementEnd ) \b
      | migrate: (?: up | down ) \b
      | luacheck:
      | stylua: \s* ignore \b
      | -? @diagnostic \s+ (?: disable | enable )
      | credo: (?: disable | enable ) \b
      | rubocop: (?: disable | enable | todo ) \b
      | (?: frozen_string_literal | warn_indent | shareable_constant_value ) : \s* \S
      | \# \s* (?: no | use ) \s+ critic \b
      | (?: <<< | >>> ) \s* $
      | requires \s+ -
      | styler: \s* (?: off | on ) \b
      | ! \s* format: \s* (?: off | on ) \b
      | :schema \s
      | taplo:
      | cmake- (?: format | lint ) :
      | buildifier: \s* (?: disable | leave-alone ) \b
      | v \d+ (?: \.\d+ )* (?: [-+][\w.]+ )? \s* $
      | \d+ \.\d+ (?: \.\d+ )* (?: [-+][\w.]+ )? \s* $
      | \#ok \b
      | \#function \s
      | (?: vim? | ex ) : \s* (?: set? \s | \w+ = )
    )""",
    re.VERBOSE | re.IGNORECASE,
)
