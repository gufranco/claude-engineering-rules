#!/usr/bin/env bash
#
# auto-continue.sh - Monitors a tmux pane running Claude Code and
# automatically continues when rate limits or pause_turn events occur.
#
# Usage: auto-continue.sh <tmux-pane-id>
#
# The script polls the pane every POLL_INTERVAL seconds. When it detects
# a rate limit or tool-use pause, it takes the appropriate action:
#   - Rate limit: selects "Stop and wait", sleeps until reset, sends "Continue"
#   - Pause turn: sends "Continue" immediately
#
# Designed to be started by the claude() shell wrapper and to self-terminate
# when Claude Code exits.

# No set -e: a long-running monitor must not die on transient failures.
# Each operation handles its own errors.
set -u

################################################################################
# Configuration
################################################################################
POLL_INTERVAL=5
RATE_LIMIT_MARGIN=60
FALLBACK_WAIT_HOURS=5
LOG_FILE="/tmp/claude-auto-continue.log"

################################################################################
# Arguments
################################################################################
PANE="${1:-}"
if [[ -z "$PANE" ]]; then
  echo "Usage: auto-continue.sh <tmux-pane-id>" >&2
  exit 1
fi

################################################################################
# PID file (prevent duplicate monitors for the same pane)
################################################################################
PANE_SAFE="${PANE//[^a-zA-Z0-9]/_}"
PIDFILE="/tmp/claude-auto-continue-${PANE_SAFE}.pid"

cleanup() {
  rm -f "$PIDFILE"
}

crash_handler() {
  local line="$1"
  local code="$2"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] CRASH: pane=$PANE line=$line exit=$code" >> "$LOG_FILE"
  cleanup
}

trap cleanup EXIT
trap 'crash_handler ${LINENO} $?' ERR

if [[ -f "$PIDFILE" ]]; then
  existing_pid=$(cat "$PIDFILE" 2>/dev/null || true)
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    exit 0
  fi
fi

echo $$ > "$PIDFILE"

################################################################################
# Logging
################################################################################
log() {
  local ts
  ts=$(date "+%Y-%m-%d %H:%M:%S")
  echo "[$ts] $*" >> "$LOG_FILE"
}

################################################################################
# macOS notification
################################################################################
notify() {
  local msg="$1"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$msg\" with title \"Claude Code\"" 2>/dev/null || true
  fi
  log "NOTIFY: $msg"
}

################################################################################
# Capture tmux pane content
################################################################################
capture_pane() {
  tmux capture-pane -t "$PANE" -p 2>/dev/null || true
}

################################################################################
# Check if the pane still exists and runs a node/claude process
################################################################################
pane_alive() {
  if ! tmux has-session -t "$PANE" 2>/dev/null; then
    return 1
  fi

  local pane_pid
  pane_pid=$(tmux display-message -t "$PANE" -p '#{pane_pid}' 2>/dev/null || true)
  if [[ -z "$pane_pid" ]]; then
    return 1
  fi

  return 0
}

################################################################################
# Date parsing helper
#
# Uses GNU date -d (available via Homebrew coreutils) with fallback to
# BSD /bin/date -j for systems without GNU date.
################################################################################
parse_time_to_epoch() {
  local time_str="$1"

  # GNU date (preferred, handles "3pm", "3:30pm", "15:00" natively)
  local epoch
  epoch=$(date -d "$time_str" +%s 2>/dev/null || true)

  # Fallback: BSD date
  if [[ -z "$epoch" ]]; then
    local upper
    upper=$(echo "$time_str" | tr '[:lower:]' '[:upper:]')
    epoch=$(/bin/date -j -f "%I:%M%p" "$upper" +%s 2>/dev/null || true)
    if [[ -z "$epoch" ]]; then
      epoch=$(/bin/date -j -f "%I%p" "$upper" +%s 2>/dev/null || true)
    fi
    if [[ -z "$epoch" ]]; then
      epoch=$(/bin/date -j -f "%H:%M" "$time_str" +%s 2>/dev/null || true)
    fi
  fi

  if [[ -n "$epoch" ]]; then
    echo "$epoch"
    return 0
  fi

  return 1
}

################################################################################
# Parse reset time from pane content
#
# Matches patterns like:
#   "resets 3pm"
#   "resets 3:30pm"
#   "resets 3:30 pm"
#   "reset at 3pm"
#   "resets at 3:30pm"
#   "Resets 15:00"
################################################################################
parse_reset_time() {
  local content="$1"
  local raw_time

  # Try 12-hour format: "resets 3pm", "resets 3:30pm", "reset at 3:30 pm"
  raw_time=$(echo "$content" \
    | grep -oEi 'resets?\s*(at\s+)?[0-9]{1,2}(:[0-9]{2})?\s*(am|pm)' \
    | tail -1 \
    | grep -oEi '[0-9]{1,2}(:[0-9]{2})?\s*(am|pm)' \
    | tail -1 \
    | tr -d ' ')

  if [[ -z "$raw_time" ]]; then
    # Try 24-hour format: "resets 15:00"
    raw_time=$(echo "$content" \
      | grep -oEi 'resets?\s*(at\s+)?[0-9]{1,2}:[0-9]{2}' \
      | tail -1 \
      | grep -oE '[0-9]{1,2}:[0-9]{2}' \
      | tail -1)
  fi

  if [[ -z "$raw_time" ]]; then
    return 1
  fi

  local epoch
  epoch=$(parse_time_to_epoch "$raw_time" || true)

  if [[ -n "$epoch" ]]; then
    local now
    now=$(date +%s)

    # If the parsed time is in the past, it means tomorrow
    if (( epoch <= now )); then
      epoch=$((epoch + 86400))
    fi

    echo "$epoch"
    return 0
  fi

  return 1
}

