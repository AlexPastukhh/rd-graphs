#!/usr/bin/env python3
"""Offline fake GitHub Contents transport: never touches user repositories."""
import copy
import hashlib
import json
import os
import time
import hmac
from importlib.machinery import SourceFileLoader
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
store=SourceFileLoader('rdg_github_smoke',str(ROOT/'tools/rdg-github-store.py')).load_module()
trust=SourceFileLoader('rdg_github_smoke_trust',str(ROOT/'tools/rdg-v6-action-trust.py')).load_module()

class MemoryTransport:
    def __init__(self):
        self.files={}
        self.counter=0
        self.read_paths=[]
    def read(self,name):
        self.read_paths.append(name)
        if name not in self.files:
            return None,None
        v=self.files[name]
        return v['data'],v['sha']
    def list(self,dirname):
        prefix=dirname.rstrip('/')+'/'
        entries={}
        for path in self.files:
            if not path.startswith(prefix):
                continue
            tail=path[len(prefix):]
            part=tail.split('/')[0]
            typ='dir' if '/' in tail else 'file'
            entries[part]={'name':part,'path':prefix+part,'type':typ}
        return list(entries.values())
    def put(self,name,data,expected_sha,message):
        prev=self.files.get(name)
        if (prev['sha'] if prev else None)!=expected_sha:
            raise ValueError('GITHUB_STORE_SHA_CONFLICT')
        self.counter+=1
        sha=hashlib.sha1(('blob '+str(len(data.encode()))+'\0'+data).encode()).hexdigest()
        self.files[name]={'data':data,'sha':sha}
        return {'content':{'sha':sha},'commit':{'sha':'synthetic-commit-'+str(self.counter)}}

def fails(what,action):
    try:
        action()
    except ValueError as exc:
        assert what in str(exc), (what,str(exc))
        return
    raise AssertionError('Expected '+what)

transport=MemoryTransport()
graph={'schemaVersion':1,'revision':1,'id':'pilot','title':'Pilot',
       'planningScale':'module','identitySpace':'pilot',
       'rootRequirementId':'R0','actionModel':'candidate-v6',
       'nodes':[{'id':'R0','kind':'requirement','title':'Root','status':'active'}],
       'edges':[],'events':[]}
filename='graphs/workspaces/test/graph.json'
transport.put(filename,json.dumps(graph),None,'synthetic initialization')
service=store.GithubGraphStore(transport)
os.environ['RDG_V6_TRUST_KEY']='test-isolated-issuer-only-'+('7'*44)
issuer='synthetic-issuer'
change={'file':'workspaces/test/graph.json',
        'patch':{'schemaVersion':1,'expectedRevision':1,
        'operations':[{'op':'graph_edit','action':'create_context',
          'node':{'id':'C1','kind':'context','title':'Data source'},
          'event':{'id':'EV-GENERAL-1','type':'graph_changed',
                   'operation':'create_context','by':'assistant',
                   'note':'Synthetic provenance','authorityPrincipal':issuer}}]}}
package={'schemaVersion':1,'transactionId':'commit-general-one','changes':[change]}
claim={'purpose':'rdg-v6-material-action-v1','principal':issuer,
       'expiresAt':int(time.time())+450}
claim['signature']=hmac.new(os.environ['RDG_V6_TRUST_KEY'].encode(),
    trust.canonical(trust.proof_payload({**package,'trustedApproval':claim})),
    hashlib.sha256).hexdigest()
package['trustedApproval']=claim
initial_sha=transport.read(filename)[1]
fails('EXPECTED_SHA_MISMATCH',lambda:service.commit_graph_package(package,'wrong-sha'))
tampered=copy.deepcopy(package)
tampered['changes'][0]['patch']['operations'][0]['node']['title']='tampered after signing'
fails('TRUST_SIGNATURE_INVALID',lambda:service.commit_graph_package(tampered,initial_sha))
result=service.commit_graph_package(package,initial_sha)
assert result['revision']==2 and result['commitSHA']=='synthetic-commit-2'
state=json.loads(transport.read(filename)[0])
assert state['nodes'][-1]['id']=='C1' and state['events'][0]['verifiedTrustReceipt']['principal']==issuer
fails('EXPECTED_SHA_MISMATCH',lambda:service.commit_graph_package(package,initial_sha))

research={'saved':True,'id':'20261017-160001000-abcd',
 'metadata':{'recordedAt':'2026-10-17T16:00:01.000Z','lensId':'L-DRY',
             'targetGraphId':'pilot','targetActionId':'A1',
             'unresolvedQrpe':['Q1']},
 'workingGraph':{'kind':'working-lens-graph','graph':{'id':'L-DRY'}}}
archived=service.save_research(research)
assert archived['path'].startswith('lens-applications/2026-10-17/')
assert json.loads(transport.read(archived['path'])[0])==research
transport.read_paths=[]
indexed=service.list_research_metadata()
assert all(name.endswith('.metadata.json') for name in transport.read_paths), transport.read_paths
assert len(indexed)==1 and indexed[0]['targetActionId']=='A1'
assert indexed[0]['researchPath']==archived['path']
assert service.load_research(indexed[0])==research
fails('RESEARCH_ALREADY_SAVED',lambda:service.save_research(research))
modified=dict(indexed[0],researchBlobSHA='incorrect-blob')
fails('RESEARCH_SHA_MISMATCH',lambda:service.load_research(modified))
# Listing many cheap runs must never require loading their full graph content.
assert any(p.endswith('.metadata.json') for p in transport.files)


unsafe=copy.deepcopy(package)
unsafe['changes'][0]['patch']['operations'][0]['action']='deactivate_requirement'
fails('CROSS_GRAPH_SCOPE_UNVERIFIED',lambda:service.commit_graph_package(unsafe,result['blobSHA']))
print('GITHUB_STORE_FAKE_PASS: expected SHA, exact signature, readback, opt-in archive, scope guards')
