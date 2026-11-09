"""R5 owner-controlled Sonar READ candidate composition (SOURCE ONLY).

One Core, one owner WebAuthn portal, one machine ingress. No Sonar WRITE or
synthetic actions registered. This is NOT a Windows deployment or permission
to provision a real token. Use a NEW R5 state directory, never A3/G2/G4 state.
"""
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

from .core import Authenticator, Core, Denied
from .owner_auth import OwnerWebAuthn
from .owner_portal import OwnerPortal
from .repo_action_contract import RepoIntentBroker, SONAR_READ_OPERATIONS
from .repo_ingress import RepoIngress
from .sonar_read import SonarReadAdapter


_ACTOR = 'repo-sonar-read-actor'
_MARKER = '.fortis-r5-sonar-read-v1'
_GRANT = re.compile(r'[A-Za-z0-9._~+/=-]{32,256}\Z')
_RESERVED_OWNER_ORIGINS = frozenset({
    'http://localhost:18990', 'http://localhost:18991',
    'http://localhost:19093',
})


def _fresh_private_state(path):
    root = Path(path)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise Denied('R5_NEW_PRIVATE_STATE_REQUIRED')
    info = root.stat()
    real = root.resolve()
    forbidden = (Path('/workspace/repo'), Path('/workspace/repos'))
    if (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700 or
            any(real == p or p in real.parents for p in forbidden) or
            real in (Path('/state'), Path('/run'))):
        raise Denied('R5_NEW_PRIVATE_STATE_REQUIRED')
    marker = root / _MARKER
    if marker.is_symlink():
        raise Denied('R5_STATE_MARKER_INVALID')
    if marker.exists():
        info = marker.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
                stat.S_IMODE(info.st_mode) != 0o600 or
                marker.read_bytes() != b'fortis-r5-sonar-read-v1\n'):
            raise Denied('R5_STATE_MARKER_INVALID')
        return root
    if any(root.iterdir()):
        raise Denied('R5_FRESH_STATE_ONLY_NO_ADOPTION')
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(b'fortis-r5-sonar-read-v1\n')
        output.flush()
        os.fsync(output.fileno())
    return root


def build_r5_read_candidate(*, state, owner_origin, ingress_host,
                            ingress_grant, sonar_transport,
                            organizations, region='eu'):
    """Return (core, owner, owner_portal, machine_ingress); no listeners.

    Sonar transport MUST be selected inside the trusted runtime, not accepted
    from the machine request. The caller cannot provide a token, method, URL
    or operation grant. No adapter is registered for Core.execute().
    """
    if (type(owner_origin) is not str or
            owner_origin in _RESERVED_OWNER_ORIGINS or
            not re.fullmatch(r'http://localhost:[0-9]{4,5}', owner_origin) or
            type(ingress_host) is not str or
            not re.fullmatch(r'host\.docker\.internal:[0-9]{4,5}', ingress_host) or
            urlsplit(owner_origin).netloc == ingress_host):
        raise Denied('R5_DISTINCT_OWNER_INGRESS_REQUIRED')
    if (type(ingress_grant) is not str or
            not _GRANT.fullmatch(ingress_grant)):
        raise Denied('R5_MACHINE_GRANT_INVALID')
    # Validate trusted Sonar region/org configuration before creating state.
    if (type(organizations) not in (tuple, list, set, frozenset) or
            any(type(org) is not str for org in organizations) or
            len(set(organizations)) != len(organizations)):
        raise ValueError('R5_ORGANIZATIONS_DUPLICATE_OR_INVALID')
    reader = SonarReadAdapter(sonar_transport,
                              organization_keys=organizations, region=region)
    root = _fresh_private_state(state)
    auth = Authenticator({ingress_grant: _ACTOR})
    owner = OwnerWebAuthn(root / 'owner.sqlite', origin=owner_origin)
    policies = {(_ACTOR, service, op): 'ALLOW'
                for service, op in SONAR_READ_OPERATIONS}
    core = Core(root / 'approvals.sqlite',
                adapters={}, policies=policies,
                authenticator=auth, owner_verifier=owner)
    portal = OwnerPortal(core, owner)  # Existing owner UI; no ASK writes in READ candidate.
    broker = RepoIntentBroker(
        core, actor_operations={},
        actor_read_operations={_ACTOR: SONAR_READ_OPERATIONS},
        read_adapter=reader)
    ingress = RepoIngress(broker, host=ingress_host)
    return core, owner, portal, ingress
