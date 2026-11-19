#!/system/bin/sh
set -eu
stage=/data/adb/c17-run0019
[ ! -e "$stage" ]
mkdir -m 0755 "$stage"
cp -R /data/local/tmp/c17-run0019/provider/lib64 "$stage/lib64"
chown -R 0:0 "$stage"
chmod 0755 "$stage/lib64"
chmod 0644 "$stage"/lib64/*
chcon -R u:object_r:vendor_file:s0 "$stage/lib64"
nsenter -t 1 -m -- mount --bind "$stage/lib64" /vendor/lib64/r94-commcenter
setprop ctl.start r94-commcenterd
setprop ctl.start c17-virtual-ril-0
setprop ctl.start c17-virtual-ril-1
