#!/usr/bin/env python3
"""Create candidate-v6 through the canonical authenticated Graph writer."""
import argparse
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
import io
import json
import os
from pathlib import Path
import re
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
WRITER=SourceFileLoader('workspace_model',str(ROOT/'tools/graph-apply.py')).load_module()
PACKAGE=SourceFileLoader('workspace_package',str(ROOT/'tools/graph-package.py')).load_module()


def create_workspace(slug,title,root_id,root_title,identity_space,transaction_id,dry_run=False,core_model=False):
    if not os.environ.get('RDG_AUTH_STORE') or not os.environ.get('RDG_AUTH_TOKEN'):
        raise ValueError('WORKSPACE_AUTH_NOT_CONFIGURED')
    if not isinstance(slug,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',slug):
        raise ValueError('WORKSPACE_SLUG_INVALID')
    if not all(isinstance(v,str) and v.strip() for v in (title,root_id,root_title,identity_space)):
        raise ValueError('WORKSPACE_GOAL_REQUIRED')
    graph={'schemaVersion':1,'actionModel':'candidate-v6','id':'rdg-'+slug,
        'identitySpace':identity_space,'rootRequirementId':root_id,'planningScale':'module',
        'title':title,'revision':1,'catalogSlug':slug,'presentation':{'usage':'working'},
        'nodes':[{'id':root_id,'kind':'requirement','title':root_title,'status':'active','qrpe':[]}],
        'edges':[],'events':[],'collections':[]}
    if core_model:
        graph=WRITER.core_model().blank('rdg-'+slug,title,identity_space,root_id,root_title,
                               scope='Рабочий scope '+slug)
        graph.update(catalogSlug=slug,presentation={'usage':'working'})
    WRITER.validate(graph)
    relative='workspaces/'+slug+'/graph.json'
    package={'schemaVersion':1,'transactionId':transaction_id,'changes':[{'file':relative,'create':graph}]}
    with redirect_stdout(io.StringIO()):
        records=PACKAGE.execute(package,dry_run=dry_run)
    return {'created':not dry_run,'dryRun':dry_run,'transactionId':transaction_id,
        'graphFile':relative,'identitySpace':identity_space,'revision':records[0]['after']['revision'],
        'actionModel':'candidate-v6','coreModel':graph.get('coreModel'),'planCreated':False,'completionAttested':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for field in ['slug','title','root-id','root-title','identity-space']:p.add_argument('--'+field,required=True)
    p.add_argument('--transaction-id',default=None)
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--core-model',action='store_true',help='Create the clarified closed core; no migration')
    a=p.parse_args()
    result=create_workspace(a.slug,a.title,a.root_id,a.root_title,a.identity_space,
                            a.transaction_id or 'workspace-'+uuid.uuid4().hex,a.dry_run,a.core_model)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as e:
        print('ERROR: '+str(e),file=sys.stderr);sys.exit(2)
