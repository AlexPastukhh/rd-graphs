#!/usr/bin/env python3
"""Filesystem adapter and recoverable multi-head coordinator for portable packages.

Semantic effects are supplied by the application. The prepared certificate is
acceptance; all staged bytes and the recovery payload precede it. A reader checks
pending certificates and never serves a half-published transaction as healthy.
"""
import base64
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid


class RecoveryRequired(ValueError):
    pass


class FileStore:
    def __init__(self, root, namespace_id, io, codec, coordination_root=None):
        self.root = Path(root).absolute()
        self.namespace_id = namespace_id
        self.io = io
        self.codec = codec
        self.coordination_root = Path(coordination_root or self.root.parent).absolute()
        self.check(str(uuid.UUID(namespace_id)) == namespace_id, 'NAMESPACE_ID')
        self.check(self.coordination_root.is_dir() and not self.coordination_root.is_symlink(), 'COORDINATION_ROOT')
        self.check(not self.root.is_symlink(), 'SYMLINK_ROOT')

    @staticmethod
    def check(condition, code):
        if not condition:raise ValueError('PACKAGE_' + code)

    def encode(self, value):return self.codec.encoded(value)
    def sha(self, value):return self.io.sha256(value)
    def path(self, relative, metadata=False):return self.io.safe_path(self.root, relative, metadata)
    def package_path(self, relative):return self.path(relative)
    def lock(self, exclusive=True, create=True):return self.io.reference_lock(self.coordination_root, exclusive, create)

    def initialized(self):
        path = self.path('.rdg/namespace.json', True)
        if not path.is_file():return False
        marker = json.loads(path.read_bytes())
        self.check(marker == {'schemaVersion': 1, 'kind': 'rdgPackageNamespace', 'namespaceId': self.namespace_id}, 'NAMESPACE_MISMATCH')
        return True

    def initialize(self):
        if not self.initialized():
            self.check(not self.scan(), 'UNREGISTERED_EXISTING_NAMESPACE')
        self.io.mkdirs(self.root)
        path = self.path('.rdg/namespace.json', True)
        marker = self.encode({'schemaVersion': 1, 'kind': 'rdgPackageNamespace', 'namespaceId': self.namespace_id})
        self.io.immutable_bytes(path, marker)

    def metadata_path(self, category, transaction_id):
        self.check(str(uuid.UUID(transaction_id)) == transaction_id, 'TRANSACTION_ID')
        return self.path('.rdg/' + category + '/' + transaction_id + '.json', True)

    def validate_head(self, value):
        self.check(isinstance(value, dict) and value.get('schemaVersion') == 1 and value.get('kind') == 'rdgGraphPackage', 'FORMAT')
        required = {'schemaVersion', 'kind', 'packageId', 'namespaceId', 'role', 'identitySpace', 'graphId', 'revision',
                    'generation', 'current', 'files', 'lastTransactionId', 'receipt'}
        self.check(required <= set(value) and set(value) <= required | {'previousHead', 'lineage', 'lensKey'}, 'MANIFEST_FIELDS')
        self.check(str(uuid.UUID(value['packageId'])) == value['packageId'] and value['namespaceId'] == self.namespace_id, 'IDENTITY')
        self.check(value['role'] in self.codec.ROLES and type(value['revision']) is int and value['revision'] >= 1 and
                   all(isinstance(value[k], str) and value[k] for k in ('identitySpace', 'graphId')), 'MANIFEST_OWNER')
        self.check(str(uuid.UUID(value['generation'])) == value['generation'] and
                   str(uuid.UUID(value['lastTransactionId'])) == value['lastTransactionId'], 'GENERATION')
        self.check(isinstance(value['files'], dict) and isinstance(value['current'], dict) and
                   set(value['current']) <= {'graph', 'plan', 'layouts'} and 'graph' in value['current'], 'INVENTORY')
        for relative, sha in value['files'].items():
            self.io.safe_path(self.root, relative, True)
            self.check(relative.startswith(('state/', 'history/', 'evidence/', 'provenance/')) and
                       bool(re.fullmatch('[0-9a-f]{64}', sha)), 'INVENTORY_ENTRY')
        for kind, relative in value['current'].items():
            parts = relative.split('/')
            self.check(len(parts) == 3 and parts[0] == 'state' and
                       parts[2] == {'graph': 'graph.json', 'plan': 'plan.json', 'layouts': 'layouts.json'}[kind] and
                       str(uuid.UUID(parts[1])) == parts[1] and relative in value['files'], 'CURRENT_FILE')
        if value['role'] in ('ready', 'lens'):self.check('plan' not in value['current'], 'PAPER_NO_WORK_HISTORY')
        if value['role']=='lens':self.check(isinstance(value.get('lensKey'),str) and bool(value['lensKey'].strip()),'LENS_KEY_REQUIRED')
        receipt = value['receipt']
        self.check(isinstance(receipt, dict) and set(receipt) == {'path', 'sha256'} and
                   receipt['path'] == '.rdg/receipts/' + value['lastTransactionId'] + '.json' and
                   bool(re.fullmatch('[0-9a-f]{64}', receipt['sha256'])), 'RECEIPT_REF')
        if value.get('previousHead'):
            previous = value['previousHead']
            self.check(set(previous) == {'path', 'sha256'} and previous['path'] in value['files'] and
                       value['files'][previous['path']] == previous['sha256'] and
                       previous['path'].startswith('history/heads/'), 'HISTORY_HEAD_REF')
        return value

    def scan(self):
        """Metadata discovery. Authorization/filtering precedes payload reads in the application."""
        if not self.root.exists():return []
        self.initialized()
        rows = []
        pending = [self.root]
        while pending:
            directory = pending.pop()
            self.check(not directory.is_symlink(), 'SYMLINK_DISCOVERY')
            head_path = directory / 'package.json'
            own_marker = directory / '.rdg/package.json'
            if directory != self.root and (head_path.is_file() or own_marker.is_file()):
                relative = directory.relative_to(self.root).as_posix()
                try:
                    self.io.safe_path(self.root, relative)
                    if not head_path.is_file():
                        marker = json.loads(own_marker.read_bytes())
                        created=marker.get('creationTransactionId');unaccepted=False
                        if created and self.initialized():
                            unaccepted=(self.metadata_path('intents',created).is_file() and not self.metadata_path('accepted',created).exists()
                                and not self.metadata_path('completed',created).exists() and str(uuid.uuid5(uuid.UUID(created),'package'))==marker.get('packageId'))
                        rows.append({'path': relative, 'packageId': marker.get('packageId'), 'health': 'unaccepted-stage' if unaccepted else 'incomplete',
                                     'error': 'NOT_ACCEPTED_STAGE' if unaccepted else 'HEAD_MISSING'})
                        continue
                    raw = head_path.read_bytes();head = json.loads(raw)
                    if head.get('kind') != 'rdgGraphPackage':
                        self.check(not own_marker.exists(), 'FORMAT')
                        pending.extend(child for child in sorted(directory.iterdir(), reverse=True)
                                       if child.is_dir() and not child.name.startswith('.') and not child.is_symlink())
                        continue
                    self.validate_head(head)
                    if own_marker.is_file():
                        self.check(json.loads(own_marker.read_bytes()).get('packageId') == head['packageId'], 'PACKAGE_MARKER_IDENTITY')
                    rows.append({'path': relative, 'packageId': head['packageId'], 'head': head,
                                 'headBytes': raw, 'headSHA256': self.sha(raw), 'health': 'metadata-verified'})
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    try:marker_id = json.loads(own_marker.read_bytes()).get('packageId') if own_marker.is_file() else None
                    except (ValueError, OSError, TypeError, AttributeError):marker_id = None
                    rows.append({'path': relative, 'packageId': marker_id, 'health': 'invalid', 'error': str(exc)})
                continue
            for child in sorted(directory.iterdir(), reverse=True):
                if child.is_symlink():
                    rows.append({'path': child.relative_to(self.root).as_posix(), 'packageId': None,
                                 'health': 'invalid', 'error': 'SYMLINK_DISCOVERY'})
                elif child.is_dir() and not child.name.startswith('.'):
                    pending.append(child)
        identities = {}
        for row in rows:
            if row.get('head'):
                identities.setdefault(('package', row['packageId']), []).append(row)
                identities.setdefault(('space', row['head']['identitySpace']), []).append(row)
                if row['head']['role']=='lens':identities.setdefault(('lensKey',row['head']['lensKey']),[]).append(row)
        for key, same in identities.items():
            if len(same) > 1:
                for row in same:row.update(health='identity-conflict', error='DUPLICATE_' + key[0].upper())
        for path in sorted(self.path('.rdg/transfers',True).glob('*.json')):
            path=self.io.safe_path(self.root,path.relative_to(self.root).as_posix(),True)
            record=json.loads(path.read_bytes())
            self.check(record.get('kind')=='rdgFilesystemTransfer','TRANSFER_JOURNAL_INVALID')
            if record['state']=='completed':continue
            moving={p['packageId'] for p in record['packages']}
            for row in rows:
                if row.get('packageId') in moving:row.update(health='recovery-required',error='MOVE_RECOVERY_REQUIRED:'+record['transactionId'])
        return rows

    def catalog_signature(self, ignore_ids=()):
        ignored=set(ignore_ids)
        rows=[{k:r.get(k) for k in ('packageId','path','health','headSHA256','error')}
              for r in self.scan() if r.get('packageId') not in ignored]
        rows.sort(key=lambda r:r['path'])
        return {'sha256':self.codec.digest(rows),'ignoreIds':sorted(ignored)}

    def folders(self):
        if not self.root.is_dir():return []
        packages={r['path'] for r in self.scan()};result=[];pending=[self.root]
        while pending:
            directory=pending.pop()
            for child in directory.iterdir():
                if child.name.startswith('.') or child.is_symlink() or not child.is_dir():continue
                relative=child.relative_to(self.root).as_posix()
                if relative in packages:continue
                self.path(relative);result.append(relative);pending.append(child)
        return sorted(result)

    def locate(self, package_id, allow_incomplete=False):
        rows = [row for row in self.scan() if row.get('packageId') == package_id]
        self.check(len(rows) == 1, 'NOT_FOUND' if not rows else 'DUPLICATE_IDENTITY')
        row = rows[0]
        self.check(row['health'] == 'metadata-verified' or allow_incomplete and row['health'] == 'incomplete',
                   row.get('error', 'UNHEALTHY'))
        return row

    def _pending_check(self, row):
        directory=self.package_path(row['path'])
        for marker in sorted((directory/'.rdg/move-pending').glob('*.json')):
            marker=self.io.safe_path(directory,marker.relative_to(directory).as_posix(),True)
            value=json.loads(marker.read_bytes());proof=directory/'.rdg/moves'/marker.name
            proof=self.io.safe_path(directory,proof.relative_to(directory).as_posix(),True)
            if not proof.is_file():raise RecoveryRequired('PACKAGE_MOVE_RECOVERY_REQUIRED:'+value['transactionId'])
            witness=json.loads(proof.read_bytes())
            self.check(witness.get('packageId')==row['packageId'] and witness.get('requestSHA256')==value.get('requestSHA256') and
                       witness.get('transactionId')==value['transactionId'] and witness.get('published') is True,'MOVE_COMPLETION_WITNESS')
        directory=self.package_path(row['path'])
        for path in (directory/'.rdg/pending').glob('*.json'):
            self.check(not path.is_symlink(),'SYMLINK_PENDING')
            marker=json.loads(path.read_bytes());tx=marker['transactionId']
            committed=directory/'.rdg/commits'/(tx+'.json')
            finalized=directory/'.rdg/completed'/(tx+'.json')
            own_complete=(self.io.file_sha(committed)==marker['commitSHA256'] and
                          self.io.file_sha(finalized)==marker['completedSHA256'])
            accepted=self.metadata_path('accepted',tx)
            if own_complete and (not accepted.is_file() or self.metadata_path('completed',tx).is_file()):continue
            if accepted.is_file():
                certificate=json.loads(accepted.read_bytes())
                self.check(certificate['requestSHA256']==marker['requestSHA256'],'PENDING_CERTIFICATE_MISMATCH')
                participant=any(e.get('packageId')==marker['packageId'] and e['afterSHA256']==marker['afterSHA256'] for e in certificate['entries'])
                if not participant:
                    self.check(row['headSHA256']!=marker['afterSHA256'],'ORPHAN_PREPARED_HEAD')
                    continue
                raise RecoveryRequired('PACKAGE_RECOVERY_REQUIRED:'+tx)
            if row['headSHA256']==marker['afterSHA256'] or not self.initialized():
                raise RecoveryRequired('PACKAGE_COORDINATOR_COMPLETION_UNAVAILABLE:'+tx)

    def read(self, package_id, include_plan=True, include_layouts=True, include_graph=True, *, on_located=None):
        row = self.locate(package_id)
        # The Application authorizes the verified metadata before payload IO.
        # Using the same located row avoids a second namespace-wide scan;
        # all pending, hash, witness and head-change checks still run below.
        if on_located is not None:on_located(row)
        self._pending_check(row)
        head = row['head'];directory = self.package_path(row['path']);result = dict(row)
        for kind in ('graph', 'plan', 'layouts'):
            if kind not in head['current'] or kind == 'plan' and not include_plan or kind == 'layouts' and not include_layouts or kind == 'graph' and not include_graph:
                result[kind] = None
                continue
            relative = head['current'][kind];path = self.io.safe_path(directory, relative, True)
            raw = path.read_bytes()
            self.check(self.sha(raw) == head['files'][relative], 'CURRENT_HASH_MISMATCH:' + kind)
            result[kind] = json.loads(raw)
        receipt = self.io.safe_path(directory, head['receipt']['path'], True)
        self.check(self.io.file_sha(receipt) == head['receipt']['sha256'], 'COMMIT_RECEIPT_MISSING_OR_CORRUPT')
        result['receiptValue'] = json.loads(receipt.read_bytes())
        self.check(result['receiptValue']['packageId'] == package_id and
                   result['receiptValue']['packageRevision'] == head['revision'] and
                   result['receiptValue']['transactionId'] == head['lastTransactionId'], 'COMMIT_RECEIPT_IDENTITY')
        commit_path = directory / '.rdg/commits' / (head['lastTransactionId'] + '.json')
        self.check(commit_path.is_file() and not commit_path.is_symlink(), 'COMMIT_WITNESS_MISSING')
        witness = json.loads(commit_path.read_bytes())
        self.check(witness['headSHA256'] == row['headSHA256'] and witness['packageId'] == package_id and
                   witness['requestSHA256'] == result['receiptValue']['requestSHA256'], 'COMMIT_WITNESS_MISMATCH')
        self.check((directory / 'package.json').read_bytes() == row['headBytes'], 'HEAD_CHANGED_DURING_READ')
        completion=directory/'.rdg/completed'/(head['lastTransactionId']+'.json')
        if not completion.is_file():raise RecoveryRequired('PACKAGE_COMPLETION_WITNESS_MISSING')
        self.check(json.loads(completion.read_bytes())==self._completion_value(head['lastTransactionId'],witness['requestSHA256'],witness['participants']),
                   'COMPLETION_WITNESS_MISMATCH')
        acceptance_path=directory/'.rdg/acceptances'/(head['lastTransactionId']+'.json')
        self.check(acceptance_path.is_file() and not acceptance_path.is_symlink(),'ACCEPTANCE_WITNESS_MISSING')
        acceptance=json.loads(acceptance_path.read_bytes())
        self.check(acceptance.get('transactionId')==head['lastTransactionId'] and acceptance.get('packageId')==package_id and
                   acceptance.get('headSHA256')==row['headSHA256'] and acceptance.get('requestSHA256')==witness['requestSHA256'] and
                   datetime.fromisoformat(acceptance['acceptedAt']).tzinfo is not None,'ACCEPTANCE_WITNESS_MISMATCH')
        result['acceptance']=acceptance
        if result['graph'] is not None:
            self.check(result['graph']['identitySpace'] == head['identitySpace'] and result['graph']['id'] == head['graphId'], 'GRAPH_IDENTITY_MISMATCH')
        return result

    def head_chain(self,row):
        directory=self.package_path(row['path']);head=row['head'];seen=set()
        while True:
            key=self.sha(self.encode(head));self.check(key not in seen,'HISTORY_CYCLE');seen.add(key)
            yield head
            previous=head.get('previousHead')
            if not previous:break
            raw=self.io.safe_path(directory,previous['path'],True).read_bytes()
            self.check(self.sha(raw)==previous['sha256'],'HISTORY_HEAD_HASH_MISMATCH')
            head=json.loads(raw);self.validate_head(head)

    def inventory(self,row):
        directory=self.package_path(row['path']);inventory={}
        for head in self.head_chain(row):
            for relative,sha in head['files'].items():
                if relative in inventory:self.check(inventory[relative]==sha,'INVENTORY_HASH_CONFLICT')
                inventory[relative]=sha
            inventory[head['receipt']['path']]=head['receipt']['sha256']
            for category in ('commits','completed','acceptances'):
                path='.rdg/'+category+'/'+head['lastTransactionId']+'.json'
                sha=self.io.file_sha(self.io.safe_path(directory,path,True))
                self.check(sha is not None,'HISTORY_COMMIT_WITNESS_MISSING');inventory[path]=sha
        for category in ('moves','move-pending'):
            for file in (directory/'.rdg'/category).glob('*.json'):
                self.check(not file.is_symlink(),'SYMLINK_MOVE_WITNESS')
                inventory[file.relative_to(directory).as_posix()]=self.io.file_sha(file)
        for relative,sha in inventory.items():
            self.check(self.io.file_sha(self.io.safe_path(directory,relative,True))==sha,'INVENTORY_BYTES_MISSING:'+relative)
        return inventory

    def find_artifact(self,row,sha256,suffix=None,prefix=None):
        directory=self.package_path(row['path']);seen=set()
        for head in self.head_chain(row):
            for relative,sha in head['files'].items():
                if relative in seen or sha!=sha256 or suffix and not relative.endswith(suffix) or prefix and not relative.startswith(prefix):continue
                seen.add(relative);raw=self.io.safe_path(directory,relative,True).read_bytes()
                self.check(self.sha(raw)==sha256,'ARTIFACT_HASH_MISMATCH')
                return relative,raw
        return None

    def historical_graph(self,package_id,identity_space,revision=None,sha256=None):
        row=self.read(package_id,include_plan=False,include_layouts=False);directory=self.package_path(row['path'])
        for head in self.head_chain(row):
            relative=head['current']['graph'];raw=self.io.safe_path(directory,relative,True).read_bytes()
            self.check(self.sha(raw)==head['files'][relative],'HISTORICAL_GRAPH_HASH');graph=json.loads(raw)
            if graph['identitySpace']==identity_space and (revision is None or graph['revision']==revision) and (sha256 is None or self.codec.digest(graph)==sha256):return graph
        raise ValueError('PACKAGE_HISTORICAL_SNAPSHOT_UNAVAILABLE')

    def public_authorization_context(self, value):
        result = copy.deepcopy(value)
        for role in ('initiator', 'executor'):
            result[role].pop('tokenSHA256', None)
        return result

    def validate_authorization_context(self, value, transaction_id, request_sha, token_sha=None):
        """Internal writer contract, not a client-supplied authorization API."""
        self.check(isinstance(value, dict) and set(value) == {
            'schemaVersion', 'kind', 'namespaceId', 'requestId', 'requestSHA256',
            'initiator', 'approver', 'executor', 'previewSHA256', 'inputBindingSHA256'} and
            value['schemaVersion'] == 1 and value['kind'] == 'rdgExactApproval' and
            value['namespaceId'] == self.namespace_id and value['requestId'] == transaction_id and
            value['requestSHA256'] == request_sha, 'APPROVAL_CONTEXT')
        fields = {'initiator': {'grantId', 'attribution', 'tokenSHA256'},
                  'executor': {'grantId', 'tokenSHA256', 'authorityPrincipal'},
                  'approver': {'principalId', 'credentialId', 'origin', 'rpId',
                               'proofSHA256', 'userVerified'}}
        for role, names in fields.items():
            self.check(isinstance(value[role], dict) and set(value[role]) == names,
                       'APPROVAL_CONTEXT')
            for name, item in value[role].items():
                self.check(item is True if name == 'userVerified' else
                           isinstance(item, str) and bool(item.strip()), 'APPROVAL_CONTEXT')
        self.check(value['initiator']['attribution'] in ('assistant', 'user'),
                   'APPROVAL_CONTEXT')
        for digest in (request_sha, value['previewSHA256'], value['inputBindingSHA256'],
                       value['initiator']['tokenSHA256'], value['executor']['tokenSHA256'],
                       value['approver']['proofSHA256']):
            self.check(isinstance(digest, str) and len(digest) == 64 and
                       all(c in '0123456789abcdef' for c in digest), 'APPROVAL_CONTEXT')
        if token_sha is not None:
            self.check(value['executor']['tokenSHA256'] == token_sha, 'APPROVAL_EXECUTOR_MISMATCH')
            self.check(self.check_intent(transaction_id, request_sha,
                                        value['initiator']['tokenSHA256']), 'APPROVAL_INTENT_REQUIRED')
            pending_path = self.metadata_path('approval-requests', transaction_id)
            self.check(pending_path.is_file(), 'APPROVAL_PENDING_REQUIRED')
            pending = json.loads(pending_path.read_bytes())
            self.check(pending.get('requestSHA256') == request_sha and
                       pending.get('namespaceId') == self.namespace_id and
                       pending.get('actorTokenSHA256') == value['initiator']['tokenSHA256'] and
                       pending.get('initiator') == {k: v for k, v in value['initiator'].items()
                                                   if k != 'tokenSHA256'}, 'APPROVAL_INITIATOR_MISMATCH')

    def transaction_actor(self, certificate, token_sha):
        if certificate.get('schemaVersion') == 2:
            value = certificate.get('authorizationContext')
            self.validate_authorization_context(value, certificate['transactionId'],
                                                certificate['requestSHA256'])
            self.check(certificate['actorTokenSHA256'] == value['initiator']['tokenSHA256'],
                       'APPROVAL_INITIATOR_MISMATCH')
            return token_sha in (value['initiator']['tokenSHA256'],
                                 value['executor']['tokenSHA256'])
        self.check(certificate.get('schemaVersion') == 1 and
                   'authorizationContext' not in certificate, 'CERTIFICATE_VERSION')
        return certificate['actorTokenSHA256'] == token_sha

    def reserve_intent(self, transaction_id, request_sha, token_sha):
        """Caller holds the reference barrier and has authorized this metadata write."""
        if self.check_intent(transaction_id, request_sha, token_sha):
            return
        self.io.immutable_bytes(self.metadata_path('intents', transaction_id), self.encode({
            'transactionId': transaction_id, 'requestSHA256': request_sha,
            'actorTokenSHA256': token_sha}))

    def check_intent(self,transaction_id,request_sha,token_sha):
        path=self.metadata_path('intents',transaction_id)
        self.check(not self.metadata_path('approval-decisions', transaction_id).exists(),
                   'TRANSACTION_REJECTED')
        if not path.is_file():return False
        value=json.loads(path.read_bytes())
        self.check(value['requestSHA256']==request_sha,'TRANSACTION_ID_CONFLICT')
        self.check(value['actorTokenSHA256']==token_sha,'TRANSACTION_ACTOR_MISMATCH')
        return True

    def validate_destination(self,relative):
        directory=self.package_path(relative)
        for parent in directory.parents:
            if parent==self.root:break
            own=parent/'.rdg/package.json';manifest=parent/'package.json'
            self.check(not own.exists() and (not manifest.is_file() or
                json.loads(manifest.read_bytes()).get('kind')!='rdgGraphPackage'),'DESTINATION_INSIDE_PACKAGE')
        return directory

    def registry_key(self):return 'registry:'+self.namespace_id

    def entry_owner(self,entry):
        return entry.get('owner') or {'kind':'package','namespaceId':self.namespace_id,'packageId':entry['packageId']}

    def entry_directory(self,entry):
        return self.path('.rdg/recommendations',True) if entry.get('owner',{}).get('kind')=='recommendationRegistry' else self.package_path(entry['path'])

    def entry_head_path(self,entry):
        return self.entry_directory(entry)/('head.json' if entry.get('owner',{}).get('kind')=='recommendationRegistry' else 'package.json')

    def registry_read(self):
        directory=self.path('.rdg/recommendations',True);path=directory/'head.json'
        # The namespace barrier serializes all participants; accepted registry
        # publication is never returned as a healthy half transaction.
        for accepted in self.path('.rdg/accepted',True).glob('*.json'):
            value=json.loads(accepted.read_bytes())
            if any(e.get('owner',{}).get('kind')=='recommendationRegistry' for e in value['entries']):
                if not self.metadata_path('completed',value['transactionId']).is_file():
                    raise RecoveryRequired('PACKAGE_REGISTRY_RECOVERY_REQUIRED:'+value['transactionId'])
        if not path.is_file():return {'ownerKey':self.registry_key(),'path':'.rdg/recommendations','headSHA256':None,'head':None,'registry':None}
        raw=self.io.safe_path(directory,'head.json',True).read_bytes();head=json.loads(raw)
        self.check(head.get('kind')=='rdgRecommendationRegistryHead' and head.get('namespaceId')==self.namespace_id,'REGISTRY_HEAD')
        artifact=self.io.safe_path(directory,head['artifact'],True);data=artifact.read_bytes()
        self.check(self.sha(data)==head['sha256'],'REGISTRY_ARTIFACT_HASH')
        tx=head['lastTransactionId'];completed=directory/'.rdg/completed'/(tx+'.json')
        if not completed.is_file():raise RecoveryRequired('PACKAGE_REGISTRY_FINALIZATION_REQUIRED:'+tx)
        receipt_path=self.io.safe_path(directory,head['receipt']['path'],True)
        self.check(self.io.file_sha(receipt_path)==head['receipt']['sha256'],'REGISTRY_RECEIPT_HASH')
        commit=json.loads((directory/'.rdg/commits'/(tx+'.json')).read_bytes())
        self.check(commit['headSHA256']==self.sha(raw),'REGISTRY_COMMIT_WITNESS')
        return {'ownerKey':self.registry_key(),'path':'.rdg/recommendations','headSHA256':self.sha(raw),
                'head':head,'registry':json.loads(data),'receiptValue':json.loads(receipt_path.read_bytes())}

    def _prepare_registry_entry(self,transaction_id,request_sha,change,authorization_context):
        before=change['before'];value=change['registry'];raw=self.encode(value);sha=self.sha(raw)
        owner={'kind':'recommendationRegistry','namespaceId':self.namespace_id}
        receipt={'schemaVersion':1,'kind':'rdgRegistryReceipt','transactionId':transaction_id,'requestSHA256':request_sha,
                 'owner':owner,'revision':value['revision'],'effects':copy.deepcopy(change.get('effects',{}))}
        if authorization_context is not None:receipt.update(schemaVersion=2,authorizationContext=self.public_authorization_context(authorization_context))
        rb=self.encode(receipt);rp='.rdg/receipts/'+transaction_id+'.json';artifact='versions/'+sha+'.json'
        head={'schemaVersion':1,'kind':'rdgRecommendationRegistryHead','namespaceId':self.namespace_id,
              'revision':value['revision'],'artifact':artifact,'sha256':sha,'files':{artifact:sha},
              'lastTransactionId':transaction_id,'receipt':{'path':rp,'sha256':self.sha(rb)}}
        return {'owner':owner,'path':'.rdg/recommendations','beforeSHA256':before['headSHA256'],
            'afterSHA256':self.sha(self.encode(head)),'afterHead':head,'artifacts':{artifact:base64.b64encode(raw).decode('ascii')},
            'receipt':{'path':rp,'bytes':base64.b64encode(rb).decode('ascii')},'permissions':change['permissions']}

    def _prepare_entry(self, transaction_id, request_sha, package_id, change, authorization_context=None):
        if package_id==self.registry_key():return self._prepare_registry_entry(transaction_id,request_sha,change,authorization_context)
        before = change.get('before');relative = change['path'];directory = self.package_path(relative)
        if before:
            self.check(before['packageId'] == package_id and before['path'] == relative, 'BEFORE_OWNER_MISMATCH')
        else:
            self.validate_destination(relative)
            self.check(not any(row.get('packageId')==package_id and
                (row['path']!=relative or row['health'] not in ('incomplete','unaccepted-stage')) for row in self.scan()),'CREATE_IDENTITY_EXISTS')
            marker = directory / '.rdg/package.json'
            staged_retry = (marker.is_file() and not (directory / 'package.json').exists() and
                            json.loads(marker.read_bytes()).get('packageId') == package_id)
            self.check(not directory.exists() or directory.is_dir() and not any(directory.iterdir()) or staged_retry,
                       'DESTINATION_EXISTS')
        material={'beforeSHA256':before['headSHA256'] if before else None,
                  'state':{k:change[k] for k in ('graph','plan','layouts','role','lineage','lensKey','effects') if k in change},
                  'artifacts':{k:self.sha(v) for k,v in change.get('artifacts',{}).items()}}
        generation=str(uuid.uuid5(uuid.UUID(transaction_id),package_id+':'+self.codec.digest(material)))
        graph = change.get('graph');role = change.get('role', before['head']['role'] if before else None)
        self.check(graph is not None or before is not None, 'CREATE_GRAPH_REQUIRED')
        files = {};artifacts = {}
        def add(relative_file, payload):
            self.io.safe_path(directory, relative_file, True)
            files[relative_file] = self.sha(payload);artifacts[relative_file] = base64.b64encode(payload).decode('ascii')
        current = {}
        for kind in ('graph', 'plan', 'layouts'):
            if kind not in change:
                if before and kind in before['head']['current']:
                    relative_file = before['head']['current'][kind]
                    sha = before['head']['files'][relative_file]
                    self.check(self.io.file_sha(self.io.safe_path(directory, relative_file, True)) == sha, 'REUSED_BYTES_CORRUPT')
                    current[kind] = relative_file;files[relative_file] = sha
                continue
            value = change[kind]
            if value is None:continue
            relative_file = 'state/' + generation + '/' + {'graph': 'graph.json', 'plan': 'plan.json', 'layouts': 'layouts.json'}[kind]
            add(relative_file, self.encode(value));current[kind] = relative_file
        for relative_file, payload in change.get('artifacts', {}).items():add(relative_file, payload)
        receipt = {'schemaVersion': 1, 'kind': 'rdgPackageReceipt', 'transactionId': transaction_id,
                   'requestSHA256': request_sha, 'packageId': package_id,
                   'packageRevision': before['head']['revision'] + 1 if before else 1,
                   'graphRevision': graph['revision'] if graph is not None else before['receiptValue']['graphRevision'],
                   'planRevision': change.get('plan', before['receiptValue'].get('planRevision') if before else None),
                   'effects': copy.deepcopy(change.get('effects', {}))}
        if isinstance(receipt['planRevision'], dict):receipt['planRevision'] = receipt['planRevision']['revision']
        if authorization_context is not None:
            receipt.update(schemaVersion=2, authorizationContext=self.public_authorization_context(authorization_context))
        receipt_bytes = self.encode(receipt);receipt_path = '.rdg/receipts/' + transaction_id + '.json'
        head = {'schemaVersion': 1, 'kind': 'rdgGraphPackage', 'packageId': package_id, 'namespaceId': self.namespace_id,
                'role': role, 'identitySpace': graph['identitySpace'] if graph is not None else before['head']['identitySpace'],
                'graphId': graph['id'] if graph is not None else before['head']['graphId'],
                'revision': receipt['packageRevision'], 'generation': generation, 'current': current,
                'files': files, 'lastTransactionId': transaction_id,
                'receipt': {'path': receipt_path, 'sha256': self.sha(receipt_bytes)}}
        if before:
            old_bytes = before['headBytes'];sha = self.sha(old_bytes);path = 'history/heads/' + sha + '.json'
            add(path, old_bytes);head['previousHead'] = {'path': path, 'sha256': sha}
        for field in ('lineage', 'lensKey'):
            value = change.get(field, before['head'].get(field) if before else None)
            if value is not None:head[field] = copy.deepcopy(value)
        self.validate_head(head);after_bytes = self.encode(head)
        return {'packageId': package_id, 'path': relative, 'beforeSHA256': before['headSHA256'] if before else None,
                'afterSHA256': self.sha(after_bytes), 'afterHead': head, 'artifacts': artifacts,
                'receipt': {'path': receipt_path, 'bytes': base64.b64encode(receipt_bytes).decode('ascii')},
                'permissions': change['permissions']}

    def _verify_before(self, entry):
        path = self.entry_head_path(entry)
        self.check(self.io.file_sha(path) == entry['beforeSHA256'], 'CAS_CONFLICT')

    def _write_artifacts(self, entry):
        directory = self.entry_directory(entry);self.io.mkdirs(directory)
        path=self.io.safe_path(directory,'.rdg/package.json',True)
        if entry.get('owner',{}).get('kind')=='recommendationRegistry':
            for relative,data in entry['artifacts'].items():
                raw=base64.b64decode(data,validate=True)
                self.check(self.sha(raw)==entry['afterHead']['files'][relative],'STAGED_BYTES_DIGEST')
                self.io.immutable_bytes(self.io.safe_path(directory,relative,True),raw)
            return
        if path.exists():self.check(json.loads(path.read_bytes()).get('packageId')==entry['packageId'],'PACKAGE_MARKER_IDENTITY')
        else:
            marker = self.encode({'schemaVersion': 1, 'kind': 'rdgPackageIdentity', 'packageId': entry['packageId'],
                                 'creationTransactionId':entry['afterHead']['lastTransactionId']})
            self.io.immutable_bytes(path,marker)
        for relative, data in entry['artifacts'].items():
            payload = base64.b64decode(data, validate=True)
            self.check(self.sha(payload) == entry['afterHead']['files'][relative], 'STAGED_BYTES_DIGEST')
            self.io.immutable_bytes(self.io.safe_path(directory, relative, True), payload)

    def _load_payload(self, transaction_id, certificate):
        path = self.metadata_path('staged', transaction_id);raw = path.read_bytes()
        self.check(self.sha(raw) == certificate['payloadSHA256'], 'RECOVERY_PAYLOAD_HASH')
        payload = json.loads(raw)
        self.check(payload['requestSHA256'] == certificate['requestSHA256'] and payload['transactionId'] == transaction_id,
                   'RECOVERY_INTENT_MISMATCH')
        if certificate.get('schemaVersion') == 2:
            context = certificate['authorizationContext']
            self.validate_authorization_context(context, transaction_id, certificate['requestSHA256'])
            for entry in payload['entries']:
                receipt = json.loads(base64.b64decode(entry['receipt']['bytes']))
                self.check(receipt.get('schemaVersion') == 2 and receipt.get('authorizationContext') ==
                           self.public_authorization_context(context), 'RECOVERY_APPROVAL_CONTEXT')
        return payload

    def _publish(self, transaction_id, certificate, failpoint=None):
        payload = self._load_payload(transaction_id, certificate)
        for i, entry in enumerate(payload['entries']):
            # Locate identity after a safe manual rename within this namespace.
            current_path = self.entry_head_path(entry)
            if not current_path.exists() and 'packageId' in entry:
                found = self.locate(entry['packageId'], allow_incomplete=True)
                self.check(found['path'] == entry['path'], 'RECOVERY_PATH_CHANGED')
            current_sha = self.io.file_sha(current_path)
            self.check(current_sha in (entry['beforeSHA256'], entry['afterSHA256']), 'RECOVERY_HEAD_CONFLICT')
            self._write_artifacts(entry)
            if current_sha != entry['afterSHA256']:
                self.io.atomic_bytes(current_path, self.encode(entry['afterHead']))
            if failpoint:failpoint('head:' + str(i + 1))
        if failpoint:failpoint('heads')
        result=self._completion_value(transaction_id,certificate['requestSHA256'],payload['entries'])
        for i,entry in enumerate(payload['entries']):
            directory=self.entry_directory(entry)
            self.io.immutable_bytes(self.io.safe_path(directory,entry['receipt']['path'],True),base64.b64decode(entry['receipt']['bytes'],validate=True))
            self.io.immutable_bytes(self.io.safe_path(directory,'.rdg/commits/'+transaction_id+'.json',True),self.encode(entry['commit']))
            if failpoint:failpoint('witness:'+str(i+1))
        self.io.atomic_bytes(self.metadata_path('completed',transaction_id),self.encode(result))
        if failpoint:failpoint('completed')
        self._finalize(payload,result,certificate,failpoint)
        return self._result(payload, False)

    def _completion_value(self,transaction_id,request_sha,entries):
        return {'schemaVersion':1,'state':'completed','transactionId':transaction_id,'requestSHA256':request_sha,
                'packageIds':[e['packageId'] for e in entries if 'packageId' in e],
                **({'owners':[self.entry_owner(e) for e in entries]} if any('owner' in e for e in entries) else {})}

    def _finalize(self,payload,result,certificate,failpoint=None):
        for i,entry in enumerate(payload['entries']):
            directory=self.entry_directory(entry)
            if 'owner' in entry:
                acceptance={'schemaVersion':1,'transactionId':payload['transactionId'],'requestSHA256':payload['requestSHA256'],
                    'owner':entry['owner'],'headSHA256':entry['afterSHA256'],'acceptedAt':certificate['acceptedAt']}
                self.io.immutable_bytes(self.io.safe_path(directory,'.rdg/acceptances/'+payload['transactionId']+'.json',True),self.encode(acceptance))
                self.io.immutable_bytes(self.io.safe_path(directory,'.rdg/completed/'+payload['transactionId']+'.json',True),self.encode(result))
                if failpoint:failpoint('finalized:'+str(i+1))
                continue
            acceptance={'schemaVersion':1,'transactionId':payload['transactionId'],
                'requestSHA256':payload['requestSHA256'],'packageId':entry['packageId'],
                'headSHA256':entry['afterSHA256'],'acceptedAt':certificate['acceptedAt']}
            acceptance_path='.rdg/acceptances/'+payload['transactionId']+'.json'
            marker=directory/'.rdg/package.json'
            if not marker.is_file() or json.loads(marker.read_bytes()).get('packageId')!=entry['packageId']:
                found=self.locate(entry['packageId']);directory=self.package_path(found['path'])
                self.check(self.io.file_sha(directory/'.rdg/completed'/(payload['transactionId']+'.json'))==self.sha(self.encode(result)),
                           'RECOVERY_PATH_CHANGED')
                self.check(self.io.file_sha(self.io.safe_path(directory,acceptance_path,True))==self.sha(self.encode(acceptance)),
                           'HISTORICAL_ACCEPTANCE_MISSING_OR_CORRUPT')
                continue
            self.io.immutable_bytes(self.io.safe_path(directory,acceptance_path,True),self.encode(acceptance))
            self.io.immutable_bytes(self.io.safe_path(directory,'.rdg/completed/'+payload['transactionId']+'.json',True),self.encode(result))
            if failpoint:failpoint('finalized:'+str(i+1))

    def _result(self, payload, idempotent):
        payload=copy.deepcopy(payload)
        payload['entries'].sort(key=lambda e: e.get('packageId')!=json.loads(base64.b64decode(e['receipt']['bytes'])).get('effects',{}).get('createdPackageId'))
        return {'transactionId': payload['transactionId'], 'requestSHA256': payload['requestSHA256'],
                'accepted': True, 'published': True, 'recovery_required': False, 'idempotent': idempotent,
                'packages': [{'packageId': e['packageId'], 'path': None if idempotent else e['path'], 'acceptedPath': e['path'],
                              'revision': e['afterHead']['revision'],
                              'receipt': json.loads(base64.b64decode(e['receipt']['bytes']))} for e in payload['entries'] if 'packageId' in e],
                'participants':[{'owner':self.entry_owner(e),'revision':e['afterHead']['revision'],
                    'sha256':e['afterSHA256'],'receipt':json.loads(base64.b64decode(e['receipt']['bytes']))} for e in payload['entries']]}

    def replay(self, transaction_id, request_sha, token_sha):
        accepted = self.metadata_path('accepted', transaction_id)
        if not accepted.is_file():return None
        certificate = json.loads(accepted.read_bytes())
        self.check(certificate['requestSHA256'] == request_sha, 'TRANSACTION_ID_CONFLICT')
        self.check(self.transaction_actor(certificate, token_sha), 'TRANSACTION_ACTOR_MISMATCH')
        payload = self._load_payload(transaction_id, certificate)
        if self.metadata_path('completed', transaction_id).is_file():
            # Complete self-contained finalization without reverting a later valid head.
            result=json.loads(self.metadata_path('completed',transaction_id).read_bytes())
            self.check(result==self._completion_value(transaction_id,request_sha,payload['entries']),'COMPLETION_CERTIFICATE')
            self._finalize(payload,result,certificate)
            return self._result(payload, True)
        result = self._publish(transaction_id, certificate);result['idempotent'] = True
        for row in result['packages']:row['path'] = None
        return result

    def commit(self, transaction_id, request_sha, changes, token_sha, preauthorize, final_authorize,
               expected_reads, failpoint=None, *, expected_catalog=None, authorization_context=None):
        """Caller holds the global reference barrier and supplies the same pure effects.

        preauthorize happens before any staging; final_authorize holds the grant
        lock through acceptance/publication. New destinations need explicit create
        permissions, and every affected Plan needs separate edit permission.
        """
        replayed = self.replay(transaction_id, request_sha, token_sha)
        if replayed:return replayed
        preauthorize()
        self.initialize()
        if authorization_context is not None:
            authorization_context = copy.deepcopy(authorization_context)
            self.validate_authorization_context(authorization_context, transaction_id, request_sha, token_sha)
        intent_actor = authorization_context['initiator']['tokenSHA256'] if authorization_context else token_sha
        self.reserve_intent(transaction_id,request_sha,intent_actor)
        entries = [self._prepare_entry(transaction_id, request_sha, key, change, authorization_context)
                   for key, change in sorted(changes.items())]
        for entry in entries:self._verify_before(entry)
        for entry in entries:self._write_artifacts(entry)
        if failpoint:failpoint('staged')
        with final_authorize() as verified:
            if expected_catalog is not None:
                self.check(self.catalog_signature(expected_catalog['ignoreIds']) == expected_catalog,
                           'INCOMING_CATALOG_CHANGED')
            for package_id, before_sha in expected_reads.items():
                current = self.registry_read() if package_id==self.registry_key() else self.locate(package_id)
                self.check(current['headSHA256'] == before_sha, 'READ_SET_CONFLICT')
            for entry in entries:self._verify_before(entry)
            participants = [{**({'packageId':e['packageId']} if 'packageId' in e else {'owner':e['owner']}),'afterSHA256':e['afterSHA256']} for e in entries]
            for entry in entries:
                entry['commit'] = {'schemaVersion': 1, 'state': 'completed', 'transactionId': transaction_id,
                                   'requestSHA256': request_sha, **({'packageId':entry['packageId']} if 'packageId' in entry else {'owner':entry['owner']}),
                                   'headSHA256': entry['afterSHA256'], 'participants': participants}
                marker = {'schemaVersion': 1, 'transactionId': transaction_id, 'requestSHA256': request_sha,
                          **({'packageId':entry['packageId']} if 'packageId' in entry else {'owner':entry['owner']}), 'afterSHA256': entry['afterSHA256'],
                          'commitSHA256': self.sha(self.encode(entry['commit'])),
                          'completedSHA256': self.sha(self.encode(self._completion_value(transaction_id,request_sha,entries)))}
                self.io.atomic_bytes(self.io.safe_path(self.entry_directory(entry), '.rdg/pending/' + transaction_id + '.json', True), self.encode(marker))
            payload = {'schemaVersion': 1, 'transactionId': transaction_id, 'requestSHA256': request_sha, 'entries': entries}
            raw = self.encode(payload)
            self.io.atomic_bytes(self.metadata_path('staged', transaction_id), raw)
            certificate = {'schemaVersion': 1, 'state': 'prepared', 'transactionId': transaction_id,
                           'requestSHA256': request_sha, 'actorTokenSHA256': token_sha,
                           'acceptedAt': datetime.now(timezone.utc).isoformat(), 'authorization': verified,
                           'payloadSHA256': self.sha(raw), 'entries': participants}
            if authorization_context is not None:
                certificate.update(schemaVersion=2, actorTokenSHA256=intent_actor,
                                   authorizationContext=authorization_context)
            self.io.atomic_bytes(self.metadata_path('accepted', transaction_id), self.encode(certificate))
            if failpoint:failpoint('prepared')
            return self._publish(transaction_id, certificate, failpoint)
