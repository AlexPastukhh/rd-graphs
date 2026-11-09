#!/usr/bin/env python3
"""GitHub Contents API adapter with optimistic SHA, isolated one-graph writes.

NO credentials in files. This is NOT a multi-graph transaction, authenticated
human approval, or external-effect runner. Canonical repo/ACL must be provided.
"""
import base64
import copy
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from importlib.machinery import SourceFileLoader
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
apply_lib = SourceFileLoader('rdg_github_apply', str(BASE/'tools/graph-apply.py')).load_module()
trust_lib = SourceFileLoader('rdg_github_trust', str(BASE/'tools/rdg-v6-action-trust.py')).load_module()


def ensure(value, message):
    if not value:
        raise ValueError('GITHUB_STORE_' + message)


class GithubContentsTransport:
    def __init__(self, repository, branch='main', token=None, api='https://api.github.com'):
        ensure(isinstance(repository, str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository),
               'REPOSITORY_REQUIRED')
        ensure(isinstance(branch, str) and branch, 'BRANCH_REQUIRED')
        token = token or os.environ.get('GITHUB_TOKEN')
        ensure(token and len(token) >= 12, 'TOKEN_REQUIRED')
        self.repository, self.branch, self.token = repository, branch, token
        self.api = api.rstrip('/')

    def request(self, method, filename, payload=None):
        quoted = urllib.parse.quote(filename, safe='/')
        url = self.api + '/repos/' + self.repository + '/contents/' + quoted
        if method == 'GET':
            url += '?ref=' + urllib.parse.quote(self.branch, safe='')
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method, headers={
            'Accept':'application/vnd.github+json',
            'Authorization':'Bearer '+self.token,
            'X-GitHub-Api-Version':'2022-11-28',
            'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if method == 'GET' and exc.code == 404:
                return None
            if exc.code in (409, 412, 422):
                raise ValueError('GITHUB_STORE_SHA_CONFLICT_OR_INVALID_WRITE') from exc
            raise ValueError('GITHUB_STORE_HTTP_'+str(exc.code)) from exc

    def list(self, dirname):
        result=self.request('GET',dirname)
        if result is None:
            return []
        ensure(isinstance(result,list), 'EXPECTED_GITHUB_DIRECTORY')
        # GitHub Contents directory listings are capped. Never silently call
        # a partial list 'the latest' when a directory cannot be exhausted.
        ensure(len(result)<1000, 'DIRECTORY_LIST_POSSIBLY_INCOMPLETE')
        return result

    def read(self, filename):
        result=self.request('GET',filename)
        if result is None:
            return None, None
        ensure(result.get('type')=='file' and result.get('encoding')=='base64' and
               isinstance(result.get('sha'),str), 'EXPECTED_GITHUB_FILE')
        return base64.b64decode(result['content']).decode('utf-8'), result['sha']

    def put(self, filename, data, expected_sha, message):
        req={'branch':self.branch,'message':message,
             'content':base64.b64encode(data.encode('utf-8')).decode('ascii')}
        if expected_sha is not None:
            req['sha']=expected_sha
        return self.request('PUT',filename,req)


class GithubGraphStore:
    def __init__(self, transport):
        self.transport=transport

    def commit_graph_package(self, package, expected_blob_sha):
        """Only one already-owned opt-in graph; no cross-graph retirement here."""
        ensure(isinstance(package,dict) and package.get('schemaVersion')==1 and
               isinstance(package.get('transactionId'),str) and
               isinstance(package.get('changes'),list) and len(package['changes'])==1,
               'SINGLE_GRAPH_TRANSACTION_REQUIRED')
        change=package['changes'][0]
        path=change.get('file')
        ensure(isinstance(path,str) and re.fullmatch(r'workspaces/(?:[a-z0-9][a-z0-9_-]*/)+graph\.json',path),
               'INVALID_WORKSPACE_PATH')
        ensure('create' not in change and 'metadata' not in change,'NO_CREATE_OR_OWNER_CHANGE')
        ops=(change.get('patch') or {}).get('operations',[])
        ensure(isinstance(ops,list) and ops,'NO_EMPTY_CHANGES')
        # Refuse any operation needing unknown other-graph dependencies until a
        # full catalog-backed Git transaction can prove safe.
        ensure(not any(op.get('op') in ('reconsider_action',) or
                       (op.get('op')=='graph_edit' and op.get('action') in
                        ('deactivate_requirement','delete_orphan_requirement','detach_requirement'))
                       for op in ops), 'CROSS_GRAPH_SCOPE_UNVERIFIED')
        target='graphs/'+path
        data, actual_sha=self.transport.read(target)
        ensure(actual_sha is not None and actual_sha==expected_blob_sha,'EXPECTED_SHA_MISMATCH')
        graph=json.loads(data)
        apply_lib.validate(graph)
        ensure(graph.get('actionModel')=='candidate-v6' and graph.get('readOnly') is not True,
               'ONLY_WRITABLE_CANDIDATE_V6')
        ensure(trust_lib.need_trust(package) and trust_lib.verify_transaction(package),
               'TRUST_REQUIRED')
        patched=copy.deepcopy(change['patch'])
        for op in patched['operations']:
            if op.get('op') in trust_lib.MATERIAL_OPS:
                proof=package['trustedApproval']
                receipt=op.get('transition') if op['op']=='transition_qrpe' else op.get('event')
                ensure(isinstance(receipt,dict),'RECEIPT_EVENT_MISSING')
                receipt['verifiedTrustReceipt']={
                    'principal':proof['principal'],'purpose':proof['purpose'],
                    'expiresAt':proof['expiresAt'],'signature':proof['signature'],
                    'transactionId':package['transactionId'],
                    'signedChangesSHA256':trust_lib.fingerprint(package['changes'])}
        after,changed=apply_lib.apply(graph,patched,trusted_verified=True)
        ensure(changed,'NO_GRAPH_CHANGE')
        # Re-read pre-commit; PUT with blob SHA still protects a racing writer.
        fresh_sha=self.transport.read(target)[1]
        ensure(fresh_sha==actual_sha,'PRE_COMMIT_SHA_CHANGED')
        result=self.transport.put(target,json.dumps(after,ensure_ascii=False,indent=2)+'\n',actual_sha,
                                  'rdg: '+package['transactionId'])
        written,sha=self.transport.read(target)
        ensure(json.loads(written)==after and sha==result.get('content',{}).get('sha'),
               'COMMIT_READBACK_FAILED')
        return {'commitSHA':result.get('commit',{}).get('sha'),
                'blobSHA':sha,'revision':after['revision'],'path':target}

    def list_research_metadata(self):
        """Read only small per-snapshot sidecars; never load working graphs."""
        found=[]
        for folder in self.transport.list('lens-applications'):
            ensure(isinstance(folder,dict), 'BAD_RESEARCH_DIRECTORY_ENTRY')
            if folder.get('type')!='dir':
                continue
            name=folder.get('name','')
            ensure(re.fullmatch(r'\d{4}-\d{2}-\d{2}',name), 'BAD_RESEARCH_DATE_FOLDER')
            for entry in self.transport.list('lens-applications/'+name):
                path=entry.get('path','')
                if entry.get('type')!='file' or not path.endswith('.metadata.json'):
                    continue
                ensure(re.fullmatch(r'lens-applications/\d{4}-\d{2}-\d{2}/[A-Za-z0-9_-]{10,95}\.metadata\.json',path),
                       'BAD_RESEARCH_METADATA_PATH')
                data, _=self.transport.read(path)
                ensure(data is not None,'RESEARCH_METADATA_MISSING')
                sidecar=json.loads(data)
                ensure(isinstance(sidecar,dict) and isinstance(sidecar.get('metadata'),dict) and
                       isinstance(sidecar.get('researchPath'),str) and
                       sidecar['researchPath']==path.replace('.metadata.json','.json') and
                       isinstance(sidecar.get('researchBlobSHA'),str), 'BAD_RESEARCH_METADATA')
                found.append({**sidecar['metadata'], 'researchPath':sidecar['researchPath'],
                              'researchBlobSHA':sidecar['researchBlobSHA']})
        return found

    def load_research(self, metadata):
        """Explicit on-demand full load after metadata-only relevance check."""
        ensure(isinstance(metadata,dict), 'RESEARCH_METADATA_REQUIRED')
        path=metadata.get('researchPath','')
        ensure(isinstance(path,str) and re.fullmatch(
            r'lens-applications/\d{4}-\d{2}-\d{2}/[A-Za-z0-9_-]{10,95}\.json',path),
            'RESEARCH_PATH_INVALID')
        data,sha=self.transport.read(path)
        ensure(data is not None and sha==metadata.get('researchBlobSHA'),
               'RESEARCH_SHA_MISMATCH')
        loaded=json.loads(data)
        ensure(loaded.get('saved') is True and loaded.get('metadata')=={
            k:v for k,v in metadata.items() if k not in ('researchPath','researchBlobSHA')} and
            isinstance(loaded.get('workingGraph'),dict), 'RESEARCH_METADATA_MISMATCH')
        return loaded

    def save_research(self, captured):
        ensure(isinstance(captured,dict) and captured.get('saved') is True and
               isinstance(captured.get('metadata'),dict) and
               isinstance(captured.get('workingGraph'),dict), 'RESEARCH_NOT_SELECTED')
        date=captured['metadata'].get('recordedAt','')[:10]
        ident=captured.get('id','')
        ensure(re.fullmatch(r'\d{4}-\d{2}-\d{2}',date) and
               re.fullmatch(r'[A-Za-z0-9_-]{10,95}',ident),'RESEARCH_FILE_ID_INVALID')
        target='lens-applications/'+date+'/'+ident+'.json'
        _,prior_sha=self.transport.read(target)
        ensure(prior_sha is None,'RESEARCH_ALREADY_SAVED')
        data=json.dumps(captured,ensure_ascii=False,indent=2)+'\n'
        result=self.transport.put(target,data,None,'rdg: preserve useful Lens research')
        readback,sha=self.transport.read(target)
        ensure(json.loads(readback)==captured and sha==result.get('content',{}).get('sha'),
               'RESEARCH_READBACK_FAILED')
        # A metadata-only sibling is a lightweight discovery surface, not an
        # ever-growing global manifest/secondary history. Write it only after
        # the full research graph is durable. A failure here leaves an orphan
        # snapshot (not a false positive) and must be reported to the caller.
        meta_path=target.replace('.json','.metadata.json')
        _,existing=self.transport.read(meta_path)
        ensure(existing is None,'RESEARCH_METADATA_ALREADY_SAVED')
        sidecar={'metadata':captured['metadata'],'researchPath':target,'researchBlobSHA':sha}
        index_result=self.transport.put(meta_path,json.dumps(sidecar,ensure_ascii=False,indent=2)+'\n',
                                        None,'rdg: index selected Lens research metadata')
        metadata_read,metadata_sha=self.transport.read(meta_path)
        ensure(json.loads(metadata_read)==sidecar and
               metadata_sha==index_result.get('content',{}).get('sha'),
               'RESEARCH_METADATA_READBACK_FAILED')
        return {'path':target,'blobSHA':sha,'commitSHA':result.get('commit',{}).get('sha'),
                'metadataPath':meta_path,'metadataBlobSHA':metadata_sha}
