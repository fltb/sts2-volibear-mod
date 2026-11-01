"""Bounded exploration selection contracts, not native 80-encounter execution."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enemy_exploration_evidence as evidence
from test_enemy_exploration_evidence import fixture


class ExplorationSelectionContractTests(unittest.TestCase):
    def loss_exploration(self):
        data, smoke_selection, catalog = fixture()
        selection = evidence.prepare_selection(catalog, mode='explore',
            encounters=['ENCOUNTER.SLIMES_WEAK'], prerequisite=data)
        loss = copy.deepcopy(data['cases'][2])
        loss['caseId'] = selection['cases'][0]['caseId']
        loss['turnBudget'] = 2
        loss['turnSlots'] = loss['turnSlots'][:2]
        data['selection'] = selection
        data['cases'] = [loss]
        return data, selection, catalog

    def test_natural_loss_before_two_complete_cycles_is_valid_exploration(self):
        data, selection, catalog = self.loss_exploration()
        self.assertEqual(selection['cases'][0]['expectedOutcome'], 'ANY')
        self.assertEqual(data['cases'][0]['completedCycles'], 1)
        self.assertEqual(data['cases'][0]['outcome'], 'LOSS')
        self.assertTrue(any(o['status']=='NOT_OBSERVED' for o in data['cases'][0]['opportunities']))
        self.assertEqual(evidence.validate_exploration(data, selection=selection, catalog=catalog, run_id='current'), [])

    def test_early_loss_cannot_be_renamed_budget_or_invent_remaining_moves(self):
        for change in ('budget', 'fake-move'):
            data, selection, catalog = self.loss_exploration()
            case=data['cases'][0]
            if change=='budget':
                case['outcome']='BUDGET_EXIT';case['terminal']['outcome']='BUDGET_EXIT'
            else:
                next(o for o in case['opportunities'] if o['status']=='NOT_OBSERVED')['status']='COMPLETED_NATIVE_HISTORY'
            self.assertTrue(evidence.validate_exploration(data, selection=selection, catalog=catalog, run_id='current'))

    def test_explore_requires_any_and_smoke_keeps_its_exact_terminal_assertions(self):
        data, smoke_selection, catalog=fixture()
        original=copy.deepcopy(smoke_selection)
        selection=evidence.prepare_selection(catalog,mode='explore',prerequisite=data)
        self.assertEqual(smoke_selection,original)
        selection['cases'][0]['expectedOutcome']='BUDGET_EXIT'
        self.assertTrue(evidence.validate_selection(selection,catalog))
        for index in (0,1,2):
            changed=copy.deepcopy(smoke_selection)
            changed['cases'][index]['expectedOutcome']='ANY'
            self.assertTrue(evidence.validate_selection(changed,catalog))

    def test_all_eighty_are_unique_act_roots_without_event_only_encounters(self):
        data,smoke_selection,catalog=fixture()
        selection=evidence.prepare_selection(catalog,mode='explore',prerequisite=data)
        roots=evidence.registered(catalog)
        selected=[c['encounter'] for c in selection['cases']]
        self.assertEqual(len(selected),80)
        self.assertEqual(len(set(selected)),80)
        self.assertEqual(set(selected),set.union(*roots.values()))
        for case in selection['cases']:
            self.assertIn(case['encounter'],roots[case['act']])
            self.assertEqual((case['policy'],case['turnBudget'],case['expectedOutcome']),('end-turn',2,'ANY'))
        self.assertEqual(selection['seed'],'VOLIBEARTEST')
        self.assertEqual(selection['ascension'],0)
        self.assertEqual(selection['prerequisiteToken'],data['token'])


if __name__=='__main__': unittest.main()
