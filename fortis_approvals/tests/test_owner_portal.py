"""Cryptographic WebAuthn test authenticator and in-process trusted WSGI G2 tests.

Virtual elliptic-curve credential is test-only; NO real human enrollment proven.
Run via the existing isolated fido2 venv (see package README).
"""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
import unittest
import uuid

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from fido2 import cbor
from fido2.cose import ES256
from fido2.utils import websafe_encode

from fortis_approvals.core import Authenticator, Core, Denied
from fortis_approvals.owner_auth import OwnerWebAuthn
from fortis_approvals.owner_portal import OwnerPortal
from fortis_approvals.synthetic import SyntheticAdapter


class VirtualKey:
    """Test-only P-256 authenticator with UP+UV, RP and monotonic counter."""
    def __init__(self):
        self.secret = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = secrets.token_bytes(32)
        self.counter = 0

    def client_data(self, opts, typ, *, origin='http://localhost:18990', cross_origin=False):
        value = {'type': typ, 'challenge': opts['publicKey']['challenge'],
                 'origin': origin}
        if cross_origin: value['crossOrigin'] = True
        return json.dumps(value, separators=(',', ':')).encode()

    def enroll(self, begin):
        client = self.client_data(begin['options'], 'webauthn.create')
        key = cbor.encode(ES256.from_cryptography_key(self.secret.public_key()))
        auth = (hashlib.sha256(b'localhost').digest() + bytes([0x45]) + (0).to_bytes(4,'big')+
                bytes(16) + len(self.cred_id).to_bytes(2,'big') + self.cred_id + key)
        attestation = cbor.encode({'fmt':'none','authData':auth,'attStmt':{}})
        return {'id':websafe_encode(self.cred_id),'rawId':websafe_encode(self.cred_id),
                'type':'public-key','response':{'clientDataJSON':websafe_encode(client),
                'attestationObject':websafe_encode(attestation)}}

    def assert_(self, begin, *, origin='http://localhost:18990', uv=True, cross_origin=False):
        self.counter += 1
        client=self.client_data(begin['options'],'webauthn.get', origin=origin,cross_origin=cross_origin)
        auth=hashlib.sha256(b'localhost').digest() + bytes([0x05 if uv else 0x01]) + self.counter.to_bytes(4,'big')
        signed=auth+hashlib.sha256(client).digest()
        signature=self.secret.sign(signed,ec.ECDSA(hashes.SHA256()))
        return {'id':websafe_encode(self.cred_id),'rawId':websafe_encode(self.cred_id),
                'type':'public-key','response':{'authenticatorData':websafe_encode(auth),
                'clientDataJSON':websafe_encode(client),'signature':websafe_encode(signature),
                'userHandle':None}}


