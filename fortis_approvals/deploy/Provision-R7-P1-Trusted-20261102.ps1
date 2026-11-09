# OWNER-ONLY GO-1 PROVISIONER. SOURCE ONLY; do not execute without a separate owner decision.
# Creates only fortis-r7-client and six scoped trust files in the five R7 volumes.
# Never starts R7, changes fortis-repo-test, calls Sonar, or modifies the state volume.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$ImageTag = 'fortis-r7-unified-read-ask-candidate:review-p1-scoped-20261102-fac3131e'
$ImageId = 'sha256:23667619c6dfac33466d0e0b4b60bcb22fb7dccb14b0a024f2c062bac0a18ce4'
$ClientVolume = 'fortis-r7-client'
$ServerVolumes = @(
    'fortis-r7-state',
    'fortis-r7-identity',
    'fortis-r7-grant',
    'fortis-r7-sonar-token'
)

$bootstrap = @'
import datetime
import os
import re
import secrets
import stat
import sys

class BootstrapStop(Exception):
    def __init__(self, code):
        self.code = code

def stop(code):
    raise BootstrapStop(code)

def _open_root(path, expected_uid=0, expected_gid=0):
    try:
        info = os.lstat(path)
    except OSError:
        stop('VOLUME_ROOT_UNAVAILABLE')
    mode = stat.S_IMODE(info.st_mode)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != expected_uid or
            info.st_gid != expected_gid or mode & 0o022 or not mode & 0o200):
        stop('VOLUME_ROOT_METADATA_UNEXPECTED')
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        stop('VOLUME_ROOT_OPEN_FAILED')
    opened = os.fstat(fd)
    if (not stat.S_ISDIR(opened.st_mode) or opened.st_ino != info.st_ino or
            opened.st_dev != info.st_dev):
        os.close(fd)
        stop('VOLUME_ROOT_CHANGED')
    return fd

def _open_private_state(state_fd):
    try:
        info = os.stat('private', dir_fd=state_fd, follow_symlinks=False)
    except OSError:
        stop('R7_STATE_PRIVATE_MISSING')
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 10001 or
            info.st_gid != 10001 or stat.S_IMODE(info.st_mode) != 0o700):
        stop('R7_STATE_PRIVATE_METADATA')
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open('private', flags, dir_fd=state_fd)
    except OSError:
        stop('R7_STATE_PRIVATE_OPEN_FAILED')
    opened = os.fstat(fd)
    if opened.st_ino != info.st_ino or opened.st_dev != info.st_dev:
        os.close(fd)
        stop('R7_STATE_PRIVATE_CHANGED')
    return fd

def preflight(paths=None):
    paths = paths or {
        'state': '/state', 'identity': '/run/r7-identity',
        'grant': '/run/r7-grant', 'token': '/run/r7-sonar-token'}
    state_fd = _open_root(paths['state'])
    try:
        if os.listdir(state_fd) != ['private']:
            stop('R7_STATE_ROOT_NOT_FRESH')
        private_fd = _open_private_state(state_fd)
        try:
            if os.listdir(private_fd):
                stop('R7_STATE_PRIVATE_NOT_EMPTY')
        finally:
            os.close(private_fd)
    finally:
        os.close(state_fd)
    for key in ('identity', 'grant', 'token'):
        fd = _open_root(paths[key])
        try:
            if os.listdir(fd):
                stop('R7_PRIVATE_VOLUME_NOT_EMPTY')
        finally:
            os.close(fd)
    print('R7_P1_EXISTING_VOLUMES_READONLY_PREFLIGHT_PASS')

def _read_token(token=None):
    if token is None:
        raw = sys.stdin.buffer.read(4099)
        if len(raw) > 4098:
            stop('SONAR_TOKEN_INPUT_TOO_LARGE')
        if raw.endswith(b'\r\n'):
            token = raw[:-2]
        elif raw.endswith(b'\n'):
            token = raw[:-1]
        else:
            stop('SONAR_TOKEN_INPUT_TERMINATOR_REQUIRED')
    if (not isinstance(token, bytes) or not 12 <= len(token) <= 4096 or
            any(byte < 33 or byte > 126 for byte in token)):
        stop('SONAR_TOKEN_INPUT_INVALID')
    return token

