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
