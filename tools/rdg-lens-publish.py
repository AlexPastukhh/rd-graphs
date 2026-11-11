#!/usr/bin/env python3
"""Publish the reviewed 19-lens content through existing Application operations.

Dry planning is the default. --apply uses the same durable journal for every
preflight/apply/receipt. Existing lens identities, anchors and historical pins
are preserved; working processes and existing recommendation definitions are not
rewritten. Supplied owners require the explicit management option.
"""
import argparse
import copy
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import re
import uuid

ROOT=Path(__file__).resolve().parents[1]
AGENT=SourceFileLoader('lens_publish_agent',str(ROOT/'tools/rdg-agent.py')).load_module()
JOURNAL=SourceFileLoader('lens_publish_journal',str(ROOT/'tools/rdg-example-journal.py')).load_module()
MODEL=SourceFileLoader('lens_publish_model',str(ROOT/'tools/rdg-portable-model.py')).load_module()
PROFILES=SourceFileLoader('lens_publish_profiles',str(ROOT/'tools/rdg-model-profiles.py')).load_module()
PLAN_FILE=ROOT/'tools/rdg-lens-content-plan.json'
VOLATILE={'revision','result','selectionState','review'}
def entities(graph):return {n['id']:n for n in graph['nodes']+graph['objects']}
def content(node):return {k:v for k,v in node.items() if k not in VOLATILE}
def bundle(keys=None):
    plan=json.loads(PLAN_FILE.read_text())
    if keys is not None:plan={k:plan[k] for k in keys}
    graphs={key:json.loads((ROOT/'tools/rdg-agent-lenses'/(key+'-decision.json')).read_text()) for key in plan}
    for g in graphs.values():PROFILES.validate_role(g,'lens')
    return plan,graphs,MODEL.digest(graphs)

def delta_commands(before,desired):
    """Deterministic, additive paper-authoring plan with no identity deletion."""
    old=entities(before);wanted=entities(desired)
    missing=set(old)-set(wanted)
    if missing:raise ValueError('UNMAPPED_EXISTING_ENTITIES:'+','.join(sorted(missing)))
    if before['rootRequirementId']!=desired['rootRequirementId']:raise ValueError('ROOT_ID_CHANGE_FORBIDDEN')
    for ident in old:
        if old[ident]['kind']!=wanted[ident]['kind']:raise ValueError('ENTITY_KIND_CHANGE:'+ident)
    commands=[];present=set(old);edges={e['id']:copy.deepcopy(e) for e in before['edges']}
    target_edges={e['id']:e for e in desired['edges']}
    removed=set(edges)-set(target_edges)
    if removed:raise ValueError('UNMAPPED_EXISTING_RELATIONS:'+','.join(sorted(removed)))
    for ident,e in edges.items():
        if e!=target_edges[ident]:raise ValueError('RELATION_IDENTITY_CHANGE:'+ident)
    for ident,node in wanted.items():
        if ident in old:
            changes={k:v for k,v in content(node).items() if k not in ('id','kind') and old[ident].get(k)!=v}
            leftovers=set(content(old[ident]))-set(content(node))
            if leftovers:raise ValueError('UNMAPPED_EXISTING_FIELDS:'+ident+':'+','.join(sorted(leftovers)))
            if changes:commands.append(('edit-'+ident,'edit',{'nodeId':ident,'changes':changes,'cosmetic':False}))
        else:
            available=present|{ident}
            initial=[e for e in desired['edges'] if e['id'] not in edges and ident in (e['from'],e['to']) and {e['from'],e['to']}<=available]
            value={k:v for k,v in node.items() if k not in VOLATILE}
            data={'entity':value,'location':'graph'}
            if initial:data['initialRelations']=initial
            commands.append(('add-'+ident,'add',data));present.add(ident)
            edges.update({e['id']:e for e in initial})
    for e in desired['edges']:
        if e['id'] not in edges:commands.append(('link-'+e['id'],'link',{'relation':e}))
    # Existing scopes remain identifiable. Scope edits use the ordinary authoring command.
    current_wgs={w['id']:w for w in before['workGraphs']}
    for w in desired['workGraphs']:
        if current_wgs.get(w['id'])!=w:commands.append(('scope-'+w['id'],'work_graph',{'workGraph':w}))
    current_causes={c['requirementId'] for c in before['rootCauses']}
    for cause in desired['rootCauses']:
        if cause['requirementId'] not in current_causes:commands.append(('root-'+cause['id'],'root_cause',{'rootCause':cause}))
    return commands

