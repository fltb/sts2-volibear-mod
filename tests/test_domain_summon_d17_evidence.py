"""Schema and adversarial rejection tests only; fixtures are not native gameplay evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('domain_summon_d17_evidence',ROOT/'tools/domain_summon_d17_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
TOKEN='summon-d17-unit-token'
def sample(case):
    family=case.split('-')[0];n=gate.COUNTS[case]
    typ='Zapbot' if case=='fabricator-attack-close' else 'Guardbot' if family=='fabricator' else 'ToughEgg' if family=='ovicopter' else 'Wriggler'
    children=[dict(id=str(2+i),type=typ,slot='bot1' if family=='fabricator' else f'egg{5-i}' if family=='ovicopter' else f'wriggler{i+1}',
        hp=18,maxHp=18,block=0,minion=0 if family=='infested' else 1,infested=0,hatch=1 if family=='ovicopter' else 0,
        nextMove=gate.CHILD[typ][2],startStunned=True if family=='infested' else None) for i in range(n)]
    initial='FABRICATE_MOVE' if family=='fabricator' else 'LAY_EGGS_MOVE' if family=='ovicopter' else 'INFECT_MOVE'
    follow='FABRICATING_STRIKE_MOVE' if family=='fabricator' else 'SMASH_MOVE' if family=='ovicopter' else None
    return gate.expected(case,TOKEN,'1','0',2,initial,follow,children)
def log(p):return gate.MARKER+json.dumps(p)+'\n[Volibear] SHUTDOWN_BEGIN '+TOKEN
class SummonD17EvidenceTests(unittest.TestCase):
    def test_all_eleven_serialized_cases(self):
        for case in gate.VARIANTS:
            with self.subTest(case=case):
                self.assertEqual(gate.validate(sample(case),TOKEN,case),[])
                self.assertTrue(gate.check_log(log(sample(case)),TOKEN,case)['passed'])
    def test_mixed_move_does_not_preconsume_future_summon(self):
        close=sample('fabricator-attack-close');opened=sample('fabricator-attack-open')
        self.assertEqual(close['before']['domain'],5);self.assertEqual(close['gates'][0]['domainBefore'],0)
        self.assertFalse(close['gates'][0]['cancelled']);self.assertEqual(len(close['childrenFinal']),1)
        self.assertEqual(close['damage'][0]['hpLost'],18);self.assertEqual(opened['damage'][0]['hpLost'],18)
        self.assertEqual(opened['childrenFinal'],[])
        close['gates'][0]['cancelled']=True;self.assertTrue(gate.validate(close,TOKEN,'fabricator-attack-close'))
    def test_consumed_batch_cannot_replay_after_expiry(self):
        p=sample('fabricator-cancel-close')
        self.assertEqual([r['cancelled'] for r in p['gates']],[True,True])
        self.assertEqual([r['domainBefore'] for r in p['gates']],[5,0])
        for field in ('cancelled','sameBatch'):
            wrong=copy.deepcopy(p);wrong['gates'][1][field]=False;self.assertTrue(gate.validate(wrong,TOKEN,p['variant']))
    def test_actual_create_counter_and_membership_proofs_required(self):
        for case in gate.VARIANTS:
            p=sample(case)
            self.assertEqual(p['final']['nextCreatureId']-p['before']['nextCreatureId'],gate.COUNTS[case])
            p['final']['nextCreatureId']+=1;self.assertTrue(gate.validate(p,TOKEN,case))
        for case in ('fabricator-partial-open','ovicopter-partial-open','infested-partial-open'):
            p=sample(case);p['creates']=[];self.assertTrue(gate.validate(p,TOKEN,case))
            p=sample(case);p['births'][0]['attached']=False;self.assertTrue(gate.validate(p,TOKEN,case))
    def test_committed_children_keep_native_initialization_and_identity(self):
        for case in ('fabricator-partial-open','ovicopter-partial-open','ovicopter-post-open','infested-partial-open','infested-post-open'):
            p=sample(case);self.assertEqual(p['final']['domain'],5)
            self.assertEqual(len(p['childrenFinal']),gate.COUNTS[case])
            if case.startswith('infested'):
                p['childrenFinal'][0]['startStunned']=False
            else:p['childrenFinal'][0]['minion']=0
            self.assertTrue(gate.validate(p,TOKEN,case))
    def test_death_wait_cancellation_cleans_corpse_and_releases_veto(self):
        p=sample('infested-wait-open');self.assertFalse(p['windows'][0]['after']['isEnding'])
        self.assertTrue(p['gates'][-1]['snapshot']['isEnding']);self.assertTrue(p['action']['winResult'])
        self.assertEqual(p['action']['wonCount'],1);self.assertFalse(p['final']['inProgress']);self.assertEqual(p['musicCalls'],0)
        for field,value in (('parentAttached',True),('parentInfested',4),('inProgress',True)):
            wrong=copy.deepcopy(p);wrong['final'][field]=value;self.assertTrue(gate.validate(wrong,TOKEN,p['variant']))
    def test_retired_metadata_is_not_live_domain_cancellation_evidence(self):
        # The real probe may report a retired/closed binding without touching a world.
        # Such a diagnostic must never satisfy these unchanged live D17 contracts.
        for case in gate.VARIANTS:
            for closed, has_payload in ((True, False), (False, True)):
                with self.subTest(case=case, closed=closed):
                    p=sample(case)
                    p['gates'][0]=dict(boundary=p['gates'][0]['boundary'],
                        scope='retired-or-closed-summon',known=True,closed=closed,
                        epoch=4,frameEpoch=5,currentEpoch=5,hasPayload=has_payload,blocked=True)
                    errors=gate.validate(p,TOKEN,case)
                    self.assertTrue(any('result.gates' in error for error in errors))
                    self.assertFalse(gate.check_log(log(p),TOKEN,case)['passed'])

    def test_every_serialized_leaf_is_checked(self):
        def leaves(value,path=()):
            if isinstance(value,dict):
                for key,child in value.items():yield from leaves(child,path+(key,))
            elif isinstance(value,list):
                for index,child in enumerate(value):yield from leaves(child,path+(index,))
            else:yield path,value
        for case in gate.VARIANTS:
            baseline=sample(case)
            for path,value in leaves(baseline):
                p=copy.deepcopy(baseline);cursor=p
                for key in path[:-1]:cursor=cursor[key]
                cursor[path[-1]]=not value if type(value) is bool else value+100 if type(value) in (int,float) else 'wrong'
                with self.subTest(case=case,path=path):self.assertTrue(gate.validate(p,TOKEN,case))
    def test_missing_receipts_extra_creation_duplicate_and_error_fail(self):
        for case in gate.VARIANTS:
            for field in ('gates','windows','moves' if not case.startswith('infested') else 'deathCallbacks'):
                p=sample(case);p[field]=[];self.assertTrue(gate.validate(p,TOKEN,case))
        p=sample('ovicopter-post-open');p['births'].append(copy.deepcopy(p['births'][0]));self.assertTrue(gate.validate(p,TOKEN,p['variant']))
        p=sample('fabricator-attack-close');good=log(p)
        for text in ('',good+'\n'+good,good.split('\n')[0],good+'\n[Volibear] DOMAIN_SUMMON_D17_ERROR x',gate.MARKER+'null'):
            self.assertFalse(gate.check_log(text,TOKEN,p['variant'])['passed'])
        p['passed']=True;p['final']['playerHp']=80;self.assertFalse(gate.check_log(log(p),TOKEN,p['variant'])['passed'])
if __name__=='__main__':unittest.main()
