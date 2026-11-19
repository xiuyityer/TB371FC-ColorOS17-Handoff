#!/usr/bin/env python3
"""Make the optional Oplus virtual-radio HIDL lookup nonblocking."""
import hashlib
import io
from pathlib import Path
import struct
import zipfile
import zlib

run = Path(__file__).resolve().parent
source = run.parents[2] / "trees/system_ext/framework/oplus-telephony-common.jar"
jar = bytearray(source.read_bytes())
with zipfile.ZipFile(io.BytesIO(jar)) as record:
    item = record.getinfo("classes.dex")
    dex = bytearray(record.read(item))
    central_start = record.start_dir
assert item.compress_type == zipfile.ZIP_STORED and not item.flag_bits & 8
assert item.header_offset == 0
assert jar[:4] == b"PK\x03\x04" and jar[central_start:central_start + 4] == b"PK\x01\x02"
assert jar[central_start + 46:central_start + 57] == b"classes.dex"
assert dex[0xC65EE:0xC65F6] == bytes.fromhex("121271200a012100")
dex[0xC65EF] = 0x02  # const/4 v2, 0 (retry=false), keep the existing exception path.
dex[12:32] = hashlib.sha1(dex[32:]).digest()
struct.pack_into("<I", dex, 8, zlib.adler32(dex[12:]))
data_start = 30 + sum(struct.unpack_from("<HH", jar, 26))
assert jar[data_start:data_start + 8] == dex[:8]
jar[data_start:data_start + len(dex)] = dex
crc = zlib.crc32(dex)
struct.pack_into("<I", jar, 14, crc)
struct.pack_into("<I", jar, central_start + 16, crc)
with zipfile.ZipFile(io.BytesIO(jar)) as patched:
    assert patched.testzip() is None
    assert patched.read("classes.dex") == dex
output = run / "oplus-telephony-common-nonblocking-radio.jar"
output.write_bytes(jar)
print(hashlib.sha256(jar).hexdigest())
