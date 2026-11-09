#!/usr/bin/env python3
"""B03A: scope, meaning, no writes, source-pinned pages and actual CLI."""
import copy
import io
import json
import os
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
T = SourceFileLoader('scoped_fixture', str(ROOT/'tests/rdg-compact-read.test.py')).load_module()
S = SourceFileLoader('scoped_reader_tests', str(ROOT/'tools/rdg-scoped-read.py')).load_module()


class ScopedReads(T.CompactReads):
    # Existing compact regression tests are inherited intentionally.
    def fixture(self):
        app = self.app()
        r = self.req('create', path='working/scoped', role='working', coreModel='rdg-decision-v1',
                     title='Scope test', scope='Synthetic', rootReason='Independent acceptance fixture')
        pid = app.request(r)['packages'][0]['packageId']
        steps = []
        def add(kind, ident, parents=(), **extra):
            links = [{'id': ident+'-'+str(j), 'type': rel, 'from': ident if rel.endswith('_FOR') else parent, 'to': parent if rel.endswith('_FOR') else ident}
                     for j, (rel, parent) in enumerate(parents)]
            entity = {'id': ident, 'kind': kind, 'title': ident, 'description': '', **extra}
            steps.append({'alias': ident.replace('-', '_'), 'op': 'core', 'command': 'add',
                          'data': {'entity': entity, **({'initialRelations': links} if links else {})}})
        add('requirement', 'R-STORE', [('DERIVES','R1')], scope='Store data')
        add('decision', 'D-SQL', [('DRIVES','R-STORE')])
        add('decision', 'D-FILE', [('DRIVES','R-STORE')])
        add('requirement', 'R-DDL', [('INTRODUCES','D-SQL')], scope='DDL')
        add('requirement', 'R-DEEP', [('DERIVES','R-DDL')], scope='Deep')
        add('action', 'A-DEEP', [('REQUIRES_ACTION','R-DEEP')], actionType='task', lowLevel=False,
            description='# Free instructions\n\nRequirements and alternatives stay text.\n' * 40,
            resultCondition='A real result', estimates={'time':{'minSeconds':0,'maxSeconds':60}})
        add('decision', 'D-TEMP', [('DRIVES','R1')])
        add('requirement', 'R-SAFE', [('DERIVES','R1'),('INTRODUCES','D-TEMP')], scope='Safety')
        add('requirement', 'R-SHARED', [('DERIVES','R-DDL'),('DERIVES','R-SAFE')], scope='Shared')
        add('context','C-LOAD', value='1000 requests/sec')
        add('canon','CAN-SQL', [('CANON_FOR','D-SQL')], guidance='General',
            canons='Check consistency', knownErrors=[{'id':'ERR','title':'Wrong assumption','description':'Check basis'}])
        add('info','INFO', [('INFO_FOR','CAN-SQL')], value='Detailed explanation')
        add('finding','F', subjectId='D-SQL', findingType='problem', rationale='A recorded issue', evidenceIds=[])
        batch = app.schema('batch', pid)['request']; batch.update(note='Synthetic scoped fixture', steps=steps)
        app.request(batch)
        self.command(pid,'decision_context',nodeId='D-SQL',sourceId='C-LOAD',action='save',comment='Measured input')
        graph = app.snapshot(pid,layouts=False)['graph']
        self.command(pid,'add',entity={'id':'Q','kind':'question','title':'How much?', 'description':'',
            'relatedRefs':[app.model.reference(pid,graph,'F')],'sourceRefs':[], 'impact':'Affects the choice',
            'answerCondition':'A measured answer'})
        return pid

    def read_scope(self,pid,detail,root,**options):
        return S.read_pages(self.app(), {'method':'read','packageId':pid,'detail':detail,
                            'nodeId':root,**options},True)

    def bodies(self,r):
        return {v['entity']['id']:v['entity'] for v in r['data']['entities']['items']}

    def test_focus_matches_existing_scope_and_keeps_root_parents_brief(self):
        pid=self.fixture();g=self.app().snapshot(pid,layouts=False)['graph'];K=self.app().kernel.for_graph(g)
        for root in ('D-SQL','R-STORE','R-SAFE','R1','A-DEEP','F','Q'):
            r=self.read_scope(pid,'focus',root,limit=2);old=K.focused_view(g,root)
            ids=set(self.bodies(r));brief_parents={p['nodeId'] for p in r['data']['parents']['items']}
            for item in old['entities']:
                if item['id'] not in brief_parents:
                    self.assertIn(item['id'],ids)
            self.assertEqual({e['id'] for e in r['data']['edges']['items']},
                             {e['id'] for e in old['edges']})
            self.assertTrue(r['reading']['pagesComplete'])
        d=self.read_scope(pid,'focus','D-SQL')
        self.assertNotIn('D-FILE',self.bodies(d));self.assertNotIn('R-DEEP',self.bodies(d))
        self.assertNotIn('R-STORE',self.bodies(d))
        self.assertEqual(d['data']['parents']['items'][0]['title'],'R-STORE')
        self.assertEqual(d['data']['entities']['items'][0]['entity']['id'],'D-SQL')

    def test_branch_closure_boundary_parents_and_single_bodies(self):
        pid=self.fixture()
        self.command(pid,'work_graph',workGraph={'id':'WG','title':'Narrow area','rootIds':['R-STORE'],'memberIds':['R-STORE','D-SQL']})
        r=self.read_scope(pid,'branch','R-STORE',limit=2)
        expected={'R-STORE','D-SQL','D-FILE','R-DDL','R-DEEP','A-DEEP','R-SHARED'}
        rows=r['data']['outline']['items']
        self.assertEqual({v['nodeId'] for v in rows},expected)
        self.assertNotIn('R1',self.bodies(r));self.assertNotIn('R-SAFE',self.bodies(r))
        self.assertEqual(len(self.bodies(r)),len(r['data']['entities']['items']))
        boundary=next(e for e in r['data']['edges']['items'] if e['from']=='R-SAFE')
        self.assertEqual(boundary['fromEndpoint']['title'],'R-SAFE')
        self.assertEqual(boundary['fromEndpoint']['bodyState'],'referenceOnly')
        full=self.read_scope(pid,'branch','R1',limit=2)
        shared=[v for v in full['data']['outline']['items'] if v['nodeId']=='R-SHARED']
        self.assertEqual(len(shared),2);self.assertEqual([x['reason'] for x in shared],[None,'shared'])
        self.assertEqual(sum(v['entity']['id']=='R-SHARED' for v in full['data']['entities']['items']),1)

    def test_data_quality_theory_info_findings_questions_and_full_markdown(self):
        pid=self.fixture();before=self.sources();r=self.read_scope(pid,'focus','D-SQL',limit=1)
        ns=self.bodies(r)
        self.assertEqual(ns['C-LOAD']['value'],'1000 requests/sec')
        self.assertEqual(ns['CAN-SQL']['canons'],'Check consistency')
        self.assertEqual(ns['CAN-SQL']['guidance'],'General')
        self.assertEqual(ns['CAN-SQL']['knownErrors'][0]['title'],'Wrong assumption')
        self.assertEqual(ns['INFO']['value'],'Detailed explanation')
        self.assertEqual(ns['Q']['answerCondition'],'A measured answer')
        self.assertEqual(r['data']['findings']['items'][0]['source']['nodeId'],'F')
        self.assertEqual(r['data']['context']['items'][0]['comment'],'Measured input')
        self.assertEqual(r['data']['completion']['items'][0]['nodeId'],'D-SQL')
        a=self.read_scope(pid,'branch','R-DEEP');body=self.bodies(a)['A-DEEP']
        self.assertEqual(body['description'],'# Free instructions\n\nRequirements and alternatives stay text.\n'*40)
        self.assertEqual(body['resultCondition'],'A real result')
        self.assertEqual(before,self.sources())

    def test_pages_distinguish_pending_missing_and_not_requested(self):
        pid=self.fixture();app=self.app();msg={'method':'read','packageId':pid,'detail':'branch','nodeId':'R1','limit':1}
        self.assertFalse(app.call({**msg,'include':['plan']})['plan']['available'])
        first=app.call(msg)
        self.assertTrue(first['data']['entities']['page']['hasMore'])
        self.assertEqual(first['data']['entities']['items'][0]['entity']['id'],'R1')
        context=first['data']['context']['items'][0]['source']
        self.assertEqual(context['bodyState'],'pendingPage')
        only=app.call({**msg,'include':['context']})
        self.assertEqual(only['data']['context']['items'][0]['source']['bodyState'],'notRequested')
        self.assertFalse(only['loaded']['entities'])
        assembled=S.read_pages(app,msg,True)
        self.assertEqual(assembled['data']['context']['items'][0]['source']['bodyState'],'loaded')
        initial_ids=[x['entity']['id'] for x in assembled['data']['entities']['items']]
        self.assertEqual(initial_ids,[x['entity']['id'] for x in self.read_scope(pid,'branch','R1',limit=100)['data']['entities']['items']])
        token=first['data']['entities']['page']['nextCursor']
        again=self.app().call({**msg,'include':['entities'],'cursor':token})
        repeat=self.app().call({**msg,'include':['entities'],'cursor':token})
        self.assertEqual(again,repeat)
        with self.assertRaisesRegex(ValueError,'FIRST_PAGE'):S.read_pages(app,{**msg,'include':['entities'],'cursor':token},True)

    def test_cursor_scope_change_stale_and_revocation(self):
        pid=self.fixture();app=self.app();msg={'method':'read','packageId':pid,'detail':'branch','nodeId':'R1','include':['entities'],'limit':1}
        token=app.call(msg)['data']['entities']['page']['nextCursor']
        for wrong in ({'detail':'focus'},{'nodeId':'R-STORE'},{'include':['outline']},{'cursor':'bad'},{'limit':0}):
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):app.call({**msg,'cursor':token,**wrong})
        self.command(pid,'edit',nodeId='R1',changes={'description':'New version'},cosmetic=False)
        with self.assertRaisesRegex(ValueError,'CURSOR_STALE'):self.app().call({**msg,'cursor':token})
        new_token=self.app().call(msg)['data']['entities']['page']['nextCursor']
        self.authority.manage('revoke',self.admin,{'id':self.grant_id})
        with self.assertRaises(ValueError):self.app().call({**msg,'cursor':new_token})

    def test_all_pages_aborts_instead_of_mixing_versions(self):
        pid=self.fixture();app=self.app();outer=self
        class Changed:
            first=True
            def call(inner,msg):
                if not inner.first:
                    outer.command(pid,'edit',nodeId='R1',changes={'description':'Concurrent change'},cosmetic=False)
                inner.first=False
                return app.call(msg)
        with self.assertRaisesRegex(ValueError,'CURSOR_STALE'):
            S.read_pages(Changed(),{'method':'read','packageId':pid,'detail':'branch','nodeId':'R1','limit':1},True)

    def test_no_full_projection_catalog_or_layout_and_bounded_response(self):
        pid=self.fixture();app=self.app()
        with patch.object(app,'_read_projection',side_effect=AssertionError('full forbidden')), \
             patch.object(app,'dependency_applications',side_effect=AssertionError('namespace inventory forbidden')), \
             patch.object(app,'layout',side_effect=AssertionError('visual forbidden')):
            r=app.read(pid,detail='focus',node_id='D-SQL',include=['entities','context'],limit=100)
        before=copy.deepcopy(r)
        self.command(pid,'add',entity={'id':'UNRELATED','kind':'info','title':'Unrelated','description':'','value':'x'*50000})
        after=app.read(pid,detail='focus',node_id='D-SQL',include=['entities','context'],limit=100)
        self.assertNotIn('UNRELATED',self.bodies(after))
        # Pins change, semantic records do not acquire unrelated data.
        self.assertEqual({i:n for i,n in self.bodies(before).items()},{i:n for i,n in self.bodies(after).items()})
        self.assertLess(len(json.dumps(after)),len(json.dumps(before))+1000)
        for options in ({'node_id':'MISSING'},{'node_id':'A-DEEP'},{'node_id':'D-SQL','include':['planForks']}):
            with self.assertRaises(ValueError):app.read(pid,detail='branch',**options)
        with self.assertRaisesRegex(ValueError,'VIEW_FILTER'):
            app.read(pid,detail='focus',node_id='D-SQL',view={'kind':'focus','id':'D-SQL'})


    def test_real_branch_cycle_is_a_reference_and_invalid_endpoint_still_fails(self):
        pid=self.fixture();app=self.app()
        self.command(pid,'link',relation={'id':'CYCLE','type':'DERIVES','from':'R-SHARED','to':'R-STORE'})
        result=self.read_scope(pid,'branch','R-STORE',include=['entities','edges','outline'],limit=2)
        self.assertEqual(sum(x['reason']=='cycle' for x in result['data']['outline']['items']),1)
        self.assertEqual(sum(x['entity']['id']=='R-STORE' for x in result['data']['entities']['items']),1)
        before=self.sources()
        with self.assertRaises(ValueError):
            self.command(pid,'link',relation={'id':'INVALID','type':'DERIVES','from':'R-STORE','to':'MISSING'})
        self.assertEqual(before,self.sources())

    def test_iterative_walker_cycle_and_deep_shared_graph(self):
        links=[{'id':str(i),'type':'DERIVES','from':str(i),'to':str(i+1)} for i in range(5000)]
        links += [{'id':'back','type':'DERIVES','from':'5000','to':'2'},
                  {'id':'shared','type':'DERIVES','from':'0','to':'5000'}]
        order,rows=S.walk('0',links,{str(i) for i in range(5001)})
        self.assertEqual(len(order),5001);self.assertEqual(len(rows),5003)
        self.assertEqual([r['reason'] for r in rows if r['reason']],['cycle','shared'])


    def test_external_action_subject_pins_plan_pages_and_source_access(self):
        pid=self.fixture();app=self.app()
        request=app.schema('create',core_model='rdg-decision-v1',role='lens')['request']
        request.update(path='lenses/read-subject',role='lens',lensKey='work',rootReason='Synthetic source',
                       graph=json.loads((ROOT/'tools/rdg-agent-lenses/work-decision.json').read_text()))
        lens=app.request(request)['packages'][0]['packageId']
        source=app.snapshot(lens,layouts=False)['graph'];root=source['rootRequirementId']
        refs=[app.model.reference(lens,source,root),app.model.reference(pid,app.snapshot(pid,layouts=False)['graph'],'Q')]
        create=app.schema('plan_action',pid)['request']
        create.update(note='Synthetic read subject task',entity={'kind':'action','title':'Read subjects','description':'Free Markdown','subjectRefs':refs})
        effects=app.request(create)['packages'][0]['receipt']['effects'];aid=effects['actionId']
        msg={'method':'read','packageId':pid,'detail':'focus','nodeId':aid,'include':['entities','subjects','plan','completion','dependencyApplications'],'limit':1}
        first=app.call(msg);token=first['data']['subjects']['page']['nextCursor']
        self.assertEqual(first['snapshot']['sources'][lens]['graphRevision'],source['revision'])
        self.assertTrue(S.read_pages(app,msg,True)['reading']['pagesComplete'])
        self.assertTrue(first['plan']['available'])
        self.assertEqual(first['data']['plan']['items'][0]['id'],effects['placementId'])
        self.assertNotIn('node',first['data']['subjects']['items'][0])
        change=app.schema('paper_edit',lens,node_id=root,command='edit')['request']
        change.update(note='Changed source definition',data={'nodeId':root,'changes':{'description':'New source text'},'cosmetic':False})
        app.request(change)
        with self.assertRaisesRegex(ValueError,'CURSOR_STALE'):
            app.call({**msg,'include':['subjects'],'cursor':token})
        current=S.read_pages(app,msg,True)
        self.assertEqual(self.bodies(current)[aid]['subjectRefs'],refs)
        # Existing path scopes cannot read the lens; a cursor is not an extra grant.
        limited=self.authority.manage('issue',self.admin,{'permissions':['graph.read','plan.read'],
                    'scopes':['package-paths/'+self.namespace+'/working/']})['token']
        hidden=S.read_pages(self.app(limited),msg,True)
        subject=hidden['data']['subjects']['items'][0]
        self.assertEqual(subject['status'],'unavailable')
        self.assertNotIn('target',subject)

    def test_plan_and_registry_changes_invalidate_original_multi_section_snapshot(self):
        pid=self.fixture();app=self.app()
        create=app.schema('plan_action',pid)['request'];create.update(note='A plan item',entity={'kind':'action','title':'Task','description':''})
        effects=app.request(create)['packages'][0]['receipt']['effects'];aid=effects['actionId']
        msg={'method':'read','packageId':pid,'detail':'branch','nodeId':'R1','include':['entities','plan','recommendations','completion','dependencyApplications'],'limit':1}
        first=app.call(msg);token=first['data']['entities']['page']['nextCursor']
        unplace=app.schema('unplace',pid)['request'];unplace.update(note='Concurrent plan edit',stepId=effects['placementId']);app.request(unplace)
        with self.assertRaisesRegex(ValueError,'CURSOR_STALE'):
            app.call({**msg,'include':['entities'],'cursor':token})
        first=app.call(msg);token=first['data']['entities']['page']['nextCursor']
        # The shared recommendation projection's Registry revision is part of the pin.
        original=app.recommendation_projection
        def different(*args,**kwargs):
            value=original(*args,**kwargs);value['registryRevision']=999999;return value
        with patch.object(app,'recommendation_projection',side_effect=different),self.assertRaisesRegex(ValueError,'CURSOR_STALE'):
            app.call({**msg,'include':['entities'],'cursor':token})


    def test_immutable_read_memo_matches_uncached_semantics_and_never_escapes(self):
        pid=self.fixture();app=self.app();row=app.snapshot(pid,layouts=False)
        K=app.kernel.for_graph(row['graph']);before=copy.deepcopy(row['graph'])
        options={'detail':'focus','node_id':'D-SQL','limit':100}
        with patch.object(app,'snapshot',return_value=row),patch.object(app,'boundaries',side_effect=AssertionError('no boundary work required')):
            cached=app.read(pid,**options)
        def plain(graph):
            return {n['id']:n for n in graph['nodes']+graph['objects']+graph.get('externalActions',[])}
        class NoCache:
            def get(self,key):return None
            def put(self,key,value):pass
        with patch.object(app,'snapshot',return_value=row),patch.object(K,'entities',side_effect=plain),patch.object(app,'_scoped_cache',NoCache()):
            uncached=app.read(pid,**options)
        self.assertEqual(cached,uncached)
        self.assertEqual(row['graph'],before)
        self.assertIsNone(K.ANALYSIS.active_read_cache(row['graph']))
        cached['data']['entities']['items'][0]['entity']['title']='Only client copy'
        self.assertEqual(row['graph'],before)
        self.command(pid,'edit',nodeId='D-SQL',changes={'description':'Fresh after read'},cosmetic=False)
        self.assertEqual(self.bodies(self.read_scope(pid,'focus','D-SQL'))['D-SQL']['description'],'Fresh after read')


    def test_pagination_reuses_only_pin_checked_derived_sections(self):
        app=self.app()
        pid=app.request(self.req('create',path='working/cache-pages',role='working',coreModel='rdg-decision-v1',
            title='Page cache',scope='Synthetic',rootReason='Read-only cache acceptance'))['packages'][0]['packageId']
        self.command(pid,'add',entity={'id':'R2','kind':'requirement','title':'Child','description':'','scope':'Synthetic'},
                     initialRelations=[{'id':'E','type':'DERIVES','from':'R1','to':'R2'}])
        K=app.kernel.for_profile('rdg-decision-v1')
        msg={'method':'read','packageId':pid,'detail':'branch','nodeId':'R1','limit':1}
        with patch.object(app,'states',wraps=app.states) as states,patch.object(K.POLICIES,'describe_applications',wraps=K.POLICIES.describe_applications) as applications:
            first=app.call(msg)
            for section in ('completion','dependencyApplications'):
                token=first['data'][section]['page']['nextCursor']
                self.assertIsNotNone(token)
                again=app.call({**msg,'include':[section],'cursor':token})
                self.assertEqual(again['snapshot'],first['snapshot'])
            self.assertEqual(states.call_count,1);self.assertEqual(applications.call_count,1)
        # Cached bytes cannot be changed by a client mutating a returned row.
        first['data']['completion']['items'][0]['state']['truth']='client mutation'
        repeat=app.call(msg)
        self.assertNotEqual(repeat['data']['completion']['items'][0]['state']['truth'],'client mutation')


    def test_snapshot_memo_keeps_the_same_validation_failures(self):
        pid=self.fixture();app=self.app();valid=app.snapshot(pid,layouts=False)
        cases=[]
        duplicate=copy.deepcopy(valid);duplicate['graph']['nodes'].append(copy.deepcopy(duplicate['graph']['nodes'][0]));cases.append(duplicate)
        endpoint=copy.deepcopy(valid);endpoint['graph']['edges'][0]['from']='MISSING';cases.append(endpoint)
        fields=copy.deepcopy(valid);fields['graph']['unexpectedField']=True;cases.append(fields)
        for value in cases:
            errors=[]
            with patch.object(app.store,'read',return_value=value):
                for memo in (False,True):
                    with self.assertRaises(ValueError) as caught:
                        app.snapshot(pid,layouts=False,scoped_read=memo)
                    errors.append(str(caught.exception))
            self.assertEqual(errors[0],errors[1])


    def test_addressed_recommendations_match_full_results_without_unused_completion(self):
        import uuid
        pid=self.fixture();app=self.app();g=copy.deepcopy(app.snapshot(pid,layouts=False)['graph'])
        definition={'id':str(uuid.uuid4()),'revision':1,'key':'read-test','title':'Read advice','supplied':False,
            'rules':[{'id':'r','nodeKinds':['decision'],'scope':'all','state':'any',
                'lensRefs':[{'packageId':str(uuid.uuid4()),'identitySpace':str(uuid.uuid4()),'lensKey':'test'}]}]}
        reg=app.recommendations.empty(self.namespace);reg['packages']=[definition];g['recommendationPackageIds']=[definition['id']]
        with patch.object(app.kernel,'completion_state',side_effect=AssertionError('any does not need completion')):
            full=app.recommendations.matches(reg,g,pid,app.kernel)
            addressed=app.recommendations.matches(reg,g,pid,app.kernel,node_ids={'D-SQL'})
        self.assertEqual(addressed['matches'],[r for r in full['matches'] if r['nodeId']=='D-SQL'])
        definition['rules'][0]['state']='completed'
        with patch.object(app.kernel,'completion_state',wraps=app.kernel.completion_state) as states:
            app.recommendations.matches(reg,g,pid,app.kernel,node_ids={'D-SQL','D-FILE'})
            self.assertEqual(states.call_count,1)


    def test_membership_only_branch_preserves_finding_scope_and_brief_parent(self):
        app=self.app();pid=app.request(self.req('create',path='working/group-only',role='working',coreModel='rdg-decision-v1',
            title='Group-only',scope='Synthetic',rootReason='Canonical membership acceptance'))['packages'][0]['packageId']
        self.command(pid,'add',entity={'id':'D','kind':'decision','title':'Decision','description':''},
                     initialRelations=[{'id':'E','type':'DRIVES','from':'R1','to':'D'}])
        self.command(pid,'decision_group',group={'id':'G','parentId':'R1','title':'Alternatives','selectionRequired':False,
                     'mutuallyExclusive':False,'members':[{'id':'M','decisionId':'D'}]})
        self.assertNotIn('E',{e['id'] for e in app.snapshot(pid,layouts=False)['graph']['edges']})
        self.command(pid,'add',entity={'id':'F','kind':'finding','title':'Issue','description':'','subjectId':'D',
                     'findingType':'problem','rationale':'A real group subject','evidenceIds':[]})
        branch=self.read_scope(pid,'branch','R1')
        self.assertEqual({r['nodeId'] for r in branch['data']['outline']['items']},{'R1','D'})
        self.assertEqual(branch['data']['findings']['items'][0]['relativeLevel'],'CURRENT')
        focus=self.read_scope(pid,'focus','D')
        self.assertEqual(focus['data']['parents']['items'][0]['via']['id'],'M')
        self.assertNotIn('R1',self.bodies(focus))

    def test_agent_and_portable_cli_same_scope_and_defaults(self):
        pid=self.fixture();app=self.app()
        args=SimpleNamespace(command='open',package_id=pid,node='R-STORE',expected_input_binding=None,
            show_excluded_alternatives=False,detail='branch',include=['entities','outline'],limit=1,
            cursor=None,lens=None,all_pages=True)
        with patch.object(T.A,'portable_application',return_value=app):
            agent=T.A.portable_command(args,{'profile':'portable'})
        self.assertTrue(agent['reading']['pagesComplete'])
        argv=['read','--packages',str(self.root),'--namespace',self.namespace,'--coordination-root',str(self.base),
              '--store',str(self.authority.path),'--package-id',pid,'--node','R-STORE','--detail','branch',
              '--include','entities','--include','outline','--limit','1','--all-pages']
        out=io.StringIO()
        with patch.dict(os.environ,{'RDG_AUTH_TOKEN':self.token}),redirect_stdout(out):T.A.PORTABLE.main(argv)
        self.assertEqual(json.loads(out.getvalue()),agent)
        args.detail=None;args.all_pages=False;args.include=None
        with patch.object(T.A,'portable_application',return_value=app):
            self.assertEqual(T.A.portable_command(args,{'profile':'portable'})['detail'],'item')
        form=app.schema('read',pid)
        self.assertIn('branch',form['read']['detail']);self.assertIn('parents',form['scoped']['include'])


if __name__=='__main__':
    unittest.main()
