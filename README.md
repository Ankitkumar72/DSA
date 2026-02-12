# Local Competitive Programming Setup

Use this folder like a simple online compiler.

## Files
- `practice.py`: write your solution here.
- `inputs.txt`: put the stdin input here.
- `output.txt`: generated output after each run.
- `expected.txt` (optional): expected output for PASS/FAIL check.
- `run_judge.py`: optional external runner script.
- `run.bat`: optional Windows shortcut to run the external judge.

## Run (recommended)
Run `practice.py` directly:
```powershell
python practice.py
```

What this does automatically:
- reads input from `inputs.txt`
- writes result to `output.txt`
- checks `expected.txt` (if present) and prints `PASS`/`FAIL`

In VS Code, you can also use:
- Run button on `practice.py`
- `F5` with launch profile `Python: Current File (CP)`
- `F5` with launch profile `CP: Run current file (inputs.txt -> output.txt)` to force file-based I/O

## Typical workflow
1. Write/modify your code in `practice.py`.
2. Put test input in `inputs.txt`.
3. Put expected output in `expected.txt` (optional).
4. Run `practice.py` directly.
5. Check `output.txt` and terminal PASS/FAIL message.
