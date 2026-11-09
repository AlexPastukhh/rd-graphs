const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const code=fs.readFileSync(path.join(__dirname,'../tools/rd-graph-viewer.user.js'),'utf8');
const loaderCode=fs.readFileSync(path.join(__dirname,'../tools/rd-graph-viewer-local-loader.user.js'),'utf8');
const bundleCode=fs.readFileSync(path.join(__dirname,'../tools/rd-graph-data.js'),'utf8');
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'../graphs/examples/example/graph.json'),'utf8'));
const clone=x=>JSON.parse(JSON.stringify(x));
function simulate(options={}) {
  let host=null,attached=false;
  const ids={};
  function node(tag='div'){
    const attrs={},children=[],listeners={},classes=new Set();let ownText='';
    const o={tag,children,listeners,style:{},get textContent(){return ownText+children.map(c=>c.textContent||'').join('');},set textContent(v){ownText=String(v);children.length=0;},value:'',hidden:false,
      disabled:false,offsetWidth:105,offsetHeight:32,clientWidth:800,clientHeight:500,
      classList:{contains:k=>classes.has(k),toggle:(k,v)=>v?classes.add(k):classes.delete(k),
        add:k=>classes.add(k),remove:k=>classes.delete(k)},
      setAttribute(k,v){attrs[k]=String(v);if(k==='class'){classes.clear();String(v).split(/\s+/).forEach(x=>classes.add(x));}},
      getAttribute:k=>attrs[k]??null,
      appendChild(child){children.push(child);return child;},
      replaceChildren(...ch){children.splice(0,children.length,...ch);},
      addEventListener(k,handler){listeners[k]=handler;},
      setPointerCapture(){},click(){return o.onclick?.();},
      closest(sel){return sel==='[data-id]'&&attrs['data-id']?o:null;},
      getBoundingClientRect(){return {left:0,top:0,width:800,height:500};}
    };
    return o;
  }
  const root={
    set innerHTML(markup){
      for(const m of markup.matchAll(/id="([^"]+)"/g))ids[m[1]]=node(m[1]);
    },
    getElementById(id){
      if(ids[id])return ids[id];
      const walk=x=>x.getAttribute?.('id')===id?x:x.children?.map(walk).find(Boolean);
      return walk(ids.canvas);
    },
    querySelectorAll(selector){
      const out=[];
      const walk=x=>{
        if(selector==='.node'&&x.classList?.contains('node'))out.push(x);
        for(const c of x.children||[])walk(c);
      };
      if(ids.canvas)walk(ids.canvas);
      return out;
    }
  };
  const document={
    getElementById:id=>id==='rdg-viewer-root'&&attached?host:null,
    createElement(tag){return tag==='div'&&!host? (host=node('host')):node(tag);},
    createElementNS(ns,tag){return node(tag);},
    documentElement:{appendChild(x){host=x;attached=true;}}
  };
  const oldNode=node;
  // Host receives attachShadow before execution so the viewer can create its
  // private DOM. First createElement('div') below returns this host.
  host=null;
  const actualCreate=document.createElement.bind(document);
  document.createElement=tag=>{
    const x=actualCreate(tag);
    if(tag==='div'&&x===host&&!x.attachShadow) {
      x.dataset={};x.attachShadow=()=>{x.shadowRoot=root;return root;};
    }
    return x;
  };
  const logs=[],storage=options.storage||new Map();
  const window={innerWidth:1200,innerHeight:800,showDirectoryPicker:null,addEventListener(){}};
  const mockGM=options.files?(request=>{
    const prefix='file:///C:/Users/alexa/Repos/rd-graphs/graphs/';
    assert(request.url.startsWith(prefix),'unexpected local path: '+request.url);
    const relative=request.url.slice(prefix.length);
    if(options.files[relative]===undefined)return request.onerror({status:404});
    request.onload({status:0,responseText:options.files[relative]});
  }):undefined;
  const sandbox={document,window,GM_xmlhttpRequest:options.viaLoader?undefined:options.modern?undefined:mockGM,
    GM:options.modern?{xmlHttpRequest:mockGM}:undefined,
    localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k),key:i=>[...storage.keys()][i]??null,get length(){return storage.size}},
    console:{info:(...xs)=>logs.push(xs.join(' ')),error:(...xs)=>logs.push(xs.join(' ')),warn:(...xs)=>logs.push(xs.join(' '))},
    Math,JSON,Date,Object,Number,Error,URL,...(options.timers||{})};
  const context=vm.createContext(sandbox);
  if(options.useBundle)vm.runInContext(bundleCode,context,{timeout:2500});
  vm.runInContext(code,context,{timeout:2500});
  if(options.viaLoader){context.GM_xmlhttpRequest=mockGM;vm.runInContext(loaderCode,context,{timeout:2500});}
  const loadFile=async(data,name='graph.json')=>{
    await ids.picker.onchange({target:{files:[{name,text:async()=>typeof data==='string'?data:JSON.stringify(data)}],value:''}});
  };
  const info=()=>ids.info.textContent;
  const text=()=>ids.message.textContent;
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  const openFolder=folder=>host.rdgExplorer.openFolder(folder);
  const openCard=async slug=>host.rdgExplorer.openGraph(slug);
  const openSet=async id=>host.rdgExplorer.openSet(id);
  const openLevel=async(parentSlug,requirementId)=>{
    await openCard(parentSlug);
    const target=root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===requirementId);
    assert(target,'Level R not displayed: '+requirementId);
    target.listeners.click({stopPropagation(){}});await flush();
  };
  const visitLevels=async visitor=>{
    const visited=new Set();
    const visit=async()=>{
      const key=host.rdgLayout.graphKey();if(visited.has(key))return;visited.add(key);
      ids['edges-all'].onclick();await visitor({key});
      const targets=root.querySelectorAll('.node').filter(n=>n.classList.contains('drill')).map(n=>n.getAttribute('data-id'));
      for(const id of targets){
        const target=root.querySelectorAll('.node').find(n=>n.getAttribute('data-id')===id);assert(target,'lost parent R '+id);
        target.listeners.click({stopPropagation(){}});await flush();assert.notEqual(host.rdgLayout.graphKey(),key,'drill opens another level');
        await visit();await ids['level-up'].onclick();assert.equal(host.rdgLayout.graphKey(),key,'returns to exact parent level');
      }
    };
    await visit();return visited;
  };
  return {ids,root,window,loadFile,info,text,logs,host,flush,openFolder,openCard,openSet,openLevel,visitLevels,
    fixture,clone,storage,context};
}
module.exports={simulate,fixture,clone,code,bundleCode,loaderCode};
