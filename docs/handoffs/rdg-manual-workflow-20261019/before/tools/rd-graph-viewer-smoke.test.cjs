const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const base = __dirname;
const script = fs.readFileSync(path.join(base, 'rd-graph-viewer.user.js'),'utf8');
const loader = fs.readFileSync(path.join(base, 'rd-graph-viewer-local-loader.user.js'),'utf8');
assert.match(loader,/^\/\/ @require +file:\/\/\/C:\/Users\/alexa\/Repos\/rd-graphs\/tools\/rd-graph-viewer\.user\.js/m);
const storage = new Map();
function boot() {
  const elements = {};
  let attached = false, host;
  function element(id) {
    const classes = new Set(), handlers = {};
    return {
      id, handlers, classes, hidden:false, style:{}, offsetWidth:100, offsetHeight:32,
      clientWidth:900, clientHeight:650, textContent:'', value:'',
      classList:{add:s=>classes.add(s),remove:s=>classes.delete(s),toggle:(s,yes)=>yes?classes.add(s):classes.delete(s)},
      addEventListener:(s,fn)=>{handlers[s]=fn}, setPointerCapture(){},
      getBoundingClientRect:()=>({left:Number.parseFloat(host.style.left)||1086,
        top:Number.parseFloat(host.style.top)||674}),
      setAttribute(){},appendChild(){},replaceChildren(){}
    };
  }
  const root = {
    set innerHTML(html) {for(const m of html.matchAll(/id="([^"]+)"/g)) elements[m[1]]=element(m[1]);},
    getElementById:id=>elements[id]||null, querySelectorAll:()=>[]
  };
  const document = {
    getElementById:id=>attached && id===host.id ? host : null,
    createElement:(tag)=>{if(!attached && tag==='div' && !host.id)return host;return element(tag);},
    createElementNS:(_ns,tag)=>element(tag),
    documentElement:{appendChild(){attached=true}}
  };
  host={id:'',dataset:{},style:{},attachShadow(){this.shadowRoot=root;return root}};
  const context={document,window:{innerWidth:1200,innerHeight:800,addEventListener(){}},
    localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},
    console,Date,Math,JSON,Object,Number,Error};
  vm.runInNewContext(script,context,{timeout:2000});
  assert.equal(host.dataset.rdgVersion,'2.0.3');
  assert(elements.launch,'launcher created');
  return {host,elements};
}
const first=boot();
assert.equal(first.host.style.bottom,'94px');
first.elements.launch.handlers.pointerdown({button:0,pointerId:1,clientX:800,clientY:660});
first.elements.launch.handlers.pointermove({pointerId:1,clientX:850,clientY:620});
first.elements.launch.handlers.pointerup({pointerId:1});
assert.equal(first.host.style.left,'1092px'); // Clamped to 8px viewport margin
assert.equal(first.host.style.top,'634px');
const key='rdg-viewer-launcher-position-v1';
assert.equal(JSON.parse(storage.get(key)).x,1092);
first.elements.launch.onclick(); // Drag must not open
assert(!first.elements.panel.classes.has('open'));
const second=boot();
assert.equal(second.host.style.left,'1092px');
assert.equal(second.host.style.top,'634px');
second.elements.launch.onclick();
assert(second.elements.panel.classes.has('open'));
console.log('SMOKE_OK: launcher, default position, drag, click separation, persistence');

(async () => {
  const fixture=JSON.parse(fs.readFileSync('/workspace/repos/rd-graphs/graphs/examples/example/graph.json','utf8'));
  const third=boot();
  const source={name:'graph.json',text:async()=>JSON.stringify(fixture)};
  await third.elements.picker.onchange({target:{files:[source],value:''}});
  assert.match(third.elements.message.textContent,/revision 1/);
  assert.match(third.elements.info.textContent,/5 узлов/);
  console.log('SMOKE_OK: JSON validation, SVG rendering, graph summary');
})().catch(e=>{console.error(e);process.exitCode=1;});
