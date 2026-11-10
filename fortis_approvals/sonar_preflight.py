"""One-shot, owner-operated G4 GET-only preflight for a single Sonar Issue.

Discover scoped projects, select the first OPEN Issue from bounded samples,
fetch its exact projection and its available transitions. Never call POST or
persist the token. Issue descriptions/messages are NEVER printed.
"""
import argparse
import json
import re
import sys

from .core import Denied
from .sonar import SonarHTTPTransport, SonarIssueAdapter, SonarTransportError
from .sonar_inventory import ORG_KEY, discover

MAX_PROJECTS = 30
SAMPLE_SIZE = 5
TRANSITION_KEY = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,39}\Z')


class PreflightGetOnly:
    """The entire CLI invocation uses only these fixed GET routes and args."""
    PARAMS = {
        '/api/components/search': ({'organization', 'p', 'ps'},),
        '/api/issues/search': ({'componentKeys', 'p', 'ps'},
                               {'componentKeys', 'issues', 'p', 'ps'},
                               {'componentKeys', 'issues', 'p', 'ps', 'additionalFields'}),
    }

    def __init__(self, transport):
        self.transport = transport

    def call(self, method, path, params):
        if (method != 'GET' or path not in self.PARAMS or
                type(params) is not dict or
                set(params) not in self.PARAMS[path] or
                any(type(k) is not str or type(v) is not str for k, v in params.items()) or
                ('additionalFields' in params and params['additionalFields'] != 'transitions')):
            raise Denied('SONAR_PREFLIGHT_GET_ONLY')
        return self.transport.call(method, path, params)


def _get(reader, stage, path, params):
    try:
        return reader.call('GET', path, params)
    except SonarTransportError as exc:
        # Only fixed stage names and already-redacted transport codes.
        raise SonarTransportError('SONAR_PREFLIGHT_' + stage + '_' + str(exc)) from None


def _transitions(row):
    # Search can return transitions as strings or key objects; missing means UNKNOWN.
    if 'transitions' not in row:
        return [], 'NOT_RETURNED'
    items = row['transitions']
    if type(items) is not list or len(items) > 32:
        raise Denied('SONAR_PREFLIGHT_TRANSITIONS_INVALID')
    keys = set()
    for item in items:
        key = item.get('key') if type(item) is dict else item
        if (type(key) is not str or not TRANSITION_KEY.fullmatch(key) or key in keys):
            raise Denied('SONAR_PREFLIGHT_TRANSITIONS_INVALID')
        keys.add(key)
    return sorted(keys), 'RETURNED' if keys else 'RETURNED_EMPTY'


def preflight(transport, organizations, *, region):
    if (region not in SonarHTTPTransport.ORIGINS or
            type(organizations) not in (list, tuple) or
            not 1 <= len(organizations) <= 20 or
            any(type(o) is not str or not ORG_KEY.fullmatch(o) for o in organizations) or
            len(set(organizations)) != len(organizations)):
        raise Denied('SONAR_PREFLIGHT_SCOPE_INVALID')
    reader = PreflightGetOnly(transport)
    projects = [(org, key) for org in organizations for key in discover(reader, org)]
    inspected = 0
    for org, project in projects[:MAX_PROJECTS]:
        inspected += 1
        result = _get(reader, 'SAMPLE', '/api/issues/search',
                      {'componentKeys': project, 'p': '1', 'ps': str(SAMPLE_SIZE)})
        if (type(result) is not dict or type(result.get('issues')) is not list or
                len(result['issues']) > SAMPLE_SIZE):
            raise Denied('SONAR_PREFLIGHT_SAMPLE_INVALID')
        for row in result['issues']:
            if (type(row) is not dict or row.get('project') != project or
                    type(row.get('key')) is not str or
                    not SonarIssueAdapter.ISSUE_KEY.fullmatch(row['key'])):
                raise Denied('SONAR_PREFLIGHT_SAMPLE_SCOPE_INVALID')
            state = row.get('issueStatus', row.get('status'))
            if type(state) is not str or not 0 < len(state) <= 64:
                raise Denied('SONAR_PREFLIGHT_SAMPLE_STATUS_INVALID')
            if state != 'OPEN':
                continue
            issue_key = row['key']
            transition_lookup = 'SEARCH_ADDITIONAL_FIELDS'
            try:
                exact = _get(reader, 'EXACT_ISSUE', '/api/issues/search',
                         {'componentKeys': project, 'issues': issue_key, 'p': '1', 'ps': '2', 'additionalFields': 'transitions'})
            except SonarTransportError as exc:
                if not str(exc).endswith('SONAR_HTTP_400'):
                    raise
                exact = _get(reader, 'EXACT_ISSUE_RETRY', '/api/issues/search',
                             {'componentKeys': project, 'issues': issue_key, 'p': '1', 'ps': '2'})
                transition_lookup = 'ADDITIONAL_FIELDS_REJECTED'
            if (type(exact) is not dict or type(exact.get('issues')) is not list or
                    len(exact['issues']) != 1):
                raise Denied('SONAR_PREFLIGHT_EXACT_ISSUE_INVALID')
            normalized = SonarIssueAdapter._normalize(exact['issues'][0], project=project)
            if normalized['key'] != issue_key or normalized['status'] != 'OPEN':
                raise Denied('SONAR_PREFLIGHT_ISSUE_CHANGED')
            transition_keys, transition_state = _transitions(exact['issues'][0])
            if transition_lookup != 'SEARCH_ADDITIONAL_FIELDS':
                transition_keys, transition_state = [], 'NOT_VERIFIED'
            fields = SonarIssueAdapter.FIELDS
            return {
                'status': 'ISSUE_PREFLIGHT_READ_OK', 'region': region,
                'organization': org, 'projectKey': project, 'issueKey': issue_key,
                'issueStatus': normalized['status'], 'updateDate': normalized['updateDate'],
                'issueSha256': SonarIssueAdapter._digest(normalized),
                'fieldsPresent': sorted(k for k in fields if normalized[k] is not None),
                'fieldsMissing': sorted(k for k in fields if normalized[k] is None),
                'availableTransitionKeys': transition_keys,
                'acceptOffered': 'accept' in transition_keys,
                'transitionState': transition_state, 'transitionLookup': transition_lookup,
                'writeAuthorized': False,
                'visibleProjectCount': len(projects), 'projectsInspected': inspected,
                'allIssuesInspected': False, 'mutations': 0, 'tokenPersisted': False,
            }
    raise Denied('SONAR_PREFLIGHT_NO_OPEN_IN_BOUNDED_SAMPLE')


def main(argv=None):
    parser = argparse.ArgumentParser(description='G4 Sonar single-Issue READ-only preflight')
    parser.add_argument('--region', required=True, choices=sorted(SonarHTTPTransport.ORIGINS))
    parser.add_argument('--organization', action='append', required=True)
    args = parser.parse_args(argv)
    try:
        if (len(args.organization) > 20 or
                any(type(org) is not str or not ORG_KEY.fullmatch(org) for org in args.organization)):
            raise Denied('SONAR_PREFLIGHT_SCOPE_INVALID')
        token = sys.stdin.readline(4097).rstrip('\r\n')
        if not 12 <= len(token) <= 4096 or any(c.isspace() for c in token):
            raise Denied('SONAR_PREFLIGHT_TOKEN_INVALID')
        result = preflight(SonarHTTPTransport(region=args.region, bearer_token=token),
                           args.organization, region=args.region)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (Denied, SonarTransportError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (OSError, RuntimeError, ValueError):
        print('SONAR_PREFLIGHT_UNAVAILABLE', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
