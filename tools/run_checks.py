"""Release check: fail if any discovered test fails OR is skipped.

Run python tools/run_checks.py from any directory. Install ngspice and test
extras first. This check never invokes live Gemini extraction or product memory.
"""
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


if __name__=='__main__':
    os.chdir(ROOT)
    suite=unittest.defaultTestLoader.discover('tests')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped:
        print('Release checks failed: skipped tests must be resolved.',file=sys.stderr)
    sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
