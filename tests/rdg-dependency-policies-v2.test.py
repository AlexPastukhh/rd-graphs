#!/usr/bin/env python3
"""Dependency policies: execution, durable catalog, suspended bindings and inspector projection.

Only synthetic Graphs and temporary package namespaces are used.
"""
import copy
from importlib.machinery import SourceFileLoader
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('policy_v2_kernel_fixture',str(ROOT/'tests/rdg-decision-model.test.py')).load_module()
API=SourceFileLoader('policy_v2_api_fixture',str(ROOT/'tests/rdg-decision-integration.test.py')).load_module()
M=BASE.M


def definition():
    return {'id':'POL-V2','version':1,'name':'Observe context','description':'Synthetic typed roles',
        'status':'active','pattern':'roles','sourceKinds':['context'],'targetKinds':['decision'],
        'roles':[{'id':'target','kinds':['decision'],'required':True},
                 {'id':'source','kinds':['context'],'required':True}],
        'relations':[], 'rules':[{'id':'content','name':'Context content changed','role':'source',
            'watch':'definition','operations':['changed'],'enabled':True}]}


def binding():
    return {'id':'B-V2','policyId':'POL-V2','policyVersion':1,'targetId':'D1',
            'sourceId':None,'parentId':None,'enabled':True,'participantBindings':{'source':'CTX'}}


