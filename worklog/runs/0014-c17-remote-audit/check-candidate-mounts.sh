#!/system/bin/sh
set -eu
dir=/data/local/tmp/c17-0014-mount
mkdir -p "$dir/system" "$dir/ext"
system_loop=
ext_loop=
overlay=
cleanup_loop() {
    point="$1"
    file="$2"
    loop="$3"
    if grep -Fq " $point " /proc/self/mountinfo; then
        umount "$point"
    fi
    # Android toybox can auto-detach the loop when unmounting it.
    if losetup -j "$file" | grep -Fq "$loop:"; then
        losetup -d "$loop"
    fi
}
cleanup() {
    if [ -n "$overlay" ]; then umount /system_ext; fi
    if [ -n "$ext_loop" ]; then cleanup_loop "$dir/ext" "$dir/ext.img" "$ext_loop"; fi
    if [ -n "$system_loop" ]; then cleanup_loop "$dir/system" "$dir/system.img" "$system_loop"; fi
}
trap cleanup EXIT
if grep -q ' shared:' /proc/self/mountinfo; then
    echo "The mount namespace is not private" >&2
    exit 1
fi
cd "$dir"
sha256sum -c candidate.sha256
system_loop=$(losetup -r -fs "$dir/system.img")
ext_loop=$(losetup -r -fs "$dir/ext.img")
mount -t erofs -o ro,nosuid,nodev "$system_loop" "$dir/system"
mount -t erofs -o ro,nosuid,nodev "$ext_loop" "$dir/ext"
grep -E "/c17-0014-mount/(system|ext) " /proc/self/mountinfo
sha256sum -c files.sha256
mount --bind "$dir/ext" /system_ext
overlay=1
env LD_PRELOAD=/system_ext/lib64/c17-netd.so /system/bin/linker64 --list /system/bin/netd > linker-list.txt
grep -F /system_ext/lib64/c17-netd.so linker-list.txt
