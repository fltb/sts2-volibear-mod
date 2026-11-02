import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import power_presentation_evidence as gate


def sample_ui():
    # Synthetic lifecycle receipt, not engine execution. The production probe uses
    # the original scene's unbound node and real Model setters/PowerCmd calls.
    cases = [
        ('unbound-ready', None, False, True, False, False),
        ('late-bound-off', 'WeakPower', False, True, False, True),
        ('domain-on', 'WeakPower', True, True, True, False),
        ('rebound-ordinary', 'StrengthPower', False, True, True, True),
        ('rebound-debuff', 'WeakPower', True, True, True, True),
        ('domain-off', 'WeakPower', False, True, False, False),
        ('tree-detached', 'WeakPower', False, False, False, False),
        ('tree-reattached', 'WeakPower', False, True, False, False),
        ('domain-reentered', 'WeakPower', True, True, True, False),
    ]
    return dict(fixture='native-multiplayer-power-intent-extracted',
        sourceScene='res://scenes/combat/multiplayer_player_intent.tscn', nodeType='MegaCrit.Sts2.Core.Nodes.Combat.NPower',
        freed=True, powersRestored=True, stages=[dict(phase=phase, nodeId=123, boundModel=model,
            ready=inside, insideTree=inside, overlays=1, children=3, visible=visible, visibleInTree=visible and inside,
            domain=domain, immediate=immediate, setterSameFrame=True if immediate else None)
            for phase, model, visible, inside, domain, immediate in cases])


