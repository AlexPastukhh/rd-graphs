"""Fortis Repo -> trusted Approvals: typed *intent*, NOT a remote executor.

Stage-1 source contract only. This module has no listener, Sonar credential,
HTTP client, Docker integration, owner approval or privileged executor.
A trusted host may later mount it behind a separate authenticated ingress.
Repository callers MUST NOT send action-level policy, approvals, tokens,
URLs, methods, raw executor params, snapshots or fingerprints.
"""
from copy import deepcopy
import re
import uuid

from .core import Denied, canonical

# Sonar is an optional typed service adapter. Synthetic-only Fortis images
# must not need to install Sonar transport merely to validate Repo intents.


INTENT_FIELDS = frozenset({'requestId', 'service', 'operation', 'target',
                           'params', 'reason'})
# Actions and reads remain separate authorization surfaces. A READ query
# is NEVER eligible for Core.submit()/Core.execute() or /v1/actions.
OPERATIONS = frozenset({('sonarcloud', 'accept_issue'),
                        ('synthetic', 'set_free'), ('synthetic', 'set_ask'),
                        ('synthetic', 'set_deny')})
SONAR_READ_OPERATIONS = frozenset({
    ('sonarcloud', 'list_projects'), ('sonarcloud', 'list_issues'),
    ('sonarcloud', 'get_issue'), ('sonarcloud', 'get_quality_gate'),
})
# Exact syntax also used by SonarIssueAdapter.PROJECT_KEY; validation must
# remain import-safe in the synthetic-only Docker image.
_SONAR_PROJECT_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')


def _envelope(value, allowed_operations):
    # Shared strict envelope; no method/URL/owner/token/policy input.
    if type(value) is not dict or set(value) != INTENT_FIELDS:
        raise Denied('REPO_INTENT_SCHEMA_DENIED')
    try:
        ident = str(uuid.UUID(value['requestId']))
    except (TypeError, KeyError, ValueError, AttributeError):
        raise Denied('REPO_REQUEST_ID_DENIED') from None
    if value['requestId'] != ident:
        raise Denied('REPO_REQUEST_ID_DENIED')
    action = (value['service'], value['operation'])
    if any(type(v) is not str for v in action) or action not in allowed_operations:
        raise Denied('REPO_OPERATION_NOT_SUPPORTED')
    if (type(value['target']) is not str or
            not _SONAR_PROJECT_KEY.fullmatch(value['target'])):
        raise Denied('REPO_TARGET_DENIED')
    if (type(value['reason']) is not str or
            not 0 < len(value['reason'].strip()) <= 1500):
        raise Denied('REPO_REASON_DENIED')
    params = value['params']
    if type(params) is not dict:
        raise Denied('REPO_PARAMS_DENIED')
    return action, params


def _checked_copy(value):
    try:
        if len(canonical(value).encode('utf-8')) > 32768:
            raise Denied('REPO_INTENT_TOO_LARGE')
    except (UnicodeError, ValueError, TypeError):
        raise Denied('REPO_INTENT_UTF8_DENIED') from None
    return deepcopy(value)


def validate_intent(value):
    """Only action submit intents, never read requests."""
    action, params = _envelope(value, OPERATIONS)
    if action == ('sonarcloud', 'accept_issue'):
        if (set(params) != {'projectKey'} or
            type(params['projectKey']) is not str or
            not _SONAR_PROJECT_KEY.fullmatch(params['projectKey'])):
            raise Denied('REPO_SONAR_PARAMS_DENIED')
    else:
        if (set(params) != {'value', 'expectedVersion'} or
            type(params['value']) is not str or len(params['value']) > 1000 or
            type(params['expectedVersion']) is not int or
            not 0 <= params['expectedVersion'] <= 2_147_483_647):
            raise Denied('REPO_SYNTHETIC_PARAMS_DENIED')
    return _checked_copy(value)


def validate_read_query(value):
    """Typed READ envelope used by R3 ingress; no transport or token here.

    list_projects: target=organization key, params={page, pageSize}.
    list_issues: target=project key, params={page, pageSize}.
    get_issue: target=issue key, params={projectKey}.
    get_quality_gate: target=project key, params={}.
    Region, trusted organization/project grants and credential never come
    from the caller. R2 must enforce actual project/org membership.
    """
    action, params = _envelope(value, SONAR_READ_OPERATIONS)
    operation = action[1]
    if operation in ('list_projects', 'list_issues'):
        if (set(params) != {'page', 'pageSize'} or
                type(params['page']) is not int or
                not 1 <= params['page'] <= 10000 or
                type(params['pageSize']) is not int or
                not 1 <= params['pageSize'] <= 100):
            raise Denied('REPO_SONAR_READ_PARAMS_DENIED')
    elif operation == 'get_issue':
        if (set(params) != {'projectKey'} or
                type(params['projectKey']) is not str or
                not _SONAR_PROJECT_KEY.fullmatch(params['projectKey'])):
            raise Denied('REPO_SONAR_READ_PARAMS_DENIED')
    elif params:
        raise Denied('REPO_SONAR_READ_PARAMS_DENIED')
    return _checked_copy(value)


