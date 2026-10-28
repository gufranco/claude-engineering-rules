#!/usr/bin/env bats

setup() {
  SCRIPT="$BATS_TEST_DIRNAME/../../.github/scripts/mcp-server-probe.py"
  export HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$HOME/.claude"
}

write_settings() {
  printf '%s\n' "$1" > "$HOME/.claude/settings.json"
}

@test "a server that exits zero passes" {
  # Arrange
  write_settings '{"mcpServers": {"ok": {"command": "true"}}}'

  # Act
  run python3 "$SCRIPT"

  # Assert
  [ "$status" -eq 0 ]
  [[ "$output" == *"PASS (ok): exited cleanly"* ]]
  [[ "$output" == *"Results: 1 passed, 0 failed, 0 skipped"* ]]
}

@test "a server still running at the deadline passes" {
  # Arrange
  write_settings '{"mcpServers": {"slow": {"command": "sleep", "args": ["10"]}}}'

  # Act
  run python3 "$SCRIPT"

  # Assert
  [ "$status" -eq 0 ]
  [[ "$output" == *"PASS (slow): started successfully"* ]]
}

@test "a server that exits non-zero fails the run" {
  # Arrange
  write_settings '{"mcpServers": {"bad": {"command": "false"}}}'

  # Act
  run python3 "$SCRIPT" --verbose

  # Assert
  [ "$status" -eq 1 ]
  [[ "$output" == *"FAIL (bad): exited with code 1"* ]]
  [[ "$output" == *"Command: false"* ]]
}

@test "a server with no command is skipped" {
  # Arrange
  write_settings '{"mcpServers": {"remote": {"type": "http", "url": "https://example.invalid/mcp"}}}'

  # Act
  run python3 "$SCRIPT"

  # Assert
  [ "$status" -eq 0 ]
  [[ "$output" == *"SKIP (remote): command not found"* ]]
  [[ "$output" == *"Results: 0 passed, 0 failed, 1 skipped"* ]]
}

@test "arguments with spaces reach the server intact" {
  # Arrange
  write_settings '{"mcpServers": {"spaced": {"command": "test", "args": ["a b", "=", "a b"]}}}'

  # Act
  run python3 "$SCRIPT"

  # Assert
  [ "$status" -eq 0 ]
  [[ "$output" == *"PASS (spaced): exited cleanly"* ]]
}

@test "no configured servers exits zero with a notice" {
  # Arrange
  write_settings '{"mcpServers": {}}'

  # Act
  run python3 "$SCRIPT"

  # Assert
  [ "$status" -eq 0 ]
  [ "$output" = "No MCP servers configured in settings.json." ]
}

@test "a missing settings file is an error" {
  # Arrange
  rm -f "$HOME/.claude/settings.json"

  # Act
  run python3 "$SCRIPT"

  # Assert
  [ "$status" -eq 1 ]
  [[ "$output" == "ERROR: settings.json not found at $HOME/.claude/settings.json" ]]
}