def sample_report():
    rows = []
    # A synthetic fixture, never native-game evidence. Expectations are frozen test data.
    for spec in gate.EXPECTED:
        for amount in ([2, 5] if '{Amount}' in spec['text'] or spec['model'] == 'StormChargePower' else [1]) + ([999999999] if spec['model'] == 'DomainPower' else []):
            small, big, exact = gate.expected_paths(spec)
            rows.append(dict(model=spec['model'], title=spec['title'], amount=amount,
                displayAmount=0 if amount == 999999999 else amount,
                description=gate.PERMANENT if amount == 999999999 else spec['text'].replace('{Amount}', str(amount)),
                mutable=True, smart=True, iconPath=small, bigIconPath=big,
                width=64 if exact else 300, height=64 if exact else 400,
                bigWidth=256 if exact else 600, bigHeight=256 if exact else 800))
    return dict(schema=1, token='fresh', acceptance=gate.ACCEPTANCE, fixture=gate.FIXTURE, testMode=False, models=25, rows=rows, uiLifecycle=sample_ui())


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

    def test_power_alias_pngs_match_approved_exports_and_production_constants(self):
        manifest = json.loads((ROOT / 'assets/art-refresh/20261102/provenance.json').read_text())
        exports = {row['path']: row for row in manifest['exports']}
        constants = (ROOT / 'src/Volibear/Presentation/VolibearIcons.cs').read_text()
        for alias, stem in [('Domain', 'domain'), ('ThunderForce', 'thunder_force'), ('BearSpirit', 'bear_spirit'), ('Wilderness', 'wilderness')]:
            self.assertIn(stem, manifest['status_sheet']['ids'])
            for suffix, folder, size in [('', '', 64), ('Big', 'big/', 256)]:
                path = f'src/Volibear/Presentation/icons/powers/{folder}{stem}.png'
                spec = exports[path]
                self.assertEqual(spec['size'], size)
                content = (ROOT / path).read_bytes()
                self.assertEqual(sha256(content).hexdigest(), spec['sha256'])
                self.assertEqual((int.from_bytes(content[16:20], 'big'), int.from_bytes(content[20:24], 'big')), (size, size))
                self.assertIn(f'{alias}{suffix} = "res://VolibearArt/icons/powers/{folder}{stem}.png";', constants)
        for spec in gate.EXPECTED:
            if spec['icon'] is None:
                small, big, exact = gate.expected_paths(spec)
                self.assertTrue(exact)
                for resource, size in [(small, 64), (big, 256)]:
                    path = resource.replace('res://VolibearArt/', 'src/Volibear/Presentation/')
                    self.assertEqual(exports[path]['size'], size)

    def test_legacy_svg_portraits_and_wrong_beast_sizes_are_rejected_with_diagnostics(self):
        baseline = sample_report()
        for index, row in enumerate(baseline['rows']):
            if '/icons/powers/' not in row['iconPath']:
                continue
            legacy = row['iconPath'].replace('.png', '.svg')
            if row['model'] in ('BearSpiritPower', 'WildernessPower'):
                legacy = 'res://VolibearArt/cards/production/sts2/Volibear/images/card_portraits/' + ('r28' if row['model'] == 'BearSpiritPower' else 'r30') + '.png'
            bad = copy.deepcopy(baseline); bad['rows'][index]['iconPath'] = legacy
            result, passed = gate.power_presentation_evidence(gate.PREFIX + json.dumps(bad), 'fresh')
            self.assertFalse(passed)
            self.assertTrue(any(f'rows[{index}] {row["model"]}' in e and '.iconPath:' in e and legacy in e for e in result['errors']))
        for model in ('BearSpiritPower', 'WildernessPower'):
            bad = copy.deepcopy(baseline)
            row = next(r for r in bad['rows'] if r['model'] == model)
            row['width'] = 300
            self.assertTrue(any(model in e and '.width:' in e for e in gate.power_presentation_errors(bad, 'fresh')))
        result, passed = gate.power_presentation_evidence(gate.PREFIX + '{"token":"fresh","token":"fresh"}', 'fresh')
        self.assertFalse(passed)
        self.assertIn('duplicate JSON key', result['errors'][0])

    def test_positive_synthetic_fixture(self):
        self.assertEqual(len(sample_report()['rows']), 46)
        storm_rows = [row for row in sample_report()['rows'] if row['model'] == 'StormChargePower']
        self.assertEqual([(row['amount'], row['displayAmount']) for row in storm_rows], [(2, 2), (5, 5)])
        self.assertEqual(storm_rows[0]['description'], storm_rows[1]['description'])
        self.assertTrue(gate.validate_power_presentation(sample_report(), 'fresh'))

    def test_ui_lifecycle_is_mandatory_and_exactly_ordered(self):
        baseline = sample_report()
        for value in (None, {}, [], True):
            bad = copy.deepcopy(baseline); bad['uiLifecycle'] = value
            self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))
        for field, value in [('fixture', 'NPower.Create'), ('sourceScene', 'fake'), ('nodeType', 'FakeNPower'), ('freed', False), ('powersRestored', False)]:
            bad = copy.deepcopy(baseline); bad['uiLifecycle'][field] = value
            self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))
        for index in range(9):
            bad = copy.deepcopy(baseline); bad['uiLifecycle']['stages'].pop(index)
            self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))
        bad = copy.deepcopy(baseline); bad['uiLifecycle']['stages'][3:5] = reversed(bad['uiLifecycle']['stages'][3:5])
        self.assertFalse(gate.validate_power_presentation(bad, 'fresh'))

    def test_ui_lifecycle_rejects_stale_binding_duplicates_and_delayed_setter(self):
        baseline = sample_report()
        for index, row in enumerate(baseline['uiLifecycle']['stages']):
            mutations = [('phase', 'fake'), ('nodeId', True), ('nodeId', 0), ('nodeId', 456),
                ('boundModel', 'OtherPower'), ('overlays', 2), ('overlays', True), ('children', 2),
                ('visible', not row['visible']), ('visibleInTree', not row['visibleInTree']),
                ('insideTree', not row['insideTree']), ('domain', not row['domain']), ('immediate', not row['immediate']),
                ('setterSameFrame', False)]
            if row['insideTree']:
                mutations.append(('ready', False))
            for field, value in mutations:
                bad = copy.deepcopy(baseline); bad['uiLifecycle']['stages'][index][field] = value
                self.assertFalse(gate.validate_power_presentation(bad, 'fresh'), (index, field))
            for field in row:
                bad = copy.deepcopy(baseline); del bad['uiLifecycle']['stages'][index][field]
                self.assertFalse(gate.validate_power_presentation(bad, 'fresh'), (index, field))

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

    def test_domain_suppression_description_is_required_for_finite_and_permanent(self):
        # The approved player-facing effects are mandatory in both duration forms.
        # Full finite/permanent templates remain exact; gameplay boundaries live in their own tests.
        sentences = (
            '禁用敌方特殊能力与全队负面状态。',
            '你每抽到状态或诅咒，消耗该牌并补抽1张；',
            '每打出一张攻击牌，对全体造成4雷伤。',
        )
        baseline = sample_report()
        for index, row in enumerate(baseline['rows']):
            if row['model'] != 'DomainPower':
                continue
            for sentence in sentences:
                with self.subTest(amount=row['amount'], missing=sentence):
                    self.assertIn(sentence, row['description'])
                    bad = copy.deepcopy(baseline)
                    bad['rows'][index]['description'] = row['description'].replace(sentence, '')
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
