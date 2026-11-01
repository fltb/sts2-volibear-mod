"""Independent schema2 persistence oracle. Does not alter frozen S1/S2 rules."""
import copy
import json
import math
import re
import sys
from pathlib import Path
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/headless.py').is_file())
if str(ROOT/'tools') not in sys.path:sys.path.append(str(ROOT/'tools'))
from save_load_evidence import eq,need,norm,positive,native_reload_expected,first_difference
from catalog_evidence import expected_catalog,display_text,TARGETS
PREFIX='[Volibear] SAVE_CATALOG_RESULT '
SCOPE='native-save-catalog-programmatic-ui-not-G6'
CATALOG=expected_catalog()
ROOT_FIELDS=set('schemaVersion scenario token pair phase mode caseId roomKind pid userRoot checkpointPath gameVersion gameCommit testMode assemblyMvid acceptance seed fixture events checkpoint afterMenu initial interruption interrupted resumed afterLoad resumedCase route'.split())
CARD_FIELDS=set('entity id nativeType upgrade type rarity target shape converted canonicalCost cost allCost costsX vars title description serialized keywords enchantment pile owner masterIndex masterEntity'.split())
SNAP_FIELDS=set('runEntity combatEntity playerEntity creatureEntity character shouldSave seed room encounter round turn energy hp maxHp block gold deck relics powers piles enemies'.split())
RELIC_FIELDS=set('entity id type owner slot melted serialized'.split())


def keys(value,fields,label):need(isinstance(value,dict) and set(value)==fields,label+' fields')
def entries(case):
    if case=='S3':return [(id,level) for id in sorted(CATALOG) for level in (0,1)]
    raise ValueError('Unimplemented staged case '+str(case))

def serialized_card(value,id,level):
    need(isinstance(value,dict) and value.get('id')=='CARD.'+id,'serialized card ID')
    need(type(value.get('current_upgrade_level',0)) is int and value.get('current_upgrade_level',0)==level,'serialized upgrade')
    need(value.get('enchantment') is None,'unexpected persistent enchantment')

def card_definition(c):
    keys(c,CARD_FIELDS,'card')
    catalogue=CATALOG;need(c['id'] in catalogue,'unknown/deprecated ID')
    need(type(c['upgrade']) is int and c['upgrade'] in (0,1),'upgrade type')
    definition=catalogue[c['id']];face=definition['faces'][c['upgrade']]
    expected=dict(nativeType='Volibear_'+definition['card_id'],type=definition['type'].title(),rarity=definition['rarity'].title(),
                  target=TARGETS[definition['play_target']],shape={'T01':'Claw','T02':'Body'}.get(definition['card_id'],'None'),converted=False,
                  canonicalCost=0 if definition['faces'][0]['cost']=='X' else definition['faces'][0]['cost'],
                  cost=0 if face['cost']=='X' else face['cost'],allCost=0 if face['cost']=='X' else face['cost'],costsX=face['cost']=='X',
                  keywords=['Exhaust'] if face['self_exhaust'] else [],enchantment=None)
    for field,value in expected.items():need(eq(c[field],value),f"{c['id']}+{c['upgrade']} {field}: expected {value!r}, observed {c[field]!r}")
    need(display_text(c['title'])==definition['name_zh']+('+' if c['upgrade'] else ''),'independent title')
    need(display_text(c['description'])==display_text(face['display_text_zh']),'independent formatted face')
    serialized_card(c['serialized'],c['id'],c['upgrade'])
    need(isinstance(c['vars'],dict),'native variables')
    # The independent fixture does NOT define engine variable names/values. Preserve
    # observations exactly across load; never manufacture a separate numeric oracle.
    for name,var in c['vars'].items():
        need(isinstance(name,str) and name,'variable name')
        keys(var,{'kind','baseValue','enchantedValue','previewValue'},'variable')
        need(isinstance(var['kind'],str) and var['kind'],'native variable kind')
        need(all(type(var[k]) in (int,float) and math.isfinite(var[k]) for k in ('baseValue','enchantedValue','previewValue')),'finite native variable values')

