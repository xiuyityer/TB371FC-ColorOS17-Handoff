#!/usr/bin/env python3
"""Add the virtual data budget and remote state fixes to the verified vendor image."""
from hashlib import sha256
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

run = Path(__file__).resolve().parent
port = run.parents[2]
prior = run.parent / "0019-c17-virtual-provider"
base = prior / "vendor-a-c17-virtual-stable-sharing.img"
out = run / "vendor-a-c17-shared-data.img"
debugfs = port / "tool-src/e2fs-build/debugfs/debugfs"
fsck = port / "tool-src/e2fs-build/e2fsck/e2fsck"
base_sha = "a9606e70633dcdf4e2f0076a5cc2fa5e494f6297c0e6822a1f3b71d061522c10"


def digest(path):
    result = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            result.update(block)
    return result.hexdigest()


def edit(command, write=False):
    argv = [debugfs, "-w"] if write else [debugfs]
    result = subprocess.run([*argv, "-R", command, out], capture_output=True, check=True)
    with (run / "vendor-debugfs.log").open("ab") as log:
        log.write(command.encode() + b"\n" + result.stdout + result.stderr)
    return result.stdout


assert digest(base) == base_sha and not out.exists()
subprocess.run(["cp", "-c", base, out], check=True)
files = (
    ("/etc/c17-start-guarded-provider.sh", "start-provider-data.sh", "vendor_configs_file", True),
    ("/etc/c17-virtualcomm-ims-guard.apk", "OplusVirtualComm-ims-slot-guard.apk", "system_file", True),
    ("/etc/c17-virtual-data-budget.jar", "oplus-telephony-common-ext-data-budget.jar", "system_file", False),
)
with TemporaryDirectory() as directory:
    temp = Path(directory)
    for dest, name, label, replacing in files:
        if replacing:
            assert b"Type: regular" in edit(f"stat {dest}")
            edit(f"rm {dest}", True)
        source = run / name
        edit(f'write "{source}" {dest}', True)
        edit(f"set_inode_field {dest} mode 0100644", True)
        expected_label = f"u:object_r:{label}:s0".encode() + bytes(1)
        (temp / "label").write_bytes(expected_label)
        edit(f'ea_set -f "{temp / "label"}" {dest} security.selinux', True)
        got = temp / "readback"
        edit(f'dump {dest} "{got}"')
        assert got.read_bytes() == source.read_bytes(), dest
        got.unlink()
        edit(f'ea_get -f "{got}" {dest} security.selinux')
        assert got.read_bytes() == expected_label, dest
        got.unlink()
        stat = edit(f"stat {dest}")
        assert b"Type: regular" in stat and b"Mode:  0644" in stat and b"User:     0   Group:     0" in stat
check = subprocess.run([fsck, "-fn", out], capture_output=True)
(run / "vendor-fsck.txt").write_bytes(check.stdout + check.stderr)
assert check.returncode == 0 and out.stat().st_size == base.stat().st_size
sha = digest(out)
(run / "vendor-partitions.tsv").write_text(f"vendor_a\t{out.stat().st_size}\t{base_sha}\t{sha}\t{out}\n")
print(sha)
