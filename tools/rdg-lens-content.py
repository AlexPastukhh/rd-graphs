#!/usr/bin/env python3
"""Compile reviewed lens prose and an authored semantic plan into Decision graphs.

The plan chooses real work; prose headings become Canon/Info, never automatic R.
Existing entity identities remain stable. No live store is edited by this tool.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'tools/rdg-agent-lenses'
PLAN=ROOT/'tools/rdg-lens-content-plan.json'
META_PREFIXES=('LS-TEXT-','LS-SOURCE-','LS-MAP-','LS-WORKFLOW-','LS-STEP-','LS-EDGE-','LS-METHOD-')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return json.dumps(value,ensure_ascii=False,indent=2)+'\n'
def slug(title):
    return re.sub(r'[^\w\s-]','',title.lower(),flags=re.U).replace(' ','-')
def source_sections(path):
    raw=path.read_bytes();text=raw.decode('utf8')
    lines=text.splitlines(keepends=True)
    starts=[(i,line[3:].strip()) for i,line in enumerate(lines) if line.startswith('## ')]
    sections=[{'title':'Введение','anchor':'','startLine':1,'endLine':starts[0][0] if starts else len(lines),'text':''.join(lines[:starts[0][0] if starts else len(lines)])}]
    for n,(i,title) in enumerate(starts):
        end=starts[n+1][0] if n+1<len(starts) else len(lines)
        sections.append({'title':title,'anchor':slug(title),'startLine':i+1,'endLine':end,'text':''.join(lines[i:end])})
    commit=subprocess.check_output(['git','log','-1','--format=%H','--',str(path.relative_to(ROOT))],cwd=ROOT,text=True).strip()
    committed=subprocess.check_output(['git','show',commit+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT) if commit else None
    source={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(raw),'gitCommit':commit if commit and committed==raw else None}
    if source['gitCommit'] is None:source['baseGitCommit']=commit or None
    return text,source,sections
def select(sections,prefix):
    matches=[s for s in sections if s['title'].startswith(prefix)]
    if len(matches)!=1:raise ValueError('SOURCE_SECTION_AMBIGUOUS:'+prefix)
    return matches[0]
def source_id(key,section):
    return 'LS-TEXT-'+key.upper()+'-'+sha(section['anchor'].encode())[:10]
def relation(kind,a,b):
    return {'id':'LS-EDGE-'+sha((kind+'|'+a+'|'+b).encode())[:20],'type':kind,'from':a,'to':b}
def compile_one(key,plan,existing=None):
    path=ROOT/('docs/lenses/'+plan['group']+'/'+key+'.md')
    text,source,sections=source_sections(path)
    purpose_section=select(sections,'Требуемый результат')
    root_match=re.search(r'\*\*(R-[A-Z0-9-]+):\*\*\s*«([^»]+)»',purpose_section['text'])
    if not root_match:raise ValueError('SOURCE_REQUIREMENT_MISSING:'+key)
    root_id,purpose=root_match.groups()
    title=text.splitlines()[0].lstrip('# ').strip()
    scope_line=next((l for l in purpose_section['text'].splitlines() if l.startswith('Область')),'Область: '+title)
    scope=scope_line.split('Родительские основания:')[0].strip()
    if existing:
        g=copy.deepcopy(existing)
        keep=set(plan['retainedIds'])
        g['nodes']=[n for n in g['nodes'] if n['id'] in keep]
        g['objects']=[n for n in g['objects'] if n['id'] in keep]
        g['edges']=[e for e in g['edges'] if not e['id'].startswith('LS-EDGE-') and e['from'] in keep and e['to'] in keep]
        g['decisionGroups']=copy.deepcopy(plan.get('decisionGroups',g.get('decisionGroups',[])))
        g['externalActions']=[]
        if g['rootRequirementId']!=root_id:raise ValueError('ROOT_ID_CHANGED:'+key)
    else:
        g={'schemaVersion':1,'actionModel':'candidate-v6','coreModel':'rdg-decision-v1',
           'id':'rdg-fundamental-'+key+'-decision','title':title,
           'identitySpace':str(uuid.uuid5(uuid.NAMESPACE_URL,'rdg:fundamental:'+key)),
           'revision':1,'rootRequirementId':root_id,
           'rootCauses':[{'id':'RC-'+key.upper(),'requirementId':root_id,'reason':'Переиспользуемое определение методики; не факт предметного исполнения.','enabled':True}],
           'nodes':[{'id':root_id,'kind':'requirement','title':purpose,'scope':scope,'description':'','revision':1,'result':{'state':'open','truth':'unknown'}}],
           'objects':[],'externalActions':[],'edges':[],'decisionGroups':[],
           'workGraphs':[],'events':[],'recommendationPackageIds':[]}
    g.update(title=title,revision=plan['sourceRevision'],events=[],recommendationPackageIds=[])
    ns={n['id']:n for n in g['nodes']+g['objects']}
    assignments={root_id:purpose_section}
    if plan['main'] in ns:assignments[plan['main']]=sections[0]
    catalog_id='I-LENS-'+key.upper()
    if catalog_id in ns:assignments[catalog_id]=select(sections,'Когда оценить')
    for prefix,ids in plan.get('assign',[]):
        section=select(sections,prefix)
        for ident in ids:
            if ident not in ns:raise ValueError('UNKNOWN_RETAINED_ID:'+key+':'+ident)
            assignments[ident]=section
    main=plan['main']
    for ident,n in list(ns.items()):
        if ident not in assignments:raise ValueError('RETAINED_SECTION_UNASSIGNED:'+key+':'+ident)
        section=assignments[ident]
        n['revision']=1
        n['description']='Источник: '+source['path']+('#'+section['anchor'] if section['anchor'] else '')+'. Содержание раскрыто в '+source_id(key,section)+'; точная редакция — LS-MAP-'+key.upper()+'.'
        if n['kind']=='requirement':
            n.update(scope=scope+' Применяется к своей части выбранного метода и условиям текущей задачи.',result={'state':'open','truth':'unknown'})
        if n['kind']=='decision':n.update(selectionState='discovered',result={'state':'open','truth':'unknown'})
        if n['kind']=='action':n.update(result={'state':'open','truth':'unknown'},actionType='task',lowLevel=False,targetIds=[],groupIds=[])
        if n['kind']=='canon':
            n.update(guidance=section['text'],canons='',knownErrors=[])
        if n['kind'] in ('info','context'):n['value']=section['text']
        for field in ('review','locks','decisionContextIds','findingOrigin'):n.pop(field,None)
    ns[root_id].update(title=purpose,description=purpose_section['text'],scope=scope)
    for ident,changes in plan.get('overrides',{}).items():ns[ident].update(changes)
    if main not in ns:
        n={'id':main,'kind':'decision','title':plan.get('methodTitle','Использовать метод: '+title.split('—')[-1].strip()),
           'description':'Выбрать уместный объём методики для текущей задачи; чтение и выбор не означают исполнение.',
           'revision':1,'selectionState':'discovered','result':{'state':'open','truth':'unknown'}}
        g['nodes'].append(n);ns[main]=n;g['edges'].append(relation('DRIVES',root_id,main))
    else:
        ns[main]['description']='Способ работы в оговорённом scope. Применимые принципы, условия, действия и достаточность раскрыты в связанных Canon. Открытие определения не исполняет метод.'
    assignments[main]=sections[0]
    # One canonical section carries the complete explanation; R/D/Actions reference it.
    section_nodes={}
    for section in sections:
        ident=source_id(key,section);section_nodes[section['anchor']]=ident
        is_reference=section['title'] in ('Введение','Нормативные источники','Источники и границы')
        n={'id':ident,'kind':'info' if is_reference else 'canon','title':section['title'],
           'description':source['path']+('#'+section['anchor'] if section['anchor'] else '')+'; точная редакция — LS-MAP-'+key.upper()+'.',
           'revision':1}
        n['value' if is_reference else 'guidance']=section['text'].strip() or title
        g['objects'].append(n);ns[ident]=n;assignments[ident]=section
        g['edges'].append(relation('INFO_FOR' if is_reference else 'CANON_FOR',ident,main))
    # A retained method must expose its assigned theory in an addressed read,
    # not only mention a source ID in description. Reuse matching legacy bindings.
    for ident,section in list(assignments.items()):
        if ns[ident]['kind'] not in ('decision','action'):continue
        sid=section_nodes[section['anchor']]
        if ns[sid]['kind']!='canon':continue
        bound=[ns[e['from']] for e in g['edges'] if e['type']=='CANON_FOR' and e['to']==ident]
        if not any(n.get('guidance','').strip()==section['text'].strip() for n in bound):
            g['edges'].append(relation('CANON_FOR',sid,ident))
    actions=[]
    for suffix,action_title,prefix in plan['steps']:
        section=select(sections,prefix);ident='LS-STEP-'+key.upper()+'-'+suffix
        n={'id':ident,'kind':'action','title':action_title,'description':'Выполнить содержательно для текущего поручения и применимых условий. Методика: '+source_id(key,section)+'; '+source['path']+'#'+section['anchor'],
           'revision':1,'actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[],
           'result':{'state':'open','truth':'unknown'}}
        g['nodes'].append(n);ns[ident]=n;assignments[ident]=section;actions.append(ident)
        g['edges'].append(relation('REQUIRES_ACTION',main,ident))
        g['edges'].append(relation('CANON_FOR',section_nodes[section['anchor']],ident))
    for suffix,method_title,prefix in plan.get('extraMethods',[]):
        section=select(sections,prefix);ident='LS-METHOD-'+key.upper()+'-'+suffix
        n={'id':ident,'kind':'decision','title':method_title,'description':'Применять при соответствующем поручении; критерии результата различаются по виду работы. Подробная методика: '+source_id(key,section),
           'revision':1,'selectionState':'discovered','result':{'state':'open','truth':'unknown'}}
        g['nodes'].append(n);ns[ident]=n;assignments[ident]=section
        g['edges'].append(relation('DRIVES',root_id,ident))
        aid='LS-STEP-'+key.upper()+'-'+suffix
        action={'id':aid,'kind':'action','title':method_title,'description':'Выполнить порученную работу по '+source_id(key,section)+' с сохранением применимых условий и критериев.',
                'revision':1,'actionType':'task','lowLevel':False,'targetIds':[],'groupIds':[],
                'result':{'state':'open','truth':'unknown'}}
        g['nodes'].append(action);ns[aid]=action;assignments[aid]=section
        g['edges'].append(relation('REQUIRES_ACTION',ident,aid))
        for target in (ident,aid):g['edges'].append(relation('CANON_FOR',section_nodes[section['anchor']],target))
    trigger=select(sections,'Когда оценить')
    card_id='I-LENS-'+key.upper()
    if card_id not in ns:
        n={'id':card_id,'kind':'info','title':'Назначение и условия применения','description':'','revision':1,'value':''}
        g['objects'].append(n);ns[card_id]=n
        g['edges'].append(relation('INFO_FOR',card_id,root_id))
    ns[card_id].update(description=purpose,value=trigger['text'].strip(),tags=['rdg:lens-catalog'])
    assignments[card_id]=trigger
    workflow_id='LS-WORKFLOW-'+key.upper()
    workflow={'id':workflow_id,'kind':'info','title':'Место методики в работе','description':'Контекст выбора; не автоматическое исполнение и не обязательный вызов соседней линзы.',
              'revision':1,'tags':['rdg:lens-workflow'],'value':plan.get('workflow','Выбирать по текущей задаче и общей стратегии work. Условия применения: '+trigger['text'].strip())}
    g['objects'].append(workflow);ns[workflow_id]=workflow;assignments[workflow_id]=trigger
    g['edges'].append(relation('INFO_FOR',workflow_id,root_id))
    full_id='LS-SOURCE-'+key.upper()
    full={'id':full_id,'kind':'info','title':'Полный Markdown-источник · '+key,'description':source['path']+' · '+(source['gitCommit'] or 'незафиксированная редакция; base '+(source.get('baseGitCommit') or 'неизвестен'))+' · SHA256 '+source['sha256'],
          'revision':1,'tags':['rdg:lens-source'],'value':text}
    g['objects'].append(full);ns[full_id]=full;assignments[full_id]=sections[0]
    g['edges'].append(relation('INFO_FOR',full_id,root_id))
    additional=[]
    if key=='model':
        shared_text,shared_source,shared_sections=source_sections(ROOT/'docs/lenses/requirements.md')
        additional.append({**shared_source,'fullTextInfoId':'LS-SOURCE-SHARED-REQUIREMENTS','rows':[{'anchor':s['anchor'],'startLine':s['startLine'],'endLine':s['endLine'],'sectionSHA256':sha(s['text'].encode()),'entityIds':['LS-SOURCE-SHARED-REQUIREMENTS']+([r for r in ('R-CONTINUITY','R-DECOMPOSITION') if s['title'].startswith(r)]),'meaning':'Полный исходник сохранён в Info; только два исходных родительских R представлены как требования model.'} for s in shared_sections]})
        common={'id':'LS-SOURCE-SHARED-REQUIREMENTS','kind':'info','title':'Общие требования и критерии качества линз','description':shared_source['path']+' · SHA256 '+shared_source['sha256'],'revision':1,'tags':['rdg:lens-shared-requirements'],'value':shared_text}
        g['objects'].append(common);ns[common['id']]=common
        g['edges'].append(relation('INFO_FOR',common['id'],root_id))
        for ident,prefix in [('R-CONTINUITY','R-CONTINUITY'),('R-DECOMPOSITION','R-DECOMPOSITION')]:
            section=select(shared_sections,prefix)
            requirement=re.search(r'\*\*Требование:\*\*\s*([^\n]+)',section['text']).group(1)
            n={'id':ident,'kind':'requirement','title':requirement,'description':section['text'],'revision':1,'scope':'Общие исходные цели применения RDG; выполнение не объявляется определением линзы.','result':{'state':'open','truth':'unknown'}}
            g['nodes'].append(n);ns[ident]=n
            g['rootCauses'].append({'id':'LS-ROOT-'+ident,'requirementId':ident,'reason':'Сохранённое исходное родительское основание model.','enabled':True})
            g['edges'].append(relation('DERIVES',ident,root_id))
    # Group membership replaces the same DRIVES participation atomically on publication.
    g['decisionGroups']=copy.deepcopy(plan.get('decisionGroups',g.get('decisionGroups',[])))
    membership_pairs={(group['parentId'],m['decisionId']) for group in g['decisionGroups'] for m in group['members']}
    g['edges']=[e for e in g['edges'] if not (e['type']=='DRIVES' and (e['from'],e['to']) in membership_pairs)]
    # Keep root causes unique across deterministic recompilation.
    g['rootCauses']=list({c['id']:c for c in g['rootCauses']}.values())
    map_id='LS-MAP-'+key.upper()
    rows=[]
    for section in sections:
        ids=[i for i,s in assignments.items() if s is section]
        edge_ids=[e['id'] for e in g['edges'] if e['from'] in ids or e['to'] in ids]
        rows.append({'anchor':section['anchor'],'title':section['title'],'startLine':section['startLine'],'endLine':section['endLine'],
                     'sectionSHA256':sha(section['text'].encode()),'nestedAnchors':[slug(m.group(1)) for m in re.finditer(r'^#{3,6} (.+)$',section['text'],re.M)],'entityIds':ids,'edgeIds':edge_ids,
                     'decisionGroupIds':[gr['id'] for gr in g['decisionGroups'] if gr['parentId'] in ids or any(m['decisionId'] in ids for m in gr['members'])],
                     'meaning':'Полный смысл сохранён в Canon/Info; действия выделены отдельным авторским планом. Пояснения не превращаются автоматически в обязательные R.'})
    correspondence={'schemaVersion':1,'lensKey':key,'source':source,'fullTextInfoId':full_id,'rows':rows,'additionalSources':additional,
                    'retainedIdentityIds':plan.get('retainedIds',[]),'notes':plan.get('notes',[]),
                    'serviceObjects':[full_id,map_id,workflow_id,card_id],
                    'rules':'Карта прослеживает представление конкретной версии текста; не самостоятельный нормативный владелец или запись выполнения.'}
    g['objects'].append({'id':map_id,'kind':'info','title':'Карта соответствия Markdown и структуры','description':'Двустороннее соответствие разделов, сущностей и существенных отношений.','revision':1,'tags':['rdg:lens-source-map'],'value':encoded(correspondence)})
    g['edges'].append(relation('INFO_FOR',map_id,root_id))
    ids=[n['id'] for n in g['nodes']+g['objects']]
    g['workGraphs']=[{'id':plan['workGraphId'],'title':title,'rootIds':[root_id]+(['R-CONTINUITY','R-DECOMPOSITION'] if key=='model' else []),'memberIds':ids}]
    return g,source,purpose,trigger['text'].strip()

def compile_all(write=False):
    plans=json.loads(PLAN.read_text())
    cat=json.loads((FOLDER/'catalog.json').read_text())
    by_key={e['key']:e for e in cat['entries']}
    changed=[]
    for key,plan in plans.items():
        file=FOLDER/(key+'-decision.json')
        existing=json.loads(file.read_text()) if file.exists() else None
        g,source,purpose,triggers=compile_one(key,plan,existing)
        value=encoded(g)
        if not file.exists() or file.read_text()!=value:
            changed.append(file.relative_to(ROOT).as_posix())
            if write:file.write_text(value)
        old=by_key.get(key,{})
        profiles=dict(old.get('profileDefinitions',{}))
        if old.get('definition'):
            previous=json.loads((FOLDER/old['definition']).read_text())
            if previous.get('coreModel')=='rdg-core-v1':profiles['rdg-core-v1']=old['definition']
        preferred={**old}
        if 'definition' in preferred:preferred['definition']=file.name
        entry={**preferred,'key':key,'title':g['title'],'purpose':purpose,'appliesWhen':triggers,'paperOnly':key not in ('work',),'companions':plan.get('companions',old.get('companions',[])),
               'profileDefinitions':{**profiles,'rdg-decision-v1':file.name},
               'sourceRef':source,'sourceMapInfoId':'LS-MAP-'+key.upper()}
        by_key[key]=entry
    order=list(plans)+[k for k in by_key if k not in plans]
    cat['entries']=[by_key[k] for k in order]
    value=encoded(cat)
    if (FOLDER/'catalog.json').read_text()!=value:
        changed.append('tools/rdg-agent-lenses/catalog.json')
        if write:(FOLDER/'catalog.json').write_text(value)
    return changed

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');args=p.parse_args()
    changed=compile_all(args.write)
    print(json.dumps({'changed':changed,'written':args.write},ensure_ascii=False))
    raise SystemExit(0 if args.write or not changed else 1)
