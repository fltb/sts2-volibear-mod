"""Finite, independent oracle for the native character integration receipt.

The containing suite supplies the pinned build, mounted artifact and process
isolation gates. This receipt checks real resource/localization/reward contracts;
it does not certify the hand illustrations or claim a naturally completed finale.
Synthetic parser fixtures are never native game evidence.
"""
import json
import re

PREFIX = '[Volibear] CHARACTER_INTEGRATION_RESULT '
SCOPE = 'native-character-resource-localization-ancient-reward-contracts'
LANGUAGES = ('zhs', 'eng', 'zhs')
TEXT = (
    ('characters', 'VOLIBEAR_CHARACTER.cardsModifierTitle', '不灭狂雷'),
    ('characters', 'VOLIBEAR_CHARACTER.cardsModifierDescription', '沃利贝尔的卡牌会出现在奖励和商店中。'),
    ('characters', 'VOLIBEAR_CHARACTER.eventDeathPrevention', '雷霆拒绝了死亡。'),
    ('characters', 'VOLIBEAR_CHARACTER.aromaPrinciple', '风暴只服从自己的意志'),
    ('characters', 'VOLIBEAR_CHARACTER.goldMonologue', '这些金属，终将被雷霆熔铸。'),
    ('characters', 'VOLIBEAR_CHARACTER.banter.alive.endTurnPing', '风暴不会等待。'),
    ('characters', 'VOLIBEAR_CHARACTER.banter.dead.endTurnPing', '雷声尚未消散……'),
    ('relics', 'SEA_GLASS.VOLIBEAR_CHARACTER.title', '风暴海玻璃'),
)
DIALOGUE = (
    ('Ancient', '你的风暴，已经震动了这里的根基。'),
    ('Character', '石墙会崩塌。雷霆不会。'),
    ('Ancient', '那就让我看看，这场风暴还能持续多久。'),
)
AUDIO = (
    'event:/sfx/characters/volibear_character/volibear_character_select',
    'event:/sfx/characters/volibear_character/volibear_character_attack',
    'event:/sfx/characters/volibear_character/volibear_character_cast',
    'event:/sfx/characters/volibear_character/volibear_character_die',
    'event:/sfx/ui/wipe_volibear_character',
)
# Canvas from the actual default hand PNGs in the public extracted-assets mirror
# hongyipan152/STS2SourceCode@d3db818409984371aa5582b94c55877ee2f72e3e,
# images/ui/hands/multiplayer_hand_ironclad_{point,rock,paper,scissors}.png.
# That mirror's game build is unspecified. The consumer and Control-space pivots
# were separately checked against the 0.107.1 / 59260271 NHandImage source in
# zhiyue/sts2-rl-agent@5d874e855ae1d0550d5c30416fadd7dbb0d133b7.
# Pivots are TextureRect coordinates, not PNG-pixel alignment targets.


def need(ok, message):
    if not ok:
        raise ValueError(message)


def shape(value, keys, message):
    need(type(value) is dict and set(value) == set(keys), message)


def integer(value, expected=None, minimum=0):
    return type(value) is int and value >= minimum and (expected is None or value == expected)


def inventory(value):
    shape(value, ('deck', 'relics'), 'inventory snapshot shape')
    identities = []
    for collection, keys in (('deck', ('instance', 'id', 'upgrade')), ('relics', ('instance', 'id'))):
        rows = value[collection]
        need(type(rows) is list and 0 < len(rows) <= 1000, 'finite nonempty native ' + collection)
        for item in rows:
            shape(item, keys, 'inventory item shape')
            need(integer(item['instance'], minimum=1) and type(item['id']) is str and
                 re.fullmatch(r'[A-Z][A-Z0-9_]*', item['id']), 'inventory object / model identity')
            if collection == 'deck':
                need(integer(item['upgrade']), 'inventory card upgrade')
            identities.append(item['instance'])
    need(len(set(identities)) == len(identities), 'inventory aliases the same live object more than once')


