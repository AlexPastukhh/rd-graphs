"""Decision analysis and process context organization inside the Graph owner.

Read projections are bounded to one semantic hop and reuse the policy resolver.
No store or independent invalidation evaluator is introduced here.
"""
import copy
from contextlib import contextmanager
from contextvars import ContextVar
import uuid


_read_cache = ContextVar('rdg_analysis_read_cache', default=None)


@contextmanager
def read_scope(g, *, fresh=False):
    # Reuse only within one synchronous read calculation. Writer evaluations
    # explicitly request a fresh scope: the mutable Graph may retain its
    # Python identity across different operations in a batch.
    current = _read_cache.get()
    if not fresh and current is not None and current[0] is g:
        yield current[1]
        return
    cache = {}
    token = _read_cache.set((g, cache))
    try:
        yield cache
    finally:
        _read_cache.reset(token)


def active_read_cache(g):
    """Read-only memo table for the currently scoped Graph identity, if any.

    Never create or keep a cache here: mutation between scopes must always
    see the new state, even if the writer reuses the same Graph dictionary.
    """
    current = _read_cache.get()
    return current[1] if current is not None and current[0] is g else None


def manual(g, ident):
    return set(next((n for n in g['nodes'] if n['id']==ident),{}).get('decisionContextIds',[])) | {
        e['from'] for e in g['edges'] if e['type']=='DEPENDS_ON' and e['to']==ident and e.get('dependencyPurpose')=='decisionContext'}


class BaseContext:
    """Resolver snapshot excludes recursively inherited context, thread-safely."""
    def __init__(self,K):self.K=K
    def __getattr__(self,name):return getattr(self.K,name)
    def decision_context(self,g,ident):return context(g,ident,self.K,derived=False)
    def _context_sources(self,g,ident):return self.K._context_sources(g,ident,include_findings=False)
    def _native_direct_scope(self,g,ident):return self.K._native_direct_scope(g,ident,include_findings=False)
    def _effective_observable(self,g,ident,rule,cosmetic):
        return self.K._effective_observable(g,ident,rule,cosmetic,include_findings=False)


def manual_order(g,ident):
    d=next((n for n in g['nodes'] if n['id']==ident),{})
    return list(dict.fromkeys([*d.get('decisionContextIds',[]),*(e['from'] for e in g['edges'] if e['type']=='DEPENDS_ON' and e['to']==ident and e.get('dependencyPurpose')=='decisionContext')]))


def context(g, ident, K, *, derived=True, applications=None):
    with read_scope(g) as cache:
        return _context(g, ident, K, derived=derived, applications=applications, cache=cache)


def _context(g, ident, K, *, derived, applications, cache):
    ns=K.entities(g);d=ns.get(ident)
    if not d or d['kind']!='decision':return []
    rows={i:{'sourceId':i,'present':True,'manual':True,'comment':d.get('contextNotes',{}).get(i,''),
             'provenance':[],'edgeIds':[e['id'] for e in g['edges'] if e['type']=='DEPENDS_ON' and e['from']==i and e['to']==ident and e.get('dependencyPurpose')=='decisionContext']}
          for i in manual_order(g,ident) if i in ns}
    findings={f['id']:f for f in g['objects'] if f['kind']=='finding' and f.get('subjectId')==ident}
    if derived and findings:
        if applications is None:
            if 'baseApplications' not in cache:
                cache['baseApplications'] = K.POLICIES.describe_applications(g,BaseContext(K))
            applications = cache['baseApplications']
        apps=applications
        for app in apps:
            f=findings.get(app['targetId'])
            if not f:continue
            for rule in app['rules']:
                if not rule.get('enabled',True):continue
                ids=set(rule.get('actorIds',[]))|set(rule.get('memberIds',[]))
                recorded=app['binding'].get('observedSources',{}).get(rule['id'],[]) if not app['enabled'] else []
                ids.update(n['id'] for n in recorded)
                for i in ids-{ident,f['id']}:
                    item=ns.get(i) or app['participants'].get(i) or next((n for n in recorded if n['id']==i),None)
                    if not item:continue
                    row=rows.setdefault(i,{'sourceId':i,'present':i in ns,'manual':False,'comment':d.get('contextNotes',{}).get(i,''),'provenance':[],'edgeIds':[]})
                    row['provenance'].append({'findingId':f['id'],'findingTitle':f['title'],
                        'applicationId':app['id'],'ruleId':rule['id'],'role':rule.get('role','source'),
                        'enabled':app['enabled'] and app['applicable'],'status':app['status'],
                        'watch':rule.get('displayWatch',rule['watch']),'source':{k:item.get(k) for k in ('id','kind','title')}})
    return [rows[i] for i in dict.fromkeys([*manual_order(g,ident),*sorted(rows)]) if i in rows]


