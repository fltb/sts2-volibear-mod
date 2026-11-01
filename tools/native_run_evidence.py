"""Normal native-run evidence, not a numerical 89-card or whole-product acceptance claim.

Modes run continuously in one process. Only three-battle-save -> resume deliberately
crosses a process boundary, exactly to test a real native disk checkpoint.
"""
import json
import re

PREFIX = '[Volibear] NATIVE_RUN_RESULT '
MODES = {'three-battle-save', 'resume', 'death-menu', 'full-run'}
SCOPE = 'normal-native-ui-paid-actions-no-debug-bootstrap-no-game-state-fixtures'
POLICY = 'paid-greedy-v1:power-attack-skill;lowest-hp-target;rest-shop-treasure-map;choice-rng314159'
KINDS = {'ui','native-text-input','menu','character-select','run-start','checkpoint','save-boundary','saved-menu',
         'checkpoint-before-continue','continued','play-request','paid-action','end-turn','turn-start','battle-start','battle-win','battle-end',
         'room','selection-open','selection-return','hand-confirm','hand-choice','map-choice','shop-request','shop-complete','rest-option',
         'rest-complete','relic-pick','relic-return','event-choice','game-over','new-run-after-death'}
# Independent approved starter fees (CARDS.md B01-B04), not DynamicVars or a bot verdict.
STARTER_FEES = {'VOLIBEAR_B01':1,'VOLIBEAR_B02':1,'VOLIBEAR_B03':1,'VOLIBEAR_B04':1}


