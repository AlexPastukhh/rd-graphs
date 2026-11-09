#!/usr/bin/env python3
"""Synthetic legacy Finding payload compatibility; new writable surface is in rdg-analysis.test.py."""
import copy
import hashlib
import json
from pathlib import Path
from importlib.machinery import SourceFileLoader
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
M=SourceFileLoader('finding_test_profiles',str(ROOT/'tools/rdg-model-profiles.py')).load_module()
K=M.for_profile('rdg-decision-v1')

def legacy_construct(g, command, data, event, K):
    """Recreate an old persisted payload; never called by the product writer."""
    ns=K.entities(g);fid=data.get('findingId',data.get('nodeId'));f=ns.get(fid)
    K.require(f is not None and f['kind']=='finding','FINDING_REQUIRED')
    K.require(set(data) <= {'findingId', 'decisionId', 'title', 'description', 'parentDecisionId', 'workGraphId', 'impactTargetIds'}, 'FINDING_DECISION_FIELDS')
    K.guard(f, event, 'link')
    parent_id = f['subjectId'] if command == 'finding_response' else data.get('parentDecisionId')
    parent = ns.get(parent_id)
    K.require(parent is not None, 'FINDING_PARENT_REQUIRED')
    K.guard(parent, event, 'link')
    if command == 'finding_proposal':
        K.require(any(e['type'] == 'FINDING_RESPONSE' and e['to'] == parent_id and e.get('findingId') == fid for e in g['edges']), 'FINDING_RESPONSE_REQUIRED')
    ident = data.get('decisionId');K.require(K.text(ident), 'NEW_ENTITY')
    existing=ns.get(ident)
    if existing is not None:
        K.require(existing['kind']=='decision' and existing in g['nodes'],'FINDING_DECISION_REQUIRED');K.guard(existing,event,'link')
    K.require(K.text(data.get('title')) and isinstance(data.get('description', ''), str), 'NEW_ENTITY_TEXT')
    n = {'id': ident, 'kind': 'decision', 'title': data['title'], 'description': data.get('description', ''),
         'revision': 1, 'selectionState': 'discovered', 'result': {'state': 'open', 'truth': 'unknown'},
         'findingOrigin': {'findingId': fid, 'subjectId': f['subjectId'], 'title': f['title'],
                           'role': 'response' if command == 'finding_response' else 'proposal'}}
    if 'impactTargetIds' in data:
        K.require(K.unique_strings(data['impactTargetIds']) and set(data['impactTargetIds'])<=set(ns),'PROPOSAL_IMPACT_TARGETS')
        K.require(existing is None,'EDIT_EXISTING_IMPACT_SEPARATELY');n['impactTargetIds']=copy.deepcopy(data['impactTargetIds'])
    if existing is None:g['nodes'].append(n)
    elif 'findingOrigin' not in existing:
        K.guard(existing,event,'edit');existing['findingOrigin']=n['findingOrigin'];existing['revision']+=1
    # IDs are derived from a preallocated Decision ID, so exact retries are stable.
    edge = {'id': 'FREL-' + uuid.uuid5(uuid.NAMESPACE_URL,command+':'+fid+':'+parent_id+':'+ident).hex, 'type': 'FINDING_RESPONSE' if command == 'finding_response' else 'FINDING_PROPOSAL',
            'from': parent_id, 'to': ident, 'findingId': fid}
    K._validate_new_relation(g, edge);g['edges'].append(edge);rels = [edge['id']]
    if command == 'finding_proposal':
        ctx = {'id': 'FCTX-' + uuid.uuid5(uuid.NAMESPACE_URL,fid+':'+ident).hex, 'type': 'DEPENDS_ON', 'from': fid, 'to': ident,
               'dependencyPurpose': 'decisionContext', 'dependencyRule': {'preset': 'L1', 'watch': ['definition']}}
        if not any(e['type']=='DEPENDS_ON' and e['from']==fid and e['to']==ident and e.get('dependencyPurpose')=='decisionContext' for e in g['edges']):
            K._validate_new_relation(g, ctx);g['edges'].append(ctx);rels.append(ctx['id'])
    if data.get('workGraphId'):
        wg = next((w for w in g['workGraphs'] if w['id'] == data['workGraphId']), None)
        K.require(wg is not None, 'WORK_GRAPH_UNKNOWN')
        if ident not in wg['memberIds']:wg['memberIds'].append(ident)
    return {fid, parent_id, ident}, rels, None


