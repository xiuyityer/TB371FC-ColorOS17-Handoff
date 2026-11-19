#!/bin/sh
# Write the exact same-size VINTF 30 candidate to C17 system_a.
set -eu

run=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workspace=$(CDPATH='' cd -- "$run/../../.." && pwd)
candidate="$run/system-a-vintf30.img"
adb="$workspace/host-tools/platform-tools/adb"
before=49ea8a803630cfea164bf8e2cb4f4a274663998fc390e45cdfe082bd5fd4f68b
after=97afde2cc1c6c46755dddab55294d63e3a14b848a4787f39dd1306fbd77f3b54
image=/tmp/c17-run0013-system.img
partition=/dev/block/mapper/system_a

device() {
    "$adb" -s DEVICE_SERIAL "$@"
}

[ "$(device get-state)" = recovery ]
[ "$(device shell 'id -u; getprop ro.product.device')" = "$(printf '0\nTB371FC')" ]
device shell getprop ro.twrp.version | grep '^3\.7\.1'
device shell 'dd if=/dev/block/by-name/recovery_a bs=1048576 count=69 2>/dev/null | sha256sum' |
    grep -F '6ce174af2b2bf6ebcec026d94fa95a12037e78ae1c27d3abfe40fbe0008fe7e7 '
[ "$(device shell "blockdev --getsize64 $partition")" = 954871808 ]
device shell "sha256sum $partition" | grep -F "$before "
shasum -a 256 "$candidate" | grep -F "$after "

device push "$candidate" "$image"
device shell "sha256sum $image" | grep -F "$after "
device shell "dd if=$image of=$partition bs=1048576 conv=fsync"
device shell "sha256sum $partition" | grep -F "$after "
