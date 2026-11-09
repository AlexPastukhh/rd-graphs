#!/usr/bin/env python3
"""Checkpoint/CANON user scenarios; pure fixtures, no live owners or human claims."""
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
M=SourceFileLoader('checkpoint_canon_model',str(ROOT/'tools/rdg-core-model.py')).load_module()
A=SourceFileLoader('checkpoint_canon_agent',str(ROOT/'tools/rdg-agent.py')).load_module()

class CheckpointCanon(unittest.TestCase):
    def setUp(self):
        self.g=M.blank('fixture','Fixture','fixture-space','R1','Test result','Isolated test')
        self.seq=0

    def do(self,command,**data):
        self.seq+=1
        event={'id':'EV-'+str(self.seq),'by':'assistant','note':'Isolated '+command,
               'verifiedTrustReceipt':{'mode':'test-only'}}
        self.g,_=M.apply(self.g,{'schemaVersion':1,'expectedRevision':self.g['revision'],
            'operations':[{'op':'graph_edit','action':'core_'+command,'data':data,'event':event}]},True)
        return self.g['events'][-1]

    def load_checkpoint(self):
        self.g=json.loads((ROOT/'tools/rdg-agent-lenses/checkpoint.json').read_text())
        M.validate(self.g)
        return self.g

    def test_five_own_canons_share_seven_real_criteria(self):
        graph=self.load_checkpoint()
        actions=[n for n in graph['nodes'] if n['kind']=='action']
        criteria={n['id'] for n in graph['objects'] if n['kind']=='info'}
        self.assertEqual(len(actions),5)
        self.assertEqual(criteria,{'CP-C'+str(i) for i in range(1,8)})
        self.assertEqual(len([e for e in graph['edges'] if e['type']=='INFO_FOR']),35)
        self.assertFalse(graph['exclusionGroups'])
        for action in actions:
            canon='CANON-'+action['id']
            view=M.focused_view(graph,canon)
            self.assertEqual({n['id'] for n in view['entities'] if n['kind']=='info'},criteria)
            self.assertEqual(M.canon_verdict(graph,action['id'])['verdict'],'comment-only')
        before={n['id']:n['comment'] for n in graph['objects'] if n['kind']=='canon'}
        self.do('edit',nodeId='CANON-CP-A1',changes={'comment':'Произвольное сочетание факторов: даже слово veto не исполняется.'})
        after={n['id']:n['comment'] for n in self.g['objects'] if n['kind']=='canon'}
        self.assertEqual({k:v for k,v in before.items() if k!='CANON-CP-A1'},
                         {k:v for k,v in after.items() if k!='CANON-CP-A1'})

    def test_shared_edit_reaches_five_views_without_criteria_clones(self):
        self.load_checkpoint()
        self.do('edit',nodeId='CP-C3',changes={'title':'Уточнённый стратегический критерий'})
        self.assertEqual(len([x for x in self.g['objects'] if x['id']=='CP-C3']),1)
        for i in range(1,6):
            c=next(n for n in M.focused_view(self.g,'CANON-CP-A'+str(i))['entities'] if n['id']=='CP-C3')
            self.assertEqual(c['title'],'Уточнённый стратегический критерий')

    def test_sequential_routes_need_no_condition_answers_or_xor(self):
        self.load_checkpoint()
        self.do('select',nodeId='CP-A4')
        self.do('select',nodeId='CP-A1')
        ns=M.entities(self.g)
        self.assertEqual(ns['CP-A4']['status'],'selected')
        self.assertEqual(ns['CP-A1']['status'],'selected')
        self.assertFalse(any('assessment' in n for n in self.g['nodes']))
        self.assertFalse(any(e['type']=='core_canon_assessed' for e in self.g['events']))

    def test_new_lens_is_readable_without_owner_and_portable_role_is_normalized(self):
        graph=self.load_checkpoint()
        paper=copy.deepcopy(graph)
        for n in paper['nodes']:
            if n['kind']=='requirement':n['status']='potential'
        M.validate_role(paper,'lens')
        self.assertIn('checkpoint',{e['key'] for e in A.read_lens_catalog()['entries']})
        self.assertTrue(A.inspect_lens('checkpoint')['validated'])

    def test_legacy_veto_survives_until_explicit_recorded_conversion(self):
        self.do('add',entity={'id':'A','kind':'action','title':'Method'})
        self.do('add',entity={'id':'K','kind':'canon','title':'Legacy veto','arguments':[
            {'id':'ARG','text':'Real legacy veto','polarity':'against','strength':'hard',
             'condition':{'id':'BLOCK','kind':'context','text':'Synthetic forbidden situation'}}]})
        self.do('link',edge={'id':'D','type':'DRIVES','from':'R1','to':'A'})
        self.do('link',edge={'id':'C','type':'CANON_FOR','from':'K','to':'A'})
        self.do('assess',nodeId='A',matches={'K':{'BLOCK':{'result':'match','reason':'Fixture','sourceIds':['R1']}}})
        original=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'HARD_INCOMPATIBLE'):
            self.do('select',nodeId='A')
        self.assertEqual(self.g,original)
        conversion={'evaluationMode':'comment-only-v1','arguments':[],'comment':'Свободная оценка: решение остаётся содержательным.'}
        with self.assertRaisesRegex(ValueError,'CANON_MIGRATION_ACKNOWLEDGEMENT_REQUIRED'):
            self.do('edit',nodeId='K',changes=conversion)
        self.assertEqual(self.g,original)
        ev=self.do('edit',nodeId='K',changes=conversion,legacyCanonMigrationAcknowledged=True)
        self.assertEqual(ev['before']['K']['arguments'][0]['strength'],'hard')
        self.do('select',nodeId='A')
        self.assertEqual(M.entities(self.g)['A']['status'],'selected')

if __name__=='__main__':unittest.main()
