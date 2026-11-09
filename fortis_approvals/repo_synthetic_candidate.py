"""Owner-reviewed synthetic candidate: one Core, separate Repo/owner WSGI apps.

SOURCE ONLY: does not open ports, deploy Windows, or use external credentials.
The trusted host supplies an independent ingress grant outside AI-controlled
files and runs both WSGI applications behind independently reviewed boundaries.
"""
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

from .core import Authenticator, Core, Denied
from .owner_auth import OwnerWebAuthn
from .owner_portal import OwnerPortal
from .repo_action_contract import RepoIntentBroker
from .repo_ingress import RepoIngress
from .synthetic import SyntheticAdapter

_MARKER = '.fortis-repo-synthetic-v1'
_ACTOR = 'repo-synthetic-actor'
_ASK = ('synthetic', 'set_ask')
_OPERATIONS = frozenset({('synthetic', 'set_free'), _ASK,
                         ('synthetic', 'set_deny')})
_RESERVED_ORIGINS = frozenset({'http://localhost:18990',
                               'http://localhost:18991',
                               'http://localhost:18992'})
def _isolated_state(state):
    root = Path(state)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise Denied('SYNTHETIC_PRIVATE_STATE_REQUIRED')
    info = root.stat()
    real = root.resolve()
    forbidden = (Path('/workspace/repo'), Path('/workspace/repos'))
    if (info.st_uid != os.geteuid() or
            stat.S_IMODE(info.st_mode) != 0o700 or
            any(real == p or p in real.parents for p in forbidden) or
            real in (Path('/state'), Path('/run'))):
        raise Denied('SYNTHETIC_PRIVATE_STATE_REQUIRED')
    marker = root / _MARKER
    if marker.is_symlink():
        raise Denied('SYNTHETIC_STATE_MARKER_INVALID')
    if marker.exists():
        if marker.read_text() != 'fortis-repo-synthetic-v1\n':
            raise Denied('SYNTHETIC_STATE_MARKER_INVALID')
        return root, False
    # No adoption/migration of G2/G4 credentials, SQLite or volumes.
    if any(root.iterdir()):
        raise Denied('SYNTHETIC_FRESH_STATE_REQUIRED')
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write('fortis-repo-synthetic-v1\n')
        stream.flush()
        os.fsync(stream.fileno())
    return root, True
def build_synthetic_candidate(*, state, owner_origin, ingress_host,
                              ingress_grant):
    """Return (core, owner, synthetic, owner_wsgi, repo_wsgi); no listener.

    The owner controls private state and credential injection. HTTPS, network
    ACL, rate limits and server identity MUST be enforced by trusted hosting.
    """
    if (type(owner_origin) is not str or
            owner_origin in _RESERVED_ORIGINS):
        raise Denied('SYNTHETIC_DISTINCT_OWNER_ORIGIN_REQUIRED')
    if (type(ingress_host) is not str or
            ingress_host == urlsplit(owner_origin).netloc):
        raise Denied('SYNTHETIC_DISTINCT_INGRESS_REQUIRED')
    if (type(ingress_grant) is not str or
            not re.fullmatch(r'[A-Za-z0-9._~+/=-]{32,256}', ingress_grant)):
        raise Denied('SYNTHETIC_INGRESS_GRANT_REQUIRED')
    root, fresh = _isolated_state(state)
    adapter = SyntheticAdapter(root / 'synthetic.sqlite')
    if fresh:
        for target in ('SYN-ALLOW', 'SYN-ASK', 'SYN-DENY'):
            adapter.seed(target, 'original')
    auth = Authenticator({ingress_grant: _ACTOR})
    core = Core(root / 'approvals.sqlite', adapters={'synthetic': adapter},
                policies={(_ACTOR, 'synthetic', 'set_free'): 'ALLOW',
                          (_ACTOR, *_ASK): 'ASK',
                          (_ACTOR, 'synthetic', 'set_deny'): 'DENY'},
                authenticator=auth)
    owner = OwnerWebAuthn(root / 'owner.sqlite', origin=owner_origin)
    core.owner_verifier = owner
    portal = OwnerPortal(core, owner, strong_operations={_ASK})
    broker = RepoIntentBroker(core, actor_operations={_ACTOR: _OPERATIONS})
    ingress = RepoIngress(broker, host=ingress_host)  # HTTPS mandatory.
    return core, owner, adapter, portal, ingress
