#!/system/bin/sh
set -eu
screen=$(cat /sys/class/drm/card0-DSI-1/dpms)
trace=/data/local/tmp/c17-shade.atrace
cleanup() {
    cmd statusbar collapse || true
    if [ "$screen" = Off ]; then input keyevent KEYCODE_SLEEP; fi
}
trap cleanup EXIT
input keyevent KEYCODE_WAKEUP
sleep 2
cmd statusbar collapse
sleep 1
atrace --async_start -b 32768 gfx view wm am dalvik sched freq binder_driver
for cycle in 1 2 3 4 5 6; do
    cmd statusbar expand-settings
    sleep .40
    cmd statusbar collapse
    sleep .40
done
atrace --async_stop gfx view wm am dalvik sched freq binder_driver > "$trace"
