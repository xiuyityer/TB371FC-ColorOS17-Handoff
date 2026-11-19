#!/usr/bin/env python3
"""Install the donor AIDL virtual-radio providers into the port's private vendor directories."""
import argparse
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

run = Path(__file__).resolve().parent
port = run.parents[2]
previous = run.parent / "0017-c17-camera-connect"
base = previous / "vendor-a-audio-override.img"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("variant", choices=("abi-first", "subscription", "guarded-data", "stable-sharing"))
options = parser.parse_args()
variant = options.variant
stable = variant == "stable-sharing"
guarded = variant in ("guarded-data", "stable-sharing")
subscription = variant != "abi-first"
image = run / f"vendor-a-c17-virtual-{variant}.img"
debugfs = port / "tool-src/e2fs-build/debugfs/debugfs"
fsck = port / "tool-src/e2fs-build/e2fsck/e2fsck"
old_sha = "655a37c2737398cebea9b182452613132c494e7b78ad8b5747264ead4d2ef454"
manifest_path = "/etc/vintf/manifest/r94-communication-center.xml"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def edit(command, write=False):
    args = [debugfs, "-w"] if write else [debugfs]
    result = subprocess.run([*args, "-R", command, image], capture_output=True, check=True)
    with (run / f"vendor-debugfs-{variant}.log").open("ab") as log:
        log.write(command.encode() + b"\n" + result.stdout + result.stderr)
    return result.stdout


assert digest(base) == old_sha and not image.exists()
subprocess.run(["cp", "-c", base, image], check=True)
manifest = ET.fromstring(edit(f"cat {manifest_path}"))
for item in list(manifest):
    if item.get("format") == "hidl":
        manifest.remove(item)
assert len(manifest) == 1 and manifest[0].findtext("name") == "vendor.oplus.hardware.communicationcenter"
donor = ET.parse(run / "donor-telephony-dsds.xml")
services = {"data", "voice", "sim", "network", "modem", "messaging"}
for item in donor.findall("hal"):
    name = item.findtext("name", "")
    if name in {f"android.hardware.radio.{s}" for s in services}:
        assert item.get("format") == "aidl" and item.findtext("version") == "2"
        assert [i.text.rsplit("/", 1)[1] for i in item.findall("fqname")] == ["vircomm1", "vircomm2"]
        manifest.append(item)
assert len(manifest) == 7
ET.indent(manifest, space="    ")
updated = run / "r94-communication-center.xml"
ET.ElementTree(manifest).write(updated, encoding="utf-8")
files = {
    manifest_path: (updated, "0644", "vendor_configs_file"),
    "/etc/init/r94-commcenterd.rc": (run / "virtual-provider.rc", "0644", "vendor_configs_file"),
    "/bin/r94-commcenter/commcenterd": (run / "provider/bin/commcenterd", "0755", "r94_commcenterd_exec"),
    "/bin/r94-commcenter/subsys_daemon": (run / "provider/bin/subsys_daemon", "0755", "vendor_file"),
    "/lib64/r94-commcenter/oplus_vnet.ko": (previous / "vnet-kbuild/oplus_vnet.ko", "0644", "vendor_file"),
}
files.update({f"/lib64/r94-commcenter/{p.name}": (p, "0644", "vendor_file")
              for p in sorted((run / "provider/lib64").glob("*.so"))
              if (subscription or p.name != "libc++.so")
              and (guarded or p.name not in {"lib-virtual-modem-qti-ims-aidl.so",
                                             "vendor.qti.hardware.radio.ims-V7-ndk.so",
                                             "vendor.qti.hardware.radio.qtiradioconfig-V2-ndk.so"})})
if subscription:
    files["/etc/permissions/c17-virtual-subscription.xml"] = (
        run / "c17-virtual-subscription.xml", "0644", "vendor_configs_file")
assert digest(files["/lib64/r94-commcenter/oplus_vnet.ko"][0]) == "b9917a9ff1b561a731501545856bb915be3a8e4469ed0292467b69868c3b5583"
if guarded:
    files.update({
        "/etc/init/r94-commcenterd.rc": (run / "virtual-provider-guarded.rc", "0644", "vendor_configs_file"),
        "/etc/permissions/c17-virtual-subscription.xml": (run / "c17-virtual-data.xml", "0644", "vendor_configs_file"),
        "/lib64/r94-commcenter/lib-virtual-modem-radio-aidl.so": (
            run / "lib-virtual-modem-radio-aidl-private-ims.so", "0644", "vendor_file"),
        "/etc/c17-virtualcomm-ims-guard.apk": (run / "OplusVirtualComm-ims-guard.apk", "0644", "system_file"),
        "/etc/c17-start-guarded-provider.sh": (run / "start-guarded-provider.sh", "0644", "vendor_configs_file"),
    })
if stable:
    files.update({
        "/etc/c17-start-guarded-provider.sh": (run / "start-stable-provider.sh", "0644", "vendor_configs_file"),
        "/etc/c17-virtualcomm-no-physical-card.apk": (
            run / "VirtualCommService-no-physical-card.apk", "0644", "system_file"),
    })
with TemporaryDirectory() as temp:
    work = Path(temp)
    for dest, (source, mode, label) in files.items():
        if dest in {manifest_path, "/etc/init/r94-commcenterd.rc", "/bin/r94-commcenter/commcenterd"}:
            edit(f"rm {dest}", True)
        edit(f'write "{source}" {dest}', True)
        label_file = work / "label"
        label_value = f"u:object_r:{label}:s0".encode() + bytes(1)
        label_file.write_bytes(label_value)
        edit(f"set_inode_field {dest} mode 010{mode}", True)
        edit(f'ea_set -f "{label_file}" {dest} security.selinux', True)
        observed = work / "readback"
        observed.unlink(missing_ok=True)
        edit(f'dump {dest} "{observed}"')
        assert observed.read_bytes() == source.read_bytes(), dest
        observed.unlink()
        edit(f'ea_get -f "{observed}" {dest} security.selinux')
        assert observed.read_bytes() == label_value, dest
        stat = edit(f"stat {dest}")
        assert f"Mode:  {mode}".encode() in stat and b"Type: regular" in stat and b"User:     0   Group:     0" in stat, dest
check = subprocess.run([fsck, "-fn", image], capture_output=True)
(run / f"vendor-fsck-{variant}.txt").write_bytes(check.stdout + check.stderr)
assert check.returncode == 0 and image.stat().st_size == base.stat().st_size
sha = digest(image)
before = old_sha
if subscription:
    prior = "abi-first"
    if guarded:
        prior = "subscription"
    if stable:
        prior = "guarded-data"
    before = (run / f"vendor-{prior}-partitions.tsv").read_text().split("\t")[3]
(run / f"vendor-{variant}-partitions.tsv").write_text(
    f"vendor_a\t{image.stat().st_size}\t{before}\t{sha}\t{image}\n")
print(json.dumps({"sha256": sha, "files": len(files), "bytes": image.stat().st_size}, indent=2))
