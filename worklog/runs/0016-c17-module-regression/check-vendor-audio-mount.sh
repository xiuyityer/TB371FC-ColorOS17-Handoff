#!/system/bin/sh
set -eu
dir=/data/local/tmp/c17-0016-vendor
cd "$dir"
mkdir -p vendor
loop=
bound=
fixture_bound=
cleanup() {
    if [ -n "$fixture_bound" ]; then umount /vendor/bin/hw/android.hardware.audio.service; fi
    if [ -n "$bound" ]; then umount /vendor; fi
    if [ -n "$loop" ]; then
        if grep -Fq " $dir/vendor " /proc/self/mountinfo; then umount "$dir/vendor"; fi
        if losetup -j "$dir/vendor.img" | grep -Fq "$loop:"; then losetup -d "$loop"; fi
    fi
}
trap cleanup EXIT
if grep -q ' shared:' /proc/self/mountinfo; then exit 1; fi
sha256sum -c vendor.sha256
loop=$(losetup -r -fs "$dir/vendor.img")
mount -t ext4 -o ro,noload,nosuid,nodev "$loop" "$dir/vendor"
grep -F " $dir/vendor " /proc/self/mountinfo
sha256sum -c vendor-files.sha256
mount --bind "$dir/vendor" /vendor
bound=1
env LD_PRELOAD=/vendor/lib/libc17_audio_rotation.so /system/bin/linker --list /vendor/bin/hw/android.hardware.audio.service > "$dir/vendor-linker-list.txt"
grep -F /vendor/lib/libc17_audio_rotation.so "$dir/vendor-linker-list.txt"
# Use the real vendor executable path to select its linker namespace. The
# substitute is a standalone fixture, so the live audio HAL is never started.
mount --bind "$dir/check-audio-rotation-compat" /vendor/bin/hw/android.hardware.audio.service
fixture_bound=1
env LD_PRELOAD=/vendor/lib/libc17_audio_rotation.so /vendor/bin/hw/android.hardware.audio.service
