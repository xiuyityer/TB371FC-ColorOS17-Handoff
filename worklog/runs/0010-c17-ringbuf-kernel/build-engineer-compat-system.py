"""Repackage the three EROFS extents touched by the engineer service lookup."""
from pathlib import Path
import ctypes
import hashlib
import json
import re
import shutil

run = Path(__file__).resolve().parent
workspace = run.parents[2]
old_jar = workspace / "trees/system/system/framework/oplus-services.jar"
new_jar = run / "oplus-services-engineer-check.jar"
source = run.parent / "0008-c17-netd-stats-compat/system_a.img"
target = run / "system-a-engineer-compat.img"
target_tmp = target.with_suffix(".img.partial")
manifest = json.loads((run / "engineer-jar-patch.json").read_text())

def digest(data):
    return hashlib.sha256(data).hexdigest()

def image_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

old, new = old_jar.read_bytes(), new_jar.read_bytes()
assert len(old) == len(new)
assert digest(old) == manifest["source_sha256"]
assert digest(new) == manifest["output_sha256"]
assert source.stat().st_size == 954871808
assert image_hash(source) == "4ce0ce2914fef9bc72cfa195bc4d3f426d608433494e14401d0d4a606c649cec"

lib = ctypes.CDLL(str(run / "liblz4-build.dylib"))
codec_args = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 3
lib.LZ4_decompress_safe_partial.argtypes = codec_args
lib.LZ4_compress_HC.argtypes = codec_args

def decode(blob, length):
    stream = blob.lstrip(b"\x00")
    out = ctypes.create_string_buffer(length)
    result = lib.LZ4_decompress_safe_partial(stream, out, len(stream), length, length)
    if result != length:
        raise ValueError(f"Decoder returned {result} for {length} bytes")
    return out.raw

changed = {i for i, (a, b) in enumerate(zip(old, new)) if a != b}
covered = set()
records = []
extent = re.compile(r"^\s*\d+:\s*(\d+)\.\.\s*(\d+)\s*\|[^:]+:\s*(\d+)\.\.\s*(\d+)")
with source.open("rb") as file:
    for line in (run / "engineer-jar-erofs-extents.txt").read_text().splitlines():
        m = extent.match(line)
        if not m:
            continue
        start, end, base, stop = map(int, m.groups())
        touch = {i for i in changed if start <= i < end}
        if not touch:
            continue
        assert not (touch & covered)
        covered |= touch
        size = stop - base
        assert size > 0 and base % 4096 == size % 4096 == 0
        file.seek(base)
        original = file.read(size)
        assert len(original) == size
        if original == old[start:end]:
            encoded = new[start:end]
            layout = "raw"
        else:
            assert decode(original, end - start) == old[start:end]
            out = ctypes.create_string_buffer(size)
            length = lib.LZ4_compress_HC(new[start:end], out, end - start, size, 12)
            if length <= 0:
                raise ValueError(f"Replacement does not fit extent {base} ({size} bytes)")
            encoded = out.raw[:length].rjust(size, b"\x00")
            assert decode(encoded, end - start) == new[start:end]
            layout = "lz4"
        assert len(encoded) == size
        row = dict(layout=layout, logical=start, physical=base, bytes=size,
                   old_sha256=digest(original), new_sha256=digest(encoded))
        records.append((row, encoded))
assert covered == changed and len(records) == 3
assert not target.exists() and not target_tmp.exists()
with source.open("rb") as src, target_tmp.open("xb") as dst:
    shutil.copyfileobj(src, dst, 8 << 20)
with target_tmp.open("r+b") as dst:
    for row, encoded in records:
        dst.seek(row["physical"])
        assert digest(dst.read(row["bytes"])) == row["old_sha256"]
        dst.seek(row["physical"])
        dst.write(encoded)
assert target_tmp.stat().st_size == source.stat().st_size
target_tmp.rename(target)
record = dict(output_sha256=image_hash(target), output_bytes=target.stat().st_size,
              extents=[row for row, _ in records])
(run / "engineer-system-image.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