def native_run_evidence(text, token, expected_mode=None, expected_pair=None):
    errors=[]
    def need(ok, why):
        if not ok: errors.append(why)
    def integer(v): return type(v) is int
    rows=[]
    for line in text.splitlines():
        if PREFIX not in line: continue
        try:
            row=json.loads(line.split(PREFIX,1)[1])
            if isinstance(row,dict) and row.get('token')==token: rows.append(row)
        except (ValueError,TypeError): need(False,'malformed normal-run result')
    need(isinstance(token,str) and bool(token),'nonempty token')
    need(len(rows)==1,'exactly one matching-token result')
    if len(rows)!=1 or not isinstance(token,str) or not token: return {'errors':errors}
    r=rows[0]; mode=r.get('mode')
    need(isinstance(mode,str) and mode in MODES and (expected_mode is None or mode==expected_mode),'requested native-run mode')
    need(isinstance(r.get('pair'),str) and bool(r['pair']) and (expected_pair is None or r['pair']==expected_pair),'requested checkpoint pair')
    need(r.get('schema')==1 and type(r.get('schema'))is int and r.get('scenario')=='native-run','native protocol identity')
    need((r.get('gameVersion'),r.get('gameCommit'))==('0.107.1','59260271'),'pinned game build')
    need(r.get('scope')==SCOPE and r.get('policy')==POLICY,'declared normal-input scope/policy')
    need(r.get('testMode') is False and r.get('steamInitialized') is False and r.get('autoSlayerActive') is False and
         r.get('isolatedProfile') is True and r.get('nativeBootstrap','missing') is None,'isolated normal menu, no Steam/TestMode/AutoSlayer/bootstrap')
    need(integer(r.get('processId')) and r['processId']>0,'real process identity')
    need(r.get('error') is None,'native driver error retained')
    need(not {'passed','verdict','expected'} & r.keys(),'runtime verdict forbidden')
    need('SHUTDOWN_BEGIN '+token in text,'shutdown token')
    for marker in ('NATIVE_RUN_ERROR','Unhandled exception','NullReferenceException','InvalidProgramException','Stack overflow','System.InvalidOperationException'):
        need(marker not in text,'full-window error: '+marker)
    events=r.get('events')
    if not isinstance(events,list): need(False,'native event stream');return {'errors':errors,'observation':r}
    by={k:[] for k in KINDS}; pending=[]; starts={}; won={}; ended={}; paid=[]; first_fee=False
    try:
        for index,event in enumerate(events):
            need(isinstance(event,dict) and type(event.get('seq'))is int and event['seq']==index,'contiguous native event sequence')
            if not isinstance(event,dict): continue
            kind=event.get('kind'); data=event.get('data')
            need(kind in KINDS and isinstance(data,dict),'known structured native event')
            if kind not in KINDS or not isinstance(data,dict): continue
            by[kind].append((index,data))
            need(not {'passed','verdict','expected'} & data.keys(),'event verdict forbidden')
            if kind=='ui': need(data.get('enabled') is True and data.get('visible') is True and isinstance(data.get('path'),str),'native UI qualification')
            if kind=='character-select': need(data.get('id')=='VOLIBEAR_CHARACTER' and data.get('locked')is False and data.get('visible')is True and data.get('api')=='NCharacterSelectButton.Select','actual available character UI')
            if kind=='run-start':
                need(data.get('character')=='VOLIBEAR_CHARACTER' and data.get('runActive')is True and data.get('shouldSave')is True,'normal selected run')
                deck=data.get('deck'); need(isinstance(deck,list) and sorted(c['id'] for c in deck)==sorted(['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']) and all(c['upgrade']==0 and type(c['upgrade'])is int for c in deck),'native unmodified starting deck')
            if kind=='battle-start':
                cid=data['combat']; need(integer(cid) and cid>0 and cid not in starts,'distinct actual combat identity'); starts[cid]=index
                need(data['state']['combatActive']is True and data['state']['character']=='VOLIBEAR_CHARACTER','active native battle')
            if kind=='battle-win':
                cid=data['combat']; need(cid in starts and starts[cid]<index and cid not in won,'native victory after distinct start');won[cid]=(index,data)
                need(data['state']['hp']>0 and data['state']['combatActive']is False,'native victory with living player, combat ended')
            if kind=='battle-end':
                cid=data['combat'];need(cid in starts and cid not in ended,'native end belongs to one battle');ended[cid]=(index,data)
                need(data['state']['combatActive']is False,'native combat end state')
            if kind=='play-request':
                need(not pending and data['combat'] in starts and data['canPlay']is True and data['validTarget']is True,'legal queued input, not direct OnPlay')
                need(integer(data['card']['entity']) and data['card']['entity']>0 and data['card']['pile']=='Hand','actual hand card input')
                if data['card']['id']=='VOLIBEAR_B02': need(data['target']==0,'native Self card uses null target')
                if data['card']['id'] in {'VOLIBEAR_B01','VOLIBEAR_B03','VOLIBEAR_B04'}: need(integer(data['target']) and data['target']>0,'native enemy target selection')
                pending.append((index,data))
            if kind=='paid-action':
                need(bool(pending),'completion needs prior native request')
                if not pending: continue
                _,request=pending.pop(0);entity=request['card']['entity']
                need(data['card']['entity']==entity and data['combat']==request['combat'] and data['before']['energy']==request['energy'],'same requested card/combat/pre-payment energy')
                need(data.get('action')=='PlayCardAction' and data.get('context')=='GameActionPlayerChoiceContext' and data.get('state')=='Finished' and data.get('exception')is None,'real completed game action and native choice context')
                need(data.get('historyCapture') in {'action-completion','before-native-victory-history-clear'},'real history completion/clear boundary')
                primary=[p for p in data['plays'] if p.get('entity')==entity and p.get('autoPlay')is False]
                need(bool(primary),'AutoPlay cannot replace the paid native primary')
                if primary:
                    spent=primary[0]['spent']; need(integer(spent) and spent>=0,'native amount actually spent')
                    need(all(p['id']==request['card']['id'] and p['spent']==spent for p in primary),'same primary native play/resource identity')
                    hooks=[h for h in data['paymentHooks'] if h['card']==entity]
                    need(all(integer(h['amount']) and h['amount']>=0 for h in hooks) and sum(h['amount'] for h in hooks)==spent,'real AfterEnergySpent witness agrees with native play')
                    need(all(integer(x) and x>=0 for x in data['energyHistory']) and sum(data['energyHistory'])>=spent,'actual native EnergySpent history retained')
                    if spent>0:
                        need(bool(hooks) and hooks[0]['energy']==request['energy']-hooks[0]['amount'],'payment boundary debits real energy')
                    if request['card']['id'] in STARTER_FEES and request['cost']==STARTER_FEES[request['card']['id']] and spent==1:
                        first_fee=True
                paid.append(data)
            if kind=='hand-choice': need(data['pendingPaidAction']is True and data['card'] in data['legalVisible'] and data['mode'] in {'SimpleSelect','UpgradeSelect'},'native visible hand choice inside real action')
            if kind=='map-choice':
                need({'row':data['row'],'col':data['col']} in data['legal'],'map input is a native legal adjacent option')
                need(data['fromRow'] is None and data['row']==0 or integer(data['fromRow']) and data['row']>data['fromRow'],'map progresses without debug jump')
            if kind=='shop-request': need(data['stocked']is True and data['enoughGold']is True and data['before']['gold']>=data['cost'],'normal merchant stock/payment qualification')
            if kind=='shop-complete': need(data['after']['gold']==data['before']['gold']-data['cost'],'native shop debits exact purchase price')
            if kind=='event-choice': need(data['path'] in data['options'],'event input belongs to real options')
        need(not pending,'no unfinished paid request concealed')
        for cid,(index,_) in won.items(): need(cid in ended and ended[cid][0]>index,'native win followed by native end')
        starts_in_order=list(starts)
        for a,b in zip(starts_in_order,starts_in_order[1:]): need(a in ended and ended[a][0]<starts[b],'prior combat closes before next begins')
        if mode!='death-menu':
            need(bool(paid) and first_fee,'at least one independently priced 1-energy starter paid normally')
            need(bool(by['end-turn']) and any(d['side']=='Enemy' for _,d in by['turn-start']),'real end-turn and enemy phase')
            need(bool(by['map-choice']) and any(d.get('type')=='NRewardsScreen' for _,d in by['selection-return']),'native victory rewards and normal map navigation')
        if mode!='resume':
            need(bool(by['menu']) and bool(by['character-select']) and bool(by['run-start']) and by['menu'][0][0]<by['character-select'][0][0]<by['run-start'][0][0],'native menu -> selection -> run chronology')
        if mode=='three-battle-save':
            need(r.get('outcome')=='checkpoint-saved' and len(won)>=3,'three actual victories before noncombat checkpoint')
            need(len(by['save-boundary'])==len(by['checkpoint'])==len(by['saved-menu'])==1,'one real save/quit boundary')
            if by['save-boundary']:
                n,state=by['save-boundary'][0]
                need(state['combatActive']is False and state['room']!='CombatRoom' and state['runActive']is True and all(i<n for i,_ in won.values()),'noncombat save after battles, never midcombat restart fixture')
                need(n<by['checkpoint'][0][0]<by['saved-menu'][0][0],'native save checkpoint/menu ordering')
            if by['saved-menu']: need(by['saved-menu'][0][1]=={'runActive':False,'combatActive':False},'save/quit cleans run and combat')
        elif mode=='resume':
            need(r.get('outcome')=='resumed-one-battle' and len(won)>=1,'continued run really plays and wins another battle')
            need(len(by['checkpoint-before-continue'])==len(by['continued'])==1 and not by['run-start'],'resume uses native Continue, not a fresh run')
            if by['continued']: need(by['continued'][0][1]['combatActive']is False and by['continued'][0][0]<min(starts.values(),default=-1),'continued at genuine noncombat boundary before next battle')
        elif mode=='death-menu':
            need(r.get('outcome')=='death-menu-restarted' and len(by['run-start'])==2 and len(by['game-over'])==1 and len(by['new-run-after-death'])==1,'actual death -> menu -> second normal run')
            if by['game-over']:
                n,data=by['game-over'][0];need(data['victory']is False and data['state']['hp']==0,'real loss, not abandonment or fake kill')
                need(by['run-start'][0][0]<n<by['run-start'][1][0] and by['run-start'][0][1]['run']!=by['run-start'][1][1]['run'],'new native run identity after death')
        elif mode=='full-run':
            need(r.get('outcome')=='victory' and len(by['game-over'])==1 and by['game-over'][0][1]['victory']is True,'S09 requires real terminal victory, never early death')
            count=by['run-start'][0][1]['actCount'] if by['run-start'] else 0
            boss_acts={d['state']['act'] for _,d in won.values() if d['state']['roomType']=='Boss'}
            need(integer(count) and count>=3 and boss_acts==set(range(count)),'S09 every reachable act has actual native Boss victory')
        for kind in ('checkpoint','checkpoint-before-continue'):
            for _,data in by[kind]: need(isinstance(data.get('sha256'),str) and bool(re.fullmatch('[0-9a-f]{64}',data['sha256'])) and integer(data.get('bytes')) and data['bytes']>0 and isinstance(data.get('nativeSave'),dict),'actual native disk checkpoint bytes/hash/content')
    except (KeyError,TypeError,ValueError,IndexError,AttributeError) as exc:
        need(False,'malformed native evidence: '+type(exc).__name__)
    coverage=[]
    if by['run-start']: coverage.append('S01-menu')
    if first_fee: coverage.append('S02-paid-input')
    if by['hand-choice'] or any(d.get('pendingPaidAction')is True for _,d in by['selection-open']): coverage.append('S02-card-choice')
    if won and by['map-choice'] and by['selection-return']: coverage.append('S03-reward-map')
    if len(won)>=3: coverage.append('S04-three-battles')
    if mode=='death-menu' and not errors: coverage.append('S05-death-menu-new-run')
    if by['rest-complete']: coverage.append('S06-rest')
    if any('Upgrade' in d.get('type','') and d.get('before',{}).get('deck')!=d.get('after',{}).get('deck') for _,d in by['selection-return']): coverage.append('S06-upgrade')
    if any('Removal' in d.get('kind','') and len(d.get('after',{}).get('deck') or [])+1==len(d.get('before',{}).get('deck') or []) for _,d in by['shop-complete']): coverage.append('S06-merchant-remove')
    shop_relic = any('Relic' in d.get('kind','') and d.get('before',{}).get('relics')!=d.get('after',{}).get('relics') for _,d in by['shop-complete'])
    chest_relic = any(i<j and a.get('relics')!=b.get('relics') and len(b.get('relics') or [])>len(a.get('relics') or []) for i,a in by['relic-pick'] for j,b in by['relic-return'])
    if shop_relic or chest_relic: coverage.append('S06-relic-observed')
    if mode=='full-run' and not errors: coverage.append('S09-terminal-all-acts')
    return {'errors':errors,'observation':r,'observed_coverage':coverage,'not_covered':['S08-clean-install-uninstall','89-card-numerical-contracts'], 'exit_and_stock_leak_gate':'runner-required'}


