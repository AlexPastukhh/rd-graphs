"""API conveniences over the existing planner, readers and coordinator."""
import base64
import copy
import hashlib
import json
import uuid


def capabilities(app, ident=None):
    # Identity comes from the running host, never from a repository checkout.
    app.authority._actor(app.authority._read(), app.token)
    owner = app.snapshot(ident, layouts=False) if ident else None
    features = {
        'ownedRefRead': {'available': True, 'version': 1},
        'receiptEnvelope': {'available': True, 'version': 1},
        'preflightPreview': {'available': True, 'version': 1},
        'graphSnapshotRead': {'available': True, 'version': 1},
        'paperBatch': {'available': True, 'version': 1},
        'paperRemoval': {'available': True, 'version': 1},
        'externalReaderRoute': {'available': True, 'version': 1},
        'crossOwnerBatch': {'available': False, 'reason': 'single-owner-batch-only'},
    }
    if owner:
        paper = owner['head']['role'] in ('ready', 'lens')
        managed = not (owner['head'].get('lineage', {}).get('supplied') and
                       not owner['head'].get('lineage', {}).get('userManaged'))
        supported = owner['graph']['coreModel'] == 'rdg-decision-v1'
        for key in ('paperBatch', 'paperRemoval'):
            features[key]['available'] = paper and managed and supported
            if not features[key]['available']:
                features[key]['reason'] = ('profile-unsupported' if not supported else
                    'paper-owner-required' if not paper else 'explicit-owner-management-required')
    build = getattr(app, 'runtime_build_id', None)
    return {'schemaVersion': 1, 'contractVersion': 2, 'readOnly': True,
            'runtime': {'buildId': build if build!='source' else None, 'mode':'source' if build=='source' else 'host' if build else 'unbound',
                        'identityAvailable': build is not None and build!='source'},
            'features': features, 'profile': app.profile_capabilities(
                owner['graph'], owner['head']['role']) if owner else None}


def receipt(app, ident, tx):
    app.check(isinstance(tx, str) and str(uuid.UUID(tx)) == tx, 'TRANSACTION_ID')
    with app.store.lock(False, create=False):
        result = app._legacy_receipt(ident, tx)
        envelope = {'schemaVersion': 1, 'transactionId': tx, 'found': False,
                    'accepted': bool(result.get('published')), 'published': False, 'currentStateVerified': False,
                    'participants': [], **result}
        path = app.store.metadata_path('accepted', tx)
        if path.is_file():
            cert = json.loads(path.read_bytes())
            if app.store.transaction_actor(cert, hashlib.sha256(app.token.encode()).hexdigest()):
                payload = app.store._load_payload(tx, cert)
                completed = app.store.metadata_path('completed', tx)
                published = completed.is_file()
                if published:
                    app.check(json.loads(completed.read_bytes()) == app.store._completion_value(
                        tx, cert['requestSHA256'], payload['entries']), 'COMPLETION_CERTIFICATE')
                participants = []
                for entry in payload['entries']:
                    item = {'owner': app.store.entry_owner(entry),
                            'revision': entry['afterHead']['revision'], 'sha256': entry['afterSHA256']}
                    if published:
                        raw = base64.b64decode(entry['receipt']['bytes'], validate=True)
                        app.check(app.store.sha(raw) == entry['afterHead']['receipt']['sha256'], 'RECEIPT_HASH_MISMATCH')
                        item['receipt'] = json.loads(raw)
                    participants.append(item)
                envelope.update(found=True, accepted=True, published=published,
                    publicationCertificatePresent=published, requestSHA256=cert['requestSHA256'],
                    participants=participants, state='completed-certificate' if published else 'prepared')
                # Keep the package receipt compatibility key, including if its current owner is unavailable.
                for item in participants:
                    if item['owner'].get('packageId') == ident and 'receipt' in item:
                        envelope.setdefault('receipt', item['receipt'])
        if 'receipt' in envelope:
            r = envelope['receipt']
            envelope.update(accepted=True, requestSHA256=r['requestSHA256'])
            if not envelope['participants']:
                envelope['participants'] = [{'owner': {'kind': 'package',
                    'namespaceId': app.store.namespace_id, 'packageId': r['packageId']},
                    'revision': r['packageRevision'], 'receipt': r}]
        envelope['currentStateVerified'] = False
        return envelope


def source_access(target):
    if target.get('kind') in ('file', 'document') and 'uri' in target:
        return {'route': 'external-reader', 'request': {k: target[k] for k in
                ('uri', 'version', 'sha256') if k in target},
                'instruction': 'Open with an authorized external reader. A link or pin is not source content; verify any supplied SHA256/version.'}
    return {'route': 'rdg',
            'instruction': 'Use explicit source expansion; availability and contentLoaded are separate.'}


