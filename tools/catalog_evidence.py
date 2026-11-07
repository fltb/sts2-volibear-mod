"""Independent 89-card/178-face native catalog comparator.

Only tests/fixtures/card_expectations.json supplies expected card IDs, values and
Chinese text (including the six approved beast display overrides). Production card
classes are NEVER read to create expectations. This proves catalog/formatting/resource
observations only, not normal-input payment, effects, or complete visual acceptance.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/card_expectations.json'
PREFIX = '[Volibear] CATALOG_RESULT '
DISCOVERY = 'ModelDb._contentById;ModelDb.GetById;CustomCardPoolModel.AllCards'
API = 'CombatState.CreateCard;CardModel.Keywords;CardCmd.Upgrade;LocManager.SetLanguage;ResourceLoader.Load<Texture2D>;Texture2D.GetImage'
COUNTS = {'Basic': 4, 'Common': 24, 'Uncommon': 36, 'Rare': 23, 'Token': 2}
TARGETS = {'single_enemy': 'AnyEnemy', 'self': 'Self', 'all_enemies': 'AllEnemies', 'random_enemy': 'RandomEnemy'}
# Remove presentation, never semantic words, digits, punctuation or unknown tags.
STYLE = re.compile(r'\[/?(?:b|i|u|s|blue|green|red|gold|purple|orange|white|gray|grey|center|left|right|color(?:=[^\]]+)?|font(?:=[^\]]+)?|font_size(?:=[^\]]+)?|outline_size(?:=[^\]]+)?|outline_color(?:=[^\]]+)?)\]')


def display_text(value):
    if not isinstance(value, str):
        raise ValueError('Native formatted text must be a string')
    return re.sub(r'\s+', '', STYLE.sub('', value)).replace('\u200b', '')


def expected_catalog():
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    cards = data['cards']
    if len(cards) != 89 or sum(len(c['faces']) for c in cards) != 178:
        raise ValueError('Independent fixture no longer contains 89/178')
    if Counter(c['rarity'].title() for c in cards) != COUNTS:
        raise ValueError('Independent fixture rarity counts drifted')
    return {'VOLIBEAR_' + card['card_id']: card for card in cards}


def catalog_errors(result, token):
    """Return diagnostics; an empty list is catalog acceptance, never gameplay acceptance."""
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    def exact(actual, expected, message):
        require(type(actual) is type(expected) and actual == expected, message + f': expected {expected!r}, observed {actual!r}')
    def unique_rows(rows, key, label):
        if not isinstance(rows, list):
            errors.append(label + ': expected array')
            return {}
        found = {}
        for row in rows:
            if not isinstance(row, dict):
                errors.append(label + ': expected object row')
                continue
            k = key(row)
            if k in found:
                errors.append(label + ': duplicate ' + repr(k))
            found[k] = row
        return found
    def text_check(text, card, face, label):
        require(isinstance(text, dict), label + ': missing text observation')
        if not isinstance(text, dict):
            return
        code = 'VOLIBEAR_' + card['card_id']
        exact(text.get('titleKey'), code + '.title', label + ' title key')
        exact(text.get('descriptionKey'), code + '.description', label + ' description key')
        exact(text.get('titleExists'), True, label + ' native title key exists')
        exact(text.get('descriptionExists'), True, label + ' native description key exists')
        for field in ('rawTitle', 'rawDescription', 'title', 'description'):
            value = text.get(field)
            require(isinstance(value, str) and bool(value), label + ' empty/missing ' + field)
            if isinstance(value, str):
                require(not re.search(r'MissingLoc|MISSING|VOLIBEAR_|(?:cards\.)|\b(?:Exhaust|Retain|Unplayable)\b', value, re.I), label + ' unresolved/English ' + field)
        exact(display_text(text.get('title', '')), card['name_zh'] + ('+' if face['upgrade'] else ''), label + ' formatted Chinese title')
        # Native GetDescriptionForPile appends its Keywords. The fixture already has
        # each self Exhaust suffix exactly once: duplicated or stale suffixes FAIL.
        exact(display_text(text.get('description', '')), display_text(face['display_text_zh']), label + ' formatted Chinese description')

    try:
        require(isinstance(result, dict), 'result must be an object')
        if not isinstance(result, dict):
            return errors
        expected = expected_catalog()
        for key, value in dict(schemaVersion=1, token=token, scenario='catalog', acceptance='catalog-not-gameplay-or-payment',
                               completed=True, testMode=False, discovery=DISCOVERY, api=API,
                               gameVersion=EXPECTED_GAME_VERSION, gameCommit=EXPECTED_GAME_COMMIT,
                               language='zhs', reloadSequence=['zhs', 'eng', 'zhs'], ownerPowerCount=0, errors=[]).items():
            exact(result.get(key), value, key)
        require(type(token) is str and bool(token), 'current run token is required')
        require(type(result.get('ownerRef')) is int and result['ownerRef'] != 0, 'actual player identity required')
        exact(result.get('character'), 'VolibearCharacter', 'actual character')
        exact(result.get('deckAfter'), result.get('deckBefore'), 'catalog must not change deck')
        require(isinstance(result.get('deckBefore'), list) and len(result['deckBefore']) == 10, 'actual starting deck observed')
        exact(result.get('energyAfter'), result.get('energyBefore'), 'catalog must not spend/gain energy')
        require(type(result.get('energyBefore')) in (int, float) and result['energyBefore'] >= 0, 'energy observed')
        exact(result.get('rarityCounts'), COUNTS, 'native pool rarity distribution')
        pool = result.get('poolIds')
        require(isinstance(pool, list) and len(pool) == 89 and len(set(pool)) == 89 and set(pool) == set(expected), 'actual BaseLib pool must contain exact 89 unique IDs')
        registry = unique_rows(result.get('registry'), lambda row: row.get('modelId'), 'registry')
        require(set(registry) == set(expected), 'actual registered ID set differs from independent 89')
        for code, card in expected.items():
            record = registry.get(code, {})
            for key, value in dict(canonical=True, resolvedSame=True, inPool=True, rarity=card['rarity'].title(), type=card['type'].title()).items():
                exact(record.get(key), value, code + ' registry ' + key)
            exact(record.get('nativeType'), 'Volibear.Content.Volibear_' + card['card_id'], code + ' registered native type')
        faces = unique_rows(result.get('faces'), lambda row: (row.get('modelId'), row.get('upgrade')), 'faces')
        keys = {(code, upgrade) for code in expected for upgrade in (False, True)}
        require(set(faces) == keys and len(result.get('faces', [])) == 178, 'must observe exact 178 mutable faces')
        refs = []
        for code, card in expected.items():
            base_keywords = ['Exhaust'] if card['faces'][0]['self_exhaust'] else []
            for face in card['faces']:
                label = face['face_id']
                observed = faces.get((code, face['upgrade']), {})
                cost = 0 if face['cost'] == 'X' else face['cost']
                canonical = 0 if card['faces'][0]['cost'] == 'X' else card['faces'][0]['cost']
                native = dict(nativeType='Volibear.Content.Volibear_' + card['card_id'], ownerRef=result.get('ownerRef'),
                              ownerMatches=True, mutable=True, upgrade=face['upgrade'], upgradeLevel=int(face['upgrade']),
                              type=card['type'].title(), rarity=card['rarity'].title(), target=TARGETS[card['play_target']],
                              initialKeywords=base_keywords, keywords=['Exhaust'] if face['self_exhaust'] else [],
                              costsX=face['cost'] == 'X', canonicalCost=canonical, localCost=cost, allCost=cost)
                for key, value in native.items():
                    exact(observed.get(key), value, label + ' ' + key)
                ref = observed.get('cardRef')
                require(type(ref) is int and ref != 0, label + ' mutable reference missing')
                refs.append(ref)
                variables = observed.get('vars')
                require(isinstance(variables, dict), label + ' missing actual DynamicVars')
                if isinstance(variables, dict):
                    for name, variable in variables.items():
                        require(isinstance(name, str) and bool(name) and isinstance(variable, dict), label + ' invalid DynamicVar')
                        if isinstance(variable, dict):
                            require(isinstance(variable.get('kind'), str) and bool(variable['kind']), label + ' DynamicVar native kind')
                            for value in ('baseValue', 'enchantedValue', 'previewValue'):
                                n = variable.get(value)
                                require(type(n) in (int, float) and math.isfinite(n), label + '.' + name + ' invalid ' + value)
                    # The fixture expressly does not define engine variable names.
                    # Values are observed, not falsely claimed as a separate numeric oracle;
                    # exact formatted face text above independently checks printed numerals.
                text_check(observed.get('text'), card, face, label)
        require(len(refs) == 178 and len(set(refs)) == 178, 'faces must be independent actual mutable instances')
        reloaded = unique_rows(result.get('reloaded'), lambda row: (row.get('modelId'), row.get('upgrade')), 'language reload')
        require(set(reloaded) == keys, 'missing language-reloaded faces')
        for code, card in expected.items():
            for face in card['faces']:
                key = (code, face['upgrade'])
                text = reloaded.get(key, {}).get('text')
                text_check(text, card, face, face['face_id'] + ' after reload')
                exact(text, faces.get(key, {}).get('text'), face['face_id'] + ' native reload equality')
        portraits = unique_rows(result.get('portraits'), lambda row: row.get('modelId'), 'portraits')
        require(set(portraits) == set(expected), 'missing portrait pairs')
        root = 'res://VolibearArt/cards/production/sts2/Volibear/images/card_portraits/'
        for code, card in expected.items():
            for size, prefix, width, height in [('small', '', 250, 190), ('big', 'big/', 1000, 760)]:
                record = portraits.get(code, {}).get(size, {})
                for key, value in dict(path=root + prefix + card['card_id'].lower() + '.png', exists=True, decoded=True,
                                       width=width, height=height, error=None).items():
                    exact(record.get(key), value, code + ' ' + size + ' portrait ' + key)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
        errors.append('Malformed catalog observation: ' + str(error))
    return errors


def validate_catalog_result(result, token):
    return not catalog_errors(result, token)


def catalog_evidence(log, run_id):
    """Runner adapter returns (parsed raw report or None, independent verdict)."""
    lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1:
        return None, False
    try:
        result = json.loads(lines[0])
    except (json.JSONDecodeError, ValueError):
        return None, False
    return result, validate_catalog_result(result, run_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--token', required=True)
    args = parser.parse_args()
    observation, passed = catalog_evidence(args.log.read_text(encoding='utf-8', errors='replace'), args.token)
    print(json.dumps({'passed': passed, 'acceptance': 'catalog-not-gameplay-or-payment',
                      'errors': catalog_errors(observation, args.token)}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if passed else 1)
