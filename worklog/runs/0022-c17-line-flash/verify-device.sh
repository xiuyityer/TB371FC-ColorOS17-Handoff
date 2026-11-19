#!/bin/sh
set -eu
run=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workspace=$(CDPATH='' cd -- "$run/../../.." && pwd)
release="$workspace/releases/TB371FC-C17-KSU-20261118"
adb="$release/tools/macos/adb"
fastboot="$release/tools/macos/fastboot"
serial=DEVICE_SERIAL
device() { "$adb" -s "$serial" "$@" </dev/null; }

if [ "${1:-}" != --android-only ]; then
count=0
until [ "$(device get-state 2>/dev/null || true)" = recovery ]; do
    count=$((count + 1))
    [ "$count" -le 90 ] || exit 1
    sleep 1
done
device shell 'id -u; getprop ro.product.device; getprop ro.twrp.version' | tee "$run/recovery-identity.txt"
grep -qx '0' "$run/recovery-identity.txt"
grep -qx 'TB371FC' "$run/recovery-identity.txt"
grep -qx '3.7.1_12-0' "$run/recovery-identity.txt"
device shell '
    sha256sum /dev/block/by-name/boot_a
    dd if=/dev/block/by-name/recovery_a bs=1048576 count=69 2>/dev/null | sha256sum
    sha256sum /dev/block/by-name/super
' | tee "$run/readback-sha256.txt"
python3 - "$release/manifest.json" "$run/readback-sha256.txt" <<'PY'
import json, pathlib, sys
manifest = json.loads(pathlib.Path(sys.argv[1]).read_text())
actual = [line.split()[0] for line in pathlib.Path(sys.argv[2]).read_text().splitlines()]
expected = [manifest["files"][name]["sha256"] for name in ("boot_a.img", "recovery_a.img")]
expected.append(manifest["super_sha256"])
if actual != expected:
    raise SystemExit(f"Device hashes did not match release: {actual} != {expected}")
PY
device reboot bootloader
count=0
until "$fastboot" devices | grep -q "^$serial"; do
    count=$((count + 1))
    [ "$count" -le 45 ] || exit 1
    sleep 1
done
"$fastboot" -s "$serial" getvar current-slot 2>&1 | tee "$run/boot.log" | grep -F 'current-slot: a'
"$fastboot" -s "$serial" continue >> "$run/boot.log" 2>&1
fi
count=0
until [ "$(device shell getprop sys.boot_completed 2>/dev/null || true)" = 1 ] &&
    [ "$(device shell getprop init.svc.c17_pen_refresh 2>/dev/null || true)" = running ]; do
    count=$((count + 1))
    [ "$count" -le 110 ] || exit 1
    sleep 1
done
device shell '
    set -e
    getprop ro.boot.slot_suffix
    getprop sys.boot_completed
    uname -r
    getprop init.svc.c17_pen_refresh
    getprop init.svc.bootanim
    su -c id
    grep -F "com.android.launcher" /my_product/etc/refresh_rate_config.xml
    settings get secure oplus_customize_screen_refresh_rate
    settings get system peak_refresh_rate
    pidof c17-pen-refresh
    pm path com.zui.camera
    pm path me.weishu.kernelsu
    pm list packages -d | grep com.oplus.camera
    cmd display get-active-mode 0
    dumpsys window | awk "/mCurrentFocus=/{print}"
' | tee "$run/android-runtime.txt"
grep -qx '_a' "$run/android-runtime.txt"
grep -qx '1' "$run/android-runtime.txt"
grep -qx '4.19.325-perf+' "$run/android-runtime.txt"
grep -Fq 'uid=0(root)' "$run/android-runtime.txt"
grep -Fq 'rateId="3-2-2-4-4"' "$run/android-runtime.txt"
grep -Fq 'com.zui.camera' "$run/android-runtime.txt"
grep -Fq 'me.weishu.kernelsu' "$run/android-runtime.txt"
grep -qx 'running' "$run/android-runtime.txt"
grep -qx 'stopped' "$run/android-runtime.txt"
