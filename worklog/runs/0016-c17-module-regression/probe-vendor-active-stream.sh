#!/system/bin/sh
set -eu
screen=$(cat /sys/class/drm/card0-DSI-1/dpms)
playback=
cleanup() {
    if [ -n "$playback" ]; then kill "$playback" 2>/dev/null || true; fi
    if [ "$screen" = Off ]; then input keyevent KEYCODE_SLEEP; fi
}
trap cleanup EXIT
input keyevent KEYCODE_WAKEUP
sleep .5
/data/local/tmp/c17-speaker-probe &
playback=$!
sleep .7
for rot in 90 270 90; do
    date -Iseconds
    /data/local/tmp/c17-send-vendor-rotation "$rot"
    /system/bin/tinymix -D 0 'TFA9894_CHAN_SELECTOR'
    sleep .45
done
wait "$playback"
playback=
