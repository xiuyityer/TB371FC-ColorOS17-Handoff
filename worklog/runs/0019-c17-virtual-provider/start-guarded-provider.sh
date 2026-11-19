#!/system/bin/sh
set -eu
source=/vendor/etc/c17-virtualcomm-ims-guard.apk
target=/system_ext/priv-app/OplusVirtualComm/OplusVirtualComm.apk
[ "$(getprop ro.product.board)" = spinel ]
[ "$(getprop ro.build.version.sdk)" = 37 ]
[ "$(sha256sum "$target" | cut -d ' ' -f1)" = f372cac9cc9865b3cb25a30b7dd010ed94e34186664db1ae2121ea5d6dc8dfec ]
patched=69f8c9f7f5fc335036c1cc11852c64d79aa7a405879e038a0b189c2551fe67cf
[ "$(sha256sum "$source" | cut -d ' ' -f1)" = "$patched" ]
nsenter -t 1 -m -- mount --bind "$source" "$target"
[ "$(nsenter -t 1 -m -- sha256sum "$target" | cut -d ' ' -f1)" = "$patched" ]
# PackageManager has already scanned the signed original. Restart only its phone client.
pids=$(pidof com.android.phone || true)
if [ -n "$pids" ]; then
    kill -TERM $pids
fi
setprop ctl.start c17-virtual-ril-0
setprop ctl.start c17-virtual-ril-1
