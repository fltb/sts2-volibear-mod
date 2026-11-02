"""Exact approved-copy parity; source/fixture check, not native rendering evidence."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from export_text_review import collect


def sections(text, level):
    heading = '#' * level
    return {m[1]: m[2].strip() for m in re.finditer(
        r'^' + heading + r' (.+)\n([\s\S]*?)(?=^#{1,' + str(level) + r'} |\Z)', text, re.M)}


def face_text(template, context):
    template = re.sub(r'\{(\w+)(?::diff\(\))?\}',
                      lambda m: str(context['values'][m[1]]), template)
    template = re.sub(r'\{IfUpgraded:show:([^{}]*)\}',
                      lambda m: m[1] if context['IfUpgraded'] else '', template)
    template = re.sub(r'\{Cards:cond:>0\?([^{}]*)\|\}',
                      lambda m: m[1] if context['values']['Cards'] > 0 else '', template)
    labels = {'Exhaust': '消耗', 'Retain': '保留', 'Innate': '固有', 'Ethereal': '虚无'}
    return template + ''.join(labels[key] + '。' for key in context['keywords'])


class ApprovedCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = (ROOT / 'docs/文案审核.md').read_text(encoding='utf-8')
        cls.groups = {title: sections(body, 4) for title, body in sections(cls.review, 3).items()}
        entries, cls.contexts, _, _ = collect(ROOT)
        cls.text = {entry.id: entry.text for entry in entries}

    def test_all_178_source_faces_costs_and_display_fixture_equal_user_copy(self):
        approved = sections(sections(self.review, 2)['卡牌'], 3)
        fixture = json.loads((ROOT / 'tests/fixtures/card_expectations.json').read_text())['cards']
        self.assertEqual(len(approved), 89)
        checked = 0
        for card in fixture:
            body = approved[card['name_zh']]
            faces = re.findall(r'\*\*(基础|升级) · 费用：([^*]+)\*\*\n([\s\S]*?)(?=\*\*|\Z)', body)
            self.assertEqual(len(faces), 2)
            for index, (_, cost, expected) in enumerate(faces):
                key = 'VOLIBEAR_' + card['card_id'] + ('.upgrade' if index else '.base')
                with self.subTest(face=key):
                    self.assertEqual(str(self.contexts[key]['cost']), cost)
                    self.assertEqual(self.text['cards:' + key + '.title'], card['name_zh'])
                    self.assertEqual(face_text(self.text['cards:' + key + '.description'], self.contexts[key]), expected.strip())
                    self.assertEqual(card['faces'][index]['display_text_zh'], expected.strip())
                    checked += 1
        self.assertEqual(checked, 178)

    def test_power_templates_short_smart_and_permanent_equal_approved(self):
        fixture = json.loads((ROOT / 'tests/fixtures/power_presentation_expected.json').read_text())
        self.assertEqual(len(fixture), 25)
        for spec in fixture:
            body = re.sub(r'X(?!费)', '{Amount}', self.groups['状态与能力'][spec['title']])
            for field in ('description', 'smartDescription'):
                self.assertEqual(self.text['powers:' + spec['model'] + '.' + field], body)
            self.assertEqual(spec['text'], body)
        self.assertEqual(self.text['powers:DomainPower.permanentDescription'], self.groups['状态与能力']['永久领域'])
        self.assertTrue(self.groups['状态与能力']['雷霆余威'].startswith('每回合第2、4、6……次雷伤后'))

    def test_glossary_and_enemy_copy_exact_and_knights_not_demon(self):
        counts = {'关键词': 0, '敌方机制': 0, '领域禁用效果': 0}
        for key, body in self.text.items():
            if key.startswith('static_hover_tips:VOLIBEAR-CONTRIBUTION-'):
                title = self.text[key.replace('static_hover_tips:', 'glossary-label:')]
                group = '领域禁用效果'
            elif key.startswith('static_hover_tips:VOLIBEAR-') and key.endswith('.description'):
                title = self.text.get(key[:-len('description')] + 'title')
                if key.startswith('static_hover_tips:VOLIBEAR-DISABLED.') or title is None:
                    continue
                group = '敌方机制' if '-ENEMY-' in key else '关键词'
            else:
                continue
            with self.subTest(key=key):
                self.assertEqual(body, self.groups[group][title])
                counts[group] += 1
        self.assertEqual(counts, {'关键词': 26, '敌方机制': 9, '领域禁用效果': 17})
        self.assertNotIn('虚无', self.groups['敌方机制']['知识限制'])
        self.assertIn('虚无', self.groups['敌方机制']['骑士限制'])

    def test_four_approved_architect_lines_and_manifest(self):
        approved = re.findall(r'^\*\*(?:建筑师|沃利贝尔)：\*\* (.+)$', self.review, re.M)
        self.assertEqual(len(approved), 4)
        for index, body in enumerate(approved):
            suffix = 'ancient' if index % 2 == 0 else 'char'
            self.assertEqual(self.text[f'ancients:THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-{index}r.{suffix}'], body)
        manifest = json.loads((ROOT / 'src/Volibear/Volibear.json').read_text())
        self.assertEqual(manifest['description'], self.groups['模组菜单']['沃利贝尔 · 不灭狂雷'])


if __name__ == '__main__':
    unittest.main()
