"""Focused regression: canonical card hover tips never read mutable ownership.

The Lead fix in ``MechanicHoverTips.ForCard`` yields the static glossary tips and
then stops with ``if (card.IsCanonical) yield break;`` before ``card.Owner``.
The real native suite reached this through ``DustyTome.SetupForPlayer`` -> BaseLib
custom tome -> canonical ``Volibear_R18.HoverTips`` and threw
``CanonicalModelException``; ``test_canonical_preview_uses_real_native_guard``
now runs the production hover-tip composition against the pinned real
``sts2.dll``/``BaseLib.dll`` and would fail the same way if the guard moved.

``test_guard_order_source_text_is_not_gameplay`` is a source-text guard only. It
is labelled NOT gameplay on purpose and never stands in for the native suite.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
PROJECT = Path(__file__).resolve().parent / 'hover_tips_canonical/HoverTipsCanonical.Tests.csproj'
SOURCE = ROOT / 'src/Volibear/Content/MechanicHoverTips.cs'


class CanonicalHoverTipsRegression(unittest.TestCase):
    def test_canonical_preview_uses_real_native_guard(self):
        # Missing pinned configuration is an environment limit, never a silent pass.
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)

        # The fixture compiles current production source: it must not consume a
        # prebuilt shared DLL, so a stale bin cannot hide a broken guard.
        project_text = PROJECT.read_text(encoding='utf-8')
        for name in ('MechanicHoverTips.cs', 'VolibearCard.cs', 'MechanicGlossary.cs', 'VolibearLoc.cs'):
            self.assertIn('src/Volibear/Content/' + name, project_text)
        self.assertNotIn('src/Volibear/bin', project_text)
        self.assertNotIn('<Reference Include="Volibear"', project_text)

        result = runtime.run(PROJECT, args=('--nologo',), timeout=240)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        match = re.search(
            r'HOVER_TIPS_CANONICAL_PASS checks=(\d+) '
            r'fixture=real-sts2\+BaseLib\+real-LocManager/LocTable '
            r'production-sources=MechanicHoverTips\+VolibearCard\+glossary\+loc '
            r'canonical-owner-throws=CanonicalModelException '
            r'static-tips=preserved live-state-tip=absent ledger-queries=0 '
            r'engagement-ledger=TEST-DOUBLE-NOT-GAMEPLAY '
            r'modeldb-and-dustytome-setup=NOT_RUN godot-render=NOT_RUN native-gameplay=NOT_RUN',
            output)
        self.assertIsNotNone(match, output)
        self.assertGreaterEqual(int(match.group(1)), 18)

    def test_guard_order_source_text_is_not_gameplay(self):
        """SOURCE-TEXT GUARD, NOT GAMEPLAY: static tips stay, then canonical stops, then Owner."""
        source = SOURCE.read_text(encoding='utf-8')
        body = source.split('internal static IEnumerable<IHoverTip> ForCard', 1)[1]
        static_tips = body.index('yield return tip')
        canonical_stop = body.index('if (card.IsCanonical) yield break;')
        owner_read = body.index('card.Owner')
        self.assertLess(static_tips, canonical_stop,
                        'canonical guard must not suppress the static glossary tips')
        self.assertLess(canonical_stop, owner_read,
                        'canonical guard must return before any card.Owner read')
        self.assertRegex(body[canonical_stop:canonical_stop + 64],
                         r'^if \(card\.IsCanonical\) yield break;',
                         'the canonical guard must depend on canonical state alone')


if __name__ == '__main__':
    unittest.main()
