"""OWNER-OPERATED LOCAL G2 DEMO ONLY — NO PRODUCTION TRUST CLAIM.

Run from a reviewed copy outside the AI-writable Repo, with a local Python venv
that has fido2 installed. Does not expose client Gateway or any secrets service.
"""
import argparse
import os
from pathlib import Path
import secrets
import uuid
from wsgiref.simple_server import make_server

from .core import Authenticator, Core
from .owner_auth import OwnerWebAuthn
from .owner_portal import OwnerPortal
from .synthetic import SyntheticAdapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18990)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('invalid port')
    folder = args.state_dir.absolute()
    if folder.is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error('state directory MUST be outside the project source tree')
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.is_symlink() or folder.stat().st_mode & 0o077:
        parser.error('state directory must be private (0700)')
    adapter=SyntheticAdapter(folder/'synthetic.sqlite')
    if not adapter.get('R3'):
        adapter.seed('R3','original')
    # In the demo only, no client-facing API is exposed. Seed one synthetic ASK
    # request to make the owner UI usable without ever accessing RDG.
    core=Core(folder/'approvals.sqlite',adapters={'synthetic':adapter},
              policies={('synthetic','set_ask'):'ASK'},
              authenticator=Authenticator({'local-demo-credential':'synthetic-client'}))
    owner=OwnerWebAuthn(folder/'owner.sqlite',origin=f'http://localhost:{args.port}')
    core.owner_verifier=owner
    if not core.owner_list(pending=True):
        request=dict(requestId=str(uuid.uuid4()),service='synthetic',operation='set_ask',
                     target='R3',params={'value':'Approved demo change'},
                     expectedVersion=adapter.get('R3')['version'],reason='Local G2 UI smoke test')
        core.client('local-demo-credential','submit',request)
    invite=owner.issue_invitation()
    print(f'Local demo UI: http://localhost:{args.port}/',flush=True)
    print('Operator invitation (one use, expires in 5 min): '+invite,flush=True)
    print('Synthetic only; not a trusted deployment. Stop with Ctrl+C.',flush=True)
    with make_server('127.0.0.1',args.port,OwnerPortal(core,owner)) as server:
        server.serve_forever()


if __name__=='__main__':
    main()
