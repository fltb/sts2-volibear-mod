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
    def test_native_starter_tags_and_formula_block_metadata(self):
        # Native starter/enchantment consumers inspect metadata, not the Chinese
        # name or OnPlay body. BaseLib 3.4.7 infers GainsBlock only from BlockVar or
        # CalculatedBlockVar, so formula-only and per-material block need a flag.
        cards = {}
        for path in (ROOT / 'src/Volibear/Content/Cards').glob('*.cs'):
            source = path.read_text(encoding='utf-8')
            cards.update(re.findall(
                r'public sealed class Volibear_([BCURT]\d\d) : VolibearCard[^\{]*\{(.*?)(?=\n\[BaseLib|\n/// <summary>|\Z)',
                source, re.S))
        catalog = json.loads((ROOT / 'docs/research/sts2-mod-research/content-cards.json').read_text(encoding='utf-8'))
        self.assertEqual(set(cards), {card['code'] for card in catalog['cards']})
        expected_strikes = {card['code'] for card in catalog['cards'] if card['strike_tag']}
        actual_strikes = {code for code, body in cards.items()
                          if 'CardTag.Strike' in body.split('protected override async Task', 1)[0]}
        self.assertEqual(actual_strikes, expected_strikes)
        self.assertRegex(cards['B01'], r'CanonicalTags\s*=>\s*\[CardTag.Strike\]')
        self.assertRegex(cards['B02'], r'CanonicalTags\s*=>\s*\[CardTag.Defend\]')
        self.assertEqual({code for code, body in cards.items() if 'CardTag.Defend' in body}, {'B02'})
        for code in ('U27', 'R21', 'R27'):
            with self.subTest(card=code):
                self.assertIn('public override bool GainsBlock => true;', cards[code])

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
