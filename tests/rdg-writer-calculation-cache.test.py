#!/usr/bin/env python3
"""Writer-local dependency cache: exact semantic parity and mutable-result barriers.

All data and authority are disposable. No live Graph owner is modified.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = SourceFileLoader('writer_cache_kernel_fixture', str(ROOT/'tests/rdg-decision-model.test.py')).load_module()
API = SourceFileLoader('writer_cache_portable_fixture', str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
WORK = SourceFileLoader('writer_cache_workflow_fixture', str(ROOT/'tests/rdg-t1-t2-workflow.test.py')).load_module()
M = BASE.M
K = M.for_profile('rdg-decision-v1')
POLICIES = K.POLICIES
ANALYSIS = K.ANALYSIS


class WriterCalculationCache(unittest.TestCase):
    def setUp(self):
        f = BASE.DecisionKernel('test_decision_context_is_local_refs_not_parents_or_completion_dependencies')
        f.setUp()
        f.add_node('D1', 'decision', decisionContextIds=['CTX'],
                   contextNotes={'CTX':'Relevant observed input'})
        f.add_node('CTX', 'context', value='Observed input')
        f.add_node('F1', 'finding', subjectId='D1',
                   subjectSnapshot={'id':'D1','kind':'decision','title':'D1'})
        f.relation('R-D1', 'DRIVES', 'R1', 'D1')
        f.g['edges'].append({'id':'CTX-F1','type':'DEPENDS_ON','from':'CTX','to':'F1','dependencyLevel':'L1'})
        M.validate(f.g)
        self.graph = f.g

    def event(self, idx):
        tx = uuid.uuid5(uuid.NAMESPACE_URL, 'writer-cache-differential-'+str(idx))
        return {'id':str(uuid.uuid5(tx,'requested')),'by':'assistant',
                'note':'Disposable writer test '+str(idx),
                'recordedAt':'2026-11-07T12:00:00+00:00',
                'verifiedTrustReceipt':{'mode':'test-only','transactionId':str(tx)}}

    def apply(self, graph, *commands):
        ops = [{'op':'graph_edit','action':'core_'+command,'data':copy.deepcopy(data),
                'event':self.event(i)} for i,(command,data) in enumerate(commands,1)]
        return K.apply(graph,{'schemaVersion':1,'expectedRevision':graph['revision'],
                             'operations':ops},True)

    def test_relations_cached_as_frozen_values_and_returned_detached(self):
        baseline = POLICIES.relations(self.graph, K)
        with ANALYSIS.read_scope(self.graph):
            first = POLICIES.relations(self.graph, K)
            self.assertEqual(first, baseline)
            first[0]['to'] = 'INJECTED'
            first.append({'id':'BAD','type':'DRIVES','from':'R1','to':'INJECTED'})
            later = POLICIES.relations(self.graph, K)
            self.assertEqual(later, baseline)
            self.assertNotIn(('INJECTED','BAD'), POLICIES.neighbors(self.graph,K,'R1','DRIVES','out'))
            neighbors = POLICIES.neighbors(self.graph,K,'R1','DRIVES','out')
            neighbors.append(('INJECTED','BAD'))
            self.assertEqual(POLICIES.neighbors(self.graph,K,'R1','DRIVES','out'), [('D1','R-D1')])
        self.assertEqual(POLICIES.relations(self.graph,K),baseline)

    def test_writer_fresh_scope_does_not_inherit_older_read_scope(self):
        with ANALYSIS.read_scope(self.graph) as parent_cache:
            POLICIES.neighbors(self.graph,K,'R1','DRIVES','out')  # prime parent
            self.graph['edges'].append({'id':'CTX-R1','type':'CONTEXT_FOR','from':'CTX','to':'R1'})
            # Valid mutation of the SAME Graph object under an unrelated parent scope.
            observed = []
            def inspect(*args,**kwargs):
                observed.extend(POLICIES.neighbors(self.graph,K,'CTX','CONTEXT_FOR','out'))
                self.assertIsNot(ANALYSIS.active_read_cache(self.graph), parent_cache)
                return []
            with patch.object(K,'_native_dependency_impacts_unscoped',side_effect=inspect):
                self.assertEqual(K.native_dependency_impacts(self.graph,self.graph),[])
            self.assertEqual(observed,[('R1','CTX-R1')])
            self.assertIs(ANALYSIS.active_read_cache(self.graph),parent_cache)
        self.assertIsNone(ANALYSIS.active_read_cache(self.graph))

    def test_failing_evaluator_restores_scope_without_retaining_cache(self):
        with patch.object(K,'_native_dependency_impacts_unscoped',side_effect=ValueError('SYNTHETIC_ERROR')):
            with self.assertRaisesRegex(ValueError,'SYNTHETIC_ERROR'):
                K.native_dependency_impacts(self.graph,self.graph)
        self.assertIsNone(ANALYSIS.active_read_cache(self.graph))
        with ANALYSIS.read_scope(self.graph) as old:
            with patch.object(K,'_native_dependency_impacts_unscoped',side_effect=ValueError('SYNTHETIC_ERROR')):
                with self.assertRaisesRegex(ValueError,'SYNTHETIC_ERROR'):
                    K.native_dependency_impacts(self.graph,self.graph)
            self.assertIs(ANALYSIS.active_read_cache(self.graph),old)
        self.assertIsNone(ANALYSIS.active_read_cache(self.graph))

    def test_unscoped_and_scoped_impacts_are_identical_without_mutation(self):
        changed = copy.deepcopy(self.graph)
        changed['objects'][0]['value']='Changed observed input'
        before = copy.deepcopy(self.graph)
        for cosmetic in ((), {'CTX'}):
            expected = K._native_dependency_impacts_unscoped(before,changed,cosmetic_ids=cosmetic)
            self.assertEqual(K.native_dependency_impacts(before,changed,cosmetic_ids=cosmetic),expected)
            self.assertEqual(before,self.graph)
            self.assertEqual(changed['objects'][0]['value'],'Changed observed input')
            self.assertIsNone(ANALYSIS.active_read_cache(changed))

    def test_multi_step_graph_and_event_history_match_without_scope(self):
        commands = [
            ('add',{'entity':{'id':'CTX2','kind':'context','title':'Next observation',
                              'description':'Synthetic','value':'Value two'}}),
            ('edit',{'nodeId':'CTX','changes':{'value':'Changed semantic input'},'cosmetic':False}),
            ('link',{'relation':{'id':'CTX2-F1','type':'DEPENDS_ON','from':'CTX2','to':'F1','dependencyLevel':'L1'}}),
            ('edit',{'nodeId':'D1','changes':{'title':'Cosmetic label'},'cosmetic':True})]
        before = copy.deepcopy(self.graph)
        after,_ = self.apply(before,*commands)
        with patch.object(K,'native_dependency_impacts',K._native_dependency_impacts_unscoped):
            baseline,_ = self.apply(copy.deepcopy(self.graph),*commands)
        self.assertEqual(after,baseline,'Graph, reviews, events, causes and evidence must be identical')
        self.assertEqual(before,self.graph)
        self.assertTrue(any(e.get('dependencyImpacts') for e in after['events']))
        self.assertTrue(K.entities(after)['F1'].get('review',{}).get('required'))

    def test_invalid_multi_step_patch_has_exact_same_failure_and_no_mutation(self):
        commands = [('edit',{'nodeId':'CTX','changes':{'value':'Valid'},'cosmetic':False}),
                    ('link',{'relation':{'id':'NOT-FOUND','type':'DRIVES','from':'MISSING','to':'D1'}})]
        graph = copy.deepcopy(self.graph)
        with self.assertRaises(ValueError) as optimized:
            self.apply(graph,*commands)
        with patch.object(K,'native_dependency_impacts',K._native_dependency_impacts_unscoped):
            with self.assertRaises(ValueError) as baseline:
                self.apply(copy.deepcopy(self.graph),*commands)
        self.assertEqual(str(optimized.exception),str(baseline.exception))
        self.assertEqual(graph,self.graph)

    def test_batch_prepare_exact_parity_including_plan_and_policy_projections(self):
        fixture = API.PortableApplication('test_finding_schema_preflight_retry_and_restart_share_writer')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        app = fixture.app()
        created = app.request({'op':'create','transactionId':str(uuid.uuid4()),
            'path':'working/scoped-writer-'+uuid.uuid4().hex,'role':'working',
            'title':'Disposable writer comparison','scope':'Disposable tests only',
            'coreModel':'rdg-decision-v1','rootReason':'Test integration'})
        ident = created['packages'][0]['packageId']
        req = app.schema('batch',ident)['request']
        req['note']='Disposable deterministic batch parity'
        req['steps']=WORK.WorkflowExperiment.wire_steps()
        timestamp='2026-11-07T12:00:00+00:00'
        baseline_kernel=app.kernel.for_profile('rdg-decision-v1')
        with patch.object(baseline_kernel,'native_dependency_impacts',baseline_kernel._native_dependency_impacts_unscoped):
            baseline=app.prepare(req,recorded_at=timestamp)
        optimized=app.prepare(req,recorded_at=timestamp)
        self.assertEqual(baseline,optimized)
        self.assertTrue(optimized['changes'][ident]['graph']['events'])
        self.assertFalse(any(n['id'] == 'SYNTHETIC_WRITER_PROBE' for n in app.read(ident)['graph']['objects']))

    def test_concurrent_evaluations_have_independent_context(self):
        before=copy.deepcopy(self.graph)
        after=copy.deepcopy(self.graph)
        after['nodes'][0]['description']='Changed root requirement'
        expected=K._native_dependency_impacts_unscoped(before,after)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(K.native_dependency_impacts,before,after) for _ in range(8)]
            self.assertTrue(all(f.result()==expected for f in futures))
        self.assertIsNone(ANALYSIS.active_read_cache(after))


if __name__=='__main__':unittest.main(verbosity=2)
