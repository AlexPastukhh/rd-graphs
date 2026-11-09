"""G4 SonarQube Cloud Issues V1: read + ONE typed ASK 'accept_issue'.

NOT wired to the owner-only G2 Docker runtime. The adapter has no default
credentials, network access, policy grants or new HTTP server. Inject a trusted
transport at a separate operator-controlled G4 deployment only.

Sonar's transition endpoint has no conditional version check. We compare a
frozen projection before dispatch AND immediately before POST, but a remote
writer can race those reads. Never retry after an ambiguous POST response.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import ssl
from urllib import error, parse, request

from .core import Denied, Stale, canonical


class SonarTransportError(RuntimeError):
    """Redacted upstream failure. Never include token, URL query, or response body."""


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SonarTransportError('SONAR_REDIRECT_DENIED')


class SonarHTTPTransport:
    """Minimal real HTTPS transport; NEVER construct in Repo with a real token.

    The origin is pinned to the official EU/US SonarQube Cloud V1 instance;
    there is no custom URL, arbitrary method or generic HTTP proxy endpoint.
    """
    ORIGINS = {'eu': 'https://sonarcloud.io', 'us': 'https://sonarqube.us'}
    ROUTES = {('GET', '/api/components/show'), ('GET', '/api/components/search'),
              ('GET', '/api/issues/search'),
              ('GET', '/api/qualitygates/project_status'),
              ('POST', '/api/issues/do_transition')}

    def __init__(self, *, region, bearer_token, timeout=8):
        if region not in self.ORIGINS or type(bearer_token) is not str or not bearer_token.strip() or '\n' in bearer_token or '\r' in bearer_token:
            raise ValueError('SONAR_CONFIG_INVALID')
        if type(timeout) not in (int, float) or not 1 <= timeout <= 15:
            raise ValueError('SONAR_TIMEOUT_INVALID')
        self._origin = self.ORIGINS[region]
        self._token = bearer_token
        self._timeout = timeout
        self._opener = request.build_opener(request.ProxyHandler({}),
                        request.HTTPSHandler(context=ssl.create_default_context()),
                        _NoRedirect())

    def call(self, method, path, params):
        if ((method, path) not in self.ROUTES or type(params) is not dict or
                not all(type(k) is str and type(v) is str for k,v in params.items())):
            raise Denied('SONAR_HTTP_ROUTE_DENIED')
        allowed = {
            ('GET', '/api/components/show'): {'component'},
            ('GET', '/api/components/search'): {'organization', 'p', 'ps', 'q'},
            ('GET', '/api/issues/search'): {'issues', 'componentKeys', 'p', 'ps', 'additionalFields'},
            ('GET', '/api/qualitygates/project_status'): {'projectKey'},
            ('POST', '/api/issues/do_transition'): {'issue', 'transition'},
        }[(method,path)]
        if set(params) - allowed or ('additionalFields' in params and
                                       params['additionalFields'] != 'transitions'):
            raise Denied('SONAR_HTTP_PARAMS_DENIED')
        data = parse.urlencode(params).encode('ascii')
        url = self._origin + path + (('?' + data.decode('ascii')) if method=='GET' else '')
        headers = {'Authorization': 'Bearer ' + self._token, 'Accept': 'application/json'}
        if method=='POST':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        outgoing = request.Request(url, data=data if method=='POST' else None,
                                   method=method, headers=headers)
        try:
            with self._opener.open(outgoing, timeout=self._timeout) as response:
                if response.status != 200:
                    raise SonarTransportError('SONAR_HTTP_NON_200')
                content = response.read(262145)
                if len(content) > 262144:
                    raise SonarTransportError('SONAR_RESPONSE_TOO_LARGE')
                return json.loads(content)
        except error.HTTPError as exc:
            raise SonarTransportError('SONAR_HTTP_' + str(exc.code)) from None
        except (error.URLError, TimeoutError, OSError):
            raise SonarTransportError('SONAR_TRANSPORT_UNAVAILABLE') from None
        except (UnicodeError, ValueError, TypeError):
            raise SonarTransportError('SONAR_RESPONSE_INVALID') from None


class SonarIssueAdapter:
    """One operation: accept_issue, with verified owner ASK via Core.

    Project allowlist is a trusted constructor input; no default project.
    expectedVersion=0 is the V1 placeholder because Sonar has no numeric
    CAS version; expectedIssueSha256 binds the current issue projection.
    """
    SERVICE = 'sonarcloud'
    OPERATION = 'accept_issue'
    PROJECT_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
    ISSUE_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
    SHA256 = re.compile(r'[0-9a-f]{64}\Z')
    FIELDS = ('key', 'project', 'status', 'updateDate', 'message', 'rule',
              'severity', 'component', 'assignee', 'type')

    def __init__(self, transport, *, project_keys=(), organization_keys=(), receipt_store, region='eu'):
        if not callable(getattr(transport,'call',None)):
            raise ValueError('SONAR_TRANSPORT_REQUIRED')
        if (not isinstance(project_keys,(set,tuple,frozenset)) or
            not all(type(k) is str and self.PROJECT_KEY.fullmatch(k) for k in project_keys)):
            raise ValueError('SONAR_PROJECT_ALLOWLIST_INVALID')
        if (not isinstance(organization_keys,(set,tuple,frozenset)) or
            not all(type(k) is str and self.PROJECT_KEY.fullmatch(k) for k in organization_keys)):
            raise ValueError('SONAR_ORGANIZATION_ALLOWLIST_INVALID')
        if not project_keys and not organization_keys:
            raise ValueError('SONAR_SCOPE_REQUIRED')
        if region not in SonarHTTPTransport.ORIGINS:
            raise ValueError('SONAR_REGION_INVALID')
        if isinstance(transport, SonarHTTPTransport) and transport._origin != SonarHTTPTransport.ORIGINS[region]:
            raise ValueError('SONAR_REGION_MISMATCH')
        self.region = region
        self.transport = transport
        self.projects = frozenset(project_keys)
        self.organizations = frozenset(organization_keys)
        self.store = Path(receipt_store)
        self.store.parent.mkdir(parents=True,exist_ok=True)
        if self.store.is_symlink():
            raise Denied('SONAR_RECEIPT_STORE_SYMLINK')
        if not self.store.exists():
            import os
            os.close(os.open(self.store, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        if self.store.stat().st_mode & 0o077:
            raise Denied('SONAR_RECEIPT_STORE_PERMISSIONS')
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS receipts
                (request_id TEXT PRIMARY KEY, result TEXT NOT NULL)''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.store,timeout=5)
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _check_project(self, key):
        if type(key) is not str or not self.PROJECT_KEY.fullmatch(key):
            raise Denied('SONAR_PROJECT_DENIED')
        if key in self.projects:
            return key
        # Organization scope comes from the trusted owner deployment, never
        # client payload. Verify *current* membership on every read/decision;
        # newly added projects are found without widening arbitrary URL access.
        if self.organizations:
            from .sonar_inventory import discover
            for organization in sorted(self.organizations):
                if key in discover(self.transport, organization, query_key=key):
                    return key
        raise Denied('SONAR_PROJECT_DENIED')

    def _check_issue_key(self,key):
        if type(key) is not str or not self.ISSUE_KEY.fullmatch(key):
            raise Denied('SONAR_ISSUE_KEY_DENIED')
        return key

    @classmethod
    def _normalize(cls, raw, *, project):
        if not isinstance(raw,dict):
            raise Denied('SONAR_ISSUE_INVALID')
        status=raw.get('issueStatus',raw.get('status'))
        if type(status) is not str or not status:
            raise Denied('SONAR_ISSUE_STATUS_MISSING')
        obj={name:raw.get(name) for name in cls.FIELDS}
        obj['status']=status
        if (obj['project']!=project or
            not isinstance(obj['key'],str) or not cls.ISSUE_KEY.fullmatch(obj['key']) or
            not isinstance(obj['updateDate'],str) or not 0<len(obj['updateDate'])<=80):
            raise Denied('SONAR_ISSUE_IDENTITY_OR_VERSION_MISSING')
        for k in ('message','rule','severity','component','assignee','type'):
            if obj[k] is not None and (type(obj[k]) is not str or len(obj[k])>4000):
                raise Denied('SONAR_ISSUE_FIELD_INVALID')
        return obj

    @staticmethod
    def _digest(issue):
        return hashlib.sha256(canonical(issue).encode('utf-8')).hexdigest()

    def read_issue(self, project_key, issue_key):
        project=self._check_project(project_key)
        issue=self._check_issue_key(issue_key)
        result=self.transport.call('GET','/api/issues/search',
                                   {'componentKeys':project,'issues':issue,'p':'1','ps':'2'})
        if not isinstance(result,dict) or not isinstance(result.get('issues'),list):
            raise Denied('SONAR_SEARCH_INVALID')
        issues=result['issues']
        if len(issues)!=1:
            raise Denied('SONAR_ISSUE_NOT_UNIQUE')
        normalized=self._normalize(issues[0],project=project)
        if normalized['key']!=issue:
            raise Denied('SONAR_ISSUE_MISMATCH')
        return {**normalized, 'sha256':self._digest(normalized)}

    def list_issues(self, project_key, *, page=1, page_size=20):
        project=self._check_project(project_key)
        if type(page) is not int or not 1<=page<=100 or type(page_size) is not int or not 1<=page_size<=100:
            raise Denied('SONAR_PAGE_DENIED')
        response=self.transport.call('GET','/api/issues/search',
                  {'componentKeys':project,'p':str(page),'ps':str(page_size)})
        if not isinstance(response,dict) or not isinstance(response.get('issues'),list) or len(response['issues'])>page_size:
            raise Denied('SONAR_SEARCH_INVALID')
        results=[]
        for issue in response['issues']:
            normalized=self._normalize(issue,project=project)
            results.append({**normalized,'sha256':self._digest(normalized)})
        return results

    @staticmethod
    def _transitions(issue):
        # Live SonarCloud returns transition *strings* within the issue row
        # when issues/search is called with additionalFields=transitions.
        # Some test/legacy responses contain keyed objects. Neither format
        # grants permission: absence, invalid values and duplicates fail shut.
        if type(issue) is not dict or type(issue.get('transitions')) is not list or len(issue['transitions']) > 32:
            raise Denied('SONAR_TRANSITIONS_INVALID')
        keys=set()
        for row in issue['transitions']:
            key=row.get('key') if type(row) is dict else row
            if (type(key) is not str or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,39}',key) or
                    key in keys):
                raise Denied('SONAR_TRANSITIONS_INVALID')
            keys.add(key)
        return keys

    def _check_request(self, req):
        if (req.get('service')!=self.SERVICE or req.get('operation')!=self.OPERATION or
            type(req.get('expectedVersion')) is not int or req['expectedVersion']!=0 or
            type(req.get('params')) is not dict or
            set(req['params'])!={'projectKey','transition','expectedIssueSha256'} or
            req['params']['transition']!='accept'):
            raise Denied('SONAR_OPERATION_DENIED')
        project=self._check_project(req['params']['projectKey'])
        issue=self._check_issue_key(req['target'])
        digest=req['params']['expectedIssueSha256']
        if type(digest) is not str or not self.SHA256.fullmatch(digest):
            raise Denied('SONAR_ISSUE_DIGEST_INVALID')
        return project,issue,digest

    def _before(self,project,issue,digest):
        # A single exact Issue read binds the frozen preview to transition
        # availability on the *same* server snapshot, not two separate reads.
        response=self.transport.call('GET','/api/issues/search',
            {'componentKeys':project,'issues':issue,'p':'1','ps':'2',
             'additionalFields':'transitions'})
        if (type(response) is not dict or type(response.get('issues')) is not list or
                len(response['issues'])!=1):
            raise Denied('SONAR_ISSUE_NOT_UNIQUE')
        raw=response['issues'][0]
        normalized=self._normalize(raw,project=project)
        if normalized['key']!=issue:
            raise Denied('SONAR_ISSUE_MISMATCH')
        current={**normalized,'sha256':self._digest(normalized)}
        if current['sha256']!=digest:
            raise Stale('SONAR_ISSUE_CHANGED')
        if current['status'] not in ('OPEN','CONFIRMED'):
            raise Denied('SONAR_ISSUE_NOT_OPEN')
        if 'accept' not in self._transitions(raw):
            raise Denied('SONAR_ACCEPT_NOT_AVAILABLE')
        return current

    def prepare(self, req):
        project,issue,digest=self._check_request(req)
        before=self._before(project,issue,digest)
        return {'projectKey':project,'issueKey':issue,'before':before,
                'after':{'status':'ACCEPTED'},'transition':'accept',
                'issueUrl':f'{SonarHTTPTransport.ORIGINS[self.region]}/project/issues?id={parse.quote(project,safe="")}&open={parse.quote(issue,safe="")}' }

    def apply(self, req):
        project,issue,digest=self._check_request(req)
        previous=self.receipt(req['requestId'])
        if previous is not None:
            return previous
        # Last defense before remote write; Sonar has no conditional HTTP CAS.
        self._before(project,issue,digest)
        response=self.transport.call('POST','/api/issues/do_transition',
                                     {'issue':issue,'transition':'accept'})
        if not isinstance(response,dict) or not isinstance(response.get('issue'),dict):
            raise SonarTransportError('SONAR_WRITE_RESPONSE_INVALID')
        posted=self._normalize(response['issue'],project=project)
        if posted['key']!=issue or posted['status']!='ACCEPTED':
            raise SonarTransportError('SONAR_WRITE_RESPONSE_UNCONFIRMED')
        after=self.read_issue(project,issue)
        if after['status']!='ACCEPTED':
            raise SonarTransportError('SONAR_READBACK_UNCONFIRMED')
        result={'requestId':req['requestId'],'projectKey':project,'issueKey':issue,
                'transition':'accept','status':after['status'],
                'beforeSha256':digest,'afterSha256':after['sha256'],
                'readback':after}
        # Only confirmed result is durable. Lost response after POST is UNCERTAIN;
        # no blind retry and no inference from state alone.
        with self._db() as db:
            db.execute('INSERT INTO receipts(request_id,result) VALUES(?,?)',
                       (req['requestId'],canonical(result)))
        return result

    def receipt(self, request_id):
        with self._db() as db:
            row=db.execute('SELECT result FROM receipts WHERE request_id=?',(request_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def confirm(self, request_id, result):
        return (type(result) is dict and result.get('requestId')==request_id and
                self.receipt(request_id)==result)