def record_disabled_sources(before,g,K):
    old={b['id']:b for b in before.get('dependencyBindings',[])}
    changed=[b for b in g.get('dependencyBindings',[]) if b.get('status')=='disabled' and old.get(b['id'],{}).get('enabled')]
    if not changed:return
    apps={r['id']:r for r in K.POLICIES.describe_applications(before,BaseContext(K))};ns=K.entities(before)
    for b in changed:
        app=apps.get(b['id'])
        if app:b['observedSources']={r['id']:[{k:ns[i][k] for k in ('id','kind','title')} for i in sorted(set(r.get('actorIds',[]))|set(r.get('memberIds',[]))) if i in ns] for r in app['rules'] if r.get('enabled',True)}


def validate_groups(g,K):
    groups=g.get('contextGroups',[])
    K.require(isinstance(groups,list),'CONTEXT_GROUPS')
    ids=set()
    for r in groups:
        K.require(isinstance(r,dict) and set(r)=={'id','title','parentId'} and K.text(r['id']) and K.text(r['title']) and (r['parentId'] is None or K.text(r['parentId'])) and r['id'] not in ids,'CONTEXT_GROUP')
        K.require(r['id'] not in K.entities(g) and not any(e['id']==r['id'] for e in g['edges']) and not any(d['id']==r['id'] for d in g['decisionGroups']),'CONTEXT_GROUP_ID_CONFLICT')
        ids.add(r['id'])
    parents={r['id']:r['parentId'] for r in groups}
    for ident in ids:
        seen=set();cur=ident
        while cur is not None:
            K.require(cur in ids and cur not in seen,'CONTEXT_GROUP_CYCLE_OR_PARENT');seen.add(cur);cur=parents[cur]
    for n in K.entities(g).values():
        if 'contextGroupId' in n:K.require(n['kind']=='context' and n['contextGroupId'] in ids,'CONTEXT_GROUP_REFERENCE')


def _valid_note_sources(g, d, K):
    """Check explicit, present context first; derive Finding sources only if needed.

    A manual source is always present in context() when it is still an entity.
    All other note references must follow the existing policy-derived resolver.
    No memo survives a mutation, validation, or Application request.
    """
    notes = d.get('contextNotes', {})
    if not notes:
        return set()
    manual_present = manual(g, d['id']) & K.entities(g).keys()
    if set(notes) <= manual_present:
        return manual_present
    return {r['sourceId'] for r in context(g, d['id'], K) if r['present']}


def validate_notes(g,K):
    for d in g['nodes']:
        if d['kind']!='decision' or 'contextNotes' not in d:continue
        notes=d['contextNotes'];K.require(isinstance(notes,dict) and all(K.text(i) and K.text(t) for i,t in notes.items()),'CONTEXT_NOTES')
        K.require(set(notes)<=_valid_note_sources(g,d,K),'CONTEXT_NOTE_REFERENCE')
    for n in K.entities(g).values():
        for p in n.get('analysisSources',[]):
            K.require(isinstance(p,dict) and set(p)=={'sourceId','revision','excerpt'} and K.text(p['sourceId']) and type(p['revision']) is int and p['revision']>=1 and isinstance(p['excerpt'],str),'ANALYSIS_SOURCE')
            K.require(p['sourceId'] not in K.entities(g) or K.entities(g)[p['sourceId']]['kind'] in ('canon','info'),'ANALYSIS_SOURCE_REFERENCE')


