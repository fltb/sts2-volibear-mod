"""Offline oracle/negative-control tests. These fixtures are NOT native evidence."""
from copy import deepcopy
import json
from pathlib import Path
import re
import unittest
from tools import card_face_evidence as gate


def synthetic(variant):
    c,face,b=variant.split('-',2)
    originals=[f'starter-{i}' for i in range(10)]
    models=['B01']*4+['B02']*4+['B03','B04']
    cards=[dict(cardRef=ref,modelId='VOLIBEAR_'+models[i],upgraded=False,combatCardIndex=i,sameObject=True,
                ownerId=0,masterIndex=i,masterModelId='VOLIBEAR_'+models[i]) for i,ref in enumerate(originals)]
    extra={'source':c}
    if b in ('converted','master'):extra['source-material']='B01' if c=='T01' else 'B02'
    if b=='master':
        index=0 if c=='T01' else 4
        material=cards[index];old=material['cardRef'];material['cardRef']='source-material';material['upgraded']=face=='upgrade'
        originals=['source-material' if ref==old else ref for ref in originals];extra.pop('source-material')
    if b=='second-instance':extra['response-card']='C02' if c=='U02' else 'R23' if c=='U21' else 'C24'
    if b=='material': extra.update(material='B01',alternate='B02')
    extra.update({ref:model for ref,model,pile in gate.selection_fixture(c,b)})
    material_rows=gate.beast_materials(c,face=='upgrade',b)
    extra.update({ref+'-beast':'T01' if model=='B01' else 'T02' for ref,model,pile in material_rows})
    if c=='R09':extra.update({'generated-0':'SLIMED','generated-1':'SLIMED'})
    for ref,model in extra.items():
        cards.append(dict(cardRef=ref,modelId=model if model in ('SLIMED','INJURY') else 'VOLIBEAR_'+model,
                          upgraded=ref in ('source','source-material') and face=='upgrade',combatCardIndex=len(cards),sameObject=True,
                          ownerId=0,masterIndex=-1,masterModelId=None))
    e=gate.expected_observations(variant,originals);aid=7;lookup={x['cardRef']:x for x in cards}
    source=lookup['source']
    identity=dict(indexBefore=source['combatCardIndex'],masterIndexBefore=source['masterIndex'],sameMaster=True,
                  masterUpgradedBefore=None,masterUpgradedAfter=None)
    pairs=([('source-material','source')] if b in ('converted','master') else [])+[(ref,ref+'-beast') for ref,model,pile in material_rows]
    conversions=[]
    for material_ref,beast_ref in pairs:
        upgraded=False if b=='master' and material_ref=='source-material' else None
        conversions.append(dict(materialRef=material_ref,cardRef=beast_ref,materialIndex=lookup[material_ref]['combatCardIndex'],
            cardIndex=lookup[beast_ref]['combatCardIndex'],sameObject=False,masterUnchanged=True,
            materialMasterUpgradedBefore=upgraded,materialMasterUpgradedAfter=upgraded,
            pileBefore='Hand',pileAfter='Hand',originalExhausted=True))
    generated=([dict(cardRef=f'generated-{i}',creatorId=None) for i in range(2)] if c=='R09' else
               [dict(cardRef=ref+'-beast',creatorId=0) for ref,model,pile in material_rows])
    destination=[dict(cardRef=f'starter-{i}',type='Volibear_'+model) for i,model in enumerate(models)]
    starter_setup=dict(moved=deepcopy(destination[5:]),destination=destination,movedCount=5,target='Draw',position='Bottom',skipVisuals=False)
    result=dict(starterSetup=starter_setup,schema=2,token='unit-fixture-not-native',variant=variant,scenario='card-face-acceptance',acceptance=gate.ACCEPTANCE,
                version='v0.107.1',commit='59260271',testMode=False,character='VolibearCharacter',enemyTypes=['LeafSlimeS','TwigSlimeS','LeafSlimeM'],
                playerId=0,enemyIds=[1,2,3],enemyOrder=[0,1,2],cards=cards,sourceIdentity=identity,starterDrawOrder=originals,
                response=None,before=e['before'],after=e['after'],choice=None,selections=[],conversions=conversions,
                action=dict(id=aid,state='Finished',type='PlayCardAction',context='GameActionPlayerChoiceContext',actionType='CombatPlayPhaseOnly',
                            target=1 if c in gate.TARGETED else None,sameCard=True,events=[
                                dict(name='before-executed',state='Executing',id=aid,energy=e['before']['energy']),
                                dict(name='after-finished',state='Finished',id=aid,energy=e['after']['energy'])]),
                payments=[dict(cardRef='source',amount=e['cost'],energy=e['paidEnergy'])],
                effects=[dict(cardRef='source',index=i,count=e['playCount'],autoPlay=False,energy=e['paidEnergy'],spent=e['cost']) for i in range(e['playCount'])],
                batches=e['batches'],history=dict(plays=[dict(cardRef='source',index=i,count=e['playCount']) for i in range(e['playCount'])],
                    draws=e['draws'],sequence=sum(e['sequenceGroups'],[]),moves=['TACKLE_MOVE','TACKLE_MOVE','STICKY_SHOT'] if c=='R09' else ['TACKLE_MOVE'] if c in gate.ENGAGE_CARDS else [],
                    generated=generated,damage=e['damage']))
    if b=='second-instance' or c=='U42' and b in ('status','curse'):
        follow=gate.expected_response(c,face=='upgrade',e['after']);fid=8;ref='selected-beast' if c=='U42' else 'response-card'
        result['response']=dict(before=follow['before'],after=follow['after'],batches=follow['batches'],history=follow['history'],
            payments=[dict(cardRef=ref,amount=follow['cost'],energy=follow['paidEnergy'])],
            effects=[dict(cardRef=ref,index=0,count=1,autoPlay=False,energy=follow['paidEnergy'],spent=follow['cost'])],
            action=dict(id=fid,state='Finished',type='PlayCardAction',context='GameActionPlayerChoiceContext',actionType='CombatPlayPhaseOnly',target=1 if c in ('U02','U21') else None,sameCard=True,
                        events=[dict(name='before-executed',state='Executing',id=fid,energy=follow['before']['energy']),dict(name='after-finished',state='Finished',id=fid,energy=follow['after']['energy'])]))
    def selection(pending,minimum,maximum,allowed,selected):
        return dict(api='CardSelectCmd.UseSelector',pending=pending,actionId=aid,min=minimum,max=maximum,
                    options=allowed,selected=selected,sameObjects=[True]*len(selected))
    if b=='material':
        pending=deepcopy(e['before']);pending['energy']=e['paidEnergy'];pending['hand'].remove('source');pending['play']=['source']
        result['choice']=selection(pending,1,1,['material','alternate'],['material'])
    for i,pending in enumerate(e['selectionPending']):
        pile,minimum,maximum,selected=gate.selection_plan(c,face=='upgrade',i,b)
        available=pending[pile.lower()]
        if c=='U17':available=available[:maximum];selected=[] if b=='zero' else available[:2]
        def eligible(ref):
            model=lookup[ref]['modelId']
            if c in ('C07','C19','U41'):return model in ('VOLIBEAR_B01','VOLIBEAR_B03','VOLIBEAR_B04')
            if c=='U39':return ref in ('selected','alternate')
            if c=='R25':return model=='VOLIBEAR_B02'
            return True
        allowed=[ref for ref in available if eligible(ref)]
        if pile=='Draw' and c!='U17':allowed.sort(key=lambda ref:lookup[ref]['modelId'])
        result['selections'].append(selection(pending,minimum,maximum,allowed,selected))
    return result