class LegacyFixtureKernel:
    # Assemble old persisted payloads without enabling retired production commands.
    def __getattr__(self,name):return getattr(K,name)
    def _validate_new_relation(self,g,relation,new_id=None):
        K._relation_error(relation,K.entities(g));K.require(not any(e['id']==relation['id'] for e in g['edges']),'RELATION_ID_CONFLICT')

class Findings(unittest.TestCase):
    def setUp(self):
        self.g=M.blank('finding-test','Finding tests',str(uuid.uuid4()),'R','Goal','Synthetic scope',core_model='rdg-decision-v1',root_reason='Synthetic only')
    def event(self):
        t=str(uuid.uuid4())
        return {'id':str(uuid.uuid4()),'by':'assistant','note':'Synthetic finding check','recordedAt':'2026-11-06T00:00:00Z','verifiedTrustReceipt':{'mode':'test-only','transactionId':t}}
    def do(self,cmd,data,coordinated=False):
        if cmd in ('finding_response','finding_proposal'):
            g=copy.deepcopy(self.g);legacy_construct(g,cmd,data,self.event(),LegacyFixtureKernel());K.validate(g);self.g=g;return
        if cmd=='decision_group' and data.get('group',{}).get('parentId') in {n['id'] for n in self.g['nodes'] if n['kind']=='decision'}:
            g=copy.deepcopy(self.g);g['decisionGroups'].append(copy.deepcopy(data['group']));K.validate(g);self.g=g;return
        e=self.event()
        if cmd=='review':e['reviewPinContext']={'packageId':str(uuid.uuid4()),'graphRevision':self.g['revision'],'sha256':K._digest(self.g)}
        before=copy.deepcopy(self.g)
        try:self.g,_=M.apply(self.g,{'schemaVersion':1,'expectedRevision':self.g['revision'],'operations':[{'op':'graph_edit','action':'core_'+cmd,'data':data,'event':e}]},True,coordinated=coordinated)
        except Exception:
            self.assertEqual(before,self.g);raise
        return self.g['events'][-1]
    def add(self,i,kind,**fields):
        n={'id':i,'kind':kind,'title':i,'description':'Synthetic content',**fields}
        if kind=='requirement':n['scope']='Synthetic scope'
        if kind=='action':n.update(actionType='task',lowLevel=False,targetIds=[],groupIds=[])
        if kind=='evidence':
            n.update(claim='Observed test outcome',scope='Synthetic scope',version='1',source='Synthetic fixture',revision=1);self.g['objects'].append(n);K.validate(self.g);return
        self.do('add',{'entity':n})
    def finding(self,subject='R',ident='F',typ='problem'):
        n=K.entities(self.g)[subject]
        self.g['objects'].append({'id':ident,'kind':'finding','title':ident,'description':'Synthetic content','revision':1,'subjectId':subject,'subjectSnapshot':{**{k:n[k] for k in ('id','kind','title','revision')},'definition':K._native_definition(self.g,subject)},'findingType':typ,'rationale':'Confirmed fixture violation','evidenceIds':[],'disposition':{'code':'unresolved','basis':'','evidenceIds':[]},'dispositionHistory':[]})
        K.validate(self.g)
    def review_all(self):
        ids=[i for i,n in K.entities(self.g).items() if n.get('review',{}).get('required')]
        if ids:
            observed={k:v for i in ids for k,v in K.pins(self.g,i).items()}
            self.do('review',{'nodeIds':ids,'observed':observed,'basis':'Verified fixture inputs'})
    def response(self):self.do('finding_response',{'findingId':'F','decisionId':'RES','title':'Resolve fixture finding'})
    def proposal(self,ident='PROP'):self.do('finding_proposal',{'findingId':'F','parentDecisionId':'RES','decisionId':ident,'title':'Fixture proposal'})
    def disposition(self,code,**kw):
        self.do('finding_disposition',{'nodeId':'F','observed':K.pins(self.g,'F'),'disposition':{'code':code,'basis':'Verified fixture disposition','evidenceIds':[],**kw}})
    def test_legacy_types_and_subject_kinds_read_without_review_or_selection(self):
        self.add('D','decision');self.add('A','action')
        for subj in ('R','D','A'):
            for typ in K.FINDINGS.TYPES:
                self.finding(subj,subj+typ,typ)
                self.assertEqual(K.entities(self.g)[subj+typ]['disposition']['code'],'unresolved')
                self.assertFalse(K.entities(self.g)[subj+typ].get('review',{}).get('required'))
    def test_subject_content_invalidates_finding_with_named_cause(self):
        self.finding();self.do('edit',{'nodeId':'R','changes':{'description':'changed'},'cosmetic':False})
        self.assertTrue(K.entities(self.g)['F']['review']['required'])
        hit=next(h for h in self.g['events'][-1]['dependencyImpacts'] if h['dependentId']=='F')
        self.assertEqual(hit['policyId'],'builtin:finding-subject');self.assertEqual(hit['changedParts'],['definition'])
        row=next(r for r in K.POLICIES.describe_applications(self.g,K) if r['targetId']=='F')
        self.assertEqual(row['observedIds'],['R'])
    def test_cosmetic_and_review_do_not_invalidate_finding(self):
        self.finding();self.do('edit',{'nodeId':'R','changes':{'title':'cosmetic'},'cosmetic':True})
        self.assertFalse(K.entities(self.g)['F'].get('review',{}).get('required'))
    def test_paper_chain_creation_never_selects_or_executes(self):
        self.add('D','decision');self.finding('D');self.response();self.proposal();self.proposal('OTHER')
        for i in ('D','RES','PROP','OTHER'):
            self.assertEqual(K.entities(self.g)[i]['selectionState'],'discovered')
            self.assertEqual(K.entities(self.g)[i]['result']['state'],'open')
        self.assertFalse(any(e['type'] in ('decision_selected','action_executed') and any(i in e['nodeIds'] for i in ('RES','PROP','OTHER')) for e in self.g['events']))
        self.assertIn('F',[x['sourceId'] for x in K._context_sources(self.g,'PROP')])
    def test_selection_requires_basis_and_does_not_select_descendants(self):
        self.finding();self.response();self.proposal();self.review_all()
        self.do('select',{'nodeId':'RES'})
        self.assertEqual(K.entities(self.g)['PROP']['selectionState'],'discovered')
        self.review_all();self.do('select',{'nodeId':'PROP'})
        self.assertEqual(K.entities(self.g)['F']['disposition']['code'],'unresolved')
        self.do('withdraw',{'nodeId':'RES'})
        self.assertEqual(K.entities(self.g)['PROP']['selectionState'],'unselected')
    def test_unselected_subject_does_not_gain_implicit_root(self):
        self.add('D','decision');self.finding('D');self.response();self.review_all()
        with self.assertRaisesRegex(ValueError,'NO_ACTIVE_BASIS'):self.do('select',{'nodeId':'RES'})
    def test_review_stale_finding_does_not_recursively_invalidate_proposal(self):
        self.finding();self.response();self.proposal();self.review_all()
        self.do('edit',{'nodeId':'R','changes':{'description':'new'},'cosmetic':False})
        self.assertTrue(K.entities(self.g)['F']['review']['required'])
        self.assertFalse(K.entities(self.g)['PROP'].get('review',{}).get('required',False))
    def test_finding_content_invalidates_proposal_but_disposition_does_not(self):
        self.finding();self.response();self.proposal();self.review_all()
        self.disposition('deferred',revisitTrigger='Fixture trigger')
        self.assertFalse(K.entities(self.g)['PROP'].get('review',{}).get('required',False))
        self.do('edit',{'nodeId':'F','changes':{'description':'New finding content'},'cosmetic':False})
        self.assertTrue(K.entities(self.g)['PROP'].get('review',{}).get('required',False))
    def test_disposition_proof_and_review_are_separate(self):
        self.finding()
        with self.assertRaisesRegex(ValueError,'FINDING_OUTCOME_EVIDENCE_REQUIRED'):self.disposition('resolved')
        self.add('EV','evidence');self.disposition('resolved',evidenceIds=['EV'])
        self.assertEqual(K.entities(self.g)['F']['disposition']['code'],'resolved')
        with self.assertRaisesRegex(ValueError,'EDIT_FIELDS'):self.do('edit',{'nodeId':'F','changes':{'disposition':{'code':'resolved'}},'cosmetic':False})
    def test_disposition_pins_and_deferred_trigger_are_checked(self):
        self.finding()
        with self.assertRaisesRegex(ValueError,'FINDING_REVISIT_REQUIRED'):self.disposition('deferred')
        with self.assertRaisesRegex(ValueError,'REVIEW_INPUTS_CHANGED'):self.do('finding_disposition',{'nodeId':'F','observed':{},'disposition':{'code':'unresolved','basis':'x','evidenceIds':[]}})
    def test_legacy_questions_read_compatibly_but_require_explicit_migration(self):
        self.finding();q={'id':'Q','question':'Which constraint?','impact':'Changes proposal','blocking':'partially-blocking','scope':'','closeCondition':'User chooses'}
        K.entities(self.g)['F']['questions']=[q]
        with self.assertRaisesRegex(ValueError,'FINDING_QUESTION'):K.validate(self.g)
        q['scope']='Storage proposal';K.validate(self.g)
        with self.assertRaisesRegex(ValueError,'LEGACY_MIGRATION_REQUIRED'):self.do('edit',{'nodeId':'F','changes':{'questions':[]},'cosmetic':False})
    def test_removing_subject_preserves_finding_and_disables_application(self):
        self.add('D','decision');self.finding('D')
        self.do('remove',{'nodeIds':['D']},coordinated=True)
        self.assertEqual(K.entities(self.g)['F']['subjectSnapshot']['title'],'D')
        r=next(r for r in K.POLICIES.describe_applications(self.g,K) if r['targetId']=='F')
        self.assertFalse(r['enabled']);self.assertFalse(K.entities(self.g)['F'].get('review',{}).get('required'))
    def test_removing_finding_keeps_decisions_as_recorded_provenance(self):
        self.finding();self.response();self.proposal()
        self.do('remove',{'nodeIds':['F']},coordinated=True)
        self.assertTrue({'RES','PROP'}<=set(K.entities(self.g)))
        self.assertEqual(K.entities(self.g)['PROP']['findingOrigin']['findingId'],'F')
    def test_groups_for_proposals_are_explicit(self):
        self.finding();self.response();self.proposal();self.proposal('P2')
        self.do('decision_group',{'group':{'id':'G','parentId':'RES','title':'Choose one','selectionRequired':False,'mutuallyExclusive':True,'members':[{'id':'M1','decisionId':'PROP'},{'id':'M2','decisionId':'P2'}]}})
        self.review_all();self.do('select',{'nodeId':'RES'});self.review_all();self.do('select',{'nodeId':'PROP'});self.review_all()
        with self.assertRaisesRegex(ValueError,'DECISION_GROUP_CONFLICT'):self.do('select',{'nodeId':'P2'})
    def test_invalid_provenance_is_atomic(self):
        self.finding();self.response()
        with self.assertRaisesRegex(ValueError,'FINDING_RESPONSE_REQUIRED'):self.do('finding_proposal',{'findingId':'F','parentDecisionId':'R','decisionId':'BAD','title':'Invalid'})
        self.assertNotIn('BAD',K.entities(self.g))

    def test_additional_context_policy_uses_common_finding_target(self):
        self.finding();self.add('CTX','context',value='before')
        policy={'id':'EXTRA','version':1,'name':'Extra context','description':'Synthetic','status':'active','pattern':'direct','sourceKinds':['context'],'targetKinds':['finding'],'rules':[{'id':'content','name':'Content changed','watch':'definition','operations':['changed'],'enabled':True}]}
        self.do('policy_change',{'action':'policy_save','value':policy})
        self.do('policy_change',{'action':'binding_save','value':{'id':'B','policyId':'EXTRA','policyVersion':1,'sourceId':'CTX','targetId':'F','parentId':None,'enabled':True}})
        self.do('edit',{'nodeId':'CTX','changes':{'value':'after'},'cosmetic':False})
        self.assertTrue(K.entities(self.g)['F']['review']['required'])
        self.assertTrue(any(h.get('bindingId')=='B' for h in self.g['events'][-1]['dependencyImpacts']))
    def test_default_application_restoration_stays_disabled_until_activation(self):
        self.add('D','decision');self.finding('D');self.do('remove',{'nodeIds':['D']},coordinated=True);self.add('D','decision')
        row=next(r for r in K.POLICIES.describe_applications(self.g,K) if r['targetId']=='F')
        self.assertTrue(row['applicable']);self.assertFalse(row['enabled'])
        self.do('policy_change',{'action':'automatic_activate','value':{'id':row['id'],'expectedRevision':row['binding']['revision']}})
        self.do('edit',{'nodeId':'D','changes':{'description':'Restored content'},'cosmetic':False})
        self.assertTrue(K.entities(self.g)['F']['review']['required'])
    def test_completion_of_resolution_decisions_does_not_set_finding_resolved(self):
        self.finding();self.response();self.proposal();self.add('EV','evidence');self.review_all();self.do('select',{'nodeId':'RES'});self.review_all();self.do('select',{'nodeId':'PROP'});self.review_all()
        with self.assertRaisesRegex(ValueError,'OBLIGATIONS_OPEN'):self.do('complete',{'nodeId':'RES','basis':'Cannot skip proposal','evidenceIds':['EV']})
        self.do('complete',{'nodeId':'PROP','basis':'Verified proposal result','evidenceIds':['EV']});self.review_all();self.do('complete',{'nodeId':'RES','basis':'Verified resolution work','evidenceIds':['EV']})
        self.assertTrue(K.completion_state(self.g)['RES']['complete']);self.assertEqual(K.entities(self.g)['F']['disposition']['code'],'unresolved')
    def test_rootless_composition_cycle_cannot_select_itself(self):
        self.add('D1','decision');self.add('D2','decision');self.finding('D1','F');self.finding('D2','F2')
        self.do('finding_response',{'findingId':'F','decisionId':'D2','title':'Existing paper decision'})
        self.do('finding_response',{'findingId':'F2','decisionId':'D1','title':'Existing paper decision'})
        self.review_all()
        with self.assertRaisesRegex(ValueError,'NO_ACTIVE_BASIS'):self.do('select',{'nodeId':'D1'})
    def test_review_lock_blocks_disposition_without_partial_history(self):
        self.finding();f=K.entities(self.g)['F'];f['locks']={'review':{'mode':'hard','principals':['user'],'message':'Fixture review lock'}}
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'LOCK'):self.disposition('deferred',revisitTrigger='Later')
        self.assertEqual(before,self.g)
    def test_relative_scope_is_computed_without_persisting_level(self):
        self.add('D','decision');self.do('link',{'relation':{'id':'RD','type':'DRIVES','from':'R','to':'D'}});self.finding('R')
        before=copy.deepcopy(self.g)
        self.assertEqual(K.FINDINGS.describe(self.g,K,'D')[0]['relativeLevel'],'UPSTREAM')
        self.assertEqual(K.FINDINGS.describe(self.g,K,'R')[0]['relativeLevel'],'CURRENT');self.assertEqual(before,self.g)

    def test_proposal_impact_does_not_change_finding_relative_level(self):
        self.add('D','decision');self.do('link',{'relation':{'id':'RD','type':'DRIVES','from':'R','to':'D'}});self.finding('D');self.response()
        self.do('finding_proposal',{'findingId':'F','parentDecisionId':'RES','decisionId':'P','title':'Change upstream','impactTargetIds':['R']})
        row=K.FINDINGS.describe(self.g,K,'D')[0]
        self.assertEqual(row['relativeLevel'],'CURRENT');self.assertEqual(row['proposalImpacts'][0]['relativeLevel'],'UPSTREAM')
    def test_action_subject_has_ordinary_active_basis_for_resolution(self):
        self.add('A','action');self.do('link',{'relation':{'id':'RA','type':'REQUIRES_ACTION','from':'R','to':'A'}});self.finding('A');self.response();self.review_all()
        self.do('select',{'nodeId':'RES'});self.assertIn('RES',K.support_state(self.g)['activeIds'])
    def test_finding_evidence_must_exist_and_response_cannot_forge_origin(self):
        self.add('D','decision')
        with self.assertRaisesRegex(ValueError,'FINDING_EVIDENCE_REQUIRED'):self.add('F','finding',subjectId='D',findingType='problem',rationale='Fixture',evidenceIds=['invented'])
        with self.assertRaisesRegex(ValueError,'NEW_FINDING_ORIGIN_NOT_ALLOWED'):self.add('FAKE','decision',findingOrigin={'findingId':'invented','subjectId':'R','title':'invented','role':'proposal'})

    def test_ready_capture_rejects_process_finding_before_losing_refs(self):
        self.finding();portable=SourceFileLoader('finding_capture_model',str(ROOT/'tools/rdg-portable-model.py')).load_module()
        before=copy.deepcopy(self.g)
        with self.assertRaisesRegex(ValueError,'FINDING_PROCESS_ONLY'):portable.decision_template(self.g)
        self.assertEqual(before,self.g)

    def test_removing_subject_with_proposals_preserves_nodes_and_detaches_composition(self):
        self.add('D','decision');self.finding('D');self.response();self.proposal()
        self.do('remove',{'nodeIds':['D']},coordinated=True)
        self.assertTrue({'F','RES','PROP'}<=set(K.entities(self.g)))
        self.assertFalse(any(e['type'] in K.FINDINGS.RELATIONS for e in self.g['edges']))
        self.assertFalse(next(r for r in K.POLICIES.describe_applications(self.g,K) if r['targetId']=='F')['enabled'])
    def test_unlinking_response_detaches_proposals_without_deleting_decisions(self):
        self.finding();self.response();self.proposal();self.review_all();self.do('select',{'nodeId':'RES'});self.review_all();self.do('select',{'nodeId':'PROP'})
        edge=next(e for e in self.g['edges'] if e['type']=='FINDING_RESPONSE')
        self.do('unlink',{'edgeId':edge['id']})
        self.assertTrue({'RES','PROP'}<=set(K.entities(self.g)))
        self.assertEqual(K.entities(self.g)['RES']['selectionState'],'unselected');self.assertEqual(K.entities(self.g)['PROP']['selectionState'],'unselected')

if __name__=='__main__':unittest.main()
