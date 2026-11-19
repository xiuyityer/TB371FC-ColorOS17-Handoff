#!/system/bin/sh
set -eu
stage=/data/local/tmp/c17-run0019/provider
mount -o bind "$stage/bin" /vendor/bin/r94-commcenter
mount -o bind "$stage/lib64" /vendor/lib64/r94-commcenter
export LD_LIBRARY_PATH=/vendor/lib64/r94-commcenter
printf '\n== daemon ==\n'
/system/bin/linker64 --list /vendor/bin/r94-commcenter/subsys_daemon
printf '\n== daemon with virtual provider ==\n'
LD_PRELOAD=/vendor/lib64/r94-commcenter/lib-virtual-modem-radio-aidl.so /system/bin/linker64 --list /vendor/bin/r94-commcenter/subsys_daemon
printf '\n== donor communication center ==\n'
/system/bin/linker64 --list /vendor/bin/r94-commcenter/commcenterd
