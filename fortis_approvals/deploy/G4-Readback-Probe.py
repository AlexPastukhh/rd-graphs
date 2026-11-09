"""G4 owner-only post-Reject audit: mounted local history (RO) + Sonar GET.

This file is streamed to `python -` inside a one-shot owner Docker container.
Requires existing, separately mounted READ-ONLY G4 state and token volumes.
No G2 mounts, no Core mutation, no Sonar POST, no secret/Issue body printing.
"""
import json
from pathlib import Path
import re
import sqlite3
import sys
import uuid
from urllib.parse import quote

from fortis_approvals.core import Denied
from fortis_approvals.g4_candidate import NoWriteTransport, _owner_token_file
from fortis_approvals.sonar import SonarHTTPTransport, SonarIssueAdapter

DB = Path('/state/private/approvals.sqlite')
TOKEN = '/run/g4-token/private/sonar_token'
SCOPE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')


class ReadbackDenied(ValueError):
    pass


def audit(project, issue, request_id, *, database=DB, transport=None):
    """Return (local_state, remote_status, digest_match) or fail closed.

    Only the owner-selected immutable request UUID can be compared. Never
    infer the target request from sort order or from project/Issue alone.
    """
    if not (type(project) is str and SCOPE.fullmatch(project)
            and type(issue) is str and SCOPE.fullmatch(issue)):
        raise ReadbackDenied('INVALID_SCOPED_TARGET')
    if (type(request_id) is not str or not re.fullmatch(r'[0-9a-f-]{36}', request_id)
            or str(uuid.UUID(request_id)) != request_id):
        raise ReadbackDenied('REQUEST_ID_REQUIRED')
    if database.is_symlink() or not database.is_file():
        raise ReadbackDenied('READONLY_G4_STATE_NOT_FOUND')
    uri = 'file:' + quote(str(database), safe='/') + '?mode=ro'
    with sqlite3.connect(uri, uri=True, timeout=5) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only = ON')
        matched = db.execute('''SELECT id, payload, snapshot, state, decision, owner
            FROM requests WHERE id=? LIMIT 1''', (request_id,)).fetchone()
        if matched is None:
            raise ReadbackDenied('EXACT_G4_REQUEST_NOT_FOUND')
        payload = json.loads(matched['payload'])
        if (payload.get('requestId') != request_id or
                payload.get('service') != 'sonarcloud' or
                payload.get('operation') != 'accept_issue' or
                payload.get('target') != issue or
                payload.get('params', {}).get('projectKey') != project):
            raise ReadbackDenied('EXACT_REQUEST_TARGET_MISMATCH')
        body = json.loads(matched['payload'])
        snapshot = json.loads(matched['snapshot'])
        digest = body['params']['expectedIssueSha256']
        if (matched['state'] != 'REJECTED' or matched['decision'] != 'reject'
                or not matched['owner'] or
                snapshot.get('projectKey') != project or
                snapshot.get('issueKey') != issue or
                snapshot.get('before', {}).get('sha256') != digest or
                snapshot.get('before', {}).get('status') != 'OPEN' or
                snapshot.get('after', {}).get('status') != 'ACCEPTED'):
            raise ReadbackDenied('LOCAL_REJECTED_SNAPSHOT_NOT_CONFIRMED')
        events = db.execute('''SELECT COUNT(*) FROM events
            WHERE request_id=? AND state='REJECTED' ''',
            (matched['id'],)).fetchone()[0]
        if events != 1:
            raise ReadbackDenied('LOCAL_REJECT_EVENT_NOT_CONFIRMED')
    if transport is None:
        transport = NoWriteTransport(SonarHTTPTransport(
            region='eu', bearer_token=_owner_token_file(TOKEN)))
    result = transport.call('GET','/api/issues/search',{
        'componentKeys':project,'issues':issue,'p':'1','ps':'2'})
    if (type(result) is not dict or type(result.get('issues')) is not list
            or len(result['issues']) != 1):
        raise ReadbackDenied('REMOTE_ISSUE_NOT_UNIQUE')
    current = SonarIssueAdapter._normalize(result['issues'][0], project=project)
    if current['key'] != issue:
        raise ReadbackDenied('REMOTE_ISSUE_ID_MISMATCH')
    return matched['state'], current['status'], SonarIssueAdapter._digest(current) == digest


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print('G4_READBACK_BAD_ARGUMENTS', file=sys.stderr)
        return 3
    try:
        local, remote, match = audit(*argv)
        print('G4_LOCAL_HISTORY:', local)
        if remote == 'OPEN' and match:
            print('G4_REMOTE_STATUS: OPEN')
            print('G4_REMOTE_PROJECTION_MATCH: YES')
            print('G4_READBACK_AFTER_REJECT: PASS')
            print('G4_PROBE_GET_ONLY: YES')
            return 0
        print('G4_READBACK_AFTER_REJECT: REVIEW_REQUIRED')
        print('G4_REMOTE_STATUS_OPEN:', 'YES' if remote == 'OPEN' else 'NO')
        print('G4_REMOTE_PROJECTION_MATCH:', 'YES' if match else 'NO')
        print('G4_PROBE_GET_ONLY: YES')
        return 4
    except (OSError, sqlite3.Error, Denied, ValueError, TypeError, KeyError, RuntimeError):
        # Do not echo remote response, token, owner identity or private fields.
        print('G4_READBACK_CHECK_FAILED_NO_POST', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
