#!/usr/bin/env python3
"""Rebuild EROFS using source inode metadata plus an explicit overlay plan.

PAX SCHILY.xattr records preserve binary SELinux/capability attributes
without depending on macOS file ownership or extended attributes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tarfile


def build(args):
    rows = {r['path']: r for r in map(json.loads, args.metadata.read_text().splitlines())}
    plan = json.loads(args.plan.read_text()) if args.plan else {}
    removed = plan.get('remove', [])
    rows = {p: r for p, r in rows.items()
            if not any(p == x or p.startswith(x.rstrip('/') + '/') for x in removed)}
    for path, change in plan.get('files', {}).items():
        if 'sha256' in change:
            actual = hashlib.sha256(Path(change['source']).read_bytes()).hexdigest()
            if actual != change['sha256']:
                raise ValueError('Overlay source changed: ' + path)
        if path not in rows:
            assert 'mode' in change and 'label' in change, path
            rows[path] = dict(path=path, mode=stat.S_IFREG | int(change['mode'], 8),
                              uid=0, gid=0, mtime=1793807029, size=0,
                              xattrs={'security.selinux': (change['label'] + '\0').encode().hex()})
        rows[path] = {**rows[path], **{k: change[k] for k in ('uid', 'gid', 'mtime') if k in change}}
        if 'mode' in change:
            rows[path]['mode'] = stat.S_IFMT(rows[path]['mode']) | int(change['mode'], 8)
        if 'label' in change:
            rows[path]['xattrs'] = {**rows[path]['xattrs'], 'security.selinux': (change['label'] + '\0').encode().hex()}
    for path, change in plan.get('dirs', {}).items():
        assert path not in rows, path
        rows[path] = dict(path=path, mode=stat.S_IFDIR | int(change.get('mode', '0755'), 8),
                         uid=change.get('uid', 0), gid=change.get('gid', 0), size=0,
                         mtime=1793807029, xattrs={'security.selinux': (change['label'] + '\0').encode().hex()})
    assert not args.output.exists(), 'Do not overwrite attributed candidates'
    command = [str(args.mkfs), '--tar=f', '-zlz4hc,9', '-C65536',
               '-E^xattr-name-filter', '-T1793807029', str(args.output)]
    with args.log.open('wb') as log:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log)
        try:
            with tarfile.open(fileobj=proc.stdin, mode='w|', format=tarfile.PAX_FORMAT) as tar:
                for path, r in sorted(rows.items(), key=lambda x: (x[0].count('/'), x[0])):
                    info = tarfile.TarInfo(path.lstrip('/') or '.')
                    info.uid, info.gid, info.mode, info.mtime = r['uid'], r['gid'], stat.S_IMODE(r['mode']), r['mtime']
                    info.pax_headers = {'SCHILY.xattr.' + k: bytes.fromhex(v).decode('utf-8', 'surrogateescape')
                                        for k, v in r['xattrs'].items()}
                    change = plan.get('files', {}).get(path, {})
                    source = Path(change['source']) if 'source' in change else args.tree / path.lstrip('/')
                    if stat.S_ISDIR(r['mode']):
                        info.type = tarfile.DIRTYPE
                        tar.addfile(info)
                    elif stat.S_ISLNK(r['mode']):
                        info.type = tarfile.SYMTYPE
                        info.linkname = source.readlink().as_posix()
                        tar.addfile(info)
                    elif stat.S_ISREG(r['mode']):
                        assert source.is_file() and not source.is_symlink(), source
                        info.size = source.stat().st_size
                        if 'source' not in change:
                            assert info.size == r['size'], source
                        with source.open('rb') as stream:
                            tar.addfile(info, stream)
                    else:
                        raise ValueError('Unhandled inode: ' + path)
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError('mkfs failed; see ' + str(args.log))
        except BaseException:
            proc.terminate()
            proc.wait()
            raise
    h = hashlib.sha256()
    with args.output.open('rb') as stream:
        while True:
            buf = stream.read(8 << 20)
            if not buf:
                break
            h.update(buf)
    record = dict(output=str(args.output), sha256=h.hexdigest(), bytes=args.output.stat().st_size,
                  inode_count=len(rows), metadata=str(args.metadata), plan=str(args.plan),
                  state='BUILT_REQUIRES_METADATA_READBACK_AND_HARDWARE_TEST', command=command)
    args.output.with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['tree', 'metadata', 'output', 'mkfs', 'log']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--plan', type=Path)
    build(ap.parse_args())
