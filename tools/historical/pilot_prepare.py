#!/usr/bin/env python3
"""Prepare reversible /data state for the boot-only KSU/EROFS pilot."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SERIAL = 'DEVICE_SERIAL'
ADB = ['/Users/REDACTED/Developer/unixnu-macos/tools/platform-tools/adb', '-s', SERIAL]
OUT = ROOT / 'c17-port/kernel-pilot-r1'
LOG = OUT / 'prepare-commands.jsonl'


def run(args, timeout=60):
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    row = dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(), argv=args,
               rc=p.returncode, stdout=p.stdout.decode(errors='replace'), stderr=p.stderr.decode(errors='replace'))
    with LOG.open('a') as f:
        f.write(json.dumps(row) + '\n')
    if p.returncode:
        raise RuntimeError(row)
    # Fastboot emits both successful getvar results and progress on stderr.
    # Keep ADB shell stdout separate because callers parse it as device data.
    if Path(args[0]).name == 'fastboot':
        return row['stdout'] + row['stderr']
    return row['stdout']


def root(command):
    return run(ADB + ['shell', 'su -c ' + shlex.quote(command)])


def main():
    marker = OUT / 'modules-before.json'
    assert not marker.exists(), 'Do not replace an existing pre-pilot state record'
    m = json.loads((OUT / 'manifest.json').read_text())
    assert hashlib.sha256((OUT / 'boot_a.img').read_bytes()).hexdigest() == m['sha256']
    before = root('id; uname -a; cat /proc/sys/kernel/random/boot_id; sha256sum /dev/block/by-name/boot_a')
    assert 'uid=0(root)' in before and '#50 ' in before
    assert '9cce59f34b1c67cfbfbd0fbc4b8947788d9520e35580f50ca9bfd4fb6e341a21' in before
    (OUT / 'device-before.txt').write_text(before)
    listing = root('for d in /data/adb/modules/*; do test -d "$d" || continue; '
                   'if test -e "$d/disable"; then echo "${d##*/}:disabled"; else echo "${d##*/}:enabled"; fi; done')
    states = {}
    for line in listing.splitlines():
        name, state = line.split(':')
        assert re.fullmatch(r'[A-Za-z0-9_.-]+', name) and state in ('enabled', 'disabled')
        states[name] = state
    marker.write_text(json.dumps(states, indent=2) + '\n')
    commands = []
    restore = []
    for name, state in states.items():
        if state == 'enabled':
            path = '/data/adb/modules/' + name + '/disable'
            commands.append('touch ' + shlex.quote(path))
            restore.append('rm -f ' + shlex.quote(path))
    if commands:
        root('set -e; ' + '; '.join(commands))
    (OUT / 'restore-module-flags.sh').write_text('#!/system/bin/sh\nset -e\n' + '\n'.join(restore) + '\n')
    remote = '/data/local/tmp/c17-kernel-pilot'
    run(ADB + ['shell', 'mkdir -p ' + remote])
    for p in [ROOT / 'c17-port/evidence/tethering-apex/apex_payload.img',
              ROOT / 'c17-port/candidate-r2/test2-my_manifest.img']:
        run(ADB + ['push', str(p), remote + '/' + p.name])
    print(json.dumps(dict(prepared=True, serial=SERIAL, module_states=states,
                          candidate_boot_sha256=m['sha256'], partition_writes=False), indent=2))


if __name__ == '__main__':
    main()
