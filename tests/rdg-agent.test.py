#!/usr/bin/env python3
"""Operate RDG in fresh CLI processes; actual work artifacts, canonical owners only."""
import copy
from importlib.machinery import SourceFileLoader
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
A=SourceFileLoader('operator_test_agent',str(ROOT/'tools/rdg-agent.py')).load_module()
PLAN='plans/agent-work/plan.json'
GRAPH='workspaces/agent-work/graph.json'


class Operator(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rdg-operator-practice-')
        self.addCleanup(self.tmp.cleanup);self.home=Path(self.tmp.name)
        shutil.copytree(ROOT/'tools',self.home/'tools',ignore=shutil.ignore_patterns('__pycache__'))
        (self.home/'graphs').mkdir();(self.home/'plan-owner').mkdir()
        self.store=self.home/'auth.json';auth=A.AUTH.Authority(self.store)
        self.token=auth.init_local(plan_capable=True,graph_read_capable=True)['token']
        self.env={**os.environ,'RDG_AUTH_STORE':str(self.store),'RDG_AUTH_TOKEN':self.token,
                  'PYTHONDONTWRITEBYTECODE':'1','PYTHONWARNINGS':'ignore::DeprecationWarning'}
        self.env.pop('RDG_V6_TRUST_KEY',None);self.env.pop('RDG_LOCAL_MANUAL_SESSION',None)
        self.context={'graphFile':GRAPH,'planFile':PLAN,'identitySpace':'agent-work-space',
            'planRoot':str(self.home/'plan-owner'),'graphId':'rdg-agent-work'}
        self.context_path=self.home/'agent-context.json';self.context_path.write_text(json.dumps(self.context))
        self.env['RDG_AGENT_CONTEXT']=str(self.context_path)
        create=self.new_workspace()
        self.assertEqual(create.returncode,0,create.stderr)
        plan={'schemaVersion':1,'kind':'temporalPlan','id':'agent-work','identitySpace':'agent-work-space',
              'revision':1,'title':'Plan for actual CSV check','status':'candidate',
              'steps':[],'sequence':[],'branches':[],'timeConstraints':[]}
        A.WF.OWNER.apply_request(self.home/'plan-owner',self.store,self.token,
            {'transactionId':'create-plan','op':'create','file':PLAN,'expectedRevision':0,'plan':plan})

    def new_workspace(self,env=None,extra=()):
        return subprocess.run(['python3','-B',str(self.home/'tools/rdg-new-workspace.py'),
            '--slug','agent-work','--title','CSV summary work','--root-id','R0',
            '--root-title','Create and verify CSV summary','--identity-space','agent-work-space',
            '--transaction-id','create-workspace',*extra],text=True,capture_output=True,
            env=env or self.env,timeout=30)

    def cli(self,command,*args,body=None,env=None,ok=True):
        r=subprocess.run(['python3','-B',str(self.home/'tools/rdg-agent.py'),command,*args],
            input=json.dumps(body) if body is not None else None,text=True,capture_output=True,
            env=env or self.env,timeout=40)
        if ok:self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr)
        else:self.assertNotEqual(r.returncode,0,r.stdout)
        self.assertNotIn(self.token,r.stdout+r.stderr,'credential must not enter output')
        return r

    def packet(self,lens='work',node=None):
        return json.loads(self.cli('open','--lens',lens,*(['--node',node] if node else [])).stdout)

    def do(self,action,tid,node,**fields):
        req=json.loads(self.cli('schema','--action',action,'--node',node).stdout)['request']
        req.update({'transactionId':tid,'note':'Actual isolated work: '+action,**fields})
        out=json.loads(self.cli('command',body=req).stdout)
        self.assertTrue(out['saved'],out)
        return out

    def graph(self):
        return json.loads((self.home/'graphs'/GRAPH).read_text())

    def evidence(self,name='work-output/proof.json'):
        p=self.home/name;p.parent.mkdir(exist_ok=True)
        if not p.exists():p.write_text(json.dumps({'checked':True}))
        return [{'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]

    def state_bytes(self):
        return {str(p.relative_to(self.home)):p.read_bytes()
            for base in [self.home/'graphs',self.home/'plan-owner']
            for p in base.rglob('*') if p.is_file()}

    def test_workspace_uses_current_writer_and_requires_auth(self):
        g=self.graph();self.assertEqual(g['actionModel'],'candidate-v6')
        journal=json.loads((self.home/'graphs/workspaces/.transactions/create-workspace.json').read_text())
        self.assertEqual(journal['state'],'completed')
        self.assertEqual(journal['records'][0]['after'],g)
        before=self.state_bytes()
        env={k:v for k,v in self.env.items() if k not in ('RDG_AUTH_STORE','RDG_AUTH_TOKEN')}
        run=self.new_workspace(env=env)
        self.assertNotEqual(run.returncode,0)
        self.assertEqual(before,self.state_bytes())

    def test_work_review_handoff_are_bound_read_only_ordinary_lenses(self):
        before=self.state_bytes()
        for lens in ('work','review','handoff'):
            p=self.packet(lens);self.assertEqual(p['lens']['rootResult'],'unknown')
            self.assertEqual(p['lens']['graphWrites'],0);self.assertFalse(p['lens']['persisted'])
            self.assertTrue(p['lens']['steps'])
            self.assertTrue(any(e['type']=='INTRODUCES' for e in p['lens']['graph']['edges']))
            self.assertTrue(p['lens']['unassessedOrStaleCanons'])
            self.assertEqual(p['context']['identitySpace'],'agent-work-space')
            self.assertIn('add_action',p['availableCommands'])
        self.assertEqual(before,self.state_bytes())

    def test_paper_graph_can_be_reworked_at_depth_without_choice_plan_or_execution(self):
        plan_before=(self.home/'plan-owner'/PLAN).read_bytes()
        self.do('add_action','paper-way','R0',title='Possible architecture',recommended='Worth comparing',
                actionType='decomposition')
        self.do('prepare_requirement','paper-child','A-paper-way',title='Possible subsystem',childRole='subgoal')
        self.do('add_action','paper-inner','R-paper-child',title='Possible inner method',recommended='If this branch is chosen',
                actionType='decomposition')
        self.do('prepare_requirement','paper-deep','A-paper-inner',title='Possible working state',childRole='subgoal')
        self.do('edit_title','paper-rethink','A-paper-inner',title='Revised possible inner method')
        g=self.graph()
        self.assertTrue(all(n['status']=='candidate' for n in g['nodes'] if n['kind']=='action'))
        self.assertTrue(all(n['status']=='potential' for n in g['nodes'] if n['id']!='R0' and n['kind']=='requirement'))
        self.assertFalse(any(e['type']=='INTRODUCES' for e in g['edges']))
        self.assertFalse(any(e['type'] in ('action_selected','action_executed','requirement_achieved') for e in g['events']))
        self.assertEqual(plan_before,(self.home/'plan-owner'/PLAN).read_bytes())
        packet=self.packet('explore','R-paper-deep')
        self.assertFalse(packet['completion']['R-paper-deep']['complete'])
        self.assertEqual(packet['focus']['status'],'potential')

    def test_user_can_open_several_registered_lenses_without_mutating_owners(self):
        before=self.state_bytes()
        packet=json.loads(self.cli('open','--lens','clarify','--lens','explore','--lens','shape','--lens','preserve').stdout)
        self.assertEqual([x['key'] for x in packet['lenses']],['clarify','explore','shape','preserve'])
        self.assertTrue(all(x['rootResult']=='unknown' and x['planWrites']==0 for x in packet['lenses']))
        shape=packet['lenses'][2];preserve=packet['lenses'][3]
        self.assertFalse(any('Q-THREE-CRITERIA' in q for q in shape['unresolvedQrpe']))
        self.assertFalse(any(n['id']=='R-PRESERVE-C3' for n in preserve['graph']['nodes']))
        self.assertTrue(any(n['id']=='K-PRESERVE' for n in preserve['graph']['objects']))
        self.assertEqual(preserve['graph']['events'],[])
        self.cli('open','--lens','not-registered',ok=False)
        self.cli('open','--lens','clarify','--lens','clarify',ok=False)
        self.assertEqual(before,self.state_bytes())

    def test_actual_work_survives_chat_restart_and_records_assistant_not_user(self):
        out=self.home/'work-output';out.mkdir()
        (out/'input.csv').write_text(chr(10).join(['id,amount','1,10','2,20','3,30','']))
        import csv
        with (out/'input.csv').open() as source:rows=list(csv.DictReader(source))
        self.assertEqual(set(rows[0]),{'id','amount'})
        self.assertTrue(all(r['amount'].isdigit() for r in rows))
        (out/'input-inspection.json').write_text(json.dumps({'columns':list(rows[0]),'integerAmounts':True,'rows':len(rows)}))
        self.do('add_action','decompose','R0',title='Deliver a checked CSV summary',
                recommended='Use one explicit deliverable and verify its result',actionType='decomposition')
        self.do('prepare_requirement','deliverable','A-decompose',
                title='Verified JSON: 3 rows, total 60',childRole='subgoal')
        self.do('select','select-decomposition','A-decompose')
        self.do('add_action','implement','R-deliverable',title='Compute with CSV parser',
                recommended='CSV has id and amount columns and integer amounts',
                contraindicated='Unknown schema requires clarification')
        self.do('add_action','alternative','R-deliverable',title='Alternative manual counting',
                recommended='Only for tiny inputs with an independent count')
        review=self.packet('review','R-deliverable')
        self.assertEqual({n['id'] for n in review['relatedNodes'] if n['kind']=='action'},
                         {'A-implement','A-alternative'})
        self.do('select','select-parser','A-implement',
                note='Inspected input.csv: id/amount columns and integer values; parser canon applies',
                evidenceRefs=self.evidence('work-output/input-inspection.json'))
        self.do('add_qrpe','row-question','A-implement',title='Are all input rows accounted for?')
        self.do('place','place-parser','A-implement',at='2026-10-22')
        # A fresh process acts as the next chat. Placement alone did not execute anything.
        resumed=self.packet('handoff','A-implement')
        self.assertTrue(resumed['openQuestions'])
        self.assertTrue(any(r['nodeId']=='A-implement' for r in resumed['future']))
        self.assertFalse(any(e['type']=='action_executed' for e in self.graph()['events']))
        (out/'summarize.py').write_text(
            "import csv,json,sys\nfrom pathlib import Path\n"
            "with Path(sys.argv[1]).open() as f:\n rows=list(csv.DictReader(f))\n"
            "assert rows and set(rows[0])=={'id','amount'}\n"
            "result={'rows':len(rows),'total':sum(int(r['amount']) for r in rows)}\n"
            "Path(sys.argv[2]).write_text(json.dumps(result))\n")
        run=subprocess.run(['python3',str(out/'summarize.py'),str(out/'input.csv'),str(out/'result.json')],
                           capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads((out/'result.json').read_text());self.assertEqual(result,{'rows':3,'total':60})
        (out/'proof.json').write_text(json.dumps({'exitCode':run.returncode,'actual':result,
                                                 'checks':['3 input rows','sum is 60']},indent=2))
        evidence=self.evidence()
        self.do('resolve_qrpe','resolved-row-question','A-implement',issueId='Q-row-question',
                evidenceRefs=evidence,note='Ran parser and checked all 3 rows and total 60')
        self.do('complete','parser-executed','A-implement',evidenceRefs=evidence,
                note='Executed summarize.py and checked result.json: rows=3, total=60')
        finished=self.packet('handoff','A-implement')
        self.assertFalse(finished['openQuestions'])
        self.assertTrue(finished['completion']['A-implement']['complete'])
        self.assertFalse(any(r['nodeId']=='A-implement' for r in finished['future']))
        event=next(e for e in self.graph()['events'] if e['id']=='EV-parser-executed')
        self.assertEqual(event['by'],'assistant');self.assertEqual(event['verifiedTrustReceipt']['mode'],'bearer')
        self.assertEqual(event['evidenceRefs'],evidence)
        self.assertEqual(next(n for n in self.graph()['nodes'] if n['id']=='A-alternative')['status'],'candidate')
        if not finished['completion']['R-deliverable']['complete']:
            self.do('complete','deliverable-achieved','R-deliverable',evidenceRefs=evidence,
                    note='Verified the Requirement criteria independently: JSON rows=3 and total=60')
        self.assertTrue(self.packet('handoff','R-deliverable')['completion']['R-deliverable']['complete'])
        # Continue with a new command, then inspect an older receipt without replaying the old write.
        self.do('add_action','later-candidate','R-deliverable',title='Candidate after handoff',
                recommended='Only if another implementation is needed')
        receipt=json.loads(self.cli('receipt','--transaction-id','parser-executed').stdout)
        self.assertTrue(receipt['found']);self.assertEqual(receipt['state'],'completed')
        self.assertGreater(receipt['currentGraphRevision'],receipt['acceptedGraphRevision'])

    def test_evidence_and_scoped_authority_block_false_completion(self):
        self.do('add_action','candidate','R0',title='Candidate work',recommended='Known input')
        self.do('select','select','A-candidate')
        request=json.loads(self.cli('schema','--action','complete','--node','A-candidate').stdout)['request']
        request.update(note='Actual result claimed',evidenceRefs=[{'path':'missing.json','sha256':'0'*64}])
        before=self.state_bytes()
        self.cli('command',body=request,ok=False)
        self.assertEqual(before,self.state_bytes())
        request['evidenceRefs']=self.evidence()
        request['evidenceRefs'][0]['sha256']='0'*64
        self.cli('command',body=request,ok=False)
        self.assertEqual(before,self.state_bytes())
        auth=A.AUTH.Authority(self.store)
        readonly=auth.manage('issue',self.token,{'permissions':['graph.read','plan.read'],
                                               'scopes':['workspaces/','plans/']})['token']
        request['evidenceRefs']=self.evidence()
        out=json.loads(self.cli('command',body=request,env={**self.env,'RDG_AUTH_TOKEN':readonly},ok=False).stdout)
        self.assertFalse(out['saved']);self.assertEqual(before,self.state_bytes())

    def test_stale_revision_wrong_owner_and_modules_are_rejected(self):
        self.do('add_action','candidate','R0',title='Candidate work',recommended='Known input')
        req=json.loads(self.cli('schema','--action','select','--node','A-candidate').stdout)['request']
        req.update(note='A selection',expectedGraphRevision=1)
        before=self.state_bytes()
        out=json.loads(self.cli('command',body=req,ok=False).stdout);self.assertFalse(out['saved'])
        bad={**self.context,'identitySpace':'wrong'};self.context_path.write_text(json.dumps(bad))
        self.cli('open',ok=False);self.cli('receipt','--transaction-id','candidate',ok=False);self.context_path.write_text(json.dumps(self.context))
        req.update(action='configure_graph_modules',modules={'rdg-test':1})
        self.cli('command',body=req,ok=False)
        self.assertEqual(before,self.state_bytes())

    def test_duplicate_transaction_requires_receipt_not_a_second_operation(self):
        req=json.loads(self.cli('schema','--action','add_action','--node','R0').stdout)['request']
        req.update(transactionId='stable-request',note='Declare candidate',title='Work',recommended='Known input')
        self.assertTrue(json.loads(self.cli('command',body=req).stdout)['saved'])
        before=self.state_bytes()
        retry=json.loads(self.cli('command',body=req,ok=False).stdout)
        self.assertIsNone(retry['saved']);self.assertTrue(retry['transactionExists'])
        self.assertTrue(retry['requestNotReplayed']);self.assertEqual(before,self.state_bytes())

    def test_unavailable_dependencies_are_not_a_successful_empty_report(self):
        data=json.loads(self.cli('dependencies').stdout)
        self.assertFalse(data['available']);self.assertNotIn('report',data)

    def test_doctor_reports_setup_and_no_token_values(self):
        data=json.loads(self.cli('doctor').stdout);self.assertTrue(data['ready'])
        env={k:v for k,v in self.env.items() if k not in ('RDG_AUTH_STORE','RDG_AUTH_TOKEN')}
        data=json.loads(self.cli('doctor',env=env).stdout);self.assertFalse(data['ready'])
        self.assertFalse(data['checks']['authTokenConfigured'])



    def test_private_context_file_routes_auth_without_tokens_in_arguments(self):
        token_file=self.home/'private-token';token_file.write_text(self.token);token_file.chmod(0o600)
        c={**self.context,'authStore':str(self.store),'tokenFile':str(token_file)}
        self.context_path.write_text(json.dumps(c))
        env={k:v for k,v in self.env.items() if k not in ('RDG_AUTH_STORE','RDG_AUTH_TOKEN')}
        self.assertTrue(json.loads(self.cli('doctor',env=env).stdout)['ready'])
        schema=json.loads(self.cli('schema','--action','add_action','--node','R0',env=env).stdout)['request']
        schema.update(note='Private file route',title='A prepared action',recommended='Known data')
        self.assertTrue(json.loads(self.cli('command',body=schema,env=env).stdout)['saved'])
        token_file.chmod(0o644)
        self.assertFalse(json.loads(self.cli('doctor',env=env).stdout)['ready'])

    def test_lost_response_after_graph_acceptance_is_reported_as_saved(self):
        req=json.loads(self.cli('schema','--action','add_action','--node','R0').stdout)['request']
        req.update(transactionId='accepted-before-error',note='Real accepted candidate',title='Work',recommended='Known data')
        script="""import sys,json
from importlib.machinery import SourceFileLoader
m=SourceFileLoader('lost_response_agent',sys.argv[1]).load_module()
original=m.PKG.execute
def interrupted(*args,**kwargs):
    original(*args,**kwargs)
    raise OSError('simulated response failure AFTER acceptance')
m.PKG.execute=interrupted
out=m.Agent(m.config(sys.argv[2])).command(json.load(sys.stdin))
print(json.dumps(out))
"""
        run=subprocess.run(['python3','-B','-c',script,str(self.home/'tools/rdg-agent.py'),str(self.context_path)],
            input=json.dumps(req),capture_output=True,text=True,env=self.env,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr)
        out=json.loads(run.stdout)
        self.assertTrue(out['saved']);self.assertTrue(out['acceptedBeforeError'])
        self.assertEqual(out['receipt']['state'],'completed')
        self.assertEqual(len([n for n in self.graph()['nodes'] if n['kind']=='action']),1)



    def test_receipt_rejects_symlinked_history_directory(self):
        directory=self.home/'graphs/workspaces/.transactions'
        real=self.home/'actual-journals';directory.rename(real);directory.symlink_to(real,target_is_directory=True)
        result=self.cli('receipt','--transaction-id','create-workspace',ok=False)
        self.assertIn('UNSAFE_RECEIPT',result.stderr)



    def test_failed_receipt_read_after_successful_writer_stays_saved(self):
        req=json.loads(self.cli('schema','--action','add_action','--node','R0').stdout)['request']
        req.update(transactionId='receipt-read-failed',note='Real accepted candidate',title='Work',recommended='Known input')
        script="""import sys,json
from importlib.machinery import SourceFileLoader
m=SourceFileLoader('receipt_failure_agent',sys.argv[1]).load_module()
client=m.Agent(m.config(sys.argv[2]))
original=client.receipt
calls=0
def interrupted(tid):
    global calls
    calls+=1
    if calls==2:raise OSError('simulated receipt read failure after successful writer return')
    return original(tid)
client.receipt=interrupted
print(json.dumps(client.command(json.load(sys.stdin))))
"""
        run=subprocess.run(['python3','-B','-c',script,str(self.home/'tools/rdg-agent.py'),str(self.context_path)],
            input=json.dumps(req),capture_output=True,text=True,env=self.env,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr)
        out=json.loads(run.stdout)
        self.assertTrue(out['saved']);self.assertFalse(out['receipt']['available'])
        receipt=json.loads(self.cli('receipt','--transaction-id','receipt-read-failed').stdout)
        self.assertTrue(receipt['found']);self.assertEqual(receipt['state'],'completed')


if __name__=='__main__':unittest.main()
