#!/usr/bin/env python3
"""Modify a clone of verified C16 vendor; preserve inode metadata and labels."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
W = ROOT / 'c17-port'
DEBUGFS = W / 'tool-src/e2fs-build/debugfs/debugfs'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        while True:
            b = f.read(8 << 20)
            if not b:
                return h.hexdigest()
            h.update(b)


def main():
    src = W / 'base-c16/vendor_a.img'
    base_hash = sha(src)
    assert base_hash == 'ae4b291db68eda3ed1155aa2b32a019c30983c7c8379f5f83faa8bc8eac2168f'
    out = W / 'rom-r1/vendor_a.img'
    assert not out.exists()
    subprocess.run(['cp', '-c', str(src), str(out)], check=True)
    work = W / 'evidence/vendor-r1'
    work.mkdir(exist_ok=True)
    log = work / 'debugfs.log'
    def command(text, write=False, absent=False):
        args = [str(DEBUGFS)] + (['-w'] if write else []) + ['-R', text, str(out)]
        p = subprocess.run(args, capture_output=True, text=True, timeout=90)
        s = p.stdout + p.stderr
        with log.open('a') as f:
            f.write(text + '\n' + s + '\n')
        if absent and 'File not found by ext2_lookup' in s:
            return None
        if p.returncode or re.search(r'File not found|Could not allocate|No free|Usage:|while writing|Unknown request', s, re.I):
            raise RuntimeError(s)
        return s
    records = []
    edits = [('/etc/fstab.qcom', W / 'overlays/fstab.qcom-c17'),
             ('/etc/selinux/vendor_sepolicy.cil', W / 'policy-inputs/vendor_sepolicy.cil'),
             ('/etc/init/r91-rom.rc', W / 'overlays/retired-r91-rom.rc')]
    for index, (target, source) in enumerate(edits):
        before = work / f'{index}-before'
        command(f'dump {target} {before}')
        info = command('stat ' + target)
        mode = re.search(r'Mode:\s+(\d+)', info).group(1)
        uid, gid = re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)', info).groups()
        label = work / f'{index}-label'
        command(f'ea_get -f {label} {target} security.selinux')
        assert label.stat().st_size > 0
        command('rm ' + target, True)
        command(f'write {source} {target}', True)
        for field, value in [('mode', '0' + format(0o100000 | int(mode, 8), 'o')), ('uid', uid), ('gid', gid)]:
            command(f'set_inode_field {target} {field} {value}', True)
        command(f'ea_set -f {label} {target} security.selinux', True)
        after = work / f'{index}-after'
        command(f'dump {target} {after}')
        assert sha(after) == sha(source), target
        after_label = work / f'{index}-label-after'
        command(f'ea_get -f {after_label} {target} security.selinux')
        assert after_label.read_bytes() == label.read_bytes()
        newinfo = command('stat ' + target)
        assert re.search(r'Mode:\s+0?' + mode.lstrip('0') + r'\b', newinfo), newinfo
        assert re.search(r'User:\s+' + uid + r'\s+Group:\s+' + gid + r'\b', newinfo), newinfo
        records.append(dict(path=target, before_sha256=sha(before), after_sha256=sha(after),
                            mode=mode, uid=uid, gid=gid, selinux_hex=label.read_bytes().hex()))
    removed = []
    for name in ['precompiled_sepolicy',
                 'precompiled_sepolicy.plat_sepolicy_and_mapping.sha256',
                 'precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256',
                 'precompiled_sepolicy.product_sepolicy_and_mapping.sha256']:
        target = '/etc/selinux/' + name
        if command('stat ' + target, absent=True) is not None:
            command('rm ' + target, True)
            assert command('stat ' + target, absent=True) is None
            removed.append(target)
    p = subprocess.run([str(W / 'tool-src/e2fs-build/e2fsck/e2fsck'), '-fn', str(out)],
                       capture_output=True, text=True, timeout=120)
    (work / 'e2fsck.txt').write_text(p.stdout + p.stderr)
    assert p.returncode == 0, p.stdout + p.stderr
    result = dict(state='VENDOR_CONTENT_METADATA_FILESYSTEM_VERIFIED', image=str(out), bytes=out.stat().st_size,
                  sha256=sha(out), base_sha256=base_hash, edits=records, removed_stale_precompiled_policy=removed,
                  data_encryption_flags_changed=False, runtime_test_pass=False)
    (W / 'rom-r1/vendor_a.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
