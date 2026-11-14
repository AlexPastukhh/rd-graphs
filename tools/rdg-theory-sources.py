"""Bounded, read-only theory sources. No local paths or ambient HTTP credentials."""
import hashlib
import http.client
import ipaddress
import socket
import ssl
import time
import queue
import threading
from urllib.parse import urlsplit, urljoin


MAX_BYTES = 1024 * 1024
TIMEOUT = 5


def url_parts(uri):
    try:
        p = urlsplit(uri)
        valid = (p.scheme == 'https' and p.hostname and not p.username and
                 not p.password and p.port in (None, 443) and
                 not any(c.isspace() or ord(c) < 32 for c in uri))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError('THEORY_SOURCE_HTTPS_REQUIRED')
    return p


def public_addresses(host):
    # The platform resolver has no timeout argument. Keep it off the serving
    # thread, and never permit the abandoned resolver to perform network I/O.
    result = queue.Queue(maxsize=1)
    def lookup():
        try:
            result.put(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        except OSError as exc:
            result.put(exc)
    threading.Thread(target=lookup, daemon=True).start()
    try:
        values = result.get(timeout=TIMEOUT)
    except queue.Empty:
        raise TimeoutError('DNS timeout') from None
    if isinstance(values, OSError):
        raise values
    addresses = list(dict.fromkeys(v[4][0] for v in values))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError('THEORY_SOURCE_PUBLIC_ADDRESS_REQUIRED')
    return addresses


class PublicHTTPS(http.client.HTTPSConnection):
    """Connect to a validated address; keep the original TLS/HTTP host identity."""
    def __init__(self, host, address):
        super().__init__(host, timeout=TIMEOUT, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def text_source(data, media, expected_sha=None):
    sha = hashlib.sha256(data).hexdigest()
    if expected_sha is not None and sha != expected_sha:
        return {'status': 'changed', 'sha256': sha, 'contentLoaded': False}
    if not (media.startswith('text/') or media.split(';')[0] in
            ('application/json', 'application/xml', 'application/javascript')):
        return {'status': 'unsupported-media', 'mediaType': media,
                'sha256': sha, 'contentLoaded': False}
    try:
        # Lossless text only; unsupported encodings remain an explicit source state.
        content = data.decode('utf-8-sig')
    except UnicodeError:
        return {'status': 'unsupported-encoding', 'sha256': sha, 'contentLoaded': False}
    return {'status': 'available', 'content': content, 'contentLoaded': True,
            'mediaType': media, 'sha256': sha, 'bytes': len(data)}


def fetch_https(target, *, max_bytes=MAX_BYTES, connection=PublicHTTPS,
                addresses=public_addresses):
    """Explicit source expansion only. Redirects get the same independent checks."""
    uri = target['uri']
    deadline = time.monotonic() + TIMEOUT
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('Source timeout')
        return value
    try:
        for redirect in range(4):
            parsed = url_parts(uri)
            address = addresses(parsed.hostname)[0]
            client = connection(parsed.hostname, address)
            client.timeout = remaining()
            try:
                path = parsed.path or '/'
                if parsed.query:
                    path += '?' + parsed.query
                client.request('GET', path, headers={
                    'Accept': 'text/plain, text/markdown, text/html, application/json',
                    'Accept-Encoding': 'identity', 'User-Agent': 'RDG-Theory-Reader/1'})
                response = client.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader('Location')
                    if not location or redirect == 3:
                        return {'status': 'redirect-limit', 'contentLoaded': False}
                    uri = urljoin(uri, location)
                    continue
                if response.status != 200:
                    return {'status': 'unavailable', 'httpStatus': response.status,
                            'contentLoaded': False}
                if response.getheader('Content-Encoding', 'identity') != 'identity':
                    return {'status': 'unsupported-encoding', 'contentLoaded': False}
                chunks, size = [], 0
                while size <= max_bytes:
                    if client.sock:
                        client.sock.settimeout(remaining())
                    else:
                        remaining()
                    chunk = response.read1(min(65536, max_bytes + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                data = b''.join(chunks)
                if len(data) > max_bytes:
                    return {'status': 'budget-exceeded', 'contentLoaded': False,
                            'maxBytes': max_bytes}
                return {**text_source(data, response.getheader('Content-Type', 'text/plain'),
                                      target.get('sha256')), 'uri': uri}
            finally:
                client.close()
    except (ValueError, OSError, http.client.HTTPException):
        # Do not expose network diagnostics, addresses, credentials or response bodies.
        return {'status': 'unavailable', 'contentLoaded': False}
