"""Independent synthetic receipt controls; these are not native game results."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import character_integration_evidence as gate


def fixture():
    text = [
        ('characters', 'VOLIBEAR_CHARACTER.cardsModifierTitle', '不灭狂雷'),
        ('characters', 'VOLIBEAR_CHARACTER.cardsModifierDescription', '沃利贝尔的卡牌会出现在奖励和商店中。'),
        ('characters', 'VOLIBEAR_CHARACTER.eventDeathPrevention', '雷霆拒绝了死亡。'),
        ('characters', 'VOLIBEAR_CHARACTER.aromaPrinciple', '风暴只服从自己的意志'),
        ('characters', 'VOLIBEAR_CHARACTER.goldMonologue', '这些金属，终将被雷霆熔铸。'),
        ('characters', 'VOLIBEAR_CHARACTER.banter.alive.endTurnPing', '风暴不会等待。'),
        ('characters', 'VOLIBEAR_CHARACTER.banter.dead.endTurnPing', '雷声尚未消散……'),
        ('relics', 'SEA_GLASS.VOLIBEAR_CHARACTER.title', '风暴海玻璃'),
    ]
    lines = [
        dict(speaker='Ancient', text='你的风暴，已经震动了这里的根基。'),
        dict(speaker='Character', text='石墙会崩塌。雷霆不会。'),
        dict(speaker='Ancient', text='那就让我看看，这场风暴还能持续多久。'),
    ]
    inventory = dict(deck=[dict(instance=i + 1, id='VOLIBEAR_' + name, upgrade=0)
                          for i, name in enumerate(['B01'] * 4 + ['B02'] * 4 + ['B03', 'B04'])],
                     relics=[dict(instance=11, id='VOLIBEAR_HUNTERS_HEART')])
    return dict(token='character-test', pid=101, result=dict(
        schema=1, character='VOLIBEAR_CHARACTER',
        hands=[dict(gesture=gesture,
                    path=f'res://VolibearArt/ui/images/multiplayer_hand_volibear_{gesture}.png',
                    width=422, height=1200, pivotX=163 if gesture == 'pointing' else 197,
                    pivotY=10 if gesture == 'pointing' else 600, decoded=True, sha256=str(index + 1) * 64)
               for index, gesture in enumerate(('pointing', 'rock', 'paper', 'scissors'))],
        textRows=[dict(language=language, table=table, key=key, text=value)
                  for language in ('zhs', 'eng', 'zhs') for table, key, value in text],
        dialogueRows=[dict(language=language, visits=visits,
                           candidates=[dict(repeating=True, lines=deepcopy(lines))])
                      for language in ('zhs', 'eng', 'zhs') for visits in (0, 1, 25)],
        tome=dict(selected='VOLIBEAR_R18', rarity='Rare', upgrade=1, restored='VOLIBEAR_R18',
                  restoredUpgrade=1, restoredRelicCard='VOLIBEAR_R18', lightning=9, pool=6,
                  relic=dict(id='RELIC.DUSTY_TOME', floor_added_to_deck=0,
                             props=dict(model_ids=[dict(name='AncientCard', value='CARD.VOLIBEAR_R18')])),
                  card=dict(id='CARD.VOLIBEAR_R18', current_upgrade_level=1)),
        suppressedNativeAudio=[
            'event:/sfx/characters/volibear_character/volibear_character_select',
            'event:/sfx/characters/volibear_character/volibear_character_attack',
            'event:/sfx/characters/volibear_character/volibear_character_cast',
            'event:/sfx/characters/volibear_character/volibear_character_die',
            'event:/sfx/ui/wipe_volibear_character',
        ], inventoryBefore=deepcopy(inventory), inventoryAfter=deepcopy(inventory), inventoryUnchanged=True,
        scope='native-character-resource-localization-ancient-reward-contracts'))


class CharacterIntegrationOracle(unittest.TestCase):
    def setUp(self):
        self.raw = fixture()

    def evaluate(self, raw=None):
        return gate.check_log('[Volibear] CHARACTER_INTEGRATION_RESULT ' +
                              json.dumps(self.raw if raw is None else raw), 'character-test', 101)

    def change(self, path, value):
        raw = deepcopy(self.raw)
        node = raw
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        return raw

    def test_complete_synthetic_native_contract_shape(self):
        checked = self.evaluate()
        self.assertEqual(checked['errors'], [])
        self.assertEqual(checked['raw'], self.raw)
        self.assertEqual(checked['scope'], 'native-character-resource-localization-ancient-reward-contracts')
        self.assertEqual(len(checked['raw']['result']['textRows']), 24)
        self.assertEqual(len(checked['raw']['result']['dialogueRows']), 9)

    def test_envelope_schema_identity_scope_and_pid_are_strict(self):
        for path, value in [
            (('token',), 'stale'), (('pid',), 102), (('pid',), True), (('pid',), 101.0),
            (('result', 'schema'), True), (('result', 'schema'), 1.0),
            (('result', 'character'), 'IRONCLAD'), (('result', 'scope'), 'natural-finale-win'),
        ]:
            with self.subTest(path=path, value=value):
                self.assertTrue(self.evaluate(self.change(path, value))['errors'])
        for token, pid in [('', 101), (' ', 101), ('character-test', True), ('character-test', 101.0)]:
            self.assertTrue(gate.check_log(gate.PREFIX + json.dumps(self.raw), token, pid)['errors'])

    def test_unknown_or_missing_result_fields_cannot_claim_passed(self):
        for key in self.raw['result']:
            raw = deepcopy(self.raw); del raw['result'][key]
            with self.subTest(missing=key): self.assertTrue(self.evaluate(raw)['errors'])
        self.raw['result']['passed'] = True
        self.assertTrue(self.evaluate()['errors'])

    def test_all_four_hand_getters_must_decode_the_approved_canvas_and_pivots(self):
        for field, value in [('gesture', 'rock'), ('path', 'res://images/packed/ironclad_pointing.png'),
                             ('width', 394), ('height', 640), ('width', 422.0), ('pivotX', 197),
                             ('pivotY', 600), ('decoded', False), ('decoded', 1), ('sha256', '')]:
            with self.subTest(field=field, value=value):
                self.assertTrue(self.evaluate(self.change(('result', 'hands', 0, field), value))['errors'])
        for index in (1, 2, 3):
            self.assertTrue(self.evaluate(self.change(('result', 'hands', index, 'pivotY'), 10))['errors'])

    def test_missing_swapped_or_identical_hand_images_fail(self):
        for mutate in (lambda hands: hands.pop(), lambda hands: hands.reverse(),
                       lambda hands: hands[1].update(sha256=hands[0]['sha256'])):
            raw = deepcopy(self.raw); mutate(raw['result']['hands'])
            self.assertTrue(self.evaluate(raw)['errors'])

    def test_language_reload_requires_every_real_camel_case_key_and_resolved_value(self):
        for index in (0, 7, 8, 15, 16, 23):
            raw = deepcopy(self.raw); raw['result']['textRows'].pop(index)
            with self.subTest(missing=index): self.assertTrue(self.evaluate(raw)['errors'])
        for field, value in [('key', 'VOLIBEAR_CHARACTER.cards_modifier_title'), ('language', 'zh'),
                             ('table', 'events'), ('text', 'VOLIBEAR_CHARACTER.cardsModifierTitle'),
                             ('text', ''), ('text', '{0}')]:
            self.assertTrue(self.evaluate(self.change(('result', 'textRows', 0, field), value))['errors'])
        self.raw['result']['textRows'][16] = deepcopy(self.raw['result']['textRows'][8])
        self.assertTrue(self.evaluate()['errors'])

    def test_finale_must_select_for_new_and_repeat_visits_after_each_reload(self):
        for index in range(9):
            raw = deepcopy(self.raw); raw['result']['dialogueRows'][index]['candidates'] = []
            with self.subTest(empty_selection=index): self.assertTrue(self.evaluate(raw)['errors'])
        for field, value in [('visits', True), ('visits', 25), ('language', 'eng')]:
            self.assertTrue(self.evaluate(self.change(('result', 'dialogueRows', 0, field), value))['errors'])
        self.raw['result']['dialogueRows'].pop()
        self.assertTrue(self.evaluate()['errors'])

    def test_finale_requires_actual_repeating_three_line_character_dialogue(self):
        prefix = ('result', 'dialogueRows', 0, 'candidates', 0)
        for value in (False, 1):
            self.assertTrue(self.evaluate(self.change((*prefix, 'repeating'), value))['errors'])
        for field, value in [('speaker', 'Character'), ('text', 'THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-0r.ancient')]:
            self.assertTrue(self.evaluate(self.change((*prefix, 'lines', 0, field), value))['errors'])
        self.raw['result']['dialogueRows'][0]['candidates'][0]['lines'].pop()
        self.assertTrue(self.evaluate()['errors'])

    def test_tome_must_keep_existing_rare_card_and_upgrade_values(self):
        for field, value in [('selected', 'VOLIBEAR_R19'), ('rarity', 'Ancient'), ('upgrade', True),
                             ('upgrade', 0), ('restored', 'STRIKE_IRONCLAD'), ('restoredUpgrade', 0),
                             ('restoredRelicCard', 'VOLIBEAR_R19'), ('lightning', 6), ('pool', 4),
                             ('lightning', '9'), ('pool', True)]:
            with self.subTest(field=field):
                self.assertTrue(self.evaluate(self.change(('result', 'tome', field), value))['errors'])

    def test_tome_summary_flags_cannot_replace_native_json_identity_and_saved_property(self):
        for path, value in [
            (('relic', 'id'), 'DUSTY_TOME'), (('relic', 'floor_added_to_deck'), False),
            (('relic', 'props'), {}), (('relic', 'props', 'model_ids', 0, 'name'), 'ancient_card'),
            (('relic', 'props', 'model_ids', 0, 'value'), 'CARD.VOLIBEAR_R19'),
            (('card', 'id'), 'VOLIBEAR_R18'), (('card', 'current_upgrade_level'), 0),
            (('card', 'current_upgrade_level'), True),
        ]:
            with self.subTest(path=path):
                self.assertTrue(self.evaluate(self.change(('result', 'tome', *path), value))['errors'])
        self.raw['result']['tome']['card']['floor_added_to_deck'] = 0
        self.assertTrue(self.evaluate()['errors'], 'Probe must not claim it added the transient reward to master deck')

    def test_inventory_flag_cannot_hide_added_removed_replaced_reordered_or_upgraded_items(self):
        for mutate in (
            lambda inv: inv['deck'].append(dict(instance=12, id='VOLIBEAR_R18', upgrade=1)),
            lambda inv: inv['deck'].pop(),
            lambda inv: inv['deck'][0].update(instance=12),
            lambda inv: inv['deck'].reverse(),
            lambda inv: inv['deck'][0].update(upgrade=1),
            lambda inv: inv['relics'].append(dict(instance=12, id='DUSTY_TOME')),
            lambda inv: inv['relics'][0].update(instance=12),
        ):
            raw = deepcopy(self.raw); mutate(raw['result']['inventoryAfter'])
            self.assertTrue(self.evaluate(raw)['errors'])
        self.raw['result']['inventoryUnchanged'] = 1
        self.assertTrue(self.evaluate()['errors'])

    def test_inventory_snapshots_require_real_finite_unique_object_identities(self):
        for mutate in (
            lambda inv: inv.update(deck=[]), lambda inv: inv.update(relics=[]),
            lambda inv: inv['deck'][0].update(instance=True),
            lambda inv: inv['deck'][0].update(upgrade=False),
            lambda inv: inv['deck'][0].update(id=''),
            lambda inv: inv['deck'][1].update(instance=inv['deck'][0]['instance']),
        ):
            raw = deepcopy(self.raw)
            for phase in ('inventoryBefore', 'inventoryAfter'): mutate(raw['result'][phase])
            self.assertTrue(self.evaluate(raw)['errors'])

    def test_audio_contract_requires_all_five_exact_native_defaults(self):
        for index in range(5):
            for replacement in ('', 'event:/sfx/characters/ironclad/ironclad_attack',
                                'event:/sfx/characters/volibear_character/volibear_character_attack_extra'):
                raw = self.change(('result', 'suppressedNativeAudio', index), replacement)
                with self.subTest(index=index, replacement=replacement): self.assertTrue(self.evaluate(raw)['errors'])
        self.raw['result']['suppressedNativeAudio'].pop()
        self.assertTrue(self.evaluate()['errors'])

    def test_missing_duplicate_malformed_oversized_or_ambiguous_json_receipts_fail(self):
        receipt = gate.PREFIX + json.dumps(self.raw)
        for log in ('', gate.PREFIX + '{', receipt + '\n' + receipt,
                    gate.PREFIX + '{"token":"character-test","token":"character-test"}',
                    gate.PREFIX + '{"pid":NaN}', gate.PREFIX + '[' * 2000,
                    gate.PREFIX + ' ' * 1_000_001, None):
            self.assertTrue(gate.check_log(log, 'character-test', 101)['errors'])
        self.assertEqual(gate.check_log('unrelated native log\n' + receipt + '\nnormal exit',
                                       'character-test', 101)['errors'], [])


if __name__ == '__main__':
    unittest.main()
