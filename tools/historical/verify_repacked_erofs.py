#!/usr/bin/env python3
"""Read back every rebuilt inode's metadata and every regular file's bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(8 << 20)
            if not b:
                return h.hexdigest()
            h.update(b)


def main(a):
    original = {r['path']: r for r in map(json.loads, a.metadata.read_text().splitlines())}
    plan = json.loads(a.plan.read_text())
    expected = {p: r.copy() for p, r in original.items()
                if not any(p == x or p.startswith(x.rstrip('/') + '/') for x in plan.get('remove', []))}
    for path, item in plan.get('files', {}).items():
        if path not in expected:
            expected[path] = dict(mode=stat.S_IFREG | int(item['mode'], 8), uid=0, gid=0,
                                  xattrs={'security.selinux': (item['label'] + '\0').encode().hex()})
        r = expected[path]
        if 'mode' in item:
            r['mode'] = stat.S_IFMT(r['mode']) | int(item['mode'], 8)
        for k in ('uid', 'gid'):
            if k in item:
                r[k] = item[k]
        if 'label' in item:
            r['xattrs'] = {**r['xattrs'], 'security.selinux': (item['label'] + '\0').encode().hex()}
    for path, item in plan.get('dirs', {}).items():
        expected[path] = dict(mode=stat.S_IFDIR | int(item.get('mode', '0755'), 8),
                              uid=item.get('uid', 0), gid=item.get('gid', 0),
                              xattrs={'security.selinux': (item['label'] + '\0').encode().hex()})
    command = [str(a.metadata_tool), str(a.image)]
    if not a.extract:
        command.append('--hash')
    result = subprocess.run(command, capture_output=True, check=True, text=True)
    actual = {r['path']: r for r in map(json.loads, result.stdout.splitlines())}
    if expected.keys() != actual.keys():
        raise ValueError(dict(missing=list(expected.keys() - actual.keys()), extra=list(actual.keys() - expected.keys())))
    for p, r in expected.items():
        for key in ('mode', 'uid', 'gid', 'xattrs'):
            if r[key] != actual[p][key]:
                raise ValueError((p, key, r[key], actual[p][key]))
    if a.extract:
        assert not a.extract.exists(), 'Use a fresh readback directory'
        a.extract.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(a.fsck), '--extract=' + str(a.extract), '--no-preserve', str(a.image)], check=True)
    count = total = links = 0
    for path, r in expected.items():
        dest = a.extract / path.lstrip('/') if a.extract else None
        if stat.S_ISREG(r['mode']):
            item = plan.get('files', {}).get(path, {})
            src = Path(item['source']) if 'source' in item else a.tree / path.lstrip('/')
            expected_hash = item.get('sha256') or sha(src)
            actual_hash = sha(dest) if dest else actual[path]['sha256']
            if expected_hash != actual_hash:
                raise ValueError('Content readback mismatch: ' + path)
            count += 1
            total += actual[path]['size']
        elif stat.S_ISLNK(r['mode']):
            expected_target = (a.tree / path.lstrip('/')).readlink().as_posix()
            matches = dest.readlink().as_posix() == expected_target if dest else actual[path]['sha256'] == hashlib.sha256(expected_target.encode()).hexdigest()
            if not matches:
                raise ValueError('Symlink readback mismatch: ' + path)
            links += 1
    report = dict(state='ALL_CONTENT_AND_METADATA_READBACK_PASS', image=str(a.image), sha256=sha(a.image),
                  inodes=len(expected), files=count, file_bytes=total, symlinks=links,
                  permissions_owners_xattrs_verified=True, hardware_test_pass=False)
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ('image', 'metadata', 'plan', 'tree', 'metadata-tool', 'fsck', 'report'):
        ap.add_argument('--' + key, type=Path, required=True)
    ap.add_argument('--extract', type=Path)
    main(ap.parse_args())