class RepoIntentBroker:
    """In-process contract implementation; no network route is installed.

    The *ingress grant* used in Core.client is not a Sonar token. The trusted
    host owns the adapters, policy and per-actor grant scopes. The Repo actor
    cannot select an owner or choose the Core policy. Action responses contain
    ID/state ONLY. Sonar read queries are validated/authorized as a separate
    R3 source supports an optional trusted GET-only reader at /v1/reads;
    synthetic-only and production-unadmitted deployments have no reader.
    """
    def __init__(self, core, *, actor_operations, actor_read_operations=None,
                 read_adapter=None):
        self.core = core
        # R3: optional trusted Sonar reader. The synthetic-only image never
        # imports Sonar, and its existing action/status routes are unaffected.
        if read_adapter is not None:
            from .sonar_read import SonarReadAdapter
            if not isinstance(read_adapter, SonarReadAdapter):
                raise ValueError('REPO_TRUSTED_READ_ADAPTER_INVALID')
        self.read_adapter = read_adapter
        if (type(actor_operations) is not dict or
                not all(type(actor) is str and actor and
                        type(ops) in (frozenset, set, tuple) and ops and
                        all(type(op) is tuple and len(op) == 2 and op in OPERATIONS
                            for op in ops)
                        for actor, ops in actor_operations.items())):
            raise ValueError('REPO_TRUSTED_GRANTS_INVALID')
        self.actor_operations = {actor: frozenset(ops)
                                 for actor, ops in actor_operations.items()}
        reads = {} if actor_read_operations is None else actor_read_operations
        if (type(reads) is not dict or
                not all(type(actor) is str and actor and
                        type(ops) in (frozenset, set, tuple) and ops and
                        all(type(op) is tuple and op in SONAR_READ_OPERATIONS
                            for op in ops)
                        for actor, ops in reads.items())):
            raise ValueError('REPO_TRUSTED_READ_GRANTS_INVALID')
        self.actor_read_operations = {actor: frozenset(ops)
                                      for actor, ops in reads.items()}

    def authorize_read(self, ingress_credential, query):
        """R1 typed authorization preflight; R2 adds the read execution route.

        No request is dispatched, persisted or sent to Sonar here.
        """
        actor = self.core.auth.authenticate(ingress_credential)
        request = validate_read_query(query)
        action = (request['service'], request['operation'])
        if action not in self.actor_read_operations.get(actor, ()):
            raise Denied('REPO_READ_GRANT_DENIED')
        if self.core._policy(actor, request) != 'ALLOW':
            raise Denied('REPO_SONAR_READ_ALLOW_REQUIRED')
        return request

    def read(self, ingress_credential, query):
        """R3: authenticated, policy-bound READ through a trusted GET-only adapter.

        No Core.submit()/execute(), no owner routes, no mutable operation, and
        no service credentials from untrusted input. R2 validates the upstream
        response and emits an allowlisted projection.
        """
        request = self.authorize_read(ingress_credential, query)
        if self.read_adapter is None:
            raise Denied('REPO_READ_ADAPTER_UNAVAILABLE')
        result = self.read_adapter.read(request)
        # Reject accidental direct export of an upstream response or internal
        # snapshot if a future adapter changes its result contract.
        public_fields = {
            'list_projects': frozenset(('operation', 'projects', 'page',
                'pageSize', 'total', 'hasMore', 'nextPage', 'complete',
                'organization')),
            'list_issues': frozenset(('operation', 'issues', 'page',
                'pageSize', 'total', 'hasMore', 'nextPage', 'coverage',
                'projectKey')),
            'get_issue': frozenset(('operation', 'issue', 'projectKey')),
            'get_quality_gate': frozenset(('operation', 'projectKey',
                'status', 'conditions', 'scope', 'prShaBinding')),
        }
        if (type(result) is not dict or
                set(result) != public_fields[request['operation']] or
                result.get('operation') != request['operation']):
            raise Denied('REPO_READ_PROJECTION_DENIED')
        # Defense in depth: do not let an adapter refactor accidentally
        # publish extra raw Sonar fields buried in a nested Issue/condition.
        issue_fields = frozenset(('key', 'projectKey', 'status', 'severity',
            'type', 'rule', 'message', 'component', 'line', 'updateDate'))
        operation = request['operation']
        if operation == 'list_projects':
            rows = result['projects']
            if (type(rows) is not list or len(rows) > 100 or
                    any(type(row) is not dict or set(row) != {'key'}
                        for row in rows)):
                raise Denied('REPO_READ_PROJECTION_DENIED')
        elif operation in ('list_issues', 'get_issue'):
            rows = (result['issues'] if operation == 'list_issues'
                    else [result['issue']])
            if (type(rows) is not list or len(rows) > 100 or
                    any(type(row) is not dict or set(row) != issue_fields
                        for row in rows)):
                raise Denied('REPO_READ_PROJECTION_DENIED')
        elif operation == 'get_quality_gate':
            conditions = result['conditions']
            allowed_condition = frozenset(('status','metricKey',
                'actualValue','errorThreshold','warningThreshold'))
            if (type(conditions) is not list or len(conditions) > 100 or
                    any(type(row) is not dict or
                        not {'status', 'metricKey'} <= set(row) or
                        not set(row) <= allowed_condition for row in conditions)):
                raise Denied('REPO_READ_PROJECTION_DENIED')
        return {'requestId': request['requestId'], 'service': 'sonarcloud',
                'operation': operation, 'data': result}

    @staticmethod
    def _public_result(row):
        # Never expose Core's snapshots, Issue messages, actor identity,
        # policy fingerprint, Sonar credential or remote API response here.
        return {'requestId': row['requestId'], 'state': row['state']}

    def submit(self, ingress_credential, intent):
        # Authenticate and authorize the actor BEFORE any remote GET.
        actor = self.core.auth.authenticate(ingress_credential)
        request = validate_intent(intent)
        action = (request['service'], request['operation'])
        if action not in self.actor_operations.get(actor, ()):
            raise Denied('REPO_GRANT_DENIED')
        adapter = self.core.adapters.get(action[0])
        if adapter is None:
            raise Denied('REPO_ADAPTER_UNAVAILABLE')
        params = request['params']
        if action == ('sonarcloud', 'accept_issue'):
            from .sonar import SonarIssueAdapter
            # Scope and exact readback digest are trusted-adapter outputs,
            # not caller-supplied fingerprints or a guessed version.
            if not isinstance(adapter, SonarIssueAdapter):
                raise Denied('REPO_SONAR_ADAPTER_DENIED')
            # Fail closed BEFORE remote lookup if the trusted policy already
            # denies this operation, or if Sonar ASK was downgraded to ALLOW.
            # The actual server-derived digest is checked again below.
            provisional = {
                'requestId': request['requestId'], 'service': 'sonarcloud',
                'operation': 'accept_issue', 'target': request['target'],
                'params': {'projectKey': params['projectKey'],
                           'transition': 'accept',
                           'expectedIssueSha256': '0' * 64},
                'expectedVersion': 0, 'reason': request['reason'],
            }
            if self.core._policy(actor, provisional) != 'ASK':
                raise Denied('REPO_SONAR_ASK_REQUIRED')
            issue = adapter.read_issue(params['projectKey'], request['target'])
            body = {
                'requestId': request['requestId'],
                'service': 'sonarcloud', 'operation': 'accept_issue',
                'target': request['target'],
                'params': {'projectKey': params['projectKey'],
                           'transition': 'accept',
                           'expectedIssueSha256': issue['sha256']},
                'expectedVersion': 0, 'reason': request['reason'],
            }
            # Fortis Sonar mutation policy is mandatory ASK. This check is
            # a front-door defense; the trusted Core/executor must ALSO pin
            # the rule and never accept caller-supplied policy.
            if self.core._policy(actor, body) != 'ASK':
                raise Denied('REPO_SONAR_ASK_REQUIRED')
        else:
            body = {
                'requestId': request['requestId'],
                'service': request['service'],
                'operation': request['operation'],
                'target': request['target'],
                'params': {'value': params['value']},
                'expectedVersion': params['expectedVersion'],
                'reason': request['reason'],
            }
        return self._public_result(self.core.client(ingress_credential, 'submit', body))

    def status(self, ingress_credential, request_id):
        # Same actor-only Core access. No generic DB or owner history reads.
        if (type(request_id) is not str or
                not re.fullmatch(r'[0-9a-f-]{36}', request_id)):
            raise Denied('REPO_REQUEST_ID_DENIED')
        return self._public_result(self.core.client(ingress_credential, 'status', request_id))
