#!/usr/bin/env python3
"""Set the C17 panel's default maximum to 144 and keep pen selector 3."""
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

run = Path(__file__).resolve().parent
workspace = run.parents[2]
source = workspace / "rom-r1/my_product_a.img"
target = run / "my-product-a-pen.img"
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
assert base == "63a2790817c706ffdb3474348a6ed9570bb3b0c811783ddbcbecd03dcb7377ef"
original = subprocess.check_output([dump, "--cat", option, source])
assert hashlib.sha256(original).hexdigest() == "d899f286748f1d46dfa2616e16a55540712ff65689efe3f47f8f51ffad640dc0"
old = b'<config ipePencilRateId="3" maxrefreshsettings="3"'
new = b'<config defaultMaxRate="144" ipePencilRateId="3" maxrefreshsettings="4"'
comment = b"maxrefreshsettings " + "默认高刷状态,设置状态会被截断".encode()
short = b"maxrefreshsettings"
extra = len(new) - len(old)
assert original.count(old) == original.count(comment) == 1
assert len(comment) - len(short) >= extra
updated = original.replace(comment, short.ljust(len(comment) - extra)).replace(old, new)
assert len(updated) == len(original)
before_xml, after_xml = map(ET.fromstring, (original, updated))
config = after_xml.find("config")
assert config.attrib.pop("defaultMaxRate") == "144"
assert config.attrib["maxrefreshsettings"] == "4"
config.attrib["maxrefreshsettings"] = "3"
assert ET.tostring(before_xml) == ET.tostring(after_xml)

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
(run / "refresh_rate_config.xml").write_bytes(updated)
(run / "my-product-a-pen.json").write_text(json.dumps({
    "source_sha256": base,
    "output_sha256": sha256(target),
    "bytes": target.stat().st_size,
    "config_sha256": hashlib.sha256(updated).hexdigest(),
}, indent=2) + "\n")
