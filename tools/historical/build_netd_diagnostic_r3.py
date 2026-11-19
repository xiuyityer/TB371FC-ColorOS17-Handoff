#!/usr/bin/env python3
"""Build the C17 r3 netd diagnostic without modifying the signed tethering APEX."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct

ROOT = Path('$WORKSPACE/c17-port')
SOURCE = ROOT / 'rom-r2/system_a.img'
OUTPUT = ROOT / 'rom-r3/system_a.img'
RC_SOURCE = ROOT / 'trees/system/system/etc/init/netd.rc'
RC_OUTPUT = ROOT / 'overlays/netd.rc-r3-ldpreload'
LIB_SOURCE = ROOT / 'evidence/tethering-apex/libnetd_updatable.so'
LIB_OUTPUT = ROOT / 'overlays/libnetd_updatable-r3.so'
EXPECTED_SOURCE = 'a69028ee0f2b0945a8ff4f945109c3e4ef62136616e27aad2b247d35edf8dc7f'
EXPECTED_LIB = '44cdbb8292982421fda05b93904fd5ebcb3bb1e00ddc288471b2f7584fbd3b65'
RC_OFFSET = 381116464
RC_SIZE = 2436
LIB_PATCH_OFFSET = 0x62f4
ENV = b'    setenv LD_PRELOAD /data/local/tmp/n.so\n'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def make_rc(original):
    modified = original.replace(
        b'service netd1shot /system/bin/netd oneshot\n',
        b'service netd1shot /system/bin/netd oneshot\n' + ENV, 1)
    modified = modified.replace(
        b'service netd /system/bin/netd\n',
        b'service netd /system/bin/netd\n' + ENV, 1)
    if modified.count(ENV) != 2:
        raise SystemExit('failed to insert both LD_PRELOAD settings')
    start = original.index(b'# Moved from external/android-clat/vendor-464xlat.rc.')
    end = original.index(b'on property:persist.vendor.net.doxlat=true')
    # Recompute the same boundaries after insertion, then replace only the
    # explanatory comment block; the functional 464xlat triggers are retained.
    new_start = modified.index(b'# Moved from external/android-clat/vendor-464xlat.rc.')
    new_end = modified.index(b'on property:persist.vendor.net.doxlat=true')
    padding_len = len(original) - (len(modified) - (new_end - new_start))
    if padding_len < 100:
        raise SystemExit('insufficient comment space for same-size diagnostic')
    first = b'# C17 netd diagnostic; comment padding preserves the original inline file size.\n'
    padding = first + b'#' * (padding_len - len(first) - 1) + b'\n'
    result = modified[:new_start] + padding + modified[new_end:]
    assert len(result) == len(original) == RC_SIZE
    assert result.count(ENV) == 2
    assert b'on property:persist.vendor.net.doxlat=true' in result
    assert b'on property:persist.vendor.net.doxlat=false' in result
    return result


def main():
    for p in (OUTPUT, RC_OUTPUT, LIB_OUTPUT):
        if p.exists():
            raise SystemExit(f'refusing to overwrite {p}')
    if sha256(SOURCE) != EXPECTED_SOURCE or sha256(LIB_SOURCE) != EXPECTED_LIB:
        raise SystemExit('input SHA-256 mismatch')
    rc_original = RC_SOURCE.read_bytes()
    if len(rc_original) != RC_SIZE:
        raise SystemExit('unexpected netd.rc size')
    with SOURCE.open('rb') as f:
        f.seek(RC_OFFSET)
        if f.read(RC_SIZE) != rc_original:
            raise SystemExit('netd.rc source image bytes differ from source tree')
    rc_new = make_rc(rc_original)
    RC_OUTPUT.write_bytes(rc_new)

    lib = bytearray(LIB_SOURCE.read_bytes())
    branch = 0x14000000 | (((0x6690 - LIB_PATCH_OFFSET) // 4) & 0x03ffffff)
    if struct.unpack_from('<I', lib, LIB_PATCH_OFFSET)[0] != 0x54001ce8:
        raise SystemExit('unexpected original b.hi instruction')
    if branch != 0x140000e7:
        raise SystemExit('unexpected replacement branch encoding')
    struct.pack_into('<I', lib, LIB_PATCH_OFFSET, branch)
    LIB_OUTPUT.write_bytes(lib)

    tmp = OUTPUT.with_name(OUTPUT.name + '.tmp')
    if tmp.exists():
        raise SystemExit(f'refusing to overwrite {tmp}')
    try:
        shutil.copyfile(SOURCE, tmp)
        with tmp.open('r+b') as f:
            f.seek(RC_OFFSET)
            f.write(rc_new)
            f.flush()
            os.fsync(f.fileno())
        if tmp.stat().st_size != SOURCE.stat().st_size:
            raise SystemExit('image size changed')
        with SOURCE.open('rb') as before, tmp.open('rb') as after:
            pos = 0
            while pos < SOURCE.stat().st_size:
                n = min(8 * 1024 * 1024, SOURCE.stat().st_size - pos)
                b, c = before.read(n), after.read(n)
                for i, (x, y) in enumerate(zip(b, c)):
                    absolute = pos + i
                    if x != y and not (RC_OFFSET <= absolute < RC_OFFSET + RC_SIZE):
                        raise SystemExit(f'out-of-range image change at {absolute}')
                pos += n
        os.replace(tmp, OUTPUT)
    finally:
        if tmp.exists():
            tmp.unlink()
    report = {
        'state': 'R3_DIAGNOSTIC_BUILT_REQUIRES_FILESYSTEM_AND_HARDWARE_TEST',
        'system_sha256': sha256(OUTPUT),
        'system_bytes': OUTPUT.stat().st_size,
        'netd_rc_sha256': sha256(RC_OUTPUT),
        'netd_rc_offset': RC_OFFSET,
        'netd_rc_bytes': RC_SIZE,
        'library_sha256': sha256(LIB_OUTPUT),
        'library_bytes': LIB_OUTPUT.stat().st_size,
        'library_patch_offset': LIB_PATCH_OFFSET,
        'library_old_instruction': '0x54001ce8',
        'library_new_instruction': '0x140000e7',
        'apex_modified': False,
        'diagnostic_only_not_final_fix': True,
        'hardware_tested': False,
    }
    (ROOT / 'rom-r3/system_a.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
