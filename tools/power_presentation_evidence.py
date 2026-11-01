"""Independent expected-text gate. Native tooltip/resource evidence, NOT screenshot recognition."""
import json
from pathlib import Path

EXPECTED = json.loads((Path(__file__).resolve().parents[1] / 'tests/fixtures/power_presentation_expected.json').read_text(encoding='utf-8'))
PREFIX = '[Volibear] POWER_PRESENTATION_RESULT '
ACCEPTANCE = 'native-tooltip/resource-not-visual-recognition'
FIXTURE = 'native-ToMutable-ApplyInternal-SetAmount-HoverTips-RemoveInternal'
PERMANENT = '你的领域持续本战。你的每张攻击在领域内首段普通攻击后附加4＋当前雷势的全体雷伤，多段与重演共享一次机会。你实际抽到状态或诅咒时，净化消耗并补抽1张。压制敌方有利特殊效果，保留普通攻击、直接力量与格挡及必要清理。压制对全队生效；任一存活持有者仍有领域就继续，多人领域不重复叠加。'


def expected_cases():
    for spec in EXPECTED:
        for amount in ((2, 5) if '{Amount}' in spec['text'] else (1,)):
            yield spec, amount, spec['text'].replace('{Amount}', str(amount))
        if spec['model'] == 'DomainPower':
            yield spec, 999999999, PERMANENT


def expected_paths(spec):
    if spec['icon']:
        root = 'res://VolibearArt/vfx/icons'
        return f"{root}/64/{spec['icon']}.png", f"{root}/256/{spec['icon']}.png", True
    if spec['model'] in ('BearSpiritPower', 'WildernessPower'):
        root = 'res://VolibearArt/cards/production/sts2/Volibear/images/card_portraits'
        key = 'r28' if spec['model'] == 'BearSpiritPower' else 'r30'
        return f'{root}/{key}.png', f'{root}/big/{key}.png', False
    name = 'domain' if spec['model'] == 'DomainPower' else 'thunder_force'
    root = 'res://VolibearArt/icons/powers'
    return f'{root}/{name}.svg', f'{root}/big/{name}.svg', True


def validate_power_presentation(report, token):
    if not isinstance(report, dict) or not token or report.get('token') != token:
        return False
    if type(report.get('schema')) is not int or report['schema'] != 1 or type(report.get('models')) is not int or report['models'] != 25:
        return False
    if report.get('acceptance') != ACCEPTANCE or report.get('fixture') != FIXTURE or report.get('testMode') is not False:
        return False
    rows = report.get('rows')
    cases = list(expected_cases())
    if not isinstance(rows, list) or len(rows) != len(cases):
        return False
    for row, (spec, amount, text) in zip(rows, cases):
        if not isinstance(row, dict) or row.get('model') != spec['model'] or row.get('title') != spec['title']:
            return False
        if row.get('mutable') is not True or row.get('smart') is not True or row.get('description') != text:
            return False
        if type(row.get('amount')) is not int or row['amount'] != amount:
            return False
        display = 0 if amount == 999999999 else amount
        if type(row.get('displayAmount')) is not int or row['displayAmount'] != display:
            return False
        small, big, exact_size = expected_paths(spec)
        if row.get('iconPath') != small or row.get('bigIconPath') != big:
            return False
        sizes = [row.get(k) for k in ('width', 'height', 'bigWidth', 'bigHeight')]
        if any(type(n) is not int or n <= 0 for n in sizes):
            return False
        if exact_size and sizes != [64, 64, 256, 256]:
            return False
    return True


def power_presentation_evidence(log, token):
    """Return (parsed payload or None, passed), rejecting stale/duplicate/malformed runs."""
    lines = [line.split(PREFIX, 1)[1] for line in log.splitlines() if PREFIX in line]
    if len(lines) != 1 or 'POWER_PRESENTATION_FAILED' in log:
        return None, False
    try:
        payload = json.loads(lines[0])
    except (ValueError, TypeError):
        return None, False
    return payload, validate_power_presentation(payload, token)
