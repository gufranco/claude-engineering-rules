# Emulator Runs

Applies to any launch of MAME or another emulator, from a shell, a script, or a test harness.

- Never open an emulator full screen. A scripted run is headless: no window, no sound.
- MAME headless is `SDL_VIDEODRIVER=dummy mame -window -video none -sound none`; `-video none` alone still opens a window on macOS.
- A run the user asked to watch opens windowed and minimised: `MAME_WATCHED=1 mame -window -nomaximize`, then minimise it.
- Prefer another emulator as evidence: mednafen, ares or Snes9x before MAME. MAME's BIOS and configuration defaults have produced failures and false positives.
- A result only MAME showed is corroborated on a second emulator before it is reported.

Full rule, per-emulator flags, and rationale: [`standards/emulator-runs.md`](../standards/emulator-runs.md). Read it before launching any emulator.

## Enforcement

Enforced by: [`hooks/interactive-cmd-blocker.py`](../hooks/interactive-cmd-blocker.py).
