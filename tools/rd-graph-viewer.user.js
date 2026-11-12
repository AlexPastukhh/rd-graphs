// ==UserScript==
// @name         R-D Graph Viewer
// @namespace    rdg.local
// @version      2.7.0
// @description  Local Requirements-Decisions JSON graph viewer
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        GM_xmlhttpRequest
// @run-at       document-idle
// ==/UserScript==
// BEGIN GENERATED RDG DECISION UI
/* Decision desktop controller. Snapshots, commands and view state come from Application. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.RDGDecisionUI=api;})(globalThis,function(){
'use strict';
const clone=x=>JSON.parse(JSON.stringify(x)),uid=()=>globalThis.crypto.randomUUID();
function mount(container,transport,{document:doc=globalThis.document,onLegacyOpen=()=>{}}={}){
 let session=null,snapshot=null,catalog=null,registry=null,history=null,pending=null,busy=false,message='',error=false,form=null,packageDetail=null;
 let queue=Promise.resolve(),pendingDraft=null,draftTimer=null,flushingDraft=null,calendar=null,explorerNode=null,graphSvg=null;const targetSnapshots=new Map();let fitGraph=()=>{},persistGraph=()=>{};let closeStructureContextMenu=()=>{};
 // View-only process-wide bank. Facts stay in their existing Graph owner and
 // are never copied into Working Graphs, focus data or independent storage.
 let policyQuery='',policyFilter='all';let policyInstancesView=null;const dependencyInspectorReturns=new Map(),dependencyInspectorFilters=new Map(),invalidationViews=new Map(),invalidationReturns=new Map();
 let contextBank={packageId:null,open:false,selectedId:null,query:''};
 const isProcess=()=>['working','copy'].includes(snapshot?.package?.role);
 function legacyRecordGroupId(){let id='@legacy-records';while((snapshot?.graph?.contextGroups||[]).some(g=>g.id===id))id+='~';return id;}
 const processContexts=()=>snapshot?.graph?
  [...snapshot.graph.nodes,...snapshot.graph.objects].filter(n=>['context','evidence'].includes(n.kind)).map(n=>n.kind==='evidence'?{...n,value:n.claim,contextGroupId:legacyRecordGroupId()}:n):[];
 function contextBankGraph(){const facts=processContexts(),groups=[...(snapshot.graph.contextGroups||[])];if(facts.some(n=>n.kind==='evidence'))groups.push({id:legacyRecordGroupId(),title:'Подтверждения · прежние записи',parentId:null});return {...snapshot.graph,objects:facts.map(n=>({...n,kind:'context'})),contextGroups:groups};}
 const roadDefaults={centerGap:140,centerWidth:220,centerHeight:84,centerFont:11,centerMetaFont:9,sideWidth:125,sideHeight:26,sideFont:9,badgeSize:9};
 const roadRanges=[
  ['centerGap','Расстояние между центральными блоками',72,260,4],
  ['centerWidth','Ширина центрального блока',150,360,5],
  ['centerHeight','Высота центрального блока',58,190,4],
  ['centerFont','Шрифт основного текста',9,18,1],
  ['centerMetaFont','Шрифт подписи события',7,15,1],
  ['sideWidth','Ширина боковых блоков',80,260,5],
  ['sideHeight','Высота боковых блоков',20,100,2],
  ['sideFont','Шрифт боковых блоков',8,15,1],
  ['badgeSize','Размер индикатора Plan',6,18,1]
 ];
 let roadUi={screenId:null,open:null,drafts:{},months:{},anchors:{},errors:{},settings:{...roadDefaults},badgeMode:'dot',details:false};
 const isoToday=()=>{const now=new Date();return [now.getFullYear(),String(now.getMonth()+1).padStart(2,'0'),String(now.getDate()).padStart(2,'0')].join('-');};
 const addRoadDays=(day,offset)=>{const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+offset);return d.toISOString().slice(0,10);};
 const roadDefaultWindows=()=>{const today=isoToday();return {historyWindow:{from:addRoadDays(today,-9),to:today},planWindow:{from:today,to:addRoadDays(today,9)}};};
 const validRoadDay=value=>{let iso=String(value||'').trim();if(/^\d{2}\.\d{2}\.\d{4}$/.test(iso))iso=iso.slice(6)+'-'+iso.slice(3,5)+'-'+iso.slice(0,2);if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))return null;const d=new Date(iso+'T12:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===iso?iso:null;};
 const roadEditDay=day=>day?.slice(8,10)+'.'+day?.slice(5,7)+'.'+day?.slice(0,4);
 const roadDayLabel=day=>new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(day+'T12:00:00Z'));
 const roadWindow=(s,kind)=>{const w=s.spec[kind]||{},defaults=roadDefaultWindows()[kind];return {from:w.from||defaults.from,to:w.to||defaults.to};};
 function roadUiFor(s){if(roadUi.screenId!==s.id){roadUi={screenId:s.id,open:null,drafts:{},months:{},anchors:{},errors:{},settings:{...roadDefaults},badgeMode:'dot',details:false};}return roadUi;}

 const call=m=>transport.call(m),root=doc.createElement('section');root.className='rdg-decision';container.replaceChildren(root);
 const style=doc.createElement('style');style.textContent=`
 .rdg-decision{height:100%;min-height:490px;display:flex;flex-direction:column;font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;background:#0e1927;overflow:hidden;color:#e4edf6;position:relative}
 .rdg-decision *{box-sizing:border-box}.rdg-decision [hidden]{display:none!important}.rdg-decision button,.rdg-decision input,.rdg-decision select,.rdg-decision textarea{font:inherit;color:inherit;background:#1b3045;border:1px solid #30495f;border-radius:7px;padding:7px 10px}.rdg-decision button{cursor:pointer}.rdg-decision button:hover{background:#254058;border-color:#557b99}.rdg-decision button:focus-visible,.rdg-decision summary:focus-visible{outline:2px solid #83c9f4;outline-offset:-2px}.rdg-decision button:disabled{opacity:.4;cursor:default}.rdg-decision h2,.rdg-decision h3,.rdg-decision p{margin:0}.rdg-decision h2{font-size:16px}.rdg-decision h3{font-size:14px}.rdg-decision .rdg-row{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
 .rdg-decision .rdg-head{padding:4px 8px;min-height:42px;gap:8px;border-bottom:1px solid #30495f;background:#142235;flex-wrap:nowrap;flex:none}.rdg-decision .rdg-brand{font-weight:750;letter-spacing:.7px;color:#b5ddf7;font-size:14px;border-color:transparent;background:transparent;white-space:nowrap;padding:4px 6px}.rdg-decision .rdg-version{font-size:10px;color:#b8c9da;border-left:1px solid #30495f;padding-left:8px;white-space:nowrap}.rdg-decision .rdg-project{flex:1;min-width:0}.rdg-decision .rdg-project strong{font-size:14px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rdg-decision .rdg-project small{display:block;font-size:10px;color:#9eb2c5}.rdg-decision .rdg-head>button:last-child{font-size:11px;padding:4px 7px}
 .rdg-decision .rdg-tabs{display:flex;gap:4px;overflow-x:auto;overflow-y:hidden;flex-wrap:nowrap;padding:4px 8px 0;border-bottom:1px solid #36516b;height:46px;flex:none;background:#101d2d;scrollbar-width:none}.rdg-decision .rdg-tab{display:flex;min-width:0;flex:0 0 224px;border:1px solid #2b4258;border-bottom:0;border-radius:6px 6px 0 0;background:#15273a;padding-right:3px}.rdg-decision .rdg-tab[aria-selected=true]{border-color:#6599b9;background:#203c52;box-shadow:inset 0 2px #83c9f4}.rdg-decision .rdg-tab:focus-within{outline:2px solid #83c9f4;outline-offset:-2px}.rdg-decision .rdg-tab button:first-child{border:0;background:none;flex:1;min-width:0;overflow:hidden;text-align:left;padding:5px 9px}.rdg-decision .rdg-tab b,.rdg-decision .rdg-tab small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rdg-decision .rdg-tab b{font-size:11px;font-weight:550}.rdg-decision .rdg-tab small{font-size:9px;color:#8faabd}.rdg-decision .rdg-tab button:last-child{border:0;background:none;width:24px;height:24px;padding:0;flex:none;align-self:center;border-radius:4px;color:#91adc3}.rdg-decision .rdg-tab button:last-child:hover{background:#405a70;color:#edf5fc}.rdg-decision .rdg-tab button:last-child:disabled{visibility:hidden}.rdg-decision .rdg-tabs>button{border:0;background:none;align-self:center;font-size:20px;padding:0;width:28px;height:28px;flex:none}
 .rdg-decision .rdg-tools{padding:5px 8px;border-bottom:1px solid #334d63;min-height:39px;gap:4px;background:#17283b;flex:none}.rdg-decision .rdg-tools button,.rdg-decision .rdg-tools select,.rdg-decision .rdg-tools summary{font-size:11px;padding:5px 8px}.rdg-decision .rdg-tools>button,.rdg-decision .rdg-tools>.rdg-menu>summary{padding-inline:6px}.rdg-decision .rdg-tools>label select{max-width:168px}.rdg-decision .rdg-tools label{font-size:11px;margin:0;display:flex;align-items:center;gap:4px}.rdg-decision .rdg-spacer{flex:1}.rdg-decision .rdg-menu{position:relative}.rdg-decision summary{cursor:pointer;list-style:none}.rdg-decision summary::-webkit-details-marker{display:none}.rdg-decision .rdg-menu>summary{padding:5px 8px;font-size:11px;border:1px solid #30495f;border-radius:6px;background:#1b3045}.rdg-decision .rdg-actions>summary{background:#287da6;border-color:#4a9ac0;color:white}.rdg-decision .rdg-menu-content{position:absolute;top:calc(100% + 7px);right:0;width:270px;background:#1a2d42;border:1px solid #58718a;border-radius:9px;padding:7px;box-shadow:0 12px 30px #0006;z-index:20}.rdg-decision .rdg-menu-content button{display:block;width:100%;text-align:left;white-space:normal;border:0;background:transparent;font-size:12px;padding:9px 10px}.rdg-decision .rdg-menu-content button:hover{background:#29455d}.rdg-decision .rdg-menu-content label{display:block;padding:8px;font-size:12px}
 .rdg-decision .rdg-status{margin:0;padding:3px 8px;color:#b8c9da;min-height:21px;font-size:10px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;flex:none;border-bottom:1px solid #334d63;background:#101b29}.rdg-decision .rdg-error{color:#ffb89f}.rdg-decision .rdg-scope{display:flex;align-items:center;gap:9px;padding:7px 12px;background:#162d3c;border-bottom:1px solid #3f665d;flex:none}.rdg-decision .rdg-scope>div{flex:1;min-width:0}.rdg-decision .rdg-scope small{font-size:10px;color:#9ac8b3;margin-right:12px}.rdg-decision .rdg-scope b{font-size:12px}.rdg-decision .rdg-scope button{font-size:11px;padding:5px 8px}.rdg-decision .rdg-scope.rdg-ready{background:#252b3d;border-color:#555c7b}.rdg-decision .rdg-scope.rdg-ready small{color:#b7b0d0}
 .rdg-decision .rdg-body{display:flex;flex:1;min-height:0;position:relative;overflow:hidden}.rdg-decision .rdg-workspace{display:flex;flex:1;min-width:260px;min-height:0;overflow:hidden}.rdg-decision .rdg-canvas{flex:1;min-width:0;min-height:0;position:relative;overflow:hidden;background-color:#101d2b;background-image:radial-gradient(#304458 1px,transparent 1px);background-size:22px 22px}.rdg-decision svg.rdg-graph{width:100%;height:100%;min-height:0;display:block;touch-action:none;border-radius:0;background:transparent}.rdg-decision .rdg-graph text{fill:#e4edf6;pointer-events:none;font-family:system-ui,-apple-system,Segoe UI,sans-serif}.rdg-decision .rdg-node{cursor:grab;user-select:none}.rdg-decision .rdg-node:focus{outline:none}.rdg-decision .rdg-node:focus .rdg-node-border{stroke:#c0e7ff;stroke-width:2}.rdg-decision .rdg-node:hover .rdg-node-border{stroke:#b9def5}.rdg-decision .rdg-canvas-head{position:absolute;top:12px;left:15px;right:15px;display:flex;align-items:center;gap:8px;z-index:1;pointer-events:none}.rdg-decision .rdg-crumb{background:#142438eb;border:1px solid #30495f;border-radius:6px;padding:6px 10px;font-size:12px}.rdg-decision .rdg-view-trail{pointer-events:auto;display:flex;gap:4px;max-width:60%;overflow:hidden}.rdg-decision .rdg-view-trail button{font-size:11px;white-space:nowrap;max-width:145px;text-overflow:ellipsis;overflow:hidden;padding:5px 7px;background:#192f45dd;border:1px solid #47627a;border-radius:5px}.rdg-decision .rdg-selection{margin-left:auto;background:#142438e8;padding:5px 9px;border-radius:5px;font-size:11px;color:#9eb2c5}.rdg-decision .rdg-zoom{position:absolute;right:15px;bottom:14px;display:flex;flex-wrap:wrap;justify-content:flex-end;max-width:calc(100% - 30px);gap:4px;padding:4px;background:#142438ee;border:1px solid #30495f;border-radius:8px}.rdg-decision .rdg-zoom button{background:transparent;border-color:transparent;padding:4px 9px;font-size:12px}.rdg-decision .rdg-legend{position:absolute;left:15px;bottom:61px;display:flex;gap:12px;flex-wrap:wrap;font-size:10px;color:#9eb2c5;background:#101d2bdb;padding:5px 8px;pointer-events:none}.rdg-decision .rdg-legend i{display:inline-block;width:8px;height:8px;border-radius:3px;margin-right:5px}
 .rdg-decision .rdg-plan-root{margin:8px 0;padding-top:6px;border-top:1px solid #44647c}.rdg-decision .rdg-plan-root>button{display:block;width:100%;text-align:left;background:var(--rdg-node-fill,#23374a);border-color:var(--rdg-node-line,#44647c);font-size:10px;padding:5px;white-space:normal;overflow-wrap:anywhere}.rdg-decision .rdg-plan-root>small{display:block;font-size:9px;margin:3px 0}.rdg-decision .rdg-plan-root>.rdg-plan-group{font-size:9px;background:#23374a}.rdg-decision .rdg-plan-moment{margin:5px 0} .rdg-decision .rdg-road{display:flex;flex-direction:column;flex:none;min-width:300px;max-width:60%;border-left:1px solid #44647c;background:#132235;overflow:hidden}.rdg-decision .rdg-road-head{padding:10px 12px;border-bottom:1px solid #30495f;flex:none}.rdg-decision .rdg-road-head h3{font-size:14px}.rdg-decision .rdg-road-head p{font-size:10px;color:#9eb2c5;margin:4px 0 7px}.rdg-decision .rdg-road-head button{font-size:10px;padding:4px 6px}.rdg-decision .rdg-road-head label{font-size:10px;color:#9eb2c5;margin:6px 0 0}.rdg-decision .rdg-road-scroll{overflow:auto;flex:1;min-height:0;padding:0 10px 18px;scroll-padding-top:16px}.rdg-decision .rdg-road-part{padding:0;position:relative}.rdg-decision .rdg-road-section{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;padding:12px 0 7px;border-bottom:1px solid #30495f;font-size:12px}.rdg-decision .rdg-road-section>label{display:flex;align-items:center;gap:6px;flex:1 0 100%;font-size:10px;min-width:0}.rdg-decision .rdg-road-section>label select{flex:1;min-width:0;padding:4px 6px;font-size:10px}.rdg-decision .rdg-road-section small{font-size:9px;color:#8fa8bb}.rdg-decision .rdg-road-row{position:relative;padding:22px 0;display:grid;grid-template-columns:minmax(0,1fr) minmax(145px,220px) minmax(0,1fr);gap:8px;align-items:center;min-height:112px}.rdg-decision .rdg-road-row:before{content:'';position:absolute;top:0;bottom:0;left:50%;width:2px;background:#385e74}.rdg-decision .rdg-road-card{grid-column:2;position:relative;z-index:1;border:1px solid var(--rdg-node-line,#92b9c8);border-radius:7px;background:var(--rdg-node-fill,#253c4a);padding:9px;font-size:11px;min-width:0;overflow-wrap:anywhere}.rdg-decision .rdg-road-card>button:first-of-type{display:block;width:100%;background:transparent;border:0;text-align:left;font-size:11px;font-weight:650;padding:3px 0;line-height:1.35}.rdg-decision .rdg-road-card>small{display:block;font-size:9px;color:var(--rdg-node-line,#92b9c8);line-height:1.3}.rdg-decision .rdg-road-card p{font-size:10px;color:#bfd0df;margin:5px 0}.rdg-decision .rdg-road-card details{margin-top:6px;font-size:9px;color:#9eb2c5}.rdg-decision .rdg-road-card details button{font-size:10px;padding:4px 0;background:none;border:0;text-align:left;display:block}.rdg-decision .rdg-road-card select{display:block;width:100%;font-size:10px;padding:5px;margin:5px 0}.rdg-decision .rdg-road-card label{font-size:10px}.rdg-decision .rdg-road-side{font-size:9px;min-width:0;position:relative;z-index:1}.rdg-decision .rdg-road-side>.rdg-road-source{display:block;font-size:9px;max-width:100%;padding:4px 6px;margin:4px 0;border:1px solid var(--rdg-node-line,#44647c);border-radius:5px;background:var(--rdg-node-fill,#253c4a);color:#e7edf5;text-transform:none;overflow-wrap:anywhere}.rdg-decision .rdg-road-side>span{display:block;font-size:8px;color:#89a3b7;margin-bottom:4px;text-transform:uppercase}.rdg-decision .rdg-road-side button{font-size:9px;display:block;max-width:100%;padding:4px 6px;margin:4px 0;border-color:var(--rdg-node-line,#48657e);background:var(--rdg-node-fill,#1b3045);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rdg-decision .rdg-now{display:flex;align-items:center;justify-content:center;gap:8px;padding:11px 0;background:#101f30;border-top:1px solid #4b647c;border-bottom:1px solid #4b647c;font-size:11px;color:#dcecf8}.rdg-decision .rdg-now i{width:9px;height:9px;border-radius:50%;background:#83c9f4}.rdg-decision .rdg-split{width:7px;cursor:col-resize;background:#1d3448;border-left:1px solid #38536a;border-right:1px solid #0b1621;flex:none}.rdg-decision .rdg-split:hover,.rdg-split:focus-visible{background:#5a94b5}.rdg-decision .rdg-inspector-split{touch-action:none}
 .rdg-decision .rdg-card{padding:10px;border:1px solid #30495f;border-radius:7px;margin:10px 0;background:#182c40;overflow-wrap:anywhere}.rdg-decision .rdg-muted{color:#9eb2c5;font-size:11px}.rdg-decision .rdg-chip{font-size:11px;padding:3px 7px;border-radius:13px;margin:3px}
 .rdg-decision .rdg-explorer{position:absolute;top:0;bottom:0;left:0;width:350px;max-width:85vw;border-right:1px solid #45596c;border-radius:0 10px 10px 0;background:#0f1b29;display:flex;flex-direction:column;min-height:0;z-index:30;box-shadow:18px 0 42px #0009;overflow:hidden}.rdg-decision .rdg-explorer-top{border-bottom:1px solid #30495f;background:#17283b}.rdg-decision .rdg-explorer-close{display:flex;align-items:center;width:100%;text-align:left;border:0;border-bottom:1px solid #42546a;border-radius:0;background:transparent;padding:14px 15px 12px}.rdg-decision .rdg-explorer-close small{display:block;font-size:10px;letter-spacing:1.6px;color:#86b6d2}.rdg-decision .rdg-explorer-close strong{display:block;font-size:15px;letter-spacing:.8px}.rdg-decision .rdg-explorer-close>span:last-child{margin-left:auto;color:#92abc0;font-size:20px}.rdg-decision .rdg-explorer-tabs{display:flex;gap:4px;padding:6px 10px;background:#142538}.rdg-decision .rdg-explorer-tabs button{flex:1;font-size:12px;padding:7px;border-color:transparent;background:transparent}.rdg-decision .rdg-explorer-tabs button[aria-selected=true]{border-color:#648fac;background:#24445c}.rdg-decision .rdg-explorer-top>label{display:block;padding:6px 10px;font-size:10px;color:#9eb2c5}.rdg-decision .rdg-explorer input:not([type=checkbox]){width:100%;padding:9px;margin-top:5px;background:#102235}.rdg-decision .rdg-explorer-list{overflow:auto;overflow-x:hidden;padding:10px;flex:1;min-height:0}.rdg-decision .rdg-explorer-list button{font-size:11px}.rdg-decision .rdg-tree>summary{display:flex;align-items:center;gap:6px;background:#1b3349;border-radius:5px;padding:7px 8px;font-size:12px;font-weight:650;margin:2px 0}.rdg-decision .rdg-tree>summary:before{content:'▸';color:#8eb2ca;font-size:11px}.rdg-decision .rdg-tree[open]>summary:before{content:'▾'}.rdg-decision .rdg-tree>summary small{margin-left:auto;color:#7896ad;font-size:9px;font-weight:400}.rdg-decision .rdg-tree-content{margin-left:13px;padding-left:8px;border-left:1px solid #2d465d;min-width:0}.rdg-decision .rdg-tree-row{display:flex;gap:8px;align-items:center;width:100%;text-align:left;border:1px solid transparent;background:transparent;padding:7px 8px;border-radius:5px;margin:2px 0;min-width:0}.rdg-decision .rdg-tree-row[aria-current=page]{background:#244a66;border-color:#4e85a7}.rdg-decision .rdg-tree-row>span:first-child{color:#8cb7d0;flex:none}.rdg-decision .rdg-tree-copy{flex:1;min-width:0}.rdg-decision .rdg-tree-copy b,.rdg-decision .rdg-tree-copy small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rdg-decision .rdg-tree-copy b{font-size:12px;font-weight:650}.rdg-decision .rdg-tree-copy small{font-size:9px;color:#8fa8bb}.rdg-decision .rdg-tree-add{width:100%;text-align:left;display:block;background:none;border:0;padding:7px 8px;color:#8faec4}.rdg-decision .rdg-tree-packages{border-top:1px solid #2c4259;margin:5px 0}.rdg-decision .rdg-tree-packages>small{font-size:9px;color:#91a8c0}.rdg-decision .rdg-tree-packages button{display:block;background:none;border:0;font-size:10px;padding:5px;text-align:left;width:100%}.rdg-decision .rdg-explorer-note{font-size:10px;color:#829aae;margin:12px 3px;line-height:1.5}
 .rdg-decision .rdg-question-workspace{display:flex;flex:1;min-width:0;min-height:0;background:#101d2d;overflow:hidden}
 .rdg-decision .rdg-question-list{width:340px;max-width:43%;min-width:220px;border-right:1px solid #385570;display:flex;flex-direction:column;min-height:0}
 .rdg-decision .rdg-question-list-head{padding:12px;border-bottom:1px solid #334d64;display:flex;flex-direction:column;gap:8px}
 .rdg-decision .rdg-question-list-head input{width:100%;font-size:12px}
 .rdg-decision .rdg-question-scroll{overflow:auto;flex:1;min-height:0;padding:9px}
 .rdg-decision .rdg-question-group{font-size:11px;color:#acc9db;margin:12px 4px 6px}
 .rdg-decision .rdg-question-row{display:block;width:100%;margin:4px 0;padding:10px;text-align:left;background:#192d40;border:1px solid #38566f;border-radius:6px;white-space:normal;overflow-wrap:anywhere}
 .rdg-decision .rdg-question-row[aria-current=true]{border-color:#86c8ec;background:#27495e}
 .rdg-decision .rdg-question-row b{display:block;font-size:12px}
 .rdg-decision .rdg-question-row small{display:block;margin-top:5px;color:#adc1d1;font-size:10px}
 .rdg-decision .rdg-question-detail{overflow:auto;flex:1;min-width:0;padding:18px 23px}
 .rdg-decision .rdg-question-detail h3{font-size:17px;margin-bottom:6px}
 .rdg-decision .rdg-question-detail h4{font-size:13px;margin:17px 0 7px}
 .rdg-decision .rdg-question-detail p{margin:7px 0;white-space:pre-wrap;overflow-wrap:anywhere}
 .rdg-decision .rdg-question-detail .rdg-card{margin:9px 0}
 .rdg-decision .rdg-question-detail .rdg-question-ref{display:inline-block;margin:3px 6px 3px 0;padding:5px 8px;max-width:100%;white-space:normal;text-align:left;font-size:11px}
 .rdg-decision .rdg-question-related{margin:7px 0}
 .rdg-decision .rdg-question-inspector-link{padding:8px 9px;border:1px solid #38566f;border-radius:6px;margin:7px 0}
 .rdg-decision .rdg-question-inspector-link button{display:block;width:100%;text-align:left;font-size:11px;white-space:normal}
 .rdg-decision .rdg-question-inspector-link small{font-size:10px;color:#a9bfd0}
 @media(max-width:700px){.rdg-decision .rdg-question-workspace{flex-direction:column}.rdg-decision .rdg-question-list{width:100%;max-width:none;min-height:180px;max-height:40%}.rdg-decision .rdg-question-detail{padding:12px}}
 .rdg-decision .rdg-context-bank-toggle[aria-expanded=true]{background:#284a63;border-color:#80b8d8;color:#f3faff}
 .rdg-decision .rdg-context-bank{position:absolute;top:128px;bottom:24px;left:8px;width:min(460px,calc(100% - 16px));z-index:29;background:#102033;border:1px solid #57809b;border-radius:9px;box-shadow:12px 12px 34px #000a;display:flex;flex-direction:column;min-height:220px;overflow:hidden}
 .rdg-decision .rdg-context-bank-head{padding:12px 13px;border-bottom:1px solid #3b5c73;background:#192e42;display:flex;align-items:center;gap:8px}
 .rdg-decision .rdg-context-bank-head strong{font-size:14px;flex:1}
 .rdg-decision .rdg-context-bank-head button{font-size:11px;padding:4px 7px}
 .rdg-decision .rdg-context-bank-desc{padding:9px 13px;color:#9ebdd0;font-size:11px;line-height:1.5}
 .rdg-decision .rdg-context-bank-search{display:flex;gap:7px;padding:5px 12px 9px}
 .rdg-decision .rdg-context-bank-search input{width:100%;min-width:0;font-size:12px}
 .rdg-decision .rdg-context-bank-search button{flex:none;min-width:78px;white-space:nowrap;font-size:11px;padding:6px 8px}
 .rdg-decision .rdg-context-bank-scroll{flex:1;min-height:0;overflow:auto;padding:3px 12px 15px}
 .rdg-decision .rdg-context-bank-item{width:100%;display:flex;align-items:flex-start;gap:9px;text-align:left;padding:9px;margin:5px 0;background:#243447;border-left:3px solid #91a7bd}
 .rdg-decision .rdg-context-bank-item[aria-pressed=true]{background:#2a455d;border-color:#a4d7f2}
 .rdg-decision .rdg-context-bank-item .rdg-context-bank-copy{flex:1;min-width:0;overflow-wrap:anywhere}
 .rdg-decision .rdg-context-bank-item b,.rdg-decision .rdg-context-bank-item small{display:block}
 .rdg-decision .rdg-context-bank-item small{color:#a5bed0;font-size:10px;margin-top:3px}
 .rdg-decision .rdg-context-bank-entry{margin:12px 0;border:1px solid #4a6880;border-radius:8px;padding:12px;background:#192e41;overflow-wrap:anywhere}
 .rdg-decision .rdg-context-bank-entry h3{margin:0 0 8px;font-size:13px}
 .rdg-decision .rdg-context-bank-entry p{font-size:12px;white-space:pre-wrap;margin:7px 0}
 .rdg-decision .rdg-context-bank-entry .rdg-row{margin-top:10px}
 .rdg-decision .rdg-context-bank-entry button{font-size:11px}
 .rdg-decision .rdg-context-bank-entry small{color:#a6bdce;font-size:10px}
 .rdg-decision .rdg-inspector{position:relative;flex:none;width:340px;max-width:calc(100% - 80px);height:100%;overflow:auto;background:#142437;border-left:1px solid #30495f;padding:15px;z-index:2}.rdg-decision .rdg-inspector p{white-space:pre-wrap;margin:10px 0;font-size:12px}.rdg-decision .rdg-inspector>button{font-size:11px;padding:6px 8px;margin:3px 2px;max-width:100%;text-align:left}.rdg-decision .rdg-inspector h3{margin:12px 0 7px}.rdg-decision .rdg-modal-shade{position:absolute;inset:0;display:flex;align-items:flex-start;justify-content:center;padding:28px;background:#050e18bb;z-index:40;overflow:auto}.rdg-decision .rdg-modal{background:#142437;border:1px solid #58718a;border-radius:9px;width:650px;max-width:96%;padding:20px;box-shadow:0 18px 70px #0008}.rdg-decision .rdg-modal label{display:block;margin:10px 0;font-size:12px;color:#9eb2c5}.rdg-decision .rdg-modal label input:not([type=checkbox]),.rdg-decision .rdg-modal label textarea,.rdg-decision .rdg-modal label select{display:block;width:100%;margin-top:5px;padding:9px;background:#0f1f2f;color:#e4edf6}.rdg-decision .rdg-modal textarea{min-height:80px}.rdg-decision .rdg-modal pre{max-height:250px;overflow:auto;white-space:pre-wrap;font-size:12px}.rdg-decision .rdg-modal p{font-size:12px;margin:10px 0}.rdg-decision .rdg-calendar{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;margin:10px 0}.rdg-decision .rdg-calendar button{padding:7px 3px}.rdg-decision .rdg-calendar .rdg-in-range{background:#396787}.rdg-decision .rdg-rule{border:1px solid #48657e;padding:9px;margin:10px 0;border-radius:5px}.rdg-decision .rdg-footer{display:flex;align-items:center;gap:12px;padding:4px 9px;font-size:10px;color:#9eb2c5;background:#101b29;border-top:1px solid #30495f;flex:none;min-height:24px}.rdg-decision .rdg-footer span:last-child{margin-left:auto}
 @media(max-width:1100px){.rdg-decision .rdg-version{display:none}.rdg-decision .rdg-tools{gap:3px}.rdg-decision .rdg-tools button,.rdg-decision .rdg-tools summary{padding:5px 6px}.rdg-decision .rdg-tools>label{max-width:180px}.rdg-decision .rdg-tools>label select{max-width:130px}.rdg-decision .rdg-selection{display:none}}
 `;
 style.textContent+=`
 .rdg-decision .rdg-road{position:relative}
 .rdg-decision .rdg-road-head-actions{display:flex;gap:4px;align-items:center;flex-wrap:wrap}
 .rdg-decision .rdg-road-head-actions button{font-size:10px;padding:4px 6px}
 .rdg-decision .rdg-road-flyout{position:absolute;z-index:14;top:83px;right:7px;width:min(370px,calc(100% - 14px));max-height:calc(100% - 94px);overflow:auto;background:#13263a;border:1px solid #5a7890;border-radius:8px;box-shadow:0 14px 34px #0009;padding:11px}
 .rdg-decision .rdg-road-flyout h4{margin:0 0 8px;font-size:12px}
 .rdg-decision .rdg-road-flyout .rdg-road-fly-head{display:flex;gap:7px;align-items:center;justify-content:space-between}
 .rdg-decision .rdg-road-flyout fieldset{border:1px solid #30495f;border-radius:6px;margin:9px 0;padding:9px;min-width:0}
 .rdg-decision .rdg-road-flyout legend{font-size:11px;padding:0 5px}
 .rdg-decision .rdg-road-date-inputs{display:grid;grid-template-columns:1fr 1fr;gap:7px}
 .rdg-decision .rdg-road-flyout label{display:block;font-size:10px;color:#aabed0;margin:6px 0}
 .rdg-decision .rdg-road-flyout label input:not([type=checkbox]):not([type=range]),.rdg-decision .rdg-road-flyout select{width:100%;min-width:0;padding:6px;background:#0f1f2f;font-size:11px}
 .rdg-decision .rdg-road-flyout input[aria-invalid=true]{border-color:#e2a294}
 .rdg-decision .rdg-road-flyout .rdg-calendar{margin:6px 0;gap:2px}
 .rdg-decision .rdg-road-flyout .rdg-calendar button{font-size:10px;padding:4px 0}
 .rdg-decision .rdg-road-flyout .rdg-calendar button[aria-pressed=true]{background:#24465e}
 .rdg-decision .rdg-road-flyout .rdg-calendar button.rdg-range-edge{background:#366482;border-color:#9dc8e3}
 .rdg-decision .rdg-road-flyout .rdg-calendar button:disabled{opacity:.22}
 .rdg-decision .rdg-road-flyout .rdg-road-setting{display:grid;gap:4px;padding:3px 0}
 .rdg-decision .rdg-road-flyout .rdg-road-setting>span{display:flex;gap:6px;justify-content:space-between}
 .rdg-decision .rdg-road-flyout input[type=range]{width:100%;padding:0;accent-color:#73b5d3}
 .rdg-decision .rdg-road-flyout .rdg-road-error{color:#ffb89f;font-size:10px}
 .rdg-decision .rdg-road-row{padding:10px 0;min-height:var(--road-center-gap,112px);grid-template-columns:minmax(0,1fr) minmax(130px,var(--road-center-width,220px)) minmax(0,1fr)}
 .rdg-decision .rdg-road-card{min-height:var(--road-center-height,84px);font-size:var(--road-center-font,11px)}
 .rdg-decision .rdg-road-card>button:first-of-type{font-size:var(--road-center-font,11px)}
 .rdg-decision .rdg-road-card>small{font-size:var(--road-center-meta-font,9px)}
 .rdg-decision .rdg-road-side button{max-width:var(--road-side-width,125px);min-height:var(--road-side-height,26px);font-size:var(--road-side-font,9px)}
 .rdg-decision .rdg-road[data-detail=full] .rdg-road-side button{white-space:normal;text-overflow:clip;overflow-wrap:anywhere}
 .rdg-decision .rdg-road-indicator{display:inline-block;vertical-align:middle;width:var(--road-badge-size,9px);height:var(--road-badge-size,9px);margin-right:5px;border:1px solid currentColor;border-radius:50%}
 .rdg-decision .rdg-road-indicator.planned{color:#c9c0ff;background:#8b79d6}.rdg-decision .rdg-road-indicator.unplanned{color:#ffd0c7;background:#d87878}
 .rdg-decision .rdg-road-label.planned{color:#c9c0ff}.rdg-decision .rdg-road-label.unplanned{color:#ffd0c7}
 .rdg-decision .rdg-road-window-note{font-size:10px;color:#a8bdcf;margin:8px 0}
`;
 style.textContent+=`

 .rdg-decision .rdg-markdown-view{overflow:auto;display:block;padding:18px 22px;line-height:1.5;min-width:0}
 .rdg-decision .rdg-markdown-part{max-width:88ch;overflow-wrap:anywhere;margin-bottom:14px}
 .rdg-decision .rdg-markdown-part h1,.rdg-decision .rdg-markdown-part h2,.rdg-decision .rdg-markdown-part h3,.rdg-decision .rdg-markdown-part h4{margin:6px 0}
 .rdg-decision .rdg-markdown-part p{margin:3px 0}
 .rdg-decision .rdg-markdown-quote{white-space:pre-wrap;margin:8px 0;padding-inline-start:12px;border-inline-start:2px solid #69839e}
 .rdg-decision .rdg-markdown-part details{margin-top:6px;padding-inline-start:8px}
 .rdg-decision .rdg-search-panel{padding:8px 12px;border-bottom:1px solid #49667d}
 .rdg-decision .rdg-search-results{max-height:270px;overflow:auto}
 .rdg-decision .rdg-search-hit{padding:5px 0;border-bottom:1px solid #49667d}
 .rdg-decision .rdg-search-hit small{margin-inline-start:10px}
 .rdg-decision .rdg-search-hit p{margin:2px 0;overflow-wrap:anywhere}
 .rdg-decision .rdg-presentation-modes{display:flex;gap:2px;align-items:center;padding:2px;border:1px solid #49667d;border-radius:7px;background:#102236;white-space:nowrap}.rdg-decision .rdg-presentation-modes button{border:0;background:transparent;color:#aec6d8;padding:4px 6px}.rdg-decision .rdg-presentation-modes button[aria-pressed=true]{color:#f2f9ff;background:#286286;box-shadow:inset 0 0 0 1px #65a4ca}.rdg-decision .rdg-structure-canvas{display:flex;flex-direction:column;background:#101b2a;background-image:none}.rdg-decision .rdg-outline-head{display:flex;flex:none;flex-wrap:wrap;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid #334d64;background:#14263a}.rdg-decision .rdg-outline-head strong{font-size:13px;color:#dfedf8}.rdg-decision .rdg-outline-head small{font-size:10px;color:#96b1c6}.rdg-decision .rdg-outline-head label{display:flex;align-items:center;gap:6px;margin-left:auto;font-size:10px;color:#99b8cb}.rdg-decision .rdg-outline-head input{width:180px;padding:5px 9px;font-size:11px}.rdg-decision .rdg-outline-head button{font-size:11px;padding:4px 9px}.rdg-decision .rdg-outline-scroll{flex:1;overflow:auto;min-height:0;padding:12px 17px 28px;scrollbar-gutter:stable;overscroll-behavior-x:contain}.rdg-decision .rdg-outline-tree{width:100%;min-width:0;max-width:none;list-style:none}.rdg-decision .rdg-outline-row{display:flex;align-items:center;gap:7px;min-height:38px;box-sizing:border-box;min-width:420px;width:calc(100% - (8px + var(--outline-depth,0)*24px));max-width:none;margin:2px 0 2px calc(8px + var(--outline-depth,0)*24px);padding:3px 10px;border-radius:6px;border:1px solid transparent;background:#17293a}.rdg-decision .rdg-outline-row:hover{background:#1e384c}.rdg-decision .rdg-outline-row[aria-current=true]{border-color:#65a4ca;background:#21465e}.rdg-decision .rdg-outline-row[data-outline-type=section],.rdg-decision .rdg-outline-row[data-outline-type=materials]{background:#192f43;color:#c0d8e9;font-weight:650;border-bottom:1px solid #37566c;margin-top:7px}.rdg-decision .rdg-outline-row[data-outline-type=group]{background:#302d45;border-left:3px solid #a99bc8}.rdg-decision .rdg-outline-row[data-excluded=true]{opacity:.65}.rdg-decision .rdg-outline-toggle{width:26px;min-width:26px;height:25px;padding:1px 4px;background:transparent;border-color:transparent;color:#b4cddd;font-size:13px}.rdg-decision .rdg-outline-toggle-spacer{width:26px;min-width:26px;text-align:center;color:#5e7b93}.rdg-decision .rdg-outline-kind{font-weight:800;min-width:19px;font-size:15px;text-align:center;color:#b7dbe9}.rdg-decision .rdg-outline-row[data-kind=decision] .rdg-outline-kind{color:#ebc991}.rdg-decision .rdg-outline-row[data-kind=action] .rdg-outline-kind{color:#9bd7c0}.rdg-decision .rdg-outline-row[data-kind=canon] .rdg-outline-kind{color:#b7a9ec}.rdg-decision .rdg-outline-body{flex:1;min-width:0;display:flex;flex-direction:column;align-items:stretch;gap:1px;border:0;background:transparent;text-align:left;padding:3px 0}.rdg-decision .rdg-outline-body:hover{background:transparent;border-color:transparent}.rdg-decision .rdg-outline-title{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rdg-decision .rdg-outline-meta{font-size:10px;color:#95b2c6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rdg-decision .rdg-outline-aux{font-size:10px;color:#94bdd0;white-space:nowrap;flex:none}.rdg-decision .rdg-outline-focus{font-size:10px;padding:4px 8px;flex:none;background:#1a334a}.rdg-decision .rdg-outline-empty{padding:28px;color:#9ab3c7;font-size:13px}.rdg-decision .rdg-outline-note{flex:none;color:#95afc5;font-size:10px;padding:6px 18px;border-top:1px solid #334d64;background:#122235}
`;
 style.textContent+=`.rdg-decision .rdg-explorer-home{position:relative;inset:auto;width:100%;max-width:none;flex:1;border:0;border-radius:0;box-shadow:none}.rdg-decision .rdg-explorer-home .rdg-explorer-close{padding:14px 24px}.rdg-decision .rdg-explorer-home .rdg-explorer-tabs{padding-left:24px}.rdg-decision .rdg-explorer-home .rdg-explorer-tabs button{flex:none;min-width:150px}.rdg-decision .rdg-explorer-home .rdg-explorer-top>label{padding:10px 24px;max-width:760px}.rdg-decision .rdg-explorer-home .rdg-explorer-list{padding:16px 24px}.rdg-decision[data-mode=explorer]>.rdg-status{padding:10px 24px;flex:none}`;
 style.textContent+=`
 .rdg-decision .rdg-outline-row[data-kind=requirement]{background:#193e52;border-left:3px solid #73b5d3}
 .rdg-decision .rdg-outline-row[data-kind=decision]{background:#3d3930;border-left:3px solid #d6b77e}
 .rdg-decision .rdg-outline-row[data-kind=action]{background:#24483f;border-left:3px solid #8bd0b8}
 .rdg-decision .rdg-outline-row[data-kind=canon]{background:#302d49;border-left:3px solid #a99bc8}
 .rdg-decision .rdg-outline-row[data-kind=context]{background:#263446;border-left:3px solid #91a7bd}
 .rdg-decision .rdg-outline-row[data-kind=info],.rdg-decision .rdg-outline-row[data-kind=evidence]{background:#253c4a;border-left:3px solid #92b9c8}
 .rdg-decision .rdg-outline-row[data-outline-section=requirements] .rdg-outline-kind{color:#73b5d3}
 .rdg-decision .rdg-outline-row[data-outline-section=groups] .rdg-outline-kind,.rdg-decision .rdg-outline-row[data-outline-section=decisions] .rdg-outline-kind{color:#d6b77e}
 .rdg-decision .rdg-outline-row[data-outline-section=actions] .rdg-outline-kind{color:#8bd0b8}
 .rdg-decision .rdg-outline-area-markers{display:flex;gap:2px;align-items:center;flex:none;margin-left:4px}
 .rdg-decision .rdg-outline-area-markers i{display:block;width:4px;height:17px;border-radius:2px;box-shadow:0 0 0 1px #0d1a25}
 .rdg-decision .rdg-outline-row[data-kind]:hover{filter:brightness(1.12)}
 .rdg-decision .rdg-outline-kind{display:inline-flex;align-items:center;justify-content:center;min-width:34px;padding:3px 5px;border-radius:5px;background:#0d2235;border:1px solid #3c5b70;font-size:11px;line-height:1.5;letter-spacing:.1px;white-space:nowrap}
 .rdg-decision .rdg-outline-row[data-outline-type=group] .rdg-outline-kind{background:#27253b;border-color:#8c7dbb}
 .rdg-decision .rdg-outline-row{position:relative}
 .rdg-decision .rdg-outline-row[data-outline-type=section][aria-expanded=false]{border:1px dashed #4f6c82;background:#172c40}
 .rdg-decision .rdg-outline-row[data-outline-type=section][aria-expanded=false] .rdg-outline-meta{color:#a9c5d9}
 /* A collapsed type envelope borrows its entity hue, with a darker fill and
    dashed outline so it cannot be mistaken for an actual Graph object. Parents
    are semantic references and deliberately keep their separate style. */
 .rdg-decision .rdg-outline-row[data-outline-type=section][data-outline-section=requirements][aria-expanded=false]{background:#142f40;border:1px dashed #517e98;border-left:3px solid #73b5d3}
 .rdg-decision .rdg-outline-row[data-outline-type=section][data-outline-section=decisions][aria-expanded=false]{background:#302d26;border:1px dashed #847451;border-left:3px solid #d6b77e}
 .rdg-decision .rdg-outline-row[data-outline-type=section][data-outline-section=actions][aria-expanded=false]{background:#1c3730;border:1px dashed #567f71;border-left:3px solid #8bd0b8}
 .rdg-decision .rdg-outline-row[data-outline-type=section][data-outline-section=context][aria-expanded=false]{background:#1e2b39;border:1px dashed #64778c;border-left:3px solid #91a7bd}
 .rdg-decision .rdg-outline-row[data-outline-type=section][data-outline-section=info][aria-expanded=false],
 .rdg-decision .rdg-outline-row[data-outline-type=section][data-outline-section=evidence][aria-expanded=false]{background:#1d303d;border:1px dashed #5b8191;border-left:3px solid #92b9c8}
 .rdg-decision .rdg-outline-row[data-outline-type=section][data-outline-section=groups][aria-expanded=false]{background:#262338;border:1px dashed #786c98;border-left:3px solid #a99bc8}
 .rdg-decision .rdg-outline-row[data-outline-type=section][data-outline-section=groups][aria-expanded=false] .rdg-outline-kind{color:#c2b5e6}
 .rdg-decision .rdg-outline-row[data-outline-type=section][aria-expanded=false]:not([data-outline-section=parents]):hover{filter:brightness(1.12)}
 .rdg-decision .rdg-outline-row[data-outline-section=parents]{background:#1c364a;border-left:3px solid #6aa9d3;margin-top:5px}
 .rdg-decision .rdg-outline-row[data-parent-ref=true]{background:#142c3c;border-left:3px solid #608daf}
 .rdg-decision .rdg-outline-row[data-parent-ref=true] .rdg-outline-kind{min-width:49px;background:#10283a;border-color:#608daf;color:#bfe4f6;font-size:10px}
 .rdg-decision .rdg-outline-row[data-focus-root=true]{border:1px solid #79b9d8;box-shadow:inset 3px 0 #9dd7ef}
 .rdg-decision .rdg-outline-row[data-kind][aria-current=true]{box-shadow:inset 0 0 0 1px #a8d8f3,0 0 0 1px #65a4ca}
 /* Real Decision Group memberships are small, read-only property chips above
    the same canonical Decision. They never create a synthetic DG tree row. */
 /* Group chips and Decision share the full-width/depth geometry of R/Act.
    Its own child disclosure remains inside the amber card. Sibling type groups
    are collapsed via the per-row context menu, not a protruding control. */
 .rdg-decision .rdg-outline-row[data-kind=decision][data-group-tags=true]{
  background:transparent;border-color:transparent;
  margin-top:11px;margin-bottom:2px;padding:0;
 }
 .rdg-decision .rdg-outline-row[data-kind=decision][data-group-tags=true]:hover{background:transparent}
 .rdg-decision .rdg-outline-decision-wrap{display:flex;flex:1 1 auto;width:100%;min-width:0;flex-direction:column;gap:4px}
 .rdg-decision .rdg-outline-group-tags{display:flex;flex-wrap:wrap;align-items:flex-start;gap:5px;min-width:0}
 .rdg-decision .rdg-outline-decision-content{display:flex;align-items:center;gap:7px;min-width:0;min-height:38px;flex:1;padding:4px 7px;border:1px solid #d6b77e;border-left:3px solid #d6b77e;border-radius:5px;background:#3d3930}

 /* The menu is anchored to the pointer, not a tree row, so horizontal/vertical
    scroll containers cannot clip it. It owns only view actions, never Graph. */
 .rdg-decision .rdg-outline-context-menu{position:fixed;z-index:1200;width:280px;max-width:calc(100vw - 16px);max-height:calc(100vh - 16px);overflow-y:auto;border:1px solid #658ba6;border-radius:9px;background:#172d42;box-shadow:0 14px 38px #0009;padding:6px;outline:none}
 .rdg-decision .rdg-outline-context-title{font-size:11px;font-weight:650;color:#c1d7e7;padding:7px 9px 9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;border-bottom:1px solid #354e63;margin-bottom:4px}
 .rdg-decision .rdg-outline-context-menu [role=menuitem]{display:block;text-align:left;width:100%;padding:9px 10px;font-size:11px;border:0;border-radius:5px;background:transparent;white-space:normal}
 .rdg-decision .rdg-outline-context-menu [role=menuitem]:hover,.rdg-decision .rdg-outline-context-menu [role=menuitem]:focus-visible{background:#285575}
 .rdg-decision .rdg-outline-context-hint{font-size:10px;color:#94adbf;padding:6px 9px}
 .rdg-decision .rdg-outline-group-caption{display:inline-flex;align-items:center;max-width:100%;width:auto;flex:none;padding:3px 7px;border:1px solid var(--rdg-group-color);border-radius:5px;background:color-mix(in srgb,var(--rdg-group-color) 9%,#142636);color:var(--rdg-group-color);font-size:10px;font-weight:650;line-height:1.45;white-space:normal;text-align:left;overflow-wrap:anywhere}
 .rdg-decision .rdg-outline-group-caption:hover,.rdg-decision .rdg-outline-group-caption:focus-visible{background:color-mix(in srgb,var(--rdg-group-color) 16%,#142636);border-color:var(--rdg-group-color);color:var(--rdg-group-color);text-decoration:underline}
 .rdg-decision .rdg-tree-area-line{display:flex;align-items:center;gap:3px;min-width:0;position:relative}
 .rdg-decision .rdg-tree-area-line>.rdg-tree-row{flex:1;min-width:0}
 .rdg-decision .rdg-tree-area-line>.rdg-tree-row>span:first-child{font-size:10px}
 .rdg-decision .rdg-tree-area-menu{position:relative;flex:none}
 .rdg-decision .rdg-tree-area-menu>summary{list-style:none;cursor:pointer;border:1px solid #30495f;border-radius:5px;background:#172b3f;color:#b8cfe0;padding:4px 7px;font-size:12px}
 .rdg-decision .rdg-tree-area-menu>summary::-webkit-details-marker{display:none}
 .rdg-decision .rdg-tree-area-menu[open]>summary{border-color:#78a9c7;background:#24445c}
 .rdg-decision .rdg-tree-area-options{position:absolute;z-index:35;right:0;top:calc(100% + 5px);width:166px;padding:5px;background:#172b3f;border:1px solid #58718a;border-radius:7px;box-shadow:0 10px 26px #0009}
 .rdg-decision .rdg-tree-area-options button{display:flex;align-items:center;gap:8px;width:100%;border:0;background:transparent;padding:6px;text-align:left;font-size:10px}
 .rdg-decision .rdg-tree-area-options button:hover,.rdg-decision .rdg-tree-area-options button[aria-pressed=true]{background:#29465e}
 .rdg-decision .rdg-tree-area-swatch{width:11px;height:11px;border-radius:3px;display:inline-block;flex:none;border:1px solid #d6e5ef66}
 .rdg-decision .rdg-road-category{display:inline-block;margin:2px 4px 3px 0;padding:2px 5px;border-radius:4px;background:#172d41;color:#a9c4d8;font-size:8px;font-weight:700;letter-spacing:.35px;text-transform:uppercase}
 .rdg-decision .rdg-road-category[data-event-category=РЕЗУЛЬТАТ]{background:#20473e;color:#9bd7c0}
 .rdg-decision .rdg-road-category[data-event-category=ВЫБОР]{background:#473d2c;color:#e4c68f}
 .rdg-decision .rdg-road-category[data-event-category=ОРГАНИЗАЦИЯ]{background:#332e4b;color:#b7a9ec}
 .rdg-decision .rdg-road-category[data-event-category=СОСТОЯНИЕ]{background:#3d3030;color:#e6aaa0}
 .rdg-decision .rdg-road-headline{display:block;margin:4px 0;font-size:12px;line-height:1.35}
 .rdg-decision .rdg-road-change-list{margin:7px 0;padding-top:5px;border-top:1px solid #ffffff22}
 .rdg-decision .rdg-road-change-list>small{display:block;color:#9fc0d2;font-size:9px;margin-bottom:3px}
 .rdg-decision .rdg-road-change-list button{display:inline-block;max-width:100%;margin:2px 3px 2px 0;padding:4px 6px;font-size:9px;white-space:normal;text-align:left}
 `;
 style.textContent+=`

 .rdg-decision .rdg-road{container-name:rdg-road;container-type:inline-size}
 .rdg-decision .rdg-road-side-left{grid-column:1;grid-row:1}
 .rdg-decision .rdg-road-side-right{grid-column:3;grid-row:1}
 .rdg-decision .rdg-road-row[data-event-id]{min-height:var(--road-center-gap,112px);height:auto;margin:10px 0;padding:12px;gap:10px;align-items:start;border:1px solid #3a5266;border-radius:11px;background:#17293bbf;grid-template-columns:minmax(0,1fr) minmax(145px,var(--road-center-width,220px)) minmax(0,1fr)}
 .rdg-decision .rdg-road-row[data-event-id]:before{display:none}
 .rdg-decision .rdg-road-row[data-event-id] .rdg-road-card{grid-column:2;grid-row:1;min-height:var(--road-center-height,84px);max-width:100%}
 .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side{min-width:0;align-self:stretch}
 .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side>span{font-size:9px;line-height:1.4;color:#a8c2d5;white-space:normal;overflow-wrap:anywhere}
 .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side button{width:100%;max-width:100%;white-space:normal;overflow:visible;text-overflow:clip;overflow-wrap:anywhere;text-align:left;line-height:1.3;padding:7px 8px}
 .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side .rdg-road-show-more{background:#19344b;border-style:dashed;color:#b8d9eb}
 .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side .rdg-road-missing{display:block;margin:5px 0;padding:5px 6px;border:1px dashed #718ba4;border-radius:5px;color:#aebfcf;overflow-wrap:anywhere}
 .rdg-decision .rdg-road-event-relation{margin:7px 0;padding:7px;border-radius:5px;background:#13283b;border:1px solid #385872;overflow-wrap:anywhere;font-size:10px;line-height:1.45}
 .rdg-decision .rdg-road-event-relation strong{display:block;color:#cde9fa;font-size:10px}
 .rdg-decision .rdg-road-event-relation small{display:block;color:#99b7cb;font-size:9px}
 .rdg-decision .rdg-road-event-hint{font-size:9px;color:#a7c6d9;margin:6px 0;overflow-wrap:anywhere}
 @container rdg-road (max-width:690px){
  .rdg-decision .rdg-road-row[data-event-id]{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
  .rdg-decision .rdg-road-row[data-event-id] .rdg-road-card{grid-column:1/-1;grid-row:1}
  .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side-left{grid-column:1;grid-row:2}
  .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side-right{grid-column:2;grid-row:2}
 }
 @container rdg-road (max-width:345px){
  .rdg-decision .rdg-road-row[data-event-id]{grid-template-columns:minmax(0,1fr)}
  .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side-left{grid-column:1;grid-row:2}
  .rdg-decision .rdg-road-row[data-event-id] .rdg-road-side-right{grid-column:1;grid-row:3}
 }
`;
 style.textContent+=`
 .rdg-decision .rdg-inspector-tabs{display:flex;gap:5px;margin:12px 0 9px;padding-bottom:6px;border-bottom:1px solid #3a5369}
 .rdg-decision .rdg-inspector-tab{flex:1;min-width:0;font-size:11px;padding:7px 6px;text-align:center;background:#1b3045}
 .rdg-decision .rdg-inspector-tab[aria-selected=true]{background:#25465e;border-color:#79b3d3;box-shadow:inset 0 -2px #83c9f4;color:#f2f9ff}
 .rdg-decision .rdg-inspector-tabpanel{padding:1px 0 8px}
 .rdg-decision .rdg-entity-reference{display:flex;align-items:center;gap:8px;width:100%;min-height:39px;margin:5px 0;padding:7px 9px;text-align:left;white-space:normal;overflow-wrap:anywhere;background:var(--rdg-node-fill,#253c4a);border-color:var(--rdg-node-line,#92b9c8)}
 .rdg-decision .rdg-entity-reference-kind{flex:none;min-width:34px;padding:2px 5px;border:1px solid var(--rdg-node-line,#92b9c8);border-radius:4px;background:#0d1b29;color:var(--rdg-node-line,#92b9c8);font-size:10px;font-weight:800;text-align:center}
 .rdg-decision .rdg-entity-reference-title{flex:1;min-width:0;overflow-wrap:anywhere}
 .rdg-decision .rdg-entity-reference-open{flex:none;color:var(--rdg-node-line,#92b9c8)}
 .rdg-decision .rdg-canon-card{margin:8px 0;padding:10px;border:1px solid #8f82b9;border-left:3px solid #a99bc8;border-radius:7px;background:#28283e}
 .rdg-decision .rdg-canon-card h4{margin:0 0 7px;font-size:12px;color:#e5ddff}
 .rdg-decision .rdg-canon-card p{margin:7px 0;white-space:pre-wrap;overflow-wrap:anywhere}
 .rdg-decision .rdg-canon-guidance{color:#e1e8f2;font-size:12px;line-height:1.5}
 .rdg-decision .rdg-canon-info-list{margin-top:10px;padding-top:7px;border-top:1px solid #ffffff22}
 .rdg-decision .rdg-canon-info-list>small{display:block;margin-bottom:5px;color:#aebfd0;font-size:10px}
 .rdg-decision .rdg-canon-info-row{margin:5px 0;padding:5px;border:1px solid #3d5065;border-radius:6px;background:#1a2b40}
 .rdg-decision .rdg-canon-info-row p{margin:5px 4px;font-size:11px;color:#c5d3df}
 .rdg-decision .rdg-canon-actions{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}
 .rdg-decision .rdg-canon-actions button{font-size:10px;padding:5px 7px}
`;
 style.textContent+=`
 .rdg-decision .rdg-dependencies{display:flex;flex-direction:column;min-height:0}
 .rdg-decision .rdg-dependencies .rdg-road-head p{line-height:1.5}
 .rdg-decision .rdg-dependency-scroll{padding:11px 12px 22px;min-height:0;overflow:auto;flex:1}
 .rdg-decision .rdg-dependency-summary{font-size:11px;color:#a7bfd1;line-height:1.5;margin:0 0 12px}
 .rdg-decision .rdg-dependency-list{display:flex;flex-direction:column;gap:10px}
 .rdg-decision .rdg-dependency-card{border:1px solid #60788b;border-left:3px solid #baa787;border-radius:8px;background:#203346;padding:11px 12px;min-width:0}
 .rdg-decision .rdg-dependency-card h4{margin:3px 0 5px;font-size:12px;line-height:1.4;overflow-wrap:anywhere}
 .rdg-decision .rdg-dependency-card small{font-size:10px;color:#aabecf}
 .rdg-decision .rdg-dependency-kind{display:inline-block;background:#273f52;color:#e4ceb0;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:650;margin-right:7px}
 .rdg-decision .rdg-dependency-cause{margin:9px 0 0;padding:8px 9px;border:1px solid #445b71;border-radius:6px;background:#15293b;font-size:11px;line-height:1.5}
 .rdg-decision .rdg-dependency-cause>small{display:block;font-size:9px;color:#9eb4c7;margin:0 0 4px}
 .rdg-decision .rdg-dependency-cause p{margin:4px 0;color:#c5d7e3;overflow-wrap:anywhere;font-size:10px}
 .rdg-decision .rdg-dependency-cause button{display:block;text-align:left;white-space:normal;overflow-wrap:anywhere;margin:5px 0 1px;font-size:10px;background:#203d50;border-color:#53738a}
 .rdg-decision .rdg-dependency-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
 .rdg-decision .rdg-dependency-actions button{font-size:11px;padding:5px 8px}
 .rdg-decision .rdg-dependency-confirm{background:#24546a;border-color:#6696b0}
 .rdg-decision .rdg-dependency-warning{font-size:10px;color:#b8cada;border-left:2px solid #8c99a6;padding:7px 10px;margin:11px 0;background:#1a2a3c}
 .rdg-decision .rdg-dependency-empty{border:1px solid #426379;padding:13px;border-radius:7px;background:#1b3344;color:#c5d9e6;font-size:11px}
 .rdg-decision .rdg-dependency-toggle[aria-pressed=true]{border-color:#a0a3bb;background:#353a54;color:#f0e9fa}
 `;
 style.textContent+=`
 .rdg-decision .rdg-context-dependency-row{display:flex;flex-direction:column;gap:5px;margin:7px 0;padding:9px;border:1px solid #4b6580;border-radius:7px;background:#172e41;min-width:0}
 .rdg-decision .rdg-context-dependency-row small{font-size:10px;line-height:1.4;color:#afc5d6;overflow-wrap:anywhere}
 .rdg-decision .rdg-context-dependency-row button:not(.rdg-entity-reference){font-size:10px;align-self:flex-start;padding:4px 8px}
 .rdg-decision .rdg-inspector-dependencies{margin:12px 0;border-top:1px solid #45576f;padding-top:6px}
 .rdg-decision .rdg-dependency-watch{border:1px solid #4c607a;border-radius:7px;padding:9px 12px;margin:10px 0;display:flex;flex-direction:column;gap:6px}
 .rdg-decision .rdg-dependency-watch legend{color:#c6dbea;font-size:11px;padding:0 5px}
 .rdg-decision .rdg-dependency-watch label{display:flex;align-items:center;gap:8px;font-size:11px;line-height:1.4}
 .rdg-decision .rdg-dependency-watch input{flex:none}
 .rdg-decision .rdg-dependencies-inactive,.rdg-decision .rdg-dependencies-cancelled{margin:13px 0;padding:8px 10px;border:1px solid #516279;border-radius:7px;background:#172b3b}
 .rdg-decision .rdg-dependencies-inactive>summary,.rdg-decision .rdg-dependencies-cancelled>summary{cursor:pointer;color:#bed6e6;font-size:12px;font-weight:650;padding:4px 0}
 .rdg-decision .rdg-dependencies-inactive .rdg-dependency-list{margin:11px 0 3px}
 .rdg-decision .rdg-dependency-watch label{min-width:0}
 `;
 style.textContent+=`
 .rdg-decision .rdg-dependency-workspace{display:flex;flex:1;min-width:0;min-height:0;flex-direction:column;background:#102031}
 .rdg-decision .rdg-policy-header{display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:16px 26px;border-bottom:1px solid #385169}
 .rdg-decision .rdg-policy-header h2{font-size:19px;color:#e5f0f8;margin:0}
 .rdg-decision .rdg-policy-header p{font-size:11px;color:#9fbaca;margin:5px 0 0}
 .rdg-decision .rdg-policy-tabs{display:flex;gap:6px;margin-left:auto}
 .rdg-decision .rdg-policy-tabs button{padding:8px 17px;font-size:12px}
 .rdg-decision .rdg-policy-tabs button[aria-selected=true]{background:#285672;border-color:#87bddf;color:#fff}
 .rdg-decision .rdg-policy-scroll{min-height:0;overflow:auto;flex:1;padding:18px 26px 40px}
 .rdg-decision .rdg-policy-grid{display:grid;grid-template-columns:minmax(250px,320px) minmax(0,1fr);gap:16px;max-width:1600px;margin:0 auto}
 .rdg-decision .rdg-policy-nav,.rdg-decision .rdg-policy-main{background:#182c3e;border:1px solid #446077;border-radius:10px;padding:15px;min-width:0}
 .rdg-decision .rdg-policy-nav h3,.rdg-decision .rdg-policy-main h3{font-size:13px;color:#e0eff6;margin:14px 0 9px}
 .rdg-decision .rdg-policy-entry{width:100%;display:block;padding:9px 11px;margin:6px 0;text-align:left;background:#193348;border:1px solid #385a72;white-space:normal}
 .rdg-decision .rdg-policy-entry[aria-current=true]{background:#295271;border-color:#92c6e2}
 .rdg-decision .rdg-policy-entry b,.rdg-decision .rdg-policy-entry small{display:block}
 .rdg-decision .rdg-policy-entry small{color:#a5c2d3;font-size:10px;margin-top:5px}
 .rdg-decision .rdg-policy-actions{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:10px 0}
 .rdg-decision .rdg-policy-actions button{padding:7px 9px;font-size:11px}
 .rdg-decision .rdg-policy-rule,.rdg-decision .rdg-policy-binding{border:1px solid #466780;background:#13283a;border-radius:8px;padding:11px;margin:9px 0;overflow-wrap:anywhere}
 .rdg-decision .rdg-policy-rule p,.rdg-decision .rdg-policy-binding p{font-size:11px;color:#bed1df;line-height:1.5}
 .rdg-decision .rdg-policy-schema{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:15px;border:1px dashed #587c92;background:#102537;border-radius:9px;margin:10px 0}
 .rdg-decision .rdg-policy-symbol{padding:12px;border-radius:6px;border:1px solid var(--rdg-node-line,#96b2c4);background:var(--rdg-node-fill,#294253);font-size:12px;min-width:130px}
 .rdg-decision .rdg-policy-symbol b,.rdg-decision .rdg-policy-symbol small{display:block}
 .rdg-decision .rdg-policy-symbol small{font-size:10px;margin-top:4px;color:#c5dae8}
 .rdg-decision .rdg-policy-arrow{color:#a5c7da;font-size:12px}
 .rdg-decision .rdg-policy-empty{padding:15px;border:1px dashed #5b7288;border-radius:7px;background:#1c3547;color:#c0d1df;font-size:12px}
 .rdg-decision .rdg-policy-chip{display:inline-block;border:1px solid #55778c;background:#1c3a4f;color:#b7d5e7;padding:4px 8px;margin:4px;border-radius:5px;font-size:10px}
 .rdg-decision .rdg-dependency-filters{position:sticky;top:0;z-index:3;background:#142437;border-bottom:1px solid #40566c;padding:8px 0 12px;margin-bottom:12px}
 .rdg-decision .rdg-dependency-filter-row+.rdg-dependency-filter-row{margin-top:12px}
 .rdg-decision .rdg-dependency-filter-row h4{font-size:12px;margin:0 0 6px;color:#d9e7f2}
 .rdg-decision .rdg-dependency-filter-buttons{display:flex;flex-wrap:wrap;gap:5px}
 .rdg-decision button.rdg-dependency-filter{display:inline-flex;align-items:center;gap:6px;border-radius:999px;border:1px solid #486278;background:#192c40;padding:5px 8px;font-size:10px;line-height:1.4;font-weight:500;white-space:nowrap}
 .rdg-decision button.rdg-dependency-filter:hover{background:#28425d;border-color:#7da4c0}
 .rdg-decision button.rdg-dependency-filter[aria-pressed=true]{background:#234bb6;border-color:#80b3ff;color:#fff}
 .rdg-decision button.rdg-dependency-filter[data-dependency-filter=participation]{border-style:dashed}
 .rdg-decision .rdg-dependency-filter-count{color:#b8cce0;min-width:1.1em;text-align:right}
 .rdg-decision .rdg-dependency-results>h3{font-size:12px;margin:12px 0 7px}
 .rdg-decision .rdg-policy-instances{width:920px;max-width:96%;overflow-wrap:anywhere}
 .rdg-decision .rdg-instance-header,.rdg-decision .rdg-instance-selected{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
 .rdg-decision .rdg-instance-header{justify-content:space-between}
 .rdg-decision .rdg-instance-header h2{font-size:15px;margin:0}
 .rdg-decision .rdg-instance-description{line-height:1.6;margin:10px 0 12px}
 .rdg-decision .rdg-instance-selected{padding-bottom:14px;border-bottom:1px solid #35526a}
 .rdg-decision .rdg-instance-selected>button{margin-left:auto}
 .rdg-decision .rdg-instance-section h3{font-size:13px;margin:18px 0 10px}
 .rdg-decision .rdg-instance-table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px}
 .rdg-decision .rdg-instance-table th{text-align:left;font-size:11px;font-weight:500;color:#9fb8cd;padding:0 10px 8px}
 .rdg-decision .rdg-instance-table th:nth-child(2){width:36%}
 .rdg-decision .rdg-instance-table td{vertical-align:top;border-top:1px solid #30495f;padding:10px;line-height:1.55}
 .rdg-decision .rdg-instance-table td p{margin:3px 0}
 .rdg-decision .rdg-instance-table tbody[data-instance-active=false]{color:#aab4bc}
 .rdg-decision .rdg-instance-disabled{color:#d3b98e;background:#332f26}
 .rdg-decision .rdg-instance-reference{margin:2px 0 5px;min-width:0}
 .rdg-decision .rdg-instance-reference .rdg-entity-reference{font-size:12px;padding:5px 7px;gap:6px;min-height:0}
 .rdg-decision .rdg-instance-reference .rdg-entity-reference-kind{min-width:24px;padding:1px 3px}
 .rdg-decision .rdg-instance-reference .rdg-entity-reference-title{white-space:normal}
 .rdg-decision .rdg-policy-instances [data-selected-instance-participant=true] .rdg-entity-reference{outline:1px solid #83c9f4}
 @media(max-width:600px){.rdg-decision .rdg-instance-table th,.rdg-decision .rdg-instance-table td{padding:6px 4px}.rdg-decision .rdg-instance-reference .rdg-entity-reference-kind{display:none}}
 .rdg-decision .rdg-invalidation-controls{position:sticky;top:-18px;z-index:3;background:#142437;padding:12px 0;border-bottom:1px solid #35526a}
 .rdg-decision .rdg-invalidation-filters{display:flex;flex-wrap:wrap;align-items:end;gap:8px 14px;margin-top:10px}
 .rdg-decision .rdg-invalidation-filters label{display:flex;flex-direction:column;gap:4px;color:#a9bfd1;font-size:11px;min-width:120px;max-width:250px}
 .rdg-decision .rdg-invalidation-filters select,.rdg-decision .rdg-invalidation-filters input{padding:6px;background:#102436;border:1px solid #48677f;border-radius:5px;color:#e4edf6;max-width:100%}
 .rdg-decision .rdg-invalidation-list{display:flex;flex-direction:column;gap:12px;padding-top:8px}
 .rdg-decision .rdg-invalidation-list>h3{font-size:13px;margin:8px 0 0}
 .rdg-decision .rdg-invalidation-card{width:100%;border:1px solid #48677f;border-radius:8px;padding:14px 16px;background:#102436;overflow-wrap:anywhere}
 .rdg-decision .rdg-invalidation-card[data-invalidation-selected=true]{border-color:#83c9f4}
 .rdg-decision .rdg-invalidation-card[data-invalidation-kind=disabled]{border-left:3px solid #bd9c60}
 .rdg-decision .rdg-invalidation-card[data-invalidation-kind=review]{border-left:3px solid #b89257}
 .rdg-decision .rdg-invalidation-card-head{display:flex;justify-content:space-between;align-items:start;gap:18px;flex-wrap:wrap}
 .rdg-decision .rdg-invalidation-card-head>.rdg-policy-actions{justify-content:flex-end;max-width:55%}
 .rdg-decision .rdg-invalidation-card-head .rdg-instance-reference{max-width:450px;margin-top:8px}
 .rdg-decision .rdg-invalidation-badge{font-size:12px;color:#e6d2a5}
 .rdg-decision .rdg-invalidation-reason{display:grid;grid-template-columns:minmax(150px,1fr) minmax(220px,1.6fr) minmax(160px,1fr);gap:18px;border-top:1px solid #30495f;padding-top:10px;margin-top:10px}
 .rdg-decision .rdg-invalidation-disable-body{display:grid;grid-template-columns:minmax(200px,1fr) minmax(260px,2fr);gap:24px;margin-top:10px}
 .rdg-decision .rdg-invalidation-card p{font-size:12px;line-height:1.55;margin:7px 0}
 .rdg-decision .rdg-invalidation-reason small{display:block;margin:5px 0}
 .rdg-decision .rdg-invalidation-details{font-size:11px;margin-top:9px;color:#a9bfd1}
 .rdg-decision .rdg-invalidation-details summary{cursor:pointer}
 .rdg-decision .rdg-invalidation-warning{color:#dac393;font-size:12px}
 @media(max-width:800px){.rdg-decision .rdg-invalidation-reason,.rdg-decision .rdg-invalidation-disable-body{grid-template-columns:1fr}.rdg-decision .rdg-invalidation-card-head>.rdg-policy-actions{max-width:100%}}
 .rdg-decision .rdg-dependency-section{margin:0;padding:0}
 .rdg-decision .rdg-dependency-application{border:1px solid #425f77;border-radius:8px;padding:10px;margin:10px 0;overflow-wrap:anywhere;background:#102436}
 .rdg-decision .rdg-dependency-application[data-dependency-status=disabled]{border-left:3px solid #bd9b67}
 .rdg-decision .rdg-dependency-application h4{font-size:12px;margin:6px 0}
 .rdg-decision .rdg-dependency-application p{font-size:11px;line-height:1.5;margin:8px 0}
 .rdg-decision .rdg-dependency-application small,.rdg-decision .rdg-dependency-role>b{font-size:10px;display:block;color:#acc3d4}
 .rdg-decision .rdg-dependency-application details>summary{font-size:11px;line-height:1.5;padding:6px 0;color:#acd4eb}
 .rdg-decision .rdg-dependency-reference{min-width:0;max-width:100%;margin:6px 0}
 .rdg-decision .rdg-dependency-reference .rdg-entity-reference{max-width:100%;width:100%}
 .rdg-decision .rdg-dependency-role,.rdg-decision .rdg-dependency-observation,.rdg-decision .rdg-dependency-link{border-top:1px solid #314e65;padding-top:8px;margin-top:10px}
 .rdg-decision .rdg-dependency-application .rdg-policy-actions{gap:5px}
 .rdg-decision .rdg-dependency-application .rdg-policy-actions button{white-space:normal;text-align:left;max-width:100%}
 .rdg-decision .rdg-stale-list{max-width:1400px;margin:0 auto}
 .rdg-decision .rdg-stale-group{padding:16px;margin:10px 0 17px;border:1px solid #4e6981;border-left:4px solid var(--rdg-node-line,#91bacc);background:#1b3044;border-radius:9px}
 .rdg-decision .rdg-stale-reason{margin:10px 0;padding:12px;border:1px solid #47637a;border-radius:7px;background:#132b3d}
 .rdg-decision .rdg-stale-reason p{font-size:11px;color:#c0d4e1}
 .rdg-decision .rdg-stale-reason small{font-size:10px;color:#9ebbd0}
 .rdg-decision .rdg-policy-participants{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:8px 0}
 .rdg-decision .rdg-policy-participants .rdg-entity-reference{width:auto;max-width:330px;flex:none}
 .rdg-decision .rdg-policy-participants>span{font-size:10px;color:#a9c6d8}
 .rdg-decision .rdg-policy-form-rules{display:flex;flex-direction:column;gap:10px;margin:10px 0}
 .rdg-decision .rdg-policy-form-rule{border:1px solid #4a647b;border-radius:7px;padding:10px}
 .rdg-decision .rdg-policy-form-rule label{display:block;margin:7px 0}
 @media (max-width:900px){.rdg-decision .rdg-policy-grid{grid-template-columns:minmax(0,1fr)}.rdg-decision .rdg-policy-header{padding:12px}.rdg-decision .rdg-policy-scroll{padding:12px}}
`;
 root.dataset.uiBuild='decision-desktop-20261103-inspector-tabs';
 function el(tag,text,cls){const n=doc.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
 function button(parent,text,fn,disabled=false){const b=el('button',text);b.type='button';b.disabled=disabled;b.onclick=e=>run(()=>fn(e));parent.append(b);return b;}
 function field(parent,label,value='',type='text',onchange=null){const row=el('label',label+' '),n=el(type==='textarea'?'textarea':'input');if(type!=='textarea')n.type=type;if(type==='checkbox')n.checked=!!value;else n.value=value??'';row.append(n);parent.append(row);if(onchange)n.oninput=()=>onchange(type==='checkbox'?n.checked:n.value);return n;}
 function select(parent,label,items,value,onchange=null){const row=el('label',label+' '),n=el('select');for(const [id,text] of items){const o=el('option',text);o.value=id;n.append(o);}n.value=value??items[0]?.[0]??'';row.append(n);parent.append(row);if(onchange)n.onchange=()=>onchange(n.value);return n;}
 function screen(){return session?.screens.find(s=>s.id===session.activeScreenId);}
 function note(text,isError=false){message=text;error=isError;const n=root.querySelector('.rdg-status');if(n){n.textContent=text;n.classList.toggle('rdg-error',isError);}}
 function sync(mutator,renderAfter=false){queue=queue.catch(()=>{}).then(async()=>{
  const before=screen(),value={activeScreenId:session.activeScreenId,screens:clone(session.screens),explorer:clone(session.explorer)};mutator(value,value.screens.find(s=>s.id===value.activeScreenId));
  session=await call({method:'view_session',action:'update',sessionId:session.id,expectedRevision:session.revision,value});if(renderAfter){const after=screen();if(before?.packageId!==after?.packageId||JSON.stringify(before?.spec)!==JSON.stringify(after?.spec))await load();else render();}return session;
 });return queue;}
 function draftValue(){return pendingDraft||screen()?.draft||(!screen()&&session?.explorer.drafts['new-process'])||{};}
 function sessionDraft(v,s,draft){if(s)s.draft=draft;else v.explorer.drafts['new-process']=draft;}
 function newScreen(packageId,spec){return {id:uid(),packageId,spec:{showLowLevel:true,...clone(spec)},presentation:{mode:'graph',expandedPaths:[],collapsedPaths:[],query:''},panels:{roadVisible:true,roadTab:'timeline',roadWidth:470,inspectorWidth:340,historyScroll:0,planScroll:0},draft:null,trail:[],viewTrail:[],focusLayouts:{},inspector:null};}
 function setDraft(key,value){pendingDraft=clone(draftValue());if(snapshot){pendingDraft.basePackageRevision??=snapshot.package.revision;pendingDraft.baseGraphRevision??=snapshot.graph.revision;}pendingDraft.form??={};pendingDraft.form[key]=value;clearTimeout(draftTimer);draftTimer=setTimeout(()=>void flushDraft().catch(e=>note(e.message,true)),180);}
 async function flushDraft(){clearTimeout(draftTimer);
  if(flushingDraft){await flushingDraft;if(pendingDraft)return flushDraft();await queue;return;}
  if(pendingDraft){const captured=pendingDraft;
   // Keep the latest local draft visible while its predecessor is in flight.
   // Typing during an update must clone that draft, never the old server value.
   flushingDraft=sync((v,s)=>sessionDraft(v,s,captured));
   try{await flushingDraft;if(pendingDraft===captured)pendingDraft=null;}finally{flushingDraft=null;}
   if(pendingDraft)return flushDraft();
  }await queue;
 }
 async function run(fn){if(busy)return;busy=true;if(error)note('');try{await flushDraft();return await fn();}catch(e){note(e.message,true);}finally{busy=false;}}
 async function loadCatalogs(initial=null){catalog=initial||await call({method:'catalog'});try{registry=await call({method:'recommendation_catalog',limit:20});}catch(e){if(!e.message.includes('PORTABLE_SCOPE_DENIED'))throw e;registry={unavailable:true,packages:[],total:0,offset:0,participation:{}};}}
 async function start(initial=null){if(!session)session=await call({method:'view_session',action:'create',sessionId:uid()});await loadCatalogs(initial);return load();}
 async function load({catalogs=false}={}){if(catalogs||!catalog)await loadCatalogs();let s=screen();if(s&&s.spec.kind!=='focus'&&s.spec.compactGraph===undefined){
   // Existing sessions get the new readable default without altering the owner layout.
   await sync((v,t)=>{if(t.spec.compactGraph===undefined){t.spec.compactGraph=true;delete t.spec.camera;}});
   s=screen();
  }
  if(!s){snapshot=null;history=null;form=session.explorer.drafts['new-process']?.open?'create':null;render();return null;}try{snapshot=await call({method:'read',packageId:s.packageId,includePlan:true,view:s.spec});}catch(e){if(!/FOCUS|VIEW_CASES|REFERENCE_MISSING:group/.test(e.message))throw e;const spec={...s.spec,kind:'graph',groupIds:[],shownCases:{}};delete spec.id;await sync((v,s)=>s.spec=spec);snapshot=await call({method:'read',packageId:s.packageId,includePlan:true,view:spec});note('Состав представления изменился; черновик сохранён.');}
  if(isProcess()&&s.spec.kind==='focus'){
   const finding=snapshot.graph.objects.find(n=>n.id===s.spec.id&&n.kind==='finding');
   if(finding){const subject=[...snapshot.graph.nodes,...snapshot.graph.objects].find(n=>n.id===finding.subjectId);inspectorTabState.set(subject?.id||finding.id,'findings');await sync((v,t)=>{t.spec={...t.spec,kind:subject?'focus':'graph',...(subject?{id:subject.id}:{})};if(!subject)delete t.spec.id;t.inspector={kind:'entity',id:subject?.id||finding.id};});return load();}
  }
  // Sessions created by older Viewer versions may still point directly to a
  // Ctx focus. That view is no longer part of the Process Graph canvas.
  if(['working','copy'].includes(snapshot.package.role)&&s.spec.kind==='focus'&&
     [...snapshot.graph.nodes,...snapshot.graph.objects].some(n=>n.id===s.spec.id&&['context','evidence'].includes(n.kind))){
   const contextId=s.spec.id;
   contextBank={packageId:s.packageId,open:true,selectedId:contextId,query:''};
   await sync((v,t)=>{t.spec={...t.spec,kind:'graph',groupIds:[]};delete t.spec.id;delete t.spec.camera;delete t.spec.focusPositions;t.inspector=null;});
   return load();
  }
  const meta=graphMeta(s.packageId);if(meta)Object.assign(meta,{revision:snapshot.package.revision,title:snapshot.graph.title,workGraphs:snapshot.graph.workGraphs,recommendationPackageIds:snapshot.graph.recommendationPackageIds});form=s.draft?.open?s.draft.form?.mode:null;history=snapshot.package.role==='working'||snapshot.package.role==='copy'?await call({method:'history',packageId:s.packageId}):null;render();return snapshot;}
 async function open(id,spec={kind:'graph'}){
  if(!session)session=await call({method:'view_session',action:'create',sessionId:uid()});if(!catalog)await loadCatalogs();return navigate(id,spec);
 }
 async function navigate(id,spec={kind:'graph'},newTab=false){
  if(pending)throw Error('Завершите или отмените предварительную проверку.');
  if(screen()?.draft&&id!==screen().packageId)newTab=true;
  const meta=catalog.packages.find(r=>r.packageId===id);if(meta?.coreModel&&meta.coreModel!=='rdg-decision-v1')return onLegacyOpen(id);
  await sync((v,s)=>{const retained=id===s?.packageId?Object.fromEntries(['camera','historyWindow','planWindow','shownCases','showExcludedAlternatives','showLowLevel','expandedOccurrenceIds','compactGraph','showAllBlocks','historyMode'].filter(k=>s.spec[k]!==undefined).map(k=>[k,s.spec[k]])):{};const nextSpec={...retained,...clone(spec)};
   // If legacy-Viewer returns to a Decision session that predates compactGraph,
   // make the mode explicit before load(): otherwise the old-screen migration
   // would delete the camera that this roundtrip must preserve.
   if(id===s?.packageId&&s.spec.kind==='focus'&&nextSpec.kind==='graph'&&
      nextSpec.camera&&nextSpec.compactGraph===undefined)nextSpec.compactGraph=true;
   // Returning from the legacy controller to the *same* Decision screen
   // must retain its previous camera. A different Working Graph has new bounds.
   if(!s||id!==s.packageId||
      ((s.spec.kind==='workGraph'||nextSpec.kind==='workGraph')&&
       (nextSpec.kind!==s.spec.kind||nextSpec.id!==s.spec.id)))delete nextSpec.camera;
   if(!s){const next=newScreen(id,nextSpec);v.screens.push(next);v.activeScreenId=next.id;v.explorer.open=false;}else if(newTab){const next=clone(s);next.id=uid();next.packageId=id;next.spec=nextSpec;next.draft=null;next.inspector=null;next.trail=[];if(id!==s.packageId)next.presentation={...(next.presentation||{mode:'graph'}),expandedPaths:[],collapsedPaths:[],query:''};v.screens.push(next);v.activeScreenId=next.id;}else{if(s.packageId!==id){s.viewTrail=[];s.focusLayouts={};s.presentation={...(s.presentation||{mode:'graph'}),expandedPaths:[],collapsedPaths:[],query:''};}
    s.packageId=id;s.spec=nextSpec;s.inspector=null;s.trail=[];}});await load();
 }
 async function refresh(){markdownView=null;if(pending)throw Error('Завершите предварительную проверку.');await flushDraft();if(!session)return start();session=await call({method:'view_session',sessionId:session.id});return load({catalogs:true});}
 async function schema(op,nodeId,extra={}){return (await call({method:'schema',op,packageId:screen().packageId,nodeId,...extra})).request;}
 function draftStale(){const d=draftValue();return !!snapshot&&(d.baseGraphRevision!=null?d.baseGraphRevision!==snapshot.graph.revision:d.basePackageRevision!=null&&d.basePackageRevision!==snapshot.package.revision);}
 function checkDraft(){if(draftStale())throw Error('Данные изменились. Черновик сохранён; перечитайте изменения и обновите его основание.');}
 async function prepare(request){if(pending)throw Error('Завершите предыдущую проверку.');const exact=clone(request);const preview=await call({method:'preflight',request:exact});pending={request:exact,preview,uncertain:false};note('Проверьте последствия перед сохранением.');render();return preview;}
 async function commit(){if(!pending)return;const exact=pending.request;const origin=clone(draftValue().form||{});let result;
  try{result=await call({method:'apply',request:exact,expectedInputBinding:pending.preview.inputBinding});if(result.published!==true)throw Error('Исход записи не подтверждён; прочитайте receipt.');}
  catch(e){pending.uncertain=e.definite!==true;render();throw e;}
  pending=null;form=null;packageDetail=null;
  if(isProcess()&&contextBank.open&&exact.op==='core'){
   if(exact.command==='add'&&exact.data?.entity?.kind==='context')contextBank.selectedId=exact.data.entity.id;
   if(exact.command==='delete'&&exact.nodeId===contextBank.selectedId)contextBank.selectedId=null;
  }
  await sync((v,s)=>{if(exact.op==='create'&&result.packages?.[0]){const id=result.packages[0].packageId;if(!s){s=newScreen(id,{kind:'graph'});v.screens.push(s);v.activeScreenId=s.id;v.explorer.open=false;}else{s.packageId=id;s.spec={kind:'graph'};s.inspector=null;s.trail=[];}delete v.explorer.drafts['new-process'];}if(exact.op==='recommendation_edit'){delete v.explorer.drafts[exact.definition?.id||exact.packageId];if(s?.draft)s.draft.open=false;}else if(s)s.draft=null;if(exact.command==='work_graph'){s.spec={...s.spec,kind:'workGraph',id:exact.data.workGraph.id,groupIds:[]};delete s.spec.workGraphId;s.inspector=null;}});await load({catalogs:!['core','paper_edit','layout_edit','place','unplace','plan_create','plan_edit'].includes(exact.op)});if(exact.command==='requirement_decision')await revealCreatedDecision(exact.data.decisionId);if(exact.command==='add'&&exact.data.entity.kind==='finding'){inspectorTabState.set(exact.data.entity.subjectId,'findings');render();}note('Сохранено и перечитано из Application.');if(origin.returnToDependencies){inspectorTabState.set(origin.returnToDependencies,'dependencies');if(origin.applyAfterCreate&&exact.command==='policy_change'&&exact.data.action==='policy_save')await showForm('policyBinding',dependencyForm(origin.returnToDependencies,{policyId:exact.data.value.id,policyVersion:exact.data.value.version}));}return result;
 }
 async function saveLayout(positions,occurrences){
  const prior=screen().draft?.layout,same=prior&&JSON.stringify(prior.positions)===JSON.stringify(positions)&&JSON.stringify(prior.occurrences)===JSON.stringify(occurrences);
  if(prior?.uncertain&&!same)throw Error('Проверьте результат или повторите прежнюю запись позиции.');
  const request=same&&prior.request?clone(prior.request):await schema('layout_edit');if(!same||!prior.request)request.commands=[{type:'set_positions',graphKey:snapshot.view.graphKey,positions},{type:'set_occurrences',graphKey:snapshot.view.graphKey,occurrences}];
  await sync((v,s)=>{s.draft??={basePackageRevision:snapshot.package.revision,baseGraphRevision:snapshot.graph.revision};s.draft.layout={positions,occurrences,request,...(same&&prior.inputBinding?{inputBinding:prior.inputBinding}:{})};});
  try{let binding=screen().draft.layout.inputBinding;if(!binding){const preview=await call({method:'preflight',request});binding=preview.inputBinding;await sync((v,s)=>s.draft.layout.inputBinding=binding);}
   const result=await call({method:'apply',request,expectedInputBinding:binding});if(result.published!==true)throw Error('Исход записи позиции не подтверждён.');
   await sync((v,s)=>{if(s.draft){delete s.draft.layout;if(!s.draft.form)s.draft=null;}});await load();note('Позиция сохранена.');}
  catch(e){await sync((v,s)=>{if(s.draft?.layout)s.draft.layout.uncertain=e.definite!==true;});note('Позиция осталась в черновике: '+e.message,true);render();throw e;}
 }
 async function cancelLayout(){const layout=screen().draft?.layout;if(layout?.request){const receipt=await call({method:'receipt',packageId:layout.request.targetPackageId,transactionId:layout.request.transactionId});if(receipt.found)throw Error('Транзакция позиции уже принята; повторите тот же запрос и перечитайте результат.');}await sync((v,s)=>{delete s.draft.layout;if(!s.draft.form)s.draft=null;},true);}
 function recordView(s){s.viewTrail??=[];s.viewTrail.push({spec:clone(s.spec),inspector:clone(s.inspector)});
  if(s.viewTrail.length>24)s.viewTrail.shift();
 }
 async function viewBack(index){await sync((v,s)=>{const trail=s.viewTrail||[];
   if(index<0||index>=trail.length)return;
   const previous=trail[index];s.spec=clone(previous.spec);s.inspector=clone(previous.inspector);
   s.viewTrail=trail.slice(0,index);
  });await load();}
 async function changeView(patch){
  const localPlan=snapshot?.plan?.schemaVersion===3&&snapshot.graph.coreModel==='rdg-decision-v1'&&Object.keys(patch).every(k=>['shownCases','planWindow','historyWindow','historyMode'].includes(k));
  const projector=()=>typeof module==='object'&&module.exports?require('./rdg-visual-projection.js'):globalThis.RDGVisualProjection;
  // Validate the next projection before saving its view state. Execution and
  // dependency facts stay exactly those of the last authorized Graph read.
  if(localPlan)projector().temporalPlan(snapshot.plan,snapshot.graph,snapshot.view.completion,{...screen().spec,...patch},snapshot.package.packageId);
  await sync((v,s)=>{const old=s.spec;
  if(patch.kind&&((patch.kind!==old.kind)||
      (Object.hasOwn(patch,'id')&&patch.id!==old.id)))recordView(s);
  s.spec={...old,...patch};
  if(patch.kind&&patch.kind!=='focus')delete s.spec.workGraphId;
  if(old.kind==='focus'&&s.spec.kind!=='focus')delete s.spec.focusPositions;
  if(patch.kind==='graph')delete s.spec.id;
  if((patch.kind&&patch.kind!==old.kind)||
     (Object.hasOwn(patch,'compactGraph')&&patch.compactGraph!==old.compactGraph)||
     (Object.hasOwn(patch,'showAllBlocks')&&patch.showAllBlocks!==old.showAllBlocks))delete s.spec.camera;
 });
  if(localPlan){snapshot.view.spec=clone(screen().spec);snapshot.planView=projector().temporalPlan(snapshot.plan,snapshot.graph,snapshot.view.completion,screen().spec,snapshot.package.packageId);const road=root.querySelector('.rdg-road');if(road)renderRoad(road.parentNode,road);else render();}
  else await load();
 }
 async function openDecisionGroup(id){
  const group=snapshot?.graph.decisionGroups.find(g=>g.id===id);
  if(!group)throw Error('Группа решений не найдена в текущем процессе.');
  if(openedDecisionGroup()?.id===id){
   await sync((v,s)=>s.inspector={kind:'group',ids:[id]},true);
   return;
  }
  await sync((v,s)=>{
   recordView(s);
   s.spec={...s.spec,kind:'graph',groupIds:[id]};
   delete s.spec.id;delete s.spec.camera;delete s.spec.focusPositions;delete s.spec.workGraphId;
   s.inspector={kind:'group',ids:[id]};
  },true);
 }
 async function showDecisionGroupDetails(ids){
  const existing=ids.filter(id=>snapshot.graph.decisionGroups.some(g=>g.id===id));
  if(!existing.length)throw Error('Группа решений не найдена в текущем процессе.');
  await sync((v,s)=>s.inspector={kind:'group',ids:existing},true);
 }
 async function focusNode(id){const n=[...snapshot.graph.nodes,...snapshot.graph.objects,...snapshot.graph.externalActions].find(n=>n.id===id);if(!n)throw Error('Сущность отсутствует в текущем процессе.');
  if(snapshot.graph.externalActions.some(a=>a.id===id)){await sync((v,s)=>s.inspector={kind:'planningAction',id},true);return;}
  if(isProcess()&&['context','evidence'].includes(n.kind)){contextBank.open=true;contextBank.selectedId=id;render();return;}
  contextBank.open=false;
  const spec={...screen().spec,kind:'focus',id};delete spec.groupIds;
  if(screen().spec.kind==='focus'&&screen().spec.id===id){await sync((v,s)=>s.inspector={kind:'entity',id},true);return;}
  spec.focusPositions=clone(screen().focusLayouts?.[id]||{});
  if(screen().spec.kind==='workGraph')spec.workGraphId=screen().spec.id;
  // Each new focus has an independent compact visual projection; fit it rather
  // than carrying the camera coordinates of the much larger process graph.
  delete spec.camera;
  await sync((v,s)=>{recordView(s);s.spec=spec;s.inspector={kind:'entity',id};});await load();
 }
 async function lens(ref){const target=await call({method:'read',packageId:ref.packageId});if(target.package.role!=='lens'||target.graph.identitySpace!==ref.identitySpace||target.graph.coreModel!=='rdg-decision-v1')throw Error('Линза или её namespace не совпадает с привязкой.');
  await sync((v,s)=>{s.trail.push({packageId:s.packageId,spec:clone(s.spec),inspector:clone(s.inspector),draft:clone(s.draft),mode:s.presentation.mode,inspectorTab:inspectorTabState.get(s.inspector?.id)||''});s.packageId=ref.packageId;s.spec=ref.nodeId?{kind:'focus',id:ref.nodeId}:{kind:'graph'};s.inspector=null;s.draft=null;});await load();
 }
 function restoreLensTrail(s,t){const {mode,inspectorTab,...rest}=t;Object.assign(s,rest);if(mode)s.presentation.mode=mode;if(inspectorTab&&t.inspector?.id)inspectorTabState.set(t.inspector.id,inspectorTab);}
 function recommendationRows(id){return (snapshot.recommendations?.matches||[]).filter(r=>r.nodeId===id);}
 function renderRecommendations(parent,node){
  parent.dataset.recommendationsFor=node.id;
  if(snapshot.recommendations?.available===false){parent.append(el('p','Рекомендации недоступны: нет доступа к реестру.'));return;}
  button(parent,'Добавить рекомендацию',()=>showForm('recommendation',{targetId:node.id,targetKind:['process','workGraph'].includes(node.kind)?node.kind:'entity'}));
  const matches=recommendationRows(node.id);if(!matches.length)parent.append(el('p','Рекомендаций пока нет.','rdg-muted'));
  for(const match of matches){
   const card=el('article',null,'rdg-card');card.dataset.recommendationId=match.recommendationId||match.reasons[0].packageId+':'+match.reasons[0].ruleId;parent.append(card);
   const meta=graphMeta(match.lensRef.packageId);button(card,meta?.title||match.lensRef.lensKey,()=>lens(match.lensRef),match.target?.available===false);
   if(match.target?.available===false)card.append(el('p','Цель недоступна или несовместима.','rdg-muted'));
   if(match.whenText)card.append(el('h4','Когда использовать'),el('p',match.whenText));if(match.usageText)card.append(el('h4','Как использовать'),el('p',match.usageText));
   const origin=definitionMeta(match.reasons[0].packageId);if(origin?.authored)card.prepend(el('h4',origin.title));const provenance=el('details');provenance.append(el('summary','Происхождение'));for(const reason of match.reasons){const p=definitionMeta(reason.packageId);provenance.append(el('p',p?.title||'Пакет рекомендаций'));}card.append(provenance);
   const p=definitionMeta(match.reasons[0].packageId);
   if(p?.authored&&(registry.participation?.[p.id]||[]).length<=1){button(card,'Изменить рекомендацию',()=>showForm('recommendation',{definitionId:p.id,ruleId:match.reasons[0].ruleId,targetId:node.id,targetKind:['process','workGraph'].includes(node.kind)?node.kind:'entity'}));button(card,'Убрать рекомендацию',async()=>{if(p.rules.length>1){await prepare({op:'recommendation_edit',transactionId:uid(),expectedRegistryRevision:registry.registryRevision,action:'edit',packageId:p.id,definition:{...clone(p),revision:p.revision+1,rules:p.rules.filter(r=>r.id!==match.reasons[0].ruleId)},note:'Удалён один адресный совет; остальные сохранены'});return;}const req=await schema('recommendation_attach');req.packageIds=snapshot.graph.recommendationPackageIds.filter(id=>id!==p.id);req.note='Снята адресная рекомендация';await prepare(req);});}
   if(['working','copy'].includes(snapshot.package.role)&&match.target?.available!==false)button(card,'Отметить применение · '+match.lensRef.lensKey,()=>showForm('lensApply',{nodeId:node.id,lensPackageId:match.lensRef.packageId,recommendationIds:[...new Set(match.reasons.map(r=>r.packageId))]}),['process','workGraph','question','finding'].includes(node.kind));
  }
 }
 function recommendationDetails(parent,node){const d=el('details');d.append(el('summary','Рекомендации · '+recommendationRows(node.id).length));parent.append(d);renderRecommendations(d,node);}
 function definitionMeta(id){return snapshot?.recommendations?.packages?.find(p=>p.id===id)||registry?.packages.find(p=>p.id===id);}
 function graphMeta(id){return catalog?.packages.find(p=>p.packageId===id);}
 function activeArea(s=screen()){return snapshot?.graph.workGraphs.find(w=>w.id===(s.spec.kind==='workGraph'?s.spec.id:s.spec.workGraphId));}
 function openedDecisionGroup(s=screen()){
  if(s?.spec.kind!=='graph'||!s.spec.groupIds?.length||s.packageId!==screen()?.packageId)return null;
  return snapshot?.graph.decisionGroups.find(g=>g.id===s.spec.groupIds[0])||null;
 }
 function groupHeading(s=screen()){
  const group=openedDecisionGroup(s);
  return group?'Открыта группа решений · '+group.title:null;
 }
 function groupParentTitle(group){
  return snapshot.graph.nodes.find(n=>n.id===group.parentId)?.title||group.parentId;
 }
 function scopeTitle(s){const meta=graphMeta(s.packageId),area=(meta?.workGraphs||[]).find(w=>w.id===(s.spec.kind==='workGraph'?s.spec.id:s.spec.workGraphId));return s.spec.kind==='focus'?'Фокус · '+(s.packageId===screen().packageId?snapshot.graph.nodes.concat(snapshot.graph.objects,snapshot.graph.externalActions).find(n=>n.id===s.spec.id)?.title||s.spec.id:s.spec.id):groupHeading(s)|| (area?'Working Graph · '+area.title:['ready','lens'].includes(meta?.role)?meta.role==='lens'?'Граф линзы':'Шаблон графа':'Process Graph · весь процесс');}
 function titleFor(s){return graphMeta(s.packageId)?.title||'Процесс-граф';}
 function menu(parent,title,cls=''){const item=el('details',null,'rdg-menu '+cls),summary=el('summary',title);summary.setAttribute('role','button');item.append(summary);const content=el('div',null,'rdg-menu-content');item.append(content);parent.append(item);content.addEventListener('click',e=>{if(e.target.closest('button'))item.open=false;});return content;}
 const palette={requirement:['#193e52','#73b5d3'],decision:['#3d3930','#d6b77e'],action:['#24483f','#8bd0b8'],canon:['#302d49','#a99bc8'],context:['#263446','#91a7bd'],info:['#253c4a','#92b9c8'],evidence:['#253c4a','#92b9c8'],finding:['#403048','#d1a0cf']};
 const workAreaColors=Object.freeze({blue:'#5aa8d2',teal:'#56c5b2',amber:'#d6b77e',violet:'#a99bc8',rose:'#d98fa8',lime:'#a7c77c',cyan:'#72cbd8',slate:'#91a7bd'});
 const workAreaColorNames=Object.freeze({blue:'Синий',teal:'Бирюзовый',amber:'Янтарный',violet:'Фиолетовый',rose:'Розовый',lime:'Лаймовый',cyan:'Голубой',slate:'Серо-голубой'});
 const workAreaColorKeys=Object.keys(workAreaColors);
 function workAreaColorKey(area,index=0){if(area?.colorKey&&Object.hasOwn(workAreaColors,area.colorKey))return area.colorKey;let hash=2166136261;for(const char of String(area?.id||index))hash=Math.imul(hash^char.charCodeAt(0),16777619);return workAreaColorKeys[(hash>>>0)%workAreaColorKeys.length];}
 function workAreaColor(area,index=0){return workAreaColors[workAreaColorKey(area,index)];}
 const kindLabel={requirement:'Requirement',decision:'Decision',action:'Action',canon:'Теория принятия решения',context:'Контекст процесса',info:'Info',evidence:'Данные контекста · прежняя запись',finding:'Файндинг'};
 const kindCode={requirement:'R',decision:'D',action:'Act',canon:'Can',context:'Ctx',info:'Inf',evidence:'Ctx',finding:'F',finding:'F'};
 const dependencyPresets=Object.freeze({L1:['definition'],L2:['definition','directScope'],
  decision_state:['selection','result'],decision_context:['definition','context'],
  decision_canon:['definition','canon'],canon_criteria:['definition']});
 const dependencyLabels={definition:'Определение источника',directScope:'Непосредственный семантический состав',
  selection:'Выбор Decision',result:'Подтверждённый результат Decision',
  context:'Контекст и срабатывания его зависимостей',canon:'Связанная теория принятия решения',info:'Связанные Info-материалы'};
 const dependencyPresetNames={L1:'L1 · Определение',L2:'L2 · Определение и прямой состав',
  decision_state:'Decision · состояние',decision_context:'Decision + контекст',
  decision_canon:'Decision + теория принятия решения',canon_criteria:'Теория · содержание',custom:'Настраиваемый'};
 function ruleOf(e){return e.dependencyRule||{preset:e.dependencyLevel||'L1',watch:dependencyPresets[e.dependencyLevel||'L1']};}
 function allowedWatch(kind){return ['definition','directScope',...(kind==='decision'?['selection','result','context','canon','info']:kind==='canon'?['info']:[])];}
 function directStructure(node){const relations=snapshot.graph.edges.filter(e=>e.to===node.id&&
   ['DERIVES','DRIVES','INTRODUCES','REQUIRES_ACTION'].includes(e.type));
  for(const g of snapshot.graph.decisionGroups)if(g.members.some(m=>m.decisionId===node.id))
    relations.push({id:g.id,type:'DECISION_MEMBER',from:g.parentId,to:node.id});
  return relations;}

 function colorize(element,kind){const [fill,line]=palette[kind]||palette.info;element.style.setProperty('--rdg-node-fill',fill);element.style.setProperty('--rdg-node-line',line);}
 function entityReference(parent,target,action){
  const b=button(parent,'',action);b.className='rdg-entity-reference';b.dataset.kind=target.kind;colorize(b,target.kind);
  const code=el('span',kindCode[target.kind]||'?', 'rdg-entity-reference-kind');code.title=kindLabel[target.kind]||target.kind;
  b.append(code,el('span',target.title,'rdg-entity-reference-title'),el('span','↗','rdg-entity-reference-open'));
  b.setAttribute('aria-label',(kindLabel[target.kind]||target.kind)+' · '+target.title);return b;
 }
 function areaEdges(area){const ids=new Set(area.memberIds),edges=[...snapshot.graph.edges,...snapshot.graph.decisionGroups.flatMap(g=>g.members.map(m=>({id:m.id,type:'DECISION_MEMBER',from:g.parentId,to:m.decisionId,groupId:g.id})))];return edges.filter(e=>ids.has(e.from)!==ids.has(e.to));}
 async function switchTab(id){if(pending)throw Error('Завершите предварительную проверку.');await sync(v=>v.activeScreenId=id);form=null;await load();}
 async function showForm(name,seed={}){if(screen()?.draft?.layout)throw Error('Сначала сохраните или отмените черновик позиции.');form=name;if(name==='insert'){seed.targetPackageId??=catalog.packages.find(p=>['working','copy'].includes(p.role)&&p.coreModel==='rdg-decision-v1')?.packageId;if(seed.targetPackageId)targetSnapshots.set(seed.targetPackageId,await call({method:'read',packageId:seed.targetPackageId}));}
  if(name==='add'&&!seed.processContextBank)seed.workGraphId??=screen().spec.kind==='workGraph'?screen().spec.id:screen().spec.workGraphId||null;await sync((v,s)=>sessionDraft(v,s,{...(snapshot?{basePackageRevision:snapshot.package.revision,baseGraphRevision:snapshot.graph.revision}:{}),open:true,form:{...seed,mode:name}}));render();}

 const markdownAnchor=/^<a id="(rdg-[a-f0-9]{24})"><\/a>$/;
 const markdownLink=/\[((?:\\.|[^\]\\])+)\]\((#rdg-[a-f0-9]{24}|rdg:[a-f0-9-]{36}\/[A-Za-z0-9_.~%+-]+)(?: "(rdg:[a-f0-9-]{36}\/[A-Za-z0-9_.~%+-]+)")?\)/g;
 const unescapeMarkdown=text=>text.replace(/\\([\\*_\[\]<>|#])/g,'$1');
 let markdownView=null,searchView=null;
 function markdownKey(){
  const s=screen();
  return JSON.stringify([s.id,s.packageId,s.spec,snapshot.package.revision,!!s.panels.roadVisible]);
 }
 function markdownLines(parent,lines,follow){
  let quote=null;
  for(const line of lines){
   if(!line){quote=null;continue;}
   if(/^\s*> /.test(line)){
    if(!quote){quote=el('blockquote',null,'rdg-markdown-quote');parent.append(quote);}
    if(quote.textContent)quote.append(doc.createTextNode('\n'));
    quote.append(doc.createTextNode(line.replace(/^\s*> /,'')));continue;
   }
   quote=null;
   const anchor=markdownAnchor.exec(line);
   if(anchor){const item=el('span');item.dataset.markdownAnchor=anchor[1];parent.append(item);continue;}
   const heading=/^(#{1,6}) (.+)$/.exec(line);
   const row=el(heading?'h'+heading[1].length:'p');
   let text=heading?heading[2]:line;
   const list=/^( *)- (.*)$/.exec(text);
   if(list){row.className='rdg-markdown-field';row.style.paddingInlineStart=Math.min(list[1].length,16)+'ch';text='• '+list[2];}
   let pos=0;
   for(const match of text.matchAll(markdownLink)){
    row.append(doc.createTextNode(unescapeMarkdown(text.slice(pos,match.index)).replaceAll('**','')));
    const link=el('a',unescapeMarkdown(match[1]));link.href=match[2];
    link.onclick=e=>{e.preventDefault();void run(()=>follow(match[2],match[3]));};row.append(link);
    pos=match.index+match[0].length;
   }
   row.append(doc.createTextNode(unescapeMarkdown(text.slice(pos)).replaceAll('**','')));
   parent.append(row);
  }
 }
 async function fetchMarkdown(state,cursor=null){
  if(state.loading)return;
  state.loading=true;state.error=null;
  const s=screen();
  try{
   const result=await call({method:'read',format:'markdown',detail:'full',
     packageId:s.packageId,view:clone(s.spec),includePlan:!!s.panels.roadVisible,cursor});
   if(state!==markdownView||!screen()||markdownKey()!==state.key)return;
   if(result.snapshot.packageRevision!==snapshot.package.revision||
      (state.pages.length&&JSON.stringify(state.pages[0].snapshot)!==JSON.stringify(result.snapshot))){
    throw Error('Снимок изменился. Обновите данные процесса.');
   }
   state.pages.push(result);state.cursor=result.page.nextCursor;
  }catch(e){state.error=e.message;}
  finally{
   state.loading=false;
   if(state===markdownView&&screen()&&markdownKey()===state.key&&screen().presentation?.mode==='markdown')render();
  }
 }
 function renderMarkdown(parent){
  parent.classList.add('rdg-markdown-view');
  const key=markdownKey();
  if(markdownView?.key!==key){
   const state={key,pages:[],cursor:null,loading:false,error:null,expanded:new Set()};
   markdownView=state;
   void fetchMarkdown(state);
  }
  const state=markdownView;
  if(state.error){parent.append(el('p',state.error,'rdg-error'));return;}
  if(!state.pages.length){parent.append(el('p','Загрузка Markdown…'));return;}
  const follow=async(address,qualified)=>{
   const target=address.startsWith('#')?
    root.querySelector('[data-markdown-anchor="'+address.slice(1)+'"]'):null;
   if(!target&&(qualified||address.startsWith('rdg:'))){
    const [owner,id]=(qualified||address).slice(4).split('/');
    if(owner!==screen().packageId)throw Error('Ссылка ведёт в другую область.');
    return focusNode(decodeURIComponent(id));
   }
   if(!target)return;
   let details=target.closest('details');
   while(details){details.open=true;details=details.parentElement.closest('details');}
   target.scrollIntoView({block:'start'});
  };
  const headings=state.pages.flatMap(page=>page.blocks).filter(block=>block.anchor&&block.title);
  if(headings.length>12){
   const toc=el('details',null,'rdg-markdown-toc');toc.append(el('summary','Оглавление'));
   const list=el('ul');
   for(const heading of headings){
    const item=el('li');item.style.marginInlineStart=Math.min(heading.depth||0,6)*12+'px';
    const link=el('a',heading.title);link.href='#'+heading.anchor;
    link.onclick=e=>{e.preventDefault();void run(()=>follow(link.hash));};
    item.append(link);list.append(item);
   }
   toc.append(list);parent.append(toc);
  }
  for(const page of state.pages){
   const lines=page.markdown.split('\n');
   for(const block of page.blocks){
    const part=el('section',null,'rdg-markdown-part');
    if(block.depth)part.style.marginInlineStart=Math.min(block.depth,6)*12+'px';
    if(block.entityId)part.dataset.markdownEntity=block.entityId;
    markdownLines(part,lines.slice(block.start,block.leadEnd),follow);
    if(block.hasDetails){
     const details=el('details');const detailKey=block.anchor||String(state.pages.indexOf(page))+'-'+block.start;
     details.open=state.expanded.has(detailKey);
     details.ontoggle=()=>{if(details.open)state.expanded.add(detailKey);else state.expanded.delete(detailKey);};
     details.append(el('summary',block.entityId?'Сведения':'Подробности'));
     markdownLines(details,lines.slice(block.detailsStart,block.end),follow);
     part.append(details);
    }
    parent.append(part);
   }
  }
  if(state.cursor){parent.append(el('p','Выдача ещё не полная.'));
   button(parent,'Показать продолжение Markdown',()=>fetchMarkdown(state,state.cursor),state.loading);}
 }
 async function findText(state,append=false,returning=false){
  const query=state.query.trim();
  if(!query||append&&!state.cursor)return;
  if(!append&&!returning)state.packageId=screen().packageId;
  const request={method:'search',query,scope:state.scope,
   ...(state.scope==='package'?{packageId:state.packageId}:{}),
   ...(append?{cursor:state.cursor}:{})};
  const attempt=++state.attempt;state.loading=true;state.error=null;
  if(!append){state.items=[];state.cursor=null;if(!returning)state.scroll=0;}
  render();
  try{
   const result=await call(request);
   if(state!==searchView||attempt!==state.attempt)return;
   state.items.push(...result.items);state.cursor=result.page.nextCursor;
  }catch(e){if(attempt===state.attempt)state.error=e.message;}
  finally{if(state===searchView&&attempt===state.attempt){state.loading=false;render();}}
 }
 function startSearch(){
  if(!searchView)searchView={query:'',scope:'package',packageId:screen().packageId,items:[],
   cursor:null,open:true,attempt:0,scroll:0};
  searchView.open=true;
  if(searchView.query.trim())return findText(searchView,false,true);
  render();
 }
 async function openSearchResult(hit){
  const ref=hit.target.ref;
  const resolved=await call({method:'resolve',packageId:hit.owner.packageId,reference:ref});
  if(resolved.status!=='current'||!resolved.node)throw Error('Совпадение больше недоступно.');
  searchView.open=false;
  const entity=resolved.node,id=entity.id;
  if(hit.owner.packageId!==screen().packageId)await navigate(hit.owner.packageId,{kind:'graph'},true);
  if(entity.kind==='question'&&isProcess())return openQuestions(id);
  if(['context','evidence'].includes(entity.kind)&&isProcess())return focusNode(id);
  if(entity.kind==='finding'&&isProcess()){
   await focusNode(entity.subjectId);
   inspectorTabState.set(entity.subjectId,'findings');
   findingFilters.delete(snapshot.package.packageId+':'+entity.subjectId);
   await sync((v,s)=>{s.inspector={kind:'entity',id:entity.subjectId};},true);
   root.querySelector('[data-finding-id="'+CSS.escape(id)+'"]')?.scrollIntoView({block:'nearest'});
  }
  await focusNode(id);
  const section=hit.target.section;
  if(section)inspectorTabState.set(id,section);
  return sync((v,s)=>{
   s.presentation??={mode:'graph',expandedPaths:[],collapsedPaths:[],query:''};
   s.presentation.mode='markdown';
  },true);
 }
 function renderTextSearch(parent){
  const state=searchView,panel=el('section',null,'rdg-search-panel');
  panel.setAttribute('aria-label','Поиск по тексту');parent.append(panel);
  const toolbar=el('div',null,'rdg-row');panel.append(toolbar);
  const input=el('input');input.type='search';input.maxLength=180;input.value=state.query;
  input.placeholder='Слово, фраза или ID';input.setAttribute('aria-label','Текст поиска');toolbar.append(input);
  input.oninput=()=>{state.query=input.value;state.attempt++;state.loading=false;state.cursor=null;};
  input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();void run(()=>findText(state));}};
  select(toolbar,'Область поиска',[['package','Открытый процесс или линза'],['catalog','Весь доступный каталог']],state.scope,
   value=>{state.scope=value;state.packageId=screen().packageId;return findText(state);});
  button(toolbar,'Найти',()=>{state.packageId=screen().packageId;return findText(state);},state.loading);
  button(toolbar,'Закрыть поиск',()=>{state.open=false;render();});
  const list=el('div',null,'rdg-search-results');panel.append(list);
  list.onscroll=()=>{state.scroll=list.scrollTop;};
  if(state.error)list.append(el('p',state.error,'rdg-error'));
  if(!state.items.length&&!state.loading&&state.attempt&&!state.error)list.append(el('p','Совпадений нет.'));
  for(const hit of state.items){
   const row=el('article',null,'rdg-search-hit');row.dataset.searchEntity=hit.ref.nodeId;
   button(row,hit.title,()=>openSearchResult(hit));
   row.append(el('small',hit.kind+' · '+hit.ref.nodeId+' · '+hit.owner.title));
   for(const match of hit.matches.slice(0,1))row.append(el('p',match.label+' · '+match.snippet));
   if(hit.matches.length>1){
    const more=el('details');more.append(el('summary','Другие поля · '+(hit.matches.length-1)));
    for(const match of hit.matches.slice(1))more.append(el('p',match.label+' · '+match.snippet));
    row.append(more);
   }
   list.append(row);
  }
  if(state.loading)list.append(el('p','Поиск…'));
  if(state.cursor)button(list,'Следующая страница поиска',()=>findText(state,true),state.loading);
  list.scrollTop=state.scroll;
 }
 function renderLanding(){root.dataset.mode='explorer';root.replaceChildren(style);const status=el('p',message||(catalog?'Выберите процесс-граф, рабочую область или готовый граф.':'Загрузка Explorer…'),'rdg-status');status.setAttribute('role','status');status.classList.toggle('rdg-error',error);root.append(status);renderExplorer(root,true);const footer=el('footer',null,'rdg-footer');footer.append(el('span','Explorer · граф ещё не выбран'),el('span','Decision UI · 20261029-fix2'));root.append(footer);if(pending)renderPreview(root);else if(form)renderForm(root);}
 function render(){captureInvalidationPosition();closeStructureContextMenu();if(!snapshot||!screen())return renderLanding();root.dataset.mode='graph';root.replaceChildren(style);const s=screen(),work=isProcess(),area=activeArea();
  if(contextBank.packageId!==s.packageId)contextBank={packageId:s.packageId,open:false,selectedId:null,query:''};
  if(!work)contextBank.open=false;
  const head=el('header',null,'rdg-row rdg-head');root.append(head);const brand=button(head,'☷ RDG Viewer',()=>sync(v=>v.explorer.open=!v.explorer.open,true));brand.className='rdg-brand';brand.setAttribute('aria-expanded',String(session.explorer.open));brand.title='Открыть или закрыть Explorer';head.append(el('span','v2.7.0','rdg-version'));
  const project=el('div',null,'rdg-project');project.append(el('strong',snapshot.graph.title),el('small',work?'Process Graph · '+snapshot.graph.workGraphs.length+' рабочих областей · Plan и History процесса':snapshot.package.role==='lens'?'Граф линзы · переиспользуемое определение':'Шаблон графа · вставить в процесс'));head.append(project);button(head,'Обновить',refresh);button(head,searchView?.items.length?'К результатам поиска':'Поиск по тексту',startSearch);
  if(s.trail.length){button(head,'Назад к линзе',async()=>{await sync((v,s)=>{const last=s.trail.pop();restoreLensTrail(s,last);});await load();});button(head,'К процессу',async()=>{await sync((v,s)=>{const first=s.trail[0];restoreLensTrail(s,first);s.trail=[];});await load();});}
  if(s.trail.some(t=>t.inspector?.kind==='planningAction'))button(head,'К метадействию в Plan',async()=>{await sync((v,s)=>{const first=s.trail.find(t=>t.inspector?.kind==='planningAction');restoreLensTrail(s,first);s.trail=[];});await load();});
  const tabs=el('nav',null,'rdg-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Вкладки экранов');root.append(tabs);
  for(const item of session.screens){const row=el('div',null,'rdg-tab');row.setAttribute('role','tab');row.setAttribute('tabindex',item.id===s.id?'0':'-1');row.setAttribute('aria-selected',String(item.id===s.id));row.dataset.screenId=item.id;
   const tab=button(row,'',()=>switchTab(item.id));tab.setAttribute('aria-label',titleFor(item)+' · '+scopeTitle(item));tab.append(el('b',titleFor(item)),el('small',scopeTitle(item)));tab.title=tab.getAttribute('aria-label');button(row,'×',async()=>{await sync(v=>{const i=v.screens.findIndex(x=>x.id===item.id);v.screens.splice(i,1);if(v.activeScreenId===item.id)v.activeScreenId=v.screens[Math.min(i,v.screens.length-1)]?.id||null;if(!v.screens.length)v.explorer.open=true;});await load();}).setAttribute('aria-label','Закрыть вкладку');
   row.onkeydown=e=>{const i=session.screens.findIndex(x=>x.id===item.id);let next;if(e.key==='ArrowRight')next=(i+1)%session.screens.length;if(e.key==='ArrowLeft')next=(i-1+session.screens.length)%session.screens.length;if(e.key==='Home')next=0;if(e.key==='End')next=session.screens.length-1;if(next!=null){e.preventDefault();void run(()=>switchTab(session.screens[next].id));}};tabs.append(row);if(item.id===s.id)queueMicrotask(()=>row.scrollIntoView({block:'nearest',inline:'nearest'}));
  }
  button(tabs,'+',async()=>{await sync((v,s)=>{const next=clone(s);next.id=uid();v.screens.push(next);v.activeScreenId=next.id;});await load();}).setAttribute('aria-label','Новая вкладка');
  const tools=el('nav',null,'rdg-row rdg-tools');tools.setAttribute('aria-label','Рабочие панели');root.append(tools);
  button(tools,'Весь процесс',()=>changeView({kind:'graph',id:undefined,groupIds:[]}));
  if(work){const bankToggle=button(tools,'Контекст процесса',()=>{contextBank.open=!contextBank.open;render();});
   bankToggle.className='rdg-context-bank-toggle';bankToggle.dataset.contextBankToggle='';bankToggle.setAttribute('aria-expanded',String(contextBank.open));
   bankToggle.setAttribute('aria-controls','rdg-process-context-bank');
   bankToggle.title='Общий банк фактов этого Process Graph, независимо от рабочей области или фокуса';}
  select(tools,'Область',[['','Весь процесс'],...snapshot.graph.workGraphs.map(w=>[w.id,w.title])],area?.id||'',id=>run(()=>changeView(id?{kind:'workGraph',id,groupIds:[]}:{kind:'graph',id:undefined,groupIds:[]})));
  const mode=s.presentation?.mode==='questions'&&!work?'graph':s.presentation?.mode||'graph',switcher=el('div',null,'rdg-presentation-modes');root.dataset.mode=mode;switcher.setAttribute('role','group');switcher.setAttribute('aria-label','Режим представления');tools.append(switcher);
  for(const [value,label] of [['graph','Граф'],['structure','Структура'],['markdown','Markdown']]){const toggle=button(switcher,label,()=>sync((v,t)=>{t.presentation??={mode:'graph',expandedPaths:[],collapsedPaths:[],query:''};t.presentation.mode=value;},true));toggle.setAttribute('aria-pressed',String(mode===value));toggle.dataset.presentationMode=value;}
  if(mode==='graph')button(tools,'Вписать',()=>fitGraph());
  if(work){const qCount=snapshot.graph.objects.filter(n=>n.kind==='question').length;
   const questionsButton=button(tools,'Вопросы · '+qCount,()=>openQuestions());
   questionsButton.dataset.questionsWorkspaceButton='';
   questionsButton.setAttribute('aria-pressed',String(mode==='questions'));
  }
  if(work){const openDependencies=button(tools,'Зависимости',()=>sync((v,t)=>{
   t.presentation??={mode:'graph',expandedPaths:[],collapsedPaths:[],query:''};
   t.presentation.mode='dependencies';t.presentation.dependencyTab??='stale';},true));
   openDependencies.dataset.dependencyWorkspaceButton='';openDependencies.setAttribute('aria-pressed',String(mode==='dependencies'));}
  const viewMenu=menu(tools,'Вид ⚙');if(mode==='graph')field(viewMenu,'Показать исключённые варианты',s.spec.showExcludedAlternatives||false,'checkbox',value=>run(()=>changeView({showExcludedAlternatives:value}))).dataset.view='variants';field(viewMenu,'Низкоуровневые операции',s.spec.showLowLevel||false,'checkbox',value=>run(()=>changeView({showLowLevel:value})));
  if(mode==='graph'&&s.spec.kind!=='focus')field(viewMenu,'Показать Info-блоки',s.spec.showAllBlocks===true,'checkbox',value=>run(()=>changeView({showAllBlocks:value}))).dataset.view='allBlocks';
  if(mode==='graph')button(viewMenu,'Сохранить раскладку',()=>persistGraph());
  tools.append(el('span',null,'rdg-spacer'));
  if(work){button(tools,s.panels.roadVisible?'Скрыть Plan / History':'Показать Plan / History',()=>sync((v,t)=>{t.panels.roadVisible=!t.panels.roadVisible;t.panels.roadTab='timeline';},true));}
  button(tools,'Сведения',()=>sync((v,s)=>s.inspector={kind:'entity',id:s.spec.kind==='focus'?s.spec.id:snapshot.graph.rootRequirementId},true));button(tools,'Пакеты линз',()=>showForm('attachments'),registry.unavailable);
  button(tools,'+ Блок',()=>showForm('add'),snapshot.immutableDefinition);
  const actions=menu(tools,'Действия ▾','rdg-actions');button(actions,'Рекомендации процесса',()=>sync((v,s)=>s.inspector={kind:'recommendationScope',scopeKind:'process'},true));if(area)button(actions,'Рекомендации области',()=>sync((v,s)=>s.inspector={kind:'recommendationScope',scopeKind:'workGraph',id:area.id},true));button(actions,'Рабочая область',()=>showForm('workGraph',{newArea:true}),!work||snapshot.immutableDefinition);button(actions,'Группа решений',()=>showForm('group'),snapshot.immutableDefinition);button(actions,'Связь',()=>showForm('relation'),snapshot.immutableDefinition);button(actions,'Сохранить как готовый граф…',()=>showForm('capture'));button(actions,'Копировать…',()=>showForm('copy'));
  if(snapshot.package.role==='ready')button(actions,'Вставить в процесс…',()=>showForm('insert',{sourcePackageId:snapshot.package.packageId}));
  if(work){button(actions,'+ Размещение',()=>showForm('place'));button(actions,'Ветвление Plan',()=>showForm('fork'));button(actions,'Границы показа',()=>openRoadControls('windows'));}
  if(screen().draft?.form?.mode&&!form)button(tools,'Продолжить черновик',()=>{form=screen().draft.form.mode;return sync((v,s)=>s.draft.open=true,true);});
  const status=el('p',message||scopeTitle(s)+' · '+snapshot.graph.title,'rdg-status');status.setAttribute('role','status');status.classList.toggle('rdg-error',error);root.append(status);
  if(area){const bar=el('div',null,'rdg-scope');bar.setAttribute('aria-label','Рабочая область');bar.dataset.workgraphId=area.id;const title=el('div');title.append(el('small','Working Graph · рабочая область'),el('b',area.title),el('span',' · '+area.memberIds.length+' блоков процесса','rdg-muted'));bar.append(title);button(bar,'Состав…',()=>showForm('workGraph',{workGraphId:area.id}));button(bar,'Внешние связи · '+areaEdges(area).length,()=>sync((v,s)=>s.inspector={kind:'boundaries',workGraphId:area.id},true));button(bar,'Процесс-граф ↗',()=>changeView({kind:'graph',id:undefined,groupIds:[]}));root.append(bar);}
  else if(!work){const bar=el('div',null,'rdg-scope rdg-ready');const title=el('div');title.append(el('small',snapshot.package.role==='lens'?'Граф линзы':'Шаблон графа'),el('b',snapshot.graph.title));bar.append(title);if(snapshot.package.role==='ready')button(bar,'Вставить в процесс…',()=>showForm('insert',{sourcePackageId:snapshot.package.packageId}));root.append(bar);}
  if(searchView?.open)renderTextSearch(root);
  const body=el('main',null,'rdg-body');root.append(body);if(session.explorer.open)renderExplorer(root);
  if(mode==='dependencies')renderDependencyWorkspace(body);
  else if(mode==='questions'&&work)renderQuestionsWorkspace(body);
  else{const workspace=el('div',null,'rdg-workspace');body.append(workspace);const canvas=el('section',null,mode==='structure'?'rdg-canvas rdg-structure-canvas':'rdg-canvas');canvas.setAttribute('aria-label',mode==='structure'?'Структура графа':mode==='markdown'?'Структурный Markdown':'Граф работы');workspace.append(canvas);if(mode==='structure')renderStructure(canvas);else if(mode==='markdown')renderMarkdown(canvas);else renderGraph(canvas);if(s.inspector)renderInspector(workspace);}
  if(mode!=='dependencies'&&work&&s.panels.roadVisible){const split=el('div',null,'rdg-split');split.setAttribute('role','separator');split.setAttribute('tabindex','0');body.append(split);let drag=null;
   split.onpointerdown=e=>{drag={x:e.clientX,width:s.panels.roadWidth};split.setPointerCapture(e.pointerId);};split.onpointermove=e=>{if(!drag)return;const width=Math.max(300,Math.min(body.clientWidth*.6,drag.width+drag.x-e.clientX));const road=body.querySelector('.rdg-road');if(road)road.style.width=width+'px';};split.onpointerup=e=>{if(!drag)return;const width=Math.max(300,Math.min(body.clientWidth*.6,drag.width+drag.x-e.clientX));drag=null;void run(()=>sync((v,s)=>s.panels.roadWidth=width));};
   split.onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();void run(()=>sync((v,s)=>s.panels.roadWidth=Math.max(300,Math.min(1000,s.panels.roadWidth+(e.key==='ArrowLeft'?25:-25))),true));}};
   renderRoad(body);
  }
  const footer=el('footer',null,'rdg-footer');footer.append(el('span',work?'Process Graph · '+snapshot.graph.title:scopeTitle(s)),el('span','Decision UI · 20261029-fix2'));root.append(footer);
  if(work&&contextBank.open)renderContextBank(root);
  if(pending)renderPreview(root);else if(form)renderForm(root);else if(policyInstancesView)renderPolicyInstances(root);
 }

 const inspectorTabState=new Map();
 const outlineScroll=new Map();
 function contextPath(id){const groups=new Map((snapshot.graph.contextGroups||[]).map(g=>[g.id,g])),names=[],seen=new Set();while(groups.has(id)&&!seen.has(id)){seen.add(id);const g=groups.get(id);names.unshift(g.title);id=g.parentId;}return names.join(' / ');}
 function contextChoices(){return [['','Без группы'],...(snapshot.graph.contextGroups||[]).map(g=>[g.id,contextPath(g.id)]).sort((a,b)=>a[1].localeCompare(b[1],'ru'))];}
 function sourceTitle(n){return (kindCode[n.kind]||n.kind)+' · '+n.title+(n.contextGroupId?' · '+contextPath(n.contextGroupId):'');}
 function theoryCanons(n){return [n.canons||'',...(n.knownErrors||[]).map(e=>[e.title,e.description].filter(Boolean).join('\n'))].filter(Boolean).join('\n\n');}
 function theoryExcerpt(n){return [theoryCanons(n)&&'Каноны: '+theoryCanons(n),n.guidance&&'Общее: '+n.guidance].filter(Boolean).join('\n\n');}
 function theoryContent(parent,n){
  const box=el('div',null,'rdg-theory-content');box.dataset.theoryId=n.id;parent.append(box);
  for(const [label,value] of [['Каноны',theoryCanons(n)],['Общее',n.guidance]]){box.append(el('h4',label),el('p',value||'Не заполнено','rdg-canon-guidance'));}
 }
 function analysisSources(id){const n=policyEntities().get(id);return n?[{sourceId:n.id,revision:n.revision,excerpt:(n.kind==='canon'?theoryExcerpt(n):n.value)||n.description||n.title}]:[];}
 function renderContextBank(parent){
  if(!isProcess())return;
  if(contextBank.groupId&&!(snapshot.graph.contextGroups||[]).some(g=>g.id===contextBank.groupId))contextBank.groupId=null;
  const facts=processContexts().slice().sort((a,b)=>a.title.localeCompare(b.title,'ru')||a.id.localeCompare(b.id));
  const bank=el('aside',null,'rdg-context-bank');bank.id='rdg-process-context-bank';
  bank.setAttribute('aria-label','Контекст процесса');bank.dataset.packageId=screen().packageId;
  parent.append(bank);
  const header=el('div',null,'rdg-context-bank-head');bank.append(header);
  header.append(el('strong','Контекст процесса · '+facts.length));
  const close=button(header,'Закрыть',()=>{contextBank.open=false;render();});
  close.setAttribute('aria-label','Закрыть банк контекстов');
  bank.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();contextBank.open=false;render();}};
  bank.append(el('p','Общий банк фактов Process Graph. Контексты не являются родителями и не входят в дерево R/D/Act. В рабочих областях и фокусах используются те же ID.','rdg-context-bank-desc'));
  const searchRow=el('div',null,'rdg-context-bank-search');bank.append(searchRow);
  const search=el('input');search.type='search';search.placeholder='Поиск по фактам, содержанию или ID';
  search.setAttribute('aria-label','Поиск по контекстам процесса');search.value=contextBank.query;
  searchRow.append(search);
  const list=el('div',null,'rdg-context-bank-scroll');bank.append(list);
  const writable=!snapshot.immutableDefinition;
  if(writable){
   const add=button(searchRow,'+ Ctx',()=>showForm('add',{processContextBank:true,kind:'context',parentId:'',workGraphId:'',contextGroupId:contextBank.groupId||''}));
   add.setAttribute('aria-label','Добавить контекст процесса');
   add.dataset.contextBankAdd='';
   button(searchRow,'Группа +',()=>showForm('contextGroup',{groupId:uid(),parentGroupId:contextBank.groupId||''}));
  }
  const references=id=>{
   const inDecisions=snapshot.graph.nodes.filter(n=>n.kind==='decision'&&(snapshot.decisionContexts?.[n.id]||[]).some(r=>r.sourceId===id));
   const viaEdges=(snapshot.graph.edges||[]).filter(e=>!e.archived&&['CONTEXT_FOR','EVIDENCE_FOR'].includes(e.type)&&e.from===id);
   return {inDecisions,viaEdges};
  };
  const redraw=()=>{
   list.replaceChildren();
   list.append(el('small','Добавлять в: '+(contextPath(contextBank.groupId)||'Без группы'),'rdg-muted'));
   const q=contextBank.query.toLocaleLowerCase().trim();
   const filtered=facts.filter(n=>!q||[n.title,n.description,n.value,n.id,contextPath(n.contextGroupId)].some(x=>String(x||'').toLocaleLowerCase().includes(q)));
   list.append(el('p','Найдено: '+filtered.length,'rdg-muted'));
   if(!facts.length)list.append(el('p','В этом процессе пока нет контекстов. Добавь первый факт через «+ Ctx».','rdg-context-bank-desc'));
   else if(!filtered.length)list.append(el('p','По запросу ничего не найдено.','rdg-muted'));
   function appendFact(fact,depth){
    const refs=references(fact.id),item=button(list,'',()=>{contextBank.selectedId=fact.id;redraw();});
    item.className='rdg-context-bank-item';item.style.marginLeft=(depth*12)+'px';item.style.width='calc(100% - '+(depth*12)+'px)';item.dataset.contextId=fact.id;
    item.setAttribute('aria-pressed',String(contextBank.selectedId===fact.id));colorize(item,'context');
    item.append(el('span','Ctx','rdg-outline-kind'));
    const copy=el('span',null,'rdg-context-bank-copy');
    copy.append(el('b',fact.title),el('small',refs.inDecisions.length+' решений с прямой ссылкой'+(refs.viaEdges.length?' · '+refs.viaEdges.length+' ссылок на данные':'')));
    item.append(copy);
   }
   const projection=(typeof module==='object'&&module.exports?require('./rdg-visual-projection.js'):globalThis.RDGVisualProjection);
   contextBank.collapsed??=new Set();
   let ungroupedShown=false;
   for(const entry of projection.contextTree(contextBankGraph(),{query:contextBank.query,collapsedIds:[...contextBank.collapsed]})){
    if(entry.type==='context'){if(entry.depth===0&&!ungroupedShown){list.append(el('small','Без группы','rdg-muted'));ungroupedShown=true;}appendFact(facts.find(n=>n.id===entry.id),entry.depth);continue;}
    const line=el('div',null,'rdg-row');line.style.marginLeft=(entry.depth*12)+'px';line.dataset.contextGroupId=entry.id;
    const toggle=button(line,(entry.expanded?'▾ ':'▸ ')+entry.title,()=>{if(entry.id!==legacyRecordGroupId())contextBank.groupId=entry.id;if(contextBank.collapsed.has(entry.id))contextBank.collapsed.delete(entry.id);else contextBank.collapsed.add(entry.id);redraw();});
    toggle.setAttribute('aria-expanded',String(entry.expanded));toggle.setAttribute('aria-label',(entry.expanded?'Свернуть группу ':'Раскрыть группу ')+entry.title);
    if(writable&&entry.id!==legacyRecordGroupId())button(line,'⋯',()=>showForm('contextGroup',{groupId:entry.id}));list.append(line);
   }
   const selected=facts.find(n=>n.id===contextBank.selectedId);
   if(!selected)return;
   const details=el('article',null,'rdg-context-bank-entry');details.dataset.contextId=selected.id;list.append(details);
   details.append(el('h3',selected.title),el('small','Ctx · '+selected.id));
   if(selected.description)details.append(el('p',selected.description));
   if(selected.value)details.append(el('p',selected.value));
   const provenance=el('details');provenance.append(el('summary','Источник и вложение'));let hasProvenance=false;for(const [key,label] of [['scope','Область'],['source','Источник'],['version','Версия']])if(selected[key]){provenance.append(el('p',label+': '+selected[key]));hasProvenance=true;}if(selected.artifact){provenance.append(el('pre',JSON.stringify(selected.artifact,null,2)));hasProvenance=true;}if(hasProvenance)details.append(provenance);
   if(!selected.value&&!selected.description)details.append(el('p','Содержание пока не задано.','rdg-muted'));
   const refs=references(selected.id);
   if(refs.inDecisions.length||refs.viaEdges.length){
    details.append(el('h3','Используется в процессе'));
    const referenced=new Set([...refs.inDecisions.map(n=>n.id),...refs.viaEdges.map(e=>e.to)]);
    for(const id of referenced){
     const target=[...snapshot.graph.nodes,...snapshot.graph.objects].find(n=>n.id===id);
     if(target)entityReference(details,target,()=>focusNode(id));
    }
   }
   if(writable&&selected.kind==='evidence'){details.append(el('p','Прежняя запись подтверждения. Перевод сохраняет ID, данные, вложение и ссылки.','rdg-muted'));button(details,'Перевести в контекст',()=>showForm('contextRecord',{nodeId:selected.id}));}
   if(writable&&selected.kind!=='evidence'){
    const actions=el('div',null,'rdg-row');details.append(actions);
    button(actions,'Переименовать',()=>showForm('rename',{nodeId:selected.id,title:selected.title}));
    button(actions,'Изменить содержание',()=>showForm('content',{nodeId:selected.id}));
    button(actions,'Переместить',()=>showForm('contextMove',{nodeId:selected.id}));
    button(actions,'Удалить',()=>showForm('command',{nodeId:selected.id,command:'delete'}));
   }
  };
  search.oninput=()=>{contextBank.query=search.value;redraw();};
  redraw();
 }
 const decisionGroupPalette=Object.freeze([
  '#86A9B9', // steel blue
  '#B89BB4', // dusty lilac
  '#83ADA7', // muted teal
  '#A8AD83', // muted olive
  '#BE9B9E', // dusty rose
  '#BC9B85', // soft terracotta
  '#8D9FC1', // cool blue
  '#94AD97', // sage green
  '#A69CBD', // dusty lavender
  '#B5AB87'  // muted sand
 ]);
 function decisionGroupColor(id){
  // Hash only the canonical group ID: creating a new group cannot recolor an
  // existing one, including in WorkGraph/Focus or after a catalog refresh.
  let hash=2166136261;
  for(const ch of String(id))hash=Math.imul(hash^ch.charCodeAt(0),16777619);
  return decisionGroupPalette[(hash>>>0)%decisionGroupPalette.length];
 }
 async function revealCreatedDecision(id){
  if(!snapshot.view.entities.some(n=>n.id===id)){
   await sync((v,s)=>{recordView(s);s.spec={...s.spec,kind:'graph',groupIds:[]};
    for(const key of ['id','workGraphId','focusPositions','camera'])delete s.spec[key];
   });await load();
  }
  const projection=(typeof module==='object'&&module.exports?require('./rdg-visual-projection.js'):globalThis.RDGVisualProjection);
  const paths=projection.decisionOutline(snapshot.graph,snapshot.view,{
   ...screen().presentation,query:'',revealEntityId:id,hideProcessContexts:isProcess()
  }).revealPaths;
  await sync((v,s)=>{s.presentation??={mode:'graph',expandedPaths:[],collapsedPaths:[],query:''};
   const p=s.presentation,required=new Set(paths);
   p.expandedPaths=[...new Set([...(p.expandedPaths||[]).filter(key=>!required.has(key)),...paths])].slice(-512);
   p.collapsedPaths=(p.collapsedPaths||[]).filter(key=>!required.has(key));p.query='';
  },true);
  const row=[...root.querySelectorAll('.rdg-outline-row')].find(n=>n.dataset.entityId===id&&!n.dataset.parentRef);
  row?.scrollIntoView({block:'nearest',inline:'nearest'});
 }
 function renderStructure(parent){
  closeStructureContextMenu(); // Close any previous menu and drop its listeners.
  const screenState=screen(),presentation=screenState.presentation||{mode:'structure',expandedPaths:[],collapsedPaths:[],query:''};
  const projection=(typeof module==='object'&&module.exports?require('./rdg-visual-projection.js'):globalThis.RDGVisualProjection);
  if(!projection?.decisionOutline)throw Error('Режим «Структура» недоступен в этой сборке Viewer.');
  const outline=projection.decisionOutline(snapshot.graph,snapshot.view,{...presentation,hideProcessContexts:isProcess()});
  const area=activeArea(),head=el('div',null,'rdg-outline-head');parent.append(head);
  const title=screenState.spec.kind==='focus'?'Фокус · '+(snapshot.graph.nodes.concat(snapshot.graph.objects).find(n=>n.id===screenState.spec.id)?.title||screenState.spec.id):
    groupHeading(screenState)|| (area?'Область · '+area.title:snapshot.package.role==='ready'?'Готовый граф':snapshot.package.role==='lens'?'Граф линзы':'Весь процесс');
  head.append(el('strong',title));
  if(openedDecisionGroup(screenState))head.append(el('small','Родитель группы · R · '+groupParentTitle(openedDecisionGroup(screenState))));
  head.append(el('small',outline.structuralCount+' структурных · '+outline.materialCount+' вспомогательных'));
  const search=el('label','Поиск'),searchInput=el('input');searchInput.type='search';searchInput.value=presentation.query||'';
  searchInput.placeholder='Блок, ID или группа';searchInput.maxLength=180;searchInput.setAttribute('aria-label','Поиск по структуре');search.append(searchInput);head.append(search);
  const find=()=>sync((v,s)=>{s.presentation??={mode:'structure',expandedPaths:[],collapsedPaths:[],query:''};s.presentation.query=searchInput.value.trim();},true);
  searchInput.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();void run(find);}};
  button(head,'Найти',find);
  if(presentation.query)button(head,'Сбросить',()=>sync((v,s)=>{s.presentation.query='';},true));
  if(screenState.viewTrail?.length)button(head,'← Назад',()=>viewBack(screenState.viewTrail.length-1));
  const scroller=el('div',null,'rdg-outline-scroll');parent.append(scroller);
  const scrollKey=screenState.id+'|'+screenState.packageId+'|'+screenState.spec.kind+'|'+(screenState.spec.id||'');
  const savedScroll=outlineScroll.get(scrollKey);
  // Old in-memory entries stored just a vertical number; retain compatibility.
  scroller.scrollTop=typeof savedScroll==='number'?savedScroll:savedScroll?.top||0;
  scroller.scrollLeft=typeof savedScroll==='number'?0:savedScroll?.left||0;
  scroller.onscroll=()=>outlineScroll.set(scrollKey,{top:scroller.scrollTop,left:scroller.scrollLeft});
  scroller.addEventListener('wheel',e=>{
   if(!e.shiftKey||e.ctrlKey||e.metaKey||scroller.scrollWidth<=scroller.clientWidth)return;
   const multiplier=e.deltaMode===1?24:e.deltaMode===2?scroller.clientWidth:1;
   const delta=(e.deltaY||e.deltaX)*multiplier;
   if(!delta)return;
   e.preventDefault();scroller.scrollLeft+=delta;
  },{passive:false});
  const tree=el('div',null,'rdg-outline-tree');tree.setAttribute('role','tree');tree.setAttribute('aria-label','Структурная иерархия Graph');scroller.append(tree);
  const sectionIcons={parents:'Par',requirements:'R',groups:'DG',decisions:'D',actions:'Act',
   context:'Ctx',info:'Inf',evidence:'Ctx',finding:'F',finding:'F'};
  async function togglePath(row){await sync((v,s)=>{
    s.presentation??={mode:'structure',expandedPaths:[],collapsedPaths:[],query:''};
    const p=s.presentation,expanded=new Set(p.expandedPaths||[]),collapsed=new Set(p.collapsedPaths||[]);
    if(row.expanded){expanded.delete(row.key);collapsed.add(row.key);}else{collapsed.delete(row.key);expanded.add(row.key);}
    p.expandedPaths=[...expanded].slice(-512);p.collapsedPaths=[...collapsed].slice(-512);
  },true);}
  function openContextMenu(event,item,line){
   if(item.type!=='entity'&&!(item.type==='section'&&item.section!=='parents'))return;
   event.preventDefault();event.stopPropagation();closeStructureContextMenu();
   const overlay=el('div',null,'rdg-outline-context-menu');overlay.dataset.outlineContextMenu='';
   overlay.setAttribute('role','menu');overlay.setAttribute('aria-label','Действия с блоком «'+item.title+'»');
   overlay.tabIndex=-1;overlay.append(el('div',item.title,'rdg-outline-context-title'));
   const controller=new AbortController();const {signal}=controller;
   let closed=false;
   const dismiss=({restoreFocus=false}={})=>{
    if(closed)return;closed=true;overlay.remove();controller.abort();
    if(restoreFocus&&line.isConnected)line.focus();
    if(closeStructureContextMenu===dismiss)closeStructureContextMenu=()=>{};
   };
   closeStructureContextMenu=dismiss;
   function command(label,action){
    const entry=el('button',label);entry.type='button';entry.setAttribute('role','menuitem');
    entry.onclick=()=>{dismiss();void run(action);};overlay.append(entry);return entry;
   }
   if(item.type==='section'){
    command('Развернуть элементы одного уровня',()=>togglePath(item));
   }else{
    if(item.sectionContext){
     command('Свернуть элементы одного уровня',()=>togglePath(item.sectionContext));
     overlay.append(el('div',item.sectionContext.title+' · '+item.sectionContext.count,'rdg-outline-context-hint'));
    }
    command('Открыть сведения',()=>sync((v,s)=>s.inspector={kind:'entity',id:item.entityId},true));
    command('Фокус',()=>focusNode(item.entityId));
   }
   parent.append(overlay);
   // A keyboard-generated contextmenu event normally has x=y=0.
   const box=line.getBoundingClientRect(),win=doc.defaultView;
   const pointer=event.clientX||event.clientY;
   const x=pointer?event.clientX:box.left+32,y=pointer?event.clientY:box.bottom;
   const menuBox=overlay.getBoundingClientRect();
   overlay.style.left=Math.max(8,Math.min(x,win.innerWidth-menuBox.width-8))+'px';
   overlay.style.top=Math.max(8,Math.min(y,win.innerHeight-menuBox.height-8))+'px';
   doc.addEventListener('pointerdown',e=>{if(!overlay.contains(e.target))dismiss();},
    {capture:true,signal});
   doc.addEventListener('keydown',e=>{
    if(e.key==='Escape'){e.preventDefault();e.stopPropagation();dismiss({restoreFocus:true});}
   },{capture:true,signal});
   scroller.addEventListener('scroll',()=>dismiss(),{passive:true,signal});
   const entry=overlay.querySelector('[role=menuitem]');entry?.focus();
  }
  for(const item of outline.rows){
   const line=el('div',null,'rdg-outline-row');line.style.setProperty('--outline-depth',String(item.depth));line.dataset.outlineType=item.type;line.dataset.outlineKey=item.key;line.dataset.outlineSection=item.section||'';line.dataset.kind=item.kind||'';
   line.setAttribute('role','treeitem');line.setAttribute('aria-level',String(item.depth+1));line.setAttribute('tabindex','-1');
   if(item.entityId)line.dataset.entityId=item.entityId;
   if(item.parentRef)line.dataset.parentRef='true';
   if(screenState.spec.kind==='focus'&&item.entityId===screenState.spec.id&&!item.parentRef)
    line.dataset.focusRoot='true';
   if(item.groupId)line.dataset.groupId=item.groupId;
   if(item.excluded)line.dataset.excluded='true';
   if(item.sectionContext){line.dataset.sectionContext=item.sectionContext.section;line.dataset.sectionContextKey=item.sectionContext.key;}
   if(item.hasChildren)line.setAttribute('aria-expanded',String(item.expanded));
   if(item.entityId&&screenState.inspector?.id===item.entityId)line.setAttribute('aria-current','true');
   // One real Decision row per structural parent, with one independently
   // inspectable property chip per group (including out-of-scope memberships).
   const memberships=item.type==='entity'&&item.kind==='decision'?item.groupMemberships||[]:[];
   let content=line;
   if(memberships.length){
    line.dataset.groupTags='true';
    const wrap=el('div',null,'rdg-outline-decision-wrap');line.append(wrap);
    const tags=el('div',null,'rdg-outline-group-tags');wrap.append(tags);
    for(const group of memberships){
     const rules=(group.mutuallyExclusive?'Взаимоисключающие':'Совместный выбор')+
      (group.selectionRequired?' · Выбрать ≥1':'');
     const caption=el('button',rules,'rdg-outline-group-caption');caption.type='button';
     caption.dataset.groupId=group.id;
     caption.style.setProperty('--rdg-group-color',decisionGroupColor(group.id));
     caption.onclick=()=>run(()=>showDecisionGroupDetails([group.id]));
     tags.append(caption);
    }
    content=el('div',null,'rdg-outline-decision-content');wrap.append(content);
   }
   // A Decision's own disclosure belongs INSIDE its card, just like R/Action.
   // A type-section collapse control remains outside on the parent row.
   if(item.hasChildren){const t=button(content,item.expanded?'▾':'▸',()=>togglePath(item));t.className='rdg-outline-toggle';t.setAttribute('aria-label',(item.expanded?'Свернуть':'Раскрыть')+' '+item.title);t.dataset.outlineToggle='';}
   else content.append(el('span','·','rdg-outline-toggle-spacer'));
   const symbol=el('span',item.parentRef?'Par '+(kindCode[item.kind]||'?'):
    item.type==='group'?'DG':item.type==='section'?sectionIcons[item.section]||'Mat':
      item.type==='materials'?'Mat':kindCode[item.kind]||'?','rdg-outline-kind');
   symbol.title=item.parentRef?'Структурный родитель · '+(kindLabel[item.kind]||item.kind):
    item.type==='group'?'Группа решений':item.type==='entity'?(kindLabel[item.kind]||item.kind):item.title;content.append(symbol);
   const display=el('button',null,'rdg-outline-body');display.type='button';display.append(el('span',item.title,'rdg-outline-title'));
   const detail=[];
   if(item.type==='group')detail.push((item.selectionRequired?'Выбор обязателен':'Выбор необязателен'),(item.mutuallyExclusive?'Взаимоисключение':'Совместный выбор'),item.selectedCount+'/'+item.memberCount+' выбрано');
   else if(['section','materials'].includes(item.type)){detail.push(item.count+' элементов');if(item.description)detail.push(item.description);}
   else if(item.type==='entity'){
    if(item.parentRef)detail.push('Родитель · '+(item.parentRelations||[]).join(', '),
      ...(item.parentGroups||[]).map(title=>'Группа «'+title+'»'));
    const completion=snapshot.completion?.[item.entityId];
    if(item.kind==='decision')detail.push(({selected:'Выбрано',unselected:'Не выбрано',discovered:'Найдено'}[item.selectionState]||'Решение'));
    else if(completion?.complete)detail.push('Завершено');
    else if(completion?.reviewRequired||item.reviewRequired)detail.push('Требует проверки');
    else if(completion&&!completion.active)detail.push('Нет действующего основания');
    else if(['requirement','action'].includes(item.kind))detail.push('Открыто');
    if(item.cycle)detail.push('Повтор в текущей ветке · раскрытие остановлено');
    if(item.multipleParents)detail.push('⧉ Несколько родителей');
    if(item.outsideParentIds?.length)detail.push('↗ Родитель вне области: '+item.outsideParentIds.length);
    if(item.excluded)detail.push('Исключённый вариант группы');
    if(item.supplemental){const sup=item.supplemental;
      if(sup.decisionContext)detail.push(sup.decisionContext+' фактов контекста решения');
      if(sup.processContext)detail.push(sup.processContext+' связанных контекстов');
      if(sup.info)detail.push(sup.info+' Info');
      if(sup.evidence)detail.push(sup.evidence+' Evidence');
      if(sup.dependency)detail.push(sup.dependency+' дополнительных зависимостей');
    }
   }
   if(detail.length)display.append(el('small',detail.join(' · '),'rdg-outline-meta'));
   if(item.type==='group')display.onclick=()=>run(()=>sync((v,s)=>s.inspector={kind:'group',ids:[item.groupId]},true));
   else if(item.entityId)display.onclick=()=>run(()=>sync((v,s)=>s.inspector={kind:'entity',id:item.entityId},true));
   else display.onclick=()=>run(()=>togglePath(item));
   content.append(display);
   if(['entity','group'].includes(item.type)&&item.workAreas?.length){const markers=el('span',null,'rdg-outline-area-markers');markers.setAttribute('aria-label','Рабочие области: '+item.workAreas.map(a=>a.title).join(', '));for(const [index,workArea] of item.workAreas.slice(0,6).entries()){const mark=el('i');mark.style.backgroundColor=workAreaColor(workArea,index);mark.title=workArea.title;markers.append(mark);}if(item.workAreas.length>6){const more=el('small','+'+(item.workAreas.length-6));more.title='Ещё рабочие области';markers.append(more);}content.append(markers);}
   if(item.type==='entity'){const target=button(content,'Фокус',()=>focusNode(item.entityId));target.className='rdg-outline-focus';target.setAttribute('aria-label','Фокус: '+item.title);}
   // Custom right-click actions apply to any sibling occurrence; the native
   // browser menu is suppressed only on Structure entity/section rows.
   if(item.type==='entity'||item.type==='section'&&item.section!=='parents')
    line.oncontextmenu=e=>openContextMenu(e,item,line);
   // Regular tree keyboard controls; mode/expanded state are only session data.
   line.onkeydown=e=>{
    if(e.target===line&&(e.key==='ContextMenu'||e.key==='F10'&&e.shiftKey)){
     e.preventDefault();openContextMenu(e,item,line);return;
    }
    if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){
     const rows=[...tree.querySelectorAll('.rdg-outline-row')],idx=rows.indexOf(line),target=e.key==='Home'?rows[0]:e.key==='End'?rows.at(-1):rows[Math.max(0,Math.min(rows.length-1,idx+(e.key==='ArrowDown'?1:-1)))];
     if(target){e.preventDefault();target.focus();}return;
   }if(e.target!==line)return;
    if(e.key==='ArrowRight'&&item.hasChildren&&!item.expanded||e.key==='ArrowLeft'&&item.hasChildren&&item.expanded){e.preventDefault();void run(()=>togglePath(item));}
    else if(e.key==='Enter'||e.key===' '){e.preventDefault();display.click();}
    else if(e.key==='f'||e.key==='F'){if(item.entityId){e.preventDefault();void run(()=>focusNode(item.entityId));}}
   };
   tree.append(line);
  }
  if(!outline.rows.length)scroller.append(el('p','В этом представлении нет доступных блоков.','rdg-outline-empty'));
  const note=el('div',null,'rdg-outline-note');note.textContent=(outline.truncated?'Показаны первые '+outline.rows.length+' строк. Сверните часть ветвей для навигации. · ':'')+
    (screenState.spec.kind==='focus'?'Par R / Par D — прямые родители выбранного блока; дочерняя ветвь показана один раз. ':
      '⧉ Повторные вхождения ссылаются на один объект. ')+
    'Цветные метки над D — принадлежность к группам решений; нажмите метку для сведений о группе. '+
    'Правый клик на блоке — меню действий со сворачиванием однотипных соседей. Shift+колесо — горизонтальная прокрутка. Дерево не изменяет Graph.';
  parent.append(note);
  fitGraph=()=>Promise.resolve();persistGraph=()=>Promise.resolve();graphSvg=null;
 }

 function renderGraph(parent){
  const raw=snapshot.view.visual||{nodes:[],routes:[],positions:{},occurrences:{},counts:{}},s=screen();
  // Filter illustrations, never the owning graph, and keep the complete
  // position maps for normal manual-layout updates (no silent loss of Ctx).
  const contextIds=isProcess()?new Set(processContexts().map(n=>n.id)):new Set();
  const nodes=raw.nodes.filter(n=>!contextIds.has(n.entityId));
  const included=new Set(nodes.map(n=>n.id));
  const picture=contextIds.size?{...raw,nodes,routes:raw.routes.filter(r=>included.has(r.from)&&included.has(r.to))}:raw;
  const area=activeArea(),canvasHead=el('div',null,'rdg-canvas-head');
  canvasHead.append(el('span',s.spec.kind==='focus'?'Фокус · '+(snapshot.view.entities.find(n=>n.id===s.spec.id)?.title||s.spec.id):
   groupHeading(s)|| (area?'Рабочая область · '+area.title:snapshot.package.role==='lens'?'Граф линзы':snapshot.package.role==='ready'?'Шаблон графа':'Процесс-граф · весь процесс'),'rdg-crumb'));
  const openedGroup=openedDecisionGroup(s);
  if(openedGroup){const parent=el('span','Родитель группы · '+(kindCode[snapshot.graph.nodes.find(n=>n.id===openedGroup.parentId)?.kind]||'R')+' · '+groupParentTitle(openedGroup),'rdg-crumb rdg-group-parent-crumb');parent.dataset.groupParentId=openedGroup.parentId;canvasHead.append(parent);}
  const navTrail=s.viewTrail||[];
  if(navTrail.length){
   const crumbs=el('nav',null,'rdg-view-trail');crumbs.setAttribute('aria-label','История переходов по графу');
   const name=spec=>spec.kind==='focus'?(snapshot.graph.nodes.concat(snapshot.graph.objects,snapshot.graph.externalActions).find(n=>n.id===spec.id)?.title||spec.id):
    spec.kind==='workGraph'?(snapshot.graph.workGraphs.find(w=>w.id===spec.id)?.title||'Рабочая область'):
    spec.groupIds?.length?'Группа решений · '+(snapshot.graph.decisionGroups.find(g=>g.id===spec.groupIds[0])?.title||spec.groupIds[0]):'Весь процесс';
   button(crumbs,'← Назад',()=>viewBack(navTrail.length-1)).dataset.graphBack='';
   navTrail.slice(-4).forEach((item,j)=>{const idx=navTrail.length-Math.min(navTrail.length,4)+j;
    button(crumbs,name(item.spec),()=>viewBack(idx)).title='Вернуться к предыдущему виду';});
   canvasHead.append(crumbs);
  }
  canvasHead.append(el('span',picture.nodes.length+' изображений','rdg-selection'));parent.append(canvasHead);

  const compactMode=s.spec.kind!=='focus'&&s.spec.compactGraph!==false;
  const positions=clone(s.draft?.layout?.positions||picture.positions),occurrences=clone(s.draft?.layout?.occurrences||picture.occurrences);
  const visualPosition=id=>occurrences[id]||positions[id],points=picture.nodes.map(n=>visualPosition(n.id)).filter(Boolean);
  // Use the visible nodes' actual extents, not the process origin (0,0).
  // Otherwise an off-origin WorkGraph appears tiny after an automatic fit.
  const bounds=()=>{if(!points.length)return {x:0,y:0,width:600,height:380};
   const xs=points.map(p=>p.x),ys=points.map(p=>p.y),x=Math.min(...xs)-55,y=Math.min(...ys)-60;
   return {x,y,width:Math.max(550,Math.max(...xs)+220+65-x),height:Math.max(340,Math.max(...ys)+126+65-y)};};
  const initialCamera=()=>{const frame=bounds();
   if(compactMode&&points.length>10){
    // Fit-for-reading, rather than making 20+ cards illegibly small.
    const width=Math.min(frame.width,1560),height=Math.min(frame.height,860);
    return {x:frame.x+(frame.width-width)/2,y:frame.y,width,height};
   }
   return frame;
  };
  let camera=clone(s.spec.camera||initialCamera());
  if(!s.spec.camera)void sync((v,s)=>{s.spec.camera??=camera;}).catch(e=>note(e.message,true));
  const ns='http://www.w3.org/2000/svg',svg=doc.createElementNS(ns,'svg');svg.classList.add('rdg-graph');svg.setAttribute('tabindex','0');svg.setAttribute('aria-label','Граф процесса');svg.setAttribute('role','img');parent.append(svg);graphSvg=svg;
  function append(tag,attrs,text,target=svg){const n=doc.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text!=null)n.textContent=text;if(tag==='text'){if(attrs['font-size'])n.style.fontSize=attrs['font-size']+'px';if(attrs.fill)n.style.fill=attrs.fill;}target.append(n);return n;}
  const setCamera=()=>svg.setAttribute('viewBox',[camera.x,camera.y,camera.width,camera.height].join(' '));setCamera();
  const defs=append('defs',{}),marker=append('marker',{id:'rdg-arrow',viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:5,markerHeight:5,orient:'auto'},null,defs);append('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#829fb5'},null,marker);
  const lines=[],pathLines=[],seenGroups=new Set();
  // Render group labels in a foreground SVG layer, above opaque entity cards.
  const groupLabelLayer=append('g',{class:'rdg-decision-group-labels','aria-label':'Подписи групп решений'});
  const nodeHeight=id=>picture.nodes.find(n=>n.id===id)?.alias&&s.spec.kind!=='focus'?126:
    picture.supportingCounts?.[picture.nodes.find(n=>n.id===id)?.entityId]?116:100;
  const visualEntityId=id=>picture.nodes.find(n=>n.id===id)?.entityId||id;
  function routeGeometry(route){const a=visualPosition(route.from),b=visualPosition(route.to);if(!a||!b)return null;const vertical=Math.abs(b.y-a.y)>Math.abs(b.x-a.x);let x1=a.x+110,y1=a.y+nodeHeight(route.from)/2,x2=b.x+110,y2=b.y+nodeHeight(route.to)/2,d;
   if(vertical){y1=a.y+(b.y>a.y?nodeHeight(route.from):0);y2=b.y+(b.y>a.y?0:nodeHeight(route.to));const middle=(y1+y2)/2;d=`M${x1} ${y1} C${x1} ${middle} ${x2} ${middle} ${x2} ${y2}`;}else{x1=a.x+(b.x>a.x?220:0);x2=b.x+(b.x>a.x?0:220);const middle=(x1+x2)/2;d=`M${x1} ${y1} C${middle} ${y1} ${middle} ${y2} ${x2} ${y2}`;}return {d,x:(x1+x2)/2,y:(y1+y2)/2-9,vertical};}
  for(const route of picture.routes){const shape=routeGeometry(route);if(!shape)continue;const e=route.edge,isGroup=e.type==='DECISION_MEMBER',key=route.from+'|'+route.to;if(isGroup&&seenGroups.has(key))continue;if(isGroup)seenGroups.add(key);
   const context=['CANON_FOR','CONTEXT_FOR','DEPENDS_ON','INFO_FOR'].includes(e.type),semanticStroke=isGroup?'#b6a4e2':e.type==='REQUIRES_ACTION'?'#8bd0b8':'#68849c';
   const fromId=visualEntityId(route.from),toId=visualEntityId(route.to),edgeAreas=(snapshot.graph.workGraphs||[]).filter(w=>(w.memberIds||[]).includes(fromId)&&(w.memberIds||[]).includes(toId));
   const line=append('path',{d:shape.d,fill:'none',stroke:edgeAreas.length===1?workAreaColor(edgeAreas[0]):semanticStroke,
    'stroke-width':edgeAreas.length===1?2.8:edgeAreas.length>1?1.2:2,'stroke-dasharray':isGroup?'3 4':context?'6 5':'',
    'marker-end':'url(#rdg-arrow)','data-relation-id':e.id});
   pathLines.push([route,line]);
   if(edgeAreas.length>1)for(const [index,workArea] of edgeAreas.entries()){
    const offset=(index-(edgeAreas.length-1)/2)*3;
    const accent=append('path',{d:shape.d,fill:'none',stroke:workAreaColor(workArea,index),'stroke-width':1.8,
     'stroke-dasharray':isGroup?'3 4':context?'6 5':'','pointer-events':'none','data-workgraph-id':workArea.id});
    pathLines.push([route,accent,offset]);
   }
   const ids=isGroup?[...new Set((picture.groupLabels||[]).filter(m=>m.from===e.from&&m.to===e.to).map(m=>m.groupId))]:[];
   const fullCaption=isGroup?ids.map(id=>{const g=snapshot.graph.decisionGroups.find(g=>g.id===id);return g?(id.length<12?id:'G'+(snapshot.graph.decisionGroups.indexOf(g)+1))+' '+(g.selectionRequired?'●':'○')+(g.mutuallyExclusive?'●':'○'):id;}).join(' / '):({DERIVES:'Обязательная под-R',INTRODUCES:'Обязательная под-R',REQUIRES_ACTION:'Обязательное действие',DRIVES:'Вариант решения',FINDING_RESPONSE:'Разрешить файндинг',FINDING_PROPOSAL:'Proposal',CANON_FOR:'Ориентиры качества',CONTEXT_FOR:'Контекст',INFO_FOR:'Пояснение',DEPENDS_ON:'Зависимость'}[e.type]||e.type);
   append('title',{},fullCaption,line);
   // A star of identical outgoing links needs one readable caption, not one
   // text object for every crossing line. Full relation names remain in titles.
   // A compact badge on the real DECISION_MEMBER edge, not a new graph node.
   // Multiple group IDs on the same pair share the original single caption.
   if(!isGroup)continue;
   const caption=fullCaption,w=Math.max(32,caption.length*6+4);
   const leader=append('path',{class:'rdg-decision-group-leader',fill:'none',
    stroke:'#b6a4e2','stroke-width':1,'stroke-dasharray':'2 3','pointer-events':'none'},null,groupLabelLayer);
   const back=append('rect',{width:w+14,height:19,rx:5,fill:'#102231',stroke:'#a998d0',
    'stroke-width':1,class:'rdg-decision-group-badge','data-group':ids.join(',')},null,groupLabelLayer);
   const label=append('text',{'text-anchor':'middle','font-size':10,fill:'#d7c8ff',
    class:'rdg-decision-group-caption','data-group':ids.join(',')},caption,groupLabelLayer);
   append('title',{},ids.map(id=>{const g=snapshot.graph.decisionGroups.find(g=>g.id===id);
    return (g?.title||id)+' · '+id+' · '+(g?.selectionRequired?'Выбор обязателен':'Выбор необязателен')+
     ' · '+(g?.mutuallyExclusive?'Взаимоисключение':'Совместный выбор');}).join('; '),label);
   label.style.paintOrder='stroke';label.style.stroke='#102231';label.style.strokeWidth='2px';label.style.strokeLinejoin='round';
   lines.push([route,line,label,back,w,leader]);
   const open=event=>{event.stopPropagation();void run(()=>showDecisionGroupDetails(ids));};
   for(const target of [label,back]){target.style.pointerEvents='auto';target.style.cursor='pointer';target.onclick=open;}
   label.setAttribute('tabindex','0');label.setAttribute('role','button');
   label.setAttribute('aria-label','Сведения о группе решений: '+ids.join(','));
   label.onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();open(event);}};
  }
  function paintEdges(){
   const occupied=picture.nodes.map(item=>{const p=visualPosition(item.id);return p?{x:p.x-5,y:p.y-5,w:230,h:nodeHeight(item.id)+10}:null;}).filter(Boolean);
   const overlap=(a,b)=>a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h;
   for(const [route,line,areaOffset] of pathLines){const shape=routeGeometry(route);if(shape){line.setAttribute('d',shape.d);if(areaOffset!=null)line.setAttribute('transform',shape.vertical?`translate(${areaOffset} 0)`:`translate(0 ${areaOffset})`);}}
   // Sample other routed paths to keep badges off crossing connections.
   const pathPoints=new Map();
   for(const [,line] of pathLines){
    if(typeof line.getTotalLength!=='function')continue;
    try{
     const length=line.getTotalLength(),points=[];
     for(let i=2;i<=18;i++){const p=line.getPointAtLength(length*i/20);points.push({x:p.x,y:p.y});}
     pathPoints.set(line,points);
    }catch{/* A non-SVG test DOM need not implement geometry methods. */}
   }
   for(const [route,line,label,back,w,leader] of lines){
    const shape=routeGeometry(route);if(!shape)continue;
    const baseX=shape.x+(shape.vertical?(w/2+20):0),baseY=shape.y-(shape.vertical?0:8);
    let chosen=null;
    const place=(x,y,avoidCrossings)=>{
     const box={x:x-w/2-7,y:y-14,w:w+14,h:19};
     if(occupied.some(other=>overlap(box,other)))return null;
     if(avoidCrossings&&Array.from(pathPoints.entries()).some(([path,pts])=>
       path!==line&&pts.some(p=>p.x>=box.x-5&&p.x<=box.x+box.w+5&&p.y>=box.y-5&&p.y<=box.y+box.h+5)))return null;
     return {x,y,box};
    };
    // Prefer the edge midpoint, then find an unobstructed nearby location.
    // Unlike the old code, a dense layout never silently hides the group.
    for(const avoidCrossings of [true,false]){
     for(const radius of [0,26,52,78,104,156,208,260,338,416]){
      for(const offset of radius?[radius,-radius]:[0]){
       for(const horizontal of [0,26,-26,65,-65,130,-130]){
        chosen=place(baseX+horizontal,baseY+offset,avoidCrossings);
        if(chosen)break;
       }
       if(chosen)break;
      }
      if(chosen)break;
     }
     if(chosen)break;
    }
    if(!chosen){
     // Even a manually overlapping, fully crowded layout must retain a
     // discoverable badge; pick the least-obscuring nearby fallback.
     let best=null;
     for(const dy of [0,-30,30,-60,60,-100,100,-145,145]){
      for(const dx of [0,45,-45,95,-95,160,-160]){
       const x=baseX+dx,y=baseY+dy,box={x:x-w/2-7,y:y-14,w:w+14,h:19};
       const cost=occupied.reduce((sum,other)=>{
        const iw=Math.max(0,Math.min(box.x+box.w,other.x+other.w)-Math.max(box.x,other.x));
        const ih=Math.max(0,Math.min(box.y+box.h,other.y+other.h)-Math.max(box.y,other.y));
        return sum+iw*ih;
       },0)+(Math.abs(dx)+Math.abs(dy))*.05;
       if(!best||cost<best.cost)best={x,y,box,cost};
      }
     }
     chosen=best;
    }
    occupied.push(chosen.box);
    label.setAttribute('x',chosen.x);label.setAttribute('y',chosen.y);
    back.setAttribute('x',chosen.box.x);back.setAttribute('y',chosen.box.y);
    label.setAttribute('visibility','visible');back.setAttribute('visibility','visible');
    if(Math.hypot(chosen.x-shape.x,chosen.y-shape.y)>60){
     const x2=Math.max(chosen.box.x,Math.min(shape.x,chosen.box.x+chosen.box.w));
     const y2=Math.max(chosen.box.y,Math.min(shape.y,chosen.box.y+chosen.box.h));
     leader.setAttribute('d','M'+shape.x+' '+shape.y+' L'+x2+' '+y2);
     leader.setAttribute('visibility','visible');
    }else leader.setAttribute('visibility','hidden');
   }
  }
  const point=e=>{const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());};
  for(const item of picture.nodes){const p=visualPosition(item.id);if(!p)continue;const node=item.node,state=snapshot.completion[item.entityId]||{},g=append('g',{transform:`translate(${p.x},${p.y})`,tabindex:0,role:'button','aria-label':node.title,'data-entity-id':item.entityId,'data-occurrence-id':item.id,class:'rdg-node'});
   const [fill,line]=palette[node.kind]||palette.info,outside=!!area&&!area.memberIds.includes(item.entityId),height=nodeHeight(item.id),selected=s.spec.kind==='focus'&&s.spec.id===item.entityId;g.dataset.outsideWorkgraph=String(outside);
   const memberships=(snapshot.graph.workGraphs||[]).filter(w=>(w.memberIds||[]).includes(item.entityId));
   // Area membership is a small color marker, not another nested node border.
   // Multiple memberships share one narrow column; the canonical entity ID,
   // geometry, click target, semantic stroke and focus outline do not change.
   if(selected)append('rect',{x:-5,y:-5,width:230,height:height+10,rx:14,fill:'none',stroke:'#c0e7ff','stroke-width':2,opacity:.9},null,g);
   append('rect',{width:220,height,rx:10,fill,stroke:selected?'#c0e7ff':line,'stroke-width':selected?2:1,class:'rdg-node-border'},null,g);
   // SVG paint order: markers must follow the opaque card rectangle.
   // Earlier builds placed them behind the card and effectively hid them.
   const markerGap=memberships.length<=4?21:15,markerHeight=memberships.length<=4?18:13;
   for(const [index,workArea] of memberships.slice(0,6).entries()){
    const marker=append('rect',{x:203,y:7+index*markerGap,width:10,height:markerHeight,rx:2,
     fill:workAreaColor(workArea,index),stroke:'#0e1e2c','stroke-width':1,opacity:1,
     class:'rdg-node-area-marker','data-workgraph-id':workArea.id},null,g);
    append('title',{},'Рабочая область · '+workArea.title,marker);
   }
   if(memberships.length>6)append('text',{x:182,y:94,'font-size':9,fill:'#c7dfed',
    class:'rdg-node-area-more'},'+'+(memberships.length-6),g);
   const shortId=node.id.length>16?node.id.slice(0,8):node.id;append('title',{},(kindLabel[node.kind]||node.kind)+' · '+node.id+' · '+node.title+(memberships.length?' · Рабочие области: '+memberships.map(w=>w.title).join(', '):''),g);
   append('text',{x:14,y:22,'font-size':10,'font-weight':650,fill:line},(kindLabel[node.kind]||node.kind)+' · '+shortId+(item.alias?' · общая ветка':'')+(outside?' · вне области':''),g);
   const words=node.title.split(/\s+/),title=[];let lineText='';for(const word of words){if(lineText.length+word.length>27&&lineText){title.push(lineText);lineText='';}lineText+=(lineText?' ':'')+word;}if(lineText)title.push(lineText);for(const [i,text] of title.slice(0,2).entries())append('text',{x:14,y:45+i*18,'font-size':14,'font-weight':550,fill:'#edf5fc'},text.length>28?text.slice(0,27)+'…':i===1&&title.length>2?text.slice(0,26)+'…':text,g);
   const stateText=node.kind==='decision'?({discovered:'Обнаружено',unselected:'Не выбрано',selected:'Выбрано',completed:'Завершено'}[node.selectionState]||''):
     ['requirement','action'].includes(node.kind)?(state.complete?'Подтверждено':state.active?'Актуально':'Нет действующего основания'):'';
   if(stateText||(['requirement','decision','action'].includes(node.kind)&&state.reviewRequired))
     append('text',{x:14,y:86,'font-size':10,fill:state.reviewRequired?'#f2c78c':'#b6c7d6'},state.reviewRequired?'Нужна проверка':stateText,g);
   const supplement=picture.supportingCounts?.[item.entityId];
   if(supplement){
     const label=supplement.info?`${supplement.info} Info`:'';
     append('text',{x:14,y:104,'font-size':10,fill:'#b5c9d8'},label+' · сведения',g);
   }
   if((picture.counts[item.entityId]||0)>1)append('text',{x:181,y:89,'font-size':15,fill:line},'⧉',g);
   if(item.alias&&s.spec.kind!=='focus'){
    const expanded=(s.spec.expandedOccurrenceIds||[]).includes(item.id),toggle=append('text',{x:14,y:113,'font-size':11,fill:line,role:'button',tabindex:0,'aria-label':expanded?'Свернуть ветвь':'Раскрыть ветвь'},expanded?'− Свернуть ветвь':'+ Раскрыть ветвь',g);
    toggle.style.pointerEvents='auto';toggle.style.cursor='pointer';toggle.onclick=event=>{event.stopPropagation();void run(()=>changeView({expandedOccurrenceIds:expanded?(s.spec.expandedOccurrenceIds||[]).filter(i=>i!==item.id):[...(s.spec.expandedOccurrenceIds||[]),item.id]}));};toggle.onpointerdown=event=>event.stopPropagation();toggle.onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();toggle.onclick(event);}};
   }
   let drag=null,suppress=false;
   g.onpointerdown=e=>{if(compactMode||busy||pending||s.draft?.layout?.uncertain||e.button!==0)return;e.stopPropagation();g.focus({preventScroll:true});const here=point(e);drag={x:here.x,y:here.y,original:{...p},moved:false};g.setPointerCapture(e.pointerId);};
   g.onpointermove=e=>{if(!drag)return;const here=point(e),dx=here.x-drag.x,dy=here.y-drag.y;drag.moved||=Math.abs(dx)+Math.abs(dy)>4;if(!drag.moved)return;const next={x:drag.original.x+dx,y:drag.original.y+dy};if(item.alias)Object.assign(occurrences[item.id],next);else positions[item.id]=next;g.setAttribute('transform',`translate(${next.x},${next.y})`);paintEdges();};
   g.onpointerup=()=>{if(!drag)return;suppress=drag.moved;drag=null;
    if(suppress)void run(async()=>{
      if(s.spec.kind==='focus'){
        const next={x:positions[item.id].x,y:positions[item.id].y};
        await sync((v,screen)=>{screen.spec.focusPositions??={};
          screen.spec.focusPositions[item.id]=next;
          screen.focusLayouts??={};screen.focusLayouts[screen.spec.id]=clone(screen.spec.focusPositions);
        },true);
      }else await saveLayout(positions,occurrences);
    });
   };
   g.onpointercancel=()=>{if(!drag)return;if(item.alias)Object.assign(occurrences[item.id],drag.original);else positions[item.id]=drag.original;g.setAttribute('transform',`translate(${drag.original.x},${drag.original.y})`);paintEdges();drag=null;suppress=true;};
   g.onclick=()=>{if(suppress){suppress=false;return;}void run(()=>focusNode(item.entityId));};g.onkeydown=e=>{if(e.key==='Escape'&&drag){e.preventDefault();e.stopPropagation();g.onpointercancel();return;}if(['Enter',' '].includes(e.key)){e.preventDefault();void run(()=>focusNode(item.entityId));}};
  }
  // SVG paint order matters: place badges after all node fills, not below them.
  svg.append(groupLabelLayer);
  paintEdges();
  let pan=null;svg.onpointerdown=e=>{if(e.target.closest('.rdg-node,[data-group]')||e.button!==0)return;svg.focus();pan={x:e.clientX,y:e.clientY,original:{...camera}};svg.setPointerCapture(e.pointerId);};
  svg.onpointermove=e=>{if(!pan)return;const box=svg.getBoundingClientRect();camera={...camera,x:pan.original.x-(e.clientX-pan.x)*camera.width/box.width,y:pan.original.y-(e.clientY-pan.y)*camera.height/box.height};setCamera();};
  svg.onpointerup=()=>{if(pan){pan=null;void sync((v,s)=>s.spec.camera=camera).catch(e=>note(e.message,true));}};svg.onpointercancel=()=>{if(pan){camera=pan.original;pan=null;setCamera();}};svg.onkeydown=e=>{if(e.key==='Escape'&&pan){e.preventDefault();svg.onpointercancel();}};
  async function zoom(factor,anchor){const box=svg.getBoundingClientRect();
   const fx=anchor&&box.width?Math.max(0,Math.min(1,(anchor.x-box.left)/box.width)):.5,
    fy=anchor&&box.height?Math.max(0,Math.min(1,(anchor.y-box.top)/box.height)):.5;
   camera={x:camera.x+camera.width*(1-factor)*fx,y:camera.y+camera.height*(1-factor)*fy,width:camera.width*factor,height:camera.height*factor};
   setCamera();await sync((v,s)=>s.spec.camera=camera);
  }
  svg.onwheel=e=>{e.preventDefault();const cursor={x:e.clientX,y:e.clientY},delta=e.deltaY,shift=e.shiftKey,dx=e.deltaX,zooming=e.ctrlKey||e.metaKey;
   void run(async()=>{if(zooming)return zoom(delta>0?1.15:1/1.15,cursor);const box=svg.getBoundingClientRect();
    camera={...camera,x:camera.x+(shift?delta:dx)*camera.width/box.width,y:camera.y+(shift?0:delta)*camera.height/box.height};
    setCamera();await sync((v,s)=>s.spec.camera=camera);});};
  if(picture.invalid?.length){const notice=el('details',null,'rdg-card');notice.style.position='absolute';notice.style.left='12px';notice.style.top='10px';notice.append(el('summary','Недоступные изображения: '+picture.invalid.length),el('p',picture.invalid.map(r=>r.reason).join('; ')));button(notice,'Убрать недоступные изображения',()=>{const bad=new Set(picture.invalid.map(r=>r.id));let added=true;while(added){added=false;for(const [id,r] of Object.entries(occurrences))if(bad.has(r.parentId)&&!bad.has(id)){bad.add(id);added=true;}}return saveLayout(positions,Object.fromEntries(Object.entries(occurrences).filter(([id])=>!bad.has(id))));});parent.append(notice);}
  const legend=el('div',null,'rdg-legend');for(const [kind,title] of [['requirement','Requirement'],['decision','Decision'],['action','Action'],...(!isProcess()?[['context','Контекст процесса']]:[])]){const item=el('span'),dot=el('i');dot.style.background=palette[kind][1];item.append(dot,doc.createTextNode(title));legend.append(item);}for(const [index,workArea] of (snapshot.graph.workGraphs||[]).entries()){const item=el('span'),dot=el('i');dot.style.background=workAreaColor(workArea,index);item.append(dot,doc.createTextNode(workArea.title));item.title='Рабочая область · '+workArea.title;legend.append(item);}legend.append(el('span','⧉ Общая ветка · повтор'));parent.append(legend);
  fitGraph=async()=>{camera=bounds();setCamera();await sync((v,s)=>s.spec.camera=camera);};
  persistGraph=()=>s.spec.kind==='focus'||compactMode?Promise.resolve():saveLayout(positions,occurrences);
  const controls=el('div',null,'rdg-zoom');parent.append(controls);button(controls,'−',()=>zoom(1.25));button(controls,'+',()=>zoom(.8));button(controls,'Вписать',()=>fitGraph()).dataset.fit='';
  if(s.spec.kind==='focus'){
   if(Object.keys(s.spec.focusPositions||{}).length)
    button(controls,'Сбросить расположение',async()=>{await sync((v,t)=>{
      delete t.spec.focusPositions;delete t.spec.camera;
      if(t.focusLayouts)delete t.focusLayouts[t.spec.id];
    });await load();});
  }else{
   const toggle=button(controls,compactMode?'Моя раскладка':'Уплотнить обзор',()=>changeView({compactGraph:!compactMode}));
   toggle.dataset.compactToggle='';toggle.title=compactMode?'Показать сохранённые позиции и включить перетаскивание':'Временный компактный обзор, без записи позиций в Graph';
   if(!compactMode)button(controls,'Сохранить раскладку',()=>persistGraph()).dataset.saveLayout='';
  }
  if(s.draft?.layout){button(controls,'Повторить сохранение позиции',()=>saveLayout(positions,occurrences));button(controls,'Отменить черновик позиции',cancelLayout);}
 }
 function renderExplorer(parent,home=false){
  const exp=session?.explorer||{tab:'graphs',query:'',scroll:0,selectedPackageId:null},panel=el('aside',null,'rdg-explorer'+(home?' rdg-explorer-home':''));panel.setAttribute('aria-label','Explorer');parent.append(panel);const top=el('div',null,'rdg-explorer-top');panel.append(top);
  const close=home?el('div'):button(top,'',()=>sync(v=>v.explorer.open=false,true));if(home)top.append(close);close.className='rdg-explorer-close';if(!home)close.setAttribute('aria-label','Закрыть Explorer');const copy=el('span');copy.append(el('small','RDG VIEWER'),el('strong','EXPLORER'));close.append(copy);if(home){const controls=el('span');button(controls,'Обновить',refresh);close.append(controls);}else close.append(el('span','×'));
  const tabs=el('nav',null,'rdg-explorer-tabs');tabs.setAttribute('aria-label','Разделы Explorer');top.append(tabs);for(const [id,title] of [['graphs','Графы'],['packages','Пакеты']]){const b=button(tabs,title,()=>sync(v=>{v.explorer.tab=id;v.explorer.query='';v.explorer.scroll=0;},true));b.setAttribute('aria-selected',String(exp.tab===id));}
  const search=field(top,'Поиск',exp.query);search.setAttribute('aria-label','Поиск в Explorer');search.placeholder=exp.tab==='graphs'?'Найти процесс, область или граф':'Найти пакет или линзу';
  const list=el('div',null,'rdg-explorer-list');panel.append(list);explorerNode=list;
  function rows(){list.replaceChildren();const query=search.value.toLocaleLowerCase();if(!session||!catalog||!registry){list.append(el('p','Загрузка каталога…','rdg-explorer-note'));return;}
   if(exp.tab==='packages'&&exp.selectedPackageId){renderPackageEditor(list);return;}
   if(exp.tab==='graphs'){
    const expanded=new Set(session.explorer.expandedIds||['processes','ready','category:fundamental','process:'+screen()?.packageId]);
    function folder(parent,id,title,count){const group=el('details',null,'rdg-tree');group.dataset.folderId=id;group.open=!!query||expanded.has(id);const label=el('summary',title);label.append(el('small',String(count)));group.append(label);const content=el('div',null,'rdg-tree-content');group.append(content);parent.append(group);group.ontoggle=()=>{if(query||group.open===expanded.has(id))return;group.open?expanded.add(id):expanded.delete(id);void sync(v=>v.explorer.expandedIds=[...expanded]).catch(e=>note(e.message,true));};return content;}
    function row(parent,title,meta,icon,fn,selected=false){const b=button(parent,'',fn);b.className='rdg-tree-row';b.setAttribute('aria-label',title);b.append(el('span',icon));const text=el('span',null,'rdg-tree-copy');text.append(el('b',title),el('small',meta));b.append(text);if(selected)b.setAttribute('aria-current','page');return b;}
    function packages(parent,graph){const box=el('div',null,'rdg-tree-packages');box.append(el('small','Пакеты · '+(graph.recommendationPackageIds||[]).length));for(const pid of graph.recommendationPackageIds||[]){const p=definitionMeta(pid);button(box,'◇ '+(p?.title||'Пакет рекомендаций'),()=>openPackage(pid));}button(box,'+ Добавить пакет…',async()=>{if(graph.packageId!==screen()?.packageId)await navigate(graph.packageId);await showForm('attachments');});parent.append(box);}
    const processes=catalog.packages.filter(r=>r.coreModel==='rdg-decision-v1'&&['working','copy'].includes(r.role)&&(!query||(r.title+' '+r.path+' '+(r.workGraphs||[]).map(w=>w.title).join(' ')).toLocaleLowerCase().includes(query)));
    const processRoot=folder(list,'processes','▰ Процесс-графы',processes.length);
    for(const graph of processes){const box=el('div',null,'rdg-tree-process');box.dataset.processId=graph.packageId;processRoot.append(box);const selected=graph.packageId===screen()?.packageId;
     const b=row(box,graph.title||graph.path,'Process Graph · '+(graph.workGraphs||[]).length+' рабочих областей'+(graph.role==='copy'?' · копия':''),'▤',e=>navigate(graph.packageId,{kind:'graph'},e.ctrlKey||e.metaKey),selected&&screen().spec.kind==='graph');b.dataset.packageId=graph.packageId;
     const children=folder(box,'process:'+graph.packageId,'Рабочие области и пакеты',(graph.workGraphs||[]).length);packages(children,graph);
     for(const [areaIndex,w] of (graph.workGraphs||[]).entries()){
      const areaLine=el('div',null,'rdg-tree-area-line');
      const area=row(areaLine,w.title,'Working Graph · '+w.memberIds.length+' блоков процесса','●',e=>navigate(graph.packageId,{kind:'workGraph',id:w.id},e.ctrlKey||e.metaKey),selected&&activeArea()?.id===w.id);
      const areaColor=workAreaColor(w,areaIndex);area.style.borderLeft='3px solid '+areaColor;area.firstChild.style.color=areaColor;
      area.dataset.workgraphId=w.id;area.dataset.processId=graph.packageId;area.title=w.title+' · цвет '+(workAreaColorNames[workAreaColorKey(w,areaIndex)]||'');
      const picker=el('details',null,'rdg-tree-area-menu');const summary=el('summary','●');summary.style.color=areaColor;summary.title='Назначить цвет рабочей области';summary.setAttribute('aria-label','Назначить цвет: '+w.title);picker.append(summary);
      const choices=el('div',null,'rdg-tree-area-options');choices.setAttribute('aria-label','Цвет рабочей области');
      for(const key of workAreaColorKeys){const choice=button(choices,'',()=>updateWorkAreaColor(graph.packageId,w.id,key));const swatch=el('i',null,'rdg-tree-area-swatch');swatch.style.backgroundColor=workAreaColors[key];choice.append(swatch,el('span',workAreaColorNames[key]));if(workAreaColorKey(w,areaIndex)===key)choice.setAttribute('aria-pressed','true');}
      picker.append(choices);areaLine.append(area,picker);children.append(areaLine);
     }
     if(!(graph.workGraphs||[]).length)children.append(el('p','Рабочих областей пока нет.','rdg-explorer-note'));
     button(children,'+ Новая рабочая область',async()=>{if(graph.packageId!==screen()?.packageId)await navigate(graph.packageId);await showForm('workGraph',{newArea:true});}).className='rdg-tree-add';
    }
    button(processRoot,'+ Создать процесс',()=>showForm('create')).className='rdg-tree-add';
    const definitions=catalog.packages.filter(r=>r.coreModel==='rdg-decision-v1'&&['ready','lens'].includes(r.role)&&(!query||(r.title+' '+r.path+' '+r.lensKey).toLocaleLowerCase().includes(query))),ready=folder(list,'ready','▰ Готовые графы',definitions.length);
    const categories=[['fundamental','Основы RDG'],['other','Свои готовые графы']];
    for(const [category,title] of categories){const graphs=definitions.filter(r=>category==='fundamental'?r.role==='lens'&&r.lensKey&&r.path.includes('lenses/'):!(r.role==='lens'&&r.lensKey&&r.path.includes('lenses/')));if(!graphs.length)continue;const categoryBox=folder(ready,'category:'+category,title,graphs.length);
     for(const [role,label] of [['ready','Шаблоны графов'],['lens','Графы линз']]){const items=graphs.filter(r=>r.role===role);if(!items.length)continue;const roleBox=folder(categoryBox,'category:'+category+':'+role,label,items.length);for(const graph of items){const b=row(roleBox,graph.title||graph.path,role==='lens'?'Линза · переиспользовать в работе':'Шаблон · вставить в процесс',role==='lens'?'◇':'▣',e=>navigate(graph.packageId,{kind:'graph'},e.ctrlKey||e.metaKey),graph.packageId===screen()?.packageId);b.dataset.packageId=graph.packageId;packages(roleBox,graph);}}
    }
    list.append(el('p','Process Graph — весь процесс со своими блоками, Plan и History. Working Graph — рабочая область внутри него. Области могут пересекаться и используют общие блоки и связи.','rdg-explorer-note'));
    const legacy=catalog.packages.filter(r=>r.coreModel&&r.coreModel!=='rdg-decision-v1');if(legacy.length){const group=folder(list,'legacy','Другие профили',legacy.length);for(const graph of legacy)row(group,graph.title||graph.path,graph.coreModel,'▤',()=>navigate(graph.packageId));}
   }else{
    if(registry.unavailable){list.append(el('p','Каталог пакетов недоступен с текущими правами.'));return;}
    button(list,'Создать пакет',()=>openPackage(null,newDefinition()));
    for(const p of registry.packages.filter(p=>!query||(p.title+' '+p.key).toLocaleLowerCase().includes(query))){const b=button(list,p.title+(p.supplied?' · поставляемый':''),()=>openPackage(p.id));b.className='rdg-tree-row';}
    list.append(el('p','Определений: '+registry.total,'rdg-muted'));
    const queryPage=async offset=>{registry=await call({method:'recommendation_catalog',query:search.value,offset,limit:20});rows();};
    button(list,'Найти в каталоге',()=>queryPage(0));button(list,'Предыдущая страница',()=>queryPage(Math.max(0,registry.offset-20)),!registry.offset);button(list,'Следующая страница',()=>queryPage(registry.offset+20),registry.offset+registry.packages.length>=registry.total);
   }
  }
  search.oninput=()=>{rows();void sync(v=>v.explorer.query=search.value).catch(e=>note(e.message,true));};rows();list.scrollTop=exp.scroll;list.onscroll=()=>{if(session.explorer.scroll!==list.scrollTop)void sync(v=>v.explorer.scroll=list.scrollTop).catch(()=>{});};
 }
 function dependencyDetails(){return snapshot?.dependencyCatalog?.localApplications||[];}
 function dependencyForm(nodeId,extra={}){const node=policyEntities().get(nodeId);return {...(['requirement','decision','action','finding'].includes(node?.kind)?{nodeId}:{sourceId:nodeId}),...extra,returnToDependencies:nodeId};}
 function openPolicyFromInspector(row,nodeId){dependencyInspectorReturns.set(screen().id,{nodeId,packageId:snapshot.package.packageId,mode:screen().presentation?.mode||'graph'});return openPolicy(row.policyId,null,row.policyVersion);}
 function dependencyIssue(code,policy){const parts=String(code).split(':'),role=id=>policyRoleName(policy,id);
  if(parts[0]==='ROLE_EMPTY')return 'Не найден обязательный участник роли «'+role(parts[1])+'»: проверьте тип, условия роли и путь поиска.';
  if(parts[0]==='PARTICIPANT_MISSING')return 'Участник отсутствует: '+parts.slice(1).map(role).join(' · ');
  if(parts[0]==='RELATION_MISSING')return 'Нет обязательного отношения: '+role(parts[1])+' → '+relationName((parts[2]||'').split('/'))+' → '+role(parts[3]);
  return ({POLICY_VERSION_DISABLED:'Использование этой версии политики отключено.',AUTOMATIC_RELATION_MISSING:'Обязательное отношение Graph отсутствует.',PARENT_RELATION_MISSING:'Decision больше не является непосредственным родителем цели.',TARGET_KIND:'Тип зависимого элемента не подходит политике.',SOURCE_KIND:'Тип источника не подходит политике.'})[code]||String(code);
 }
 function applicationReference(parent,row,id,selectedId=null){const n=row.participants[id]||{id,title:id,present:false};const box=el('div',null,'rdg-dependency-reference');parent.append(box);box.dataset.dependencyParticipantId=id;if(id===selectedId){box.dataset.selectedInstanceParticipant='true';box.append(el('small','ВЫБРАННЫЙ ЭЛЕМЕНТ'));}
  if(n.present&&policyEntities().has(id))entityReference(box,policyEntities().get(id),()=>{closePolicyInstances(false);return openDependencyInspector(id);});
  else box.append(el('span',n.title+' · участник удалён или недоступен','rdg-muted'));
  box.append(el('small',id));return box;
 }
 function renderApplicationParticipants(parent,row){
  const roles=el('section',null,'rdg-dependency-roles');parent.append(roles);roles.append(el('h4','Участники применения'));
  const assigned=new Set();
  for(const role of row.roles){const box=el('div',null,'rdg-dependency-role');roles.append(box);box.dataset.dependencyRole=role.id;
   box.append(el('b',policyRoleName(row.policy,role.id)+(role.selector?' · динамический набор':'')));
   if(role.selector)box.append(el('p','Поиск от роли «'+policyRoleName(row.policy,role.selector.anchor)+'» · '+(role.selector.direction==='in'?'связь направлена к ней':'связь направлена от неё')+' · '+relationName(role.selector.relation)+' · глубина '+role.selector.minDepth+'–'+role.selector.maxDepth,'rdg-muted'));
   for(const condition of role.conditions||[])box.append(el('p','Применимость — '+policyPredicateText(condition),'rdg-muted'));
   if(!role.ids.length)box.append(el('p',role.selector?'Текущий набор пуст.':'Текущий участник не соответствует условиям роли.','rdg-muted'));
   for(const id of role.ids){applicationReference(box,row,id);assigned.add(id);}
   if(role.configuredId&&!role.ids.includes(role.configuredId)){box.append(el('small','Сохранённое назначение роли'));applicationReference(box,row,role.configuredId);assigned.add(role.configuredId);}
  }
  const others=row.nodeIds.filter(id=>!assigned.has(id));if(others.length){const box=el('details');roles.append(box);box.append(el('summary','Участники путей и наблюдений · '+others.length));for(const id of others)applicationReference(box,row,id);}
  if(row.paths.length||row.relations.length){const box=el('details',null,'rdg-dependency-paths');parent.append(box);box.append(el('summary','Связи и пути поиска · '+row.relations.length));
   for(const path of row.paths){const route=el('div');box.append(route);route.dataset.dependencyPathRole=path.role;route.append(el('p',path.kind==='observation'?'Цепочка наблюдения «'+observationMetadata(path.watch).name+'» · '+path.participantId:'Путь к роли «'+policyRoleName(row.policy,path.role)+'» · '+path.participantId));
    if(path.nodeIds.length)route.append(el('p','Участники пути: '+path.nodeIds.map(id=>(row.participants[id]?.title||id)+' · '+id).join(', '),'rdg-muted'));
    route.append(el('small','Связи пути: '+path.relationIds.join(', ')));
   }
   box.append(el('p','Ниже показаны фактические направленные связи. К одному участнику могут вести несколько путей.','rdg-muted'));
   for(const relation of row.relations){const link=el('div',null,'rdg-dependency-link');box.append(link);link.dataset.dependencyRelationId=relation.id;
    if(relation.from&&relation.to){applicationReference(link,row,relation.from);link.append(el('span','→ '+relationName(relation.type)+' →'));applicationReference(link,row,relation.to);}
    else if(relation.type==='SHARED_WORK_GRAPH')link.append(el('p','Общая рабочая область: '+(relation.title||relation.workGraphId)));
    else link.append(el('p','Связь отсутствует. Сохранён только её идентификатор.','rdg-muted'));
    link.append(el('small',relation.id+(relation.historicalOnly?' · сведения на момент отключения':'')));
   }
  }
 }
 function policyInstanceKey(row){return row.policyId+'@'+row.policyVersion+(row.policyId.startsWith('legacy:')?':'+JSON.stringify(row.rules.map(rule=>[rule.watch,rule.operations,rule.eventType,rule.predicate])):'');}
 function closePolicyInstances(restoreFocus=true){const previous=policyInstancesView;policyInstancesView=null;root.querySelector('[data-policy-instances-dialog]')?.closest('.rdg-modal-shade')?.remove();if(restoreFocus&&previous?.trigger?.isConnected)previous.trigger.focus({preventScroll:true});}
 function showPolicyInstances(row,nodeId,trigger){closePolicyInstances(false);policyInstancesView={packageId:snapshot.package.packageId,screenId:screen().id,nodeId,key:policyInstanceKey(row),policy:row.policy,trigger};renderPolicyInstances(root);}
 function renderApplicationState(parent,row){
  if(!row.enabled){const reason=({applicability:'нарушена применимость',manual:'отключено пользователем',policy:'версия политики отключена'})[row.reasonCode]||row.reasonCode||'применение отключено';parent.append(el('p','Причина отключения: '+reason));
   for(const issue of row.violations)parent.append(el('p',dependencyIssue(issue,row.policy),'rdg-muted'));
   parent.append(el('p',row.applicable?'Сейчас условия применимости выполнены. Для возобновления нажмите «Активировать снова».':'Сейчас применение не может действовать:','rdg-muted'));
   for(const issue of row.currentViolations)parent.append(el('p',dependencyIssue(issue,row.policy),'rdg-muted'));
   parent.append(el('p','Отключение само по себе не означает «Требует пересмотра». Восстановление условий не включает применение автоматически.','rdg-muted'));
  }
 }
 function instanceReference(parent,row,id,selectedId){const n=row.participants[id]||{id,title:id,present:false},box=el('div',null,'rdg-instance-reference');parent.append(box);box.dataset.dependencyParticipantId=id;
  if(id===selectedId)box.dataset.selectedInstanceParticipant='true';
  if(n.present&&policyEntities().has(id)){const link=entityReference(box,policyEntities().get(id),()=>{closePolicyInstances(false);return openDependencyInspector(id);});link.title='Перейти к элементу';}
  else box.append(el('span',n.title+' · участник удалён или недоступен','rdg-muted'));
 }
 function instanceChangeText(watch,operations,rule,kind){
  if(watch==='definition')return ({canon:'Изменится теория принятия решения: каноны, общее, известные ошибки, название, описание или метки.',context:'Изменится содержание контекста: значение, название, описание или метки.',info:'Изменится содержание Info: значение, название, описание или метки.'})[kind]||'Изменится содержание элемента.';
  if(watch==='event')return 'Будет записано событие «'+eventMetadata(rule.eventType).name+'».';
  if(watch==='predicate')return 'Условие «'+policyPredicateText(rule.predicate)+'» '+(operations.includes('changed')?'изменит истинность':operations.includes('added')&&operations.includes('removed')?'станет истинным или ложным':operations.includes('added')?'станет истинным':'станет ложным')+'.';
  const labels={selection:{changed:'Изменится состояние выбора Decision'},result:{changed:'Изменится сохранённый результат блока'},locks:{changed:'Изменятся настройки блокировок'},
   directScope:{changed:'Изменятся включённые данные ближайшего окружения',added:'В ближайшем окружении появится участник или связь',removed:'Из ближайшего окружения исчезнет участник или связь'},
   context:{changed:'Изменятся наблюдаемые данные контекста',added:'В контекст принятия решения будет добавлен участник',removed:'Из контекста принятия решения будет исключён участник'},
   canon:{changed:'Изменится теория принятия решения',added:'К элементу будет привязана теория принятия решения',removed:'Теория принятия решения будет отвязана от элемента'},
   info:{changed:'Изменится содержание прямого Info',added:'К элементу будет привязано Info',removed:'Info будет отвязано от элемента'},
   canonInfo:{changed:'Изменится связанная информация теории',added:'Будет добавлена информация теории',removed:'Будет удалена связь с информацией теории'},
   membership:{added:'Участник войдёт в выбранный набор',removed:'Участник выйдет из выбранного набора'},
   structuralScope:{changed:'Изменятся состав или правила Decision Group',added:'Появится непосредственная структурная связь или группа',removed:'Исчезнет непосредственная структурная связь или группа'},
   relations:{added:'Появится непосредственное отношение',removed:'Исчезнет непосредственное отношение'},
   workGraphs:{added:'Элемент будет включён в рабочую область',removed:'Элемент будет исключён из рабочей области'},
   rootCauses:{changed:'Изменится запись корневого основания',added:'Будет добавлено корневое основание',removed:'Будет удалено корневое основание'}};
  return operations.map(op=>labels[watch]?.[op]||observationMetadata(watch).operationLabels?.[op]||policyOperationLabels[op]).join('; ')+'.';
 }
 function instanceObservationRows(row,rule,selectedId,direction){if(!rule.enabled)return [];
  const watch=rule.displayWatch||rule.watch,result=[],configured=row.roles.find(role=>role.id===rule.role)?.configuredId;
  const points=rule.observations?.length?rule.observations:(rule.actorIds.length?rule.actorIds:configured?[configured]:[]).map(actorId=>({actorId,memberIds:[],contextSources:[]}));
  for(const point of points){const actor=point.actorId,members=point.memberIds||[],kind=row.participants[actor]?.kind;
   if(rule.whenKinds&&!rule.whenKinds.includes(kind))continue;
   const add=(ids,text,{via=null,members:related=[],memberLabel='Участники окружения'}={})=>{
    if(direction==='outgoing'&&![actor,...ids,...related].includes(selectedId))return;
    if(direction==='outgoing'&&actor!==selectedId){if(ids.includes(selectedId))ids=[selectedId];else if(related.includes(selectedId)){ids=[selectedId];related=[];via=actor;}}
    result.push({actorId:actor,sourceIds:[...new Set(ids)],text,via,members:related,memberLabel,ruleId:rule.id});
   };
   if(watch==='context'&&rule.operations.includes('changed')){
    for(const source of point.contextSources||[]){if(!source.watches.length)continue;
     if(direction==='outgoing'&&selectedId!==actor&&selectedId!==source.sourceId&&source.memberIds.includes(selectedId)){add([selectedId],'Изменятся включённые данные наблюдаемого окружения.',{via:source.sourceId});continue;}
     const changes=source.watches.map(id=>instanceChangeText(id,['changed'],rule,row.participants[source.sourceId]?.kind)).join(' ');
     add([source.sourceId],changes,{via:actor,members:source.memberIds,memberLabel:'Включённые участники окружения'});
    }
   }else if(['canon','info','canonInfo'].includes(watch)&&rule.operations.includes('changed')){
    if(members.length)add(members,instanceChangeText(watch,['changed'],rule,kind),{via:actor});
   }else if(rule.operations.includes('changed')||watch==='membership')add([actor],instanceChangeText(watch,watch==='membership'?rule.operations:['changed'],rule,kind),{members,memberLabel:watch==='directScope'?'Участники ближайшего окружения':'Участники связей'});
   if(watch!=='membership')for(const op of rule.operations.filter(op=>op!=='changed')){
    if(['canon','info','canonInfo'].includes(watch)&&(op==='removed'||rule.memberRole)){
     if(members.length)add(members,instanceChangeText(watch,[op],rule,kind),{via:actor});
    }else add([actor],instanceChangeText(watch,[op],rule,kind),{members:['directScope','structuralScope','relations'].includes(watch)?members:[]});
   }
  }
  return result;
 }
 function renderPolicyInstances(parent){const view=policyInstancesView;if(!view)return;
  if(view.packageId!==snapshot?.package.packageId||view.screenId!==screen()?.id){closePolicyInstances(false);return;}
  const rows=dependencyDetails().filter(row=>policyInstanceKey(row)===view.key&&row.nodeIds.includes(view.nodeId));
  const shade=el('div',null,'rdg-modal-shade'),body=el('section',null,'rdg-modal rdg-policy-instances');body.dataset.policyInstancesDialog='';body.setAttribute('role','dialog');body.setAttribute('aria-modal','true');body.setAttribute('aria-label','Инстансы политики');shade.append(body);parent.append(shade);
  const top=el('div',null,'rdg-instance-header');body.append(top);top.append(el('h2',view.policy.name+' · v'+view.policy.version));const close=button(top,'Закрыть инстансы',()=>closePolicyInstances());
  body.append(el('p',view.policy.description,'rdg-instance-description'));
  const selected=el('div',null,'rdg-instance-selected');body.append(selected);selected.append(el('span','Для элемента:','rdg-muted'));instanceReference(selected,rows[0]||{participants:{}},view.nodeId,view.nodeId);
  if(!view.policy.id.startsWith('legacy:'))button(selected,'Открыть политику · v'+view.policy.version,()=>{closePolicyInstances(false);return openPolicyFromInspector({policyId:view.policy.id,policyVersion:view.policy.version},view.nodeId);});
  const groups=[['incoming','Что инвалидирует выбранный элемент',row=>row.targetId===view.nodeId],['outgoing','Что инвалидируется при его изменении',row=>row.targetId!==view.nodeId&&row.observedIds.includes(view.nodeId)],['participation','Участие в политике',row=>row.targetId!==view.nodeId&&!row.observedIds.includes(view.nodeId)]];
  for(const [direction,title,accept] of groups){const instances=rows.filter(accept);if(!instances.length)continue;const section=el('section',null,'rdg-instance-section');section.dataset.instanceDirection=direction;body.append(section);section.append(el('h3',title));
   if(direction==='participation')section.append(el('p','Выбранный элемент участвует в применимости политики. Его содержание здесь не отслеживается.','rdg-muted'));
   const table=el('table',null,'rdg-instance-table');section.append(table);const head=el('thead'),headRow=el('tr');table.append(head);head.append(headRow);for(const title of ['Что меняется','Как именно','Что требует пересмотра'])headRow.append(el('th',title));
   for(const row of instances){const instance=el('tbody');instance.dataset.dependencyInstanceId=row.id;instance.dataset.instanceActive=String(row.enabled&&row.applicable);table.append(instance);
    if(!row.enabled||!row.applicable){const line=el('tr'),status=el('td',null,'rdg-instance-disabled');line.append(status);status.colSpan=3;instance.append(line);status.append(el('b','Отключено — не вызывает инвалидацию. '));
     const issue=row.currentViolations[0]||row.violations[0];status.append(el('span',issue?dependencyIssue(issue,row.policy):row.reasonCode==='manual'?'Отключено пользователем.':'Применение не действует.'));
    }
    const conditions=row.rules.flatMap(rule=>instanceObservationRows(row,rule,view.nodeId,direction));
    for(const condition of conditions){const line=el('tr');line.dataset.instanceActorId=condition.actorId;line.dataset.instanceRuleId=condition.ruleId;instance.append(line);
     const source=el('td'),change=el('td'),target=el('td');line.append(source,change,target);for(const id of condition.sourceIds)instanceReference(source,row,id,view.nodeId);
     if(condition.members.length){source.append(el('small',condition.memberLabel+':','rdg-muted'));for(const id of condition.members)instanceReference(source,row,id,view.nodeId);}
     change.append(el('p',condition.text));if(condition.via&&condition.via!==row.targetId){change.append(el('small','В наблюдении элемента:','rdg-muted'));instanceReference(change,row,condition.via,view.nodeId);}
     target.dataset.instanceDependentId=row.targetId;instanceReference(target,row,row.targetId,view.nodeId);
    }
    if(!conditions.length){const line=el('tr'),empty=el('td','Сейчас нет участников с отслеживаемыми изменениями.','rdg-muted');empty.colSpan=3;line.append(empty);instance.append(line);}
   }
  }
  if(!rows.length)body.append(el('p','Сейчас нет применений этой версии с выбранным элементом.'));
  shade.onkeydown=event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closePolicyInstances();}
   else if(event.key==='Tab'){const nodes=[...body.querySelectorAll('button,[tabindex]')].filter(node=>!node.disabled&&node.getClientRects().length);const first=nodes[0],last=nodes.at(-1);if(event.shiftKey&&doc.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&doc.activeElement===last){event.preventDefault();first?.focus();}}
  };
  queueMicrotask(()=>{if(close.isConnected)close.focus({preventScroll:true});});
 }
 function renderDependencyApplication(parent,row,nodeId){const card=el('article',null,'rdg-dependency-application');parent.append(card);card.dataset.dependencyApplicationId=row.id;card.dataset.dependencyApplicationKind=row.kind;card.dataset.dependencyStatus=row.status;
  card.append(el('h4',row.policy.name),el('p','Версия '+row.policyVersion+' · '+(row.enabled?'Действует':'Отключено')+' · '+({automatic:'автоматическое применение',policy:'применение сохранённой политики',legacy:'настройки отдельной связи','legacy-context':'контекст Decision'})[row.kind],'rdg-dependency-status'));
  card.append(el('p',row.policy.description,'rdg-muted'));renderApplicationState(card,row);
  const actions=el('div',null,'rdg-policy-actions');card.append(actions);
  if(!row.policyId.startsWith('legacy:'))button(actions,'Открыть политику · v'+row.policyVersion,()=>openPolicyFromInspector(row,nodeId));
  const instances=button(actions,'Показать инстансы',()=>showPolicyInstances(row,nodeId,instances));instances.dataset.showPolicyInstances=row.id;instances.setAttribute('aria-haspopup','dialog');
  if(!isProcess()||snapshot.immutableDefinition)return;
  if(row.kind==='policy'){
   button(actions,'Изменить применение',()=>showForm('policyBinding',dependencyForm(nodeId,{bindingId:row.id,policyId:row.policyId,policyVersion:row.policyVersion,nodeId:row.targetId})));
   button(actions,row.enabled?'Отключить':'Активировать снова',()=>savePolicyChange(row.enabled?'binding_disable':'binding_activate',{id:row.id,expectedRevision:row.binding.revision||1},'Изменено состояние применения '+row.id));
   button(actions,'Удалить применение',()=>savePolicyChange('binding_remove',{id:row.id,expectedRevision:row.binding.revision||1},'Удалено применение '+row.id));
  }else if(row.kind==='automatic')button(actions,row.enabled?'Отключить':'Активировать снова',()=>savePolicyChange(row.enabled?'automatic_disable':'automatic_activate',{id:row.id,expectedRevision:row.binding.revision||1},'Изменено состояние автоматического применения'));
  else button(actions,'Настроить наблюдения',()=>showForm('dependencyRule',{nodeId:row.targetId,edgeId:row.legacyEdgeId,sourceId:row.binding.sourceId,context:row.decisionContext,convertLegacy:row.legacyContextId,returnToDependencies:nodeId}));
 }
 function dependencyGroup(row,nodeId){
  if(row.targetId!==nodeId&&!row.observedIds.includes(nodeId))return 'participation';
  if(row.kind==='automatic')return 'automatic';
  if(row.decisionContext||row.kind==='legacy-context')return 'context';
  return 'explicit';
 }
 function renderEntityDependencies(parent,node){parent.dataset.entityDependenciesId=node.id;
  if(invalidationReturns.get(screen().id)?.packageId===snapshot.package.packageId)button(parent,'← К инвалидации',returnToInvalidation);
  parent.append(el('p','Применения политик всего процесса, включая отключённые. Рабочая область и фокус не ограничивают список.','rdg-muted'));
  const rows=dependencyDetails().filter(row=>row.nodeIds.includes(node.id));
  const byDirection={incoming:rows.filter(row=>row.targetId===node.id),outgoing:rows.filter(row=>row.targetId!==node.id&&row.observedIds.includes(node.id)),participation:rows.filter(row=>row.targetId!==node.id&&!row.observedIds.includes(node.id))};
  const groups=[['all','Показать все','Все зависимости или влияния выбранного направления. Справочное участие в схемах сюда не входит.'],['context','Контекст Decision','Подписки из контекста принятия Decision — ссылки и настроенные наблюдения его участников.'],['automatic','Автоматические','Наблюдение родителя, непосредственной структуры и групп решений, привязанной теории принятия решения.'],['explicit','Явные зависимости','Индивидуально настроенные связи и применения сохранённых политик. Способ настройки указан в карточке.']];
  const key=snapshot.package.packageId+':'+node.id;
  const selection=dependencyInspectorFilters.get(key)||{direction:'incoming',group:'all'};dependencyInspectorFilters.set(key,selection);
  const controls=el('div',null,'rdg-dependency-filters');controls.dataset.dependencyFilters='';parent.append(controls);
  const choices=[];
  const results=el('div',null,'rdg-dependency-results');results.dataset.dependencyResults='';
  function renderResults(){
   for(const choice of choices)choice.button.setAttribute('aria-pressed',String(choice.direction===selection.direction&&choice.group===selection.group));
   results.replaceChildren();results.dataset.selectedDirection=selection.direction;results.dataset.selectedGroup=selection.group;
   const selectedRows=selection.group==='participation'?byDirection.participation:byDirection[selection.direction].filter(row=>selection.group==='all'||dependencyGroup(row,node.id)===selection.group);
   const title=selection.group==='participation'?'Справочно':selection.direction==='incoming'?'Зависимости':'Влияния';
   const category=[...groups,['participation','Участие в схеме']].find(([id])=>id===selection.group)?.[1];
   const heading=el('h3',title+' · '+category+' · '+selectedRows.length);heading.tabIndex=-1;results.append(heading);
   results.append(el('p',selection.group==='participation'?'Участие в поиске и применимости. Эти записи не включены в счётчик влияний.':selection.direction==='incoming'?'При изменении каких данных или связей этот элемент может потребовать пересмотра.':'Какие зависимые элементы могут потребовать пересмотра при изменении наблюдаемых данных или связей этого элемента.','rdg-muted'));
   if(!selectedRows.length){results.append(el('p','В этой группе нет применений.','rdg-muted'));return;}
   const sections=selection.direction==='incoming'?[['incoming',selectedRows]]:[['outgoing',selectedRows.filter(row=>row.observedIds.includes(node.id))],['participation',selectedRows.filter(row=>!row.observedIds.includes(node.id))]];
   for(const [direction,records] of sections){if(!records.length)continue;const box=el('section',null,'rdg-dependency-section');box.dataset.dependencyDirection=direction;results.append(box);
    if(direction==='participation')box.append(el('h4','Участие в схеме'),el('p','Промежуточные роли, пути поиска и сохранённые сведения отключённых применений. Содержание этого участника не наблюдается данным применением.','rdg-muted'));
    for(const row of records)renderDependencyApplication(box,row,node.id);
   }
  }
  for(const [direction,title] of [['incoming','Зависимости'],['outgoing','Влияния']]){
   const row=el('div',null,'rdg-dependency-filter-row');controls.append(row);row.dataset.dependencyFilterDirection=direction;
   row.append(el('h4',title));const buttons=el('div',null,'rdg-dependency-filter-buttons');buttons.setAttribute('role','group');buttons.setAttribute('aria-label','Группы: '+title);row.append(buttons);
   const options=direction==='outgoing'?[...groups,['participation','Участие в схеме','Справочно: промежуточные роли и пути. Не входит в «Показать все» влияний, поскольку содержание участника не наблюдается.']]:groups;
   for(const [group,label,description] of options){const count=group==='participation'?byDirection.participation.length:byDirection[direction].filter(item=>group==='all'||dependencyGroup(item,node.id)===group).length;
    const chip=button(buttons,'',()=>{selection.direction=direction;selection.group=group;renderResults();});chip.className='rdg-dependency-filter';chip.dataset.dependencyFilter=group;chip.dataset.dependencyDirection=direction;chip.dataset.count=String(count);chip.title=description;chip.setAttribute('aria-label',label+' · '+count);
    chip.append(el('span',label),el('span',String(count),'rdg-dependency-filter-count'));choices.push({button:chip,direction,group});
   }
  }
  parent.append(results);renderResults();
  if(isProcess()&&!snapshot.immutableDefinition){const actions=el('div',null,'rdg-policy-actions');parent.append(actions);
   if(['requirement','decision','action','finding'].includes(node.kind))button(actions,'+ Ручная зависимость L1/L2',()=>showForm('dependencyRule',{nodeId:node.id,returnToDependencies:node.id}));
   button(actions,'+ Применить политику',()=>showForm('policyBinding',dependencyForm(node.id)));
   button(actions,'Создать новую политику',()=>showForm('policyEditor',{returnToDependencies:node.id,applyAfterCreate:true,sourceKind:['requirement','decision','action'].includes(node.kind)?'context':node.kind}));
  }
 }
  const findingTypes={problem:'Problem',risk:'Risk',decision_uncertainty:'Decision Uncertainty',improvement_opportunity:'Improvement Opportunity'};
 const findingCodes={problem:'F-P',risk:'F-R',decision_uncertainty:'F-U',improvement_opportunity:'F-O'};
 const findingDispositions={unresolved:'Не разрешён',deferred:'Отложен',resolved:'Разрешён',invalidated:'Опровергнут',superseded:'Заменён'};
 const findingReturns=new Map(),findingFilters=new Map();
 function rememberFindingSource(nodeId){if(!findingReturns.has(screen().id))findingReturns.set(screen().id,{packageId:snapshot.package.packageId,spec:clone(screen().spec),mode:screen().presentation?.mode||'graph',tab:inspectorTabState.get(nodeId)||'findings',scrollTop:root.querySelector('.rdg-inspector')?.scrollTop||0,nodeId});}
 async function returnToFindings(){const prev=findingReturns.get(screen().id);if(!prev||prev.packageId!==snapshot.package.packageId)return;findingReturns.delete(screen().id);inspectorTabState.set(prev.nodeId,prev.tab||'findings');await sync((v,s)=>{s.spec=prev.spec;s.presentation.mode=prev.mode;s.inspector={kind:'entity',id:prev.nodeId};});await load();const panel=root.querySelector('.rdg-inspector');if(panel)panel.scrollTop=prev.scrollTop||0;}
 function findingReference(parent,id,sourceId){const node=policyEntities().get(id);if(!node){parent.append(el('p','Участник удалён или недоступен.','rdg-muted'));return;}entityReference(parent,node,async()=>{rememberFindingSource(sourceId);await focusNode(id);});}
 function renderFindingQuestionsEditor(container,current,F){
   const extras=el('details');extras.append(el('summary','Вопросы и ограничения проверки'));container.append(extras);
   for(const fieldName of ['reviewLimitations']){
    if(F()[fieldName]===undefined)setDraft(fieldName,clone(current?.[fieldName]||[]));
    const rows=F()[fieldName];rows.forEach((q,index)=>{const box=el('fieldset');extras.append(box);box.append(el('legend',fieldName==='questions'?'Вопрос':'Ограничение'));
     const update=(key,value)=>{const copy=clone(F()[fieldName]);copy[index][key]=value;setDraft(fieldName,copy);};
     const specs=fieldName==='questions'?[['question','Что выяснить'],['impact','На что влияет'],['scope','Блокируемая часть работы'],['closeCondition','Условие ответа']]:[['claim','Что не подтверждено'],['reason','Почему'],['limitation','Какие выводы ограничены']];
     for(const [key,label] of specs)field(box,label,q[key]||'','textarea',v=>update(key,v));
     if(fieldName==='questions')select(box,'Блокирование',[['non-blocking','Не блокирует'],['blocking','Блокирует'],['partially-blocking','Частично блокирует']],q.blocking,v=>update('blocking',v));
     button(box,'Убрать запись',()=>{setDraft(fieldName,F()[fieldName].filter((_,i)=>i!==index));render();});
    });
    button(extras,fieldName==='questions'?'Добавить вопрос':'Добавить ограничение',()=>{setDraft(fieldName,[...F()[fieldName],fieldName==='questions'?{id:uid(),question:'',impact:'',blocking:'non-blocking',scope:'',closeCondition:''}:{id:uid(),claim:'',reason:'',limitation:''}]);render();});
   }
 }
 function renderFindings(parent,node){
  parent.dataset.entityFindingsId=node.id;
  const editable=isProcess()&&!snapshot.immutableDefinition,key=snapshot.package.packageId+':'+node.id;
  const state=findingFilters.get(key)||{query:'',disposition:'all'};findingFilters.set(key,state);
  const all=snapshot.graph.objects.filter(f=>f.kind==='finding'&&(f.subjectId===node.id||f.id===node.id));
  if(node.kind==='decision'&&editable)button(parent,'Добавить файндинг',()=>showForm('finding',{subjectId:node.id,nodeId:node.id}));
  if(node.kind!=='finding'){
   const filters=el('div',null,'rdg-row');parent.append(filters);
   field(filters,'Поиск файндингов',state.query,'search',v=>{state.query=v;draw();});
   select(filters,'Итог',[['all','Все'],...Object.entries(findingDispositions)],state.disposition,v=>{state.disposition=v;draw();});
  }
  const list=el('div',null,'rdg-finding-list');parent.append(list);
  function draw(){list.replaceChildren();const rows=all.filter(f=>(state.disposition==='all'||f.disposition.code===state.disposition)&&(!state.query||(f.title+' '+f.description+' '+findingTypes[f.findingType]).toLowerCase().includes(state.query.toLowerCase())));
   if(!rows.length)list.append(el('p',all.length?'По фильтру ничего не найдено.':'Файндингов пока нет.','rdg-muted'));
   for(const f of rows){const card=el('article',null,'rdg-card rdg-finding-card');card.dataset.findingId=f.id;list.append(card);recommendationDetails(card,f);
    card.append(el('small',findingCodes[f.findingType]+'-'+f.id.slice(0,8)+' · '+findingTypes[f.findingType]),el('h4',f.title),el('p',f.description));
    card.append(el('p',findingDispositions[f.disposition.code]+(f.review?.required?' · Требуется пересмотр':' · Не требует пересмотра'),'rdg-finding-state'));
    const responses=snapshot.graph.edges.filter(e=>e.type==='FINDING_RESPONSE'&&e.findingId===f.id);
    const linkedQuestions=relatedQuestions(f.id);
    if(linkedQuestions.length){const related=el('div',null,'rdg-question-related');card.append(related);
     related.append(el('small','Связанные Questions · '+linkedQuestions.length));
     for(const question of linkedQuestions){const link=button(related,question.title+' · '+questionState(question),()=>openQuestions(question.id));
      link.className='rdg-question-ref';link.dataset.findingQuestionId=question.id;}
    }
    for(const q of (f.questions||[]).filter(q=>q.blocking!=='non-blocking'))card.append(el('p',(q.blocking==='partially-blocking'?'Частично блокирует: ':'Блокирует: ')+q.question+(q.scope?' · '+q.scope:''),'rdg-dependency-warning'));
    const actions=el('div',null,'rdg-policy-actions');card.append(actions);
    if(editable){
     button(actions,'Изменить файндинг',()=>showForm('finding',{nodeId:f.id,edit:true}));
     if(f.review?.required)button(actions,'Подтвердить пересмотр',()=>showForm('command',{nodeId:f.id,command:'review'}));
     button(actions,'Указать итог рассмотрения',()=>showForm('findingDisposition',{nodeId:f.id}));
     if(f.subjectSnapshot.kind!=='decision')card.append(el('small','Совместимая находка прежнего элемента'));
     if(f.subjectSnapshot.kind!=='decision'||responses.length)button(actions,'Перенести к решению',()=>showForm('findingTransfer',{nodeId:f.id}));
    }
    button(actions,'Зависимости',()=>{rememberFindingSource(node.id);return openDependencyInspector(f.id);});
    if(responses.length){const old=el('details');old.append(el('summary','Совместимые решения прежнего workflow'));card.append(old);
     for(const edge of responses){findingReference(old,edge.to,node.id);for(const proposal of snapshot.graph.edges.filter(e=>e.type==='FINDING_PROPOSAL'&&e.from===edge.to&&e.findingId===f.id))findingReference(old,proposal.to,node.id);}
    }
    const detail=el('details');detail.append(el('summary','Обоснование, вопросы и история'),el('p',f.rationale));card.append(detail);
    const scope=(snapshot.findings||[]).find(r=>r.findingId===f.id);if(scope?.relativeLevel)detail.append(el('p','Относительно области проверки: '+scope.relativeLevel));
    for(const impact of scope?.proposalImpacts||[])if(impact.relativeLevel)detail.append(el('p','Proposal: '+(policyEntities().get(impact.decisionId)?.title||impact.decisionId)+' · влияние '+impact.relativeLevel));
    const subject=policyEntities().get(f.subjectId);if(subject)findingReference(detail,f.subjectId,node.id);else detail.append(el('p','Исходный элемент удалён · '+f.subjectSnapshot.title));
    for(const id of f.evidenceIds||[])findingReference(detail,id,node.id);
    for(const source of f.analysisSources||[]){const n=policyEntities().get(source.sourceId);if(n)findingReference(detail,n.id,node.id);else detail.append(el('small','Записанный источник · '+source.sourceId));detail.append(el('p','Версия '+source.revision+' · '+source.excerpt));}
    for(const q of f.questions||[])detail.append(el('p',q.question+' · '+q.impact+' · '+q.blocking+(q.scope?' · '+q.scope:'')+' · Условие ответа: '+q.closeCondition));
    if(f.userAssistance)detail.append(el('p','Нужна помощь: '+f.userAssistance));
    for(const gap of f.reviewLimitations||[])detail.append(el('p','Ограничение проверки: '+gap.claim+' · '+gap.reason+' · '+gap.limitation));
    for(const d of [...f.dispositionHistory,f.disposition]){detail.append(el('p',(findingDispositions[d.code]||d.code)+' · '+d.basis+(d.revisitTrigger?' · Вернуться: '+d.revisitTrigger:'')+(d.recordedAt?' · '+d.recordedAt:'')));if(d.replacementId)findingReference(detail,d.replacementId,node.id);}
    const technical=el('details');technical.append(el('summary','ID и версия'),el('pre',JSON.stringify({id:f.id,revision:f.revision,review:f.review},null,2)));detail.append(technical);
    if(editable)button(detail,'Удалить файндинг',()=>showForm('command',{nodeId:f.id,command:'delete'}));
   }
  }draw();
 }

 function renderInspector(parent){const s=screen(),ins=s.inspector,panel=el('section',null,'rdg-inspector');panel.setAttribute('aria-label','Сведения');
  const split=el('div',null,'rdg-split rdg-inspector-split');split.setAttribute('role','separator');split.tabIndex=0;
  split.setAttribute('aria-label','Ширина сведений');split.setAttribute('aria-orientation','vertical');
  split.setAttribute('aria-valuemin','260');
  const limit=()=>Math.max(260,Math.min(1000,parent.clientWidth-180));
  const clamp=width=>Math.max(260,Math.min(limit(),width));
  const preview=width=>{width=clamp(width);panel.style.width=width+'px';split.setAttribute('aria-valuenow',String(Math.round(width)));split.setAttribute('aria-valuemax',String(Math.round(limit())));return width;};
  parent.append(split,panel);preview(s.panels.inspectorWidth??340);let drag=null;
  split.onpointerdown=e=>{if(busy||e.button!==0)return;e.preventDefault();drag={x:e.clientX,width:panel.getBoundingClientRect().width};split.setPointerCapture(e.pointerId);};
  split.onpointermove=e=>{if(drag)preview(drag.width+drag.x-e.clientX);};
  split.onpointerup=e=>{if(!drag)return;const width=preview(drag.width+drag.x-e.clientX);drag=null;void run(()=>sync((v,s)=>s.panels.inspectorWidth=width));};
  split.onpointercancel=()=>{drag=null;preview(screen().panels.inspectorWidth??340);};
  split.onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();const width=preview(panel.getBoundingClientRect().width+(e.key==='ArrowLeft'?25:-25));void run(()=>sync((v,s)=>s.panels.inspectorWidth=width));}};
  button(panel,'Закрыть сведения',()=>sync((v,s)=>s.inspector=null,true));
  const entities=[...snapshot.graph.nodes,...snapshot.graph.objects,...snapshot.graph.externalActions];
  if(ins.kind==='recommendationScope'){const node=ins.scopeKind==='process'?{id:snapshot.graph.id,kind:'process',title:snapshot.graph.title}:snapshot.graph.workGraphs.find(w=>w.id===ins.id);if(node){panel.append(el('h3',node.title),el('h4','Рекомендации'));renderRecommendations(panel,{...node,kind:ins.scopeKind});}return;}
  if(ins.kind==='boundaries'){const area=snapshot.graph.workGraphs.find(w=>w.id===ins.workGraphId);panel.append(el('h3','Внешние связи области'));if(!area){panel.append(el('p','Область недоступна.'));return;}panel.append(el('p',area.title+' · открытие внешнего блока не меняет состав области.'));for(const edge of areaEdges(area)){const card=el('div',null,'rdg-card');card.append(el('small',edge.type));for(const id of [edge.from,edge.to])button(card,entities.find(n=>n.id===id)?.title||id,()=>focusNode(id));panel.append(card);}return;}
  if(ins.kind==='group'){
   for(const id of ins.ids){const g=snapshot.graph.decisionGroups.find(g=>g.id===id);if(!g)continue;panel.append(el('h3',g.title));
    const viewIsOpen=openedDecisionGroup(s)?.id===id;
    const go=button(panel,viewIsOpen?'Группа решений открыта':'Открыть группу',()=>openDecisionGroup(id),viewIsOpen);
    go.dataset.openDecisionGroup=id;
    button(panel,'Исходный '+(kindLabel[entities.find(n=>n.id===g.parentId)?.kind]||'Requirement')+': '+(entities.find(n=>n.id===g.parentId)?.title||g.parentId),()=>focusNode(g.parentId));
    panel.append(el('p',(g.selectionRequired?'Выбрать необходимо':'Выбор необязателен')+' · '+(g.mutuallyExclusive?'Взаимоисключение':'Совместный выбор разрешён')));
    for(const m of g.members){const d=entities.find(n=>n.id===m.decisionId);button(panel,(d?.title||m.decisionId)+' · '+(d?.selectionState||''),()=>focusNode(m.decisionId));}
    button(panel,'Изменить группу',()=>showForm('group',{groupId:id}));
   }return;
  }
  const node=entities.find(n=>n.id===ins.id);if(!node){panel.append(el('p','Сущность удалена; черновик сохранён.'));return;}
  const findingBack=findingReturns.get(screen().id);if(findingBack?.packageId===snapshot.package.packageId)button(panel,findingBack.tab==='context'?'← К контексту решения':'← К файндингам',returnToFindings);
  if(node.findingOrigin){const origin=node.findingOrigin;panel.append(el('small',origin.role==='response'?'Прежнее решение разрешить файндинг':'Прежний proposal по файндингу'));if(!origin.recordedOnly&&entities.some(n=>n.id===origin.findingId))entityReference(panel,entities.find(n=>n.id===origin.findingId),()=>focusNode(origin.findingId));else panel.append(el('p','Записанный файндинг: '+origin.title));}
  panel.append(el('h3',node.title));panel.append(el('p',node.kind+(node.selectionState?' · '+node.selectionState:'')+(snapshot.completion[node.id]?.complete?' · подтверждено':''),'rdg-muted'));panel.append(el('p',node.description||''));if(node.kind==='canon')theoryContent(panel,node);if(node.value)panel.append(el('p',node.value));if(node.scope)panel.append(el('p','Область: '+node.scope));
  if(node.kind==='action'&&snapshot.graph.externalActions.some(a=>a.id===node.id)){
   if(node.resultCondition)panel.append(el('h4','Условия результата'),el('p',node.resultCondition));
   if('subjectRefs' in node){
    const section=el('section',null,'rdg-card');section.dataset.actionSubjects=node.id;section.append(el('h4','Предмет работы'));
    for(const subject of snapshot.actionSubjects?.[node.id]||[]){
     const target=subject.node,title=target?.title||subject.reference.nodeId||subject.reference.workGraphId||'Процесс / линза';
     if(subject.status==='current'&&target)button(section,title+ (subject.changed?' · изменилось':''),()=>followActionSubject(node,subject));
     else section.append(el('p',title+' · '+subject.status,'rdg-muted'));
    }panel.append(section);
   }
   if(node.actionType==='task'&&!node.lowLevel&&!snapshot.immutableDefinition)button(panel,'Изменить метадействие',()=>showForm('planAction',{nodeId:node.id}));
  }
  if(node.kind==='action'&&(node.actionType==='task'||!node.lowLevel)){
   const e=node.estimates,box=el('section',null,'rdg-card');box.dataset.actionEstimates=node.id;
   box.append(el('h4','Оценки исполнения'),el('p','Сложность: '+(e?.complexity||'неизвестна')),el('p','Время: '+(e?.time?e.time.minSeconds+'–'+e.time.maxSeconds+' с':'неизвестно')));
   if(e?.basis)box.append(el('p',e.basis));panel.append(box);
   if(!snapshot.immutableDefinition)button(box,'Изменить оценки',()=>showForm('actionEstimates',{nodeId:node.id}));
  }
  for(const id of node.targetIds||[])button(panel,'↗ '+(entities.find(n=>n.id===id)?.title||id),()=>focusNode(id));
  const processDecision=node.kind==='decision'&&['working','copy'].includes(snapshot.package.role);
  const canonIds=[...new Set(snapshot.graph.edges.filter(e=>!e.archived&&e.type==='CANON_FOR'&&e.to===node.id).map(e=>e.from))];
  const canons=canonIds.map(id=>entities.find(n=>n.id===id&&n.kind==='canon')).filter(Boolean);
  const showCanonTab=['decision','action'].includes(node.kind);
  {
   const tabs=el('div',null,'rdg-inspector-tabs');tabs.setAttribute('role','tablist');
   tabs.setAttribute('aria-label','Вкладки сведений выбранного блока');panel.append(tabs);
   const tabButtons=new Map(),tabPanels=new Map();
   const selectInspectorTab=key=>{
    inspectorTabState.set(node.id,key);
    for(const [name,tab] of tabButtons){const selected=name===key;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;tabPanels.get(name).hidden=!selected;}
   };
   const addInspectorTab=(key,title,renderBody)=>{
    const tab=button(tabs,title,()=>selectInspectorTab(key));tab.className='rdg-inspector-tab';
    tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;tab.dataset.inspectorTab=key;
    const body=el('section',null,'rdg-inspector-tabpanel');body.setAttribute('role','tabpanel');body.setAttribute('aria-label',title);body.dataset.inspectorPanel=key;body.hidden=true;
    tabButtons.set(key,tab);tabPanels.set(key,body);panel.append(body);renderBody(body);
   };
   addInspectorTab('recommendations','Рекомендации · '+recommendationRows(node.id).length,body=>renderRecommendations(body,node));
   if(processDecision)addInspectorTab('context','Контекст принятия решения',body=>{
    const rows=snapshot.decisionContexts?.[node.id]||[];
    if(!rows.length)body.append(el('p','Контекстных оснований пока нет.','rdg-muted'));
    if(node.analysisSources?.length){const sources=el('details');sources.append(el('summary','Источники анализа'));for(const source of node.analysisSources){const n=entities.find(n=>n.id===source.sourceId);if(n)entityReference(sources,n,()=>focusNode(n.id));sources.append(el('p','Версия '+source.revision+' · '+source.excerpt));}body.append(sources);}
    for(const entry of rows){const target=entities.find(n=>n.id===entry.sourceId),row=el('div',null,'rdg-context-dependency-row');row.dataset.contextSourceId=entry.sourceId;
     if(entry.edgeIds.length)row.dataset.contextDependencyId=entry.edgeIds[0];else if(entry.manual)row.dataset.legacyDependencyId=entry.sourceId;
     if(target){entityReference(row,target,()=>focusNode(target.id));if(target.kind==='context'&&contextPath(target.contextGroupId))row.append(el('small',contextPath(target.contextGroupId)));}
     else row.append(el('small','Удалённый источник · '+entry.sourceId));
     if(entry.comment||entry.manual)row.append(el('p',entry.comment||'Роль не описана'));
     const seen=new Set();for(const origin of entry.provenance){const key=origin.findingId+'|'+origin.enabled;if(seen.has(key))continue;seen.add(key);
      const line=el('div',null,'rdg-muted');line.append(el('span','Из файндинга · '+(origin.enabled?'':'наблюдение отключено · ')));
      button(line,'Относится к файндингу «'+origin.findingTitle+'»',()=>{rememberFindingSource(node.id);return focusNode(origin.findingId);});row.append(line);
     }
     if(target&&isProcess()&&!snapshot.immutableDefinition){
      button(row,'Изменить роль',()=>showForm('contextEntry',{nodeId:node.id,sourceId:entry.sourceId,action:'note',comment:entry.comment}));
      if(entry.manual){button(row,'Настроить',()=>showForm('dependencyRule',{nodeId:node.id,sourceId:entry.sourceId,edgeId:entry.edgeIds[0],context:true,comment:entry.comment,convertLegacy:entry.edgeIds.length?null:entry.sourceId}));
       button(row,'Убрать ручное участие',()=>showForm('contextEntry',{nodeId:node.id,sourceId:entry.sourceId,action:'remove'}));}
      else row.append(el('small','Участие управляется находкой и её зависимостями.'));
     }
     body.append(row);
    }
    if(isProcess()&&!snapshot.immutableDefinition){button(body,'+ Зависимость контекста',()=>showForm('contextEntry',{nodeId:node.id}));button(body,'Изменить контекст решения',()=>showForm('decisionContext',{nodeId:node.id,decisionContextIds:[...(node.decisionContextIds||[])]}));}
   });
   if(showCanonTab)addInspectorTab('canon','Теория принятия решения',body=>{
    body.append(el('p','Каноны описывают подходящие, пограничные и плохие ситуации, включая известные ошибки. Общее содержит остальные сведения. Теория относится к Decision или Action; выбор и выполнение фиксируются отдельно.','rdg-muted'));
    if(!canons.length)body.append(el('p','Теория принятия решения для этого блока пока не задана.','rdg-muted'));
    if(['working','copy'].includes(snapshot.package.role)&&!snapshot.immutableDefinition)
     button(body,'Добавить теорию',()=>showForm('add',{parentId:node.id,kind:'canon'}));
    for(const canon of canons){
     const card=el('article',null,'rdg-canon-card');card.append(el('h4',canon.title));
     if(canon.description)card.append(el('p',canon.description,'rdg-muted'));
     theoryContent(card,canon);

     const infoIds=[...new Set(snapshot.graph.edges.filter(e=>!e.archived&&e.type==='INFO_FOR'&&e.to===canon.id).map(e=>e.from))];
     const infos=infoIds.map(id=>entities.find(n=>n.id===id&&n.kind==='info')).filter(Boolean);
     if(infos.length){
      const list=el('div',null,'rdg-canon-info-list');list.append(el('small','Связанная информация · '+infos.length));
      for(const info of infos){
       const row=el('div',null,'rdg-canon-info-row');entityReference(row,info,()=>focusNode(info.id));
       if(info.description)row.append(el('p',info.description,'rdg-muted'));
       if(info.value)row.append(el('p',info.value));
       if(processDecision&&isProcess()&&!snapshot.immutableDefinition){const use=el('details');use.append(el('summary','Использовать в анализе'));button(use,'Добавить в контекст решения',()=>showForm('contextEntry',{nodeId:node.id,analysisSourceId:info.id}));button(use,'Записать файндинг',()=>showForm('finding',{subjectId:node.id,analysisSourceId:info.id}));row.append(use);}
       list.append(row);
      }
      card.append(list);
     }
     if(['working','copy'].includes(snapshot.package.role)&&!snapshot.immutableDefinition){
      const actions=el('div',null,'rdg-canon-actions');
      button(actions,'Переименовать',()=>showForm('rename',{nodeId:canon.id,title:canon.title}));
      button(actions,'Изменить содержание',()=>showForm('content',{nodeId:canon.id}));
      button(actions,'Добавить информацию',()=>showForm('add',{parentId:canon.id,kind:'info'}));
      if(processDecision){button(actions,'Добавить в контекст решения',()=>showForm('contextEntry',{nodeId:node.id,analysisSourceId:canon.id}));button(actions,'Записать файндинг',()=>showForm('finding',{subjectId:node.id,analysisSourceId:canon.id}));}
      card.append(actions);
     }
     body.append(card);
    }
   });
   if(isProcess()&&node.kind==='requirement'&&!snapshot.immutableDefinition)button(panel,'Обсудить обязательность',()=>showForm('requirementDecision',{nodeId:node.id}));
   if(isProcess()&&(node.kind==='decision'||node.kind==='finding'||snapshot.graph.objects.some(f=>f.kind==='finding'&&f.subjectId===node.id)))addInspectorTab('findings','Файндинги',body=>renderFindings(body,node));
   if(isProcess()){
    const qs=relatedQuestions(node.id);
    if(qs.length||node.kind==='question'||isProcess())addInspectorTab('questions','Вопросы · '+qs.length,body=>{
     if(!qs.length)body.append(el('p','Связанных вопросов нет.','rdg-muted'));
     if(!snapshot.immutableDefinition){button(body,'Добавить вопрос об элементе',()=>showForm('question',{relatedIds:[node.id]}));if(node.questions?.length)button(body,'Перенести прежние вопросы',()=>showForm('questionMigrate',{nodeId:node.id}));}
     for(const q of qs){
      const card=el('div',null,'rdg-question-inspector-link');card.dataset.relatedQuestionId=q.id;
      button(card,q.title,()=>openQuestions(q.id));
      card.append(el('small',questionState(q)));body.append(card);
     }
    });
   }
   addInspectorTab('dependencies','Зависимости',body=>renderEntityDependencies(body,node,entities));
   const remembered=inspectorTabState.get(node.id),fallback=processDecision?'context':showCanonTab?'canon':'dependencies';
   selectInspectorTab(tabButtons.has(remembered)?remembered:fallback);
  }
  if(node.kind==='decision'){
   const questions=el('details');questions.append(el('summary','Вопросы и помощь'));panel.append(questions);
   for(const q of node.questions||[])questions.append(el('p',q.question+' · '+q.impact+' · '+q.blocking+(q.scope?' · '+q.scope:'')+' · '+q.closeCondition));
   for(const gap of node.reviewLimitations||[])questions.append(el('p',gap.claim+' · '+gap.reason+' · '+gap.limitation));
   if(node.userAssistance)questions.append(el('p',node.userAssistance));
   if(isProcess()&&!snapshot.immutableDefinition){
    button(questions,'Добавить самостоятельный вопрос',()=>showForm('question',{relatedIds:[node.id]}));
    if(node.questions?.length)button(questions,'Перенести прежние вопросы',()=>showForm('questionMigrate',{nodeId:node.id}));
   }
  }
  for(const group of snapshot.graph.decisionGroups.filter(g=>g.parentId===node.id||g.members.some(m=>m.decisionId===node.id)))button(panel,'Группа: '+group.title,()=>showDecisionGroupDetails([group.id]));
  const work=['working','copy'].includes(snapshot.package.role);
  if(!snapshot.immutableDefinition){button(panel,'Переименовать блок',()=>showForm('rename',{nodeId:node.id,title:node.title}));button(panel,'Изменить содержание',()=>showForm(node.kind==='finding'?'finding':'content',{nodeId:node.id,edit:true}));if(node.kind==='requirement')button(panel,'Основания корня',()=>showForm('rootCause',{nodeId:node.id}));button(panel,'Добавить связанный блок',()=>showForm('add',{parentId:node.id}));}
  if(work){
   button(panel,'Подтвердить пересмотр',()=>showForm('command',{nodeId:node.id,command:'review'}));
   if(node.kind==='decision'){button(panel,'Выбрать Decision',()=>showForm('command',{nodeId:node.id,command:'select'}));button(panel,'Отказаться от Decision',()=>showForm('command',{nodeId:node.id,command:'withdraw'}));}
   if(['requirement','decision','action'].includes(node.kind)){button(panel,'Подтвердить результат',()=>showForm('command',{nodeId:node.id,command:'complete'}));button(panel,'Переоткрыть',()=>showForm('command',{nodeId:node.id,command:'reopen'}));}
   if(node.kind!=='finding')button(panel,'Разместить в Plan',()=>showForm('place',{nodeId:node.id}));button(panel,'Удалить блок',()=>showForm('command',{nodeId:node.id,command:'delete'}));
  }
  const extra=el('details');extra.append(el('summary','Версия и ID'),el('pre',JSON.stringify({id:node.id,revision:node.revision,review:node.review,result:node.result},null,2)));panel.append(extra);
 }
 async function openRoadControls(mode){
  if(!screen())return;
  roadUiFor(screen()).open=mode;
  if(!screen().panels.roadVisible)await sync((v,s)=>s.panels.roadVisible=true,true);
  else render();
 }
 function roadAvailableBounds(kind){
  const w=roadDefaultWindows()[kind],days=[w.from,w.to];
  const include=value=>{const day=validRoadDay(String(value||'').slice(0,10));if(day)days.push(day);};
  if(kind==='historyWindow'){
   for(const r of history?.events||[])include(r.event?.recordedAt);
   for(const r of history?.planVersions||[])include(r.acceptedAt||r.recordedAt);
  }else for(const r of snapshot?.plan?.timeConstraints||[])include(r.at);
  days.sort();return {from:days[0],to:days.at(-1)};
 }
 async function applyRoadWindow(kind,ui){
  const draft=ui.drafts[kind]||{},from=validRoadDay(draft.from),to=validRoadDay(draft.to),bounds=roadAvailableBounds(kind);
  const reason=!from||!to?'Введите существующую дату в формате дд.мм.гггг.':
   from>to?'Начало периода не может быть позже конца.':
   from<bounds.from||to>bounds.to?'Доступный период: '+roadEditDay(bounds.from)+' — '+roadEditDay(bounds.to):'';
  if(reason){ui.errors[kind]=reason;render();return;}
  ui.errors[kind]='';ui.months[kind]=from.slice(0,7);ui.drafts[kind]={from:roadEditDay(from),to:roadEditDay(to)};
  await changeView({[kind]:{from,to}});
 }
 function renderRoadPopup(road,s,ui){
  if(!ui.open)return;
  const settings=ui.open==='settings',box=el('section',null,'rdg-road-flyout');
  box.dataset.roadPopover=ui.open;box.setAttribute('aria-label',settings?'Настройки временной дороги':'Границы показа History и Plan');
  box.setAttribute('role','region');road.append(box);
  box.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();ui.open=null;render();}};
  const headHeight=road.querySelector('.rdg-road-head')?.offsetHeight||78;
  box.style.top=(headHeight+4)+'px';box.style.maxHeight='calc(100% - '+(headHeight+14)+'px)';
  const head=el('div',null,'rdg-road-fly-head');box.append(head);head.append(el('h4',settings?'Настройки дороги':'Границы показа'));
  button(head,'×',()=>{ui.open=null;render();}).setAttribute('aria-label','Закрыть панель');
  if(settings){
   select(box,'Индикатор связи с Plan',[['dot','Только цветной кружок'],['label','Подпись']],ui.badgeMode,v=>{ui.badgeMode=v;render();}).dataset.roadSetting='badgeMode';
   box.append(el('p','Фиолетовый — связь с Plan; красный — событие без размещения.','rdg-road-window-note'));
   field(box,'Low-level Actions в графе и Plan',s.spec.showLowLevel===true,'checkbox',v=>run(()=>changeView({showLowLevel:v}))).dataset.roadSetting='showLowLevel';
   for(const [key,label,min,max,step] of roadRanges){
    const row=el('label',null,'rdg-road-setting'),title=el('span');row.append(title);title.append(el('span',label));
    const output=el('output',ui.settings[key]+' px');output.dataset.roadOutput=key;title.append(output);
    const input=el('input');input.type='range';input.min=min;input.max=max;input.step=step;input.value=ui.settings[key];input.dataset.roadSetting=key;
    row.append(input);box.append(row);
    input.oninput=()=>{ui.settings[key]=Number(input.value);output.textContent=input.value+' px';road.style.setProperty('--road-'+key.replace(/[A-Z]/g,c=>'-'+c.toLowerCase()),input.value+'px');};
   }
   button(box,'Сбросить настройки',()=>{ui.settings={...roadDefaults};ui.badgeMode='dot';render();});
   return;
  }
  for(const [kind,title] of [['historyWindow','History'],['planWindow','Plan']]){
   const area=el('fieldset');area.dataset.roadArea=title.toLowerCase();box.append(area);area.append(el('legend',title));
   const window=roadWindow(s,kind),bounds=roadAvailableBounds(kind),draft=ui.drafts[kind]??={from:roadEditDay(window.from),to:roadEditDay(window.to)};
   const inputs=el('div',null,'rdg-road-date-inputs');area.append(inputs);
   for(const edge of ['from','to']){
    const label=el('label',edge==='from'?'С':'По'),input=el('input');input.type='text';input.placeholder='дд.мм.гггг';
    input.value=draft[edge];input.dataset.roadBound=kind+'.'+edge;input.setAttribute('aria-invalid',String(!!ui.errors[kind]));
    label.append(input);inputs.append(label);input.oninput=()=>{draft[edge]=input.value;ui.errors[kind]='';input.setAttribute('aria-invalid','false');};
   }
   if(ui.errors[kind]){const err=el('p',ui.errors[kind],'rdg-road-error');err.setAttribute('role','alert');area.append(err);}
   const month=ui.months[kind]||validRoadDay(draft.from)?.slice(0,7)||window.from.slice(0,7);ui.months[kind]=month;
   const nav=el('div',null,'rdg-row');area.append(nav);
   const shift=n=>{const d=new Date(month+'-01T12:00:00Z');d.setUTCMonth(d.getUTCMonth()+n);ui.months[kind]=d.toISOString().slice(0,7);render();};
   button(nav,'‹',()=>shift(-1),month<=bounds.from.slice(0,7)).setAttribute('aria-label','Предыдущий месяц '+title);
   nav.append(el('strong',new Intl.DateTimeFormat('ru-RU',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(month+'-01T12:00:00Z'))));
   button(nav,'›',()=>shift(1),month>=bounds.to.slice(0,7)).setAttribute('aria-label','Следующий месяц '+title);
   const grid=el('div',null,'rdg-calendar');area.append(grid);
   for(const d of ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'])grid.append(el('small',d));
   const first=new Date(month+'-01T12:00:00Z'),offset=(first.getUTCDay()+6)%7,total=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
   for(let i=0;i<offset;i++)grid.append(el('span'));
   for(let i=1;i<=total;i++){
    const day=month+'-'+String(i).padStart(2,'0');
    const b=button(grid,String(i),async()=>{
      const anchor=ui.anchors[kind];
      if(!anchor){ui.anchors[kind]=day;ui.drafts[kind]={from:roadEditDay(day),to:roadEditDay(day)};render();return;}
      ui.anchors[kind]=null;ui.drafts[kind]={from:roadEditDay(anchor<day?anchor:day),to:roadEditDay(anchor>day?anchor:day)};
      await applyRoadWindow(kind,ui);
    },day<bounds.from||day>bounds.to);
    b.dataset.roadDay=day;b.dataset.area=kind;b.setAttribute('aria-label',roadEditDay(day));
    b.setAttribute('aria-pressed',String(day>=window.from&&day<=window.to));
    if(day===window.from||day===window.to)b.classList.add('rdg-range-edge');
   }
   area.append(el('p',ui.anchors[kind]?'Начало: '+roadEditDay(ui.anchors[kind])+' · выберите конец':'Первый клик — начало, второй — конец','rdg-road-window-note'));
   button(area,'Применить '+title,()=>applyRoadWindow(kind,ui));
   area.append(el('p','Доступный период: '+roadEditDay(bounds.from)+' — '+roadEditDay(bounds.to),'rdg-road-window-note'));
  }
  box.append(el('p','Границы включают оба дня. Шаги Plan без даты остаются в порядке.','rdg-road-window-note'));
 }
 function policyRoleName(policy,id){return policy.roles?.find(r=>r.id===id)?.name||({target:'Зависимый элемент',source:'Источник изменений',parent:'Родительский Decision',parents:'Непосредственные родители',children:'Непосредственные дети',context:'Элементы контекста'}[id])||id;}
 function dependencyCapabilities(){return snapshot?.dependencyCatalog?.capabilities||{};}
 function relationMetadata(id){return dependencyCapabilities().relations?.find(r=>r.id===id)||{id,name:id,description:'',example:''};}
 function relationName(types){return [].concat(types).map(id=>relationMetadata(id).name).join(' / ');}
 function observationMetadata(id){return dependencyCapabilities().observations?.find(o=>o.id===id)||{id,name:dependencyLabels[id]||id,description:'',example:'',operationLabels:{}};}
 function eventMetadata(id){return dependencyCapabilities().eventDescriptions?.find(e=>e.id===id)||{id,name:id,description:''};}
 function renderMeaning(parent,entry,{technicalId=false,compact=false}={}){
  const box=el('div',null,'rdg-policy-meaning');if(entry.id)box.dataset.capabilityId=entry.id;parent.append(box);
  if(entry.description)box.append(el('p',entry.description,compact?'rdg-muted':null));
  if(entry.example){const example=el('details');example.append(el('summary','Пример'),el('p',entry.example));box.append(example);}
  if(technicalId&&entry.id){const code=el('details');code.append(el('summary','Техническое обозначение'),el('code',entry.id));box.append(code);}
  return box;
 }
 function renderPolicyRelationChoice(parent,label,value,onChange,cap){
  const box=el('fieldset');parent.append(box);box.append(el('legend',label));
  const chosen=Array.isArray(value)?value:[value];
  for(const rel of cap.relations){const item=el('div',null,'rdg-policy-choice');box.append(item);
   field(item,rel.name||rel.id,chosen.includes(rel.id),'checkbox',yes=>{const values=new Set(chosen);yes?values.add(rel.id):values.delete(rel.id);onChange([...values]);});
   renderMeaning(item,rel,{technicalId:true,compact:true});
  }
  box.append(el('p','Несколько отмеченных типов — альтернативы: достаточно любого из них. Отдельные обязательные отношения выполняются одновременно.','rdg-muted'));
 }
 const policyPredicateLabels={selectionState:'Состояние выбора Decision','result.state':'Состояние результата','result.truth':'Истинность результата',tag:'Метка элемента',active:'Структурная активность'};
 function policyPredicateValue(value){return ({discovered:'Обнаружен',selected:'Выбран',unselected:'Выбор снят',open:'Открыт',confirmed:'Подтверждён',true:'Да',false:'Нет',unknown:'Не определено'})[String(value)]??String(value);}
 function policyPredicateText(predicate){return (policyPredicateLabels[predicate.field]||predicate.field)+': '+(predicate.field==='tag'?String(predicate.equals):policyPredicateValue(predicate.equals));}
 function renderPolicyPredicate(parent,predicate,onChange,cap){
  const values={selectionState:['discovered','selected','unselected'],'result.state':['open','confirmed'],'result.truth':['true','false','unknown'],active:[true,false]};
  const key=predicate?.field||'tag';
  select(parent,'Поле условия',cap.predicateFields.map(k=>[k,policyPredicateLabels[k]||k]),key,v=>{onChange({field:v,equals:values[v]?.[0]??''});render();});
  if(values[key])select(parent,'Значение условия',values[key].map(v=>[String(v),policyPredicateValue(v)]),String(predicate?.equals),v=>onChange({...predicate,equals:key==='active'?v==='true':v}));
  else field(parent,'Значение условия',String(predicate?.equals??''),'text',v=>onChange({...predicate,equals:v}));
 }
 function actualPolicyRoles(policy,binding){
  const graph=snapshot.graph,ns=policyEntities(),out={target:[binding.targetId]},links=[...graph.edges];
  for(const group of graph.decisionGroups)for(const m of group.members)links.push({id:m.id,type:'DECISION_MEMBER',from:group.parentId,to:m.decisionId});
  for(const node of ns.values()){
   if(node.kind==='decision'){const ids=new Set(node.decisionContextIds||[]);for(const e of graph.edges)if(e.type==='DEPENDS_ON'&&e.dependencyPurpose==='decisionContext'&&e.to===node.id)ids.add(e.from);for(const id of ids)links.push({id:'context:'+node.id+':'+id,type:'DECISION_CONTEXT',from:id,to:node.id});}
   if(node.kind==='action')for(const id of node.targetIds||[])links.push({id:'action-target:'+node.id+':'+id,type:'ACTION_TARGET',from:node.id,to:id});
  }
  if(policy.pattern!=='roles'){out[policy.pattern==='direct'?'source':'parent']=[binding.sourceId||binding.parentId];return out;}
  const passes=(id,role)=>{const node=ns.get(id);if(!node||!role.kinds.includes(node.kind))return false;return (role.conditions||[]).every(p=>{
   if(p.field==='tag')return (node.tags||[]).includes(p.equals);
   if(p.field==='active')return (snapshot.view?.support?.activeIds||[]).includes(id)===p.equals;
   return p.field.split('.').reduce((value,key)=>value?.[key],node)===p.equals;
  });};
  for(const role of policy.roles){if(role.id==='target'){out.target=out.target.filter(id=>passes(id,role));continue;}
   if(!role.selector){out[role.id]=[binding.participantBindings?.[role.id]].filter(id=>id&&passes(id,role));continue;}
   const sel=role.selector;let front=out[sel.anchor]||[],found=new Set(),seen=new Set(front);
   for(let depth=1;depth<=sel.maxDepth;depth++){const next=new Set();for(const id of front){
    if((Array.isArray(sel.relation)?sel.relation:[sel.relation]).includes('SHARED_WORK_GRAPH')){for(const w of graph.workGraphs)if(w.memberIds.includes(id))for(const member of w.memberIds)if(!seen.has(member))next.add(member);}
    for(const e of links)if((Array.isArray(sel.relation)?sel.relation:[sel.relation]).includes(e.type)&&e[sel.direction==='out'?'from':'to']===id&&!seen.has(e[sel.direction==='out'?'to':'from']))next.add(e[sel.direction==='out'?'to':'from']);
   }if(depth>=sel.minDepth)for(const id of next)found.add(id);for(const id of next)seen.add(id);front=[...next];}
   out[role.id]=[...found].filter(id=>passes(id,role));
  }return out;
 }
 function renderActualPolicyRoles(parent,policy,binding){
  const saved=dependencyDetails().find(row=>row.id===binding.id&&row.policyId===policy.id&&row.policyVersion===policy.version&&row.targetId===binding.targetId&&row.binding.sourceId===binding.sourceId&&row.binding.parentId===binding.parentId&&JSON.stringify(row.binding.participantBindings||{})===JSON.stringify(binding.participantBindings||{}));if(saved){renderApplicationParticipants(parent,saved);return;}
  const out=actualPolicyRoles(policy,binding);for(const [role,ids] of Object.entries(out)){
   const row=el('div',null,'rdg-policy-participants');parent.append(row);row.append(el('b',policyRoleName(policy,role)+': '));
   if(!ids.length)row.append(el('span','Набор пуст'));for(const id of ids)policyReference(row,id,role);
  }
  for(const role of policy.roles||[])if(role.selector)parent.append(el('p',(role.selector.direction==='in'?policyRoleName(policy,role.id):policyRoleName(policy,role.selector.anchor))+' → '+relationName(role.selector.relation)+' → '+(role.selector.direction==='in'?policyRoleName(policy,role.selector.anchor):policyRoleName(policy,role.id))));
  for(const r of policy.relations||[])parent.append(el('p','Обязательно: '+policyRoleName(policy,r.from)+' → '+relationName(r.type)+' → '+policyRoleName(policy,r.to)));
 }
 const policyOperationLabels={changed:'Изменилось',added:'Добавлено',removed:'Удалено'};
 const policyPatternLabels={roles:'Схема участников и отношений',direct:'Конкретный источник → зависимый блок',parentDecisionContext:'Контекст родительского Decision → непосредственный ребёнок'};
 function policyEntities(){return new Map([...snapshot.graph.nodes,...snapshot.graph.objects,...snapshot.graph.externalActions].map(n=>[n.id,n]));}
 function latestPolicies(){const out=new Map();for(const p of snapshot.dependencyCatalog?.policies||snapshot.graph.dependencyPolicies||[]){const old=out.get(p.id);if(!old||old.version<p.version)out.set(p.id,p);}return [...out.values()].sort((a,b)=>a.name.localeCompare(b.name,'ru'));}
 function builtInPolicies(){return (snapshot.dependencyCatalog?.systemPolicies||[]).map(p=>({...p,builtIn:true}));}
 function allPolicies(){return [...builtInPolicies(),...latestPolicies()];}
 function openPolicy(id,ruleId=null,version=null){if(ruleId&&snapshot.dependencyCatalog?.policyAliases?.[id])id=snapshot.dependencyCatalog.policyAliases[id];return sync((v,t)=>{
   t.presentation??={mode:'dependencies',expandedPaths:[],collapsedPaths:[],query:''};
   t.presentation.mode='dependencies';t.presentation.dependencyTab='policies';
   t.presentation.selectedPolicyId=id;t.presentation.selectedPolicyVersion=version;
   t.presentation.selectedPolicyRuleId=ruleId;
  },true);}
 function openDependencyInspector(id){inspectorTabState.set(id,'dependencies');return sync((v,t)=>{if(t.presentation.mode==='dependencies')t.presentation.mode='graph';t.inspector={kind:'entity',id};},true);}
 function policyReference(parent,id,role){const node=policyEntities().get(id);if(!id)return;parent.append(el('span',role+' · '+id,'rdg-policy-chip'));if(node)entityReference(parent,node,()=>openDependencyInspector(id));}
 function policyDiagram(parent,policy){const schema=el('div',null,'rdg-policy-schema');parent.append(schema);
  function symbol(kind,role,desc){const part=el('div',null,'rdg-policy-symbol');colorize(part,kind);part.append(el('b',role),el('small',desc));schema.append(part);}
  if(policy.pattern==='roles'){
   for(const role of policy.roles){symbol(role.kinds[0],policyRoleName(policy,role.id),role.kinds.map(k=>kindLabel[k]||k).join(' / '));
    if(role.selector)schema.append(el('span',(role.selector.direction==='in'?policyRoleName(policy,role.id):policyRoleName(policy,role.selector.anchor))+' → '+relationName(role.selector.relation)+' → '+(role.selector.direction==='in'?policyRoleName(policy,role.selector.anchor):policyRoleName(policy,role.id))+' · глубина '+role.selector.minDepth+'–'+role.selector.maxDepth,'rdg-policy-arrow'));
    schema.append(el('small',role.selector?(role.required?'Этот набор должен оставаться непустым.':'Набор может быть пустым; его участники определяются по текущему Graph.'):policy.automatic?'Участник определяется автоматически по отношениям Graph.':'Конкретный элемент выбирается при применении политики.'));
    for(const condition of role.conditions||[])schema.append(el('span','Условие применимости роли — '+policyPredicateText(condition),'rdg-policy-chip'));}
   for(const rel of policy.relations||[])schema.append(el('span','Обязательно: '+policyRoleName(policy,rel.from)+' → '+relationName(rel.type)+' → '+policyRoleName(policy,rel.to),'rdg-policy-chip'));
   if(!policy.relations.length&&policy.roles.every(r=>!r.selector))schema.append(el('p','Структурная связь не требуется. Источник выбирается при применении.'));
  }else if(policy.pattern==='parentDecisionContext'){
   symbol('context','C · Элементы контекста','Динамический набор решения P');schema.append(el('span','→','rdg-policy-arrow'));
   symbol('decision','P · Родитель','Обязательно Decision');schema.append(el('span','→','rdg-policy-arrow'));
   symbol('requirement','T · Ребёнок','Непосредственный R / Act');
  }else{
   symbol(policy.sourceKinds[0]||'context','S · Источник','Абстрактная роль источника');schema.append(el('span','→ требует пересмотра →','rdg-policy-arrow'));
   symbol(policy.targetKinds[0]||'decision','T · Зависимый','Абстрактная роль цели R / D / Act');
  }
 }
 async function savePolicyChange(action,value,description){const req=await requestCore('policy_change',snapshot.graph.rootRequirementId,description,{action,value});if(snapshot.dependencyCatalog?.revision!=null)req.expectedDependencyCatalogRevision=snapshot.dependencyCatalog.revision;await prepare(req);}
 function openQuestions(questionId=null){
  if(!isProcess())throw Error('Вопросы доступны только для Process Graph.');
  return sync((v,s)=>{
   s.presentation??={mode:'graph',expandedPaths:[],collapsedPaths:[],query:''};
   s.presentation.mode='questions';
   if(questionId)s.presentation.questionId=questionId;
  },true);
 }
 async function followActionSubject(action,subject){
  const ref=subject.reference;
  await sync((v,s)=>{s.inspector={kind:'planningAction',id:action.id};});
  if(subject.packageId!==snapshot.package.packageId){await lens({...ref,nodeId:ref.kind?undefined:ref.nodeId});return;}
  await sync((v,s)=>{s.trail.push({packageId:s.packageId,spec:clone(s.spec),inspector:clone(s.inspector),draft:clone(s.draft),mode:s.presentation.mode,inspectorTab:inspectorTabState.get(action.id)||''});});
  if(ref.kind){await changeView(ref.kind==='workGraph'?{kind:'workGraph',id:ref.workGraphId}:{kind:'graph'});return;}
  const node=subject.node;
  if(node.kind==='question'){await openQuestions(node.id);return;}
  await focusNode(node.id);
 }
 function questionRefId(ref,q=null){
  if(ref.mode==='historical')return null;
  const key=JSON.stringify([ref.packageId,ref.identitySpace,ref.nodeId]);
  if(q?.referenceBindings?.[key])return q.referenceBindings[key];
  if(ref.identitySpace===snapshot.graph.identitySpace)return ref.nodeId;
  if(ref.mode!=='inherited')return null;
  return Object.entries(snapshot.graph.entityLineage||{}).find(([,origins])=>origins.some(p=>['packageId','identitySpace','nodeId'].every(k=>p[k]===ref[k])))?.[0]||null;
 }
 function relatedQuestions(id){
  return (snapshot?.graph?.objects||[]).filter(n=>n.kind==='question'&&
   ((n.relatedRefs||[]).some(ref=>questionRefId(ref,n)===id) || n.id===id));
 }
 function questionState(question){
  if(question.assessmentReviewRequired)return 'Требуется пересмотр достаточности';
  if(!question.assessment)return 'Достаточность не оценена';
  return question.assessment.sufficient?'Ответ признан достаточным':'Ответ недостаточен';
 }
 async function followQuestionRef(ref,q=null){
  const nodeId=questionRefId(ref,q);
  const exists=policyEntities().has(nodeId);
  if(!exists)return;
  await sync((v,s)=>{s.presentation.mode='graph';});
  await focusNode(nodeId);
 }
 function questionReferences(parent,refs,label,q=null){
  const section=el('div',null,'rdg-question-related');parent.append(section);
  section.append(el('small',label));
  if(!refs?.length){section.append(el('p','Нет записанных ссылок.','rdg-muted'));return;}
  for(const ref of refs){
   const own=ref?.packageId===snapshot.package.packageId&&ref?.identitySpace===snapshot.graph.identitySpace;
   if(ref.kind){
    const label=ref.kind==='document'?ref.uri:ref.kind==='workGraph'?(snapshot.graph.workGraphs.find(w=>w.id===ref.workGraphId)?.title||'Рабочая область недоступна'):ref.kind==='process'?'Весь процесс':'Определение линзы';
    section.append(el('p',label,'rdg-muted'));continue;
   }
   const target=policyEntities().get(questionRefId(ref,q));
   if(target){
    const b=button(section,(kindLabel[target.kind]||target.kind)+' · '+target.title,
      ()=>followQuestionRef(ref,q));b.className='rdg-question-ref';b.dataset.questionTargetId=target.id;
   }else section.append(el('p','Записанная ссылка недоступна: '+String(ref?.nodeId||'неизвестный ID'),'rdg-muted'));
  }
 }
 function renderQuestionDetail(parent,q){
  parent.dataset.questionDetailId=q.id;recommendationDetails(parent,q);
  parent.append(el('h3',q.title),el('p',questionState(q),'rdg-muted'));
  if(q.description)parent.append(el('p',q.description));
  parent.append(el('h4','Значение вопроса'),el('p',q.impact||'Не указано'));
  parent.append(el('h4','Условие достаточности'),el('p',q.answerCondition||'Не указано'));
  if(q.blocking)parent.append(el('p','Блокирование: '+q.blocking.mode+
     (q.blocking.scope?' · '+q.blocking.scope:''),'rdg-muted'));
  questionReferences(parent,q.relatedRefs,'Относится к',q);
  questionReferences(parent,q.sourceRefs,'Основания возникновения',q);
  parent.append(el('h4','Актуальные ответы · '+(q.answers?.length||0)));
  if(!q.answers?.length)parent.append(el('p','Актуальных ответов нет.','rdg-muted'));
  for(const answer of q.answers||[]){
   const card=el('article',null,'rdg-card');card.dataset.questionAnswerId=answer.id;
   card.append(el('small',({hypothesis:'Гипотеза',observation:'Наблюдение',user_answer:'Ответ пользователя'}[answer.kind])+
     ' · '+(answer.recordedBy||'')+(answer.recordedAt?' · '+answer.recordedAt:'')),
     el('p',answer.text));parent.append(card);
   if(answer.sourceRefs?.length)questionReferences(card,answer.sourceRefs,'Источники ответа',q);
   if(isProcess()&&!snapshot.immutableDefinition){
    button(card,'Изменить ответ',()=>showForm('questionAnswer',{nodeId:q.id,answerId:answer.id}));
    button(card,'Удалить ответ',()=>showForm('questionAnswer',{nodeId:q.id,answerId:answer.id,action:'remove'}));
   }
  }
  const evaluation=el('section',null,'rdg-card');evaluation.dataset.questionAssessment='';
  evaluation.append(el('h4','Оценка достаточности'));
  if(q.assessment){
   evaluation.append(el('p',(q.assessment.sufficient?'Достаточно':'Недостаточно')+
     (q.assessmentReviewRequired?' · Нужна повторная оценка':'')),
     el('p',q.assessment.basis),el('small','Связанные ответы: '+q.assessment.answerIds.length));
  }else evaluation.append(el('p','Оценка ещё не записана.'));
  parent.append(evaluation);
  const prior=q.answerHistory||[],reviews=q.assessmentHistory||[];
  if(prior.length||reviews.length){
   const history=el('details');history.append(el('summary','Предыдущие версии и оценки'));parent.append(history);
   for(const entry of prior)history.append(el('p',(entry.action==='remove'?'Удалён':'Изменён')+
     ' · '+entry.previous.text+' · '+entry.recordedAt));
   for(const entry of reviews)history.append(el('p',(entry.sufficient?'Достаточно':'Недостаточно')+
     ' · '+entry.basis+' · '+entry.recordedAt));
  }
  if(q.review?.required)parent.append(el('p','Требуется пересмотр вопроса','rdg-dependency-warning'));
  if(isProcess()&&!snapshot.immutableDefinition){
   button(parent,'Изменить вопрос',()=>showForm('question',{nodeId:q.id}));
   button(parent,'Добавить ответ',()=>showForm('questionAnswer',{nodeId:q.id}));
   button(parent,'Оценить достаточность',()=>showForm('questionAssess',{nodeId:q.id}));
   if(q.review?.required)button(parent,'Подтвердить пересмотр',()=>showForm('command',{nodeId:q.id,command:'review'}));
   button(parent,'Удалить вопрос',()=>showForm('command',{nodeId:q.id,command:'delete'}));
  }
  button(parent,'Подготовить запрос пользователю',()=>showForm('questionRequest',{nodeId:q.id}));
 }
 function renderQuestionsWorkspace(parent){
  const questions=(snapshot.graph.objects||[]).filter(n=>n.kind==='question');
  const workspace=el('section',null,'rdg-question-workspace');workspace.dataset.questionsWorkspace='';
  workspace.setAttribute('aria-label','Вопросы процесса');parent.append(workspace);
  const list=el('div',null,'rdg-question-list'),head=el('div',null,'rdg-question-list-head');
  workspace.append(list);list.append(head);
  head.append(el('h3','Вопросы процесса · '+questions.length));
  if(isProcess()&&!snapshot.immutableDefinition)button(head,'Добавить вопрос',()=>showForm('question'));
  const input=el('input');input.type='search';input.placeholder='Найти вопрос, ID, ответ или основание';
  input.setAttribute('aria-label','Поиск вопросов');head.append(input);
  const scroll=el('div',null,'rdg-question-scroll'),detail=el('section',null,'rdg-question-detail');
  list.append(scroll);workspace.append(detail);
  const sorted=questions.slice().sort((a,b)=>a.title.localeCompare(b.title,'ru')||a.id.localeCompare(b.id));
  let selectedId=sorted.some(n=>n.id===screen().presentation?.questionId)?screen().presentation.questionId:sorted[0]?.id;
  const matches=q=>{
   const term=input.value.trim().toLocaleLowerCase();
   return !term||[q.title,q.description,q.impact,q.answerCondition,q.id,
     ...(q.answers||[]).map(a=>a.text)].join(' ').toLocaleLowerCase().includes(term);
  };
  const drawDetail=()=>{
   detail.replaceChildren();
   const q=sorted.find(n=>n.id===selectedId);
   if(q)renderQuestionDetail(detail,q);
   else detail.append(el('p',questions.length?'Выберите вопрос из списка.':'В этом процессе ещё нет самостоятельных Questions.','rdg-muted'));
  };
  const drawList=()=>{
   scroll.replaceChildren();
   const filtered=sorted.filter(matches);
   if(!filtered.length){scroll.append(el('p',questions.length?'Вопросы не найдены.':'Самостоятельных вопросов пока нет.','rdg-muted'));return;}
   for(const [heading,rows] of [
    ['Вопросы Findings',filtered.filter(q=>(q.relatedRefs||[]).some(ref=>
      policyEntities().get(questionRefId(ref,q))?.kind==='finding'))],
    ['Остальные вопросы',filtered.filter(q=>!(q.relatedRefs||[]).some(ref=>
      policyEntities().get(questionRefId(ref,q))?.kind==='finding'))]]){
    if(!rows.length)continue;
    scroll.append(el('h4',heading+' · '+rows.length,'rdg-question-group'));
    for(const q of rows){
     const b=button(scroll,'',()=>{selectedId=q.id;return sync((v,s)=>{
       s.presentation.questionId=q.id;
      },true);});b.className='rdg-question-row';b.dataset.questionId=q.id;
     b.setAttribute('aria-current',String(q.id===selectedId));
     b.append(el('b',q.title),el('small',questionState(q)));
    }
   }
  };
  input.oninput=()=>{const filtered=sorted.filter(matches);
   if(!filtered.some(q=>q.id===selectedId))selectedId=filtered[0]?.id;
   drawList();drawDetail();};
  drawList();drawDetail();
 }
 function renderDependencyWorkspace(parent){const shell=el('section',null,'rdg-dependency-workspace');shell.dataset.dependencyWorkspace='';parent.append(shell);
  const head=el('header',null,'rdg-policy-header');shell.append(head);const title=el('div');title.append(el('h2','Зависимости'),el('p','Политики и инвалидация · '+snapshot.graph.title));head.append(title);
  const tabs=el('div',null,'rdg-policy-tabs');tabs.setAttribute('role','tablist');head.append(tabs);
  const chosen=screen().presentation?.dependencyTab||'stale';
  const count=(snapshot.dependencyCatalog?.invalidationRecords||[]).filter(row=>row.active).length;
  for(const [id,label] of [['stale','Инвалидация · '+count],['policies','Политики']]){
   const control=button(tabs,label,()=>sync((v,t)=>{t.presentation.dependencyTab=id;},true));control.setAttribute('role','tab');control.setAttribute('aria-selected',String(chosen===id));control.dataset.dependencyTab=id;
  }
  const dependencyBack=dependencyInspectorReturns.get(screen().id);if(dependencyBack?.packageId===snapshot.package.packageId)button(head,'← К сведениям элемента',()=>{inspectorTabState.set(dependencyBack.nodeId,'dependencies');dependencyInspectorReturns.delete(screen().id);return sync((v,t)=>{t.presentation.mode=dependencyBack.mode;t.inspector={kind:'entity',id:dependencyBack.nodeId};},true);});
  if(chosen!=='stale'&&invalidationReturns.get(screen().id)?.packageId===snapshot.package.packageId)button(head,'← К инвалидации',returnToInvalidation);
  button(head,'← К графу',()=>sync((v,t)=>{t.presentation.mode='graph';},true));
  const content=el('div',null,'rdg-policy-scroll');content.setAttribute('role','tabpanel');content.dataset.dependencyPanel=chosen;shell.append(content);
  if(chosen==='policies')renderPolicyCatalog(content);else renderStaleWorkspace(content);
 }
 function policyBindings(policy){return (snapshot.graph.dependencyBindings||[]).filter(b=>b.policyId===policy.id&&b.status!=='deleted');}
 function policyLegacyEdges(policy){if(!policy.builtIn||policy.automatic)return [];
  if(policy.id==='builtin:automatic-canon')return snapshot.graph.edges.filter(e=>e.type==='CANON_FOR');
  if(policy.id==='builtin:structural')return [
   ...snapshot.graph.edges.filter(e=>['DERIVES','INTRODUCES','DRIVES','REQUIRES_ACTION'].includes(e.type)),
   ...snapshot.graph.decisionGroups.flatMap(g=>g.members.map(m=>({id:m.id,type:'DECISION_MEMBER',from:g.parentId,to:m.decisionId})))];
  return snapshot.graph.edges.filter(e=>e.type==='DEPENDS_ON'&&'builtin:'+(e.dependencyRule?.preset||e.dependencyLevel||'L1')===policy.id);
 }
 function renderPolicyBindings(parent,policy){const box=el('section',null,'rdg-policy-bindings');parent.append(box);
  const bindings=policyBindings(policy),legacy=policyLegacyEdges(policy);
  const uses=(snapshot.dependencyCatalog?.applications||[]).filter(r=>r.policyId===policy.id);
  box.append(el('p','Доступное пространство RDG: '+uses.length+' применений · действуют '+uses.filter(r=>r.binding.enabled??r.binding.status==='active').length+' · автоматических '+uses.filter(r=>r.automatic).length,'rdg-muted'));
  for(const use of uses.filter(r=>r.packageId!==snapshot.package.packageId)){const row=el('article',null,'rdg-policy-binding');box.append(row);row.append(el('b',use.graphTitle+' · v'+use.policyVersion+' · '+(use.binding.enabled??use.binding.status==='active'?'действует':'отключено')),el('p',use.binding.id+' · '+[use.binding.sourceId,use.binding.targetId,...Object.values(use.binding.participantBindings||{})].filter(Boolean).join(', ')));button(row,'Открыть Process Graph',()=>navigate(use.packageId,{kind:'graph'}));}
  const automatic=uses.filter(r=>r.automatic&&r.packageId===snapshot.package.packageId);
  box.append(el('h3','Применения в текущем Process Graph · '+(bindings.length+legacy.length+automatic.length)));
  for(const use of automatic){const b=use.binding,active=b.enabled??b.status==='active';const row=el('article',null,'rdg-policy-binding');row.dataset.automaticBindingId=b.id;box.append(row);
   row.append(el('b','Автоматическое применение · '+(active?'действует':'отключено')),el('small',b.id));
   renderActualPolicyRoles(row,policy,{...b,participantBindings:{source:b.sourceId}});
   if(!active)row.append(el('p','Причина: '+(b.reasonCode==='applicability'?'нарушена применимость':b.reasonCode==='manual'?'отключено пользователем':b.reasonCode)));
   if(['working','copy'].includes(snapshot.package.role))button(row,active?'Отключить':'Активировать снова',()=>savePolicyChange(active?'automatic_disable':'automatic_activate',{id:b.id},'Изменено состояние автоматического применения'));
  }
  if(!bindings.length&&!legacy.length&&!automatic.length)box.append(el('p','Нет применений в этом Process Graph.','rdg-policy-empty'));
  for(const b of bindings){const row=el('article',null,'rdg-policy-binding');row.dataset.bindingId=b.id;box.append(row);
   row.append(el('b','Применение '+b.id+' · v'+b.policyVersion+' · '+(b.enabled?'действует':'отключено')));
   if(!b.enabled)row.append(el('p','Причина: '+(b.reasonCode==='applicability'?'нарушена применимость':b.reasonCode==='policy'?'версия политики отключена':'отключено пользователем')+' · '+(b.violations||[]).join(', ')));
   if(b.participantBindings)for(const [role,id] of Object.entries(b.participantBindings))policyReference(row,id,role);
   if(policy.pattern==='roles')renderActualPolicyRoles(row,policy,b);
   const participants=el('div',null,'rdg-policy-participants');row.append(participants);
   if(b.sourceId)policyReference(participants,b.sourceId,'Источник');
   if(b.parentId){policyReference(participants,b.parentId,'Родитель Decision');
    const decision=policyEntities().get(b.parentId),refs=new Set(decision?.decisionContextIds||[]);
    for(const edge of snapshot.graph.edges)if(edge.type==='DEPENDS_ON'&&edge.dependencyPurpose==='decisionContext'&&edge.to===b.parentId)refs.add(edge.from);
    row.append(el('p','Текущий контекст: '+([...refs].join(', ')||'нет'),'rdg-muted'));
   }
   policyReference(participants,b.targetId,'Зависимый');
   const actions=el('div',null,'rdg-policy-actions');row.append(actions);
   if(['working','copy'].includes(snapshot.package.role)){
    button(actions,'Изменить применение',()=>showForm('policyBinding',{bindingId:b.id,policyId:b.policyId,nodeId:b.targetId}));
    button(actions,b.enabled?'Отключить':'Активировать снова',()=>savePolicyChange(b.enabled?'binding_disable':'binding_activate',{id:b.id,expectedRevision:b.revision||1},'Изменено состояние применения '+b.id));
    button(actions,'Удалить',()=>savePolicyChange('binding_remove',{id:b.id},'Удалено применение '+b.id));
   }
  }
  for(const edge of legacy){const row=el('article',null,'rdg-policy-binding');box.append(row);
   row.append(el('small',(edge.type==='DEPENDS_ON'?'Существующая ручная зависимость':'Автоматическое структурное отношение')+' · '+edge.id));
   const part=el('div',null,'rdg-policy-participants');row.append(part);
   policyReference(part,edge.from,'Источник');policyReference(part,edge.to,'Зависимый');
   if(edge.type==='DEPENDS_ON'&&['working','copy'].includes(snapshot.package.role))button(row,'Настроить L1/L2',()=>showForm('dependencyRule',{nodeId:edge.to,edgeId:edge.id}));
  }
  if(['working','copy'].includes(snapshot.package.role)&&!policy.automatic&&policy.status==='active')
   button(box,'+ Применить политику',()=>showForm('policyBinding',{policyId:policy.id}));
 }
 function renderPolicyCatalog(parent){const grid=el('div',null,'rdg-policy-grid');parent.append(grid);
  const rail=el('aside',null,'rdg-policy-nav');grid.append(rail);const buttons=el('div',null,'rdg-policy-actions');rail.append(buttons);
  const writable=['working','copy'].includes(snapshot.package.role)&&!snapshot.immutableDefinition;
  button(buttons,'+ Новая политика',()=>showForm('policyEditor'),!writable);
  if(snapshot.dependencyCatalog?.migrationRequired)button(buttons,'Перенести прежний каталог',()=>savePolicyChange('catalog_migrate',{},'Перенесён прежний каталог без дублирования применений'),!writable);
  const all=allPolicies();
  field(rail,'Поиск политик',policyQuery,'text',value=>{policyQuery=value;render();});
  select(rail,'Показать',[['all','Все'],['system','Системные'],['user','Пользовательские'],['active','Активные'],['disabled','Отключённые'],['archived','Архивные']],policyFilter,value=>{policyFilter=value;render();});
  const policies=all.filter(p=>(!policyQuery||(p.name+' '+p.description).toLocaleLowerCase().includes(policyQuery.toLocaleLowerCase()))&&(policyFilter==='all'||policyFilter==='system'&&p.builtIn||policyFilter==='user'&&!p.builtIn||p.status===policyFilter));
  const selectedId=screen().presentation?.selectedPolicyId||policies[0]?.id;
  rail.append(el('h3','Системные политики · '+policies.filter(p=>p.builtIn).length));
  for(const p of policies){if(!p.builtIn&&!rail.dataset.userHeading){rail.dataset.userHeading='yes';rail.append(el('h3','Пользовательские политики · '+latestPolicies().length));}
   const uses=(snapshot.dependencyCatalog?.applications||[]).filter(r=>r.policyId===p.id);
   const count=uses.length;
   const b=button(rail,'',()=>openPolicy(p.id));b.className='rdg-policy-entry';b.dataset.policyId=p.id;
   b.setAttribute('aria-current',String(selectedId===p.id));
   b.append(el('b',p.name),el('small',(p.builtIn?'Системная':p.status+' · версия '+p.version)+' · применений '+count));
  }
  if(!latestPolicies().length)rail.append(el('p','Собственных политик пока нет.','rdg-muted'));
  const main=el('section',null,'rdg-policy-main');grid.append(main);
  let policy=all.find(p=>p.id===selectedId)||policies[0];
  if(!policy){main.append(el('p','Подходящих политик нет.'));return;}
  const history=(snapshot.dependencyCatalog?.policies||snapshot.graph.dependencyPolicies||[]).filter(p=>p.id===policy.id).sort((a,b)=>a.version-b.version);
  const pinnedVersion=screen().presentation?.selectedPolicyVersion;
  if(!policy.builtIn&&pinnedVersion)policy=history.find(p=>p.version===pinnedVersion)||policy;
  main.dataset.policyId=policy.id;main.dataset.policyVersion=String(policy.version);
  main.append(el('small',policy.builtIn?'СИСТЕМНАЯ ПОЛИТИКА':'ПОЛИТИКА · версия '+policy.version+' · '+policy.status),el('h2',policy.name));
  if(history.length>1)select(main,'Версия политики',history.map(p=>[String(p.version),'Версия '+p.version+' · '+p.status]),String(policy.version),
   v=>sync((session,tab)=>{tab.presentation.selectedPolicyVersion=Number(v);tab.presentation.selectedPolicyRuleId=null;},true));
  main.append(el('p',policy.description,'rdg-muted'),el('p','Тип: '+(policyPatternLabels[policy.pattern]||policy.pattern),'rdg-muted'));
  main.append(el('p','Источники: '+policy.sourceKinds.map(k=>kindLabel[k]||k).join(', ')+' · Цели: '+policy.targetKinds.map(k=>kindLabel[k]||k).join(', '),'rdg-muted'));
  const meaning=dependencyCapabilities().policyHelp?.[policy.id];
  if(meaning){const facts=el('section',null,'rdg-policy-facts');main.append(facts);facts.dataset.policyExplanation=policy.id;
   for(const [key,label] of [['applicability','Когда применение действует'],['observes','Что отслеживается'],['example','Пример']]){facts.append(el('h3',label),el('p',meaning[key]));}
   facts.append(el('h3','Результат'),el('p','При выполнении включённого условия цель получает статус «Требует пересмотра».'));
   facts.append(el('h3','Если нарушена применимость'),el('p','Применение отключается и сохраняется с причиной. Восстановление условий само по себе его не включает. Действие «Активировать снова» выполняет новую проверку.'));
  }
  main.append(el('p',policy.automatic?'Способ применения: автоматически по существующим фактам Graph.':'Способ применения: источник и цель назначаются явно; копировать политику перед использованием не требуется.','rdg-muted'));
  const actions=el('div',null,'rdg-policy-actions');main.append(actions);
  if(writable){
   if(policy.builtIn)button(actions,'Создать копию',()=>showForm('policyEditor',{copyPolicyId:policy.id}));
   else{
    button(actions,'Изменить — новая версия',()=>showForm('policyEditor',{policyId:policy.id}));
    button(actions,'Создать копию',()=>showForm('policyEditor',{copyPolicyId:policy.id}));
    for(const [status,label] of [['active','Разрешить использование'],['disabled','Отключить версию'],['archived','Архивировать версию']])if(policy.status!==status)button(actions,label,()=>savePolicyChange('policy_status',{id:policy.id,version:policy.version,status},'Изменено состояние версии политики '+policy.name));
   }
  }
  main.append(el('h3','Схема политики: роли, не реальные ID'));policyDiagram(main,policy);
  main.append(el('h3','Отслеживаемые изменения · '+policy.rules.length));
  for(const rule of policy.rules){const card=el('article',null,'rdg-policy-rule');card.dataset.ruleId=rule.id;main.append(card);
   const selectedRule=screen().presentation?.selectedPolicyRuleId===rule.id;
   card.setAttribute('aria-current',String(selectedRule));
   if(selectedRule)card.style.borderColor='#a0cef0';
   card.append(el('small',rule.enabled?'ВКЛЮЧЕНО':'ВЫКЛЮЧЕНО'),el('h4',rule.name));
   if(selectedRule){card.append(el('small','ПРАВИЛО ИЗ ВЫБРАННОГО СРАБАТЫВАНИЯ'));
    queueMicrotask(()=>{if(card.isConnected)card.scrollIntoView({block:'center'});});}
   const observation=observationMetadata(rule.watch);
   card.append(el('p','Наблюдаемый участник: '+policyRoleName(policy,rule.role||'source')));
   card.append(el('p','Что сравниваем: '+observation.name));renderMeaning(card,observation);
   card.append(el('p','Когда срабатывает: '+rule.operations.map(op=>observation.operationLabels?.[op]||policyOperationLabels[op]||op).join('; ')));
   if(rule.eventType){const event=eventMetadata(rule.eventType);card.append(el('p','Тип записанного события: '+event.name));renderMeaning(card,event,{technicalId:true});}
   if(rule.predicate)card.append(el('p','Проверяемое условие — '+policyPredicateText(rule.predicate)));
   if(rule.whenKinds)card.append(el('p','Условие действует для типов: '+rule.whenKinds.map(k=>kindLabel[k]||k).join(', ')));
   if(rule.memberRole)card.append(el('p','Изменение должно относиться к участнику роли «'+policyRoleName(policy,rule.memberRole)+'».'));

  }
  renderPolicyBindings(main,policy);
 }
 function invalidationState(){const key=screen().id+':'+snapshot.package.packageId;if(!invalidationViews.has(key))invalidationViews.set(key,{filter:'all',query:'',element:'',policy:'',version:'',cause:'',scroll:0,selectedId:null});return invalidationViews.get(key);}
 function captureInvalidationPosition(){const scroller=root.querySelector('[data-invalidation-scroll-key]');if(scroller){const state=invalidationViews.get(scroller.dataset.invalidationScrollKey);if(state)state.scroll=scroller.scrollTop;}}
 function rememberInvalidation(record){captureInvalidationPosition();invalidationState().selectedId=record.id;invalidationReturns.set(screen().id,{packageId:snapshot.package.packageId});}
 async function returnToInvalidation(){invalidationReturns.delete(screen().id);await sync((v,t)=>{t.presentation.mode='dependencies';t.presentation.dependencyTab='stale';},true);}
 function invalidationPolicy(id,version){return [...snapshot.dependencyCatalog?.systemPolicies||[],...snapshot.dependencyCatalog?.policies||[]].find(p=>p.id===id&&p.version===version);}
 function invalidationReference(parent,record,id){if(!id)return;const saved=record.participants[id],now=policyEntities().get(id),n=saved||now||{id,title:'Неизвестный участник'},box=el('div',null,'rdg-instance-reference');parent.append(box);box.dataset.invalidationParticipantId=id;
  if(now){const link=entityReference(box,{...now,...n},()=>{rememberInvalidation(record);return openDependencyInspector(id);});link.title='Перейти к элементу'+(n.title!==now.title?' · сейчас «'+now.title+'»':'');}
  else box.append(el('span',(n.title||id)+' · участник удалён или недоступен','rdg-muted'));
 }
 function invalidationPolicyLink(parent,record,id,version,ruleId,name){const text=(name||invalidationPolicy(id,version)?.name||'Политика')+(version?' · v'+version:'');
  if(id&&version&&invalidationPolicy(id,version)){const link=button(parent,text,()=>{rememberInvalidation(record);return openPolicy(id,ruleId,version);});link.dataset.invalidationPolicyId=id;link.dataset.policyVersion=String(version);link.setAttribute('aria-label',ruleId?'Открыть политику и правило':'Открыть политику');}
  else parent.append(el('span',text,'rdg-muted'));
 }
 const invalidationParts={definition:'содержание элемента','direct-scope':'данные ближайшего окружения','source-removed':'исключение источника','source-added':'добавление источника',selection:'состояние выбора Decision',result:'сохранённый результат',context:'контекст принятия решения',canon:'теория принятия решения',info:'связанные Info',structure:'структурные связи или правила групп',basis:'корневые основания'};
 function invalidationChange(hit){const rule=hit.ruleSnapshot;const watch=rule?.watch==='info'&&invalidationPolicy(hit.policyId,hit.policyVersion)?.pattern==='direct'?'canonInfo':rule?.watch;
  if(rule){if(rule.watch==='event')return eventMetadata(rule.eventType).name;
   if(rule.watch==='predicate')return (observationMetadata('predicate').operationLabels?.[hit.triggerOperation]||'Изменилось условие')+': '+policyPredicateText(rule.predicate);
   return observationMetadata(watch).operationLabels?.[hit.triggerOperation]||rule.name||hit.ruleName;
  }
  return 'Изменилось: '+hit.changedParts.map(part=>invalidationParts[part]||part).join('; ');
 }
 function invalidationTime(value){return value?new Date(value).toLocaleString('ru-RU'):'Время события не записано';}
 function invalidationDetails(parent,record,cause=null,hit=null){const details=el('details',null,'rdg-invalidation-details');parent.append(details);details.append(el('summary','Подробности события'));
  const eventId=cause?.eventId??record.eventId;details.append(el('p','Событие: '+(eventId||'не записано')));
  if(cause?.basis)details.append(el('p','Записанное основание: '+cause.basis));
  if(record.resolvedEventId)details.append(el('p','Событие разрешения: '+record.resolvedEventId));
  if(hit?.policyId)details.append(el('p','Политика: '+hit.policyId+' · версия '+hit.policyVersion+' · условие '+hit.ruleId));
  if(record.bindingId)details.append(el('p','Применение: '+record.bindingId+' · политика '+record.policyId+' · версия '+record.policyVersion));
  if(hit?.ruleSnapshot)details.append(el('p','Условие: '+hit.ruleSnapshot.name));
  if(hit?.valueSnapshot){details.append(el('p','Записанное содержание: было → стало'),el('pre',JSON.stringify(hit.valueSnapshot,null,2)));}
  const matched=hit?.matchedParticipants||record.participantRoles||{};for(const [role,ids] of Object.entries(matched))details.append(el('p',role+': '+[].concat(ids).map(id=>(record.participants[id]?.title||id)+' · '+id).join(', ')));
  for(const [id,node] of Object.entries(record.participants))details.append(el('p',node.title+' · '+id+(node.recorded?' · сведения записаны в событии':' · историческое имя не записано; показаны доступные сведения')));
  const rels=hit?.matchedRelations||record.relations||[];if(rels.length)details.append(el('p','Записанные связи: '+rels.join(', ')));
  for(const relation of record.relationSnapshot||[])details.append(el('p',(record.participants[relation.from]?.title||relation.from)+' → '+relationName(relation.type)+' → '+(record.participants[relation.to]?.title||relation.to)));
  if(record.kind==='disabled'&&!record.targetRecorded)details.append(el('p','Историческая схема полностью не записана. Цель, если доступна, показана по текущему применению.'));
 }
 function openInvalidationApplication(record){const app=dependencyDetails().find(row=>row.id===record.bindingId);if(!app)return;
  rememberInvalidation(record);dependencyInspectorFilters.set(snapshot.package.packageId+':'+app.targetId,{direction:'incoming',group:'all'});
  return openDependencyInspector(app.targetId);
 }
 function renderInvalidationCard(parent,record){const card=el('article',null,'rdg-invalidation-card');parent.append(card);card.dataset.invalidationId=record.id;card.dataset.invalidationKind=record.kind;card.dataset.invalidationActive=String(record.active);card.tabIndex=-1;
  if(invalidationState().selectedId===record.id)card.dataset.invalidationSelected='true';card.onfocus=()=>{invalidationState().selectedId=record.id;};card.onclick=()=>{invalidationState().selectedId=record.id;for(const other of parent.querySelectorAll('[data-invalidation-selected]'))delete other.dataset.invalidationSelected;card.dataset.invalidationSelected='true';};
  const head=el('div',null,'rdg-invalidation-card-head');card.append(head);const heading=el('div');head.append(heading);
  const status=record.kind==='review'?'Требуется пересмотр':'Зависимость отключена';heading.append(el('b',status,'rdg-invalidation-badge'));
  if(!record.active)heading.append(el('span',' · История · '+({reviewed:'Пересмотр подтверждён',activated:'Применение активировано',deleted:'Применение удалено',targetRemoved:'Элемент удалён',historical:'Историческая причина'})[record.resolution||'historical'],'rdg-muted'));
  if(record.kind==='review'&&!record.structurallyActive&&record.active)heading.append(el('span',' · Неактивная ветвь','rdg-invalidation-warning'));
  if(record.targetId)invalidationReference(heading,record,record.targetId);else heading.append(el('p','Цель в событии не записана.'));
  const actions=el('div',null,'rdg-policy-actions');head.append(actions);const writable=isProcess()&&!snapshot.immutableDefinition;
  if(record.targetPresent!==false&&record.targetId&&policyEntities().has(record.targetId))button(actions,'Открыть сведения',()=>{rememberInvalidation(record);return openDependencyInspector(record.targetId);});
  if(record.kind==='review'){
   if(record.active){card.dataset.staleNodeId=record.targetId;if(writable)button(actions,'Подтвердить пересмотр',()=>{rememberInvalidation(record);return showForm('command',{nodeId:record.targetId,command:'review'});}).dataset.reviewNodeId=record.targetId;}
   for(const cause of record.causes){const hits=cause.hits.length?cause.hits:[null];for(const hit of hits){const line=el('section',null,'rdg-invalidation-reason rdg-stale-reason');line.dataset.causeEventId=cause.eventId;line.dataset.triggerPolicyId=hit?.policyId||'';line.dataset.triggerRuleId=hit?.ruleId||'';card.append(line);
     const sources=el('div'),change=el('div'),policy=el('div');line.append(sources,change,policy);
     const evidence=hit?{...record,participants:{...record.participants,...Object.fromEntries(Object.entries(hit.participantSnapshot||{}).map(([id,n])=>[id,{...n,recorded:true,present:policyEntities().has(id)}]))}}:record;
     if(hit){invalidationReference(sources,evidence,hit.sourceId);change.append(el('p',invalidationChange(hit)));
      if(!hit.ruleSnapshot)change.append(el('small','Историческая причина: точное условие не записано.','rdg-muted'));
      const name=hit.policyName||({structural:'Структурная зависимость',canon:'Наблюдение теории принятия решения',decisionContext:'Контекст Decision'})[hit.origin]||'Ручная зависимость · '+(hit.preset||hit.level||'');
      invalidationPolicyLink(policy,record,hit.policyId,hit.policyVersion,hit.ruleId,name);
     }else change.append(el('p','Историческая причина: точное условие не записано.'));
     policy.append(el('small',invalidationTime(cause.recordedAt),'rdg-muted'));invalidationDetails(change,evidence,cause,hit);
    }}
  }else{
   const policy=invalidationPolicy(record.policyId,record.policyVersion)||{roles:[]};const line=el('div',null,'rdg-invalidation-disable-body');card.append(line);
   const participants=el('div'),reason=el('div');line.append(participants,reason);invalidationPolicyLink(participants,record,record.policyId,record.policyVersion,null,record.policyName);
   const sources=record.participantRoles.source||record.participantRoles.parent||[];
   for(const id of (sources.length?sources:Object.keys(record.participants)).filter(id=>id!==record.targetId))invalidationReference(participants,record,id);
   reason.append(el('p',({applicability:'Нарушена применимость политики.',manual:'Применение отключено пользователем.',policy:'Использование версии политики отключено.'})[record.reasonCode]||'Применение не действует.'));
   for(const issue of record.violations)reason.append(el('p',dependencyIssue(issue,policy)));
   reason.append(el('small',invalidationTime(record.recordedAt),'rdg-muted'));
   if(record.active){reason.append(el('p',record.applicable?'Условия сейчас выполнены. Для возобновления нужна явная активация.':'Сейчас активировать применение нельзя:','rdg-invalidation-warning'));
    for(const issue of record.currentViolations||[])reason.append(el('p',dependencyIssue(issue,policy)));
    if(record.currentTargetId!==record.targetId||record.currentPolicyId!==record.policyId||record.currentPolicyVersion!==record.policyVersion)reason.append(el('p','Применение перенастроено. Причина выше сохранена на момент отключения; действия относятся к текущему применению.','rdg-muted'));
    if(writable){button(actions,'Активировать снова',()=>{rememberInvalidation(record);return savePolicyChange(record.applicationKind==='automatic'?'automatic_activate':'binding_activate',{id:record.bindingId,expectedRevision:record.bindingRevision},'Повторная активация применения');}).dataset.invalidationActivate=record.bindingId;
     button(actions,'Удалить применение',()=>{rememberInvalidation(record);return savePolicyChange(record.applicationKind==='automatic'?'automatic_remove':'binding_remove',{id:record.bindingId,expectedRevision:record.bindingRevision},'Удалено отключённое применение');}).dataset.invalidationRemove=record.bindingId;}
   }
   if(dependencyDetails().some(row=>row.id===record.bindingId))button(actions,'Открыть применение',()=>openInvalidationApplication(record));invalidationDetails(reason,record);
  }
  if(record.resolvedAt)card.append(el('small','Разрешено: '+invalidationTime(record.resolvedAt),'rdg-muted'));
 }
 function renderStaleWorkspace(parent){const records=snapshot.dependencyCatalog?.invalidationRecords||[],ui=invalidationState();parent.dataset.invalidationScrollKey=screen().id+':'+snapshot.package.packageId;
  const controls=el('div',null,'rdg-invalidation-controls');controls.dataset.invalidationControls='';parent.append(controls);const tabs=el('div',null,'rdg-dependency-filter-buttons');controls.append(tabs);
  const choices=[];for(const [id,label] of [['all','Все актуальные'],['review','Требуется пересмотр'],['disabled','Зависимости отключены'],['history','История']]){const b=button(tabs,'',()=>{ui.filter=id;ui.scroll=0;parent.scrollTop=0;renderResults();});b.className='rdg-dependency-filter';b.dataset.invalidationFilter=id;choices.push({id,label,b});}
  const filters=el('div',null,'rdg-invalidation-filters');controls.append(filters);
  const processes=(catalog?.packages||[]).filter(p=>['working','copy'].includes(p.role));
  if(!processes.some(p=>p.packageId===snapshot.package.packageId))processes.push({packageId:snapshot.package.packageId,title:snapshot.graph.title});
  const process=select(filters,'Процесс',processes.map(p=>[p.packageId,p.title]),snapshot.package.packageId,async id=>{if(id===snapshot.package.packageId)return;await run(async()=>{await navigate(id,{kind:'graph'});await sync((v,t)=>{t.presentation.mode='dependencies';t.presentation.dependencyTab='stale';},true);});});process.dataset.invalidationProcess='';
  const entities=new Map();for(const record of records)for(const id of record.nodeIds)entities.set(id,record.participants[id]?.title||id);
  const element=select(filters,'Элемент',[['','Все элементы'],...[...entities].sort((a,b)=>a[1].localeCompare(b[1],'ru'))],ui.element,value=>{ui.element=value;renderResults();});element.dataset.invalidationElement='';
  const policies=new Map();for(const record of records)for(const [id,version] of record.policyVersions)policies.set(id,invalidationPolicy(id,version)?.name||record.policyName||record.causes?.flatMap(c=>c.hits).find(h=>h.policyId===id)?.policyName||id);
  const policy=select(filters,'Политика',[['','Все политики'],...[...policies].sort((a,b)=>a[1].localeCompare(b[1],'ru'))],ui.policy,value=>{ui.policy=value;ui.version='';versions();renderResults();});policy.dataset.invalidationPolicy='';
  const version=select(filters,'Версия',[['','Все версии']],ui.version,value=>{ui.version=value;renderResults();});version.dataset.invalidationVersion='';
  function versions(){const values=[...new Set(records.flatMap(r=>r.policyVersions.filter(([id])=>!ui.policy||id===ui.policy).map(([,v])=>v)))].sort((a,b)=>a-b);version.replaceChildren();for(const [id,label] of [['','Все версии'],...values.map(v=>[String(v),'v'+v])]){const option=el('option',label);option.value=id;version.append(option);}version.value=ui.version;}
  versions();const cause=select(filters,'Причина',[['','Все причины'],['definition','Содержание'],['context','Контекст Decision'],['structure','Связи и состав'],['selection','Выбор Decision'],['result','Результат'],['canon','Теория принятия решения'],['info','Info'],['applicability','Потеря применимости'],['manual','Отключено вручную'],['policy','Версия отключена'],['other','Другие / исторические']],ui.cause,value=>{ui.cause=value;renderResults();});cause.dataset.invalidationCause='';
  const query=field(filters,'Поиск',ui.query,'search',value=>{ui.query=value;renderResults();});query.dataset.invalidationSearch='';
  button(filters,'Сбросить фильтры',()=>{Object.assign(ui,{element:'',policy:'',version:'',cause:'',query:'',filter:'all',scroll:0});render();});
  const results=el('div',null,'rdg-invalidation-list');results.dataset.invalidationList='';parent.append(results);
  function matches(record){if(ui.element&&!record.nodeIds.includes(ui.element))return false;
   if((ui.policy||ui.version)&&!record.policyVersions.some(([id,v])=>(!ui.policy||id===ui.policy)&&(!ui.version||String(v)===ui.version)))return false;
   if(ui.cause){const reasons=record.kind==='disabled'?[record.reasonCode]:record.causes.flatMap(c=>c.hits.flatMap(h=>h.changedParts.map(x=>x==='direct-scope'?'structure':x)));
    if(ui.cause==='other'?!reasons.length||reasons.some(c=>!['definition','context','structure','selection','result','canon','info','applicability','manual','policy'].includes(c)):reasons.includes(ui.cause)){}else return false;
   }
   const text=[...Object.values(record.participants).map(p=>p.title),record.policyName,record.reasonCode,...record.causes?.flatMap(c=>[c.basis,...c.hits.flatMap(h=>[h.policyName,h.ruleName])])||[]].join(' ').toLocaleLowerCase();return !ui.query||text.includes(ui.query.toLocaleLowerCase());
  }
  function accepts(record,filter){return filter==='history'?!record.active:record.active&&(filter==='all'||record.kind===filter);}
  function renderResults(){const filtered=records.filter(matches);for(const choice of choices){choice.b.replaceChildren(el('span',choice.label),el('span',String(filtered.filter(r=>accepts(r,choice.id)).length),'rdg-dependency-filter-count'));choice.b.setAttribute('aria-pressed',String(ui.filter===choice.id));}
   results.replaceChildren();const shown=filtered.filter(r=>accepts(r,ui.filter));results.append(el('h3',ui.filter==='history'?'История инвалидации':'Актуальные записи'));
   if(!shown.length)results.append(el('p','Нет записей по выбранным фильтрам.','rdg-policy-empty'));
   for(const record of shown)renderInvalidationCard(results,record);
   if(ui.filter==='history'){const cancelled=snapshot.graph.events.filter(e=>e.type==='branch_cancelled'&&(!ui.element||e.nodeIds.includes(ui.element))&&!ui.policy&&!ui.version&&!ui.cause).slice().reverse();if(cancelled.length){const details=el('details');results.append(details);details.append(el('summary','Структурные отмены — отдельная история · '+cancelled.length));for(const event of cancelled)details.append(el('p',invalidationTime(event.recordedAt)+' · '+event.basis));}}
  }
  renderResults();parent.onscroll=()=>{ui.scroll=parent.scrollTop;};queueMicrotask(()=>{if(parent.isConnected)parent.scrollTop=ui.scroll;});
 }
 function renderDependencies(parent){
  const s=screen(),graph=snapshot.graph,byId=new Map([...graph.nodes,...graph.objects,...graph.externalActions].map(n=>[n.id,n]));
  const events=new Map(graph.events.map(e=>[e.id,e]));
  const stale=[...graph.nodes,...graph.externalActions].filter(n=>n.review?.required);
  const activeSet=new Set(snapshot.view?.support?.activeIds||graph.nodes.map(n=>n.id));
  const eventOrder=new Map(graph.events.map((e,i)=>[e.id,i]));
  const hasExactCause=n=>n.review.causeEventIds.some(id=>(events.get(id)?.dependencyImpacts||[]).some(hit=>hit.dependentId===n.id));
  stale.sort((a,b)=>Number(activeSet.has(b.id))-Number(activeSet.has(a.id))||
   Number(hasExactCause(b))-Number(hasExactCause(a))||
   Math.max(-1,...b.review.causeEventIds.map(id=>eventOrder.get(id)??-1))-
   Math.max(-1,...a.review.causeEventIds.map(id=>eventOrder.get(id)??-1))||
   a.title.localeCompare(b.title,'ru')||a.id.localeCompare(b.id));
  const aside=el('aside',null,'rdg-road rdg-dependencies');aside.id='rdg-right-dependencies';
  aside.dataset.processId=s.packageId;aside.style.width=s.panels.roadWidth+'px';
  aside.setAttribute('aria-label','Зависимости, требующие пересмотра');parent.append(aside);
  const head=el('header',null,'rdg-road-head');head.append(el('h3','Зависимости · '+stale.length),
   el('p','Текущие требования повторной проверки процесса «'+graph.title+'». Все рабочие области используют одни состояния.'));
  const actions=el('div',null,'rdg-road-head-actions');head.append(actions);
  button(actions,'Plan / History',()=>sync((v,t)=>{t.panels.roadVisible=true;t.panels.roadTab='timeline';},true));
  button(actions,'Закрыть',()=>sync((v,t)=>t.panels.roadVisible=false,true));aside.append(head);
  const scroll=el('div',null,'rdg-dependency-scroll');aside.append(scroll);
  scroll.append(el('p','Stale означает «проверить актуальность», а не «результат ошибочен». Подтверждение требует проверки действующих входов и точных pins; текущие факты и выбор автоматически не отменяются.','rdg-dependency-summary'));
  if(!stale.length)scroll.append(el('p','Нет объектов с активным флагом review.required. Это не подтверждение выполнения всех обязательств.','rdg-dependency-empty'));
  const list=el('div',null,'rdg-dependency-list');scroll.append(list);
  const inactive=stale.filter(n=>!activeSet.has(n.id));
  const inactiveGroup=el('details',null,'rdg-dependencies-inactive');
  const inactiveList=el('div',null,'rdg-dependency-list');
  if(inactive.length){inactiveGroup.append(el('summary','Неактуальные ветви · '+inactive.length),
   el('p','Эти блоки потеряли действующее структурное основание. Проверка может понадобиться при повторном использовании; подтверждение не активирует ветку.','rdg-dependency-summary'),inactiveList);scroll.append(inactiveGroup);}
  const label={requirement:'R',decision:'D',action:'Act'};
  for(const node of stale){
   const card=el('article',null,'rdg-dependency-card');card.dataset.staleNodeId=node.id;
   (activeSet.has(node.id)?list:inactiveList).append(card);
   card.append(el('span',label[node.kind]||node.kind,'rdg-dependency-kind'),el('small','ТРЕБУЕТ ПРОВЕРКИ'));
   card.append(el('h4',node.title),el('small',node.kind+' · '+node.review.causeEventIds.length+' причин(ы) пересмотра'));
   const causes=[...node.review.causeEventIds].reverse();
   if(!causes.length)card.append(el('p','Причина не записана в текущем Graph; без проверки нельзя автоматически снять флаг.','rdg-dependency-warning'));
   for(const eventId of causes){
    const event=events.get(eventId),cause=el('div',null,'rdg-dependency-cause');cause.dataset.causeEventId=eventId;card.append(cause);
    if(!event){cause.append(el('small','Историческое событие '+eventId+' недоступно в текущем Graph'));continue;}
    cause.append(el('small',(event.recordedAt?.replace('T',' ').slice(0,16)||'')+' · '+event.type));
    cause.append(el('p',event.basis||'Описание причины отсутствует'));
    const hits=(event.dependencyImpacts||[]).filter(row=>row.dependentId===node.id);
    if(hits.length){
     for(const hit of hits){
      const source=byId.get(hit.sourceId),parts=[];
      const meaning={definition:'определение', 'direct-scope':'непосредственный состав',selection:'выбор Decision',
       result:'результат',context:'контекст принятия решения',canon:'теория принятия решения',info:'материалы Info',
       structure:'состав связей',basis:'структурное основание','source-removed':'источник удалён','source-added':'источник добавлен'};
      for(const part of hit.changedParts)parts.push(meaning[part]||part);
      const via=hit.origin==='structural'?'Структурная':hit.origin==='decisionContext'?'Контекст (старая ссылка)':
       hit.origin==='canon'?'Теория принятия решения':'Ручная';
      const title=via+' · '+(hit.preset&&hit.preset!=='L1'?(dependencyPresetNames[hit.preset]||hit.preset):hit.level)+
       ' · '+(source?.title||hit.sourceId)+' · '+parts.join(', ');
      if(source)button(cause,title,()=>focusNode(source.id));else cause.append(el('p',title));
     }
    }else{
     cause.append(el('p','Причина пересмотра сохранена в старом формате без точного правила. Проверьте связанные блоки и History.'));
    }
   }
   const row=el('div',null,'rdg-dependency-actions');card.append(row);
   button(row,'Открыть блок',()=>focusNode(node.id));
   const confirm=button(row,'Подтвердить пересмотр',()=>showForm('command',{nodeId:node.id,command:'review'}));
   confirm.className='rdg-dependency-confirm';confirm.dataset.reviewNodeId=node.id;
  }
  const cancelled=graph.events.filter(e=>e.type==='branch_cancelled').slice(-8).reverse();
  if(cancelled.length){
   const historyBox=el('details',null,'rdg-dependencies-cancelled');
   historyBox.append(el('summary','Последствия структурных отмен · '+cancelled.length));
   historyBox.append(el('p','Исторические отмены отображаются отдельно от stale. Текущие основания пересчитываются по всему Graph.','rdg-dependency-summary'));
   for(const ev of cancelled){const card=el('div',null,'rdg-dependency-cause');
    card.append(el('small',(ev.recordedAt||'').slice(0,16)+' · '+ev.basis));
    for(const id of ev.nodeIds){const n=byId.get(id),isActive=activeSet.has(id);
     if(n)button(card,n.title+' · '+(isActive?'актуален сейчас':'неактуален сейчас'),()=>focusNode(id));}
    historyBox.append(card);
   }scroll.append(historyBox);
  }
  const derived=graph.nodes.filter(n=>!n.review?.required&&snapshot.completion[n.id]?.reviewRequired&&snapshot.completion[n.id]?.previouslyConfirmed);
  if(derived.length)scroll.append(el('p','Отдельно: '+derived.length+' ранее подтверждённых блоков имеют незакрытые обязательства. Это не снимается нажатием «Подтвердить пересмотр» — сначала нужно восстановить условия завершения.','rdg-dependency-warning'));
 }
 function planMomentParts(at){
  if(!at)return {date:'',time:''};if(!at.includes('T'))return {date:at,time:''};
  const d=new Date(at),pad=n=>String(n).padStart(2,'0');return {date:d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()),time:pad(d.getHours())+':'+pad(d.getMinutes())};
 }
 function planMoment(date,time){
  if(!date){if(time)throw Error('Укажите дату для времени.');return '';}
  if(!time)return date;
  const d=new Date(date+'T'+time+':00');if(!Number.isFinite(+d)||planMomentParts(d.toISOString()).date!==date||planMomentParts(d.toISOString()).time!==time)throw Error('Проверьте дату и время в часовом поясе браузера.');
  const offset=-d.getTimezoneOffset(),abs=Math.abs(offset),pad=n=>String(n).padStart(2,'0');return date+'T'+time+':00'+(offset>=0?'+':'-')+pad(Math.floor(abs/60))+':'+pad(abs%60);
 }
 function planMomentLabel(at){if(!at)return 'Только порядок, без даты';return at.includes('T')?new Intl.DateTimeFormat('ru-RU',{dateStyle:'short',timeStyle:'short'}).format(new Date(at)):new Intl.DateTimeFormat('ru-RU',{dateStyle:'long'}).format(new Date(at+'T12:00:00'));}
 function planRoots(parent,roots){
  if(!roots.length){parent.append(el('small','Корневые решения не привязаны','rdg-muted'));return;}
  for(const id of roots){const n=snapshot.graph.nodes.find(n=>n.id===id&&n.kind==='decision');if(!n){parent.append(el('small','Решение отсутствует в текущем Graph'));continue;}
   const row=el('div',null,'rdg-plan-root');row.dataset.planRootId=id;parent.append(row);
   const link=button(row,'D · '+n.title,()=>sync((v,s)=>s.inspector={kind:'entity',id},true));colorize(link,n.kind);
   row.append(el('small',[n.selectionState==='selected'?'Выбрано':n.result.state==='confirmed'?'Не выбрано':'На бумаге',...(n.result.state==='confirmed'?[n.result.truth==='true'?'Выполнено':n.result.truth==='false'?'Опровергнуто':'Результат зафиксирован']:[]),...((snapshot.view.completion?.[id]?.reviewRequired||n.review?.required)?['Требует проверки']:[])].join(' · ')));
   const groups=snapshot.graph.decisionGroups.filter(g=>g.members.some(m=>m.decisionId===id));
   if(!groups.length)row.append(el('small','Без группы решений','rdg-muted'));
   for(const g of groups){const title=(g.title||snapshot.graph.nodes.find(n=>n.id===g.parentId)?.title||'Группа')+' · '+(g.mutuallyExclusive?'Взаимоисключающие':'Совместный выбор')+(g.selectionRequired?' · Выбрать ≥1':'');
    const chip=button(row,title,()=>showDecisionGroupDetails([g.id]));chip.className='rdg-plan-group';chip.dataset.planGroupId=g.id;chip.style.borderColor=decisionGroupColor(g.id);chip.style.color=decisionGroupColor(g.id);
   }
  }
 }
 function renderRoad(parent,retained=null){const s=screen(),ui=roadUiFor(s),road=retained||el('aside',null,'rdg-road');if(retained)road.replaceChildren();
  road.style.width=s.panels.roadWidth+'px';road.setAttribute('aria-label','Plan и History');road.dataset.processId=s.packageId;
  road.dataset.detail=ui.details?'full':'compact';
  for(const [key] of roadRanges)road.style.setProperty('--road-'+key.replace(/[A-Z]/g,c=>'-'+c.toLowerCase()),ui.settings[key]+'px');
  if(!retained)parent.append(road);
  const head=el('header',null,'rdg-road-head');head.append(el('h3','Временная дорога'),el('p','Plan и History процесса «'+snapshot.graph.title+'»'));
  const actions=el('div',null,'rdg-road-head-actions');head.append(actions);
  button(actions,'К границе',()=>road.querySelector('.rdg-now').scrollIntoView({block:'center'}));
  button(actions,ui.details?'Свернуть всё':'Раскрыть всё',()=>{ui.details=!ui.details;render();}).dataset.roadDetails='';
  const boundary=button(actions,'Границы показа',()=>{ui.open=ui.open==='windows'?null:'windows';render();});
  boundary.dataset.roadWindowButton='';boundary.setAttribute('aria-expanded',String(ui.open==='windows'));
  const settings=button(actions,'⚙',()=>{ui.open=ui.open==='settings'?null:'settings';render();});
  settings.dataset.roadSettingsButton='';settings.setAttribute('aria-label','Настройки временной дороги');
  settings.setAttribute('aria-expanded',String(ui.open==='settings'));
  button(actions,'+ Размещение',()=>showForm('place'));
  button(actions,'+ Метадействие',()=>showForm('planAction'));
  road.append(head);renderRoadPopup(road,s,ui);
  const scroll=el('div',null,'rdg-road-scroll');road.append(scroll);const byId=new Map([...snapshot.graph.nodes,...snapshot.graph.externalActions,...snapshot.graph.objects].map(n=>[n.id,n]));
  function side(parent,ids,label,position,record=null){
   const unique=[...new Set((ids||[]).filter(Boolean))];if(!unique.length)return;
   const container=el('div',null,'rdg-road-side rdg-road-side-'+(position===0?'left':'right'));
   container.dataset.roadSide=position===0?'left':'right';
   container.append(el('span',label+' · '+unique.length));
   parent.append(container);
   let displayed=0;const chunk=ui.details?unique.length:12;
   const addMore=()=>{
    for(const id of unique.slice(displayed,displayed+chunk)){
     const n=record?.historyView?.subjects?.[id]||(!record?.inherited?byId.get(id):null);
     if(!n){const missing=el('span','Исторический блок '+id+' · сведения не сохранены','rdg-road-missing');missing.title=id;container.append(missing);continue;}
     const title=(kindCode[n.kind]||'?')+' · '+n.title;
     const b=record?.inherited||!byId.has(id)?el('span',title,'rdg-road-source'):button(container,title,()=>focusNode(id));
     if(record?.inherited||!byId.has(id))container.append(b);
     colorize(b,n.kind);b.title=(kindLabel[n.kind]||n.kind)+' · '+n.title+' · '+id;
     if(!record?.inherited&&byId.has(id))b.dataset.roadNodeId=id;

    }
    displayed=Math.min(displayed+chunk,unique.length);
    if(displayed<unique.length){
     const more=button(container,'Показать ещё '+Math.min(chunk,unique.length-displayed)+' из '+(unique.length-displayed),()=>{
      more.remove();addMore();
     });more.className='rdg-road-show-more';more.dataset.roadShowMore='';
    }
   };
   addMore();
   return container;
  }
  function entry(parent,node,caption,headline=null){const row=el('article',null,'rdg-road-row'),card=el('div',null,'rdg-road-card');colorize(card,node?.kind);card.append(el('small',caption));if(headline)card.append(el('b',headline,'rdg-road-headline'));else if(node){if(byId.has(node.id))button(card,node.title,()=>focusNode(node.id));else card.append(el('b',node.title));}else card.append(el('b','Сохранённый факт'));row.append(card);parent.append(row);return {row,card};}
  function historyBlockList(parent,ids,label,recorded={},inherited=false){const found=ids.map(id=>recorded[id]||(!inherited?byId.get(id):null)||{id,kind:'requirement',title:'Записанный ID · '+id});if(!found.length)return;const list=el('div',null,'rdg-road-change-list');list.append(el('small',label));for(const node of found){const b=!inherited&&byId.has(node.id)?button(list,node.title,()=>focusNode(node.id)):el('span',node.title);if(inherited||!byId.has(node.id))list.append(b);colorize(b,node.kind);b.title=(kindLabel[node.kind]||node.kind)+' · '+node.id;}parent.append(list);}
  const facts=el('section',null,'rdg-road-part');facts.dataset.road='history';scroll.append(facts);const historyHead=el('div',null,'rdg-road-section');historyHead.append(el('b','History'),el('small','Записанные события, не равнозначные выполнению'));facts.append(historyHead);
  const historyMode=s.spec.historyMode||'important';select(historyHead,'События истории',[['important','Важное'],['meaningful','Без технических'],['technical','Технические'],['all','Всё']],historyMode,v=>run(()=>changeView({historyMode:v}))).dataset.historyMode='';
  const eventNames={created:'Создан блок',edited:'Изменён блок',linked:'Добавлена связь',unlinked:'Связь удалена',group_changed:'Изменена группа решений',work_graph_changed:'Изменена рабочая область',root_cause_changed:'Изменено основание',decision_selected:'Решение выбрано',decision_unselected:'Решение отменено',branch_cancelled:'Ветвь автоматически деактивирована',action_executed:'Действие выполнено',requirement_achieved:'Требование достигнуто',decision_completed:'Решение завершено',reopened:'Результат открыт для пересмотра',removed:'Блок удалён',lock_set:'Установлено ограничение',lock_removed:'Снято ограничение',lens_application_recorded:'Записано применение линзы',completed:'Результат зафиксирован',reviewed:'Проверена актуальность',lens_applied:'Применение линзы',policy_changed:'Изменена политика зависимостей',binding_changed:'Изменено применение зависимости'};
  const eventCategories={created:'ИЗМЕНЕНИЕ GRAPH',edited:'ИЗМЕНЕНИЕ GRAPH',linked:'ИЗМЕНЕНИЕ GRAPH',unlinked:'ИЗМЕНЕНИЕ GRAPH',removed:'ИЗМЕНЕНИЕ GRAPH',group_changed:'ОРГАНИЗАЦИЯ',work_graph_changed:'ОРГАНИЗАЦИЯ',root_cause_changed:'ОСНОВАНИЕ',decision_selected:'ВЫБОР',decision_unselected:'ВЫБОР',branch_cancelled:'СОСТОЯНИЕ',action_executed:'РЕЗУЛЬТАТ',requirement_achieved:'РЕЗУЛЬТАТ',decision_completed:'РЕЗУЛЬТАТ',reopened:'ПЕРЕСМОТР',lock_set:'УПРАВЛЕНИЕ',lock_removed:'УПРАВЛЕНИЕ',lens_application_recorded:'ПРИМЕНЕНИЕ',completed:'РЕЗУЛЬТАТ',reviewed:'ПЕРЕСМОТР',lens_applied:'ПРИМЕНЕНИЕ'};
  const relationNames={FINDING_RESPONSE:'Решение разрешить файндинг',FINDING_PROPOSAL:'Предложенный способ разрешения',DERIVES:'Требование вводит подцель',DRIVES:'Цель задаёт решение',INTRODUCES:'Решение вводит требование',
   REQUIRES_ACTION:'Родитель требует действие',CANON_FOR:'Теория принятия решения для блока',CONTEXT_FOR:'Контекст процесса для блока',
   INFO_FOR:'Информация для блока',EVIDENCE_FOR:'Свидетельство для блока',DEPENDS_ON:'Зависимость от блока'};
  const affectedRoles={created:'Блоки в событии создания',edited:'Блоки, учтённые при изменении',
   group_changed:'Участники изменения группы',root_cause_changed:'Блоки, связанные с основанием',
   decision_selected:'Участники выбора',decision_unselected:'Участники отмены выбора',
   branch_cancelled:'Деактивированные блоки',action_executed:'Блоки события выполнения',
   requirement_achieved:'Блоки подтверждения цели',decision_completed:'Блоки завершения решения',
   reopened:'Блоки повторного открытия',removed:'Блоки события удаления',
   lock_set:'Блоки с ограничениями',lock_removed:'Блоки снятия ограничений',
   lens_application_recorded:'Участники применения линзы',completed:'Блоки результата',
   reviewed:'Проверенные блоки',lens_applied:'Участники применения линзы'};
  const edgesById=new Map(snapshot.graph.edges.map(e=>[e.id,e]));
  // A 'created' event records every entity affected by the operation, not
  // just the entity that was added. Infer the added entity only from owner
  // history/operation IDs when the origin is unambiguous; never claim that all
  // event.nodeIds were created. Transactions can append their linked/executed
  // companion events before the actual 'created' event.
  const seenBeforeTransaction=new Map(),seenInPast=new Set([snapshot.graph.rootRequirementId]);
  for(const past of snapshot.graph.events||[]){
   const tx=past.transactionId||past.id;
   if(!seenBeforeTransaction.has(tx))seenBeforeTransaction.set(tx,new Set(seenInPast));
   for(const id of past.nodeIds||[])seenInPast.add(id);
  }
  const ownerEventIds=new Set((snapshot.graph.events||[]).map(e=>e.id));
  function createdEntityId(event){
   if(!ownerEventIds.has(event.id))return null; // inherited event: no local creation proof
   const all=[...new Set(event.nodeIds||[])],operation=byId.get(event.operationActionId);
   if(operation?.actionType==='discover_decision'){
    const target=(operation.targetIds||[]).filter(id=>all.includes(id)&&byId.get(id)?.kind==='decision');
    if(target.length===1)return target[0];
   }
   const before=seenBeforeTransaction.get(event.transactionId||event.id);
   if(!before)return null;
   const candidates=all.filter(id=>id!==event.operationActionId&&id!==snapshot.graph.rootRequirementId&&
    byId.has(id)&&!before.has(id));
   if(candidates.length!==1)return null;
   const result=candidates[0];
   // Single, unambiguous newly mentioned entity. Even when its initial
   // relation was later deleted, do not infer lost endpoint roles.
   return result;
  }
  const createdNames={requirement:'Создано требование',decision:'Создано решение',action:'Создано действие',
   canon:'Создана теория принятия решения',context:'Создан контекст процесса',info:'Создана информация',evidence:'Создано свидетельство'};
  let visibleEvents=0;const historyWindow=roadWindow(s,'historyWindow'),planWindow=roadWindow(s,'planWindow');
  for(const record of history?.events||[]){const event=record.event,day=event.recordedAt?.slice(0,10),change=event.workGraphChange;
   if(day&&(day<historyWindow.from||day>historyWindow.to))continue;
   const hv=record.historyView||{level:'unknown',targetIds:[],subjects:{},createdIds:[],activatedRequirementIds:[],deactivatedRequirementIds:[],edits:[]};
   if(!(historyMode==='all'||historyMode==='important'&&hv.level==='important'||historyMode==='technical'&&hv.level==='technical'||historyMode==='meaningful'&&hv.level!=='technical'))continue;
   const activityOnly=historyMode==='important'&&hv.operationLevel!=='important'&&(hv.activatedRequirementIds.length||hv.deactivatedRequirementIds.length);
   const historicalNode=id=>hv.subjects[id]||(!record.inherited?byId.get(id):null);
   visibleEvents++;
   const historySide=(parent,ids,label,position)=>side(parent,ids,label,position,record);
   const ids=[...new Set(hv.targetIds?.length?hv.targetIds:record.inherited?event.nodeIds||[]:record.displayTargetIds||event.nodeIds||[])],linkEvent=['linked','unlinked'].includes(event.type);
   const born=(hv.createdIds||[]).filter(id=>!hv.subjects[id]?.lowLevel);const createdId=event.type==='created'?(born.length===1?born[0]:createdEntityId(event)):null;
   const createdNode=createdId?historicalNode(createdId):null;
   const relationIds=[...new Set(event.relationIds||[])];
   const recordedRelations=new Map((hv.relations||[]).map(r=>[r.id,r]));const relations=relationIds.map(id=>recordedRelations.get(id)||(!record.inherited?edgesById.get(id):null)).filter(Boolean);
   const missingRelations=relationIds.filter(id=>!recordedRelations.has(id)&&(record.inherited||!edgesById.has(id)));
   const workGraphHeadline=change?(change.action==='created'?'Создана рабочая область «'+change.title+'»':'Изменена рабочая область «'+change.title+'»'):
    event.type==='work_graph_changed'?'Рабочая область изменена · старая запись без детализации состава':null;
   const mainKind={decision_selected:'decision',decision_unselected:'decision',decision_completed:'decision',
    requirement_achieved:'requirement',action_executed:'action'}[event.type];
   const candidates=mainKind?ids.filter(id=>historicalNode(id)?.kind===mainKind):[];
   const mainId=ids.length===1?ids[0]:candidates.length===1?candidates[0]:null;
   const node=workGraphHeadline||linkEvent||event.type==='created'&&!createdNode?null:createdNode||historicalNode(mainId);
   const eventLabel=hv.label|| (change?(change.action==='created'?'Создание рабочей области':'Изменение рабочей области'):
    event.type==='created'&&createdNode?(createdNames[createdNode.kind]||'Создан блок'):(eventNames[event.type]||event.type));
   const linkHeadline=linkEvent?(relations.length===1?(relationNames[relations[0].type]||relations[0].type):
     relations.length>1?'Связи · '+relations.length:eventLabel):null;
   const caption=eventLabel+' · '+(event.recordedAt?.slice(0,16).replace('T',' ')||'');
   const headline=activityOnly?'Изменена актуальность требований':workGraphHeadline||linkHeadline||(event.type==='created'&&!createdNode?'Создание · состав события не определён':!node?eventLabel:null);
   const {row,card}=entry(facts,activityOnly?null:node,caption,headline||(record.inherited&&node?node.title:null));row.dataset.historyLevel=hv.level;row.dataset.eventId=event.id;row.dataset.eventType=event.type;
   if(createdId)row.dataset.createdId=createdId;
   const category=el('span',eventCategories[event.type]||'СОБЫТИЕ','rdg-road-category');category.dataset.eventCategory=eventCategories[event.type]||'other';card.prepend(category);
   if(event.basis&&!activityOnly)card.append(el('p',event.basis));if(hv.decisionOutcome){const d=hv.subjects[hv.decisionOutcome.decisionId]||(!record.inherited?byId.get(hv.decisionOutcome.decisionId):null);card.append(el('p','Результат рассмотрения: '+(d?.title||hv.decisionOutcome.decisionId)+' · '+(hv.decisionOutcome.decisionOutcome==='selected'?'выбрано':'не выбрано')));}
   historyBlockList(card,hv.activatedRequirementIds,'Стали актуальны требования',hv.subjects,record.inherited);historyBlockList(card,hv.deactivatedRequirementIds,'Потеряли актуальность требования',hv.subjects,record.inherited);
   const edits=hv.edits||[],labels={title:'Название',description:'Описание',value:'Содержание',source:'Источник',scope:'Область',version:'Версия'};
   for(const edit of edits.filter(e=>labels[e.field]).slice(0,3)){const text=v=>typeof v==='string'?v:JSON.stringify(v);const a=edit.beforePresent?text(edit.before):'не задано',b=edit.afterPresent?text(edit.after):'не задано';card.append(el('p',labels[edit.field]+': '+a.slice(0,230)+' → '+b.slice(0,230),'rdg-road-event-hint'));}
   if(activityOnly){if(event.basis){const why=el('details');why.append(el('summary','Основание операции'),el('p',event.basis));card.append(why);}}else if(change){
    const before=change.before,after=change.after,oldMembers=new Set(before?.memberIds||[]),newMembers=new Set(after.memberIds);
    const added=after.memberIds.filter(id=>!oldMembers.has(id)),removed=(before?.memberIds||[]).filter(id=>!newMembers.has(id));
    const oldRoots=new Set(before?.rootIds||[]),newRoots=new Set(after.rootIds||[]),addedRoots=after.rootIds.filter(id=>!oldRoots.has(id)),removedRoots=(before?.rootIds||[]).filter(id=>!newRoots.has(id));
    historySide(row,added,'Добавлены в область',0);
    historySide(row,removed,'Исключены из области',1);
    const details=el('details');details.open=ui.details;details.append(el('summary','Состав рабочей области'));
    if(addedRoots.length)historyBlockList(details,addedRoots,'Добавлены начальные требования');
    if(removedRoots.length)historyBlockList(details,removedRoots,'Убраны начальные требования');
    if(!added.length&&!removed.length&&!addedRoots.length&&!removedRoots.length)details.append(el('p','Состав блоков и начальные требования не изменились.'));
    if(before&&before.title!==after.title)details.append(el('p','Название: «'+before.title+'» → «'+after.title+'»'));
    if(before&&before.colorKey!==after.colorKey)details.append(el('p','Цвет: '+(workAreaColorNames[before.colorKey]||'по умолчанию')+' → '+(workAreaColorNames[after.colorKey]||'по умолчанию')));
    card.append(details);
   }else if(event.type==='work_graph_changed'){
    historySide(row,ids,'Блоки, упомянутые в старой записи (точный состав изменений неизвестен)',0);
   }else if(event.type==='created'){
    if(createdNode){
     const isStructural=type=>['DERIVES','DRIVES','INTRODUCES','REQUIRES_ACTION'].includes(type);
     card.append(el('p',(kindCode[createdNode.kind]||'?')+' · '+(kindLabel[createdNode.kind]||createdNode.kind)+' · '+createdId,'rdg-road-event-hint'));
     const parentRelations=relations.filter(e=>e.from===createdId||e.to===createdId);
     const adjacentIds=[...new Set(parentRelations.map(e=>e.from===createdId?e.to:e.from))];
     historySide(row,adjacentIds,parentRelations.every(e=>isStructural(e.type))?'Родители при создании':'Объекты привязки при создании',0);
     const extraIds=ids.filter(id=>id!==createdId&&id!==event.operationActionId&&!adjacentIds.includes(id));
     historySide(row,extraIds,'Другие блоки, учтённые при операции',1);
     if(relations.length){
      const relationSummary=el('div',null,'rdg-road-event-relation');
      relationSummary.append(el('strong','Созданы связи · '+relations.length));
      for(const rel of relations){
       relationSummary.append(el('small',(relationNames[rel.type]||rel.type)+(['FINDING_RESPONSE','FINDING_PROPOSAL'].includes(rel.type)?'':' · '+rel.type)));
      }
      card.append(relationSummary);
     }
     if(missingRelations.length)card.append(el('p','Часть связей создания отсутствует в текущем Graph ('+missingRelations.length+'). Исторические концы доступны в версии события.','rdg-road-event-hint'));
     if(event.operationActionId){
      const operation=!record.inherited?byId.get(event.operationActionId):null,technical=el('details',null,'rdg-road-technical');
      technical.append(el('summary','Служебная запись об обнаружении'));
      if(operation){
       const link=button(technical,(kindCode[operation.kind]||'Act')+' · '+operation.title,()=>focusNode(operation.id));
       link.title='Низкоуровневая операция · '+operation.id;
      }else technical.append(el('p','Служебная запись '+event.operationActionId+' · подробности в версии события.'));
      card.append(technical);
     }
    }else{
     historySide(row,ids,'Участники записи (созданный объект не определяется однозначно)',0);
     card.append(el('p','Историческая запись не указывает однозначно, какой блок был создан. Откройте версию события для точной проверки.','rdg-road-event-hint'));
    }
   }else if(linkEvent){
    if(relations.length){
     historySide(row,relations.map(e=>e.from),'Откуда · источник связи',0);
     historySide(row,relations.map(e=>e.to),'Куда · получатель связи',1);
     for(const rel of relations){
      const pair=el('div',null,'rdg-road-event-relation');pair.dataset.relationId=rel.id;
      pair.append(el('strong',(relationNames[rel.type]||'Связь')+(['FINDING_RESPONSE','FINDING_PROPOSAL'].includes(rel.type)?'':' · '+rel.type)));
      const source=historicalNode(rel.from),target=historicalNode(rel.to);
      pair.append(el('small',(source?.title||rel.from)+' → '+(target?.title||rel.to)));card.append(pair);
     }
    }
    if(missingRelations.length){
     card.append(el('p','Связи из старой записи отсутствуют в текущем Graph ('+missingRelations.length+'). Для точных концов откройте версию события.','rdg-road-event-hint'));
     if(!relations.length)historySide(row,ids,'Участники записи (их роли не сохранились)',0);
    }
    if(!relationIds.length)historySide(row,ids,'Участники записи (тип и направление связи не сохранены)',0);
   }else if(ids.length>1){
    const otherIds=ids.filter(id=>id!==mainId);
    historySide(row,otherIds,mainId?'Другие участники события':affectedRoles[event.type]||'Участники исторической записи',0);
    if(['created','edited','removed'].includes(event.type))card.append(el('p',
     'Перечислены участники записи; не каждый из них обязательно был изменён непосредственно.','rdg-road-event-hint'));
   }   if(Array.isArray(event.placementIds)){const indicator=el('span',ui.badgeMode==='label'?(event.placementIds.length?'Есть связь с Plan':'Без размещения'):'',
     ui.badgeMode==='label'?'rdg-road-label '+(event.placementIds.length?'planned':'unplanned'):
       'rdg-road-indicator '+(event.placementIds.length?'planned':'unplanned'));
    indicator.title=event.placementIds.length?'Есть связь с Plan':'Событие без размещения';card.prepend(indicator);}
   const details=el('details');details.open=ui.details;details.append(el('summary','Сведения о факте'));if(hv.reason==='cosmetic-flag-not-recorded')details.append(el('p','В прежней записи не сохранён признак семантического переименования. Она не скрывается как техническая.'));if(record.inherited)details.append(el('p','Наследованная запись исходного процесса.'));if(edits.length)details.append(el('pre',JSON.stringify(edits,null,2)));if(event.placementIds?.length)details.append(el('p','Размещений при событии: '+event.placementIds.length));button(details,'Версия события',async()=>{const source=await call({method:'source_snapshot',packageId:screen().packageId,pin:record.source});form='snapshot';packageDetail={...source,planAtEvent:history.planVersions.find(v=>v.sha256===record.planPin?.sha256)?.plan||null};render();});card.append(details);
  }
  if(!visibleEvents)facts.append(el('p','В выбранном периоде и режиме истории нет событий.','rdg-explorer-note'));
  const now=el('div',null,'rdg-now');now.append(el('i'),el('b','Сейчас'),el('span','History / Plan'));scroll.append(now);
  const plan=el('section',null,'rdg-road-part');plan.dataset.road='plan';scroll.append(plan);const planHead=el('div',null,'rdg-road-section');planHead.append(el('b','Plan'),el('small','Порядок и необязательное время'));plan.append(planHead);
  if(!snapshot.plan){const empty=el('div',null,'rdg-card');empty.append(el('p','План процесса ещё не создан.','rdg-muted'));button(empty,'Добавить план во времени',async()=>prepare(await schema('plan_create')));plan.append(empty);}
  else{
   const rows=new Map(snapshot.planView.placements.map(r=>[r.step.id,r]));let shown=0;
   for(const item of snapshot.planView.road||[]){
    if(item.type==='fork'||item.type==='join'){
     const fork=snapshot.planView.forks.find(f=>f.id===item.forkId),end=item.type==='join';
     const {row,card}=entry(plan,null,end?'Конец ветвления':'Начало ветвления',end?fork.end.title:fork.title);row.dataset[end?'forkEndId':'forkId']=fork.id;
     card.style.setProperty('--rdg-node-fill','#29263f');card.style.setProperty('--rdg-node-line','#9d8ad6');card.append(el('small',planMomentLabel(end?fork.end.at:fork.startAt),'rdg-plan-moment'));
     if(end)card.append(el('p','Дальше — общая последовательность для всех продолжений.'));
     else{
      card.append(el('small','Просмотр продолжения не принимает решение.','rdg-muted'));
      select(card,'Показать продолжение',fork.cases.map(c=>[c.id,c.title]),fork.shownCaseId,id=>run(()=>changeView({shownCases:{...(screen().spec.shownCases||{}),[fork.id]:id}})));
      planRoots(card,fork.cases.find(c=>c.id===fork.shownCaseId).decisionIds);
      const others=el('details');others.append(el('summary','Другие корни и их группы'));for(const c of fork.cases.filter(c=>c.id!==fork.shownCaseId)){others.append(el('b',c.title));planRoots(others,c.decisionIds);}card.append(others);
     }
     const details=el('details');details.append(el('summary','Настроить'));button(details,'Изменить ветвление',()=>showForm('fork',{forkId:fork.id}));card.append(details);continue;
    }
    const placement=rows.get(item.stepId);if(!placement||!s.spec.showLowLevel&&placement.node?.lowLevel)continue;
    const days=(placement.timeConstraints||[]).map(v=>String(v.at||'').slice(0,10)).filter(validRoadDay).sort();
    if(days.length&&(days.at(-1)<planWindow.from||days[0]>planWindow.to))continue;
    shown++;const node=placement.node||byId.get(placement.step.ref.nodeId),{row,card}=entry(plan,node,(placement.step.state==='possible'?'Возможное размещение · ':'Размещение · ')+(kindLabel[node?.kind]||'Блок')+' · '+(placement.timeConstraints.length?placement.timeConstraints.map(r=>(r.type==='deadline'?'До ':'С ')+r.at).join(' · '):'Только порядок, без даты'),node?null:placement.step.title+' · элемент недоступен');row.dataset.placementId=placement.step.id;
    const sourceIds=snapshot.graph.edges.filter(e=>e.to===node?.id&&['INTRODUCES','DERIVES','DRIVES','REQUIRES_ACTION'].includes(e.type)).map(e=>e.from);side(row,[...new Set(sourceIds)],'Происхождение',0);side(row,node?.targetIds||[],'Контекст Action',1);
    const badge=el('span',ui.badgeMode==='label'?'Есть связь с Plan':'',ui.badgeMode==='label'?'rdg-road-label planned':'rdg-road-indicator planned');
    badge.title='Есть связь с Plan';card.prepend(badge);
    const details=el('details');details.open=ui.details;details.append(el('summary','Размещение'));button(details,'Изменить размещение',()=>showForm('place',{nodeId:placement.step.ref.nodeId,stepId:placement.step.id}));button(details,'Убрать размещение',async()=>{const request=await schema('unplace');Object.assign(request,{stepId:placement.step.id,note:'Явно убрать размещение из Plan'});await prepare(request);});card.append(details);
   }
   if(!shown)plan.append(el('p','В выбранном периоде и продолжении нет размещений.','rdg-explorer-note'));button(plan,'Проверить размещение',()=>showForm('place'));
  }
  scroll.scrollTop=ui.scroll??s.panels.planScroll;let timer;scroll.onscroll=()=>{
   ui.scroll=scroll.scrollTop;clearTimeout(timer);
   if(screen()?.panels.planScroll!==scroll.scrollTop)timer=setTimeout(()=>void sync((v,s)=>s.panels.planScroll=scroll.scrollTop).catch(()=>{}),120);
  };
 }
 function modal(parent,title){const shade=el('div',null,'rdg-modal-shade'),body=el('section',null,'rdg-modal');body.setAttribute('role','dialog');body.setAttribute('aria-label',title);shade.append(body);parent.append(shade);const head=el('div',null,'rdg-row');body.append(head);head.append(el('h2',title));button(head,'Закрыть',async()=>{form=null;calendar=null;await sync((v,s)=>{const d=s?.draft||v.explorer.drafts['new-process'];if(d)d.open=false;});render();});return body;}
 function renderPreview(parent){const body=modal(parent,pending.uncertain?'Исход записи требует проверки':'Предварительная проверка');body.append(el('p','Операция: '+pending.request.op));const details=el('details');details.open=true;details.append(el('summary','Последствия'),el('pre',JSON.stringify(pending.preview.effects,null,2)));body.append(details);
  button(body,pending.uncertain?'Повторить тот же запрос':'Сохранить',commit);button(body,'Прочитать receipt',async()=>{const receipt=await call({method:'receipt',packageId:pending.request.targetPackageId||pending.preview.effects?.createdPackageId||snapshot?.package.packageId,transactionId:pending.request.transactionId});body.append(el('pre',JSON.stringify(receipt,null,2)));});button(body,'Отменить подготовку',()=>{pending=null;render();},pending.uncertain);
 }

 function newDefinition(){const lens=catalog.packages.find(r=>r.role==='lens'&&r.coreModel==='rdg-decision-v1');return {id:uid(),revision:1,key:'custom-'+uid().slice(0,8),title:'Новый пакет',supplied:false,rules:[{id:uid(),nodeKinds:['requirement','decision','action'],scope:'all',state:'any',lensRefs:lens?[{packageId:lens.packageId,identitySpace:lens.identitySpace,lensKey:lens.lensKey}]:[]}]};}
 function formFields(body){const values=()=>draftValue().form||{};
  return {values,input:(label,key,value='',type='text')=>{if(values()[key]===undefined)setDraft(key,value);return field(body,label,values()[key]??value,type,v=>setDraft(key,v));},
   pick:(label,key,items,value)=>{const chosen=values()[key]??(items.some(i=>i[0]===value)?value:items[0]?.[0]);if(values()[key]===undefined)setDraft(key,chosen);return select(body,label,items,chosen,v=>setDraft(key,v));}};
 }
 async function requestCore(command,nodeId,note,data=null){const work=['working','copy'].includes(snapshot.package.role);const req=await schema(work?'core':'paper_edit',nodeId,{command});req.note=note;if(data)req.data=data;return req;}
 async function updateWorkAreaColor(packageId,workGraphId,colorKey){
  if(pending)throw Error('Завершите предварительную проверку.');
  if(screen()?.packageId!==packageId)await navigate(packageId,{kind:'graph'});
  const current=snapshot.graph.workGraphs.find(w=>w.id===workGraphId);if(!current)throw Error('Рабочая область больше не существует.');
  if(workAreaColorKey(current)===colorKey)return;
  const noteText='Назначен цвет рабочей области: '+(workAreaColorNames[colorKey]||colorKey);
  const request=await requestCore('work_graph',current.rootIds[0]||snapshot.graph.rootRequirementId,noteText,
   {workGraph:{...clone(current),colorKey}});
  await prepare(request);
 }
 function renderForm(parent){const names={planAction:'Планировочное метадействие',question:'Вопрос',questionAnswer:'Ответ на вопрос',questionAssess:'Достаточность ответа',questionMigrate:'Перенос прежних вопросов',questionRequest:'Подготовка обращения',actionEstimates:'Оценки исполнения Action',contextRecord:'Перевести запись в контекст',finding:'Файндинг',findingQuestions:'Вопросы решения',contextGroup:'Группа контекстов',contextMove:'Переместить контекст',contextEntry:'Роль в контексте решения',findingTransfer:'Перенести файндинг',requirementDecision:'Обязательность requirement',findingDisposition:'Итог рассмотрения файндинга',policyEditor:'Редактор политики',policyBinding:'Применение политики',dependencyRule:'Настройка зависимости',decisionContext:'Контекст принятия решения',add:'Добавить блок',rename:'Переименовать блок',command:'Действие',place:'Разместить существующий блок',fork:'Ветвления Plan',windows:'Границы показа',workGraph:'Рабочая область',group:'Группа решений',attachments:'Пакеты линз процесса',capture:'Сохранить как готовый граф',insert:'Вставить шаблон',create:'Создать процесс',snapshot:'Сохранённая версия',relation:'Связь'};
  const body=modal(parent,form==='add'&&draftValue().form?.processContextBank?'Новый контекст процесса':names[form]||form),{values:F,input,pick}=formFields(body),entities=snapshot?[...snapshot.graph.nodes,...snapshot.graph.objects,...snapshot.graph.externalActions]:[];
  const data=F(),focusId=data.nodeId||data.parentId||(screen()?.spec.kind==='focus'?screen().spec.id:snapshot?.graph.rootRequirementId);
  if(draftStale()){body.append(el('p','Данные процесса изменились. Черновик сохранён; проверьте актуальные значения.','rdg-error'));button(body,'Обновить основание после проверки',async()=>{await sync((v,s)=>{s.draft.basePackageRevision=snapshot.package.revision;s.draft.baseGraphRevision=snapshot.graph.revision;});render();});}
  if(form==='planAction'){
   const old=snapshot.graph.externalActions.find(a=>a.id===data.nodeId);
   input('Название','title',old?.title||'');input('Описание','description',old?.description||'','textarea');
   input('Условия результата','resultCondition',old?.resultCondition||'','textarea');
   if(F().subjectRefs===undefined)setDraft('subjectRefs',clone(old?.subjectRefs||[]));
   const same=(a,b)=>JSON.stringify([a.packageId,a.identitySpace,a.kind||'entity',a.nodeId||a.workGraphId||''])===JSON.stringify([b.packageId,b.identitySpace,b.kind||'entity',b.nodeId||b.workGraphId||'']);
   const toggle=(ref,yes)=>{const refs=(F().subjectRefs||[]).filter(r=>!same(r,ref));if(yes)refs.push(clone(ref));setDraft('subjectRefs',refs);};
   const subjects=el('details');subjects.open=true;subjects.append(el('summary','Предмет работы'));body.append(subjects);
   for(const n of entities.filter(n=>n.id!==old?.id)){
    const ref=snapshot.references[n.id];field(subjects,(kindCode[n.kind]||n.kind)+' · '+n.title,F().subjectRefs.some(r=>same(r,ref)||questionRefId(r,old)===n.id),'checkbox',yes=>{setDraft('subjectRefs',F().subjectRefs.filter(r=>questionRefId(r,old)!==n.id));toggle(ref,yes);});
   }
   const scopes=[['Весь процесс',snapshot.scopeReferences.process],...snapshot.graph.workGraphs.map(w=>[w.title,snapshot.scopeReferences.workGraphs[w.id]])];
   for(const [title,ref] of scopes)field(subjects,title,F().subjectRefs.some(r=>same(r,ref)),'checkbox',yes=>toggle(ref,yes));
   select(body,'Линза',[['','Выберите линзу'],...catalog.packages.filter(p=>p.role==='lens'&&p.coreModel==='rdg-decision-v1').map(p=>[p.packageId,p.title])],F().subjectLens||'',id=>run(async()=>{setDraft('subjectLens',id);if(id){const row=await call({method:'read',packageId:id});setDraft('subjectLensChoices',[{title:row.graph.title,ref:{...row.scopeReferences.process,kind:'lens'}},...Object.values(row.references).map(ref=>({title:[...row.graph.nodes,...row.graph.objects,...row.graph.externalActions].find(n=>n.id===ref.nodeId).title,ref}))]);}else setDraft('subjectLensChoices',[]);render();}));
   if(F().subjectLensChoices?.length){pick('Элемент линзы','subjectLensChoice',F().subjectLensChoices.map((v,i)=>[String(i),v.title]),'0');button(body,'Добавить линзу / элемент',()=>{toggle(F().subjectLensChoices[Number(F().subjectLensChoice||0)].ref,true);render();});}
   const selected=el('div');body.append(selected);for(const ref of F().subjectRefs){const line=el('div');line.append(el('span',entities.find(n=>questionRefId(ref,old)===n.id)?.title||ref.nodeId||ref.workGraphId||ref.kind));button(line,'Убрать предмет',()=>{toggle(ref,false);render();});selected.append(line);}
   if(!old){
    const plan=snapshot.plan;
    const caseSelect=pick('Часть Plan','caseId',[['','Общая часть'],...(plan?.forks||[]).flatMap(f=>f.cases.map(c=>[c.id,f.title+' / '+c.title]))],'');
    const lane=F().caseId?(plan?.forks||[]).flatMap(f=>f.cases).find(c=>c.id===F().caseId)?.stepIds||[]:plan?.mainStepIds||[];
    pick('После размещения','afterStepId',[['','В начале'],...(plan?.steps||[]).filter(p=>lane.includes(p.id)).map(p=>[p.id,p.title])],lane.at(-1)||'');
    caseSelect.onchange=()=>run(async()=>{setDraft('caseId',caseSelect.value);setDraft('afterStepId','');await flushDraft();render();});
    input('Не раньше','at','','date');input('Дедлайн','deadline','','date');
   }
   input('Основание изменения','note','','textarea');
   button(body,'Проверить метадействие',async()=>{checkDraft();const f=F(),entity={title:f.title,description:f.description||'',resultCondition:f.resultCondition||'',subjectRefs:clone(f.subjectRefs)};
    if(old){await prepare(await requestCore('edit',old.id,f.note,{nodeId:old.id,changes:entity,cosmetic:false}));return;}
    const req=await schema('plan_action');Object.assign(req,{entity:{...req.entity,...entity},placement:{caseId:f.caseId||null,afterStepId:f.afterStepId||null,at:f.at||'',deadline:f.deadline||''},note:f.note});await prepare(req);
   });return;
  }
  if(form==='recommendation'){
   const prior=definitionMeta(data.definitionId),rule=prior?.rules.find(r=>r.id===data.ruleId)||prior?.rules[0],oldRef=rule?.lensRefs[0];
   input('Название рекомендации','recommendationTitle',prior?.title||'Рекомендация');
   const choices=catalog.packages.filter(p=>p.role==='lens'&&p.coreModel==='rdg-decision-v1');
   if(F().lensId===undefined)setDraft('lensId',oldRef?.packageId||'');
   select(body,'Линза',[['','Выберите линзу'],...choices.map(p=>[p.packageId,p.title])],F().lensId,async id=>{setDraft('lensId',id);setDraft('lensStep','');if(id){const row=await call({method:'read',packageId:id});setDraft('lensSteps',[...row.graph.nodes,...row.graph.objects].map(n=>[n.id,n.title]));}render();});
   pick('Часть линзы','lensStep',[['','Вся линза'],...(F().lensSteps||[]),...(oldRef?.nodeId&&!F().lensSteps?[[oldRef.nodeId,'Записанный шаг линзы']]:[])],oldRef?.nodeId||'');
   input('Когда использовать','whenText',rule?.whenText||'','textarea');input('Как использовать','usageText',rule?.usageText||'','textarea');
   pick('Охват','recommendationScope',data.targetKind==='entity'?[['identity','Этот элемент'],['children','Прямые дети'],['descendants','Все потомки']]:[['identity','Выбранный процесс или область']],rule?.scope||'identity');
   input('Основание изменения','note','','textarea');
   button(body,'Проверить рекомендацию',async()=>{checkDraft();const f=F(),meta=choices.find(p=>p.packageId===f.lensId);if(!meta)throw Error('Выберите доступную линзу.');
    const targetKind=data.targetKind||'entity',target=[...entities,{id:snapshot.graph.id,kind:'process'},...snapshot.graph.workGraphs.map(w=>({...w,kind:'workGraph'}))].find(n=>n.id===data.targetId);if(!target)throw Error('Объект рекомендации недоступен.');
    const definition={id:prior?.id||uid(),revision:prior?prior.revision+1:1,key:prior?.key||'authored-'+uid(),title:f.recommendationTitle,supplied:false,authored:true,rules:[{id:rule?.id||uid(),nodeKinds:f.recommendationScope==='identity'?[target.kind]:['requirement','decision','action','context','canon','info','finding','question'],scope:f.recommendationScope,state:'any',anchor:{packageId:snapshot.package.packageId,identitySpace:snapshot.graph.identitySpace,nodeId:data.targetId,kind:targetKind},whenText:f.whenText,usageText:f.usageText,lensRefs:[{packageId:meta.packageId,identitySpace:meta.identitySpace,lensKey:meta.lensKey,...(f.lensStep?{nodeId:f.lensStep}:{})}]}]};
    if(prior)definition.rules=prior.rules.map(r=>r.id===rule.id?definition.rules[0]:clone(r));
    const request={op:'recommendation_edit',transactionId:uid(),expectedRegistryRevision:registry.registryRevision,action:prior?'edit':'create',...(prior?{packageId:prior.id}:{attachTo:{packageId:snapshot.package.packageId,expectedPackageRevision:snapshot.package.revision,expectedGraphRevision:snapshot.graph.revision}}),definition,note:f.note};await prepare(request);
   });return;
  }
  const theoryFields=node=>{
    input('Каноны','canons',theoryCanons(node||{}),'textarea');input('Общее','guidance',node?.guidance||'','textarea');
    if(node?.knownErrors?.length)setDraft('knownErrors',[]);
   };
   if(['question','questionAnswer','questionAssess','questionMigrate','questionRequest'].includes(form)){
   const q=entities.find(n=>n.id===data.nodeId&&n.kind==='question');
   const refsEditor=(key,label,prior=[])=>{
    const box=el('details');box.append(el('summary',label));body.append(box);
    if(F()[key]===undefined)setDraft(key,prior.map(ref=>questionRefId(ref,q)).filter(id=>id&&entities.some(n=>n.id===id)));
    const recorded=prior.filter(r=>r.mode==='historical');
    if(F()[key+'Recorded']===undefined)setDraft(key+'Recorded',clone(recorded));
    for(const ref of recorded)field(box,'Записанная связь с удалённым элементом · '+ref.nodeId,(F()[key+'Recorded']||[]).some(r=>JSON.stringify(r)===JSON.stringify(ref)),'checkbox',yes=>{const rows=F()[key+'Recorded']||[];setDraft(key+'Recorded',yes?[...rows,clone(ref)]:rows.filter(r=>JSON.stringify(r)!==JSON.stringify(ref)));});
    for(const n of entities.filter(n=>n.id!==q?.id&&!n.lowLevel))field(box,(kindLabel[n.kind]||n.kind)+' · '+n.title,(F()[key]||[]).includes(n.id),'checkbox',yes=>{
     const ids=new Set(F()[key]||[]);yes?ids.add(n.id):ids.delete(n.id);setDraft(key,[...ids]);
    });
   };
   const pins=key=>{
    const prior=key==='relatedIds'?q?.relatedRefs:key==='sourceIds'?q?.sourceRefs:null;
    return [...(F()[key]||[]).map(id=>clone(prior?.find(ref=>questionRefId(ref,q)===id)||snapshot.references[id])),...(F()[key+'Recorded']||[]).map(ref=>clone(ref))];
   };
   if(form==='questionRequest'){
    if(!q)throw Error('Вопрос не найден.');
    body.append(el('h3',q.title),el('p','Значение: '+q.impact),el('p','Достаточность: '+q.answerCondition));
    questionReferences(body,q.sourceRefs,'Доступные основания');
    for(const a of q.answers||[])body.append(el('p',({hypothesis:'Гипотеза',observation:'Наблюдение',user_answer:'Ответ пользователя'}[a.kind])+': '+a.text));
    body.append(el('p',questionState(q)+(q.assessment?' · '+q.assessment.basis:'')));
    body.append(el('p','Перед обращением проверьте источники и возможные собственные ответы. Создание вопроса и эта подготовка не отправляют сообщение и не предоставляют разрешения.','rdg-muted'));
    return;
   }
   if(form==='questionMigrate'){
    const old=entities.find(n=>n.id===data.nodeId);
    for(const row of old?.questions||[])body.append(el('p',row.question+' · '+row.impact+' · '+row.closeCondition));
    body.append(el('p','Каждый прежний вопрос получит отдельный ID. Старое содержание останется в истории; дальше редактируется только самостоятельный вопрос.'));
    input('Основание изменения','note','','textarea');
    button(body,'Проверить перенос вопросов',async()=>{checkDraft();await prepare(await requestCore('question_migrate',old.id,F().note,{nodeId:old.id,sourceRef:clone(snapshot.references[old.id])}));});return;
   }
   if(form==='question'){
    input('Название вопроса','title',q?.title||'');input('Описание','description',q?.description||'','textarea');
    input('На что влияет ответ','impact',q?.impact||'','textarea');input('Условие достаточности','answerCondition',q?.answerCondition||'','textarea');
    pick('Блокирование','blockingMode',[['non-blocking','Не блокирует'],['blocking','Блокирует'],['partially-blocking','Частично блокирует']],q?.blocking?.mode||'non-blocking');
    input('Блокируемая часть работы','blockingScope',q?.blocking?.scope||'');
    refsEditor('relatedIds','Относится к',q?.relatedRefs||data.relatedIds?.map(id=>snapshot.references[id])||[]);
    const areas=el('details');areas.dataset.questionAreaPicker='';areas.append(el('summary','Рабочие области вопроса'));body.append(areas);
    if(F().questionAreaIds===undefined)setDraft('questionAreaIds',(q?.relatedRefs||[]).filter(r=>r.kind==='workGraph').map(r=>r.workGraphId));
    for(const area of snapshot.graph.workGraphs){const choice=field(areas,area.title,(F().questionAreaIds||[]).includes(area.id),'checkbox',yes=>{const ids=new Set(F().questionAreaIds||[]);yes?ids.add(area.id):ids.delete(area.id);setDraft('questionAreaIds',[...ids]);});choice.dataset.questionAreaId=area.id;}

    refsEditor('sourceIds','Основания возникновения',q?.sourceRefs||[]);
    input('Документы-источники HTTPS, по одному в строке','documentUris',(q?.sourceRefs||[]).filter(r=>r.kind==='document').map(r=>r.uri).join('\n'),'textarea');
    field(body,'Также относится ко всему процессу',F().wholeProcess??!!q?.relatedRefs?.some(r=>r.kind==='process'),'checkbox',v=>setDraft('wholeProcess',v));
    input('Основание изменения','note','','textarea');
    button(body,'Проверить вопрос',async()=>{checkDraft();const f=F(),sourceRefs=pins('sourceIds');
     sourceRefs.push(...(q?.sourceRefs||[]).filter(r=>r.kind&&r.kind!=='document'),...(f.documentUris||'').split('\n').map(uri=>uri.trim()).filter(Boolean).map(uri=>({schemaVersion:1,kind:'document',uri})));
     const relatedRefs=[...pins('relatedIds'),...(q?.relatedRefs||[]).filter(r=>r.kind&&!['process','workGraph'].includes(r.kind)),...(f.questionAreaIds||[]).map(workGraphId=>({schemaVersion:1,kind:'workGraph',workGraphId,packageId:snapshot.package.packageId,identitySpace:snapshot.graph.identitySpace}))];if((f.wholeProcess??q?.relatedRefs?.some(r=>r.kind==='process'))||!relatedRefs.length)relatedRefs.push({schemaVersion:1,kind:'process',packageId:snapshot.package.packageId,identitySpace:snapshot.graph.identitySpace});
     const value={title:f.title,description:f.description||'',impact:f.impact,answerCondition:f.answerCondition,relatedRefs,sourceRefs,
      blocking:{mode:f.blockingMode,...(f.blockingScope?.trim()?{scope:f.blockingScope.trim()}:{})}};
     await prepare(await requestCore(q?'edit':'add',q?.id||snapshot.graph.rootRequirementId,f.note,q?{nodeId:q.id,changes:value,cosmetic:false}:{entity:{id:uid(),kind:'question',...value},location:'graph'}));
    });return;
   }
   if(!q)throw Error('Вопрос не найден.');
   if(form==='questionAnswer'){
    const prior=q.answers.find(a=>a.id===data.answerId),action=data.action||(prior?'edit':'add');
    if(action==='remove')body.append(el('p','Удаляется актуальный ответ; предыдущие версии и оценки останутся в истории.'),el('p',prior?.text));
    else{
     input('Текст ответа','answerText',prior?.text||'','textarea');
     pick('Вид ответа','answerKind',[['hypothesis','Гипотеза'],['observation','Наблюдение'],['user_answer','Ответ пользователя']],prior?.kind||'hypothesis');
     refsEditor('answerSourceIds','Источники ответа',prior?.sourceRefs||[]);
     body.append(el('p','Ответ пользователя подтверждается доверенным пользовательским вводом. ИИ может записать его только как точную цитату ранее введённого пользователем контекста.','rdg-muted'));
    }
    input('Основание изменения','note','','textarea');
    button(body,action==='remove'?'Проверить удаление ответа':'Проверить ответ',async()=>{checkDraft();const payload={nodeId:q.id,action};
     if(prior)Object.assign(payload,{answerId:prior.id,expectedAnswerEventId:prior.eventId});
     if(action!=='remove')Object.assign(payload,{kind:F().answerKind,text:F().answerText,sourceRefs:pins('answerSourceIds')});
     await prepare(await requestCore('question_answer',q.id,F().note,payload));
    });return;
   }
   if(F().answerIds===undefined)setDraft('answerIds',q.assessment?.answerIds.filter(id=>q.answers.some(a=>a.id===id))||[]);
   for(const a of q.answers)field(body,a.text,(F().answerIds||[]).includes(a.id),'checkbox',yes=>{const ids=new Set(F().answerIds||[]);yes?ids.add(a.id):ids.delete(a.id);setDraft('answerIds',[...ids]);});
   field(body,'Ответ достаточен',F().sufficient??q.assessment?.sufficient??false,'checkbox',v=>setDraft('sufficient',v));
   input('Обоснование оценки','assessmentBasis',q.assessment?.basis||'','textarea');input('Основание изменения','note','','textarea');
   button(body,'Проверить достаточность',async()=>{checkDraft();await prepare(await requestCore('question_assess',q.id,F().note,{nodeId:q.id,answerIds:F().answerIds,sufficient:F().sufficient??q.assessment?.sufficient??false,basis:F().assessmentBasis}));});return;
  }
  if(form==='actionEstimates'){
   const action=entities.find(n=>n.id===focusId&&n.kind==='action');if(!action)throw Error('Action не найден.');
   input('Сложность исполнения','estimateComplexity',action.estimates?.complexity||'','textarea');
   input('Минимум времени (секунды)','estimateMin',action.estimates?.time?.minSeconds??'','number');
   input('Максимум времени (секунды)','estimateMax',action.estimates?.time?.maxSeconds??'','number');
   input('Основание оценки','estimateBasis',action.estimates?.basis||'','textarea');
   body.append(el('p','Пустые поля означают неизвестное. Оценки не меняют Plan и не подтверждают выполнение.','rdg-muted'));
   input('Основание изменения','note','','textarea');
   button(body,'Проверить оценки',async()=>{checkDraft();const f=F(),value={};
    if(f.estimateComplexity?.trim())value.complexity=f.estimateComplexity.trim();
    if(String(f.estimateMin)!==''||String(f.estimateMax)!==''){
     if(String(f.estimateMin)===''||String(f.estimateMax)==='')throw Error('Укажите обе границы времени.');
     value.time={minSeconds:Number(f.estimateMin),maxSeconds:Number(f.estimateMax)};
    }
    if(f.estimateBasis?.trim())value.basis=f.estimateBasis.trim();
    await prepare(await requestCore('edit',action.id,f.note,{nodeId:action.id,changes:{estimates:('complexity' in value||'time' in value)?value:null},cosmetic:false}));
   });return;
  }
  if(form==='contextGroup'){
   const group=(snapshot.graph.contextGroups||[]).find(g=>g.id===data.groupId);
   input('Название группы','title',group?.title||'');pick('Родительская группа','parentGroupId',contextChoices().filter(([id])=>id!==data.groupId),group?.parentId||data.parentGroupId||'');input('Основание изменения','note','','textarea');
   button(body,'Проверить группу',async()=>{checkDraft();const f=F();await prepare(await requestCore('context_group',snapshot.graph.rootRequirementId,f.note,{action:'save',id:data.groupId,title:f.title,parentId:f.parentGroupId||null}));});
   if(group){body.append(el('p','Удаление группы перенесёт её содержимое к родителю; факты и их связи сохранятся.','rdg-muted'));
    button(body,'Удалить группу',async()=>{checkDraft();await prepare(await requestCore('context_group',snapshot.graph.rootRequirementId,F().note,{action:'remove',id:group.id}));});}
   return;
  }
  if(form==='contextMove'){
   const fact=entities.find(n=>n.id===focusId&&n.kind==='context');if(!fact)throw Error('Контекст не найден.');
   pick('Группа','contextGroupId',contextChoices(),fact.contextGroupId||'');input('Основание изменения','note','','textarea');
   button(body,'Проверить перенос',async()=>{checkDraft();await prepare(await requestCore('edit',focusId,F().note,{nodeId:focusId,changes:{contextGroupId:F().contextGroupId||null},cosmetic:false}));});return;
  }
  if(form==='contextEntry'){
   const decision=entities.find(n=>n.id===focusId&&n.kind==='decision');if(!decision)throw Error('Ожидался Decision.');const action=data.action||'save';
   if(!data.sourceId)pick('Элемент контекста','sourceId',[['','Выберите элемент'],...entities.filter(n=>n.id!==focusId&&!n.lowLevel).map(n=>[n.id,sourceTitle(n)])],'');
   else body.append(el('p',sourceTitle(entities.find(n=>n.id===data.sourceId))));
   if(action!=='remove')input('Роль элемента','comment',data.comment||decision.contextNotes?.[data.sourceId]||'','textarea');
   else body.append(el('p','Убирается ручное участие. Основания из файндингов сохраняются.'));
   if(data.analysisSourceId)body.append(el('p','Источник анализа: '+entities.find(n=>n.id===data.analysisSourceId)?.title,'rdg-muted'));
   input('Основание изменения','note','','textarea');
   button(body,'Проверить контекст',async()=>{checkDraft();const f=F(),sourceId=data.sourceId||f.sourceId;if(!sourceId)throw Error('Выберите конкретный элемент процесса.');
    const payload={nodeId:focusId,sourceId,action,...(action==='remove'?{}:{comment:f.comment||''})};
    if(data.analysisSourceId)payload.analysisSources=[...(decision.analysisSources||[]),...analysisSources(data.analysisSourceId)];
    await prepare(await requestCore('decision_context',focusId,f.note,payload));});return;
  }
  if(form==='findingTransfer'){
   pick('Decision','subjectId',entities.filter(n=>n.kind==='decision').map(n=>[n.id,n.title]),entities.find(n=>n.id===focusId)?.subjectId||'');
   if(snapshot.graph.edges.some(e=>e.findingId===focusId)){field(body,'Отсоединить прежние resolve/proposal-связи',!!data.detachLegacy,'checkbox',v=>setDraft('detachLegacy',v));body.append(el('p','Сами Decisions сохранятся. Потеря оснований и изменение выбора будут показаны в предварительной проверке.','rdg-muted'));}
   input('Основание изменения','note','','textarea');
   button(body,'Проверить перенос',async()=>{checkDraft();await prepare(await requestCore('finding_transfer',focusId,F().note,{nodeId:focusId,subjectId:F().subjectId,detachLegacy:!!F().detachLegacy}));});return;
  }
  if(form==='requirementDecision'){
   const requirement=entities.find(n=>n.id===focusId);pick('Родительское основание','basisId',entities.filter(n=>n.kind==='requirement'&&n.id!==focusId).map(n=>[n.id,n.title]),snapshot.graph.rootRequirementId===focusId?'':snapshot.graph.rootRequirementId);
   pick('Использовать Decision','existingDecisionId',[['','Создать новое'],...entities.filter(n=>n.kind==='decision').map(n=>[n.id,n.title])],'');
   input('Название решения','title','Считать «'+requirement.title+'» необходимым');input('Описание','description','','textarea');
   pick('Прямое обязательство','replaceEdgeId',[['','Сохранить все существующие связи'],...snapshot.graph.edges.filter(e=>e.type==='DERIVES'&&e.to===focusId).map(e=>[e.id,'Заменить связь от «'+entities.find(n=>n.id===e.from)?.title+'»'])],'');input('Основание изменения','note','','textarea');
   button(body,'Проверить решение',async()=>{checkDraft();const f=F(),prior=entities.find(n=>n.id===f.existingDecisionId),payload={nodeId:focusId,parentId:f.basisId,decisionId:prior?.id||uid(),title:prior?.title||f.title,description:prior?.description||f.description||''};if(f.replaceEdgeId)payload.replaceEdgeId=f.replaceEdgeId;const area=activeArea();if(area)payload.workGraphId=area.id;
    await prepare(await requestCore('requirement_decision',focusId,f.note,payload));});return;
  }

  if(form==='findingQuestions'){
   const current=entities.find(n=>n.id===focusId);renderFindingQuestionsEditor(body,current,F);
   input('Помощь пользователя','userAssistance',current?.userAssistance||'','textarea');input('Основание изменения','note','','textarea');
   button(body,'Проверить вопросы',async()=>{checkDraft();const f=F();await prepare(await requestCore('edit',current.id,f.note,{nodeId:current.id,changes:{questions:current?.questions||[],reviewLimitations:f.reviewLimitations||[],userAssistance:f.userAssistance||''},cosmetic:false}));});return;
  }
  if(['finding','findingDisposition'].includes(form)){
   const current=entities.find(n=>n.id===focusId&&n.kind==='finding');
   const evidence=()=>{const box=el('details');box.append(el('summary','Подтверждающие данные контекста'));body.append(box);for(const ev of entities.filter(n=>['context','evidence'].includes(n.kind)))field(box,ev.title,(F().evidenceIds||[]).includes(ev.id),'checkbox',yes=>{const ids=new Set(F().evidenceIds||[]);yes?ids.add(ev.id):ids.delete(ev.id);setDraft('evidenceIds',[...ids]);});};
   if(form==='findingDisposition'){
    body.append(el('p',current.title));pick('Итог рассмотрения','dispositionCode',Object.entries(findingDispositions),current.disposition.code);input('Обоснование итога','note','','textarea');input('Условие возврата при отсрочке','revisitTrigger','');pick('Заменяющий файндинг','replacementId',[['','Не выбран'],...entities.filter(n=>n.kind==='finding'&&n.id!==current.id).map(n=>[n.id,n.title])],'');
    evidence();button(body,'Проверить итог',async()=>{checkDraft();const f=F(),req=await requestCore('finding_disposition',current.id,f.note),d={code:f.dispositionCode,basis:f.note,evidenceIds:f.evidenceIds||[]};if(d.code==='deferred')d.revisitTrigger=f.revisitTrigger;if(d.code==='superseded')d.replacementId=f.replacementId;req.data.disposition=d;req.evidenceRefs=d.evidenceIds.map(id=>entities.find(n=>n.id===id)?.artifact).filter(Boolean);await prepare(req);});return;
   }
   input('Название файндинга','title',current?.title||'');input('Содержание файндинга','description',current?.description||'','textarea');pick('Тип файндинга','findingType',[['','Выберите тип'],...Object.entries(findingTypes)],current?.findingType||'');input('Обоснование находки','rationale',current?.rationale||'','textarea');
   if(F().evidenceIds===undefined)setDraft('evidenceIds',current?.evidenceIds||[]);evidence();
   renderFindingQuestionsEditor(body,current,F);
   input('Помощь пользователя','userAssistance',current?.userAssistance||'','textarea');
   input('Срочность вмешательства','interventionPriority',current?.interventionPriority||'');input('Важность внимания пользователя','userReviewPriority',current?.userReviewPriority||'');input('Область проверки','reviewScope',current?.reviewScope||'');input('Основание изменения','note','','textarea');
   button(body,'Проверить файндинг',async()=>{checkDraft();const f=F(),value={title:f.title,description:f.description||'',findingType:f.findingType,rationale:f.rationale,evidenceIds:f.evidenceIds||[],questions:current?.questions||[],userAssistance:f.userAssistance||'',reviewLimitations:f.reviewLimitations||[],interventionPriority:f.interventionPriority||'',userReviewPriority:f.userReviewPriority||'',reviewScope:f.reviewScope||''};if(!value.findingType)throw Error('Выберите тип файндинга.');
    const req=current?await requestCore('edit',current.id,f.note,{nodeId:current.id,changes:value,cosmetic:false}):await requestCore('add',data.subjectId,f.note,{entity:{id:uid(),kind:'finding',subjectId:data.subjectId,...value,...(data.analysisSourceId?{analysisSources:analysisSources(data.analysisSourceId)}:{})},location:'graph'});await prepare(req);});return;
  }
  if(form==='snapshot'){body.append(el('p','Точная сохранённая версия; только чтение.'));body.append(el('pre',JSON.stringify(packageDetail,null,2)));return;}
  if(form==='create'){
   input('Название','title');input('Назначение процесса','scope');input('Основание процесса','reason');input('Папка','path','processes/'+uid());
   button(body,'Проверить создание',async()=>{const f=F(),req=(await call({method:'schema',op:'create'})).request;Object.assign(req,{path:f.path||'processes/'+uid(),title:f.title,scope:f.scope,rootReason:f.reason,coreModel:'rdg-decision-v1',role:'working'});await prepare(req);});return;
  }
  if(['policyEditor','policyBinding'].includes(form)){
   if(!['working','copy'].includes(snapshot.package.role)||snapshot.immutableDefinition)throw Error('Изменения доступны в рабочем Process Graph.');
   const cap=snapshot.dependencyCatalog?.capabilities;if(!cap)throw Error('Реестр возможностей недоступен.');
   const fresh=()=>F(),definitions=[...builtInPolicies(),...(snapshot.dependencyCatalog?.policies||[])];
   const selected=definitions.filter(p=>p.id===(data.policyId||data.copyPolicyId)).sort((a,b)=>a.version-b.version).at(-1);
   const observationName=id=>cap.observations.find(o=>o.id===id)?.name||id;
   const write=async(action,value,note)=>savePolicyChange(action,value,note||'Настроена политика зависимостей');
   if(form==='policyEditor'){
    body.dataset.policyEditor='';
    if(!fresh().policyDraft){
     let p=selected?clone(selected):{name:'Новая политика',description:'',sourceKinds:[data.sourceKind||'context'],targetKinds:['requirement','decision','action'],rules:[{id:uid(),name:'Изменение содержания источника',role:'source',watch:'definition',operations:['changed'],enabled:true}]};
     if(p.pattern==='direct')p.rules=p.rules.map(r=>r.watch==='info'?{...r,watch:'canonInfo'}:r);
     if(p.pattern!=='roles'){
      p.roles=[{id:'target',kinds:p.targetKinds,required:true},{id:'source',kinds:p.sourceKinds,required:true}];p.relations=[];
      if(p.pattern==='parentDecisionContext'){
       p.roles=[{id:'target',kinds:p.targetKinds,required:true},{id:'parent',kinds:['decision'],required:true},
        {id:'source',kinds:['requirement','decision','action','context'],required:false,selector:{anchor:'parent',relation:'DECISION_CONTEXT',direction:'in',minDepth:1,maxDepth:1}}];
       p.relations=[{from:'parent',to:'target',type:['INTRODUCES','REQUIRES_ACTION']}];
      }
      p.rules=p.rules.flatMap(r=>p.pattern==='parentDecisionContext'?[...(r.operations.includes('changed')?[{...r,role:'source',operations:['changed']}]:[]),...(r.operations.some(o=>o!=='changed')?[{...r,id:uid(),name:r.name+' · состав контекста',role:'source',watch:'membership',operations:r.operations.filter(o=>o!=='changed')}]:[])]:[{...r,role:'source'}]);
     }
     p.pattern='roles';p.status='active';p.origin='user';delete p.builtIn;delete p.automatic;
     p.id=data.policyId?p.id:uid();p.version=data.policyId?p.version+1:1;
     setDraft('policyDraft',p);
    }
    const draft=fresh().policyDraft;
    const update=fn=>{const value=clone(fresh().policyDraft);fn(value);setDraft('policyDraft',value);};
    const rerun=fn=>{update(fn);render();};
    field(body,'Название политики',draft.name,'text',v=>update(p=>p.name=v));
    field(body,'Описание',draft.description,'textarea',v=>update(p=>p.description=v));
    body.append(el('p','Политика определяет роли и изменения. Реальные ID выбираются при применении. Требования применимости отключают зависимость при нарушении.','rdg-muted'));
    body.append(el('h3','Участники и отношения'));
    body.append(el('p','Роль — место участника в схеме. Конкретный ID выбирается при применении; динамическая роль находит текущий набор по отношению. Условия применимости проверяют, может ли применение продолжать действовать.','rdg-muted'));
    draft.roles.forEach((role,index)=>{
     const box=el('fieldset',null,'rdg-policy-form-rule');body.append(box);box.append(el('legend',role.id==='target'?'Цель пересмотра':policyRoleName(draft,role.id)));
     field(box,'Название роли',policyRoleName(draft,role.id),'text',v=>update(p=>p.roles[index].name=v));
     const change=(key,value)=>update(p=>p.roles[index][key]=value);
     const allowed=(role.id==='target'?cap.targetKinds:cap.entityKinds).filter(k=>k!=='evidence'||role.kinds.includes(k));
     for(const kind of allowed)field(box,kindLabel[kind]||kind,role.kinds.includes(kind),'checkbox',yes=>rerun(p=>{
      const kinds=new Set(p.roles[index].kinds);yes?kinds.add(kind):kinds.delete(kind);p.roles[index].kinds=[...kinds];
      if(role.id==='target')p.targetKinds=[...kinds];
     }));
     if(index>0){
      select(box,'Способ получения',[['explicit','Выбрать элемент при применении'],['selector','Набор по отношению']],role.selector?'selector':'explicit',v=>rerun(p=>{
       if(v==='explicit')delete p.roles[index].selector;
       else p.roles[index].selector={anchor:draft.roles[0].id,relation:'DEPENDS_ON',direction:'in',minDepth:1,maxDepth:1};
       p.roles[index].required=v==='explicit';
      }));
      if(role.selector){const sel=role.selector;
       const set=(key,value)=>rerun(p=>p.roles[index].selector[key]=value);
       select(box,'От какой роли',draft.roles.slice(0,index).map(r=>[r.id,policyRoleName(draft,r.id)]),sel.anchor,v=>set('anchor',v));
       renderPolicyRelationChoice(box,'Допустимые отношения (любое из выбранных)',sel.relation,v=>set('relation',v),cap);
       select(box,'Направление отношения',[['out','От выбранной роли к искомым участникам'],['in','От искомых участников к выбранной роли']],sel.direction,v=>set('direction',v));
       box.append(el('p','Глубина 1 — непосредственная связь. Большая глубина задаёт путь поиска участников; она не включает рекурсивное распространение stale.','rdg-muted'));
       for(const key of ['minDepth','maxDepth'])field(box,key==='minDepth'?'Минимальная глубина':'Максимальная глубина',sel[key],'number',v=>update(p=>p.roles[index].selector[key]=Number(v)));
       field(box,'Набор должен быть непустым',role.required||false,'checkbox',v=>change('required',v));
      }
      button(box,'Удалить роль',()=>rerun(p=>{p.roles.splice(index,1);p.rules=p.rules.filter(r=>r.role!==role.id);}));
     }
     const preds=role.conditions||[];
     preds.forEach((pred,j)=>renderPolicyPredicate(box,pred,v=>update(p=>p.roles[index].conditions[j]=v),cap));
     button(box,'+ Условие применимости роли',()=>rerun(p=>{p.roles[index].conditions??=[];p.roles[index].conditions.push({field:'tag',equals:'required'});}));
     if(preds.length)button(box,'Убрать условия роли',()=>rerun(p=>p.roles[index].conditions=[]));
    });
    button(body,'+ Наблюдаемый или промежуточный участник',()=>rerun(p=>{let id='role'+(p.roles.length+1);while(p.roles.some(r=>r.id===id))id+='x';p.roles.push({id,kinds:['context'],required:true});}));
    draft.relations.forEach((rel,index)=>{const box=el('fieldset',null,'rdg-policy-form-rule');body.append(box);box.append(el('legend','Обязательное отношение '+(index+1)));
     const set=(key,value)=>rerun(p=>p.relations[index][key]=value);
     select(box,'От роли',draft.roles.map(r=>[r.id,policyRoleName(draft,r.id)]),rel.from,v=>set('from',v));
     renderPolicyRelationChoice(box,'Обязательная связь (любое из выбранных отношений)',rel.type,v=>set('type',v),cap);
     select(box,'К роли',draft.roles.map(r=>[r.id,policyRoleName(draft,r.id)]),rel.to,v=>set('to',v));
     button(box,'Удалить ограничение',()=>rerun(p=>p.relations.splice(index,1)));
    });
    button(body,'+ Обязательное отношение',()=>rerun(p=>p.relations.push({from:p.roles[1].id,to:'target',type:'DEPENDS_ON'})));
    body.append(el('h3','Отслеживаемые изменения'));
    draft.rules.forEach((rule,index)=>{
     const box=el('fieldset',null,'rdg-policy-form-rule');body.append(box);box.dataset.policyRuleIndex=String(index);
     const set=(key,value)=>update(p=>p.rules[index][key]=value);
     select(box,'Наблюдаемый участник',draft.roles.map(r=>[r.id,policyRoleName(draft,r.id)]),rule.role,v=>rerun(p=>{const row=p.rules[index];row.role=v;const types=p.roles.find(r=>r.id===v).kinds,obs=cap.observations.find(o=>o.id===row.watch);const valid=types.filter(k=>obs.kinds.includes(k));if(!valid.length){row.watch='definition';row.operations=['changed'];delete row.eventType;delete row.predicate;delete row.whenKinds;}else if(valid.length<types.length)row.whenKinds=valid;else delete row.whenKinds;}));
     const kinds=draft.roles.find(r=>r.id===rule.role)?.kinds||[];
     const options=cap.observations.filter(o=>kinds.some(k=>o.kinds.includes(k)));
     const watchPicker=select(box,'Наблюдаемое изменение',cap.observations.map(o=>[o.id,o.name+(options.includes(o)?'':' · недоступно для этих типов')]),rule.watch,v=>rerun(p=>{
      const row=p.rules[index];row.watch=v;row.name=observationName(v);row.operations=[cap.observations.find(o=>o.id===v).operations[0]];delete row.predicate;delete row.eventType;
      if(v==='predicate')row.predicate={field:'tag',equals:'observed'};
      if(v==='event')row.eventType=cap.events[0];
      const supported=kinds.filter(k=>cap.observations.find(o=>o.id===v).kinds.includes(k));
      if(supported.length<kinds.length)row.whenKinds=supported;else delete row.whenKinds;
      delete row.memberRole;
     }));
     for(const option of watchPicker.options)option.disabled=!options.some(o=>o.id===option.value);
     const obs=cap.observations.find(o=>o.id===rule.watch);
     if(obs)renderMeaning(box,obs);
     if(kinds.length>1&&obs){const guard=el('fieldset');guard.append(el('legend','Для каких типов участника действует это условие'));box.append(guard);
      for(const kind of kinds){const supported=obs.kinds.includes(kind);const control=field(guard,(kindLabel[kind]||kind)+(supported?'':' · это наблюдение не поддерживается'),(rule.whenKinds||kinds).includes(kind)&&supported,'checkbox',yes=>rerun(p=>{const current=new Set(p.rules[index].whenKinds||kinds.filter(k=>obs.kinds.includes(k)));yes?current.add(kind):current.delete(kind);p.rules[index].whenKinds=[...current];}));control.disabled=!supported;}
     }
     for(const op of (obs?.operations||[]).filter(op=>(rule.whenKinds||kinds).some(k=>(obs.operationsByKind?.[k]||obs.operations).includes(op))))field(box,obs.operationLabels?.[op]||policyOperationLabels[op],rule.operations.includes(op),'checkbox',yes=>update(p=>{const ops=new Set(p.rules[index].operations);yes?ops.add(op):ops.delete(op);p.rules[index].operations=[...ops];}));
     if(rule.watch==='event'){select(box,'Тип записанного события',cap.eventDescriptions.map(e=>[e.id,e.name]),rule.eventType,v=>{set('eventType',v);render();});renderMeaning(box,eventMetadata(rule.eventType),{technicalId:true});}
     if(['directScope','context','canon','info','canonInfo','relations'].includes(rule.watch))select(box,'Ограничить изменившегося участника ролью',[['','Любой участник наблюдаемого набора'],...draft.roles.map(r=>[r.id,policyRoleName(draft,r.id)])],rule.memberRole||'',v=>rerun(p=>{if(v)p.rules[index].memberRole=v;else delete p.rules[index].memberRole;}));
     if(rule.watch==='predicate')renderPolicyPredicate(box,rule.predicate,v=>set('predicate',v),cap);
     field(box,'Название условия (можно оставить предложенное)',rule.name,'text',v=>set('name',v));
     field(box,'Условие включено',rule.enabled,'checkbox',v=>set('enabled',v));
     button(box,'Удалить условие',()=>rerun(p=>p.rules.splice(index,1)),draft.rules.length===1);
    });
    button(body,'+ Отслеживаемое изменение',()=>rerun(p=>p.rules.push({id:uid(),name:'Изменение содержания',role:p.roles[1].id,watch:'definition',operations:['changed'],enabled:true})));
    const dictionary=el('details');dictionary.dataset.policyDictionary='';dictionary.append(el('summary','Справочник отношений, наблюдений и событий'));body.append(dictionary);
    dictionary.append(el('p','Операция «добавлен участник» относится к выбранному набору. Сам участник мог существовать заранее; Graph-событие при этом может быть обычным изменением Decision.'));
    for(const [title,entries] of [['Отношения',cap.relations],['Наблюдения',cap.observations],['Записанные события',cap.eventDescriptions]]){const group=el('details');group.append(el('summary',title+' · '+entries.length));dictionary.append(group);for(const entry of entries){const item=el('section',null,'rdg-policy-rule');item.append(el('h4',entry.name));group.append(item);renderMeaning(item,entry,{technicalId:true});if(entry.operations)item.append(el('p','Операции: '+entry.operations.map(op=>entry.operationLabels[op]).join('; ')));}}
    body.append(el('h3','Абстрактная схема'));policyDiagram(body,draft);
    body.append(el('p','Обязательные отношения и условия ролей определяют применимость. Наблюдаемые изменения ниже определяют stale. Нарушение применимости сохраняет отключённое применение.','rdg-muted'));
    input('Основание изменения','note','Сохранена политика');
    button(body,'Проверить и сохранить политику',async()=>{const p=clone(fresh().policyDraft);p.sourceKinds=[...new Set(p.roles.filter(r=>r.id!=='target').flatMap(r=>r.kinds))];p.targetKinds=p.roles.find(r=>r.id==='target').kinds;await write('policy_save',p,fresh().note);});return;
   }
   body.dataset.policyBindingEditor='';
   const existing=(snapshot.graph.dependencyBindings||[]).find(b=>b.id===data.bindingId);
   const latest=allPolicies().filter(p=>!p.automatic&&(p.status==='active'||p.id===existing?.policyId));
   if(!latest.length){body.append(el('p','Нет доступных политик.'));return;}
   const pid=fresh().policyId||existing?.policyId||data.policyId||latest[0].id;
   const versions=definitions.filter(p=>p.id===pid&&(p.status==='active'||p.id===existing?.policyId&&p.version===existing.policyVersion)).sort((a,b)=>a.version-b.version);
   const policy=versions.find(p=>p.version===(fresh().policyVersion||existing?.policyVersion))||versions.at(-1);
   select(body,'Политика',latest.map(p=>[p.id,p.name]),pid,v=>{setDraft('policyId',v);setDraft('policyVersion',null);setDraft('bindings',{});render();});
   select(body,'Версия',versions.map(p=>[String(p.version),'v'+p.version+' · '+({active:'разрешена',disabled:'отключена',archived:'архивная'})[p.status]]),String(policy.version),v=>{setDraft('policyVersion',Number(v));render();});
   const explicit=policy.pattern==='roles'?policy.roles.filter(r=>!r.selector):[
    {id:'target',kinds:policy.targetKinds},{id:policy.pattern==='direct'?'source':'parent',kinds:policy.sourceKinds}];
   const binds=fresh().bindings||existing?.participantBindings||{};const resolved={...binds};
   const sourceSeed=explicit.find(role=>role.id!=='target'&&entities.some(n=>n.id===data.sourceId&&role.kinds.includes(n.kind)))?.id;
   for(const role of explicit){const candidates=entities.filter(n=>role.kinds.includes(n.kind)&&!n.lowLevel);
    const fallback=role.id==='target'?(existing?.targetId||data.nodeId||data.targetId):role.id==='source'?(existing?.sourceId||data.sourceId):role.id==='parent'?existing?.parentId:role.id===sourceSeed?data.sourceId:null;
    const assigned=binds[role.id]||(existing?.policyId===pid?(role.id==='target'?existing.targetId:role.id==='source'?existing.sourceId:role.id==='parent'?existing.parentId:null):null);
    const id=assigned||(candidates.some(n=>n.id===fallback)?fallback:null)||candidates[0]?.id;resolved[role.id]=id;
    if(id&&!candidates.some(n=>n.id===id)){const current=entities.find(n=>n.id===id);candidates.push({id,kind:current?.kind||role.kinds[0],title:current?'Тип не подходит роли · '+current.title:'Удалённый или недоступный участник'});}
    select(body,role.id==='target'?'Элемент для пересмотра':policyRoleName(policy,role.id),candidates.map(n=>[n.id,(kindCode[n.kind]||n.kind)+' · '+n.title+' · '+n.id]),id,v=>{setDraft('bindings',{...resolved,[role.id]:v});render();});
   }
   const value={id:existing?.id||uid(),policyId:pid,policyVersion:policy.version,targetId:resolved.target,
    sourceId:policy.pattern==='direct'?resolved.source:null,parentId:policy.pattern==='parentDecisionContext'?resolved.parent:null,
    enabled:existing?.enabled??true};
   if(existing){value.revision=existing.revision||1;value.status=existing.status|| (existing.enabled?'active':'disabled');value.reasonCode=existing.reasonCode||null;}
   if(policy.pattern==='roles')value.participantBindings=Object.fromEntries(Object.entries(resolved).filter(([k])=>k!=='target'));
   body.append(el('h3','Участники применения'));renderActualPolicyRoles(body,policy,value);
   if(existing)body.append(el('p','Смена версии выполняется только вашим выбором. Отключённое применение после редактирования остаётся отключённым до отдельной активации.','rdg-muted'));
   body.append(el('p','Создание не делает цель stale. Отключённое применение активируется отдельной кнопкой после проверки.','rdg-muted'));
   input('Основание','note','Настроено применение политики');
   button(body,'Проверить и сохранить применение',()=>write('binding_save',value,fresh().note));return;
  }
  if(form==='add'){
   if(data.processContextBank){body.append(el('p','Новый факт всего Process Graph. Рабочая область, структурный родитель и фокус не назначаются.','rdg-muted'));}
   else{if(F().kind===undefined)setDraft('kind',data.kind||'decision');select(body,'Новый блок',[['decision','Decision'],['requirement','Requirement'],['action','Обязательный Graph Action'],['external','Внешний Action'],['canon','Теория принятия решения'],['context','Контекст процесса'],['info','Info']],F().kind,v=>{setDraft('kind',v);render();});}
   input('Название','title');input('Описание','description','','textarea');
   if(data.processContextBank)input('Содержание','value','','textarea');
   else{
    input('Область R','scope',entities.find(n=>n.kind==='requirement')?.scope||'');
    if(F().kind==='canon')theoryFields();else input('Значение Context или Info','value','','textarea');
    pick('Тип Action','actionType',[['task','Реальное действие'],['select_decision','Выбрать Decisions'],['decide_acceptance','Проверить принятие Decision']],data.actionType||'task');
   }
   if(!data.processContextBank){
     const parentKinds=F().kind==='canon'?['decision','action']:['requirement','decision','action','canon'];
     if(F().kind==='canon'&&!entities.some(n=>n.id===(F().parentId??data.parentId??focusId)&&parentKinds.includes(n.kind)))setDraft('parentId','');
     pick('Связать с блоком','parentId',[['','Без связи'],...entities.filter(n=>parentKinds.includes(n.kind)&&n.id!==data.nodeId).map(n=>[n.id,(kindCode[n.kind]||'?')+' · '+n.title])],data.parentId??focusId);
   }
   if(!data.processContextBank){
    const targets=el('details');targets.append(el('summary','Контекст / targets Action'));body.append(targets);
    for(const node of snapshot.graph.nodes.filter(n=>['requirement','decision'].includes(n.kind)))field(targets,node.title,(data.targetIds||[]).includes(node.id),'checkbox',checked=>{const ids=new Set(F().targetIds||[]);if(checked)ids.add(node.id);else ids.delete(node.id);setDraft('targetIds',[...ids]);});
   }
   if(data.processContextBank){pick('Группа','contextGroupId',contextChoices(),data.contextGroupId||'');const extra=el('details');extra.append(el('summary','Источник данных'));body.append(extra);for(const [key,label] of [['scope','Область данных'],['version','Версия данных'],['source','Источник данных']])field(extra,label,F()[key]||'','text',v=>setDraft(key,v));}
   input('Основание изменения','note','','textarea');
   button(body,data.processContextBank?'Добавить контекст':'Добавить блок',async()=>{checkDraft();const f=F(),kind=data.processContextBank?'context':f.kind||'decision',id=uid(),entity={id,kind:kind==='external'?'action':kind,title:f.title,description:f.description||''};
    if(entity.kind==='requirement')entity.scope=f.scope||entities.find(n=>n.kind==='requirement')?.scope;
    if(entity.kind==='action')Object.assign(entity,{actionType:f.actionType||'task',lowLevel:kind==='external'&&(f.actionType||'task')!=='task',targetIds:f.targetIds||[],groupIds:[]});
    if(entity.kind==='canon')Object.assign(entity,{guidance:f.guidance||'',canons:f.canons||'',knownErrors:clone(f.knownErrors||[])});
    if(['context','info'].includes(entity.kind))entity.value=f.value;
    if(entity.kind==='context'){if(f.contextGroupId)entity.contextGroupId=f.contextGroupId;for(const key of ['scope','version','source'])if(data.processContextBank&&f[key])entity[key]=f[key];}
    const payload={entity,location:kind==='external'?'external':'graph'},parentNode=data.processContextBank?null:entities.find(n=>n.id===(f.parentId??focusId));
    if(payload.location==='graph'){
     if(f.workGraphId&&!data.processContextBank)payload.workGraphId=f.workGraphId;
     let type=null;if(parentNode?.kind==='requirement')type=entity.kind==='decision'?'DRIVES':entity.kind==='requirement'?'DERIVES':entity.kind==='action'?'REQUIRES_ACTION':null;
     if(parentNode?.kind==='decision')type=entity.kind==='requirement'?'INTRODUCES':entity.kind==='action'?'REQUIRES_ACTION':null;
     if(entity.kind==='canon'&&['decision','action'].includes(parentNode?.kind))type='CANON_FOR';
     if(entity.kind==='info'&&parentNode?.kind==='canon')type='INFO_FOR';
     if(type)payload.initialRelations=[{id:uid(),type,from:['CANON_FOR','INFO_FOR'].includes(type)?id:parentNode.id,
       to:['CANON_FOR','INFO_FOR'].includes(type)?parentNode.id:id}];
    }
    await prepare(await requestCore('add',focusId,f.note,payload));
   });return;
  }
  if(form==='dependencyRule'){
   if(!['working','copy'].includes(snapshot.package.role))throw Error('Изменение зависимостей доступно только в процессном Graph.');
   const dependent=entities.find(n=>n.id===focusId),existing=snapshot.graph.edges.find(e=>e.id===data.edgeId&&e.type==='DEPENDS_ON');
   if(!dependent||!['requirement','decision','action','finding'].includes(dependent.kind))throw Error('Некорректный зависимый блок.');
   const candidates=entities.filter(n=>n.id!==focusId&&!n.lowLevel&&['requirement','decision','action','context','info','canon'].includes(n.kind));
   const defaultSource=existing?.from||data.sourceId||candidates[0]?.id;
   const srcId=F().sourceId||defaultSource,src=entities.find(n=>n.id===srcId);
   body.dataset.dependencyRuleEditor='';
   body.append(el('p','Зависимый блок: '+dependent.title+'. Это правило вызывает пересмотр, но никогда не создаёт структурного родителя и не отменяет выбранный Decision.','rdg-muted'));
   if(existing){body.append(el('p','Источник: '+(src?.title||existing.from),'rdg-muted'));}
   else select(body,'Источник зависимости',candidates.map(n=>[n.id,sourceTitle(n)]),srcId,v=>{
    setDraft('sourceId',v);setDraft('preset','L1');setDraft('watch',['definition']);render();
   });
   const prior=existing?ruleOf(existing):null,preset=F().preset||prior?.preset||'L1';
   const options=[['L1',dependencyPresetNames.L1],['L2',dependencyPresetNames.L2]];
   if(src?.kind==='decision')options.push(...['decision_state','decision_context','decision_canon'].map(k=>[k,dependencyPresetNames[k]]));
   if(src?.kind==='canon')options.push(['canon_criteria',dependencyPresetNames.canon_criteria]);
   options.push(['custom','Настраиваемый']);
   select(body,'Базовое наблюдение',options,preset,v=>{
    setDraft('preset',v);setDraft('watch',[...(dependencyPresets[v]||['definition'])]);render();
   });
   const initial=prior?.watch||dependencyPresets[preset]||['definition'];
   const toggles=el('fieldset',null,'rdg-dependency-watch');toggles.append(el('legend','Отслеживать изменения'));body.append(toggles);
   for(const watch of allowedWatch(src?.kind)){
    field(toggles,watch==='info'&&src?.kind==='decision'?'Info теории решения · совместимость':dependencyLabels[watch],(F().watch||initial).includes(watch),'checkbox',checked=>{
     const current=new Set(F().watch||initial);if(checked)current.add(watch);else current.delete(watch);
     setDraft('watch',[...current]);
    });
   }
   if(src?.kind==='decision')body.append(el('p','В прежнем наблюдении Info для Decision отслеживаются Info его теории. В новом конструкторе это отдельный вариант «Info теории решения · совместимость»; прямые Info Decision выбираются отдельно.','rdg-muted'));
   body.append(el('p','L2 учитывает непосредственное окружение источника, включая предусмотренных его типом родителей. Набор наблюдений сохраняется на зависимости и может быть изменён вручную.','rdg-muted'));
   if(data.context)input('Роль элемента','comment',entities.find(n=>n.id===focusId)?.contextNotes?.[srcId]||data.comment||'','textarea');
   input('Основание изменения','note','','textarea');
   button(body,'Проверить зависимость',async()=>{checkDraft();const f=F();const sourceId=existing?.from||f.sourceId||defaultSource,
    selectedPreset=f.preset||prior?.preset||'L1';
    let watch=f.watch||prior?.watch||dependencyPresets[selectedPreset]||['definition'];
    if(!watch.length)throw Error('Выберите хотя бы одну отслеживаемую характеристику.');
    const relation={id:existing?.id||uid(),type:'DEPENDS_ON',from:sourceId,to:focusId,
     dependencyRule:{preset:selectedPreset,watch:[...new Set(watch)]}};
    if(data.context||existing?.dependencyPurpose==='decisionContext')relation.dependencyPurpose='decisionContext';
    const req=data.context?await requestCore('decision_context',focusId,f.note,{nodeId:focusId,sourceId,action:'save',comment:f.comment||'',rule:relation.dependencyRule}):await requestCore('dependency_rule',focusId,f.note,{mode:'save',relation,...(data.convertLegacy?{convertLegacy:data.convertLegacy}:{})});await prepare(req);
   });
   if(existing)button(body,'Удалить зависимость',async()=>{checkDraft();const f=F();
    await prepare(await requestCore('dependency_rule',focusId,f.note||'Явно удалить зависимость',
     {mode:'remove',edgeId:existing.id}));
   });
   return;
  }
  if(form==='contextRecord'){
   body.append(el('p','Сохранить ID, содержание, источник, версию, вложение и все ссылки. Изменение типа проходит обычную проверку зависимостей.'));
   pick('Группа','contextGroupId',[['default','Подтверждения (создать при отсутствии)'],...contextChoices()],F().contextGroupId||'default');input('Основание изменения','note','','textarea');
   button(body,'Проверить перевод',async()=>{const data={nodeId:focusId};if(F().contextGroupId!=='default'&&F().contextGroupId!==undefined)data.contextGroupId=F().contextGroupId||null;await prepare(await requestCore('context_record',focusId,F().note,data));});return;
  }
  if(form==='decisionContext'){
   if(!['working','copy'].includes(snapshot.package.role))throw Error('Контекст принятия решения разрешён только в процессном графе.');
   const decision=entities.find(n=>n.id===focusId);if(decision?.kind!=='decision')throw Error('Ожидался Decision.');
   body.append(el('p','Ссылки на существующие факты и блоки этого процесса. Не создают родителей, зависимостей или новых блоков.'));
   const candidates=[...snapshot.graph.nodes,...snapshot.graph.objects].filter(n=>n.id!==focusId&&['requirement','decision','action','context'].includes(n.kind));
   for(const n of candidates)field(body,(kindLabel[n.kind]||n.kind)+' · '+n.title,(data.decisionContextIds||[]).includes(n.id),'checkbox',yes=>{const ids=new Set(F().decisionContextIds||[]);if(yes)ids.add(n.id);else ids.delete(n.id);setDraft('decisionContextIds',[...ids].sort());});
   for(const n of candidates)input('Роль · '+n.title,'contextNote:'+n.id,decision.contextNotes?.[n.id]||'','textarea');
   input('Основание изменения','note','','textarea');
   button(body,'Проверить ссылки',async()=>{checkDraft();await prepare(await requestCore('edit',focusId,F().note,{nodeId:focusId,changes:{decisionContextIds:[...(F().decisionContextIds||[])].sort(),contextNotes:Object.fromEntries([...new Set([...(F().decisionContextIds||[]),...(snapshot.decisionContexts?.[focusId]||[]).map(r=>r.sourceId)])].map(id=>[id,F()['contextNote:'+id]??decision.contextNotes?.[id]??'']).filter(([,v])=>v.trim()))},cosmetic:false}));});return;
  }
  if(form==='rename'){
   const node=entities.find(n=>n.id===focusId);input('Название','title',node?.title);field(body,'Без изменения смысла',F().cosmetic??true,'checkbox',v=>setDraft('cosmetic',v));input('Основание изменения','note','','textarea');
   button(body,'Проверить переименование',async()=>{checkDraft();await prepare(await requestCore('edit',focusId,F().note,{nodeId:focusId,changes:{title:F().title},cosmetic:F().cosmetic??true}));});return;
  }
  if(form==='content'){
   const node=entities.find(n=>n.id===focusId);input('Название','title',node?.title);input('Описание','description',node?.description||'','textarea');input('Метки через запятую','tags',(node?.tags||[]).join(', '));
   if(node?.kind==='requirement')input('Область','scope',node.scope);
   if(node?.kind==='canon')theoryFields(node);
   if(['context','info'].includes(node?.kind))input('Содержание','value',node.value,'textarea');
   if(node?.kind==='context'){const extra=el('details');extra.append(el('summary','Источник данных'));body.append(extra);for(const [key,label] of [['scope','Область данных'],['version','Версия данных'],['source','Источник данных']])field(extra,label,F()[key]??node[key]??'','text',v=>setDraft(key,v));}
   if(node?.findingOrigin?.role==='proposal'){for(const n of entities.filter(n=>n.id!==node.id))field(body,'Изменяет: '+n.title,(F().impactTargetIds||node.impactTargetIds||[]).includes(n.id),'checkbox',yes=>{const ids=new Set(F().impactTargetIds||node.impactTargetIds||[]);yes?ids.add(n.id):ids.delete(n.id);setDraft('impactTargetIds',[...ids]);});}
   if(node?.kind==='evidence')for(const [key,label] of [['claim','Утверждение'],['scope','Область'],['version','Версия'],['source','Источник']])input(label,key,node[key]);
   input('Основание изменения','note','','textarea');button(body,'Проверить содержание',async()=>{checkDraft();const f=F(),changes={title:f.title,description:f.description,tags:f.tags.split(',').map(s=>s.trim()).filter(Boolean)};for(const key of ['scope','guidance','canons','knownErrors','value','claim','version','source','impactTargetIds'])if(f[key]!==undefined)changes[key]=f[key];await prepare(await requestCore('edit',focusId,f.note,{nodeId:focusId,changes,cosmetic:false}));});return;
  }
  if(form==='rootCause'){
   const causes=snapshot.graph.rootCauses.filter(c=>c.requirementId===focusId);for(const cause of causes){body.append(el('p',cause.reason+(cause.enabled?' · действует':' · выключено')));button(body,cause.enabled?'Выключить основание':'Включить основание',async()=>prepare(await requestCore('root_cause',focusId,F().note||'Явно изменить независимое основание',{cause:{...cause,enabled:!cause.enabled}})));}
   input('Новое независимое основание','reason','','textarea');input('Основание изменения','note','','textarea');button(body,'Добавить основание',async()=>prepare(await requestCore('root_cause',focusId,F().note,{cause:{id:uid(),requirementId:focusId,reason:F().reason,enabled:true}})));return;
  }
  if(form==='lensApply'){
   body.append(el('p','Записывается применение к наблюдаемой версии блока. Завершение работы подтверждается отдельно.'));input('Что сделано и проверено','note','','textarea');
   for(const ev of snapshot.graph.objects.filter(n=>['context','evidence'].includes(n.kind)))field(body,ev.title,(data.evidenceIds||[]).includes(ev.id),'checkbox',yes=>{const ids=new Set(F().evidenceIds||[]);if(yes)ids.add(ev.id);else ids.delete(ev.id);setDraft('evidenceIds',[...ids]);});
   button(body,'Проверить запись применения',async()=>{checkDraft();const req=await schema('lens_apply');Object.assign(req,{lensPackageId:F().lensPackageId,nodeIds:[focusId],evidenceIds:F().evidenceIds||[],recommendationIds:F().recommendationIds,note:F().note});await prepare(req);});return;
  }
  if(form==='command'){
   const node=entities.find(n=>n.id===focusId),command=data.command;body.append(el('h3',(node?.title||focusId)+' · '+command));input('Основание / наблюдение','note','','textarea');
   if(command==='complete'){
    const evidence=el('section');body.append(evidence);evidence.append(el('h3','Подтверждающие данные контекста'));
    for(const ev of snapshot.graph.objects.filter(n=>['context','evidence'].includes(n.kind)))field(evidence,ev.title,(data.evidenceIds||[]).includes(ev.id),'checkbox',checked=>{const ids=new Set(F().evidenceIds||[]);if(checked)ids.add(ev.id);else ids.delete(ev.id);setDraft('evidenceIds',[...ids]);});
    if(node?.actionType==='decide_acceptance')pick('Фактический исход','decisionOutcome',[['selected','Принято'],['unselected','Не принято']],data.decisionOutcome||'selected');
   }
   button(body,'Проверить действие',async()=>{checkDraft();let req;
    if(command==='delete'){req=await schema('delete',focusId);req.note=F().note;}
    else{req=await requestCore(command,focusId,F().note);if(command==='complete'){
      req.data={nodeId:focusId,basis:F().note,evidenceIds:F().evidenceIds||[]};if(node?.actionType==='decide_acceptance')req.data.decisionOutcome=F().decisionOutcome||'selected';
      req.evidenceRefs=req.data.evidenceIds.map(id=>entities.find(n=>n.id===id)?.artifact).filter(Boolean);
     }else if(command==='reopen')req.data.basis=F().note;else if(command==='review')req.data.basis=F().note;
    }await prepare(req);
   });return;
  }
  if(form==='workGraph'){
   const old=data.newArea?undefined:snapshot.graph.workGraphs.find(w=>w.id===(data.workGraphId||(screen().spec.kind==='workGraph'?screen().spec.id:null)));
   const areaIndex=old?snapshot.graph.workGraphs.findIndex(w=>w.id===old.id):snapshot.graph.workGraphs.length;
   const initialRoots=data.rootIds||old?.rootIds||(data.rootId||snapshot.graph.rootRequirementId?[data.rootId||snapshot.graph.rootRequirementId]:[]);
   const initialMembers=data.memberIds||old?.memberIds||initialRoots;
   input('Название области','title',old?.title||'');
   select(body,'Цвет рабочей области',workAreaColorKeys.map(key=>[key,workAreaColorNames[key]]),data.colorKey||workAreaColorKey(old,areaIndex),value=>setDraft('colorKey',value));
   const roots=el('section');body.append(roots);roots.append(el('h3','Начальные требования'));
   roots.append(el('p','Можно выбрать несколько точек входа в одну рабочую область.','rdg-muted'));
   for(const n of snapshot.graph.nodes.filter(n=>n.kind==='requirement'))field(roots,n.title,initialRoots.includes(n.id),'checkbox',yes=>{const ids=new Set(F().rootIds||initialRoots);if(yes)ids.add(n.id);else ids.delete(n.id);setDraft('rootIds',[...ids]);});
   const members=el('section');body.append(members);members.append(el('h3','Состав области'));
   members.append(el('p','Блоки могут входить сразу в несколько рабочих областей. Начальные требования будут включены автоматически.','rdg-muted'));
   for(const n of [...snapshot.graph.nodes,...snapshot.graph.objects])field(members,n.title,initialMembers.includes(n.id),'checkbox',yes=>{const ids=new Set(F().memberIds||initialMembers);if(yes)ids.add(n.id);else ids.delete(n.id);setDraft('memberIds',[...ids]);});
   input('Основание','note');
   button(body,'Проверить область',async()=>{checkDraft();const f=F(),rootIds=[...new Set(f.rootIds||initialRoots)],members=[...new Set([...(f.memberIds||initialMembers),...rootIds])];if(!rootIds.length)throw Error('Выберите хотя бы одно начальное требование.');await prepare(await requestCore('work_graph',focusId,f.note,{workGraph:{id:old?.id||uid(),title:f.title||old?.title,rootIds,memberIds:members,colorKey:f.colorKey||workAreaColorKey(old,areaIndex)}}));});return;
  }
  if(form==='group'){
   const old=snapshot.graph.decisionGroups.find(g=>g.id===data.groupId);input('Название группы','title',old?.title||'');pick('Родитель группы','parentId',snapshot.graph.nodes.filter(n=>n.kind==='requirement'||n.kind==='decision'&&snapshot.graph.edges.some(e=>e.type==='FINDING_RESPONSE'&&e.to===n.id)).map(n=>[n.id,n.title]),data.parentId||old?.parentId||snapshot.graph.rootRequirementId);
   input('Выбрать необходимо','selectionRequired',data.selectionRequired??old?.selectionRequired??true,'checkbox');input('Взаимоисключение','mutuallyExclusive',data.mutuallyExclusive??old?.mutuallyExclusive??true,'checkbox');
   const chosen=old?.members.map(m=>m.decisionId)||[];
   for(const n of snapshot.graph.nodes.filter(n=>n.kind==='decision'))field(body,n.title,(data.decisionIds||chosen).includes(n.id),'checkbox',yes=>{const ids=new Set(F().decisionIds||chosen);if(yes)ids.add(n.id);else ids.delete(n.id);setDraft('decisionIds',[...ids]);});input('Основание','note');
   button(body,'Проверить группу',async()=>{checkDraft();const f=F();await prepare(await requestCore('decision_group',focusId,f.note,{group:{id:old?.id||uid(),title:f.title||old?.title,parentId:f.parentId||old?.parentId||snapshot.graph.rootRequirementId,
    selectionRequired:f.selectionRequired??old?.selectionRequired??true,mutuallyExclusive:f.mutuallyExclusive??old?.mutuallyExclusive??true,members:(f.decisionIds||chosen).map(id=>({id:old?.members.find(m=>m.decisionId===id)?.id||uid(),decisionId:id}))}}));});return;
  }
  if(form==='place'){
   if(!snapshot.plan){button(body,'Добавить план во времени',async()=>prepare(await schema('plan_create')));return;}
   const step=snapshot.plan.steps.find(s=>s.id===data.stepId);pick('Разместить блок','nodeId',[...snapshot.graph.nodes,...snapshot.graph.externalActions].filter(n=>!n.lowLevel||screen().spec.showLowLevel).map(n=>[n.id,n.title]),data.nodeId||step?.ref.nodeId||focusId);
   const initialCase=data.caseId??snapshot.plan.forks.flatMap(f=>f.cases).find(c=>c.stepIds.includes(step?.id))?.id??'';
   const caseSelect=pick('Часть Plan','caseId',[['','Общая часть'],...snapshot.plan.forks.flatMap(f=>f.cases.map(c=>[c.id,f.title+' / '+c.title]))],initialCase);
   const lane=(F().caseId||initialCase)?snapshot.plan.forks.flatMap(f=>f.cases).find(c=>c.id===(F().caseId||initialCase))?.stepIds||[]:snapshot.plan.mainStepIds;
   pick('После размещения','afterStepId',[['','В начале'],...snapshot.plan.steps.filter(s=>lane.includes(s.id)&&s.id!==step?.id).map(s=>[s.id,s.title])],data.afterStepId??lane.filter(i=>i!==step?.id).at(-1)??'');
   caseSelect.onchange=()=>run(async()=>{setDraft('caseId',caseSelect.value);setDraft('afterStepId','');await flushDraft();render();});
   input('Не раньше','at',data.at??snapshot.plan.timeConstraints.find(t=>t.stepId===step?.id&&t.type==='notBefore')?.at??'','date');input('Дедлайн','deadline',data.deadline??snapshot.plan.timeConstraints.find(t=>t.stepId===step?.id&&t.type==='deadline')?.at??'','date');input('Основание','note');
   button(body,'Проверить размещение',async()=>{checkDraft();const f=F(),nodeId=f.nodeId||step?.ref.nodeId||focusId,req=await schema('place',nodeId);Object.assign(req,{nodeId,at:f.at??'','afterStepId':f.afterStepId||null,caseId:f.caseId||null,note:f.note||'Явное размещение существующего элемента'});if(step)req.stepId=step.id;
    if(f.deadline!=null){req.deadline=f.deadline;}await prepare(req);
   });return;
  }
  if(form==='fork'){
   if(!snapshot.plan){button(body,'Добавить план во времени',async()=>prepare(await schema('plan_create')));return;}
   const old=snapshot.plan.forks.find(f=>f.id===data.forkId);input('Название ветви','title',old?.title||'');pick('Начало после','afterStepId',[['','В начале Plan'],...snapshot.plan.steps.filter(s=>snapshot.plan.mainStepIds.includes(s.id)).map(s=>[s.id,s.title])],data.afterStepId||old?.afterStepId||'');
   const start=planMomentParts(old?.startAt),finish=planMomentParts(old?.end?.at);
   const dates=el('details');dates.append(el('summary','Дата и время начала · необязательно'));body.append(dates);
   field(dates,'Дата начала',F().startDate??start.date,'date',v=>setDraft('startDate',v));field(dates,'Время начала',F().startTime??start.time,'time',v=>setDraft('startTime',v));
   dates.append(el('small','Время — в часовом поясе браузера: '+Intl.DateTimeFormat().resolvedOptions().timeZone,'rdg-muted'));
   field(body,'Отметить конец ветвления',F().hasEnd??!!old?.end,'checkbox',v=>run(async()=>{setDraft('hasEnd',v);await flushDraft();render();}));
   if(F().hasEnd??!!old?.end){
    input('Название общей части','endTitle',old?.end?.title||'Общая последовательность');
    const endDates=el('details');endDates.append(el('summary','Дата и время конца · необязательно'));body.append(endDates);
    field(endDates,'Дата конца',F().endDate??finish.date,'date',v=>setDraft('endDate',v));field(endDates,'Время конца',F().endTime??finish.time,'time',v=>setDraft('endTime',v));
    body.append(el('p','После конца идёт основная последовательность Plan. Общие элементы размещайте в ней один раз.','rdg-muted'));
   }
   const cases=data.cases||old?.cases||[1,2].map(i=>({id:uid(),title:'Вариант '+i,decisionIds:[],stepIds:[]}));if(!data.cases)setDraft('cases',clone(cases));
   const editCase=(index,key,value)=>{const next=clone(F().cases||cases);next[index][key]=value;setDraft('cases',next);};
   for(const [i,c] of cases.entries()){
    const box=el('div',null,'rdg-rule');body.append(box);field(box,i===0?'Первое продолжение':i===1?'Второе продолжение':'Продолжение '+(i+1),c.title,'text',v=>editCase(i,'title',v));
    select(box,i===0?'Decision первого варианта':i===1?'Decision второго варианта':'Decision варианта '+(i+1),[['','Без привязки'],...snapshot.graph.nodes.filter(n=>n.kind==='decision').map(n=>[n.id,n.title])],c.decisionIds[0]||'',v=>editCase(i,'decisionIds',v?[v]:[]));
    button(box,'Убрать продолжение '+(i+1),async()=>{const next=clone(F().cases||cases);next.splice(i,1);setDraft('cases',next);await flushDraft();render();},cases.length<=2);
   }
   button(body,'Добавить продолжение',async()=>{setDraft('cases',[...clone(F().cases||cases),{id:uid(),title:'Вариант '+(cases.length+1),decisionIds:[],stepIds:[]}]);await flushDraft();render();});
   button(body,'Проверить ветвление',async()=>{checkDraft();const f=F(),req=await schema('plan_edit'),fork={id:old?.id||uid(),title:f.title||old?.title,afterStepId:f.afterStepId??old?.afterStepId??null,cases:clone(f.cases||cases)};if(!fork.afterStepId)fork.afterStepId=null;
    const markerAt=(prefix,parts,original)=>f[prefix+'Date']!==undefined||f[prefix+'Time']!==undefined?planMoment(f[prefix+'Date']??parts.date,f[prefix+'Time']??parts.time):original||'';
    const at=markerAt('start',start,old?.startAt);if(at)fork.startAt=at;
    if(f.hasEnd??!!old?.end){fork.end={title:f.endTitle??old?.end?.title??'Общая последовательность'};const at=markerAt('end',finish,old?.end?.at);if(at)fork.end.at=at;}
    const retained=new Set(fork.cases.map(c=>c.id));req.plan.mainStepIds.push(...(old?.cases||[]).filter(c=>!retained.has(c.id)).flatMap(c=>c.stepIds));
    const index=req.plan.forks.findIndex(v=>v.id===fork.id);if(index<0)req.plan.forks.push(fork);else req.plan.forks[index]=fork;await prepare(req);});
   if(old)button(body,'Убрать ветвление, сохранить размещения в общей части',async()=>{const req=await schema('plan_edit');req.plan.forks=req.plan.forks.filter(f=>f.id!==old.id);req.plan.mainStepIds.push(...old.cases.flatMap(c=>c.stepIds));await prepare(req);});return;
  }
  if(form==='copy'){
   input('Папка копии','path');input('Основание','note');button(body,'Проверить копирование',async()=>{checkDraft();if(screen().draft?.layout)throw Error('Сохраните раскладку перед копированием.');const req=await schema('copy');req.path=F().path;req.note=F().note;const spec=screen().spec;if(spec.kind==='workGraph')req.focus={kind:'workGraph',id:spec.id};else if(spec.kind==='focus'){const n=entities.find(n=>n.id===spec.id);req.focus={kind:n.kind,id:n.id};}await prepare(req);});return;
  }
  if(form==='relation'){
   const graphEntities=[...snapshot.graph.nodes,...snapshot.graph.objects];pick('От','from',graphEntities.map(n=>[n.id,n.title]),focusId);pick('Связь','type',['DRIVES','INTRODUCES','DERIVES','REQUIRES_ACTION','CANON_FOR','CONTEXT_FOR','INFO_FOR','EVIDENCE_FOR','DEPENDS_ON'].map(t=>[t,t]),'DRIVES');pick('К','to',graphEntities.map(n=>[n.id,n.title]),focusId);pick('Уровень зависимости','dependencyLevel',[['L1','L1'],['L2','L2']],'L1');input('Основание','note');
   button(body,'Проверить связь',async()=>{checkDraft();const f=F(),relation={id:uid(),type:f.type,from:f.from,to:f.to};if(f.type==='DEPENDS_ON')relation.dependencyLevel=f.dependencyLevel;await prepare(await requestCore('link',focusId,f.note,{relation}));});
   for(const e of snapshot.graph.edges.filter(e=>e.from===focusId||e.to===focusId))button(body,'Снять '+e.type+' · '+(entities.find(n=>n.id===(e.from===focusId?e.to:e.from))?.title||''),async()=>{const request=await schema('unlink',focusId);request.data={edgeId:e.id};request.note=F().note;await prepare(request);});return;
  }
  if(form==='windows'){renderWindows(body);return;}
  if(form==='attachments'){
   body.append(el('p','Здесь показаны участвующие пакеты. Изменение общего определения видно во всех подключениях.'));
   for(const id of snapshot.graph.recommendationPackageIds){const p=definitionMeta(id),card=el('div',null,'rdg-card');card.append(el('strong',p?.title||'Определение недоступно'));button(card,'Подробности пакета',()=>openPackage(id));button(card,'Отключить',async()=>{const req=await schema('recommendation_attach');req.packageIds=snapshot.graph.recommendationPackageIds.filter(i=>i!==id);req.note='Явно отключён пакет рекомендаций';await prepare(req);});body.append(card);}
   button(body,'Добавить пакет…',async()=>{form=null;await sync(v=>{v.explorer.open=true;v.explorer.tab='packages';v.explorer.selectedPackageId=null;});render();});return;
  }
  if(form==='capture'){
   input('Название готового графа','title',snapshot.graph.title);pick('Тип','role',[['ready','Шаблон графа'],['lens','Граф линзы']],data.role||'ready');input('Папка','path');input('Ключ линзы','lensKey');input('Основание','note');
   for(const p of (snapshot.recommendations?.packages||[]))field(body,'Включить пакет: '+p.title,(data.recommendationIds||[]).includes(p.id),'checkbox',yes=>{const ids=new Set(F().recommendationIds||[]);if(yes)ids.add(p.id);else ids.delete(p.id);setDraft('recommendationIds',[...ids]);});
   button(body,'Проверить упаковку',async()=>{checkDraft();const f=F(),req=await schema('capture_ready');Object.assign(req,{role:f.role||'ready',title:f.title||snapshot.graph.title,path:f.path,note:f.note,recommendationIds:f.recommendationIds||[]});
    if(req.role==='lens')req.lensKey=f.lensKey;const spec=screen().spec;if(spec.kind==='workGraph')req.focus={kind:'workGraph',id:spec.id};else if(spec.kind==='focus'){const n=entities.find(n=>n.id===spec.id);req.focus={kind:n.kind,id:n.id};}await prepare(req);
   });return;
  }
  if(form==='insert'){
   const ready=catalog.packages.find(r=>r.packageId===data.sourcePackageId);body.append(el('p','Шаблон: '+(ready?.title||'')));
   const targetId=data.targetPackageId||catalog.packages.find(p=>['working','copy'].includes(p.role)&&p.coreModel==='rdg-decision-v1')?.packageId;
   select(body,'Процесс назначения',catalog.packages.filter(p=>['working','copy'].includes(p.role)&&p.coreModel==='rdg-decision-v1').map(p=>[p.packageId,p.title]),targetId,id=>run(async()=>{setDraft('targetPackageId',id);await flushDraft();targetSnapshots.set(id,await call({method:'read',packageId:id}));render();}));
   const target=targetSnapshots.get(targetId);pick('Родительский Requirement','parentRequirementId',[['','Без родителя'],...(target?.graph.nodes||[]).filter(n=>n.kind==='requirement').map(n=>[n.id,n.title])],data.parentRequirementId||'');input('Основание','note');
   button(body,'Проверить вставку',async()=>{const f=F(),target=f.targetPackageId||snapshot.package.packageId,req=(await call({method:'schema',op:'apply_ready',packageId:target,sourcePackageId:data.sourcePackageId})).request;req.note=f.note;if(f.parentRequirementId)req.parentRequirementId=f.parentRequirementId;await prepare(req);});return;
  }
 }
 function renderWindows(body){const data=draftValue().form||{},s=screen();for(const [name,title] of [['historyWindow','History'],['planWindow','Plan']]){
  const box=el('section',null,'rdg-rule');body.append(box);box.append(el('h3',title));const active=data[name]||s.spec[name]||{};
  const update=(key,value)=>{const range={...(draftValue().form?.[name]||s.spec[name]||{}),[key]:value};if(!value)delete range[key];setDraft(name,range);};
  field(box,'Начало '+title,active.from||'','text',v=>update('from',v));field(box,'Конец '+title,active.to||'','text',v=>update('to',v));
  button(box,'Календарь '+title,()=>{calendar={name,month:(active.from||new Date().toISOString().slice(0,10)).slice(0,7),first:null};render();});
  button(box,'Применить '+title,async()=>{const range=clone(draftValue().form?.[name]||{});await changeView({[name]:range});form='windows';render();});
 }
 if(calendar){const box=el('div',null,'rdg-rule');body.append(box);const [year,month]=calendar.month.split('-').map(Number);const row=el('div',null,'rdg-row');box.append(row);
  const move=delta=>{const d=new Date(year,month-1+delta,1);calendar.month=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');render();};button(row,'← Месяц',()=>move(-1));row.append(el('strong',calendar.month));button(row,'Месяц →',()=>move(1));
  const grid=el('div',null,'rdg-calendar');box.append(grid);const first=(new Date(year,month-1,1).getDay()+6)%7,total=new Date(year,month,0).getDate();for(let i=0;i<first;i++)grid.append(el('span'));
  for(let day=1;day<=total;day++){const iso=calendar.month+'-'+String(day).padStart(2,'0');button(grid,String(day),async()=>{if(!calendar.first){calendar.first=iso;note('Выберите конец периода.');return;}const range={from:[calendar.first,iso].sort()[0],to:[calendar.first,iso].sort()[1]},name=calendar.name;setDraft(name,range);await flushDraft();await changeView({[name]:range});calendar=null;form='windows';render();}).setAttribute('aria-label',iso);}
 }
 }

 async function openPackage(id,definition=null){form=null;packageDetail=null;
  if(id&&!registry.packages.some(p=>p.id===id)){const one=await call({method:'recommendation_catalog',packageId:id,limit:1});registry.packages.push(...one.packages);}
  await sync(v=>{v.explorer.open=true;v.explorer.tab='packages';v.explorer.selectedPackageId=id||definition.id;const active=v.screens.find(s=>s.id===v.activeScreenId);if(active?.draft)active.draft.open=false;if(definition)v.explorer.drafts[definition.id]={definition,baseRegistryRevision:registry.registryRevision,isNew:true,attach:false};});render();
 }
 function renderPackageEditor(list){const exp=session.explorer,id=exp.selectedPackageId,current=registry.packages.find(p=>p.id===id),draft=exp.drafts[id],definition=clone(draft?.definition||current);if(!definition){list.append(el('p','Пакет недоступен.'));return;}
  list.replaceChildren();button(list,'← Все пакеты',()=>sync(v=>v.explorer.selectedPackageId=null,true));list.append(el('h3',definition.title));
  const supplied=!!(current?.supplied&&!current?.userManaged),base=draft?.baseRegistryRevision??registry.registryRevision,isNew=draft?.isNew||false;
  function change(fn){return sync(v=>{const d=v.explorer.drafts[id]??={definition:clone(current),baseRegistryRevision:registry.registryRevision,isNew:false,attach:false};fn(d);});}
  const title=field(list,'Название',definition.title,'text',value=>void change(d=>d.definition.title=value).catch(e=>note(e.message,true)));title.disabled=supplied;
  const key=field(list,'Ключ',definition.key,'text',value=>void change(d=>d.definition.key=value).catch(e=>note(e.message,true)));key.disabled=supplied;
  for(const [index,rule] of definition.rules.entries()){
   const card=el('section',null,'rdg-rule');list.append(card);card.append(el('strong','Правило '+(index+1)));
   for(const kind of ['requirement','decision','action','canon','context','info',...(rule.nodeKinds.includes('evidence')?['evidence']:[])]){const n=field(card,kind,rule.nodeKinds.includes(kind),'checkbox',yes=>void change(d=>{const values=new Set(d.definition.rules[index].nodeKinds);if(yes)values.add(kind);else values.delete(kind);d.definition.rules[index].nodeKinds=[...values];}).catch(e=>note(e.message,true)));n.disabled=supplied;}
   const sc=select(card,'Область',[['all','Все подходящие'],...(snapshot?[['identity','Одна identity'],['children','Прямые дети'],['descendants','Все потомки']]:[])],rule.scope,value=>run(async()=>{await change(d=>{const r=d.definition.rules[index];r.scope=value;if(value==='all')delete r.anchor;else r.anchor??={packageId:snapshot.package.packageId,identitySpace:snapshot.graph.identitySpace,nodeId:screen().spec.kind==='focus'?screen().spec.id:snapshot.graph.rootRequirementId};});render();}));sc.disabled=supplied;
   if(rule.anchor){card.append(el('p','Graph: '+(graphMeta(rule.anchor.packageId)?.title||rule.anchor.packageId),'rdg-muted'));const ids=snapshot?[...snapshot.graph.nodes,...snapshot.graph.objects,...snapshot.graph.externalActions]:[];
    const anchor=select(card,'Опорный блок',ids.map(n=>[n.id,n.title]),rule.anchor.nodeId,value=>void change(d=>d.definition.rules[index].anchor={packageId:snapshot.package.packageId,identitySpace:snapshot.graph.identitySpace,nodeId:value}).catch(e=>note(e.message,true)));anchor.disabled=supplied||!snapshot;
   }
   const state=select(card,'Состояние',[['any','Любое'],['open','Открыто'],['discovered','Обнаружено'],['unselected','Не выбрано'],['selected','Выбрано'],['completed','Завершено'],['review_required','Нужна проверка']],rule.state,value=>void change(d=>d.definition.rules[index].state=value).catch(e=>note(e.message,true)));state.disabled=supplied;
   const tag=field(card,'Метка',rule.tag||'','text',value=>void change(d=>{const r=d.definition.rules[index];if(value)r.tag=value;else delete r.tag;}).catch(e=>note(e.message,true)));tag.disabled=supplied;
   const lenses=el('details');lenses.append(el('summary','Графы линз'));card.append(lenses);
   for(const lens of catalog.packages.filter(p=>p.role==='lens'&&p.coreModel==='rdg-decision-v1')){
    const checked=rule.lensRefs.some(ref=>ref.packageId===lens.packageId),control=field(lenses,lens.title,checked,'checkbox',yes=>void change(d=>{const r=d.definition.rules[index];r.lensRefs=r.lensRefs.filter(ref=>ref.packageId!==lens.packageId);if(yes)r.lensRefs.push({packageId:lens.packageId,identitySpace:lens.identitySpace,lensKey:lens.lensKey});}).catch(e=>note(e.message,true)));control.disabled=supplied;
   }
   button(card,'Удалить правило',async()=>{await change(d=>d.definition.rules.splice(index,1));render();},supplied||definition.rules.length===1);
  }
  if(!supplied)button(list,'Добавить правило',async()=>{await change(d=>d.definition.rules.push(newDefinition().rules[0]));render();});
  const attach=field(list,'Подключить к открытому Graph после создания',draft?.attach||false,'checkbox',yes=>void change(d=>d.attach=yes).catch(e=>note(e.message,true)));attach.disabled=!isNew||!snapshot;
  if(draft&&base!==registry.registryRevision){list.append(el('p','Каталог изменился; черновик сохранён.','rdg-error'));button(list,'Обновить основание после просмотра',async()=>{await change(d=>{d.baseRegistryRevision=registry.registryRevision;if(!d.isNew)d.definition.revision=(current?.revision||0)+1;});render();});}
  button(list,'Проверить сохранение пакета',async()=>{await queue;const d=session.explorer.drafts[id]||{definition:clone(current),baseRegistryRevision:registry.registryRevision,isNew:false};
   const value=clone(d.definition);value.revision=d.isNew?1:(current?.revision||0)+1;
   const request={op:'recommendation_edit',transactionId:uid(),expectedRegistryRevision:d.baseRegistryRevision,action:d.isNew?'create':'edit',definition:value,note:'Явная правка определения пакета рекомендаций'};
   if(!d.isNew)request.packageId=id;if(d.isNew&&d.attach)request.attachTo={packageId:snapshot.package.packageId,expectedPackageRevision:snapshot.package.revision,expectedGraphRevision:snapshot.graph.revision};await prepare(request);
  },supplied);
  if(current){button(list,'Создать изменяемую копию',()=>prepare({op:'recommendation_edit',transactionId:uid(),expectedRegistryRevision:registry.registryRevision,action:'copy',packageId:current.id,note:'Независимая копия определения пакета'}));
   if(snapshot&&!snapshot.graph.recommendationPackageIds.includes(id))button(list,'Подключить к открытому Graph',async()=>{const request=await schema('recommendation_attach');request.packageIds=[...snapshot.graph.recommendationPackageIds,id];request.note='Явно подключён пакет рекомендаций';await prepare(request);});
   button(list,'Удалить определение',()=>prepare({op:'recommendation_edit',transactionId:uid(),expectedRegistryRevision:registry.registryRevision,action:'remove',packageId:id,note:'Явно удалить определение пакета'}),!!current.supplied);
  }
  list.append(el('h3','Участвует в Graph'));
  for(const ref of registry.participation?.[id]||[])button(list,ref.title,()=>navigate(ref.packageId,{kind:'graph'}));
 }
 render();
 const api={start:initial=>run(()=>start(initial)),open,refresh,prepare,commit,focus:focusNode,
  get view(){return snapshot;},get session(){return session;},get busy(){return busy;},get pending(){return pending;},
  get switchBlocked(){return !!pending||!!screen()?.draft?.layout;},
  async api(message){await flushDraft();const result=await call(message);if(message.method==='view_session'&&message.sessionId===session?.id){session=result;if(message.action==='update')await load();}return result;}
 };
 return api;
}
return {mount};
});
// END GENERATED RDG DECISION UI
// BEGIN GENERATED RDG VISUAL PROJECTION
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
    if(options.document){
      const documentRows=[],seen=new Set(),active=new Set();
      for(const {id,relations,groups} of focusParents.values()){
        documentRows.push({entityId:id,parentRef:true,entityDepth:0,
          parentRelations:[...relations].sort(),parentGroups:[...groups].sort()});
      }
      const order=options.documentRootId&&structural.has(options.documentRootId)?
        [options.documentRootId,...roots.filter(id=>id!==options.documentRootId)]:roots;
      for(const root of order){
        if(seen.has(root))continue;
        const stack=[{id:root,depth:0,relation:'root'}];
        while(stack.length){
          const row=stack.pop();
          if(row.exit){active.delete(row.id);continue;}
          const cycle=active.has(row.id),shared=seen.has(row.id);
          documentRows.push({entityId:row.id,entityDepth:row.depth,relation:row.relation,
            via:row.via,parentId:row.parentId,cycle,shared,
            outsideParentIds:[...(outsideParents.get(row.id)||[])],
            groupMemberships:membershipsByDecision.get(row.id)||[]});
          if(shared)continue;
          seen.add(row.id);active.add(row.id);
          stack.push({id:row.id,exit:true});
          const b=bucket(row.id);
          for(const child of [...b.requirements,...b.decisions,...b.actions].reverse())
            stack.push({id:child.id,depth:row.depth+1,relation:child.relation,
              via:child.via,parentId:row.id});
        }
      }
      return {rows:documentRows};
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
// END GENERATED RDG VISUAL PROJECTION
// BEGIN GENERATED RDG PORTABLE UI
/* Portable UI: application projections and intents only. No domain writer. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else{
    root.RDGPortableUI=api;
    if(root.RDG_LOCAL_PORTABLE)Promise.resolve().then(()=>{
      const host=document.createElement('div');host.id='rdg-viewer-root';document.body.appendChild(host);
      const base=new URL('./',location.href);
      const send=async (route,body)=>{
        const response=await fetch(new URL(route,base),{method:'POST',credentials:root.RDG_AUTHENTICATED_SERVER?'same-origin':'omit',redirect:'error',
          headers:{'Content-Type':'application/json','X-RDG-Session':root.RDG_SESSION},body:JSON.stringify(body)});
        const value=await response.json();
        if(!response.ok){const error=Error(value.error||'Запрос отклонён');error.definite=value.definite!==false;throw error;}
        return value;
      };
      const call=body=>send('command',body),approval=root.RDG_APPROVAL_AVAILABLE?body=>send('approval',body):undefined;
      root.RDG_PORTABLE_EDITOR=api.mount(host,{call,approval},{document});void root.RDG_PORTABLE_EDITOR.start();
    });
  }
})(globalThis,function(){
  'use strict';
  const clone=value=>JSON.parse(JSON.stringify(value));
  const names={working:'Рабочий',ready:'Шаблон ready',copy:'Копия',lens:'Линза'};
  const statuses={future:'Предстоящие',possible:'Возможные',unresolved:'Требуют решения',excluded:'Не входят в предстоящее'};
  function diffRows(before,after,path=''){
    if(JSON.stringify(before)===JSON.stringify(after))return [];
    if(Array.isArray(before)&&Array.isArray(after)){
      const keyed=value=>value.every(v=>v&&typeof v==='object'&&typeof v.id==='string')&&new Set(value.map(v=>v.id)).size===value.length;
      if(keyed(before)&&keyed(after)){
        const old=new Map(before.map(v=>[v.id,v])),next=new Map(after.map(v=>[v.id,v])),rows=[];
        const ids=[...new Set([...old.keys(),...next.keys()])].sort();
        for(const id of ids)rows.push(...diffRows(old.get(id),next.get(id),path+'['+id+']'));
        const oldOrder=before.map(v=>v.id),newOrder=after.map(v=>v.id);
        if(JSON.stringify(oldOrder)!==JSON.stringify(newOrder))rows.push({path:path+' · порядок',before:oldOrder,after:newOrder});
        return rows;
      }
    }else if(before&&after&&typeof before==='object'&&typeof after==='object'&&!Array.isArray(before)&&!Array.isArray(after)){
      return [...new Set([...Object.keys(before),...Object.keys(after)])].sort().flatMap(
        key=>diffRows(before[key],after[key],path?path+'.'+key:key));
    }
    return [{path:path||'Содержимое',before,after}];
  }
  async function browserAssertion(begin){
    if(!globalThis.isSecureContext||!globalThis.navigator?.credentials?.get)throw Error('WebAuthn недоступен в этом браузере или по этому адресу.');
    const decode=text=>Uint8Array.from(atob(text.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));
    const encode=value=>btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
    const options=begin.options.publicKey;
    const publicKey=globalThis.PublicKeyCredential?.parseRequestOptionsFromJSON?
      globalThis.PublicKeyCredential.parseRequestOptionsFromJSON(options):
      {...options,challenge:decode(options.challenge),allowCredentials:options.allowCredentials?.map(c=>({...c,id:decode(c.id)}))};
    const credential=await navigator.credentials.get({publicKey});
    if(!credential)throw Error('Подтверждение отменено.');
    if(credential.toJSON)return credential.toJSON();
    const r=credential.response;
    return {id:credential.id,rawId:encode(credential.rawId),type:credential.type,
      clientExtensionResults:credential.getClientExtensionResults(),
      response:{authenticatorData:encode(r.authenticatorData),clientDataJSON:encode(r.clientDataJSON),
        signature:encode(r.signature),userHandle:r.userHandle==null?null:encode(r.userHandle)}};
  }
  async function browserRegistration(begin){
    if(!globalThis.isSecureContext||!navigator.credentials?.create)throw Error('Регистрация ключа недоступна в этом браузере.');
    const decode=text=>Uint8Array.from(atob(text.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));
    const encode=value=>btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
    const options=begin.options.publicKey;
    const publicKey=globalThis.PublicKeyCredential?.parseCreationOptionsFromJSON?
      PublicKeyCredential.parseCreationOptionsFromJSON(options):
      {...options,challenge:decode(options.challenge),user:{...options.user,id:decode(options.user.id)},
       excludeCredentials:options.excludeCredentials?.map(c=>({...c,id:decode(c.id)}))};
    const credential=await navigator.credentials.create({publicKey});
    if(!credential)throw Error('Регистрация отменена.');
    if(credential.toJSON)return credential.toJSON();
    return {id:credential.id,rawId:encode(credential.rawId),type:credential.type,
      clientExtensionResults:credential.getClientExtensionResults(),
      response:{attestationObject:encode(credential.response.attestationObject),
                clientDataJSON:encode(credential.response.clientDataJSON),
                transports:credential.response.getTransports?.()||[]}};
  }
  function mount(container,transport,{document:doc=globalThis.document,onStateChange=()=>{},getAssertion=null,startInExplorer=globalThis.RDG_DECISION_EXPLORER===true}={}){
    let decisionController=null,decisionActive=false;let catalog=null,migrationSources=null,view=null,selected=null,focus={kind:'graph'},busy=false,pending=null,draft=null,history=null,lensReturn=null;
    let approvalList=null,approvalCurrent=null,approvalMessage='',approvalUncertain=false,approvalWorking=false,approvalOpening=null,enrollment=null,enrollmentMessage='';
    const root=doc.createElement('section');root.className='rdgp';container.replaceChildren(root);
    const style=doc.createElement('style');style.textContent=`
      .rdgp{font:14px/1.5 system-ui;color:#e3edf7;background:#14263a;padding:16px;border-radius:10px;min-width:0}
      .rdgp *{box-sizing:border-box}.rdgp h2,.rdgp h3{margin:8px 0}.rdgp button,.rdgp input,.rdgp select,.rdgp textarea{font:inherit;color:inherit;background:#203b53;border:1px solid #65849f;border-radius:5px;padding:6px 9px}
      .rdgp button{cursor:pointer}.rdgp button:disabled{opacity:.5;cursor:default}.rdgp label{display:block;margin:7px 0}.rdgp input,.rdgp textarea,.rdgp select{max-width:100%}.rdgp textarea{width:100%;min-height:90px}.rdgp pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 ui-monospace,monospace}
      .rdgp .rp-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.rdgp .rp-grid{display:grid;grid-template-columns:minmax(180px,260px) minmax(0,1fr);gap:16px}.rdgp .rp-catalog button{display:block;width:100%;text-align:left;margin:7px 0}.rdgp .rp-catalog small{display:block;overflow-wrap:anywhere;color:#bdd0df}.rdgp .rp-card{border:1px solid #58748c;border-radius:7px;padding:10px;margin:10px 0}.rdgp .rp-error{color:#ffc5ab}.rdgp .rp-stale{color:#ffd28f}.rdgp summary{cursor:pointer;font-weight:600}.rdgp svg{width:100%;min-height:260px;background:#102033;border-radius:6px;touch-action:none}.rdgp svg text{fill:#e3edf7;font:12px system-ui;pointer-events:none}.rdgp svg .rp-node{cursor:pointer}.rdgp .rp-status{white-space:pre-wrap;margin:10px 0}.rdgp .rp-graph-tools{display:flex;gap:8px;flex-wrap:wrap}.rdgp .rp-pill{border:1px solid #6c8399;border-radius:12px;padding:2px 8px;display:inline-block;margin-right:6px}@media(max-width:720px){.rdgp .rp-grid{grid-template-columns:1fr}.rdgp .rp-catalog{max-height:220px;overflow:auto}}
    `;root.appendChild(style);
    style.textContent+=".rdgp .rp-diff{width:100%;table-layout:fixed;border-collapse:collapse;margin:10px 0}.rdgp .rp-diff th,.rdgp .rp-diff td{border:1px solid #58748c;padding:7px;vertical-align:top;overflow-wrap:anywhere}.rdgp .rp-diff th{text-align:left}.rdgp .rp-diff pre{margin:0}.rdgp .rp-approvals{overflow-wrap:anywhere}.rdgp .rp-approvals button{max-width:100%;overflow-wrap:anywhere}.rdgp .rp-approvals>button{margin:4px}.rdgp .rp-approval-status{white-space:pre-wrap}";
    style.textContent+=`
      .rdgp .rp-approval-header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px}
      .rdgp .rp-approval-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:10px;margin:12px 0}
      .rdgp .rp-request{display:flex;flex-direction:column;align-items:flex-start;gap:7px;text-align:left;padding:12px;min-width:0}
      .rdgp .rp-request strong{font-size:15px;line-height:1.4}.rdgp .rp-request[aria-pressed="true"]{background:#24506b;border-color:#8ccbf0;box-shadow:inset 3px 0 #8ccbf0}
      .rdgp .rp-request-summary{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:13px;color:#c4d4e2}
      .rdgp .rp-request-meta{font-size:13px;color:#bdd0df}.rdgp .rp-badge{font-size:12px;padding:2px 8px;border-radius:10px;background:#152b3d;color:#d5e7f3}
      .rdgp .rp-enrollment{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:10px 12px;margin:12px 0;background:#102033;border:1px solid #496880;border-radius:6px}
      .rdgp .rp-enrollment details{margin-left:auto}.rdgp .rp-enrollment p{margin:0}.rdgp .rp-selected-request{border-color:#8ccbf0}
      .rdgp .rp-approval-status{padding:10px 12px;background:#203b53;border-radius:6px}
    `;
    const approvals=el('section',null,'rp-card rp-approvals');approvals.setAttribute('aria-label','Запросы подтверждения');
    const heading=el('h2','Graph · пакеты'),status=el('p','Подключение…','rp-status'),bar=el('div',null,'rp-bar');
    const grid=el('div',null,'rp-grid'),aside=el('nav',null,'rp-catalog'),main=el('main'),preview=el('section',null,'rp-card');
    root.appendChild(heading);root.appendChild(bar);root.appendChild(status);root.appendChild(preview);root.appendChild(approvals);root.appendChild(grid);grid.appendChild(aside);grid.appendChild(main);
    style.textContent+=".rdgp.rdgp-decision-host{padding:0;border-radius:0;height:100%;min-height:490px}body:has(#rdg-viewer-root .rdgp-decision-host){margin:0;background:#0e1927}#rdg-viewer-root:has(.rdgp-decision-host){height:100dvh}body:has(#rdg-viewer-root .rdgp-decision-host)>.rdg-session-notice{display:none}";
    const decisionHost=el('section');decisionHost.style.height='100%';decisionHost.hidden=true;root.appendChild(decisionHost);
    function decisionMode(enabled){decisionActive=enabled;root.classList.toggle('rdgp-decision-host',enabled);for(const n of [heading,bar,status,preview,approvals,grid])n.style.display=enabled?'none':'';decisionHost.hidden=!enabled;}
    function el(tag,text,cls){const n=doc.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
    function button(parent,text,fn,disabled=false){const n=el('button',text);n.type='button';n.disabled=disabled;n.onclick=()=>run(fn);parent.appendChild(n);return n;}
    function field(parent,title,value='',type='text'){const label=el('label',title+' '),n=el(type==='textarea'?'textarea':'input');if(type!=='textarea')n.type=type;n.value=value;label.appendChild(n);parent.appendChild(label);return n;}
    function select(parent,title,items,value){const label=el('label',title+' '),n=el('select');for(const [id,text] of items){const o=el('option',text);o.value=id;n.appendChild(o);}n.value=value??items[0]?.[0]??'';label.appendChild(n);parent.appendChild(label);return n;}
    function details(parent,title){const n=el('details'),s=el('summary',title);n.appendChild(s);parent.appendChild(n);return n;}
    function json(parent,value){const pre=el('pre',JSON.stringify(value,null,2));parent.appendChild(pre);return pre;}
    function note(text,error=false){status.textContent=text;status.className='rp-status'+(error?' rp-error':'');}
    async function run(fn){if(busy)return;busy=true;onStateChange();try{await fn();}catch(e){note(e.message,true);}finally{busy=false;onStateChange();}}
    const call=message=>transport.call?transport.call(message):transport.write(message);
    function guarded(){if(pending)throw Error('Сначала завершите или отмените подготовленную операцию.');}
    function cleanLayout(){if(draft)throw Error('Сначала сохраните или отмените изменения раскладки.');}
    function activateDecision(){const api=typeof module==='object'&&module.exports?require('./rdg-decision-ui.js'):globalThis.RDGDecisionUI;if(!api)throw Error('Decision Viewer недоступен.');decisionController??=api.mount(decisionHost,{call,approval:transport.approval},{document:doc,onLegacyOpen:async id=>{decisionMode(false);return open(id);}});decisionMode(true);return decisionController;}
    async function refresh(){if(decisionActive)return decisionController.refresh();guarded();catalog=await call({method:'catalog'});if(!selected&&catalog.packages.some(p=>p.coreModel==='rdg-decision-v1'))return activateDecision().start(catalog);migrationSources=await call({method:'migration_sources'});renderCatalog();if(selected)await open(selected,focus);else renderEmpty();await refreshApprovals();note('Каталог прочитан из фактических папок.');}
    async function open(id,spec={kind:'graph'}){
      guarded();cleanLayout();const current=await call({method:'read',packageId:id,includePlan:true,view:spec});
      if(current.graph.coreModel==='rdg-decision-v1'){
        await activateDecision().open(id,spec);return decisionController.view;
      }
      decisionMode(false);selected=id;focus=spec;view=current;history=null;render();return view;
    }
    async function schema(op,nodeId,extra={}){return (await call({method:'schema',op,packageId:selected,nodeId,...extra})).request;}
    async function prepare(request){
      if(decisionActive)return decisionController.prepare(request);
      guarded();if(request.op!=='layout_edit')cleanLayout();
      const exact=clone(request);
      if(transport.approval&&['lock_set','lock_remove'].includes(exact.op))exact.authorityPrincipal='';
      let result;
      try{result=await call({method:'preflight',request:exact});}
      catch(error){
        if(transport.approval&&error.message.includes('VERIFIED_APPROVAL_REQUIRED')){
          const proposed=await call({method:'approval_request',request:exact,rationale:exact.note});
          await refreshApprovals();await openApproval(proposed.requestId);
          note('Проверьте изменение замка и подтвердите его зарегистрированным ключом.');return;
        }
        throw error;
      }
      pending={request:exact,preview:result,uncertain:false};renderPreview();note('Проверьте последствия и подтвердите сохранение.');
    }
    async function commit(){
      if(decisionActive)return decisionController.commit();
      if(!pending)return;const exact=pending.request;
      try{
        const result=await call({method:'apply',request:exact});
        if(result.published!==true)throw Error('Сохранение не подтверждено. Проверьте receipt.');
        const created=result.packages?.find(r=>r.receipt?.effects?.createdPackageId)?.receipt.effects.createdPackageId;
        const committed=exact.op;pending=null;if(committed==='layout_edit')draft=null;renderPreview();
        catalog=await call({method:'catalog'});migrationSources=await call({method:'migration_sources'});renderCatalog();
        if(created)await open(created);else if(selected)await open(selected,committed==='delete'||committed==='apply_ready'?{kind:'graph'}:focus);
        note('Изменения сохранены. Receipt подтверждён.');return result;
      }catch(e){if(pending)pending.uncertain=e.definite!==true;renderPreview();throw e;}
    }
    function renderPreview(){
      preview.replaceChildren();preview.hidden=!pending;if(!pending)return;
      preview.appendChild(el('h3',pending.uncertain?'Исход операции нужно подтвердить':'Предварительная проверка'));
      preview.appendChild(el('p','Операция: '+pending.request.op+' · '+pending.request.transactionId));
      if(pending.request.data?.cosmetic===true)preview.appendChild(el('p','Косметическая правка: изменение определения не вызывает пересмотр у L1/L2-подписчиков.'));
      const effects=clone(pending.preview.effects||{});
      for(const key of ['graphs','plans'])if(effects[key])effects[key]=Object.fromEntries(Object.entries(effects[key]).map(([id,value])=>[id,{revision:value.revision,entities:value.nodes?.length,placements:value.steps?.length}]));
      json(preview,effects);
      button(preview,pending.uncertain?'Повторить тот же запрос':'Сохранить',commit);
      button(preview,'Отменить подготовку',async()=>{pending=null;renderPreview();note('Подготовка отменена.');},pending.uncertain);
      button(preview,'Прочитать receipt',async()=>{
        const result=await call({method:'receipt',packageId:pending.preview.effects?.createdPackageId||pending.request.targetPackageId||selected,transactionId:pending.request.transactionId});json(preview,result);
      });
    }
    const approvalLabels={pending:'Ожидает решения',rejected:'Отклонено',
      'approved-awaiting-recovery':'Подтверждено · требуется восстановление',
      'executed-approved':'Выполнено после подтверждения','executed-independently':'Выполнено самостоятельно'};
    const approveCall=message=>{
      if(!transport.approval)throw Error('Подтверждение недоступно в этом подключении.');
      return transport.approval(message);
    };
    function approvalError(error){
      if(/CAS_MISMATCH|REVISION_CONFLICT|PIN_CHANGED/.test(error.message))return 'Запрос создан для прежней версии. Инициатор должен подготовить новый запрос.';
      if(/PREVIEW_CHANGED|INCOMING_|REQUEST_CHANGED/.test(error.message))return 'Данные изменились. Обновите изменения и подтвердите их заново.';
      if(/VIEW_UNAVAILABLE|CEREMONY_UNAVAILABLE/.test(error.message))return 'Подтверждение больше не действует. Обновите изменения.';
      if(/CREDENTIAL_UNAVAILABLE|PRINCIPAL_NOT_ENROLLED|BINDING_UNAVAILABLE/.test(error.message))return 'Ключ отозван или недоступен. Для нового ключа требуется приглашение владельца.';
      if(/AUTH_|EXECUTOR_BINDING/.test(error.message))return 'Право исполнения недоступно. Обновите запрос или обратитесь к владельцу прав.';
      return error.message;
    }
    async function refreshApprovals(){
      if(!transport.approval){renderApprovals();return;}
      const result=await approveCall({method:'list'});approvalList=result.requests;enrollment=result.enrollment||null;renderApprovals();
    }
    async function openApproval(requestId){
      guarded();cleanLayout();
      approvalOpening=requestId;approvalCurrent=null;approvalUncertain=false;
      approvalMessage='Открываем запрос…';note(approvalMessage);renderApprovals();
      try{
        approvalCurrent=await approveCall({method:'open',requestId});
        approvalMessage='';note('Запрос открыт. Сравните изменения ниже.');return approvalCurrent;
      }catch(error){
        approvalMessage='Не удалось открыть запрос: '+approvalError(error);throw error;
      }finally{
        approvalOpening=null;renderApprovals();
        if(approvalCurrent)approvals.querySelector?.('[data-approval-current]')?.scrollIntoView?.({block:'nearest',behavior:'smooth'});
      }
    }
    async function approvalStatus(){
      if(!approvalCurrent)return;
      const requestId=approvalCurrent.record.requestId;
      const record=await approveCall({method:'status',requestId});
      approvalCurrent={record,previewAvailable:false,preview:null};
      approvalUncertain=false;renderApprovals();return record;
    }
    async function refreshAfterApproval(){
      catalog=await call({method:'catalog'});renderCatalog();
      await refreshApprovals();
      if(selected)await open(selected,{kind:'graph'});
    }
    async function decideApproval(decision){
      guarded();cleanLayout();
      if(!approvalCurrent?.viewId||approvalUncertain)throw Error('Сначала обновите изменения запроса.');
      approvalWorking=true;approvalMessage='Проверка запроса…';renderApprovals();
      let submitted=false;
      try{
        const begin=await approveCall({method:'choose',viewId:approvalCurrent.viewId,decision});
        approvalMessage='Подтвердите решение средствами браузера.';renderApprovals();
        const response=await (getAssertion||browserAssertion)(begin);
        submitted=true;
        await approveCall({method:'complete',ceremonyId:begin.ceremonyId,response});
        const state=await approvalStatus();
        approvalMessage=state.state==='rejected'?'Запрос отклонён. Предложенные изменения не выполнены.':
          state.state==='executed-approved'?'Подтверждённые изменения выполнены.':
          'Решение сохранено. Прочитайте состояние операции.';
        try{await refreshAfterApproval();}catch(e){approvalMessage+=' Не удалось обновить Graph или список: '+e.message;}
      }catch(error){
        if(submitted){
          approvalUncertain=true;approvalMessage='Ответ исполнения не получен. Проверяется фактическое состояние…';renderApprovals();
          try{
            const state=await approvalStatus();
            approvalMessage=state.state==='executed-approved'?'Изменения выполнены; результат подтверждён чтением состояния.':
              state.state==='approved-awaiting-recovery'?'Операция принята. Завершите восстановление без нового подтверждения.':
              state.state==='rejected'?'Запрос отклонён.':
              approvalError(error)+' Принятие не подтверждено. Обновите изменения перед новым решением.';
            if(state.state==='executed-approved')try{await refreshAfterApproval();}catch(e){approvalMessage+=' Graph нужно перечитать: '+e.message;}
          }catch(_){approvalMessage='Исход исполнения неизвестен. Сначала прочитайте состояние запроса.';}
        }else{
          approvalMessage=['NotAllowedError','AbortError'].includes(error.name)?
            'Подтверждение отменено в браузере. Изменения не отправлены.':approvalError(error);
          approvalCurrent.viewId=null;approvalCurrent.previewAvailable=false;
          approvalCurrent.previewStale=true;
        }
      }finally{approvalWorking=false;renderApprovals();}
    }
    async function recoverApproval(){
      guarded();cleanLayout();
      if(!approvalCurrent||approvalCurrent.record.state!=='approved-awaiting-recovery')throw Error('Нет принятой операции для восстановления.');
      approvalWorking=true;approvalMessage='Завершение ранее принятой операции…';renderApprovals();
      try{
        await approveCall({method:'recover',requestId:approvalCurrent.record.requestId});
        await approvalStatus();approvalMessage='Ранее принятые изменения восстановлены.';
        try{await refreshAfterApproval();}catch(e){approvalMessage+=' Graph нужно перечитать: '+e.message;}
      }catch(e){
        approvalUncertain=true;approvalMessage='Исход восстановления нужно проверить.';
        try{await approvalStatus();}catch(_){/* keep the unknown result visible */}
      }finally{approvalWorking=false;renderApprovals();}
    }
    async function registerCredential(){
      guarded();cleanLayout();approvalWorking=true;enrollmentMessage='Подготовка регистрации…';renderApprovals();
      let submitted=false;
      try{
        const begin=await approveCall({method:'registration_begin'});
        enrollmentMessage='Зарегистрируйте свой ключ средствами браузера.';renderApprovals();
        const response=await browserRegistration(begin);
        submitted=true;
        await approveCall({method:'registration_complete',ceremonyId:begin.ceremonyId,response});
        await refreshApprovals();enrollmentMessage='Ключ зарегистрирован. Привязка сохранена.';
      }catch(error){
        if(submitted){
          try{
            await refreshApprovals();
            enrollmentMessage=enrollment?.state==='completed'?'Ключ зарегистрирован; результат подтверждён чтением состояния.':
              'Регистрация не подтверждена. Проверьте состояние приглашения.';
          }catch(_){enrollmentMessage='Исход регистрации неизвестен. Обновите запросы перед повтором.';}
        }else enrollmentMessage=['NotAllowedError','AbortError'].includes(error.name)?
          'Регистрация отменена в браузере.':approvalError(error);
      }finally{approvalWorking=false;renderApprovals();}
    }
    function renderEnrollment(){
      if(!enrollment)return;
      const box=el('section',null,'rp-enrollment');box.setAttribute('data-enrollment-state',enrollment.state);
      approvals.appendChild(box);
      if(enrollment.state==='completed'){
        box.appendChild(el('strong','Ключ зарегистрирован'));
        box.appendChild(el('span','Можно подтверждать запросы.','rp-request-meta'));
        const account=details(box,'Учётная запись');account.appendChild(el('p',enrollment.displayName+' · '+enrollment.principalId));
        return;
      }
      box.appendChild(el('h3','Регистрация ключа'));
      box.appendChild(el('p','Учётная запись: '+enrollment.displayName+' · '+enrollment.principalId));
      box.appendChild(el('p','Ключ будет связан с существующими правами этой учётной записи.'));
      if(enrollmentMessage){const message=el('p',enrollmentMessage);message.setAttribute('role','status');box.appendChild(message);}
      if(['issued','started'].includes(enrollment.state)){
        box.appendChild(el('p','Приглашение на регистрацию подготовлено владельцем Authority.'));
        button(box,'Зарегистрировать ключ',registerCredential,approvalWorking||!globalThis.isSecureContext||!globalThis.navigator?.credentials?.create);
      }else box.appendChild(el('p',enrollment.state==='completed'?'Ключ зарегистрирован.':
        enrollment.state==='revoked'?'Ключ отозван. Для нового ключа нужно новое приглашение владельца.':
        'Приглашение больше не действует. Требуется новое приглашение владельца.'));
    }
    function operationLabel(request){
      const operation=request.command||request.op,target=request.data?.nodeId||request.nodeId;
      const labels={edit:'Изменить блок',lock_set:'Установить замок',lock_remove:'Снять замок',
        delete:'Удалить блок',select:'Выбрать Action',review:'Подтвердить пересмотр',
        complete:'Подтвердить результат',dependency_add:'Добавить зависимость',dependency_remove:'Снять зависимость'};
      return (labels[operation]||operation)+(target?' · '+target:'')+(request.data?.cosmetic===true?' · Косметическая правка':'');
    }
    function requestTitle(item){
      return catalog?.packages?.find(row=>row.packageId===item.targetPackageId)?.title||operationLabel(item.request);
    }
    function renderApprovals(){
      approvals.replaceChildren();
      const header=el('div',null,'rp-approval-header');approvals.appendChild(header);
      const waiting=approvalList?.filter(item=>item.state==='pending').length;
      header.appendChild(el('h3','Запросы подтверждения'+(waiting!=null?' · '+waiting+' ожидают решения':'')));
      if(!transport.approval){approvals.appendChild(el('p','Подтверждение недоступно в этом подключении.'));return;}
      button(header,'Обновить запросы',refreshApprovals,approvalWorking||!!approvalOpening);renderEnrollment();
      if(approvalList===null)approvals.appendChild(el('p','Список ещё не прочитан.'));
      else if(!approvalList.length)approvals.appendChild(el('p','Доступных запросов нет.'));
      else{
        approvals.appendChild(el('p','Выберите запрос, чтобы сравнить «Было / Станет» и принять решение.','rp-request-meta'));
        const list=el('div',null,'rp-approval-list');approvals.appendChild(list);
        for(const item of approvalList){
          const b=button(list,'',()=>openApproval(item.requestId),approvalWorking||!!approvalOpening);
          b.className='rp-request';b.setAttribute('data-approval-request',item.requestId);
          b.setAttribute('aria-pressed',String((approvalOpening||approvalCurrent?.record.requestId)===item.requestId));
          b.appendChild(el('span',approvalOpening===item.requestId?'Открываем…':approvalLabels[item.state]||item.state,'rp-badge'));
          b.appendChild(el('strong',requestTitle(item)));
          b.appendChild(el('span',operationLabel(item.request),'rp-request-meta'));
          b.appendChild(el('span',item.rationale,'rp-request-summary'));
        }
      }
      if(approvalMessage){const message=el('p',approvalMessage,'rp-approval-status');message.setAttribute('role','status');approvals.appendChild(message);}
      if(!approvalCurrent)return;
      const value=approvalCurrent.record,card=el('article',null,'rp-card rp-selected-request');
      card.setAttribute('data-approval-current',value.requestId);approvals.appendChild(card);
      card.appendChild(el('span',approvalLabels[value.state]||value.state,'rp-badge'));
      card.appendChild(el('h3',operationLabel(value.request)));
      card.appendChild(el('p',value.rationale));
      const metadata=details(card,'Сведения о запросе');
      metadata.appendChild(el('p','Запрос: '+value.requestId));
      metadata.appendChild(el('p','Пакет: '+value.targetPackageId+' · инициатор: '+value.initiator.grantId));
      if(approvalUncertain)card.appendChild(el('p','Результат пока неизвестен. Новое решение заблокировано.','rp-error'));
      if(approvalCurrent.previewStale)card.appendChild(el('p','Показанные изменения больше не разрешают исполнение. Обновите карточку.','rp-stale'));
      const shown=approvalCurrent.preview;
      if(shown){
        card.appendChild(el('p','Затронутых пакетов: '+shown.owners.length,'rp-request-meta'));
        for(const owner of shown.owners){
          const box=el('section',null,'rp-card');box.setAttribute('data-approval-owner',owner.packageId);card.appendChild(box);
          box.appendChild(el('h3',owner.before?.graph?.title||owner.after.graph?.title||owner.path));
          box.appendChild(el('p',owner.path,'rp-request-meta'));
          const table=el('table',null,'rp-diff'),head=el('tr');
          for(const text of ['Поле','Было','Станет'])head.appendChild(el('th',text));
          table.appendChild(head);
          const rows=diffRows(owner.before,owner.after),audit=rows.filter(r=>/^graph\.events(?:\[|\s|$)/.test(r.path)||/(^|\.)revision$/.test(r.path));
          const material=rows.filter(r=>!audit.includes(r)).sort((a,b)=>{
            const rank=r=>/\.(title|description|scope)$/.test(r.path)?0:/\.review$/.test(r.path)?2:1;
            return rank(a)-rank(b)||a.path.localeCompare(b.path);
          });
          for(const row of material){
            const label=row.path.replace(/^graph\.nodes/,'Блоки').replace(/^graph\.objects/,'Объекты').replace(/^graph\.edges/,'Связи')
              .replace(/\.title$/,' · Название').replace(/\.description$/,' · Описание').replace(/\.scope$/,' · Область').replace(/\.review$/,' · Пересмотр');
            const tr=el('tr');tr.appendChild(el('td',label));
            for(const value of [row.before,row.after]){
              const cell=el('td');
              if(/\.review$/.test(row.path)&&value&&typeof value.required==='boolean'){
                cell.appendChild(el('p',value.required?'Требуется пересмотр.':'Пересмотр не требуется.'));json(details(cell,'Основания'),value);
              }else cell.appendChild(el('pre',value===undefined?'Отсутствует':typeof value==='string'?value:JSON.stringify(value,null,2)));
              tr.appendChild(cell);
            }
            table.appendChild(tr);
          }
          if(material.length)box.appendChild(table);
          for(const kind of ['graph','plan','layouts'])if(owner.after[kind]?.revision!=null)box.appendChild(el('p','Версия '+kind+': '+(owner.before?.[kind]?.revision??'нет')+' → '+owner.after[kind].revision));
          if(audit.length){
            const added=(owner.after.graph?.events?.length||0)-(owner.before?.graph?.events?.length||0);
            if(added>0)box.appendChild(el('p','В историю будет добавлено записей: '+added+'.'));
            const technical=details(box,'Записи истории и служебные версии');technical.setAttribute('data-approval-audit','');json(technical,audit);
          }
          if(owner.artifacts.length){box.appendChild(el('p','Добавляемые файлы:'));json(box,owner.artifacts);}
        }
        const full=details(card,'Все согласуемые данные');json(full,shown);
      }else if(value.state==='pending'){
        card.appendChild(el('p','Полный просмотр изменений недоступен. Подтверждение выполнения заблокировано.','rp-stale'));
        if(/CAS_MISMATCH|REVISION_CONFLICT|PIN_CHANGED/.test(approvalCurrent.blocker||''))card.appendChild(el('p','Запрос создан для прежней версии. Инициатор должен подготовить новый запрос.','rp-stale'));
        if(approvalCurrent.blocker)json(details(card,'Причина недоступности'),{error:approvalCurrent.blocker});
      }
      const request=details(card,'Точное тело запроса');json(request,value.request);
      if(value.authorizationContext)json(details(card,'Инициатор, подтвердивший и исполнитель'),value.authorizationContext);
      const canSign=getAssertion!==null||!!globalThis.navigator?.credentials?.get&&globalThis.isSecureContext;
      if(value.state==='pending'){
        if(!canSign)card.appendChild(el('p','В этом браузере или по этому адресу WebAuthn недоступен.','rp-stale'));
        button(card,'Подтвердить',()=>decideApproval('approve'),approvalWorking||approvalUncertain||!canSign||!approvalCurrent.previewAvailable||!approvalCurrent.viewId);
        button(card,'Отклонить',()=>decideApproval('reject'),approvalWorking||approvalUncertain||!canSign||!approvalCurrent.viewId);
        button(card,'Обновить изменения',()=>openApproval(value.requestId),approvalWorking||approvalUncertain);
      }
      button(card,'Прочитать состояние',async()=>{try{await approvalStatus();approvalMessage='Состояние перечитано.';}catch(e){approvalMessage=approvalError(e);}renderApprovals();},approvalWorking);
      if(value.state==='approved-awaiting-recovery')button(card,'Завершить принятую операцию',recoverApproval,approvalWorking||approvalUncertain);
    }
    function renderCatalog(){
      aside.replaceChildren();aside.appendChild(el('h3','Папки и Graph'));
      const folders=new Map([['',aside]]);
      function folder(path){
        if(folders.has(path))return folders.get(path);
        const parts=path.split('/'),name=parts.pop(),parent=folder(parts.join('/'));
        const box=details(parent,name);box.open=true;folders.set(path,box);return box;
      }
      for(const row of catalog?.folders||[])folder(row.path);
      const stages=(catalog?.packages||[]).filter(r=>r.health==='unaccepted-stage');
      const stageBox=stages.length?details(aside,'Непринятые операции · '+stages.length):null;
      for(const row of catalog?.packages||[]){
        const parent=folder(row.path.split('/').slice(0,-1).join('/'));
        const b=button(row.health==='unaccepted-stage'?stageBox:parent,(names[row.role]||'Пакет')+' · '+(row.title||row.packageId||row.path),()=>open(row.packageId));
        b.setAttribute('data-package-id',row.packageId||'');
        b.appendChild(el('small',row.path+(row.lensKey?' · lensKey: '+row.lensKey:'')));
        if(row.health!=='metadata-verified')b.appendChild(el('small',row.error||row.health,'rp-error'));
      }
    }
    function renderEmpty(){main.replaceChildren();main.appendChild(el('p','Выберите пакет или создайте Graph.'));createForm(main);}
    function createForm(parent){
      const form=details(parent,'Создать Graph');const role=select(form,'Назначение',Object.entries(names).filter(([k])=>k!=='copy'));
      const profile=select(form,'Модель',[['rdg-core-v1','R / Action'],['rdg-decision-v1','R / Decision / Action']]);
      const reason=field(form,'Основание процесса');
      const path=field(form,'Папка относительно корня пакетов'),title=field(form,'Название и корневая R'),scope=field(form,'Область применения'),lens=field(form,'lensKey для линзы');
      button(form,'Проверить создание',async()=>{
        const request=(await call({method:'schema',op:'create'})).request;Object.assign(request,{role:role.value,path:path.value,title:title.value,scope:scope.value,coreModel:profile.value});
        if(profile.value==='rdg-decision-v1')request.rootReason=reason.value;
        if(role.value==='lens')request.lensKey=lens.value;await prepare(request);
      });
      const folders=details(parent,'Папки');
      for(const row of catalog?.folders||[])folders.appendChild(el('p',row.path));
      const destination=field(folders,'Новая папка'),source=field(folders,'Текущая папка для переноса');
      button(folders,'Проверить создание папки',async()=>{const request=(await call({method:'schema',op:'folder_create'})).request;request.path=destination.value;await prepare(request);});
      button(folders,'Проверить перенос папки',async()=>{const request=(await call({method:'schema',op:'folder_move',sourcePath:source.value})).request;request.path=destination.value;await prepare(request);});
      const recovery=field(folders,'ID уже принятой операции');
      button(folders,'Завершить принятую операцию',async()=>{guarded();cleanLayout();await call({method:'recover',transactionId:recovery.value.trim()});await refresh();});
      button(folders,'Снять блокировку непринятой миграции',async()=>{guarded();cleanLayout();await call({method:'cancel_migration',transactionId:recovery.value.trim()});await refresh();});
      if(migrationSources?.sources?.some(s=>!s.route)){
        const migration=details(parent,'Перенести прежний owner в пакет');
        const sources=select(migration,'Источник',migrationSources.sources.filter(s=>!s.route).map(s=>[s.sourceKey,s.sourceKey+' · '+s.graphFile]));
        const path=field(migration,'Папка нового пакета');
        const switchOwner=field(migration,'Переключить owner и запретить прежнюю запись',false,'checkbox');
        const quiesced=field(migration,'Прежние Helper и writers остановлены',false,'checkbox');
        const complete=field(migration,'Все сохранённые раскладки включены',false,'checkbox');
        const paused=field(migration,'Запись раскладок приостановлена',false,'checkbox');
        const gaps=field(migration,'Прочитал и принимаю ограничения исторических доказательств',false,'checkbox');
        button(migration,'Прочитать preflight источника',async()=>json(migration,await call({method:'migration_inspect',sourceKey:sources.value})));
        button(migration,'Проверить переключение owner',async()=>{
          const request=(await call({method:'schema',op:'migrate',sourceKey:sources.value})).request;
          Object.assign(request,{path:path.value,confirmOwnerSwitch:switchOwner.checked,legacyWritersQuiesced:quiesced.checked,presentationSourcesComplete:complete.checked,
            presentationWritersPaused:paused.checked,acknowledgeHistoricalGaps:gaps.checked});await prepare(request);
        });
      }
    }
    function render(){
      main.replaceChildren();bar.replaceChildren();button(bar,'Обновить каталог',refresh);button(bar,'Все пакеты',async()=>{guarded();cleanLayout();selected=null;view=null;renderEmpty();});
      main.appendChild(el('h2',view.graph.title));main.appendChild(el('p',(names[view.package.role]||view.package.role)+' · '+view.path));
      const work=view.package.role==='working'||view.package.role==='copy';
      const choices=[['graph','Весь Graph'],...view.graph.workGraphs.map(w=>['workGraph:'+w.id,'Область: '+w.title]),
        ...[...view.graph.nodes,...view.graph.objects,...(view.graph.externalActions||[])].map(n=>['focus:'+n.id,n.kind+' · '+n.title])];
      const picker=select(main,'Представление',choices,focus.kind==='graph'?'graph':focus.kind+':'+focus.id);
      picker.onchange=()=>run(()=>{const [kind,...id]=picker.value.split(':');return open(selected,kind==='graph'?{kind}:{kind,id:id.join(':')});});
      if(lensReturn&&view.package.role==='lens')button(bar,'К процессу',async()=>{const target=lensReturn;lensReturn=null;await open(target.id,target.spec);});
      if(work)for(const lens of (catalog?.packages||[]).filter(r=>r.role==='lens'))button(bar,'Открыть линзу · '+lens.title,async()=>{
        const definition=await call({method:'read',packageId:lens.packageId});
        if(definition.graph.coreModel!==view.graph.coreModel)throw Error('Линза не поддерживает модель этого процесса');
        lensReturn={id:selected,spec:clone(focus)};await open(lens.packageId);
      });
      if(view.graph.coreModel==='rdg-decision-v1'){
        for(const g of view.view.decisionGroups||[])main.appendChild(el('p',g.title+' · '+g.parentId+' · '+g.members.map(m=>m.decisionId).join(', ')+
          (g.selectionRequired?' · выбор необходим':' · выбор необязателен')+(g.mutuallyExclusive?' · взаимоисключение':'')));
        if(view.view.externalAction){const info=details(main,'Внешний Action');info.open=true;json(info,view.view.externalAction);}
      }
      draw(main);renderDetached(main);renderReferences(main);renderOperations(main,work);
      if(work){renderPlan(main);const historyBox=details(main,'История Graph и версии Plan');
        button(historyBox,'Прочитать историю',async()=>{history=await call({method:'history',packageId:selected});renderHistory(historyBox,history);});}
      createForm(main);
    }
    function draw(parent,snapshot=view,{readOnly=false,onOpen=null}={}){
      const box=el('section',null,'rp-card'),tools=el('div',null,'rp-graph-tools');
      parent.appendChild(box);box.appendChild(tools);
      const key=snapshot.view.graphKey,saved=snapshot.layouts?.layouts?.[key]||{};
      const active=!readOnly&&draft?.key===key?draft:null;
      const positions=clone(active?.positions||saved.positions||{});
      const occurrences=clone(active?.occurrences||saved.occurrences||{});
      const nodes=snapshot.view.entities;
      for(const canon of nodes.filter(n=>n.kind==='canon'&&n.evaluationMode==='comment-only-v1')){
        const comment=details(box,'Комментарий канона · '+canon.title);comment.open=snapshot.view.spec.kind==='focus';
        comment.appendChild(el('p',canon.comment));
      }
      nodes.forEach((n,i)=>{positions[n.id]??={x:30+(i%3)*235,y:30+Math.floor(i/3)*115};});
      const projection=(typeof module==='object'&&module.exports?require('./rdg-visual-projection.js'):globalThis.RDGVisualProjection);
      const allEntities=[...snapshot.graph.nodes,...snapshot.graph.objects];
      const allEdges=snapshot.graph.edges.filter(e=>!e.archived).concat(snapshot.view.decisionMemberships||[]);
      const picture=projection.project(nodes,snapshot.view.edges.concat((snapshot.view.decisionMemberships||[]).filter(m=>!snapshot.view.edges.some(e=>e.id===m.id))),positions,occurrences,
        {externalEntities:allEntities,externalEdges:allEdges});
      const external=snapshot.view.spec.kind==='workGraph'?projection.boundaries(
        allEntities,allEdges,nodes.map(n=>n.id)):[];
      const exteriorNodes=new Map(allEntities.map(n=>[n.id,n]));
      const renderedBoundary=new Set(picture.routes.map(r=>r.edge.id));
      const ports=external.filter(e=>!renderedBoundary.has(e.edge.id)).slice(0,100).map((item,i)=>{
        const base=positions[item.inside]||{x:30,y:30};
        return {...item,x:base.x+(item.direction==='out'?265:-190),y:base.y+(i%5)*23};
      });
      const ns='http://www.w3.org/2000/svg',svg=doc.createElementNS(ns,'svg');box.appendChild(svg);
      const points=[...picture.nodes.map(n=>n.position).filter(Boolean),...ports];
      const maxX=Math.max(500,...points.map(p=>p.x+230)),maxY=Math.max(280,...points.map(p=>p.y+110));
      const minX=Math.min(0,...points.map(p=>p.x-10)),minY=Math.min(0,...points.map(p=>p.y-10));
      svg.setAttribute('viewBox',[minX,minY,maxX-minX,maxY-minY].join(' '));
      svg.setAttribute('aria-label','Граф: '+snapshot.graph.title);
      const append=(tag,attrs,text)=>{const n=doc.createElementNS(ns,tag);
        for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));
        if(text!=null)n.textContent=text;svg.appendChild(n);return n;};
      const edgeVisuals=[];
      for(const route of picture.routes)edgeVisuals.push([route,
        append('line',{stroke:'#8bb5cc','stroke-width':1.5}),
        append('text',{'text-anchor':'middle'},route.edge.type+' →')]);
      const visualPosition=id=>occurrences[id]||positions[id];
      function paintEdges(){for(const [route,line,text] of edgeVisuals){
        const a=visualPosition(route.from),b=visualPosition(route.to);if(!a||!b)continue;
        for(const [k,v] of Object.entries({x1:a.x+100,y1:a.y+38,x2:b.x+100,y2:b.y+38}))
          line.setAttribute(k,String(v));
        text.setAttribute('x',String((a.x+b.x)/2+100));
        text.setAttribute('y',String((a.y+b.y)/2+29));
      }}
      paintEdges();
      for(const item of ports){
        const inside=positions[item.inside];if(!inside)continue;
        const anchorX=item.x+65,anchorY=item.y+8;
        append('line',{x1:inside.x+100,y1:inside.y+38,x2:anchorX,y2:anchorY,
          stroke:'#7892a5','stroke-width':1,'stroke-dasharray':'5 5'});
        const externalNode=exteriorNodes.get(item.outside);
        const port=append('text',{x: item.x,y:item.y,'aria-label':'Вне WorkGraph: '+(externalNode?.title||item.outside)},
          '↗ '+item.edge.type+' · '+(externalNode?.title||item.outside).slice(0,23));
        port.setAttribute('role','button');port.setAttribute('tabindex','0');port.style.pointerEvents='auto';
        const openPort=()=>readOnly?onOpen?.(item.outside):open(selected,{kind:'focus',id:item.outside});
        port.ondblclick=()=>run(openPort);
        port.onkeydown=e=>{if(e.key==='Enter')void run(openPort);};
      }
      if(picture.invalid.length)box.appendChild(el('p',
        'Есть недействительные визуальные ссылки: '+picture.invalid.map(v=>v.id).join(', '),'rp-error'));
      const editable=()=>!readOnly&&!pending&&!busy;
      const changed=()=>{draft={key,positions,occurrences};note('Раскладка изменена. Сохраните её перед copy или переходом.');};
      const change=fn=>{if(readOnly||pending)return;fn();changed();render();};
      const idFactory=()=> 'occ-'+(globalThis.crypto?.randomUUID?.()||String(Date.now())+'-'+Math.random().toString(36).slice(2));
      const focusNode=n=>readOnly?onOpen?.(n.entityId):open(selected,{kind:'focus',id:n.entityId});
      const groups=[];
      for(const n of picture.nodes){
        const p=visualPosition(n.id);if(!p)continue;
        const state=snapshot.completion[n.entityId]||{};
        const group=doc.createElementNS(ns,'g');
        group.setAttribute('transform',`translate(${p.x},${p.y})`);
        group.setAttribute('class','rp-node');
        group.setAttribute('data-entity-id',n.entityId);
        group.setAttribute('data-occurrence-id',n.id);
        group.setAttribute('tabindex','0');group.setAttribute('role','button');
        const repeated=(picture.counts.get(n.entityId)||0)>1;
        const isOutside=snapshot.view.spec.kind==='workGraph'&&!nodes.some(entity=>entity.id===n.entityId);
        const label=n.node.title+(repeated?' · визуально повторён':'')+(isOutside?' · вне WorkGraph':'');
        group.setAttribute('aria-label',label);svg.appendChild(group);groups.push(group);
        if(repeated){const title=doc.createElementNS(ns,'title');title.textContent='Та же R/A показана в других местах этого вида';group.appendChild(title);}
        const rect=doc.createElementNS(ns,'rect');
        for(const [k,v] of Object.entries({width:205,height:80,rx:9,fill:n.node.kind==='requirement'?'#1c4a60':'#314d63',
          stroke:state.reviewRequired?'#ffc179':'#9fbed0','stroke-width':state.reviewRequired?3:1.5,
          ...(isOutside?{'stroke-dasharray':'5 4'}:{})}))
          rect.setAttribute(k,String(v));group.appendChild(rect);
        for(const [i,line] of [[n.node.kind,n.node.selectionState||n.node.status].filter(Boolean).join(' · '),
          n.node.title.length>27?n.node.title.slice(0,26)+'…':n.node.title,
          state.reviewRequired?'Нужна проверка':state.complete?'Подтверждено':n.entityId.slice(0,24)].entries()){
          const t=doc.createElementNS(ns,'text');t.setAttribute('x','10');t.setAttribute('y',String(20+i*22));
          t.textContent=line;group.appendChild(t);
        }
        if(repeated){const mark=doc.createElementNS(ns,'text');mark.setAttribute('x','186');mark.setAttribute('y','18');mark.setAttribute('aria-hidden','true');mark.textContent='⧉';group.appendChild(mark);}
        const choose=()=>focusNode(n);
        group.ondblclick=()=>run(choose);group.onkeydown=e=>{if(e.key==='Enter')void run(choose);};
        group.onclick=()=>{for(const item of groups)
          item.setAttribute('opacity',item.getAttribute('data-entity-id')===n.entityId?'1':'0.5');};
        let drag=null;
        group.onpointerdown=e=>{if(!editable())return;
          drag={x:e.clientX,y:e.clientY,original:{...visualPosition(n.id)},moved:false};group.setPointerCapture?.(e.pointerId);};
        group.onpointermove=e=>{if(!drag)return;const bounds=svg.getBoundingClientRect();
          const x=drag.original.x+(e.clientX-drag.x)*(maxX-minX)/bounds.width,
            y=drag.original.y+(e.clientY-drag.y)*(maxY-minY)/bounds.height;
          drag.moved ||= Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y)>3;
          if(drag.moved){
            if(n.alias)Object.assign(occurrences[n.id],{x,y});else positions[n.id]={x,y};
            draft={key,positions,occurrences};group.setAttribute('transform',`translate(${x},${y})`);paintEdges();
          }};
        group.onpointerup=()=>{if(drag?.moved)changed();drag=null;};
        button(tools,n.node.title,choose);
      }
      if(ports.length){
        const boundary=details(tools,'Связи за пределами WorkGraph · '+external.length);
        for(const item of external){
          const text=item.edge.type+' · '+(item.direction==='in'?'из':'к')+' '+(exteriorNodes.get(item.outside)?.title||item.outside);
          button(boundary,text,()=>readOnly?onOpen?.(item.outside):open(selected,{kind:'focus',id:item.outside}));
          if(!readOnly)button(boundary,'Показать внешнюю R/A здесь · '+item.outside,()=>change(()=>{
            const outside=exteriorNodes.get(item.outside);
            if(!outside||!['requirement','action'].includes(outside.kind))return;
            const anchor=positions[item.inside]||{x:30,y:30},id=idFactory();
            occurrences[id]={entityId:item.outside,x:anchor.x+235,y:anchor.y+35,parentId:item.inside,
              viaEdgeId:item.edge.id,...(item.direction==='in'?{reverse:true}:{})};
          }));
        }
      }
      if(!readOnly&&snapshot.graph.coreModel!=='rdg-decision-v1'){
        const controls=details(tools,'Визуальные повторы R/A');
        controls.appendChild(el('p','Повторяются только изображения. Identity, связи, история и Plan общие.'));
        if(picture.invalid.length)button(controls,'Убрать недействительные визуальные ссылки',()=>change(()=>{
          const removal=new Set(picture.invalid.map(row=>row.id));let changed=true;
          while(changed){changed=false;for(const [id,o] of Object.entries(occurrences))
            if(o.parentId&&removal.has(o.parentId)&&!removal.has(id)){removal.add(id);changed=true;}}
          for(const id of removal)delete occurrences[id];
        }));
        const choices=picture.nodes.filter(n=>['action','requirement'].includes(n.node.kind))
          .map(n=>[n.id,(n.alias?'⧉ ':'')+n.node.title+' · '+n.id]);
        if(choices.length){
          const pick=select(controls,'Блок или визуальное вхождение',choices);
          button(controls,'Повторить только блок',()=>change(()=>{
            const src=picture.nodes.find(n=>n.id===pick.value),pos=visualPosition(src.id);
            const id=idFactory();occurrences[id]={entityId:src.entityId,x:pos.x+245,y:pos.y+45};
          }));
          for(const [label,depth] of [['Повторить ветвь · 1 уровень',1],['Повторить ветвь · 2 уровня',2],
            ['Раскрыть здесь следующий уровень',0]]){
            button(controls,label,()=>change(()=>{
              const result=projection.addBranch(allEntities,allEdges,positions,occurrences,pick.value,depth||1,idFactory,{duplicateRoot:depth!==0});
              Object.assign(occurrences,result.occurrences);
            }));
          }
          const removeButton=button(controls,'Убрать только это изображение',()=>change(()=>{
            if(!Object.hasOwn(occurrences,pick.value))throw Error('Основное изображение нельзя убрать');
            const removal=new Set([pick.value]);let changed=true;
            while(changed){changed=false;for(const [id,o] of Object.entries(occurrences))
              if(o.parentId&&removal.has(o.parentId)&&!removal.has(id)){removal.add(id);changed=true;}}
            for(const id of removal)delete occurrences[id];
          }),!Object.hasOwn(occurrences,pick.value));
          pick.onchange=()=>{removeButton.disabled=!Object.hasOwn(occurrences,pick.value);};
          button(controls,'Показать Context/Canon и сведения здесь',()=>change(()=>{
            const result=projection.addBranch(allEntities,allEdges,positions,occurrences,
              pick.value,1,idFactory,{duplicateRoot:false,includeCompanions:true,onlyCompanions:true});
            Object.assign(occurrences,result.occurrences);
          }));
          button(controls,'Свернуть визуальное продолжение здесь',()=>change(()=>{
            const removal=new Set();let progress=true;
            while(progress){progress=false;for(const [id,o] of Object.entries(occurrences))
              if(o.parentId&&(o.parentId===pick.value||removal.has(o.parentId))&&!removal.has(id)){
                removal.add(id);progress=true;
              }}
            for(const id of removal)delete occurrences[id];
          }));
          button(controls,'Разместить общие блоки возле остальных входящих R/A',()=>change(()=>{
            const inbound=new Map();
            for(const e of snapshot.view.edges.filter(e=>['DRIVES','INTRODUCES','DERIVES'].includes(e.type))){
              const list=inbound.get(e.to)||[];list.push(e);inbound.set(e.to,list);
            }
            for(const list of inbound.values())if(list.length>1){
              for(const e of list.slice(1)){
                if(Object.values(occurrences).some(o=>o.viaEdgeId===e.id))continue;
                const parent=positions[e.from];if(!parent)continue;
                const id=idFactory();occurrences[id]={entityId:e.to,x:parent.x+235,y:parent.y+15,parentId:e.from,viaEdgeId:e.id};
              }
            }
          }));
        }
      }
      if(!readOnly){
        button(tools,'Сохранить раскладку',async()=>{
          const request=await schema('layout_edit');
          request.commands=[{type:'set_positions',graphKey:key,positions},{type:'set_occurrences',graphKey:key,occurrences}];
          await prepare(request);
        });
        button(tools,'Отменить изменения раскладки',async()=>{draft=null;render();});
      }
    }
    function renderDetached(parent){
      const box=details(parent,'Отрезанные графы · '+view.detached.length);
      box.appendChild(el('p','Эти блоки принадлежат этому Graph. Выбор и необходимость проверки сохранены.'));
      for(const component of view.detached){const card=el('div',null,'rp-card');box.appendChild(card);
        card.appendChild(el('p',component.reviewIds.length?'Нужна проверка':'Отрезанный компонент',component.reviewIds.length?'rp-stale':null));
        for(const id of component.memberIds){const n=[...view.graph.nodes,...view.graph.objects].find(n=>n.id===id);button(card,n?.title||id,()=>open(selected,{kind:'focus',id}));}}
    }
    async function historicalGraph(parent,pin,spec={kind:'graph'}){
      const snapshot=await call({method:'source_snapshot',packageId:selected,pin,view:spec});
      const box=details(parent,'Сохранённый Graph · версия '+pin.graphRevision);box.open=true;
      box.appendChild(el('p',snapshot.graph.title+' · только чтение'));
      draw(box,snapshot,{readOnly:true,onOpen:id=>historicalGraph(box,pin,{kind:'focus',id})});
    }
    function renderReferences(parent){
      const box=details(parent,'Внешние зависимости и ссылки · '+view.external.states.length);
      for(const state of view.external.states){const card=el('div',null,'rp-card');box.appendChild(card);
        card.appendChild(el('p',state.relation.type+' · '+state.direction+' · '+state.target.nodeId));
        card.appendChild(el('p',state.resolved.status+(state.reviewRequired?' · нужна проверка':''),state.reviewRequired?'rp-stale':null));
        button(card,'Открыть исходный Graph',()=>open(state.target.packageId,{kind:'focus',id:state.target.nodeId}));
        button(card,'Открыть сохранённый Graph',()=>historicalGraph(card,Object.fromEntries(['packageId','identitySpace','graphRevision','sha256'].map(k=>[k,state.target[k]]))));
        button(card,'Прочитать сохранённую ссылку',async()=>json(card,await call({method:'resolve',packageId:selected,reference:state.target})));
        button(card,'Принять текущую версию ссылки',async()=>{
          const source=await call({method:'read',packageId:state.target.packageId});
          const n=[...source.graph.nodes,...source.graph.objects].find(n=>n.id===state.target.nodeId);if(!n)throw Error('В текущем исходнике этого блока нет. Выберите новую связь или удалите прежнюю.');
          const request=await schema('external_edit');request.referenceId=state.referenceId;
          request.target=source.references[n.id];
          request.note='Проверена текущая версия внешнего блока';await prepare(request);
        });
        const alternatives=select(card,'Переназначить на Graph',(catalog?.packages||[]).filter(r=>r.packageId).map(r=>[r.packageId,r.title||r.path]),state.target.packageId);
        const endpoint=field(card,'ID блока в выбранном Graph',state.target.nodeId),reason=field(card,'Основание изменения ссылки');
        button(card,'Проверить новую связь',async()=>{
          const source=await call({method:'read',packageId:alternatives.value});
          if(!source.references[endpoint.value])throw Error('В выбранном Graph нет этого блока.');
          const request=await schema('external_edit');request.referenceId=state.referenceId;request.target=source.references[endpoint.value];request.note=reason.value;await prepare(request);
        });
        button(card,'Убрать внешнюю связь',async()=>{const request=await schema('external_edit');request.referenceId=state.referenceId;delete request.target;request.remove=true;request.note=reason.value;await prepare(request);});
      }
    }
    function renderOperations(parent,work){
      if(view.graph.coreModel==='rdg-decision-v1')return renderDecisionOperations(parent,work);
      const box=details(parent,'Изменить Graph');const entities=[...view.graph.nodes,...view.graph.objects];
      const focusId=focus.kind==='focus'?focus.id:view.graph.rootRequirementId||view.graph.fragmentFocus?.id;
      const node=entities.find(n=>n.id===focusId),noteInput=field(box,'Основание изменения','','textarea');
      const kind=select(box,'Новый блок',[['action','Action'],['requirement','Requirement'],['context','Context'],['canon','Канон'],['info','Информация']]);
      const title=field(box,'Название'),description=field(box,'Описание','','textarea'),scope=field(box,'Область R');
      const cosmetic=node?field(box,'Косметическая правка: не требовать пересмотра у L1/L2-подписчиков из-за изменения определения.','','checkbox'):null;
      const comment=field(box,'Комментарий канона',node?.kind==='canon'?node.comment||'':'','textarea');
      const migrate=node?.kind==='canon'&&node.evaluationMode!=='comment-only-v1'?field(box,'Преобразовать выбранный канон в свободный комментарий'):null;
      if(migrate){migrate.type='checkbox';box.appendChild(el('p','Прежние условия сохранятся в истории; изменение будет показано перед записью.'));}
      button(box,'Добавить блок',async()=>{
        const request=await schema(work?'core':'paper_edit',focusId,{command:'add'});const id=(globalThis.crypto?.randomUUID?.()||String(Date.now())+Math.random()).replaceAll('.','');
        const entity={id,kind:kind.value,title:title.value,description:description.value};
        if(kind.value==='requirement')entity.scope=scope.value;
        if(kind.value==='canon')Object.assign(entity,{evaluationMode:'comment-only-v1',comment:comment.value,arguments:[]});
        request.data={entity,workGraphId:view.graph.workGraphs.find(w=>w.memberIds.includes(focusId))?.id||view.graph.workGraphs[0]?.id};request.note=noteInput.value;await prepare(request);
      });
      if(node){button(box,'Изменить выбранный блок',async()=>{const request=await schema(work?'core':'paper_edit',node.id,{command:'edit'});
        request.data={nodeId:node.id,changes:{title:title.value||node.title,description:description.value,
          ...(node.kind==='canon'&&(node.evaluationMode==='comment-only-v1'||migrate?.checked)?{comment:comment.value}:{}),
          ...(migrate?.checked?{evaluationMode:'comment-only-v1',arguments:[]}:{})},
          ...(migrate?.checked?{legacyCanonMigrationAcknowledged:true}:{}),
           ...(cosmetic?.checked?{cosmetic:true}:{})};
        request.note=noteInput.value;await prepare(request);});
        if(work){for(const [command,label] of [['select','Выбрать Action'],['review','Подтвердить пересмотр']])button(box,label,async()=>{const request=await schema('core',node.id,{command});request.note=noteInput.value;await prepare(request);},command==='select'&&node.kind!=='action');}
        if(work)button(box,'Убрать блок из Graph',async()=>{const request=await schema('delete',node.id);request.note=noteInput.value;await prepare(request);});}
      const from=select(box,'От',entities.map(n=>[n.id,n.kind+' · '+n.title]));
      const relation=select(box,'Связь',['DRIVES','DERIVES','INTRODUCES','RELATES_R','CONTEXT_FOR','CANON_FOR','INFO_FOR','DEPENDS_ON'].map(x=>[x,x]));
      const to=select(box,'К',entities.map(n=>[n.id,n.kind+' · '+n.title]));
      button(box,'Добавить связь',async()=>{const request=await schema(work?'core':'paper_edit',focusId,{command:'link'});request.data={edge:{id:globalThis.crypto.randomUUID(),type:relation.value,from:from.value,to:to.value,...(relation.value==='INTRODUCES'?{origin:{role:'method_correctness'}}:{})}};request.note=noteInput.value;await prepare(request);});
      if(work){
        const native=details(parent,'Нативные зависимости L1/L2');
        const dependencySources=entities.filter(n=>['requirement','action','context','info'].includes(n.kind));
        const dependencyTargets=entities.filter(n=>['requirement','action','context'].includes(n.kind));
        const dependencySource=select(native,'Источник',dependencySources.map(n=>[n.id,n.kind+' · '+n.title]),focusId);
        const dependencyTarget=select(native,'Зависимый блок',dependencyTargets.map(n=>[n.id,n.kind+' · '+n.title]),focusId);
        const dependencyLevel=select(native,'Уровень',[['L1','L1 · собственное определение'],['L2','L2 · прямой семантический scope']],'L1');
        const dependencyNote=field(native,'Основание зависимости','','textarea');
        button(native,'Добавить L1/L2 зависимость',async()=>{const request=await schema('dependency_add',focusId);
          request.sourceId=dependencySource.value;request.dependentId=dependencyTarget.value;
          request.dependencyLevel=dependencyLevel.value;request.note=dependencyNote.value;await prepare(request);});
        for(const edge of view.graph.edges.filter(e=>!e.archived&&e.type==='DEPENDS_ON'&&e.dependencyLevel)){
          const row=el('div',null,'rp-card');native.appendChild(row);
          row.appendChild(el('p',edge.dependencyLevel+' · '+edge.from+' → '+edge.to));
          const removeNote=field(row,'Причина снятия','','textarea');
          button(row,'Снять зависимость',async()=>{const request=await schema('dependency_remove',focusId);
            request.edgeId=edge.id;request.disposition=removeNote.value;request.note=removeNote.value;await prepare(request);});
        }
        const lockNode=entities.find(n=>n.id===focusId);
        if(lockNode){
          const lockBox=details(parent,'Замок object+operation');
          const lockOperation=select(lockBox,'Операция',[['edit','Изменение определения'],['link','Изменение связи'],['unlink','Снятие связи'],['select','Выбор Action'],['withdraw','Отказ от Action'],['complete','Подтверждение результата'],['dependency_add','Создание зависимости'],['dependency_remove','Снятие зависимости']],'edit');
          const lockMode=select(lockBox,'Режим',[['warning','Warning · только сообщение'],['hard','Hard · требует principal']],'hard');
          const lockPrincipals=field(lockBox,'Разрешённые principals, через запятую');
          const lockMessage=field(lockBox,'Сообщение замка','','textarea');
          const authorityPrincipal=transport.approval?{value:''}:field(lockBox,'Principal текущего user path');
          if(transport.approval)lockBox.appendChild(el('p','Исполнитель будет установлен по зарегистрированному ключу при подтверждении.'));
          button(lockBox,'Установить замок',async()=>{const request=await schema('lock_set',focusId);
            request.nodeId=lockNode.id;request.operation=lockOperation.value;request.mode=lockMode.value;
            request.principals=lockPrincipals.value.split(',').map(x=>x.trim()).filter(Boolean);
            request.message=lockMessage.value;request.authorityPrincipal=authorityPrincipal.value;
            request.note=lockMessage.value;await prepare(request);});
          for(const [operation,spec] of Object.entries(lockNode.locks||{})){
            const row=el('div',null,'rp-card');lockBox.appendChild(row);
            row.appendChild(el('p',operation+' · '+spec.mode+' · '+spec.message));
            const removeDisposition=field(row,'Причина снятия','','textarea');
            button(row,'Снять замок',async()=>{const request=await schema('lock_remove',focusId);
              request.nodeId=lockNode.id;request.operation=operation;
              request.disposition=removeDisposition.value;request.authorityPrincipal=authorityPrincipal.value;
              request.note=removeDisposition.value;await prepare(request);});
          }
        }
      }
      const transfer=details(parent,'Шаблон, копирование и вставка');
      const sources=select(transfer,'Источник',(catalog?.packages||[]).filter(r=>r.packageId).map(r=>[r.packageId,(names[r.role]||'')+' · '+(r.title||r.path)]),selected);
      const path=field(transfer,'Папка новой копии'),reason=field(transfer,'Основание');
      transfer.appendChild(el('p','Если папка не указана, копия попадёт в папку даты Asia/Bangkok с уникальным именем.'));
      const moved=field(transfer,'Новое расположение этого пакета');button(transfer,'Проверить перемещение пакета',async()=>{const request=await schema('move');request.path=moved.value;request.note=reason.value;await prepare(request);});
      button(transfer,focus.kind==='focus'?'Скопировать этот фокус':'Скопировать весь Graph',async()=>{const request=await schema('copy');if(path.value.trim())request.path=path.value;request.note=reason.value;request.focus=focus.kind==='focus'?{kind:node.kind,id:node.id}:{kind:'graph'};await prepare(request);},focus.kind==='focus'&&!['action','requirement','canon'].includes(node?.kind));
      if(work){button(transfer,'Вставить копию источника целиком',async()=>{const request=await schema('insert_copy',focusId,{sourcePackageId:sources.value});request.note=reason.value;await prepare(request);});
        const mode=select(transfer,'Применить весь шаблон',[['ADD_ROOT','Добавить корень'],['REPLACE_R','Заменить выбранную R']]);
        button(transfer,'Проверить применение ready',async()=>{const request=await schema('apply_ready',focusId,{sourcePackageId:sources.value});request.mode=mode.value;if(mode.value==='REPLACE_R')request.targetRequirementId=focusId;request.note=reason.value;await prepare(request);});}
      const advanced=details(parent,'Дополнительные команды');advanced.appendChild(el('p','Для сложного origin, канонов, evidence и ветвления доступны те же команды, что у Agent.'));
      const command=field(advanced,'Команда (например, output_origin или complete)'),input=field(advanced,'Параметры команды','','textarea');
      button(advanced,'Получить форму команды',async()=>{const value=await schema(work?'core':'paper_edit',focusId,{command:command.value});input.value=JSON.stringify(value,null,2);});
      button(advanced,'Проверить команду',()=>prepare(JSON.parse(input.value)));
    }
    function renderDecisionOperations(parent,work){
      const box=details(parent,'Изменить Graph'),entities=[...view.graph.nodes,...view.graph.objects,...view.graph.externalActions];
      const focusId=focus.kind==='focus'?focus.id:view.graph.rootRequirementId,node=entities.find(n=>n.id===focusId);
      if(node){box.appendChild(el('p',node.description||''));if(node.guidance)box.appendChild(el('p',node.guidance));}
      const noteInput=field(box,'Основание изменения','','textarea');
      const kind=select(box,'Новый блок',[['decision','Decision'],['requirement','Requirement'],['action','Обязательный Graph Action'],['external','Внешний Action']]);
      const title=field(box,'Название'),description=field(box,'Описание','','textarea');
      const scope=field(box,'Область R',node?.scope||view.graph.nodes.find(n=>n.kind==='requirement')?.scope||'');
      button(box,'Добавить блок',async()=>{
        const request=await schema(work?'core':'paper_edit',focusId,{command:'add'}),id=globalThis.crypto.randomUUID();
        const entity={id,kind:kind.value==='external'?'action':kind.value,title:title.value,description:description.value};
        if(entity.kind==='requirement')entity.scope=scope.value;
        if(entity.kind==='action')Object.assign(entity,{actionType:'task',lowLevel:false,targetIds:node?[node.id]:[],groupIds:[]});
        const data={entity,location:kind.value==='external'?'external':'graph'};
        if(data.location==='graph'){
          if(focus.kind==='workGraph')data.workGraphId=focus.id;
          let type=null;
          if(node?.kind==='requirement')type=entity.kind==='decision'?'DRIVES':entity.kind==='requirement'?'DERIVES':'REQUIRES_ACTION';
          if(node?.kind==='decision')type=entity.kind==='requirement'?'INTRODUCES':entity.kind==='action'?'REQUIRES_ACTION':null;
          if(type)data.initialRelations=[{id:globalThis.crypto.randomUUID(),type,from:node.id,to:id}];
        }
        request.data=data;request.note=noteInput.value;await prepare(request);
      });
      if(node){
        button(box,'Переименовать блок',async()=>{
          const request=await schema(work?'core':'paper_edit',node.id,{command:'edit'});
          request.data={nodeId:node.id,changes:{title:title.value||node.title},cosmetic:true};request.note=noteInput.value;await prepare(request);
        });
        if(work){
          button(box,'Подтвердить пересмотр',async()=>{const request=await schema('core',node.id,{command:'review'});request.note=noteInput.value;await prepare(request);});
          if(node.kind==='decision')for(const [command,label] of [['select','Выбрать Decision'],['withdraw','Отказаться от Decision']])
            button(box,label,async()=>{const request=await schema('core',node.id,{command});request.note=noteInput.value;await prepare(request);});
        }
      }
      const advanced=details(box,'Команда API'),command=field(advanced,'Команда'),input=field(advanced,'Параметры команды','','textarea');
      button(advanced,'Получить форму команды',async()=>{input.value=JSON.stringify(await schema(work?'core':'paper_edit',focusId,{command:command.value}),null,2);});
      button(advanced,'Проверить команду',()=>prepare(JSON.parse(input.value)));
    }

    function renderPlan(parent){
      const box=details(parent,'План во времени');if(!view.plan){box.appendChild(el('p','У этого пакета нет Plan.'));button(box,'Добавить план во времени',async()=>prepare(await schema('plan_create')));return;}
      for(const bucket of Object.keys(statuses)){box.appendChild(el('h3',statuses[bucket]));
        for(const item of view.planView.placements.filter(r=>r.bucket===bucket)){const card=el('div',null,'rp-card');box.appendChild(card);
          card.appendChild(el('p',(item.node?.title||item.step.title)+(item.reason?' · '+item.reason:'')));
          button(card,'Открыть блок',()=>open(item.step.ref.packageId,{kind:'focus',id:item.step.ref.nodeId}));
          button(card,'Убрать размещение',async()=>{const request=await schema('unplace');request.stepId=item.step.id;request.note='Убрано размещение';await prepare(request);});}}
      const target=select(box,'Разместить блок',[...view.graph.nodes,...(view.graph.externalActions||[])].map(n=>[n.id,n.kind+' · '+n.title]));
      const at=field(box,'Не раньше','', 'date');button(box,'Проверить размещение',async()=>{const request=await schema('place',target.value);request.at=at.value;request.note='Явное размещение во времени';await prepare(request);});
      if(view.plan.schemaVersion===3){box.appendChild(el('p','Порядок: '+view.plan.mainStepIds.map(id=>view.plan.steps.find(s=>s.id===id)?.title).join(' → ')));return;}
      const branches=details(box,'Порядок, условия и исходы ветвей');json(branches,{sequence:view.planView.sequence,branches:view.planView.branches});
      const plan=field(branches,'Изменение Plan','','textarea');button(branches,'Получить текущую форму',async()=>{plan.value=JSON.stringify(await schema('plan_edit'),null,2);});button(branches,'Проверить изменение',()=>prepare(JSON.parse(plan.value)));
    }
    function renderHistory(parent,value){
      for(const event of value.events){const box=details(parent,(event.inherited?'Унаследовано · ':'')+event.event.type+' · '+(event.event.recordedAt||event.acceptedAt||'время не установлено'));json(box,event);button(box,'Открыть Graph на момент события',()=>historicalGraph(box,event.source));}
      for(const version of value.planVersions){const box=details(parent,'Plan '+version.plan.revision+(version.inherited?' · унаследованная версия':'')+(version.legacy?' · прежний формат':''));json(box,version);}
      if(value.migrationEvidenceGaps?.length)json(parent,{migrationEvidenceGaps:value.migrationEvidenceGaps});
    }
    button(bar,'Обновить каталог',refresh);renderPreview();renderApprovals();renderEmpty();if(startInExplorer)activateDecision();
    return {start:()=>run(()=>startInExplorer?activateDecision().start():refresh()),refresh,open,prepare,commit,refreshApprovals,openApproval,decideApproval,approvalStatus,recoverApproval,registerCredential,get enrollment(){return enrollment;},get approval(){return approvalCurrent;},get view(){return decisionActive?decisionController.view:view;},get session(){return decisionActive?decisionController.session:undefined;},api(message){if(decisionActive)return decisionController.api(message);return call(message);},get busy(){return busy||decisionActive&&!!decisionController?.busy;},get pending(){return decisionActive?decisionController.pending:pending;},get switchBlocked(){return decisionActive?decisionController.switchBlocked:!!pending||!!draft;}};
  }
  return {mount,diffRows};
});
// END GENERATED RDG PORTABLE UI
// BEGIN GENERATED RDG WORKFLOW UI
/* Local manual workflow controller. Same Graph/Plan writers, no optimistic facts. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else{
    root.RDGWorkflowUI=api;
    const host=document.getElementById('rdg-viewer-root');
    if(host&&root.RDG_LOCAL_WORKFLOW){
      // The Viewer defers catalog initialization in a loopback Helper page.
      // The standalone controller is responsible for bootstrapping it once.
      // Otherwise folder/root selection stays unavailable despite a healthy
      // authenticated snapshot and a running Gendocen engine.
      if(typeof host.rdgStart==='function')void host.rdgStart();
      const base=new URL('./',location.href),session=root.RDG_SESSION;
      const request=async(path,body)=>{
        const response=await fetch(new URL(path,base),{method:body?'POST':'GET',credentials:'omit',
          redirect:'error',headers:{'X-RDG-Session':session,...(body?{'Content-Type':'application/json'}:{})},
          ...(body?{body:JSON.stringify(body)}:{})});
        const result=await response.json();
        if(!response.ok){const error=Error(result.error||'Запрос отклонён');error.definite=result.definite!==false;throw error;}
        return result;
      };
      root.RDG_LOCAL_DEPENDENCIES=body=>request('dependencies',body);
      const ui=api.mount(host.rdgWorkflow.attach(),{read:()=>request('state'),write:r=>request('command',r),admin:r=>request('admin',r)},
        {document,graphContainer:host.rdgWorkflow.graphEditor(),onGraph:(g,v)=>host.rdgWorkflow.loadGraph(g,v),onNavigate:(ref,v)=>host.rdgWorkflow.openDeclaration(ref,v)});
      root.RDG_LOCAL_EDITOR=ui;void ui.refresh();
    }
  }
})(globalThis,function(){
  'use strict';
  function fileTransport(directory,options={}){
    const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    let report=options.onStatus||(()=>{});
    const readJson=async name=>JSON.parse(await (await directory.getFileHandle(name)).getFile().then(f=>f.text()));
    const writeJson=async(name,value)=>{
      const file=await directory.getFileHandle(name,{create:true}),writer=await file.createWritable();
      await writer.write(JSON.stringify(value));await writer.close();
    };
    const checkDescriptor=async()=>{
      let descriptor;
      try{descriptor=await readJson('session.json');}
      catch(e){
        if(e.name==='NotFoundError')throw Error('В этой папке нет session.json. Выберите папку session, созданную локальным Helper.');
        throw e;
      }
      if(!descriptor||descriptor.schemaVersion!==1||descriptor.kind!=='rdg-local-manual-session')
        throw Error('Это не папка сессии RDG. Выберите папку session, созданную локальным Helper.');
      if(descriptor.active===false)throw Error('Сессия Helper завершена. Запустите новую сессию и подключите её папку.');
      if(descriptor.active!==true||typeof descriptor.session!=='string'||!descriptor.session)
        throw Error('Файл session.json повреждён или неполон. Запустите новую сессию Helper и подключите её папку.');
      return descriptor;
    };
    async function exchange(kind,body){
      let queued=false;
      try{
        report('Проверяю папку сессии…');
        const descriptor=await checkDescriptor();
        const random=randomId();
        const id='io-'+random,request='request-'+id+'.json',ready='request-'+id+'.ready',response='response-'+id+'.json';
        report('Записываю запрос в папку сессии… Если браузер просит доступ к записи, подтвердите его для выбранной папки session.');
        await writeJson(request,{session:descriptor.session,kind,body});
        // A failed close of the ready marker may still have queued the request.
        queued=true;await writeJson(ready,{ready:true});
        const started=Date.now(),timeout=options.timeoutMs??(kind==='state'?10000:45000);
        let checked=started,shown=-1;
        while(Date.now()-started<timeout){
          let result;
          try{result=await readJson(response);}
          catch(e){if(e.name!=='NotFoundError')throw e;}
          if(result){
            for(const name of [ready,request,response]){
              try{await directory.removeEntry(name);}catch{/* cleanup never changes accepted outcome */}
            }
            if(!result.ok){const error=Error(result.error||'Запрос отклонён');error.definite=result.definite!==false;throw error;}
            return result.result;
          }
          const seconds=Math.floor((Date.now()-started)/1000);
          if(seconds!==shown){shown=seconds;report('Ожидаю ответ локального Helper… '+seconds+' с.');}
          if(Date.now()-checked>=1000){
            const current=await checkDescriptor();checked=Date.now();
            if(current.session!==descriptor.session)throw Error('В папке уже другая сессия Helper. Подключите папку заново.');
          }
          await pause(options.pollMs??150);
        }
        throw Error(kind==='state'?
          'Helper не ответил за '+Math.round(timeout/1000)+' с. Проверьте, что он запущен и выбрана его папка session. Затем нажмите «Обновить» или подключите новую папку.':
          'Helper не ответил. Исход записи неизвестен. Проверьте Helper, обновите данные и повторите тот же запрос.');
      }catch(e){
        if(e.name==='NotAllowedError'||e.name==='SecurityError'){
          const error=Error('Нет доступа к папке сессии. Подключите её заново и разрешите чтение и запись.');
          error.definite=!queued||kind==='state';throw error;
        }
        if(!queued||kind==='state')e.definite=true;
        throw e;
      }
    }
    return {describe:checkDescriptor,read:contextId=>exchange('state',contextId==null?null:{contextId}),
      write:body=>exchange('command',body),admin:body=>exchange('admin',body),
      dependencies:body=>exchange('dependencies',body),
      setStatus:callback=>{report=callback;}};
  }
  // Internal educational view only. Real working graphs require a saved
  // Plan owner; do not expose a generated empty Plan as if it were persisted.
  function localPlanPreview(entry,graphs,{exampleOnly=false}={}){
    if(!entry||!entry.slug||!entry.file||!graphs||!graphs[entry.file])
      throw Error('LOCAL_PLAN_WORKSPACE_REQUIRED');
    const root=graphs[entry.file],identitySpace=root.identitySpace||'legacy-'+entry.slug;
    const educational=exampleOnly||!!root.readOnly||!!root.exampleOnly;
    const sanitized={};for(const [file,g] of Object.entries(graphs)){
      if(g&&Array.isArray(g.nodes)&&Array.isArray(g.edges)&&Array.isArray(g.events)&&
         (file===entry.file||g.identitySpace&&g.identitySpace===root.identitySpace))
        sanitized[file]={...g,identitySpace};
    }
    // Published read-only examples may already carry an explicit authored
    // workflow snapshot. Reuse it instead of erasing historical/future cards.
    if(educational&&root.workflowExample){
      const authored=JSON.parse(JSON.stringify(root.workflowExample));
      if(authored.graphFile===entry.file&&authored.sources?.plan&&
         Array.isArray(authored.history)&&Array.isArray(authored.future)){
        // An educational timeline is not permission to fabricate placements.
        // Every referenced step must resolve to an existing owned Graph node.
        const steps=authored.sources.plan.steps;
        if(!Array.isArray(steps)||!steps.every(step=>{
          const ref=step.actionRef||step.requirementRef;
          const owner=ref&&sanitized[ref.graphFile];
          const node=owner?.nodes?.find(n=>n.id===ref.nodeId);
          return !ref||!!(node&&owner.identitySpace===ref.identitySpace&&
              node.kind===step.kind&&step.kind=== (step.actionRef?'action':'requirement'));
        })||!authored.future.every(row=>{
          const step=steps.find(step=>step.id===row.stepId),ref=row.graphRef;
          const owner=ref&&sanitized[ref.graphFile];
          const node=owner?.nodes?.find(n=>n.id===ref.nodeId);
          const original=step&&(step.actionRef||step.requirementRef);
          return !!(step&&node&&owner.identitySpace===ref.identitySpace&&
            node.kind===step.kind&&row.kind===step.kind&&row.nodeId===ref.nodeId&&
            original?.graphFile===ref.graphFile&&original.identitySpace===ref.identitySpace&&
            original.nodeId===ref.nodeId&&
            (node.kind!=='action'||node.status==='selected'));
        }))throw Error('EDUCATIONAL_PLAN_REFERENCES_MUST_EXIST_IN_GRAPH');
        for(const g of Object.values(sanitized))delete g.workflowExample;
        return {...authored,localPreview:false,examplePreview:true,authoredExamplePreview:true,
          planFile:null,permissions:[],grantAdminAvailable:false,
          planProvenance:{mode:'embedded-read-only-example',persisted:false},
          sources:{...authored.sources,graphs:sanitized}};
      }
    }
    const history=[];
    const types={module_event:'module_event',modules_configured:'modules_configured',
      graph_changed:'graph_saved',action_executed:'action_executed',
      requirement_achieved:'requirement_achieved',action_withdrawn:'action_withdrawn',
      action_reconsidered:'action_reconsidered',action_selected:'action_selected',
      requirement_reformulated:'requirement_reformulated'};
    for(const [file,g] of Object.entries(sanitized))for(const [index,event] of g.events.entries()){
      if(!types[event.type])continue;
      const id=event.targetId||event.actionId||event.requirementId||null;
      const node=g.nodes.find(n=>n.id===id)||null;
      const savedSelection=node?.selectionBasis?.actionSnapshot;
      const snapshot=event.viewSnapshot||event.priorActionSnapshot||
        event.previousRequirementSnapshot||savedSelection||null;
      history.push({id:file+'::'+(event.id||index),graphFile:file,
        kind:types[event.type],sourceEventType:event.type,targetId:id,
        title:node?.title||snapshot?.title||null,
        nodeSnapshot:snapshot,materialSnapshotAvailable:!!snapshot,
        recordedAt:event.recordedAt||null,note:event.note||null,
        previousRequirementSnapshot:event.previousRequirementSnapshot||null,
        newRequirementSnapshot:event.newRequirementSnapshot||null,
        transition:event.type==='action_reconsidered'?event.transition:null,
        reviewActionId:event.reviewActionId||null,
        summary:event.label||event.note||null,by:event.by||null});
    }
    // Known timestamps are sorted; unknown timestamps remain visibly unknown.
    history.sort((a,b)=>String(a.recordedAt||'').localeCompare(String(b.recordedAt||''))||a.id.localeCompare(b.id));
    const plan={schemaVersion:1,kind:'temporalPlan',id:entry.slug,title:'План · '+(entry.title||root.title||entry.slug),
      identitySpace,revision:1,status:'candidate',steps:[],sequence:[],branches:[],timeConstraints:[]};
    return {schemaVersion:1,title:plan.title,planFile:null,graphFile:entry.file,
      planId:plan.id,planProvenance:{mode:educational?'educational-example-no-owner':'internal-unpersisted-view',persisted:false},
      coverage:'events visible in available Graph files; writer journal not independently loaded',
      localPreview:!educational,examplePreview:educational,authoredExamplePreview:false,
      permissions:[],history,future:[],unresolved:[],
      sources:{plan,graphs:sanitized,completion:{}},excludedPlacements:[]};
  }
  function localPlanFromOwner(entry,graphs,store){
    // View the *real persisted owner*. Never synthesize an empty Plan for a
    // missing file. Cryptographic journal validation is delegated to Helper.
    const expected='plans/'+entry.slug+'/plan.json';
    const root=graphs?.[entry.file];
    const space=root?.identitySpace||'legacy-'+entry.slug;
    if(!root||!store||store.kind!=='temporalPlanOwner'||store.schemaVersion!==1||
       store.owner?.sourcePath!==expected||store.owner?.planId!==entry.slug||
       store.owner?.identitySpace!==space||!Number.isInteger(store.revision)||
       store.revision<1||!Array.isArray(store.versions)||store.versions.length!==store.revision)
      throw Error('PLAN_OWNER_NOT_MATCHING_GRAPH');
    const last=store.versions[store.versions.length-1];
    const plan=last?.plan;
    if(last.revision!==store.revision||plan?.id!==entry.slug||plan?.identitySpace!==space||
       plan?.revision!==store.revision||!Array.isArray(plan.steps)||
       !Array.isArray(plan.sequence)||!Array.isArray(plan.timeConstraints)||!Array.isArray(plan.branches))
      throw Error('PLAN_OWNER_RECORD_INVALID');
    const base=localPlanPreview(entry,graphs);
    if(base.examplePreview)throw Error('PLAN_EXAMPLE_CANNOT_OVERRIDE_AUTHORED_SNAPSHOT');
    const covered=new Set(plan.timeConstraints.map(x=>x.stepId));
    for(const edge of plan.sequence){covered.add(edge.before);covered.add(edge.after);}
    const future=[];const unresolved=[];
    for(const step of plan.steps){
      if(!['action','requirement'].includes(step.kind)||!covered.has(step.id))continue;
      const ref=step.actionRef||step.requirementRef,own=ref&&base.sources.graphs[ref.graphFile];
      const node=own?.nodes?.find(n=>n.id===ref.nodeId);
      if(!node||own.identitySpace!==ref.identitySpace||node.kind!==step.kind){
        unresolved.push({nodeId:ref?.nodeId||step.id,reason:'owner not verified without Helper'});continue;
      }
      future.push({stepId:step.id,kind:step.kind,graphRef:ref,nodeId:ref.nodeId,
        title:node.title,plannedTitle:step.title,state:step.state,
        timeConstraints:plan.timeConstraints.filter(x=>x.stepId===step.id),
        sequence:plan.sequence.filter(x=>x.before===step.id||x.after===step.id)});
    }
    // File-only mode may read the real Plan owner versions. Show recorded
    // placement changes, not fabricated executions. Helper remains the
    // independent authority for Graph writer journals and completion.
    const placementHistory=[];let prior=new Map(),priorPosition=new Map();
    for(const version of store.versions){
      const current=new Map(version.plan.steps.map(step=>[step.id,step]));
      const positions=new Map([...current.keys()].map(id=>[id,{
        timeConstraints:version.plan.timeConstraints.filter(t=>t.stepId===id),
        sequence:version.plan.sequence.filter(e=>id===e.before||id===e.after)}]));
      for(const [id,step] of current){
        if(JSON.stringify(prior.get(id))===JSON.stringify(step)&&
           JSON.stringify(priorPosition.get(id))===JSON.stringify(positions.get(id)))continue;
        const ref=step.actionRef||step.requirementRef;if(!ref)continue;
        placementHistory.push({id:expected+'::plan-r'+version.revision+'::'+id,
          kind:'plan_placement_saved',graphFile:ref.graphFile,targetId:ref.nodeId,
          title:step.title,recordedAt:version.recordedAt,planRevision:version.revision,
          summary:'Сохранено размещение '+step.kind+' '+ref.nodeId+' в Plan owner',
          transactionId:version.transactionId,
          previousPlacementSnapshot:priorPosition.get(id)||null,
          newPlacementSnapshot:positions.get(id)||null,materialSnapshotAvailable:false});
      }
      for(const [id,step] of prior){
        if(current.has(id))continue;
        const ref=step.actionRef||step.requirementRef;if(!ref)continue;
        placementHistory.push({id:expected+'::plan-r'+version.revision+'::'+id,
          kind:'plan_placement_removed',graphFile:ref.graphFile,targetId:ref.nodeId,
          title:step.title,recordedAt:version.recordedAt,planRevision:version.revision,
          summary:'Удалено размещение '+step.kind+' '+ref.nodeId+' из Plan owner',
          transactionId:version.transactionId,materialSnapshotAvailable:false});
      }
      if(version.revision===1)placementHistory.push({id:expected+'::created',
        kind:'plan_created',recordedAt:version.recordedAt,planRevision:1,
        summary:'Создан настоящий Plan owner '+plan.id,
        transactionId:version.transactionId,materialSnapshotAvailable:false});
      prior=current;priorPosition=positions;
    }
    return {...base,localPreview:false,storedPlanReadOnly:true,title:plan.title,planFile:expected,
      planId:plan.id,planProvenance:{mode:'local-plan-file',persisted:true,
        revision:store.revision,journalVerified:false},
      history:[...base.history,...placementHistory].sort((a,b)=>String(a.recordedAt||'').localeCompare(String(b.recordedAt||''))||a.id.localeCompare(b.id)),
      sources:{...base.sources,plan},future,unresolved,
      coverage:'Saved Plan owner file; full graph journal and completion require Helper'};
  }
  // Independent dimensions: Graph completion, Plan placement, Graph branch
  // applicability. Never infer an execution from a date, selection or absence
  // of entries in the historical UI; completion is only from owner evidence.
  function historyKind(kind){
    if(['module_event','module_plan_changed','modules_configured'].includes(kind))
      return {group:'module',label:'МОДУЛЬ',description:'Изменение модуля — не факт выполнения'};
    if(['plan_created','plan_placement_saved','plan_placement_removed'].includes(kind))
      return {group:'plan',label:'ПЛАН',description:'Версия Plan owner — размещение, не выполнение Action'};
    if(['action_executed','requirement_achieved'].includes(kind))
      return {group:'result',label:'РЕЗУЛЬТАТ',description:'Подтверждённый результат / запись выполнения'};
    if(['requirement_falsified','action_reopened','core_requirement_necessity_changed','core_review_confirmed'].includes(kind))
      return {group:'state',label:'АКТУАЛЬНОСТЬ',description:'Проверка, потеря истинности или повторное открытие'};
    if(typeof kind==='string'&&kind.startsWith('core_'))return {group:'change',label:'ИЗМЕНЕНИЕ ГРАФА',description:'Принятое изменение уточнённой модели'};
    if(['requirement_activated','requirement_deactivated','action_withdrawn',
        'action_reconsidered'].includes(kind))
      return {group:'state',label:'СОСТОЯНИЕ',description:'Изменение актуальности или отзыв'};
    if(['action_selected','decision_selected','decision_revised'].includes(kind))
      return {group:'choice',label:'ВЫБОР',description:'Выбор способа или решения — не выполнение'};
    if(['graph_saved','graph_changed','requirement_reformulated','requirement_reparented','context_discovered',
        'action_requirement_linked'].includes(kind))
      return {group:'change',label:'ИЗМЕНЕНИЕ ГРАФА',description:'Изменено определение работы или контекст'};
    return {group:'other',label:'ДРУГОЕ СОБЫТИЕ',description:'Неуточнённый тип события'};
  }
  function planningInventory(view){
    const graphSet=view?.sources?.graphs||{},states=view?.sources?.completion||{};
    const plan=view?.sources?.plan||{},steps=Array.isArray(plan.steps)?plan.steps:[];
    const placeIds=new Set((plan.timeConstraints||[]).map(x=>x.stepId));
    for(const edge of plan.sequence||[]){placeIds.add(edge.before);placeIds.add(edge.after);}
    const placed=new Set();
    for(const row of view.future||[]){
      const ref=row.graphRef;
      if(ref)placed.add([ref.graphFile,ref.identitySpace,ref.nodeId].join('|'));
    }
    for(const step of steps){
      if(!placeIds.has(step.id))continue;
      const ref=step.actionRef||step.requirementRef;
      if(ref)placed.add([ref.graphFile,ref.identitySpace,ref.nodeId].join('|'));
    }
    const result={unplaced:[],placedCount:0,completedCount:0,needsVerification:[],excludedCount:0};
    for(const [file,g] of Object.entries(graphSet)){
      if(!g||!Array.isArray(g.nodes))continue;
      for(const n of g.nodes){
        if(!['requirement','action'].includes(n.kind)||n.projectionOf){continue;}
        const key=[file,g.identitySpace,n.id].join('|'),state=states[file]?.[n.id];
        const inactive=n.active===false||['inactive','superseded','rejected'].includes(n.status);
        const preliminary=['candidate','potential'].includes(n.status);
        if(inactive||preliminary||n.kind==='action'&&n.status!=='selected'||
            state?.reason==='potential-inactive-or-unavailable-owner'){
          result.excludedCount++;continue;
        }
        const current=state?.currentScopeComplete===true;
        if(state?.reviewRequired){result.needsVerification.push({graphFile:file,nodeId:n.id,kind:n.kind,title:n.title,reason:'dependency-review-required'});continue;}
        // An Action execution is immutable history even after the definition
        // changes. A Requirement is achieved only in its current scope.
        if(state?.historyPending){
          result.needsVerification.push({graphFile:file,nodeId:n.id,kind:n.kind,title:n.title,
            reason:state.reason||'history-record-not-confirmed'});continue;
        }
        const finished=n.kind==='action'?state?.complete===true&&!!state?.eventId:
          current&&!!state?.eventId;
        if(finished){result.completedCount++;continue;}
        if(state?.complete===true||current&&!state?.eventId){
          result.needsVerification.push({graphFile:file,nodeId:n.id,kind:n.kind,title:n.title,
            reason:state.reason||'history-record-not-confirmed'});continue;
        }
        if(placed.has(key)){result.placedCount++;continue;}
        result.unplaced.push({graphFile:file,identitySpace:g.identitySpace,
          nodeId:n.id,kind:n.kind,title:n.title,
          verification:state?'not-complete-in-current-authorized-view':'completion-not-verified'});
      }
    }
    return result;
  }
  function declarationFor(view,reference){
    const graphs=view?.sources?.graphs||{};
    let ref={...reference},node,graph,kind=null;const seen=new Set();
    for(;;){
      const key=[ref.graphFile,ref.identitySpace,ref.nodeId].join('|');
      if(seen.has(key))throw Error('Цикл ссылок на объявление узла');seen.add(key);
      graph=graphs[ref.graphFile];node=graph?.nodes.find(n=>n.id===ref.nodeId);
      if(!graph||graph.identitySpace!==ref.identitySpace||!node)throw Error('Граф объявления недоступен в подключённой сессии');
      if(kind&&node.kind!==kind)throw Error('Тип узла владельца не совпадает с проекцией');kind=node.kind;
      if(!node.projectionOf)break;
      const owner=view.sources.completion?.[ref.graphFile]?.[ref.nodeId]?.ownerRef;
      if(!owner||owner.identitySpace!==ref.identitySpace)throw Error('Владелец проекции не подтверждён; переход к личному графу не выполняется');
      ref={...owner};
    }
    const root=graph.rootRequirementId||graph.nodes.find(n=>n.kind==='requirement')?.id;
    let contextRootId=root;
    if(node.kind==='requirement'&&node.id!==root){
      // A historical Requirement may only have archived introduction edges.
      // Resolve its *existing* owner and fall back to the owner graph when
      // historic hierarchy is no longer part of the active composition.
      const candidates=graph.edges.filter(e=>e.type==='INTRODUCES'&&e.to===node.id);
      const introductions=candidates.some(e=>!e.archived)?candidates.filter(e=>!e.archived):candidates;
      const contexts=introductions.flatMap(e=>e.parent?[e.parent]:graph.edges.filter(d=>
        ['DRIVES','OPTION_FOR'].includes(d.type)&&d.to===e.from).map(d=>d.from));
      contextRootId=contexts.find(id=>graph.nodes.some(n=>n.id===id&&n.kind==='requirement'))||root;
    }else if(node.kind==='action'){
      contextRootId=graph.edges.find(e=>['DRIVES','OPTION_FOR'].includes(e.type)&&e.to===node.id&&!e.archived)?.from||
        graph.edges.find(e=>['DRIVES','OPTION_FOR'].includes(e.type)&&e.to===node.id)?.from||root;
    }
    if(!contextRootId||!graph.nodes.some(n=>n.id===contextRootId&&n.kind==='requirement'))
      throw Error('В исходном графе нет доступной корневой Requirement');
    return {ref,graph,node,contextRootId};
  }
  function randomId(){return typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);}
  // A read guard for local snapshots. The authoritative mutation validator remains Python.
  function validateCoreSnapshot(g){
    const fail=message=>{throw Error('CORE_SNAPSHOT: '+message);};
    if(g?.coreModel!=='rdg-core-v1'||g.actionModel!=='candidate-v6'||g.schemaVersion!==1)fail('неподдерживаемый профиль');
    for(const k of ['nodes','objects','edges','events','workGraphs'])if(!Array.isArray(g[k]))fail('нет массива '+k);
    const ids=new Set(),kinds=new Map();
    for(const [values,allowed] of [[g.nodes,['requirement','action']],[g.objects,['context','canon','info','evidence']]])for(const n of values){
      if(!n||typeof n.id!=='string'||!n.id||ids.has(n.id)||typeof n.title!=='string'||!n.title.trim()||!allowed.includes(n.kind)||!Number.isInteger(n.revision)||n.revision<1)fail('некорректный блок');
      ids.add(n.id);kinds.set(n.id,n.kind);
    }
    if(kinds.get(g.rootRequirementId)!=='requirement')fail('нет корневой R');
    const relations=new Set(['DRIVES','RELATES_R','DERIVES','INTRODUCES','CONTEXT_FOR','DEPENDS_ON','CANON_FOR','INFO_FOR','EVIDENCE_FOR']),edges=new Set();
    for(const e of g.edges){
      if(!e||!e.id||edges.has(e.id)||!ids.has(e.from)||!ids.has(e.to)||!relations.has(e.type))fail('некорректная связь');edges.add(e.id);
      if(e.origin!==undefined){
        const o=e.origin;
        if(e.type!=='INTRODUCES'||!o||typeof o!=='object'||Array.isArray(o))fail('происхождение выхода');
        if(o.role==='method_correctness'){if(Object.keys(o).length!==1)fail('поля корректности способа');}
        else if(o.role!=='subgoal'||Object.keys(o).sort().join(',')!=='requirementIds,role'||!Array.isArray(o.requirementIds)||!o.requirementIds.length||new Set(o.requirementIds).size!==o.requirementIds.length||o.requirementIds.some(i=>kinds.get(i)!=='requirement'))fail('исходные цели выхода');
      }
    }
    // Import is read-only, but status labels must not accept invented completion/selection events.
    const eventById=new Map();
    for(const e of g.events){
      if(!e||typeof e.id!=='string'||!e.id.trim()||eventById.has(e.id)||
          typeof e.type!=='string'||!e.type.trim()||!['assistant','user'].includes(e.by)||
          typeof e.note!=='string'||!e.note.trim())fail('некорректное событие');
      eventById.set(e.id,e);
    }
    for(const n of [...g.nodes,...g.objects]){
      if(n.kind==='requirement'&&(!['active','potential','inactive'].includes(n.status)||
          typeof n.description!=='string'||!n.description.trim()||
          typeof n.scope!=='string'||!n.scope.trim()))fail('некорректная R');
      if(n.kind==='action'&&!['candidate','selected','rejected','superseded'].includes(n.status))fail('некорректный статус A');
      if(['requirement','action'].includes(n.kind)){
        const r=n.result;
        if(!r||!['open','confirmed'].includes(r.state)||!['true','false','unknown'].includes(r.truth)||
            (r.state==='confirmed')!==(r.truth==='true')||
            (n.kind==='action'&&r.truth==='false'))fail('противоречивый результат');
        if(r.state==='confirmed'){
          const e=eventById.get(r.eventId);
          if(!e||e.type!==(n.kind==='action'?'action_executed':'requirement_achieved')||
              e.targetId!==n.id||!Array.isArray(e.evidenceRefs)||!e.evidenceRefs.length)
            fail('результат без события и доказательств');
        }
        if(n.kind==='requirement'&&r.truth==='false'){
          const e=eventById.get(r.eventId);
          if(!e||e.type!=='requirement_falsified'||e.targetId!==n.id||
              !Array.isArray(e.evidenceRefs)||!e.evidenceRefs.length)fail('потеря истинности без доказательств');
        }
      }
      if(n.kind==='action'&&n.status==='selected'){
        const e=eventById.get(n.selectedEventId);
        if(!e||e.type!=='action_selected'||e.targetId!==n.id||
            !g.edges.some(d=>!d.archived&&d.type==='DRIVES'&&d.to===n.id))
          fail('выбор A без действующего основания и события');
      }
      if(n.kind==='canon'){
        const mode=n.evaluationMode||'legacy-arguments-v1';
        if(!['legacy-arguments-v1','comment-only-v1'].includes(mode)||!Array.isArray(n.arguments)||
            (mode==='comment-only-v1'&&(typeof n.comment!=='string'||n.arguments.length))||
            (mode==='legacy-arguments-v1'&&!n.arguments.length))fail('некорректный формат канона');
      }
      if(n.assessment){
        const e=eventById.get(n.assessment.eventId);
        if(n.kind!=='action'||!e||e.type!=='core_canon_assessed'||e.targetId!==n.id)
          fail('оценка без события');
      }
    }
    if(g.lensRecommendations!==undefined){
      if(!Array.isArray(g.lensRecommendations))fail('рекомендации линз должны быть списком');
      const seen=new Set();
      for(const r of g.lensRecommendations){
        if(!r||typeof r!=='object'||Array.isArray(r)||!
          ([2,3].includes(Object.keys(r).length))||
          Object.keys(r).some(k=>!['lensKey','text','targetId'].includes(k))||
          typeof r.lensKey!=='string'||!(/^[a-z][a-z0-9-]*$/).test(r.lensKey)||
          typeof r.text!=='string'||!r.text.trim()||r.text.length>10000||
          (r.targetId!==undefined&&!['requirement','action','canon'].includes(kinds.get(r.targetId))))
          fail('некорректная рекомендация линзы');
        const key=JSON.stringify([r.lensKey,r.targetId||null,r.text]);
        if(seen.has(key))fail('повтор рекомендации');seen.add(key);
      }
    }
    if(!g.workGraphs.length)fail('нет рабочего scope');
    const members=new Set();
    for(const w of g.workGraphs){
      if(!Array.isArray(w.memberIds)||!Array.isArray(w.rootIds)||!w.rootIds.length||
          w.memberIds.some(i=>!ids.has(i))||w.rootIds.some(i=>!w.memberIds.includes(i)||kinds.get(i)!=='requirement'))
        fail('некорректный рабочий граф');
      w.memberIds.forEach(i=>members.add(i));
    }
    if(members.size!==ids.size)fail('блок вне рабочего scope');
    return g;
  }
  function coreOutputOrigin(g,e){
    const drivers=[...new Set(g.edges.filter(d=>!d.archived&&d.type==='DRIVES'&&d.to===e.from).map(d=>d.from))].sort();
    const role=e.origin?.role||'unspecified',declared=role==='subgoal'?e.origin.requirementIds:role==='method_correctness'?drivers:[];
    const externalRequirementRefs=(e.origin?.externalRequirementRefs||[]).map(x=>({...x}));
    const actualExternal=(g.externalRefs||[]).filter(r=>r.localId===e.from&&r.direction==='incoming'&&
      r.relation?.type==='DRIVES'&&!r.relation?.archived).map(r=>r.target);
    const missingExternalDriverRefs=externalRequirementRefs.filter(ref=>!actualExternal.some(target=>
      ['packageId','identitySpace','nodeId'].every(k=>ref[k]===target[k])));
    return {externalRequirementRefs,missingExternalDriverRefs,edgeId:e.id,actionId:e.from,role,requirementIds:[...declared].sort(),
      activeRequirementIds:declared.filter(i=>drivers.includes(i)).sort(),missingDriverIds:declared.filter(i=>!drivers.includes(i)).sort()};
  }
  // Focused projections of the closed core. They never become writable owners.
  function coreFocusedView(g,id){
    validateCoreSnapshot(g);
    const all=[...g.nodes,...g.objects],by=new Map(all.map(n=>[n.id,n])),focus=by.get(id);
    if(!focus)throw Error('CORE_FOCUS_UNKNOWN');
    const edges=g.edges.filter(e=>!e.archived),chosen=new Set([id]),terminal=new Set(),origins=[],originDetails=[];
    for(const e of edges){
      if(focus.kind==='requirement'){
        if(e.from===id&&['DRIVES','DERIVES'].includes(e.type)){chosen.add(e.to);terminal.add(e.to);}
        if(e.to===id&&['INTRODUCES','DERIVES'].includes(e.type)){
          chosen.add(e.from);origins.push(e);
          if(e.type==='INTRODUCES'){
            const detail=coreOutputOrigin(g,e);originDetails.push(detail);
            for(const d of edges)if(d.to===e.from&&d.type==='DRIVES'&&(detail.role==='unspecified'||detail.activeRequirementIds.includes(d.from))){chosen.add(d.from);origins.push(d);}
          }
        }
      }else if(focus.kind==='action'){
        if(e.to===id&&['DRIVES','RELATES_R','CONTEXT_FOR','CANON_FOR'].includes(e.type))chosen.add(e.from);
        if(e.from===id&&e.type==='INTRODUCES'){chosen.add(e.to);terminal.add(e.to);}
      }else if(focus.kind==='canon'&&e.from===id&&e.type==='CANON_FOR'){chosen.add(e.to);terminal.add(e.to);}
    }
    for(const e of edges)if(chosen.has(e.to)&&['INFO_FOR','EVIDENCE_FOR'].includes(e.type))chosen.add(e.from);
    const allowed=focus.kind==='requirement'?['DRIVES','DERIVES','INTRODUCES','INFO_FOR','EVIDENCE_FOR']:
      ['DRIVES','RELATES_R','CONTEXT_FOR','CANON_FOR','INTRODUCES','INFO_FOR','EVIDENCE_FOR'];
    return {focusId:id,focusKind:focus.kind,entities:all.filter(n=>chosen.has(n.id)),
      edges:edges.filter(e=>chosen.has(e.from)&&chosen.has(e.to)&&allowed.includes(e.type)&&
        !(focus.kind==='requirement'&&terminal.has(e.from)&&e.type==='INTRODUCES')),
      terminalIds:[...terminal],origins,originDetails,viewOnly:true};
  }
  function mountCore(container,g,{document:doc=globalThis.document,onCommand=null,onFocus=null,focusId=null,readOnly=false}={}){
    const make=(tag,text,parent=container)=>{const n=doc.createElement(tag);if(text!==undefined)n.textContent=text;parent.appendChild(n);return n;};
    const kinds={requirement:'R · требуемая истинность',action:'A · способ',context:'Context · факты',canon:'Канон',info:'Информация',evidence:'Evidence'};
    const roles={DRIVES:'реализует R',RELATES_R:'относится к R',DERIVES:'непосредственная под-R',INTRODUCES:'вводит R',CONTEXT_FOR:'контекст A',CANON_FOR:'оценивает A',DEPENDS_ON:'рабочая зависимость',INFO_FOR:'поясняет',EVIDENCE_FOR:'подтверждает'};
    const all=[...g.nodes,...g.objects],by=new Map(all.map(n=>[n.id,n]));
    const section=make('section');section.className='rdg-core';
    const style=make('style',undefined,section);style.textContent='.rdg-core{padding:16px;overflow:auto;color:#e7eff7;background:#17283b}.rdg-core label{display:block;margin:10px 0}.rdg-core input,.rdg-core select,.rdg-core textarea{display:block;box-sizing:border-box;max-width:100%;width:100%;padding:7px;color:inherit;background:#102235;border:1px solid #607a96}.rdg-core textarea{min-height:70px}.rdg-core button{padding:7px;margin:6px}.rdg-core svg{position:static;display:block;width:100%;min-width:700px;background:#102235;height:auto;touch-action:auto;cursor:default}.rdg-core .core-map{overflow:auto;max-height:65vh}.rdg-core summary{cursor:pointer}.rdg-core table{border-collapse:collapse;width:100%}.rdg-core td,.rdg-core th{padding:5px;border-bottom:1px solid #526680;text-align:left}';
    make('h3','Собственные графы R, A и канонов',section);
    make('p','Рабочий scope и фокус различаются. Нажатие на блок открывает его собственный граф; терминальные блоки здесь не разворачиваются.',section);
    const work=make('select',undefined,make('label','Рабочий граф',section));
    for(const w of g.workGraphs){const o=make('option',w.title,work);o.value=w.id;}
    const focus=make('select',undefined,make('label','Открыть собственный граф',section));
    const content=make('div',undefined,section),form=make('details',undefined,section);make('summary','Изменить граф или подтвердить результат',form);
    const body=make('div',undefined,form),status=make('p','',form);status.setAttribute('role','status');
    const option=(s,v,t)=>{const o=make('option',t,s);o.value=v;return o;};
    const field=(parent,label,value='',tag='input')=>{const e=make(tag,undefined,make('label',label,parent));e.value=value;return e;};
    const select=(parent,label,items,value)=>{const e=field(parent,label,'','select');for(const [v,t] of items)option(e,v,t);if(value!=null)e.value=value;return e;};
    const choose=id=>{focus.value=id;draw();if(onFocus)onFocus(id);};
    function fill(){
      const w=g.workGraphs.find(w=>w.id===work.value);focus.replaceChildren();
      const visible=all.filter(n=>w.memberIds.includes(n.id));
      for(const n of visible)option(focus,n.id,n.title+' · '+kinds[n.kind]);
      focus.value=visible.some(n=>n.id===focusId)?focusId:w.rootIds[0];draw();
    }
    work.onchange=fill;focus.onchange=()=>choose(focus.value);
    if(focusId){const w=g.workGraphs.find(w=>w.memberIds.includes(focusId));if(w)work.value=w.id;}
    const commands=[['add','Создать блок'],['edit','Уточнить описание'],['link','Добавить связь'],['unlink','Снять связь'],['output_origin','Уточнить происхождение выходной R'],
      ['assess','Сопоставить каноны'],['select','Выбрать способ'],['review','Подтвердить актуальность'],['complete','Подтвердить результат'],
      ['falsify','Зафиксировать потерю истинности R'],['reopen','Вернуться к прежнему A'],['requirement_state','Пересмотреть необходимость R'],
      ['withdraw','Отказаться от способа'],['lens_recommendations','Рекомендовать линзу текстом'],['work_graph','Добавить рабочий граф'],['join','Соединить рабочие графы'],['include','Показать тот же блок в другом рабочем графе'],['finding','Записать находку']];
    const cmd=select(body,'Действие',commands,'edit'),details=make('div',undefined,body);
    let build=()=>({}),proofNeeded=false;
    function editForm(){
      details.replaceChildren();const n=by.get(focus.value);if(!n)return;
      proofNeeded=['complete','falsify','review'].includes(cmd.value);
      const pick=(label,values=all)=>select(details,label,values.map(n=>[n.id,n.title+' · '+n.id]));
      function originFields(parent,initial={}){
        const role=select(parent,'Назначение выходной R',[['subgoal','Подцель исходных R'],['method_correctness','Корректность самого Action']],initial.role||'subgoal');
        const ids=field(parent,'Исходные R: ID через запятую',(initial.requirementIds||[]).join(', '));
        const update=()=>{ids.parentElement.hidden=role.value!=='subgoal';};role.onchange=update;update();
        return ()=>role.value==='subgoal'?{role:'subgoal',requirementIds:ids.value.split(',').map(s=>s.trim()).filter(Boolean)}:{role:'method_correctness'};
      }
      if(cmd.value==='add'){
        const kind=select(details,'Роль блока',Object.entries(kinds),'requirement');
        const title=field(details,'Смысловой заголовок'),description=field(details,'Подробное описание','','textarea');
        const scope=field(details,'Область истинности / применения',by.get(g.rootRequirementId).scope||'');
        make('p','Для сложной R предпочтительны полезные под-R. Подробности без пользы отдельной под-R остаются в описании.',details);
        const extras=make('div',undefined,details);let extraValues=()=>({});
        function kindFields(){
          extras.replaceChildren();extraValues=()=>({});
          if(kind.value==='requirement'){
            const status=select(extras,'Нормативный статус',[['potential','Потенциальная R на бумаге'],['active','Установленная R']],'potential');
            extraValues=()=>({scope:scope.value,status:status.value});
          }else if(kind.value==='evidence'){
            const claim=field(extras,'Какое утверждение подтверждается','','textarea'),version=field(extras,'Версия проверенного объекта'),source=field(extras,'Источник доказательства');
            extraValues=()=>({scope:scope.value,claim:claim.value,version:version.value,source:source.value});
          }else if(kind.value==='canon'){
            const comment=field(extras,'Комментарий к применимости Action','','textarea');
            extraValues=()=>({evaluationMode:'comment-only-v1',comment:comment.value,arguments:[]});
          }
        }
        kind.onchange=kindFields;kindFields();
        build=()=>{const id=(kind.value==='action'?'A-':kind.value==='requirement'?'R-':'O-')+randomId();
          return {entity:{id,kind:kind.value,title:title.value,description:description.value,...extraValues()},workGraphId:work.value};};
      }else if(cmd.value==='edit'){
        const title=field(details,'Заголовок',n.title),description=field(details,'Описание',n.description||'','textarea');
        const scope=n.kind==='requirement'?field(details,'Область истинности',n.scope):null;
        const comment=n.kind==='canon'?field(details,'Комментарий к применимости Action',n.comment||'','textarea'):null;
        const migrate=n.kind==='canon'&&n.evaluationMode!=='comment-only-v1'?field(details,'Преобразовать этот канон в свободный комментарий','','input'):null;
        if(migrate){migrate.type='checkbox';make('p','Прежние условия сохранятся в истории. Перед записью проверьте изменение.',details);}
        build=()=>({nodeId:n.id,changes:{title:title.value,description:description.value,...(scope?{scope:scope.value}:{}),
          ...(comment&&(n.evaluationMode==='comment-only-v1'||migrate?.checked)?{comment:comment.value}:{}),
          ...(migrate?.checked?{evaluationMode:'comment-only-v1',arguments:[]}:{})},
          ...(migrate?.checked?{legacyCanonMigrationAcknowledged:true}:{})});
      }else if(cmd.value==='link'){
        const type=select(details,'Смысл связи',Object.entries(roles),'DRIVES'),from=pick('Источник'),to=pick('Получатель');
        const role=select(details,'Роль относящейся R',[['affected','Затрагиваемая'],['constraining','Ограничивающая']]);
        const originBox=make('div',undefined,details),origin=originFields(originBox);
        type.onchange=()=>{originBox.hidden=type.value!=='INTRODUCES';role.parentElement.hidden=type.value!=='RELATES_R';};type.onchange();
        from.value=n.id;build=()=>({edge:{id:'E-'+randomId(),type:type.value,from:from.value,to:to.value,...(type.value==='RELATES_R'?{role:role.value}:{}),...(type.value==='INTRODUCES'?{origin:origin()}:{})}});
      }else if(cmd.value==='output_origin'){
        const outputs=g.edges.filter(e=>!e.archived&&e.type==='INTRODUCES'&&(e.from===n.id||e.to===n.id));
        const edge=select(details,'Выход способа',outputs.map(e=>[e.id,by.get(e.from).title+' → '+by.get(e.to).title]));
        const box=make('div',undefined,details);let readOrigin=()=>({});
        edge.onchange=()=>{box.replaceChildren();readOrigin=originFields(box,outputs.find(e=>e.id===edge.value)?.origin);};edge.onchange();
        build=()=>({edgeId:edge.value,origin:readOrigin()});
      }else if(cmd.value==='unlink'){
        const edges=g.edges.filter(e=>!e.archived&&(e.from===n.id||e.to===n.id));
        const edge=select(details,'Снимаемая связь',edges.map(e=>[e.id,(by.get(e.from)?.title||e.from)+' → '+(by.get(e.to)?.title||e.to)+' · '+roles[e.type]]));
        const disposition=field(details,'Судьба обязательств после снятия связи','','textarea');build=()=>({edgeId:edge.value,disposition:disposition.value});
      }else if(cmd.value==='assess'){
        const matches={},situation=g.edges.filter(e=>!e.archived&&e.to===n.id&&['DRIVES','RELATES_R','CONTEXT_FOR'].includes(e.type)).map(e=>by.get(e.from));
        function conditions(c,cid,parent){
          if(c.all||c.any){make('strong',c.all?'Все условия AND':'Хотя бы одно условие OR',parent);for(const child of c.all||c.any)conditions(child,cid,parent);return;}
          const row=make('fieldset',undefined,parent);make('legend',c.text,row);
          const result=select(row,'Результат сравнения',[['unknown','Неизвестно'],['match','Совпало'],['partial','Частичное сходство'],['no-match','Не совпало']]);
          const reason=field(row,'Основание смыслового сопоставления','','textarea'),source=select(row,'Факт рабочей ситуации',situation.map(n=>[n.id,n.title]));
          matches[cid][c.id]=()=>({result:result.value,reason:reason.value,sourceIds:source.value?[source.value]:[]});
        }
        for(const e of g.edges.filter(e=>!e.archived&&e.type==='CANON_FOR'&&e.to===n.id)){
          const canon=by.get(e.from);matches[canon.id]={};make('h4',canon.title,details);
          if(canon.evaluationMode==='comment-only-v1')make('p',canon.comment,details);
          for(const a of canon.arguments){make('p',(a.polarity==='against'?'Против':'За')+' · '+(a.strength==='hard'?'жёсткая несовместимость':'мягкий довод')+': '+a.text,details);conditions(a.condition,canon.id,details);}
        }
        build=()=>({nodeId:n.id,matches:Object.fromEntries(Object.entries(matches).map(([cid,v])=>[cid,Object.fromEntries(Object.entries(v).map(([id,fn])=>[id,fn()]))]))});
      }else if(cmd.value==='review'){
        const allStale=field(details,'Проверены все затронутые элементы вместе?','','input');allStale.type='checkbox';
        make('p','Stale требует проверки. Подтверждение сохраняет прежний результат; не заменяет доказательство его потери.',details);
        build=()=>{const ids=allStale.checked?all.filter(n=>n.review?.required).map(n=>n.id):[n.id];const observed={};
          for(const id of ids){observed[id]=by.get(id).revision;for(const e of g.edges)if(!e.archived&&e.to===id&&!['INFO_FOR','EVIDENCE_FOR'].includes(e.type))observed[e.from]=by.get(e.from).revision;}
          return {nodeIds:ids,observed};};
      }else if(cmd.value==='withdraw'){
        const outputs=g.edges.filter(e=>!e.archived&&e.from===n.id&&e.type==='INTRODUCES');const fields=outputs.map(e=>[e.to,field(details,'Судьба R: '+by.get(e.to).title,'','textarea')]);
        build=()=>({nodeId:n.id,dispositions:Object.fromEntries(fields.map(([id,f])=>[id,f.value]))});
      }else if(cmd.value==='requirement_state'){
        const state=select(details,'Необходимость R',[['active','Нужна'],['inactive','Не требуется']]),disposition=field(details,'Основание и последствия для общей работы','','textarea');
        const shared=field(details,'Рассмотрены последствия для всех общих родителей?','','input');shared.type='checkbox';
        const linked=g.edges.filter(e=>!e.archived&&e.type==='DRIVES'&&e.from===n.id).map(e=>by.get(e.to))
          .filter(a=>a?.kind==='action'&&a.status==='selected'&&a.result?.state==='confirmed');
        const decision=select(details,'Подтверждённый Action решения о ненужности',linked.map(a=>[a.id,a.title+' · '+a.id]));
        make('p','Сначала создайте, выберите и подтвердите связанный с этой R Action проверки необходимости. Writer проверит актуальность результата и evidence.',details);
        const update=()=>{decision.parentElement.hidden=state.value!=='inactive';};
        state.onchange=update;update();
        build=()=>({nodeId:n.id,state:state.value,disposition:disposition.value,acceptSharedConsequences:shared.checked,
          ...(state.value==='inactive'?{decisionActionId:decision.value}:{})});
      }else if(cmd.value==='lens_recommendations'){
        const lens=field(details,'Ключ рекомендуемой линзы (из каталога)');
        const text=field(details,'Когда и для чего её использовать','','textarea');
        const target=select(details,'К чему относится рекомендация',[
          ['', 'Ко всему графу'],...all.filter(x=>['requirement','action','canon'].includes(x.kind)).map(x=>[x.id,x.title+' · '+x.id])],n.id);
        make('p','Это только текстовая рекомендация. Линза не запускается, действия не выбираются и evidence не создаётся.',details);
        build=()=>({recommendations:[...(g.lensRecommendations||[]),{
          lensKey:lens.value.trim(),text:text.value,...(target.value?{targetId:target.value}:{})}]});
      }else if(cmd.value==='work_graph'){
        const title=field(details,'Название рабочего scope');const root=pick('Корневая R',all.filter(n=>n.kind==='requirement'));
        build=()=>({id:'WG-'+randomId(),title:title.value,rootIds:[root.value],memberIds:[root.value]});
      }else if(cmd.value==='join'||cmd.value==='include'){
        const other=select(details,'Другой рабочий граф',g.workGraphs.filter(w=>w.id!==work.value).map(w=>[w.id,w.title]));
        build=()=>cmd.value==='join'?{workGraphIds:[work.value,other.value]}:{nodeId:n.id,workGraphId:other.value};
      }else if(cmd.value==='finding'){
        const type=select(details,'Тип находки',[['problem','Подтверждённая проблема'],['risk','Риск'],['decision-uncertainty','Развилка решения'],['opportunity','Улучшение']]);const description=field(details,'Ситуация и основания','','textarea');
        build=()=>({nodeId:n.id,finding:{id:'F-'+randomId(),type:type.value,text:description.value}});
      }else{make('p',cmd.value==='select'?'Выбор принимает все актуальные выходные R способа. Совместимые способы допускаются; hard-несовместимость не компенсируется плюсами.':'Записывается отдельный факт; история прежних достижений сохраняется.',details);build=()=>({nodeId:n.id});}
      const note=field(details,'Основание действия / результат проверки','','textarea');
      const path=proofNeeded?field(details,'Проверенный файл результата, путь в рабочем owner'):null;
      const sha=proofNeeded?field(details,'SHA256 проверенного файла'):null;
      const submit=make('button','Записать и перечитать',details);submit.disabled=readOnly||!onCommand;
      submit.onclick=async()=>{submit.disabled=true;status.textContent='Проверяю и записываю…';try{
        const request={action:'core_'+cmd.value,transactionId:'ui-'+randomId(),nodeId:n.id,data:build(),note:note.value,expectedGraphRevision:g.revision};
        if(path?.value)request.evidenceRefs=[{path:path.value,sha256:sha.value}];
        await onCommand(request);status.textContent='Результат запроса показан в статусе writer.';
      }catch(e){status.textContent=e.message;}finally{submit.disabled=readOnly||!onCommand;}};
    }
    cmd.onchange=editForm;
    function draw(){
      const n=by.get(focus.value);if(!n)return;focusId=n.id;content.replaceChildren();
      const v=coreFocusedView(g,n.id);make('h4',kinds[n.kind]+' · '+n.title,content);
      make('p',(n.review?.required?'Требует проверки актуальности. ':'')+(n.result?.state==='confirmed'?'Результат ранее подтверждён. ':'')+'Область: '+(n.scope||g.title),content);
      for(const item of g.lensRecommendations||[]){
        if(item.targetId&&item.targetId!==n.id)continue;
        make('p','Рекомендуемая линза '+item.lensKey+(item.targetId?' для '+item.targetId:' для графа')+': '+item.text,content);
      }
      for(const origin of v.originDetails){
        const names=origin.activeRequirementIds.map(i=>by.get(i).title+' · '+i).join(', ');
        make('p',origin.role==='subgoal'?'Подцель через Action для: '+names:origin.role==='method_correctness'?'Требование корректности Action; он служит: '+names:'Происхождение выхода ещё не уточнено; цели Action не объявляются родителями автоматически.',content);
        if(origin.missingDriverIds.length)make('p','Связи с исходными R изменились. Пересмотрите происхождение: '+origin.missingDriverIds.join(', '),content);
      }
      const wrap=make('div',undefined,content);wrap.className='core-map';
      const ns='http://www.w3.org/2000/svg',svg=doc.createElementNS(ns,'svg');wrap.appendChild(svg);
      const groups=[v.entities.filter(x=>x.id!==n.id&&!v.terminalIds.includes(x.id)),[n],v.entities.filter(x=>v.terminalIds.includes(x.id))];
      const rows=Math.max(...groups.map(x=>x.length),1),height=rows*155+70;svg.setAttribute('viewBox','0 0 1060 '+height);svg.style.height=height+'px';
      const pos=new Map();groups.forEach((items,col)=>items.forEach((x,row)=>pos.set(x.id,{x:175+col*350,y:85+row*155})));
      const shape=(tag,attrs,parent=svg)=>{const e=doc.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);parent.appendChild(e);return e;};
      const markerId='core-arrow-'+randomId(),defs=shape('defs',{}),marker=shape('marker',{id:markerId,viewBox:'0 0 10 10',refX:10,refY:5,markerWidth:7,markerHeight:7,orient:'auto'},defs);
      shape('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#a7c4dc'},marker);
      for(const e of v.edges){
        const a=pos.get(e.from),b=pos.get(e.to),aw=by.get(e.from).kind==='action'?62:125,bw=by.get(e.to).kind==='action'?62:125;
        let points;
        if(a.x===b.x)points=[[a.x-aw,a.y],[20,a.y],[20,b.y],[b.x-bw,b.y]];
        else if(Math.abs(a.x-b.x)>350)points=[[a.x+aw,a.y],[350,a.y],[350,height-20],[700,height-20],[700,b.y],[b.x-bw,b.y]];
        else{const lane=(a.x+b.x)/2;points=[[a.x+aw,a.y],[lane,a.y],[lane,b.y],[b.x-bw,b.y]];}
        shape('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:['INFO_FOR','EVIDENCE_FOR'].includes(e.type)?'#92a8b8':'#84b5df','stroke-width':2,'marker-end':'url(#'+markerId+')','stroke-dasharray':['INFO_FOR','EVIDENCE_FOR'].includes(e.type)?'5 4':'none'});
      }
      for(const x of v.entities){const p=pos.get(x.id),group=shape('g',{'role':'button','tabindex':'0','aria-label':'Открыть '+x.title});
        const color={requirement:'#234e75',action:'#72532b',context:'#245c57',canon:'#573f7b',info:'#3c4c5b',evidence:'#3e624f'}[x.kind];
        shape(x.kind==='action'?'circle':'rect',x.kind==='action'?{cx:p.x,cy:p.y,r:62,fill:color,stroke:x.review?.required?'#ffc18c':'#a7c4dc'}:{x:p.x-125,y:p.y-55,width:250,height:110,rx:7,fill:color,stroke:x.review?.required?'#ffc18c':'#a7c4dc'},group);
        const limit=x.kind==='action'?14:30,lines=x.title.match(new RegExp('.{1,'+limit+'}(?:\\s|$)|.{1,'+limit+'}','gu'))||[x.title];
        const tooltip=shape('title',{},group);tooltip.textContent=x.title;
        for(let i=0;i<Math.min(lines.length,3);i++){const t=shape('text',{x:p.x,y:p.y-18+i*18,fill:'#fff','font-size':14,'text-anchor':'middle'},group);t.textContent=lines[i]+(i===2&&lines.length>3?'…':'');}
        const label=shape('text',{x:p.x,y:p.y+42,fill:'#d8e8f6','font-size':11,'text-anchor':'middle'},group);label.textContent=x.id+(v.terminalIds.includes(x.id)?' ↗':'');
        group.onclick=()=>choose(x.id);group.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(x.id);}};
      }
      const table=make('table',undefined,content);for(const e of v.edges){const tr=make('tr',undefined,table);make('td',by.get(e.from).title,tr);make('td',roles[e.type]+(e.role?' · '+e.role:'')+(e.origin?' · '+(e.origin.role==='subgoal'?'подцель '+e.origin.requirementIds.join(', '):'корректность Action'):''),tr);make('td',by.get(e.to).title,tr);}
      if(n.kind==='action'&&n.assessment){
        const current=Object.entries(n.assessment.pins||{}).every(([id,revision])=>by.get(id)?.revision===revision);
        const record=g.events.find(e=>e.id===n.assessment.eventId),assessment=make('section',undefined,content);
        make('h4',current?'Сохранённая оценка текущей ситуации':'Историческая оценка: нужна проверка актуальности',assessment);
        if(record?.verdict)make('p','Вывод оценки: '+({incompatible:'жёсткая несовместимость',undetermined:'существенная неизвестность',assessed:'сопоставление зафиксировано'}[record.verdict.verdict]||record.verdict.verdict),assessment);
        for(const [canon,matches] of Object.entries(n.assessment.matches))for(const [condition,m] of Object.entries(matches))
          make('p',(by.get(canon)?.title||canon)+' / '+condition+': '+m.result+' · '+m.reason+' · факты: '+m.sourceIds.map(id=>by.get(id)?.title||id).join(', '),assessment);
      }
      for(const x of v.entities){const d=make('details',undefined,content);make('summary',kinds[x.kind]+' · '+x.title+' · версия '+x.revision,d);make('p',x.description||x.claim||'',d);
        if(x.kind==='evidence')make('p','Утверждение: '+x.claim+' · область: '+x.scope+' · версия: '+x.version+' · источник: '+x.source,d);
        if(x.kind==='info')for(const usage of g.edges.filter(e=>!e.archived&&e.from===x.id&&e.type==='INFO_FOR')){const b=make('button','Поясняет: '+by.get(usage.to).title,d);b.onclick=()=>choose(usage.to);}
        if(x.kind==='canon'){
          if(x.evaluationMode==='comment-only-v1')make('p',x.comment,d);
          else for(const arg of x.arguments){make('p',(arg.strength==='hard'?'Hard':'Soft')+' · '+arg.text,d);const condition=c=>c.all?'AND ('+c.all.map(condition).join('; ')+')':c.any?'OR ('+c.any.map(condition).join('; ')+')':c.text;make('p',condition(arg.condition),d);}
        }
        if(x.review?.required)make('p','Причины проверки: '+x.review.causes.map(c=>c.sourceId+' @ '+c.sourceRevision).join(', '),d);
      }
      editForm();
    }
    fill();form.hidden=readOnly;
    return {focus:choose,get focusId(){return focusId;},projection:()=>coreFocusedView(g,focusId)};
  }

  function mount(container,transport,options={}){
    const doc=options.document||document,fields={},buttons={};
    let view=null,busy=false,pending=null,activeId=null,workspace=null,contextSelectionRequired=false;const cardControls=[];let graphStatus=null,graphRetry=null;
    const make=(tag,text,parent)=>{const x=doc.createElement(tag);if(text!==undefined)x.textContent=text;
      if(parent)parent.appendChild(x);return x;};
    const toolbar=make('div',undefined,container);toolbar.classList.add('wf-toolbar');
    const heading=make('h3','Данные плана',toolbar);
    const refresh=make('button','Обновить',toolbar);
    const jump=make('button','Перейти к плану ↓',toolbar);jump.classList.add('wf-jump-plan');
    jump.disabled=true;buttons.jumpPlan=jump;let firstPlannedCard=null;
    jump.onclick=()=>{
      if(!firstPlannedCard)return;
      const scrollRoot=container.closest?.('#workflow-page');
      const behavior=typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';
      if(scrollRoot?.scrollTo){
        const top=firstPlannedCard.getBoundingClientRect().top-scrollRoot.getBoundingClientRect().top+
          scrollRoot.scrollTop-toolbar.getBoundingClientRect().height-16;
        scrollRoot.scrollTo({top,behavior});
      }else firstPlannedCard.scrollIntoView?.({block:'start',behavior});
      firstPlannedCard.focus?.({preventScroll:true});
    };
    const status=make('div','Данные ещё не загружены. Нажмите «Обновить».',toolbar);status.classList.add('wf-status');status.setAttribute('role','status');
    // No admin bearer or token is stored in this UI. A trusted owner must
    // explicitly enable the optional admin endpoint when starting Helper.
    const modulePanel=make('details',undefined,container);modulePanel.classList.add('wf-modules');
    make('summary','Модули · в разработке',modulePanel);
    make('p','Экспериментальная подсистема. Используйте для разработки и проверки модулей.',modulePanel);
    const moduleList=make('div',undefined,modulePanel);
    function renderModules(){
      moduleList.replaceChildren();
      make('p','Базовый модуль · Requirements, Actions, история и Plan',moduleList);
      const all=view?.moduleCapabilities;
      if(!all){make('p','Для управления модулями подключите авторизованный Helper.',moduleList);return;}
      for(const scope of ['graph','plan']){
        const caps=all[scope];if(!caps)continue;
        for(const [mid,versions] of Object.entries(caps.available||{})){
          const enabled=Object.hasOwn(caps.enabled||{},mid);
          const row=make('p',scope+' · '+mid+' · '+(enabled?'включён':'выключен')+' ',moduleList);
          const button=make('button',enabled?'Отключить':'Подключить',row);
          const can=scope==='plan'?view.permissions?.includes('plan.edit'):
            view.permissions?.some(p=>p==='graph.write'||p==='graph.configure_modules');
          button.disabled=busy||!!pending||!!options.readOnly||!!options.localPreview||!can;
          button.onclick=()=>configureModule(scope,mid,!enabled);
        }
      }
    }
    async function configureModule(scope,mid,enable){
      if(busy||pending||!view)return;
      const caps=view.moduleCapabilities?.[scope];
      if(!caps?.available?.[mid])throw Error('Модуль недоступен в выбранной области');
      const modules={...caps.pinned};
      if(enable)modules[mid]??=Math.min(...caps.available[mid]);
      const disabled=new Set(caps.disabled||[]);
      if(enable)disabled.delete(mid);else disabled.add(mid);
      const owner=view.sources.graphs[view.graphFile];
      const random=randomId();
      return send({...(workspace?.contextId!=null?{contextId:workspace.contextId}:{}),
        action:scope==='plan'?'configure_plan_modules':'configure_graph_modules',
        transactionId:'ui-'+random,modules,disabledModules:[...disabled],
        note:(enable?'Подключение':'Отключение')+' модуля '+mid+' для '+scope,
        expectedGraphRevision:owner.revision,expectedPlanRevision:view.sources.plan.revision});
    }
    const grantPanel=make('details',undefined,container);grantPanel.classList.add('wf-grants');grantPanel.hidden=true;
    make('summary','Управление полномочиями',grantPanel);
    make('p','Только доверенная административная сессия. Новый токен показывается после выдачи; сохраните его самостоятельно.',grantPanel);
    const grantStatus=make('p','Нажмите «Просмотреть права».',grantPanel);grantStatus.setAttribute('role','status');
    const grantSelect=make('select',undefined,make('label','Выданный grant',grantPanel));
    grantSelect.setAttribute('aria-label','Выданный grant');
    const grantLabel=make('input',undefined,make('label','Метка полномочия',grantPanel));
    grantLabel.setAttribute('aria-label','Метка полномочия');
    make('p','Разрешение grant.admin не выдаётся через этот интерфейс; управление выдачей прав остаётся у владельца.',grantPanel);
    const grantPermissions=make('textarea',undefined,make('label','Разрешения — по одному в строке',grantPanel));
    grantPermissions.setAttribute('aria-label','Разрешения — по одному в строке');
    const grantScopes=make('textarea',undefined,make('label','Области доступа — по одной в строке',grantPanel));
    grantScopes.setAttribute('aria-label','Области доступа — по одной в строке');
    const grantRead=make('button','Просмотреть права',grantPanel);
    const grantIssue=make('button','Выдать токен',grantPanel);
    const grantAmend=make('button','Изменить выбранный grant',grantPanel);
    const grantRevoke=make('button','Отозвать выбранный grant',grantPanel);
    const grantRetry=make('button','Повторить тот же запрос',grantPanel);grantRetry.hidden=true;
    const grantSecret=make('code','',grantPanel);grantSecret.setAttribute('aria-label','Новый токен — одноразовый показ');
    const grantHide=make('button','Скрыть показанный токен',grantPanel);grantHide.onclick=()=>{grantSecret.textContent='';};
    let grants=[],grantRevision=null,grantBusy=false,grantPending=null;
    const lines=v=>v.split(/\r?\n|,/).map(x=>x.trim()).filter(Boolean);
    const grantSpec=()=>({label:grantLabel.value.trim(),permissions:lines(grantPermissions.value),scopes:lines(grantScopes.value)});
    const grantChoice=()=>grants.find(g=>g.id===grantSelect.value);
    function grantControls(){
      const ready=!grantBusy&&grantRevision!==null&&!grantPending;
      grantRead.disabled=grantBusy||!!grantPending;
      grantIssue.disabled=!ready;
      grantAmend.disabled=!ready||!grantChoice();grantRevoke.disabled=!ready||!grantChoice();
      grantRetry.hidden=!grantPending;grantRetry.disabled=grantBusy||!grantPending;
    }
    function grantRender(result){
      grants=(result.grants||[]).filter(g=>!g.owner);
      grantRevision=result.revision;
      const previous=grantSelect.value;
      grantSelect.replaceChildren();
      for(const g of grants){const option=make('option',g.id+' · '+(g.label||'Без метки')+(g.active?'':' · отозван'),grantSelect);option.value=g.id;}
      grantSelect.value=grants.some(g=>g.id===previous)?previous:(grants[0]?.id||'');
      grantFillSelected();grantControls();
    }
    function grantFillSelected(){
      const g=grantChoice();
      grantLabel.value=g?.label||'';
      grantPermissions.value=(g?.permissions||[]).join('\n');
      grantScopes.value=(g?.scopes||[]).join('\n');
    }
    grantSelect.onchange=()=>{
      grantSecret.textContent='';grantFillSelected();grantControls();
    };
    async function grantRefresh(){
      if(grantBusy||grantPending)return;
      grantBusy=true;grantControls();grantSecret.textContent='';
      try{grantRender(await transport.admin({operation:'list'}));grantStatus.textContent='Права перечитаны. Токены существующих grants не отображаются.';}
      catch(e){grantStatus.textContent='Не удалось прочитать права: '+e.message;}
      finally{grantBusy=false;grantControls();}
    }
    async function grantSend(req){
      if(grantBusy||!req)return;
      grantBusy=true;grantPending=req;grantControls();grantSecret.textContent='';
      let accepted;
      try{
        accepted=await transport.admin(req);
      }catch(e){
        // Only uncertainty about the mutation itself permits exact retry.
        if(e.definite)grantPending=null;
        grantStatus.textContent=(e.definite?'Запрос отклонён: ':'Исход запроса неизвестен; повторите тот же запрос: ')+e.message;
        grantBusy=false;grantControls();return;
      }
      grantPending=null;
      if(req.operation==='issue'&&accepted.token){
        grantSecret.textContent='Новый токен (сохраните сейчас): '+accepted.token;
      }
      const outcome=accepted.replayed?'Повтор подтверждён, дополнительного grant нет.':'Изменение полномочий принято.';
      try{
        // Refresh is independent of the already accepted mutation. A failed
        // refresh must not call the mutation uncertain or enable its retry.
        const listed=await transport.admin({operation:'list'});
        grantRender(listed);
        grantStatus.textContent=outcome;
      }catch(e){
        grantRevision=null; // Avoid a new mutation using an outdated grant revision.
        grantStatus.textContent=outcome+' Не удалось обновить список прав: '+e.message+' Нажмите «Просмотреть права».';
      }finally{grantBusy=false;grantControls();}
    }
    const newGrantRequest=operation=>{
      if(grantPending)return null;
      if(grantRevision===null)throw Error('Сначала просмотрите права.');
      const uuid=randomId();
      const request={operation,transactionId:'grant-ui-'+uuid,expectedRevision:grantRevision};
      if(operation==='issue')request.grant=grantSpec();
      else{if(!grantChoice())throw Error('Выберите существующий grant.');request.id=grantSelect.value;
        if(operation==='amend')request.grant=grantSpec();}
      return request;
    };
    function performGrant(operation){try{const request=newGrantRequest(operation);if(request)void grantSend(request);}
      catch(e){grantStatus.textContent=e.message;}}
    grantRead.onclick=()=>void grantRefresh();
    grantIssue.onclick=()=>performGrant('issue');
    grantAmend.onclick=()=>performGrant('amend');
    grantRevoke.onclick=()=>performGrant('revoke');
    grantRetry.onclick=()=>void grantSend(grantPending);
    const editor=make('details',undefined,container);editor.classList.add('wf-editor');editor.hidden=true;
    make('summary','Разместить из графа',editor);
    make('h3','Размещение цели или Action',editor);
    const grid=make('div',undefined,container);grid.classList.add('wf-grid');grid.classList.add('wf-timeline');grid.hidden=true;
    if(transport.setStatus)transport.setStatus(message=>{status.textContent=message;syncStatus();});
    const history=make('section',undefined,grid),future=make('section',undefined,grid),
      unplaced=make('section',undefined,grid);
    history.classList.add('wf-history');history.setAttribute('aria-label','История');
    future.classList.add('wf-future');future.setAttribute('aria-label','План во времени');
    unplaced.classList.add('wf-unplaced');unplaced.setAttribute('aria-label','Без места во времени');
    let fieldParent=editor;
    function field(name,label,tag='input',type='text'){
      const l=make('label',label,fieldParent),x=make(tag,undefined,l);
      if(tag==='input')x.type=type;x.value='';
      x.setAttribute('aria-label',label);fields[name]=x;return x;
    }
    field('graph','Граф с существующей целью или Action','select');
    const target=field('target','Цель или Action','select');
    const details=make('p','',editor);
    field('note','Основание изменения или результат выполнения','textarea');
    field('placement','Сохранённое размещение','select');
    field('at','Дата начала не ранее','input','date');
    field('after','После размещённой цели или Action','select');
    const placementDetails=make('p',undefined,editor);
    const planControls=make('div',undefined,editor);
    const graphEditor=make('details',undefined,options.graphContainer);
    make('summary','Редактировать граф / записать результат',graphEditor);
    graphEditor.open=!!options.graphContainer;
    graphStatus=make('div','',graphEditor);graphStatus.setAttribute('role','status');
    graphRetry=make('button','Повторить тот же запрос',graphEditor);graphRetry.onclick=()=>send(pending);
    function syncStatus(){if(graphStatus){graphStatus.textContent=status.textContent;graphStatus.classList.toggle('wf-error',!!status.classList.contains?.('wf-error'));}if(graphRetry){graphRetry.hidden=!pending;graphRetry.disabled=busy||!pending;}}
    const corePane=make('div',undefined,graphEditor);corePane.hidden=true;let coreEditor=null,coreFocusId=null;
    make('p','Изменения в подключённом графе. Размещение во времени выполняется на вкладке плана.',graphEditor);
    const graphTarget=make('select',undefined,make('label','Сущность графа',graphEditor));
    graphTarget.setAttribute('aria-label','Сущность редактируемого графа');
    const graphNote=make('textarea',undefined,make('label','Основание изменения или результат',graphEditor));
    graphNote.setAttribute('aria-label','Основание изменения графа');
    graphNote.oninput=()=>{fields.note.value=graphNote.value;};
    fields.note.oninput=()=>{graphNote.value=fields.note.value;};
    fieldParent=graphEditor;
    field('title','Название');
    field('actionType','Тип нового Action','select');
    field('recommended','Когда способ подходит — по одному случаю на строку','textarea');
    field('contraindicated','Когда способ не подходит','textarea');
    field('childRole','Роль новой дочерней R','select');
    field('qrpe','Новая запись QRPE');
    const childBox=make('div',undefined,graphEditor);make('p','При отзыве укажите судьбу каждой введённой R. Изменения примет только штатный writer.',childBox);
    const dispositionFields=[];
    const controls=make('div',undefined,graphEditor);
    function button(name,title,action){
      const b=make('button',title,['place','unplace'].includes(name)?planControls:controls);b.onclick=()=>run(action);buttons[name]=b;return b;
    }
    button('add','Создать вариант Action','add_action');button('title','Изменить название','edit_title');
    button('canon','Записать канон','edit_canon');button('requirement','Добавить дочернюю R','prepare_requirement');
    button('qrpe','Добавить QRPE','add_qrpe');button('select','Выбрать Action','select');
    button('complete','Записать выполнение / достижение','complete');button('withdraw','Отозвать выполненный Action','withdraw');
    button('place','Разместить / изменить место','place');button('unplace','Снять размещение','unplace');
    buttons.retry=make('button','Повторить тот же запрос',container);buttons.retry.onclick=()=>send(pending);
    buttons.refresh=refresh;refresh.onclick=()=>refreshView();
    function optionsFor(select,items,value){
      select.replaceChildren();for(const [id,title] of items){const o=make('option',title,select);o.value=id;}
      select.value=items.some(x=>x[0]===value)?value:(items[0]?.[0]||'');
    }
    optionsFor(fields.actionType,[['general','Обычный'],['decomposition','Выделение подцелей']],'general');
    optionsFor(fields.childRole,[['subgoal','Часть разбиения родительской цели'],['method_correctness','Нужно для корректного выполнения Action']],'subgoal');
    function selectedFile(){return fields.graph.value||view?.graphFile;}
    function graph(){return view?.sources.graphs[selectedFile()];}
    function fillTargets(id=activeId){
      optionsFor(target,(graph()?.nodes||[]).filter(n=>['action','requirement'].includes(n.kind)).map(n=>[n.id,n.title+' · '+n.kind+' · '+(n.status||'active')]),id);
      focus();
    }
    fields.graph.onchange=()=>fillTargets(null);
    graphTarget.onchange=()=>{fields.graph.value=view.graphFile;fillTargets(graphTarget.value);};
    function selected(){return graph()?.nodes.find(n=>n.id===target.value);}
    function updateControls(){
      renderModules();
      const n=selected(),perms=view?.permissions||[],graphWrite=p=>selectedFile()===view?.graphFile&&(perms.includes('graph.write')||perms.includes('graph.'+p));
      const protectedGraph=view&&Object.values(view.sources.graphs).some(g=>g.nodes.some(n=>n.reconsiderationPolicy?.mode==='protected'));
      jump.disabled=!view||!firstPlannedCard;
      const locked=busy||!!pending||!view,own=n&&!n.projectionOf,executed=graph()?.events.some(e=>e.type==='action_executed'&&e.targetId===n?.id);
      const policy=protectedGraph||!own;
      const canDrive=own||n?.id===view?.continuationRootId;
      buttons.add.disabled=locked||protectedGraph||!canDrive||n?.kind!=='requirement'||!graphWrite('add_action');
      buttons.title.disabled=locked||policy||!graphWrite('graph_edit.edit_node');
      buttons.canon.disabled=locked||policy||n?.kind!=='action'||!graphWrite('graph_edit.edit_node');
      buttons.requirement.disabled=locked||policy||n?.kind!=='action'||!graphWrite('graph_edit.prepare_action_requirement');
      buttons.qrpe.disabled=locked||policy||!graphWrite('append_qrpe');
      buttons.select.disabled=locked||policy||n?.kind!=='action'||n.status!=='candidate'||!graphWrite('select_action');
      buttons.complete.disabled=locked||policy||executed||n?.status==='superseded'||
        !graphWrite(n?.kind==='action'?'record_action_execution':'record_requirement_achievement');
      buttons.withdraw.disabled=locked||policy||n?.kind!=='action'||n.status!=='selected'||!executed||!graphWrite('withdraw_action');
      buttons.place.disabled=locked||!n||!perms.includes('plan.edit')||placementState().complex||
        (n.kind==='action'&&n.status!=='selected');
      buttons.unplace.disabled=locked||!fields.placement.value||!perms.includes('plan.edit');
      for(const control of cardControls)control.button.disabled=locked||!perms.includes('plan.edit')||!control.allowed;
      buttons.retry.hidden=!pending;buttons.retry.disabled=busy||!pending;buttons.refresh.disabled=busy;
      syncStatus();
      if(options.onStateChange)options.onStateChange({busy,pending:!!pending,ready:!!view});
    }
    function placementState(){
      const plan=view?.sources.plan,chosen=plan?.steps.find(s=>s.id===fields.placement.value);
      const rules=chosen?(plan.timeConstraints||[]).filter(r=>r.stepId===chosen.id):[];
      const starts=rules.filter(r=>r.type==='notBefore');
      const incoming=chosen?(plan.sequence||[]).filter(e=>e.after===chosen.id):[];
      return {chosen,rules,starts,incoming,complex:starts.length>1||incoming.length>1||
        starts.some(r=>!/^\d{4}-\d{2}-\d{2}$/.test(r.at))};
    }
    function loadPlacement(){
      const p=placementState();
      fields.at.value=p.starts.length===1&&!p.complex?p.starts[0].at:'';
      const steps=view.sources.plan.steps.filter(s=>s.id!==p.chosen?.id);
      optionsFor(fields.after,[['','Без порядка'],...steps.map(s=>[s.id,s.title])],
        p.incoming.length===1?p.incoming[0].before:'');
      placementDetails.textContent=p.complex?'Сложное размещение: измените его через полный API. Сохранённые правила не будут обрезаны.':
        p.rules.map(r=>(r.type==='deadline'?'Срок до ':'Начать не ранее ')+r.at+' ['+r.strength+']').join('; ')+
        (p.incoming[0]?.minDelayDays!==undefined?' · Интервал после предшественника: '+p.incoming[0].minDelayDays+' дн.':'');
      updateControls();
    }
    function focus(){
      const n=selected();if(!n)return;activeId=n.id;
      if(selectedFile()===view.graphFile)graphTarget.value=n.id;
      graphNote.value=fields.note.value;
      fields.title.value=n.title;
      fields.recommended.value=(n.canonBlock?.recommended||[]).map(c=>c.text).join('\n');
      fields.contraindicated.value=(n.canonBlock?.contraindicated||[]).map(c=>c.text).join('\n');
      const completion=view.sources.completion?.[selectedFile()]?.[n.id];
      details.textContent=n.id+' · '+n.kind+' · '+(n.status||'active')+
        (completion?.complete&&!completion.historyPending?' · выполнено':completion?.historyPending?' · результат ожидает записи writer':' · не завершено')+
        (n.projectionOf&&completion?.ownerRef?' · владелец: '+completion.ownerRef.graphFile:'')+
        (n.qrpe?.length?'\nQRPE: '+n.qrpe.map(q=>'['+q.status+'] '+q.text).join('; '):'')+
        (n.reconsiderationPolicy?.mode==='protected'?' · защищено: ручная запись недоступна':'');
      const placements=view.sources.plan.steps.filter(s=>{
        const ref=s.actionRef||s.requirementRef;
        return ref?.nodeId===n.id&&ref.graphFile===selectedFile()&&ref.identitySpace===graph().identitySpace;
      });
      optionsFor(fields.placement,[['','Выберите размещение'],...placements.map(s=>[s.id,s.title+' · '+s.id])],
        placements.length===1?placements[0].id:'');
      loadPlacement();
      childBox.replaceChildren();dispositionFields.length=0;
      for(const e of graph().edges.filter(e=>e.type==='INTRODUCES'&&e.from===n.id&&!e.archived)){
        const row=make('label',graph().nodes.find(n=>n.id===e.to)?.title||e.to,childBox);
        const select=make('select',undefined,row);optionsFor(select,[['','Выберите судьбу R'],['retain_supported','Сохранить: поддержана другим выбранным Action'],['deactivate','Деактивировать: нет других зависимостей']],'');
        dispositionFields.push({id:e.to,select});
      }
      updateControls();
    }
    target.onchange=focus;fields.placement.onchange=loadPlacement;
    function reference(file,id){return {graphFile:file,identitySpace:view.sources.graphs[file]?.identitySpace,nodeId:id};}
    function nodeAt(ref){return view.sources.graphs[ref.graphFile]?.identitySpace===ref.identitySpace?
      view.sources.graphs[ref.graphFile].nodes.find(n=>n.id===ref.nodeId):null;}
    function editPlacement(ref,stepId){
      if(!view.sources.graphs[ref.graphFile]||!nodeAt(ref))return;
      if(ref.graphFile!==view.graphFile&&!view.capabilities?.includes('plan.place.from-read-sources')){status.textContent='Для размещения из другого графа обновите локальный Helper.';return;}
      fields.graph.value=ref.graphFile;fillTargets(ref.nodeId);
      if(stepId){fields.placement.value=stepId;loadPlacement();}
      editor.open=true;editor.scrollIntoView?.({block:'nearest',behavior:'smooth'});
    }
    async function navigate(ref){
      try{
        const origin=declarationFor(view,ref);
        if(origin.ref.graphFile===view.graphFile||view.capabilities?.includes('plan.place.from-read-sources')){fields.graph.value=origin.ref.graphFile;fillTargets(origin.ref.nodeId);}
        if(!options.onNavigate)throw Error('Переход доступен в подключённом Viewer');
        await options.onNavigate(origin.ref,view);
      }catch(e){status.textContent='Не удалось открыть объявление: '+e.message;status.classList.add('wf-error');}
    }
    function declarationLink(parent,ref,label='Открыть блок в графе ↗'){
      let verified=null,problem=null;
      try{verified=declarationFor(view,ref);}catch(error){problem=error.message;}
      const button=make('button',label,parent);button.classList.add('wf-open-graph');
      button.setAttribute('data-node-id',ref.nodeId);
      button.setAttribute('data-graph-file',ref.graphFile);
      button.disabled=!verified||!options.onNavigate;
      button.title=verified?'Открыть объявление и выделить блок в графе':
        'Переход недоступен: '+(problem||'Viewer не подключён');
      button.onclick=()=>navigate(ref);
      return button;
    }
    const refKey=ref=>[ref.graphFile,ref.identitySpace,ref.nodeId].join('|');
    function entityKey(ref){try{return refKey(declarationFor(view,ref).ref);}catch{return refKey(ref);}}
    function material(card,node,historical=false){
      if(node.kind==='action'||node.kind==='option'){
        const canon=make('details',undefined,card);canon.classList.add('wf-canon');
        canon.open=!historical;
        const positive=node.canonBlock?.recommended||[],negative=node.canonBlock?.contraindicated||[];
        make('summary',(node.kind==='option'?'Канон варианта решения':historical?'Канон на момент записи':'Канон Action')+' (+'+positive.length+'/−'+negative.length+')',canon);
        for(const [label,rows] of [['Когда подходит',positive],['Когда не подходит',negative]]){
          const block=make('div',undefined,canon);block.classList.add('wf-canon-case');
          block.setAttribute('data-valence',label==='Когда подходит'?'positive':'negative');
          make('strong',label,block);const ul=make('ul',undefined,block);
          if(!rows.length)make('li','Не заполнено',ul);
          for(const c of rows)make('li',c.text,ul);
        }
      }
      const issues=node.qrpe||[],open=issues.filter(q=>!['closed','resolved','invalidated'].includes(q.status));
      const qrpe=make('details',undefined,card);qrpe.classList.add('wf-qrpe');qrpe.open=!historical&&open.length>0;
      make('summary',(historical?'QRPE на момент записи':'QRPE')+' · '+open.length+' открыто / '+issues.length,qrpe);
      if(!issues.length)make('p','Записей QRPE нет.',qrpe);
      for(const q of issues)make('p','['+q.status+'] '+q.text,qrpe);
      if(historical&&open.length){const warning=make('p',open[0].text,card);warning.classList.add('wf-qrpe-preview');}
    }
    function card(parent,ref,{row=null,variant=false,historical=false,event=null,title=null,variants=true}={}){
      const local=nodeAt(ref);let origin=null;try{origin=declarationFor(view,ref);}catch{}
      const n=historical?(event?.nodeSnapshot||local):origin?.node||local;
      if(!n){make('p','Узел недоступен: '+ref.nodeId,parent);return;}
      const article=make('article',undefined,parent);article.classList.add('wf-card');article.classList.add(n.kind);
      article.setAttribute('data-node-id',n.id);article.setAttribute('data-graph-file',ref.graphFile);
      article.setAttribute('data-status',n.status||'active');
      article.setAttribute('data-placement-id',row?.stepId||'');article.setAttribute('data-context',variant?'variant':historical?'history':'placement');
      const kind=n.kind==='action'?'Action / способ':n.kind==='option'?'Option / вариант решения':'R / цель';
      const state={selected:'выбран',candidate:'кандидат',potential:'предварительная',active:'активная',superseded:'пересмотрен',inactive:'неактивная'}[n.status]||n.status||'';
      const placements=view.future.filter(r=>entityKey(r.graphRef||reference(view.graphFile,r.nodeId))===entityKey(ref));
      const isPlaced=placements.length>0;
      const meta=make('small',undefined,article);meta.classList.add('wf-card-meta');
      make('span',kind,meta).classList.add('wf-kind-badge');
      if(state)make('span',historical?'На момент записи: '+state:state,meta).classList.add('wf-state-badge');
      if(variant){
        const chosen=n.kind==='option'&&origin?.graph?.nodes?.some(d=>d.kind==='decision'&&
          d.selectedOptionId===n.id&&['committed','selected-in-example-only'].includes(d.status));
        make('span',n.kind==='option'?(chosen?'выбран в Decision (не Action)':'альтернатива Decision'):
          isPlaced?'размещён отдельно':'вариант Action, не размещён',meta);
      }
      if(event){
        article.setAttribute('data-event-kind',event.kind);classifyEvent(article,event);
        make('span',eventLabels[event.kind]||event.kind,meta).classList.add('wf-event-badge');
        eventTime(article,event.recordedAt);
      }
      const open=make('button',title||n.title,article);open.classList.add('wf-card-title');open.onclick=()=>navigate(ref);
      open.disabled=!origin||!options.onNavigate;open.title=origin?'Открыть место объявления в графе':'Объявление недоступно в подключённой сессии';
      make('small',n.id,article);
      if(n.kind==='action'&&origin&&!variant){
        const goalRef={...origin.ref,nodeId:origin.contextRootId},goal=nodeAt(goalRef);
        if(goal){
          const context=make('p','Для цели: ',article),link=make('button',goal.title,context);link.classList.add('wf-card-goal');
          link.onclick=()=>navigate(goalRef);link.disabled=!options.onNavigate;
          if(!view.future.some(r=>entityKey(r.graphRef||reference(view.graphFile,r.nodeId))===entityKey(goalRef)))
            make('small','Цель показана для контекста и не размещена.',context);
        }
      }
      if(row){
        for(const rule of row.timeConstraints||[])make('p',(rule.type==='deadline'?'Срок до ':'Начать не ранее ')+rule.at+' ['+rule.strength+']',article);
        for(const link of row.sequence||[]){
          const sid=link.after===row.stepId?link.before:link.after,step=view.sources.plan.steps.find(s=>s.id===sid);
          const targetRef=step?.actionRef||step?.requirementRef,other=targetRef&&nodeAt(targetRef);
          make('p',(link.after===row.stepId?'После: ':'Перед: ')+(other?.title||step?.title||sid)+
            (link.minDelayDays!==undefined?' · интервал '+link.minDelayDays+' дн.':''),article);
        }
      }
      if(event?.note){const note=make('p',event.note,article);note.classList.add('wf-result-note');}
      if(historical&&!event?.materialSnapshotAvailable)
        make('p','Канон и QRPE на момент записи не сохранены. Текущий материал доступен по переходу в граф.',article);
      else if(historical||origin||!n.projectionOf)material(article,n,historical);
      else make('p','Канон и QRPE владельца недоступны в этой сессии.',article);
      if(!variant)declarationLink(article,ref);
      if(!historical&&!options.readOnly&&n.kind!=='option'){
        const placement=row||(variant?placements[0]:null),placementRef=placement?.graphRef||ref;
        const edit=make('button',variant&&!isPlaced?'Разместить':variant&&placements.length>1?'К первому размещению':'Изменить размещение',article);
        const selectable=n.kind!=='action'||n.status==='selected';
        edit.disabled=!selectable||busy||!!pending||!(view.permissions||[]).includes('plan.edit');
        edit.onclick=()=>editPlacement(placementRef,placement?.stepId);edit.classList.add('wf-card-place');
        const inAuthorizedGraph=placementRef.graphFile===view.graphFile||!!view.capabilities?.includes('plan.place.from-read-sources');
        const allowed=selectable&&inAuthorizedGraph;
        cardControls.push({button:edit,allowed});if(!allowed){edit.disabled=true;
          edit.title=!selectable?'Сначала выберите Action в графе. Сам Plan не выбирает Action.':
            'Для размещения из другого графа обновите локальный Helper';}
      }
      if(variants&&origin&&['requirement','action'].includes(n.kind)){
        const alternatives=[],seen=new Set();
        const context=origin.contextRootId;
        for(const [file,source] of Object.entries(view.sources.graphs)){
          if(source.identitySpace!==origin.ref.identitySpace)continue;
          const driverIds=n.kind==='requirement'?[n.id]:[context];
          for(const edge of source.edges.filter(e=>['DRIVES','OPTION_FOR'].includes(e.type)&&
              driverIds.includes(e.from)&&!e.archived)){
            const child=source.nodes.find(a=>a.id===edge.to&&
              ['action','option'].includes(a.kind));
            // Retired alternatives are still helpful for comparing canons;
            // their status is shown, never converted to Plan placement.
            if(!child||child.id===n.id)continue;
            const ref=reference(file,child.id),key=refKey(ref);
            if(!seen.has(key)){seen.add(key);alternatives.push({node:child,ref});}
          }
        }
        if(alternatives.length){
          const chain=make('details',undefined,article);chain.classList.add('wf-variants');
          chain.open=true;
          const kinds=new Set(alternatives.map(a=>a.node.kind));
          const text=kinds.has('action')?'Способы Action для этой цели — канон каждого, выбор ≠ выполнение':
            'Варианты Decision — канон каждого; это не исполняемые Actions';
          make('summary',text+' · '+alternatives.length,chain);
          const list=make('div',undefined,chain);list.classList.add('wf-variant-list');
          for(const alternative of alternatives)card(list,alternative.ref,{variant:true,historical:false,variants:false});
        }
      }
      return article;
    }
    function classifyEvent(article,event){
      const description={
        graph_created:['НОВЫЙ GRAPH','Создан действительный Graph owner, не выполнена цель'],
        context_added:['ДОБАВЛЕН КОНТЕКСТ','Сохранено основание/условие выбора способа, не Action и не подцель'],
        context_link_added:['КОНТЕКСТНАЯ СВЯЗЬ','Контекст подключён к Action и показывается в полном режиме связей'],
        action_added:['НОВЫЙ ACTION','Добавлен способ-кандидат. Это не выбор и не выполнение'],
        requirement_added:['НОВАЯ R','Добавлено активное объявление Requirement. Это не достижение'],
        requirement_prepared:['ПОТЕНЦИАЛЬНАЯ R','Создан кандидат/потенциальная R, ещё не введённая выбранным Action'],
        requirement_activated:['АКТИВИРОВАНА R','Requirement переведена в активное состояние. Это не достижение'],
        requirement_deactivated:['ДЕАКТИВИРОВАНА R','Requirement исключена из активной работы, но история сохранена'],
        action_removed:['УДАЛЁН ACTION','Удалена декларация Action — не исполнение и не отзыв результата'],
        requirement_removed:['УДАЛЕНА R','Удалена декларация Requirement — не достигнута цель'],
      };
      const diff=event.kind==='graph_saved'&&description[event.changeKind];
      const family=diff?{...historyKind(event.kind),label:diff[0],description:diff[1]}:
        historyKind(event.kind);
      article.classList.add('wf-event-'+family.group);
      article.setAttribute('data-event-family',family.group);
      const head=article.querySelector?.('.wf-card-meta')||article;
      const badge=make('span',family.label,head);badge.classList.add('wf-event-family');
      badge.title=family.description;
      if(event.exampleOnly)make('small','Учебное событие, не подтверждённое журналом владельца',article);
    }
    function renderReformulation(parent,r){
      if(r.kind!=='requirement_reformulated')return;
      const section=make('section',undefined,parent);section.classList.add('wf-reformulation');
      const before=r.previousRequirementSnapshot||r.nodeSnapshot;
      const after=r.newRequirementSnapshot;
      if(!before||!after){make('p','Исторический снимок «было / стало» недоступен; не реконструируем его из текущего графа.',section);return;}
      make('strong','Переформулировка Requirement · '+r.targetId,section);
      for(const field of new Set([...Object.keys(before),...Object.keys(after)])){
        if(['id','kind','revision'].includes(field)||JSON.stringify(before[field])===JSON.stringify(after[field]))continue;
        make('p','Было ('+field+'): '+(typeof before[field]==='object'?JSON.stringify(before[field]):before[field]??'—'),section);
        make('p','Стало ('+field+'): '+(typeof after[field]==='object'?JSON.stringify(after[field]):after[field]??'—'),section);
      }
      make('small','Событие изменения Graph. Зависимые Actions и каноны требуют повторной проверки в Gendocen.',section);
    }
    function renderReconsideration(parent,r){
      if(r.kind!=='action_reconsidered')return;
      const panel=make('div',undefined,parent);panel.classList.add('wf-action-switch');
      const transition=r.transition;
      if(!transition){
        make('p','Action пересмотрен. Механизм отмены последствий и новый способ не указаны в исторической записи.',panel);
        return;
      }
      const actionName=id=>Object.values(view.sources?.graphs||{}).flatMap(g=>g.nodes||[])
        .find(n=>n.id===id)?.title||id;
      make('strong','Смена: '+actionName(r.targetId)+' → '+actionName(transition.replacementActionId),panel);
      const cancellation=transition.cancellation;
      if(cancellation?.mode==='no_additional_action')
        make('p','Отмена последствий: дополнительных действий не потребовалось (зафиксированная оценка). '+cancellation.reason,panel);
      else if(cancellation?.mode==='compensating_action')
        make('p','Отмена последствий: выполнен Action «'+actionName(cancellation.actionId)+'».'+
          ' Событие результата: '+cancellation.executionEventId+'. '+cancellation.reason,panel);
      make('small','Пересмотр, выбор замены и компенсация — разные факты. Запись пересмотра не выполняет действий.',panel);
    }
    const changeLabels={graph_created:'Создан рабочий Graph',
      context_added:'Добавлен контекст',context_link_added:'Установлена связь контекста с Action',
      action_added:'Добавлен кандидат Action',
      requirement_added:'Создана Requirement',requirement_prepared:'Подготовлена Requirement',
      requirement_activated:'Активирована Requirement',requirement_deactivated:'Деактивирована Requirement',
      action_removed:'Удалён Action',
      requirement_removed:'Удалена Requirement'};
    function historicalDisplay(historyRows){
      // A writer transaction may yield one technical graph_saved row and one
      // semantic Action/Requirement event. Keep both in provenance, show one
      // primary operation card with an expandable technical save record.
      const technical=new Map(),semantic=new Set();
      const transactionKey=r=>r.transactionId&&r.graphFile?
        r.transactionId+'\0'+r.graphFile:null;
      for(const row of historyRows){
        const key=transactionKey(row);if(!key)continue;
        if(row.kind==='graph_saved')technical.set(key,row);
        else if(!row.kind.startsWith('plan_'))semantic.add(key);
      }
      const retained=new Set();
      return historyRows.flatMap(row=>{
        const key=transactionKey(row);
        if(row.kind==='graph_saved'&&key&&semantic.has(key))return [];
        if(key&&row.kind!=='graph_saved'&&semantic.has(key)&&!retained.has(key)){
          retained.add(key);
          return [{...row,technicalSave:technical.get(key)||null}];
        }
        return [row];
      });
    }
    function renderIntroducedRequirements(article,r){
      if(r.kind!=='action_selected')return;
      const section=make('section',undefined,article);section.classList.add('wf-introduced-requirements');
      if(!Array.isArray(r.introducedRequirements)){
        make('small','Снимок введённых подцелей из транзакции недоступен. Не восстанавливаем их по текущему графу.',section);
        return;
      }
      if(!r.introducedRequirements.length){
        make('small','Выбор Action не вводил новых Requirements в этой транзакции.',section);
        return;
      }
      make('strong','В рамках этого выбора введены Requirements:',section);
      for(const item of r.introducedRequirements){
        const mode=item.introductionMode==='created'?'создана и активирована':
          item.introductionMode==='activated'?'активирована из '+item.previousStatus:
          'связана с Action (уже существовала)';
        const role=item.childRole==='subgoal'?'Подцель':
          item.childRole==='method_correctness'?'Проверка корректности способа':'Requirement';
        const line=make('div',undefined,section);line.classList.add('wf-introduced-requirement');
        make('span',role+' '+item.nodeId+' — '+mode+' · '+item.title,line);
        const linked=reference(item.graphFile||r.graphFile||view.graphFile,item.nodeId);
        if(nodeAt(linked))declarationLink(line,linked,'Открыть R в графе ↗');
        else make('small','Ранее введённый узел недоступен в подключённом Graph owner.',line);
      }
      make('small','Введение или активация подцели ≠ размещение во времени и ≠ достижение цели.',section);
    }
    function renderSaveDetails(article,r){
      const save=r.technicalSave||(r.kind==='graph_saved'?r:null);
      if(!save)return;
      const detail=make('details',undefined,article);detail.classList.add('wf-save-details');
      make('summary','Технические сведения о транзакции',detail);
      const prev=save.previousRevision;
      const revision=save.revision;
      if(revision!=null)make('p','Ревизия Graph: '+(prev==null?'создание → ':'r'+prev+' → ')+'r'+revision,detail);
      if(save.transactionId)make('p','Транзакция: '+save.transactionId,detail);
      if(save.changed){
        const listed=save.changed.nodes||[];
        if(listed.length)make('p','Затронутые узлы: '+listed.join(', '),detail);
        if(save.changed.edges?.length)make('p','Затронутые связи: '+save.changed.edges.join(', '),detail);
      }
      make('small','Сведения из принятого журнала writer. Дополнительного выполнения Action эта запись не означает.',detail);
    }
    const eventLabels={module_event:'Событие модуля',module_plan_changed:'Изменение Plan модулем',
      modules_configured:'Изменено подключение модулей',graph_saved:'Изменён граф',action_executed:'Выполнен Action',
      requirement_achieved:'Достигнута цель',action_withdrawn:'Отозван Action',
      decision_selected:'Учебный выбор решения',context_discovered:'Выявлен контекст',
      requirement_reparented:'Уточнена связь Requirement',
      plan_created:'Создан Plan',plan_placement_saved:'Размещён шаг Plan',
      plan_placement_removed:'Удалено размещение Plan',
      requirement_reformulated:'Переформулирована Requirement',
      requirement_deactivated:'Requirement деактивирована',
      requirement_activated:'Requirement активирована',action_selected:'Выбран Action',
      action_reconsidered:'Action пересмотрен',action_requirement_linked:'Связан Action и Requirement',
      decision_revised:'Решение пересмотрено'};
    function eventTime(parent,at){
      const time=make('time',undefined,parent);time.classList.add('wf-event-time');
      const value=at&&new Date(at);
      time.textContent=value&&!Number.isNaN(value.getTime())?
        'Записано '+value.toLocaleString('ru-RU',{dateStyle:'medium',timeStyle:'short'}):
        (at&&/^T[0-9]+$/.test(at)?'Учебный момент '+at:'Время записи неизвестно');
      if(at&&!/^T[0-9]+$/.test(at))time.setAttribute('datetime',at);
      if(at)time.title=at;
    }
    function renderPlan(){
      cardControls.length=0;firstPlannedCard=null;
      history.replaceChildren();make('h3','История',history);
      if(!view.history.length)make('p',view.localPreview&&!view.examplePreview?'В доступных событиях графа записей нет; журнал writer не загружен.':'Записей ещё нет.',history);
      let lastDay=null;
      for(const r of historicalDisplay(view.history)){
        const date=r.recordedAt&&new Date(r.recordedAt),valid=date&&!Number.isNaN(date.getTime());
        const day=valid?date.toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'}):
          r.symbolicTime?'Учебная последовательность':'Без времени записи';
        if(day!==lastDay){const divider=make('h4',day,history);divider.classList.add('wf-day');lastDay=day;}
        const ref=reference(r.graphFile||view.graphFile,r.targetId),node=nodeAt(ref);
        if(historyKind(r.kind).group==='result'&&
          ['action','requirement'].includes((r.nodeSnapshot||node)?.kind)){
          card(history,ref,{historical:true,event:r,title:r.title||r.nodeSnapshot?.title||node?.title,variants:false});
        }else{
          const event=make('article',undefined,history);event.classList.add('wf-history-event');event.classList.add('wf-card');
          event.setAttribute('data-context','history');event.setAttribute('data-event-kind',r.kind);
          if(r.changeKind)event.setAttribute('data-change-kind',r.changeKind);
          classifyEvent(event,r);
          make('strong',(r.kind==='graph_saved'&&changeLabels[r.changeKind])||eventLabels[r.kind]||r.kind,event);
          eventTime(event,r.recordedAt||r.symbolicTime);
          make('p',r.summary||r.title||r.note||'Запись об изменении графа.',event);
          if(r.kind==='graph_saved'&&r.note&&r.note!==r.summary)
            make('p','Заметка автора: '+r.note,event);
          renderReformulation(event,r);
          renderReconsideration(event,r);
          renderIntroducedRequirements(event,r);
          renderSaveDetails(event,r);
          const links=make('div',undefined,event);links.classList.add('wf-changed-nodes');
          const ids=[...(r.changed?.nodes||[]),...(r.technicalSave?.changed?.nodes||[]),
            r.changeTargetId,r.targetId,r.actionId,r.requirementId,
            r.reviewActionId,r.transition?.replacementActionId,r.transition?.cancellation?.actionId];
          for(const id of new Set(ids.filter(Boolean))){
            const changedRef=reference(r.graphFile||view.graphFile,id),changed=nodeAt(changedRef);
            if(!changed||!['action','requirement'].includes(changed.kind))continue;
            declarationLink(links,changedRef,'Открыть блок в графе ↗ '+changed.title);
          }
          if(r.note&&r.note!==(r.summary||r.title)){const note=make('p',r.note,event);note.classList.add('wf-result-note');}
          if(r.targetId&&!node)make('small','Узел '+r.targetId+' недоступен в подключённом графе.',event);
        }
      }
      future.replaceChildren();
      const boundary=make('header',undefined,future);boundary.classList.add('wf-plan-boundary');
      make('small','Конец истории · далее запланированное',boundary);
      make('h3','План во времени',boundary);
      if(view.examplePreview&&view.relatedActionExampleSlug&&options.onOpenExample){
        const jumpExample=make('button','Открыть отдельный учебный граф с Actions и их канонами →',boundary);
        jumpExample.classList.add('wf-example-switch');
        jumpExample.onclick=()=>options.onOpenExample(view.relatedActionExampleSlug);
      }
      make('p',view.examplePreview?(view.authoredExamplePreview?
        'Учебный снимок: явно размещённые шаги · '+view.future.length+' (не пользовательский Plan owner).':
        'Учебный пример: запланированных шагов нет. Это пример графа, не сохранённый пользовательский Plan.'):
        view.localPreview?'Сохранённый Plan owner не подключён; размещения не подтверждены.':
        view.future.length?'Явно размещённые цели и Actions · '+view.future.length:
        'Пока нет запланированных целей или Actions.',boundary);
      for(const row of view.future){
        const article=card(future,row.graphRef||reference(view.graphFile,row.nodeId),{row});
        if(!firstPlannedCard&&article){firstPlannedCard=article;article.setAttribute('tabindex','-1');}
      }
      if(view.unresolved.length)make('p','Не разрешены ссылки: '+view.unresolved.map(r=>r.nodeId).join(', '),future);
      unplaced.replaceChildren();
      const inventory=planningInventory(view);
      const group=make('details',undefined,unplaced);group.classList.add('wf-unplaced-group');
      const summary=make('summary','Без места во времени · '+inventory.unplaced.length,group);
      summary.title='Актуальные цели и выбранные Actions, которым ещё не задано место в Plan';
      group.open=inventory.unplaced.length<=16;
      make('p','Сущности из Graph без размещения в Plan. Это НЕ доказательство их невыполнения. Выполнение определяется только настоящими событиями и расчётом зависимостей Graph.',group);
      const list=make('div',undefined,group);list.classList.add('wf-unplaced-list');
      for(const row of inventory.unplaced){
        const ref={graphFile:row.graphFile,identitySpace:row.identitySpace,nodeId:row.nodeId};
        const article=card(list,ref,{variants:true});
        if(!article)continue;
        article.classList.add('wf-unplaced-card');
        make('small',row.verification==='completion-not-verified'?
          'Результат не проверен по writer':'Результат пока не подтверждён',article);
      }
      if(inventory.needsVerification.length)
        make('p','Требуют проверки результата/журнала: '+inventory.needsVerification.length+
          '. Не помечены выполненными автоматически.',unplaced);
      jump.disabled=!firstPlannedCard;
      jump.title=firstPlannedCard?'Перейти к первому запланированному блоку':'В плане пока нет доступных блоков';
    }
    async function install(next){
      view=next;
      optionsFor(fields.graph,Object.entries(view.sources.graphs).filter(([file,g])=>g.identitySpace===view.sources.graphs[view.graphFile].identitySpace&&(file===view.graphFile||view.capabilities?.includes('plan.place.from-read-sources')))
        .map(([file,g])=>[file,(g.title||file)+' · '+file]),fields.graph.value||view.graphFile);
      optionsFor(graphTarget,view.sources.graphs[view.graphFile].nodes.filter(n=>['action','requirement'].includes(n.kind)).map(n=>[n.id,n.title+' · '+n.id]),activeId);
      fillTargets();renderPlan();
      heading.textContent=view.title;grid.hidden=false;editor.hidden=!!options.readOnly;
      grantPanel.hidden=!!options.readOnly||!view.grantAdminAvailable||!transport.admin;
      if(grantPanel.hidden){grantSecret.textContent='';grants=[];grantRevision=null;grantPending=null;}
      grantControls();
      const owner=view.sources.graphs[view.graphFile],core=owner.coreModel==='rdg-core-v1';
      for(const child of graphEditor.children)if(child!==corePane&&child.tagName?.toLowerCase()!=='summary')child.hidden=core;
      corePane.hidden=!core;
      if(core){corePane.replaceChildren();coreEditor=mountCore(corePane,owner,{document:doc,readOnly:!!options.readOnly,
        focusId:coreFocusId,onFocus:id=>{coreFocusId=id;},onCommand:async request=>{
          if(workspace?.contextId!=null)request.contextId=workspace.contextId;
          const result=await send(request);if(!result?.saved)throw Error(status.textContent);return result;}});}
      if(options.onGraph)await options.onGraph(owner,view);
    }
    async function refreshView(){
      if(contextSelectionRequired&&!workspace){updateControls();return;}
      if(busy)return;busy=true;updateControls();status.textContent=options.localPreview?'Открываю учебную временную ленту…':options.readOnly?'Открываю учебный план…':'Запрашиваю данные локального Helper…';syncStatus();
      try{
        const next=await transport.read(workspace?.contextId);
        if(workspace){
          if(next.graphFile!==workspace.graphFile||
            (workspace.planFile!=null&&next.planFile!==workspace.planFile)||
            next.sources?.graphs?.[next.graphFile]?.identitySpace!==workspace.identitySpace||
            (workspace.contextId!=null&&next.contextId!==workspace.contextId))
            throw Error('PLAN_WORKSPACE_IDENTITY_MISMATCH: Helper вернул другой рабочий граф.');
        }
        await install(next);
        status.textContent=next.storedPlanReadOnly?'Сохранённый Plan из файла · только чтение; полный журнал истории и результаты выполнения требуют Helper.':options.localPreview?(next.examplePreview?'Учебный пример · только чтение; собственный Plan-файл у примера отсутствует.':'Нет подключённого Plan owner; размещения не подтверждены.'):options.readOnly?'Учебный снимок · только чтение.':'Данные перечитаны.';status.classList.remove('wf-error');
      }
      catch(e){status.textContent='Не удалось загрузить данные: '+e.message+(view?' Показаны ранее загруженные данные.':'');status.classList.add('wf-error');}
      finally{busy=false;updateControls();}
    }
    async function switchWorkspace(next,missingMessage='Для этого рабочего графа план пока не подключён.'){
      if(busy||pending||grantBusy||grantPending)throw Error('Завершите прежний запрос перед переключением рабочего графа.');
      // Drop the previous source *before* attempting a new read. An error
      // must never leave another workspace's Plan visible or writable.
      contextSelectionRequired=true;workspace=next;view=null;activeId=null;heading.textContent=next?.title||'План во времени';
      grid.hidden=true;editor.hidden=true;grantPanel.hidden=true;grantSecret.textContent='';
      grants=[];grantRevision=null;firstPlannedCard=null;
      history.replaceChildren();future.replaceChildren();unplaced.replaceChildren();cardControls.length=0;
      if(options.graphContainer)options.graphContainer.hidden=true;
      status.textContent=next?'Подключаю план выбранного рабочего графа…':missingMessage;
      status.classList.toggle('wf-error',!next);syncStatus();updateControls();
      if(next)await refreshView();
      return !!view;
    }
    function request(action){
      const n=selected();if(!n)throw Error('Выберите сущность графа');
      const random=randomId();
      const req={...(workspace?.contextId!=null?{contextId:workspace.contextId}:{}),action,transactionId:'ui-'+random,nodeId:n.id,note:fields.note.value,
        expectedGraphRevision:graph().revision,expectedPlanRevision:view.sources.plan.revision};
      if(['add_action','edit_title','prepare_requirement'].includes(action))req.title=fields.title.value;
      if(['add_action','edit_canon'].includes(action)){req.recommended=fields.recommended.value;req.contraindicated=fields.contraindicated.value;}
      if(action==='add_action')req.actionType=fields.actionType.value;
      if(action==='prepare_requirement')req.childRole=fields.childRole.value;
      if(action==='add_qrpe')req.title=fields.qrpe.value;
      if(action==='place'){if(selectedFile()!==view.graphFile)req.graphFile=selectedFile();req.at=fields.at.value;req.afterStepId=fields.after.value;req.stepId=fields.placement.value;}
      if(action==='unplace')req.stepId=fields.placement.value;
      if(action==='withdraw'){
        req.dispositions=dispositionFields.map(d=>{
          if(!d.select.value)throw Error('Укажите судьбу каждой дочерней R');
          const result={requirementId:d.id,effect:d.select.value,reason:fields.note.value};
          if(d.select.value==='deactivate')result.downstreamScope='single_graph_verified';
          else result.supportingActionIds=graph().edges.filter(e=>e.type==='INTRODUCES'&&e.to===d.id&&e.from!==n.id&&!e.archived&&
            graph().nodes.some(n=>n.id===e.from&&n.status==='selected')).map(e=>e.from);
          return result;
        });
      }
      return req;
    }
    async function run(action){
      if(busy)return;
      if(!['place','unplace'].includes(action)&&selectedFile()!==view?.graphFile){status.textContent='Изменять можно только подключённый граф. Выберите его сущность на вкладке графа.';return;}
      if(pending){status.textContent='Сначала проверьте исход предыдущего запроса или повторите тот же запрос.';return;}
      try{return await send(request(action));}
      catch(e){status.textContent=e.message;status.classList.add('wf-error');syncStatus();}
    }
    async function send(req){
      if(busy||!req)return;busy=true;pending=req;let accepted=false;updateControls();status.textContent='Сохранение…';syncStatus();
      try{
        const result=await transport.write(req);
        if(!result.saved)throw Error('Writer не подтвердил сохранение');
        pending=null;accepted=true;
        if(req.action==='add_action')activeId='A-'+req.transactionId;
        if(req.action==='prepare_requirement')activeId='R-'+req.transactionId;
        if(result.view)await install(result.view);
        status.textContent=result.refreshError?'Запись сохранена, но перечитать данные не удалось: '+result.refreshError:
          result.replayed?'Предыдущая запись подтверждена; повторного действия нет.':'Запись сохранена и перечитана.';
        if(result.dependencyUpdate?.refreshed===false)
          status.textContent+=' '+result.dependencyUpdate.warning;
        else if(result.dependencyUpdate?.refreshed===true)
          status.textContent+=' Gendocen: зависимости обновлены; статусы проверки доступны во вкладке «Зависимости».';
        status.classList.toggle('wf-error',!!result.refreshError||result.dependencyUpdate?.refreshed===false);
        return result;
      }catch(e){
        if(e.definite)pending=null;
        status.textContent=accepted?'Запись сохранена, интерфейс не обновлён: '+e.message:(e.definite?'Запись отклонена: ':'Исход запроса не подтверждён; обновите данные и повторите тот же запрос: ')+e.message;
        status.classList.add('wf-error');
      }finally{busy=false;updateControls();}
    }
    updateControls();
    return {fields,buttons,refresh:refreshView,switchWorkspace,run,editPlacement,navigate,configureModule,
      focusCore(id){if(!coreEditor||!view?.sources.graphs[view.graphFile].coreModel)return false;coreEditor.focus(id);return true;},
      get switchBlocked(){return busy||!!pending||grantBusy||!!grantPending;},
      get view(){return view;},get pending(){return pending;},
      get busy(){return busy;},get status(){return status.textContent;},get text(){return container.textContent;}};
  }
  return {mount,mountCore,coreFocusedView,validateCoreSnapshot,fileTransport,declarationFor,localPlanPreview,localPlanFromOwner,planningInventory,historyKind};
});
// END GENERATED RDG WORKFLOW UI
// BEGIN GENERATED RDG ROOT PROJECTION
/* Read-only root-Requirement projection for migration away from graph-set maps.
 * A folder is a navigation container; only typed graph edges establish lineage.
 * This does not import or promote a prepared graph into a writable project.
 */
(function(host, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else host.RDGRootProjection = api;
})(globalThis, function() {
  'use strict';
  const inactive = n => n?.active === false || ['inactive', 'superseded', 'rejected'].includes(n?.status);
  function index(manifest) {
    if (!manifest || !Array.isArray(manifest.graphs)) throw Error('Missing RDG graph sources');
    const bySlug = new Map();
    for (const item of manifest.graphs) {
      if (!item.graph) throw Error('Root projection needs bundled graph: ' + item.slug);
      if (bySlug.has(item.slug)) throw Error('Duplicate graph slug: ' + item.slug);
      bySlug.set(item.slug, item);
    }
    return bySlug;
  }
  // A root graph entry is a source graph not reached through another graph.
  // A same-requirement/refinement file is NOT automatically another project.
  function listEntries(manifest) {
    const bySlug = index(manifest);
    const downstream = new Set((manifest.relations || [])
      .filter(r => ['selected', 'prepared', 'potential', 'derived', 'same-requirement'].includes(r.relationKind))
      .map(r => r.to));
    return [...bySlug.values()].filter(item => {
      const root = item.graph.rootRequirementId;
      return root && item.graph.nodes.some(n => n.kind === 'requirement' && n.id === root) && !downstream.has(item.slug);
    }).map(item => ({kind: 'full-graph', slug: item.slug,
      rootRequirementId: item.graph.rootRequirementId,
      identitySpace: item.graph.identitySpace,
      folder: item.folder,
      title: item.presentation?.title || item.graph.title || item.title || item.slug,
      presentation: item.presentation || {}, file: item.file}));
  }
  function decisionActive(n, g) {
    if (!n || !g || inactive(n) || n.templateOnly === true || g.templateOnly === true) return false;
    return (n.status === 'committed' && g.exampleOnly !== true) ||
      (n.status === 'selected-in-example-only' && g.exampleOnly === true &&
      g.hypothetical === true && g.readOnly === true && g.selectedInProject === false);
  }
  // Every projection along the chain must be authorized, including its
  // canonical owner. Unavailable, cyclic and cross-project owners fail closed.
  function decisionGuard(bySlug, space) {
    return (decision, graph) => {
      let node=decision, owner=graph;
      const visited=new Set();
      while(true) {
        if(!decisionActive(node,owner)) return false;
        if(!node.projectionOf) return true;
        const ref=node.projectionOf, key=ref.graphSlug+'::'+ref.nodeId;
        if(visited.has(key))return false;
        visited.add(key);
        const next=bySlug.get(ref.graphSlug)?.graph;
        if(!next || next.identitySpace!==space || ref.nodeId!==node.id)return false;
        const canonical=next.nodes.find(n=>n.id===ref.nodeId&&n.kind==='decision');
        if(!canonical || node.selectedOptionId!==canonical.selectedOptionId)return false;
        node=canonical; owner=next;
      }
    };
  }
  // Read-only selection check for opt-in Action graphs; a source status alone
  // is not evidence that this Action was actually selected for this driver.
  function actionActive(action, graph, requirementId) {
    if (!action || !graph || graph.actionModel !== 'candidate-v6' ||
        action.kind !== 'action' || inactive(action) || action.status !== 'selected' ||
        graph.templateOnly === true || (graph.exampleOnly === true &&
        !(graph.hypothetical === true && graph.readOnly === true && graph.selectedInProject === false))) return false;
    const basis=action.selectionBasis;
    if (basis?.actionSnapshot?.id !== action.id || basis.actionSnapshot.status !== 'candidate' ||
        basis.driverSnapshot?.id !== requirementId) return false;
    const selected=(graph.events||[]).filter(ev=>ev.type==='action_selected' && ev.actionId===action.id);
    return selected.length===1 && selected[0].driverRequirementId===requirementId &&
      ['user','assistant'].includes(selected[0].by) &&
      typeof selected[0].note==='string' && selected[0].note.trim().length>0;
  }
  function project(manifest, rootSlug, {includePotential = true} = {}) {
    const bySlug = index(manifest);
    const entry = bySlug.get(rootSlug);
    if (!entry) throw Error('Unknown root graph: ' + rootSlug);
    const space = entry.graph.identitySpace, rootId = entry.graph.rootRequirementId;
    if (!space || !rootId) throw Error('Full root needs identitySpace and rootRequirementId');
    const sources = [...bySlug.values()].filter(it => it.graph.identitySpace === space);
    const activeCause=decisionGuard(bySlug,space);
    const records = new Map(), arcs = [], warnings = [];
    // projectionOf is a repeated representation, never a second R owner.
    for (const it of sources) for (const n of it.graph.nodes) {
      if (n.kind !== 'requirement' || inactive(n)) continue;
      const old = records.get(n.id);
      if (!old || old.node.projectionOf && !n.projectionOf)
        records.set(n.id, {node: n, source: it.slug});
    }
    if (!records.has(rootId)) throw Error('Root R missing: ' + rootId);
    const add = (from, to, kind, ref, source, childRole) => {
      if (!records.has(from) || !records.has(to) || from === to) return;
      arcs.push({from, to, kind, childRole, causeKind: ref.kind, causeId: ref.id,
        sourceGraphSlug: source, id: source + ':' + kind + ':' + ref.id + ':' + from + ':' + to});
    };
    for (const it of sources) {
      const g = it.graph, ns = new Map(g.nodes.map(n => [n.id, n]));
      const edges = g.edges.filter(e => e.archived !== true);
      for (const e of edges) {
        if (e.type === 'DERIVES' && !inactive(ns.get(e.from)) && !inactive(ns.get(e.to)))
          add(e.from, e.to, 'refinement', {kind: 'requirement', id: e.from}, it.slug);
        if (e.type === 'INTRODUCES') {
          const cause = ns.get(e.from);
          const actionMode = g.actionModel === 'candidate-v6';
          if (!cause || inactive(cause) || !ns.has(e.to) ||
              !(cause.kind === 'decision' || (actionMode && cause.kind === 'action'))) continue;
          if (!edges.some(x => x.type === 'DRIVES' && x.from === e.parent && x.to === cause.id)) {
            warnings.push({source: it.slug, edge: e.id, reason: 'unverified-driving-R'});continue;
          }
          const actionSelected = actionMode && actionActive(cause,g,e.parent);
          const type = cause.kind === 'decision' ?
            (activeCause(cause, g) ? 'selected' :
              (g.templateOnly === true || cause.status === 'reusable-unselected') ? 'prepared' : null) :
            (actionSelected ? 'selected' : null);
          if (type) add(e.parent, e.to, type, {kind:cause.kind, id:cause.id}, it.slug, e.childRole);
        }
        if (e.type === 'OUTCOME_OF') {
          const o = ns.get(e.from);
          if (!o || inactive(o)) continue;
          const action = g.actionModel === 'candidate-v6' && o.kind === 'action' && o.status === 'candidate';
          if (o.kind !== 'option' && !action) continue;
          for (const link of edges.filter(x => x.type === (action ? 'DRIVES' : 'OPTION_FOR') && x.to === o.id))
            add(link.from, e.to, 'potential', {kind:o.kind, id:o.id}, it.slug, e.childRole);
        }
      }
    }
    // Multiple physical R-view files may repeat the same canonical
    // OPTION_FOR+OUTCOME_OF or DRIVES+INTRODUCES answer. They are projections
    // of a *single* causal edge, not parallel routes for the overview.
    // Keep distinct origins / decisions, but collapse exact owner projections.
    const ownerFor = arc => {
      let slug=arc.sourceGraphSlug, record=bySlug.get(slug)?.graph.nodes.find(n=>n.id===arc.causeId&&n.kind===arc.causeKind);
      const visited=new Set();
      while(record?.projectionOf){
        const ref=record.projectionOf, k=ref.graphSlug+'::'+ref.nodeId;
        if(visited.has(k))break;visited.add(k);
        const target=bySlug.get(ref.graphSlug)?.graph.nodes.find(n=>n.id===ref.nodeId&&n.kind===arc.causeKind);
        if(!target||bySlug.get(ref.graphSlug).graph.identitySpace!==space)break;
        slug=ref.graphSlug;record=target;
      }
      return slug;
    };
    const unique=new Map();
    for (const arc of arcs) {
      const owner=ownerFor(arc), key=[arc.from,arc.to,arc.kind,arc.causeKind,owner,arc.causeId].join('|');
      const earlier=unique.get(key);
      if(!earlier||arc.sourceGraphSlug===owner&&earlier.sourceGraphSlug!==owner)unique.set(key,arc);
    }
    const causalArcs=[...unique.values()];
    const adjacency = new Map();
    for (const arc of causalArcs) {
      if (!adjacency.has(arc.from)) adjacency.set(arc.from, []);
      adjacency.get(arc.from).push(arc);
    }
    // Reachability is from this root only. Same identitySpace alone does not
    // prove that a second root is part of this full graph.
    const seen = new Set([rootId]), actual = new Set([rootId]);
    const queue = [{id:rootId, possible:false}], usedEdges = new Set();
    const visitedStates = new Set([rootId+':false']);
    for (let i=0; i<queue.length; i++) {
      const next = queue[i];
      for (const arc of adjacency.get(next.id) || []) {
        if (!includePotential && ['potential','prepared'].includes(arc.kind)) continue;
        const possible = next.possible || ['potential','prepared'].includes(arc.kind);
        usedEdges.add(arc.id); seen.add(arc.to);
        if (!possible) actual.add(arc.to);
        const state = arc.to + ':' + possible;
        if (!visitedStates.has(state)) {
          visitedStates.add(state); queue.push({id:arc.to, possible});
        }
      }
    }
    // Keep auxiliary files discoverable without claiming DERIVES or
    // same-requirement is a new child Requirement. Old sets could list both.
    const indexed = (manifest.relations || []).filter(r =>
      bySlug.has(r.from) && bySlug.has(r.to) &&
      bySlug.get(r.from).graph.identitySpace === space &&
      bySlug.get(r.to).graph.identitySpace === space);
    const navigableSources = new Set([rootSlug]);
    for (let changed=true; changed;) {
      changed=false;
      for (const r of indexed) if (navigableSources.has(r.from) && !navigableSources.has(r.to)) {
        navigableSources.add(r.to); changed=true;
      }
    }
    const supplementaryViews = indexed.filter(r =>
      navigableSources.has(r.from) && navigableSources.has(r.to) &&
      ['derived', 'same-requirement'].includes(r.relationKind))
      .map(r=>({fromGraphSlug:r.from,toGraphSlug:r.to,
        relationKind:r.relationKind,requirementId:r.requirementId}));
    return {schemaVersion:1, rootRequirementId:rootId, identitySpace:space, entryGraphSlug:rootSlug,
      nodes:[...seen].map(id=>({...records.get(id).node, id, kind:'requirement',
        sourceGraphSlug:records.get(id).source, branchState:actual.has(id)?'actual':'potential'})),
      edges:causalArcs.filter(a=>usedEdges.has(a.id)), supplementaryViews, warnings,
      coverage:'indexed-sources-only; unavailable continuation may exist'};
  }
  return Object.freeze({listEntries, project, decisionActive, decisionGuard, actionActive});
});
// END GENERATED RDG ROOT PROJECTION
// BEGIN GENERATED RDG VIEW GEOMETRY
/* Common camera and target-label geometry for R graphs and graph sets. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.RDGViewGeometry=api;})(globalThis,function(){
  'use strict';
  const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
  function wheelView(view,event,point,size){
    const factor=event.deltaMode===1?16:event.deltaMode===2?size.height:1;
    const dx=(Number(event.deltaX)||0)*(event.deltaMode===2?size.width:factor),dy=(Number(event.deltaY)||0)*factor;
    if(event.ctrlKey){
      const delta=dy||dx;if(!delta)return {...view};
      const scale=clamp(view.scale*Math.exp(-clamp(delta,-600,600)*.0015),.07,3);
      return {x:point.x-(point.x-view.x)*scale/view.scale,y:point.y-(point.y-view.y)*scale/view.scale,scale};
    }
    return {...view,x:view.x-(event.shiftKey?(dx||dy):dx),y:view.y-(event.shiftKey?0:dy)};
  }
  const hit=(a,b,pad=6)=>a.x<b.x+b.w+pad&&a.x+a.w+pad>b.x&&a.y<b.y+b.h+pad&&a.y+a.h+pad>b.y;
  function placeTargetLabel({target,endpoint,width,height,nodeBoxes,labels,otherRoutes=[]}){
    const center={x:target.x+target.w/2,y:target.y+target.h/2};
    const distance=box=>Math.hypot(Math.max(box.x-endpoint.x,endpoint.x-box.x-box.w,0),Math.max(box.y-endpoint.y,endpoint.y-box.y-box.h,0));
    const crosses=box=>otherRoutes.reduce((n,ps)=>n+ps.slice(1).filter((p,i)=>{
      const a=ps[i];return a[0]===p[0]?a[0]>box.x&&a[0]<box.x+box.w&&Math.max(a[1],p[1])>box.y&&Math.min(a[1],p[1])<box.y+box.h:
        a[1]>box.y&&a[1]<box.y+box.h&&Math.max(a[0],p[0])>box.x&&Math.min(a[0],p[0])<box.x+box.w;
    }).length,0);
    const nearby=[];
    for(let ring=0;ring<=14;ring++){
      const candidates=[],step=height+8;
      for(const shift of ring?[ring*step,-ring*step]:[0]){
        candidates.push({x:target.x-width-12,y:endpoint.y-height/2+shift,w:width,h:height},
          {x:target.x+target.w+12,y:endpoint.y-height/2+shift,w:width,h:height},
          {x:center.x-width/2+shift,y:target.y-height-12,w:width,h:height},
          {x:center.x-width/2+shift,y:target.y+target.h+12,w:width,h:height});
      }
      const valid=candidates.filter(b=>!nodeBoxes.some(n=>hit(b,n))&&!labels.some(l=>hit(b,l)));
      for(const b of valid)nearby.push({...b,crowded:ring>5,score:distance(b)+crosses(b)*90+ring*2});
      if(ring>=5&&nearby.length){nearby.sort((a,b)=>a.score-b.score);return nearby[0];}
    }
    // Only physically packed/overlapping user layouts reach this local fallback.
    // Expand around the target, never use a shared gutter at the source.
    for(let ring=1;;ring++){
      const step=height+8;
      for(let i=-ring;i<=ring;i++)for(const [x,y] of [[i,-ring],[i,ring],[-ring,i],[ring,i]]){
        const b={x:center.x+x*(width+12)-width/2,y:center.y+y*step-height/2,w:width,h:height};
        if(!nodeBoxes.some(n=>hit(b,n))&&!labels.some(l=>hit(b,l)))return {...b,crowded:true};
      }
    }
  }
  return Object.freeze({wheelView,placeTargetLabel});
});
// END GENERATED RDG VIEW GEOMETRY
// BEGIN GENERATED RDG CATALOG
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
// END GENERATED RDG CATALOG
// BEGIN GENERATED RDG STATE
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
// END GENERATED RDG STATE
// BEGIN GENERATED RDG LAYOUT CORE
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
// END GENERATED RDG LAYOUT CORE
(() => {
  'use strict';
  if (globalThis.RDG_LOCAL_PORTABLE) return;
  if (document.getElementById('rdg-viewer-root')) return;
  const host = document.createElement('div');
  host.id = 'rdg-viewer-root';
  document.documentElement.appendChild(host);
  Object.assign(host.style, {position:'fixed',right:'14px',bottom:'94px',
    zIndex:'2147483600',display:'block'});
  const VIEWER_VERSION = '2.7.0';
  host.dataset.rdgVersion = VIEWER_VERSION;
  const root = host.attachShadow({ mode: 'open' });
  const ns = 'http://www.w3.org/2000/svg';
  // Local Windows directory belonging to this viewer. No filesystem picker on startup.
  const GRAPH_ROOT_URL = 'file:///C:/Users/alexa/Repos/rd-graphs/graphs/';
  let graph = null, sourceGraph = null, localRootId = null, selected = null, selectedEdge = null, showAuxiliaryEdges = false;
  // Variant visibility and collection folding are independent of the All Relations mode.
  let showAllVariants = false, expandedCollections = new Set();
  let graphs = [], projectContexts = {}, sourceUpdateAlerts = [], activeSlug = null, source = 'auto', catalogLoading = null;
  let selectedFolder = '', graphRelations = [], catalogModel=null, activeFullRootSlug=null, fullMode=false;
  const catalogCore=globalThis.RDGCatalog,viewGeometry=globalThis.RDGViewGeometry;
  let fullGraphData=null;
  const refreshedSpaces=new Set();
  const explorerStates=new Map(),fullViewStates=new Map();
  let levelStack = [];
  const embeddedSnapshot = typeof globalThis !== 'undefined' ? globalThis.RDG_EMBEDDED_GRAPHS : null;
  let privilegedRequest = null, startupRequested = false;
  let layoutBands = [], positions = new Map(), view = { x: 0, y: 0, scale: 1 };
  let graphWidth = 800, graphHeight = 600, renderBounds = null, drag = null;
  let viewportWidth=window.innerWidth,viewportHeight=window.innerHeight;
  let enteringNodes=new Set();
  const collectionPositions=new Map();
  const layoutCore=globalThis.RDGLayoutCore;
  let layoutDocument=layoutCore.empty(),layoutBaseDocument=layoutCore.empty(),layoutFileHandle=null,layoutFileRevision=null;
  let layoutReady=false,layoutDirty=false,nodeDrag=null,suppressNodeClickUntil=0;
  const layoutCacheKey='rdg-layout-document:'+GRAPH_ROOT_URL;
  let layoutPendingCommands=[],layoutSaving=false,layoutReading=false;
  let layoutAutoTimer=null,layoutAutoPaused=false,layoutAutoBlocked='',layoutLastSaved=null,layoutSavePromise=null;
  const legacyDraftKey=layoutCacheKey+':draft',draftPrefix=legacyDraftKey+':';
  const newDraftOwner=()=>typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
  let draftOwner=newDraftOwner(),draftKey=draftPrefix+draftOwner;
  // A duplicated tab may inherit sessionStorage. A document must hold its own lease
  // before reusing that owner; otherwise it gets a fresh journal.
  let draftOwnerInitialized=false,draftOwnerReady=initializeDraftOwner();
  async function initializeDraftOwner(){
    let previous;try{previous=sessionStorage.getItem(draftPrefix+'owner');}catch(_){}
    const claim=async owner=>{
      if(typeof navigator==='undefined'||!navigator.locks?.request)return false;
      return new Promise(resolve=>{
        navigator.locks.request(draftPrefix+owner,{ifAvailable:true},lock=>{
          resolve(!!lock);
          if(lock)return new Promise(()=>{}); // released by the browser when this document closes
        }).catch(()=>resolve(false));
      });
    };
    if(previous&&await claim(previous))draftOwner=previous;
    else await claim(draftOwner);
    draftKey=draftPrefix+draftOwner;
    try{sessionStorage.setItem(draftPrefix+'owner',draftOwner);}catch(_){}
    draftOwnerInitialized=true;
  }
  const currentLayoutKey=()=>fullMode?layoutCore.graphKey(sourceGraph.identitySpace,'full-'+activeFullRootSlug,sourceGraph.rootRequirementId):layoutCore.graphKey(sourceGraph?.identitySpace||'manual',activeSlug||sourceGraph?.id||'manual',localRootId||undefined);
  const savedPositions=()=>layoutDocument.layouts[currentLayoutKey()]?.positions||{};
  function clearCollectionPositionCache(key=currentLayoutKey()){if(fullMode&&key===currentLayoutKey()){const state=fullViewStates.get(activeFullRootSlug);if(state)delete state.positions;}const prefix=key+'::';for(const entry of collectionPositions.keys())if(entry.startsWith(prefix))collectionPositions.delete(entry);}
  function applyLayoutPositions(){const saved=savedPositions();if(Object.keys(saved).length)layoutBands=[];for(const [id,p] of Object.entries(saved))if(positions.has(id))positions.set(id,{x:p.x,y:p.y});}
  function updateLayoutControls(){
    if(!el('layout-save'))return;
    el('layout-save').textContent=layoutSaving?'Сохранение расположения…':'Сохранить расположение'+(layoutDirty?' *':'');
    for(const id of ['layout-save','layout-open','layout-discard'])el(id).disabled=layoutSaving||layoutReading;
    el('layout-pause').textContent=layoutAutoPaused?'Возобновить автосохранение':'Приостановить автосохранение';
    const status=layoutSaving?'Сохранение…':layoutReading?'Чтение файла…':layoutAutoBlocked||
      (layoutAutoPaused?'Автосохранение приостановлено':!layoutFileHandle?
      (layoutDirty?(typeof window.showSaveFilePicker==='function'?'Расположение блоков не сохранено — подключите файл расположений':'Изменения не записаны в файл · доступен экспорт'):(typeof window.showSaveFilePicker==='function'?'Для автосохранения подключите файл расположений':'Файл не подключён · доступен экспорт')):
      layoutDirty?'Ожидает сохранения':layoutLastSaved?'Сохранено':'Файл подключён · автосохранение включено');
    el('layout-status').textContent=status;
    el('layout-status').setAttribute('data-state',layoutSaving?'saving':layoutAutoBlocked?'error':layoutDirty?'dirty':layoutLastSaved?'saved':'idle');
    el('layout-connect').hidden=!!layoutFileHandle&&!layoutAutoBlocked;
    el('layout-status').title=status+' · '+(layoutFileHandle?.name||'Общий файл не подключён')+
      (layoutLastSaved?' · последняя проверенная запись '+new Date(layoutLastSaved).toLocaleTimeString():'');
  }
  let draftPersistence=Promise.resolve();
  async function draftStorage(key,value,write=false){
    if(typeof indexedDB==='undefined')return null;
    try{return await new Promise((resolve,reject)=>{
      const request=indexedDB.open('rdg-layout-files',1);
      request.onupgradeneeded=()=>request.result.createObjectStore('handles');
      request.onerror=()=>reject(request.error);
      request.onsuccess=()=>{const db=request.result,tx=db.transaction('handles',write?'readwrite':'readonly'),store=tx.objectStore('handles');
        const op=write?(value===null?store.delete(key):store.put(value,key)):key===null?store.getAllKeys():store.get(key);
        tx.oncomplete=()=>{db.close();resolve(write?null:op.result)};tx.onerror=()=>{db.close();reject(tx.error)};};
    });}catch(_){return null;}
  }
  function persistLayoutDraft(){
    const value=layoutPendingCommands.length?{base:layoutBaseDocument,commands:layoutPendingCommands,updatedAt:Date.now()}:null;
    const snapshot=value?JSON.parse(JSON.stringify(value)):null;
    // Only this document's journal is changed. Saving B cannot erase A's draft.
    const localWrite=()=>{try{if(snapshot)localStorage.setItem(draftKey,JSON.stringify(snapshot));else localStorage.removeItem(draftKey);}catch(_){}};
    const wroteSync=draftOwnerInitialized;if(wroteSync)localWrite();
    draftPersistence=draftPersistence.catch(()=>{}).then(async()=>{
      await draftOwnerReady;
      if(!draftOwnerInitialized)return;
      if(!wroteSync)localWrite();
      await draftStorage(draftKey,snapshot,true);
    });
  }
  async function readLayoutDraft(key){
    try{const raw=localStorage.getItem(key);if(raw!==null)return JSON.parse(raw);}catch(_){}
    return draftStorage(key);
  }
  async function listLayoutDrafts(){
    await draftOwnerReady;await draftPersistence;
    const keys=new Set(await draftStorage(null)||[]);
    try{for(let i=0;i<localStorage.length;i++)keys.add(localStorage.key(i));}catch(_){}
    const result=[];
    for(const key of keys){
      if(typeof key!=='string'||key!==legacyDraftKey&&!key.startsWith(draftPrefix))continue;
      const draft=await readLayoutDraft(key);
      if(draft?.commands?.length)result.push({id:key,own:key===draftKey,legacy:key===legacyDraftKey,updatedAt:draft.updatedAt||0,commands:draft.commands.length});
    }
    return result.sort((a,b)=>b.updatedAt-a.updatedAt);
  }
  async function recoverLayoutDraft(key){
    await draftOwnerReady;
    if(layoutDirty||layoutSaving||layoutReading)throw Error('Сначала сохраните или отмените текущие перемещения блоков');
    if(key!==legacyDraftKey&&!key.startsWith(draftPrefix))throw Error('Неверный черновик');
    const draft=await readLayoutDraft(key);
    if(layoutDirty||layoutSaving||layoutReading)throw Error('Сначала сохраните или отмените текущие перемещения блоков');
    if(!draft?.commands?.length)return false;
    const base=layoutCore.validate(draft.base);
    if(!Array.isArray(draft.commands))throw Error('Неверные команды черновика');
    layoutCore.apply(base,draft.commands);
    const same=JSON.stringify(base)===JSON.stringify(layoutBaseDocument);
    layoutPendingCommands=JSON.parse(JSON.stringify(draft.commands));installLayoutBase(base);
    layoutAutoBlocked=same?'Восстановлен черновик расположения блоков — нажмите «Сохранить расположение»':
      'Конфликт файла расположений — восстановлен черновик прежней версии';
    persistLayoutDraft();await draftPersistence;
    // A foreign/legacy source remains intact: recovery copies it into our journal.
    collectionPositions.clear();for(const state of fullViewStates.values())delete state.positions;if(graph){layout();render();}updateLayoutControls();return true;
  }
  async function restoreLayoutDraft(){
    await draftOwnerReady;
    try{
      if((await readLayoutDraft(draftKey))?.commands?.length)await recoverLayoutDraft(draftKey);
      else {
        const legacy=await readLayoutDraft(legacyDraftKey),migrationKey=legacyDraftKey+':migration';
        const migrated=await readLayoutDraft(migrationKey);
        if(legacy?.commands?.length&&JSON.stringify(migrated?.source)!==JSON.stringify(legacy)){
          await recoverLayoutDraft(legacyDraftKey);
          // Keep the source recoverable, but do not automatically replay it after
          // the imported journal has already been saved or explicitly discarded.
          const marker={source:legacy};
          try{localStorage.setItem(migrationKey,JSON.stringify(marker));}catch(_){}
          await draftStorage(migrationKey,marker,true);
        }
      }
    }catch(_){layoutAutoBlocked='Не удалось восстановить локальный черновик';}
    updateLayoutControls();
  }
  async function showLayoutDrafts(){
    const list=el('layout-draft-list');list.replaceChildren();
    const drafts=await listLayoutDrafts();
    if(!drafts.length){list.textContent='Нет несохранённых черновиков';return;}
    for(const draft of drafts){
      const button=document.createElement('button');
      button.textContent=(draft.own?'Текущая вкладка':draft.legacy?'Прежний формат':'Другая вкладка / сеанс')+
        ' · '+draft.commands+' команд'+(draft.updatedAt?' · '+new Date(draft.updatedAt).toLocaleString():'');
      button.disabled=layoutDirty||layoutSaving||layoutReading;
      button.onclick=async()=>{try{await recoverLayoutDraft(draft.id);await showLayoutDrafts();}catch(error){message(error.message);}};
      list.appendChild(button);
    }
  }
  function scheduleLayoutSave(){
    if(layoutAutoTimer!==null&&typeof clearTimeout==='function')clearTimeout(layoutAutoTimer);
    layoutAutoTimer=null;
    if(!layoutDirty||layoutAutoPaused||layoutAutoBlocked||!layoutFileHandle||layoutSaving||layoutReading||nodeDrag?.moved||typeof setTimeout!=='function')return;
    layoutAutoTimer=setTimeout(()=>{layoutAutoTimer=null;if(layoutAutoPaused||layoutAutoBlocked||nodeDrag?.moved)return;void saveLayout({interactive:false}).catch(()=>{});},650);
  }
  function markLayoutDirty(){layoutDirty=true;persistLayoutDraft();updateLayoutControls();scheduleLayoutSave();}
  function recordLayoutCommands(commands){
    const next=layoutCore.apply(layoutDocument,commands);
    layoutPendingCommands.push(...JSON.parse(JSON.stringify(commands)));
    layoutDocument=next;markLayoutDirty();
  }
  function installLayoutBase(document){
    layoutBaseDocument=layoutCore.validate(document);
    layoutDocument=layoutCore.apply(layoutBaseDocument,layoutPendingCommands);
    layoutDirty=layoutPendingCommands.length>0;updateLayoutControls();
  }
  function captureLayoutCommand(){
    if(!sourceGraph)return null;
    const key=currentLayoutKey();
    const last=layoutPendingCommands.filter(c=>c.graphKey===key).at(-1);
    if(last?.type==='clear_layout')return null;
    const captured=Object.fromEntries([...positions].map(([id,p])=>[id,{x:p.x,y:p.y}]));
    for(const [cacheKey,p] of collectionPositions)if(cacheKey.startsWith(key+'::')){
      const id='__collection__'+cacheKey.slice((key+'::').length);
      if(!positions.has(id))captured[id]=savedPositions()[id]||{...p};
    }
    return {type:'set_positions',graphKey:key,positions:captured};
  }
  function discardLayoutChanges(){
    if(layoutSaving||layoutReading)throw Error('Дождитесь завершения файловой операции');
    layoutPendingCommands=[];layoutAutoBlocked='';collectionPositions.clear();for(const state of fullViewStates.values())delete state.positions;installLayoutBase(layoutBaseDocument);persistLayoutDraft();
    if(graph){layout();render();}message('Черновые перемещения отменены.');
  }
  function layoutCommand(commands){
    if(!sourceGraph)throw Error('Сначала откройте граф');
    const list=(Array.isArray(commands)?commands:[commands]).map(c=>({...c,graphKey:c.graphKey||currentLayoutKey()}));
    const allowed=new Set([...sourceGraph.nodes.map(n=>n.id),...sourceGraph.nodes.filter(n=>['option','action'].includes(n.kind)).map(n=>'__canon__'+n.id),...(sourceGraph.collections||[]).map(c=>'__collection__'+c.id)]);
    for(const c of list){
      if(c.graphKey!==currentLayoutKey())throw Error('Команда адресована другому открытому графу');
      for(const id of Object.keys(c.positions||{}))if(!allowed.has(id))throw Error('Неизвестный узел: '+id);
    }
    recordLayoutCommands(list);
    for(const c of list){
      if(c.type==='clear_layout')clearCollectionPositionCache(c.graphKey);
      else for(const [id,p] of Object.entries(c.positions))if(id.startsWith('__collection__'))
        collectionPositions.set(c.graphKey+'::'+id.slice('__collection__'.length),{...p});
    }
    if(list.some(c=>c.type==='clear_layout'))layout();else applyLayoutPositions();
    render();return layoutCore.validate(layoutDocument);
  }
  async function rememberLayoutHandle(handle){
    if(typeof indexedDB==='undefined'||typeof FileSystemFileHandle==='undefined'||!(handle instanceof FileSystemFileHandle))return;
    try{await new Promise((resolve,reject)=>{
      const request=indexedDB.open('rdg-layout-files',1);
      request.onupgradeneeded=()=>request.result.createObjectStore('handles');
      request.onerror=()=>reject(request.error);
      request.onsuccess=()=>{const db=request.result,tx=db.transaction('handles','readwrite');tx.objectStore('handles').put(handle,GRAPH_ROOT_URL);tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(tx.error);};};
    });}catch(_){/* Layout file remains saved even if remembering its handle is unavailable. */}
  }
  async function restoredLayoutHandle(){
    if(typeof indexedDB==='undefined')return null;
    try{return await new Promise((resolve,reject)=>{
      const request=indexedDB.open('rdg-layout-files',1);
      request.onupgradeneeded=()=>request.result.createObjectStore('handles');
      request.onerror=()=>reject(request.error);
      request.onsuccess=()=>{const db=request.result,read=db.transaction('handles').objectStore('handles').get(GRAPH_ROOT_URL);read.onsuccess=()=>{db.close();resolve(read.result||null);};read.onerror=()=>{db.close();reject(read.error);};};
    });}catch(_){return null;}
  }
  async function attachLayoutFile(handle){
    if(layoutSaving||layoutReading)throw Error('Дождитесь завершения файловой операции');
    if(layoutDirty)throw Error('Есть несохранённое расположение. Сначала сохраните его или сбросьте изменения.');
    layoutReading=true;updateLayoutControls();
    try{
      const doc=layoutCore.validate(JSON.parse(await (await handle.getFile()).text()));
      if(layoutDirty)throw Error('Во время чтения появились новые перемещения; файл не заменил черновик.');
      collectionPositions.clear();for(const state of fullViewStates.values())delete state.positions;layoutAutoBlocked='';layoutLastSaved=null;layoutFileHandle=handle;layoutFileRevision=doc.revision;installLayoutBase(doc);persistLayoutDraft();
      await rememberLayoutHandle(handle);
      if(graph){layout();render();}message('Расположение прочитано из '+handle.name);return layoutCore.validate(doc);
    }finally{layoutReading=false;updateLayoutControls();scheduleLayoutSave();}
  }
  async function writeLayoutSnapshot(snapshot,base,savedCommandCount,interactive){
    if(!layoutFileHandle){
      if(!interactive)throw Error('Нет доступа к файлу — подключите файл расположений');
      if(typeof window.showSaveFilePicker!=='function')throw Error('Запись общего файла недоступна. Используйте экспорт JSON и сохраните его как graphs/layouts.json.');
      const handle=await window.showSaveFilePicker({suggestedName:'layouts.json',types:[{description:'Расположение RDG (graphs/layouts.json)',accept:{'application/json':['.json']}}]});
      const text=await (await handle.getFile()).text();
      if(text.trim()){
        const disk=layoutCore.validate(JSON.parse(text));
        if(JSON.stringify(disk)!==JSON.stringify(base))throw Error('В выбранном файле другое расположение. Откройте его кнопкой «Файл расположений», затем повторите правки.');
        layoutFileRevision=disk.revision;
      }else layoutFileRevision=base.revision;
      layoutFileHandle=handle;
    }
    const handle=layoutFileHandle;
    if(handle.queryPermission&&await handle.queryPermission({mode:'readwrite'})!=='granted'){
      if(!interactive||!handle.requestPermission||await handle.requestPermission({mode:'readwrite'})!=='granted')throw Error('Нет доступа к файлу — подключите разрешение на запись');
    }
    const text=await (await handle.getFile()).text();
    const disk=text.trim()?layoutCore.validate(JSON.parse(text)):layoutCore.empty();
    if(text.trim()&&(disk.revision!==layoutFileRevision||JSON.stringify(disk)!==JSON.stringify(base)))throw Error('Файл расположений изменён извне. Правки не перезаписаны; перечитайте файл перед сохранением.');
    const committed=layoutCore.commit(snapshot,base.revision);
    const writable=await handle.createWritable();
    try{await writable.write(JSON.stringify(committed,null,2)+'\n');const latest=await (await handle.getFile()).text();if(latest!==text)throw Error('Файл расположений изменён во время записи; черновик не применён.');await writable.close();}catch(error){if(writable.abort)try{await writable.abort();}catch(_){}throw error;}
    const checked=layoutCore.validate(JSON.parse(await (await handle.getFile()).text()));
    if(JSON.stringify(checked)!==JSON.stringify(committed))throw Error('Проверка записанного файла не совпала');
    // Commands issued after the snapshot remain an unsaved draft, even on another graph.
    layoutPendingCommands=layoutPendingCommands.slice(savedCommandCount);
    layoutFileRevision=checked.revision;layoutLastSaved=Date.now();layoutAutoBlocked='';installLayoutBase(checked);persistLayoutDraft();
    try{localStorage.setItem(layoutCacheKey,JSON.stringify(checked));}catch(_){}
    if(graph){applyLayoutPositions();render();}
    await rememberLayoutHandle(handle);
    message('Расположение сохранено в '+handle.name+' · ревизия '+checked.revision+
      (layoutDirty?'. Новые перемещения остались в черновике.':''));
    return layoutCore.validate(checked);
  }
  function saveLayout({interactive=true}={}){
    if(layoutSaving)return Promise.reject(Error('Дождитесь завершения файловой операции'));
    if(layoutReading)return Promise.reject(Error('Дождитесь завершения файловой операции'));
    if(!sourceGraph)return Promise.reject(Error('Сначала откройте граф'));
    if(interactive){layoutAutoBlocked='';const capture=captureLayoutCommand();if(capture)recordLayoutCommands([capture]);}
    if(!layoutDirty)return Promise.resolve(layoutCore.validate(layoutDocument));
    const snapshot=layoutCore.validate(layoutDocument),base=layoutCore.validate(layoutBaseDocument),count=layoutPendingCommands.length;
    layoutSaving=true;updateLayoutControls();
    const task=async()=>{
      try{
        const write=()=>writeLayoutSnapshot(snapshot,base,count,interactive);
        if(typeof navigator!=='undefined'&&navigator.locks?.request&&layoutFileHandle)
          return await navigator.locks.request('rdg-layout-write:'+GRAPH_ROOT_URL,write);
        return await write();
      }catch(error){
        layoutAutoBlocked=/изменён|ревизи|другое расположение/.test(error.message)?'Конфликт версий — изменения не записаны':
          /разрешени|доступ/.test(error.message)?'Нет доступа к файлу — подключите разрешение':
          error.name==='AbortError'?'Выбор файла отменён · локальный черновик':'Ошибка записи — повторите сохранение';
        persistLayoutDraft();throw error;
      }finally{layoutSaving=false;layoutSavePromise=null;updateLayoutControls();scheduleLayoutSave();}
    };
    layoutSavePromise=task();return layoutSavePromise;
  }
  async function initializeLayouts(manifest){
    if(layoutReady)return;layoutReady=true;
    let doc=layoutCore.validate(manifest.layouts||layoutCore.empty());
    const handle=await restoredLayoutHandle();
    if(handle&&(!handle.queryPermission||await handle.queryPermission({mode:'read'})==='granted')){
      try{doc=layoutCore.validate(JSON.parse(await (await handle.getFile()).text()));layoutFileHandle=handle;layoutFileRevision=doc.revision;installLayoutBase(doc);await restoreLayoutDraft();return;}catch(_){}
    }
    try{doc=layoutCore.validate(JSON.parse(await readLocalFile('layouts.json')));}
    catch(_){try{const cache=localStorage.getItem(layoutCacheKey);if(cache){const cached=layoutCore.validate(JSON.parse(cache));if(cached.revision>doc.revision)doc=cached;}}catch(_){}}
    installLayoutBase(doc);await restoreLayoutDraft();
  }
  function exportLayout(){
    const capture=captureLayoutCommand();
    const draft=capture?layoutCore.apply(layoutDocument,capture):layoutDocument;
    const data=layoutCore.commit(draft,layoutDocument.revision),a=document.createElement('a');
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));
    a.href=url;a.download='layouts.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    message('JSON подготовлен к скачиванию. Для общей записи сохраните его в graphs/layouts.json.');return data;
  }
  host.rdgLayout={getDocument:()=>layoutCore.validate(layoutDocument),graphKey:currentLayoutKey,apply:layoutCommand,save:saveLayout,attachFile:attachLayoutFile,
    drafts:listLayoutDrafts,recoverDraft:recoverLayoutDraft,
    pause:()=>{layoutAutoPaused=true;updateLayoutControls();scheduleLayoutSave();},
    resume:()=>{layoutAutoPaused=false;updateLayoutControls();scheduleLayoutSave();},
    status:()=>({dirty:layoutDirty,saving:layoutSaving,paused:layoutAutoPaused,blocked:layoutAutoBlocked,lastSaved:layoutLastSaved}),
    load:document=>{if(layoutSaving||layoutReading||layoutDirty)throw Error('Есть несохранённые изменения или файловая операция');collectionPositions.clear();for(const state of fullViewStates.values())delete state.positions;layoutFileHandle=null;layoutFileRevision=null;layoutLastSaved=null;layoutAutoBlocked='';installLayoutBase(document);persistLayoutDraft();if(graph){layout();render();}return layoutCore.validate(layoutDocument);}};

  root.innerHTML = [
    '<style>:host{position:fixed;right:14px;bottom:94px;z-index:2147483600;color:#e4edf7;font:13px system-ui}',
    'button,input,select{font:inherit}button{cursor:pointer;border:1px solid #506681;border-radius:6px;background:#263b52;color:white;padding:7px}',
    '#launch{background:#295779;cursor:grab;touch-action:none;user-select:none}#launch:active{cursor:grabbing}#panel{display:none;position:fixed;inset:20px;background:#101b29;border:1px solid #45596c;border-radius:10px;box-shadow:0 12px 35px #0009;flex-direction:column}',
    '#panel.open{display:flex}#bar{position:relative;display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:9px 49px 9px 9px;background:#1a2a3d}#bar #close{position:absolute;top:9px;right:9px}',
    '#bar strong{margin-right:auto;font-size:16px}#viewer-version{font-size:12px;color:#b8c9da;white-space:nowrap}#bar input,#bar select{background:#102235;border:1px solid #526680;color:white;padding:7px;min-width:150px}',
    '#message{padding:8px;color:#b8c9da}#content{display:flex;flex:1;min-height:0}svg{width:100%;height:100%;background:#111d2a;touch-action:none;cursor:grab}',
    '#canvas-wrap{flex:1;min-width:0;min-height:0;position:relative;overflow:hidden}#canvas{position:absolute;inset:0;display:block}#inspector-toggle{display:block;position:absolute;right:8px;top:8px;z-index:1;background:#263b52}#pan-hint{display:none;position:absolute;left:8px;right:8px;bottom:7px;text-align:center;pointer-events:none;font-size:12px;color:#ddedf9;background:#0e2030d9;border:1px solid #4a657a;border-radius:6px;padding:5px 7px}#content.info-open #info{display:block}#info{display:none;width:355px;max-width:38%;overflow:auto;border-left:1px solid #42546a;padding:16px;font-size:14px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}',
    '#catalog{flex:1;min-height:0;overflow:auto;padding:26px 34px;background:linear-gradient(180deg,#142437,#101b29 45%)}',
    '#catalog-header{max-width:1050px;margin:0 auto 26px}#catalog h2{font-size:23px;font-weight:650;margin:0 0 8px}#catalog p{color:#9fb2c7;margin:0;font-size:14px}',
    '#graph-list,#folder-list{max-width:1050px;margin:0 auto;display:flex;flex-direction:column;gap:8px}#folder-list{margin-bottom:8px}#catalog-search{display:block;box-sizing:border-box;width:min(100%,1050px);margin:0 auto 16px;background:#102235;color:white;border:1px solid #526680;border-radius:6px;padding:10px}.explorer-row{display:flex;flex-direction:column;text-align:left;gap:5px;padding:15px 18px;background:#1b3047}.explorer-row:hover,.explorer-row:focus-visible{background:#24415e;border-color:#83b5d4}.explorer-title{font-size:16px;font-weight:650}.explorer-meta,.explorer-description{font-size:12px;color:#abc0d4}#folder-back{margin-bottom:16px}',
    '#breadcrumbs{display:flex;gap:5px;align-items:center;flex-wrap:wrap;padding:5px 10px;font-size:12px}#breadcrumbs button{padding:4px 7px;background:transparent}#layout-indicator{display:flex;gap:12px;align-items:center;padding:4px 10px;color:#b8c9da;font-size:12px}#layout-connect{padding:4px 7px}#layout-status[data-state=error]{color:#ffc49d}#layout-status[data-state=saved]{color:#9ed8b4}#layout-status{min-width:120px}.node.graph rect{fill:#213c52;stroke:#8ab8d8}.edge[data-relation-kind=potential]{stroke-dasharray:7 4}.edge[data-relation-kind=derived],.edge[data-relation-kind=same-requirement]{stroke-dasharray:2 5}.node.graph:focus rect{stroke:#dbf1ff;stroke-width:3}',
    '#catalog[hidden],#folder-list[hidden],#folder-back[hidden],#graph-list[hidden],#edge-toolbar[hidden],#content[hidden],#source-view[hidden],#source[hidden],#level-up[hidden],#back[hidden],#reload[hidden],#fit[hidden],#search[hidden]{display:none}',
    '#source-view{flex:1;min-height:0;overflow:auto;padding:24px;background:#111d2a}#source-text{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;max-width:1150px;margin:auto;color:#d7e5f2}',

    '@keyframes rdg-appear{from{opacity:0}to{opacity:1}}@media(prefers-reduced-motion:no-preference){.node.appearing{animation:rdg-appear .18s ease-out}}.node rect{fill:#263c52;stroke:#7590aa;stroke-width:1.5;rx:9}.node.requirement rect{fill:#183b50;stroke:#84b7d2}',
    '.node.decision rect{fill:#4a3724;stroke:#ccb17f}.node.context rect{fill:#264536;stroke:#80b499}.node.option rect{fill:#34415c;stroke:#9fbded}.node.action rect{fill:#294457;stroke:#9bc6d7}.node.collection rect{fill:#3b3254;stroke:#c0a8e6}.node.canon rect{fill:#244454;stroke:#63bdd2;stroke-dasharray:4 2}',
    '.node .qrpe-badge{fill:#7c4235;stroke:#eda987;stroke-width:1}.node .qrpe-badge-label{fill:#fff0d6;font-size:10px;font-weight:700}.node .guide-badge{fill:#285572;stroke:#8fbedb;stroke-width:1}.node .guide-badge-label{fill:#edf7ff;font-size:10px;font-weight:650}.node.selected rect{stroke:#ffe096;stroke-width:3}.node.root rect{stroke:#e5db9f;stroke-width:2.5}.node.drill rect{stroke:#88d4ff;stroke-width:2.3}.node.dim{opacity:.2}.node text{fill:#f3f5fa;font-size:13px;pointer-events:none}.node text.node-kind{font-size:12px}',
    '.edge{fill:none;stroke:#c0d2e2;stroke-width:1.9}.edge.g-core{stroke:#d2dce7;stroke-width:2.1}',
    '.edge.g-ground{stroke:#94b9cc;stroke-dasharray:8 4}.edge.g-origin{stroke:#a7c9ac;stroke-dasharray:4 3}',
    '.edge.g-ready{stroke:#d3be9e;stroke-dasharray:10 3 2 3}.edge.g-review{stroke:#d0a7b1;stroke-dasharray:2 4}',
    '.edge.g-scope{stroke:#c8bae4;stroke-dasharray:6 5}.edge.g-other{stroke:#a7b3c0;stroke-dasharray:5 5}',
    '.edge-label{cursor:pointer}.edge-label rect{fill:#152637;stroke:#466079;stroke-width:.8;rx:4;opacity:.98}',
    '.node.graph[data-branch-state=alternative] rect{fill:#1b2d3c;stroke:#566d80;stroke-dasharray:5 3}.node.graph[data-branch-state=unknown] rect{fill:#233440;stroke:#7d909f;stroke-dasharray:2 3}.node.graph[data-branch-state=alternative] text{fill:#c6d3de}.node.graph.selected rect,.node.graph:focus rect{stroke:#e5f1fa;stroke-width:3;stroke-dasharray:5 3}.edge[data-branch-state=alternative]{stroke:#617587;stroke-width:1.3}.edge-label[data-branch-state=alternative] rect{fill:#16232e;stroke:#4c6274}.edge-label[data-branch-state=alternative] text{fill:#c6d3de}',
    '.node.requirement[data-branch-state=potential] rect,.node.option[data-branch-state=potential] rect{fill:#182938;stroke:#738b9b;stroke-dasharray:6 4}.node.requirement[data-branch-state=potential] text,.node.option[data-branch-state=potential] text{fill:#d2dce4}.node.requirement[data-branch-state=actual] rect{stroke:#9fd0da}.node.decision[data-branch-state=actual] rect{stroke:#9fd0da}',
    '.node.requirement-graph>rect:first-of-type{fill:#17364d;stroke:#a2d1ea;stroke-width:2.5}.node.requirement-graph .requirement-graph-outline{fill:none!important;stroke:#c5e1f2!important;stroke-width:1!important;stroke-dasharray:4 5;opacity:.85}.node.requirement-graph .node-kind{font-weight:800;letter-spacing:.045em}.node.requirement-graph[data-branch-state=potential]>rect:first-of-type{stroke-dasharray:6 4}.node.requirement-graph:focus>rect:first-of-type{stroke:#ffe096;stroke-width:3}',
    '#graph-meta #graph-scope-hint{flex-basis:100%;margin:2px 5px 6px;padding:6px 10px;border-left:3px solid #8bc5e5;border-radius:3px;background:#1e394b;color:#d0e5f2;font-size:11px;line-height:1.45}#graph-meta #graph-scope-hint[hidden]{display:none}',

    '.edge-label text{font:11px system-ui;fill:#edf4fb;pointer-events:none}.edge-label.selected rect{stroke:#ffe096;stroke-width:2}',
    '.edge.selected{stroke:#ffe096;stroke-width:3}.edge.dim,.edge-label.dim{opacity:.13}.edge-label:hover rect{fill:#29435a;stroke:#cde5f7}',
    '#edge-toolbar{padding:8px 12px;border-bottom:1px solid #334d63;display:flex;flex-wrap:wrap;align-items:center;gap:9px;max-height:108px;overflow:auto}',
    '#layout-controls summary{cursor:pointer;border:1px solid #506681;border-radius:6px;padding:7px;background:#263b52}#layout-controls .layout-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}#edge-toolbar:has(#layout-controls[open]){max-height:220px}#edge-toolbar[hidden]{display:none}#edge-toolbar button[aria-pressed="true"]{background:#375773;border-color:#acd8f5}',
    '#edge-legend{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:12px;color:#cfdfeb}',
    '.edge-legend-item{white-space:nowrap}.edge-legend-symbol{display:inline-block;width:22px;margin-right:5px;border-bottom:2px solid #ddd;vertical-align:middle}',
    '.edge-legend-symbol.g-ground{border-bottom-style:dashed;border-bottom-color:#94b9cc}',
    '.edge-legend-symbol.g-origin{border-bottom-style:dotted;border-bottom-color:#a7c9ac}',
    '.edge-legend-symbol.g-ready{border-bottom-style:dashed;border-bottom-color:#d3be9e}',
    '.edge-legend-symbol.g-review{border-bottom-style:dotted;border-bottom-color:#d0a7b1}',
    '.edge-legend-symbol.g-scope{border-bottom-style:dashed;border-bottom-color:#c8bae4}',
    '#view-tabs{display:flex;gap:6px;padding:8px 12px;background:#17283b;border-bottom:1px solid #42546a}#view-tabs [aria-selected=true]{background:#315c7e;border-color:#a7cde9}#graph-pane{display:flex;flex:1;min-height:0;flex-direction:column}#graph-pane[hidden],#workflow-page[hidden],#dependency-page[hidden],#workflow-panel .wf-grid[hidden]{display:none}#workflow-page{flex:1;min-height:0;overflow:auto;background:#17283b}#workflow-connection-box{padding:18px 20px 6px;max-width:960px}#workflow-connection-box h2{margin:0 0 8px}#workflow-connection-box p{line-height:1.5;color:#b8c9da}#workflow-connection.wf-error{color:#ffc49d}#panel[data-view=workflow] #bar :is(#back,#level-up,#example-set-map,#file,#source,#reload,#fit,#search){display:none}#workflow-panel{padding:10px 20px 20px;background:#17283b}#workflow-panel[hidden],#workflow-toggle[hidden]{display:none}#workflow-panel input,#workflow-panel textarea,#workflow-panel select{display:block;width:100%;box-sizing:border-box;max-width:100%;background:#102235;color:white;padding:7px;border:1px solid #526680;border-radius:5px}#workflow-panel textarea{width:100%;min-height:54px}#workflow-panel label{display:block;margin:6px 0}#workflow-panel .wf-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}#workflow-panel button{margin:4px}#workflow-panel .wf-status{white-space:pre-wrap;padding:8px}#workflow-panel .wf-error{color:#ffc49d}#workflow-panel details{margin-top:16px;border-top:1px solid #42546a;padding-top:12px}#workflow-panel summary{cursor:pointer;font-weight:600}#workflow-panel .wf-status{min-height:24px}#workflow-panel ul{padding-left:22px}#info a{color:#a7dcff}#info a:visited{color:#d2c0ff}#info section{border-top:1px solid #42546a;padding-top:8px}#info small{color:#adbfcd}',
    '@media(max-width:650px){#panel{inset:4px}#bar{gap:6px;padding:7px 48px 7px 7px;flex-shrink:0}#bar strong{font-size:14px}#message{max-height:58px;overflow:auto;flex-shrink:0}#content{flex-direction:column}#canvas-wrap{min-height:0}#info{display:none;width:auto;max-width:none;min-height:0;max-height:38%;box-sizing:border-box;flex:0 0 auto;border-left:none;border-top:1px solid #42546a;padding:12px;font-size:13px;line-height:1.4}#content.info-open #info{display:block}#inspector-toggle{display:block}#edge-toolbar{gap:5px;flex-shrink:0;max-height:92px}#edge-label-hint,#edge-legend{display:none}#pan-hint{display:block}}',
    '@media(max-width:650px) and (max-height:650px){#bar{max-height:28vh;overflow:auto}#message{max-height:40px}#edge-toolbar{max-height:70px}}#panel{inset:10px}#bar{padding:5px 42px 5px 8px;gap:6px;flex-shrink:0}#bar #close{top:5px;right:6px}#bar strong{font-size:14px;flex:1 1 90px;min-width:64px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#bar #viewer-version{font-size:11px}#bar #view-tabs{padding:0;border:0;background:transparent;gap:4px;flex-shrink:0}#bar button,#bar input,#bar select,#edge-toolbar button,#edge-toolbar summary{padding:4px 6px;font-size:12px}#bar #search{min-width:110px;width:140px}#graph-meta{display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;padding:3px 8px}#graph-meta #breadcrumbs,#graph-meta #layout-indicator,#graph-meta #message{padding:0;font-size:11px;line-height:1.4;gap:4px}#breadcrumbs button{padding:2px 5px}#layout-status{min-width:0;max-width:380px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}#graph-meta #message{flex:1 1 160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-height:22px}#edge-toolbar{padding:4px 8px;gap:5px;max-height:96px;flex-shrink:0}#graph-help{margin-left:auto}#graph-help summary{cursor:pointer;border:1px solid #506681;border-radius:5px;background:#263b52}#graph-help[open]{flex-basis:100%;margin-left:0}#graph-help .graph-help-body{padding:8px;line-height:1.5}#graph-help #edge-legend{display:flex;flex-wrap:wrap}#graph-help #edge-label-hint{display:block;margin:6px 0}#edge-toolbar:has(#graph-help[open]){max-height:240px}#workflow-connection-box{padding:8px 12px;max-width:none;display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px}#workflow-settings summary,#workflow-panel .wf-editor>summary{cursor:pointer;border:1px solid #506681;border-radius:5px;background:#263b52;padding:5px 8px;font-size:12px;width:fit-content}#workflow-settings[open]{flex-basis:100%}#workflow-settings>div{padding:8px 0;max-width:800px}#workflow-settings h3{margin:4px 0}#workflow-connection-box #workflow-connection{margin:0;font-size:12px;flex:1;min-width:180px}#workflow-panel{padding:0 12px 12px}#workflow-panel .wf-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:6px 12px}#workflow-panel .wf-toolbar h3{font-size:16px;margin:8px 0}#workflow-panel .wf-toolbar button{margin:0;padding:4px 7px}#workflow-panel .wf-status{font-size:12px;padding:0;min-height:0}#workflow-panel .wf-editor{margin:6px 0 10px;padding:0;border:0}#workflow-panel .wf-editor[hidden]{display:none}#workflow-panel .wf-editor[open]{max-width:760px;padding-bottom:12px}#workflow-panel .wf-grid{grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px 24px}#workflow-panel .wf-grid h3{margin:8px 0}#workflow-panel ul{line-height:1.5;margin-top:8px}@media(max-width:650px){#panel{inset:4px}#bar{gap:4px}#bar strong{flex-basis:110px}#graph-meta #layout-status{max-width:270px}#graph-meta #message{flex-basis:100%}#edge-toolbar{max-height:96px}#workflow-panel .wf-grid{grid-template-columns:1fr}}#workflow-panel .wf-card{box-sizing:border-box;border:1.5px solid #7590aa;border-radius:9px;padding:12px;margin:0 0 12px;min-width:0;overflow-wrap:anywhere;background:#263c52}#workflow-panel .wf-card.requirement{background:#183b50;border-color:#84b7d2}#workflow-panel .wf-card.action{background:#294457;border-color:#9bc6d7}#workflow-panel .wf-card[data-status=candidate],#workflow-panel .wf-card[data-status=potential]{border-style:dashed}#workflow-panel .wf-card>small{display:block;color:#c7d9e7;font-size:11px;margin:3px 0}#workflow-panel .wf-card p{margin:6px 0;line-height:1.45}#workflow-panel .wf-card .wf-card-title{display:block;width:100%;margin:4px 0;padding:0;text-align:left;background:transparent;border:0;color:#f3f5fa;font-size:14px;font-weight:650;line-height:1.45}#workflow-panel .wf-card .wf-card-title:not(:disabled):hover{text-decoration:underline}#workflow-panel .wf-card-title:disabled{cursor:default;opacity:1}#workflow-panel .wf-card details{margin:8px 0;padding:6px 0 0;border-color:#58758b}#workflow-panel .wf-card summary{font-size:12px}#workflow-panel .wf-card .wf-qrpe-preview{color:#ffd0a6;font-size:12px}#workflow-panel .wf-card .wf-card-place{padding:4px 7px;margin:8px 0 0;font-size:12px}#workflow-panel .wf-variants{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;border-left:2px solid #84b7d2;margin-top:12px;padding-left:12px}#workflow-panel .wf-variants>p{grid-column:1/-1;color:#c4d7e7;font-size:12px}#workflow-panel .wf-variants>.wf-card{margin:0}#workflow-panel .wf-history-event{border-left:2px solid #58758b;padding:6px 10px;margin-bottom:10px;font-size:12px}#workflow-graph-editor{max-height:42%;overflow:auto;flex:0 0 auto;padding:8px 12px;border-bottom:1px solid #42546a}#workflow-graph-editor[hidden],#workflow-graph-toggle[hidden]{display:none}#workflow-graph-editor label{display:block;margin:8px 0}#workflow-graph-editor input,#workflow-graph-editor select,#workflow-graph-editor textarea{display:block;box-sizing:border-box;width:min(100%,760px);padding:6px;background:#102235;color:white;border:1px solid #526680}#workflow-graph-editor button{margin:4px}#workflow-graph-editor summary{cursor:pointer}#workflow-graph-editor p{margin:6px 0}#workflow-panel .wf-grid>section{min-width:0}@media(max-width:650px){#workflow-panel .wf-variants{grid-template-columns:1fr}}#workflow-graph-editor .wf-error{color:#ffc49d}#workflow-panel .wf-card .wf-card-goal{background:transparent;border:0;color:#b8dcf3;text-align:left;padding:0;margin:0;text-decoration:underline;font-size:12px}#workflow-panel .wf-card p>small{display:block;color:#b8c9da}',
    ":host{--rdg-requirement-bg:#173c60;--rdg-requirement-line:#80baff;--rdg-action-bg:#35294e;--rdg-action-line:#bc9ded;--rdg-canon-bg:#153e42;--rdg-canon-line:#75c9c2;--rdg-qrpe-bg:#45321d;--rdg-qrpe-line:#efba69;--rdg-history-bg:#203044;--rdg-history-line:#809bb6}",
    ".node.requirement rect,.node.graph rect{fill:var(--rdg-requirement-bg);stroke:var(--rdg-requirement-line)}",
    ".node.action rect,.node.option rect{fill:var(--rdg-action-bg);stroke:var(--rdg-action-line)}",
    ".node.canon rect{fill:var(--rdg-canon-bg);stroke:var(--rdg-canon-line)}",
    ".edge.canon-attachment{stroke:var(--rdg-canon-line);stroke-width:1.5;stroke-dasharray:3 3;cursor:pointer}.edge.canon-attachment.selected{stroke:#ffe096;stroke-width:2.5}",
    ".node .qrpe-badge{fill:var(--rdg-qrpe-bg);stroke:var(--rdg-qrpe-line)}",
    ".node.requirement[data-branch-state=potential] rect{fill:var(--rdg-requirement-bg);stroke:var(--rdg-requirement-line)}",
    ".node.option[data-branch-state=potential] rect{fill:var(--rdg-action-bg);stroke:var(--rdg-action-line)}",
    ".node.graph[data-branch-state=alternative] rect{fill:#182d43;stroke:#6686a5}",
    ".node.selected rect,.node.root rect,.node.drill rect{stroke-width:3}",
    ".node.root rect{stroke:#e5db9f}",
    ".node.drill rect{stroke:#88d4ff}",
    ".node.selected rect{stroke:#ffe096}",
    "#workflow-panel{padding-bottom:32px}",
    "#workflow-panel .wf-toolbar{position:sticky;top:0;z-index:3;padding:8px 0;margin-bottom:8px;background:#17283b;box-shadow:0 4px 10px #101b2944}",
    "#workflow-panel .wf-toolbar .wf-jump-plan{margin-left:auto;padding:7px 12px;background:#244d67;border-color:#7cb6d4;white-space:nowrap}",
    "#workflow-panel .wf-toolbar .wf-jump-plan:disabled{opacity:.5;cursor:default}",
    "#workflow-panel .wf-timeline{display:block;max-width:1040px;margin:0 auto;padding:0 0 0 25px;border-left:2px solid #47637c}",
    "#workflow-panel .wf-timeline[hidden]{display:none}",
    "#workflow-panel .wf-timeline>section{display:block;min-width:0}",
    "#workflow-panel .wf-unplaced{margin:34px 0 0;padding:6px 0 0;border-top:1px solid #526680}",
    "#workflow-panel .wf-unplaced .wf-unplaced-group{margin:0;padding:8px 0;border:0}",
    "#workflow-panel .wf-unplaced summary{font-size:17px;color:#d8e9f5}",
    "#workflow-panel .wf-unplaced-group>p{font-size:12px;color:#bad0df;line-height:1.5}",
    "#workflow-panel .wf-unplaced-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}",
    "#workflow-panel .wf-unplaced-card{background:#1d354b;border:1px dashed #7094af;border-radius:8px;padding:10px;min-width:0}",
    "#workflow-panel .wf-unplaced-card .wf-card-title{display:block;width:100%;text-align:left;background:transparent;border:0;padding:5px 0;color:#f0f5fa;font-weight:600}",
    "#workflow-panel .wf-unplaced-card>small{display:block;color:#b8cfde;font-size:11px}",

    "#workflow-panel .wf-timeline h3{font-size:18px;margin:16px 0}",
    "#workflow-panel .wf-day{font-size:12px;font-weight:500;letter-spacing:.03em;color:#b9ccdc;margin:24px 0 12px}",
    "#workflow-panel .wf-card{position:relative;border:1px solid var(--rdg-history-line);border-left-width:5px;border-radius:12px;background:var(--rdg-history-bg);padding:16px 18px;margin:0 0 24px;box-shadow:0 6px 16px #07111d33;scroll-margin-top:110px}",
    "#workflow-panel .wf-card.requirement{background:var(--rdg-requirement-bg);border-color:var(--rdg-requirement-line)}",
    "#workflow-panel .wf-card.action{background:var(--rdg-action-bg);border-color:var(--rdg-action-line)}",
    "#workflow-panel .wf-history>.wf-card::before,#workflow-panel .wf-future>.wf-card::before{content:\"\";position:absolute;width:10px;height:10px;box-sizing:border-box;top:24px;left:-37px;border:2px solid #a8c5df;border-radius:50%;background:#17283b;box-shadow:0 0 0 5px #17283b}",
    "#workflow-panel .wf-future>.wf-card::before{background:#8ec9e2;border-color:#8ec9e2}",
    "#workflow-panel .wf-card .wf-card-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:0 0 10px;color:#d5dfed;font-size:11px}",
    "#workflow-panel .wf-card-meta span{padding:3px 7px;border-radius:5px;background:#0b172f4d}",
    "#workflow-panel .wf-card.action>.wf-card-meta>.wf-kind-badge{background:#6c4c8e;color:#fff2ff}",
    "#workflow-panel .wf-card.requirement>.wf-card-meta>.wf-kind-badge{background:#285d8e;color:#eff7ff}",
    "#workflow-panel .wf-card[data-event-kind=action_executed] .wf-event-badge,#workflow-panel .wf-card[data-event-kind=requirement_achieved] .wf-event-badge{background:#214a3b;color:#b6f1ce}",
    "#workflow-panel .wf-card[data-event-kind=action_withdrawn] .wf-event-badge{background:#61402e;color:#ffdab3}",
    "#workflow-panel .wf-event-family{display:inline-block;margin:0 0 9px;padding:4px 9px;border-radius:4px;font-size:10px;font-weight:800;letter-spacing:.1em;line-height:1.3}",
    "#workflow-panel .wf-history>.wf-card.wf-event-result{background:#193c35;border-left-color:#75c6a0}",
    "#workflow-panel .wf-history>.wf-card.wf-event-state{background:#433529;border-left-color:#e8b471}",
    "#workflow-panel .wf-history>.wf-card.wf-event-choice{background:#302f4f;border-left-color:#ae9ae0}",
    "#workflow-panel .wf-history>.wf-card.wf-event-change{background:#22394c;border-left-color:#77b2df}",
    "#workflow-panel .wf-event-result .wf-event-family{background:#245f49;color:#e1ffef}",
    "#workflow-panel .wf-event-state .wf-event-family{background:#845c2f;color:#fff1d7}",
    "#workflow-panel .wf-event-choice .wf-event-family{background:#625291;color:#f0e6ff}",
    "#workflow-panel .wf-event-change .wf-event-family{background:#295f8a;color:#e4f4ff}",
    "#workflow-panel .wf-history>.wf-event-plan{border-left-color:#84cad9;background:#233f4a}#workflow-panel .wf-event-plan .wf-event-family{background:#307b8a;color:#ebfbff}",
    "#workflow-panel .wf-introduced-requirements{margin:12px 0;padding:10px 12px;border-left:3px solid #8dc4df;background:#203c50;border-radius:4px}#workflow-panel .wf-introduced-requirements strong{display:block;margin-bottom:7px}#workflow-panel .wf-introduced-requirement{margin:8px 0;line-height:1.5;display:flex;flex-wrap:wrap;align-items:center;gap:8px}#workflow-panel .wf-introduced-requirements small{display:block;opacity:.82;font-size:11px;margin-top:8px}#workflow-panel .wf-save-details{margin-top:13px;border-top:1px solid #5e7586;padding-top:9px}#workflow-panel .wf-save-details summary{cursor:pointer;font-size:12px;color:#bce1f8}#workflow-panel .wf-save-details p{font-size:12px;margin:7px 0}",
    "#workflow-panel .wf-card.option>.wf-card-meta>.wf-kind-badge{background:#4c578f;color:#fff}",
    "#workflow-panel .wf-card.option details.wf-canon{border-color:#b1a0ed;background:#232e4b}",
    "#workflow-panel .wf-example-switch{margin:10px 0 4px;padding:10px 12px;border:1px solid #a1cce7;background:#174665;color:#fff;border-radius:7px;text-align:left;font-weight:600}",
    "#workflow-panel .wf-action-switch{margin:10px 0;padding:12px 14px;border:1px solid #a6b8e1;border-left:4px solid #b1b7f5;border-radius:7px;background:#28344e;color:#f7f8ff}",
    "#workflow-panel .wf-action-switch strong{display:block;font-size:14px;color:#f7f8ff}",
    "#workflow-panel .wf-action-switch p{margin:8px 0;font-size:13px}",
    "#workflow-panel .wf-action-switch small{font-size:11px;color:#cad6e6}",


    "#workflow-panel .wf-card .wf-card-title{font-size:16px;line-height:1.45;margin:5px 0 8px}",
    "#workflow-panel .wf-card .wf-card-title:focus-visible,#workflow-panel .wf-open-graph:focus-visible{outline:2px solid #ffe096;outline-offset:4px}",
    "#workflow-panel .wf-card>small{color:#b9cbdc}",
    "#workflow-panel .wf-card .wf-event-time{display:block;color:#bacbda;font-size:11px;margin:4px 0 8px}",
    "#workflow-panel .wf-card p{font-size:13px;line-height:1.55}",
    "#workflow-panel .wf-card .wf-result-note{border-left:2px solid #9bc5b0;padding:8px 12px;background:#0b17252e;white-space:pre-wrap;border-radius:0 5px 5px 0}",
    "#workflow-panel .wf-card details.wf-canon,#workflow-panel .wf-card details.wf-qrpe{border:1px solid var(--rdg-canon-line);border-left-width:3px;border-radius:7px;padding:9px 11px;margin:12px 0;background:var(--rdg-canon-bg)}",
    "#workflow-panel .wf-card details.wf-qrpe{border-color:var(--rdg-qrpe-line);background:var(--rdg-qrpe-bg)}",
    "#workflow-panel .wf-card details>summary{padding:0;color:#e9f3f6;font-weight:600;font-size:12px}",
    "#workflow-panel .wf-canon-case{border-left:2px solid #75bfa9;margin-top:12px;padding:2px 10px}",
    "#workflow-panel .wf-canon-case[data-valence=negative]{border-left-color:#d7a0a0}",
    "#workflow-panel .wf-canon-case strong{font-size:12px}",
    "#workflow-panel .wf-canon-case ul{margin:5px 0}",
    "#workflow-panel .wf-card .wf-qrpe-preview{color:#ffcf8f}",
    "#workflow-panel .wf-variants{display:block;border-left:2px solid var(--rdg-action-line);gap:16px;margin:18px 0 0;padding-left:14px}",
    "#workflow-panel .wf-variant-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:16px}#workflow-panel .wf-variant-list>.wf-card{box-shadow:none;padding:12px;border-left-width:3px;margin:0}",
    "#workflow-panel .wf-variant-list>.wf-card .wf-card-title{font-size:14px}",
    "#workflow-panel .wf-card .wf-card-place,#workflow-panel .wf-card .wf-open-graph{font-size:12px;padding:6px 10px;margin:8px 0 0;background:#0b172533;border-color:#8d9eb4}",
    "#workflow-panel .wf-history-event{padding:14px 18px;font-size:13px;background:var(--rdg-history-bg);border-color:var(--rdg-history-line)}",
    "#workflow-panel .wf-history-event>strong{display:block;color:#cfdbe8;font-size:13px;margin:0 0 7px}",
    "#workflow-panel .wf-changed-nodes{display:flex;flex-wrap:wrap;gap:8px}",
    "#workflow-panel .wf-plan-boundary{position:relative;margin:32px 0 24px;padding:18px 20px;background:#203d50;border:1px solid #709eb7;border-left:5px solid #8ec9e2;border-radius:10px}",
    "#workflow-panel .wf-plan-boundary::before{content:\"\";position:absolute;width:14px;height:14px;box-sizing:border-box;top:26px;left:-39px;background:#8ec9e2;border:3px solid #17283b;border-radius:50%;box-shadow:0 0 0 3px #8ec9e2}",
    "#workflow-panel .wf-plan-boundary small{color:#acd0e1;font-size:11px;letter-spacing:.04em}",
    "#workflow-panel .wf-plan-boundary h3{margin:6px 0;font-size:20px}",
    "#workflow-panel .wf-plan-boundary p{margin:0;color:#c8dce7;font-size:12px}",
    "@media(max-width:650px){#workflow-panel .wf-timeline{padding-left:18px}#workflow-panel .wf-card{padding:12px;margin-bottom:20px}#workflow-panel .wf-history>.wf-card::before,#workflow-panel .wf-future>.wf-card::before{left:-30px}#workflow-panel .wf-plan-boundary{padding:14px}#workflow-panel .wf-plan-boundary::before{left:-32px}#workflow-panel .wf-toolbar{gap:8px;padding:8px 0}#workflow-panel .wf-toolbar .wf-jump-plan{margin-left:0}#workflow-panel .wf-toolbar .wf-status{flex:1 1 120px;font-size:11px}#workflow-panel .wf-variants{padding-left:10px}#workflow-panel .wf-variant-list{grid-template-columns:1fr}}",
    "@media(prefers-reduced-motion:reduce){#workflow-page{scroll-behavior:auto}}",
    "#bar #back,#bar #example-set-map,#edge-toolbar #edges-core,#edge-toolbar #edges-all{display:none!important}",
    "#panel[data-view=workflow] #viewer-more,#panel[data-view=dependencies] #viewer-more{display:none!important}",
    "#dependency-page{flex:1;min-height:0;overflow:auto;background:#17283b;color:#e5eff7;padding:18px 22px;box-sizing:border-box}#dependency-page h2{font-size:19px;margin:5px 0}#dependency-page header p{font-size:12px;color:#b6cadd;line-height:1.5}#dependency-page .dep-controls{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin:16px 0}#dependency-page select,#dependency-page button{font:inherit;font-size:12px;border:1px solid #7389a0;border-radius:6px;background:#24405a;color:#ecf6ff;padding:7px 10px}#dependency-page .dep-controls label{font-size:12px}#dependency-page .dep-item{padding:15px;border:1px solid #536b80;border-left:4px solid #96afc8;border-radius:8px;margin:12px 0;background:#203449;max-width:1020px}#dependency-page .dep-item[data-status=review_required]{border-left-color:#f3bd72}#dependency-page .dep-item[data-status=valid]{border-left-color:#81cba4}#dependency-page .dep-item h3{margin:0 0 8px;font-size:15px}#dependency-page .dep-item>p,#dependency-page .dep-item li{font-size:12px;line-height:1.5}#dependency-page .dep-item small{color:#b7c9d9;font-size:11px}#dependency-page .dep-item details{margin:12px 0}#dependency-page .dep-item summary{cursor:pointer;font-size:12px;color:#bce1f8}#dependency-page .dep-item button{margin:5px 8px 5px 0}#dependency-page .dep-item button:disabled{opacity:.55;cursor:not-allowed}#dependency-page .dep-item .dep-reasons{white-space:pre-wrap;color:#b8d5e5}#dependency-page .dep-item .dep-history{white-space:pre-wrap;color:#b8d5e5;padding:8px}#dependency-page .dep-item .dep-changed{color:#ffcf9a}#dependency-page .dep-scope-state{color:#b9cadc}#dependency-items>.dep-empty{font-size:13px;color:#aec6d8}#dependency-page .dep-controls button:focus-visible,#dependency-page .dep-item button:focus-visible{outline:2px solid #ffe096}",
    "#bar #viewer-more{position:relative;flex-shrink:0}#bar #viewer-more>summary{list-style:none;cursor:pointer;border:1px solid #506681;border-radius:6px;padding:6px 11px;background:#263b52;font-size:18px;line-height:1}#bar #viewer-more>summary::-webkit-details-marker{display:none}",
    "#bar #viewer-more[open] .viewer-more-actions{position:absolute;right:0;top:calc(100% + 6px);z-index:20;width:min(280px,80vw);padding:9px;display:flex;flex-direction:column;gap:6px;border:1px solid #526680;border-radius:7px;background:#1c3045;box-shadow:0 10px 26px #0009}#bar .viewer-more-actions>button{display:block;width:100%;text-align:left;white-space:normal}#bar .viewer-more-actions>button[hidden]{display:none}",
    "#edge-toolbar{overflow:visible;max-height:none;gap:8px;align-items:center}#edge-toolbar[hidden]{display:none}#edge-toolbar #edges-selector{display:flex;align-items:center;gap:7px;white-space:nowrap}#edge-toolbar #edges-selector[hidden]{display:none!important}#edge-toolbar #edges-mode{font:inherit;color:#e4edf7;background:#263b52;border:1px solid #506681;border-radius:6px;padding:5px}#edge-toolbar #search{margin-left:auto;max-width:230px;min-width:110px;flex:1 1 120px;box-sizing:border-box;padding:5px 7px}#edge-toolbar #search[hidden]{display:none}#edge-toolbar #fit{white-space:nowrap}#edge-toolbar #fit[hidden]{display:none}",
    "#view-options{position:relative;flex-shrink:0}#view-options>summary{cursor:pointer;list-style:none;white-space:nowrap;border:1px solid #506681;border-radius:6px;padding:6px 9px;background:#263b52}#view-options>summary::-webkit-details-marker{display:none}#view-options[open]>.view-options-body{position:absolute;right:0;top:calc(100% + 6px);z-index:12;box-sizing:border-box;width:min(470px,calc(100vw - 32px));max-height:min(68vh,520px);overflow:auto;padding:12px;border:1px solid #637a93;border-radius:8px;background:#1c3045;box-shadow:0 12px 24px #0009}#view-options .view-options-body>button{margin:2px 3px 8px 0}#view-options .view-options-body>details{margin:8px 0}#view-options #graph-help{margin-left:0}#view-options #layout-controls summary{background:#29465f}#edge-toolbar:has(#view-options[open]),#edge-toolbar:has(#layout-controls[open]),#edge-toolbar:has(#graph-help[open]){max-height:none;overflow:visible}",
    "#graph-meta #level-up{align-self:center;flex-shrink:0;padding:3px 7px;font-size:11px}#graph-meta #level-up[hidden]{display:none}#graph-meta #layout-status[data-state=error]{font-weight:600}#graph-meta #message{max-height:44px;overflow:hidden}",
    "@media(max-width:650px){#edge-toolbar{max-height:none;overflow:visible}#edge-toolbar #edges-mode{max-width:130px}#edge-toolbar #search{max-width:100%;order:2;flex-basis:130px}#view-options[open]>.view-options-body{position:fixed;top:clamp(145px,24vh,225px);left:12px;right:12px;width:auto;max-height:calc(100dvh - clamp(145px,24vh,225px) - 20px)}#bar #viewer-more[open] .viewer-more-actions{position:fixed;top:clamp(58px,14vh,135px);left:12px;right:12px;width:auto}#graph-meta #message{max-height:44px}}",
    '</style>',
    '<button id="launch">Граф R–D</button><section id="panel"><div id="bar">',
    '<button id="back" hidden>← Назад</button><button id="example-set-map" hidden>К полному графу</button><strong id="bar-title">Графы R–D</strong><span id="viewer-version" title="Версия скрипта R-D Graph Viewer" aria-label="Версия Viewer"></span>',
    '<div id="view-tabs" role="tablist" aria-label="Разделы Viewer"><button id="graph-tab" role="tab" aria-selected="true" aria-controls="graph-pane">Граф</button><button id="workflow-toggle" role="tab" aria-selected="false" aria-controls="workflow-page">План во времени</button><button id="dependency-toggle" role="tab" aria-selected="false" aria-controls="dependency-page">Зависимости</button></div>',
    '<details id="viewer-more"><summary title="Открытие файлов и обновление">⋯</summary><div class="viewer-more-actions"><button id="file">Открыть другой JSON…</button><button id="reload" hidden>Перечитать граф из файла</button><button id="source" hidden>Исходный модуль</button></div></details><button id="close" aria-label="Закрыть Viewer">×</button></div>',
    '<div id="graph-pane" role="tabpanel" aria-labelledby="graph-tab"><div id="graph-meta"><button id="level-up" hidden>← Уровень выше</button><div id="breadcrumbs" aria-label="Путь"></div><div id="layout-indicator"><span id="layout-status" role="status" aria-live="polite"></span></div><div id="message" role="status">Загрузка локальных графов…</div><p id="graph-scope-hint" role="status" aria-live="polite" hidden></p></div>',
    '<div id="catalog"><div id="catalog-header"><button id="folder-back" hidden>← Все папки</button><h2 id="catalog-title">Папки графов</h2>',
    '<p id="catalog-description">Выберите папку, чтобы открыть рабочие графы, примеры или готовые 2D-модели.</p></div>',
    '<input id="catalog-search" type="search" placeholder="Найти папку, набор или граф" aria-label="Поиск в проводнике"><div id="folder-list" aria-label="Папки графов"></div>',
    '<div id="graph-list" aria-label="Графы и наборы"></div></div>',
    '<div id="edge-toolbar" hidden><label id="edges-selector"><span id="edges-selector-title">Связи:</span> <select id="edges-mode" aria-label="Режим представления графа"><option value="core">Основные связи</option><option value="all">Связи и контекст</option></select></label><button id="edges-core" hidden aria-pressed="true">Основная цепочка</button><button id="edges-all" hidden aria-pressed="false">Связи и контекст</button><button id="variants-all" aria-pressed="false">Варианты: Только выбранные</button><button id="collections-collapse" hidden>Свернуть группы</button><input type="search" id="search" hidden placeholder="Найти узел" aria-label="Найти Requirement или Action"><button id="fit" hidden title="Вместить видимую схему в экран; позиции блоков не изменятся">Вместить в экран</button><details id="view-options"><summary>Вид ⚙</summary><div class="view-options-body"><button id="context-fields">Поля контекста</button><button id="workflow-graph-toggle" hidden>Изменить граф</button><button id="context-mode" hidden aria-pressed="false">Просмотр контекста: выкл.</button><details id="layout-controls"><summary>Расположение блоков</summary><div class="layout-actions"><button id="layout-connect">Подключить файл расположений</button><button id="layout-save">Записать расположение</button><button id="layout-pause">Приостановить автосохранение</button><button id="layout-open">Файл расположений</button><button id="layout-export">Экспорт расположения</button><button id="layout-reset">Авторасположение</button><button id="layout-discard">Отменить правки расположения</button><button id="layout-drafts">Восстановить черновик…</button></div><div id="layout-draft-list" class="layout-actions"></div></details><details id="graph-help"><summary>Справка о графе</summary><div class="graph-help-body"><div id="edge-legend"></div><p id="edge-label-hint"></p></div></details></div></details></div>',
    '<section id="workflow-graph-editor" hidden aria-label="Редактор подключённого графа"></section><div id="content" hidden><div id="canvas-wrap"><svg id="canvas"></svg><button id="inspector-toggle" aria-controls="info" aria-expanded="false">Сведения</button><div id="pan-hint">↔ Перетащите схему: продолжение за краем экрана</div></div><aside id="info">Выберите узел или подпись стрелки.</aside></div>',
    '<div id="source-view" hidden><pre id="source-text"></pre></div></div>',
    '<section id="workflow-page" hidden role="tabpanel" aria-labelledby="workflow-toggle"><div id="workflow-connection-box"><details id="workflow-settings"><summary>Настройки плана</summary><div><h3>Подключение локального Helper</h3><p id="workflow-help">Для каждого рабочего графа существует один настоящий Plan owner. Viewer сначала читает его локальный файл; при отсутствии разрешения на file:// может показать только явно опубликованный снимок реального Plan owner той же ревизии. Если ни файла, ни допустимого снимка нет — сообщение об ошибке, а не вымышленный Plan. Чтобы редактировать размещения и проверить полный журнал истории, подключите папку session, созданную авторизованным Helper. Обмен Helper с браузером идёт через файлы запросов и ответов. Браузер выдаёт доступ странице chatgpt.com к выбранной папке; выбирайте отдельную папку session, а не весь проект.</p><button id="workflow-reconnect" hidden>Подключить сохранённую папку</button><button id="workflow-connect">Подключить папку сессии</button><button id="workflow-forget" hidden>Забыть папку</button><p id="workflow-folder-note"></p></div></details><p id="workflow-connection" role="status" aria-live="polite">Выберите рабочий граф. Сохранённый план открывается во вкладке «План во времени».</p></div><section id="workflow-panel" hidden aria-label="Редактор плана и история"></section></section><section id="dependency-page" hidden role="tabpanel" aria-labelledby="dependency-toggle"><header><h2>Зависимости Graph · Gendocen</h2><p id="dependency-status" role="status" aria-live="polite">Откройте рабочий граф и подключите Helper с Gendocen.</p><div class="dep-controls"><button id="dependency-refresh">Проверить зависимости</button><button id="dependency-all">Весь граф</button><select id="dependency-scope" aria-label="Зависимости конкретной Requirement"><option value="">Все Requirements графа</option></select><label><input type="checkbox" id="dependency-show-valid">Показывать также проверенные</label></div></header><section id="dependency-items" aria-label="Предупреждения и зависимости"></section></section></section>',
    '<input type="file" id="picker" accept=".json,application/json" hidden>'
  ].join('');
  const el = id => root.getElementById(id);
  el('viewer-version').textContent='Viewer v'+VIEWER_VERSION;
  const svg = el('canvas'), info = el('info');
  function setInspector(open){
    el('content').classList.toggle('info-open',open);
    el('inspector-toggle').setAttribute('aria-expanded',String(open));
    el('inspector-toggle').textContent=open?'Скрыть сведения':'Сведения';
  }
  el('inspector-toggle').onclick=()=>{
    setInspector(!el('content').classList.contains('info-open'));
    if(selected)centerNode(selected);else fit();
  };
  const message = text => { el('message').textContent = text;el('message').title=text; };
  const launcher = el('launch');
  if (!launcher) throw new Error('[RDG] Launcher was not created');
  console.info('[RDG Viewer] loaded v'+VIEWER_VERSION);
  const launcherPositionKey = 'rdg-viewer-launcher-position-v1';
  let launcherDrag = null;
  let suppressLauncherClickUntil = 0;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  function positionLauncher(x, y) {
    const rightmost = Math.max(8, window.innerWidth - launcher.offsetWidth - 8);
    const lowest = Math.max(8, window.innerHeight - launcher.offsetHeight - 8);
    host.style.right = 'auto';
    host.style.bottom = 'auto';
    host.style.left = clamp(x, 8, rightmost) + 'px';
    host.style.top = clamp(y, 8, lowest) + 'px';
  }
  try {
    const stored = JSON.parse(localStorage.getItem(launcherPositionKey));
    if (stored && Number.isFinite(stored.x) && Number.isFinite(stored.y))
      positionLauncher(stored.x, stored.y);
  } catch (_) { /* Local storage can be unavailable in restricted contexts. */ }
  launcher.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const rect = launcher.getBoundingClientRect();
    launcherDrag = { id: event.pointerId, startX: event.clientX,
      startY: event.clientY, x: rect.left, y: rect.top, moved: false };
    launcher.setPointerCapture(event.pointerId);
  });
  launcher.addEventListener('pointermove', event => {
    if (!launcherDrag || event.pointerId !== launcherDrag.id) return;
    const dx = event.clientX - launcherDrag.startX;
    const dy = event.clientY - launcherDrag.startY;
    if (!launcherDrag.moved && Math.hypot(dx, dy) < 6) return;
    launcherDrag.moved = true;
    positionLauncher(launcherDrag.x + dx, launcherDrag.y + dy);
  });
  function endLauncherDrag(event) {
    if (!launcherDrag || event.pointerId !== launcherDrag.id) return;
    if (launcherDrag.moved) {
      suppressLauncherClickUntil = Date.now() + 350;
      try {
        localStorage.setItem(launcherPositionKey, JSON.stringify({
          x: parseFloat(host.style.left), y: parseFloat(host.style.top)
        }));
      } catch (_) { /* The button remains movable without persistence. */ }
    }
    launcherDrag = null;
  }
  launcher.addEventListener('pointerup', endLauncherDrag);
  launcher.addEventListener('pointercancel', endLauncherDrag);
  window.addEventListener('resize', () => {
    if(viewportWidth===window.innerWidth&&viewportHeight===window.innerHeight)return;
    viewportWidth=window.innerWidth;viewportHeight=window.innerHeight;
    if (host.style.left) positionLauncher(parseFloat(host.style.left), parseFloat(host.style.top));
    if(graph&&!el('content').hidden){if(selected)centerNode(selected);else fit();}

  });
  function folderLabel(id){return catalogModel?.folders.find(f=>f.id===id)?.title||id||'Папки';}
  function rememberFullView(){if(fullMode&&sourceGraph)fullViewStates.set(activeFullRootSlug,{view:{...view},search:el('search').value,showAlternatives:showAllVariants,showDetails:showAuxiliaryEdges,positions:[...positions].map(([id,p])=>[id,{...p}])});}
  function breadcrumbs(){
    const target=el('breadcrumbs');target.replaceChildren();
    const add=(title,fn)=>{const button=document.createElement('button');button.textContent=title;button.onclick=fn;target.appendChild(button);};
    add('Папки',()=>openFolder(''));
    let prefix='';
    for(const piece of (selectedFolder||'').split('/').filter(Boolean)){
      prefix=prefix?prefix+'/'+piece:piece;const id=prefix;add(folderLabel(id),()=>openFolder(id));
    }
    if(activeFullRootSlug&&!el('content').hidden){const full=catalogModel?.fullGraphs.find(g=>g.slug===activeFullRootSlug);if(full)add(full.title,()=>openFullGraph(full.slug));}
    if(!fullMode&&!el('content').hidden&&graph){const title=document.createElement('span');title.textContent=graphRoot(graph)?.title||graph.title||'Граф';target.appendChild(title);}
  }
  function openFolder(id){
    if(!manualEditor){activeSlug=null;activeFullRootSlug=null;showLocalWorkingPlan();}
    explorerStates.set(selectedFolder,{query:el('catalog-search').value,scroll:el('catalog').scrollTop||0});
    selectedFolder=id;activeFullRootSlug=null;
    showCatalog();
    const state=explorerStates.get(id);el('catalog-search').value=state?.query||'';renderCatalog();el('catalog').scrollTop=state?.scroll||0;
  }
  function showCatalog(){
    rememberFullView();
    if(coreStandalone)coreStandalone.hidden=true;
    el('workflow-graph-editor').hidden=true;
    el('catalog').hidden=false;el('content').hidden=true;el('edge-toolbar').hidden=true;
    el('graph-scope-hint').hidden=true;
    el('source-view').hidden=true;el('source').hidden=true;
    for(const id of ['back','level-up','example-set-map','reload','fit','search'])el(id).hidden=true;
    levelStack=[];renderCatalog();
    el('bar-title').textContent=folderLabel(selectedFolder);
    message(catalogModel?'Выберите папку и полный граф Requirements; старые одиночные графы остаются доступными отдельно.':'Загрузка локальных графов…');
    breadcrumbs();updateLayoutControls();
  }
  let coreStandalone=null,coreStandaloneController=null;
  function showGraph(){
    if(sourceGraph?.coreModel==='rdg-core-v1'){
      el('catalog').hidden=true;el('content').hidden=true;el('edge-toolbar').hidden=true;el('source-view').hidden=true;
      for(const id of ['fit','search','level-up','source','example-set-map'])el(id).hidden=true;
      el('reload').hidden=false;
      const writable=source==='helper'&&workflowSnapshot&&workflowGraphFile===workflowSnapshot.graphFile;
      el('workflow-graph-editor').hidden=!writable;
      if(writable){if(coreStandalone)coreStandalone.hidden=true;return;}
      if(!coreStandalone){coreStandalone=document.createElement('section');el('graph-pane').appendChild(coreStandalone);}
      coreStandalone.hidden=false;coreStandalone.replaceChildren();
      coreStandalone.style.overflow='auto';coreStandalone.style.flex='1';
      coreStandaloneController=globalThis.RDGWorkflowUI.mountCore(coreStandalone,sourceGraph,{document,readOnly:true,focusId:localRootId||sourceGraph.rootRequirementId});
      message('Снимок уточнённой модели · только чтение. Изменения доступны через подключённый Helper.');
      return;
    }
    if(coreStandalone)coreStandalone.hidden=true;
    el('workflow-graph-toggle').hidden=!workflowSnapshot||workflowSnapshot.exampleOnly||workflowGraphFile!==workflowSnapshot.graphFile;
    if(el('workflow-graph-toggle').hidden)el('workflow-graph-editor').hidden=true;
    el('catalog').hidden=true;el('content').hidden=false;el('edge-toolbar').hidden=false;el('source-view').hidden=true;
    el('context-mode').hidden=!fullMode;
    el('context-mode').setAttribute('aria-pressed',String(stateMode));
    el('context-mode').textContent='Просмотр контекста: '+(stateMode?'вкл.':'выкл.');
    renderEdgeLegend();
    el('source').hidden=fullMode||sourceMarkdownFor(graph)===null;el('source').textContent='Исходный модуль';
    for(const id of ['fit','search'])el(id).hidden=false;
    el('back').hidden=true; // Breadcrumb navigation replaces duplicate Back/full-graph controls.
    el('reload').hidden=false;
    el('level-up').hidden=fullMode||!(levelStack.length||incomingToGraph(activeSlug).length);
    el('level-up').textContent=levelStack.at(-1)?.reference?'← К предыдущему графу':'← Уровень выше';
    const opened=graphs.find(x=>x.slug===activeSlug);
    if(!activeFullRootSlug&&!fullMode)activeFullRootSlug=null;
    el('example-set-map').hidden=true; // The same route exists in breadcrumbs.
    el('example-set-map').textContent='К полному графу';
    el('edges-core').textContent=fullMode?'Графы Requirements':'Основные связи';
    el('edges-all').textContent=fullMode?'Графы и способы':'Связи и контекст';
    el('edges-selector').hidden=!fullMode;
    el('edges-selector-title').textContent='Состав полного графа:';
    el('edges-mode').setAttribute('aria-label','Состав полного графа Requirements');
    const options=el('edges-mode').options||el('edges-mode').children||[];
    if(options[0])options[0].textContent='Графы Requirements';
    if(options[1])options[1].textContent='Графы + Actions и каноны';
    // Local R shows the complete one-wave structure without a second filter.
    const hint=el('graph-scope-hint');hint.hidden=false;
    hint.textContent=fullMode?
      'ПОЛНЫЙ ГРАФ · блоки «ГРАФ R» ведут к локальным графам целей (одна волна); это не отдельные сущности.':
      'ЛОКАЛЬНЫЙ ГРАФ ОДНОЙ ВОЛНЫ · все отношения R, Actions, канонов и контекста видны сразу; второстепенные линии приглушены. Нажмите дочернюю R для её графа.';
    el('bar-title').textContent=fullMode?graph.title:graphRoot(graph)?.title||graph?.title||'Граф';
    for(const id of ['edges-core','edges-all'])el(id).hidden=false;
    el('search').placeholder=fullMode?'Найти Requirement':'Найти узел';
    fitVisibleNodeText();fit(!fullMode);breadcrumbs();updateLayoutControls();
  }
  function outgoingForRequirement(slug,id){return graphRelations.filter(r=>r.from===slug&&r.requirementId===id);}
  function incomingToGraph(slug){return graphRelations.filter(r=>r.to===slug);}
  function childLevelForRequirement(id){
    if(id===graphRoot(graph)?.id)return null;
    const matches=outgoingForRequirement(activeSlug,id);
    if(matches.length===1)return matches[0].to;
    return sourceGraph?.edges.some(e=>e.from===id&&e.archived!==true&&['OPTION_FOR','DRIVES','DERIVES'].includes(e.type))?
      {localRootId:id}:null;
  }
  function graphRoot(g) {
    if(!g?.nodes)return null;
    if(g.rootRequirementId)return g.nodes.find(n=>n.id===g.rootRequirementId&&n.kind==='requirement')||null;
    // Older teaching files start with their main R. This display fallback
    // does not create identities, hierarchy links or new persisted records.
    const first=g.nodes[0];
    if(first?.kind!=='requirement'||g.edges?.some(e=>e.type==='INTRODUCES'&&e.to===first.id))return null;
    return g.nodes.length===1||g.edges?.some(e=>e.type==='DRIVES'&&e.from===first.id)?first:null;
  }
  function isUnit(item){return (item.planningScale||item.graph?.planningScale)==='unit';}
  function scaleLabel(g){return g?.planningScale==='unit'?'Узкая задача · Unit':'План · TM';}
  function sourceMarkdownFor(g){
    const seen=new Set();
    while(g && typeof g.sourceMarkdown!=='string' && g.sourceOwnerGraphSlug){
      if(seen.has(g.sourceOwnerGraphSlug))return null;
      seen.add(g.sourceOwnerGraphSlug);g=graphs.find(x=>x.slug===g.sourceOwnerGraphSlug)?.graph;
    }
    return typeof g?.sourceMarkdown==='string'?g.sourceMarkdown:null;
  }
  function graphCaption(item){return graphRoot(item.graph)?.title||item.title||item.slug;}
  function usageLabel(p){return p?.usage==='ready'?'Готовый':p?.usage==='working'?'Рабочий':'Назначение не указано';}
  function itemMeta(item){
    const p=item.presentation||{};
    return [item.kind==='folder'?'Папка':item.kind==='full-graph'?'Полный граф':'Граф',
      item.kind==='folder'?'':usageLabel(p),p.exampleOnly?'Учебный':'',p.archived?'Архив':'',
      item.graph?.readOnly?'Только чтение':''].filter(Boolean).join(' · ');
  }
  function renderCatalog(){
    const list=el('graph-list'),folderList=el('folder-list');list.replaceChildren();folderList.replaceChildren();
    list.hidden=false;folderList.hidden=false;
    el('folder-back').hidden=!selectedFolder;
    el('catalog-title').textContent=folderLabel(selectedFolder);
    el('catalog-description').textContent=catalogModel?.folders.find(f=>f.id===selectedFolder)?.presentation?.description||'Папки и полные графы Requirements';
    if(!catalogModel)return;
    const query=el('catalog-search').value||'';
    const entries=query.trim()?catalogCore.searchCatalog(catalogModel,query):catalogCore.listFolder(catalogModel,selectedFolder);
    for(const item of entries){
      const row=document.createElement('button');row.type='button';row.className='explorer-row';
      row.setAttribute('data-kind',item.kind);
      if(item.kind==='folder')row.setAttribute('data-folder',item.id);
      else if(item.kind==='full-graph')row.setAttribute('data-full-root',item.slug);
      else row.setAttribute('data-graph',item.slug);
      const title=document.createElement('span');title.className='explorer-title';title.textContent=item.title;row.appendChild(title);
      const meta=document.createElement('span');meta.className='explorer-meta';meta.textContent=itemMeta(item);row.appendChild(meta);
      if(item.presentation?.description){const desc=document.createElement('span');desc.className='explorer-description';desc.textContent=item.presentation.description;row.appendChild(desc);}
      row.onclick=async()=>{
        if(item.kind==='folder'){openFolder(item.id);return;}
        explorerStates.set(selectedFolder,{query:el('catalog-search').value,scroll:el('catalog').scrollTop||0});
        if(item.kind==='full-graph'){await openFullGraph(item.slug);return;}
        activeFullRootSlug=null;selectedFolder=item.folder;
        try{await loadGraphSlug(item.slug);}catch(error){message(error.message);}
      };
      (item.kind==='folder'?folderList:list).appendChild(row);
    }
    if(!entries.length){const empty=document.createElement('p');empty.textContent=query?'Ничего не найдено.':'В этой папке пока нет графов.';list.appendChild(empty);}
  }
  const rootProjection=globalThis.RDGRootProjection;
  function fullProjectedGraph(){
    const wanted=sourceGraph.nodes.filter(n=>
      (showAllVariants||n.branchState!=='potential')&&
      (showAuxiliaryEdges||n.kind==='requirement'));
    const ids=new Set(wanted.map(n=>n.id));
    const edges=sourceGraph.edges.filter(e=>
      ids.has(e.from)&&ids.has(e.to)&&(showAllVariants||e.branchState!=='alternative')&&
      (showAuxiliaryEdges?!e.rootOnly:!e.fullDetailOnly));
    const decorations=[];
    for(const method of wanted.filter(n=>['option','action','decision'].includes(n.kind))){
      const owner=graphs.find(g=>g.slug===method.sourceGraphSlug)?.graph;
      const option=method.kind==='decision'&&method.selectedOptionId?
        owner?.nodes.find(n=>n.id===method.selectedOptionId&&n.kind==='option'):null;
      // A visible Option owns its own block. Otherwise the selected Decision
      // carries that Option's canon without inventing a causal child.
      if(option&&wanted.some(n=>n.kind==='option'&&n.sourceGraphSlug===method.sourceGraphSlug&&
        n.id.split('::').slice(1).join('::')===option.id))continue;
      const material=option||method;if(!material.canonBlock)continue;
      const id='__canon__'+method.id;
      decorations.push({id,kind:'canon',canonForId:material.id,
        title:'Канон '+material.title,canonBlock:material.canonBlock,
        contextChecks:material.contextChecks,sourceGraphSlug:method.sourceGraphSlug,
        branchState:method.branchState});
      edges.push({id:'__viewcanon__'+method.id,type:'VIEW_CANON',from:method.id,to:id});
    }
    return {...sourceGraph,nodes:[...wanted,...decorations],edges,
      alternativeCount:sourceGraph.nodes.filter(n=>n.kind==='requirement'&&n.branchState==='potential').length};
  }
  async function openFullGraph(slug,{fresh=false}={}){
    if(activeFullRootSlug!==slug&&manualEditor?.switchBlocked)
      throw Error('Завершите запись в прежнем плане перед выбором другого рабочего графа');
    if(!catalogModel)throw Error('Каталог ещё не загружен');
    // A user-requested refresh reads a NEW index and ALL files in this
    // identitySpace. Do not blend stale embedded graphs with current files.
    // Only swap the catalog after every source and the projection validates.
    const manifest=fresh?JSON.parse(await readLocalFile('index.json')):null;
    const nextCatalog=fresh?catalogCore.normalizeCatalog(manifest):catalogModel;
    const entry=nextCatalog.fullGraphs.find(g=>g.slug===slug);
    if(!entry||entry.actionModel&&entry.actionModel!=='candidate-v6')
      throw Error('Корневой граф недоступен: старая модель не работает, выберите candidate-v6: '+slug);
    const coreEntry=nextCatalog.graphs.find(it=>it.slug===slug);
    if(entry.coreModel==='rdg-core-v1'||coreEntry?.coreModel==='rdg-core-v1'||coreEntry?.graph?.coreModel==='rdg-core-v1'){
      const snapshotText=fresh||!coreEntry.graph?await readLocalFile(coreEntry.file):JSON.stringify(coreEntry.graph);
      const checked=validate(JSON.parse(snapshotText));
      if(checked.identitySpace!==entry.identitySpace||checked.rootRequirementId!==entry.rootRequirementId)
        throw Error('Расхождение core owner с каталогом');
      if(fresh){catalogModel=nextCatalog;graphs=nextCatalog.graphs;}
      activeFullRootSlug=null;selectedFolder=entry.folder;
      return loadGraphSlug(slug,{snapshotText,readFresh:fresh});
    }
    const all=[],missing=[];
    for(const it of nextCatalog.graphs){
      if((it.identitySpace||it.graph?.identitySpace)!==entry.identitySpace)continue;
      if(!fresh&&it.graph){all.push(it);continue;}
      try{
        const graph=validate(JSON.parse(await readLocalFile(it.file)));
        if(graph.actionModel!=='candidate-v6'||graph.readOnly===true||
           graph.exampleOnly===true||graph.templateOnly===true)
          throw Error('OLD_GRAPH_MODEL_DISABLED: требуются только рабочие графы candidate-v6');
        if(graph.identitySpace!==entry.identitySpace||
           graph.rootRequirementId!==(it.rootRequirementId||graph.rootRequirementId))
          throw Error('Расхождение identitySpace/rootRequirementId с индексом');
        all.push({...it,graph});
      }catch(error){
        if(fresh)throw Error('Полный граф не обновлён: '+it.slug+' — '+error.message);
        missing.push(it.slug);
      }
    }
    const data=rootProjection.project({graphs:all,relations:nextCatalog.relations},slug);
    // Preserve current content and navigation if the refresh fails.
    rememberFullView();
    if(fresh){
      for(const item of all)nextCatalog.graphs.find(g=>g.slug===item.slug).graph=item.graph;
      catalogModel=nextCatalog;graphs=catalogModel.graphs;
      graphRelations=catalogModel.relations.filter(r=>r&&
        graphs.some(g=>g.slug===r.from)&&graphs.some(g=>g.slug===r.to));
      stateSources=manifest.stateGraphs||[];
      projectContexts=manifest.projectContexts&&typeof manifest.projectContexts==='object'?manifest.projectContexts:{};
      sourceUpdateAlerts=Array.isArray(manifest.sourceUpdateAlerts)?manifest.sourceUpdateAlerts:[];
      refreshedSpaces.add(entry.identitySpace);
      renderCatalog();
    }
    const indexedBySlug=new Map(all.map(g=>[g.slug,g]));
    // The same D/Option can have exact projectionOf representations in child
    // files. Show its authoritative semantic record only once in full detail.
    const canonicalCause=(slug,record)=>{
      let owner=slug,node=record;const visited=new Set();
      while(node?.projectionOf){
        const ref=node.projectionOf,key=ref.graphSlug+'|'+ref.nodeId;
        if(visited.has(key))break;visited.add(key);
        const candidate=indexedBySlug.get(ref.graphSlug)?.graph;
        const target=candidate?.nodes.find(n=>n.id===ref.nodeId&&n.kind===node.kind);
        if(!target||candidate.identitySpace!==data.identitySpace)break;
        owner=ref.graphSlug;node=target;
      }
      return {id:'__cause__'+owner+'::'+node.id,sourceGraphSlug:owner,node};
    };
    const decisionAccepted=rootProjection.decisionGuard(indexedBySlug,data.identitySpace);
    const activeProjectionDecision=(d,g)=>decisionAccepted(d,g);
    const nodes=data.nodes.map(n=>({...n,graphSlug:n.sourceGraphSlug}));
    const edges=[];
    const extras=new Map();
    for(const a of data.edges){
      const effective=nodes.find(n=>n.id===a.to)?.branchState==='potential'||
        nodes.find(n=>n.id===a.from)?.branchState==='potential'?'potential':a.kind;
      const state=effective==='potential'||effective==='prepared'?'alternative':'selected';
      const relation={from:a.from,to:a.to,requirementId:a.to,relationKind:a.kind,childRole:a.childRole,
        originatingOptionId:a.causeKind==='option'?a.causeId:null,
        introducedByDecisionId:a.causeKind==='decision'?a.causeId:null,
        introducedByActionId:a.causeKind==='action'?a.causeId:null,
        sourceGraphSlug:a.sourceGraphSlug};
      const item=indexedBySlug.get(a.sourceGraphSlug);
      const cause=item?.graph.nodes.find(n=>n.id===a.causeId && n.kind===a.causeKind);
      if(cause && ['decision','option','action'].includes(a.causeKind)){
        const owner=canonicalCause(a.sourceGraphSlug,cause),causeKey=owner.id;
        if(!extras.has(causeKey))extras.set(causeKey,{...owner.node,id:causeKey,
          title:owner.node.title,branchState:state==='alternative'?'potential':'actual',sourceGraphSlug:owner.sourceGraphSlug});
        edges.push({id:'__r_details_from__'+a.id,type:'VIEW_SET_'+a.kind.toUpperCase(),from:causeKey,to:a.to,
          branchState:state,relation,meaning:'Порождает R: '+a.to});
      }
      edges.push({id:'__r_full__'+a.id,type:'VIEW_SET_'+(a.kind==='refinement'?'DERIVED':a.kind==='potential'||state==='alternative'?'POTENTIAL':a.kind.toUpperCase()),
        from:a.from,to:a.to,branchState:state,relation,
        meaning:'R → R по '+a.causeKind+' '+a.causeId});
    }
    // Full detail includes ALL prepared options and decisions directly attached
    // to reached Requirements, even when a variant introduces no new R.
    // The R-only projection never renders these as source Requirements.
    const reached=new Map(nodes.map(n=>[n.id,n]));
    const attached=new Set();
    for(const it of all){
      if(it.graph.identitySpace!==data.identitySpace)continue;
      const g=it.graph,by=new Map(g.nodes.map(n=>[n.id,n]));
      for(const edge of g.edges){
        if(edge.archived===true||!['OPTION_FOR','DRIVES'].includes(edge.type)||!reached.has(edge.from))continue;
        const cause=by.get(edge.to);
        if(!cause||!(edge.type==='OPTION_FOR'?cause.kind==='option':
          (cause.kind==='decision'||g.actionModel==='candidate-v6'&&cause.kind==='action'))||
          cause.active===false||cause.status==='inactive')continue;
        const currentParent=reached.get(edge.from).branchState==='actual';
        // Same authorization semantics as the R-only root projection.
        const selected=(cause.kind==='action'&&rootProjection.actionActive(cause,g,edge.from))||
          (cause.kind==='decision'&&activeProjectionDecision(cause,g,it.slug))||
          (cause.kind==='option'&&g.nodes.some(d=>d.kind==='decision'&&
            d.active!==false&&activeProjectionDecision(d,g,it.slug)&&d.selectedOptionId===cause.id));
        const effective=currentParent&&selected?'actual':'potential';
        const owner=canonicalCause(it.slug,cause),causeKey=owner.id;
        if(!extras.has(causeKey))extras.set(causeKey,{...owner.node,id:causeKey,
          sourceGraphSlug:owner.sourceGraphSlug,branchState:effective});
        const attachmentKey=edge.from+'→'+causeKey;
        if(attached.has(attachmentKey))continue;
        attached.add(attachmentKey);
        const id='__attachment__'+it.slug+'::'+edge.id;
        const relation={from:edge.from,to:edge.to,requirementId:edge.from,
          relationKind:effective==='actual'?'selected':'potential',sourceGraphSlug:it.slug,
          originatingOptionId:cause.kind==='option'?cause.id:null,
          introducedByDecisionId:cause.kind==='decision'?cause.id:null,
          introducedByActionId:cause.kind==='action'?cause.id:null};
        edges.push({id,type:effective==='actual'?'VIEW_SET_SELECTED':'VIEW_SET_POTENTIAL',
          from:edge.from,to:causeKey,branchState:effective==='actual'?'selected':'alternative',
          relation,fullDetailOnly:true,meaning:'Способ/вариант для R '+edge.from});
      }
    }
    // In the detailed mode replace each R→R shortcut with its exact cause.
    for(const e of edges)if(e.id.startsWith('__r_details_'))e.fullDetailOnly=true;
    for(const e of edges)if(e.id.startsWith('__r_full__')&&e.relation.relationKind!=='refinement')e.rootOnly=true; // DERIVES remains visible in both modes.
    const state=fullViewStates.get(slug);
    fullMode=true;activeFullRootSlug=slug;selectedFolder=entry.folder;activeSlug=null;localRootId=null;levelStack=[];
    showAllVariants=state?.showAlternatives??entry.presentation?.usage==='ready';
    showAuxiliaryEdges=state?.showDetails??false;
    expandedCollections=new Set();selected=null;selectedEdge=null;setInspector(false);
    fullGraphData={rootSlug:slug,projection:data,entry,missing,fresh:fresh||refreshedSpaces.has(entry.identitySpace)};
    sourceGraph={schemaVersion:1,id:'full:'+slug,revision:1,title:entry.title,identitySpace:data.identitySpace,
      rootRequirementId:data.rootRequirementId,readOnly:true,exampleOnly:entry.presentation?.exampleOnly===true,
      nodes:[...nodes,...extras.values()],edges};
    graph=fullProjectedGraph();el('search').value=state?.search||'';
    layout();render();showGraph();
    if(state){for(const [id,p] of state.positions||[])if(positions.has(id))positions.set(id,p);
      applyLayoutPositions();render();Object.assign(view,state.view);transform();}
    message('Полный граф Requirement-графов · '+entry.title+' · '+data.nodes.length+' графов R'+
      (fullGraphData.fresh?' · ранее перечитано из файлов по обновлённому индексу':' · встроенная копия; для изменений нажмите «Обновить»')+
      (missing.length?' · НЕПОЛНЫЙ каталог: '+missing.length+' недоступных файлов':''));
    if(manualEditor)await syncSelectedGraphPlan();
    else showLocalWorkingPlan();
  }
  async function openFullRequirement(n){
    if(n.kind!=='requirement')return;
    const space=sourceGraph.identitySpace;
    const matching=graphs.filter(g=>g.graph?.identitySpace===space&&
      g.graph.rootRequirementId===n.id&&g.slug!==n.sourceGraphSlug&&
      (g.graph.expansionOf?.nodeId===n.id||
       g.graph.nodes.some(x=>x.kind==='requirement'&&x.id===n.id&&x.projectionOf?.nodeId===n.id)));
    if(matching.length>1){
      setInspector(true);info.textContent='Для '+n.title+' найдены несколько представлений. Выберите нужное:';
      for(const item of matching){const button=document.createElement('button');
        button.textContent=item.title;button.onclick=()=>{
          rememberFullView();void loadGraphSlug(item.slug,{localRootId:n.id}).catch(e=>message(e.message));};info.appendChild(button);}
      return;
    }
    rememberFullView();
    await loadGraphSlug(matching[0]?.slug||n.sourceGraphSlug,{localRootId:n.id});
  }
  function projectFullGraph(){return fullProjectedGraph();}
  function graphBranchCaption(n){
    return n.branchState==='potential'?'Потенциальный граф R · ветвь ещё не принята':
      'Граф Requirement · текущий путь';
  }
  function layoutFullGraph(){
    positions=new Map();layoutBands=[];
    // Calculate geometry from what is ACTUALLY on screen. Hidden D/Options
    // must not create invisible generations or distort R-only spacing.
    const coreNodes=graph.nodes.filter(n=>n.kind!=='canon');
    const indegree=new Map(coreNodes.map(n=>[n.id,0])),depth=new Map(),children=new Map(coreNodes.map(n=>[n.id,[]]));
    for(const e of graph.edges){
      if(!indegree.has(e.to)||!children.has(e.from))continue;
      indegree.set(e.to,indegree.get(e.to)+1);children.get(e.from).push(e.to);
    }
    const queue=coreNodes.filter(n=>!indegree.get(n.id)).map(n=>n.id);
    queue.forEach(id=>depth.set(id,0));
    for(let i=0;i<queue.length;i++)for(const child of children.get(queue[i])){
      // DERIVES is a refinement of the same planning problem, not a
      // next-generation Requirement introduced by a chosen method.
      // Keep source R and its composite refinement in one visual column.
      const refinement=graph.edges.some(e=>e.from===queue[i]&&e.to===child&&
        e.relation?.relationKind==='refinement');
      depth.set(child,Math.max(depth.get(child)||0,Math.min(30,depth.get(queue[i])+(refinement?0:1))));
      indegree.set(child,indegree.get(child)-1);if(!indegree.get(child))queue.push(child);
    }
    const columns=new Map();
    for(const n of coreNodes){const d=depth.get(n.id)||0;if(!columns.has(d))columns.set(d,[]);columns.get(d).push(n);}
    const incoming=new Map(graph.nodes.map(n=>[n.id,graph.edges.filter(e=>e.to===n.id)]));
    const group=n=>{
      const e=(incoming.get(n.id)||[]).find(e=>e.relation?.originatingOptionId)||
        (incoming.get(n.id)||[]).find(e=>e.relation?.introducedByDecisionId)||
        (incoming.get(n.id)||[])[0];
      return e?.relation?.originatingOptionId||e?.relation?.introducedByDecisionId||e?.from||'';
    };
    const maxRows=Math.max(1,...[...columns.values()].map(xs=>xs.length));
    for(const [d,items] of columns){
      items.sort((a,b)=>(a.branchState==='potential'?1:0)-(b.branchState==='potential'?1:0)||
        group(a).localeCompare(group(b))||a.id.localeCompare(b.id));
      items.forEach((n,i)=>positions.set(n.id,{x:48+d*450,y:72+(maxRows-items.length)*72+i*160}));
    }
    const visible=new Set(graph.nodes.map(n=>n.id));for(const id of positions.keys())if(!visible.has(id))positions.delete(id);
    applyLayoutPositions();
  }
  const edgeDefinitions={
    VIEW_SET_UNKNOWN:{label:'Путь не подтверждён',group:'other',detail:'Тип или основание перехода не подтверждено. Он не объявляется выбранным решением.'},
    VIEW_SET_SELECTED:{label:'Дочерняя R',group:'core',detail:'Переход по выбранному разбиению. Учебный выбор не является решением проекта.'},
    VIEW_SET_PREPARED:{label:'Готовое разбиение',group:'core',detail:'Подготовленный состав, не принятое решение проекта.'},
    VIEW_SET_POTENTIAL:{label:'Потенциальная R',group:'ready',detail:'Будущее продолжение непринятого варианта; не факт исполнения.'},
    VIEW_SET_DERIVED:{label:'Уточнение R',group:'scope',detail:'Уточнение содержания, не выбранное D.'},
    VIEW_SET_SAME_REQUIREMENT:{label:'Та же R',group:'scope',detail:'Другое представление записи той же идентичности.'},
    DRIVES:{label:'требует ответа от D',group:'core',detail:'Requirement является драйвером конкретного Decision; само по себе не означает разбиение.'},
    INTRODUCES:{label:'вводит дочерний R',group:'core',detail:'Решение о разбиении вводит конкретное дочернее Requirement.'},
    DERIVES:{label:'уточняется в R',group:'core',detail:'Содержательное уточнение R, не подмена INTRODUCES.'},
    CONTEXT_FOR:{label:'задаёт условия выбора',group:'ground',detail:'Контекст является основанием/условием решения; не создаёт Requirement.'},
    INFORMS:{label:'передаёт содержание в D',group:'ground',detail:'Содержательная часть одного ответа используется в другом решении; не дочерний Requirement.'},
    IDENTIFIES:{label:'выявляет требование',group:'origin',detail:'Решение обнаружило актуальное Requirement; это не декомпозиция родительской цели.'},
    REVEALS_NEED:{label:'выявляет потребность',group:'origin',detail:'Анализ ответа обнаружил отдельную потребность; не обязательное под-R.'},
    USES_VARIANT:{label:'использует готовый вариант',group:'ready',detail:'Конкретное D или кандидат ссылается на готовый переиспользуемый способ.'},
    OPTION_FOR:{label:'имеет вариант ответа',group:'ready',detail:'Потенциально доступный способ ответа на R, не принятый выбор.'},
    USES_PREPARED:{label:'использует заготовку',group:'ready',detail:'Условное конкретное решение использует подготовленный способ.'},
    PER_ITEM_MODEL:{label:'использует модель элемента',group:'ready',detail:'Повторяемая готовая модель, не количество конкретных применений.'},
    GENERATES_ITEM_ROLE:{label:'задаёт роль элемента',group:'ready',detail:'Роль повторяемого Requirement в готовой схеме; не фактическая ветвь.'},
    INSTANCE_OF_MODEL:{label:'имеет конкретное применение',group:'ready',detail:'Отдельное применение общей модели, не копия её определения.'},
    GOVERNED_BY_SHARED_CHOICE:{label:'задаёт общий способ',group:'ready',detail:'Одно конкретное решение задаёт способ для нескольких применений.'},
    QRPE_FOR:{label:'ставит вопрос к R или D',group:'review',detail:'Вопрос необходимости R или достаточности D; не принятое изменение.'},
    RECONSIDERS:{label:'предлагает пересмотр',group:'review',detail:'Кандидат предлагает пересмотреть выбор; ещё не пересмотренное Decision.'},
    APPLIES_TO:{label:'распространяется на',group:'scope',detail:'Одно сквозное R применяется к другой R, но не является дочерней задачей.'},
    OUTCOME_OF:{label:'возможная под-R',group:'ready',detail:'Потенциальная дочерняя R непринятого способа. Не является текущим обязательством.'},
    VIEW_COLLECTION:{label:'группировка',group:'core',detail:'Список Requirements. Раскрытие показывает только его R; продолжения R открываются отдельными графами.'},
    VIEW_CANON:{label:'канон способа',group:'ready',detail:'Канон принадлежит этому способу и показан над ним. Короткая линия без стрелки обозначает принадлежность, а не введение дочернего Requirement.'}
  };
  const edgeGroups=[
    ['core','Планирование / разбиение'],['ground','Основания выбора'],
    ['origin','Происхождение R'],['ready','Готовые варианты'],
    ['review','Проверка / пересмотр'],['scope','Область действия'],
    ['other','Другие связи']
  ];
  const edgeMeta=type=>edgeDefinitions[type]||{label:String(type),group:'other',detail:'Иллюстративная связь без отдельного согласованного контракта.'};
  // A prepared option is visible by default while its own R has no selected D.
  // A selected ancestor cannot hide options of an undecided child R.
  function optionVisible(id) {
    if(showAllVariants)return true;
    const edge=graph.edges.find(e=>e.type==='OPTION_FOR'&&e.to===id);
    if(!edge)return true;
    return !(sourceGraph?.nodes||graph.nodes).some(n=>n.kind==='decision'&&['committed','selected-in-example-only'].includes(n.status)&&
      n.selectedOptionId&&(sourceGraph?.edges||graph.edges).some(x=>x.type==='OPTION_FOR'&&x.from===edge.from&&x.to===n.selectedOptionId));
  }
  const spineEdge=e=>fullMode||e.type==='VIEW_CANON'||edgeMeta(e.type).group==='core'||
    (e.type==='OPTION_FOR'&&graph.nodes.some(n=>n.id===e.to&&n.kind==='option')&&optionVisible(e.to))||
    (e.type==='OUTCOME_OF'&&optionVisible(e.from));
  const edgeIsVisible=e=>e.archived!==true&&positions.has(e.from)&&positions.has(e.to)&&
    (showAuxiliaryEdges||spineEdge(e));
  const edgeLabel=e=>{
    if(!fullMode)return e.templateOnly&&e.type==='INTRODUCES'?'готовое разбиение · под-R':
      e.templateOnly&&e.type==='DRIVES'?'готовый способ для R':edgeMeta(e.type).label;
    if(e.relation?.relationKind==='refinement')return 'Уточнение R';
    const from=graph.nodes.find(n=>n.id===e.from),to=graph.nodes.find(n=>n.id===e.to);
    const prospective=e.branchState==='alternative';
    if(from?.kind==='requirement'&&to?.kind==='action')
      return prospective?'Action · кандидат':'Action · выбран';
    if(from?.kind==='action'&&to?.kind==='requirement')return prospective?'Возможная R':'R введена Action';
    if(from?.kind==='requirement'&&to?.kind==='decision')
      return prospective?'Рассматривается D':sourceGraph.exampleOnly?'Учебное выбранное D':'Принятое D';
    if(from?.kind==='requirement'&&to?.kind==='option')
      return prospective?'Вариант для R':'Выбранный вариант';
    if(from?.kind==='decision'&&to?.kind==='requirement')
      return prospective?'Возможная R':sourceGraph.exampleOnly?'R от учебно выбранного D':'R от принятого D';
    if(from?.kind==='option'&&to?.kind==='requirement')return 'Возможная R от варианта';
    return prospective?'Возможная R':'Действующая R';
  };
  function renderEdgeLegend(){
    const legend=el('edge-legend');legend.replaceChildren();
    el('edges-mode').value=fullMode&&showAuxiliaryEdges?'all':
      fullMode?'core':'all';
    if(!graph)return;
    if(fullMode){
      legend.textContent='Каждый блок «ГРАФ R» — вход в локальный граф одной Requirement. Сплошные связи показывают текущие пути между графами R; потенциальные ветви отмечены отдельно. Ни один режим просмотра не принимает решение.'+
        (fullGraphData?.fresh?' Данные перечитаны из файлов по обновлённому индексу.':
          ' Встроенная копия: после изменения файлов нажмите «Обновить».');
      el('edge-label-hint').textContent='Графов Requirements: '+graph.nodes.filter(n=>n.kind==='requirement').length+
        ' · переходов: '+graph.edges.length+(fullGraphData.missing.length?' · возможны недоступные продолжения':'');
      el('variants-all').hidden=!sourceGraph.nodes.some(n=>n.branchState==='potential');
      el('variants-all').setAttribute('aria-pressed',String(showAllVariants));
      el('variants-all').textContent=showAllVariants?'Варианты: Все ветви':'Варианты: Принятые';
      el('edges-all').setAttribute('aria-pressed',String(showAuxiliaryEdges));
      el('edges-core').setAttribute('aria-pressed',String(!showAuxiliaryEdges));
      el('collections-collapse').hidden=true;return;
    }
    // Local graph has ONE complete set of relations. Core is not an alternate
    // mode here; all relation types remain visible and differentiated by line
    // treatment and legend. Only a full graph has a projection switch.
    const present=new Set(graph.edges.filter(edgeIsVisible).map(e=>edgeMeta(e.type).group));
    for(const [group,caption] of edgeGroups){
      if(!present.has(group))continue;
      const entry=document.createElement('span');entry.className='edge-legend-item';
      const sample=document.createElement('span');sample.className='edge-legend-symbol g-'+group;
      entry.appendChild(sample);const label=document.createElement('span');
      label.textContent=caption+' ('+graph.edges.filter(e=>edgeIsVisible(e)&&edgeMeta(e.type).group===group).length+')';entry.appendChild(label);legend.appendChild(entry);
    }
    el('edge-label-hint').textContent='Локальный граф одной волны: все '+graph.edges.filter(edgeIsVisible).length+' связи, включая контекст и проверку, видны без переключения. Основной путь выделен линиями и легендой. Нажмите стрелку для пояснения; колесо — прокрутка, Ctrl + колесо — масштаб.';
    el('edges-all').setAttribute('aria-pressed',String(showAuxiliaryEdges));
    el('edges-core').setAttribute('aria-pressed',String(!showAuxiliaryEdges));
    el('variants-all').hidden=sourceGraph?.templateOnly===true||!!graphRoot(graph)&&!sourceGraph.edges.some(e=>e.from===graphRoot(graph).id&&
      (e.type==='OPTION_FOR'||e.type==='DRIVES'&&sourceGraph.actionModel==='candidate-v6'));
    el('collections-collapse').hidden=!(graph?.collections||[]).some(c=>c.memberRefs.length>2);
    el('collections-collapse').disabled=expandedCollections.size===0;
    el('variants-all').setAttribute('aria-pressed',String(showAllVariants));
    el('variants-all').textContent=showAllVariants?'Варианты: Все':'Варианты: Только выбранные';
  }
  function validate(g) {
    if(g?.coreModel)return globalThis.RDGWorkflowUI.validateCoreSnapshot(g);
    if (!g || g.schemaVersion !== 1 || !Array.isArray(g.nodes) || !Array.isArray(g.edges))
      throw Error('Нужны schemaVersion=1, nodes[] и edges[]');
    if(g.planningScale!==undefined&&!['module','unit'].includes(g.planningScale))throw Error('Некорректный масштаб графа');
    if (g.nodes.length > 500) throw Error('В этой версии максимум 500 узлов');
    const ids = new Set(), eid = new Set();
    for (const n of g.nodes) {
      if (!n || typeof n.id !== 'string' || typeof n.title !== 'string' || typeof n.kind !== 'string' || ids.has(n.id))
        throw Error('Некорректный или повторный узел: ' + (n && n.id));
      ids.add(n.id);
    }
    for (const e of g.edges) {
      if (!e || !e.id || eid.has(e.id) || !ids.has(e.from) || !ids.has(e.to) || !e.type)
        throw Error('Некорректная связь: ' + (e && e.id));
      eid.add(e.id);
      if (e.type === 'INTRODUCES' && !ids.has(e.parent)) throw Error('Нет parent для ' + e.id);
    }
    if (g.events !== undefined) {
      if (!Array.isArray(g.events)) throw Error('events должен быть массивом');
      const eventIds=new Set();
      for(const e of g.events){
        if(!e || typeof e.id!=='string' || !e.id.trim() || eventIds.has(e.id) ||
           typeof e.type!=='string' || !e.type.trim() ||
           (e.decisionId!==undefined && !g.nodes.some(n=>n.id===e.decisionId&&n.kind==='decision'))||
           (e.actionId!==undefined && !g.nodes.some(n=>n.id===e.actionId&&n.kind==='action'))) 
          throw Error('Некорректное событие: '+(e&&e.id));
        eventIds.add(e.id);
      }
    }
    for(const n of g.nodes){
      for(const key of ['answerParts','answerBindings','delegations']){
        if(n[key]!==undefined && (!Array.isArray(n[key])||n[key].some(x=>!x||typeof x!=='object')))
          throw Error('Некорректное поле '+key+' узла '+n.id);
      }
    }
    for(const n of g.nodes){
      if(n.answerParts?.some(p=>typeof p.id!=='string'||typeof p.text!=='string'))
        throw Error('Некорректная часть ответа '+n.id);
      if(n.answerBindings?.some(b=>typeof b.requirementId!=='string'||!Array.isArray(b.parts)||b.parts.some(p=>typeof p!=='string')||typeof b.sufficiency!=='string'))
        throw Error('Некорректная адресация ответа '+n.id);
    }
    if(g.collections!==undefined){
      if(!Array.isArray(g.collections))throw Error('collections должен быть массивом');
      const names=new Set();
      for(const c of g.collections){
        if(!c||typeof c.id!=='string'||names.has(c.id)||!ids.has(c.anchor)||!Array.isArray(c.memberRefs)||new Set(c.memberRefs).size!==c.memberRefs.length||
          c.memberRefs.some(id=>id===g.rootRequirementId||!g.nodes.some(n=>n.id===id&&n.kind==='requirement')))
          throw Error('Группа '+(c?.id||'?')+' должна содержать только R с уникальными ID и допустимым anchor');
        names.add(c.id);
      }
    }
    return g;
  }
  function make(tag, parent, attrs, text) {
    const n = document.createElementNS(ns, tag);
    for (const [key,val] of Object.entries(attrs || {})) n.setAttribute(key, String(val));
    if (text !== undefined) n.textContent = text;
    parent.appendChild(n); return n;
  }
  // SVG uses the actual inherited font; character counts cannot bound Cyrillic
  // text. The conservative fallback also works in non-DOM test environments.
  function textWidth(node,value){
    node.textContent=value;
    const measured=node.getComputedTextLength?.();
    const bounds=measured>0?node.getBBox?.():null;
    return measured>0?Math.max(measured,bounds?.width||0):Array.from(value).length*9;
  }
  function fitText(node,value,width=202){
    node.setAttribute('data-fit-width',width);
    value=String(value);
    if(textWidth(node,value)<=width)return value;
    let low=0,high=value.length;
    while(low<high){const mid=Math.ceil((low+high)/2);
      if(textWidth(node,value.slice(0,mid)+'…')<=width)low=mid;else high=mid-1;}
    const result=value.slice(0,low).trimEnd()+'…';node.textContent=result;return result;
  }
  function nodeTitle(group,value){
    let rest=String(value).trim();
    for(let row=0;row<2&&rest;row++){
      const text=make('text',group,{x:10,y:40+row*16,'data-fit-width':202});
      if(row===1){fitText(text,rest);break;}
      if(textWidth(text,rest)<=202){text.textContent=rest;break;}
      let low=1,high=rest.length;
      while(low<high){const mid=Math.ceil((low+high)/2);
        if(textWidth(text,rest.slice(0,mid))<=202)low=mid;else high=mid-1;}
      const space=rest.lastIndexOf(' ',low),cut=space>0?space:low;
      text.textContent=rest.slice(0,cut).trimEnd();rest=rest.slice(cut).trimStart();
    }
  }
  function fitVisibleNodeText(){
    for(const text of root.querySelectorAll('.node text[data-fit-width]')){
      if(text.getComputedTextLength?.()>0)fitText(text,text.textContent,Number(text.getAttribute('data-fit-width')));
    }
  }
  function positionCanonAttachments(){
    const links=graph.edges.filter(e=>e.type==='VIEW_CANON');
    if(!links.length)return;
    const canonIds=new Set(links.map(e=>e.to)),owners=new Set(links.map(e=>e.from));
    // Saved coordinates and navigation caches may still use the old 124px
    // row spacing. Reserve the whole pair, including its connecting gap.
    const groups=graph.nodes.filter(n=>positions.has(n.id)&&!canonIds.has(n.id)).map(n=>{
      const p=positions.get(n.id),attached=owners.has(n.id);
      return {id:n.id,x:p.x,y:p.y-(attached?96:0),h:attached?168:72,attached};
    }).sort((a,b)=>a.y-b.y||a.x-b.x||a.id.localeCompare(b.id));
    const placed=[];
    for(const group of groups){
      for(;;){
        const collisions=placed.filter(other=>(group.attached||other.attached)&&
          group.x<other.x+222&&group.x+222>other.x&&group.y<other.y+other.h&&group.y+group.h>other.y);
        if(!collisions.length)break;
        group.y=Math.max(...collisions.map(other=>other.y+other.h))+28;
      }
      const p=positions.get(group.id),y=group.y+(group.attached?96:0);
      if(p.y!==y)positions.set(group.id,{x:p.x,y});
      placed.push(group);
    }
    for(const e of links){
      const owner=positions.get(e.from);
      if(owner)positions.set(e.to,{x:owner.x,y:owner.y-96});
      else positions.delete(e.to);
    }
  }
  function layout() {
    if(fullMode){layoutFullGraph();return;}
    // The one-wave graph never has a Requirements-only or core-only filter.
    // Additional context nodes still obey localLevelSource's one-hop boundary.
    showAuxiliaryEdges=true;
    positions=new Map();layoutBands=[];
    const order=new Map(graph.nodes.map((n,i)=>[n.id,i]));
    const canonIds=new Set(graph.edges.filter(e=>e.type==='VIEW_CANON').map(e=>e.to));
    const layoutNodes=graph.nodes.filter(n=>!canonIds.has(n.id));
    const rowPitch=canonIds.size?220:124,canonReserve=canonIds.size?96:0;
    const coreEdges=graph.edges.filter(e=>e.archived!==true&&e.type!=='VIEW_CANON'&&spineEdge(e));
    const adjacent=new Map(graph.nodes.map(n=>[n.id,[]]));
    for(const e of coreEdges){adjacent.get(e.from).push(e.to);adjacent.get(e.to).push(e.from);}
    const rootId=graphRoot(graph)?.id;
    const main=new Set(),queue=rootId?[rootId]:[];
    for(let i=0;i<queue.length;i++){
      const id=queue[i];if(main.has(id))continue;main.add(id);
      for(const next of adjacent.get(id)||[])if(!main.has(next))queue.push(next);
    }
    if(!main.size)for(const e of coreEdges){main.add(e.from);main.add(e.to);}
    if(!rootId&&!coreEdges.length){
      layoutNodes.forEach((n,i)=>positions.set(n.id,{x:48+(i%3)*420,y:72+canonReserve+Math.floor(i/3)*rowPitch}));
      layoutBands.push({text:'Записи · основной R не задан',x:48,y:50});
      graphWidth=Math.max(360,...[...positions.values()].map(p=>p.x+262));
      graphHeight=Math.max(180,...[...positions.values()].map(p=>p.y+112));applyLayoutPositions();return;
    }
    // "Связи и контекст" adds relation layers, but must not turn on hidden alternatives.
    const hidden=new Set(graph.nodes.filter(n=>n.kind==='option'&&!optionVisible(n.id)).map(n=>n.id));
    let changed=true;
    while(changed){changed=false;for(const e of graph.edges){
      if(e.type==='OUTCOME_OF'&&e.archived!==true&&hidden.has(e.from)&&!hidden.has(e.to)&&
         !graph.edges.some(x=>x.type==='INTRODUCES'&&x.to===e.to&&x.archived!==true)){
        hidden.add(e.to);changed=true;
      }
    }}
    const visible=showAuxiliaryEdges?new Set(graph.nodes.filter(n=>!hidden.has(n.id)).map(n=>n.id)):
      new Set([...main].filter(id=>!hidden.has(id)));
    const core=new Set([...main,...coreEdges.flatMap(e=>[e.from,e.to])].filter(id=>visible.has(id)));
    const unseen=new Set(core),components=[];
    for(const first of [rootId,...core]){
      if(!unseen.has(first))continue;
      const members=[],todo=[first];unseen.delete(first);
      for(let i=0;i<todo.length;i++){
        const id=todo[i];members.push(id);
        for(const next of adjacent.get(id)||[])if(unseen.delete(next))todo.push(next);
      }
      components.push(members);
    }
    let nextY=72;
    // Rank only the actual R-D spine. Auxiliary records never become root peers
    // merely because a particular relationship is absent from the rank graph.
    const arrange=(ids,relations,caption)=>{
      if(!ids.length)return;
      const set=new Set(ids),out=new Map(ids.map(id=>[id,[]])),inc=new Map(ids.map(id=>[id,0]));
      const links=relations.filter(e=>set.has(e.from)&&set.has(e.to)&&e.from!==e.to);
      for(const e of links){out.get(e.from).push(e.to);inc.set(e.to,inc.get(e.to)+1);}
      const depth=new Map(),todo=ids.filter(id=>!inc.get(id));
      for(const id of todo)depth.set(id,0);
      for(let i=0;i<todo.length;i++)for(const id of out.get(todo[i])){
        depth.set(id,Math.max(depth.get(id)||0,(depth.get(todo[i])||0)+1));
        inc.set(id,inc.get(id)-1);if(!inc.get(id))todo.push(id);
      }
      // Cyclic reference/review links are displayed, without a fictitious rank.
      for(const id of ids)if(!depth.has(id))depth.set(id,0);
      const columns=new Map();
      for(const id of ids){const d=depth.get(id);if(!columns.has(d))columns.set(d,[]);columns.get(d).push(id);}
      const ranks=[...columns.keys()].sort((a,b)=>a-b);
      for(const xs of columns.values())xs.sort((a,b)=>order.get(a)-order.get(b));
      // Barycentric ordering reduces branch crossings; IDs are identity, not order.
      for(let pass=0;pass<4;pass++){
        const traversal=pass%2?[...ranks].reverse():ranks;
        const slot=new Map();for(const xs of columns.values())xs.forEach((id,i)=>slot.set(id,i));
        for(const rank of traversal){
          const xs=columns.get(rank),score=id=>{
            const ns=links.filter(e=>pass%2?e.from===id:e.to===id).map(e=>pass%2?e.to:e.from);
            return ns.length?ns.reduce((sum,n)=>sum+slot.get(n),0)/ns.length:slot.get(id);
          };
          const scores=new Map(xs.map(id=>[id,score(id)]));
          xs.sort((a,b)=>scores.get(a)-scores.get(b)||order.get(a)-order.get(b));
          xs.forEach((id,i)=>slot.set(id,i));
        }
      }
      const rows=Math.max(...[...columns.values()].map(xs=>xs.length));
      layoutBands.push({text:caption,x:48,y:nextY-22});
      for(const [rank,xs] of columns){
        const shift=(rows-xs.length)*rowPitch/2;
        xs.forEach((id,i)=>positions.set(id,{x:48+rank*420,y:nextY+canonReserve+shift+i*rowPitch}));
      }
      nextY+=rows*rowPitch+68;
    };
    components.forEach((ids,i)=>arrange(ids,coreEdges,i===0?'Основной R → конкретный ответ D → под-R':'Связанная цепочка R → D'));
    if(showAuxiliaryEdges){
      const extras=layoutNodes.filter(n=>visible.has(n.id)&&!core.has(n.id));
      const groups=[['grounds','Основания и контекст'],['ready','Готовые варианты и применения'],['review','Вопросы и пересмотр'],['other','Другие записи']];
      const category=n=>n.kind==='context'||n.kind==='decision'?'grounds':
        ['variant','application','target_module'].includes(n.kind)||n.templateRole||
        graph.edges.some(e=>e.archived!==true&&edgeMeta(e.type).group==='ready'&&(e.from===n.id||e.to===n.id))?'ready':
        ['question','proposal','problem','risk'].includes(n.kind)?'review':'other';
      for(const [key,caption]of groups){
        const ids=extras.filter(n=>category(n)===key).map(n=>n.id);
        let links=graph.edges.filter(e=>e.archived!==true&&edgeMeta(e.type).group!=='review');
        if(!links.some(e=>ids.includes(e.from)&&ids.includes(e.to))){
          // Independent records fill a compact grid instead of one tall column.
          if(!ids.length)continue;
          layoutBands.push({text:caption,x:48,y:nextY-22});
          ids.forEach((id,i)=>positions.set(id,{x:48+(i%3)*420,y:nextY+canonReserve+Math.floor(i/3)*rowPitch}));
          nextY+=Math.ceil(ids.length/3)*rowPitch+68;
        }else arrange(ids,links,caption);
      }
    }
    applyLayoutPositions();
    graphWidth=Math.max(360,...[...positions.values()].map(p=>p.x+262));
    graphHeight=Math.max(180,...[...positions.values()].map(p=>p.y+112));
  }
  function centerNode(id){
    const p=positions.get(id);
    if(!p)return;
    view.x=(svg.clientWidth||800)/2-(p.x+111)*view.scale;
    view.y=(svg.clientHeight||500)/2-(p.y+36)*view.scale;
    transform();
  }
  let textFitScale=null;
  function transform() {
    const scene=el('scene');
    if(scene)scene.setAttribute('transform','translate('+view.x+' '+view.y+') scale('+view.scale+')');
    // Chromium's hinted SVG font metrics can change at overview zoom levels.
    if(textFitScale!==view.scale){textFitScale=view.scale;fitVisibleNodeText();}
  }
  function fit(readable=true) {
    if(!graph)return;
    const w=svg.clientWidth||800,h=svg.clientHeight||500,points=[...positions.values()];
    if(!points.length)return;
    const bounds=renderBounds||{minX:Math.min(...points.map(p=>p.x)),minY:Math.min(...points.map(p=>p.y)),maxX:Math.max(...points.map(p=>p.x+222)),maxY:Math.max(...points.map(p=>p.y+72))};
    const minX=bounds.minX-20,minY=bounds.minY-30;
    const width=bounds.maxX+20-minX,height=bounds.maxY+20-minY;
    const fitted=Math.min(1.1,(w-30)/width,(h-30)/height);
    const minimum=.82;
    view.scale=readable===false?Math.max(.07,fitted):Math.max(minimum,fitted);
    view.x=width*view.scale>w-29?16-minX*view.scale:(w-width*view.scale)/2-minX*view.scale;
    const goal=positions.get(graphRoot(graph)?.id);
    view.y=height*view.scale>h-29&&goal?h/2-(goal.y+36)*view.scale:(h-height*view.scale)/2-minY*view.scale;
    transform();
  }
  function render() {
    positionCanonAttachments();
    svg.replaceChildren();
    const defs=make('defs',svg),marker=make('marker',defs,
      {id:'rdg-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto'});
    make('path',marker,{d:'M0,0 L10,5 L0,10 z',fill:'#92a9bb'});
    const scene=make('g',svg,{id:'scene'}),edges=make('g',scene);
    const leaderLayer=make('g',scene,{id:'edge-label-leaders','pointer-events':'none'});
    const nodes=make('g',scene);
    const labels=make('g',scene,{id:'edge-labels'});
    const visibleNodes=graph.nodes.filter(n=>positions.has(n.id));
    graphWidth=Math.max(360,...[...positions.values()].map(p=>p.x+262));
    graphHeight=Math.max(180,...[...positions.values()].map(p=>p.y+112));
    for(const band of layoutBands)make('text',scene,{x:band.x,y:band.y,fill:'#b8cfe0','font-size':14,'font-weight':600,'data-layout-band':band.text},band.text);
    const occupied=visibleNodes.map(n=>{
      const p=positions.get(n.id);return {x:p.x,y:p.y,w:222,h:72};
    });
    const nodeBoxes=visibleNodes.map(n=>({...positions.get(n.id),w:222,h:72,id:n.id}));
    renderStateCard(scene,occupied,nodeBoxes);
    const routes=[];
    const clean=points=>points.filter((p,i)=>!i||p[0]!==points[i-1][0]||p[1]!==points[i-1][1])
      .filter((p,i,xs)=>!i||i===xs.length-1||!((xs[i-1][0]===p[0]&&p[0]===xs[i+1][0])||(xs[i-1][1]===p[1]&&p[1]===xs[i+1][1])));
    const hitsNode=(points,source,target)=>points.some((p,i)=>i&&nodeBoxes.some(r=>{
      // Only the first/last port stem may touch its own endpoint rectangle.
      if(i===1&&r.id===source||i===points.length-1&&r.id===target)return false;
      const a=points[i-1],pad=8;
      return a[0]===p[0]?a[0]>r.x-pad&&a[0]<r.x+r.w+pad&&Math.max(a[1],p[1])>r.y-pad&&Math.min(a[1],p[1])<r.y+r.h+pad:
        a[1]>r.y-pad&&a[1]<r.y+r.h+pad&&Math.max(a[0],p[0])>r.x-pad&&Math.min(a[0],p[0])<r.x+r.w+pad;
    }));
    const visibleEdges=graph.edges.filter(edgeIsVisible).sort((a,b)=>(edgeMeta(a.type).group==='core'?0:1)-(edgeMeta(b.type).group==='core'?0:1));
    const route=(e,index)=>{
      const a=positions.get(e.from),b=positions.get(e.to),forward=b.x>a.x,same=b.x===a.x;
      if(e.type==='VIEW_CANON'){
        const points=[[a.x+111,a.y],[b.x+111,b.y+72]];routes.push(points);return points;
      }
      const outgoing=visibleEdges.filter(x=>x.type!=='VIEW_CANON'&&x.from===e.from),
        incoming=visibleEdges.filter(x=>x.type!=='VIEW_CANON'&&x.to===e.to);
      const sy=a.y+12+48*(outgoing.indexOf(e)+1)/(outgoing.length+1);
      let ty=b.y+12+48*(incoming.indexOf(e)+1)/(incoming.length+1);if(e.from===e.to)ty=a.y+60;
      const start=[a.x+(forward||same?222:0),sy],end=[b.x+(forward?0:222),ty];
      const stub=[start[0]+(forward||same?18:-18),sy],tail=[end[0]+(forward?-18:18),ty];
      const candidates=[],track=(index%12)*12;
      const xs=[(stub[0]+tail[0])/2+track,same?Math.max(stub[0],tail[0])+38+track:(stub[0]+tail[0])/2,...nodeBoxes.flatMap(r=>[r.x-28-track,r.x+r.w+28+track])];
      for(const x of xs)candidates.push([start,stub,[x,sy],[x,ty],tail,end]);
      const ys=[(sy+ty)/2,Math.min(sy,ty)-36-track,Math.max(sy,ty)+36+track,...nodeBoxes.flatMap(r=>[r.y-28-track,r.y+r.h+28+track])];
      for(const y of ys)candidates.push([start,stub,[stub[0],y],[tail[0],y],tail,end]);
      const overlap=points=>{
        let penalty=0;
        for(let i=1;i<points.length;i++)for(const old of routes)for(let j=1;j<old.length;j++){
          const a=points[i-1],b=points[i],c=old[j-1],d=old[j];
          if(a[0]===b[0]&&c[0]===d[0]&&a[0]===c[0])penalty+=Math.max(0,Math.min(Math.max(a[1],b[1]),Math.max(c[1],d[1]))-Math.max(Math.min(a[1],b[1]),Math.min(c[1],d[1])))*2;
          if(a[1]===b[1]&&c[1]===d[1]&&a[1]===c[1])penalty+=Math.max(0,Math.min(Math.max(a[0],b[0]),Math.max(c[0],d[0]))-Math.max(Math.min(a[0],b[0]),Math.min(c[0],d[0])))*2;
        }
        return penalty;
      };
      const cost=points=>points.reduce((sum,p,i)=>sum+(i?Math.abs(p[0]-points[i-1][0])+Math.abs(p[1]-points[i-1][1]):0),0)+points.length*12+overlap(points);
      const valid=candidates.map(clean).filter(ps=>!hitsNode(ps,e.from,e.to));
      valid.sort((x,y)=>cost(x)-cost(y));
      const top=Math.min(...nodeBoxes.map(r=>r.y))-40-track;
      const points=valid[0]||clean([start,stub,[stub[0],top],[tail[0],top],tail,end]);
      routes.push(points);return points;
    };
    // Orthogonal routes use separate endpoint ports and avoid other node boxes.
    const routedEdges=visibleEdges.map((e,index)=>({e,points:route(e,index)}));
    const labelBoxes=[];
    for(const {e,points} of routedEdges){
      const meta=edgeMeta(e.type);
      const path=points.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ');
      const visual=make('path',edges,{d:path,class:'edge g-'+meta.group+(e.type==='VIEW_CANON'?' canon-attachment':'')+
        (selectedEdge===e.id?' selected':selectedEdge?' dim':''),'data-edge-id':e.id,...(fullMode&&e.relation?{'data-requirement':e.relation.requirementId,'data-relation-kind':e.relation.relationKind,'data-branch-state':e.branchState}:{}),
        ...(e.type==='VIEW_CANON'?{}:{'marker-end':'url(#rdg-arrow)'})});
      make('title',visual,{},e.type+' — '+meta.label+(e.meaning?'\n'+e.meaning:''));
      if(e.type==='VIEW_CANON'){
        visual.setAttribute('tabindex','0');visual.setAttribute('role','button');
        visual.setAttribute('aria-label','Канон принадлежит способу '+(graph.nodes.find(n=>n.id===e.from)?.title||e.from));
        visual.addEventListener('click',event=>{event.stopPropagation();chooseEdge(e.id);});
        visual.addEventListener('keydown',event=>{
          if(event.key==='Enter'||event.key===' '){event.preventDefault();chooseEdge(e.id);}
        });
        continue;
      }
      const words=edgeLabel(e),lines=[];
      for(const word of words.split(' ').flatMap(w=>w.match(/.{1,24}/gu)||[])){
        if(!lines.length||lines.at(-1).length+word.length>24)lines.push(word);
        else lines[lines.length-1]+=' '+word;
      }
      if(lines.length>3){lines.splice(3);lines[2]=lines[2].slice(0,22)+'…';}
      const width=Math.max(76,Math.max(...lines.map(l=>l.length))*6.5+20),height=lines.length*14+10;
      const target=nodeBoxes.find(n=>n.id===e.to),last=points.at(-1),anchor={x:last[0],y:last[1]};
      const box=viewGeometry.placeTargetLabel({target,endpoint:anchor,width,height,nodeBoxes,labels:labelBoxes,
        otherRoutes:routedEdges.filter(r=>r.e!==e).map(r=>r.points)});
      labelBoxes.push(box);occupied.push(box);
      const mx=box.x+width/2,my=box.y+height/2;
      const near={x:clamp(anchor.x,box.x,box.x+box.w),y:clamp(anchor.y,box.y,box.y+box.h)};
      make('path',leaderLayer,{d:'M'+anchor.x+','+anchor.y+' L'+near.x+','+near.y,
        fill:'none',stroke:'#617f96','stroke-width':1,'stroke-dasharray':'3 3','data-label-leader':e.id});
      graphWidth=Math.max(graphWidth,box.x+box.w+40);
      graphHeight=Math.max(graphHeight,box.y+box.h+40);
      const group=make('g',labels,{class:'edge-label g-'+meta.group+
        (selectedEdge===e.id?' selected':selectedEdge?' dim':''),'data-edge-id':e.id,
        transform:'translate('+mx+' '+my+')',...(fullMode&&e.relation?{'data-requirement':e.relation.requirementId,'data-relation-kind':e.relation.relationKind,'data-branch-state':e.branchState}:{}),tabindex:0,role:'button',
        'aria-label':e.type+' — '+words,'data-label-target':e.to,'data-label-crowded':String(box.crowded)});
      make('rect',group,{x:-width/2,y:-height/2,width:width,height});
      lines.forEach((line,i)=>make('text',group,{'text-anchor':'middle',y:-height/2+15+i*14},line));
      make('title',group,{},e.type+' — '+words+
        '\n'+meta.detail+(e.meaning?'\nВ примере: '+e.meaning:''));
      const inspect=event=>{event.stopPropagation();chooseEdge(e.id);};
      group.addEventListener('click',inspect);
      group.addEventListener('keydown',event=>{
        if(event.key==='Enter'||event.key===' '){event.preventDefault();inspect(event);}
      });
      visual.addEventListener('click',inspect);
    }
    for(const n of visibleNodes){
      const nextLevel=n.kind==='requirement'?childLevelForRequirement(n.id):null;
      const requirementGraph=fullMode&&n.kind==='requirement';
      const p=positions.get(n.id),g=make('g',nodes,
        {class:'node '+n.kind+(requirementGraph?' requirement-graph':'')+(enteringNodes.has(n.id)?' appearing':'')+(n.id===graphRoot(graph)?.id?' root':'')+(nextLevel?' drill':''),transform:'translate('+p.x+' '+p.y+')','data-id':n.id,
          'data-view-role':requirementGraph?'requirement-graph':n.kind,
          ...(fullMode?{'data-graph':n.sourceGraphSlug||n.graphSlug,'data-branch-state':n.branchState}:{} )});
      if(n.kind==='canon')g.setAttribute('data-canon-for',n.canonForId);
      make('rect',g,{width:222,height:72});
      // Nested outline is a visual GRAPH card, not a new underlying node kind.
      if(requirementGraph)make('rect',g,{x:4,y:4,width:214,height:64,class:'requirement-graph-outline',rx:7,
        'pointer-events':'none'});
      const teachingExample=graphs.find(item=>item.slug===activeSlug)?.group==='examples';
      const canon=['option','action'].includes(n.kind)&&n.canonBlock;
      const canonBadge=canon?' · канон +'+(canon.recommended||[]).length+
        '/−'+(canon.contraindicated||[]).length:'';
      const readableKind={graph:'Граф',requirement:'Требование / цель',decision:'Способ / решение',action:'Action / способ',context:'Условие',canon:'Блок канона (вид)',question:'Вопрос',proposal:'Предложение',variant:'Готовый вариант',application:'Применение',collection:'Группа'};
      const kindText=make('text',g,{x:10,y:20,'font-weight':'bold',class:'node-kind'},
        fullMode?(n.kind==='canon'?'КАНОН (+'+(n.canonBlock?.recommended||[]).length+'/−'+(n.canonBlock?.contraindicated||[]).length+')':n.kind==='requirement'?(n.id===graphRoot(graph)?.id?'ГРАФ R · корень':
          n.branchState==='potential'?'ГРАФ R · возможный':'ГРАФ R · текущий'):
          n.kind==='option'?'Option · вариант':n.kind==='decision'?'Decision · ответ':n.kind==='action'?'Action · '+n.status:n.id):
        n.kind==='graph'?graphBranchCaption(n):
        n.kind==='canon'?'КАНОН (+'+(n.canonBlock?.recommended||[]).length+'/−'+(n.canonBlock?.contraindicated||[]).length+')':
        n.kind==='collection'?'Группа '+(n.expanded?'▾':'▸'):
        canon?'Вариант · канон':
        teachingExample?(readableKind[n.kind]||'Запись графа'):
        n.kind==='requirement'?'R · '+n.id:n.id);
      make('title',g,{},n.title+'\n'+(requirementGraph?
        'ГРАФ ЭТОЙ REQUIREMENT: нажмите, чтобы открыть локальный граф одной волны. Не обязательно отдельный сохранённый файл.\n':
        !fullMode&&n.kind==='requirement'?'REQ: конкретный блок цели внутри локального графа. Нажмите дочернюю R для перехода в её граф.\n':'')+
        (n.kind==='collection'?'Группа, '+n.memberCount+' R. Нажмите, чтобы '+(n.expanded?'свернуть':'раскрыть')+'.\n':'')+'ID: '+n.id+canonBadge);
      if(n.kind==='canon'){
        const preview=(cases,sign)=>{
          const first=String(cases?.[0]?.text||'нет записей');
          const limit=cases?.length>1?12:24;
          return sign+first.slice(0,limit)+(first.length>limit?'…':'')+
            (cases?.length>1?' (ещё '+(cases.length-1)+')':'');
        };
        fitText(make('text',g,{x:10,y:40}),preview(n.canonBlock?.recommended,'+ '));
        fitText(make('text',g,{x:10,y:56}),preview(n.canonBlock?.contraindicated,'− '));
        make('title',g,{},'Канон '+n.canonForId+' (ID и адреса проверки — по клику)');
      }else nodeTitle(g,n.title);
      // Summary badges never change source statuses; no badge means no recorded QRPE.
      const qrpe=n.qrpe||[],open=qrpe.filter(q=>!['resolved','closed','invalidated'].includes(q.status)).length;
      const badge=open?'QRPE !'+open:qrpe.length?'QRPE ✓'+qrpe.length:
        n.kind==='collection'?(n.candidateMemberCount?'Канд. '+n.candidateMemberCount:'R: '+n.memberCount):
        n.kind==='decision'&&!n.selectedOptionId?'Прямое D':
        n.kind==='requirement'&&n.compositeOf?'Композит':'';
      fitText(kindText,kindText.textContent,badge?130:nextLevel?178:202);
      if(badge){
        make('rect',g,{x:147,y:2,width:73,height:21,class:open?'qrpe-badge':'guide-badge',rx:5});
        fitText(make('text',g,{x:151,y:17,class:open?'qrpe-badge-label':'guide-badge-label'}),badge,65);
        make('title',g,{},open?'Нерешённые вопросы QRPE: '+open:
          qrpe.length?'Записано QRPE: '+qrpe.length:
          n.compositeOf?'Композитное R':'Прямое D: отдельный вариант/канон не показан.');
      }
      if(nextLevel)make('text',g,{x:196,y:20,'font-size':17},'↗');
      g.style.cursor=nextLevel?'zoom-in':'pointer';
      g.setAttribute('tabindex','0');
      g.setAttribute('role','button');
      g.setAttribute('aria-label',n.title+(requirementGraph?' · Граф Requirement, открыть локальный граф этой цели':
        !fullMode&&n.kind==='requirement'?' · блок Requirement локального графа':
        fullMode?' · '+graphBranchCaption(n):'')+(canon?' · канон':'')+
        (n.kind==='collection'?' · '+(n.expanded?'свернуть':'раскрыть'):''));
      if(n.kind==='collection')g.setAttribute('aria-expanded',String(n.expanded));
      g.addEventListener('click',e=>{e.stopPropagation();
        if(Date.now()<suppressNodeClickUntil)return;
        if(fullMode){if(stateMode){showStateFields(n.sourceGraphSlug);return;}if(n.kind!=='requirement'){choose(n.id);return;}void openFullRequirement(n).catch(error=>message(error.message));return;}
        if(n.kind==='collection'){toggleCollection(n.collectionId);return;}
        choose(n.id,false);
        if(nextLevel)openChildLevel(nextLevel);
        else choose(n.id);
      });
      if(!nextLevel)g.addEventListener('keydown',e=>{
        if(fullMode&&(e.key==='Enter'||e.key===' ')){e.preventDefault();if(stateMode){showStateFields(n.sourceGraphSlug);return;}if(n.kind!=='requirement'){choose(n.id);return;}void openFullRequirement(n).catch(error=>message(error.message));return;}
        if(e.key==='Enter'||e.key===' '){e.preventDefault();if(n.kind==='collection')toggleCollection(n.collectionId);else choose(n.id);}
      });
      if(nextLevel)g.addEventListener('keydown',e=>{
        if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(n.id,false);openChildLevel(nextLevel);}
      });
    }
    const routePoints=routes.flat();
    renderBounds=occupied.length?{
      minX:Math.min(...occupied.map(b=>b.x),...routePoints.map(p=>p[0])),
      minY:Math.min(...occupied.map(b=>b.y),...routePoints.map(p=>p[1])),
      maxX:Math.max(...occupied.map(b=>b.x+b.w),...routePoints.map(p=>p[0])),
      maxY:Math.max(...occupied.map(b=>b.y+b.h),...routePoints.map(p=>p[1]))}:null;
    enteringNodes.clear();textFitScale=null;
    transform();choose(selected&&graph.nodes.some(n=>n.id===selected)?selected:null,false);
  }
  function chooseEdge(id){
    if(fullMode&&graph.edges.find(e=>e.id===id)?.type!=='VIEW_CANON'){
      const edge=graph.edges.find(e=>e.id===id);if(!edge)return;
      selected=null;selectedEdge=id;render();setInspector(true);
      const r=edge.relation;
      const describeEnd=id=>{
        const n=sourceGraph.nodes.find(node=>node.id===id);
        return (n?.kind==='decision'?'Decision ':n?.kind==='action'?'Action ':n?.kind==='option'?'Option ':'Requirement ')+
          (n?.id?.startsWith('__cause__')?n.id.split('::').slice(1).join('::'):n?.id||id);
      };
      info.textContent=(r.relationKind==='refinement'?'Содержательное уточнение Requirement: ':'Связь: ')+
        describeEnd(edge.from)+' → '+describeEnd(edge.to)+'\n'+
        'Тип: '+edge.type+' · '+r.relationKind+'\n'+
        'Статус пути: '+(edge.branchState==='alternative'?'ПОТЕНЦИАЛЬНО, НЕ ПРИНЯТО':'ДОСТУПЕН ПО ТЕКУЩЕМУ ПУТИ')+'\n'+
        (r.childRole?'Роль дочерней R: '+(r.childRole==='subgoal'?'подцель разбиения':'корректность выполнения Action')+'\n':'')+
        'Основание: '+(r.relationKind==='refinement'?'DERIVES — уточнение R, НЕ выбранная дочерняя R':r.introducedByActionId?'Action '+r.introducedByActionId:r.introducedByDecisionId?'Decision '+r.introducedByDecisionId:r.originatingOptionId?'Option '+r.originatingOptionId:'прямая связь из source')+
        '\nИсточник записи: '+r.sourceGraphSlug+(sourceGraph.exampleOnly?'\nУчебный выбор не принят в основном проекте.':'')+'\nПросмотр не принимает решения.';
      return;
    }
    const e=graph?.edges.find(x=>x.id===id);
    if(!e)return;
    if(!edgeIsVisible(e)){showAuxiliaryEdges=true;layout();renderEdgeLegend();}
    setInspector(true);
    selected=null;selectedEdge=id;
    render();
    const meta=edgeMeta(e.type);
    const from=graph.nodes.find(n=>n.id===e.from),to=graph.nodes.find(n=>n.id===e.to);
    info.textContent='Отношение: '+edgeLabel(e)+' ('+e.type+')'+
      '\n\n'+e.from+' → '+e.to+
      '\n\nКак читать: «'+(from?.title||e.from)+'» → '+meta.label+' → «'+(to?.title||e.to)+'»'+
      '\n\nИсточник: '+(from?.title||e.from)+
      '\nПолучатель: '+(to?.title||e.to)+
      '\n\nСмысл: '+meta.detail+
      (e.meaning?'\n\nКонкретно в этом примере: '+e.meaning:'')+
      (e.parent?'\n\nРодительский Requirement: '+e.parent:'')+
      '\n\nНаличие связи не подтверждает выполнение R или реализацию D.'+
      (graph.exampleOnly?'\n\nЭто read-only учебная проекция; не каждый тип связи поддержан writer.':'');
  }
  function recordSourceFor(local){
    if(typeof graph.identitySpace!=='string'||!graph.identitySpace.trim())return null;
    let node=local,ownerGraph=graph,slug=activeSlug;const seen=new Set();
    while(node?.projectionOf){
      const ref=node.projectionOf,key=ref.graphSlug+'|'+ref.nodeId;
      if(seen.has(key)||ref.nodeId!==local.id)return null;seen.add(key);
      const item=graphs.find(item=>item.slug===ref.graphSlug);
      if(!item?.graph||item.graph.identitySpace!==graph.identitySpace)return null;
      const next=item.graph.nodes.find(n=>n.id===ref.nodeId&&n.kind===local.kind);
      if(!next)return null;
      node=next;ownerGraph=item.graph;slug=item.slug;
    }
    return node===local?null:{node,graph:ownerGraph,slug};
  }
  // Canon cases are search directions, not evidence that a fact is proven.
  function canonCasesText(cases,checks=[]) {
    const ref=v=>typeof v==='string'?v:
      v&&typeof v==='object'?((v.graphSlug||'текущий граф')+' / '+(v.collectionId||v.id||'?')):String(v);
    if(!cases?.length)return '— случаи не записаны';
    return cases.map(c=>{
      const notes=[];
      if(c.checkRequirements?.length)notes.push('  Проверить R: '+c.checkRequirements.map(ref).join(', '));
      if(c.checkCollections?.length)notes.push('  Проверить Collections: '+c.checkCollections.map(ref).join(', '));
      if(c.checkCategories?.length)notes.push('  Категории поиска (не доказано): '+c.checkCategories.map(ref).join(', '));
      for(const key of ['sourceRef','evidence','source','provenance']){
        if(c[key])notes.push('  '+key+': '+(typeof c[key]==='string'?c[key]:JSON.stringify(c[key])));
      }
      const recorded=(checks||[]).filter(x=>x.canonCaseId===c.id);
      if(recorded.length)notes.push('  Записанные оценки: '+recorded.map(x=>
        (x.requirementId||x.contextRef||'источник не указан')+' · '+x.state+
        (x.impact?' · '+x.impact:'')+(x.knownAt?' · известно '+x.knownAt:'')).join('; '));
      else notes.push('  Применимость в этом контексте: не подтверждена, проверки случая не записаны.');
      return '- ['+(c.id||'без ID')+'] '+c.text+'\n'+notes.join('\n');
    }).join('\n');
  }
  function appendCanonMaterial(n){
    const material=n?.canonBlock;if(!material)return;
    const p=document.createElement('p');p.textContent='Материал канона: '+(material.preparation==='link-only'?'пока только ссылка · список полей неполон':material.interpretation||'интерпретация отдельно не записана');info.appendChild(p);
    const items=new Map([...stateSources,...graphs.filter(i=>i.graph)].map(i=>[i.slug,i]));if(sourceGraph)items.set(sourceGraph.id,{graph:sourceGraph});
    appendSources(info,(material.sourceRefs||[]).map(r=>items.get(r.graphSlug)?.graph.knowledgeSources?.find(x=>x.id===r.sourceId)||r));
  }
  // Read-only full projection: inspect the original kind and semantic ID.
  // Display aliases (__cause__) never turn Options/Decisions into Requirements.
  function fullRecordDetails(n){
    if(n.kind==='canon')return 'Канон '+n.canonForId+'\n'+n.title+
      '\nВладелец: '+n.sourceGraphSlug+
      '\nБлок материала способа; не дочерняя R.\nКанонические ситуации (+):\n'+
      canonCasesText(n.canonBlock?.recommended,n.contextChecks)+
      '\nКанонические ситуации (−):\n'+canonCasesText(n.canonBlock?.contraindicated,n.contextChecks);
    const owner=catalogModel?.graphs.find(item=>item.slug===n.sourceGraphSlug)?.graph;
    const kind=({requirement:'Requirement',decision:'Decision',option:'Option',action:'Action'})[n.kind]||n.kind;
    const id=n.id.startsWith('__cause__')?n.id.split('::').slice(1).join('::'):n.id;
    const completionHistory=(owner?.events||[]).filter(e=>e.targetId===id&&['action_executed','requirement_achieved'].includes(e.type));
    const state=n.kind==='action'&&n.status==='superseded'?
      'Исторический Action · выбор пересмотрен, не действует на текущем пути':
      n.kind==='requirement'?graphBranchCaption(n):
      n.branchState==='potential'?'Вариант / решение пока не принято на текущем пути':
      'Доступно на текущем пути (не равно выполнению)';
    const selected=n.kind==='decision'&&n.selectedOptionId?
      owner?.nodes.find(o=>o.kind==='option'&&o.id===n.selectedOptionId):null;
    const cases=(block,checks)=>block?'\nКанонические ситуации (+):\n'+canonCasesText(block.recommended,checks)+
      '\nКанонические ситуации (−):\n'+canonCasesText(block.contraindicated,checks):'';
    const qrpe=(n.qrpe||[]).map(q=>q.id+' ['+q.status+'] '+q.text+
      (q.recordedAt?' · записано '+q.recordedAt:'')+
      (q.statusHistory?.length?' · История: '+q.statusHistory.map(t=>t.status+' ('+t.recordedAt+')').join(' → '):'')).join('\n');
    return id+' · '+kind+(n.status?' · '+n.status:'')+'\n'+n.title+'\n'+state+
      (n.kind==='requirement'?'\nЭто обзорный блок ГРАФА Requirements. Нажатие открывает локальный граф одной волны для этой R; отдельного файла у каждой R может не быть. Это НЕ выполненная цель.':'')+
      '\nВладелец: '+n.sourceGraphSlug+
      (owner?.exampleOnly?'\nУЧЕБНЫЙ пример, не принят в основном проекте.':'')+
      (n.kind==='option'?'\nПроисхождение: '+({prepared:'готовый',situational:'ситуативный',adapted:'адаптированный'}[n.origin]||n.origin||'не указано')+
        (n.preparedSource?'\nПодготовленный источник: '+JSON.stringify(n.preparedSource):''):'')+
      (n.kind==='decision'?'\nВыбранный вариант: '+(n.selectedOptionId||'не указан')+
        (selected?' · '+selected.title:''):'')+
      (n.kind==='action'?'\nAction: '+(n.status==='selected'?(completionHistory.length?'выбран; запись выполнения — в истории':'выбран, не доказано исполнение'):n.status==='superseded'?'исторически выбран, затем пересмотрен':'не выбран')+
        '\nВыбор и достижение Requirement — разные факты.':'')+
      (n.kind==='action'&&n.reconsiderationEventId?
        '\nПересмотр: '+n.reconsiderationEventId+' · Action '+(n.reconsideredByActionId||'?')+
        '\nПричина: '+(owner?.events?.find(e=>e.id===n.reconsiderationEventId)?.note||'не указана'):'')+
      (n.description?'\n'+n.description:'')+
      cases(n.canonBlock,n.contextChecks)+
      (selected?.canonBlock?'\nКанон выбранного варианта '+selected.title+cases(selected.canonBlock,selected.contextChecks):'')+
      (n.compositeOf?'\nУточняет: '+n.compositeOf:'')+
      (n.history?.length?'\nИстория R:\n'+n.history.map(h=>h.id+' · '+h.statement+' · записано '+h.recordedAt+
        (h.knownAt?' · известно '+h.knownAt:'')+(h.effectiveAt?' · действует '+h.effectiveAt:'')).join('\n'):'')+
      (n.kind==='action'?'\nТип Action: '+(n.actionType==='decomposition'?'выделение подцели / связанного набора подцелей':'общий'):'')+
      (completionHistory.length?'\n\nИстория результатов (в своей сохранённой композиции):\n'+completionHistory.map(e=>e.id+' · '+(e.type==='action_executed'?'выполнен Action':'достигнута R')+' · '+e.note).join('\n'):'')+
      '\n\nQRPE:\n'+(qrpe||'Нет записанных QRPE; это не доказывает отсутствия рисков.')+
      (n.selectionBasis?'\n\nОснование выбора (известно '+(n.selectionBasis.knownAt||'не указано')+'): '+
        (n.selectionBasis.rationale||n.selectionBasis.note||'не указано')+
        (n.selectionBasis.acceptedContraindicationCaseIds?.length?'\nОсознанные противопоказания: '+n.selectionBasis.acceptedContraindicationCaseIds.join(', '):'')+
        (n.selectionBasis.outstandingRiskIssueIds?.length?'\nОткрытые QRPE: '+n.selectionBasis.outstandingRiskIssueIds.join(', '):'')+
        '\nИсторический снимок:\n'+JSON.stringify(n.selectionBasis,null,2):'')+
      (n.source?'\nИсточник: '+n.source:'')+
      '\nПросмотр не принимает D и не изменяет исходные файлы.';
  }
  function lensAdvice(owner,targetId=null){
    // Plain text attached to a prepared or working Graph. This never starts a Lens.
    const notes=Array.isArray(owner?.lensRecommendations)?owner.lensRecommendations:[];
    const relevant=notes.filter(n=>n&&!n.targetId||n?.targetId===targetId);
    return relevant.length?'\n\nРекомендуемые линзы (текст, не применение):\n'+
      relevant.map(n=>'• '+n.lensKey+(n.targetId?' · '+n.targetId:' · весь граф')+': '+n.text).join('\n'):'';
  }
  function choose(id,center=true){
    if(fullMode){
      selected=id;
      for(const node of root.querySelectorAll('.node'))node.classList.toggle('selected',node.getAttribute('data-id')===id);
      const record=graph.nodes.find(n=>n.id===id);
      if(record){
        info.textContent=fullRecordDetails(record)+lensAdvice(sourceGraph,id);
        appendCanonMaterial(record);
        if(center){setInspector(true);centerNode(id);}
      }else{
        info.textContent=graph.title+'\n'+graph.nodes.filter(n=>n.kind==='requirement').length+
          ' Requirements. Корневая R: '+sourceGraph.rootRequirementId+
          '\nФайл-источник не ограничивает полный граф.';
        for(const r of fullGraphData?.projection?.supplementaryViews||[]){
          const button=document.createElement('button');button.textContent='Связанное представление '+r.relationKind+': '+r.toGraphSlug;
          button.onclick=()=>loadGraphSlug(r.toGraphSlug);info.appendChild(button);
        }
      }
      return;
    }
    if(id&&!positions.has(id)){showAuxiliaryEdges=true;layout();render();renderEdgeLegend();}
    if(id && selectedEdge){selectedEdge=null;render();}
    selected=id;
    if(id&&center)setInspector(true);
    for(const node of root.querySelectorAll('.node')){
      const nId=node.getAttribute('data-id'),n=graph.nodes.find(x=>x.id===nId);
      const q=el('search').value.trim().toLowerCase();
      node.classList.toggle('selected',id===nId);
      const focusedEdge=selectedEdge?graph.edges.find(e=>e.id===selectedEdge):null;
      node.classList.toggle('dim',!!focusedEdge&&nId!==focusedEdge.from&&nId!==focusedEdge.to||!!q&&!(n.id+' '+n.title).toLowerCase().includes(q)&&id!==nId);
    }
    if(!id){
      const count=Array.isArray(graph.events)?graph.events.length:0;
      const modernOptions=graph.nodes.filter(n=>['option','action'].includes(n.kind)&&n.canonBlock);
      const archive=graphs.find(x=>x.slug===activeSlug)?.catalogLegacy;
      info.textContent=(graph.title||graph.id||'Граф')+
        (archive?'\nАРХИВНАЯ ПРОЕКЦИЯ: в этом файле нет полной модели canonBlock/QRPE v7. Для современных примеров откройте reference-prepared-planning-tree или reference-mixed-active-work.':
          modernOptions.length?'\nВарианты с блоками канонов: '+modernOptions.length+
          '. Нажмите узел «Вариант · канон» для подробных ситуаций; если D выбран, нажмите «Показать все варианты».':'')+
        '\n\n'+graph.nodes.length+
        ' узлов / '+graph.edges.length+' связей\nПоказано: '+positions.size+' записей'+(showAuxiliaryEdges?' · связи и контекст':' · основная цепочка')+'\nRevision: '+(graph.revision||'?')+'\nМасштаб: '+scaleLabel(graph)+
        (graph.templateOnly?'\nЗаготовка Target Module/Unit · НЕ ПРИНЯТО\nЭто не результат проекта и не применённая модель.':graph.readOnly?'\nЭталон · только чтение':'')+
        (graph.coverage?'\n\nСодержание:\n'+graph.coverage:'')+
        (graph.sourceSections?'\n\nРазделы: '+graph.sourceSections.join(', '):'')+
        (graph.sourceDocument?'\nИсточник: '+graph.sourceDocument:'')+
        (count?'\n\nСобытия ('+count+'):\n'+graph.events.map(e=>
          e.id+' · '+e.type+(e.note?'\n'+e.note:'')).join('\n\n'):'')+
        projectContextSummary()+lensAdvice(sourceGraph||graph,null)+
        (graph.preparedGraphSetReference?.applicabilityStatus==='candidate-unverified'?
          '\n\nПРИМЕНИМОСТЬ: совпадение корневых заголовков — учебное допущение, не подтверждение одной нормативной цели/scope. Исторический T1 не менялся.':'')+
        (sourceUpdateAlerts.some(a=>a.graphSlug===activeSlug)?
          '\n\nИЗМЕНИЛСЯ ПОДГОТОВЛЕННЫЙ ИСТОЧНИК: проверьте исторические pins и применимость перед новым использованием; прежний T1 не обновляется.':'')+
        '\n\nВыберите узел, чтобы увидеть его основания и связи.';
      return;
    }
    const local=graph.nodes.find(x=>x.id===id);
    if(!local) {
      // A previously focused node can become hidden after a different view is
      // loaded. Do not crash or silently pretend that a choice was erased.
      selected=null;
      message('Узел '+id+' сейчас скрыт. Раскройте его коллекцию или варианты.');
      return;
    }
    const record=recordSourceFor(local);
    const n=record?{...local,...record.node,projectionOf:local.projectionOf}:local;
    const related=graph.edges.filter(e=>e.from===id||e.to===id);
    const outgoing=n.kind==='requirement'?outgoingForRequirement(activeSlug,id):[];
    const incoming=n.kind==='requirement'&&id===graph.rootRequirementId?
      incomingToGraph(activeSlug):[];
    const history=((record?.graph||graph).events||[]).filter(e=>e.decisionId===id||e.actionId===id||e.targetId===id);
    const chosenOption=n.kind==='decision'&&n.selectedOptionId?
      (sourceGraph?.nodes||graph.nodes).find(x=>x.id===n.selectedOptionId&&x.kind==='option'):null;
    const canonOption=n.kind==='canon'?
      (sourceGraph?.nodes||graph.nodes).find(x=>x.id===n.canonForId&&x.kind==='option'):null;
    const caseChecks=canonOption?.contextChecks||n.contextChecks||[];
    const chosenCanon=chosenOption?.canonBlock;
    const canonExcerpt=chosenCanon?'\n\nКанон выбранного варианта '+chosenOption.title+
      ' (+):\n'+canonCasesText(chosenCanon.recommended,chosenOption.contextChecks)+
      '\nКанон (−):\n'+canonCasesText(chosenCanon.contraindicated,chosenOption.contextChecks)+
      '\nИсходный вариант доступен через «Показать все варианты».':'';

    info.textContent=n.id+' · '+n.kind+(n.status?' · '+n.status:'')+'\n\n'+n.title+
      (graphs.find(x=>x.slug===activeSlug)?.catalogLegacy?
        '\n\nАРХИВНЫЙ ПРИМЕР: это прежняя иллюстративная схема без полноценного canonBlock/QRPE v7.':'')+
      (n.templateRole?'\n\nРоль заготовки: '+n.templateRole+'\nНе является принятым проектным решением.':'')+
      (n.kind==='action'?'\n\nТип Action: '+(n.actionType==='decomposition'?'выделение подцели / связанного набора подцелей':'общий')+'\nAction: '+(n.status==='selected'?(history.some(e=>e.type==='action_executed')?'выбран; запись выполнения — в истории':'выбран, исполнение не подтверждено'):n.status==='superseded'?'исторически выбран, затем пересмотрен':'не выбран'):'')+
      (n.kind==='option'?'\n\nПроисхождение: '+({prepared:'готовый',situational:'ситуативный',adapted:'адаптированный'}[n.origin]||'не указано')+
       (n.preparedSource?'\nПодготовленный источник: '+JSON.stringify(n.preparedSource):''):'')+
      (n.currentStatement&&n.currentStatement!==n.title?'\n\nТекущая формулировка: '+n.currentStatement:'')+
      (n.description?'\n\n'+n.description:'')+
      (n.id===graph.rootRequirementId&&graph.preparedGraphSetReference?.applicabilityStatus==='candidate-unverified'?
        '\n\nПРИМЕНИМОСТЬ: одинаковые заголовки R0/R-PLAN в учебном примере не подтверждают нормативную эквивалентность или scope. Историческая T1 сохранена.':'')+
      (sourceUpdateAlerts.filter(a=>a.graphSlug===activeSlug&&a.nodeId===id).map(a=>
        '\n\nИсточник требует проверки: '+a.sourceGraphSlug+':'+a.sourceOptionId+
        ', pin '+a.pinnedVersion+', доступна '+(a.availableVersion||'не найдена')+
        '. Это НЕ значит, что исторический T1 использовал новую версию.').join(''))+
      (n.kind==='collection'?'\n\nГРУППИРОВКА, а не R/Unit. Участников: '+n.memberCount+
        ' (кандидатных R: '+n.candidateMemberCount+').'+(n.memberCount===1?
          ' Один R выделен в группу только для показа контекста.':'')+
        ' '+(n.expanded?'Нажмите для сворачивания.':'Нажмите для раскрытия.')+
        ' Состояния исходных R не меняются.':'')+
      (n.kind==='canon'?'\n\nБлок канона варианта '+n.canonForId+' — только отображение одного блока с ситуациями (+/−); не отдельный R или D.':'')+
      (canonExcerpt||'')+
      (n.canonBlock?'\n\nКанонические ситуации (+):\n'+canonCasesText(n.canonBlock.recommended,caseChecks)+
       '\nКанонические ситуации (−):\n'+canonCasesText(n.canonBlock.contraindicated,caseChecks):'')+
      (n.compositeRequirementId?'\n\nКомпозит для оценки этого варианта: '+n.compositeRequirementId:'')+
      (n.contextChecks?.length?'\n\nПроверенные факторы до выбора:\n'+n.contextChecks.map(x=>
        x.canonCaseId+': '+x.requirementId+' · '+x.state+(x.impact?' · '+x.impact:'')).join('\n'):'')+
      (n.kind==='decision'&&n.status==='selected-in-example-only'&&!n.selectedOptionId?
        '\n\nПРЯМОЕ УЧЕБНОЕ D: отдельные option/канон и снимок выбора в этом примере не представлены. Это не доказательство оценки по канонам.':'')+
      (n.compositeOf?'\n\nКомпозит исходной R: '+n.compositeOf+
       '\nВерсии / факторы:\n'+(n.history||[]).map(x=>x.id+' · '+x.recordedAt+' · '+x.statement).join('\n'):'')+
      '\n\nQRPE:\n'+(n.qrpe?.length?n.qrpe.map(x=>'['+x.status+'] '+x.text+
        (x.recordedAt?' (записано '+x.recordedAt+')':'')+
        (x.statusHistory?.length?'\nИстория: '+x.statusHistory.map(t=>t.status+' ('+t.recordedAt+')'+(t.note?': '+t.note:'')).join(' → '):'')).join('\n'):'Нет записанных QRPE. Это НЕ доказывает отсутствие рисков.')+
      (n.implementationStatus?'\n\nРеализация: '+n.implementationStatus:'')+
      (n.goalAchievementStatus?'\nДостижение R: '+n.goalAchievementStatus:'')+
      (n.selectionBasis?'\n\nОснование выбора (срез '+(n.selectionBasis.knownAt||'дата не указана')+
        '):\n'+(n.selectionBasis.rationale||n.selectionBasis.note||'основание не указано')+
        (n.selectionBasis.acceptedContraindicationCaseIds?.length?
          '\nОсознанно принятые противопоказания: '+n.selectionBasis.acceptedContraindicationCaseIds.join(', '):'')+
        (n.selectionBasis.outstandingRiskIssueIds?.length?
          '\nОставленные открытыми QRPE: '+n.selectionBasis.outstandingRiskIssueIds.join(', '):'')+
        '\n\nПолный исторический снимок:\n'+JSON.stringify(n.selectionBasis,null,2):'')+
      (outgoing.length?'\n\n↗ Отдельный граф того же R: '+outgoing.map(r=>r.to+
        ' [R: '+r.requirementId+
        (r.relationKind==='potential'?', планируется вариантом '+r.originatingOptionId+'; D НЕ выбран':
         r.introducedByDecisionId?', введён D '+r.introducedByDecisionId+', статус '+r.relationKind:
         ', отношение '+r.relationKind+', без выбранного D')+']').join(', ')+
        '\nНажмите узел, чтобы перейти.':'')+
      (incoming.length?'\n\nПереход к этой R:\n'+incoming.map(r=>r.from+
        ' [R: '+r.requirementId+
        (r.relationKind==='potential'?', потенциальный путь через O: '+r.originatingOptionId+', НЕ выбран':', D: '+r.introducedByDecisionId)+']').join('\n'):'')+
      (n.preparedModelRef?'\nГотовая модель: '+(typeof n.preparedModelRef==='object'?JSON.stringify(n.preparedModelRef,null,2):n.preparedModelRef):'')+
      (n.repetition?'\nПовторяемость: '+n.repetition.mode+' '+n.repetition.cardinality:'')+
      (n.scope?'\n\nScope: '+n.scope:'')+
       (n.supersededBy?'\nЗаменён ответом: '+n.supersededBy:'')+
      (n.targetModule?'\n\nМесто ответа: '+n.targetModule:'')+
      (n.evidenceStatus?'\nПроверка: '+n.evidenceStatus:'')+
      (n.openQuestion?'\nОткрытый вопрос: '+n.openQuestion:'')+
      (n.source?'\n\nИсточник: '+n.source:'')+
      '\n\nСвязи:\n'+(related.length?related.map(e=>e.from+' —'+e.type+' ('+edgeMeta(e.type).label+')→ '+e.to+
        (e.parent?' (parent '+e.parent+')':'')+(e.meaning?' · '+e.meaning:'')).join('\n'):'нет')+
      (history.length?'\n\n'+((record?.graph||graph).exampleOnly||history.every(e=>e.exampleOnly===true||['example','example-only'].includes(e.by))?'История (иллюстрация)':'История')+':\n'+history.map(e=>
        e.id+' · '+e.type+(e.note?': '+e.note:'')+(e.previousDecisionSnapshot?'\nПрежний ответ: '+JSON.stringify(e.previousDecisionSnapshot,null,2):'')).join('\n'):'')+
      lensAdvice(record?.graph||sourceGraph||graph,id);
    if(n.preparedModelRef && typeof n.preparedModelRef==='object'){
      const ref=n.preparedModelRef,button=document.createElement('button');
      button.textContent='Открыть готовый модуль · '+ref.id;
      button.onclick=async()=>{if(await loadGraphSlug(ref.graphSlug,{reference:true}))focusRecord(ref.methodDecisionId);};
      info.appendChild(button);
    }
    if(n.answerParts)info.textContent+='\n\nЧасти ответа:\n'+n.answerParts.map(p=>p.id+': '+p.text).join('\n');
    if(n.answerBindings)info.textContent+='\n\nНа какие R отвечает:\n'+n.answerBindings.map(b=>b.requirementId+' ← '+b.parts.join(', ')+' · '+b.sufficiency).join('\n');
    if(n.blocking)info.textContent+='\n\nВлияние вопроса: '+n.blocking+(n.blocks?' · '+n.blocks:'')+(n.closesWith?'\nЗакрывается: '+n.closesWith:'');
    if(n.delegations)info.textContent+='\n\nДелегации (не выполнение):\n'+n.delegations.map(d=>d.targetModuleInstance+' · модель '+d.modelRef+' · ответ '+d.answerRef).join('\n');
    const ref=n.projectionOf;
    if(ref && graph.identitySpace && ref.nodeId===n.id && graphs.some(item=>item.slug===ref.graphSlug&&item.graph?.identitySpace===graph.identitySpace)){
      info.textContent+='\n\nИсточник той же записи: '+ref.graphSlug+' · '+ref.nodeId;
      const link=document.createElement('button');
      link.type='button';link.textContent='Открыть источник '+ref.nodeId;
      link.setAttribute('data-record-source',ref.graphSlug);
      link.onclick=async()=>{
        if(await loadGraphSlug(ref.graphSlug,{reference:true}))focusRecord(ref.nodeId);
      };
      info.appendChild(link);
    }
    appendCanonMaterial(n.kind==='canon'?sourceGraph.nodes.find(o=>o.id===n.canonForId):n);
    if(n.kind==='requirement'||n.kind==='action'){
      const current=currentFullGraphEntry()||currentWorkingGraphEntry();
      const available=dependencyCurrent&&current&&dependencyCurrent.sourceGraphs?.includes(current.file);
      const alerts=available?dependencyCurrent.rows.filter(row=>row.nodeId===n.id&&
        (row.graphFile===current.file||dependencyCurrent.sourceGraphs?.includes(row.graphFile))&&row.status!=='valid'):[];
      if(alerts.length)info.textContent+='\n\n⚠ Gendocen: требуется повторная проверка зависимостей ('+alerts.length+'). Это НЕ признание решения неверным.';
      const link=document.createElement('button');link.type='button';
      link.textContent=n.kind==='requirement'?'Зависимости этой Requirement ↗':'Зависимости этого Action ↗';
      link.setAttribute('data-open-dependencies',n.id);
      link.onclick=()=>el('dependency-toggle').click();
      info.appendChild(link);
    }
    if(center)centerNode(id);
  }
  // View-only Collections and canonical situation blocks never persist as
  // Requirements/Decisions/edges. The underlying source JSON is unchanged.
  function localLevelSource(source,id){
    const byId=new Map(source.nodes.map(n=>[n.id,n])),keep=new Set([id]),queue=[id];
    const structural=new Set(['OPTION_FOR','DRIVES','DERIVES','INTRODUCES','OUTCOME_OF','GENERATES_ITEM_ROLE']);
    for(let i=0;i<queue.length;i++){
      const current=queue[i],n=byId.get(current);
      if(n?.kind==='decision'&&n.selectedOptionId&&byId.has(n.selectedOptionId))keep.add(n.selectedOptionId);
      if(n?.kind==='requirement'&&current!==id)continue;
      for(const e of source.edges)if(e.archived!==true&&e.from===current&&structural.has(e.type)&&!keep.has(e.to)){keep.add(e.to);queue.push(e.to);}
      for(const c of source.collections||[])if(c.anchor===current)for(const ref of c.memberRefs)if(!keep.has(ref)){keep.add(ref);queue.push(ref);}
    }
    // Supplementary grounds can be shown for this ONE wave, but may not
    // transitively pull in unrelated Actions or their Requirement graphs via
    // a shared context node. One-hop references from the structural wave are
    // sufficient; they cannot become a second traversal root.
    const wave=new Set(keep);
    for(const e of source.edges){
      if(e.archived===true||structural.has(e.type))continue;
      const other=wave.has(e.from)?e.to:wave.has(e.to)?e.from:null;
      if(other&&byId.has(other))keep.add(other);
    }
    return {...source,rootRequirementId:id,nodes:source.nodes.filter(n=>keep.has(n.id)),
      edges:source.edges.filter(e=>keep.has(e.from)&&keep.has(e.to)),
      collections:(source.collections||[]).filter(c=>keep.has(c.anchor)&&c.memberRefs.every(ref=>keep.has(ref))&&
        (c.anchor===id||byId.get(c.anchor)?.kind!=='requirement'))};
  }
  function displayGraph(source) {
    if(localRootId)source=localLevelSource(source,localRootId);
    const nodes=source.nodes.slice(),edges=source.edges.slice();
    const hidden=new Set(),virtualNodes=[],virtualEdges=[];
    const rootId=graphRoot(source)?.id;
    const bounded=!!rootId;
    const protectedRoot=new Set([rootId,...edges.filter(e=>e.from===rootId&&e.archived!==true&&['OPTION_FOR','DRIVES','DERIVES'].includes(e.type)).map(e=>e.to)]);
    if(bounded){
      // A non-root R is a boundary, including a composite/derived R.
      // Its own answers belong in a separate graph of the same identity.
      for(const e of edges){
        if(e.archived===true||e.from===rootId)continue;
        if(['OPTION_FOR','DRIVES','DERIVES'].includes(e.type)&&!protectedRoot.has(e.to)&&nodes.some(n=>n.id===e.from&&n.kind==='requirement'))hidden.add(e.to);
      }
    }
    for(const col of source.collections||[]){
      const candidateMembers=col.memberRefs.map(ref=>source.nodes.find(n=>n.id===ref));
      if(candidateMembers.some(n=>!n||n.kind!=='requirement'))throw Error('Группа '+col.id+' должна содержать только R');
      const expanded=col.memberRefs.length<=2||expandedCollections.has(col.id);
      const id='__collection__'+col.id;
      if(!expanded){
        const statuses=candidateMembers.filter(n=>n.status==='candidate').length;
        virtualNodes.push({id,kind:'collection',collectionId:col.id,title:col.title,
          memberCount:col.memberRefs.length,candidateMemberCount:statuses,expanded:false});
        virtualEdges.push({id:'__group__'+col.id,type:'VIEW_COLLECTION',from:col.anchor,to:id});
        for(const member of col.memberRefs)hidden.add(member);
      }else for(const member of col.memberRefs){
        const connected=source.edges.some(e=>e.archived!==true&&(e.from===member||e.to===member));
        if(!connected)virtualEdges.push({id:'__groupmember__'+col.id+'__'+member,
          type:'VIEW_COLLECTION',from:col.anchor,to:member});
      }
      // Opening a list reveals its R, never the R's own options/answers.
      for(const e of source.edges)if(e.archived!==true&&col.memberRefs.includes(e.from)&&
        ['OPTION_FOR','DRIVES','DERIVES'].includes(e.type))hidden.add(e.to);
    }
    // While a Collection is folded, do not leak its descendant candidates
    // into All Relations. This does not delete the source records.
    let changed=true;
    while(changed){
      changed=false;
      for(const e of source.edges){
        if(e.archived===true||!hidden.has(e.from)||
           !['OPTION_FOR','OUTCOME_OF','DRIVES','INTRODUCES','DERIVES'].includes(e.type)||hidden.has(e.to)||protectedRoot.has(e.to))continue;
        hidden.add(e.to);changed=true;
      }
    }
    // A selected option is hidden as a candidate; show its actual canon
    // next to selected D instead. Other options retain one block per option.
    const chosen=new Map();
    for(const d of source.nodes.filter(n=>n.kind==='decision'&&
      ['committed','selected-in-example-only'].includes(n.status)&&n.selectedOptionId)){
      const parentEdge=source.edges.find(e=>e.type==='OPTION_FOR'&&e.to===d.selectedOptionId);
      if(parentEdge)chosen.set(parentEdge.from,d);
    }
    for(const option of source.nodes.filter(n=>['option','action'].includes(n.kind)&&n.canonBlock)){
      const parentEdge=source.edges.find(e=>e.type==='OPTION_FOR'&&e.to===option.id)||
        source.edges.find(e=>e.type==='DRIVES'&&e.to===option.id);
      const selected=option.kind==='option'?(parentEdge?chosen.get(parentEdge.from):source.nodes.find(n=>n.kind==='decision'&&['committed','selected-in-example-only'].includes(n.status)&&n.selectedOptionId===option.id)):null;
      if(selected&&!showAllVariants&&option.id!==selected.selectedOptionId)continue;
      // A copied canon source without its own R->Option placement belongs
      // to the selected Decision even while other variants are requested.
      const anchor=selected&&(!showAllVariants||!parentEdge)?selected.id:option.id;
      if(hidden.has(option.id)||hidden.has(anchor))continue;
      const id='__canon__'+option.id;
      virtualNodes.push({id,kind:'canon',canonForId:option.id,
        title:'Канон '+option.title,canonBlock:option.canonBlock});
      virtualEdges.push({id:'__viewcanon__'+option.id,type:'VIEW_CANON',from:anchor,to:id});
    }
    // A collapsed outer Collection may hide another group's anchor.
    const candidateNodes=[...nodes.filter(n=>!hidden.has(n.id)),...virtualNodes];
    const candidateIds=new Set(candidateNodes.map(n=>n.id));
    const visibleVirtual=virtualNodes.filter(n=>{
      const link=virtualEdges.find(e=>e.to===n.id);
      return !link||candidateIds.has(link.from);
    });
    const visibleIds=new Set([...nodes.filter(n=>!hidden.has(n.id)),...visibleVirtual].map(n=>n.id));
    return {...source,...(rootId?{rootRequirementId:rootId}:{}),nodes:[...nodes.filter(n=>!hidden.has(n.id)),...visibleVirtual],
      edges:[...edges.filter(e=>visibleIds.has(e.from)&&visibleIds.has(e.to)),
        ...virtualEdges.filter(e=>visibleIds.has(e.from)&&visibleIds.has(e.to))]};
  }
  function updateCollections(openId){
    const before=new Map(positions),camera={...view};
    const opening=!!openId;
    if(opening){
      if(positions.has('__collection__'+openId))collectionPositions.set(currentLayoutKey()+'::'+openId,{...positions.get('__collection__'+openId)});
      expandedCollections.add(openId);
    }else expandedCollections.clear();
    graph=displayGraph(sourceGraph);selected=null;selectedEdge=null;
    layout();
    for(const [id,p] of before)if(positions.has(id))positions.set(id,p);
    const occupied=[...positions].filter(([id])=>before.has(id)).map(([,p])=>p);
    for(const col of sourceGraph.collections||[]){
      if(col.memberRefs.length<=2)continue;
      const remembered=collectionPositions.get(currentLayoutKey()+'::'+col.id);
      if(!remembered)continue;
      if(!expandedCollections.has(col.id)){
        if(positions.has('__collection__'+col.id))positions.set('__collection__'+col.id,{...remembered});
      }else if(openId===col.id){
        for(const [i,id] of col.memberRefs.entries()){
          if(!positions.has(id)||before.has(id))continue;
          let p={x:remembered.x,y:remembered.y+i*112};
          while(occupied.some(q=>Math.abs(q.x-p.x)<250&&Math.abs(q.y-p.y)<90))p.y+=112;
          positions.set(id,p);occupied.push(p);
        }
      }
    }
    enteringNodes=new Set([...positions.keys()].filter(id=>!before.has(id)));
    applyLayoutPositions();Object.assign(view,camera);render();renderEdgeLegend();
  }
  function toggleCollection(id){updateCollections(id);}
  el('collections-collapse').onclick=()=>updateCollections(null);
  const stateCore=globalThis.RDGState;
  let stateMode=false,stateSources=[];
  function stateProjection(slug=null){
    const items=new Map(stateSources.map(i=>[i.slug,i]));
    for(const item of graphs)if(item.graph)items.set(item.slug,item);
    if(!fullMode&&sourceGraph){
      const id=sourceGraph.id||activeSlug||'local';
      items.set(id,{...(items.get(id)||{}),slug:id,group:sourceGraph.readOnly?'examples':'workspaces',graph:sourceGraph});
    }
    stateCore.validate([...items.values()],{partial:true});
    return stateCore.collect({items:[...items.values()],manifest:catalogModel||{},
      ...(fullMode?{rootGraphSlug:slug||activeFullRootSlug}:{graphSlug:slug||sourceGraph?.id||activeSlug})});
  }
  function appendSources(parent,refs){
    for(const s of refs||[]){
      const line=document.createElement('p');
      if(s.url&&stateCore.safeURL(s.url)){
        const a=document.createElement('a');a.setAttribute('href',s.url);a.setAttribute('target','_blank');a.setAttribute('rel','noopener noreferrer');
        a.textContent=s.title||s.url;line.appendChild(a);
      }else line.textContent='Источник недоступен: '+(s.sourceId||'не указан');
      parent.appendChild(line);
    }
  }
  function showStateFields(slug=null){
    try{
      const data=stateProjection(slug);setInspector(true);selected=null;selectedEdge=null;
      info.textContent=(slug?'Поля графа: '+slug:fullMode?'Контекст полного графа':'Контекст графа')+
        '\nОбщий контекст проекта · '+(data.identitySpace||'проект не указан')+
        '\nСначала используйте известный ответ. Условные вопросы — после соответствующего выбора.\n';
      for(const state of ['now','later','unknown']){
        const rows=data.fields.filter(f=>f.state===state);if(!rows.length)continue;
        const h=document.createElement('h3');h.textContent=({now:'Актуально сейчас',later:'После выбора ветки',unknown:'Актуальность требует проверки'})[state];info.appendChild(h);
        for(const f of rows){
          const box=document.createElement('section');box.setAttribute('data-state-field',f.fieldRef.graphSlug+':'+f.fieldRef.fieldId);
          const title=document.createElement('h4');title.textContent=f.title+' · '+({known:'поле заполнено',missing:'поле пустое',conflict:'противоречивые владельцы','needs-assessment':'область значения требует проверки'})[f.answerStatus];box.appendChild(title);
          const explain=document.createElement('p');explain.textContent=f.explanation;box.appendChild(explain);appendSources(box,f.sources);
          const details=document.createElement('p');details.textContent=f.usages.map(u=>u.graphSlug+' / '+u.location+': '+u.purpose+(u.reasons.length?' · '+u.reasons.join('; '):' · нужно сейчас')).join('\n');box.appendChild(details);
          for(const a of f.answer?[f.answer]:f.conflictingOwners||[]){const answer=document.createElement('p');answer.textContent=a.value+' · '+a.source+' · '+({applicable:'применим', 'scope-needs-assessment':'область применимости требует проверки'})[a.status]+(a.exampleOnly?' · УЧЕБНЫЙ ОТВЕТ':'');box.appendChild(answer);}
          const id=document.createElement('small');id.textContent='Поле: '+f.fieldRef.graphSlug+':'+f.fieldRef.fieldId+(f.question?' · нужно уточнить':'');box.appendChild(id);info.appendChild(box);
        }
      }
      if(!data.fields.length){const p=document.createElement('p');p.textContent='Явно объявленных использований полей пока нет.';info.appendChild(p);}
      if(data.incomplete.length){const p=document.createElement('p');p.setAttribute('data-state-incomplete','true');p.textContent='НЕПОЛНЫЙ СПИСОК: '+data.incomplete.map(x=>(x.graphSlug||x.fieldRef?.graphSlug||'')+' '+(x.location||'')+' · '+x.reason).join('\n');info.appendChild(p);}
      if(data.freeformCandidates.length){const p=document.createElement('p');p.textContent='Свободный контекст доступен для смысловой проверки при необходимости; не нужно перечитывать все записи для каждого поля.\n'+data.freeformCandidates.map(c=>c.graphSlug+':'+c.nodeId+' — '+c.text).join('\n');info.appendChild(p);}
      const help=document.createElement('p');help.textContent='Запись текущего значения: set_context_value через штатный writer с проверкой ревизии. Просмотр не изменяет факты или выбор решения.';info.appendChild(help);
      if(slug){const b=document.createElement('button');b.textContent='Открыть граф';b.onclick=()=>loadGraphSlug(slug);info.appendChild(b);}
      return data;
    }catch(error){message('Контекст: '+error.message);return null;}
  }
  function renderStateCard(scene,occupied,nodeBoxes){
    if(!graph||!stateCore)return;
    const rootId=graphRoot(graph)?.id;
    const anchor=positions.get(rootId)||positions.values().next().value||{x:48,y:72};
    const box={x:anchor.x-50,y:Math.min(anchor.y,...occupied.map(b=>b.y))-130,w:290,h:86,id:'__state_info__'};
    let data;try{data=stateProjection();}catch(_){}
    const group=make('g',scene,{id:'context-summary',class:'context-summary',transform:'translate('+box.x+' '+box.y+')',tabindex:0,role:'button','aria-label':fullMode?'Контекст полного графа':'Поля контекста графа'});
    make('rect',group,{width:box.w,height:box.h,rx:10,fill:'#263f49',stroke:'#8eb6bc','stroke-dasharray':'5 3'});
    make('text',group,{x:12,y:23,fill:'#e5f1f4','font-weight':'bold'},fullMode?'Контекст полного графа':'Поля контекста графа');
    make('text',group,{x:12,y:46,fill:'#d6e7ec'},data?'Сейчас: '+data.fields.filter(f=>f.state==='now').length+' · После выбора: '+data.fields.filter(f=>f.state==='later').length:'Список требует проверки');
    make('text',group,{x:12,y:67,fill:'#d6e7ec'},data?.incomplete.length?'Список неполон · открыть':'Общие ответы проекта · открыть');
    const open=e=>{e.stopPropagation();showStateFields();};
    group.addEventListener('pointerdown',e=>e.stopPropagation());
    group.addEventListener('click',open);group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open(e);}});
    occupied.push(box);nodeBoxes.push(box);
  }

  host.rdgState={list:stateProjection,show:showStateFields};
  function projectContextSummary() {
    const source=sourceGraph||graph;
    if(!source||!source.identitySpace||source.readOnly||source.exampleOnly)return '';
    const fromIndex=projectContexts[source.identitySpace];
    const today=new Date().toISOString().slice(0,10);
    const rows=fromIndex?.records?.map(n=>{
      const since=n.effectiveAt||n.validFrom;
      const until=n.validUntil||n.validTo;
      // Freeform Context is current project state, not a temporal evidence record.
      const timing=n.kind==='context'?'':since&&since.slice(0,10)>today?' · БУДУЩЕЕ, с '+since:
        until&&until.slice(0,10)<today?' · ИСТЕКЛО '+until:
        since||until?' · дата действия требует проверки':' · дата действия неизвестна';
      const scope=n.kind==='context'?(n.scope?' · scope '+n.scope:''):
        n.scope?' · scope '+n.scope+' (применимость не подтверждена)':' · scope не указан';
      return n.kind.toUpperCase().slice(0,1)+' '+n.id+': '+(n.currentStatement||n.title)+
        ' ['+n.graphSlug+']'+timing+scope+
        (n.scopeCompatibility==='declared-unverified'?' · совместимость scope НЕ ДОКАЗАНА':'');
    })||[];
    if(!fromIndex){
      for(const n of source.nodes||[]){
        if(n.projectionOf||n.active===false||n.status==='inactive'||n.status==='candidate'||n.status==='superseded')continue;
        if(['requirement','context'].includes(n.kind)||n.kind==='decision'&&['committed','selected-in-example-only'].includes(n.status))
          rows.push(n.kind[0].toUpperCase()+' '+n.id+': '+n.title);
      }
    }
    return '\n\nПроектные записи для проверки (инвентарь, НЕ доказанная текущая применимость; '+source.identitySpace+'):\n'+
      (rows.slice(0,40).join('\n')||'Пока нет подтверждённых элементов')+
      (fromIndex?'\nЛокально проиндексированы графы: '+fromIndex.graphSlugs.join(', '):'\nДля этого проекта общий индекс контекста недоступен.')+
      (fromIndex?.reviewAlerts?.length?'\n\nТребуют проверки после изменения R:\n'+
        fromIndex.reviewAlerts.slice(0,30).map(a=>a.graphSlug+':'+a.nodeId+
        ' ← '+a.sourceRequirementIds.join(', ')).join('\n'):'')+
      '\nОхват внешних источников неизвестен; недоступно ≠ не существует.';
  }
  async function load(text,description,options={}){
    try{
      const validated=validate(JSON.parse(text));
      if(validated.coreModel==='rdg-core-v1'){
        sourceGraph=validated;graph=JSON.parse(JSON.stringify(validated));fullMode=false;activeFullRootSlug=null;localRootId=options.localRootId||null;
        selected=null;selectedEdge=null;return true;
      }
      if(validated.actionModel!=='candidate-v6'||validated.readOnly===true||
         validated.exampleOnly===true||validated.templateOnly===true)
        throw Error('OLD_GRAPH_MODEL_DISABLED: активен только candidate-v6. Архивы Decision/Option недоступны в рабочем Viewer.');
      if(options.localRootId&&!validated.nodes.some(n=>n.id===options.localRootId&&n.kind==='requirement'))throw Error('В обновлённом графе нет R текущего уровня: '+options.localRootId);
      if(fullMode){rememberFullView();fullMode=false;}
      sourceGraph=validated;localRootId=options.localRootId||null;expandedCollections=new Set();showAllVariants=false;setInspector(false);
      graph=displayGraph(sourceGraph);selected=null;selectedEdge=null;el('search').value='';
      layout();render();fit();message(description+' · revision '+(graph.revision||'?'));
      return true;
    }catch(e){message('Ошибка: '+e.message);return false;}
  }
  function requestBackend() {
    if(typeof privilegedRequest === 'function') return privilegedRequest;
    if(typeof GM_xmlhttpRequest === 'function') return GM_xmlhttpRequest;
    if(typeof GM !== 'undefined' && GM && typeof GM.xmlHttpRequest === 'function')
      return details => GM.xmlHttpRequest(details);
    return null;
  }
  function readLocalFile(relativePath) {
    const request=requestBackend();
    if(!request)
      return Promise.reject(Error('Нет API локального чтения в Tampermonkey. Установите актуальный Local Loader v2.5.2 с @grant GM_xmlhttpRequest.'));
    if(relativePath!=='index.json'&&relativePath!=='layouts.json'&&
       (!catalogCore.validPath(relativePath)||!relativePath.endsWith('/graph.json')))
      return Promise.reject(Error('Недопустимый путь графа'));
    return new Promise((resolve,reject) => {
      request({
        method:'GET', url:GRAPH_ROOT_URL+relativePath.split('/').map(encodeURIComponent).join('/'), timeout:15000, nocache:true,
        onload: response => {
          if(response.status !== 0 && response.status !== 200)
            return reject(Error('HTTP/file status: '+response.status));
          if(typeof response.responseText !== 'string' || !response.responseText.length)
            return reject(Error('Файл пустой или не читается: '+relativePath));
          resolve(response.responseText);
        },
        onerror: err => reject(Error('Доступ к локальному файлу запрещён или файл не найден: '+relativePath)),
        ontimeout: () => reject(Error('Время чтения файла истекло: '+relativePath))
      });
    });
  }
  function navigationView(){return {showAllVariants,expandedCollections:[...expandedCollections],showAuxiliaryEdges,
    selectedEdge,search:el('search').value,view:{...view},positions:[...positions].map(([id,p])=>[id,{...p}])};}
  function navigationEntry(){return {slug:activeSlug,manualGraph:sourceGraph,manualSource:source,localRootId,focus:selected,returnView:navigationView()};}
  function showLocalLevel(id){
    localRootId=id;expandedCollections=new Set();showAllVariants=false;selected=null;selectedEdge=null;setInspector(false);
    graph=displayGraph(sourceGraph);layout();render();showGraph();
  }
  function focusRecord(id){
    if(!graph.nodes.some(n=>n.id===id)){
      const n=sourceGraph.nodes.find(n=>n.id===id);
      const parent=n?.kind==='requirement'?id:sourceGraph.edges.find(e=>e.to===id&&['DRIVES','OPTION_FOR'].includes(e.type))?.from;
      if(parent)showLocalLevel(parent);
    }
    choose(id);
  }
  async function openChildLevel(target){
    try {
      if(typeof target==='object'&&target.localRootId){
        levelStack.push(navigationEntry());showLocalLevel(target.localRootId);
      }else await loadGraphSlug(target,{child:true});
    }
    catch(err) { message('Следующий уровень недоступен: '+err.message); }
  }
  function refreshNavigationSources(slug,updated){
    levelStack=levelStack.filter(previous=>{
      if(previous.slug!==slug||!previous.manualGraph)return true;
      const rootId=previous.localRootId||graphRoot(previous.manualGraph)?.id;
      if(rootId&&!updated.nodes.some(n=>n.id===rootId&&n.kind==='requirement'))return false;
      previous.manualGraph=updated;
      previous.localRootId=rootId===graphRoot(updated)?.id?null:rootId;
      return true;
    });
  }
  async function loadGraphSlug(slug, options={}) {
    workflowGraphFile=null;
    const candidate = graphs.find(item => item.slug===slug);
    if(!candidate) throw Error('Неизвестный граф: '+slug);
    const bundled=!!candidate.graph && !options.fresh&&!options.snapshotText;
    const data=options.snapshotText||(bundled ? JSON.stringify(candidate.graph) : await readLocalFile(candidate.file));
    const fromSlug=activeSlug, fromSelected=selected;
    const fromGraph=sourceGraph,fromSource=source,fromLocalRoot=localRootId;
    const returnView=navigationView();
    // The rendering pass must see the target graph identity, not the old level.
    activeSlug=slug;
    const ok=await load(data,(bundled?'Встроенный локальный граф: ':'Локальный граф: ')+candidate.file,{localRootId:options.localRootId|| (options.fresh?fromLocalRoot:null)});
    if(!ok)activeSlug=fromSlug;
    if(ok) {
      if(options.fresh)refreshNavigationSources(slug,sourceGraph);
      if((options.child||options.reference) && fromSlug)levelStack.push({slug:fromSlug,manualGraph:fromGraph,manualSource:fromSource,localRootId:fromLocalRoot,focus:fromSelected,returnView,reference:!!options.reference});
      else if((options.child||options.reference)&&fromGraph)levelStack.push({manualGraph:fromGraph,manualSource:fromSource,localRootId:fromLocalRoot,focus:fromSelected,returnView,reference:!!options.reference});
      else if(!options.returning)levelStack=[];
      if(!bundled)candidate.graph=sourceGraph;
      source=bundled?'embedded':'auto'; activeSlug=slug;
      showGraph();
      if(!options.child&&!options.reference){
        if(manualEditor)await syncSelectedGraphPlan();
        else showLocalWorkingPlan();
      }
    }
    return ok;
  }
  async function loadCatalog() {
    if(catalogLoading) return catalogLoading;
    catalogLoading=(async()=>{
      // Data loaded by @require is available without a privileged file:// XHR.
      const manifest=embeddedSnapshot && embeddedSnapshot.schemaVersion===1
        ? embeddedSnapshot : JSON.parse(await readLocalFile('index.json'));
      if(!manifest || manifest.schemaVersion!==1 || !Array.isArray(manifest.graphs))
        throw Error('Неверный graphs/index.json');
      await initializeLayouts(manifest);
      stateSources=manifest.stateGraphs||[];
      projectContexts=manifest.projectContexts&&typeof manifest.projectContexts==='object'?manifest.projectContexts:{};
      sourceUpdateAlerts=Array.isArray(manifest.sourceUpdateAlerts)?manifest.sourceUpdateAlerts:[];
      catalogModel=catalogCore.normalizeCatalog(manifest);
      graphs=catalogModel.graphs;graphRelations=catalogModel.relations.filter(r=>
        r&&typeof r.requirementId==='string'&&typeof r.identitySpace==='string'&&
        graphs.some(g=>g.slug===r.from)&&graphs.some(g=>g.slug===r.to));
      renderCatalog();
      if(!el('catalog').hidden) showCatalog();
    })().catch(err=>{
      message('Автозагрузка недоступна: '+err.message+
        '. Проверьте доступ Tampermonkey к file://. Можно выбрать «Другой JSON».');
      console.warn('[RDG Viewer] Local graph load failed:',err);
    }).finally(()=>{catalogLoading=null;});
    return catalogLoading;
  }
  async function reload() {
    if(fullMode && activeFullRootSlug){
      try {await openFullGraph(activeFullRootSlug,{fresh:true});return true;}
      catch(err){message('Обновление полного графа не выполнено: '+err.message+
        '. Показана прежняя копия; проверьте доступ к файлам и обновите индекс.');return false;}
    }
    if(source==='auto' && activeSlug) {
      try {return await loadGraphSlug(activeSlug,{returning:true,fresh:true});}
      catch(err){message('Не удалось обновить файл: '+err.message+'. Сохраняется ранее открытый граф.');return false;}
    }
    if(source==='embedded') {
      const candidate=graphs.find(g=>g.slug===activeSlug);
      if(candidate){
        try{
          const fresh=await readLocalFile(candidate.file);
          if(await load(fresh,'Файл: '+candidate.file,{localRootId})) {
            source='auto';
            candidate.graph=sourceGraph;refreshNavigationSources(activeSlug,sourceGraph);
          }
          return;
        }catch(err){
          message('Граф загружен через локальный @require. Для обновления данных '+
            'перезагрузите страницу ChatGPT. Прямой запрос к файлу не разрешён.');
          return;
        }
      }
    }
    message('Для обновления вручную выбранного файла укажите его повторно.');
    el('picker').click();
  }
  launcher.onclick=()=>{
    if (Date.now() < suppressLauncherClickUntil) return;
    el('panel').classList.add('open');launcher.hidden=true;showCatalog();
  };
  el('close').onclick=()=>{if(layoutDirty&&!layoutAutoPaused&&!layoutAutoBlocked&&layoutFileHandle)void saveLayout({interactive:false}).catch(()=>{});el('panel').classList.remove('open');el('launch').hidden=false;};
  el('back').onclick=()=>{if(!fullMode&&activeFullRootSlug)void openFullGraph(activeFullRootSlug);else {const folder=selectedFolder;activeFullRootSlug=null;openFolder(folder);}};
  el('folder-back').onclick=()=>openFolder(selectedFolder.includes('/')?selectedFolder.slice(0,selectedFolder.lastIndexOf('/')):'');
  el('example-set-map').onclick=()=>openFullGraph(activeFullRootSlug);
  el('catalog-search').oninput=renderCatalog;
  function restoreNavigationView(previous){
    const state=previous.returnView;
    if(state){
      showAllVariants=state.showAllVariants;
      expandedCollections=new Set(state.expandedCollections);
      showAuxiliaryEdges=state.showAuxiliaryEdges;
      selectedEdge=null;
      el('search').value=state.search;
      graph=displayGraph(sourceGraph);
      layout();for(const [id,p] of state.positions||[])if(positions.has(id))positions.set(id,p);
      applyLayoutPositions();render();renderEdgeLegend();
      Object.assign(view,state.view);
      transform();
    }
    if(previous.focus)choose(previous.focus,false);
    else choose(null,false);
  }
  el('level-up').onclick=async()=>{
    if(levelStack.length){
      const prev=levelStack.at(-1);
      let ok=false;
      if(prev.manualGraph){
        activeSlug=prev.slug||null;
        ok=await load(JSON.stringify(prev.manualGraph),'Ранее открытый JSON',{localRootId:prev.localRootId});
        if(ok){source=prev.manualSource;showGraph();}
      }else ok=await loadGraphSlug(prev.slug,{returning:true});
      if(ok){
        levelStack.pop();
        el('level-up').hidden=!(levelStack.length||incomingToGraph(activeSlug).length);
        restoreNavigationView(prev);
      }
      return;
    }
    const incoming=incomingToGraph(activeSlug);
    if(incoming.length===1)await loadGraphSlug(incoming[0].from,{returning:true});
  };
  el('source').onclick=()=>{
    el('viewer-more').open=false;
    const originalSource=sourceMarkdownFor(graph);
    if(originalSource===null)return;
    const opening=el('source-view').hidden;
    el('source-view').hidden=!opening;
    el('content').hidden=opening;
    el('edge-toolbar').hidden=opening;
    el('source-text').textContent=originalSource;
    el('source').textContent=opening?'← К графу':'Исходный модуль';
    for(const id of ['fit','search']) el(id).hidden=opening;
    if(!opening)fit();
  };
  el('file').onclick=()=>{el('viewer-more').open=false;el('picker').click();};
  el('picker').onchange=async e=>{
    const input=e.target,file=input.files&&input.files[0];
    if(!file)return;
    const fromSlug=activeSlug;
    try{
      const text=await file.text();activeSlug=null;
      const ok=await load(text,'Файл: '+file.name);
      if(ok){source='file';activeSlug=null;levelStack=[];showGraph();}
      else activeSlug=fromSlug;
    }catch(error){activeSlug=fromSlug;message('Ошибка чтения файла: '+error.message);}
    finally{input.value='';}
  };
  el('reload').onclick=async()=>{el('viewer-more').open=false;await reload();};
  el('fit').onclick=()=>fit(false);
  el('context-fields').onclick=()=>showStateFields();
  el('context-mode').onclick=()=>{stateMode=!stateMode;el('context-mode').setAttribute('aria-pressed',String(stateMode));el('context-mode').textContent='Просмотр контекста: '+(stateMode?'вкл.':'выкл.');message(stateMode?'Просмотр контекста: нажмите граф, чтобы увидеть его поля.':'Навигация: нажмите граф, чтобы открыть его.');};
  el('edges-all').onclick=()=>{if(!fullMode)return;showAuxiliaryEdges=true;selectedEdge=null;graph=projectFullGraph();layout();render();renderEdgeLegend();fit();};
  el('edges-mode').onchange=()=>{if(!fullMode)return;
    (el('edges-mode').value==='all'?el('edges-all'):el('edges-core')).onclick();};
  el('edges-core').onclick=()=>{if(!fullMode)return;showAuxiliaryEdges=false;selectedEdge=null;selected=null;el('search').value='';graph=projectFullGraph();layout();render();renderEdgeLegend();fit();};
  el('variants-all').onclick=()=>{
    const before=new Map(positions),camera={...view};
    rememberFullView();showAllVariants=!showAllVariants;graph=fullMode?projectFullGraph():displayGraph(sourceGraph);
    selected=null;selectedEdge=null;setInspector(false);layout();
    for(const [id,p] of before)if(positions.has(id))positions.set(id,p);
    const occupied=[...positions].filter(([id])=>before.has(id)).map(([,p])=>p);
    for(const [id,value] of positions)if(!before.has(id)&&!savedPositions()[id]){
      const p={...value};while(occupied.some(q=>Math.abs(q.x-p.x)<250&&Math.abs(q.y-p.y)<90))p.y+=112;
      positions.set(id,p);occupied.push(p);
    }
    enteringNodes=new Set([...positions.keys()].filter(id=>!before.has(id)));
    applyLayoutPositions();Object.assign(view,camera);render();renderEdgeLegend();rememberFullView();
  };
  el('search').oninput=e=>{
    if(!graph)return;
    const q=e.target.value.trim().toLowerCase();
    let found=graph.nodes.find(n=>n.id.toLowerCase()===q)||graph.nodes.find(n=>(n.id+' '+n.title).toLowerCase().includes(q));
    if(q&&!found&&fullMode){
      const hidden=sourceGraph.nodes.find(n=>n.id.toLowerCase()===q)||sourceGraph.nodes.find(n=>(n.id+' '+n.title).toLowerCase().includes(q));
      if(hidden){if(!showAllVariants)el('variants-all').onclick();found=graph.nodes.find(n=>n.id===hidden.id);}
    }
    if(q&&!found&&!fullMode){
      const record=sourceGraph.nodes.find(n=>n.id.toLowerCase()===q)||sourceGraph.nodes.find(n=>(n.id+' '+n.title).toLowerCase().includes(q));
      const parent=record?.kind==='requirement'?record.id:sourceGraph.edges.find(e=>e.to===record?.id&&['OPTION_FOR','DRIVES'].includes(e.type))?.from;
      if(parent&&sourceGraph.nodes.some(n=>n.id===parent&&n.kind==='requirement')){
        openChildLevel({localRootId:parent});found=graph.nodes.find(n=>n.id===record.id);
      }
    }
    choose(q&&found?found.id:null,!!(q&&found));
  };
  svg.addEventListener('pointerdown',e=>{
    if(e.button!==0)return;
    const target=e.target.closest('[data-id]'),visibleId=target?.getAttribute('data-id');
    const id=graph?.edges.find(link=>link.type==='VIEW_CANON'&&link.to===visibleId)?.from||visibleId;
    if(id&&positions.has(id)){nodeDrag={id,pointerId:e.pointerId,x:e.clientX,y:e.clientY,start:{...positions.get(id)},moved:false};return;}
    drag={x:e.clientX,y:e.clientY,ox:view.x,oy:view.y};svg.setPointerCapture(e.pointerId);
  });
  svg.addEventListener('pointermove',e=>{
    if(nodeDrag){
      if(e.pointerId!==nodeDrag.pointerId)return;
      const dx=e.clientX-nodeDrag.x,dy=e.clientY-nodeDrag.y;
      if(!nodeDrag.moved&&Math.hypot(dx,dy)<6)return;
      nodeDrag.moved=true;svg.setPointerCapture(e.pointerId);
      const p={x:Math.round((nodeDrag.start.x+dx/view.scale)*100)/100,y:Math.round((nodeDrag.start.y+dy/view.scale)*100)/100};
      layoutCommand({type:'set_positions',positions:{[nodeDrag.id]:p}});return;
    }
    if(!drag)return;
    view.x=drag.ox+e.clientX-drag.x;view.y=drag.oy+e.clientY-drag.y;transform();
  });
  const stop=e=>{
    if(nodeDrag){
      if(nodeDrag.moved){
        suppressNodeClickUntil=Date.now()+350;choose(nodeDrag.id,false);
        // Persist the displayed geometry of every pair moved out of the way,
        // so an automatic save/reload cannot restore the old overlap.
        if(graph.edges.some(edge=>edge.type==='VIEW_CANON')){
          const capture=captureLayoutCommand();if(capture)recordLayoutCommands([capture]);
        }
      }
      nodeDrag=null;scheduleLayoutSave();
    }
    drag=null;
    if(e&&svg.hasPointerCapture?.(e.pointerId))svg.releasePointerCapture(e.pointerId);
  };
  svg.addEventListener('pointerup',stop);svg.addEventListener('pointercancel',stop);
  el('layout-save').onclick=async()=>{try{await saveLayout();}catch(e){message(e.name==='AbortError'?'Сохранение отменено; расположение осталось в черновике.':e.message);}};
  el('layout-open').onclick=async()=>{try{
    if(typeof window.showOpenFilePicker!=='function')throw Error('Выбор общего файла недоступен в этом браузере');
    const [handle]=await window.showOpenFilePicker({multiple:false,types:[{description:'RDG layouts.json',accept:{'application/json':['.json']}}]});
    await attachLayoutFile(handle);
  }catch(e){message(e.name==='AbortError'?'Выбор файла отменён.':e.message);}};
  el('layout-connect').onclick=async()=>{
    if(sourceGraph&&layoutDirty)return el('layout-save').onclick();
    try{
      if(typeof window.showOpenFilePicker!=='function')throw Error('Прямое подключение файла недоступно; используйте экспорт');
      const [handle]=await window.showOpenFilePicker({multiple:false,types:[{description:'RDG layouts.json',accept:{'application/json':['.json']}}]});
      if(handle.requestPermission&&await handle.requestPermission({mode:'readwrite'})!=='granted')throw Error('Нет разрешения на запись');
      await attachLayoutFile(handle);
    }catch(error){message(error.name==='AbortError'?'Выбор файла отменён.':error.message);}
  };
  el('layout-pause').onclick=()=>{layoutAutoPaused=!layoutAutoPaused;updateLayoutControls();scheduleLayoutSave();};
  window.addEventListener('beforeunload',event=>{if(layoutDirty){event.preventDefault();event.returnValue='';}});
  window.addEventListener('pagehide',()=>{persistLayoutDraft();});
  el('layout-export').onclick=()=>{try{exportLayout();}catch(e){message(e.message);}};
  el('layout-drafts').onclick=()=>{void showLayoutDrafts().catch(error=>message(error.message));};
  el('layout-discard').onclick=()=>{try{discardLayoutChanges();}catch(error){message(error.message);}};
  el('layout-reset').onclick=()=>{
    if(!sourceGraph)return;
    layoutCommand({type:'clear_layout'});
    message('Автоматическое расположение восстановлено. Изменение будет сохранено при подключённом файле.');
  };
  svg.addEventListener('wheel',e=>{
    if(!graph)return;
    e.preventDefault();
    const rect=svg.getBoundingClientRect();
    Object.assign(view,viewGeometry.wheelView(view,e,{x:e.clientX-rect.left,y:e.clientY-rect.top},
      {width:rect.width,height:rect.height}));transform();
  },{passive:false});
  // @require executes before the loader body. The loader passes its privileged
  // GM request function explicitly; a direct install starts on the next microtask.
  function startViewer(request) {
    if(typeof request === 'function') privilegedRequest = request;
    if(startupRequested) {
      if(request && !graph) return loadCatalog();
      return catalogLoading;
    }
    startupRequested = true;
    return loadCatalog();
  }
  host.rdgExplorer=Object.freeze({openFolder,openFull:openFullGraph,openGraph:async slug=>{
    const item=graphs.find(g=>g.slug===slug);if(!item)throw Error('Неизвестный граф: '+slug);
    activeFullRootSlug=null;selectedFolder=item.folder;
    return loadGraphSlug(slug);
  },getCatalog:()=>JSON.parse(JSON.stringify(catalogModel))});
  const PLAN_ROOT_URL=GRAPH_ROOT_URL.replace(/graphs\/$/,'');
  function readLocalPlanOwner(slug){
    if(!/^[a-z0-9][a-z0-9_-]*$/.test(slug))return Promise.reject(Error('PLAN_ROOT_SLUG_INVALID'));
    const request=requestBackend();
    if(!request)return Promise.reject(Error('Нет разрешённого локального чтения Plan owner; настройте Loader/Helper.'));
    const url=PLAN_ROOT_URL+'plans/'+encodeURIComponent(slug)+'/plan.json';
    return new Promise((resolve,reject)=>request({method:'GET',url,timeout:15000,nocache:true,
      onload:r=>{
        if(r.status!==0&&r.status!==200)return reject(Error('PLAN_FILE_NOT_FOUND'));
        try{resolve(JSON.parse(r.responseText));}catch{reject(Error('PLAN_FILE_INVALID_JSON'));}
      },onerror:()=>reject(Error('PLAN_FILE_NOT_FOUND_OR_ACCESS_DENIED')),
      ontimeout:()=>reject(Error('PLAN_FILE_READ_TIMEOUT'))}));
  }
  let planLoadSerial=0;
  let manualEditor=null,manualContainer=null,workflowSnapshot=null,workflowGraphFile=null,localPreviewEditor=null;
  let sessionDependencyTransport=null,dependencyCurrent=null,dependencySerial=0,dependencyHistorySerial=0;
  let dependencySnapshotPublished=false;
  function publishedReadOnlyOwner(entry,root){
    // Derived from real Graph/Plan/Gendocen owner files, read-only forever.
    // Publisher verifies owner source hashes. A changed Graph revision must
    // NEVER borrow old Plan/engine data silently.
    const record=entry&&embeddedSnapshot?.publishedOwners?.[entry.slug];
    const graph=root||graphs.find(g=>g.slug===entry?.slug)?.graph;
    if(!record||!graph||record.mode!=='published-owner-snapshot'||
       record.schemaVersion!==1||graph.actionModel!=='candidate-v6'||
       record.graphFile!==entry.file||record.identitySpace!==entry.identitySpace||
       record.rootRequirementId!==entry.rootRequirementId||
       record.graphRevision!==graph.revision||graph.identitySpace!==entry.identitySpace||
       record.planOwner?.kind!=='temporalPlanOwner'||
       record.planOwner?.owner?.sourcePath!=='plans/'+entry.slug+'/plan.json'||
       record.planOwner?.owner?.identitySpace!==graph.identitySpace||
       record.planOwner?.revision!==record.planRevision||
       record.dependencies?.engine!=='gendocen'||
       record.dependencies?.identitySpace!==graph.identitySpace||
       !record.dependencies?.sourceGraphs?.includes(entry.file))return null;
    return record;
  }
  function currentWorkingGraphEntry(){
    if(!catalogModel)return null;
    if(activeFullRootSlug)return catalogModel.fullGraphs.find(e=>e.slug===activeFullRootSlug)||null;
    const entry=graphs.find(e=>e.slug===activeSlug);
    return entry&&(entry.presentation?.usage==='working'||entry.file?.startsWith('workspaces/'))?entry:null;
  }
  async function showLocalWorkingPlan(force=false){
    if(manualEditor&&!force)return;
    const sequence=++planLoadSerial,entry=currentWorkingGraphEntry(),api=globalThis.RDGWorkflowUI;
    if(!entry||!api){
      if(localPreviewEditor){localPreviewEditor=null;el('workflow-panel').replaceChildren();
        el('workflow-panel').hidden=true;}
      if(!entry)connectionStatus('Папка Helper не подключена. Выберите рабочий граф в «Папках», чтобы увидеть его план и историю.');
      return;
    }
    const published=graphs.find(g=>g.slug===entry.slug)?.graph;
    // Navigating to a declaration loads a sanitized Graph without its authored
    // workflowExample. For read-only teaching sources retain the canonical
    // published sample instead of replacing its timeline with an empty one.
    const root=published&&(published.readOnly||published.exampleOnly)?published:
      (activeSlug===entry.slug&&!fullMode?sourceGraph:null)||published;
    if(!root){connectionStatus('Граф ещё не прочитан: '+entry.title,true);return;}
    const owners={[entry.file]:root};
    if(entry.identitySpace){
      for(const g of graphs)if(g.slug!==entry.slug&&(g.identitySpace||g.graph?.identitySpace)===entry.identitySpace&&g.graph)
        owners[g.file]=g.graph;
    }
    const panel=el('workflow-panel');panel.replaceChildren();panel.hidden=false;
    localPreviewEditor=null;
    const isExample=!!(root.readOnly||root.exampleOnly||entry.presentation?.exampleOnly||
                     !entry.file.startsWith('workspaces/')&&entry.presentation?.usage!=='working');
    connectionStatus('Читаю сохранённый Plan «'+entry.title+'»…');
    try{
      let published=false,storedOwner=null;
      if(!isExample){
        try{storedOwner=await readLocalPlanOwner(entry.slug);}
        catch(error){
          const saved=publishedReadOnlyOwner(entry,root);
          if(!saved)throw error;
          storedOwner=saved.planOwner;published=true;
        }
      }
      let view=isExample?api.localPlanPreview(entry,owners,{exampleOnly:true}):
        api.localPlanFromOwner(entry,owners,storedOwner);
      if(published){
        const sourceSnapshot=publishedReadOnlyOwner(entry,root);
        if(!sourceSnapshot||!Array.isArray(sourceSnapshot.history))
          throw Error('PUBLISHED_GRAPH_HISTORY_NOT_VERIFIED');
        // This is a serialized result of the regular authorized workflow
        // reader, not a fabricated educational scene.
        view={...view,history:sourceSnapshot.history,
          coverage:'Опубликованный read-only снимок реальных Graph и Plan writer journals. Не live.'};
      }
      if(sequence!==planLoadSerial)return;
      localPreviewEditor=api.mount(panel,{read:async()=>view},{document,readOnly:true,
        localPreview:isExample,onNavigate:(ref,v)=>host.rdgWorkflow.openDeclaration(ref,v),
        onOpenExample:slug=>openFullGraph(slug)});
      await localPreviewEditor.refresh();
      connectionStatus(isExample?'Архивный Plan недоступен в рабочем Viewer.':published?
        'Plan «'+entry.title+'» · опубликованный снимок настоящего Plan owner r'+storedOwner.revision+
        ', только чтение. Данные могут устареть. Для записи и актуализации подключите Helper.':
        'Сохранённый Plan «'+entry.title+'» открыт из файла · только чтение. Для записи и полной истории подключите Helper.');
    }catch(error){
      if(sequence!==planLoadSerial)return;
      panel.replaceChildren();localPreviewEditor=null;
      connectionStatus('Plan «'+entry.title+'» не открыт: '+error.message+
        '. Файл может существовать, но быть недоступен через file://. Подключите авторизованный Helper; '+
        'если owner ещё не создан, Helper --auto-workspaces инициализирует его при наличии прав.',true);
    }
  }
  el('workflow-graph-toggle').onclick=()=>{el('workflow-graph-editor').hidden=!el('workflow-graph-editor').hidden;};
  function viewerTab(name){
    const workflow=name==='workflow',dependencies=name==='dependencies',graphView=name==='graph';
    el('viewer-more').open=false;
    el('view-options').open=false;
    el('graph-pane').hidden=!graphView;el('workflow-page').hidden=!workflow;
    el('dependency-page').hidden=!dependencies;
    el('graph-tab').setAttribute('aria-selected',String(graphView));
    el('workflow-toggle').setAttribute('aria-selected',String(workflow));
    el('dependency-toggle').setAttribute('aria-selected',String(dependencies));
    el('panel').setAttribute('data-view',name);
    el('panel').classList.add('open');
  }
  el('graph-tab').onclick=()=>viewerTab('graph');
  el('workflow-toggle').onclick=async()=>{
    viewerTab('workflow');if(!manualEditor)await showLocalWorkingPlan();
    await sessionFolderReady;
    if(sessionFolder&&!manualEditor&&!sessionRestoreAttempted)await connectSessionFolder(sessionFolder,false);
  };
  const depText=(id,value)=>{el(id).textContent=value;};
  async function dependencyRequest(request){
    const entry=currentFullGraphEntry()||currentWorkingGraphEntry();
    if(!entry)throw Error('Выберите рабочий Graph owner candidate-v6.');
    const direct=!!(globalThis.RDG_LOCAL_WORKFLOW&&workflowSnapshot&&
      workflowSnapshot.graphFile===entry.file&&
      workflowSnapshot.sources?.graphs?.[entry.file]?.identitySpace===entry.identitySpace);
    const binding=planBinding(entry)||(direct?{contextId:workflowSnapshot.contextId||null,
      graphFile:entry.file,identitySpace:entry.identitySpace}:null);
    const args={...(binding?.contextId?{contextId:binding.contextId}:{}),...request};
    if(binding&&sessionDependencyTransport)return sessionDependencyTransport.dependencies(args);
    if(binding&&globalThis.RDG_LOCAL_DEPENDENCIES)return globalThis.RDG_LOCAL_DEPENDENCIES(args);
    // Offline Viewers can use ONLY explicitly published historical engine
    // receipts. They are never live status and never authorize writes.
    const snapshot=publishedReadOnlyOwner(entry);
    if(snapshot){
      if(request.historyTarget){
        if(!Object.prototype.hasOwnProperty.call(snapshot.dependencyHistory,request.historyTarget))
          throw Error('GENDOCEN_PUBLISHED_HISTORY_NOT_IN_SCOPE');
        return {available:true,publishedSnapshot:true,history:snapshot.dependencyHistory[request.historyTarget]};
      }
      return {available:true,publishedSnapshot:true,report:snapshot.dependencies};
    }
    throw Error('Для актуальной проверки подключите авторизованный Helper. У этого рабочего Graph нет опубликованного снимка Gendocen.');
  }

  function dependencyScopeOptions(report){
    const dropdown=el('dependency-scope'),prior=dropdown.value;
    const ids=new Set();for(const row of report.rows)for(const source of row.uses)ids.add(source.nodeId);
    dropdown.replaceChildren();const all=document.createElement('option');all.value='';all.textContent='Все Requirements графа';dropdown.appendChild(all);
    for(const id of [...ids].sort()){
      const item=document.createElement('option');item.value=id;item.textContent='R: '+id;dropdown.appendChild(item);
    }
    dropdown.value=ids.has(prior)?prior:'';
  }
  function dependencyLink(parent,file,nodeId,label){
    const button=document.createElement('button');button.textContent=label;parent.appendChild(button);
    const entry=currentFullGraphEntry()||currentWorkingGraphEntry();
    const published=publishedReadOnlyOwner(entry);
    const offline=published?{graphFile:entry.file,contextRootId:entry.rootRequirementId,
      sources:{graphs:{[entry.file]:graphs.find(g=>g.slug===entry.slug)?.graph},
        plan:published.planOwner.versions.at(-1).plan}}:null;
    const snap=manualEditor?.view||workflowSnapshot||offline;
    const g=snap?.sources?.graphs?.[file];
    const found=g?.nodes?.some(n=>n.id===nodeId);
    button.disabled=!found||!snap||!snap.sources.graphs[file];
    button.title=button.disabled?'Исходный владелец недоступен в авторизованной Helper-сессии':'Открыть исходный узел в Graph';
    button.onclick=async()=>{
      if(button.disabled)return;
      await host.rdgWorkflow.openDeclaration({graphFile:file,identitySpace:g.identitySpace,nodeId},snap);
    };
    return button;
  }
  async function dependencyHistory(parent,target){
    const token=++dependencyHistorySerial;parent.textContent='Загружаю Gendocen receipts и историю…';
    try{
      const result=await dependencyRequest({historyTarget:target});
      if(token!==dependencyHistorySerial)return;
      const history=result.history||{},events=history.events||[];
      parent.replaceChildren();
      const label=document.createElement('p');label.textContent='Receipts: '+(history.receipt_ids||[]).join(', ');parent.appendChild(label);
      if(!events.length){const x=document.createElement('p');x.textContent='Событий Gendocen пока нет.';parent.appendChild(x);}
      for(const event of events){const x=document.createElement('pre');x.textContent=JSON.stringify(event,null,2);parent.appendChild(x);}
    }catch(error){parent.textContent='История не прочитана: '+error.message;}
  }
  function renderDependencies(){
    const container=el('dependency-items');container.replaceChildren();
    const report=dependencyCurrent;
    if(!report)return;
    const scope=el('dependency-scope').value,showValid=el('dependency-show-valid').checked;
    const selectedRows=report.rows.filter(row=>(!scope||row.nodeId===scope||
      row.uses.some(u=>u.nodeId===scope))&&(showValid||row.status!=='valid'));
    const summary=document.createElement('p');summary.className='dep-scope-state';
    summary.textContent=(scope?'Область: Requirement '+scope:'Весь доступный Graph owner')+
      ' · '+(dependencySnapshotPublished?'предупреждений в снимке: ':'предупреждений: ')+selectedRows.filter(r=>r.status!=='valid').length+
      ' · Gendocen, результаты не подтверждают истинность решений.';
    container.appendChild(summary);
    if(!selectedRows.length){const item=document.createElement('p');item.className='dep-empty';
      item.textContent='В выбранной области нет предупреждений с текущими подписками. Это не означает отсутствие скрытых или внешних зависимостей.';
      container.appendChild(item);}
    for(const row of selectedRows){
      const card=document.createElement('article');card.className='dep-item';card.dataset.status=row.status;container.appendChild(card);
      const head=document.createElement('h3');head.textContent=row.kind+' '+row.nodeId+' · '+row.title;card.appendChild(head);
      const state=document.createElement('p');state.className='dep-changed';
      state.textContent={review_required:'ТРЕБУЕТ ПРОВЕРКИ по Gendocen',valid:'Проверено по принятому Gendocen receipt',
        stale:'STALE — требуется проверка',invalid:'Недействительный dependency receipt'}[row.status]||'Статус Gendocen: '+row.status;
      card.appendChild(state);
      dependencyLink(card,row.graphFile,row.nodeId,'Открыть зависимый блок в Graph ↗');
      for(const source of row.uses){
        const part=document.createElement('div');card.appendChild(part);
        const text=document.createElement('p');text.className='dep-reasons';
        text.textContent='Использована R '+source.nodeId+' · '+source.reasons.join('; ');part.appendChild(text);
        dependencyLink(part,source.graphFile,source.nodeId,'Открыть изменённую R ↗');
      }
      if(row.changedDependencies?.length){const changed=document.createElement('p');changed.className='dep-changed';
        changed.textContent='Изменились входы: '+row.changedDependencies.join('; ');card.appendChild(changed);}
      const details=document.createElement('details');card.appendChild(details);
      const heading=document.createElement('summary');heading.textContent='История обновлений зависимостей (Gendocen)';details.appendChild(heading);
      const history=document.createElement('div');history.className='dep-history';details.appendChild(history);
      details.addEventListener('toggle',()=>{if(details.open&&!details.dataset.loaded){details.dataset.loaded='true';void dependencyHistory(history,row.target);}});
    }
  }
  async function refreshDependencies(){
    const serial=++dependencySerial;
    depText('dependency-status','Сверяю реальные Graph owners и Gendocen receipts…');
    try{
      await sessionFolderReady;
      const payload=await dependencyRequest({});
      if(serial!==dependencySerial)return;
      if(!payload.available)throw Error(payload.reason||'Gendocen не настроен');
      dependencyCurrent=payload.report;
      dependencySnapshotPublished=!!payload.publishedSnapshot;
      el('dependency-refresh').textContent=dependencySnapshotPublished?'Повторно открыть опубликованный снимок':'Проверить зависимости';
      dependencyScopeOptions(dependencyCurrent);renderDependencies();
      depText('dependency-status',dependencySnapshotPublished?
        'ОПУБЛИКОВАННЫЙ СНИМОК Gendocen, только чтение. Исторические статусы на момент публикации — НЕ текущая проверка. Подключите Helper для актуализации.':
        'Данные получены из живого Gendocen. Изменившиеся источники требуют повторной проверки, но не доказывают ошибочность решения.');
    }catch(error){if(serial!==dependencySerial)return;dependencyCurrent=null;el('dependency-items').replaceChildren();
      depText('dependency-status','Зависимости недоступны: '+error.message);
    }
  }
  el('dependency-refresh').onclick=refreshDependencies;
  el('dependency-scope').onchange=renderDependencies;
  el('dependency-show-valid').onchange=renderDependencies;
  el('dependency-all').onclick=()=>{el('dependency-scope').value='';renderDependencies();};
  el('dependency-toggle').onclick=async()=>{
    const node=sourceGraph?.nodes?.find(n=>n.id===selected&&n.kind==='requirement');
    viewerTab('dependencies');
    await refreshDependencies();
    if(node&&[...el('dependency-scope').options].some(x=>x.value===node.id)){
      el('dependency-scope').value=node.id;renderDependencies();
    }
  };

  el('workflow-toggle').hidden=false;el('workflow-page').hidden=true;

  const connectionStatus=(text,error=false)=>{
    el('workflow-connection').textContent=text;
    el('workflow-connection').classList.toggle('wf-error',error);
  };
  if(typeof window.showDirectoryPicker!=='function'){
    el('workflow-connect').disabled=true;
    connectionStatus('В этом браузере недоступен выбор папки. Откройте Viewer в браузере с поддержкой доступа к локальным папкам или используйте локальный интерфейс Helper.');
  }
  host.rdgWorkflow=Object.freeze({
    attach(){
      viewerTab('workflow');el('workflow-panel').hidden=false;
      if(globalThis.RDG_LOCAL_WORKFLOW){
        for(const id of ['workflow-connect','workflow-reconnect','workflow-forget'])el(id).hidden=true;
        el('workflow-help').textContent='Подключено к локальному Helper. Данные и изменения проходят через него.';
        connectionStatus('Локальный Helper подключён.');
      }
      return el('workflow-panel');
    },
    graphEditor(){
      const panel=el('workflow-graph-editor');panel.replaceChildren();panel.hidden=true;
      return panel;
    },
    async loadGraph(data,snapshot){
      workflowSnapshot=snapshot||workflowSnapshot;workflowGraphFile=snapshot?.graphFile||null;
      if(data.coreModel==='rdg-core-v1'){
        sourceGraph=JSON.parse(JSON.stringify(data));graph=JSON.parse(JSON.stringify(data));source='helper';activeSlug=null;
        el('content').hidden=true;el('workflow-graph-editor').hidden=false;
        el('message').textContent='Уточнённая модель: собственные графы и изменения доступны ниже.';
        showGraph();return;
      }
      const ok=await load(JSON.stringify(data),'Локальный Helper');
      if(!ok)throw Error('Helper вернул некорректный граф');
      source='helper';activeSlug=null;showGraph();
    },
    async openDeclaration(reference,snapshot){
      const api=globalThis.RDGWorkflowUI;
      if(!api)throw Error('Модуль перехода к объявлению недоступен');
      const origin=api.declarationFor(snapshot,reference);
      const item=graphs.find(g=>g.file===origin.ref.graphFile&&(!g.identitySpace||g.identitySpace===origin.ref.identitySpace));
      workflowSnapshot=snapshot;workflowGraphFile=origin.ref.graphFile;activeSlug=item?.slug||null;
      if(origin.graph.coreModel==='rdg-core-v1'){
        const panel=el('workflow-graph-editor');panel.hidden=false;
        const controller=manualEditor||globalThis.RDG_LOCAL_EDITOR;
        if(controller?.view?.graphFile===origin.ref.graphFile&&controller.focusCore?.(origin.node.id)){
          el('content').hidden=true;viewerTab('graph');
          return {graphFile:origin.ref.graphFile,nodeId:origin.node.id,contextRootId:origin.contextRootId};
        }
        panel.replaceChildren();api.mountCore(panel,origin.graph,{document,focusId:origin.node.id,readOnly:true});
        el('content').hidden=true;viewerTab('graph');
        return {graphFile:origin.ref.graphFile,nodeId:origin.node.id,contextRootId:origin.contextRootId};
      }
      const ok=await load(JSON.stringify(origin.graph),'Объявление: '+origin.ref.graphFile);
      if(!ok)throw Error('Граф объявления не прошёл проверку');
      source='helper';levelStack=[];localRootId=origin.contextRootId===graphRoot(sourceGraph)?.id?null:origin.contextRootId;
      showAllVariants=true;showAuxiliaryEdges=true;expandedCollections=new Set();
      graph=displayGraph(sourceGraph);layout();render();
      if(!positions.has(origin.node.id)){
        // Historical R/Action may no longer be on the active path because its
        // introduction was archived or its Collection is folded. Show the
        // existing owner Graph in full; never invent a missing Graph node.
        localRootId=null;
        expandedCollections=new Set((sourceGraph.collections||[]).map(c=>c.id));
        graph=displayGraph(sourceGraph);layout();render();
      }
      if(!positions.has(origin.node.id))throw Error('Исходный блок есть в файле, но не может быть показан в графе');
      viewerTab('graph');showGraph();el('workflow-graph-editor').hidden=true;
      choose(origin.node.id,true);
      return {graphFile:origin.ref.graphFile,nodeId:origin.node.id,contextRootId:origin.contextRootId};
    }
  });
  // IndexedDB stores the browser directory handle only, never the session token.
  // Permissions remain controlled by the browser; restore never prompts on load.
  function sessionFolderStore(operation,handle){
    return new Promise((resolve,reject)=>{
      if(typeof indexedDB==='undefined')return reject(Error('IndexedDB недоступна'));
      const request=indexedDB.open('rdg-workflow-folders',1);
      request.onupgradeneeded=()=>request.result.createObjectStore('handles');
      request.onerror=()=>reject(request.error);
      request.onblocked=()=>reject(Error('Хранилище папки занято другой вкладкой'));
      request.onsuccess=()=>{
        const db=request.result;let result;
        try{
          const tx=db.transaction('handles',operation==='get'?'readonly':'readwrite'),store=tx.objectStore('handles');
          const item=operation==='get'?store.get(GRAPH_ROOT_URL):
            operation==='put'?store.put(handle,GRAPH_ROOT_URL):store.delete(GRAPH_ROOT_URL);
          item.onsuccess=()=>{result=item.result;};
          tx.oncomplete=()=>{db.close();resolve(result||null);};
          tx.onerror=tx.onabort=()=>{db.close();reject(tx.error||Error('Не удалось сохранить папку'));};
        }catch(error){db.close();reject(error);}
      };
    });
  }
  let sessionFolder=null,sessionFolderSaved=false,sessionConnecting=false,sessionRestoreAttempted=false;
  let sessionContexts=null;
  function currentFullGraphEntry(){
    if(!catalogModel)return null;
    if(activeFullRootSlug)return catalogModel.fullGraphs.find(x=>x.slug===activeFullRootSlug)||null;
    const current=graphs.find(x=>x.slug===activeSlug);
    if(!current?.identitySpace)return null;
    const candidates=catalogModel.fullGraphs.filter(x=>x.identitySpace===current.identitySpace);
    return candidates.length===1?candidates[0]:null;
  }
  function planBinding(entry){
    if(!entry||!sessionContexts)return null;
    if(Array.isArray(sessionContexts.contexts)){
      const matchingIdentity=entry.identitySpace||'legacy-'+entry.slug;
      const matchingRoot=entry.rootRequirementId||entry.graph?.rootRequirementId||
        entry.graph?.nodes?.find(n=>n.kind==='requirement')?.id;
      const row=sessionContexts.contexts.find(x=>x.rootSlug===entry.slug&&x.graphFile===entry.file&&
        x.identitySpace===matchingIdentity&&x.rootRequirementId===matchingRoot);
      return row?{contextId:row.rootSlug,graphFile:row.graphFile,planFile:row.planFile,
        identitySpace:row.identitySpace,title:entry.title}:null;
    }
    // Older single-workspace sessions are only safe for their exact root.
    return sessionContexts.graphFile===entry.file?
      {contextId:null,graphFile:entry.file,planFile:sessionContexts.planFile,
        identitySpace:entry.identitySpace,title:entry.title}:null;
  }
  async function syncSelectedGraphPlan(){
    if(!manualEditor)return;
    if(sessionContexts?.profile==='portable'){el('workflow-panel').replaceChildren(manualContainer);return;}
    const entry=currentFullGraphEntry()||currentWorkingGraphEntry(),binding=planBinding(entry);
    if(!binding){
      await manualEditor.switchWorkspace(null,'У этого графа пока нет сохранённого плана в текущей Helper-сессии.');
      await showLocalWorkingPlan(true);
      return;
    }
    localPreviewEditor=null;
    el('workflow-panel').replaceChildren(manualContainer);
    await manualEditor.switchWorkspace(binding);
    if(!manualEditor.view){
      await showLocalWorkingPlan(true);
      connectionStatus('Не удалось прочитать Plan через Helper для «'+entry.title+'»; проверьте права и журнал.',true);
    }else connectionStatus('План «'+entry.title+'» подключён и сохранён в Plan owner.');
  }
  const sessionControls=()=>{
    const blocked=sessionConnecting||!!(manualEditor?.busy||manualEditor?.pending);
    for(const id of ['workflow-connect','workflow-reconnect','workflow-forget'])el(id).disabled=blocked;
    if(typeof window.showDirectoryPicker!=='function')el('workflow-connect').disabled=true;
    el('workflow-reconnect').hidden=!sessionFolder;
    el('workflow-forget').hidden=!sessionFolder;
    el('workflow-connect').textContent=sessionFolder?'Выбрать другую папку':'Подключить папку сессии';
  };
  const folderNote=()=>{el('workflow-folder-note').textContent=sessionFolder?
    (sessionFolderSaved?'Папка «'+(sessionFolder.name||'session')+'» запомнена в этом браузере.':
      'Папка доступна до закрытия страницы: браузер не смог сохранить её выбор.')+
      ' Сохранение папки не продлевает сессию Helper.':'';};
  const sessionFolderReady=(async()=>{
    if(globalThis.RDG_LOCAL_WORKFLOW||typeof window.showDirectoryPicker!=='function')return;
    try{
      const handle=await sessionFolderStore('get');
      if(handle?.kind!=='directory'||typeof handle.getFileHandle!=='function')return;
      sessionFolder=handle;sessionFolderSaved=true;folderNote();sessionControls();
      connectionStatus('Сохранена папка «'+(handle.name||'session')+'». Откройте план для подключения.');
    }catch(_){/* Explicit folder selection still works when storage is unavailable. */}
  })();
  async function connectSessionFolder(handle,interactive){
    if(sessionConnecting||manualEditor?.busy||manualEditor?.pending){
      connectionStatus('Сначала завершите текущий запрос или подтвердите его исход в прежней сессии.',true);return;
    }
    sessionConnecting=true;sessionRestoreAttempted=true;sessionControls();
    try{
      if(handle.queryPermission&&await handle.queryPermission({mode:'readwrite'})!=='granted'){
        if(!interactive){
          connectionStatus('Папка запомнена. Для доступа нажмите «Подключить сохранённую папку» в настройках плана.');
          el('workflow-settings').open=true;return;
        }
        connectionStatus('Ожидаю разрешение на чтение и запись в выбранную папку session…');
        if(!handle.requestPermission||await handle.requestPermission({mode:'readwrite'})!=='granted')
          throw Error('Нет разрешения на папку сессии. Подключите её снова и разрешите чтение и запись.');
      }
      const api=globalThis.RDGWorkflowUI;
      if(!api)throw Error('Обновите исходник Viewer с модулем ручного интерфейса');
      const transport=api.fileTransport(handle);
      try{sessionContexts=await transport.describe();sessionDependencyTransport=transport;}
      catch(error){
        // Preserve the older in-panel diagnostic and disabled controls for
        // expired/invalid sessions; never keep the preceding Plan visible.
        sessionContexts=null;
        el('workflow-panel').replaceChildren();
        manualEditor=api.mount(host.rdgWorkflow.attach(),transport,
          {document,graphContainer:host.rdgWorkflow.graphEditor(),
            onGraph:(g,v)=>host.rdgWorkflow.loadGraph(g,v),
            onNavigate:(ref,v)=>host.rdgWorkflow.openDeclaration(ref,v),onStateChange:sessionControls});
        await manualEditor.refresh();
        throw error;
      }
      sessionFolder=handle;
      try{await sessionFolderStore('put',handle);sessionFolderSaved=true;}
      catch(_){sessionFolderSaved=false;}
      folderNote();sessionControls();
      localPreviewEditor=null;el('workflow-panel').replaceChildren();
      manualContainer=document.createElement('div');host.rdgWorkflow.attach().appendChild(manualContainer);
      if(sessionContexts?.profile==='portable'){
        if(!globalThis.RDGPortableUI)throw Error('Обновите Viewer с поддержкой пакетов.');
        manualEditor=globalThis.RDGPortableUI.mount(manualContainer,{call:message=>transport.write(message)},{document,onStateChange:sessionControls});
        await manualEditor.refresh();el('workflow-settings').open=false;
        connectionStatus('Подключён каталог переносимых Graph-пакетов.');return;
      }
      manualEditor=api.mount(manualContainer,transport,
        {document,graphContainer:host.rdgWorkflow.graphEditor(),onGraph:(g,v)=>
            currentFullGraphEntry()?undefined:host.rdgWorkflow.loadGraph(g,v),
          onNavigate:(ref,v)=>host.rdgWorkflow.openDeclaration(ref,v),onStateChange:sessionControls});
      connectionStatus('Выбрана папка «'+(handle.name||'session')+'». Проверяю ответ Helper.');
      if(Array.isArray(sessionContexts.contexts))await syncSelectedGraphPlan();
      else if(currentFullGraphEntry()&&planBinding(currentFullGraphEntry()))await syncSelectedGraphPlan();
      else if(currentWorkingGraphEntry())await syncSelectedGraphPlan();
      else await manualEditor.refresh();
      if(manualEditor.view)el('workflow-settings').open=false;
      if(manualEditor.view&&!currentFullGraphEntry())
        connectionStatus('Папка «'+(handle.name||'session')+'» подключена.');
    }catch(error){
      connectionStatus(error.name==='AbortError'?'Выбор папки или разрешение отменены. Можно подключить папку снова.':error.message,true);
    }finally{sessionConnecting=false;sessionControls();}
  }
  el('workflow-connect').onclick=async()=>{
    await sessionFolderReady;
    if(sessionConnecting||manualEditor?.busy||manualEditor?.pending)return;
    sessionConnecting=true;sessionControls();
    let handle;
    try{
      if(typeof window.showDirectoryPicker!=='function')throw Error('Выбор папки сессии недоступен');
      connectionStatus('Выберите папку session. Браузер запросит чтение и запись для обмена с Helper.');
      handle=await window.showDirectoryPicker({mode:'readwrite'});
    }catch(error){
      connectionStatus(error.name==='AbortError'?'Выбор папки или разрешение отменены. Можно подключить папку снова.':error.message,true);
    }finally{sessionConnecting=false;sessionControls();}
    if(handle)await connectSessionFolder(handle,true);
  };
  el('workflow-reconnect').onclick=()=>sessionFolder&&connectSessionFolder(sessionFolder,true);
  el('workflow-forget').onclick=async()=>{
    if(sessionConnecting||manualEditor?.busy||manualEditor?.pending)return;
    sessionConnecting=true;sessionControls();
    try{
      await sessionFolderStore('delete');sessionFolder=null;sessionFolderSaved=false;folderNote();
      connectionStatus(manualEditor?.view?'Папка забыта. Текущее подключение работает до закрытия страницы.':
        'Папка забыта. Подключите папку сессии через настройки плана.');
    }catch(_){connectionStatus('Не удалось забыть папку. Повторите действие.',true);}
    finally{sessionConnecting=false;sessionControls();}
  };
  host.rdgStart = startViewer;
  Promise.resolve().then(() => {
    if(!startupRequested && !globalThis.RDG_LOCAL_WORKFLOW) return startViewer();
  });
})();