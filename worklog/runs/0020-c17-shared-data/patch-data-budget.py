#!/usr/bin/env python3
"""Keep one data attach slot when the QTI OEM query fails on the Wi-Fi port."""
import hashlib
import io
from pathlib import Path
import struct
import zipfile
import zlib

run = Path(__file__).resolve().parent
source = run.parents[2] / "trees/system_ext/framework/oplus-telephony-common-ext.jar"
jar = bytearray(source.read_bytes())
assert hashlib.sha256(jar).hexdigest() == "8c675d769e756483b5f7b4771f7b3a9ab9736955f994767c9059209b42cbb90d"
with zipfile.ZipFile(io.BytesIO(jar)) as archive:
    entry = archive.getinfo("classes.dex")
    dex = bytearray(archive.read(entry))
    central = archive.start_dir
assert entry.header_offset == 0 and entry.compress_type == zipfile.ZIP_STORED
assert not entry.flag_bits & 8 and jar[central+46:central+57] == b"classes.dex"
assert dex[0x187BC:0x187C2] == bytes.fromhex("0a0128021201")
dex[0x187C1] = 0x11  # const/4 v1, 1 on the exception/null-result branch
dex[12:32] = hashlib.sha1(dex[32:]).digest()
struct.pack_into("<I", dex, 8, zlib.adler32(dex[12:]))
start = 30 + sum(struct.unpack_from("<HH", jar, 26))
jar[start:start+len(dex)] = dex
crc = zlib.crc32(dex)
struct.pack_into("<I", jar, 14, crc)
struct.pack_into("<I", jar, central + 16, crc)
with zipfile.ZipFile(io.BytesIO(jar)) as archive:
    assert archive.testzip() is None and archive.read(entry.filename) == dex
out = run / "oplus-telephony-common-ext-data-budget.jar"
out.write_bytes(jar)
print(hashlib.sha256(jar).hexdigest())
