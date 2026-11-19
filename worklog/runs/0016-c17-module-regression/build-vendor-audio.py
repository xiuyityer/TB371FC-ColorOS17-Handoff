#!/usr/bin/env python3
"""Add the scoped audio parameter compatibility library to the verified vendor."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

run = Path(__file__).resolve().parent
workspace = run.parents[2]
base = workspace / "rom-r1/vendor_a.img"
output = run / "vendor-a-audio.img"
debugfs = workspace / "tool-src/e2fs-build/debugfs/debugfs"
e2fsck = workspace / "tool-src/e2fs-build/e2fsck/e2fsck"
rc_path = "/etc/init/android.hardware.audio.service.rc"
lib_path = "/lib/libc17_audio_rotation.so"
lib = run / Path(lib_path).name


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cmd(command, write=False):
    args = [str(debugfs), *(["-w"] if write else []), "-R", command, str(output)]
    proc = subprocess.run(args, capture_output=True, text=True, check=True)
    response = proc.stdout + proc.stderr
    with (run / "debugfs.txt").open("a") as log:
        log.write(command + "\n" + response)
    if re.search(r"file not found|could not allocate|no free|usage:|while writing|unknown request",
                 response, re.I):
        raise RuntimeError(response)
    return response


base_hash = sha(base)
assert base_hash == "834d966f20117d6579e237887ebcd2690b2c513331bf0c5bcefd9f48f0865c27"
assert not output.exists()
subprocess.run(["cp", "-c", base, output], check=True)
original = run / "audio-service.before.rc"
cmd(f'dump {rc_path} "{original}"')
old = original.read_bytes()
entry = b"service vendor.audio-hal /vendor/bin/hw/android.hardware.audio.service\n"
assert old.count(entry) == 1 and b"LD_PRELOAD" not in old
new_rc = run / "audio-service.rc"
new_rc.write_bytes(old.replace(entry, entry + b"    setenv LD_PRELOAD /vendor/lib/libc17_audio_rotation.so\n"))
rc_label = run / "audio-service.selinux"
library_label = run / "audio-library.selinux"
cmd(f'ea_get -f "{rc_label}" {rc_path} security.selinux')
cmd(f'ea_get -f "{library_label}" /lib/hw/audio.primary.kona.so security.selinux')
assert rc_label.read_bytes() == b"u:object_r:vendor_configs_file:s0\0"
assert library_label.read_bytes() == b"u:object_r:vendor_file:s0\0"
cmd(f"rm {rc_path}", True)
records = {}
for name, source, label in [(rc_path, new_rc, rc_label), (lib_path, lib, library_label)]:
    cmd(f'write "{source}" {name}', True)
    for attr, value in [("mode", "0100644"), ("uid", "0"), ("gid", "0")]:
        cmd(f"set_inode_field {name} {attr} {value}", True)
    cmd(f'ea_set -f "{label}" {name} security.selinux', True)
    dump = run / (Path(name).name + ".readback")
    actual_label = dump.with_suffix(".label")
    cmd(f'dump {name} "{dump}"')
    cmd(f'ea_get -f "{actual_label}" {name} security.selinux')
    assert sha(dump) == sha(source)
    assert actual_label.read_bytes() == label.read_bytes()
    status = cmd(f"stat {name}")
    assert "Mode:  0644" in status and re.search(r"User:\s+0\s+Group:\s+0", status)
    records[name] = sha(source)
p = subprocess.run([e2fsck, "-fn", output], capture_output=True, text=True)
(run / "vendor-e2fsck.txt").write_text(p.stdout + p.stderr)
assert p.returncode == 0, p.stdout + p.stderr
assert output.stat().st_size == base.stat().st_size == 899_739_648
print(json.dumps({"image": output.name, "bytes": output.stat().st_size,
                  "sha256": sha(output), "base_sha256": base_hash, "files": records}, indent=2))
