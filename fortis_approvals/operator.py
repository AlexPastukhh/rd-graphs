"""Owner-only CLI: invitations, synthetic fixtures and status (NO HTTP API).

Run via docker compose run on owner's Docker host. Not exposed to Repo/AI.
"""
import argparse
import uuid

from .runtime import build_runtime


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('invite','seed','inspect'))
    args = cli.parse_args()
    core,owner,adapter,_=build_runtime()
    if args.action=='invite':
        print('One-use owner enrollment invitation (expires in 5 minutes):')
        print(owner.issue_invitation(),flush=True)
    elif args.action=='seed':
        if adapter.get('R3') is None:
            adapter.seed('R3','original')
        current=adapter.get('R3')
        request={'requestId':str(uuid.uuid4()),'service':'synthetic',
                 'operation':'set_ask','target':'R3',
                 'params':{'value':'Approved synthetic change'},
                 'expectedVersion':current['version'],
                 'reason':'Standalone G2 synthetic owner-interface check'}
        view=core.client('operator-synthetic-only','submit',request)
        print('Seeded synthetic request:',view['requestId'],'state:',view['state'],flush=True)
    elif args.action=='inspect':
        print('Pending:',len(core.owner_list(pending=True)),
              'History:',len(core.owner_list(pending=False)),flush=True)


if __name__=='__main__':
    main()
