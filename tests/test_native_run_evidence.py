"""Synthetic protocol tests only, never normal-game or full-run acceptance evidence."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_run_evidence import PREFIX,SCOPE,POLICY,native_run_evidence,native_run_pair_evidence


def state(**changes):
    value=dict(run=1,combat=0,player=2,room='EventRoom',roomType='Event',floor=0,act=0,actCount=3,
               character='VOLIBEAR_CHARACTER',seed='NATIVE-GENERATED-SEED',shouldSave=True,runActive=True,combatActive=False,
               mapOpen=False,round=None,phase=None,hp=80,maxHp=80,block=0,energy=None,gold=99,
               deck=[dict(id=id,upgrade=0) for id in ['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']],
               relics=['HUNTERS_HEART'],powers=[],hand=[],enemies=[])
    value.update(changes);return value


def fixture(mode='three-battle-save',token='normal-token',pid=100):
    events=[]
    def emit(kind,data):events.append(dict(seq=len(events),kind=kind,data=copy.deepcopy(data)))
    checkpoint=dict(sha256='a'*64,bytes=2000,nativeSave={'schema_version':1,'native':'synthetic-unit-only'})
    boundary=state(room='RestSiteRoom',roomType='RestSite',floor=4,hp=61,gold=130)
    def menu_start(run=1):
        emit('menu',dict(runActive=False,combatActive=False))
        emit('ui',dict(type='NButton',path='/MainMenu/SingleplayerButton',enabled=True,visible=True))
        emit('character-select',dict(id='VOLIBEAR_CHARACTER',locked=False,visible=True,api='NCharacterSelectButton.Select'))
        emit('run-start',state(run=run))
    if mode=='resume':
        emit('checkpoint-before-continue',checkpoint);emit('continued',boundary)
    else:menu_start()
    count=3 if mode in ('three-battle-save','full-run') else 1
    for index in range(count):
        cid=10+index;floor=index+1 if mode!='resume' else 5
        current=state(combat=cid,combatActive=True,floor=floor,room='CombatRoom',roomType='Boss' if mode=='full-run' else 'Monster',
                      act=index if mode=='full-run' else 0,phase='Play',round=1,energy=3,hp=80-index*6)
        emit('map-choice',dict(act=current['act'],fromRow=None if index==0 else index-1,fromCol=None if index==0 else 0,row=index,col=0,type='Monster',legal=[dict(row=index,col=0)]))
        emit('room',current);emit('battle-start',dict(combat=cid,encounter='NATIVE_MONSTER',state=current))
        card=dict(entity=100+index,id='VOLIBEAR_B01',upgrade=0,pile='Hand')
        if mode!='death-menu':
            emit('play-request',dict(combat=cid,card=card,target=500+index,canPlay=True,validTarget=True,cost=1,energy=3))
            emit('paid-action',dict(before=current,after=dict(current,energy=2),combat=cid,card=dict(card,pile='Discard'),costBefore=1,
                                   action='PlayCardAction',actionId=index,state='Finished',exception=None,context='GameActionPlayerChoiceContext',
                                   paymentHooks=[dict(card=100+index,amount=1,energy=2)],historyCapture='action-completion',
                                   plays=[dict(entity=100+index,id='VOLIBEAR_B01',autoPlay=False,spent=1,index=0,count=1)],energyHistory=[1]))
        emit('end-turn',current);emit('turn-start',dict(combat=cid,side='Enemy',round=1))
        final=dict(current,combatActive=False,hp=0 if mode=='death-menu' else current['hp']-6)
        if mode!='death-menu':emit('battle-win',dict(combat=cid,encounter='NATIVE_MONSTER',state=final))
        emit('battle-end',dict(combat=cid,state=final))
        if mode!='death-menu':
            emit('selection-open',dict(type='NRewardsScreen',pendingPaidAction=False,state=final))
            emit('selection-return',dict(type='NRewardsScreen',before=final,after=dict(final,gold=final['gold']+10)))
    if mode=='three-battle-save':
        emit('save-boundary',boundary);emit('checkpoint',checkpoint);emit('saved-menu',dict(runActive=False,combatActive=False));outcome='checkpoint-saved'
    elif mode=='resume':outcome='resumed-one-battle'
    elif mode=='death-menu':
        emit('game-over',dict(victory=False,state=final));menu_start(200);emit('new-run-after-death',state(run=200));outcome='death-menu-restarted'
    else:emit('game-over',dict(victory=True,state=final));outcome='victory'
    return dict(schema=1,token=token,mode=mode,pair='pair-one',processId=pid,scenario='native-run',gameVersion='0.107.1',gameCommit='59260271',
                scope=SCOPE,policy=POLICY,isolatedProfile=True,nativeBootstrap=None,testMode=False,steamInitialized=False,autoSlayerActive=False,
                outcome=outcome,error=None,events=events,elapsedSeconds=10)


def log(row):return PREFIX+json.dumps(row)+'\n[Volibear] SHUTDOWN_BEGIN '+row['token']
def find(row,kind):return next(e['data'] for e in row['events'] if e['kind']==kind)
def resequence(row):
    for index,event in enumerate(row['events']):event['seq']=index


class NativeRunEvidenceTests(unittest.TestCase):
    def errors(self,row):return native_run_evidence(log(row),row['token'],row['mode'],row['pair'])['errors']
    def test_four_distinct_bounded_modes(self):
        for mode in ('three-battle-save','resume','death-menu','full-run'):
            with self.subTest(mode=mode):self.assertEqual(self.errors(fixture(mode)),[])
    def test_real_restart_pair_matches_without_importing_a_save(self):
        a=fixture();b=fixture('resume','resume-token',101)
        self.assertEqual(native_run_pair_evidence(log(a),a['token'],log(b),b['token'],'pair-one')['errors'],[])
    def test_autoplay_cannot_masquerade_as_paid(self):
        row=fixture();find(row,'paid-action')['plays'][0]['autoPlay']=True;self.assertTrue(self.errors(row))
    def test_legality_and_native_choice_context_required(self):
        for target,field,value in [('play-request','canPlay',False),('play-request','validTarget',False),('paid-action','action','AutoPlay'),
                                   ('paid-action','context','ThrowingPlayerChoiceContext'),('paid-action','state','Queued')]:
            row=fixture();find(row,target)[field]=value
            with self.subTest(field=field):self.assertTrue(self.errors(row))
    def test_real_energy_hook_and_history_required(self):
        for field,value in [('paymentHooks',[]),('energyHistory',[]),('historyCapture','runtime-verdict')]:
            row=fixture();find(row,'paid-action')[field]=value;self.assertTrue(self.errors(row))
        row=fixture();find(row,'paid-action')['paymentHooks'][0]['energy']=3;self.assertTrue(self.errors(row))
    def test_native_victory_clear_boundary_supported_without_suppressing_clear(self):
        row=fixture();find(row,'paid-action')['historyCapture']='before-native-victory-history-clear';self.assertEqual(self.errors(row),[])
    def test_three_actual_battles_and_native_end_not_counter_claim(self):
        for kind in ('battle-start','battle-win','battle-end'):
            row=fixture();victim=next(e for e in row['events'] if e['kind']==kind);row['events'].remove(victim);resequence(row)
            with self.subTest(kind=kind):self.assertTrue(self.errors(row))
    def test_disabled_ui_and_debug_map_jump_rejected(self):
        row=fixture();find(row,'ui')['enabled']=False;self.assertTrue(self.errors(row))
        row=fixture();find(row,'map-choice')['col']=99;self.assertTrue(self.errors(row))
    def test_early_death_or_missing_act_is_not_S09(self):
        row=fixture('full-run');row['outcome']='death';find(row,'game-over')['victory']=False;self.assertTrue(self.errors(row))
        row=fixture('full-run');find(row,'battle-win')['state']['roomType']='Monster';self.assertTrue(self.errors(row))
    def test_S05_is_real_death_and_new_identity_not_abandon(self):
        row=fixture('death-menu');find(row,'game-over')['state']['hp']=80;self.assertTrue(self.errors(row))
        row=fixture('death-menu');runs=[e['data'] for e in row['events'] if e['kind']=='run-start'];runs[1]['run']=runs[0]['run'];self.assertTrue(self.errors(row))
    def test_noncombat_checkpoint_and_restart_boundaries(self):
        row=fixture();find(row,'save-boundary')['room']='CombatRoom';self.assertTrue(self.errors(row))
        a=fixture();b=fixture('resume','resume-token',100)
        self.assertTrue(native_run_pair_evidence(log(a),a['token'],log(b),b['token'],'pair-one')['errors'])
        b=fixture('resume','resume-token',101);find(b,'checkpoint-before-continue')['sha256']='b'*64
        self.assertTrue(native_run_pair_evidence(log(a),a['token'],log(b),b['token'],'pair-one')['errors'])
        b=fixture('resume','resume-token',101);find(b,'continued')['gold']+=1
        self.assertTrue(native_run_pair_evidence(log(a),a['token'],log(b),b['token'],'pair-one')['errors'])
    def test_runtime_verdict_pinned_build_and_full_window_errors(self):
        for field,value in [('gameCommit','wrong'),('nativeBootstrap','VolibearBootstrap'),('autoSlayerActive',True),('steamInitialized',True),('passed',True)]:
            row=fixture();row[field]=value
            with self.subTest(field=field):self.assertTrue(self.errors(row))
        row=fixture();self.assertTrue(native_run_evidence(log(row)+'\nUnhandled exception',row['token'])['errors'])
    def test_partial_coverage_does_not_claim_unseen_choices_shop_or_install(self):
        result=native_run_evidence(log(fixture()),'normal-token')
        self.assertNotIn('S02-card-choice',result['observed_coverage'])
        self.assertNotIn('S06-merchant-remove',result['observed_coverage'])
        self.assertIn('S08-clean-install-uninstall',result['not_covered'])
    def test_visible_hand_selection_requires_real_pending_card_action(self):
        row=fixture();row['events'].insert(7,dict(seq=0,kind='hand-choice',data=dict(pendingPaidAction=False,mode='SimpleSelect',card=12,legalVisible=[12])))
        resequence(row);self.assertTrue(self.errors(row))
    def test_duplicate_output_wrong_token_and_malformed_record(self):
        row=fixture();self.assertTrue(native_run_evidence(log(row)+'\n'+log(row),'normal-token')['errors'])
        self.assertTrue(native_run_evidence(log(row),'wrong-token')['errors'])
        row['events'][0]['seq']=True;self.assertTrue(self.errors(row))
        row=fixture();row['mode']=[];self.assertTrue(native_run_evidence(log(row),'normal-token')['errors'])
    def test_source_uses_native_inputs_and_no_world_fixture_or_os_input(self):
        source=(Path(__file__).resolve().parents[1]/'src/Volibear/NativeRunAcceptanceProbe.cs').read_text(encoding='utf-8')
        for forbidden in ('CardCmd.AutoPlay(', 'CreatureCmd.Kill(', 'DamageCmd.', '.OnPlay(', 'CardPileCmd.Add(', 'CardSelectCmd.UseSelector(',
                          'SetCurrentHp(', 'DebugSeedOverride =', 'SetActDebug(', 'ObtainEpochOverride(', 'SetFtuesEnabled(', 'Input.WarpMouse(', 'SendInput(', 'SetForegroundWindow('):
            self.assertNotIn(forbidden,source)
        self.assertIn('new PlayCardAction(card, target)',source)
        self.assertIn('ActionQueueSynchronizer.RequestEnqueue(_play)',source)
        self.assertIn('character.Select()',source)
        self.assertIn('BeforeHistoryClear',source)
        self.assertIn('await SaveAndQuit()',source)
        self.assertIn('GetNode<NConfirmButton>("%SelectModeConfirmButton")',source)
        self.assertIn('ConditionalWeakTable<object, Identity>',source)


if __name__=='__main__':unittest.main()
