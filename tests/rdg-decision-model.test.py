#!/usr/bin/env python3
"""Synthetic executable tests for the Decision v1 kernel; no live owners or storage writes."""
import copy
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
M = SourceFileLoader('decision_kernel_tests', str(ROOT / 'tools/rdg-model-profiles.py')).load_module()
P = SourceFileLoader('policy_portable_tests', str(ROOT / 'tools/rdg-portable-model.py')).load_module()


class DecisionKernel(unittest.TestCase):
    def setUp(self):
        self.seq = 0
        self.g = M.blank('graph-test', 'Decision test', str(uuid.uuid5(uuid.NAMESPACE_URL, 'decision-test-space')),
                         'R1', 'Primary goal', 'Synthetic test scope', core_model='rdg-decision-v1',
                         root_reason='Test primary goal')
        # The scenarios below deliberately use one explicit area, never the process owner.
        self.g['workGraphs']=[{'id':'WG1','title':'Test area','rootIds':['R1'],'memberIds':['R1']}]

    def event(self, label):
        self.seq += 1
        tx = str(uuid.uuid5(uuid.NAMESPACE_URL, 'decision-test-tx-' + str(self.seq)))
        return {'id': str(uuid.uuid5(uuid.UUID(tx), label)), 'type': 'requested', 'by': 'assistant',
                'note': 'Synthetic scenario: ' + label, 'recordedAt': '2026-10-27T12:00:00Z',
                'verifiedTrustReceipt': {'mode': 'test-only', 'transactionId': tx}}

    def do(self, command, data, label=None):
        ev = self.event(label or command)
        if command == 'review':
            import hashlib, json
            ev['reviewPinContext']={
                'packageId':str(uuid.uuid5(uuid.NAMESPACE_URL, 'decision-test-package')),
                'graphRevision':self.g['revision'],
                'sha256':hashlib.sha256(json.dumps(self.g,sort_keys=True,
                    ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()}
        self.g, _ = M.apply(self.g, {'schemaVersion': 1, 'expectedRevision': self.g['revision'],
            'operations': [{'op': 'graph_edit', 'action': 'core_' + command, 'data': data, 'event': ev}]}, True)
        return self.g['events'][-1]

    def add_node(self, ident, kind, **extra):
        base = {'id': ident, 'kind': kind, 'title': ident, 'description': ident, 'revision': 1, **extra}
        if kind == 'requirement':
            base.setdefault('scope', 'Synthetic scope'); base.setdefault('result', {'state': 'open', 'truth': 'unknown'})
        elif kind == 'decision':
            base.setdefault('selectionState', 'unselected'); base.setdefault('result', {'state': 'open', 'truth': 'unknown'})
        elif kind == 'action':
            base.setdefault('actionType', 'task'); base.setdefault('lowLevel', False)
            base.setdefault('targetIds', []); base.setdefault('groupIds', [])
            base.setdefault('result', {'state': 'open', 'truth': 'unknown'})
        elif kind == 'finding':
            base.setdefault('subjectId','R1');base.setdefault('subjectSnapshot',{'id':'R1','kind':'requirement','title':'Primary goal'})
            base.setdefault('findingType','problem');base.setdefault('rationale','Synthetic fixture violation');base.setdefault('evidenceIds',[])
            base.setdefault('disposition',{'code':'unresolved','basis':'','evidenceIds':[]});base.setdefault('dispositionHistory',[])
        elif kind == 'evidence':
            base.setdefault('claim', ident); base.setdefault('scope', 'Synthetic scope')
            base.setdefault('version', 'v1'); base.setdefault('source', 'test fixture')
        decision_kernel = M.for_profile('rdg-decision-v1')
        self.g['nodes' if kind in decision_kernel.NODE_KINDS else 'objects'].append(base)
        if self.g['workGraphs'] and kind != 'action' or self.g['workGraphs'] and kind in ('requirement', 'decision'):
            if ident not in self.g['workGraphs'][0]['memberIds']: self.g['workGraphs'][0]['memberIds'].append(ident)
        return base

    def relation(self, ident, kind, source, target):
        self.g['edges'].append({'id': ident, 'type': kind, 'from': source, 'to': target})

    def group(self, ident, parent, decisions, *, required=True, exclusive=True):
        self.g['decisionGroups'].append({'id': ident, 'parentId': parent, 'title': ident,
            'selectionRequired': required, 'mutuallyExclusive': exclusive,
            'members': [{'id': ident + '-M' + str(i), 'decisionId': decision} for i, decision in enumerate(decisions, 1)]})

    def test_decision_context_is_local_refs_not_parents_or_completion_dependencies(self):
        self.add_node('D1','decision');self.add_node('D2','decision')
        self.add_node('R2','requirement');self.add_node('A1','action')
        self.add_node('CT1','context',value='Actual process circumstance')
        self.add_node('C1','canon',guidance='Quality guidance')
        self.add_node('I1','info',value='Background information')
        self.add_node('EV1','evidence',claim='Observed',scope='test',version='1',source='test')
        self.relation('RD1','DRIVES','R1','D1')
        before=copy.deepcopy(self.g)
        baseline_support=M.support_state(self.g)
        baseline_completion=M.completion_state(self.g)
        self.do('edit',{'nodeId':'D1','changes':{
            'decisionContextIds':['R2','D2','CT1','A1'],'contextNotes':{i:'Material fixture input' for i in ('R2','D2','CT1','A1')}},'cosmetic':False})
        decision=M.entities(self.g)['D1']
        self.assertEqual(decision['decisionContextIds'],['R2','D2','CT1','A1'])
        self.assertEqual(self.g['edges'],before['edges'],'context adds no semantic edge')
        self.assertEqual(M.support_state(self.g),baseline_support)
        self.assertEqual(M.completion_state(self.g)['R1']['blockers'],
                         baseline_completion['R1']['blockers'])
        focus=M.focused_view(self.g,'D1')
        self.assertEqual({n['id'] for n in focus['entities']},
                         {'R1','D1','R2','D2','CT1','A1'})
        self.assertEqual([e['id'] for e in focus['edges']],['RD1'],
                         'do not invent a structural Decision-to-Decision edge')
        self.assertEqual(before['nodes'][0]['id'],self.g['nodes'][0]['id'])
        for refs in (['D1'],['missing'],['R2','R2'],['A-EXTERNAL'],['']):
            snapshot=copy.deepcopy(self.g)
            with self.assertRaisesRegex(ValueError,'DECISION_CONTEXT_REFS'):
                self.do('edit',{'nodeId':'D1','changes':{'decisionContextIds':refs},'cosmetic':False})
            self.assertEqual(self.g,snapshot,'invalid edit is atomic')
        # Newly created Decisions use the same refs contract.
        self.do('add',{'entity':{'id':'D3','kind':'decision','title':'D3','description':'Candidate',
            'decisionContextIds':['R2','CT1'],'contextNotes':{'R2':'Requirement basis','CT1':'Process fact'}}})
        self.assertEqual(M.entities(self.g)['D3']['decisionContextIds'],['R2','CT1'])

    def test_context_semantic_change_requests_review_without_cascade(self):
        self.add_node('D1','decision',decisionContextIds=['CT1'])
        self.add_node('CT1','context',value='Current process fact')
        self.relation('E1','DRIVES','R1','D1')
        before=M.support_state(self.g)
        self.assertEqual(M.pins(self.g,'D1')['CT1'],1)
        self.do('edit',{'nodeId':'CT1',
            'changes':{'value':'Changed actual context'},'cosmetic':False})
        self.assertTrue(M.entities(self.g)['D1']['review']['required'])
        self.assertEqual(M.support_state(self.g),before)
        self.assertEqual(M.entities(self.g)['D1']['selectionState'],'unselected')
        self.assertFalse(any(e['type']=='branch_cancelled' for e in self.g['events']))

    def test_decision_context_copy_remaps_local_refs_and_captures_context_objects(self):
        from importlib.machinery import SourceFileLoader
        portable=SourceFileLoader('decision_context_portable',str(ROOT/'tools/rdg-portable-model.py')).load_module()
        self.add_node('D1','decision',decisionContextIds=['R2','D2','CT1'])
        self.add_node('D2','decision');self.add_node('R2','requirement')
        self.add_node('CT1','context',value='Current condition')
        self.relation('RD1','DRIVES','R1','D1')
        M.validate(self.g)
        snapshot=copy.deepcopy(self.g)
        captured,inventory=portable.fragment('source-package',self.g,
            {'kind':'decision','id':'D1'},M,False)
        self.assertEqual(set(inventory['entityIds']),{'R1','D1','R2','D2','CT1'})
        refs=portable.graph_references(captured)
        self.assertEqual({r['value'] for r in refs if 'decisionContextIds' in r['path']},
                         {'R2','D2','CT1'})
        mapping={namespace:{key:'new-'+key for key in values}
                 for namespace,values in portable.definitions(captured).items()}
        clone=portable.remap_graph(captured,mapping)
        self.assertEqual(M.entities(clone)['new-D1']['decisionContextIds'],
                         ['new-R2','new-D2','new-CT1'])
        M.validate(clone)
        self.assertEqual(self.g,snapshot,'read/capture/remap do not mutate source')

    def test_decision_process_context_is_not_part_of_reusable_template(self):
        from importlib.machinery import SourceFileLoader
        portable=SourceFileLoader('decision_paper_context',str(ROOT/'tools/rdg-portable-model.py')).load_module()
        self.add_node('D1','decision',decisionContextIds=['R1'])
        M.validate(self.g)
        original=copy.deepcopy(self.g)
        for role in ('ready','lens'):
            with self.assertRaisesRegex(ValueError,'DECISION_CONTEXT_PROCESS_ONLY'):
                M.validate_role(self.g,role)
        template=portable.decision_template(self.g)
        self.assertNotIn('decisionContextIds',M.entities(template)['D1'])
        M.validate_role(template,'ready')
        M.validate_role(template,'lens')
        self.assertEqual(self.g,original)

    def test_decision_context_removal_clears_refs_without_dangling_ids(self):
        self.add_node('D1','decision',decisionContextIds=['R2','CT1'])
        self.add_node('R2','requirement')
        self.add_node('CT1','context',value='Actual process fact')
        M.validate(self.g)
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'REMOVE_REQUIRES_COORDINATOR'):
            self.do('remove',{'nodeIds':['CT1']})
        self.assertEqual(self.g,before)
        ev=self.event('delete_context');patch={'schemaVersion':1,'expectedRevision':self.g['revision'],
            'operations':[{'op':'graph_edit','action':'core_remove',
                'data':{'nodeIds':['CT1']},'event':ev}]}
        after,_=M.apply(self.g,patch,True,coordinated=True)
        M.validate(after)
        self.assertEqual(M.entities(after)['D1']['decisionContextIds'],['R2'])
        self.assertTrue(M.entities(after)['D1']['review']['required'])
        self.assertEqual(self.g,before)
        self.assertIn('D1',after['events'][-1]['nodeIds'])

    def test_work_graph_color_is_optional_and_history_records_before_after(self):
        # Old work-area records without colorKey remain valid and readable.
        M.validate(self.g)
        original_revision = M.entities(self.g)['R1']['revision']
        created = self.do('work_graph', {'workGraph': {'id': 'WG2', 'title': 'Storage work',
            'rootIds': ['R1'], 'memberIds': ['R1'], 'colorKey': 'teal'}})
        self.assertEqual(created['workGraphChange'], {'action': 'created', 'workGraphId': 'WG2',
            'title': 'Storage work', 'before': None,
            'after': {'title': 'Storage work', 'rootIds': ['R1'], 'memberIds': ['R1'], 'colorKey': 'teal'}})
        after_create_revision = M.entities(self.g)['R1']['revision']
        self.assertGreaterEqual(after_create_revision, original_revision)
        updated = self.do('work_graph', {'workGraph': {'id': 'WG2', 'title': 'Storage and migrations',
            'rootIds': ['R1'], 'memberIds': ['R1'], 'colorKey': 'amber'}})
        self.assertEqual(updated['workGraphChange']['action'], 'updated')
        self.assertEqual(updated['workGraphChange']['before'], {'title': 'Storage work',
            'rootIds': ['R1'], 'memberIds': ['R1'], 'colorKey': 'teal'})
        self.assertEqual(updated['workGraphChange']['after']['colorKey'], 'amber')
        self.assertEqual(M.entities(self.g)['R1']['revision'], after_create_revision,
                         'a color/title-only edit is metadata on the area, not an edit to its members')
        before = copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError, 'WORK_GRAPH'):
            self.do('work_graph', {'workGraph': {'id': 'WG2', 'title': 'Invalid color',
                'rootIds': ['R1'], 'memberIds': ['R1'], 'colorKey': 'ultraviolet'}})
        self.assertEqual(self.g, before)

    def test_process_creation_has_no_implicit_working_area(self):
        graph=M.blank('graph-new','New process',str(uuid.uuid4()),'R0','Whole process',
            'Process scope',core_model='rdg-decision-v1',root_reason='Explicit process reason')
        M.validate(graph)
        self.assertEqual(graph['workGraphs'],[])
        self.assertEqual(graph['rootCauses'][0]['requirementId'],'R0')

    def test_add_uses_only_explicit_area_and_keeps_whole_process_distinct(self):
        self.g['workGraphs'].append({'id':'WG2','title':'Second area','rootIds':['R1'],'memberIds':['R1']})
        scopes=copy.deepcopy(self.g['workGraphs'])
        self.do('add',{'entity':{'id':'D-PROCESS','kind':'decision','title':'Process alternative','description':'Outside all areas'},
            'initialRelations':[{'id':'RD-PROCESS','type':'DRIVES','from':'R1','to':'D-PROCESS'}]})
        self.assertEqual(self.g['workGraphs'],scopes)
        self.do('add',{'entity':{'id':'D-AREA','kind':'decision','title':'Area alternative','description':'In WG2 only'},
            'workGraphId':'WG2','initialRelations':[{'id':'RD-AREA','type':'DRIVES','from':'R1','to':'D-AREA'}]})
        self.assertEqual(self.g['workGraphs'][0],scopes[0])
        self.assertEqual(self.g['workGraphs'][1]['memberIds'],['R1','D-AREA'])
        self.assertNotIn('D-PROCESS',self.g['workGraphs'][1]['memberIds'])
        # Existing saved areas keep their membership; no hidden main-area behavior survives.
        self.g['workGraphs'][0]['title']='Main work'
        saved=copy.deepcopy(self.g['workGraphs'])
        self.do('add',{'entity':{'id':'R-PROCESS','kind':'requirement','title':'Another goal','description':'Outside areas','scope':'Process'}})
        self.assertEqual(self.g['workGraphs'],saved)

    def test_overlapping_exclusive_groups_are_independent_and_visibility_is_view_only(self):
        for ident in ('D1', 'D2', 'D3'): self.add_node(ident, 'decision')
        self.group('G1', 'R1', ['D1', 'D2'])
        self.group('G2', 'R1', ['D2', 'D3'])
        M.validate(self.g)
        self.do('select', {'nodeId': 'D1'})
        visibility = {x['groupId']: x for x in M.group_visibility(self.g)}
        self.assertEqual(visibility['G1']['hiddenIds'], ['D2'])
        self.assertEqual(visibility['G2']['hiddenIds'], [])
        self.assertEqual(M.group_visibility(self.g, True)[0]['hiddenIds'], [])
        before = copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError, 'DECISION_GROUP_CONFLICT'):
            self.do('select', {'nodeId': 'D2'})
        self.assertEqual(self.g, before)

    def test_shared_requirement_retains_other_enabled_root_basis(self):
        self.add_node('R2', 'requirement'); self.add_node('R3', 'requirement'); self.add_node('D1', 'decision')
        self.g['rootCauses'].append({'id': 'RC2', 'requirementId': 'R2', 'reason': 'Second independent goal', 'enabled': True})
        self.g['workGraphs'][0]['rootIds'].append('R2')
        self.relation('E1', 'DERIVES', 'R1', 'R3'); self.relation('E2', 'DERIVES', 'R2', 'R3')
        self.group('G1', 'R3', ['D1'])
        self.g['nodes'][-1]['selectionState'] = 'selected'
        M.validate(self.g)
        self.do('root_cause', {'cause': {'id': 'RC1', 'requirementId': 'R1', 'reason': 'Test primary goal', 'enabled': False}})
        active = set(M.support_state(self.g)['activeIds'])
        self.assertIn('R3', active); self.assertIn('D1', active)
        self.assertEqual(M.entities(self.g)['D1']['selectionState'], 'selected')

    def test_one_decision_identity_is_driven_by_two_goals_and_keeps_remaining_basis(self):
        self.add_node('R2', 'requirement'); self.add_node('D1', 'decision')
        self.g['rootCauses'].append({'id': 'RC2', 'requirementId': 'R2',
            'reason': 'Second independent goal', 'enabled': True})
        self.g['workGraphs'][0]['rootIds'].append('R2')
        self.relation('E1', 'DRIVES', 'R1', 'D1')
        self.relation('E2', 'DRIVES', 'R2', 'D1')
        M.entities(self.g)['D1']['selectionState'] = 'selected'
        M.validate(self.g)
        self.assertEqual(sum(n['id'] == 'D1' for n in self.g['nodes']), 1)
        self.assertEqual(M.support_state(self.g)['basisById']['D1'],
                         ['relation:E1', 'relation:E2'])
        first = next(c for c in self.g['rootCauses'] if c['requirementId'] == 'R1')
        self.do('root_cause', {'cause': {**first, 'enabled': False}})
        state = M.support_state(self.g)
        self.assertIn('D1', state['activeIds'])
        self.assertEqual(state['basisById']['D1'], ['relation:E2'])
        self.assertEqual(M.entities(self.g)['D1']['selectionState'], 'selected')

    def test_one_requirement_identity_is_introduced_by_two_decisions_and_survives_one_loss(self):
        self.add_node('R2', 'requirement'); self.add_node('R3', 'requirement')
        self.add_node('D1', 'decision'); self.add_node('D2', 'decision')
        self.g['rootCauses'].append({'id': 'RC2', 'requirementId': 'R2',
            'reason': 'Second independent goal', 'enabled': True})
        self.g['workGraphs'][0]['rootIds'].append('R2')
        self.relation('E1', 'DRIVES', 'R1', 'D1')
        self.relation('E2', 'DRIVES', 'R2', 'D2')
        self.relation('E3', 'INTRODUCES', 'D1', 'R3')
        self.relation('E4', 'INTRODUCES', 'D2', 'R3')
        M.entities(self.g)['D1']['selectionState'] = 'selected'
        M.entities(self.g)['D2']['selectionState'] = 'selected'
        M.validate(self.g)
        self.assertEqual(sum(n['id'] == 'R3' for n in self.g['nodes']), 1)
        self.assertEqual(M.support_state(self.g)['basisById']['R3'],
                         ['relation:E3', 'relation:E4'])
        first = next(c for c in self.g['rootCauses'] if c['requirementId'] == 'R1')
        self.do('root_cause', {'cause': {**first, 'enabled': False}})
        state = M.support_state(self.g)
        self.assertNotIn('D1', state['activeIds'])
        self.assertIn('D2', state['activeIds'])
        self.assertIn('R3', state['activeIds'])
        self.assertEqual(state['basisById']['R3'], ['relation:E4'])
        self.assertEqual(M.entities(self.g)['D1']['selectionState'], 'unselected')
        self.assertEqual(M.entities(self.g)['D2']['selectionState'], 'selected')

    def test_losing_last_basis_cascades_selection_but_preserves_confirmed_fact(self):
        self.add_node('R2', 'requirement'); self.add_node('R3', 'requirement'); self.add_node('D1', 'decision')
        self.add_node('EVID1', 'evidence')
        self.g['workGraphs'][0]['rootIds'].append('R2')
        self.relation('E1', 'DERIVES', 'R1', 'R2')
        self.group('G1', 'R2', ['D1'])
        self.relation('E2', 'INTRODUCES', 'D1', 'R3')
        tx = str(uuid.uuid5(uuid.NAMESPACE_URL, 'old-decision-result'))
        result_event = {'id': str(uuid.uuid5(uuid.UUID(tx), 'completed')), 'type': 'decision_completed',
            'transactionId': tx, 'recordedAt': '2026-10-26T12:00:00Z', 'by': 'assistant',
            'nodeIds': ['D1'], 'basis': 'Observed in the synthetic fixture', 'evidenceIds': ['EVID1']}
        self.g['events'].append(result_event)
        M.entities(self.g)['D1']['selectionState'] = 'selected'
        M.entities(self.g)['D1']['result'] = {'state': 'confirmed', 'truth': 'true', 'eventId': result_event['id']}
        M.validate(self.g)
        self.do('root_cause', {'cause': {'id': 'RC1', 'requirementId': 'R1', 'reason': 'Test primary goal', 'enabled': False}})
        d = M.entities(self.g)['D1']
        self.assertEqual(d['selectionState'], 'unselected')
        self.assertEqual(d['result'], {'state': 'confirmed', 'truth': 'true', 'eventId': result_event['id']})
        self.assertTrue(any(e['id'] == result_event['id'] for e in self.g['events']))
        self.assertFalse(M.support_state(self.g)['activeIds'])
        self.assertTrue(any(e['type'] == 'branch_cancelled' and 'D1' in e['nodeIds'] for e in self.g['events']))

    def test_rootless_cycle_does_not_support_itself(self):
        self.add_node('R2', 'requirement'); self.add_node('R3', 'requirement')
        self.g['rootCauses'][0]['enabled'] = False
        self.relation('E1', 'DERIVES', 'R2', 'R3'); self.relation('E2', 'DERIVES', 'R3', 'R2')
        M.validate(self.g)
        self.assertEqual(M.support_state(self.g)['activeIds'], [])

    def test_connected_add_is_atomic_and_rejects_unrelated_initial_relation(self):
        entity = {'id': 'A1', 'kind': 'action', 'title': 'Run check', 'description': 'Run check',
                  'revision': 1, 'result': {'state': 'open', 'truth': 'unknown'}, 'actionType': 'task',
                  'lowLevel': False, 'targetIds': [], 'groupIds': []}
        before_revision = self.g['revision']
        self.do('add', {'entity': entity, 'location': 'graph', 'workGraphId': 'WG1',
                        'initialRelations': [{'id': 'RA1', 'type': 'REQUIRES_ACTION', 'from': 'R1', 'to': 'A1'}]})
        self.assertEqual(self.g['revision'], before_revision + 1)
        self.assertIn('A1', M.entities(self.g))
        self.assertEqual(M.active_edges(self.g)[0]['id'], 'RA1')
        self.assertEqual(self.g['events'][-1]['relationIds'], ['RA1'])
        bad = copy.deepcopy(self.g)
        tx = str(uuid.uuid5(uuid.NAMESPACE_URL, 'bad-add-tx'))
        event = {'id': str(uuid.uuid5(uuid.UUID(tx), 'bad-add')), 'type': 'requested', 'by': 'assistant',
                 'note': 'Bad connected add', 'recordedAt': '2026-10-27T12:00:00Z',
                 'verifiedTrustReceipt': {'mode': 'test-only', 'transactionId': tx}}
        entity2 = {**entity, 'id': 'A2'}
        with self.assertRaisesRegex(ValueError, '^INITIAL_RELATION_UNRELATED$'):
            M.apply(bad, {'schemaVersion': 1, 'expectedRevision': bad['revision'], 'operations': [{
                'op': 'graph_edit', 'action': 'core_add', 'data': {'entity': entity2, 'location': 'graph',
                'initialRelations': [{'id': 'bad-edge', 'type': 'REQUIRES_ACTION', 'from': 'R1', 'to': 'A1'}]},
                'event': event}]}, True)
        self.assertNotIn('A2', M.entities(bad))

    def test_action_and_requirement_completion_use_evidence_and_real_obligations(self):
        self.add_node('A1', 'action')
        self.add_node('EVID1', 'evidence')
        self.relation('RA1', 'REQUIRES_ACTION', 'R1', 'A1')
        M.validate(self.g)
        with self.assertRaisesRegex(ValueError, 'OBLIGATIONS_OPEN'):
            self.do('complete', {'nodeId': 'R1', 'basis': 'Goal observed', 'evidenceIds': ['EVID1']})
        self.do('complete', {'nodeId': 'A1', 'basis': 'Action observed', 'evidenceIds': ['EVID1']})
        self.assertTrue(M.completion_state(self.g)['A1']['complete'])
        self.assertFalse(M.completion_state(self.g)['R1']['blockers'])
        self.do('complete', {'nodeId': 'R1', 'basis': 'Goal observed', 'evidenceIds': ['EVID1']})
        self.assertTrue(M.completion_state(self.g)['R1']['complete'])

    def test_completed_decision_requires_reopen_before_direct_withdraw(self):
        self.add_node('D1', 'decision'); self.add_node('EVID1', 'evidence'); self.group('G1', 'R1', ['D1'])
        self.do('select', {'nodeId': 'D1'})
        self.do('complete', {'nodeId': 'D1', 'basis': 'Decision result observed', 'evidenceIds': ['EVID1']})
        before = copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError, 'DECISION_REOPEN_REQUIRED'):
            self.do('withdraw', {'nodeId': 'D1'})
        self.assertEqual(self.g, before)

    def test_decide_acceptance_requires_actual_outcome_and_applies_it_atomically(self):
        self.add_node('D1', 'decision'); self.add_node('EVID1', 'evidence')
        action = self.add_node('A1', 'action', actionType='decide_acceptance', targetIds=['D1'])
        self.relation('RA1', 'REQUIRES_ACTION', 'R1', 'A1'); self.group('G1', 'R1', ['D1'])
        M.validate(self.g)
        before = copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError, 'ACTION_OUTCOME_REQUIRED'):
            self.do('complete', {'nodeId': 'A1', 'basis': 'Acceptance checked', 'evidenceIds': ['EVID1']})
        self.assertEqual(self.g, before)
        self.do('complete', {'nodeId': 'A1', 'basis': 'Acceptance checked', 'evidenceIds': ['EVID1'], 'decisionOutcome': 'selected'})
        self.assertEqual(M.entities(self.g)['D1']['selectionState'], 'selected')
        self.assertEqual(self.g['events'][-1]['actionResult'], {'decisionId': 'D1', 'decisionOutcome': 'selected'})
        self.assertTrue(M.completion_state(self.g)['A1']['complete'])

    def test_select_decision_action_emits_atomic_selection_events_for_all_targets(self):
        for ident in ('D1','D2'):self.add_node(ident,'decision')
        self.add_node('A1','action',actionType='select_decision',targetIds=['D1','D2'])
        self.add_node('EVID1','evidence')
        self.group('G1','R1',['D1','D2'],required=False,exclusive=False)
        self.relation('REQACT','REQUIRES_ACTION','R1','A1')
        self.do('complete',{'nodeId':'A1','basis':'Both choices deliberately selected',
            'evidenceIds':['EVID1']})
        self.assertEqual([M.entities(self.g)[i]['selectionState'] for i in ('D1','D2')],
                         ['selected','selected'])
        completion=self.g['events'][-1]
        events=[e for e in self.g['events'] if e['type']=='decision_selected']
        self.assertEqual([e['nodeIds'] for e in events],[['D1'],['D2']])
        self.assertTrue(all(e['transactionId']==completion['transactionId'] and
            e['operationActionId']=='A1' for e in events))
        self.assertEqual(completion['type'],'action_executed')
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'NO_CHANGE'):
            self.do('complete',{'nodeId':'A1','basis':'Duplicate application',
                'evidenceIds':['EVID1']})
        self.assertEqual(self.g,before)

    def test_remove_requires_coordinator_and_cleans_memberships_targets_and_support(self):
        self.add_node('D1', 'decision')
        self.add_node('R2', 'requirement')
        self.add_node('A1', 'action', targetIds=['D1'], groupIds=['G1'])
        self.group('G1', 'R1', ['D1'])
        self.relation('E1', 'INTRODUCES', 'D1', 'R2')
        self.relation('E2', 'REQUIRES_ACTION', 'R1', 'A1')
        self.do('select', {'nodeId': 'D1'})
        before = copy.deepcopy(self.g)
        ev = self.event('remove-decision')
        patch = {'schemaVersion': 1, 'expectedRevision': self.g['revision'], 'operations': [{
            'op': 'graph_edit', 'action': 'core_remove', 'data': {'nodeIds': ['D1']},
            'event': ev}]}
        with self.assertRaisesRegex(ValueError, 'REMOVE_REQUIRES_COORDINATOR'):
            M.apply(self.g, patch, True)
        self.assertEqual(self.g, before)
        after, _ = M.apply(self.g, patch, True, coordinated=True)
        M.validate(after)
        self.assertNotIn('D1', M.entities(after))
        self.assertFalse(after['decisionGroups'])
        self.assertFalse(any(e['id'] == 'E1' for e in after['edges']))
        self.assertEqual(M.entities(after)['A1']['targetIds'], [])
        self.assertEqual(M.entities(after)['A1']['groupIds'], [])
        self.assertNotIn('R2', M.support_state(after)['activeIds'])
        self.assertTrue(M.entities(after)['R2'].get('review',{}).get('required',False))
        self.assertTrue(any(s['sourceId']=='D1' and s['targetId']=='R2' and s['status']=='disabled' for s in after['dependencyAutomaticStates'].values()))
        self.assertTrue(any(e['type'] == 'removed' and 'D1' in e['nodeIds'] for e in after['events']))
        self.assertTrue(any(e['type'] == 'branch_cancelled' and 'R2' in e['nodeIds'] for e in after['events']))
        self.assertEqual(after['revision'], before['revision'] + 1)

    def test_locked_completion_and_cascade_fail_atomically(self):
        self.add_node('D1','decision'); self.add_node('D2','decision')
        self.add_node('R2','requirement'); self.add_node('EVID1','evidence')
        self.group('G1','R1',['D1'])
        self.group('G2','R2',['D2'])
        self.relation('INTRO','INTRODUCES','D1','R2')
        self.do('select',{'nodeId':'D1'})
        self.do('select',{'nodeId':'D2'})
        self.g['nodes'][0]['locks']={'complete':{'mode':'hard','principals':['owner:key'],
             'message':'Only owner can complete the primary goal'}}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'OBJECT_OPERATION_LOCK_REQUIRED'):
            self.do('complete',{'nodeId':'R1','basis':'Observed','evidenceIds':['EVID1']})
        self.assertEqual(self.g,before)
        M.entities(self.g)['D2']['locks']={'withdraw':{'mode':'hard','principals':['owner:key'],
             'message':'Protected decision withdrawal'}}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'OBJECT_OPERATION_LOCK_REQUIRED'):
            self.do('withdraw',{'nodeId':'D1'})
        self.assertEqual(self.g,before)

    def policy(self, ident='POL1', pattern='direct', operations=None, watch='definition', version=1):
        return {'id':ident,'version':version,'name':'Test policy '+ident,
                'description':'A named, immutable test policy','status':'active',
                'pattern':pattern,'sourceKinds':['decision'] if pattern=='parentDecisionContext' else ['context'],
                'targetKinds':['requirement','action'] if pattern=='parentDecisionContext' else ['decision','requirement','action'],
                'rules':[{'id':'RULE1','name':'Observed change','watch':watch,
                          'operations':operations or ['changed'],'enabled':True}]}

    def binding(self, target='D1', source='CT1', parent=None, ident='B1'):
        return {'id':ident,'policyId':'POL1','policyVersion':1,
                'sourceId':source if parent is None else None,'targetId':target,
                'parentId':parent,'enabled':True}

    def test_named_policy_direct_trigger_and_pinned_version(self):
        self.add_node('D1','decision');self.add_node('CT1','context',value='100')
        self.relation('DR1','DRIVES','R1','D1')
        self.do('policy_change',{'action':'policy_save','value':self.policy()})
        self.do('policy_change',{'action':'binding_save','value':self.binding()})
        self.assertFalse(M.entities(self.g)['D1'].get('review',{}).get('required',False))
        ev=self.do('edit',{'nodeId':'CT1','changes':{'value':'1000'},'cosmetic':False})
        hits=[x for x in ev['dependencyImpacts'] if x.get('origin')=='policy']
        self.assertEqual(len(hits),1)
        hit=hits[0];self.assertEqual((hit['policyId'],hit['policyVersion'],hit['ruleId'],hit['triggerOperation']),
                                   ('POL1',1,'RULE1','changed'))
        self.assertEqual(hit['matchedParticipants'],{'sourceId':'CT1','targetId':'D1'})
        second=self.policy(version=2);second['name']='Test policy version 2'
        self.do('policy_change',{'action':'policy_save','value':second})
        self.assertEqual(self.g['dependencyBindings'][0]['policyVersion'],1)
        self.assertEqual(self.g['events'][-2]['dependencyImpacts'][-1]['policyVersion'],1)
        M.validate(self.g)

    def test_named_policy_parent_decision_context_added_changed_removed(self):
        self.add_node('D1','decision',decisionContextIds=['CT1'])
        self.add_node('R2','requirement');self.add_node('CT1','context',value='old')
        self.add_node('CT2','context',value='new')
        self.relation('DR1','DRIVES','R1','D1');self.relation('DR2','INTRODUCES','D1','R2')
        policy=self.policy(pattern='parentDecisionContext',operations=['added','removed','changed'])
        self.do('policy_change',{'action':'policy_save','value':policy})
        self.do('policy_change',{'action':'binding_save','value':self.binding(target='R2',parent='D1')})
        def matching(ev):return [i for i in ev.get('dependencyImpacts',[]) if i.get('origin')=='policy']
        ev=self.do('edit',{'nodeId':'CT1','changes':{'value':'updated'},'cosmetic':False})
        self.assertEqual([(i['triggerOperation'],i['sourceId']) for i in matching(ev)],[('changed','CT1')])
        self.assertEqual(matching(ev)[0]['matchedParticipants']['parentId'],'D1')
        ev=self.do('edit',{'nodeId':'D1','changes':{'decisionContextIds':['CT1','CT2'],'contextNotes':{'CT2':'Additional process fact'}},'cosmetic':False})
        self.assertEqual([(i['triggerOperation'],i['sourceId']) for i in matching(ev)],[('added','CT2')])
        ev=self.do('edit',{'nodeId':'D1','changes':{'decisionContextIds':['CT2']},'cosmetic':False})
        self.assertEqual([(i['triggerOperation'],i['sourceId']) for i in matching(ev)],[('removed','CT1')])
        self.assertTrue(M.entities(self.g)['R2']['review']['required'])

    def test_multiple_policy_rules_preserve_independent_stale_causes(self):
        self.add_node('D1','decision');self.add_node('CT1','context',value='a')
        policy=self.policy();policy['rules'].append({'id':'RULE2','name':'Second rule',
            'watch':'definition','operations':['changed'],'enabled':True})
        self.do('policy_change',{'action':'policy_save','value':policy})
        self.do('policy_change',{'action':'binding_save','value':self.binding()})
        ev=self.do('edit',{'nodeId':'CT1','changes':{'value':'b'},'cosmetic':False})
        self.assertEqual({r['ruleId'] for r in ev['dependencyImpacts'] if r.get('policyId')=='POL1'},
                         {'RULE1','RULE2'})
        self.assertEqual(M.entities(self.g)['D1']['review']['causeEventIds'][-1],ev['id'])

    def test_invalid_named_policy_binding_never_changes_graph(self):
        self.add_node('R2','requirement');self.add_node('CT1','context',value='1')
        self.do('policy_change',{'action':'policy_save','value':self.policy(pattern='parentDecisionContext')})
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'POLICY_BINDING_INAPPLICABLE'):
            self.do('policy_change',{'action':'binding_save','value':self.binding(target='R2',parent='R1')})
        self.assertEqual(self.g,before)
        with self.assertRaisesRegex(ValueError,'POLICY_VERSION_CONFLICT'):
            self.do('policy_change',{'action':'policy_save','value':self.policy(pattern='parentDecisionContext')})
        self.assertEqual(self.g,before)

    def test_policy_direct_scope_added_and_removed_ids(self):
        self.add_node('TARGET','requirement');self.add_node('R2','requirement')
        policy=self.policy(watch='directScope',operations=['added','removed'])
        policy['sourceKinds']=['requirement']
        self.do('policy_change',{'action':'policy_save','value':policy})
        self.do('policy_change',{'action':'binding_save','value':self.binding(target='TARGET',source='R1')})
        self.assertFalse(M.entities(self.g)['TARGET'].get('review',{}).get('required',False))
        ev=self.do('link',{'relation':{'id':'E-TARGET','type':'DERIVES','from':'R1','to':'R2'}})
        hits=[i for i in ev.get('dependencyImpacts',[]) if i.get('policyId')=='POL1']
        self.assertEqual([(i['triggerOperation'],i['matchedParticipants'].get('memberId')) for i in hits],
                         [('added','R2')])
        self.do('review',{'nodeId':'TARGET','observed':M.pins(self.g,'TARGET'),'basis':'Added child evaluated'})
        ev=self.do('unlink',{'edgeId':'E-TARGET'})
        hits=[i for i in ev.get('dependencyImpacts',[]) if i.get('policyId')=='POL1']
        self.assertEqual([(i['triggerOperation'],i['matchedParticipants'].get('memberId')) for i in hits],
                         [('removed','R2')])

    def test_policy_parent_relation_loss_does_not_corrupt_saved_binding(self):
        self.add_node('D1','decision',decisionContextIds=['CTX'])
        self.add_node('R2','requirement');self.add_node('CTX','context',value='a')
        self.relation('E-RD','DRIVES','R1','D1')
        self.relation('E-PARENT','INTRODUCES','D1','R2')
        self.do('policy_change',{'action':'policy_save','value':self.policy(pattern='parentDecisionContext')})
        self.do('policy_change',{'action':'binding_save','value':self.binding(target='R2',parent='D1')})
        self.do('unlink',{'edgeId':'E-PARENT'})
        self.assertEqual(self.g['dependencyBindings'][0]['parentId'],'D1')
        self.assertEqual(self.g['dependencyBindings'][0]['enabled'],False)
        self.assertEqual(self.g['dependencyBindings'][0]['reasonCode'],'applicability')
        M.validate(self.g)
        ev=self.do('edit',{'nodeId':'CTX','changes':{'value':'b'},'cosmetic':False})
        self.assertFalse(any(i.get('policyId')=='POL1' for i in ev.get('dependencyImpacts',[])),
                         'disconnected parent context cannot spuriously invalidate old structural child')

    def test_policy_invalid_operation_watch_and_locked_bindings_atomic(self):
        self.add_node('D1','decision');self.add_node('CT1','context',value='a')
        invalid=self.policy(operations=['added'])
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'POLICY_RULE_OPERATION_WATCH'):
            self.do('policy_change',{'action':'policy_save','value':invalid})
        self.assertEqual(self.g,before)
        with self.assertRaisesRegex(ValueError,'POLICY_PRESET_OPERATION_WATCH'):
            self.do('policy_change',{'action':'preset_save','value':{'id':'PRESET1','name':'Broken',
               'sourceKinds':['context'],'watch':['definition'],'operations':['removed']}})
        self.assertEqual(self.g,before)
        self.do('policy_change',{'action':'policy_save','value':self.policy()})
        M.entities(self.g)['CT1']['locks']={'link':{'mode':'hard','principals':['owner:exclusive'],
                                          'message':'No dependency registration'}}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'OBJECT_OPERATION_LOCK_REQUIRED'):
            self.do('policy_change',{'action':'binding_save','value':self.binding()})
        self.assertEqual(self.g,before)

    def test_portable_template_strips_context_policy_applications_but_keeps_catalog(self):
        self.add_node('D1','decision',decisionContextIds=['CT1'])
        self.add_node('R2','requirement');self.add_node('CT1','context',value='process-only')
        self.relation('RD','DRIVES','R1','D1');self.relation('DR','INTRODUCES','D1','R2')
        direct=self.policy(ident='POL-REQ')
        direct['sourceKinds']=['requirement']
        self.do('policy_change',{'action':'policy_save','value':direct})
        self.do('policy_change',{'action':'policy_save','value':self.policy(ident='POL-CTX',pattern='parentDecisionContext')})
        self.do('policy_change',{'action':'binding_save','value':{**self.binding(target='R2',source='R1',ident='B-REQ'),
            'policyId':'POL-REQ'}})
        self.do('policy_change',{'action':'binding_save','value':{**self.binding(target='R2',parent='D1',ident='B-CTX'),
            'policyId':'POL-CTX'}})
        template=P.decision_template(self.g)
        self.assertEqual([b['id'] for b in template['dependencyBindings']],['B-REQ'])
        self.assertEqual(len(template['dependencyPolicies']),2)
        self.assertNotIn('decisionContextIds',next(n for n in template['nodes'] if n['id']=='D1'))
        M.validate_role(template,'ready')

    def test_portable_decision_insert_keeps_named_policy_definitions_and_bindings(self):
        self.add_node('R2','requirement')
        direct=self.policy()
        direct['sourceKinds']=['requirement']
        self.do('policy_change',{'action':'policy_save','value':direct})
        self.do('policy_change',{'action':'binding_save','value':self.binding(target='R2',source='R1')})
        template=P.decision_template(self.g)
        template['rootCauses'][0]['id']='RC-READY'
        template['workGraphs'][0]['id']='WG-READY'
        target=M.blank('target','Target process',str(uuid.uuid5(uuid.NAMESPACE_URL,'target-space')),
                       'R-TARGET','New root','New scope',core_model='rdg-decision-v1',
                       root_reason='Target root')
        ev=self.event('insert-policy-ready')
        merged,scope=P.decision_insert(target,template,ev,'WG-INSERTED',M.for_profile('rdg-decision-v1'))
        self.assertEqual(scope,'WG-INSERTED')
        self.assertEqual(len(merged['dependencyPolicies']),1)
        self.assertEqual(len(merged['dependencyBindings']),1)
        self.assertEqual(merged['dependencyBindings'][0]['policyId'],'POL1')
        M.validate(merged)

    def test_implicit_structural_stale_one_hop_not_recursive(self):
        self.add_node('D1','decision');self.add_node('R2','requirement');self.add_node('D2','decision')
        self.relation('RD','DRIVES','R1','D1');self.relation('DR','INTRODUCES','D1','R2')
        self.relation('RD2','DRIVES','R2','D2')
        M.entities(self.g)['D1']['selectionState']='selected'
        M.entities(self.g)['D2']['selectionState']='selected'
        M.validate(self.g)
        self.do('edit',{'nodeId':'R1','changes':{'description':'Root changed'},'cosmetic':False})
        impacts=self.g['events'][-1]['dependencyImpacts']
        self.assertEqual([(r['sourceId'],r['dependentId']) for r in impacts],[('R1','D1')])
        self.assertTrue(M.entities(self.g)['D1']['review']['required'])
        self.assertFalse(M.entities(self.g)['R2'].get('review',{}).get('required',False))
        self.assertFalse(M.entities(self.g)['D2'].get('review',{}).get('required',False))
        self.assertEqual(M.entities(self.g)['D1']['selectionState'],'selected')
        self.do('edit',{'nodeId':'D1','changes':{'description':'Decision changed'},'cosmetic':False})
        self.assertEqual([(r['sourceId'],r['dependentId']) for r in self.g['events'][-1]['dependencyImpacts']],
                         [('D1','R2')])
        self.assertFalse(M.entities(self.g)['D2'].get('review',{}).get('required',False))

    def test_decision_context_legacy_changes_stale_decision_and_only_direct_child(self):
        self.add_node('D1','decision',decisionContextIds=['CT1'])
        self.add_node('R2','requirement');self.add_node('D2','decision')
        self.add_node('CT1','context',value='Load 100')
        self.relation('RD','DRIVES','R1','D1');self.relation('DR','INTRODUCES','D1','R2')
        self.relation('RD2','DRIVES','R2','D2')
        M.entities(self.g)['D1']['selectionState']='selected'
        M.entities(self.g)['D2']['selectionState']='selected'
        original=M.support_state(self.g)
        self.do('edit',{'nodeId':'CT1','changes':{'value':'Load 100000'},'cosmetic':False})
        impacts=self.g['events'][-1]['dependencyImpacts']
        self.assertEqual({r['dependentId'] for r in impacts},{'D1','R2'})
        self.assertTrue(M.entities(self.g)['D1']['review']['required'])
        self.assertTrue(M.entities(self.g)['R2']['review']['required'])
        self.assertFalse(M.entities(self.g)['D2'].get('review',{}).get('required',False))
        self.assertEqual(M.support_state(self.g),original)

    def test_configurable_dependency_rule_save_update_convert_and_remove(self):
        self.add_node('D1','decision',decisionContextIds=['CT1'])
        self.add_node('CT1','context',value='Old condition')
        self.relation('RD','DRIVES','R1','D1')
        before=copy.deepcopy(self.g)
        bad={'id':'DEP1','type':'DEPENDS_ON','from':'CT1','to':'D1',
             'dependencyPurpose':'decisionContext','dependencyRule':{'preset':'custom','watch':[]}}
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_RULE_SCHEMA'):
            self.do('dependency_rule',{'mode':'save','relation':bad,'convertLegacy':'CT1'})
        self.assertEqual(self.g,before)
        rule={'id':'DEP1','type':'DEPENDS_ON','from':'CT1','to':'D1',
              'dependencyPurpose':'decisionContext','dependencyRule':{'preset':'L1','watch':['definition']}}
        self.do('dependency_rule',{'mode':'save','relation':rule,'convertLegacy':'CT1'})
        self.assertNotIn('CT1',M.entities(self.g)['D1']['decisionContextIds'])
        self.assertEqual([e['id'] for e in self.g['edges'] if e['type']=='DEPENDS_ON'],['DEP1'])
        self.assertEqual(len([i for i in self.g['events'][-1]['dependencyImpacts'] if i['dependentId']=='D1']),1)
        self.do('review',{'nodeId':'D1','observed':M.pins(self.g,'D1'),'basis':'Initial context checked'})
        self.do('edit',{'nodeId':'CT1','changes':{'value':'New load'},'cosmetic':False})
        self.assertEqual([r['edgeId'] for r in self.g['events'][-1]['dependencyImpacts']],['DEP1'])
        self.assertTrue(M.entities(self.g)['D1']['review']['required'])
        self.do('dependency_rule',{'mode':'save','relation':{
            **rule,'dependencyRule':{'preset':'custom','watch':['definition','directScope']}}})
        self.assertEqual(next(e for e in self.g['edges'] if e['id']=='DEP1')['dependencyRule']['preset'],'custom')
        self.do('dependency_rule',{'mode':'remove','edgeId':'DEP1'})
        self.assertFalse(any(e['id']=='DEP1' for e in self.g['edges']))
        self.assertEqual(M.entities(self.g)['D1']['decisionContextIds'],[])

    def test_manual_decision_state_changes_other_decision_without_structural_cancel(self):
        self.add_node('D1','decision');self.add_node('D2','decision')
        self.relation('RD1','DRIVES','R1','D1');self.relation('RD2','DRIVES','R1','D2')
        self.g['edges'].append({'id':'DEP-STATE','type':'DEPENDS_ON','from':'D1','to':'D2',
            'dependencyRule':{'preset':'decision_state','watch':['selection']}})
        M.entities(self.g)['D1']['selectionState']='selected'
        M.entities(self.g)['D2']['selectionState']='selected'
        self.do('withdraw',{'nodeId':'D1'})
        self.assertTrue(M.entities(self.g)['D2']['review']['required'])
        self.assertEqual(M.entities(self.g)['D2']['selectionState'],'selected')
        self.assertEqual(M.entities(self.g)['D1']['selectionState'],'unselected')
        self.assertEqual([r['edgeId'] for r in self.g['events'][-1]['dependencyImpacts']],['DEP-STATE'])

    def test_canon_direct_review_and_decision_canon_custom_subscription(self):
        self.add_node('D1','decision');self.add_node('D2','decision')
        self.add_node('R2','requirement');self.add_node('C1','canon',guidance='Transactions')
        self.add_node('I1','info',value='Article v1')
        self.relation('RD1','DRIVES','R1','D1');self.relation('RD2','DRIVES','R1','D2')
        self.relation('DR1','INTRODUCES','D1','R2')
        self.relation('CAN1','CANON_FOR','C1','D1');self.relation('INFO1','INFO_FOR','I1','C1')
        self.g['edges'].append({'id':'DEP-CAN','type':'DEPENDS_ON','from':'D1','to':'D2',
            'dependencyRule':{'preset':'decision_canon','watch':['definition','canon']}})
        self.do('edit',{'nodeId':'I1','changes':{'value':'Article v2'},'cosmetic':False})
        self.assertNotIn('dependencyImpacts',self.g['events'][-1]);self.assertFalse(M.entities(self.g)['D2'].get('review',{}).get('required',False))
        self.do('edit',{'nodeId':'C1','changes':{'guidance':'Transactions+correctness'},'cosmetic':False})
        hits=self.g['events'][-1]['dependencyImpacts']
        self.assertEqual({(r['sourceId'],r['dependentId']) for r in hits},{('C1','D1'),('D1','D2')})
        self.assertFalse(M.entities(self.g)['R2'].get('review',{}).get('required',False),
                         'Canon is NOT a default transitive child stale trigger')
        self.assertTrue(M.entities(self.g)['D1']['review']['required'])
        self.assertTrue(M.entities(self.g)['D2']['review']['required'])

    def test_custom_context_uses_configured_one_hop_source_watch(self):
        self.add_node('D1','decision');self.add_node('D2','decision');self.add_node('R2','requirement')
        self.add_node('CT1','context',value='Load 100')
        self.relation('RD1','DRIVES','R1','D1');self.relation('RD2','DRIVES','R1','D2')
        self.relation('DR1','INTRODUCES','D1','R2')
        self.g['edges'] += [
            {'id':'DEP-CTX','type':'DEPENDS_ON','from':'CT1','to':'D1',
             'dependencyPurpose':'decisionContext','dependencyRule':{'preset':'L1','watch':['definition']}},
            {'id':'DEP-D-CTX','type':'DEPENDS_ON','from':'D1','to':'D2',
             'dependencyRule':{'preset':'decision_context','watch':['definition','context']}}]
        self.do('edit',{'nodeId':'CT1','changes':{'value':'Load 10000'},'cosmetic':False})
        self.assertEqual({(r['sourceId'],r['dependentId']) for r in self.g['events'][-1]['dependencyImpacts']},
                         {('CT1','D1'),('D1','D2'),('CT1','R2')})
        structural=next(r for r in self.g['events'][-1]['dependencyImpacts'] if r['dependentId']=='R2')
        self.assertEqual(structural['matchedParticipants']['parentId'],'D1')
        self.assertEqual(structural['matchedParticipants']['contextId'],'CT1')
        self.assertEqual(structural['ruleId'],'context-content')
        self.assertTrue(M.entities(self.g)['D2']['review']['required'])
        self.assertTrue(M.entities(self.g)['R2']['review']['required'])

    def test_native_L1_L2_tracks_exact_direct_content_and_can_be_reviewed(self):
        for ident in ('R2','R3','X','Y'):
            self.add_node(ident,'requirement')
        self.relation('DER12','DERIVES','R1','R2')
        self.relation('DER23','DERIVES','R2','R3')
        self.g['edges'] += [
            {'id':'DEP-L1','type':'DEPENDS_ON','from':'R1','to':'X','dependencyLevel':'L1'},
            {'id':'DEP-L2','type':'DEPENDS_ON','from':'R1','to':'Y','dependencyLevel':'L2'}]
        before=copy.deepcopy(self.g)
        # R3 is deeper than the immediate content of the R1 L2 subscription.
        self.do('edit',{'nodeId':'R3','changes':{'description':'Deep-only new value'},'cosmetic':False})
        self.assertFalse(M.entities(self.g)['X'].get('review',{}).get('required',False))
        self.assertFalse(M.entities(self.g)['Y'].get('review',{}).get('required',False))
        self.assertEqual(self.g['events'][-1].get('dependencyImpacts'),None)
        # Direct R2 definition is part of R1 L2, not its L1 definition.
        self.do('edit',{'nodeId':'R2','changes':{'description':'Direct changed content'},'cosmetic':False})
        self.assertTrue(M.entities(self.g)['Y']['review']['required'])
        self.assertFalse(M.entities(self.g)['X'].get('review',{}).get('required',False))
        self.assertEqual([r for r in self.g['events'][-1]['dependencyImpacts']
            if r['edgeId']=='DEP-L2'],[{
            'edgeId':'DEP-L2','sourceId':'R1','dependentId':'Y','level':'L2',
            'changedParts':['direct-scope']}])
        event_id=self.g['events'][-1]['id']
        self.assertIn(event_id,M.entities(self.g)['Y']['review']['causeEventIds'])
        self.do('review',{'nodeId':'Y','observed':M.pins(self.g,'Y'),'basis':'Checked the new direct requirement'})
        self.assertFalse(M.entities(self.g)['Y']['review']['required'])
        self.assertEqual(M.entities(self.g)['Y']['review']['causeEventIds'],[])
        self.assertTrue(any(e.get('observedPins') for e in self.g['events'] if e['type']=='edited'))
        # The cosmetic rename is audited, but no L1/L2 freshness is invalidated.
        self.do('edit',{'nodeId':'R1','changes':{'title':'Display-only name'},'cosmetic':True})
        self.assertFalse(M.entities(self.g)['X'].get('review',{}).get('required',False))
        self.assertFalse(M.entities(self.g)['Y']['review']['required'])
        # Semantic definition changes invalidate both levels.
        self.do('edit',{'nodeId':'R1','changes':{'description':'Changed requirement definition'},'cosmetic':False})
        rows=self.g['events'][-1]['dependencyImpacts']
        self.assertEqual([(r['edgeId'],r['changedParts']) for r in rows if r['edgeId'].startswith('DEP-')],
                         [('DEP-L1',['definition']),('DEP-L2',['definition'])])
        self.assertTrue(M.entities(self.g)['X']['review']['required'])
        self.assertTrue(M.entities(self.g)['Y']['review']['required'])
        self.assertEqual(M.entities(before)['R1']['title'],'Primary goal')

    def test_native_stale_respects_dependent_review_lock_atomically(self):
        self.add_node('R2','requirement')
        self.g['edges'].append({'id':'DEP1','type':'DEPENDS_ON','from':'R1',
                                'to':'R2','dependencyLevel':'L1'})
        M.entities(self.g)['R2']['locks']={'review':{'mode':'hard','principals':['owner:key'],
             'message':'Only an owner can invalidate this dependent'}}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'OBJECT_OPERATION_LOCK_REQUIRED'):
            self.do('edit',{'nodeId':'R1','changes':{'description':'Semantically changed'},'cosmetic':False})
        self.assertEqual(self.g,before,'rejected native stale must leave source and dependent unchanged')

    def test_native_decision_L2_group_and_context_are_one_hop_only(self):
        self.add_node('D1','decision',decisionContextIds=['CT1'])
        self.add_node('D2','decision');self.add_node('R2','requirement')
        self.add_node('CT1','context',value='Context v1')
        self.add_node('C1','canon',guidance='Current canon')
        self.add_node('I1','info',value='Explanatory info')
        self.add_node('X','requirement');self.add_node('Y','requirement')
        self.g['edges'] += [
            {'id':'DEP-D-L1','type':'DEPENDS_ON','from':'D1','to':'X','dependencyLevel':'L1'},
            {'id':'DEP-D-L2','type':'DEPENDS_ON','from':'D1','to':'Y','dependencyLevel':'L2'},
            {'id':'CAN1','type':'CANON_FOR','from':'C1','to':'D1'},
            {'id':'INFO1','type':'INFO_FOR','from':'I1','to':'C1'}]
        self.group('G1','R2',['D1','D2'],required=False,exclusive=True)
        self.do('edit',{'nodeId':'I1','changes':{'value':'Changed explanatory info'},'cosmetic':False})
        self.assertFalse(M.entities(self.g)['Y'].get('review',{}).get('required',False),
                         'a shared INFO inside Canon is not recursive Decision L2')
        self.do('edit',{'nodeId':'CT1','changes':{'value':'Changed factual context'},'cosmetic':False})
        self.assertEqual([r['dependentId'] for r in self.g['events'][-1]['dependencyImpacts']
            if r['edgeId']=='DEP-D-L2'],['Y'])
        self.assertFalse(M.entities(self.g)['X'].get('review',{}).get('required',False))
        self.do('review',{'nodeId':'Y','observed':M.pins(self.g,'Y'),'basis':'Context reviewed'})
        self.do('edit',{'nodeId':'C1','changes':{'guidance':'Changed direct Canon'},'cosmetic':False})
        self.assertEqual([r['dependentId'] for r in self.g['events'][-1]['dependencyImpacts']
            if r['edgeId']=='DEP-D-L2'],['Y'])
        self.do('review',{'nodeId':'Y','observed':M.pins(self.g,'Y'),'basis':'Canon reviewed'})
        g=copy.deepcopy(self.g['decisionGroups'][0]);g['selectionRequired']=True
        self.do('decision_group',{'group':g})
        self.assertEqual([r['dependentId'] for r in self.g['events'][-1]['dependencyImpacts']
            if r['edgeId']=='DEP-D-L2'],['Y'])
        self.assertTrue(M.entities(self.g)['Y']['review']['required'])
        self.assertFalse(M.entities(self.g)['X'].get('review',{}).get('required',False))

    def test_explicit_child_dependency_invalidates_parent_and_respects_review_lock(self):
        self.add_node('R2','requirement')
        self.relation('DER','DERIVES','R1','R2')
        # A child edit does NOT stale its parent implicitly; this is an explicit
        # L1 requirement for reviewing the parent when R2 changes.
        self.g['edges'].append({'id':'DEP-PARENT','type':'DEPENDS_ON','from':'R2',
                               'to':'R1','dependencyLevel':'L1'})
        self.g['nodes'][0]['locks']={'review':{'mode':'hard','principals':['owner:key'],
             'message':'Review of main goal requires owner'}}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'OBJECT_OPERATION_LOCK_REQUIRED'):
            self.do('edit',{'nodeId':'R2','changes':{'description':'New criterion'},'cosmetic':False})
        self.assertEqual(self.g,before)
        del self.g['nodes'][0]['locks']
        self.do('edit',{'nodeId':'R2','changes':{'description':'New criterion'},'cosmetic':False})
        self.assertTrue(M.entities(self.g)['R1']['review']['required'])
        self.assertTrue(M.entities(self.g)['R2']['review']['required'])

    def test_external_task_can_be_executed_separately_without_selection_or_graph_placement(self):
        self.add_node('EVID1','evidence')
        task={'id':'EXT1','kind':'action','title':'External task','description':'Task',
            'revision':1,'actionType':'task','lowLevel':True,'targetIds':[],
            'groupIds':[],'result':{'state':'open','truth':'unknown'}}
        self.g['externalActions'].append(task)
        M.validate(self.g)
        self.do('complete',{'nodeId':'EXT1','basis':'Task actually performed','evidenceIds':['EVID1']})
        state=M.completion_state(self.g)
        self.assertTrue(state['EXT1']['complete'])
        self.assertFalse(state['EXT1']['active'])
        self.assertFalse(state['R1']['complete'])
        self.assertNotIn('EXT1',self.g['workGraphs'][0]['memberIds'])

    def test_discovery_and_rename_have_atomic_completed_low_level_operation_records(self):
        requirement={'id':'R2','kind':'requirement','title':'Second goal',
            'description':'Second goal','scope':'Synthetic scope','revision':1,
            'result':{'state':'open','truth':'unknown'}}
        self.do('add',{'entity':requirement,'location':'graph','workGraphId':'WG1'})
        created=self.g['events'][-1]
        operation=next(a for a in self.g['externalActions'] if a['id']==created['operationActionId'])
        execution=next(e for e in self.g['events'] if e['id']==operation['result']['eventId'])
        self.assertEqual((operation['actionType'],operation['lowLevel']),('discover_requirement',True))
        self.assertEqual((operation['result']['state'],execution['type']),('confirmed','action_executed'))
        self.assertTrue(M.completion_state(self.g)[operation['id']]['complete'])
        self.assertEqual(created['transactionId'],execution['transactionId'])
        self.assertNotIn(operation['id'],self.g['workGraphs'][0]['memberIds'])
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'OPERATION_RECORD_ONLY'):
            self.do('complete',{'nodeId':operation['id'],'basis':'Cannot execute the same operation again',
                'evidenceIds':['EVIDENCE-NOT-NEEDED']})
        self.assertEqual(self.g,before)
        self.do('edit',{'nodeId':'R2','changes':{'title':'Renamed goal'},'cosmetic':True})
        renamed=self.g['events'][-1]
        operation=next(a for a in self.g['externalActions'] if a['id']==renamed['operationActionId'])
        self.assertEqual(operation['actionType'],'rename_block')
        self.assertEqual(operation['result']['state'],'confirmed')
        self.assertEqual(self.g['nodes'][-1]['title'],'Renamed goal')
        M.validate(self.g)

    def test_review_multiple_targets_uses_one_pinned_union_atomically(self):
        self.add_node('R2','requirement');self.add_node('R3','requirement')
        self.relation('DER','DERIVES','R1','R2')
        self.g['edges'] += [
            {'id':'DEP-R2-R1','type':'DEPENDS_ON','from':'R2','to':'R1','dependencyLevel':'L1'},
            {'id':'DEP-R3-R2','type':'DEPENDS_ON','from':'R3','to':'R2','dependencyLevel':'L1'}]
        self.do('edit',{'nodeId':'R2','changes':{'description':'Changed basis'},'cosmetic':False})
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'REVIEW_INPUTS_CHANGED'):
            self.do('review',{'nodeIds':['R1','R2'],'observed':M.pins(self.g,'R1'),
                'basis':'One pin set is insufficient for both targets'})
        self.assertEqual(self.g,before)
        observed={**M.pins(self.g,'R1'),**M.pins(self.g,'R2')}
        self.do('review',{'nodeIds':['R1','R2'],'observed':observed,
                'basis':'All actual inputs reviewed together'})
        self.assertFalse(M.entities(self.g)['R1']['review']['required'])
        self.assertFalse(M.entities(self.g)['R2']['review']['required'])

    def test_checkpoint_supporting_info_is_accessible_by_focus_without_graph_change(self):
        graph=json.loads((ROOT/'tools/rdg-agent-lenses/checkpoint-decision.json').read_text())
        before=copy.deepcopy(graph)
        def ids(target):
            view=M.focused_view(graph,target)
            return {n['id'] for n in view['entities']},{e['type'] for e in view['edges']}
        roots,edges=ids('R-LENS-CHECKPOINT')
        self.assertEqual(roots,{'R-LENS-CHECKPOINT','CP-A1','CP-A2','CP-A3','CP-A4','CP-A5',
                                'INFO-DECISION-API-CHECKPOINT','I-LENS-CHECKPOINT',
                                'LS-MAP-CHECKPOINT','LS-SOURCE-CHECKPOINT','LS-WORKFLOW-CHECKPOINT'})
        self.assertIn('INFO_FOR',edges)
        decision,edges=ids('CP-A1')
        self.assertTrue({'R-LENS-CHECKPOINT','CP-A1','CANON-CP-A1',
                         'LS-STEP-CHECKPOINT-TRIGGER','LS-STEP-CHECKPOINT-BASIS','LS-STEP-CHECKPOINT-NEXT'}<=decision)
        self.assertTrue(any(i.startswith('LS-TEXT-CHECKPOINT-') for i in decision))
        self.assertIn('CANON_FOR',edges)
        canon,edges=ids('CANON-CP-A1')
        self.assertEqual(len([i for i in canon if i.startswith('CP-C')]),7)
        self.assertEqual(len(canon),9)
        self.assertIn('INFO_FOR',edges)
        self.assertEqual(graph,before,'opening focus is a read-only projection')

    def test_strict_focus_multisource_and_external_action_details(self):
        self.add_node('R2','requirement'); self.add_node('D1','decision'); self.add_node('D2','decision')
        self.add_node('R3','requirement'); self.add_node('A1','action'); self.group('G1','R1',['D1','D2'])
        self.relation('E1','DERIVES','R1','R3')
        self.relation('E2','DERIVES','R2','R3')
        self.relation('E3','REQUIRES_ACTION','D1','A1')
        M.validate(self.g)
        focused=M.focused_view(self.g,'D1')
        self.assertEqual({n['id'] for n in focused['entities']},{'R1','D1','A1'})
        self.assertNotIn('D2',{n['id'] for n in focused['entities']})
        self.assertEqual([r['id'] for r in focused['decisionMemberships']],['G1-M1'])
        self.assertEqual({n['id'] for n in M.focused_view(self.g,'R3')['entities']},{'R1','R2','R3'})
        external={'id':'EXT1','kind':'action','title':'Outside graph','description':'Outside graph',
                  'revision':1,'actionType':'task','lowLevel':True,'targetIds':[],
                  'groupIds':[],'result':{'state':'open','truth':'unknown'}}
        self.g['externalActions'].append(external)
        M.validate(self.g)
        self.assertNotIn('EXT1',{n['id'] for n in M.focused_view(self.g,'R1')['entities']})

    def test_finding_01_stable_requirement_rejects_note_without_explicit_reason(self):
        self.g['nodes'][0]['policy']={'mode':'stable'}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'STABLE_REASON_REQUIRED'):
            self.do('edit',{'nodeId':'R1','changes':{'description':'Changed'},'cosmetic':False})
        self.assertEqual(self.g,before)
        ev=self.event('explicit reconsideration')
        ev['reasonForReconsideration']='Conditions have materially changed'
        after,_=M.apply(self.g,{'schemaVersion':1,'expectedRevision':self.g['revision'],
            'operations':[{'op':'graph_edit','action':'core_edit',
                'data':{'nodeId':'R1','changes':{'description':'Changed'},'cosmetic':False},'event':ev}]},True)
        self.assertEqual(M.entities(after)['R1']['description'],'Changed')

    def test_finding_04_warning_lock_is_durable_and_deduplicated(self):
        self.g['nodes'][0]['locks']={'edit':{'mode':'warning','principals':[],
            'message':'Read warning before editing'}}
        self.do('edit',{'nodeId':'R1','changes':{'description':'Changed'},'cosmetic':False})
        self.assertEqual(self.g['events'][-1]['lockWarnings'],
            [{'nodeId':'R1','operation':'edit','message':'Read warning before editing'}])
        M.validate(self.g)

    def test_finding_07_special_operation_records_cannot_be_created_directly(self):
        for kind in ('discover_requirement','discover_decision','rename_block'):
            before=copy.deepcopy(self.g)
            fake={'id':'FAKE-'+kind,'kind':'action','title':'Fake','description':'Not performed',
                'revision':1,'result':{'state':'open','truth':'unknown'},
                'actionType':kind,'lowLevel':True,'targetIds':[],'groupIds':[]}
            with self.assertRaisesRegex(ValueError,'OPERATION_RECORD_ONLY'):
                self.do('add',{'entity':fake,'location':'external'})
            self.assertEqual(self.g,before)
        external_task={'id':'T1','kind':'action','title':'Legitimate task','description':'Task',
            'revision':1,'result':{'state':'open','truth':'unknown'},
            'actionType':'task','lowLevel':True,'targetIds':[],'groupIds':[]}
        self.do('add',{'entity':external_task,'location':'external'})
        self.assertIn('T1',M.entities(self.g))

    def test_finding_05_connected_add_records_created_and_linked_same_transaction(self):
        action={'id':'A1','kind':'action','title':'Required','description':'Required action',
            'revision':1,'result':{'state':'open','truth':'unknown'},
            'actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[]}
        self.do('add',{'entity':action,'location':'graph','workGraphId':'WG1',
            'initialRelations':[{'id':'E1','type':'REQUIRES_ACTION','from':'R1','to':'A1'}]})
        linked,created=self.g['events'][-2:]
        self.assertEqual((linked['type'],created['type']),('linked','created'))
        self.assertEqual(linked['relationIds'],['E1'])
        self.assertEqual(linked['transactionId'],created['transactionId'])
        self.assertEqual([e['id'] for e in self.g['edges']],['E1'])
        self.assertEqual(self.g['revision'],2)

    def test_finding_06_completion_distinguishes_missing_evidence_invalid_enum_and_outcome(self):
        self.add_node('D1','decision');self.add_node('EVID1','evidence')
        self.add_node('A1','action',actionType='decide_acceptance',targetIds=['D1'])
        self.relation('RA1','REQUIRES_ACTION','R1','A1')
        self.group('G1','R1',['D1'])
        for data,code in (
            ({'nodeId':'A1','basis':'Observed','evidenceIds':[]},'RESULT_EVIDENCE_REQUIRED'),
            ({'nodeId':'A1','basis':'Observed','evidenceIds':['EVID1'],
              'decisionOutcome':'not-an-outcome'},'SCHEMA_INVALID'),
            ({'nodeId':'A1','basis':'Observed','evidenceIds':['EVID1']},'ACTION_OUTCOME_REQUIRED')):
            before=copy.deepcopy(self.g)
            with self.assertRaisesRegex(ValueError,'^'+code+'$'):
                self.do('complete',data)
            self.assertEqual(self.g,before)

    def test_finding_03_review_retains_exact_typed_snapshot_pins(self):
        self.add_node('R2','requirement')
        self.relation('DER','DERIVES','R1','R2')
        self.g['edges'].append({'id':'DEP-R2-R1','type':'DEPENDS_ON','from':'R2',
                                'to':'R1','dependencyLevel':'L1'})
        self.do('edit',{'nodeId':'R2','changes':{'description':'Changed'},'cosmetic':False})
        observed={**M.pins(self.g,'R1'),**M.pins(self.g,'R2')}
        original_revision=self.g['revision']
        self.do('review',{'nodeIds':['R1','R2'],'observed':observed,
            'basis':'Verified each input revision'})
        event=self.g['events'][-1]
        self.assertEqual({p['nodeId']:p['revision'] for p in event['observedPins']},observed)
        self.assertEqual({p['graphRevision'] for p in event['observedPins']},{original_revision})
        self.assertTrue(all(p['mode']=='historical' for p in event['observedPins']))
        self.assertTrue(M.validate(self.g))
        self.assertFalse(M.entities(self.g)['R1']['review']['required'])


    def test_postfix_remove_checks_protected_surviving_action(self):
        self.add_node('D1','decision')
        ext={'id':'E1','kind':'action','title':'External','description':'External',
            'revision':1,'result':{'state':'open','truth':'unknown'},'actionType':'task',
            'lowLevel':True,'targetIds':['D1'],'groupIds':[],
            'locks':{'edit':{'mode':'hard','principals':['owner:key'],'message':'Protect targets'}}}
        self.g['externalActions'].append(ext)
        M.validate(self.g)
        ev=self.event('remove-protected-target')
        patch={'schemaVersion':1,'expectedRevision':self.g['revision'],
            'operations':[{'op':'graph_edit','action':'core_remove',
              'data':{'nodeIds':['D1']},'event':ev}]}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'OBJECT_OPERATION_LOCK_REQUIRED'):
            M.apply(self.g,patch,True,coordinated=True)
        self.assertEqual(before,self.g)
        ev['authorityPrincipal']='owner:key'
        allowed={**patch,'operations':[{**patch['operations'][0],'event':ev}]}
        result,_=M.apply(before,allowed,True,coordinated=True)
        self.assertEqual(M.entities(result)['E1']['targetIds'],[])

    def test_postfix_decide_acceptance_can_record_decline_of_unselected_decision(self):
        self.add_node('D1','decision')
        self.add_node('EVID1','evidence')
        self.add_node('A1','action',actionType='decide_acceptance',targetIds=['D1'])
        self.relation('RA1','REQUIRES_ACTION','R1','A1')
        self.group('G1','R1',['D1'])
        self.do('complete',{'nodeId':'A1','basis':'Examined and rejected',
            'evidenceIds':['EVID1'],'decisionOutcome':'unselected'})
        decision=M.entities(self.g)['D1']
        action=M.entities(self.g)['A1']
        self.assertEqual(decision['selectionState'],'unselected')
        self.assertEqual(action['result']['state'],'confirmed')
        self.assertEqual(self.g['events'][-1]['actionResult'],
            {'decisionId':'D1','decisionOutcome':'unselected'})
        self.assertTrue(M.validate(self.g))

    def test_postfix_direct_focus_keeps_only_focused_decision_members(self):
        self.add_node('R2','requirement')
        for ident in ('D1','D2','D3'):self.add_node(ident,'decision')
        self.group('G1','R1',['D1','D2'])
        self.group('G2','R2',['D3'])
        v=M.focused_view(self.g,'D1')
        self.assertEqual([g['id'] for g in v['decisionGroups']],['G1'])
        self.assertEqual([m['decisionId'] for m in v['decisionGroups'][0]['members']],['D1'])
        self.assertEqual({m['to'] for m in v['decisionMemberships']},{'D1'})
        self.assertEqual({e['id'] for e in v['entities']},{'R1','D1'})

    def test_postfix_order_and_normalized_codes(self):
        self.add_node('D1','decision')
        for evidence in ([],['missing']):
            before=copy.deepcopy(self.g)
            with self.assertRaisesRegex(ValueError,'^DECISION_NOT_SELECTED$'):
                self.do('complete',{'nodeId':'D1','basis':'Attempt','evidenceIds':evidence})
            self.assertEqual(self.g,before)
        entity={'id':'A1','kind':'action','title':'A1','description':'A1',
            'revision':1,'result':{'state':'open','truth':'unknown'},'actionType':'task',
            'lowLevel':False,'targetIds':[],'groupIds':[]}
        for relation,code in (
            ({'id':'E1','type':'DERIVES','from':'R1','to':'D1'},'RELATION_ENDPOINT_TYPES'),
            ({'id':'E2','type':'REQUIRES_ACTION','from':'R1','to':'D1'},'RELATION_ENDPOINT_TYPES'),
        ):
            with self.assertRaisesRegex(ValueError,'^'+code+'$'):
                self.do('add',{'entity':entity,'location':'graph',
                    'initialRelations':[relation]})
        self.add_node('R2','requirement')
        self.add_node('R3','requirement')
        with self.assertRaisesRegex(ValueError,'^INITIAL_RELATION_UNRELATED$'):
            self.do('add',{'entity':entity,'location':'graph',
                'initialRelations':[{'id':'E3','type':'DERIVES','from':'R2','to':'R3'}]})

if __name__ == '__main__':
    unittest.main()
