#!/usr/bin/env python3
"""Portable-model scenarios on synthetic documents; no live store or grants."""
import copy
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
M = SourceFileLoader('portable_core_scenarios', str(ROOT / 'tools/rdg-core-model.py')).load_module()


class Scenario(unittest.TestCase):
    def setUp(self):
        self.g = M.blank('proof', 'Portable proof', 'proof-space', 'R1', 'Required result', 'Synthetic scope')
        self.sequence = 0

    def do(self, command, coordinated=False, **data):
        self.sequence += 1
        event = {'id': 'EV-' + str(self.sequence), 'type': 'requested', 'by': 'assistant',
                 'note': 'Isolated model test: ' + command,
                 'verifiedTrustReceipt': {'mode': 'test-only'},
                 'evidenceRefs': [{'path': 'synthetic/proof.json', 'sha256': '0' * 64}]}
        self.g, _ = M.apply(self.g, {'schemaVersion': 1, 'expectedRevision': self.g['revision'],
            'operations': [{'op': 'graph_edit', 'action': 'core_' + command, 'data': data, 'event': event}]},
            True, coordinated=coordinated)
        return self.g['events'][-1]

    def add(self, ident, kind='requirement', **fields):
        value = {'id': ident, 'kind': kind, 'title': ident, **fields}
        if kind == 'requirement':value.update(description=ident, scope='Synthetic scope')
        self.do('add', entity=value)

    def link(self, kind, source, target, **fields):
        ident = 'EDGE-' + str(self.sequence + 1)
        self.do('link', edge={'id': ident, 'type': kind, 'from': source, 'to': target, **fields})
        return ident

    def review(self, *ids):
        ns = M.entities(self.g)
        ids = list(ids) or [i for i, n in ns.items() if n.get('review', {}).get('required')]
        if ids:self.do('review', nodeIds=ids, observed={i: ns[i]['revision'] for j in ids for i in M.pins(self.g, j)})

    def selected(self, origin=None):
        self.add('A', 'action');self.add('OUT', status='potential')
        driver = self.link('DRIVES', 'R1', 'A')
        self.link('INTRODUCES', 'A', 'OUT', origin=origin or {'role': 'method_correctness'})
        self.review();self.do('select', nodeId='A');self.review()
        return driver

