#!/usr/bin/env python3
"""Integrate the two verified VINTF declarations into fixed EROFS extents."""
import ctypes
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

run = Path(__file__).resolve().parent
prior = run.parent / "0012-c17-cold-boot"
tools = run.parents[2] / "tool-src/erofs-utils-1.8.10"
source = prior / "system-a-cold-boot.img"
target = run / "system-a-vintf30.img"
dump = tools / "dump/dump.erofs"
codec = ctypes.CDLL(str(run.parent / "0010-c17-ringbuf-kernel/liblz4-build.dylib"))
codec.LZ4_decompress_safe_partial.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 3
codec.LZ4_compress_HC.argtypes = codec.LZ4_decompress_safe_partial.argtypes


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as image:
        for block in iter(lambda: image.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_file(path, image):
    return subprocess.check_output([dump, "--cat", f"--path={path}", image])


def decode_lz4(blob, size):
    stream = blob.lstrip(b"\0")
    unpacked = ctypes.create_string_buffer(size)
    result = codec.LZ4_decompress_safe_partial(stream, unpacked, len(stream), size, size)
    assert result == size
    return unpacked.raw


before = sha256(source)
assert before == "49ea8a803630cfea164bf8e2cb4f4a274663998fc390e45cdfe082bd5fd4f68b"
entries = [
    ("/system/etc/vintf/compatibility_matrix.device.xml", "compatibility_matrix.device.xml",
     382_914_560, 8192, True),
    ("/system/etc/vintf/manifest.xml", "framework-manifest.xml",
     382_922_832, 2869, False),
]
checked = []
shutil.copyfile(source, target)
with target.open("r+b") as image:
    for path, filename, offset, capacity, compressed in entries:
        old = read_file(path, source)
        new = (prior / filename).read_bytes()
        assert len(old) == len(new)
        image.seek(offset)
        packed = image.read(capacity)
        if compressed:
            assert decode_lz4(packed, len(old)) == old
            buffer = ctypes.create_string_buffer(capacity)
            size = codec.LZ4_compress_HC(new, buffer, len(new), capacity, 12)
            assert 0 < size <= capacity
            encoded = buffer.raw[:size].rjust(capacity, b"\0")
            assert decode_lz4(encoded, len(new)) == new
        else:
            assert packed == old
            encoded = new
        image.seek(offset)
        image.write(encoded)
        checked.append((path, new))
for path, expected in checked:
    assert read_file(path, target) == expected
assert target.stat().st_size == source.stat().st_size == 954_871_808
record = {
    "system_a_before_sha256": before,
    "system_a_after_sha256": sha256(target),
    "bytes": target.stat().st_size,
    "vintf_files_sha256": {
        path: hashlib.sha256(data).hexdigest() for path, data in checked
    },
}
(run / "candidate.json").write_text(json.dumps(record, indent=2) + "\n")