def neutral_snapshot(s):
    value=copy.deepcopy(s)
    for key in ('runEntity','combatEntity','playerEntity','creatureEntity'):value.pop(key)
    for c in value['deck']+[c for rows in value['piles'].values() for c in rows]:
        for key in ('entity','owner','masterEntity'):c.pop(key)
    for relic in value['relics']:
        for key in ('entity','owner'):relic.pop(key)
    for enemy in value['enemies']:enemy.pop('entity')
    return value

def base_vars(c):
    value=copy.deepcopy(c['vars'])
    for var in value.values():var.pop('previewValue')
    return value


def stable_card(c):
    value=copy.deepcopy(c)
    value.pop('pile');value.pop('description')
    for var in value['vars'].values():var.pop('previewValue')
    return value


def continuity(a,b):
    # No load/room boundary: native identities and persistent/base definition
    # fields cannot change. Only pile membership, contextual text and previews
    # are mutable here. Generated statuses are validated separately.
    for key in ('runEntity','combatEntity','playerEntity','creatureEntity'):need(eq(a[key],b[key]),'continuous '+key)
    need(eq(a['relics'],b['relics']),'continuous relic identity/data')
    need(eq([stable_card(c) for c in a['deck']],[stable_card(c) for c in b['deck']]),'continuous masters/base/enchanted vars')
    def clones(s):return {c['entity']:stable_card(c) for rows in s['piles'].values() for c in rows if c['masterIndex']>=0}
    need(eq(clones(a),clones(b)),'continuous clone identities and serialized/base fields')


def snapshot(s,case,seed,interrupted=False):
    keys(s,SNAP_FIELDS,'active snapshot')
    for key in ('runEntity','combatEntity','playerEntity','creatureEntity'):need(positive(s[key]),'native identity '+key)
    for key,value in dict(character='VOLIBEAR_CHARACTER',shouldSave=True,seed=seed,room='CombatRoom',round=1,turn=1,energy=2 if interrupted else 3,
                          hp=80,maxHp=80,block=5 if interrupted else 0,gold=99,powers=[]).items():
        need(eq(s[key],value),f'snapshot.{key}: expected {value!r}, observed {s[key]!r}')
    expected=entries(case)
    need([(c['id'],c['upgrade']) for c in s['deck']]==expected,'exact ordered89/178 master faces')
    master_ids=[]
    for i,c in enumerate(s['deck']):
        card_definition(c)
        need(positive(c['entity']) and positive(c['owner']) and c['owner']==s['playerEntity'],'master owner identity')
        need(c['pile']=='Deck' and eq(c['masterIndex'],i) and c['masterEntity'] is None,'master scope/index')
        master_ids.append(c['entity'])
    need(len(set(master_ids))==178,'independent master objects')
    need(set(s['piles'])=={'Draw','Hand','Discard','Exhaust','Play'},'native combat piles')
    clones=[]
    for pile,rows in s['piles'].items():
        need(isinstance(rows,list),'pile rows')
        for c in rows:
            card_definition(c);i=c['masterIndex'];need(type(i) is int and 0<=i<178,'clone index')
            need(c['pile']==pile and positive(c['owner']) and c['owner']==s['playerEntity'] and positive(c['entity']) and positive(c['masterEntity']),'clone owner/pile')
            need(c['masterEntity']==master_ids[i] and c['entity'] not in master_ids,'DeckVersion native linkage')
            need((c['id'],c['upgrade'])==expected[i],'clone face maps to correct master instance')
            need(eq(c['serialized'],s['deck'][i]['serialized']),'clone serialized fields exactly inherit master')
            need(eq(base_vars(c),base_vars(s['deck'][i])),'clone inherits master base/enchanted values; preview is contextual')
            clones.append(c)
    need(len(clones)==178 and len({c['entity'] for c in clones})==178 and sorted(c['masterIndex'] for c in clones)==list(range(178)),'one clone per master')
    need(not s['piles']['Exhaust'] and not s['piles']['Play'],'no unintended played/exhausted cards')
    discard=s['piles']['Discard']
    if interrupted:need(len(discard)==1 and discard[0]['id']=='VOLIBEAR_B02' and discard[0]['upgrade']==0,'actual base B02 discard')
    else:need(not discard and len(s['piles']['Hand'])==5,'native fresh hand')
    need(len(s['relics'])==1,'starter relic count')
    relic=s['relics'][0];keys(relic,RELIC_FIELDS,'relic')
    need(positive(relic['entity']) and relic['owner']==s['playerEntity'] and eq(relic['slot'],0),'relic ownership/slot')
    need(eq(relic['melted'],False) and relic['id']=='VOLIBEAR_HUNTERS_HEART' and relic['type']=='HuntersHeart','starter relic definition')
    need(relic['serialized']['id']=='RELIC.VOLIBEAR_HUNTERS_HEART','serialized relic')
    all_refs=[s[k] for k in ('runEntity','combatEntity','playerEntity','creatureEntity')]+master_ids+[c['entity'] for c in clones]+[relic['entity']]+[enemy['entity'] for enemy in s['enemies']]
    need(len(set(all_refs))==len(all_refs),'native object type/instance alias')
    need(s['encounter']=='NIBBITS_WEAK' and len(s['enemies'])==1,'pinned fresh native solo encounter')
    first=s['enemies'][0]
    need(first['id']=='NIBBIT' and type(first['hp']) is int and 42<=first['hp']<=46 and first['maxHp']==first['hp'] and first['block']==0 and first['move']=='BUTT_MOVE','pinned ascension0 initial Nibbit, not the obsolete HP30/BUTT fixture')
    for enemy in s['enemies']:
        keys(enemy,{'entity','id','hp','maxHp','block','move'},'enemy')
        need(positive(enemy['entity']),'native enemy identity')
        need(isinstance(enemy['id'],str) and enemy['id'] and isinstance(enemy['move'],str) and enemy['move'],'native monster intent')
        need(all(type(enemy[k]) in (int,float) for k in ('hp','maxHp','block')) and 0<enemy['hp']<=enemy['maxHp'] and enemy['block']>=0,'native enemy resources')

