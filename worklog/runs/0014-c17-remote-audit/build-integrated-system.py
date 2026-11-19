#!/usr/bin/env python3
"""Redirect verified run 0013 boot inputs to the companion system_ext image."""
import ctypes
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess

run = Path(__file__).resolve().parent
workspace = run.parents[2]
source = run.parent / "0013-c17-vintf30/system-a-vintf30.img"
target = run / "system-a-integrated.img"
dump = workspace / "tool-src/erofs-utils-1.8.10/dump/dump.erofs"
codec = ctypes.CDLL(str(run.parent / "0010-c17-ringbuf-kernel/liblz4-build.dylib"))
codec.LZ4_compress_HC.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 3
codec.LZ4_decompress_safe_partial.argtypes = codec.LZ4_compress_HC.argtypes


def digest(path):
    hash_ = sha256()
    with path.open("rb") as image:
        for block in iter(lambda: image.read(8 << 20), b""):
            hash_.update(block)
    return hash_.hexdigest()


def extract(path, image):
    return subprocess.check_output([dump, "--cat", f"--path={path}", image])


def encode(original, current, replacement):
    stream = original.lstrip(b"\0")
    decoded = ctypes.create_string_buffer(len(current))
    count = codec.LZ4_decompress_safe_partial(stream, decoded, len(stream), len(current), len(current))
    assert count == len(current) and decoded.raw == current
    packed = ctypes.create_string_buffer(len(original))
    count = codec.LZ4_compress_HC(replacement, packed, len(current), len(original), 12)
    assert count > 0, "Replacement pcluster exceeds its original capacity"
    return packed.raw[:count].rjust(len(original), b"\0")


base_hash = digest(source)
assert base_hash == "97afde2cc1c6c46755dddab55294d63e3a14b848a4787f39dd1306fbd77f3b54"
bpf = "/system/bin/c17-netbpfload"
bpf_rc = "/system/etc/init/netbpfload.rc"
netd_rc = "/system/etc/init/netd.rc"
original = {path: extract(path, source) for path in (bpf, bpf_rc, netd_rc)}

legacy = b"/data/local/tmp/c17-bpf/netd.o\0"
relocated = b"/system_ext/etc/c17/netd.o\0"
assert original[bpf].count(legacy) == 1
new_bpf = original[bpf].replace(legacy, relocated.ljust(len(legacy), b"\0"), 1)

old_mount = b"/data/adb/c17-port/service-wifi.jar"
qspm_mount = b"    mount none /data/adb/c17-port/libupdateprof.qti.so /system_ext/lib64/libupdateprof.qti.so bind\n"
assert original[bpf_rc].count(old_mount) == original[bpf_rc].count(qspm_mount) == 1
new_bpf_rc = original[bpf_rc].replace(old_mount, b"/system_ext/etc/c17-port/service-wifi.jar").replace(qspm_mount, b"")
spare = len(original[bpf_rc]) - len(new_bpf_rc)
assert spare > 0
anchor = b"    exec_start c17_bpfloader\n"
assert new_bpf_rc.count(anchor) == 1
new_bpf_rc = new_bpf_rc.replace(anchor, b"#" * (spare - 1) + b"\n" + anchor, 1)

assert original[netd_rc].count(b"/data/local/tmp/n.so") == 2
new_netd_rc = original[netd_rc].replace(b"/data/local/tmp/n.so", b"/system_ext/lib64/c17-netd.so")
extra = len(new_netd_rc) - len(original[netd_rc])
new_netd_rc = re.sub(rb"(?m)^#{100,}$", lambda m: m[0][extra:], new_netd_rc, count=1)
updated = {bpf: new_bpf, bpf_rc: new_bpf_rc, netd_rc: new_netd_rc}
extents = {
    bpf: (0, 73800, 335_015_936, 40960),
    bpf_rc: (0, 4096, 381_054_976, 4096),
    netd_rc: (0, 2436, 381_116_464, 2436),
}

shutil.copyfile(source, target)
with target.open("r+b") as image:
    for path, (start, end, offset, capacity) in extents.items():
        old, new = original[path], updated[path]
        assert len(old) == len(new) and old[end:] == new[end:]
        image.seek(offset)
        blob = image.read(capacity)
        if path == bpf:
            packed = encode(blob, old[start:end], new[start:end])
        else:
            assert blob == old[start:end]
            packed = new[start:end]
        assert len(packed) == capacity
        image.seek(offset)
        image.write(packed)
for path, content in updated.items():
    assert extract(path, target) == content
    (run / ("integrated-" + Path(path).name)).write_bytes(content)
assert source.stat().st_size == target.stat().st_size == 954_871_808
(run / "system-a-integrated.json").write_text(json.dumps({
    "source_sha256": base_hash,
    "output_sha256": digest(target),
    "bytes": target.stat().st_size,
    "requires": "system-ext-a-integrated.img",
    "files_sha256": {path: sha256(data).hexdigest() for path, data in updated.items()},
}, indent=2) + "\n")
