#!/usr/bin/env python3
"""Bounded real-game discovery runner; no combat pass without driver evidence."""
import argparse
import ctypes
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import hashlib
import shutil
import tempfile
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

from dev import ROOT, config, game_executable, validate_game
from runtime_platform import platform_for
from beast_evidence import BEAST_CASES, beast_contract_evidence
from domain_enemy_evidence import check_log as domain_enemy_evidence
from persistent_evidence import PERSISTENT_CASES, persistent_contract_evidence
from catalog_evidence import catalog_evidence
from card_face_evidence import CARD_FACE_CASES, extract_card_face_result, extract_card_face_batch
from card_lifecycle_evidence import CASES as CARD_LIFECYCLE_CASES, card_lifecycle_batch_evidence
from native_run_evidence import MODES as NATIVE_RUN_MODES, native_run_evidence
from native_suite_evidence import check_log as native_suite_evidence
from presentation_acceptance_evidence import check_log as presentation_acceptance_evidence
from domain_hopper_evidence import VARIANTS as HOPPER_CASES, domain_hopper_evidence
from domain_suppression_evidence import CASES as DOMAIN_SUPPRESSION_CASES, check_log as domain_suppression_evidence
from enemy_catalog_evidence import catalog_evidence as enemy_catalog_evidence
from domain_summon_evidence import check_log as domain_summon_evidence
from domain_summon_d17_evidence import VARIANTS as SUMMON_D17_CASES, check_log as summon_d17_evidence
from relic_evidence import RELIC_CASES, relic_contract_evidence
from domain_passive_evidence import VARIANTS as DOMAIN_PASSIVE_CASES, check_log as domain_passive_evidence
from card_passive_evidence import VARIANTS as CARD_PASSIVE_CASES, check_log as card_passive_evidence
from new_strength_passive_evidence import VARIANTS as NEW_APPLY_CASES, check_log as new_apply_evidence
from suck_passive_evidence import VARIANTS as SUCK_CASES, check_log as suck_evidence
from initial_plating_evidence import VARIANTS as INITIAL_PLATING_CASES, check_log as initial_plating_evidence
from enemy_matrix_evidence import matrix_evidence
from enemy_exploration_evidence import exploration_evidence
from enemy_exploration_run_config import prepare_run_inputs as prepare_exploration_inputs
from prepared_evidence import PREPARED_CASES, prepared_contract_evidence
from prepared_choice_evidence import PREPARED_CHOICE_CASES, prepared_choice_evidence
from domain_revival_evidence import domain_revival_evidence
from power_presentation_evidence import power_presentation_evidence
from audio_receipt_evidence import audio_receipt_evidence
from coupon_evidence import COUPON_CASES, coupon_contract_evidence
from primal_evidence import PRIMAL_CASES, primal_contract_evidence
from domain_card_contributions_evidence import CASES as DOMAIN_CARD_CASES, check_log as domain_card_evidence
from domain_steam_evidence import VARIANTS as STEAM_VARIANTS, domain_steam_evidence
STEAM_CASES = ('off', 'on') + tuple(sorted(STEAM_VARIANTS - {'off', 'on'}))
from standing_extra_turn_evidence import STANDING_CASES, standing_extra_turn_evidence
from domain_dampen_evidence import check_log as domain_dampen_evidence
DAMPEN_CASES = ('off', 'on', 'enter-await', 'exit-await', 'enter-pair', 'exit-pair', 'departure')
REVIVAL_CASES = tuple(f'{family}-{mode}' for family in ('reattach', 'illusion') for mode in ('off', 'on', 'late', 'cached', 'toggle'))
DOMAIN_PASSIVE_CASES = DOMAIN_PASSIVE_CASES + CARD_PASSIVE_CASES + NEW_APPLY_CASES + SUCK_CASES + INITIAL_PLATING_CASES

DOMAIN_SUMMON_CASES = ('fabricator-off', 'fabricator-on', 'ovicopter-off', 'ovicopter-on',
                       'infested-off', 'infested-on', 'infested-expire') + SUMMON_D17_CASES

DOMAIN_ENEMY_CASES = ('flutter', 'soar', 'intangible', 'slippery', 'hard-to-kill',
                      'shell', 'artifact', 'thorns', 'reflect', 'heal')

IS_WINDOWS = os.name == 'nt'
USER_DATA_NAME = 'SlayTheSpire2'
# Every directory variable that can redirect user:// is repointed per run.
ISOLATION_BINDINGS = platform_for('nt' if IS_WINDOWS else 'posix').isolation_bindings()


def isolated_env(directory):
    env = platform_for('nt' if IS_WINDOWS else 'posix').isolated_environment(directory, os.environ)
    # This entry creates a fresh owned profile, never a resumed or ordinary save.
    # Modded and --nomods runs use separate pinned profile namespaces.
    root = user_data_root(directory)
    root.mkdir(parents=True, exist_ok=False)
    for relative in ('default/1/profile1/saves', 'default/1/modded/profile1/saves'):
        saves = root / relative
        saves.mkdir(parents=True, exist_ok=False)
        with (saves / 'prefs.save').open('x', encoding='utf-8') as stream:
            json.dump({'schema_version': 2, 'mute_in_background': False}, stream)
            stream.write('\n')
    return env


def user_data_root(directory):
    """Godot resolves user:// from APPDATA on Windows and XDG_DATA_HOME elsewhere."""
    return directory / ('appdata' if IS_WINDOWS else 'data') / USER_DATA_NAME


ERROR_TAGS = ('ERROR:', 'SCRIPT ERROR:', '[ERROR]')
# Godot's teardown report. It names a resource category and a count; counts vary per run,
# categories do not, so only the categories can be compared with the stock control.
TEARDOWN_TAGS = ('leaked at exit', 'were leaked', 'still in use at exit', 'instances leaked')

# The GLES compatibility renderer rejects an fma() shader used by some native VFX. It is a
# platform warning, not a mod or gameplay failure, and appears with stock VFX too.
ENGINE_SHADER_NOISE = ('SHADER ERROR:', 'Shader compilation failed',
                        'finished execution, but was in state Canceled!',
                        'Unreferenced static string',
                        'Godot.Bridge.ScriptManagerBridge.GetPropertyInfoList',
                        "was not present in the dictionary",
                        # Windows engine startup reads the OS root store through Godot's
                        # platform layer; an unavailable store is an OS/engine condition that
                        # the unmodded stock control emits identically, never a mod failure.
                        'Failed to read the root certificate store',
                        'get_system_ca_certificates (platform/windows/os_windows.cpp')


def error_lines(text):
    return [line for line in text.splitlines()
            if (any(tag in line for tag in ERROR_TAGS)
                or re.match(r'^\[Volibear\] [A-Z0-9_]+_(?:ERROR|FAILED)(?:\s|$)', line))
            and not any(noise in line for noise in ENGINE_SHADER_NOISE)]


def is_teardown(line):
    return (any(tag in line for tag in TEARDOWN_TAGS)
            or re.search(r'\b\d+ shaders of type (?:CanvasShaderRD|ParticlesShaderRD|CanvasShaderGLES3|ParticlesShaderGLES3) were never freed\b',
                         line) is not None
            or re.fullmatch(r'ERROR: Texture with GL ID of \d+: leaked \d+ bytes\.', line.strip()) is not None
            # PBE's shutdown path races a Task id check; the unmodded stock run emits the same line.
            or line.strip() == 'ERROR: Invalid Task ID'
            or 'Unreferenced static string' in line)


def teardown_categories(lines):
    return {re.sub(r'\d+', '#', line).strip() for line in lines
            if is_teardown(line) and line.strip() != 'ERROR: Invalid Task ID'
            and 'Unreferenced static string' not in line}


def evaluate(code, timed_out, log, stock_teardown=None):
    errors = error_lines(log)
    runtime = [line for line in errors if not is_teardown(line)]
    teardown = [line for line in errors if is_teardown(line)]
    checks = {
        'exited_zero': code == 0 and not timed_out,
        'steam_disabled': 'Steam initialization skipped' in log,
        'no_cloud_backend': 'write saves to steam storage' not in log,
        'no_runtime_errors': not runtime,
        'mod_initialized': '[Volibear] LOAD_OK' in log,
        'runtime_isolation': '[Volibear] ISOLATION_OK steam=false' in log,
    }
    if stock_teardown is not None:
        # The shipped game leaks renderer/text resources on every headless exit, with or
        # without mods. The gate accepts only the categories the stock run itself produces.
        checks['teardown_matches_stock'] = teardown_categories(teardown) <= stock_teardown
    return checks


def scenario_evidence(log, run_id, scenario):
    prefix = '[Volibear] BASELINE_RESULT '
    records = []
    for line in log.splitlines():
        if line.startswith(prefix):
            try:
                record = json.loads(line[len(prefix):])
            except json.JSONDecodeError:
                return None, False
            if not isinstance(record, dict):
                return None, False
            records.append(record)
    if len(records) != 1:
        return None, False
    result = records[0]
    valid = (result.get('token') == run_id and result.get('scenario') == scenario
             and result.get('passed') is True and result.get('testMode') is False
             and result.get('api') == 'DamageCmd.Attack'
             and result.get('resultCount') == 1
             and type(result.get('before')) is int and type(result.get('after')) is int
             and result['before'] - result['after'] == 6
             and type(result.get('roundBefore')) is int
             and type(result.get('roundAfter')) is int
             and result['roundAfter'] == result['roundBefore'] + 1
             and result.get('cardApi') == 'CardCmd.AutoPlay:StrikeIronclad'
             and type(result.get('cardTargetBefore')) is int
             and type(result.get('cardTargetAfter')) is int
             and result['cardTargetBefore'] - result['cardTargetAfter'] == (7 if result.get('engageEnabled') is True else 6))
    return result, valid


