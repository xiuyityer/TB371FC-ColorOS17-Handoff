#!/system/bin/sh
set -eu
ims=/system_ext/priv-app/OplusVirtualComm/OplusVirtualComm.apk
sharing=/system_ext/priv-app/VirtualCommService/VirtualCommService.apk
ims_patch=/vendor/etc/c17-virtualcomm-ims-guard.apk
sharing_patch=/vendor/etc/c17-virtualcomm-no-physical-card.apk
hash_file() { nsenter -t 1 -m -- sha256sum "$1" | cut -d ' ' -f1; }
[ "$(getprop ro.product.board)" = spinel ]
[ "$(getprop ro.baseband)" = apq ]
[ "$(getprop ro.build.version.sdk)" = 37 ]
[ "$(hash_file "$ims")" = f372cac9cc9865b3cb25a30b7dd010ed94e34186664db1ae2121ea5d6dc8dfec ]
[ "$(hash_file "$sharing")" = 0ba01a0701519950c97febb1629d053256bc5d1b6da83bf722265baa484d4acf ]
[ "$(hash_file "$ims_patch")" = 69f8c9f7f5fc335036c1cc11852c64d79aa7a405879e038a0b189c2551fe67cf ]
[ "$(hash_file "$sharing_patch")" = c2c4c7ed7f41d7f8d5e544431a8e45c507a762b1292f08b51763c1f52b49cb73 ]
nsenter -t 1 -m -- mount --bind "$ims_patch" "$ims"
if ! nsenter -t 1 -m -- mount --bind "$sharing_patch" "$sharing"; then
    nsenter -t 1 -m -- umount "$ims"
    exit 1
fi
# PackageManager has already scanned the original signed APKs.
for process in com.oplus.subsys com.android.phone; do
    pids=$(pidof "$process" || true)
    if [ -n "$pids" ]; then
        kill -TERM $pids || true
    fi
done
setprop ctl.start c17-virtual-ril-0
setprop ctl.start c17-virtual-ril-1
