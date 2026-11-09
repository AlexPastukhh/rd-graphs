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
    const allGraphs=manifest.graphs.map(g=>{
      if(!g||!/^([a-z0-9][a-z0-9_-]*)$/.test(g.slug)||!path(g.file)||!g.file.endsWith('/graph.json'))throw Error('Недопустимый путь/slug графа');
      return {...g,kind:'graph',folder:g.folder??(g.group||'legacy'),presentation:g.presentation||{}};
    });
    if(new Set(allGraphs.map(g=>g.slug)).size!==allGraphs.length)throw Error('Дублирующийся граф');
    const graphs=allGraphs.filter(g=>g.actionModel==='candidate-v6'&&
      g.catalogHidden!==true&&g.presentation?.archived!==true&&
      !g.presentation?.exampleOnly&&g.graph?.readOnly!==true&&g.graph?.exampleOnly!==true);
    const by=new Map(graphs.map(g=>[g.slug,g]));
    const sourceFolders=manifest.folders||[...new Set(graphs.map(g=>g.folder))].map(id=>({id,kind:'folder',folder:'',title:id,presentation:{}}));
    if(new Set(sourceFolders.map(f=>f.id)).size!==sourceFolders.length||sourceFolders.some(f=>!path(f.id)||f.folder!==''&&!path(f.folder)))throw Error('Неверные папки каталога');
    const usedFolders=new Set();
    for(const graph of graphs){let folder=graph.folder;while(folder){usedFolders.add(folder);folder=folder.includes('/')?folder.slice(0,folder.lastIndexOf('/')):'';}}
    const folders=sourceFolders.filter(f=>usedFolders.has(f.id));
    const fullGraphs=manifest.fullGraphs.map(entry=>{
      const g=by.get(entry.slug);
      if(!g)return null; // Archived legacy full graphs cannot be opened in the active application.
      if(!entry.rootRequirementId||entry.rootRequirementId!==(g.rootRequirementId||g.graph?.rootRequirementId)||entry.identitySpace!==(g.identitySpace||g.graph?.identitySpace)||entry.file!==g.file||!path(entry.folder)&&entry.folder!=='')throw Error('Неверная точка входа полного графа: '+entry.slug);
      return {...entry,kind:'full-graph',presentation:entry.presentation||{}};
    }).filter(Boolean);
    if(new Set(fullGraphs.map(x=>x.slug)).size!==fullGraphs.length)throw Error('Дублирующаяся точка входа');
    // Active standalone graph roots still need the candidate-v6 model.
    // Historical Decision/Option graphs remain on disk only for offline migration.
    const fullSlugs=new Set(fullGraphs.map(e=>e.slug));
    const standalone=graphs.filter(g=>!fullSlugs.has(g.slug)&&(!g.identitySpace||!g.rootRequirementId))
      .map(g=>({...g,kind:'graph'}));
    const activeSlugs=new Set(graphs.map(g=>g.slug));
    return {graphs,folders,fullGraphs,standalone,relations:(manifest.relations||[]).filter(r=>
      activeSlugs.has(r.from)&&activeSlugs.has(r.to))};
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
