"""Static full-face wording contracts, including native appended keyword text.

This does not replace native catalog/locale-reload verification.
"""
import json
from pathlib import Path
import re
import unittest
from test_direct_cards import append_native_keywords, literal_vars

ROOT = Path(__file__).resolve().parents[1]


def localized_face(body, upgraded):
    values = literal_vars(body)
    if upgraded:
        for key, delta in re.findall(r'UpgradeVar\("(\w+)",\s*(-?\d+)m\)', body):
            values[key] += int(delta)
    text = re.search(r'new CardLoc\("[^"]+",\s*"([^"]+)"', body)[1]
    text = re.sub(r'\{(\w+):diff\(\)\}', lambda m: str(values[m[1]]), text)
    text = re.sub(r'\{Cards:cond:>0\?([^{}]*)\|\}', lambda m: m[1] if values['Cards'] > 0 else '', text)
    return append_native_keywords(text, body, upgraded)


class CatalogTextSourceContracts(unittest.TestCase):
    def test_history_and_token_fourteen_faces_equal_original_fixture(self):
        fixtures = {card['card_id']: card for card in json.loads((ROOT / 'tests/fixtures/card_expectations.json').read_text(encoding='utf-8'))['cards']}
        codes = set()
        for name in ['HistoryEffects.cs', 'BeastTokens.cs']:
            source = (ROOT / 'src/Volibear/Content/Cards' / name).read_text(encoding='utf-8')
            cards = re.findall(r'public sealed class Volibear_([CURT]\d\d) : VolibearCard[^\{]*\{(.*?)(?=\n\[BaseLib|\n/// <summary>|\Z)', source, re.S)
            for code, body in cards:
                codes.add(code)
                for i, face in enumerate(fixtures[code]['faces']):
                    with self.subTest(card=code, upgraded=bool(i)):
                        self.assertEqual(localized_face(body, bool(i)), face['display_text_zh'])
        self.assertEqual(codes, {'C20', 'U07', 'U20', 'U38', 'R14', 'T01', 'T02'})

    def test_native_exhaust_body_is_not_duplicated_or_upgrade_removal_lost(self):
        for name in ['DirectEffects.cs', 'ControlledEffects.cs', 'PreparedEffects.cs', 'HistoryEffects.cs', 'BeastTokens.cs']:
            source = (ROOT / 'src/Volibear/Content/Cards' / name).read_text(encoding='utf-8')
            for raw in re.findall(r'new CardLoc\("[^"]+",\s*"([^"]+)"', source):
                self.assertNotIn('消耗。', raw, name)
        body = 'CanonicalKeywords => [CardKeyword.Exhaust]; RemoveKeyword(CardKeyword.Exhaust);'
        self.assertEqual(append_native_keywords('正文。', body, False), '正文。消耗。')
        self.assertEqual(append_native_keywords('正文。', body, True), '正文。')
        self.assertEqual(append_native_keywords('消耗1张手牌。', '', False), '消耗1张手牌。')


if __name__ == '__main__':
    unittest.main()
