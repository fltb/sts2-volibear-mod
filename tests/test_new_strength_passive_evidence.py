"""New-Apply gate mutation tests, not native gameplay evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('new_strength_passive_evidence',ROOT/'tools/new_strength_passive_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
TOKEN='new-apply-gate-unit-run'

def sample(case):
    p=dict(schema=1,token=TOKEN,scenario='domain-passive-contract',variant=case,
        acceptance='controlled-native-new-apply-await-not-natural-input',testMode=False,version='v0.107.1',commit='59260271',
        fixture='SlimesWeak+Ritual3+separate-TwigSlimeS-direct-controls',targetType='LeafSlimeS',controlType='TwigSlimeS')
    p.update(gate.expectations(case,'0','1','2'))
    p['moves']=[dict(sourceId='1',type='LeafSlimeS',move='TACKLE_MOVE'),dict(sourceId='2',type='TwigSlimeS',move='TACKLE_MOVE'),
                dict(sourceId='3',type='LeafSlimeM',move='GOOP_MOVE')]
    return p

def log(p):return gate.MARKER+json.dumps(p)+'\n[Volibear] SHUTDOWN_BEGIN '+TOKEN

class NewStrengthEvidenceTests(unittest.TestCase):
    def test_five_serialized_modes(self):
        for case in gate.VARIANTS:
            self.assertEqual(gate.validate(sample(case),TOKEN,case),[])
            self.assertTrue(gate.check_log(log(sample(case)),TOKEN,case)['passed'])
    def test_zero_amount_is_not_absent_instance_or_no_side_effects(self):
        for case in ('newapply-on','newapply-open'):
            original=sample(case)
            self.assertEqual(original['final']['target']['strengthInstances'],0)
            self.assertIsNone(original['candidateFinal']['ownerId'])
            self.assertEqual(original['events'],[]);self.assertEqual(original['powerHistory'],[]);self.assertEqual(original['postHooks'],[])
            for key,value in (('attached',True),('currentIdentity',True),('ownerId','1'),('amount',3)):
                p=copy.deepcopy(original);p['candidateFinal'][key]=value;self.assertTrue(gate.validate(p,TOKEN,case))
            for field in ('events','powerHistory','postHooks'):
                p=copy.deepcopy(original);p[field]=[{}];self.assertTrue(gate.validate(p,TOKEN,case))
            p=copy.deepcopy(original);p['final']['target']['strengthInstances']=1;self.assertTrue(gate.validate(p,TOKEN,case))
    def test_no_precommit_same_type_nesting_and_postcommit_identity_preserved(self):
        for case in ('newapply-off','newapply-on','newapply-open','newapply-close'):
            p=sample(case);self.assertEqual(p['gates'][0]['nestedStrengthInput'],0)
            p['gates'][0]['nestedStrengthInput']=2;self.assertTrue(gate.validate(p,TOKEN,case))
        p=sample('newapply-post')
        self.assertEqual(p['gates'][0]['before']['target']['strength'],3)
        self.assertEqual(p['final']['target']['strength'],5)
        self.assertEqual([x['kind'] for x in p['events']],['display','increased','applied','display','increased'])
        self.assertTrue(p['candidateFinal']['currentIdentity'])
        p['events'][3]['candidate']['attached']=False;self.assertTrue(gate.validate(p,TOKEN,'newapply-post'))
    def test_every_expected_leaf_is_checked(self):
        def leaves(obj,path=()):
            if isinstance(obj,dict):
                for k,v in obj.items():yield from leaves(v,path+(k,))
            elif isinstance(obj,list):
                for i,v in enumerate(obj):yield from leaves(v,path+(i,))
            else:yield path,obj
        for case in gate.VARIANTS:
            p=sample(case)
            for path,value in list(leaves(gate.expectations(case,'0','1','2'))):
                current=p
                for key in path[:-1]:current=current[key]
                current[path[-1]]=not value if type(value) is bool else value+1 if type(value) is int else 'wrong'
                self.assertTrue(gate.validate(p,TOKEN,case),(case,path))
                current[path[-1]]=value
    def test_first_tick_and_actual_native_execution_required(self):
        for case in gate.VARIANTS:
            for field,value in (('candidateAfterFirst',True),('gates',[]),('candidateBefore',None),('armedAfter',True),('moves',[])):
                p=sample(case);p[field]=value;self.assertTrue(gate.validate(p,TOKEN,case))
    def test_bad_metadata_duplicates_shutdown_and_errors_fail(self):
        for field in ('schema','token','testMode','fixture','version','commit','acceptance'):
            p=sample('newapply-on');p[field]='wrong';p['passed']=True;self.assertFalse(gate.check_log(log(p),TOKEN,'newapply-on')['passed'])
        good=log(sample('newapply-off'))
        for text in ('',good+'\n'+good,good.split('\n')[0],good+'\n[Volibear] DOMAIN_NEW_APPLY_ERROR fail',gate.MARKER+'null'):
            self.assertFalse(gate.check_log(text,TOKEN,'newapply-off')['passed'])

if __name__=='__main__':unittest.main()
