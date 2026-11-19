#!/system/bin/sh
set -eu
dir=/data/local/tmp/c17-0015-mount
cd "$dir"
mkdir -p my_product system_ext
product_loop=
ext_loop=
cleanup_loop() {
    point="$1"
    file="$2"
    loop="$3"
    if grep -Fq " $point " /proc/self/mountinfo; then umount "$point"; fi
    if losetup -j "$file" | grep -Fq "$loop:"; then losetup -d "$loop"; fi
}
cleanup() {
    if [ -n "$ext_loop" ]; then cleanup_loop "$dir/system_ext" "$dir/ext.img" "$ext_loop"; fi
    if [ -n "$product_loop" ]; then cleanup_loop "$dir/my_product" "$dir/product.img" "$product_loop"; fi
}
trap cleanup EXIT
if grep -q ' shared:' /proc/self/mountinfo; then exit 1; fi
sha256sum -c candidate.sha256
product_loop=$(losetup -r -fs "$dir/product.img")
ext_loop=$(losetup -r -fs "$dir/ext.img")
mount -t erofs -o ro,nosuid,nodev "$product_loop" "$dir/my_product"
mount -t erofs -o ro,nosuid,nodev "$ext_loop" "$dir/system_ext"
grep -E '/c17-0015-mount/(my_product|system_ext) ' /proc/self/mountinfo
sha256sum -c files.sha256
/system/bin/sh -n "$dir/system_ext/etc/c17-port/pen-refresh-service.sh"
/system/bin/sh -n "$dir/system_ext/bin/c17-ai-controls"