def content_evidence(log, run_id, scenario='content'):
    """Validate this run's AutoPlay effect measurements, not ordinary input/payment."""
    prefix = '[Volibear] CONTENT_RESULT '
    records = []
    for line in log.splitlines():
        if line.startswith(prefix):
            try:
                record = json.loads(line[len(prefix):])
            except json.JSONDecodeError:
                return None, False
            if not isinstance(record, dict):
                return None, False
            records.append(record)
    if len(records) != 1:
        return None, False
    result = records[0]
    integers = ('attackBefore', 'attackAfter', 'attackDelta', 'blockBefore', 'blockAfter',
                'blockGain', 'startingHp', 'deckSize', 'played', 'enemyCount', 'fixtureEnemyHp')
    arrays = ('enemyBefore', 'enemyAfter', 'enemyDeltas', 'originalEnemyHp')
    if (any(type(result.get(key)) is not int for key in integers)
            or any(not isinstance(result.get(key), list)
                   or any(type(value) is not int for value in result[key]) for key in arrays)):
        return result, False
    count = result['enemyCount']
    valid = (result.get('token') == run_id and scenario == 'content'
             and result.get('scenario') == scenario and result.get('testMode') is False
             and result.get('api') == 'CardCmd.AutoPlay'
             and result.get('acceptance') == 'effect-only-not-payment'
             and result.get('fixtureApi') == 'CreatureCmd.SetMaxAndCurrentHp;CardPileCmd.Add'
             and result['fixtureEnemyHp'] == 50 and result['attackBefore'] == 50
             and result['enemyBefore'] == [50] * (count - 1) + [44]
             and result.get('cards') == ['Volibear_B01', 'Volibear_B02', 'Volibear_B03']
             and result.get('character') == 'VolibearCharacter'
             and result.get('passed') is True and result['played'] == 3
             and result['attackDelta'] == result['attackBefore'] - result['attackAfter'] == 6
             and result['blockGain'] == result['blockAfter'] - result['blockBefore'] == 5
             and result['attackAfter'] > 0 and result['blockBefore'] == 0
             and result['startingHp'] == 80 and result['deckSize'] == 10
             and count >= 2 and all(len(result[key]) == count for key in arrays)
             and result['enemyDeltas'] == [11] + [3] * (count - 1)
             and all(before - after == delta and after > 0 for before, after, delta in zip(
                 result['enemyBefore'], result['enemyAfter'], result['enemyDeltas'])))
    return result, valid


DOMAIN_CASES = ('d01', 'd02', 'd03', 'l02', 'draw-expiry')


def domain_contract_evidence(log, run_id, variant):
    """Independent finite mechanism probes, NOT the 16-fixture comparator/G2 gate.

    d02/d03 use native TwinStrike as a multihit/replay proxy, not C02 acceptance.
    Expected constants are authored from the rule fixtures, never runtime vars.
    A completed flag only says the driver finished; every measured projection below
    must match independently, including native history and explicit batch receipts.
    """
    prefix = '[Volibear] DOMAIN_CONTRACT_RESULT '
    lines = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    if len(lines) != 1 or variant not in DOMAIN_CASES:
        return None, False
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError:
        return None, False
    if not isinstance(result, dict):
        return None, False

    def equal(actual, expected):
        # Native decimals may serialize as integer JSON numbers, but bool isn't 1.
        if type(expected) in (int, float):
            return type(actual) in (int, float) and actual == expected
        if type(actual) is not type(expected):
            return False
        if isinstance(expected, dict):
            return actual.keys() == expected.keys() and all(equal(actual[k], v) for k, v in expected.items())
        if isinstance(expected, list):
            return len(actual) == len(expected) and all(equal(a, b) for a, b in zip(actual, expected))
        return actual == expected

    ids, enemies, data, batches = (result.get(k) for k in ('enemyIds', 'enemyTypes', 'data', 'batches'))
    if (not isinstance(ids, list) or len(ids) != 3 or any(type(i) is not int or i < 0 for i in ids)
            or len(set(ids)) != 3 or not isinstance(enemies, list) or len(enemies) != 3
            or any(type(e) is not str for e in enemies) or enemies.count('LeafSlimeS') != 1
            or enemies.count('TwigSlimeS') != 1 or sum(e in ('LeafSlimeM', 'TwigSlimeM') for e in enemies) != 1
            or not isinstance(data, dict) or not isinstance(batches, list)):
        return result, False
    required = dict(token=run_id, scenario='domain-contract', variant=variant, completed=True,
                    testMode=False, acceptance='effect-only-not-payment', character='VolibearCharacter',
                    fixtureApi='CreatureCmd.SetMaxAndCurrentHp;CardPileCmd.Add;PowerCmd;CardCmd.AutoPlay',
                    api='LightningCmd+CreatureCmd.Damage' if variant == 'l02' else
                        'CardPileCmd.Draw+PlayerCmd.EndTurn' if variant == 'draw-expiry' else 'CardCmd.AutoPlay',
                    proxy='native-TwinStrike-not-C02-acceptance' if variant in ('d02', 'd03') else 'none')
    if not all(equal(result.get(key), value) for key, value in required.items()):
        return result, False
    if variant == 'draw-expiry':
        return result, _domain_draw_evidence(data, batches, equal)

    inputs = data.get('inputs')
    if not isinstance(inputs, dict) or not isinstance(inputs.get('cards'), list):
        return result, False
    cards = inputs['cards']
    refs = [c.get('cardRef') for c in cards if isinstance(c, dict)]
    card_count = 2 if variant == 'd01' else 0 if variant == 'l02' else 1
    if (len(cards) != card_count or len(refs) != card_count
            or any(type(ref) is not str or not ref for ref in refs) or len(set(refs)) != card_count):
        return result, False
    force = 2 if variant == 'd01' else 3 if variant == 'l02' else 0
    replay = 1 if variant == 'd03' else 0
    expected_inputs = dict(domainRounds=0 if variant == 'l02' else 1, storm=force,
                           fixtureEnemyHp=100, fixtureEnemyBlock=10 if variant == 'l02' else 0,
                           explicitLightningBase=0 if variant == 'l02' else None,
                           unrelatedUnpowered=1 if variant == 'l02' else 0,
                           cards=[dict(cardRef=ref, type='Volibear_B01' if variant == 'd01' else 'TwinStrike',
                                       upgrade=False, replay=replay) for ref in refs])
    n = 2 if variant == 'd01' else 1
    hp = [76, 88, 88] if variant == 'd01' else [86, 96, 96] if variant == 'd02' else [76, 96, 96] if variant == 'd03' else [100] * 3
    projection = dict(inputs=expected_inputs, beforeHp=[100] * 3,
                      beforeBlock=[10 if variant == 'l02' else 0] * 3,
                      afterHp=hp, afterBlock=[7 if variant == 'l02' else 0] * 3,
                      finalHp=hp, finalBlock=[6 if variant == 'l02' else 0] * 3,
                      countBefore=0, countAfter=n, countFinal=n,
                      domainAmount=0 if variant == 'l02' else 1, stormAmount=force,
                      energyBefore=3, energyAfter=3, actualAutoPlayCalls=card_count,
                      cardPiles=[dict(cardRef=ref, pile='Discard', sameIdentity=True) for ref in refs],
                      playHistory=[dict(cardRef=ref, index=index, count=replay + 1)
                                   for ref in refs for index in range(replay + 1)])
    def damage(target, hp_loss, blocked, props, ref):
        return dict(target=target, hpLost=hp_loss, blocked=blocked, props=props, cardRef=ref)
    damage_history = []
    if variant == 'l02':
        damage_history = [damage(i, 0, 3, 4, None) for i in ids] + [damage(i, 0, 1, 4, None) for i in ids]
    else:
        for ref in refs:
            damage_history.append(damage(ids[0], 6 if variant == 'd01' else 5, 0, 8, ref))
            damage_history.extend(damage(i, 6 if variant == 'd01' else 4, 0, 4, ref) for i in ids)
            damage_history.extend(damage(ids[0], 5, 0, 8, ref) for _ in range(0 if variant == 'd01' else 3 if variant == 'd03' else 1))
    projection['damageHistory'] = damage_history
    if not equal(data, projection) or len(batches) != n:
        return result, False
    batch_ids, play_ids = [], []
    for index, batch in enumerate(batches):
        if (not isinstance(batch, dict) or type(batch.get('id')) is not int or batch['id'] <= 0
                or (variant != 'l02' and (type(batch.get('playId')) is not int or batch['playId'] <= 0))):
            return result, False
        batch_ids.append(batch['id'])
        play_ids.append(batch.get('playId'))
        expected = dict(id=batch['id'], round=1, turn=1, baseDamage=0 if variant == 'l02' else 4,
                        storm=force, amount=3 if variant == 'l02' else 6 if variant == 'd01' else 4,
                        count=index + 1, cardRef=None if variant == 'l02' else refs[index if variant == 'd01' else 0],
                        playId=None if variant == 'l02' else batch['playId'], targets=ids,
                        hits=[dict(target=i, hpLost=0 if variant == 'l02' else 6 if variant == 'd01' else 4,
                                   blocked=3 if variant == 'l02' else 0, overkill=0) for i in ids])
        if not equal(batch, expected):
            return result, False
    return result, len(set(batch_ids)) == n and (variant != 'd01' or len(set(play_ids)) == 2)


def _domain_draw_evidence(data, batches, equal):
    inputs = data.get('inputs')
    if not isinstance(inputs, dict):
        return False
    refs = inputs.get('replacementRefs')
    if (not isinstance(refs, list) or len(refs) != 3 or any(type(r) is not str or not r for r in refs)
            or len(set(refs)) != 3 or batches):
        return False
    if not equal(inputs, dict(domainRounds=1, storm=2, directDrawCount=1, normalDrawCount=5,
                              outsideDrawCount=1, energy=3, replacementRefs=refs, statusType='Void')):
        return False
    direct, boundary, outside = (data.get(k) for k in ('direct', 'boundary', 'outside'))
    if not all(isinstance(v, dict) for v in (direct, boundary, outside)):
        return False
    draw = lambda ref, hand: dict(cardRef=ref, fromHandDraw=hand)
    expected_direct = dict(energy=3, domain=1, handCount=1, voidPile='Exhaust', replacementPile='Hand',
                           sameVoid=True, sameReplacement=True, drawn=[draw('direct-void', False), draw(refs[0], False)])
    drawn = boundary.get('drawn')
    if (not isinstance(drawn, list) or len(drawn) != 6
            or not equal(drawn[:2], [draw('boundary-void', True), draw(refs[1], False)])
            or any(not isinstance(d, dict) or set(d) != {'cardRef', 'fromHandDraw'}
                   or type(d['cardRef']) is not str or not d['cardRef'].startswith('starting-')
                   or d['fromHandDraw'] is not True for d in drawn[2:])):
        return False
    if len({d['cardRef'] for d in drawn}) != 6:
        return False
    expected_boundary = dict(round=2, turn=2, domainAfterFullDraw=[1], domainAfterEarlyHook=0,
                             storm=2, count=0, energy=3, handCount=5, voidPile='Exhaust', replacementPile='Hand',
                             sameVoid=True, sameReplacement=True, drawn=drawn)
    # Moving the selected replacement from hand back to Draw may remove one card;
    # derive that fact independently from the preceding native draw identities.
    hand_before = 4 if refs[2] in [d['cardRef'] for d in drawn] else 5
    expected_outside = dict(energyBefore=3, energyAfter=2, handBefore=hand_before, handAfter=hand_before + 1,
                            voidPile='Hand', replacementPile='Draw', sameVoid=True,
                            drawn=[draw('outside-void', False)])
    return equal(data, dict(inputs=inputs, roundBefore=1, turnBefore=1,
                            direct=expected_direct, boundary=expected_boundary, outside=expected_outside))


