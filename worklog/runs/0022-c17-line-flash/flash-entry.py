#!/usr/bin/env python3
"""Flash the TB371FC C17 A-slot release with the original TWRP."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(8 << 20), b""):
            digest.update(data)
    return digest.hexdigest()


def executable(name):
    system = platform.system()
    if system == "Darwin":
        path = PACKAGE / "tools/macos" / name
    elif system == "Windows":
        path = PACKAGE / "tools/windows" / (name + ".exe")
    else:
        path = None
    result = str(path) if path and path.is_file() else shutil.which(name)
    if not result:
        raise RuntimeError(f"{name} is required. Install Android Platform-Tools.")
    return result


def verify(manifest):
    if (manifest["format"], manifest["product"], manifest["slot"]) != (1, "spinel", "a"):
        raise RuntimeError("Unsupported release manifest")
    if set(manifest["files"]) != {
        "boot_a.img", "recovery_a.img", "apps/KernelSU-32720.apk", "apps/ZUI-Camera.apk"
    }:
        raise RuntimeError("Unexpected release files")
    cursor = 0
    for index, entry in enumerate(manifest["parts"]):
        if entry["file"] != f"super/super.part{index:04d}.sparse.img":
            raise RuntimeError("Unexpected sparse image filename")
        if entry["start"] != cursor or entry["raw_bytes"] <= 0:
            raise RuntimeError("Sparse image coverage is incomplete")
        cursor += entry["raw_bytes"]
    if cursor != manifest["super_bytes"]:
        raise RuntimeError("Sparse image size does not match super")
    files = {entry["file"]: entry for entry in manifest["parts"]}
    files.update(manifest["files"])
    for filename, entry in files.items():
        path = PACKAGE / filename
        if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
            raise RuntimeError(f"Size or SHA-256 mismatch: {filename}")
    print(f"Verified {len(manifest['parts'])} sparse images, boot, recovery and APKs", flush=True)


def run(command, timeout=120):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{subprocess.list2cmdline(command)}\n{result.stdout.rstrip()}")
    return result.stdout


def save(path, state):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)
        file.write("\n")
    tmp.replace(path)


def flash(manifest, args):
    fastboot = executable("fastboot")
    devices = re.findall(r"^(\S+)\s+fastboot\s*$", run([fastboot, "devices"], 15), re.M)
    if args.serial:
        if args.serial not in devices:
            raise RuntimeError("The selected device is not in bootloader Fastboot")
        serial = args.serial
    elif len(devices) == 1:
        serial = devices[0]
    else:
        raise RuntimeError("Connect one Fastboot device or select it with --serial")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", serial):
        raise RuntimeError("Unsupported device serial format")

    args.state_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = args.state_dir / f"{serial}.json"
    log = args.state_dir / f"{serial}.log"

    def fb(*cmd):
        command = [fastboot, "-s", serial, *cmd]
        try:
            result = run(command)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            with log.open("a", encoding="utf-8") as file:
                file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(cmd)}\n{exc}\n")
            raise
        with log.open("a", encoding="utf-8") as file:
            file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(cmd)}\n{result}")
        return result

    def getvar(name):
        output = fb("getvar", name)
        match = re.search(rf"^{re.escape(name)}:\s*(\S+)", output, re.M)
        if not match:
            raise RuntimeError(f"Unexpected fastboot reply: {output.rstrip()}")
        return match.group(1)

    if getvar("product") != manifest["product"] or getvar("unlocked") != "yes":
        raise RuntimeError("Requires an unlocked Lenovo TB371FC (spinel)")
    sizes = {
        "super": manifest["super_bytes"],
        "boot_a": manifest["files"]["boot_a.img"]["bytes"],
        "recovery_a": manifest["recovery_partition_bytes"],
    }
    for name, size in sizes.items():
        if int(getvar(f"partition-size:{name}"), 16) != size:
            raise RuntimeError(f"Unexpected partition size: {name}")
    max_size = int(getvar("max-download-size"), 0)
    largest = max(*(part["bytes"] for part in manifest["parts"]),
                  manifest["files"]["boot_a.img"]["bytes"],
                  manifest["files"]["recovery_a.img"]["bytes"])
    if largest > max_size:
        raise RuntimeError("Bootloader download size is too small")
    current_slot = getvar("current-slot")
    if current_slot not in {"a", "b"}:
        raise RuntimeError(f"Unexpected active slot: {current_slot}")

    steps = [("flash", "recovery_a", "recovery_a.img")]
    steps.extend(("flash", "super", entry["file"]) for entry in manifest["parts"])
    steps.extend([("flash", "boot_a", "boot_a.img"), ("set_active", "a", None)])
    identity = {"serial": serial, "manifest_sha256": sha(PACKAGE / "manifest.json")}
    if args.resume:
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
        if any(state.get(key) != value for key, value in identity.items()):
            raise RuntimeError("Checkpoint belongs to another device or release")
        offset = state["next_step"]
        if not 0 <= offset <= len(steps):
            raise RuntimeError("Invalid checkpoint step")
    else:
        if checkpoint.exists() and not args.restart:
            raise RuntimeError("Checkpoint exists. Use --resume or --restart explicitly.")
        offset = 0
        state = dict(identity, next_step=0)
        save(checkpoint, state)

    for index in range(offset, len(steps)):
        action, name, file = steps[index]
        if file:
            fb(action, name, str(PACKAGE / file))
        else:
            fb(action, name)
        state["next_step"] = index + 1
        save(checkpoint, state)
        if name != "super" or index % 20 == 0 or index == len(manifest["parts"]):
            print(f"Step {index + 1}/{len(steps)} confirmed: {name}", flush=True)
    if getvar("current-slot") != "a":
        raise RuntimeError("Fastboot did not select slot A")
    if args.recovery:
        fb("reboot", "recovery")
    else:
        fb("reboot")
    print("Fastboot writes confirmed. Device is rebooting.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify package files without a device")
    parser.add_argument("--serial", help="select a specific Fastboot serial")
    parser.add_argument("--state-dir", type=Path, default=PACKAGE / "flash-state")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true", help="continue an interrupted flash")
    mode.add_argument("--restart", action="store_true", help="start at the first image")
    parser.add_argument("--recovery", action="store_true", help="boot original TWRP after flashing")
    args = parser.parse_args()
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    verify(manifest)
    if not args.check:
        flash(manifest, args)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