def checkpoint(c,case,seed):
    need(isinstance(c,dict) and c.get('pre_finished_room') is None,'active-entry checkpoint')
    need(c['rng']['seed']==seed and positive(c['start_time']) and len(c['visited_map_coords'])==1,'entry checkpoint identity')
    need(len(c['players'])==1,'singleplayer checkpoint');p=c['players'][0]
    for key,value in dict(character_id='CHARACTER.VOLIBEAR_CHARACTER',current_hp=80,max_hp=80,max_energy=3,gold=99).items():need(eq(p[key],value),'saved '+key)
    expected=entries(case);need(len(p['deck'])==178,'native master count')
    for row,(id,level) in zip(p['deck'],expected):serialized_card(row,id,level)
    need([r['id'] for r in p['relics']]==['RELIC.VOLIBEAR_HUNTERS_HEART'],'saved relic set')
    native_reload_expected(c)

def preparation(r):
    fixture=r['fixture'];keys(fixture,set('directRunApi statsExistedBefore statsPresent ftuesDisabledInIsolatedProfile shouldSave startedWithNeow masterPreparation'.split()),'fixture')
    for key,value in dict(directRunApi=True,statsPresent=True,ftuesDisabledInIsolatedProfile=True,shouldSave=True,startedWithNeow=False).items():need(eq(fixture[key],value),'fixture '+key)
    need(type(fixture['statsExistedBefore']) is bool,'prior stats marker')
    prep=fixture['masterPreparation'];keys(prep,{'kind','removed','registryIds','acquired'},'catalog acquisition')
    need(prep['kind']=='explicit-native-catalog-master-construction-not-natural-acquisition','scope of catalog setup')
    need(prep['registryIds']==sorted(CATALOG),'independent exact89 registry')
    need([c['id'] for c in prep['removed']]==['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04'],'actual removed starter deck')
    for row in prep['removed']:
        keys(row,{'entity','id','upgrade'},'removed starter');need(positive(row['entity']) and eq(row['upgrade'],0),'starter removal identity')
    need(len({c['entity'] for c in prep['removed']})==10,'unique removed starter objects')
    expected=entries(r['caseId']);need(len(prep['acquired'])==178,'native acquired178')
    for i,(row,(id,level)) in enumerate(zip(prep['acquired'],expected)):
        keys(row,set('entity id upgrade upgraderCalled owner deckIndex beforeKeywords afterKeywords serialized'.split()),'native acquire receipt')
        definition=CATALOG[id]
        need(row['id']==id and eq(row['upgrade'],level) and eq(row['upgraderCalled'],level==1) and row['deckIndex']==i,'native upgrade operation/index')
        need(eq(row['beforeKeywords'],['Exhaust'] if definition['faces'][0]['self_exhaust'] else []),'keywords read before upgrade')
        need(eq(row['afterKeywords'],['Exhaust'] if definition['faces'][level]['self_exhaust'] else []),'native upgrade keyword cache')
        master=r['initial']['deck'][i]
        need(row['entity']==master['entity'] and row['owner']==r['initial']['playerEntity'],'acquired master identity')
        need(eq(row['serialized'],master['serialized']),'acquisition persisted properties')
    need(not ({c['entity'] for c in prep['removed']} & {c['entity'] for c in prep['acquired']}),'removed starter objects not reused')

