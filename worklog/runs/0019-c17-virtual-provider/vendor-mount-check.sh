#!/system/bin/sh
set -eu
stage=/data/local/tmp/c17-run0019
! grep -q ' shared:' /proc/self/mountinfo
mkdir -p "$stage/vendor-check"
loop=$(losetup -r -fs "$stage/vendor.img")
cleanup() {
    umount /vendor 2>/dev/null || true
    umount "$stage/vendor-check" 2>/dev/null || true
    if losetup -j "$stage/vendor.img" | grep -q .; then losetup -d "$loop"; fi
}
trap cleanup EXIT
mount -t ext4 -o ro,noload,nosuid,nodev "$loop" "$stage/vendor-check"
mount --bind "$stage/vendor-check" /vendor
sha256sum /vendor/etc/vintf/manifest/r94-communication-center.xml
/system/bin/vintf dm > "$stage/vintf-dm.txt"
grep -F 'vircomm' "$stage/vintf-dm.txt"
"$stage/../c17-check-vintf"
export LD_LIBRARY_PATH=/vendor/lib64/r94-commcenter
LD_PRELOAD=/vendor/lib64/r94-commcenter/lib-virtual-modem-radio-aidl.so /system/bin/linker64 --list /vendor/bin/r94-commcenter/subsys_daemon
/system/bin/linker64 --list /vendor/bin/r94-commcenter/commcenterd
