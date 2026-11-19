#!/usr/bin/env python3
"""Add two early-init file mounts to the run 0011 EROFS image."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

run = Path(__file__).resolve().parent
dump = run.parents[2] / "tool-src/erofs-utils-1.8.10/dump/dump.erofs"
source = run.parent / "0010-c17-ringbuf-kernel/system-a-engineer-compat.img"
output = run / "system-a-cold-boot.img"
path = "/system/etc/init/netbpfload.rc"

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as image:
        for block in iter(lambda: image.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


digest = sha256(source)
assert digest == "76f665ffbbe2c5126993bbad1887b2532c7064b5de7eb364675de54f11b5308e"
listing = subprocess.check_output([dump, f"--path={path}", "-e", source], text=True)
assert "Layout: 2" in listing
extents = re.findall(r"^\s*\d+:\s*(\d+)\.\.\s*(\d+)\s*\|\s*\d+\s*:\s*(\d+)\.\.\s*(\d+)", listing, re.M)
original = subprocess.check_output([dump, "--cat", f"--path={path}", source])
start = original.index(b"# It is important that we start bpfloader after:")
end = original.index(b"    exec_start c17_bpfloader", start)
commands = (
    b"# APEX is activated during post-fs-data, before zygote-start.\n"
    b"on load-bpf-programs\n"
    b"    mount none /data/adb/c17-port/service-wifi.jar /apex/com.android.wifi/javalib/service-wifi.jar bind\n"
    b"    mount none /data/adb/c17-port/libupdateprof.qti.so /system_ext/lib64/libupdateprof.qti.so bind\n"
    b"    write /proc/sys/kernel/kptr_restrict 1\n"
)
assert start < end <= 4096 and len(commands) + 2 <= end - start
padding = b"#" + b" " * (end - start - len(commands) - 2) + b"\n"
patched = original[:start] + commands + padding + original[end:]
assert len(patched) == len(original)
shutil.copyfile(source, output)
covered = 0
with output.open("r+b") as image:
    for low, high, offset, stop in (map(int, row) for row in extents):
        assert low == covered and high - low == stop - offset
        image.seek(offset)
        assert image.read(stop - offset) == original[low:high]
        if patched[low:high] != original[low:high]:
            image.seek(offset)
            image.write(patched[low:high])
        covered = high
assert covered == len(original)
assert output.stat().st_size == source.stat().st_size == 954_871_808
assert subprocess.check_output([dump, "--cat", f"--path={path}", output]) == patched
(run / "netbpfload.rc").write_bytes(patched)
patched_digest = sha256(output)
(run / "candidate.json").write_text(json.dumps({
    "system_a_before_sha256": digest,
    "system_a_after_sha256": patched_digest,
    "bytes": output.stat().st_size,
    "rc_path": path,
    "rc_sha256": hashlib.sha256(patched).hexdigest(),
}, indent=2) + "\n")
