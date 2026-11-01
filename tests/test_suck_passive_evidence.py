"""Suck evidence gate mutation tests, not gameplay evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('suck_passive_evidence',ROOT/'tools/suck_passive_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
TOKEN='suck-gate-unit-run'
def sample(case):
    p=dict(schema=1,token=TOKEN,scenario='domain-passive-contract',variant=case,
        acceptance='native-encounter-endturn-controlled-existing-move-not-natural-input',testMode=False,
        version='v0.107.1',commit='59260271',fixture='FossilStalkerNormal',targetType='FossilStalker')
    p.update(gate.expectations(case,'0','1'));return p
def log(p):return gate.MARKER+json.dumps(p)+'\n[Volibear] SHUTDOWN_BEGIN '+TOKEN
class SuckEvidenceTests(unittest.TestCase):
    def test_both_serialized_modes(self):
        for case in gate.VARIANTS:
            self.assertEqual(gate.validate(sample(case),TOKEN,case),[])
            self.assertTrue(gate.check_log(log(sample(case)),TOKEN,case)['passed'])
    def test_fixed_native_multi_hit_and_blocked_control(self):
        off=sample('suck-off');on=sample('suck-on')
        self.assertEqual(off['final']['strength'],10);self.assertEqual(on['final']['strength'],4)
        self.assertEqual(off['final']['playerHp'],66);self.assertEqual(on['final']['playerHp'],66)
        self.assertEqual(off['attacks'][0]['hits'][0][0]['blocked'],16)
        self.assertEqual(off['attacks'][0]['hits'][0][0]['unblocked'],0)
        self.assertEqual([h[0]['unblocked'] for h in off['attacks'][1]['hits']],[7,7])
        self.assertEqual(off['powerHistory'][0]['amount'],6)
    def test_every_expected_leaf_is_checked(self):
        def leaves(obj,path=()):
            if isinstance(obj,dict):
                for k,v in obj.items():yield from leaves(v,path+(k,))
            elif isinstance(obj,list):
                for i,v in enumerate(obj):yield from leaves(v,path+(i,))
            else:yield path,obj
        for case in gate.VARIANTS:
            p=sample(case)
            for path,value in list(leaves(gate.expectations(case,'0','1'))):
                current=p
                for key in path[:-1]:current=current[key]
                current[path[-1]]=not value if type(value) is bool else value+1 if type(value) is int else 'wrong'
                self.assertTrue(gate.validate(p,TOKEN,case),(case,path));current[path[-1]]=value
    def test_no_zero_commit_history_posthooks_or_instance_replacement(self):
        for field in ('powerHistory','events','postHooks'):
            p=sample('suck-on');p[field]=[{}];self.assertTrue(gate.validate(p,TOKEN,'suck-on'))
        p=sample('suck-on');p['sameStrengthIdentity']=False;self.assertTrue(gate.validate(p,TOKEN,'suck-on'))
        p=sample('suck-off');p['eventsAfterBlocked']=1;self.assertTrue(gate.validate(p,TOKEN,'suck-off'))
    def test_actual_attacks_and_moves_cannot_be_omitted(self):
        for case in gate.VARIANTS:
            for field in ('attacks','moves'):
                p=sample(case);p[field]=[];self.assertTrue(gate.validate(p,TOKEN,case))
    def test_invalid_metadata_log_and_shutdown_fail(self):
        for field in ('token','schema','testMode','fixture','version','commit','acceptance'):
            p=sample('suck-on');p[field]='wrong';p['passed']=True;self.assertFalse(gate.check_log(log(p),TOKEN,'suck-on')['passed'])
        good=log(sample('suck-off'))
        for text in ('',good+'\n'+good,good.split('\n')[0],good+'\n[Volibear] DOMAIN_SUCK_ERROR fail',gate.MARKER+'null'):
            self.assertFalse(gate.check_log(text,TOKEN,'suck-off')['passed'])
if __name__=='__main__':unittest.main()