def native_run_pair_evidence(prepare_text, prepare_token, resume_text, resume_token, pair):
    a=native_run_evidence(prepare_text,prepare_token,'three-battle-save',pair)
    b=native_run_evidence(resume_text,resume_token,'resume',pair)
    errors=['prepare: '+e for e in a['errors']]+['resume: '+e for e in b['errors']]
    try:
        left=a['observation'];right=b['observation']
        if left['processId']==right['processId']:errors.append('S07 requires an actual process restart, not same-process Continue')
        def event(row,kind):return next(e['data'] for e in row['events'] if e['kind']==kind)
        old=event(left,'checkpoint');new=event(right,'checkpoint-before-continue')
        if old!=new:errors.append('native disk checkpoint changed across restart before Continue')
        saved=event(left,'save-boundary');restored=event(right,'continued')
        for key in ('character','seed','floor','act','room','roomType','hp','maxHp','gold','deck','relics'):
            if saved.get(key)!=restored.get(key):errors.append('continued native state differs: '+key)
        if restored.get('combatActive')is not False:errors.append('noncombat checkpoint replayed a battle')
    except (KeyError,TypeError,StopIteration):errors.append('missing actual checkpoint-pair evidence')
    return {'errors':errors,'scope':'S07-one-required-process-restart;not-per-room-or-per-battle-restarts'}
