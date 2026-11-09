"""R2: bounded, organization-scoped SonarCloud GET-only domain adapter.

NOT a network listener, owner-secret resolver or Repo response endpoint.
Compose ONLY behind RepoIntentBroker.authorize_read, never trust read() alone
to authenticate the caller. The transport is independently GET-only even if
an upstream transport supports POST for an unrelated ASK adapter.
"""
from .core import Denied
from .repo_action_contract import validate_read_query
from .sonar import SonarHTTPTransport, SonarIssueAdapter
from .sonar_inventory import ORG_KEY, discover

MAX_RESULTS = 10_000
_ALLOWED_ROUTES = {
    '/api/components/search': frozenset({'organization', 'p', 'ps', 'q'}),
    '/api/issues/search': frozenset({'componentKeys', 'p', 'ps', 'issues'}),
    '/api/qualitygates/project_status': frozenset({'projectKey'}),
}
_STATUSES = frozenset({'OK', 'WARN', 'ERROR', 'NONE'})


class SonarReadOnlyTransport:
    """Independent GET-only allowlist. Never expose the underlying transport."""

    def __init__(self, underlying):
        if not callable(getattr(underlying, 'call', None)):
            raise ValueError('SONAR_READ_TRANSPORT_REQUIRED')
        self._underlying = underlying

    def call(self, method, path, params):
        if (method != 'GET' or path not in _ALLOWED_ROUTES or
                type(params) is not dict or
                not set(params) <= _ALLOWED_ROUTES[path] or
                not all(type(k) is str and type(v) is str
                            for k, v in params.items())):
            raise Denied('SONAR_READ_ONLY_ROUTE_DENIED')
        return self._underlying.call(method, path, params)


