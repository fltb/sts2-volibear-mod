"""Independent oracle for the bounded native domain-suppression fixture.

This validates one process's fresh-family receipts. It is not the full release
gate and never starts the game. Native checks must match the frozen set exactly.
"""
import json
import math

PREFIX = '[Volibear] DOMAIN_SUPPRESSION_RESULT '
ERROR_PREFIX = '[Volibear] DOMAIN_SUPPRESSION_ERROR '
FAMILIES = ('sandpit', 'knights', 'self')
CASES = ('all',) + FAMILIES
REQUIRED_CHECKS = {
    'sandpit': frozenset((
        'fresh-domain-off', 'sandpit-counter-frozen', 'sandpit-position-frozen',
        'sandpit-player-alive', 'sandpit-resumes-one-tick', 'sandpit-position-resumes',
    )),
    'knights': frozenset((
        'fresh-domain-off', 'dampen-applied-before-entry', 'hex-applied-before-entry',
        'dampen-entry-restores-upgrade', 'hex-entry-restores-retention',
        'native-debuff-identities-retained', 'independent-ethereal-retained',
        'dampen-exit-resumes-downgrade', 'hex-exit-resumes-ethereal',
        'dampen-native-removal-no-double-upgrade', 'dampen-removal-survives-domain-exit',
        'disabled-ui-before-domain', 'disabled-ui-during-domain', 'disabled-ui-after-domain',
    )),
    'self': frozenset((
        'fresh-domain-off', 'self-source-mindrot-before', 'self-source-waste-before',
        'self-source-mindrot-restored', 'self-source-waste-restored', 'self-source-sloth-muted',
        'self-disintegration-callback-muted', 'native-weak-duration-ticked',
        'new-no-draw-committed-muted', 'self-mindrot-resumes', 'self-waste-resumes', 'new-no-draw-resumes',
    )),
}


def _need(value, message):
    if not value:
        raise ValueError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate(result, token, family):
    _need(type(result) is dict, 'receipt must be an object')
    for key, expected in dict(schema=1, token=token, scenario='domain-suppression', family=family,
                              version='v0.107.1', commit='59260271', testMode=False, passed=True).items():
        _need(type(result.get(key)) is type(expected) and result[key] == expected, 'invalid ' + key)
    checks = result.get('checks')
    _need(type(checks) is dict and set(checks) == REQUIRED_CHECKS[family], 'missing/extra checks for ' + family)
    _need(all(value is True for value in checks.values()), 'failed/non-boolean check for ' + family)
    steps = result.get('steps')
    _need(type(steps) is list, 'steps must be an array')
    if family == 'sandpit':
        _need(len(steps) == 3 and all(type(row) is dict for row in steps), 'sandpit snapshot count')
        _need([row.get('phase') for row in steps] == ['baseline', 'domain-on', 'domain-off'], 'sandpit snapshot order')
        for row in steps:
            _need(type(row.get('count')) is int and row['count'] > 0 and _number(row.get('x')), 'invalid sandpit count/position')
        before, during, after = steps
        _need(during['count'] == before['count'], 'sandpit counter changed during domain')
        _need(abs(during['x'] - before['x']) <= 1, 'sandpit moved during domain')
        _need(after['count'] == during['count'] - 1, 'sandpit did not resume exactly one tick')
        _need(abs(after['x'] - during['x']) > 1, 'sandpit did not resume movement')
    else:
        _need(steps == [], 'unexpected snapshots for ' + family)


def check_log(log, token, family='all'):
    """Return a headless.run_once result plus its independent acceptance boolean."""
    results = []
    try:
        _need(family in CASES, 'unknown requested family')
        _need(type(token) is str and bool(token), 'missing run token')
        _need(ERROR_PREFIX not in log, 'native suppression error')
        expected = FAMILIES if family == 'all' else (family,)
        lines = [line.split(PREFIX, 1)[1] for line in log.splitlines() if PREFIX in line]
        _need(len(lines) == len(expected), 'missing/duplicate family receipt')
        results = [json.loads(line, object_pairs_hook=_unique_object) for line in lines]
        _need(all(type(row) is dict for row in results), 'receipt must be an object')
        _need(tuple(row.get('family') for row in results) == expected, 'wrong/duplicate/out-of-order families')
        for row, name in zip(results, expected):
            validate(row, token, name)
        return {'family': family, 'results': results, 'errors': [], 'passed': True}, True
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return {'family': family, 'results': results, 'errors': [str(error)], 'passed': False}, False
