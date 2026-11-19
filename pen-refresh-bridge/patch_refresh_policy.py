#!/usr/bin/env python3
"""Hash-locked, same-length DEX patch: add the missing 120-Hz bucket.

Only the project's R94RefreshPolicy.floor method changes. OEM methods and
DEX/JAR layout sizes are retained. Requires androguard 4.1.3 for verification.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import struct
import sys
import types
import zipfile
import zlib

# Only raw DEX is parsed; avoid importing unrelated APK certificate tooling.
apk = types.ModuleType('androguard.core.apk')
apk.APK = type('APK', (), {})
sys.modules['androguard.core.apk'] = apk
from loguru import logger
logger.remove()
from androguard.core.dex import DEX

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
SOURCE = WORKSPACE / 'analysis/pen-144hz/oem-binaries/oplus-services.jar'
BASE_SHA = 'a5928b090b68085bd2f32d9ecd39d76d1f4919ffee7072a071ef978232f46136'
INPUTS = WORKSPACE / 'analysis/pen-144hz/home-gesture-bug/guard-inputs'
OUTPUT = ROOT / 'module/system'

def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]

def execute(code, rate, registers, infinite, isnan):
    """Execute the actual old/new small instruction streams for boundary QA."""
    r = [0] * registers
    r[-1] = rate
    pc, result = 0, None
    for _ in range(100):
        op, a = code[pc:pc+2]
        if op == 0: pc += 2
        elif op == 0x71:
            method = struct.unpack_from('<H', code, pc+2)[0]
            arg = r[code[pc+4] & 15]
            assert method in (infinite, isnan)
            result = math.isinf(arg) if method == infinite else math.isnan(arg)
            pc += 6
        elif op == 0x0a: r[a] = result; pc += 2
        elif op == 0x14: r[a] = struct.unpack_from('<f', code, pc+2)[0]; pc += 6
        elif op == 0x15:
            r[a] = struct.unpack('<f', struct.pack('<I', struct.unpack_from('<H', code, pc+2)[0] << 16))[0]
            pc += 4
        elif op in (0x2d, 0x2e):
            x, y = r[code[pc+2]], r[code[pc+3]]
            r[a] = (1 if op == 0x2e else -1) if math.isnan(x) or math.isnan(y) else (x > y) - (x < y)
            pc += 4
        elif op in (0x39, 0x3a, 0x3b):
            take = (r[a] != 0) if op == 0x39 else ((r[a] < 0) if op == 0x3a else r[a] >= 0)
            pc += struct.unpack_from('<h', code, pc+2)[0] * 2 if take else 4
        elif op == 0x28: pc += struct.unpack('<b', bytes([a]))[0] * 2
        elif op == 0xc6: r[a & 15] = f32(r[a & 15] + r[a >> 4]); pc += 2
        elif op == 0x0f: return r[a]
        else: raise AssertionError((pc, op))
    raise AssertionError('Unexpected loop')

def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == BASE_SHA
    with zipfile.ZipFile(SOURCE) as jar:
        original = jar.read('classes2.dex')
        dex = DEX(original)
        method = next(m for c in dex.get_classes() if c.get_name() == 'Lorg/tb371fc/display/R94RefreshPolicy;'
                      for m in c.get_methods() if m.get_name() == 'floor')
        item = method.get_code()
        assert item.get_registers_size() == 2 and item.get_ins_size() == 1 and item.get_tries_size() == 0
        old = item.get_bc().get_raw()
        assert len(old) == 88
        calls = {i.get_output(): struct.unpack_from('<H', i.get_raw(), 2)[0]
                 for i in item.get_bc().get_instructions() if i.get_name() == 'invoke-static'}
        infinite = next(v for k, v in calls.items() if '->isInfinite' in k)
        isnan = next(v for k, v in calls.items() if '->isNaN' in k)
        body, labels, branches = bytearray(), {}, []
        def branch(op, reg, label):
            branches.append((len(body), label)); body.extend(bytes([op, reg]) + b'\0\0')
        body.extend(bytes.fromhex('7110') + struct.pack('<H', infinite) + bytes.fromhex('03000a00'))
        branch(0x39, 0, 'input')
        body.extend(bytes.fromhex('2e000303'))  # cmpg v0, p0, p0: NaN => nonzero
        branch(0x39, 0, 'input')
        body.extend(bytes.fromhex('1402') + struct.pack('<f', .02) + bytes.fromhex('c632'))
        for n, rate in enumerate([144., 120., 60., 30.]):
            body.extend(bytes.fromhex('1500') + struct.pack('<H', struct.unpack('<I', struct.pack('<f', rate))[0] >> 16))
            body.extend(bytes.fromhex('2e010200'))
            branch(0x3a, 1, f'next{n}')
            body.extend(bytes.fromhex('0f00'))
            labels[f'next{n}'] = len(body)
        labels['input'] = len(body)
        body.extend(bytes.fromhex('0f03'))
        for pos, label in branches:
            struct.pack_into('<h', body, pos+2, (labels[label] - pos) // 2)
        body.extend(b'\0' * (len(old)-len(body)))
        assert len(body) == len(old)
        cases = [float('-inf'), -1., 0., 1., 29.97, 29.99, 30., 59.97, 59.99, 60., 90., 119.97,
                 119.99, 120., 120.00001, 130., 143.97, 143.99, 144., 144.00002, 165., float('inf'), float('nan')]
        qa = []
        for rate in cases:
            rate = f32(rate)
            before = execute(old, rate, 2, infinite, isnan)
            after = execute(body, rate, 4, infinite, isnan)
            expected = 120. if math.isfinite(rate) and 119.98 <= rate < 143.98 else before
            assert after == expected or math.isnan(after) and math.isnan(expected), (rate, before, after, expected)
            qa.append({'input': str(rate), 'before': str(before), 'after': str(after)})
        patched = bytearray(original)
        offset = method.get_code_off()
        struct.pack_into('<H', patched, offset, 4)
        struct.pack_into('<I', patched, offset+8, 0)  # discard only this method's stale register debug info
        patched[offset+16:offset+16+len(body)] = body
        patched[12:32] = hashlib.sha1(patched[32:]).digest()
        struct.pack_into('<I', patched, 8, zlib.adler32(patched[12:]) & 0xffffffff)
        assert len(patched) == len(original)
        check = DEX(bytes(patched))
        changed = next(m for c in check.get_classes() if c.get_name() == 'Lorg/tb371fc/display/R94RefreshPolicy;'
                       for m in c.get_methods() if m.get_name() == 'floor')
        listing = [i.get_name()+' '+i.get_output() for i in changed.get_code().get_bc().get_instructions()]
        target = OUTPUT / 'framework/oplus-services.jar'
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, 'w') as out:
            out.comment = jar.comment
            for info in jar.infolist():
                out.writestr(copy.copy(info), bytes(patched) if info.filename == 'classes2.dex' else jar.read(info.filename))
        with zipfile.ZipFile(target) as out:
            assert out.testzip() is None
            for name in jar.namelist():
                if name != 'classes2.dex': assert out.read(name) == jar.read(name)
        new_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    source_apply = INPUTS / 'system_ext/etc/r91-rom/apply.sh'
    old_apply = source_apply.read_bytes()
    assert old_apply.count(BASE_SHA.encode()) == 1
    new_apply = old_apply.replace(BASE_SHA.encode(), new_sha.encode())
    sums = (INPUTS / 'system_ext/etc/r91-rom/SHA256SUMS').read_bytes()
    old_apply_sha = hashlib.sha256(old_apply).hexdigest().encode()
    assert sums.count(old_apply_sha) == 1
    sums = sums.replace(old_apply_sha, hashlib.sha256(new_apply).hexdigest().encode())
    dest = OUTPUT / 'system_ext/etc/r91-rom'; dest.mkdir(parents=True, exist_ok=True)
    (dest/'apply.sh').write_bytes(new_apply); (dest/'SHA256SUMS').write_bytes(sums)
    receipt = {'base_jar_sha256': BASE_SHA, 'patched_jar_sha256': new_sha,
               'method': 'R94RefreshPolicy.floor(F)F', 'code_item_offset': offset,
               'dex_size_unchanged': True, 'code_size_unchanged': True,
               'unchanged_jar_members_preserved': True, 'boundary_cases': qa,
               'disassembly': listing, 'r91_apply_sha256': hashlib.sha256(new_apply).hexdigest()}
    (ROOT/'refresh-policy-patch-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PATCH_VERIFIED', new_sha, 'boundary_cases', len(qa))

if __name__ == '__main__': main()
