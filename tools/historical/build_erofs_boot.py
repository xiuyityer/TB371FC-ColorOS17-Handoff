#!/usr/bin/env python3
"""Build a boot-only #789/KSU/EROFS pilot retaining C16 fstab and KB50 DTBs."""
import gzip
import argparse
import hashlib
import json
from pathlib import Path
import struct
from build_boot import unpack, ROOT, BASE, KSU


def cpio_read(data):
    off, rows = 0, []
    while True:
        assert data[off:off + 6] == b'070701'
        fields = [int(data[off + i:off + i + 8], 16) for i in range(6, 110, 8)]
        size, namesize = fields[6], fields[11]
        name = data[off + 110:off + 110 + namesize - 1].decode()
        start = (off + 110 + namesize + 3) // 4 * 4
        if name == 'TRAILER!!!':
            return rows
        rows.append((name, fields, data[start:start + size]))
        off = (start + size + 3) // 4 * 4


def cpio_write(rows):
    data = bytearray()
    rows = rows + [('TRAILER!!!', [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0], b'')]
    for index, (name, fields, content) in enumerate(rows, 1):
        fields = fields.copy()
        fields[0], fields[6], fields[11] = index, len(content), len(name.encode()) + 1
        data.extend(b'070701' + ''.join(f'{v:08x}' for v in fields).encode())
        data.extend(name.encode() + b'\0')
        data.extend(bytes(-len(data) % 4))
        data.extend(content)
        data.extend(bytes(-len(data) % 4))
    data.extend(bytes(-len(data) % 512))
    return bytes(data)


def repack(base_data, kernel, ramdisk, dtb):
    base = unpack(base_data)
    page = base['page']
    header = bytearray(base['header'])
    struct.pack_into('<I', header, 8, len(kernel))
    struct.pack_into('<I', header, 16, len(ramdisk))
    struct.pack_into('<I', header, 1648, len(dtb))
    identity = hashlib.sha1()
    for part in [kernel, ramdisk, b'', b'', dtb]:
        identity.update(part)
        identity.update(struct.pack('<I', len(part)))
    header[576:608] = identity.digest() + bytes(12)
    data = bytearray(header)
    for part in [kernel, ramdisk, dtb]:
        data.extend(part)
        data.extend(bytes(-len(data) % page))
    assert len(data) <= len(base_data)
    data.extend(bytes(len(base_data) - len(data)))
    return bytes(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--module', type=Path, required=True)
    ap.add_argument('--abi-report', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--fstab', type=Path)
    ap.add_argument('--trace-init', type=Path)
    args = ap.parse_args()
    sha = lambda d: hashlib.sha256(d).hexdigest()
    base_data, ksu_data = BASE.read_bytes(), KSU.read_bytes()
    assert sha(base_data) == '9cce59f34b1c67cfbfbd0fbc4b8947788d9520e35580f50ca9bfd4fb6e341a21'
    assert sha(ksu_data) == 'e061f2501742162978081104346bf113424e701c616a781d660fb7878db681e9'
    base, ksu = unpack(base_data), unpack(ksu_data)
    stub = (ROOT / 'c17-port/overlays/early-erofs-init').read_bytes()
    module = args.module.read_bytes()
    abi = json.loads(args.abi_report.read_text())
    assert abi['all_crcs_match'] and sha(module) == abi['module_sha256']
    rows = cpio_read(gzip.decompress(ksu['ramdisk']))
    original_rows = {name: content for name, _, content in rows}
    assert not any('magisk' in name.lower() for name in original_rows)
    result = []
    for name, fields, content in rows:
        if name == 'init':
            result.extend([('ksu_init', fields, content), ('init', fields, stub)])
        elif name == 'fstab.qcom' and args.fstab:
            result.append((name, fields, args.fstab.read_bytes()))
        elif name == 'init.real' and args.trace_init:
            result.extend([('init.android', fields, content), ('init.real', fields, args.trace_init.read_bytes())])
        else:
            result.append((name, fields, content))
    result.append(('erofs.ko', [0, 0o100644, 0, 0, 1, 1793807029, 0, 0, 0, 0, 0, 0, 0], module))
    raw = cpio_write(result)
    ramdisk = gzip.compress(raw, compresslevel=9, mtime=0)
    data = repack(base_data, ksu['kernel'], ramdisk, base['dtb'])
    check = unpack(data)
    readback = {name: content for name, _, content in cpio_read(gzip.decompress(check['ramdisk']))}
    assert check['kernel'] == ksu['kernel'] and check['dtb'] == base['dtb']
    expected_fstab = args.fstab.read_bytes() if args.fstab else original_rows['fstab.qcom']
    assert readback['fstab.qcom'] == expected_fstab
    if args.trace_init:
        assert readback['init.android'] == original_rows['init.real']
        assert readback['init.real'] == args.trace_init.read_bytes()
    else:
        assert readback['init.real'] == original_rows['init.real']
    assert readback['kernelsu.ko'] == original_rows['kernelsu.ko']
    assert readback['ksu_init'] == original_rows['init'] and readback['erofs.ko'] == module
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'boot_a.img').open('xb') as f:
        f.write(data)
    record = dict(state='OFFLINE_BUILT_HARDWARE_PENDING', sha256=sha(data), bytes=len(data),
                  kernel_sha256=sha(ksu['kernel']), dtb_sha256=sha(base['dtb']),
                  module_sha256=sha(module), stub_sha256=sha(stub),
                  filesystem='C17 logical EROFS fstab' if args.fstab else 'Unchanged C16 fstab; EROFS loaded before KSU init',
                  fstab_sha256=sha(expected_fstab),
                  magisk_in_ramdisk=False, device_serial='DEVICE_SERIAL', device_product='spinel',
                  intended_write='boot_a only', rollback=str(BASE),
                  module_abi_note='Module uses exact #789 source/config and CRC table recovered from that binary; runtime validation pending.')
    if args.trace_init:
        record['trace_init_sha256'] = sha(args.trace_init.read_bytes())
        record['trace_init_path'] = str(args.trace_init)
        record['trace_behavior'] = 'Android init wrapped by the supplied diagnostics shim; identify exact behavior by trace_init_path and trace_init_sha256.'
    (out / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
