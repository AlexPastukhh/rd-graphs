"""Actual localhost WSGI subprocess/restart + owner-only CLI synthetic scenario.

No Docker daemon, RDG or Sonar is involved.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from fortis_approvals.runtime import build_runtime, settings
from fortis_approvals.core import Denied


class G2RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fortis-g2-runtime-')
        self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name)
        self.state.chmod(0o700)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            self.port=sock.getsockname()[1]
        self.env={**os.environ,'FORTIS_STATE_DIR':str(self.state),
                  'FORTIS_PORT':str(self.port),
                  'FORTIS_OWNER_ORIGIN':f'http://localhost:{self.port}',
                  'PYTHONDONTWRITEBYTECODE':'1'}
        self.open=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.server=None
        self.addCleanup(self.stop_server)

    def start_server(self):
        self.server=subprocess.Popen([sys.executable,'-B','-m','fortis_approvals.server'],
                      env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(75):
            if self.server.poll() is not None:
                raise AssertionError('service exited: '+self.server.stderr.read().decode()[-1200:])
            try:
                with self.open.open(f'http://localhost:{self.port}/',timeout=.3) as result:
                    if result.read().find(b'Fortis Approvals')>=0:
                        return
            except (OSError,urllib.error.URLError):
                time.sleep(.04)
        raise AssertionError('service did not become reachable')

    def stop_server(self):
        if self.server and self.server.poll() is None:
            self.server.terminate()
            try:self.server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.server.kill();self.server.wait(timeout=3)
        if self.server and self.server.stderr:self.server.stderr.close()
        self.server=None

    def operator(self, action):
        return subprocess.run([sys.executable,'-B','-m','fortis_approvals.operator',action],
                    env=self.env,capture_output=True,text=True,timeout=6,check=True).stdout

    def test_always_on_owner_service_and_operator_cli_persist_across_restart(self):
        self.start_server()
        address=f'http://localhost:{self.port}'
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.open.open(address+'/v1/owner/pending',timeout=2)
        self.assertEqual(failure.exception.code,403)
        self.assertIn(b'OWNER_SESSION_REQUIRED', failure.exception.read())
        # A browser/app can add marketing query parameters; the portal rejects
        # these before attempting authentication (a different 403 reason).
        with self.assertRaises(urllib.error.HTTPError) as tracking:
            self.open.open(address+'/v1/owner/pending?utm_source=chatgpt.com',timeout=2)
        self.assertEqual(tracking.exception.code,403)
        self.assertIn(b'HOST_DENIED',tracking.exception.read())
        output=self.operator('seed')
        self.assertIn('PENDING',output)
        invitation=self.operator('invite')
        self.assertIn('One-use owner enrollment invitation',invitation)
        self.assertEqual(len(invitation.splitlines()[-1]),43)
        self.assertIn('Pending: 1',self.operator('inspect'))
        self.stop_server()
        self.start_server()
        self.assertIn('Pending: 1',self.operator('inspect'))
        with self.open.open(address+'/app.js',timeout=2) as result:
            self.assertIn(b'Notification.requestPermission',result.read())
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.open.open(address+'/v1/owner/history',timeout=2)
        self.assertEqual(failure.exception.code,403)

    def test_stalled_http_post_does_not_block_other_clients(self):
        """A partial Content-Length request must not freeze all owner UI GETs."""
        self.start_server()
        with socket.create_connection(('127.0.0.1',self.port),timeout=3) as slow:
            slow.sendall((f'POST /v1/login/begin HTTP/1.1\r\n'
                          f'Host: localhost:{self.port}\r\n'
                          f'Origin: http://localhost:{self.port}\r\n'
                          'Content-Type: application/json\r\n'
                          'Content-Length: 200\r\n'
                          'Connection: close\r\n\r\n'+'{').encode())
            # This stalls on body read; independent GET should still get a fast
            # response from another worker, not wait 10 seconds for timeout.
            time.sleep(.12)
            start=time.perf_counter()
            with self.open.open(f'http://localhost:{self.port}/',timeout=2) as result:
                self.assertEqual(result.status,200)
            self.assertLess(time.perf_counter()-start,1.4)

    def test_private_state_directory_required(self):
        self.state.chmod(0o755)
        old=dict(os.environ)
        try:
            os.environ.update(self.env)
            with self.assertRaises(Denied):
                settings()
        finally:
            os.environ.clear();os.environ.update(old)


if __name__=='__main__': unittest.main()
