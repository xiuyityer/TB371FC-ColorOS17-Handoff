#!/bin/sh
set -eu
run=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workspace=$(CDPATH='' cd -- "$run/../../.." && pwd)
adb="$workspace/host-tools/platform-tools/adb"
target=/tmp/c17-run0017-image.img
rows="${1:-$run/partitions.tsv}"
device() { "$adb" -s DEVICE_SERIAL "$@" </dev/null; }
[ "$(device get-state)" = recovery ]
[ "$(device shell 'id -u; getprop ro.product.device')" = "$(printf '0\nTB371FC')" ]
device shell getprop ro.twrp.version | grep '^3\.7\.1'
device shell 'dd if=/dev/block/by-name/recovery_a bs=1048576 count=69 2>/dev/null | sha256sum' |
    grep -F '6ce174af2b2bf6ebcec026d94fa95a12037e78ae1c27d3abfe40fbe0008fe7e7 '
while IFS="$(printf '\t')" read -r name size before after image; do
    partition="/dev/block/mapper/$name"
    [ "$(device shell "blockdev --getsize64 $partition")" = "$size" ]
    actual=$(device shell "sha256sum $partition")
    case "$actual" in
        "$before "*|"$after "*) printf '%s\n' "$actual";;
        *) printf 'Unexpected partition %s\n' "$actual" >&2; exit 1;;
    esac
    shasum -a 256 "$image" | grep -F "$after "
done < "$rows"
while IFS="$(printf '\t')" read -r name size before after image; do
    partition="/dev/block/mapper/$name"
    if device shell "sha256sum $partition" | grep -F "$after "; then
        continue
    fi
    device push "$image" "$target"
    device shell "sha256sum $target" | grep -F "$after "
    device shell "dd if=$target of=$partition bs=1048576 conv=fsync"
    device shell "sha256sum $partition" | grep -F "$after "
    device shell "rm $target"
done < "$rows"
while IFS="$(printf '\t')" read -r name size before after image; do
    device shell "sha256sum /dev/block/mapper/$name" | grep -F "$after "
done < "$rows"
