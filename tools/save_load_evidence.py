"""Strict S1/S2 room-entry save lifecycle oracle; synthetic tests are not game evidence."""
import copy
import json
import ntpath
import re

PREFIX = '[Volibear] SAVE_LOAD_RESULT '
SCOPE = 'native-checkpoint-save-load-apis-no-input'
CARD_FIELDS = set('entity id nativeType upgrade type target shape converted canonicalCost cost costsX vars keywords enchantment pile owner masterIndex masterEntity'.split())
SNAP_FIELDS = set('runEntity combatEntity playerEntity character shouldSave seed room encounter round turn energy hp maxHp block gold deck relics powers piles enemies'.split())
ROOT_FIELDS = set('schema token pair phase mode caseId pid userRoot checkpointPath gameVersion gameCommit testMode assemblyMvid acceptance seed fixture events checkpoint afterMenu initial interruption interrupted resumed afterLoad'.split())
FACES = {
 'VOLIBEAR_B01': ('Attack','AnyEnemy',{'Damage':6}),
 'VOLIBEAR_B02': ('Skill','Self',{'Block':5}),
 'VOLIBEAR_B03': ('Attack','AnyEnemy',{'Damage':8,'Lightning':3}),
 'VOLIBEAR_B04': ('Attack','AnyEnemy',{'Damage':6,'Block':8}),
 'VOLIBEAR_U03': ('Power','Self',{'Block':12,'Decay':3}),
}

def need(ok, message):
    if not ok: raise ValueError(message)

