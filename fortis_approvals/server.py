"""G2 owner-only WSGI runtime with bounded request concurrency.

Separate owner UI, bound on Docker loopback publication. No AI/client Gateway.
A slow local HTTP client must not block the owner queue or sign-in page.
"""
from socketserver import ThreadingMixIn
from threading import BoundedSemaphore
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server


class OwnerHTTPServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 32

    def __init__(self, *args, **kwargs):
        self._slots = BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        self._slots.acquire()
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def get_request(self):
        conn, addr = super().get_request()
        conn.settimeout(10)  # Avoid indefinitely blocking on partial request bodies.
        return conn, addr


class OwnerRequestHandler(WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        # The UI polls every 5 seconds: do not write an access log for each 200.
        # Keep unexpected 4xx/5xx responses observable in Docker logs.
        if str(code).startswith(('4', '5')):
            super().log_request(code, size)


def main():
    # G2 synthetic runtime is not part of R5's read-only import graph.
    from .runtime import build_portal
    portal, port = build_portal()
    print(f'Fortis Approvals G2 owner UI ready on container port {port}', flush=True)
    with make_server('0.0.0.0', port, portal,
                     server_class=OwnerHTTPServer,
                     handler_class=OwnerRequestHandler) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