def verify_graph(actual,desired):
    a=entities(actual);d=entities(desired)
    if set(a)!=set(d):raise ValueError('PUBLISHED_ENTITY_SET_MISMATCH')
    for ident,node in d.items():
        if content(a[ident])!=content(node):raise ValueError('PUBLISHED_CONTENT_MISMATCH:'+ident)
    if {e['id']:e for e in actual['edges']}!={e['id']:e for e in desired['edges']}:raise ValueError('PUBLISHED_RELATIONS_MISMATCH')
    for w in desired['workGraphs']:
        if w not in actual['workGraphs']:raise ValueError('PUBLISHED_SCOPE_MISMATCH:'+w['id'])
    if any(e['type']!='created' for e in actual['events']):raise ValueError('DEFINITION_CONTAINS_EXECUTION')
    if any(n.get('selectionState')=='selected' or n.get('result',{}).get('state') in ('confirmed','completed') for n in a.values()):raise ValueError('FALSE_DEFINITION_EXECUTION')
    return {'entities':len(a),'edges':len(actual['edges']),'sourceSHA256':json.loads(next(n for n in actual['objects'] if 'rdg:lens-source-map' in n.get('tags',[]))['value'])['source']['sha256']}

def inventory(client,graphs):
    catalog=client.call({'method':'catalog'})
    if catalog.get('complete') is False:raise ValueError('INCOMPLETE_CATALOG')
    rows={p['lensKey']:p for p in catalog['packages'] if p.get('role')=='lens'}
    existing={};counts={}
    for key,graph in graphs.items():
        if key in rows:
            row=client.call({'method':'read','packageId':rows[key]['packageId'],'detail':'full'})
            if row['graph']['coreModel']!='rdg-decision-v1':raise ValueError('EXISTING_PROFILE_MISMATCH:'+key)
            commands=delta_commands(row['graph'],graph)
            existing[key]=row
            counts[key]={'mode':'update','commands':len(commands),'packageId':row['package']['packageId'],'immutable':row.get('immutableDefinition',False)}
        else:counts[key]={'mode':'create','commands':1}
    return catalog,existing,counts


def navigation_definitions(graphs,published):
    """Resolve authored prose cross-links to existing qualified lens addresses."""
    from urllib.parse import unquote
    maps={k:json.loads(next(n['value'] for n in g['objects'] if 'rdg:lens-source-map' in n.get('tags',[]))) for k,g in graphs.items()}
    paths={(ROOT/m['source']['path']).resolve():k for k,m in maps.items()}
    definitions={}
    for key,g in graphs.items():
        source=maps[key];ns=entities(g);raw=ns[source['fullTextInfoId']]['value'].splitlines(keepends=True);rules=[]
        for row in source['rows']:
            body=''.join(raw[row['startLine']-1:row['endLine']]);refs=[]
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',body):
                href,_,anchor=target.partition('#')
                if not href or '://' in href:continue
                path=((ROOT/source['source']['path']).parent/unquote(href)).resolve()
                target_key=paths.get(path)
                shared=path==(ROOT/'docs/lenses/requirements.md').resolve()
                if shared:target_key='model'
                if target_key is None or target_key==key or target_key not in published:continue
                target_node='LS-SOURCE-SHARED-REQUIREMENTS' if shared else graphs[target_key]['rootRequirementId']
                if anchor and not shared:
                    target_row=next((r for r in maps[target_key]['rows'] if r['anchor']==unquote(anchor) or unquote(anchor) in r.get('nestedAnchors',[])),None)
                    if target_row is None:raise ValueError('LENS_CROSS_LINK_ANCHOR_MISSING:'+key+':'+target)
                    target_node=next(i for i in target_row['entityIds'] if i.startswith('LS-TEXT-'))
                bound=published[target_key]
                ref={'packageId':bound['packageId'],'identitySpace':bound['identitySpace'],'lensKey':target_key,'nodeId':target_node}
                if ref not in refs:refs.append(ref)
            if not refs:continue
            anchors=[i for i in row['entityIds'] if i.startswith('LS-TEXT-') or ns[i]['kind']=='action']
            for node_id in anchors:
                rules.append({'id':'link-'+MODEL.digest({'node':node_id})[:20],
                    'nodeKinds':[ns[node_id]['kind']],'scope':'identity','anchor':{'packageId':published[key]['packageId'],'identitySpace':published[key]['identitySpace'],'nodeId':node_id},
                    'state':'any','whenText':'Когда при работе с разделом «'+row['title']+'» нужны указанные в нём связанные методики или основания.',
                    'usageText':'Перейти к нужной линзе или её разделу в подходящем объёме. Ссылка раскрывает исходный текст и сохраняет контекст; она не запускает методику.',
                    'lensRefs':refs})
        if rules:
            definitions[key]={'id':str(uuid.uuid5(uuid.UUID(published[key]['packageId']),'source-lens-navigation')),
                'revision':1,'key':'lens-source-'+key,'title':'Связанные методики · '+key,'supplied':False,'authored':True,'rules':rules}
    return definitions