def eq(a,b):
    if isinstance(a,bool) or isinstance(b,bool): return type(a) is type(b) and a==b
    if isinstance(a,dict) and isinstance(b,dict): return a.keys()==b.keys() and all(eq(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list): return len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
    return a==b

def first_difference(expected,observed,path='$'):
    """Diagnostic only: does not normalize values or participate in the verdict."""
    if eq(expected,observed):return ''
    if isinstance(expected,dict) and isinstance(observed,dict):
        for key in expected:
            child=path+'.'+key
            if key not in observed:return f'{child}: missing; expected {expected[key]!r}'
            if not eq(expected[key],observed[key]):return first_difference(expected[key],observed[key],child)
        for key in observed:
            if key not in expected:return f'{path}.{key}: unexpected value {observed[key]!r}'
    if isinstance(expected,list) and isinstance(observed,list):
        if len(expected)!=len(observed):return f'{path}: expected length {len(expected)}, observed {len(observed)}'
        for index,(a,b) in enumerate(zip(expected,observed)):
            if not eq(a,b):return first_difference(a,b,f'{path}[{index}]')
    return f'{path}: expected {expected!r}, observed {observed!r}'

def positive(x): return type(x) is int and x>0

def norm(path):
    need(isinstance(path,str) and path, 'path type')
    return ntpath.normcase(ntpath.normpath(path))

def neutral(value):
    refs={'entity','owner','masterEntity','runEntity','combatEntity','playerEntity'}
    if isinstance(value,dict): return {k:neutral(v) for k,v in value.items() if k not in refs}
    if isinstance(value,list): return [neutral(v) for v in value]
    return value

def expected_deck(case):
    return ['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']+(['VOLIBEAR_U03'] if case=='S2' else [])

def card(c, snapshot, index, pile, form=False):
    need(set(c)==CARD_FIELDS,'card fields')
    need(positive(c['entity']) and positive(c['owner']) and c['owner']==snapshot['playerEntity'],'card identity/owner')
    need(type(c['upgrade']) is int and type(c['cost']) in (int,float) and type(c['canonicalCost']) in (int,float),'card numeric types')
    need(type(c['masterIndex']) is int and c['masterIndex']==index and c['pile']==pile,'card scope')
    need(c['nativeType']=='Volibear_'+c['id'].removeprefix('VOLIBEAR_'),'native model/deprecated')
    need(eq(c['costsX'],False) and c['enchantment'] is None and c['canonicalCost']==1,'card canonical cost')
    if form:
        need(index==-1 and c['masterEntity'] is None,'generated token has no master link')
        need(c['id'] in ('VOLIBEAR_T01','VOLIBEAR_T02') and eq(c['converted'],True),'native beast definition')
        claw=c['id']=='VOLIBEAR_T01';shape='Claw' if claw else 'Body'
        need(c['upgrade']==(0 if claw else 1),'material upgrade inherited')
        vars={'Damage':7,'Hits':2} if claw else {'Block':12,'Lightning':3}
        need(c['shape']==shape and c['cost']==0 and c['pile']=='Hand','temporary token cost/location')
        need(c['type']==('Attack' if claw else 'Skill') and c['target']==('AnyEnemy' if claw else 'AllEnemies'),'token metadata')
        need(eq(c['vars'],vars) and eq(c['keywords'],['Exhaust']),'token vars/keywords')
    else:
        master=snapshot['deck'][index]
        need(c['id']==master['id'] and c['upgrade']==master['upgrade'],'clone definition identity')
        if pile=='Deck': need(c['masterEntity'] is None,'master is not a clone')
        else: need(positive(c['masterEntity']) and c['masterEntity']==master['entity'] and c['entity']!=master['entity'],'DeckVersion identity')
        kind,target,vars=FACES[c['id']]
        need(eq(c['converted'],False) and c['shape']=='None' and c['cost']==1,'original form/cost')
        need(c['type']==kind and c['target']==target and eq(c['vars'],vars) and eq(c['keywords'],[]),'original native definition')

def snapshot(s, case, seed, interrupted=False):
    need(isinstance(s,dict) and set(s)==SNAP_FIELDS,'snapshot fields')
    need(all(positive(s[k]) for k in ('runEntity','combatEntity','playerEntity')),'runtime identities')
    for key,val in dict(character='VOLIBEAR_CHARACTER',shouldSave=True,seed=seed,room='CombatRoom',round=1,turn=1,
                        energy=2 if interrupted else 3,hp=80,maxHp=80,block=5 if interrupted else 0,gold=99).items():
        need(eq(s[key],val),f'snapshot.{key}: expected {val!r}, observed {s[key]!r}')
    need(isinstance(s['encounter'],str) and s['encounter'],'encounter')
    need(eq(s['powers'],[]) and eq(s['relics'],[{'id':'VOLIBEAR_HUNTERS_HEART','type':'HuntersHeart'}]),'starter relic/powers')
    deck=expected_deck(case)
    need([c['id'] for c in s['deck']]==deck,'ordered master deck')
    need([c['upgrade'] for c in s['deck']]==[0]*10+([1] if case=='S2' else []),'master upgrades')
    for i,c in enumerate(s['deck']): card(c,s,i,'Deck')
    need(len({c['entity'] for c in s['deck']})==len(deck),'master duplicates')
    need(set(s['piles'])=={'Draw','Hand','Discard','Exhaust','Play'},'native piles')
    rows=[];forms=[]
    for pile,cards in s['piles'].items():
        need(isinstance(cards,list),'pile list')
        for c in cards:
            idx=c['masterIndex'];isform=interrupted and case=='S2' and c['converted'] is True
            need(type(idx) is int and (idx==-1 if isform else 0<=idx<len(deck)),'master index')
            card(c,s,idx,pile,isform);rows.append(c)
            if isform: forms.append(c['id'])
    originals=[c for c in rows if c['masterIndex']>=0]
    need(len(originals)==len(deck) and sorted(c['masterIndex'] for c in originals)==list(range(len(deck))),'original clone coverage')
    need(len(rows)==len(deck)+(2 if interrupted and case=='S2' else 0),'native generated token count')
    need(len({c['entity'] for c in rows})==len(rows),'duplicate clone')
    need(not s['piles']['Play'],'unexpected playing card')
    need([c['id'] for c in s['piles']['Exhaust']]==(['VOLIBEAR_B01','VOLIBEAR_U03'] if interrupted and case=='S2' else []),'native material exhaust pile')
    if interrupted:
        need(len(s['piles']['Discard'])==1 and s['piles']['Discard'][0]['id']=='VOLIBEAR_B02','native defend discarded')
        need(sorted(forms)==(['VOLIBEAR_T01','VOLIBEAR_T02'] if case=='S2' else []),'exact changed materials')
    else: need(not s['piles']['Discard'] and len(s['piles']['Hand'])==5,'fresh starting hand')
    need(isinstance(s['enemies'],list) and len(s['enemies'])>0,'native encounter enemies')
    for e in s['enemies']:
        need(set(e)=={'id','hp','maxHp','block','move'} and isinstance(e['id'],str) and e['id'] and isinstance(e['move'],str) and e['move'],'enemy identity/intent')
        need(all(type(e[k]) in (int,float) for k in ('hp','maxHp','block')) and 0<e['hp']<=e['maxHp'] and e['block']>=0,'enemy initial hp/block')

def checkpoint(c,case,seed):
    need(isinstance(c,dict) and c.get('pre_finished_room') is None,'active room checkpoint')
    need(c['rng']['seed']==seed and positive(c['start_time']) and type(c['num_reloads']) is int and c['num_reloads']>=0,'checkpoint seed/reloads')
    need(len(c['players'])==1 and len(c['visited_map_coords'])==1,'checkpoint player/map route')
    p=c['players'][0]
    need(p['character_id']=='CHARACTER.VOLIBEAR_CHARACTER','saved character')
    for key,val in [('current_hp',80),('max_hp',80),('max_energy',3),('gold',99)]: need(eq(p[key],val),'saved '+key)
    need([row['id'] for row in p['deck']]==['CARD.'+i for i in expected_deck(case)],'saved master identities')
    need(all(type(row.get('current_upgrade_level',0)) is int for row in p['deck']) and
         [row.get('current_upgrade_level',0) for row in p['deck']]==[0]*10+([1] if case=='S2' else []),'saved upgrades')
    need([row['id'] for row in p['relics']]==['RELIC.VOLIBEAR_HUNTERS_HEART'],'saved relic')
    need(not any(k in p for k in ('hand','draw','discard','exhaust','powers','energy')),'no fake midbattle save')
    native_reload_expected(c) # Validate the exact pinned native map representation before permitting phase B.

def native_reload_expected(before):
    """Pinned SerializableMapPoint.cs19-21 only: omitted false deserializes to true.

    The native initializer is true but WhenWritingDefault omits false. IncrementNumReloads
    reserializes that loaded SerializableRun. Do not ignore map fields or normalize any
    other path: construct its precise rewrite and still compare the complete JSON tree.
    """
    expected=copy.deepcopy(before)
    need(type(expected['num_reloads']) is int and expected['num_reloads']>=0,'native reload integer counter')
    expected['num_reloads']+=1
    need(isinstance(expected['acts'],list) and expected['acts'],'native acts list')
    paths=[]
    for ai,act in enumerate(expected['acts']):
        need(isinstance(act,dict),'native act object')
        saved_map=act.get('saved_map')
        if saved_map is None:continue
        need(isinstance(saved_map,dict) and isinstance(saved_map.get('points'),list),'native saved_map points')
        for pi,point in enumerate(saved_map['points']):
            need(isinstance(point,dict),'native map point object')
            if 'can_modify' in point:
                need(point['can_modify'] is True,'native fresh checkpoint can_modify must be literal true or omitted')
            else:
                point['can_modify']=True
                paths.append(f'acts[{ai}].saved_map.points[{pi}].can_modify')
    return expected,paths

def validate_phase(r, expected, errors=None):
    """Return the unchanged strict verdict; optionally report the first failing assertion."""
    stage='bindings'
    try:
        need(set(r)==ROOT_FIELDS,'root fields')
        for k in ('token','pair','phase','mode','caseId','seed','pid'): need(eq(r[k],expected[k]),'phase binding '+k)
        for k in ('userRoot','checkpointPath'): need(norm(r[k])==norm(expected[k]),'profile binding '+k)
        need(positive(r['pid']) and r['caseId'] in ('S1','S2'),'pid/case')
        need((r['mode']=='same-process' and r['phase']=='same') or (r['mode']=='restart' and r['phase'] in ('prepare','resume')),'mode/phase')
        for k,v in dict(schema=1,gameVersion='v0.107.1',gameCommit='59260271',testMode=False,acceptance=SCOPE).items(): need(eq(r[k],v),k)
        need(isinstance(r['assemblyMvid'],str) and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',r['assemblyMvid']) is not None,'assembly binding')
        stage='checkpoint'
        checkpoint(r['checkpoint'],r['caseId'],r['seed'])
        stage='fixture-and-native-menu-events'
        events=r['events'];need(isinstance(events,list),'events')
        allowed={'native-run-api','state-fixture-native-move-to-hand','state-fixture-convert-and-temporary-zero'}
        need(all(e.get('op') in allowed for e in events),'fixture/UI operations')
        for event in events:
            fields = {'op','api'} if event['op']=='native-run-api' else ({'op','id'} if event['op']=='state-fixture-convert-and-temporary-zero' else {'op','id','entity'})
            need(set(event)==fields,'operation fields')
        conversions=[v['id'] for v in events if v['op']=='state-fixture-convert-and-temporary-zero']
        need(conversions==(['VOLIBEAR_B01','VOLIBEAR_U03'] if r['caseId']=='S2' and r['phase']!='resume' else []),'explicit state-fixture labels')
        ui_started=False
        for event in events:
            if event['op']=='native-run-api':ui_started=True
            else:
                need(not ui_started,'no fixture after quit/load')
                if 'entity' in event:
                    need(positive(event['entity']) and event['id'] in ('VOLIBEAR_B01','VOLIBEAR_B02','VOLIBEAR_U03'),'move fixture identity')
                    matches=[c for cards in r['interrupted']['piles'].values() for c in cards if c['entity']==event['entity'] and c['id']==event['id']]
                    need(len(matches)==1,'move fixture belongs to native combat')
        apis=[event['api'] for event in events if event['op']=='native-run-api']
        restore=next((api for api in apis if api.startswith('SaveManager.LoadRunSave;')),None)
        if restore is not None:
            need(restore in ('SaveManager.LoadRunSave;RunState.FromSerializable;RunManager.SetUpSavedSingleplayer;NGame.LoadRun',
                             'SaveManager.LoadRunSave;RunState.FromSerializable;RunManager.SetUpSavedSinglePlayer;NGame.LoadRun'),'native synchronizer setup + restore')
        need(apis==([restore] if r['phase']=='resume' else ['NGame.ReturnToMainMenu']+([restore] if r['phase']=='same' else [])), 'actual native save/restore lifecycle')
        need(r['phase']=='prepare' or restore is not None,'native checkpoint restoration required')
        if r['phase']=='resume':
            need(all(r[k] is None for k in ('fixture','initial','interruption','interrupted','afterMenu')),'resume cannot create/modify run')
            need(len(events)==1,'resume-only operation')
        else:
            f=r['fixture'];need(set(f)==set('directRunApi statsExistedBefore statsPresent ftuesDisabledInIsolatedProfile shouldSave startedWithNeow masterPreparation'.split()),'fixture fields')
            need(type(f['statsExistedBefore']) is bool,'stats prior type')
            need(eq(f,dict(directRunApi=True,statsExistedBefore=f['statsExistedBefore'],statsPresent=True,ftuesDisabledInIsolatedProfile=True,
                           shouldSave=True,startedWithNeow=False,masterPreparation='native-CreateCard-AddToDeck-Upgrade-U03' if r['caseId']=='S2' else 'native-starter-deck')),'explicit prerequisites')
            stage='initial'
            snapshot(r['initial'],r['caseId'],r['seed'])
            stage='interrupted'
            snapshot(r['interrupted'],r['caseId'],r['seed'],True)
            stage='interruption-receipts'
            need(eq(r['afterMenu'],r['checkpoint']),'SaveQuit must not write interrupted combat')
            need(eq(r['initial']['deck'],r['interrupted']['deck']),'master untouched in combat')
            need(eq(r['initial']['enemies'],r['interrupted']['enemies']),'no accidental kill/checkpoint advance')
            d=r['interruption'];need(set(d)=={'converted','payment'},'interruption fields')
            p=d['payment'];aid=p['actionId'];need(type(aid) is int and aid>=0,'action id')
            need(eq(p,dict(action='PlayCardAction',state='Finished',actionId=aid,context='GameActionPlayerChoiceContext',
                           history=[dict(id='VOLIBEAR_B02',autoPlay=False,spent=1,index=0,count=1)],
                           afterEnergySpent=[dict(id='VOLIBEAR_B02',amount=1,energy=2)],energyHistory=[1])),f'native paid disturbance: observed {p!r}')
            need(len(d['converted'])==(2 if r['caseId']=='S2' else 0),'conversion receipts')
            for row,id in zip(d['converted'],['VOLIBEAR_B01','VOLIBEAR_U03']):
                need(set(row)=={'original','materialAfter','form','masterBefore','masterAfter','nativeExhaust','nativeGenerated'},'conversion fields')
                need(row['original']['id']==id and row['materialAfter']['id']==id,'original material definition retained')
                need(row['form']['id']==('VOLIBEAR_T01' if id=='VOLIBEAR_B01' else 'VOLIBEAR_T02'),'new native token definition')
                need(row['nativeExhaust'] is True and row['nativeGenerated'] is True,'native exhaustion and generation history')
                need(eq(row['masterBefore'],row['masterAfter']),'master state untouched by conversion')
                idx=row['original']['masterIndex'];need(eq(row['masterBefore'],r['initial']['deck'][idx]),'master source binding')
                card(row['original'],r['initial'],idx,'Hand');card(row['materialAfter'],r['interrupted'],idx,'Exhaust')
                card(row['form'],r['interrupted'],-1,'Hand',True)
                need(row['original']['entity']==row['materialAfter']['entity']!=row['form']['entity'],'native generated token has a new identity')
                for key,pile in [('materialAfter','Exhaust'),('form','Hand')]:
                    found=[c for c in r['interrupted']['piles'][pile] if c['entity']==row[key]['entity']]
                    need(eq(found,[row[key]]),'material/token native pile identities')
        if r['phase']=='prepare': need(r['resumed'] is None and r['afterLoad'] is None,'A must not Continue')
        else:
            stage='resumed'
            snapshot(r['resumed'],r['caseId'],r['seed'])
            stage='reload-and-fresh-instance-identity'
            expected_save,_=native_reload_expected(r['checkpoint'])
            need(eq(r['afterLoad'],expected_save),'exact native reload rewrite: '+first_difference(expected_save,r['afterLoad']))
            if r['phase']=='same':
                need(eq(neutral(r['initial']),neutral(r['resumed'])),'room-entry replay, not midbattle restore')
                for k in ('runEntity','combatEntity','playerEntity'):need(r['initial'][k]!=r['resumed'][k],'fresh runtime '+k)
                def entities(s):return {c['entity'] for c in s['deck']} | {c['entity'] for pile in s['piles'].values() for c in pile}
                need(not (entities(r['initial']) & entities(r['resumed'])),'new master and combat instances')
        return True
    except (ValueError,KeyError,TypeError,IndexError,AttributeError) as error:
        if errors is not None: errors.append(f'{stage}: {type(error).__name__}: {error}')
        return False

def diagnose_phase(raw, expected):
    errors=[]
    validate_phase(raw,expected,errors)
    return errors

def validate_pair(a,b,expected_a,expected_b,a_shared,b_shared):
    if not a_shared or not b_shared: return False
    if not validate_phase(a,expected_a) or not validate_phase(b,expected_b): return False
    try:
        need(a['phase']=='prepare' and b['phase']=='resume' and a['pid']!=b['pid'] and a['token']!=b['token'],'two real processes')
        for k in ('pair','caseId','mode','seed','userRoot','checkpointPath','assemblyMvid'):need(a[k]==b[k],'pair '+k)
        need(eq(a['afterMenu'],b['checkpoint']),'unchanged shared isolated checkpoint')
        need(eq(neutral(a['initial']),neutral(b['resumed'])),'restarted native entry')
        return True
    except (ValueError,KeyError,TypeError):return False

def parse_log(log,expected,errors=None):
    matches=[line.split(PREFIX,1)[1] for line in log.splitlines() if PREFIX in line]
    if len(matches)!=1 or '[Volibear] SHUTDOWN_BEGIN '+expected['token'] not in log or 'SAVE_LOAD_PROBE_ERROR' in log:
        if errors is not None: errors.append(f'log envelope: result_count={len(matches)}, token-bound shutdown required, no probe error permitted')
        return None,False
    try:r=json.loads(matches[0])
    except (ValueError,TypeError) as error:
        if errors is not None: errors.append(f'raw JSON: {error}')
        return None,False
    return r,validate_phase(r,expected,errors)