################################################################################
# Detect rate limit menu
#
# Returns 0 if the Claude Code rate limit menu is showing.
# Only checks the last 15 lines to avoid matching old output that scrolled up.
#
# Exact UI strings from Claude Code:
#   "Claude usage limit reached. Your limit will reset at ..."
#   "5-hour limit reached - resets ..."
#   Menu: "Stop and wait for limit to reset"
################################################################################
detect_rate_limit_menu() {
  local content="$1"
  local recent
  recent=$(echo "$content" | tail -15)

  # Primary: the exact Claude Code rate limit message
  if echo "$recent" | grep -qiE 'Claude usage limit reached|hour limit reached'; then
    return 0
  fi

  # Secondary: the menu option text (specific enough to avoid false positives)
  if echo "$recent" | grep -qiF 'Stop and wait for limit to reset'; then
    return 0
  fi

  return 1
}

################################################################################
# Detect pause_turn (tool-use limit per turn)
#
# Returns 0 if Claude paused due to the per-turn tool call limit.
# Only checks the last 10 lines to avoid false positives from earlier output.
#
# Exact UI string from Claude Code:
#   "Claude reached its tool-use limit for this turn"
################################################################################
detect_pause_turn() {
  local content="$1"
  local tail_content
  tail_content=$(echo "$content" | tail -10)

  if echo "$tail_content" | grep -qiF 'reached its tool-use limit for this turn'; then
    return 0
  fi

  return 1
}

################################################################################
# Handle rate limit: select "stop and wait", parse time, sleep, continue
################################################################################
handle_rate_limit() {
  local content="$1"

  log "Rate limit detected"
  notify "Rate limit hit. Selecting 'Stop and wait'..."

  # Small delay to let the menu render fully
  sleep 2

  # Select option 1: "Stop and wait for limit to reset"
  tmux send-keys -t "$PANE" "1" 2>/dev/null || true
  sleep 1
  tmux send-keys -t "$PANE" Enter 2>/dev/null || true

  # Wait for the confirmation to render
  sleep 3

  # Re-capture to get the full rate limit message with the reset time
  content=$(capture_pane)

  local reset_epoch
  reset_epoch=$(parse_reset_time "$content" || true)

  local wait_seconds
  if [[ -n "$reset_epoch" ]]; then
    local now
    now=$(date +%s)
    wait_seconds=$(( reset_epoch - now + RATE_LIMIT_MARGIN ))
    if (( wait_seconds < RATE_LIMIT_MARGIN )); then
      wait_seconds=$RATE_LIMIT_MARGIN
    fi

    local human_time
    human_time=$(date -r "$reset_epoch" "+%H:%M" 2>/dev/null || echo "unknown")
    notify "Waiting until $human_time (+${RATE_LIMIT_MARGIN}s margin). Total: ${wait_seconds}s."
    log "Reset at $human_time, waiting ${wait_seconds}s"
  else
    wait_seconds=$(( FALLBACK_WAIT_HOURS * 3600 ))
    notify "Could not parse reset time. Waiting ${FALLBACK_WAIT_HOURS}h as fallback."
    log "Reset time unparseable, using fallback: ${wait_seconds}s"
  fi

  # Sleep until reset
  sleep "$wait_seconds"

  # After the wait, send Continue regardless. If the user already resumed
  # manually, typing "Continue" into an active prompt is harmless (Claude
  # treats it as a normal message). Not sending it risks leaving a session
  # stuck forever if nobody is at the keyboard.
  log "Wait complete. Sending Continue."
  tmux send-keys -t "$PANE" "Continue" Enter 2>/dev/null || true
  notify "Rate limit wait complete. Resuming session."
}

################################################################################
# Handle pause_turn: send Continue immediately
################################################################################
handle_pause_turn() {
  log "Pause turn detected. Sending Continue."
  sleep 2
  tmux send-keys -t "$PANE" "Continue" Enter 2>/dev/null || true
}

################################################################################
# Cooldown tracker (prevent sending Continue multiple times for the same pause)
################################################################################
LAST_ACTION_TIME=0
ACTION_COOLDOWN=30

should_act() {
  local now
  now=$(date +%s)
  if (( now - LAST_ACTION_TIME < ACTION_COOLDOWN )); then
    return 1
  fi
  return 0
}

mark_acted() {
  LAST_ACTION_TIME=$(date +%s)
}

################################################################################
# Main loop
################################################################################
log "Monitor started for pane $PANE (PID $$)"

while true; do
  # Check pane is still alive
  if ! pane_alive; then
    log "Pane $PANE no longer exists. Exiting."
    exit 0
  fi

  # Wrap iteration in a subshell-free guard so a single failure
  # never kills the monitor. Worst case: one poll is skipped.
  content=$(capture_pane) || content=""

  if [[ -n "$content" ]] && should_act; then
    if detect_rate_limit_menu "$content"; then
      mark_acted
      handle_rate_limit "$content" || log "handle_rate_limit failed (non-fatal)"
    elif detect_pause_turn "$content"; then
      mark_acted
      handle_pause_turn || log "handle_pause_turn failed (non-fatal)"
    fi
  fi

  sleep "$POLL_INTERVAL"
done
