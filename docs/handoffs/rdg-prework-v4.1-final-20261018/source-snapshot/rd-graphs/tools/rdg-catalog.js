/* Folder-first catalog. Full graphs are entries rooted in semantic Requirements,
 * not graph file membership sets. Sources remain canonical graph.json files. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;else root.RDGCatalog=api;
})(globalThis,function(){
  'use strict';
  const path=p=>typeof p==='string'&&p.length>0&&!p.includes(String.fromCharCode(92))&&!/[?:]/.test(p)&&![...p].some(c=>c.charCodeAt(0)<32)&&p.split('/').every(x=>x&&x!=='.'&&x!=='..');
  function normalizeCatalog(manifest){
    if(!manifest||manifest.schemaVersion!==1||!Array.isArray(manifest.graphs)||!Array.isArray(manifest.fullGraphs))throw Error('Неверный каталог полных графов');
    const graphs=manifest.graphs.map(g=>{
      if(!g||!/^([a-z0-9][a-z0-9_-]*)$/.test(g.slug)||!path(g.file)||!g.file.endsWith('/graph.json'))throw Error('Недопустимый путь/slug графа');
      return {...g,kind:'graph',folder:g.folder??(g.group||'legacy'),presentation:g.presentation||{}};
    });
    const by=new Map(graphs.map(g=>[g.slug,g]));
    if(by.size!==graphs.length)throw Error('Дублирующийся граф');
    const folders=manifest.folders||[...new Set(graphs.map(g=>g.folder))].map(id=>({id,kind:'folder',folder:'',title:id,presentation:{}}));
    if(new Set(folders.map(f=>f.id)).size!==folders.length||folders.some(f=>!path(f.id)||f.folder!==''&&!path(f.folder)))throw Error('Неверные папки каталога');
    const fullGraphs=manifest.fullGraphs.map(entry=>{
      const g=by.get(entry.slug);
      if(!g||!entry.rootRequirementId||entry.rootRequirementId!==(g.rootRequirementId||g.graph?.rootRequirementId)||entry.identitySpace!==(g.identitySpace||g.graph?.identitySpace)||entry.file!==g.file||!path(entry.folder)&&entry.folder!=='')throw Error('Неверная точка входа полного графа: '+entry.slug);
      return {...entry,kind:'full-graph',presentation:entry.presentation||{}};
    });
    if(new Set(fullGraphs.map(x=>x.slug)).size!==fullGraphs.length)throw Error('Дублирующаяся точка входа');
    // Older standalone graphs without an identitySpace/rootRequirementId remain
    // accessible for editing. Do not pretend they have a proven full R closure.
    const fullSlugs=new Set(fullGraphs.map(e=>e.slug));
    const standalone=graphs.filter(g=>!fullSlugs.has(g.slug)&&(!g.identitySpace||!g.rootRequirementId))
      .map(g=>({...g,kind:'graph'}));
    return {graphs,folders,fullGraphs,standalone,relations:manifest.relations||[]};
  }
  function listFolder(catalog,folder='',query=''){
    const items=[...catalog.folders.filter(f=>f.folder===folder),
      ...catalog.fullGraphs.filter(g=>g.folder===folder),
      ...catalog.standalone.filter(g=>g.folder===folder)];
    const q=query.trim().toLowerCase();
    return items.filter(e=>!q||[e.title,e.slug,e.id,e.presentation?.description].join(' ').toLowerCase().includes(q))
      .sort((a,b)=>(a.kind==='folder'?0:1)-(b.kind==='folder'?0:1)||a.title.localeCompare(b.title));
  }
  function searchCatalog(catalog,query){
    const q=query.trim().toLowerCase();
    return [...catalog.folders,...catalog.fullGraphs,...catalog.standalone].filter(e=>[e.title,e.slug,e.id,e.presentation?.description].join(' ').toLowerCase().includes(q));
  }
  return Object.freeze({normalizeCatalog,listFolder,searchCatalog,validPath:path});
});
