"""Independent oracle for two real Architect event fixtures, not full-run acceptance."""
import json
import math
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

MARKER = '[Volibear] ARCHITECT_ENDING_RESULT '


def validate(payload, token):
    errors = []
    def need(ok, label):
        if not ok:
            errors.append(label)
    def integer(n):
        return type(n) is int
    try:
        need(type(payload) is dict and bool(token), 'object and current token required')
        for key, value in dict(schema=1, token=token, scenario='architect-ending',
                fixture='isolated-architect-events-not-full-run', version=EXPECTED_GAME_VERSION, commit=EXPECTED_GAME_COMMIT, testMode=False, passed=True).items():
            need(type(payload[key]) is type(value) and payload[key] == value, 'metadata ' + key)
        rows = payload['cases']
        need(type(rows) is list and len(rows) == 2, 'exact bear and stock fixtures required')
        for index, family in enumerate(('volibear', 'ironclad')):
            row = rows[index]; bear = index == 0
            need(row['family'] == family and row['character'] == ('VolibearCharacter' if bear else 'Ironclad'), 'ordered actual character')
            need(integer(row['optionsChosen']) and 1 <= row['optionsChosen'] <= 12, 'real bounded dialogue selections')
            before, after, records, visual = (row[k] for k in ('before', 'after', 'records', 'visual'))
            for n in (before['hp'], before['wins'], after['hp'], after['wins'], after['deaths'], after['domainEntries'], records['victoryCalls'], records['lossCalls'], visual['arcs']):
                need(integer(n), 'integer receipt required')
            need(before['hp'] > 0 and before['wins'] >= 0 and before['saved'] is True, 'living saved baseline')
            need(after['wins'] == before['wins'] + 1 and after['saved'] is False, 'one persisted win and active save deleted')
            need(after['gameOver'] is True and after['victoryRoom'] is True and after['screen'] == 'NGameOverScreen', 'actual native terminal victory screen')
            need(after['hp'] == (before['hp'] if bear else 0), 'bear preserves exact HP; stock dies')
            need(after['deaths'] == (0 if bear else 1) and after['domainEntries'] == (1 if bear else 0), 'character-scoped death/domain callbacks')
            need(records['victoryCalls'] == 1 and records['lossCalls'] == (0 if bear else 1), 'original native bookkeeping calls')
            need(records['originalSnapshot'] is bear, 'bear screen uses original sole victory snapshot; stock uses native post-death snapshot')
            need(visual['entered'] is bear and visual['shader'] is bear and visual['arcs'] == (6 if bear else 0), 'actual domain visual material and populated arcs')
            ratio = visual['scaleRatio']
            need(type(ratio) in (int, float) and math.isfinite(ratio) and abs(ratio - (1.22 if bear else 1)) < .001, 'actual domain scale')
            need(visual['animation'] in ('domain_enter', 'domain_idle') if bear else visual['animation'] == '', 'live domain animation')
        need(rows[1]['before']['wins'] == rows[0]['after']['wins'], 'same isolated profile consecutive fixtures')
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        errors.append('malformed raw evidence: ' + str(exc))
    return errors


def check_log(text, token):
    rows = []
    errors = []
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    for line in text.splitlines():
        if 'ARCHITECT_ENDING_ERROR' in line:
            errors.append('native Architect error')
        if MARKER not in line:
            continue
        try:
            row = json.loads(line.split(MARKER, 1)[1], object_pairs_hook=unique)
            if isinstance(row, dict) and row.get('token') == token:
                rows.append(row)
        except (ValueError, TypeError):
            errors.append('malformed Architect result')
    if len(rows) != 1:
        errors.append('exactly one current-token Architect result required')
    else:
        errors += validate(rows[0], token)
    return {'errors': errors, 'passed': not errors, 'cases': 2 if not errors else 0}
