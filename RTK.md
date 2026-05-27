# RTK - Rust Token Killer

**Usage**: Token-optimized CLI proxy with 60 to 90 percent savings on dev operations.

## Meta Commands, always use rtk directly

```bash
rtk gain              # Show token savings analytics
rtk gain --history    # Show command usage history with savings
rtk discover          # Analyze Claude Code history for missed opportunities
rtk proxy <cmd>       # Execute raw command without filtering (for debugging)
```

## Installation Verification

```bash
rtk --version         # Should show: rtk X.Y.Z
rtk gain              # Should work (not "command not found")
which rtk             # Verify correct binary
```

**Name collision**: If `rtk gain` fails, you may have the `reachingforthejack/rtk` Rust Type Kit installed instead.

## Hook-Based Usage

All other commands are automatically rewritten by the Claude Code hook.
Example: `git status` becomes `rtk git status`, transparent with zero tokens overhead.

Refer to CLAUDE.md for full command reference.
