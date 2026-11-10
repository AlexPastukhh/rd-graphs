#!/usr/bin/env python3
"""Core through real authenticated package writer, fresh CLI, Plan and history."""
from importlib.machinery import SourceFileLoader
import hashlib,json,os,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=SourceFileLoader('core_cli_fixture',str(ROOT/'tests/rdg-agent.test.py')).load_module()
M=BASE.A.CORE

class CoreWorkflow(unittest.TestCase):
    setUp=BASE.Operator.setUp
    cli=BASE.Operator.cli
    packet=BASE.Operator.packet
    graph=BASE.Operator.graph
    evidence=BASE.Operator.evidence
    state_bytes=BASE.Operator.state_bytes

    def new_workspace(self,env=None,extra=()):
        return BASE.Operator.new_workspace(self,env,('--core-model',*extra))

    def do(self,cmd,tid,**data):
        req={'action':'core_'+cmd,'transactionId':tid,'note':'Real isolated CLI check: '+cmd,
             'expectedGraphRevision':self.graph()['revision'],'data':data}
        if cmd in ('complete','falsify','review','resolve_finding'):req['evidenceRefs']=self.evidence()
        result=json.loads(self.cli('command',body=req).stdout)
        self.assertTrue(result['saved'],result)
        return result

    def add(self,i,kind='requirement',**kw):
        e={'id':i,'kind':kind,'title':kw.pop('title',i),**kw}
        if kind=='requirement':e.update(scope='Isolated current application',description=i)
        self.do('add','new-'+i,entity=e)

    def edge(self,t,a,b,i,origin='method_correctness'):
        edge={'id':i,'type':t,'from':a,'to':b}
        if t=='INTRODUCES' and origin is not None:edge['origin']={'role':origin}
        self.do('link','link-'+i,edge=edge)

    def review(self,tid):
        g=self.graph();ns=M.entities(g);ids=[i for i,n in ns.items() if n.get('review',{}).get('required')]
        if ids:self.do('review',tid,nodeIds=ids,observed={i:ns[i]['revision'] for j in ids for i in M.pins(g,j)})

    def test_actual_shared_identity_revisions_receipt_and_focused_views(self):
        self.add('R2');self.add('A','action');self.add('OUT');self.add('C','context',description='Internal network')
        self.edge('DRIVES','R0','A','d1');self.edge('DRIVES','R2','A','d2')
        self.edge('CONTEXT_FOR','C','A','ctx');self.edge('INTRODUCES','A','OUT','out')
        self.review('review-construction');self.do('select','choose-a',nodeId='A');self.review('review-output')
        p=self.packet(node='A')
        self.assertEqual({'R0','R2'},{s['id'] for s in p['focusedGraph']['situation'] if s['role']=='realized'})
        self.assertEqual(p['context']['coreModel'],'rdg-core-v1')
        self.assertNotIn('OUT',{n['id'] for n in self.packet(node='R0')['focusedGraph']['entities']})
        self.do('edit','r0-change',nodeId='R0',changes={'description':'Literal new requirement'})
        self.assertTrue(M.entities(self.graph())['A']['review']['required'])
        self.do('unlink','detach-r0',edgeId='d1');self.review('review-remaining')
        self.do('edit','r0-again',nodeId='R0',changes={'description':'Another change'})
        self.assertFalse(M.entities(self.graph())['A']['review']['required'])
        self.assertEqual(1,sum(n['id']=='A' for n in self.graph()['nodes']))
        receipt=json.loads(self.cli('receipt','--transaction-id','choose-a').stdout)
        self.assertTrue(receipt['found']);self.assertEqual(receipt['state'],'completed')
        self.assertEqual(self.graph()['revision'],receipt['currentGraphRevision'])

    def test_explicit_output_origin_through_authenticated_writer_and_fresh_cli(self):
        self.add('R2');self.add('A','action');self.add('OUT')
        self.edge('DRIVES','R0','A','d0');self.edge('DRIVES','R2','A','d2');self.edge('INTRODUCES','A','OUT','out',origin=None)
        req=json.loads(self.cli('schema','--action','core_output_origin','--node','A').stdout)['request']
        req.update(transactionId='qualify-origin',note='OUT is a subgoal only of R0; keep A terminal in the R0 graph')
        req['data']={'edgeId':'out','origin':{'role':'subgoal','requirementIds':['R0']}}
        self.assertTrue(json.loads(self.cli('command',body=req).stdout)['saved'])
        self.review('review-origin');self.do('select','choose-origin-a',nodeId='A');self.review('review-origin-selection')
        parent=self.packet(node='R0')['focusedGraph'];child=self.packet(node='OUT')['focusedGraph']
        self.assertNotIn('OUT',parent['terminalIds']);self.assertEqual(['OUT'],parent['completion']['R0']['blockers'])
        self.assertEqual([],parent['completion']['R2']['blockers']);self.assertNotIn('R2',[n['id'] for n in child['entities']])
        event=next(e for e in self.graph()['events'] if e['id']=='EV-qualify-origin')
        self.assertEqual(['R0'],event['newRelation']['origin']['requirementIds'])
        receipt=json.loads(self.cli('receipt','--transaction-id','qualify-origin').stdout)
        self.assertTrue(receipt['found']);self.assertEqual('completed',receipt['state'])

    def test_true_false_true_and_real_history_keep_ids(self):
        self.add('A','action');self.add('OUT');self.edge('DRIVES','R0','A','d');self.edge('INTRODUCES','A','OUT','o')
        self.review('review1');self.do('select','choose',nodeId='A');self.review('review2')
        self.do('complete','proof-out-1',nodeId='OUT');self.do('complete','proof-a-1',nodeId='A')
        original_ids={n['id'] for n in self.graph()['nodes']}
        self.do('falsify','loss-out',nodeId='OUT');self.review('review-loss')
        self.do('complete','proof-out-2',nodeId='OUT');self.do('complete','proof-a-2',nodeId='A')
        p=self.packet(node='A');events=p['history']
        self.assertEqual(original_ids,{n['id'] for n in self.graph()['nodes']})
        self.assertTrue(any(e['kind']=='requirement_falsified' for e in events))
        raw=self.graph()['events']
        self.assertEqual(2,sum(e['type']=='action_executed' for e in raw))
        self.assertEqual('OUT',next(e for e in raw if e['id']=='EV-loss-out')['after']['OUT']['id'])
        self.assertTrue(p['focusedGraph']['completion']['A']['complete'])

    def test_authenticated_text_only_lens_advice_and_lens_to_lens_reads(self):
        self.add('A-GUIDED','action',title='Assess whether the method fits')
        proposed=[{'lensKey':'review','targetId':'A-GUIDED',
                   'text':'During selection, check canon applicability with relevant R and Context.'},
                  {'lensKey':'clarify',
                   'text':'When goals are ambiguous, first clarify actual required truth.'}]
        before=self.graph();revision=before['revision']
        self.do('lens_recommendations','write-advice',recommendations=proposed)
        after=self.graph()
        self.assertEqual(revision+1,after['revision'])
        self.assertEqual(proposed,after['lensRecommendations'])
        self.assertEqual([n['result'] for n in before['nodes']],
                         [n['result'] for n in after['nodes']])
        event=next(e for e in after['events'] if e['id']=='EV-write-advice')
        self.assertEqual('core_lens_recommendations_changed',event['type'])
        packet=self.packet(lens='review',node='A-GUIDED')
        self.assertEqual(proposed,packet['lensRecommendations'])
        self.assertEqual('clarify',packet['lens']['lensRecommendations'][0]['lensKey'])
        receipt=json.loads(self.cli('receipt','--transaction-id','write-advice').stdout)
        self.assertEqual('completed',receipt['state'])
        request={'action':'core_lens_recommendations','transactionId':'bad-advice',
                 'expectedGraphRevision':after['revision'],'note':'Reject nonexistent local target',
                 'data':{'recommendations':[{'lensKey':'review','targetId':'not-a-node',
                                              'text':'Bad dangling reference'}]}}
        failed=json.loads(self.cli('command',body=request,ok=False).stdout)
        self.assertFalse(failed['saved'])
        self.assertEqual(after,self.graph())

    def test_necessity_decision_requires_actual_completed_action_and_preserves_history(self):
        self.add('CHECK-NEED','action',title='Check whether R0 remains necessary')
        self.edge('DRIVES','R0','CHECK-NEED','need-driver')
        self.review('review-need-method')
        req={'action':'core_requirement_state','transactionId':'need-too-early',
             'note':'Attempt without completed decision','expectedGraphRevision':self.graph()['revision'],
             'data':{'nodeId':'R0','state':'inactive','disposition':'Decision must be proven',
                     'decisionActionId':'CHECK-NEED'}}
        denied=self.cli('command',body=req,ok=False)
        self.assertFalse(json.loads(denied.stdout or denied.stderr)['saved'])
        self.do('select','select-need-method',nodeId='CHECK-NEED')
        self.do('complete','confirm-need-method',nodeId='CHECK-NEED')
        self.do('requirement_state','need-is-not-required',nodeId='R0',state='inactive',
                disposition='Verified that R0 is not needed for this work',decisionActionId='CHECK-NEED')
        g=self.graph()
        self.assertEqual('inactive',M.entities(g)['R0']['status'])
        ev=next(e for e in g['events'] if e['id']=='EV-need-is-not-required')
        self.assertEqual('CHECK-NEED',ev['decisionActionId'])
        self.assertTrue(any(e['type']=='action_executed' and e['targetId']=='CHECK-NEED' for e in g['events']))
        receipt=json.loads(self.cli('receipt','--transaction-id','need-is-not-required').stdout)
        self.assertEqual('completed',receipt['state'])
        self.do('requirement_state','need-again',nodeId='R0',state='active',
                disposition='New evidence changed the scope')
        self.assertEqual('active',M.entities(self.graph())['R0']['status'])

    def test_same_real_plan_ref_becomes_unresolved_on_stale(self):
        self.add('A','action');self.edge('DRIVES','R0','A','d');self.review('review');self.do('select','choose',nodeId='A')
        self.do('complete','a-done',nodeId='A')
        req={'action':'place','transactionId':'place-a','nodeId':'A','note':'Place existing shared Action',
             'expectedPlanRevision':1,'at':'2026-10-25'}
        result=json.loads(self.cli('command',body=req).stdout);self.assertTrue(result['saved'],result)
        self.assertTrue(any(r['reason']=='completed' for r in self.packet()['excludedPlacements']))
        self.do('edit','changed-goal',nodeId='R0',changes={'description':'Changed goal; actual method needs review'})
        p=self.packet();self.assertTrue(any(r['reason']=='dependency-review-required' for r in p['unresolved']))
        store=json.loads((self.home/'plan-owner'/BASE.PLAN).read_text())
        self.assertEqual(2,store['revision'])

    def test_canonical_writer_denies_unverified_evidence_and_generic_status(self):
        before=self.state_bytes()
        req={'action':'core_complete','transactionId':'bad-proof','note':'Must fail',
             'expectedGraphRevision':1,'data':{'nodeId':'R0'},'evidenceRefs':[{'path':'absent.txt','sha256':'0'*64}]}
        run=self.cli('command',body=req,ok=False);result=json.loads(run.stdout or run.stderr)
        self.assertFalse(result['saved']);self.assertEqual(before,self.state_bytes())
        req={'action':'core_edit','transactionId':'smuggle','note':'Must fail',
             'expectedGraphRevision':1,'data':{'nodeId':'R0','changes':{'status':'inactive'}}}
        run=self.cli('command',body=req,ok=False);result=json.loads(run.stdout or run.stderr)
        self.assertFalse(result['saved']);self.assertEqual(before,self.state_bytes())

    def test_schema_gives_core_shape_instead_of_legacy_or_invalid_node_fields(self):
        req=json.loads(self.cli('schema','--action','core_add','--node','R0').stdout)['request']
        self.assertNotIn('nodeId',req['data']);self.assertEqual(req['data']['entity']['kind'],'action')
        req.update(note='Candidate method from the supported schema')
        req['data']['entity']['title']='Compute the checked result'
        result=json.loads(self.cli('command',body=req).stdout);self.assertTrue(result['saved'],result)
        link=json.loads(self.cli('schema','--action','core_link','--node','R0').stdout)['request']
        self.assertEqual(set(link['data']),{'edge'});self.assertEqual(link['data']['edge']['from'],'R0')

    def test_manual_helper_uses_same_core_writer_and_keeps_receipt(self):
        helper=SourceFileLoader('core_manual_helper',str(self.home/'tools/rdg-workflow-helper.py')).load_module()
        editor=helper.Editor(self.home/'plan-owner',BASE.PLAN,self.home/'graphs',BASE.GRAPH,self.store,self.token,tools=self.home/'tools')
        req={'action':'core_edit','transactionId':'manual-edit','note':'Clarified real requirement scope',
             'expectedGraphRevision':1,'data':{'nodeId':'R0','changes':{'description':'Explicitly clarified assertion'}}}
        result=editor.dispatch(req);self.assertTrue(result['saved'])
        self.assertEqual(self.graph()['revision'],2)
        event=self.graph()['events'][-1];self.assertEqual(event['by'],'user')
        self.assertEqual(event['verifiedTrustReceipt']['mode'],'local-manual-session')
        self.assertTrue(editor.dispatch(req)['replayed']);self.assertEqual(self.graph()['revision'],2)

    def test_dependency_inventory_has_a_context_and_transitive_sources(self):
        self.add('A','action');self.add('OUT');self.add('N','action');self.add('C','context',description='Observed state')
        self.edge('DRIVES','R0','A','d');self.edge('CONTEXT_FOR','C','A','c')
        self.edge('INTRODUCES','A','OUT','o');self.edge('DRIVES','OUT','N','n')
        nodes,deps=BASE.A.DEP.inventory({BASE.GRAPH:self.graph()})
        self.assertTrue({(BASE.GRAPH,i) for i in ('R0','A','C','OUT')} <= set(deps[BASE.GRAPH,'N']))
        self.assertEqual(nodes[BASE.GRAPH,'C']['kind'],'context')

    def test_lenses_are_read_only_real_graphs_and_preserve_conditions_are_local(self):
        before=self.state_bytes()
        for lens in ('orient','clarify','explore','shape','preserve','work','review','handoff','operate','develop'):
            p=self.packet(lens)
            self.assertEqual(p['lens']['rootResult'],'unknown');self.assertEqual(p['lens']['graphWrites'],0)
            self.assertEqual(p['lens']['graph']['coreModel'],'rdg-core-v1')
        preserve=self.packet('preserve')['lens']['graph']
        self.assertFalse(any(n['id'].startswith('R-PRESERVE-C') for n in preserve['nodes']))
        self.assertTrue({'A-PRESERVE-DRAW','A-PRESERVE-SKIP'} <= {n['id'] for n in preserve['nodes']})
        self.assertEqual(before,self.state_bytes())

if __name__=='__main__':unittest.main()
