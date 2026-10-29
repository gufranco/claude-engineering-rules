# Emulator Runs

## Scope

Loaded on demand before launching MAME, mednafen, ares, Snes9x, or any other emulator, whether from a shell, a script, a test harness, or a subagent.

## Core Rule

The user works while emulator runs happen. An emulator that takes the display, steals focus, or plays sound stops that work. A scripted run therefore shows nothing and plays nothing, and a run the user asked to watch stays windowed and minimised.

## Mandatory Targets

| Situation | Rule |
|---|---|
| Scripted run, output is a file | Headless: no window, no sound |
| User asked to watch | Windowed, never maximised, minimised after launch |
| Full screen | Never, in any situation |
| Choosing the emulator for evidence | Prefer mednafen, ares or Snes9x over MAME |
| A result only MAME showed | Corroborate it on a second emulator before reporting it |
| A new emulator or GUI tool | Read its default window mode before the first launch |

## Per-Emulator Flags

| Emulator | Headless | Watched |
|---|---|---|
| MAME | `SDL_VIDEODRIVER=dummy mame -window -video none -sound none` | `MAME_WATCHED=1 mame -window -nomaximize` |
| mednafen | `SDL_VIDEODRIVER=dummy mednafen -sound 0` | windowed by default; never pass `-video.fs 1` |
| ares, Snes9x | GUI applications; launch only when the user asks to watch | open with `open -g` so focus stays put, then minimise |

On macOS MAME defaults to full screen. Its `-video none` still creates an SDL window, and so does adding `-window`; only `SDL_VIDEODRIVER=dummy` prevents it. A `mame.ini` in the working directory carrying `window 1`, `maximize 0`, `video none` and `sound none` is a backstop for scripts that build their own command line.

MAME writes snapshots, configuration, NVRAM and saved states under its working directory, as `snap/`, `cfg/`, `nvram/` and `sta/`. A scripted run started from inside a repository leaves a screenshot of the cartridge there, untracked, one `git add -A` away from being committed. Run it from a scratch directory and pass `-snapshot_directory`, `-cfg_directory`, `-nvram_directory` and `-state_directory` pointing inside that directory.

## Why MAME Is Not The First Witness

MAME runs a system through its BIOS and its own configuration defaults: the BIOS it selects, the region, the slot device and the ini files it finds on the search path. A wrong default produces a failure that is the configuration's, or a pass that the hardware would not give. Prefer an emulator that runs the cartridge directly, and treat a MAME-only result as unconfirmed until a second emulator agrees.

## Enforcement

[`hooks/interactive-cmd-blocker.py`](../hooks/interactive-cmd-blocker.py) blocks a shell launch of `mame` that would open a window: one without `-window`, a headless run missing `SDL_VIDEODRIVER=dummy`, `-video none` or `-sound none`, and a watched run without `-nomaximize`. Informational commands such as `-listxml` and `-verifyroms` pass. It cannot see an emulator started from inside a Python or shell script; that launch follows this standard by hand.
