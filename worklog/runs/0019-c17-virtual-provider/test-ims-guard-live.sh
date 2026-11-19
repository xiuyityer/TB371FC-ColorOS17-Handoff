#!/system/bin/sh
set -eu
source=/data/adb/c17-run0019-ims/OplusVirtualComm-ims-guard.apk
target=/system_ext/priv-app/OplusVirtualComm/OplusVirtualComm.apk
original=f372cac9cc9865b3cb25a30b7dd010ed94e34186664db1ae2121ea5d6dc8dfec
patched=69f8c9f7f5fc335036c1cc11852c64d79aa7a405879e038a0b189c2551fe67cf
test "$(nsenter -t 1 -m -- sha256sum "$target" | cut -d ' ' -f1)" = "$original"
install -m 0644 /data/local/tmp/c17-run0019/OplusVirtualComm-ims-guard.apk "$source"
chown 0:0 "$source"
chcon u:object_r:system_file:s0 "$source"
test "$(sha256sum "$source" | cut -d ' ' -f1)" = "$patched"
nsenter -t 1 -m -- mount --bind "$source" "$target"
test "$(nsenter -t 1 -m -- sha256sum "$target" | cut -d ' ' -f1)" = "$patched"
pids=$(pidof com.android.phone || true)
if [ -n "$pids" ]; then
    kill -TERM $pids
fi
