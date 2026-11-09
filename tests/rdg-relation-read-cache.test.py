#!/usr/bin/env python3
"""Read-scope dependency relation index regression: only disposable Graphs/owners."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = SourceFileLoader('cache_decision_test_fixture', str(ROOT/'tests/rdg-decision-model.test.py')).load_module()
API = SourceFileLoader('cache_portable_test_fixture', str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
M = BASE.M
K = M.for_profile('rdg-decision-v1')
POLICIES = K.POLICIES
ANALYSIS = K.ANALYSIS


class ReadScopeRelationIndex(unittest.TestCase):
    def setUp(self):
        fixture = BASE.DecisionKernel('test_decision_context_is_local_refs_not_parents_or_completion_dependencies')
        fixture.setUp()
        fixture.add_node('D1','decision',decisionContextIds=['CTX'],contextNotes={'CTX':'Observation relevant to choice'})
        fixture.add_node('CTX','context',value='Initial observed input')
        fixture.add_node('F1','finding',subjectId='D1',
                         subjectSnapshot={'id':'D1','kind':'decision','title':'D1'})
        fixture.relation('RD1','DRIVES','R1','D1')
        M.validate(fixture.g)
        self.graph = fixture.g

    def test_full_and_base_relation_sets_match_uncached_evaluator(self):
        for mode in (K, ANALYSIS.BaseContext(K)):
            with self.subTest(base=isinstance(mode, ANALYSIS.BaseContext)):
                with patch.object(ANALYSIS, 'active_read_cache', return_value=None):
                    baseline = POLICIES.relations(self.graph, mode)
                    applications = POLICIES.describe_applications(self.graph, mode)
                with ANALYSIS.read_scope(self.graph):
                    optimized = POLICIES.relations(self.graph, mode)
                    neighbors = POLICIES.neighbors(self.graph, mode, 'R1', ['DRIVES','DECISION_CONTEXT'], 'out')
                    again = POLICIES.relations(self.graph, mode)
                    self.assertIsNot(optimized, again, 'cached relation output must be mutation-isolated')
                    self.assertEqual(neighbors, sorted(set(
                        (e['to'],e['id']) for e in optimized
                        if e['from']=='R1' and e['type'] in ('DRIVES','DECISION_CONTEXT'))))
                self.assertEqual(optimized, baseline)
                self.assertEqual(POLICIES.describe_applications(self.graph, mode), applications)

    def test_repeated_neighbor_lookups_do_not_rebuild_derived_relations(self):
        def count_sources(use_cache):
            with patch.object(K, '_context_sources', wraps=K._context_sources) as observed:
                with ANALYSIS.read_scope(self.graph):
                    if use_cache:
                        for _ in range(8):
                            POLICIES.neighbors(self.graph, K, 'R1', 'DRIVES', 'out')
                    else:
                        with patch.object(ANALYSIS, 'active_read_cache', return_value=None):
                            for _ in range(8):
                                POLICIES.neighbors(self.graph, K, 'R1', 'DRIVES', 'out')
                return observed.call_count
        uncached = count_sources(False)
        indexed = count_sources(True)
        self.assertGreater(uncached, indexed)
        self.assertLessEqual(indexed, 2)

    def test_no_stale_index_when_graph_is_mutated_after_scope(self):
        with ANALYSIS.read_scope(self.graph):
            before = POLICIES.neighbors(self.graph, K, 'CTX', 'CONTEXT_FOR', 'out')
            self.assertEqual(before, [])
        self.graph['edges'].append({'id':'NEW-CONTEXT','type':'CONTEXT_FOR','from':'CTX','to':'D1'})
        with ANALYSIS.read_scope(self.graph):
            after = POLICIES.neighbors(self.graph, K, 'CTX', 'CONTEXT_FOR', 'out')
            self.assertEqual(after, [('D1','NEW-CONTEXT')])
        self.assertEqual(before,[])
        M.validate(self.graph)

    def test_no_base_derived_cache_collision_in_one_scope(self):
        with patch.object(ANALYSIS,'active_read_cache',return_value=None):
            baseline_full = POLICIES.relations(self.graph,K)
            baseline_base = POLICIES.relations(self.graph,ANALYSIS.BaseContext(K))
        with ANALYSIS.read_scope(self.graph):
            full = POLICIES.relations(self.graph,K)
            base = POLICIES.relations(self.graph,ANALYSIS.BaseContext(K))
            self.assertIsNot(full,base)
            self.assertEqual(full,baseline_full)
            self.assertEqual(base,baseline_base)
            self.assertIsNot(full,POLICIES.relations(self.graph,K))
            self.assertIsNot(base,POLICIES.relations(self.graph,ANALYSIS.BaseContext(K)))

    def test_explicit_notes_do_not_trigger_derived_policy_resolution(self):
        self.assertEqual(K.entities(self.graph)['D1']['contextNotes'], {'CTX':'Observation relevant to choice'})
        # Both validation and reconciliation only need the direct, present
        # source for this note; no Finding policy result can change validity.
        with patch.object(ANALYSIS, 'context', side_effect=AssertionError('unnecessary derived resolution')):
            ANALYSIS.validate_notes(self.graph, K)
            self.assertEqual(ANALYSIS.reconcile_notes(self.graph, self.graph, {}, K), set())

    def test_derived_notes_still_validate_against_policy_context(self):
        decision=K.entities(self.graph)['D1']
        decision['decisionContextIds']=[]
        self.graph['edges'].append({'id':'CTX-F1','type':'DEPENDS_ON',
                                    'from':'CTX','to':'F1','dependencyLevel':'L1'})
        self.assertIn('CTX', {row['sourceId'] for row in ANALYSIS.context(self.graph, 'D1', K)})
        with patch.object(ANALYSIS, 'context', wraps=ANALYSIS.context) as derived:
            ANALYSIS.validate_notes(self.graph, K)
            self.assertGreater(derived.call_count, 0)
        self.graph['edges'].pop()
        with self.assertRaisesRegex(ValueError, 'CONTEXT_NOTE_REFERENCE'):
            ANALYSIS.validate_notes(self.graph, K)

    def test_prepare_semantics_identical_with_and_without_cache(self):
        test = API.PortableApplication('test_finding_schema_preflight_retry_and_restart_share_writer')
        test.setUp()
        try:
            pid,_ = test.finding_package()
            app = test.app()
            req = app.schema('core',pid,node_id='R1',command='add')['request']
            req['data']={'entity':{'id':'PROBE','kind':'context','title':'Probe','description':'No publication','value':'Known'}}
            req['note']='Synthetic equal-effect cache test'
            frozen='2026-11-07T12:00:00+00:00'
            analysis=app.kernel.for_profile('rdg-decision-v1').ANALYSIS
            with patch.object(analysis,'active_read_cache',return_value=None):
                old = app.prepare(req,recorded_at=frozen)
            new = app.prepare(req,recorded_at=frozen)
            self.assertEqual(new,old)
            self.assertFalse(any(o['id']=='PROBE' for o in app.read(pid)['graph']['objects']))
        finally:
            test.tearDown()


if __name__ == '__main__':
    unittest.main(verbosity=2)
