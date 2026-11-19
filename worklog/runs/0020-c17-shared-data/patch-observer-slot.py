#!/usr/bin/env python3
"""Select the stock Wi-Fi virtual state path and bound its peer-slot caches."""
import hashlib
import io
from pathlib import Path
import struct
import zipfile
import zlib

run = Path(__file__).resolve().parent
source = run.parent / "0019-c17-virtual-provider/OplusVirtualComm-ims-guard.apk"
apk = bytearray(source.read_bytes())
assert hashlib.sha256(apk).hexdigest() == "69f8c9f7f5fc335036c1cc11852c64d79aa7a405879e038a0b189c2551fe67cf"
with zipfile.ZipFile(io.BytesIO(apk)) as archive:
    entry = archive.getinfo("classes.dex")
    dex = bytearray(archive.read(entry))
    central = archive.start_dir
assert entry.compress_type == zipfile.ZIP_STORED and not entry.flag_bits & 8
# A Wi-Fi tablet uses the stock virtual-only state observer. Keep the tablet check.
assert dex[0x859BC:0x859D4] == bytes.fromhex("3900040012010f0171006c3200000a003800040012110f01")
dex[0x859CC:0x859D0] = bytes(4)
# These arrays are indexed by the virtual peer slot, with vircomm1 and vircomm2 declared.
assert dex[0x8C504:0x8C510] == bytes.fromhex("7100673200000a016701f504")
dex[0x8C50A:0x8C50C] = bytes.fromhex("1221")
for offset, expected in ((0x8CBEA, "37030800"), (0x8D83A, "37050800"), (0x8D99E, "37040800")):
    assert dex[offset:offset+4] == bytes.fromhex(expected)
    dex[offset] = 0x34
dex[12:32] = hashlib.sha1(dex[32:]).digest()
struct.pack_into("<I", dex, 8, zlib.adler32(dex[12:]))
offset = entry.header_offset
start = offset + 30 + sum(struct.unpack_from("<HH", apk, offset + 26))
apk[start:start+len(dex)] = dex
crc = zlib.crc32(dex)
struct.pack_into("<I", apk, offset + 14, crc)
while apk[central:central+4] == b"PK\x01\x02":
    name_size, extra_size, comment_size = struct.unpack_from("<HHH", apk, central + 28)
    if apk[central+46:central+46+name_size] == b"classes.dex":
        struct.pack_into("<I", apk, central + 16, crc)
        break
    central += 46 + name_size + extra_size + comment_size
else:
    raise ValueError("Missing classes.dex central directory entry")
with zipfile.ZipFile(io.BytesIO(apk)) as archive:
    assert archive.testzip() is None and archive.read(entry.filename) == dex
out = run / "OplusVirtualComm-ims-slot-guard.apk"
out.write_bytes(apk)
print(hashlib.sha256(apk).hexdigest())
