#!/usr/bin/env python3
"""Install one already validated EROFS pcluster without changing image size."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pcluster', type=Path, required=True)
    p.add_argument('--old-payload', type=Path, required=True)
    p.add_argument('--new-payload', type=Path, required=True)
    p.add_argument('--source-sha256', required=True)
    p.add_argument('--old-sha256', required=True)
    p.add_argument('--new-sha256', required=True)
    p.add_argument('--offset', type=int, default=335015936)
    p.add_argument('--pcluster-bytes', type=int, default=40960)
    a = p.parse_args()
    if a.output.exists():
        raise SystemExit(f'refusing to overwrite {a.output}')
    source_size = a.source.stat().st_size
    if sha256(a.source) != a.source_sha256:
        raise SystemExit('source SHA-256 mismatch')
    if sha256(a.old_payload) != a.old_sha256 or sha256(a.new_payload) != a.new_sha256:
        raise SystemExit('payload SHA-256 mismatch')
    old = a.old_payload.read_bytes()
    new = a.new_payload.read_bytes()
    if len(old) != len(new) or len(old) != 73800:
        raise SystemExit('unexpected payload size')
    diffs = [i for i, (x, y) in enumerate(zip(old, new)) if x != y]
    if diffs != list(range(0x68a4, 0x68a8)):
        raise SystemExit(f'unexpected payload differences: {diffs}')
    if old[0x68a4:0x68a8] != bytes.fromhex('41210054') or new[0x68a4:0x68a8] != bytes.fromhex('1f2003d5'):
        raise SystemExit('unexpected instruction bytes')
    cluster = a.pcluster.read_bytes()
    if len(cluster) != a.pcluster_bytes:
        raise SystemExit('unexpected pcluster size')
    if a.offset < 0 or a.offset + len(cluster) > source_size:
        raise SystemExit('pcluster outside source image')
    tmp = a.output.with_name(a.output.name + '.tmp')
    if tmp.exists():
        raise SystemExit(f'refusing to overwrite {tmp}')
    try:
        shutil.copyfile(a.source, tmp)
        with tmp.open('r+b') as f:
            f.seek(a.offset)
            f.write(cluster)
            f.flush()
            os.fsync(f.fileno())
        if tmp.stat().st_size != source_size:
            raise SystemExit('output size changed')
        with a.source.open('rb') as before, tmp.open('rb') as after:
            pos = 0
            while pos < source_size:
                n = min(8 * 1024 * 1024, source_size - pos)
                b = before.read(n)
                c = after.read(n)
                if len(b) != n or len(c) != n:
                    raise SystemExit('short verification read')
                if pos < a.offset or pos + n > a.offset + len(cluster):
                    for i, (x, y) in enumerate(zip(b, c)):
                        absolute = pos + i
                        if x != y and not (a.offset <= absolute < a.offset + len(cluster)):
                            raise SystemExit(f'out-of-range change at {absolute}')
                pos += n
        os.replace(tmp, a.output)
    finally:
        if tmp.exists():
            tmp.unlink()
    print(json.dumps({
        'state': 'BUILT_SAME_SIZE_REQUIRES_FILESYSTEM_AND_HARDWARE_TEST',
        'source_sha256': a.source_sha256,
        'output': str(a.output),
        'output_sha256': sha256(a.output),
        'output_bytes': source_size,
        'pcluster_offset': a.offset,
        'pcluster_bytes': len(cluster),
        'pcluster_sha256': sha256(a.pcluster),
        'payload_sha256': a.new_sha256,
        'payload_patch_offset': 0x68a4,
        'superblock_changed': False,
        'inode_changed': False,
        'hardware_tested': False,
    }, indent=2))


if __name__ == '__main__':
    main()
