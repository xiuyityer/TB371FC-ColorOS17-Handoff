#!/usr/bin/env python3
"""Enable 144 Hz in C17 launcher and system UI high-mode rules."""
import ctypes
import hashlib
from re import escape, subn
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

run = Path(__file__).resolve().parent
workspace = run.parents[2]
source = run.parent / "0015-c17-native-features/my-product-a-native.img"
target = run / "my-product-a-system-ui-144.img"
dump = workspace / "tool-src/erofs-utils-1.8.10/dump/dump.erofs"
codec = ctypes.CDLL(str(run.parent / "0010-c17-ringbuf-kernel/liblz4-build.dylib"))
codec.LZ4_compress_HC.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 3
codec.LZ4_decompress_safe_partial.argtypes = codec.LZ4_compress_HC.argtypes


def sha256(path):
    hasher = hashlib.sha256()
    with path.open("rb") as data:
        for block in iter(lambda: data.read(8 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def decode(packed, size):
    stream = packed.lstrip(b"\0")
    buffer = ctypes.create_string_buffer(size)
    assert codec.LZ4_decompress_safe_partial(stream, buffer, len(stream), size, size) == size
    return buffer.raw


option = "--path=/etc/refresh_rate_config.xml"
base = sha256(source)
assert base == "920db09b2eaca7121e66107db12864e58a438a8d8727bd5c1f27f489cdb167cf"
original = subprocess.check_output([dump, "--cat", option, source])
system_ui = (
    "com.android.launcher", "com.android.settings", "com.oplus.wirelesssettings",
    "com.android.contacts", "com.android.permissioncontroller", "com.android.phone",
    "com.oplus.uxdesign", "com.coloros.assistantscreen", "com.coloros.smartsidebar",
    "com.android.documentsui", "com.coloros.filemanager", "com.android.systemui",
    "com.heytap.quicksearchbox", "com.coloros.gallery3d", "com.android.mms",
    "com.oplus.battery", "com.oplus.notificationmanager", "com.oplus.appdetail",
    "com.coloros.digitalwellbeing", "com.oplus.encryption",
)

updated = original
for package in system_ui:
    prefix = f'<item package="{package}" rateId="'.encode()
    updated, count = subn(rb'(' + escape(prefix) + rb'[0-9]-[0-9]-[0-9])-3"', rb'\g<1>-4"', updated)
    assert count == 1, package

launcher = b'<item package="com.android.launcher" rateId="3-2-2-4" />'
activity = b'<item package="com.android.launcher" activity="com.android.launcher/.Launcher" rateId="3-2-2-4-4" />'
assert updated.count(launcher) == 1
updated = updated.replace(launcher, launcher + b"\r\n  " + activity)
# Use space from the introductory XML comment to keep the EROFS file length.
start = updated.index(b"<!-- format:")
stop = updated.index(b"-->", start) + 3
new_comment = b"<!-- Refresh rates by setting mode. -->"
room = stop - start - (len(updated) - len(original))
assert room >= len(new_comment)
updated = updated[:start] + new_comment.ljust(room) + updated[stop:]
assert len(updated) == len(original)
config = ET.fromstring(updated).find("config")
assert config.attrib["defaultMaxRate"] == "144"
assert config.attrib["maxrefreshsettings"] == "4"
assert config.attrib["ipePencilRateId"] == "3"

offset, capacity = 2_206_187_520, 57344
assert "2206187520..2206244864" in subprocess.check_output([dump, option, "-e", source], text=True)
with source.open("rb") as image:
    image.seek(offset)
    packed = image.read(capacity)
assert decode(packed, len(original)) == original
buffer = ctypes.create_string_buffer(capacity)
size = codec.LZ4_compress_HC(updated, buffer, len(updated), capacity, 12)
assert 0 < size <= capacity
encoded = buffer.raw[:size].rjust(capacity, b"\0")
assert decode(encoded, len(updated)) == updated

assert not target.exists()
subprocess.run(["cp", "-c", source, target], check=True)
with target.open("r+b") as image:
    image.seek(offset)
    image.write(encoded)
assert subprocess.check_output([dump, "--cat", option, target]) == updated
assert target.stat().st_size == source.stat().st_size == 2570592256
(run / "refresh_rate_config.system-ui.xml").write_bytes(updated)
row = ("my_product_a", str(target.stat().st_size), base, sha256(target), str(target))
(run / "system-ui-partitions.tsv").write_text("\t".join(row) + "\n")
