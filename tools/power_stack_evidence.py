"""Independent UI stacking contract; native rows, not model Amount alone, are checked."""
import json
from pathlib import Path

TITLES = {spec['model']: spec['title'] for spec in json.loads(
    (Path(__file__).resolve().parents[1] / 'tests/fixtures/power_presentation_expected.json').read_text(encoding='utf-8'))}

COUNT = {'ThunderGuardPower', 'StormConductionPower', 'BattleScarsPower', 'LingeringStormPower',
         'ThunderAftershockPower', 'PreyStillStandsPower', 'GrowingFuryPower', 'ThunderPoolPower',
         'BearSpiritPower', 'WildernessPower'}
INSTANCED = COUNT | {'ThunderArmorPower', 'WelcomeThunderPower'}
FLAGS = {'NextEngageDiscount', 'BiteMarkPower', 'ImmovableBodyPower'}
FIXED = {'ThunderAftershockPower', 'LingeringStormPower'}
ORDER = ['NextAttackDiscount', 'NextEngageDiscount', 'NextAttackReplayPower', 'NextAttackTrainingPower',
         'UnifyPower', 'PrimalThunderPower', 'ThunderGuardPower', 'BiteMarkPower', 'StormConductionPower',
         'StandingPower', 'BattleScarsPower', 'LingeringStormPower', 'ThunderAftershockPower',
         'PreyStillStandsPower', 'GrowingFuryPower', 'WelcomeThunderPower', 'ThunderArmorPower',
         'ImmovableBodyPower', 'BattleBodyPower', 'ThunderPoolPower', 'BearSpiritPower', 'WildernessPower',
         'StormChargePower', 'DomainPower', 'EndlessHuntPower']


PERMANENT_DURATION = 999_999_999
# Permanent domain lasts the whole combat by default, so the native amount label
# shows nothing and the hover text states the lifetime in words instead of 本战.
PERMANENT = '领域持续。禁用敌方特殊能力与全队负面状态。你每抽到状态或诅咒，消耗该牌并补抽1张；每打出一张攻击牌，对全体造成4雷伤。'


def label_for(model, amounts):
    if not amounts or model in FLAGS:
        return ''
    if model == 'DomainPower':
        return '' if amounts == [PERMANENT_DURATION] else str(amounts[0])
    if model in COUNT:
        return str(len(amounts))
    if model in {'NextAttackDiscount', 'WelcomeThunderPower'}:
        return str(max(amounts))
    if model == 'StandingPower':
        return str(min(amounts))
    return str(sum(amounts))


def expected_samples():
    for phase, amounts in [('armor-paid-base', [3]), ('armor-paid-mixed', [3, 4]),
                           ('armor-after-lightning', [3, 4]), ('armor-representative-removed', [4]),
                           ('armor-tree-reentered', [4]), ('armor-amount-changed', [5]),
                           ('armor-last-removed', [])]:
        yield phase, 'ThunderArmorPower', amounts
    for model in ORDER:
        first = 1 if model in FLAGS | FIXED else 2
        yield 'matrix-single', model, [first]
        amounts = [first, 1 if model in FIXED else 5] if model in INSTANCED else [first if model in FLAGS else 5]
        yield 'matrix-updated', model, amounts
        if model == 'DomainPower':
            yield 'domain-permanent', model, [999999999]
        yield 'matrix-cleared', model, []


