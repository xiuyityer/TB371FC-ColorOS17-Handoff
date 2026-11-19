#!/bin/sh
# Compile ringbuf and its entry points with the Darwin host adaptations.
set -eu

run=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workspace=$(CDPATH='' cd -- "$run/../../.." && pwd)
src="$run/kernel-build-volume/kernel-v2.2"
out="$run/kernel-build-volume/obj-baseline"
llvm="$workspace/host-tools/android-ndk-r27d/toolchains/llvm/prebuilt/darwin-x86_64/bin"
openssl="$workspace/host-tools/openssl-3.5.9"

test -f "$out/.config"
test -f "$openssl/libcrypto.a"
PATH="$llvm:$PATH" make -j4 -C "$src" O="$out" ARCH=arm64 LLVM=1 LLVM_IAS=1 \
    CROSS_COMPILE=aarch64-linux-gnu- CC=clang HOSTCC=/usr/bin/clang HOSTCXX=/usr/bin/clang++ \
    "HOSTCFLAGS=-I$workspace/tools/host-include -I$out/arch/arm64/include/generated/uapi -I$src/arch/arm64/include/uapi -I$src/include/uapi" \
    "CRYPTO_CFLAGS=-I$openssl/include" "CRYPTO_LIBS=$openssl/libcrypto.a" \
    PYTHON=python3 PYTHON3=python3 kernel/bpf/syscall.o kernel/bpf/verifier.o kernel/bpf/ringbuf.o net/core/filter.o
"$llvm/llvm-readelf" -h "$out/kernel/bpf/syscall.o" "$out/kernel/bpf/verifier.o" "$out/kernel/bpf/ringbuf.o" "$out/net/core/filter.o" | grep -E 'Type:|Machine:'
