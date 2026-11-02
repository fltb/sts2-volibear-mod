"""Independent expected-text gate. Native tooltip/resource evidence, NOT screenshot recognition."""
import json
from pathlib import Path

EXPECTED = json.loads((Path(__file__).resolve().parents[1] / 'tests/fixtures/power_presentation_expected.json').read_text(encoding='utf-8'))
PREFIX = '[Volibear] POWER_PRESENTATION_RESULT '
ACCEPTANCE = 'native-tooltip/resource-not-visual-recognition'
FIXTURE = 'native-ToMutable-ApplyInternal-SetAmount-HoverTips-RemoveInternal'
PERMANENT = '领域持续本战。禁用敌方特殊能力与全队负面状态。你每抽到状态或诅咒，消耗该牌并补抽1张；每打出一张攻击牌，对全体造成4雷伤。'


def expected_cases():
    for spec in EXPECTED:
        # 雷势 now explains each point; its native amount badge still needs both samples.
        for amount in ((2, 5) if '{Amount}' in spec['text'] or spec['model'] == 'StormChargePower' else (1,)):
            yield spec, amount, spec['text'].replace('{Amount}', str(amount))
        if spec['model'] == 'DomainPower':
            yield spec, 999999999, PERMANENT


def expected_paths(spec):
    if spec['icon']:
        root = 'res://VolibearArt/vfx/icons'
        return f"{root}/64/{spec['icon']}.png", f"{root}/256/{spec['icon']}.png", True
    # Approved 20261102/provenance.json exports: all four power aliases are
    # dedicated 64/256 PNGs, including the former Bear/Wilderness card portraits.
    # PersistentPower subclasses without an override inherit ThunderForce.
    name = {'BearSpiritPower': 'bear_spirit', 'WildernessPower': 'wilderness',
            'DomainPower': 'domain'}.get(spec['model'], 'thunder_force')
    root = 'res://VolibearArt/icons/powers'
    return f'{root}/{name}.png', f'{root}/big/{name}.png', True


def validate_ui_lifecycle(value):
    if type(value) is not dict or value.get('fixture') != 'native-multiplayer-power-intent-extracted' or value.get('sourceScene') != 'res://scenes/combat/multiplayer_player_intent.tscn':
        return False
    if value.get('nodeType') != 'MegaCrit.Sts2.Core.Nodes.Combat.NPower' or value.get('freed') is not True or value.get('powersRestored') is not True:
        return False
    expected = (
        ('unbound-ready', None, False, True, False, False),
        ('late-bound-off', 'WeakPower', False, True, False, True),
        ('domain-on', 'WeakPower', True, True, True, False),
        ('rebound-ordinary', 'StrengthPower', False, True, True, True),
        ('rebound-debuff', 'WeakPower', True, True, True, True),
        ('domain-off', 'WeakPower', False, True, False, False),
        ('tree-detached', 'WeakPower', False, False, False, False),
        ('tree-reattached', 'WeakPower', False, True, False, False),
        ('domain-reentered', 'WeakPower', True, True, True, False),
    )
    rows = value.get('stages')
    if type(rows) is not list or len(rows) != len(expected):
        return False
    identity = None
    for row, (phase, model, visible, inside, domain, immediate) in zip(rows, expected):
        if type(row) is not dict or row.get('phase') != phase or row.get('boundModel') != model or 'boundModel' not in row:
            return False
        node = row.get('nodeId')
        if type(node) is not int or node <= 0 or (identity is not None and node != identity):
            return False
        identity = node
        if type(row.get('overlays')) is not int or row['overlays'] != 1 or type(row.get('children')) is not int or row['children'] != 3:
            return False
        if row.get('visible') is not visible or row.get('visibleInTree') is not (visible and inside) or row.get('insideTree') is not inside or row.get('domain') is not domain or row.get('immediate') is not immediate:
            return False
        if type(row.get('ready')) is not bool or (inside and row['ready'] is not True):
            return False
        if 'setterSameFrame' not in row or (row['setterSameFrame'] is not True if immediate else row['setterSameFrame'] is not None):
            return False
    return True


def power_presentation_errors(report, token):
    errors = []
    if type(report) is not dict:
        return ['report must be an object']
    def equal(where, actual, expected):
        if type(actual) is not type(expected) or actual != expected:
            errors.append(f'{where}: expected {expected!r}, got {actual!r}')
    if not token:
        errors.append('current token required')
    for field, value in dict(token=token, schema=1, models=25, acceptance=ACCEPTANCE, fixture=FIXTURE, testMode=False).items():
        equal(field, report.get(field), value)
    rows = report.get('rows')
    cases = list(expected_cases())
    if type(rows) is not list or len(rows) != len(cases):
        errors.append(f'rows: expected {len(cases)} ordered tooltip/resource samples')
        return errors
    for index, (row, (spec, amount, text)) in enumerate(zip(rows, cases)):
        label = f'rows[{index}] {spec["model"]} amount={amount}'
        if type(row) is not dict:
            errors.append(label + ': sample must be an object')
            continue
        small, big, exact_size = expected_paths(spec)
        expected = dict(model=spec['model'], title=spec['title'], description=text, mutable=True, smart=True,
            amount=amount, displayAmount=0 if amount == 999999999 else amount, iconPath=small, bigIconPath=big)
        if exact_size:
            expected.update(width=64, height=64, bigWidth=256, bigHeight=256)
        for field, value in expected.items():
            equal(label + '.' + field, row.get(field), value)
        for field in ('width', 'height', 'bigWidth', 'bigHeight'):
            if type(row.get(field)) is not int or row[field] <= 0:
                errors.append(label + '.' + field + ': positive integer dimension required')
    if not validate_ui_lifecycle(report.get('uiLifecycle')):
        errors.append('uiLifecycle: expected nine ordered native placeholder/binding/domain/tree stages, stable node identity, immediate setters, release and restoration')
    return errors


def validate_power_presentation(report, token):
    return not power_presentation_errors(report, token)


def power_presentation_evidence(log, token):
    """Return (parsed payload or None, passed), rejecting stale/duplicate/malformed runs."""
    lines = [line.split(PREFIX, 1)[1] for line in log.splitlines() if PREFIX in line]
    if len(lines) != 1 or 'POWER_PRESENTATION_FAILED' in log:
        return {'errors': ['exactly one receipt and no POWER_PRESENTATION_FAILED marker required']}, False
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    try:
        payload = json.loads(lines[0], object_pairs_hook=unique)
    except (ValueError, TypeError) as error:
        return {'errors': ['malformed power receipt: ' + str(error)]}, False
    errors = power_presentation_errors(payload, token)
    result = dict(payload) if type(payload) is dict else {}
    result['errors'] = errors
    return result, not errors