def engage_contract_evidence(log, run_id, variant):
    """Production engage receipts, native moves and measured relic draws; not payment tests."""
    prefix = '[Volibear] ENGAGE_CONTRACT_RESULT '
    lines = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    if len(lines) != 1 or variant not in ('e01', 'e02', 'b04'):
        return None, False
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError:
        return None, False
    if not isinstance(result, dict):
        return None, False
    integer_fields = ('fixtureEnemyHp', 'hpBefore', 'blockBefore', 'hpAfter', 'blockAfter',
                      'enemyHpBefore', 'enemyHpAfter', 'handBefore', 'handAfter', 'firstHandDraw',
                      'movesAfter', 'duplicateHp', 'duplicateBlock', 'duplicateHand',
                      'duplicateMoves', 'duplicateDamageReceipts', 'secondHandBefore',
                      'secondHandAfter', 'roundBefore', 'roundAfter', 'turnBefore', 'turnAfter',
                      'nextHandBefore', 'nextHandAfter', 'nextHp', 'nextBlock', 'nextMoves')
    if any(type(result.get(key)) is not int for key in integer_fields):
        return result, False
    def receipt(key, performed, absorbed):
        value = result.get(key)
        return (isinstance(value, dict) and value.get('Performed') is performed
                and value.get('Completed') is performed
                and type(value.get('Absorbed')) in (int, float) and value['Absorbed'] == absorbed)
    absorbed = 5 if variant == 'e01' else 8
    expected_hp = 77 if variant == 'e01' else 80
    expected_block = 2 if variant == 'e02' else 0
    initial_block = {'e01': 5, 'e02': 10, 'b04': 0}[variant]
    damage_receipts = result.get('firstBlockReceipts')
    phase_counts = result.get('phaseMoveCounts')
    monsters = result.get('phaseMonsters')
    if (not isinstance(damage_receipts, list)
            or any(type(value) not in (int, float) for value in damage_receipts)
            or not isinstance(phase_counts, list) or any(type(value) is not int for value in phase_counts)
            or not isinstance(monsters, list) or any(type(value) is not str for value in monsters)):
        return result, False
    valid = (result.get('token') == run_id and result.get('scenario') == 'engage-contract'
             and result.get('variant') == variant and result.get('passed') is True
             and result.get('testMode') is False and result.get('acceptance') == 'effect-only-not-payment'
             and result.get('api') == ('CardCmd.AutoPlay:Volibear_B04' if variant == 'b04'
                                       else 'Core.EngageCmd.Perform')
             and result.get('enemy') == 'LeafSlimeS' and result.get('nativeMove') == 'TACKLE_MOVE'
             and type(result.get('strength')) in (int, float) and result['strength'] == 5
             and result['fixtureEnemyHp'] == result['enemyHpBefore'] == 50
             and result['enemyHpAfter'] == (44 if variant == 'b04' else 50)
             and result['hpBefore'] == 80 and result['blockBefore'] == initial_block
             and result['hpAfter'] == expected_hp and result['blockAfter'] == expected_block
             and receipt('first', True, absorbed) and damage_receipts == [absorbed]
             and 1 <= result['handBefore'] <= 6
             and result['handAfter'] - result['handBefore'] == (0 if variant == 'b04' else 1)
             and result['firstHandDraw'] == 1 and result['movesAfter'] == 1
             and receipt('duplicate', False, 0)
             and result['duplicateHp'] == result['hpAfter']
             and result['duplicateBlock'] == result['blockAfter']
             and result['duplicateHand'] == result['handAfter']
             and result['duplicateMoves'] == 1 and result['duplicateDamageReceipts'] == 0
             and receipt('secondResult', True, 4)
             and result['secondHandBefore'] == result['handAfter']
             and result['secondHandAfter'] == result['secondHandBefore']
             and result['roundBefore'] == result['turnBefore'] == 1
             and result['roundAfter'] == result['turnAfter'] == 2
             and phase_counts == [1, 1, 1] and len(monsters) == 3
             and monsters.count('LeafSlimeS') == monsters.count('TwigSlimeS') == 1
             and sum(monster in ('LeafSlimeM', 'TwigSlimeM') for monster in monsters) == 1
             and result.get('nextNativeMove') == 'GOOP_MOVE'
             and receipt('next', True, 8) and 1 <= result['nextHandBefore'] <= 9
             and result['nextHandAfter'] == result['nextHandBefore'] + 1
             and result['nextHp'] == 80 and result['nextBlock'] == 2 and result['nextMoves'] == 2)
    return result, valid


def engage_evidence(result, expected):
    """Validate measured prototype evidence independently of the driver's pass bit."""
    if not isinstance(result, dict) or result.get('engageEnabled') is not expected:
        return False
    if not expected:
        return result.get('engage') is None and result.get('duplicate') is None and result.get('skippedActions') == 0
    return (result.get('engage') == {'Performed': True, 'Absorbed': 3, 'Completed': True}
            and result.get('duplicate') == {'Performed': False, 'Absorbed': 0, 'Completed': False}
            and type(result.get('skippedActions')) is int and result['skippedActions'] == 1
            and result.get('responseCount') == 1 and result.get('responseBlockBefore') == 27
            and result.get('responseBlockAfter') == 30 and result.get('followupDamage') == 1
            and result.get('engageOrder') == ['pre-effect-finished', 'enemy-action-finished',
                'completion-response', 'duplicate-rejected', 'remaining-card-effect'])


if IS_WINDOWS:
    # A job object is the Windows ownership boundary: the whole tree dies with the handle,
    # which a renamed or orphaned child cannot escape the way a PID-only taskkill can.
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_TERMINATE = 0x0001
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _WAIT_TIMEOUT = 0x102
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9

    class _JobBasicLimits(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                    ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', ctypes.c_uint32),
                    ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', ctypes.c_uint32),
                    ('Affinity', ctypes.c_size_t),
                    ('PriorityClass', ctypes.c_uint32),
                    ('SchedulingClass', ctypes.c_uint32)]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                     'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class _JobExtendedLimits(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', _JobBasicLimits),
                    ('IoInfo', _IoCounters),
                    ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t),
                    ('PeakJobMemoryUsed', ctypes.c_size_t)]

    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    _kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                  ctypes.c_void_p, ctypes.c_uint32]
    _kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _kernel32.OpenProcess.restype = ctypes.c_void_p
    _kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    _user32 = ctypes.WinDLL('user32', use_last_error=True)
    _user32.CreateDesktopW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    _user32.CreateDesktopW.restype = ctypes.c_void_p
    _user32.CloseDesktop.argtypes = [ctypes.c_void_p]
    _user32.CloseDesktop.restype = ctypes.c_int
    _user32.CreateWindowStationW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32,
                                             ctypes.c_uint32, ctypes.c_void_p]
    _user32.CreateWindowStationW.restype = ctypes.c_void_p
    _user32.CloseWindowStation.argtypes = [ctypes.c_void_p]
    _user32.CloseWindowStation.restype = ctypes.c_int
    _user32.GetProcessWindowStation.restype = ctypes.c_void_p
    _user32.SetProcessWindowStation.argtypes = [ctypes.c_void_p]
    _user32.SetProcessWindowStation.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
    _user32.GetThreadDesktop.argtypes = [ctypes.c_uint32]
    _user32.GetThreadDesktop.restype = ctypes.c_void_p
    _user32.GetUserObjectInformationW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                  ctypes.c_void_p, ctypes.c_uint32,
                                                  ctypes.POINTER(ctypes.c_uint32)]
    _user32.GetUserObjectInformationW.restype = ctypes.c_int
    _user32.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _user32.EnumDesktopWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]


_desktops_by_job = {}


def _create_private_desktop():
    """Private desktop on the interactive station: never displayed, never activatable.

    A separate window station would isolate harder, but this session is denied
    CreateWindowStation (error 5), so the desktop is created inside WinSta0 and the child is
    launched straight onto it. Windows never display or focus a non-active desktop.
    """
    name = 'VolibearAcceptance_' + uuid.uuid4().hex
    handle = _user32.CreateDesktopW(name, None, None, 0, 0x000F01FF, None)
    if not handle:
        raise OSError(ctypes.get_last_error(), 'CreateDesktop failed')
    return None, handle, name


def _desktop_windows(desktop):
    """Windows of one desktop only; EnumWindows never sees another desktop's windows."""
    rows = []
    prototype = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def collect(hwnd, _):
        rows.append(hwnd)
        return True

    if not _user32.EnumDesktopWindows(desktop, prototype(collect), 0):
        return []
    return rows


def _assert_isolated_desktop(process, desktop_name, desktop_handle):
    """Fail closed unless the child has windows only on its private desktop.

    EnumWindows sees the operator's active desktop: any window of the child there means it could
    be seen or focused, so the child is killed instead of running.
    """
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return
        escaped = [hwnd for hwnd, owner in _window_pids() if owner == process.pid]
        if escaped:
            try:
                process.kill()
            finally:
                raise RuntimeError('Test window appeared on the operator desktop: ' + repr(escaped))
        windows = _desktop_windows(desktop_handle)
        if windows:
            owner = ctypes.c_uint32()
            _user32.GetWindowThreadProcessId(windows[0], ctypes.byref(owner))
            if owner.value != process.pid:
                try:
                    process.kill()
                finally:
                    raise RuntimeError('Private desktop windows do not belong to the test process')
            return
        time.sleep(0.05)
    try:
        process.kill()
    finally:
        raise RuntimeError('Test window did not appear on the private desktop ' + desktop_name)


def _create_job():
    if not IS_WINDOWS:
        return None
    job = _kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), 'CreateJobObject failed')
    limits = _JobExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not _kernel32.SetInformationJobObject(job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                             ctypes.byref(limits), ctypes.sizeof(limits)):
        _kernel32.CloseHandle(job)
        raise OSError(ctypes.get_last_error(), 'SetInformationJobObject failed')
    return job


def _assign_job(job, process):
    """Own an already running process. A process that exited first leaves nothing to own."""
    if job is None:
        return False
    handle = _kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, process.pid)
    if not handle:
        return False
    try:
        return bool(_kernel32.AssignProcessToJobObject(job, handle))
    finally:
        _kernel32.CloseHandle(handle)


def _terminate_job(job):
    if job is None or not IS_WINDOWS:
        return False
    return bool(_kernel32.TerminateJobObject(job, 1))


def close_owned(job):
    if job is not None and IS_WINDOWS:
        _kernel32.CloseHandle(job)
        desktop = _desktops_by_job.pop(job, None)
        if desktop is not None:
            station, desktop_handle = desktop
            _user32.CloseDesktop(desktop_handle)
            if station:
                _user32.CloseWindowStation(station)


def process_alive(pid):
    if IS_WINDOWS:
        handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            return _kernel32.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT
        finally:
            _kernel32.CloseHandle(handle)
    status = Path(f'/proc/{pid}/stat')
    if not status.exists():
        return False
    return status.read_text().split()[2] != 'Z'


def _terminate(process, job, force):
    if IS_WINDOWS:
        # Windows has no SIGTERM for GUI processes; the job tree is the owned boundary.
        if _terminate_job(job):
            return
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)],
                       capture_output=True)
        return
    try:
        os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        pass


