"""Aggregate the existing native oracles; this never turns parser tests into game evidence."""
import json

from architect_ending_evidence import check_log as architect_ending_evidence
from domain_suppression_evidence import check_log as domain_suppression_evidence
from card_face_evidence import extract_card_face_batch
from card_lifecycle_evidence import card_lifecycle_batch_evidence
from presentation_media_checks import check_log as presentation_media_report
from native_product_flow_evidence import check_log as product_flow_evidence
from character_integration_evidence import check_log as character_evidence, check_baselib_runtime

BEGIN = '[Volibear] NATIVE_SUITE_BEGIN '
RESULT = '[Volibear] NATIVE_SUITE_RESULT '
STAGES = ['domain-suppression', 'architect-ending', 'card-faces', 'card-lifecycle', 'presentation', 'product-flow', 'save-load-same-process']


def check_log(log, token, faces, lifecycle, presentation_mode, artifact_dir, user_root):
    errors, results = [], {}
    suppression, suppression_passed = domain_suppression_evidence(log, token, 'all')
    results['domain-suppression'] = suppression
    if suppression_passed is not True:
        errors.append('domain-suppression: independent native receipt oracle failed')
    ending = architect_ending_evidence(log, token)
    results['architect-ending'] = ending
    errors.extend('architect-ending: ' + error for error in ending['errors'])
    results['baselib-runtime'] = check_baselib_runtime(log)
    errors.extend('baselib-runtime: ' + error for error in results['baselib-runtime']['errors'])
    try:
        results['card-faces'] = extract_card_face_batch(log, token, faces)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        errors.append('card-faces: ' + str(error))
    result, passed = card_lifecycle_batch_evidence(log, token, lifecycle)
    results['card-lifecycle'] = result
    if passed is not True:
        errors.append('card-lifecycle: independent native receipt oracle failed')
    media = presentation_media_report(log, token, presentation_mode, artifact_dir)
    presentation = media['errors']
    results['presentation'] = {'mode': presentation_mode, 'errors': presentation,
                               'media': media, 'humanReview': 'required'}
    errors.extend('presentation: ' + error for error in presentation)
    try:
        def one(prefix):
            lines = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
            if len(lines) != 1:
                raise ValueError('exactly one ' + prefix.strip() + ' required')
            return json.loads(lines[0])
        begin, final = one(BEGIN), one(RESULT)
        if (type(begin.get('pid')) is not int or begin['pid'] <= 0 or begin.get('token') != token
                or not token or final.get('token') != token or final.get('pid') != begin['pid']):
            raise ValueError('invocation token / native process identity differs')
        expected = dict(schema=2, token=token, pid=begin['pid'], completed=STAGES, finished=True,
                        osInput=False, simulatedClicks=False, processRestarts=0,
                        selector='CardSelectCmd.UseSelector',
                        rewardDecisionBoundary='NCardRewardSelectionScreen.OptionSelected',
                        cleanup=dict(RunNull=True, CombatNull=True, InProgress=False,
                                     QueueEmpty=True, ActionNull=True, HistoryVisible=0),
                        scope='native-paid-card-faces-lifecycle-presentation-product-flow-and-checkpoint',
                        exclusions=['live-multiplayer-peers', 'physical-input',
                                    'human-visual-listening-review', 'disk-process-restart'])
        # bool is an int in Python: compare typed JSON values, not Python dict equality.
        from card_lifecycle_evidence import same
        same(final, expected, 'suite envelope')
        boundaries = [BEGIN, '[Volibear] CHARACTER_INTEGRATION_RESULT ', '[Volibear] CARD_FACE_BATCH_RESULT ',
                      '[Volibear] CARD_LIFECYCLE_BATCH_RESULT ',
                      '[Volibear] PRESENTATION_ACCEPTANCE_RESULT ', '[Volibear] NATIVE_PRODUCT_FLOW_RESULT ',
                      '[Volibear] SAVE_LOAD_RESULT ', RESULT,
                      '[Volibear] SHUTDOWN_BEGIN ' + token]
        positions = [log.index(marker) for marker in boundaries]
        if positions != sorted(positions) or any(log.count(marker) != 1 for marker in boundaries):
            raise ValueError('suite stages or the single shutdown are incomplete/out of order')
        domain_positions = [log.index(line) for line in log.splitlines()
                            if line.startswith('[Volibear] DOMAIN_SUPPRESSION_RESULT ')]
        if (len(domain_positions) != 3 or
                not positions[1] < min(domain_positions) <= max(domain_positions) < positions[2]):
            raise ValueError('domain suppression families must complete before card faces')
        ending_position = log.index('[Volibear] ARCHITECT_ENDING_RESULT ')
        if not max(domain_positions) < ending_position < positions[2]:
            raise ValueError('Architect ending must complete between suppression and card faces')
        if '[Volibear] NATIVE_SUITE_ERROR ' in log:
            raise ValueError('native coordinator reported an error')
        character = character_evidence(log, token, begin['pid'])
        results['character-integration'] = character
        errors.extend('character-integration: ' + error for error in character['errors'])
        flow = product_flow_evidence(log, token, begin['pid'])
        results['product-flow'] = flow
        errors.extend('product-flow: ' + error for error in flow['errors'])
        from pathlib import Path
        import save_load_evidence as save
        checkpoint_path = Path(user_root) / 'default/1/modded/profile1/saves/current_run.save'
        expected_save = dict(token=token,pair=token,phase='same',mode='same-process',caseId='S2',seed='VOLIBEARTEST',
                             pid=begin['pid'],userRoot=str(user_root),checkpointPath=str(checkpoint_path))
        saved, valid = save.parse_log(log,expected_save,errors)
        if valid is not True:
            errors.append('save-load: independent same-process checkpoint oracle failed')
        else:
            resolved = checkpoint_path.resolve(strict=True)
            if resolved != checkpoint_path.absolute() or not resolved.is_relative_to(Path(user_root).resolve(strict=True)):
                raise ValueError('checkpoint escaped the isolated profile')
            if not save.eq(json.loads(resolved.read_text(encoding='utf-8')),saved['afterLoad']):
                raise ValueError('actual checkpoint bytes differ from native afterLoad JSON')
            results['save-load-same-process'] = saved
        results['suite'] = final
    except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
        errors.append('suite: ' + str(error))
    return {'errors': errors, 'stages': results, 'scope': 'single-process-native-receipts-not-full-product-acceptance'}
