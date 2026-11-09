"""R7 unified Sonar READ + owner-WebAuthn ASK/APPROVE/EXECUTE candidate.

ONE Core, ONE owner WebAuthn portal/queue, ONE authenticated machine ingress.
The machine may submit a typed accept_issue ASK proposal; it cannot approve,
execute, choose a transport, or access owner routes. Sonar POST is available
only through Core.execute after an exact owner WebAuthn approval. Project
scope is pinned by trusted deployment configuration. SOURCE ONLY, NO DEPLOYMENT.
Never adopt A3/R5/G2/G4 identity or state; R7 requires a NEW private root.
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
from .r5_read_candidate import _GRANT, _RESERVED_OWNER_ORIGINS
from .sonar import SonarIssueAdapter
from .sonar_read import SonarReadAdapter


ACTOR = 'repo-sonar-read-proposal-actor'
G4_OPERATION = ('sonarcloud', 'accept_issue')


MARKER = '.fortis-r7-unified-v1'
_MARKER_CONTENT = b'fortis-r7-unified-v1\n'


def _fresh_r7_state(path):
    root = Path(path)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise Denied('R7_NEW_PRIVATE_STATE_REQUIRED')
    info = root.stat()
    real = root.resolve()
    forbidden = (Path('/workspace/repo'), Path('/workspace/repos'))
    if (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700 or
            any(real == p or p in real.parents for p in forbidden) or
            real in (Path('/state'), Path('/run'))):
        raise Denied('R7_NEW_PRIVATE_STATE_REQUIRED')
    marker = root / MARKER
    if marker.is_symlink():
        raise Denied('R7_STATE_MARKER_INVALID')
    if marker.exists():
        status = marker.stat()
        if (not stat.S_ISREG(status.st_mode) or
                status.st_uid != os.geteuid() or
                stat.S_IMODE(status.st_mode) != 0o600 or
                marker.read_bytes() != _MARKER_CONTENT):
            raise Denied('R7_STATE_MARKER_INVALID')
        return root
    if any(root.iterdir()):
        raise Denied('R7_FRESH_STATE_ONLY_NO_ADOPTION')
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(_MARKER_CONTENT)
        stream.flush()
        os.fsync(stream.fileno())
    return root


def build_r7_unified_candidate(*, state, owner_origin, ingress_host,
                              ingress_grant, sonar_transport,
                              organizations, region='eu', actor_grants=None,
                              project_keys=None):
    """Return (core, owner, portal, ingress), no listeners or token provisioning.

    Restricted machine actor is authorized for four READ + one ASK proposal;
    the same actor NEVER receives owner decisions, raw service token or POST.
    """
    if (type(owner_origin) is not str or
            owner_origin in _RESERVED_OWNER_ORIGINS or
            not re.fullmatch(r'http://localhost:[0-9]{4,5}', owner_origin) or
            type(ingress_host) is not str or
            not re.fullmatch(r'host\.docker\.internal:[0-9]{4,5}', ingress_host) or
            urlsplit(owner_origin).netloc == ingress_host):
        raise Denied('R7_DISTINCT_OWNER_INGRESS_REQUIRED')
    if type(ingress_grant) is not str or not _GRANT.fullmatch(ingress_grant):
        raise Denied('R7_MACHINE_GRANT_INVALID')
    grants = ({ingress_grant: ACTOR} if actor_grants is None else actor_grants)
    if (type(grants) is not dict or not grants or
            any(type(grant) is not str or not _GRANT.fullmatch(grant) or
                type(actor) is not str or not actor
                for grant, actor in grants.items()) or
            len(set(grants.values())) != len(grants) or
            ingress_grant not in grants):
        raise Denied('R7_MACHINE_GRANTS_INVALID')
    if (type(organizations) not in (tuple,list,set,frozenset) or
            not organizations or len(organizations) > 20 or
            any(type(org) is not str for org in organizations) or
            len(set(organizations)) != len(organizations)):
        raise ValueError('R7_ORGANIZATIONS_INVALID')
    # Construct adapters *before* modifying state: invalid org/region fail closed.
    reader = SonarReadAdapter(sonar_transport,
                              organization_keys=organizations, region=region,
                              allowed_project_keys=project_keys)
    root = _fresh_r7_state(state)
    writer = SonarIssueAdapter(
        sonar_transport,
        project_keys=() if project_keys is None else tuple(project_keys),
        organization_keys=tuple(organizations) if project_keys is None else (),
        receipt_store=root/'sonar-receipts.sqlite',region=region)
    owner = OwnerWebAuthn(root/'owner.sqlite',origin=owner_origin)
    auth = Authenticator(grants)
    actors = tuple(grants.values())
    policies = {(actor, service, operation): 'ALLOW'
                for actor in actors
                for service, operation in SONAR_READ_OPERATIONS}
    policies.update({(actor, *G4_OPERATION): 'ASK' for actor in actors})
    core = Core(root/'approvals.sqlite',adapters={'sonarcloud':writer},
                policies=policies,authenticator=auth,owner_verifier=owner,
                policy_version='r7-p1-sonar-accept-issue-write-v1')
    portal = OwnerPortal(core,owner,strong_operations={G4_OPERATION},
                         read_only_banner=False)
    broker = RepoIntentBroker(
        core,actor_operations={actor:{G4_OPERATION} for actor in actors},
        actor_read_operations={actor: SONAR_READ_OPERATIONS for actor in actors},
        read_adapter=reader)
    ingress = RepoIngress(broker,host=ingress_host)
    return core,owner,portal,ingress
