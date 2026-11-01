"""Gate serialization/mutation tests; these are not gameplay evidence."""
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('card_passive_evidence',ROOT/'tools/card_passive_evidence.py')
gate=importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
TOKEN='card-passive-gate-unit-run'


def sample(case):
    family,mode=case.split('-'); curl=family=='curlup'; on=mode=='on'; e=gate.expectations(case); ids=dict(ownerId='0',targetId='1')
    p=dict(schema=1,token=TOKEN,scenario='domain-passive-contract',variant=case,
        acceptance='native-encounter-card-autoplay-contract-not-natural-input',testMode=False,version='v0.107.1',commit='59260271',
        targetType='LouseProgenitor' if curl else 'PhantasmalGardener',fixture='LouseProgenitorNormal' if curl else 'PhantasmalGardenersElite',
        api='native-encounter-powers+CardCmd.AutoPlay<StrikeIronclad>+PlayerCmd.EndTurn',directStrengthInput=4,directBlockInput=7,
        directStrengthResult=4,directBlockResult=7,attemptsAfterFirst=1,attemptsAfterSecond=1,cardCount=2 if curl else 3)
    for k in ('directBefore','directAfter','beforeCards','firstCard','beforeSecond','secondCard','nextTurn','final'): p[k]=dict(e[k],**ids)
    p['attempts']=[dict(amount=14 if curl else 6,props=4,cardSource=None,before=dict(x,**ids)) for x in e['attempts']]
    if curl:
        p['blockHistory']=([dict(targetId='1',amount=14,props=4)] if not on else [])+[dict(targetId='1',amount=14,props=8)]
        p['powerHistory']=[dict(targetId='1',power='StrengthPower',amount=5,applierId='1')]
        p['rosterAfterTurn']=[dict(id='1',type='LouseProgenitor',slot=None,hp=980 if on else 988,strength=4,enlarge=None)]
        p['moves']=[dict(sourceId='1',type='LouseProgenitor',slot=None,move=m) for m in ('WEB_CANNON_MOVE','CURL_AND_GROW_MOVE')]
    else:
        p['blockHistory']=[dict(targetId='1',amount=6,props=4)]*2 if not on else []
        p['powerHistory']=[]; p['rosterAfterTurn']=[]; p['moves']=[]
        for i,(slot,move) in enumerate(zip(('first','second','third','fourth'),('FLAIL_MOVE','BITE_MOVE','LASH_MOVE','ENLARGE_MOVE')),1):
            p['rosterAfterTurn'].append(dict(id=str(i),type='PhantasmalGardener',slot=slot,
                hp=(980 if on else 988) if i==1 else 992 if on else 1000,strength=4 if i==1 else 2 if i==4 else 0,enlarge=1 if i==4 else 0))
            p['moves'].append(dict(sourceId=str(i),type='PhantasmalGardener',slot=slot,move=move))
    p['batches']=[]
    if on:
        target_ids=['1'] if curl else ['1','2','3','4']
        for i in range(2 if curl else 3):
            p['batches'].append(dict(cardRef='strike-'+str(i+1),baseDamage=4,amount=4,count=1 if i==2 else i+1,targetIds=target_ids,
                hits=[dict(targetId=t,hpLost=4,blocked=0,overkill=0) for t in target_ids]))
    return p


def log(p): return gate.MARKER+json.dumps(p)+'\n[Volibear] SHUTDOWN_BEGIN '+TOKEN


