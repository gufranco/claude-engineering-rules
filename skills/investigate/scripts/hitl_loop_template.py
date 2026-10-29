from __future__ import annotations

import sys

NO_TERMINAL = (
    "No terminal input. Run this in your own terminal window, "
    "never through the ! prefix."
)


def step(instruction: str) -> None:
    print(f"\n>>> {instruction}", flush=True)
    input("    [Enter when done] ")


def capture(question: str) -> str:
    print(f"\n>>> {question}", flush=True)
    return input("    > ")


def session() -> dict[str, str]:
    step("Open the app at http://localhost:3000 and sign in.")
    errored = capture("Click the Export button. Did it throw an error? (y/n)")
    error_message = capture("Paste the error message, or none:")
    return {"ERRORED": errored, "ERROR_MSG": error_message}


def main() -> int:
    try:
        captured = session()
    except EOFError:
        print(f"\n{NO_TERMINAL}", file=sys.stderr)
        return 1
    print("\n--- Captured ---", flush=True)
    for name, value in captured.items():
        print(f"{name}={value}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
