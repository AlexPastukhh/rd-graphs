#!/usr/bin/env python3
"""Two local full graph roots -> two Plan owners through one real Helper FileSession."""
from importlib.machinery import SourceFileLoader
import copy,json,os
from pathlib import Path
import subprocess,threading,unittest

ROOT=Path(__file__).resolve().parents[1]
FIX=SourceFileLoader('workspace_test_fixture',str(ROOT/'tests/rdg-workflow.acceptance.test.py')).load_module()
H=SourceFileLoader('workspace_test_helper',str(ROOT/'tools/rdg-workflow-helper.py')).load_module()

class WorkspaceSwitch(unittest.TestCase):
 def setUp(self):
  self.f=FIX.Workflow('test_whole_future_execution_withdrawal_new_variant_and_history')
  self.f.setUp();self.addCleanup(self.f.doCleanups)
  w=self.f.w
  g=copy.deepcopy(w.graph)
  g.update(id='beta',title='Root B',identitySpace='beta',rootRequirementId='RB')
  g['nodes'][0].update(id='RB',title='Root B')
  self.beta_graph='workspaces/beta/graph.json'
  self.beta_plan='plans/beta/plan.json'
  package={'schemaVersion':1,'transactionId':'create-beta-graph',
   'changes':[{'file':self.beta_graph,'create':g}]}
  w.assert_ok(w.write(package,w.token))
  plan={'schemaVersion':1,'kind':'temporalPlan','id':'beta','title':'Plan B',
   'identitySpace':'beta','revision':1,'status':'candidate',
   'steps':[],'sequence':[],'branches':[],'timeConstraints':[]}
  self.f.owner({'transactionId':'create-beta-plan','op':'create',
   'file':self.beta_plan,'expectedRevision':0,'plan':plan})
  self.config={'schemaVersion':1,'contexts':[
   {'rootSlug':'demo','graphFile':w.rel,'planFile':self.f.rel,'identitySpace':'demo','rootRequirementId':'R0'},
   {'rootSlug':'beta','graphFile':self.beta_graph,'planFile':self.beta_plan,
    'identitySpace':'beta','rootRequirementId':'RB'}]}
  self.contexts=H.WorkspaceEditors(self.config,self.f.root,w.home/'graphs',w.store,w.token,tools=w.home/'tools')

 def test_file_transport_two_full_graphs_and_no_cross_write(self):
  w=self.f.w
  s=H.FileSession(self.contexts,w.home/'workspaces-session')
  stop=threading.Event()
  def poll():
   while not stop.wait(.01):s.process_once()
  worker=threading.Thread(target=poll,daemon=True);worker.start()
  try:
   env={**os.environ,'RDG_WORKSPACE_TEST_DIR':str(s.directory)}
   r=subprocess.run(['node','--test','tests/rdg-workspace-switch.test.cjs'],cwd=ROOT,
    text=True,capture_output=True,timeout=85,env=env)
   self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr)
   self.assertEqual([n['title'] for n in w.read()['nodes'] if n['kind']=='action'],['Action only in A'])
   gb=json.loads((w.home/'graphs'/self.beta_graph).read_text())
   self.assertEqual([n['title'] for n in gb['nodes'] if n['kind']=='action'],['Action only in B'])
   self.assertEqual(H.WF.OWNER.read_snapshot(self.f.root,self.f.rel)['plan']['id'],'demo')
   self.assertEqual(len(H.WF.OWNER.read_snapshot(self.f.root,self.f.rel)['plan']['steps']),1)
   self.assertEqual(len(H.WF.OWNER.read_snapshot(self.f.root,self.beta_plan)['plan']['steps']),1)
   self.assertEqual(H.WF.OWNER.read_snapshot(self.f.root,self.beta_plan)['plan']['id'],'beta')
  finally:stop.set();worker.join(3);s.close()

 def test_new_child_owner_same_identity_is_read_and_requires_scope(self):
  w=self.f.w
  child=copy.deepcopy(w.graph)
  child.update(id='alpha-child',title='Synthetic child',identitySpace='demo',
               rootRequirementId='RC',events=[],edges=[])
  child['nodes']=[{'id':'RC','kind':'requirement','title':'Child','status':'candidate'}]
  file='workspaces/alpha-child/graph.json'
  package={'schemaVersion':1,'transactionId':'create-alpha-child',
           'changes':[{'file':file,'create':child}]}
  w.assert_ok(w.write(package,w.token))
  # An already-created context must refresh the owner set when the index changes.
  self.assertIn(file,self.contexts.snapshot('demo')['sources']['graphs'])
  limited=w.grant(['graph.read','plan.read'],[w.rel,self.f.rel])['token']
  pool=H.WorkspaceEditors(self.config,self.f.root,w.home/'graphs',w.store,limited,tools=w.home/'tools')
  with self.assertRaisesRegex(ValueError,'AUTH_|TOKEN_|SCOPE_'):
   pool.snapshot('demo')

 def test_legacy_working_graph_gets_real_empty_plan_at_session_start(self):
  w=self.f.w
  graph=copy.deepcopy(json.loads((ROOT/'graphs/workspaces/try-it/graph.json').read_text()))
  graph['id']='legacy-synthetic';graph['title']='Legacy Working';graph['revision']=1
  graph['presentation']={'usage':'working'}
  file='workspaces/legacy-synthetic/graph.json';plan='plans/legacy-synthetic/plan.json'
  # Legacy source was authored before the candidate-v6 writer contract.
  # Publish a *synthetic fixture* in its isolated temp catalog; do not forge
  # an unsupported create operation through the modern graph writer.
  path=w.home/'graphs'/file
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps(graph),encoding='utf8')
  index=w.home/'graphs/index.json';manifest=json.loads(index.read_text())
  manifest['graphs'].append({'slug':'legacy-synthetic','title':graph['title'],
    'file':file,'group':'workspaces','folder':'workspaces','kind':'graph',
    'presentation':{'usage':'working'},'catalogLegacy':False,
    'catalogHidden':False,'planningScale':'module'})
  index.write_text(json.dumps(manifest),encoding='utf8')
  entries=H.automatic_working_contexts(w.home/'graphs')['contexts']
  row=next((r for r in entries if r['graphFile']==file),None)
  self.assertIsNotNone(row,'catalog must discover legacy published working graph')
  self.assertEqual(row['identitySpace'],'legacy-legacy-synthetic')
  config={'schemaVersion':1,'contexts':[row]}
  target=self.f.root/plan
  self.assertFalse(target.exists())
  denied_token=w.grant(['graph.read','plan.read'],[file,plan])['token']
  denied=H.WorkspaceEditors(config,self.f.root,w.home/'graphs',w.store,denied_token,tools=w.home/'tools')
  with self.assertRaisesRegex(ValueError,'AUTH_|TOKEN_|SCOPE_'):
   H.FileSession(denied,w.home/'denied-legacy-session')
  self.assertFalse(target.exists())
  pool=H.WorkspaceEditors(config,self.f.root,w.home/'graphs',w.store,w.token,tools=w.home/'tools')
  session=H.FileSession(pool,w.home/'allowed-legacy-session')
  try:
   self.assertTrue(target.is_file(),'Plan owner must be created before any request')
   self.assertEqual(H.WF.OWNER.read_snapshot(self.f.root,plan)['plan']['steps'],[])
   self.assertEqual(H.WF.OWNER.read_snapshot(self.f.root,plan)['plan']['id'],'legacy-synthetic')
   view=pool.snapshot('legacy-synthetic')
   self.assertEqual(view['planFile'],plan)
   self.assertEqual(view['future'],[])
   self.assertTrue(view['legacyGraphReadOnly'])
   with self.assertRaisesRegex(ValueError,'LEGACY_GRAPH_REQUIRES_EXPLICIT_MIGRATION'):
    pool.dispatch({'contextId':'legacy-synthetic','action':'place'})
   before=target.read_bytes()
   pool.initialize_missing_plans()
   self.assertEqual(before,target.read_bytes(),'Plan owner cannot be recreated on repeated init')
  finally:session.close()

 def test_catalog_auto_discovery_matches_only_real_writable_roots(self):
  w=self.f.w
  mappings=H.automatic_working_contexts(w.home/'graphs')
  by={row['rootSlug']:row for row in mappings['contexts']}
  self.assertEqual(set(by),{'demo','beta'})
  self.assertEqual(by['demo']['graphFile'],w.rel)
  self.assertEqual(by['beta']['planFile'],'plans/beta/plan.json')
  # Auto discovery reads the existing catalog; it may not create a Plan.
  self.assertEqual(H.WF.OWNER.read_snapshot(self.f.root,self.beta_plan)['plan']['id'],'beta')

 def test_missing_plan_is_initialized_only_by_authorized_plan_writer(self):
  w=self.f.w
  g=copy.deepcopy(w.graph)
  g.update(id='gamma',title='Third working graph',identitySpace='gamma',rootRequirementId='RG')
  g['nodes'][0].update(id='RG',title='Root G')
  file='workspaces/gamma/graph.json';plan='plans/gamma/plan.json'
  w.assert_ok(w.write({'schemaVersion':1,'transactionId':'create-gamma-graph',
    'changes':[{'file':file,'create':g}]},w.token))
  config={'schemaVersion':1,'contexts':[{'rootSlug':'gamma','graphFile':file,
    'planFile':plan,'identitySpace':'gamma','rootRequirementId':'RG'}]}
  destination=self.f.root/plan
  self.assertFalse(destination.exists())
  restricted=w.grant(['graph.read','plan.read'],[file,plan])['token']
  denied=H.WorkspaceEditors(config,self.f.root,w.home/'graphs',w.store,restricted,tools=w.home/'tools')
  with self.assertRaisesRegex(ValueError,'AUTH_|SCOPE_|TOKEN_'):
   denied.snapshot('gamma')
  self.assertFalse(destination.exists(),'denied create must not materialize Plan')
  creator=H.WorkspaceEditors(config,self.f.root,w.home/'graphs',w.store,w.token,tools=w.home/'tools')
  view=creator.snapshot('gamma')
  self.assertTrue(destination.is_file())
  self.assertEqual(view['sources']['plan']['steps'],[])
  self.assertEqual(view['sources']['plan']['identitySpace'],'gamma')
  self.assertEqual(view['contextId'],'gamma')
  before=destination.read_bytes()
  self.assertEqual(creator.snapshot('gamma')['sources']['plan']['revision'],1)
  self.assertEqual(destination.read_bytes(),before,'second read cannot recreate or reset owner')
  self.assertEqual(H.WF.OWNER.read_snapshot(self.f.root,plan)['plan']['id'],'gamma')

 def test_unregistered_and_inconsistent_mapping_fail_closed(self):
  w=self.f.w
  with self.assertRaisesRegex(ValueError,'WORKSPACE_NOT_REGISTERED'):self.contexts.snapshot('unknown')
  bad=copy.deepcopy(self.config);bad['contexts'][1]['rootRequirementId']='R0'
  pool=H.WorkspaceEditors(bad,self.f.root,w.home/'graphs',w.store,w.token,tools=w.home/'tools')
  with self.assertRaisesRegex(ValueError,'WORKSPACE_(GRAPH_IDENTITY|CATALOG_ROOT)_MISMATCH'):pool.snapshot('beta')
  broken=copy.deepcopy(self.config);broken['contexts'][1]['planFile']=self.f.rel
  with self.assertRaisesRegex(ValueError,'WORKSPACE_OWNER_REUSED'):
   H.WorkspaceEditors(broken,self.f.root,w.home/'graphs',w.store,w.token,tools=w.home/'tools')
  restricted=w.grant(['graph.read','plan.read'],[w.rel,self.f.rel])['token']
  pool=H.WorkspaceEditors(self.config,self.f.root,w.home/'graphs',w.store,restricted,tools=w.home/'tools')
  self.assertEqual(pool.snapshot('demo')['contextId'],'demo')
  with self.assertRaisesRegex(ValueError,'AUTH_|TOKEN_|SCOPE_'):
   pool.snapshot('beta')

if __name__=='__main__':unittest.main()
