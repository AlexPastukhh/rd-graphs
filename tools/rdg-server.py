#!/usr/bin/env python3
"""Personal RDG WSGI host. All domain operations use the existing Application."""
import argparse
import base64
from collections import OrderedDict
from importlib.machinery import SourceFileLoader
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit
import uuid

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
KIND = 'rdg-personal-server'
PERMISSIONS = ['graph.read', 'graph.write', 'plan.read', 'plan.create', 'plan.edit',
               'plan.branch', 'package.create', 'package.copy', 'package.move', 'folder.write']


def load(name):
    return SourceFileLoader('server_' + name.replace('-', '_'), str(TOOLS / (name + '.py'))).load_module()


def require(ok, code):
    if not ok:
        raise ValueError('RDG_SERVER_' + code)


def outside_code(path):
    path = Path(path).absolute()
    require(not path.resolve().is_relative_to(ROOT), 'DATA_OUTSIDE_CODE_REQUIRED')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'SYMLINK_DENIED')
    return path


def origin_value(value):
    parsed = urlsplit(value)
    require(parsed.scheme in ('http', 'https') and parsed.hostname and
            not parsed.username and not parsed.password and not parsed.query and
            not parsed.fragment and parsed.path in ('', '/') and
            value == parsed.scheme + '://' + parsed.netloc, 'PUBLIC_ORIGIN_INVALID')
    require(parsed.scheme == 'https' or parsed.hostname in ('localhost', '127.0.0.1', '::1'),
            'HTTPS_REQUIRED')
    require(not any(c in value for c in ('\r', '\n', '\\', ' ')), 'PUBLIC_ORIGIN_INVALID')
    return value


def read_config(data_dir):
    data = outside_code(data_dir)
    config = json.loads((data / 'server.json').read_text(encoding='utf8'))
    require(set(config) == {'schemaVersion', 'kind', 'namespaceId', 'browserGrantId', 'agentGrantId'}
            and config['schemaVersion'] == 1 and config['kind'] == KIND, 'CONFIG_INVALID')
    require(str(uuid.UUID(config['namespaceId'])) == config['namespaceId'], 'NAMESPACE_INVALID')
    require(config['browserGrantId'] != config['agentGrantId'] and
            all(re.fullmatch(r'g_[a-f0-9]{20}', config[k]) for k in ('browserGrantId', 'agentGrantId')),
            'GRANTS_INVALID')
    return data, config


def app_config(data, config):
    return {'packageRoot': str(data / 'packages'), 'namespaceId': config['namespaceId'],
            'coordinationRoot': str(data), 'authorityStore': str(data / 'authority.json')}


