/* Pure viewer-only projection. Domain entity/edge identity is never duplicated. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.RDGVisualProjection=api;
})(globalThis,function(){
  'use strict';
  const structural=new Set(['DRIVES','DERIVES','INTRODUCES','DECISION_MEMBER','REQUIRES_ACTION','FINDING_RESPONSE','FINDING_PROPOSAL']);
  function canonOnlyInfoIds(graph){
    const canonIds=new Set((graph.objects||[]).filter(n=>n.kind==='canon').map(n=>n.id));
    const active=(graph.edges||[]).filter(e=>!e.archived);
    return new Set((graph.objects||[]).filter(n=>n.kind==='info').filter(n=>{
      const links=active.filter(e=>e.from===n.id||e.to===n.id);
      return links.length>0&&links.every(e=>e.type==='INFO_FOR'&&e.from===n.id&&canonIds.has(e.to));
    }).map(n=>n.id));
  }
  function project(entities,edges,positions,occurrences={},options={}){
    const byId=new Map([...(options.externalEntities||[]),...entities].map(n=>[n.id,n]));
    const realEdges=new Map([...(options.externalEdges||[]),...edges].map(e=>[e.id,e]));
    const nodes=entities.map(n=>({id:n.id,entityId:n.id,node:n,position:positions[n.id],alias:false}));
    const invalid=[];
    const seen=new Map(nodes.map(n=>[n.id,n]));
    for(const [id,o] of Object.entries(occurrences)){
      const n=byId.get(o.entityId);
      if(!n){invalid.push({id,reason:'entity missing'});continue;}
      const item={id,entityId:n.id,node:n,position:o,alias:true};
      nodes.push(item);seen.set(id,item);
    }
    const routes=[],replaced=new Set();
    for(const [id,o] of Object.entries(occurrences)){
      if(!o.parentId)continue;
      const parent=seen.get(o.parentId),child=seen.get(id),edge=realEdges.get(o.viaEdgeId);
      const reverse=o.reverse===true;
      if(!parent||!child||!edge||
         (reverse?(edge.from!==child.entityId||edge.to!==parent.entityId):
           (edge.from!==parent.entityId||edge.to!==child.entityId))){
        invalid.push({id,reason:'source relation missing or endpoints changed'});continue;}
      routes.push({id:'route-'+id,edge,from:reverse?id:parent.id,to:reverse?parent.id:id});
      if(!reverse&&parent.id===edge.from)replaced.add(edge.id);
    }
    for(const e of edges)if(!replaced.has(e.id)&&seen.has(e.from)&&seen.has(e.to))
      routes.push({id:'edge-'+e.id,edge:e,from:e.from,to:e.to});
    const counts=new Map();
    for(const n of nodes)counts.set(n.entityId,(counts.get(n.entityId)||0)+1);
    return {nodes,routes,counts,invalid};
  }
  function boundaries(allEntities,allEdges,memberIds){
    const member=new Set(memberIds),byId=new Set(allEntities.map(n=>n.id));
    return allEdges.filter(e=>!e.archived&&byId.has(e.from)&&byId.has(e.to)&&member.has(e.from)!==member.has(e.to))
      .map(e=>({edge:e,inside:member.has(e.from)?e.from:e.to,outside:member.has(e.from)?e.to:e.from,
        direction:member.has(e.from)?'out':'in'}));
  }
  function addBranch(entities,edges,positions,records,startId,depth,idFactory,{duplicateRoot=true,includeCompanions=false,onlyCompanions=false}={}){
    const base=project(entities,edges,positions,records),start=base.nodes.find(n=>n.id===startId);
    if(!start||!['action','requirement','decision'].includes(start.node.kind))throw Error('VISUAL_ROOT_UNKNOWN');
    if(!Number.isInteger(depth)||depth<0||depth>3)throw Error('VISUAL_DEPTH');
    const result=JSON.parse(JSON.stringify(records)),used=new Set([...Object.keys(records),...entities.map(n=>n.id)]);
    const create=(entityId,x,y,parentId,viaEdgeId,reverse=false)=>{
      const id=idFactory();if(!id.startsWith('occ-')||used.has(id))throw Error('VISUAL_OCCURRENCE_ID');
      used.add(id);result[id]={entityId,x,y,...(parentId?{parentId,viaEdgeId,...(reverse?{reverse:true}:{})}:{})};return id;
    };
    const here=start.position||{x:30,y:30};
    const root=duplicateRoot?create(start.entityId,here.x+245,here.y+45):start.id;
    let frontier=[{id:root,entityId:start.entityId,path:new Set([start.entityId]),x:duplicateRoot?here.x+245:here.x,y:duplicateRoot?here.y+45:here.y}];
    const allowed=new Map(entities.map(n=>[n.id,n.kind]));
    const outgoing=new Map(),incoming=new Map();
    for(const e of edges){const list=outgoing.get(e.from)||[];list.push(e);outgoing.set(e.from,list);
      const inbound=incoming.get(e.to)||[];inbound.push(e);incoming.set(e.to,inbound);}
    for(let level=0;level<depth;level++){
      const next=[];
      for(const parent of frontier){
        const children=(onlyCompanions?[]:outgoing.get(parent.entityId)||[]).filter(e=>structural.has(e.type)&&allowed.has(e.to))
          .map(e=>({edge:e,other:e.to,reverse:false}));
        if(includeCompanions)for(const e of incoming.get(parent.entityId)||[])
          if(['CONTEXT_FOR','CANON_FOR','INFO_FOR','EVIDENCE_FOR'].includes(e.type)&&allowed.has(e.from))
            children.push({edge:e,other:e.from,reverse:true});
        children.sort((a,b)=>a.edge.id.localeCompare(b.edge.id));
        for(const [i,{edge:e,other,reverse}] of children.entries()){
          if(parent.path.has(other)||Object.keys(result).length>=400)continue;
          const x=parent.x+(reverse?-235:235),y=parent.y+i*115;
          const id=create(other,x,y,parent.id,e.id,reverse);
          next.push({id,entityId:other,x,y,path:new Set([...parent.path,other])});
        }
      }
      frontier=next;if(!frontier.length)break;
    }
    return {occurrences:result,root};
  }
  // A focus is a view, not a durable layout owner. Keep real process coordinates
  // untouched and derive a deterministic, one-hop compact arrangement on read.
  function compactFocus(nodes,edges,stored,focusId,contextIds=[]){
    const selected=nodes.find(n=>n.id===focusId);
    if(!selected)return {};
    const byId=new Map(nodes.map(n=>[n.id,n]));
    // Decision-context references are shown to the left like factual inputs,
    // without forging a typed semantic edge or adding parent-child behavior.
    const incoming=new Set([...edges.filter(e=>e.to===focusId&&byId.has(e.from)).map(e=>e.from),
      ...contextIds.filter(id=>id!==focusId&&byId.has(id))]);
    const outgoing=new Set(edges.filter(e=>e.from===focusId&&byId.has(e.to)).map(e=>e.to));
    outgoing.delete(focusId);
    const before=nodes.filter(n=>incoming.has(n.id)&&n.id!==focusId);
    const after=nodes.filter(n=>n.id!==focusId&&!incoming.has(n.id));
    const order=(a,b)=>(stored[a.id]?.y??Infinity)-(stored[b.id]?.y??Infinity)||
      a.id.localeCompare(b.id);
    before.sort(order);after.sort((a,b)=>Number(!outgoing.has(a.id))-Number(!outgoing.has(b.id))||order(a,b));
    // A large one-hop focus must not turn into a 20-card vertical scroll.
    // Up to six cards per column, with incoming cards before the focus and
    // outgoing cards after it; all coordinates remain session-only.
    const columns=items=>Math.max(1,Math.ceil(items.length/6));
    const beforeColumns=columns(before),afterColumns=columns(after),step=152,top=44;
    const beforeRows=Math.ceil(before.length/beforeColumns),afterRows=Math.ceil(after.length/afterColumns);
    const rows=Math.max(beforeRows,afterRows,1);
    const focusY=top+(rows-1)*step/2;
    const centerX=before.length?44+beforeColumns*260+50:44;
    const result={[focusId]:{x:centerX,y:focusY}};
    const line=(items,x,count)=>items.forEach((n,i)=>{
      const row=Math.floor(i/count),col=i%count;
      result[n.id]={x:x+col*260,y:top+(rows-Math.ceil(items.length/count))*step/2+row*step};
    });
    line(before,44,beforeColumns);line(after,centerX+310,afterColumns);
    return result;
  }
  // Read-only overview. Compact *visible images*, including real occurrence
  // images, without writing or changing the process' canonical layout.
  function compactOverview(picture){
    // A bounded, deterministic, read-only layout for visible images. Structural
    // dependencies define top-to-bottom layers; context/canon/info images share
    // their target's layer. No persistent position or domain relation is edited.
    const nodes=picture.nodes,byId=new Map(nodes.map(n=>[n.id,n]));
    const outbound=new Map(nodes.map(n=>[n.id,[]]));
    const inbound=new Map(nodes.map(n=>[n.id,[]]));
    const supporting=new Map(nodes.map(n=>[n.id,[]]));
    for(const route of picture.routes){
      if(!byId.has(route.from)||!byId.has(route.to))continue;
      if(structural.has(route.edge.type)){
        outbound.get(route.from).push(route.to);
        inbound.get(route.to).push(route.from);
      }else if(['CANON_FOR','CONTEXT_FOR','INFO_FOR','EVIDENCE_FOR'].includes(route.edge.type)){
        supporting.get(route.from).push(route.to);
      }
    }
    const kinds={requirement:0,decision:1,action:2,canon:3,context:4,info:5,evidence:6};
    const order=(a,b)=>(kinds[a.node.kind]??7)-(kinds[b.node.kind]??7)||a.id.localeCompare(b.id);
    const roots=nodes.filter(n=>inbound.get(n.id).length===0).sort(order);
    const rank=new Map(),queue=[];
    for(const n of roots){rank.set(n.id,0);queue.push(n.id);}
    const visit=()=>{for(let k=0;k<queue.length;k++)for(const to of [...outbound.get(queue[k])].sort())
      if(!rank.has(to)){
        rank.set(to,Math.min(32,rank.get(queue[k])+1));queue.push(to);
      }
      queue.length=0;
    };
    visit();
    // Disconnected all-cycle components have no entry node; choose a stable
    // starting image. This also prevents any unpositioned images.
    for(const n of [...nodes].sort(order))if(!rank.has(n.id)){
      rank.set(n.id,0);queue.push(n.id);visit();
    }
    // Isolated supporting facts are visually associated with their targets;
    // they do not become unrelated roots above every decision branch.
    for(const n of nodes)if(!inbound.get(n.id).length&&!outbound.get(n.id).length&&supporting.get(n.id).length){
      const targets=supporting.get(n.id).filter(id=>rank.has(id));
      if(targets.length)rank.set(n.id,Math.min(...targets.map(id=>rank.get(id))));
    }
    const layers=new Map();
    for(const n of nodes){const row=rank.get(n.id)??0;if(!layers.has(row))layers.set(row,[]);layers.get(row).push(n);}
    const positions={},occurrences={},cardW=220,cardH=126,stepX=260,stepY=156;
    const maxColumns=5;
    let top=28,previousOrder=new Map();
    for(const depth of [...layers.keys()].sort((a,b)=>a-b)){
      const items=layers.get(depth);
      const center=n=>{
        const source=inbound.get(n.id).filter(id=>previousOrder.has(id));
        const refs=source.length?source:supporting.get(n.id).filter(id=>previousOrder.has(id));
        return refs.length?refs.reduce((sum,id)=>sum+previousOrder.get(id),0)/refs.length:Infinity;
      };
      items.sort((a,b)=>center(a)-center(b)||order(a,b));
      // Wrap very wide layers, so a graph with many alternatives stays readable
      // without a several-thousand-pixel horizontal strip.
      const columns=Math.min(maxColumns,items.length),rows=Math.ceil(items.length/columns);
      items.forEach((n,i)=>{
        const row=Math.floor(i/columns),col=i%columns,used=Math.min(columns,items.length-row*columns);
        const at={x:34+(maxColumns-used)*stepX/2+col*stepX,y:top+row*stepY};
        if(n.alias)occurrences[n.id]={...n.position,x:at.x,y:at.y};
        else positions[n.id]=at;
        previousOrder.set(n.id,at.x);
      });
      top+=rows*stepY+26;
    }
    const point=id=>occurrences[id]||positions[id];
    return {...picture,nodes:nodes.map(n=>({...n,position:point(n.id)})),
      positions,occurrences,compact:true};
  }

  function decisionProject(graph,view,layout={},options={}){
    const core=typeof module==='object'&&module.exports?require('./rdg-layout-core.js'):globalThis.RDGLayoutCore;
    const entities=view.entities,all=graph.nodes.concat(graph.objects),byId=new Map(all.map(n=>[n.id,n]));
    const memberships=graph.decisionGroups.flatMap(g=>g.members.map(m=>({id:m.id,type:'DECISION_MEMBER',from:g.parentId,to:m.decisionId,groupId:g.id})));
    const allEdges=graph.edges.filter(e=>!e.archived).concat(memberships),pairs=new Set();
    const edges=allEdges.filter(e=>{if(e.type!=='DECISION_MEMBER')return true;const key=e.from+'|'+e.to;if(pairs.has(key))return false;pairs.add(key);return true;});
    const hidden=new Set((view.groupVisibility||[]).flatMap(g=>g.hiddenIds));
    if(view.spec.kind==='focus')hidden.delete(view.spec.id);
    const cut=new Set(hidden),visible=new Set(),structuralEdges=edges.filter(e=>structural.has(e.type));
    let front=new Set([...graph.rootCauses.map(c=>c.requirementId),...all.filter(n=>!structuralEdges.some(e=>e.to===n.id)).map(n=>n.id)]);
    while(front.size){const next=new Set();for(const id of front){if(hidden.has(id)||visible.has(id))continue;visible.add(id);for(const e of structuralEdges)if(e.from===id)next.add(e.to);}front=next;}
    front=new Set(hidden);while(front.size){const next=new Set();for(const id of front)for(const e of structuralEdges)if(e.from===id&&!cut.has(e.to)){cut.add(e.to);next.add(e.to);}front=next;}
    for(const id of visible)if(!hidden.has(id))cut.delete(id);
    // Canon and Info used only by Canon remain owner objects, but are
    // presented in the target's inspector rather than as graph images.
    // Standalone Info stays available in full/focus; a focused Info can still
    // be opened directly from the Canon tab.
    const scoped=entities.filter(n=>!cut.has(n.id)&&!['finding','evidence','question'].includes(n.kind)),canonOnlyInfo=canonOnlyInfoIds(graph);
    const overview=view.spec.kind!=='focus'&&view.spec.showAllBlocks!==true&&
      scoped.some(n=>!['canon','info'].includes(n.kind));
    const nodes=overview?scoped.filter(n=>!['canon','info'].includes(n.kind)):
      scoped.filter(n=>n.kind!=='canon'&&(!canonOnlyInfo.has(n.id)||view.spec.kind==='focus'&&view.spec.id===n.id));
    const included=new Set(nodes.map(n=>n.id));
    const supportingCounts={};
    if(overview){
      const present=new Set(scoped.map(n=>n.id)),kindOf=new Map(scoped.map(n=>[n.id,n.kind]));
      const adjacent=new Map();
      for(const e of edges){
        if(!present.has(e.from)||!present.has(e.to)||e.archived)continue;
        if(!adjacent.has(e.to))adjacent.set(e.to,[]);
        adjacent.get(e.to).push(e);
      }
      for(const n of nodes){
        const canons=new Set((adjacent.get(n.id)||[]).filter(e=>e.type==='CANON_FOR'&&kindOf.get(e.from)==='canon').map(e=>e.from));
        const infos=new Set((adjacent.get(n.id)||[]).filter(e=>e.type==='INFO_FOR'&&kindOf.get(e.from)==='info').map(e=>e.from));
        for(const canonId of canons)for(const e of adjacent.get(canonId)||[])
          if(e.type==='INFO_FOR'&&kindOf.get(e.from)==='info')infos.add(e.from);
        if(infos.size)supportingCounts[n.id]={info:infos.size};
      }
    }
    const storedPositions=layout.positions||{};
    const positions=JSON.parse(JSON.stringify(storedPositions));
    // Temporary safe anchors for shared-branch occurrence construction. Nodes
    // without stored coordinates are rearranged below, before projection output.
    all.forEach((n,i)=>positions[n.id]??={x:40+(i%4)*260,y:40+Math.floor(i/4)*156});
    const records=JSON.parse(JSON.stringify(layout.occurrences||{})),expanded=new Set(view.spec.expandedOccurrenceIds||[]);
    const drawEdges=view.edges.concat((view.decisionMemberships||[]).filter(m=>!view.edges.some(e=>e.id===m.id))).filter(e=>included.has(e.from)&&included.has(e.to));
    if(view.spec.kind==='workGraph'){
      // Occurrences belong to the process' layout, not automatically to every
      // WorkGraph. Keep only duplicates justified by multiple *visible* incoming
      // relations; a repeat whose other parent is outside this scope would be
      // an orphan image (A5/A17 in the Viewer+Plan acceptance WorkGraph).
      const edgeById=new Map(drawEdges.map(e=>[e.id,e])),inbound=new Map();
      for(const e of drawEdges.filter(e=>structural.has(e.type))){
        const set=inbound.get(e.to)||new Set();
        set.add(e.from+'|'+e.to);inbound.set(e.to,set);
      }
      const checked=new Map(),visiting=new Set();
      const localRecord=id=>{
        if(checked.has(id))return checked.get(id);
        const r=records[id];
        if(!r||!included.has(r.entityId)||visiting.has(id))return false;
        visiting.add(id);
        const edge=edgeById.get(r.viaEdgeId),parent=records[r.parentId];
        const parentEntity=parent?.entityId||r.parentId;
        const oriented=edge&&(r.reverse===true?
          edge.from===r.entityId&&edge.to===parentEntity:
          edge.from===parentEntity&&edge.to===r.entityId);
        const valid=!!oriented&&
          (parent?localRecord(r.parentId):
            included.has(r.parentId)&&(inbound.get(r.entityId)?.size||0)>1);
        visiting.delete(id);checked.set(id,valid);
        return valid;
      };
      for(const id of Object.keys(records))if(!localRecord(id))delete records[id];
    }
    if(view.spec.kind==='focus'){
      // Preserve the shared process graphKey while returning only ephemeral positions.
      // No copies of process locations are created or written as focus layout.
      const decision=graph.nodes.find(n=>n.id===view.spec.id&&n.kind==='decision');
      const compact=compactFocus(nodes,drawEdges,positions,view.spec.id,
        decision?.decisionContextIds||[]);
      for(const [id,p] of Object.entries(view.spec.focusPositions||{})){
        if(Object.hasOwn(compact,id))compact[id]={x:p.x,y:p.y};
      }
      const picture=project(nodes,drawEdges,compact);
      return {...picture,counts:Object.fromEntries(picture.counts),positions:compact,
        occurrences:{},hiddenIds:[...cut],
        groupLabels:memberships.filter(m=>included.has(m.from)&&included.has(m.to)),factsCreated:false};
    }
    if(view.spec.kind!=='focus'){
      const inbound=new Map();for(const e of drawEdges.filter(e=>structural.has(e.type))){const key=e.to;const list=inbound.get(key)||[];
        if(!list.some(v=>v.from===e.from&&v.to===e.to))list.push(e);inbound.set(key,list);}
      for(const list of inbound.values())if(list.length>1)for(const e of (()=>{const saved=new Set(Object.values(records).filter(r=>r.entityId===list[0].to&&r.parentId&&r.viaEdgeId).map(r=>r.viaEdgeId));const sorted=list.slice().sort((a,b)=>a.id.localeCompare(b.id));const primary=sorted.find(e=>!saved.has(e.id))||sorted[0];return sorted.filter(e=>e.id!==primary.id);})()){
        const route=[[e.id,false]],id=core.occurrenceKey(graph.identitySpace,e.from,route,e.to),p=positions[e.from];
        records[id]??={entityId:e.to,x:p.x+250,y:p.y+90,parentId:e.from,viaEdgeId:e.id};
        const queue=[{id,entity:e.to,anchor:e.from,route,path:new Set([e.from,e.to]),depth:0}];
        while(queue.length){const item=queue.shift();if(!expanded.has(item.id)||item.depth>=8||Object.keys(records).length>=1900)continue;
          const children=structuralEdges.filter(v=>v.from===item.entity&&included.has(v.to));
          for(const [i,edge] of children.entries()){
            const path=[...item.route,[edge.id,false]],child=core.occurrenceKey(graph.identitySpace,item.anchor,path,edge.to),here=records[item.id];
            records[child]??={entityId:edge.to,x:here.x+250,y:here.y+i*135,parentId:item.id,viaEdgeId:edge.id};
            if(!item.path.has(edge.to))queue.push({id:child,entity:edge.to,anchor:item.anchor,route:path,path:new Set([...item.path,edge.to]),depth:item.depth+1});
          }
        }
      }
    }
    const allowedRecords=Object.fromEntries(Object.entries(records).filter(([,r])=>included.has(r.entityId)));
    const visibleRecords=Object.fromEntries(Object.entries(allowedRecords).filter(([id,record])=>{let parent=record.parentId;while(parent&&allowedRecords[parent]){if(!expanded.has(parent))return false;parent=allowedRecords[parent].parentId;}return true;}));
    // Only fill images without an owner-saved position. An entirely new graph
    // starts from the same semantic layout as compact view. Partial saved
    // layouts are preserved byte-for-byte; new nodes are placed beside them.
    const missing=nodes.filter(n=>!Object.hasOwn(storedPositions,n.id));
    if(missing.length){
      const candidates=compactOverview(project(nodes,drawEdges,positions,visibleRecords,
        {externalEntities:all,externalEdges:allEdges})).positions;
      const saved=nodes.filter(n=>Object.hasOwn(storedPositions,n.id));
      const offset=saved.length?Math.max(...saved.map(n=>positions[n.id].x))+270-34:0;
      for(const n of missing)positions[n.id]={x:candidates[n.id].x+offset,y:candidates[n.id].y};
    }
    // New repeat images get a free position near their parent. Explicitly
    // saved repeat coordinates are authoritative, including manual overlaps.
    const storedOccurrences=layout.occurrences||{};
    const occupied=nodes.map(n=>positions[n.id]).filter(Boolean);
    for(const [id,record] of Object.entries(visibleRecords))
      if(Object.hasOwn(storedOccurrences,id))occupied.push(record);
    for(const [id,record] of Object.entries(visibleRecords)){
      if(Object.hasOwn(storedOccurrences,id))continue;
      const parent=visibleRecords[record.parentId]||positions[record.parentId]||{x:34,y:28};
      let at=null;
      for(let i=0;i<2000;i++){
        // 1st column is after the parent, then spill to nearby rows.
        const next={x:parent.x+260+Math.floor(i/7)*260,y:parent.y+(i%7-3)*156};
        if(!occupied.some(p=>Math.abs(p.x-next.x)<240&&Math.abs(p.y-next.y)<144)){
          at=next;break;
        }
      }
      if(!at)at={x:parent.x+260+occupied.length*260,y:parent.y};
      Object.assign(record,at);occupied.push(at);
    }
    const picture=project(nodes,drawEdges,positions,visibleRecords,{externalEntities:all,externalEdges:allEdges});
    if(view.spec.compactGraph===true){
      const compact=compactOverview(picture);
      return {...compact,counts:Object.fromEntries(picture.counts),
        groupLabels:memberships.filter(m=>included.has(m.from)&&included.has(m.to)),
        supportingCounts,factsCreated:false};
    }
    // In 'My layout', unchanged hidden occurrences are still part of the
    // owner's layout. Keep them in the eventual save payload even though the
    // brief projection does not draw them. Otherwise dragging one visible card
    // could silently erase manual positions of hidden Canon/Info images.
    const preservedOccurrences={...layout.occurrences,...allowedRecords};
    return {...picture,counts:Object.fromEntries(picture.counts),positions,occurrences:preservedOccurrences,
      hiddenIds:[...cut],groupLabels:memberships.filter(m=>included.has(m.from)&&included.has(m.to)),
      supportingCounts,factsCreated:false};
  }
  // Read-only structural outline of the same graph. A row is an *occurrence*
  // (one parent/path); entityId is always the actual owner-local entity ID.
  // View-only section and group rows never masquerade as Graph entities/edges.
  function decisionOutline(graph,view,options={}){
    // Canon and Info used only by Canon are read through the target inspector,
    // not as separate rows. A focused standalone Info can still be opened.
    const canonOnlyInfo=canonOnlyInfoIds(graph);
    const visible=new Map((view.entities||[]).filter(n=>!['canon','finding','evidence','question'].includes(n.kind)&&
      (!options.hideProcessContexts||n.kind!=='context')&&
      (!canonOnlyInfo.has(n.id)||view.spec?.kind==='focus'&&view.spec.id===n.id)).map(n=>[n.id,n]));
    const structural=new Map([...visible].filter(([,n])=>['requirement','decision','action'].includes(n.kind)));
    const all=new Map([...(graph.nodes||[]),...(graph.objects||[])].map(n=>[n.id,n]));
    const buckets=new Map(),incoming=new Map();
    const empty=()=>({requirements:[],decisions:[],actions:[]});
    const bucket=id=>{if(!buckets.has(id))buckets.set(id,empty());return buckets.get(id);};
    const groupById=new Map((view.decisionGroups||[]).map(g=>[g.id,g]));
    const groupVisibility=new Map((view.groupVisibility||[]).map(g=>[g.groupId,new Set(g.hiddenIds||[])]));
    const workAreasByEntity=new Map();
    for(const area of graph.workGraphs||[])for(const id of area.memberIds||[]){
      if(!workAreasByEntity.has(id))workAreasByEntity.set(id,[]);
      workAreasByEntity.get(id).push({id:area.id,title:area.title,colorKey:area.colorKey||null});
    }
    const childKinds={DERIVES:'requirements',INTRODUCES:'requirements',DRIVES:'decisions',FINDING_RESPONSE:'decisions',FINDING_PROPOSAL:'decisions',REQUIRES_ACTION:'actions'};
    for(const edge of view.edges||[]){
      const category=childKinds[edge.type];
      if(!category||!structural.has(edge.from)||!structural.has(edge.to))continue;
      bucket(edge.from)[category].push({type:'entity',id:edge.to,via:edge.id,relation:edge.type});
      incoming.set(edge.to,(incoming.get(edge.to)||0)+1);
    }
    // Decision Groups are not extra rows in Structure. A real Decision has one
    // occurrence per structural parent, even when several groups share its
    // (parent, decision) pair. Its group frames are independent read-only
    // decorations, drawn from all groups of this Graph (including out-of-scope
    // memberships in Work Graph / Focus).
    const membershipsByDecision=new Map();
    for(const group of graph.decisionGroups||[]){
      const otherMembers=(group.members||[]).map(m=>all.get(m.decisionId)).filter(Boolean);
      for(const member of group.members||[]){
        if(!all.has(member.decisionId))continue;
        if(!membershipsByDecision.has(member.decisionId))membershipsByDecision.set(member.decisionId,[]);
        membershipsByDecision.get(member.decisionId).push({
          id:group.id,title:group.title,parentId:group.parentId,
          parentTitle:all.get(group.parentId)?.title||group.parentId,
          selectionRequired:group.selectionRequired,mutuallyExclusive:group.mutuallyExclusive,
          memberCount:group.members.length,
          selectedCount:otherMembers.filter(n=>n.selectionState==='selected').length,
          otherDecisions:otherMembers.filter(n=>n.id!==member.decisionId).map(n=>({id:n.id,title:n.title})),
          excluded:(groupVisibility.get(group.id)||new Set()).has(member.decisionId)
        });
      }
    }
    for(const groups of membershipsByDecision.values())groups.sort((a,b)=>
      a.title.localeCompare(b.title,'ru')||a.id.localeCompare(b.id));
    for(const group of groupById.values()){
      if(!structural.has(group.parentId))continue;
      for(const member of group.members||[]){
        if(!structural.has(member.decisionId))continue;
        const decisions=bucket(group.parentId).decisions;
        if(decisions.some(item=>item.id===member.decisionId))continue;
        decisions.push({type:'entity',id:member.decisionId,via:member.id,relation:'DECISION_MEMBER'});
        incoming.set(member.decisionId,(incoming.get(member.decisionId)||0)+1);
      }
    }
    const query=String(options.query||'').trim().toLocaleLowerCase();
    const groupMatches=new Set(),relevant=new Set(),parents=new Map();
    if(query){
      for(const [id,n] of visible)if((n.title+' '+id+' '+(n.description||'')).toLocaleLowerCase().includes(query))relevant.add(id);
      for(const edge of view.edges||[])if(childKinds[edge.type]&&structural.has(edge.from)&&structural.has(edge.to)){
        if(!parents.has(edge.to))parents.set(edge.to,new Set());parents.get(edge.to).add(edge.from);
      }
      for(const group of groupById.values()){
        for(const member of group.members){
          if(!structural.has(member.decisionId))continue;
          if(!parents.has(member.decisionId))parents.set(member.decisionId,new Set());
          parents.get(member.decisionId).add(group.parentId);
        }
        if((group.title+' '+group.id).toLocaleLowerCase().includes(query)){
          groupMatches.add(group.id);relevant.add(group.parentId);
          for(const member of group.members)if(structural.has(member.decisionId))relevant.add(member.decisionId);
        }
      }
      const queue=[...relevant];while(queue.length){const id=queue.pop();for(const parent of parents.get(id)||[]){
        if(!relevant.has(parent)){relevant.add(parent);queue.push(parent);}
      }}
    }
    const sorted=(rows)=>rows.slice().sort((a,b)=>{
      const name=x=>visible.get(x.id)?.title;
      return String(name(a)||a.id).localeCompare(String(name(b)||b.id),'ru')||a.id.localeCompare(b.id);
    });
    for(const value of buckets.values())for(const name of Object.keys(value))value[name]=sorted(value[name]);
    // Reveal a newly created entity through existing occurrences, including
    // collapsed type buckets. Only presentation keys are returned to the UI.
    const revealAncestors=new Set(),revealParents=new Map(),revealPaths=new Set();
    if(structural.has(options.revealEntityId)){
      for(const [parent,b] of buckets)for(const members of Object.values(b))for(const item of members){
        if(!revealParents.has(item.id))revealParents.set(item.id,new Set());
        revealParents.get(item.id).add(parent);
      }
      const queue=[options.revealEntityId];while(queue.length){const id=queue.pop();
        if(revealAncestors.has(id))continue;revealAncestors.add(id);
        queue.push(...revealParents.get(id)||[]);
      }
    }
    const reached=new Set();
    const reach=id=>{const queue=[id];while(queue.length){const current=queue.pop();if(reached.has(current))continue;reached.add(current);
      const b=bucket(current);for(const name of ['requirements','decisions','actions'])for(const item of b[name])queue.push(item.id);
    }};
    const requested=[];
    if(view.spec?.kind==='workGraph'){
      const area=(graph.workGraphs||[]).find(w=>w.id===view.spec.id);
      for(const id of area?.rootIds||[])if(structural.has(id))requested.push(id);
    }else if(view.spec?.kind==='focus'){
      if(structural.has(view.spec.id)&&!(incoming.get(view.spec.id)||0))requested.push(view.spec.id);
    }else if(structural.has(graph.rootRequirementId))requested.push(graph.rootRequirementId);
    const roots=[];
    const use=id=>{if(!reached.has(id)){roots.push(id);reach(id);}};
    for(const id of requested)use(id);
    for(const id of [...structural.keys()].filter(id=>!incoming.has(id)).sort((a,b)=>{
      return visible.get(a).title.localeCompare(visible.get(b).title,'ru')||a.localeCompare(b);
    }))use(id);
    // A missing ancestor in a Working Graph or a malformed cyclic fixture must
    // never make otherwise visible entities disappear from the outline.
    for(const id of [...structural.keys()].sort())use(id);
    // In a focused R/D (or Action) outline, parents are references preceding
    // one focused root. The process-wide multi-parent occurrence tree is NOT
    // copied into focus: descendants are drawn at most once as well.
    const isFocus=view.spec?.kind==='focus'&&structural.has(view.spec.id);
    const focusId=isFocus?view.spec.id:null;
    if(isFocus){roots.length=0;roots.push(focusId);}
    const focusParents=new Map();
    if(isFocus){
      for(const edge of view.edges||[]){
        if(edge.to!==focusId||!childKinds[edge.type]||!structural.has(edge.from)||edge.from===focusId)continue;
        const row=focusParents.get(edge.from)||{id:edge.from,relations:new Set(),groups:new Set()};
        row.relations.add(edge.type);focusParents.set(edge.from,row);
      }
      for(const group of groupById.values()){
        if(!structural.has(group.parentId)||group.parentId===focusId||
           !group.members.some(m=>m.decisionId===focusId))continue;
        const row=focusParents.get(group.parentId)||{id:group.parentId,relations:new Set(),groups:new Set()};
        row.relations.add('DECISION_MEMBER');row.groups.add(group.title);focusParents.set(group.parentId,row);
      }
    }
    const outsideParents=new Map();
    if(view.spec?.kind==='workGraph'){
      for(const edge of graph.edges||[]){
        if(!childKinds[edge.type]||!structural.has(edge.to)||visible.has(edge.from))continue;
        if(!outsideParents.has(edge.to))outsideParents.set(edge.to,new Set());
        outsideParents.get(edge.to).add(edge.from);
      }
      for(const group of graph.decisionGroups||[])if(!visible.has(group.parentId))for(const m of group.members||[])
        if(structural.has(m.decisionId)){
          if(!outsideParents.has(m.decisionId))outsideParents.set(m.decisionId,new Set());
          outsideParents.get(m.decisionId).add(group.parentId);
        }
    }
    const extras=new Map([['context',[]],['info',[]],['evidence',[]],['finding',[]]]);
    for(const entity of visible.values())if(extras.has(entity.kind)&&
        (!query||(entity.title+' '+entity.id+' '+(entity.description||'')).toLocaleLowerCase().includes(query)))
      extras.get(entity.kind).push(entity);
    for(const rows of extras.values())rows.sort((a,b)=>a.title.localeCompare(b.title,'ru')||a.id.localeCompare(b.id));
    const supplemental=new Map();
    for(const edge of graph.edges||[])if(['CONTEXT_FOR','INFO_FOR','EVIDENCE_FOR','DEPENDS_ON'].includes(edge.type)&&structural.has(edge.to)){
      const entry=supplemental.get(edge.to)||{processContext:0,info:0,evidence:0,dependency:0};
      const key={CONTEXT_FOR:'processContext',INFO_FOR:'info',EVIDENCE_FOR:'evidence',DEPENDS_ON:'dependency'}[edge.type];
      entry[key]++;supplemental.set(edge.to,entry);
    }
    for(const [id,node] of structural)if(node.kind==='decision'&&node.decisionContextIds?.length){
      const entry=supplemental.get(id)||{processContext:0,info:0,evidence:0,dependency:0};
      entry.decisionContext=node.decisionContextIds.length;supplemental.set(id,entry);
    }
    const expanded=new Set(options.expandedPaths||[]),collapsed=new Set(options.collapsedPaths||[]);
    const maxRows=Math.min(1500,Math.max(100,options.maxRows||900)),maxDepth=48;
    const rows=[],counts=new Map(),focusDisplayed=new Set();let truncated=false;
    const keyHash=str=>{let a=2166136261,b=16777619;for(let i=0;i<str.length;i++){
      a=Math.imul(a^str.charCodeAt(i),16777619);b=Math.imul(b^str.charCodeAt(i),2166136261);
    }return (a>>>0).toString(36)+'-'+(b>>>0).toString(36);};
    const childKey=(parent,type,id,via)=>type+':'+id+'@'+keyHash(parent+'|'+via);
    const show=(key,initial,reveal=false)=>{if(reveal)revealPaths.add(key);
      return reveal||expanded.has(key)||!collapsed.has(key)&&initial;};
    const add=row=>{if(rows.length>=maxRows){truncated=true;return false;}
      rows.push(row);if(row.type==='entity')counts.set(row.entityId,(counts.get(row.entityId)||0)+1);return true;};
    // Tree hierarchy is expressed solely by the depth of actual rows.
    const subcategories=[['requirements','Обязательные требования','Необходимы для завершения родителя'],['decisions','Решения','Варианты выбора в рамках требований'],['actions','Действия','Способы выполнения выбранной работы']];
    function entity(id,key,depth,entityDepth,path,relation='root',excluded=false){
      const node=visible.get(id);
      if(!node||query&&!relevant.has(id)&&!(isFocus&&id===focusId))return;
      if(isFocus&&focusDisplayed.has(id))return;
      const cycle=path.has(id),b=bucket(id);
      const filtered=Object.fromEntries(Object.entries(b).map(([name,members])=>[name,
        query?members.filter(item=>relevant.has(item.id)):members]));
      const size=Object.values(filtered).reduce((sum,a)=>sum+a.length,0),hasChildren=!cycle&&size>0&&depth<maxDepth;
      const isOpen=hasChildren&&(!!query||show(key,entityDepth<2,revealAncestors.has(id))),pathNext=new Set(path);pathNext.add(id);
      if(!add({type:'entity',key,depth,entityDepth,entityId:id,kind:node.kind,title:node.title,
        relation,cycle,hasChildren,expanded:isOpen,multipleParents:(incoming.get(id)||0)>1,excluded,
        workAreas:workAreasByEntity.get(id)||[],
        groupMemberships:node.kind==='decision'?membershipsByDecision.get(id)||[]:[],
        selectionState:node.selectionState||null,
        resultState:node.result?.state||null,reviewRequired:!!node.review?.required,
        outsideParentIds:[...(outsideParents.get(id)||[])],supplemental:supplemental.get(id)||null}))return;
      if(isFocus)focusDisplayed.add(id);
      if(!isOpen)return;
      for(const [name,title,description] of subcategories){
        const members=filtered[name];if(!members.length)continue;
        // Type buckets are view-only. Their context-menu collapse action is
        // available on EVERY direct sibling, never only the first entity.
        // Collapsed state retains one synthetic, individually expandable row.
        const sectionKey=childKey(key,'section',name,name);
        const collapsible=members.length>1,open=!!query||show(sectionKey,true,
          members.some(item=>revealAncestors.has(item.id)))||!collapsible;
        if(!open){
          if(!add({type:'section',key:sectionKey,depth:depth+1,title,count:members.length,
            hasChildren:true,expanded:false,section:name,description}))return;
          continue;
        }
        for(const member of members){
          if(truncated)return;
          const first=rows.length,child=childKey(sectionKey,'entity',member.id,member.via);
          const memberships=(membershipsByDecision.get(member.id)||[]).filter(g=>g.parentId===id);
          const excluded=member.relation==='DECISION_MEMBER'&&memberships.length>0&&
            memberships.every(g=>g.excluded);
          entity(member.id,child,depth+1,entityDepth+1,pathNext,member.relation,excluded);
          if(collapsible&&!query&&rows[first]?.key===child){
            rows[first].sectionContext={key:sectionKey,title,count:members.length,
              section:name,expanded:true};
          }
        }
      }
    }
    if(isFocus&&focusParents.size){
      const parentList=[...focusParents.values()].sort((a,b)=>visible.get(a.id).title.localeCompare(visible.get(b.id).title,'ru')||a.id.localeCompare(b.id));
      const parentKey='focus:parents:'+focusId,parentOpen=show(parentKey,true);
      if(add({type:'section',key:parentKey,depth:0,title:'Родители',count:parentList.length,
        hasChildren:true,expanded:parentOpen,section:'parents',
        description:'Прямые структурные родители; ссылки на существующие R/D/Act'})){
        if(parentOpen)for(const {id,relations,groups} of parentList){
          const n=visible.get(id);
          if(!n||!add({type:'entity',key:'focus:parent:'+focusId+':'+id,depth:1,entityDepth:0,
            entityId:id,kind:n.kind,title:n.title,relation:'parent',parentRef:true,
            parentRelations:[...relations].sort(),parentGroups:[...groups].sort(),
            cycle:false,hasChildren:false,expanded:false,multipleParents:false,excluded:false,
            selectionState:n.selectionState||null,resultState:n.result?.state||null,
            reviewRequired:!!n.review?.required,outsideParentIds:[],supplemental:null,
            workAreas:workAreasByEntity.get(id)||[]}))break;
        }
      }
    }
    for(const id of roots){
      if(truncated)break;
      if(!query||relevant.has(id)||isFocus&&id===focusId)
        entity(id,'root:'+id,0,0,new Set());
    }
    const auxiliaryCount=[...extras.values()].reduce((a,v)=>a+v.length,0);
    // Process facts and other independent materials are also first-class
    // rows. They do not require Mat > Ctx > entity nesting when expanded.
    if(auxiliaryCount&&!truncated)for(const [kind,title] of
      [['context','Контекст процесса'],['info','Информация'],['evidence','Свидетельства'],['finding','Файндинги']]){
      const material=extras.get(kind);if(!material?.length||truncated)continue;
      const categoryKey=childKey('materials','materials',kind,kind);
      const collapsible=material.length>1,categoryOpen=!!query||!collapsible||show(categoryKey,true);
      if(!categoryOpen){
        if(!add({type:'section',key:categoryKey,depth:1,title,count:material.length,
          hasChildren:true,expanded:false,section:kind}))break;
        continue;
      }
      for(const node of material){
        const row={type:'entity',key:childKey(categoryKey,'entity',node.id,node.id),depth:1,
          entityDepth:0,entityId:node.id,kind:node.kind,title:node.title,
          relation:'material',cycle:false,hasChildren:false,expanded:false,
          selectionState:null,resultState:null,reviewRequired:!!node.review?.required,
          outsideParentIds:[],supplemental:null,
          workAreas:workAreasByEntity.get(node.id)||[]};
        if(collapsible&&!query)row.sectionContext={key:categoryKey,title,count:material.length,
          section:kind,expanded:true};
        if(!add(row))break;
      }
    }
    return {rows,roots,revealPaths:[...revealPaths],uniqueEntityCount:visible.size,structuralCount:structural.size,materialCount:auxiliaryCount,
      repeatedIds:[...counts].filter(([,v])=>v>1).map(([id])=>id),truncated,
      graphId:graph.id,identitySpace:graph.identitySpace,revision:graph.revision,viewKind:view.spec?.kind||'graph',viewOnly:true};
  }

  function contextTree(graph,options={}){
    const groups=graph.contextGroups||[],facts=(graph.objects||[]).filter(n=>n.kind==='context');
    const byId=new Map(groups.map(g=>[g.id,g])),closed=new Set(options.collapsedIds||[]),q=String(options.query||'').toLocaleLowerCase().trim(),rows=[];
    const path=id=>{const names=[],seen=new Set();while(id&&byId.has(id)&&!seen.has(id)){seen.add(id);const g=byId.get(id);names.unshift(g.title);id=g.parentId;}return names.join(' / ');};
    const sorted=a=>a.slice().sort((a,b)=>a.title.localeCompare(b.title,'ru')||a.id.localeCompare(b.id));
    function walk(parent,depth){
      for(const g of sorted(groups.filter(g=>g.parentId===parent))){
        const first=rows.length,open=!!q||!closed.has(g.id);rows.push({type:'group',id:g.id,title:g.title,depth,path:path(g.id),expanded:open});
        if(open)walk(g.id,depth+1);
        if(q&&rows.length===first+1&&!path(g.id).toLocaleLowerCase().includes(q))rows.pop();
      }
      for(const n of sorted(facts.filter(n=>(n.contextGroupId||null)===parent))){const location=path(n.contextGroupId);
        if(!q||[n.title,n.description,n.value,n.id,location].join(' ').toLocaleLowerCase().includes(q))rows.push({type:'context',id:n.id,title:n.title,depth,path:location});
      }
    }
    walk(null,0);return rows;
  }
  // View-only order projection from an already-authorized immutable snapshot.
  // No Cartesian product of cases; each fork contributes one displayed lane.
  function temporalPlan(plan,graph,completion={},spec={},packageId){
    if(!plan)return null;
    if(plan.schemaVersion!==3)throw Error('PLAN_VIEW_VERSION');
    const copy=x=>JSON.parse(JSON.stringify(x));
    const steps=new Map(plan.steps.map(s=>[s.id,s])),nodes=new Map([...graph.nodes,...graph.objects,...(graph.externalActions||[])].map(n=>[n.id,n]));
    const shown=spec.shownCases||{},known=new Set(plan.forks.map(f=>f.id)),order=[],markers=[],road=[],placements=[];
    if(Object.keys(shown).some(id=>!known.has(id)))throw Error('PLAN_VIEW_CASES');
    const after=new Map();for(const f of plan.forks){const key=f.afterStepId;if(!after.has(key))after.set(key,[]);after.get(key).push(f);}
    const forksAfter=anchor=>{for(const f of after.get(anchor)||[]){
      const id=shown[f.id]??f.cases[0].id,c=f.cases.find(c=>c.id===id);if(!c)throw Error('PLAN_VIEW_CASES');
      markers.push({...copy(f),shownCaseId:id});road.push({type:'fork',forkId:f.id});
      for(const sid of c.stepIds){order.push(sid);road.push({type:'placement',stepId:sid});}
      if(f.end)road.push({type:'join',forkId:f.id});
    }};
    forksAfter(null);for(const sid of plan.mainStepIds){order.push(sid);road.push({type:'placement',stepId:sid});forksAfter(sid);}
    const times=new Map();for(const t of plan.timeConstraints){if(!times.has(t.stepId))times.set(t.stepId,[]);times.get(t.stepId).push(t);}
    for(const sid of order){const step=steps.get(sid),rules=times.get(sid)||[],days=rules.map(t=>t.at.slice(0,10)),w=spec.planWindow||{};
      if(days.length&&((w.from&&days.every(d=>d<w.from))||(w.to&&days.every(d=>d>w.to))))continue;
      const available=step.ref.packageId===packageId,node=available?nodes.get(step.ref.nodeId):null;
      const reason=!available?'source-unavailable':graph.identitySpace!==step.ref.identitySpace?'identity-mismatch':!node?'missing-current-block':node.kind!==step.kind?'kind-mismatch':null;
      placements.push({step:copy(step),node:node?copy(node):null,positioned:true,bucket:reason?'unresolved':'future',reason,
        completion:available?copy(completion[step.ref.nodeId]||{}):{},timeConstraints:copy(rules)});
    }
    return {revision:plan.revision,placements,mainStepIds:copy(plan.mainStepIds),forks:markers,shownStepIds:order,road,currentGraphOnly:true,factsCreated:false};
  }
  return Object.freeze({project,addBranch,boundaries,decisionProject,decisionOutline,contextTree,temporalPlan});
});
