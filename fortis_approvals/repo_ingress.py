"""Strict WSGI Repo action/status + typed Sonar READ routes; no listener.

The machine request bears a Fortis ingress grant, NEVER the SonarCloud token.
Owner/admin/executor/generic proxy routes are unavailable. Source-only R3 tests
use an isolated localhost server; the Windows A3 synthetic image has no Sonar
reader, and production source/TLS/secret admission remains OPEN.
"""
import json
import re
import threading
import time

from .core import ApprovalError, Conflict, Denied


_ID_PATH = re.compile(r'/v1/requests/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\Z')
_HOST = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z')
_AUTH = re.compile(r'Bearer ([A-Za-z0-9._~+/=-]{8,512})\Z')
_ALLOWED_METHODS = frozenset(('POST','GET'))
_PROXY_FIELDS = ('HTTP_X_FORWARDED_FOR','HTTP_X_FORWARDED_HOST',
                 'HTTP_X_FORWARDED_PROTO','HTTP_X_FORWARDED_PORT',
                 'HTTP_FORWARDED','HTTP_X_REAL_IP','HTTP_PROXY_AUTHORIZATION',
                 'HTTP_PROXY_CONNECTION','HTTP_X_HTTP_METHOD_OVERRIDE',
                 'HTTP_X_METHOD_OVERRIDE')


