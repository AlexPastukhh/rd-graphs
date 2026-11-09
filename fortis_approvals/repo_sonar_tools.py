"""Fortis Repo-side restricted Sonar client bridge; SOURCE ONLY, NOT EXPOSED MCP.

Connects to ONE pinned trusted Fortis TLS endpoint. The only secret it reads
is a *limited machine ingress grant*, never an upstream SonarCloud credential.
Owner must provision its own read-only 0600 file OUTSIDE Repo workspace and
mount it at /run/fortis-client/grant; public server cert at server.crt.
No arbitrary HTTP URL/method/body, owner route, Docker, config or admin action.
Any AI with arbitrary Repo shell can potentially read its machine grant:
account for that with server-side actor scopes/least privilege and host ACL.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import ssl
import stat
import sys
from urllib import error, request
import uuid

from .core import Denied
from .repo_action_contract import validate_intent, validate_read_query


ENDPOINT = 'https://host.docker.internal:19104'
PUBLIC_SERVER_CERT = '/run/fortis-client/server.crt'
CLIENT_GRANT_FILE = '/run/fortis-client/grant'
MAX_RESPONSE_BYTES = 65536
_OPERATIONS = {
    'sonar.list_projects': ('list_projects','/v1/reads'),
    'sonar.list_issues': ('list_issues','/v1/reads'),
    'sonar.get_issue': ('get_issue','/v1/reads'),
    'sonar.get_quality_gate': ('get_quality_gate','/v1/reads'),
    'sonar.propose_accept_issue': ('accept_issue','/v1/actions'),
    'approvals.request_status': (None, '/v1/requests/'),
}
_STATES = frozenset(('PENDING','APPROVED','DISPATCHED','EXECUTED','REJECTED',
                     'DENIED','EXPIRED','STALE','UNCERTAIN'))


class _NoRedirectHandler(request.HTTPRedirectHandler):
    """A pinned gateway response must never redirect its machine grant."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _reject_nonfinite(_value):
    raise ValueError('FORTIS_NONFINITE_RESPONSE')


def _parse_finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('FORTIS_NONFINITE_RESPONSE')
    return number


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('FORTIS_DUPLICATE_JSON_FIELD')
        result[key] = value
    return result


def _grant_from_file(path=CLIENT_GRANT_FILE):
    item=Path(path)
    if (not item.is_absolute() or item.is_symlink() or not item.is_file()):
        raise Denied('FORTIS_MACHINE_GRANT_FILE_REQUIRED')
    info=item.stat()
    if (not stat.S_ISREG(info.st_mode) or
            stat.S_IMODE(info.st_mode)!=0o600 or
            info.st_uid!=os.geteuid() or not 32<=info.st_size<=257 or
            any(item.is_relative_to(p) for p in (
                Path('/workspace/repo'),Path('/workspace/repos')))):
        raise Denied('FORTIS_MACHINE_GRANT_FILE_INSECURE')
    data=item.read_bytes()
    if data.endswith(b'\n'):
        data=data[:-1]
    try:
        credential=data.decode('ascii')
    except UnicodeError:
        raise Denied('FORTIS_MACHINE_GRANT_INVALID') from None
    if not re.fullmatch(r'[A-Za-z0-9._~+/=-]{32,256}',credential):
        raise Denied('FORTIS_MACHINE_GRANT_INVALID')
    return credential


def payload(tool, *, target=None,project_key=None,page=1,page_size=20,
            reason=None,request_id=None):
    """Build a strict request. Proposal MUST have stable request_id provided."""
    if tool not in _OPERATIONS:
        raise Denied('FORTIS_TOOL_NOT_SUPPORTED')
    if tool=='approvals.request_status':
        if (type(request_id) is not str or
                not re.fullmatch(
                    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                    request_id) or
                str(uuid.UUID(request_id)) != request_id):
            raise Denied('FORTIS_STATUS_REQUEST_ID_REQUIRED')
        return '/v1/requests/'+request_id,None
    operation,path=_OPERATIONS[tool]
    if operation=='accept_issue' and request_id is None:
        raise Denied('FORTIS_PROPOSAL_STABLE_REQUEST_ID_REQUIRED')
    ident=request_id or str(uuid.uuid4())
    if type(ident) is not str:
        raise Denied('FORTIS_REQUEST_ID_INVALID')
    params={}
    if operation in ('list_projects','list_issues'):
        params={'page':page,'pageSize':page_size}
    elif operation in ('get_issue','accept_issue'):
        params={'projectKey':project_key}
    body={'requestId':ident,'service':'sonarcloud',
          'operation':operation,'target':target,'params':params,
          'reason':reason or 'Read Sonar quality or propose owner action'}
    if operation=='accept_issue':
        validate_intent(body)
    else:
        validate_read_query(body)
    return path,body


