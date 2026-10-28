#!/usr/bin/env bats

setup() {
  SCRIPT="$BATS_TEST_DIRNAME/../../.github/scripts/hook-benchmark.py"
}

@test "a threshold flag without a value is rejected" {
  # Arrange
  local flag="--threshold"

  # Act
  run python3 "$SCRIPT" "$flag"

  # Assert
  [ "$status" -ne 0 ]
  [[ "$output" == *"--threshold needs a value in milliseconds"* ]]
}

@test "a threshold no hook can meet fails the benchmark" {
  # Arrange
  local threshold_ms="0"

  # Act
  run python3 "$SCRIPT" --threshold "$threshold_ms"

  # Assert
  [ "$status" -eq 1 ]
  [[ "$output" == *"ms over 0 ms"* ]]
}