def initialize(data_dir, credentials_dir, runtime_uid=None):
    """Explicit operator setup for a NEW namespace; no existing owners are imported."""
    data, credentials = outside_code(data_dir), outside_code(credentials_dir)
    require(not data.is_relative_to(credentials) and not credentials.is_relative_to(data),
            'SEPARATE_CREDENTIALS_REQUIRED')
    if (data / 'server.json').is_file():
        _, config = read_config(data)
        return {'initialized': True, 'alreadyInitialized': True, 'namespaceId': config['namespaceId']}
    require(not data.exists() or not any(data.iterdir()), 'EXISTING_DATA_REFUSED')
    require(not credentials.exists() or not any(credentials.iterdir()), 'EXISTING_CREDENTIALS_REFUSED')
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    credentials.mkdir(parents=True, exist_ok=True, mode=0o700)
    authority_module, io = load('rdg-authority'), load('rdg-transaction-io')
    namespace = str(uuid.uuid4())
    authority = authority_module.Authority(data / 'authority.json')
    owner = authority.init_local(plan_capable=True, graph_read_capable=True, portable_roots=[namespace])
    # Owner credentials never enter the serving process or an HTTP response.
    def secret_file(name, value):
        with os.fdopen(os.open(credentials / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as out:
            out.write(value + '\n'); out.flush(); os.fsync(out.fileno())
    secret_file('owner-token.txt', owner['token'])
    browser = authority.manage('issue', owner['token'], {'label': 'RDG browser',
        'permissions': PERMISSIONS, 'scopes': ['packages/' + namespace + '/']})
    secret_file('browser-token.txt', browser['token'])
    agent = authority.manage('issue', owner['token'], {'label': 'RDG assistant',
        'permissions': PERMISSIONS, 'scopes': ['packages/' + namespace + '/']})
    secret_file('agent-token.txt', agent['token'])
    secret_file('namespace-id.txt', namespace)
    config = {'schemaVersion': 1, 'kind': KIND, 'namespaceId': namespace,
              'browserGrantId': browser['id'], 'agentGrantId': agent['id']}
    app = load('rdg-portable').application(app_config(data, config), browser['token'], 'user')
    with app.store.lock():
        app.store.initialize()
    io.atomic_bytes(data / 'server.json', (json.dumps(config, indent=2) + '\n').encode())
    if runtime_uid is not None:
        require(os.getuid() == 0 and runtime_uid > 0, 'RUNTIME_UID_INVALID')
        for path in [data, *data.rglob('*')]:
            require(not path.is_symlink(), 'SYMLINK_DENIED')
            os.chown(path, runtime_uid, runtime_uid)
    return {'initialized': True, 'alreadyInitialized': False, 'namespaceId': namespace,
            'includesDemoGraphs': False, 'credentialsDirectory': str(credentials)}


def build_identity(path=None):
    path = Path(path) if path is not None else TOOLS.parent / 'RDG-BUILD.json'
    if not path.is_file():
        return 'source'
    value = json.loads(path.read_text())
    require(isinstance(value, dict) and set(value) == {'buildId', 'contentSHA256', 'repositoryHead'} and
            isinstance(value['buildId'], str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,110}', value['buildId']) and
            re.fullmatch(r'[a-f0-9]{64}', value['contentSHA256']) and
            re.fullmatch(r'[a-f0-9]{40}', value['repositoryHead']), 'BUILD_ID_INVALID')
    return value['buildId']


class Host:
    """One process owns volatile view sessions; FileStore owns all durable facts."""
    def __init__(self, data_dir, public_origin):
        self.data, self.config = read_config(data_dir)
        self.origin = origin_value(public_origin)
        self.build_id = build_identity()
        self.authority = load('rdg-authority').Authority(self.data / 'authority.json')
        self.compose = load('rdg-portable').application
        self.endpoint_type = load('rdg-loopback-helper').PortableEditor
        self.endpoints, self.caps = OrderedDict(), {}
        self.guard = threading.RLock()

    def authenticated(self, environ, browser):
        header = environ.get('HTTP_AUTHORIZATION', '')
        require(len(header) <= 1024, 'AUTH_REQUIRED')
        if browser:
            require(header.startswith('Basic '), 'AUTH_REQUIRED')
            try:
                username, token = base64.b64decode(header[6:], validate=True).decode('ascii').split(':', 1)
            except (ValueError, UnicodeError):
                raise ValueError('RDG_SERVER_AUTH_REQUIRED') from None
            require(username == 'rdg', 'AUTH_REQUIRED')
        else:
            require(header.startswith('Bearer '), 'AUTH_REQUIRED')
            token = header[7:]
        try:
            ident, _ = self.authority._actor(self.authority._read(), token)
        except ValueError:
            raise ValueError('RDG_SERVER_AUTH_REQUIRED') from None
        expected = self.config['browserGrantId' if browser else 'agentGrantId']
        require(hmac.compare_digest(ident, expected), 'AUTH_REQUIRED')
        key = hashlib.sha256(token.encode()).hexdigest()
        if key not in self.endpoints:
            # Reuse the existing dispatch/outcome guard, with server-owned attribution.
            endpoint = object.__new__(self.endpoint_type)
            endpoint.application = self.compose(app_config(self.data, self.config), token,
                                                'user' if browser else 'assistant')
            endpoint.application.runtime_build_id = self.build_id
            endpoint.require_verified_locks = True
            self.endpoints[key] = endpoint
        return ident, self.endpoints[key]

    def response(self, start, status, value, *, mime='application/json; charset=utf-8', extra=(), nonce=None):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        policy = "default-src 'self'; script-src 'self'" + (" 'nonce-" + nonce + "'" if nonce else '')
        policy += "; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        headers = [('Content-Type', mime), ('Content-Length', str(len(body))),
                   ('Cache-Control', 'no-store'), ('Referrer-Policy', 'no-referrer'),
                   ('X-Content-Type-Options', 'nosniff'), ('Content-Security-Policy', policy), *extra]
        if self.origin.startswith('https:'):
            headers.append(('Strict-Transport-Security', 'max-age=31536000'))
        start(status, headers)
        return [body]

    def __call__(self, environ, start_response):
        with self.guard:
            return self.dispatch(environ, start_response)

    def dispatch(self, env, start):
        path = env.get('PATH_INFO', '')
        api = path.startswith('/api/')
        method = env.get('REQUEST_METHOD', '')
        try:
            require(env.get('HTTP_HOST') == urlsplit(self.origin).netloc, 'HOST_DENIED')
            require(not env.get('QUERY_STRING'), 'QUERY_DENIED')
            if path == '/healthz' and method == 'GET':
                return self.response(start, '200 OK', {'status': 'ok', 'service': 'rdg', 'buildId': self.build_id})
            ident, endpoint = self.authenticated(env, browser=not api)
            if api:
                require(env.get('HTTP_X_RDG_NAMESPACE') == self.config['namespaceId'], 'NAMESPACE_DENIED')
            if env.get('HTTP_ORIGIN'):
                require(env['HTTP_ORIGIN'] == self.origin, 'ORIGIN_DENIED')
            if api and path == '/api/capabilities' and method == 'GET':
                return self.response(start, '200 OK', {'protocol': 'rdg-application-v1',
                    'namespaceId': self.config['namespaceId'], 'attribution': 'assistant',
                    'operations': sorted(endpoint.application.OPERATIONS), 'humanApprovalAvailable': False})
            if not api:
                cap = self.caps.setdefault(ident, secrets.token_urlsafe(32))
                prefix = '/session/' + cap + '/'
                if path == '/' and method == 'GET':
                    return self.response(start, '303 See Other', b'', extra=[('Location', prefix)])
                # After a server restart the prior browser document still points
                # to its old volatile capability.  A Basic-authenticated GET of
                # that *document URL only* may recover the new session.  Never
                # redirect old JS paths, API calls or POST commands.
                if method == 'GET' and path != prefix and re.fullmatch(r'/session/[A-Za-z0-9_-]{43}/', path):
                    return self.response(start, '303 See Other', b'', extra=[('Location', prefix)])
                require(path.startswith(prefix), 'SESSION_DENIED')
                route = path[len(prefix):]
                if route == '' and method == 'GET':
                    nonce = secrets.token_urlsafe(24)
                    boot = ('globalThis.RDG_LOCAL_PORTABLE=true;globalThis.RDG_DECISION_EXPLORER=true;'
                            'globalThis.RDG_AUTHENTICATED_SERVER=true;globalThis.RDG_SESSION=' + json.dumps(cap) + ';' +
                            'globalThis.RDG_BUILD_ID=' + json.dumps(self.build_id) + ';' +
                            "setInterval(async()=>{try{const r=await fetch('/healthz',{cache:'no-store'});"
                            "if(!r.ok)return;const v=await r.json();if(v.buildId&&v.buildId!==RDG_BUILD_ID){"
                            "const b=document.getElementById('rdg-build-refresh');b.hidden=false;"
                            "b.onclick=()=>location.reload();}}catch{}},5000);")
                    page = ('<!doctype html><html lang="ru"><meta charset="utf-8">'
                            '<meta name="viewport" content="width=device-width,initial-scale=1">'
                            '<title>RDG</title><body><div style="position:fixed;bottom:4px;right:8px;z-index:2147483647;font:11px monospace;color:#9bbbd3;pointer-events:none">'
                            'RDG ' + self.build_id + ' <button id="rdg-build-refresh" hidden style="pointer-events:auto">Новая сборка — обновить</button></div><script nonce="' + nonce + '">' + boot +
                            '</script><script src="viewer.js"></script></body></html>').encode()
                    return self.response(start, '200 OK', page, mime='text/html; charset=utf-8', nonce=nonce)
                if route == 'viewer.js' and method == 'GET':
                    return self.response(start, '200 OK', (TOOLS / 'rd-graph-viewer.user.js').read_bytes(),
                                         mime='text/javascript; charset=utf-8')
                require(route == 'command' and hmac.compare_digest(env.get('HTTP_X_RDG_SESSION', ''), cap),
                        'SESSION_DENIED')
                require(env.get('HTTP_ORIGIN') == self.origin, 'ORIGIN_DENIED')
            else:
                require(path == '/api/command', 'ROUTE_DENIED')
            require(method == 'POST', 'METHOD_DENIED')
            require(env.get('CONTENT_TYPE', '').split(';')[0] == 'application/json', 'CONTENT_TYPE')
            length = env.get('CONTENT_LENGTH', '')
            require(length.isdigit() and 0 < int(length) <= 1000000, 'REQUEST_SIZE')
            raw = env['wsgi.input'].read(int(length))
            require(len(raw) == int(length), 'REQUEST_SIZE')
            message = json.loads(raw)
            result = endpoint.dispatch(message)
            return self.response(start, '200 OK', result)
        except ValueError as exc:
            code = str(exc).split(':', 1)[0]
            if code == 'RDG_SERVER_AUTH_REQUIRED':
                scheme = 'Bearer' if api else 'Basic'
                return self.response(start, '401 Unauthorized', {'error': 'AUTH_REQUIRED', 'definite': True},
                    extra=[('WWW-Authenticate', scheme + ' realm="RDG", charset="UTF-8"')])
            if code.startswith('RDG_SERVER_') and code.endswith(('DENIED', 'REQUIRED')):
                status = '403 Forbidden'
            elif code.endswith('REQUEST_SIZE'):
                status = '413 Content Too Large'
            else:
                status = '400 Bad Request'
            if not re.fullmatch(r'[A-Z][A-Z0-9_ -]{0,160}', code):
                code = 'REQUEST_REJECTED'
            return self.response(start, status, {'error': code,
                'definite': not str(exc).startswith('WRITER_OUTCOME_UNCONFIRMED')})
        except (OSError, KeyError, TypeError, UnicodeError):
            return self.response(start, '500 Internal Server Error', {'error': 'RDG_SERVER_REQUEST_FAILED',
                'definite': method != 'POST'})


def from_environment():
    return Host(os.environ['RDG_DATA_DIR'], os.environ['RDG_PUBLIC_ORIGIN'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--data-dir', type=Path, required=True)
    init.add_argument('--credentials-dir', type=Path, required=True)
    init.add_argument('--runtime-uid', type=int)
    show = commands.add_parser('show-credential')
    show.add_argument('--credentials-dir', type=Path, required=True)
    show.add_argument('--which', choices=('browser', 'agent', 'owner', 'namespace'), required=True)
    args = parser.parse_args()
    if args.command == 'init':
        print(json.dumps(initialize(args.data_dir, args.credentials_dir, args.runtime_uid)))
    else:
        name = 'namespace-id.txt' if args.which == 'namespace' else args.which + '-token.txt'
        path = outside_code(args.credentials_dir) / name
        require(path.is_file() and not path.is_symlink(), 'CREDENTIAL_UNAVAILABLE')
        print(path.read_text(encoding='utf8').strip())


if __name__ == '__main__':
    main()
