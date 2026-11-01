"""Initial-side Plating gate mutation tests, not gameplay evidence."""
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('initial_plating_evidence',ROOT/'tools/initial_plating_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
TOKEN='initial-plating-gate-unit-run'
def sample(case):
    p=dict(schema=1,token=TOKEN,scenario='domain-passive-contract',variant=case,
        acceptance='native-first-side-dispatch-controlled-domain-fixture',testMode=False,
        version='v0.107.1',commit='59260271',fixture='FrogKnightNormal',targetType='FrogKnight')
    p.update(gate.expectations(case,'0','1'));return p
def log(p):return gate.MARKER+json.dumps(p)+'\n[Volibear] SHUTDOWN_BEGIN '+TOKEN
class InitialPlatingEvidenceTests(unittest.TestCase):
    def test_both_serialized_modes(self):
        for case in gate.VARIANTS:
            self.assertEqual(gate.validate(sample(case),TOKEN,case),[])
            self.assertTrue(gate.check_log(log(sample(case)),TOKEN,case)['passed'])
    def test_fixed_initial_block_and_direct_control(self):
        off=sample('plating-initial-off');on=sample('plating-initial-on')
        self.assertEqual(off['afterSource']['block'],15);self.assertEqual(on['afterSource']['block'],0)
        self.assertEqual(off['final']['block'],22);self.assertEqual(on['final']['block'],7)
        self.assertEqual(on['final']['strength'],4);self.assertEqual(on['final']['plating'],15)
        self.assertEqual(on['final']['domain'],5);self.assertEqual(on['nativeMoveCount'],0)
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
    def test_late_or_skipped_callback_and_whole_power_removal_fail(self):
        for case in gate.VARIANTS:
            for field,value in (('callbackObserved',False),('callbackCompleted',False),('callbackRound',2),('callbackSide','Enemy'),('nativeMoveCount',1),('participants',[])):
                p=sample(case);p[field]=value;self.assertTrue(gate.validate(p,TOKEN,case))
            p=sample(case);p['final']['sameSourceIdentity']=False;self.assertTrue(gate.validate(p,TOKEN,case))
            p=sample(case);p['final']['plating']=0;self.assertTrue(gate.validate(p,TOKEN,case))
    def test_positive_histories_and_negative_scope_cannot_be_faked(self):
        for case in gate.VARIANTS:
            for field in ('blockHistory','powerHistory'):
                p=sample(case);p[field]=[];self.assertTrue(gate.validate(p,TOKEN,case))
        p=sample('plating-initial-on');p['blockHistory'].insert(0,dict(targetId='1',amount=0,props=4))
        self.assertTrue(gate.validate(p,TOKEN,'plating-initial-on'))
    def test_bad_metadata_duplicate_error_and_missing_shutdown_fail(self):
        for field in ('schema','token','version','commit','testMode','fixture','acceptance'):
            p=sample('plating-initial-on');p[field]='wrong';p['passed']=True
            self.assertFalse(gate.check_log(log(p),TOKEN,'plating-initial-on')['passed'])
        good=log(sample('plating-initial-off'))
        for text in ('',good+'\n'+good,good.split('\n')[0],good+'\n[Volibear] DOMAIN_INITIAL_PLATING_ERROR fail',gate.MARKER+'null'):
            self.assertFalse(gate.check_log(text,TOKEN,'plating-initial-off')['passed'])
if __name__=='__main__':unittest.main()
