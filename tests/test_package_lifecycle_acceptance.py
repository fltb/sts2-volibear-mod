"""Synthetic unit fixtures; these tests do not claim installed game acceptance."""
import json
from unittest.mock import patch
from tests import test_package_lifecycle as fixtures
import unittest
from tools import package_lifecycle_acceptance as acceptance


class AcceptanceTests(unittest.TestCase):
    setUp = fixtures.PackageLifecycleTests.setUp
    _make_game = fixtures.PackageLifecycleTests._make_game
    build_package = fixtures.PackageLifecycleTests.build_package
    def test_acceptance_real_operations(self):
        package, _ = self.build_package()
        before = self.sentinel.read_bytes()
        report = acceptance.accept(package, self.game, self.root / 'acceptance')
        self.assertEqual(report['status'], 'passed')
        self.assertEqual([s['action'] for s in report['steps']], ['install', 'update', 'uninstall'])
        self.assertTrue(all(report['checks'].values()))
        self.assertEqual(before, self.sentinel.read_bytes())
        self.assertFalse((self.game / 'mods/Volibear').exists())
        self.assertFalse((self.root / 'acceptance/game/mods/Volibear').exists())
        again = acceptance.accept(package, self.game, self.root / 'acceptance2')
        self.assertEqual(report, again)

    def test_refuses_existing_or_source_directory(self):
        package, _ = self.build_package()
        with self.assertRaises(ValueError):
            acceptance.accept(package, self.game, self.game / 'fixture')
        with self.assertRaises(FileExistsError):
            acceptance.accept(package, self.game, self.root)

    def test_failure_records_and_propagates(self):
        package, _ = self.build_package()
        with patch.object(acceptance.lifecycle, 'run', side_effect=ValueError('injected')):
            with self.assertRaisesRegex(ValueError, 'injected'):
                acceptance.accept(package, self.game, self.root / 'failure')
        report = json.loads((self.root / 'failure/report.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['steps'], [])