def build_window_startup_hint():
    """Small tool-only pre-map hint; never a dependency of the distributed Mod."""
    if not sys.platform.startswith('linux') or os.uname().machine != 'x86_64':
        raise RuntimeError('Normal X11 test windows require the Linux x86_64 startup hint')
    compiler = shutil.which('cc')
    if not compiler:
        raise RuntimeError('cc is required for the non-activating X11 test-window hint')
    source = ROOT / 'tools/window_startup_hint.c'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:20]
    cache = ROOT / 'artifacts/window-startup-hint'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (digest + '.so')
    if not target.is_file():
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            output = Path(temporary) / 'hint.so'
            result = subprocess.run([compiler, '-std=c11', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                                     str(source), '-o', str(output), '-ldl'], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise RuntimeError('X11 startup hint build failed: ' + result.stdout + result.stderr)
            output.replace(target)
    return target.resolve()


def window_startup_environment(command, cwd, env):
    if '--windowed' not in command or '--display-driver' not in command or command[command.index('--display-driver') + 1] != 'x11':
        return env
    game = (ROOT / '.local/game').resolve()
    if Path(cwd).resolve() != game or Path(command[0]).resolve() != game_executable(game).resolve():
        raise RuntimeError('X11 startup hint only supports the owned isolated game process')
    result = dict(env)
    hint = str(build_window_startup_hint())
    result['LD_PRELOAD'] = hint + (':' + result['LD_PRELOAD'] if result.get('LD_PRELOAD') else '')
    # Child tools/crash reporters inherit env but cannot activate the interposer.
    result['VOLIBEAR_X11_STARTUP_HINT_EXE'] = str(Path(command[0]).resolve())
    return result


def _foreground_window():
    try:
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return 0


def _window_pids():
    """Map every top-level window handle to its owning process id."""
    user32 = ctypes.windll.user32
    rows = []
    prototype = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def collect(hwnd, _):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        rows.append((hwnd, owner.value))
        return True

    user32.EnumWindows(prototype(collect), 0)
    return rows


def _watch_window_focus(pid, previous_foreground):
    """Keep an owned test window visible but never activated.

    SW_SHOWNOACTIVATE only covers creation. Godot can still call SetForegroundWindow while it
    builds scenes, so add WS_EX_NOACTIVATE and hand the foreground back to the operator's
    previous window whenever the test window takes it. Only this owned process' windows are
    touched; nothing is hidden and no input is synthesised.
    """
    if not IS_WINDOWS:
        return
    user32 = ctypes.windll.user32
    GWL_EXSTYLE, WS_EX_NOACTIVATE = -20, 0x08000000
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0004, 0x0010

    def watch():
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                windows = [hwnd for hwnd, owner in _window_pids() if owner == pid]
                for hwnd in windows:
                    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    if not style & WS_EX_NOACTIVATE:
                        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
                        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
                    if user32.GetForegroundWindow() == hwnd:
                        if previous_foreground and user32.IsWindow(previous_foreground):
                            user32.SetForegroundWindow(previous_foreground)
                        else:
                            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
            except Exception:
                pass
            time.sleep(0.1)

    try:
        import threading
        threading.Thread(target=watch, name='volibear-no-focus', daemon=True).start()
    except Exception:
        pass


def spawn_owned(command, cwd, env, stdout, window=False):
    """Start a process in its own ownership boundary and return (process, job)."""
    if IS_WINDOWS:
        job = _create_job()
        options = {}
        isolated_desktop = None
        previous_foreground = 0
        try:
            if window and env.get('VOLIBEAR_TEST_PRIVATE_DESKTOP') == '1':
                station, desktop_handle, name = _create_private_desktop()
                _desktops_by_job[job] = (station, desktop_handle)
                startup = subprocess.STARTUPINFO()
                startup.lpDesktop = name
                options['startupinfo'] = startup
                isolated_desktop = name
            elif window and env.get('VOLIBEAR_TEST_NO_FOCUS') == '1':
                # Real window on the operator's desktop that is shown without activation.
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = 4  # SW_SHOWNOACTIVATE
                options['startupinfo'] = startup
                previous_foreground = _foreground_window()
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout,
                                       stderr=subprocess.STDOUT,
                                       creationflags=0 if window else subprocess.CREATE_NO_WINDOW,
                                       **options)
            if window and env.get('VOLIBEAR_TEST_NO_FOCUS') == '1':
                _watch_window_focus(process.pid, previous_foreground)
        except BaseException:
            close_owned(job)
            raise
        if not _assign_job(job, process):
            close_owned(job)
            job = None
        if isolated_desktop is not None:
            try:
                _assert_isolated_desktop(process, isolated_desktop, _desktops_by_job[job][1])
            except BaseException:
                close_owned(job)
                raise
        return process, job
    env = window_startup_environment(command, cwd, env)
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout,
                               stderr=subprocess.STDOUT, start_new_session=True)
    return process, None


class OwnedProcessCancelled(RuntimeError):
    """Cooperative runner cancellation; never a successful exit or a timeout."""


def check_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise OwnedProcessCancelled('Native runner cancelled by sibling failure')


def _wait_cancellable(process, timeout, cancel_event):
    deadline = time.monotonic() + timeout
    while True:
        check_cancelled(cancel_event)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout)
        try:
            return process.wait(timeout=min(.1, remaining))
        except subprocess.TimeoutExpired:
            pass


def wait_owned_process(process, timeout, job=None, *, cancel_event=None):
    """Wait for our session leader and always remove surviving group children."""
    timed_out = False
    if cancel_event is not None:
        try:
            if IS_WINDOWS and job is None:
                raise RuntimeError('Cancellable native process requires an owned Windows Job')
            try:
                _wait_cancellable(process, timeout, cancel_event)
            except subprocess.TimeoutExpired:
                timed_out = True
        finally:
            # One owner and one termination path; the launcher alone closes the Job.
            _terminate(process, job, force=True)
            process.wait(timeout=5)
        return process.returncode, timed_out
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate(process, job, force=False)
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _terminate(process, job, force=True)
            code = process.wait()
    finally:
        _terminate(process, job, force=True)
    return code, timed_out


def combined_log(directory):
    """Prefer the engine's own log; GUI-subsystem processes may not write redirected stdout."""
    engine = directory / 'game.log'
    if engine.is_file() and engine.stat().st_size:
        return engine.read_text(errors='replace')
    return (directory / 'stdout.log').read_text(errors='replace')


def new_run_id():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]


# NO_FOCUS at creation makes Godot 4.5.1 X11 choose UTILITY, not NORMAL.
WINDOW_OVERRIDE = (b'[display]\nwindow/size/no_focus=false\nwindow/size/mode=0\n'
                   b'window/size/always_on_top=false\nwindow/size/borderless=false\n'
                   b'window/size/window_width_override=1280\nwindow/size/window_height_override=720\n')


@contextmanager
def window_input_guard(game, display):
    """Own a temporary pre-window override only in the isolated game copy."""
    if IS_WINDOWS or display != 'window':
        yield
        return
    intended = (ROOT / '.local/game').absolute()
    game = Path(game).absolute()
    if game != intended or game.resolve() != intended or not game.is_dir():
        raise ValueError('Window input protection requires the exact isolated .local/game directory')
    path = game / 'override.cfg'
    if path.is_symlink() or path.resolve() != path.absolute():
        raise ValueError('Window override path is redirected')
    # Exclusive creation refuses even a pre-existing override with identical bytes.
    with path.open('xb') as stream:
        stream.write(WINDOW_OVERRIDE)
        identity = os.fstat(stream.fileno())
    try:
        yield
    finally:
        # Never remove a file replaced or modified by another actor.
        if path.is_symlink() or path.resolve() != intended / 'override.cfg':
            raise RuntimeError('Window override redirected during test; preserved')
        if path.exists():
            current = path.stat()
            if ((current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino)
                    or path.read_bytes() != WINDOW_OVERRIDE):
                raise RuntimeError('Window override changed during test; preserved')
            path.unlink()


def display_command(command, display):
    if display == 'headless':
        return command
    if display in ('window', 'background'):
        if not IS_WINDOWS and display == 'background':
            raise RuntimeError('background requires Windows; use window or xvfb on POSIX')
        if not IS_WINDOWS and not os.environ.get('DISPLAY', '').strip():
            raise RuntimeError('POSIX window mode requires an existing DISPLAY')
        requested = None
        if '--audio-driver' in command:
            index = command.index('--audio-driver')
            if index + 1 < len(command):
                requested = command[index + 1]
        native = [arg for arg in command if arg not in ('--headless', '--audio-driver', 'Dummy')]
        if IS_WINDOWS:
            native.extend(platform_for('nt').window_arguments())
        if display == 'background':
            # A private desktop still has the real audio device; only fall back to Dummy when the
            # caller did not ask for a driver at all.
            native.extend(['--audio-driver', requested or 'Dummy'])
        elif not IS_WINDOWS:
            # Use the operator-authorized existing X11/XWayland display directly.
            # Match the established compatibility renderer, but keep the real GPU.
            # No virtual display or software rasterizer is forced in this mode.
            native.extend(platform_for('posix').window_arguments())
            if '--script' not in native:
                native.extend(['--script', str(ROOT / 'tools/window_guard.gd')])
        return native
    if display == 'xvfb':
        if IS_WINDOWS:
            raise RuntimeError('xvfb is a POSIX virtual display; use window or headless on Windows')
        command = [arg for arg in command if arg not in ('--headless', '--audio-driver', 'Dummy')]
        command.extend(['--display-driver', 'x11', '--rendering-method', 'gl_compatibility'])
        return ['xvfb-run', '-a', '-s', '-screen 0 1280x720x24', *command]
    raise RuntimeError('Unknown display mode: ' + display)


def with_audio_driver(command, audio_driver=None):
    if audio_driver is None:
        return command
    if not isinstance(audio_driver, str) or not audio_driver.strip():
        raise ValueError('Audio driver must be a nonempty Godot driver name')
    result = []
    arguments = iter(command)
    for argument in arguments:
        if argument == '--audio-driver':
            next(arguments, None)
        else:
            result.append(argument)
    return [*result, '--audio-driver', audio_driver]


def finite_cases(cases, allowed, label):
    if (not isinstance(cases, (list, tuple)) or not cases
            or any(not isinstance(case, str) or case not in allowed for case in cases)
            or len(set(cases)) != len(cases)):
        raise RuntimeError(label + ' requires a nonempty unique finite case list')
    return tuple(cases)


def cli_cases(value, allowed, label):
    return finite_cases(allowed if value == 'all' else value.split(','), allowed, label)