def call(tool, *, target=None,project_key=None,page=1,page_size=20,
         reason=None,request_id=None, transport=None, grant_path=None,
         certificate_path=None):
    """Invoke typed operation; test-only dependency injection via transport.

    Production CLI never exposes transport/certificate/grant path as AI args.
    """
    path,body=payload(tool,target=target,project_key=project_key,page=page,
                      page_size=page_size,reason=reason,request_id=request_id)
    grant=_grant_from_file(grant_path or CLIENT_GRANT_FILE)
    cert=Path(certificate_path or PUBLIC_SERVER_CERT)
    if (not cert.is_absolute() or cert.is_symlink() or
            not cert.is_file() or cert.stat().st_size>16384):
        raise Denied('FORTIS_TRUSTED_PUBLIC_CERT_REQUIRED')
    context=ssl.create_default_context(cafile=str(cert))
    context.minimum_version=ssl.TLSVersion.TLSv1_3
    opener=transport or request.build_opener(
        request.ProxyHandler({}),request.HTTPSHandler(context=context),
        _NoRedirectHandler())
    raw=(json.dumps(body,separators=(',',':'),ensure_ascii=True).encode('ascii')
         if body is not None else None)
    headers={'Host':'host.docker.internal:19104',
             'Accept':'application/json','Authorization':'Bearer '+grant}
    if raw is not None:
        headers['Content-Type']='application/json'
    req=request.Request(ENDPOINT+path,data=raw,headers=headers,
                        method='POST' if raw is not None else 'GET')
    try:
        with opener.open(req,timeout=12) as resp:
            if resp.status != 200 and not (
                    resp.status == 202 and body is not None and
                    body['operation']=='accept_issue'):
                raise Denied('FORTIS_HTTP_UNEXPECTED_STATUS')
            content=resp.read(MAX_RESPONSE_BYTES+1)
            if len(content)>MAX_RESPONSE_BYTES:
                raise Denied('FORTIS_RESPONSE_TOO_LARGE')
            result=json.loads(content, parse_constant=_reject_nonfinite,
                                parse_float=_parse_finite_float,
                                object_pairs_hook=_unique_json_pairs)
    except error.HTTPError as exc:
        # Never expose remote response, URL, Location or Authorization header.
        status = exc.code
        exc.close()
        if 300 <= status < 400:
            raise Denied('FORTIS_REDIRECT_DENIED') from None
        raise Denied('FORTIS_HTTP_'+str(status)) from None
    except Denied:
        raise
    except (error.URLError,TimeoutError,OSError,UnicodeError,ValueError,
            RecursionError):
        raise Denied('FORTIS_UPSTREAM_UNAVAILABLE_OR_INVALID') from None
    if type(result) is not dict:
        raise Denied('FORTIS_RESPONSE_INVALID')
    if body is None or body['operation']=='accept_issue':
        if (set(result)!={'requestId','state'} or
                result['requestId'] != (
                    request_id if body is None else body['requestId']) or
                type(result['state']) is not str or
                result['state'] not in _STATES):
            raise Denied('FORTIS_STATUS_RESPONSE_INVALID')
    else:
        if (set(result)!={'requestId','service','operation','data'} or
                result['requestId']!=body['requestId'] or
                result['operation']!=body['operation'] or
                result['service']!='sonarcloud' or
                type(result['data']) is not dict):
            raise Denied('FORTIS_READ_RESPONSE_INVALID')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(
        description='Restricted owner-approved Fortis Sonar bridge (not live by default)')
    parser.add_argument('tool',choices=sorted(_OPERATIONS))
    parser.add_argument('--target')
    parser.add_argument('--project-key')
    parser.add_argument('--page',type=int,default=1)
    parser.add_argument('--page-size',type=int,default=20)
    parser.add_argument('--reason')
    parser.add_argument('--request-id')
    args=parser.parse_args(argv)
    try:
        result=call(args.tool,target=args.target,project_key=args.project_key,
                    page=args.page,page_size=args.page_size,reason=args.reason,
                    request_id=args.request_id)
    except (Denied,ValueError) as exc:
        # Error tokens carry no private data; never dump underlying exceptions.
        print('FORTIS_REPO_TOOL_DENIED='+str(exc),file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,separators=(',',':')))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
