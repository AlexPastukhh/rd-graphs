#!/usr/bin/env python3
"""Operator-only setup; reuse RDG bootstrap and prepare an isolated gateway secret."""
import argparse
import hmac
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re
import stat
import uuid

TOOLS = Path(__file__).resolve().parent
HOST = SourceFileLoader('gateway_setup_host', str(TOOLS / 'rdg-server.py')).load_module()


def prepare_gateway(credentials_dir, gateway_dir, runtime_uid=None, expected_namespace=None):
    source, target = HOST.outside_code(credentials_dir), HOST.outside_code(gateway_dir)
    HOST.require(not source.is_relative_to(target) and not target.is_relative_to(source),
                 'SEPARATE_CREDENTIALS_REQUIRED')
    for name in ('agent-token.txt', 'namespace-id.txt'):
        HOST.require((source / name).is_file() and not (source / name).is_symlink(), 'CREDENTIAL_UNAVAILABLE')
    token = (source / 'agent-token.txt').read_text(encoding='utf8').strip()
    namespace = (source / 'namespace-id.txt').read_text(encoding='utf8').strip()
    HOST.require(re.fullmatch(r'rdg_[A-Za-z0-9_-]{40,100}', token), 'TOKEN_INVALID')
    HOST.require(str(uuid.UUID(namespace)) == namespace, 'NAMESPACE_INVALID')
    HOST.require(expected_namespace is None or namespace == expected_namespace, 'GATEWAY_NAMESPACE_MISMATCH')
    wanted = {'kind': 'rdg-private-gateway-credential', 'namespaceId': namespace, 'token': token}
    file = target / 'credentials.json'
    if target.exists() and any(target.iterdir()):
        HOST.require(set(p.name for p in target.iterdir()) == {'credentials.json'} and
                     file.is_file() and not file.is_symlink(), 'EXISTING_GATEWAY_DATA_REFUSED')
        current = json.loads(file.read_text(encoding='utf8'))
        HOST.require(isinstance(current, dict) and set(current) == set(wanted) and
                     current['kind'] == wanted['kind'] and current['namespaceId'] == namespace and
                     isinstance(current['token'], str) and hmac.compare_digest(current['token'], token),
                     'GATEWAY_CREDENTIAL_MISMATCH')
    else:
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        with os.fdopen(os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as out:
            out.write(json.dumps(wanted) + '\n'); out.flush(); os.fsync(out.fileno())
    os.chmod(target, 0o700); os.chmod(file, 0o600)
    if runtime_uid is not None:
        HOST.require(os.getuid() == 0 and runtime_uid > 0, 'RUNTIME_UID_INVALID')
        for path in (target, file):
            os.chown(path, runtime_uid, runtime_uid)
    return {'gatewayCredentialPrepared': True, 'namespaceId': namespace, 'credentialLocation': 'gateway-only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data-dir', 'credentials-dir', 'gateway-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--runtime-uid', type=int)
    args = parser.parse_args()
    HOST.require(not args.gateway_dir.resolve().is_relative_to(args.data_dir.resolve()) and
                 not args.data_dir.resolve().is_relative_to(args.gateway_dir.resolve()),
                 'SEPARATE_GATEWAY_DATA_REQUIRED')
    initialized = HOST.initialize(args.data_dir, args.credentials_dir, args.runtime_uid)
    gateway = prepare_gateway(args.credentials_dir, args.gateway_dir, args.runtime_uid,
                              expected_namespace=initialized['namespaceId'])
    print(json.dumps({**initialized, **gateway}))


if __name__ == '__main__':
    main()
