#!/system/bin/sh
set -eu
old_min=$(settings get system min_refresh_rate)
old_peak=$(settings get system peak_refresh_rate)
old_oem=$(settings get secure oplus_customize_screen_refresh_rate)
old_pen=$(settings get global settings_enable_oppo_pencil)
old_mode=$(cmd display get-user-preferred-display-mode 0)
old_screen=$(cat /sys/class/drm/card0-DSI-1/dpms)
restore_setting() {
    if [ "$3" = null ]; then settings delete "$1" "$2"; else settings put "$1" "$2" "$3"; fi
}
restore() {
    restore_setting system min_refresh_rate "$old_min"
    restore_setting system peak_refresh_rate "$old_peak"
    restore_setting secure oplus_customize_screen_refresh_rate "$old_oem"
    restore_setting global settings_enable_oppo_pencil "$old_pen"
    case "$old_mode" in
        *': -1 -1 0.0'|*': null') cmd display clear-user-preferred-display-mode 0;;
        'User preferred display mode: '*) set -- ${old_mode#User preferred display mode: }; [ "$#" = 3 ] && cmd display set-user-preferred-display-mode "$1" "$2" "$3" 0;;
    esac
    if [ "$old_screen" = Off ]; then input keyevent KEYCODE_SLEEP; fi
}
trap restore EXIT
input keyevent KEYCODE_WAKEUP
sleep 1
report() {
    printf '### %s\n' "$1"
    dumpsys display | sed -n '/DisplayDeviceInfo{.*renderFrameRate/{s/.*modeId \([0-9]*\), renderFrameRate \([0-9.]*\).*/mode=\1 renderFrameRate=\2/p; q;}'
    dumpsys SurfaceFlinger | grep -m4 -E 'activeMode=|active mode|displayManagerPolicy|DisplayManagerPolicy' || true
}
report before
settings put global settings_enable_oppo_pencil 0
settings put secure oplus_customize_screen_refresh_rate 4
settings put system peak_refresh_rate 144.00002
settings put system min_refresh_rate 144.00002
cmd display set-user-preferred-display-mode 1840 2944 144.00002 0
sleep 2
report target144
settings put global settings_enable_oppo_pencil 1
settings put secure oplus_customize_screen_refresh_rate 3
settings put system peak_refresh_rate 120.00001
settings put system min_refresh_rate 120.00001
cmd display set-user-preferred-display-mode 1840 2944 120.00001 0
sleep 2
report target120
