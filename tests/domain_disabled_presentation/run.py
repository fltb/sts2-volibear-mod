"""Focused native-reference hover test; never launches a game or release gate."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime

try:
    runtime = fixture_runtime(unittest.TestCase(), 'sdk', 'native', 'baselib', root=ROOT)
except unittest.SkipTest as error:
    print(str(error))
    sys.exit(0)
result = runtime.run(Path(__file__).with_name('DomainDisabledPresentation.Tests.csproj'), timeout=120)
print(result.stdout, end='')
print(result.stderr, end='', file=sys.stderr)
sys.exit(result.returncode)
