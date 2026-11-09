"""Isolated G4 ASK preview candidate for the existing owner UI.

This module never changes the running G2 runtime. It refuses to adopt an
existing G2 state directory, never exposes a client HTTP listener and hard-
disables all remote SonarCloud writes. This is NOT a G4 production deployment.
"""
import os
from pathlib import Path
import stat
import uuid

from .core import Authenticator, Denied
from .owner_portal import OwnerPortal
from .runtime import build_runtime, settings
from .sonar import SonarHTTPTransport, SonarIssueAdapter
from .sonar_inventory import ORG_KEY

G4_OPERATION = ('sonarcloud', 'accept_issue')
OPERATOR_CREDENTIAL = 'trusted-g4-proposal-cli-only'
MARKER = '.g4-candidate-v1'


class NoWriteTransport:
    """Backstop: even direct Core.execute cannot issue Sonar POST in candidate."""
    def __init__(self, source):
        self.source = source

    def call(self, method, path, params):
        if method != 'GET':
            raise Denied('SONAR_G4_CANDIDATE_WRITE_DISABLED')
        return self.source.call(method, path, params)


def _candidate_state(state):
    """Fail closed if given an existing G2 directory with enrolled keys/DB."""
    marker = state / MARKER
    if marker.is_symlink():
        raise Denied('G4_CANDIDATE_MARKER_INVALID')
    if marker.exists():
        if marker.read_text() != 'fortis-g4-isolated-candidate-v1\n':
            raise Denied('G4_CANDIDATE_MARKER_INVALID')
        return
    if any((state / name).exists() for name in ('owner.sqlite','approvals.sqlite','synthetic.sqlite')):
        raise Denied('G4_REFUSE_EXISTING_G2_STATE')
    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write('fortis-g4-isolated-candidate-v1\n')
        stream.flush()
        os.fsync(stream.fileno())


def _owner_token_file(path):
    """Only private, owner-managed files outside AI-mounts or repository."""
    source = Path(path)
    if not source.is_absolute() or source.is_symlink():
        raise Denied('G4_TOKEN_FILE_NOT_TRUSTED')
    try:
        detail = source.stat()
    except OSError:
        raise Denied('G4_TOKEN_FILE_NOT_TRUSTED') from None
    real = source.resolve()
    forbidden = (Path('/workspace/repo'), Path('/workspace/repos'))
    if (not stat.S_ISREG(detail.st_mode) or detail.st_uid != os.geteuid() or
            detail.st_mode & 0o077 or detail.st_size < 12 or detail.st_size > 4096 or
            any(real == p or p in real.parents for p in forbidden)):
        raise Denied('G4_TOKEN_FILE_NOT_TRUSTED')
    try:
        token = source.read_text(encoding='utf-8').strip('\r\n')
    except (OSError, UnicodeError):
        raise Denied('G4_TOKEN_FILE_NOT_TRUSTED') from None
    if not 12 <= len(token) <= 4096 or any(ch.isspace() for ch in token):
        raise Denied('G4_TOKEN_FILE_NOT_TRUSTED')
    return token


def build_candidate(*, token_file, organizations, region='eu', transport=None):
    """Create isolated candidate with G2 portal + real/synthetic Sonar GETs.

    The trusted operator explicitly supplies the token path and org scope.
    No environment flag, browser route or AI-provided request may enable POST.
    A synthetic injected transport is allowed only for isolated tests.
    """
    state, origin, _, port = settings()
    if transport is None and (port == 18990 or origin == 'http://localhost:18990'):
        # Never accidentally bind a real-token candidate to the default G2 UI.
        raise Denied('G4_DISTINCT_OWNER_PORT_REQUIRED')
    if transport is None and any(state == root or root in state.parents for root in
                                 (Path('/workspace/repo'), Path('/workspace/repos'))):
        raise Denied('G4_CANDIDATE_STATE_NOT_TRUSTED')
    if (region not in SonarHTTPTransport.ORIGINS or
            type(organizations) not in (list, tuple) or not organizations or
            len(organizations) > 20 or len(set(organizations)) != len(organizations) or
            any(type(org) is not str or not ORG_KEY.fullmatch(org) for org in organizations)):
        raise Denied('G4_SCOPE_INVALID')
    if transport is None:
        source = SonarHTTPTransport(region=region, bearer_token=_owner_token_file(token_file))
    else:
        if not callable(getattr(transport, 'call', None)):
            raise Denied('G4_TRANSPORT_INVALID')
        source = transport
    _candidate_state(state)
    core, owner, synthetic, port = build_runtime()
    sonar = SonarIssueAdapter(NoWriteTransport(source),
        organization_keys=tuple(organizations),
        receipt_store=state / 'g4-receipts.sqlite', region=region)
    # The G4 image must never include the old G2 synthetic operator grant.
    core.adapters.clear()
    core.adapters['sonarcloud'] = sonar
    core.policies.clear()
    core.policies[G4_OPERATION] = 'ASK'
    core.auth = Authenticator({OPERATOR_CREDENTIAL: 'g4-trusted-proposer'})
    portal = OwnerPortal(core, owner, strong_operations={G4_OPERATION},
                         blocked_approvals={G4_OPERATION}, read_only_banner=True)
    return core, owner, sonar, portal, port


def propose_issue(core, adapter, *, project_key, issue_key, reason):
    """Trusted in-process owner CLI only. Never accept arbitrary HTTP payloads."""
    issue = adapter.read_issue(project_key, issue_key)
    payload = {'requestId': str(uuid.uuid4()), 'service':'sonarcloud',
               'operation':'accept_issue', 'target':issue_key,
               'params':{'projectKey':project_key,'transition':'accept',
                         'expectedIssueSha256':issue['sha256']},
               'expectedVersion':0, 'reason':reason}
    return core.client(OPERATOR_CREDENTIAL, 'submit', payload)