def reconcile_notes(before,g,event,K):
    old=K.entities(before);changed=set()
    for d in g['nodes']:
        if d['kind']!='decision':continue
        notes=d.get('contextNotes',{})
        valid=_valid_note_sources(g,d,K)
        if set(notes)-valid:
            previous=old.get(d['id'],{}).get('contextNotes',{})
            K.require(all(i in previous and previous[i]==notes[i] for i in set(notes)-valid),'CONTEXT_NOTE_REFERENCE')
            changed.add(d['id'])
            K.guard(d,event,'edit');d['contextNotes']={i:v for i,v in notes.items() if i in valid};d['revision']+=1
        new=manual(g,d['id'])-manual(before,d['id'])
        new|={i for i in manual(g,d['id']) if K.text(old.get(d['id'],{}).get('contextNotes',{}).get(i))}
        # New manual memberships require user reasoning, regardless of writer path.
        K.require(all(K.text(d.get('contextNotes',{}).get(i)) for i in new),'CONTEXT_COMMENT_REQUIRED')
    for n in K.entities(g).values():
        for p in n.get('analysisSources',[]):
            if p not in old.get(n['id'],{}).get('analysisSources',[]):
                source=K.entities(g).get(p.get('sourceId'));K.require(source is not None and source['kind'] in ('canon','info'),'ANALYSIS_SOURCE_REFERENCE');K.guard(source,event,'link')
    return changed


