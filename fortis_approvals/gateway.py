"""G1 WSGI typed client surface. No owner/admin routes, no network listener.

A trusted deployment must supply credentials, fixed host and TLS/ingress rules.
The G2 owner session/verifier is deliberately not implemented here.
"""
import json
import re

from .core import ApprovalError, Conflict, Denied, loads_strict


class ClientGateway:
    def __init__(self, core, *, host):
        if not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,200}', host):
            raise ValueError('HOST_INVALID')
        self.core = core
        self.host = host

    @staticmethod
    def _reply(start, code, body):
        encoded = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        labels = {200: 'OK', 202: 'Accepted', 400: 'Bad Request', 401: 'Unauthorized',
                  403: 'Forbidden', 404: 'Not Found', 409: 'Conflict', 413: 'Payload Too Large',
                  500: 'Internal Server Error'}
        start(f'{code} {labels[code]}', [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Content-Length', str(len(encoded))), ('Cache-Control', 'no-store'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")])
        return [encoded]

    def __call__(self, env, start):
        try:
            if env.get('HTTP_HOST') != self.host or env.get('QUERY_STRING') or any(
                env.get(key) for key in ('HTTP_X_FORWARDED_HOST', 'HTTP_FORWARDED',
                                         'HTTP_ORIGIN', 'HTTP_COOKIE', 'HTTP_PROXY_AUTHORIZATION')):
                raise Denied('INGRESS_DENIED')
            method, path = env.get('REQUEST_METHOD'), env.get('PATH_INFO', '')
            if method == 'GET' and path == '/healthz':
                return self._reply(start, 200, {'service': 'fortis-approvals-g1', 'status': 'ok'})
            credential = env.get('HTTP_AUTHORIZATION', '')
            if not credential.startswith('Bearer ') or len(credential) > 1024:
                return self._reply(start, 401, {'error': 'CLIENT_UNAUTHORIZED'})
            token = credential[7:]
            if method == 'POST' and path == '/v1/actions':
                if env.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
                    return self._reply(start, 400, {'error': 'CONTENT_TYPE'})
                length = env.get('CONTENT_LENGTH', '')
                if not length.isdecimal() or int(length) > 32768 or int(length) == 0:
                    return self._reply(start, 413, {'error': 'REQUEST_SIZE'})
                body = env['wsgi.input'].read(int(length))
                if len(body) != int(length):
                    return self._reply(start, 400, {'error': 'REQUEST_SIZE'})
                try:
                    value = loads_strict(body)
                except (ValueError, TypeError, UnicodeError, RecursionError):
                    raise ValueError('REQUEST_JSON') from None
                result = self.core.client(token, 'submit', value)
                return self._reply(start, 202 if result['state'] == 'PENDING' else 200, result)
            match = re.fullmatch(r'/v1/requests/([0-9a-f-]{36})', path)
            if method == 'GET' and match:
                return self._reply(start, 200, self.core.client(token, 'status', match.group(1)))
            return self._reply(start, 404, {'error': 'ROUTE_NOT_FOUND'})
        except Conflict as exc:
            return self._reply(start, 409, {'error': str(exc)})
        except Denied as exc:
            return self._reply(start, 403, {'error': str(exc)})
        except (ApprovalError, ValueError, TypeError, KeyError, UnicodeError):
            return self._reply(start, 400, {'error': 'REQUEST_REJECTED'})
        except (OSError, RuntimeError):
            return self._reply(start, 500, {'error': 'OUTCOME_UNCONFIRMED'})