def next_read(ref):
    return {'method': 'read_ref', 'reference': copy.deepcopy(ref)}


def read_ref(app, reference, ident=None, expand=False, output_format='json'):
    app.check(isinstance(reference, dict) and
        set(reference) == {'theoryRef', 'collection', 'itemId'}, 'OWNED_REF_FIELDS')
    ref = reference['theoryRef']
    app.model.validate_reference(ref)
    app.check(ref['mode'] in ('current', 'historical'), 'OWNED_REF_MODE_UNSUPPORTED')
    with app.store.lock(False, create=False):
        consumer = app.snapshot(ident or ref['packageId'], layouts=False)
        source = consumer if consumer['packageId'] == ref['packageId'] else app.snapshot(ref['packageId'], layouts=False)
        resolved = app.resolve_for(ref, consumer)
        node = resolved.get('node')
        app.check(node is not None and node.get('kind') == 'canon', 'OWNED_REF_UNAVAILABLE')
        historical = resolved['status'] in ('historical', 'deleted', 'historical-current-unavailable')
        if historical:
            _, history = app.reference_snapshots(ref, consumer)
            graph = history.get((ref['packageId'], ref['identitySpace'], ref['sha256']))
            app.check(graph is not None, 'HISTORICAL_GRAPH_UNAVAILABLE')
            source = {**source, 'graph': graph, 'head': {**source['head'], 'revision': None}}
        else:
            app.check(node['revision'] == ref['revision'], 'OWNED_REF_CHANGED')
        result = app.kernel.for_graph(source['graph']).THEORY.read(app, source, ref['nodeId'],
            collection=reference['collection'], item_ids=[reference['itemId']], expand=expand,
            output_format=output_format, expected_revision=node['revision'])
        result['historical'] = historical
        if historical:
            result['theory']['ref']['mode'] = 'historical'
            for page in result['data'].values():
                for item in page['items']:
                    item['ref']['theoryRef']['mode'] = 'historical'
                    item['nextRead'] = next_read(item['ref'])
        return result


def removal_effects(app, before, after):
    removed = sorted(set(app.kernel.entities(before)) - set(app.kernel.entities(after)))
    return {'removedNodeIds': removed,
        'removedEdgeIds': sorted({e['id'] for e in before['edges']} - {e['id'] for e in after['edges']}),
        'removedRootCauseIds': sorted({c['id'] for c in before['rootCauses']} - {c['id'] for c in after['rootCauses']}),
        'removedMemberships': [dict(groupId=g['id'],**m) for g in before['decisionGroups'] for m in g['members']
            if not any(q['id']==g['id'] and m in q['members'] for q in after['decisionGroups'])],
        'removedDecisionGroupIds': sorted({g['id'] for g in before['decisionGroups']} -
                                         {g['id'] for g in after['decisionGroups']}),
        'changedDecisionGroupIds': sorted(g['id'] for g in after['decisionGroups']
            if next((v for v in before['decisionGroups'] if v['id'] == g['id']), None) != g),
        'changedWorkGraphIds': sorted(g['id'] for g in after['workGraphs']
            if next((v for v in before['workGraphs'] if v['id'] == g['id']), None) != g),
        'dependentOwnersChanged': False}


def paper_removal_guard(app, row, removed, candidate):
    """Fail closed on incoming current refs; never rewrite another owner."""
    removed = set(removed); groups = set()
    app.check(row['head']['role'] in ('ready', 'lens'), 'PAPER_OWNER_REQUIRED')
    app.check(not (row['head'].get('lineage', {}).get('supplied') and
                   not row['head'].get('lineage', {}).get('userManaged')), 'PACKAGE_IMMUTABLE')
    metas = app.store.scan()
    app.check(app.store.initialized() and all(m['health'] in
              ('metadata-verified', 'unaccepted-stage') for m in metas), 'INCOMING_INVENTORY_UNHEALTHY')
    rows = {}; blockers = []
    def visit(value, owner, path=(), registry=False):
        if isinstance(value, dict):
            same = (value.get('packageId') == row['packageId'] and
                    value.get('identitySpace') == row['graph']['identitySpace'])
            if same and (registry or value.get('mode') == 'current') and (
                    value.get('nodeId') in removed or value.get('workGraphId') in groups):
                blockers.append({'owner': owner, 'path': list(path), 'reference': copy.deepcopy(value)})
            for key, item in value.items():
                if key not in ('events', 'entityLineage', 'factLineage'):
                    visit(item, owner, path + (key,), registry)
        elif isinstance(value, list):
            for i, item in enumerate(value):visit(item, owner, path + (i,), registry)
    for meta in metas:
        pid = meta.get('packageId')
        if meta['health'] == 'unaccepted-stage' or pid == row['packageId']:continue
        foreign = app.snapshot(pid, True, layouts=False); rows[pid] = foreign
        visit(foreign['graph'], {'kind': 'package', 'packageId': pid})
        if foreign['plan']:
            visit(foreign['plan'], {'kind': 'package', 'packageId': pid}, ('plan',))
    visit(candidate, {'kind': 'package', 'packageId': row['packageId']})
    registry = app.registry()
    visit(registry['registry'].get('packages', []), {'kind': 'recommendationRegistry'}, registry=True)
    app.check(not blockers, 'PAPER_REMOVE_CURRENT_REFERENCES:' + json.dumps(blockers, ensure_ascii=False, sort_keys=True))
    return rows, registry


