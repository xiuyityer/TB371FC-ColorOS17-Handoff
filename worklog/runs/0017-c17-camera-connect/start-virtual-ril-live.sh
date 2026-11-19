#!/system/bin/sh
set -eu
source=/data/adb/c17-virtual-radio
[ ! -e "$source" ]
[ -e /sys/class/net/ovnet0 ]
[ "$(sha256sum /data/local/tmp/c17-virtual-radio/bin/commcenterd | cut -d ' ' -f1)" = "$(sha256sum /vendor/bin/r94-commcenter/commcenterd | cut -d ' ' -f1)" ]
cp -R /data/local/tmp/c17-virtual-radio "$source"
chown -R 0:0 "$source"
chmod 0755 "$source" "$source/bin" "$source/lib64" "$source"/bin/*
chmod 0644 "$source"/lib64/*
chcon -R u:object_r:vendor_file:s0 "$source"
mount --bind "$source/bin" /vendor/bin/r94-commcenter
mount --bind "$source/lib64" /vendor/lib64/r94-commcenter
/system/bin/linker64 --list /vendor/bin/r94-commcenter/subsys_daemon
cd /
su -Z u:r:rild:s0 -g 1001 -G 1001 -G 2001 -G 3003 -G 9998 -G 1005 -G 1007 -G 3009 -G 3010 1001 -c 'exec /vendor/bin/r94-commcenter/subsys_daemon -l /vendor/lib64/r94-commcenter/lib-virtual-modem-radio.so -i 0'
