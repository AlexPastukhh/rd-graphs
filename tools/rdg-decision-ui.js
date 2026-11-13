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
