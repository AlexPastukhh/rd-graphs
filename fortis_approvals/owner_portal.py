"""Standalone, owner-only WSGI origin for G2 WebAuthn and approval UI.

Never mount at client Gateway. No deployment/privilege administration APIs.
"""
from http.cookies import SimpleCookie
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .core import ApprovalError, Denied, loads_strict

STATIC = Path(__file__).resolve().parent / 'static'


class OwnerPortal:
    def __init__(self, core, authenticator, *, strong_operations=(), blocked_approvals=(),
                 read_only_banner=False):
        if core.owner_verifier is not authenticator:
            raise ValueError('OWNER_VERIFIER_MUST_MATCH')
        self.core, self.auth = core, authenticator
        self.origin = authenticator.origin
        self.host = urlsplit(self.origin).netloc
        self.strong_operations = frozenset(strong_operations)
        self.blocked_approvals = frozenset(blocked_approvals)
        self.read_only_banner = bool(read_only_banner)

    def _approval_policy_current(self, row):
        return (row.get('policyVersion') == self.core.policy_version and
                self.core._policy(row['actor'], row['request']) == 'ASK')

    def _approval_allowed(self, row, decision):
        if decision != 'approve':
            return
        action = (row['request']['service'], row['request']['operation'])
        if action in self.blocked_approvals:
            raise Denied('OWNER_OPERATION_WRITE_NOT_ENABLED')
        if not self._approval_policy_current(row):
            raise Denied('OWNER_OPERATION_POLICY_CHANGED')

    @staticmethod
    def _reply(start, status, content, mime='application/json; charset=utf-8', extras=()):
        if isinstance(content, dict) or isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False, separators=(',', ':')).encode()
        elif isinstance(content, str):
            content = content.encode()
        titles = {200:'OK', 400:'Bad Request', 401:'Unauthorized', 403:'Forbidden',
                  404:'Not Found', 409:'Conflict', 413:'Payload Too Large', 500:'Internal Server Error'}
        headers=[('Content-Type',mime),('Content-Length',str(len(content))),
                 ('Cache-Control','no-store'),('Referrer-Policy','no-referrer'),
                 ('X-Content-Type-Options','nosniff'),('X-Frame-Options','DENY'),
                 ('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
                 *extras]
        start(f'{status} {titles[status]}', headers)
        return [content]

    def _strong(self, row):
        req = row['request']
        return (req['service'], req['operation']) in self.strong_operations

    def _owner_view(self, row):
        action = (row['request']['service'], row['request']['operation'])
        return {**row, 'requiresStrongProof': self._strong(row),
                'approvalAllowed': (action not in self.blocked_approvals and
                                    self._approval_policy_current(row))}

    def _cookie(self, env):
        cookies = SimpleCookie()
        cookies.load(env.get('HTTP_COOKIE','')[:4096])
        value = cookies.get('fortis_owner')
        return value.value if value else ''

    def _json(self, env):
        if env.get('CONTENT_TYPE','').split(';')[0] != 'application/json':
            raise Denied('JSON_REQUIRED')
        length = env.get('CONTENT_LENGTH','')
        if not re.fullmatch(r'[0-9]{1,9}', length):
            raise Denied('BODY_SIZE')
        size = int(length)
        if not 0 < size <= 262144:
            raise Denied('BODY_SIZE')
        body = env['wsgi.input'].read(size)
        if len(body) != size:
            raise Denied('BODY_SIZE')
        try:
            value = loads_strict(body)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ValueError('BODY_INVALID') from None
        if not isinstance(value, dict):
            raise Denied('BODY_INVALID')
        return value

    def __call__(self, env, start):
        try:
            if (env.get('HTTP_HOST') != self.host or env.get('QUERY_STRING') or
                any(env.get(x) for x in ('HTTP_X_FORWARDED_HOST', 'HTTP_FORWARDED',
                                          'HTTP_PROXY_AUTHORIZATION', 'HTTP_AUTHORIZATION'))):
                raise Denied('HOST_DENIED')
            method, path = env.get('REQUEST_METHOD'), env.get('PATH_INFO','')
            if method == 'GET' and path in ('/', '/app.js', '/style.css'):
                filename = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path]
                mime = ('text/html; charset=utf-8' if path=='/' else
                        'text/javascript; charset=utf-8' if path=='/app.js' else 'text/css; charset=utf-8')
                content=(STATIC / filename).read_bytes()
                if filename=='index.html' and self.read_only_banner:
                    content=content.replace(b'<h1>Fortis Approvals</h1>',
                        b'<h1>Fortis Approvals - G4 READ ONLY</h1>')
                return self._reply(start,200,content,mime)
            if method == 'GET' and path == '/v1/owner/session':
                row = self.auth.session(self._cookie(env))
                return self._reply(start,200,{'owner':row['owner'],'csrf':row['csrf']})
            if method == 'GET' and path in ('/v1/owner/pending','/v1/owner/history'):
                self.auth.session(self._cookie(env))
                return self._reply(start,200,[self._owner_view(r) for r in self.core.owner_list(pending=path.endswith('pending'))])
            if method == 'GET' and re.fullmatch('/v1/owner/requests/[0-9a-f-]{36}',path):
                self.auth.session(self._cookie(env))
                return self._reply(start,200,self._owner_view(self.core._read(path.rsplit('/',1)[-1])))
            if method != 'POST':
                return self._reply(start,404,{'error':'ROUTE_NOT_FOUND'})
            if env.get('HTTP_ORIGIN') != self.origin:
                raise Denied('ORIGIN_DENIED')
            body=self._json(env)
            if path == '/v1/enroll/begin' and set(body)=={'invitation'}:
                return self._reply(start,200,self.auth.begin_enrollment(body['invitation']))
            if path == '/v1/enroll/finish' and set(body)=={'ceremonyId','response'}:
                return self._reply(start,200,self.auth.finish_enrollment(body['ceremonyId'],body['response']))
            if path == '/v1/login/begin' and not body:
                return self._reply(start,200,self.auth.begin_login())
            if path == '/v1/login/finish' and set(body)=={'ceremonyId','response'}:
                session, csrf=self.auth.finish_login(body['ceremonyId'],body['response'])
                # Secure attribute mandatory for HTTPS; HTTP is permitted only localhost.
                cookie=('fortis_owner='+session+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+str(self.auth.session_ttl)+
                        ('; Secure' if self.origin.startswith('https:') else ''))
                return self._reply(start,200,{'owner':self.auth.owner,'csrf':csrf},
                                   extras=[('Set-Cookie',cookie)])
            token = self._cookie(env)
            csrf = env.get('HTTP_X_FORTIS_CSRF')
            if not csrf:
                raise Denied('CSRF_REQUIRED')
            self.auth.session(token, csrf)
            if path == '/v1/owner/decision/session' and set(body)=={'requestId','decision','fingerprint'}:
                row = self.core._read(body['requestId'])
                if row['state'] != 'PENDING' or row['fingerprint'] != body['fingerprint']:
                    raise Denied('REQUEST_NOT_PENDING_OR_CHANGED')
                self._approval_allowed(row, body['decision'])
                if self._strong(row):
                    raise Denied('STRONG_PROOF_REQUIRED')
                proof = self.auth.begin_session_decision(token, row['requestId'], row['fingerprint'], body['decision'])
                return self._reply(start,200,self._owner_view(
                    self.core.owner_decide(row['requestId'], body['decision'], proof)))
            if path == '/v1/owner/decision/begin' and set(body)=={'requestId','decision'}:
                if body['decision'] not in ('approve','reject'):
                    raise Denied('DECISION_INVALID')
                view=self.core._read(body['requestId'])
                if view['state'] != 'PENDING':
                    raise Denied('REQUEST_NOT_PENDING')
                self._approval_allowed(view, body['decision'])
                return self._reply(start,200,self.auth.begin_decision(token,view['requestId'],
                                                  view['fingerprint'],body['decision']))
            if path == '/v1/owner/decision/finish' and set(body)=={'requestId','decision','ceremonyId','response'}:
                self._approval_allowed(self.core._read(body['requestId']), body['decision'])
                proof={'session':token,'ceremonyId':body['ceremonyId'],'response':body['response']}
                return self._reply(start,200,self._owner_view(self.core.owner_decide(body['requestId'],body['decision'],proof)))
            return self._reply(start,404,{'error':'ROUTE_NOT_FOUND'})
        except Denied as e:
            return self._reply(start,403,{'error':str(e)})
        except (ApprovalError, ValueError, TypeError, KeyError, UnicodeError):
            return self._reply(start,400,{'error':'REQUEST_INVALID'})
        except (OSError, RuntimeError):
            return self._reply(start,500,{'error':'OUTCOME_UNCONFIRMED'})