def errors(value):
    if type(value) is not dict:
        return ['stackUi: native stack receipt required']
    failures = []
    def equal(where, actual, wanted):
        if type(actual) is not type(wanted) or actual != wanted:
            failures.append(f'stackUi.{where}: expected {wanted!r}, got {actual!r}')
    equal('fixture', value.get('fixture'), 'native-container-matrix-and-paid-armor')
    equal('powersRestored', value.get('powersRestored'), True)
    equal('blockGains', value.get('blockGains'), [3, 4])
    rows = value.get('samples')
    expected = list(expected_samples())
    if type(rows) is not list or len(rows) != len(expected):
        return failures + [f'stackUi.samples: expected {len(expected)} ordered native UI samples']
    identities = {}
    for i, (row, (phase, model, amounts)) in enumerate(zip(rows, expected)):
        where = f'samples[{i}] {phase}/{model}'
        if type(row) is not dict:
            failures.append(where + ': object required')
            continue
        for field, wanted in dict(phase=phase, model=model, amounts=amounts, nodeCount=len(amounts),
                                 visibleCount=int(bool(amounts)), label=label_for(model, amounts)).items():
            equal(where + '.' + field, row.get(field), wanted)
        if any(type(n) is not int for n in row.get('amounts', [])):
            failures.append(where + ': integer native amounts required')
        node = row.get('visibleNode')
        if type(node) is not int or (node <= 0 if amounts else node != 0):
            failures.append(where + ': valid visible node identity required')
        identities[(phase, model)] = node
        titles = row.get('tipTitles')
        if type(titles) is not list or any(type(t) is not str for t in titles) or bool(titles) != bool(amounts):
            failures.append(where + ': native tooltip titles required exactly while active')
        elif amounts and (titles[0] != TITLES[model] or titles.count(TITLES[model]) != 1):
            failures.append(where + ': own state heading must occur exactly once')
        tips = row.get('tips')
        if type(tips) is not list or any(type(t) is not str for t in tips) or bool(tips) != bool(amounts):
            failures.append(where + ': native tooltip text required exactly while active')
        elif amounts:
            if any('{Amount}' in t for t in tips):
                failures.append(where + ': unresolved template')
            if model in COUNT and len(amounts) == 2 and not ('共2份' in tips[0] and '分别' in tips[0]):
                failures.append(where + ': independent multi-response count must be explained')
            if model == 'ThunderArmorPower' and len(amounts) == 2 and not (str(sum(amounts)) in tips[0] and '2次' in tips[0]):
                failures.append(where + ': combined armor and separate block gains must be explained')
            if phase == 'domain-permanent':
                if any('本战' in t for t in tips):
                    failures.append(where + ': permanent domain must not display 本战')
                if not tips[0].startswith('领域持续。'):
                    failures.append(where + ': permanent lifetime must keep the 领域持续。 description')
                if tips[0] != PERMANENT:
                    failures.append(where + ': permanent lifetime must keep the full permanent description')
    def identity(phase):
        return identities.get((phase, 'ThunderArmorPower'))
    if identity('armor-paid-base') != identity('armor-paid-mixed') or identity('armor-paid-mixed') != identity('armor-after-lightning'):
        failures.append('stackUi: stable representative during add/trigger required')
    if identity('armor-paid-mixed') == identity('armor-representative-removed'):
        failures.append('stackUi: removed representative must be replaced')
    if not (identity('armor-representative-removed') == identity('armor-tree-reentered') == identity('armor-amount-changed')):
        failures.append('stackUi: representative must survive tree reentry and amount change')
    for before, after, delta in [('blockBefore', 'blockAfter', 7), ('lightningBefore', 'lightningAfter', 1)]:
        if type(value.get(before)) is not int or type(value.get(after)) is not int or value[after] - value[before] != delta:
            failures.append(f'stackUi: {before}/{after} must change by {delta}')
    expected_payments = [dict(model='Volibear_U34', upgraded=False, before=10, after=9, state='Finished', type='PlayCardAction'),
                         dict(model='Volibear_U34', upgraded=True, before=9, after=8, state='Finished', type='PlayCardAction'),
                         dict(model='Volibear_C24', upgraded=False, before=8, after=7, state='Finished', type='PlayCardAction')]
    equal('payments', value.get('payments'), expected_payments)
    equal('captures', value.get('captures'), ['armor-mixed.png', 'multiple-lightning.png', 'nonstacking.png', 'domain-permanent.png'])
    return failures
