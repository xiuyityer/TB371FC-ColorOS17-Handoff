#!/system/bin/sh
set -eu
stage=/data/adb/c17-run0019-ims
[ ! -e "$stage" ]
mkdir -m 0755 "$stage"
cp -a /odm/lib64 "$stage/odm"
cp -a /vendor/lib64/r94-commcenter "$stage/vendor"
shared=/data/local/tmp/c17-run0019/provider/lib64
install -m 0644 "$shared/lib-virtual-modem-qti-ims-aidl.so" "$stage/odm/"
install -m 0644 "$shared/vendor.qti.hardware.radio.ims-V7-ndk.so" "$shared/vendor.qti.hardware.radio.qtiradioconfig-V2-ndk.so" "$stage/vendor/"
chcon u:object_r:vendor_file:s0 "$stage/odm/lib-virtual-modem-qti-ims-aidl.so" "$stage"/vendor/vendor.qti.hardware.radio*.so
nsenter -t 1 -m -- mount --bind "$stage/vendor" /vendor/lib64/r94-commcenter
nsenter -t 1 -m -- mount --bind "$stage/odm" /odm/lib64
setprop ctl.start c17-virtual-ril-0
setprop ctl.start c17-virtual-ril-1
