#!/usr/bin/env python3
"""Code module integration; temporary owners, real writers/receipts, no live writes."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader

ROOT=Path(__file__).resolve().parents[1]
H=SourceFileLoader('module_test_helper',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()
M=SourceFileLoader('module_test_runtime',str(ROOT/'tools/rdg-modules.py')).load_module()
DEP=SourceFileLoader('module_test_dep',str(ROOT/'tools/rdg-requirement-gendocen.py')).load_module()
NODE=SourceFileLoader('module_test_apply',str(ROOT/'tools/graph-apply.py')).load_module()
REL='workspaces/module-test/graph.json'
PLAN='plans/module-test/plan.json'


class Modules(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rdg-code-module-')
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        shutil.copytree(ROOT/'tools',self.home/'tools',ignore=shutil.ignore_patterns('__pycache__'))
        self.graph_root=self.home/'graphs';self.graph_root.mkdir()
        self.plan_root=self.home/'plan-owner';self.plan_root.mkdir()
        self.store=self.home/'auth.json'
        self.auth=H.AUTH.Authority(self.store)
        self.token=self.auth.init_local(plan_capable=True,graph_read_capable=True)['token']
        self.graph={'schemaVersion':1,'actionModel':'candidate-v6','planningScale':'module',
            'id':'module-test','identitySpace':'rdg-module-test','title':'Isolated module probe',
            'rootRequirementId':'R0','revision':1,
            'nodes':[{'id':'R0','kind':'requirement','title':'Synthetic root','status':'active'}],
            'edges':[],'events':[]}
        package={'schemaVersion':1,'transactionId':'create','changes':[{'file':REL,'create':self.graph}]}
        self.write(package)
        plan={'schemaVersion':1,'kind':'temporalPlan','id':'module-test','identitySpace':'rdg-module-test',
              'title':'Test Plan','revision':1,'status':'candidate','steps':[],'sequence':[],
              'branches':[],'timeConstraints':[]}
        H.WF.OWNER.apply_request(self.plan_root,self.store,self.token,
            {'transactionId':'plan-create','op':'create','file':PLAN,'expectedRevision':0,'plan':plan})
        self.editor=H.Editor(self.plan_root,PLAN,self.graph_root,REL,self.store,self.token,
                             tools=self.home/'tools')
        self.seq=0

    def write(self, package, token=None, error=None):
        request=self.home/'request.json';request.write_text(json.dumps(package))
        env={**os.environ,'RDG_AUTH_STORE':str(self.store),'RDG_AUTH_TOKEN':token or self.token,
             'PYTHONDONTWRITEBYTECODE':'1'}
        env.pop('RDG_V6_TRUST_KEY',None);env.pop('RDG_LOCAL_MANUAL_SESSION',None)
        run=subprocess.run(['python3','-B',str(self.home/'tools/graph-apply.py'),'--package','--patch',str(request)],
                           capture_output=True,text=True,env=env,timeout=30)
        if error:
            self.assertNotEqual(run.returncode,0,run.stdout);self.assertIn(error,run.stderr)
        else:self.assertEqual(run.returncode,0,run.stderr)
        return run

    def snapshot(self):
        return self.editor.snapshot()

    def command(self, action, **fields):
        self.seq+=1;v=self.snapshot()
        return {'action':action,'transactionId':'module-'+str(self.seq),'note':'Synthetic module operation',
                'expectedGraphRevision':v['sources']['graphs'][REL]['revision'],
                'expectedPlanRevision':v['sources']['plan']['revision'],**fields}

    def apply(self, action, **fields):
        return self.editor.dispatch(self.command(action,**fields))

    def enable(self, scope='graph'):
        return self.apply('configure_'+scope+'_modules',modules={'rdg-test':1})

    def marker(self, value='  probe  ', nodeid='TEST1'):
        return {'id':nodeid,'kind':'rdg-test.marker','title':'Synthetic marker',
            'module':{'id':'rdg-test','version':1},
            'data':{'value':value,'inputs':[{'graphFile':REL,'identitySpace':'rdg-module-test','nodeId':'R0'}]}}

    def create_marker(self):
        return self.apply('module_operation',module='rdg-test',version=1,
                          operation='rdg-test.create',node=self.marker())

    def sources(self):
        return {str(p.relative_to(self.home)):p.read_bytes()
                for base in (self.graph_root,self.plan_root)
                for p in base.rglob('*') if p.is_file()}

    def test_base_and_test_module_are_closed_and_code_entry_is_not_data(self):
        v=self.snapshot();self.assertEqual(v['moduleCapabilities']['graph']['enabled'],{})
        for kind in ['rdg-test.marker','anything','decision','option']:
            g=copy.deepcopy(self.graph);g['nodes'].append({'id':'BAD','kind':kind,'title':'Bad'})
            with self.assertRaisesRegex(ValueError,'INVALID_OR_UNAPPROVED_NODE_KIND'):NODE.validate(g)
        before=self.sources()
        for modules in ({'unknown':1},{'rdg-test':2},{'rdg-base':1},{'../../code':1}):
            with self.assertRaises(ValueError):self.apply('configure_graph_modules',modules=modules)
        self.assertEqual(before,self.sources())

    def test_real_graph_writer_runs_module_code_and_history_hook(self):
        self.enable();result=self.create_marker();self.assertTrue(result['saved'])
        g=result['view']['sources']['graphs'][REL];n=g['nodes'][-1]
        self.assertEqual(n['data']['value'],'PROBE','module Python logic must execute')
        event=g['events'][-1]
        self.assertEqual(event['verifiedTrustReceipt']['mode'],'local-manual-session')
        self.assertEqual(event['nodeSnapshot'],n)
        row=next(r for r in result['view']['history'] if r['kind']=='module_event')
        self.assertIn('PROBE',row['summary']);self.assertEqual(row['snapshotProvenance'],'module-event-snapshot')
        self.assertFalse(any(e['type'] in ('action_executed','requirement_achieved') for e in g['events']))
        changed=self.marker('updated')
        next_view=self.apply('module_operation',module='rdg-test',version=1,
            operation='rdg-test.update',node=changed)['view']
        rows=[r for r in next_view['history'] if r['kind']=='module_event']
        self.assertEqual(rows[0]['nodeSnapshot']['data']['value'],'PROBE')
        self.assertEqual(rows[-1]['nodeSnapshot']['data']['value'],'UPDATED')

    def test_module_off_on_preserves_data_and_blocks_operations(self):
        self.enable();self.create_marker()
        off=self.apply('configure_graph_modules',modules={'rdg-test':1},disabledModules=['rdg-test'])
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'NOT_ENABLED'):self.create_marker()
        self.assertEqual(before,self.sources())
        self.assertTrue(any(n['id']=='TEST1' for n in off['view']['sources']['graphs'][REL]['nodes']))
        self.assertTrue(any(r['kind']=='module_event' for r in off['view']['history']))
        self.enable()
        self.apply('module_operation',module='rdg-test',version=1,
                   operation='rdg-test.update',node=self.marker('resumed'))
        with self.assertRaisesRegex(ValueError,'DISABLE_HAS_DEPENDENT_DATA_OR_HISTORY'):
            self.apply('configure_graph_modules',modules={})

    def test_connect_disconnect_before_use_and_wrong_owner(self):
        self.enable()
        self.apply('configure_graph_modules',modules={})
        self.assertEqual(self.snapshot()['sources']['graphs'][REL]['modules'],{})
        g={**self.graph,'modules':{'rdg-test':1},'identitySpace':'some-other-space'}
        with self.assertRaisesRegex(ValueError,'OWNER_NOT_GRANTED'):NODE.validate(g)
        g={**self.graph,'modules':{'rdg-test':1},'disabledModules':['unknown']}
        with self.assertRaisesRegex(ValueError,'DISABLED_PINS_INVALID'):NODE.validate(g)

    def test_unknown_operations_fields_versions_and_validation_code_rejected_atomically(self):
        self.enable();before=self.sources()
        cases=[{'operation':'rdg-test.invented'}, {'version':9},
               {'node':{**self.marker(),'kind':'requirement'}},
               {'node':{**self.marker(),'data':{'value':'x'*33,'inputs':[]}}},
               {'node':{**self.marker(),'status':'selected'}},
               {'node':{**self.marker(),'data':{'value':'x','inputs':[],'arbitrary':1}}}]
        for change in cases:
            fields={'module':'rdg-test','version':1,'operation':'rdg-test.create','node':self.marker(),**change}
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.apply('module_operation',**fields)
            self.assertEqual(before,self.sources())

    def test_real_plan_owner_code_data_and_history_are_independent_of_graph(self):
        graph_before=(self.graph_root/REL).read_bytes()
        self.enable('plan')
        result=self.apply('set_module_data',module='rdg-test',version=1,
                          data={'annotation':'  one two  ','score':999})
        plan=result['view']['sources']['plan']
        self.assertEqual(plan['moduleData']['rdg-test'],{'annotation':'one two','score':2})
        self.assertEqual(plan['steps'],[])
        self.assertEqual((self.graph_root/REL).read_bytes(),graph_before)
        row=next(r for r in result['view']['history'] if r['kind']=='module_plan_changed')
        self.assertEqual(row['newModuleData']['score'],2)
        self.assertIn('one two',row['summary']);self.assertTrue(row['receiptDigest'])
        self.apply('configure_plan_modules',modules={'rdg-test':1},disabledModules=['rdg-test'])
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'NOT_ENABLED'):
            self.apply('set_module_data',module='rdg-test',version=1,data={'annotation':'three','score':1})
        self.assertEqual(before,self.sources())
        self.enable('plan')
        self.apply('set_module_data',module='rdg-test',version=1,data={'annotation':'three','score':99})
        rows=[r for r in self.snapshot()['history'] if r['kind']=='module_plan_changed']
        self.assertEqual([r['newModuleData']['score'] for r in rows],[2,1])

    def test_plan_full_snapshot_cannot_bypass_disabled_module_or_base_rules(self):
        self.enable('plan')
        self.apply('set_module_data',module='rdg-test',version=1,data={'annotation':'probe','score':1})
        self.apply('configure_plan_modules',modules={'rdg-test':1},disabledModules=['rdg-test'])
        p=copy.deepcopy(self.snapshot()['sources']['plan']);oldrev=p['revision'];p['revision']+=1
        p['moduleData']['rdg-test']={'annotation':'bypass','score':1}
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'DISABLED_DATA_IMMUTABLE'):
            H.WF.OWNER.apply_request(self.plan_root,self.store,self.token,
                {'transactionId':'raw-bypass','op':'edit','file':PLAN,'expectedRevision':oldrev,'plan':p})
        self.assertEqual(before,self.sources())
        p['steps']=[{'id':'S1','kind':'invented','title':'Bad','state':'planned'}]
        with self.assertRaisesRegex(ValueError,'INVALID_STEP'):H.WF.OWNER.PLAN.validate(p)

    def test_dependency_discovery_uses_only_declared_typed_module_fields(self):
        self.enable();self.create_marker()
        g=self.snapshot()['sources']['graphs'][REL]
        nodes,deps=DEP.inventory({REL:g})
        self.assertEqual(set(deps[REL,'TEST1']),{(REL,'R0')})
        g['nodes'][-1]['data']['inputs']=[]
        self.assertNotIn((REL,'TEST1'),DEP.inventory({REL:g})[1])

    def test_permissions_cas_and_exact_replay_use_existing_writer(self):
        self.enable()
        req=self.command('module_operation',module='rdg-test',version=1,
                         operation='rdg-test.create',node=self.marker())
        result=self.editor.dispatch(req);before=self.sources()
        self.assertTrue(self.editor.dispatch(req)['replayed']);self.assertEqual(before,self.sources())
        stale={**req,'transactionId':'stale'}
        with self.assertRaisesRegex(ValueError,'CAS_MISMATCH'):self.editor.dispatch(stale)
        reader=self.auth.manage('issue',self.token,{'permissions':['graph.read','plan.read'],
                           'scopes':['workspaces/','plans/']})['token']
        self.editor.token=reader
        with self.assertRaisesRegex(ValueError,'MISSING_PERMISSION'):self.enable()
        self.assertEqual(before,self.sources())

    def test_missing_or_incompatible_module_code_fails_closed(self):
        original=M.REGISTRY
        self.addCleanup(setattr,M,'REGISTRY',original)
        M.REGISTRY=self.home/'tools/rdg-module-registry.json'
        code=self.home/'tools/rdg-module-test.py'
        code.unlink()
        with self.assertRaisesRegex(ValueError,'CODE_NOT_INSTALLED'):
            M.resolve({**self.graph,'modules':{'rdg-test':1}},'graph')
        code.write_text('API_VERSION = 999\n')
        with self.assertRaisesRegex(ValueError,'CODE_API_INCOMPATIBLE'):
            M.resolve({**self.graph,'modules':{'rdg-test':1}},'graph')


    def test_browser_connects_real_modules_through_helper_and_preserves_history_when_disabled(self):
        import threading
        server=H.make_server(self.editor)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            run=subprocess.run(['bash','tools/rdg-visual-test.sh','tests/visual/rdg-modules.cjs'],
                cwd=ROOT,capture_output=True,text=True,timeout=80,
                env={**os.environ,'RDG_MODULE_TEST_URL':server.session_url})
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            self.assertIn('MODULE_CODE_CONNECTION_GRAPH_PLAN_HISTORY_BROWSER_PASS',run.stdout)
        finally:
            server.shutdown();server.server_close();thread.join(2)

    def test_module_input_requires_real_owner_and_read_permission_before_commit(self):
        self.enable()
        node=self.marker();node['data']['inputs'][0]['nodeId']='MISSING'
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'REQUIREMENT_OWNER_UNRESOLVED'):
            self.apply('module_operation',module='rdg-test',version=1,operation='rdg-test.create',node=node)
        self.assertEqual(before,self.sources())
        token=self.auth.manage('issue',self.token,{'permissions':['graph.write'],'scopes':['workspaces/']})['token']
        op={'op':'module_operation','module':'rdg-test','version':1,'operation':'rdg-test.create',
            'node':self.marker(),'event':{'id':'DENIED','type':'module_event','by':'assistant','note':'Synthetic read denial'}}
        revision=self.snapshot()['sources']['graphs'][REL]['revision']
        self.write({'schemaVersion':1,'transactionId':'denied-ref-read','changes':[{'file':REL,
            'patch':{'schemaVersion':1,'expectedRevision':revision,'operations':[op]}}]},
            token=token,error='MISSING_PERMISSION: graph.read')
        self.assertEqual(before,self.sources())




    def test_real_engine_reviews_module_target_when_its_requirement_changes(self):
        self.enable();self.create_marker()
        project=self.home/'engine-module-project'
        initial=DEP.refresh(self.graph_root,[REL],project)
        marker=next(r for r in initial['rows'] if r['nodeId']=='TEST1')
        self.assertEqual(marker['status'],'review_required','a new subscription needs explicit review')
        packet=DEP.engine_cli(project,'explain',marker['target'])
        DEP.engine_cli(project,'validate',marker['target'],'--result','still-valid',
            '--reason','Synthetic module baseline review, not real-world completion',
            '--review-context',packet['review_context_id'])
        accepted=DEP.refresh(self.graph_root,[REL],project)
        self.assertEqual(next(r for r in accepted['rows'] if r['nodeId']=='TEST1')['status'],'valid')
        self.apply('edit_title',nodeId='R0',title='Changed synthetic input')
        changed=DEP.refresh(self.graph_root,[REL],project)
        row=next(r for r in changed['rows'] if r['nodeId']=='TEST1')
        self.assertEqual(row['status'],'review_required')
        self.assertEqual(row['kind'],'rdg-test.marker')
        self.assertEqual(row['target'],marker['target'])

    def test_direct_owner_snapshots_cannot_bypass_module_operation_code(self):
        self.enable('plan')
        plan=copy.deepcopy(self.snapshot()['sources']['plan']);revision=plan['revision']
        plan['revision']+=1;plan['moduleData']={'rdg-test':{'annotation':'bypass','score':1}}
        before=self.sources()
        with self.assertRaisesRegex(ValueError,'MODULE_DATA_REQUIRES_OPERATION'):
            H.WF.OWNER.apply_request(self.plan_root,self.store,self.token,
                {'transactionId':'raw-module-data','op':'edit','file':PLAN,
                 'expectedRevision':revision,'plan':plan})
        self.assertEqual(before,self.sources())



if __name__=='__main__':unittest.main()
