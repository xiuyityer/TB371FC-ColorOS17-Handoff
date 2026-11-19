#!/bin/sh
# Stage only the existing per-device netd diagnostic library.
set -eu
run_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
adb="$run_dir/../../../host-tools/platform-tools/adb"
serial=DEVICE_SERIAL
source_hash=d97e4575ecc3c4f06a94e6f7d003729637e021d0dac70dac10524cd68dc88cc3
diagnostic_hash=c0165dad6e99e7d11f26b10429de979223c4618e298e1a85c5dc8d6382afaa20
system_hash=5849cab7d51c99101c5fb0f78a037f1d70b9e0d0b9055f4a9c8272b71dd092fe
library=/data/local/tmp/n.so
staged=/data/local/tmp/n.so.run0007.pending

device() {
    "$adb" -s "$serial" "$@"
}

[ "$(device get-state)" = recovery ]
[ "$(device shell 'id -u')" = 0 ]
[ "$(device shell getprop ro.serialno)" = "$serial" ]
[ "$(device shell getprop ro.product.device)" = TB371FC ]
device shell getprop ro.twrp.version | grep -q '^3\.7\.1'
device shell 'grep -q " /data " /proc/mounts && test -b /dev/block/mapper/system_a'
system_result=$(device shell 'sha256sum /dev/block/mapper/system_a')
[ "${system_result%% *}" = "$system_hash" ]
printf '%s\n' "$system_result"
old=$(device shell "test -f $library && test ! -L $library && sha256sum $library")
[ "${old%% *}" = "$source_hash" ]
local_hash=$(shasum -a 256 "$run_dir/netd-abort-message.so")
[ "${local_hash%% *}" = "$diagnostic_hash" ]

device shell "test ! -e $staged && test ! -L $staged"
device push "$run_dir/netd-abort-message.so" "$staged"
device shell "set -e
    result=\$(sha256sum $staged)
    [ \"\${result%% *}\" = $diagnostic_hash ]
    chown 0:0 $staged
    chmod 0644 $staged
    chcon u:object_r:shell_data_file:s0 $staged
    mv -f $staged $library
    sync
    result=\$(sha256sum $library)
    [ \"\${result%% *}\" = $diagnostic_hash ]
    printf '%s\\n' \"\$result\"
    ls -lZ $library"
