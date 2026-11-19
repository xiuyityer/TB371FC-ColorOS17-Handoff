#!/usr/bin/env python3
"""Build raw super using the device's geometry and verified image provenance.

Format: AOSP system/core fs_mgr/liblp/include/liblp/metadata_format.h.
No device writes. B partitions remain empty, as in the original layout.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

W = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(8 << 20):
            h.update(chunk)
    return h.hexdigest()


def validate_header(h, tables):
    assert struct.unpack_from('<I', h)[0] == 0x414c5030
    check = bytearray(h)
    check[12:44] = bytes(32)
    assert hashlib.sha256(check).digest() == h[12:44]
    assert hashlib.sha256(tables).digest() == h[48:80]


def main():
    out = W / 'rom-r1/super.raw.img'
    assert not out.exists(), 'Refusing to overwrite a candidate'
    original = (W / 'base-c16/super-metadata-readback.bin').read_bytes()
    assert hashlib.sha256(original).hexdigest() == '538b1f455aa3ed096496efefe0442c8ce7440f99a2ba646b2b74467cce985ee6'
    geo = bytearray(original[4096:4148])
    checksum = geo[8:40]
    geo[8:40] = bytes(32)
    assert hashlib.sha256(geo).digest() == checksum
    maximum, slots, blocksize = struct.unpack_from('<III', geo, 40)
    assert (maximum, slots, blocksize) == (65536, 3, 4096)
    header = bytearray(original[12288:12544])
    oldtables = original[12544:12544 + struct.unpack_from('<I', header, 44)[0]]
    validate_header(header, oldtables)
    def oldtable(i):
        off, count, size = struct.unpack_from('<III', header, 80 + 12*i)
        return oldtables[off:off+count*size], count, size
    groups, ng, gs = oldtable(2)
    devices, nd, ds = oldtable(3)
    assert (ng, gs, nd, ds) == (3, 48, 1, 64)
    first, alignment, alignment_offset, device_size, name, flags = struct.unpack('<QIIQ36sI', devices)
    assert device_size == 12884901888 and first == 2048 and name.rstrip(b'\0') == b'super'
    donor = {p['name']: p for p in json.loads((W/'evidence/payload-manifest.json').read_text())['partitions']}
    inputs = []
    for part in ('system', 'system_ext', 'product', 'vendor', 'odm', 'my_manifest', 'my_product',
                 'my_stock', 'my_engineering', 'my_heytap', 'my_carrier', 'my_region', 'my_bigball'):
        if part in ('system', 'system_ext', 'my_manifest', 'my_product'):
            reportname = 'rom-r1-system_ext-current-readback.json' if part == 'system_ext' else f'rom-r1-{part}-readback.json'
            proof = json.loads((W/'evidence'/reportname).read_text())
            assert proof['state'] == 'ALL_CONTENT_AND_METADATA_READBACK_PASS'
            path = W/'rom-r1'/f'{part}_a.img'
            expected = proof['sha256']
        elif part == 'vendor':
            proof = json.loads((W/'rom-r1/vendor_a.json').read_text())
            assert proof['state'] == 'VENDOR_CONTENT_METADATA_FILESYSTEM_VERIFIED'
            path, expected = W/'rom-r1/vendor_a.img', proof['sha256']
        elif part == 'odm':
            path = W/'base-c16/odm_a.img'
            expected = 'eec06da5d0fbab6808028cc7341a495ed810de30b7f931db988ca664a9525a17'
        else:
            path, expected = W/'donor'/f'{part}.img', donor[part]['sha256']
            assert path.stat().st_size == donor[part]['size']
        assert sha(path) == expected, part
        assert path.stat().st_size % blocksize == 0
        inputs.append(dict(name=part+'_a', image=str(path), sha256=expected, bytes=path.stat().st_size))
    partitions = bytearray()
    extents = bytearray()
    cursor = first * 512
    used = 0
    for n, item in enumerate(inputs):
        # Conservative 1 MiB alignment, matching the existing device layout.
        cursor = (cursor + (1 << 20)-1) // (1 << 20) * (1 << 20)
        item['offset'] = cursor
        for suffix in ('a', 'b'):
            pname = item['name'][:-1] + suffix
            partitions += struct.pack('<36sIIII', pname.encode(), 0, n if suffix == 'a' else n+1,
                                      1 if suffix == 'a' else 0, 1 if suffix == 'a' else 2)
        extents += struct.pack('<QIQI', item['bytes']//512, 0, cursor//512, 0)
        cursor += item['bytes']
        used += item['bytes']
    assert cursor <= device_size and used <= struct.unpack_from('<Q', groups, 48+40)[0]
    tables = bytearray()
    for i, (data, count, size) in enumerate(((partitions, 26, 52), (extents, 13, 24),
                                            (groups, ng, gs), (devices, nd, ds))):
        struct.pack_into('<III', header, 80+12*i, len(tables), count, size)
        tables += data
    struct.pack_into('<I', header, 44, len(tables))
    header[48:80] = hashlib.sha256(tables).digest()
    header[12:44] = bytes(32)
    header[12:44] = hashlib.sha256(header).digest()
    validate_header(header, tables)
    metadata = header + tables
    assert len(metadata) <= maximum
    prefix = bytearray(first*512)
    prefix[4096:8192] = original[4096:8192]
    prefix[8192:12288] = original[8192:12288]
    for slot in range(slots*2):
        start = 12288 + slot*maximum
        prefix[start:start+len(metadata)] = metadata
    spec = importlib.util.spec_from_file_location('probe', W.parent/'sources/rom/rom-build/tools/lp_probe.py')
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    parsed = probe.parse_metadata(prefix, probe.parse_geometry(prefix))
    assert len(parsed['partitions']) == 26
    for item, parsedpart in zip(inputs, parsed['partitions'][::2]):
        assert item['name'] == parsedpart['name'] and item['bytes'] == parsedpart['size_bytes']
        assert item['offset'] == parsedpart['extents'][0]['target_data']*512
    with out.open('xb') as f:
        f.truncate(device_size)
        f.write(prefix)
        for item in inputs:
            f.seek(item['offset'])
            digest = hashlib.sha256()
            with Path(item['image']).open('rb') as src:
                while chunk := src.read(8 << 20):
                    f.write(chunk)
                    digest.update(chunk)
            assert digest.hexdigest() == item['sha256']
    # Verify the bytes of every embedded partition, independently of the copy loop.
    with out.open('rb') as f:
        assert f.read(len(prefix)) == prefix
        for item in inputs:
            f.seek(item['offset'])
            remaining = item['bytes']
            digest = hashlib.sha256()
            while remaining:
                chunk = f.read(min(8 << 20, remaining))
                assert chunk
                digest.update(chunk)
                remaining -= len(chunk)
            assert digest.hexdigest() == item['sha256']
    report = dict(state='SUPER_ALL_EMBEDDED_IMAGES_READBACK_VERIFIED_HARDWARE_PENDING',
                  image=str(out), bytes=device_size, sha256=sha(out), inputs=inputs,
                  geometry_slots=slots, metadata_copies=slots*2, b_partitions_empty=True,
                  original_device_alignment=alignment, original_alignment_offset=alignment_offset,
                  layout=parsed, partition_writes=False)
    (W/'rom-r1/super.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('inputs','layout')}, indent=2))


if __name__ == '__main__':
    main()
