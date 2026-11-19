#!/bin/sh
# Stage the complete pinned kernel source on the case-sensitive build volume.
set -eu

run=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workspace=$(CDPATH='' cd -- "$run/../../.." && pwd)
volume="$run/kernel-build-volume"
archive="$run/kernel-v2.2-source.tar.gz"
source="$volume/kernel-v2.2"
stage="$volume/kernel-v2.2.extracting"
out="$volume/obj-baseline"
tools="$workspace/host-tools/android-ndk-r27d/toolchains/llvm/prebuilt/darwin-x86_64/bin"

diskutil info "$volume" | grep -Eq 'File System Personality: +Case-sensitive APFS'
test -f "$archive"
if [ ! -d "$source" ]; then
    mkdir "$stage"
    tar -xzf "$archive" -C "$stage" --strip-components 1
    for tracked in include/linux/bpf.h include/uapi/linux/bpf.h kernel/bpf/syscall.c kernel/bpf/verifier.c; do
        cmp "$stage/$tracked" "$run/baseline/$tracked"
    done
    cmp "$stage/tb371fc/config-v2.2.txt" "$run/config-v2.2.txt"
    mv "$stage" "$source"
fi

mkdir -p "$out"
if [ ! -e "$out/.config" ]; then
    cp "$run/config-from-boot-789.txt" "$out/.config"
fi
PATH="$tools:$PATH" make -C "$source" O="$out" ARCH=arm64 LLVM=1 LLVM_IAS=1 \
    CROSS_COMPILE=aarch64-linux-gnu- CC=clang HOSTCC=/usr/bin/clang HOSTCXX=/usr/bin/clang++ \
    PYTHON=python3 PYTHON3=python3 olddefconfig
