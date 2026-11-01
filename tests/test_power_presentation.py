import copy
import json
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import power_presentation_evidence as gate


def sample_report():
    rows = []
    # A synthetic fixture, never native-game evidence. Expectations are frozen test data.
    for spec in gate.EXPECTED:
        for amount in ([2, 5] if '{Amount}' in spec['text'] else [1]) + ([999999999] if spec['model'] == 'DomainPower' else []):
            small, big, exact = gate.expected_paths(spec)
            rows.append(dict(model=spec['model'], title=spec['title'], amount=amount,
                displayAmount=0 if amount == 999999999 else amount,
                description=gate.PERMANENT if amount == 999999999 else spec['text'].replace('{Amount}', str(amount)),
                mutable=True, smart=True, iconPath=small, bigIconPath=big,
                width=64 if exact else 300, height=64 if exact else 400,
                bigWidth=256 if exact else 600, bigHeight=256 if exact else 800))
    return dict(schema=1, token='fresh', acceptance=gate.ACCEPTANCE, fixture=gate.FIXTURE, testMode=False, models=25, rows=rows)


class PowerPresentationTests(unittest.TestCase):
    def test_source_complete_smart_text_and_semantic_resources(self):
        source_root = Path(os.environ.get('VOLIBEAR_POWER_SOURCE_ROOT', ROOT / 'src/Volibear'))
        catalog = json.loads((ROOT / 'assets/animation/vfx/icons/manifest.json').read_text(encoding='utf-8'))
        icon_ids = {row['id'] for row in catalog['icons']}
        pattern = re.compile(r'new PowerLoc\(\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"')
        self.assertEqual(len(gate.EXPECTED), 25)
        self.assertEqual(sum(s['icon'] is not None for s in gate.EXPECTED), 13)
        for spec in gate.EXPECTED:
            source = (source_root / spec['file']).read_text(encoding='utf-8')
            texts = [match[3] for match in pattern.finditer(source) if match[1] == spec['title']]
            self.assertEqual(texts, [spec['text']], spec['model'])
            if spec['icon']:
                self.assertIn(spec['icon'], icon_ids)
                block = source.split('public sealed class ' + spec['model'] + ' ', 1)[1].split('public sealed class ', 1)[0]
                for size, getter in [(64, 'CustomPackedIconPath'), (256, 'CustomBigIconPath')]:
                    self.assertIn(f'{getter} => "res://VolibearArt/vfx/icons/{size}/{spec["icon"]}.png";', block)
                    self.assertTrue((ROOT / f'assets/animation/vfx/icons/{size}/{spec["icon"]}.png').is_file())
        domain = (source_root / 'Core/DomainPower.cs').read_text(encoding='utf-8')
        self.assertIn('("permanentDescription", "' + gate.PERMANENT + '")', domain)

    def test_positive_synthetic_fixture(self):
        self.assertEqual(len(sample_report()['rows']), 46)
        self.assertTrue(gate.validate_power_presentation(sample_report(), 'fresh'))

    def test_negative_each_title_text_amount_icon_dimension_and_type(self):
        baseline = sample_report()
        for index, row in enumerate(baseline['rows']):
            for field, wrong in [('title', 'Strength'), ('description', '每个实例分别计数。'),
                                 ('amount', True), ('displayAmount', False), ('mutable', False), ('smart', False),
                                 ('iconPath', 'res://images/powers/strength.png'), ('bigIconPath', 'missing'),
                                 ('width', 0), ('height', -1), ('bigWidth', True), ('bigHeight', '256')]:
                bad = copy.deepcopy(baseline); bad['rows'][index][field] = wrong
                self.assertFalse(gate.validate_power_presentation(bad, 'fresh'), (index, field))
            if '{Amount}' in gate.EXPECTED[[s['model'] for s in gate.EXPECTED].index(row['model'])]['text'] and row['amount'] == 5:
                bad = copy.deepcopy(baseline); bad['rows'][index]['description'] = row['description'].replace('5', '2')
                self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))

    def test_permanent_native_clamp_bug_stays_rejected(self):
        report = sample_report()
        index = next(i for i, row in enumerate(report['rows']) if row['amount'] == 999999999)
        # Native SetAmount clamps the obsolete int.MaxValue sentinel. The observed
        # bad run displayed a finite duration; merely accepting its amount is NOT a fix.
        bad = copy.deepcopy(report)
        bad['rows'][index]['displayAmount'] = 999999999
        spec = next(s for s in gate.EXPECTED if s['model'] == 'DomainPower')
        bad['rows'][index]['description'] = spec['text'].replace('{Amount}', '999999999')
        self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))
        for field, value in [('amount', 2147483647), ('displayAmount', 999999999),
                             ('description', spec['text'].replace('{Amount}', '999999999'))]:
            bad = copy.deepcopy(report); bad['rows'][index][field] = value
            self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))
        bad = copy.deepcopy(report)
        finite = next(i for i, row in enumerate(report['rows']) if row['model'] == 'DomainPower' and row['amount'] == 5)
        bad['rows'][finite]['description'] = gate.PERMANENT
        self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))

    def test_negative_metadata_rows_and_runtime_failure(self):
        baseline = sample_report()
        for field, value in [('token', 'stale'), ('schema', True), ('models', 24), ('testMode', True),
                             ('acceptance', 'visual-pass'), ('fixture', 'synthetic')]:
            bad = copy.deepcopy(baseline); bad[field] = value
            self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))
        bad = copy.deepcopy(baseline); bad['rows'].pop()
        self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))
        line = gate.PREFIX + json.dumps(baseline)
        self.assertTrue(gate.power_presentation_evidence(line, 'fresh')[1])
        for log in ['', gate.PREFIX + '{', line + '\n' + line, 'POWER_PRESENTATION_FAILED failure\n' + line]:
            self.assertFalse(gate.power_presentation_evidence(log, 'fresh')[1])


if __name__ == '__main__':
    unittest.main()
