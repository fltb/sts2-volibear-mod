"""Synthetic independent evidence-gate tests; never native gameplay acceptance."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'tools/prepared_choice_evidence.py'
PROBE=ROOT/'src/Volibear/PreparedChoiceProbe.cs'
DRIVER=ROOT/'src/Volibear/NativeControlledChoice.cs'
spec=importlib.util.spec_from_file_location('pc_gate',MODULE)
evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)


def specimen(case, medium='LeafSlimeM'):
    search=case=='PC-U39-native-search'; dynamic=case=='PC-C19-dynamic-replay'
    models=['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']
    cards=[dict(cardRef=f'starter-{i}',modelId=m,combatCardIndex=100+i,sameObject=True,ownerId=10,masterIndex=i,masterModelId=m,upgraded=False) for i,m in enumerate(models)]
    roles=[('selected','R07' if search else 'U05' if dynamic else 'B01'),('alternate','R09' if search else 'B01' if dynamic else 'U05')]
    if not search:roles.append(('ineligible','B02'))
    roles.append(('source','U39' if search else 'C19'))
    if not search:roles.append(('replay','U11'))
    for role,code in roles:
        cards.append(dict(cardRef=role,modelId='VOLIBEAR_'+code,combatCardIndex=100+len(cards),sameObject=True,ownerId=10,masterIndex=-1,masterModelId=None,upgraded=False))
    lookup={c['cardRef']:c for c in cards}
    original=[f'starter-{i}' for i in range(10)]
    initial=dict(round=1,turn=1,energy=10,hp=80,block=10 if dynamic else 0,enemyHp=[500]*3,
                 hand=['source'] if search else ['selected','alternate','ineligible','source'],draw=original+(['selected','alternate'] if search else []),
                 discard=[],play=[],exhaust=[],prepared=0,retain=False,enhanced=[],powers=[])
    def identity(ref,pile):
        c=lookup[ref]
        return dict(modelId=c['modelId'],combatCardIndex=c['combatCardIndex'],sameObject=True,ownerId=10,masterIndex=c['masterIndex'],pile=pile)
    pile='Draw' if search else 'Hand'
    available=initial['draw'][:] if search else ['selected','alternate','ineligible']
    excluded=original if search else ['ineligible']
    request=dict(actionId=1,actionState='GatheringPlayerChoice',choiceId=0,source=identity('source','Play'),pile=pile,min=1,max=1,
                 manualConfirmation=False,available=[identity(c,pile) for c in available],eligible=[identity(c,pile) for c in ['selected','alternate']],
                 ineligible=[identity(c,pile) for c in excluded],synced=[])
    waiting=deepcopy(initial);waiting['hand'].remove('source');waiting['play']=['source'];waiting['energy']=9 if search else 10
    if search:waiting.update(block=4,powers=[dict(type='DomainPower',amount=1)])
    def inp(control):return dict(api='Viewport.PushInput',action='ui_select',controlType=control,visible=True,focusMatched=True,pressed=[True,False])
    choice=dict(request=request,uiType='NCombatPileCardSelectScreen' if search else 'NPlayerHand',visible=['selected','alternate'],
                excluded=[dict(cardRef=c,filterAccepted=False,holderCount=0 if search else 1,visibleHolderCount=0) for c in excluded],
                exclusionClaim='native-filter-and-ui-exclusion-not-illegal-card-submit',beforeWrongId=deepcopy(waiting),afterWrongId=deepcopy(waiting),
                rejected=dict(kind='unreserved-future-choice-id-not-card-eligibility',requested=0,attempted=1,exception='InvalidOperationException',
                              syncBefore=0,syncAfter=0,counterBefore=1,counterAfter=1,actionState='GatheringPlayerChoice'),
                wrongBoundary=dict(historyBefore=8,historyAfter=8,paymentsBefore=1,paymentsAfter=1,effectsBefore=1,effectsAfter=1,playedBefore=0,playedAfter=0),
                inputs=[inp('NGridCardHolder')] if search else [inp('NHandCardHolder'),dict(api='Viewport.PushInput',action='viewport-left-pointer-confirm',
                    controlType='NConfirmButton',insideTree=True,visible=True,enabled=True,stableFrames=3,hoverMatched=True,nativeFocused=True,
                    focusModeBefore='None',focusModeAfter='None',position=[1800.0,950.0],viewportSize=[1920.0,1080.0],pressed=[True,False])],
                sync=[dict(choiceId=0,actionId=1,actionState='GatheringPlayerChoice',selected=[identity('selected',pile)],selectedSameObjects=[True])])
    r=dict(token='run-token',variant=case,scenario='prepared-choice',completed=True,gameVersion='v0.107.1',gameCommit='59260271',testMode=False,
           acceptance=evidence.ACCEPTANCE,character='VolibearCharacter',playerId=10,enemyIds=[11,12,13],enemyTypes=['LeafSlimeS','TwigSlimeS',medium],
           cards=cards,initial=initial,choice=choice,steps=[],returned=None,played=[],payments=[],beforeEffects=[],requestCount=1)
    def step(role,cost,before,after,count=1,damage=0,prepared=0):
        i=len(r['steps'])+1;energy=after['energy']
        action=dict(id=i,state='Finished',target=11 if role=='selected' else None,type='PlayCardAction',context='GameActionPlayerChoiceContext',
                    actionType='CombatPlayPhaseOnly',sameCard=True,events=[dict(name='before-executed',state='Executing',id=i,energy=before['energy']),
                                                                      dict(name='after-finished',state='Finished',id=i,energy=energy)])
        r['steps'].append(dict(cardRef=role,before=deepcopy(before),after=deepcopy(after),action=action,
                               plays=[dict(cardRef=role,index=j,count=count) for j in range(count)],draws=[],moves=[],
                               damage=[dict(target=11,cardRef=role,hpLost=damage,blocked=0,props=8) for _ in range(count)] if damage else []))
        r['payments'].append(dict(cardRef=role,amount=cost,energy=energy))
        for j in range(count):
            r['beforeEffects'].append(dict(cardRef=role,index=j,count=count,playId=100+i,autoPlay=False,energy=energy,spent=cost,
                                           prepared=prepared,retain=role=='selected',replay=0))
    after=deepcopy(waiting);after['play']=[];after['discard']=['source']
    if search:
        after['draw'].remove('selected');after['hand'].append('selected');step('source',1,initial,after)
        return r
    after.update(prepared=3,retain=True,enhanced=[dict(cardRef='selected',prepared=3,retain=True)])
    step('source',0,initial,after)
    before=deepcopy(after);before['hand'].append('replay')
    after=deepcopy(before);after['hand'].remove('replay');after['discard'].append('replay');after.update(energy=9,powers=[dict(type='NextAttackReplayPower',amount=1)])
    step('replay',1,before,after)
    before=deepcopy(after);after=deepcopy(before);after['hand'].remove('selected');after['discard'].append('selected')
    after.update(energy=8,enemyHp=[480 if dynamic else 482,500,500],prepared=0,powers=[],enhanced=[dict(cardRef='selected',prepared=0,retain=True)])
    step('selected',1,before,after,2,10 if dynamic else 9,3)
    r['played'].append(dict(cardRef='selected',prepared=3,retain=True,enemyHp=after['enemyHp'][:]))
    before=deepcopy(after);after=deepcopy(before);after['discard'].remove('selected');after['hand'].append('selected')
    r['returned']=dict(operation='CardPileCmd.Add-same-instance-fixture-return',before=before,after=deepcopy(after),cardRef='selected')
    before=deepcopy(after);after=deepcopy(before);after['hand'].remove('selected');after['discard'].append('selected');after.update(energy=7,enemyHp=[470 if dynamic else 476,500,500])
    step('selected',1,before,after,1,10 if dynamic else 6,0)
    r['played'].append(dict(cardRef='selected',prepared=0,retain=True,enemyHp=after['enemyHp'][:]))
    return r


class ChoiceEvidenceTests(unittest.TestCase):
    def reject(self,case,mutations):
        for index,mutate in enumerate(mutations):
            r=specimen(case);mutate(r)
            with self.subTest(case=case,mutation=index):self.assertFalse(evidence.validate_prepared_choice_result(r,'run-token',case))

    def test_three_synthetic_cases_both_native_medium_variants(self):
        for medium in ['LeafSlimeM','TwigSlimeM']:
            for case in evidence.PREPARED_CHOICE_CASES:
                with self.subTest(case=case,medium=medium):self.assertTrue(evidence.validate_prepared_choice_result(specimen(case,medium),'run-token',case))

    def test_real_request_ui_and_same_object_sync_cannot_be_omitted_or_relabelled(self):
        self.reject('PC-C19-fixed-replay',[
            lambda r:r.update(requestCount=0),lambda r:r['choice']['request'].update(actionState='Executing'),
            lambda r:r['choice']['request']['eligible'].pop(),lambda r:r['choice']['request']['source'].update(pile='Hand'),
            lambda r:r['choice'].update(uiType='TestCardSelector'),lambda r:r['choice']['visible'].append('ineligible'),
            lambda r:r['choice']['excluded'][0].update(filterAccepted=True),lambda r:r['choice']['excluded'][0].update(visibleHolderCount=1),
            lambda r:r['choice']['sync'][0].update(selectedSameObjects=[False]),lambda r:r['choice']['sync'][0].update(choiceId=1),
            lambda r:r['choice']['sync'][0]['selected'][0].update(combatCardIndex=111),
            lambda r:r['choice']['inputs'][0].update(api='Control._GuiInput'),lambda r:r['choice']['inputs'][1].update(focusMatched=False),
            lambda r:r['choice']['inputs'][0].update(pressed=[True]),lambda r:r.update(acceptance='ordinary-mouse-accepted')])

    def test_confirm_requires_native_viewport_hit_test_without_focus_override(self):
        self.reject('PC-C19-fixed-replay',[
            lambda r:r['choice']['inputs'][1].update(hoverMatched=False),
            lambda r:r['choice']['inputs'][1].update(nativeFocused=False),
            lambda r:r['choice']['inputs'][1].update(insideTree=False),
            lambda r:r['choice']['inputs'][1].update(enabled=False),
            lambda r:r['choice']['inputs'][1].update(visible=False),
            lambda r:r['choice']['inputs'][1].update(stableFrames=2),
            lambda r:r['choice']['inputs'][1].update(focusModeAfter='All'),
            lambda r:r['choice']['inputs'][1].update(position=[2000,950]),
            lambda r:r['choice']['inputs'][1].update(viewportSize=[float('inf'),1080]),
            lambda r:r['choice']['inputs'].__setitem__(1,dict(api='Viewport.PushInput',action='ui_select',controlType='NConfirmButton',visible=True,focusMatched=True,pressed=[True,False]))])
        driver=DRIVER.read_text(encoding='utf-8')
        for expected in ['viewport.GuiGetHoveredControl()', 'ReferenceEquals(hovered,confirm)', 'stableFrames < 3',
                         'new InputEventMouseMotion', 'new InputEventMouseButton', 'confirm.IsInsideTree()', 'confirm.IsEnabled']:
            self.assertIn(expected,driver)
        for forbidden in ['.FocusMode =', 'SetFocusMode(', 'SetIsGameFocused', 'GuiReleaseFocus(', 'NotifyMouseEntered(', '.GuiEmbedSubwindows =']:
            self.assertNotIn(forbidden,driver)

    def test_pointer_diagnostic_is_read_only_and_does_not_create_acceptance(self):
        source=DRIVER.read_text(encoding='utf-8')
        diagnostic=source.split('private static void PointerDiagnostics(',1)[1].split('internal static async Task ConfirmIfRequired(',1)[0]
        for text in ['PREPARED_CHOICE_POINTER_DIAGNOSTIC', 'viewport.GuiGetHoveredControl()', 'control.GetPath()', 'control.MouseFilter',
                     'control.GetGlobalRect()', 'control.GetScreenTransform()', 'nativeFocused', 'NativeField("_isHovered")',
                     'NativeField("_isControllerFocused")', 'root.GuiEmbedSubwindows', 'DisplayServer.MouseGetPosition()',
                     'DisplayServer.WindowIsFocused(window.GetWindowId())', 'gameFocused = MegaCrit.Sts2.Core.Nodes.NGame.IsGameFocusedWindow()']:
            self.assertIn(text,diagnostic)
        for text in ['PushInput(', 'GrabFocus(', 'SetValue(', '.Set(', '.Call(', 'NotifyMouseEntered(', 'WarpMouse(',
                     'WindowMoveToForeground(', 'SetInputAsHandled(', '.Patch(', 'PREPARED_CHOICE_RESULT', 'SetResult(']:
            self.assertNotIn(text,diagnostic)
        for text in ['NotifyMouseEntered(', '.GuiEmbedSubwindows =', 'WindowMoveToForeground(', 'WarpMouse(']:
            self.assertNotIn(text,source)
        self.assertIn('if (!hoverMatched || !nativeFocused || !confirm.IsInsideTree()',source)
        self.assertIn('if (!ReferenceEquals(viewport.GuiGetFocusOwner(), control)) throw',source)

    def test_wrong_future_id_throw_requires_unchanged_counter_piles_power_and_energy(self):
        self.reject('PC-U39-native-search',[
            lambda r:r['choice']['rejected'].update(exception=None),lambda r:r['choice']['rejected'].update(syncAfter=1),
            lambda r:r['choice']['rejected'].update(counterAfter=2),lambda r:r['choice']['rejected'].update(attempted=0),
            lambda r:r['choice']['afterWrongId'].update(energy=8),lambda r:r['choice']['afterWrongId']['draw'].pop(),
            lambda r:r['choice']['afterWrongId']['powers'].clear(),lambda r:r['choice']['rejected'].update(actionState='Finished'),
            lambda r:r['choice'].update(exclusionClaim='native-invalid-card-submission-rejected'),
            lambda r:r['choice']['wrongBoundary'].update(historyAfter=9),lambda r:r['choice']['wrongBoundary'].update(paymentsAfter=2),
            lambda r:r['choice']['wrongBoundary'].update(effectsAfter=2),lambda r:r['choice']['wrongBoundary'].update(playedAfter=1)])

    def test_c19_fixed_bonus_spans_entire_replay_then_expires_but_retain_stays(self):
        self.reject('PC-C19-fixed-replay',[
            lambda r:r['steps'][2]['damage'][1].update(hpLost=6),lambda r:r['beforeEffects'][3].update(prepared=0),
            lambda r:r['steps'][2]['after'].update(prepared=3),lambda r:r['steps'][2]['after'].update(retain=False),
            lambda r:r['steps'][3]['damage'][0].update(hpLost=9),lambda r:r['played'][0].update(enemyHp=[491,500,500]),
            lambda r:r['steps'][0]['after']['enhanced'].append(dict(cardRef='alternate',prepared=3,retain=True)),
            lambda r:r['beforeEffects'][3].update(playId=999),lambda r:r['beforeEffects'][4].update(playId=103),
            lambda r:r['payments'].append(deepcopy(r['payments'][2])),lambda r:r['beforeEffects'][2].update(autoPlay=True),
            lambda r:r['steps'][2]['action'].update(sameCard=False),lambda r:r['returned']['after']['hand'].append('source')])

    def test_c19_cannot_buff_dynamic_damage_or_lose_native_payment(self):
        self.reject('PC-C19-dynamic-replay',[
            lambda r:r['steps'][2]['damage'][0].update(hpLost=13),lambda r:r['steps'][2]['damage'][1].update(hpLost=13),
            lambda r:r['steps'][3]['damage'][0].update(hpLost=13),lambda r:r['steps'][3]['before'].update(block=0),
            lambda r:r['payments'][0].update(amount=1),lambda r:r['beforeEffects'][2].update(spent=0),
            lambda r:r['steps'][2]['action'].update(context='ThrowingPlayerChoiceContext'),
            lambda r:r['steps'][2]['plays'][1].update(index=0)])

    def test_u39_uses_actual_search_not_draw_clone_or_unfiltered_skill(self):
        self.reject('PC-U39-native-search',[
            lambda r:r['steps'][0]['after']['draw'].append('selected'),lambda r:r['steps'][0]['after']['hand'].clear(),
            lambda r:r['steps'][0]['draws'].append('selected'),lambda r:r['steps'][0]['after'].update(block=7),
            lambda r:r['steps'][0]['after']['powers'][0].update(amount=2),lambda r:r['choice']['excluded'].pop(),
            lambda r:r['choice']['request']['eligible'][0].update(modelId='VOLIBEAR_B02'),
            lambda r:r['cards'][10].update(masterIndex=1),lambda r:r['cards'][10].update(sameObject=False),
            lambda r:r['cards'][10].update(combatCardIndex=100),lambda r:r['steps'][0]['after']['draw'].reverse()])

    def test_provenance_schema_and_log_uniqueness(self):
        case='PC-C19-fixed-replay'
        self.reject(case,[lambda r:r.update(token='old'),lambda r:r.update(passed=True),lambda r:r.update(testMode=True),
                          lambda r:r.update(completed=False),lambda r:r['cards'][0].update(ownerId=99),lambda r:r['cards'][0].update(masterModelId=None),
                          lambda r:r['payments'][1].update(amount=True)])
        line=evidence.PREFIX+json.dumps(specimen(case))
        self.assertTrue(evidence.prepared_choice_evidence(line,'run-token',case)[1])
        for log in ['',line+'\n'+line,evidence.PREFIX+'{']:
            self.assertFalse(evidence.prepared_choice_evidence(log,'run-token',case)[1])
        self.assertFalse(evidence.validate_prepared_choice_result({},'run-token','PC-unsupported'))

    def test_probe_routes_real_choice_input_and_never_injects_prepared_or_selector(self):
        source=PROBE.read_text(encoding='utf-8');driver=DRIVER.read_text(encoding='utf-8')
        for text in ['new PlayCardAction(card,target)','ActionQueueSynchronizer.RequestEnqueue(action)','await action.CompletionTask',
                     'choiceEvidence = new','beforeWrongId = Snapshot()','afterWrongId = Snapshot()',
                     'CardModifier.Modifiers(card)','selected.Played +=','CardPlayStartedEntry','DamageReceivedEntry','CardDrawnEntry']:
            self.assertIn(text,source)
        for text in ['UseSelector(', 'PushSelector(', '.TrySetResult(', '.SetResult(', '.EmitSignal(', 'PreparedAttackBonus.Prepare(',
                     'CardModifier.AddModifier', 'CardCmd.AutoPlay(', 'WaitForRemoteChoice(', 'SetMoveImmediate(']:
            self.assertNotIn(text,source+driver)
        self.assertIn('viewport.PushInput(new InputEventAction',driver)
        self.assertIn('GameActionState.GatheringPlayerChoice',driver)
        self.assertIn('await original;',source)


if __name__=='__main__':unittest.main()
