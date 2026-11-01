"""Synthetic oracle negatives only; new keeper/ending fixtures are NOT game acceptance."""
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_steam_adversarial_evidence import challenge
from test_domain_steam_evidence import log
from domain_steam_evidence import domain_steam_evidence, KEEPER_VARIANTS, ENDING_VARIANTS, VARIANTS


def application_case(name):
    keeper = name in KEEPER_VARIANTS
    base = (KEEPER_VARIANTS if keeper else ENDING_VARIANTS)[name]
    r = challenge(base)
    r.update(variant=name, fixtureVariant=base)
    r['challengeInstrumentation'] += ';native-primary-keeper' if keeper else ';sole-primary-ending-negative'
    veto = keeper and base.startswith('veto-')
    state = dict(present=keeper, combatId=7 if keeper else None, model='Stabbot' if keeper else None,
                 hp=40 if keeper else None, alive=keeper, primary=keeper, minion=False, osty=False,
                 attached=keeper, listed=keeper, nodePresent=keeper)
    f = dict(kind='native-primary-keeper' if keeper else 'sole-primary-ending-negative', keeperAddCalls=int(keeper),
             keeperAddCompleted=int(keeper), bossCombatId=1, keeperAfterAdd=copy.deepcopy(state),
             keeperBeforeApply=copy.deepcopy(state), keeperAfterApply=copy.deepcopy(state), keeperAfterAction=copy.deepcopy(state),
             applyEvidence=dict(api='PowerCmd.Apply<DomainPower>', nativeIsEndingBefore=not keeper, activePrimaryBefore=int(keeper),
                                returnedPower='DomainPower' if keeper else None, returnedMatchesOwnerPower=keeper,
                                afterAppliedCalls=int(keeper), afterAppliedInstanceMatches=keeper, afterAppliedTaskCompleted=keeper, domainAfter=3 if keeper else 0),
             beforeCleanupInProgress=True, bossCleanupCalls=int(veto), bossCleanupDeaths=int(veto),
             keeperBeforeCleanup=copy.deepcopy(state) if keeper else None, keeperCleanupCalls=int(keeper), keeperDied=int(keeper),
             keeperAfterCleanup=dict(state,hp=0,alive=False,attached=False,listed=False,nodePresent=False) if keeper else None,
             sourceAfterCleanup=None, bossAfterCleanup=None, cleanupTrace=['terminal-death-confirmed'] if veto else [])
    if keeper:
        r.update(explicitWinCheck=True, checkResult=True, victories=1, endings=1, inProgress=False)
        f['sourceAfterCleanup']=dict(copy.deepcopy(r['observation']),retired=True,terminalDeaths=1,terminalDeathConfirmed=True,
                                     terminalStarted=True,unconfirmedDeathHold=False,ownerDeathAttempts=3 if veto else 2)
        f['bossAfterCleanup']=dict(r['final'],bossHp=0,bossAlive=False,attached=False,listed=False,nodePresent=False,
                                   sourcePresent=False,nextMove=None,nativeEventCursor=0,nativeStageId=0)
    else:
        for key in ('afterOpen','challengeState','final'): r[key]['domain']=0
        for key in ('windowAfter','afterChallenge','observation'): r[key]['cancelled']=False
        r['windowAfter']['terminalRequested']=False
    r['applicationFixture']=f
    if not keeper:
        n=r['nativeObservation'];n.update(finalAmbientRegistered=True,stops=[],ambientParameterCalls=[1,3,1])
        end=copy.deepcopy(n);end.update(finalAmbientRegistered=False,stops=[dict(before=True,after=False,nodeStillInRoom=False)],ambientParameterCalls=[1,3,1,2])
        r['soleAudioTail']=dict(scope='sole-native-node-exit-after-action-before-wincheck',nodeId=123,exitNodeId=123,
            treeExited=True,originalAnimationCompleted=True,finalLoopRegistered=False,
            events=['exit-enter','effective-stop-in-exit','exit-body-finished','tree-exited'],worldAtExit=copy.deepcopy(r['final']),nativeAtExit=end)
    if keeper and not base.endswith('-set-hp'):
        # Independent native contract: primary keeper keeps IsEnding false when
        # the external HP write commits, before Domain's hook or a later veto.
        h=r['nativeObservation']['historyEvidence']; gate=h['externalHistoryGates'][0]
        gate['isEnding']=False
        data=dict(type='DamageReceivedEntry',actor='boss',dealer='player',cardSource=None,
                  result=dict(receiver='boss',blocked=0,hp=999999999,overkill=0,killed=True,
                              blockBroken=False,fullyBlocked=False))
        index=h['finalCount']; reference=1+max(x['referenceId'] for x in h['allFinalReferences'])
        h['captured'].append(dict(index=index,referenceId=reference,stageId=gate['stageId'],changeCursor=4,
                                 data=copy.deepcopy(data),finalData=copy.deepcopy(data),sameReferenceAtEnd=True,sameHistoryAtEnd=True))
        h['actualFinal'].append(dict(index=index,data=copy.deepcopy(data)))
        h['allFinalReferences'].append(dict(index=index,referenceId=reference,type='DamageReceivedEntry',sameHistory=True))
        h['externalPlayerToBoss']=[copy.deepcopy(data)];h['finalCount']+=1
    return r