def publish_navigation(client,graphs,state,write,save,progress):
    navigation=state.setdefault('navigation',{})
    definitions=navigation_definitions(graphs,state['verified'])
    for key,definition in definitions.items():
        pid=state['verified'][key]['packageId']
        registry=client.call({'method':'recommendation_catalog','query':definition['key'],'limit':100})
        existing=next((d for d in registry['packages'] if d['id']==definition['id']),None)
        if existing:
            if existing!=definition:raise ValueError('NAVIGATION_DEFINITION_EXISTS_REVIEW_NEW_VERSION:'+key)
            row=client.call({'method':'read','packageId':pid,'detail':'full'})
            if definition['id'] not in row['graph']['recommendationPackageIds']:raise ValueError('NAVIGATION_ATTACHMENT_UNCONFIRMED:'+key)
        else:
            row=client.call({'method':'read','packageId':pid,'detail':'full'})
            req=client.call({'method':'schema','op':'recommendation_edit'})['request']
            req.update(action='create',definition=definition,expectedRegistryRevision=registry['registryRevision'],
                attachTo={'packageId':pid,'expectedPackageRevision':row['package']['revision'],'expectedGraphRevision':row['graph']['revision']},
                note='Адресные переходы из сохранённых Markdown-разделов линзы '+key+'; существующие общие definitions и рабочие процессы сохраняются.')
            # Schema may expose edit-only optional selectors.
            req.pop('packageId',None)
            write(key+'/navigation',req)
            row=client.call({'method':'read','packageId':pid,'detail':'full'})
            verified=client.call({'method':'recommendation_catalog','query':definition['key'],'limit':100})
            if not any(d==definition for d in verified['packages']):raise ValueError('NAVIGATION_READBACK_MISMATCH:'+key)
            if definition['id'] not in row['graph']['recommendationPackageIds']:raise ValueError('NAVIGATION_ATTACHMENT_UNCONFIRMED:'+key)
        verify_graph(row['graph'],graphs[key])
        state['verified'][key].update(packageRevision=row['package']['revision'],graphRevision=row['graph']['revision'])
        navigation[key]={'definitionId':definition['id'],'rules':len(definition['rules'])};save()
        progress('LENS_NAVIGATION_READY '+key+' '+str(len(definition['rules'])))
    return navigation