class PortableModel(Scenario):
    def test_unlink_last_driver_preserves_choice_and_derives_detached_scope(self):
        edge = self.selected();before = copy.deepcopy(self.g)
        selected = M.entities(before)['A']['selectedEventId']
        members = copy.deepcopy(before['workGraphs'])
        self.do('unlink', edgeId=edge)
        self.assertEqual(M.entities(self.g)['A']['status'], 'selected')
        self.assertEqual(M.entities(self.g)['A']['selectedEventId'], selected)
        self.assertTrue(M.entities(self.g)['A']['review']['required'])
        self.assertEqual(self.g['workGraphs'], members)
        self.assertEqual(M.detached_components(self.g)[0]['memberIds'], ['A', 'OUT'])
        self.review('A', 'OUT')
        self.assertFalse(M.entities(self.g)['A']['review']['required'])
        self.assertEqual(M.detached_components(self.g)[0]['memberIds'], ['A', 'OUT'])
        with self.assertRaisesRegex(ValueError, 'REALIZED_REQUIREMENT_REQUIRED'):
            self.do('complete', nodeId='A')
        self.assertEqual(M.entities(self.g)['A']['selectedEventId'], selected)

    def test_stale_flag_alone_does_not_justify_driverless_selected_state(self):
        edge = self.selected()
        self.g['edges'] = [e for e in self.g['edges'] if e['id'] != edge]
        M.entities(self.g)['A']['review'] = {'required': True, 'causes': []}
        with self.assertRaisesRegex(ValueError, 'SELECTED_ACTION_DRIVER_REQUIRED'):M.validate(self.g)

    def test_new_selection_without_driver_stays_forbidden(self):
        self.add('A', 'action')
        with self.assertRaisesRegex(ValueError, 'REALIZED_REQUIREMENT_REQUIRED'):self.do('select', nodeId='A')

    def test_remove_requires_coordinator_and_does_not_mutate_source_on_rejection(self):
        self.selected();before = copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError, 'REMOVAL_REQUIRES_COORDINATOR'):
            self.do('remove', nodeIds=['R1'])
        self.assertEqual(self.g, before)

    def test_removing_last_root_preserves_orphans_and_exact_before_facts(self):
        self.selected();before = copy.deepcopy(self.g)
        original_choice = M.entities(before)['A']['selectedEventId']
        event = self.do('remove', coordinated=True, nodeIds=['R1'])
        self.assertIsNone(self.g['rootRequirementId'])
        self.assertEqual(set(M.entities(self.g)), {'A', 'OUT'})
        self.assertEqual(M.entities(self.g)['A']['selectedEventId'], original_choice)
        self.assertEqual(self.g['workGraphs'][0]['memberIds'], ['A', 'OUT'])
        self.assertEqual(self.g['workGraphs'][0]['rootIds'], [])
        self.assertEqual(M.detached_components(self.g)[0]['memberIds'], ['A', 'OUT'])
        self.assertEqual(event['removedEntities']['R1'], M.entities(before)['R1'])
        self.assertEqual(self.g['events'][:-1], before['events'])
        cause = M.entities(self.g)['A']['review']['causes'][0]
        self.assertEqual(cause['sourceRef']['mode'], 'historical')
        self.assertEqual(cause['sourceRef']['graphSHA256'], M.digest(before))
        M.validate(self.g)

    def test_newly_unresolved_origin_cannot_be_cleared_by_ordinary_review(self):
        self.selected({'role': 'subgoal', 'requirementIds': ['R1']})
        self.do('remove', coordinated=True, nodeIds=['R1'])
        origin = next(e['origin'] for e in M.active_edges(self.g) if e['type'] == 'INTRODUCES')
        self.assertEqual(origin['role'], 'unresolved')
        self.assertTrue(M.output_origin_issues(self.g, 'A'))
        with self.assertRaisesRegex(ValueError, 'OUTPUT_ORIGIN_DRIVER_REQUIRED'):self.review('A', 'OUT')
        self.assertTrue(M.entities(self.g)['A']['review']['required'])

    def test_other_driver_and_root_prevent_false_detachment_but_not_stale(self):
        self.add('R2');self.add('A', 'action');self.add('OUT', status='potential')
        self.link('DRIVES', 'R1', 'A');self.link('DRIVES', 'R2', 'A')
        self.link('INTRODUCES', 'A', 'OUT', origin={'role': 'subgoal', 'requirementIds': ['R1', 'R2']})
        self.g['workGraphs'][0]['rootIds'].append('R2')
        self.review();self.do('select', nodeId='A');self.review()
        self.do('remove', coordinated=True, nodeIds=['R1'])
        self.assertEqual(M.detached_components(self.g), [])
        self.assertEqual(M.entities(self.g)['A']['status'], 'selected')
        self.assertTrue(M.entities(self.g)['A']['review']['required'])
        self.assertEqual(next(e['origin'] for e in self.g['edges'] if e['type'] == 'INTRODUCES'),
                         {'role': 'subgoal', 'requirementIds': ['R2']})

    def test_shared_context_and_explanatory_relations_are_not_realization_paths(self):
        driver = self.selected();self.add('C', 'context');self.add('OTHER', 'action')
        self.link('DRIVES', 'R1', 'OTHER');self.link('CONTEXT_FOR', 'C', 'OTHER')
        self.link('CONTEXT_FOR', 'C', 'A');self.link('RELATES_R', 'R1', 'A', role='affected')
        self.link('DEPENDS_ON', 'R1', 'A')
        self.do('unlink', edgeId=driver)
        self.assertEqual(M.detached_components(self.g)[0]['memberIds'], ['A', 'OUT'])
        self.assertIn('C', self.g['workGraphs'][0]['memberIds'])
        self.assertEqual(M.detached_components(self.g), M.detached_components(copy.deepcopy(self.g)))

    def test_rooted_policy_terminates_on_cycles_and_does_not_rewrite_membership(self):
        driver = self.selected();self.add('NEXT', 'action')
        self.link('DRIVES', 'OUT', 'NEXT');self.link('INTRODUCES', 'NEXT', 'OUT')
        self.do('unlink', edgeId=driver)
        before = copy.deepcopy(self.g)
        self.assertEqual(M.detached_components(self.g)[0]['memberIds'], ['A', 'NEXT', 'OUT'])
        self.assertEqual(self.g, before)

    def test_paper_policy_checks_children_and_has_no_work_history_or_plan(self):
        self.add('CHILD', status='potential');self.add('A', 'action')
        self.link('DERIVES', 'R1', 'CHILD');self.link('DRIVES', 'R1', 'A')
        paper = copy.deepcopy(self.g);paper['events'] = []
        for n in M.entities(paper).values():
            n.pop('review', None)
            if n['kind'] == 'requirement':n['status'] = 'potential'
        M.validate_role(paper, 'ready');M.validate_role(paper, 'lens')
        M.entities(paper)['CHILD']['status'] = 'active'
        with self.assertRaisesRegex(ValueError, 'PAPER_REQUIREMENT_POTENTIAL'):M.validate_role(paper, 'ready')
        M.entities(paper)['CHILD']['status'] = 'potential'
        with self.assertRaisesRegex(ValueError, 'PAPER_NO_PLAN_OR_WORK_HISTORY'):M.validate_role(paper, 'ready', {})

    def test_indirect_protected_consequences_are_guarded_before_removal(self):
        self.selected()
        M.entities(self.g)['OUT']['policy'] = {'mode': 'protected', 'authorityPrincipal': 'owner'}
        before = copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError, 'PROTECTED_OWNER_GRANT_REQUIRED'):
            self.do('remove', coordinated=True, nodeIds=['R1'])
        self.assertEqual(self.g, before)





