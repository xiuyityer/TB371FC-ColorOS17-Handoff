#!/usr/bin/env python3
"""Compare an arm64 LKM's __versions against boot v2's exported CRC tables.

The symbol input is kallsyms-finder output from the exact same boot image.
This is an offline rejection gate, not proof of runtime compatibility.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def sections(data):
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('requires ELF64 little endian')
    shoff = struct.unpack_from('<Q', data, 40)[0]
    size, count, strings_index = struct.unpack_from('<HHH', data, 58)
    rows = [struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * size)
            for i in range(count)]
    row = rows[strings_index]
    names = data[row[4]:row[4] + row[5]]
    return {names[r[0]:].split(b'\0')[0].decode(): data[r[4]:r[4] + r[5]]
            for r in rows}


def kernel_exports(boot, symbols):
    data = boot.read_bytes()
    if data[:8] != b'ANDROID!' or struct.unpack_from('<I', data, 40)[0] != 2:
        raise ValueError('requires boot v2')
    page = struct.unpack_from('<I', data, 36)[0]
    sym = {s[2]: int(s[0], 16) for line in symbols.read_text().splitlines()
           if len(s := line.split()) == 3}
    base = sym['_text']
    crcs, categories = {}, {}
    for group in ['', '_gpl', '_gpl_future', '_unused', '_unused_gpl']:
        start = sym['__start___ksymtab' + group]
        stop = sym['__stop___ksymtab' + group]
        crcstart = sym['__start___kcrctab' + group]
        crcstop = sym['__stop___kcrctab' + group]
        if (stop - start) // 8 != (crcstop - crcstart) // 4:
            raise ValueError('unexpected kernel_symbol/CRC table sizes')
        for i, addr in enumerate(range(start, stop, 8)):
            off = page + addr - base
            nameoff = off + 4 + struct.unpack_from('<i', data, off + 4)[0]
            if not 0 <= nameoff < len(data):
                raise ValueError('symbol address is outside boot image')
            name = data[nameoff:data.index(b'\0', nameoff)].decode()
            if '__ksymtab_' + name not in sym:
                raise ValueError('export name failed cross-check: ' + name)
            crcs[name] = struct.unpack_from('<I', data, page + crcstart - base + i * 4)[0]
            categories[name] = 'EXPORT_SYMBOL_GPL' if 'gpl' in group else 'EXPORT_SYMBOL'
    return crcs, categories


def compare(boot, symbols, module):
    data, ko = boot.read_bytes(), module.read_bytes()
    crcs, _ = kernel_exports(boot, symbols)
    sec = sections(ko)
    rows = []
    for i in range(0, len(sec['__versions']), 64):
        crc = struct.unpack_from('<Q', sec['__versions'], i)[0]
        name = sec['__versions'][i + 8:i + 64].split(b'\0')[0].decode()
        actual = crcs.get(name)
        rows.append(dict(symbol=name, module_crc=hex(crc),
                         kernel_crc=None if actual is None else hex(actual),
                         matches=crc == actual))
    return dict(boot=str(boot), boot_sha256=hashlib.sha256(data).hexdigest(),
                module=str(module), module_sha256=hashlib.sha256(ko).hexdigest(),
                vermagic=[v.decode() for v in sec['.modinfo'].split(b'\0') if v.startswith(b'vermagic=')],
                exports=len(crcs), required=len(rows), matching=sum(r['matches'] for r in rows),
                mismatches=[r for r in rows if not r['matches']],
                all_crcs_match=all(r['matches'] for r in rows),
                note='CRC agreement alone does not prove semantic or hardware compatibility.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('boot', type=Path)
    ap.add_argument('symbols', type=Path)
    ap.add_argument('module', type=Path)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    result = compare(args.boot, args.symbols, args.module)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'mismatches'}, indent=2))
