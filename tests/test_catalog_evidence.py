"""Adversarial tests of the independent catalog comparator.

These rows are SYNTHETIC comparator test input, never native engine evidence.
Only CardCatalogProbe's actual process output may enter the runner's native gate.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('catalog_evidence', ROOT / 'tools/catalog_evidence.py')
CATALOG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CATALOG)
TOKEN = 'synthetic-comparator-test-only'


def synthetic_observation():
    cards = json.loads((ROOT / 'tests/fixtures/card_expectations.json').read_text(encoding='utf-8'))['cards']
    result = dict(schemaVersion=1, token=TOKEN, scenario='catalog', acceptance='catalog-not-gameplay-or-payment',
                  completed=True, testMode=False, discovery=CATALOG.DISCOVERY, api=CATALOG.API,
                  gameVersion='v0.107.1', gameCommit='59260271',
                  startLanguage='zhs', language='zhs', reloadSequence=['zhs', 'eng', 'zhs'],
                  ownerRef=777, character='VolibearCharacter', ownerPowerCount=0,
                  energyBefore=3, energyAfter=3, deckBefore=['VOLIBEAR_B01'] * 10, deckAfter=['VOLIBEAR_B01'] * 10,
                  registry=[], poolIds=[], rarityCounts={'Basic': 4, 'Common': 24, 'Uncommon': 36, 'Rare': 23, 'Token': 2},
                  faces=[], portraits=[], reloaded=[], errors=[])
    for card in cards:
        model = 'VOLIBEAR_' + card['card_id']
        native = 'Volibear.Content.Volibear_' + card['card_id']
        result['registry'].append(dict(modelId=model, nativeType=native, canonical=True, resolvedSame=True, inPool=True,
                                       type=card['type'].title(), rarity=card['rarity'].title()))
        result['poolIds'].append(model)
        initial = ['Exhaust'] if card['faces'][0]['self_exhaust'] else []
        for face in card['faces']:
            text = dict(titleKey=model + '.title', descriptionKey=model + '.description', titleExists=True, descriptionExists=True,
                        rawTitle=card['name_zh'], rawDescription=face['display_text_zh'],
                        title=card['name_zh'] + ('+' if face['upgrade'] else ''), description=face['display_text_zh'])
            cost = 0 if face['cost'] == 'X' else face['cost']
            result['faces'].append(dict(modelId=model, nativeType=native, cardRef=len(result['faces']) + 1, ownerRef=777,
                                       ownerMatches=True, mutable=True, upgrade=face['upgrade'], upgradeLevel=int(face['upgrade']),
                                       type=card['type'].title(), rarity=card['rarity'].title(), target=CATALOG.TARGETS[card['play_target']],
                                       initialKeywords=initial, keywords=['Exhaust'] if face['self_exhaust'] else [],
                                       costsX=face['cost'] == 'X', canonicalCost=0 if card['faces'][0]['cost'] == 'X' else card['faces'][0]['cost'],
                                       localCost=cost, allCost=cost,
                                       vars={'SyntheticTestValue': dict(kind='DynamicVar', baseValue=1, enchantedValue=1, previewValue=1)},
                                       text=text))
            result['reloaded'].append(dict(modelId=model, upgrade=face['upgrade'], text=copy.deepcopy(text)))
        root = 'res://VolibearArt/cards/production/sts2/Volibear/images/card_portraits/'
        result['portraits'].append(dict(modelId=model,
             small=dict(path=root + card['card_id'].lower() + '.png', exists=True, decoded=True, width=250, height=190, error=None),
             big=dict(path=root + 'big/' + card['card_id'].lower() + '.png', exists=True, decoded=True, width=1000, height=760, error=None)))
    return result


class CatalogEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.result = synthetic_observation()

    def face(self, code, upgraded=False):
        return next(x for x in self.result['faces'] if x['modelId'] == 'VOLIBEAR_' + code and x['upgrade'] is upgraded)

    def check_rejected(self):
        self.assertFalse(CATALOG.validate_catalog_result(self.result, TOKEN))
        self.assertTrue(CATALOG.catalog_errors(self.result, TOKEN))

    def test_synthetic_valid_comparator_input(self):
        self.assertEqual([], CATALOG.catalog_errors(self.result, TOKEN))

    def test_stale_run_token_is_not_evidence(self):
        self.assertFalse(CATALOG.validate_catalog_result(self.result, 'different-native-run'))

    def test_missing_and_duplicate_reports_fail(self):
        line = CATALOG.PREFIX + json.dumps(self.result)
        self.assertTrue(CATALOG.catalog_evidence(line, TOKEN)[1])
        self.assertFalse(CATALOG.catalog_evidence('', TOKEN)[1])
        self.assertFalse(CATALOG.catalog_evidence(line + '\n' + line, TOKEN)[1])
        self.assertFalse(CATALOG.catalog_evidence(CATALOG.PREFIX + '{bad json', TOKEN)[1])

    def test_missing_registered_card_fails(self):
        self.result['registry'].pop()
        self.check_rejected()

    def test_duplicate_registered_card_fails_even_with_89_rows(self):
        self.result['registry'][-1] = copy.deepcopy(self.result['registry'][0])
        self.check_rejected()

    def test_unresolved_or_noncanonical_registration_fails(self):
        for key in ('canonical', 'resolvedSame', 'inPool'):
            with self.subTest(key=key):
                self.result = synthetic_observation()
                self.result['registry'][0][key] = False
                self.check_rejected()

    def test_foreign_or_extra_pool_card_fails(self):
        self.result['poolIds'].append('STRIKE_IRONCLAD')
        self.check_rejected()

    def test_wrong_rarity_distribution_fails(self):
        self.result['rarityCounts']['Common'] = 25
        self.check_rejected()

    def test_177_faces_is_not_178(self):
        self.result['faces'].pop()
        self.check_rejected()

    def test_duplicate_upgraded_face_is_not_second_face(self):
        self.result['faces'][-1] = copy.deepcopy(self.result['faces'][-2])
        self.check_rejected()

    def test_same_mutable_entity_reused_for_all_faces_rejected(self):
        for face in self.result['faces']:
            face['cardRef'] = 99
        self.check_rejected()

    def test_owner_and_mutability_must_be_real(self):
        for key, value in [('ownerMatches', False), ('mutable', False), ('ownerRef', 778), ('upgradeLevel', 1)]:
            with self.subTest(key=key):
                self.result = synthetic_observation()
                self.result['faces'][0][key] = value
                self.check_rejected()

    def test_runtime_type_target_and_rarity_are_checked(self):
        for key, value in [('type', 'Skill'), ('target', 'AllEnemies'), ('rarity', 'Rare')]:
            with self.subTest(key=key):
                self.result = synthetic_observation()
                self.face('B01')[key] = value
                self.check_rejected()

    def test_upgraded_cost_is_not_canonical_cost(self):
        self.face('C14', True)['allCost'] += 1
        self.check_rejected()

    def test_x_cost_flag_and_native_canonical_zero_checked(self):
        self.face('U31')['costsX'] = False
        self.check_rejected()
        self.result = synthetic_observation()
        self.face('R17')['canonicalCost'] = -1
        self.check_rejected()

    def test_native_exhaust_cache_upgrade_regression(self):
        for code in ('C14', 'U14'):
            with self.subTest(code=code):
                self.result = synthetic_observation()
                self.assertEqual(['Exhaust'], self.face(code, True)['initialKeywords'])
                self.assertEqual([], self.face(code, True)['keywords'])
                self.face(code, True)['keywords'] = ['Exhaust']
                self.check_rejected()

    def test_not_reading_keywords_before_upgrade_rejected(self):
        self.face('C14', True)['initialKeywords'] = []
        self.check_rejected()

    def test_duplicate_native_keyword_suffix_not_normalized_away(self):
        self.face('U20')['text']['description'] += '\n[gold]消耗。[/gold]'
        self.check_rejected()

    def test_only_known_display_tags_and_whitespace_are_removed(self):
        self.assertEqual('造成6伤害。', CATALOG.display_text('[blue]造成6[/blue]伤害。\n'))
        self.assertEqual('造成7伤害。', CATALOG.display_text('[color=#ff0000]造成7[/color]伤害。'))
        self.assertIn('[unknown]', CATALOG.display_text('[unknown]text[/unknown]'))
        self.assertIn('[img]', CATALOG.display_text('[img]arbitrary-resource[/img]'))
        self.face('B01')['text']['description'] = '[blue]造成7[/blue]伤害。'
        self.check_rejected()

    def test_formatted_chinese_not_raw_template_is_required(self):
        self.face('B01')['text']['description'] = '造成{Damage:diff()}伤害。'
        self.check_rejected()

    def test_six_display_only_override_cards_stay_exact(self):
        for code in ('U41', 'U42', 'U43', 'R27', 'R29', 'R30'):
            with self.subTest(code=code):
                self.result = synthetic_observation()
                face = self.face(code)
                self.assertIn('下次打出时为0费', face['text']['description'])
                face['text']['description'] = face['text']['description'].replace('下次打出时为0费', '下次打出时减费1')
                self.check_rejected()

    def test_language_reload_must_execute_full_sequence(self):
        self.result['reloadSequence'] = ['zhs']
        self.check_rejected()

    def test_missing_inline_strings_after_language_reload_rejected(self):
        self.result['reloaded'][-1]['text']['titleExists'] = False
        self.result['reloaded'][-1]['text']['title'] = '[MissingLoc:VOLIBEAR_T02.title]'
        self.check_rejected()

    def test_english_keyword_after_reload_rejected(self):
        self.result['reloaded'][-1]['text']['description'] += ' Exhaust.'
        self.check_rejected()

    def test_resource_path_alone_is_not_decode_evidence(self):
        self.result['portraits'][0]['small']['decoded'] = False
        self.check_rejected()

    def test_missing_big_portrait_or_wrong_dimensions_rejected(self):
        self.result['portraits'][-1]['big']['exists'] = False
        self.check_rejected()
        self.result = synthetic_observation()
        self.result['portraits'][0]['big']['width'] = 250
        self.check_rejected()

    def test_dynamic_vars_are_raw_finite_values_not_fake_labels(self):
        self.result['faces'][0]['vars']['SyntheticTestValue']['baseValue'] = float('nan')
        self.check_rejected()

    def test_completed_and_forged_pass_flag_cannot_override_oracle(self):
        self.result['passed'] = True
        self.face('B01')['text']['title'] = '错误标题'
        self.check_rejected()

    def test_catalog_cannot_claim_payment_or_change_player_state(self):
        self.result['acceptance'] = 'normal-input-payment'
        self.check_rejected()
        self.result = synthetic_observation()
        self.result['energyAfter'] = 0
        self.check_rejected()

    def test_bool_number_confusion_and_malformed_input_fail_closed(self):
        self.result['faces'][0]['allCost'] = True
        self.check_rejected()
        for malformed in (None, [], {}, {'faces': '178'}):
            self.assertFalse(CATALOG.validate_catalog_result(malformed, TOKEN))


if __name__ == '__main__':
    unittest.main()
