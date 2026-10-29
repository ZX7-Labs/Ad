"""Fixed synthetic worker boundary experiment; never enables product execution.

A launch failure is reported as unavailable, not as passed isolation. The probe
does not exercise arbitrary imported projects, GPU containment or kernel escape.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile


WORKER = r'''
import json, os, socket
from pathlib import Path
checks = {}
checks['input_readable'] = Path('/inputs/canary').read_text() == 'synthetic-input'
try:
    Path('/inputs/canary').write_text('changed')
    checks['input_readonly'] = False
except OSError:
    checks['input_readonly'] = True
checks['host_file_hidden'] = not Path(os.environ['PROBE_HOST_FILE']).exists()
checks['host_environment_hidden'] = 'ZX7_SYNTHETIC_SECRET' not in os.environ
with socket.socket() as client:
    client.settimeout(1)
    try:
        client.connect(('127.0.0.1', int(os.environ['PROBE_HOST_PORT'])))
        checks['host_loopback_unreachable'] = False
    except OSError:
        checks['host_loopback_unreachable'] = True
Path('/out/positive-control').write_text('synthetic-output')
checks['output_writable'] = Path('/out/positive-control').read_text() == 'synthetic-output'
print(json.dumps(checks))
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--require-boundaries', action='store_true')
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    result = {'schema': 1, 'source_commit': subprocess.check_output(
        ['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
        'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'launch_supported': False, 'boundary_checks_passed': False,
        'full_worker_isolation_verified': False,
        'scope': 'Fixed synthetic worker input/output, host-file/environment and host-loopback separation',
        'not_established': ['resource exhaustion containment', 'process-tree cancellation',
                            'GPU isolation', 'hostile native-project safety', 'kernel escape resistance']}
    binary = shutil.which('bwrap')
    if not binary:
        result['blocked_reason'] = 'bubblewrap executable missing'
    else:
        result['bubblewrap_version'] = subprocess.check_output([binary, '--version'], text=True).strip()
        with tempfile.TemporaryDirectory(prefix='zx7-boundary-research-') as temporary, socket.socket() as listener:
            root = Path(temporary)
            incoming, outgoing = root/'inputs', root/'output'
            incoming.mkdir(); outgoing.mkdir()
            (incoming/'canary').write_text('synthetic-input')
            hidden = root/'host-only-canary'; hidden.write_text('synthetic-host-only')
            worker = root/'worker.py'; worker.write_text(WORKER)
            listener.bind(('127.0.0.1', 0)); listener.listen(1)
            command = [binary, '--unshare-all', '--die-with-parent', '--new-session',
                       '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
                       '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
                       '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                       '--ro-bind', str(incoming), '/inputs', '--bind', str(outgoing), '/out',
                       '--ro-bind', str(worker), '/probe.py', '--clearenv',
                       '--setenv', 'PATH', '/usr/bin', '--setenv', 'LC_ALL', 'C',
                       '--setenv', 'PROBE_HOST_FILE', str(hidden),
                       '--setenv', 'PROBE_HOST_PORT', str(listener.getsockname()[1]),
                       '--chdir', '/out', '/usr/bin/python3', '-I', '/probe.py']
            try:
                completed = subprocess.run(command, capture_output=True, text=True, timeout=10,
                                           env={**os.environ, 'ZX7_SYNTHETIC_SECRET': 'synthetic-only'})
                result['launch_exit_code'] = completed.returncode
                result['stderr'] = completed.stderr[-2000:]
                if completed.returncode == 0:
                    checks = json.loads(completed.stdout)
                    expected = {'input_readable', 'input_readonly', 'host_file_hidden',
                                'host_environment_hidden', 'host_loopback_unreachable', 'output_writable'}
                    if set(checks) != expected or any(type(v) is not bool for v in checks.values()):
                        raise ValueError('Malformed worker evidence')
                    result['launch_supported'] = True
                    checks['host_input_unchanged'] = (incoming/'canary').read_text() == 'synthetic-input'
                    checks['host_received_output'] = (outgoing/'positive-control').read_text() == 'synthetic-output'
                    result['checks'] = checks
                    result['boundary_checks_passed'] = all(checks.values())
                else:
                    result['blocked_reason'] = 'Requested isolation profile could not execute its fixed worker'
            except subprocess.TimeoutExpired:
                result['blocked_reason'] = 'Fixed worker launch timed out'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return int(args.require_boundaries and not result['boundary_checks_passed'])


if __name__ == '__main__':
    raise SystemExit(main())
