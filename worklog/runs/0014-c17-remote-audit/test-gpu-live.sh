#!/system/bin/sh
# Mount only the GPU extension, then restart the independent init service.
set -eu
target=/system_ext/lib64/libgpuserviceextimpl.so
source=/data/adb/c17-port/gpu-precache-test.so
original=0e664704c359ed308bb119dd89eb09542f36f53d8621a5ff0b2ccdb960e64394
expected="$1"

old_boot=$(cat /proc/sys/kernel/random/boot_id)
old_server=$(pidof system_server)
old_gpu=$(pidof gpuservice)
test "$(getprop init.svc.gpu)" = running
test "$(sha256sum "$target" | cut -d' ' -f1)" = "$original"
cp /data/local/tmp/c17-gpu-precache.pending "$source"
chmod 0644 "$source"
chown 0:0 "$source"
chcon u:object_r:system_lib_file:s0 "$source"
test "$(sha256sum "$source" | cut -d' ' -f1)" = "$expected"

restore() {
    umount -l "$target" || true
    setprop ctl.restart gpu || true
}
mount --bind "$source" "$target"
trap restore EXIT
setprop ctl.restart gpu
for second in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    new_gpu=$(pidof gpuservice || true)
    if [ -n "$new_gpu" ] && [ "$new_gpu" != "$old_gpu" ] &&
       [ "$(getprop init.svc.gpu)" = running ] &&
       service check gpu | grep -q 'Service gpu: found'; then
        break
    fi
done
test -n "$new_gpu"
test "$new_gpu" != "$old_gpu"
test "$(cat /proc/sys/kernel/random/boot_id)" = "$old_boot"
test "$(pidof system_server)" = "$old_server"
inode=$(nsenter -t "$new_gpu" -m -- stat -c %i "$target")
awk -v i="$inode" '$5 == i && $6 ~ /libgpuserviceextimpl[.]so$/ {print; n++} END {exit (n == 0)}' "/proc/$new_gpu/maps"
test "$(sha256sum "$target" | cut -d' ' -f1)" = "$expected"
date -Iseconds
printf 'boot=%s system_server=%s old_gpu=%s new_gpu=%s\n' "$old_boot" "$old_server" "$old_gpu" "$new_gpu"
dumpsys -t 4 gpu --precache apps
trap - EXIT
