#!/usr/bin/env python3
"""Guard the optional ImsPhone callback without changing non-null behavior."""
import hashlib
import io
import struct
import sys
import zipfile
import zlib
from pathlib import Path

run = Path(__file__).resolve().parent
kind = sys.argv[1] if len(sys.argv) > 1 else "ims"
assert kind in ("ims", "physical-card")
package = "OplusVirtualComm" if kind == "ims" else "VirtualCommService"
source = run.parents[2] / "trees/system_ext/priv-app" / package / f"{package}.apk"
apk = bytearray(source.read_bytes())
with zipfile.ZipFile(io.BytesIO(apk)) as archive:
    entry = archive.getinfo("classes.dex")
    dex = bytearray(archive.read(entry))
    central = archive.start_dir
assert entry.compress_type == zipfile.ZIP_STORED

if kind == "ims":
    # Use the old debug-log instructions for the checked callback.
    log = bytes.fromhex("1a0735247120e5017000")
    call = bytes.fromhex("6e10a1020100")
    assert dex[0x807F4:0x807FE] == log
    assert dex[0x80812:0x80816] == bytes.fromhex("1f01ec00")
    assert dex[0x80816:0x8081C] == call
    dex[0x807F4:0x807FE] = bytes.fromhex("2805") + call + bytes.fromhex("2810")
    dex[0x80816:0x8081C] = bytes.fromhex("3801030028ee")
else:
    # Only the no-modem branch reaches this local physical-card flag.
    assert dex[0xE6E80:0xE6E8C] == bytes.fromhex("7100c63500000a0239022e00")
    assert dex[0xE6F5E:0xE6F62] == bytes.fromhex("d6330001")
    dex[0xE6F5E:0xE6F62] = bytes(4)
dex[12:32] = hashlib.sha1(dex[32:]).digest()
struct.pack_into("<I", dex, 8, zlib.adler32(dex[12:]))
crc = zlib.crc32(dex)

local = entry.header_offset
assert apk[local:local+4] == b"PK\x03\x04"
start = local + 30 + sum(struct.unpack_from("<HH", apk, local + 26))
assert apk[start:start+8] == dex[:8]
apk[start:start+len(dex)] = dex
assert not entry.flag_bits & 8
struct.pack_into("<I", apk, local + 14, crc)
while apk[central:central+4] == b"PK\x01\x02":
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", apk, central + 28)
    if apk[central+46:central+46+name_len] == b"classes.dex":
        struct.pack_into("<I", apk, central + 16, crc)
        break
    central += 46 + name_len + extra_len + comment_len
else:
    raise ValueError("Missing classes.dex central directory entry")

with zipfile.ZipFile(io.BytesIO(apk)) as updated:
    assert updated.testzip() is None
    assert updated.read("classes.dex") == dex
out = run / ("OplusVirtualComm-ims-guard.apk" if kind == "ims" else "VirtualCommService-no-physical-card.apk")
out.write_bytes(apk)
print(hashlib.sha256(apk).hexdigest())
