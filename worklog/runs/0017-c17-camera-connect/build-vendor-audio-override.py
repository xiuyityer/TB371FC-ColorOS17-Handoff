#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import subprocess

run = Path(__file__).resolve().parent
w = run.parents[2]
base = run.parent / "0016-c17-module-regression/vendor-a-audio.img"
out = run / "vendor-a-audio-override.img"
debugfs = w / "tool-src/e2fs-build/debugfs/debugfs"
e2fsck = w / "tool-src/e2fs-build/e2fsck/e2fsck"
path = "/etc/init/hw/init.qcom.rc"


def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def edit(command, write=False):
    result = subprocess.run([debugfs, *(["-w"] if write else []), "-R", command, out],
                            text=True, capture_output=True, check=True)
    (run/"vendor-audio-override-debugfs.txt").open("a").write(result.stdout + result.stderr)
    return result.stdout


assert sha(base) == "f9ca92fac0ba74e389e71aab06a280a7b65d8c6c654ed1c40c6390ff6b442310"
assert not out.exists()
subprocess.run(["cp", "-c", base, out], check=True)
old, label, updated = (run / n for n in ("init.qcom.original.rc", "init.qcom.label", "init.qcom.audio.rc"))
edit(f'dump {path} "{old}"')
edit(f'ea_get -f "{label}" {path} security.selinux')
original = old.read_bytes()
entry = b"service vendor.audio-hal /vendor/bin/hw/android.hardware.audio.service\n    override\n"
assert original.count(entry) == 1 and b"libc17_audio_rotation.so" not in original
updated.write_bytes(original.replace(entry, entry + b"    setenv LD_PRELOAD /vendor/lib/libc17_audio_rotation.so\n"))
mode = edit(f"stat {path}")
assert "Mode:  0644" in mode and "User:     0   Group:     0" in mode
edit(f"rm {path}", True)
edit(f'write "{updated}" {path}', True)
edit(f"set_inode_field {path} mode 0100644", True)
edit(f'ea_set -f "{label}" {path} security.selinux', True)
readback, actual_label = run / "init.qcom.audio.readback.rc", run / "init.qcom.readback.label"
edit(f'dump {path} "{readback}"')
edit(f'ea_get -f "{actual_label}" {path} security.selinux')
assert readback.read_bytes() == updated.read_bytes()
assert label.read_bytes() == actual_label.read_bytes()
mode = edit(f"stat {path}")
assert "Mode:  0644" in mode and "User:     0   Group:     0" in mode
p = subprocess.run([e2fsck, "-fn", out], capture_output=True, text=True)
(run/"vendor-audio-override-fsck.txt").write_text(p.stdout+p.stderr)
assert p.returncode == 0 and out.stat().st_size == base.stat().st_size
print(json.dumps(dict(sha256=sha(out),bytes=out.stat().st_size,file=path),indent=2))
