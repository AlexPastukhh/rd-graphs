#!/usr/bin/env python3
"""Small empirical T1/T2 workflow, using only ephemeral Decision owners.

This is a deterministic client scenario, not proof of autonomous AI behavior.
Print measured payload sizes and timings, never assert wall-clock thresholds.
"""
from importlib.machinery import SourceFileLoader
from pathlib import Path
from time import perf_counter
import json
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
T=SourceFileLoader('workflow_fixture',str(ROOT/'tests/rdg-portable-service.test.py')).load_module()
P=SourceFileLoader('workflow_cli',str(ROOT/'tools/rdg-portable.py')).load_module()


class WorkflowExperiment(unittest.TestCase):
    setUp=T.PortableApplication.setUp
    config=T.PortableApplication.config
    app=T.PortableApplication.app
    sources=T.PortableApplication.sources

    @staticmethod
    def wire_steps():
        a=lambda name: {'$alias':name}
        return [
            {'alias':'load','op':'core','command':'add','data':{
                'entity':{'kind':'requirement','title':'Serve changing load',
                          'description':'Account for variable demand','scope':'Synthetic ticket service'},
                'initialRelations':[{'id':'LOAD-DERIVES','type':'DERIVES','from':'R1','to':a('load')}]}},
            {'alias':'queue','op':'core','command':'add','data':{
                'entity':{'kind':'decision','title':'Queue requests','description':'Buffer peaks'},
                'initialRelations':[{'id':'QUEUE-DRIVES','type':'DRIVES','from':a('load'),'to':a('queue')}]}},
            {'alias':'scale','op':'core','command':'add','data':{
                'entity':{'kind':'decision','title':'Scale workers','description':'Add concurrent workers'},
                'initialRelations':[{'id':'SCALE-DRIVES','type':'DRIVES','from':a('load'),'to':a('scale')}]}},
            {'alias':'taskQueue','op':'core','command':'add','data':{
                'entity':{'kind':'action','title':'Prototype the queue','description':'Experiment only',
                          'actionType':'task','lowLevel':False},
                'initialRelations':[{'id':'QUEUE-TASK','type':'REQUIRES_ACTION','from':a('queue'),'to':a('taskQueue')}]}},
            {'alias':'taskScale','op':'core','command':'add','data':{
                'entity':{'kind':'action','title':'Estimate worker budget','description':'Experiment only',
                          'actionType':'task','lowLevel':False},
                'initialRelations':[{'id':'SCALE-TASK','type':'REQUIRES_ACTION','from':a('scale'),'to':a('taskScale')}]}},
            {'alias':'facts','op':'core','command':'context_group','data':{
                'action':'save','title':'Observed constraints','parentId':None}},
            {'alias':'budget','op':'core','command':'add','data':{
                'entity':{'kind':'context','title':'Budget ceiling','description':'Synthetic input only',
                          'value':'Fixed monthly infrastructure budget','contextGroupId':a('facts')}}},
            {'alias':'canon','op':'core','command':'add','data':{
                'entity':{'kind':'canon','title':'Measure queue latency','description':'Diagnostic rule',
                          'guidance':'Measure p95 waiting time before selecting a queue.'},
                'initialRelations':[{'id':'CANON-QUEUE','type':'CANON_FOR','from':a('canon'),'to':a('queue')}]}},
            {'alias':'role','op':'core','command':'decision_context','data':{
                'nodeId':a('queue'),'sourceId':a('budget'),'action':'save',
                'comment':'Operating cost is a constraint on queue adoption.'}},
            {'alias':'risk','op':'core','command':'add','data':{
                'entity':{'kind':'finding','title':'Queue may delay urgent work',
                          'description':'Queueing can add latency under peaks.',
                          'subjectId':a('queue'),'findingType':'risk',
                          'rationale':'Peak arrival rate is not yet measured','evidenceIds':[]}}},
            {'alias':'plan','op':'plan_create','title':'Investigate alternatives'},
            {'alias':'queuePlacement','op':'place','nodeId':a('taskQueue'),'at':'2026-11-11'},
            {'alias':'scalePlacement','op':'place','nodeId':a('taskScale'),'at':'2026-11-12'}]

    def test_isolated_branch_compact_read_and_metrics(self):
        app=self.app()
        ident=app.request({'op':'create','transactionId':str(uuid.uuid4()),
           'path':'working/t1t2-experiment-'+uuid.uuid4().hex,'role':'working',
           'title':'Ticket load: synthetic experiment','scope':'Synthetic acceptance only',
           'coreModel':'rdg-decision-v1','rootReason':'Explore ticket throughput under fixed cost'})['packages'][0]['packageId']
        api_calls=0
        def call(message):
            nonlocal api_calls
            api_calls+=1
            started=perf_counter()
            out=app.call(message)
            elapsed=(perf_counter()-started)*1000
            return out,round(elapsed,2)
        form,_=call({'method':'schema','op':'batch','packageId':ident})
        request=form['request'];request['note']='Synthetic alternatives; no decision accepted'
        request['steps']=self.wire_steps()
        baseline=self.sources()
        preview,t_pre=call({'method':'preflight','request':request})
        self.assertEqual(baseline,self.sources(),'Preflight writes are prohibited')
        aliases=preview['effects']['aliasIds']
        self.assertEqual(len(aliases),13)
        applied,t_apply=call({'method':'apply','request':request,
                              'expectedInputBinding':preview['inputBinding']})
        self.assertTrue(applied['published'])
        self.assertEqual(len(applied['packages']),1)
        self.assertEqual(applied['packages'][0]['receipt']['effects']['aliasIds'],aliases)
        full,t_full=call({'method':'read','packageId':ident,'includePlan':True})
        overview,t_overview=call({'method':'read','packageId':ident,'detail':'summary','limit':10})
        card,t_card=call({'method':'read','packageId':ident,'detail':'item',
            'nodeId':aliases['queue'],'include':['context','canon','findings'],'limit':10})
        plan,t_plan=call({'method':'read','packageId':ident,'detail':'summary','include':['plan'],'limit':10})
        history,t_history=call({'method':'history','packageId':ident,'detail':'compact','limit':10})
        self.assertEqual(card['item']['selectionState'],'discovered')
        self.assertEqual(next(n for n in full['graph']['nodes'] if n['id']==aliases['scale'])['selectionState'],'discovered')
        self.assertEqual(card['data']['context']['items'][0]['sourceId'],aliases['budget'])
        self.assertEqual(card['data']['canon']['items'][0]['id'],aliases['canon'])
        self.assertEqual(card['data']['findings']['items'][0]['id'],aliases['risk'])
        self.assertEqual({row['ref']['nodeId'] for row in plan['data']['plan']['items']},
                         {aliases['taskQueue'],aliases['taskScale']})
        self.assertGreaterEqual(len(full['graph']['events']),11)
        self.assertEqual(len({e['id'] for e in full['graph']['events']}),len(full['graph']['events']))
        self.assertEqual(len(full['plan']['steps']),2)
        self.assertFalse(overview['loaded']['context'])
        self.assertFalse(card['loaded']['plan'])
        self.assertEqual(len(full['graph']['events']),history['data']['events']['page']['total'])
        restarted=P.application(self.config(),self.token)
        self.assertEqual(restarted.read(ident,True)['plan'],full['plan'])
        self.assertTrue(app.call({'method':'receipt','packageId':ident,
            'transactionId':request['transactionId']})['found'])
        def size(o):return len(json.dumps(o,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
        measurements={'scenario':'synthetic-ticket-processing-branch',
            'coreSteps':10,'planSteps':3,'apiCallsIncludingSchemaAndReads':api_calls,
            'timingMs':{'preflight':t_pre,'apply':t_apply,'fullRead':t_full,
                'overviewRead':t_overview,'decisionCard':t_card,
                'planRead':t_plan,'compactHistory':t_history},
            'responseBytes':{'fullRead':size(full),'overview':size(overview),
                'decisionCard':size(card),'planPage':size(plan),'historyPage':size(history)},
            'aliases':len(aliases),'graphEvents':len(full['graph']['events']),
            'decisionsSelected':sum(n.get('selectionState')=='selected' for n in full['graph']['nodes']),
            'planPlacements':len(full['plan']['steps'])}
        self.assertLess(size(overview),size(full))
        print('RDG_T1_T2_WORKFLOW_METRICS '+json.dumps(measurements,ensure_ascii=False,sort_keys=True))


    def test_ten_graph_operations_batch_vs_separate_transactions(self):
        """Compare the same semantic edit sequence, not different work products."""
        def create_owner(label):
            app=self.app()
            return app.request({'op':'create','transactionId':str(uuid.uuid4()),
                'path':'working/t1t2-'+label+'-'+uuid.uuid4().hex,
                'role':'working','title':'T1 T2 comparison',
                'scope':'Synthetic ticket service','coreModel':'rdg-decision-v1',
                'rootReason':'Explore ticket throughput under fixed cost'})['packages'][0]['packageId']
        def resolve(value, aliases):
            if isinstance(value,dict):
                if set(value)=={'$alias'}:return aliases[value['$alias']]
                return {k:resolve(v,aliases) for k,v in value.items()}
            if isinstance(value,list):return [resolve(v,aliases) for v in value]
            return value
        # Each owner begins with identical synthetic graph semantics and independent identity.
        app=self.app()
        separate=create_owner('separate')
        batched=create_owner('batch')
        steps=self.wire_steps()[:10]
        # A common UUID seed allows cross-run IDs to be directly comparable.
        seed=uuid.uuid4()
        aliases={}
        start=app.call({'method':'read','packageId':separate,'detail':'summary','limit':1})
        package_revision=start['package']['revision']
        graph_revision=start['graph']['revision']
        calls_individual=1
        began=perf_counter()
        for step in steps:
            # Resolve a previous alias before allocating the new stable ID.
            # Self-references in initialRelations resolve to the just allocated ID.
            data=step['data']
            command=step['command'];alias=step['alias']
            if command=='add':
                aliases[alias]=str(uuid.uuid5(seed,'entity:'+alias))
            elif command=='context_group':
                aliases[alias]=str(uuid.uuid5(seed,'context-group:'+alias))
            data=resolve(data,aliases)
            if command=='add':data['entity']['id']=aliases[alias]
            if command=='context_group':data['id']=aliases[alias]
            transaction={'op':'core','transactionId':str(uuid.uuid4()),
                'targetPackageId':separate,'expectedPackageRevision':package_revision,
                'expectedGraphRevision':graph_revision,
                'command':command,'data':data,'note':'Synthetic comparison step '+alias}
            app.call({'method':'preflight','request':transaction})
            result=app.call({'method':'apply','request':transaction})
            calls_individual+=2
            receipt=result['packages'][0]['receipt']
            package_revision=receipt['packageRevision'];graph_revision=receipt['graphRevision']
        elapsed_individual=round((perf_counter()-began)*1000,2)
        form=app.call({'method':'schema','op':'batch','packageId':batched})
        request=form['request'];request['note']='Same synthetic branch in one package'
        request['transactionId']=str(seed)
        request['steps']=steps
        began=perf_counter()
        preview=app.call({'method':'preflight','request':request})
        outcome=app.call({'method':'apply','request':request,
                          'expectedInputBinding':preview['inputBinding']})
        elapsed_batch=round((perf_counter()-began)*1000,2)
        one=app.read(separate)['graph']
        other=app.read(batched)['graph']
        def normalized(graph):
            return {'nodes':sorted((n['kind'],n['title'],n.get('description'))
                                  for n in graph['nodes']),
                    'objects':sorted((n['kind'],n['title'],n.get('description'))
                                    for n in graph['objects']),
                    'edges':sorted((e['type'],e['from'],e['to'])
                                   for e in graph['edges'])}
        # Root IDs are normalized as well, because these are different owner identities.
        self.assertEqual(normalized(one),normalized(other))
        self.assertEqual(outcome['packages'][0]['receipt']['effects']['stepCount'],len(steps))
        print('RDG_T1_T2_COMPARISON '+json.dumps({
            'coreSteps':len(steps),'separatePreflightApplyCalls':calls_individual-1,
            'batchPreflightApplyCalls':2,'individualElapsedMs':elapsed_individual,
            'batchElapsedMs':elapsed_batch,
            'separatePackageRevision':package_revision,
            'batchPackageRevision':outcome['packages'][0]['revision'],
            'note':'local calls; not network RPC, single trial'
        },sort_keys=True))


if __name__=='__main__':unittest.main()
