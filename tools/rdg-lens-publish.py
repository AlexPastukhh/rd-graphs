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
    advice={key:p.get('recommendationAdvice',[]) for key,p in plan.items()}
    return plan,graphs,MODEL.digest({'graphs':graphs,'recommendationAdvice':advice})

def delta_commands(before,desired):
    """Deterministic, additive paper-authoring plan with no identity deletion."""
    old=entities(before);wanted=entities(desired)
    missing=set(old)-set(wanted)
    if missing:raise ValueError('UNMAPPED_EXISTING_ENTITIES:'+','.join(sorted(missing)))
    if before['rootRequirementId']!=desired['rootRequirementId']:raise ValueError('ROOT_ID_CHANGE_FORBIDDEN')
    for ident in old:
        if old[ident]['kind']!=wanted[ident]['kind']:raise ValueError('ENTITY_KIND_CHANGE:'+ident)
    commands=[];present=set(old);edges={e['id']:copy.deepcopy(e) for e in before['edges']}
    if before['title']!=desired['title']:
        commands.append(('graph-title','graph_title',{'title':desired['title']}))
    target_edges={e['id']:e for e in desired['edges']}
    current_groups={group['id']:group for group in before.get('decisionGroups',[])}
    target_groups={group['id']:group for group in desired.get('decisionGroups',[])}
    removed_groups=set(current_groups)-set(target_groups)
    if removed_groups:raise ValueError('UNMAPPED_EXISTING_GROUPS:'+','.join(sorted(removed_groups)))
    memberships={(group['parentId'],m['decisionId']) for group in target_groups.values() for m in group['members']}
    removed=set(edges)-set(target_edges)
    replaced={ident for ident in removed if edges[ident]['type']=='DRIVES' and (edges[ident]['from'],edges[ident]['to']) in memberships}
    remapped={ident for ident in removed-replaced if ident.startswith('LS-EDGE-') and edges[ident]['from'].startswith('LS-TEXT-')
              and edges[ident]['type'] in ('CANON_FOR','INFO_FOR') and any(e['type']==edges[ident]['type'] and e['to']==edges[ident]['to']
              and e['from'].startswith('LS-TEXT-') for e in desired['edges'])}
    if removed-replaced-remapped:raise ValueError('UNMAPPED_EXISTING_RELATIONS:'+','.join(sorted(removed-replaced-remapped)))
    for ident,e in edges.items():
        if ident not in replaced|remapped and e!=target_edges[ident]:raise ValueError('RELATION_IDENTITY_CHANGE:'+ident)
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
    for ident in sorted(remapped):
        commands.append(('unlink-'+ident,'unlink',{'relationId':ident}))
    for e in desired['edges']:
        if e['id'] not in edges:commands.append(('link-'+e['id'],'link',{'relation':e}))
    # The existing decision_group command replaces matching DRIVES atomically.
    for group in desired.get('decisionGroups',[]):
        if current_groups.get(group['id'])!=group:
            commands.append(('group-'+group['id'],'decision_group',{'group':group}))
    # Existing scopes remain identifiable. Scope edits use the ordinary authoring command.
    current_wgs={w['id']:w for w in before['workGraphs']}
    for w in desired['workGraphs']:
        if current_wgs.get(w['id'])!=w:commands.append(('scope-'+w['id'],'work_graph',{'workGraph':w}))
    current_causes={c['id']:c for c in before['rootCauses']}
    target_causes={c['id']:c for c in desired['rootCauses']}
    if set(current_causes)-set(target_causes):
        raise ValueError('UNMAPPED_EXISTING_ROOT_CAUSES:'+','.join(sorted(set(current_causes)-set(target_causes))))
    for cause in desired['rootCauses']:
        if current_causes.get(cause['id'])!=cause:
            commands.append(('root-'+cause['id'],'root_cause',{'cause':cause}))
    return commands

