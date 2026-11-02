"""Narrow source-export tests: no game, build, native harness or release gate."""
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import export_text_review as review


EXPECTED_CARDS = set('B01 B02 B03 B04 C01 C02 C03 C04 C05 C06 C07 C08 C09 C10 C11 C12 C13 C14 C15 C17 C18 C19 C20 C21 C22 C24 C25 C26 U02 U03 U04 U05 U06 U07 U08 U10 U11 U12 U13 U14 U15 U17 U19 U20 U21 U23 U24 U25 U26 U27 U28 U29 U31 U32 U34 U35 U36 U37 U38 U39 U40 U41 U42 U43 R01 R02 R05 R06 R07 R08 R09 R10 R12 R13 R14 R16 R17 R18 R21 R23 R24 R25 R27 R28 R29 R30 R31 T01 T02'.split())


class TextReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Compare renders against one source snapshot, not concurrently edited files.
        snapshot = tempfile.TemporaryDirectory()
        cls.addClassCleanup(snapshot.cleanup)
        root = Path(snapshot.name)
        shutil.copytree(review.ROOT / 'src', root / 'src',
                        ignore=shutil.ignore_patterns('bin', 'obj', '.godot'))
        root_patch = patch.object(review, 'ROOT', root)
        root_patch.start()
        cls.addClassCleanup(root_patch.stop)
        cls.entries, cls.contexts, cls.manifest, cls.cards = review.collect()
        cls.by_id = {e.id: e for e in cls.entries}

    def test_exact_89_cards_and_178_independent_faces(self):
        self.assertEqual(set(self.cards), {'VOLIBEAR_' + c for c in EXPECTED_CARDS})
        self.assertEqual(len(self.contexts), 178)
        for card in EXPECTED_CARDS:
            for face in ('base', 'upgrade'):
                for field in ('title', 'description'):
                    self.assertIn(f'cards:VOLIBEAR_{card}.{face}.{field}', self.by_id)
        self.assertEqual(Counter(e.category for e in self.entries)['card-faces'], 356)

    def test_values_costs_keywords_and_conditional_templates(self):
        self.assertEqual(self.contexts['VOLIBEAR_B01.base']['values']['Damage'], 6)
        self.assertEqual(self.contexts['VOLIBEAR_B01.upgrade']['values']['Damage'], 9)
        self.assertEqual(self.contexts['VOLIBEAR_U03.upgrade']['values']['Decay'], 3)
        self.assertEqual(self.contexts['VOLIBEAR_R01.upgrade']['cost'], 2)
        self.assertEqual(self.contexts['VOLIBEAR_U31.base']['cost'], 'X')
        self.assertEqual(self.contexts['VOLIBEAR_R17.upgrade']['cost'], 'X')
        self.assertIn('Exhaust', self.contexts['VOLIBEAR_U14.base']['keywords'])
        self.assertNotIn('Exhaust', self.contexts['VOLIBEAR_U14.upgrade']['keywords'])
        self.assertFalse(self.contexts['VOLIBEAR_R17.base']['IfUpgraded'])
        self.assertTrue(self.contexts['VOLIBEAR_R17.upgrade']['IfUpgraded'])
        self.assertIn('{IfUpgraded:show:＋1}', self.by_id['cards:VOLIBEAR_R17.upgrade.description'].text)
        self.assertIn('{Cards:cond:>0?', self.by_id['cards:VOLIBEAR_R14.base.description'].text)

    def test_unique_ids_and_all_source_locations_resolve(self):
        self.assertEqual(len(self.by_id), len(self.entries))
        for e in self.entries:
            text = (review.ROOT / e.source).read_text(encoding='utf-8-sig')
            self.assertGreater(e.line, 0)
            self.assertLessEqual(e.line, len(text.splitlines()))
            # Current sources use unescaped single-line Chinese literals.
            self.assertIn(e.text, text.splitlines()[e.line - 1], e.id)

    def test_every_chinese_csharp_literal_is_accounted_for(self):
        exported = {(e.source, e.line, e.text) for e in self.entries}
        for rel, _ in self.manifest:
            if not rel.endswith('.cs'):
                continue
            text = (review.ROOT / rel).read_text(encoding='utf-8-sig')
            _, literals = review.scan(text)
            for lit in literals:
                if review.HAN.search(lit.value):
                    self.assertIn((rel, text.count('\n', 0, lit.start)+1, lit.value), exported)

    def test_required_non_card_surfaces_and_mod_menu(self):
        for ident in ('characters:VOLIBEAR_CHARACTER.banter.dead.endTurnPing',
                      'ancients:THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-2r.ancient',
                      'ancients:THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-3r.char',
                      'relics:VOLIBEAR_HUNTERS_HEART.flavor',
                      'relics:VOLIBEAR_IMMORTAL_HEART.flavor',
                      'relics:SEA_GLASS.VOLIBEAR_CHARACTER.title',
                      'powers:DomainPower.permanentDescription',
                      'static_hover_tips:VOLIBEAR-SUPPRESSION.description',
                      'static_hover_tips:VOLIBEAR-ENGAGE_STATE.spent',
                      'cards:VOLIBEAR_U43.beastSelectionPrompt',
                      'json:src/Volibear/Volibear.json:/description',
                      'ui:src/Volibear/Presentation/volibear_energy.tscn:text:1'):
            self.assertIn(ident, self.by_id)
        self.assertIn('{Enemies}', self.by_id['static_hover_tips:VOLIBEAR-ENGAGE_STATE.spent'].text)
        self.assertEqual(Counter(e.category for e in self.entries)['ancients'], 4)

    def test_enemy_and_contribution_namespaces_match_runtime(self):
        enemy = 'static_hover_tips:VOLIBEAR-ENEMY-CARD_THEFT.description'
        contribution = 'static_hover_tips:VOLIBEAR-CONTRIBUTION-CARD_THEFT'
        self.assertIn(enemy, self.by_id)
        self.assertIn(contribution, self.by_id)
        self.assertNotEqual(self.by_id[enemy].text, self.by_id[contribution].text)
        self.assertNotIn('static_hover_tips:VOLIBEAR-CARD_THEFT.description', self.by_id)
        self.assertNotIn(contribution + '.title', self.by_id)
        self.assertFalse(any(e.id.startswith('glossary-match:CARD_THEFT') for e in self.entries))
        self.assertEqual(sum(e.id.startswith('static_hover_tips:VOLIBEAR-ENEMY-')
                             for e in self.entries), 18)
        self.assertEqual(sum(e.id.startswith('static_hover_tips:VOLIBEAR-CONTRIBUTION-')
                             for e in self.entries), 17)

    def test_manifest_covers_all_source_files_and_matches_bytes(self):
        expected = {p.relative_to(review.ROOT).as_posix()
                    for p in (review.ROOT / 'src/Volibear').rglob('*')
                    if p.suffix in {'.cs', '.gd', '.tscn', '.tres', '.json'}
                    and not {'bin', 'obj'}.intersection(p.parts)}
        self.assertEqual({rel for rel, _ in self.manifest}, expected)
        for rel, digest in self.manifest:
            self.assertEqual(hashlib.sha256((review.ROOT / rel).read_bytes()).hexdigest(), digest)

    def test_scanner_ignores_comments_and_balances_string_braces(self):
        source = '// "伪造"\nclass Demo { string x = "真实{Amount}\\n\\\""; /* } "假的" */ string y = @"多""行"; }'
        mask, literals = review.scan(source)
        self.assertEqual([v.value for v in literals], ['真实{Amount}\n"', '多"行'])
        self.assertEqual(list(review.class_blocks(mask))[0][0], 'Demo')
        self.assertEqual(len(mask), len(source))

    def test_localization_expressions_fail_closed(self):
        text = '"前" + suffix'
        _, literals = review.scan(text)
        with self.assertRaisesRegex(ValueError, 'one literal'):
            review.literal_at(text, literals, 0, len(text))

    def test_markdown_preserves_nested_placeholders_and_empty_edit_cells(self):
        text = '{Cards:cond:>0?抽{Cards:diff()}张牌。|}\n[color=red]雷伤[/color] <tag>'
        self.assertEqual(html.unescape(review.cell(text).replace('<br>', '\n')), text)
        row = review.row(review.Entry('stable', 'ui', 'source.cs', 7, text))
        self.assertEqual(len(row.split('|')), 6)
        self.assertEqual(row.split('|')[-2].strip(), '')

    def test_deterministic_render_and_all_rows_blank(self):
        first = review.render()
        self.assertEqual(first, review.render())
        rows = [line for line in first.splitlines() if line.startswith('| `')]
        self.assertEqual(len(rows), len(self.entries))
        for row in rows:
            self.assertEqual(len(row.split('|')), 6)
            self.assertEqual(row.split('|')[-2].strip(), '')

    def test_default_export_freezes_and_check_never_writes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(review, 'render', return_value='snapshot\n'):
            path = review.export(directory)
            before = path.stat().st_mtime_ns
            with self.assertRaisesRegex(ValueError, '冻结'):
                review.export(directory)
            review.export(directory, check=True)
            self.assertEqual(path.stat().st_mtime_ns, before)
            with patch.object(review, 'render', return_value='changed\n'):
                with self.assertRaisesRegex(ValueError, '未写入'):
                    review.export(directory, check=True)
            self.assertEqual(path.read_text(), 'snapshot\n')

    def test_check_preserves_crlf_source_snippets_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(review, 'render', return_value='source\r\ntext\n'):
            path = review.export(directory)
            self.assertEqual(path.read_bytes(), b'source\r\ntext\n')
            review.export(directory, check=True)

    def test_final_refresh_requires_blank_edits(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(review, 'render', return_value='final\n'):
            path = Path(directory) / review.OUTPUT
            path.parent.mkdir()
            for edited in ('| `id` | source | original | 人工修改 |\n',
                           '| `id` | source | original | 含|竖线 |\n'):
                path.write_text(edited)
                with self.assertRaisesRegex(ValueError, '拒绝覆盖'):
                    review.export(directory, replace_final=True)
                self.assertEqual(path.read_text(), edited)
            path.write_text('| `id` | source | original |  |\n')
            review.export(directory, replace_final=True)
            self.assertEqual(path.read_text(), 'final\n')


if __name__ == '__main__':
    unittest.main()