def validate(raw, token, pid):
    shape(raw, ('token', 'pid', 'result'), 'character receipt envelope')
    need(type(token) is str and bool(token.strip()) and raw['token'] == token and
         integer(pid, minimum=1) and integer(raw['pid'], expected=pid, minimum=1), 'character invocation binding')
    result = raw['result']
    shape(result, ('schema', 'character', 'hands', 'textRows', 'dialogueRows', 'tome',
                   'suppressedNativeAudio', 'inventoryBefore', 'inventoryAfter', 'inventoryUnchanged', 'scope'),
          'character result shape')
    need(integer(result['schema'], expected=1) and result['character'] == 'VOLIBEAR_CHARACTER' and
         result['scope'] == SCOPE, 'character schema / identity / scope')

    hands = result['hands']
    need(type(hands) is list and len(hands) == 4, 'four native hand resources required')
    hashes = []
    for hand, gesture in zip(hands, ('pointing', 'rock', 'paper', 'scissors')):
        shape(hand, ('gesture', 'path', 'width', 'height', 'pivotX', 'pivotY', 'decoded', 'sha256'),
              'native hand row shape')
        pivot = (163, 10) if gesture == 'pointing' else (197, 600)
        need(hand['gesture'] == gesture and
             hand['path'] == f'res://VolibearArt/ui/images/multiplayer_hand_volibear_{gesture}.png' and
             integer(hand['width'], expected=422) and integer(hand['height'], expected=1200) and
             integer(hand['pivotX'], expected=pivot[0]) and integer(hand['pivotY'], expected=pivot[1]) and
             hand['decoded'] is True, 'native hand getter / decoded canvas / pivot contract')
        need(type(hand['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', hand['sha256']),
             'decoded hand pixel hash required')
        hashes.append(hand['sha256'])
    need(len(set(hashes)) == 4, 'four hand gestures must not reuse the same decoded image')

    expected_text = [dict(language=language, table=table, key=key, text=text)
                     for language in LANGUAGES for table, key, text in TEXT]
    need(type(result['textRows']) is list and result['textRows'] == expected_text,
         'all 24 native text reads must resolve after zhs / eng / zhs reloads')
    dialogues = result['dialogueRows']
    need(type(dialogues) is list and len(dialogues) == 9, 'nine final dialogue selections required')
    for row, (language, visits) in zip(dialogues, ((lang, visit) for lang in LANGUAGES for visit in (0, 1, 25))):
        shape(row, ('language', 'visits', 'candidates'), 'native final dialogue row shape')
        need(row['language'] == language and integer(row['visits'], expected=visits),
             'final dialogue language reload / visit coverage')
        candidates = row['candidates']
        need(type(candidates) is list and len(candidates) == 1, 'one authored character finale candidate required')
        shape(candidates[0], ('repeating', 'lines'), 'native final dialogue candidate shape')
        need(candidates[0]['repeating'] is True and candidates[0]['lines'] ==
             [dict(speaker=speaker, text=text) for speaker, text in DIALOGUE],
             'repeatable native three-speaker finale content')

    tome = result['tome']
    shape(tome, ('selected', 'rarity', 'upgrade', 'restored', 'restoredUpgrade', 'restoredRelicCard',
                 'lightning', 'pool', 'relic', 'card'), 'native Tome receipt shape')
    need(tome['selected'] == tome['restored'] == tome['restoredRelicCard'] == 'VOLIBEAR_R18' and
         tome['rarity'] == 'Rare' and integer(tome['upgrade'], expected=1) and
         integer(tome['restoredUpgrade'], expected=1), 'Tome must select and restore the existing upgraded rare R18')
    need(type(tome['lightning']) in (int, float) and tome['lightning'] == 9 and
         type(tome['pool']) in (int, float) and tome['pool'] == 6, 'Tome reward must retain the frozen upgraded numbers')
    # Locked native JsonPropertyName and ModelIdRunSaveConverter representations,
    # not a second set of summary flags. A transient Tome has native floor 0;
    # its upgraded card has not been added to the master deck and has no floor.
    shape(tome['relic'], ('id', 'floor_added_to_deck', 'props'), 'native Tome JSON shape')
    need(tome['relic']['id'] == 'RELIC.DUSTY_TOME' and
         integer(tome['relic']['floor_added_to_deck'], expected=0) and
         tome['relic']['props'] == {'model_ids': [{'name': 'AncientCard', 'value': 'CARD.VOLIBEAR_R18'}]},
         'native Tome JSON must persist its AncientCard ModelId')
    shape(tome['card'], ('id', 'current_upgrade_level'), 'native transient reward JSON shape')
    need(tome['card']['id'] == 'CARD.VOLIBEAR_R18' and integer(tome['card']['current_upgrade_level'], expected=1),
         'native reward JSON must persist R18 upgrade')

    inventory(result['inventoryBefore'])
    inventory(result['inventoryAfter'])
    need(result['inventoryUnchanged'] is True and result['inventoryBefore'] == result['inventoryAfter'],
         'probe must leave actual inventory object identities, order and upgrades unchanged')
    need(type(result['suppressedNativeAudio']) is list and result['suppressedNativeAudio'] == list(AUDIO),
         'five exact fabricated native FMOD keys required; legitimate cues must remain outside this filter')


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON field: ' + key)
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError('nonfinite JSON number: ' + value)


def check_log(log, token, pid):
    errors, raw = [], None
    try:
        need(type(log) is str, 'character log text required')
        lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
        need(len(lines) == 1, 'exactly one native character integration receipt required')
        need(len(lines[0]) <= 1_000_000, 'character receipt exceeds finite size limit')
        raw = json.loads(lines[0], object_pairs_hook=strict_object, parse_constant=invalid_constant)
        validate(raw, token, pid)
    except (ValueError, TypeError, KeyError, IndexError, RecursionError) as error:
        errors.append(str(error))
    return {'errors': errors, 'raw': raw, 'scope': SCOPE}
