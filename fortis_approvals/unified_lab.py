"""OFFLINE composition proof: one Fortis Approvals for synthetic + Sonar ASK.

Lab only: in-memory fake Sonar, independent temporary SQLite and WebAuthn,
no real token, HTTP listener, Docker image, or live G2/G4 state migration.
ALLOW and approved ASK both use the SAME existing Core.execute().
"""
import os
from pathlib import Path
import stat

from .core import Authenticator, Core, Denied
from .g4_candidate import NoWriteTransport, G4_OPERATION
from .owner_auth import OwnerWebAuthn
from .owner_portal import OwnerPortal
from .sonar import SonarIssueAdapter
from .synthetic import SyntheticAdapter

LAB_ORIGIN = 'http://localhost:18992'  # test origin only; no port opened
LAB_ORGANIZATION = 'unifiedlab'
LAB_PROJECT = 'unifiedlab_project'
LAB_ISSUE = 'LAB-1'
LAB_MARKER = '.fortis-unified-offline-lab-v1'
SYNTHETIC_CREDENTIAL = 'unified-lab-synthetic-only'
SONAR_CREDENTIAL = 'unified-lab-sonar-proposal-only'


class UnifiedFakeSonar:
    """Fixed in-memory scope; any POST raises before network or state mutation."""
    def __init__(self):
        self.calls = []
        self.posts = 0
        self.issue = dict(key=LAB_ISSUE, project=LAB_PROJECT,
                          issueStatus='OPEN', updateDate='2026-10-31T00:00:00+0000',
                          message='synthetic unified preview', rule='python:S100',
                          severity='MAJOR', component=LAB_PROJECT+':lab.py',
                          assignee=None, type='CODE_SMELL')

    def call(self, method, path, params):
        self.calls.append((method,path,dict(params)))
        if method != 'GET':
            self.posts += 1
            raise Denied('UNIFIED_LAB_SONAR_WRITE_NOT_AVAILABLE')
        if path == '/api/components/search':
            if params.get('organization') != LAB_ORGANIZATION:
                return {'components':[], 'paging':{'pageIndex':1,'total':0}}
            matches = [{'qualifier':'TRK','organization':LAB_ORGANIZATION,
                        'key':LAB_PROJECT}]
            if 'q' in params:
                matches = [v for v in matches if v['key']==params['q']]
            return {'components':matches,'paging':{'pageIndex':1,'total':len(matches)}}
        if path == '/api/issues/search':
            issues = [dict(self.issue)] if (params.get('componentKeys') == LAB_PROJECT and
                params.get('issues', LAB_ISSUE) == LAB_ISSUE) else []
            if params.get('additionalFields') == 'transitions':
                for issue in issues: issue['transitions'] = ['accept']
            return {'issues':issues}
        raise Denied('UNIFIED_LAB_ROUTE_DENIED')


def _lab_root(state):
    state = Path(state)
    if (not state.is_absolute() or state.is_symlink() or not state.is_dir() or
            state.stat().st_uid != os.geteuid() or
            stat.S_IMODE(state.stat().st_mode) != 0o700 or
            any(part in ('fortis-approvals-g4_state','fortis-approvals-g4_token','g2_state')
                for part in state.parts)):
        raise Denied('UNIFIED_LAB_PRIVATE_ROOT_REQUIRED')
    real = state.resolve()
    if (real == Path('/workspace/repo') or Path('/workspace/repo') in real.parents or
            real == Path('/workspace/repos') or Path('/workspace/repos') in real.parents or
            real == Path('/state') or real == Path('/run')):
        # No operator/AI repository, G2 or G4 named-volume state.
        raise Denied('UNIFIED_LAB_OWNER_STATE_FORBIDDEN')
    marker = state / LAB_MARKER
    if marker.is_symlink():
        raise Denied('UNIFIED_LAB_MARKER_INVALID')
    if not marker.exists():
        if any((state / n).exists() for n in ('owner.sqlite','approvals.sqlite',
                   'synthetic.sqlite','.g4-candidate-v1')):
            raise Denied('UNIFIED_LAB_EXISTING_STATE_DENIED')
        fd = os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as file:
            file.write('offline-unified-lab-v1\n')
            file.flush();os.fsync(file.fileno())
    elif marker.read_text() != 'offline-unified-lab-v1\n':
        raise Denied('UNIFIED_LAB_MARKER_INVALID')
    return state


def build_unified_offline_lab(state, *, sonar=None, origin=LAB_ORIGIN):
    """One unified UI/Core/history, two typed adapters. Never a real deployment."""
    if origin != LAB_ORIGIN:
        raise Denied('UNIFIED_LAB_TEST_ORIGIN_ONLY')
    if sonar is None:sonar = UnifiedFakeSonar()
    if type(sonar) is not UnifiedFakeSonar:
        raise Denied('UNIFIED_LAB_SYNTHETIC_TRANSPORT_ONLY')
    state = _lab_root(state)
    synthetic = SyntheticAdapter(state / 'synthetic.sqlite')
    adapter = SonarIssueAdapter(NoWriteTransport(sonar),
        organization_keys=(LAB_ORGANIZATION,),
        receipt_store=state/'sonar-receipts.sqlite')
    owner = OwnerWebAuthn(state/'owner.sqlite',origin=origin,owner='lab-owner')
    core = Core(state/'approvals.sqlite',
        adapters={'synthetic':synthetic,'sonarcloud':adapter},
        policies={('lab-synthetic-actor','synthetic','set_free'):'ALLOW',
                  ('lab-synthetic-actor','synthetic','set_ask'):'ASK',
                  ('lab-synthetic-actor','synthetic','set_deny'):'DENY',
                  ('lab-sonar-actor',*G4_OPERATION):'ASK'},
        authenticator=Authenticator({SYNTHETIC_CREDENTIAL:'lab-synthetic-actor',
                                     SONAR_CREDENTIAL:'lab-sonar-actor'}),
        owner_verifier=owner)
    portal = OwnerPortal(core,owner,strong_operations={G4_OPERATION},
                         blocked_approvals={G4_OPERATION})
    return core,owner,synthetic,adapter,portal,sonar