def validate_phase(r,expected,errors=None):
    stage='bindings'
    try:
        keys(r,ROOT_FIELDS,'schema2 root')
        for k in ('token','pair','phase','mode','caseId','seed','pid'):need(eq(r[k],expected[k]),'binding '+k)
        for k in ('userRoot','checkpointPath'):need(norm(r[k])==norm(expected[k]),'isolation '+k)
        need(positive(r['pid']) and r['caseId']=='S3','supported staged case/PID')
        need((r['mode']=='same-process' and r['phase']=='same') or (r['mode']=='restart' and r['phase'] in ('prepare','resume')),'phase/mode')
        for k,value in dict(schemaVersion=2,scenario='save-load-catalog',roomKind='active-entry',gameVersion='v0.107.1',gameCommit='59260271',testMode=False,acceptance=SCOPE).items():need(eq(r[k],value),k)
        need(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',r['assemblyMvid']) is not None,'assembly MVID')
        stage='checkpoint';checkpoint(r['checkpoint'],r['caseId'],r['seed'])
        stage='native UI';events=r['events'];need(isinstance(events,list),'events list')
        for event in events:
            need(event.get('op') in ('native-ui-forceclick','state-fixture-native-move-to-hand'),'allowed UI/fixture operation')
            keys(event,{'op','button'} if event['op']=='native-ui-forceclick' else {'op','id','entity'},'event')
        buttons=[v['button'] for v in events if v['op']=='native-ui-forceclick']
        need(buttons==(['Continue'] if r['phase']=='resume' else ['Pause','SaveAndQuit']+(['Continue'] if r['phase']=='same' else [])),'real menu lifecycle')
        if r['phase']=='resume':
            need(len(events)==1 and all(r[k] is None for k in ('fixture','afterMenu','initial','interruption','interrupted')),'resume only')
        else:
            stage='initial';snapshot(r['initial'],r['caseId'],r['seed'])
            stage='acquisition';preparation(r)
            stage='interrupted';snapshot(r['interrupted'],r['caseId'],r['seed'],True)
            continuity(r['initial'],r['interrupted'])
            need(eq(r['initial']['enemies'],r['interrupted']['enemies']),'defend cannot replace or mutate enemies')
            need(eq(r['initial']['enemies'],r['interrupted']['enemies']),'no accidental victory')
            need(eq([c['serialized'] for c in r['initial']['deck']],r['checkpoint']['players'][0]['deck']),'native checkpoint contains actual master instances')
            need(eq([v['serialized'] for v in r['initial']['relics']],r['checkpoint']['players'][0]['relics']),'native checkpoint contains actual relics')
            need(eq(r['afterMenu'],r['checkpoint']),'no midbattle save rewrite')
            d=r['interruption'];keys(d,{'kind','payment'},'interruption')
            need(d['kind']=='paid-base-defend-state-fixture','disturbance scope')
            p=d['payment'];aid=p['actionId'];need(type(aid) is int and aid>=0,'paid action ID')
            need(eq(p,dict(action='PlayCardAction',state='Finished',actionId=aid,context='GameActionPlayerChoiceContext',
                 history=[dict(id='VOLIBEAR_B02',autoPlay=False,spent=1,index=0,count=1)],afterEnergySpent=[dict(id='VOLIBEAR_B02',amount=1,energy=2)],energyHistory=[1])),'actual native paid disturbance')
            moves=[v for v in events if v['op']=='state-fixture-native-move-to-hand'];need(len(moves)<=1,'bounded explicit hand move')
            if moves:
                move=moves[0];discard=r['interrupted']['piles']['Discard'][0]
                need(events[0]==move and move['id']=='VOLIBEAR_B02' and move['entity']==discard['entity'],'moved base B02 identity/order')
        need(r['resumedCase'] is None and r['route'] is None,'no extra case behavior in S3')
        if r['phase']=='prepare':need(r['resumed'] is None and r['afterLoad'] is None,'A cannot Continue')
        else:
            stage='resumed';snapshot(r['resumed'],r['caseId'],r['seed'])
            need(eq([c['serialized'] for c in r['resumed']['deck']],r['checkpoint']['players'][0]['deck']),'restored actual master serialized fields')
            need(eq([v['serialized'] for v in r['resumed']['relics']],r['checkpoint']['players'][0]['relics']),'restored native relic serialized fields')
            stage='native reload rewrite';wanted,_=native_reload_expected(r['checkpoint'])
            need(eq(r['afterLoad'],wanted),first_difference(wanted,r['afterLoad']))
            if r['phase']=='same':
                stage='same-process reconstruction';need(eq(neutral_snapshot(r['initial']),neutral_snapshot(r['resumed'])),'exact entry-context definition/state roundtrip')
                def refs(s):return {s['runEntity'],s['combatEntity'],s['playerEntity']}|{c['entity'] for c in s['deck']}|{c['entity'] for rows in s['piles'].values() for c in rows}|{v['entity'] for v in s['relics']}|{s['creatureEntity']}|{v['entity'] for v in s['enemies']}
                need(not refs(r['initial'])&refs(r['resumed']),'new native objects required')
        return True
    except (ValueError,KeyError,TypeError,IndexError,AttributeError) as error:
        if errors is not None:errors.append(f'{stage}: {type(error).__name__}: {error}')
        return False

def validate_pair(a,b,xa,xb,a_shared,b_shared):
    if not a_shared or not b_shared or not validate_phase(a,xa) or not validate_phase(b,xb):return False
    try:
        need(a['phase']=='prepare' and b['phase']=='resume' and a['pid']!=b['pid'] and a['token']!=b['token'],'distinct processes/phases')
        for k in ('pair','caseId','mode','seed','userRoot','checkpointPath','assemblyMvid'):need(a[k]==b[k],'pair '+k)
        need(eq(a['afterMenu'],b['checkpoint']),'exact shared native checkpoint')
        need(eq(neutral_snapshot(a['initial']),neutral_snapshot(b['resumed'])),'exact cross-process entry-context roundtrip')
        return True
    except (ValueError,KeyError,TypeError,IndexError,AttributeError):return False

def parse_log(log,expected,errors=None):
    lines=[line.split(PREFIX,1)[1] for line in log.splitlines() if PREFIX in line]
    if len(lines)!=1 or '[Volibear] SHUTDOWN_BEGIN '+expected['token'] not in log or 'SAVE_CATALOG_PROBE_ERROR' in log:
        if errors is not None:errors.append('invalid token-bound native log envelope')
        return None,False
    try:raw=json.loads(lines[0])
    except (ValueError,TypeError) as error:
        if errors is not None:errors.append('JSON: '+str(error))
        return None,False
    return raw,validate_phase(raw,expected,errors)
