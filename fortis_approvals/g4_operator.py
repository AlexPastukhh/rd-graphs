"""Trusted local candidate CLI. No G4 client HTTP route, no token in args.

Usage: python -m fortis_approvals.g4_operator propose --project KEY --issue KEY
Reads reason from local stdin. Requires owner-managed G4 environment.
"""
import argparse
import sys

from .g4_candidate import build_candidate, propose_issue
from .g4_server import config
from .core import Denied
from .sonar import SonarTransportError


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    cmd=parser.add_subparsers(dest='action',required=True)
    propose=cmd.add_parser('propose')
    propose.add_argument('--project',required=True)
    propose.add_argument('--issue',required=True)
    cmd.add_parser('inspect')
    cmd.add_parser('invite')
    args=parser.parse_args(argv)
    try:
        core, owner, adapter, _, _=build_candidate(**config())
        if args.action=='invite':
            print('G4-only owner invitation (single-use, expires in 5 minutes):')
            print(owner.issue_invitation(),flush=True)
            return 0
        if args.action=='inspect':
            print('Pending:',len(core.owner_list(pending=True)),
                  'History:',len(core.owner_list(pending=False)),flush=True)
            return 0
        reason=sys.stdin.readline(1502).strip()
        if not 0<len(reason)<=1500:
            raise Denied('G4_REASON_INVALID')
        row=propose_issue(core,adapter,project_key=args.project,
                          issue_key=args.issue,reason=reason)
        print('G4 proposal:',row['requestId'],'state:',row['state'],
              'mutationRequests: 0',flush=True)
        return 0
    except (Denied, SonarTransportError, ValueError, OSError):
        # No token, URL, issue message or untrusted remote response in errors.
        print('G4_CANDIDATE_REQUEST_DENIED',file=sys.stderr)
        return 3


if __name__=='__main__':
    raise SystemExit(main())