class PolicyKernel(BASE.DecisionKernel):
    def setup_policy(self,p=None,b=None):
        self.add_node('D1','decision');self.add_node('CTX','context',value='before')
        self.do('policy_change',{'action':'policy_save','value':p or definition()})
        return self.do('policy_change',{'action':'binding_save','value':b or binding()})

    def test_v2_registration_is_not_stale_and_content_has_exact_evidence(self):
        event=self.setup_policy();self.assertNotIn('dependencyImpacts',event)
        self.assertFalse(M.entities(self.g)['D1'].get('review',{}).get('required',False))
        ev=self.do('edit',{'nodeId':'CTX','changes':{'value':'after'},'cosmetic':False})
        hit=next(h for h in ev['dependencyImpacts'] if h.get('bindingId')=='B-V2')
        self.assertEqual(hit['matchedParticipants']['sourceId'],'CTX')
        self.assertEqual(hit['ruleSnapshot']['id'],'content')
        self.assertEqual(hit['participantSnapshot']['CTX']['title'],'CTX')

    def test_v2_applicability_latches_until_explicit_activation(self):
        p=definition();p['relations']=[{'from':'source','to':'target','type':'CONTEXT_FOR'}]
        self.add_node('D1','decision');self.add_node('CTX','context',value='before')
        self.relation('CONTEXT-REL','CONTEXT_FOR','CTX','D1')
        self.do('policy_change',{'action':'policy_save','value':p})
        self.do('policy_change',{'action':'binding_save','value':binding()})
        ev=self.do('unlink',{'edgeId':'CONTEXT-REL'})
        b=self.g['dependencyBindings'][0]
        self.assertFalse(b['enabled']);self.assertEqual(b['reasonCode'],'applicability')
        self.assertTrue(ev['dependencyTransitions']);self.assertNotIn('dependencyImpacts',ev)
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'INAPPLICABLE'):
            self.do('policy_change',{'action':'binding_activate','value':{'id':b['id']}})
        self.assertEqual(before,self.g)
        self.do('link',{'relation':{'id':'RESTORED','type':'CONTEXT_FOR','from':'CTX','to':'D1'}})
        self.assertFalse(self.g['dependencyBindings'][0]['enabled'])
        self.do('edit',{'nodeId':'CTX','changes':{'value':'while disabled'},'cosmetic':False})
        self.assertFalse(any(h.get('bindingId')==b['id'] for h in self.g['events'][-1].get('dependencyImpacts',[])))
        self.do('policy_change',{'action':'binding_activate','value':{'id':b['id']}})
        self.assertTrue(self.g['dependencyBindings'][0]['enabled'])
        self.assertNotIn('dependencyImpacts',self.g['events'][-1])

    def test_v2_removal_preserves_binding_and_historical_participant(self):
        self.setup_policy();ev=self.event('remove mandatory context')
        self.g,_=M.apply(self.g,{'schemaVersion':1,'expectedRevision':self.g['revision'],
            'operations':[{'op':'graph_edit','action':'core_remove','data':{'nodeIds':['CTX']},'event':ev}]},True,coordinated=True)
        b=self.g['dependencyBindings'][0]
        self.assertFalse(b['enabled']);self.assertEqual(b['participantBindings']['source'],'CTX')
        self.assertEqual(b['participantSnapshot']['CTX']['title'],'CTX');M.validate(self.g)
        self.do('policy_change',{'action':'binding_remove','value':{'id':b['id']}})
        self.assertEqual(self.g['dependencyBindings'][0]['status'],'deleted');M.validate(self.g)

    def test_v2_dynamic_membership_removal_is_not_loss_of_applicability(self):
        p=definition();p['roles'][1]={'id':'source','kinds':['context'],'required':False,
            'selector':{'anchor':'target','relation':'DECISION_CONTEXT','direction':'in','minDepth':1,'maxDepth':1}}
        p['rules']=[{'id':'removed','name':'Member removed','role':'source','watch':'membership','operations':['removed'],'enabled':True}]
        b=binding();b['participantBindings']={}
        self.add_node('D1','decision',decisionContextIds=['CTX']);self.add_node('CTX','context',value='before')
        self.do('policy_change',{'action':'policy_save','value':p});self.do('policy_change',{'action':'binding_save','value':b})
        ev=self.do('edit',{'nodeId':'D1','changes':{'decisionContextIds':[]},'cosmetic':False})
        hits=[h for h in ev.get('dependencyImpacts',[]) if h.get('bindingId')==b['id']]
        self.assertEqual([(h['triggerOperation'],h['sourceId']) for h in hits],[('removed','CTX')])
        self.assertTrue(self.g['dependencyBindings'][0]['enabled'])
        self.assertIn('context:D1:CTX',hits[0]['matchedRelations'])

    def test_v2_multihop_chain_records_all_three_roles_and_exact_path(self):
        p=definition();p['targetKinds']=['action'];p['roles']=[{'id':'target','kinds':['action']},
            {'id':'parent','kinds':['decision'],'selector':{'anchor':'target','relation':'REQUIRES_ACTION','direction':'in','minDepth':1,'maxDepth':1},'required':True},
            {'id':'source','kinds':['context'],'selector':{'anchor':'parent','relation':'DECISION_CONTEXT','direction':'in','minDepth':1,'maxDepth':1},'required':False}]
        self.add_node('A1','action');self.add_node('D1','decision',decisionContextIds=['CTX']);self.add_node('CTX','context',value='before')
        self.relation('DA','REQUIRES_ACTION','D1','A1')
        b=binding();b.update(targetId='A1',participantBindings={})
        self.do('policy_change',{'action':'policy_save','value':p});self.do('policy_change',{'action':'binding_save','value':b})
        ev=self.do('edit',{'nodeId':'CTX','changes':{'value':'after'},'cosmetic':False})
        hit=next(h for h in ev['dependencyImpacts'] if h.get('bindingId')==b['id'])
        self.assertTrue({'A1','D1','CTX'}<=set(hit['matchedParticipants'].values()))
        self.assertEqual(set(hit['matchedRelations']),{'DA','context:D1:CTX'})

    def test_v2_invariant_transition_and_applicability_are_distinct(self):
        p=definition();p['rules'][0].update(watch='predicate',predicate={'field':'tag','equals':'accepted'},operations=['removed'])
        self.setup_policy(p);M.entities(self.g)['CTX']['tags']=['accepted']
        ev=self.do('edit',{'nodeId':'CTX','changes':{'tags':[]},'cosmetic':False})
        self.assertTrue(any(h.get('bindingId')=='B-V2' for h in ev['dependencyImpacts']))
        self.assertTrue(self.g['dependencyBindings'][0]['enabled'])

    def test_v2_shared_context_retains_both_matching_parent_paths(self):
        p=definition();p['targetKinds']=['requirement'];p['roles']=[{'id':'target','kinds':['requirement']},
            {'id':'parents','kinds':['decision'],'required':True,'selector':{'anchor':'target','relation':'INTRODUCES','direction':'in','minDepth':1,'maxDepth':1}},
            {'id':'source','kinds':['context'],'required':False,'selector':{'anchor':'parents','relation':'DECISION_CONTEXT','direction':'in','minDepth':1,'maxDepth':1}}]
        self.add_node('T','requirement');self.add_node('CTX','context',value='old')
        for ident in ('D1','D2'):
            self.add_node(ident,'decision',decisionContextIds=['CTX']);self.relation('P-'+ident,'INTRODUCES',ident,'T')
        b=binding();b.update(targetId='T',participantBindings={})
        self.do('policy_change',{'action':'policy_save','value':p});self.do('policy_change',{'action':'binding_save','value':b})
        ev=self.do('edit',{'nodeId':'CTX','changes':{'value':'new'},'cosmetic':False})
        hits=[h for h in ev['dependencyImpacts'] if h.get('bindingId')=='B-V2'];self.assertEqual(len(hits),1)
        self.assertTrue({'D1','D2','CTX','T'}<=set(hits[0]['matchedParticipants'].values()))
        self.assertEqual(set(hits[0]['matchedRelations']),{'P-D1','P-D2','context:D1:CTX','context:D2:CTX'})

    def test_v2_disabled_binding_cannot_invent_a_participant_or_invalid_snapshot(self):
        self.setup_policy();b=binding();b.update(id='BAD',enabled=False,participantBindings={'source':'MISSING'})
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'INAPPLICABLE'):
            self.do('policy_change',{'action':'binding_save','value':b})
        self.assertEqual(before,self.g)
        b.update(participantBindings={'source':'CTX'},violations='not-a-list')
        with self.assertRaisesRegex(ValueError,'VIOLATIONS'):
            self.do('policy_change',{'action':'binding_save','value':b})
        self.assertEqual(before,self.g)

    def test_v2_registry_covers_all_kind_watch_operation_families(self):
        K=M.for_profile('rdg-decision-v1');cap=K.dependency_capabilities()
        for builtin in K.POLICIES.builtins(K):K.POLICIES.validate_definition(builtin,K)
        self.assertEqual(set(cap['entityKinds']),K.ENTITY_KINDS)
        self.assertEqual(set(cap['events']),K.EVENT_TYPES)
        self.assertTrue(K.RELATION_TYPES<=set(r['id'] for r in cap['relations']))
        for row in cap['combinations']:
            p=definition();p['sourceKinds']=[row['sourceKind']];p['roles'][1]['kinds']=[row['sourceKind']]
            for operation in row['operations']:
                rule=p['rules'][0];rule.update(watch=row['watch'],operations=[operation])
                rule.pop('eventType',None);rule.pop('predicate',None)
                if row['watch']=='event':rule['eventType']=cap['events'][0]
                if row['watch']=='predicate':rule['predicate']={'field':'tag','equals':'watched'}
                with self.subTest(kind=row['sourceKind'],watch=row['watch'],operation=operation):K.POLICIES.validate_definition(p,K)
        bad=definition();bad['rules'][0]['watch']='selection'
        with self.assertRaisesRegex(ValueError,'OPERATION_WATCH'):K.POLICIES.validate_definition(bad,K)

    def test_v2_descriptions_cover_every_executable_choice(self):
        K=M.for_profile('rdg-decision-v1');cap=K.dependency_capabilities()
        for family in ('relations','observations','eventDescriptions'):
            for item in cap[family]:
                with self.subTest(family=family,item=item['id']):
                    self.assertTrue(item['name']);self.assertTrue(item['description'])
                    self.assertNotEqual(item['name'],item['id'])
                    if family!='eventDescriptions':self.assertTrue(item['example'])
                    if family=='observations':self.assertEqual(set(item['operations']),set(item['operationLabels']))
        self.assertEqual({e['id'] for e in cap['eventDescriptions']},set(cap['events']))
        self.assertEqual(set(cap['policyHelp']),{p['id'] for p in K.POLICIES.builtins(K)})
        self.assertEqual(len({p['description'] for p in K.POLICIES.builtins(K)}),len(K.POLICIES.builtins(K)))
        for help in cap['policyHelp'].values():
            for field in ('name','description','applicability','observes','example'):self.assertTrue(help[field])

    def test_v2_l2_context_has_same_meaning_in_both_storage_forms(self):
        self.add_node('D1','decision',decisionContextIds=['CTX']);self.add_node('CTX','context',value='old')
        self.add_node('TARGET','requirement');K=M.for_profile('rdg-decision-v1')
        before=copy.deepcopy(self.g);modern=copy.deepcopy(before)
        K.entities(modern)['D1']['decisionContextIds']=[]
        modern['edges'].append({'id':'CTX-D','type':'DEPENDS_ON','from':'CTX','to':'D1','dependencyPurpose':'decisionContext','dependencyLevel':'L1'})
        self.assertEqual(K._native_direct_scope(before,'D1'),K._native_direct_scope(modern,'D1'))
        p=self.policy(watch='directScope');p['sourceKinds']=['decision']
        self.g=modern;self.do('policy_change',{'action':'policy_save','value':p})
        self.do('policy_change',{'action':'binding_save','value':self.binding(target='TARGET',source='D1')})
        ev=self.do('edit',{'nodeId':'CTX','changes':{'value':'new'},'cosmetic':False})
        self.assertTrue(any(h.get('bindingId')=='B1' and h['triggerOperation']=='changed' for h in ev['dependencyImpacts']))

    def test_v2_automatic_context_records_actual_operation_rule_and_member(self):
        self.add_node('D1','decision',decisionContextIds=[]);self.add_node('R2','requirement')
        self.add_node('CTX','context',value='old');self.relation('D-R','INTRODUCES','D1','R2')
        def hits(ev):return [h for h in ev.get('dependencyImpacts',[]) if h.get('policyId')=='builtin:structural']
        ev=self.do('edit',{'nodeId':'D1','changes':{'decisionContextIds':['CTX'],'contextNotes':{'CTX':'Material observed condition'}},'cosmetic':False})
        self.assertEqual([(h['ruleId'],h['triggerOperation'],h['sourceId']) for h in hits(ev)],[('context-membership','added','CTX')])
        self.assertEqual(hits(ev)[0]['matchedParticipants']['parentId'],'D1')
        ev=self.do('edit',{'nodeId':'CTX','changes':{'value':'changed'},'cosmetic':False})
        self.assertEqual([(h['ruleId'],h['triggerOperation']) for h in hits(ev)],[('context-content','changed')])
        ev=self.do('edit',{'nodeId':'D1','changes':{'decisionContextIds':[]},'cosmetic':False})
        self.assertEqual([(h['ruleId'],h['triggerOperation'],h['sourceId']) for h in hits(ev)],[('context-membership','removed','CTX')])

        # A Requirement parent cannot be the source of a Decision withdrawal.
        K=M.for_profile('rdg-decision-v1');structural=next(p for p in K.POLICIES.builtins(K) if p['id']=='builtin:structural')
        root_graph=copy.deepcopy(self.g);root_graph['edges'].append({'id':'ROOT-D','type':'DRIVES','from':'R1','to':'D1'})
        bound=self.binding(target='D1',source='R1')
        self.assertFalse(K.POLICIES.role_impacts(root_graph,copy.deepcopy(root_graph),structural,bound,K,event={'type':'decision_unselected','nodeIds':['R1']}))

    def test_v2_canon_attachment_is_not_recorded_as_content_change(self):
        self.add_node('CAN','canon',guidance='Criteria')
        ev=self.do('link',{'relation':{'id':'CAN-R','type':'CANON_FOR','from':'CAN','to':'R1'}})
        hit=next(h for h in ev['dependencyImpacts'] if h.get('policyId')=='builtin:automatic-canon')
        self.assertEqual((hit['ruleId'],hit['triggerOperation']),('canon-attached','added'))
        self.assertEqual(hit['ruleSnapshot']['memberRole'],'source')
        ev=self.do('edit',{'nodeId':'CAN','changes':{'guidance':'New criteria'},'cosmetic':False})
        hit=next(h for h in ev['dependencyImpacts'] if h.get('policyId')=='builtin:automatic-canon')
        self.assertEqual((hit['ruleId'],hit['triggerOperation']),('definition','changed'))

    def test_v2_kind_guard_member_filter_and_legacy_info_are_executable(self):
        K=M.for_profile('rdg-decision-v1');self.add_node('D1','decision');self.add_node('CAN','canon',guidance='Criteria')
        self.add_node('INFO','info',value='old');self.add_node('OTHER','canon',guidance='Other')
        self.relation('CAN-D','CANON_FOR','CAN','D1');self.relation('INFO-CAN','INFO_FOR','INFO','CAN')
        legacy=K._effective_observable(self.g,'D1',{'watch':['info']},set())['info']
        self.assertEqual(K.POLICIES.observation(self.g,'D1',{'watch':'canonInfo'},K),K._projection_item_index(legacy,'info'))
        p=copy.deepcopy(next(p for p in K.POLICIES.builtins(K) if p['id']=='builtin:automatic-canon'))
        p.update(id='USER-CAN',origin='user',relations=[]);p.pop('automatic')
        b=binding();b.update(policyId='USER-CAN',participantBindings={'source':'CAN'})
        before=copy.deepcopy(self.g);after=copy.deepcopy(before);after['edges'].append({'id':'OTHER-D','type':'CANON_FOR','from':'OTHER','to':'D1'})
        self.assertFalse(K.POLICIES.role_impacts(before,after,p,b,K),'a bound Canon must not react to another Canon attachment')
        p=definition();p['roles'][1]['kinds']=['requirement','context'];p['sourceKinds']=['requirement','context'];p['rules'][0]['whenKinds']=['context']
        K.POLICIES.validate_definition(p,K);b=binding();b['participantBindings']={'source':'R1'}
        after=copy.deepcopy(before);K.entities(after)['R1']['description']='new root text'
        self.assertFalse(K.POLICIES.role_impacts(before,after,p,b,K))

    def test_v2_alternative_relations_and_contradictory_predicates(self):
        p=definition();p['roles'][1]['selector']={'anchor':'target','relation':['CONTEXT_FOR','DECISION_CONTEXT'],
            'direction':'in','minDepth':1,'maxDepth':1};p['roles'][1]['required']=False
        K=M.for_profile('rdg-decision-v1');K.POLICIES.validate_definition(p,K)
        self.add_node('D1','decision',decisionContextIds=['CTX']);self.add_node('CTX','context')
        b=binding();b['participantBindings']={}
        self.assertEqual(K.POLICIES.resolve(self.g,p,b,K)[0]['source'],['CTX'])
        bad=definition();bad['roles'][1]['conditions']=[{'field':'active','equals':True},{'field':'active','equals':False}]
        bad['roles'][1]['kinds']=['requirement'];bad['sourceKinds']=['requirement']
        with self.assertRaisesRegex(ValueError,'CONTRADICTORY'):K.POLICIES.validate_definition(bad,K)

    def test_v2_all_relation_kind_pairs_match_in_both_directions(self):
        K=M.for_profile('rdg-decision-v1')
        for rel,(left,right) in K.POLICIES.relation_pairs(K).items():
            for a in sorted(left):
                for b in sorted(right):
                    for direction in ('in','out'):
                        with self.subTest(relation=rel,left=a,right=b,direction=direction):
                            g=copy.deepcopy(self.g);g['nodes']=[];g['objects']=[];g['externalActions']=[];g['edges']=[];g['decisionGroups']=[];g['workGraphs']=[]
                            x={'id':'X','kind':a,'title':'X','revision':1};y={'id':'Y','kind':b,'title':'Y','revision':1}
                            for n in (x,y):
                                if n['kind']=='action':n.update(targetIds=[],groupIds=[])
                                g['nodes' if n['kind'] in K.NODE_KINDS else 'objects'].append(n)
                            if rel=='FINDING_SUBJECT':y['subjectId']='X'
                            elif rel=='DECISION_MEMBER':g['decisionGroups']=[{'id':'DG','parentId':'X','members':[{'id':'GM','decisionId':'Y'}]}]
                            elif rel=='DECISION_CONTEXT':y['decisionContextIds']=['X']
                            elif rel=='ACTION_TARGET':x['targetIds']=['Y']
                            elif rel=='SHARED_WORK_GRAPH':g['workGraphs']=[{'id':'WG','memberIds':['X','Y']}]
                            else:g['edges']=[{'id':'XY','type':rel,'from':'X','to':'Y'}]
                            origin,expected=('X','Y') if direction=='out' else ('Y','X')
                            self.assertIn(expected,{i for i,_ in K.POLICIES.neighbors(g,K,origin,rel,direction)})

    def test_v2_every_observation_operation_family_executes(self):
        K=M.for_profile('rdg-decision-v1');cap=K.dependency_capabilities()
        for row in cap['combinations']:
            for operation in row['operations']:
                for target_kind in cap['targetKinds']:
                    with self.subTest(kind=row['sourceKind'],watch=row['watch'],operation=operation,target=target_kind):
                        g=copy.deepcopy(self.g)
                        self.add_node('OBS',row['sourceKind']);self.add_node('MEM','context',value='old')
                        self.add_node('CAN','canon',guidance='old');self.add_node('INF','info',value='old')
                        self.add_node('TGT',target_kind)
                        g=copy.deepcopy(self.g);self.g['nodes']=[n for n in self.g['nodes'] if n['id'] not in ('OBS','TGT')]
                        self.g['objects']=[n for n in self.g['objects'] if n['id'] not in ('OBS','MEM','CAN','INF','TGT')]
                        watch=row['watch'];p=definition();p['sourceKinds']=[row['sourceKind']];p['targetKinds']=[target_kind]
                        p['roles'][0]['kinds']=[target_kind];p['roles'][1]['kinds']=[row['sourceKind']]
                        r=p['rules'][0];r.update(watch=watch,operations=[operation]);b=binding();b.update(targetId='TGT',participantBindings={'source':'OBS'})
                        if watch=='membership':
                            p['roles'][1].update(required=False,selector={'anchor':'target','relation':'INFO_FOR','direction':'in','minDepth':1,'maxDepth':1})
                            # Membership semantics are independent of the relation's endpoint kind restrictions.
                            # Use a supported relation for the source kind in this synthetic execution family.
                            p['roles'][1]['selector']['relation']='SHARED_WORK_GRAPH';b['participantBindings']={}
                            g['workGraphs']=[{'id':'W','memberIds':['TGT','OBS']}] if operation=='removed' else []
                        if watch=='predicate':r['predicate']={'field':'tag','equals':'watched'};K.entities(g)['OBS']['tags']=['watched'] if operation=='removed' else []
                        if watch=='event':r['eventType']='edited'
                        if watch=='canonInfo' and row['sourceKind']=='decision':g['edges'].append({'id':'CAN-LINK','type':'CANON_FOR','from':'CAN','to':'OBS'})
                        if watch in ('directScope','structuralScope','context','canon','info','canonInfo','relations','workGraphs','rootCauses') and operation!='added':
                            if watch in ('directScope','structuralScope'):g['edges'].append({'id':'OBS-M','type':'REQUIRES_ACTION' if watch=='structuralScope' and row['sourceKind']=='action' else 'DRIVES' if watch=='structuralScope' and row['sourceKind']=='decision' else 'DERIVES' if watch=='structuralScope' else 'CONTEXT_FOR','from':'R1' if watch=='structuralScope' else 'MEM','to':'OBS'})
                            elif watch=='context':K.entities(g)['OBS']['decisionContextIds']=['MEM']
                            elif watch=='canon':g['edges'].append({'id':'OBS-M','type':'CANON_FOR','from':'CAN','to':'OBS'})
                            elif watch in ('info','canonInfo'):g['edges'].append({'id':'OBS-M','type':'INFO_FOR','from':'INF','to':'CAN' if watch=='canonInfo' and row['sourceKind']=='decision' else 'OBS'})
                            elif watch=='relations':g['edges'].append({'id':'OBS-M','type':'INFO_FOR','from':'INF','to':'OBS'})
                            elif watch=='workGraphs':g['workGraphs']=[{'id':'W','memberIds':['OBS']}]
                            elif watch=='rootCauses':g['rootCauses'].append({'id':'OBS-ROOT','requirementId':'OBS','reason':'before'})
                        after=copy.deepcopy(g)
                        if watch=='definition':K.entities(after)['OBS']['description']='changed'
                        elif watch=='selection':K.entities(after)['OBS']['selectionState']='selected'
                        elif watch=='result':K.entities(after)['OBS']['result']={'state':'confirmed','truth':'true'}
                        elif watch=='locks':K.entities(after)['OBS']['locks']={'edit':{'mode':'warning','message':'changed'}}
                        elif watch=='predicate':K.entities(after)['OBS']['tags']=[] if operation=='removed' else ['watched']
                        elif watch=='membership':after['workGraphs']=[] if operation=='removed' else [{'id':'W','memberIds':['TGT','OBS']}]
                        elif watch in ('context','canon','info','canonInfo','directScope','structuralScope','relations'):
                            if operation=='changed':
                                if watch=='structuralScope':
                                    parent='OBS' if row['sourceKind']=='requirement' else 'R1';member='OBS' if row['sourceKind']=='decision' else 'DG-DECISION'
                                    if member=='DG-DECISION':g['nodes'].append({'id':member,'kind':'decision','title':member,'description':'Group fixture','revision':1,'selectionState':'unselected','result':{'state':'open','truth':'unknown'}})
                                    group={'id':'OBS-GROUP','title':'Group','parentId':parent,'members':[{'id':'GM','decisionId':member}],'mutuallyExclusive':False,'selectionRequired':False}
                                    g['decisionGroups']=[group];after['nodes']=copy.deepcopy(g['nodes']);after['decisionGroups']=[{**group,'selectionRequired':True}]
                                elif watch=='relations':after['edges'][-1]['to']='TGT'
                                else:K.entities(after)[{'context':'MEM','canon':'CAN','info':'INF','canonInfo':'INF','directScope':'MEM'}[watch]]['description']='changed'
                            elif watch=='context':K.entities(after)['OBS']['decisionContextIds']=['MEM'] if operation=='added' else []
                            elif operation=='removed':after['edges']=[e for e in after['edges'] if e['id']!='OBS-M']
                            else:
                                source='R1' if watch=='structuralScope' else 'CAN' if watch=='canon' else 'MEM' if watch=='directScope' else 'INF';typ=('REQUIRES_ACTION' if row['sourceKind']=='action' else 'DRIVES' if row['sourceKind']=='decision' else 'DERIVES') if watch=='structuralScope' else 'CANON_FOR' if watch=='canon' else 'CONTEXT_FOR' if watch=='directScope' else 'INFO_FOR'
                                after['edges'].append({'id':'OBS-M','type':typ,'from':source,'to':'CAN' if watch=='canonInfo' and row['sourceKind']=='decision' else 'OBS'})
                        elif watch=='workGraphs':
                            # An area's title is not a membership change; changed is tested as a false positive below.
                            if operation=='changed':continue
                            after['workGraphs']=[{'id':'W','memberIds':['OBS']}] if operation=='added' else []
                        elif watch=='rootCauses':
                            if operation=='changed':after['rootCauses'][-1]['reason']='changed'
                            elif operation=='removed':after['rootCauses']=[c for c in after['rootCauses'] if c['requirementId']!='OBS']
                            else:after['rootCauses'].append({'id':'OBS-ROOT','requirementId':'OBS','reason':'added'})
                        event={'type':'edited','nodeIds':['OBS']}
                        hits=K.POLICIES.role_impacts(g,after,p,b,K,event=event)
                        self.assertTrue(hits,'supported observation must execute, not merely serialize')
                        self.assertTrue(all(h['dependentId']=='TGT' and h['triggerOperation']==operation for h in hits))

    def test_v2_automatic_relation_restoration_does_not_reactivate(self):
        self.add_node('R2','requirement');self.relation('RR','DERIVES','R1','R2')
        self.do('unlink',{'edgeId':'RR'})
        state=next(s for s in self.g['dependencyAutomaticStates'].values() if s['targetId']=='R2')
        self.do('link',{'relation':{'id':'RR-NEW','type':'DERIVES','from':'R1','to':'R2'}})
        self.do('edit',{'nodeId':'R1','changes':{'description':'new content'},'cosmetic':False})
        self.assertFalse(any(h['dependentId']=='R2' for h in self.g['events'][-1].get('dependencyImpacts',[])))
        self.do('policy_change',{'action':'automatic_activate','value':{'id':state['id']}})
        self.do('edit',{'nodeId':'R1','changes':{'description':'another content'},'cosmetic':False})
        self.assertTrue(any(h['dependentId']=='R2' for h in self.g['events'][-1].get('dependencyImpacts',[])))

    def inspector_rows(self):
        K=M.for_profile('rdg-decision-v1')
        return K.POLICIES.describe_applications(self.g,K)

    def test_v2_inspector_is_read_only_and_keeps_pinned_policy_version(self):
        self.setup_policy();p=definition();p.update(version=2,name='New meaning',description='Version two description')
        self.do('policy_change',{'action':'policy_save','value':p})
        before=copy.deepcopy(self.g);row=next(r for r in self.inspector_rows() if r['id']=='B-V2')
        self.assertEqual(row['policyVersion'],1);self.assertEqual(row['policy']['name'],'Observe context')
        self.assertEqual(row['observedIds'],['CTX']);self.assertEqual(row['roles'][1]['ids'],['CTX'])
        self.assertEqual(self.g,before)

    def test_v2_inspector_exposes_multihop_intermediates_from_execution_trace(self):
        p=definition();p['roles'][1].update(required=True,selector={'anchor':'target','relation':'SHARED_WORK_GRAPH','direction':'out','minDepth':2,'maxDepth':2})
        b=binding();b['participantBindings']={}
        self.add_node('D1','decision');self.add_node('CTX','context',value='before');self.add_node('BRIDGE','requirement')
        self.g['workGraphs']=[{'id':'W1','title':'First','rootIds':['BRIDGE'],'memberIds':['D1','BRIDGE']},
            {'id':'W2','title':'Second','rootIds':['BRIDGE'],'memberIds':['BRIDGE','CTX']}]
        self.do('policy_change',{'action':'policy_save','value':p});self.do('policy_change',{'action':'binding_save','value':b})
        row=next(r for r in self.inspector_rows() if r['id']=='B-V2')
        self.assertEqual(row['observedIds'],['CTX']);self.assertIn('BRIDGE',row['nodeIds'])
        path=next(path for path in row['paths'] if path['role']=='source')
        self.assertEqual(set(path['nodeIds']),{'D1','BRIDGE','CTX'})
        self.assertEqual(set(path['relationIds']),{'workGraph:W1','workGraph:W2'})
        self.assertEqual({r['type'] for r in row['relations']},{'SHARED_WORK_GRAPH'})
        ev=self.event('remove intermediate')
        self.g,_=M.apply(self.g,{'schemaVersion':1,'expectedRevision':self.g['revision'],
            'operations':[{'op':'graph_edit','action':'core_remove','data':{'nodeIds':['BRIDGE']},'event':ev}]},True,coordinated=True)
        row=next(r for r in self.inspector_rows() if r['id']=='B-V2')
        self.assertFalse(row['enabled']);self.assertFalse(row['participants']['BRIDGE']['present'])
        self.assertTrue(row['participants']['BRIDGE']['recorded'])

    def test_v2_inspector_alternative_relation_loss_is_disabled_not_type_error(self):
        self.add_node('D1','decision');self.add_node('CTX','context',value='before')
        self.relation('CTX-D','CONTEXT_FOR','CTX','D1')
        p=definition();p['relations']=[{'from':'source','to':'target','type':['CONTEXT_FOR','DECISION_CONTEXT']}]
        self.do('policy_change',{'action':'policy_save','value':p});self.do('policy_change',{'action':'binding_save','value':binding()})
        self.do('unlink',{'edgeId':'CTX-D'})
        row=next(r for r in self.inspector_rows() if r['id']=='B-V2')
        self.assertEqual(row['status'],'disabled');self.assertFalse(row['applicable'])
        self.assertTrue(any(x.startswith('RELATION_MISSING:source:') for x in row['currentViolations']))
        self.assertTrue(next(r for r in row['relations'] if r['id']=='CTX-D')['historicalOnly'])
        self.do('link',{'relation':{'id':'RESTORED','type':'CONTEXT_FOR','from':'CTX','to':'D1'}})
        row=next(r for r in self.inspector_rows() if r['id']=='B-V2')
        self.assertTrue(row['applicable']);self.assertFalse(row['enabled']);self.assertTrue(row['violations'])
        self.assertIn('RESTORED',{r['id'] for r in row['relations']})

    def test_v2_inspector_deleted_participant_is_recorded_without_invented_live_role(self):
        self.setup_policy();ev=self.event('remove mandatory context')
        self.g,_=M.apply(self.g,{'schemaVersion':1,'expectedRevision':self.g['revision'],
            'operations':[{'op':'graph_edit','action':'core_remove','data':{'nodeIds':['CTX']},'event':ev}]},True,coordinated=True)
        row=next(r for r in self.inspector_rows() if r['id']=='B-V2')
        self.assertEqual(row['roles'][1]['ids'],[]);self.assertEqual(row['roles'][1]['configuredId'],'CTX')
        self.assertFalse(row['participants']['CTX']['present']);self.assertTrue(row['participants']['CTX']['recorded'])
        self.assertEqual(row['participants']['CTX']['title'],'CTX');self.assertEqual(row['status'],'disabled')

    def test_v2_inspector_automatic_context_members_are_outgoing_sources(self):
        self.add_node('D1','decision',decisionContextIds=['CTX']);self.add_node('CTX','context',value='before')
        self.add_node('R2','requirement');self.relation('D-R','INTRODUCES','D1','R2')
        row=next(r for r in self.inspector_rows() if r['policyId']=='builtin:structural' and r['targetId']=='R2')
        self.assertIn('CTX',row['observedIds']);self.assertEqual(row['roles'][2]['ids'],['CTX'])
        self.assertEqual({r['id'] for r in row['relations']},{'D-R','context:D1:CTX'})

    def test_v2_inspector_automatic_disabled_application_survives_restored_relation(self):
        self.add_node('R2','requirement');self.relation('RR','DERIVES','R1','R2');self.do('unlink',{'edgeId':'RR'})
        row=next(r for r in self.inspector_rows() if r['policyId']=='builtin:structural' and r['targetId']=='R2')
        self.assertFalse(row['enabled']);self.assertFalse(row['applicable']);key=row['id']
        self.do('link',{'relation':{'id':'NEW-RR','type':'DERIVES','from':'R1','to':'R2'}})
        row=next(r for r in self.inspector_rows() if r['id']==key)
        self.assertTrue(row['applicable']);self.assertFalse(row['enabled'])
        self.do('policy_change',{'action':'automatic_activate','value':{'id':key,'expectedRevision':row['binding']['revision']}})
        active=next(r for r in self.inspector_rows() if r['id']==key)
        self.assertTrue(active['enabled']);self.assertNotIn('RR',{r['id'] for r in active['relations']})

    def test_v2_inspector_legacy_context_deduplicates_and_info_keeps_canon_meaning(self):
        self.add_node('D1','decision',decisionContextIds=['CTX']);self.add_node('CTX','context',value='before')
        self.add_node('R2','requirement');self.add_node('CAN','canon',guidance='Criteria');self.add_node('INF','info',value='Fact')
        self.relation('CAN-D','CANON_FOR','CAN','D1');self.relation('INF-CAN','INFO_FOR','INF','CAN')
        self.g['edges'] += [{'id':'DEP-C','type':'DEPENDS_ON','from':'CTX','to':'D1','dependencyPurpose':'decisionContext','dependencyLevel':'L1'},
            {'id':'DEP-I','type':'DEPENDS_ON','from':'D1','to':'R2','dependencyRule':{'preset':'custom','watch':['info']}}]
        rows=self.inspector_rows()
        self.assertEqual(len([r for r in rows if r['kind'] in ('legacy','legacy-context') and r['binding']['sourceId']=='CTX' and r['targetId']=='D1']),1)
        context_row=next(r for r in rows if r['id']=='DEP-C');self.assertTrue(context_row['decisionContext'])
        self.assertEqual(context_row['legacyEdgeId'],'DEP-C')
        row=next(r for r in rows if r['id']=='DEP-I');self.assertIn('INF',row['observedIds'])
        self.assertEqual(row['rules'][0]['displayWatch'],'canonInfo');self.assertEqual(row['policyId'],'legacy:custom')
        self.assertIn('CAN',row['nodeIds']);self.assertNotIn('CAN',row['observedIds'])
        self.assertTrue({'CAN-D','INF-CAN'}<={r['id'] for r in row['relations']})
        self.assertTrue(any(path.get('kind')=='observation' and path.get('watch')=='canonInfo' for path in row['paths']))


    def test_v2_instances_keep_each_actor_with_its_observed_members(self):
        self.add_node('D1','decision')
        for suffix in ('2','3'):
            self.add_node('D'+suffix,'decision');self.add_node('CAN'+suffix,'canon',guidance='Criteria '+suffix)
            self.relation('CAN-D'+suffix,'CANON_FOR','CAN'+suffix,'D'+suffix)
        self.g['workGraphs']=[{'id':'OBS-WG','title':'Observed peers','rootIds':[],'memberIds':['D1','D2','D3']}]
        p=definition();p['sourceKinds']=['decision'];p['roles'][1]={'id':'source','kinds':['decision'],'required':True,
            'selector':{'anchor':'target','relation':'SHARED_WORK_GRAPH','direction':'out','minDepth':1,'maxDepth':1}}
        p['rules'][0].update(watch='canon',operations=['changed'])
        b=binding();b['participantBindings']={}
        self.do('policy_change',{'action':'policy_save','value':p});self.do('policy_change',{'action':'binding_save','value':b})
        before=copy.deepcopy(self.g);row=next(row for row in self.inspector_rows() if row['id']=='B-V2')
        points=row['rules'][0]['observations']
        self.assertEqual({point['actorId']:point['memberIds'] for point in points},{'D2':['CAN2'],'D3':['CAN3']})
        self.assertEqual({point['actorId']:point['relationIds'] for point in points},{'D2':['CAN-D2'],'D3':['CAN-D3']})
        self.assertEqual(self.g,before)

    def test_v2_instances_preserve_per_context_source_watch_settings(self):
        self.add_node('D1','decision',decisionContextIds=['CTX','D2']);self.add_node('D2','decision')
        self.add_node('CTX','context',value='Data');self.add_node('R2','requirement')
        self.relation('PARENT','INTRODUCES','D1','R2')
        self.g['edges'].append({'id':'D-CONTEXT','type':'DEPENDS_ON','from':'D2','to':'D1','dependencyPurpose':'decisionContext',
            'dependencyRule':{'preset':'custom','watch':['selection']}})
        row=next(row for row in self.inspector_rows() if row['policyId']=='builtin:structural' and row['targetId']=='R2')
        point=next(rule for rule in row['rules'] if rule['id']=='context-content')['observations'][0]
        self.assertEqual(point['actorId'],'D1')
        self.assertEqual({source['sourceId']:source['watches'] for source in point['contextSources']},{'CTX':['definition'],'D2':['selection']})
        self.assertIn('D2',point['memberIds']);self.assertIn('CTX',point['memberIds'])



    def invalidation_rows(self):
        K=M.for_profile('rdg-decision-v1')
        return K.POLICIES.describe_invalidation(self.g,K)

    def test_v2_invalidation_review_groups_causes_and_keeps_resolution_cycles(self):
        self.setup_policy()
        first=self.do('edit',{'nodeId':'CTX','changes':{'value':'one'},'cosmetic':False})
        second=self.do('edit',{'nodeId':'CTX','changes':{'value':'two'},'cosmetic':False})
        before=copy.deepcopy(self.g);rows=self.invalidation_rows();self.assertEqual(self.g,before)
        current=[r for r in rows if r['kind']=='review' and r['targetId']=='D1' and r['active']]
        self.assertEqual(len(current),1);self.assertEqual({c['eventId'] for c in current[0]['causes']},{first['id'],second['id']})
        reviewed=self.do('review',{'nodeId':'D1','observed':M.pins(self.g,'D1'),'basis':'Verified actual sources'})
        self.assertEqual(reviewed['reviewResolutions'],[{'nodeId':'D1','causeEventIds':[first['id'],second['id']]}])
        self.do('edit',{'nodeId':'CTX','changes':{'title':'Renamed source'},'cosmetic':True})
        third=self.do('edit',{'nodeId':'CTX','changes':{'value':'three'},'cosmetic':False})
        rows=[r for r in self.invalidation_rows() if r['kind']=='review' and r['targetId']=='D1']
        self.assertEqual(len(rows),2)
        old=next(r for r in rows if not r['active']);self.assertEqual(old['resolvedEventId'],reviewed['id'])
        self.assertEqual(old['participants']['CTX']['title'],'CTX');self.assertTrue(old['participants']['CTX']['recorded'])
        self.assertEqual(next(r for r in rows if r['active'])['causes'][0]['eventId'],third['id'])

    def test_v2_invalidation_disabled_cycles_wait_for_activation_and_keep_history(self):
        p=definition();p['relations']=[{'from':'source','to':'target','type':'CONTEXT_FOR'}]
        self.add_node('D1','decision');self.add_node('CTX','context',value='before');self.relation('REL','CONTEXT_FOR','CTX','D1')
        self.do('policy_change',{'action':'policy_save','value':p});self.do('policy_change',{'action':'binding_save','value':binding()})
        removed=self.do('unlink',{'edgeId':'REL'})
        transition=removed['dependencyTransitions'][0];self.assertEqual(transition['targetId'],'D1')
        self.assertEqual(transition['participantRoles']['source'],['CTX']);self.assertEqual(transition['relationSnapshot'][0]['id'],'REL')
        frozen=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'INAPPLICABLE'):self.do('policy_change',{'action':'binding_activate','value':{'id':'B-V2'}})
        self.assertEqual(frozen,self.g)
        self.do('link',{'relation':{'id':'RESTORED','type':'CONTEXT_FOR','from':'CTX','to':'D1'}})
        self.do('edit',{'nodeId':'CTX','changes':{'value':'disabled edit'},'cosmetic':False})
        row=next(r for r in self.invalidation_rows() if r['kind']=='disabled' and r['bindingId']=='B-V2')
        self.assertTrue(row['active']);self.assertTrue(row['applicable']);self.assertEqual(row['eventId'],removed['id'])
        activated=self.do('policy_change',{'action':'binding_activate','value':{'id':'B-V2'}})
        row=next(r for r in self.invalidation_rows() if r['kind']=='disabled' and r['bindingId']=='B-V2')
        self.assertFalse(row['active']);self.assertEqual(row['resolvedEventId'],activated['id'])
        self.do('unlink',{'edgeId':'RESTORED'})
        deleted=self.do('policy_change',{'action':'binding_remove','value':{'id':'B-V2'}})
        rows=[r for r in self.invalidation_rows() if r['kind']=='disabled' and r['bindingId']=='B-V2']
        self.assertEqual(len(rows),2);self.assertFalse(any(r['active'] for r in rows))
        self.assertEqual({r['resolution'] for r in rows},{'activated','deleted'})
        self.assertTrue(any(r['resolvedEventId']==deleted['id'] for r in rows))

    def test_v2_invalidation_disabled_edit_keeps_original_version_and_participants(self):
        self.setup_policy();self.add_node('D2','decision');self.add_node('OTHER','context',value='other')
        disabled=self.do('policy_change',{'action':'binding_disable','value':{'id':'B-V2'}})
        p=definition();p.update(version=2,name='Second version');self.do('policy_change',{'action':'policy_save','value':p})
        value=copy.deepcopy(self.g['dependencyBindings'][0]);value.update(policyVersion=2,targetId='D2',participantBindings={'source':'OTHER'})
        self.do('policy_change',{'action':'binding_save','value':value})
        row=next(r for r in self.invalidation_rows() if r['kind']=='disabled' and r['bindingId']=='B-V2')
        self.assertEqual(row['targetId'],'D1');self.assertEqual(row['policyVersion'],1)
        self.assertEqual(row['currentTargetId'],'D2');self.assertEqual(row['currentPolicyVersion'],2)
        self.assertEqual(row['eventId'],disabled['id']);self.assertEqual(row['participantRoles']['source'],['CTX'])

    def test_v2_invalidation_automatic_removal_is_durable_and_cas_guarded(self):
        self.add_node('D1','decision');self.add_node('CAN','canon',guidance='Criteria');self.relation('CAN-D','CANON_FOR','CAN','D1')
        row=next(r for r in self.inspector_rows() if r['policyId']=='builtin:automatic-canon' and r['targetId']=='D1')
        key=row['id'];self.do('policy_change',{'action':'automatic_disable','value':{'id':key}})
        frozen=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'CAS'):self.do('policy_change',{'action':'automatic_remove','value':{'id':key,'expectedRevision':999}})
        self.assertEqual(self.g,frozen)
        M.entities(self.g)['CAN']['locks']={'dependency_remove':{'mode':'hard','principals':['owner:key'],'message':'Protect dependency'}}
        locked=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'LOCK_REQUIRED'):self.do('policy_change',{'action':'automatic_remove','value':{'id':key}})
        self.assertEqual(self.g,locked);M.entities(self.g)['CAN'].pop('locks')
        self.do('policy_change',{'action':'automatic_remove','value':{'id':key,'expectedRevision':self.g['dependencyAutomaticStates'][key]['revision']}})
        self.assertEqual(self.g['dependencyAutomaticStates'][key]['status'],'deleted')
        self.assertFalse(any(r['id']==key for r in self.inspector_rows()))
        row=next(r for r in self.invalidation_rows() if r['kind']=='disabled' and r['bindingId']==key)
        self.assertEqual(row['resolution'],'deleted');self.assertFalse(row['active'])
        self.do('edit',{'nodeId':'CAN','changes':{'guidance':'New'},'cosmetic':False})
        self.assertFalse(any(h.get('bindingId')==key for h in self.g['events'][-1].get('dependencyImpacts',[])))
        with self.assertRaisesRegex(ValueError,'DELETED'):self.do('policy_change',{'action':'automatic_activate','value':{'id':key}})

    def test_v2_invalidation_legacy_missing_evidence_is_not_fabricated(self):
        self.setup_policy();event=self.do('edit',{'nodeId':'CTX','changes':{'value':'one'},'cosmetic':False})
        hit=next(h for h in event['dependencyImpacts'] if h.get('bindingId')=='B-V2')
        sparse={k:hit[k] for k in ('edgeId','sourceId','dependentId','level','changedParts')}
        self.g['events'][-1]['dependencyImpacts']=[sparse]
        row=next(r for r in self.invalidation_rows() if r['kind']=='review' and r['targetId']=='D1')
        self.assertEqual(row['policyVersions'],[]);self.assertNotIn('ruleSnapshot',row['causes'][0]['hits'][0])
        self.assertFalse(row['participants']['CTX']['recorded'])
        self.g['events']=[e for e in self.g['events'] if e['id']!=event['id']]
        row=next(r for r in self.invalidation_rows() if r['kind']=='review' and r['targetId']=='D1')
        self.assertIsNone(row['causes'][0]['recordedAt']);self.assertEqual(row['causes'][0]['hits'],[])

    def test_v2_invalidation_manual_disable_records_event_time_snapshot(self):
        self.setup_policy();ev=self.do('policy_change',{'action':'binding_disable','value':{'id':'B-V2'}})
        self.do('edit',{'nodeId':'CTX','changes':{'title':'Later title'},'cosmetic':True})
        row=next(r for r in self.invalidation_rows() if r['kind']=='disabled' and r['bindingId']=='B-V2')
        self.assertEqual(row['participants']['CTX']['title'],'CTX');self.assertTrue(row['targetRecorded'])
        old=copy.deepcopy(ev);old['dependencyTransitions'][0]={k:v for k,v in old['dependencyTransitions'][0].items() if k not in ('targetId','participantRoles','relationSnapshot')}
        M.for_profile('rdg-decision-v1')._validate_event(old)
        invalid=copy.deepcopy(ev);invalid['dependencyTransitions'][0]['participantRoles']={'source':'not a list'}
        with self.assertRaisesRegex(ValueError,'TRANSITIONS'):M.for_profile('rdg-decision-v1')._validate_event(invalid)

