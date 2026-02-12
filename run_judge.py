from pathlib import Path
import subprocess
import sys


BASE_DIR = Path(__file__).resolve().parent
CODE_FILE = BASE_DIR / "practice.py"
INPUT_FILE = BASE_DIR / "inputs.txt"
OUTPUT_FILE = BASE_DIR / "output.txt"
EXPECTED_FILE = BASE_DIR / "expected.txt"


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def main() -> int:
    if not CODE_FILE.exists():
        print("Missing practice.py")
        return 1

    if not INPUT_FILE.exists():
        print("Missing inputs.txt")
        return 1

    input_data = INPUT_FILE.read_text(encoding="utf-8")

    run = subprocess.run(
        [sys.executable, str(CODE_FILE)],
        input=input_data,
        text=True,
        capture_output=True,
        cwd=BASE_DIR,
    )

    OUTPUT_FILE.write_text(run.stdout, encoding="utf-8")

    if run.returncode != 0:
        print("Runtime Error in practice.py")
        if run.stderr:
            print(run.stderr)
        return run.returncode

    print("Program executed successfully.")
    print("Output written to output.txt")

    if EXPECTED_FILE.exists():
        expected = normalize(EXPECTED_FILE.read_text(encoding="utf-8"))
        actual = normalize(run.stdout)
        if actual == expected:
            print("Test Result: PASS")
            return 0

        print("Test Result: FAIL")
        print("Expected (expected.txt):")
        print(EXPECTED_FILE.read_text(encoding="utf-8"))
        print("Actual (output.txt):")
        print(run.stdout)
        return 2

    print("Tip: add expected.txt to enable automatic PASS/FAIL checks.")
    return 0


if __name__ == "__main__":
    exit_code = main()

    # In debugger mode (F5), avoid raising SystemExit so VS Code doesn't show
    # it as an exception popup for FAIL cases (exit code 2).
    if sys.gettrace() is None:
        raise SystemExit(exit_code)
