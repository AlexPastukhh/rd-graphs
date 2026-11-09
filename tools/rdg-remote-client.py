#!/usr/bin/env python3
"""RDG-only HTTP client: no owner files, shell transport or token forwarding."""
import json
import http.client
from pathlib import Path
import re
import stat
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid


def require(ok, code):
    if not ok:
        raise ValueError('RDG_REMOTE_' + code)


def validate_config(config):
    if isinstance(config, dict) and config.get('profile') == 'gateway':
        require({'profile', 'origin', 'namespaceId'} <= set(config) <=
                {'profile', 'origin', 'namespaceId', 'packageId'} and
                config['origin'] == 'http://rdg-api-gateway:8081', 'GATEWAY_CONTEXT_SCHEMA')
        require(str(uuid.UUID(config['namespaceId'])) == config['namespaceId'], 'NAMESPACE_INVALID')
        return config
    require(isinstance(config, dict) and {'profile', 'origin', 'namespaceId', 'tokenFile'} <= set(config)
            <= {'profile', 'origin', 'namespaceId', 'tokenFile', 'packageId'} and
            config['profile'] == 'remote', 'CONTEXT_SCHEMA')
    origin = config['origin']; parsed = urlsplit(origin)
    require(parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and
            not parsed.password and not parsed.query and not parsed.fragment and not parsed.path and
            origin == parsed.scheme + '://' + parsed.netloc and
            not any(c in origin for c in ('\r', '\n', '\\', ' ')), 'ORIGIN_INVALID')
    require(parsed.scheme == 'https' or parsed.hostname in ('localhost', '127.0.0.1', '::1'),
            'HTTPS_REQUIRED')
    require(str(uuid.UUID(config['namespaceId'])) == config['namespaceId'], 'NAMESPACE_INVALID')
    token = Path(config['tokenFile'])
    require(token.is_absolute() and token.is_file() and
            not any(p.is_symlink() for p in (token, *token.parents)) and
            stat.S_IMODE(token.stat().st_mode) & 0o077 == 0, 'PRIVATE_TOKEN_FILE_REQUIRED')
    return config


class Client:
    def __init__(self, config):
        self.config = validate_config(config)
        self.token = None
        if config['profile'] == 'gateway':
            return
        self.token = Path(config['tokenFile']).read_text(encoding='utf8').strip()
        require(re.fullmatch(r'rdg_[A-Za-z0-9_-]{40,100}', self.token), 'TOKEN_INVALID')

    def catalog(self):
        return self.call({'method': 'catalog'})

    def call(self, message):
        require(isinstance(message, dict), 'MESSAGE_REQUIRED')
        headers = {'Content-Type': 'application/json', 'X-RDG-Namespace': self.config['namespaceId']}
        if self.token is not None:
            headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request(self.config['origin'] + '/api/command',
            data=json.dumps(message, ensure_ascii=False, allow_nan=False).encode(), method='POST',
            headers=headers)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        # Explicit endpoint only. Ambient proxies must not receive scoped credentials.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(request, timeout=60) as response:
                raw = response.read(16000001)
                length = response.headers.get('Content-Length')
                if len(raw) > 16000000 or (length and length.isdigit() and int(length) != len(raw)):
                    error = ValueError('RDG_REMOTE_RESPONSE_UNCONFIRMED: inspect receipt before retry')
                    error.definite = False
                    raise error
                try:
                    return json.loads(raw)
                except (ValueError, UnicodeError):
                    error = ValueError('RDG_REMOTE_INVALID_RESPONSE: inspect receipt before retry')
                    error.definite = False
                    raise error from None
        except urllib.error.HTTPError as exc:
            try:
                failure = json.loads(exc.read(4096)); code = failure.get('error', 'REQUEST_FAILED')
                definite = failure.get('definite', False)
            except (ValueError, AttributeError):
                code, definite = 'HTTP_' + str(exc.code), False
            if exc.code in (301, 302, 303, 307, 308):
                code, definite = 'REDIRECT_DENIED', True
            error = ValueError('RDG_REMOTE_' + code + ('' if definite else ': inspect receipt before retry'))
            error.definite = definite
            raise error from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):
            error = ValueError('RDG_REMOTE_UNAVAILABLE: inspect receipt before retry')
            error.definite = False
            raise error from None


if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = Client(json.loads(args.context.read_text(encoding='utf8'))).call(json.load(sys.stdin))
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
