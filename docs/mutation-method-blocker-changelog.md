# mutation-method-blocker changelog

All notable changes to the `hooks/mutation-method-blocker.py` hook and its supporting scripts. Format loosely follows Keep a Changelog. Detector codes MMB000-MMB092 are stable across versions; new codes are appended, never renumbered.

## [3.0.0-dev] - 2026-05-11

### Added

- `scripts/mutation_version.py` as the single source of truth for `VERSION`, `SARIF_SCHEMA_VERSION`, and `LSP_SCHEMA_VERSION`. Three call sites updated to import the constant.
- `hooks/i18n/ja.json` Japanese locale bundle, matching the `en.json` schema.
- CLI introspection flags on `hooks/mutation-method-blocker.py`:
  - `--version` and `-V`: print the version string.
  - `--print-detectors`: emit a JSON document listing every active MMB code.
  - `--list-allowlists`: emit a JSON document dumping the framework, hot-path, and scope allowlists for debugging.
- Spec folder under `specs/2026-05-11-mutation-method-blocker-state-of-art/` with `context.md`, `plan.md` covering 165 items across phases A through N, `decisions.md` recording eight ADRs, and `references.md` listing research links.

### Changed

- `hooks/mutation-method-blocker.py`, `hooks/sarif_emitter.py`, and `hooks/lsp_emitter.py` consume `mutation_version.VERSION` instead of hard-coding their own string.

### Detector codes (stable, no renumbering)

- MMB000-MMB092 remain unchanged. Phase B of the v3 plan reserves MMB093-MMB120 for the new detector surfaces: Temporal mutation, Upsert receivers, `using` / `await using` misuse, AsyncIterator helpers, URLSearchParams / Headers / FormData hardening, cross-statement antipatterns, IndexedDB scope boundary.

## [2.3.0] - 2026-04 (snapshot before v3 plan)

### Summary

- 92 stable detector codes MMB001-MMB092 across 16 categories.
- 13 supporting scripts, roughly 5,862 LOC, plus 39 test modules around 16,240 LOC.
- TypeScript Project Service integration via `scripts/mutation_ts_project_service.py` plus a Node helper.
- SARIF 2.1.0 and LSP 3.17 emitters as separate modules.
- Suppression budget enforcement via `scripts/mutation_budget_check.py`.
- Detector tuning report via `scripts/detector_tuning_report.py`.
- Five locale bundles: `en`, `pt-BR`, `es`, `fr`, `de`.

## [2.0.0] - 2026-01

### Summary

- Refactored the original 700-line monolith into `hooks/mutation-method-blocker.py` plus modular detectors under `scripts/mutation_detectors_*.py`.
- Added framework auto-allow scopes for Immer, Mutative, Redux Toolkit, Pinia, MobX, Zustand, Valtio, Jotai, Recoil, XState, Solid stores, Effect-TS, Nanostores, LegendApp, TanStack Store, Yjs, Vue 3.5, Svelte 5.
- Added hot-path directory auto-allows for crypto, codec, image, audio, parser, wasm, canvas, encoder, decoder, simd, webgl, pixel, hash, cipher, dsp, signal, fft, ml, tensor.

## [1.0.0] - 2025

### Summary

- Initial release. Single regex-based detector for the nine mutating Array prototype methods: `push`, `pop`, `shift`, `unshift`, `splice`, `sort`, `reverse`, `fill`, `copyWithin`.
