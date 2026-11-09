#!/usr/bin/env python3
"""State-preserving copies, exact inherited facts, partial capture and boundary pins."""
import copy
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('copy_core_scenario_fixture',str(ROOT/'tests/rdg-portable-model.test.py')).load_module()
P=SourceFileLoader('copy_pure_model',str(ROOT/'tools/rdg-portable-model.py')).load_module()
M=T.M


class Copies(T.Scenario):
    def copied(self,focus=None,source=None,prefix='copy'):
        source=source or self.g;focus=focus or {'kind':'graph'}
        fragment,inventory=P.fragment('source-package',source,focus,M)
        mapping={kind:{old:prefix+'-'+kind+'-'+old for old in ids} for kind,ids in P.definitions(fragment).items()}
        graph,actual=P.copy_graph('source-package',source,focus,mapping,prefix+'-space',prefix+'-graph',M)
        self.assertEqual(actual,inventory)
        return graph,mapping

    def test_full_copy_keeps_choice_results_findings_and_exact_source_events(self):
        self.selected();self.review();self.do('complete',nodeId='OUT');self.do('complete',nodeId='A')
        self.do('finding',nodeId='A',finding={'id':'F1','type':'risk','text':'Synthetic finding'})
        self.do('resolve_finding',nodeId='A',findingId='F1')
        before=copy.deepcopy(self.g);graph,mapping=self.copied();ns=M.entities(graph);aid=mapping['entity']['A']
        self.assertEqual(graph['events'],[])
        self.assertEqual(graph['inheritedHistory'][P.digest(before)]['events'],before['events'])
        self.assertEqual(ns[aid]['selectedEventId'],M.entities(before)['A']['selectedEventId'])
        self.assertEqual(ns[aid]['result'],M.entities(before)['A']['result'])
        self.assertEqual(ns[aid]['qrpe'],M.entities(before)['A']['qrpe'])
        self.assertTrue(M.completion_state(graph)[aid]['complete'])
        self.assertNotEqual(graph['identitySpace'],before['identitySpace']);self.assertEqual(self.g,before)

    def test_copy_of_copy_keeps_original_fact_identity_without_new_execution(self):
        self.selected();self.review();self.do('complete',nodeId='OUT');self.do('complete',nodeId='A')
        first,first_map=self.copied();second,mapping=self.copied(source=first,prefix='second')
        aid=mapping['entity'][first_map['entity']['A']]
        self.assertTrue(M.completion_state(second)[aid]['complete'])
        self.assertEqual(second['events'],[])
        event,subject,_=M.fact_record(second,aid,M.entities(second)[aid]['selectedEventId'])
        self.assertEqual(subject,'A');self.assertEqual(event['targetId'],'A')

    def test_detached_copy_and_later_detachment_keep_selection_witness(self):
        driver=self.selected();self.do('unlink',edgeId=driver)
        graph,mapping=self.copied();aid=mapping['entity']['A']
        self.assertTrue(M.retained_selection(graph,M.entities(graph)[aid]))
        self.assertTrue(M.entities(graph)[aid]['review']['required'])
        self.assertTrue(any(aid in c['memberIds'] for c in M.detached_components(graph)))
        self.setUp();driver=self.selected();graph,mapping=self.copied()
        event={'id':'new-loss','by':'assistant','note':'Synthetic copy dependency loss','verifiedTrustReceipt':{'mode':'test-only'}}
        after,_=M.apply(graph,{'schemaVersion':1,'expectedRevision':graph['revision'],'operations':[
            {'op':'graph_edit','action':'core_unlink','data':{'edgeId':mapping['edge'][driver]},'event':event}]},True)
        self.assertEqual(M.entities(after)[mapping['entity']['A']]['status'],'selected')
        self.assertTrue(M.retained_selection(after,M.entities(after)[mapping['entity']['A']]))

    def test_partial_r_keeps_external_driver_origin_and_observed_pins(self):
        self.add('R2');self.add('A','action');self.add('OUT',status='potential')
        self.link('DRIVES','R1','A');self.link('DRIVES','R2','A')
        self.link('INTRODUCES','A','OUT',origin={'role':'subgoal','requirementIds':['R2']})
        self.review();self.do('select',nodeId='A');self.review()
        observed={i:r for i,r in M.pins(self.g,'A').items()}
        self.do('review',nodeIds=['A'],observed=observed)
        graph,mapping=self.copied({'kind':'requirement','id':'R1'})
        self.assertNotIn('R2',P.definitions(graph)['entity'])
        refs=[r for r in graph['externalRefs'] if r['target']['nodeId']=='R2']
        self.assertTrue(refs);self.assertTrue(all(r['target']['packageId']=='source-package' for r in refs))
        origin=next(e['origin'] for e in graph['edges'] if e['type']=='INTRODUCES')
        self.assertEqual(origin['requirementIds'],[]);self.assertEqual(origin['externalRequirementRefs'][0]['nodeId'],'R2')
        aid=mapping['entity']['A'];self.assertEqual(M.pins(graph,aid),M.entities(graph)[aid]['review']['pins'])
        self.assertEqual(M.output_origin_issues(graph,aid),[])

    def test_canon_fragment_has_real_focus_and_boundary_action_without_fake_r(self):
        self.add('A','action')
        self.add('C','canon',arguments=[{'id':'ARG','text':'Useful pattern','polarity':'for','strength':'soft',
            'condition':{'id':'COND','kind':'requirement','text':'Illustrative requirement'}}])
        self.link('CANON_FOR','C','A')
        graph,mapping=self.copied({'kind':'canon','id':'C'})
        self.assertEqual([n['kind'] for n in graph['objects']],['canon'])
        self.assertEqual(graph['nodes'],[]);self.assertIsNone(graph['rootRequirementId'])
        self.assertEqual(M.detached_components(graph),[])
        self.assertEqual(graph['fragmentFocus'],{'kind':'canon','id':mapping['entity']['C']})
        self.assertEqual(graph['externalRefs'][0]['target']['nodeId'],'A')
        M.validate(graph)

    def test_unresolved_origin_is_inherited_and_cannot_be_cleared_as_plain_review(self):
        self.selected({'role':'subgoal','requirementIds':['R1']});self.do('remove',coordinated=True,nodeIds=['R1'])
        graph,mapping=self.copied();edge=next(e for e in graph['edges'] if e['type']=='INTRODUCES')
        self.assertEqual(edge['origin']['role'],'unresolved');self.assertIn(edge['id'],graph['relationLineage'])
        self.assertTrue(M.output_origin_issues(graph,mapping['entity']['A']))
        M.validate(graph)

    def test_changed_historical_bytes_and_forged_fact_subject_fail(self):
        self.selected();graph,mapping=self.copied();key=P.digest(self.g)
        broken=copy.deepcopy(graph);broken['inheritedHistory'][key]['events'][0]['note']='Rewritten history'
        with self.assertRaisesRegex(ValueError,'INHERITED_HISTORY_BYTES'):M.validate(broken)
        broken=copy.deepcopy(graph);aid=mapping['entity']['A'];event=M.entities(broken)[aid]['selectedEventId']
        broken['factLineage'][aid][event]['sourceId']='R1'
        with self.assertRaisesRegex(ValueError,'SELECTION_EVENT_REQUIRED'):M.validate(broken)

    def test_current_plan_targets_map_and_external_temporal_context_survives(self):
        self.selected();graph,mapping=self.copied()
        plan={'schemaVersion':2,'kind':'temporalPlan','id':'plan','title':'Plan','identitySpace':'old','revision':7,
            'status':'candidate','steps':[{'id':'S1','title':'Local','kind':'action','state':'planned',
                'ref':P.reference('source-package',self.g,'A')},{'id':'S2','title':'Outside','kind':'requirement','state':'planned',
                'ref':P.reference('outside-package',self.g,'R1')}],
            'sequence':[{'before':'S1','after':'S2'}],'branches':[],'timeConstraints':[]}
        before=copy.deepcopy(plan);after,context=P.copy_plan(plan,'source-package','copy-package',graph,mapping)
        self.assertEqual(after['steps'][0]['ref']['nodeId'],mapping['entity']['A'])
        self.assertEqual(after['steps'][0]['ref']['packageId'],'copy-package')
        self.assertEqual(after['steps'][1],before['steps'][1]);self.assertEqual(after['sequence'],before['sequence'])
        self.assertEqual(context['externalContextStepIds'],['S2']);self.assertEqual(before,plan)


    def test_review_cause_resolves_exact_source_fact_after_repeated_copy(self):
        self.selected()
        self.do('edit',nodeId='R1',changes={'title':'Changed dependency'})
        before=copy.deepcopy(self.g);cause=M.entities(before)['A']['review']['causes'][-1]
        self.assertTrue(cause.get('eventId'))
        first,first_map=self.copied()
        aid=first_map['entity']['A'];event,subject,_=M.fact_record(first,aid,cause['eventId'])
        self.assertEqual(subject,'A')
        self.assertEqual(event,next(e for e in before['events'] if e['id']==cause['eventId']))
        second,mapping=self.copied(source=first,prefix='next')
        event2,subject2,_=M.fact_record(second,mapping['entity'][aid],cause['eventId'])
        self.assertEqual(event2,event);self.assertEqual(subject2,subject)

if __name__=='__main__':unittest.main()
