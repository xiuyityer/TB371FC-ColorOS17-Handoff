#!/system/bin/sh
set -eu
screen=$(cat /sys/class/drm/card0-DSI-1/dpms)
blur=$(settings get global disable_window_blurs)
timeout=$(settings get system screen_off_timeout)
restore_blur() {
    if [ "$blur" = null ]; then settings delete global disable_window_blurs >/dev/null
    else settings put global disable_window_blurs "$blur"; fi
}
cleanup() {
    restore_blur
    if [ "$timeout" = null ]; then settings delete system screen_off_timeout >/dev/null
    else settings put system screen_off_timeout "$timeout"; fi
    cmd statusbar collapse || true
    if [ "$screen" = Off ]; then input keyevent KEYCODE_SLEEP; fi
}
trap cleanup EXIT
settings put system screen_off_timeout 60000
input keyevent KEYCODE_WAKEUP
sleep 2
cmd statusbar collapse
sleep .6
cycles() {
    for i in $(seq "$1"); do
        cmd statusbar expand-settings
        sleep .36
        cmd statusbar collapse
        sleep .36
    done
}
measure() {
    echo "### $1"
    cat /sys/class/drm/card0-DSI-1/dpms
    wm disable-blur
    cycles 2
    dumpsys gfxinfo com.android.systemui reset >/dev/null
    cycles 7
    dumpsys gfxinfo com.android.systemui | awk '
        /\*\* Graphics info/ {keep=(++count==1)}
        keep && /Total frames rendered|Janky frames:|95th percentile|99th percentile|Slow UI thread|Slow issue draw commands/ {print}
    '
}
measure A1
wm disable-blur 1
sleep .6
measure B
restore_blur
sleep .6
measure A2
