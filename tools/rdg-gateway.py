#!/usr/bin/env python3
"""Private RDG-only gateway. Its bearer never enters the client container."""
import json
import http.client
from pathlib import Path
import re
import stat
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

ORIGIN = 'http://rdg-api-gateway:8081'
UPSTREAM = 'http://rdg:8080'
SECRET_KIND = 'rdg-private-gateway-credential'
MAX_RESPONSE = 16000000


def require(ok, code):
    if not ok:
        raise ValueError('RDG_GATEWAY_' + code)


def credentials(path):
    path = Path(path)
    require(path.is_absolute() and path.is_file() and
            not any(p.is_symlink() for p in (path, *path.parents)), 'SECRET_FILE_REQUIRED')
    require(stat.S_IMODE(path.stat().st_mode) & 0o077 == 0, 'PRIVATE_SECRET_REQUIRED')
    value = json.loads(path.read_text(encoding='utf8'))
    require(isinstance(value, dict) and set(value) == {'kind', 'namespaceId', 'token'} and
            value['kind'] == SECRET_KIND, 'SECRET_SCHEMA')
    require(str(uuid.UUID(value['namespaceId'])) == value['namespaceId'], 'NAMESPACE_INVALID')
    require(re.fullmatch(r'rdg_[A-Za-z0-9_-]{40,100}', value['token']), 'TOKEN_INVALID')
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Gateway:
    def __init__(self, secret_path, public_origin, *, upstream=UPSTREAM, origin=ORIGIN):
        value = credentials(secret_path)
        self.namespace, self.token = value['namespaceId'], value['token']
        parsed = urlsplit(public_origin)
        require(parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and
                not parsed.password and not parsed.path and not parsed.query and not parsed.fragment and
                public_origin == parsed.scheme + '://' + parsed.netloc and
                not any(c in public_origin for c in ('\r', '\n', '\\', ' ')), 'PUBLIC_ORIGIN_INVALID')
        require(parsed.scheme == 'https' or parsed.hostname in ('localhost', '127.0.0.1', '::1'),
                'PUBLIC_HTTPS_REQUIRED')
        self.public_host, self.host, self.upstream = parsed.netloc, urlsplit(origin).netloc, upstream
        # Runtime always uses the fixed upstream; loopback injection is only for isolated tests.
        require(upstream == UPSTREAM or (urlsplit(upstream).scheme == 'http' and
                urlsplit(upstream).hostname in ('127.0.0.1', 'localhost')), 'UPSTREAM_INVALID')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def relay(self, path, data=None):
        request = urllib.request.Request(self.upstream + path, data=data,
            method='GET' if data is None else 'POST', headers={
                'Host': self.public_host, 'Authorization': 'Bearer ' + self.token,
                'X-RDG-Namespace': self.namespace, 'Content-Type': 'application/json'})
        try:
            try:
                response = self.opener.open(request, timeout=60)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                raw = response.read(MAX_RESPONSE + 1)
                length = response.headers.get('Content-Length')
                require(len(raw) <= MAX_RESPONSE and
                        (not length or (length.isdigit() and int(length) == len(raw))),
                        'RESPONSE_UNCONFIRMED')
                if response.status in (301, 302, 303, 307, 308):
                    return 502, {'error': 'RDG_GATEWAY_REDIRECT_DENIED', 'definite': False}
                try:
                    value = json.loads(raw)
                    require(isinstance(value, dict), 'RESPONSE_UNCONFIRMED')
                    # A broken upstream must not echo its Authorization back to the client.
                    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
                    if self.token in encoded:
                        return 502, {'error': 'RDG_GATEWAY_SECRET_IN_RESPONSE', 'definite': False}
                    return response.status, value
                except (ValueError, UnicodeError):
                    return 502, {'error': 'RDG_GATEWAY_RESPONSE_UNCONFIRMED', 'definite': False}
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException,
                OSError, ValueError):
            return 502, {'error': 'RDG_GATEWAY_UPSTREAM_UNCONFIRMED', 'definite': False}

    @staticmethod
    def response(start, status, value):
        labels = {200: 'OK', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
                  404: 'Not Found', 405: 'Method Not Allowed', 413: 'Content Too Large',
                  500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable'}
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        start(str(status) + ' ' + labels.get(status, 'Request Rejected'), [
            ('Content-Type', 'application/json; charset=utf-8'), ('Content-Length', str(len(body))),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
            ('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")])
        return [body]

    def __call__(self, env, start):
        try:
            require(env.get('HTTP_HOST') == self.host, 'HOST_DENIED')
            require(not env.get('QUERY_STRING'), 'QUERY_DENIED')
            require(not any(env.get(k) for k in ('HTTP_ORIGIN', 'HTTP_AUTHORIZATION',
                'HTTP_PROXY_AUTHORIZATION', 'HTTP_COOKIE', 'HTTP_X_RDG_SESSION',
                'HTTP_FORWARDED', 'HTTP_X_FORWARDED_HOST')), 'CLIENT_CREDENTIALS_DENIED')
            path, method = env.get('PATH_INFO', ''), env.get('REQUEST_METHOD', '')
            require(path in ('/healthz', '/api/capabilities', '/api/command'), 'ROUTE_DENIED')
            if path in ('/healthz', '/api/capabilities'):
                require(method == 'GET', 'METHOD_DENIED')
                status, value = self.relay('/api/capabilities')
                if status == 200:
                    require(value.get('namespaceId') == self.namespace and
                            value.get('protocol') == 'rdg-application-v1', 'UPSTREAM_IDENTITY_DENIED')
                    if path == '/healthz':
                        value = {'status': 'ok', 'service': 'rdg-agent-gateway',
                                 'namespaceId': self.namespace, 'credentialLocation': 'gateway-only'}
                    else:
                        value['credentialLocation'] = 'gateway-only'
                return self.response(start, status, value)
            require(method == 'POST', 'METHOD_DENIED')
            require(env.get('HTTP_X_RDG_NAMESPACE') == self.namespace, 'NAMESPACE_DENIED')
            require(env.get('CONTENT_TYPE', '').split(';')[0] == 'application/json', 'CONTENT_TYPE')
            length = env.get('CONTENT_LENGTH', '')
            require(length.isdigit() and 0 < int(length) <= 1000000, 'REQUEST_SIZE')
            raw = env['wsgi.input'].read(int(length))
            require(len(raw) == int(length), 'REQUEST_SIZE')
            message = json.loads(raw)
            require(isinstance(message, dict), 'MESSAGE')
            status, value = self.relay('/api/command',
                json.dumps(message, ensure_ascii=False, allow_nan=False).encode())
            return self.response(start, status, value)
        except (ValueError, UnicodeError) as error:
            code = str(error)
            if not re.fullmatch(r'RDG_GATEWAY_[A-Z_]{1,80}', code):
                code = 'RDG_GATEWAY_REQUEST_REJECTED'
            status = 413 if code.endswith('REQUEST_SIZE') else 403 if code.endswith('DENIED') else 400
            return self.response(start, status, {'error': code, 'definite': True})
        except (OSError, KeyError, TypeError):
            return self.response(start, 500, {'error': 'RDG_GATEWAY_REQUEST_FAILED', 'definite': False})


def from_environment():
    import os
    return Gateway('/run/rdg-gateway/credentials.json', os.environ['RDG_PUBLIC_ORIGIN'])