def verify_graph(actual,desired):
    if actual['title']!=desired['title']:raise ValueError('PUBLISHED_TITLE_MISMATCH')
    if actual['rootRequirementId']!=desired['rootRequirementId']:raise ValueError('PUBLISHED_ROOT_MISMATCH')
    a=entities(actual);d=entities(desired)
    if set(a)!=set(d):raise ValueError('PUBLISHED_ENTITY_SET_MISMATCH')
    for ident,node in d.items():
        if content(a[ident])!=content(node):raise ValueError('PUBLISHED_CONTENT_MISMATCH:'+ident)
    if {e['id']:e for e in actual['edges']}!={e['id']:e for e in desired['edges']}:raise ValueError('PUBLISHED_RELATIONS_MISMATCH')
    if {c['id']:c for c in actual['rootCauses']}!={c['id']:c for c in desired['rootCauses']}:
        raise ValueError('PUBLISHED_ROOT_CAUSES_MISMATCH')
    if {group['id']:group for group in actual.get('decisionGroups',[])}!={group['id']:group for group in desired.get('decisionGroups',[])}:
        raise ValueError('PUBLISHED_GROUPS_MISMATCH')
    for w in desired['workGraphs']:
        if w not in actual['workGraphs']:raise ValueError('PUBLISHED_SCOPE_MISMATCH:'+w['id'])
    if any(e['type']!='created' for e in actual['events']):raise ValueError('DEFINITION_CONTAINS_EXECUTION')
    if any(n.get('selectionState')=='selected' or n.get('result',{}).get('state') in ('confirmed','completed') for n in a.values()):raise ValueError('FALSE_DEFINITION_EXECUTION')
    return {'entities':len(a),'edges':len(actual['edges']),'sourceSHA256':json.loads(next(n for n in actual['objects'] if 'rdg:lens-source-map' in n.get('tags',[]))['value'])['source']['sha256']}

def api_features(client):
    cached=getattr(client,'_rdg_api_features',None)
    if cached is not None:return cached
    try:cached=client.call({'method':'capabilities'}).get('features',{})
    except ValueError as exc:
        # Only an explicit old-server method rejection permits legacy reads.
        if not any(code in str(exc) for code in ('MESSAGE_FIELDS','UNKNOWN_METHOD')):raise
        cached={}
    client._rdg_api_features=cached
    return cached


def read_graph(client,pid):
    if not api_features(client).get('graphSnapshotRead',{}).get('available'):
        return client.call({'method':'read','packageId':pid,'detail':'full'})
    summary=client.call({'method':'read','packageId':pid,'detail':'summary','include':[]})
    snap=summary['snapshot']
    pin={'packageId':pid,'identitySpace':summary['package']['identitySpace'],
         'graphRevision':snap['graphRevision'],'sha256':snap['graphSHA256']}
    graph=client.call({'method':'source_snapshot','packageId':pid,'pin':pin,'detail':'graph'})['graph']
    if MODEL.digest(graph)!=pin['sha256']:raise ValueError('PINNED_GRAPH_READ_MISMATCH')
    root=graph.get('rootRequirementId')
    return {'package':summary['package'],'graph':graph,'path':summary['path'],
            'immutableDefinition':summary['immutableDefinition'],
            'references':{root:MODEL.reference(pid,graph,root)} if root else {}}


def inventory(client,graphs):
    catalog=client.call({'method':'catalog'})
    if catalog.get('complete') is False:raise ValueError('INCOMPLETE_CATALOG')
    rows={p['lensKey']:p for p in catalog['packages'] if p.get('role')=='lens'}
    existing={};counts={}
    for key,graph in graphs.items():
        if key in rows:
            row=read_graph(client,rows[key]['packageId'])
            if row['graph']['coreModel']!='rdg-decision-v1':raise ValueError('EXISTING_PROFILE_MISMATCH:'+key)
            commands=delta_commands(row['graph'],graph)
            existing[key]=row
            counts[key]={'mode':'update','commands':len(commands),'packageId':row['package']['packageId'],'immutable':row.get('immutableDefinition',False)}
        else:counts[key]={'mode':'create','commands':1}
    return catalog,existing,counts


