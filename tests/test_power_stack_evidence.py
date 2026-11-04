import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import power_stack_evidence as gate
from power_stack_samples import sample_stack


class PowerStackEvidenceTests(unittest.TestCase):
    def test_complete_synthetic_contract(self):
        self.assertEqual(gate.errors(sample_stack()), [])
        self.assertEqual(len(gate.ORDER), 25)
        self.assertEqual(len(list(gate.expected_samples())), 83)
        self.assertNotIn('本战', gate.PERMANENT)
        self.assertTrue(gate.PERMANENT.startswith('领域持续。'))
        permanent = next(row for row in sample_stack()['samples'] if row['phase'] == 'domain-permanent')
        self.assertEqual(permanent['label'], '')
        self.assertEqual(permanent['tips'], [gate.PERMANENT])

    def test_requires_new_complete_receipt(self):
        for value in (None, {}, [], {'fixture': 'wrong'}):
            self.assertTrue(gate.errors(value))
        value = sample_stack(); value['samples'].pop()
        self.assertTrue(gate.errors(value))

    def test_rejects_duplicate_visible_icons_or_merged_models(self):
        for field, wrong in [('visibleCount', 2), ('nodeCount', 1), ('amounts', [7]), ('label', '3'), ('visibleNode', True)]:
            value = sample_stack(); value['samples'][1][field] = wrong
            self.assertTrue(gate.errors(value), field)

    def test_rejects_incomplete_or_unpaid_armor_response(self):
        for field, wrong in [('blockAfter', 14), ('blockGains', [7]), ('lightningAfter', 2), ('powersRestored', False)]:
            value = sample_stack(); value[field] = wrong
            self.assertTrue(gate.errors(value), field)
        value = sample_stack(); value['payments'][1]['after'] = 9
        self.assertTrue(gate.errors(value))

    def test_rejects_stale_representative(self):
        for index, wrong in [(3, 101), (4, 999), (5, 999)]:
            value = sample_stack(); value['samples'][index]['visibleNode'] = wrong
            self.assertTrue(gate.errors(value))

    def test_rejects_wrong_counter_semantics_and_hover(self):
        for model, phase, label in [('StormConductionPower', 'matrix-updated', '7'),
                                    ('ImmovableBodyPower', 'matrix-single', '1'),
                                    ('DomainPower', 'domain-permanent', '0'),
                                    ('DomainPower', 'domain-permanent', '本战'),
                                    ('WelcomeThunderPower', 'matrix-updated', '7')]:
            value = sample_stack()
            row = next(r for r in value['samples'] if r['model'] == model and r['phase'] == phase)
            row['label'] = label
            self.assertTrue(gate.errors(value), model)
        value = sample_stack(); value['samples'][1]['tips'] = ['每次获得3格挡。']
        self.assertTrue(gate.errors(value))

    def test_rejects_permanent_lifetime_marker_and_incomplete_copy(self):
        def permanent_row():
            value = sample_stack()
            return value, next(r for r in value['samples'] if r['phase'] == 'domain-permanent')
        for tips in (['领域持续本战。禁用敌方特殊能力与全队负面状态。'],
                     [gate.PERMANENT, '本战'],
                     ['禁用敌方特殊能力与全队负面状态。每打出一张攻击牌，对全体造成4雷伤。'],
                     ['领域持续。']):
            value, row = permanent_row()
            row['tips'] = tips
            self.assertTrue(gate.errors(value), tips)

    def test_rejects_duplicate_self_glossary(self):
        for model in ('ThunderArmorPower', 'DomainPower', 'ImmovableBodyPower'):
            value = sample_stack()
            row = next(r for r in value['samples'] if r['model'] == model and r['phase'] == 'matrix-single')
            row['tipTitles'].append(gate.TITLES[model])
            row['tips'].append('重复自身说明。')
            self.assertTrue(gate.errors(value))

    def test_all_twenty_five_rows_are_mandatory_in_order(self):
        value = sample_stack(); value['samples'][8], value['samples'][9] = value['samples'][9], value['samples'][8]
        self.assertTrue(gate.errors(value))
        for model in gate.ORDER:
            value = sample_stack()
            next(r for r in value['samples'] if r['model'] == model and r['phase'] == 'matrix-single')['visibleCount'] = 0
            self.assertTrue(gate.errors(value), model)
