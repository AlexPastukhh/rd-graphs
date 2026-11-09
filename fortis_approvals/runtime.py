"""Operator-controlled G2 runtime composition. Synthetic operations ONLY.

No live Sonar/RDG adapter or AI-facing HTTP action endpoint is mounted here.
"""
import os
from pathlib import Path

from .core import Authenticator, Core, Denied
from .owner_auth import OwnerWebAuthn
from .owner_portal import OwnerPortal
from .synthetic import SyntheticAdapter


def settings():
    state = Path(os.environ.get('FORTIS_STATE_DIR', '/state')).absolute()
    origin = os.environ.get('FORTIS_OWNER_ORIGIN', 'http://localhost:18990')
    owner = os.environ.get('FORTIS_OWNER_ID', 'owner')
    port = int(os.environ.get('FORTIS_PORT', '18990'))
    if not 1024 <= port <= 65535:
        raise Denied('PORT_INVALID')
    if (state.is_symlink() or not state.is_dir() or state.stat().st_mode & 0o077 or
        state.stat().st_uid != os.geteuid() or state.is_relative_to(Path(__file__).resolve().parents[1])):
        raise Denied('TRUSTED_STATE_DIR_REQUIRED')
    return state, origin, owner, port


def build_runtime():
    state, origin, owner_id, port = settings()
    adapter = SyntheticAdapter(state / 'synthetic.sqlite')
    # Synthetic client ID is only used by the private operator CLI. No public
    # client Gateway is hosted; never embed a live service secret in this module.
    core = Core(state / 'approvals.sqlite', adapters={'synthetic': adapter},
                authenticator=Authenticator({'operator-synthetic-only': 'operator-fixture'}),
                policies={('synthetic','set_ask'): 'ASK'}, expiry_seconds=7*86400)
    session_seconds=int(os.environ.get('FORTIS_OWNER_SESSION_SECONDS', '43200'))
    owner = OwnerWebAuthn(state / 'owner.sqlite', origin=origin, owner=owner_id,
                         session_seconds=session_seconds)
    core.owner_verifier=owner
    return core, owner, adapter, port


def build_portal():
    core,owner,_,port = build_runtime()
    # Operator-controlled high-risk operation list may grow on G4/D phases.
    # For the G2 synthetic-only runtime no operations require a second key prompt.
    return OwnerPortal(core,owner),port