def _build_tls():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    now = datetime.datetime.now(datetime.timezone.utc)
    not_before = now - datetime.timedelta(minutes=5)
    not_after = now + datetime.timedelta(days=90)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    server_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'Fortis R7 P1 Local CA')])
    ca_cert = (x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before).not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=None, decipher_only=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(
            ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256()))
    server_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'host.docker.internal')])
    server_cert = (x509.CertificateBuilder()
        .subject_name(server_name).issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before).not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName('host.docker.internal')]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([
            ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=None, decipher_only=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(
            server_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
            ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256()))
    key_pem = server_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
    chain_pem = server_cert.public_bytes(serialization.Encoding.PEM) + ca_pem
    fingerprint = server_cert.fingerprint(hashes.SHA256()).hex()
    ca_fingerprint = ca_cert.fingerprint(hashes.SHA256()).hex()
    expiry = server_cert.not_valid_after_utc.isoformat().replace('+00:00', 'Z')
    del ca_key
    del server_key
    return key_pem, chain_pem, ca_pem, fingerprint, ca_fingerprint, expiry

def _stage_file(dir_fd, name, data, uid, gid, mode):
    if not data or name in os.listdir(dir_fd):
        stop('R7_TARGET_FILE_ALREADY_EXISTS')
    temporary = '.r7-p1-stage-' + secrets.token_hex(16)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(temporary, flags, 0o600, dir_fd=dir_fd)
    except OSError:
        stop('R7_STAGE_FILE_CREATE_FAILED')
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                stop('R7_STAGE_FILE_WRITE_FAILED')
            view = view[written:]
        os.fchown(fd, uid, gid)
        os.fchmod(fd, mode)
        os.fsync(fd)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or
                info.st_gid != gid or stat.S_IMODE(info.st_mode) != mode or
                info.st_size != len(data)):
            stop('R7_STAGE_FILE_METADATA_FAILED')
    finally:
        os.close(fd)
    return temporary

def _commit_file(dir_fd, temporary, name):
    try:
        os.link(temporary, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd,
                follow_symlinks=False)
        os.fsync(dir_fd)
        os.unlink(temporary, dir_fd=dir_fd)
        os.fsync(dir_fd)
    except OSError:
        stop('R7_ATOMIC_FILE_COMMIT_FAILED_REVIEW_REQUIRED')

def _open_empty_roots(paths):
    opened = {}
    try:
        for key, path in paths.items():
            fd = _open_root(path)
            opened[key] = fd
            if os.listdir(fd):
                stop('R7_PRIVATE_VOLUME_NOT_EMPTY')
        return opened
    except BaseException:
        for fd in opened.values():
            os.close(fd)
        raise

