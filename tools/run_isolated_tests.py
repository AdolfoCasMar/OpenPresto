"""Run each test module in its own process so Qt applications cannot leak across suites."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
failed = []
for path in sorted((root / 'tests').glob('test_*.py')):
    print('TEST MODULE: ' + path.name, flush=True)
    try:
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', path.name, '-v'], cwd=root, timeout=120)
        if result.returncode:
            failed.append((path.name, result.returncode))
    except subprocess.TimeoutExpired:
        failed.append((path.name, 'timeout'))
print('Failed modules: ' + repr(failed), flush=True)
raise SystemExit(bool(failed))