class CardPassiveEvidenceTests(unittest.TestCase):
    def test_four_supported_serialized_cases(self):
        for case in gate.VARIANTS:
            self.assertEqual(gate.validate(sample(case),TOKEN,case),[])
            self.assertTrue(gate.check_log(log(sample(case)),TOKEN,case)['passed'])

    def test_fixed_native_lifecycle_expectations(self):
        self.assertEqual(gate.expectations('curlup-on')['firstCard']['curlup'],0)
        self.assertTrue(gate.expectations('curlup-on')['firstCard']['curled'])
        self.assertEqual(gate.expectations('curlup-on')['final']['strength'],9)
        self.assertEqual(gate.expectations('curlup-on')['final']['block'],14)
        self.assertTrue(gate.expectations('skittish-on')['secondCard']['latch'])
        self.assertFalse(gate.expectations('skittish-on')['nextTurn']['latch'])
        self.assertTrue(gate.expectations('skittish-on')['final']['latch'])
        self.assertEqual(gate.expectations('skittish-on')['final']['hp'],970)
        self.assertEqual(gate.expectations('skittish-off')['final']['hp'],982)

    def test_every_actual_snapshot_field_is_asserted(self):
        for case in gate.VARIANTS:
            p=sample(case)
            snapshots=[p[k] for k in ('directBefore','directAfter','beforeCards','firstCard','beforeSecond','secondCard','nextTurn','final')]
            snapshots += [a['before'] for a in p['attempts']]
            for snapshot in snapshots:
                for field,value in list(snapshot.items()):
                    snapshot[field]=not value if type(value) is bool else value+1 if type(value) is int else 'wrong'
                    self.assertTrue(gate.validate(p,TOKEN,case),(case,field))
                    snapshot[field]=value

    def test_native_callbacks_not_blanket_skipped_or_rearmed(self):
        for case in gate.VARIANTS:
            p=sample(case); p['attempts']=[]; self.assertTrue(gate.validate(p,TOKEN,case))
            p=sample(case); p['attemptsAfterSecond']=2; self.assertTrue(gate.validate(p,TOKEN,case))
        p=sample('curlup-on'); p['firstCard']['curlup']=14; self.assertTrue(gate.validate(p,TOKEN,'curlup-on'))
        p=sample('skittish-on'); p['final']['latch']=False; self.assertTrue(gate.validate(p,TOKEN,'skittish-on'))

    def test_native_direct_move_block_and_strength_are_not_suppressed(self):
        for case in ('curlup-on','curlup-off'):
            p=sample(case); p['blockHistory']=[]; self.assertTrue(gate.validate(p,TOKEN,case))
            p=sample(case); p['powerHistory']=[]; self.assertTrue(gate.validate(p,TOKEN,case))
        p=sample('skittish-on'); p['rosterAfterTurn'][3]['strength']=0
        self.assertTrue(gate.validate(p,TOKEN,'skittish-on'))

    def test_no_cancelled_zero_history_and_actual_moves_required(self):
        p=sample('skittish-on'); p['blockHistory']=[dict(targetId='1',amount=0,props=4)]
        self.assertTrue(gate.validate(p,TOKEN,'skittish-on'))
        for case in gate.VARIANTS:
            p=sample(case); p['moves']=[]; self.assertTrue(gate.validate(p,TOKEN,case))

    def test_domain_lightning_must_be_real_correct_identity_and_count(self):
        for case in ('curlup-on','skittish-on'):
            for field in ('cardRef','baseDamage','amount','count','targetIds','hits'):
                p=sample(case); p['batches'][0][field]=[] if field in ('hits','targetIds') else 'wrong'
                self.assertTrue(gate.validate(p,TOKEN,case))
            p=sample(case); p['batches'][0]['hits'][0]['hpLost']=0
            self.assertTrue(gate.validate(p,TOKEN,case))

    def test_metadata_unsupported_duplicate_error_shutdown_rejected(self):
        for field in ('token','schema','version','commit','testMode','acceptance','api','fixture'):
            p=sample('curlup-on'); p[field]='wrong'; p['passed']=True
            self.assertFalse(gate.check_log(log(p),TOKEN,'curlup-on')['passed'])
        for case in ('curlup-open','skittish-post','ritual-on'):
            self.assertTrue(gate.validate(sample('curlup-on'),TOKEN,case))
        text=log(sample('curlup-on'))
        for bad in ('',text+'\n'+text,text.split('\n')[0],text+'\n[Volibear] DOMAIN_CARD_PASSIVE_ERROR fail',gate.MARKER+'null'):
            self.assertFalse(gate.check_log(bad,TOKEN,'curlup-on')['passed'])


if __name__=='__main__': unittest.main()
