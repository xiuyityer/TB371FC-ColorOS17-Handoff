#!/bin/sh
# Build the kernel with Darwin host tools. This does not package or flash boot.
set -eu

run=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workspace=$(CDPATH='' cd -- "$run/../../.." && pwd)
src="$run/kernel-build-volume/kernel-v2.2"
out="$run/kernel-build-volume/obj-baseline"
llvm="$workspace/host-tools/android-ndk-r27d/toolchains/llvm/prebuilt/darwin-x86_64/bin"
openssl="$workspace/host-tools/openssl-3.5.9"

sed_dir="$workspace/host-tools/sed-4.9/sed"

test -f "$out/.config"
test -x "$sed_dir/sed"
test -f "$openssl/libcrypto.a"

# Match the links created by the vendor audio Makefile.am for standalone builds.
for entry in \
    'techpack/audio/soc/core.h:../../../drivers/pinctrl/core.h' \
    'techpack/audio/soc/pinctrl-utils.h:../../../drivers/pinctrl/pinctrl-utils.h' \
    'techpack/audio/include/soc/internal.h:../../../../drivers/base/regmap/internal.h'
do
    link="$src/${entry%%:*}"
    target="${entry#*:}"
    test -f "$(dirname "$link")/$target"
    if [ -L "$link" ]; then
        current=$(readlink "$link")
        if [ "$current" != "$target" ]; then
            vendor="/home/smith/kernels/tb371fc/android_kernel_lenovo_tb371fc/drivers/${target#*drivers/}"
            test "$current" = "$vendor"
            ln -sfn "$target" "$link"
        fi
    else
        test ! -e "$link"
        ln -s "$target" "$link"
    fi
done
PATH="$sed_dir:$llvm:$PATH" make -j4 -C "$src" O="$out" ARCH=arm64 LLVM=1 LLVM_IAS=1 \
    CROSS_COMPILE=aarch64-linux-gnu- CC=clang HOSTCC=/usr/bin/clang HOSTCXX=/usr/bin/clang++ \
    "HOSTCFLAGS=-I$workspace/tools/host-include -I$out/arch/arm64/include/generated/uapi -I$src/arch/arm64/include/uapi -I$src/include/uapi" \
    "CRYPTO_CFLAGS=-I$openssl/include" "CRYPTO_LIBS=$openssl/libcrypto.a" \
    PYTHON=python3 PYTHON3=python3 DYNAMIC_SINGLE_CHIP=qca6390 Image
test -s "$out/arch/arm64/boot/Image"