def cleaned_layouts(app, row, graph):
    if row['layouts'] is None:return None
    before = row['graph']; ids = set(app.kernel.entities(graph)); edges = app.visual_edges(before)
    cleaned = app.layout('remap', document=row['layouts'], spec={
        'sourceSpace': before['identitySpace'], 'targetSpace': graph['identitySpace'],
        'viewMap': {graph['id']: graph['id']}, 'entityMap': {i:i for i in ids},
        'sourceIds': sorted(app.kernel.entities(before)), 'sourceSlugs': [graph['id']],
        'edgeMap': {e['id']:e['id'] for e in app.visual_edges(graph)},
        'edgeEndpoints': {e['id']:{'from':e['from'], 'to':e['to']} for e in edges}})['document']
    cleaned['revision'] = row['layouts']['revision'] + 1
    return cleaned


def preview(app, prepared, tx, options):
    app.check(isinstance(options, dict) and set(options) <=
              {'packageId', 'detail', 'nodeId', 'include', 'format', 'limit'}, 'PREVIEW_FIELDS')
    ident = options.get('packageId')
    app.check(ident in prepared['changes'], 'PREVIEW_EFFECT_OWNER_REQUIRED')
    change = prepared['changes'][ident]
    app.check('graph' in change, 'PREVIEW_GRAPH_REQUIRED')
    # Readers receive an in-memory owner overlay. No draft files, pins or owners are created.
    projected = copy.copy(app)
    def snapshot(pid, plan=False, layouts=True, **kwargs):
        if pid not in prepared['changes']:return app.snapshot(pid, plan, layouts, **kwargs)
        delta = prepared['changes'][pid]; before = delta.get('before')
        graph = delta.get('graph', (before or {}).get('graph'))
        app.check(graph is not None, 'PREVIEW_GRAPH_REQUIRED')
        row = copy.deepcopy(before) if before else {
            'packageId': pid, 'path': delta['path'], 'head': {
                'packageId': pid, 'role': delta['role'], 'identitySpace': graph['identitySpace'],
                'revision': 0, 'current': {}}, 'headSHA256': None,
                'plan': None, 'layouts': None, 'receiptValue': None}
        row['graph'] = graph
        row['plan'] = delta.get('plan', row.get('plan'))
        row['layouts'] = delta.get('layouts', row.get('layouts'))
        return row
    projected.snapshot = snapshot
    key = app.store.registry_key()
    if key in prepared['changes']:
        reg = prepared['changes'][key]['registry']
        projected.registry = lambda: {'registry': reg}
    detail = options.get('detail', 'focus')
    app.check(detail in ('focus', 'branch'), 'PREVIEW_DETAIL')
    value = projected.read(ident, detail=detail, node_id=options.get('nodeId'),
        include=options.get('include'), limit=options.get('limit', 25),
        output_format=options.get('format', 'json'))
    return {'accepted': False, 'transactionId': tx, 'persisted': False, 'projection': value,
            'instruction': 'Unaccepted proposed Graph. Projection references are not accepted source pins. Apply the exact request with inputBinding; read accepted state afterwards.'}


def normalize_paper(app, graph):
    graph['events'] = []
    for node in app.kernel.entities(graph).values():
        node.pop('review', None)
        if node['kind'] in ('requirement','decision','action'):
            node['result']={'state':'open','truth':'unknown'}
        if node['kind']=='decision' and node['selectionState']=='selected':
            node['selectionState']='unselected'
    return graph
