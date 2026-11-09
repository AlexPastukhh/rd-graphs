#!/usr/bin/env python3
"""Executable user scenarios for the clarified core; no live owners or engine writes."""
import copy
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
M=SourceFileLoader('core_scenarios',str(ROOT/'tools/rdg-core-model.py')).load_module()

class Core(unittest.TestCase):
    def setUp(self):
        self.g=M.blank('rdg-proof','Proof','proof-space','R1','Requests survive restart','Test system, current version')
        self.seq=0
        self.ev=[{'path':'proof/result.json','sha256':'0'*64}]

    def do(self,cmd,**data):
        self.seq+=1
        event={'id':'EV-'+str(self.seq),'type':'requested','by':'assistant','note':'Isolated scenario: '+cmd,
               'verifiedTrustReceipt':{'mode':'test-only'},'evidenceRefs':self.ev}
        self.g,_=M.apply(self.g,{'schemaVersion':1,'expectedRevision':self.g['revision'],
            'operations':[{'op':'graph_edit','action':'core_'+cmd,'data':data,'event':event}]},True)
        return self.g['events'][-1]

    def add(self,i,kind='requirement',**kw):
        n={'id':i,'kind':kind,'title':i,**kw}
        if kind=='requirement': n.update(description=kw.get('description',i),scope='Proof current scope')
        self.do('add',entity=n)

    def edge(self,kind,a,b,**kw):
        ident='E-'+str(self.seq+1)
        self.do('link',edge={'id':ident,'type':kind,'from':a,'to':b,**kw})
        return ident

    def review(self,*ids):
        ns=M.entities(self.g)
        ids=list(ids) or [i for i,n in ns.items() if n.get('review',{}).get('required')]
        if ids:self.do('review',nodeIds=ids,observed={i:ns[i]['revision'] for j in ids for i in M.pins(self.g,j)})

    def shared(self):
        self.add('R2');self.add('A','action');self.add('OUT');self.add('NEXT','action');self.add('END')
        self.add('C','context',description='Network is internal')
        self.edge('DRIVES','R1','A');self.edge('DRIVES','R2','A')
        self.edge('CONTEXT_FOR','C','A');self.edge('INTRODUCES','A','OUT')
        self.edge('DRIVES','OUT','NEXT');self.edge('INTRODUCES','NEXT','END')
        self.review()

    def test_r1_change_detach_adapt_and_new_method(self):
        self.shared();self.add('INDEPENDENT','action');self.edge('DRIVES','R2','INDEPENDENT');self.qualify_output(role='method_correctness');self.review()
        self.do('select',nodeId='A')
        self.review()
        self.do('edit',nodeId='R1',changes={'description':'Now requires encrypted offline storage'})
        ns=M.entities(self.g)
        self.assertTrue(all(ns[i]['review']['required'] for i in ('A','OUT','NEXT','END')))
        self.assertFalse(ns['INDEPENDENT'].get('review',{}).get('required',False))
        link=next(e for e in M.active_edges(self.g) if e['from']=='R1' and e['to']=='A')
        self.do('unlink',edgeId=link['id'])
        self.do('edit',nodeId='A',changes={'description':'Retain general method for R2; offline work split explicitly'})
        self.add('NEW','action');self.edge('DRIVES','R1','NEW')
        self.review()
        self.do('edit',nodeId='R1',changes={'description':'Another literal revision'})
        ns=M.entities(self.g)
        self.assertFalse(ns['A']['review']['required'])
        self.assertTrue(ns['NEW']['review']['required'])
        self.assertEqual([s['id'] for s in M.focused_view(self.g,'A')['situation'] if s['role']=='realized'],['R2'])
        self.assertTrue(any(e.get('archived') for e in self.g['edges']))

    def test_context_and_action_changes_reach_cycle_and_branch(self):
        self.shared();self.edge('DEPENDS_ON','END','C');self.review()
        self.do('edit',nodeId='C',changes={'description':'Network changed'})
        ns=M.entities(self.g)
        self.assertTrue(all(ns[i]['review']['required'] for i in ('C','A','OUT','NEXT','END')))
        self.review('C','A','OUT','NEXT','END')
        self.assertTrue(all(not M.entities(self.g)[i]['review']['required'] for i in ('C','A','OUT','NEXT','END')))
        self.do('edit',nodeId='A',changes={'description':'New implementation'})
        self.assertTrue(M.entities(self.g)['NEXT']['review']['required'])

    def test_loss_reopens_same_r_and_a_preserves_achievement(self):
        self.add('A','action');self.add('OUT');self.edge('DRIVES','R1','A');self.edge('INTRODUCES','A','OUT',origin={'role':'method_correctness'})
        self.review();self.do('select',nodeId='A');self.review()
        with self.assertRaisesRegex(ValueError,'OPEN_OBLIGATIONS'):self.do('complete',nodeId='A')
        self.do('complete',nodeId='OUT');self.do('complete',nodeId='A');self.do('complete',nodeId='R1')
        ids=set(M.entities(self.g));old_event=M.entities(self.g)['OUT']['result']['eventId']
        self.do('falsify',nodeId='OUT')
        self.assertFalse(M.completion_state(self.g)['OUT']['complete'])
        self.assertFalse(M.completion_state(self.g)['A']['complete'])
        self.assertEqual(ids,set(M.entities(self.g)))
        self.assertTrue(any(e['id']==old_event and e['type']=='requirement_achieved' for e in self.g['events']))
        self.review('OUT');self.do('complete',nodeId='OUT');self.review('A','R1');self.do('complete',nodeId='A')
        self.assertTrue(M.completion_state(self.g)['A']['complete'])
        self.assertEqual(2,sum(e['type']=='action_executed' for e in self.g['events']))

    def test_leaf_and_parent_never_complete_from_shape(self):
        self.add('CHILD');self.edge('DERIVES','R1','CHILD');self.review()
        self.assertFalse(M.completion_state(self.g)['CHILD']['complete'])
        self.do('complete',nodeId='CHILD')
        self.assertFalse(M.completion_state(self.g)['R1']['complete'])
        self.assertFalse(M.completion_state(self.g)['R1']['blockers'])
        self.do('complete',nodeId='R1');self.assertTrue(M.completion_state(self.g)['R1']['complete'])

    def test_lost_sub_r_blocks_previously_confirmed_parent_without_falsifying_it(self):
        self.add('CHILD');self.edge('DERIVES','R1','CHILD');self.review()
        self.do('complete',nodeId='CHILD');self.do('complete',nodeId='R1')
        self.do('falsify',nodeId='CHILD')
        state=M.completion_state(self.g)['R1']
        self.assertFalse(state['complete']);self.assertTrue(state['previouslyConfirmed'])
        self.assertTrue(state['reviewRequired']);self.assertEqual(state['truth'],'unknown')
        self.assertEqual(state['blockers'],['CHILD'])
        with self.assertRaisesRegex(ValueError,'REVIEW_OPEN_OBLIGATIONS'):self.review('R1')
        self.do('complete',nodeId='CHILD')
        self.assertFalse(M.completion_state(self.g)['R1']['complete'])
        self.review('R1')
        self.assertTrue(M.completion_state(self.g)['R1']['complete'])

    def test_stale_does_not_falsify_and_can_be_confirmed_without_rework(self):
        self.add('A','action');self.edge('DRIVES','R1','A');self.review();self.do('select',nodeId='A')
        self.do('complete',nodeId='A');old=M.entities(self.g)['A']['result']['eventId']
        self.do('edit',nodeId='R1',changes={'description':'Clarified wording, same actual suitability'})
        state=M.completion_state(self.g)['A']
        self.assertTrue(state['previouslyConfirmed']);self.assertTrue(state['reviewRequired'])
        self.review();self.assertTrue(M.completion_state(self.g)['A']['complete'])
        self.assertEqual(old,M.entities(self.g)['A']['result']['eventId'])

    def canon(self):
        self.add('A','action');self.edge('DRIVES','R1','A')
        def c(i):return {'id':i,'kind':'requirement','text':'Illustrative '+i}
        self.add('K','canon',arguments=[
            {'id':'H','text':'Hard incompatible conjunction','polarity':'against','strength':'hard','condition':{'all':[c('h1'),c('h2')]}},
            {'id':'S','text':'Soft learning cost','polarity':'against','strength':'soft','condition':c('s')},
            {'id':'P','text':'Useful composition','polarity':'for','strength':'soft','condition':{'any':[c('p1'),c('p2')]}}])
        self.edge('CANON_FOR','K','A');self.review()

    def assess(self,second='match'):
        self.do('assess',nodeId='A',matches={'K':{i:{'result':second if i=='h2' else 'match',
                 'reason':'Compared actual meaning and scope','sourceIds':['R1']} for i in ('h1','h2','s','p1','p2')}})

    def test_hard_soft_and_or_unknown_are_distinct(self):
        self.canon();self.assess('unknown')
        v=M.canon_verdict(self.g,'A');self.assertEqual(v['verdict'],'undetermined')
        with self.assertRaisesRegex(ValueError,'ACKNOWLEDGEMENT'):self.do('select',nodeId='A')
        self.assess();self.assertEqual(M.canon_verdict(self.g,'A')['verdict'],'incompatible')
        with self.assertRaisesRegex(ValueError,'HARD_INCOMPATIBLE'):self.do('select',nodeId='A')
        self.assess('no-match');self.do('select',nodeId='A')
        self.assertEqual(M.entities(self.g)['A']['status'],'selected')
        self.assertTrue(any(a['id']=='S' and a['result']=='match' for a in M.canon_verdict(self.g,'A')['arguments']))

    def test_canon_rejects_live_refs_even_nested(self):
        bad={'id':'K','kind':'canon','title':'No live references','arguments':[{'id':'X','text':'x','polarity':'for','strength':'soft',
             'condition':{'id':'L','kind':'context','text':'local','properties':{'ref':{'nodeId':'R1'}}}}]}
        with self.assertRaisesRegex(ValueError,'EXTERNAL_REF'):self.do('add',entity=bad)

    def test_focus_boundaries_origins_and_shared_identity_across_work_scopes(self):
        self.shared();self.add('R3');self.edge('DERIVES','R2','R3')
        self.do('work_graph',id='WG-other',title='Intersecting application',rootIds=['R2'],memberIds=['R2'])
        self.do('join',workGraphIds=['WG-main','WG-other']);self.do('include',nodeId='A',workGraphId='WG-other')
        self.assertEqual(1,sum(n['id']=='A' for n in self.g['nodes']))
        r=M.focused_view(self.g,'R1');self.assertNotIn('OUT',{n['id'] for n in r['entities']})
        a=M.focused_view(self.g,'A');self.assertIn('OUT',a['terminalIds']);self.assertNotIn('NEXT',{n['id'] for n in a['entities']})
        out=M.focused_view(self.g,'OUT');self.assertTrue({'R1','R2','A'} <= {n['id'] for n in out['entities']})
        self.assertEqual(2,len(a['workGraphIds']))
        # Equal titles never merge independent entities.
        self.add('B','action',title='A');self.assertNotEqual(M.entities(self.g)['B']['id'],M.entities(self.g)['A']['id'])

    def test_closed_kinds_cas_authority_and_history_are_not_generic_edits(self):
        with self.assertRaisesRegex(ValueError,'NEW_ENTITY'):self.add('CUSTOM','invented')
        with self.assertRaisesRegex(ValueError,'EDIT_FIELDS'):self.do('edit',nodeId='R1',changes={'result':{'state':'confirmed'}})
        with self.assertRaisesRegex(ValueError,'TRUST'):M.apply(self.g,{'schemaVersion':1,'expectedRevision':1,'operations':[]})
        with self.assertRaisesRegex(ValueError,'REVISION'):M.apply(self.g,{'schemaVersion':1,'expectedRevision':0,'operations':[]},True)
        bad=copy.deepcopy(self.g);bad['nodes'][0]['result']['truth']='true'
        with self.assertRaisesRegex(ValueError,'RESULT_TRUTH'):M.validate(bad)
        self.add('A','action');bad=copy.deepcopy(self.g)
        next(n for n in bad['nodes'] if n['id']=='A')['assessment']={'eventId':'invented','pins':{},'matches':{}}
        with self.assertRaisesRegex(ValueError,'ASSESSMENT_EVENT_REQUIRED'):M.validate(bad)
        self.g['nodes'][0]['policy']={'mode':'protected','authorityPrincipal':'user:owner'}
        with self.assertRaisesRegex(ValueError,'PROTECTED'):self.do('edit',nodeId='R1',changes={'title':'Forbidden'})

    def test_protected_requirement_cannot_be_changed_through_its_method_or_outputs(self):
        self.add('A','action');self.add('OUT');self.edge('DRIVES','R1','A')
        self.g['nodes'][0]['policy']={'mode':'protected','authorityPrincipal':'user:owner'}
        with self.assertRaisesRegex(ValueError,'PROTECTED'):self.do('edit',nodeId='A',changes={'description':'Proxy change'})
        with self.assertRaisesRegex(ValueError,'PROTECTED'):self.edge('INTRODUCES','A','OUT')

    def test_all_selected_outputs_mandatory_and_removal_explicit(self):
        self.add('A','action');self.add('O1');self.add('O2');self.edge('DRIVES','R1','A')
        self.edge('INTRODUCES','A','O1',origin={'role':'method_correctness'});out_edge=self.edge('INTRODUCES','A','O2',origin={'role':'method_correctness'})
        self.review();ev=self.do('select',nodeId='A');self.assertEqual({'O1','O2'},set(ev['outputIds']))
        with self.assertRaisesRegex(ValueError,'DISPOSITION'):self.do('unlink',edgeId=out_edge)
        self.do('unlink',edgeId=out_edge,disposition='O2 remains an independent required result; retained, not cancelled')
        self.assertEqual(M.entities(self.g)['O2']['status'],'active')
        with self.assertRaisesRegex(ValueError,'EVERY_OUTPUT'):self.do('withdraw',nodeId='A',dispositions={})

    def test_compatible_methods_can_coexist_and_exclusion_is_explicit(self):
        self.add('A','action');self.add('B','action');self.edge('DRIVES','R1','A');self.edge('DRIVES','R1','B')
        self.review();self.do('select',nodeId='A');self.do('select',nodeId='B')
        self.assertEqual(2,sum(n.get('status')=='selected' for n in self.g['nodes']))
        with self.assertRaisesRegex(ValueError,'EXCLUDED_ACTIONS_SELECTED'):
            self.do('exclusion_group',id='X',actionIds=['A','B'],reason='A separately established conflict')

    def test_potential_outputs_are_all_accepted_and_necessity_is_explicit(self):
        self.add('A','action');self.add('OUT',status='potential')
        self.edge('DRIVES','R1','A');self.edge('INTRODUCES','A','OUT',origin={'role':'method_correctness'});self.review()
        self.do('select',nodeId='A');self.assertEqual(M.entities(self.g)['OUT']['status'],'active')
        with self.assertRaisesRegex(ValueError,'SHARED_REQUIREMENT_CONSEQUENCES'):
            self.do('requirement_state',nodeId='OUT',state='inactive',disposition='Reconsidered need')
        with self.assertRaisesRegex(ValueError,'NECESSITY_DECISION_ACTION_REQUIRED'):
            self.do('requirement_state',nodeId='OUT',state='inactive',disposition='No linked decision',acceptSharedConsequences=True)
        self.add('CHECK-NEED','action',description='Examine if OUT is needed in this scope')
        self.edge('DRIVES','OUT','CHECK-NEED');self.review()
        with self.assertRaisesRegex(ValueError,'NECESSITY_DECISION_ACTION_NOT_CONFIRMED'):
            self.do('requirement_state',nodeId='OUT',state='inactive',disposition='Decision not performed',
                    acceptSharedConsequences=True,decisionActionId='CHECK-NEED')
        self.do('select',nodeId='CHECK-NEED')
        with self.assertRaisesRegex(ValueError,'NECESSITY_DECISION_ACTION_NOT_CONFIRMED'):
            self.do('requirement_state',nodeId='OUT',state='inactive',disposition='Decision not executed',
                    acceptSharedConsequences=True,decisionActionId='CHECK-NEED')
        self.do('complete',nodeId='CHECK-NEED')
        self.do('requirement_state',nodeId='OUT',state='inactive',
                disposition='Explicitly no longer needed in all uses',
                acceptSharedConsequences=True,decisionActionId='CHECK-NEED')
        self.assertEqual('CHECK-NEED',self.g['events'][-1]['decisionActionId'])
        self.review();self.assertFalse(M.completion_state(self.g)['A']['complete'])
        self.do('complete',nodeId='A');self.assertTrue(M.completion_state(self.g)['A']['complete'])

    def test_findings_and_explanatory_material_do_not_create_obligations(self):
        self.add('I','info',description='Shared explanation')
        self.edge('INFO_FOR','I','R1')
        self.do('finding',nodeId='R1',finding={'id':'F1','type':'risk','text':'Potential future loss'})
        self.assertEqual(1,len(self.g['nodes']));self.assertFalse(M.completion_state(self.g)['R1']['complete'])
        self.do('edit',nodeId='I',changes={'description':'New wording'})
        self.assertFalse(M.entities(self.g)['R1'].get('review',{}).get('required',False))

    def qualify_output(self, role='subgoal', ids=('R1',)):
        edge=next(e for e in M.active_edges(self.g) if e['type']=='INTRODUCES' and e['from']=='A')
        origin={'role':role,**({'requirementIds':list(ids)} if role=='subgoal' else {})}
        self.do('output_origin',edgeId=edge['id'],origin=origin)
        return edge['id']

    def test_output_for_r1_blocks_only_r1_without_expanding_its_own_graph(self):
        self.shared();self.qualify_output();self.review();self.do('select',nodeId='A');self.review()
        state=M.completion_state(self.g)
        self.assertEqual(['OUT'],state['R1']['blockers']);self.assertEqual([],state['R2']['blockers'])
        self.assertEqual(['OUT'],state['A']['blockers'])
        self.assertNotIn('OUT',[n['id'] for n in M.focused_view(self.g,'R1')['entities']])
        child=M.focused_view(self.g,'OUT')
        self.assertIn('R1',[n['id'] for n in child['entities']]);self.assertNotIn('R2',[n['id'] for n in child['entities']])
        self.assertEqual('subgoal',child['originDetails'][0]['role'])
        self.assertFalse(any(e['type']=='DERIVES' for e in self.g['edges']))

    def test_shared_subgoal_and_method_correctness_are_explicit_different_origins(self):
        self.shared();self.qualify_output(ids=('R1','R2'));self.review();self.do('select',nodeId='A');self.review()
        self.assertEqual(['OUT'],M.completion_state(self.g)['R2']['blockers'])
        self.qualify_output(role='method_correctness');self.review()
        detail=M.focused_view(self.g,'OUT')['originDetails'][0]
        self.assertEqual('method_correctness',detail['role']);self.assertEqual(['R1','R2'],detail['requirementIds'])
        self.assertEqual(['OUT'],M.completion_state(self.g)['R1']['blockers'])
        self.assertNotIn('OUT',M.focused_view(self.g,'R2')['terminalIds'])

    def test_lost_qualified_child_requires_its_parent_review_but_preserves_other_goal(self):
        self.shared();self.qualify_output();self.review();self.do('select',nodeId='A');self.review()
        self.do('complete',nodeId='OUT');self.do('complete',nodeId='A')
        self.do('complete',nodeId='R1');self.do('complete',nodeId='R2')
        event=M.entities(self.g)['R1']['result']['eventId'];self.do('falsify',nodeId='OUT')
        state=M.completion_state(self.g)
        self.assertFalse(state['R1']['complete']);self.assertTrue(state['R1']['previouslyConfirmed'])
        self.assertTrue(state['R2']['complete']);self.assertEqual(event,M.entities(self.g)['R1']['result']['eventId'])
        self.assertEqual(['OUT'],state['R1']['blockers'])

    def test_detaching_driver_requires_explicit_origin_reconsideration(self):
        self.shared();edge=self.qualify_output();self.review();self.do('select',nodeId='A');self.review()
        d=next(e for e in M.active_edges(self.g) if e['type']=='DRIVES' and e['from']=='R1' and e['to']=='A')
        self.do('unlink',edgeId=d['id'])
        self.assertEqual([edge],M.completion_state(self.g)['A']['originIssues'])
        with self.assertRaisesRegex(ValueError,'OUTPUT_ORIGIN_DRIVER_REQUIRED'):self.review('A')
        self.do('output_origin',edgeId=edge,origin={'role':'subgoal','requirementIds':['R2']});self.review()
        self.assertEqual([],M.completion_state(self.g)['R1']['blockers'])
        self.assertEqual(['OUT'],M.completion_state(self.g)['R2']['blockers'])
        change=next(e for e in reversed(self.g['events']) if e['type']=='core_output_origin_changed')
        self.assertEqual(['R1'],change['previousRelation']['origin']['requirementIds'])
        self.assertEqual(['R2'],change['newRelation']['origin']['requirementIds'])

    def test_typed_origin_is_supported_at_link_creation_and_checked(self):
        self.add('A','action');self.add('OUT');self.edge('DRIVES','R1','A')
        before=copy.deepcopy(self.g)
        for origin in ({'role':'subgoal','requirementIds':[]},{'role':'subgoal','requirementIds':['A']},
                       {'role':'method_correctness','requirementIds':['R1']},{'role':'invented'}):
            with self.assertRaisesRegex(ValueError,'ORIGIN'):
                self.edge('INTRODUCES','A','OUT',origin=origin)
            self.assertEqual(before,self.g)
        self.edge('INTRODUCES','A','OUT',origin={'role':'subgoal','requirementIds':['R1']})
        self.review();self.do('select',nodeId='A');self.review()
        self.assertEqual(['OUT'],M.completion_state(self.g)['R1']['blockers'])

    def test_origin_cannot_remove_a_protected_parent_through_an_output(self):
        self.shared();self.qualify_output();ns=M.entities(self.g)
        ns['R1']['policy']={'mode':'protected','authorityPrincipal':'owner'}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'PROTECTED_OWNER_GRANT_REQUIRED'):
            self.qualify_output(ids=('R2',))
        self.assertEqual(before,self.g)

    def test_advisory_lens_recommendations_are_typed_and_do_not_change_truth(self):
        self.add('A','action');self.edge('DRIVES','R1','A');self.review()
        notes=[{'lensKey':'review','targetId':'A',
                'text':'Before selecting A, inspect hard/soft canon and unknown applicability.'},
               {'lensKey':'clarify','text':'If the work scope changes, clarify required truth first.'}]
        before=M.completion_state(self.g);revisions={i:n['revision'] for i,n in M.entities(self.g).items()}
        event=self.do('lens_recommendations',recommendations=notes)
        self.assertEqual(event['type'],'core_lens_recommendations_changed')
        self.assertEqual(notes,self.g['lensRecommendations']);self.assertEqual(before,M.completion_state(self.g))
        self.assertEqual(revisions,{i:n['revision'] for i,n in M.entities(self.g).items()})
        for bad in ([{'lensKey':'review','targetId':'UNKNOWN','text':'No target'}],
                    [{'lensKey':'missing key','text':'Wrong name'}],
                    [{'lensKey':'review','text':'  '}],notes+notes[:1]):
            with self.assertRaisesRegex(ValueError,'LENS_RECOMMENDATION'):
                self.do('lens_recommendations',recommendations=bad)
        with self.assertRaisesRegex(ValueError,'LENS_RECOMMENDATIONS_UNCHANGED'):
            self.do('lens_recommendations',recommendations=notes)
        self.g['nodes'][0]['policy']={'mode':'protected','authorityPrincipal':'owner'}
        with self.assertRaisesRegex(ValueError,'PROTECTED'):
            self.do('lens_recommendations',recommendations=[{'lensKey':'review','targetId':'R1',
                'text':'Inspect the protected goal only after approved authority.'}])
        self.g['lensRecommendations'].append({'lensKey':'work','targetId':'R1',
                'text':'Historic protected scope advice must not be removed by proxy.'})
        with self.assertRaisesRegex(ValueError,'PROTECTED'):
            self.do('lens_recommendations',recommendations=notes)

    def test_new_selection_requires_origin_and_selected_link_cannot_hide_obligation(self):
        self.add('A','action');self.add('OUT');self.add('LATE')
        self.edge('DRIVES','R1','A');self.edge('INTRODUCES','A','OUT');self.review()
        with self.assertRaisesRegex(ValueError,'SELECT_OUTPUT_ORIGIN_REQUIRED'):
            self.do('select',nodeId='A')
        edge=next(e for e in M.active_edges(self.g) if e['type']=='INTRODUCES')
        self.do('output_origin',edgeId=edge['id'],origin={'role':'subgoal','requirementIds':['R1']})
        self.review();self.do('select',nodeId='A')
        with self.assertRaisesRegex(ValueError,'SELECTED_OUTPUT_ORIGIN_REQUIRED'):
            self.edge('INTRODUCES','A','LATE')
        self.edge('INTRODUCES','A','LATE',origin={'role':'method_correctness'})
        self.assertIn('LATE',M.completion_state(self.g)['R1']['blockers'])

    def test_repeat_complete_rejects_identical_proof_but_allows_new_evidence(self):
        self.do('complete',nodeId='R1');old=len(self.g['events'])
        with self.assertRaisesRegex(ValueError,'RECONFIRMATION_WITH_SAME_EVIDENCE'):
            self.do('complete',nodeId='R1')
        self.assertEqual(old,len(self.g['events']))
        self.ev=[{'path':'proof/independent.json','sha256':'1'*64}]
        self.do('complete',nodeId='R1')
        self.assertEqual(old+1,len(self.g['events']))

    def test_old_unqualified_core_output_remains_readable_without_invented_parent(self):
        self.shared();self.review()
        with self.assertRaisesRegex(ValueError,'SELECT_OUTPUT_ORIGIN_REQUIRED'):
            self.do('select',nodeId='A')
        action=M.entities(self.g)['A'];action['status']='selected';action['selectedEventId']='OLD-SELECT'
        self.g['events'].append({'id':'OLD-SELECT','type':'action_selected','targetId':'A','by':'user',
                                 'note':'Historic selected Action with unspecified origin'})
        M.validate(self.g)
        self.assertEqual('unspecified',M.focused_view(self.g,'OUT')['originDetails'][0]['role'])
        self.assertEqual([],M.completion_state(self.g)['R1']['blockers'])

if __name__=='__main__':unittest.main()
