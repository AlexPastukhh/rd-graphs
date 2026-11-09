/* Shared data/command layer; embedded into the userscript by build-rdg-layout.py. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.RDGLayoutCore=api;
})(globalThis,function(){
  'use strict';
  const clone=x=>JSON.parse(JSON.stringify(x));
  const object=x=>x&&typeof x==='object'&&!Array.isArray(x);
  const key=k=>typeof k==='string'&&k.length>0&&k.length<=500&&!['__proto__','prototype','constructor'].includes(k)&&!/[\x00-\x1f]/.test(k);
  const empty=()=>({schemaVersion:1,revision:0,layouts:{}});
  const occurrenceId=id=>key(id)&&id.startsWith('occ-');
  const validPosition=(id,p)=>key(id)&&object(p)&&Number.isFinite(p.x)&&Number.isFinite(p.y)&&Math.abs(p.x)<=1000000&&Math.abs(p.y)<=1000000;
  function validateOccurrences(records){
    if(!object(records)||Object.keys(records).length>2000)throw Error('LAYOUT_OCCURRENCES_LIMIT');
    for(const [id,record] of Object.entries(records)){
      if(!occurrenceId(id)||!object(record)||!validPosition(id,record)||!key(record.entityId)||
         Object.keys(record).some(k=>!['entityId','x','y','parentId','viaEdgeId','reverse'].includes(k))||
         (record.parentId!==undefined&&!key(record.parentId))||
         (record.viaEdgeId!==undefined&&!key(record.viaEdgeId))||
         (record.parentId===undefined)!==(record.viaEdgeId===undefined)||
         (record.reverse!==undefined&&record.reverse!==true)||
         (record.reverse===true&&record.parentId===undefined))
        throw Error('LAYOUT_OCCURRENCE_INVALID:'+id);
      if(record.parentId===id)throw Error('LAYOUT_OCCURRENCE_CYCLE:'+id);
    }
    for(const [id,record] of Object.entries(records)){
      const ancestors=new Set([id]);let parent=record.parentId;
      while(parent&&Object.hasOwn(records,parent)){
        if(ancestors.has(parent))throw Error('LAYOUT_OCCURRENCE_CYCLE:'+id);
        ancestors.add(parent);parent=records[parent].parentId;
      }
    }
  }

  function validate(doc){
    if(!object(doc)||doc.schemaVersion!==1||!Number.isSafeInteger(doc.revision)||doc.revision<0||!object(doc.layouts))throw Error('Некорректный документ расположений');
    for(const [graphKey,layout] of Object.entries(doc.layouts)){
      if(!key(graphKey)||!object(layout)||!object(layout.positions))throw Error('Некорректный ключ графа/расположение');
      if(Object.keys(layout.positions).length>2000)throw Error('Слишком много координат');
      for(const [id,p] of Object.entries(layout.positions)){
        if(!validPosition(id,p))throw Error('Некорректные координаты: '+id);
      }
      if(layout.occurrences!==undefined)validateOccurrences(layout.occurrences);
    }
    return clone(doc);
  }
  function graphKey(identitySpace,slug,rootRequirementId){
    if(!key(identitySpace)||!key(slug)||rootRequirementId!==undefined&&!key(rootRequirementId))throw Error('Для расположения нужны identitySpace, slug и допустимая корневая R');
    return JSON.stringify(rootRequirementId===undefined?[identitySpace,slug]:[identitySpace,slug,rootRequirementId]);
  }
  function apply(document,commands){
    const doc=validate(document);
    for(const cmd of Array.isArray(commands)?commands:[commands]){
      if(!object(cmd)||!key(cmd.graphKey))throw Error('Команда без graphKey');
      if(cmd.type==='set_positions'){
        if(!object(cmd.positions))throw Error('Нет positions');
        const current=doc.layouts[cmd.graphKey]?.positions||{};
        for(const id of Object.keys(cmd.positions))if(!key(id))throw Error('Некорректный ID');
        doc.layouts[cmd.graphKey]={...(doc.layouts[cmd.graphKey]||{}),positions:{...current,...clone(cmd.positions)}};
      }else if(cmd.type==='set_occurrences'){
        validateOccurrences(cmd.occurrences);
        const existing=doc.layouts[cmd.graphKey]||{positions:{}};
        doc.layouts[cmd.graphKey]={...existing,occurrences:clone(cmd.occurrences)};
      }else if(cmd.type==='clear_layout')delete doc.layouts[cmd.graphKey];
      else throw Error('Неизвестная команда расположения: '+cmd.type);
    }
    return validate(doc);
  }
  function commit(document,expectedRevision){
    const doc=validate(document);
    if(doc.revision!==expectedRevision)throw Error('Конфликт ревизии расположений');
    doc.revision++;return validate(doc);
  }
  function occurrenceKey(space,anchor,route,entity){
    if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(space))throw Error('LAYOUT_UUID_NAMESPACE');
    const bytes=[...space.replaceAll('-','').match(/../g).map(x=>parseInt(x,16)),...new TextEncoder().encode(JSON.stringify([anchor,route,entity]))];
    const bits=bytes.length*8;bytes.push(128);while(bytes.length%64!==56)bytes.push(0);
    for(let i=7;i>=0;i--)bytes.push(i>=4?0:(bits>>>i*8)&255);
    const rotate=(n,k)=>(n<<k)|(n>>>(32-k));let h=[0x67452301,0xefcdab89,0x98badcfe,0x10325476,0xc3d2e1f0];
    for(let offset=0;offset<bytes.length;offset+=64){
      const w=[];for(let i=0;i<16;i++)w[i]=(bytes[offset+i*4]<<24)|(bytes[offset+i*4+1]<<16)|(bytes[offset+i*4+2]<<8)|bytes[offset+i*4+3];
      for(let i=16;i<80;i++)w[i]=rotate(w[i-3]^w[i-8]^w[i-14]^w[i-16],1);
      let [a,b,c,d,e]=h;
      for(let i=0;i<80;i++){const f=i<20?(b&c)|(~b&d):i<40?b^c^d:i<60?(b&c)|(b&d)|(c&d):b^c^d;
        const k=i<20?0x5a827999:i<40?0x6ed9eba1:i<60?0x8f1bbcdc:0xca62c1d6;
        const t=(rotate(a,5)+f+e+k+w[i])|0;e=d;d=c;c=rotate(b,30);b=a;a=t;}
      h=h.map((v,i)=>(v+[a,b,c,d,e][i])|0);
    }
    const out=h.flatMap(v=>[v>>>24,(v>>>16)&255,(v>>>8)&255,v&255]).slice(0,16);out[6]=(out[6]&15)|80;out[8]=(out[8]&63)|128;
    const hex=out.map(v=>v.toString(16).padStart(2,'0')).join('');return 'occ-'+[hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join('-');
  }
  function remap(document,spec){
    const source=validate(document),result={...clone(source),revision:0,layouts:{}};
    if(!object(spec)||!key(spec.sourceSpace)||!key(spec.targetSpace)||!object(spec.viewMap)||!object(spec.entityMap)||!Array.isArray(spec.sourceIds)||!Array.isArray(spec.sourceSlugs))throw Error('LAYOUT_REMAP_SPEC');
    const known=new Set(),map=new Map(),copiedKeys=[],skippedKeys=[],skippedPositionIds=[];
    for(const id of spec.sourceIds){
      known.add(id);known.add('__canon__'+id);
      const mapped=spec.entityMap[id];
      if(mapped){map.set(id,mapped);map.set('__canon__'+id,'__canon__'+mapped);}
      for(const slug of spec.sourceSlugs){
        known.add(slug+'::'+id);known.add('__canon__'+slug+'::'+id);
        if(mapped){
          if(!key(spec.viewMap[slug]))throw Error('LAYOUT_OWNER_SLUG_UNMAPPED');
          map.set(slug+'::'+id,spec.viewMap[slug]+'::'+mapped);
          map.set('__canon__'+slug+'::'+id,'__canon__'+spec.viewMap[slug]+'::'+mapped);
        }
      }
    }
    for(const [oldKey,layout] of Object.entries(source.layouts)){
      let address;try{address=JSON.parse(oldKey);}catch{throw Error('LAYOUT_ADDRESS_FORMAT');}
      if(!Array.isArray(address)||![2,3].includes(address.length))throw Error('LAYOUT_ADDRESS_FORMAT');
      if(address[0]!==spec.sourceSpace){skippedKeys.push(oldKey);continue;}
      if(Object.hasOwn(spec.viewMap,address[1])&&spec.viewMap[address[1]]===null){skippedKeys.push(oldKey);continue;}
      if(!key(spec.viewMap[address[1]]))throw Error('LAYOUT_VIEW_UNMAPPED:'+address[1]);
      const root=address.length===3?spec.entityMap[address[2]]:undefined;
      if(address.length===3&&!root){skippedKeys.push(oldKey);continue;}
      const newKey=graphKey(spec.targetSpace,spec.viewMap[address[1]],root),positions={};
      if(Object.hasOwn(result.layouts,newKey))throw Error('LAYOUT_ADDRESS_COLLISION');
      for(const [id,position] of Object.entries(layout.positions)){
        if(!known.has(id))throw Error('LAYOUT_POSITION_UNMAPPED:'+id);
        if(map.has(id))positions[map.get(id)]=clone(position);else skippedPositionIds.push({graphKey:oldKey,id});
      }
      const occurrences={};
      for(const [id,o] of Object.entries(layout.occurrences||{})){
        if(!known.has(o.entityId))throw Error('LAYOUT_OCCURRENCE_UNMAPPED:'+o.entityId);
        const entity=spec.entityMap[o.entityId];
        if(!entity){skippedPositionIds.push({graphKey:oldKey,id});continue;}
        const copy=clone(o);copy.entityId=entity;
        if(copy.viaEdgeId){
          if(!object(spec.edgeMap)||!object(spec.edgeEndpoints))throw Error('LAYOUT_EDGE_MAP_REQUIRED');
          const edge=spec.edgeEndpoints[copy.viaEdgeId];
          if(!edge||(o.reverse===true?edge.from!==o.entityId:edge.to!==o.entityId))throw Error('LAYOUT_OCCURRENCE_EDGE:'+id);
          const parentEntity=layout.occurrences[copy.parentId]?.entityId||copy.parentId;
          if((o.reverse===true?edge.to!==parentEntity:edge.from!==parentEntity))throw Error('LAYOUT_OCCURRENCE_PARENT:'+id);
          if(!spec.edgeMap[copy.viaEdgeId]||!spec.entityMap[parentEntity]){
            skippedPositionIds.push({graphKey:oldKey,id});continue;
          }
          copy.viaEdgeId=spec.edgeMap[copy.viaEdgeId];
          if(!Object.hasOwn(layout.occurrences,copy.parentId))copy.parentId=spec.entityMap[parentEntity];
        }
        occurrences[id]=copy;
      }
      // Skip descendants whose parent was omitted by a selective copy.
      for(const id of Object.keys(occurrences)){
        let parent=occurrences[id].parentId;
        while(parent&&Object.hasOwn(layout.occurrences,parent)){
          if(!Object.hasOwn(occurrences,parent)){delete occurrences[id];skippedPositionIds.push({graphKey:oldKey,id});break;}
          parent=occurrences[parent].parentId;
        }
      }
      if(spec.profile==='rdg-decision-v1'){
        const idMap={};
        function rekey(id,active=new Set()){
          if(idMap[id])return idMap[id];if(active.has(id))throw Error('LAYOUT_OCCURRENCE_CYCLE');active.add(id);
          const original=layout.occurrences[id],copy=occurrences[id];if(!copy)return null;
          if(!original.parentId){idMap[id]=spec.targetSpace===spec.sourceSpace?id:occurrenceKey(spec.targetSpace,copy.entityId,[],id);return idMap[id];}
          const parentOriginal=layout.occurrences[original.parentId];let route=[],anchor;
          if(parentOriginal){rekey(original.parentId,active);const chain=[];let cursor=original.parentId;
            while(layout.occurrences[cursor]?.parentId){const v=layout.occurrences[cursor];chain.unshift([spec.edgeMap[v.viaEdgeId],v.reverse===true]);cursor=v.parentId;}
            anchor=spec.entityMap[layout.occurrences[cursor]?.entityId||cursor];route=chain;
          }else anchor=spec.entityMap[original.parentId];
          route.push([copy.viaEdgeId,copy.reverse===true]);idMap[id]=occurrenceKey(spec.targetSpace,anchor,route,copy.entityId);return idMap[id];
        }
        for(const id of Object.keys(occurrences))rekey(id);
        const renamed={};for(const [id,value] of Object.entries(occurrences)){if(layout.occurrences[value.parentId])value.parentId=idMap[value.parentId];renamed[idMap[id]]=value;}
        result.layouts[newKey]={positions,occurrences:renamed};
      }else result.layouts[newKey]={...clone(layout),positions,...(layout.occurrences?{occurrences}:{})};
      copiedKeys.push({from:oldKey,to:newKey});
    }
    const translation=spec.translation||{x:0,y:0};if(!object(translation)||!Number.isFinite(translation.x)||!Number.isFinite(translation.y))throw Error('LAYOUT_TRANSLATION');
    if(translation.x||translation.y)for(const layout of Object.values(result.layouts))for(const records of [layout.positions,layout.occurrences||{}])for(const p of Object.values(records)){p.x+=translation.x;p.y+=translation.y;}
    return {document:validate(result),report:{copiedKeys,skippedKeys,skippedPositionIds,...(spec.translation?{translation}:{} )}};
  }
  return Object.freeze({empty,validate,graphKey,apply,commit,remap,occurrenceKey});
});
