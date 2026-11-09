"""Owner-only one-shot read probe. Exactly two Sonar GET requests, zero writes.

Invoke only from the owner's independently reviewed Windows Docker artifact.
Bearer token comes from Docker STDIN, never CLI args/env/files/logs. This
module intentionally does not load the Core, receipt store or Approvals DB.
"""
import argparse
from collections import Counter
import json
import sys

from .core import Denied
from .sonar import SonarHTTPTransport, SonarIssueAdapter, SonarTransportError


class ReadOnlySonarProbe:
    def __init__(self, transport):
        self.transport = transport

    def call(self, method, path, params):
        if method != 'GET' or path not in ('/api/components/show', '/api/issues/search'):
            raise Denied('SONAR_READ_PROBE_ONLY')
        return self.transport.call(method, path, params)


def probe(*, transport, project_key, region):
    """Return intentionally limited, non-sensitive telemetry to owner's terminal."""
    if (region not in SonarHTTPTransport.ORIGINS or type(project_key) is not str or
            not SonarIssueAdapter.PROJECT_KEY.fullmatch(project_key)):
        raise Denied('SONAR_PROBE_INPUT_DENIED')
    reader = ReadOnlySonarProbe(transport)
    try:
        component = reader.call('GET', '/api/components/show', {'component': project_key})
    except SonarTransportError as exc:
        # Fixed stage label only: never include URL, parameters, token or body.
        raise SonarTransportError('SONAR_PROJECT_LOOKUP_' + str(exc)) from None
    if (type(component) is not dict or type(component.get('component')) is not dict or
            component['component'].get('key') != project_key or
            component['component'].get('qualifier') != 'TRK'):
        raise Denied('SONAR_PROJECT_READBACK_DENIED')
    try:
        result = reader.call('GET', '/api/issues/search',
                             {'componentKeys': project_key, 'p': '1', 'ps': '5'})
    except SonarTransportError as exc:
        raise SonarTransportError('SONAR_ISSUES_SEARCH_' + str(exc)) from None
    if (type(result) is not dict or type(result.get('issues')) is not list or
            len(result['issues']) > 5):
        raise Denied('SONAR_ISSUES_RESPONSE_DENIED')
    states = Counter()
    for row in result['issues']:
        if (type(row) is not dict or row.get('project') != project_key or
                type(row.get('key')) is not str or
                not SonarIssueAdapter.ISSUE_KEY.fullmatch(row['key'])):
            raise Denied('SONAR_ISSUES_SCOPE_DENIED')
        status = row.get('issueStatus', row.get('status'))
        if type(status) is not str or len(status) > 64 or not status:
            raise Denied('SONAR_ISSUE_STATUS_DENIED')
        states[status] += 1
    total = result.get('paging', {}).get('total') if isinstance(result.get('paging'), dict) else None
    if total is not None and (type(total) is not int or total < len(result['issues'])):
        raise Denied('SONAR_ISSUES_PAGING_DENIED')
    return {'status': 'READ_OK', 'region': region, 'project': project_key,
            'projectVerified': True, 'pageSize': len(result['issues']),
            'totalIssues': total, 'sampleStatusCounts': dict(sorted(states.items())),
            'mutationRequests': 0, 'tokenPersisted': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='SonarQube Cloud G4 READ-only Docker probe')
    parser.add_argument('--region', choices=sorted(SonarHTTPTransport.ORIGINS), required=True)
    parser.add_argument('--project', required=True)
    args = parser.parse_args(argv)
    if not SonarIssueAdapter.PROJECT_KEY.fullmatch(args.project):
        print('SONAR_PROBE_INPUT_DENIED', file=sys.stderr)
        return 2
    try:
        token = sys.stdin.readline(4097).rstrip('\r\n')
        if not 12 <= len(token) <= 4096 or any(ch.isspace() for ch in token):
            raise Denied('SONAR_PROBE_TOKEN_INVALID')
        client = SonarHTTPTransport(region=args.region,bearer_token=token)
        # Probe takes the token exclusively via STDIN. No credentials are
        # included in report, traceback, request URL, or user-visible logs.
        result = probe(transport=client,project_key=args.project,region=args.region)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (Denied, SonarTransportError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (OSError, ValueError, RuntimeError):
        print('SONAR_PROBE_UNAVAILABLE',file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
