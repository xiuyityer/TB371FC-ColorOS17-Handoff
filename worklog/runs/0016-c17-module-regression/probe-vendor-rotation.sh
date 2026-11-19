#!/system/bin/sh
set -eu
screen=$(cat /sys/class/drm/card0-DSI-1/dpms)
rotation=$(wm user-rotation)
playback=
cleanup() {
    if [ -n "$playback" ]; then kill "$playback" 2>/dev/null || true; fi
    case "$rotation" in
        free*) wm user-rotation free ;;
        'lock '*) wm user-rotation lock "${rotation#lock }" ;;
    esac
    if [ "$screen" = Off ]; then input keyevent KEYCODE_SLEEP; fi
}
trap cleanup EXIT
printf 'initial user_rotation=%s screen=%s\n' "$rotation" "$screen"
input keyevent KEYCODE_WAKEUP
sleep 1
wm user-rotation lock 1
sleep 1
/data/local/tmp/c17-speaker-probe &
playback=$!
for rot in 1 3 1; do
    date -Iseconds
    wm user-rotation lock "$rot"
    sleep 2
    printf 'rotation=%s\n' "$rot"
    /data/local/tmp/c17-send-vendor-rotation "$((rot * 90))"
    sleep .15
    /system/bin/tinymix -D 0 'TFA9894_CHAN_SELECTOR'
    /system/bin/tinymix -D 0 'Swap channel'
    dumpsys input | grep -m2 -E 'SurfaceOrientation:|orientation=ROTATION' || true
    dumpsys media.audio_flinger | grep -iE 'KVP received: rotation=|devices.*SPEAKER|ACTIVE.*MIXER' | tail -13 || true
done
wait "$playback"
playback=
