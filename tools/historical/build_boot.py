#!/usr/bin/env python3
"""Preserve KB50 boot v2 header/DTBs; use the matched #789 kernel+KSU ramdisk."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'ColorOS16_TB371FC_v27_r108_KB50_20261112_R5_CANDIDATE/images/boot_a.img'
KSU = ROOT / 'c17-port/donor/boot-tb371fc-v2.2-ksu.img'
OUT = ROOT / 'c17-port/candidate-r1'


def unpack(data):
    u32 = lambda off: struct.unpack_from('<I', data, off)[0]
    assert data[:8] == b'ANDROID!' and u32(40) == 2
    page = u32(36)
    align = lambda n: (n + page - 1) // page * page
    kernel_size, ramdisk_size, second_size = u32(8), u32(16), u32(24)
    recovery_size, dtb_size = u32(1632), u32(1648)
    assert second_size == recovery_size == 0
    ramdisk_offset = align(page + kernel_size)
    dtb_offset = align(ramdisk_offset + ramdisk_size)
    assert dtb_offset + dtb_size <= len(data)
    return dict(page=page, header=data[:page], kernel=data[page:page + kernel_size],
                ramdisk=data[ramdisk_offset:ramdisk_offset + ramdisk_size],
                dtb=data[dtb_offset:dtb_offset + dtb_size])


def main():
    base_data, ksu_data = BASE.read_bytes(), KSU.read_bytes()
    sha = lambda d: hashlib.sha256(d).hexdigest()
    assert sha(base_data) == '9cce59f34b1c67cfbfbd0fbc4b8947788d9520e35580f50ca9bfd4fb6e341a21'
    assert sha(ksu_data) == 'e061f2501742162978081104346bf113424e701c616a781d660fb7878db681e9'
    base, ksu = unpack(base_data), unpack(ksu_data)
    assert base['page'] == ksu['page'] == 4096
    page = base['page']
    align = lambda n: (n + page - 1) // page * page
    header = bytearray(base['header'])
    struct.pack_into('<I', header, 8, len(ksu['kernel']))
    struct.pack_into('<I', header, 16, len(ksu['ramdisk']))
    identity = hashlib.sha1()
    for part in [ksu['kernel'], ksu['ramdisk'], b'', b'', base['dtb']]:
        identity.update(part)
        identity.update(struct.pack('<I', len(part)))
    header[576:608] = identity.digest() + bytes(12)
    data = bytearray(header)
    for part in [ksu['kernel'], ksu['ramdisk'], base['dtb']]:
        data.extend(part)
        data.extend(bytes(align(len(data)) - len(data)))
    assert len(data) <= len(base_data)
    data.extend(bytes(len(base_data) - len(data)))
    check = unpack(data)
    assert check['kernel'] == ksu['kernel']
    assert check['ramdisk'] == ksu['ramdisk']
    assert check['dtb'] == base['dtb']
    OUT.mkdir(exist_ok=True)
    path = OUT / 'boot_a.img'
    with path.open('xb') as f:
        f.write(data)
    record = dict(state='OFFLINE_BUILT_DEVICE_UNTESTED', image=str(path), bytes=len(data),
                  sha256=sha(data), base_boot_sha256=sha(base_data), ksu_boot_sha256=sha(ksu_data),
                  kernel_sha256=sha(check['kernel']), ramdisk_sha256=sha(check['ramdisk']),
                  dtb_sha256=sha(check['dtb']), dtb_origin='Exact KB50 R5 DTBs retained',
                  magisk_ramdisk=False, kernel_build=789,
                  device_serial='DEVICE_SERIAL', device_product='spinel', slot='a',
                  rollback_image=str(BASE), temporary_boot_previous_response="FAILED (remote: 'unknown command')",
                  note='Candidate requires matching C17 system/vendor setup; no runtime compatibility claim.')
    (OUT / 'boot-manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