class SteamApplicationPrerequisiteTests(unittest.TestCase):
    def check_row(self, row):
        return domain_steam_evidence(log(row), 'unit-token', row['variant'])['errors']

    def test_all_six_keeper_and_three_separately_named_ending_cases(self):
        for name in list(KEEPER_VARIANTS)+list(ENDING_VARIANTS):
            with self.subTest(name=name): self.assertEqual(self.check_row(application_case(name)), [])
        self.assertEqual(len(VARIANTS - set(KEEPER_VARIANTS) - set(ENDING_VARIANTS)), 29)

    def test_missing_minion_dead_secondary_or_changed_keeper_rejected(self):
        for field,value in [('present',False),('minion',True),('osty',True),('alive',False),('primary',False),
                            ('hp',0),('attached',False),('listed',False),('combatId',1),('model','Osty')]:
            row=application_case('keeper-external-after-damage')
            row['applicationFixture']['keeperBeforeApply'][field]=value
            with self.subTest(field=field): self.assertTrue(self.check_row(row))

    def test_actual_add_apply_afterapplied_and_independent_cleanup_required(self):
        for field,value in [('keeperAddCalls',0),('keeperAddCompleted',0),('keeperCleanupCalls',0),('keeperDied',0),('beforeCleanupInProgress',False)]:
            row=application_case('keeper-external-after-hp');row['applicationFixture'][field]=value
            with self.subTest(field=field):self.assertTrue(self.check_row(row))
        for field,value in [('nativeIsEndingBefore',True),('activePrimaryBefore',0),('returnedPower',None),
                            ('afterAppliedCalls',0),('afterAppliedTaskCompleted',False),('afterAppliedInstanceMatches',False),('domainAfter',0)]:
            row=application_case('keeper-external-set-hp');row['applicationFixture']['applyEvidence'][field]=value
            with self.subTest(field=field): self.assertTrue(self.check_row(row))

    def test_veto_still_retains_original_source_until_separate_native_cleanup(self):
        row=application_case('keeper-veto-after-damage');row['final']['bossHp']=0
        self.assertTrue(self.check_row(row))
        row=application_case('keeper-veto-after-damage');row['applicationFixture']['bossCleanupDeaths']=0
        self.assertTrue(self.check_row(row))
        row=application_case('keeper-veto-after-damage');row['applicationFixture']['sourceAfterCleanup']['retired']=False
        self.assertTrue(self.check_row(row))

    def test_ending_negative_does_not_fake_apply_or_refund_original_failure(self):
        row=application_case('sole-ending-external-after-damage')
        row['applicationFixture']['applyEvidence']['afterAppliedCalls']=1
        self.assertTrue(self.check_row(row))
        row=application_case('sole-ending-external-after-damage');row['windowAfter']['cancelled']=True
        self.assertTrue(self.check_row(row))
        # Historical original name stays strict: Domain=0 must not become a newly passing positive.
        row=challenge('external-after-damage');row['afterOpen']['domain']=0;row['final']['domain']=0
        self.assertTrue(self.check_row(row))

    def test_native_window_history_exceptions_and_event_order_are_not_waived(self):
        for name in ('keeper-external-after-damage','sole-ending-external-after-damage'):
            row=application_case(name);row['foreignObservation']['hookWindows'][0]['deathEntries']=2
            self.assertTrue(self.check_row(row))
            row=application_case(name);row['nativeObservation']['changes'][0]['after']=99
            self.assertTrue(self.check_row(row))
            row=application_case(name);row['nativeObservation']['historyEvidence']['initialReferencesIntact']=False
            self.assertTrue(self.check_row(row))
            row=application_case(name)
            self.assertTrue(domain_steam_evidence(log(row)+'\nUnhandled exception', 'unit-token', name)['errors'])

    def test_keeper_requires_actual_external_history_not_ending_suppression(self):
        for name in KEEPER_VARIANTS:
            if name.endswith('-set-hp'): continue
            row=application_case(name);h=row['nativeObservation']['historyEvidence']
            h['captured'].pop();h['actualFinal'].pop();h['allFinalReferences'].pop();h['finalCount']-=1
            h['externalPlayerToBoss']=[]
            with self.subTest(name=name): self.assertTrue(self.check_row(row))
            row=application_case(name)
            row['nativeObservation']['historyEvidence']['externalHistoryGates'][0]['isEnding']=True
            self.assertTrue(self.check_row(row))

    def test_keeper_external_history_exact_source_result_and_original_cursor(self):
        for name in ('keeper-external-after-hp','keeper-veto-after-damage'):
            for key,value in [('dealer','boss'),('actor','player'),('cardSource','forged')]:
                row=application_case(name);h=row['nativeObservation']['historyEvidence']
                for data in (h['captured'][-1]['data'],h['captured'][-1]['finalData'],h['actualFinal'][-1]['data'],h['externalPlayerToBoss'][0]): data[key]=value
                with self.subTest(name=name,key=key): self.assertTrue(self.check_row(row))
            for key,value in [('hp',999999998),('killed',False),('blocked',1),('overkill',1)]:
                row=application_case(name);h=row['nativeObservation']['historyEvidence']
                for data in (h['captured'][-1]['data'],h['captured'][-1]['finalData'],h['actualFinal'][-1]['data'],h['externalPlayerToBoss'][0]): data['result'][key]=value
                with self.subTest(name=name,result=key): self.assertTrue(self.check_row(row))
        row=application_case('keeper-veto-after-damage')
        row['nativeObservation']['historyEvidence']['captured'][-1]['changeCursor']=5
        self.assertTrue(self.check_row(row)) # Restoration/command completion is too late.
        row=application_case('keeper-external-after-hp');h=row['nativeObservation']['historyEvidence']
        h['captured'][-1]['stageId']=h['externalHistoryGates'][0]['stageId']=3
        self.assertTrue(self.check_row(row))
        row=application_case('keeper-external-after-hp')
        row['nativeObservation']['damage']=[dict(historyAdded=True,result=copy.deepcopy(row['nativeObservation']['historyEvidence']['externalPlayerToBoss'][0]['result']))]
        self.assertTrue(self.check_row(row)) # External history is not Steam boss-dealt damage.

    def test_keeper_external_history_cannot_enable_original_default_path(self):
        from steam_native_protocol import verify_native_protocol
        row=application_case('keeper-external-after-damage');row['variant']=row['fixtureVariant']
        errors=[]
        verify_native_protocol(row,lambda ok,label: errors.append(label) if not ok else None)
        self.assertIn('actual external lethal history absent under native ending branch',errors)
        self.assertIn('observed native lethal-history suppression, not fabricated returned result',errors)

    def test_sole_tail_requires_natural_exit_original_animation_and_loop_stop(self):
        for key,value in [('treeExited',False),('originalAnimationCompleted',False),('finalLoopRegistered',True),('exitNodeId',124)]:
            row=application_case('sole-ending-external-after-hp');row['soleAudioTail'][key]=value
            with self.subTest(key=key): self.assertTrue(self.check_row(row))
        for events in (['effective-stop-in-exit','exit-enter','exit-body-finished','tree-exited'],
                       ['exit-enter','unexpected-stop','exit-body-finished','tree-exited'],
                       ['exit-enter','effective-stop-in-exit','exit-body-finished']):
            row=application_case('sole-ending-external-after-hp');row['soleAudioTail']['events']=events
            self.assertTrue(self.check_row(row))
        row=application_case('sole-ending-external-after-hp');row.pop('soleAudioTail')
        self.assertTrue(self.check_row(row))

    def test_sole_tail_cannot_rewrite_action_end_or_history_prefix(self):
        for field in ('tree','history','hp','event','loop'):
            row=application_case('sole-ending-external-after-damage');tail=row['soleAudioTail']
            if field=='tree': tail['nativeAtExit']['stops'][0]['nodeStillInRoom']=True
            elif field=='history': tail['nativeAtExit']['historyEvidence']['initialReferencesIntact']=False
            elif field=='hp': tail['worldAtExit']['playerHp']+=1
            elif field=='event': tail['nativeAtExit']['changes'].pop()
            else: tail['nativeAtExit']['finalAmbientRegistered']=True
            with self.subTest(field=field): self.assertTrue(self.check_row(row))
        row=application_case('sole-ending-external-after-damage')
        row['nativeObservation']=copy.deepcopy(row['soleAudioTail']['nativeAtExit'])
        self.assertTrue(self.check_row(row)) # Never replace action-end with the later successful state.
        row=application_case('keeper-external-after-hp')
        row['soleAudioTail']=application_case('sole-ending-external-after-hp')['soleAudioTail']
        self.assertTrue(self.check_row(row))

    def test_probe_tail_is_bounded_observation_without_forced_cleanup(self):
        source=(Path(__file__).resolve().parents[1]/'src/Volibear/DomainSteamEruptionProbe.cs').read_text(encoding='utf-8')
        tail=source[source.index('private sealed class SoleAudioTail'):source.index('private static bool _started')]
        self.assertIn('node.TreeExited += OnExited',tail)
        self.assertIn('Task.WhenAll(animation, exited.Task).WaitAsync(TimeSpan.FromSeconds(15))',tail)
        for forbidden in ('StopAmbient(','.StopSfxLoop(','.StopLoop(','RemoveCreatureNode(','CheckWinCondition(','QueueFree('): self.assertNotIn(forbidden,tail)
        self.assertLess(source.index('var nativeObservation = native.Snapshot();'),source.index('await soleTail.Complete('))
        self.assertLess(source.index('await soleTail.Complete('),source.index('native.Dispose();'))
        self.assertLess(source.index('native.Dispose();'),source.index('await CombatManager.Instance.CheckWinCondition()'))

    def test_probe_uses_native_add_and_original_afterapplied_task_without_core_changes(self):
        source=(Path(__file__).resolve().parents[1]/'src/Volibear/DomainSteamEruptionProbe.cs').read_text(encoding='utf-8')
        for name in list(KEEPER_VARIANTS)+list(ENDING_VARIANTS): self.assertIn('"'+name+'"',source)
        self.assertIn('await CreatureCmd.Add<Stabbot>(combat)',source)
        self.assertIn('keeper.IsPrimaryEnemy',source)
        self.assertIn('_afterAppliedTask = __result',source)
        self.assertNotIn('await applied.AfterApplied(',source)
        self.assertIn('await CreatureCmd.Kill(keeper!)',source)
        self.assertLess(source.index('native.Dispose();'),source.index('await CreatureCmd.Kill(keeper!)'))


if __name__ == '__main__': unittest.main()
