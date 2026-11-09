"""R5 source candidate: real local TLS1.3 wire with fake Sonar transport.

No Windows, no real token, no Sonar API/network calls. Localhost test ports
are ephemeral; all private files and state are disposable.
"""
from datetime import datetime, timedelta, timezone
import http.client
import json
from pathlib import Path
import socket
import ssl
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from fortis_approvals import r5_read_server as server
from test_sonar_read_adapter import FakeRemote


GRANT='R5-ONLY-SYNTHETIC-GRANT-000000001'
SONAR_TOKEN='R5-SYNTHETIC-SONAR-TOKEN-NOT-REAL-0000001'


class R5TLSWireTests(unittest.TestCase):
    def setUp(self):
        temporary=TemporaryDirectory(prefix='fortis-r5-tls-offline-')
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        state=root/'state'
        state.mkdir(mode=0o700)
        self.remote=FakeRemote()
        self.grant_path=root/'grant'
        self.grant_path.write_text(GRANT+'\n')
        self.grant_path.chmod(0o600)
        self.token_path=root/'sonar-token'
        self.token_path.write_text(SONAR_TOKEN+'\n')
        self.token_path.chmod(0o600)
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(
            NameOID.COMMON_NAME,'host.docker.internal')])
        now=datetime.now(timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(key.public_key())
              .serial_number(x509.random_serial_number())
              .not_valid_before(now-timedelta(minutes=5))
              .not_valid_after(now+timedelta(hours=1))
              .add_extension(x509.SubjectAlternativeName([
                  x509.DNSName('host.docker.internal')]),critical=False)
              .add_extension(x509.BasicConstraints(ca=False,path_length=None),
                             critical=True)
              .add_extension(x509.ExtendedKeyUsage([
                  ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
              .sign(key,hashes.SHA256()))
        self.cert_path=root/'cert.pem'
        self.cert_path.write_bytes(
            cert.public_bytes(serialization.Encoding.PEM))
        key_path=root/'key.pem'
        key_path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        key_path.chmod(0o600)
        with (patch.object(server,'OWNER_PORT',0),
              patch.object(server,'REPO_PORT',0),
              patch.object(server,'SonarHTTPTransport',return_value=self.remote)
              as transport):
            self.owner,self.repo=server.create_servers(
                state=state,grant_path=self.grant_path,
                sonar_token_path=self.token_path,
                cert_path=self.cert_path,key_path=key_path,
                region='eu',organizations=('trusted_org',),
                bind_host='127.0.0.1')
        self.assertEqual(transport.call_count,1)
        self.assertEqual(transport.call_args.kwargs['bearer_token'],SONAR_TOKEN)
        self.addCleanup(self.owner.server_close)
        self.addCleanup(self.repo.server_close)
        self.threads=[]
        for instance in (self.owner,self.repo):
            thread=Thread(target=instance.serve_forever,daemon=True)
            thread.start()
            self.threads.append(thread)
        self.addCleanup(self.shutdown)

    def shutdown(self):
        for instance in (self.repo,self.owner):
            instance.shutdown()
        for thread in self.threads:
            thread.join(timeout=3)

    def request(self, operation='list_issues', *, target='trusted_project_000',
                params=None, grant=GRANT, path='/v1/reads',
                server_hostname='host.docker.internal'):
        payload=json.dumps({
            'requestId':str(uuid.uuid4()),'service':'sonarcloud',
            'operation':operation,'target':target,
            'params':params if params is not None else
                     {'page':1,'pageSize':2},
            'reason':'R5 TLS offline check',
        }).encode()
        ctx=ssl.create_default_context(cafile=str(self.cert_path))
        ctx.minimum_version=ssl.TLSVersion.TLSv1_3
        with socket.create_connection(
                ('127.0.0.1',self.repo.server_port),timeout=4) as raw:
            raw.settimeout(4)
            with ctx.wrap_socket(raw,server_hostname=server_hostname) as tls:
                self.assertEqual(tls.version(),'TLSv1.3')
                client=http.client.HTTPConnection('127.0.0.1')
                client.sock=tls
                headers={'Host':'host.docker.internal:19104',
                         'Content-Type':'application/json'}
                if grant is not None:
                    headers['Authorization']='Bearer '+grant
                client.request('POST',path,body=payload,headers=headers)
                response=client.getresponse()
                return response.status,json.loads(response.read())

    def test_real_pinned_tls13_read_and_default_deny(self):
        code,data=self.request()
        self.assertEqual(code,200)
        self.assertEqual(data['data']['operation'],'list_issues')
        self.assertEqual(len(data['data']['issues']),2)
        self.assertNotIn(GRANT,json.dumps(data))
        self.assertNotIn(SONAR_TOKEN,json.dumps(data))
        self.assertEqual(self.request(grant=None)[0],401)
        self.assertEqual(self.request(grant='other-test-grant')[0],401)
        self.assertEqual(self.request(path='/v1/actions')[0],403)
        self.assertEqual(self.request(path='/v1/owner/pending')[0],404)
        self.assertEqual(self.request(operation='accept_issue',params={
            'projectKey':'trusted_project_000'})[0],403)
        self.assertTrue(all(call[0]=='GET' for call in self.remote.calls))

    def test_tls_wrong_hostname_refused(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.request(server_hostname='incorrect.invalid')
        self.assertFalse(self.remote.calls)

    def test_existing_owner_ui_available_without_exposing_token(self):
        connection=http.client.HTTPConnection('127.0.0.1',
                                               self.owner.server_port,timeout=4)
        try:
            connection.request('GET','/',headers={'Host':'localhost:19103'})
            response=connection.getresponse()
            html=response.read().decode()
            self.assertEqual(response.status,200)
            self.assertIn('Fortis Approvals',html)
            self.assertNotIn(SONAR_TOKEN,html)
            self.assertNotIn(GRANT,html)
        finally:
            connection.close()


if __name__=='__main__':
    unittest.main()
