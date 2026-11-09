"""R5 isolated lifecycle drill: safe STOP / ROTATE / START, fake Sonar.

This tests R5's *current startup-loaded* TLS identity and machine grant.
No production containers, host volumes, real machine token, or real Sonar
network/credentials. A3/Repo/Windows are NEVER touched by these tests.
"""
from datetime import datetime, timedelta, timezone
import http.client
import json
from pathlib import Path
import socket
import ssl
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from fortis_approvals import r5_read_server as server
from fortis_approvals.core import Denied
from test_owner_portal import VirtualKey
from test_sonar_read_adapter import FakeRemote


OLD_GRANT = 'R5-LIFECYCLE-TEST-OLD-GRANT-0000000000001'
NEW_GRANT = 'R5-LIFECYCLE-TEST-NEW-GRANT-0000000000002'
SONAR = 'R5-LIFECYCLE-TEST-FAKE-SONAR-ONLY-000001'


class R5VirtualKey(VirtualKey):
    """Real test cryptographic FIDO2 assertions, R5 localhost origin."""
    def client_data(self, opts, typ, *, origin='http://localhost:19103',
                    cross_origin=False):
        return super().client_data(opts, typ, origin=origin,
                                   cross_origin=cross_origin)

    def assert_(self, begin, *, origin='http://localhost:19103',
                uv=True, cross_origin=False):
        return super().assert_(begin, origin=origin, uv=uv,
                               cross_origin=cross_origin)


def create_test_identity(cert_path, key_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(
        NameOID.COMMON_NAME, 'host.docker.internal')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=5))
            .not_valid_after(now+timedelta(hours=2))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName('host.docker.internal')]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False,path_length=None),
                           critical=True)
            .add_extension(x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
            .sign(key,hashes.SHA256()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    key_path.chmod(0o600)


class R5LifecycleOfflineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='r5-lifecycle-fake-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root/'private'
        self.state.mkdir(mode=0o700)
        self.grant = self.root/'grant'
        self.grant.write_text(OLD_GRANT+'\n')
        self.grant.chmod(0o600)
        self.sonar = self.root/'sonar-token'
        self.sonar.write_text(SONAR+'\n')
        self.sonar.chmod(0o600)
        self.cert = self.root/'cert.pem'
        self.key = self.root/'key.pem'
        create_test_identity(self.cert,self.key)
        self.remote = FakeRemote()
        self.running = None
        self.addCleanup(self.stop)

    def start(self):
        self.assertIsNone(self.running)
        with (patch.object(server,'OWNER_PORT',0),
              patch.object(server,'REPO_PORT',0),
              patch.object(server,'SonarHTTPTransport',return_value=self.remote)):
            owner,repo=server.create_servers(
                state=self.state,grant_path=self.grant,
                sonar_token_path=self.sonar,
                cert_path=self.cert,key_path=self.key,
                region='eu',organizations=('trusted_org',),
                bind_host='127.0.0.1')
        thread=Thread(target=repo.serve_forever,daemon=True)
        thread.start()
        self.running = owner,repo,thread
        return owner.get_app().auth

    def stop(self):
        if self.running is None:
            return
        owner,repo,thread=self.running
        self.running=None
        repo.shutdown()
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        owner.server_close()
        repo.server_close()

    def request(self, grant, *, trust=None):
        self.assertIsNotNone(self.running)
        _owner,repo,_thread=self.running
        body=json.dumps({
            'requestId':str(uuid.uuid4()),
            'service':'sonarcloud','operation':'list_issues',
            'target':'trusted_project_000',
            'params':{'page':1,'pageSize':2},
            'reason':'R5 offline rotation acceptance',
        }).encode('utf-8')
        context=ssl.create_default_context(cafile=str(trust or self.cert))
        context.minimum_version=ssl.TLSVersion.TLSv1_3
        with socket.create_connection(
                ('127.0.0.1',repo.server_port),timeout=3) as raw:
            raw.settimeout(3)
            with context.wrap_socket(raw,
                                     server_hostname='host.docker.internal') as tls:
                self.assertEqual(tls.version(),'TLSv1.3')
                client=http.client.HTTPConnection('127.0.0.1')
                client.sock=tls
                client.request('POST','/v1/reads',body=body,headers={
                    'Host':'host.docker.internal:19104',
                    'Content-Type':'application/json',
                    'Authorization':'Bearer '+grant})
                response=client.getresponse()
                return response.status,json.loads(response.read())

    def test_stop_rotate_start_old_grant_denied_new_allow_cert_pin_switch(self):
        owner=self.start()
        key=R5VirtualKey()
        invite=owner.issue_invitation()
        begin=owner.begin_enrollment(invite)
        self.assertTrue(owner.finish_enrollment(
            begin['ceremonyId'],key.enroll(begin))['registered'])
        begin=owner.begin_login()
        old_session,_csrf=owner.finish_login(
            begin['ceremonyId'],key.assert_(begin))
        self.assertEqual(owner.session(old_session)['owner'],'owner')
        self.assertEqual(self.request(OLD_GRANT)[0],200)
        self.assertEqual(self.request(NEW_GRANT)[0],401)
        old_trust=self.root/'old-trust.pem'
        old_trust.write_bytes(self.cert.read_bytes())
        owner_store=(self.state/'owner.sqlite').stat().st_ino
        core_store=(self.state/'approvals.sqlite').stat().st_ino
        marker_before=(self.state/'.fortis-r5-sonar-read-v1').read_bytes()
        self.stop()

        # Offline replacement only, *after stopping the previous process*.
        self.grant.write_text(NEW_GRANT+'\n')
        self.grant.chmod(0o600)
        create_test_identity(self.cert,self.key)
        new_owner=self.start()
        self.assertEqual((self.state/'owner.sqlite').stat().st_ino,
                         owner_store)
        self.assertEqual((self.state/'approvals.sqlite').stat().st_ino,
                         core_store)
        self.assertEqual(
            (self.state/'.fortis-r5-sonar-read-v1').read_bytes(),
            marker_before)
        # The virtual FIDO2 credential survives; browser sessions do not.
        with self.assertRaises(Denied):
            new_owner.session(old_session)
        begin=new_owner.begin_login()
        session,_=new_owner.finish_login(
            begin['ceremonyId'],key.assert_(begin))
        self.assertEqual(new_owner.session(session)['owner'],'owner')
        self.assertEqual(self.request(OLD_GRANT)[0],401)
        self.assertEqual(self.request(NEW_GRANT)[0],200)
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.request(NEW_GRANT, trust=old_trust)
        self.assertTrue(all(x[0]=='GET' for x in self.remote.calls))

    def test_bad_replacement_fails_closed_without_erasing_state(self):
        self.start()
        self.assertEqual(self.request(OLD_GRANT)[0],200)
        self.stop()
        original=(self.state/'.fortis-r5-sonar-read-v1').read_bytes()
        self.grant.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError,'R5_PRIVATE_FILE'):
            self.start()
        self.assertIsNone(self.running)
        self.assertEqual(
            (self.state/'.fortis-r5-sonar-read-v1').read_bytes(),
            original)
        self.grant.chmod(0o600)
        self.key.write_bytes(b'INVALID-KEY-NOT-A-REAL-PEM')
        self.key.chmod(0o600)
        with self.assertRaises((ssl.SSLError,ValueError)):
            self.start()
        self.assertIsNone(self.running)
        self.assertTrue((self.state/'owner.sqlite').exists())
        self.assertTrue((self.state/'approvals.sqlite').exists())


if __name__=='__main__':
    unittest.main()