def navigation_inventory(client,graphs,existing):
    """Freeze each existing advice definition before any owner mutation."""
    reviewed={}
    for key in graphs:
        row=existing.get(key)
        if row is None:
            reviewed[key]=None;continue
        ident=str(uuid.uuid5(uuid.UUID(row['package']['packageId']),'source-lens-navigation'))
        registry=client.call({'method':'recommendation_catalog','query':'lens-source-'+key,'limit':100})
        reviewed[key]=copy.deepcopy(next((d for d in registry['packages'] if d['id']==ident),None))
    return reviewed

def navigation_definitions(graphs,published):
    """Resolve authored prose cross-links to existing qualified lens addresses."""
    from urllib.parse import unquote
    maps={k:json.loads(next(n['value'] for n in g['objects'] if 'rdg:lens-source-map' in n.get('tags',[]))) for k,g in graphs.items()}
    paths={(ROOT/m['source']['path']).resolve():k for k,m in maps.items()}
    definitions={}
    plans=json.loads(PLAN_FILE.read_text())
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
            context='\n\n'.join(p.strip() for p in re.split(r'\n\s*\n',body) if re.search(r'\[[^\]]*\]\([^)]+\)',p))
            anchors=[i for i in row['entityIds'] if i.startswith('LS-TEXT-') or ns[i]['kind']=='action']
            for node_id in anchors:
                rules.append({'id':'link-'+MODEL.digest({'node':node_id})[:20],
                    'nodeKinds':[ns[node_id]['kind']],'scope':'identity','anchor':{'packageId':published[key]['packageId'],'identitySpace':published[key]['identitySpace'],'nodeId':node_id},
                    'state':'any','whenText':'Когда при работе с разделом «'+row['title']+'» нужны указанные в нём связанные методики или основания.',
                    'usageText':'Смысл ссылок в исходном разделе:\n'+context+'\nИспользовать относящееся содержание в указанной роли и нужном объёме; переход сам по себе не запускает методику.',
                    'lensRefs':refs})
        for advice in plans[key].get('recommendationAdvice',[]):
            target_key=advice['lensKey']
            if target_key not in published:continue
            bound=published[target_key]
            target={'packageId':bound['packageId'],'identitySpace':bound['identitySpace'],'lensKey':target_key}
            if advice.get('nodeId'):target['nodeId']=advice['nodeId']
            anchors=advice.get('anchorIds',[plans[key]['main']])
            for node_id in anchors:
                if node_id not in ns:raise ValueError('ADVICE_ANCHOR_MISSING:'+key+':'+node_id)
                rules.append({'id':'advice-'+advice['id']+'-'+MODEL.digest(node_id)[:12],
                    'nodeKinds':[ns[node_id]['kind']],'scope':'identity',
                    'anchor':{'packageId':published[key]['packageId'],'identitySpace':published[key]['identitySpace'],'nodeId':node_id},
                    'state':'any','whenText':advice['whenText'],'usageText':advice['usageText'],'lensRefs':[target]})
        if rules:
            definitions[key]={'id':str(uuid.uuid5(uuid.UUID(published[key]['packageId']),'source-lens-navigation')),
                'revision':1,'key':'lens-source-'+key,'title':'Связанные методики · '+key,'supplied':False,'authored':True,'rules':rules}
    return definitions

def reviewed_navigation(state,key):
    if key in state.get('reviewedNavigationBefore',{}):
        return state['reviewedNavigationBefore'][key]
    frozen=state.get('operations',{}).get('$inventory',{}).get('snapshot',{}).get('navigationBefore',{})
    if key in frozen and frozen[key] is not None:return frozen[key]
    created=state.get('operations',{}).get(key+'/navigation',{})
    if created.get('result',{}).get('published'):return created['request']['definition']
    if key in frozen:return None
    raise ValueError('NAVIGATION_REVIEW_BASE_MISSING:'+key)

