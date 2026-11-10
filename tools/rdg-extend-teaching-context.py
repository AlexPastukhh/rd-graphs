#!/usr/bin/env python3
"""Extend the real candidate-v6 teaching Graph via ordinary authorized API.

Idempotent against accepted writer journals; does not invent completion facts,
replace Graph/Plan owners, or persist credentials. All accepted mutations are
separate real graph_edit operations with event notes and CAS revisions.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
from importlib.machinery import SourceFileLoader

ROOT=Path(__file__).resolve().parents[1]
GRAPH='workspaces/requirements-dependencies-demo/graph.json'
SLUG='requirements-dependencies-demo'
NID='C-ASSURANCE'
TITLE='Условие выбора: учитывать актуальность требований и канонов'
TARGETS=['A-DESIGN','A-CANON','A-VERIFY']


def load(name,filename):
    return SourceFileLoader(name,str(ROOT/'tools'/filename)).load_module()


def main():
    graph_path=ROOT/'graphs'/GRAPH
    if not graph_path.is_file():raise RuntimeError('CANONICAL_TEACHING_GRAPH_NOT_FOUND')
    auth=load('teaching_context_auth','rdg-authority.py')
    writer=load('teaching_context_writer','graph-package.py')
    trust=load('teaching_context_trust','rdg-v6-action-trust.py')
    gendocen=load('teaching_context_gendocen','rdg-requirement-gendocen.py')
    with tempfile.TemporaryDirectory(prefix='rdg-demo-context-private-') as folder:
        grant=Path(folder)/'authorization.json'
        bearer=auth.Authority(grant).init_local(plan_capable=True,graph_read_capable=True)
        key=secrets.token_hex(32)
        os.environ.update(RDG_AUTH_STORE=str(grant),RDG_AUTH_TOKEN=bearer['token'],
            RDG_LOCAL_MANUAL_SESSION='1',RDG_V6_TRUST_KEY=key)

        def graph():return json.loads(graph_path.read_text(encoding='utf8'))
        def commit(suffix,action,**arguments):
            tid='demo-context-'+suffix
            journal=ROOT/'graphs/workspaces/.transactions'/(tid+'.json')
            if journal.exists():
                record=json.loads(journal.read_text(encoding='utf8'))
                if record['state']!='completed' or len(record['records'])!=1 or record['records'][0]['file']!=GRAPH:
                    raise RuntimeError('INCONSISTENT_ACCEPTED_WRITER_RECEIPT: '+tid)
                print('ALREADY_ACCEPTED',tid,flush=True)
                return
            current=graph()
            if current.get('actionModel')!='candidate-v6' or current.get('id')!=SLUG:
                raise RuntimeError('WRONG_GRAPH_MODEL_OR_OWNER')
            note={
                'create':'Добавлено реальное условие выбора: нужно проверять актуальность требований и канонов. Контекст не означает выполненную работу.',
                'A-DESIGN':'Условие применяется к выбору способа декомпозиции исходной цели. Это основание выбора, не новая подцель.',
                'A-CANON':'Условие применяется к Action проверки канона: изменение R требует пересмотра применимости канона.',
                'A-VERIFY':'Условие применяется к проверке Gendocen: предупреждение review_required не доказывает выполнение Action.',
            }[suffix]
            event={'id':'EV-DEMO-CONTEXT-'+suffix,'type':'graph_changed',
                'operation':action,'by':'assistant','authorityPrincipal':'bearer:root','note':note}
            op={'op':'graph_edit','action':action,'event':event,**arguments}
            package={'schemaVersion':1,'transactionId':tid,
              'changes':[{'file':GRAPH,'patch':{'schemaVersion':1,
                'expectedRevision':current['revision'],'operations':[op]}}]}
            if trust.need_trust(package):
                package['trustedApproval']={'purpose':'rdg-v6-material-action-v1',
                    'principal':'bearer:root','expiresAt':int(time.time())+600}
                package['trustedApproval']['signature']=hmac.new(key.encode(),
                    trust.canonical(trust.proof_payload(package)),hashlib.sha256).hexdigest()
            writer.execute(package)
            print('ACCEPTED_REAL_API',tid,'revision',graph()['revision'],flush=True)

        present=graph()
        if not any(n['id']==NID for n in present['nodes']):
            commit('create','create_context',node={'id':NID,'kind':'context',
                'title':TITLE,'contextText':'При выборе способа работы нужно учитывать актуальную редакцию R и проверяемые каноны. Gendocen фиксирует необходимость пересмотра, но не доказывает результат.'})
        for target in TARGETS:
            edge='context-for-'+target
            if any(e['id']==edge for e in graph()['edges']):continue
            commit(target,'add_edge',edge={'id':edge,'type':'CONTEXT_FOR','from':NID,'to':target})
        result=graph()
        if not all(any(e['type']=='CONTEXT_FOR' and e['from']==NID and e['to']==target
                       for e in result['edges']) for target in TARGETS):
            raise RuntimeError('REAL_CONTEXT_RELATIONS_NOT_PERSISTED')
        report=gendocen.refresh(ROOT/'graphs',[GRAPH],
            ROOT/'.rdg-gendocen-projects'/SLUG,bearer['token'],str(grant))
        print('REAL_CONTEXT_GRAPH_AND_GENDOCEN',json.dumps({
          'revision':result['revision'],'contextEdges':len([e for e in result['edges'] if e['type']=='CONTEXT_FOR']),
          'engineRows':len(report['rows']),
          'reviewRequired':sorted(x['nodeId'] for x in report['rows'] if x['status']=='review_required')},
          ensure_ascii=False),flush=True)

if __name__=='__main__':main()
