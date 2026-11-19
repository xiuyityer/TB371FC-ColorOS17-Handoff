#!/system/bin/sh
set -eu
original=$(cat /sys/class/drm/card0-DSI-1/dpms)
cleanup() {
    cmd statusbar collapse || true
    if [ "$original" = Off ]; then input keyevent KEYCODE_SLEEP; fi
}
trap cleanup EXIT
input keyevent KEYCODE_WAKEUP
sleep 2
cmd statusbar collapse
sleep 1
for round in 1 2 3; do
    printf '\n=== ROUND %s ===\n' "$round"
    dumpsys gfxinfo com.android.systemui reset >/dev/null
    for cycle in 1 2 3 4 5 6; do
        cmd statusbar expand-settings
        sleep .40
        cmd statusbar collapse
        sleep .40
    done
    dumpsys gfxinfo com.android.systemui framestats
done