def run(client,journal_file,*,apply=False,manage_supplied=False,keys=None,progress=print):
    plan,graphs,digest=bundle(keys)
    journal=JOURNAL.Journal(Path(journal_file),{'operations':{},'bundleSHA256':digest,'lensKeys':list(graphs),'verified':{}})
    state=journal.state
    if state['bundleSHA256']!=digest:raise ValueError('LENS_SOURCE_BUNDLE_CHANGED_USE_NEW_REVIEWED_JOURNAL')
    def save(key=None):journal.append(key)
    def write(key,request):
        op=state['operations'].get(key)
        if op is None:op={'request':request};state['operations'][key]=op;save(key)
        req=op['request'];pid=req.get('targetPackageId') or req.get('attachTo',{}).get('packageId') or str(uuid.uuid5(uuid.UUID(req['transactionId']),'package'))
        if op.get('applyAttempted'):
            receipt=client.call({'method':'receipt','packageId':pid,'transactionId':req['transactionId']})
            op['receipt']=receipt;save(key)
            if receipt.get('found') and receipt.get('published'):
                if not op.get('result',{}).get('published'):
                    r=receipt['receipt']
                    op['result']={'published':True,'reconciledFromReceipt':True,'packages':[{'packageId':pid,'revision':r['packageRevision'],'receipt':r}]};save(key)
                return op['result']
            raise RuntimeError('UNCERTAIN_LENS_OPERATION_STOP:'+req['transactionId'])
        op['preview']=client.call({'method':'preflight','request':req});save(key)
        op['applyAttempted']=True;save(key)
        try:op['result']=client.call({'method':'apply','request':req,'expectedInputBinding':op['preview']['inputBinding']});save(key)
        except Exception as exc:
            op['uncertain']=type(exc).__name__;save(key)
            raise RuntimeError('UNCERTAIN_LENS_OPERATION_SAVED:'+req['transactionId']) from exc
        if not op['result'].get('published'):raise RuntimeError('LENS_PUBLICATION_UNCONFIRMED:'+req['transactionId'])
        op['receipt']=client.call({'method':'receipt','packageId':pid,'transactionId':req['transactionId']});save(key)
        if not op['receipt'].get('found') or not op['receipt'].get('published'):raise RuntimeError('LENS_RECEIPT_UNCONFIRMED:'+req['transactionId'])
        return op['result']
    try:
        # Large immutable inventory belongs in one journal record, not repeated metadata.
        if state.get('inventory'):
            state['operations']['$inventory']={'snapshot':state.pop('inventory')};save('$inventory')
        if '$inventory' not in state['operations']:
            catalog,existing,counts=inventory(client,graphs)
            state['operations']['$inventory']={'snapshot':{'catalog':catalog,'existing':existing,'counts':counts}};save('$inventory')
        else:
            snapshot=state['operations']['$inventory']['snapshot']
            catalog=snapshot['catalog'];existing=snapshot['existing'];counts=snapshot['counts']
        progress('LENS_PLAN '+json.dumps({'bundleSHA256':digest,'lenses':counts},ensure_ascii=False))
        if not apply:return {'planned':True,'counts':counts,'bundleSHA256':digest}
        if not manage_supplied and any(r.get('immutableDefinition') for r in existing.values()):raise ValueError('EXPLICIT_SUPPLIED_MANAGEMENT_REQUIRED')
        # Mutations affect only the requested lens owners, never working processes.
        for key,desired in graphs.items():
            if key in state['verified']:
                row=client.call({'method':'read','packageId':state['verified'][key]['packageId'],'detail':'full'})
                verify_graph(row['graph'],desired);continue
            old=existing.get(key)
            if old is None:
                req=client.call({'method':'schema','op':'create','coreModel':'rdg-decision-v1','role':'lens'})['request']
                req.update(path='lenses/fundamental/'+key,lensKey=key,title=desired['title'],scope=entities(desired)[desired['rootRequirementId']]['scope'],
                    rootReason='Поручение пользователя: перенести согласованные Markdown-линзы в RDG с сохранением исходников и возможностью работы в приложении.',graph=desired)
                result=write(key+'/create',req);pid=result['packages'][0]['packageId']
            else:
                pid=old['package']['packageId']
                if old.get('immutableDefinition'):
                    req=client.call({'method':'schema','op':'lens_manage','packageId':pid})['request']
                    req.update(confirmOwnerManagement=True,note='Поручение владельца о переносе 19 согласованных линз в приложение. Сохраняются packageId, identitySpace, старые anchors, версии и история; меняется содержание этой линзы.')
                    write(key+'/manage',req)
                row=client.call({'method':'read','packageId':pid,'detail':'full'})
                # Build once against the reviewed initial graph. Each request is persisted before effect.
                commands=delta_commands(old['graph'],desired)
                package_revision=row['package']['revision'];graph_revision=row['graph']['revision']
                for index,(name,command,data) in enumerate(commands):
                    op_key=key+'/'+name
                    if op_key in state['operations']:
                        req=state['operations'][op_key]['request']
                    else:
                        message={'method':'schema','op':'paper_edit','packageId':pid,'nodeId':data.get('nodeId',old['graph']['rootRequirementId']),'command':command}
                        if command=='add':message['entityKind']=data['entity']['kind']
                        req=client.call(message)['request']
                        if (req['expectedPackageRevision'],req['expectedGraphRevision'])!=(package_revision,graph_revision):raise ValueError('LENS_CHANGED_DURING_AUTHORING:'+key)
                        req.update(data=data,note='Структурный перенос '+key+': '+name+'; полный исходник и карта сохранены.')
                    result=write(op_key,req)
                    changed=next(p for p in result['packages'] if p['packageId']==pid)
                    package_revision=changed['revision'];graph_revision=changed['receipt']['graphRevision']
                    if (index+1)%10==0:progress('LENS_PROGRESS '+key+' '+str(index+1)+'/'+str(len(commands)))
            actual=client.call({'method':'read','packageId':pid,'detail':'full'})
            checked=verify_graph(actual['graph'],desired)
            if old:
                ref=old['references'][old['graph']['rootRequirementId']]
                pin={k:ref[k] for k in ('packageId','identitySpace','graphRevision','sha256')}
                historical=client.call({'method':'source_snapshot','packageId':pid,'pin':pin})
                if historical['graph']!=old['graph']:raise ValueError('HISTORICAL_LENS_CHANGED:'+key)
                if actual['package']['identitySpace']!=old['package']['identitySpace']:raise ValueError('LENS_IDENTITY_CHANGED')
            state['verified'][key]={'packageId':pid,'identitySpace':actual['package']['identitySpace'],'packageRevision':actual['package']['revision'],
                                    'graphRevision':actual['graph']['revision'],**checked};save()
            progress('LENS_READY '+key+' '+pid)
        publish_navigation(client,graphs,state,write,lambda:save(),progress)
        progress('STRUCTURED_LENSES_READY '+json.dumps(state['verified'],ensure_ascii=False))
        return state
    finally:journal.checkpoint()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--context',required=True);parser.add_argument('--journal',required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--manage-existing-supplied',action='store_true')
    args=parser.parse_args()
    client=AGENT.portable_application(AGENT.config(args.context))
    run(client,args.journal,apply=args.apply,manage_supplied=args.manage_existing_supplied)
