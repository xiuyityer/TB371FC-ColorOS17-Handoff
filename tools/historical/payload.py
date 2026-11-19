#!/usr/bin/env python3
"""Inspect/extract full Android OTA payload v2; no device writes or dependencies.

Wire field numbers follow the adjacent LineageOS update_metadata.proto.
Source-dependent operations are deliberately rejected.
"""
import argparse
import bz2
from collections import Counter
import hashlib
import json
import lzma
from pathlib import Path
import struct


def varint(data, pos):
    value = shift = 0
    while True:
        b = data[pos]
        pos += 1
        value |= (b & 127) << shift
        if b < 128:
            return value, pos
        shift += 7
        if shift > 63:
            raise ValueError('oversized varint')


def message(data):
    result, pos = {}, 0
    while pos < len(data):
        tag, pos = varint(data, pos)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            value, pos = varint(data, pos)
        elif wire == 2:
            size, pos = varint(data, pos)
            value = data[pos:pos + size]
            if len(value) != size:
                raise ValueError('truncated protobuf')
            pos += size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value = data[pos:pos + size]
            pos += size
        else:
            raise ValueError('unsupported protobuf wire type')
        result.setdefault(field, []).append(value)
    return result


def one(msg, key, default=None):
    return msg.get(key, [default])[0]


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(8 << 20)
            if not chunk:
                return h.hexdigest()
            h.update(chunk)


def inspect(path):
    with path.open('rb') as f:
        magic, version, size, sigsize = struct.unpack('>4sQQI', f.read(24))
        if magic != b'CrAU' or version != 2:
            raise ValueError('requires CrAU v2')
        raw = f.read(size)
        sig = f.read(sigsize)
    manifest = message(raw)
    partitions = []
    for raw_part in manifest.get(13, []):
        p = message(raw_part)
        info = message(one(p, 7, b''))
        ops = [message(o) for o in p.get(8, [])]
        partitions.append((dict(
            name=one(p, 1).decode(), size=one(info, 1),
            sha256=one(info, 2, b'').hex(), has_old_partition=6 in p,
            operations=dict(Counter(str(one(o, 1)) for o in ops)),
            compressed_bytes=sum(one(o, 3, 0) for o in ops),
        ), ops))
    result = dict(payload_bytes=path.stat().st_size, major=version,
                  minor=one(manifest, 12, 0), block_size=one(manifest, 3, 4096),
                  data_offset=24 + size + sigsize,
                  metadata_sha256=hashlib.sha256(struct.pack('>4sQQI', magic, version, size, sigsize) + raw + sig).hexdigest(),
                  partitions=[p for p, _ in partitions])
    return result, partitions


def extract(path, out, names):
    summary, partitions = inspect(path)
    chosen = [(p, ops) for p, ops in partitions if p['name'] in names]
    if set(names) != {p['name'] for p, _ in chosen}:
        raise ValueError('unknown partition requested')
    out.mkdir(parents=True, exist_ok=True)
    for p, ops in chosen:
        if p['has_old_partition'] or any(4 in o or 9 in o for o in ops):
            raise ValueError('source-dependent partition unsupported')
        if any(one(o, 1) not in (0, 1, 6, 8) for o in ops):
            raise ValueError('unsupported or undefined operation in ' + p['name'])
        dest = out / (p['name'] + '.img')
        bs = summary['block_size']
        with path.open('rb') as src, dest.open('xb') as dst:
            dst.truncate(p['size'])
            ranges = []
            for o in ops:
                extents = [message(e) for e in o.get(6, [])]
                total = sum(one(e, 2) * bs for e in extents)
                if one(o, 1) == 6:
                    data = bytes(total)
                else:
                    src.seek(summary['data_offset'] + one(o, 2, 0))
                    blob = src.read(one(o, 3, 0))
                    if 8 in o and hashlib.sha256(blob).digest() != one(o, 8):
                        raise ValueError('operation hash mismatch')
                    data = {0: lambda x: x, 1: bz2.decompress, 8: lzma.decompress}[one(o, 1)](blob)
                if len(data) != total:
                    raise ValueError('extent data length mismatch')
                pos = 0
                for e in extents:
                    start, length = one(e, 1) * bs, one(e, 2) * bs
                    if start + length > p['size']:
                        raise ValueError('extent outside image')
                    ranges.append((start, start + length))
                    dst.seek(start)
                    dst.write(data[pos:pos + length])
                    pos += length
            end = 0
            for start, stop in sorted(ranges):
                if start != end:
                    raise ValueError('overlap or hole in destination extents')
                end = stop
            if end != p['size']:
                raise ValueError('incomplete image coverage')
        actual = digest_file(dest)
        if actual != p['sha256']:
            raise ValueError('partition hash mismatch: ' + p['name'])
        print(json.dumps(dict(name=p['name'], bytes=p['size'], sha256=actual, verified=True)), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('payload', type=Path)
    ap.add_argument('--report', type=Path)
    ap.add_argument('--extract', nargs='+')
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    summary, _ = inspect(args.payload)
    if args.report:
        args.report.write_text(json.dumps(summary, indent=2) + '\n')
    if args.extract:
        if not args.out:
            ap.error('--out is required for extraction')
        extract(args.payload, args.out, args.extract)
    else:
        print(json.dumps(summary, indent=2))
