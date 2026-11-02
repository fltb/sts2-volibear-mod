#!/usr/bin/env python3
"""Export source text, never load the game or rewrite production localization.

Default is create-only. --check is read-only; --replace-final is the explicit,
one-time end-of-implementation refresh (refuses filled-in review cells).
The small C# scanner understands comments/string boundaries, not arbitrary C#:
unsupported localization expressions fail closed instead of dropping text.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path('docs/TEXT_REVIEW.md')
HAN = re.compile(r'[\u3400-\u9fff]')
LEX = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|(?:\$@|@\$|@)"(?:""|[^"])*"|\$?"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
STRING = re.compile(r'^(?:\$@|@\$|@|\$)?"')


@dataclass(frozen=True)
class Literal:
    start: int
    end: int
    value: str


@dataclass(frozen=True)
class Entry:
    id: str
    category: str
    source: str
    line: int
    text: str


def scan(text):
    """Return a same-length code mask and literals; comment contents never count."""
    mask = list(text)
    literals = []
    for match in LEX.finditer(text):
        raw = match.group()
        if STRING.match(raw):
            first = raw.index('"')
            body = raw[first + 1:-1]
            if '@' in raw[:first]:
                value = body.replace('""', '"')
            else:
                # C# normal escapes used by these sources; preserve actual Unicode.
                escapes = {'0': '\0', 'a': '\a', 'b': '\b', 'f': '\f', 'n': '\n',
                           'r': '\r', 't': '\t', 'v': '\v', '"': '"', "'": "'", '\\': '\\'}
                def unescape(m):
                    code = m[1]
                    if code[0] in 'uUx':
                        return chr(int(code[1:], 16))
                    if code not in escapes:
                        raise ValueError(f'Unsupported string escape: {code}')
                    return escapes[code]
                value = re.sub(r'\\(u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|x[0-9a-fA-F]{1,4}|.)', unescape, body)
            literals.append(Literal(match.start(), match.end(), value))
        mask[match.start():match.end()] = ['\n' if c == '\n' else ' ' for c in raw]
    return ''.join(mask), literals


def matching(mask, start, opening='(', closing=')'):
    depth = 0
    for pos in range(start, len(mask)):
        if mask[pos] == opening:
            depth += 1
        elif mask[pos] == closing:
            depth -= 1
            if depth == 0:
                return pos
    raise ValueError(f'Unbalanced {opening} at {start}')


def arguments(mask, start, end):
    result, depth, previous = [], 0, start + 1
    for pos in range(start + 1, end):
        c = mask[pos]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == ',' and depth == 0:
            result.append((previous, pos))
            previous = pos + 1
    result.append((previous, end))
    return result


def literal_at(text, literals, start, end):
    values = [v for v in literals if start <= v.start and v.end <= end]
    if len(values) != 1 or text[start:values[0].start].strip() or text[values[0].end:end].strip():
        raise ValueError(f'Localization must be one literal, got {text[start:end]!r}')
    return values[0]


def class_blocks(mask):
    for m in re.finditer(r'\bclass\s+(\w+)[^{;]*\{', mask):
        begin = m.end() - 1
        yield m[1], m.start(), begin, matching(mask, begin, '{', '}')


def member_expression(text, mask, name):
    m = re.search(r'\b' + name + r'\b[^=;{]*=>', mask)
    if not m:
        return ''
    end = mask.index(';', m.end())
    return text[m.end():end].strip()


def upgrade_body(text, mask):
    m = re.search(r'\bOnUpgrade\s*\(\s*\)\s*(=>|\{)', mask)
    if not m:
        raise ValueError('Card missing OnUpgrade')
    if m[1] == '=>':
        return text[m.end():mask.index(';', m.end())] + ';'
    return text[m.end():matching(mask, m.end()-1, '{', '}')].strip()


def card_context(text, mask, upgraded):
    constructor = re.search(r':\s*base\(\s*(\d+),\s*CardType\.(\w+),\s*CardRarity\.(\w+),\s*TargetType\.(\w+)', mask)
    if not constructor:
        raise ValueError('Unsupported card constructor')
    cost, kind, rarity, target = constructor.groups()
    cost = int(cost)
    variables = member_expression(text, mask, 'CanonicalVars')
    keywords = re.findall(r'CardKeyword\.(\w+)', member_expression(text, mask, 'CanonicalKeywords'))
    values = {}
    for m in re.finditer(r'new\s+(\w+Var)(?:<[^>]+>)?\(\s*(?:"([^"]+)",\s*)?(-?\d+)(?:m)?\b', variables):
        values[m[2] or m[1][:-3]] = int(m[3])
    upgrade = upgrade_body(text, mask)
    supported = r'UpgradeVar\("[^"]+",\s*-?\d+m?\)\s*;|EnergyCost\.UpgradeBy\(-?\d+\)\s*;|(?:Remove|Add)Keyword\(CardKeyword\.\w+\)\s*;'
    remaining = re.sub(supported, '', upgrade)
    remaining = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/', '', remaining)
    if remaining.strip():
        raise ValueError(f'Unsupported upgrade expression: {remaining.strip()}')
    if upgraded:
        for key, delta in re.findall(r'UpgradeVar\("([^"]+)",\s*(-?\d+)m?\)', upgrade):
            if key not in values:
                raise ValueError(f'Unknown upgrade variable {key}')
            values[key] += int(delta)
        for delta in re.findall(r'EnergyCost\.UpgradeBy\((-?\d+)\)', upgrade):
            cost += int(delta)
        for key in re.findall(r'RemoveKeyword\(CardKeyword\.(\w+)\)', upgrade):
            keywords.remove(key)
        keywords += re.findall(r'AddKeyword\(CardKeyword\.(\w+)\)', upgrade)
    if re.search(r'HasEnergyCostX\s*=>\s*true', mask):
        cost = 'X'
    return {'cost': cost, 'type': kind, 'rarity': rarity, 'target': target,
            'keywords': keywords, 'values': values, 'vars_source': variables,
            'upgrade_source': upgrade, 'IfUpgraded': upgraded}


def collect(root=None):
    root = Path(ROOT if root is None else root)
    entries, contexts, manifest, claimed = [], {}, [], set()
    sources = {}
    for path in sorted((root / 'src/Volibear').rglob('*')):
        if path.suffix not in {'.cs', '.gd', '.tscn', '.tres', '.json'} or any(p in {'bin', 'obj'} for p in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
        mask, literals = scan(text) if path.suffix == '.cs' else ('', [])
        sources[rel] = (text, mask, literals)
        manifest.append((rel, sha256(raw).hexdigest()))

    def add(ident, category, rel, literal):
        text = sources[rel][0]
        entries.append(Entry(ident, category, rel, text.count('\n', 0, literal.start) + 1, literal.value))
        claimed.add((rel, literal.start))

    # Explicit tables retain exact table/key IDs, including compatibility aliases.
    rel = 'src/Volibear/Content/VolibearLoc.cs'
    text, mask, literals = sources[rel]
    table = None
    for m in re.finditer(r'\[\s*"([^"]+)"\s*\]\s*=\s*(new\b|"(?:\\.|[^"\\])*")', text):
        if mask[m.start()] != '[':
            continue
        if m[2] == 'new':
            table = m[1]
        else:
            lit = literal_at(text, literals, m.start(2), m.end(2))
            add(f'{table}:{m[1]}', table, rel, lit)

    # Model-owned strings and optional named prompt/description tuples.
    cards = {}
    for rel, (text, mask, literals) in sources.items():
        if not rel.endswith('.cs'):
            continue
        blocks = list(class_blocks(mask))
        for m in re.finditer(r'new\s+(CardLoc|PowerLoc|RelicLoc)\s*\(', mask):
            owner = next((b for b in reversed(blocks) if b[2] < m.start() < b[3]), None)
            if owner is None:
                raise ValueError(f'Localization outside class: {rel}')
            model = owner[0]
            kind = {'CardLoc': 'cards', 'PowerLoc': 'powers', 'RelicLoc': 'relics'}[m[1]]
            key = model.upper() if kind == 'cards' else model
            if kind == 'relics' and model == 'ImmortalHeart':
                key = 'VOLIBEAR_IMMORTAL_HEART'
            args = arguments(mask, m.end()-1, matching(mask, m.end()-1))
            fields = ('title', 'description') if kind == 'cards' else ('title', 'description', 'smartDescription' if kind == 'powers' else 'flavor')
            for i, (start, end) in enumerate(args):
                if i < len(fields):
                    field, lit = fields[i], literal_at(text, literals, start, end)
                else:
                    start += len(text[start:end]) - len(text[start:end].lstrip())
                    if mask[start] != '(':
                        raise ValueError(f'Unsupported named localization: {rel}:{start}')
                    pair = arguments(mask, start, matching(mask, start))
                    if len(pair) != 2:
                        raise ValueError('Named localization must be a pair')
                    field = literal_at(text, literals, *pair[0]).value
                    lit = literal_at(text, literals, *pair[1])
                add(f'{kind}:{key}.{field}', kind, rel, lit)
        for model, start, begin, end in blocks:
            if re.fullmatch(r'Volibear_[BCURT]\d\d', model):
                key = model.upper()
                if key in cards:
                    raise ValueError(f'Duplicate card {key}')
                cards[key] = (rel, text.count('\n', 0, start)+1)
                body, body_mask = text[begin:end+1], mask[begin:end+1]
                for face in ('base', 'upgrade'):
                    contexts[f'{key}.{face}'] = card_context(body, body_mask, face == 'upgrade')

    rel = 'src/Volibear/Content/MechanicGlossary.cs'
    text, mask, literals = sources[rel]
    # Separate runtime localization namespaces; enemy/contribution keys can overlap.
    for group, prefix in (('Entries', 'VOLIBEAR-'), ('EnemyEntries', 'VOLIBEAR-ENEMY-'),
                          ('SuppressedContributions', 'VOLIBEAR-CONTRIBUTION-')):
        declaration = re.search(r'\b' + group + r'\b.*?=\s*(?:new\s+\w+\[\]\s*)?([\[{])', mask, re.S)
        if declaration is None:
            if group == 'Entries':
                raise ValueError('Missing glossary Entries')
            continue
        start = declaration.start(1)
        opening = mask[start]
        end = matching(mask, start, opening, ']' if opening == '[' else '}')
        for m in re.finditer(r'\bnew\s*\(', mask[start:end]):
            args_start = start + m.end() - 1
            args = arguments(mask, args_start, matching(mask, args_start))
            vals = [literal_at(text, literals, *a) for a in args]
            if len(vals) < 3:
                raise ValueError('Glossary entry missing fields')
            key = prefix + vals[0].value
            if group == 'SuppressedContributions':
                add(f'static_hover_tips:{key}', 'keywords', rel, vals[2])
                # Human label is catalog metadata, not a generated localization key.
                add(f'glossary-label:{key}', 'text-reference', rel, vals[1])
            else:
                for field, lit in zip(('title', 'description'), vals[1:3]):
                    add(f'static_hover_tips:{key}.{field}', 'keywords', rel, lit)
            if group == 'Entries':
                for i, lit in enumerate(vals[3:]):
                    add(f'glossary-match:{vals[0].value}.{i}', 'keyword-match', rel, lit)
    for m in re.finditer(r'result\.Add\s*\(', mask):
        args = arguments(mask, m.end()-1, matching(mask, m.end()-1))
        # Generated key expressions are represented by the glossary rows above.
        if '+' in text[args[0][0]:args[0][1]]:
            continue
        key = literal_at(text, literals, *args[0]).value
        add('static_hover_tips:' + key, 'ui', rel, literal_at(text, literals, *args[1]))

    # Exhaustive Han-literal backstop: retain references too, explicitly labelled.
    # A new hardcoded Chinese UI string cannot silently disappear from export.
    for rel, (text, mask, literals) in sources.items():
        counts = Counter()
        for lit in literals:
            if (rel, lit.start) in claimed or not HAN.search(lit.value):
                continue
            owner = next((b[0] for b in reversed(list(class_blocks(mask))) if b[2] < lit.start < b[3]), 'file')
            line = text[text.rfind('\n', 0, lit.start)+1:text.find('\n', lit.end) if '\n' in text[lit.end:] else len(text)]
            category = 'text-reference' if any(s in line for s in ('ForText(', '.Contains(')) else 'additional'
            stem = f'literal:{rel}:{owner}'
            counts[stem] += 1
            add(stem + f':{counts[stem]}', category, rel, lit)
        if rel.endswith('.json'):
            def leaves(value, pointer=''):
                if isinstance(value, dict):
                    for key, child in value.items():
                        yield from leaves(child, pointer + '/' + key.replace('~', '~0').replace('/', '~1'))
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        yield from leaves(child, pointer + '/' + str(index))
                elif isinstance(value, str):
                    yield pointer, value
            for pointer, value in leaves(json.loads(text)):
                encoded = json.dumps(value, ensure_ascii=False)
                pos = text.find(encoded)
                if pos < 0:
                    raise ValueError(f'JSON literal source cannot be located: {rel}:{pointer}')
                category = 'mod-menu' if pointer in ('/name', '/description', '/author', '/version') else 'metadata'
                add(f'json:{rel}:{pointer}', category, rel, Literal(pos, pos+len(encoded), value))
        if rel.endswith(('.gd', '.tscn', '.tres')):
            # Label properties (all languages) and any Han string in resource scripts.
            # Verification-only scripts are not shipped; inventory still includes them.
            if Path(rel).name.startswith('verify_'):
                continue
            seen = Counter()
            for m in re.finditer(r'"(?:\\.|[^"\\])*"', text):
                value = json.loads(m[0])
                prefix = text[text.rfind('\n', 0, m.start())+1:m.start()]
                if HAN.search(value) or re.search(r'\b(?:text|tooltip_text)\s*=\s*$', prefix):
                    prop = re.search(r'(\w+)\s*=\s*$', prefix)
                    label = prop[1] if prop else sha256(value.encode()).hexdigest()[:12]
                    seen[label] += 1
                    add(f'ui:{rel}:{label}:{seen[label]}', 'ui', rel, Literal(m.start(), m.end(), value))

    by_id = {e.id: e for e in entries}
    if len(by_id) != len(entries):
        raise ValueError('Duplicate text IDs')
    if len(cards) != 89:
        raise ValueError(f'Expected 89 cards, found {len(cards)}')
    # Turn each card's text into two separately editable faces; keep prompts once.
    for key, (rel, line) in sorted(cards.items()):
        for field in ('title', 'description'):
            ident = f'cards:{key}.{field}'
            if ident not in by_id:
                raise ValueError(f'Missing card text {ident}')
            entry = by_id[ident]
            entries.remove(entry)
            for face in ('base', 'upgrade'):
                entries.append(Entry(f'cards:{key}.{face}.{field}', 'card-faces', entry.source, entry.line, entry.text))
    entries.sort(key=lambda e: (e.category, e.id))
    return entries, contexts, manifest, cards


def cell(value):
    # HTML entities protect table delimiters and markup while preserving placeholders.
    return html.escape(str(value), quote=False).replace('|', '&#124;').replace('\n', '<br>').replace('\r', '&#13;')


def source_link(path, line=None):
    suffix = f'#L{line}' if line else ''
    return f'[{Path(path).name}{":"+str(line) if line else ""}](<../{path}{suffix}>)'


def render(root=ROOT):
    entries, contexts, manifest, cards = collect(root)
    counts = Counter(e.category for e in entries)
    out = ['# 当前 Mod 全部游戏文本审核', '',
           '> 初次导出快照；实施期间冻结。所有实施结束后由 Lead 统一执行一次最终再导出。', '',
           '仅填写“修改”栏；空白表示尚未提出修改。稳定 ID 用于后续人工回填，工具不修改生产文本。',
           '原文来自当前生产源码，不用设计卡表或旧资产预览替代。占位符、条件分支、富文本标记原样保留；表格中的 HTML 实体仅作 Markdown 转义。',
           '基础/升级均独立列出：模板相同仍保留两行；数值、费用、关键词与 IfUpgraded 上下文见各卡。升级名称的原生“+”、原版类型/关键词翻译由游戏追加，不伪造为 Mod 原文。',
           '状态以 C# 类名作稳定审核 ID（不是推测的原生 ModelId）；其它项优先用定位表/键。未归类中文字符串自动收入补充项，匹配用词单独列出。', '',
           '## 覆盖与计数', '', f'- 卡牌：{len(cards)}；基础/升级牌面：{len(contexts)}；牌面标题/描述字段：{counts["card-faces"]}。',
           f'- 审核字段合计：{len(entries)}；扫描生产源文件：{len(manifest)}。',
           '- 两件遗物含初始遗物兼容别名、升级遗物；另收角色专属海玻璃名称。剧情为当前实际新增的建筑师三句对话。',
           '- 扫描 src/Volibear 下 C#、GDScript、场景、资源与 JSON；排除 bin/obj。原生游戏通用文案、日志/异常、注释、验收探针英文诊断、未打包设计/资产预览不作为游戏文本。',
           '- 能量 UI 动态数值由原生 Label 提供；此处收入场景初始文本。音频媒体无 Mod 字幕，不将语音目录元数据充当屏幕文本。',
           '- 文本表合并入口：' + source_link('src/Volibear/Content/VolibearLoc.cs') + '、' + source_link('src/Volibear/Content/InlineModelLocalization.cs') + '；资源打包入口：' + source_link('tools/build_assets.py') + '。', '',
           '| 分类 | 字段数 |', '| --- | ---: |']
    out += [f'| {cat} | {count} |' for cat, count in sorted(counts.items())]
    out += ['', '## 卡牌：89 卡 / 178 牌面', '']
    for key, (path, line) in sorted(cards.items()):
        out += [f'### {key}', '', '模型来源：' + source_link(path, line), '']
        for face in ('base', 'upgrade'):
            context = contexts[f'{key}.{face}']
            out += [f'#### {"基础" if face == "base" else "升级"} · {key}.{face}', '',
                    f'- 费用：{context["cost"]}；类型：{context["type"]}；稀有度：{context["rarity"]}；目标：{context["target"]}；原生关键词：{", ".join(context["keywords"]) or "无"}。',
                    '- 模板变量：`' + json.dumps({'IfUpgraded': context['IfUpgraded'], **context['values']}, ensure_ascii=False, sort_keys=True) + '`。', '',
                    '| 稳定 ID | 来源 | 原文 | 修改 |', '| --- | --- | --- | --- |']
            for entry in entries:
                if entry.id.startswith(f'cards:{key}.{face}.'):
                    out.append(row(entry))
            out.append('')
        out += ['<details><summary>动态变量与升级规则原始源码（供核查，不作生产改写）</summary>', '', '```csharp',
                contexts[f'{key}.base']['vars_source'] or '// 无额外 CanonicalVars',
                contexts[f'{key}.base']['upgrade_source'], '```', '', '</details>', '']
    titles = {'cards': '选牌与兽化提示', 'characters': '角色', 'ancients': '剧情', 'powers': '状态与能力',
              'relics': '遗物', 'keywords': '关键词悬停', 'keyword-match': '关键词匹配词（非独立可见文案）',
              'ui': 'UI 与动态信息', 'mod-menu': 'Mod 菜单', 'metadata': 'Mod 标识与依赖元数据',
              'additional': '其它硬编码文本', 'text-reference': '文本引用（匹配/悬停入口）'}
    for category in sorted(counts):
        if category == 'card-faces':
            continue
        out += [f'## {titles.get(category, category)}', '', '| 稳定 ID | 来源 | 原文 | 修改 |', '| --- | --- | --- | --- |']
        out += [row(e) for e in entries if e.category == category]
        out.append('')
    per_source = Counter(e.source for e in entries)
    out += ['## 来源清单与快照摘要', '',
            '每个扫描文件均列出 SHA-256；0 行表示没有新增可审核文本（包括诊断/探针及资源引用）。文本行数含基础/升级重复字段。', '',
            '| 来源 | 审核字段数 | SHA-256 |', '| --- | ---: | --- |']
    out += [f'| {source_link(path)} | {per_source[path]} | `{digest}` |' for path, digest in manifest]
    out += ['', '## 复跑与冻结约定', '', '```sh', 'python -B tools/export_text_review.py',
            'python -B tools/export_text_review.py --check',
            '# 仅在所有实施结束且 Lead 授权后运行一次：',
            'python -B tools/export_text_review.py --replace-final', '```', '',
            '默认命令拒绝覆盖已有文档；--check 只比较而不写入。最终覆盖前须先合并人工修改；修改栏非空时工具拒绝覆盖。', '']
    return '\n'.join(out)


def row(entry):
    return f'| `{entry.id}` | {source_link(entry.source, entry.line)} | {cell(entry.text)} |  |'


def export(root=ROOT, check=False, replace_final=False):
    path = Path(root) / OUTPUT
    if path.exists() and not check and not replace_final:
        raise ValueError('审核文档已冻结；默认拒绝覆盖。最终统一导出才使用 --replace-final。')
    if path.exists() and replace_final:
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('| `'):
                parts = line.split('|')
                if len(parts) != 6 or parts[-2].strip():
                    raise ValueError('修改栏已有内容或表格格式改变，请先合并人工审核意见；拒绝覆盖。')
    content = render(root)
    if check:
        if not path.exists() or path.read_bytes() != content.encode('utf-8'):
            raise ValueError('文档与当前源码不同（冻结期间允许漂移）；未写入任何文件。')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w' if replace_final else 'x', encoding='utf-8', newline='') as handle:
            handle.write(content)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument('--check', action='store_true')
    options.add_argument('--replace-final', action='store_true')
    args = parser.parse_args()
    try:
        path = export(check=args.check, replace_final=args.replace_final)
    except (ValueError, KeyError) as exc:
        print(f'TEXT_REVIEW_ERROR: {exc}', file=sys.stderr)
        return 1
    print(f'TEXT_REVIEW_OK: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