def provision(paths=None, token=None, server_uid=10001, server_gid=10001,
              client_uid=1000, client_gid=1000):
    paths = paths or {
        'identity': '/run/r7-identity', 'grant': '/run/r7-grant',
        'token': '/run/r7-sonar-token', 'client': '/run/r7-client'}
    fds = _open_empty_roots(paths)
    try:
        token = _read_token(token)
        grant = secrets.token_urlsafe(48)
        if not re.fullmatch(r'[A-Za-z0-9._~+/=-]{32,256}', grant):
            stop('R7_GENERATED_GRANT_INVALID')
        key_pem, chain_pem, ca_pem, fingerprint, ca_fingerprint, expiry = _build_tls()
        grant_pem = (grant + '\n').encode('ascii')
        token_pem = token + b'\n'
        files = (
            ('identity', 'server.crt', chain_pem, server_uid, server_gid, 0o644),
            ('identity', 'server.key', key_pem, server_uid, server_gid, 0o600),
            ('grant', 'grant', grant_pem, server_uid, server_gid, 0o600),
            ('token', 'token', token_pem, server_uid, server_gid, 0o600),
            ('client', 'grant', grant_pem, client_uid, client_gid, 0o600),
            ('client', 'server.crt', ca_pem, client_uid, client_gid, 0o644))
        staged = []
        for key, name, data, uid, gid, mode in files:
            temp = _stage_file(fds[key], name, data, uid, gid, mode)
            staged.append((fds[key], temp, name))
        for dir_fd, temp, name in staged:
            _commit_file(dir_fd, temp, name)
        print('R7_P1_TRUST_FILES_CREATED=6')
        print('R7_P1_TLS_CA_SHA256=' + ca_fingerprint)
        print('R7_P1_TLS_LEAF_SHA256=' + fingerprint)
        print('R7_P1_TLS_SAN=host.docker.internal')
        print('R7_P1_TLS_VALID_DAYS=90')
        print('R7_P1_SONAR_TOKEN_STORED=YES')
        print('R7_P1_SONAR_NETWORK_REQUESTS=NONE')
    finally:
        for fd in fds.values():
            os.close(fd)