class G2WebAuthnTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fortis-g2-')
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.adapter=SyntheticAdapter(root/'fake.sqlite')
        self.adapter.seed('R3','before')
        self.owner=OwnerWebAuthn(root/'credentials.sqlite',origin='http://localhost:18990')
        self.auth=Authenticator({'agent-secret':'agent-1'})
        self.core=Core(root/'requests.sqlite',adapters={'synthetic':self.adapter},
                       policies={('synthetic','set_ask'):'ASK'},authenticator=self.auth,
                       owner_verifier=self.owner)
        self.portal=OwnerPortal(self.core,self.owner)
        self.key=VirtualKey()
        self.invite=self.owner.issue_invitation()

    def action(self):
        return dict(requestId=str(uuid.uuid4()),service='synthetic',operation='set_ask',
                    target='R3',params={'value':'after'},expectedVersion=0,reason='test')

    def call(self,path,body=None,cookie=None,csrf=None,origin='http://localhost:18990',method=None):
        raw=body if isinstance(body,bytes) else json.dumps(body or {}).encode()
        env={'HTTP_HOST':'localhost:18990','REQUEST_METHOD':method or ('POST' if body is not None else 'GET'),
             'PATH_INFO':path,'QUERY_STRING':'','wsgi.input':BytesIO(raw),
             'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json'}
        if method == 'POST' or body is not None:env['HTTP_ORIGIN']=origin
        if cookie:env['HTTP_COOKIE']='fortis_owner='+cookie
        if csrf:env['HTTP_X_FORTIS_CSRF']=csrf
        out=[]
        raw_resp=b''.join(self.portal(env,lambda status,headers:out.append((status,dict(headers)))))
        code=int(out[0][0][:3]);headers=out[0][1]
        value=json.loads(raw_resp) if 'application/json' in headers['Content-Type'] else raw_resp
        return code,value,headers

    def enroll(self):
        code,b,_=self.call('/v1/enroll/begin',{'invitation':self.invite})
        self.assertEqual(code,200,b)
        code,b,_=self.call('/v1/enroll/finish',{'ceremonyId':b['ceremonyId'],
                                               'response':self.key.enroll(b)})
        self.assertEqual(code,200,b)

    def login(self):
        code,b,_=self.call('/v1/login/begin',{})
        self.assertEqual(code,200,b)
        code,b,h=self.call('/v1/login/finish',{'ceremonyId':b['ceremonyId'],
                                              'response':self.key.assert_(b)})
        self.assertEqual(code,200,b)
        self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('SameSite=Strict',h['Set-Cookie'])
        return h['Set-Cookie'].split(';',1)[0].split('=',1)[1],b['csrf']

    def test_full_enroll_login_and_approve_exact(self):
        record=self.core.client('agent-secret','submit',self.action())
        self.assertEqual(record['state'],'PENDING')
        self.assertEqual(self.call('/v1/owner/pending')[0],403)
        self.enroll();cookie,csrf=self.login()
        self.assertEqual(self.call('/v1/owner/pending',cookie=cookie)[1][0]['requestId'],record['requestId'])
        code,b,_=self.call('/v1/owner/decision/begin',{'requestId':record['requestId'],
                                                     'decision':'approve'},cookie=cookie,csrf=csrf)
        self.assertEqual(code,200,b)
        code,answer,_=self.call('/v1/owner/decision/finish',
            {'requestId':record['requestId'],'decision':'approve','ceremonyId':b['ceremonyId'],
             'response':self.key.assert_(b)},cookie=cookie,csrf=csrf)
        self.assertEqual(code,200,answer)
        self.assertEqual(answer['state'],'EXECUTED')
        self.assertEqual(self.adapter.get('R3'),{'version':1,'value':'after'})
        self.assertEqual(len(self.call('/v1/owner/history',cookie=cookie)[1]),1)
        self.assertEqual(len(self.call('/v1/owner/pending',cookie=cookie)[1]),0)
        self.assertEqual(self.core.client('agent-secret','status',record['requestId'])['state'],'EXECUTED')

    def test_reject_creates_audit_without_write(self):
        record=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        _,begin,_=self.call('/v1/owner/decision/begin',{'requestId':record['requestId'],
                                     'decision':'reject'},cookie=cookie,csrf=csrf)
        code,out,_=self.call('/v1/owner/decision/finish',{'requestId':record['requestId'],
                         'decision':'reject','ceremonyId':begin['ceremonyId'],
                         'response':self.key.assert_(begin)},cookie=cookie,csrf=csrf)
        self.assertEqual((code,out['state']),(200,'REJECTED'))
        self.assertEqual(self.adapter.get('R3')['version'],0)

    def test_login_required_origin_csrf_and_no_admin_routes(self):
        self.enroll();cookie,csrf=self.login()
        self.assertEqual(self.call('/v1/owner/pending')[0],403)
        self.assertEqual(self.call('/v1/owner/pending',cookie=cookie)[0],200)
        self.assertEqual(self.call('/v1/owner/decision/begin',{'requestId':str(uuid.uuid4()),
                      'decision':'approve'},cookie=cookie)[0],403)
        self.assertEqual(self.call('/v1/owner/decision/begin',{'requestId':str(uuid.uuid4()),
                      'decision':'approve'},cookie=cookie,csrf=csrf,origin='https://evil.test')[0],403)
        self.assertEqual(self.call('/v1/owner/admin/invite',{},cookie=cookie,csrf=csrf)[0],404)
        self.assertEqual(self.call('/v1/owner/pending',cookie=cookie,method='POST')[0],403)

    def test_invalid_invite_and_no_self_enrollment(self):
        self.assertEqual(self.call('/v1/enroll/begin',{'invitation':'forged'*7})[0],403)
        self.enroll()
        self.assertEqual(self.call('/v1/enroll/begin',{'invitation':self.invite})[0],403)
        with self.assertRaises(Denied):
            self.owner.finish_enrollment('forged',{})

    def test_signatures_binding_and_replay(self):
        record=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        _,begin,_=self.call('/v1/owner/decision/begin',
            {'requestId':record['requestId'],'decision':'approve'},cookie=cookie,csrf=csrf)
        assert0=self.key.assert_(begin)
        result=self.call('/v1/owner/decision/finish',
            {'requestId':record['requestId'],'decision':'reject',
             'ceremonyId':begin['ceremonyId'],'response':assert0},cookie=cookie,csrf=csrf)
        self.assertEqual(result[0],403)
        self.assertEqual(self.adapter.get('R3')['version'],0)
        # The mismatch consumed the ceremony. A replay cannot complete it.
        self.assertEqual(self.call('/v1/owner/decision/finish',
            {'requestId':record['requestId'],'decision':'approve',
             'ceremonyId':begin['ceremonyId'],'response':assert0},cookie=cookie,csrf=csrf)[0],403)
        # Origin modification invalidates an independent assertion.
        _,begin2,_=self.call('/v1/owner/decision/begin',
            {'requestId':record['requestId'],'decision':'approve'},cookie=cookie,csrf=csrf)
        code,_,_=self.call('/v1/owner/decision/finish',
            {'requestId':record['requestId'],'decision':'approve','ceremonyId':begin2['ceremonyId'],
             'response':self.key.assert_(begin2,origin='https://evil.test')},cookie=cookie,csrf=csrf)
        self.assertEqual(code,403)
        self.assertEqual(self.adapter.get('R3')['version'],0)

    def test_owner_session_expires_and_relogin_is_required(self):
        self.enroll();cookie,csrf=self.login()
        self.assertEqual(self.call('/v1/owner/pending',cookie=cookie)[0],200)
        old=self.owner.clock
        self.owner.clock=lambda:old()+self.owner.session_ttl+3
        self.assertEqual(self.call('/v1/owner/pending',cookie=cookie)[0],403)
        self.assertEqual(self.call('/v1/owner/decision/session',
            {'requestId':str(uuid.uuid4()),'fingerprint':'0'*64,'decision':'approve'},
            cookie=cookie,csrf=csrf)[0],403)

    def test_user_verification_required_for_decision(self):
        record=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        _,begin,_=self.call('/v1/owner/decision/begin',
            {'requestId':record['requestId'],'decision':'approve'},cookie=cookie,csrf=csrf)
        response=self.key.assert_(begin,uv=False)
        code,_,_=self.call('/v1/owner/decision/finish',
            {'requestId':record['requestId'],'decision':'approve',
             'ceremonyId':begin['ceremonyId'],'response':response},cookie=cookie,csrf=csrf)
        self.assertEqual(code,403)
        self.assertEqual(self.adapter.get('R3')['version'],0)

    def test_login_ceremony_capacity_and_reuse_denied(self):
        self.enroll()
        for _ in range(128): self.owner.begin_login()
        with self.assertRaises(Denied): self.owner.begin_login()
        self.assertEqual(self.call('/v1/owner/pending')[0],403)

    def test_owner_origin_binding_is_persistent(self):
        self.enroll()
        with self.assertRaises(Denied):
            OwnerWebAuthn(self.owner.path,origin='http://localhost:18991')

    def test_session_approval_without_second_webauthn_and_replay(self):
        record=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        code,result,_=self.call('/v1/owner/decision/session',
            {'requestId':record['requestId'], 'fingerprint':record['fingerprint'],
             'decision':'approve'},cookie=cookie,csrf=csrf)
        self.assertEqual((code,result['state']), (200,'EXECUTED'))
        self.assertEqual(self.adapter.get('R3')['version'],1)
        self.assertEqual(self.call('/v1/owner/decision/session',
            {'requestId':record['requestId'], 'fingerprint':record['fingerprint'],
             'decision':'approve'},cookie=cookie,csrf=csrf)[0],403)

    def test_session_reject_without_second_webauthn(self):
        record=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        code,result,_=self.call('/v1/owner/decision/session',
            {'requestId':record['requestId'], 'fingerprint':record['fingerprint'],
             'decision':'reject'},cookie=cookie,csrf=csrf)
        self.assertEqual((code,result['state']),(200,'REJECTED'))
        self.assertEqual(self.adapter.get('R3')['version'],0)

    def test_session_approve_requires_valid_csrf_origin_and_exact_fingerprint(self):
        record=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        body={'requestId':record['requestId'], 'fingerprint':record['fingerprint'],
              'decision':'approve'}
        self.assertEqual(self.call('/v1/owner/decision/session',body,cookie=cookie)[0],403)
        self.assertEqual(self.call('/v1/owner/decision/session',body,cookie=cookie,
                                   csrf='forged')[0],403)
        self.assertEqual(self.call('/v1/owner/decision/session',body,cookie=cookie,
                                   csrf=csrf,origin='https://evil.test')[0],403)
        self.assertEqual(self.call('/v1/owner/decision/session',{**body,'fingerprint':'0'*64},
                                   cookie=cookie,csrf=csrf)[0],403)
        self.assertEqual(self.call('/v1/owner/decision/session',{**body,'decision':'unexpected'},
                                   cookie=cookie,csrf=csrf)[0],403)
        self.assertEqual(self.call('/v1/owner/decision/session',body,csrf=csrf)[0],403)
        self.assertEqual(self.adapter.get('R3')['version'],0)

    def test_strong_operations_cannot_use_session_only(self):
        self.portal=OwnerPortal(self.core,self.owner, strong_operations={('synthetic','set_ask')})
        record=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        pending=self.call('/v1/owner/pending',cookie=cookie)[1]
        self.assertTrue(pending[0]['requiresStrongProof'])
        body={'requestId':record['requestId'], 'fingerprint':record['fingerprint'],'decision':'approve'}
        self.assertEqual(self.call('/v1/owner/decision/session',body,cookie=cookie,csrf=csrf)[0],403)
        _,begin,_=self.call('/v1/owner/decision/begin',
            {'requestId':record['requestId'],'decision':'approve'},cookie=cookie,csrf=csrf)
        code,result,_=self.call('/v1/owner/decision/finish',
            {'requestId':record['requestId'],'decision':'approve','ceremonyId':begin['ceremonyId'],
             'response':self.key.assert_(begin)},cookie=cookie,csrf=csrf)
        self.assertEqual((code,result['state']),(200,'EXECUTED'))

    def test_one_use_session_proof_is_bound_to_request_and_decision(self):
        row=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        proof=self.owner.begin_session_decision(cookie,row['requestId'],row['fingerprint'],'approve')
        with self.assertRaises(Denied):
            self.owner.verify(row['requestId'],row['fingerprint'],'reject',proof)
        with self.assertRaises(Denied):
            self.owner.verify(row['requestId'],row['fingerprint'],'approve',proof)
        self.assertEqual(self.adapter.get('R3')['version'],0)

    def test_session_proof_invalid_after_revocation_or_restart(self):
        row=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        proof=self.owner.begin_session_decision(cookie,row['requestId'],row['fingerprint'],'approve')
        self.owner.revoke_credentials()
        with self.assertRaises(Denied):
            self.owner.verify(row['requestId'],row['fingerprint'],'approve',proof)

    def test_strict_json_boundary_rejects_duplicate_nonfinite_and_deep_payloads(self):
        duplicate=(b'{"requestId":"00000000-0000-4000-8000-000000000001",'
                   b'"requestId":"00000000-0000-4000-8000-000000000002",'
                   b'"fingerprint":"' + b'0'*64 + b'","decision":"approve"}')
        nonfinite=(b'{"requestId":"00000000-0000-4000-8000-000000000001",'
                   b'"fingerprint":1e9999,"decision":"approve"}')
        deeply_nested=b'{"nested":'+b'['*1200+b'0'+b']'*1200+b'}'
        for body in (duplicate,nonfinite,deeply_nested):
            with self.subTest(prefix=body[:24]):
                code,result,_=self.call('/v1/owner/decision/session',body)
                self.assertEqual(code,400)
                self.assertEqual(result['error'],'REQUEST_INVALID')
        self.assertEqual(self.adapter.get('R3')['version'],0)

    def test_stale_preview_blocks_real_owner_session_decision(self):
        record=self.core.client('agent-secret','submit',self.action())
        self.enroll();cookie,csrf=self.login()
        with self.adapter._db() as db:
            db.execute('UPDATE objects SET value=?,version=? WHERE id=?',
                       ('external-change',1,'R3'))
        code,result,_=self.call('/v1/owner/decision/session',
            {'requestId':record['requestId'],'fingerprint':record['fingerprint'],
             'decision':'approve'},cookie=cookie,csrf=csrf)
        self.assertEqual((code,result['state']),(200,'STALE'))
        self.assertEqual(self.adapter.get('R3'),{'value':'external-change','version':1})
        self.assertIsNone(self.adapter.receipt(record['requestId']))

    def test_credential_persist_and_fail_closed_restart(self):
        self.enroll();cookie,csrf=self.login()
        self.owner=OwnerWebAuthn(self.owner.path,origin='http://localhost:18990')
        self.assertRaises(Denied,self.owner.session,cookie)
        self.core.owner_verifier=self.owner
        self.portal=OwnerPortal(self.core,self.owner)
        self.assertEqual(self.call('/v1/owner/pending',cookie=cookie)[0],403)
        cookie,csrf=self.login()
        self.assertEqual(self.call('/v1/owner/pending',cookie=cookie)[0],200)
        self.owner.revoke_credentials()
        self.assertEqual(self.call('/v1/owner/pending',cookie=cookie)[0],403)
        self.assertEqual(self.call('/v1/login/begin',{})[0],403)


if __name__=='__main__':unittest.main()
