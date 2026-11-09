from pathlib import Path
from importlib.machinery import SourceFileLoader
import copy,hashlib,hmac,json,os,secrets,shutil,subprocess,time
root=Path('/workspace/repos/rd-graphs');out=root/'docs/handoffs/rdg-plan-completion-review-20261019'
M=SourceFileLoader('pc_recheck_fixture',str(root/'tests/rdg-deep-action.acceptance.test.py')).load_module()
observations=[]
def probe(name,fun):
 w=M.DeepAction('test_leaf_no_extra_result_goal_and_later_definition_edit_preserves_history');w.setUp()
 try:observations.append({'name':name,**fun(w)})
 finally:w.tearDown()
def typed_r(w):
 w.apply([w.add('A'),w.prepare('A','R1','method_correctness'),w.choose('A')])
 w.apply([w.edit('edit_node',nodeId='R1',changes={'actionType':'decomposition'})])
 before=w.states()['R1']['reason'];w.apply([w.result('R1')])
 return {'reasonBefore':before,'completeAfter':{key:w.states()[key]['complete'] for key in ['R1','A','R0']}}
def signed(w):
 trust=SourceFileLoader('pc_trust',str(root/'tools/rdg-v6-action-trust.py')).load_module()
 ops=[w.add('A'),w.prepare('A','RC','method_correctness'),w.choose('A'),w.result('RC')]
 for op in ops:
  if op['op'] in trust.MATERIAL_OPS:op['event']['authorityPrincipal']='synthetic-issuer'
 pkg=w.patch(ops,w.read()['revision'],'signed-completion')
 pkg['trustedApproval']={'principal':'synthetic-issuer','expiresAt':int(time.time())+500,'purpose':'rdg-v6-material-action-v1'}
 key=secrets.token_hex(32)
 pkg['trustedApproval']['signature']=hmac.new(key.encode(),trust.canonical(trust.proof_payload(pkg)),hashlib.sha256).hexdigest()
 path=w.home/'signed-request.json';path.write_text(json.dumps(pkg))
 env={k:v for k,v in w.env.items() if k not in ['RDG_AUTH_STORE','RDG_AUTH_TOKEN']};env['RDG_V6_TRUST_KEY']=key
 r=subprocess.run(['python3','-B',str(w.home/'tools/graph-apply.py'),'--package','--patch',str(path)],env=env,text=True,capture_output=True)
 assert r.returncode==0,r.stderr
 return {'exitCode':r.returncode,'actionComplete':w.states()['A']['complete'],'rootComplete':w.states()['R0']['complete'],'newResultKinds':sorted(e['type'] for e in w.read()['events'] if e['type'] in M.MODEL.COMPLETION_EVENTS)}
probe('requirement-with-action-type-after-fix',typed_r)
probe('signed-package-result-and-final-derivation',signed)
assert observations[0]['completeAfter']=={'R1':True,'A':True,'R0':True}
assert observations[1]['actionComplete'] and observations[1]['rootComplete']
(out/'independent-observations-after.json').write_text(json.dumps(observations,indent=2)+'\n')
print(json.dumps(observations,indent=2))