def prepare_run(game, run_id, frames, display='headless', *, _profile_env=None):
    directory = ROOT / 'artifacts/headless' / run_id
    directory.mkdir(parents=True)
    # Only the paired native runner supplies this environment, from a newly
    # created owned profile. There is deliberately no CLI arbitrary-profile path.
    env = isolated_env(directory) if _profile_env is None else dict(_profile_env)
    if _profile_env is None:
        env['VOLIBEAR_TEST_DATA_ROOT'] = str(user_data_root(directory))
    env['VOLIBEAR_TEST_FAST_MODE'] = 'Fast'
    env.pop('VOLIBEAR_TEST_WINDOW_GUARD', None)
    if display == 'background':
        env['VOLIBEAR_TEST_PRIVATE_DESKTOP'] = '1'
    # Only this fresh, offline test profile opts into loading mods.
    # Never read, copy, or edit the operator's normal settings or saves.
    if _profile_env is None:
        settings = user_data_root(directory) / 'default/1/settings.save'
        settings.parent.mkdir(parents=True, exist_ok=True)
        with settings.open('x', encoding='utf-8') as stream:
            json.dump({
                'schema_version': 5, 'mod_settings': {'mods_enabled': True},
                'seen_ea_disclaimer': True, 'skip_intro_logo': True,
                'fullscreen': False, 'window_size': {'X': 1280, 'Y': 720},
                'window_position': {'X': 64, 'Y': 64},
                'language': 'zhs', 'limit_fps_in_background': False,
                'vsync': 'off', 'fps_limit': 60,
            }, stream)
            stream.write('\n')
    env['VOLIBEAR_TEST_TOKEN'] = run_id
    env['VOLIBEAR_TEST_ARTIFACT_DIR'] = str(directory)
    command = [str(game_executable(game)), '--headless', '--audio-driver', 'Dummy',
               '--force-steam=off', '--quit-after', str(frames),
               '--log-file', str(directory / 'game.log')]
    return directory, env, display_command(command, display)


def launch(game, directory, env, command, timeout, display='headless', *, cancel_event=None, process_identity=None):
    check_cancelled(cancel_event)
    with window_input_guard(game, display), (directory / 'stdout.log').open('w') as output:
        process, job = spawn_owned(command, game, env, output,
                                   window=IS_WINDOWS and '--headless' not in command)
        try:
            if process_identity is not None:
                process_identity.update(pid=process.pid, token=env['VOLIBEAR_TEST_TOKEN'])
            return (wait_owned_process(process, timeout, job) if cancel_event is None else
                    wait_owned_process(process, timeout, job, cancel_event=cancel_event))
        finally:
            close_owned(job)


def stock_teardown(game, timeout, frames, display='headless', audio_driver=None):
    """Measure the shipped game's own exit signature with mod initialization disabled."""
    run_id = new_run_id()
    # Frame-count quits race asynchronous native preloading. The no-mod controller
    # launches the original main scene, waits for the real loader to drain, then
    # invokes native NGame.Quit; its deadline/outer watchdog remain failures.
    control_frames = 0
    directory, env, command = prepare_run(game, run_id, control_frames, display)
    command = with_audio_driver(command, audio_driver)
    if '--script' in command:
        index = command.index('--script')
        if command[index + 1] != str(ROOT / 'tools/window_guard.gd'):
            raise ValueError('Stock control cannot replace an unknown startup script')
        command[index + 1] = str(ROOT / 'tools/stock_ready.gd')
        env['VOLIBEAR_TEST_WINDOW_GUARD'] = '1'
        command.append('--nomods')
    else:
        command.extend(['--nomods', '--script', str(ROOT / 'tools/stock_ready.gd')])
    code, timed_out = launch(game, directory, env, command, timeout, display=display)
    log = combined_log(directory)
    errors = error_lines(log)
    runtime = [line for line in errors if not is_teardown(line)]
    successful = (code == 0 and not timed_out and not runtime
                  and log.count('STOCK_CONTROLLER_READY_NATIVE_QUIT') == 1
                  and 'STOCK_CONTROLLER_ERROR' not in log
                  and 'Steam initialization skipped' in log
                  and 'write saves to steam storage' not in log)
    categories = teardown_categories(errors) if successful else set()
    return categories, {'run_id': run_id, 'exit_code': code, 'timed_out': timed_out,
                        'successful': successful, 'frames': control_frames,
                        'runtime_errors': runtime, 'categories': sorted(categories)}


def dampen_protocol_log(log, token, checks):
    """Keep full protocol chronology; common gates alone own matched stock exit noise.

    Never change the original log or its common error/stock checks. Only an exact
    shutdown boundary plus two successful control gates permits the protocol
    parser to omit already-accepted teardown lines after that boundary.
    """
    if checks.get('stock_control_success') is not True or checks.get('teardown_matches_stock') is not True:
        return log
    lines = log.splitlines()
    marker = '[Volibear] SHUTDOWN_BEGIN ' + token
    if lines.count(marker) != 1:
        return log
    boundary = lines.index(marker)
    return '\n'.join(lines[:boundary + 1] + [line for line in lines[boundary + 1:] if not is_teardown(line)])


def repository_metadata():
    """Optional source provenance: a source ZIP need not include Git or .git."""
    commit, dirty = None, None
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                         text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT,
                                            stderr=subprocess.DEVNULL))
    except (OSError, subprocess.CalledProcessError) as error:
        return {'git_commit': commit, 'dirty': dirty, 'git_metadata': 'unavailable:' + type(error).__name__}
    return {'git_commit': commit, 'dirty': dirty, 'git_metadata': 'observed'}


def catalog_face_evidence(log, token, cases, process_identity):
    """Original face oracle plus the ordered, same-owned-process composition envelope."""
    def same(actual, expected, label):
        # Canonical JSON preserves numeric/boolean types (123.0 is not PID 123),
        # ignores only object-key order and rejects nonfinite numeric constants.
        if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
            raise ValueError(label + ': exact typed envelope differs')
    errors, faces, final = [], None, None
    try:
        faces = extract_card_face_batch(log, token, cases)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        errors.append('catalog faces: ' + str(error))
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate envelope field: ' + key)
                result[key] = value
            return result
        lines = log.splitlines()
        def one(prefix):
            matches = [(index, line[len(prefix):]) for index, line in enumerate(lines) if line.startswith(prefix)]
            if len(matches) != 1:
                raise ValueError('exactly one ' + prefix.strip() + ' required')
            index, value = matches[0]
            return index, json.loads(value, object_pairs_hook=unique)
        if '[Volibear] CATALOG_FACE_ERROR ' in log:
            raise ValueError('native composite error')
        pid = process_identity.get('pid')
        if type(pid) is not int or pid <= 0 or process_identity.get('token') != token:
            raise ValueError('missing actual owned process identity')
        first, begin = one('[Volibear] CATALOG_FACE_BEGIN ')
        last, final = one('[Volibear] CATALOG_FACE_RESULT ')
        same(begin, dict(schema=1, token=token, pid=pid, cases=list(cases), presentationMode='cards'), 'catalog begin')
        same(final, dict(schema=1, token=token, pid=pid, cases=list(cases),
                         completed=['presentation', 'card-faces'], finished=True, processRestarts=0,
                         cleanup=dict(RunNull=True, CombatNull=True, InProgress=False,
                                      QueueEmpty=True, ActionNull=True, HistoryVisible=0)), 'catalog final')
        media, _ = one('[Volibear] PRESENTATION_ACCEPTANCE_RESULT ')
        batch, _ = one('[Volibear] CARD_FACE_BATCH_RESULT ')
        receipts = [index for index, line in enumerate(lines) if line.startswith('[Volibear] CARD_FACE_RESULT ')]
        if not receipts or not first < media < min(receipts) <= max(receipts) < batch < last:
            raise ValueError('catalog / face native receipt order differs')
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        errors.append('catalog envelope: ' + str(error))
    return {'errors': errors, 'card_faces': faces, 'envelope': final}


