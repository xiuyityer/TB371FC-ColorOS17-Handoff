#!/system/bin/sh
set -eu
source=/data/adb/c17-run0019-ims/VirtualCommService-no-physical-card.apk
target=/system_ext/priv-app/VirtualCommService/VirtualCommService.apk
[ "$(getprop ro.product.board)" = spinel ]
[ "$(getprop ro.baseband)" = apq ]
original=0ba01a0701519950c97febb1629d053256bc5d1b6da83bf722265baa484d4acf
patched=c2c4c7ed7f41d7f8d5e544431a8e45c507a762b1292f08b51763c1f52b49cb73
[ "$(nsenter -t 1 -m -- sha256sum "$target" | cut -d ' ' -f1)" = "$original" ]
install -m 0644 /data/local/tmp/c17-run0019/VirtualCommService-no-physical-card.apk "$source"
chown 0:0 "$source"
chcon u:object_r:system_file:s0 "$source"
[ "$(sha256sum "$source" | cut -d ' ' -f1)" = "$patched" ]
nsenter -t 1 -m -- mount --bind "$source" "$target"
[ "$(nsenter -t 1 -m -- sha256sum "$target" | cut -d ' ' -f1)" = "$patched" ]
pids=$(pidof com.oplus.subsys || true)
if [ -n "$pids" ]; then
    kill -TERM $pids
fi
date -Iseconds
