#!/bin/sh
# Compile the isolated file-operations patch against the prepared #789 headers.
set -eu

run=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workspace=$(CDPATH='' cd -- "$run/../../.." && pwd)
kernel="$workspace/casefs/kernel-v2.2"
llvm="$workspace/host-tools/android-ndk-r27d/toolchains/llvm/prebuilt/darwin-x86_64/bin"
clang="$llvm/clang"

test -f "$kernel/include/generated/autoconf.h"
test -x "$clang"
cd "$kernel"
resource=$("$clang" -print-resource-dir)
for source in baseline review-tree; do
    "$clang" --target=aarch64-linux-gnu -nostdinc -isystem "$resource/include" \
        -Iarch/arm64/include -Iarch/arm64/include/generated -I"$run/$source/include" -Iinclude \
        -Iarch/arm64/include/uapi -Iarch/arm64/include/generated/uapi -Iinclude/uapi -Iinclude/generated/uapi \
        -include include/linux/kconfig.h -include include/linux/compiler_types.h -D__KERNEL__ \
        -DKBUILD_MODNAME='"bpf_syscall"' -DKBUILD_BASENAME='"syscall"' -std=gnu89 -O2 \
        -fno-pie -fno-strict-aliasing -fno-asynchronous-unwind-tables -fno-delete-null-pointer-checks \
        -fshort-wchar -mno-implicit-float -Werror=implicit-function-declaration -Werror=return-type \
        -c "$run/$source/kernel/bpf/syscall.c" -o "$run/$source-syscall.o" \
        >"$run/$source-compile.txt" 2>&1
done
"$llvm/llvm-nm" "$run/review-tree-syscall.o" | grep -E 'bpf_map_(poll|mmap|fops)$'
