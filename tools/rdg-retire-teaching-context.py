#!/usr/bin/env python3
"""Retire the UI-only context through real Graph writer transactions.

No direct JSON editing: archive the three existing CONTEXT_FOR edges and
mark the now-detached context inactive, retaining snapshots in Graph history.
"""
import hashlib,hmac,json,os,secrets,tempfile,time
from pathlib import Path
from importlib.machinery import SourceFileLoader
ROOT=Path(__file__).resolve().parents[1]
GRAPH='workspaces/requirements-dependencies-demo/graph.json'
CONTEXT_ID='C-ASSURANCE'

def module(name,script):return SourceFileLoader(name,str(ROOT/'tools'/script)).load_module()
def main():
    auth=module('rdg_retire_auth','rdg-authority.py')
    writer=module('rdg_retire_writer','graph-package.py')
    trust=module('rdg_retire_trust','rdg-v6-action-trust.py')
    gendocen=module('rdg_retire_engine','rdg-requirement-gendocen.py')
    path=ROOT/'graphs'/GRAPH
    def read():return json.loads(path.read_text(encoding='utf8'))
    initial=read()
    if (initial.get('actionModel')!='candidate-v6' or
        initial.get('id')!='requirements-dependencies-demo' or
        not any(n['id']==CONTEXT_ID and n['kind']=='context' for n in initial['nodes'])):
        raise RuntimeError('EXPECTED_EXISTING_ACTIVE_TEACHING_CONTEXT')
    with tempfile.TemporaryDirectory(prefix='rdg-retire-context-bearer-') as folder:
        grant=Path(folder)/'auth.json'
        issued=auth.Authority(grant).init_local(plan_capable=True,graph_read_capable=True)
        key=secrets.token_hex(32)
        os.environ.update(RDG_AUTH_STORE=str(grant),RDG_AUTH_TOKEN=issued['token'],
            RDG_LOCAL_MANUAL_SESSION='1',RDG_V6_TRUST_KEY=key)
        def apply(tag,action,**kwargs):
            tid='demo-retire-context-'+tag
            receipt=ROOT/'graphs/workspaces/.transactions'/(tid+'.json')
            if receipt.exists():
                j=json.loads(receipt.read_text(encoding='utf8'))
                if j['state']!='completed' or len(j['records'])!=1 or j['records'][0]['file']!=GRAPH:
                    raise RuntimeError('INVALID_EXISTING_RETIREMENT_RECEIPT '+tid)
                print('ALREADY_ACCEPTED',tid,flush=True);return
            current=read()
            note=('Убрана демонстрационная контекстная связь '+tag+
                  ': это не самостоятельное ограничение проекта. Старые события сохранены.'
                  if action=='archive_edge' else
                  'Деактивирован искусственный контекст C-ASSURANCE: он создавался лишь для проверки переключателя. История остаётся доступной; отдельного действия или выполнения не было.')
            event={'id':'EV-DEMO-RETIRE-CONTEXT-'+tag,'type':'graph_changed',
                'operation':action,'by':'assistant','authorityPrincipal':'bearer:root','note':note}
            pkg={'schemaVersion':1,'transactionId':tid,'changes':[{'file':GRAPH,
                'patch':{'schemaVersion':1,'expectedRevision':current['revision'],
                    'operations':[{'op':'graph_edit','action':action,'event':event,**kwargs}]}}]}
            if trust.need_trust(pkg):
                pkg['trustedApproval']={'purpose':'rdg-v6-material-action-v1',
                    'principal':'bearer:root','expiresAt':int(time.time())+600}
                pkg['trustedApproval']['signature']=hmac.new(key.encode(),
                    trust.canonical(trust.proof_payload(pkg)),hashlib.sha256).hexdigest()
            writer.execute(pkg)
            print('WRITER_ACCEPTED',tid,'revision',read()['revision'],flush=True)
        for target in ('A-DESIGN','A-CANON','A-VERIFY'):
            edge='context-for-'+target
            if any(e['id']==edge and e.get('archived') is not True for e in read()['edges']):
                apply(target,'archive_edge',edgeId=edge)
        context=next(n for n in read()['nodes'] if n['id']==CONTEXT_ID)
        if context.get('active') is not False:
            apply('deactivate','edit_node',nodeId=CONTEXT_ID,changes={'active':False})
        g=read()
        assert all(e.get('archived') is True for e in g['edges'] if
                   e['type']=='CONTEXT_FOR' and e['from']==CONTEXT_ID)
        assert next(n for n in g['nodes'] if n['id']==CONTEXT_ID)['active'] is False
        report=gendocen.refresh(ROOT/'graphs',[GRAPH],
            ROOT/'.rdg-gendocen-projects/requirements-dependencies-demo',issued['token'],str(grant))
        print('RETIRED_ARTIFICIAL_CONTEXT',json.dumps({'graphRevision':g['revision'],
            'activeContextEdges':sum(e.get('archived') is not True and
                 e.get('type')=='CONTEXT_FOR' for e in g['edges']),
            'reviewRequired':[x['nodeId'] for x in report['rows'] if x['status']=='review_required']},
            ensure_ascii=False),flush=True)
if __name__=='__main__':main()
