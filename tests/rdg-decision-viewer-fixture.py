#!/usr/bin/env python3
"""Disposable PR-6 host using the product Application/Helper/generated Viewer."""
import argparse
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import uuid

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):return SourceFileLoader(name,str(ROOT/file)).load_module()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-fixture',action='store_true',required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    args=parser.parse_args();base=args.data_dir.resolve();base.mkdir(exist_ok=True)
    config_path=base/'fixture.json'
    cli=load('pr6_host_cli','tools/rdg-portable.py')
    helper=load('pr6_host_helper','tools/rdg-loopback-helper.py')
    if not config_path.exists():
        if any(base.iterdir()):raise ValueError('SYNTHETIC_EMPTY_DIRECTORY_REQUIRED')
        namespace=str(uuid.uuid4());authority=cli.module('rdg-authority').Authority(base/'authority.json')
        admin=authority.init_local(plan_capable=True,graph_read_capable=True,portable_roots=[namespace])['token']
        token=authority.manage('issue',admin,{'permissions':['graph.read','graph.write','plan.read','plan.create','plan.edit','plan.branch','package.create','package.copy'],
            'scopes':['packages/'+namespace+'/']})['token']
        config={'packageRoot':str(base/'packages'),'namespaceId':namespace,'coordinationRoot':str(base),
            'authorityStore':str(authority.path)}
        app=cli.application(config,token)
        def create(**data):
            request={'op':'create','transactionId':str(uuid.uuid4()),'coreModel':'rdg-decision-v1',**data}
            preview=app.request(request,preflight=True)
            return app.request(request,expected_input_binding=preview['inputBinding'])['packages'][0]['packageId']
        process=create(path='working/pr6',role='working',title='PR-6 process',scope='Synthetic integration only',rootReason='Verify the real Viewer path')
        agent=load('pr6_host_agent','tools/rdg-agent.py')
        lens_graph=agent.lens_definition('work','rdg-decision-v1')[2]
        lens=create(path='lenses/test-work',role='lens',lensKey='work',
                    rootReason='Explicit test-only lens import',graph=lens_graph)
        fixture={'application':config,'token':token,'packageId':process,'lensId':lens}
        config_path.write_text(json.dumps(fixture));config_path.chmod(0o600)
    fixture=json.loads(config_path.read_text())
    editor=helper.PortableEditor(fixture['application'],fixture['token'])
    server=helper.make_server(editor,banner='PR-6 · synthetic Decision integration')
    url_file=base/'helper-url.txt';url_file.write_text(server.session_url);url_file.chmod(0o600)
    token_file=base/'agent-token.txt';token_file.write_text(fixture['token']);token_file.chmod(0o600)
    agent_config={'profile':'portable','packageRoot':fixture['application']['packageRoot'],'namespaceId':fixture['application']['namespaceId'],
        'coordinationRoot':fixture['application']['coordinationRoot'],'authStore':fixture['application']['authorityStore'],
        'tokenFile':str(token_file),'packageId':fixture['packageId'],'helperUrlFile':str(url_file)}
    context=base/'agent-context.json';context.write_text(json.dumps(agent_config));context.chmod(0o600)
    print(json.dumps({'url':server.session_url,'processId':os.getpid(),'packageId':fixture['packageId'],'lensId':fixture['lensId']}),flush=True)
    try:server.serve_forever()
    finally:server.server_close()

if __name__=='__main__':main()