class PolicyApplication(API.DecisionIntegration):
    def setup_shared(self):
        ident=self.decision();self.command(ident,'add',entity={'id':'CTX','kind':'context','title':'Context','description':'Before','value':'before'})
        self.command(ident,'policy_change',action='policy_save',value=definition())
        self.command(ident,'policy_change',action='binding_save',value=binding())
        return ident

    def test_v2_inspector_api_read_is_local_authorized_and_survives_restart(self):
        ident=self.setup_shared();other=self.app().request(self.req('create',path='working/inspector-other',role='working',title='Other',scope='Synthetic',coreModel='rdg-decision-v1',rootReason='Inspector isolation'))['packages'][0]['packageId']
        before=self.sources();read=self.app().read(ident);self.assertEqual(before,self.sources())
        rows=read['dependencyCatalog']['localApplications'];row=next(r for r in rows if r['id']=='B-V2')
        self.assertEqual(row['policyVersion'],1);self.assertEqual(row['observedIds'],['CTX'])
        self.assertEqual(rows,self.app().read(ident)['dependencyCatalog']['localApplications'])
        grant=self.authority.manage('issue',self.admin,{'permissions':['graph.read'],'scopes':['packages/'+self.namespace+'/'+ident]})
        scoped=self.app(grant['token']).read(ident)['dependencyCatalog'];self.assertFalse(scoped['available'])
        self.assertEqual(scoped['localApplications'],rows)
        self.assertEqual(scoped['invalidationRecords'],read['dependencyCatalog']['invalidationRecords'])
        self.assertNotIn(other,str(scoped['invalidationRecords']))
        self.assertTrue(all(r['packageId']==ident for r in scoped['applications']))
        self.assertNotIn(other,str(scoped['localApplications']))

    def test_v2_shared_catalog_cross_process_and_restarted_reader(self):
        ident=self.setup_shared()
        second=self.app().request(self.req('create',path='working/other',role='working',title='Other',scope='Synthetic',coreModel='rdg-decision-v1',rootReason='Test shared policy'))['packages'][0]['packageId']
        self.command(second,'add',entity={'id':'D1','kind':'decision','title':'Other decision','description':'Synthetic'})
        self.command(second,'add',entity={'id':'CTX','kind':'context','title':'Other context','description':'Synthetic','value':'before'})
        self.assertIn('POL-V2',{p['id'] for p in self.app().read(second)['dependencyCatalog']['policies']})
        self.command(second,'policy_change',action='binding_save',value=binding())
        self.command(second,'edit',nodeId='CTX',changes={'value':'after'},cosmetic=False)
        self.assertTrue(self.app().read(second)['graph']['nodes'][1]['review']['required'])
        reg=self.app().registry()['registry'];self.assertEqual(len(reg['dependencyPolicies']),1)
        self.assertEqual(self.current(ident)['graph']['dependencyBindings'][0]['policyVersion'],1)

    def test_v2_global_status_update_is_atomic_and_manual_resume_required(self):
        ident=self.setup_shared();before=self.sources()
        req=self.command_request(ident,'policy_change',action='policy_status',value={'id':'POL-V2','version':1,'status':'disabled'})
        preview=self.app().request(req,preflight=True);self.assertEqual(before,self.sources())
        self.app().request(req,expected_input_binding=preview['inputBinding'])
        b=self.current(ident)['graph']['dependencyBindings'][0];self.assertFalse(b['enabled']);self.assertEqual(b['reasonCode'],'policy')
        self.command(ident,'policy_change',action='policy_status',value={'id':'POL-V2','version':1,'status':'active'})
        self.assertFalse(self.current(ident)['graph']['dependencyBindings'][0]['enabled'])
        self.command(ident,'policy_change',action='binding_activate',value={'id':'B-V2'})
        self.assertTrue(self.current(ident)['graph']['dependencyBindings'][0]['enabled'])

    def test_v2_shared_catalog_cas_rejects_without_partial_graph_change(self):
        ident=self.setup_shared();p=definition();p['version']=2
        req=self.command_request(ident,'policy_change',action='policy_save',value=p)
        req['expectedDependencyCatalogRevision']=-1;before=self.sources()
        with self.assertRaisesRegex(ValueError,'CATALOG_CAS'):self.app().request(req)
        self.assertEqual(before,self.sources())

    def test_v2_version_two_can_be_first_use_in_another_process(self):
        self.setup_shared();p=definition();p['version']=2;p['name']='Version two'
        first=next(r['packageId'] for r in self.app().catalog()['packages'] if r['path']=='working/decision')
        self.command(first,'policy_change',action='policy_save',value=p)
        other=self.app().request(self.req('create',path='working/v2-first',role='working',title='First use v2',scope='Synthetic',coreModel='rdg-decision-v1',rootReason='Version pin test'))['packages'][0]['packageId']
        for ident,kind in [('D1','decision'),('CTX','context')]:self.command(other,'add',entity={'id':ident,'kind':kind,'title':ident,'description':'Synthetic',**({'value':'before'} if kind=='context' else {})})
        b=binding();b['policyVersion']=2;self.command(other,'policy_change',action='binding_save',value=b)
        self.assertEqual(self.current(other)['graph']['dependencyBindings'][0]['policyVersion'],2)
        self.assertEqual(len(self.app().registry()['registry']['dependencyPolicies']),2)

    def test_v2_catalog_graph_interrupted_publication_recovers_exactly_once(self):
        ident=self.decision();p=definition()
        req=self.command_request(ident,'policy_change',action='policy_save',value=p)
        def fail(stage):
            if stage=='head:1':raise RuntimeError('Synthetic policy participant interruption')
        with self.assertRaisesRegex(RuntimeError,'participant'):self.app().request(req,failpoint=fail)
        with self.assertRaises(ValueError):self.app().read(ident)
        self.app().recover(req['transactionId']);self.assertTrue(self.app().request(req)['idempotent'])
        self.assertEqual(len(self.app().registry()['registry']['dependencyPolicies']),1)
        self.assertEqual(self.current(ident)['graph']['dependencyPolicies'][0]['id'],'POL-V2')

    def test_v2_catalog_write_requires_namespace_scope_without_leaking_others(self):
        ident=self.setup_shared()
        grant=self.authority.manage('issue',self.admin,{'permissions':['graph.read','graph.write'],
            'scopes':['packages/'+self.namespace+'/'+ident]})
        app=self.app(grant['token']);read=app.read(ident)
        self.assertFalse(read['dependencyCatalog']['available'])
        self.assertTrue(all(r['packageId']==ident for r in read['dependencyCatalog']['applications']))
        p=definition();p['version']=2;req=self.command_request(ident,'policy_change',action='policy_save',value=p)
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'SCOPE_DENIED'):app.request(req)
        self.assertEqual(before,self.sources())

    def test_v2_explicit_legacy_catalog_migration_preserves_presets_and_conflicts(self):
        self.setup_shared()
        graph=M.blank('legacy-policy-owner','Legacy policies',self.namespace,'R1','Root','Synthetic',
            core_model='rdg-decision-v1',root_reason='Legacy fixture')
        local=definition();local['description']='Independent legacy policy with colliding ID'
        graph['dependencyPolicies']=[local]
        graph['dependencyPresets']=[{'id':'OLD-PRESET','name':'Previously saved policy','sourceKinds':['context'],
            'watch':['definition'],'operations':['changed']}]
        ident=self.app().request(self.req('create',path='working/legacy-catalog',role='working',graph=graph,
            title='Legacy fixture',coreModel='rdg-decision-v1',rootReason='Test explicit migration'))['packages'][0]['packageId']
        req=self.command_request(ident,'policy_change',action='catalog_migrate',value={})
        self.app().request(req);self.assertTrue(self.app().request(req)['idempotent'])
        current=self.current(ident)['graph'];self.assertEqual(current['dependencyPresets'],[])
        self.assertNotEqual(current['dependencyPolicyAliases']['POL-V2'],'POL-V2')
        policies=self.app().registry()['registry']['dependencyPolicies']
        self.assertEqual(len(policies),3)
        self.assertTrue(any(p['name']=='Previously saved policy' for p in policies))


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(cls(name) for cls in (PolicyKernel,PolicyApplication)
        for name in loader.getTestCaseNames(cls) if name.startswith('test_v2_'))


if __name__=='__main__':unittest.main(verbosity=2)