def publish_navigation(client,graphs,state,write,save,progress,*,revise_navigation=False):
    navigation=state.setdefault('navigation',{})
    # A targeted owner update must retain advice pointing to other available lenses.
    catalog=client.call({'method':'catalog'})
    if catalog.get('complete') is False:raise ValueError('INCOMPLETE_CATALOG')
    bindings=dict(state['verified'])
    for package in catalog['packages']:
        if package.get('role')=='lens' and package.get('lensKey'):
            bindings.setdefault(package['lensKey'],{'packageId':package['packageId'],'identitySpace':package['identitySpace']})
    available={key:g for key,g in bundle()[1].items() if key in bindings}
    definitions={key:d for key,d in navigation_definitions(available,bindings).items() if key in graphs}
    for key,definition in definitions.items():
        # Reconcile original accepted attempts even if a later Registry version exists.
        for saved_key,saved in list(state.get('operations',{}).items()):
            if (saved_key==key+'/navigation' or saved_key.startswith(key+'/navigation-v')) and saved.get('applyAttempted'):
                write(saved_key,saved['request'])
        pid=state['verified'][key]['packageId']
        registry=client.call({'method':'recommendation_catalog','query':definition['key'],'limit':100})
        existing=next((d for d in registry['packages'] if d['id']==definition['id']),None)
        if existing:
            definition=copy.deepcopy(definition)
            same=all(existing.get(k)==v for k,v in definition.items() if k!='revision')
            definition['revision']=existing['revision'] if same else existing['revision']+1
            op_key=key+'/navigation-v'+str(definition['revision'])
            if not same:
                if not revise_navigation or existing.get('supplied') or not existing.get('authored'):
                    raise ValueError('NAVIGATION_DEFINITION_EXISTS_REVIEW_NEW_VERSION:'+key)
                reviewed=reviewed_navigation(state,key)
                if reviewed!=existing:raise ValueError('NAVIGATION_CHANGED_SINCE_REVIEW:'+key)
                state.setdefault('reviewedNavigationBefore',{})[key]=copy.deepcopy(reviewed);save()
                req=client.call({'method':'schema','op':'recommendation_edit'})['request']
                req.update(action='edit',packageId=definition['id'],definition=definition,expectedRegistryRevision=registry['registryRevision'],
                    note='Согласованное уточнение рекомендаций '+key+': конкретный контекст и роль для полноты текущей линзы; следующая версия того же определения.')
                req.pop('attachTo',None)
                write(op_key,req)
                verified=client.call({'method':'recommendation_catalog','query':definition['key'],'limit':100})
                if not any(d==definition for d in verified['packages']):raise ValueError('NAVIGATION_READBACK_MISMATCH:'+key)
            row=read_graph(client,pid)
            if definition['id'] not in row['graph']['recommendationPackageIds']:raise ValueError('NAVIGATION_ATTACHMENT_UNCONFIRMED:'+key)
        else:
            row=read_graph(client,pid)
            base=state['verified'][key]
            if (row['package']['revision'],row['graph']['revision'])!=(base['packageRevision'],base['graphRevision']):
                raise ValueError('LENS_CHANGED_SINCE_REVIEW:'+key)
            req=client.call({'method':'schema','op':'recommendation_edit'})['request']
            req.update(action='create',definition=definition,expectedRegistryRevision=registry['registryRevision'],
                attachTo={'packageId':pid,'expectedPackageRevision':row['package']['revision'],'expectedGraphRevision':row['graph']['revision']},
                note='Адресные переходы из сохранённых Markdown-разделов линзы '+key+'; существующие общие definitions и рабочие процессы сохраняются.')
            # Schema may expose edit-only optional selectors.
            req.pop('packageId',None)
            write(key+'/navigation',req)
            row=read_graph(client,pid)
            verified=client.call({'method':'recommendation_catalog','query':definition['key'],'limit':100})
            if not any(d==definition for d in verified['packages']):raise ValueError('NAVIGATION_READBACK_MISMATCH:'+key)
            if definition['id'] not in row['graph']['recommendationPackageIds']:raise ValueError('NAVIGATION_ATTACHMENT_UNCONFIRMED:'+key)
        verify_graph(row['graph'],graphs[key])
        state['verified'][key].update(packageRevision=row['package']['revision'],graphRevision=row['graph']['revision'])
        navigation[key]={'definitionId':definition['id'],'rules':len(definition['rules'])};save()
        progress('LENS_NAVIGATION_READY '+key+' '+str(len(definition['rules'])))
    return navigation