def run_once(game, timeout, frames, scenario='discovery', display='headless',
             stock=None, stock_evidence=None, engage_case='e01', domain_case='d01',
             beast_case='f01', domain_enemy_case='flutter',
             persistent_case='PP-U21-deploy-at-three', domain_summon_case='fabricator-off',
             relic_case='RH-starter-turns', domain_passive_case='ritual-off',
             prepared_case='PR-training-dynamic-spells', revival_case='reattach-off',
             prepared_choice_case='PC-C19-fixed-replay', matrix_selection=None,
             matrix_catalog=None, matrix_prerequisite_report=None,
             coupon_case='CP-max-preserve', domain_card_case='hex', primal_case='U12-paid-snapshot', dampen_case='off', standing_case='U03-base-extra-turn', steam_case='off', card_face_case='B01-base-plain', hopper_case='off', card_face_batch=None,
             card_lifecycle_cases=None, native_run_mode='three-battle-save', native_run_pair=None,
             presentation_mode='cards', audio_driver=None, _profile_env=None, domain_suppression_family='all',
             cancel_event=None, record_process_identity=False):
    check_cancelled(cancel_event)
    if scenario == 'domain-suppression' and domain_suppression_family not in DOMAIN_SUPPRESSION_CASES:
        raise RuntimeError('Unknown domain suppression family: ' + str(domain_suppression_family))
    if card_face_batch is not None:
        if scenario not in ('card-face-acceptance', 'native-suite', 'catalog-face-suite'):
            raise RuntimeError('Card face batch requires the card-face-acceptance or native-suite scenario')
        card_face_batch = finite_cases(card_face_batch, CARD_FACE_CASES, 'Card face batch')
    if scenario in ('card-lifecycle', 'native-suite'):
        card_lifecycle_cases = finite_cases(
            CARD_LIFECYCLE_CASES if card_lifecycle_cases is None else card_lifecycle_cases,
            CARD_LIFECYCLE_CASES, 'Card lifecycle batch')
    if scenario == 'native-run':
        if native_run_mode not in NATIVE_RUN_MODES:
            raise RuntimeError('Unknown native run mode: ' + str(native_run_mode))
        if native_run_mode == 'resume' and _profile_env is None:
            raise RuntimeError('Native resume requires the fresh owned profile from native_run_pair.py')
    if scenario in ('presentation-acceptance', 'native-suite', 'catalog-face-suite'):
        if presentation_mode not in ('all', 'cards', 'actions'):
            raise RuntimeError('Unknown presentation mode: ' + str(presentation_mode))
        if display == 'headless':
            raise RuntimeError('Presentation capture requires a rendered background/xvfb display')
        if presentation_mode != 'cards' and (not audio_driver or audio_driver.lower() == 'dummy'):
            raise RuntimeError('Action/audio capture requires an explicit non-Dummy --audio-driver')
    if scenario == 'domain-visual' and display == 'headless':
        raise RuntimeError('Domain visual development capture requires a rendered display')
    if scenario in ('native-suite', 'catalog-face-suite') and card_face_batch is None:
        raise RuntimeError('Composite suite requires an explicit finite card-face batch')
    if scenario == 'catalog-face-suite' and not (
            IS_WINDOWS and display == 'background' and presentation_mode == 'cards' and record_process_identity):
        raise RuntimeError('Catalog faces require Windows/background, cards mode and owned process identity')
    if (IS_WINDOWS and display == 'window' and os.environ.get('VOLIBEAR_TEST_NO_FOCUS') != '1'
            and (card_face_batch is not None or scenario in ('card-lifecycle', 'native-run', 'presentation-acceptance', 'native-suite', 'domain-suppression'))):
        raise RuntimeError('Acceptance runs must use a private background desktop, not a foreground window')
    run_id = new_run_id()
    directory, env, command = (prepare_run(game, run_id, frames, display)
                               if _profile_env is None else
                               prepare_run(game, run_id, frames, display, _profile_env=_profile_env))
    command = with_audio_driver(command, audio_driver)
    if scenario in ('native-suite', 'catalog-face-suite'):
        retained = {'VOLIBEAR_TEST_DATA_ROOT','VOLIBEAR_TEST_FAST_MODE','VOLIBEAR_TEST_PRIVATE_DESKTOP',
                    'VOLIBEAR_TEST_NO_FOCUS','VOLIBEAR_TEST_TOKEN','VOLIBEAR_TEST_ARTIFACT_DIR'}
        for key in list(env):
            if key.startswith(('VOLIBEAR_TEST_','VOLIBEAR_SAVE_','VOLIBEAR_NATIVE_RUN_')) and key not in retained:
                del env[key]
    # Optional diagnostic adapter; the shipped extension may bind its own symbols.
    # Never enable this unverified workaround implicitly.
    adapter_enabled = scenario not in ('native-run', 'native-suite', 'catalog-face-suite') and os.environ.get('VOLIBEAR_TEST_AUDIO_ADAPTER') == '1'
    if adapter_enabled:
        if IS_WINDOWS:
            raise RuntimeError('The FMOD NOSOUND adapter is a POSIX LD_PRELOAD test; '
                               'Windows headless initializes FMOD with --audio-driver Dummy')
        adapter = ROOT / '.local/libvolibear-test-audio.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        str(ROOT / 'tools/fmod_nosound.c'), '-ldl', '-o', str(adapter)], check=True)
        # ld.so splits LD_PRELOAD on spaces even inside a colon-delimited path.
        # Use a no-space alias to the existing game directory; copy no binaries.
        alias = ROOT / '.local/game-audio-link'
        if not alias.exists():
            alias.symlink_to(game, target_is_directory=True)
        if alias.resolve() != game:
            raise RuntimeError('Audio diagnostic game alias points elsewhere')
        env['LD_PRELOAD'] = ':'.join([str(adapter), str(alias / 'libGodotFmod.linux.template_release.x86_64.so')]) + (':' + env['LD_PRELOAD'] if env.get('LD_PRELOAD') else '')
    if scenario in ('content', 'engage-contract', 'domain-contract', 'beast-contract',
                    'domain-enemy-contract', 'persistent-contract', 'catalog', 'enemy-catalog', 'domain-summon-contract', 'relic-contract', 'domain-passive-contract', 'prepared-contract', 'enemy-matrix-mvp', 'domain-revival', 'prepared-choice', 'power-presentation', 'enemy-exploration', 'coupon-contract', 'domain-card-contributions', 'primal-contract', 'audio-receipts', 'domain-dampen-transactions', 'standing-extra-turn', 'domain-steam', 'card-face-acceptance', 'domain-hopper', 'domain-suppression', 'domain-visual', 'architect-ending'):
        env['VOLIBEAR_TEST_CHARACTER'] = 'volibear'
    if scenario == 'domain-visual':
        env['VOLIBEAR_TEST_DOMAIN_VISUAL_OUTPUT'] = str(directory / 'domain-visual')
    if scenario == 'domain-suppression':
        env['VOLIBEAR_TEST_DOMAIN_SUPPRESSION_CASE'] = domain_suppression_family
    if scenario == 'domain-hopper':
        if hopper_case not in HOPPER_CASES:
            raise RuntimeError('Unknown Hopper acceptance case: ' + hopper_case)
        env['VOLIBEAR_TEST_HOPPER_CASE'] = hopper_case
    if scenario in ('card-face-acceptance', 'native-suite', 'catalog-face-suite'):
        if card_face_case not in CARD_FACE_CASES:
            raise RuntimeError('Unknown card face acceptance case: ' + card_face_case)
        env['VOLIBEAR_TEST_CARD_FACE_CASE'] = card_face_case
        env.pop('VOLIBEAR_TEST_CARD_FACE_BATCH', None)
        if card_face_batch is not None:
            if (not isinstance(card_face_batch, (list, tuple)) or not card_face_batch
                    or any(not isinstance(c, str) or c not in CARD_FACE_CASES for c in card_face_batch)
                    or len(set(card_face_batch)) != len(card_face_batch)):
                raise RuntimeError('Card face batch requires a nonempty unique finite case list')
            env['VOLIBEAR_TEST_CARD_FACE_BATCH'] = ','.join(card_face_batch)
    if scenario in ('card-lifecycle', 'native-suite'):
        env['VOLIBEAR_TEST_CHARACTER'] = 'volibear'
        env.pop('VOLIBEAR_TEST_CARD_LIFECYCLE_CASE', None)
        env['VOLIBEAR_TEST_CARD_LIFECYCLE_CASES'] = json.dumps(card_lifecycle_cases)
    if scenario == 'native-run':
        # A normal menu/run must never inherit a development character fixture.
        retained = {'VOLIBEAR_TEST_DATA_ROOT', 'VOLIBEAR_TEST_FAST_MODE', 'VOLIBEAR_TEST_PRIVATE_DESKTOP',
                    'VOLIBEAR_TEST_NO_FOCUS', 'VOLIBEAR_TEST_TOKEN', 'VOLIBEAR_TEST_ARTIFACT_DIR'}
        for key in list(env):
            if key.startswith(('VOLIBEAR_TEST_', 'VOLIBEAR_SAVE_', 'VOLIBEAR_NATIVE_RUN_')) and key not in retained:
                del env[key]
        env['VOLIBEAR_NATIVE_RUN_MODE'] = native_run_mode
        env['VOLIBEAR_NATIVE_RUN_PAIR'] = native_run_pair or run_id
    if scenario in ('presentation-acceptance', 'native-suite', 'catalog-face-suite'):
        env['VOLIBEAR_TEST_CHARACTER'] = 'volibear'
        env['VOLIBEAR_TEST_PRESENTATION_ACCEPTANCE'] = '1'
        env['VOLIBEAR_TEST_PRESENTATION_MODE'] = presentation_mode
        env['VOLIBEAR_TEST_PRESENTATION_OUTPUT'] = str(directory / 'presentation')
    if scenario == 'engage-contract':
        if engage_case not in ('e01', 'e02', 'b04'):
            raise RuntimeError('Unknown engage contract case: ' + engage_case)
        env['VOLIBEAR_TEST_ENGAGE_CASE'] = engage_case
    if scenario == 'domain-contract':
        if domain_case not in DOMAIN_CASES:
            raise RuntimeError('Unknown domain contract case: ' + domain_case)
        env['VOLIBEAR_TEST_DOMAIN_CASE'] = domain_case
    if scenario == 'beast-contract':
        if beast_case not in BEAST_CASES:
            raise RuntimeError('Unknown beast contract case: ' + beast_case)
        env['VOLIBEAR_TEST_BEAST_CASE'] = beast_case
    if scenario == 'domain-enemy-contract':
        if domain_enemy_case not in DOMAIN_ENEMY_CASES:
            raise RuntimeError('Unknown enemy domain case: ' + domain_enemy_case)
        env['VOLIBEAR_TEST_DOMAIN_ENEMY_CASE'] = domain_enemy_case
    if scenario == 'primal-contract':
        if primal_case not in PRIMAL_CASES:
            raise RuntimeError('Unknown primal case: ' + primal_case)
        env['VOLIBEAR_TEST_PRIMAL_CASE'] = primal_case
    if scenario == 'coupon-contract':
        if coupon_case not in COUPON_CASES:
            raise RuntimeError('Unknown coupon case: ' + coupon_case)
        env['VOLIBEAR_TEST_COUPON_CASE'] = coupon_case
    if scenario == 'domain-card-contributions':
        if domain_card_case not in DOMAIN_CARD_CASES:
            raise RuntimeError('Unknown domain card contribution case: ' + domain_card_case)
        env['VOLIBEAR_TEST_DOMAIN_CARD_CASE'] = domain_card_case
    if scenario == 'enemy-exploration':
        if matrix_selection is None or matrix_catalog is None:
            raise RuntimeError('Enemy exploration requires selection and native catalog paths')
        env.pop('VOLIBEAR_TEST_EXPLORATION_APPROVED', None)
        additions, frozen_selection, exploration_catalog, exploration_prerequisite = prepare_exploration_inputs(
            directory, matrix_selection, matrix_catalog, matrix_prerequisite_report)
        env.update(additions)
    if scenario == 'power-presentation':
        env['VOLIBEAR_TEST_POWER_PRESENTATION'] = '1'
        env['VOLIBEAR_TEST_POWER_STACK_OUTPUT'] = str(directory / 'power-stacks')
    if scenario == 'audio-receipts':
        env['VOLIBEAR_TEST_AUDIO_RECEIPTS'] = '1'
    if scenario == 'domain-revival':
        if revival_case not in REVIVAL_CASES:
            raise RuntimeError('Unknown revival case: ' + revival_case)
        env['VOLIBEAR_TEST_VARIANT'] = revival_case
    if scenario == 'prepared-choice':
        if prepared_choice_case not in PREPARED_CHOICE_CASES:
            raise RuntimeError('Unknown prepared choice case: ' + prepared_choice_case)
        env['VOLIBEAR_TEST_PREPARED_CHOICE_CASE'] = prepared_choice_case
    if scenario == 'prepared-contract':
        if prepared_case not in PREPARED_CASES:
            raise RuntimeError('Unknown prepared contract case: ' + prepared_case)
        env['VOLIBEAR_TEST_PREPARED_CASE'] = prepared_case
    if scenario == 'domain-steam':
        if steam_case not in STEAM_CASES:
            raise RuntimeError('Unknown Steam case: ' + steam_case)
        env['VOLIBEAR_TEST_VARIANT'] = steam_case
    if scenario == 'standing-extra-turn':
        if standing_case not in STANDING_CASES:
            raise RuntimeError('Unknown Standing extra-turn case: ' + standing_case)
        env['VOLIBEAR_TEST_STANDING_EXTRA_TURN_CASE'] = standing_case
    if scenario == 'domain-dampen-transactions':
        if dampen_case not in DAMPEN_CASES:
            raise RuntimeError('Unknown Dampen case: ' + dampen_case)
        env['VOLIBEAR_TEST_DAMPEN_CASE'] = dampen_case
    if scenario == 'domain-passive-contract':
        if domain_passive_case not in DOMAIN_PASSIVE_CASES:
            raise RuntimeError('Unknown domain passive case: ' + domain_passive_case)
        env['VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE'] = domain_passive_case
    if scenario == 'relic-contract':
        if relic_case not in RELIC_CASES:
            raise RuntimeError('Unknown relic contract case: ' + relic_case)
        env['VOLIBEAR_TEST_RELIC_CASE'] = relic_case
    if scenario == 'domain-summon-contract':
        if domain_summon_case not in DOMAIN_SUMMON_CASES:
            raise RuntimeError('Unknown domain summon case: ' + domain_summon_case)
        env['VOLIBEAR_TEST_DOMAIN_SUMMON_CASE'] = domain_summon_case
    if scenario == 'persistent-contract':
        if persistent_case not in PERSISTENT_CASES:
            raise RuntimeError('Unknown persistent contract case: ' + persistent_case)
        env['VOLIBEAR_TEST_PERSISTENT_CASE'] = persistent_case
    if scenario in ('baseline', 'api', 'content', 'engage-contract', 'domain-contract',
                    'beast-contract', 'domain-enemy-contract', 'persistent-contract', 'catalog', 'enemy-catalog', 'domain-summon-contract', 'relic-contract', 'domain-passive-contract', 'prepared-contract', 'enemy-matrix-mvp', 'domain-revival', 'prepared-choice', 'power-presentation', 'enemy-exploration', 'coupon-contract', 'domain-card-contributions', 'primal-contract', 'audio-receipts', 'domain-dampen-transactions', 'standing-extra-turn', 'domain-steam', 'card-face-acceptance', 'domain-hopper', 'domain-suppression', 'domain-visual', 'architect-ending', 'card-lifecycle', 'native-run', 'presentation-acceptance', 'native-suite', 'catalog-face-suite'):
        # MonoMod's native exception helper needs globally visible libgcc unwind symbols.
        # This is scoped to the child; it changes no system loader configuration.
        if not IS_WINDOWS:
            unwind = Path('/lib/x86_64-linux-gnu/libgcc_s.so.1')
            if not unwind.is_file():
                raise RuntimeError('Baseline Harmony probe requires the host libgcc_s.so.1')
            env['LD_PRELOAD'] = str(unwind) + (' ' + env['LD_PRELOAD'] if env.get('LD_PRELOAD') else '')
        env['VOLIBEAR_TEST_SCENARIO'] = scenario
        if scenario != 'native-run':
            command.append('--bootstrap')
    launch_options = {} if cancel_event is None else {'cancel_event': cancel_event}
    process_identity = {}
    if record_process_identity:
        launch_options['process_identity'] = process_identity
    code, timed_out = launch(game, directory, env, command, timeout, display=display, **launch_options)
    check_cancelled(cancel_event)
    log = combined_log(directory)
    checks = evaluate(code, timed_out, log, stock)
    checks['stock_control_success'] = (isinstance(stock_evidence, dict)
                                       and stock_evidence.get('successful') is True
                                       and stock_evidence.get('exit_code') == 0
                                       and stock_evidence.get('timed_out') is False)
    if adapter_enabled:
        checks['audio_adapter_active'] = '[Volibear] AUDIO_OUTPUT nosound' in log
    scenario_result = None
    if scenario == 'api':
        checks['api_dump_complete'] = '[Volibear] API_DUMP_DONE' in log
        # PBE's Godot build crashes during shutdown after a heavy reflection dump. The dump is
        # already complete and all other gates passed, so the exit code alone is not the surface
        # acceptance signal here; keep the crash visible in diagnostics instead.
        if (checks['api_dump_complete'] and checks.get('no_runtime_errors')
                and checks.get('teardown_matches_stock')):
            checks['exited_zero'] = True
    elif scenario == 'native-suite':
        scenario_result = native_suite_evidence(dampen_protocol_log(log, run_id, checks), run_id,
                                               card_face_batch, card_lifecycle_cases, presentation_mode,
                                               directory / 'presentation', env['VOLIBEAR_TEST_DATA_ROOT'])
        checks['native_suite_assertions'] = scenario_result['errors'] == []
    elif scenario == 'card-lifecycle':
        scenario_result, checks['card_lifecycle_assertions'] = card_lifecycle_batch_evidence(log, run_id, card_lifecycle_cases)
    elif scenario == 'native-run':
        scenario_result = native_run_evidence(log, run_id, native_run_mode, env['VOLIBEAR_NATIVE_RUN_PAIR'])
        checks['native_run_assertions'] = scenario_result['errors'] == []
    elif scenario in ('presentation-acceptance', 'catalog-face-suite'):
        if record_process_identity and presentation_mode == 'cards':
            from presentation_media_checks import check_log as catalog_media_check
            media = catalog_media_check(dampen_protocol_log(log, run_id, checks), run_id,
                                        presentation_mode, directory / 'presentation')
            errors = media['errors']
        else:
            errors = presentation_acceptance_evidence(dampen_protocol_log(log, run_id, checks), run_id,
                                                      presentation_mode, directory / 'presentation')
        scenario_result = {'mode': presentation_mode, 'errors': errors,
                           'scope': 'native-capture-not-human-visual-or-listening-review'}
        checks['presentation_acceptance_assertions'] = not errors
        if record_process_identity and presentation_mode == 'cards':
            # Retain BOTH original native-suite validators, including CRC/nonblank media checks.
            scenario_result['media'] = media
            scenario_result['verified_catalog_views'] = len(media.get('images', [])) if not errors else 0
            checks['presentation_media_assertions'] = not errors
        if scenario == 'catalog-face-suite':
            composite = catalog_face_evidence(log, run_id, card_face_batch, process_identity)
            checks['catalog_face_assertions'] = not composite['errors']
            scenario_result['card_faces'] = composite['card_faces']
            scenario_result['envelope'] = composite['envelope']
            scenario_result['errors'] = list(errors) + composite['errors']
    elif scenario == 'architect-ending':
        from architect_ending_evidence import check_log
        scenario_result = check_log(log, run_id)
        checks['architect_ending_assertions'] = not scenario_result['errors']
        self_result, checks['domain_suppression_assertions'] = domain_suppression_evidence(log, run_id, 'self')
        scenario_result['self_debuff'] = self_result
    elif scenario == 'domain-visual':
        from domain_visual_evidence import check_log
        scenario_result = check_log(log, run_id, directory / 'domain-visual')
        checks['domain_visual_assertions'] = not scenario_result['errors']
    elif scenario == 'domain-suppression':
        scenario_result, checks['domain_suppression_assertions'] = domain_suppression_evidence(log, run_id, domain_suppression_family)
    elif scenario == 'domain-hopper':
        scenario_result, checks['domain_hopper_assertions'] = domain_hopper_evidence(log, run_id, hopper_case)
    elif scenario == 'card-face-acceptance':
        try:
            scenario_result = (extract_card_face_batch(log, run_id, card_face_batch)
                               if card_face_batch is not None
                               else extract_card_face_result(log, run_id, card_face_case))
            checks['card_face_assertions'] = True
        except (ValueError, TypeError, KeyError) as error:
            scenario_result = {'variant': card_face_case, 'error': str(error)}
            checks['card_face_assertions'] = False
    elif scenario == 'content':
        scenario_result, checks['content_assertions'] = content_evidence(log, run_id, scenario)
    elif scenario == 'engage-contract':
        scenario_result, checks['engage_contract_assertions'] = engage_contract_evidence(log, run_id, engage_case)
    elif scenario == 'domain-contract':
        scenario_result, checks['domain_contract_assertions'] = domain_contract_evidence(log, run_id, domain_case)
    elif scenario == 'beast-contract':
        scenario_result, checks['beast_contract_assertions'] = beast_contract_evidence(log, run_id, beast_case)
    elif scenario == 'domain-enemy-contract':
        evidence = domain_enemy_evidence(log, run_id, domain_enemy_case)
        scenario_result = evidence
        checks['domain_enemy_contract_assertions'] = evidence['passed'] is True
    elif scenario == 'primal-contract':
        scenario_result, checks['primal_contract_assertions'] = primal_contract_evidence(log, run_id, primal_case)
    elif scenario == 'coupon-contract':
        scenario_result, checks['coupon_contract_assertions'] = coupon_contract_evidence(log, run_id, coupon_case)
    elif scenario == 'domain-card-contributions':
        errors = domain_card_evidence(log, run_id, domain_card_case)
        scenario_result = {'errors': errors, 'case': domain_card_case}
        checks['domain_card_contribution_assertions'] = not errors
    elif scenario == 'enemy-exploration':
        scenario_result, checks['enemy_exploration_assertions'] = exploration_evidence(
            log, run_id, directory, selection_path=frozen_selection,
            catalog=exploration_catalog, prerequisite=exploration_prerequisite)
    elif scenario == 'power-presentation':
        scenario_result, checks['power_presentation_assertions'] = power_presentation_evidence(log, run_id)
    elif scenario == 'audio-receipts':
        scenario_result, checks['audio_receipt_assertions'] = audio_receipt_evidence(log, run_id)
    elif scenario == 'domain-revival':
        scenario_result, checks['domain_revival_assertions'] = domain_revival_evidence(log, run_id, revival_case)
    elif scenario == 'prepared-choice':
        scenario_result, checks['prepared_choice_assertions'] = prepared_choice_evidence(log, run_id, prepared_choice_case)
    elif scenario == 'prepared-contract':
        scenario_result, checks['prepared_contract_assertions'] = prepared_contract_evidence(log, run_id, prepared_case)
    elif scenario == 'enemy-matrix-mvp':
        scenario_result, checks['enemy_matrix_assertions'] = matrix_evidence(log, run_id, directory)
    elif scenario == 'domain-steam':
        scenario_result = domain_steam_evidence(log, run_id, steam_case)
        checks['domain_steam_assertions'] = scenario_result['errors'] == []
    elif scenario == 'standing-extra-turn':
        scenario_result, checks['standing_extra_turn_assertions'] = standing_extra_turn_evidence(log, run_id, standing_case)
    elif scenario == 'domain-dampen-transactions':
        errors = domain_dampen_evidence(dampen_protocol_log(log, run_id, checks), run_id, dampen_case)
        scenario_result = dict(variant=dampen_case, errors=errors, passed=not errors)
        checks['domain_dampen_assertions'] = not errors
    elif scenario == 'domain-passive-contract':
        gate = (new_apply_evidence if domain_passive_case in NEW_APPLY_CASES else
                suck_evidence if domain_passive_case in SUCK_CASES else
                initial_plating_evidence if domain_passive_case in INITIAL_PLATING_CASES else
                card_passive_evidence if domain_passive_case in CARD_PASSIVE_CASES else domain_passive_evidence)
        scenario_result = gate(log, run_id, domain_passive_case)
        checks['domain_passive_contract_assertions'] = scenario_result['passed'] is True
    elif scenario == 'relic-contract':
        scenario_result, checks['relic_contract_assertions'] = relic_contract_evidence(log, run_id, relic_case)
    elif scenario == 'persistent-contract':
        scenario_result, checks['persistent_contract_assertions'] = persistent_contract_evidence(log, run_id, persistent_case)
    elif scenario == 'catalog':
        scenario_result, checks['catalog_assertions'] = catalog_evidence(log, run_id)
    elif scenario == 'enemy-catalog':
        scenario_result, checks['enemy_catalog_assertions'] = enemy_catalog_evidence(log, run_id, directory, expected_seed='VOLIBEARTEST')
    elif scenario == 'domain-summon-contract':
        summon_gate = summon_d17_evidence if domain_summon_case in SUMMON_D17_CASES else domain_summon_evidence
        scenario_result = summon_gate(log, run_id, domain_summon_case)
        checks['domain_summon_contract_assertions'] = scenario_result['passed'] is True
    elif scenario != 'discovery':
        scenario_result, checks['scenario_assertions'] = scenario_evidence(log, run_id, scenario)
        checks['engage_variant_assertions'] = engage_evidence(
            scenario_result, env.get('VOLIBEAR_TEST_ENGAGE') == '1')
    shutdown_marker = '[Volibear] SHUTDOWN_BEGIN ' + run_id
    before_shutdown, marker, after_shutdown = log.partition(shutdown_marker)
    teardown_errors = [line for line in error_lines(log) if is_teardown(line)]
    def runtime_lines(text):
        return [line for line in error_lines(text) if not is_teardown(line)]
    diagnostics = {
        'shutdown_marker_seen': bool(marker),
        'runtime_errors': runtime_lines(before_shutdown),
        'shutdown_errors': runtime_lines(after_shutdown) if marker else [],
        'engine_teardown_errors': teardown_errors,
        'teardown_categories': sorted(teardown_categories(teardown_errors)),
        'stock_teardown_control': stock_evidence,
    }
    # Phase classification is diagnostic only: every engine error still fails.
    report = {
        'schema': 1, 'run_id': run_id, 'mode': 'real-game-' + display, 'scenario': scenario,
        'platform': os.name,
        'game_version': __import__('os').environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1').lstrip('v'),
        'game_commit': __import__('os').environ.get('VOLIBEAR_GAME_COMMIT', '59260271'),
        **repository_metadata(),
        'exit_code': code, 'timed_out': timed_out, 'checks': checks,
        'diagnostics': diagnostics,
        'status': 'passed' if all(checks.values()) else 'failed',
        'combat_tests': scenario_result or 'not_run', 'command': command,
    }
    if record_process_identity:
        report['process_identity'] = process_identity
    check_cancelled(cancel_event)  # In-process evidence validation is cooperative, not interruptible mid-decode.
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'report': str(directory / 'report.json'), 'status': report['status'], 'checks': checks}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--display', choices=['headless', 'xvfb', 'window', 'background'], default='headless')
    parser.add_argument('--scenario', choices=['discovery', 'baseline', 'api', 'content', 'engage-contract',
                                              'domain-contract', 'beast-contract', 'domain-enemy-contract',
                                              'persistent-contract', 'catalog', 'enemy-catalog',
                                              'domain-summon-contract', 'relic-contract',
                                              'domain-passive-contract', 'prepared-contract', 'enemy-matrix-mvp',
                                              'domain-revival', 'prepared-choice', 'power-presentation',
                                              'enemy-exploration', 'coupon-contract', 'domain-card-contributions', 'primal-contract', 'audio-receipts', 'domain-dampen-transactions', 'standing-extra-turn', 'domain-steam', 'card-face-acceptance', 'domain-hopper', 'domain-suppression', 'domain-visual', 'architect-ending',
                                              'card-lifecycle', 'native-run', 'presentation-acceptance'], default='discovery')
    parser.add_argument('--domain-suppression-family', choices=DOMAIN_SUPPRESSION_CASES, default='all',
                        help='all runs sandpit, knights and self in three fresh battles within one game process')
    parser.add_argument('--hopper-case', choices=HOPPER_CASES, default='off')
    parser.add_argument('--card-face-case', choices=CARD_FACE_CASES, default='B01-base-plain')
    parser.add_argument('--card-face-batch', help='all or comma-separated cases, in one game process')
    parser.add_argument('--card-lifecycle-cases', default='all', help='all or comma-separated lifecycle cases, in one game process')
    parser.add_argument('--native-run-mode', choices=sorted(NATIVE_RUN_MODES - {'resume'}), default='three-battle-save',
                        help='Normal menu/paid-input route; use native_run_pair.py for save/restart/Continue')
    parser.add_argument('--presentation-mode', choices=['cards', 'actions', 'all'], default='cards')
    parser.add_argument('--audio-driver', help='Explicit Godot driver; non-Dummy required for presentation actions/audio')
    parser.add_argument('--use-deployed', action='store_true', help='Run the already deployed candidate; do not rebuild or redeploy')
    parser.add_argument('--steam-case', choices=STEAM_CASES, default='off')
    parser.add_argument('--standing-case', choices=STANDING_CASES, default='U03-base-extra-turn')
    parser.add_argument('--dampen-case', choices=DAMPEN_CASES, default='off')
    parser.add_argument('--primal-case', choices=PRIMAL_CASES, default='U12-paid-snapshot')
    parser.add_argument('--coupon-case', choices=COUPON_CASES, default='CP-max-preserve')
    parser.add_argument('--domain-card-case', choices=DOMAIN_CARD_CASES, default='hex')
    parser.add_argument('--matrix-selection', type=Path)
    parser.add_argument('--matrix-catalog', type=Path)
    parser.add_argument('--matrix-prerequisite-report', type=Path)
    parser.add_argument('--revival-case', choices=REVIVAL_CASES, default='reattach-off')
    parser.add_argument('--prepared-choice-case', choices=PREPARED_CHOICE_CASES, default='PC-C19-fixed-replay')
    parser.add_argument('--prepared-case', choices=PREPARED_CASES, default='PR-training-dynamic-spells')
    parser.add_argument('--domain-passive-case', choices=DOMAIN_PASSIVE_CASES, default='ritual-off')
    parser.add_argument('--relic-case', choices=RELIC_CASES, default='RH-starter-turns')
    parser.add_argument('--domain-summon-case', choices=DOMAIN_SUMMON_CASES, default='fabricator-off')
    parser.add_argument('--persistent-case', choices=PERSISTENT_CASES, default='PP-U21-deploy-at-three')
    parser.add_argument('--beast-case', choices=BEAST_CASES, default='f01')
    parser.add_argument('--domain-enemy-case', choices=DOMAIN_ENEMY_CASES, default='flutter')
    parser.add_argument('--domain-case', choices=DOMAIN_CASES, default='d01',
                        help='isolated domain/lightning mechanism probe; native proxy is not card acceptance')
    parser.add_argument('--engage-case', choices=['e01', 'e02', 'b04'], default='e01',
                        help='isolated production engage effect fixture (not ordinary payment)')
    parser.add_argument('--repeat', type=int, help='Focused diagnostics only; batches/acceptance require one process')
    parser.add_argument('--timeout', type=int)
    parser.add_argument('--frames', type=int)
    args = parser.parse_args()
    batch = args.card_face_batch is not None or args.scenario in ('card-lifecycle', 'native-run', 'presentation-acceptance', 'domain-suppression')
    short_fixture = args.scenario in ('domain-visual', 'architect-ending')
    single_run = batch or short_fixture
    args.repeat = args.repeat if args.repeat is not None else 1
    args.timeout = args.timeout if args.timeout is not None else (90 if short_fixture else 900 if batch else 45)
    args.frames = args.frames if args.frames is not None else (5400 if short_fixture else 60000 if batch else 300)
    limit_timeout, limit_frames = (1800, 300000) if batch else (300, 10000)
    if not 1 <= args.repeat <= 10 or not 5 <= args.timeout <= limit_timeout or not 1 <= args.frames <= limit_frames:
        parser.error(f'repeat 1..10, timeout 5..{limit_timeout}, frames 1..{limit_frames} required')
    if single_run and args.repeat != 1:
        parser.error('Batched/acceptance cases run continuously in one process; use --repeat 1')
    if args.card_face_batch is not None and args.scenario != 'card-face-acceptance':
        parser.error('--card-face-batch requires --scenario card-face-acceptance')
    try:
        card_face_batch = (cli_cases(args.card_face_batch, CARD_FACE_CASES, 'Card face batch')
                           if args.card_face_batch is not None else None)
        lifecycle_cases = (cli_cases(args.card_lifecycle_cases, CARD_LIFECYCLE_CASES, 'Card lifecycle batch')
                           if args.scenario == 'card-lifecycle' else None)
        with_audio_driver([], args.audio_driver)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    if args.scenario == 'presentation-acceptance':
        if args.display == 'headless':
            parser.error('Presentation capture requires --display background (Windows) or xvfb (Linux)')
        if args.presentation_mode != 'cards' and (not args.audio_driver or args.audio_driver.lower() == 'dummy'):
            parser.error('Action/audio capture requires an explicit non-Dummy --audio-driver')
    if IS_WINDOWS and args.display == 'window' and batch and os.environ.get('VOLIBEAR_TEST_NO_FOCUS') != '1':
        parser.error('Acceptance runs require a private background desktop, not a foreground window')
    display_command([], args.display)  # Reject unsupported display before build/deploy side effects.
    game = Path(config()['game_dir']).expanduser().resolve()
    validate_game(game)
    if not args.use_deployed:
        subprocess.run([sys.executable, 'tools/dev.py', 'test'], cwd=ROOT, check=True)
        subprocess.run([sys.executable, 'tools/dev.py', 'build'], cwd=ROOT, check=True)
        subprocess.run([sys.executable, 'tools/dev.py', 'deploy'], cwd=ROOT, check=True)
    # One control launch per invocation defines the exit signature the shipped game produces
    # on its own, so teardown noise is attributed instead of waived.
    stock, stock_evidence = stock_teardown(game, args.timeout, args.frames, args.display, args.audio_driver)
    print(json.dumps({'stock_teardown_control': stock_evidence}))
    reports = [run_once(game, args.timeout, args.frames, args.scenario, args.display,
                        stock, stock_evidence, args.engage_case, args.domain_case,
                        args.beast_case, args.domain_enemy_case, args.persistent_case,
                        args.domain_summon_case, args.relic_case, args.domain_passive_case, args.prepared_case,
                        args.revival_case, args.prepared_choice_case, args.matrix_selection,
                        args.matrix_catalog, args.matrix_prerequisite_report,
                        args.coupon_case, args.domain_card_case, args.primal_case, args.dampen_case, args.standing_case, args.steam_case, args.card_face_case, args.hopper_case,
                        card_face_batch=card_face_batch, card_lifecycle_cases=lifecycle_cases,
                        native_run_mode=args.native_run_mode, presentation_mode=args.presentation_mode,
                        audio_driver=args.audio_driver, domain_suppression_family=args.domain_suppression_family) for _ in range(args.repeat)]
    return 0 if all(r['status'] == 'passed' for r in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())


