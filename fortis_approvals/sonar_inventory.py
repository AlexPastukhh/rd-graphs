"""G4 READ-only all-project inventory for explicitly selected Sonar organizations.
No Issue mutation, admin endpoint, owner state, credential file or write policy.
SonarCloud API cannot reliably discover user's organizations via public API;
owner supplies organization key(s) once, then all projects are paginated.
"""
import argparse
import json
import re
import sys

from collections import Counter
from .core import Denied
from .sonar import SonarHTTPTransport, SonarTransportError

ORG_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
PROJECT_KEY = ORG_KEY
PAGE_SIZE = 100
MAX_PAGES = 100


class ReadOnlyTransport:
    def __init__(self, underlying):
        self.underlying=underlying

    def call(self, method, path, params):
        routes={'/api/components/search': {'organization','p','ps','q'},
                '/api/issues/search': {'componentKeys','p','ps'}}
        if (method != 'GET' or path not in routes or type(params) is not dict or
                set(params)-routes[path] or
                not all(type(k) is str and type(v) is str for k,v in params.items())):
            raise Denied('SONAR_INVENTORY_READ_ONLY')
        return self.underlying.call(method,path,params)


def discover(transport, organization, query_key=None):
    if type(organization) is not str or not ORG_KEY.fullmatch(organization):
        raise Denied('SONAR_ORGANIZATION_INVALID')
    if query_key is not None and (type(query_key) is not str or not PROJECT_KEY.fullmatch(query_key)):
        raise Denied('SONAR_PROJECT_KEY_INVALID')
    keys, total = set(), None
    for page in range(1, MAX_PAGES + 1):
        params={'organization':organization, 'p':str(page), 'ps':str(PAGE_SIZE)}
        if query_key is not None:
            params['q']=query_key
        try:
            data = transport.call('GET', '/api/components/search',params)
        except SonarTransportError as exc:
            raise SonarTransportError('SONAR_PROJECT_DISCOVERY_' + str(exc)) from None
        if type(data) is not dict or type(data.get('components')) is not list:
            raise Denied('SONAR_PROJECT_SEARCH_INVALID')
        paging = data.get('paging')
        if (type(paging) is not dict or type(paging.get('total')) is not int or
            type(paging.get('pageIndex')) is not int or
            not 0 <= paging['total'] <= PAGE_SIZE * MAX_PAGES or
            paging['pageIndex'] != page):
            raise Denied('SONAR_PAGING_INVALID')
        if total is None:
            total = paging['total']
        elif total != paging['total']:
            raise Denied('SONAR_PAGING_CHANGED')
        rows = data['components']
        if len(rows) > PAGE_SIZE:
            raise Denied('SONAR_PAGE_TOO_LARGE')
        for row in rows:
            if (type(row) is not dict or row.get('qualifier') != 'TRK' or
                type(row.get('key')) is not str or
                not PROJECT_KEY.fullmatch(row['key']) or
                ('organization' in row and row['organization'] != organization) or
                row['key'] in keys):
                raise Denied('SONAR_PROJECT_RESPONSE_INVALID')
            keys.add(row['key'])
        if len(keys) == total:
            return sorted(keys)
        if not rows or len(keys) > total:
            raise Denied('SONAR_PAGING_INCOMPLETE')
    raise Denied('SONAR_PAGING_CAPACITY')
def read_issue_sample(transport, project_key):
    if type(project_key) is not str or not PROJECT_KEY.fullmatch(project_key):
        raise Denied('SONAR_ISSUE_PROJECT_INVALID')
    try:
        payload=transport.call('GET','/api/issues/search',
            {'componentKeys':project_key,'p':'1','ps':'5'})
    except SonarTransportError as exc:
        raise SonarTransportError('SONAR_ISSUES_SEARCH_' + str(exc)) from None
    if (type(payload) is not dict or type(payload.get('issues')) is not list
            or len(payload['issues'])>5):
        raise Denied('SONAR_ISSUES_RESPONSE_INVALID')
    counts=Counter()
    for row in payload['issues']:
        if (type(row) is not dict or row.get('project') != project_key or
            type(row.get('key')) is not str or
            not PROJECT_KEY.fullmatch(row['key'])):
            raise Denied('SONAR_ISSUE_IDENTITY_INVALID')
        state=row.get('issueStatus',row.get('status'))
        if type(state) is not str or not 0<len(state)<=64:
            raise Denied('SONAR_ISSUE_STATUS_INVALID')
        counts[state]+=1
    return {'projectKey':project_key,'readOk':True,
            'sampleCount':len(payload['issues']),
            'sampleStatusCounts':dict(sorted(counts.items()))}


def inventory(transport, organizations, *, region, read_issues=False):
    if (region not in SonarHTTPTransport.ORIGINS or
        type(organizations) not in (list, tuple) or
        not 1 <= len(organizations) <= 20 or
        any(type(o) is not str or not ORG_KEY.fullmatch(o) for o in organizations) or
        len(set(organizations)) != len(organizations)):
        raise Denied('SONAR_INVENTORY_INPUT_INVALID')
    if type(read_issues) is not bool:
        raise Denied('SONAR_INVENTORY_READ_MODE_INVALID')
    summary, samples, total, keys_for_checks = [], [], 0, []
    for org in organizations:
        keys = discover(transport,org)
        summary.append({'organization':org,'visibleProjects':len(keys)})
        total += len(keys)
        for key in keys:
            if len(samples) < 12:
                samples.append({'organization':org,'projectKey':key})
            if len(keys_for_checks) < 30:
                keys_for_checks.append(key)
    report={'status':'DISCOVERY_OK','region':region,'organizations':summary,
            'visibleProjectCount':total,'sampleProjectKeys':samples,
            'mutations':0,'tokenPersisted':False}
    if read_issues:
        checked=[read_issue_sample(transport,key) for key in keys_for_checks]
        report.update(status='ISSUES_READ_OK',issuesCheckedProjects=len(checked),
                      allProjectsChecked=(len(checked)==total),issuesReadResults=checked)
    return report
def main(argv=None):
    parser=argparse.ArgumentParser(description='G4 owner-only SonarCloud project discovery (READ only)')
    parser.add_argument('--region',choices=sorted(SonarHTTPTransport.ORIGINS),required=True)
    parser.add_argument('--organization',action='append',required=True)
    parser.add_argument('--read-issues',action='store_true',help='GET a sample of Issues for up to 30 discovered projects')
    args=parser.parse_args(argv)
    try:
        if (len(args.organization)>20 or
            any(not ORG_KEY.fullmatch(o) for o in args.organization)):
            raise Denied('SONAR_ORGANIZATION_INVALID')
        token=sys.stdin.readline(4097).rstrip('\r\n')
        if not 12 <= len(token) <= 4096 or any(ch.isspace() for ch in token):
            raise Denied('SONAR_INVENTORY_TOKEN_INVALID')
        transport=ReadOnlyTransport(SonarHTTPTransport(region=args.region,bearer_token=token))
        result=inventory(transport,args.organization,region=args.region,read_issues=args.read_issues)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except (Denied,SonarTransportError) as exc:
        print(str(exc),file=sys.stderr)
        return 3
    except (OSError,RuntimeError,ValueError):
        print('SONAR_INVENTORY_UNAVAILABLE',file=sys.stderr)
        return 3


if __name__=='__main__':
    raise SystemExit(main())