def run(client,journal_file,*,apply=False,manage_supplied=False,revise_navigation=False,keys=None,progress=print):
    plan,graphs,digest=bundle(keys)
    journal=JOURNAL.Journal(Path(journal_file),{'operations':{},'bundleSHA256':digest,'lensKeys':list(graphs),'verified':{}})
    state=journal.state
    if state['bundleSHA256']!=digest:raise ValueError('LENS_SOURCE_BUNDLE_CHANGED_USE_NEW_REVIEWED_JOURNAL')
    def save(key=None):journal.append(key)
    def write(key,request):
        op=state['operations'].get(key)
        if op is None:op={'request':request};state['operations'][key]=op;save(key)
        req=op['request'];registry_only=req.get('op')=='recommendation_edit' and not req.get('attachTo')
        pid=None if registry_only else req.get('targetPackageId') or req.get('attachTo',{}).get('packageId') or str(uuid.uuid5(uuid.UUID(req['transactionId']),'package'))
        def receipt_published(receipt):
            return receipt.get('found') and (receipt.get('published') or registry_only and receipt.get('accepted')
                and receipt.get('publicationCertificatePresent') and receipt.get('state')=='completed-certificate'
                and receipt.get('requestSHA256')==MODEL.digest(req))
        if op.get('applyAttempted'):
            receipt=client.call({'method':'receipt','packageId':pid,'transactionId':req['transactionId']})
            op['receipt']=receipt;save(key)
            if receipt_published(receipt):
                if not op.get('result',{}).get('published'):
                    if registry_only:op['result']={'published':True,'reconciledFromReceipt':True,'packages':[],'transactionId':req['transactionId']}
                    else:
                        r=receipt['receipt']
                        op['result']={'published':True,'reconciledFromReceipt':True,'packages':[{'packageId':pid,'revision':r['packageRevision'],'receipt':r}]}
                    save(key)
                return op['result']
            raise RuntimeError('UNCERTAIN_LENS_OPERATION_STOP:'+req['transactionId'])
        op['preview']=client.call({'method':'preflight','request':req});save(key)
        op['applyAttempted']=True;save(key)
        try:op['result']=client.call({'method':'apply','request':req,'expectedInputBinding':op['preview']['inputBinding']});save(key)
        except Exception as exc:
            if getattr(exc,'definite',False) is True and str(exc) in (
                    'RDG_REMOTE_PORTABLE_APP_PREVIEW_INPUTS_CHANGED','RDG_REMOTE_PREVIEW_INPUTS_CHANGED'):
                # The server rejected before acceptance. Keep the exact intent/CAS;
                # a deliberate resume may obtain a new preview for that same request.
                op.setdefault('rejections',[]).append({'code':str(exc),'inputBinding':op['preview']['inputBinding']})
                op['applyAttempted']=False;op.pop('uncertain',None);save(key)
                raise RuntimeError('LENS_PREVIEW_CHANGED_RETRY_SAME_REQUEST:'+req['transactionId']) from exc
            op['uncertain']=type(exc).__name__;save(key)
            raise RuntimeError('UNCERTAIN_LENS_OPERATION_SAVED:'+req['transactionId']) from exc
        if not op['result'].get('published'):raise RuntimeError('LENS_PUBLICATION_UNCONFIRMED:'+req['transactionId'])
        op['receipt']=client.call({'method':'receipt','packageId':pid,'transactionId':req['transactionId']});save(key)
        if not receipt_published(op['receipt']):raise RuntimeError('LENS_RECEIPT_UNCONFIRMED:'+req['transactionId'])
        return op['result']
    try:
        # Large immutable inventory belongs in one journal record, not repeated metadata.
        if state.get('inventory'):
            state['operations']['$inventory']={'snapshot':state.pop('inventory')};save('$inventory')
        if '$inventory' not in state['operations']:
            catalog,existing,counts=inventory(client,graphs)
            state['operations']['$inventory']={'snapshot':{'catalog':catalog,'existing':existing,'counts':counts,
                'navigationBefore':navigation_inventory(client,graphs,existing)}};save('$inventory')
        else:
            snapshot=state['operations']['$inventory']['snapshot']
            catalog=snapshot['catalog'];existing=snapshot['existing'];counts=snapshot['counts']
        progress('LENS_PLAN '+json.dumps({'bundleSHA256':digest,'lenses':counts},ensure_ascii=False))
        if not apply:return {'planned':True,'counts':counts,'bundleSHA256':digest}
        if not manage_supplied and any(r.get('immutableDefinition') for r in existing.values()):raise ValueError('EXPLICIT_SUPPLIED_MANAGEMENT_REQUIRED')
        # Mutations affect only the requested lens owners, never working processes.
        for key,desired in graphs.items():
            if key in state['verified']:
                row=read_graph(client,state['verified'][key]['packageId'])
                verify_graph(row['graph'],desired);continue
            old=existing.get(key)
            if old is None:
                req=client.call({'method':'schema','op':'create','coreModel':'rdg-decision-v1','role':'lens'})['request']
                req.update(path='lenses/fundamental/'+key,lensKey=key,title=desired['title'],scope=entities(desired)[desired['rootRequirementId']]['scope'],
                    rootReason='Поручение пользователя: перенести согласованные Markdown-линзы в RDG с сохранением исходников и возможностью работы в приложении.',graph=desired)
                result=write(key+'/create',req);pid=result['packages'][0]['packageId']
                changed=result['packages'][0]
                package_revision=changed['revision'];graph_revision=changed['receipt']['graphRevision']
            else:
                pid=old['package']['packageId']
                # Advance the reviewed base only through receipts from this journal.
                package_revision=old['package']['revision'];graph_revision=old['graph']['revision']
                if old.get('immutableDefinition'):
                    op=state['operations'].get(key+'/manage')
                    req=op['request'] if op else client.call({'method':'schema','op':'lens_manage','packageId':pid})['request']
                    if not op and (req['expectedPackageRevision'],req['expectedGraphRevision'])!=(package_revision,graph_revision):
                        raise ValueError('LENS_CHANGED_SINCE_REVIEW:'+key)
                    if not op:
                        req.update(confirmOwnerManagement=True,note='Поручение владельца о переносе 19 согласованных линз в приложение. Сохраняются packageId, identitySpace, старые anchors, версии и история; меняется содержание этой линзы.')
                    result=write(key+'/manage',req)
                    changed=next(p for p in result['packages'] if p['packageId']==pid)
                    package_revision=changed['revision'];graph_revision=changed['receipt']['graphRevision']
                # Build once against the reviewed initial graph. Each request is persisted before effect.
                commands=delta_commands(old['graph'],desired)
                legacy=any(key+'/'+name in state['operations'] for name,_,_ in commands)
                saved_batch=any(k.startswith(key+'/batch/') for k in state['operations'])
                if legacy and saved_batch:raise ValueError('LENS_JOURNAL_MIXED_AUTHORING_PROTOCOL:'+key)
                # An existing uncertain batch retains its protocol even if the server later changes.
                use_batch=saved_batch or not legacy and api_features(client).get('paperBatch',{}).get('available')
                if use_batch:
                    for offset in range(0,len(commands),100):
                        chunk=commands[offset:offset+100];op_key=key+'/batch/'+str(offset//100)
                        op=state['operations'].get(op_key)
                        req=op['request'] if op else client.call({'method':'schema','op':'batch','packageId':pid})['request']
                        if not op:
                            if (req['expectedPackageRevision'],req['expectedGraphRevision'])!=(package_revision,graph_revision):
                                raise ValueError('LENS_CHANGED_SINCE_REVIEW:'+key)
                            req.update(steps=[{'alias':'c'+str(offset+i),'op':'paper_edit','command':command,'data':data,
                                'note':'Структурный перенос '+key+': '+name} for i,(name,command,data) in enumerate(chunk)],
                                note='Согласованные структурные правки линзы '+key+'; исходники и история сохранены.')
                        result=write(op_key,req)
                        changed=next(p for p in result['packages'] if p['packageId']==pid)
                        package_revision=changed['revision'];graph_revision=changed['receipt']['graphRevision']
                        progress('LENS_PROGRESS '+key+' '+str(min(offset+100,len(commands)))+'/'+str(len(commands)))
                else:
                    for index,(name,command,data) in enumerate(commands):
                        op_key=key+'/'+name
                        if op_key in state['operations']:
                            req=state['operations'][op_key]['request']
                        else:
                            message={'method':'schema','op':'paper_edit','packageId':pid,'nodeId':data.get('nodeId',old['graph']['rootRequirementId']),'command':command}
                            if command=='add':message['entityKind']=data['entity']['kind']
                            req=client.call(message)['request']
                            if (req['expectedPackageRevision'],req['expectedGraphRevision'])!=(package_revision,graph_revision):raise ValueError('LENS_CHANGED_SINCE_REVIEW:'+key)
                            req.update(data=data,note='Структурный перенос '+key+': '+name+'; полный исходник и карта сохранены.')
                        result=write(op_key,req)
                        changed=next(p for p in result['packages'] if p['packageId']==pid)
                        package_revision=changed['revision'];graph_revision=changed['receipt']['graphRevision']
                        if (index+1)%10==0:progress('LENS_PROGRESS '+key+' '+str(index+1)+'/'+str(len(commands)))
            actual=read_graph(client,pid)
            if (actual['package']['revision'],actual['graph']['revision'])!=(package_revision,graph_revision):
                raise ValueError('LENS_CHANGED_SINCE_REVIEW:'+key)
            checked=verify_graph(actual['graph'],desired)
            if old:
                ref=old['references'][old['graph']['rootRequirementId']]
                pin={k:ref[k] for k in ('packageId','identitySpace','graphRevision','sha256')}
                historical=client.call({'method':'source_snapshot','packageId':pid,'pin':pin,**({'detail':'graph'} if api_features(client).get('graphSnapshotRead',{}).get('available') else {})})
                if historical['graph']!=old['graph']:raise ValueError('HISTORICAL_LENS_CHANGED:'+key)
                if actual['package']['identitySpace']!=old['package']['identitySpace']:raise ValueError('LENS_IDENTITY_CHANGED')
            state['verified'][key]={'packageId':pid,'identitySpace':actual['package']['identitySpace'],'packageRevision':actual['package']['revision'],
                                    'graphRevision':actual['graph']['revision'],**checked};save()
            progress('LENS_READY '+key+' '+pid)
        publish_navigation(client,graphs,state,write,lambda:save(),progress,revise_navigation=revise_navigation)
        progress('STRUCTURED_LENSES_READY '+json.dumps(state['verified'],ensure_ascii=False))
        return state
    finally:journal.checkpoint()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--context',required=True);parser.add_argument('--journal',required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--manage-existing-supplied',action='store_true')
    parser.add_argument('--revise-navigation',action='store_true',help='Publish the reviewed next revision of this transfer’s authored advice only')
    args=parser.parse_args()
    client=AGENT.portable_application(AGENT.config(args.context))
    run(client,args.journal,apply=args.apply,manage_supplied=args.manage_existing_supplied,revise_navigation=args.revise_navigation)