class CardFaceEvidenceTests(unittest.TestCase):
    def test_starter_setup_schema_identity_types_and_order_are_strict(self):
        mutations = [
            lambda r: r.pop('starterSetup'),
            lambda r: r.update(unapproved=True),
            lambda r: r['starterSetup'].update(extra=True),
            lambda r: r['starterSetup'].update(movedCount=4),
            lambda r: r['starterSetup'].update(movedCount=5.0),
            lambda r: r['starterSetup'].update(target='Hand'),
            lambda r: r['starterSetup'].update(position='Top'),
            lambda r: r['starterSetup'].update(skipVisuals=True),
            lambda r: r['starterSetup']['moved'].pop(),
            lambda r: r['starterSetup']['destination'].pop(),
            lambda r: r['starterSetup']['destination'][0].update(cardRef='source'),
            lambda r: r['starterSetup']['destination'][0].update(extra=True),
            lambda r: r['starterSetup']['moved'].reverse(),
            lambda r: r['starterSetup']['destination'].reverse(),
            lambda r: r['starterSetup']['destination'][0].update(type='Volibear_B04'),
            lambda r: r['starterSetup']['destination'].__setitem__(slice(0,2), r['starterSetup']['destination'][0:2][::-1]),
        ]
        for variant in ('B02-upgrade-frail', 'T01-base-master'):
            for index, mutate in enumerate(mutations):
                with self.subTest(variant=variant, mutation=index):
                    row=synthetic(variant);mutate(row)
                    with self.assertRaises((ValueError,KeyError)):
                        gate._validate(row,row['token'],variant)

    def test_random_intents_are_fixed_with_real_native_moves(self):
        source = (Path(__file__).resolve().parents[1] / 'src/Volibear/CardFaceAcceptanceProbe.cs').read_text()
        self.assertIn('leafMonster.SetMoveImmediate(tackle, forceTransition: true)', source)
        self.assertIn('monster.SetMoveImmediate(move, forceTransition: true)', source)
        self.assertIn('monster.IntendsToAttack != (i < 2)', source)
        self.assertIn('id == "R09" ? 180 : 30', source)
        self.assertIn('await action.CompletionTask', source)
        self.assertNotIn('Expected native LeafSlimeS first TACKLE_MOVE', source)

    def valid(self,r): return gate.validate_card_face_result(r,'unit-fixture-not-native',r['variant'])

    def test_all_explicit_oracle_examples_are_well_formed(self):
        for case in gate.CARD_FACE_CASES:
            with self.subTest(case=case): self.assertTrue(self.valid(synthetic(case)))

    def test_draw_search_options_use_stable_model_order_not_draw_order(self):
        # Independent explicit native presentation order; physical pile remains
        # starter-0..9 followed by the injected candidates.
        for face in ('base','upgrade'):
            for card,expected in (
                ('C07',['starter-0','starter-1','starter-2','starter-3','selected','alternate','starter-8','starter-9']),
                ('U43',['starter-0','starter-1','starter-2','starter-3','selected','starter-4','starter-5','starter-6','starter-7','third','starter-8','starter-9']),
            ):
                r=synthetic(f'{card}-{face}-plain')
                self.assertEqual(r['selections'][0]['options'],expected)
                self.assertTrue(self.valid(r))
                # Do not accept permutations, duplicates, omitted identities,
                # a reordered physical pile, or a different selected object.
                for mutation in ('physical','tie','duplicate','missing','pending','selected'):
                    bad=deepcopy(r);s=bad['selections'][0]
                    if mutation=='physical':s['options']=sorted(expected,key=s['pending']['draw'].index)
                    elif mutation=='tie':s['options'][0],s['options'][1]=s['options'][1],s['options'][0]
                    elif mutation=='duplicate':s['options'][1]=s['options'][0]
                    elif mutation=='missing':s['options'].pop()
                    elif mutation=='pending':s['pending']['draw'].reverse()
                    else:s['selected']=['starter-0']
                    with self.subTest(card=card,face=face,mutation=mutation):self.assertFalse(self.valid(bad))
                if card=='U43':
                    self.assertEqual(r['selections'][1]['options'],['alternate','selected'])
                    bad=deepcopy(r);bad['selections'][1]['options'].reverse()
                    self.assertFalse(self.valid(bad))

    def test_release_denominator_matches_reference(self):
        text=Path(gate.REFERENCE).read_text(encoding='utf-8')
        ids=re.findall(r'^\| ([BCURT]\d\d) \|',text,re.M)
        self.assertEqual(tuple(ids),gate.ALL_IDS)
        self.assertEqual(len(gate.ALL_FACES),178)
        coverage=gate.release_coverage([])
        self.assertEqual(coverage['executed_faces'],0)
        self.assertEqual(len(coverage['missing_faces']),178)
        self.assertFalse(coverage['release_pass'])
        self.assertEqual(set(coverage['section7_unclosed']),set(gate.ALL_IDS))

    def test_probe_and_oracle_finite_card_lists_match(self):
        text=Path('src/Volibear/CardFaceAcceptanceProbe.cs').read_text(encoding='utf-8')
        ids=re.search(r'Implemented = "([^"]+)"',text).group(1).split()
        self.assertEqual(set(ids),set(gate.IMPLEMENTED_IDS))
        self.assertEqual(set(gate.ROWS),set(ids))
        self.assertNotIn('CardCmd.AutoPlay',text)
        self.assertIn('new PlayCardAction(source,target)',text)
        self.assertIn('ActionQueueSynchronizer.RequestEnqueue(action)',text)
        self.assertIn('new NativeAutomationSelector',text)
        self.assertNotIn('NativeControlledChoice',text)
        self.assertNotIn('PushInput',text)
        self.assertNotIn('CanonicalVars',text)
        self.assertNotIn('passed = true',text)

    def test_independent_reference_spot_values(self):
        expected=gate.expected_observations('B03-upgrade-plain',[str(i) for i in range(10)])
        self.assertEqual(expected['after']['enemyHp'],[484,495,495])
        self.assertEqual([d['props'] for d in expected['damage']],[8,4,4,4])
        self.assertEqual(gate.expected_observations('R17-upgrade-x0',[])['after']['enemyHp'],[493,500,500])
        self.assertEqual(gate.expected_observations('R17-upgrade-x3',[])['after']['enemyHp'],[460,500,500])
        self.assertEqual(gate.expected_observations('U40-base-prior1',[])['after']['energy'],9)
        self.assertEqual(gate.expected_observations('U40-base-prior2',[])['after']['energy'],11)
        self.assertEqual(gate.expected_observations('R05-upgrade-plain',[])['after']['block'],30)
        self.assertEqual(gate.expected_observations('C12-upgrade-negative-strength',[])['after']['block'],13)

    def test_mutated_payment_hp_block_piles_powers_rejected_for_every_case(self):
        for case in gate.CARD_FACE_CASES:
            for field in ('energy','hp','block','lightningCount'):
                r=synthetic(case);r['after'][field]+=1
                with self.subTest(case=case,field=field): self.assertFalse(self.valid(r))
            r=synthetic(case);r['payments'][0]['amount']+=1;self.assertFalse(self.valid(r))
            r=synthetic(case);r['after']['powers']['FakePower']=1;self.assertFalse(self.valid(r))
            r=synthetic(case);r['after']['discard'].append('source');self.assertFalse(self.valid(r))
            r=synthetic(case);r['cards'][-1]['sameObject']=False;self.assertFalse(self.valid(r))

    def test_missing_receipts_autoplay_and_fake_pass_rejected(self):
        for field in ('payments','effects','history','action','cards'):
            r=synthetic('B01-base-plain');del r[field];self.assertFalse(self.valid(r))
        r=synthetic('B01-base-plain');r['effects'][0]['autoPlay']=True;self.assertFalse(self.valid(r))
        r=synthetic('B01-base-plain');r['passed']=True;self.assertFalse(self.valid(r))
        self.assertFalse(gate.validate_card_face_result({'passed':True},'x','B01-base-plain'))

    def test_lightning_order_count_and_damage_mutations(self):
        for case in ('C22-base-plain','R23-upgrade-blocked','R17-upgrade-x3'):
            r=synthetic(case);r['batches'][0]['count']+=1;self.assertFalse(self.valid(r))
            r=synthetic(case);r['history']['damage'][0]['hpLost']+=1;self.assertFalse(self.valid(r))
            r=synthetic(case);r['batches'].pop();self.assertFalse(self.valid(r))
            r=synthetic(case);r['history']['damage'][0]['props']=0;self.assertFalse(self.valid(r))

    def test_choice_identity_and_pending_boundary_mutations(self):
        for case in ('C13-base-material','U15-upgrade-material'):
            r=synthetic(case);r['choice']['sameObjects']=[False];self.assertFalse(self.valid(r))
            r=synthetic(case);r['choice']['actionId']+=1;self.assertFalse(self.valid(r))
            r=synthetic(case);r['choice']['pending']['exhaust']=['material'];self.assertFalse(self.valid(r))
            r=synthetic(case);r['choice']['api']='Viewport.PushInput';self.assertFalse(self.valid(r))
            r=synthetic(case);r['choice']['options']=['material','material'];self.assertFalse(self.valid(r))
            r=synthetic(case);r['choice']['selected']=['alternate'];self.assertFalse(self.valid(r))

    def test_stale_cross_run_duplicate_logs_and_wrong_face_rejected(self):
        r=synthetic('B01-base-plain')
        self.assertFalse(gate.validate_card_face_result(r,'another-run','B01-base-plain'))
        self.assertFalse(gate.validate_card_face_result(r,r['token'],'B01-upgrade-plain'))
        r['version']='v0.107.2';self.assertFalse(self.valid(r))
        r=synthetic('B01-base-plain');line=gate.PREFIX+json.dumps(r)
        self.assertEqual(gate.extract_card_face_result(line,r['token'],r['variant']),r)
        with self.assertRaises(ValueError):gate.extract_card_face_result(line+'\n'+line,r['token'],r['variant'])
        coverage=gate.release_coverage([r,r])
        self.assertEqual(coverage['executed_faces'],1);self.assertEqual(len(coverage['invalid']),1)
        self.assertFalse(coverage['release_pass'])

    def test_engage_and_lightning_cross_target_order_is_not_erased(self):
        for case in ('R09-base-plain','R09-upgrade-plain'):
            r=synthetic(case);damage=r['history']['damage']
            r['history']['damage']=[d for d in damage if d['props']==4]+[d for d in damage if d['props']!=4]
            self.assertFalse(self.valid(r),case)
        for card in ('B04','C04'):
            r=synthetic(card+'-base-plain')
            self.assertEqual([d['target'] for d in r['history']['damage']],[0,-1])
            r['history']['damage'].reverse();self.assertFalse(self.valid(r))
        for card in ('C10','U28'):
            r=synthetic(card+'-base-plain');self.assertEqual(r['history']['damage'][0]['target'],-1)
            r['history']['damage']=r['history']['damage'][1:]+r['history']['damage'][:1]
            self.assertFalse(self.valid(r))
        r=synthetic('U35-base-plain');self.assertEqual(r['history']['damage'][-1]['target'],-1)
        r['history']['damage']=r['history']['damage'][-1:]+r['history']['damage'][:-1];self.assertFalse(self.valid(r))

    def test_permutation_allowed_only_inside_one_aoe_segment(self):
        r=synthetic('C22-base-plain');damage=r['history']['damage']
        r['history']['damage']=sum([list(reversed(damage[i:i+3])) for i in range(0,12,3)],[])
        r['history']['sequence']=[dict(kind='damage',**d) for d in r['history']['damage']]
        self.assertTrue(self.valid(r))
        r['history']['damage'][0],r['history']['damage'][3]=r['history']['damage'][3],r['history']['damage'][0]
        self.assertFalse(self.valid(r))

    def test_upgraded_u26_initial_strength_is_one_not_response_two(self):
        r=synthetic('U26-upgrade-plain')
        self.assertEqual(r['after']['powers'],{'GrowingFuryPower':2,'StrengthPower':1})
        r['after']['powers']['StrengthPower']=2;self.assertFalse(self.valid(r))
        # This test does NOT claim the second-attack responder has executed.
        self.assertEqual(gate.ENTRY_POWERS['U26'][1]['GrowingFuryPower'],2)

    def test_probe_and_oracle_branch_manifests_match(self):
        text=Path('src/Volibear/CardFaceAcceptanceProbe.cs').read_text(encoding='utf-8')
        body=text.split('internal static string[] Branches(string id) => id switch',1)[1].split('};',1)[0]
        parsed={}
        for lhs,rhs in re.findall(r'([^\n]+)=>\s*\[([^\]]+)\]',body):
            values=tuple(re.findall(r'"([^"]+)"',rhs))
            for card in re.findall(r'"([A-Z]\d\d)"',lhs):parsed[card]=values
        for card in gate.ALL_IDS:self.assertEqual(parsed.get(card,('plain',)),gate.branches(card),card)

    def test_replay_single_payment_and_x_snapshot(self):
        r=synthetic('U31-base-x3-replay')
        self.assertEqual(r['payments'],[{'cardRef':'source','amount':3,'energy':0}])
        self.assertEqual(r['after']['enemyHp'],[452,482,482])
        self.assertEqual(len(r['batches']),6)
        r['payments'].append(deepcopy(r['payments'][0]));self.assertFalse(self.valid(r))
        r=synthetic('U31-base-x3-replay');r['effects'][1]['spent']=0;self.assertFalse(self.valid(r))
        r=synthetic('U31-base-x0-replay');self.assertEqual(r['history']['damage'],[])
        self.assertEqual(len(r['history']['plays']),2)

    def test_each_segment_conduction_vs_once_per_play_domain(self):
        r=synthetic('C22-base-domain');self.assertEqual([x['amount'] for x in r['batches']],[4,2,2])
        r=synthetic('C22-base-conduction');self.assertEqual([x['amount'] for x in r['batches']],[3,2,3,2])
        self.assertEqual([x['cardRef'] for x in r['batches']],[None,'source',None,'source'])
        r['batches'][0]['cardRef']='source';self.assertFalse(self.valid(r))

    def test_new_beast_identity_material_exhaust_master_upgrade_and_zero_payment(self):
        for c in ('T01','T02'):
            for face in ('base','upgrade'):
                r=synthetic(f'{c}-{face}-master');self.assertTrue(self.valid(r))
                self.assertEqual(len(r['cards']),11)
                self.assertEqual(r['payments'][0]['amount'],0)
                self.assertIsNone(r['sourceIdentity']['masterUpgradedAfter'])
                self.assertEqual(r['conversions'][0]['materialMasterUpgradedAfter'],False)
                self.assertEqual(r['before']['exhaust'],['source-material'])
                self.assertNotEqual(r['conversions'][0]['materialIndex'],r['conversions'][0]['cardIndex'])
                broken=deepcopy(r);broken['sourceIdentity']['sameMaster']=False;self.assertFalse(self.valid(broken))
                broken=deepcopy(r);broken['sourceIdentity']['indexBefore']+=99;self.assertFalse(self.valid(broken))
                broken=deepcopy(r);broken['conversions'][0]['materialMasterUpgradedAfter']=True;self.assertFalse(self.valid(broken))
                broken=deepcopy(r);broken['conversions'][0]['originalExhausted']=False;self.assertFalse(self.valid(broken))
                broken=deepcopy(r);broken['conversions'][0]['sameObject']=True;self.assertFalse(self.valid(broken))
                broken=deepcopy(r);broken['payments'][0]['amount']=1;self.assertFalse(self.valid(broken))

    def test_exhaust_generate_and_body_response_remain_distinct_native_cards(self):
        r=synthetic('U42-base-curse');self.assertTrue(self.valid(r))
        self.assertEqual(r['after']['hand'],['alternate','selected-beast'])
        self.assertEqual(r['history']['generated'],[dict(cardRef='selected-beast',creatorId=0)])
        self.assertEqual(r['response']['effects'][0]['cardRef'],'selected-beast')
        material=next(card for card in r['after']['selectedCards'] if card['cardRef']=='selected')
        self.assertEqual((material['shape'],material['type'],material['pile']),('None','Curse','Exhaust'))
        for key in ('generated','sequence'):
            broken=deepcopy(r);broken['history'][key]=[];self.assertFalse(self.valid(broken))
        broken=deepcopy(r);broken['response']['effects'][0]['cardRef']='selected';self.assertFalse(self.valid(broken))
        for face in ('base','upgrade'):
            r=synthetic('R27-'+face+'-plain');self.assertTrue(self.valid(r))
            events=r['history']['sequence']
            self.assertEqual([(event['kind'],event.get('cardRef')) for event in events[:3]],
                             [('exhaust','selected'),('exhaust','alternate'),('block','source')])

    def test_native_cross_effect_order_mutations_are_rejected(self):
        for case in ('B04-base-plain','C04-base-plain','C05-base-plain','C13-base-material','U23-base-plain','C24-base-plain','U37-base-plain'):
            r=synthetic(case);sequence=r['history']['sequence']
            self.assertGreater(len(sequence),1)
            sequence[0],sequence[-1]=sequence[-1],sequence[0]
            # Keep redundant projections consistent: reject effect ordering itself.
            r['history']['damage']=[{k:v for k,v in e.items() if k!='kind'} for e in sequence if e['kind']=='damage']
            r['history']['draws']=[e['cardRef'] for e in sequence if e['kind']=='draw']
            self.assertFalse(self.valid(r),case)
        self.assertEqual([e['kind'] for e in synthetic('B04-base-plain')['history']['sequence']],['block','damage','damage','draw'])
        self.assertEqual([e['kind'] for e in synthetic('C10-base-plain')['history']['sequence']],['block','damage','draw','damage'])
        self.assertEqual([e['kind'] for e in synthetic('U23-base-plain')['history']['sequence']],['power','power','power','block'])
        self.assertEqual([e['kind'] for e in synthetic('C13-base-material')['history']['sequence']],['exhaust','draw','draw','draw'])

    def test_distinct_native_instances_and_later_real_payments(self):
        r=synthetic('U02-base-second-instance')
        self.assertEqual(r['after']['powerInstances'],{'StormConductionPower':2})
        self.assertEqual(r['response']['after']['enemyHp'],[472,482,482])
        self.assertEqual([b['amount'] for b in r['response']['batches']],[3,3,3,3])
        self.assertEqual(r['response']['payments'],[dict(cardRef='response-card',amount=1,energy=8)])
        broken=deepcopy(r);broken['after']['powerInstances']['StormConductionPower']=1;self.assertFalse(self.valid(broken))
        broken=deepcopy(r);broken['response']=None;self.assertFalse(self.valid(broken))
        broken=deepcopy(r);broken['response']['effects'][0]['autoPlay']=True;self.assertFalse(self.valid(broken))
        broken=deepcopy(r);broken['response']['payments']=[];self.assertFalse(self.valid(broken))
        for face,energy,block in (('base',9,10),('upgrade',10,15)):
            r=synthetic(f'U21-{face}-second-instance');self.assertEqual(r['response']['after']['energy'],energy)
            r['response']['after']['energy']-=1;self.assertFalse(self.valid(r))
            r=synthetic(f'U34-{face}-second-instance');self.assertEqual(r['response']['after']['block'],block)
            events=r['response']['history']['sequence'];blocks=[x for x in events if x['kind']=='block'];self.assertEqual(len(blocks),2)
            events.remove(blocks[1]);blocks[0]['amount']*=2;self.assertFalse(self.valid(r))
        r=synthetic('U29-upgrade-second-instance')
        self.assertEqual(r['response']['after']['enemyHp'],[488,488,488])
        self.assertEqual(r['response']['after']['powers'],{'StormChargePower':6})

    def test_single_process_batch_completeness_and_native_cleanup(self):
        cases=['B01-base-plain','B02-upgrade-dexterity'];token='unit-fixture-not-native'
        records=[synthetic(case) for case in cases]
        summary=dict(schema=1,token=token,cases=cases,completed=cases,lifecycle='EnterRoom(MapRoom)->ReturnToMainMenu->StartNewSingleplayerRun',shouldSave=False,
            transitions=[dict(variant=case,runIdentity=4+4*i,playerIdentity=5+4*i,creatureIdentity=6+4*i,deckIdentity=7+4*i,
                              runNull=True,combatNull=True,inProgress=False,queueEmpty=True,actionNull=True,historyVisible=0) for i,case in enumerate(cases)])
        def log(rs=records,s=summary):return '\n'.join(gate.PREFIX+json.dumps(r) for r in rs)+'\n'+gate.BATCH_PREFIX+json.dumps(s)
        self.assertTrue(gate.validate_card_face_batch(log(),token,cases))
        self.assertEqual(gate.extract_card_face_batch(log(),token,cases)['coverage']['executed_faces'],2)
        for text in (log(records[:1]),log(records+records[:1]),log(list(reversed(records))),log()+'\n'+gate.BATCH_PREFIX+json.dumps(summary),
                     log()+'\n[Volibear] CARD_FACE_BATCH_ERROR injected'):
            self.assertFalse(gate.validate_card_face_batch(text,token,cases))
        broken=deepcopy(records);broken[1]['token']='other-run';self.assertFalse(gate.validate_card_face_batch(log(broken),token,cases))
        broken=deepcopy(records);broken[1]['after']['block']-=1;self.assertFalse(gate.validate_card_face_batch(log(broken),token,cases))
        for key,value in [('runNull',False),('combatNull',False),('inProgress',True),('queueEmpty',False),('actionNull',False),('historyVisible',1),('runIdentity',4)]:
            broken=deepcopy(summary);broken['transitions'][1][key]=value
            self.assertFalse(gate.validate_card_face_batch(log(s=broken),token,cases),key)
        broken=deepcopy(summary);broken['completed']=cases[:1];self.assertFalse(gate.validate_card_face_batch(log(s=broken),token,cases))
        self.assertFalse(gate.validate_card_face_batch(log(),token,cases+cases[:1]))
        host=Path('src/Volibear/NativeAcceptanceRunHost.cs').read_text(encoding='utf-8')
        for api in ('EnterRoom(new MapRoom())','ReturnToMainMenu()','StartNewSingleplayerRun','EnterRoomDebug','shouldSave:false','WaitForQuiet'):
            self.assertIn(api,host)
        self.assertNotIn('SendInput',host)

    def test_full_implemented_set_is_not_full_g2(self):
        coverage=gate.release_coverage([synthetic(v) for v in gate.CARD_FACE_CASES])
        self.assertEqual(coverage['executed_faces'],len(gate.IMPLEMENTED_IDS)*2)
        self.assertEqual(len(coverage['missing_faces']),178-len(gate.IMPLEMENTED_IDS)*2)
        self.assertFalse(coverage['section7_complete']);self.assertFalse(coverage['release_pass'])


if __name__=='__main__': unittest.main()