P = SourceFileLoader('portable_planning_scenarios', str(ROOT / 'tools/rdg-portable-model.py')).load_module()


class PortablePlanning(Scenario):
    def paper(self):
        graph = M.blank('template', 'Complete paper template', 'template-space', 'T', 'Template root', 'Paper scope')
        root = graph['nodes'][0];root['status'] = 'potential'
        def requirement(i):return {'id': i, 'kind': 'requirement', 'title': i, 'description': i,
            'scope': 'Paper scope', 'revision': 1, 'status': 'potential', 'qrpe': [],
            'result': {'state': 'open', 'truth': 'unknown'}}
        def action(i):return {'id': i, 'kind': 'action', 'title': i, 'revision': 1, 'status': 'candidate',
            'qrpe': [], 'result': {'state': 'open', 'truth': 'unknown'}}
        graph['nodes'] += [requirement('TC'), action('TA'), action('TB')]
        graph['objects'] = [
            {'id': 'K', 'kind': 'canon', 'title': 'Canon', 'revision': 1, 'arguments': [
                {'id': 'arg', 'text': 'Illustrative incompatibility', 'polarity': 'against', 'strength': 'hard',
                 'condition': {'id': 'local-condition', 'kind': 'context', 'text': 'Illustrative context'}}]},
            {'id': 'C', 'kind': 'context', 'title': 'Context', 'revision': 1},
            {'id': 'I', 'kind': 'info', 'title': 'Info', 'revision': 1, 'properties': {'literal-id-text': 'TA'}},
            {'id': 'E', 'kind': 'evidence', 'title': 'Evidence', 'revision': 1,
             'claim': 'Claim', 'scope': 'Paper scope', 'version': '1', 'source': 'synthetic/source.txt'}]
        graph['edges'] = [
            {'id': 'D1', 'type': 'DRIVES', 'from': 'T', 'to': 'TA'},
            {'id': 'D2', 'type': 'DRIVES', 'from': 'T', 'to': 'TB'},
            {'id': 'O1', 'type': 'INTRODUCES', 'from': 'TA', 'to': 'TC',
             'origin': {'role': 'subgoal', 'requirementIds': ['T']}},
            {'id': 'K1', 'type': 'CANON_FOR', 'from': 'K', 'to': 'TA'},
            {'id': 'C1', 'type': 'CONTEXT_FOR', 'from': 'C', 'to': 'TA'},
            {'id': 'I1', 'type': 'INFO_FOR', 'from': 'I', 'to': 'TA'},
            {'id': 'E1', 'type': 'EVIDENCE_FOR', 'from': 'E', 'to': 'TA'}]
        graph['workGraphs'][0]['memberIds'] = sorted(M.entities(graph))
        graph['exclusionGroups'] = [{'id': 'X', 'actionIds': ['TA', 'TB'], 'reason': 'Alternative strategies'}]
        graph['lensRecommendations'] = [{'lensKey': 'review', 'text': 'Review the imported scope'},
                                        {'lensKey': 'clarify', 'text': 'Clarify the action', 'targetId': 'TA'}]
        M.validate_role(graph, 'ready')
        return graph

    def inputs(self, replace=False):
        self.selected({'role': 'subgoal', 'requirementIds': ['R1']})
        source = self.paper()
        snapshots = {'packages': {'P-target': {'graph': self.g, 'role': 'working', 'revision': 3},
                                  'P-ready': {'graph': source, 'role': 'ready', 'revision': 2}},
                     'plans': {}, 'incomingComplete': True}
        command = {'op': 'apply_ready', 'sourcePackageId': 'P-ready', 'targetPackageId': 'P-target',
            'expectedPackageRevision': 3, 'expectedGraphRevision': self.g['revision'],
            'sourcePin': {'revision': 2, 'sha256': P.digest(source)},
            'mode': 'REPLACE_R' if replace else 'ADD_ROOT', 'note': 'Use the complete paper template'}
        if replace:command['targetRequirementId'] = 'R1'
        allocation = {'idMap': {kind: {i: 'new-' + kind + '-' + i for i in ids}
                               for kind, ids in P.definitions(source).items()},
                      'eventId': 'APPLY', 'removalEventId': 'REMOVE', 'scopeId': 'aggregate',
                      'recordedAt': '2026-10-23T10:00:00+07:00'}
        return command, snapshots, allocation

    def placement_plan(self, ident):
        graph = self.g
        def step(i, nid, kind, possible=False):return {'id': i, 'title': i, 'kind': kind,
            'state': 'possible' if possible else 'planned', 'ref': P.reference('P-target', graph, nid)}
        plan = {'schemaVersion': 2, 'kind': 'temporalPlan', 'id': ident, 'title': ident,
            'identitySpace': 'plan-space-' + ident, 'revision': 4, 'status': 'candidate',
            'steps': [step('X', 'A', 'action'), step('OLD', 'R1', 'requirement'),
                      step('Y', 'OUT', 'requirement'), step('OLD-CASE', 'R1', 'requirement', True),
                      step('OTHER-CASE', 'A', 'action', True)],
            'sequence': [{'before': 'X', 'after': 'OLD'}, {'before': 'OLD', 'after': 'Y'}],
            'branches': [{'id': 'B', 'title': 'Conditional work', 'cases': [
                {'id': 'C1', 'title': 'First', 'condition': 'First outcome', 'stepIds': ['OLD-CASE']},
                {'id': 'C2', 'title': 'Second', 'condition': 'Second outcome', 'stepIds': ['OTHER-CASE']}]}],
            'timeConstraints': [{'stepId': i, 'type': 'notBefore', 'at': '2026-10-24',
                                 'strength': 'soft', 'basis': 'Synthetic placement'}
                                for i in ('OLD-CASE', 'OTHER-CASE')]}
        P.validate_plan(plan)
        return plan

    def test_full_apply_keeps_all_alternatives_and_scopes_global_advice(self):
        command, snapshots, allocation = self.inputs()
        original = copy.deepcopy(snapshots)
        effects = P.prepare_effects(command, snapshots, {'kernel': M}, allocation).value
        after = effects['graphs']['P-target'];mapping = allocation['idMap']['entity']
        self.assertEqual(after['rootRequirementId'], 'R1')
        self.assertEqual(set(M.entities(after)), set(M.entities(self.g)) | set(mapping.values()))
        self.assertEqual(M.entities(after)['A']['status'], 'selected')
        self.assertEqual(M.entities(after)[mapping['T']]['status'], 'active')
        self.assertEqual(M.entities(after)[mapping['TC']]['status'], 'potential')
        self.assertTrue(all(M.entities(after)[mapping[i]]['status'] == 'candidate' for i in ('TA', 'TB')))
        self.assertEqual(M.entities(after)[mapping['I']]['properties']['literal-id-text'], 'TA')
        self.assertEqual(M.entities(after)[mapping['K']]['arguments'][0]['condition']['id'], 'local-condition')
        self.assertEqual(effects['insertedWorkGraphId'], 'new-workGraph-WG-main')
        self.assertEqual(after['lensRecommendations'][0]['targetWorkGraphId'], effects['insertedWorkGraphId'])
        self.assertNotIn('targetId', after['lensRecommendations'][0])
        self.assertEqual(after['lensRecommendations'][1]['targetId'], mapping['TA'])
        self.assertEqual(after['events'][:-1], self.g['events'])
        self.assertEqual(snapshots, original)
        self.assertEqual(effects['plans'], {})

    def test_replace_removes_all_current_placements_and_preserves_empty_case(self):
        command, snapshots, allocation = self.inputs(True)
        snapshots['plans'] = {i: {'plan': self.placement_plan(i)} for i in ('P1', 'P2')}
        original = copy.deepcopy(snapshots)
        effects = P.prepare_effects(command, snapshots, {'kernel': M}, allocation).value
        after = effects['graphs']['P-target'];new_root = allocation['idMap']['entity']['T']
        self.assertEqual(after['rootRequirementId'], new_root)
        self.assertNotIn('R1', M.entities(after))
        self.assertEqual(M.entities(after)['A']['status'], 'selected')
        self.assertTrue(M.entities(after)['A']['review']['required'])
        self.assertEqual(M.detached_components(after)[0]['memberIds'], ['A', 'OUT'])
        self.assertFalse(any(e['from'] == new_root and e['to'] == 'A' for e in after['edges']))
        for owner in ('P1', 'P2'):
            plan = effects['plans'][owner]
            self.assertEqual({s['id'] for s in plan['steps']}, {'X', 'Y', 'OTHER-CASE'})
            self.assertEqual(plan['sequence'], [])
            self.assertEqual(plan['branches'][0]['cases'][0]['stepIds'], [])
            self.assertEqual(plan['branches'][0]['cases'][0]['emptyOutcome'], 'no-placed-work')
            self.assertFalse(any(s['ref']['nodeId'] in ('R1', new_root) for s in plan['steps']))
            self.assertEqual(plan['revision'], 5)
            self.assertEqual(effects['removedPlacements'][owner], ['OLD', 'OLD-CASE'])
        self.assertEqual(snapshots, original)
        self.assertEqual(effects['graphs']['P-target']['revision'], self.g['revision'] + 1)

    def test_plan_with_no_matching_placement_retains_exact_payload_and_revision(self):
        self.selected();plan = self.placement_plan('unchanged')
        after, removed = P.remove_plan_references(plan, 'another-package', self.g['identitySpace'], {'R1'})
        self.assertEqual(after, plan);self.assertEqual(removed, [])

    def test_planning_is_deterministic_and_returned_effects_are_defensive_copies(self):
        command, snapshots, allocation = self.inputs(True)
        snapshots['plans'] = {i: {'plan': self.placement_plan(i)} for i in ('P2', 'P1')}
        first = P.prepare_effects(command, snapshots, {'kernel': M}, allocation)
        shuffled = copy.deepcopy(snapshots)
        shuffled['packages'] = dict(reversed(list(shuffled['packages'].items())))
        shuffled['plans'] = dict(reversed(list(shuffled['plans'].items())))
        second = P.prepare_effects(command, shuffled, {'kernel': M}, allocation)
        self.assertEqual(first.payload, second.payload)
        value = first.value;value['graphs']['P-target']['nodes'].clear()
        self.assertTrue(first.value['graphs']['P-target']['nodes'])

    def test_source_conflict_and_incomplete_incoming_set_are_rejected_before_effects(self):
        command, snapshots, allocation = self.inputs(True)
        original = copy.deepcopy(snapshots)
        command['sourcePin']['revision'] = 999
        with self.assertRaisesRegex(ValueError, 'SOURCE_REVISION_CONFLICT'):
            P.prepare_effects(command, snapshots, {'kernel': M}, allocation)
        command['sourcePin']['revision'] = 2;snapshots['incomingComplete'] = False
        with self.assertRaisesRegex(ValueError, 'INCOMING_CLOSURE_UNCONFIRMED'):
            P.prepare_effects(command, snapshots, {'kernel': M}, allocation)
        snapshots['incomingComplete'] = True;self.assertEqual(snapshots, original)

    def test_capture_policies_preserve_boundaries_and_do_not_expand_shared_drivers(self):
        self.add('R2');self.add('A', 'action');self.add('OUT', status='potential');self.add('NEXT', 'action')
        self.add('K', 'canon', arguments=[{'id': 'H', 'text': 'Condition', 'polarity': 'against', 'strength': 'hard',
            'condition': {'id': 'local', 'kind': 'requirement', 'text': 'Illustrative'}}])
        self.link('DRIVES', 'R1', 'A');self.link('DRIVES', 'R2', 'A');self.link('CANON_FOR', 'K', 'A')
        self.link('INTRODUCES', 'A', 'OUT');self.link('DRIVES', 'OUT', 'NEXT')
        r = P.capture(self.g, {'kind': 'requirement', 'id': 'R1'}, M)
        self.assertEqual(set(r['entityIds']), {'R1', 'A', 'K', 'OUT', 'NEXT'})
        self.assertTrue(any(e['from'] == 'R2' and e['to'] == 'A' for e in r['boundaryEdges']))
        a = P.capture(self.g, {'kind': 'action', 'id': 'A'}, M)
        self.assertEqual(set(a['entityIds']), {'A', 'R1', 'R2', 'K', 'OUT'})
        canon = P.capture(self.g, {'kind': 'canon', 'id': 'K'}, M)
        self.assertEqual(canon['entityIds'], ['K'])
        self.assertEqual(canon['boundaryEdges'][0]['to'], 'A')

    def test_typed_ref_namespace_and_new_scope_advice_slot_use_one_remapper(self):
        source = self.paper();source['edges'][0]['id'] = 'T'
        source['workGraphs'][0]['id'] = 'T'
        source['lensRecommendations'].append({'lensKey': 'review', 'text': 'This scope', 'targetWorkGraphId': 'T'})
        mapping = {kind: {i: kind + ':' + i for i in ids} for kind, ids in P.definitions(source).items()}
        after = P.remap_graph(source, mapping)
        self.assertEqual(after['rootRequirementId'], 'entity:T')
        self.assertEqual(after['edges'][0]['id'], 'edge:T')
        self.assertEqual(after['edges'][0]['from'], 'entity:T')
        self.assertEqual(after['workGraphs'][0]['id'], 'workGraph:T')
        self.assertEqual(after['lensRecommendations'][-1]['targetWorkGraphId'], 'workGraph:T')
        M.validate_role(after, 'ready')

    def test_ref_freshness_uses_target_revision_and_history_distinguishes_unavailability(self):
        self.selected();ref = P.reference('P', self.g, 'A');history = copy.deepcopy(self.g)
        self.g['revision'] += 1
        self.assertIsNone(P.resolve_reference(ref, {'P': {'graph': self.g}})['changed'])
        baseline={('P',history['identitySpace'],P.digest(history)):history}
        self.assertFalse(P.resolve_reference(ref, {'P': {'graph': self.g}},baseline,M)['changed'])
        M.entities(self.g)['A']['revision'] += 1
        self.assertTrue(P.resolve_reference(ref, {'P': {'graph': self.g}})['changed'])
        self.g['nodes'] = [n for n in self.g['nodes'] if n['id'] != 'A']
        historical = {('P', history['identitySpace'], P.digest(history)): history}
        self.assertEqual(P.resolve_reference(ref, {'P': {'graph': self.g}}, historical)['status'], 'deleted')
        unavailable = P.resolve_reference(ref, {}, historical)
        self.assertEqual(unavailable['status'], 'historical-current-unavailable')
        self.assertIsNone(unavailable['changed'])
        self.assertEqual(P.resolve_reference(ref, {})['status'], 'unavailable')

    def test_reference_detects_new_result_without_definition_revision(self):
        self.selected();self.review();self.do('complete',nodeId='OUT')
        ref=P.reference('P',self.g,'A');baseline=copy.deepcopy(self.g)
        revision=M.entities(self.g)['A']['revision'];self.do('complete',nodeId='A')
        self.assertEqual(M.entities(self.g)['A']['revision'],revision)
        history={('P',baseline['identitySpace'],P.digest(baseline)):baseline}
        self.assertTrue(P.resolve_reference(ref,{'P':{'graph':self.g}},history,M)['changed'])

    def test_unknown_fields_and_incomplete_maps_cannot_silently_drop_content(self):
        command, snapshots, allocation = self.inputs()
        snapshots['packages']['P-ready']['graph']['unregisteredRefs'] = ['T']
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_GRAPH_FIELDS'):
            P.prepare_effects(command, snapshots, {'kernel': M}, allocation)
        snapshots['packages']['P-ready']['graph'].pop('unregisteredRefs')
        allocation['idMap']['entity'].pop('TA')
        with self.assertRaisesRegex(ValueError, 'ID_MAP_entity'):
            P.prepare_effects(command, snapshots, {'kernel': M}, allocation)

    def test_plan_branches_reject_cross_case_dependencies_and_invalid_dates(self):
        self.selected();plan = self.placement_plan('invalid')
        plan['sequence'].append({'before': 'OLD-CASE', 'after': 'OTHER-CASE'})
        with self.assertRaisesRegex(ValueError, 'PLAN_EXCLUSIVE_BRANCH_DEPENDENCY'):P.validate_plan(plan)
        plan['sequence'].pop();plan['timeConstraints'][0]['at'] = '2026-99-99'
        with self.assertRaisesRegex(ValueError, 'PLAN_TIME_LITERAL'):P.validate_plan(plan)

    def test_domain_imports_and_calls_do_not_cross_io_or_clock_boundaries(self):
        import ast
        tree = ast.parse((ROOT / 'tools/rdg-portable-model.py').read_text())
        forbidden = {'os', 'pathlib', 'subprocess', 'random', 'secrets', 'fcntl', 'http', 'socket'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):self.assertFalse({n.name.split('.')[0] for n in node.names} & forbidden)
            if isinstance(node, ast.ImportFrom):self.assertNotIn(node.module.split('.')[0], forbidden)
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ''
                self.assertNotIn(name, {'open', 'read_text', 'write_text', 'now', 'today', 'uuid4'})


if __name__ == '__main__':unittest.main()
