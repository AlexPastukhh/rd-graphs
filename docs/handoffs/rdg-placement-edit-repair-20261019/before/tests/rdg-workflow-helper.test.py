#!/usr/bin/env python3
"""Real local session HTTP -> existing writers; isolated synthetic owners only."""
from importlib.machinery import SourceFileLoader
import copy
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
FIX=SourceFileLoader('manual_fixture',str(ROOT/'tests/rdg-workflow.acceptance.test.py')).load_module()
H=SourceFileLoader('manual_helper_test',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()


class Manual(unittest.TestCase):
    def setUp(self):
        self.f=FIX.Workflow('test_whole_future_execution_withdrawal_new_variant_and_history')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.w=self.f.w
        self.editor=H.Editor(self.f.root,self.f.rel,self.w.home/'graphs',self.w.rel,
            self.w.store,self.w.token,tools=self.w.home/'tools')
        self.server=H.make_server(self.editor)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
        self.seq=0
        self.base=self.server.session_url
        self.session=self.base.rstrip('/').split('/')[-1]

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)

    def http(self,path='state',body=None,headers=None,expected=200,url=None):
        base={'X-RDG-Session':self.session}
        if body is not None:base.update({'Content-Type':'application/json','Origin':self.server.origin})
        base.update(headers or {})
        req=Request(url or self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=base)
        try:
            with urlopen(req,timeout=30) as r:status=r.status;data=r.read();hdr=r.headers
        except HTTPError as r:status=r.code;data=r.read();hdr=r.headers
        self.assertEqual(status,expected,data[:500])
        return json.loads(data) if hdr.get_content_type()=='application/json' else data.decode()

    def command(self,action,node='R0',**extra):
        self.seq+=1;view=self.editor.snapshot()
        return {'action':action,'nodeId':node,'transactionId':'manual-'+str(self.seq),'note':'Synthetic manual note',
            'expectedGraphRevision':view['sources']['graphs'][self.w.rel]['revision'],
            'expectedPlanRevision':view['sources']['plan']['revision'],**extra}

    def apply(self,action,node='R0',**extra):
        return self.http('command',self.command(action,node,**extra))

    def add(self,title='Action'):
        r=self.apply('add_action',title=title,recommended='Suitable synthetic case',actionType='general')
        return next(n['id'] for n in r['view']['sources']['graphs'][self.w.rel]['nodes'] if n['title']==title)

    def test_gui_controller_whole_path_through_http_and_real_writers(self):
        run=subprocess.run(['node','--test','tests/rdg-workflow-ui.test.cjs'],cwd=ROOT,
            text=True,capture_output=True,timeout=90,
            env={**os.environ,'RDG_WORKFLOW_TEST_URL':self.base})
        self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
        out=ROOT/'docs/handoffs/rdg-manual-workflow-20261019/gui-controller.log'
        out.write_text(run.stdout+run.stderr)
        events=self.w.read()['events']
        actions=[e for e in events if e['type'] in ('action_executed','action_withdrawn')]
        self.assertEqual([e['type'] for e in actions],['action_executed','action_withdrawn','action_executed'])
        self.assertTrue(all(e['by']=='user' and e['authorityPrincipal'].startswith('bearer:') for e in actions))
        self.assertTrue(all(e['verifiedTrustReceipt']['mode']=='local-manual-session' for e in actions))

    def test_gui_controller_whole_path_through_files_without_network_transport(self):
        session=H.FileSession(self.editor,self.w.home/'manual-session')
        stop=threading.Event()
        def poll():
            while not stop.wait(0.01):session.process_once()
        worker=threading.Thread(target=poll,daemon=True);worker.start()
        try:
            env={**os.environ,'RDG_WORKFLOW_TEST_DIR':str(session.directory)}
            env.pop('RDG_WORKFLOW_TEST_URL',None)
            run=subprocess.run(['node','--test','tests/rdg-workflow-ui.test.cjs'],cwd=ROOT,
                text=True,capture_output=True,timeout=90,env=env)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            (ROOT/'docs/handoffs/rdg-manual-workflow-20261019/gui-file-controller.log').write_text(run.stdout+run.stderr)
            before=self.w.sources()
            session.process_once();self.assertEqual(before,self.w.sources())
        finally:
            stop.set();worker.join(2);session.close()

    def test_file_session_rejects_wrong_capability_symlinks_and_reused_directory(self):
        session=H.FileSession(self.editor,self.w.home/'manual-session')
        before=self.w.sources(),self.f.plan_sources()
        q=session.directory/'request-bad.json'
        q.write_text(json.dumps({'session':'wrong','kind':'command','body':self.command('edit_title',title='Denied')}))
        (session.directory/'request-bad.ready').write_text('1')
        session.process_once();r=json.loads((session.directory/'response-bad.json').read_text())
        self.assertFalse(r['ok']);self.assertIn('SESSION_DENIED',r['error'])
        (session.directory/'request-link.json').symlink_to(self.w.store)
        (session.directory/'request-link.ready').write_text('1')
        session.process_once();self.assertFalse(json.loads((session.directory/'response-link.json').read_text())['ok'])
        self.assertEqual(before,(self.w.sources(),self.f.plan_sources()))
        with self.assertRaisesRegex(ValueError,'CHOOSE_NEW'):H.FileSession(self.editor,session.directory)
        session.close();self.assertFalse(json.loads((session.directory/'session.json').read_text())['active'])

    def test_read_only_snapshot_static_assets_and_no_bearer_exposure(self):
        before=self.w.sources(),self.f.plan_sources()
        state=self.http();html=self.http('')
        for path in ['viewer.js','ui.js']:
            text=self.http(path);self.assertGreater(len(text),100)
        self.assertNotIn(self.w.token,json.dumps(state)+html)
        self.assertNotIn(self.editor.key,json.dumps(state)+html)
        self.assertIn('sources',state)
        self.assertEqual(before,(self.w.sources(),self.f.plan_sources()))

    def test_session_origin_host_content_and_request_guards(self):
        original=self.w.sources(),self.f.plan_sources()
        req=self.command('add_action',title='Denied',recommended='Case')
        self.http('command',req,{'Origin':'https://example.invalid'},400)
        self.http('command',req,{'Host':'attacker.invalid'},400)
        self.http('command',req,{'X-RDG-Session':'bad'},400)
        self.http('command',req,{'Content-Type':'text/plain'},400)
        self.http(headers={'X-RDG-Session':'bad'},expected=403)
        self.http(url=self.server.origin+'/state',expected=403)
        self.http('command',{**req,'package':{}},expected=400)
        self.assertEqual(original,(self.w.sources(),self.f.plan_sources()))

    def test_exact_retry_after_lost_response_and_later_mutation(self):
        aid=self.add()
        req=self.command('select',aid)
        first=self.http('command',req);self.assertTrue(first['saved'])
        sources=self.w.sources()
        again=self.http('command',req);self.assertTrue(again['replayed']);self.assertEqual(sources,self.w.sources())
        self.apply('complete',aid)
        sources=self.w.sources()
        self.assertTrue(self.http('command',req)['replayed']);self.assertEqual(sources,self.w.sources())
        self.http('command',{**req,'note':'different'},expected=400)
        self.assertEqual(len([e for e in self.w.read()['events'] if e['type']=='action_selected']),1)

    def test_stale_view_and_second_execution_are_denied_without_writes(self):
        aid=self.add()
        stale=self.command('edit_title',aid,title='Stale')
        self.apply('select',aid)
        before=self.w.sources()
        self.assertIn('CAS',self.http('command',stale,expected=400)['error']);self.assertEqual(before,self.w.sources())
        self.apply('complete',aid)
        self.apply('edit_title',aid,title='Edited executed instance')
        before=self.w.sources()
        self.assertIn('already executed',self.http('command',self.command('complete',aid),expected=400)['error'])
        self.assertEqual(before,self.w.sources());self.assertEqual(self.http()['future'],[])

    def test_deep_candidate_canon_qrpe_requirement_placement_and_unplace(self):
        aid=self.add()
        self.apply('edit_canon',aid,recommended='Updated case',contraindicated='Contraindication')
        self.apply('add_qrpe',aid,title='Check the mechanism')
        r=self.apply('prepare_requirement',aid,title='Potential child',childRole='method_correctness')
        child=next(n for n in r['view']['sources']['graphs'][self.w.rel]['nodes'] if n['title']=='Potential child')
        self.assertEqual(child['status'],'potential')
        self.apply('place',aid,at='2026-10-21')
        first=self.http()['sources']['plan']['steps'][0]['id']
        self.apply('place',child['id'],afterStepId=first)
        view=self.http();self.assertEqual(len(view['future']),2)
        self.assertTrue(all(n['status']=='candidate' for n in self.w.read()['nodes'] if n['kind']=='action'))
        sid=next(s['id'] for s in view['sources']['plan']['steps'] if s['kind']=='requirement')
        before=self.w.sources()
        self.apply('unplace',child['id'],stepId=sid)
        self.assertEqual(before,self.w.sources())
        self.assertEqual(len(self.http()['future']),1)

    def test_unscheduled_execution_and_protected_graph_denial(self):
        aid=self.add();self.apply('select',aid);self.apply('complete',aid)
        state=self.http();self.assertEqual(state['future'],[]);self.assertEqual(state['sources']['plan']['steps'],[])
        graph=self.w.read();graph['nodes'][0]['reconsiderationPolicy']={'mode':'protected','authorityPrincipal':'owner'}
        # Test fixture only; do not use raw edits as the product mutation path.
        self.w.path.write_text(json.dumps(graph))
        before=self.w.sources()
        self.assertIn('PROTECTED',self.http('command',self.command('edit_title',aid,title='Denied'),expected=400)['error'])
        self.assertEqual(before,self.w.sources())

    def test_api_bearer_keeps_user_and_forged_manual_proof_denial(self):
        aid=self.add()
        op=self.w.choose(aid);op['event']['by']='user'
        before=self.w.sources()
        package=self.w.patch([op],self.w.read()['revision'],'ordinary-user-spoof')
        self.w.assert_denied(self.w.write(package,self.w.token),'BEARER_CANNOT_CLAIM_USER_IDENTITY')
        forged=copy.deepcopy(package);forged['trustedApproval']={'principal':'fake','expiresAt':9999999999,'purpose':'rdg-v6-material-action-v1','signature':'0'*64}
        self.w.assert_denied(self.w.write(forged,self.w.token),'BEARER_CLIENT_MUST_NOT_SUPPLY_HMAC_APPROVAL')
        forged['trustedApproval'].update(expiresAt=int(__import__('time').time())+60)
        forged['trustedApproval']['principal']='bearer:'+H.AUTH.Authority(self.w.store)._actor(H.AUTH.Authority(self.w.store)._read(),self.w.token)[0]
        path=self.w.home/'forged-manual.json';path.write_text(json.dumps(forged))
        result=subprocess.run(['python3','-B',str(self.w.home/'tools/graph-apply.py'),'--package','--patch',str(path)],
            text=True,capture_output=True,env={**self.w.env,'RDG_AUTH_TOKEN':self.w.token,
                'RDG_LOCAL_MANUAL_SESSION':'1','RDG_V6_TRUST_KEY':self.editor.key})
        self.w.assert_denied(result,'TRUST_SIGNATURE_INVALID')
        self.assertEqual(before,self.w.sources())

    def test_write_permissions_and_revocation_apply_to_session_and_cached_retry(self):
        aid=self.add()
        request=self.command('select',aid);self.http('command',request)
        grant_id=H.AUTH.Authority(self.w.store)._actor(H.AUTH.Authority(self.w.store)._read(),self.w.token)[0]
        self.w.admin('amend',{'id':grant_id,'grant':{'permissions':['graph.read','plan.read'],'scopes':['workspaces/','plans/']}},self.w.owner)
        before=self.w.sources(),self.f.plan_sources()
        self.assertIn('MISSING_PERMISSION',self.http('command',request,expected=400)['error'])
        self.assertIn('MISSING_PERMISSION',self.http('command',self.command('place',aid,at='2026-10-21'),expected=400)['error'])
        self.w.admin('revoke',{'id':grant_id},self.w.owner)
        self.assertIn('TOKEN_REVOKED',self.http(expected=403)['error'])
        self.assertEqual(before,(self.w.sources(),self.f.plan_sources()))

    def test_plan_error_after_durable_prepare_retains_uncertain_outcome_until_recovery(self):
        aid=self.add();req=self.command('place',aid,at='2026-10-21')
        original=H.WF.OWNER.replay
        def fault(root,journal):
            first=journal['writes'][0]
            H.WF.OWNER.atomic(H.WF.OWNER.safe(root,first['path']),first['after'])
            raise OSError('Synthetic interruption after first accepted Plan write')
        H.WF.OWNER.replay=fault
        try:
            response=self.http('command',req,expected=400)
            self.assertFalse(response['definite']);self.assertIn('OUTCOME_UNCONFIRMED',response['error'])
            self.assertTrue((self.f.root/H.WF.OWNER.JOURNAL).exists())
            self.assertIn('RECOVERY_REQUIRED',self.http(expected=403)['error'])
        finally:H.WF.OWNER.replay=original
        H.WF.OWNER.recover(self.f.root)
        result=self.http('command',req);self.assertTrue(result['saved'])
        self.assertEqual(result['view']['sources']['plan']['revision'],2)
        sources=self.f.plan_sources();self.http('command',req);self.assertEqual(sources,self.f.plan_sources())

    def test_pending_graph_journal_blocks_gui_until_existing_recovery(self):
        aid=self.add()
        op=self.w.choose(aid);package=self.w.patch([op],self.w.read()['revision'],'pending')
        # Produce an actual prepared journal using the existing fixture failpoint hook.
        script=self.w.home/'prepare-pending.py'
        script.write_text("""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import json,os
m=SourceFileLoader('pending_package',str(Path(__file__).parent/'tools/graph-package.py')).load_module()
real=m.finish
def crash(path,journal):os._exit(77)
m.finish=crash
m.execute(json.loads((Path(__file__).parent/'pending-package.json').read_text()))
""")
        (self.w.home/'pending-package.json').write_text(json.dumps(package))
        r=subprocess.run(['python3','-B',str(script)],env={**self.w.env,'RDG_AUTH_TOKEN':self.w.token},capture_output=True)
        self.assertEqual(r.returncode,77)
        before=self.w.sources()
        self.assertIn('RECOVERY_REQUIRED',self.http(expected=403)['error']);self.assertEqual(before,self.w.sources())
        self.w.assert_ok(self.w.write(package,self.w.token))
        self.assertEqual(self.http()['sources']['graphs'][self.w.rel]['revision'],self.w.read()['revision'])


if __name__=='__main__':unittest.main()