def _unique_json_pairs(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError('JSON_DUPLICATE_FIELD')
        data[key] = value
    return data


def _bad_constant(_):
    raise ValueError('JSON_NONFINITE_DENIED')


class _PerActorWindow:
    """In-memory defense-in-depth only; not cross-worker/shared rate policy."""
    def __init__(self, *, max_requests, seconds, clock):
        if type(max_requests) is not int or not 1 <= max_requests <= 10000:
            raise ValueError('RATE_LIMIT_INVALID')
        if type(seconds) not in (int,float) or not 1 <= seconds <= 86400:
            raise ValueError('RATE_WINDOW_INVALID')
        self.max_requests = max_requests
        self.seconds = seconds
        self.clock = clock
        self.lock = threading.Lock()
        self.records = {}

    def take(self, actor):
        now = self.clock()
        with self.lock:
            previous = self.records.get(actor, ())
            current = [n for n in previous if now - n < self.seconds]
            if len(current) >= self.max_requests:
                self.records[actor] = current
                return False
            current.append(now)
            self.records[actor] = current
            return True


class RepoIngress:
    """No direct Core/owner HTTP dispatch; broker actions/status/typed reads.

    `allow_http_local_test` is deliberately test-only and checks loopback
    connection metadata. It is NOT a deployment setting to use for live Repo.
    """
    def __init__(self, broker, *, host, max_bytes=8192,
                 max_requests=30, rate_seconds=60, clock=None,
                 allow_http_local_test=False, max_read_response_bytes=65536):
        if type(host) is not str or not _HOST.fullmatch(host):
            raise ValueError('REPO_HOST_INVALID')
        if type(max_bytes) is not int or not 128 <= max_bytes <= 8192:
            raise ValueError('REPO_BODY_LIMIT_INVALID')
        if type(allow_http_local_test) is not bool:
            raise ValueError('REPO_LOCAL_TEST_INVALID')
        if (type(max_read_response_bytes) is not int or
                not 1024 <= max_read_response_bytes <= 262144):
            raise ValueError('REPO_READ_RESPONSE_LIMIT_INVALID')
        if allow_http_local_test and not host.startswith(('localhost:', '127.0.0.1:')):
            raise ValueError('REPO_LOCAL_TEST_HOST_REQUIRED')
        self.broker = broker
        self.host = host
        self.max_bytes = max_bytes
        self.max_read_response_bytes = max_read_response_bytes
        self.allow_http_local_test = allow_http_local_test
        self.limiter = _PerActorWindow(max_requests=max_requests,
                        seconds=rate_seconds,clock=clock or time.monotonic)

    @staticmethod
    def _reply(start, code, content):
        body = json.dumps(content,ensure_ascii=False,separators=(',',':'),
                          allow_nan=False).encode('utf-8')
        label = {200:'OK',202:'Accepted',400:'Bad Request',401:'Unauthorized',
                 403:'Forbidden',404:'Not Found',409:'Conflict',
                 413:'Content Too Large',429:'Too Many Requests',
                 500:'Internal Server Error'}[code]
        start(f'{code} {label}',[('Content-Type','application/json; charset=utf-8'),
             ('Content-Length',str(len(body))),('Cache-Control','no-store'),
             ('Pragma','no-cache'),('X-Content-Type-Options','nosniff'),
             ('Referrer-Policy','no-referrer'),('X-Frame-Options','DENY'),
             ('Content-Security-Policy',"default-src 'none'; frame-ancestors 'none'"),
             ('Vary','Authorization')])
        return [body]

    def _environment(self, env):
        if (env.get('HTTP_HOST') != self.host or env.get('QUERY_STRING') or
                env.get('SCRIPT_NAME') or
                any(env.get(field) for field in _PROXY_FIELDS) or
                any(env.get(field) for field in ('HTTP_COOKIE','HTTP_ORIGIN',
                    'HTTP_REFERER','HTTP_X_FORTIS_CSRF','HTTP_X_FORWARDED_PREFIX')) or
                env.get('HTTP_TRANSFER_ENCODING') or
                env.get('HTTP_CONNECTION','').lower() == 'upgrade'):
            raise Denied('REPO_INGRESS_DENIED')
        if env.get('wsgi.url_scheme') != 'https':
            if not (self.allow_http_local_test and
                    env.get('wsgi.url_scheme') == 'http' and
                    env.get('REMOTE_ADDR') in ('127.0.0.1','::1')):
                raise Denied('REPO_TLS_REQUIRED')
        if env.get('REQUEST_METHOD') not in _ALLOWED_METHODS:
            return False
        return True

    def _credential(self, env):
        header = env.get('HTTP_AUTHORIZATION','')
        match = _AUTH.fullmatch(header) if type(header) is str else None
        if match is None:
            raise Denied('REPO_AUTH_REQUIRED')
        credential = match.group(1)
        # A distinct ingress credential, never the external Sonar bearer.
        actor = self.broker.core.auth.authenticate(credential)
        return credential, actor

    def _body(self, env):
        if env.get('CONTENT_TYPE') != 'application/json':
            raise Denied('REPO_CONTENT_TYPE_DENIED')
        length = env.get('CONTENT_LENGTH')
        if type(length) is not str or not length.isdecimal() or length.startswith('0'):
            raise Denied('REPO_CONTENT_LENGTH_DENIED')
        length = int(length)
        if length > self.max_bytes:
            return None
        if length == 0:
            raise Denied('REPO_CONTENT_LENGTH_DENIED')
        stream = env.get('wsgi.input')
        if stream is None:
            raise Denied('REPO_CONTENT_LENGTH_DENIED')
        raw = stream.read(length)
        if len(raw) != length:
            raise Denied('REPO_CONTENT_LENGTH_DENIED')
        try:
            return json.loads(raw.decode('utf-8'),object_pairs_hook=_unique_json_pairs,
                              parse_constant=_bad_constant)
        except (ValueError,TypeError,UnicodeError,RecursionError):
            raise Denied('REPO_JSON_DENIED') from None

    def __call__(self, env, start):
        try:
            if not self._environment(env):
                return self._reply(start,404,{'error':'ROUTE_NOT_FOUND'})
            method, path = env.get('REQUEST_METHOD'),env.get('PATH_INFO','')
            if not (method == 'POST' and path in ('/v1/actions', '/v1/reads') or
                    method == 'GET' and _ID_PATH.fullmatch(path)):
                return self._reply(start,404,{'error':'ROUTE_NOT_FOUND'})
            credential, actor = self._credential(env)
            if not self.limiter.take(actor):
                return self._reply(start,429,{'error':'REPO_RATE_LIMITED'})
            if method == 'POST':
                action = self._body(env)
                if action is None:
                    return self._reply(start,413,{'error':'REPO_BODY_TOO_LARGE'})
                if path == '/v1/reads':
                    out = self.broker.read(credential, action)
                    raw = json.dumps(out, ensure_ascii=False, separators=(',', ':'),
                                     allow_nan=False).encode('utf-8')
                    if len(raw) > self.max_read_response_bytes:
                        return self._reply(start,413,
                                           {'error':'REPO_READ_RESPONSE_TOO_LARGE'})
                    return self._reply(start,200,out)
                out = self.broker.submit(credential,action)
                return self._reply(start,202 if out['state']=='PENDING' else 200,out)
            # The Python wsgiref server synthesizes CONTENT_TYPE='text/plain'
            # for a bodyless GET even when the HTTP client sends no Content-Type.
            # Reject any actual Content-Length/body; accept CGI's benign default.
            if (env.get('CONTENT_LENGTH') not in (None,'','0') or
                env.get('CONTENT_TYPE') not in (None,'','text/plain')):
                raise Denied('REPO_GET_NO_BODY')
            out = self.broker.status(credential,_ID_PATH.fullmatch(path).group(1))
            return self._reply(start,200,out)
        except Conflict:
            return self._reply(start,409,{'error':'REPO_REQUEST_ID_CONFLICT'})
        except Denied as exc:
            code = 401 if str(exc) in ('REPO_AUTH_REQUIRED','CLIENT_UNAUTHORIZED') else 403
            # Stable public categories; no secrets or upstream response leakage.
            return self._reply(start,code,{'error':'REPO_UNAUTHORIZED' if code==401 else 'REPO_DENIED'})
        except (ApprovalError,ValueError,TypeError,KeyError,UnicodeError):
            return self._reply(start,400,{'error':'REPO_REQUEST_INVALID'})
        except (OSError,RuntimeError):
            return self._reply(start,500,{'error':'REPO_OUTCOME_UNCONFIRMED'})
