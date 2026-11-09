/* Shared RDG context contract, validation and projection. No network or writes. */
(function(root,factory){
  const api=factory(typeof module==='object'&&module.exports?require('./rdg-catalog.js'):root.RDGCatalog);
  if(typeof module==='object'&&module.exports)module.exports=api;else root.RDGState=api;
})(globalThis,function(catalog){
  'use strict';
  const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
  const text=v=>typeof v==='string'&&v.trim().length>0;
  const array=v=>Array.isArray(v);
  const check=(v,m)=>{if(!v)throw Error('CONTEXT_CONTRACT: '+m);};
  const slug=v=>typeof v==='string'&&/^[a-z0-9][a-z0-9_-]*$/.test(v);
  const object=v=>v&&typeof v==='object'&&!array(v);
  const key=r=>r.graphSlug+':'+r.fieldId;
  const safeURL=v=>{try{const u=new URL(v);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password;}catch(_){return false;}};
  function uses(g){
    const out=[];
    const add=(part,location)=>{for(const u of part.contextUses||[])out.push({...u,location});};
    add(g,'graph');
    for(const n of g.nodes||[]){
      if(n.projectionOf||n.active===false||['inactive','superseded','rejected','historical'].includes(n.status))continue;
      add(n,n.id);
      for(const polarity of ['recommended','contraindicated'])
        for(const c of n.canonBlock?.[polarity]||[])add(c,n.id+'/'+polarity+'/'+c.id);
    }
    return out;
  }
  function validate(items,{partial=false}={}){
    const by=new Map(items.map(i=>[i.slug,i]));
    const resolve=(ref,kind,local)=>{
      const id=kind==='field'?'fieldId':'sourceId',prop=kind==='field'?'contextFields':'knowledgeSources';
      check(object(ref)&&Object.keys(ref).length===2&&slug(ref.graphSlug)&&text(ref[id]),'invalid '+kind+' ref');
      const owner=by.get(ref.graphSlug);
      if(!owner){check(partial,'missing owner '+ref.graphSlug);return;}
      check((owner.graph[prop]||[]).some(x=>x.id===ref[id]),'missing '+kind+' '+ref[id]);
      if(owner.group==='workspaces'&&local.graph.identitySpace!==owner.graph.identitySpace)
        throw Error('CONTEXT_CONTRACT: cross-project definition/source ref');
    };
    const unique=(xs,label)=>{check(array(xs),label+' must be array');const ids=new Set();for(const x of xs){check(object(x)&&text(x.id)&&!ids.has(x.id),'duplicate/invalid '+label+' id');ids.add(x.id);}};
    const sources=(part,item)=>{
      if(own(part,'sourceRefs')){check(array(part.sourceRefs),'sourceRefs must be array');for(const r of part.sourceRefs)resolve(r,'source',item);}
    };
    const answerOwners=new Set();
    for(const item of items){
      const g=item.graph;
      unique(g.knowledgeSources||[],'knowledgeSources');
      for(const s of g.knowledgeSources||[])check(text(s.title)&&safeURL(s.url),'source needs title and safe http(s) URL');
      unique(g.contextFields||[],'contextFields');
      for(const f of g.contextFields||[]){check(text(f.title)&&text(f.explanation),'field needs title/explanation');sources(f,item);}
      if(own(g,'contextFieldsComplete'))check(typeof g.contextFieldsComplete==='boolean','invalid contextFieldsComplete');
      const parts=[g,...(g.nodes||[])];
      for(const n of g.nodes||[]){
        if(n.canonBlock){
          parts.push(n.canonBlock,...(n.canonBlock.recommended||[]),...(n.canonBlock.contraindicated||[]));
          const c=n.canonBlock;
          check(!own(c,'contextUses'),'contextUses belongs on graph, node or canon case, not canonBlock');
          if(own(c,'preparation'))check(['link-only','interpreted'].includes(c.preparation),'invalid preparation');
          if(c.preparation==='link-only')check(c.fieldsComplete!==true&&array(c.sourceRefs)&&c.sourceRefs.length,'link-only needs source; cannot declare complete');
          if(c.preparation==='interpreted')check(text(c.interpretation),'interpreted canon needs interpretation for R/option');
          if(own(c,'fieldsComplete'))check(typeof c.fieldsComplete==='boolean','invalid fieldsComplete');
        }
        check(!own(n,'contextAnswers'),'legacy contextAnswers history must be migrated to one current contextValue');
        if(own(n,'contextFieldRef')||own(n,'contextValue')){
          check(n.kind==='context'&&!n.projectionOf&&text(g.identitySpace),'only project-scoped owning Context stores field values');
          resolve(n.contextFieldRef,'field',item);
          if(own(n,'contextValue')){
            const v=n.contextValue;
            check(object(v)&&Object.keys(v).every(k=>['value','source','scope'].includes(k))&&
              text(v.value)&&text(v.source)&&text(v.scope),'contextValue needs value/source/scope, no history or dates');
          }
          if(item.group==='workspaces'&&n.active!==false&&!['inactive','superseded'].includes(n.status)){
            const k=g.identitySpace+'|'+key(n.contextFieldRef);check(!answerOwners.has(k),'duplicate project answer owner '+k);answerOwners.add(k);
          }
        }
      }
      for(const p of parts){
        sources(p,item);
        if(own(p,'contextUses')){
          check(array(p.contextUses),'contextUses must be array');
          for(const u of p.contextUses){
            check(object(u)&&text(u.purpose),'usage needs purpose');resolve(u.fieldRef,'field',item);
            if(own(u,'when')){
              check(object(u.when)&&Object.keys(u.when).length===1&&array(u.when.allSelected)&&u.when.allSelected.length,'when needs allSelected');
              for(const r of u.when.allSelected){
                check(object(r)&&Object.keys(r).length===2&&slug(r.graphSlug)&&text(r.optionId),'invalid selection condition');
                const target=by.get(r.graphSlug);
                if(!target){check(partial,'condition graph unavailable');continue;}
                check(target.graph.identitySpace===g.identitySpace,'cross-project condition');
                check(target.graph.nodes.some(n=>n.id===r.optionId&&n.kind==='option'),'missing condition option');
              }
            }
          }
        }
      }
    }
    return true;
  }
  function collect({items,manifest={},graphSlug,rootGraphSlug,identitySpace,scope='project'}){
    const by=new Map(items.filter(i=>i.graph).map(i=>[i.slug,i]));
    const rootSlug=rootGraphSlug||graphSlug;
    const targets=rootGraphSlug?(()=>{
      const included=new Set([rootGraphSlug]);
      let changed=true;
      while(changed){changed=false;for(const r of manifest.relations||[]){
        if(included.has(r.from)&&!included.has(r.to)&&
          ['selected','prepared','potential','derived','same-requirement'].includes(r.relationKind)){
          included.add(r.to);changed=true;
        }
      }}
      return [...included];
    })():[graphSlug];
    check(targets.length&&targets.every(s=>typeof s==='string'),'graphSlug or rootGraphSlug required');
    let states=null;
    if(rootGraphSlug){
      const actual=new Set([rootGraphSlug]),alternative=new Set();let changed=true;
      while(changed){changed=false;for(const r of manifest.relations||[]){
        const fromActual=actual.has(r.from),fromAlternative=alternative.has(r.from);
        const isAlternative=fromAlternative||r.relationKind==='potential'||r.relationKind==='prepared';
        const target=isAlternative?alternative:actual;
        if((fromActual||fromAlternative)&&!target.has(r.to)&&!actual.has(r.to)){
          target.add(r.to);changed=true;
        }
      }}
      states=Object.fromEntries(targets.map(x=>[x,alternative.has(x)?'alternative':actual.has(x)?'current':'unknown']));
    }
    const spaces=new Set(targets.map(s=>by.get(s)?.graph.identitySpace).filter(Boolean));
    if(identitySpace)check([...spaces].every(s=>s===identitySpace),'identitySpace mismatch');
    else if(spaces.size===1)identitySpace=[...spaces][0];
    check(spaces.size<=1,'mixed project graph set');
    const result={identitySpace:identitySpace||null,graphSlugs:targets,scope,fields:[],incomplete:[],freeformCandidates:[],coverage:'declared uses in available catalog; external sources not inspected'};
    const sourceList=refs=>(refs||[]).map(r=>{
      const s=by.get(r.graphSlug)?.graph.knowledgeSources?.find(s=>s.id===r.sourceId);
      return s?{...s,graphSlug:r.graphSlug}:{...r,unavailable:true};
    });
    const selected=r=>{
      const g=by.get(r.graphSlug)?.graph;
      if(!g)return null;
      return g.nodes.some(n=>n.kind==='decision'&&(n.status==='committed'&&g.exampleOnly!==true||n.status==='selected-in-example-only'&&g.exampleOnly===true&&g.hypothetical===true&&g.readOnly===true&&g.selectedInProject===false)&&n.selectedOptionId===r.optionId&&n.active!==false);
    };
    if(!identitySpace)result.incomplete.push({reason:'project-identity-unavailable'});
    const fields=new Map();
    for(const s of targets){
      const item=by.get(s),g=item?.graph;
      if(!g){result.incomplete.push({graphSlug:s,reason:'graph-unavailable'});continue;}
      if(g.contextFieldsComplete!==true)result.incomplete.push({graphSlug:s,reason:'field-list-not-declared-complete'});
      for(const n of g.nodes||[])if(n.canonBlock&&(n.canonBlock.preparation==='link-only'||n.canonBlock.fieldsComplete===false))
        result.incomplete.push({graphSlug:s,location:n.id,reason:'canon-fields-incomplete'});
      for(const u of uses(g)){
        const k=key(u.fieldRef),owner=by.get(u.fieldRef.graphSlug),def=owner?.graph.contextFields?.find(f=>f.id===u.fieldRef.fieldId);
        if(!fields.has(k))fields.set(k,{fieldRef:u.fieldRef,title:def?.title||k,explanation:def?.explanation||'Определение недоступно',sources:sourceList(def?.sourceRefs),definitionAvailable:!!def,usages:[],answer:null,answerStatus:'missing'});
        let state='now',reasons=[];
        if(states?.[s]==='alternative'){state='later';reasons.push('Граф относится к невыбранному пути');}
        else if(states?.[s]==='unknown'){state='unknown';reasons.push('Актуальность пути не установлена');}
        for(const condition of u.when?.allSelected||[]){
          const yes=selected(condition);const cg=by.get(condition.graphSlug)?.graph,option=cg?.nodes.find(n=>n.id===condition.optionId);
          reasons.push('После выбора «'+(option?.title||condition.optionId)+'» в «'+(cg?.title||condition.graphSlug)+'»');
          if(yes===false)state='later';else if(yes===null&&state!=='later')state='unknown';
        }
        fields.get(k).usages.push({...u,graphSlug:s,state,reasons});
      }
    }
    // Values are authoritative only in owning Context records in this project.
    for(const item of items){
      const g=item.graph;if(!g||!identitySpace||g.identitySpace!==identitySpace)continue;
      const teaching=targets.some(s=>by.get(s)?.group==='examples');
      if(item.group!=='workspaces'&&!(teaching&&item.group==='examples'))continue;
      if(g.templateOnly)continue;
      for(const n of g.nodes||[]){
        if(n.kind!=='context'||n.projectionOf||n.active===false||['inactive','superseded','candidate','potential'].includes(n.status))continue;
        if(!n.contextFieldRef){result.freeformCandidates.push({graphSlug:item.slug,nodeId:n.id,text:n.currentStatement||n.description||n.title,status:'mapping-needs-assessment'});continue;}
        const row=fields.get(key(n.contextFieldRef));if(!row||!n.contextValue)continue;
        const v=n.contextValue;
        const status=v.scope!=='project'&&v.scope!==scope?'scope-needs-assessment':'applicable';
        const candidate={...v,status,graphSlug:item.slug,nodeId:n.id,exampleOnly:item.group==='examples'};
        (row._candidates??=[]).push(candidate);
      }
    }
    for(const row of fields.values()){
      row.state=row.usages.some(u=>u.state==='now')?'now':row.usages.some(u=>u.state==='unknown')?'unknown':'later';
      const candidates=row._candidates||[];
      row.answerStatus=candidates.length>1?'conflict':candidates.length===1?
        (candidates[0].status==='applicable'?'known':'needs-assessment'):'missing';
      row.answer=candidates.length===1?candidates[0]:null;
      if(candidates.length>1)row.conflictingOwners=candidates;
      delete row._candidates;
      row.nextAction=row.state!=='now'?'defer':row.answerStatus==='known'?'reuse':'check-known-context-or-ask';
      row.question=row.state==='now'&&row.answerStatus!=='known';
      if(!row.definitionAvailable)result.incomplete.push({fieldRef:row.fieldRef,reason:'definition-unavailable'});
      result.fields.push(row);
    }
    result.fields.sort((a,b)=>key(a.fieldRef).localeCompare(key(b.fieldRef)));
    return result;
  }
  return Object.freeze({validate,collect,uses,safeURL});
});
