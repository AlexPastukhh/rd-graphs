#!/usr/bin/env python3
"""Legacy path-reference adapter. No publication or semantic mutation."""
import hashlib
import json
from pathlib import Path
import re
from importlib.machinery import SourceFileLoader
IO=SourceFileLoader('legacy_reference_routes',str(Path(__file__).with_name('rdg-transaction-io.py'))).load_module()


def legacy_plan_readset(plan, graph_root, authorize):
    refs = [(step['kind'], step.get('actionRef') or step.get('requirementRef'))
            for step in plan['steps'] if step['kind'] in ('action', 'requirement')]
    paths = sorted({ref['graphFile'] for _, ref in refs})
    authorize(paths)
    root = Path(graph_root).absolute();readset = {};graphs = {}
    for relative in paths:
        if not re.fullmatch(r'workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json', relative):
            raise ValueError('PLAN_REFERENCE_PATH_INVALID')
        path = root / relative
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()) or any(
                p.is_symlink() for p in (path, *path.parents) if p != root.parent):
            raise ValueError('PLAN_REFERENCE_GRAPH_UNAVAILABLE')
        if IO.portable_container(path,root) is not None:
            raise ValueError('PLAN_REFERENCE_REQUIRES_PACKAGE_ID')
        IO.require_current_legacy(path)
        raw = path.read_bytes();graph = json.loads(raw)
        if not isinstance(graph.get('nodes'), list):raise ValueError('PLAN_REFERENCE_GRAPH_INVALID')
        nodes = {node['id']: node for node in graph['nodes']}
        if len(nodes) != len(graph['nodes']):raise ValueError('PLAN_REFERENCE_GRAPH_INVALID')
        graphs[relative] = graph, nodes
        readset[path] = hashlib.sha256(raw).hexdigest()
    for kind, ref in refs:
        graph, nodes = graphs[ref['graphFile']]
        node = nodes.get(ref['nodeId'])
        if graph.get('identitySpace') != ref['identitySpace'] or not node or node.get('kind') != kind:
            raise ValueError('PLAN_REFERENCE_IDENTITY_OR_NODE_MISMATCH')
    return readset


def verify_readset(readset):
    for path, expected in readset.items():
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('PLAN_REFERENCE_CHANGED_DURING_PREPARE')
