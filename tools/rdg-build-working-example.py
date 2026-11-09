#!/usr/bin/env python3
"""One-time local demo construction using real authorized Graph/Plan/Gendocen APIs.

No fabricated workflowExample, event snapshots, receipts or status flags.
Never resets an existing workspace or overwrites an existing Plan/Gendocen state.
The bearer + issuer key are ephemeral (process only); installed applications
must use their normal live grants when continuing to edit this same workspace.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
from importlib.machinery import SourceFileLoader

ROOT=Path(__file__).resolve().parent.parent
TOOLS=ROOT/'tools'
GRAPH='workspaces/requirements-dependencies-demo/graph.json'
PLAN='plans/requirements-dependencies-demo/plan.json'
ENGINE_STATE=ROOT/'.rdg-gendocen-projects/requirements-dependencies-demo'
SLUG='requirements-dependencies-demo'
SPACE='rdg-working-requirements-dependencies-demo'


def load(name,filename):
    return SourceFileLoader(name,str(TOOLS/filename)).load_module()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply',action='store_true',help='Explicitly accept new real owner creation, no overwrite')
    ap.add_argument('--resume',action='store_true',help='Resume this builder only from its accepted transaction journals')
    opts=ap.parse_args()
    if not (opts.apply or opts.resume):
        print('NO_CHANGES: run --apply to create a real teaching workspace via writers')
        return
    target=ROOT/'graphs'/GRAPH
    if opts.resume:
        journal=ROOT/'graphs/workspaces/.transactions/demo-create-owner.json'
        if not (target.is_file() and journal.is_file() and
                json.loads(journal.read_text())['state']=='completed' and
                json.loads(target.read_text()).get('identitySpace')==SPACE):
            raise SystemExit('RESUME_DENIED: missing exact accepted example owner and journal')
    elif target.exists() or (ROOT/PLAN).exists() or ENGINE_STATE.exists():
        raise SystemExit('EXAMPLE_OWNER_ALREADY_EXISTS: refusing to overwrite/replay any existing owner')
    auth=load('demo_auth','rdg-authority.py')
    writer=load('demo_writer','graph-package.py')
    trust=load('demo_trust','rdg-v6-action-trust.py')
    plan_owner=load('demo_plan_owner','rdg-temporal-plan-owner.py')
    gendocen=load('demo_gendocen','rdg-requirement-gendocen.py')
    with tempfile.TemporaryDirectory(prefix='rdg-example-builder-private-') as tmp:
        store=Path(tmp)/'authorization.json'
        boot=auth.Authority(store).init_local(plan_capable=True,graph_read_capable=True)
        key=secrets.token_hex(32)
        os.environ.update(RDG_AUTH_STORE=str(store),RDG_AUTH_TOKEN=boot['token'],
                          RDG_V6_TRUST_KEY=key,RDG_LOCAL_MANUAL_SESSION='1')
        def graph():return json.loads(target.read_text(encoding='utf8'))
        def send(tid,op=None,create=None):
            accepted=ROOT/'graphs/workspaces/.transactions'/('demo-'+tid+'.json')
            if accepted.exists():
                saved=json.loads(accepted.read_text(encoding='utf8'))
                if saved.get('state')!='completed' or [r['file'] for r in saved['records']]!=[GRAPH]:
                    raise RuntimeError('RESUME_NOT_AN_ACCEPTED_EXAMPLE_TRANSACTION: '+tid)
                print('ALREADY_ACCEPTED',tid,flush=True)
                return
            if op is None:
                change={'file':GRAPH,'create':create}
            else:
                g=graph();change={'file':GRAPH,'patch':{'schemaVersion':1,'expectedRevision':g['revision'],
                                                       'operations':[op]}}
                if op.get('event'):
                    op['event']['authorityPrincipal']='bearer:root'
            package={'schemaVersion':1,'transactionId':'demo-'+tid,'changes':[change]}
            if trust.need_trust(package):
                claim={'purpose':'rdg-v6-material-action-v1','principal':'bearer:root',
                       'expiresAt':int(time.time())+600}
                package['trustedApproval']=claim
                claim['signature']=hmac.new(key.encode(),trust.canonical(trust.proof_payload(package)),hashlib.sha256).hexdigest()
            writer.execute(package)
        def event(tag,note,**kwargs):
            return {'id':'EV-DEMO-'+tag,'type':'graph_changed','operation':tag,'by':'assistant',
                    'note':note,**kwargs}
        def graph_edit(tag,action,note,**kwargs):
            ev=event(tag,note);ev['operation']=action
            send(tag,{'op':'graph_edit','action':action,'event':ev,**kwargs})
        def action(tag,rid,title,plus,minus=(),check=(),kind='general'):
            canon={'recommended':[{'id':'C-'+tag,'text':plus,**({'checkRequirements':list(check)} if check else {})}],
                   'contraindicated':[{'id':'N-'+tag,'text':x} for x in minus]}
            send('add-'+tag,{'op':'add_action','requirementId':rid,
                'action':{'id':tag,'kind':'action','title':title,'actionType':kind,
                          'status':'candidate','canonBlock':canon,'qrpe':[]}})
        def select(tag,rid,children=()):
            ev={'id':'EV-DEMO-SELECT-'+tag,'type':'action_selected','actionId':tag,
                'driverRequirementId':rid,'by':'assistant',
                'note':'Выбран существующий Action после проверки его канона. Это не выполнение.'}
            send('select-'+tag,{'op':'select_action','actionId':tag,'event':ev,
                               'children':[{'role':role,'requirement':{'id':child,'kind':'requirement',
                                      'title':title,'status':'active'}} for role,child,title in children]})
        first={'schemaVersion':1,'id':SLUG,'title':'Учебная реальная работа: изменение R и зависимые Actions',
               'revision':1,'planningScale':'module','identitySpace':SPACE,'rootRequirementId':'R0',
               'actionModel':'candidate-v6','purpose':'real-api-teaching-workflow',
               'presentation':{'usage':'working','title':'Рабочий пример · зависимые Requirements и Actions',
                 'description':'Настоящие Graph/Plan owners, история Graph API и Gendocen receipts. Работа ведётся обычными writers.'},
               'nodes':[{'id':'R0','kind':'requirement','status':'active',
                  'title':'Сделать проверяемую рабочую демонстрацию зависимостей RDG',
                  'requirementText':'Продемонстрировать реальные Graph/Plan/API события и Gendocen-обнаружение зависимостей.'}],
               'edges':[],'events':[]}
        send('create-owner',create=first)
        action('A-DESIGN','R0','Развернуть работу в проверяемые подцели',
               'Когда нужна явная декомпозиция через Action и последующий независимый контроль подцелей.',
               ('Не создавать пустые подцели без связи с корневой Requirement.',),kind='decomposition')
        action('A-DESIGN-ALTERNATIVE','R0','Альтернатива: решить задачу без декомпозиции',
               'Когда работа настолько мала, что декомпозиция не повышает проверяемость.',
               ('Не применять для демонстрации ссылок между подцелями и канонами.',))
        select('A-DESIGN','R0',[
          ('subgoal','R-CANON','Проследить, какие способы зависят от актуальности канона'),
          ('subgoal','R-VERIFY','Проверить в Gendocen изменение подписанных входов')])
        action('A-CANON','R-CANON','Поддерживать способ работы с зависимым каноном',
               'Применить только если актуальная формулировка R-CANON соответствует выбранному сценарию.',
               ('Не считать канон пригодным без пересмотра после новой редакции R-CANON.',),check=['R-CANON'])
        action('A-CANON-ALT','R-CANON','Альтернативный способ: заменить проверку ручным осмотром',
               'Применить, если Gendocen невозможно использовать в данной области.',
               ('Не скрывать отсутствие двигателя под видом подтверждённой актуальности.',))
        action('A-VERIFY','R-VERIFY','Проверить API и Gendocen на настоящем рабочем графе',
               'Запускать после создания Graph и Plan owners; читать только реальные engine receipts.',
               ('Не объявлять review_required доказательством ошибочности решения.',),check=['R-CANON'])
        select('A-CANON','R-CANON')
        select('A-VERIFY','R-VERIFY')
        # The real durable Plan exists now, including an initially empty version.
        plan={'schemaVersion':1,'kind':'temporalPlan','id':SLUG,
              'title':'План во времени · '+first['title'],'identitySpace':SPACE,
              'revision':1,'status':'candidate','steps':[],'sequence':[],
              'branches':[],'timeConstraints':[]}
        if not (ROOT/PLAN).exists():
            plan_owner.apply_request(ROOT,str(store),boot['token'],{'transactionId':'demo-init-plan',
                'op':'create','file':PLAN,'expectedRevision':0,'plan':plan})
        def place(tid,nid,kind,date,revision):
            ref={'graphFile':GRAPH,'identitySpace':SPACE,'nodeId':nid}
            field='actionRef' if kind=='action' else 'requirementRef'
            req={'transactionId':'demo-place-'+tid,'op':'edit','file':PLAN,'expectedRevision':revision,
                 'operations':[{'op':'place','step':{'id':'S-'+nid,'title':next(n['title'] for n in graph()['nodes'] if n['id']==nid),
                  'kind':kind,'state':'planned',field:ref},
                 'timeConstraints':[{'stepId':'S-'+nid,'type':'notBefore','at':date,
                  'strength':'soft','basis':'Запланированное положение существующего Graph узла'}]}]}
            # Intentional CAS, never replace a previously edited placement.
            saved=plan_owner.read_snapshot(ROOT,PLAN)['plan']
            if any(step['id']=='S-'+nid for step in saved['steps']):
                return
            req['expectedRevision']=saved['revision']
            plan_owner.apply_request(ROOT,str(store),boot['token'],req)
        place('r-canon','R-CANON','requirement','2026-11-05',1)
        place('a-canon','A-CANON','action','2026-11-06',2)
        place('r-verify','R-VERIFY','requirement','2026-11-07',3)
        # Gendocen baseline: review is limited to structural source linkage,
        # not an attestation that business requirements are true.
        already_reformulated=any(e.get('type')=='requirement_reformulated' and
            e.get('id')=='EV-DEMO-reformulate-canon' for e in graph()['events'])
        if not already_reformulated:
            initial=gendocen.refresh(ROOT/'graphs',[GRAPH],ENGINE_STATE,boot['token'],str(store))
            expected={'R-CANON','A-CANON','A-VERIFY'}
            eligible=[row for row in initial['rows'] if any(src['nodeId']=='R-CANON' for src in row['uses'])]
            if not {'A-CANON','A-VERIFY'}<=set(row['nodeId'] for row in eligible):
                raise RuntimeError('Actual Gendocen did not register Action -> R-CANON links')
            for row in initial['rows']:
                details=gendocen.engine_cli(ENGINE_STATE,'explain',row['target'])
                gendocen.engine_cli(ENGINE_STATE,'validate',row['target'],'--result','still-valid',
                  '--reason','Начальная структурная проверка: ссылки действительно указывают на существующие Graph IDs; не доказательство корректности бизнеса.',
                  '--review-context',details['review_context_id'])
            graph_edit('reformulate-canon','reformulate_requirement',
                'После принятой исходной версии обновили формулировку R-CANON; каноны ссылались на старый снимок.',
                nodeId='R-CANON',changes={'title':'Проверить каноны с учётом новой редакции требований',
                  'requirementText':'Нужно повторно оценить канон каждого зависимого Action после уточнения R-CANON.'})
        after=gendocen.refresh(ROOT/'graphs',[GRAPH],ENGINE_STATE,boot['token'],str(store))
        stale={row['nodeId'] for row in after['rows'] if row['status']=='review_required'}
        if not {'A-CANON','A-VERIFY'}<=stale:
            raise RuntimeError('Actual Gendocen failed to invalidate previously accepted dependent Actions: '+str(stale))
        # We deliberately leave R0/R-CANON and selected Actions unfinished:
        # the actual work demonstrates the need to REVIEW, not a fictional result.
        records=graph()['events']
        if not any(e['type']=='requirement_reformulated' for e in records):
            raise RuntimeError('Missing real writer reformulation event')
        print('REAL_API_TEACHING_WORKSPACE_CREATED',json.dumps({'graphFile':GRAPH,'planFile':PLAN,
            'graphRevision':graph()['revision'],'graphEvents':len(records),
            'planRevision':plan_owner.read_snapshot(ROOT,PLAN)['plan']['revision'],
            'gendocenReviewRequired':sorted(stale),'engineState':str(ENGINE_STATE)},ensure_ascii=False))

if __name__=='__main__':main()