def mutate(g,cmd,data,event,K):
    ns=K.entities(g)
    if cmd=='context_record':
        K.require({'nodeId'}<=set(data)<={'nodeId','contextGroupId'},'CONTEXT_RECORD_FIELDS')
        n=ns.get(data['nodeId']);K.require(n is not None and n['kind']=='evidence','LEGACY_EVIDENCE_REQUIRED');K.guard(n,event,'edit')
        group=data.get('contextGroupId')
        if 'contextGroupId' not in data:
            groups=g.setdefault('contextGroups',[])
            group='CG-'+uuid.uuid5(uuid.NAMESPACE_URL,g['identitySpace']+':records').hex
            if not any(r['id']==group for r in groups):
                for root in g['rootCauses']:K.guard(ns[root['requirementId']],event,'edit')
                groups.append({'id':group,'title':'Подтверждения','parentId':None})
        elif group is not None:K.require(any(r['id']==group for r in g.get('contextGroups',[])),'CONTEXT_GROUP_UNKNOWN')
        n['kind']='context';n['value']=n.pop('claim');n['revision']+=1
        if group is not None:n['contextGroupId']=group
        return {n['id']}
    if cmd=='context_group':
        K.require(set(data)<= {'action','id','title','parentId'} and data.get('action') in ('save','remove'),'CONTEXT_GROUP_COMMAND')
        for root in g['rootCauses']:K.guard(ns[root['requirementId']],event,'edit')
        groups=g.setdefault('contextGroups',[]);old=next((r for r in groups if r['id']==data.get('id')),None)
        if data['action']=='remove':
            K.require(old is not None,'CONTEXT_GROUP_UNKNOWN');parent=old['parentId']
            for n in g['objects']:
                if n.get('contextGroupId')==old['id']:
                    K.guard(n,event,'edit')
                    if parent is None:n.pop('contextGroupId')
                    else:n['contextGroupId']=parent
                    n['revision']+=1
            for r in groups:
                if r['parentId']==old['id']:r['parentId']=parent
            groups.remove(old)
        else:
            row={'id':data.get('id'),'title':data.get('title'),'parentId':data.get('parentId')}
            K.require(row!=old,'NO_CHANGE')
            if old:groups.remove(old)
            groups.append(row)
        validate_groups(g,K);return set()
    if cmd=='decision_context':
        K.require(set(data)<= {'nodeId','sourceId','action','comment','rule','analysisSources'} and data.get('action') in ('save','remove','note'),'DECISION_CONTEXT_COMMAND')
        d=ns.get(data.get('nodeId'));i=data.get('sourceId');x=ns.get(i)
        K.require(d is not None and d['kind']=='decision' and x is not None and i!=d['id'] and x['kind'] in K.ENTITY_KINDS,'DECISION_CONTEXT_REFS')
        K.guard(d,event,'edit');action=data['action']
        if action=='remove':
            K.require(i in manual(g,d['id']),'DERIVED_CONTEXT_READONLY')
            K.guard(x,event,'unlink');K.guard(d,event,'unlink')
            d['decisionContextIds']=[r for r in d.get('decisionContextIds',[]) if r!=i]
            g['edges']=[e for e in g['edges'] if not(e['type']=='DEPENDS_ON' and e['to']==d['id'] and e['from']==i and e.get('dependencyPurpose')=='decisionContext')]
        else:
            comment=data.get('comment','')
            if action=='save':
                K.require(K.text(comment),'CONTEXT_COMMENT_REQUIRED');K.guard(x,event,'link');K.guard(d,event,'link')
                d['decisionContextIds']=[r for r in d.get('decisionContextIds',[]) if r!=i]
                edge=next((e for e in g['edges'] if e['type']=='DEPENDS_ON' and e['to']==d['id'] and e['from']==i),None)
                if edge:K.guard(d,event,'dependency_add')
                r={'id':edge['id'] if edge else 'CTX-'+uuid.uuid5(uuid.NAMESPACE_URL,d['id']+':'+i).hex,'type':'DEPENDS_ON','from':i,'to':d['id'],'dependencyPurpose':'decisionContext',
                   'dependencyRule':copy.deepcopy(data.get('rule',{'preset':'L1','watch':['definition']}))}
                if edge:g['edges'].remove(edge)
                K._validate_new_relation(g,r);g['edges'].append(r)
            else:K.require(any(r['sourceId']==i for r in context(g,d['id'],K)),'CONTEXT_NOTE_REFERENCE')
            K.require(isinstance(comment,str),'CONTEXT_NOTES')
            if comment.strip():d.setdefault('contextNotes',{})[i]=comment
            else:
                K.require(i not in manual(g,d['id']),'CONTEXT_COMMENT_REQUIRED');d.get('contextNotes',{}).pop(i,None)
        if 'analysisSources' in data:d['analysisSources']=copy.deepcopy(data['analysisSources'])
        d['revision']+=1;return {d['id'],i}
    if cmd=='finding_transfer':
        K.require({'nodeId','subjectId'}<=set(data)<={'nodeId','subjectId','detachLegacy'} and type(data.get('detachLegacy',False)) is bool,'FINDING_TRANSFER_FIELDS')
        f=ns.get(data['nodeId']);d=ns.get(data['subjectId'])
        K.require(f is not None and f['kind']=='finding' and d is not None and d['kind']=='decision','FINDING_SUBJECT_REQUIRED')
        legacy=[e for e in g['edges'] if e.get('findingId')==f['id']]
        K.require(not legacy or data.get('detachLegacy'),'LEGACY_FINDING_COMPOSITION_REQUIRES_UNLINK')
        detached=set()
        if legacy:
            for e in legacy:
                for i in (e['from'],e['to']):K.guard(ns[i],event,'unlink');detached.add(i)
                g['edges'].remove(e)
            for group in list(g['decisionGroups']):
                if ns[group['parentId']]['kind']!='decision':continue
                group['members']=[m for m in group['members'] if any(e['type']=='FINDING_PROPOSAL' and e['from']==group['parentId'] and e['to']==m['decisionId'] for e in g['edges'])]
                if not group['members']:g['decisionGroups'].remove(group)
            for i in detached:
                n=ns[i]
                if n.get('findingOrigin',{}).get('findingId')==f['id']:K.guard(n,event,'edit');n['findingOrigin']['recordedOnly']=True;n['revision']+=1

        K.guard(f,event,'edit');K.guard(d,event,'link');old=ns.get(f['subjectId'])
        if old:K.guard(old,event,'unlink')
        f['subjectId']=d['id'];f['subjectSnapshot']={k:d[k] for k in ('id','kind','title','revision')};f['subjectSnapshot']['definition']=K._native_definition(g,d['id']);f['revision']+=1
        return {f['id'],d['id']}|detached
    if cmd=='requirement_decision':
        K.require(set(data)<= {'nodeId','parentId','decisionId','title','description','replaceEdgeId','workGraphId'},'REQUIREMENT_DECISION_FIELDS')
        r=ns.get(data.get('nodeId'));parent=ns.get(data.get('parentId'));ident=data.get('decisionId')
        K.require(r is not None and r['kind']=='requirement' and parent is not None and parent['kind']=='requirement' and parent['id']!=r['id'],'REQUIREMENT_DECISION_PARENT')
        existing=ns.get(ident)
        K.require(K.text(ident) and (existing is None or existing['kind']=='decision') and K.text(data.get('title')),'NEW_ENTITY')
        if existing:K.guard(existing,event,'link')
        K.guard(r,event,'link');K.guard(parent,event,'link')
        remove=data.get('replaceEdgeId')
        if remove:
            edge=next((e for e in g['edges'] if e['id']==remove),None)
            K.require(edge is not None and edge['type']=='DERIVES' and edge['to']==r['id'],'REQUIREMENT_DECISION_EDGE');K.guard(ns[edge['from']],event,'unlink');K.guard(r,event,'unlink');g['edges'].remove(edge)
        # Parent must not be a descendant of R, even along a paper branch.
        reached={r['id']};structural=g['edges']+K.decision_memberships(g)
        while True:
            more={e['to'] for e in structural if e['type'] in K.STRUCTURAL_KINDS and e['from'] in reached}
            if more<=reached:break
            reached|=more
        K.require(parent['id'] not in reached and ident not in reached,'REQUIREMENT_DECISION_CYCLE')
        if existing is None:g['nodes'].append({'id':ident,'kind':'decision','title':data['title'],'description':data.get('description',''),'revision':1,'selectionState':'discovered','result':{'state':'open','truth':'unknown'}})
        for kind,a,b in (('DRIVES',parent['id'],ident),('INTRODUCES',ident,r['id'])):
            if any(e['type']==kind and e['from']==a and e['to']==b for e in g['edges']):continue
            if kind=='DRIVES' and any(group['parentId']==a and any(m['decisionId']==b for m in group['members']) for group in g['decisionGroups']):continue
            edge={'id':'RD-'+uuid.uuid5(uuid.NAMESPACE_URL,ident+':'+kind+':'+a+':'+b).hex,'type':kind,'from':a,'to':b};K._validate_new_relation(g,edge);g['edges'].append(edge)
        if data.get('workGraphId'):
            area=next((w for w in g['workGraphs'] if w['id']==data['workGraphId']),None);K.require(area is not None,'WORK_GRAPH_UNKNOWN');area['memberIds']=sorted(set(area['memberIds'])|{ident,r['id'],parent['id']})
        for i in {ident,r['id'],parent['id']}:
            if i in ns:ns[i]['revision']+=1
        return {ident,r['id'],parent['id']}
    raise ValueError('ANALYSIS_COMMAND')