def _read_file(dir_fd, name, uid, gid, mode, minimum, maximum):
    try:
        info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError:
        stop('R7_PROVISIONED_FILE_MISSING')
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or
            info.st_gid != gid or stat.S_IMODE(info.st_mode) != mode or
            not minimum <= info.st_size <= maximum or info.st_nlink != 1):
        stop('R7_PROVISIONED_FILE_METADATA_INVALID')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(name, flags, dir_fd=dir_fd)
    except OSError:
        stop('R7_PROVISIONED_FILE_OPEN_FAILED')
    opened = os.fstat(fd)
    if opened.st_ino != info.st_ino or opened.st_dev != info.st_dev:
        os.close(fd)
        stop('R7_PROVISIONED_FILE_CHANGED')
    try:
        chunks = []
        total = 0
        while total <= maximum:
            chunk = os.read(fd, min(4096, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        data = b''.join(chunks)
        if len(data) != info.st_size or total > maximum:
            stop('R7_PROVISIONED_FILE_CHANGED')
        return data
    finally:
        os.close(fd)

def _verify_tls(key_pem, chain_pem, client_ca_pem):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID

    blocks = re.findall(
        rb'-----BEGIN CERTIFICATE-----\n.*?-----END CERTIFICATE-----\n',
        chain_pem, re.DOTALL)
    if len(blocks) != 2 or b''.join(blocks) != chain_pem:
        stop('R7_TLS_CHAIN_FORMAT_INVALID')
    leaf = x509.load_pem_x509_certificate(blocks[0])
    ca = x509.load_pem_x509_certificate(blocks[1])
    client_ca = x509.load_pem_x509_certificate(client_ca_pem)
    key = serialization.load_pem_private_key(key_pem, password=None)
    if client_ca_pem != blocks[1] or leaf.issuer != ca.subject:
        stop('R7_TLS_CA_CHAIN_MISMATCH')
    if key.public_key().public_numbers() != leaf.public_key().public_numbers():
        stop('R7_TLS_PRIVATE_KEY_MISMATCH')
    ca.public_key().verify(
        ca.signature, ca.tbs_certificate_bytes,
        ec.ECDSA(ca.signature_hash_algorithm))
    ca.public_key().verify(
        leaf.signature, leaf.tbs_certificate_bytes,
        ec.ECDSA(leaf.signature_hash_algorithm))
    ca_constraints = ca.extensions.get_extension_for_class(
        x509.BasicConstraints).value
    leaf_constraints = leaf.extensions.get_extension_for_class(
        x509.BasicConstraints).value
    san = leaf.extensions.get_extension_for_class(
        x509.SubjectAlternativeName).value
    eku = leaf.extensions.get_extension_for_class(
        x509.ExtendedKeyUsage).value
    ca_usage = ca.extensions.get_extension_for_class(x509.KeyUsage).value
    leaf_usage = leaf.extensions.get_extension_for_class(x509.KeyUsage).value
    if (not ca_constraints.ca or ca_constraints.path_length != 0 or
            not ca_usage.key_cert_sign or not ca_usage.crl_sign or
            leaf_constraints.ca or not leaf_usage.digital_signature or
            san.get_values_for_type(x509.DNSName) != ['host.docker.internal'] or
            ExtendedKeyUsageOID.SERVER_AUTH not in eku):
        stop('R7_TLS_CERTIFICATE_PROFILE_INVALID')
    now = datetime.datetime.now(datetime.timezone.utc)
    if (not leaf.not_valid_before_utc <= now < leaf.not_valid_after_utc or
            not ca.not_valid_before_utc <= now < ca.not_valid_after_utc):
        stop('R7_TLS_CERTIFICATE_NOT_CURRENT')
    lifetime = leaf.not_valid_after_utc - leaf.not_valid_before_utc
    if lifetime > datetime.timedelta(days=91):
        stop('R7_TLS_CERTIFICATE_LIFETIME_INVALID')
    if ca.subject != ca.issuer:
        stop('R7_TLS_CA_NOT_SELF_ISSUED')
    return (leaf.fingerprint(hashes.SHA256()).hex(),
            ca.fingerprint(hashes.SHA256()).hex(),
            leaf.not_valid_after_utc.isoformat().replace('+00:00', 'Z'))

def verify(paths=None, server_uid=10001, server_gid=10001,
           client_uid=1000, client_gid=1000):
    paths = paths or {
        'identity': '/run/r7-identity', 'grant': '/run/r7-grant',
        'token': '/run/r7-sonar-token', 'client': '/run/r7-client'}
    expected = {
        'identity': {'server.crt', 'server.key'},
        'grant': {'grant'}, 'token': {'token'},
        'client': {'grant', 'server.crt'}}
    fds = {}
    try:
        for key, path in paths.items():
            fd = _open_root(path)
            fds[key] = fd
            if set(os.listdir(fd)) != expected[key]:
                stop('R7_PROVISIONED_VOLUME_CONTENTS_INVALID')
        identity = fds['identity']
        grant_fd = fds['grant']
        token_fd = fds['token']
        client = fds['client']
        chain = _read_file(identity, 'server.crt', server_uid, server_gid,
                           0o644, 100, 16384)
        key = _read_file(identity, 'server.key', server_uid, server_gid,
                         0o600, 100, 16384)
        server_grant = _read_file(grant_fd, 'grant', server_uid, server_gid,
                                  0o600, 33, 257)
        sonar_token = _read_file(token_fd, 'token', server_uid, server_gid,
                                 0o600, 13, 4097)
        client_grant = _read_file(client, 'grant', client_uid, client_gid,
                                  0o600, 33, 257)
        client_ca = _read_file(client, 'server.crt', client_uid, client_gid,
                               0o644, 100, 8192)
        if server_grant != client_grant or not server_grant.endswith(b'\n'):
            stop('R7_SERVER_CLIENT_GRANT_MISMATCH')
        grant_value = server_grant[:-1]
        if not re.fullmatch(rb'[A-Za-z0-9._~+/=-]{32,256}', grant_value):
            stop('R7_MACHINE_GRANT_FORMAT_INVALID')
        if not sonar_token.endswith(b'\n'):
            stop('R7_SONAR_TOKEN_FILE_FORMAT_INVALID')
        token_value = sonar_token[:-1]
        if (not 12 <= len(token_value) <= 4096 or
                any(byte < 33 or byte > 126 for byte in token_value) or
                token_value == grant_value):
            stop('R7_SONAR_TOKEN_FILE_FORMAT_INVALID')
        fingerprint, ca_fingerprint, expiry = _verify_tls(key, chain, client_ca)
        print('R7_P1_FILE=server.crt|uid=10001|gid=10001|mode=0644')
        print('R7_P1_FILE=server.key|uid=10001|gid=10001|mode=0600')
        print('R7_P1_FILE=server-grant|uid=10001|gid=10001|mode=0600')
        print('R7_P1_FILE=sonar-token|uid=10001|gid=10001|mode=0600')
        print('R7_P1_FILE=client-grant|uid=1000|gid=1000|mode=0600')
        print('R7_P1_FILE=client-ca|uid=1000|gid=1000|mode=0644')
        print('R7_P1_SERVER_CLIENT_GRANT_MATCH_PASS')
        print('R7_P1_TLS_CA_SHA256=' + ca_fingerprint)
        print('R7_P1_TLS_LEAF_SHA256=' + fingerprint)
        print('R7_P1_TLS_SAN=host.docker.internal')
        print('R7_P1_TLS_NOT_AFTER=' + expiry)
        print('R7_P1_SONAR_TOKEN_STORED=YES')
        print('R7_P1_METADATA_AND_TLS_VERIFY_PASS')
    finally:
        for fd in fds.values():
            os.close(fd)

def main():
    if len(sys.argv) != 2:
        stop('BOOTSTRAP_MODE_REQUIRED')
    mode = sys.argv[1]
    if mode == 'preflight':
        preflight()
    elif mode == 'provision':
        provision()
    elif mode == 'verify':
        verify()
    else:
        stop('BOOTSTRAP_MODE_UNKNOWN')

if __name__ == '__main__':
    try:
        main()
    except BootstrapStop as error:
        print('FORTIS_R7_P1_BOOTSTRAP_STOP=' + error.code)
        raise SystemExit(2)
    except BaseException:
        print('FORTIS_R7_P1_BOOTSTRAP_STOP=UNEXPECTED_FAILURE_REVIEW_REQUIRED')
        raise SystemExit(3)
'@
$bootstrapB64 = [Convert]::ToBase64String(
    [Text.Encoding]::UTF8.GetBytes($bootstrap)
)
$pythonLoader = "exec(compile(__import__('base64').b64decode(__import__('sys').stdin.buffer.readline().strip(),validate=True),'<r7-p1-bootstrap>','exec'))"

function Invoke-R7Bootstrap {
    param(
        [ValidateSet('preflight','provision','verify')]
        [string]$Mode,
        [byte[]]$SecretBytes
    )
    $dockerArgs = @(
        'run','--rm','-i','--pull=never','--network','none','--read-only',
        '--pids-limit','16','--memory','128m',
        '--security-opt','no-new-privileges:true'
    )
    if ($Mode -eq 'preflight') {
        $dockerArgs += @('--user','10001:10001','--cap-drop','ALL')
    }
    elseif ($Mode -eq 'provision') {
        $dockerArgs += @('--user','0:0','--cap-drop','ALL',
            '--cap-add','CHOWN','--cap-add','FOWNER')
    }
    else {
        $dockerArgs += @('--user','0:0','--cap-drop','ALL',
            '--cap-add','DAC_OVERRIDE')
    }
    if ($Mode -eq 'preflight') {
        $dockerArgs += @(
            '--mount','type=volume,source=fortis-r7-state,target=/state,readonly',
            '--mount','type=volume,source=fortis-r7-identity,target=/run/r7-identity,readonly',
            '--mount','type=volume,source=fortis-r7-grant,target=/run/r7-grant,readonly',
            '--mount','type=volume,source=fortis-r7-sonar-token,target=/run/r7-sonar-token,readonly'
        )
    }
    elseif ($Mode -eq 'provision') {
        $dockerArgs += @(
            '--mount','type=volume,source=fortis-r7-identity,target=/run/r7-identity',
            '--mount','type=volume,source=fortis-r7-grant,target=/run/r7-grant',
            '--mount','type=volume,source=fortis-r7-sonar-token,target=/run/r7-sonar-token',
            '--mount','type=volume,source=fortis-r7-client,target=/run/r7-client'
        )
    }
    else {
        $dockerArgs += @(
            '--mount','type=volume,source=fortis-r7-identity,target=/run/r7-identity,readonly',
            '--mount','type=volume,source=fortis-r7-grant,target=/run/r7-grant,readonly',
            '--mount','type=volume,source=fortis-r7-sonar-token,target=/run/r7-sonar-token,readonly',
            '--mount','type=volume,source=fortis-r7-client,target=/run/r7-client,readonly'
        )
    }
    $dockerArgs += @(
        '--entrypoint','python',$ImageId,'-c',$pythonLoader,$Mode
    )
    $prefix = [Text.Encoding]::ASCII.GetBytes($bootstrapB64 + "`n")
    if ($Mode -eq 'provision') {
        if ($null -eq $SecretBytes -or $SecretBytes.Length -lt 12 -or $SecretBytes.Length -gt 4096) {
            throw 'R7_P1_SECRET_INPUT_MISSING_OR_INVALID'
        }
        $payloadBytes = New-Object byte[] ($prefix.Length + $SecretBytes.Length + 1)
        [Array]::Copy($prefix, 0, $payloadBytes, 0, $prefix.Length)
        [Array]::Copy($SecretBytes, 0, $payloadBytes, $prefix.Length, $SecretBytes.Length)
        $payloadBytes[$payloadBytes.Length - 1] = 10
    }
    else {
        $payloadBytes = $prefix
    }
    foreach ($argument in $dockerArgs) {
        if ($argument -match '\s' -or $argument.Contains('"')) {
            [Array]::Clear($payloadBytes, 0, $payloadBytes.Length)
            throw 'R7_P1_DOCKER_ARGUMENT_REQUIRES_REVIEWED_QUOTING'
        }
    }
    # Resolve exactly one Windows executable; 'docker' can match docker.exe and docker.
    $dockerPath = (Get-Command docker.exe -CommandType Application -ErrorAction Stop |
        Select-Object -First 1).Source
    if ([string]::IsNullOrWhiteSpace($dockerPath) -or
        -not (Test-Path -LiteralPath $dockerPath -PathType Leaf)) {
        throw 'R7_P1_DOCKER_EXECUTABLE_NOT_FOUND'
    }
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $dockerPath
    $startInfo.Arguments = [string]::Join(' ', $dockerArgs)
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $started = $false
    try {
        if (-not $process.Start()) { throw 'R7_P1_DOCKER_PROCESS_START_FAILED' }
        $started = $true
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        try {
            $process.StandardInput.BaseStream.Write($payloadBytes, 0, $payloadBytes.Length)
            $process.StandardInput.BaseStream.Flush()
        }
        finally {
            $process.StandardInput.Close()
        }
        if (-not $process.WaitForExit(120000)) {
            try { $process.Kill() } catch {}
            $process.WaitForExit()
            throw 'R7_P1_BOOTSTRAP_TIMEOUT_REVIEW_REQUIRED'
        }
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        $exitCode = $process.ExitCode
        if (-not [string]::IsNullOrEmpty($stdout)) { Write-Host $stdout.TrimEnd() }
        if (-not [string]::IsNullOrEmpty($stderr)) { Write-Host $stderr.TrimEnd() }
    }
    finally {
        try {
            if ($started -and -not $process.HasExited) {
                try { $process.Kill() } catch {}
                try { $process.WaitForExit() } catch {}
            }
        }
        finally {
            [Array]::Clear($payloadBytes, 0, $payloadBytes.Length)
            $process.Dispose()
        }
    }
    if ($exitCode -ne 0) {
        throw "R7_P1_BOOTSTRAP_$($Mode.ToUpperInvariant())_FAILED_REVIEW_REQUIRED"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI missing'
}
$engineOs = (& docker info --format '{{.OSType}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $engineOs -cne 'linux') {
    throw 'R7_P1_LINUX_DOCKER_ENGINE_REQUIRED'
}
$imageIdActual = (& docker image inspect --format '{{.Id}}' $ImageTag 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $imageIdActual -cne $ImageId) {
    throw 'R7_P1_EXACT_SCOPED_IMAGE_ID_MISMATCH'
}
$allVolumes = @(& docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'R7_P1_VOLUME_LIST_FAILED' }
foreach ($volume in $ServerVolumes) {
    if ($allVolumes -cnotcontains $volume) {
        throw "R7_P1_REQUIRED_VOLUME_MISSING: $volume"
    }
}
if ($allVolumes -ccontains $ClientVolume) {
    throw 'R7_P1_CLIENT_VOLUME_ALREADY_EXISTS_STOP'
}
$r7Containers = @(& docker ps -a --filter 'label=com.docker.compose.project=fortis-r7-p1' --format '{{.Names}}')
if ($LASTEXITCODE -ne 0) { throw 'R7_P1_CONTAINER_LIST_FAILED' }
if ($r7Containers.Count -ne 0) { throw 'R7_P1_CONTAINER_ALREADY_EXISTS_STOP' }

foreach ($volume in $ServerVolumes) {
    $metadata = (& docker volume inspect --format '{{.Name}}|{{.Driver}}|{{.Scope}}' $volume 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $metadata -cne "$volume|local|local") {
        throw "R7_P1_VOLUME_METADATA_MISMATCH: $volume"
    }
    $refs = @(& docker ps -a --filter "volume=$volume" --format '{{.Names}}')
    if ($LASTEXITCODE -ne 0) { throw 'R7_P1_VOLUME_REFERENCE_CHECK_FAILED' }
    if ($refs.Count -ne 0) { throw "R7_P1_VOLUME_ATTACHED_STOP: $volume" }
    Write-Host "R7_P1_EXISTING_VOLUME_METADATA_PASS=$volume"
}

Invoke-R7Bootstrap -Mode preflight
Write-Host 'FORTIS_R7_P1_EXISTING_VOLUMES_CONTENT_LAYOUT_PASS'
Write-Host 'R7 P1 GO-1 ONLY: creates fortis-r7-client and writes TLS/grant/Sonar token files.'
Write-Host 'No R7 service, no Repo container change, no Sonar HTTP request, no owner enrollment.'
Write-Host 'Use a newly created owner-approved SonarCloud API token with the privileges required by the intended typed operations; do not reuse the existing G4 credential.'
Write-Host 'The accepted owner architecture permits a broadly privileged account token; do not require a Browse-only SOT or a dedicated low-privilege account.'
Write-Host 'A stolen/extracted token can bypass Fortis ASK and act with the issuing account privileges; keep it private to Fortis and accept the host/backup/memory trust boundary.'
Write-Host 'This offline script cannot validate token type, expiry or upstream permissions; existing G4 live READ/ASK/Reject evidence is not proof of a real Sonar WRITE.'
Write-Host 'Docker/Windows administrators can still inspect Docker volumes and host memory.'
$ack = Read-Host 'Type PROVISION-R7-P1 to authorize this one-shot local provisioning run'
if ($ack -cne 'PROVISION-R7-P1') {
    throw 'R7_P1_PROVISIONING_CANCELLED_NO_SECRET_REQUESTED'
}
$secure = $null
$ptr = [IntPtr]::Zero
$secretBytes = $null
try {
    $secure = Read-Host 'New owner-approved SonarCloud API token (hidden local input)' -AsSecureString
    if ($secure.Length -lt 12 -or $secure.Length -gt 4096) {
        throw 'R7_P1_SONAR_TOKEN_LENGTH_INVALID'
    }
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $secretBytes = New-Object byte[] $secure.Length
    for ($i = 0; $i -lt $secure.Length; $i++) {
        $code = [Runtime.InteropServices.Marshal]::ReadInt16($ptr, 2 * $i)
        if ($code -lt 33 -or $code -gt 126) {
            throw 'R7_P1_SONAR_TOKEN_FORMAT_INVALID'
        }
        $secretBytes[$i] = [byte]$code
    }
    $volumesNow = @(& docker volume ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0 -or $volumesNow -ccontains $ClientVolume) {
        throw 'R7_P1_CLIENT_VOLUME_APPEARED_DURING_PREFLIGHT_STOP'
    }
    $containersNow = @(& docker ps -a --filter 'label=com.docker.compose.project=fortis-r7-p1' --format '{{.Names}}')
    if ($LASTEXITCODE -ne 0 -or $containersNow.Count -ne 0) {
        throw 'R7_P1_CONTAINER_APPEARED_DURING_PREFLIGHT_STOP'
    }
    foreach ($volume in $ServerVolumes) {
        $refsNow = @(& docker ps -a --filter "volume=$volume" --format '{{.Names}}')
        if ($LASTEXITCODE -ne 0 -or $refsNow.Count -ne 0) {
            throw "R7_P1_VOLUME_ATTACHMENT_CHANGED_STOP: $volume"
        }
    }
    $provisionId = [Guid]::NewGuid().ToString('N')
    & docker volume create --label 'com.fortis.r7.p1.role=client-only' --label "com.fortis.r7.p1.provision-id=$provisionId" $ClientVolume | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'R7_P1_CLIENT_VOLUME_CREATE_FAILED_REVIEW_REQUIRED'
    }
    $clientMetadata = (& docker volume inspect --format '{{.Name}}|{{.Driver}}|{{.Scope}}' $ClientVolume 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $clientMetadata -cne "$ClientVolume|local|local") {
        throw 'R7_P1_CLIENT_VOLUME_METADATA_FAILED_REVIEW_REQUIRED'
    }
    $clientLabel = (& docker volume inspect --format '{{ index .Labels "com.fortis.r7.p1.provision-id" }}' $ClientVolume 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $clientLabel -cne $provisionId) {
        throw 'R7_P1_CLIENT_VOLUME_NOT_CREATED_BY_THIS_RUN_STOP'
    }
    $clientRefs = @(& docker ps -a --filter "volume=$ClientVolume" --format '{{.Names}}')
    if ($LASTEXITCODE -ne 0 -or $clientRefs.Count -ne 0) {
        throw 'R7_P1_CLIENT_VOLUME_UNEXPECTED_ATTACHMENT_REVIEW_REQUIRED'
    }
    Write-Host 'R7_P1_CLIENT_VOLUME_CREATED_PASS'
    Invoke-R7Bootstrap -Mode preflight
    Write-Host 'R7_P1_EXISTING_SERVER_VOLUMES_RECHECK_PASS'
    foreach ($volume in $ServerVolumes) {
        $finalRefs = @(& docker ps -a --filter "volume=$volume" --format '{{.Names}}')
        if ($LASTEXITCODE -ne 0 -or $finalRefs.Count -ne 0) {
            throw "R7_P1_VOLUME_ATTACHED_BEFORE_WRITE_STOP: $volume"
        }
    }
    Invoke-R7Bootstrap -Mode provision -SecretBytes $secretBytes
    Invoke-R7Bootstrap -Mode verify
    Write-Host 'FORTIS_R7_P1_TRUSTED_MATERIAL_PROVISIONED_PASS'
    Write-Host 'FORTIS_R7_P1_SONAR_NETWORK_REQUESTS=NONE'
    Write-Host 'FORTIS_R7_P1_SONAR_POST=DISABLED'
    Write-Host 'FORTIS_R7_P1_R7_CONTAINERS_STARTED=NONE'
    Write-Host 'FORTIS_R7_P1_REPO_CONTAINER_CHANGED=NO'
    Write-Host 'FORTIS_R7_P1_DEPLOYMENT=NOT_AUTHORIZED'
}
catch {
    Write-Host 'FORTIS_R7_P1_PROVISIONING_FAILED_REVIEW_REQUIRED'
    throw
}
finally {
    if ($null -ne $secretBytes) {
        [Array]::Clear($secretBytes, 0, $secretBytes.Length)
    }
    if ($ptr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
    if ($null -ne $secure) {
        $secure.Dispose()
    }
}