class SonarReadAdapter:
    """Internal READ-only adapter; external projection/HTTP is R3.

    Owner supplies one or more trusted organization keys at construction.
    Org/project membership is checked before fetching issues or quality gate.
    Project list is all visible projects in each trusted org, capped by the
    existing Sonar inventory discovery limit. Issues are bounded per page;
    the API's 10k search cap is exposed, not presented as full coverage.
    """

    def __init__(self, transport, *, organization_keys, region='eu',
                 allowed_project_keys=None):
        if (type(organization_keys) not in (tuple, list, set, frozenset) or
                not 1 <= len(organization_keys) <= 20 or
                any(type(key) is not str or not ORG_KEY.fullmatch(key)
                    for key in organization_keys) or
                region not in SonarHTTPTransport.ORIGINS):
            raise ValueError('SONAR_READ_SCOPE_INVALID')
        if allowed_project_keys is not None and (
                type(allowed_project_keys) not in (tuple, list, set, frozenset) or
                not 1 <= len(allowed_project_keys) <= 20 or
                len(set(allowed_project_keys)) != len(allowed_project_keys) or
                any(type(key) is not str or not ORG_KEY.fullmatch(key)
                    for key in allowed_project_keys)):
            raise ValueError('SONAR_READ_PROJECT_ALLOWLIST_INVALID')
        if (isinstance(transport, SonarHTTPTransport) and
                transport._origin != SonarHTTPTransport.ORIGINS[region]):
            raise ValueError('SONAR_REGION_MISMATCH')
        self._organizations = frozenset(organization_keys)
        self._allowed_projects = (None if allowed_project_keys is None else
                                  frozenset(allowed_project_keys))
        self._reader = SonarReadOnlyTransport(transport)

    @staticmethod
    def _page(keys, *, page, page_size, field, name):
        total = len(keys)
        start = (page - 1) * page_size
        result = keys[start:start + page_size]
        has_more = start + len(result) < total
        return {'operation': name, field: result, 'page': page,
                'pageSize': page_size, 'total': total, 'hasMore': has_more,
                'nextPage': page + 1 if has_more else None,
                'complete': not has_more and start <= total}

    def _check_project(self, key):
        if (type(key) is not str or not ORG_KEY.fullmatch(key) or
                self._allowed_projects is not None and
                key not in self._allowed_projects):
            raise Denied('SONAR_READ_PROJECT_DENIED')
        for organization in sorted(self._organizations):
            if key in discover(self._reader, organization, query_key=key):
                return key
        raise Denied('SONAR_READ_PROJECT_DENIED')

    @staticmethod
    def _issue(raw, project):
        normalized = SonarIssueAdapter._normalize(raw, project=project)
        if not 1 <= len(normalized['status']) <= 64:
            raise Denied('SONAR_READ_ISSUE_STATUS_INVALID')
        line = raw.get('line')
        if line is not None and (type(line) is not int or
                                 not 1 <= line <= 2_147_483_647):
            raise Denied('SONAR_READ_ISSUE_LINE_INVALID')
        # No owner preview, assignee, upstream token/headers, transitions,
        # unvalidated response fields or generic response body.
        return {'key': normalized['key'], 'projectKey': project,
                'status': normalized['status'], 'severity': normalized['severity'],
                'type': normalized['type'], 'rule': normalized['rule'],
                'message': normalized['message'], 'component': normalized['component'],
                'line': line, 'updateDate': normalized['updateDate']}

    @staticmethod
    def _paging(response, page, page_size):
        if (type(response) is not dict or type(response.get('issues')) is not list or
                len(response['issues']) > page_size):
            raise Denied('SONAR_READ_ISSUES_INVALID')
        paging = response.get('paging')
        if (type(paging) is not dict or
                type(paging.get('pageIndex')) is not int or
                paging['pageIndex'] != page or
                type(paging.get('pageSize')) is not int or
                paging['pageSize'] != page_size or
                type(paging.get('total')) is not int or
                not 0 <= paging['total'] <= 2_147_483_647 or
                ('total' in response and response['total'] != paging['total'])):
            raise Denied('SONAR_READ_PAGING_INVALID')
        total = paging['total']
        offset = (page - 1) * page_size
        if offset >= MAX_RESULTS or (offset + page_size) > MAX_RESULTS:
            raise Denied('SONAR_READ_PAGE_WINDOW_EXCEEDED')
        count = len(response['issues'])
        if (offset < total and not count or count > max(0, total - offset) or
                offset + count < min(total, MAX_RESULTS) and count != page_size or
                offset >= total and count):
            raise Denied('SONAR_READ_PAGING_INCOMPLETE')
        return total

    @staticmethod
    def _quality_gate(data, project):
        if type(data) is not dict or type(data.get('projectStatus')) is not dict:
            raise Denied('SONAR_QUALITY_GATE_INVALID')
        status = data['projectStatus']
        if (type(status.get('status')) is not str or
                status['status'] not in _STATUSES or
                type(status.get('conditions')) is not list or
                len(status['conditions']) > 100):
            raise Denied('SONAR_QUALITY_GATE_INVALID')
        conditions = []
        for condition in status['conditions']:
            if (type(condition) is not dict or
                    type(condition.get('status')) is not str or
                    condition['status'] not in _STATUSES or
                    type(condition.get('metricKey')) is not str or
                    not 1 <= len(condition['metricKey']) <= 128):
                raise Denied('SONAR_QUALITY_GATE_CONDITION_INVALID')
            out = {'status': condition['status'],
                   'metricKey': condition['metricKey']}
            for field in ('actualValue', 'errorThreshold', 'warningThreshold'):
                value = condition.get(field)
                if value is not None:
                    if type(value) is not str or len(value) > 64:
                        raise Denied('SONAR_QUALITY_GATE_CONDITION_INVALID')
                    out[field] = value
            conditions.append(out)
        return {'operation': 'get_quality_gate', 'projectKey': project,
                'status': status['status'], 'conditions': conditions,
                'scope': 'CURRENT_DEFAULT_BRANCH',
                'prShaBinding': 'NOT_VERIFIED_D2'}

    def read(self, query):
        """R2 domain call. Caller MUST authorize with broker before invoking."""
        req = validate_read_query(query)
        operation, target = req['operation'], req['target']
        params = req['params']
        if operation == 'list_projects':
            if target not in self._organizations:
                raise Denied('SONAR_READ_ORGANIZATION_DENIED')
            projects = [{'key': key} for key in (
                discover(self._reader, target)
                if self._allowed_projects is None else
                [self._check_project(key) for key in sorted(self._allowed_projects)])]
            result = self._page(projects, page=params['page'],
                                page_size=params['pageSize'],
                                field='projects', name=operation)
            result['organization'] = target
            return result

        if operation == 'list_issues':
            project = self._check_project(target)
            page, page_size = params['page'], params['pageSize']
            if (page - 1) * page_size + page_size > MAX_RESULTS:
                raise Denied('SONAR_READ_PAGE_WINDOW_EXCEEDED')
            data = self._reader.call('GET', '/api/issues/search', {
                'componentKeys': project, 'p': str(page), 'ps': str(page_size)})
            total = self._paging(data, page, page_size)
            issues = [self._issue(item, project) for item in data['issues']]
            keys = [item['key'] for item in issues]
            if len(set(keys)) != len(keys):
                raise Denied('SONAR_READ_DUPLICATE_ISSUES')
            offset = (page - 1) * page_size
            has_more = offset + len(issues) < total
            next_page = page + 1 if has_more and (offset + page_size +
                                                  page_size) <= MAX_RESULTS else None
            return {'operation': operation, 'projectKey': project,
                    'issues': issues, 'total': total, 'page': page,
                    'pageSize': page_size, 'hasMore': has_more,
                    'nextPage': next_page, 'coverage':
                    'CAPPED_AT_10000' if total > MAX_RESULTS else
                    'LIVE_PAGE_NOT_CROSS_PAGE_SNAPSHOT'}

        if operation == 'get_issue':
            project = self._check_project(params['projectKey'])
            data = self._reader.call('GET', '/api/issues/search', {
                'componentKeys': project, 'issues': target,
                'p': '1', 'ps': '2'})
            if (type(data) is not dict or type(data.get('issues')) is not list or
                    len(data['issues']) != 1):
                raise Denied('SONAR_READ_ISSUE_NOT_UNIQUE')
            issue = self._issue(data['issues'][0], project)
            if issue['key'] != target:
                raise Denied('SONAR_READ_ISSUE_MISMATCH')
            return {'operation': operation, 'projectKey': project, 'issue': issue}

        if operation == 'get_quality_gate':
            project = self._check_project(target)
            data = self._reader.call('GET', '/api/qualitygates/project_status',
                                     {'projectKey': project})
            return self._quality_gate(data, project)
        raise Denied('SONAR_READ_OPERATION_DENIED')
